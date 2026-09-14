"""Pure explicit K materiality boundaries; no source reading or publication."""

from copy import deepcopy
from hashlib import sha256
import unittest
from unittest.mock import patch

from palimpsest import knowledge_revision as revision
from palimpsest.errors import PalimpsestError
from palimpsest.i2k_selection import selection_fingerprints


def uid(number):
    return f'019947e2-1234-7000-8000-{number:012x}'


def semantic(object_value='Original explicit meaning'):
    return {'subject': 'One logical entity', 'relation': 'has a stated property', 'object': object_value,
        'polarity': 'positive', 'quantifier': 'qualified', 'scope': 'same source entity', 'conditions': [], 'time_range': ''}


def target():
    payload = semantic()
    return {'knode_id': uid(1), 'knode_revision_id': uid(2), 'current_revision_id': uid(2),
        'kind': 'proposition', 'identity_scope': 'source', 'source_data_id': 'a' * 64,
        'semantic_payload': payload, 'statement': 'Original display statement.',
        **selection_fingerprints('proposition', payload, 'source', 'a' * 64), 'origin_record_id': uid(3),
        'current_applicability': 'current_premises'}


def comparison(operation='i2k', value=None):
    return revision.freeze_target(value or target(), operation=operation,
        target_knode_id=uid(1), expected_revision_id=uid(2))


def candidate(operation='i2k', *, object_value='Changed explicit meaning'):
    payload = semantic(object_value)
    result = {'candidate_key': 'change', 'kind': 'proposition', 'identity_scope': 'source',
        'source_data_id': 'a' * 64, 'statement': 'Proposed display statement.', 'semantic_payload': payload,
        **selection_fingerprints('proposition', payload, 'source', 'a' * 64)}
    quote = 'Actual source text'
    if operation == 'i2k':
        result.update(claim_basis='explicit_source_content', is_inferred=False,
            evidence=[{'information_id': uid(10), 'data_id': 'a' * 64, 'source_execution_id': uid(11),
                'quote': quote, 'char_start': 0, 'char_end': len(quote), 'media_sha256': None, 'source_role': 'other'}])
    elif operation == 'd2k':
        result.update(claim_basis='explicit_source_content', is_inferred=False,
            direct_evidence=[{'view_id': uid(12), 'data_id': 'a' * 64, 'representation': 'original_utf8_excerpt',
                'quote': quote, 'quote_sha256': sha256(quote.encode()).hexdigest(),
                'char_start': 0, 'char_end': len(quote), 'media_sha256': None, 'source_role': 'other',
                'locator': {'byte_start': 0, 'byte_end': len(quote), 'char_start': 0, 'char_end': len(quote),
                            'line_start': 1, 'line_end': 1}}])
    else:
        result.update(premise_revision_ids=[uid(20), uid(21)], inference_type='deductive',
            assumptions=['Synthetic premise rule.'], limitations=['Pure storage-contract fixture.'],
            derivation_basis='Synthetic exact-premise derivation.', derivation_depth=1)
    return result


def review(material=True):
    return {'comparison_base_revision_id': uid(2), 'same_identity': True, 'material_change': material,
        'grounding_valid': True, 'reason_codes': ['synthetic_independent_review'],
        'reason': 'Independent test decision, not a live semantic-quality result.'}


class KnowledgeRevisionTests(unittest.TestCase):
    def reject(self, callback, code=None):
        with self.assertRaises(PalimpsestError) as caught:
            callback()
        if code:
            self.assertEqual(caught.exception.code, code)

    def test_exact_current_target_snapshot_excludes_raw_source_and_preserves_core(self):
        original = {**target(), 'direct_groundings': [{'quote': 'PRIVATE_RAW_SOURCE'}],
                    'generation_origin': {'raw_premise': 'PRIVATE_RAW_SOURCE'}}
        before = deepcopy(original)
        frozen = comparison(value=original)
        self.assertEqual(revision.check_target(frozen), target())
        self.assertEqual(frozen['schema_version'], revision.TARGET_SCHEMA)
        self.assertEqual(original, before)
        self.assertNotIn('direct_groundings', frozen['target'])
        self.assertNotIn('generation_origin', frozen['target'])
        frozen['target']['semantic_payload']['object'] = 'tampered target'
        self.reject(lambda: revision.check_target(frozen), 'knowledge_revision_target_changed')

    def test_wrong_logical_target_stale_expected_revision_and_unclassified_scope_fail(self):
        self.reject(lambda: revision.freeze_target(target(), operation='i2k', target_knode_id=uid(99), expected_revision_id=uid(2)))
        self.reject(lambda: revision.freeze_target(target(), operation='i2k', target_knode_id=uid(1), expected_revision_id=uid(99)))
        stale = target(); stale['current_revision_id'] = uid(99)
        self.reject(lambda: comparison(value=stale), 'knowledge_revision_target_changed')
        unclassified = target(); unclassified['identity_scope'] = None
        self.reject(lambda: comparison(value=unclassified))
        self.reject(lambda: comparison('w2k'))

    def test_binding_freezes_logical_fingerprint_but_recomputes_changed_content(self):
        proposal, frozen = candidate(), comparison()
        before = deepcopy((proposal, frozen))
        bound = revision.bind_candidate(proposal, frozen)
        self.assertNotEqual(proposal['identity_fingerprint'], target()['identity_fingerprint'])
        self.assertEqual(bound['identity_fingerprint'], target()['identity_fingerprint'])
        self.assertEqual(bound['content_fingerprint'], proposal['content_fingerprint'])
        self.assertEqual(bound['revision_target'], {'knode_id': uid(1), 'expected_revision_id': uid(2),
                                                   'target_sha256': frozen['target_sha256']})
        self.assertEqual(bound['evidence'], proposal['evidence'])
        self.assertEqual(revision.bind_candidate(bound, frozen), bound)
        self.assertEqual((proposal, frozen), before)

    def test_kind_source_identity_and_fingerprint_tampering_cannot_retarget_K(self):
        for key, value in (('kind', 'observation'), ('identity_scope', 'general'), ('source_data_id', 'b' * 64),
                           ('identity_fingerprint', 'f' * 64), ('content_fingerprint', 'f' * 64)):
            proposal = candidate(); proposal[key] = value
            with self.subTest(key=key): self.reject(lambda: revision.bind_candidate(proposal, comparison()))
        bound = revision.bind_candidate(candidate(), comparison())
        bound['revision_target']['expected_revision_id'] = uid(99)
        self.reject(lambda: revision.bind_candidate(bound, comparison()), 'knowledge_revision_target_changed')
        for field in ('knode_id', 'knode_revision_id', 'origin_record_id', 'supersedes_revision_id', 'generation_origin'):
            proposal = candidate(); proposal[field] = uid(99)
            self.reject(lambda: revision.bind_candidate(proposal, comparison()))

    def test_source_operations_keep_real_evidence_types_and_cannot_claim_inference(self):
        for operation in ('i2k', 'd2k'):
            original = candidate(operation)
            self.assertEqual(revision.bind_candidate(original, comparison(operation))['is_inferred'], False)
            for mutation in ('inferred', 'basis', 'empty', 'other_evidence', 'premises'):
                value = deepcopy(original)
                if mutation == 'inferred': value['is_inferred'] = True
                elif mutation == 'basis': value['claim_basis'] = 'new_inference'
                elif mutation == 'empty': value['evidence' if operation == 'i2k' else 'direct_evidence'] = []
                elif mutation == 'other_evidence': value['direct_evidence' if operation == 'i2k' else 'evidence'] = []
                else: value['premise_revision_ids'] = [uid(20), uid(21)]
                with self.subTest(operation=operation, mutation=mutation):
                    self.reject(lambda: revision.bind_candidate(value, comparison(operation)), 'knowledge_revision_source_boundary')

    def test_K2K_requires_distinct_premises_and_cannot_use_its_own_comparison_base(self):
        original = candidate('k2k')
        revision.bind_candidate(original, comparison('k2k'))
        for mutation in ('self_base', 'duplicate', 'one', 'direct_I', 'direct_D', 'false_origin'):
            value = deepcopy(original)
            if mutation == 'self_base': value['premise_revision_ids'] = [uid(2), uid(20)]
            elif mutation == 'duplicate': value['premise_revision_ids'] = [uid(20), uid(20)]
            elif mutation == 'one': value['premise_revision_ids'] = [uid(20)]
            elif mutation == 'direct_I': value['evidence'] = []
            elif mutation == 'direct_D': value['direct_evidence'] = []
            else: value['is_inferred'] = False
            with self.subTest(mutation=mutation):
                self.reject(lambda: revision.bind_candidate(value, comparison('k2k')), 'knowledge_revision_premise_boundary')

    def test_independent_material_true_sets_actual_new_operation_origin_only(self):
        for operation in ('i2k', 'd2k', 'k2k'):
            proposal, frozen = candidate(operation), comparison(operation)
            result = revision.resolve(proposal, frozen, review(True))
            self.assertEqual(result['action'], 'accepted_revision')
            self.assertEqual(result['identity_fingerprint'], target()['identity_fingerprint'])
            self.assertEqual(result['result_content_fingerprint'], proposal['content_fingerprint'])
            self.assertEqual(result['origin'], {'mode': 'new_record', 'origin_operation': operation, 'is_inferred': operation == 'k2k'})
            self.assertNotIn('new_revision_id', result)
            self.assertEqual(result['reason_codes'], [])

    def test_non_material_reuses_exact_existing_revision_even_when_payload_or_wording_differs(self):
        for operation in ('i2k', 'd2k', 'k2k'):
            proposed = candidate(operation, object_value='Equivalent structured presentation chosen by independent review')
            result = revision.resolve(proposed, comparison(operation), review(False))
            self.assertEqual(result['action'], 'reused')
            self.assertEqual(result['revision_target']['expected_revision_id'], uid(2))
            self.assertEqual(result['result_content_fingerprint'], target()['content_fingerprint'])
            self.assertNotEqual(result['candidate_content_fingerprint'], result['result_content_fingerprint'])
            self.assertEqual(result['origin'], {'mode': 'preserve_existing', 'origin_record_id': uid(3)})
            self.assertNotIn('is_inferred', result['origin'])  # Never relabel the old origin from the current operation.

    def test_material_true_for_same_canonical_content_is_held_instead_of_new_revision(self):
        proposed = candidate(object_value=target()['semantic_payload']['object'])
        proposed['statement'] = 'A display-only paraphrase.'
        result = revision.resolve(proposed, comparison(), review(True))
        self.assertEqual(result['action'], 'needs_human')
        self.assertEqual(result['reason_codes'], ['knowledge_revision_materiality_conflict'])
        self.assertEqual(result['origin'], {'mode': 'no_publication'})
        self.assertIsNone(result['result_content_fingerprint'])
        self.assertTrue(result['review']['material_change'])

    def test_uncertain_materiality_identity_or_grounding_cannot_publish_or_reuse(self):
        for field, value in (('material_change', None), ('same_identity', False), ('grounding_valid', False)):
            verdict = review(); verdict[field] = value
            result = revision.resolve(candidate(), comparison(), verdict)
            self.assertEqual(result['action'], 'needs_human')
            self.assertEqual(result['origin']['mode'], 'no_publication')
            self.assertEqual(result['review'][field], value)

    def test_review_is_exact_target_bound_typed_and_closed(self):
        for change in ({'comparison_base_revision_id': uid(99)}, {'same_identity': 1}, {'material_change': 0},
                       {'grounding_valid': None}, {'user_authorized': True}, {'reason_codes': []}):
            self.reject(lambda: revision.resolve(candidate(), comparison(), {**review(), **change}))
        schema = revision.review_schema(comparison())
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(set(schema['required']), set(schema['properties']))
        self.assertEqual(schema['properties']['comparison_base_revision_id']['enum'], [uid(2)])
        self.assertEqual(schema['properties']['material_change']['type'], ['boolean', 'null'])

    def test_pure_resolution_never_reads_sources_allocates_ids_or_mutates_inputs(self):
        proposal, frozen, verdict = candidate('d2k'), comparison('d2k'), review()
        before = deepcopy((proposal, frozen, verdict))
        with patch('builtins.open', side_effect=AssertionError('No source access')), \
                patch('urllib.request.urlopen', side_effect=AssertionError('No source fetch')), \
                patch('subprocess.Popen', side_effect=AssertionError('No model or parser')):
            result = revision.resolve(proposal, frozen, verdict)
        self.assertEqual(result['action'], 'accepted_revision')
        self.assertEqual((proposal, frozen, verdict), before)


if __name__ == '__main__':
    unittest.main()
