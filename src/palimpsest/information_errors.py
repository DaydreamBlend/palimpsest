"""Report I2K Information errors from frozen I and retained model decisions.

The historical ``source_requests`` wire field is an error report under this
policy, not permission to fetch D, rerun D2I, or compile directly from D.
No source bytes, database, parser, storage, or provider are accessed here.
"""

from copy import deepcopy

from .data import data_id, request_id
from .errors import PalimpsestError


POLICY = 'i2k-information-required-v1'
REASON_CODES = ('d2i_information_error', 'd2i_missing_information', 'd2i_transcription_error',
                'd2i_missing_media', 'd2i_provenance_error')
RULES = '''
INFORMATION-REQUIRED POLICY: i2k-information-required-v1.
Every Knowledge candidate must be supported by actual supplied Information (I)
and its exact retained text or owned media. Do not compile Knowledge directly
from original Data (D), invent an I citation, or use inspected I as a substitute
for evidence it does not contain. No D2K or direct-D grounding is permitted.
If necessary source content is missing, mistranscribed, lacks required media,
or has broken provenance in I, report a D2I Information error for user review.
Use the existing source_requests field only as the compatibility error-report
wire: identify the actual affected I and Data and explain the concrete issue in
question. This is not a request to fetch D or to repair or rerun D2I. Do not
reparse, regroup, create new I, rewrite old I, or silently fall back to original D.
Validator: mark affected I needs_review with an applicable reason code from
d2i_information_error, d2i_missing_information, d2i_transcription_error,
d2i_missing_media, d2i_provenance_error; mark affected candidates needs_human.
Keep the run incomplete while required Information errors remain unresolved.
A missing or insufficiently selected K item alone is a Knowledge-selection gap,
not evidence of a D2I error: missing_material_content and ordinary selection
review misses must not be relabeled as missing Information. A reported error
remains verification_pending, not a confirmed semantic omission or a repaired
source. Preserve the exact source and raw Generator/Validator decisions.
'''


def _fail(code='invalid_information_error_report'):
    raise PalimpsestError(code, '보존된 Information 오류 보고와 정확한 원문 실행 범위를 확인하세요.', 4)


def _uuid(value):
    if not isinstance(value, str) or request_id(value) != value:
        _fail()
    return value


def _text(value):
    if not isinstance(value, str) or not value.strip() or '\x00' in value:
        _fail()
    try:
        value.encode('utf-8')
    except UnicodeEncodeError:
        _fail()
    return value


def _ids(values):
    if not isinstance(values, list) or not values:
        _fail()
    identifiers = [_uuid(value) for value in values]
    if len(identifiers) != len(set(identifiers)):
        _fail()
    return identifiers


def _payload(value):
    if not isinstance(value, dict):
        _fail()
    payload = value.get('payload', value)
    if not isinstance(payload, dict):
        _fail()
    return payload


def _review(value):
    if (not isinstance(value, dict) or value.get('verdict') not in ('confirmed', 'needs_review')
            or not isinstance(value.get('reason_codes'), list)):
        _fail()
    identifier = _uuid(value.get('information_id'))
    codes = [_text(code) for code in value['reason_codes']]
    return identifier, [code for code in codes if code in REASON_CODES]


def affected_information_ids(source_requests, information_reviews):
    """Return I requiring a hold, without inventing source ownership or repairs.

Requests may be persisted rows or the raw Generator receipt payloads used at
commit time. Even a contradictory confirmed verdict with a D2I error code is
blocking; the original verdict is never rewritten by this helper.
"""
    if not isinstance(source_requests, list) or not isinstance(information_reviews, list):
        _fail()
    affected = set()
    for value in source_requests:
        affected.update(_ids(_payload(value).get('information_ids')))
    for review in information_reviews:
        identifier, codes = _review(review)
        if codes:
            affected.add(identifier)
    return affected


def _source_information(job):
    if (not isinstance(job, dict) or job.get('operation') != 'i2k'
            or not isinstance(job.get('input_snapshot'), dict)):
        _fail()
    packet = job['input_snapshot'].get('input')
    if not isinstance(packet, dict):
        _fail()
    sources = packet.get('sources', [packet])
    if not isinstance(sources, list) or not sources:
        _fail()
    result = {}
    for source in sources:
        if not isinstance(source, dict):
            _fail()
        owner = data_id(source.get('data_id'))
        execution = _uuid(source.get('source_execution_id'))
        profile = _uuid(source.get('profile_id'))
        input_sha = data_id(source.get('input_sha256'))
        units = source.get('model_input', {}).get('information') if isinstance(source.get('model_input'), dict) else None
        if not isinstance(units, list) or not units:
            _fail()
        for unit in units:
            if not isinstance(unit, dict):
                _fail()
            identifier = _uuid(unit.get('information_id'))
            if (identifier in result or unit.get('data_id', owner) != owner
                    or unit.get('source_execution_id', execution) != execution
                    or not isinstance(unit.get('source_refs'), list)
                    or any(not isinstance(ref, dict) or ref.get('data_id', owner) != owner
                           or ref.get('source_execution_id', execution) != execution for ref in unit['source_refs'])):
                _fail('information_error_scope_mismatch')
            result[identifier] = {'data_id': owner, 'source_execution_id': execution,
                'source_profile_id': profile, 'source_input_sha256': input_sha,
                'source_refs': deepcopy(unit['source_refs'])}
    units = packet.get('model_input', {}).get('information') if isinstance(packet.get('model_input'), dict) else None
    if not isinstance(units, list):
        _fail()
    visible = []
    for unit in units:
        if not isinstance(unit, dict):
            _fail()
        identifier = _uuid(unit.get('information_id'))
        owner = result.get(identifier)
        if (owner is None or identifier in visible or unit.get('data_id', owner['data_id']) != owner['data_id']
                or unit.get('source_execution_id', owner['source_execution_id']) != owner['source_execution_id']
                or unit.get('source_refs') != owner['source_refs']):
            _fail('information_error_scope_mismatch')
        visible.append(identifier)
    if set(visible) != set(result):
        _fail('information_error_scope_mismatch')
    return result


def _scope(identifiers, declared, information):
    if any(identifier not in information for identifier in identifiers):
        _fail('information_error_scope_mismatch')
    first = information[identifiers[0]]
    fields = ('data_id', 'source_execution_id', 'source_profile_id', 'source_input_sha256')
    if (any(any(information[identifier][field] != first[field] for field in fields) for identifier in identifiers)
            or declared.get('data_id', first['data_id']) != first['data_id']
            or declared.get('source_execution_id', first['source_execution_id']) != first['source_execution_id']):
        _fail('information_error_scope_mismatch')
    return {field: first[field] for field in fields} | {
        'information_ids': list(identifiers),
        'source_refs': [{'information_id': identifier, 'source_refs': deepcopy(information[identifier]['source_refs'])}
                        for identifier in identifiers]}


def report(job):
    """Project reported I errors; neither verify an omission nor repair source."""
    information = _source_information(job)
    execution_id = _uuid(job.get('execution_id'))
    requests, reviews = job.get('source_requests', []), job.get('information_review_decisions', [])
    if not isinstance(requests, list) or not isinstance(reviews, list):
        _fail()
    errors = []
    for value in requests:
        payload = _payload(value)
        identifier = _uuid(value.get('request_id'))
        if value.get('execution_id', execution_id) != execution_id:
            _fail('information_error_scope_mismatch')
        scope = _scope(_ids(payload.get('information_ids')), payload, information)
        errors.append({'reported_by': 'generator', 'source_request_id': identifier, **scope,
            'reason_codes': ['d2i_information_error'], 'reason': _text(payload.get('question')),
            'status': 'reported_error', 'verification_status': 'verification_pending'})
    for review in reviews:
        identifier, codes = _review(review)
        if review.get('execution_id', execution_id) != execution_id:
            _fail('information_error_scope_mismatch')
        scope = _scope([identifier], review, information)
        if not codes:
            continue
        errors.append({'reported_by': 'validator', 'source_request_id': None, **scope,
            'reason_codes': codes, 'reason': _text(review.get('reason')),
            'status': 'reported_error', 'verification_status': 'verification_pending',
            'review_verdict': review['verdict'], 'contradictory_verdict': review['verdict'] == 'confirmed'})
    return {'schema_version': 'i2k-information-errors-v1', 'execution_id': execution_id,
        'requires_user_review': bool(errors), 'errors': errors, 'd2i_calls': 0,
        'direct_source_compilation_allowed': False}
