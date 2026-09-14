"""Synthetic controller checks; no PostgreSQL, provider or semantic evaluation."""

from copy import deepcopy
import unittest
from unittest.mock import Mock

from palimpsest.errors import PalimpsestError
from palimpsest.knowledge_review import KnowledgeReview, review_status


REQUEST = '019941d7-9200-7000-8000-000000000001'


def fixture():
    record = {'record_id': 'r1', 'execution_id': 'e1', 'disposition': 'reused',
              'reason_codes': ['same_meaning'], 'reason': 'Synthetic same-meaning assessment.',
              'result_node_id': 'k1', 'result_node_revision_id': 'kr1',
              'body': {'candidate_key': 'c1'}}
    return {
        'execution_id': 'e1', 'request_id': 'original', 'operation': 'i2k',
        'state': 'needs_human', 'data_id': 'd1', 'input_digest': 'input-hash',
        'profile': {'schema_version': 'source-complete-i2k-v1',
                    'model': {'model': 'unchanged-model'}, 'source_review': 'source-review-v1'},
        'input_snapshot': {'input': {
            'data_id': 'd1', 'source_execution_id': 'source-1',
            'target_information_ids': ['i1', 'i2'], 'context_information_ids': [],
            'excluded_information_ids': [], 'model_input': {'information': [
                {'information_id': 'i1', 'content': 'Retained source A'},
                {'information_id': 'i2', 'content': 'Retained source B'}]}},
            'data_versions': [{'version_id': 'v1', 'data_id': 'd1', 'series_id': 's1'}],
            'data_version_mode': 'current'},
        'records': [record],
        'information_review_records': [{'information_id': 'i1', 'record_id': 'r1'}],
        'information_reviews': [
            {'information_id': 'i1', 'disposition': 'selected', 'reason': 'Synthetic selection.'},
            {'information_id': 'i2', 'disposition': 'context_only', 'reason': 'Synthetic context.'}],
        'information_review_decisions': [
            {'information_id': 'i1', 'verdict': 'confirmed', 'reason': 'Synthetic review A.'},
            {'information_id': 'i2', 'verdict': 'confirmed', 'reason': 'Synthetic review B.'}],
        'source_review': {
            'manifest': {'targets': [
                {'target_id': 't1', 'information_id': 'i1', 'data_id': 'd1', 'char_ranges': [[0, 17]]},
                {'target_id': 't2', 'information_id': 'i2', 'data_id': 'd1', 'char_ranges': [[0, 17]]}]},
            'generator_reviews': [
                {'target_id': 't1', 'items': [{'item_key': 'item-1', 'disposition': 'selected',
                    'candidate_keys': ['c1'], 'reason': 'Synthetic item selection.', 'anchors': []}]},
                {'target_id': 't2', 'items': [{'item_key': 'item-2', 'disposition': 'context_only',
                    'candidate_keys': [], 'reason': 'Synthetic item context.', 'anchors': []}]}],
            'validation': {
                'targets': [{'target_id': 't1', 'verdict': 'confirmed', 'reason': 'Synthetic target A.'},
                            {'target_id': 't2', 'verdict': 'needs_review', 'reason': 'Synthetic missing detail.'}],
                'items': [{'item_key': 'item-1', 'verdict': 'confirmed', 'reason': 'Synthetic item A.'},
                          {'item_key': 'item-2', 'verdict': 'needs_review', 'reason': 'Synthetic item issue.'}],
                'pending_target_ids': ['t2'], 'pending_item_keys': ['item-2'],
                'bindings': [{'item_key': 'item-1', 'records': [{'record_id': 'r1',
                    'disposition': 'reused', 'knode_id': 'k1', 'knode_revision_id': 'kr1'}]}]}},
        'source_requests': [], 'model_calls': [],
    }


class KnowledgeReviewTests(unittest.TestCase):
    def test_actual_accepted_new_record_is_resolved_and_listed(self):
        job = fixture()
        job['records'][0]['disposition'] = 'accepted_new'
        job['source_review']['validation']['bindings'][0]['records'][0]['disposition'] = 'accepted_new'
        status = review_status(job)
        self.assertEqual(status['accepted_knowledge'][0]['result_node_revision_id'], 'kr1')
        self.assertEqual(status['items'][0]['status'], 'reviewed')
        self.assertNotIn('i1', status['pending_information_ids'])

    def test_status_keeps_every_i_and_actual_reasons_with_exact_reused_revision(self):
        job = fixture()
        saved = deepcopy(job)
        status = review_status(job)
        self.assertEqual([row['information_id'] for row in status['information']], ['i1', 'i2'])
        self.assertEqual(status['pending_information_ids'], ['i2'])
        self.assertEqual(status['pending_target_ids'], ['t2'])
        self.assertEqual(status['pending_item_keys'], ['item-2'])
        self.assertEqual(status['targets'][1]['validator_review']['reason'], 'Synthetic missing detail.')
        self.assertEqual(status['items'][1]['validator_review']['reason'], 'Synthetic item issue.')
        self.assertEqual(status['accepted_knowledge'][0]['result_node_revision_id'], 'kr1')
        self.assertEqual(status['accepted_knowledge'][0]['reason'], 'Synthetic same-meaning assessment.')
        self.assertEqual(status['information'][0]['records'][0]['record_id'], 'r1')
        status['information'][0]['records'][0]['reason'] = 'changed projection'
        self.assertEqual(job, saved)

    def test_missing_validation_keeps_all_targets_items_and_i_pending(self):
        job = fixture()
        job.update(state='proposed', information_review_decisions=[])
        job['source_review']['validation'] = None
        result = review_status(job)
        self.assertEqual(result['next_action'], 'await_validator')
        self.assertEqual(result['pending_information_ids'], ['i1', 'i2'])
        self.assertEqual(result['pending_target_ids'], ['t1', 't2'])
        self.assertEqual(result['pending_item_keys'], ['item-1', 'item-2'])

    def test_source_delivery_alone_does_not_resolve_review(self):
        job = fixture()
        job['source_requests'] = [{'status': 'provided', 'payload': {
            'information_ids': ['i1'], 'reason': 'Need exact original source.'},
            'receipt': {'actual_delivery': True}}]
        result = review_status(job)
        self.assertEqual(result['pending_information_ids'], ['i1', 'i2'])
        self.assertEqual(result['source_requests'], job['source_requests'])
        self.assertEqual(len(result['accepted_knowledge']), 1)

    def test_held_candidate_or_missing_binding_stays_unresolved_despite_confirmed_item(self):
        for disposition in ('needs_human', None):
            with self.subTest(disposition=disposition):
                job = fixture()
                bindings = job['source_review']['validation']['bindings'][0]['records']
                if disposition:
                    bindings[0]['disposition'] = disposition
                else:
                    bindings.clear()
                result = review_status(job)
                self.assertEqual(result['pending_target_ids'], ['t1', 't2'])
                self.assertEqual(result['pending_item_keys'], ['item-1', 'item-2'])
                self.assertEqual(result['pending_information_ids'], ['i1', 'i2'])

    def test_multi_source_ownership_and_entire_source_bundle_are_preserved(self):
        job = fixture()
        job['profile']['schema_version'] = 'multi-source-explicit-i2k-v1'
        packet = job['input_snapshot']['input']
        packet['sources'] = [{'data_id': 'd1', 'source_execution_id': 'source-1'},
                             {'data_id': 'd2', 'source_execution_id': 'source-2'}]
        packet['model_input']['information'][0]['data_id'] = 'd1'
        packet['model_input']['information'][1]['data_id'] = 'd2'
        job['input_snapshot']['data_versions'].append(
            {'version_id': 'v2', 'data_id': 'd2', 'series_id': 's2'})
        runtime = Mock()
        runtime.show.return_value = job
        runtime.prepare.return_value = {'execution_id': 'multi-new', 'replayed': False}
        service = KnowledgeReview(runtime)
        status = service.status('e1')
        self.assertEqual([row['data_id'] for row in status['information']], ['d1', 'd2'])
        self.assertEqual(status['sources'], packet['sources'])
        service.prepare_resume('e1', REQUEST)
        self.assertEqual(runtime.prepare.call_args.args[3], packet)
        self.assertEqual(runtime.prepare.call_args.kwargs['data_version_ids'], ['v1', 'v2'])

    def test_resume_preserves_entire_input_model_and_current_or_pinned_version_scope(self):
        for mode in ('current', 'pinned'):
            with self.subTest(mode=mode):
                job = fixture()
                job['input_snapshot']['data_version_mode'] = mode
                original = deepcopy(job)
                runtime = Mock()
                runtime.show.return_value = job
                runtime.prepare.return_value = {'execution_id': 'new', 'replayed': False}
                result = KnowledgeReview(runtime).prepare_resume('e1', REQUEST)
                args, kwargs = runtime.prepare.call_args
                self.assertEqual(args, ('i2k', 'd1', REQUEST, job['input_snapshot']['input']))
                self.assertEqual(kwargs, {'selection': True, 'feedback_execution_id': 'e1',
                    'model_profile': {'model': 'unchanged-model'}, 'data_version_ids': ['v1'],
                    'data_version_mode': mode})
                args[3]['model_input']['information'].clear()
                kwargs['model_profile']['model'] = 'changed copy'
                self.assertEqual(job, original)
                self.assertEqual(result['action'], 'prepared')

    def test_resume_propagates_runtime_current_head_rejection_without_retargeting(self):
        runtime = Mock()
        runtime.show.return_value = fixture()
        runtime.prepare.side_effect = PalimpsestError('data_version_head_changed', 'Synthetic stale head.', 6)
        with self.assertRaises(PalimpsestError) as caught:
            KnowledgeReview(runtime).prepare_resume('e1', REQUEST)
        self.assertEqual(caught.exception.code, 'data_version_head_changed')
        self.assertEqual(runtime.prepare.call_count, 1)
        self.assertEqual(runtime.prepare.call_args.kwargs['data_version_mode'], 'current')

    def test_same_request_delegates_replay_and_legacy_profile_upgrade_to_runtime(self):
        job = fixture()
        job['profile'].pop('source_review')
        job.pop('source_review')
        job['input_snapshot'].pop('data_versions')
        job['input_snapshot'].pop('data_version_mode')
        runtime = Mock()
        runtime.show.return_value = job
        runtime.prepare.return_value = {'execution_id': 'same-new', 'replayed': True}
        result = KnowledgeReview(runtime).prepare_resume('e1', REQUEST)
        self.assertEqual(result['action'], 'replayed')
        self.assertNotIn('source_review', runtime.prepare.call_args.kwargs)
        self.assertNotIn('data_version_ids', runtime.prepare.call_args.kwargs)
        self.assertNotIn('source_review', job['profile'])

    def test_finished_and_inflight_jobs_never_start_another_review(self):
        for state in ('completed', 'zero_output', 'prepared', 'proposed', 'failed'):
            with self.subTest(state=state):
                job = fixture()
                job['state'] = state
                runtime = Mock()
                runtime.show.return_value = job
                service = KnowledgeReview(runtime)
                if state in ('completed', 'zero_output'):
                    self.assertEqual(service.prepare_resume('e1', REQUEST)['action'], 'no_work')
                else:
                    with self.assertRaises(PalimpsestError) as caught:
                        service.prepare_resume('e1', REQUEST)
                    self.assertEqual(caught.exception.code, 'knowledge_review_resume_not_ready')
                runtime.prepare.assert_not_called()

    def test_history_preserves_accepted_results_through_failed_rounds_without_a_depth_cutoff(self):
        jobs = {}
        previous = None
        for number in range(40):
            job = fixture()
            job.update(execution_id=f'e{number}', state='failed' if number else 'needs_human')
            if previous is not None:
                job['input_snapshot']['selection_feedback'] = {'execution_id': previous}
                job.update(records=[], information_review_records=[], information_reviews=[],
                           information_review_decisions=[], source_review=None)
            job['model_calls'] = [{'phase': 'generator', 'status': 'failed',
                                   'receipt': {'structural_error_code': 'synthetic_failure'}}]
            jobs[job['execution_id']] = job
            previous = job['execution_id']
        runtime = Mock()
        runtime.show.side_effect = lambda identifier: jobs[identifier]
        status = KnowledgeReview(runtime).status(previous)
        self.assertEqual(len(status['history']), 39)
        self.assertEqual(status['history'][0]['accepted_knowledge'][0]['result_node_revision_id'], 'kr1')
        self.assertEqual(status['model_calls'][0]['receipt']['structural_error_code'], 'synthetic_failure')
        self.assertEqual(status['next_action'], 'resume_review')
        runtime.prepare.assert_not_called()

    def test_changed_or_cyclic_history_and_partial_source_are_rejected(self):
        for failure in ('cycle', 'scope', 'partial'):
            with self.subTest(failure=failure):
                job = fixture()
                prior = deepcopy(job)
                prior['execution_id'] = 'previous'
                job['input_snapshot']['selection_feedback'] = {'execution_id': 'previous'}
                if failure == 'cycle':
                    prior['input_snapshot']['selection_feedback'] = {'execution_id': 'e1'}
                elif failure == 'scope':
                    prior['input_snapshot']['data_version_mode'] = 'pinned'
                else:
                    job['input_snapshot']['input']['target_information_ids'] = ['i1']
                runtime = Mock()
                runtime.show.side_effect = lambda identifier: job if identifier == 'e1' else prior
                with self.assertRaises(PalimpsestError) as caught:
                    KnowledgeReview(runtime).status('e1')
                self.assertEqual(caught.exception.code, {
                    'cycle': 'knowledge_review_history_cycle', 'scope': 'knowledge_review_scope_changed',
                    'partial': 'knowledge_review_full_source_required'}[failure])
                runtime.prepare.assert_not_called()


if __name__ == '__main__':
    unittest.main()
