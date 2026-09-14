"""Versioned source collections, separate from canonical D/I/K and permissions.

The application router verifies trusted stores and actual source/version ownership.
This module validates metadata, retains immutable membership and freezes I2K scope.
It does not open source stores, copy evidence, or authorize provider delivery.
"""

from contextlib import contextmanager
from hashlib import sha256
import json

from .data import data_id, request_id as uuid7
from .errors import PalimpsestError


PROFILE = 'realm-catalog-v1'
SCOPE_PROFILE = 'realm-i2k-scope-v1'
SCOPE_POLICY = 'single-realm-explicit-cross-v1'


def _fail(code, message, *, details=None, status=2):
    raise PalimpsestError(code, message, status, details)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _digest(value):
    return sha256(_json(value).encode('utf-8')).hexdigest()


def _text(value, field, *, empty=False):
    if not isinstance(value, str) or '\x00' in value or (not empty and not value.strip()):
        _fail('invalid_realm_metadata', f'Realm {field} 값을 확인하세요.')
    try:
        value.encode('utf-8')
    except UnicodeError:
        _fail('invalid_realm_metadata', f'Realm {field}의 문자 인코딩을 확인하세요.')
    return value


def normalize_members(members):
    if not isinstance(members, list):
        _fail('invalid_realm_members', 'Realm 구성 자료는 목록이어야 합니다.')
    result, seen = [], set()
    for member in members:
        if not isinstance(member, dict) or set(member) != {'store_id', 'member_kind', 'member_id'}:
            _fail('invalid_realm_member', 'Realm 구성 자료의 저장소·종류·ID를 확인하세요.')
        store = uuid7(member['store_id'])
        kind = member['member_kind']
        if kind not in ('data', 'data_series'):
            _fail('invalid_realm_member', 'Realm은 등록된 Data 또는 Data series를 참조합니다.')
        identifier = data_id(member['member_id']) if kind == 'data' else uuid7(member['member_id'])
        key = (store, kind, identifier)
        if key in seen:
            _fail('duplicate_realm_member', '같은 Realm revision에 같은 자료를 중복 등록할 수 없습니다.')
        seen.add(key)
        result.append(dict(zip(('store_id', 'member_kind', 'member_id'), key)))
    return sorted(result, key=lambda item: (item['store_id'], item['member_kind'], item['member_id']))


def normalize_sources(sources):
    if not isinstance(sources, list) or not sources:
        _fail('realm_sources_required', 'I2K 범위를 고정할 실제 source 목록이 필요합니다.')
    result, data_seen, execution_seen = [], set(), set()
    required = {'store_id', 'data_id', 'source_execution_id'}
    for source in sources:
        if (not isinstance(source, dict) or not required <= set(source)
                or set(source) - required - {'version_id', 'series_id'}):
            _fail('invalid_realm_source', 'Realm source의 저장소·Data·완료 source execution을 확인하세요.')
        value = {'store_id': uuid7(source['store_id']), 'data_id': data_id(source['data_id']),
                 'source_execution_id': uuid7(source['source_execution_id'])}
        for field in ('version_id', 'series_id'):
            value[field] = uuid7(source[field]) if source.get(field) is not None else None
        if (value['version_id'] is None) != (value['series_id'] is None):
            _fail('invalid_realm_source_version', 'Data version과 소속 series를 함께 고정해야 합니다.')
        data_key = (value['store_id'], value['data_id'])
        execution_key = (value['store_id'], value['source_execution_id'])
        if data_key in data_seen or execution_key in execution_seen:
            _fail('duplicate_realm_source', '한 Data의 source execution을 중복하거나 섞을 수 없습니다.')
        data_seen.add(data_key)
        execution_seen.add(execution_key)
        result.append(value)
    return result


def freeze_scope(revisions, sources, *, explicit_cross=False, actor='local'):
    """Freeze verified revision snapshots; old snapshots remain replayable.

    A series membership is resolved to the actual version/Data supplied by the
    router. It is not a claim that a Realm revision pins a dynamic series head.
    """
    actor = _text(actor, 'actor')
    if type(explicit_cross) is not bool:
        _fail('invalid_realm_cross_selection', 'Realm 교차 선택은 실제 사용자 선택이어야 합니다.')
    if not isinstance(revisions, list) or not revisions:
        _fail('realm_required', 'I2K에는 선택한 Realm이 필요합니다.')
    selected, members, seen = [], [], set()
    for revision in revisions:
        if not isinstance(revision, dict):
            _fail('invalid_realm_revision', '정확한 Realm revision이 필요합니다.')
        realm = uuid7(revision.get('realm_id'))
        identifier = uuid7(revision.get('revision_id'))
        if realm in seen:
            _fail('duplicate_realm_selection', '동일 Realm의 여러 revision을 한 범위에 섞을 수 없습니다.')
        seen.add(realm)
        selected.append({'realm_id': realm, 'revision_id': identifier})
        members.extend(normalize_members(revision.get('members')))
    if len(selected) > 1 and not explicit_cross:
        _fail('realm_crossing_requires_explicit_selection', '여러 Realm의 I2K 결합은 명시적인 교차 선택이 필요합니다.')
    sources = normalize_sources(sources)
    if len({source['store_id'] for source in sources}) != 1:
        _fail('realm_cross_store_i2k_unsupported', '여러 저장소의 자료는 함께 조회할 수 있지만 I2K 저장은 아직 단일 저장소만 지원합니다.')
    membership = {(member['store_id'], member['member_kind'], member['member_id']) for member in members}
    for source in sources:
        if ((source['store_id'], 'data', source['data_id']) not in membership
                and (source['series_id'] is None or (source['store_id'], 'data_series', source['series_id']) not in membership)):
            _fail('realm_source_outside_scope', '선택한 Realm revision에 속하지 않는 source입니다.',
                  details={'store_id': source['store_id'], 'data_id': source['data_id']})
    scope = {'schema_version': SCOPE_PROFILE, 'policy': SCOPE_POLICY,
             'realm_revisions': sorted(selected, key=lambda item: item['realm_id']),
             'sources': sources, 'explicit_cross': explicit_cross, 'actor': actor}
    return {**scope, 'scope_sha256': _digest(scope)}


class RealmCatalog:
    def __init__(self, dsn):
        self.dsn = dsn

    @contextmanager
    def _connection(self):
        # Lazy storage import keeps pure scope validation usable without psycopg.
        from .canonical_store import connection
        with connection(self.dsn) as conn:
            if conn.execute("SELECT to_regprocedure('realm_store.schema_version()') AS name").fetchone()['name'] is None:
                _fail('realm_catalog_not_initialized', '명시적으로 준비한 Realm catalog가 필요합니다.', status=3)
            if conn.execute('SELECT realm_store.schema_version() AS version').fetchone()['version'] != PROFILE:
                _fail('realm_catalog_version_mismatch', 'Realm catalog schema 버전을 확인하세요.', status=3)
            yield conn

    @staticmethod
    def _revision(conn, identifier):
        row = conn.execute('SELECT * FROM realm_store.realm_revisions WHERE revision_id=%s', (identifier,)).fetchone()
        if row is None:
            _fail('realm_revision_not_found', 'Realm revision을 찾을 수 없습니다.', status=4)
        result = json.loads(json.dumps(row, default=str, ensure_ascii=False))
        result['members'] = json.loads(json.dumps(conn.execute('''SELECT store_id,member_kind,member_id
            FROM realm_store.realm_members WHERE revision_id=%s ORDER BY store_id,member_kind,member_id''',
            (identifier,)).fetchall(), default=str, ensure_ascii=False))
        return result

    def create(self, name, description, actor, reason, request_id):
        return self._write(None, None, name, description, [], actor, reason, request_id)

    def revise(self, realm_id, expected_revision_id, name, description, members, actor, reason, request_id):
        return self._write(uuid7(realm_id), uuid7(expected_revision_id), name, description,
                           normalize_members(members), actor, reason, request_id)

    def _write(self, realm_id, expected, name, description, members, actor, reason, identifier):
        identifier = uuid7(identifier)
        payload = {'schema_version': PROFILE, 'operation': 'create' if realm_id is None else 'revise',
                   'realm_id': realm_id, 'expected_revision_id': expected, 'name': _text(name, 'name'),
                   'description': _text(description, 'description', empty=True), 'members': members,
                   'actor': _text(actor, 'actor'), 'reason': _text(reason, 'reason')}
        encoded, fingerprint = _json(payload), _digest(payload)
        with self._connection() as conn, conn.transaction():
            # Request replay is serialized before the Realm's expected-head lock.
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (identifier,))
            previous = conn.execute('SELECT * FROM realm_store.requests WHERE request_id=%s', (identifier,)).fetchone()
            if previous:
                if previous['request_fingerprint'] != fingerprint:
                    _fail('realm_request_conflict', '같은 요청 ID에 다른 Realm 변경을 재사용할 수 없습니다.', status=6)
                return {**self._revision(conn, previous['result_revision_id']), 'replayed': True}
            if realm_id is None:
                realm_id = str(conn.execute('SELECT uuidv7() AS id').fetchone()['id'])
                number = 1
            else:
                head = conn.execute('SELECT current_revision_id FROM realm_store.realms WHERE realm_id=%s FOR UPDATE',
                                    (realm_id,)).fetchone()
                if head is None:
                    _fail('realm_not_found', 'Realm을 찾을 수 없습니다.', status=4)
                if str(head['current_revision_id']) != expected:
                    _fail('realm_revision_changed', 'Realm이 이미 변경되었습니다. 현재 revision을 확인한 뒤 다시 선택하세요.',
                          details={'realm_id': realm_id, 'current_revision_id': str(head['current_revision_id'])}, status=6)
                number = self._revision(conn, expected)['revision_no'] + 1
            revision_id = str(conn.execute('SELECT uuidv7() AS id').fetchone()['id'])
            conn.execute('''INSERT INTO realm_store.requests
                (request_id,request_fingerprint,operation,request_json,realm_id,expected_revision_id,result_revision_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s)''',
                (identifier, fingerprint, payload['operation'], encoded, realm_id, expected, revision_id))
            if expected is None:
                conn.execute('INSERT INTO realm_store.realms(realm_id,current_revision_id) VALUES (%s,%s)', (realm_id, revision_id))
            conn.execute('''INSERT INTO realm_store.realm_revisions
                (revision_id,realm_id,parent_revision_id,revision_no,name,description,actor,reason,request_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (revision_id, realm_id, expected, number, name, description, actor, reason, identifier))
            for member in members:
                conn.execute('''INSERT INTO realm_store.realm_members(revision_id,store_id,member_kind,member_id)
                    VALUES (%s,%s,%s,%s)''', (revision_id, member['store_id'], member['member_kind'], member['member_id']))
            if expected is not None:
                conn.execute('UPDATE realm_store.realms SET current_revision_id=%s WHERE realm_id=%s', (revision_id, realm_id))
            return {**self._revision(conn, revision_id), 'replayed': False}

    def catalog(self):
        with self._connection() as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            rows = conn.execute('SELECT current_revision_id FROM realm_store.realms ORDER BY realm_id').fetchall()
            return {'schema_version': PROFILE, 'realms': [self._revision(conn, row['current_revision_id']) for row in rows]}

    def revision(self, revision_id):
        with self._connection() as conn:
            return self._revision(conn, uuid7(revision_id))

    def current(self, realm_id):
        with self._connection() as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            row = conn.execute('SELECT current_revision_id FROM realm_store.realms WHERE realm_id=%s',
                               (uuid7(realm_id),)).fetchone()
            if row is None:
                _fail('realm_not_found', 'Realm을 찾을 수 없습니다.', status=4)
            return self._revision(conn, row['current_revision_id'])

    def request_result(self, request_id):
        """Read a committed metadata request after a lost response; no head rewrite."""
        with self._connection() as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            row = conn.execute('SELECT request_json,result_revision_id FROM realm_store.requests WHERE request_id=%s',
                               (uuid7(request_id),)).fetchone()
            return ({'request': json.loads(row['request_json']), 'revision': self._revision(conn, row['result_revision_id'])}
                    if row else None)

    def history(self, realm_id):
        realm_id = uuid7(realm_id)
        with self._connection() as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            row = conn.execute('SELECT current_revision_id FROM realm_store.realms WHERE realm_id=%s', (realm_id,)).fetchone()
            if row is None:
                _fail('realm_not_found', 'Realm을 찾을 수 없습니다.', status=4)
            revisions = conn.execute('SELECT revision_id FROM realm_store.realm_revisions WHERE realm_id=%s ORDER BY revision_no',
                                     (realm_id,)).fetchall()
            return {'realm_id': realm_id, 'current_revision_id': str(row['current_revision_id']),
                    'revisions': [self._revision(conn, item['revision_id']) for item in revisions]}

    def build_scope(self, realm_ids, sources, explicit_cross=False, actor='local'):
        if not isinstance(realm_ids, list) or not realm_ids:
            _fail('realm_required', 'I2K에는 선택한 Realm이 필요합니다.')
        identifiers = [uuid7(value) for value in realm_ids]
        if len(set(identifiers)) != len(identifiers):
            _fail('duplicate_realm_selection', '동일 Realm을 중복 선택할 수 없습니다.')
        if type(explicit_cross) is not bool:
            _fail('invalid_realm_cross_selection', 'Realm 교차 선택은 명시적인 값이어야 합니다.')
        if len(identifiers) > 1 and not explicit_cross:
            _fail('realm_crossing_requires_explicit_selection', '여러 Realm의 I2K 결합은 명시적인 교차 선택이 필요합니다.')
        sources = normalize_sources(sources)
        if len({source['store_id'] for source in sources}) != 1:
            _fail('realm_cross_store_i2k_unsupported', '여러 저장소의 I2K 저장은 아직 지원하지 않습니다.')
        with self._connection() as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            revisions = []
            for identifier in identifiers:
                row = conn.execute('SELECT current_revision_id FROM realm_store.realms WHERE realm_id=%s', (identifier,)).fetchone()
                if row is None:
                    _fail('realm_not_found', 'Realm을 찾을 수 없습니다.', status=4)
                revisions.append(self._revision(conn, row['current_revision_id']))
            return freeze_scope(revisions, sources, explicit_cross=explicit_cross, actor=actor)
