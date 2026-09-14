"""K-grounded explanation/recommendation contracts; no calls or storage.

Runtime owns canonical acceptance, currentness and independent model delivery.
Context can constrain advice but is never promoted to accepted Knowledge.
"""

from copy import deepcopy

from .data import data_id
from .i2k import digest
from .k2k_effective import check_ref, EDGE_FIELDS
from .knowledge import (_array, _enum, _fail, _key, _keys, _object, _strings,
                        _text, _uuid, normalize_semantic_payload, KEY_PATTERN)
from .n2e import _qualifiers
from .n2e_relations import canonical_pair


PROFILE = 'knowledge-wisdom-v1'
INPUT_SCHEMA = 'k2w-input-v1'
ANSWER_SCHEMA = 'k2w-answer-v1'
KINDS = ('explanation', 'recommendation')
CLAIM_FIELDS = ('claim_key', 'text', 'epistemic_basis', 'k_revision_ids',
                'effective_edge_revision_ids', 'assumptions', 'limitations')
CLAIM_CHECKS = ('supported', 'citations_sufficient', 'scope_preserved',
                'limits_preserved', 'no_unattributed_inference')


def build_input(nodes, effective_edges=None, *, query, context_snapshot,
                knowledge_state_version, wisdom_kind='explanation', retrieval_snapshot=None):
    if (wisdom_kind not in KINDS or not isinstance(context_snapshot, dict)
            or type(knowledge_state_version) is not int or knowledge_state_version < 0
            or not isinstance(nodes, list) or not nodes
            or (retrieval_snapshot is not None and not isinstance(retrieval_snapshot, dict))):
        _fail('invalid_k2w_input')
    _text(query, code='invalid_k2w_input')
    revisions, logical = {}, set()
    for node in nodes:
        if not isinstance(node, dict):
            _fail('invalid_k2w_input')
        identifier = _uuid(node.get('knode_id'), 'invalid_k2w_input')
        revision = _uuid(node.get('knode_revision_id'), 'invalid_k2w_input')
        if (identifier in logical or revision in revisions
                or node.get('kind') not in ('proposition', 'observation')
                or node.get('current_revision_id', revision) != revision):
            _fail('invalid_k2w_input')
        _text(node.get('statement'), code='invalid_k2w_input')
        normalize_semantic_payload(node.get('semantic_payload'))
        data_id(node.get('current_support_signature'))
        revisions[revision] = node
        logical.add(identifier)
    edges = [] if effective_edges is None else effective_edges
    if not isinstance(edges, list):
        _fail('invalid_k2w_input')
    edge_ids, edge_logical, pairs = set(), set(), set()
    for edge in edges:
        _keys(edge, EDGE_FIELDS, 'invalid_k2w_edge')
        identifier = _uuid(edge['kedge_id'], 'invalid_k2w_edge')
        ref = check_ref(edge['effective_edge_ref'])
        source, target = (revisions.get(ref[name]) for name in
                          ('from_knode_revision_id', 'to_knode_revision_id'))
        if source is None or target is None:
            _fail('k2w_effective_endpoint_missing')
        pair = (edge['predicate'], source['knode_id'], target['knode_id'])
        if (identifier in edge_logical or ref['semantic_kedge_revision_id'] in edge_ids
                or pair in pairs or canonical_pair(edge['predicate'], source, target) != (source, target)
                or _qualifiers(edge['qualifiers']) != edge['qualifiers']
                or edge['endpoint_support_signatures'] != [source['current_support_signature'], target['current_support_signature']]):
            _fail('invalid_k2w_edge')
        originals = [_uuid(edge[name], 'invalid_k2w_edge') for name in
                     ('original_from_revision_id', 'original_to_revision_id')]
        if (originals[0] == originals[1] or (ref['applicability_basis_type'] == 'origin_acceptance'
                and originals != [ref['from_knode_revision_id'], ref['to_knode_revision_id']])):
            _fail('invalid_k2w_edge')
        edge_logical.add(identifier)
        edge_ids.add(ref['semantic_kedge_revision_id'])
        pairs.add(pair)
    packet = {'schema_version': INPUT_SCHEMA, 'wisdom_kind': wisdom_kind, 'query': query,
              'context_snapshot': deepcopy(context_snapshot), 'nodes': deepcopy(nodes),
              'effective_edges': deepcopy(edges), 'knowledge_state_version': knowledge_state_version,
              'retrieval_snapshot': deepcopy(retrieval_snapshot or {}),
              'evidence_mode': 'knowledge_only', 'retrieval_strategy': 'standard'}
    try:
        packet['input_sha256'] = digest(packet)
    except (TypeError, ValueError, UnicodeError):
        _fail('invalid_k2w_input')
    return packet


def check_input(packet):
    fields = ('schema_version', 'wisdom_kind', 'query', 'context_snapshot', 'nodes',
              'effective_edges', 'knowledge_state_version', 'retrieval_snapshot',
              'evidence_mode', 'retrieval_strategy', 'input_sha256')
    _keys(packet, fields, 'invalid_k2w_input')
    rebuilt = build_input(packet['nodes'], packet['effective_edges'], query=packet['query'],
        context_snapshot=packet['context_snapshot'], wisdom_kind=packet['wisdom_kind'],
        knowledge_state_version=packet['knowledge_state_version'], retrieval_snapshot=packet['retrieval_snapshot'])
    if rebuilt != packet:
        _fail('k2w_input_changed')
    return [node['knode_revision_id'] for node in packet['nodes']]


def _refs_schema(refs):
    return _array(_enum(refs)) if refs else {**_array({'type': 'string'}), 'maxItems': 0}


def generation_schema(packet):
    nodes = check_input(packet)
    edges = [edge['effective_edge_ref']['semantic_kedge_revision_id'] for edge in packet['effective_edges']]
    text = {'type': 'string', 'minLength': 1}
    key = {'type': 'string', 'pattern': KEY_PATTERN}
    recommendation = _object({
        'options': _array(_object({'option_key': key, 'label': text}), nonempty=True),
        'criteria': _array(text, nonempty=True),
        'comparison': _array(_object({'option_key': key, 'criterion': text,
                                     'claim_keys': _array(key, nonempty=True)}), nonempty=True),
        'recommended_option': {'type': ['string', 'null'], 'pattern': KEY_PATTERN},
    })
    bases = ('accepted_knowledge', 'advisory_recommendation') if packet['wisdom_kind'] == 'recommendation' else ('accepted_knowledge',)
    return _object({'status': _enum(('answered', 'insufficient')),
        'claims': _array(_object({'claim_key': key, 'text': text, 'epistemic_basis': _enum(bases),
            'k_revision_ids': {**_refs_schema(nodes), 'minItems': 1},
            'effective_edge_revision_ids': _refs_schema(edges),
            'assumptions': _array(text), 'limitations': _array(text)})),
        'recommendation': {'anyOf': [recommendation, {'type': 'null'}]} if packet['wisdom_kind'] == 'recommendation' else {'type': 'null'},
        'unresolved': _array(text)})


def _selected_refs(values, allowed, *, nonempty=False):
    if (not isinstance(values, list) or (nonempty and not values)
            or any(not isinstance(value, str) or value not in allowed for value in values)
            or len(values) != len(set(values))):
        _fail('k2w_citation_not_delivered')
    return list(values)


def normalize_answer(response, packet):
    nodes = check_input(packet)
    edges = {edge['effective_edge_ref']['semantic_kedge_revision_id']: edge['effective_edge_ref']
             for edge in packet['effective_edges']}
    _keys(response, ('status', 'claims', 'recommendation', 'unresolved'), 'invalid_k2w_answer')
    if response['status'] not in ('answered', 'insufficient') or not isinstance(response['claims'], list):
        _fail('invalid_k2w_answer')
    result = deepcopy(response)
    result['unresolved'] = _strings(response['unresolved'], code='invalid_k2w_answer')
    if ((response['status'] == 'answered' and not response['claims'])
            or (response['status'] == 'insufficient' and not result['unresolved'])):
        _fail('invalid_k2w_answer')
    keys = set()
    for claim in result['claims']:
        _keys(claim, CLAIM_FIELDS, 'invalid_k2w_claim')
        key = _key(claim['claim_key'], 'invalid_k2w_claim')
        if key in keys or claim['epistemic_basis'] not in ('accepted_knowledge', 'advisory_recommendation'):
            _fail('invalid_k2w_claim')
        if claim['epistemic_basis'] == 'advisory_recommendation' and packet['wisdom_kind'] != 'recommendation':
            _fail('k2w_advisory_kind_required')
        keys.add(key)
        claim['text'] = _text(claim['text'], code='invalid_k2w_claim')
        claim['k_revision_ids'] = _selected_refs(claim['k_revision_ids'], nodes, nonempty=True)
        selected = _selected_refs(claim['effective_edge_revision_ids'], edges)
        for revision in selected:
            if any(edges[revision][field] not in claim['k_revision_ids'] for field in
                   ('from_knode_revision_id', 'to_knode_revision_id')):
                _fail('k2w_citation_endpoint_missing')
        for name in ('assumptions', 'limitations'):
            claim[name] = _strings(claim[name], code='invalid_k2w_claim')
    recommendation = result['recommendation']
    if packet['wisdom_kind'] == 'explanation':
        if recommendation is not None:
            _fail('k2w_advisory_kind_required')
    elif recommendation is None:
        if result['status'] != 'insufficient':
            _fail('k2w_recommendation_required')
    else:
        _keys(recommendation, ('options', 'criteria', 'comparison', 'recommended_option'), 'invalid_k2w_recommendation')
        if not isinstance(recommendation['options'], list) or not recommendation['options']:
            _fail('invalid_k2w_recommendation')
        options = set()
        for option in recommendation['options']:
            _keys(option, ('option_key', 'label'), 'invalid_k2w_recommendation')
            key = _key(option['option_key'], 'invalid_k2w_recommendation')
            if key in options:
                _fail('invalid_k2w_recommendation')
            options.add(key)
            option['label'] = _text(option['label'], code='invalid_k2w_recommendation')
        criteria = _strings(recommendation['criteria'], code='invalid_k2w_recommendation')
        if not criteria or len(criteria) != len(set(criteria)):
            _fail('invalid_k2w_recommendation')
        recommendation['criteria'] = criteria
        comparison = recommendation['comparison']
        if not isinstance(comparison, list):
            _fail('invalid_k2w_recommendation')
        pairs = set()
        for entry in comparison:
            _keys(entry, ('option_key', 'criterion', 'claim_keys'), 'invalid_k2w_recommendation')
            _key(entry['option_key'], 'invalid_k2w_recommendation')
            _text(entry['criterion'], code='invalid_k2w_recommendation')
            pair = (entry['option_key'], entry['criterion'])
            if (entry['option_key'] not in options or entry['criterion'] not in criteria or pair in pairs):
                _fail('invalid_k2w_recommendation')
            _selected_refs(entry['claim_keys'], keys, nonempty=True)
            pairs.add(pair)
        if pairs != {(option, criterion) for option in options for criterion in criteria}:
            _fail('k2w_comparison_incomplete')
        if recommendation['recommended_option'] is not None:
            _key(recommendation['recommended_option'], 'invalid_k2w_recommendation')
            if recommendation['recommended_option'] not in options:
                _fail('invalid_k2w_recommendation')
    return result


def validation_schema(answer):
    keys = [claim['claim_key'] for claim in answer['claims']]
    claim = _object({'claim_key': _enum(keys) if keys else {'type': 'string'},
                     **{name: {'type': 'boolean'} for name in CLAIM_CHECKS}})
    claims = _array(claim)
    if not keys:
        claims['maxItems'] = 0
    return _object({'verdict': _enum(('accepted', 'rejected', 'needs_human')), 'claims': claims,
        'query_addressed': {'type': 'boolean'}, 'advisory_boundary_preserved': {'type': 'boolean'},
        'reason': {'type': 'string', 'minLength': 1}})


def validate_answer(response, answer):
    _keys(response, ('verdict', 'claims', 'query_addressed', 'advisory_boundary_preserved', 'reason'), 'invalid_k2w_validation')
    if (response['verdict'] not in ('accepted', 'rejected', 'needs_human')
            or not isinstance(response['claims'], list)
            or any(type(response[name]) is not bool for name in ('query_addressed', 'advisory_boundary_preserved'))):
        _fail('invalid_k2w_validation')
    expected = {claim['claim_key'] for claim in answer['claims']}
    seen = set()
    for item in response['claims']:
        _keys(item, ('claim_key', *CLAIM_CHECKS), 'invalid_k2w_validation')
        key = _key(item['claim_key'], 'invalid_k2w_validation')
        if key in seen or key not in expected or any(type(item[name]) is not bool for name in CLAIM_CHECKS):
            _fail('invalid_k2w_validation')
        if response['verdict'] == 'accepted' and not all(item[name] for name in CLAIM_CHECKS):
            _fail('k2w_acceptance_not_justified')
        seen.add(key)
    if seen != expected:
        _fail('k2w_validation_incomplete')
    if response['verdict'] == 'accepted' and not all(response[name] for name in ('query_addressed', 'advisory_boundary_preserved')):
        _fail('k2w_acceptance_not_justified')
    result = deepcopy(response)
    result['reason'] = _text(response['reason'], code='invalid_k2w_validation')
    return result
