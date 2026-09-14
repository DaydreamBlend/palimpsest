"""Real disposable PG queue checks; every semantic response is synthetic.

These exercise durable transport, not the dispatcher's semantic dependency
coverage or LLM quality. Root alone provisions and runs this database suite.
"""

from concurrent.futures import ThreadPoolExecutor
import os
import sys
import time
import unittest

from palimpsest.canonical_store import connection
from palimpsest.errors import PalimpsestError
from palimpsest.propagation_queue import PropagationQueue, _counts, _seconds, _transport_streak
from palimpsest import revalidation

import test_selection_runtime as selection_fixtures
import test_k2k_runtime as inference_fixtures
import test_revalidation_runtime as revalidation_fixtures


class QueueInputTests(unittest.TestCase):
    def test_nonpositive_or_noninteger_lease_is_not_an_unbounded_semantic_cap(self):
        for value in (0, -1, True, 1.5, '30', None):
            with self.subTest(value=value), self.assertRaises(PalimpsestError):
                _seconds(value)
        self.assertEqual(_seconds(180), 180)
        counts = _counts([{'state': value} for value in ('done', 'blocked', 'retry', 'leased')])
        self.assertEqual(counts['total'], 4)
        self.assertEqual(counts['done'], 1)
        self.assertEqual(sum(counts[state] for state in counts if state != 'total'), 4)

    def test_transport_streak_counts_only_consecutive_failures_in_one_phase(self):
        def event(kind, phase=None):
            return {'event_type': kind, 'payload': {'details': {'phase': phase}}}
        generator = event('retry', 'generator')
        self.assertEqual(_transport_streak([generator, generator], 'generator'), 3)
        self.assertEqual(_transport_streak([generator, generator], 'validator'), 1)
        self.assertEqual(_transport_streak([event('transport_succeeded'), generator, generator], 'generator'), 1)
        self.assertEqual(_transport_streak([event('retry_requested'), generator, generator], 'generator'), 1)
        self.assertEqual(_transport_streak([generator, event('retry_requested'), generator], 'generator'), 2)


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires the explicitly provisioned disposable Linux PostgreSQL fixture')
class PropagationQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with connection(os.environ['PALIMPSEST_TEST_DSN']) as conn:
            if conn.execute('SELECT current_database() AS name').fetchone()['name'] not in ('palimpsest', 'palimpsest_propagation_checks'):
                raise RuntimeError('Propagation tests require a disposable fixture DB')
            if conn.execute("SELECT to_regclass('compiler_runtime.propagation_runs') AS name").fetchone()['name'] is None:
                raise RuntimeError('Explicitly provision reviewed migration 0016 first')

    def setUp(self):
        self.fixture = selection_fixtures.SelectionRuntimeTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.dsn, self.data_id = self.fixture.dsn, self.fixture.data_id
        self.runtime, self.repo = self.fixture.runtime, self.fixture.helper.repo
        self.seed = self.fixture.commit(self.fixture.prepare(), self.fixture.response())
        self.root_record = self.seed['records'][0]['record_id']
        self.queue = PropagationQueue(self.dsn)
        self.scope = {'root_record_ids': [self.root_record], 'allowed_data_ids': [self.data_id], 'wiki_ids': []}
        self.policy = {'schema_version': 'synthetic-queue-fixture', 'model_calls': 'none', 'no_semantic_quality_claim': True}
        self.run = self.queue.prepare(self.repo.allocate_id(), self.scope, self.policy)

    def start(self):
        return self.queue.start(self.run['run_id'], self.run['request_fingerprint'], 'synthetic-test-user')

    def reject(self, code, callback):
        with self.assertRaises(PalimpsestError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def finish(self, task, outcome=None):
        with self.queue.transaction(task['task_id'], task['lease_token']) as (conn, current, run):
            return self.queue.finish(conn, current, task['lease_token'], outcome or {'synthetic_queue_ack': True})

    def events(self):
        with connection(self.dsn) as conn:
            return conn.execute('''SELECT event_type,payload FROM compiler_runtime.propagation_events
                WHERE run_id=%s ORDER BY created_at,event_id''', (self.run['run_id'],)).fetchall()

    def test_scope_replay_exact_confirmation_and_original_outbox_stays_immutable(self):
        self.assertEqual(self.queue.show(self.run['run_id'])['counts']['total'], 0)
        self.assertIsNone(self.queue.claim(self.run['run_id']))
        replay = self.queue.prepare(self.run['run_id'], self.scope, self.policy)
        self.assertEqual(replay['initial_watermark'], self.run['initial_watermark'])
        self.reject('propagation_request_conflict', lambda: self.queue.prepare(self.run['run_id'], self.scope, {'different': True}))
        self.reject('propagation_confirmation_changed', lambda: self.queue.start(self.run['run_id'], '0'*64, 'synthetic-test-user'))
        with connection(self.dsn) as conn:
            before = conn.execute('SELECT to_jsonb(o) AS body FROM compiler_runtime.k_outbox o WHERE record_id=%s', (self.root_record,)).fetchall()
        self.start()
        self.start()
        first = self.queue.show(self.run['run_id'])
        self.assertEqual(first['counts']['pending'], len(before))
        with connection(self.dsn) as conn, conn.transaction():
            self.queue._fence(conn)
            self.assertEqual(self.queue.harvest(conn, first), [])
            after = conn.execute('SELECT to_jsonb(o) AS body FROM compiler_runtime.k_outbox o WHERE record_id=%s', (self.root_record,)).fetchall()
        self.assertEqual(before, after)
        self.assertTrue(all(row['body']['state'] == 'pending' for row in after))

    def test_two_workers_only_one_live_claim_and_stale_token_cannot_ack(self):
        self.start()
        with ThreadPoolExecutor(max_workers=2) as workers:
            claims = list(workers.map(lambda _: self.queue.claim(self.run['run_id']), range(2)))
        self.assertEqual(sum(task is not None for task in claims), 1)
        task = next(task for task in claims if task is not None)
        self.reject('propagation_claim_lost', lambda: self.queue.block(task['task_id'], self.repo.allocate_id(), 'wrong_worker', {}))
        renewed = self.queue.renew(task['task_id'], task['lease_token'])
        self.assertEqual(renewed['attempt'], task['attempt'])
        self.assertEqual(renewed['request_id'], task['request_id'])
        self.finish(renewed)
        self.reject('propagation_claim_lost', lambda: self.finish(task))

    def test_expired_claim_is_recovered_with_new_token_and_same_request(self):
        self.start()
        task = self.queue.claim(self.run['run_id'], lease_seconds=1)
        time.sleep(1.05)
        replacement = self.queue.claim(self.run['run_id'])
        self.assertEqual(replacement['task_id'], task['task_id'])
        self.assertEqual(replacement['request_id'], task['request_id'])
        self.assertEqual(replacement['attempt'], task['attempt']+1)
        self.assertNotEqual(replacement['lease_token'], task['lease_token'])
        self.reject('propagation_claim_lost', lambda: self.finish(task))
        self.finish(replacement)
        self.assertEqual(self.queue.settle(self.run['run_id'])['status'], 'completed')

    def test_atomic_child_enrolment_and_fanin_prevent_empty_queue_false_completion(self):
        self.start()
        parent = self.queue.claim(self.run['run_id'])
        payload = {'target': 'synthetic exact dependency, no actual model result'}
        with self.queue.transaction(parent['task_id'], parent['lease_token']) as (conn, task, run):
            child = self.queue.enqueue(conn, run['run_id'], 'node_revalidate', payload,
                cause_record_id=self.root_record, outbox_id=parent['payload']['event_id'], parent_task_id=task['task_id'])
            same = self.queue.enqueue(conn, run['run_id'], 'node_revalidate', payload, parent_task_id=task['task_id'])
            self.assertEqual(child['task_id'], same['task_id'])
            self.queue.finish(conn, task, task['lease_token'], {'synthetic_children_enrolled': [child['task_id']]})
        pending = self.queue.settle(self.run['run_id'])
        self.assertEqual((pending['status'], pending['counts']['pending']), ('running', 1))
        with connection(self.dsn) as conn:
            count = conn.execute('SELECT count(*) AS n FROM compiler_runtime.propagation_task_causes WHERE task_id=%s', (child['task_id'],)).fetchone()['n']
        self.assertEqual(count, 2)
        self.finish(self.queue.claim(self.run['run_id']))
        completed = self.queue.settle(self.run['run_id'])
        self.assertEqual(completed['receipt']['task_counts']['total'], 2)
        self.assertEqual(completed['receipt']['dependency_coverage']['undispatched_outbox'], 0)
        self.assertEqual(completed['status'], 'completed')

    def test_provider_backoff_and_human_block_remain_unfinished_and_retain_attempt_history(self):
        self.start()
        task = self.queue.claim(self.run['run_id'])
        retry = self.queue.transport_retry(task['task_id'], task['lease_token'], 'synthetic_transport_failure', {'delivered': False}, 60)
        self.assertEqual(retry['state'], 'retry')
        self.assertIsNone(self.queue.claim(self.run['run_id']))
        self.assertEqual(self.queue.settle(self.run['run_id'])['status'], 'retry_wait')
        self.queue.retry(task['task_id'], 'Synthetic transport recovered; preserve earlier failure.')
        current = self.queue.claim(self.run['run_id'])
        with self.queue.transaction(current['task_id'], current['lease_token']) as (conn, owned, _):
            rotated = self.queue.rotate_request(conn, owned, 'Synthetic failed provider execution requires a fresh request.')
        self.assertNotEqual(rotated['request_id'], current['request_id'])
        self.queue.block(rotated['task_id'], rotated['lease_token'], 'synthetic_target_uncertain', {'confirmed': False})
        held = self.queue.settle(self.run['run_id'])
        self.assertEqual(held['status'], 'needs_human')
        self.assertFalse(any(event['event_type'] == 'completed' for event in self.events()))
        self.queue.retry(task['task_id'], 'Synthetic explicit retry, not a fabricated validation.')
        self.finish(self.queue.claim(self.run['run_id']))
        self.assertEqual(self.queue.settle(self.run['run_id'])['status'], 'completed')
        types = [event['event_type'] for event in self.events()]
        self.assertIn('retry', types)
        self.assertIn('blocked', types)
        self.assertIn('request_rotated', types)

    def test_pause_and_cancel_keep_work_and_reject_publication(self):
        self.start()
        task = self.queue.claim(self.run['run_id'])
        self.queue.control(self.run['run_id'], 'pause', 'synthetic-test-user', 'Pause while a provider could be outside the DB.')
        self.reject('propagation_claim_lost', lambda: self.finish(task))
        self.assertEqual(self.queue.settle(self.run['run_id'])['status'], 'paused')
        self.assertEqual(self.queue.show(self.run['run_id'])['counts']['leased'], 1)
        self.queue.control(self.run['run_id'], 'cancel', 'synthetic-test-user', 'Cancel, retaining unfinished obligations.')
        self.assertIsNone(self.queue.claim(self.run['run_id']))
        self.assertEqual(self.queue.settle(self.run['run_id'])['status'], 'cancelled')
        self.assertFalse(any(event['event_type'] == 'completed' for event in self.events()))

    def test_resume_invalidates_old_worker_even_before_its_clock_lease_expires(self):
        self.start()
        old = self.queue.claim(self.run['run_id'], lease_seconds=180)
        self.queue.control(self.run['run_id'], 'pause', 'synthetic-test-user', 'Pause the old worker.')
        resumed = self.queue.control(self.run['run_id'], 'resume', 'synthetic-test-user', 'Resume with a fresh lease epoch.')
        self.assertGreater(resumed['lease_epoch'], old['lease_epoch'])
        self.reject('propagation_claim_lost', lambda: self.finish(old))
        self.reject('propagation_claim_lost', lambda: self.queue.renew(old['task_id'], old['lease_token']))
        current = self.queue.claim(self.run['run_id'])
        self.assertEqual(current['task_id'], old['task_id'])
        self.assertEqual(current['lease_epoch'], resumed['lease_epoch'])
        self.assertEqual(current['request_id'], old['request_id'])
        self.assertNotEqual(current['lease_token'], old['lease_token'])
        self.finish(current)
        self.assertEqual(self.queue.settle(self.run['run_id'])['status'], 'completed')

    def test_three_transport_failures_are_operational_hold_and_user_retry_resets_streak(self):
        self.start()
        for number in range(1, 4):
            task = self.queue.claim(self.run['run_id'])
            result = self.queue.transport_retry(task['task_id'], task['lease_token'], 'synthetic_timeout',
                {'phase': 'generator', 'actual_delivery': None}, 1)
            if number < 3:
                self.assertEqual(result['state'], 'retry')
                time.sleep(1.05)
        self.assertEqual(result['state'], 'blocked')
        self.assertEqual(result['error_code'], 'propagation_transport_anomaly')
        self.assertEqual(self.queue.settle(self.run['run_id'])['status'], 'needs_human')
        anomaly = [event for event in self.events() if event['event_type'] == 'transport_anomaly']
        self.assertEqual(len(anomaly), 1)
        self.assertEqual(anomaly[0]['payload']['consecutive_transport_failures'], 3)
        self.assertFalse(any(event['event_type'] == 'completed' for event in self.events()))
        self.queue.retry(task['task_id'], 'Explicit recovery after inspecting the three preserved failures.')
        retried = self.queue.claim(self.run['run_id'])
        result = self.queue.transport_retry(retried['task_id'], retried['lease_token'], 'synthetic_timeout',
            {'phase': 'generator', 'actual_delivery': None}, 1)
        self.assertEqual(result['state'], 'retry')
        last = [event for event in self.events() if event['event_type'] == 'retry'][-1]
        self.assertEqual(last['payload']['details']['consecutive_transport_failures'], 1)

    def test_successful_generator_does_not_carry_failures_into_validator(self):
        self.start()
        for _ in range(2):
            task = self.queue.claim(self.run['run_id'])
            self.queue.transport_retry(task['task_id'], task['lease_token'], 'synthetic_timeout', {'phase': 'generator'}, 1)
            time.sleep(1.05)
        task = self.queue.claim(self.run['run_id'])
        self.queue.transport_succeeded(task['task_id'], task['lease_token'], 'generator')
        result = self.queue.transport_retry(task['task_id'], task['lease_token'], 'synthetic_timeout', {'phase': 'validator'}, 1)
        self.assertEqual(result['state'], 'retry')
        last = [event for event in self.events() if event['event_type'] == 'retry'][-1]
        self.assertEqual(last['payload']['details']['consecutive_transport_failures'], 1)
        self.assertFalse(any(event['event_type'] == 'transport_anomaly' for event in self.events()))

    def test_bound_late_descendant_outbox_is_enrolled_beyond_initial_watermark(self):
        self.start()
        parent = self.queue.claim(self.run['run_id'])
        with self.queue.transaction(parent['task_id'], parent['lease_token']) as (conn, owned, run):
            child = self.queue.enqueue(conn, run['run_id'], 'k2k', {'synthetic_inference': self.data_id}, parent_task_id=owned['task_id'])
            self.queue.finish(conn, owned, owned['lease_token'], {'synthetic_children_enrolled': [child['task_id']]})
        task = self.queue.claim(self.run['run_id'])
        premises = [row['result_node_revision_id'] for row in self.seed['records']]
        packet = self.runtime.inference_input(self.data_id, premises)
        claim = {'task_id': task['task_id'], 'lease_token': task['lease_token']}
        job = self.runtime.prepare('k2k', self.data_id, task['request_id'], packet, propagation_claim=claim)
        self.reject('database_error', lambda: self.finish(task, {'execution_id': job['execution_id']}))
        still_leased = next(row for row in self.queue.show(self.run['run_id'])['tasks'] if row['task_id'] == task['task_id'])
        self.assertEqual(still_leased['state'], 'leased')
        helper = inference_fixtures.K2KRuntimeTests('runTest')
        helper.runtime, helper.data_id, helper.dsn = self.runtime, self.data_id, self.dsn
        response = helper.response(job)
        self.runtime.stage(job['execution_id'], response, helper.receipt(job, response, 'generator'), propagation_claim=claim)
        decisions = helper.decisions(response)
        accepted = self.runtime.decide(job['execution_id'], decisions, helper.receipt(job, decisions, 'validator'), propagation_claim=claim)
        self.assertEqual(accepted['state'], 'completed')
        self.finish(task, {'execution_id': job['execution_id'], 'synthetic_semantic_responses': True})
        pending = self.queue.settle(self.run['run_id'])
        self.assertEqual(pending['status'], 'running')
        shown = self.queue.show(self.run['run_id'])
        descendant = next(row for row in shown['tasks'] if row['kind'] == 'outbox'
            and row['payload']['record_id'] == accepted['records'][0]['record_id'])
        self.assertEqual(descendant['state'], 'pending')
        self.assertGreater(pending['initial_watermark'], 0)
        self.finish(self.queue.claim(self.run['run_id']))
        complete = self.queue.settle(self.run['run_id'])
        self.assertEqual(complete['status'], 'completed')
        self.assertGreater(complete['receipt']['completion_watermark'], complete['receipt']['initial_watermark'])

    def test_same_meaning_support_has_separate_durable_maintenance_without_material_outbox(self):
        revalidation_fixtures.RevalidationRuntimeTests.setUpClass()
        fixture = revalidation_fixtures.RevalidationRuntimeTests('runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        target, _ = fixture.f.inference()
        fixture.revise_source()
        job = revalidation.prepare_node(fixture.runtime, target['knode_revision_id'], fixture.f.repo.allocate_id())
        response = inference_fixtures.K2KRuntimeTests.response(fixture.f, job, existing=target)
        accepted = fixture.commit(job, response, fixture.f.decisions(job, response, material=False))
        record = accepted['records'][0]
        self.assertEqual(record['disposition'], 'reused')
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM compiler_runtime.k_outbox WHERE record_id=%s',
                (record['record_id'],)).fetchone()['n'], 0)
        scope = {'root_record_ids': [record['record_id']], 'allowed_data_ids': [fixture.f.data_id], 'wiki_ids': []}
        run = self.queue.prepare(self.repo.allocate_id(), scope, self.policy)
        self.queue.start(run['run_id'], run['request_fingerprint'], 'synthetic-test-user')
        shown = self.queue.show(run['run_id'])
        self.assertEqual([task['kind'] for task in shown['tasks']], ['support_refresh'])
        task = self.queue.claim(run['run_id'])
        self.assertEqual(task['payload']['support_record_id'], record['record_id'])
        self.assertNotIn('event_id', task['payload'])
        self.assertEqual(self.queue.settle(run['run_id'])['status'], 'running')
        self.finish(task)
        completed = self.queue.settle(run['run_id'])
        self.assertEqual(completed['status'], 'completed')
        self.assertEqual(completed['receipt']['dependency_coverage']['undispatched_supports'], 0)
