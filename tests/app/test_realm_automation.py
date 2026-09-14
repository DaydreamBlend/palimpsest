"""Realm defaults and frozen automation requests; synthetic inputs only."""

from copy import deepcopy
import os
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

from palimpsest.errors import PalimpsestError
from palimpsest.realm_automation import (PropagationRealmGuard, common_realm,
    default_i2k_realm, root_realm_ids, replay_scope)
from palimpsest.realm_registration import PROFILE as REGISTRATION_PROFILE
from test_realms import STORE, OTHER_STORE, SERIES, D1, D2, identifier, member, source, revision


class RealmAutomationTests(unittest.TestCase):
    def reject(self, code, callback):
        with self.assertRaises(PalimpsestError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_common_membership_uses_initial_realm_only_to_resolve_a_real_tie(self):
        first, second = revision(10, [member(), member(D2)]), revision(20, [member()])
        self.assertEqual(common_realm([first, second], [source(), source(D2)])['realm_id'], first['realm_id'])
        self.reject('realm_selection_ambiguous', lambda: common_realm([first, second], [source()]))
        self.assertEqual(common_realm([first, second], [source()], [second['realm_id']]), second)
        self.reject('realm_source_outside_scope', lambda: common_realm([first], [source(store=OTHER_STORE)]))
        self.reject('realm_source_outside_scope', lambda: common_realm(
            [{**first, 'members': []}], [source()], [first['realm_id']]))
        series = revision(30, [member(SERIES, kind='data_series')])
        self.assertEqual(common_realm([series], [source(series=SERIES, version=identifier(40))]), series)

    def test_default_i2k_requires_common_initial_choice_for_every_source(self):
        first, second = revision(10, [member(), member(D2)]), revision(20, [member(), member(D2)])
        catalog, conn = Mock(), Mock()
        catalog.catalog.return_value = {'realms': [first, second]}
        initial = {'schema_version': REGISTRATION_PROFILE, 'realm_id': second['realm_id'],
            'initial_revision_id': second['revision_id'], 'store_id': STORE, 'membership_request_id': identifier(80),
            'actor': 'user', 'reason': 'Initial selection'}
        rows = [{'data_id': owner, 'external_metadata': {'realm_registration': deepcopy(initial)}} for owner in (D1, D2)]
        conn.execute.return_value.fetchall.return_value = rows
        self.assertEqual(default_i2k_realm(conn, catalog, [source(), source(D2)]), second)
        conn.execute.return_value.fetchall.return_value = rows[:1]
        self.reject('realm_selection_ambiguous', lambda: default_i2k_realm(conn, catalog, [source(), source(D2)]))

    def test_root_scope_does_not_implicitly_union_realms_or_legacy_inputs(self):
        first = {'realm_scope': {'realm_revisions': [{'realm_id': identifier(10)}]}}
        derived = {'propagation_scope': {'scope': deepcopy(first)}}
        self.assertEqual(root_realm_ids([first, derived]), [identifier(10)])
        second = {'realm_scope': {'realm_revisions': [{'realm_id': identifier(20)}]}}
        self.reject('realm_crossing_requires_explicit_selection', lambda: root_realm_ids([first, second]))
        self.reject('realm_required', lambda: root_realm_ids([first, {}]))

    def test_propagation_resolves_only_verified_selected_store_members(self):
        catalog, conn = Mock(), Mock()
        first, second = revision(10, [member(), member(D2, OTHER_STORE)]), revision(20, [member(D2)])
        catalog.catalog.return_value = {'realms': [first, second]}
        def execute(query, args=()):
            if 'k_execution_contexts' in query:
                rows = [{'input_snapshot': {'realm_scope': {'realm_revisions': [{'realm_id': first['realm_id']}]}}}]
            elif 'data_acquisitions' in query:
                rows = []
            elif 'canonical_store.data WHERE' in query:
                rows = [{'data_id': owner} for owner in args[0]]
            else:
                raise AssertionError(query)
            return Mock(fetchall=Mock(return_value=rows))
        conn.execute.side_effect = execute
        versions = ModuleType('palimpsest.data_versions')
        versions.immutable_versions = Mock(return_value=[])
        with patch.dict('sys.modules', {'palimpsest.data_versions': versions}):
            guard = PropagationRealmGuard(catalog, STORE, 'unused')
            frozen = guard.prepare(conn, [identifier(50)])
            self.assertEqual(frozen['allowed_data_ids'], [D1])
            self.assertEqual(frozen['realm_revisions'], [{'realm_id': first['realm_id'], 'revision_id': first['revision_id']}])
            self.reject('realm_source_outside_scope', lambda: guard.prepare(conn, [identifier(50)], allowed_data_ids=[D2]))
            crossing = PropagationRealmGuard(catalog, STORE, 'unused', realm_ids=[first['realm_id'], second['realm_id']])
            self.reject('realm_crossing_requires_explicit_selection', lambda: crossing.prepare(conn, [identifier(50)]))
            crossing.explicit_cross = True
            self.assertEqual(crossing.prepare(conn, [identifier(50)])['allowed_data_ids'], [D1, D2])

    def test_frozen_replay_does_not_read_new_membership_or_erase_legacy_policy(self):
        scope = {'root_record_ids': [identifier(50)], 'allowed_data_ids': [D1], 'wiki_ids': [],
                 'data_versions': [], 'data_version_mode': 'current'}
        policy = {'discovery': True, 'repeated_outcome': 'halt'}
        original = {'scope': deepcopy(scope), 'policy': deepcopy(policy)}
        args = dict(roots=[identifier(50)], allowed_data_ids=None, wiki_ids=None,
                    version_ids=None, version_mode='current', discovery=True)
        self.assertEqual(replay_scope(original, **args), (scope, policy))
        self.reject('propagation_request_conflict', lambda: replay_scope(original, **{**args, 'allowed_data_ids': [D2]}))
        guard = PropagationRealmGuard(Mock(), STORE, 'unused', realm_ids=[identifier(10)])
        self.reject('propagation_request_conflict', lambda: replay_scope(original, **args, guard=guard))
        scope['realm_scope'] = {'store_id': STORE, 'realm_revisions': [{'realm_id': identifier(10)}], 'explicit_cross': False}
        original['scope'] = deepcopy(scope)
        self.assertEqual(replay_scope(original, **args, guard=guard), (scope, policy))
        guard.catalog.catalog.assert_not_called()
        guard.store_id = OTHER_STORE
        self.reject('propagation_request_conflict', lambda: replay_scope(original, **args, guard=guard))

    def test_product_cli_binds_realm_to_the_selected_source_database(self):
        from types import SimpleNamespace
        from palimpsest import cli
        from palimpsest.propagation_cli import run
        args = cli._parser().parse_args(['propagation', 'prepare', '--directory', 'unused',
            '--database-name', 'source-checks', '--request-id', identifier(50), '--record-id', identifier(51),
            '--realm-id', identifier(10), '--realm-id', identifier(20), '--allow-cross-realm'])
        module, runtime, guard = ModuleType('palimpsest.propagation_runtime'), Mock(), Mock()
        module.PropagationRuntime = Mock(return_value=runtime)
        with patch.dict('sys.modules', {'palimpsest.propagation_runtime': module}), \
                patch('palimpsest.config.select_database', return_value='selected source dsn'), \
                patch('palimpsest.realm_automation.configured_guard', return_value=guard) as configure:
            run(args, SimpleNamespace(database_dsn='base', artifact_root='artifacts', actor_ref='user'))
        configure.assert_called_once_with('selected source dsn', realm_ids=[identifier(10), identifier(20)],
                                         explicit_cross=True, actor='user', database_name=None)
        self.assertTrue(module.PropagationRuntime.call_args.kwargs['require_realm'])
        self.assertIs(module.PropagationRuntime.call_args.kwargs['realm_guard'], guard)
        self.assertEqual(runtime.prepare.call_args.args[:2], (identifier(50), [identifier(51)]))


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN')
                     and os.environ.get('PALIMPSEST_REALM_TEST_DSN'), 'Requires disposable source and Realm PG fixtures')
class RealmAutomationPostgresTests(unittest.TestCase):
    def setUp(self):
        from palimpsest.artifact_store import ArtifactStore
        from palimpsest.canonical_store import connection
        from palimpsest.knowledge_runtime import KnowledgeRuntime
        from palimpsest.realm_i2k import RealmI2KGuard
        from palimpsest.realms import RealmCatalog
        from palimpsest.service import DataService
        from test_knowledge_revision_integration import KnowledgeRevisionIntegrationTests
        self.dsn = os.environ['PALIMPSEST_TEST_DSN']
        with connection(self.dsn) as conn:
            self.assertIn(conn.execute('SELECT current_database() AS name').fetchone()['name'],
                          ('palimpsest', 'palimpsest_propagation_checks', 'palimpsest_effective_k2k_checks', 'palimpsest_wisdom_checks'))
        self.catalog = RealmCatalog(os.environ['PALIMPSEST_REALM_TEST_DSN'])
        with self.catalog._connection() as conn:
            self.assertEqual(conn.execute('SELECT current_database() AS name').fetchone()['name'], 'palimpsest_realm_checks')
        self.fixture = KnowledgeRevisionIntegrationTests('runTest')
        self.fixture.dsn = self.dsn
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.store = self.fixture.repo.allocate_id()
        self.realm = self.make_realm(self.fixture.data_id)
        self.fixture.runtime = KnowledgeRuntime(self.dsn, require_realm=True,
            realm_guard=RealmI2KGuard(self.catalog, self.store, self.dsn, actor='test-user'))
        job = self.fixture.prepare_source(self.fixture.source_target)
        changed = self.fixture.commit(job, self.fixture.source_response([
            self.fixture.source_candidate('observation', 'observation', 'four')]))
        self.root = changed['records'][0]['record_id']
        extra = self.fixture.base / 'second.md'
        extra.write_text('# Another synthetic Realm\n' + self.fixture.repo.allocate_id(), encoding='utf-8')
        self.other_data = DataService(self.fixture.repo, ArtifactStore(self.fixture.root), actor_ref='test-user').import_file(extra)['data_id']
        self.other_realm = self.make_realm(self.other_data)

    def make_realm(self, owner):
        current = self.catalog.create('Automation fixture', '', 'test-user', 'Synthetic Realm', self.fixture.repo.allocate_id())
        return self.catalog.revise(current['realm_id'], current['revision_id'], current['name'], current['description'],
            [member(owner, self.store)], 'test-user', 'Synthetic membership', self.fixture.repo.allocate_id())

    def worker(self, *, realm_ids=(), cross=False):
        from palimpsest.propagation_runtime import PropagationRuntime
        return PropagationRuntime(self.dsn, self.fixture.root, self.fixture.base / 'realm-worker', require_realm=True,
            realm_guard=PropagationRealmGuard(self.catalog, self.store, self.dsn,
                realm_ids=realm_ids, explicit_cross=cross, actor='test-user'))

    def test_actual_root_scope_default_and_replay_survive_reclassification(self):
        worker = self.worker()
        identifier = self.fixture.repo.allocate_id()
        prepared = worker.prepare(identifier, [self.root], wiki_ids=[], discovery=False)
        self.assertEqual(prepared['scope']['allowed_data_ids'], [self.fixture.data_id])
        self.assertEqual(prepared['scope']['realm_scope']['realm_revisions'],
            [{'realm_id': self.realm['realm_id'], 'revision_id': self.realm['revision_id']}])
        current = self.catalog.current(self.realm['realm_id'])
        self.catalog.revise(current['realm_id'], current['revision_id'], current['name'], current['description'],
            [*current['members'], member(self.other_data, self.store)], 'test-user', 'Classification update', self.fixture.repo.allocate_id())
        replayed = worker.prepare(identifier, [self.root], wiki_ids=[], discovery=False)
        self.assertEqual(replayed['request_fingerprint'], prepared['request_fingerprint'])
        self.assertEqual(replayed['scope'], prepared['scope'])
        fresh = worker.prepare(self.fixture.repo.allocate_id(), [self.root], wiki_ids=[], discovery=False)
        self.assertEqual(fresh['scope']['allowed_data_ids'], sorted([self.fixture.data_id, self.other_data]))
        with self.assertRaises(PalimpsestError) as crossed:
            self.worker(realm_ids=[self.realm['realm_id'], self.other_realm['realm_id']]).prepare(
                self.fixture.repo.allocate_id(), [self.root], wiki_ids=[])
        self.assertEqual(crossed.exception.code, 'realm_crossing_requires_explicit_selection')
        crossing = self.worker(realm_ids=[self.realm['realm_id'], self.other_realm['realm_id']], cross=True).prepare(
            self.fixture.repo.allocate_id(), [self.root], wiki_ids=[])
        self.assertTrue(crossing['scope']['realm_scope']['explicit_cross'])
        self.assertEqual(len(crossing['scope']['realm_scope']['realm_revisions']), 2)

    def test_actual_series_membership_pins_requested_version_and_checks_current_head(self):
        from palimpsest.artifact_store import ArtifactStore
        from palimpsest.data_versions import DataVersions
        versions = DataVersions(self.dsn, ArtifactStore(self.fixture.root))
        series = versions.create('Realm version fixture', self.fixture.repo.allocate_id(), actor_ref='test-user')['series_id']
        old = versions.append(series, self.fixture.data_id, self.fixture.repo.allocate_id(), None, actor_ref='test-user')
        versions.append(series, self.other_data, self.fixture.repo.allocate_id(), old['version_id'], actor_ref='test-user')
        current = self.catalog.current(self.realm['realm_id'])
        self.catalog.revise(current['realm_id'], current['revision_id'], current['name'], current['description'],
            [member(series, self.store, 'data_series')], 'test-user', 'Classify series', self.fixture.repo.allocate_id())
        worker = self.worker()
        with self.assertRaises(PalimpsestError) as stale:
            worker.prepare(self.fixture.repo.allocate_id(), [self.root], wiki_ids=[], data_version_ids=[old['version_id']])
        self.assertEqual(stale.exception.code, 'data_version_head_changed')
        pinned = worker.prepare(self.fixture.repo.allocate_id(), [self.root], wiki_ids=[],
            data_version_ids=[old['version_id']], data_version_mode='pinned')
        self.assertEqual(pinned['scope']['allowed_data_ids'], [self.fixture.data_id])
        self.assertEqual(pinned['scope']['realm_scope']['series_versions'],
            [{'series_id': series, 'version_id': old['version_id'], 'data_id': self.fixture.data_id}])


if __name__ == '__main__':
    unittest.main()
