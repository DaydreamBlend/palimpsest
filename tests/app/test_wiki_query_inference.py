"""Accepted inference reuse contracts; synthetic evidence, no model/DB calls."""

from copy import deepcopy
import json
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.paper_wiki import escape_text
from palimpsest.wiki_query import (ANSWER_SCHEMA, ANSWER_WITH_INFERENCE_SCHEMA,
    INFERENCE_CLAIM_CHECKS, OVERALL_CHECKS, generation_schema, generation_prompt,
    normalize_answer, validation_schema, validation_prompt, validate_answer, render_answer)
from test_wiki_query import context, proposal, uid


def inference_context():
    result = context()
    result['inference_citations_supported'] = True
    result['source_version_snapshot'] = {'versions': [], 'heads': {}}
    records, groundings, nodes = [], [], []
    for ordinal, unit in enumerate(result['information'], 1):
        revision, record = uid(100 + ordinal), uid(1000 + ordinal)
        grounding = {'grounding_id': uid(2000 + ordinal), 'node_revision_id': revision,
            'information_id': unit['information_id'], 'data_id': unit['data_id'],
            'source_execution_id': unit['source_execution_id'], 'char_start': 0,
            'char_end': len(unit['content']), 'quote': unit['content'], 'media_sha256': None}
        detail = {'record_id': record, 'knode_revision_id': revision, 'operation': 'i2k',
            'premise_revision_ids': [], 'information_ids': [unit['information_id']], 'data_versions': []}
        source = {'knode_id': uid(200 + ordinal), 'knode_revision_id': revision,
            'current_revision_id': revision, 'origin_record_id': record, 'statement': unit['content'],
            'record_disposition': 'accepted_new', 'current_applicability': 'current_premises',
            'source_version_status': 'untracked', 'data_version_supports': [],
            'identity_scope': 'general', 'retrieval_basis': 'source_content',
            'generation_origin': {'origin_operation': 'i2k', 'is_inferred': False, 'origin_record_id': record},
            'groundings': [grounding], 'transitive_source_refs': [],
            'retrieval_support': {'record_id': record, 'operation': 'i2k',
                'premise_revision_ids': [], 'information_ids': [unit['information_id']],
                'source_data_ids': [unit['data_id']], 'records': [detail]}}
        records.append(detail)
        groundings.append(grounding)
        nodes.append(source)
    revision, record = uid(103), uid(1003)
    premises = [node['knode_revision_id'] for node in nodes]
    derivation = {'record_id': record, 'result_node_revision_id': revision,
        'premise_revision_ids': premises, 'inference_type': 'deductive',
        'assumptions': ['동일한 입력 조건을 가정한다.'], 'limitations': ['실제 배포 여부는 검증하지 않았다.'],
        'derivation_basis': 'Synthetic fixture inference; no semantic evaluation.',
        'validation': {'verdict': 'accepted', 'inference_valid': True, 'premises_sufficient': True,
                       'limits_preserved': True, 'novel_conclusion': True},
        'current_applicability': 'current_premises'}
    detail = {'record_id': record, 'knode_revision_id': revision, 'operation': 'k2k',
        'premise_revision_ids': premises, 'information_ids': [], 'data_versions': [], 'derivation': derivation}
    inferred = {'knode_id': uid(203), 'knode_revision_id': revision, 'current_revision_id': revision,
        'origin_record_id': record, 'statement': '동일 입력 조건에서 이 결론을 도출했다. 배포 여부는 확인하지 않았다.',
        'record_disposition': 'accepted_new', 'current_applicability': 'current_premises',
        'source_version_status': 'untracked', 'data_version_supports': [], 'identity_scope': 'general',
        'retrieval_basis': 'system_inference', 'groundings': [], 'transitive_source_refs': groundings,
        'derivations': [derivation], 'generation_origin': {'origin_operation': 'k2k', 'is_inferred': True,
            'origin_record_id': record, **{key: deepcopy(derivation[key]) for key in
                ('inference_type', 'premise_revision_ids', 'assumptions', 'limitations', 'derivation_basis', 'validation')}},
        'retrieval_support': {'record_id': record, 'operation': 'k2k', 'premise_revision_ids': premises,
            'information_ids': sorted(unit['information_id'] for unit in result['information']),
            'source_data_ids': [result['sources'][0]['data_id']], 'records': records + [detail]}}
    result['knowledge'] = nodes + [inferred]
    return result


def inferred_proposal():
    response = proposal()
    response['claims'][0].update(text=inference_context()['knowledge'][-1]['statement'], evidence=[],
        knowledge_evidence=[{'node_revision_id': uid(103)}])
    return response


def decision(answer):
    return {'verdict': 'accepted', 'claims': [{'claim_key': claim['claim_key'],
        **{key: True for key in INFERENCE_CLAIM_CHECKS}, 'reason': 'Synthetic faithful-reuse review.'}
        for claim in answer['claims']], **{key: True for key in OVERALL_CHECKS},
        'reason': 'Synthetic review; no model was run.'}


class WikiQueryInferenceTests(unittest.TestCase):
    def rejects(self, action, code=None):
        with self.assertRaises(PalimpsestError) as caught:
            action()
        if code:
            self.assertEqual(caught.exception.code, code)

    def test_new_schema_exposes_only_eligible_inferred_revisions_and_legacy_schema_is_unchanged(self):
        ctx = inference_context()
        claim = generation_schema(ctx)['properties']['claims']['items']
        self.assertEqual(claim['properties']['knowledge_evidence']['items']['properties']['node_revision_id']['enum'],
                         [uid(103)])
        self.assertIn('knowledge_evidence', claim['required'])
        old = context()
        old_schema = generation_schema(old)
        self.assertNotIn('knowledge_evidence', old_schema['properties']['claims']['items']['properties'])
        self.assertEqual(generation_schema({**old, 'inference_citations_supported': False}), old_schema)
        answer = normalize_answer(proposal(), old)
        self.assertEqual(answer['schema_version'], ANSWER_SCHEMA)
        self.assertEqual(set(answer['claims'][0]), {'claim_key', 'text', 'evidence', 'source_evidence'})
        self.rejects(lambda: normalize_answer(inferred_proposal(), old))
        ctx['knowledge'] = []
        self.assertEqual(generation_schema(ctx)['properties']['claims']['items']['properties']['knowledge_evidence']['maxItems'], 0)
        self.assertNotIn('"enum": []', json.dumps(generation_schema(ctx)))

    def test_exact_accepted_inference_retains_origin_support_and_premises_without_fabricated_source_citation(self):
        ctx, response = inference_context(), inferred_proposal()
        before = deepcopy((ctx, response))
        answer = normalize_answer(response, ctx)
        self.assertEqual(answer['schema_version'], ANSWER_WITH_INFERENCE_SCHEMA)
        self.assertEqual(answer['context_sha256'], digest(ctx))
        claim = answer['claims'][0]
        self.assertEqual(claim['epistemic_basis'], 'accepted_system_inference')
        self.assertEqual(claim['evidence'], [])
        self.assertEqual(claim['source_evidence'], [])
        citation = claim['knowledge_evidence'][0]
        self.assertEqual(citation['node_revision_id'], uid(103))
        self.assertEqual(citation['statement'], ctx['knowledge'][-1]['statement'])
        self.assertEqual(citation['generation_origin'], ctx['knowledge'][-1]['generation_origin'])
        self.assertEqual({p['node_revision_id'] for p in citation['premise_revisions']}, {uid(101), uid(102)})
        self.assertEqual(citation['direct_groundings'], [])
        self.assertEqual({g['node_revision_id'] for g in citation['transitive_source_refs']}, {uid(101), uid(102)})
        citation['generation_origin']['limitations'].append('Do not mutate original.')
        self.assertEqual((ctx, response), before)

    def test_unknown_source_created_duplicate_and_model_declared_inference_refs_are_rejected(self):
        for references in ([{'node_revision_id': uid(999)}], [{'node_revision_id': uid(101)}],
                           [{'node_revision_id': uid(103)}] * 2,
                           [{'node_revision_id': uid(103), 'is_inferred': True}], []):
            response = inferred_proposal()
            response['claims'][0]['knowledge_evidence'] = references
            with self.subTest(references=references):
                self.rejects(lambda: normalize_answer(response, inference_context()))
        forged = context()
        forged['inference_citations_supported'] = True
        forged['knowledge'] = [{'knode_revision_id': uid(103), 'is_inferred': True, 'accepted': True}]
        self.assertEqual(generation_schema(forged)['properties']['claims']['items']['properties']['knowledge_evidence']['maxItems'], 0)

    def test_missing_exact_premise_or_actual_source_coverage_invalidates_inference_context(self):
        for mutation in ('missing_premise', 'missing_information', 'stale', 'review_required',
                         'historical', 'source_execution', 'quote', 'partial_information',
                         'foreign_source_scope', 'mismatched_route_ref', 'transitive_relabel'):
            ctx = inference_context()
            node = ctx['knowledge'][0]
            if mutation == 'missing_premise':
                ctx['knowledge'].pop(0)
            elif mutation == 'missing_information':
                ctx['information'].pop(0)
            elif mutation == 'stale':
                node['current_applicability'] = 'needs_revalidation'
            elif mutation == 'review_required':
                node['record_disposition'] = 'needs_human'
            elif mutation == 'historical':
                node['source_version_status'] = 'historical'
            elif mutation == 'source_execution':
                node['groundings'][0]['source_execution_id'] = uid(900)
            elif mutation == 'quote':
                node['groundings'][0]['quote'] = 'Forged source quote'
            elif mutation == 'partial_information':
                ctx['knowledge'][-1]['retrieval_support']['information_ids'].pop()
            elif mutation == 'foreign_source_scope':
                node.update(identity_scope='source', source_data_id='9' * 64)
            elif mutation == 'mismatched_route_ref':
                node['retrieval_support']['record_id'] = uid(900)
            else:
                ctx['knowledge'][-1]['transitive_source_refs'][0]['node_revision_id'] = uid(103)
            with self.subTest(mutation=mutation):
                self.rejects(lambda: generation_schema(ctx), 'invalid_wiki_query_inference_context')

    def test_origin_must_match_actual_validated_derivation_not_just_inferred_boolean(self):
        for mutation in ('wrong_record', 'wrong_inference_type', 'changed_limits', 'unsupported_derivation',
                         'missing_derivation', 'source_operation', 'wrong_result', 'not_current'):
            ctx = inference_context()
            node = ctx['knowledge'][-1]
            if mutation == 'wrong_record':
                node['generation_origin']['origin_record_id'] = uid(900)
            elif mutation == 'wrong_inference_type':
                node['generation_origin']['inference_type'] = 'inductive'
            elif mutation == 'changed_limits':
                node['generation_origin']['limitations'] = []
            elif mutation == 'unsupported_derivation':
                node['derivations'][0]['validation']['premises_sufficient'] = False
            elif mutation == 'missing_derivation':
                node['derivations'] = []
            elif mutation == 'source_operation':
                node['generation_origin']['origin_operation'] = 'i2k'
            elif mutation == 'wrong_result':
                node['derivations'][0]['result_node_revision_id'] = uid(900)
            else:
                node['current_revision_id'] = uid(900)
            with self.subTest(mutation=mutation):
                self.rejects(lambda: generation_schema(ctx), 'invalid_wiki_query_inference_context')

    def test_source_only_and_mixed_v2_claims_keep_explicit_distinct_bases(self):
        ctx = inference_context()
        source = proposal()
        source['claims'][0]['knowledge_evidence'] = []
        answer = normalize_answer(source, ctx)
        self.assertEqual(answer['claims'][0]['epistemic_basis'], 'direct_source')
        self.assertEqual(answer['claims'][0]['knowledge_evidence'], [])
        source['claims'][0]['knowledge_evidence'] = [{'node_revision_id': uid(103)}]
        mixed = normalize_answer(source, ctx)
        self.assertEqual(mixed['claims'][0]['epistemic_basis'], 'mixed_source_and_accepted_inference')
        self.assertEqual(len(mixed['claims'][0]['evidence']), 1)
        self.assertEqual(len(mixed['claims'][0]['knowledge_evidence']), 1)
        # Structured validation permits explicit mixed evidence; independent
        # semantic validation still decides whether the actual wording is valid.
        self.assertIn('[원문 + K2K 추론]', render_answer(mixed, validate_answer(decision(mixed), mixed)))

    def test_new_independent_validator_checks_are_required_boolean_and_gate_acceptance(self):
        answer = normalize_answer(inferred_proposal(), inference_context())
        schema = validation_schema(answer)['properties']['claims']['items']
        for key in ('accepted_inference_faithful', 'inference_limits_preserved'):
            self.assertIn(key, schema['required'])
            response = decision(answer)
            response['claims'][0][key] = False
            self.rejects(lambda: validate_answer(response, answer), 'wiki_query_unverified_acceptance')
            response['verdict'] = 'needs_review'
            validation = validate_answer(response, answer)
            self.assertNotIn(answer['claims'][0]['text'], render_answer(answer, validation))
            del response['claims'][0][key]
            self.rejects(lambda: validate_answer(response, answer))
            response = decision(answer)
            response['claims'][0][key] = 1
            self.rejects(lambda: validate_answer(response, answer))

    def test_normalized_knowledge_citation_and_context_are_hash_bound_and_reverified(self):
        ctx = inference_context()
        answer = normalize_answer(inferred_proposal(), ctx)
        checked = validate_answer(decision(answer), answer)
        self.assertEqual(checked['answer_sha256'], digest(answer))
        for field in ('statement', 'generation_origin', 'retrieval_support', 'transitive_source_refs', 'premise_revisions'):
            changed = deepcopy(answer)
            citation = changed['claims'][0]['knowledge_evidence'][0]
            citation[field] = 'Tampered' if field == 'statement' else {} if field in ('generation_origin', 'retrieval_support') else []
            with self.subTest(field=field):
                self.rejects(lambda: validation_prompt(ctx, changed))
                self.rejects(lambda: render_answer(changed, checked), 'wiki_query_answer_changed')
        changed = deepcopy(ctx)
        del changed['inference_citations_supported']
        self.rejects(lambda: validation_prompt(changed, answer), 'wiki_query_context_changed')
        answer['claims'][0]['epistemic_basis'] = 'direct_source'
        self.rejects(lambda: validation_schema(answer))

    def test_prompts_and_rendering_label_reused_system_inference_with_exact_refs_and_limits(self):
        ctx = inference_context()
        answer = normalize_answer(inferred_proposal(), ctx)
        generation = generation_prompt(ctx)
        validation = validation_prompt(ctx, answer)
        for text in ('never as an explicit statement by the source author', 'Do not combine existing K into a new conclusion',
                     'NOT fabricated direct source citations', 'accepted_inference_faithful', 'inference_limits_preserved'):
            self.assertIn(text, generation)
            self.assertIn(text, validation)
        self.assertNotIn('Knowledge nodes are navigation/context only', generation)
        self.assertIn('independent Validator', validation)
        rendered = render_answer(answer, validate_answer(decision(answer), answer))
        for text in ('[K2K 추론]', '시스템의 승인된 K2K 추론', uid(103), uid(1003), uid(101), uid(102),
                     '가정:', '한계:', '전제의 원문 계보:', escape_text('실제 배포 여부는 검증하지 않았다.')):
            self.assertIn(text, rendered)

    def test_current_version_context_must_match_frozen_heads(self):
        ctx = inference_context()
        node = ctx['knowledge'][0]
        version = {'version_id': uid(501), 'series_id': uid(500), 'data_id': ctx['sources'][0]['data_id']}
        record = node['retrieval_support']['records'][0]
        record['data_versions'] = [version]
        node['data_version_supports'] = [{'record_id': record['record_id'], 'versions': [version]}]
        node['source_version_status'] = 'current'
        ctx['source_version_snapshot']['heads'] = {uid(500): uid(501)}
        generation_schema(ctx)
        ctx['source_version_snapshot']['heads'][uid(500)] = uid(502)
        self.rejects(lambda: generation_schema(ctx), 'invalid_wiki_query_inference_context')

    def test_later_actual_source_support_does_not_erase_inferred_origin_or_require_undelivered_old_premises(self):
        ctx = inference_context()
        inferred = ctx['knowledge'][-1]
        original = deepcopy(inferred['generation_origin'])
        inferred['groundings'] = [{**deepcopy(grounding), 'node_revision_id': uid(103),
            'grounding_id': uid(2200 + ordinal)} for ordinal, grounding in enumerate(inferred['transitive_source_refs'])]
        inferred['transitive_source_refs'] = []
        support = {'record_id': uid(1203), 'knode_revision_id': uid(103), 'operation': 'i2k',
            'premise_revision_ids': [], 'information_ids': [uid(1), uid(2)], 'data_versions': []}
        inferred['retrieval_support'].update(record_id=uid(1203), operation='i2k',
            premise_revision_ids=[], records=[support])
        ctx['knowledge'] = [inferred]
        answer = normalize_answer(inferred_proposal(), ctx)
        citation = answer['claims'][0]['knowledge_evidence'][0]
        self.assertEqual(citation['generation_origin'], original)
        self.assertEqual(citation['retrieval_support']['record_id'], uid(1203))
        self.assertEqual(citation['premise_revisions'], [])
        self.assertEqual(len(citation['direct_groundings']), 2)
        self.assertEqual(answer['claims'][0]['evidence'], [])
        self.assertEqual(answer['claims'][0]['epistemic_basis'], 'accepted_system_inference')

    def test_malformed_support_metadata_has_structured_errors(self):
        for mutation in ('snapshot', 'support', 'origin', 'groundings', 'versions',
                         'information_ids', 'summary_ids', 'transitive_duplicate'):
            ctx = inference_context()
            if mutation == 'snapshot':
                ctx['source_version_snapshot'] = None
            elif mutation == 'support':
                ctx['knowledge'][0]['retrieval_support'] = None
            elif mutation == 'origin':
                ctx['knowledge'][-1]['generation_origin'] = None
            elif mutation == 'groundings':
                ctx['knowledge'][0]['groundings'] = [None]
            elif mutation == 'versions':
                ctx['knowledge'][0]['data_version_supports'] = [{'record_id': uid(1001)}]
            elif mutation == 'information_ids':
                ctx['knowledge'][-1]['retrieval_support']['records'][0]['information_ids'] = [{}]
            elif mutation == 'summary_ids':
                ctx['knowledge'][-1]['retrieval_support']['information_ids'] = [{}]
            else:
                ctx['knowledge'][-1]['transitive_source_refs'] *= 2
            with self.subTest(mutation=mutation):
                self.rejects(lambda: generation_schema(ctx), 'invalid_wiki_query_inference_context')

    def test_reciprocal_support_refs_cannot_make_a_cycle_valid_by_adding_a_source_leaf(self):
        ctx = inference_context()
        source, circular, inferred = ctx['knowledge']
        old = inferred['derivations'][0]
        derivation = {**deepcopy(old), 'record_id': uid(1102), 'result_node_revision_id': uid(102),
                      'premise_revision_ids': [uid(103), uid(101)]}
        circular['derivations'] = [derivation]
        extra = {'record_id': uid(1102), 'knode_revision_id': uid(102), 'operation': 'k2k',
            'premise_revision_ids': [uid(103), uid(101)], 'information_ids': [], 'data_versions': [],
            'derivation': derivation}
        route = [source['retrieval_support']['records'][0], extra, inferred['retrieval_support']['records'][-1]]
        circular['retrieval_support'] = {'record_id': uid(1102), 'operation': 'k2k',
            'premise_revision_ids': [uid(103), uid(101)], 'information_ids': [uid(1)],
            'source_data_ids': [ctx['sources'][0]['data_id']], 'records': route}
        inferred['retrieval_support']['records'] = route
        inferred['retrieval_support']['information_ids'] = [uid(1)]
        inferred['transitive_source_refs'] = source['groundings']
        self.rejects(lambda: generation_schema(ctx), 'invalid_wiki_query_inference_context')


if __name__ == '__main__':
    unittest.main()
