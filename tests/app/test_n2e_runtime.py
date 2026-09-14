"""Modern N2E on a dedicated real PostgreSQL fixture; no provider calls."""

from copy import deepcopy
from hashlib import sha256
import os
import unittest
from uuid import uuid4

from palimpsest.canonical_store import PostgresRepository, connection
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.knowledge_runtime import KnowledgeRuntime, MODEL
from palimpsest.knowledge_requests import edge_generation_request, edge_validation_request
from palimpsest import n2e_runtime
import test_knowledge_postgres as sql_fixture


@unittest.skipUnless(os.environ.get('PALIMPSEST_TEST_DSN'), 'Requires dedicated N2E PostgreSQL')
class N2ERuntimeTests(unittest.TestCase):
    def setUp(self):
        self.dsn = os.environ['PALIMPSEST_TEST_DSN']
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT current_database() AS name').fetchone()['name'], 'palimpsest_n2e_checks')
            self.assertTrue(n2e_runtime.available(conn))
        self.fixture = sql_fixture.KnowledgePostgresTests('runTest')
        self.fixture.dsn = self.dsn
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.runtime, self.repo = KnowledgeRuntime(self.dsn), PostgresRepository(self.dsn)
        self.data_id = self.fixture.data_id
        with self.fixture.connection() as conn:
            self.seed = [self.fixture.classified_node(conn, kind=kind, value=index)
                         for index, kind in enumerate(('proposition', 'proposition', 'observation'), 1)]
        self.refresh()

    def refresh(self):
        with connection(self.dsn) as conn:
            nodes = self.runtime._nodes(conn)
        by_id = {node['knode_id']: node for node in nodes}
        self.nodes = [by_id[str(node['node_id'])] for node in self.seed]

    def prepare(self, selected=None):
        packet = {'schema_version': 'n2e-input-v1', 'nodes': deepcopy(selected or self.nodes)}
        return self.runtime.prepare('n2e', self.data_id, self.repo.allocate_id(), packet)

    def edge(self, predicate='supports', source=2, target=0, *, scope='', key='relation'):
        return {'candidate_key': key, 'from_revision_id': self.nodes[source]['knode_revision_id'],
            'to_revision_id': self.nodes[target]['knode_revision_id'], 'predicate': predicate,
            'qualifiers': {'scope': scope, 'conditions': []}, 'rationale': 'Synthetic relation fixture only.'}

    def receipt(self, job, phase, output, context=None):
        prompt, schema = edge_generation_request(job['input_snapshot']) if phase == 'generator' else edge_validation_request(context)
        receipt = {'profile': {**MODEL, 'synthetic_receipt': True}, 'actual_delivery': True,
            'provider_ref': 'synthetic-n2e-' + str(uuid4()), 'usage': {}, 'test_only': True,
            'input_sha256': job['input_digest'] if phase == 'generator' else context['validation_context_sha'],
            'output_sha256': digest(output), 'prompt_sha256': sha256(prompt.encode()).hexdigest(),
            'schema_sha256': digest(schema), 'image_attachments': [],
            'delivered_knowledge_revision_ids': [node['knode_revision_id'] for node in job['input_snapshot']['input']['nodes']]}
        if job['input_snapshot'].get('edge_review_target'):
            receipt['delivered_edge_review_target_sha256'] = job['input_snapshot']['edge_review_target']['target_sha256']
        return receipt

    def stage(self, job, edges, applicable='discovery'):
        response = {'edges': edges, 'complete': True}
        if applicable != 'discovery':
            response['applicability'] = {'applicable': applicable, 'reason_codes': ['synthetic_fixture'], 'reason': 'Synthetic explicit assessment.'}
        return self.runtime.stage(job['execution_id'], response, self.receipt(job, 'generator', response))

    def decisions(self, context, *, material=None, applicable='discovery', confirmed=True):
        decisions = {'decisions': [], 'complete': True}
        for candidate in context['candidates']:
            changed = (candidate['comparison_base_revision_id'] is None) if material is None else material
            decisions['decisions'].append({'candidate_key': candidate['candidate_key'], 'verdict': 'accepted',
                'comparison_base_revision_id': candidate['comparison_base_revision_id'],
                'material_change': None if candidate['role'] == 'target_assessment' else changed,
                'relation_valid': True, 'scope_compatible': True, 'reason_codes': ['synthetic_fixture'],
                'reason': 'Synthetic independent acceptance; no semantic model test.'})
        if applicable != 'discovery':
            decisions['applicability'] = {'applicable': applicable, 'confirmed': confirmed,
                'reason_codes': ['synthetic_fixture'], 'reason': 'Synthetic independent assessment.'}
        return decisions

    def accept(self, job, edges, *, material=None, applicable='discovery', confirmed=True):
        context = self.stage(job, edges, applicable)
        response = self.decisions(context, material=material, applicable=applicable, confirmed=confirmed)
        return self.runtime.decide(job['execution_id'], response, self.receipt(job, 'validator', response, context))

    def created(self, predicate='supports', **kwargs):
        result = self.accept(self.prepare(), [self.edge(predicate, **kwargs)])
        self.assertEqual(result['state'], 'completed')
        return result['records'][0]['result_edge_revision_id']

    def review(self, revision, prior_pair=None):
        return n2e_runtime.prepare_review(self.runtime, revision, self.repo.allocate_id(), data_id=self.data_id, prior_pair=prior_pair)

    def projected(self, revision):
        return next(edge for edge in self.runtime.graph(self.data_id)['edges'] if edge['kedge_revision_id'] == revision)

    def test_four_predicates_exact_revisions_and_symmetric_deduplication(self):
        edges = [self.edge('supports', key='s'), self.edge('qualifies', key='q'),
                 self.edge('contradicts', source=0, target=1, key='c'), self.edge('composes', source=2, target=1, key='p')]
        first = self.accept(self.prepare(), edges)
        self.assertEqual([r['disposition'] for r in first['records']], ['accepted_new'] * 4)
        self.assertTrue(all(r['body'] is None for r in first['records']))
        graph = self.runtime.graph(self.data_id)
        self.assertEqual(len(graph['usable_edges']), 4)
        self.assertEqual(len(graph['node_revisions']), 3)
        contested = [node for node in graph['nodes'] if node.get('epistemic_projection') == 'contested']
        self.assertEqual({n['knode_id'] for n in contested}, {self.nodes[0]['knode_id'], self.nodes[1]['knode_id']})
        reversed_result = self.accept(self.prepare(), [self.edge('contradicts', source=1, target=0)])
        self.assertEqual(reversed_result['records'][0]['disposition'], 'reused')
        self.assertEqual(len(self.runtime.graph(self.data_id)['edge_revisions']), 4)

    def test_material_qualifier_revision_then_paraphrase_reuses_accepted_base(self):
        initial = self.created(scope='condition A')
        changed = self.accept(self.prepare(), [self.edge(scope='condition B')], material=True)
        revision = changed['records'][0]['result_edge_revision_id']
        self.assertNotEqual(initial, revision)
        self.assertEqual(changed['records'][0]['disposition'], 'accepted_revision')
        reused = self.accept(self.prepare(), [self.edge(scope='Equivalent presentation of condition B')], material=False)
        self.assertEqual(reused['records'][0]['result_edge_revision_id'], revision)
        graph = self.runtime.graph(self.data_id)
        self.assertEqual(len(graph['edge_revisions']), 2)
        self.assertEqual(graph['edges'][0]['qualifiers']['scope'], 'condition B')
        self.assertEqual(graph['edges'][0]['supersedes_revision_id'], initial)

    def test_review_pending_unknown_and_new_confirmation_overrides_older_fence(self):
        revision = self.created('contradicts', source=0, target=1)
        pending = self.review(revision)
        self.assertEqual(self.projected(revision)['applicability'], 'pending')
        result = self.accept(pending, [], applicable=None, confirmed=False)
        self.assertEqual(result['state'], 'needs_human')
        self.assertIsNotNone(result['records'][0]['body'])
        self.assertEqual(self.runtime.graph(self.data_id)['usable_edges'], [])
        accepted = self.accept(self.review(revision), [], applicable=True)
        self.assertEqual(accepted['records'][0]['disposition'], 'no_material_delta')
        self.assertEqual(self.projected(revision)['applicability'], 'applicable')
        self.assertEqual(len(self.runtime.graph(self.data_id)['edge_revisions']), 1)

    def test_explicit_negative_and_predicate_change_are_separate_atomic_records(self):
        revision = self.created()
        result = self.accept(self.review(revision), [self.edge('qualifies')], applicable=False)
        self.assertEqual([r['disposition'] for r in result['records']], ['no_material_delta', 'accepted_new'])
        self.assertEqual(self.projected(revision)['applicability'], 'not_applicable')
        self.assertEqual({edge['predicate'] for edge in self.runtime.graph(self.data_id)['usable_edges']}, {'qualifies'})
        self.assertEqual(len(self.runtime.graph(self.data_id)['node_revisions']), 3)

    def test_predicate_change_can_retain_old_relation(self):
        revision = self.created()
        result = self.accept(self.review(revision), [self.edge('qualifies')], applicable=True)
        self.assertEqual(result['state'], 'completed')
        self.assertEqual({edge['predicate'] for edge in self.runtime.graph(self.data_id)['usable_edges']}, {'supports', 'qualifies'})

    def test_repeated_negative_is_nonmaterial_without_duplicate_outbox(self):
        revision = self.created()
        self.accept(self.review(revision), [], applicable=False)
        repeated = self.accept(self.review(revision), [], applicable=False)
        record = repeated['records'][0]
        self.assertEqual(record['disposition'], 'no_material_delta')
        self.assertFalse(repeated['relation_decisions'][0]['material_change'])
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM compiler_runtime.k_outbox WHERE record_id=%s',
                (record['record_id'],)).fetchone()['n'], 0)
        self.assertEqual(self.projected(revision)['applicability'], 'not_applicable')

    def test_endpoint_only_rebase_keeps_semantic_revision_and_original_refs(self):
        revision = self.created()
        original = self.projected(revision)['from_knode_revision_id']
        with self.fixture.connection() as conn:
            self.seed[2] = self.fixture.revise(conn, self.seed[2], value=7)
        self.refresh()
        self.assertEqual(self.projected(revision)['applicability'], 'pending')
        result = self.accept(self.review(revision, [original, self.nodes[0]['knode_revision_id']]), [], applicable=True)
        self.assertEqual(result['records'][0]['result_edge_revision_id'], revision)
        edge = self.projected(revision)
        self.assertEqual(edge['from_knode_revision_id'], original)
        self.assertEqual(edge['effective_from_revision_id'], self.nodes[2]['knode_revision_id'])
        self.assertEqual(edge['applicability'], 'applicable')

    def test_composes_cycle_is_contextual_hold_and_inactive_history_does_not_block(self):
        first = self.created('composes', source=0, target=1)
        held = self.accept(self.prepare(), [self.edge('composes', source=1, target=0)])
        self.assertEqual(held['state'], 'needs_human')
        self.assertEqual(held['records'][0]['reason_codes'], ['composes_cycle_pending'])
        self.accept(self.review(first), [], applicable=False)
        second = self.created('composes', source=1, target=0)
        self.assertNotEqual(first, second)
        self.assertEqual(len(self.runtime.graph(self.data_id)['usable_edges']), 1)

    def test_two_prepared_jobs_cannot_commit_stale_independent_validation(self):
        first, second = self.prepare(), self.prepare()
        context = self.stage(second, [self.edge('qualifies')])
        self.accept(first, [self.edge()])
        response = self.decisions(context)
        with self.assertRaises(PalimpsestError) as caught:
            self.runtime.decide(second['execution_id'], response, self.receipt(second, 'validator', response, context))
        self.assertEqual(caught.exception.code, 'knowledge_state_changed')
        self.assertEqual(self.runtime.show(second['execution_id'])['state'], 'proposed')

    def test_coupled_review_checks_positive_target_behind_its_own_pending_fence(self):
        revision = self.created('composes', source=0, target=1)
        result = self.accept(self.review(revision), [self.edge('composes', source=1, target=0)], applicable=True)
        self.assertEqual([r['disposition'] for r in result['records']], ['needs_human', 'needs_human'])
        self.assertEqual(self.projected(revision)['applicability'], 'pending')
        self.assertEqual(len(self.runtime.graph(self.data_id)['edge_revisions']), 1)

    def test_composition_batch_cycle_holds_every_proposed_composition_independent_of_order(self):
        items = [self.edge('composes', source=0, target=1, key='ab'),
                 self.edge('composes', source=1, target=2, key='bc'),
                 self.edge('composes', source=2, target=0, key='ca')]
        for ordered in (items, list(reversed(items))):
            result = self.accept(self.prepare(), ordered + [self.edge('supports', key='unrelated')])
            self.assertEqual([r['disposition'] for r in result['records'][:3]], ['needs_human'] * 3)
            self.assertEqual({edge['predicate'] for edge in self.runtime.graph(self.data_id)['usable_edges']}, {'supports'})
            for decision in result['relation_decisions'][:3]:
                self.assertEqual(decision['validation']['model_decision']['reason'],
                    'Synthetic independent acceptance; no semantic model test.')
                self.assertEqual(decision['validation']['reason_codes'], ['composes_cycle_pending'])

    def test_reactivating_cyclic_old_composition_also_holds_unrelated_replacement(self):
        revision = self.created('composes', source=0, target=1)
        self.accept(self.review(revision), [], applicable=False)
        self.created('composes', source=1, target=0)
        result = self.accept(self.review(revision), [self.edge('qualifies', source=0, target=1)], applicable=True)
        self.assertEqual([r['disposition'] for r in result['records']], ['needs_human', 'needs_human'])
        self.assertEqual({edge['predicate'] for edge in self.runtime.graph(self.data_id)['edges']}, {'composes'})
        self.assertEqual(self.projected(revision)['applicability'], 'pending')

    def test_effect_failure_rolls_back_revision_applicability_record_and_outbox(self):
        revision = self.created()
        job = self.review(revision)
        context = self.stage(job, [self.edge('qualifies')], False)
        response = self.decisions(context, applicable=False)
        receipt = self.receipt(job, 'validator', response, context)
        def fail(stage):
            if stage == 'after_knowledge_effect':
                raise RuntimeError('synthetic N2E crash')
        with self.assertRaisesRegex(RuntimeError, 'synthetic N2E crash'):
            self.runtime.decide(job['execution_id'], response, receipt, checkpoint=fail)
        state = self.runtime.show(job['execution_id'])
        self.assertEqual(state['relation_decisions'], [])
        self.assertEqual([r['disposition'] for r in state['records']], ['pending', 'pending'])
        self.assertEqual(len(self.runtime.graph(self.data_id)['edge_revisions']), 1)
        self.assertEqual(self.runtime.decide(job['execution_id'], response, receipt)['state'], 'completed')
        self.assertEqual(self.runtime.decide(job['execution_id'], response, receipt)['state'], 'completed')

    def test_review_request_retry_and_call_export_are_idempotent(self):
        revision = self.created()
        job = self.review(revision)
        replay = n2e_runtime.prepare_review(self.runtime, revision, job['request_id'], data_id=self.data_id)
        self.assertTrue(replay['replayed'])
        with self.assertRaises(PalimpsestError) as caught:
            n2e_runtime.prepare_review(self.runtime, revision, job['request_id'], data_id=self.data_id,
                prior_pair=list(reversed(job['input_snapshot']['edge_review_target']['prior_pair'])))
        self.assertEqual(caught.exception.code, 'idempotency_conflict')
        directory = self.fixture.root / 'n2e-call'
        first = n2e_runtime.prepare_call(self.runtime, job['execution_id'], 'generator', directory)
        replay = n2e_runtime.prepare_call(self.runtime, job['execution_id'], 'generator', directory)
        self.assertEqual(first['request_sha256'], replay['request_sha256'])
        self.assertTrue(replay['replayed'])


if __name__ == '__main__':
    unittest.main()
