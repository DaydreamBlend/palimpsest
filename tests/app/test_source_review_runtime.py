"""Generic source-review persistence in the explicitly isolated PostgreSQL fixture.

All claims and review verdicts are labelled synthetic. These tests establish
bindings, atomicity, and replay behavior, not semantic extraction quality.
"""

from copy import deepcopy
from hashlib import sha256
import os
import sys
import unittest
from uuid import uuid4

from palimpsest.canonical_store import connection
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.i2k_selection import normalize_selection
from palimpsest.knowledge_requests import generation_request, validation_request
from palimpsest import multi_source_i2k as multi

import test_selection_runtime as selection_fixtures
import test_multi_source_runtime as multi_fixtures


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires an explicit Linux PostgreSQL fixture database named palimpsest')
class SourceReviewRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with connection(os.environ['PALIMPSEST_TEST_DSN']) as conn:
            if conn.execute('SELECT current_database() AS name').fetchone()['name'] != 'palimpsest':
                raise RuntimeError('Source-review fixtures require the isolated database named palimpsest')

    def setUp(self):
        self.fixture = selection_fixtures.SelectionRuntimeTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.runtime, self.packet, self.helper = self.fixture.runtime, self.fixture.packet, self.fixture.helper
        self.dsn = self.fixture.dsn

    def prepare(self, *, packet=None, request=None, **kwargs):
        packet = packet or self.packet
        return self.runtime.prepare('i2k', packet['data_id'], request or self.helper.repo.allocate_id(),
                                    packet, selection=True, **kwargs)

    def reviewed_response(self, job, base=None):
        """Synthetic per-target accounting; this deliberately makes no importance claim."""
        response = deepcopy(base if base is not None else self.fixture.response())
        packet = job['input_snapshot']['input']
        normalized = (multi.normalize_proposals(response, packet) if packet['schema_version'] == multi.INPUT_SCHEMA
                      else normalize_selection(response, packet))
        reviews = []
        for number, target in enumerate(job['input_snapshot']['source_review_manifest']['targets']):
            anchors, keys = [], []
            for candidate in normalized['nodes']:
                for evidence in candidate['evidence']:
                    if evidence['information_id'] != target['information_id']:
                        continue
                    for start, end in target['char_ranges']:
                        start, end = max(start, evidence['char_start']), min(end, evidence['char_end'])
                        if start < end:
                            anchor = {'char_start': start, 'char_end': end, 'media_sha256': None}
                            if anchor not in anchors:
                                anchors.append(anchor)
                            if candidate['candidate_key'] not in keys:
                                keys.append(candidate['candidate_key'])
            if not anchors:
                span = next(((start, end) for start, end in target['char_ranges'] if start < end), None)
                if span:
                    anchors = [{'char_start': span[0], 'char_end': span[1], 'media_sha256': None}]
                elif target['media_sha256s']:
                    anchors = [{'char_start': None, 'char_end': None,
                                'media_sha256': target['media_sha256s'][0]}]
            disposition = 'selected' if keys else 'context_only'
            if target['mapping_status'] == 'unmapped':
                disposition, keys, anchors = 'needs_review', [], []
                response['complete'] = False
            reviews.append({'target_id': target['target_id'], 'items': [{
                'item_key': f'synthetic-content-{number}', 'label': 'Synthetic independent content item',
                'disposition': disposition, 'candidate_keys': keys, 'anchors': anchors,
                'reason': 'Synthetic source review for persistence testing; no model or scientific validation.'}]})
        response['source_reviews'] = reviews
        return response

    def decisions(self, response, *, multi_source=False):
        result = (multi_fixtures.MultiSourceRuntimeTests.decisions(response) if multi_source
                  else self.fixture.decisions(response))
        result['source_review_decisions'] = {
            'targets': [{'target_id': review['target_id'], 'verdict': 'confirmed',
                         'reason': 'Synthetic independent target review.'} for review in response['source_reviews']],
            'items': [{'item_key': item['item_key'], 'verdict': 'confirmed',
                       'reason': 'Synthetic independent content review.'}
                      for review in response['source_reviews'] for item in review['items']]}
        return result

    def receipt(self, job, response, phase):
        current = self.runtime.show(job['execution_id'])
        snapshot = current['input_snapshot']
        packet = snapshot['input']
        attachments = [{'sha256': asset['sha256'], 'byte_size': asset['byte_size']}
                       for asset in packet['media_assets']]
        if phase == 'generator':
            prompt, schema = generation_request(snapshot, attachments)
            input_sha = current['input_digest']
        else:
            context = self.runtime.validation_context(job['execution_id'])
            prompt, schema = validation_request(context, attachments)
            input_sha = context['validation_context_sha']
        return {'profile': {**current['profile']['model'], 'synthetic_receipt': True},
                'input_sha256': input_sha, 'output_sha256': digest(response),
                'prompt_sha256': sha256(prompt.encode('utf-8')).hexdigest(), 'schema_sha256': digest(schema),
                'provider_ref': 'synthetic-no-model-' + str(uuid4()), 'actual_delivery': True,
                'delivered_information_ids': [unit['information_id'] for unit in packet['model_input']['information']],
                'image_attachments': attachments, 'original_pdf_delivered': False, 'usage': {}, 'test_only': True}

    def stage(self, job, response):
        return self.runtime.stage(job['execution_id'], response, self.receipt(job, response, 'generator'))

    def commit(self, job, response, decisions=None):
        self.stage(job, response)
        decisions = decisions or self.decisions(response)
        return self.runtime.decide(job['execution_id'], decisions, self.receipt(job, decisions, 'validator'))

    def test_manifest_and_reviews_persist_with_exact_record_revision_bindings(self):
        job = self.prepare()
        manifest = job['input_snapshot']['source_review_manifest']
        self.assertEqual(job['profile']['source_review'], 'source-review-v1')
        self.assertGreater(len(manifest['targets']), 0)
        self.assertEqual({target['information_id'] for target in manifest['targets']},
                         {unit['information_id'] for unit in self.packet['model_input']['information']})
        response = self.reviewed_response(job)
        result = self.commit(job, response)
        self.assertEqual(result['state'], 'completed')
        saved = self.runtime.show(job['execution_id'])['source_review']
        self.assertEqual(saved['manifest'], manifest)
        self.assertEqual(len(saved['generator_reviews']), len(manifest['targets']))
        records = {record['record_id']: record for record in result['records']}
        bound = [record for binding in saved['validation']['bindings'] for record in binding['records']]
        self.assertTrue(bound)
        for record in bound:
            canonical = records[record['record_id']]
            self.assertEqual(record['knode_id'], canonical['result_node_id'])
            self.assertEqual(record['knode_revision_id'], canonical['result_node_revision_id'])
            self.assertEqual(record['disposition'], canonical['disposition'])
        replay = self.prepare(request=job['request_id'])
        self.assertTrue(replay['replayed'])
        self.assertEqual(replay['input_snapshot'], job['input_snapshot'])

    def test_missing_target_is_rejected_before_staged_records_or_reviews(self):
        job = self.prepare()
        response = self.reviewed_response(job)
        response['source_reviews'].pop()
        with self.assertRaises(PalimpsestError):
            self.stage(job, response)
        saved = self.runtime.show(job['execution_id'])
        self.assertEqual(saved['state'], 'prepared')
        self.assertEqual(saved['records'], [])
        self.assertEqual(saved['information_reviews'], [])
        self.assertIsNone(saved['generator_receipt'])
        self.assertEqual(self.runtime.graph(self.helper.data_id)['nodes'], [])

    def test_unresolved_target_prevents_success_without_discarding_accepted_k(self):
        job = self.prepare()
        response = self.reviewed_response(job)
        decisions = self.decisions(response)
        decisions['source_review_decisions']['targets'][0].update(
            verdict='needs_review', reason='Synthetic additional independent detail remains unrepresented.')
        result = self.commit(job, response, decisions)
        self.assertEqual(result['state'], 'needs_human')
        self.assertTrue(all(record['disposition'] == 'accepted_new' for record in result['records']))
        self.assertEqual(result['source_review']['validation']['pending_target_ids'],
                         [response['source_reviews'][0]['target_id']])

    def test_unresolved_item_prevents_success_even_when_all_targets_are_confirmed(self):
        job = self.prepare()
        response = self.reviewed_response(job)
        decisions = self.decisions(response)
        held = decisions['source_review_decisions']['items'][0]
        held.update(verdict='needs_review', reason='Synthetic content item needs another independent review.')
        result = self.commit(job, response, decisions)
        self.assertEqual(result['state'], 'needs_human')
        self.assertIn(held['item_key'], result['source_review']['validation']['pending_item_keys'])

    def test_late_failure_rolls_back_knowledge_and_review_result_together(self):
        job = self.prepare()
        response = self.reviewed_response(job)
        self.stage(job, response)
        decisions = self.decisions(response)
        receipt = self.receipt(job, decisions, 'validator')
        def fail(phase):
            if phase == 'after_knowledge_effect':
                raise RuntimeError('Synthetic source-review commit interruption')
        with self.assertRaisesRegex(RuntimeError, 'Synthetic source-review'):
            self.runtime.decide(job['execution_id'], decisions, receipt, checkpoint=fail)
        saved = self.runtime.show(job['execution_id'])
        self.assertEqual(saved['state'], 'proposed')
        self.assertIsNone(saved['source_review']['validation'])
        self.assertIsNone(saved['validator_receipt'])
        self.assertEqual(saved['information_review_decisions'], [])
        self.assertEqual(self.runtime.graph(self.helper.data_id)['nodes'], [])
        final = self.runtime.decide(job['execution_id'], decisions, receipt)
        self.assertEqual(final['state'], 'completed')
        self.assertTrue(final['source_review']['validation']['bindings'])

    def test_missing_validator_item_rolls_back_all_decision_effects(self):
        job = self.prepare()
        response = self.reviewed_response(job)
        self.stage(job, response)
        decisions = self.decisions(response)
        decisions['source_review_decisions']['items'].pop()
        with self.assertRaises(PalimpsestError):
            self.runtime.decide(job['execution_id'], decisions, self.receipt(job, decisions, 'validator'))
        saved = self.runtime.show(job['execution_id'])
        self.assertEqual(saved['state'], 'proposed')
        self.assertIsNone(saved['validator_receipt'])
        self.assertEqual(saved['information_review_decisions'], [])
        self.assertEqual(self.runtime.graph(self.helper.data_id)['nodes'], [])

    def test_provider_cannot_supply_application_owned_revision_bindings(self):
        job = self.prepare()
        response = self.reviewed_response(job)
        self.stage(job, response)
        decisions = self.decisions(response)
        receipt = self.receipt(job, decisions, 'validator')
        receipt['source_review_result'] = {'bindings': [{'knode_revision_id': self.helper.repo.allocate_id()}]}
        with self.assertRaises(PalimpsestError):
            self.runtime.decide(job['execution_id'], decisions, receipt)
        self.assertIsNone(self.runtime.show(job['execution_id'])['source_review']['validation'])
        self.assertEqual(self.runtime.graph(self.helper.data_id)['nodes'], [])

    def test_reuse_retains_exact_revision_and_new_review_bindings_without_duplicate_k(self):
        first = self.prepare()
        response = self.reviewed_response(first)
        before = self.commit(first, response)
        graph_before = self.runtime.graph(self.helper.data_id)
        second = self.prepare()
        repeated = self.reviewed_response(second)
        decisions = self.decisions(repeated)
        for decision, record in zip(decisions['decisions'], before['records']):
            decision.update(verdict='reused', equivalent_revision_id=record['result_node_revision_id'])
        result = self.commit(second, repeated, decisions)
        self.assertEqual([record['disposition'] for record in result['records']], ['reused', 'reused'])
        graph_after = self.runtime.graph(self.helper.data_id)
        self.assertEqual(graph_before['node_revisions'], graph_after['node_revisions'])
        self.assertEqual(graph_before['groundings'], graph_after['groundings'])
        old_revisions = {record['result_node_revision_id'] for record in before['records']}
        bindings = [record for item in result['source_review']['validation']['bindings'] for record in item['records']]
        self.assertEqual({record['knode_revision_id'] for record in bindings}, old_revisions)
        self.assertTrue(all(record['disposition'] == 'reused' for record in bindings))

    def test_legacy_request_replay_preserves_absent_source_review_profile(self):
        legacy = self.prepare(source_review=False)
        self.assertNotIn('source_review', legacy['profile'])
        self.assertNotIn('source_review_manifest', legacy['input_snapshot'])
        replay = self.prepare(request=legacy['request_id'])
        self.assertTrue(replay['replayed'])
        self.assertEqual(replay['profile'], legacy['profile'])
        self.assertEqual(replay['input_snapshot'], legacy['input_snapshot'])
        self.assertIsNone(self.runtime.show(legacy['execution_id']).get('source_review'))
        self.assertEqual(self.prepare()['profile']['source_review'], 'source-review-v1')

    def test_multi_data_target_cannot_bind_another_sources_observation(self):
        fixture = multi_fixtures.MultiSourceRuntimeTests('runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.runtime = fixture.runtime
        job = self.prepare(packet=fixture.bundle)
        response = self.reviewed_response(job, fixture.response())
        target = next(target for target in job['input_snapshot']['source_review_manifest']['targets']
                      if target['information_id'] == fixture.second.text['information_id']
                      and any(start < end for start, end in target['char_ranges']))
        changed = deepcopy(response)
        review = next(review for review in changed['source_reviews'] if review['target_id'] == target['target_id'])
        review['items'][0]['candidate_keys'] = ['observation_a']
        review['items'][0]['disposition'] = 'selected'
        with self.assertRaises(PalimpsestError):
            self.stage(job, changed)
        self.assertEqual(self.runtime.show(job['execution_id'])['records'], [])
        result = self.commit(job, response, self.decisions(response, multi_source=True))
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(len(result['records']), 3)
        self.assertEqual({target['data_id'] for target in result['source_review']['manifest']['targets']},
                         fixture.data_ids)


if __name__ == '__main__':
    unittest.main()
