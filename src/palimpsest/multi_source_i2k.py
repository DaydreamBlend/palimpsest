"""Source-explicit I2K over several complete, immutable source inputs.

This module checks structure and exact references. It does not decide source
meaning, importance, experimental identity or whether evidence implies a claim.
"""

from copy import deepcopy

from .data import data_id, request_id
from .i2k import digest
from .i2k_selection import (check_selection_input, selection_schema, selection_decision_schema,
                            selection_fingerprints, validate_selection_decisions)
from .knowledge import (_array, _enum, _fail, _keys, _object, _strings, _text,
                        normalize_nodes, source_block_ranges, SOURCE_ROLES)


PROFILE = 'multi-source-explicit-i2k-v1'
INPUT_SCHEMA = 'multi-source-i2k-input-v1'


def combine_packets(packets):
    """Keep all I and their source refs; deduplicate only identical media bytes.

    Runtime must verify each source packet against its canonical DB rows before
    preparing an execution. Packet hashes alone are not authority or delivery.
    """
    if not isinstance(packets, list) or not packets:
        _fail('invalid_multi_source_input')
    sources, units, assets = [], [], {}
    seen_data, seen_executions, seen_information = set(), set(), set()
    for packet in packets:
        if (not isinstance(packet, dict) or not isinstance(packet.get('model_input'), dict)
                or not isinstance(packet['model_input'].get('information'), list)
                or any(not isinstance(unit, dict) for unit in packet['model_input']['information'])):
            _fail('invalid_multi_source_input')
        ids = check_selection_input(packet)
        owner = data_id(packet.get('data_id'))
        execution = request_id(packet.get('source_execution_id'))
        request_id(packet.get('profile_id'))
        if (packet.get('input_sha256') != digest({k: v for k, v in packet.items() if k != 'input_sha256'})
                or packet['model_input'].get('data_id') != owner
                or type(packet.get('page_count')) is not int or packet['page_count'] < 0):
            _fail('multi_source_packet_changed')
        if owner in seen_data or execution in seen_executions or seen_information.intersection(ids):
            _fail('duplicate_multi_source_input')
        if not isinstance(packet.get('media_assets'), list):
            _fail('invalid_multi_source_media')
        local_assets = {}
        for asset in packet['media_assets']:
            _keys(asset, ('sha256', 'byte_size', 'artifact_path'), 'invalid_multi_source_media')
            sha = data_id(asset['sha256'])
            if (sha in local_assets or type(asset['byte_size']) is not int or asset['byte_size'] <= 0
                    or asset['artifact_path'] != f'derived/objects/sha256/{sha[:2]}/{sha}'):
                _fail('invalid_multi_source_media')
            if sha in assets and assets[sha] != asset:
                _fail('multi_source_media_conflict')
            local_assets[sha] = deepcopy(asset)
            assets.setdefault(sha, deepcopy(asset))
        used = set()
        for unit in packet['model_input']['information']:
            request_id(unit['information_id'])
            request_id(unit['origin_record_id'])
            if not isinstance(unit.get('content'), str) or not isinstance(unit.get('source_refs'), list):
                _fail('invalid_multi_source_input')
            if not isinstance(unit.get('media'), list):
                _fail('invalid_multi_source_media')
            for media in unit['media']:
                if not isinstance(media, dict):
                    _fail('invalid_multi_source_media')
                asset = local_assets.get(media.get('sha256'))
                if asset is None or media.get('byte_size') != asset['byte_size']:
                    _fail('invalid_multi_source_media')
                used.add(media['sha256'])
            units.append({**deepcopy(unit), 'data_id': owner, 'source_execution_id': execution,
                          'source_input_sha256': packet['input_sha256']})
        if used != set(local_assets):
            _fail('invalid_multi_source_media')
        seen_data.add(owner)
        seen_executions.add(execution)
        seen_information.update(ids)
        sources.append(deepcopy(packet))
    result = {'schema_version': INPUT_SCHEMA, 'state': 'prepared_not_delivered',
        'data_id': sources[0]['data_id'], 'data_id_role': 'operational_anchor_not_evidence_owner',
        'source_data_ids': [source['data_id'] for source in sources],
        'source_execution_ids': [source['source_execution_id'] for source in sources],
        'sources': sources, 'target_information_ids': [unit['information_id'] for unit in units],
        'context_information_ids': [], 'excluded_information_ids': [],
        'model_input': {'information': units, 'authority': 'untrusted_source_information',
            'claim_policy': 'explicit_source_content_only',
            'quality_evidence': [{'data_id': source['data_id'], 'source_execution_id': source['source_execution_id'],
                'evidence': deepcopy(source['model_input'].get('quality_evidence'))} for source in sources]},
        'media_assets': list(assets.values()), 'actual_delivery': False, 'llm_calls': 0, 'canonical_writes': 0}
    result['input_sha256'] = digest(result)
    return result


def check_input(bundle):
    if not isinstance(bundle, dict) or bundle.get('schema_version') != INPUT_SCHEMA:
        _fail('invalid_multi_source_input')
    if combine_packets(bundle.get('sources')) != bundle:
        _fail('multi_source_input_changed')
    return list(bundle['target_information_ids'])


def generation_schema(bundle):
    ids = check_input(bundle)
    schema = selection_schema(ids, [asset['sha256'] for asset in bundle['media_assets']])
    node = schema['properties']['nodes']['items']
    node['properties'].update(source_data_id=_enum(bundle['source_data_ids'], nullable=True),
        claim_basis=_enum(('explicit_source_content',)), is_inferred={'type': 'boolean', 'enum': [False]})
    node['required'] = list(node['properties'])
    blocks = list(dict.fromkeys(block for unit in bundle['model_input']['information']
                                for block in source_block_ranges(unit)))
    if blocks:
        evidence = node['properties']['evidence']
        evidence['items'] = {'anyOf': [evidence['items'], _object({
            'information_id': _enum(ids), 'source_block_id': _enum(blocks),
            'source_role': _enum(SOURCE_ROLES),
        })]}
    schema['properties']['source_requests'] = _array(_object({
        'data_id': _enum(bundle['source_data_ids']), 'information_ids': _array(_enum(ids), nonempty=True),
        'page_numbers': _array({'type': 'integer', 'minimum': 1}), 'question': {'type': 'string', 'minLength': 1},
    }))
    return schema


def validation_schema(candidate_keys, existing_revision_ids, bundle):
    schema = selection_decision_schema(candidate_keys, existing_revision_ids, check_input(bundle))
    item = schema['properties']['decisions']['items']
    for branch in item.get('anyOf', [item]):
        branch['properties'].update(source_explicit={'type': 'boolean'}, no_novel_inference={'type': 'boolean'},
                                    source_identity_preserved={'type': 'boolean'})
        branch['required'] = list(branch['properties'])
    return schema


def normalize_source_requests(requests, bundle):
    check_input(bundle)
    if not isinstance(requests, list):
        _fail('invalid_multi_source_request')
    packets = {packet['data_id']: packet for packet in bundle['sources']}
    result = []
    for value in requests:
        _keys(value, ('data_id', 'information_ids', 'page_numbers', 'question'), 'invalid_multi_source_request')
        owner = data_id(value['data_id'])
        packet = packets.get(owner)
        identifiers, pages = value['information_ids'], value['page_numbers']
        if (packet is None or not isinstance(identifiers, list) or not identifiers
                or any(not isinstance(identifier, str) for identifier in identifiers)
                or len(identifiers) != len(set(identifiers))
                or not set(identifiers) <= set(packet['target_information_ids'])
                or not isinstance(pages, list) or any(type(page) is not int or not 1 <= page <= packet['page_count'] for page in pages)
                or len(pages) != len(set(pages))):
            _fail('invalid_multi_source_request')
        result.append({**deepcopy(value), 'question': _text(value['question'])})
    return result


def normalize_proposals(response, bundle):
    ids = check_input(bundle)
    _keys(response, ('nodes', 'reviews', 'source_requests', 'complete', 'coverage_notes'), 'invalid_multi_source_proposal')
    requests = normalize_source_requests(response['source_requests'], bundle)
    if not isinstance(response['nodes'], list) or type(response['complete']) is not bool:
        _fail('invalid_multi_source_proposal')
    if requests and response['complete']:
        _fail('unresolved_multi_source_request')
    raw = {'nodes': [], 'source_requests': [], 'complete': response['complete'],
           'coverage_notes': deepcopy(response['coverage_notes'])}
    classifications = []
    for value in response['nodes']:
        _keys(value, ('candidate_key', 'kind', 'statement', 'semantic_payload', 'evidence', 'uncertainties',
                     'identity_scope', 'selection_reason', 'source_data_id', 'claim_basis', 'is_inferred'),
              'invalid_multi_source_proposal')
        if value['claim_basis'] != 'explicit_source_content' or value['is_inferred'] is not False:
            _fail('i2k_novel_inference_forbidden')
        classification = {key: deepcopy(value[key]) for key in
            ('identity_scope', 'selection_reason', 'source_data_id', 'claim_basis', 'is_inferred')}
        classifications.append(classification)
        raw['nodes'].append({key: deepcopy(item) for key, item in value.items() if key not in classification})
    units = {unit['information_id']: unit for unit in bundle['model_input']['information']}
    # Only exact citation checking is shared with the single-source helper. No
    # synthetic Data ID or document page count is invented for this union.
    citation_input = {'model_input': {'information': list(units.values())}}
    nodes = normalize_nodes(raw, citation_input, allow_media_only=True, allow_block_refs=True)
    by_key = {}
    for node, classification in zip(nodes, classifications):
        scope, owner = classification['identity_scope'], classification['source_data_id']
        evidence_owners = {units[citation['information_id']]['data_id'] for citation in node['evidence']}
        if (scope == 'source' and (owner not in bundle['source_data_ids'] or owner not in evidence_owners)):
            _fail('source_owner_evidence_required')
        if scope == 'general' and owner is not None:
            _fail('invalid_knowledge_identity_scope')
        node.update(classification, selection_reason=_text(classification['selection_reason']),
                    **selection_fingerprints(node['kind'], node['semantic_payload'], scope, owner))
        for citation in node['evidence']:
            unit = units[citation['information_id']]
            citation.update(data_id=unit['data_id'], source_execution_id=unit['source_execution_id'])
        by_key[node['candidate_key']] = node
    if not isinstance(response['reviews'], list):
        _fail('invalid_selection_reviews')
    reviews, completions = {}, []
    for value in response['reviews']:
        _keys(value, ('information_id', 'disposition', 'candidate_keys', 'reason'), 'invalid_selection_reviews')
        identifier = value['information_id']
        if not isinstance(identifier, str) or identifier not in units or identifier in reviews:
            _fail('selection_review_coverage_mismatch')
        disposition, keys = value['disposition'], _strings(value['candidate_keys'])
        if (disposition not in ('selected', 'context_only', 'not_selected', 'needs_review')
                or len(keys) != len(set(keys)) or not set(keys) <= by_key.keys()
                or (disposition in ('context_only', 'not_selected') and keys)):
            _fail('invalid_selection_reviews')
        actual = [key for key, node in by_key.items()
                  if any(citation['information_id'] == identifier for citation in node['evidence'])]
        if not set(keys) <= set(actual):
            _fail('selection_review_evidence_mismatch')
        if disposition == 'selected':
            if not actual:
                _fail('invalid_selection_reviews')
            missing = [key for key in actual if key not in keys]
            if missing:
                completions.append({'information_id': identifier, 'data_id': units[identifier]['data_id'],
                    'added_candidate_keys': missing, 'basis': 'existing_candidate_evidence; importance_disposition_unchanged'})
            keys = actual
        if not set(actual) <= set(keys):
            _fail('selection_review_evidence_mismatch')
        reviews[identifier] = {**deepcopy(value), 'candidate_keys': keys, 'reason': _text(value['reason']),
                              'data_id': units[identifier]['data_id']}
    if set(reviews) != set(ids):
        _fail('selection_review_coverage_mismatch')
    if response['complete'] and any(review['disposition'] == 'needs_review' for review in reviews.values()):
        _fail('unresolved_selection_reviews')
    return {'nodes': nodes, 'reviews': [reviews[identifier] for identifier in ids], 'link_completions': completions,
            'source_requests': requests, 'complete': response['complete'], 'coverage_notes': _strings(response['coverage_notes'])}


def validate_decisions(value, candidates, existing_ids, bundle):
    ids = check_input(bundle)
    _keys(value, ('decisions', 'reviews', 'complete'), 'invalid_multi_source_decision')
    if not isinstance(value['decisions'], list):
        _fail('invalid_multi_source_decision')
    raw = {'decisions': [], 'reviews': deepcopy(value['reviews']), 'complete': value['complete']}
    explicit_checks = {}
    for value_decision in value['decisions']:
        if not isinstance(value_decision, dict):
            _fail('invalid_multi_source_decision')
        item = deepcopy(value_decision)
        fields = ('source_explicit', 'no_novel_inference', 'source_identity_preserved')
        if any(type(item.get(field)) is not bool for field in fields):
            _fail('invalid_multi_source_decision')
        checks = {field: item.pop(field) for field in fields}
        if item.get('verdict') in ('accepted', 'reused') and not all(checks.values()):
            _fail('i2k_explicit_source_acceptance_required')
        key = item.get('candidate_key')
        if not isinstance(key, str) or key in explicit_checks:
            _fail('invalid_multi_source_decision')
        explicit_checks[key] = checks
        raw['decisions'].append(item)
    checked = validate_selection_decisions(raw, candidates, existing_ids, ids)
    for key, decision in checked['decisions'].items():
        decision.update(explicit_checks[key])
    units = {unit['information_id']: unit for unit in bundle['model_input']['information']}
    for review in checked['reviews']:
        review['data_id'] = units[review['information_id']]['data_id']
    return checked


def check_scope_reuse(candidate, existing):
    """Classified source identity keeps its owner even with external evidence.

    Binding unclassified historical nodes needs Runtime's atomic authority and
    owner-source evidence checks; this helper never invents that classification.
    """
    if candidate['kind'] != existing['kind']:
        _fail('knowledge_scope_reuse_conflict')
    classified = existing.get('identity_scope')
    if classified is not None and (classified != candidate['identity_scope']
            or (classified == 'source' and existing.get('source_data_id') != candidate['source_data_id'])):
        _fail('knowledge_scope_reuse_conflict')
    return True
