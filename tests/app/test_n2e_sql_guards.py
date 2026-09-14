"""Dedicated PG guard regressions, with synthetic receipts and no provider.

Root provisions/runs these tests. Direct SQL failures roll back their isolated
transactions; normal fixture helpers preserve all prior rows and source bytes.
"""

from copy import deepcopy
from hashlib import sha256
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb

from palimpsest import k2k, n2e_runtime, revalidation
from palimpsest.canonical_store import connection
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest

import test_n2e_runtime as fixtures
import test_k2k_runtime as inference_fixtures
import test_knowledge_revision_integration as normalized_fixtures


@unittest.skipUnless(os.environ.get('PALIMPSEST_TEST_DSN'), 'Requires dedicated N2E PostgreSQL with additive0018')
class N2ESqlGuardTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.N2ERuntimeTests('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.runtime, self.dsn = self.f.runtime, self.f.dsn
        with self.f.fixture.connection() as conn:
            self.assertTrue(conn.execute("SELECT 1 FROM compiler_runtime.schema_migrations WHERE version='0019_n2e_effect_fence'").fetchone())

    def rejected_sql(self, action, text, *, immediate=False):
        with self.assertRaises(psycopg.Error) as caught:
            with self.f.fixture.connection() as conn:
                action(conn)
                if immediate:
                    self.fail('The before-insert guard accepted the invalid row.')
                conn.execute('SET CONSTRAINTS ALL IMMEDIATE')
        self.assertIn(text, caught.exception.diag.message_primary)

    def decision_insert(self, conn, job, context, *, applicable=True, material=None, confirmed=True):
        candidate = context['candidates'][0]
        record = self.runtime.show(job['execution_id'])['records'][0]
        raw = self.f.decisions(context, applicable=applicable, confirmed=confirmed)
        validation = {**raw['decisions'][0], 'material_change': material,
            'applicability_review': raw['applicability']}
        before = job['input_snapshot']['edge_review_target']['prior_applicable']
        conn.execute('''INSERT INTO compiler_runtime.n2e_review_decisions
            (record_id,execution_id,candidate_key,role,validation,action,material_change,before_applicable,after_applicable)
            VALUES (%s,%s,%s,'target_assessment',%s,'no_material_delta',%s,%s,%s)''',
            (record['record_id'], job['execution_id'], candidate['candidate_key'], Jsonb(validation),
             before is not applicable, before, applicable))

    def test_database_rejects_reserved_predicates_kind_mismatch_and_reverse_symmetric_order(self):
        logical = sorted(self.f.nodes[:2], key=lambda node: node['knode_id'])
        cases = [('supersedes', self.f.nodes[0], self.f.nodes[1], 'knowledge_edges_predicate_registry'),
            ('unsupported_relation', self.f.nodes[0], self.f.nodes[1], 'knowledge_edges_predicate_registry'),
            ('supports', self.f.nodes[0], self.f.nodes[2], 'endpoint kinds'),
            ('qualifies', self.f.nodes[0], self.f.nodes[2], 'endpoint kinds'),
            ('contradicts', logical[1], logical[0], 'symmetric logical ordering')]
        for predicate, source, target, reason in cases:
            with self.subTest(predicate=predicate):
                def insert(conn):
                    conn.execute('''INSERT INTO canonical_store.knowledge_edges
                        (kedge_id,predicate,from_knode_id,to_knode_id,identity_fingerprint,current_revision_id)
                        VALUES (uuidv7(),%s,%s,%s,%s,uuidv7())''',
                        (predicate, source['knode_id'], target['knode_id'], 'a'*64))
                # BEFORE triggers may reject an unknown predicate before its CHECK.
                expected = 'registry' if predicate in ('supersedes', 'unsupported_relation') else reason
                self.rejected_sql(insert, expected, immediate=True)
        self.assertEqual(self.runtime.graph(self.f.data_id)['edges'], [])

    def test_model_receipts_and_applicability_record_binding_are_database_requirements(self):
        job = self.f.prepare()
        context = self.f.stage(job, [self.f.edge()])
        response = self.f.decisions(context)
        receipt = self.f.receipt(job, 'validator', response, context)
        original_call = self.runtime._call

        def omit_validator(conn, current, phase, actual_receipt):
            if phase != 'validator':
                return original_call(conn, current, phase, actual_receipt)

        with patch.object(self.runtime, '_call', side_effect=omit_validator), self.assertRaises(PalimpsestError) as caught:
            self.runtime.decide(job['execution_id'], response, receipt)
        self.assertEqual(caught.exception.code, 'database_error')
        self.assertIn('actual independent delivery', caught.exception.__context__.diag.message_primary)
        self.assertEqual(self.runtime.show(job['execution_id'])['state'], 'proposed')
        self.assertEqual(self.runtime.graph(self.f.data_id)['edges'], [])
        accepted = self.runtime.decide(job['execution_id'], response, receipt)
        revision = accepted['records'][0]['result_edge_revision_id']
        original = self.f.projected(revision)
        other = self.f.created('qualifies')
        pending = self.f.review(revision)
        with self.f.fixture.connection() as conn:
            original_record = conn.execute('SELECT origin_record_id FROM canonical_store.knowledge_edge_revisions WHERE kedge_revision_id=%s', (revision,)).fetchone()['origin_record_id']
            before = conn.execute('SELECT count(*) AS n FROM canonical_store.knowledge_edge_applicability_events').fetchone()['n']
        detail = {'n2e_policy': 'n2e-relations-v1', **n2e_runtime.support_binding([self.f.nodes[2], self.f.nodes[0]])}

        def old_record_republish(conn):
            conn.execute('''INSERT INTO canonical_store.knowledge_edge_applicability_events
                (kedge_id,semantic_kedge_revision_id,from_knode_revision_id,to_knode_revision_id,applicable,origin_record_id,detail)
                VALUES (%s,%s,%s,%s,true,%s,%s)''', (original['kedge_id'], revision,
                self.f.nodes[2]['knode_revision_id'], self.f.nodes[0]['knode_revision_id'], original_record, Jsonb(detail)))

        self.rejected_sql(old_record_republish, 'fresh pending Record', immediate=True)
        self.assertEqual(self.f.projected(revision)['applicability'], 'pending')
        wrong_job = self.f.prepare()
        wrong_context = self.f.stage(wrong_job, [self.f.edge('qualifies')])
        wrong_record = self.runtime.show(wrong_job['execution_id'])['records'][0]
        wrong_validation = self.f.decisions(wrong_context, material=False)['decisions'][0]
        other_edge = self.f.projected(other)

        def wrong_result(conn):
            conn.execute('''INSERT INTO canonical_store.knowledge_edge_applicability_events
                (kedge_id,semantic_kedge_revision_id,from_knode_revision_id,to_knode_revision_id,applicable,origin_record_id,detail)
                VALUES (%s,%s,%s,%s,true,%s,%s)''', (original['kedge_id'], revision,
                self.f.nodes[2]['knode_revision_id'], self.f.nodes[0]['knode_revision_id'], wrong_record['record_id'], Jsonb(detail)))
            conn.execute('''INSERT INTO compiler_runtime.n2e_review_decisions
                (record_id,execution_id,candidate_key,role,validation,action,material_change,before_applicable,after_applicable)
                VALUES (%s,%s,'relation','relation',%s,'reused',false,true,true)''',
                (wrong_record['record_id'], wrong_job['execution_id'], Jsonb(wrong_validation)))
            self.runtime._resolve(conn, wrong_record, 'reused', wrong_validation,
                edge={'kedge_id': other_edge['kedge_id'], 'kedge_revision_id': other})

        self.rejected_sql(wrong_result, 'Modern applicability requires its own resolved N2E result')
        self.f.review(revision)
        def stale_preparation(conn):
            conn.execute('''INSERT INTO canonical_store.knowledge_edge_applicability_events
                (kedge_id,semantic_kedge_revision_id,from_knode_revision_id,to_knode_revision_id,applicable,origin_record_id,detail)
                VALUES (%s,%s,%s,%s,true,%s,%s)''', (original['kedge_id'], revision,
                self.f.nodes[2]['knode_revision_id'], self.f.nodes[0]['knode_revision_id'], wrong_record['record_id'], Jsonb(detail)))
        self.rejected_sql(stale_preparation, 'after the exact review fence', immediate=True)
        # A legacy-shaped Record cannot bypass a modern semantic origin/fence.
        def legacy_downgrade(conn):
            execution = self.f.fixture.execution(conn, 'n2e', (self.f.seed[2], self.f.seed[0]))
            record = self.f.fixture.record(conn, execution, 0, 'n2e', 'a'*64, 'b'*64)
            conn.execute('''INSERT INTO canonical_store.knowledge_edge_applicability_events
                (kedge_id,semantic_kedge_revision_id,from_knode_revision_id,to_knode_revision_id,applicable,origin_record_id)
                VALUES (%s,%s,%s,%s,true,%s)''', (original['kedge_id'], revision,
                self.f.nodes[2]['knode_revision_id'], self.f.nodes[0]['knode_revision_id'], record))
        self.rejected_sql(legacy_downgrade, 'downgraded to legacy N2E evidence', immediate=True)
        with self.f.fixture.connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM canonical_store.knowledge_edge_applicability_events').fetchone()['n'], before)

    def test_assessment_requires_null_materiality_completed_agreeing_generator_and_resolved_record(self):
        revision = self.f.created()
        false_job = self.f.review(revision)
        false_context = self.f.stage(false_job, [], False)
        self.rejected_sql(lambda conn: self.decision_insert(conn, false_job, false_context, applicable=True),
            'agreeing independent assessment', immediate=True)
        true_job = self.f.review(revision)
        true_context = self.f.stage(true_job, [], True)
        self.rejected_sql(lambda conn: self.decision_insert(conn, true_job, true_context, material=True),
            'leaves semantic materiality to Runtime', immediate=True)
        incomplete_job = self.f.review(revision)
        raw = {'edges': [], 'complete': False, 'applicability': {'applicable': True,
            'reason_codes': ['synthetic_fixture'], 'reason': 'Synthetic partial Generator output.'}}
        incomplete_context = self.runtime.stage(incomplete_job['execution_id'], raw,
            self.f.receipt(incomplete_job, 'generator', raw))
        self.rejected_sql(lambda conn: self.decision_insert(conn, incomplete_job, incomplete_context),
            'completed Generator', immediate=True)
        # Inserting a planned accepted decision alone must not make it durable.
        self.rejected_sql(lambda conn: self.decision_insert(conn, true_job, true_context),
            'resolved Record must commit together')
        with self.f.fixture.connection() as conn:
            count = conn.execute('SELECT count(*) AS n FROM compiler_runtime.n2e_review_decisions WHERE execution_id=ANY(%s::uuid[])',
                ([false_job['execution_id'], true_job['execution_id'], incomplete_job['execution_id']],)).fetchone()['n']
        self.assertEqual(count, 0)
        self.assertEqual(self.f.projected(revision)['applicability'], 'pending')

    def inference_receipt(self, job, phase, response, context=None):
        prompt, schema = (k2k.generation_request(job['input_snapshot'], []) if phase == 'generator'
                          else k2k.validation_request(context, []))
        receipt = {'profile': {**job['profile']['model'], 'synthetic_receipt': True},
            'actual_delivery': True, 'provider_ref': 'synthetic-sql-guard-' + str(uuid4()), 'usage': {}, 'test_only': True,
            'input_sha256': job['input_digest'] if phase == 'generator' else context['validation_context_sha'],
            'output_sha256': digest(response), 'prompt_sha256': sha256(prompt.encode()).hexdigest(),
            'schema_sha256': digest(schema), 'image_attachments': [],
            'delivered_knowledge_revision_ids': [n['knode_revision_id'] for n in job['input_snapshot']['input']['nodes']]}
        if job['input_snapshot'].get('revision_target'):
            receipt['delivered_revision_target_id'] = job['input_snapshot']['revision_target']['expected_revision_id']
        if job['input_snapshot'].get('revalidation_target'):
            receipt['delivered_revalidation_target_sha256'] = job['input_snapshot']['revalidation_target']['target_sha256']
        return receipt

    def inference_commit(self, job, response, *, same_meaning=False):
        context = self.runtime.stage(job['execution_id'], response, self.inference_receipt(job, 'generator', response))
        decision = inference_fixtures.K2KRuntimeTests.decisions(response)
        if job['input_snapshot'].get('revision_target'):
            decision['revision_review'] = {'comparison_base_revision_id': job['input_snapshot']['revision_target']['expected_revision_id'],
                'same_identity': True, 'material_change': not same_meaning, 'grounding_valid': True,
                'reason_codes': ['synthetic_fixture'], 'reason': 'Synthetic support-only review; no model called.'}
        return self.runtime.decide(job['execution_id'], decision, self.inference_receipt(job, 'validator', decision, context))

    def test_support_signature_parity_and_same_revision_support_change_requires_edge_review(self):
        # The low-level N2E fixture intentionally has legacy measurement payloads.
        # K2K inputs require normal structured Knowledge, so use the existing
        # normalized source/I2K fixture for this cross-operation assertion.
        normalized = normalized_fixtures.KnowledgeRevisionIntegrationTests('runTest')
        normalized.dsn = self.dsn
        normalized.setUp()
        self.addCleanup(normalized.doCleanups)
        derived, _ = normalized.inference(name='signature_fixture')
        revision = derived['knode_revision_id']
        source_nodes = [normalized.node(ref) for ref in normalized.premises]
        with self.f.fixture.connection() as conn:
            for node in [*source_nodes, derived]:
                sql_signature = conn.execute('SELECT canonical_store.current_knowledge_support_signature(%s) AS signature',
                    (node['knode_revision_id'],)).fetchone()['signature']
                self.assertEqual(sql_signature, node['current_support_signature'])
        edge = self.f.edge()
        edge['from_revision_id'] = source_nodes[0]['knode_revision_id']
        edge['to_revision_id'] = revision
        job = self.runtime.prepare('n2e', normalized.data_id, self.f.repo.allocate_id(),
            {'schema_version': 'n2e-input-v1', 'nodes': [source_nodes[0], derived]})
        created = self.f.accept(job, [edge])
        edge_revision = created['records'][0]['result_edge_revision_id']
        def projected():
            return next(row for row in self.runtime.graph(normalized.data_id)['edges'] if row['kedge_revision_id'] == edge_revision)
        self.assertEqual(projected()['applicability'], 'applicable')
        original_signature = derived['current_support_signature']
        reviewed = revalidation.prepare_node(self.runtime, revision, self.f.repo.allocate_id(), data_id=normalized.data_id)
        response = inference_fixtures.K2KRuntimeTests.response(normalized, reviewed, existing=derived)
        reused = self.inference_commit(reviewed, response, same_meaning=True)
        self.assertEqual(reused['records'][0]['disposition'], 'reused')
        self.assertEqual(reused['records'][0]['result_node_revision_id'], revision)
        current = next(node for node in self.runtime.graph(normalized.data_id)['nodes'] if node['knode_revision_id'] == revision)
        self.assertNotEqual(current['current_support_signature'], original_signature)
        self.assertEqual(current['current_applicability'], 'current_premises')
        self.assertEqual(projected()['applicability'], 'pending')
        edge_review = n2e_runtime.prepare_review(self.runtime, edge_revision, self.f.repo.allocate_id(), data_id=normalized.data_id)
        self.f.accept(edge_review, [], applicable=True)
        self.assertEqual(projected()['applicability'], 'applicable')

    def test_database_rejects_prospective_batch_cycle_when_runtime_dfs_is_bypassed(self):
        job = self.f.prepare()
        edges = [self.f.edge('composes', source=0, target=1, key='ab'),
                 self.f.edge('composes', source=1, target=2, key='bc'),
                 self.f.edge('composes', source=2, target=0, key='ca')]
        context = self.f.stage(job, edges)
        response = self.f.decisions(context)
        receipt = self.f.receipt(job, 'validator', response, context)
        with patch('palimpsest.n2e_runtime._cycle', return_value=False), self.assertRaises(PalimpsestError) as caught:
            self.runtime.decide(job['execution_id'], response, receipt)
        self.assertEqual(caught.exception.code, 'database_error')
        self.assertIn('proper-component relations must be acyclic', caught.exception.__context__.diag.message_primary)
        state = self.runtime.show(job['execution_id'])
        self.assertEqual(state['state'], 'proposed')
        self.assertEqual(state['relation_decisions'], [])
        self.assertEqual([record['disposition'] for record in state['records']], ['pending']*3)
        self.assertEqual(self.runtime.graph(self.f.data_id)['edges'], [])
        # The same staged work can still resolve through an actual acyclic verdict.
        response['decisions'][-1].update(verdict='rejected', relation_valid=False,
            reason_codes=['synthetic_cycle_rejected'], reason='Synthetic independent refusal of the closing component edge.')
        accepted = self.runtime.decide(job['execution_id'], response, self.f.receipt(job, 'validator', response, context))
        self.assertEqual(accepted['state'], 'completed')
        self.assertEqual(len(self.runtime.graph(self.f.data_id)['usable_edges']), 2)
