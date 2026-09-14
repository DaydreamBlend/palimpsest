"""Real isolated PG runtime checks with explicitly synthetic model receipts.

No LLM is called; no user paper or existing row is modified or deleted.
"""

from copy import deepcopy
import os
import unittest
from uuid import uuid4

from psycopg.types.json import Jsonb

from palimpsest.canonical_store import PostgresRepository, connection
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.knowledge_runtime import KnowledgeRuntime, MODEL

import test_source_runtime_integration as source_fixture


@unittest.skipUnless(os.environ.get('PALIMPSEST_TEST_DSN'), 'Requires explicitly provisioned PALIMPSEST_TEST_DSN')
class KnowledgeRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.dsn = os.environ['PALIMPSEST_TEST_DSN']
        self.fixture = source_fixture.SourceRuntimeIntegrationTests('runTest')
        self.fixture.dsn = self.dsn
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        result = self.fixture.runtime.materialize_source(self.fixture._prepared())
        self.packet = self.fixture.runtime.prepare_input(str(result['execution_id']))
        self.runtime = KnowledgeRuntime(self.dsn)
        self.data_id = self.fixture.data_id
        self.repo = PostgresRepository(self.dsn)
        units = self.packet['model_input']['information']
        self.text = next(unit for unit in units if unit['content'] == self.fixture.source_text)
        self.other = next(unit for unit in units if unit['content'] == self.fixture.equation)

    def error(self, code, call):
        with self.assertRaises(PalimpsestError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def prepare(self, operation='i2k', snapshot=None):
        return self.runtime.prepare(operation, self.data_id, self.repo.allocate_id(), snapshot or self.packet)

    def response(self):
        nodes = []
        for index, (kind, unit) in enumerate((('observation', self.text), ('proposition', self.other))):
            nodes.append({'candidate_key': 'claim' + str(index), 'kind': kind,
                'statement': 'Synthetic result ' + str(index), 'semantic_payload': {
                    'subject': 'Synthetic sample ' + self.data_id, 'relation': 'has test property',
                    'object': str(index), 'polarity': 'positive', 'quantifier': 'one fixture',
                    'scope': 'storage test only', 'conditions': [], 'time_range': ''},
                'evidence': [{'information_id': unit['information_id'], 'quote': unit['content'],
                              'media_sha256': None, 'source_role': 'results' if index == 0 else 'abstract'}],
                'uncertainties': []})
        return {'nodes': nodes, 'source_requests': [], 'complete': True, 'coverage_notes': ['Synthetic storage fixture.']}

    def receipt(self, input_digest, output, *, images=True):
        assets = self.packet['media_assets'] if images else []
        return {'profile': {**MODEL, 'requested_model': MODEL['model'], 'synthetic_receipt': True},
                'input_sha256': input_digest, 'output_sha256': digest(output),
                'provider_ref': 'synthetic-no-model-' + str(uuid4()), 'actual_delivery': True,
                'image_attachments': [{'sha256': image['sha256'], 'byte_size': image['byte_size']} for image in assets],
                'usage': {}, 'test_only': True}

    @staticmethod
    def decisions(response):
        return {'complete': True, 'decisions': [{'candidate_key': node['candidate_key'], 'verdict': 'accepted',
            'equivalent_candidate_key': None, 'equivalent_revision_id': None,
            'reason_codes': ['synthetic_fixture'], 'reason': 'Synthetic storage acceptance, not scientific validation.'}
            for node in response['nodes']]}

    def stage(self, job, response=None):
        response = response or self.response()
        return self.runtime.stage(job['execution_id'], response, self.receipt(job['input_digest'], response))

    def accept(self, job, response=None):
        response = response or self.response()
        context = self.stage(job, response)
        decisions = self.decisions(response)
        return self.runtime.decide(job['execution_id'], decisions,
                                   self.receipt(context['validation_context_sha'], decisions))

    def test_first_revisions_atomic_rollback_receipt_binding_and_replay(self):
        job = self.prepare()
        self.assertTrue(self.runtime.prepare('i2k', self.data_id, job['request_id'], self.packet)['replayed'])
        response = self.response()
        context = self.stage(job, response)
        staged = self.runtime.show(job['execution_id'])
        self.assertEqual({r['context_fingerprint'] for r in staged['records']}, {context['validation_context_sha']})
        decisions = self.decisions(response)
        receipt = self.receipt(context['validation_context_sha'], decisions)
        bad = {**receipt, 'input_sha256': '0' * 64}
        self.error('knowledge_provider_receipt_mismatch', lambda: self.runtime.decide(job['execution_id'], decisions, bad))
        def fail(stage):
            if stage == 'after_knowledge_effect':
                raise RuntimeError('injected K failure')
        with self.assertRaisesRegex(RuntimeError, 'injected K failure'):
            self.runtime.decide(job['execution_id'], decisions, receipt, checkpoint=fail)
        self.assertEqual(self.runtime.graph(self.data_id)['nodes'], [])
        self.assertEqual([r['disposition'] for r in self.runtime.show(job['execution_id'])['records']], ['pending', 'pending'])
        result = self.runtime.decide(job['execution_id'], decisions, receipt)
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(self.runtime.decide(job['execution_id'], decisions, receipt)['state'], 'completed')
        graph = self.runtime.graph(self.data_id)
        self.assertEqual((len(graph['nodes']), len(graph['node_revisions']), len(graph['groundings'])), (2, 2, 2))
        self.assertTrue(all(row['supersedes_revision_id'] is None for row in graph['node_revisions']))
        self.assertTrue(all(record['body'] is None for record in result['records']))

    def test_reuse_does_not_add_revision_or_duplicate_exact_grounding(self):
        first = self.accept(self.prepare())
        refs = {row['ordinal']: row['result_node_revision_id'] for row in first['records']}
        response = self.response()
        response['nodes'][0]['statement'] = 'A presentation paraphrase.'
        job = self.prepare()
        context = self.stage(job, response)
        decisions = self.decisions(response)
        for index, item in enumerate(decisions['decisions']):
            item.update(verdict='reused', equivalent_revision_id=refs[index])
        result = self.runtime.decide(job['execution_id'], decisions, self.receipt(context['validation_context_sha'], decisions))
        self.assertEqual([r['disposition'] for r in result['records']], ['reused', 'reused'])
        graph = self.runtime.graph(self.data_id)
        self.assertEqual((len(graph['nodes']), len(graph['node_revisions']), len(graph['groundings'])), (2, 2, 2))

    def test_two_prepared_readsets_cannot_commit_stale_approval(self):
        first, second = self.prepare(), self.prepare()
        response = self.response()
        context = self.stage(second, response)
        self.accept(first)
        decisions = self.decisions(response)
        self.error('knowledge_state_changed', lambda: self.runtime.decide(second['execution_id'], decisions,
            self.receipt(context['validation_context_sha'], decisions)))
        self.assertEqual(self.runtime.show(second['execution_id'])['state'], 'proposed')
        self.assertEqual(len(self.runtime.graph(self.data_id)['nodes']), 2)

    def test_undelivered_source_holds_affected_claims_and_keeps_independent_effect(self):
        job, response = self.prepare(), self.response()
        response.update(complete=False, source_requests=[{'information_ids': [self.text['information_id']],
            'question': 'Verify original numeric glyph.', 'page_numbers': [1]}])
        result = self.accept(job, response)
        self.assertEqual(result['state'], 'needs_human')
        self.assertEqual([r['disposition'] for r in result['records']], ['needs_human', 'accepted_new'])
        self.assertIsNotNone(result['records'][0]['body'])
        self.assertEqual(result['source_requests'][0]['status'], 'unavailable')
        self.assertIs(result['source_requests'][0]['receipt']['actual_delivery'], False)
        self.assertEqual(len(self.runtime.graph(self.data_id)['nodes']), 1)

    def test_image_receipt_source_metadata_and_failed_call_receipt(self):
        packet = deepcopy(self.packet)
        packet['model_input']['information'][0]['title'] = 'Forged title'
        packet['input_sha256'] = digest({key: value for key, value in packet.items() if key != 'input_sha256'})
        self.error('knowledge_input_changed', lambda: self.prepare(snapshot=packet))
        packet = deepcopy(self.packet)
        packet['model_input']['information'][0]['source_refs'][0]['page_index'] = 99
        packet['input_sha256'] = digest({key: value for key, value in packet.items() if key != 'input_sha256'})
        self.error('knowledge_input_changed', lambda: self.prepare(snapshot=packet))
        job, response = self.prepare(), self.response()
        receipt = self.receipt(job['input_digest'], response)
        receipt['image_attachments'].pop()
        self.error('knowledge_image_delivery_mismatch', lambda: self.runtime.stage(job['execution_id'], response, receipt))
        response['nodes'][0]['evidence'][0]['quote'] = 'Not actually in source'
        receipt = self.receipt(job['input_digest'], response)
        self.error('knowledge_quote_mismatch', lambda: self.runtime.stage(job['execution_id'], response, receipt))
        failure = self.runtime.record_call_failure(job['execution_id'], 'generator', receipt, 'knowledge_quote_mismatch')
        self.assertEqual(failure['state'], 'prepared')
        self.assertEqual(self.runtime.show(job['execution_id'])['records'], [])
        self.assertEqual(self.runtime.show(job['execution_id'])['model_calls'][0]['status'], 'failed')
        self.assertEqual(self.accept(job)['state'], 'completed')

    def test_n2e_db_hydration_exact_endpoints_and_reuse(self):
        self.accept(self.prepare())
        graph = self.runtime.graph(self.data_id)
        nodes = graph['nodes']
        supplied = deepcopy(nodes)
        supplied[0]['groundings'] = [{'quote': 'forged arbitrary source'}]
        job = self.prepare('n2e', {'schema_version': 'n2e-input-v1', 'nodes': supplied})
        for node in job['input_snapshot']['input']['nodes']:
            self.assertTrue(node['groundings'])
            self.assertNotIn('forged', str(node['groundings']))
        source = next(node for node in nodes if node['kind'] == 'observation')
        target = next(node for node in nodes if node['kind'] == 'proposition')
        response = {'edges': [{'candidate_key': 'support1', 'from_revision_id': source['knode_revision_id'],
            'to_revision_id': target['knode_revision_id'], 'predicate': 'supports',
            'qualifiers': {'scope': 'storage fixture', 'conditions': []}, 'rationale': 'Synthetic support.'}], 'complete': True}
        decisions = {'complete': True, 'decisions': [{'candidate_key': 'support1', 'verdict': 'accepted',
            'reason_codes': ['synthetic_fixture'], 'reason': 'Synthetic storage check.'}]}
        for repeat in range(2):
            if repeat:
                job = self.prepare('n2e', {'schema_version': 'n2e-input-v1', 'nodes': nodes})
            context = self.runtime.stage(job['execution_id'], response, self.receipt(job['input_digest'], response, images=False))
            result = self.runtime.decide(job['execution_id'], decisions,
                self.receipt(context['validation_context_sha'], decisions, images=False))
            self.assertEqual(result['records'][0]['disposition'], 'reused' if repeat else 'accepted_new')
        graph = self.runtime.graph(self.data_id)
        self.assertEqual((len(graph['edges']), len(graph['edge_revisions']), len(graph['usable_edges'])), (1, 1, 1))
        self.assertEqual(graph['edges'][0]['from_knode_revision_id'], source['knode_revision_id'])
        self.assertEqual(graph['edges'][0]['effective_to_revision_id'], target['knode_revision_id'])

        # The public first slice discovers supports; seed a prior negative
        # applicability decision directly to exercise its read/revalidation path.
        negative_job = self.prepare('n2e', {'schema_version': 'n2e-input-v1', 'nodes': nodes})
        self.runtime.stage(negative_job['execution_id'], response,
                           self.receipt(negative_job['input_digest'], response, images=False))
        record = self.runtime.show(negative_job['execution_id'])['records'][0]
        edge = graph['edges'][0]
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('''UPDATE compiler_runtime.k_compilation_records SET disposition='no_material_delta',
                result_edge_id=%s,result_edge_revision_id=%s,resolved_at=clock_timestamp() WHERE record_id=%s''',
                (edge['kedge_id'], edge['kedge_revision_id'], record['record_id']))
            conn.execute('DELETE FROM compiler_runtime.k_temporary_candidates WHERE record_id=%s', (record['record_id'],))
            conn.execute('''INSERT INTO canonical_store.knowledge_edge_applicability_events
                (kedge_id,semantic_kedge_revision_id,from_knode_revision_id,to_knode_revision_id,applicable,origin_record_id)
                VALUES (%s,%s,%s,%s,false,%s)''', (edge['kedge_id'], edge['kedge_revision_id'],
                source['knode_revision_id'], target['knode_revision_id'], record['record_id']))
            conn.execute("INSERT INTO compiler_runtime.k_outbox(record_id,operation) VALUES (%s,'k2k')", (record['record_id'],))
            conn.execute("UPDATE compiler_runtime.operation_executions SET state='completed',validator_receipt=%s WHERE execution_id=%s",
                         (Jsonb({'synthetic_sql_applicability_fixture': True}), negative_job['execution_id']))
        negative = self.runtime.graph(self.data_id)
        self.assertEqual(negative['usable_edges'], [])
        self.assertEqual(negative['edges'][0]['applicability'], 'not_applicable')

        fresh = self.prepare('n2e', {'schema_version': 'n2e-input-v1', 'nodes': nodes})
        context = self.runtime.stage(fresh['execution_id'], response, self.receipt(fresh['input_digest'], response, images=False))
        renewed = self.runtime.decide(fresh['execution_id'], decisions,
            self.receipt(context['validation_context_sha'], decisions, images=False))
        self.assertEqual(renewed['records'][0]['disposition'], 'no_material_delta')
        restored = self.runtime.graph(self.data_id)
        self.assertEqual((len(restored['edge_revisions']), len(restored['applicability_events']), len(restored['usable_edges'])), (1, 2, 1))
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM compiler_runtime.k_outbox WHERE record_id=%s AND operation=%s',
                (renewed['records'][0]['record_id'], 'k2k')).fetchone()['n'], 1)


if __name__ == '__main__':
    unittest.main()
