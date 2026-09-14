"""Synthetic inference contracts; no model, code execution or canonical writes."""

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.i2k_selection import selection_fingerprints
from palimpsest.k2k import (build_input, check_input, generation_schema, validation_schema,
                           normalize_proposals, validate_decisions, generation, validation)


def uid(number):
    return f'019947e2-1234-7000-8000-{number:012x}'


def semantic(subject='A', relation='implies', object='B'):
    return {'subject': subject, 'relation': relation, 'object': object, 'polarity': 'positive',
            'quantifier': 'all', 'scope': '', 'conditions': [], 'time_range': ''}


def packet():
    return build_input([{'knode_id': uid(n), 'knode_revision_id': uid(n + 10),
        'kind': 'proposition', 'statement': statement, 'semantic_payload': semantic(*terms),
        'origin_record_id': uid(n + 20), 'transitive_provenance': {'source_ids': ['1' * 64]}}
        for n, statement, terms in [(1, 'A implies B.', ('A', 'implies', 'B')),
                                   (2, 'B implies C.', ('B', 'implies', 'C'))]], '1' * 64)


def response():
    return {'nodes': [{'candidate_key': 'inference', 'kind': 'proposition', 'statement': 'A implies C.',
        'semantic_payload': semantic('A', 'implies', 'C'), 'identity_scope': 'general', 'source_data_id': None,
        'premise_revision_ids': [uid(11), uid(12)], 'inference_type': 'deductive', 'assumptions': [],
        'limitations': ['Only under the exact scopes of both premises.'],
        'derivation_basis': 'Transitivity of the two explicitly supplied implications.'}],
        'complete': True, 'coverage_notes': []}


def decision(key='inference'):
    return {'candidate_key': key, 'verdict': 'accepted', 'equivalent_candidate_key': None,
        'equivalent_revision_id': None, 'reason_codes': ['valid_inference'],
        'reason': 'Synthetic validation fixture; no model judgment was performed.',
        'inference_valid': True, 'premises_sufficient': True, 'limits_preserved': True, 'novel_conclusion': True}


class K2KTests(unittest.TestCase):
    def reject(self, action, code=None):
        with self.assertRaises(PalimpsestError) as caught:
            action()
        if code:
            self.assertEqual(caught.exception.code, code)

    def test_exact_input_order_and_provenance_are_frozen_without_mutation(self):
        source = packet()
        nodes = list(reversed(source['nodes']))
        before = deepcopy(nodes)
        result = build_input(nodes, source['data_id'])
        self.assertEqual(result['nodes'], before)
        self.assertEqual(check_input(result), [uid(12), uid(11)])
        nodes[0]['transitive_provenance']['source_ids'].clear()
        self.assertEqual(result['nodes'], before)
        result['nodes'][0]['statement'] = 'Tampered premise.'
        self.reject(lambda: check_input(result), 'k2k_input_changed')

    def test_two_distinct_logical_premises_not_two_revisions_or_duplicates(self):
        original = packet()['nodes']
        for nodes in [[], original[:1], [original[0], original[0]],
                      [original[0], {**original[1], 'knode_id': original[0]['knode_id']}],
                      [original[0], {**original[1], 'knode_revision_id': original[0]['knode_revision_id']}]]:
            self.reject(lambda: build_input(nodes, '1' * 64), 'k2k_distinct_premises_required')
        changed = deepcopy(original)
        changed[0]['current_revision_id'] = uid(99)
        self.reject(lambda: build_input(changed, '1' * 64), 'invalid_k2k_input')
        changed = deepcopy(original)
        changed[0]['knode_id'] = str(changed[0]['knode_id']).upper()
        self.reject(lambda: build_input(changed, '1' * 64))

    def test_normalized_proposition_reuses_existing_semantic_identity_profile(self):
        raw = response()
        before = deepcopy(raw)
        result = normalize_proposals(raw, packet())[0]
        self.assertEqual(raw, before)
        fingerprints = selection_fingerprints('proposition', result['semantic_payload'], 'general', None)
        self.assertEqual({key: result[key] for key in fingerprints}, fingerprints)
        self.assertNotIn('evidence', result)
        self.assertNotIn('is_inferred', result)
        self.assertNotIn('derivation_depth', result)
        for field in ('premise_revision_ids', 'inference_type', 'assumptions', 'limitations', 'derivation_basis'):
            self.assertEqual(result[field], raw['nodes'][0][field])
        raw['nodes'][0].update(inference_type='inductive', identity_scope='source', source_data_id='1' * 64)
        self.assertEqual(normalize_proposals(raw, packet())[0]['inference_type'], 'inductive')

    def test_observations_direct_I_and_model_owned_origin_or_depth_are_rejected(self):
        for field, value in [('evidence', [{'information_id': uid(55)}]), ('is_inferred', True),
                             ('origin_operation', 'k2k'), ('knode_id', uid(60)), ('derivation_depth', 1),
                             ('origin_record_id', uid(61)), ('source_requests', [])]:
            raw = response()
            raw['nodes'][0][field] = value
            with self.subTest(field=field): self.reject(lambda: normalize_proposals(raw, packet()))
        raw = response()
        raw['nodes'][0]['kind'] = 'observation'
        self.reject(lambda: normalize_proposals(raw, packet()), 'k2k_observation_forbidden')
        raw = response()
        raw['source_requests'] = []
        self.reject(lambda: normalize_proposals(raw, packet()))

    def test_candidate_premises_must_be_two_owned_exact_revisions(self):
        for refs in [[uid(11)], [uid(11), uid(11)], [uid(11), uid(99)], [uid(1), uid(2)],
                     [uid(11), None], [uid(11), uid(12).upper()], 'premises']:
            raw = response()
            raw['nodes'][0]['premise_revision_ids'] = refs
            self.reject(lambda: normalize_proposals(raw, packet()), 'k2k_distinct_premises_required')

    def test_scope_inference_type_and_nonempty_explanation_are_required(self):
        for field, value in [('identity_scope', 'paper'), ('source_data_id', '2' * 64),
                             ('inference_type', 'observation'), ('assumptions', 'none'),
                             ('limitations', ['']), ('derivation_basis', ' '), ('statement', '\x00')]:
            raw = response()
            raw['nodes'][0][field] = value
            self.reject(lambda: normalize_proposals(raw, packet()))
        raw = response()
        raw['nodes'][0].update(identity_scope='source', source_data_id='2' * 64)
        self.reject(lambda: normalize_proposals(raw, packet()), 'invalid_k2k_identity_scope')
        raw['nodes'][0]['source_data_id'] = None
        self.reject(lambda: normalize_proposals(raw, packet()), 'invalid_k2k_identity_scope')

    def test_independent_validation_requires_all_checks_for_new_inference(self):
        candidates = normalize_proposals(response(), packet())
        for field in ('inference_valid', 'premises_sufficient', 'limits_preserved', 'novel_conclusion'):
            item = decision()
            item[field] = False
            self.reject(lambda: validate_decisions({'decisions': [item], 'complete': True}, candidates, []),
                        'k2k_acceptance_not_justified')
            item[field] = 1
            self.reject(lambda: validate_decisions({'decisions': [item], 'complete': True}, candidates, []))
        item = decision()
        item.update(verdict='rejected', inference_valid=False, premises_sufficient=False,
                    limits_preserved=False, novel_conclusion=False)
        self.assertEqual(validate_decisions({'decisions': [item], 'complete': True}, candidates, [])
                         ['decisions']['inference']['verdict'], 'rejected')

    def test_reuse_has_one_exact_target_and_can_preserve_same_meaning(self):
        candidates = normalize_proposals(response(), packet())
        item = decision()
        item.update(verdict='reused', equivalent_revision_id=uid(90), novel_conclusion=False)
        checked = validate_decisions({'decisions': [item], 'complete': True}, candidates, [uid(90)])
        self.assertEqual(checked['decisions']['inference']['equivalent_revision_id'], uid(90))
        self.reject(lambda: validate_decisions({'decisions': [item], 'complete': True}, candidates, []))
        item['equivalent_candidate_key'] = 'inference'
        self.reject(lambda: validate_decisions({'decisions': [item], 'complete': True}, candidates, [uid(90)]))
        item['equivalent_revision_id'] = None
        self.reject(lambda: validate_decisions({'decisions': [item], 'complete': True}, candidates, []))
        item.update(equivalent_candidate_key=None, equivalent_revision_id=uid(90), premises_sufficient=False)
        self.reject(lambda: validate_decisions({'decisions': [item], 'complete': True}, candidates, [uid(90)]))

    def test_batch_reuse_is_ordered_and_cycles_are_rejected(self):
        raw = response()
        raw['nodes'].append({**deepcopy(raw['nodes'][0]), 'candidate_key': 'duplicate'})
        candidates = normalize_proposals(raw, packet())
        root, duplicate = decision(), decision('duplicate')
        duplicate.update(verdict='reused', equivalent_candidate_key='inference', novel_conclusion=False)
        checked = validate_decisions({'decisions': [duplicate, root], 'complete': True}, candidates, [])
        self.assertEqual(list(checked['decisions']), ['inference', 'duplicate'])
        root.update(verdict='reused', equivalent_candidate_key='duplicate')
        self.reject(lambda: validate_decisions({'decisions': [duplicate, root], 'complete': True}, candidates, []),
                    'knowledge_reuse_cycle')

    def test_empty_output_and_incomplete_review_do_not_fabricate_completion(self):
        self.assertEqual(normalize_proposals({'nodes': [], 'complete': True, 'coverage_notes': []}, packet()), [])
        self.assertEqual(validate_decisions({'decisions': [], 'complete': True}, [], []),
                         {'decisions': {}, 'complete': True})
        candidates = normalize_proposals(response(), packet())
        checked = validate_decisions({'decisions': [decision()], 'complete': False}, candidates, [])
        self.assertFalse(checked['complete'])
        self.assertEqual(checked['decisions']['inference']['verdict'], 'accepted')
        self.reject(lambda: validate_decisions({'decisions': [], 'complete': False}, candidates, []))
        raw = response()
        raw['complete'] = 1
        self.reject(lambda: normalize_proposals(raw, packet()))

    def test_schema_and_prompts_expose_exact_K_only_and_no_execution_claim(self):
        source = packet()
        schema = generation_schema(source)
        fields = schema['properties']['nodes']['items']['properties']
        self.assertEqual(fields['premise_revision_ids']['items']['enum'], [uid(11), uid(12)])
        self.assertEqual(fields['kind']['enum'], ['proposition'])
        self.assertNotIn('evidence', fields)
        self.assertNotIn('is_inferred', fields)
        snapshot = {'input': source, 'existing_nodes': [], 'existing_edges': []}
        prompt = generation(snapshot)
        self.assertIn(uid(11), prompt)
        self.assertIn('not proof of actual execution', prompt)
        self.assertIn('untrusted evidence', prompt)
        self.reject(lambda: generation(snapshot, [{'sha256': 'a' * 64}]), 'k2k_direct_media_forbidden')
        context = {'input_snapshot': snapshot, 'candidates': normalize_proposals(response(), source)}
        self.assertIn('Independent Validator', validation(context))
        self.assertEqual(validation_schema([], [])['properties']['decisions']['maxItems'], 0)
        branches = validation_schema(['inference'], [uid(90)])['properties']['decisions']['items']['anyOf']
        self.assertEqual(len(branches), 3)
        self.assertTrue(all(set(('inference_valid', 'premises_sufficient', 'limits_preserved', 'novel_conclusion'))
                            <= set(branch['required']) for branch in branches))

    def test_prompts_project_source_quotes_without_changing_K_or_frozen_provenance(self):
        source = packet()
        known = deepcopy(source['nodes'][0])
        quotes = []
        for index, owner in enumerate((source['nodes'][0], known)):
            for field in ('groundings', 'direct_groundings', 'transitive_source_refs'):
                quote = f'UNDELIVERED_I_QUOTE_{index}_{field} 😀 Cafe\u0301\r\n'
                quotes.append(quote)
                owner[field] = [{'quote': quote, 'information_id': uid(51), 'node_revision_id': uid(11),
                                 'source_execution_id': uid(61), 'char_start': 9, 'char_end': 9 + len(quote),
                                 'raw_locator': '/source/code.py:41', 'data_id': 'a' * 64}]
        source = build_input(source['nodes'], source['data_id'])
        snapshot = {'input': source, 'existing_nodes': [known], 'existing_edges': []}
        context = {'input_snapshot': snapshot, 'candidates': normalize_proposals(response(), source)}
        before_snapshot, before_context = deepcopy(snapshot), deepcopy(context)
        generator_prompt, validator_prompt = generation(snapshot), validation(context)
        for prompt in (generator_prompt, validator_prompt):
            for quote in quotes:
                self.assertNotIn(quote, prompt)
                self.assertNotIn(json.dumps(quote, ensure_ascii=False)[1:-1], prompt)
                self.assertIn(sha256(quote.encode('utf-8')).hexdigest(), prompt)
            self.assertIn(source['nodes'][0]['statement'], prompt)
            self.assertIn(source['nodes'][1]['statement'], prompt)
            self.assertIn('/source/code.py:41', prompt)
            self.assertIn(uid(51), prompt)
            self.assertIn(source['input_sha256'], prompt)
        projected = json.loads(generator_prompt.split('PREMISES_AND_CATALOG_JSON:\n', 1)[1])
        self.assertEqual(projected['input']['nodes'][0]['semantic_payload'], source['nodes'][0]['semantic_payload'])
        for field in ('groundings', 'direct_groundings', 'transitive_source_refs'):
            original = source['nodes'][0][field][0]
            retained = projected['input']['nodes'][0][field][0]
            self.assertNotIn('quote', retained)
            self.assertEqual(retained['quote_character_count'], len(original['quote']))
            self.assertEqual({k: v for k, v in retained.items() if k not in ('quote_sha256', 'quote_character_count')},
                             {k: v for k, v in original.items() if k != 'quote'})
        self.assertEqual(snapshot, before_snapshot)
        self.assertEqual(context, before_context)
        self.assertEqual(check_input(source), [uid(11), uid(12)])


if __name__ == '__main__':
    unittest.main()
