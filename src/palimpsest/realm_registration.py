"""Recoverable Data registration followed by an exact Realm membership receipt.

The existing source import journal freezes the selection. Source bytes may be
committed before the separate Realm database is available; compilation waits
for its receipt. Low-level unscoped imports remain historical/fixture APIs.
"""

from copy import deepcopy

from .data import data_id, request_id
from .errors import PalimpsestError
from .realms import _text


PROFILE = 'realm-data-registration-v1'


def validate_registration(value):
    fields = {'schema_version', 'realm_id', 'initial_revision_id', 'store_id',
              'membership_request_id', 'actor', 'reason'}
    if not isinstance(value, dict) or set(value) != fields or value.get('schema_version') != PROFILE:
        raise PalimpsestError('invalid_realm_registration', '등록할 Realm의 정확한 선택 기록이 필요합니다.', 2)
    result = deepcopy(value)
    for key in ('realm_id', 'initial_revision_id', 'store_id', 'membership_request_id'):
        result[key] = request_id(value[key])
    for key in ('actor', 'reason'):
        result[key] = _text(value[key], key)
    return result


def registration(row):
    metadata = row.get('external_metadata') if row else None
    if not isinstance(metadata, dict) or 'realm_registration' not in metadata:
        return None
    return validate_registration(metadata['realm_registration'])


def _member(selection, owner):
    return {'store_id': selection['store_id'], 'member_kind': 'data', 'member_id': data_id(owner)}


def receipt(catalog, selection, owner):
    """Validate the original assignment, not its current classification/head."""
    selection = validate_registration(selection)
    result = catalog.request_result(selection['membership_request_id'])
    if result is None:
        return None
    request, revision = result['request'], result['revision']
    if (request.get('operation') != 'revise' or request.get('realm_id') != selection['realm_id']
            or request.get('actor') != selection['actor'] or request.get('reason') != selection['reason']
            or revision.get('realm_id') != selection['realm_id']
            or str(revision.get('request_id')) != selection['membership_request_id']
            or _member(selection, owner) not in revision.get('members', [])
            or _member(selection, owner) not in request.get('members', [])):
        raise PalimpsestError('realm_registration_receipt_mismatch', '등록 요청과 Realm 연결 기록이 일치하지 않습니다.', 6)
    return revision


class RealmRegistration:
    def __init__(self, service, catalog, store_id):
        self.service, self.catalog, self.store_id = service, catalog, request_id(store_id)

    def _selection(self, identifier, realm_id, reason):
        row = self.service.repository.get_request(identifier)
        self.service._authorize(row)
        previous = registration(row)
        if previous is not None:
            if (previous['realm_id'] != request_id(realm_id) or previous['store_id'] != self.store_id
                    or previous['actor'] != self.service.actor_ref or previous['reason'] != _text(reason, 'reason')):
                raise PalimpsestError('idempotency_conflict', '같은 등록 요청의 Realm 선택을 변경할 수 없습니다.', 6)
            return previous
        if row is not None:
            raise PalimpsestError('idempotency_conflict', '과거 등록 요청에 Realm 선택을 덧붙일 수 없습니다.', 6)
        current = self.catalog.current(request_id(realm_id))
        return validate_registration({'schema_version': PROFILE, 'realm_id': current['realm_id'],
            'initial_revision_id': current['revision_id'], 'store_id': self.store_id,
            'membership_request_id': self.service.repository.allocate_id(),
            'actor': self.service.actor_ref, 'reason': reason})

    def _import(self, method, path, *, realm_id, reason='자료 등록', request_id=None, **kwargs):
        if realm_id is None:
            raise PalimpsestError('realm_required', '자료를 등록하기 전에 Realm을 선택하세요.', 2)
        identifier = request_id or self.service.repository.allocate_id()
        result = getattr(self.service, method)(path, request_id=identifier,
            realm_registration=lambda: self._selection(identifier, realm_id, reason), **kwargs)
        # A concurrent replay uses the winning immutable source journal selection.
        return self._finish(result, registration(self.service.repository.get_request(identifier)))

    def import_file(self, path, **kwargs):
        return self._import('import_file', path, **kwargs)

    def import_code_snapshot(self, directory, **kwargs):
        return self._import('import_code_snapshot', directory, **kwargs)

    def _finish(self, result, selection):
        if selection is None or result['state'] != 'committed':
            return result
        if selection['store_id'] != self.store_id or selection['actor'] != self.service.actor_ref:
            raise PalimpsestError('realm_registration_scope_mismatch', '원래 등록한 저장소와 actor 설정이 필요합니다.', 6)
        try:
            bound = receipt(self.catalog, selection, result['data_id'])
            if bound is None:
                current = self.catalog.current(selection['realm_id'])
                member = _member(selection, result['data_id'])
                members = current['members'] if member in current['members'] else [*current['members'], member]
                self.catalog.revise(current['realm_id'], current['revision_id'], current['name'], current['description'],
                    members, selection['actor'], selection['reason'], selection['membership_request_id'])
                bound = receipt(self.catalog, selection, result['data_id'])
                if bound is None:
                    raise PalimpsestError('realm_registration_receipt_missing', 'Realm 연결 기록을 다시 확인해야 합니다.', 6)
        except PalimpsestError as error:
            if error.code in ('realm_revision_changed', 'realm_request_conflict'):
                # Another replay may have completed between our receipt read
                # and CAS. Its immutable receipt wins; unrelated edits do not.
                completed = receipt(self.catalog, selection, result['data_id'])
                if completed is not None:
                    return {**result, 'realm_id': selection['realm_id'],
                            'realm_revision_id': completed['revision_id'], 'realm_registration_state': 'completed'}
            raise PalimpsestError('realm_registration_pending',
                '원본은 보존되었지만 Realm 연결이 끝나지 않았습니다. 같은 등록 요청을 복구하세요.', 7,
                {'request_id': result['request_id'], 'data_id': result['data_id'],
                 'state': 'realm_pending', 'source_state': 'committed', 'cause': error.code}) from error
        return {**result, 'realm_id': selection['realm_id'], 'realm_revision_id': bound['revision_id'],
                'realm_registration_state': 'completed'}

    def recover(self, identifier):
        result = self.service.recover(identifier)
        return self._finish(result, registration(self.service.repository.get_request(identifier)))

    def request_status(self, identifier):
        result = self.service.request_status(identifier)
        selection = registration(self.service.repository.get_request(identifier))
        if selection is None:
            return result
        if selection['store_id'] != self.store_id:
            raise PalimpsestError('realm_registration_scope_mismatch', '원래 등록한 저장소 설정이 필요합니다.', 6)
        bound = receipt(self.catalog, selection, result['data_id']) if result['state'] == 'committed' else None
        return {**result, 'realm_id': selection['realm_id'], 'source_state': result['state'],
                'state': 'realm_pending' if result['state'] == 'committed' and bound is None else result['state'],
                'realm_registration_state': 'completed' if bound else 'pending',
                'realm_revision_id': bound['revision_id'] if bound else None}


def configured_service(service, source_dsn, *, database_name=None):
    from .realm_i2k import configured_guard
    guard = configured_guard(source_dsn, database_name=database_name)
    if guard is None:
        raise PalimpsestError('realm_configuration_required', '등록할 Realm catalog와 trusted store 설정이 필요합니다.', 3)
    return RealmRegistration(service, guard.catalog, guard.store_id)


def verify_ready(conn, data_ids, catalog=None, store_id=None):
    """Gate new compilation only for Data registered with this new policy.

    Caller may supply an already trusted catalog/store. Otherwise the source
    connection DSN and host configuration resolve it lazily. Historical Data
    have no marker, so no Realm connection is needed for their exact replay.
    """
    owners = sorted({data_id(owner) for owner in data_ids})
    if not owners:
        return
    rows = conn.execute('''SELECT data_id,external_metadata FROM canonical_store.data_acquisitions
        WHERE data_id=ANY(%s::text[]) AND external_metadata ? 'realm_registration' ''', (owners,)).fetchall()
    if not rows:
        return
    if catalog is None or store_id is None:
        from .realm_i2k import configured_guard
        guard = configured_guard(conn.info.dsn)
        if guard is None:
            raise PalimpsestError('realm_configuration_required', '등록 완료를 확인할 Realm catalog 설정이 필요합니다.', 3)
        catalog, store_id = guard.catalog, guard.store_id
    for row in rows:
        selection = registration(row)
        if selection['store_id'] != store_id:
            raise PalimpsestError('realm_registration_scope_mismatch', '원래 등록한 저장소 설정이 필요합니다.', 6)
        if receipt(catalog, selection, row['data_id']) is None:
            raise PalimpsestError('realm_registration_pending',
                'Realm 연결이 완료된 뒤 컴파일을 시작할 수 있습니다. 원래 등록 요청을 복구하세요.', 7,
                {'data_id': row['data_id'], 'realm_id': selection['realm_id']})
