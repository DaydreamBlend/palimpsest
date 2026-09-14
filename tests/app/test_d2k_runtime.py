"""Explicit D2K persistence in the disposable Linux PostgreSQL fixture only.

All grants and model receipts here are labelled synthetic fixtures. No real
provider, PDF renderer, migration, or existing user source is used. Root runs
these sequential tests only after provisioning the reviewed schema.
"""

from contextlib import contextmanager, ExitStack
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

import psycopg

from palimpsest import d2k, k2k
from palimpsest.artifact_store import ArtifactStore
from palimpsest.canonical_store import PostgresRepository, connection
from palimpsest.compiler_runtime import CompilerRuntime
from palimpsest.d2k_runtime import D2KRuntime
from palimpsest.data_versions import DataVersions
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.knowledge_runtime import KnowledgeRuntime, MODEL
from palimpsest.service import DataService
import test_d2k as pure
import test_k2k_runtime as inference_fixtures
import test_selection_runtime as selection_fixtures


@contextmanager
def no_d2i(*, no_source_reads=False):
    targets = ['palimpsest.compiler_runtime.CompilerRuntime.compile_code',
        'palimpsest.compiler_runtime.CompilerRuntime.compile_markdown',
        'palimpsest.compiler_runtime.CompilerRuntime.materialize_source',
        'palimpsest.compiler_runtime.CompilerRuntime.prepare_input',
        'palimpsest.compiler_runtime.CompilerRuntime.add_source_pages',
        'palimpsest.codex_provider.CodexProvider.generate']
    if no_source_reads:
        targets.append('palimpsest.artifact_store.ArtifactStore.read')
    with ExitStack() as stack:
        probes = [stack.enter_context(patch(target, side_effect=AssertionError('D2K must not invoke D2I/I repair or a model')))
                  for target in targets]
        yield
        for probe in probes:
            probe.assert_not_called()


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires explicitly provisioned Linux PostgreSQL fixture database palimpsest')
class D2KRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['PALIMPSEST_TEST_DSN']
        with connection(cls.dsn) as conn:
            if conn.execute('SELECT current_database() AS name').fetchone()['name'] not in (
                    'palimpsest','palimpsest_d2k_checks','palimpsest_propagation_checks'):
                raise RuntimeError('D2K tests require isolated database palimpsest')
            for table in ('compiler_runtime.d2k_preparations', 'compiler_runtime.d2k_source_views',
                          'compiler_runtime.d2k_authorizations', 'canonical_store.knowledge_data_groundings'):
                if conn.execute('SELECT to_regclass(%s) AS name', (table,)).fetchone()['name'] is None:
                    raise RuntimeError('Provision the reviewed D2K fixture migration before these tests')

    def setUp(self):
        temporary = TemporaryDirectory(prefix='d2k-runtime-fixture-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / 'artifacts'
        self.repo = PostgresRepository(self.dsn)
        self.store = ArtifactStore(self.root)
        self.data = DataService(self.repo, self.store)
        self.runtime = KnowledgeRuntime(self.dsn)
        self.source = D2KRuntime(self.dsn, self.root)
        self.raw = (f'\ufeff# Unique D2K fixture {uuid4()}\r\n'
                    'The source explicitly declares μ 😀 Cafe\u0301.\r\n'
                    'Second explicitly reported fixture statement.\r\n').encode('utf-8')
        self.path = self.base / 'source.md'
        self.path.write_bytes(self.raw)
        self.data_id = self.data.import_file(self.path, media_type='text/markdown')['data_id']
        self.reason = 'Synthetic user-reported D2I problem; no successful parse or repaired source is claimed.'
        split = self.raw.index(b'Second')
        self.ranges = [[0, split], [split, len(self.raw)]]
        for target in ('subprocess.Popen', 'subprocess.run', 'urllib.request.urlopen'):
            blocked = patch(target, side_effect=AssertionError('No real provider, renderer or network call in D2K fixture'))
            blocked.start()
            self.addCleanup(blocked.stop)

    def row(self, query, parameters=()):
        with connection(self.dsn) as conn:
            return conn.execute(query, parameters).fetchone()

    def counts(self):
        return self.row('''SELECT
            (SELECT count(*) FROM canonical_store.data WHERE data_id=%s) AS data,
            (SELECT count(*) FROM canonical_store.information WHERE data_id=%s) AS information,
            (SELECT count(*) FROM compiler_runtime.operation_executions WHERE data_id=%s AND operation='d2i') AS d2i,
            (SELECT count(*) FROM compiler_runtime.operation_executions WHERE data_id=%s AND operation='d2k') AS d2k,
            (SELECT count(*) FROM canonical_store.knowledge_node_scopes WHERE source_data_id=%s) AS nodes,
            (SELECT count(*) FROM canonical_store.knowledge_data_groundings WHERE data_id=%s) AS data_groundings,
            (SELECT count(*) FROM canonical_store.knowledge_node_groundings g JOIN canonical_store.information i USING(information_id) WHERE i.data_id=%s) AS information_groundings,
            (SELECT count(*) FROM compiler_runtime.k_temporary_candidates c JOIN compiler_runtime.k_compilation_records r USING(record_id)
                JOIN compiler_runtime.operation_executions e USING(execution_id) WHERE e.data_id=%s) AS candidates''', (self.data_id,) * 8)

    def grant(self, *, preparation_id=None, **options):
        preparation_id = preparation_id or self.repo.allocate_id()
        with no_d2i():
            drafted = self.source.draft(self.data_id, preparation_id, reason=self.reason, byte_ranges=self.ranges, **options)
            saved = self.source.preparation(preparation_id)
            authorization = self.source.authorize(preparation_id, self.repo.allocate_id(), drafted['manifest_sha256'], actor_ref='test-user')
        return drafted, saved, authorization

    def prepare(self, authorization, *, identifier=None, prior=None):
        with no_d2i():
            return self.source.prepare(authorization['authorization_id'], identifier or self.repo.allocate_id(), prior_execution_id=prior)

    def response(self, job):
        value = pure.response(job['input_snapshot']['input'])
        value['nodes'][0]['semantic_payload']['subject'] = 'Synthetic original D ' + self.data_id
        return value

    def receipt(self, job, response, phase):
        current = self.runtime.show(job['execution_id'])
        snapshot, packet = current['input_snapshot'], current['input_snapshot']['input']
        context = self.runtime.validation_context(job['execution_id']) if phase == 'validator' else None
        if current['operation'] == 'd2k':
            prompt = d2k.generation(snapshot, []) if phase == 'generator' else d2k.validation(context, [])
            schema = (d2k.generation_schema(packet) if phase == 'generator' else d2k.validation_schema(
                [node['candidate_key'] for node in context['candidates']],
                [node['knode_revision_id'] for node in snapshot['existing_nodes']], packet))
            delivered = {'delivered_data_view_ids': d2k.check_input(packet),
                'delivered_knowledge_revision_ids': [node['knode_revision_id'] for node in snapshot['existing_nodes']]}
        else:
            prompt = k2k.generation(snapshot, []) if phase == 'generator' else k2k.validation(context, [])
            schema = (k2k.generation_schema(packet) if phase == 'generator' else k2k.validation_schema(
                [node['candidate_key'] for node in context['candidates']],
                [node['knode_revision_id'] for node in snapshot['existing_nodes']]))
            delivered = {'delivered_knowledge_revision_ids': [node['knode_revision_id'] for node in packet['nodes']]}
        result = {'profile': {**current['profile']['model'], 'synthetic_receipt': True},
            'input_sha256': current['input_digest'] if phase == 'generator' else context['validation_context_sha'],
            'output_sha256': digest(response), 'prompt_sha256': sha256(prompt.encode('utf-8')).hexdigest(),
            'schema_sha256': digest(schema), 'provider_ref': 'synthetic-d2k-no-model-' + str(uuid4()),
            'actual_delivery': True, 'original_pdf_delivered': False, 'image_attachments': [],
            'usage': {}, 'test_only': True, **delivered}
        if snapshot.get('data_versions'):
            result['delivered_data_version_ids'] = [version['version_id'] for version in snapshot['data_versions']]
        return result

    def stage(self, job, response=None):
        value = response or self.response(job)
        with no_d2i(no_source_reads=True):
            return self.runtime.stage(job['execution_id'], value, self.receipt(job, value, 'generator'))

    def commit(self, job, *, response=None, decisions=None):
        value = response or self.response(job)
        self.stage(job, value)
        verdicts = decisions or pure.decisions(job['input_snapshot']['input'])
        with no_d2i(no_source_reads=True):
            return self.runtime.decide(job['execution_id'], verdicts, self.receipt(job, verdicts, 'validator'))

    def reject(self, action, code=None):
        with self.assertRaises(PalimpsestError) as caught:
            action()
        if code is not None:
            self.assertEqual(caught.exception.code, code)

    def test_original_with_zero_I_has_reviewable_exact_manifest_and_explicit_immutable_grant(self):
        self.assertEqual((self.counts()['information'], self.counts()['d2i']), (0, 0))
        identifier = self.repo.allocate_id()
        with no_d2i():
            drafted = self.source.draft(self.data_id, identifier, reason=self.reason, byte_ranges=self.ranges)
            repeated = self.source.draft(self.data_id, identifier, reason=self.reason, byte_ranges=self.ranges)
        self.assertTrue(repeated['replayed'])
        self.assertEqual(repeated['manifest_sha256'], drafted['manifest_sha256'])
        saved = self.source.preparation(identifier)
        self.assertEqual(saved['manifest_sha256'], digest(saved['manifest']))
        self.assertEqual(saved['manifest']['input'], saved['packet'])
        self.assertEqual(saved['manifest']['failure']['kind'], 'user_reported_d2i_issue')
        self.assertEqual(b''.join(view['text'].encode('utf-8') for view in saved['packet']['views']), self.raw)
        self.assertEqual(saved['manifest']['existing_knowledge'], d2k.catalog_nodes(saved['manifest']['existing_knowledge']))
        self.assertEqual(drafted['state'], 'awaiting_explicit_user_confirmation')
        self.assertFalse(drafted['actual_delivery'])
        self.assertEqual((drafted['d2i_calls'], drafted['information_writes']), (0, 0))
        self.reject(lambda: self.source.prepare(self.repo.allocate_id(), self.repo.allocate_id()), 'd2k_user_confirmation_required')
        self.reject(lambda: self.source.authorize(identifier, self.repo.allocate_id(), 'f' * 64, actor_ref='test-user'),
                    'd2k_exact_confirmation_required')
        authorization_id = self.repo.allocate_id()
        granted = self.source.authorize(identifier, authorization_id, drafted['manifest_sha256'], actor_ref='test-user')
        self.assertTrue(self.source.authorize(identifier, authorization_id, drafted['manifest_sha256'], actor_ref='test-user')['replayed'])
        self.reject(lambda: self.source.authorize(identifier, authorization_id, drafted['manifest_sha256'], actor_ref='different-user'),
                    'idempotency_conflict')
        self.assertEqual(granted['model_calls'], 0)
        self.reject(lambda: self.source.draft(self.data_id, identifier, reason='A changed request.', byte_ranges=self.ranges), 'idempotency_conflict')
        view_id = saved['packet']['views'][0]['view_id']
        for query, parameters in (
            ('UPDATE compiler_runtime.d2k_preparations SET manifest_sha256=%s WHERE preparation_id=%s', ('f' * 64, identifier)),
            ('UPDATE compiler_runtime.d2k_authorizations SET actor_ref=%s WHERE authorization_id=%s', ('changed', authorization_id)),
            ("UPDATE compiler_runtime.d2k_source_views SET body=body||'{\"text\":\"invented\"}'::jsonb WHERE view_id=%s", (view_id,))):
            with connection(self.dsn) as conn:
                try:
                    with self.assertRaises(psycopg.Error): conn.execute(query, parameters)
                finally:
                    conn.rollback()
        self.assertEqual(self.source.preparation(identifier), saved)
        self.assertEqual((self.counts()['information'], self.counts()['d2i'], self.counts()['d2k']), (0, 0, 0))

    def test_scope_model_and_absent_authorization_cannot_be_replaced_by_caller_fields(self):
        _, saved, grant = self.grant()
        packet = saved['packet']
        self.reject(lambda: self.runtime.prepare('d2k', self.data_id, self.repo.allocate_id(), packet))
        self.reject(lambda: self.runtime.prepare('d2k', self.data_id, self.repo.allocate_id(), packet,
            authorization_id=self.repo.allocate_id()))
        self.reject(lambda: self.runtime.prepare('d2k', self.data_id, self.repo.allocate_id(), packet,
            authorization_id=grant['authorization_id'], model_profile={**MODEL, 'reasoning_effort': 'high'}))
        first = packet['views'][0]
        changed_view = d2k.text_view(self.raw, view_id=first['view_id'], data_id=self.data_id,
            byte_start=0, byte_end=self.raw.index(b'\r\n') + 2)
        changed = d2k.build_input(self.data_id, media_type='text/markdown', original_byte_size=len(self.raw), views=[changed_view])
        self.reject(lambda: self.runtime.prepare('d2k', self.data_id, self.repo.allocate_id(), changed,
            authorization_id=grant['authorization_id'], model_profile=dict(MODEL)))
        self.assertEqual(self.counts()['d2k'], 0)
        self.assertEqual(self.source.preparation(saved['preparation_id']), saved)

    def test_request_replay_and_same_grant_active_or_completed_retry_boundaries(self):
        _, _, grant = self.grant()
        request = self.repo.allocate_id()
        first = self.prepare(grant, identifier=request)
        repeated = self.prepare(grant, identifier=request)
        self.assertTrue(repeated['replayed'])
        self.assertEqual(first['execution_id'], repeated['execution_id'])
        self.reject(lambda: self.prepare(grant))
        self.reject(lambda: self.prepare(grant, prior=first['execution_id']))
        decided = self.commit(first)
        self.assertEqual(decided['state'], 'completed')
        self.assertTrue(self.prepare(grant, identifier=request)['replayed'])
        self.reject(lambda: self.prepare(grant, prior=first['execution_id']))
        self.assertEqual(self.counts()['d2k'], 1)

    def test_within_grant_held_and_failed_retries_retain_prior_outcomes_and_scope(self):
        _, saved, grant = self.grant()
        first = self.prepare(grant)
        verdicts = pure.decisions(first['input_snapshot']['input'])
        verdicts['complete'] = False
        verdicts['decisions'][0].update(verdict='needs_human', source_explicit=False)
        verdicts['reviews'][0]['verdict'] = 'needs_review'
        held = self.commit(first, decisions=verdicts)
        self.assertEqual(held['state'], 'needs_human')
        before = deepcopy(self.runtime.show(first['execution_id']))
        request = self.repo.allocate_id()
        child = self.prepare(grant, identifier=request, prior=first['execution_id'])
        self.assertEqual(child['input_snapshot']['input'], first['input_snapshot']['input'])
        self.assertTrue(child['input_snapshot'].get('prior_d2k_review'))
        self.assertTrue(self.prepare(grant, identifier=request, prior=first['execution_id'])['replayed'])
        self.reject(lambda: self.prepare(grant, prior=first['execution_id']))
        self.runtime.fail_execution(child['execution_id'], 'synthetic_dispatch_failed')
        failed = deepcopy(self.runtime.show(child['execution_id']))
        retry = self.prepare(grant, prior=child['execution_id'])
        self.assertEqual(retry['state'], 'prepared')
        self.assertEqual(retry['input_snapshot']['input'], saved['packet'])
        self.assertEqual(self.runtime.show(first['execution_id']), before)
        self.assertEqual(self.runtime.show(child['execution_id']), failed)
        _, _, other_grant = self.grant()
        self.reject(lambda: self.prepare(other_grant, prior=first['execution_id']))
        self.assertEqual((self.counts()['information'], self.counts()['d2i']), (0, 0))

    def test_model_delivery_metadata_and_independent_validator_are_required(self):
        _, _, grant = self.grant()
        job = self.prepare(grant)
        value = self.response(job)
        good = self.receipt(job, value, 'generator')
        for mutation in ('views_missing', 'views_wrong', 'views_reversed', 'catalog_missing', 'catalog_wrong',
                         'delivery_false', 'model', 'prompt', 'schema', 'image'):
            receipt = deepcopy(good)
            if mutation == 'views_missing': receipt.pop('delivered_data_view_ids')
            elif mutation == 'views_wrong': receipt['delivered_data_view_ids'] = [self.repo.allocate_id()]
            elif mutation == 'views_reversed': receipt['delivered_data_view_ids'].reverse()
            elif mutation == 'catalog_missing': receipt.pop('delivered_knowledge_revision_ids')
            elif mutation == 'catalog_wrong': receipt['delivered_knowledge_revision_ids'] = [self.repo.allocate_id()]
            elif mutation == 'delivery_false': receipt['actual_delivery'] = False
            elif mutation == 'model': receipt['profile']['reasoning_effort'] = 'high'
            elif mutation == 'prompt': receipt['prompt_sha256'] = 'a' * 64
            elif mutation == 'schema': receipt['schema_sha256'] = 'a' * 64
            else: receipt['image_attachments'] = [{'sha256': 'a' * 64, 'byte_size': 10}]
            with self.subTest(phase='generator', mutation=mutation), no_d2i(no_source_reads=True):
                self.reject(lambda: self.runtime.stage(job['execution_id'], value, receipt))
            self.assertEqual(self.runtime.show(job['execution_id'])['state'], 'prepared')
            self.assertEqual(self.runtime.show(job['execution_id'])['records'], [])
        self.runtime.stage(job['execution_id'], value, good)
        verdicts = pure.decisions(job['input_snapshot']['input'])
        validator = self.receipt(job, verdicts, 'validator')
        for mutation in ('missing_views', 'wrong_catalog', 'same_provider', 'delivery_false'):
            receipt = deepcopy(validator)
            if mutation == 'missing_views': receipt.pop('delivered_data_view_ids')
            elif mutation == 'wrong_catalog': receipt['delivered_knowledge_revision_ids'] = [self.repo.allocate_id()]
            elif mutation == 'same_provider': receipt['provider_ref'] = good['provider_ref']
            else: receipt['actual_delivery'] = False
            with self.subTest(phase='validator', mutation=mutation), no_d2i(no_source_reads=True):
                self.reject(lambda: self.runtime.decide(job['execution_id'], verdicts, receipt))
            self.assertIsNone(self.runtime.show(job['execution_id'])['validator_receipt'])
            self.assertEqual(self.counts()['data_groundings'], 0)
        with no_d2i(no_source_reads=True):
            result = self.runtime.decide(job['execution_id'], verdicts, validator)
        self.assertEqual(result['state'], 'completed')

    def test_D2K_source_origin_has_D_groundings_without_I_and_exact_reuse_keeps_revision(self):
        _, saved, grant = self.grant()
        job = self.prepare(grant)
        expected = d2k.normalize_proposals(self.response(job), job['input_snapshot']['input'])['nodes'][0]
        result = self.commit(job)
        record, = result['records']
        self.assertEqual((record['record_type'], record['disposition']), ('d2k', 'accepted_new'))
        revision = record['result_node_revision_id']
        node = next(node for node in self.runtime.graph(self.data_id)['nodes'] if node['knode_revision_id'] == revision)
        self.assertEqual(node['generation_origin']['origin_operation'], 'd2k')
        self.assertFalse(node['generation_origin']['is_inferred'])
        self.assertEqual(node['origin_record_id'], record['record_id'])
        self.assertEqual(node['generation_origin']['origin_record_id'], record['record_id'])
        self.assertEqual(node['direct_groundings'], [])
        self.assertEqual(node['source_data_ids'], [self.data_id])
        with connection(self.dsn) as conn:
            groundings = conn.execute('SELECT * FROM canonical_store.knowledge_data_groundings WHERE origin_record_id=%s ORDER BY view_id',
                                      (record['record_id'],)).fetchall()
            inputs = conn.execute('''SELECT
                (SELECT count(*) FROM compiler_runtime.k_input_information WHERE execution_id=%s) AS i,
                (SELECT count(*) FROM compiler_runtime.k_input_node_revisions WHERE execution_id=%s) AS k''',
                (job['execution_id'], job['execution_id'])).fetchone()
        self.assertEqual(inputs, {'i': 0, 'k': 0})
        self.assertEqual(len(groundings), len(saved['packet']['views']))
        actual = {row['evidence']['view_id']: row['evidence'] for row in groundings}
        self.assertEqual(actual, {citation['view_id']: citation for citation in expected['direct_evidence']})
        for row in groundings:
            self.assertEqual(UUID(str(row['grounding_id'])).version, 7)
            locator = row['evidence']['locator']
            self.assertEqual(self.raw[locator['byte_start']:locator['byte_end']], row['evidence']['quote'].encode('utf-8'))
            self.assertEqual(row['data_id'], self.data_id)
            self.assertNotIn('information_id', row['evidence'])
        old_revision = self.row('SELECT * FROM canonical_store.knowledge_node_revisions WHERE knode_revision_id=%s', (revision,))
        _, _, new_grant = self.grant()
        again = self.prepare(new_grant)
        verdicts = pure.decisions(again['input_snapshot']['input'])
        verdicts['decisions'][0].update(verdict='reused', equivalent_revision_id=revision)
        reused = self.commit(again, decisions=verdicts)
        self.assertEqual(reused['records'][0]['result_node_revision_id'], revision)
        self.assertEqual(reused['records'][0]['disposition'], 'reused')
        self.assertEqual(self.row('SELECT * FROM canonical_store.knowledge_node_revisions WHERE knode_revision_id=%s', (revision,)), old_revision)
        self.assertEqual((self.counts()['nodes'], self.counts()['information'], self.counts()['information_groundings'], self.counts()['d2i']), (1, 0, 0, 0))
        self.assertEqual(self.counts()['data_groundings'], len(groundings) * 2)

    def test_intervening_unapproved_duplicate_is_held_while_independent_and_same_batch_results_commit(self):
        _, saved, grant = self.grant()
        # This K does not exist when the user confirms the catalog. A separate
        # ordinary I2K execution creates it before the old grant is prepared.
        fixture = selection_fixtures.SelectionRuntimeTests('runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        incoming = fixture.response(general=True)
        incoming['nodes'] = [node for node in incoming['nodes'] if node['kind'] == 'proposition'][:1]
        incoming['nodes'][0]['semantic_payload']['subject'] = 'Intervening general K ' + self.data_id
        fixture.reviews(incoming, fixture.packet)
        outside = fixture.commit(fixture.prepare(), incoming)['records'][0]
        outside_id = outside['result_node_revision_id']
        historical = self.row('SELECT * FROM canonical_store.knowledge_node_revisions WHERE knode_revision_id=%s', (outside_id,))
        self.assertNotIn(outside_id, [node['knode_revision_id'] for node in saved['manifest']['existing_knowledge']])
        job = self.prepare(grant)
        self.assertNotIn(outside_id, [node['knode_revision_id'] for node in job['input_snapshot']['existing_nodes']])
        response = self.response(job)
        independent = deepcopy(response['nodes'][0]); independent['candidate_key'] = 'independent'
        duplicate = deepcopy(independent)
        duplicate.update(candidate_key='outside', identity_scope='general', source_data_id=None,
                         semantic_payload=deepcopy(incoming['nodes'][0]['semantic_payload']),
                         statement=incoming['nodes'][0]['statement'])
        same_batch = deepcopy(independent); same_batch['candidate_key'] = 'same-batch'
        dependent = deepcopy(duplicate); dependent['candidate_key'] = 'dependent'
        response['nodes'] = [duplicate, independent, same_batch, dependent]
        keys = [node['candidate_key'] for node in response['nodes']]
        for review in response['reviews']:
            review['candidate_keys'] = list(keys)
        decisions = pure.decisions(job['input_snapshot']['input'], keys=keys)
        decisions['decisions'][-1].update(verdict='reused', equivalent_candidate_key='outside')
        result = self.commit(job, response=response, decisions=decisions)
        self.assertEqual(result['state'], 'needs_human')
        records = dict(zip(keys, result['records']))
        self.assertEqual(records['outside']['disposition'], 'needs_human')
        self.assertIn('d2k_catalog_confirmation_required', records['outside']['reason_codes'])
        self.assertIsNone(records['outside']['result_node_revision_id'])
        self.assertEqual(records['dependent']['disposition'], 'needs_human')
        self.assertIn('reuse_target_unresolved', records['dependent']['reason_codes'])
        self.assertEqual(records['independent']['disposition'], 'accepted_new')
        self.assertEqual(records['same-batch']['disposition'], 'reused')
        self.assertEqual(records['same-batch']['result_node_revision_id'], records['independent']['result_node_revision_id'])
        for key in ('outside', 'dependent'):
            self.assertEqual(self.row('SELECT count(*) AS n FROM canonical_store.knowledge_data_groundings WHERE origin_record_id=%s',
                                      (records[key]['record_id'],))['n'], 0)
        self.assertEqual(self.row('SELECT * FROM canonical_store.knowledge_node_revisions WHERE knode_revision_id=%s', (outside_id,)), historical)
        self.assertEqual(self.source.preparation(saved['preparation_id']), saved)
        self.assertEqual((self.counts()['information'], self.counts()['d2i'], self.counts()['nodes']), (0, 0, 1))
        # Confirmation of a new manifest is the only way to include outside K.
        _, fresh, _ = self.grant()
        self.assertIn(outside_id, [node['knode_revision_id'] for node in fresh['manifest']['existing_knowledge']])

    def test_recorded_D2I_failure_is_preserved_and_D2K_does_not_repair_it(self):
        compiler = CompilerRuntime(self.dsn, self.root)
        self.reject(lambda: compiler.compile_code(self.data_id), 'invalid_code_source')
        failed = self.row("SELECT execution_id FROM compiler_runtime.operation_executions WHERE operation='d2i' AND data_id=%s", (self.data_id,))
        execution = str(failed['execution_id'])
        before = deepcopy(compiler.show(execution, include_input=True))
        _, saved, grant = self.grant(failure_execution_id=execution)
        self.assertEqual(saved['manifest']['failure']['kind'], 'recorded_d2i_failure')
        self.assertEqual(saved['manifest']['failure']['execution_id'], execution)
        self.assertEqual(self.commit(self.prepare(grant))['state'], 'completed')
        self.assertEqual(compiler.show(execution, include_input=True), before)
        self.assertEqual(before['state'], 'failed')
        self.assertEqual((self.counts()['information'], self.counts()['d2i']), (0, 1))
        self.assertEqual(self.store.read(self.data_id, len(self.raw)), self.raw)

    def test_explicit_D2K_links_an_I2K_information_error_without_resuming_or_repairing_it(self):
        from palimpsest import multi_source_i2k as multi
        from palimpsest.knowledge_requests import generation_request, validation_request
        compiler=CompilerRuntime(self.dsn,self.root)
        parsed=compiler.compile_markdown(self.data_id)
        packet=multi.combine_packets([compiler.prepare_input(parsed['execution_id'])])
        job=self.runtime.prepare('i2k',self.data_id,self.repo.allocate_id(),packet,selection=True,source_review=False)
        ids=packet['target_information_ids']
        output={'nodes':[],'complete':False,'coverage_notes':['Synthetic reported gap, not a measured parser omission.'],
            'source_requests':[{'data_id':self.data_id,'information_ids':[ids[0]],'page_numbers':[],
                'question':'Synthetic user-visible Information error; source needs manual review.'}],
            'reviews':[{'information_id':value,'disposition':'needs_review','candidate_keys':[],
                'reason':'Synthetic gap report.'} for value in ids]}
        def receipt(value,phase):
            context=self.runtime.validation_context(job['execution_id']) if phase=='validator' else None
            prompt,schema=(generation_request(job['input_snapshot'],[]) if phase=='generator' else validation_request(context,[]))
            return {'profile':job['profile']['model'],'actual_delivery':True,'provider_ref':'synthetic-'+str(uuid4()),
                'input_sha256':job['input_digest'] if phase=='generator' else context['validation_context_sha'],
                'output_sha256':digest(value),'prompt_sha256':sha256(prompt.encode()).hexdigest(),'schema_sha256':digest(schema),
                'delivered_information_ids':ids,'image_attachments':[],'test_only':True}
        with no_d2i(no_source_reads=True):
            self.runtime.stage(job['execution_id'],output,receipt(output,'generator'))
            validation={'complete':False,'decisions':[],'reviews':[{'information_id':value,'verdict':'needs_review',
                'reason_codes':['d2i_information_error'],'reason':'Synthetic missing Information report.'} for value in ids]}
            self.runtime.decide(job['execution_id'],validation,receipt(validation,'validator'))
        before=self.runtime.show(job['execution_id'])
        _,saved,grant=self.grant(failure_execution_id=job['execution_id'])
        self.assertEqual(saved['manifest']['failure']['kind'],'recorded_information_error')
        self.assertTrue(saved['manifest']['failure']['information_errors'])
        self.assertEqual(self.commit(self.prepare(grant))['state'],'completed')
        self.assertEqual(self.runtime.show(job['execution_id']),before)
        self.assertTrue(before['information_errors']['requires_user_review'])
        self.assertEqual(before['state'],'needs_human')
        self.assertEqual(self.counts()['d2i'],1)

    def test_failed_atomic_commit_preserves_proposal_and_retries_original_records(self):
        _, _, grant = self.grant()
        job = self.prepare(grant)
        self.stage(job)
        before = deepcopy(self.runtime.show(job['execution_id']))
        verdicts = pure.decisions(job['input_snapshot']['input'])
        receipt = self.receipt(job, verdicts, 'validator')
        def interrupt(phase):
            if phase == 'after_knowledge_effect':
                raise RuntimeError('Synthetic D2K atomic interruption')
        with no_d2i(no_source_reads=True), self.assertRaisesRegex(RuntimeError, 'Synthetic D2K atomic'):
            self.runtime.decide(job['execution_id'], verdicts, receipt, checkpoint=interrupt)
        self.assertEqual(self.runtime.show(job['execution_id']), before)
        self.assertEqual((self.counts()['nodes'], self.counts()['data_groundings'], self.counts()['candidates']), (0, 0, 1))
        with no_d2i(no_source_reads=True):
            result = self.runtime.decide(job['execution_id'], verdicts, receipt)
        self.assertEqual(result['state'], 'completed')
        self.assertEqual([record['record_id'] for record in result['records']], [record['record_id'] for record in before['records']])
        self.assertEqual(self.counts()['candidates'], 0)
        self.assertEqual(self.row('SELECT count(*) AS n FROM compiler_runtime.k_outbox WHERE record_id=%s',
                                 (result['records'][0]['record_id'],))['n'], 1)

    def test_prepare_call_verifies_original_and_exports_expected_delivery_without_calling_model(self):
        _, _, grant = self.grant()
        job = self.prepare(grant)
        before = deepcopy(self.runtime.show(job['execution_id']))
        with no_d2i():
            exported = self.source.prepare_call(job['execution_id'], 'generator', self.base / 'call')
        request_file = Path(exported['request_file'])
        request = json.loads(request_file.read_text(encoding='utf-8'))
        self.assertFalse(exported['actual_delivery'])
        self.assertEqual(request['delivered_data_view_ids'], d2k.check_input(job['input_snapshot']['input']))
        self.assertEqual(request['delivered_knowledge_revision_ids'], [node['knode_revision_id'] for node in job['input_snapshot']['existing_nodes']])
        self.assertEqual((request['prompt'], request['schema']),
                         (d2k.generation(job['input_snapshot'], []), d2k.generation_schema(job['input_snapshot']['input'])))
        self.assertTrue(self.source.prepare_call(job['execution_id'], 'generator', self.base / 'call')['replayed'])
        self.assertEqual(self.runtime.show(job['execution_id']), before)
        artifact = self.root / self.repo.get_data(self.data_id)['artifact_path']
        old_mode = artifact.stat().st_mode
        try:
            artifact.chmod(0o600)
            artifact.write_bytes(bytes([self.raw[0] ^ 1]) + self.raw[1:])
            self.reject(lambda: self.source.prepare_call(job['execution_id'], 'generator', self.base / 'corrupt-call'), 'integrity_conflict')
        finally:
            artifact.write_bytes(self.raw)
            artifact.chmod(old_mode)
        self.assertEqual(self.runtime.show(job['execution_id']), before)
        self.assertEqual(self.runtime.show(job['execution_id'])['model_calls'], [])

    def test_current_and_pinned_version_scope_and_delivery_ids_are_bound_to_grant(self):
        versions = DataVersions(self.dsn, self.store)
        series = versions.create('Synthetic D2K version context')['series_id']
        first = versions.append(series, self.data_id, self.repo.allocate_id(), None)
        _, _, grant = self.grant(data_version_ids=[first['version_id']])
        job = self.prepare(grant)
        response = self.response(job)
        receipt = self.receipt(job, response, 'generator')
        receipt.pop('delivered_data_version_ids')
        self.reject(lambda: self.runtime.stage(job['execution_id'], response, receipt), 'data_version_delivery_mismatch')
        self.stage(job)
        other = self.base / 'later.md'
        other.write_text(f'Later original bytes {uuid4()}\n', encoding='utf-8')
        later_data = self.data.import_file(other, media_type='text/markdown')['data_id']
        versions.append(series, later_data, self.repo.allocate_id(), first['version_id'])
        before = deepcopy(self.runtime.show(job['execution_id']))
        verdicts = pure.decisions(job['input_snapshot']['input'])
        self.reject(lambda: self.runtime.decide(job['execution_id'], verdicts, self.receipt(job, verdicts, 'validator')),
                    'data_version_head_changed')
        self.assertEqual(self.runtime.show(job['execution_id']), before)
        self.assertEqual(self.counts()['data_groundings'], 0)
        _, _, pinned = self.grant(data_version_ids=[first['version_id']], data_version_mode='pinned')
        historical = self.prepare(pinned)
        self.assertEqual(historical['input_snapshot']['data_version_mode'], 'pinned')
        self.assertEqual(self.commit(historical)['state'], 'completed')

    def test_D_only_and_I_origin_premises_form_K2K_without_fake_direct_evidence(self):
        _, _, grant = self.grant()
        direct = self.commit(self.prepare(grant))['records'][0]['result_node_revision_id']
        fixture = selection_fixtures.SelectionRuntimeTests('runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        source = fixture.commit(fixture.prepare(), fixture.response())
        information_premise = source['records'][1]['result_node_revision_id']
        premises = [direct, information_premise]
        packet = self.runtime.inference_input(self.data_id, premises)
        self.assertEqual(packet['nodes'][0]['direct_groundings'], [])
        self.assertTrue(packet['nodes'][0]['direct_data_groundings'])
        self.assertTrue(packet['nodes'][1]['direct_groundings'])
        job = self.runtime.prepare('k2k', self.data_id, self.repo.allocate_id(), packet)
        response = inference_fixtures.K2KRuntimeTests.response(self, job, name='mixed_D_and_I')
        self.runtime.stage(job['execution_id'], response, self.receipt(job, response, 'generator'))
        verdicts = inference_fixtures.K2KRuntimeTests.decisions(response)
        result = self.runtime.decide(job['execution_id'], verdicts, self.receipt(job, verdicts, 'validator'))
        revision = result['records'][0]['result_node_revision_id']
        node = next(node for node in self.runtime.graph(self.data_id)['nodes'] if node['knode_revision_id'] == revision)
        self.assertEqual(node['generation_origin']['origin_operation'], 'k2k')
        self.assertTrue(node['generation_origin']['is_inferred'])
        self.assertEqual(node['generation_origin']['premise_revision_ids'], premises)
        self.assertEqual(node['direct_groundings'], [])
        self.assertEqual(node['direct_data_groundings'], [])
        self.assertTrue(node['transitive_source_refs'])
        self.assertTrue(node['transitive_data_refs'])
        self.assertEqual({row['node_revision_id'] for row in node['transitive_data_refs']}, {direct})
        self.assertEqual((self.counts()['information'], self.counts()['d2i']), (0, 0))


if __name__ == '__main__':
    unittest.main()
