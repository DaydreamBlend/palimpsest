"""Pure modern N2E contracts. No model calls, DB or canonical effect claims."""

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from palimpsest import n2e, n2e_relations as modern
from palimpsest.errors import PalimpsestError


def uid(number):
    return f'019947e2-1234-7000-8000-{number:012x}'


def node(number, kind='proposition'):
    return {'knode_id': uid(number), 'knode_revision_id': uid(number + 100),
        'current_revision_id': uid(number + 100), 'kind': kind, 'statement': f'Accepted statement {number}.',
        'semantic_payload': {'subject': str(number), 'relation': 'has value', 'object': 'value',
            'polarity': 'positive', 'quantifier': 'one', 'scope': 'fixture', 'conditions': [], 'time_range': ''},
        'current_support_record_id': None, 'current_support_signature': sha256(str(number).encode()).hexdigest()}


def snapshot():
    return {'n2e_policy': modern.PROFILE,
        'input': {'schema_version': 'n2e-input-v1', 'nodes': [node(1, 'observation'), node(2), node(3, 'observation'), node(4)]},
        'existing_edges': []}


def proposal(predicate='supports', source=1, target=2, key='relation', *, scope='fixture'):
    return {'candidate_key': key, 'from_revision_id': uid(source + 100), 'to_revision_id': uid(target + 100),
        'predicate': predicate, 'qualifiers': {'scope': scope, 'conditions': []}, 'rationale': 'Synthetic relation explanation.'}


def existing(predicate='supports', source=1, target=2):
    if predicate == 'contradicts':
        source, target = sorted((source, target))
    qualifiers = {'scope': 'fixture', 'conditions': []}
    return {'kedge_id': uid(300), 'kedge_revision_id': uid(301), 'current_revision_id': uid(301),
        'predicate': predicate, 'from_knode_id': uid(source), 'to_knode_id': uid(target),
        'from_knode_revision_id': uid(source + 100), 'to_knode_revision_id': uid(target + 100), 'qualifiers': qualifiers,
        **modern.edge_fingerprints(uid(source), uid(target), predicate, qualifiers)}


def assessment(value, *, confirmed=None):
    result = {'applicable': value, 'reason_codes': ['synthetic_review'], 'reason': 'Synthetic assessment only.'}
    if confirmed is not None:
        result['confirmed'] = confirmed
    return result


def reviewed_snapshot(predicate='supports', *, prior=True):
    value = snapshot()
    edge = existing(predicate)
    value['existing_edges'] = [edge]
    pair = [value['input']['nodes'][0], value['input']['nodes'][1]]
    target = modern.freeze_target(edge, [n['knode_revision_id'] for n in pair], prior, None,
        [edge['from_knode_revision_id'], edge['to_knode_revision_id']],
        [n['current_support_record_id'] for n in pair], [n['current_support_signature'] for n in pair])
    value['edge_review_target'] = target
    return value


def decisions(candidates, *, material=True, applicable=None, confirmed=None):
    result = {'decisions': [{'candidate_key': c['candidate_key'], 'verdict': 'accepted',
        'reason_codes': ['synthetic_review'], 'reason': 'Synthetic independent relation judgment.',
        'comparison_base_revision_id': c['comparison_base_revision_id'],
        'material_change': None if c['role'] == 'target_assessment' else material,
        'relation_valid': True, 'scope_compatible': True} for c in candidates], 'complete': True}
    if confirmed is not None:
        result['applicability'] = assessment(applicable, confirmed=confirmed)
    return result


class N2ERelationsTests(unittest.TestCase):
    def reject(self, callback, code=None):
        with self.assertRaises(PalimpsestError) as caught:
            callback()
        if code:
            self.assertEqual(caught.exception.code, code)

    def test_supports_fingerprints_are_exact_legacy_bytes(self):
        qualifiers = {'scope': 'fixture', 'conditions': ['b', 'a', 'b']}
        self.assertEqual(modern.edge_fingerprints(uid(1), uid(2), 'supports', qualifiers),
                         n2e.edge_fingerprints(uid(1), uid(2), 'supports', qualifiers))
        self.assertNotEqual(modern.edge_fingerprints(uid(1), uid(2), 'qualifies', qualifiers),
                            modern.edge_fingerprints(uid(1), uid(2), 'supports', qualifiers))

    def test_contradiction_swaps_logical_nodes_and_matching_revisions_without_mutating_raw(self):
        value = snapshot()
        raw = {'edges': [proposal('contradicts', 2, 1)], 'complete': True}
        original = deepcopy(raw)
        candidate = modern.normalize_response(raw, value)[0]
        self.assertEqual(raw, original)
        self.assertEqual([candidate['from_revision_id'], candidate['to_revision_id']], [uid(101), uid(102)])
        self.assertEqual(modern.edge_fingerprints(uid(2), uid(1), 'contradicts', candidate['qualifiers']),
                         modern.edge_fingerprints(uid(1), uid(2), 'contradicts', candidate['qualifiers']))
        self.assertEqual(candidate['role'], 'relation')
        self.assertIsNone(candidate['comparison_base_revision_id'])

    def test_symmetric_duplicates_and_same_identity_different_qualifiers_are_rejected(self):
        for edges in ([proposal('contradicts', 1, 2, 'first'), proposal('contradicts', 2, 1, 'second')],
                      [proposal('supports', key='first'), proposal('supports', key='second', scope='another scope')]):
            self.reject(lambda: modern.normalize_response({'edges': edges, 'complete': True}, snapshot()),
                        'duplicate_n2e_relation_identity')

    def test_predicate_matrix_and_directions_are_structural_not_semantic_approval(self):
        value = snapshot()
        for predicate in modern.PREDICATES:
            self.assertEqual(modern.normalize_response({'edges': [proposal(predicate)], 'complete': True}, value)[0]['predicate'], predicate)
        for predicate in ('supports', 'qualifies'):
            self.reject(lambda: modern.normalize_response({'edges': [proposal(predicate, 2, 1)], 'complete': True}, value),
                        'invalid_n2e_endpoint_types')
        for predicate in ('contradicts', 'composes'):
            self.assertEqual(len(modern.normalize_response({'edges': [proposal(predicate, 1, 3)], 'complete': True}, value)), 1)
        for predicate in ('supersedes', 'causes', 'arbitrary_relation'):
            self.reject(lambda: modern.normalize_response({'edges': [proposal(predicate)], 'complete': True}, value))
        self.reject(lambda: modern.normalize_response({'edges': [proposal('composes', 1, 1)], 'complete': True}, value))
        self.assertNotEqual(modern.edge_fingerprints(uid(1), uid(2), 'composes', {'scope': '', 'conditions': []}),
                            modern.edge_fingerprints(uid(2), uid(1), 'composes', {'scope': '', 'conditions': []}))

    def test_existing_identity_binds_exact_semantic_revision_while_predicate_change_is_new(self):
        value = snapshot()
        value['existing_edges'] = [existing()]
        raw = {'edges': [proposal(scope='narrower valid condition')], 'complete': True}
        candidate = modern.normalize_response(raw, value)[0]
        self.assertEqual(candidate['comparison_base_revision_id'], uid(301))
        self.assertNotEqual(candidate['content_fingerprint'], value['existing_edges'][0]['content_fingerprint'])
        changed = modern.normalize_response({'edges': [proposal('qualifies')], 'complete': True}, value)[0]
        self.assertIsNone(changed['comparison_base_revision_id'])
        self.assertEqual(value['existing_edges'][0]['predicate'], 'supports')

    def test_endpoint_rebasing_preserves_original_edge_and_fingerprints(self):
        value = snapshot()
        edge = existing()
        value['existing_edges'] = [edge]
        value['input']['nodes'][0].update(knode_revision_id=uid(201), current_revision_id=uid(201))
        raw = proposal()
        raw['from_revision_id'] = uid(201)
        candidate = modern.normalize_response({'edges': [raw], 'complete': True}, value)[0]
        self.assertEqual(candidate['identity_fingerprint'], edge['identity_fingerprint'])
        self.assertEqual(candidate['content_fingerprint'], edge['content_fingerprint'])
        self.assertEqual(candidate['comparison_base_revision_id'], edge['kedge_revision_id'])
        self.assertEqual(edge['from_knode_revision_id'], uid(101))

    def test_empty_discovery_is_valid_but_empty_review_always_has_application_assessment(self):
        self.assertEqual(modern.normalize_response({'edges': [], 'complete': True}, snapshot()), [])
        value = reviewed_snapshot()
        candidates = modern.normalize_response({'edges': [], 'complete': True, 'applicability': assessment(None)}, value)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]['candidate_key'], modern.REVIEW_KEY)
        self.assertEqual(candidates[0]['role'], 'target_assessment')
        checked = modern.validate_decisions(decisions(candidates, applicable=None, confirmed=False), candidates, value['edge_review_target'])
        self.assertFalse(checked[modern.REVIEW_KEY]['applicability_review']['confirmed'])
        self.assertIsNone(checked[modern.REVIEW_KEY]['material_change'])
        self.reject(lambda: modern.normalize_response({'edges': [], 'complete': True}, value))

    def test_model_cannot_emit_reserved_role_fingerprints_or_assessment_key(self):
        for change in ({'candidate_key': modern.REVIEW_KEY}, {'role': 'target_assessment'},
                       {'comparison_base_revision_id': uid(301)}, {'identity_fingerprint': 'a' * 64}):
            raw = proposal()
            raw.update(change)
            self.reject(lambda: modern.normalize_response({'edges': [raw], 'complete': True}, snapshot()))

    def test_review_predicate_change_contains_both_old_assessment_and_new_relation(self):
        value = reviewed_snapshot()
        candidates = modern.normalize_response({'edges': [proposal('qualifies')], 'complete': True,
            'applicability': assessment(True)}, value)
        self.assertEqual([c['role'] for c in candidates], ['target_assessment', 'relation'])
        self.assertEqual([c['predicate'] for c in candidates], ['supports', 'qualifies'])
        self.assertEqual([c['comparison_base_revision_id'] for c in candidates], [uid(301), None])
        checked = modern.validate_decisions(decisions(candidates, applicable=True, confirmed=True), candidates, value['edge_review_target'])
        self.assertTrue(checked[modern.REVIEW_KEY]['applicability_review']['applicable'])
        self.reject(lambda: modern.normalize_response({'edges': [proposal('qualifies'), proposal('contradicts', key='other')],
            'complete': True, 'applicability': assessment(True)}, value), 'n2e_single_review_relation_required')

    def test_definite_negative_is_valid_assessment_and_has_no_model_owned_materiality(self):
        value = reviewed_snapshot()
        candidates = modern.normalize_response({'edges': [], 'complete': True, 'applicability': assessment(False)}, value)
        result = modern.validate_decisions(decisions(candidates, applicable=False, confirmed=True), candidates, value['edge_review_target'])
        self.assertEqual(result[modern.REVIEW_KEY]['verdict'], 'accepted')
        self.assertFalse(result[modern.REVIEW_KEY]['applicability_review']['applicable'])
        wrong = decisions(candidates, applicable=False, confirmed=True)
        wrong['decisions'][0]['material_change'] = True
        self.reject(lambda: modern.validate_decisions(wrong, candidates, value['edge_review_target']),
                    'n2e_assessment_materiality_is_application_owned')

    def test_independent_confirmation_requires_definite_agreement_validity_and_scope(self):
        value = reviewed_snapshot()
        candidates = modern.normalize_response({'edges': [], 'complete': True, 'applicability': assessment(False)}, value)
        for modification in ('disagreement', 'unknown', 'rejected', 'invalid', 'scope'):
            raw = decisions(candidates, applicable=False, confirmed=True)
            if modification == 'disagreement': raw['applicability']['applicable'] = True
            elif modification == 'unknown': raw['applicability']['applicable'] = None
            elif modification == 'rejected': raw['decisions'][0]['verdict'] = 'rejected'
            elif modification == 'invalid': raw['decisions'][0]['relation_valid'] = False
            else: raw['decisions'][0]['scope_compatible'] = False
            with self.subTest(modification=modification):
                self.reject(lambda: modern.validate_decisions(raw, candidates, value['edge_review_target']),
                            'n2e_applicability_confirmation_not_supported')

    def test_new_positive_relation_requires_materiality_existing_uncertainty_is_preserved(self):
        fresh = modern.normalize_response({'edges': [proposal()], 'complete': True}, snapshot())
        for material in (False, None):
            self.reject(lambda: modern.validate_decisions(decisions(fresh, material=material), fresh),
                        'n2e_new_relation_requires_materiality')
        value = snapshot(); value['existing_edges'] = [existing()]
        candidates = modern.normalize_response({'edges': [proposal(scope='changed expression')], 'complete': True}, value)
        raw = decisions(candidates, material=None)
        raw['decisions'][0]['scope_compatible'] = False
        checked = modern.validate_decisions(raw, candidates)
        self.assertIsNone(checked['relation']['material_change'])
        self.assertFalse(checked['relation']['scope_compatible'])
        raw['decisions'][0].update(material_change=False, scope_compatible=True)
        self.assertFalse(modern.validate_decisions(raw, candidates)['relation']['material_change'])
        self.assertEqual(value['existing_edges'][0]['qualifiers']['scope'], 'fixture')

    def test_exhaustive_decisions_and_exact_comparison_base_are_required(self):
        value = reviewed_snapshot()
        candidates = modern.normalize_response({'edges': [proposal('qualifies')], 'complete': True,
            'applicability': assessment(True)}, value)
        raw = decisions(candidates, applicable=True, confirmed=True)
        raw['decisions'].pop()
        self.reject(lambda: modern.validate_decisions(raw, candidates, value['edge_review_target']), 'n2e_decision_coverage_mismatch')
        raw = decisions(candidates, applicable=True, confirmed=True)
        raw['decisions'][0]['comparison_base_revision_id'] = uid(999)
        self.reject(lambda: modern.validate_decisions(raw, candidates, value['edge_review_target']))
        raw = decisions(candidates, applicable=True, confirmed=True)
        raw['complete'] = False
        self.assertEqual(len(modern.validate_decisions(raw, candidates, value['edge_review_target'])), 2)

    def test_frozen_target_binds_hash_exact_endpoint_revisions_and_support_signatures(self):
        value = reviewed_snapshot()
        self.assertEqual(modern.check_target(value['edge_review_target']), value['edge_review_target'])
        modified = deepcopy(value)
        modified['input']['nodes'][0]['current_support_signature'] = 'a' * 64
        self.reject(lambda: modern.generation_request(modified), 'n2e_review_input_changed')
        modified = deepcopy(value)
        modified['edge_review_target']['prior_applicable'] = False
        self.reject(lambda: modern.check_target(modified['edge_review_target']), 'n2e_review_target_changed')

    def test_selected_legacy_node_payload_is_preserved_but_foreign_catalog_and_provenance_quotes_are_not_sent(self):
        value = snapshot()
        value['input']['nodes'][0]['semantic_payload'] = {'measurement': {'value': 3, 'unit': 'au'}, 'quote': 'ACCEPTED_LEGACY_MEANING'}
        value['input']['nodes'][0]['direct_groundings'] = [{'quote': 'PRIVATE_PROVENANCE_QUOTE', 'information_id': uid(999)}]
        value['existing_nodes'] = [{'statement': 'FOREIGN_GLOBAL_CATALOG'}]
        value['existing_edges'] = [existing('supports', 88, 89)]
        prompt, schema = modern.generation_request(value)
        self.assertIn('ACCEPTED_LEGACY_MEANING', prompt)
        self.assertNotIn('PRIVATE_PROVENANCE_QUOTE', prompt)
        self.assertNotIn('FOREIGN_GLOBAL_CATALOG', prompt)
        self.assertNotIn(uid(88), prompt)
        candidates = modern.normalize_response({'edges': [proposal()], 'complete': True}, value)
        context = {'input_snapshot': value, 'candidates': candidates, 'generator_complete': True,
                   'existing_nodes': [{'statement': 'FOREIGN_VALIDATOR_TOP_LEVEL'}]}
        prompt, _ = modern.validation_request(context)
        self.assertIn('ACCEPTED_LEGACY_MEANING', prompt)
        self.assertNotIn('PRIVATE_PROVENANCE_QUOTE', prompt)
        self.assertNotIn('FOREIGN_GLOBAL_CATALOG', prompt)
        self.assertNotIn('FOREIGN_VALIDATOR_TOP_LEVEL', prompt)
        self.assertEqual(schema['properties']['edges']['items']['properties']['predicate']['enum'], list(modern.PREDICATES))

    def test_zero_input_schemas_are_closed_and_review_adds_only_assessment_wire(self):
        value = snapshot(); value['input']['nodes'] = []
        _, generated = modern.generation_request(value)
        self.assertEqual(generated['properties']['edges']['maxItems'], 0)
        _, validated = modern.validation_request({'input_snapshot': value, 'candidates': [], 'generator_complete': True})
        self.assertEqual(validated['properties']['decisions']['maxItems'], 0)
        self.assertFalse(validated['properties']['decisions']['items']['additionalProperties'])
        self.assertNotIn('applicability', generated['properties'])
        value = reviewed_snapshot()
        _, generated = modern.generation_request(value)
        self.assertEqual(generated['properties']['edges']['maxItems'], 1)
        self.assertIn('applicability', generated['required'])
        candidates = modern.normalize_response({'edges': [], 'complete': True, 'applicability': assessment(True)}, value)
        _, validated = modern.validation_request({'input_snapshot': value, 'candidates': candidates, 'generator_complete': True})
        self.assertIn('applicability', validated['required'])
        branch = validated['properties']['decisions']['items']['anyOf'][0]
        self.assertEqual(branch['properties']['material_change'], {'type': 'null'})
        self.assertEqual(branch['properties']['comparison_base_revision_id']['enum'], [uid(301)])


if __name__ == '__main__':
    unittest.main()
