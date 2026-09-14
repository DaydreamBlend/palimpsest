"""Explicit, pure material-revision comparisons over an exact current K target.

Ordinary I2K/D2K/K2K owns evidence normalization and independent source/inference
validation. Runtime owns actual accepted/current reads, authority, Record IDs,
CAS and atomic publication. This module creates no new operation or Record type.
"""

from copy import deepcopy

from .data import data_id as check_digest
from .i2k_selection import selection_fingerprints
from .knowledge import (_array, _digest, _enum, _fail, _keys, _object, _text, _uuid,
    _decision_reason, normalize_semantic_payload, REASON_PATTERN)


PROFILE = 'explicit-knowledge-revision-v1'
TARGET_SCHEMA = 'knowledge-revision-target-v1'
_OPERATIONS = ('i2k', 'd2k', 'k2k')
_TARGET_FIELDS = ('knode_id', 'knode_revision_id', 'current_revision_id', 'kind',
    'identity_scope', 'source_data_id', 'semantic_payload', 'statement',
    'identity_fingerprint', 'content_fingerprint', 'origin_record_id')
_REVIEW_FIELDS = ('comparison_base_revision_id', 'same_identity', 'material_change',
                  'grounding_valid', 'reason_codes', 'reason')


def freeze_target(target, *, operation, target_knode_id, expected_revision_id):
    """Freeze the caller-selected current target, excluding all raw source refs."""
    if (operation not in _OPERATIONS or not isinstance(target, dict)
            or not set(_TARGET_FIELDS) <= target.keys()):
        _fail('invalid_knowledge_revision_target')
    _uuid(target_knode_id, 'invalid_knowledge_revision_target')
    _uuid(expected_revision_id, 'invalid_knowledge_revision_target')
    if (target['knode_id'] != target_knode_id or target['knode_revision_id'] != expected_revision_id
            or target['current_revision_id'] != expected_revision_id):
        _fail('knowledge_revision_target_changed')
    _uuid(target['origin_record_id'], 'invalid_knowledge_revision_target')
    check_digest(target['identity_fingerprint'])
    check_digest(target['content_fingerprint'])
    semantic = normalize_semantic_payload(target['semantic_payload'])
    # Reject an unclassified target rather than inventing a new identity/scope.
    selection_fingerprints(target['kind'], semantic, target['identity_scope'], target['source_data_id'])
    _text(target['statement'], code='invalid_knowledge_revision_target')
    frozen = {field: deepcopy(target[field]) for field in _TARGET_FIELDS}
    if 'current_applicability' in target:
        if target['current_applicability'] not in ('current_premises', 'needs_revalidation'):
            _fail('invalid_knowledge_revision_target')
        frozen['current_applicability'] = target['current_applicability']
    result = {'schema_version': TARGET_SCHEMA, 'operation': operation, 'target_knode_id': target_knode_id,
        'expected_revision_id': expected_revision_id, 'target': frozen}
    return {**result, 'target_sha256': _digest(result)}


def check_target(snapshot):
    _keys(snapshot, ('schema_version', 'operation', 'target_knode_id', 'expected_revision_id', 'target', 'target_sha256'),
          'invalid_knowledge_revision_target')
    expected = freeze_target(snapshot['target'], operation=snapshot['operation'],
        target_knode_id=snapshot['target_knode_id'], expected_revision_id=snapshot['expected_revision_id'])
    if snapshot != expected:
        _fail('knowledge_revision_target_changed')
    return deepcopy(snapshot['target'])


def _evidence_boundary(candidate, operation, expected_revision_id):
    """Check operation shape; this does not prove source delivery or grounding."""
    if operation == 'k2k':
        refs = candidate.get('premise_revision_ids')
        if (candidate.get('kind') != 'proposition' or 'evidence' in candidate or 'direct_evidence' in candidate
                or candidate.get('is_inferred', True) is not True
                or not isinstance(refs, list) or len(refs) < 2):
            _fail('knowledge_revision_premise_boundary')
        for identifier in refs:
            _uuid(identifier, 'knowledge_revision_premise_boundary')
        if len(refs) != len(set(refs)) or expected_revision_id in refs:
            # Publishing a successor would immediately stale its own origin
            # premise. The previous target is comparison context, not a premise.
            _fail('knowledge_revision_premise_boundary')
        return
    field, other = ('evidence', 'direct_evidence') if operation == 'i2k' else ('direct_evidence', 'evidence')
    citations = candidate.get(field)
    if (candidate.get('claim_basis') != 'explicit_source_content' or candidate.get('is_inferred') is not False
            or other in candidate or 'premise_revision_ids' in candidate
            or not isinstance(citations, list) or not citations):
        _fail('knowledge_revision_source_boundary')
    for citation in citations:
        if not isinstance(citation, dict):
            _fail('knowledge_revision_source_boundary')
        if operation == 'i2k':
            _uuid(citation.get('information_id'), 'knowledge_revision_source_boundary')
            if 'view_id' in citation:
                _fail('knowledge_revision_source_boundary')
        else:
            _uuid(citation.get('view_id'), 'knowledge_revision_source_boundary')
            check_digest(citation.get('data_id'))
            if 'information_id' in citation:
                _fail('knowledge_revision_source_boundary')


def bind_candidate(candidate, snapshot):
    """Bind an already normalized ordinary candidate to the explicit target.

The candidate's source/premise details remain unchanged. Its logical fingerprint
is the target's immutable fingerprint; only its content fingerprint is new.
"""
    target = check_target(snapshot)
    if not isinstance(candidate, dict) or any(field in candidate for field in (
            'knode_id', 'knode_revision_id', 'supersedes_revision_id', 'origin_record_id', 'generation_origin')):
        _fail('invalid_knowledge_revision_candidate')
    if any(candidate.get(field) != target[field] for field in ('kind', 'identity_scope', 'source_data_id')):
        _fail('knowledge_revision_identity_mismatch')
    _text(candidate.get('statement'), code='invalid_knowledge_revision_candidate')
    semantic = normalize_semantic_payload(candidate.get('semantic_payload'))
    computed = selection_fingerprints(candidate['kind'], semantic, candidate['identity_scope'], candidate['source_data_id'])
    binding = {'knode_id': snapshot['target_knode_id'], 'expected_revision_id': snapshot['expected_revision_id'],
               'target_sha256': snapshot['target_sha256']}
    already_bound = 'revision_target' in candidate
    if already_bound and candidate['revision_target'] != binding:
        _fail('knowledge_revision_target_changed')
    expected_identity = target['identity_fingerprint'] if already_bound else computed['identity_fingerprint']
    if (candidate.get('identity_fingerprint') != expected_identity
            or candidate.get('content_fingerprint') != computed['content_fingerprint']):
        _fail('knowledge_revision_candidate_changed')
    _evidence_boundary(candidate, snapshot['operation'], snapshot['expected_revision_id'])
    return {**deepcopy(candidate), 'semantic_payload': semantic, 'revision_target': binding,
        'identity_fingerprint': target['identity_fingerprint'], 'content_fingerprint': computed['content_fingerprint']}


def review_schema(snapshot):
    check_target(snapshot)
    return _object({'comparison_base_revision_id': _enum((snapshot['expected_revision_id'],)),
        'same_identity': {'type': 'boolean'}, 'material_change': {'type': ['boolean', 'null']},
        'grounding_valid': {'type': 'boolean'},
        'reason_codes': _array({'type': 'string', 'pattern': REASON_PATTERN}, nonempty=True),
        'reason': {'type': 'string', 'minLength': 1}})


def resolve(candidate, snapshot, review):
    """Return the publication action; never infer materiality from inequality."""
    bound = bind_candidate(candidate, snapshot)
    target = snapshot['target']
    _keys(review, _REVIEW_FIELDS, 'invalid_knowledge_revision_review')
    if (review['comparison_base_revision_id'] != snapshot['expected_revision_id']
            or type(review['same_identity']) is not bool or type(review['grounding_valid']) is not bool
            or (review['material_change'] is not None and type(review['material_change']) is not bool)):
        _fail('invalid_knowledge_revision_review')
    reviewed = {**deepcopy(review), **_decision_reason(review, 'invalid_knowledge_revision_review')}
    reasons = []
    if not review['same_identity']:
        reasons.append('knowledge_revision_identity_unconfirmed')
    if not review['grounding_valid']:
        reasons.append('knowledge_revision_grounding_unconfirmed')
    if review['material_change'] is None:
        reasons.append('knowledge_revision_materiality_undecidable')
    same_content = (normalize_semantic_payload(target['semantic_payload']) == bound['semantic_payload']
                    or target['content_fingerprint'] == bound['content_fingerprint'])
    if review['material_change'] is True and same_content:
        reasons.append('knowledge_revision_materiality_conflict')
    action = 'needs_human' if reasons else 'accepted_revision' if review['material_change'] else 'reused'
    origin = ({'mode': 'new_record', 'origin_operation': snapshot['operation'], 'is_inferred': snapshot['operation'] == 'k2k'}
              if action == 'accepted_revision' else {'mode': 'preserve_existing', 'origin_record_id': target['origin_record_id']}
              if action == 'reused' else {'mode': 'no_publication'})
    return {'action': action, 'revision_target': deepcopy(bound['revision_target']),
        'identity_fingerprint': target['identity_fingerprint'],
        'candidate_content_fingerprint': bound['content_fingerprint'],
        'result_content_fingerprint': (bound['content_fingerprint'] if action == 'accepted_revision'
            else target['content_fingerprint'] if action == 'reused' else None),
        'origin': origin, 'review': reviewed, 'reason_codes': reasons}
