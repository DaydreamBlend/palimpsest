"""Supports proposals over exact accepted KNode revisions; no storage or I2K."""

from copy import deepcopy

from .knowledge import (PROFILE, _array, _decision_reason, _digest, _enum, _fail,
                        _key, _keys, _object, _strings, _text, _uuid,
                        KEY_PATTERN, REASON_PATTERN)


def EDGE_SCHEMA(revision_ids):
    return _object({'edges': _array(_object({
        'candidate_key': {'type': 'string', 'pattern': KEY_PATTERN},
        'from_revision_id': _enum(revision_ids), 'to_revision_id': _enum(revision_ids),
        'predicate': _enum(('supports',)),
        'qualifiers': _object({'scope': {'type': 'string'},
                               'conditions': _array({'type': 'string'})}),
        'rationale': {'type': 'string', 'minLength': 1},
    })), 'complete': {'type': 'boolean'}})


def EDGE_DECISION_SCHEMA(candidate_keys):
    return _object({'decisions': _array(_object({
        'candidate_key': _enum(candidate_keys),
        'verdict': _enum(('accepted', 'rejected', 'needs_human')),
        'reason_codes': _array({'type': 'string', 'pattern': REASON_PATTERN}, nonempty=True),
        'reason': {'type': 'string', 'minLength': 1},
    })), 'complete': {'type': 'boolean'}})


def _qualifiers(value):
    _keys(value, ('scope', 'conditions'), 'invalid_edge_proposal')
    return {'scope': _text(value['scope'], empty=True, code='invalid_edge_proposal'),
            'conditions': sorted(set(_strings(value['conditions'], code='invalid_edge_proposal')))}


def edge_fingerprints(from_knode_id, to_knode_id, predicate, qualifiers):
    source, target = _uuid(from_knode_id), _uuid(to_knode_id)
    if predicate != 'supports' or source == target:
        _fail('invalid_edge_proposal')
    identity = {'profile': PROFILE, 'from_knode_id': source,
                'to_knode_id': target, 'predicate': predicate}
    return {'identity_fingerprint': _digest({'domain': 'kedge-identity', **identity}),
            'content_fingerprint': _digest({'domain': 'kedge-content', **identity,
                                            'qualifiers': _qualifiers(qualifiers)})}


def normalize_edges(response, nodes_by_revision):
    """Callers supply accepted revisions only and recheck their state at commit."""
    code = 'invalid_edge_proposal'
    _keys(response, ('edges', 'complete'), code)
    if type(response['complete']) is not bool or not isinstance(response['edges'], list):
        _fail(code)
    keys, fingerprints, result = set(), set(), []
    for item in response['edges']:
        _keys(item, ('candidate_key', 'from_revision_id', 'to_revision_id',
                     'predicate', 'qualifiers', 'rationale'), code)
        key = _key(item['candidate_key'], code)
        source_id, target_id = _uuid(item['from_revision_id'], code), _uuid(item['to_revision_id'], code)
        source, target = nodes_by_revision.get(source_id), nodes_by_revision.get(target_id)
        if (key in keys or source is None or target is None or item['predicate'] != 'supports'
                or source['kind'] not in ('observation', 'proposition') or target['kind'] != 'proposition'
                or str(source['knode_id']) == str(target['knode_id'])):
            _fail(code)
        keys.add(key)
        qualifiers = _qualifiers(item['qualifiers'])
        fp = edge_fingerprints(str(source['knode_id']), str(target['knode_id']), item['predicate'], qualifiers)
        if fp['content_fingerprint'] in fingerprints:
            _fail('duplicate_edge_proposal')
        fingerprints.add(fp['content_fingerprint'])
        result.append({**deepcopy(item), 'qualifiers': qualifiers,
                       'rationale': _text(item['rationale'], code=code), **fp})
    return result


def validate_edge_decisions(value, candidates):
    code = 'invalid_edge_decision'
    _keys(value, ('decisions', 'complete'), code)
    if value['complete'] is not True or not isinstance(value['decisions'], list):
        _fail(code)
    keys = {candidate['candidate_key'] for candidate in candidates}
    if len(keys) != len(candidates):
        _fail(code)
    result = {}
    for item in value['decisions']:
        _keys(item, ('candidate_key', 'verdict', 'reason_codes', 'reason'), code)
        key = _key(item['candidate_key'], code)
        if key not in keys or key in result or item['verdict'] not in ('accepted', 'rejected', 'needs_human'):
            _fail(code)
        result[key] = {**deepcopy(item), **_decision_reason(item, code)}
    if set(result) != keys:
        _fail(code)
    return result
