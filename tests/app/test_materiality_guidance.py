"""New propagation-only guidance; preserve exact prior prompts and schemas."""

from copy import deepcopy
from hashlib import sha256
import unittest

from palimpsest import k2k, knowledge_requests
from palimpsest.knowledge_revision_runtime import MATERIALITY_POLICY, materiality_guidance
from palimpsest.i2k import digest
import test_k2k as inference_fixture
import test_knowledge_revision as revision_fixture


def snapshot(operation='k2k', *, active=False, target=False):
    packet = inference_fixture.packet()
    value = {'input': packet if operation == 'k2k' else {'schema_version': 'n2e-input-v1', 'nodes': packet['nodes']},
        'existing_nodes': deepcopy(packet['nodes']), 'existing_edges': []}
    if active:
        value['propagation_scope'] = {'policy': {'materiality_policy': MATERIALITY_POLICY, 'repeated_outcome': 'observe'}}
    if target:
        value['revision_target'] = revision_fixture.comparison('k2k')
        value['existing_nodes'].append(value['revision_target']['target'])
    return value


def context(value):
    return {'input_snapshot': value, 'candidates': [], 'generator_complete': True, 'source_requests': []}


class MaterialityGuidanceTests(unittest.TestCase):
    def test_unbound_exact_prompt_and_schema_hashes_match_measured_prechange_bytes(self):
        cases = [
            (k2k.generation_request(snapshot(), []), 'e76a04da5c907a508f266945f81a65b87553ee036348f6259c470400afb16e5a',
             'd57b06fb7b0b0c7ffaac36697af3839e3e2e899d5db5f773a8f3d9e0c88795e5'),
            (k2k.validation_request(context(snapshot()), []), 'a577726201a850af531ce56787c38f7a2b632fef2dee8427b7c9d895434008a4',
             '73a0d9c481707bfe0fe136ecb1b14f8fca71844f2452eac69bf8af3e4ecb70bb'),
            (knowledge_requests.edge_generation_request(snapshot('n2e')), 'f63a02839145b63f7f7ad5e65f38484740a8fa0c80a8ea58f862def13ad9518e',
             '9942767ae3183ff18f8e98adae16d3477beaaac7a79f675990b5c7be14410a3d'),
            (knowledge_requests.edge_validation_request(context(snapshot('n2e'))), '5d6b2078a5e8d2e82762b5ba857f3f51f631f2f97e93ee72794bd47fa4820fe6',
             '37f1bfdb8f8c5a5bf4101c009842347563a3aa2bcbf705c4faf5316085fcfccc'),
        ]
        for (prompt, schema), expected_prompt, expected_schema in cases:
            self.assertEqual(sha256(prompt.encode()).hexdigest(), expected_prompt)
            self.assertEqual(digest(schema), expected_schema)

    def test_policy_is_only_enabled_by_exact_frozen_new_run_shape(self):
        for scope in (None, {}, {'policy': {}}, {'policy': {'anomaly_detection': 'legacy'}},
                      {'policy': {'materiality_policy': MATERIALITY_POLICY}},
                      {'policy': {'materiality_policy': MATERIALITY_POLICY, 'repeated_outcome': 'suspend'}},
                      {'policy': {'materiality_policy': 'future-policy', 'repeated_outcome': 'observe'}}):
            value = snapshot()
            value['propagation_scope'] = scope
            self.assertEqual(materiality_guidance(value, 'k2k', 'validator'), '')
        value = snapshot(active=True)
        for operation in ('i2k', 'd2k', 'w2k'):
            self.assertEqual(materiality_guidance(value, operation, 'validator'), '')
        injected = snapshot()
        injected['source_text'] = repr(value['propagation_scope'])
        self.assertEqual(materiality_guidance(injected, 'k2k', 'validator'), '')

    def test_discovery_uses_honest_current_revision_reuse_without_new_schema_fields(self):
        value = snapshot(active=True)
        before = deepcopy(value)
        prompt, schema = k2k.validation_request(context(value), [])
        self.assertEqual(schema, k2k.validation_request(context(snapshot()), [])[1])
        for text in ('current accepted snapshot', 'ordinary reused', 'equivalent_revision_id',
                     'novel_conclusion=false', 'fingerprint or wording alone', 'schema has no revision_review'):
            self.assertIn(text, prompt)
        self.assertNotIn('revision_review', schema['properties'])
        self.assertEqual(value, before)

    def test_explicit_target_nonmaterial_requires_current_claim_support_and_undecidable_holds(self):
        current = snapshot(active=True, target=True)
        baseline = snapshot(target=True)
        prompt, schema = k2k.validation_request(context(current), [])
        self.assertEqual(schema, k2k.validation_request(context(baseline), [])[1])
        for text in ('unchanged accepted claim', 'truth conditions', 'decision consequences', 'procedural obligations',
                     'null remains unresolved', 'last generated candidate', 'minor or meaningful',
                     'Empty output does not', 'updated support is still independently validated'):
            self.assertIn(text, prompt)
        self.assertEqual(schema['properties']['revision_review'], {'type': 'null'})

    def test_domain_precision_categorical_changes_and_conflicts_are_not_silently_smoothed(self):
        prompt, _ = k2k.generation_request(snapshot(active=True), [])
        for text in ('no\nuniversal numeric epsilon or embedding threshold', 'polarity', 'quantifiers',
                     'ordered procedure steps', 'Do not average contradictory facts', 'separate experimental records',
                     'last\naccepted meaning', 'guaranteed damping', 'independent Validator decides materiality'):
            self.assertIn(text, prompt)
        self.assertEqual(prompt.count('ACCEPTED-STATE MATERIALITY POLICY:'), 1)

    def test_N2E_relation_status_and_materiality_remain_distinct(self):
        value = snapshot('n2e', active=True)
        prompt, schema = knowledge_requests.edge_validation_request(context(value))
        self.assertEqual(schema, knowledge_requests.edge_validation_request(context(snapshot('n2e')))[1])
        for text in ('applicable=false describes a negative relation status', 'material\nchange',
                     'Uncertain/pending is not a', 'original semantic revision', 'same-worded predicate',
                     'dependency maintenance', 'already pending obligation'):
            self.assertIn(text, prompt)
        self.assertEqual(prompt.count('ACCEPTED-STATE MATERIALITY POLICY:'), 1)

    def test_new_generation_and_validation_guidance_does_not_change_output_contract(self):
        for operation in ('k2k', 'n2e'):
            old, new = snapshot(operation), snapshot(operation, active=True)
            if operation == 'k2k':
                first, schema = k2k.generation_request(new, [])
                _, old_schema = k2k.generation_request(old, [])
            else:
                first, schema = knowledge_requests.edge_generation_request(new)
                _, old_schema = knowledge_requests.edge_generation_request(old)
            self.assertEqual(schema, old_schema)
            self.assertIn('Repetition is not a reason to stop, reject, accept, or reuse', first)
            self.assertIn('do not add a convergence score, tolerance, control action or authority field.', first)


if __name__ == '__main__':
    unittest.main()
