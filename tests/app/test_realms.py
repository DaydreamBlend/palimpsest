"""Realm metadata and scope contracts; no source/LLM access.

The optional PostgreSQL tests require a separately provisioned disposable catalog.
They never migrate, delete, or connect to the user's existing source databases.
"""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import os
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.realms import RealmCatalog, PROFILE, _digest, _json, freeze_scope, normalize_members, normalize_sources


def identifier(number):
    return f'019af000-0000-7000-8000-{number:012x}'


STORE, OTHER_STORE, SERIES = (identifier(value) for value in (1, 2, 3))
D1, D2 = 'a'*64, 'b'*64


def member(data=D1, store=STORE, kind='data'):
    return {'store_id': store, 'member_kind': kind, 'member_id': data}


def source(data=D1, store=STORE, execution=4, series=None, version=None):
    return {'store_id': store, 'data_id': data, 'source_execution_id': identifier(execution),
            'series_id': series, 'version_id': version}


def revision(number, members):
    return {'realm_id': identifier(number), 'revision_id': identifier(number+100), 'members': members}


class RealmScopeTests(unittest.TestCase):
    def reject(self, code, callback):
        with self.assertRaises(PalimpsestError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_default_separation_and_explicit_cross_preserve_source_order(self):
        realms = [revision(10, [member()]), revision(20, [member(D2)])]
        sources = [source(D2, execution=5), source()]
        self.reject('realm_crossing_requires_explicit_selection', lambda: freeze_scope(realms, sources))
        self.reject('realm_source_outside_scope', lambda: freeze_scope(realms[:1], sources))
        scope = freeze_scope(realms, sources, explicit_cross=True, actor='test-user')
        self.assertEqual(scope['sources'], sources)
        self.assertEqual(scope['realm_revisions'], [{'realm_id': item['realm_id'], 'revision_id': item['revision_id']} for item in realms])
        self.assertEqual(scope['scope_sha256'], _digest({key: value for key, value in scope.items() if key != 'scope_sha256'}))
        self.assertEqual(freeze_scope(list(reversed(realms)), sources, explicit_cross=True, actor='test-user'), scope)

    def test_membership_is_many_to_many_but_store_qualified(self):
        realms = [revision(10, [member()]), revision(20, [member()])]
        for realm in realms:
            self.assertEqual(freeze_scope([realm], [source()])['sources'][0]['data_id'], D1)
        self.reject('realm_source_outside_scope', lambda: freeze_scope(realms[:1], [source(store=OTHER_STORE)]))
        both = [revision(10, [member(), member(D2, OTHER_STORE)])]
        self.reject('realm_cross_store_i2k_unsupported', lambda: freeze_scope(both, [source(), source(D2, OTHER_STORE, execution=5)]))

    def test_series_member_needs_exact_supplied_version_and_data(self):
        realm = revision(10, [member(SERIES, kind='data_series')])
        actual = source(series=SERIES, version=identifier(30))
        scope = freeze_scope([realm], [actual])
        self.assertEqual(scope['sources'][0], actual)
        self.reject('realm_source_outside_scope', lambda: freeze_scope([realm], [source()]))
        self.reject('invalid_realm_source_version', lambda: normalize_sources([source(series=SERIES)]))
        changed = source(series=SERIES, version=identifier(31))
        self.assertNotEqual(freeze_scope([realm], [changed])['scope_sha256'], scope['scope_sha256'])

    def test_old_snapshot_replay_and_no_implicit_member_or_cross_flags(self):
        old = revision(10, [member()])
        frozen = freeze_scope([old], [source()])
        changed = {**old, 'revision_id': identifier(300), 'members': []}
        self.reject('realm_source_outside_scope', lambda: freeze_scope([changed], [source()]))
        self.assertEqual(freeze_scope([old], [source()]), frozen)
        self.reject('invalid_realm_cross_selection', lambda: freeze_scope([old], [source()], explicit_cross='true'))
        self.reject('duplicate_realm_selection', lambda: freeze_scope([old, changed], [source()], explicit_cross=True))
        self.reject('duplicate_realm_source', lambda: normalize_sources([source(), source(execution=5)]))
        self.reject('invalid_realm_source', lambda: normalize_sources([{**source(), 'database': 'untrusted'}]))

    def test_member_normalization_is_strict_and_order_independent(self):
        members = [member(D2), member()]
        self.assertEqual(normalize_members(members), list(reversed(members)))
        self.reject('duplicate_realm_member', lambda: normalize_members([member(), member()]))
        self.reject('invalid_realm_member', lambda: normalize_members([{**member(), 'uri': 'file:///private'}]))
        self.reject('invalid_data_id', lambda: normalize_members([member('a'*63)]))
        self.reject('invalid_request_id', lambda: normalize_members([member(store='019af000-0000-4000-8000-000000000001')]))


@unittest.skipUnless(os.environ.get('PALIMPSEST_REALM_TEST_DSN'), 'Requires an explicitly provisioned disposable Realm catalog')
class RealmPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['PALIMPSEST_REALM_TEST_DSN']
        cls.repo = RealmCatalog(cls.dsn)
        with cls.repo._connection() as conn:
            if conn.execute('SELECT current_database() AS name').fetchone()['name'] != 'palimpsest_realm_checks':
                raise RuntimeError('Realm tests require the dedicated palimpsest_realm_checks database')

    def uid(self):
        with self.repo._connection() as conn:
            return str(conn.execute('SELECT uuidv7() AS id').fetchone()['id'])

    def create(self, name='Synthetic Realm'):
        return self.repo.create(name, 'Metadata fixture; no source import.', 'test-user', 'synthetic-test', self.uid())

    def revise(self, old, members, *, name=None, request=None):
        return self.repo.revise(old['realm_id'], old['revision_id'], name or old['name'], old['description'],
                                members, 'test-user', 'synthetic-revision', request or self.uid())

    def test_request_replay_current_head_cas_and_immutable_history(self):
        request = self.uid()
        first = self.repo.create('Replay Realm', '', 'test-user', 'create', request)
        replay = self.repo.create('Replay Realm', '', 'test-user', 'create', request)
        self.assertTrue(replay['replayed'])
        self.assertEqual(first['revision_id'], replay['revision_id'])
        with self.assertRaises(PalimpsestError) as conflict:
            self.repo.create('Different Realm', '', 'test-user', 'create', request)
        self.assertEqual(conflict.exception.code, 'realm_request_conflict')
        revision_request = self.uid()
        changed = self.revise(first, [member()], request=revision_request)
        latest = self.revise(changed, [member(), member(D2)])
        replay_changed = self.revise(first, [member()], request=revision_request)
        self.assertEqual(replay_changed['revision_id'], changed['revision_id'])
        self.assertTrue(replay_changed['replayed'])
        with self.assertRaises(PalimpsestError) as stale:
            self.revise(first, [])
        self.assertEqual(stale.exception.code, 'realm_revision_changed')
        history = self.repo.history(first['realm_id'])
        self.assertEqual(history['current_revision_id'], latest['revision_id'])
        self.assertEqual([row['revision_no'] for row in history['revisions']], [1, 2, 3])
        self.assertEqual(self.repo.revision(first['revision_id'])['members'], [])

    def test_scopes_and_shared_members_do_not_modify_original_snapshots(self):
        a = self.revise(self.create('Project A'), [member()])
        b = self.revise(self.create('Project B'), [member(), member(D2), member(SERIES, kind='data_series')])
        scope = self.repo.build_scope([a['realm_id']], [source()])
        changed = self.revise(a, [])
        self.assertEqual(freeze_scope([self.repo.revision(a['revision_id'])], [source()]), scope)
        with self.assertRaises(PalimpsestError):
            self.repo.build_scope([a['realm_id']], [source()])
        self.assertEqual(self.repo.build_scope([b['realm_id']], [source()])['sources'][0]['data_id'], D1)
        self.assertNotEqual(changed['revision_id'], a['revision_id'])
        with self.repo._connection() as conn:
            tables = conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='realm_store' ORDER BY tablename").fetchall()
        self.assertEqual([row['tablename'] for row in tables], ['realm_members', 'realm_revisions', 'realms', 'requests'])

    def test_concurrent_revisions_have_one_winner_without_lost_updates(self):
        old = self.create()
        requests = [self.uid(), self.uid()]
        def write(index):
            try:
                return self.revise(old, [member(D1 if index == 0 else D2)], request=requests[index])
            except PalimpsestError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, [0, 1]))
        self.assertEqual(sum(isinstance(value, dict) for value in results), 1)
        self.assertEqual([value for value in results if isinstance(value, str)], ['realm_revision_changed'])
        self.assertEqual(len(self.repo.history(old['realm_id'])['revisions']), 2)

    def test_sql_rejects_history_mutation_and_incomplete_publication(self):
        old = self.revise(self.create(), [member()])
        for sql, values in (
                ('UPDATE realm_store.realm_revisions SET name=%s WHERE revision_id=%s', ('tamper', old['revision_id'])),
                ('DELETE FROM realm_store.realm_members WHERE revision_id=%s', (old['revision_id'],)),
                ('UPDATE realm_store.requests SET request_fingerprint=%s WHERE request_id=%s', ('0'*64, old['request_id'])),
                ('DELETE FROM realm_store.realms WHERE realm_id=%s', (old['realm_id'],))):
            with self.subTest(sql=sql), self.assertRaises(PalimpsestError):
                with self.repo._connection() as conn, conn.transaction():
                    conn.execute(sql, values)
        request, revision_id = self.uid(), self.uid()
        payload = {'schema_version': PROFILE, 'operation': 'revise', 'realm_id': old['realm_id'],
                   'expected_revision_id': old['revision_id'], 'name': old['name'], 'description': old['description'],
                   'members': [member(D2)], 'actor': 'test-user', 'reason': 'synthetic incomplete publication'}
        with self.assertRaises(PalimpsestError):
            with self.repo._connection() as conn, conn.transaction():
                conn.execute('''INSERT INTO realm_store.requests
                    (request_id,request_fingerprint,operation,request_json,realm_id,expected_revision_id,result_revision_id)
                    VALUES (%s,%s,'revise',%s,%s,%s,%s)''',
                    (request, _digest(payload), _json(payload), old['realm_id'], old['revision_id'], revision_id))
                conn.execute('''INSERT INTO realm_store.realm_revisions
                    (revision_id,realm_id,parent_revision_id,revision_no,name,description,actor,reason,request_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (revision_id, old['realm_id'], old['revision_id'], old['revision_no']+1,
                     payload['name'], payload['description'], payload['actor'], payload['reason'], request))
                conn.execute('UPDATE realm_store.realms SET current_revision_id=%s WHERE realm_id=%s', (revision_id, old['realm_id']))
                # The declared member is deliberately absent: deferred guard must reject.
        self.assertEqual(self.repo.history(old['realm_id'])['current_revision_id'], old['revision_id'])
