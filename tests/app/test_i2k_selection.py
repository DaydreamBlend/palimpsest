"""Pure selection coverage/scope contracts; no model or importance heuristic."""

from copy import deepcopy
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.i2k_selection import (check_scope_reuse, check_selection_input,
    normalize_selection, selection_decision_schema, selection_fingerprints,
    selection_schema, validate_selection_decisions)
from palimpsest.knowledge import normalize_nodes
from test_knowledge import fixture, uid, decision


def selection_fixture():
    packet, response = fixture()
    packet.update(data_id='d' * 64, target_information_ids=[uid(1), uid(2)],
                  context_information_ids=[], excluded_information_ids=[])
    for unit in packet['model_input']['information']:
        unit['role'] = 'target'
    response['nodes'][0].update(identity_scope='source', selection_reason='A reported experimental measurement.')
    response['reviews'] = [{'information_id': uid(1), 'disposition': 'selected',
        'candidate_keys': ['obs_1'], 'reason': 'A measured result is useful.'},
        {'information_id': uid(2), 'disposition': 'not_selected',
         'candidate_keys': [], 'reason': 'Repeated page furniture; no scientific claim.'}]
    return packet, response


class SelectionTests(unittest.TestCase):
    def error(self, code, call):
        with self.assertRaises(PalimpsestError) as caught:
            call()
        self.assertEqual(code, caught.exception.code)

    def test_all_information_is_reviewed_even_when_not_selected(self):
        packet, response = selection_fixture()
        normalized = normalize_selection(response, packet)
        self.assertEqual(len(normalized['nodes']), 1)
        self.assertEqual(len(normalized['reviews']), 2)
        response['reviews'].pop()
        self.error('selection_review_coverage_mismatch', lambda: normalize_selection(response, packet))
        response['reviews'].append(deepcopy(response['reviews'][0]))
        self.error('selection_review_coverage_mismatch', lambda: normalize_selection(response, packet))

    def test_subset_and_context_only_input_are_not_whole_source_selection(self):
        packet, unused = selection_fixture()
        packet['excluded_information_ids'] = [uid(3)]
        self.error('selection_requires_all_information', lambda: check_selection_input(packet))
        packet['excluded_information_ids'] = []
        packet['model_input']['information'][1]['role'] = 'context'
        self.error('selection_requires_all_information', lambda: check_selection_input(packet))

    def test_linked_review_must_match_actual_candidate_evidence(self):
        packet, response = selection_fixture()
        response['reviews'][1].update(disposition='selected', candidate_keys=['obs_1'])
        self.error('selection_review_evidence_mismatch', lambda: normalize_selection(response, packet))
        response['reviews'][1].update(disposition='not_selected', candidate_keys=[])
        response['reviews'][0].update(disposition='context_only', candidate_keys=[])
        self.error('selection_review_evidence_mismatch', lambda: normalize_selection(response, packet))

    def test_source_fp_is_data_specific_and_general_fp_is_reusable(self):
        packet, response = selection_fixture()
        payload = response['nodes'][0]['semantic_payload']
        source_a = selection_fingerprints('observation', payload, 'source', 'a' * 64)
        source_b = selection_fingerprints('observation', payload, 'source', 'b' * 64)
        self.assertNotEqual(source_a, source_b)
        general_a = selection_fingerprints('proposition', payload, 'general')
        general_b = selection_fingerprints('proposition', deepcopy(payload), 'general')
        self.assertEqual(general_a, general_b)
        response['nodes'][0]['identity_scope'] = 'general'
        self.error('observation_requires_source_scope', lambda: normalize_selection(response, packet))

    def test_missing_redundant_links_are_derived_without_changing_llm_selection(self):
        packet, response = selection_fixture()
        original = normalize_selection(response, packet)
        response['reviews'][0]['candidate_keys'] = []
        repaired = normalize_selection(response, packet)
        self.assertEqual(repaired['nodes'], original['nodes'])
        self.assertEqual(repaired['reviews'], original['reviews'])
        self.assertEqual(response['reviews'][0]['disposition'], 'selected')
        self.assertEqual(repaired['link_completions'][0]['added_candidate_keys'], ['obs_1'])
        response['reviews'][0]['disposition'] = 'not_selected'
        self.error('selection_review_evidence_mismatch', lambda: normalize_selection(response, packet))

    def test_media_only_citation_is_explicit_and_does_not_change_legacy(self):
        packet, response = selection_fixture()
        response['nodes'][0]['evidence'][0]['quote'] = ''
        node = normalize_selection(response, packet)['nodes'][0]
        self.assertEqual((node['evidence'][0]['char_start'], node['evidence'][0]['char_end']), (0, 0))
        legacy = {key: deepcopy(value) for key, value in response.items() if key != 'reviews'}
        del legacy['nodes'][0]['identity_scope'], legacy['nodes'][0]['selection_reason']
        self.error('invalid_knowledge_evidence', lambda: normalize_nodes(legacy, packet))
        response['nodes'][0]['evidence'][0]['media_sha256'] = None
        self.error('invalid_knowledge_evidence', lambda: normalize_selection(response, packet))

    def test_needs_review_cannot_claim_complete(self):
        packet, response = selection_fixture()
        response['reviews'][1]['disposition'] = 'needs_review'
        self.error('unresolved_selection_reviews', lambda: normalize_selection(response, packet))
        response['complete'] = False
        self.assertEqual(len(normalize_selection(response, packet)['reviews']), 2)

    def test_validator_checks_importance_scope_and_every_review_even_without_nodes(self):
        packet, response = selection_fixture()
        candidates = normalize_selection(response, packet)['nodes']
        result = {'complete': True, 'decisions': [{**decision('obs_1'), 'scope_correct': True, 'importance_justified': True}],
                  'reviews': [{'information_id': ref, 'verdict': 'confirmed',
                               'reason_codes': ['review_confirmed'], 'reason': 'Review checked.'} for ref in (uid(1), uid(2))]}
        self.assertEqual(len(validate_selection_decisions(result, candidates, [], [uid(1), uid(2)])['reviews']), 2)
        result['decisions'][0]['scope_correct'] = False
        self.error('selection_acceptance_not_justified', lambda: validate_selection_decisions(result, candidates, [], [uid(1), uid(2)]))
        result['decisions'] = []
        self.assertEqual(validate_selection_decisions(result, [], [], [uid(1), uid(2)])['decisions'], {})
        result['reviews'].pop()
        self.error('selection_review_coverage_mismatch', lambda: validate_selection_decisions(result, [], [], [uid(1), uid(2)]))

    def test_cross_data_source_reuse_and_legacy_binding_rules(self):
        packet, response = selection_fixture()
        candidate = normalize_selection(response, packet)['nodes'][0]
        existing = {'kind': 'observation', 'identity_scope': None, 'source_data_id': None,
                    'grounding_data_ids': [packet['data_id']]}
        self.assertTrue(check_scope_reuse(candidate, existing, packet['data_id']))
        existing['grounding_data_ids'].append('a' * 64)
        self.error('knowledge_scope_reuse_conflict', lambda: check_scope_reuse(candidate, existing, packet['data_id']))
        existing.update(identity_scope='source', source_data_id='a' * 64)
        self.error('knowledge_scope_reuse_conflict', lambda: check_scope_reuse(candidate, existing, packet['data_id']))
        existing.update(identity_scope='general', source_data_id=None)
        self.error('knowledge_scope_reuse_conflict', lambda: check_scope_reuse(candidate, existing, packet['data_id']))

    def test_strict_schema_has_media_only_and_empty_candidate_review_support(self):
        schema = selection_schema([uid(1)], ['a' * 64])
        node = schema['properties']['nodes']['items']
        self.assertIn('identity_scope', node['required'])
        self.assertEqual(node['properties']['evidence']['items']['properties']['quote']['minLength'], 0)
        empty = selection_decision_schema([], [], [uid(1)])
        self.assertEqual(empty['properties']['decisions']['maxItems'], 0)
        self.assertEqual(empty['properties']['reviews']['items']['properties']['verdict']['enum'], ['confirmed', 'needs_review'])

    def test_reuse_schema_branches_make_reference_modes_exclusive(self):
        schema = selection_decision_schema(['a', 'b'], [uid(9)], [uid(1)])
        branches = schema['properties']['decisions']['items']['anyOf']
        self.assertEqual(len(branches), 3)
        modes = set()
        for branch in branches:
            self.assertIs(branch['additionalProperties'], False)
            self.assertEqual(set(branch['required']), set(branch['properties']))
            props = branch['properties']
            modes.add((props['equivalent_candidate_key']['type'], props['equivalent_revision_id']['type']))
        self.assertEqual(modes, {('null', 'null'), ('string', 'null'), ('null', 'string')})
        no_existing = selection_decision_schema(['a'], [], [uid(1)])
        self.assertEqual(len(no_existing['properties']['decisions']['items']['anyOf']), 2)

    def test_full_coverage_can_preserve_semantic_incompleteness(self):
        packet, response = selection_fixture()
        candidates = normalize_selection(response, packet)['nodes']
        value = {'complete': False, 'decisions': [{**decision('obs_1'), 'scope_correct': True, 'importance_justified': True}],
                 'reviews': [{'information_id': identifier, 'verdict': 'needs_review' if identifier == uid(2) else 'confirmed',
                    'reason_codes': ['reviewed'], 'reason': 'Further semantic review remains.'}
                             for identifier in (uid(1), uid(2))]}
        checked = validate_selection_decisions(value, candidates, [], [uid(1), uid(2)])
        self.assertIs(checked['complete'], False)
        self.assertEqual(len(checked['decisions']), 1)
        value['decisions'] = []
        self.error('invalid_knowledge_decision', lambda: validate_selection_decisions(value, candidates, [], [uid(1), uid(2)]))
        value['complete'] = 'false'
        self.error('invalid_selection_decision', lambda: validate_selection_decisions(value, candidates, [], [uid(1), uid(2)]))


if __name__ == '__main__':
    unittest.main()
