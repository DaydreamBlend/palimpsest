"""Pure exact effective-Edge inference contracts; no DB/provider execution."""

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from palimpsest import k2k, k2k_effective as effective, knowledge_revision, revalidation
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
import test_k2k as legacy


uid = legacy.uid


def packet(*, extra_node=False, two_edges=False):
    nodes = legacy.packet()['nodes']
    if extra_node:
        nodes.append({**deepcopy(nodes[0]), 'knode_id': uid(3), 'knode_revision_id': uid(13)})
    for node in nodes:
        node['current_support_signature'] = digest({'node': node['knode_revision_id']})
    edges = []
    for index in range(2 if two_edges else 1):
        source, target = nodes[0:2] if index == 0 else list(reversed(nodes[0:2]))
        edges.append({'kedge_id': uid(100 + index), 'predicate': 'supports' if index == 0 else 'qualifies',
            'qualifiers': {'scope': 'Exact supplied conditions.', 'conditions': []},
            'original_from_revision_id': source['knode_revision_id'],
            'original_to_revision_id': target['knode_revision_id'],
            'effective_edge_ref': {'semantic_kedge_revision_id': uid(110 + index),
                'from_knode_revision_id': source['knode_revision_id'], 'to_knode_revision_id': target['knode_revision_id'],
                'applicability_basis_type': 'applicability_event', 'applicability_basis_ref': uid(120 + index),
                'relation_read_state_token': digest({'read': index})},
            'endpoint_support_signatures': [source['current_support_signature'], target['current_support_signature']]})
    return effective.build_input(nodes, edges, '1' * 64)


def response(source):
    value = legacy.response()
    value['nodes'][0].update(premise_revision_ids=[node['knode_revision_id'] for node in source['nodes']],
                            premise_edge_revision_ids=effective.edge_revision_ids(source))
    return value


def snapshot(source=None):
    return {'input': source or packet(), 'existing_nodes': [], 'existing_edges': []}


class EffectiveK2KTests(unittest.TestCase):
    def reject(self, callback, code=None):
        with self.assertRaises(PalimpsestError) as caught:
            callback()
        if code:
            self.assertEqual(caught.exception.code, code)

    def test_one_edge_requires_its_real_endpoint_bundle_and_preserves_exact_input(self):
        value = packet()
        before = deepcopy(value)
        self.assertEqual(effective.check_input(value), [uid(11), uid(12)])
        self.assertEqual(k2k.check_input(value), [uid(11), uid(12)])
        rebuilt = effective.build_input(value['nodes'], value['effective_edges'], value['data_id'])
        self.assertEqual(rebuilt, value)
        value['effective_edges'][0]['qualifiers']['scope'] = 'Changed.'
        self.reject(lambda: effective.check_input(value), 'k2k_effective_input_changed')
        self.assertEqual(rebuilt, before)
        self.reject(lambda: effective.build_input([], before['effective_edges'], before['data_id']))
        self.reject(lambda: effective.build_input(before['nodes'][:1], before['effective_edges'], before['data_id']))
        self.reject(lambda: effective.build_input(before['nodes'], [], before['data_id']), 'k2k_effective_edges_required')

    def test_effective_refs_reject_missing_foreign_duplicate_and_noncanonical_inputs(self):
        source = packet()
        for mutate in (
            lambda edge: edge['effective_edge_ref'].pop('applicability_basis_ref'),
            lambda edge: edge['effective_edge_ref'].update(from_knode_revision_id=uid(99)),
            lambda edge: edge['effective_edge_ref'].update(applicability_basis_type='pending'),
            lambda edge: edge['effective_edge_ref'].update(relation_read_state_token='bad'),
            lambda edge: edge.update(applicable=True),
            lambda edge: edge.update(predicate='supersedes'),
            lambda edge: edge.update(endpoint_support_signatures=['0' * 64, '0' * 64]),
        ):
            changed = deepcopy(source['effective_edges'])
            mutate(changed[0])
            self.reject(lambda: effective.build_input(source['nodes'], changed, source['data_id']))
        self.reject(lambda: effective.build_input(source['nodes'], source['effective_edges'] * 2, source['data_id']),
                    'duplicate_k2k_effective_edge')
        opposite = packet(two_edges=True)['effective_edges'][1]
        opposite['predicate'] = 'contradicts'
        self.reject(lambda: effective.build_input(source['nodes'], [opposite], source['data_id']),
                    'k2k_effective_edge_not_canonical')

    def test_four_current_relation_predicates_keep_type_and_direction_rules(self):
        source = packet()
        for predicate in ('supports', 'contradicts', 'qualifies', 'composes'):
            edge = deepcopy(source['effective_edges'][0])
            edge['predicate'] = predicate
            self.assertEqual(effective.build_input(source['nodes'], [edge], source['data_id'])['effective_edges'][0], edge)
        nodes = deepcopy(source['nodes'])
        nodes[1]['kind'] = 'observation'
        self.reject(lambda: effective.build_input(nodes, source['effective_edges'], source['data_id']),
                    'invalid_n2e_endpoint_types')

    def test_rebased_effective_pair_does_not_overwrite_original_endpoints(self):
        source = packet()
        edge = deepcopy(source['effective_edges'][0])
        edge['original_from_revision_id'] = uid(211)
        built = effective.build_input(source['nodes'], [edge], source['data_id'])
        self.assertEqual(built['effective_edges'][0]['original_from_revision_id'], uid(211))
        self.assertEqual(built['effective_edges'][0]['effective_edge_ref']['from_knode_revision_id'], uid(11))
        edge['effective_edge_ref']['applicability_basis_type'] = 'origin_acceptance'
        self.reject(lambda: effective.build_input(source['nodes'], [edge], source['data_id']),
                    'k2k_effective_origin_pair_changed')

    def test_every_candidate_declares_the_complete_ordered_node_and_edge_bundle(self):
        source = packet(extra_node=True, two_edges=True)
        for field in ('premise_revision_ids', 'premise_edge_revision_ids'):
            full = response(source)['nodes'][0][field]
            for refs in (full[:-1], list(reversed(full)), full + full[:1], [], [uid(90)], [None]):
                raw = response(source)
                raw['nodes'][0][field] = refs
                self.reject(lambda: effective.normalize_proposals(raw, source), 'k2k_effective_bundle_incomplete')
        raw = response(source)
        raw['nodes'].append({**deepcopy(raw['nodes'][0]), 'candidate_key': 'other'})
        raw['nodes'][1]['premise_edge_revision_ids'] = []
        self.reject(lambda: effective.normalize_proposals(raw, source), 'k2k_effective_bundle_incomplete')

    def test_normalization_binds_exact_refs_and_retains_legacy_semantic_fingerprints(self):
        source, raw = packet(), response(packet())
        before = deepcopy(raw)
        candidate = k2k.normalize_proposals(raw, source)[0]
        original = legacy.normalize_proposals(legacy.response(), legacy.packet())[0]
        for field in ('identity_fingerprint', 'content_fingerprint', 'semantic_payload'):
            self.assertEqual(candidate[field], original[field])
        self.assertEqual(candidate['premise_effective_edge_refs'], effective.effective_refs(source))
        self.assertEqual(raw, before)
        candidate['premise_effective_edge_refs'][0]['applicability_basis_ref'] = uid(99)
        self.assertNotEqual(candidate['premise_effective_edge_refs'], effective.effective_refs(source))
        self.assertNotIn('premise_effective_edge_refs', raw['nodes'][0])

    def test_models_cannot_supply_binding_origin_depth_direct_sources_or_other_outputs(self):
        source = packet()
        for field, value in (('premise_effective_edge_refs', effective.effective_refs(source)), ('derivation_depth', 1),
                             ('is_inferred', True), ('origin_record_id', uid(50)), ('evidence', []), ('source_requests', [])):
            raw = response(source)
            raw['nodes'][0][field] = value
            self.reject(lambda: effective.normalize_proposals(raw, source), 'invalid_k2k_effective_proposal')
        raw = response(source)
        raw['nodes'][0]['kind'] = 'observation'
        self.reject(lambda: effective.normalize_proposals(raw, source), 'k2k_observation_forbidden')

    def test_independent_four_checks_and_reuse_are_preserved_with_exact_edge_bindings(self):
        source = packet()
        candidates = effective.normalize_proposals(response(source), source)
        value = {'decisions': [legacy.decision()], 'complete': True}
        self.assertEqual(effective.validate_decisions(value, candidates, [], source)['decisions']['inference']['verdict'], 'accepted')
        self.assertEqual(k2k.validate_decisions(value, candidates, []), effective.validate_decisions(value, candidates, [], source))
        for field in k2k.CHECKS:
            wrong = deepcopy(value)
            wrong['decisions'][0][field] = False
            self.reject(lambda: effective.validate_decisions(wrong, candidates, [], source), 'k2k_acceptance_not_justified')
        value['decisions'][0].update(verdict='reused', equivalent_revision_id=uid(90), novel_conclusion=False)
        self.assertEqual(effective.validate_decisions(value, candidates, [uid(90)], source)
                         ['decisions']['inference']['equivalent_revision_id'], uid(90))
        changed = deepcopy(candidates)
        changed[0]['premise_effective_edge_refs'][0]['applicability_basis_ref'] = uid(99)
        self.reject(lambda: effective.validate_decisions(value, changed, [uid(90)], source), 'k2k_effective_bundle_incomplete')

    def test_schema_exposes_model_attribution_ids_but_never_application_ref_fields(self):
        source = packet(extra_node=True, two_edges=True)
        schema = k2k.generation_schema(source)
        item = schema['properties']['nodes']['items']
        self.assertFalse(item['additionalProperties'])
        self.assertEqual(item['properties']['premise_revision_ids']['minItems'], 3)
        self.assertEqual(item['properties']['premise_edge_revision_ids']['items']['enum'], [uid(110), uid(111)])
        self.assertEqual(item['properties']['premise_edge_revision_ids']['maxItems'], 2)
        self.assertIn('premise_edge_revision_ids', item['required'])
        self.assertNotIn('premise_effective_edge_refs', item['properties'])

    def test_prompt_preserves_relation_meaning_and_quote_metadata_without_hidden_edges(self):
        source = packet()
        quote = 'UNDISCLOSED SOURCE QUOTE 😀'
        source['nodes'][0]['groundings'] = [{'quote': quote, 'information_id': uid(80), 'raw_locator': '/paper/page1'}]
        source = effective.build_input(source['nodes'], source['effective_edges'], source['data_id'])
        snap = snapshot(source)
        snap['existing_edges'] = [{'foreign_statement': 'UNBOUND EDGE CATALOG'}]
        context = {'input_snapshot': snap, 'candidates': effective.normalize_proposals(response(source), source)}
        before = deepcopy(context)
        for prompt, _ in (k2k.generation_request(snap), k2k.validation_request(context)):
            self.assertNotIn(quote, prompt)
            self.assertNotIn('UNBOUND EDGE CATALOG', prompt)
            self.assertIn(sha256(quote.encode()).hexdigest(), prompt)
            self.assertIn(source['effective_edges'][0]['effective_edge_ref']['applicability_basis_ref'], prompt)
            self.assertIn('not automatically a logical', prompt)
            self.assertIn('explosion', prompt)
            self.assertIn('independent experimental evidence', prompt)
            self.assertIn('No D2I, D2K', prompt)
        self.assertEqual(context, before)
        self.reject(lambda: k2k.generation_request(snap, [{}]), 'k2k_direct_media_forbidden')
        bad = deepcopy(context)
        bad['candidates'][0]['premise_revision_ids'].reverse()
        self.reject(lambda: k2k.validation_request(bad), 'k2k_effective_bundle_incomplete')

    def test_explicit_revision_and_mandatory_revalidation_wrappers_still_apply(self):
        snap = snapshot()
        target = {**deepcopy(snap['input']['nodes'][0]), 'knode_id': uid(501), 'knode_revision_id': uid(502),
            'current_revision_id': uid(502), 'identity_scope': 'general', 'source_data_id': None,
            'identity_fingerprint': 'a' * 64, 'content_fingerprint': 'b' * 64}
        snap['revision_target'] = knowledge_revision.freeze_target(target, operation='k2k',
            target_knode_id=uid(501), expected_revision_id=uid(502))
        snap['existing_nodes'] = [target]
        required = {'schema_version': revalidation.PROFILE, 'kind': 'node', 'target_revision_id': uid(502),
            'target_knode_id': uid(501), 'prior_support_record_id': uid(503),
            'premise_revision_ids': effective.check_input(snap['input'])}
        snap['revalidation_target'] = {**required, 'target_sha256': digest(required)}
        context = {'input_snapshot': snap, 'candidates': effective.normalize_proposals(response(snap['input']), snap['input'])}
        gen, schema = k2k.generation_request(snap)
        val, validation_schema = k2k.validation_request(context)
        self.assertEqual(schema['properties']['nodes']['maxItems'], 1)
        self.assertIn('revision_review', validation_schema['properties'])
        for prompt in (gen, val):
            self.assertIn('EXPLICIT KNOWLEDGE REVISION', prompt)
            self.assertIn('MANDATORY EXISTING CONCLUSION REVIEW', prompt)
            self.assertIn('Empty output remains unresolved', prompt)

    def test_empty_discovery_and_incomplete_validation_keep_original_completion_semantics(self):
        source = packet()
        self.assertEqual(k2k.normalize_proposals({'nodes': [], 'complete': True, 'coverage_notes': []}, source), [])
        self.assertEqual(effective.validate_decisions({'decisions': [], 'complete': True}, [], [], source),
                         {'decisions': {}, 'complete': True})
        candidates = effective.normalize_proposals(response(source), source)
        checked = effective.validate_decisions({'decisions': [legacy.decision()], 'complete': False}, candidates, [], source)
        self.assertFalse(checked['complete'])


if __name__ == '__main__':
    unittest.main()
