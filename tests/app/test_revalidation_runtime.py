"""Actual isolated PG target reviews with synthetic independent model receipts.

Root provisions the DB; these tests neither migrate/reset it nor call a provider.
"""

from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

from palimpsest import revalidation
from palimpsest.canonical_store import connection
from palimpsest.errors import PalimpsestError
from palimpsest.propagation_runtime import PropagationRuntime
import test_knowledge_revision_integration as revision_fixture
import test_k2k_runtime as inference_fixture


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires the explicitly provisioned isolated Linux PostgreSQL fixture')
class RevalidationRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        revision_fixture.KnowledgeRevisionIntegrationTests.setUpClass()
        with connection(os.environ['PALIMPSEST_TEST_DSN']) as conn:
            if not conn.execute("SELECT to_regclass('canonical_store.knowledge_current_supports') AS relation").fetchone()['relation']:
                raise RuntimeError('Root must provision additive0016 before these tests')

    def setUp(self):
        self.f = revision_fixture.KnowledgeRevisionIntegrationTests('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.runtime, self.dsn = self.f.runtime, self.f.dsn

    def receipt(self, job, response, phase):
        receipt = self.f.receipt(job, response, phase)
        target = job['input_snapshot']['revalidation_target']
        receipt.update(delivered_revalidation_target_sha256=target['target_sha256'],
            delivered_knowledge_revision_ids=[n['knode_revision_id'] for n in job['input_snapshot']['input']['nodes']])
        return receipt

    def commit(self, job, response, decision, checkpoint=None):
        self.runtime.stage(job['execution_id'], response, self.receipt(job, response, 'generator'))
        return self.runtime.decide(job['execution_id'], decision,
            self.receipt(job, decision, 'validator'), checkpoint=checkpoint)

    def revise_source(self):
        job = self.f.prepare_source(self.f.source_target)
        return self.f.commit(job, self.f.source_response([self.f.source_candidate('observation', 'observation', 'four')]))

    def test_same_meaning_revalidation_restores_current_support_preserves_origin_and_stales_consumers(self):
        target, _ = self.f.inference()
        child_job = self.f.prepare_inference(premises=[target['knode_revision_id'], self.f.premises[1]])
        child = self.f.commit(child_job, inference_fixture.K2KRuntimeTests.response(self.f, child_job, name='child'))
        child_id = child['records'][0]['result_node_revision_id']
        origin = deepcopy(target['generation_origin'])
        self.revise_source()
        self.assertEqual(self.f.node(target['knode_revision_id'])['current_applicability'], 'needs_revalidation')
        job = revalidation.prepare_node(self.runtime, target['knode_revision_id'], self.f.repo.allocate_id())
        response = inference_fixture.K2KRuntimeTests.response(self.f, job, existing=target)
        result = self.commit(job, response, self.f.decisions(job, response, material=False))
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(result['records'][0]['disposition'], 'reused')
        after = self.f.node(target['knode_revision_id'])
        self.assertEqual(after['generation_origin'], origin)
        self.assertEqual(after['current_applicability'], 'current_premises')
        self.assertEqual(after['current_support_record_id'], result['records'][0]['record_id'])
        with connection(self.dsn) as conn:
            outbox = conn.execute('SELECT operation FROM compiler_runtime.k_outbox WHERE record_id=%s',
                (result['records'][0]['record_id'],)).fetchall()
            support = conn.execute('SELECT node_revision_id FROM canonical_store.knowledge_current_supports WHERE record_id=%s',
                (result['records'][0]['record_id'],)).fetchone()
        self.assertEqual(outbox, [])
        self.assertEqual(str(support['node_revision_id']), target['knode_revision_id'])
        self.assertEqual(len(self.f.revision_rows(target['knode_id'])), 1)
        child = self.f.node(child_id)
        self.assertEqual(child['current_applicability'], 'needs_revalidation')
        self.assertIn(target['knode_revision_id'], child['current_stale_premise_revision_ids'])
        next_job = revalidation.prepare_node(self.runtime, child_id, self.f.repo.allocate_id())
        response = inference_fixture.K2KRuntimeTests.response(self.f, next_job, existing=child)
        result = self.commit(next_job, response, self.f.decisions(next_job, response, material=False))
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(self.f.node(child_id)['current_applicability'], 'current_premises')
        self.assertEqual(self.f.source_state(), self.f.source_before)

    def test_material_revalidation_creates_exact_successor_and_atomic_support(self):
        target, _ = self.f.inference()
        self.revise_source()
        job = revalidation.prepare_node(self.runtime, target['knode_revision_id'], self.f.repo.allocate_id())
        response = inference_fixture.K2KRuntimeTests.response(self.f, job, name='material_successor')
        result = self.commit(job, response, self.f.decisions(job, response, material=True))
        record = result['records'][0]
        self.assertEqual(record['disposition'], 'accepted_revision')
        node = self.f.node(record['result_node_revision_id'])
        self.assertEqual(node['knode_id'], target['knode_id'])
        self.assertEqual(node['supersedes_revision_id'], target['knode_revision_id'])
        self.assertEqual(node['current_support_record_id'], record['record_id'])
        self.assertEqual(node['generation_origin']['origin_record_id'], record['record_id'])
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM compiler_runtime.k_outbox WHERE record_id=%s',
                (record['record_id'],)).fetchone()['n'], 2)

    def bound_target(self, directory='honest-scoped-reuse'):
        target, _ = self.f.inference()
        changed = self.revise_source()
        worker = PropagationRuntime(self.dsn, self.f.root, self.f.base / directory)
        run = worker.prepare(self.f.repo.allocate_id(), [changed['records'][0]['record_id']],
            allowed_data_ids=[self.f.data_id], wiki_ids=[], discovery=False)
        worker.queue.start(run['run_id'], run['request_fingerprint'], 'synthetic-test-user')
        for _ in range(20):
            action = worker.next(run['run_id'])
            if action['action'] == 'model_request':
                break
            self.assertEqual(action['action'], 'task_completed', action)
        else:
            self.fail('The mandatory target was not prepared.')
        self.assertEqual(worker._task(action['task_id'])['kind'], 'node_revalidate')
        job = self.runtime.show(action['execution_id'])
        return target, worker, run, action, job

    def test_scoped_stale_comparison_target_remains_reusable_but_never_a_premise(self):
        target, worker, run, action, job = self.bound_target()
        exact = target['knode_revision_id']
        catalog = {node['knode_revision_id']: node for node in job['input_snapshot']['existing_nodes']}
        self.assertIn(exact, catalog)
        self.assertEqual(catalog[exact]['current_applicability'], 'needs_revalidation')
        self.assertNotIn(exact, [node['knode_revision_id'] for node in job['input_snapshot']['input']['nodes']])
        with self.assertRaises(PalimpsestError) as caught:
            self.runtime.inference_input(self.f.data_id, [exact, self.f.premises[1]])
        self.assertEqual(caught.exception.code, 'k2k_premise_needs_revalidation')
        response = inference_fixture.K2KRuntimeTests.response(self.f, job, existing=target)
        validator = worker.accept(action['task_id'], action['lease_token'], 'generator',
            {'response': response, 'receipt': self.receipt(job, response, 'generator')})
        request = json.loads(Path(validator['request_file']).read_text(encoding='utf-8'))
        branches = request['schema']['properties']['decisions']['items']['anyOf']
        self.assertTrue(any(exact in branch['properties']['equivalent_revision_id'].get('enum', []) for branch in branches))
        decision = self.f.decisions(job, response, material=False)
        decision['decisions'][0].update(verdict='reused', equivalent_candidate_key=None,
            equivalent_revision_id=exact, novel_conclusion=False)
        result = worker.accept(validator['task_id'], validator['lease_token'], 'validator',
            {'response': decision, 'receipt': self.receipt(job, decision, 'validator')})
        self.assertEqual(result['action'], 'task_completed')
        reviewed = self.runtime.show(job['execution_id'])
        self.assertEqual(reviewed['records'][0]['disposition'], 'reused')
        self.assertEqual(reviewed['records'][0]['result_node_revision_id'], exact)
        self.assertEqual(self.f.node(exact)['current_applicability'], 'current_premises')
        self.assertEqual(self.f.node(exact)['generation_origin'], target['generation_origin'])
        self.assertEqual(len(self.f.revision_rows(target['knode_id'])), 1)

    def test_generator_lease_expiring_after_staged_writes_rolls_back_every_staged_effect(self):
        target, worker, run, action, job = self.bound_target('stage-end-fence')
        response = inference_fixture.K2KRuntimeTests.response(self.f, job, existing=target)
        receipt = self.receipt(job, response, 'generator')
        original_event, reached = self.runtime._event, []

        def slow_final_event(conn, current, state, error=None):
            original_event(conn, current, state, error)
            if state == 'proposed':
                reached.append(state)
                time.sleep(1.1)

        worker.queue.renew(action['task_id'], action['lease_token'], lease_seconds=1)
        with patch.object(self.runtime, '_event', side_effect=slow_final_event), self.assertRaises(PalimpsestError) as caught:
            self.runtime.stage(job['execution_id'], response, receipt,
                propagation_claim={'task_id': action['task_id'], 'lease_token': action['lease_token']})
        self.assertEqual(caught.exception.code, 'propagation_claim_lost')
        self.assertEqual(reached, ['proposed'])
        after = self.runtime.show(job['execution_id'])
        self.assertEqual(after['state'], 'prepared')
        self.assertIsNone(after['generator_receipt'])
        self.assertEqual(after['records'], [])
        self.assertEqual(after['model_calls'], [])
        self.assertTrue(all(event['state'] == 'prepared' for event in after['events']))
        self.assertEqual(self.f.node(target['knode_revision_id'])['current_revision_id'], target['knode_revision_id'])

    def test_validator_lease_expiring_after_material_effect_rolls_back_K_support_and_outbox(self):
        target, worker, run, action, job = self.bound_target('commit-end-fence')
        response = inference_fixture.K2KRuntimeTests.response(self.f, job, name='lease-material-successor')
        worker.accept(action['task_id'], action['lease_token'], 'generator',
            {'response': response, 'receipt': self.receipt(job, response, 'generator')})
        decision = self.f.decisions(job, response, material=True)
        receipt = self.receipt(job, decision, 'validator')
        staged = self.runtime.show(job['execution_id'])
        record_id = staged['records'][0]['record_id']
        before_revisions = self.f.revision_rows(target['knode_id'])
        with connection(self.dsn) as conn:
            before_version = conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton').fetchone()['version']
        reached = []

        def delay_before_commit(phase):
            if phase == 'before_knowledge_commit':
                reached.append(phase)
                time.sleep(1.1)

        worker.queue.renew(action['task_id'], action['lease_token'], lease_seconds=1)
        with self.assertRaises(PalimpsestError) as caught:
            self.runtime.decide(job['execution_id'], decision, receipt, checkpoint=delay_before_commit,
                propagation_claim={'task_id': action['task_id'], 'lease_token': action['lease_token']})
        self.assertEqual(caught.exception.code, 'propagation_claim_lost')
        self.assertEqual(reached, ['before_knowledge_commit'])
        after = self.runtime.show(job['execution_id'])
        self.assertEqual(after['state'], 'proposed')
        self.assertIsNone(after['validator_receipt'])
        self.assertEqual(after['records'][0]['disposition'], 'pending')
        self.assertIsNotNone(after['records'][0]['body'])
        self.assertEqual([call['phase'] for call in after['model_calls']], ['generator'])
        self.assertEqual(self.f.revision_rows(target['knode_id']), before_revisions)
        with connection(self.dsn) as conn:
            for table in ('compiler_runtime.k_outbox', 'compiler_runtime.k_revision_impacts',
                          'compiler_runtime.k_revision_decisions', 'compiler_runtime.k_revalidation_decisions',
                          'canonical_store.knowledge_current_supports', 'canonical_store.knowledge_derivations'):
                self.assertEqual(conn.execute(f'SELECT count(*) AS n FROM {table} WHERE record_id=%s', (record_id,)).fetchone()['n'], 0, table)
            self.assertEqual(conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton').fetchone()['version'], before_version)

    def edge(self):
        nodes = [self.f.node(ref) for ref in self.f.premises]
        job = self.runtime.prepare('n2e', self.f.data_id, self.f.repo.allocate_id(), {'schema_version': 'n2e-input-v1', 'nodes': nodes})
        raw = {'edges': [{'candidate_key': 'edge', 'predicate': 'supports',
            'from_revision_id': nodes[0]['knode_revision_id'], 'to_revision_id': nodes[1]['knode_revision_id'],
            'qualifiers': {'scope': 'fixture', 'conditions': []}, 'rationale': 'Synthetic supports fixture.'}], 'complete': True}
        self.f.stage(job, raw)
        decision = {'decisions': [{'candidate_key': 'edge', 'verdict': 'accepted',
            'reason_codes': ['synthetic'], 'reason': 'Synthetic independent relation.'}], 'complete': True}
        result = self.runtime.decide(job['execution_id'], decision, self.f.receipt(job, decision, 'validator'))
        return next(e for e in self.runtime.graph(self.f.data_id)['edges'] if e['kedge_revision_id'] == result['records'][0]['result_edge_revision_id'])

    @staticmethod
    def edge_response(job, applicable):
        target = job['input_snapshot']['revalidation_target']
        return {'edges': [{'candidate_key': 'edge', 'predicate': 'supports',
            'from_revision_id': target['from_revision_id'], 'to_revision_id': target['to_revision_id'],
            'qualifiers': deepcopy(target['target']['qualifiers']), 'rationale': 'Review only the exact existing relation.'}],
            'complete': True, 'applicability': {'applicable': applicable,
                'reason_codes': ['synthetic'], 'reason': 'Synthetic assessment, not a model result.'}}

    @staticmethod
    def edge_decision(applicable, keys=('edge',)):
        return {'decisions': [{'candidate_key': key, 'verdict': 'accepted', 'reason_codes': ['synthetic'],
            'reason': 'Independent synthetic assessment.'} for key in keys], 'complete': True,
            'applicability': {'applicable': applicable, 'confirmed': True,
                'reason_codes': ['synthetic'], 'reason': 'Independently checked applicability.'}}

    def test_edge_negative_latest_precedence_and_repeated_negative_has_no_cascade(self):
        edge = self.edge()
        before = deepcopy(edge)
        job = revalidation.prepare_edge(self.runtime, edge['kedge_revision_id'], self.f.repo.allocate_id())
        result = self.commit(job, self.edge_response(job, False), self.edge_decision(False))
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(result['records'][0]['disposition'], 'no_material_delta')
        graph = self.runtime.graph(self.f.data_id)
        current = next(e for e in graph['edges'] if e['kedge_id'] == edge['kedge_id'])
        self.assertEqual(current['applicability'], 'not_applicable')
        for key in ('kedge_revision_id', 'from_knode_revision_id', 'to_knode_revision_id'):
            self.assertEqual(current[key], before[key])
        again = revalidation.prepare_edge(self.runtime, edge['kedge_revision_id'], self.f.repo.allocate_id())
        result = self.commit(again, self.edge_response(again, False), self.edge_decision(False))
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM compiler_runtime.k_outbox WHERE record_id=%s',
                (result['records'][0]['record_id'],)).fetchone()['n'], 0)

    def test_zero_edge_review_and_missing_target_receipt_do_not_clear_obligation(self):
        edge = self.edge()
        job = revalidation.prepare_edge(self.runtime, edge['kedge_revision_id'], self.f.repo.allocate_id())
        response = self.edge_response(job, None)
        response['edges'] = []
        receipt = self.receipt(job, response, 'generator')
        receipt.pop('delivered_revalidation_target_sha256')
        with self.assertRaises(PalimpsestError) as caught:
            self.runtime.stage(job['execution_id'], response, receipt)
        self.assertEqual(caught.exception.code, 'revalidation_target_delivery_mismatch')
        result = self.commit(job, response, self.edge_decision(None, ()))
        self.assertEqual(result['state'], 'needs_human')
        self.assertFalse(result['validator_receipt']['revalidation_result']['confirmed'])
        self.assertEqual(result['records'], [])

    def test_source_nodes_cannot_be_repaired_by_invented_inference_or_d2k(self):
        with self.assertRaises(PalimpsestError) as caught:
            revalidation.prepare_node(self.runtime, self.f.premises[1], self.f.repo.allocate_id())
        self.assertEqual(caught.exception.code, 'revalidation_source_review_required')
        self.assertEqual(self.f.source_state(), self.f.source_before)
