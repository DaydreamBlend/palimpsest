"""BGE wire/coverage guards with synthetic vectors, never model quality claims."""

from copy import deepcopy
from hashlib import sha256
import unittest

from palimpsest.bge_retrieval import (BgeM3, MODEL_FILES, MODEL_ID, REVISION, VERSIONS, digest,
    token_windows, validate_request, validate_profile, validate_embedding_result, validate_rerank_result)
from palimpsest.errors import PalimpsestError


class CharacterTokenizer:
    """Explicit synthetic tokenizer: each non-whitespace character is one token."""
    def num_special_tokens_to_add(self, pair=False):
        return 2

    def __call__(self, text, *, add_special_tokens=True, truncation=False, return_offsets_mapping=False):
        assert truncation is False
        offsets = [(i, i + 1) for i, character in enumerate(text) if not character.isspace()]
        result = {'input_ids': list(range(len(offsets) + (2 if add_special_tokens else 0)))}
        if return_offsets_mapping:
            result['offset_mapping'] = offsets
        return result


def profile():
    manifest = {name: {'sha256': expected if algorithm == 'sha256' else '0' * 64, 'byte_size': size}
                for name, (algorithm, expected, size) in MODEL_FILES.items()}
    return {'model_id': MODEL_ID, 'revision': REVISION, 'dimensions': 1024, 'pooling': 'cls',
        'normalization': 'l2', 'distance_metric': 'cosine', 'scoring': 'colbert_late_interaction',
        'score_transform': 'mean_query_token_max_dot', 'colbert_tokens': 'exclude_cls_and_padding_include_eos',
        'max_tokens': 512, 'overlap_tokens': 64, 'input_projection': 'exact_char_windows_v1',
        'query_instruction': '', 'document_instruction': '', 'precision': 'float32', 'device': 'cpu',
        'runtime': VERSIONS, 'adapter': 'bge_m3_transformers_v1', 'attention': 'eager',
        'adapter_sha256': 'a' * 64, 'model_files': manifest, 'model_files_sha256': digest(manifest),
        'deterministic_algorithms': True, 'cross_device_bitwise_reproducible': False}


def synthetic_embedding():
    request = {'schema_version': 'wiki-embedding-request-v1', 'documents': [
        {'document_id': 'first', 'text': '  α μ Caf\u0065\u0301 한글\n' * 100},
        {'document_id': 'second', 'text': 'Second synthetic source.'}]}
    worker = BgeM3.__new__(BgeM3)
    worker.tokenizer, worker.profile = CharacterTokenizer(), profile()
    worker._encode = lambda texts: [[1.0, *([0.0] * 1023)] for _ in texts]
    return request, worker.encode(request)


class BgeRetrievalTests(unittest.TestCase):
    def test_windows_cover_every_original_character_and_retokenize_without_truncation(self):
        text = ' \t' + ('α μ e\u0301 한글.\n' * 40) + '   '
        tokenizer = CharacterTokenizer()
        windows = token_windows(text, tokenizer, max_tokens=14, overlap_tokens=4)
        self.assertGreater(len(windows), 2)
        covered, previous = 0, -1
        for window in windows:
            start, end = window['char_start'], window['char_end']
            self.assertLess(previous, start)
            self.assertLessEqual(start, covered)
            self.assertGreater(end, covered)
            substring = text[start:end]
            self.assertLessEqual(len(tokenizer(substring)['input_ids']), 14)
            self.assertEqual(window['text_sha256'], sha256(substring.encode()).hexdigest())
            previous, covered = start, end
        self.assertEqual(covered, len(text))
        self.assertEqual(windows[0]['char_start'], 0)
        self.assertTrue(any(b['char_start'] < a['char_end'] for a, b in zip(windows, windows[1:])))

    def test_window_edge_cases_reject_empty_and_unencodable_or_invalid_policy(self):
        for text in ('', '  \n', '\x00invalid'):
            with self.subTest(text=repr(text)), self.assertRaises(PalimpsestError):
                token_windows(text, CharacterTokenizer())
        for options in ({'max_tokens': 2}, {'max_tokens': 8, 'overlap_tokens': 6}, {'max_tokens': '512'}):
            with self.subTest(options=options), self.assertRaises(PalimpsestError):
                token_windows('Source text', CharacterTokenizer(), **options)

    def test_encode_wire_keeps_order_all_ranges_and_model_profile(self):
        request, result = synthetic_embedding()
        self.assertEqual(result['input_sha256'], digest(request))
        self.assertEqual([r['document_id'] for r in result['documents']], ['first', 'second'])
        self.assertGreater(len(result['documents'][0]['chunks']), 1)
        self.assertEqual(result['profile']['scoring'], 'colbert_late_interaction')
        validate_embedding_result(request, result)

    def test_changed_input_gaps_tail_loss_vectors_and_profiles_are_rejected(self):
        request, original = synthetic_embedding()
        def bad_gap(value):
            value['documents'][0]['chunks'][1]['char_start'] = value['documents'][0]['chunks'][0]['char_end'] + 1
        mutations = [bad_gap, lambda v: v['documents'][0]['chunks'].pop(),
            lambda v: v['documents'][0]['chunks'][0]['dense'].pop(),
            lambda v: v['documents'][0]['chunks'][0]['dense'].__setitem__(0, float('nan')),
            lambda v: v['documents'][0]['chunks'][0].update(text_sha256='0' * 64),
            lambda v: v['profile'].update(scoring='dense_similarity'),
            lambda v: v.update(input_sha256='0' * 64)]
        for mutate in mutations:
            value = deepcopy(original)
            mutate(value)
            with self.assertRaises(PalimpsestError):
                validate_embedding_result(request, value)

    def test_ids_and_source_text_must_be_nonempty_and_unique(self):
        request, _ = synthetic_embedding()
        request['documents'].append(deepcopy(request['documents'][0]))
        with self.assertRaises(PalimpsestError):
            validate_request(request, 'encode')
        request['documents'].pop()
        request['documents'][1]['text'] = ''
        with self.assertRaises(PalimpsestError):
            validate_request(request, 'encode')

    def test_rerank_wire_requires_exact_profile_id_order_and_finite_scores(self):
        request = {'schema_version': 'wiki-rerank-request-v1', 'query': 'synthetic query', 'profile': profile(),
                   'passages': [{'chunk_id': 'a', 'text': 'first'}, {'chunk_id': 'b', 'text': 'second'}]}
        result = {'schema_version': 'wiki-rerank-result-v1', 'input_sha256': digest(request),
                  'profile': deepcopy(request['profile']),
                  'scores': [{'chunk_id': 'a', 'score': -0.15}, {'chunk_id': 'b', 'score': 0.72}]}
        validate_rerank_result(request, result)
        for mutation in (lambda v: v['scores'].reverse(), lambda v: v['scores'][0].update(score=float('inf')),
                         lambda v: v['profile'].update(device='cuda')):
            changed = deepcopy(result)
            mutation(changed)
            with self.assertRaises(PalimpsestError):
                validate_rerank_result(request, changed)

    def test_profile_rejects_changed_weights_runtime_or_cross_encoder(self):
        for mutation in (lambda v: v.update(model_id='BAAI/bge-reranker-v2-m3'),
                         lambda v: v['runtime'].update(transformers='other'),
                         lambda v: v['model_files']['colbert_linear.pt'].update(sha256='0' * 64)):
            changed = deepcopy(profile())
            mutation(changed)
            with self.assertRaises(PalimpsestError):
                validate_profile(changed)

    def test_rerank_rejects_overlong_query_or_passage_before_encoding(self):
        worker = BgeM3.__new__(BgeM3)
        worker.profile, worker.tokenizer = profile(), CharacterTokenizer()
        worker._encode = lambda *args, **kwargs: self.fail('Overlong input must not be encoded or truncated')
        for query, passage in (('x' * 511, 'short'), ('short', 'x' * 511)):
            request = {'schema_version': 'wiki-rerank-request-v1', 'profile': worker.profile,
                       'query': query, 'passages': [{'chunk_id': 'chunk', 'text': passage}]}
            with self.assertRaises(PalimpsestError) as caught:
                worker.rerank(request)
            self.assertEqual(caught.exception.code, 'retrieval_input_too_long')


if __name__ == '__main__':
    unittest.main()
