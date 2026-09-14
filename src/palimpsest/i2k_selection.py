"""Full-source I review and scoped Knowledge selection, without I/O or scoring.

Scripts check coverage and binding. The model chooses importance and whether a
proposition is reusable general knowledge or a claim about this source's study.
"""

from copy import deepcopy

from .data import data_id
from .knowledge import (NODE_SCHEMA, NODE_DECISION_SCHEMA, _array, _digest, _enum,
                        _fail, _key, _keys, _object, _strings, _text, _decision_reason, REASON_PATTERN, normalize_nodes,
                        normalize_semantic_payload, validate_node_decisions)


PROFILE = 'source-complete-i2k-v1'
SCOPES = ('general', 'source')
REVIEW_DISPOSITIONS = ('selected', 'context_only', 'not_selected', 'needs_review')


def selection_schema(information_ids, media_sha256s):
    schema = NODE_SCHEMA(information_ids, media_sha256s)
    node = schema['properties']['nodes']['items']
    node['properties'].update(identity_scope=_enum(SCOPES),
                              selection_reason={'type': 'string', 'minLength': 1})
    node['required'] = list(node['properties'])
    node['properties']['evidence']['items']['properties']['quote']['minLength'] = 0
    schema['properties']['reviews'] = _array(_object({
        'information_id': _enum(information_ids), 'disposition': _enum(REVIEW_DISPOSITIONS),
        'candidate_keys': _array({'type': 'string'}), 'reason': {'type': 'string', 'minLength': 1},
    }))
    schema['required'] = list(schema['properties'])
    return schema


def selection_decision_schema(candidate_keys, existing_revision_ids, information_ids):
    schema = NODE_DECISION_SCHEMA(candidate_keys, existing_revision_ids)
    item = schema['properties']['decisions']['items']
    if not candidate_keys:
        item['properties']['candidate_key'] = {'type': 'string'}
        item['properties']['equivalent_candidate_key'] = {'type': ['string', 'null']}
        schema['properties']['decisions']['maxItems'] = 0
    item['properties'].update(scope_correct={'type': 'boolean'}, importance_justified={'type': 'boolean'})
    item['required'] = list(item['properties'])
    if candidate_keys:
        nonreuse = deepcopy(item['properties'])
        nonreuse.update(verdict=_enum(('accepted', 'rejected', 'needs_human')),
                        equivalent_candidate_key={'type': 'null'}, equivalent_revision_id={'type': 'null'})
        batch = deepcopy(item['properties'])
        batch.update(verdict=_enum(('reused',)), equivalent_candidate_key=_enum(candidate_keys),
                     equivalent_revision_id={'type': 'null'})
        branches = [_object(nonreuse), _object(batch)]
        if existing_revision_ids:
            existing = deepcopy(item['properties'])
            existing.update(verdict=_enum(('reused',)), equivalent_candidate_key={'type': 'null'},
                            equivalent_revision_id=_enum(existing_revision_ids))
            branches.append(_object(existing))
        schema['properties']['decisions']['items'] = {'anyOf': branches}
    schema['properties']['reviews'] = _array(_object({
        'information_id': _enum(information_ids), 'verdict': _enum(('confirmed', 'needs_review')),
        'reason_codes': _array({'type': 'string', 'pattern': REASON_PATTERN}, nonempty=True),
        'reason': {'type': 'string', 'minLength': 1},
    }))
    schema['required'] = list(schema['properties'])
    return schema


def check_selection_input(packet):
    """Canonical membership is checked separately by Runtime against the DB."""
    if (not isinstance(packet, dict) or packet.get('schema_version') != 'i2k-input-v1'
            or packet.get('excluded_information_ids') != [] or packet.get('context_information_ids') != []):
        _fail('selection_requires_all_information')
    units = packet.get('model_input', {}).get('information')
    if not isinstance(units, list) or not units:
        _fail('selection_requires_all_information')
    ids = [unit['information_id'] for unit in units]
    if (len(ids) != len(set(ids)) or packet.get('target_information_ids') != ids
            or any(unit.get('role') != 'target' for unit in units)):
        _fail('selection_requires_all_information')
    return ids


def selection_fingerprints(kind, semantic_payload, identity_scope, source_data_id=None):
    if identity_scope not in SCOPES or kind not in ('proposition', 'observation'):
        _fail('invalid_knowledge_identity_scope')
    if kind == 'observation' and identity_scope != 'source':
        _fail('observation_requires_source_scope')
    if identity_scope == 'source':
        data_id(source_data_id)
    elif source_data_id is not None:
        _fail('invalid_knowledge_identity_scope')
    seed = {'profile': PROFILE, 'kind': kind, 'identity_scope': identity_scope,
            'source_data_id': source_data_id, 'semantic_payload': normalize_semantic_payload(semantic_payload)}
    return {'identity_fingerprint': _digest({'domain': 'knode-exact', **seed}),
            'content_fingerprint': _digest({'domain': 'knode-content', **seed})}


def normalize_selection(response, packet):
    information_ids = check_selection_input(packet)
    _keys(response, ('nodes', 'source_requests', 'complete', 'coverage_notes', 'reviews'), 'invalid_selection_response')
    if not isinstance(response['nodes'], list):
        _fail('invalid_selection_response')
    raw = deepcopy(response)
    raw.pop('reviews')
    scopes = []
    for item in raw['nodes']:
        if not isinstance(item, dict) or 'identity_scope' not in item or 'selection_reason' not in item:
            _fail('invalid_selection_response')
        scopes.append((item.pop('identity_scope'), _text(item.pop('selection_reason'))))
    nodes = normalize_nodes(raw, packet, allow_media_only=True)
    by_key = {}
    for node, (scope, reason) in zip(nodes, scopes):
        source_id = packet['data_id'] if scope == 'source' else None
        node.update(identity_scope=scope, source_data_id=source_id, selection_reason=reason,
                    **selection_fingerprints(node['kind'], node['semantic_payload'], scope, source_id))
        by_key[node['candidate_key']] = node
    reviews = {}
    link_completions = []
    if not isinstance(response['reviews'], list):
        _fail('invalid_selection_reviews')
    for item in response['reviews']:
        _keys(item, ('information_id', 'disposition', 'candidate_keys', 'reason'), 'invalid_selection_reviews')
        identifier, disposition = item['information_id'], item['disposition']
        if not isinstance(identifier, str) or identifier not in information_ids or identifier in reviews:
            _fail('selection_review_coverage_mismatch')
        keys = _strings(item['candidate_keys'])
        if (disposition not in REVIEW_DISPOSITIONS or len(keys) != len(set(keys))
                or not set(keys) <= by_key.keys()
                or (disposition in ('context_only', 'not_selected') and keys)):
            _fail('invalid_selection_reviews')
        for key in keys:
            if identifier not in {citation['information_id'] for citation in by_key[key]['evidence']}:
                _fail('selection_review_evidence_mismatch')
        actual_keys = [key for key,node in by_key.items()
                       if identifier in {citation['information_id'] for citation in node['evidence']}]
        if disposition == 'selected':
            if not actual_keys:
                _fail('invalid_selection_reviews')
            missing = [key for key in actual_keys if key not in keys]
            if missing:
                link_completions.append({'information_id':identifier,'added_candidate_keys':missing,
                    'basis':'existing_candidate_evidence; importance_disposition_unchanged'})
            keys = actual_keys
        reviews[identifier] = {**deepcopy(item), 'candidate_keys': keys, 'reason': _text(item['reason'])}
    if set(reviews) != set(information_ids):
        _fail('selection_review_coverage_mismatch')
    # Every candidate's actual I evidence must be accounted for, including mixed
    # groups. A context-only I may be read without becoming a Knowledge claim.
    for key, node in by_key.items():
        for citation in node['evidence']:
            if key not in reviews[citation['information_id']]['candidate_keys']:
                _fail('selection_review_evidence_mismatch')
    if response['complete'] and any(review['disposition'] == 'needs_review' for review in reviews.values()):
        _fail('unresolved_selection_reviews')
    return {'nodes': nodes, 'reviews': [reviews[identifier] for identifier in information_ids],
            'link_completions':link_completions}


def validate_selection_decisions(value, candidates, existing_ids, information_ids):
    _keys(value, ('decisions', 'reviews', 'complete'), 'invalid_selection_decision')
    if not isinstance(value['decisions'], list) or type(value['complete']) is not bool:
        _fail('invalid_selection_decision')
    # The legacy helper verifies exhaustive decision coverage and reuse links.
    # A complete set of decisions can still report unresolved semantic review.
    raw = {'complete': True, 'decisions': []}
    classifications = {}
    for item in value['decisions']:
        if not isinstance(item, dict) or type(item.get('scope_correct')) is not bool or type(item.get('importance_justified')) is not bool:
            _fail('invalid_selection_decision')
        decision = deepcopy(item)
        candidate_key = _key(item.get('candidate_key'), 'invalid_selection_decision')
        classifications[candidate_key] = {
            'scope_correct': decision.pop('scope_correct'),
            'importance_justified': decision.pop('importance_justified')}
        if decision.get('verdict') in ('accepted', 'reused') and not all(classifications[item['candidate_key']].values()):
            _fail('selection_acceptance_not_justified')
        raw['decisions'].append(decision)
    decisions = validate_node_decisions(raw, candidates, existing_ids)
    for key, decision in decisions.items():
        decision.update(classifications[key])
    if not isinstance(value['reviews'], list):
        _fail('invalid_selection_decision')
    reviews = {}
    for review in value['reviews']:
        _keys(review, ('information_id', 'verdict', 'reason_codes', 'reason'), 'invalid_selection_decision')
        identifier = review['information_id']
        if (not isinstance(identifier, str) or identifier not in information_ids or identifier in reviews
                or review['verdict'] not in ('confirmed', 'needs_review')):
            _fail('selection_review_coverage_mismatch')
        reviews[identifier] = {**deepcopy(review), **_decision_reason(review, 'invalid_selection_decision')}
    if set(reviews) != set(information_ids):
        _fail('selection_review_coverage_mismatch')
    return {'decisions': decisions, 'reviews': [reviews[identifier] for identifier in information_ids],
            'complete': value['complete']}


def check_scope_reuse(candidate, existing, current_data_id):
    """Require explicit compatible classifications; never rewrite legacy FP."""
    scope = candidate['identity_scope']
    classified = existing.get('identity_scope')
    source_id = existing.get('source_data_id')
    if classified is None:
        grounded = set(existing.get('grounding_data_ids', []))
        if scope == 'source' and grounded != {current_data_id}:
            _fail('knowledge_scope_reuse_conflict')
    elif classified != scope or (scope == 'source' and source_id != current_data_id):
        _fail('knowledge_scope_reuse_conflict')
    if scope == 'source' and candidate['source_data_id'] != current_data_id:
        _fail('knowledge_scope_reuse_conflict')
    if candidate['kind'] != existing['kind']:
        _fail('knowledge_scope_reuse_conflict')
    return True
