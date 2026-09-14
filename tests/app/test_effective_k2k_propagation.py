"""Actual scoped worker with effective Edge premises and synthetic exchanges.

Root provisions the dedicated effective K2K DB. No provider, Wiki generation,
database migration/reset or source reparse occurs in these propagation tests.
Test loop bounds fail; they never count as successful propagation completion.
"""

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import unittest
from uuid import uuid4

from palimpsest.canonical_store import connection
from palimpsest.i2k import digest
from palimpsest.k2k_effective import PROFILE, INPUT_SCHEMA
from palimpsest.propagation_runtime import PropagationRuntime
import test_effective_k2k_runtime as fixtures


@unittest.skipUnless(os.environ.get('PALIMPSEST_TEST_DSN'), 'Requires dedicated effective K2K PostgreSQL')
class EffectiveK2KPropagationTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.EffectiveK2KRuntimeTests('runTest')
        self.addCleanup(self.f.doCleanups)
        self.f.setUp()  # Asserts palimpsest_effective_k2k_checks and the new table.
        self.dsn, self.runtime = self.f.dsn, self.f.runtime
        self.node, _ = self.f.created()
        self.node_revision = self.node['knode_revision_id']
        self.origin = deepcopy(self.node['generation_origin'])
        self.node_history = self.f.f.revision_rows(self.node['knode_id'])
        self.edge_history = self.read_edge_history()
        self.worker = PropagationRuntime(self.dsn, self.f.f.root, self.f.f.base / 'effective-propagation')
        self.generated, self.calls, self.blocked = {}, [], []

    def read_edge_history(self):
        with connection(self.dsn) as conn:
            return conn.execute('SELECT to_jsonb(r) AS body FROM canonical_store.knowledge_edge_revisions r '
                'WHERE kedge_revision_id=%s', (self.f.edge,)).fetchone()['body']

    def events(self, event_type):
        with connection(self.dsn) as conn:
            return conn.execute('SELECT task_id,payload FROM compiler_runtime.propagation_events '
                'WHERE run_id=%s AND event_type=%s ORDER BY created_at,event_id',
                (self.run['run_id'], event_type)).fetchall()

    def latest_edge_record(self):
        with connection(self.dsn) as conn:
            return str(conn.execute('SELECT origin_record_id FROM canonical_store.knowledge_edge_applicability_events '
                'WHERE semantic_kedge_revision_id=%s ORDER BY event_order DESC LIMIT 1',
                (self.f.edge,)).fetchone()['origin_record_id'])

    def start(self, record_id):
        self.run = self.worker.prepare(self.f.repo.allocate_id(), [record_id],
            allowed_data_ids=[self.f.data_id], wiki_ids=[], discovery=False)
        self.assertEqual(self.run['policy']['effective_k2k'], PROFILE)
        self.worker.queue.start(self.run['run_id'], self.run['request_fingerprint'], 'synthetic-effective-worker-user')

    def next_request(self):
        for _ in range(80):
            action = self.worker.next(self.run['run_id'])
            if action['action'] == 'model_request':
                return action
            if action['action'] == 'blocked':
                self.blocked.append(self.worker._task(action['task_id']))
            else:
                self.assertEqual(action['action'], 'task_completed', action)
        self.fail('Small fixture did not reach a model request; no success cutoff is allowed.')

    def exchange(self, action):
        job = self.worker.knowledge.show(action['execution_id'])
        request = json.loads(Path(action['request_file']).read_text(encoding='utf-8'))
        snapshot, operation = job['input_snapshot'], job['operation']
        task = self.worker._task(action['task_id'])
        self.assertEqual(request['delivered_knowledge_revision_ids'],
                         [node['knode_revision_id'] for node in snapshot['input']['nodes']])
        if operation == 'k2k':
            self.assertEqual(task['kind'], 'node_revalidate')
            self.assertEqual(snapshot['input']['schema_version'], INPUT_SCHEMA)
            self.assertEqual(snapshot['revision_target']['expected_revision_id'], self.node_revision)
            refs = [edge['effective_edge_ref'] for edge in snapshot['input']['effective_edges']]
            self.assertEqual(request['delivered_effective_edge_refs'], refs)
            self.assertEqual(request['delivered_effective_input_sha256'], snapshot['input']['input_sha256'])
            self.assertEqual(snapshot['revalidation_target']['effective_edge_refs'], refs)
            self.assertEqual(request['delivered_revalidation_target_sha256'],
                             snapshot['revalidation_target']['target_sha256'])
            if action['phase'] == 'generator':
                response = self.f.response(job, existing=self.f.f.node(self.node_revision))
                self.generated[job['execution_id']] = deepcopy(response)
            else:
                response = self.f.decisions(job, self.generated[job['execution_id']], material=False)
                for decision in response['decisions']:
                    decision.update(verdict='reused', equivalent_candidate_key=None,
                        equivalent_revision_id=self.node_revision, novel_conclusion=False)
        else:
            self.assertEqual(operation, 'n2e')
            self.assertEqual(task['kind'], 'edge_revalidate')
            target = snapshot['edge_review_target']
            self.assertEqual(target['target_revision_id'], self.f.edge)
            self.assertEqual(request['delivered_edge_review_target_sha256'], target['target_sha256'])
            assessment = {'applicable': True, 'reason_codes': ['synthetic_fixture'],
                          'reason': 'Synthetic explicit same-relation assessment.'}
            if action['phase'] == 'generator':
                response = {'edges': [], 'complete': True, 'applicability': assessment}
            else:
                context = self.worker.knowledge.validation_context(job['execution_id'])
                self.assertEqual(len(context['candidates']), 1)
                candidate = context['candidates'][0]
                self.assertEqual(candidate['role'], 'target_assessment')
                response = {'complete': True, 'applicability': {**assessment, 'confirmed': True}, 'decisions': [{
                    'candidate_key': candidate['candidate_key'], 'verdict': 'accepted',
                    'comparison_base_revision_id': candidate['comparison_base_revision_id'], 'material_change': None,
                    'relation_valid': True, 'scope_compatible': True, 'reason_codes': ['synthetic_fixture'],
                    'reason': 'Synthetic independent exact-pair judgment; no model quality claim.'}]}
        receipt = {'profile': deepcopy(job['profile']['model']), 'actual_delivery': True, 'test_only': True,
            'provider_ref': 'synthetic-effective-worker-' + str(uuid4()), 'usage': {}, 'image_attachments': [],
            'input_sha256': request['input_sha256'], 'output_sha256': digest(response),
            'prompt_sha256': sha256(request['prompt'].encode()).hexdigest(), 'schema_sha256': digest(request['schema']),
            **{key: deepcopy(value) for key, value in request.items() if key.startswith('delivered_')}}
        self.calls.append({'operation': operation, 'phase': action['phase'], 'execution_id': job['execution_id'],
                           'task_id': action['task_id']})
        return {'response': response, 'receipt': receipt}

    def drive(self, action=None):
        action = action or self.worker.next(self.run['run_id'])
        for _ in range(150):
            if action['action'] == 'model_request':
                action = self.worker.accept(action['task_id'], action['lease_token'], action['phase'], self.exchange(action))
            elif action['action'] in ('task_completed', 'blocked', 'running'):
                if action['action'] == 'blocked':
                    self.blocked.append(self.worker._task(action['task_id']))
                action = self.worker.next(self.run['run_id'])
            else:
                return action
        self.fail('Fixture did not settle; a test loop limit is never successful completion.')

    def assert_restored(self, action, *, n2e_calls=0):
        self.assertEqual(action['action'], 'completed', action)
        run = self.worker.queue.show(self.run['run_id'])
        self.assertTrue(all(task['state'] == 'done' for task in run['tasks']))
        self.assertFalse(any(task['kind'] in ('n2e', 'k2k', 'wiki_refresh') for task in run['tasks']))
        self.assertEqual(sum(call['operation'] == 'n2e' for call in self.calls), n2e_calls)
        self.assertEqual(sum(call['operation'] == 'k2k' for call in self.calls), 2)
        current = self.f.f.node(self.node_revision)
        self.assertEqual(current['current_applicability'], 'current_premises')
        self.assertEqual(current['generation_origin'], self.origin)
        self.assertNotEqual(current['current_support_record_id'], self.node['current_support_record_id'])
        self.assertEqual(self.f.f.revision_rows(self.node['knode_id']), self.node_history)
        self.assertEqual(self.read_edge_history(), self.edge_history)
        self.assertEqual(self.f.f.source_state(), self.f.f.source_before)
        execution = next(call['execution_id'] for call in self.calls if call['operation'] == 'k2k')
        result = self.worker.knowledge.show(execution)
        self.assertEqual(result['records'][0]['disposition'], 'reused')
        self.assertEqual(result['records'][0]['result_node_revision_id'], self.node_revision)
        self.assertEqual(current['current_support_record_id'], result['records'][0]['record_id'])
        completion = self.events('completed')
        self.assertEqual(len(completion), 1)
        self.assertEqual(completion[0]['payload']['dependency_coverage'],
                         {'undispatched_outbox': 0, 'undispatched_supports': 0, 'enumeration_complete': True})
        return current

    def test_endpoint_change_waits_for_relation_review_then_refreshes_same_conclusion(self):
        job = self.f.f.prepare_source(self.f.f.source_target)
        changed = self.f.f.commit(job, self.f.f.source_response([
            self.f.f.source_candidate('observation', 'observation', 'four')]))['records'][0]
        self.start(changed['record_id'])
        request = self.next_request()
        self.assertEqual(self.worker.knowledge.show(request['execution_id'])['operation'], 'n2e')
        pending = [task for task in self.blocked if task['kind'] == 'node_revalidate']
        self.assertTrue(pending, 'The exact consumer must wait while its required relation is pending.')
        self.assertTrue(all(task['error_code'] == 'propagation_dependency_waiting' for task in pending))
        self.assertEqual(self.f.f.node(self.node_revision)['current_applicability'], 'needs_revalidation')
        current = self.assert_restored(self.drive(request), n2e_calls=2)
        active_ref = current['current_effective_edge_refs'][0]['effective_edge_ref']
        self.assertEqual(active_ref['semantic_kedge_revision_id'], self.f.edge)
        self.assertEqual(active_ref['from_knode_revision_id'], changed['result_node_revision_id'])
        self.assertEqual(self.origin['effective_edge_premises'][0]['effective_edge_ref']['from_knode_revision_id'],
                         self.edge_history['from_knode_revision_id'])
        for task in pending:
            self.assertEqual(self.worker._task(task['task_id'])['state'], 'done')
        releases = self.events('retry_requested')
        self.assertTrue(any(str(event['task_id']) in {task['task_id'] for task in pending}
                            and event['payload']['actor_ref'] == 'dependency_worker' for event in releases))

    def test_same_pair_positive_basis_change_runs_nonmaterial_consumer_maintenance(self):
        self.assertEqual(self.f.create_edge(), self.f.edge)
        record_id = self.latest_edge_record()
        self.start(record_id)
        self.assert_restored(self.drive())
        dispatched = [event['payload'] for event in self.events('dependencies_enumerated')
                      if event['payload']['record_id'] == record_id]
        self.assertEqual(len(dispatched), 1)
        self.assertFalse(dispatched[0]['material'])
        self.assertFalse(dispatched[0]['semantic_revision_change'])
        self.assertFalse(dispatched[0]['applicability_change'])
        self.assertEqual([consumer['result_node_revision_id'] for consumer in dispatched[0]['effective_edge_consumers']],
                         [self.node_revision])

    def test_negative_dependency_remains_unfinished_then_existing_obligation_resumes_after_restore(self):
        negative = self.f.edge_review(False)['records'][0]
        self.start(negative['record_id'])
        stopped = self.drive()
        self.assertEqual(stopped['action'], 'needs_human')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.events('completed'), [])
        blocked = [task for task in self.worker.queue.show(self.run['run_id'])['tasks'] if task['state'] == 'blocked']
        self.assertTrue(blocked)
        self.assertTrue(all(task['kind'] == 'node_revalidate' and task['error_code'] == 'k2k_edge_premise_inapplicable'
                            for task in blocked))
        self.assertEqual(self.f.f.node(self.node_revision)['current_applicability'], 'needs_revalidation')
        self.assertEqual(self.f.f.node(self.node_revision)['generation_origin'], self.origin)
        self.f.edge_review(True)
        # An operator resumes the held run; the worker must release the same
        # retained dependency task only after checking the now-positive basis.
        self.worker.queue.control(self.run['run_id'], 'resume', 'synthetic-effective-worker-user',
                                  'The required exact relation has been independently restored.')
        current = self.assert_restored(self.drive())
        for task in blocked:
            self.assertEqual(self.worker._task(task['task_id'])['state'], 'done')
        releases = self.events('retry_requested')
        self.assertTrue(any(str(event['task_id']) in {task['task_id'] for task in blocked}
                            and event['payload']['actor_ref'] == 'dependency_worker' for event in releases))
        self.assertEqual(self.worker.queue.show(self.run['run_id'])['scope']['root_record_ids'], [negative['record_id']])
        self.assertEqual(current['current_stale_effective_edge_refs'], [])


if __name__ == '__main__':
    unittest.main()
