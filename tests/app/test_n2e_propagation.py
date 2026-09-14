"""Modern relation review through the real queue; synthetic model exchanges only.

Root provisions palimpsest_n2e_checks. These tests never migrate/reset a database
or invoke a provider. Bounded test loops fail rather than declare convergence.
"""

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import unittest
from uuid import uuid4

from palimpsest.canonical_store import connection
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.knowledge_runtime import MODEL
from palimpsest.n2e_relations import PROFILE, REVIEW_KEY
from palimpsest.propagation_runtime import PropagationRuntime
import test_n2e_runtime as relations


@unittest.skipUnless(os.environ.get('PALIMPSEST_TEST_DSN'), 'Requires dedicated N2E PostgreSQL')
class N2EPropagationTests(unittest.TestCase):
    def setUp(self):
        self.f = relations.N2ERuntimeTests('runTest')
        self.addCleanup(self.f.doCleanups)
        self.f.setUp()  # Also asserts the exact disposable database name.
        self.dsn = self.f.dsn
        self.worker = PropagationRuntime(self.dsn, self.f.fixture.root / 'artifacts',
                                         self.f.fixture.root / 'n2e-propagation')
        self.calls = []

    def edge_history(self):
        with connection(self.dsn) as conn:
            return conn.execute('SELECT to_jsonb(r) AS body FROM canonical_store.knowledge_edge_revisions r '
                'WHERE kedge_revision_id=%s', (self.revision,)).fetchone()['body']

    def start(self, predicate='supports', *, source=2, target=0):
        self.revision = self.f.created(predicate, source=source, target=target)
        self.original = self.edge_history()
        with self.f.fixture.connection() as conn:
            self.f.seed[source] = self.f.fixture.revise(conn, self.f.seed[source], value=7)
        self.f.refresh()
        self.current_nodes = deepcopy(self.f.nodes)
        self.assertEqual(self.f.projected(self.revision)['applicability'], 'pending')
        self.run = self.worker.prepare(self.f.repo.allocate_id(), [str(self.f.seed[source]['record_id'])],
            allowed_data_ids=[self.f.data_id], wiki_ids=[], discovery=False)
        self.worker.queue.start(self.run['run_id'], self.run['request_fingerprint'], 'synthetic-n2e-test-user')
        return self.model_request()

    def model_request(self):
        for _ in range(30):
            action = self.worker.next(self.run['run_id'])
            if action['action'] == 'model_request':
                task = self.worker._task(action['task_id'])
                self.assertEqual(task['kind'], 'edge_revalidate')
                job = self.worker.knowledge.show(action['execution_id'])
                snapshot = job['input_snapshot']
                self.assertEqual(snapshot['n2e_policy'], PROFILE)
                self.assertEqual(job['profile']['n2e_policy'], PROFILE)
                self.assertNotIn('revalidation_target', snapshot)
                target = snapshot['edge_review_target']
                self.assertEqual(target['target_revision_id'], self.revision)
                self.assertEqual(target['prior_applicable'], True)
                self.assertEqual(target['prior_pair'], [self.original['from_knode_revision_id'],
                                                       self.original['to_knode_revision_id']])
                by_id = {node['knode_id']: node for node in self.f.nodes}
                expected_pair = [by_id[target['target'][key]]['knode_revision_id']
                                 for key in ('from_knode_id', 'to_knode_id')]
                self.assertEqual([target['from_revision_id'], target['to_revision_id']], expected_pair)
                return action
            self.assertEqual(action['action'], 'task_completed', action)
        self.fail('No mandatory relation request reached; this is a test failure, not successful cutoff.')

    def exchange(self, action, applicable):
        request = json.loads(Path(action['request_file']).read_text(encoding='utf-8'))
        job = self.worker.knowledge.show(action['execution_id'])
        target = job['input_snapshot']['edge_review_target']
        self.assertEqual(request['delivered_edge_review_target_sha256'], target['target_sha256'])
        self.assertEqual(request['delivered_knowledge_revision_ids'],
                         [node['knode_revision_id'] for node in job['input_snapshot']['input']['nodes']])
        if action['phase'] == 'generator':
            response = {'edges': [], 'complete': True, 'applicability': {'applicable': applicable,
                'reason_codes': ['synthetic_fixture'], 'reason': 'Synthetic exact-pair assessment.'}}
        else:
            context = self.worker.knowledge.validation_context(action['execution_id'])
            self.assertEqual([item['candidate_key'] for item in context['candidates']], [REVIEW_KEY])
            response = self.f.decisions(context, applicable=applicable)
        receipt = {'profile': deepcopy(MODEL), 'actual_delivery': True, 'test_only': True,
            'provider_ref': 'synthetic-n2e-propagation-' + str(uuid4()), 'usage': {}, 'image_attachments': [],
            'input_sha256': request['input_sha256'], 'output_sha256': digest(response),
            'prompt_sha256': sha256(request['prompt'].encode()).hexdigest(), 'schema_sha256': digest(request['schema']),
            **{key: deepcopy(value) for key, value in request.items() if key.startswith('delivered_')}}
        return {'response': response, 'receipt': receipt}

    def finish(self, action, *, applicable):
        for _ in range(40):
            if action['action'] == 'model_request':
                self.calls.append((action['execution_id'], action['phase']))
                action = self.worker.accept(action['task_id'], action['lease_token'], action['phase'],
                                            self.exchange(action, applicable))
            elif action['action'] == 'task_completed':
                action = self.worker.next(self.run['run_id'])
            else:
                break
        self.assertEqual(action['action'], 'completed', action)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual([phase for _, phase in self.calls], ['generator', 'validator'])
        run = self.worker.queue.show(self.run['run_id'])
        self.assertTrue(all(task['state'] == 'done' for task in run['tasks']))
        self.assertEqual({task['kind'] for task in run['tasks']}, {'outbox', 'edge_revalidate'})
        self.assertEqual(sum(task['kind'] == 'edge_revalidate' for task in run['tasks']), 1)
        self.assertEqual(self.edge_history(), self.original)
        result = self.worker.knowledge.show(self.calls[-1][0])
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(result['records'][0]['disposition'], 'no_material_delta')
        self.assertEqual(result['records'][0]['result_edge_revision_id'], self.revision)
        record_id = result['records'][0]['record_id']
        with connection(self.dsn) as conn:
            events = conn.execute('SELECT event_type,payload FROM compiler_runtime.propagation_events '
                'WHERE run_id=%s', (self.run['run_id'],)).fetchall()
            outbox = conn.execute('SELECT operation FROM compiler_runtime.k_outbox WHERE record_id=%s',
                                  (record_id,)).fetchall()
            assessments = conn.execute('SELECT * FROM canonical_store.knowledge_edge_applicability_events '
                'WHERE semantic_kedge_revision_id=%s ORDER BY event_order', (self.revision,)).fetchall()
        dispatched = [event['payload'] for event in events if event['event_type'] == 'dependencies_enumerated'
                      and event['payload']['record_id'] == record_id]
        self.assertEqual(len(dispatched), 1)
        self.assertEqual(dispatched[0]['material'], not applicable)
        self.assertEqual(dispatched[0]['applicability_change'], not applicable)
        self.assertFalse(dispatched[0]['semantic_revision_change'])
        self.assertEqual([row['operation'] for row in outbox], ['k2k'])
        self.assertEqual([row['applicable'] for row in assessments], [True, applicable])
        self.assertEqual(str(assessments[-1]['origin_record_id']), record_id)
        self.assertGreater(assessments[-1]['event_order'], self.run['initial_watermark'])
        completed = [event['payload'] for event in events if event['event_type'] == 'completed']
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0]['dependency_coverage'],
                         {'undispatched_outbox': 0, 'undispatched_supports': 0, 'enumeration_complete': True})
        return result

    def test_same_relation_rebases_exact_endpoints_and_dispatches_only_maintenance(self):
        request = self.start()
        self.finish(request, applicable=True)
        edge = self.f.projected(self.revision)
        self.assertEqual(edge['applicability'], 'applicable')
        self.assertEqual(edge['from_knode_revision_id'], self.original['from_knode_revision_id'])
        self.assertEqual(edge['effective_from_revision_id'], self.f.nodes[2]['knode_revision_id'])
        self.assertEqual(len(self.f.runtime.graph(self.f.data_id)['edge_revisions']), 1)

    def test_negative_contradiction_dispatches_material_effect_without_changing_nodes(self):
        request = self.start('contradicts', source=0, target=1)
        self.finish(request, applicable=False)
        self.assertEqual(self.f.projected(self.revision)['applicability'], 'not_applicable')
        graph = self.f.runtime.graph(self.f.data_id)
        self.assertEqual(graph['usable_edges'], [])
        self.assertFalse(any(node.get('epistemic_projection') == 'contested' for node in graph['nodes']))
        self.f.refresh()
        self.assertEqual(self.f.nodes, self.current_nodes)
        self.assertEqual(len(graph['node_revisions']), 4)

    def test_old_lease_cannot_stage_review_and_resume_reuses_the_exact_execution(self):
        request = self.start()
        exchange = self.exchange(request, True)
        self.worker.queue.control(self.run['run_id'], 'pause', 'synthetic-n2e-test-user', 'Synthetic pause before stage.')
        self.worker.queue.control(self.run['run_id'], 'resume', 'synthetic-n2e-test-user', 'Synthetic resume with a fresh epoch.')
        with self.assertRaises(PalimpsestError) as caught:
            self.worker.accept(request['task_id'], request['lease_token'], 'generator', exchange)
        self.assertEqual(caught.exception.code, 'propagation_claim_lost')
        unchanged = self.worker.knowledge.show(request['execution_id'])
        self.assertEqual(unchanged['state'], 'prepared')
        self.assertEqual(unchanged['records'], [])
        self.assertIsNone(unchanged['generator_receipt'])
        replacement = self.model_request()
        self.assertEqual(replacement['execution_id'], request['execution_id'])
        self.assertNotEqual(replacement['lease_token'], request['lease_token'])
        self.finish(replacement, applicable=True)


if __name__ == '__main__':
    unittest.main()
