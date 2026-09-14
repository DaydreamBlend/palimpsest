"""Selection persistence in caller-provisioned PG, with synthetic LLM receipts."""

from copy import deepcopy
from hashlib import sha256
import os
import struct
import unittest
from unittest.mock import patch
import zlib

from palimpsest.canonical_store import connection
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.i2k_selection import selection_schema, selection_decision_schema
from palimpsest import selection_prompts
import test_knowledge_runtime as fixtures


@unittest.skipUnless(os.environ.get('PALIMPSEST_TEST_DSN'), 'Requires explicitly provisioned PALIMPSEST_TEST_DSN')
class SelectionRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.helper = self._fixture()
        self.runtime, self.packet = self.helper.runtime, self.helper.packet
        self.data_id, self.dsn = self.helper.data_id, self.helper.dsn

    def _fixture(self):
        helper = fixtures.KnowledgeRuntimeTests('runTest')
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        from test_source_reconstruction import visuals_for
        source = helper.fixture
        _, parsed, _ = source.runtime._source_snapshot(helper.packet['source_execution_id'])
        visuals = visuals_for(parsed['bundle'])
        visuals['source']['pdf_size_bytes'] = (source.base / 'source.pdf').stat().st_size
        width, height = 1200, 1600
        def chunk(kind, body):
            return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body))
        png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
        png += chunk(b'IDAT', zlib.compress((b'\x00' + b'\xff\xff\xff' * width) * height)) + chunk(b'IEND', b'')
        image = visuals['pages'][0]['page_image']
        image.update(sha256=sha256(png).hexdigest(), size_bytes=len(png), pixel_size=[width, height])
        directory = source.base / 'selection-page-fixture'
        (directory / 'pages').mkdir(parents=True)
        (directory / image['path']).write_bytes(png)
        evidence = {'source_bundle': parsed['bundle'], 'visuals': visuals,
                    'manifest_sha256': 'e' * 64, 'asset_base_directory': str(directory)}
        with patch('palimpsest.pdf_evidence.read_evidence', return_value=evidence):
            grouped = source.runtime.add_source_pages(helper.packet['source_execution_id'], directory)
        helper.packet = source.runtime.prepare_input(grouped['execution_id'])
        units = [unit for unit in helper.packet['model_input']['information']
                 if unit['unit_type'] != 'page_image' and unit['content']]
        helper.text, helper.other = units[:2]
        return helper

    def prepare(self, helper=None, packet=None):
        helper = helper or self.helper
        return helper.runtime.prepare('i2k', helper.data_id, helper.repo.allocate_id(),
                                      packet or helper.packet, selection=True, source_review=False)

    def response(self, helper=None, *, general=False, empty=False):
        helper = helper or self.helper
        result = helper.response()
        if empty:
            result['nodes'] = []
        for node in result['nodes']:
            node.update(identity_scope='general' if general and node['kind'] == 'proposition' else 'source',
                        selection_reason='Useful synthetic claim for this storage check.')
            if node['identity_scope'] == 'general':
                node['semantic_payload']['subject'] = 'Shared general fixture concept'
        self.reviews(result, helper.packet)
        return result

    @staticmethod
    def reviews(response, packet):
        response['reviews'] = []
        for unit in packet['model_input']['information']:
            keys = [node['candidate_key'] for node in response['nodes']
                    if any(e['information_id'] == unit['information_id'] for e in node['evidence'])]
            response['reviews'].append({'information_id': unit['information_id'],
                'disposition': 'selected' if keys else 'context_only', 'candidate_keys': keys,
                'reason': 'Synthetic review: selected evidence.' if keys else 'Synthetic review: contextual source content.'})

    def decisions(self, response):
        result = self.helper.decisions(response)
        for item in result['decisions']:
            item.update(scope_correct=True, importance_justified=True)
        result['reviews'] = [{'information_id': r['information_id'], 'verdict': 'confirmed',
            'reason_codes': ['synthetic_review'], 'reason': 'Synthetic independent review, no model called.'}
            for r in response['reviews']]
        return result

    def receipt(self, helper, input_sha, response):
        result = helper.receipt(input_sha, response)
        ids = [unit['information_id'] for unit in helper.packet['model_input']['information']]
        result['delivered_information_ids'] = ids
        with connection(helper.dsn) as conn:
            row = conn.execute('''SELECT execution_id FROM compiler_runtime.k_execution_contexts
                WHERE input_digest=%s OR validation_context_sha=%s ORDER BY created_at DESC LIMIT 1''',
                (input_sha, input_sha)).fetchone()
        job = helper.runtime.show(row['execution_id'])
        snapshot = job['input_snapshot']
        if input_sha == job['input_digest']:
            prompt = selection_prompts.generation(snapshot, result['image_attachments'])
            schema = selection_schema(ids, [asset['sha256'] for asset in helper.packet['media_assets']])
        else:
            context = helper.runtime.validation_context(row['execution_id'])
            prompt = selection_prompts.validation(context, result['image_attachments'])
            schema = selection_decision_schema([node['candidate_key'] for node in context['candidates']],
                [node['knode_revision_id'] for node in snapshot['existing_nodes']], ids)
        result.update(prompt_sha256=sha256(prompt.encode('utf-8')).hexdigest(), schema_sha256=digest(schema))
        return result

    def stage(self, job, response, helper=None):
        helper = helper or self.helper
        return helper.runtime.stage(job['execution_id'], response, self.receipt(helper, job['input_digest'], response))

    def commit(self, job, response, decisions=None, helper=None):
        helper = helper or self.helper
        context = self.stage(job, response, helper)
        decisions = decisions or self.decisions(response)
        return helper.runtime.decide(job['execution_id'], decisions,
            self.receipt(helper, context['validation_context_sha'], decisions))

    def error(self, code, call):
        with self.assertRaises(PalimpsestError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_all_i_review_selection_scope_and_same_meaning_rerun_reuse(self):
        response = self.response()
        first = self.commit(self.prepare(), response)
        self.assertEqual(first['state'], 'completed')
        self.assertEqual(len(first['information_reviews']), len(self.packet['model_input']['information']))
        self.assertEqual(len(first['information_review_decisions']), len(first['information_reviews']))
        self.assertEqual(len(first['information_review_records']), 2)
        before = self.runtime.graph(self.data_id)
        self.assertEqual({(n['identity_scope'], n['source_data_id']) for n in before['nodes']}, {('source', self.data_id)})
        decisions = self.decisions(response)
        for item, record in zip(decisions['decisions'], first['records']):
            item.update(verdict='reused', equivalent_revision_id=record['result_node_revision_id'])
        again = self.commit(self.prepare(), response, decisions)
        self.assertEqual([r['disposition'] for r in again['records']], ['reused', 'reused'])
        after = self.runtime.graph(self.data_id)
        self.assertEqual(before['node_revisions'], after['node_revisions'])
        self.assertEqual(before['groundings'], after['groundings'])

    def test_legacy_reuse_binds_scope_without_rewriting_uuid_fp_or_revision(self):
        legacy = self.helper.accept(self.helper.prepare())
        before = self.runtime.graph(self.data_id)
        self.assertTrue(all(node['identity_scope'] is None for node in before['nodes']))
        response = self.response()
        decisions = self.decisions(response)
        for item, record in zip(decisions['decisions'], legacy['records']):
            item.update(verdict='reused', equivalent_revision_id=record['result_node_revision_id'])
        result = self.commit(self.prepare(), response, decisions)
        after = self.runtime.graph(self.data_id)
        self.assertEqual([r['disposition'] for r in result['records']], ['reused', 'reused'])
        self.assertEqual(before['node_revisions'], after['node_revisions'])
        self.assertTrue(all(node['identity_scope'] == 'source' for node in after['nodes']))

    def test_source_reuse_cannot_cross_data_but_general_equivalence_can(self):
        response_a = self.response(general=True)
        first = self.commit(self.prepare(), response_a)
        other = self._fixture()
        response_b = self.response(other, general=True)
        decisions = self.decisions(response_b)
        for item, record in zip(decisions['decisions'], first['records']):
            item.update(verdict='reused', equivalent_revision_id=record['result_node_revision_id'])
        job = self.prepare(other)
        context = self.stage(job, response_b, other)
        receipt = self.receipt(other, context['validation_context_sha'], decisions)
        self.error('knowledge_scope_reuse_conflict', lambda: other.runtime.decide(job['execution_id'], decisions, receipt))
        self.assertEqual(other.runtime.graph(other.data_id)['nodes'], [])
        decisions['decisions'][0].update(verdict='accepted', equivalent_revision_id=None)
        committed = other.runtime.decide(job['execution_id'], decisions,
            self.receipt(other, context['validation_context_sha'], decisions))
        self.assertEqual([record['disposition'] for record in committed['records']], ['accepted_new', 'reused'])
        self.assertEqual(committed['records'][1]['result_node_id'], first['records'][1]['result_node_id'])
        self.assertNotEqual(committed['records'][0]['result_node_id'], first['records'][0]['result_node_id'])

    def test_no_k_still_requires_all_i_generator_and_validator_reviews(self):
        response = self.response(empty=True)
        result = self.commit(self.prepare(), response)
        self.assertEqual(result['state'], 'zero_output')
        self.assertEqual(result['records'], [])
        self.assertEqual(len(result['information_review_decisions']), len(self.packet['model_input']['information']))
        self.assertEqual(self.runtime.graph(self.data_id)['nodes'], [])

    def test_unresolved_i_review_preserves_independently_accepted_k_without_claiming_complete(self):
        response = self.response()
        decisions = self.decisions(response)
        decisions['complete'] = False
        affected = response['nodes'][0]['evidence'][0]['information_id']
        for review in decisions['reviews']:
            if review['information_id'] == affected:
                review.update(verdict='needs_review', reason='The synthetic review found another important experiment not yet extracted.')
        result = self.commit(self.prepare(), response, decisions)
        self.assertEqual(result['state'], 'needs_human')
        self.assertEqual([r['disposition'] for r in result['records']], ['accepted_new', 'accepted_new'])
        self.assertIsNone(result['records'][0]['body'])
        feedback = self.runtime.prepare('i2k', self.data_id, self.helper.repo.allocate_id(), self.packet,
            selection=True, source_review=False, feedback_execution_id=result['execution_id'])['input_snapshot']['selection_feedback']
        self.assertTrue(any(review['verdict'] == 'needs_review' for review in feedback['validator_reviews']))

    def test_false_complete_with_confirmed_reviews_still_remains_unfinished(self):
        response = self.response()
        decisions = self.decisions(response)
        decisions['complete'] = False
        result = self.commit(self.prepare(), response, decisions)
        self.assertEqual(result['state'], 'needs_human')
        self.assertEqual([record['disposition'] for record in result['records']], ['accepted_new', 'accepted_new'])

    def test_late_validator_failure_receipt_can_be_recovered_without_effects(self):
        job = self.prepare()
        response = self.response()
        context = self.stage(job,response)
        decisions = self.decisions(response)
        receipt = self.receipt(self.helper,context['validation_context_sha'],decisions)
        self.runtime.fail_execution(job['execution_id'],'invalid_knowledge_decision')
        saved = self.runtime.record_call_failure(job['execution_id'],'validator',receipt,'invalid_knowledge_decision')
        self.assertEqual(saved['state'],'failed')
        replay = self.runtime.record_call_failure(job['execution_id'],'validator',receipt,'invalid_knowledge_decision')
        self.assertEqual(saved['call_id'],replay['call_id'])
        self.assertEqual(self.runtime.graph(self.data_id)['nodes'],[])

    def test_failed_validator_logging_uses_the_exact_frozen_context(self):
        response, job = self.response(), self.prepare()
        context = self.stage(job, response)
        malformed = self.decisions(response)
        malformed['decisions'].pop()
        receipt = self.receipt(self.helper, context['validation_context_sha'], malformed)
        self.error('invalid_knowledge_decision', lambda: self.runtime.decide(job['execution_id'], malformed, receipt))
        failed = self.runtime.record_call_failure(job['execution_id'], 'validator', receipt,
            'invalid_knowledge_decision', response=malformed)
        self.assertEqual(failed['status'], 'failed')
        self.assertEqual(self.runtime.validation_context(job['execution_id']), context)

    def test_identical_delivered_generator_can_be_replayed_into_a_new_profile(self):
        original = self.prepare()
        response = self.response()
        receipt = self.receipt(self.helper, original['input_digest'], response)
        changed_signature = deepcopy(original['profile']['selection_implementation_sha256'])
        changed_signature['i2k_selection.py'] = 'a' * 64
        with patch('palimpsest.knowledge_runtime._selection_implementation', return_value=changed_signature):
            successor = self.prepare()
            self.assertNotEqual(successor['profile_id'], original['profile_id'])
            self.assertEqual(successor['input_digest'], original['input_digest'])
            result = self.runtime.stage(successor['execution_id'], response, receipt)
        self.assertEqual(len(result['candidates']), len(response['nodes']))

    def test_subset_and_missing_review_are_rejected_before_any_selection_effect(self):
        subset = self.helper.fixture.runtime.prepare_input(self.packet['source_execution_id'],
            information_ids=[self.packet['target_information_ids'][0]])
        self.error('selection_requires_all_information', lambda: self.prepare(packet=subset))
        response = self.response()
        response['reviews'].pop()
        job = self.prepare()
        self.error('selection_review_coverage_mismatch', lambda: self.stage(job, response))
        self.assertEqual(self.runtime.show(job['execution_id'])['information_reviews'], [])
        self.assertEqual(self.runtime.show(job['execution_id'])['records'], [])

    def test_image_only_evidence_has_zero_text_range_and_owned_delivered_media(self):
        response = self.response()
        unit = next(item for item in self.packet['model_input']['information'] if item['media'])
        response['nodes'][0]['evidence'] = [{'information_id': unit['information_id'], 'quote': '',
            'media_sha256': unit['media'][0]['sha256'], 'source_role': 'figure'}]
        self.reviews(response, self.packet)
        result = self.commit(self.prepare(), response)
        self.assertEqual(result['state'], 'completed')
        groundings = self.runtime.graph(self.data_id)['groundings']
        media = next(g for g in groundings if g['media_sha256'] is not None)
        self.assertEqual((media['quote'], media['char_start'], media['char_end']), ('', 0, 0))

    def test_every_i_must_have_actual_delivery_receipt_in_both_model_phases(self):
        job, response = self.prepare(), self.response()
        receipt = self.receipt(self.helper, job['input_digest'], response)
        receipt['delivered_information_ids'].pop()
        self.error('knowledge_information_delivery_mismatch',
                   lambda: self.runtime.stage(job['execution_id'], response, receipt))
        self.assertEqual(self.runtime.show(job['execution_id'])['information_reviews'], [])
        prompt_forged = self.receipt(self.helper, job['input_digest'], response)
        omitted_source = deepcopy(job['input_snapshot'])
        omitted_source['input']['model_input']['information'].pop()
        prompt_forged['prompt_sha256'] = sha256(selection_prompts.generation(omitted_source,
            prompt_forged['image_attachments']).encode('utf-8')).hexdigest()
        self.error('knowledge_prompt_delivery_mismatch',
                   lambda: self.runtime.stage(job['execution_id'], response, prompt_forged))
        context = self.stage(job, response)
        decisions = self.decisions(response)
        receipt = self.receipt(self.helper, context['validation_context_sha'], decisions)
        receipt['delivered_information_ids'] = list(reversed(receipt['delivered_information_ids']))
        self.error('knowledge_information_delivery_mismatch',
                   lambda: self.runtime.decide(job['execution_id'], decisions, receipt))
        self.assertEqual(self.runtime.show(job['execution_id'])['information_review_decisions'], [])

    def test_feedback_is_frozen_bound_to_request_and_keeps_full_source(self):
        response = self.response()
        decisions = self.decisions(response)
        decisions['reviews'][0].update(verdict='needs_review', reason='Review this I again for missed limitations.')
        prior = self.commit(self.prepare(), response, decisions)
        self.assertEqual(prior['state'], 'needs_human')
        request_id = self.helper.repo.allocate_id()
        kwargs = {'selection': True, 'source_review': False, 'feedback_execution_id': prior['execution_id']}
        job = self.runtime.prepare('i2k', self.data_id, request_id, self.packet, **kwargs)
        feedback = job['input_snapshot']['selection_feedback']
        self.assertEqual(feedback['execution_id'], prior['execution_id'])
        self.assertEqual(len(feedback['validator_reviews']), len(self.packet['model_input']['information']))
        self.assertNotIn('body', feedback)
        self.assertEqual(job['input_snapshot']['input']['target_information_ids'], self.packet['target_information_ids'])
        self.assertTrue(self.runtime.prepare('i2k', self.data_id, request_id, self.packet, **kwargs)['replayed'])
        self.error('idempotency_conflict', lambda: self.runtime.prepare('i2k', self.data_id, request_id, self.packet, selection=True))
        other = self._fixture()
        self.error('invalid_selection_feedback', lambda: other.runtime.prepare('i2k', other.data_id,
            other.repo.allocate_id(), other.packet, **kwargs))

    def test_auto_profile_uses_selection_for_new_i2k_but_replays_legacy_request(self):
        auto = self.runtime.prepare('i2k', self.data_id, self.helper.repo.allocate_id(), self.packet, selection=None)
        self.assertEqual(auto['profile']['schema_version'], 'source-complete-i2k-v1')
        self.assertEqual(auto['profile']['source_review'], 'source-review-v1')
        legacy = self.helper.prepare()
        replay = self.runtime.prepare('i2k', self.data_id, legacy['request_id'], self.packet, selection=None)
        self.assertTrue(replay['replayed'])
        self.assertEqual(replay['profile']['schema_version'], 'paper-claims-v1')

    def test_failed_quote_feedback_is_bound_and_repeatable_without_candidate_effects(self):
        job = self.prepare()
        response = self.response()
        response['nodes'][0]['evidence'][0]['quote'] += ' absent suffix'
        receipt = self.receipt(self.helper, job['input_digest'], response)
        self.error('knowledge_quote_mismatch', lambda:self.runtime.stage(job['execution_id'],response,receipt))
        failed = self.runtime.record_call_failure(job['execution_id'],'generator',receipt,
            'knowledge_quote_mismatch',response=response)
        self.runtime.fail_execution(job['execution_id'],'knowledge_quote_mismatch')
        same = self.runtime.record_call_failure(job['execution_id'],'generator',receipt,
            'knowledge_quote_mismatch',response=response)
        self.assertEqual(same['call_id'],failed['call_id'])
        identifier = self.helper.repo.allocate_id()
        kwargs = {'selection':True,'source_review':False,'feedback_execution_id':job['execution_id']}
        repair = self.runtime.prepare('i2k',self.data_id,identifier,self.packet,**kwargs)
        feedback = repair['input_snapshot']['selection_feedback']['failed_generator']
        self.assertEqual(feedback['call_id'],failed['call_id'])
        self.assertEqual(feedback['issues'][0]['proposed_quote'],response['nodes'][0]['evidence'][0]['quote'])
        self.assertTrue(self.runtime.prepare('i2k',self.data_id,identifier,self.packet,**kwargs)['replayed'])
        self.assertEqual(self.runtime.graph(self.data_id)['nodes'],[])

    def test_pdf_selection_requires_original_page_information(self):
        import test_source_runtime_integration as source_fixtures
        source = source_fixtures.SourceRuntimeIntegrationTests('runTest')
        source.dsn = self.dsn
        source.setUp()
        self.addCleanup(source.doCleanups)
        execution_id = source._prepared()
        source.runtime.materialize_source(execution_id)
        packet = source.runtime.prepare_input(execution_id)
        self.error('source_page_information_required',lambda:self.runtime.prepare(
            'i2k',source.data_id,self.helper.repo.allocate_id(),packet,selection=True))

    def test_new_legacy_reuse_also_respects_cross_source_classification(self):
        legacy_response = self.helper.response()
        legacy = self.helper.accept(self.helper.prepare(), legacy_response)
        other = self._fixture()
        response_b = other.response()
        job_b = other.prepare()
        context_b = other.stage(job_b, response_b)
        decisions_b = other.decisions(response_b)
        for item, record in zip(decisions_b['decisions'], legacy['records']):
            item.update(verdict='reused', equivalent_revision_id=record['result_node_revision_id'])
        held = other.runtime.decide(job_b['execution_id'], decisions_b,
            other.receipt(context_b['validation_context_sha'], decisions_b))
        self.assertEqual([record['disposition'] for record in held['records']], ['needs_human', 'needs_human'])
        self.assertEqual(other.runtime.graph(other.data_id)['nodes'], [])

        selection_response = self.response()
        selection_response['nodes'][1]['identity_scope'] = 'general'
        classified = self.decisions(selection_response)
        for item, record in zip(classified['decisions'], legacy['records']):
            item.update(verdict='reused', equivalent_revision_id=record['result_node_revision_id'])
        self.commit(self.prepare(), selection_response, classified)
        duplicate = other.response()
        for new, original in zip(duplicate['nodes'], legacy_response['nodes']):
            new['semantic_payload'] = deepcopy(original['semantic_payload'])
        result = other.accept(other.prepare(), duplicate)
        self.assertEqual([record['disposition'] for record in result['records']], ['needs_human', 'reused'])
        self.assertEqual(result['records'][1]['result_node_id'], legacy['records'][1]['result_node_id'])
        replay = self.runtime.decide(legacy['execution_id'], self.helper.decisions(legacy_response), legacy['validator_receipt'])
        self.assertEqual(replay['state'], 'completed')


if __name__ == '__main__':
    unittest.main()
