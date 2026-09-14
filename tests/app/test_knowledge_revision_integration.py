"""Explicit I2K/K2K revisions in an explicitly provisioned isolated PostgreSQL DB.

All proposals and delivery/validation receipts are synthetic. These tests do not
migrate, reset a DB, call providers or establish semantic inference quality.
"""

from copy import deepcopy
from hashlib import sha256
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from palimpsest import k2k, multi_source_i2k as multi
from palimpsest.artifact_store import ArtifactStore
from palimpsest.canonical_store import PostgresRepository, connection
from palimpsest.compiler_runtime import CompilerRuntime
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.knowledge_requests import (generation_request, validation_request,
    edge_generation_request, edge_validation_request)
from palimpsest.knowledge_revision_runtime import PROFILE
from palimpsest.knowledge_runtime import KnowledgeRuntime
from palimpsest.service import DataService

import test_k2k_runtime as inference_fixtures
import test_multi_source_runtime as source_fixtures


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires explicitly provisioned Linux PostgreSQL revision fixture')
class KnowledgeRevisionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['PALIMPSEST_TEST_DSN']
        with connection(cls.dsn) as conn:
            if conn.execute('SELECT current_database() AS name').fetchone()['name'] not in (
                    'palimpsest', 'palimpsest_d2k_checks', 'palimpsest_propagation_checks'):
                raise RuntimeError('Explicit revisions require the isolated fixture database')
            for table in ('compiler_runtime.k_revision_targets', 'compiler_runtime.k_revision_decisions',
                          'compiler_runtime.k_revision_impacts'):
                if conn.execute('SELECT to_regclass(%s) AS name', (table,)).fetchone()['name'] is None:
                    raise RuntimeError('Root must provision reviewed migration0015 before these tests')

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='palimpsest-explicit-revision-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / 'artifacts'
        self.repo = PostgresRepository(self.dsn)
        path = self.base / 'source.md'
        path.write_text(f'# Synthetic revision fixture {uuid4()}\n\n'
                        'The fixture reports a measured value of three and a revised value of four.\n\n'
                        'A second explicit premise reports a controlled fixture condition.\n', encoding='utf-8')
        imported = DataService(self.repo, ArtifactStore(self.root), actor_ref='test-user').import_file(
            path, media_type='text/markdown')
        self.data_id = imported['data_id']
        source = CompilerRuntime(self.dsn, self.root)
        self.source_result = source.compile_markdown(self.data_id)
        self.packet = source.prepare_input(self.source_result['execution_id'])
        self.bundle = multi.combine_packets([self.packet])
        self.unit = next(unit for unit in self.bundle['model_input']['information'] if unit['content'].strip())
        self.runtime = KnowledgeRuntime(self.dsn)
        self.seed_response = self.source_response([
            self.source_candidate('observation', 'observation', 'three'),
            self.source_candidate('proposition', 'proposition', 'controlled condition')])
        initial = self.prepare_source()
        self.seed = self.commit(initial, self.seed_response)
        self.source_target = self.node(self.seed['records'][0]['result_node_revision_id'])
        self.premises = [record['result_node_revision_id'] for record in self.seed['records']]
        self.source_before = self.source_state()
        # Fixture setup is the only D2I call. Revision work must consume frozen I.
        d2i_guard = patch('palimpsest.compiler_runtime.CompilerRuntime.compile_markdown',
                         side_effect=AssertionError('Revision must not invoke D2I'))
        d2i_guard.start()
        self.addCleanup(d2i_guard.stop)

    def source_candidate(self, key, kind, value):
        return {'candidate_key': key, 'kind': kind,
            'statement': 'Synthetic source-explicit ' + value,
            'semantic_payload': {'subject': 'Synthetic source ' + self.data_id,
                'relation': 'reports ' + key, 'object': value, 'polarity': 'positive',
                'quantifier': 'source-reported fixture', 'scope': 'isolated revision test',
                'conditions': [], 'time_range': ''},
            'identity_scope': 'source', 'source_data_id': self.data_id,
            'selection_reason': 'Synthetic useful explicit assertion.',
            'claim_basis': 'explicit_source_content', 'is_inferred': False, 'uncertainties': [],
            'evidence': [{'information_id': self.unit['information_id'], 'quote': self.unit['content'],
                          'media_sha256': None, 'source_role': 'other'}]}

    def source_response(self, nodes):
        return {'nodes': nodes, 'source_requests': [], 'complete': True,
            'coverage_notes': ['Synthetic fixture; independent semantic validity is not established.'],
            'reviews': [{'information_id': unit['information_id'],
                'disposition': 'selected' if unit['information_id'] == self.unit['information_id'] and nodes else 'context_only',
                'candidate_keys': [node['candidate_key'] for node in nodes]
                    if unit['information_id'] == self.unit['information_id'] else [],
                'reason': 'Synthetic full I review.'} for unit in self.bundle['model_input']['information']]}

    def prepare_source(self, target=None, request=None):
        return self.runtime.prepare('i2k', self.data_id, request or self.repo.allocate_id(),
            self.bundle, selection=True, source_review=False, **self.target_args(target))

    @staticmethod
    def target_args(target):
        return {} if target is None else {'target_knode_id': target['knode_id'],
                                         'expected_revision_id': target['knode_revision_id']}

    def prepare_inference(self, target=None, premises=None):
        packet = self.runtime.inference_input(self.data_id, premises or self.premises)
        return self.runtime.prepare('k2k', self.data_id, self.repo.allocate_id(), packet,
                                    **self.target_args(target))

    def receipt(self, job, output, phase):
        current = self.runtime.show(job['execution_id'])
        snapshot = current['input_snapshot']
        if phase == 'generator':
            input_sha = current['input_digest']
            prompt, schema = (k2k.generation_request(snapshot, []) if current['operation'] == 'k2k'
                else edge_generation_request(snapshot) if current['operation'] == 'n2e'
                else generation_request(snapshot, []))
        else:
            context = self.runtime.validation_context(job['execution_id'])
            input_sha = context['validation_context_sha']
            prompt, schema = (k2k.validation_request(context, []) if current['operation'] == 'k2k'
                else edge_validation_request(context) if current['operation'] == 'n2e'
                else validation_request(context, []))
        result = {'profile': deepcopy(current['profile']['model']), 'actual_delivery': True,
            'original_pdf_delivered': False, 'provider_ref': 'synthetic-revision-' + str(uuid4()),
            'input_sha256': input_sha, 'output_sha256': digest(output),
            'prompt_sha256': sha256(prompt.encode()).hexdigest(), 'schema_sha256': digest(schema),
            'image_attachments': [], 'usage': {}, 'test_only': True}
        if current['operation'] == 'i2k':
            result['delivered_information_ids'] = multi.check_input(snapshot['input'])
        elif current['operation'] == 'k2k':
            result['delivered_knowledge_revision_ids'] = k2k.check_input(snapshot['input'])
        if snapshot.get('revision_target') is not None:
            result['delivered_revision_target_id'] = snapshot['revision_target']['expected_revision_id']
        return result

    def decisions(self, job, response, *, material=True):
        result = (inference_fixtures.K2KRuntimeTests.decisions(response) if job['operation'] == 'k2k'
                  else source_fixtures.MultiSourceRuntimeTests.decisions(response))
        if job['input_snapshot'].get('revision_target') is not None:
            result['revision_review'] = ({'comparison_base_revision_id':
                job['input_snapshot']['revision_target']['expected_revision_id'],
                'same_identity': True, 'material_change': material, 'grounding_valid': True,
                'reason_codes': ['synthetic_material_review'],
                'reason': 'Independent synthetic materiality verdict; no model called.'} if response['nodes'] else None)
        return result

    def stage(self, job, response):
        return self.runtime.stage(job['execution_id'], response, self.receipt(job, response, 'generator'))

    def commit(self, job, response, decisions=None):
        self.stage(job, response)
        decision = self.decisions(job, response) if decisions is None else decisions
        self.runtime.decide(job['execution_id'], decision, self.receipt(job, decision, 'validator'))
        return self.runtime.show(job['execution_id'])

    def node(self, revision):
        return next(node for node in self.runtime.graph(self.data_id)['nodes'] if node['knode_revision_id'] == revision)

    def revision_rows(self, node_id):
        with connection(self.dsn) as conn:
            return conn.execute('SELECT * FROM canonical_store.knowledge_node_revisions WHERE knode_id=%s '
                                'ORDER BY knode_revision_id', (node_id,)).fetchall()

    def source_state(self):
        with connection(self.dsn) as conn:
            information = conn.execute('SELECT * FROM canonical_store.information WHERE data_id=%s '
                                       'ORDER BY information_id', (self.data_id,)).fetchall()
            sources = conn.execute("SELECT * FROM compiler_runtime.operation_executions WHERE data_id=%s "
                "AND operation IN ('d2i','d2k') ORDER BY execution_id", (self.data_id,)).fetchall()
            data = conn.execute('SELECT * FROM canonical_store.data WHERE data_id=%s', (self.data_id,)).fetchone()
        return {'information': information, 'sources': sources, 'data': data,
                'raw': ArtifactStore(self.root).read(self.data_id, data['byte_size'])}

    def inference(self, name='initial_inference'):
        job = self.prepare_inference()
        response = inference_fixtures.K2KRuntimeTests.response(self, job, name=name)
        result = self.commit(job, response)
        return self.node(result['records'][0]['result_node_revision_id']), result

    def assert_no_new_revision(self, target, before):
        self.assertEqual(self.revision_rows(target['knode_id']), before)
        self.assertEqual(self.node(target['knode_revision_id'])['current_revision_id'], target['knode_revision_id'])
        self.assertEqual(self.source_state(), self.source_before)

    def test_i2k_material_revision_keeps_identity_history_and_exact_dependency_impacts(self):
        target = self.source_target
        historical = self.revision_rows(target['knode_id'])
        inferred, derivation_job = self.inference()
        graph = self.runtime.graph(self.data_id)
        nodes = [node for node in graph['nodes'] if node['knode_revision_id'] in self.premises]
        edge_job = self.runtime.prepare('n2e', self.data_id, self.repo.allocate_id(),
                                       {'schema_version': 'n2e-input-v1', 'nodes': nodes})
        edge_response = {'edges': [{'candidate_key': 'edge', 'predicate': 'supports',
            'from_revision_id': self.premises[0], 'to_revision_id': self.premises[1],
            'qualifiers': {'scope': 'isolated revision fixture', 'conditions': []},
            'rationale': 'Synthetic explicitly checked fixture support.'}], 'complete': True}
        self.stage(edge_job, edge_response)
        edge_decision = {'complete': True, 'decisions': [{'candidate_key': 'edge', 'verdict': 'accepted',
            'reason_codes': ['synthetic_fixture'], 'reason': 'Synthetic storage verdict.'}]}
        self.runtime.decide(edge_job['execution_id'], edge_decision, self.receipt(edge_job, edge_decision, 'validator'))
        edge = self.runtime.show(edge_job['execution_id'])['records'][0]
        request = self.repo.allocate_id()
        job = self.prepare_source(target, request)
        response = self.source_response([self.source_candidate('observation', 'observation', 'four')])
        result = self.commit(job, response)
        record = result['records'][0]
        new = self.node(record['result_node_revision_id'])
        self.assertEqual((result['state'], record['disposition']), ('completed', 'accepted_revision'))
        self.assertEqual(new['knode_id'], target['knode_id'])
        self.assertEqual(new['identity_fingerprint'], target['identity_fingerprint'])
        self.assertNotEqual(new['content_fingerprint'], target['content_fingerprint'])
        self.assertEqual(new['origin_record_id'], record['record_id'])
        self.assertEqual(new['generation_origin']['origin_operation'], 'i2k')
        self.assertFalse(new['generation_origin']['is_inferred'])
        self.assertEqual(self.revision_rows(target['knode_id'])[:1], historical)
        self.assertEqual(str(self.revision_rows(target['knode_id'])[1]['supersedes_revision_id']), target['knode_revision_id'])
        self.assertEqual(result['profile']['explicit_knowledge_revision'], PROFILE)
        self.assertEqual(result['revision']['target'], job['input_snapshot']['revision_target'])
        for receipt in (result['generator_receipt'], result['validator_receipt']):
            self.assertEqual(receipt['delivered_revision_target_id'], target['knode_revision_id'])
            self.assertEqual(receipt['delivered_information_ids'], self.bundle['target_information_ids'])
        impacts = result['revision']['impacts'][0]['impacts']
        self.assertEqual(impacts['source_revision_id'], target['knode_revision_id'])
        self.assertEqual({row['record_id'] for row in impacts['derivations']}, {derivation_job['records'][0]['record_id']})
        self.assertEqual({row['kedge_revision_id'] for row in impacts['edges']}, {edge['result_edge_revision_id']})
        stale = self.node(inferred['knode_revision_id'])
        self.assertEqual(stale['current_applicability'], 'needs_revalidation')
        self.assertEqual(stale['generation_origin'], inferred['generation_origin'])
        self.assertEqual(result['revision']['result']['propagation_status'], 'outbox_pending_not_converged')
        with connection(self.dsn) as conn:
            operations = conn.execute('SELECT operation FROM compiler_runtime.k_outbox WHERE record_id=%s',
                                      (record['record_id'],)).fetchall()
        self.assertEqual({row['operation'] for row in operations}, {'n2e', 'k2k'})
        replay = self.prepare_source(target, request)
        self.assertTrue(replay['replayed'])
        self.assertEqual(replay['execution_id'], job['execution_id'])
        self.assertEqual(self.source_state(), self.source_before)

    def test_k2k_material_revision_owns_new_origin_and_exact_premises_without_fake_i(self):
        target, original = self.inference()
        historical = self.revision_rows(target['knode_id'])
        job = self.prepare_inference(target)
        response = inference_fixtures.K2KRuntimeTests.response(self, job, name='material_inference')
        result = self.commit(job, response)
        record = result['records'][0]
        new = self.node(record['result_node_revision_id'])
        self.assertEqual(record['disposition'], 'accepted_revision')
        self.assertEqual(new['knode_id'], target['knode_id'])
        self.assertEqual(new['identity_fingerprint'], target['identity_fingerprint'])
        self.assertNotEqual(new['content_fingerprint'], target['content_fingerprint'])
        self.assertEqual(new['generation_origin']['origin_operation'], 'k2k')
        self.assertTrue(new['generation_origin']['is_inferred'])
        self.assertEqual(new['origin_record_id'], record['record_id'])
        self.assertEqual(new['direct_groundings'], [])
        self.assertEqual(new.get('direct_data_groundings', []), [])
        self.assertEqual(self.revision_rows(target['knode_id'])[:1], historical)
        self.assertEqual(self.runtime.show(original['execution_id'])['derivations'], original['derivations'])
        derivation = result['derivations'][0]
        self.assertEqual(derivation['premise_revision_ids'], self.premises)
        self.assertEqual(derivation['assumptions'], response['nodes'][0]['assumptions'])
        self.assertEqual(derivation['limitations'], response['nodes'][0]['limitations'])
        self.assertEqual(result['generator_receipt']['delivered_knowledge_revision_ids'], self.premises)
        self.assertEqual(self.source_state(), self.source_before)

    def test_nonmaterial_source_and_inference_results_reuse_exact_revision_and_origin(self):
        inferred, _ = self.inference()
        for operation, target in [('i2k', self.source_target), ('k2k', inferred)]:
            with self.subTest(operation=operation):
                before = self.revision_rows(target['knode_id'])
                job = self.prepare_source(target) if operation == 'i2k' else self.prepare_inference(target)
                response = (self.source_response([self.source_candidate('observation', 'observation', 'three in other words')])
                    if operation == 'i2k' else inference_fixtures.K2KRuntimeTests.response(self, job, name='paraphrase'))
                result = self.commit(job, response, self.decisions(job, response, material=False))
                record = result['records'][0]
                self.assertEqual((result['state'], record['disposition']), ('completed', 'reused'))
                self.assertEqual(record['result_node_revision_id'], target['knode_revision_id'])
                self.assertEqual(self.node(target['knode_revision_id'])['generation_origin'], target['generation_origin'])
                self.assertEqual(result['revision']['impacts'], [])
                self.assertEqual(result['revision']['result']['propagation_status'], 'no_new_semantic_branch')
                with connection(self.dsn) as conn:
                    self.assertEqual(conn.execute('SELECT count(*) AS n FROM compiler_runtime.k_outbox WHERE record_id=%s',
                                                  (record['record_id'],)).fetchone()['n'], 0)
                self.assert_no_new_revision(target, before)

    def test_empty_explicit_requests_remain_unresolved_in_both_operations(self):
        inferred, _ = self.inference()
        for operation, target in [('i2k', self.source_target), ('k2k', inferred)]:
            with self.subTest(operation=operation):
                before = self.revision_rows(target['knode_id'])
                job = self.prepare_source(target) if operation == 'i2k' else self.prepare_inference(target)
                response = (self.source_response([]) if operation == 'i2k'
                            else {'nodes': [], 'complete': True, 'coverage_notes': ['No supportable revision.']})
                result = self.commit(job, response)
                self.assertEqual(result['state'], 'needs_human')
                self.assertEqual(result['records'], [])
                self.assertTrue(result['revision']['result']['requires_user_review'])
                self.assertEqual(result['revision']['decisions'], [])
                self.assertEqual(result['revision']['impacts'], [])
                self.assert_no_new_revision(target, before)

    def test_target_delivery_and_ordinary_source_checks_cannot_be_bypassed_by_materiality(self):
        target = self.source_target
        before = self.revision_rows(target['knode_id'])
        job = self.prepare_source(target)
        response = self.source_response([self.source_candidate('observation', 'observation', 'four')])
        receipt = self.receipt(job, response, 'generator')
        receipt.pop('delivered_revision_target_id')
        with self.assertRaises(PalimpsestError) as missing:
            self.runtime.stage(job['execution_id'], response, receipt)
        self.assertEqual(missing.exception.code, 'knowledge_revision_target_delivery_mismatch')
        self.assertEqual(self.runtime.show(job['execution_id'])['records'], [])
        self.stage(job, response)
        decisions = self.decisions(job, response)
        receipt = self.receipt(job, decisions, 'validator')
        receipt['delivered_revision_target_id'] = self.premises[1]
        with self.assertRaises(PalimpsestError) as wrong:
            self.runtime.decide(job['execution_id'], decisions, receipt)
        self.assertEqual(wrong.exception.code, 'knowledge_revision_target_delivery_mismatch')
        decisions['decisions'][0]['source_explicit'] = False
        with self.assertRaises(PalimpsestError) as ordinary:
            self.runtime.decide(job['execution_id'], decisions, self.receipt(job, decisions, 'validator'))
        self.assertEqual(ordinary.exception.code, 'i2k_explicit_source_acceptance_required')
        self.assertEqual(self.runtime.show(job['execution_id'])['state'], 'proposed')
        self.assertEqual(self.runtime.show(job['execution_id'])['revision']['decisions'], [])
        self.assert_no_new_revision(target, before)

    def test_k2k_target_is_neither_premise_nor_replacement_for_ordinary_inference_review(self):
        target, _ = self.inference()
        before = self.revision_rows(target['knode_id'])
        with self.assertRaises(PalimpsestError) as premise:
            self.prepare_inference(target, [target['knode_revision_id'], self.premises[0]])
        self.assertEqual(premise.exception.code, 'knowledge_revision_premise_boundary')
        job = self.prepare_inference(target)
        response = inference_fixtures.K2KRuntimeTests.response(self, job, name='changed')
        self.stage(job, response)
        decisions = self.decisions(job, response)
        decisions['decisions'][0]['inference_valid'] = False
        with self.assertRaises(PalimpsestError) as ordinary:
            self.runtime.decide(job['execution_id'], decisions, self.receipt(job, decisions, 'validator'))
        self.assertEqual(ordinary.exception.code, 'k2k_acceptance_not_justified')
        decisions = self.decisions(job, response)
        decisions['revision_review']['comparison_base_revision_id'] = self.premises[0]
        with self.assertRaises(PalimpsestError):
            self.runtime.decide(job['execution_id'], decisions, self.receipt(job, decisions, 'validator'))
        self.assert_no_new_revision(target, before)

    def test_two_staged_requests_hold_stale_target_without_second_revision_or_outbox(self):
        target = self.source_target
        first, second = self.prepare_source(target), self.prepare_source(target)
        responses = [self.source_response([self.source_candidate('observation', 'observation', value)])
                     for value in ('four', 'five')]
        for job, response in zip((first, second), responses):
            self.stage(job, response)
        first_decision = self.decisions(first, responses[0])
        self.runtime.decide(first['execution_id'], first_decision, self.receipt(first, first_decision, 'validator'))
        accepted = self.runtime.show(first['execution_id'])
        winning = accepted['records'][0]['result_node_revision_id']
        rows = self.revision_rows(target['knode_id'])
        second_decision = self.decisions(second, responses[1])
        self.runtime.decide(second['execution_id'], second_decision, self.receipt(second, second_decision, 'validator'))
        held = self.runtime.show(second['execution_id'])
        self.assertEqual((held['state'], held['records'][0]['disposition']), ('needs_human', 'needs_human'))
        self.assertIsNone(held['records'][0]['result_node_revision_id'])
        self.assertIn('knowledge_revision_target_changed', held['revision']['decisions'][0]['validation']['reason_codes'])
        self.assertEqual(held['revision']['impacts'], [])
        self.assertEqual(self.revision_rows(target['knode_id']), rows)
        self.assertEqual(self.node(winning)['current_revision_id'], winning)
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM compiler_runtime.k_outbox WHERE record_id=%s',
                                          (held['records'][0]['record_id'],)).fetchone()['n'], 0)
        self.assertEqual(self.source_state(), self.source_before)

    def test_failure_after_revision_effect_rolls_back_revision_groundings_decision_and_impacts(self):
        target = self.source_target
        before = self.revision_rows(target['knode_id'])
        job = self.prepare_source(target)
        response = self.source_response([self.source_candidate('observation', 'observation', 'four')])
        self.stage(job, response)
        staged = self.runtime.show(job['execution_id'])
        decisions = self.decisions(job, response)
        receipt = self.receipt(job, decisions, 'validator')
        def interrupt(phase):
            if phase == 'after_knowledge_effect':
                raise RuntimeError('Synthetic transaction interruption')
        with self.assertRaisesRegex(RuntimeError, 'Synthetic transaction interruption'):
            self.runtime.decide(job['execution_id'], decisions, receipt, checkpoint=interrupt)
        self.assertEqual(self.runtime.show(job['execution_id']), staged)
        self.assert_no_new_revision(target, before)
        with connection(self.dsn) as conn:
            record_id = staged['records'][0]['record_id']
            for table, field in (('canonical_store.knowledge_node_groundings', 'origin_record_id'),
                                 ('compiler_runtime.k_outbox', 'record_id'),
                                 ('compiler_runtime.k_revision_decisions', 'record_id'),
                                 ('compiler_runtime.k_revision_impacts', 'record_id')):
                self.assertEqual(conn.execute(f'SELECT count(*) AS n FROM {table} WHERE {field}=%s',
                                              (record_id,)).fetchone()['n'], 0)
        self.runtime.decide(job['execution_id'], decisions, receipt)
        self.assertEqual(self.runtime.show(job['execution_id'])['records'][0]['disposition'], 'accepted_revision')


if __name__ == '__main__':
    unittest.main()
