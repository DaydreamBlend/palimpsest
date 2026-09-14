"""Version-bound I2K/N2E/K2K in isolated PG with synthetic model receipts only."""

from copy import deepcopy
from hashlib import sha256
import os
import sys
import unittest
from uuid import uuid4

from palimpsest.canonical_store import connection
from palimpsest.data_versions import DataVersions
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest import k2k
from palimpsest.knowledge_requests import (generation_request, validation_request,
                                          edge_generation_request, edge_validation_request)
from palimpsest.service import DataService
import test_selection_runtime as selection_fixtures
import test_k2k_runtime as inference_fixtures


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires explicitly provisioned Linux PostgreSQL fixture database palimpsest')
class VersionedKnowledgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with connection(os.environ['PALIMPSEST_TEST_DSN']) as conn:
            if conn.execute('SELECT current_database() AS name').fetchone()['name'] != 'palimpsest':
                raise RuntimeError('Versioned Knowledge fixtures require the isolated database palimpsest')
            if conn.execute("SELECT to_regclass('compiler_runtime.k_execution_data_versions') AS name").fetchone()['name'] is None:
                raise RuntimeError('Provision version migration 0013 in the isolated fixture first')

    def setUp(self):
        self.fixture = selection_fixtures.SelectionRuntimeTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.helper, self.runtime, self.dsn = self.fixture.helper, self.fixture.runtime, self.fixture.dsn
        self.data_id, self.packet = self.fixture.data_id, self.fixture.packet
        self.versions = DataVersions(self.dsn, self.helper.fixture.runtime.store)
        self.series = self.versions.create('Synthetic maintained source')['series_id']
        self.v1 = self.versions.append(self.series, self.data_id, self.uid(), None, title='Original synthetic source')
        changed = self.helper.fixture.base / 'changed-source.txt'
        changed.write_text(f'Synthetic changed source {uuid4()}\n', encoding='utf-8')
        self.changed_data = DataService(self.helper.repo, self.helper.fixture.runtime.store).import_file(changed)['data_id']

    def uid(self):
        return self.helper.repo.allocate_id()

    def prepare_i2k(self, *, versions=None, mode='current', request=None):
        return self.runtime.prepare('i2k', self.data_id, request or self.uid(), self.packet,
            selection=True, source_review=False,
            data_version_ids=versions or [self.v1['version_id']], data_version_mode=mode)

    def prepare_k2k(self, premises, *, versions=None, mode='current'):
        packet = self.runtime.inference_input(self.data_id, premises)
        return self.runtime.prepare('k2k', self.data_id, self.uid(), packet,
            data_version_ids=versions or [self.v1['version_id']], data_version_mode=mode)

    def inference_response(self, job, name='inferred'):
        # The established K2K fixture creates only a labelled synthetic proposal.
        return inference_fixtures.K2KRuntimeTests.response(self, job, name=name)

    def receipt(self, job, response, phase, *, context=None):
        current = self.runtime.show(job['execution_id'])
        snapshot, operation = current['input_snapshot'], current['operation']
        attachments = ([{key: asset[key] for key in ('sha256', 'byte_size')}
                        for asset in snapshot['input']['media_assets']] if operation == 'i2k' else [])
        if phase == 'validator' and context is None:
            context = self.runtime.validation_context(job['execution_id'])
        if operation == 'i2k':
            prompt, schema = (generation_request(snapshot, attachments) if phase == 'generator'
                              else validation_request(context, attachments))
        elif operation == 'k2k':
            if phase == 'generator':
                prompt, schema = k2k.generation(snapshot, []), k2k.generation_schema(snapshot['input'])
            else:
                prompt = k2k.validation(context, [])
                schema = k2k.validation_schema([node['candidate_key'] for node in context['candidates']],
                    [node['knode_revision_id'] for node in snapshot['existing_nodes']])
        else:
            prompt, schema = (edge_generation_request(snapshot) if phase == 'generator'
                              else edge_validation_request(context))
        result = {'profile': {**current['profile']['model'], 'synthetic_receipt': True},
            'input_sha256': current['input_digest'] if phase == 'generator' else context['validation_context_sha'],
            'output_sha256': digest(response), 'prompt_sha256': sha256(prompt.encode('utf-8')).hexdigest(),
            'schema_sha256': digest(schema), 'provider_ref': 'synthetic-version-no-model-' + str(uuid4()),
            'actual_delivery': True, 'original_pdf_delivered': False, 'image_attachments': attachments,
            'delivered_data_version_ids': [version['version_id'] for version in snapshot['data_versions']],
            'usage': {}, 'test_only': True}
        if operation == 'i2k':
            result['delivered_information_ids'] = snapshot['input']['target_information_ids']
        else:
            result['delivered_knowledge_revision_ids'] = [node['knode_revision_id'] for node in snapshot['input']['nodes']]
        return result

    def stage(self, job, response):
        return self.runtime.stage(job['execution_id'], response, self.receipt(job, response, 'generator'))

    def commit(self, job, response, decisions):
        self.stage(job, response)
        return self.runtime.decide(job['execution_id'], decisions, self.receipt(job, decisions, 'validator'))

    def source_knowledge(self, *, version=None, mode='current', decisions=None):
        job = self.prepare_i2k(versions=[version or self.v1['version_id']], mode=mode)
        response = self.fixture.response()
        return job, self.commit(job, response, decisions or self.fixture.decisions(response))

    def move_head(self, *, return_to_a=False):
        second = self.versions.append(self.series, self.changed_data, self.uid(), self.v1['version_id'], message='Synthetic B')
        if return_to_a:
            return self.versions.append(self.series, self.data_id, self.uid(), second['version_id'], message='Exact A again')
        return second

    def links(self, execution):
        with connection(self.dsn) as conn:
            return [str(row['version_id']) for row in conn.execute('''SELECT version_id
                FROM compiler_runtime.k_execution_data_versions WHERE execution_id=%s ORDER BY version_id''',
                (execution,)).fetchall()]

    def source_counts(self):
        with connection(self.dsn) as conn:
            return conn.execute('''SELECT
                (SELECT count(*) FROM canonical_store.information WHERE data_id=%s) AS information,
                (SELECT count(*) FROM compiler_runtime.operation_executions WHERE data_id=%s AND operation='d2i') AS d2i''',
                (self.data_id, self.data_id)).fetchone()

    def assert_code(self, code, call):
        with self.assertRaises(PalimpsestError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_versioned_i2k_to_k2k_retains_exact_origin_context_and_typed_links(self):
        source_job, source = self.source_knowledge()
        premises = [record['result_node_revision_id'] for record in source['records']]
        graph = self.runtime.graph(data_version_id=self.v1['version_id'])
        self.assertEqual(graph['selected_data_version']['version_id'], self.v1['version_id'])
        self.assertTrue(all(node['origin_data_versions'][0]['version_id'] == self.v1['version_id'] for node in graph['nodes']))
        self.assertTrue(all(node['source_version_status'] == 'current' for node in graph['nodes']))
        inference = self.prepare_k2k(premises)
        response = self.inference_response(inference)
        result = self.commit(inference, response, inference_fixtures.K2KRuntimeTests.decisions(response))
        node = next(node for node in self.runtime.graph(self.data_id)['nodes']
                    if node['knode_revision_id'] == result['records'][0]['result_node_revision_id'])
        self.assertEqual(node['generation_origin']['origin_operation'], 'k2k')
        self.assertEqual(node['generation_origin']['premise_revision_ids'], premises)
        self.assertEqual(node['direct_groundings'], [])
        self.assertEqual([row['version_id'] for row in node['origin_data_versions']], [self.v1['version_id']])
        self.assertEqual(self.links(source_job['execution_id']), [self.v1['version_id']])
        self.assertEqual(self.links(inference['execution_id']), [self.v1['version_id']])

    def test_head_change_rejects_current_prepare_stage_and_commit_but_pinned_old_version_works(self):
        awaiting_stage = self.prepare_i2k()
        awaiting_decision = self.prepare_i2k()
        response = self.fixture.response()
        self.stage(awaiting_decision, response)
        before_state = self.runtime.graph(self.data_id)['state_version']
        newer = self.move_head()
        self.assertEqual(self.runtime.graph(self.data_id)['state_version'], before_state)
        self.assert_code('data_version_head_changed', self.prepare_i2k)
        self.assert_code('data_version_head_changed', lambda: self.stage(awaiting_stage, response))
        decisions = self.fixture.decisions(response)
        self.assert_code('data_version_head_changed', lambda: self.runtime.decide(awaiting_decision['execution_id'], decisions,
            self.receipt(awaiting_decision, decisions, 'validator')))
        self.assertEqual(self.runtime.show(awaiting_stage['execution_id'])['records'], [])
        self.assertIsNone(self.runtime.show(awaiting_decision['execution_id'])['validator_receipt'])
        self.assertEqual(self.runtime.graph(self.data_id)['nodes'], [])
        _, historical = self.source_knowledge(mode='pinned')
        self.assertEqual(historical['state'], 'completed')
        graph = self.runtime.graph(data_version_id=self.v1['version_id'])
        self.assertTrue(all(node['source_version_status'] == 'historical' for node in graph['nodes']))
        self.assertTrue(all(node['source_version_current_heads'][0]['version_id'] == newer['version_id'] for node in graph['nodes']))

    def test_foreign_version_data_cannot_replace_the_actual_source(self):
        other = self.versions.create('Different source series')['series_id']
        foreign = self.versions.append(other, self.changed_data, self.uid(), None)
        self.assert_code('data_version_source_mismatch', lambda: self.prepare_i2k(versions=[foreign['version_id']]))
        self.assert_code('data_version_source_mismatch', lambda: self.prepare_i2k(
            versions=[self.v1['version_id'], foreign['version_id']]))

    def test_a_b_a_reuses_exact_k_revision_and_information_with_new_support_context(self):
        _, first = self.source_knowledge()
        original = self.runtime.graph(self.data_id)
        source_before = self.source_counts()
        third = self.move_head(return_to_a=True)
        response = self.fixture.response()
        decisions = self.fixture.decisions(response)
        for decision, record in zip(decisions['decisions'], first['records']):
            decision.update(verdict='reused', equivalent_revision_id=record['result_node_revision_id'])
        _, reused = self.source_knowledge(version=third['version_id'], decisions=decisions)
        self.assertEqual([record['disposition'] for record in reused['records']], ['reused', 'reused'])
        after = self.runtime.graph(data_version_id=third['version_id'])
        self.assertEqual(after['node_revisions'], original['node_revisions'])
        self.assertEqual(after['groundings'], original['groundings'])
        self.assertEqual(self.source_counts(), source_before)
        for node in after['nodes']:
            self.assertEqual([version['version_id'] for version in node['origin_data_versions']], [self.v1['version_id']])
            self.assertEqual({version for support in node['data_version_supports'] for version in support['version_ids']},
                             {self.v1['version_id'], third['version_id']})
            self.assertEqual(node['source_version_status'], 'current')

    def test_accepted_request_and_receipt_replay_survive_a_later_head_change(self):
        job = self.prepare_i2k()
        response = self.fixture.response()
        self.stage(job, response)
        decisions = self.fixture.decisions(response)
        receipt = self.receipt(job, decisions, 'validator')
        first = self.runtime.decide(job['execution_id'], decisions, receipt)
        before = self.runtime.graph(self.data_id)
        self.move_head()
        replay = self.runtime.decide(job['execution_id'], decisions, receipt)
        self.assertEqual(replay['execution_id'], first['execution_id'])
        self.assertEqual(replay['state'], 'completed')
        prepared_again = self.prepare_i2k(request=job['request_id'])
        self.assertTrue(prepared_again['replayed'])
        self.assertEqual(prepared_again['input_snapshot'], job['input_snapshot'])
        after = self.runtime.graph(self.data_id)
        self.assertEqual(after['node_revisions'], before['node_revisions'])
        self.assertEqual(after['groundings'], before['groundings'])

    def test_missing_version_delivery_or_wrong_schema_cannot_stage_a_candidate(self):
        job = self.prepare_i2k()
        response = self.fixture.response()
        proper = self.receipt(job, response, 'generator')
        missing = deepcopy(proper)
        missing.pop('delivered_data_version_ids')
        self.assert_code('data_version_delivery_mismatch', lambda: self.runtime.stage(job['execution_id'], response, missing))
        forged = {**proper, 'schema_sha256': '0' * 64}
        self.assert_code('knowledge_prompt_delivery_mismatch', lambda: self.runtime.stage(job['execution_id'], response, forged))
        self.assertEqual(self.runtime.show(job['execution_id'])['state'], 'prepared')
        self.assertEqual(self.runtime.show(job['execution_id'])['records'], [])

    def test_tracked_premises_require_explicit_k2k_version_context(self):
        _, source = self.source_knowledge()
        refs = [record['result_node_revision_id'] for record in source['records']]
        packet = self.runtime.inference_input(self.data_id, refs)
        self.assert_code('data_version_context_required', lambda: self.runtime.prepare('k2k', self.data_id, self.uid(), packet))

    def test_versioned_n2e_binds_exact_nodes_and_version_in_its_delivery_and_sql_links(self):
        _, source = self.source_knowledge()
        nodes = self.runtime.graph(self.data_id)['nodes']
        job = self.runtime.prepare('n2e', self.data_id, self.uid(), {'schema_version': 'n2e-input-v1', 'nodes': nodes},
                                   data_version_ids=[self.v1['version_id']])
        observation = next(node for node in nodes if node['kind'] == 'observation')
        proposition = next(node for node in nodes if node['kind'] == 'proposition')
        response = {'edges': [{'candidate_key': 'version_bound_relation',
            'from_revision_id': observation['knode_revision_id'], 'to_revision_id': proposition['knode_revision_id'],
            'predicate': 'supports', 'qualifiers': {'scope': 'Synthetic fixture only', 'conditions': []},
            'rationale': 'Synthetic independently judged relation; no semantic model was called.'}], 'complete': True}
        receipt = self.receipt(job, response, 'generator')
        missing = deepcopy(receipt)
        missing.pop('delivered_knowledge_revision_ids')
        self.assert_code('knowledge_premise_delivery_mismatch', lambda: self.runtime.stage(job['execution_id'], response, missing))
        stage_context = self.runtime.stage(job['execution_id'], response, receipt)
        reloaded_context = self.runtime.validation_context(job['execution_id'])
        self.assertEqual(digest(stage_context), digest(reloaded_context))
        stage_request = edge_validation_request(stage_context)
        self.assertTrue(stage_request == edge_validation_request(reloaded_context),
                        'N2E validator prompt/schema must survive JSONB object-key reordering')

        def reverse_object_keys(value):
            if isinstance(value, dict):
                return {key: reverse_object_keys(value[key]) for key in reversed(value)}
            if isinstance(value, list):
                return [reverse_object_keys(item) for item in value]
            return value

        self.assertTrue(stage_request == edge_validation_request(reverse_object_keys(stage_context)),
                        'Recursive object-key order must not change the validator request')
        self.assertTrue(edge_generation_request(job['input_snapshot']) ==
                        edge_generation_request(reverse_object_keys(job['input_snapshot'])),
                        'Recursive object-key order must not change the generator request')
        reordered_array = deepcopy(stage_context)
        reordered_array['input_snapshot']['input']['nodes'].reverse()
        self.assertNotEqual(digest(stage_context), digest(reordered_array))
        self.assertFalse(stage_request == edge_validation_request(reordered_array),
                         'Canonical object ordering must preserve meaningful array order')
        decisions = {'decisions': [{'candidate_key': 'version_bound_relation', 'verdict': 'accepted',
            'reason_codes': ['synthetic_fixture'], 'reason': 'Synthetic exact endpoint validation.'}], 'complete': True}
        result = self.runtime.decide(job['execution_id'], decisions,
            self.receipt(job, decisions, 'validator', context=stage_context))
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(self.links(job['execution_id']), [self.v1['version_id']])
        edge = self.runtime.graph(self.data_id)['edges'][0]
        self.assertEqual(edge['from_knode_revision_id'], observation['knode_revision_id'])
        self.assertEqual(edge['to_knode_revision_id'], proposition['knode_revision_id'])


if __name__ == '__main__':
    unittest.main()
