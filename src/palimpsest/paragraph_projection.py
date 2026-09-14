"""Read-only MinerU paragraph joins with exact, original-page segment refs."""

from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
import json

from .errors import PalimpsestError


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _pieces(node, locator, inherited_box=None):
    """Walk retained content nodes without accepting their container as source."""
    box = node.get('bbox', inherited_box)
    if any(key in node for key in ('content', 'html', 'latex', 'image_path')):
        yield locator, node, box
    for field in ('blocks', 'lines', 'spans'):
        for index, child in enumerate(node.get(field, [])):
            yield from _pieces(child, f'{locator}/{field}/{index}', box)


def _key(node):
    # cross_page is a postprocessing annotation, not part of original content.
    return digest({key: node[key] for key in
                   ('type', 'bbox', 'content', 'html', 'latex', 'image_path') if key in node})


def _text(node):
    return '\n'.join(value if isinstance(value, str) else '\n'.join(value)
                     for key in ('content', 'html', 'latex') if (value := node.get(key)))


def _selected_segment(item, block):
    """Project only whole, uniquely located edits; raw paragraph text stays intact."""
    result = {'selected_text': item['parser_text'], 'changes': [],
              'status': 'native_retained_unresolved_mapping'}
    if block is None or item.get('match_status') != 'exact_unique_source_segment':
        result['issue'] = 'source_segment_not_unique'
        return result
    native, source = block['native_text'], item['source_text']
    choice = block['transcription_selection']
    result.update(native_raw_artifact=deepcopy(block['native_raw_artifact']),
                  selection_status=choice['status'], selection_issues=deepcopy(choice['issues']))
    if not source:
        result['status'] = 'nontext_segment'
        return result
    start = native.find(source)
    if start < 0 or native.find(source, start + 1) >= 0:
        result['issue'] = 'native_segment_range_not_unique'
        return result
    end = start + len(source)
    result['native_block_range'] = [start, end]
    changes = []
    for change in choice['changes']:
        a, b = change['native_range']
        if (a == b and a in (start, end)) or (a < end and b > start and not start <= a <= b <= end):
            result['issue'] = 'selection_crosses_segment_boundary'
            return result
        if start <= a <= b <= end:
            changes.append(change)
    text, cursor = '', start
    for change in changes:
        a, b = change['native_range']
        if not cursor <= a <= b <= end or native[a:b] != change['native_text']:
            result['issue'] = 'selection_range_not_reproducible'
            return result
        text += native[cursor:a] + change['selected_text']
        cursor = b
    result.update(selected_text=text + native[cursor:end], changes=deepcopy(changes),
                  status='exact_source_segment_projection')
    return result


def _add_selected_paragraph(paragraph, blocks):
    selected, issues = '', []
    for item in paragraph['segments']:
        projection = _selected_segment(item, blocks.get(item.get('source_block_id')))
        if selected or item is not paragraph['segments'][0]:
            selected += '\n'
        projection['selected_char_start'] = len(selected)
        selected += projection['selected_text']
        projection['selected_char_end'] = len(selected)
        item['transcription_projection'] = projection
        if 'issue' in projection:
            issues.append(projection['issue'])
    paragraph.update(selected_text=selected, preferred_text_field='selected_text',
                     selected_mapping_complete=not issues,
                     selected_projection_warnings=sorted(set(issues)))


def build_paragraphs(middle, bundle):
    """Link para content to unique preproc occurrences, retaining ambiguity.

    No source span is moved, reworded, or assigned a guessed original page.
    A paragraph's presentation separators are explicit character-offset gaps.
    """
    if bundle.get('block_collection') != 'preproc_blocks':
        raise PalimpsestError('preproc_required', '문단 조회에는 병합 전 원문 근거가 필요합니다.', 4)
    by_key = defaultdict(list)
    dual = 'transcription_selection' in bundle
    blocks = {block['block_id']: block for block in bundle['blocks']}
    source_refs = {}
    for block in bundle['blocks']:
        for segment in block['segments']:
            source_refs[segment['raw_locator']] = (block, segment)
    for page_position, page in enumerate(middle['pdf_info']):
        for collection in ('preproc_blocks', 'discarded_blocks'):
            for number, raw in enumerate(page.get(collection, [])):
                parent = f'/pdf_info/{page_position}/{collection}/{number}'
                for locator, node, box in _pieces(raw, parent):
                    if locator not in source_refs:
                        raise PalimpsestError('source_ref_missing', '정규화된 원문 segment가 빠졌습니다.', 4)
                    block, segment = source_refs[locator]
                    reference = {
                        'source_block_id': block['block_id'], 'raw_locator': locator,
                        'page_index': block['page_index'], 'bbox': deepcopy(box),
                        'segment_sha256': digest(node), 'source_text': _text(node),
                        'source_asset': deepcopy(segment.get('image_path'))}
                    if 'coordinate_transform' in block:
                        reference.update(bbox=deepcopy(segment['bbox']), raw_bbox=deepcopy(box),
                            coordinate_transform=deepcopy(block['coordinate_transform']))
                    by_key[_key(node)].append(reference)
    paragraphs, matched_source = [], set()
    for page_position, page in enumerate(middle['pdf_info']):
        for number, raw in enumerate(page.get('para_blocks', [])):
            pointer = f'/pdf_info/{page_position}/para_blocks/{number}'
            refs, content, warnings = [], '', []
            for locator, node, _ in _pieces(raw, pointer):
                candidates = by_key.get(_key(node), [])
                # A non-moved occurrence may be disambiguated on its own page.
                # cross_page occurrences never inherit the para page index.
                if not node.get('cross_page'):
                    local = [x for x in candidates if x['page_index'] == page['page_idx']]
                    if local:
                        candidates = local
                item = {'paragraph_raw_locator': locator, 'parser_text': _text(node)}
                if len(candidates) == 1:
                    item.update(deepcopy(candidates[0]))
                    item['match_status'] = 'exact_unique_source_segment'
                    matched_source.add(item['raw_locator'])
                else:
                    item.update({'match_status': 'ambiguous' if candidates else 'unmatched',
                                 'possible_source_refs': deepcopy(candidates)})
                    warnings.append(item['match_status'])
                if refs:
                    content += '\n'
                item['char_start'] = len(content)
                content += item['parser_text']
                item['char_end'] = len(content)
                refs.append(item)
            original_pages = sorted({x['page_index'] for x in refs if 'page_index' in x})
            if original_pages and original_pages[-1] - original_pages[0] + 1 != len(original_pages):
                warnings.append('nonadjacent_source_pages')
            paragraphs.append({'paragraph_id': pointer, 'type': raw.get('type'),
                'parser_container_page_index': page['page_idx'],
                'source_pages': original_pages, 'cross_page': len(original_pages) > 1,
                'text': content, 'segments': refs, 'warnings': sorted(set(warnings)),
                'source_mapping_complete': all(x['match_status'] == 'exact_unique_source_segment' for x in refs),
                'join_status': 'upstream_paragraph_association_not_validated',
                'authority': 'reading_projection_only'})
            if dual:
                _add_selected_paragraph(paragraphs[-1], blocks)
    return {'schema_version': 'source-paragraph-projection-v1', 'data_id': bundle['data_id'],
        'source_bundle_sha256': digest(bundle), 'source_middle_sha256': digest(middle),
        'join_separator': '\n', 'paragraphs': paragraphs,
        'source_segment_count': len(source_refs), 'matched_source_segment_count': len(matched_source),
        'source_segments_outside_paragraph_view': sorted(set(source_refs) - matched_source),
        'canonical_writes': 0}


def select_evidence_context(evidence, page_number):
    """Provide ±1 physical pages and joined paragraphs with all original refs."""
    pages = evidence['source_bundle']['pages']
    if type(page_number) is not int or not 1 <= page_number <= len(pages):
        raise PalimpsestError('invalid_page_number', '원본의 물리 페이지 번호를 확인하세요.', 2)
    center = page_number - 1
    selected = set(range(max(0, center - 1), min(len(pages), center + 2)))
    bundle = evidence['source_bundle']
    analysis, visuals = evidence['text_analysis'], evidence['visuals']
    asset_lookup = {(p['parser_asset']['original_path'], p['parser_asset']['sha256']): p['parser_asset']['copied_asset']
                    for p in visuals['panels'] if p['parser_asset'].get('copied_asset')}
    paragraphs = []
    for paragraph in evidence['paragraphs']['paragraphs']:
        if (selected.intersection(paragraph['source_pages'])
                or (not paragraph['source_mapping_complete'] and paragraph['parser_container_page_index'] in selected)):
            paragraph = deepcopy(paragraph)
            paragraph['source_pages_outside_window'] = sorted(set(paragraph['source_pages']) - selected)
            for segment in paragraph['segments']:
                if source_asset := segment.get('source_asset'):
                    segment['display_asset'] = deepcopy(asset_lookup.get((source_asset['path'], source_asset['sha256'])))
            paragraphs.append(paragraph)
    result = {'schema_version': 'pdf-evidence-context-v1', 'data_id': bundle['data_id'],
        'evidence_manifest_sha256': evidence['manifest_sha256'], 'page_number': page_number,
        'page_indices': sorted(selected), 'source_bundle_sha256': digest(bundle),
        'source_blocks': [deepcopy(b) for b in bundle['blocks'] if b['page_index'] in selected],
        'paragraphs': paragraphs,
        'heading_candidates': [x for x in analysis['heading_candidates'] if x['page_index'] in selected],
        'discrepancies': [x for x in analysis['discrepancies'] if x['page_index'] in selected],
        'page_images': [x for x in visuals['pages'] if x['page_index'] in selected],
        'panels': [x for x in visuals['panels'] if x['page_index'] in selected],
        'figures': [x for x in visuals['figures'] if x['page_index'] in selected],
        'source_asset_resolution': [{'original_parser_asset': {'path': key[0], 'sha256': key[1]},
                                     'copied_asset': deepcopy(asset)} for key, asset in sorted(asset_lookup.items())],
        'asset_base_directory': evidence.get('asset_base_directory'),
        'asset_path_policy': 'display/copied/rendered assets use asset_base_directory; original parser paths remain provenance locators',
        'authority': 'untrusted_source_and_reading_projections', 'semantic_llm_calls': 0}
    if bundle.get('profile', {}).get('adapter_version') == 'mineru-hybrid-image200-v1':
        result.update(rendered_source_pages=[{
            'page_index': page['page_index'], 'page_image': deepcopy(page['source_page_image']),
            'coordinate_transform': deepcopy(page['coordinate_transform'])}
            for page in pages if page['page_index'] in selected],
            parser_artifact_base_directory=evidence['parser_artifact_base_directory'],
            preferred_page_image_collection='rendered_source_pages',
            rendered_source_image_path_policy='paths use parser_artifact_base_directory; original 200 DPI raster bytes')
    if 'transcription_selection' in bundle:
        unmatched = [deepcopy(b) for b in bundle['transcription_selection'].get('unmatched_ocr_blocks', [])
                     if b['page_index'] in selected]
        result.update(transcription_selection={
            **{key: deepcopy(value) for key, value in bundle['transcription_selection'].items()
               if key not in ('blocks', 'unresolved', 'unmatched_ocr_blocks', 'unmatched_ocr_block_ids')},
            'blocks': [deepcopy(b) for b in bundle['transcription_selection']['blocks'] if b['page_index'] in selected],
            'unresolved': [deepcopy(b) for b in bundle['transcription_selection']['unresolved'] if b['page_index'] in selected],
            'unmatched_ocr_blocks': unmatched, 'unmatched_ocr_block_ids': [b['block_id'] for b in unmatched]},
            ocr_source_blocks=[deepcopy(b) for b in bundle['ocr_bundle']['blocks'] if b['page_index'] in selected],
            parser_artifact_base_directory=evidence.get('parser_artifact_base_directory'),
            preferred_paragraph_text_field='selected_text')
    result['context_sha256'] = digest(result)
    return result
