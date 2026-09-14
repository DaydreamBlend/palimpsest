"""Realm I2K source checks; synthetic receipts only, never a provider call."""

from copy import deepcopy
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from palimpsest.errors import PalimpsestError
from palimpsest.realms import RealmCatalog, freeze_scope
from palimpsest.realm_i2k import PROFILE, RealmI2KGuard, comparison_catalog, configured_guard, verify_job
from test_realms import STORE, OTHER_STORE, D1, member, source, revision, identifier


class RealmI2KUnitTests(unittest.TestCase):
    def test_comparison_catalog_keeps_global_k_meaning_but_no_raw_source(self):
        node = {'knode_id': identifier(40), 'statement': 'Accepted shared definition.', 'semantic_payload': {'scope': 'general'},
                'identity_scope': 'general', 'direct_groundings': [{'quote': 'private I outside this Realm'}],
                'transitive_data_refs': [{'evidence': {'quote': 'private original D'}}],
                'current_applicability': 'current_premises', 'content_fingerprint': 'a'*64}
        projected, edges = comparison_catalog([node], [])
        self.assertEqual(projected[0]['statement'], node['statement'])
        self.assertEqual(projected[0]['content_fingerprint'], node['content_fingerprint'])
        self.assertNotIn('direct_groundings', projected[0])
        self.assertNotIn('transitive_data_refs', projected[0])
        self.assertEqual(comparison_catalog(projected, edges), (projected, edges))
        self.assertIn('direct_groundings', node)

    def test_stored_scoped_job_cannot_use_unconfigured_raw_runtime(self):
        legacy = {'operation': 'i2k', 'profile': {}, 'input_snapshot': {}}
        verify_job(SimpleNamespace(realm_guard=None), None, legacy)
        job = {'operation': 'i2k', 'profile': {'realm_i2k_policy': PROFILE}, 'input_snapshot': {'realm_scope': {}}}
        with self.assertRaises(PalimpsestError) as failure:
            verify_job(SimpleNamespace(realm_guard=None), None, job)
        self.assertEqual(failure.exception.code, 'realm_configuration_required')

    def test_self_declared_cross_flag_is_not_trusted_caller_selection(self):
        catalog = Mock()
        guard = RealmI2KGuard(catalog, STORE, 'unused')
        scope = freeze_scope([revision(10, [member()]), revision(20, [member()])], [source()], explicit_cross=True)
        with self.assertRaises(PalimpsestError) as failure:
            guard.prepare(None, {}, scope=scope)
        self.assertEqual(failure.exception.code, 'realm_crossing_requires_explicit_selection')
        catalog.revision.assert_not_called()

    def test_missing_host_configuration_does_not_read_a_secret_or_source(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(configured_guard('unused'))
            with self.assertRaises(PalimpsestError) as failure:
                configured_guard('unused', realm_ids=[identifier(10)])
        self.assertEqual(failure.exception.code, 'realm_configuration_required')


@unittest.skipUnless(os.environ.get('PALIMPSEST_TEST_DSN') and os.environ.get('PALIMPSEST_REALM_TEST_DSN'),
                     'Requires separately provisioned source fixture and Realm catalog databases')
class RealmI2KPostgresTests(unittest.TestCase):
    def setUp(self):
        from palimpsest.canonical_store import connection
        from palimpsest.knowledge_runtime import KnowledgeRuntime
        import test_multi_source_runtime as fixtures
        self.dsn = os.environ['PALIMPSEST_TEST_DSN']
        self.catalog = RealmCatalog(os.environ['PALIMPSEST_REALM_TEST_DSN'])
        with connection(self.dsn) as conn:
            self.assertIn(conn.execute('SELECT current_database() AS name').fetchone()['name'],
                          ('palimpsest', 'palimpsest_effective_k2k_checks', 'palimpsest_wisdom_checks'))
        with self.catalog._connection() as conn:
            self.assertEqual(conn.execute('SELECT current_database() AS name').fetchone()['name'], 'palimpsest_realm_checks')
        self.fixture = fixtures.MultiSourceRuntimeTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.raw = self.fixture.runtime
        self.product = KnowledgeRuntime(self.dsn, require_realm=True)
        self.uid = self.fixture.first.repo.allocate_id
        self.a = self.make_realm(self.fixture.first.data_id)
        self.b = self.make_realm(self.fixture.second.data_id)

    def make_realm(self, owner):
        empty = self.catalog.create('Synthetic I2K Realm', 'Fixture only.', 'test-user', 'create fixture', self.uid())
        return self.catalog.revise(empty['realm_id'], empty['revision_id'], empty['name'], empty['description'],
            [member(owner)], 'test-user', 'bind actual source fixture', self.uid())

    def runtime(self, realms=(), *, cross=False, store=STORE):
        from palimpsest.knowledge_runtime import KnowledgeRuntime
        return KnowledgeRuntime(self.dsn, require_realm=True,
            realm_guard=RealmI2KGuard(self.catalog, store, self.dsn, realm_ids=realms, explicit_cross=cross, actor='test-user'))

    def prepare(self, runtime, *, identifier_value=None, feedback=None):
        return runtime.prepare('i2k', self.fixture.bundle['data_id'], identifier_value or self.uid(), self.fixture.bundle,
                               selection=True, source_review=False, feedback_execution_id=feedback)

    def test_product_start_requires_realm_and_cross_requires_explicit_selection(self):
        for runtime, expected in ((self.product, 'realm_required'),
                (self.runtime([self.a['realm_id']]), 'realm_source_outside_scope'),
                (self.runtime([self.a['realm_id'], self.b['realm_id']]), 'realm_crossing_requires_explicit_selection')):
            with self.assertRaises(PalimpsestError) as failure:
                self.prepare(runtime)
            self.assertEqual(failure.exception.code, expected)
        runtime = self.runtime([self.a['realm_id'], self.b['realm_id']], cross=True)
        job = self.prepare(runtime)
        self.assertEqual(job['profile']['realm_i2k_policy'], PROFILE)
        self.assertEqual([row['data_id'] for row in job['input_snapshot']['realm_scope']['sources']],
                         [self.fixture.first.data_id, self.fixture.second.data_id])
        replay = self.prepare(runtime, identifier_value=job['request_id'])
        self.assertTrue(replay['replayed'])
        self.assertEqual(replay['input_digest'], job['input_digest'])

    def test_automatic_i2k_chooses_unique_current_common_realm(self):
        from palimpsest.multi_source_i2k import combine_packets
        packet = combine_packets([self.fixture.first.packet])
        runtime = self.runtime()
        job = runtime.prepare('i2k', packet['data_id'], self.uid(), packet, selection=True, source_review=False)
        self.assertEqual(job['input_snapshot']['realm_scope']['realm_revisions'],
                         [{'realm_id': self.a['realm_id'], 'revision_id': self.a['revision_id']}])
        self.make_realm(self.fixture.first.data_id)
        with self.assertRaises(PalimpsestError) as ambiguous:
            runtime.prepare('i2k', packet['data_id'], self.uid(), packet, selection=True, source_review=False)
        self.assertEqual(ambiguous.exception.code, 'realm_selection_ambiguous')

    def test_stage_decide_and_feedback_keep_frozen_scope_after_membership_change(self):
        runtime = self.runtime([self.a['realm_id'], self.b['realm_id']], cross=True)
        self.fixture.runtime = runtime
        job = self.prepare(runtime)
        scope = deepcopy(job['input_snapshot']['realm_scope'])
        output = self.fixture.response()
        receipt = self.fixture.receipt(job, output, 'generator')
        with self.assertRaises(PalimpsestError) as missing:
            self.raw.stage(job['execution_id'], output, receipt)
        self.assertEqual(missing.exception.code, 'realm_configuration_required')
        with self.assertRaises(PalimpsestError) as wrong:
            self.runtime(store=OTHER_STORE).stage(job['execution_id'], output, receipt)
        self.assertEqual(wrong.exception.code, 'realm_source_outside_scope')
        runtime.stage(job['execution_id'], output, receipt)
        self.catalog.revise(self.a['realm_id'], self.a['revision_id'], self.a['name'], self.a['description'], [],
                            'test-user', 'organizational change only', self.uid())
        decisions = self.fixture.decisions(output)
        receipt = self.fixture.receipt(job, decisions, 'validator')
        with self.assertRaises(PalimpsestError) as missing:
            self.raw.decide(job['execution_id'], decisions, receipt)
        self.assertEqual(missing.exception.code, 'realm_configuration_required')
        final = runtime.decide(job['execution_id'], decisions, receipt)
        self.assertEqual(final['state'], 'completed')
        self.assertEqual(final['input_snapshot']['realm_scope'], scope)
        # No fresh cross selection: same complete source review inherits its
        # previously explicit, exact immutable scope, not the current Realm head.
        resumed = self.prepare(self.runtime(), feedback=job['execution_id'])
        self.assertEqual(resumed['input_snapshot']['realm_scope'], scope)

    def test_actual_information_ownership_and_catalogue_do_not_leak_other_sources(self):
        from palimpsest.canonical_store import connection
        guard = RealmI2KGuard(self.catalog, STORE, self.dsn)
        packet = deepcopy(self.fixture.first.packet)
        wrong_id = self.fixture.second.packet['model_input']['information'][0]['information_id']
        packet['model_input']['information'][0]['information_id'] = wrong_id
        with connection(self.dsn) as conn, self.assertRaises(PalimpsestError) as wrong:
            guard.source_refs(conn, packet)
        self.assertEqual(wrong.exception.code, 'realm_i2k_information_owner_mismatch')
        # Seed source-grounded K via the explicitly preserved low-level fixture.
        prior = self.fixture.prepare()
        output = self.fixture.response()
        self.raw.stage(prior['execution_id'], output, self.fixture.receipt(prior, output, 'generator'))
        self.raw.decide(prior['execution_id'], self.fixture.decisions(output),
                        self.fixture.receipt(prior, self.fixture.decisions(output), 'validator'))
        job = self.prepare(self.runtime([self.a['realm_id'], self.b['realm_id']], cross=True))
        nodes = job['input_snapshot']['existing_nodes']
        self.assertTrue(nodes)
        self.assertTrue(any(node['identity_scope'] == 'general' for node in nodes))
        self.assertFalse(any('direct_groundings' in node or 'transitive_source_refs' in node or 'direct_data_groundings' in node for node in nodes))

    def test_actual_series_version_ownership_and_pinned_scope_survive_new_head(self):
        from palimpsest.artifact_store import ArtifactStore
        from palimpsest.data_versions import DataVersions
        from palimpsest.multi_source_i2k import combine_packets
        first = self.fixture.first
        versions = DataVersions(self.dsn, ArtifactStore(first.fixture.root))
        series = versions.create('Synthetic Realm version scope', self.uid())['series_id']
        initial = versions.append(series, first.data_id, self.uid(), None)
        other_series = versions.create('Different synthetic series', self.uid())['series_id']
        other_version = versions.append(other_series, first.data_id, self.uid(), None)
        self.catalog.revise(self.a['realm_id'], self.a['revision_id'], self.a['name'], self.a['description'],
            [member(series, kind='data_series')], 'test-user', 'use explicit versioned source membership', self.uid())
        current = DataVersions(self.dsn, ArtifactStore(self.fixture.second.fixture.root)).append(
            series, self.fixture.second.data_id, self.uid(), initial['version_id'])
        runtime = self.runtime([self.a['realm_id']])
        packet = combine_packets([first.packet])
        def prepare(version, mode='pinned'):
            return runtime.prepare('i2k', first.data_id, self.uid(), packet, selection=True, source_review=False,
                data_version_ids=[version], data_version_mode=mode)
        for version, expected in ((current['version_id'], 'realm_source_version_mismatch'),
                (other_version['version_id'], 'realm_source_outside_scope')):
            with self.assertRaises(PalimpsestError) as failure:
                prepare(version)
            self.assertEqual(failure.exception.code, expected)
        with self.assertRaises(PalimpsestError) as stale:
            prepare(initial['version_id'], 'current')
        self.assertEqual(stale.exception.code, 'data_version_head_changed')
        pinned = prepare(initial['version_id'])
        bound = pinned['input_snapshot']['realm_scope']['sources'][0]
        self.assertEqual((bound['data_id'], bound['series_id'], bound['version_id']),
                         (first.data_id, series, initial['version_id']))
        self.assertEqual(pinned['input_snapshot']['data_version_mode'], 'pinned')
