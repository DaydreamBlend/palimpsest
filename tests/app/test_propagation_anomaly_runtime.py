"""Stored synthetic revision trajectories, actual PG dispatch/hold/acknowledgment.

No provider is called. Accepted synthetic verdicts deliberately describe a
returning outcome; they do not establish that a real LLM entered an infinite loop.
"""
import os
import sys
import unittest
from unittest.mock import patch

from palimpsest.canonical_store import connection
from palimpsest.errors import PalimpsestError
from palimpsest.propagation_runtime import PropagationRuntime
from palimpsest import revalidation
import test_knowledge_revision_integration as fixture
import test_k2k_runtime as inference
import test_revalidation_runtime as reviews


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
    'Requires the explicitly provisioned isolated PostgreSQL fixture')
class PropagationAnomalyRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.KnowledgeRevisionIntegrationTests.setUpClass()

    def setUp(self):
        self.f = fixture.KnowledgeRevisionIntegrationTests('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.dsn, self.runtime = self.f.dsn, self.f.runtime
        self.worker = PropagationRuntime(self.dsn, self.f.root, self.f.base / 'anomaly-worker')

    def revise(self, target, *, name=None, existing=None, premises=None):
        job = self.f.prepare_inference(target, premises=premises)
        response = inference.K2KRuntimeTests.response(self.f, job,
            **({'existing': existing} if existing is not None else {'name': name}))
        result = self.f.commit(job, response)
        self.assertEqual(result['records'][0]['disposition'], 'accepted_revision')
        return self.f.node(result['records'][0]['result_node_revision_id']), result['records'][0]

    def trajectory(self):
        original, _ = self.f.inference(name='original-A')
        middle, _ = self.revise(original, name='material-B')
        returned, record = self.revise(middle, existing=original)
        self.assertEqual(returned['content_fingerprint'], original['content_fingerprint'])
        self.assertNotEqual(returned['knode_revision_id'], original['knode_revision_id'])
        return original, middle, returned, record

    def start(self, record, *, worker=None):
        worker = worker or self.worker
        original_prepare = worker.queue.prepare
        def legacy_policy(identifier, scope, policy):
            # Reproduce the old frozen policy, not the corrected default.
            policy.pop('repeated_outcome', None)
            policy.pop('materiality_policy', None)
            return original_prepare(identifier, scope, policy)
        with patch.object(worker.queue, 'prepare', side_effect=legacy_policy):
            run = worker.prepare(self.f.repo.allocate_id(), [record['record_id']],
                allowed_data_ids=[self.f.data_id], wiki_ids=[], discovery=False)
        worker.queue.start(run['run_id'], run['request_fingerprint'], 'synthetic-test-operator')
        return run

    def drain(self, run, *, worker=None):
        worker = worker or self.worker
        for _ in range(40):
            action = worker.next(run['run_id'])
            if action['action'] in ('completed', 'needs_human'):
                return action
            self.assertEqual(action['action'], 'task_completed', action)
        self.fail('Small fixture failed to settle; this test bound is not a success policy.')

    def test_returning_outcome_stops_dispatch_and_requires_exact_acknowledgement(self):
        original, middle, returned, record = self.trajectory()
        before = self.f.revision_rows(original['knode_id'])
        run = self.start(record)
        held = self.worker.next(run['run_id'])
        self.assertEqual(held['action'], 'needs_human', held)
        self.assertEqual(held['reason'], 'propagation_semantic_oscillation')
        saved = self.worker.queue.show(run['run_id'])
        self.assertEqual(saved['state'], 'needs_human')
        self.assertEqual(saved['counts']['done'], 0)
        self.assertGreater(saved['counts']['pending'], 0)
        self.assertEqual(saved['counts']['blocked'], 1)
        self.assertEqual(len([e for e in saved['anomalies'] if e['event_type'] == 'semantic_anomaly']), 1)
        self.assertEqual(self.f.revision_rows(original['knode_id']), before)
        self.assertEqual(self.f.source_state(), self.f.source_before)
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM compiler_runtime.k_outbox WHERE record_id=%s',
                (record['record_id'],)).fetchone()['n'], 2)
            self.assertIsNone(conn.execute("SELECT 1 FROM compiler_runtime.propagation_events WHERE run_id=%s AND event_type='completed'",
                (run['run_id'],)).fetchone())
        replacement = PropagationRuntime(self.dsn, self.f.root, self.f.base / 'anomaly-worker')
        self.assertEqual(replacement.next(run['run_id'])['action'], 'needs_human')
        with self.assertRaises(PalimpsestError) as caught:
            replacement.queue.control(run['run_id'], 'resume', 'synthetic-test-operator', 'Resume is not anomaly acknowledgment.')
        self.assertEqual(caught.exception.code, 'propagation_anomaly_acknowledgement_required')
        with self.assertRaises(PalimpsestError):
            replacement.retry(held['task_id'], 'Missing exact diagnosis confirmation.')
        with self.assertRaises(PalimpsestError):
            replacement.retry(held['task_id'], 'Wrong diagnosis.', acknowledge_anomaly='0' * 64)
        replacement.retry(held['task_id'], 'Synthetic operator reviewed this exact returning outcome.',
            acknowledge_anomaly=held['witness_sha256'], actor_ref='synthetic-test-operator')
        # Maintenance-only must not even load the unused discovery catalog.
        with patch.object(replacement, '_nodes', side_effect=AssertionError('No discovery catalog is needed.')):
            self.assertEqual(self.drain(run, worker=replacement)['action'], 'completed')
        after = replacement.queue.show(run['run_id'])
        acknowledgments = [e for e in after['anomalies'] if e['event_type'] == 'semantic_anomaly_acknowledged']
        self.assertEqual(len(acknowledgments), 1)
        self.assertEqual(acknowledgments[0]['payload']['witness_sha256'], held['witness_sha256'])
        self.assertEqual(acknowledgments[0]['payload']['actor_ref'], 'synthetic-test-operator')
        self.assertEqual(self.f.revision_rows(original['knode_id']), before)

    def test_changed_premise_breaks_episode_and_stale_ack_never_expands_scope(self):
        original, middle, returned, record = self.trajectory()
        run = self.start(record)
        held = self.worker.next(run['run_id'])
        self.assertEqual(held['action'], 'needs_human')
        changed_job = self.f.prepare_source(self.f.source_target)
        changed = self.f.commit(changed_job,
            self.f.source_response([self.f.source_candidate('observation', 'observation', 'four')]))
        with self.assertRaises(PalimpsestError) as caught:
            self.worker.retry(held['task_id'], 'Stale premise acknowledgment must fail.',
                acknowledge_anomaly=held['witness_sha256'], actor_ref='synthetic-test-operator')
        self.assertEqual(caught.exception.code, 'propagation_anomaly_scope_changed')
        self.assertEqual(self.worker.queue.show(run['run_id'])['state'], 'needs_human')
        next_premises = [changed['records'][0]['result_node_revision_id'], self.f.premises[1]]
        new_middle, _ = self.revise(returned, name='material-C', premises=next_premises)
        next_source = self.f.prepare_source(self.f.node(next_premises[0]))
        newer = self.f.commit(next_source,
            self.f.source_response([self.f.source_candidate('observation', 'observation', 'three')]))
        different_premises = [newer['records'][0]['result_node_revision_id'], self.f.premises[1]]
        _, new_record = self.revise(new_middle, existing=original, premises=different_premises)
        # It returns to the same semantic value, but the exact source K premise changed.
        new_run = self.start(new_record)
        first = self.worker.next(new_run['run_id'])
        self.assertEqual(first['action'], 'task_completed', first)
        self.assertFalse(self.worker.queue.show(new_run['run_id'])['anomalies'])
        self.assertEqual(self.f.source_state(), self.f.source_before)

    def test_new_return_is_not_permanently_whitelisted_by_previous_acknowledgement(self):
        original, _, returned, record = self.trajectory()
        run = self.start(record)
        held = self.worker.next(run['run_id'])
        self.worker.retry(held['task_id'], 'Review first return.', acknowledge_anomaly=held['witness_sha256'])
        self.assertEqual(self.drain(run)['action'], 'completed')
        middle, _ = self.revise(returned, name='new-material-B')
        _, next_record = self.revise(middle, existing=original)
        next_run = self.start(next_record)
        again = self.worker.next(next_run['run_id'])
        self.assertEqual(again['action'], 'needs_human', again)
        self.assertNotEqual(again['witness_sha256'], held['witness_sha256'])

    def test_retrying_an_unrelated_hold_cannot_bypass_the_run_anomaly(self):
        _, _, _, record = self.trajectory()
        run = self.start(record)
        with connection(self.dsn) as conn, conn.transaction():
            unrelated = self.worker.queue.enqueue(conn, run['run_id'], 'n2e',
                {'synthetic_unrelated_hold': True}, cause_record_id=record['record_id'])
            # A separate synthetic operational hold; no invented model verdict or K effect.
            conn.execute("""UPDATE compiler_runtime.propagation_tasks SET state='blocked',
                error_code='knowledge_needs_human' WHERE task_id=%s""", (unrelated['task_id'],))
        held = self.worker.next(run['run_id'])
        self.assertEqual(held['action'], 'needs_human')
        with self.assertRaises(PalimpsestError) as caught:
            self.worker.retry(unrelated['task_id'], 'This request did not acknowledge the semantic diagnostic.')
        self.assertEqual(caught.exception.code, 'propagation_anomaly_acknowledgement_required')
        after = self.worker.queue.show(run['run_id'])
        self.assertEqual(after['state'], 'needs_human')
        self.assertEqual(after['counts']['blocked'], 2)
        self.assertFalse(any(e['event_type'] == 'semantic_anomaly_acknowledged' for e in after['anomalies']))
        self.worker.queue.control(run['run_id'], 'cancel', 'synthetic-test-operator', 'Cancel without approving the diagnosis.')
        self.assertEqual(self.worker.next(run['run_id'])['action'], 'cancelled')
        self.assertEqual(self.worker.queue.show(run['run_id'])['counts']['blocked'], 2)

    def test_same_endpoint_applicability_return_is_held_without_rewriting_edge(self):
        target, _ = self.f.inference()
        edge = reviews.RevalidationRuntimeTests.edge(self)
        records = []
        for applicable in (False, True):
            job = revalidation.prepare_edge(self.runtime, edge['kedge_revision_id'], self.f.repo.allocate_id())
            response = reviews.RevalidationRuntimeTests.edge_response(job, applicable)
            verdict = reviews.RevalidationRuntimeTests.edge_decision(applicable)
            generator_receipt = self.f.receipt(job, response, 'generator')
            generator_receipt.update(delivered_knowledge_revision_ids=[n['knode_revision_id'] for n in job['input_snapshot']['input']['nodes']],
                delivered_revalidation_target_sha256=job['input_snapshot']['revalidation_target']['target_sha256'])
            self.runtime.stage(job['execution_id'], response, generator_receipt)
            validator_receipt = self.f.receipt(job, verdict, 'validator')
            validator_receipt.update(delivered_knowledge_revision_ids=generator_receipt['delivered_knowledge_revision_ids'],
                delivered_revalidation_target_sha256=generator_receipt['delivered_revalidation_target_sha256'])
            result = self.runtime.decide(job['execution_id'], verdict, validator_receipt)
            records.append(result['records'][0])
        run = self.start(records[-1])
        held = self.worker.next(run['run_id'])
        self.assertEqual(held['action'], 'needs_human', held)
        with connection(self.dsn) as conn:
            rows = conn.execute('SELECT * FROM canonical_store.knowledge_edge_revisions WHERE kedge_id=%s',
                (edge['kedge_id'],)).fetchall()
        self.assertEqual(len(rows), 1)
        self.worker.retry(held['task_id'], 'Reviewed this exact applicability return.',
            acknowledge_anomaly=held['witness_sha256'])
        self.assertEqual(self.drain(run)['action'], 'completed')
