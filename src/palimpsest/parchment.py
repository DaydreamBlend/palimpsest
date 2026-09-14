"""Deterministic W2P: compose exact immutable Wisdom without new assertions."""

from copy import deepcopy
from datetime import datetime

from .data import data_id
from .errors import PalimpsestError
from .i2k import digest
from .knowledge import _text, _uuid
from .wisdom import SCHEMA as WISDOM_SCHEMA


SCHEMA = 'parchment-v1'
PROFILE = 'w2p-exact-wisdom-v1'
SECTION_FIELDS = ('wisdom_id', 'wisdom_kind', 'query', 'context_snapshot',
                  'evidence_mode', 'epistemic_basis', 'answer_or_payload', 'uncertainty')


def _fail(code):
    raise PalimpsestError(code, 'Parchment의 정확한 Wisdom·인용·불변 snapshot을 확인하세요.', 4)


def check_wisdom(value):
    if not isinstance(value, dict) or value.get('schema_version') != WISDOM_SCHEMA:
        _fail('invalid_parchment_wisdom')
    _uuid(value.get('wisdom_id'), 'invalid_parchment_wisdom')
    data_id(value.get('snapshot_sha256'))
    if (value.get('wisdom_kind') not in ('explanation', 'recommendation')
            or not isinstance(value.get('answer_or_payload'), dict)
            or not isinstance(value['answer_or_payload'].get('claims'), list)
            or not isinstance(value.get('citations'), list)
            or any(name not in value for name in SECTION_FIELDS)
            or not isinstance(value.get('validation'), dict)
            or value.get('validation', {}).get('verdict') != 'accepted'):
        _fail('invalid_parchment_wisdom')
    try:
        expected = digest({key: item for key, item in value.items() if key != 'snapshot_sha256'})
    except (TypeError, ValueError, UnicodeError):
        _fail('invalid_parchment_wisdom')
    if expected != value['snapshot_sha256']:
        _fail('parchment_wisdom_changed')
    return value


def build_snapshot(wisdoms, *, parchment_id, title, actor, created_at, implementation_sha256):
    """A new request gets a new P. Existing W text and evidence stay unchanged."""
    _uuid(parchment_id, 'invalid_parchment_id')
    _text(title, code='invalid_parchment_title')
    _text(actor, code='invalid_parchment_actor')
    if not isinstance(wisdoms, list) or not wisdoms:
        _fail('parchment_wisdom_required')
    try:
        stamp = datetime.fromisoformat(created_at)
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError
    except (TypeError, ValueError):
        _fail('invalid_parchment_created_at')
    if not isinstance(implementation_sha256, dict) or not implementation_sha256:
        _fail('invalid_parchment_profile')
    for name, signature in implementation_sha256.items():
        _text(name, code='invalid_parchment_profile')
        data_id(signature)
    sections, citations, identifiers = [], [], []
    for value in wisdoms:
        check_wisdom(value)
        if value['wisdom_id'] in identifiers:
            _fail('duplicate_parchment_wisdom')
        identifiers.append(value['wisdom_id'])
        section = {name: deepcopy(value[name]) for name in SECTION_FIELDS}
        section['wisdom_snapshot_sha256'] = value['snapshot_sha256']
        sections.append(section)
        citations.append({'section_index': len(sections) - 1, 'wisdom_id': value['wisdom_id'],
            'wisdom_snapshot_sha256': value['snapshot_sha256'], 'claims': deepcopy(value['citations'])})
    value = {'schema_version': SCHEMA, 'parchment_id': parchment_id, 'title': title,
        'body': {'sections': sections}, 'input_wisdom_ids': identifiers,
        'direct_k_revision_ids': [], 'direct_information_ids': [], 'citations': citations,
        'provenance': {'operation': 'w2p', 'actor': actor, 'profile': {
            'schema_version': PROFILE, 'implementation_sha256': deepcopy(implementation_sha256)}},
        'supersedes_parchment_id': None, 'created_at': created_at}
    value['snapshot_sha256'] = digest(value)
    return value


def check_snapshot(value):
    if not isinstance(value, dict) or value.get('schema_version') != SCHEMA:
        _fail('invalid_parchment_snapshot')
    try:
        expected = digest({key: item for key, item in value.items() if key != 'snapshot_sha256'})
    except (TypeError, ValueError, UnicodeError):
        _fail('invalid_parchment_snapshot')
    if value.get('snapshot_sha256') != expected:
        _fail('parchment_snapshot_changed')
    return value
