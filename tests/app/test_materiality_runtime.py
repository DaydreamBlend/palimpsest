"""Real PG materiality/control tests with explicitly synthetic Validator verdicts.

Numeric tolerance below belongs only to the hypothetical test judgments. The
application receives the verdicts; it implements no numeric epsilon or metric.
"""
from copy import deepcopy
from decimal import Decimal
import os
import sys
import unittest
from unittest.mock import patch

from palimpsest.canonical_store import connection
from palimpsest.propagation_runtime import PropagationRuntime
from palimpsest import revalidation
import test_knowledge_revision_integration as fixture
import test_k2k_runtime as inference
import test_revalidation_runtime as reviews


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
    'Requires the explicitly provisioned isolated PostgreSQL fixture')
class MaterialityRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.KnowledgeRevisionIntegrationTests.setUpClass()

    def setUp(self):
        self.f = fixture.KnowledgeRevisionIntegrationTests('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.dsn, self.runtime = self.f.dsn, self.f.runtime
        self.worker = PropagationRuntime(self.dsn, self.f.root, self.f.base / 'materiality-worker')
        job = self.f.prepare_inference()
        response = self.response(job, '0')
        result = self.f.commit(job, response)
        self.initial = self.f.node(result['records'][0]['result_node_revision_id'])

    def response(self, job, value, target=None):
        response = inference.K2KRuntimeTests.response(self.f, job, name='indicator', existing=target)
        candidate = response['nodes'][0]
        candidate['semantic_payload']['object'] = value
        candidate['semantic_payload']['conditions'] = ['Synthetic approximate indicator with declared fixture precision; not experimental evidence.']
        candidate['statement'] = 'Synthetic approximate indicator: ' + value
        return response

    def revise(self, target, value, material):
        job = self.f.prepare_inference(target)
        response = self.response(job, value, target)
        verdict = self.f.decisions(job, response, material=material)
        if not material:
            verdict['decisions'][0].update(verdict='reused',
                equivalent_revision_id=target['knode_revision_id'], novel_conclusion=False)
        verdict['revision_review']['reason'] = 'Synthetic independent assessment at declared fixture precision; not an application threshold.'
        result = self.f.commit(job, response, verdict)
        record = result['records'][0]
        return self.f.node(record['result_node_revision_id']), record, job

    def start(self, record, *, discovery=False):
        run = self.worker.prepare(self.f.repo.allocate_id(), [record['record_id']],
            allowed_data_ids=[self.f.data_id], wiki_ids=[], discovery=discovery)
        self.assertEqual(run['policy']['repeated_outcome'], 'observe')
        self.worker.queue.start(run['run_id'], run['request_fingerprint'], 'synthetic-test-operator')
        return run

    def drain_no_models(self, run):
        for _ in range(50):
            action = self.worker.next(run['run_id'])
            if action['action'] == 'completed': return
            self.assertEqual(action['action'], 'task_completed', action)
        self.fail('Small fixture did not finish; this bound is not a production completion cap.')

    def test_material_return_is_observed_once_and_never_blocks_dispatch(self):
        middle, _, _ = self.revise(self.initial, '1', True)
        returned, record, _ = self.revise(middle, '0', True)
        self.assertEqual(returned['content_fingerprint'], self.initial['content_fingerprint'])
        run = self.start(record)
        self.drain_no_models(run)
        saved = self.worker.queue.show(run['run_id'])
        self.assertEqual(saved['state'], 'completed')
        self.assertEqual(saved['counts']['blocked'], 0)
        observed = [e for e in saved['anomalies'] if e['event_type'] == 'semantic_return_observed']
        self.assertEqual(len(observed), 1)
        self.assertFalse(any(e['event_type'] == 'semantic_anomaly_acknowledged' for e in saved['anomalies']))
        self.assertEqual(len(self.f.revision_rows(self.initial['knode_id'])), 3)
        self.assertEqual(self.f.source_state(), self.f.source_before)

    def test_diminishing_updates_end_on_independent_nonmaterial_not_repeat_count(self):
        target = self.initial
        for value in ('0.08', '-0.04', '0.02'):
            target, record, _ = self.revise(target, value, True)
            self.assertEqual(record['disposition'], 'accepted_revision')
        before = self.f.revision_rows(target['knode_id'])
        unchanged, record, job = self.revise(target, '0.019', False)
        self.assertEqual(record['disposition'], 'reused')
        self.assertEqual(unchanged['knode_revision_id'], target['knode_revision_id'])
        self.assertEqual(self.f.revision_rows(target['knode_id']), before)
        self.assertEqual(job['input_snapshot']['revision_target']['expected_revision_id'], target['knode_revision_id'])
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM compiler_runtime.k_outbox WHERE record_id=%s',
                (record['record_id'],)).fetchone()['n'], 0)

    def test_ignored_small_changes_compare_last_accepted_base_without_drift(self):
        target = self.initial
        original_ref = target['knode_revision_id']
        for value in ('0.004', '0.008', '0.012'):
            # This criterion is only a synthetic independent review fixture.
            material = abs(Decimal(value) - Decimal(target['semantic_payload']['object'])) >= Decimal('0.01')
            target, record, job = self.revise(target, value, material)
            self.assertEqual(job['input_snapshot']['revision_target']['expected_revision_id'], original_ref)
            self.assertEqual(record['disposition'], 'accepted_revision' if value == '0.012' else 'reused')
        self.assertEqual(len(self.f.revision_rows(target['knode_id'])), 2)
        self.assertEqual(target['semantic_payload']['object'], '0.012')

    def test_discovery_equivalence_with_different_fingerprint_reuses_current_K(self):
        before = self.f.revision_rows(self.initial['knode_id'])
        job = self.f.prepare_inference()
        response = self.response(job, '0.001', self.initial)
        verdict = inference.K2KRuntimeTests.decisions(response, verdict='reused',
            equivalent=self.initial['knode_revision_id'])
        result = self.f.commit(job, response, verdict)
        record = result['records'][0]
        self.assertNotEqual(record['content_fingerprint'], self.initial['content_fingerprint'])
        self.assertEqual(record['disposition'], 'reused')
        self.assertEqual(record['result_node_revision_id'], self.initial['knode_revision_id'])
        self.assertEqual(self.f.revision_rows(self.initial['knode_id']), before)
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM compiler_runtime.k_outbox WHERE record_id=%s',
                (record['record_id'],)).fetchone()['n'], 0)

    def test_a_tiny_but_independently_material_change_is_not_suppressed(self):
        updated, record, _ = self.revise(self.initial, '0.000001', True)
        self.assertEqual(record['disposition'], 'accepted_revision')
        self.assertNotEqual(updated['knode_revision_id'], self.initial['knode_revision_id'])
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM compiler_runtime.k_outbox WHERE record_id=%s',
                (record['record_id'],)).fetchone()['n'], 2)

    def test_current_origin_support_needs_no_extra_revalidation_or_support_rotation(self):
        run = self.start(self.f.seed['records'][0])
        with connection(self.dsn) as conn, conn.transaction():
            task = self.worker.queue.enqueue(conn, run['run_id'], 'node_revalidate',
                {'target_knode_id': self.initial['knode_id'], 'enumerated_revision_id': self.initial['knode_revision_id'],
                 'input_signature': 'a' * 64}, cause_record_id=self.f.seed['records'][0]['record_id'])
        with patch.object(self.worker, '_prepare_knowledge', side_effect=AssertionError('Current origin support already proves applicability.')):
            self.drain_no_models(run)
        saved = self.worker._task(task['task_id'])
        self.assertEqual(saved['outcome']['effect'], 'covered_by_current_validated_support')
        self.assertEqual(saved['outcome']['support_record_id'], self.initial['origin_record_id'])
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM canonical_store.knowledge_current_supports WHERE node_revision_id=%s',
                (self.initial['knode_revision_id'],)).fetchone()['n'], 0)

    def test_applicability_flip_is_material_even_without_a_new_edge_revision(self):
        edge = reviews.RevalidationRuntimeTests.edge(self)
        records = []
        for applicable in (False, False):
            job = revalidation.prepare_edge(self.runtime, edge['kedge_revision_id'], self.f.repo.allocate_id())
            response = reviews.RevalidationRuntimeTests.edge_response(job, applicable)
            decision = reviews.RevalidationRuntimeTests.edge_decision(applicable)
            for phase, value in (('generator', response), ('validator', decision)):
                receipt = self.f.receipt(job, value, phase)
                receipt.update(delivered_knowledge_revision_ids=[n['knode_revision_id'] for n in job['input_snapshot']['input']['nodes']],
                    delivered_revalidation_target_sha256=job['input_snapshot']['revalidation_target']['target_sha256'])
                (self.runtime.stage if phase == 'generator' else self.runtime.decide)(job['execution_id'], value, receipt)
            records.append(self.runtime.show(job['execution_id'])['records'][0])
        self.assertEqual(records[0]['disposition'], 'no_material_delta')
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM compiler_runtime.k_outbox WHERE record_id=%s',
                (records[1]['record_id'],)).fetchone()['n'], 0)
        run = self.start(records[0], discovery=True)
        self.assertEqual(self.worker.next(run['run_id'])['action'], 'task_completed')
        tasks = self.worker.queue.show(run['run_id'])['tasks']
        self.assertTrue(any(t['kind'] == 'k2k' and t['state'] == 'pending' for t in tasks))
        with connection(self.dsn) as conn:
            event = conn.execute("""SELECT payload FROM compiler_runtime.propagation_events WHERE run_id=%s
                AND event_type='dependencies_enumerated' AND payload->>'record_id'=%s""",
                (run['run_id'], records[0]['record_id'])).fetchone()['payload']
        self.assertTrue(event['material'])
        self.assertTrue(event['applicability_change'])
        self.assertFalse(event['semantic_revision_change'])
        self.worker.queue.control(run['run_id'], 'cancel', 'synthetic-test-operator',
            'Fixture inspected the pending node-only discovery obligation; no provider was called.')
