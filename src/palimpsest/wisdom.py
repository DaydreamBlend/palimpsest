"""Immutable W value assembly; application IDs, no persistence or authority."""

from copy import deepcopy
from datetime import datetime

from . import k2w
from .i2k import digest
from .knowledge import _fail, _uuid


SCHEMA = 'wisdom-v1'


def build_snapshot(*, wisdom_id, execution_id, created_at, packet, answer,
                   validation, generation_profile):
    """Assemble one independently accepted synthesis, never a Decision or K.

Runtime allocates UUIDv7/time once and atomically freezes the value with exact
read-set and receipt verification. An ordinary new synthesis gets a distinct W.
"""
    _uuid(wisdom_id, 'invalid_wisdom_id')
    _uuid(execution_id, 'invalid_wisdom_execution')
    try:
        stamp = datetime.fromisoformat(created_at)
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError
    except (TypeError, ValueError):
        _fail('invalid_wisdom_created_at')
    if not isinstance(generation_profile, dict) or not generation_profile:
        _fail('invalid_wisdom_profile')
    answer = k2w.normalize_answer(answer, packet)
    validation = k2w.validate_answer(validation, answer)
    if validation['verdict'] != 'accepted':
        _fail('wisdom_requires_independent_acceptance')
    node_ids, edge_ids, citations = [], [], []
    edges = {edge['effective_edge_ref']['semantic_kedge_revision_id']: edge['effective_edge_ref']
             for edge in packet['effective_edges']}
    for claim in answer['claims']:
        node_ids.extend(ref for ref in claim['k_revision_ids'] if ref not in node_ids)
        edge_ids.extend(ref for ref in claim['effective_edge_revision_ids'] if ref not in edge_ids)
        citations.append({'claim_key': claim['claim_key'], 'epistemic_basis': claim['epistemic_basis'],
            'k_revision_ids': list(claim['k_revision_ids']),
            'effective_edge_refs': [deepcopy(edges[ref]) for ref in claim['effective_edge_revision_ids']]})
    value = {'schema_version': SCHEMA, 'wisdom_id': wisdom_id, 'execution_id': execution_id,
        'wisdom_kind': packet['wisdom_kind'], 'query': packet['query'],
        'context_snapshot': deepcopy(packet['context_snapshot']),
        'used_k_revision_ids': node_ids + edge_ids,
        'used_effective_edge_refs': [deepcopy(edges[ref]) for ref in edge_ids],
        'used_information_ids': [], 'retrieval_snapshot': deepcopy(packet['retrieval_snapshot']),
        'evidence_mode': packet['evidence_mode'], 'retrieval_strategy': packet['retrieval_strategy'],
        'epistemic_basis': 'accepted_knowledge', 'answer_or_payload': answer, 'citations': citations,
        'uncertainty': {'unresolved': list(answer['unresolved']), 'claims': [
            {'claim_key': claim['claim_key'], 'assumptions': list(claim['assumptions']),
             'limitations': list(claim['limitations'])} for claim in answer['claims']]},
        'generation_profile': deepcopy(generation_profile), 'validation': validation,
        'input_sha256': packet['input_sha256'], 'created_at': created_at}
    try:
        value['snapshot_sha256'] = digest(value)
    except (TypeError, ValueError, UnicodeError):
        _fail('invalid_wisdom_snapshot')
    return value
