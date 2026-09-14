"""Read-only page and adjacent-page views of immutable source Information."""

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
import math
from uuid import UUID

from .errors import PalimpsestError


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def _fail(code='invalid_page_projection'):
    raise PalimpsestError(code, '페이지와 원문 Information 참조를 확인하세요.', 4)


def build_pages(bundle, information_rows):
    """Join exact block text by retained parser order; retain source mapping.

    Figure primary assets stay separate from original text. A cross-page I has
    one processing owner, the earliest page of its original source blocks.
    """
    if isinstance(bundle, dict) and bundle.get('coordinate_system') == 'text_ranges':
        _fail('pdf_page_view_required')
    if (not isinstance(bundle, dict) or bundle.get('schema_version') != 1
            or bundle.get('coordinate_system') != 'pdf_points_top_left'):
        _fail()
    paddle = bundle.get('reading_order_source') == 'paddleocr'
    index_key = 'paddleocr_index' if paddle else 'mineru_index'
    pages = bundle.get('pages', [])
    blocks = bundle.get('blocks', [])
    if (not pages or [p.get('page_index') for p in pages] != list(range(len(pages)))
            or not isinstance(information_rows, list)):
        _fail()
    by_id = {b['block_id']:b for b in blocks}
    if len(by_id) != len(blocks):
        _fail()
    primary_ids = {f['block_id'] for f in bundle.get('required_figures', [])}
    for block in blocks:
        if block['block_id'] in primary_ids:
            continue
        index = block.get('upstream_metadata', {}).get('index')
        if type(index) not in (int, float) or (type(index) is float and not math.isfinite(index)):
            _fail('reading_order_unavailable')
    source_hash = _digest(bundle)
    owner_by_block, rows_by_id, information_pages = {}, {}, {}
    for row in information_rows:
        raw_identifier = row.get('information_id')
        if not isinstance(raw_identifier, (str, UUID)) or not str(raw_identifier):
            _fail()
        identifier = str(raw_identifier)
        payload = row.get('payload', {})
        refs = payload.get('source_blocks', [])
        if (not identifier or identifier in rows_by_id or row.get('data_id') != bundle['data_id']
                or payload.get('schema_version') != 'source-information-v1'
                or payload.get('source_bundle_sha256') != source_hash
                or row.get('semantic_type') is not None or not refs):
            _fail()
        source_pages = set()
        for block in refs:
            ref = block['block_id']
            if ref in owner_by_block or by_id.get(ref) != block:
                _fail()
            owner_by_block[ref] = identifier
            if ref not in primary_ids:
                source_pages.add(block['page_index'])
        if not source_pages:
            _fail()
        information_pages[identifier] = sorted(source_pages)
        rows_by_id[identifier] = row
    if set(owner_by_block) != set(by_id):
        _fail()
    output_pages = []
    for page in pages:
        page_index = page['page_index']
        original = [b for b in blocks if b['page_index'] == page_index and b['block_id'] not in primary_ids]
        # Python's stable sort retains the parser array order for tied indices.
        ordered = sorted(original, key=lambda b:b['upstream_metadata']['index'])
        indices = [b['upstream_metadata']['index'] for b in ordered]
        spans, content, page_ids = [], '', []
        for ordinal, block in enumerate(ordered):
            if ordinal:
                content += '\n\n'
            start = len(content)
            content += block['text']
            identifier = owner_by_block[block['block_id']]
            if identifier not in page_ids:
                page_ids.append(identifier)
            spans.append({'block_id':block['block_id'], 'information_id':identifier,
                'source_type':block['type'], 'source_collection':block.get('source_collection'),
                'raw_locator':block['raw_locator'], 'bbox':block['bbox'],
                'anchor_sha256':block['anchor_sha256'], index_key:block['upstream_metadata']['index'],
                'char_start':start, 'char_end':len(content)})
            if 'transcription_selection' in block:
                spans[-1].update(native_text=block['native_text'],
                    native_raw_artifact=deepcopy(block['native_raw_artifact']),
                    transcription_selection=deepcopy(block['transcription_selection']),
                    text_representation='deterministic_transcription_selection')
        images = []
        for identifier in page_ids:
            row = rows_by_id[identifier]
            payload = row['payload']
            primary = payload.get('primary_block_id')
            if primary is not None:
                if primary not in by_id or owner_by_block.get(primary) != identifier:
                    _fail()
                if by_id[primary]['page_index'] != page_index:
                    continue
                assets = payload.get('images', [])
            else:
                assets = [asset for name, asset in payload.get('source_artifacts', {}).items()
                          if any(b['page_index'] == page_index and any(a['path'] == name for a in b['image_paths'])
                                 for b in payload['source_blocks'])]
            images.extend({'information_id':identifier, 'unit_type':row['unit_type'],
                           'primary_block_id':primary, 'artifact':asset} for asset in assets)
        output_pages.append({'page_index':page_index, 'page_number':page_index+1,
            'page_size':page['page_size'], 'content':content, 'blocks':spans, 'images':images,
            'reading_order':'paddleocr_array_order' if paddle else 'mineru_index_stable',
            'reading_order_ties':[n for n,count in Counter(indices).items() if count>1],
            'character_offsets':'unicode_codepoints', 'separator':'\n\n',
            'information_ids':page_ids,
            'target_information_ids':[identifier for identifier in page_ids if information_pages[identifier][0]==page_index]})
    result = {'schema_version':'source-pages-v1', 'data_id':bundle['data_id'],
              'source_bundle_sha256':source_hash, 'information_pages':information_pages,
              'pages':output_pages}
    result['projection_sha256'] = _digest(result)
    return deepcopy(result)


def select_page_context(projection, page_number):
    """Supply center ±1 pages and explicit omissions, without calling an LLM."""
    if type(page_number) is not int or not 1 <= page_number <= len(projection['pages']):
        _fail('invalid_page_number')
    if (projection.get('schema_version') != 'source-pages-v1'
            or projection.get('projection_sha256') != _digest({k:v for k,v in projection.items() if k!='projection_sha256'})):
        _fail()
    center = page_number-1
    pages = deepcopy(projection['pages'][max(0,center-1):center+2])
    target = projection['pages'][center]['target_information_ids']
    available = {page['page_index'] for page in pages}
    visible = list(dict.fromkeys(identifier for page in pages for identifier in page['information_ids']))
    missing = []
    for identifier in visible:
        absent = set(projection['information_pages'][identifier])-available
        if absent:
            missing.append({'information_id':identifier,
                            'role':'target' if identifier in target else 'context',
                            'page_numbers':sorted(index+1 for index in absent)})
    for page in pages:
        page['role'] = 'target' if page['page_index']==center else 'context'
    result = {'schema_version':'page-context-v1', 'data_id':projection['data_id'],
        'projection_sha256':projection['projection_sha256'], 'page_number':page_number,
        'pages':pages, 'target_information_ids':list(target),
        'context_information_ids':[identifier for identifier in visible if identifier not in target],
        'missing_information_pages':sorted({n for item in missing for n in item['page_numbers']}),
        'incomplete_information_refs':missing,
        'target_complete':not any(item['role']=='target' for item in missing),
        'context_complete':not missing,
        'ownership_rule':'earliest_original_source_page_per_information',
        'llm_calls':0}
    result['context_sha256'] = _digest(result)
    return result
