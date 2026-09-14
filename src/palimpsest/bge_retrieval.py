"""Pinned local BGE-M3 dense/ColBERT inference with complete source windows.

Torch/Transformers are imported only by the optional worker, never by the app.
Math follows FlagOpen's M3 CLS pooling, learned token projection and mean-MaxSim.
"""

from hashlib import sha1, sha256
import json
import math
from pathlib import Path

from .errors import PalimpsestError


MODEL_ID = 'BAAI/bge-m3'
REVISION = '5617a9f61b028005a4858fdac845db406aefb181'
DIMENSIONS = 1024
MAX_TOKENS = 512
OVERLAP_TOKENS = 64
VERSIONS = {'torch': '2.8.0', 'transformers': '4.57.6', 'tokenizers': '0.22.2',
            'safetensors': '0.8.0', 'huggingface-hub': '0.36.2'}
# Official Hub API metadata for the exact revision. Small files use Git blob IDs.
MODEL_FILES = {
    'pytorch_model.bin': ('sha256', 'b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38', 2271145830),
    'colbert_linear.pt': ('sha256', '19bfbae397c2b7524158c919d0e9b19393c5639d098f0a66932c91ed8f5f9abb', 2100674),
    'sentencepiece.bpe.model': ('sha256', 'cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865', 5069051),
    'tokenizer.json': ('sha256', '21106b6d7dab2952c1d496fb21d5dc9db75c28ed361a05f5020bbba27810dd08', 17098108),
    'config.json': ('git_sha1', 'e6eda1c72da8f9dc30fdd9b69c73d35af3b7a7ad', 687),
    'tokenizer_config.json': ('git_sha1', 'dc69ac559dcba2694012009aaa108c614541789a', 444),
    'special_tokens_map.json': ('git_sha1', 'b1879d702821e753ffe4245048eee415d54a9385', 964),
}


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _fail(code='invalid_retrieval_input'):
    raise PalimpsestError(code, '검색 모델 profile·입력·완전한 문자 범위·결과를 확인하세요.', 4)


def _text(value):
    if not isinstance(value, str) or not value.strip() or '\x00' in value:
        _fail()
    try:
        value.encode('utf-8')
    except UnicodeEncodeError:
        _fail()
    return value


def validate_request(request, operation):
    collection, identifier = ('documents', 'document_id') if operation == 'encode' else ('passages', 'chunk_id')
    expected = {'schema_version', collection} if operation == 'encode' else {'schema_version', 'query', 'passages', 'profile'}
    version = 'wiki-embedding-request-v1' if operation == 'encode' else 'wiki-rerank-request-v1'
    if (operation not in ('encode', 'rerank') or not isinstance(request, dict) or set(request) != expected
            or request['schema_version'] != version or not isinstance(request[collection], list)
            or not request[collection]):
        _fail()
    if operation == 'rerank':
        _text(request['query'])
        validate_profile(request['profile'])
    seen = set()
    for row in request[collection]:
        if not isinstance(row, dict) or set(row) != {identifier, 'text'}:
            _fail()
        key = _text(row[identifier])
        _text(row['text'])
        if key in seen:
            _fail('duplicate_retrieval_document')
        seen.add(key)
    return request


def validate_profile(profile):
    if (not isinstance(profile, dict) or profile.get('model_id') != MODEL_ID or profile.get('revision') != REVISION
            or profile.get('dimensions') != DIMENSIONS or profile.get('pooling') != 'cls'
            or profile.get('normalization') != 'l2' or profile.get('scoring') != 'colbert_late_interaction'
            or profile.get('max_tokens') != MAX_TOKENS or profile.get('overlap_tokens') != OVERLAP_TOKENS
            or profile.get('input_projection') != 'exact_char_windows_v1'
            or profile.get('precision') != 'float32' or profile.get('device') not in ('cpu', 'cuda')
            or profile.get('runtime') != VERSIONS
            or profile.get('adapter') != 'bge_m3_transformers_v1'
            or profile.get('distance_metric') != 'cosine'
            or profile.get('score_transform') != 'mean_query_token_max_dot'
            or profile.get('colbert_tokens') != 'exclude_cls_and_padding_include_eos'
            or profile.get('attention') != 'eager' or profile.get('deterministic_algorithms') is not True
            or profile.get('cross_device_bitwise_reproducible') is not False
            or profile.get('query_instruction') != '' or profile.get('document_instruction') != ''):
        _fail('retrieval_profile_mismatch')
    manifest = profile.get('model_files')
    if (not isinstance(manifest, dict) or set(manifest) != set(MODEL_FILES)
            or profile.get('model_files_sha256') != digest(manifest)
            or not isinstance(profile.get('adapter_sha256'), str) or len(profile['adapter_sha256']) != 64):
        _fail('retrieval_profile_mismatch')
    for name, (algorithm, expected, size) in MODEL_FILES.items():
        item = manifest[name]
        if (not isinstance(item, dict) or set(item) != {'sha256', 'byte_size'} or item['byte_size'] != size
                or not isinstance(item['sha256'], str) or len(item['sha256']) != 64
                or any(c not in '0123456789abcdef' for c in item['sha256'])
                or (algorithm == 'sha256' and item['sha256'] != expected)):
            _fail('retrieval_profile_mismatch')
    return profile


def token_windows(text, tokenizer, *, max_tokens=MAX_TOKENS, overlap_tokens=OVERLAP_TOKENS):
    """Return exact character ranges with no gaps, checked without truncation.

    Offsets propose boundaries; every resulting substring is tokenized again.
    This catches tokenization changes at a window boundary and retains spaces.
    """
    _text(text)
    if type(max_tokens) is not int or type(overlap_tokens) is not int:
        _fail('invalid_retrieval_window')
    special = tokenizer.num_special_tokens_to_add(pair=False)
    budget = max_tokens - special
    if not 0 <= overlap_tokens < budget:
        _fail('invalid_retrieval_window')
    tokens = tokenizer(text, add_special_tokens=False, truncation=False, return_offsets_mapping=True)
    offsets = tokens['offset_mapping']
    if not offsets or len(offsets) != len(tokens['input_ids']):
        _fail('retrieval_text_unencodable')
    if any(not (0 <= start <= end <= len(text)) for start, end in offsets):
        _fail('invalid_retrieval_token_offsets')
    index, start, result = 0, 0, []
    while start < len(text):
        limit = min(len(offsets), index + budget)
        while limit > index:
            end = len(text) if limit == len(offsets) else offsets[limit][0]
            ids = tokenizer(text[start:end], add_special_tokens=True, truncation=False)['input_ids']
            if end > start and len(ids) <= max_tokens:
                break
            limit -= 1
        else:
            _fail('retrieval_window_unencodable')
        result.append({'char_start': start, 'char_end': end,
                       'text_sha256': sha256(text[start:end].encode()).hexdigest()})
        if end == len(text):
            break
        next_index = max(index + 1, limit - overlap_tokens)
        while next_index < len(offsets) and offsets[next_index][0] <= start:
            next_index += 1
        if next_index >= len(offsets) or offsets[next_index][0] > end:
            _fail('retrieval_window_coverage')
        index, start = next_index, offsets[next_index][0]
    return result


def _vector(vector):
    if (not isinstance(vector, list) or len(vector) != DIMENSIONS
            or any(type(value) not in (int, float) or not math.isfinite(value) for value in vector)
            or abs(sum(value * value for value in vector) - 1.0) > 1e-4):
        _fail('invalid_retrieval_vector')


def validate_embedding_result(request, result):
    validate_request(request, 'encode')
    if (not isinstance(result, dict) or set(result) != {'schema_version', 'input_sha256', 'profile', 'documents'}
            or result['schema_version'] != 'wiki-embedding-result-v1' or result['input_sha256'] != digest(request)
            or not isinstance(result['documents'], list) or len(result['documents']) != len(request['documents'])):
        _fail('invalid_embedding_result')
    validate_profile(result['profile'])
    for source, row in zip(request['documents'], result['documents'], strict=True):
        text = source['text']
        if (not isinstance(row, dict) or set(row) != {'document_id', 'text_sha256', 'chunks'} or row['document_id'] != source['document_id']
                or row['text_sha256'] != sha256(text.encode()).hexdigest()
                or not isinstance(row['chunks'], list) or not row['chunks']):
            _fail('invalid_embedding_result')
        covered, previous_start = 0, -1
        for chunk in row['chunks']:
            if not isinstance(chunk, dict) or set(chunk) != {'char_start', 'char_end', 'text_sha256', 'dense'}:
                _fail('invalid_embedding_result')
            start, end = chunk['char_start'], chunk['char_end']
            if (type(start) is not int or type(end) is not int or not previous_start < start <= covered < end <= len(text)
                    or chunk['text_sha256'] != sha256(text[start:end].encode()).hexdigest()):
                _fail('retrieval_window_coverage')
            _vector(chunk['dense'])
            previous_start, covered = start, end
        if covered != len(text):
            _fail('retrieval_window_coverage')
    return result


def validate_rerank_result(request, result):
    validate_request(request, 'rerank')
    if (not isinstance(result, dict) or set(result) != {'schema_version', 'input_sha256', 'profile', 'scores'}
            or result['schema_version'] != 'wiki-rerank-result-v1' or result['input_sha256'] != digest(request)
            or result['profile'] != request['profile'] or not isinstance(result['scores'], list)
            or len(result['scores']) != len(request['passages'])):
        _fail('invalid_rerank_result')
    for passage, score in zip(request['passages'], result['scores'], strict=True):
        if (not isinstance(score, dict) or set(score) != {'chunk_id', 'score'} or score['chunk_id'] != passage['chunk_id']
                or type(score['score']) not in (int, float) or not math.isfinite(score['score'])):
            _fail('invalid_rerank_result')
    return result


def verify_model(model_path):
    root = Path(model_path).resolve(strict=True)
    manifest = {}
    for name, (algorithm, expected, size) in MODEL_FILES.items():
        path = root / name
        if not path.is_file() or path.is_symlink() or path.stat().st_size != size:
            _fail('bge_model_files_missing')
        checksum = sha256()
        blob = sha1(f'blob {size}\0'.encode()) if algorithm == 'git_sha1' else None
        with path.open('rb') as stream:
            while chunk := stream.read(8 * 1024 * 1024):
                checksum.update(chunk)
                if blob:
                    blob.update(chunk)
        if (blob.hexdigest() if blob else checksum.hexdigest()) != expected:
            _fail('bge_model_hash_mismatch')
        manifest[name] = {'sha256': checksum.hexdigest(), 'byte_size': size}
    return manifest


class BgeM3:
    """A local worker; no implicit download, provider or semantic authority."""
    def __init__(self, model_path, *, device='cpu'):
        from importlib.metadata import version
        import torch
        from transformers import AutoModel, AutoTokenizer
        if device not in ('cpu', 'cuda') or (device == 'cuda' and not torch.cuda.is_available()):
            _fail('retrieval_device_unavailable')
        versions = {name: version(name) for name in VERSIONS}
        if versions != VERSIONS:
            _fail('retrieval_runtime_mismatch')
        manifest = verify_model(model_path)
        self.torch, self.device = torch, device
        torch.set_num_threads(4)
        torch.use_deterministic_algorithms(True)
        torch.backends.cuda.matmul.allow_tf32 = False
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=True, local_files_only=True, trust_remote_code=False)
        if not self.tokenizer.is_fast:
            _fail('retrieval_fast_tokenizer_required')
        self.model = AutoModel.from_pretrained(model_path, local_files_only=True, trust_remote_code=False,
                                              torch_dtype=torch.float32, attn_implementation='eager').to(device).eval()
        if self.model.config.hidden_size != DIMENSIONS:
            _fail('retrieval_dimensions_mismatch')
        self.colbert = torch.nn.Linear(DIMENSIONS, DIMENSIONS)
        self.colbert.load_state_dict(torch.load(Path(model_path) / 'colbert_linear.pt', map_location='cpu', weights_only=True))
        self.colbert.to(device).eval()
        self.profile = {'model_id': MODEL_ID, 'revision': REVISION, 'dimensions': DIMENSIONS,
            'pooling': 'cls', 'normalization': 'l2', 'distance_metric': 'cosine',
            'scoring': 'colbert_late_interaction', 'score_transform': 'mean_query_token_max_dot',
            'colbert_tokens': 'exclude_cls_and_padding_include_eos', 'max_tokens': MAX_TOKENS,
            'overlap_tokens': OVERLAP_TOKENS, 'input_projection': 'exact_char_windows_v1',
            'query_instruction': '', 'document_instruction': '', 'precision': 'float32', 'device': device,
            'runtime': versions, 'adapter': 'bge_m3_transformers_v1', 'attention': 'eager',
            'adapter_sha256': sha256(Path(__file__).read_text(encoding='utf-8').encode()).hexdigest(),
            'model_files_sha256': digest(manifest), 'model_files': manifest,
            'deterministic_algorithms': True, 'cross_device_bitwise_reproducible': False}

    def _encode(self, texts, *, colbert=False):
        inputs = self.tokenizer(texts, padding=True, truncation=False, return_tensors='pt', return_token_type_ids=False)
        if inputs['input_ids'].shape[1] > MAX_TOKENS:
            _fail('retrieval_input_too_long')
        inputs = inputs.to(self.device)
        with self.torch.inference_mode():
            hidden = self.model(**inputs).last_hidden_state
            if not colbert:
                return self.torch.nn.functional.normalize(hidden[:, 0], p=2, dim=-1).cpu().tolist()
            vectors = self.torch.nn.functional.normalize(self.colbert(hidden[:, 1:]), p=2, dim=-1)
            return [vectors[index, :int(mask.sum().item()) - 1] for index, mask in enumerate(inputs['attention_mask'])]

    def encode(self, request):
        validate_request(request, 'encode')
        documents = []
        for document in request['documents']:
            text = document['text']
            chunks = token_windows(text, self.tokenizer)
            for index in range(0, len(chunks), 8):
                batch = chunks[index:index + 8]
                dense = self._encode([text[c['char_start']:c['char_end']] for c in batch])
                for chunk, vector in zip(batch, dense, strict=True):
                    chunk['dense'] = vector
            documents.append({'document_id': document['document_id'], 'text_sha256': sha256(text.encode()).hexdigest(),
                              'chunks': chunks})
        return validate_embedding_result(request, {'schema_version': 'wiki-embedding-result-v1',
            'input_sha256': digest(request), 'profile': self.profile, 'documents': documents})

    def rerank(self, request):
        validate_request(request, 'rerank')
        if request['profile'] != self.profile:
            _fail('retrieval_profile_mismatch')
        # Rerank receives the exact already-windowed passage. Never truncate or
        # silently replace ColBERT with a max/mean of independently cut passages.
        texts = [request['query'], *[row['text'] for row in request['passages']]]
        if any(len(self.tokenizer(text, truncation=False)['input_ids']) > MAX_TOKENS for text in texts):
            _fail('retrieval_input_too_long')
        query = self._encode([request['query']], colbert=True)[0]
        scores = []
        for start in range(0, len(request['passages']), 8):
            batch = request['passages'][start:start + 8]
            for passage, vectors in zip(batch, self._encode([row['text'] for row in batch], colbert=True), strict=True):
                score = (query @ vectors.T).max(dim=1).values.mean().item()
                scores.append({'chunk_id': passage['chunk_id'], 'score': score})
        return validate_rerank_result(request, {'schema_version': 'wiki-rerank-result-v1',
            'input_sha256': digest(request), 'profile': self.profile, 'scores': scores})
