"""Isolated PostgreSQL K2W contracts; synthetic receipts, zero provider calls."""
from copy import deepcopy
from hashlib import sha256
import os
import json
import unittest
from uuid import uuid4

from psycopg.types.json import Jsonb

from palimpsest import k2w, k2w_prompts
from palimpsest.canonical_store import connection
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.wisdom_runtime import WisdomRuntime
import test_knowledge_revision_integration as fixtures
import test_effective_k2k_runtime as edge_fixtures


@unittest.skipUnless(os.environ.get('PALIMPSEST_TEST_DSN'), 'Requires dedicated K2W PostgreSQL')
class WisdomRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.dsn = os.environ['PALIMPSEST_TEST_DSN']
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT current_database() AS name').fetchone()['name'], 'palimpsest_wisdom_checks')
            self.assertIsNotNone(conn.execute("SELECT to_regclass('canonical_store.wisdoms') AS name").fetchone()['name'])
        self.f = fixtures.KnowledgeRevisionIntegrationTests('runTest')
        self.f.dsn = self.dsn
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.repo, self.runtime = self.f.repo, WisdomRuntime(self.dsn)

    def prepare(self, *, identifier=None, kind='explanation', edge_revision_ids=()):
        return self.runtime.prepare(identifier or self.repo.allocate_id(), query='Explain the synthetic reported value.',
            context_snapshot={'purpose': 'isolated structural test'}, revision_ids=self.f.premises[:1],
            edge_revision_ids=edge_revision_ids, wisdom_kind=kind)

    @staticmethod
    def response(job):
        packet = job['input_snapshot']
        recommended = packet['wisdom_kind'] == 'recommendation'
        return {'status': 'answered', 'claims': [{'claim_key': 'reported',
            'text': 'The source reports the synthetic value within its stated fixture conditions.',
            'epistemic_basis': 'advisory_recommendation' if recommended else 'accepted_knowledge',
            'k_revision_ids': [node['knode_revision_id'] for node in packet['nodes']],
            'effective_edge_revision_ids': [edge['effective_edge_ref']['semantic_kedge_revision_id'] for edge in packet['effective_edges']],
            'assumptions': [], 'limitations': ['Synthetic fixture; not a real semantic evaluation.']}],
            'recommendation': {'options': [{'option_key': 'review', 'label': 'Review the fixture'}],
                'criteria': ['traceability'], 'comparison': [{'option_key': 'review', 'criterion': 'traceability',
                    'claim_keys': ['reported']}], 'recommended_option': 'review'} if recommended else None,
            'unresolved': []}

    @staticmethod
    def validation(answer):
        return {'verdict': 'accepted', 'claims': [{'claim_key': value['claim_key'],
            **{key: True for key in k2w.CLAIM_CHECKS}} for value in answer['claims']],
            'query_addressed': True, 'advisory_boundary_preserved': True,
            'reason': 'Synthetic independent test fixture, no provider call.'}

    def receipt(self, job, phase, response):
        request = job[phase + '_request']
        return {'profile': {**job['profile']['model'], 'synthetic_receipt': True},
            'test_only': True, 'actual_delivery': True, 'provider_ref': 'synthetic-wisdom-' + str(uuid4()),
            'input_sha256': request['input_sha256'], 'output_sha256': digest(response),
            'prompt_sha256': sha256(request['prompt'].encode()).hexdigest(), 'schema_sha256': digest(request['schema']),
            'delivered_knowledge_revision_ids': request['delivered_knowledge_revision_ids'],
            'delivered_effective_edge_refs': request['delivered_effective_edge_refs'],
            'image_attachments': [], 'usage': {}}

    def accept(self, job):
        answer = self.response(job)
        staged = self.runtime.stage(job['execution_id'], answer, self.receipt(job, 'generator', answer))
        verdict = self.validation(answer)
        self.runtime.validate(job['execution_id'], verdict, self.receipt(staged, 'validator', verdict))
        return self.runtime.commit(job['execution_id'])

    def assert_error(self, code, function):
        with self.assertRaises(PalimpsestError) as caught:
            function()
        self.assertEqual(caught.exception.code, code)

    def counts(self):
        with connection(self.dsn) as conn:
            return conn.execute('''SELECT (SELECT count(*) FROM canonical_store.knowledge_nodes) AS nodes,
                (SELECT count(*) FROM canonical_store.knowledge_edges) AS edges,
                (SELECT version FROM compiler_runtime.knowledge_state WHERE singleton) AS version''').fetchone()

    def edge(self):
        helper = edge_fixtures.EffectiveK2KRuntimeTests('runTest')
        helper.dsn, helper.f, helper.runtime = self.dsn, self.f, self.f.runtime
        helper.repo, helper.data_id = self.repo, self.f.data_id
        return helper.create_edge()

    def test_accepted_explanation_preserves_exact_snapshot_without_creating_k(self):
        before = self.counts()
        job = self.prepare()
        result = self.accept(job)
        self.assertEqual(result['wisdom_kind'], 'explanation')
        self.assertEqual(result['used_k_revision_ids'], self.f.premises[:1])
        self.assertEqual(result['used_information_ids'], [])
        self.assertEqual(result['input_sha256'], job['input_snapshot']['input_sha256'])
        self.assertEqual(self.runtime.wisdom(result['wisdom_id']), {k: v for k, v in result.items() if k != 'replayed'})
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.f.source_state(), self.f.source_before)
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM compiler_runtime.w_calls WHERE execution_id=%s',
                (job['execution_id'],)).fetchone()['n'], 2)
        self.assertEqual([event['state'] for event in self.runtime.show(job['execution_id'])['events']],
                         ['prepared', 'proposed', 'validated', 'completed'])

    def test_replay_returns_existing_w_after_graph_changes_and_request_change_conflicts(self):
        identifier = self.repo.allocate_id()
        job = self.prepare(identifier=identifier)
        result = self.accept(job)
        with connection(self.dsn) as conn:
            conn.execute('UPDATE compiler_runtime.knowledge_state SET version=version+1 WHERE singleton')
        replay = self.prepare(identifier=identifier)
        self.assertTrue(replay['replayed'])
        self.assertEqual(replay['wisdom_id'], result['wisdom_id'])
        self.assertEqual(self.runtime.commit(job['execution_id'])['wisdom_id'], result['wisdom_id'])
        self.assert_error('idempotency_conflict', lambda: self.prepare(identifier=identifier, kind='recommendation'))
        other = self.accept(self.prepare())
        self.assertNotEqual(other['wisdom_id'], result['wisdom_id'])

    def test_receipts_require_exact_delivery_output_and_independent_validation(self):
        job = self.prepare()
        answer = self.response(job)
        receipt = self.receipt(job, 'generator', answer)
        for key, value in [('actual_delivery', False), ('delivered_knowledge_revision_ids', []),
                           ('output_sha256', digest('different')), ('schema_sha256', digest('different'))]:
            forged = deepcopy(receipt)
            forged[key] = value
            self.assert_error('wisdom_provider_receipt_mismatch', lambda: self.runtime.stage(job['execution_id'], answer, forged))
        staged = self.runtime.stage(job['execution_id'], answer, receipt)
        verdict = self.validation(answer)
        validation_receipt = self.receipt(staged, 'validator', verdict)
        validation_receipt['provider_ref'] = receipt['provider_ref']
        self.assert_error('wisdom_validator_not_independent', lambda: self.runtime.validate(job['execution_id'], verdict, validation_receipt))
        self.assertEqual(self.runtime.show(job['execution_id'])['state'], 'proposed')

    def test_stale_read_set_blocks_w_commit_without_repair_or_canonical_effect(self):
        job = self.prepare()
        answer = self.response(job)
        staged = self.runtime.stage(job['execution_id'], answer, self.receipt(job, 'generator', answer))
        verdict = self.validation(answer)
        self.runtime.validate(job['execution_id'], verdict, self.receipt(staged, 'validator', verdict))
        with connection(self.dsn) as conn:
            conn.execute('UPDATE compiler_runtime.knowledge_state SET version=version+1 WHERE singleton')
        self.assert_error('wisdom_knowledge_state_changed', lambda: self.runtime.commit(job['execution_id']))
        self.assertEqual(self.runtime.show(job['execution_id'])['state'], 'validated')
        self.assertEqual(self.f.source_state(), self.f.source_before)

    def test_negative_validation_is_retained_without_w_and_exact_replay_is_safe(self):
        job = self.prepare()
        answer = self.response(job)
        staged = self.runtime.stage(job['execution_id'], answer, self.receipt(job, 'generator', answer))
        verdict = self.validation(answer)
        verdict.update(verdict='needs_human', reason='Need a semantic review of the reported scope.')
        verdict['claims'][0]['supported'] = False
        receipt = self.receipt(staged, 'validator', verdict)
        held = self.runtime.validate(job['execution_id'], verdict, receipt)
        self.assertEqual(held['state'], 'needs_human')
        self.assertEqual(held['validator_response'], verdict)
        self.assertTrue(self.runtime.validate(job['execution_id'], verdict, receipt)['replayed'])
        self.assert_error('wisdom_not_validated', lambda: self.runtime.commit(job['execution_id']))

    def test_selected_edge_expands_both_endpoints_and_retains_typed_effective_refs(self):
        edge = self.edge()
        job = self.prepare(edge_revision_ids=[edge])
        result = self.accept(job)
        self.assertEqual(len(job['input_snapshot']['nodes']), 2)
        self.assertEqual(result['used_k_revision_ids'], self.f.premises + [edge])
        self.assertEqual(result['used_effective_edge_refs'], [job['input_snapshot']['effective_edges'][0]['effective_edge_ref']])
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM compiler_runtime.w_edge_inputs WHERE execution_id=%s',
                (job['execution_id'],)).fetchone()['n'], 1)

    def test_recommendation_is_advisory_and_cannot_be_decision(self):
        before = self.counts()
        result = self.accept(self.prepare(kind='recommendation'))
        self.assertEqual(result['answer_or_payload']['claims'][0]['epistemic_basis'], 'advisory_recommendation')
        self.assertEqual(self.counts(), before)
        self.assert_error('invalid_k2w_input', lambda: self.prepare(kind='decision'))

    def test_sql_cannot_skip_receipts_or_mutate_w(self):
        job = self.prepare()
        with self.assertRaises(PalimpsestError), connection(self.dsn) as conn:
            conn.execute("UPDATE compiler_runtime.w_jobs SET state='validated' WHERE execution_id=%s", (job['execution_id'],))
        result = self.accept(job)
        for sql in ('UPDATE canonical_store.wisdoms SET snapshot=snapshot WHERE wisdom_id=%s',
                    'DELETE FROM canonical_store.wisdoms WHERE wisdom_id=%s'):
            with self.assertRaises(PalimpsestError), connection(self.dsn) as conn:
                conn.execute(sql, (result['wisdom_id'],))
        self.assertEqual(self.runtime.wisdom(result['wisdom_id'])['input_sha256'], job['input_snapshot']['input_sha256'])

    def test_sql_checks_actual_output_hash_and_generation_to_answer_binding(self):
        job = self.prepare()
        answer = self.response(job)
        receipt = self.receipt(job, 'generator', answer)
        forged = {**receipt, 'output_sha256': digest('not the actual response')}
        with self.assertRaises(PalimpsestError), connection(self.dsn) as conn, conn.transaction():
            self.runtime._call(conn, job, 'generator', answer, forged)
        changed = deepcopy(answer)
        changed['claims'][0]['text'] = 'Forged different factual output not delivered by Generator.'
        prompt, schema = k2w_prompts.validation_request(job['input_snapshot'], changed)
        context = {'input': job['input_snapshot'], 'answer': changed}
        request = self.runtime._request(job['input_snapshot'], prompt, schema, digest(context))
        from palimpsest.wisdom_runtime import _json_text
        request['validation_context_json'] = _json_text(context)
        with self.assertRaises(PalimpsestError), connection(self.dsn) as conn, conn.transaction():
            self.runtime._call(conn, job, 'generator', answer, receipt)
            conn.execute('''UPDATE compiler_runtime.w_jobs SET state='proposed',generator_response=%s,
                generator_receipt=%s,answer=%s,validator_request=%s WHERE execution_id=%s''',
                (Jsonb(answer), Jsonb(receipt), Jsonb(changed), Jsonb(request), job['execution_id']))
        self.assertEqual(self.runtime.show(job['execution_id'])['state'], 'prepared')
        self.accept(job)

    def test_sql_rejects_missing_input_contract_and_mismatched_canonical_text(self):
        job = self.prepare()
        with connection(self.dsn) as conn:
            for packet, raw in [({}, '{}'), (job['input_snapshot'], '{}')]:
                with self.assertRaises(PalimpsestError), connection(self.dsn) as attempt:
                    attempt.execute('''INSERT INTO compiler_runtime.w_jobs
                        (request_id,request_fingerprint,profile_id,input_snapshot,input_json,expected_state_version,generator_request)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)''', (self.repo.allocate_id(), digest('forged'), job['profile_id'],
                        Jsonb(packet), raw, job['expected_state_version'], Jsonb(job['generator_request'])))

    def test_exact_json_hashes_and_normalization_survive_unicode_and_small_floats(self):
        job = self.runtime.prepare(self.repo.allocate_id(), query='이 근거를 설명해 줘.',
            context_snapshot={'weight': 1e-7, 'label': '원문 조건'}, revision_ids=self.f.premises[:1])
        answer = self.response(job)
        answer['claims'][0]['text'] = '\u3000e\u0301 보고 내용 \t'
        staged = self.runtime.stage(job['execution_id'], answer, self.receipt(job, 'generator', answer))
        self.assertEqual(staged['answer']['claims'][0]['text'], 'é 보고 내용')
        verdict = self.validation(staged['answer'])
        verdict['reason'] = '\u3000e\u0301 검토 \n'
        self.runtime.validate(job['execution_id'], verdict, self.receipt(staged, 'validator', verdict))
        result = self.runtime.commit(job['execution_id'])
        self.assertEqual(result['validation']['reason'], 'é 검토')
        self.assertEqual(result['context_snapshot'], {'weight': 1e-7, 'label': '원문 조건'})

    def test_prepared_call_export_is_repeatable_and_not_a_delivery(self):
        job = self.prepare()
        directory = self.f.base / 'wisdom-call'
        prepared = self.runtime.prepare_call(job['execution_id'], 'generator', directory)
        self.assertFalse(prepared['actual_delivery'])
        self.assertTrue(self.runtime.prepare_call(job['execution_id'], 'generator', directory)['replayed'])
        request = json.loads((directory / 'generator-request.json').read_text())
        self.assertEqual(request['delivered_knowledge_revision_ids'], self.f.premises[:1])
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM compiler_runtime.w_calls WHERE execution_id=%s',
                (job['execution_id'],)).fetchone()['n'], 0)

    def test_sql_preserves_used_edge_union_and_uncertainty(self):
        from unittest.mock import patch
        from palimpsest import wisdom
        edge = self.edge()
        job = self.prepare(edge_revision_ids=[edge])
        answer = self.response(job)
        staged = self.runtime.stage(job['execution_id'], answer, self.receipt(job, 'generator', answer))
        verdict = self.validation(answer)
        self.runtime.validate(job['execution_id'], verdict, self.receipt(staged, 'validator', verdict))
        original = wisdom.build_snapshot
        def altered(fault, **kwargs):
            value = original(**kwargs)
            if fault == 'missing_edge':
                value['used_effective_edge_refs'] = []
            elif fault == 'duplicate_edge':
                value['used_effective_edge_refs'] *= 2
            elif fault == 'limits':
                value['uncertainty']['claims'][0]['limitations'] = []
            else:
                value['epistemic_basis'] = 'decision'
            value['snapshot_sha256'] = digest({k: v for k, v in value.items() if k != 'snapshot_sha256'})
            return value
        for fault in ('missing_edge', 'duplicate_edge', 'limits', 'basis'):
            with self.subTest(fault=fault), patch.object(wisdom, 'build_snapshot', side_effect=lambda **kw: altered(fault, **kw)):
                self.assert_error('database_error', lambda: self.runtime.commit(job['execution_id']))
        self.assertEqual(len(self.runtime.commit(job['execution_id'])['used_effective_edge_refs']), 1)
