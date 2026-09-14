"""Real isolated PostgreSQL, marked synthetic model receipts; no provider calls."""
from copy import deepcopy
from hashlib import sha256
import json
import os
import unittest
from uuid import uuid4

from palimpsest import k2k, k2k_effective_runtime as effective, revalidation, n2e_runtime
from palimpsest.canonical_store import connection
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.knowledge_requests import edge_generation_request, edge_validation_request
import test_knowledge_revision_integration as fixtures
import test_k2k_runtime as inference


@unittest.skipUnless(os.environ.get('PALIMPSEST_TEST_DSN'), 'Requires dedicated effective K2K PostgreSQL')
class EffectiveK2KRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.dsn = os.environ['PALIMPSEST_TEST_DSN']
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT current_database() AS name').fetchone()['name'], 'palimpsest_effective_k2k_checks')
            self.assertTrue(effective.available(conn))
        self.f = fixtures.KnowledgeRevisionIntegrationTests('runTest')
        self.f.dsn = self.dsn
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.runtime, self.repo, self.data_id = self.f.runtime, self.f.repo, self.f.data_id
        self.edge = self.create_edge()

    def receipt(self, job, phase, response):
        context = self.runtime.validation_context(job['execution_id']) if phase == 'validator' else None
        if job['operation'] == 'k2k':
            prompt, schema = k2k.generation_request(job['input_snapshot']) if phase == 'generator' else k2k.validation_request(context)
        else:
            prompt, schema = edge_generation_request(job['input_snapshot']) if phase == 'generator' else edge_validation_request(context)
        packet = job['input_snapshot']['input']
        result = {'profile': {**job['profile']['model'], 'synthetic_receipt': True}, 'test_only': True, 'actual_delivery': True,
            'input_sha256': job['input_digest'] if phase == 'generator' else context['validation_context_sha'],
            'output_sha256': digest(response), 'prompt_sha256': sha256(prompt.encode()).hexdigest(), 'schema_sha256': digest(schema),
            'provider_ref': 'synthetic-effective-' + str(uuid4()), 'usage': {}, 'image_attachments': [],
            'delivered_knowledge_revision_ids': [node['knode_revision_id'] for node in packet['nodes']]}
        if packet.get('effective_edges'):
            result.update(effective.delivery(packet))
        for target, field, key in [('revision_target', 'delivered_revision_target_id', 'expected_revision_id'),
                ('revalidation_target', 'delivered_revalidation_target_sha256', 'target_sha256'),
                ('edge_review_target', 'delivered_edge_review_target_sha256', 'target_sha256')]:
            if job['input_snapshot'].get(target):
                result[field] = job['input_snapshot'][target][key]
        return result

    def edge_response(self):
        nodes = [self.f.node(ref) for ref in self.f.premises]
        return {'edges': [{'candidate_key': 'support', 'from_revision_id': nodes[0]['knode_revision_id'],
            'to_revision_id': nodes[1]['knode_revision_id'], 'predicate': 'supports',
            'qualifiers': {'scope': 'Synthetic binding test', 'conditions': []}, 'rationale': 'Synthetic relation only.'}], 'complete': True}

    def create_edge(self):
        job = self.runtime.prepare('n2e', self.data_id, self.repo.allocate_id(),
            {'schema_version': 'n2e-input-v1', 'nodes': [self.f.node(ref) for ref in self.f.premises]})
        return self.commit_edge(job, self.edge_response())['records'][0]['result_edge_revision_id']

    def commit_edge(self, job, response, *, applicable=None):
        context = self.runtime.stage(job['execution_id'], response, self.receipt(job, 'generator', response))
        decisions = {'complete': True, 'decisions': [{'candidate_key': c['candidate_key'], 'verdict': 'accepted',
            'comparison_base_revision_id': c['comparison_base_revision_id'],
            'material_change': None if c['role'] == 'target_assessment' else c['comparison_base_revision_id'] is None,
            'relation_valid': True, 'scope_compatible': True, 'reason_codes': ['synthetic_fixture'],
            'reason': 'Synthetic independent relation assessment.'} for c in context['candidates']]}
        if job['input_snapshot'].get('edge_review_target'):
            decisions['applicability'] = {'applicable': applicable, 'confirmed': applicable is not None,
                'reason_codes': ['synthetic_fixture'], 'reason': 'Synthetic explicit applicability.'}
        return self.runtime.decide(job['execution_id'], decisions, self.receipt(job, 'validator', decisions))

    def edge_review(self, applicable=True):
        job = n2e_runtime.prepare_review(self.runtime, self.edge, self.repo.allocate_id(), data_id=self.data_id)
        response = {'edges': [], 'complete': True, 'applicability': {'applicable': applicable,
            'reason_codes': ['synthetic_fixture'], 'reason': 'Synthetic explicit applicability.'}}
        return self.commit_edge(job, response, applicable=applicable)

    def prepare(self):
        packet = self.runtime.inference_input(self.data_id, edge_revision_ids=[self.edge])
        return self.runtime.prepare('k2k', self.data_id, self.repo.allocate_id(), packet)

    def response(self, job, existing=None):
        result = inference.K2KRuntimeTests.response(self.f, job, name='effective_result', existing=existing)
        result['nodes'][0]['premise_edge_revision_ids'] = effective.edge_ids(job['input_snapshot']['input'])
        return result

    def stage(self, job, response):
        return self.runtime.stage(job['execution_id'], response, self.receipt(job, 'generator', response))

    def decisions(self, job, response, *, material=True):
        result = inference.K2KRuntimeTests.decisions(response)
        if job['input_snapshot'].get('revision_target'):
            result['revision_review'] = {'comparison_base_revision_id': job['input_snapshot']['revision_target']['expected_revision_id'],
                'same_identity': True, 'material_change': material, 'grounding_valid': True,
                'reason_codes': ['synthetic_fixture'], 'reason': 'Synthetic exact accepted-base comparison.'}
        return result

    def accept(self, job, response=None, *, material=True):
        response = response or self.response(job)
        self.stage(job, response)
        decisions = self.decisions(job, response, material=material)
        return self.runtime.decide(job['execution_id'], decisions, self.receipt(job, 'validator', decisions))

    def created(self):
        result = self.accept(self.prepare())
        self.assertEqual(result['state'], 'completed')
        return self.f.node(result['records'][0]['result_node_revision_id']), result

    def test_one_edge_expands_exact_endpoint_bundle_and_keeps_self_commit_current(self):
        job = self.prepare()
        packet = job['input_snapshot']['input']
        self.assertEqual(len(packet['nodes']), 2)
        self.assertEqual(len(packet['effective_edges']), 1)
        result = self.accept(job)
        record = result['records'][0]
        node = self.f.node(record['result_node_revision_id'])
        self.assertEqual(node['current_applicability'], 'current_premises')
        self.assertEqual(node['generation_origin']['origin_operation'], 'k2k')
        self.assertTrue(node['generation_origin']['is_inferred'])
        self.assertEqual(node['direct_groundings'], [])
        self.assertEqual(node['generation_origin']['effective_edge_premises'][0]['effective_edge_ref'],
            packet['effective_edges'][0]['effective_edge_ref'])
        with connection(self.dsn) as conn:
            self.assertTrue(conn.execute('SELECT compiler_runtime.current_k2k_premise(%s) AS ok', (node['knode_revision_id'],)).fetchone()['ok'])
            count = conn.execute('SELECT count(*) AS n FROM canonical_store.knowledge_derivation_edge_premises WHERE record_id=%s',
                                 (record['record_id'],)).fetchone()['n']
            self.assertEqual(count, 1)
        self.assertEqual(self.f.source_state(), self.f.source_before)

    def test_refreshed_positive_basis_invalidates_consumers_and_emits_maintenance(self):
        node, _ = self.created()
        original = deepcopy(node['generation_origin'])
        record = self.create_edge()  # Same relation reused, fresh positive basis.
        self.assertEqual(record, self.edge)
        self.assertEqual(self.f.node(node['knode_revision_id'])['current_applicability'], 'needs_revalidation')
        with connection(self.dsn) as conn:
            latest = conn.execute('''SELECT origin_record_id FROM canonical_store.knowledge_edge_applicability_events
                WHERE semantic_kedge_revision_id=%s ORDER BY event_order DESC LIMIT 1''', (self.edge,)).fetchone()['origin_record_id']
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM compiler_runtime.k_outbox WHERE record_id=%s', (latest,)).fetchone()['n'], 1)
        reviewed = revalidation.prepare_node(self.runtime, node['knode_revision_id'], self.repo.allocate_id(), data_id=self.data_id)
        result = self.accept(reviewed, self.response(reviewed, existing=node), material=False)
        self.assertEqual(result['records'][0]['disposition'], 'reused')
        self.assertEqual(result['records'][0]['result_node_revision_id'], node['knode_revision_id'])
        restored = self.f.node(node['knode_revision_id'])
        self.assertEqual(restored['current_applicability'], 'current_premises')
        self.assertEqual(restored['generation_origin'], original)
        self.assertNotEqual(restored['current_support_record_id'], node['current_support_record_id'])

    def test_pending_and_negative_never_become_valid_premises_or_erase_history(self):
        node, _ = self.created()
        pending = n2e_runtime.prepare_review(self.runtime, self.edge, self.repo.allocate_id(), data_id=self.data_id)
        with self.assertRaises(PalimpsestError) as error:
            self.prepare()
        self.assertEqual(error.exception.code, 'k2k_edge_premise_pending')
        self.assertEqual(self.f.node(node['knode_revision_id'])['current_applicability'], 'needs_revalidation')
        response = {'edges': [], 'complete': True, 'applicability': {'applicable': False,
            'reason_codes': ['synthetic_fixture'], 'reason': 'No longer justified in this synthetic case.'}}
        self.commit_edge(pending, response, applicable=False)
        with self.assertRaises(PalimpsestError) as error:
            revalidation.prepare_node(self.runtime, node['knode_revision_id'], self.repo.allocate_id(), data_id=self.data_id)
        self.assertEqual(error.exception.code, 'k2k_edge_premise_inapplicable')
        self.assertEqual(self.f.node(node['knode_revision_id'])['generation_origin'], node['generation_origin'])

    def test_basis_change_after_prepare_prevents_atomic_commit_and_preserves_proposal(self):
        job = self.prepare()
        response = self.response(job)
        self.stage(job, response)
        self.edge_review()
        decisions = self.decisions(job, response)
        with self.assertRaises(PalimpsestError) as error:
            self.runtime.decide(job['execution_id'], decisions, self.receipt(job, 'validator', decisions))
        self.assertEqual(error.exception.code, 'knowledge_state_changed')
        self.assertEqual(self.runtime.show(job['execution_id'])['records'][0]['disposition'], 'pending')

    def test_actual_edge_delivery_and_full_candidate_dependency_bundle_are_required(self):
        job = self.prepare()
        response = self.response(job)
        receipt = self.receipt(job, 'generator', response)
        receipt['delivered_effective_edge_refs'] = []
        with self.assertRaises(PalimpsestError) as error:
            self.runtime.stage(job['execution_id'], response, receipt)
        self.assertEqual(error.exception.code, 'effective_k2k_delivery_mismatch')
        missing = deepcopy(response)
        missing['nodes'][0]['premise_edge_revision_ids'] = []
        with self.assertRaises(PalimpsestError):
            self.stage(job, missing)
        self.assertEqual(self.accept(job, response)['state'], 'completed')

    def test_failure_rolls_back_edge_premises_support_and_outbox_then_replays(self):
        job = self.prepare()
        response = self.response(job)
        self.stage(job, response)
        decisions = self.decisions(job, response)
        receipt = self.receipt(job, 'validator', decisions)
        def crash(stage):
            if stage == 'after_knowledge_effect':
                raise RuntimeError('synthetic effective crash')
        with self.assertRaisesRegex(RuntimeError, 'synthetic effective crash'):
            self.runtime.decide(job['execution_id'], decisions, receipt, checkpoint=crash)
        self.assertEqual(self.runtime.show(job['execution_id'])['records'][0]['disposition'], 'pending')
        result = self.runtime.decide(job['execution_id'], decisions, receipt)
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(self.runtime.decide(job['execution_id'], decisions, receipt)['state'], 'completed')

    def test_empty_discovery_requires_actual_two_calls_and_has_no_inferred_result(self):
        job = self.prepare()
        result = self.accept(job, {'nodes': [], 'complete': True, 'coverage_notes': ['No inference in this fixture.']})
        self.assertEqual(result['state'], 'zero_output')
        self.assertEqual(result['records'], [])
        self.assertEqual(len(result['model_calls']), 2)


if __name__ == '__main__':
    unittest.main()
