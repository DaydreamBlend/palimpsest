"""Explicit append-only histories over already registered, immutable Data bytes."""

from hashlib import sha256
import json

from psycopg.types.json import Jsonb

from .canonical_store import connection
from .data import data_id as validate_data_id, request_id as validate_request_id
from .errors import PalimpsestError


def _json(value):
    return json.loads(json.dumps(value, default=str, ensure_ascii=False))


def _text(value, *, empty=False):
    if not isinstance(value, str) or '\x00' in value or (not empty and not value.strip()):
        raise PalimpsestError('invalid_data_version_metadata', '자료 이름·변경 설명·actor 값을 확인하세요.', 2)
    try:
        value.encode('utf-8')
    except UnicodeError:
        raise PalimpsestError('invalid_data_version_metadata', '자료 버전 metadata는 UTF-8 문자열이어야 합니다.', 2) from None
    return value


def _ready(conn):
    if conn.execute("SELECT to_regclass('canonical_store.data_versions') AS name").fetchone()['name'] is None:
        raise PalimpsestError('data_versions_schema_required', '자료 버전 schema가 설치된 저장소를 선택하세요.', 3)


def immutable_versions(conn, version_ids):
    """Read ordered immutable rows inside the caller's existing transaction.

    Current-head policy and head locking belong to that caller. No live head,
    display label, or other mutable field enters this returned snapshot.
    """
    if not isinstance(version_ids, (list, tuple)):
        raise PalimpsestError('invalid_data_version_refs', '자료 버전 ID 목록이 필요합니다.', 2)
    identifiers = [validate_request_id(value) for value in version_ids]
    if len(set(identifiers)) != len(identifiers):
        raise PalimpsestError('invalid_data_version_refs', '동일한 버전 ID가 중복됐습니다.', 2)
    if not identifiers:
        return []
    _ready(conn)
    rows = conn.execute('SELECT * FROM canonical_store.data_versions WHERE version_id=ANY(%s::uuid[])',
                        (identifiers,)).fetchall()
    by_id = {str(row['version_id']): _json(row) for row in rows}
    if set(by_id) != set(identifiers):
        raise PalimpsestError('data_version_not_found', '등록된 자료 버전을 찾을 수 없습니다.', 2)
    return [by_id[identifier] for identifier in identifiers]


class DataVersions:
    def __init__(self, dsn, store):
        self.dsn, self.store = dsn, store

    @staticmethod
    def _series(conn, series_id, *, lock=False):
        row = conn.execute('SELECT * FROM canonical_store.data_series WHERE series_id=%s'
                           + (' FOR UPDATE' if lock else ''), (series_id,)).fetchone()
        if row is None:
            raise PalimpsestError('data_series_not_found', '자료 이력을 찾을 수 없습니다.', 2)
        return _json(row)

    @staticmethod
    def _request(conn, identifier, payload, actor_ref):
        # A request lock precedes a head lock, including requests that race on creation.
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (identifier,))
        row = conn.execute('SELECT * FROM compiler_runtime.data_version_requests WHERE request_id=%s',
                           (identifier,)).fetchone()
        fingerprint = sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()
        if row is not None:
            if row['actor_ref'] != actor_ref:
                raise PalimpsestError('permission_denied', '다른 actor의 자료 버전 요청은 재사용할 수 없습니다.', 5)
            if row['request_fingerprint'] != fingerprint or row['request_payload'] != payload:
                raise PalimpsestError('idempotency_conflict', '같은 요청 ID에 다른 버전 갱신 입력이 있습니다.', 6)
            return fingerprint, {**row['result'], 'replayed': True}
        return fingerprint, None

    @staticmethod
    def _save_request(conn, identifier, fingerprint, payload, result):
        conn.execute('''INSERT INTO compiler_runtime.data_version_requests
            (request_id,request_fingerprint,operation,series_id,expected_head,data_id,actor_ref,
             result_version_id,outcome,request_payload,result)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (identifier, fingerprint, payload['operation'], result['series_id'], payload.get('expected_head'),
             payload.get('data_id'), payload['actor_ref'], result.get('version_id'), result['outcome'],
             Jsonb(payload), Jsonb(result)))

    def create(self, name, request_id=None, *, actor_ref='local'):
        name, actor_ref = _text(name), _text(actor_ref)
        with connection(self.dsn) as conn, conn.transaction():
            _ready(conn)
            identifier = (validate_request_id(request_id) if request_id is not None
                          else str(conn.execute('SELECT uuidv7() AS id').fetchone()['id']))
            payload = {'operation': 'create', 'name': name, 'actor_ref': actor_ref}
            fingerprint, replay = self._request(conn, identifier, payload, actor_ref)
            if replay is not None:
                return replay
            row = conn.execute('INSERT INTO canonical_store.data_series(name,actor_ref) VALUES (%s,%s) RETURNING *',
                               (name, actor_ref)).fetchone()
            result = {**_json(row), 'request_id': identifier, 'outcome': 'created', 'replayed': False}
            self._save_request(conn, identifier, fingerprint, payload, result)
        return result

    def append(self, series_id, data_id, request_id, expected_head, *, message='', actor_ref='local', title=''):
        series_id, identifier = validate_request_id(series_id), validate_request_id(request_id)
        data_id = validate_data_id(data_id)
        expected_head = validate_request_id(expected_head) if expected_head is not None else None
        actor_ref, title, message = _text(actor_ref), _text(title, empty=True), _text(message, empty=True)
        payload = {'operation': 'append', 'series_id': series_id, 'data_id': data_id,
                   'expected_head': expected_head, 'title': title, 'message': message, 'actor_ref': actor_ref}
        with connection(self.dsn) as conn, conn.transaction():
            _ready(conn)
            fingerprint, replay = self._request(conn, identifier, payload, actor_ref)
            if replay is not None:
                return replay
            series = self._series(conn, series_id, lock=True)
            if series['actor_ref'] != actor_ref:
                raise PalimpsestError('permission_denied', '다른 actor의 자료 이력은 갱신할 수 없습니다.', 5)
            if series['head_version_id'] != expected_head:
                raise PalimpsestError('data_version_head_changed', '자료의 현재 버전이 변경됐습니다.', 6,
                                      {'series_id': series_id, 'expected_head': expected_head,
                                       'current_head': series['head_version_id']})
            registered = conn.execute('SELECT * FROM canonical_store.data WHERE data_id=%s', (data_id,)).fetchone()
            if registered is None:
                raise PalimpsestError('data_not_found', '먼저 정확한 원본을 Data로 등록하세요.', 2)
            self.store.verify(data_id, registered['byte_size'])
            previous = immutable_versions(conn, [expected_head])[0] if expected_head else None
            if previous is not None and previous['data_id'] == data_id:
                version, outcome = previous, 'no_op'
            else:
                version = _json(conn.execute('''INSERT INTO canonical_store.data_versions
                    (series_id,parent_version_id,data_id,version_number,title,message,actor_ref)
                    VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                    (series_id, expected_head, data_id, previous['version_number'] + 1 if previous else 1,
                     title, message, actor_ref)).fetchone())
                conn.execute('UPDATE canonical_store.data_series SET head_version_id=%s WHERE series_id=%s',
                             (version['version_id'], series_id))
                outcome = 'created'
            result = {**version, 'request_id': identifier, 'outcome': outcome, 'replayed': False}
            self._save_request(conn, identifier, fingerprint, payload, result)
        return result

    def show(self, series_id):
        series_id = validate_request_id(series_id)
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            _ready(conn)
            series = self._series(conn, series_id)
            head = immutable_versions(conn, [series['head_version_id']])[0] if series['head_version_id'] else None
        return {**series, 'head': head}

    def version(self, version_id):
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SET TRANSACTION READ ONLY')
            return immutable_versions(conn, [version_id])[0]

    def history(self, series_id):
        series_id = validate_request_id(series_id)
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            _ready(conn)
            series = self._series(conn, series_id)
            rows = conn.execute('SELECT * FROM canonical_store.data_versions WHERE series_id=%s ORDER BY version_number DESC',
                                (series_id,)).fetchall()
        return {'series': series, 'versions': _json(rows)}
