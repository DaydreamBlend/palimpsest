"""Prepare exact Information input and optional source requests, without I/O.

These are local preparations, not model-delivery receipts or Knowledge effects.
Parser trees and retained original-page companions stay outside model input.
"""

from copy import deepcopy
from hashlib import sha256
import json

from .data import data_id, request_id
from .errors import PalimpsestError
from .information import fingerprints
from .page_projection import build_pages
from .source_units import SOURCE_UNITS_VERSION
from .d2i import build_units, assembly_payload, text_assemblies, MARKDOWN_ALGORITHM, CODE_ALGORITHM, TEXT_ALGORITHMS


def digest(value):
    try:
        return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
            separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError):
        _fail()


def _fail(code='invalid_i2k_input'):
    raise PalimpsestError(code, 'I2K 입력 snapshot과 정확한 Information·원문 참조를 확인하세요.', 4)


def _ids(values, *, allow_empty=False, code='invalid_i2k_input'):
    if not isinstance(values, list) or (not values and not allow_empty):
        _fail(code)
    result = [request_id(value) for value in values]
    if len(result) != len(set(result)):
        _fail(code)
    return result


def _asset(value, expected_sha):
    data_id(expected_sha)
    if (not isinstance(value, dict) or value.get('sha256') != expected_sha
            or type(value.get('byte_size')) is not int or value['byte_size'] <= 0
            or value.get('artifact_path') != f'derived/objects/sha256/{expected_sha[:2]}/{expected_sha}'):
        _fail()
    return {key: value[key] for key in ('sha256', 'byte_size', 'artifact_path')}


def _source_ref(block, *, derived_primary, grounding=None):
    if block.get('locator_type') == 'text_range':
        result = {key: deepcopy(block[key]) for key in
                  ('block_id', 'locator_type', 'text_range', 'raw_locator', 'anchor_sha256')}
        result.update(source_type=block['type'], heading_path=deepcopy(block.get('heading_path', [])),
                      referenced_images=deepcopy(block.get('referenced_images', [])))
        if 'code_context' in block:
            result['code_context'] = deepcopy(block['code_context'])
        if grounding is not None:
            result.update(grounding_id=request_id(grounding['grounding_id']),
                          parse_artifact_id=request_id(grounding['parse_artifact_id']))
        return result
    result = {key: deepcopy(block[key]) for key in
        ('block_id', 'page_index', 'bbox', 'page_size', 'raw_locator', 'anchor_sha256')}
    result.update(source_type=block['type'], source_collection=block.get('source_collection'),
        source_text_range=({'char_start': 0, 'char_end': len(block['text']),
                           'offsets': 'unicode_codepoints_half_open'} if not derived_primary else None),
        derived_primary=derived_primary)
    # Leaf refs keep exact provenance without forwarding arbitrary parser trees.
    for collection in ('grounding_regions', 'source_regions', 'segments'):
        if collection in block:
            result[collection] = [{key: deepcopy(region[key]) for key in
                ('type', 'page_index', 'bbox', 'raw_locator', 'parent_locator',
                 'segment_sha256', 'char_start', 'char_end') if key in region}
                for region in block[collection]]
    if grounding is not None:
        result.update(grounding_id=request_id(grounding['grounding_id']),
                      parse_artifact_id=request_id(grounding['parse_artifact_id']))
    if 'facsimile_provenance' in block:
        result['facsimile_provenance'] = deepcopy(block['facsimile_provenance'])
        result['source_text_range'] = None
    return result


def _quality(evidence, bundle, selected_blocks):
    if evidence is None:
        return {'status': 'not_supplied', 'source_fidelity_verified': False, 'issues': []}
    if not isinstance(evidence, dict):
        _fail('i2k_evidence_mismatch')
    if evidence.get('source_bundle') != bundle:
        from .source_pages import parent_bundle
        supplement = bundle.get('source_page_supplement')
        if (not isinstance(supplement, dict)
                or supplement.get('evidence_manifest_sha256') != evidence.get('manifest_sha256')
                or parent_bundle(bundle) != evidence.get('source_bundle')):
            _fail('i2k_evidence_mismatch')
    data_id(evidence.get('manifest_sha256'))
    selected = {b['block_id']: b for b in selected_blocks}
    pages = {b['page_index'] for b in selected_blocks}
    issues = []
    for item in evidence['text_analysis']['discrepancies']:
        locators = {ref['raw_locator'] for ref in item.get('parser_refs', [])}
        refs = [b['block_id'] for b in selected_blocks if b['raw_locator'] in locators]
        if refs or (not locators and item['page_index'] in pages):
            issues.append({'code': 'transcription_discrepancy',
                'discrepancy_id': item['discrepancy_id'], 'kind': item['kind'],
                'alignment_status': item.get('alignment_status'), 'page_index': item['page_index'],
                'source_block_ids': refs})
    for paragraph in evidence['paragraphs']['paragraphs']:
        refs = {segment['source_block_id'] for segment in paragraph['segments'] if 'source_block_id' in segment}
        refs.update(ref['source_block_id'] for segment in paragraph['segments']
                    for ref in segment.get('possible_source_refs', []))
        if (not paragraph['source_mapping_complete'] and
                (refs & selected.keys() or paragraph.get('parser_container_page_index') in pages)):
            issues.append({'code': 'paragraph_source_mapping_incomplete',
                'paragraph_id': paragraph['paragraph_id'], 'source_block_ids': sorted(refs & selected.keys()),
                'page_index': paragraph.get('parser_container_page_index')})
    from .section_projection import build_sections
    sections = build_sections(evidence)
    for figure in sections['figures']:
        refs = {a['source_block_id'] for a in figure['caption_anchors'] + figure['mentions']}
        if refs & selected.keys():
            issues.extend({'code': warning, 'figure_key': figure['figure_key'],
                'source_block_ids': sorted(refs & selected.keys())} for warning in figure['warnings'])
    # Unbound visual warnings have uncertain source scope; keep them document-scoped.
    issues.extend({**deepcopy(warning), 'scope': 'document_projection'} for warning in sections['warnings'])
    return {'status': 'supplied_review_signals', 'source_fidelity_verified': False,
        'evidence_manifest_sha256': evidence['manifest_sha256'],
        'projection_sha256': sections['projection_sha256'], 'issues': issues}


def build_input(bundle, information_rows, *, execution_id, profile_id,
                selected_information_ids=None, context_information_ids=None, evidence=None,
                assembly_algorithm=SOURCE_UNITS_VERSION):
    """Select whole canonical I units in source order, retaining all their media.

    Callers load one completed execution and verify stored bytes. This function
    independently checks content and metadata equality, but performs no I/O.
    """
    execution_id, profile_id = request_id(execution_id), request_id(profile_id)
    if not isinstance(bundle, dict) or not isinstance(information_rows, list):
        _fail()
    data_id(bundle.get('data_id'))
    markdown = assembly_algorithm in TEXT_ALGORITHMS
    pages = None if markdown else build_pages(bundle, information_rows)
    blocks = {block['block_id']: block for block in bundle['blocks']}
    derived_primaries = {figure['block_id'] for figure in bundle.get('required_figures', [])}
    proposals = build_units(bundle, assembly_algorithm)
    expected = {tuple(proposal['block_ids']): proposal for proposal in proposals}
    assemblies = text_assemblies(bundle, proposals, assembly_algorithm)[1] if markdown else None
    rows, assets_by_id, groundings_by_id, manifests, parse_ids = {}, {}, {}, set(), set()
    owner_by_block = {}
    for row in information_rows:
        identifier = request_id(row['information_id'])
        request_id(row.get('origin_record_id'))
        payload = row['payload']
        if (identifier in rows or row.get('data_id') != bundle['data_id']
                or payload.get('schema_version') != 'source-information-v1'
                or payload.get('source_bundle_sha256') != digest(bundle)):
            _fail()
        for source in payload['source_blocks']:
            ref = source['block_id']
            if ref in owner_by_block or blocks.get(ref) != source:
                _fail()
            owner_by_block[ref] = identifier
        proposal = expected.get(tuple(block['block_id'] for block in payload['source_blocks']))
        if proposal is None or any(row.get(key) != proposal[key] for key in
                ('kind', 'unit_type', 'semantic_type', 'title', 'content')):
            _fail()
        expected_assembly = (assemblies[tuple(proposal['block_ids'])] if assemblies is not None else
                             assembly_payload(bundle, proposal, assembly_algorithm))
        if payload.get('source_assembly') != expected_assembly.get('source_assembly'):
            _fail()
        if (payload.get('primary_block_id') != proposal['image_block_id']
                or payload.get('validation_basis') != 'source_structure'
                or payload.get('semantic_checked') is not False
                or payload.get('empty_content') != (row['content'] == '')):
            _fail()
        calculated = fingerprints(bundle['data_id'], proposal, blocks)
        if any(row.get(key) != calculated[key] for key in ('identity_fingerprint', 'content_fingerprint')):
            _fail()
        manifests.add(data_id(payload.get('parse_manifest_sha256')))
        expected_images = {image['path']: image['sha256'] for block in payload['source_blocks']
                           for image in block['image_paths']}
        source_assets = payload.get('source_artifacts')
        if not isinstance(source_assets, dict) or set(source_assets) != set(expected_images):
            _fail()
        assets = {path: _asset(source_assets[path], value) for path, value in expected_images.items()}
        primary = proposal['image_block_id']
        if payload.get('images') != ([source_assets[image['path']] for image in blocks[primary]['image_paths']]
                                     if primary else []):
            _fail()
        groundings = row.get('groundings')
        by_ref = {}
        if groundings is not None:
            if not isinstance(groundings, list):
                _fail()
            for grounding in groundings:
                ref = grounding.get('block_id')
                location_keys = ('page_index', 'bbox', 'page_size', 'raw_locator', 'anchor_sha256')
                if markdown:
                    location_keys += ('locator_type', 'text_range')
                if (ref in by_ref or ref not in proposal['block_ids']
                        or str(grounding.get('information_id')) != identifier
                        or grounding.get('data_id') != bundle['data_id']
                        or any(grounding.get(key) != blocks[ref][key] for key in location_keys)):
                    _fail()
                request_id(grounding.get('grounding_id'))
                parse_ids.add(request_id(grounding.get('parse_artifact_id')))
                by_ref[ref] = grounding
            if set(by_ref) != set(proposal['block_ids']):
                _fail()
        groundings_by_id[identifier] = by_ref
        rows[identifier], assets_by_id[identifier] = row, assets
    if len(manifests) != 1 or len(parse_ids) > 1 or set(owner_by_block) != set(blocks):
        _fail()
    ordered = (list(dict.fromkeys(owner_by_block[b['block_id']] for b in bundle['blocks'])) if markdown else
               list(dict.fromkeys(identifier for page in pages['pages'] for identifier in page['information_ids'])))
    selected = set(ordered if selected_information_ids is None else _ids(selected_information_ids))
    context = set(_ids(context_information_ids, allow_empty=True)) if context_information_ids is not None else set()
    context -= selected
    visible = selected | context
    if not visible <= rows.keys():
        _fail('i2k_information_scope_mismatch')
    targets = [identifier for identifier in ordered if identifier in selected]
    contexts = [identifier for identifier in ordered if identifier in context]
    excluded = [identifier for identifier in ordered if identifier not in visible]
    units, media_assets, selected_blocks = [], {}, []
    for identifier in (identifier for identifier in ordered if identifier in visible):
        row, assets = rows[identifier], assets_by_id[identifier]
        payload = row['payload']
        media = []
        for block in payload['source_blocks']:
            selected_blocks.append(block)
            for image in block['image_paths']:
                asset = assets[image['path']]
                if asset['sha256'] in media_assets and media_assets[asset['sha256']] != asset:
                    _fail()
                media_assets[asset['sha256']] = asset
                media.append({'sha256': asset['sha256'], 'byte_size': asset['byte_size'],
                              'source_block_id': block['block_id'], 'page_index': block['page_index']})
        units.append({'information_id': identifier, 'origin_record_id': str(row['origin_record_id']),
            'role': 'target' if identifier in selected else 'context',
            **{key: row[key] for key in ('kind', 'unit_type', 'title', 'content',
                                         'identity_fingerprint', 'content_fingerprint')},
            'source_refs': [_source_ref(block, derived_primary=block['block_id'] in derived_primaries,
                                       grounding=groundings_by_id[identifier].get(block['block_id']))
                            for block in payload['source_blocks']], 'media': media})
        if 'source_assembly' in payload:
            units[-1]['source_assembly'] = deepcopy(payload['source_assembly'])
        if assembly_algorithm == CODE_ALGORITHM:
            units[-1]['code_context'] = [deepcopy(block['code_context']) for block in payload['source_blocks']]
    if markdown and evidence is not None:
        _fail('i2k_evidence_mismatch')
    quality = _quality(evidence, bundle, selected_blocks)
    result = {'schema_version': 'i2k-input-v1', 'state': 'prepared_not_delivered',
        'source_execution_id': execution_id, 'profile_id': profile_id, 'data_id': bundle['data_id'],
        'source_bundle_sha256': digest(bundle), 'parse_manifest_sha256': next(iter(manifests)),
        'page_count': len(bundle['pages']), 'target_information_ids': targets,
        'context_information_ids': contexts,
        'excluded_information_ids': excluded,
        'model_input': {'data_id': bundle['data_id'], 'information': units,
            'quality_evidence': quality, 'authority': 'untrusted_source_information',
            'original_pdf_request_supported': not markdown},
        'media_assets': list(media_assets.values()), 'actual_delivery': False,
        'llm_calls': 0, 'canonical_writes': 0, 'model_budget_status': 'not_measured'}
    if assembly_algorithm != SOURCE_UNITS_VERSION:
        result['source_assembly_algorithm'] = assembly_algorithm
    if markdown:
        result['model_input']['source_format'] = 'code' if assembly_algorithm == CODE_ALGORITHM else 'markdown'
        result['model_input']['external_resources'] = 'references_only_not_fetched'
    result['input_sha256'] = digest(result)
    return deepcopy(result)


def validate_source_request(request, packet):
    """Validate a request against sent-scope preparation; do not claim delivery."""
    if (not isinstance(packet, dict) or packet.get('schema_version') != 'i2k-input-v1'
            or packet.get('input_sha256') != digest({k: v for k, v in packet.items() if k != 'input_sha256'})):
        _fail('i2k_input_changed')
    if packet['model_input']['original_pdf_request_supported'] is not True:
        _fail('original_pdf_required')
    fields = {'schema_version', 'input_sha256', 'information_ids', 'question', 'page_numbers'}
    if (not isinstance(request, dict) or set(request) != fields
            or request.get('schema_version') != 'i2k-source-request-v1'):
        _fail('invalid_i2k_source_request')
    if request['input_sha256'] != packet['input_sha256']:
        _fail('i2k_input_changed')
    ids = _ids(request['information_ids'], code='invalid_i2k_source_request')
    if not set(ids) <= set(packet['target_information_ids'] + packet['context_information_ids']):
        _fail('i2k_information_scope_mismatch')
    question, page_numbers = request['question'], request['page_numbers']
    if (not isinstance(question, str) or not question.strip() or len(question) > 4096 or '\x00' in question
            or not isinstance(page_numbers, list) or any(type(n) is not int or not 1 <= n <= packet['page_count']
                                                        for n in page_numbers)
            or len(page_numbers) != len(set(page_numbers))):
        _fail('invalid_i2k_source_request')
    result = {**deepcopy(request), 'information_ids': ids, 'data_id': packet['data_id'],
        'source_execution_id': packet['source_execution_id'], 'state': 'validated_not_delivered',
        'actual_delivery': False, 'model_request_observed': False}
    result['request_sha256'] = digest(result)
    return result
