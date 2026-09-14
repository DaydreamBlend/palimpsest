"""Source-preserving reading groups; neither K revisions nor decision reasons.

Consume verified PDF evidence, keep every source block in one primary group,
and connect explicit Figure references without rewriting historical visuals.
"""

from collections import Counter
from copy import deepcopy
import math
import re

from .errors import PalimpsestError
from .figure_references import extract_caption_anchors, extract_figure_mentions
from .paragraph_projection import digest


SCHEMA = 'source-sections-v1'
MAJORS = {
    'abstract': 'abstract', 'summary': 'abstract', 'introduction': 'introduction',
    'results': 'results', 'results and discussion': 'results_and_discussion',
    'discussion': 'discussion', 'methods': 'methods', 'online methods': 'methods',
    'materials and methods': 'methods', 'materials & methods': 'methods',
    'conclusions': 'conclusion', 'conclusion': 'conclusion', 'significance': 'significance',
    'references': 'references', 'acknowledgments': 'acknowledgments',
    'acknowledgements': 'acknowledgments', 'funding': 'funding',
    'author contributions': 'author_contributions', 'authorship': 'author_contributions',
    'disclosures': 'disclosures', 'supplementary material': 'supplementary_material',
}


def _fail(code='invalid_section_projection'):
    raise PalimpsestError(code, '읽기 그룹의 원문·실행·근거 연결을 확인하세요.', 4)


def _key(value):
    return f"{value['scope']}:{value['number']}"


def _ordered(bundle):
    pages, blocks = bundle['pages'], bundle['blocks']
    if (bundle.get('schema_version') != 1 or not pages
            or bundle.get('coordinate_system') != 'pdf_points_top_left'
            or [p['page_index'] for p in pages] != list(range(len(pages)))
            or len({b['block_id'] for b in blocks}) != len(blocks)):
        _fail()
    primary = {f['block_id'] for f in bundle.get('required_figures', [])}
    ordered, warnings = [], []
    if not primary <= {b['block_id'] for b in blocks}:
        _fail()
    for block in blocks:
        if (type(block['page_index']) is not int or not 0 <= block['page_index'] < len(pages)
                or not isinstance(block['text'], str)):
            _fail()
    for page in pages:
        members = [b for b in blocks if b['page_index'] == page['page_index']]
        original = [b for b in members if b['block_id'] not in primary]
        indices = [b.get('upstream_metadata', {}).get('index') for b in original]
        if any(type(n) not in (int, float) or not math.isfinite(n) for n in indices):
            _fail('reading_order_unavailable')
        if len(set(indices)) != len(indices):
            warnings.append({'code': 'reading_order_ties', 'page_index': page['page_index']})
        ordered.extend(sorted(original, key=lambda b: b['upstream_metadata']['index']))
        # App-provided whole-Figure regions have no parser reading-order index.
        ordered.extend(b for b in members if b['block_id'] in primary)
    return ordered, primary, warnings


def _canonical_mapping(bundle, pages):
    if pages is None:
        return {}, {'canonical_information_binding': 'not_requested'}
    if (pages.get('schema_version') != 'source-pages-v1'
            or pages.get('projection_sha256') != digest({k: v for k, v in pages.items() if k != 'projection_sha256'})
            or pages.get('source_bundle_sha256') != digest(bundle)
            or pages.get('data_id') != bundle['data_id']
            or not pages.get('execution_id') or not pages.get('profile_id')):
        _fail('section_execution_mismatch')
    mapping = {b['block_id']: b['information_id'] for p in pages['pages'] for b in p['blocks']}
    primary = {f['block_id']: f for f in bundle.get('required_figures', [])}
    for ref, figure in primary.items():
        owners = {mapping[b] for b in figure['member_block_ids'] + figure['caption_block_ids']}
        if len(owners) != 1:
            _fail('section_execution_mismatch')
        mapping[ref] = owners.pop()
    if set(mapping) != {b['block_id'] for b in bundle['blocks']}:
        _fail('section_execution_mismatch')
    return mapping, {'canonical_information_binding': 'completed_source_execution',
                     'execution_id': pages['execution_id'], 'profile_id': pages['profile_id'],
                     'source_page_projection_sha256': pages['projection_sha256']}


def group_source_blocks(ordered, primary, mapping=None):
    """Group already ordered source blocks by the established heading rules.

    This pure helper is shared by reading projections and grouped storage.
    Callers choose their block inventory; no source text is rewritten here.
    """
    groups, current, major_heading = [], None, None
    for block in ordered:
        is_source = block['block_id'] not in primary
        title = block['text'] if is_source and block['type'] == 'title' else None
        label = re.sub(r'^\s*\d+(?:\.\d+)*[.\s]+', '', title or '').strip().casefold()
        role = MAJORS.get(label)
        boundary = role is not None
        if role:
            major_heading = {'text': title, 'source_block_id': block['block_id'], 'role_hint': role}
        elif title and major_heading and major_heading['role_hint'] not in ('abstract', 'introduction', 'significance'):
            boundary = True
        if current is None or boundary:
            # Merge a section's title-only prefix into its first subheading.
            reuse = (current is not None and not role and
                     all(b['source_type'] in ('title', 'header', 'footer', 'page_number') for b in current['spans']))
            if not reuse:
                current = {'section_id': f'section-{len(groups) + 1}', 'title': title if boundary else None,
                           'role_hint': role or (major_heading['role_hint'] if major_heading else 'unclassified'),
                           'heading_path': [], 'source_block_ids': [], 'spans': [], 'text': '',
                           'page_indices': [], 'figure_keys': []}
                groups.append(current)
            elif title:
                current['title'] = title
            current['heading_path'] = ([deepcopy(major_heading)] if major_heading else [])
            if title and not role:
                current['heading_path'].append({'text': title, 'source_block_id': block['block_id'],
                                                'role_hint': 'subsection_candidate'})
        current['source_block_ids'].append(block['block_id'])
        if current['spans']:
            current['text'] += '\n\n'
        start = len(current['text'])
        # A derived Figure display label is not transcription of the original.
        current['text'] += block['text'] if is_source else ''
        span = {'source_block_id': block['block_id'], 'page_index': block['page_index'],
                'source_type': block['type'], 'raw_locator': block['raw_locator'],
                'bbox': deepcopy(block['bbox']), 'anchor_sha256': block['anchor_sha256'],
                'source_char_range': [0, len(block['text'])] if is_source else None,
                'char_start': start, 'char_end': len(current['text']),
                'text_origin': 'parser_source' if is_source else 'derived_visual_reference'}
        if mapping:
            span['information_id'] = mapping[block['block_id']]
        current['spans'].append(span)
        if block['page_index'] not in current['page_indices']:
            current['page_indices'].append(block['page_index'])
    return groups


def build_sections(evidence, *, canonical_pages=None):
    """Build a deterministic full-document reading plan, not actual model input.

    ``evidence`` comes from read_evidence; canonical_pages, when supplied, comes
    from CompilerRuntime.page_view, never from a cross-execution Data query.
    Native typography remains a hint; it cannot supply OCR character offsets.
    """
    bundle = evidence['source_bundle']
    ordered, primary, warnings = _ordered(bundle)
    mapping, binding = _canonical_mapping(bundle, canonical_pages)
    groups = group_source_blocks(ordered, primary, mapping)
    group_for = {ref: group['section_id'] for group in groups for ref in group['source_block_ids']}
    figures = {}

    def figure(ref):
        key = _key(ref)
        return figures.setdefault(key, {'figure_key': key, 'scope': ref['scope'], 'number': ref['number'],
            'caption_anchors': [], 'caption_completeness': 'not_verified',
            'mentions': [], 'context_section_ids': [], 'visual_proposals': [], 'warnings': []})

    for block in ordered:
        if block['block_id'] in primary:
            continue
        anchors = extract_caption_anchors(block)
        for anchor in anchors:
            figure(anchor)['caption_anchors'].append(anchor)
        for mention in extract_figure_mentions(block['text']):
            item = figure(mention)
            item['mentions'].append({**mention, 'source_block_id': block['block_id'],
                                     'page_index': block['page_index'],
                                     'kind': 'caption_reference' if anchors else 'body_reference'})
            if mention.get('warnings'):
                item['warnings'].extend(mention['warnings'])
            if not anchors and group_for[block['block_id']] not in item['context_section_ids']:
                item['context_section_ids'].append(group_for[block['block_id']])
    for visual in evidence['visuals']['figures']:
        number = str(visual['number'])
        visual_key = ('supplement:' + number[1:] if number.upper().startswith('S') else 'main:' + number)
        refs = {(a['source_block_id'], a['raw_locator']) for a in visual['caption_anchors']}
        actual = {key for key, f in figures.items() for a in f['caption_anchors']
                  if (a['source_block_id'], a['raw_locator']) in refs}
        if actual == {visual_key}:
            figures[visual_key]['visual_proposals'].append(deepcopy(visual))
        else:
            warnings.append({'code': 'visual_caption_number_conflict' if actual else 'visual_caption_unresolved',
                             'visual_figure_id': visual['figure_id'], 'declared_key': visual_key,
                             'source_keys': sorted(actual)})
    for key, item in figures.items():
        if not item['caption_anchors']:
            item['warnings'].append('caption_not_found_in_source')
        elif all(a['is_continuation'] for a in item['caption_anchors']):
            item['warnings'].append('initial_caption_not_found_in_source')
        if not item['visual_proposals']:
            item['warnings'].append('no_bound_visual_proposal_use_source_pages')
        item['warnings'] = sorted(set(item['warnings']))
        for group in groups:
            if group['section_id'] in item['context_section_ids']:
                group['figure_keys'].append(key)
    counts = Counter(ref for g in groups for ref in g['source_block_ids'])
    if set(counts) != {b['block_id'] for b in ordered} or any(n != 1 for n in counts.values()):
        _fail('section_source_coverage_failed')
    result = {'schema_version': SCHEMA, 'data_id': bundle['data_id'], **binding,
              'evidence_manifest_sha256': evidence['manifest_sha256'],
              'source_bundle_sha256': digest(bundle), 'parser_profile_sha256': digest(bundle.get('profile', {})),
              'evidence_inputs': {key: digest(evidence[key]) for key in ('paragraphs', 'text_analysis', 'visuals')},
              'policy': {'boundary': 'explicit_title_and_major_hint_v1', 'native_headings': 'candidate_only',
                         'figure_references': 'explicit_source_references_v1', 'separator': '\n\n',
                         'offsets': 'unicode_codepoints_half_open', 'target_assignment': 'source_block_once'},
              'sections': groups, 'figures': list(figures.values()), 'warnings': warnings,
              'coverage': {'source_block_count': len(ordered), 'assigned_source_block_count': len(counts),
                           'unassigned_source_block_ids': [], 'duplicate_source_block_ids': [],
                           'assignment_complete': True, 'actual_model_delivery': 'not_performed'},
              'authority': 'untrusted_source_and_reading_projection', 'canonical_writes': 0,
              'semantic_llm_calls': 0, 'semantic_revision': False}
    result['projection_sha256'] = digest(result)
    return result


def section_context(evidence, section_id, *, expected_projection_sha256=None, canonical_pages=None):
    """Return an exact reading group, neighbors and referenced source companions.

    This is not a tokenizer-budgeted model payload or a semantic completion.
    """
    projection = build_sections(evidence, canonical_pages=canonical_pages)
    if expected_projection_sha256 != projection['projection_sha256']:
        _fail('section_projection_changed')
    selected = next((s for s in projection['sections'] if s['section_id'] == section_id), None)
    if selected is None:
        _fail('unknown_section_id')
    bundle = evidence['source_bundle']
    ordered, _, _ = _ordered(bundle)
    targets = set(selected['source_block_ids'])
    context = set()
    for i, block in enumerate(ordered):
        if block['block_id'] in targets:
            context.update(b['block_id'] for b in ordered[max(0, i - 1):i + 2])
    figures = [f for f in projection['figures'] if f['figure_key'] in selected['figure_keys'] or
               any(a['source_block_id'] in targets for a in f['caption_anchors'])]
    for f in figures:
        context.update(a['source_block_id'] for a in f['caption_anchors'])
        for a in f['caption_anchors']:
            if a['is_continuation']:
                context.update(b['block_id'] for b in ordered if abs(b['page_index'] - a['page_index']) <= 1)
    # Preserve paragraph associations as proposals and reveal exact missing refs.
    visible = targets | context
    visible_pages = {b['page_index'] for b in ordered if b['block_id'] in visible}
    paragraphs = [deepcopy(p) for p in evidence['paragraphs']['paragraphs']
                  if (any(s.get('source_block_id') in visible or
                          any(r.get('source_block_id') in visible for r in s.get('possible_source_refs', []))
                          for s in p['segments'])
                      or (not p['source_mapping_complete'] and
                          p.get('parser_container_page_index') in visible_pages))]
    for paragraph in paragraphs:
        context.update(s['source_block_id'] for s in paragraph['segments'] if 'source_block_id' in s)
        context.update(r['source_block_id'] for s in paragraph['segments']
                       for r in s.get('possible_source_refs', []) if 'source_block_id' in r)
    available = targets | context
    if not available <= {b['block_id'] for b in ordered}:
        _fail('section_source_coverage_failed')
    pages = sorted({b['page_index'] for b in ordered if b['block_id'] in available})
    issues = [{'code': w, 'figure_key': f['figure_key']} for f in figures for w in f['warnings']]
    issues.extend({'code': 'paragraph_source_mapping_incomplete', 'paragraph_id': p['paragraph_id']}
                  for p in paragraphs if not p['source_mapping_complete'])
    rendered = []
    for page in bundle['pages']:
        if page['page_index'] in pages:
            if 'source_page_image' in page:
                rendered.append({'page_index': page['page_index'], 'page_image': deepcopy(page['source_page_image']),
                                 'coordinate_transform': deepcopy(page.get('coordinate_transform'))})
            else:
                issues.append({'code': 'retained_ocr_page_image_unavailable', 'page_index': page['page_index']})
    result = {'schema_version': 'source-section-context-v1', 'data_id': bundle['data_id'],
              'section_id': section_id, 'projection_sha256': projection['projection_sha256'],
              'source_binding': {k: projection[k] for k in ('canonical_information_binding',
                  'evidence_manifest_sha256', 'source_bundle_sha256', 'parser_profile_sha256')},
              'section': selected, 'source_blocks': [deepcopy(b) for b in ordered if b['block_id'] in available],
              'target_source_block_ids': list(selected['source_block_ids']),
              'context_source_block_ids': [b['block_id'] for b in ordered if b['block_id'] in context - targets],
              'paragraphs': paragraphs, 'figures': figures, 'page_indices': pages,
              'rendered_source_pages': rendered,
              'heading_candidates': [deepcopy(h) for h in evidence['text_analysis']['heading_candidates'] if h['page_index'] in pages],
              'discrepancies': [deepcopy(d) for d in evidence['text_analysis']['discrepancies'] if d['page_index'] in pages],
              'visual_pages': [deepcopy(p) for p in evidence['visuals']['pages'] if p['page_index'] in pages],
              'panels': [deepcopy(p) for p in evidence['visuals']['panels'] if p['page_index'] in pages],
              'asset_base_directory': evidence.get('asset_base_directory'),
              'parser_artifact_base_directory': evidence.get('parser_artifact_base_directory'),
              'unresolved_context': issues, 'projection_warnings': projection['warnings'],
              'model_input_status': 'not_budgeted_or_delivered',
              'authority': projection['authority'], 'canonical_writes': 0, 'semantic_llm_calls': 0}
    if canonical_pages is not None:
        result.update(execution_id=canonical_pages['execution_id'], profile_id=canonical_pages['profile_id'])
        mapping, _ = _canonical_mapping(bundle, canonical_pages)
        result['source_information_ids'] = {b['block_id']: mapping[b['block_id']] for b in ordered
                                           if b['block_id'] in available}
    result['context_sha256'] = digest(result)
    return result


def document_context(evidence, *, expected_projection_sha256=None, canonical_pages=None):
    """Whole-paper text once, ordered source spans and separate image indexes.

    The I2K adapter must measure the real multimodal payload before delivery.
    An available image descriptor is not proof that a model saw that image.
    """
    projection = build_sections(evidence, canonical_pages=canonical_pages)
    if expected_projection_sha256 != projection['projection_sha256']:
        _fail('section_projection_changed')
    text, spans, outline = '', [], []
    for group in projection['sections']:
        if outline:
            text += '\n\n'
        offset = len(text)
        text += group['text']
        spans.extend({**deepcopy(s), 'char_start': s['char_start'] + offset,
                      'char_end': s['char_end'] + offset} for s in group['spans'])
        outline.append({k: deepcopy(group[k]) for k in ('section_id', 'title', 'role_hint',
                                                       'heading_path', 'source_block_ids', 'page_indices')})
    bundle, visuals = evidence['source_bundle'], evidence['visuals']
    rendered, unresolved = [], []
    for page in bundle['pages']:
        if 'source_page_image' in page:
            rendered.append({'page_index': page['page_index'], 'page_image': deepcopy(page['source_page_image']),
                             'coordinate_transform': deepcopy(page.get('coordinate_transform'))})
        else:
            unresolved.append({'code': 'retained_ocr_page_image_unavailable', 'page_index': page['page_index']})
    figure_index = []
    for f in projection['figures']:
        figure_index.append({'figure_key': f['figure_key'], 'caption_completeness': f['caption_completeness'],
            'caption_source_refs': [{k: deepcopy(a[k]) for k in ('source_block_id', 'raw_locator', 'page_index',
                                                               'bbox', 'is_continuation')} for a in f['caption_anchors']],
            'mention_source_refs': [{k: deepcopy(m[k]) for k in ('source_block_id', 'page_index', 'char_start', 'char_end',
                                                               'scope', 'number', 'panels')} for m in f['mentions']],
            'visual_proposal_ids': [v['figure_id'] for v in f['visual_proposals']], 'warnings': f['warnings']})
        unresolved.extend({'code': warning, 'figure_key': f['figure_key']} for warning in f['warnings'])
    visual_assets = [{k: deepcopy(v[k]) for k in ('figure_id', 'page_index', 'region_proposal',
                    'whole_page_fallback', 'continuation_page_fallbacks', 'member_panel_ids', 'certainty', 'warnings') if k in v}
                    for v in visuals['figures']]
    result = {'schema_version': 'source-document-context-v1', 'data_id': bundle['data_id'],
              'projection_sha256': projection['projection_sha256'],
              'source_binding': {k: projection[k] for k in ('canonical_information_binding', 'source_bundle_sha256',
                                                           'evidence_manifest_sha256', 'parser_profile_sha256')},
              'text': text, 'spans': spans, 'section_outline': outline,
              'figure_index': figure_index, 'visual_asset_index': visual_assets,
              'source_image_index': [{'source_block_id': b['block_id'], 'page_index': b['page_index'],
                                      'images': deepcopy(b['image_paths'])} for b in bundle['blocks'] if b.get('image_paths')],
              'rendered_source_pages': rendered, 'panels': deepcopy(visuals['panels']),
              'page_indices': [p['page_index'] for p in bundle['pages']],
              'target_source_block_ids': [s['source_block_id'] for s in spans], 'context_source_block_ids': [],
              'discrepancies': deepcopy(evidence['text_analysis']['discrepancies']),
              'asset_base_directory': evidence.get('asset_base_directory'),
              'parser_artifact_base_directory': evidence.get('parser_artifact_base_directory'),
              'coverage': deepcopy(projection['coverage']), 'unresolved_context': unresolved,
              'projection_warnings': projection['warnings'],
              'model_input_status': 'not_budgeted_or_delivered', 'input_scope': 'whole_document',
              'authority': projection['authority'], 'canonical_writes': 0, 'semantic_llm_calls': 0}
    if canonical_pages is not None:
        result.update(execution_id=canonical_pages['execution_id'], profile_id=canonical_pages['profile_id'])
    result['context_sha256'] = digest(result)
    return result
