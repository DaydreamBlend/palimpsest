"""Paper claim proposals and exact I citations; no storage or model calls.

Fingerprints test structured equality. A Validator, not a fingerprint or a
source section label, decides whether different payloads mean the same thing.
"""

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
import re
import unicodedata

from .data import request_id
from .errors import PalimpsestError


PROFILE = 'paper-claims-v1'
KINDS = ('proposition', 'observation')
SOURCE_ROLES = ('abstract', 'results', 'methods', 'figure', 'discussion', 'other')
SEMANTIC_FIELDS = ('subject', 'relation', 'object', 'polarity', 'quantifier',
                   'scope', 'conditions', 'time_range')
KEY_PATTERN = r'^[A-Za-z][A-Za-z0-9_.-]{0,127}$'
REASON_PATTERN = r'^[a-z][a-z0-9_]{0,63}$'


def _object(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties),
            'additionalProperties': False}


def _array(items, *, nonempty=False):
    return {'type': 'array', 'items': items, **({'minItems': 1} if nonempty else {})}


def _enum(values, *, nullable=False):
    return {'type': ['string', 'null'] if nullable else 'string',
            'enum': list(values) + ([None] if nullable else [])}


def NODE_SCHEMA(input_information_ids, media_sha256s):
    text = {'type': 'string'}
    semantic = {key: text.copy() for key in SEMANTIC_FIELDS}
    semantic.update(polarity=_enum(('positive', 'negative')), conditions=_array(text))
    return _object({
        'nodes': _array(_object({
            'candidate_key': {'type': 'string', 'pattern': KEY_PATTERN},
            'kind': _enum(KINDS), 'statement': {'type': 'string', 'minLength': 1},
            'semantic_payload': _object(semantic),
            'evidence': _array(_object({
                'information_id': _enum(input_information_ids),
                'quote': {'type': 'string', 'minLength': 1},
                'media_sha256': _enum(media_sha256s, nullable=True),
                'source_role': _enum(SOURCE_ROLES),
            }), nonempty=True),
            'uncertainties': _array(text),
        })),
        'source_requests': _array(_object({
            'information_ids': _array(_enum(input_information_ids), nonempty=True),
            'question': {'type': 'string', 'minLength': 1},
            'page_numbers': _array({'type': 'integer', 'minimum': 1}),
        })),
        'complete': {'type': 'boolean'}, 'coverage_notes': _array(text),
    })


def NODE_DECISION_SCHEMA(candidate_keys, existing_revision_ids):
    return _object({'decisions': _array(_object({
        'candidate_key': _enum(candidate_keys),
        'verdict': _enum(('accepted', 'reused', 'rejected', 'needs_human')),
        'equivalent_candidate_key': _enum(candidate_keys, nullable=True),
        'equivalent_revision_id': _enum(existing_revision_ids, nullable=True),
        'reason_codes': _array({'type': 'string', 'pattern': REASON_PATTERN}, nonempty=True),
        'reason': {'type': 'string', 'minLength': 1},
    })), 'complete': {'type': 'boolean'}})


def _fail(code='invalid_knowledge_proposal'):
    raise PalimpsestError(code, '지식 제안의 구조·정확한 근거·Revision 참조를 확인하세요.', 4)


def _keys(value, keys, code='invalid_knowledge_proposal'):
    if not isinstance(value, dict) or set(value) != set(keys):
        _fail(code)


def _text(value, *, empty=False, code='invalid_knowledge_proposal'):
    if not isinstance(value, str) or '\x00' in value:
        _fail(code)
    try:
        value.encode('utf-8')
    except UnicodeEncodeError:
        _fail(code)
    result = unicodedata.normalize('NFC', value).strip()
    if not empty and not result:
        _fail(code)
    return result


def _strings(value, *, code='invalid_knowledge_proposal'):
    if not isinstance(value, list):
        _fail(code)
    return [_text(item, code=code) for item in value]


def _key(value, code='invalid_knowledge_proposal'):
    if not isinstance(value, str) or re.fullmatch(KEY_PATTERN, value) is None:
        _fail(code)
    return value


def _uuid(value, code='invalid_knowledge_proposal'):
    try:
        if not isinstance(value, str) or request_id(value) != value:
            _fail(code)
    except PalimpsestError:
        _fail(code)
    return value


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def normalize_semantic_payload(value):
    _keys(value, SEMANTIC_FIELDS)
    result = {key: _text(value[key], empty=key in ('scope', 'quantifier', 'time_range'))
              for key in SEMANTIC_FIELDS if key != 'conditions'}
    if result['polarity'] not in ('positive', 'negative'):
        _fail()
    result['conditions'] = sorted(set(_strings(value['conditions'])))
    return result


def node_fingerprints(kind, semantic_payload):
    if kind not in KINDS:
        _fail()
    payload = normalize_semantic_payload(semantic_payload)
    seed = {'profile': PROFILE, 'kind': kind, 'semantic_payload': payload}
    # This exact seed does not decide logical identity across material changes.
    return {'identity_fingerprint': _digest({'domain': 'knode-exact', **seed}),
            'content_fingerprint': _digest({'domain': 'knode-content', **seed})}


def validate_source_requests(requests, packet):
    """Check generator requests before Runtime binds/prepares original bytes."""
    if not isinstance(requests, list):
        _fail()
    ids = {item['information_id'] for item in packet['model_input']['information']}
    result = []
    for item in requests:
        _keys(item, ('information_ids', 'question', 'page_numbers'))
        refs = item['information_ids']
        pages = item['page_numbers']
        if (not isinstance(refs, list) or not refs or any(not isinstance(ref, str) for ref in refs)
                or len(refs) != len(set(refs)) or not set(refs) <= ids
                or not isinstance(pages, list)
                or any(type(page) is not int or not 1 <= page <= packet['page_count'] for page in pages)
                or len(pages) != len(set(pages))):
            _fail('invalid_knowledge_source_request')
        result.append({'information_ids': list(refs), 'question': _text(item['question']),
                       'page_numbers': list(pages)})
    return result


def source_block_ranges(unit):
    """Return unambiguous source-text spans already recorded in this I.

    Missing, ambiguous or non-text assembly metadata cannot authorize a block
    citation. All I content/media is still delivered; this is only an inventory
    of exact citation addresses, never a content-importance filter. Runtime must
    verify the frozen I and its assembly against canonical source provenance.
    """
    assembly = unit.get('source_assembly')
    segments = assembly.get('content_segments') if isinstance(assembly, dict) else None
    refs, content = unit.get('source_refs'), unit.get('content')
    if not isinstance(segments, list) or not isinstance(refs, list) or not isinstance(content, str):
        return {}
    segments = [item for item in segments if isinstance(item, dict) and isinstance(item.get('source_block_id'), str)]
    refs = [item for item in refs if isinstance(item, dict) and isinstance(item.get('block_id'), str)]
    segment_counts = Counter(item['source_block_id'] for item in segments)
    ref_counts = Counter(item['block_id'] for item in refs)
    owned = {item['block_id']: item for item in refs}
    result = {}
    for segment in segments:
        identifier = segment['source_block_id']
        ref = owned.get(identifier)
        start, end = segment.get('char_start'), segment.get('char_end')
        source_range = segment.get('source_char_range')
        if (not identifier or '\x00' in identifier or segment_counts[identifier] != 1
                or ref_counts[identifier] != 1 or ref is None
                or segment.get('text_origin') not in ('parser_source', 'registered_source')
                or identifier.startswith('/original_page_facsimile/')
                or ref.get('source_collection') == 'original_page_facsimile'
                or ref.get('facsimile_provenance') is not None or ref.get('derived_primary') is True
                or type(start) is not int or type(end) is not int or not 0 <= start < end <= len(content)
                or not isinstance(source_range, list) or len(source_range) != 2
                or any(type(offset) is not int for offset in source_range)
                or not 0 <= source_range[0] < source_range[1]
                or source_range[1] - source_range[0] != end - start
                or any(not isinstance(segment.get(key), str) or not segment[key]
                       or segment[key] != ref.get(key) for key in ('raw_locator', 'anchor_sha256'))
                or segment.get('page_index') != ref.get('page_index')
                or not content[start:end].strip() or '\x00' in content[start:end]):
            continue
        result[identifier] = (start, end)
    return result


def normalize_evidence(citation, units, *, allow_media_only=False, allow_block_refs=False):
    """Resolve an owned block or exact quote without changing source text."""
    code = 'invalid_knowledge_evidence'
    if allow_block_refs and isinstance(citation, dict) and 'source_block_id' in citation:
        _keys(citation, ('information_id', 'source_block_id', 'source_role'), code)
        identifier = _uuid(citation['information_id'], code)
        unit, block = units.get(identifier), citation['source_block_id']
        if unit is None or not isinstance(block, str) or citation['source_role'] not in SOURCE_ROLES:
            _fail(code)
        span = source_block_ranges(unit).get(block)
        if span is None:
            _fail('invalid_knowledge_block_reference')
        start, end = span
        # The address disambiguates identical text in different blocks. Never
        # search for this quote again or normalize its Unicode/spacing.
        return {**deepcopy(citation), 'quote': unit['content'][start:end], 'media_sha256': None,
                'char_start': start, 'char_end': end}
    _keys(citation, ('information_id', 'quote', 'media_sha256', 'source_role'), code)
    identifier = _uuid(citation['information_id'], code)
    unit = units.get(identifier)
    quote, media = citation['quote'], citation['media_sha256']
    media_only = allow_media_only and quote == '' and media is not None
    if (unit is None or not isinstance(quote, str) or (not quote.strip() and not media_only)
            or '\x00' in quote or citation['source_role'] not in SOURCE_ROLES
            or (media is not None and (not isinstance(media, str)
                or media not in {image['sha256'] for image in unit['media']}))):
        _fail(code)
    # Do not normalize a quote: even Unicode normalization alters its locus.
    start = 0 if media_only else unit['content'].find(quote)
    if start < 0 or (not media_only and unit['content'].find(quote, start + 1) >= 0):
        _fail('ambiguous_knowledge_quote' if start >= 0 else 'knowledge_quote_mismatch')
    return {**deepcopy(citation), 'char_start': start, 'char_end': start + len(quote)}


def normalize_nodes(response, packet, *, allow_media_only=False, allow_block_refs=False):
    """Bind citations to exact delivered I, with optional owned block addresses.

    ``complete`` describes the model's claim, not independently verified
    coverage. The caller must retain and evaluate it, including unresolved
    source requests; returning proposals is not accepting Knowledge.
    """
    _keys(response, ('nodes', 'source_requests', 'complete', 'coverage_notes'))
    if type(response['complete']) is not bool or not isinstance(response['nodes'], list):
        _fail()
    _strings(response['coverage_notes'])
    if validate_source_requests(response['source_requests'], packet) and response['complete']:
        _fail('unresolved_knowledge_source_request')
    units = {item['information_id']: item for item in packet['model_input']['information']}
    seen, result = set(), []
    for proposal in response['nodes']:
        _keys(proposal, ('candidate_key', 'kind', 'statement', 'semantic_payload', 'evidence', 'uncertainties'))
        key = _key(proposal['candidate_key'])
        if key in seen or proposal['kind'] not in KINDS:
            _fail()
        seen.add(key)
        semantic = normalize_semantic_payload(proposal['semantic_payload'])
        if not isinstance(proposal['evidence'], list) or not proposal['evidence']:
            _fail('invalid_knowledge_evidence')
        evidence, evidence_seen = [], set()
        for citation in proposal['evidence']:
            normalized = normalize_evidence(citation, units, allow_media_only=allow_media_only,
                                            allow_block_refs=allow_block_refs)
            marker = tuple(normalized[key] for key in
                           ('information_id', 'char_start', 'char_end', 'media_sha256', 'source_role'))
            if marker in evidence_seen:
                _fail('duplicate_knowledge_evidence')
            evidence_seen.add(marker)
            evidence.append(normalized)
        result.append({'candidate_key': key, 'kind': proposal['kind'],
                       'statement': _text(proposal['statement']), 'semantic_payload': semantic,
                       'evidence': evidence, 'uncertainties': _strings(proposal['uncertainties']),
                       **node_fingerprints(proposal['kind'], semantic)})
    return result


def _decision_reason(decision, code):
    reasons = _strings(decision['reason_codes'], code=code)
    if (not reasons or len(reasons) != len(set(reasons))
            or any(re.fullmatch(REASON_PATTERN, value) is None for value in reasons)):
        _fail(code)
    return {'reason_codes': reasons, 'reason': _text(decision['reason'], code=code)}


def validate_node_decisions(value, candidates, existing_ids):
    """Require complete decisions; resolve batch reuse without self/cycle reuse.

    The returned mapping places accepted roots before their reused dependents.
    This is ordering for identity reuse, not a DAG constraint on Knowledge.
    """
    code = 'invalid_knowledge_decision'
    _keys(value, ('decisions', 'complete'), code)
    if value['complete'] is not True or not isinstance(value['decisions'], list):
        _fail(code)
    by_key = {candidate['candidate_key']: candidate for candidate in candidates}
    if len(by_key) != len(candidates):
        _fail(code)
    existing = {_uuid(str(identifier), code) for identifier in existing_ids}
    decisions = {}
    for item in value['decisions']:
        _keys(item, ('candidate_key', 'verdict', 'equivalent_candidate_key',
                     'equivalent_revision_id', 'reason_codes', 'reason'), code)
        key = _key(item['candidate_key'], code)
        if key not in by_key or key in decisions:
            _fail(code)
        verdict, target, revision = item['verdict'], item['equivalent_candidate_key'], item['equivalent_revision_id']
        if verdict not in ('accepted', 'reused', 'rejected', 'needs_human'):
            _fail(code)
        if verdict == 'reused':
            if (target is None) == (revision is None):
                _fail(code)
            if target is not None:
                _key(target, code)
                if target == key or target not in by_key or by_key[key]['kind'] != by_key[target]['kind']:
                    _fail(code)
            elif _uuid(revision, code) not in existing:
                _fail(code)
        elif target is not None or revision is not None:
            _fail(code)
        decisions[key] = {**deepcopy(item), **_decision_reason(item, code)}
    if set(decisions) != set(by_key):
        _fail(code)
    ordered = {}
    for key in decisions:
        trail, current = [], key
        while current not in ordered:
            if current in trail:
                _fail('knowledge_reuse_cycle')
            trail.append(current)
            decision = decisions[current]
            target = decision['equivalent_candidate_key']
            if target is None:
                break
            if decisions[target]['verdict'] not in ('accepted', 'reused'):
                _fail(code)
            current = target
        for item in reversed(trail):
            ordered[item] = decisions[item]
    return ordered
