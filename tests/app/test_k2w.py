"""Pure K2W boundaries: these checks do not claim live semantic correctness."""

from copy import deepcopy
import json
import unittest

from palimpsest import k2w, k2w_prompts, wisdom
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest


def uid(number):
    return f'019947e2-1234-7000-8000-{number:012x}'


def packet(*, recommendation=False, edge=False):
    nodes = [{'knode_id': uid(index), 'knode_revision_id': uid(index + 10),
        'kind': 'proposition', 'statement': text, 'semantic_payload': {
            'subject': f'Option {index}', 'relation': 'has', 'object': 'bounded capacity',
            'polarity': 'positive', 'quantifier': '', 'scope': 'test fixture',
            'conditions': [], 'time_range': ''}, 'current_support_signature': digest(index)}
        for index, text in [(1, 'Option A has a documented capacity bound.'),
                            (2, 'The bound is valid only for an independent cache.')]]
    edges = []
    if edge:
        edges.append({'kedge_id': uid(30), 'predicate': 'qualifies',
            'qualifiers': {'scope': 'Independent caches only.', 'conditions': []},
            'original_from_revision_id': uid(12), 'original_to_revision_id': uid(11),
            'effective_edge_ref': {'semantic_kedge_revision_id': uid(31),
                'from_knode_revision_id': uid(12), 'to_knode_revision_id': uid(11),
                'applicability_basis_type': 'origin_acceptance', 'applicability_basis_ref': uid(32),
                'relation_read_state_token': digest('read')},
            'endpoint_support_signatures': [nodes[1]['current_support_signature'], nodes[0]['current_support_signature']]})
    return k2w.build_input(nodes, edges, query='Explain the documented bound.',
        context_snapshot={'priority': 'predictable memory'}, knowledge_state_version=10,
        wisdom_kind='recommendation' if recommendation else 'explanation')


def answer(*, recommendation=False, edge=False):
    return {'status': 'answered', 'claims': [{'claim_key': 'capacity',
        'text': 'The documented bound applies under the independent-cache condition.',
        'epistemic_basis': 'advisory_recommendation' if recommendation else 'accepted_knowledge',
        'k_revision_ids': [uid(11), uid(12)], 'effective_edge_revision_ids': [uid(31)] if edge else [],
        'assumptions': [], 'limitations': ['The documented scope only.']}],
        'recommendation': {'options': [{'option_key': 'A', 'label': 'Option A'}],
            'criteria': ['predictable memory'], 'comparison': [{'option_key': 'A',
                'criterion': 'predictable memory', 'claim_keys': ['capacity']}],
            'recommended_option': 'A'} if recommendation else None, 'unresolved': []}


def validation(value):
    return {'verdict': 'accepted', 'claims': [{'claim_key': claim['claim_key'],
        **{name: True for name in k2w.CLAIM_CHECKS}} for claim in value['claims']],
        'query_addressed': True, 'advisory_boundary_preserved': True,
        'reason': 'Synthetic structural fixture; no live semantic validation.'}


class K2WTests(unittest.TestCase):
    def rejects(self, function, code=None):
        with self.assertRaises(PalimpsestError) as caught:
            function()
        if code:
            self.assertEqual(caught.exception.code, code)

    def test_single_node_allowed_but_changed_input_and_duplicate_logical_nodes_rejected(self):
        source = packet()
        single = k2w.build_input(source['nodes'][:1], query='What is A?',
            context_snapshot={}, knowledge_state_version=10)
        self.assertEqual(k2w.check_input(single), [uid(11)])
        changed = deepcopy(source)
        changed['context_snapshot']['priority'] = 'unrecorded change'
        self.rejects(lambda: k2w.check_input(changed), 'k2w_input_changed')
        self.rejects(lambda: k2w.build_input(source['nodes'] * 2, query='Q',
            context_snapshot={}, knowledge_state_version=10))
        self.rejects(lambda: k2w.build_input(source['nodes'], query='Q',
            context_snapshot={}, knowledge_state_version=10, wisdom_kind='decision'))

    def test_exact_edge_and_both_effective_endpoints_are_required(self):
        source, value = packet(edge=True), answer(edge=True)
        self.assertEqual(k2w.normalize_answer(value, source), value)
        for mutate in (lambda v: v['claims'][0].update(k_revision_ids=[uid(11)]),
                       lambda v: v['claims'][0].update(effective_edge_revision_ids=[uid(90)]),
                       lambda v: v['claims'][0].update(k_revision_ids=[uid(90)])):
            changed = deepcopy(value)
            mutate(changed)
            self.rejects(lambda: k2w.normalize_answer(changed, source))
        changed = deepcopy(source)
        changed['effective_edges'][0]['effective_edge_ref']['applicability_basis_type'] = 'pending'
        self.rejects(lambda: k2w.check_input(changed))

    def test_model_cannot_emit_ids_direct_information_or_authority(self):
        for field, injected in [('wisdom_id', uid(91)), ('information_ids', [uid(92)]),
                                ('confirmation_ref', 'I approve'), ('new_knowledge', [])]:
            value = answer()
            value[field] = injected
            self.rejects(lambda: k2w.normalize_answer(value, packet()))
        value = answer()
        value['claims'][0]['epistemic_basis'] = 'advisory_recommendation'
        self.rejects(lambda: k2w.normalize_answer(value, packet()), 'k2w_advisory_kind_required')

    def test_claim_text_rejects_punctuation_only_placeholder(self):
        value = answer()
        value['claims'][0]['text'] = '...'
        self.rejects(lambda: k2w.normalize_answer(value, packet()), 'invalid_k2w_claim')

    def test_recommendation_requires_closed_options_complete_comparison_and_exact_claims(self):
        source, value = packet(recommendation=True), answer(recommendation=True)
        self.assertEqual(k2w.normalize_answer(value, source), value)
        for mutate in (lambda v: v['recommendation'].update(recommended_option='unknown'),
                       lambda v: v['recommendation'].update(recommended_option=[]),
                       lambda v: v['recommendation'].update(comparison=[]),
                       lambda v: v['recommendation']['comparison'][0].update(claim_keys=['missing']),
                       lambda v: v['recommendation']['comparison'][0].update(option_key=[]),
                       lambda v: v['recommendation'].update(confirmed=True)):
            changed = deepcopy(value)
            mutate(changed)
            self.rejects(lambda: k2w.normalize_answer(changed, source))

    def test_partial_and_insufficient_answers_retain_missing_basis(self):
        value = {'status': 'insufficient', 'claims': [], 'recommendation': None,
                 'unresolved': ['The selected K do not specify cost.']}
        checked = k2w.normalize_answer(value, packet())
        self.assertEqual(k2w.validate_answer(validation(checked), checked)['verdict'], 'accepted')
        value['unresolved'] = []
        self.rejects(lambda: k2w.normalize_answer(value, packet()))
        value.update(status='answered', unresolved=[])
        self.rejects(lambda: k2w.normalize_answer(value, packet()))

    def test_independent_validation_exhaustive_and_all_acceptance_checks_true(self):
        value = answer()
        for name in k2w.CLAIM_CHECKS:
            check = validation(value)
            check['claims'][0][name] = False
            self.rejects(lambda: k2w.validate_answer(check, value), 'k2w_acceptance_not_justified')
        for mutate in (lambda v: v.update(claims=[]),
                       lambda v: v.update(advisory_boundary_preserved=False),
                       lambda v: v.update(query_addressed=1),
                       lambda v: v['claims'].append(deepcopy(v['claims'][0]))):
            check = validation(value)
            mutate(check)
            self.rejects(lambda: k2w.validate_answer(check, value))

    def test_prompts_deliver_K_meaning_and_inference_limits_without_nested_source_quotes(self):
        source = packet()
        source['nodes'][0].update(groundings=[{'quote': 'SECRET_SOURCE_QUOTE'}],
            generation_origin={'origin_operation': 'k2k', 'is_inferred': True,
                'limitations': ['Explicit inference limit.'], 'premise_revision_ids': [uid(55)],
                'validation': {'quote': 'SECRET_VALIDATOR_QUOTE'}})
        source = k2w.build_input(source['nodes'], query=source['query'],
            context_snapshot=source['context_snapshot'], knowledge_state_version=10,
            retrieval_snapshot={'quote': 'SECRET_RETRIEVAL_QUOTE'})
        prompt, schema = k2w_prompts.generation_request(source)
        self.assertNotIn('SECRET_', prompt)
        self.assertIn('Explicit inference limit.', prompt)
        self.assertIn(source['nodes'][0]['statement'], prompt)
        self.assertFalse(schema['additionalProperties'])
        review, review_schema = k2w_prompts.validation_request(source, answer())
        self.assertNotIn('SECRET_', review)
        self.assertIn('Independent Validator', review)
        json.dumps(review_schema, allow_nan=False)

    def test_similar_observations_keep_source_and_exact_version_attribution_without_source_text(self):
        original = packet()
        versions = []
        for index, node in enumerate(original['nodes'], 1):
            version = {'version_id': uid(150 + index), 'series_id': uid(160), 'parent_version_id': None,
                'data_id': str(index) * 64, 'version_number': index,
                'title': 'SECRET_VERSION_TITLE', 'message': 'SECRET_VERSION_SOURCE_TEXT'}
            versions.append(version)
            node.update(kind='observation', statement='The sample increased.', identity_scope='source',
                source_data_id=version['data_id'], source_data_ids=[version['data_id']],
                grounding_data_ids=[version['data_id']], origin_data_versions=[version],
                data_version_supports=[{'record_id': uid(170 + index), 'operation': 'i2k',
                    'version_ids': [version['version_id']], 'versions': [version], 'quote': 'SECRET_SUPPORT_QUOTE'}],
                source_version_current_heads=[{'series_id': version['series_id'], 'version_id': version['version_id']}])
        value = k2w.build_input(original['nodes'], query='Compare the two source observations.',
            context_snapshot={}, knowledge_state_version=10)
        prompt, _ = k2w_prompts.generation_request(value)
        delivered = json.loads(prompt.split('INPUT_JSON:\n', 1)[1])
        for index, node in enumerate(delivered['nodes']):
            self.assertEqual(node['source_data_id'], versions[index]['data_id'])
            self.assertEqual(node['identity_scope'], 'source')
            self.assertEqual(node['origin_data_versions'][0]['version_id'], versions[index]['version_id'])
            self.assertEqual(node['data_version_supports'][0]['versions'][0]['data_id'], versions[index]['data_id'])
            self.assertEqual(node['source_version_current_heads'][0]['version_id'], versions[index]['version_id'])
        self.assertNotIn('SECRET_', prompt)
        self.assertNotEqual(delivered['nodes'][0]['source_data_id'], delivered['nodes'][1]['source_data_id'])

    def test_wisdom_is_distinct_app_owned_snapshot_with_actual_citations_and_no_W2K(self):
        source, value = packet(edge=True), answer(edge=True)
        args = dict(execution_id=uid(80), created_at='2026-09-14T12:00:00+00:00',
            packet=source, answer=value, validation=validation(value), generation_profile={'schema_version': k2w.PROFILE})
        first = wisdom.build_snapshot(wisdom_id=uid(81), **args)
        second = wisdom.build_snapshot(wisdom_id=uid(82), **args)
        self.assertNotEqual(first['snapshot_sha256'], second['snapshot_sha256'])
        self.assertEqual(first['used_k_revision_ids'], [uid(11), uid(12), uid(31)])
        self.assertEqual(first['used_information_ids'], [])
        self.assertEqual(first['used_effective_edge_refs'], [source['effective_edges'][0]['effective_edge_ref']])
        self.assertEqual(first['answer_or_payload'], value)
        self.assertNotIn('confirmation_ref', first)
        self.assertNotIn('knode_id', first)
        args['validation']['verdict'] = 'needs_human'
        self.rejects(lambda: wisdom.build_snapshot(wisdom_id=uid(83), **args), 'wisdom_requires_independent_acceptance')


if __name__ == '__main__':
    unittest.main()
