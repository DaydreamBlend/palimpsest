"""Pure mandatory-review and current-support counterexamples; no model or DB."""

from copy import deepcopy
import unittest

from palimpsest import revalidation as review, knowledge_provenance as provenance, n2e
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest


def uid(number):
    return f'019947e2-1234-7000-8000-{number:012x}'


def edge_fixture():
    nodes = {uid(11): {'knode_id': uid(1), 'kind': 'observation'},
             uid(12): {'knode_id': uid(2), 'kind': 'proposition'}}
    qualifier = {'scope': 'fixture', 'conditions': []}
    fp = n2e.edge_fingerprints(uid(1), uid(2), 'supports', qualifier)
    body = {'schema_version': review.PROFILE, 'kind': 'edge', 'target_revision_id': uid(21),
        'target_kedge_id': uid(20), 'from_revision_id': uid(11), 'to_revision_id': uid(12),
        'prior_applicable': True, 'prior_basis_event_id': None, 'prior_pair': [uid(11), uid(12)],
        'target': {'kedge_id': uid(20), 'kedge_revision_id': uid(21), 'predicate': 'supports',
            'from_knode_id': uid(1), 'to_knode_id': uid(2), 'from_knode_revision_id': uid(11),
            'to_knode_revision_id': uid(12), 'qualifiers': qualifier, **fp}}
    target = {**body, 'target_sha256': digest(body)}
    candidate = {'candidate_key': 'edge', 'from_revision_id': uid(11), 'to_revision_id': uid(12),
        'predicate': 'supports', 'qualifiers': qualifier, 'rationale': 'Synthetic assessment target.'}
    return nodes, target, candidate


def assessment(applicable, *, validator=False):
    result = {'applicable': applicable, 'reason_codes': ['synthetic_review'], 'reason': 'Synthetic assessment only.'}
    return {**result, 'confirmed': True} if validator else result


def state_fixture():
    revisions = {uid(i): {'knode_revision_id': uid(i), 'knode_id': uid(i+20),
        'origin_record_id': uid(i+40), 'current_revision_id': uid(i)} for i in range(1, 5)}
    derivation = {'record_id': uid(43), 'result_node_revision_id': uid(3), 'premise_revision_ids': [uid(1), uid(2)]}
    return {'revisions': revisions, 'by_record': {uid(43): derivation},
        'by_result': {uid(3): [derivation]}, 'edges': {uid(3): [uid(1), uid(2)]},
        'groundings': {}, 'current_supports': {}, 'support_refs': {uid(43): {uid(1): None, uid(2): None}}}


class RevalidationTests(unittest.TestCase):
    def test_definite_false_is_valid_assessment_and_material_without_new_semantic_edge(self):
        nodes, target, candidate = edge_fixture()
        raw = {'edges': [candidate], 'complete': True, 'applicability': assessment(False)}
        candidates, _ = review.normalize_edge_response(raw, nodes, target)
        decisions = {'decisions': [{'candidate_key': 'edge', 'verdict': 'accepted',
            'reason_codes': ['synthetic_review'], 'reason': 'Independently confirmed false.'}],
            'complete': True, 'applicability': assessment(False, validator=True)}
        _, result = review.edge_decisions(decisions, candidates, target)
        self.assertTrue(result['confirmed'])
        self.assertTrue(result['material_change'])
        self.assertFalse(result['applicable'])
        self.assertEqual(candidates[0]['content_fingerprint'], target['target']['content_fingerprint'])

    def test_zero_output_and_disagreement_never_resolve_mandatory_target(self):
        nodes, target, candidate = edge_fixture()
        empty = {'edges': [], 'complete': True, 'applicability': assessment(False)}
        candidates, _ = review.normalize_edge_response(empty, nodes, target)
        _, result = review.edge_decisions({'decisions': [], 'complete': True,
            'applicability': assessment(False, validator=True)}, candidates, target)
        self.assertFalse(result['confirmed'])
        candidates, _ = review.normalize_edge_response({'edges': [candidate], 'complete': True,
            'applicability': assessment(True)}, nodes, target)
        _, result = review.edge_decisions({'decisions': [{'candidate_key': 'edge', 'verdict': 'accepted',
            'reason_codes': ['synthetic_review'], 'reason': 'Disagreement.'}], 'complete': True,
            'applicability': assessment(False, validator=True)}, candidates, target)
        self.assertFalse(result['confirmed'])

    def test_repeated_negative_is_nonmaterial_and_qualifier_change_is_not_rebasing(self):
        nodes, target, candidate = edge_fixture()
        target['prior_applicable'] = False
        target['target_sha256'] = digest({k: v for k, v in target.items() if k != 'target_sha256'})
        candidates, _ = review.normalize_edge_response({'edges': [candidate], 'complete': True,
            'applicability': assessment(False)}, nodes, target)
        _, result = review.edge_decisions({'decisions': [{'candidate_key': 'edge', 'verdict': 'accepted',
            'reason_codes': ['synthetic_review'], 'reason': 'Repeated false.'}], 'complete': True,
            'applicability': assessment(False, validator=True)}, candidates, target)
        self.assertTrue(result['confirmed']); self.assertFalse(result['material_change'])
        candidate['qualifiers']['scope'] = 'Changed meaning'
        with self.assertRaises(PalimpsestError):
            review.normalize_edge_response({'edges': [candidate], 'complete': True,
                'applicability': assessment(True)}, nodes, target)

    def test_schema_keeps_target_single_and_explicit_independent_assessment(self):
        nodes, target, _ = edge_fixture()
        prompt, schema = review.edge_request('base', n2e.EDGE_SCHEMA(list(nodes)), target)
        self.assertEqual(schema['properties']['edges']['maxItems'], 1)
        self.assertIn('applicability', schema['required'])
        self.assertIn('Empty output never finishes', prompt)
        _, schema = review.edge_request('base', n2e.EDGE_DECISION_SCHEMA(['edge']), target, validator=True)
        self.assertIn('confirmed', schema['properties']['applicability']['required'])

    def test_existing_node_review_explicitly_requests_supported_unchanged_candidate(self):
        body = {'schema_version': review.PROFILE, 'kind': 'node', 'target_revision_id': uid(3),
            'target_knode_id': uid(23), 'prior_support_record_id': uid(43), 'premise_revision_ids': [uid(1), uid(2)]}
        target = {**body, 'target_sha256': digest(body)}
        schema = {'type': 'object', 'properties': {'nodes': {'type': 'array'}}}
        prompt, result = review.node_request('ordinary inference policy', schema, target)
        self.assertEqual(result, schema)
        self.assertIn('not discovery of novel K', prompt)
        self.assertIn('Lack of novelty', prompt)
        prompt, _ = review.node_request('ordinary validator policy', schema, target, validator=True)
        self.assertIn('novel_conclusion=false', prompt)
        self.assertIn('revision_review.material_change=false', prompt)
        self.assertIn('Empty output remains unresolved', prompt)

    def test_support_switch_restores_same_revision_without_rewriting_origin(self):
        state = state_fixture()
        state['revisions'][uid(1)]['current_revision_id'] = uid(4)
        self.assertEqual(provenance.current_route(state, uid(3))['stale_revision_ids'], [uid(1)])
        before = deepcopy(state['revisions'][uid(3)])
        state['by_record'][uid(60)] = {'record_id': uid(60), 'premise_revision_ids': [uid(4), uid(2)]}
        state['support_refs'][uid(60)] = {uid(4): None, uid(2): None}
        state['current_supports'][uid(3)] = {'record_id': uid(60), 'node_revision_id': uid(3), 'event_order': 1}
        self.assertEqual(provenance.current_route(state, uid(3))['stale_revision_ids'], [])
        self.assertEqual(state['revisions'][uid(3)], before)
        self.assertEqual(provenance._origin_stale(state, uid(3)), [uid(1)])

    def test_consumed_support_change_stales_child_even_when_revision_unchanged(self):
        state = state_fixture()
        state['by_record'][uid(44)] = {'record_id': uid(44), 'premise_revision_ids': [uid(3), uid(2)]}
        state['support_refs'][uid(44)] = {uid(3): uid(43), uid(2): None}
        self.assertFalse(provenance.current_route(state, uid(4))['stale_revision_ids'])
        state['by_record'][uid(60)] = {'record_id': uid(60), 'premise_revision_ids': [uid(1), uid(2)]}
        state['support_refs'][uid(60)] = {uid(1): None, uid(2): None}
        state['current_supports'][uid(3)] = {'record_id': uid(60), 'node_revision_id': uid(3), 'event_order': 1}
        self.assertEqual(provenance.current_route(state, uid(4))['stale_revision_ids'], [uid(3)])

    def test_historical_unbound_support_and_partial_new_refs_do_not_hide_changes(self):
        state = state_fixture()
        del state['support_refs'][uid(43)][uid(2)]
        self.assertEqual(provenance.current_route(state, uid(3))['stale_revision_ids'], [uid(2)])
        del state['support_refs'][uid(43)]
        self.assertFalse(provenance.current_route(state, uid(3))['stale_revision_ids'])

    def test_cycle_is_unresolved_not_a_depth_limit_or_false_success(self):
        state = state_fixture()
        state['by_record'][uid(41)] = {'record_id': uid(41), 'premise_revision_ids': [uid(3), uid(2)]}
        self.assertTrue(provenance.current_route(state, uid(3))['stale_revision_ids'])


if __name__ == '__main__':
    unittest.main()
