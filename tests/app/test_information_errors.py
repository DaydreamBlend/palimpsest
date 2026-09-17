"""Reported Information errors stay distinct from K selection and verified D2I faults."""

from copy import deepcopy
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from palimpsest.errors import PalimpsestError
from palimpsest.information_errors import (POLICY, REASON_CODES, RULES, affected_information_ids,
                                           candidate_has_reported_error, report)


def uid(number):
    return f'019947e2-1234-7000-8000-{number:012x}'


def source(number):
    packet = {'data_id': str(number) * 64, 'source_execution_id': uid(100 + number),
        'profile_id': uid(200 + number), 'model_input': {'information': [
            {'information_id': uid(number * 10 + index), 'content': f'Retained I {number}/{index}',
             'source_refs': [{'block_id': '/source/' + str(index), 'locator_type': 'text_range',
                 'text_range': {'byte_start': 0, 'byte_end': 3, 'char_start': 0, 'char_end': 3,
                                'line_start': 1, 'line_end': 1}, 'anchor_sha256': 'a' * 64}]}
            for index in (1, 2)]}}
    packet['input_sha256'] = sha256(json.dumps(packet, sort_keys=True).encode('utf-8')).hexdigest()
    return packet


def job(*, multi=False):
    packets = [source(1), source(2)] if multi else [source(1)]
    packet = ({'data_id': packets[0]['data_id'], 'sources': deepcopy(packets),
               'model_input': {'information': [dict(deepcopy(unit), data_id=packet['data_id'],
                   source_execution_id=packet['source_execution_id']) for packet in packets
                   for unit in packet['model_input']['information']]}}
              if multi else packets[0])
    return {'execution_id': uid(900), 'operation': 'i2k', 'profile_id': uid(901),
        'input_snapshot': {'input': packet}, 'source_requests': [], 'information_review_decisions': []}


def request(owner=1, *, number=1, with_owner=True):
    payload = {'information_ids': [uid(owner * 10 + 1), uid(owner * 10 + 2)],
               'page_numbers': [], 'question': 'The retained I lacks the necessary source detail.\r\nNeeds user review.'}
    if with_owner:
        payload['data_id'] = str(owner) * 64
    return {'request_id': uid(1000 + number), 'execution_id': uid(900), 'payload': payload,
        'status': 'unavailable', 'receipt': {'actual_delivery': False, 'reason_code': 'native_pdf_unsupported'}}


def decision(owner=1, *, code='d2i_missing_information', verdict='needs_review'):
    return {'execution_id': uid(900), 'information_id': uid(owner * 10 + 1), 'verdict': verdict,
        'reason_codes': [code], 'reason': 'Validator reports a concrete problem in the supplied Information.'}


class InformationErrorTests(unittest.TestCase):
    def test_page_scoped_error_only_holds_matching_parser_page(self):
        value = {'information_ids': [uid(11)], 'page_numbers': [2],
                 'data_id': '1' * 64, 'question': 'One page differs.'}
        candidate = lambda block: {'evidence': [
            {'information_id': uid(11), 'source_block_id': block}]}
        self.assertTrue(candidate_has_reported_error(
            candidate('/pdf_info/1/preproc_blocks/0'), [value]))
        self.assertFalse(candidate_has_reported_error(
            candidate('/pdf_info/2/preproc_blocks/0'), [value]))
        self.assertTrue(candidate_has_reported_error(
            {'evidence': [{'information_id': uid(11), 'quote': 'unscoped'}]}, [value]))

    def test_page_scoped_error_uses_owned_media_page(self):
        value = {'information_ids': [uid(11)], 'page_numbers': [2],
                 'data_id': '1' * 64, 'question': 'One page differs.'}
        information = [{'information_id': uid(11), 'media': [
            {'sha256': 'a' * 64, 'page_index': 1}, {'sha256': 'b' * 64, 'page_index': 2}]}]
        candidate = lambda digest: {'evidence': [
            {'information_id': uid(11), 'media_sha256': digest}]}
        self.assertTrue(candidate_has_reported_error(candidate('a' * 64), [value], information))
        self.assertFalse(candidate_has_reported_error(candidate('b' * 64), [value], information))
        self.assertTrue(candidate_has_reported_error(candidate('c' * 64), [value], information))

    def reject(self, call, code=None):
        with self.assertRaises(PalimpsestError) as caught:
            call()
        if code:
            self.assertEqual(caught.exception.code, code)

    def test_no_reported_information_problem_and_generic_selection_gap_remain_separate(self):
        saved = job()
        saved['information_review_decisions'] = [decision(code='missing_material_content'),
            {**decision(code='selection_incomplete'), 'information_id': uid(12)}]
        result = report(saved)
        self.assertEqual(result, {'schema_version': 'i2k-information-errors-v1', 'execution_id': uid(900),
            'requires_user_review': False, 'errors': [], 'd2i_calls': 0, 'direct_source_compilation_allowed': False})
        self.assertEqual(affected_information_ids([], saved['information_review_decisions']), set())
        self.assertEqual(POLICY, 'i2k-information-required-v1')

    def test_legacy_generator_request_resolves_only_frozen_I_profile_and_source_refs(self):
        saved = job()
        value = request(with_owner=False)
        saved['source_requests'] = [value]
        before = deepcopy(saved)
        result = report(saved)
        error, = result['errors']
        packet = saved['input_snapshot']['input']
        self.assertTrue(result['requires_user_review'])
        self.assertEqual(error['reported_by'], 'generator')
        self.assertEqual(error['source_request_id'], value['request_id'])
        self.assertEqual(error['data_id'], packet['data_id'])
        self.assertEqual(error['source_execution_id'], packet['source_execution_id'])
        self.assertEqual(error['source_profile_id'], packet['profile_id'])
        self.assertNotEqual(error['source_profile_id'], saved['profile_id'])
        self.assertEqual(error['source_input_sha256'], packet['input_sha256'])
        self.assertEqual(error['information_ids'], [uid(11), uid(12)])
        self.assertEqual(error['source_refs'], [{'information_id': unit['information_id'], 'source_refs': unit['source_refs']}
                                               for unit in packet['model_input']['information']])
        self.assertEqual(error['reason'], value['payload']['question'])
        self.assertEqual(error['reason_codes'], ['d2i_information_error'])
        self.assertEqual((error['status'], error['verification_status']), ('reported_error', 'verification_pending'))
        self.assertEqual(saved, before)
        error['source_refs'][0]['source_refs'].clear()
        self.assertEqual(saved, before)

    def test_multi_Data_request_uses_its_actual_owner_not_the_operational_anchor(self):
        saved = job(multi=True)
        saved['source_requests'] = [request(2)]
        error, = report(saved)['errors']
        second = saved['input_snapshot']['input']['sources'][1]
        self.assertEqual(error['data_id'], '2' * 64)
        self.assertEqual(error['source_execution_id'], second['source_execution_id'])
        self.assertEqual(error['source_profile_id'], second['profile_id'])
        self.assertEqual(error['source_input_sha256'], second['input_sha256'])
        self.assertEqual(error['information_ids'], [uid(21), uid(22)])

    def test_all_recognized_validator_codes_report_pending_faults_and_preserve_original_verdict(self):
        for code in REASON_CODES:
            for verdict in ('needs_review', 'confirmed'):
                saved = job()
                value = decision(code=code, verdict=verdict)
                saved['information_review_decisions'] = [value]
                before = deepcopy(saved)
                with self.subTest(code=code, verdict=verdict):
                    error, = report(saved)['errors']
                    self.assertEqual(error['reported_by'], 'validator')
                    self.assertIsNone(error['source_request_id'])
                    self.assertEqual(error['reason_codes'], [code])
                    self.assertEqual(error['review_verdict'], verdict)
                    self.assertEqual(error['contradictory_verdict'], verdict == 'confirmed')
                    self.assertEqual(error['status'], 'reported_error')
                    self.assertEqual(error['verification_status'], 'verification_pending')
                    self.assertEqual(affected_information_ids([], [value]), {uid(11)})
                    self.assertEqual(saved, before)

    def test_mixed_validator_codes_do_not_turn_selection_errors_into_D2I_evidence(self):
        saved = job()
        value = decision()
        value['reason_codes'] = ['missing_material_content', 'd2i_missing_media', 'importance_uncertain']
        saved['information_review_decisions'] = [value]
        before = deepcopy(value)
        error, = report(saved)['errors']
        self.assertEqual(error['reason_codes'], ['d2i_missing_media'])
        self.assertEqual(value, before)

    def test_affected_set_accepts_persisted_or_raw_requests_without_fetching_any_source(self):
        value = request()
        reviews = [decision(2, code='d2i_transcription_error', verdict='confirmed'),
                   {**decision(2, code='missing_material_content'), 'information_id': uid(22)}]
        expected = {uid(11), uid(12), uid(21)}
        self.assertEqual(affected_information_ids([value], reviews), expected)
        self.assertEqual(affected_information_ids([value['payload']], reviews), expected)

    def test_unknown_I_cross_Data_and_foreign_execution_are_strictly_rejected(self):
        for mutation in ('unknown_request_I', 'wrong_request_D', 'mixed_request_D', 'wrong_request_execution',
                         'unknown_validator_I', 'wrong_validator_D', 'wrong_validator_execution',
                         'wrong_source_execution', 'foreign_source_ref'):
            saved = job(multi=True)
            saved['source_requests'] = [request()]
            saved['information_review_decisions'] = [decision()]
            req, review = saved['source_requests'][0], saved['information_review_decisions'][0]
            if mutation == 'unknown_request_I': req['payload']['information_ids'] = [uid(999)]
            elif mutation == 'wrong_request_D': req['payload']['data_id'] = '2' * 64
            elif mutation == 'mixed_request_D': req['payload']['information_ids'] = [uid(11), uid(21)]
            elif mutation == 'wrong_request_execution': req['execution_id'] = uid(999)
            elif mutation == 'unknown_validator_I':
                review.update(information_id=uid(999), reason_codes=['missing_material_content'])
            elif mutation == 'wrong_validator_D': review['data_id'] = '2' * 64
            elif mutation == 'wrong_validator_execution': review['execution_id'] = uid(999)
            elif mutation == 'wrong_source_execution': review['source_execution_id'] = uid(999)
            else: saved['input_snapshot']['input']['sources'][0]['model_input']['information'][0]['source_refs'][0]['data_id'] = '2' * 64
            with self.subTest(mutation=mutation): self.reject(lambda: report(saved), 'information_error_scope_mismatch')

    def test_missing_provenance_stays_empty_instead_of_fabricating_a_reference(self):
        saved = job()
        saved['input_snapshot']['input']['model_input']['information'][0]['source_refs'] = []
        saved['information_review_decisions'] = [decision(code='d2i_provenance_error')]
        error, = report(saved)['errors']
        self.assertEqual(error['information_ids'], [uid(11)])
        self.assertEqual(error['source_refs'], [{'information_id': uid(11), 'source_refs': []}])

    def test_historical_request_status_does_not_enable_D2K_or_claim_an_error_is_verified(self):
        for status in ('pending', 'unavailable', 'provided'):
            saved = job()
            saved['source_requests'] = [{**request(), 'status': status, 'receipt': {'actual_delivery': status == 'provided'}}]
            before = deepcopy(saved)
            result = report(saved)
            self.assertEqual(result['errors'][0]['verification_status'], 'verification_pending')
            self.assertFalse(result['direct_source_compilation_allowed'])
            self.assertEqual(result['d2i_calls'], 0)
            self.assertEqual(saved, before)

    def test_malformed_values_fail_and_pure_reporting_has_no_IO(self):
        saved = job()
        saved['source_requests'] = [request()]
        with patch('builtins.open', side_effect=AssertionError('No source file read')), \
                patch('urllib.request.urlopen', side_effect=AssertionError('No source fetch')), \
                patch('subprocess.Popen', side_effect=AssertionError('No parser/model call')):
            self.assertTrue(report(saved)['requires_user_review'])
            self.assertEqual(affected_information_ids(saved['source_requests'], []), {uid(11), uid(12)})
        self.reject(lambda: affected_information_ids(None, []))
        self.reject(lambda: affected_information_ids([{'information_ids': []}], []))
        self.reject(lambda: affected_information_ids([], [{**decision(), 'reason_codes': 'd2i_information_error'}]))
        self.reject(lambda: report({**saved, 'operation': 'k2k'}))
        self.assertIn('No D2K or direct-D grounding is permitted.', RULES)
        self.assertIn('missing_material_content', RULES)


if __name__ == '__main__':
    unittest.main()
