"""Negative SQL checks beneath the effective K2K writer, no provider calls.

Root provisions/runs palimpsest_effective_k2k_checks. Fault injection skips only
the stated application check/write so actual database guards must reject it.
"""

from copy import deepcopy
import os
import unittest
from unittest.mock import patch

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from palimpsest import k2k_effective_runtime as effective, revalidation
from palimpsest.canonical_store import connection
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
import test_effective_k2k_runtime as fixtures


@unittest.skipUnless(os.environ.get('PALIMPSEST_TEST_DSN'), 'Requires dedicated effective K2K PostgreSQL')
class EffectiveK2KSqlTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.EffectiveK2KRuntimeTests('runTest')
        self.addCleanup(self.f.doCleanups)
        self.f.setUp()  # Asserts the exact isolated DB and effective input table.
        self.runtime, self.dsn = self.f.runtime, self.f.dsn
        with connection(self.dsn) as conn:
            self.assertTrue(conn.execute("SELECT 1 FROM compiler_runtime.schema_migrations "
                "WHERE version='0020_effective_k2k'").fetchone())

    def rejected_sql(self, callback, message):
        with self.assertRaises(psycopg.Error) as caught:
            with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
                callback(conn)
                conn.execute('SET CONSTRAINTS ALL IMMEDIATE')
        self.assertIn(message, caught.exception.diag.message_primary)

    def rejected_runtime(self, callback, message):
        with self.assertRaises(PalimpsestError) as caught:
            callback()
        self.assertEqual(caught.exception.code, 'database_error', 'The injected write must reach SQL.')
        self.assertIn(message, caught.exception.__context__.diag.message_primary)

    def no_preparation(self, request_id):
        with connection(self.dsn) as conn:
            self.assertIsNone(conn.execute('SELECT execution_id FROM compiler_runtime.k_execution_contexts '
                'WHERE request_id=%s', (request_id,)).fetchone())

    def still_proposed(self, job, *, records=1):
        saved = self.runtime.show(job['execution_id'])
        self.assertEqual(saved['state'], 'proposed')
        self.assertIsNone(saved['validator_receipt'])
        self.assertEqual([record['disposition'] for record in saved['records']], ['pending'] * records)
        self.assertEqual(saved['derivations'], [])
        self.assertEqual(len(saved['model_calls']), 1)
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('''SELECT count(*) AS n FROM compiler_runtime.k_outbox o
                JOIN compiler_runtime.k_compilation_records r USING(record_id) WHERE r.execution_id=%s''',
                (job['execution_id'],)).fetchone()['n'], 0)

    def test_typed_endpoint_and_basis_record_cannot_disagree_with_the_frozen_relation(self):
        before = self.runtime.graph(self.f.data_id)
        for fault in ('endpoint', 'basis_owner'):
            with self.subTest(fault=fault):
                packet = self.runtime.inference_input(self.f.data_id, edge_revision_ids=[self.f.edge])
                identifier = self.f.repo.allocate_id()

                def forge(conn, execution_id, supplied):
                    edge = supplied['effective_edges'][0]
                    ref = edge['effective_edge_ref']
                    event = ref['applicability_basis_ref']
                    origin = conn.execute('SELECT origin_record_id FROM canonical_store.knowledge_edge_applicability_events '
                        'WHERE applicability_event_id=%s', (event,)).fetchone()['origin_record_id']
                    source = ref['to_knode_revision_id'] if fault == 'endpoint' else ref['from_knode_revision_id']
                    if fault == 'basis_owner':
                        # This is a real FK-compatible Record, but does not own the relation assessment.
                        origin = supplied['nodes'][0]['origin_record_id']
                    conn.execute('''INSERT INTO compiler_runtime.k_input_effective_edges
                        (execution_id,ordinal,kedge_id,semantic_kedge_revision_id,from_knode_revision_id,to_knode_revision_id,
                         basis_type,basis_origin_record_id,applicability_event_id,relation_read_state_token,
                         from_support_signature,to_support_signature,payload)
                        VALUES (%s,0,%s,%s,%s,%s,'applicability_event',%s,%s,%s,%s,%s,%s)''',
                        (execution_id, edge['kedge_id'], ref['semantic_kedge_revision_id'], source, ref['to_knode_revision_id'],
                         origin, event, ref['relation_read_state_token'], *edge['endpoint_support_signatures'], Jsonb(edge)))

                with patch.object(effective, 'bind_inputs', side_effect=forge):
                    self.rejected_runtime(lambda: self.runtime.prepare('k2k', self.f.data_id, identifier, packet),
                                          'actual current relation basis and both delivered endpoint values')
                self.no_preparation(identifier)
        self.assertEqual(self.runtime.graph(self.f.data_id), before)

    def test_complete_declared_bundle_cannot_commit_without_its_typed_edge_premise(self):
        job = self.f.prepare()
        response = self.f.response(job)
        self.f.stage(job, response)
        decisions = self.f.decisions(job, response)
        receipt = self.f.receipt(job, 'validator', decisions)
        before = self.runtime.graph(self.f.data_id)
        with patch.object(effective, 'bind_derivation', return_value=None):
            self.rejected_runtime(lambda: self.runtime.decide(job['execution_id'], decisions, receipt),
                                  'complete current dependencies')
        self.still_proposed(job)
        self.assertEqual(self.runtime.graph(self.f.data_id), before)
        result = self.runtime.decide(job['execution_id'], decisions, receipt)
        self.assertEqual(result['state'], 'completed')
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM canonical_store.knowledge_derivation_edge_premises '
                'WHERE record_id=%s', (result['records'][0]['record_id'],)).fetchone()['n'], 1)

    def test_zero_output_requires_real_generator_and_independent_validator_delivery(self):
        job = self.f.prepare()
        self.rejected_sql(lambda conn: conn.execute("UPDATE compiler_runtime.operation_executions SET state='zero_output' "
            'WHERE execution_id=%s', (job['execution_id'],)), 'independent actual delivery')
        self.assertEqual(self.runtime.show(job['execution_id'])['state'], 'prepared')
        self.assertEqual(self.runtime.show(job['execution_id'])['model_calls'], [])
        response = {'nodes': [], 'complete': True, 'coverage_notes': ['Synthetic empty inference.']}
        self.f.stage(job, response)
        decisions = {'decisions': [], 'complete': True}
        receipt = self.f.receipt(job, 'validator', decisions)
        original_call = self.runtime._call

        def omit_validator(conn, current, phase, supplied):
            if phase != 'validator':
                return original_call(conn, current, phase, supplied)

        with patch.object(self.runtime, '_call', side_effect=omit_validator):
            self.rejected_runtime(lambda: self.runtime.decide(job['execution_id'], decisions, receipt),
                                  'independent actual delivery')
        self.still_proposed(job, records=0)
        result = self.runtime.decide(job['execution_id'], decisions, receipt)
        self.assertEqual(result['state'], 'zero_output')
        self.assertEqual(len(result['model_calls']), 2)

    def test_revalidation_target_cannot_omit_the_previous_active_edge_bundle(self):
        node, _ = self.f.created()
        self.f.create_edge()  # Refresh the same relation basis; the previous support needs review.
        original = deepcopy(self.f.f.node(node['knode_revision_id'])['generation_origin'])
        identifier = self.f.repo.allocate_id()
        freeze = revalidation.freeze_node

        def omit(*args, **kwargs):
            target = freeze(*args, **kwargs)
            target.pop('effective_edge_refs')
            target['target_sha256'] = digest({key: value for key, value in target.items() if key != 'target_sha256'})
            return target

        with patch.object(revalidation, 'freeze_node', side_effect=omit):
            self.rejected_runtime(lambda: revalidation.prepare_node(self.runtime, node['knode_revision_id'], identifier,
                data_id=self.f.data_id), 'preserve every previous logical Edge')
        self.no_preparation(identifier)
        self.assertEqual(self.f.f.node(node['knode_revision_id'])['generation_origin'], original)
        valid = revalidation.prepare_node(self.runtime, node['knode_revision_id'], identifier, data_id=self.f.data_id)
        self.assertEqual(valid['input_snapshot']['revalidation_target']['effective_edge_refs'],
                         effective.delivery(valid['input_snapshot']['input'])['delivered_effective_edge_refs'])

    def test_stale_basis_cannot_publish_even_empty_results_below_runtime_freshness_checks(self):
        job = self.f.prepare()
        response = {'nodes': [], 'complete': True, 'coverage_notes': ['Synthetic empty inference.']}
        self.f.stage(job, response)
        decisions = {'decisions': [], 'complete': True}
        receipt = self.f.receipt(job, 'validator', decisions)
        staged = self.runtime.show(job['execution_id'])
        self.f.edge_review()  # Same endpoints, new latest basis; the old exact ref is no longer current.

        def publish_unchecked(conn):
            # Deliberately bypass Python's knowledge-state test while retaining
            # complete actual synthetic call evidence. SQL must fence this path.
            self.runtime._call(conn, staged, 'validator', receipt)
            stored = {**deepcopy(receipt), 'effective_validation_output': decisions}
            conn.execute("UPDATE compiler_runtime.operation_executions SET state='zero_output',validator_receipt=%s "
                         'WHERE execution_id=%s', (Jsonb(stored), job['execution_id']))

        self.rejected_sql(publish_unchecked, 'still-current whole bundle')
        self.still_proposed(job, records=0)
        with connection(self.dsn) as conn:
            self.assertFalse(conn.execute('SELECT compiler_runtime.k2k_edge_input_current(%s,0) AS current',
                (job['execution_id'],)).fetchone()['current'])
        self.assertEqual(self.f.f.source_state(), self.f.f.source_before)


if __name__ == '__main__':
    unittest.main()
