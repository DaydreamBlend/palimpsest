"""I-only I2K error/hold behavior in an explicitly isolated PG fixture.

All source data, model outputs and delivery receipts are synthetic. These tests
exercise real Runtime persistence, not provider execution or semantic quality.
They never repair Information, fetch original Data, or migrate a database.
"""

from contextlib import contextmanager, ExitStack
from copy import deepcopy
from hashlib import sha256
import os
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

from palimpsest.canonical_store import connection
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.information_errors import POLICY, REASON_CODES
from palimpsest.knowledge_requests import generation_request, validation_request
from palimpsest.knowledge_review import KnowledgeReview

import test_multi_source_runtime as fixtures
import test_source_review_runtime as source_reviews


@contextmanager
def no_source_fallback():
    """After fixture setup, even attempting source repair/read is a test failure."""
    targets = (
        'palimpsest.artifact_store.ArtifactStore.read',
        'palimpsest.compiler_runtime.CompilerRuntime.compile_markdown',
        'palimpsest.compiler_runtime.CompilerRuntime.compile_code',
        'palimpsest.compiler_runtime.CompilerRuntime.add_source_pages',
        'palimpsest.compiler_runtime.CompilerRuntime.prepare_input',
        'palimpsest.codex_provider.CodexProvider.generate',
    )
    with ExitStack() as stack:
        trapped = [stack.enter_context(patch(target, side_effect=AssertionError(
            'I2K must hold insufficient Information without original-D access, D2I, or a provider call')))
            for target in targets]
        yield
        for operation in trapped:
            operation.assert_not_called()


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires the explicitly isolated Linux PostgreSQL fixture named palimpsest')
class InformationErrorRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with connection(os.environ['PALIMPSEST_TEST_DSN']) as conn:
            if conn.execute('SELECT current_database() AS name').fetchone()['name'] != 'palimpsest':
                raise RuntimeError('Information error tests require the isolated database named palimpsest')

    def setUp(self):
        self.fixture = fixtures.MultiSourceRuntimeTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.runtime, self.dsn = self.fixture.runtime, self.fixture.dsn
        self.bundle = self.fixture.bundle
        self.first, self.second = self.fixture.first, self.fixture.second

    def prepare(self, request=None, **kwargs):
        job = self.runtime.prepare('i2k', self.bundle['data_id'], request or self.first.repo.allocate_id(),
            self.bundle, selection=True, source_review=False, **kwargs)
        self.assertEqual(job['profile']['information_error_policy'], POLICY)
        self.assertEqual(job['input_snapshot']['information_error_policy'], POLICY)
        return job

    def receipt(self, job, output, phase):
        current = self.runtime.show(job['execution_id'])
        snapshot = current['input_snapshot']
        attachments = [{key: asset[key] for key in ('sha256', 'byte_size')}
                       for asset in snapshot['input']['media_assets']]
        if phase == 'generator':
            prompt, schema = generation_request(snapshot, attachments)
            input_sha = current['input_digest']
        else:
            context = self.runtime.validation_context(job['execution_id'])
            prompt, schema = validation_request(context, attachments)
            input_sha = context['validation_context_sha']
        return {'profile': {**current['profile']['model'], 'synthetic_receipt': True},
            'input_sha256': input_sha, 'output_sha256': digest(output),
            'prompt_sha256': sha256(prompt.encode('utf-8')).hexdigest(), 'schema_sha256': digest(schema),
            'provider_ref': 'synthetic-no-provider-' + str(uuid4()), 'actual_delivery': True,
            'delivered_information_ids': list(self.bundle['target_information_ids']),
            'image_attachments': attachments, 'original_pdf_delivered': False,
            'usage': {}, 'test_only': True}

    def stage(self, job, response):
        receipt = self.receipt(job, response, 'generator')
        self.runtime.stage(job['execution_id'], response, receipt)
        return receipt

    def commit(self, job, response, decisions=None):
        generated = self.stage(job, response)
        decisions = decisions or self.fixture.decisions(response)
        validated = self.receipt(job, decisions, 'validator')
        return self.runtime.decide(job['execution_id'], decisions, validated), generated, validated

    def source_state(self):
        owners = sorted(self.fixture.data_ids)
        with connection(self.dsn) as conn:
            return {
                'data': conn.execute('SELECT * FROM canonical_store.data WHERE data_id=ANY(%s::text[]) ORDER BY data_id',
                                     (owners,)).fetchall(),
                'information': conn.execute('SELECT * FROM canonical_store.information WHERE data_id=ANY(%s::text[]) ORDER BY information_id',
                                            (owners,)).fetchall(),
                'executions': conn.execute("SELECT * FROM compiler_runtime.operation_executions WHERE operation='d2i' AND data_id=ANY(%s::text[]) ORDER BY execution_id",
                                           (owners,)).fetchall(),
                'records': conn.execute('''SELECT r.* FROM compiler_runtime.records r
                    WHERE r.record_id IN (SELECT origin_record_id FROM canonical_store.information
                        WHERE data_id=ANY(%s::text[])) ORDER BY r.record_id''', (owners,)).fetchall()}

    def request_for_first_source(self):
        return {'data_id': self.first.data_id, 'information_ids': [self.first.text['information_id']],
                'page_numbers': [], 'question': 'Synthetic D2I information error: the retained transcription is incomplete.'}

    def assert_scoped_hold(self, result, response, *, unrelated_disposition='accepted_new'):
        # Terminal candidate bodies are deliberately discarded. Bind the
        # retained Records to the frozen emitted candidate order instead.
        keys = [node['candidate_key'] for node in response['nodes']]
        self.assertEqual([record['ordinal'] for record in result['records']], list(range(len(keys))))
        self.assertEqual(len({record['record_id'] for record in result['records']}), len(keys))
        records = {keys[record['ordinal']]: record for record in result['records']}
        self.assertEqual(result['state'], 'needs_human')
        for key in ('shared_general', 'observation_a'):
            self.assertEqual(records[key]['disposition'], 'needs_human')
            self.assertIsNone(records[key]['result_node_revision_id'])
        self.assertEqual(records['observation_b']['disposition'], unrelated_disposition)
        self.assertIsNone(records['observation_b']['body'])
        revision = records['observation_b']['result_node_revision_id']
        with connection(self.dsn) as conn:
            groundings = conn.execute('''SELECT g.*,i.data_id FROM canonical_store.knowledge_node_groundings g
                JOIN canonical_store.information i USING(information_id) WHERE node_revision_id=%s''', (revision,)).fetchall()
        self.assertTrue(groundings)
        self.assertEqual({row['data_id'] for row in groundings}, {self.second.data_id})
        self.assertTrue(all(row['information_id'] is not None for row in groundings))

    def error_report(self, execution_id):
        result = KnowledgeReview(self.runtime).status(execution_id)['information_errors']
        self.assertEqual(result['schema_version'], 'i2k-information-errors-v1')
        self.assertEqual(result['execution_id'], execution_id)
        self.assertEqual(result['d2i_calls'], 0)
        self.assertIs(result['direct_source_compilation_allowed'], False)
        return result

    def assert_first_source_binding(self, error):
        self.assertEqual(error['data_id'], self.first.data_id)
        self.assertEqual(error['source_execution_id'], self.first.packet['source_execution_id'])
        self.assertEqual(error['source_profile_id'], self.first.packet['profile_id'])
        self.assertEqual(error['source_input_sha256'], self.first.packet['input_sha256'])
        self.assertEqual(error['information_ids'], [self.first.text['information_id']])
        self.assertEqual(error['source_refs'], [{'information_id': self.first.text['information_id'],
                                                'source_refs': self.first.text['source_refs']}])
        self.assertEqual(error['status'], 'reported_error')
        self.assertEqual(error['verification_status'], 'verification_pending')

    def test_generator_information_error_holds_only_affected_k_and_preserves_source_receipts(self):
        job, response = self.prepare(), self.fixture.response()
        request = self.request_for_first_source()
        response.update(complete=False, source_requests=[request])
        before = self.source_state()
        with no_source_fallback():
            result, generated, validated = self.commit(job, response)
        self.assert_scoped_hold(result, response)
        self.assertEqual(self.source_state(), before)
        self.assertEqual(result['input_snapshot']['input'], self.bundle)
        self.assertEqual(result['source_requests'][0]['payload'], request)
        self.assertIs(result['source_requests'][0]['receipt']['actual_delivery'], False)
        self.assertEqual(result['generator_receipt']['source_requests'], [request])
        self.assertEqual([call['receipt'] for call in result['model_calls']], [generated, validated])
        self.assertEqual(result['generator_receipt']['delivered_information_ids'], self.bundle['target_information_ids'])
        self.assertIs(result['generator_receipt']['original_pdf_delivered'], False)
        report = self.error_report(job['execution_id'])
        self.assertIs(report['requires_user_review'], True)
        error = next(row for row in report['errors'] if row['reported_by'] == 'generator')
        self.assert_first_source_binding(error)
        self.assertEqual(error['source_request_id'], result['source_requests'][0]['request_id'])
        self.assertEqual(error['reason'], request['question'])

    def test_validator_only_recognized_codes_overrule_acceptance_even_with_confirmed_review(self):
        before = self.source_state()
        unrelated_revision = None
        for code in REASON_CODES:
            for verdict in ('needs_review', 'confirmed'):
                with self.subTest(code=code, verdict=verdict):
                    job, response = self.prepare(), self.fixture.response()
                    decisions = self.fixture.decisions(response)
                    issue = next(row for row in decisions['reviews'] if row['information_id'] == self.first.text['information_id'])
                    issue.update(verdict=verdict, reason_codes=[code],
                                 reason='Synthetic independent validator reported an Information error in this exact I.')
                    if unrelated_revision:
                        decisions['decisions'][2].update(verdict='reused', equivalent_revision_id=unrelated_revision)
                    with no_source_fallback():
                        result, _, _ = self.commit(job, response, decisions)
                    self.assert_scoped_hold(result, response,
                        unrelated_disposition='reused' if unrelated_revision else 'accepted_new')
                    unrelated_revision = result['records'][2]['result_node_revision_id']
                    self.assertEqual(result['source_requests'], [])
                    saved = next(row for row in result['information_review_decisions']
                                 if row['information_id'] == self.first.text['information_id'])
                    self.assertEqual(saved['reason_codes'], [code])
                    self.assertEqual(saved['verdict'], verdict)
                    self.assertEqual(saved['reason'], issue['reason'])
                    report = self.error_report(job['execution_id'])
                    self.assertIs(report['requires_user_review'], True)
                    error = next(row for row in report['errors'] if row['reported_by'] == 'validator')
                    self.assert_first_source_binding(error)
                    self.assertEqual(error['review_verdict'], verdict)
                    self.assertEqual(error['contradictory_verdict'], verdict == 'confirmed')
        self.assertEqual(self.source_state(), before)

    def test_generic_selection_gap_does_not_invalidate_independently_accepted_i_grounded_k(self):
        job, response = self.prepare(), self.fixture.response()
        decisions = self.fixture.decisions(response)
        review = next(row for row in decisions['reviews'] if row['information_id'] == self.first.text['information_id'])
        review.update(verdict='needs_review', reason_codes=['missing_material_content'],
                      reason='Synthetic K selection gap; the Information itself contains the source content.')
        before = self.source_state()
        with no_source_fallback():
            result, _, _ = self.commit(job, response, decisions)
        self.assertEqual(result['state'], 'needs_human')
        self.assertEqual([row['disposition'] for row in result['records']], ['accepted_new'] * 3)
        self.assertEqual(result['source_requests'], [])
        self.assertEqual(self.source_state(), before)
        report = self.error_report(job['execution_id'])
        self.assertEqual(report['errors'], [])
        self.assertIs(report['requires_user_review'], False)

    def test_forbidden_direct_or_null_information_candidates_never_stage_or_fetch_original(self):
        before = self.source_state()
        for invalid in ('direct_evidence', 'null_information', 'empty_evidence'):
            with self.subTest(invalid=invalid):
                job, response = self.prepare(), self.fixture.response()
                if invalid == 'direct_evidence':
                    response['nodes'][0]['direct_evidence'] = [{'data_id': self.first.data_id, 'quote': 'forbidden'}]
                elif invalid == 'null_information':
                    response['nodes'][0]['evidence'][0]['information_id'] = None
                else:
                    response['nodes'][0]['evidence'] = []
                with no_source_fallback(), self.assertRaises(PalimpsestError):
                    self.stage(job, response)
                retained = self.runtime.show(job['execution_id'])
                self.assertEqual(retained['state'], 'prepared')
                self.assertEqual(retained['records'], [])
                self.assertEqual(retained['model_calls'], [])
                self.assertEqual(retained['source_requests'], [])
        self.assertEqual(self.source_state(), before)

    def test_empty_and_proposed_error_rounds_have_no_automatic_source_compilation(self):
        job, response = self.prepare(), self.fixture.response()
        response.update(nodes=[], complete=False, source_requests=[self.request_for_first_source()])
        for review in response['reviews']:
            review.update(disposition='context_only', candidate_keys=[])
        before = self.source_state()
        with no_source_fallback():
            self.stage(job, response)
            proposed = self.runtime.show(job['execution_id'])
            self.assertEqual(proposed['state'], 'proposed')
            self.assertEqual(proposed['records'], [])
            broken = self.fixture.decisions(response)
            broken['reviews'] = []
            with self.assertRaises(PalimpsestError):
                self.runtime.decide(job['execution_id'], broken, self.receipt(job, broken, 'validator'))
            self.assertEqual(self.runtime.show(job['execution_id'])['state'], 'proposed')
            valid = self.fixture.decisions(response)
            result = self.runtime.decide(job['execution_id'], valid, self.receipt(job, valid, 'validator'))
        self.assertEqual(result['state'], 'needs_human')
        self.assertEqual(result['records'], [])
        self.assertEqual(result['source_requests'], proposed['source_requests'])
        self.assertEqual(self.source_state(), before)

    def test_information_error_blocks_resume_and_preserves_prior_selection_history_and_request_replay(self):
        job, response = self.prepare(), self.fixture.response()
        decisions = self.fixture.decisions(response)
        decisions['reviews'][0].update(verdict='needs_review', reason_codes=['missing_material_content'],
                                       reason='Synthetic unresolved K selection; no Information error.')
        with no_source_fallback():
            parent, _, _ = self.commit(job, response, decisions)
        before = self.source_state()
        request = self.first.repo.allocate_id()
        service = KnowledgeReview(self.runtime)
        with no_source_fallback():
            child = service.prepare_resume(job['execution_id'], request)
            replay = service.prepare_resume(job['execution_id'], request)
            failed_response = deepcopy(response)
            failed_response.update(complete=False, source_requests=[self.request_for_first_source()])
            # A new explicit review may adopt Runtime's current source-review
            # profile; produce the real manifest-bound synthetic test shape.
            failed_response = source_reviews.SourceReviewRuntimeTests.reviewed_response(
                self, child['job'], base=failed_response)
            failed_decisions = source_reviews.SourceReviewRuntimeTests.decisions(
                self, failed_response, multi_source=True)
            for decision, record in zip(failed_decisions['decisions'], parent['records']):
                decision.update(verdict='reused', equivalent_revision_id=record['result_node_revision_id'])
            child_job = child['job']
            result, _, _ = self.commit(child_job, failed_response, failed_decisions)
            with self.assertRaises(PalimpsestError) as held:
                service.prepare_resume(child['execution_id'], self.first.repo.allocate_id())
            self.assertEqual(held.exception.code, 'd2i_information_error_requires_review')
            confirmed = service.prepare_resume(child['execution_id'], self.first.repo.allocate_id(),
                                               retain_information_errors=True)
            self.assertEqual(confirmed['job']['input_snapshot']['selection_feedback']['source_requests'],
                             failed_response['source_requests'])
            status = service.status(child['execution_id'])
            original_replay = self.prepare(request=job['request_id'])
        self.assertEqual(child['execution_id'], replay['execution_id'])
        self.assertEqual(replay['action'], 'replayed')
        self.assertTrue(original_replay['replayed'])
        self.assertEqual(original_replay['input_snapshot'], job['input_snapshot'])
        self.assertEqual(child['job']['input_snapshot']['input'], self.bundle)
        self.assertEqual(child['job']['input_snapshot']['selection_feedback']['execution_id'], job['execution_id'])
        self.assertEqual(status['history'][-1]['execution_id'], job['execution_id'])
        self.assertEqual(status['history'][-1]['source_requests'], parent['source_requests'])
        self.assertEqual(status['history'][-1]['profile'], parent['profile'])
        self.assertEqual(status['source_requests'], result['source_requests'])
        self.assertIs(status['information_errors']['requires_user_review'], True)
        self.assertIs(status['history'][-1]['information_errors']['requires_user_review'], False)
        self.assertEqual(self.source_state(), before)


if __name__ == '__main__':
    unittest.main()
