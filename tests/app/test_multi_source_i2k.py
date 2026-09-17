"""Pure multi-source identity/citation/explicitness contracts, no LLM or DB."""

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.i2k_selection import selection_fingerprints
from palimpsest.multi_source_i2k import (combine_packets, check_input, generation_schema, validation_schema,
    normalize_proposals, normalize_source_requests, validate_decisions, check_scope_reuse)
from palimpsest.multi_source_prompts import generation, validation, source_input


def uid(number):
    return f'019947e2-1234-7000-8000-{number:012x}'


def packet(number):
    owner = str(number) * 64
    image = sha256(b'identical shared image bytes').hexdigest()
    text = ('Alpha is an ordered sequence. Study A reports a readout of 3 μm. Cafe\u0301.' if number == 1 else
            'Element positions are meaningful. This document explicitly reports Study A readout of 3 μm.')
    unit = {'information_id': uid(number), 'origin_record_id': uid(10 + number), 'role': 'target',
        'kind': 'text', 'unit_type': 'text', 'title': f'Document {number}', 'content': text,
        'identity_fingerprint': sha256(f'identity{number}'.encode()).hexdigest(),
        'content_fingerprint': sha256(text.encode()).hexdigest(),
        'source_refs': [{'block_id': '/page0/body', 'page_index': 0, 'bbox': [0, 0, 300, 200],
                        'raw_locator': '/pdf_info/0/preproc_blocks/0', 'anchor_sha256': sha256(text.encode()).hexdigest()}],
        'media': [{'sha256': image, 'byte_size': 28, 'page_index': 0, 'source_block_id': '/page0/body'}]}
    unit['source_assembly'] = {'algorithm': 'source-groups-v1', 'content_segments': [
        {'source_block_id': '/page0/body', 'page_index': 0, 'char_start': 0, 'char_end': len(text),
         'source_char_range': [0, len(text)], 'text_origin': 'parser_source',
         'raw_locator': '/pdf_info/0/preproc_blocks/0', 'anchor_sha256': sha256(text.encode()).hexdigest()}]}
    result = {'schema_version': 'i2k-input-v1', 'data_id': owner, 'source_execution_id': uid(20 + number),
        'profile_id': uid(30 + number), 'page_count': 2, 'target_information_ids': [uid(number)],
        'context_information_ids': [], 'excluded_information_ids': [],
        'model_input': {'data_id': owner, 'information': [unit], 'quality_evidence': {'status': 'not_supplied'}},
        'media_assets': [{'sha256': image, 'byte_size': 28, 'artifact_path': f'derived/objects/sha256/{image[:2]}/{image}'}]}
    result['input_sha256'] = digest(result)
    return result


def proposal(bundle, *, source=False):
    units = bundle['model_input']['information']
    quotes = ([units[0]['content'].split('. ')[1] + '.', units[1]['content'].split('. ')[1]] if source else
              [units[0]['content'].split('. ')[0] + '.', units[1]['content'].split('. ')[0] + '.'])
    node = {'candidate_key': 'claim', 'kind': 'observation' if source else 'proposition',
        'statement': 'The explicit source statement.', 'semantic_payload': {'subject': 'Study A' if source else 'Alpha',
            'relation': 'reported' if source else 'is', 'object': '3 μm' if source else 'an ordered sequence with meaningful positions',
            'polarity': 'positive', 'quantifier': 'reported statement', 'scope': 'Study A' if source else '',
            'conditions': [], 'time_range': ''},
        'evidence': [{'information_id': unit['information_id'], 'quote': quote, 'media_sha256': None,
                      'source_role': 'results' if source else 'other'} for unit, quote in zip(units, quotes)],
        'uncertainties': [], 'identity_scope': 'source' if source else 'general',
        'source_data_id': units[0]['data_id'] if source else None,
        'selection_reason': 'Explicit content useful for the knowledge wiki.',
        'claim_basis': 'explicit_source_content', 'is_inferred': False}
    return {'nodes': [node], 'source_requests': [], 'complete': True, 'coverage_notes': [],
        'reviews': [{'information_id': unit['information_id'], 'disposition': 'selected', 'candidate_keys': ['claim'],
                     'reason': 'Explicitly supports a material part of the claim.'} for unit in units]}


def decisions(bundle):
    return {'complete': True, 'decisions': [{'candidate_key': 'claim', 'verdict': 'accepted',
        'equivalent_candidate_key': None, 'equivalent_revision_id': None, 'reason_codes': ['source_supported'],
        'reason': 'Every material element is directly stated without a new inference.',
        'scope_correct': True, 'importance_justified': True, 'source_explicit': True,
        'no_novel_inference': True, 'source_identity_preserved': True}],
        'reviews': [{'information_id': identifier, 'verdict': 'confirmed', 'reason_codes': ['reviewed'],
                     'reason': 'Source reviewed.'} for identifier in bundle['target_information_ids']]}


class MultiSourceTests(unittest.TestCase):
    def setUp(self):
        self.packets = [packet(1), packet(2)]
        self.bundle = combine_packets(self.packets)

    def error(self, code, call):
        with self.assertRaises(PalimpsestError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_complete_sources_keep_identity_order_provenance_and_deduplicate_only_media(self):
        before = deepcopy(self.packets)
        self.assertEqual(check_input(self.bundle), [uid(1), uid(2)])
        self.assertEqual(self.bundle['sources'], before)
        self.assertEqual(self.bundle['data_id_role'], 'operational_anchor_not_evidence_owner')
        self.assertEqual(len(self.bundle['media_assets']), 1)
        units = self.bundle['model_input']['information']
        self.assertEqual([unit['data_id'] for unit in units], ['1' * 64, '2' * 64])
        self.assertEqual([unit['source_execution_id'] for unit in units], [uid(21), uid(22)])
        self.assertEqual(units[0]['source_refs'], before[0]['model_input']['information'][0]['source_refs'])
        self.assertEqual(self.packets, before)

    def test_tampering_duplicate_data_shared_i_and_subset_are_rejected(self):
        changed = deepcopy(self.bundle)
        changed['model_input']['information'][0]['data_id'] = '2' * 64
        changed['input_sha256'] = digest({k: v for k, v in changed.items() if k != 'input_sha256'})
        self.error('multi_source_input_changed', lambda: check_input(changed))
        self.error('duplicate_multi_source_input', lambda: combine_packets([packet(1), packet(1)]))
        source = packet(2)
        source['model_input']['information'][0]['information_id'] = uid(1)
        source['target_information_ids'] = [uid(1)]
        source['input_sha256'] = digest({k: v for k, v in source.items() if k != 'input_sha256'})
        self.error('duplicate_multi_source_input', lambda: combine_packets([packet(1), source]))
        source = packet(1)
        source['excluded_information_ids'] = [uid(99)]
        self.error('selection_requires_all_information', lambda: combine_packets([source]))

    def test_general_material_elements_can_be_explicitly_supported_by_different_data(self):
        node = normalize_proposals(proposal(self.bundle), self.bundle)['nodes'][0]
        self.assertEqual({e['data_id'] for e in node['evidence']}, {'1' * 64, '2' * 64})
        self.assertIsNone(node['source_data_id'])
        self.assertEqual(node['identity_fingerprint'], selection_fingerprints('proposition', node['semantic_payload'], 'general')['identity_fingerprint'])
        for evidence in node['evidence']:
            unit = next(unit for unit in self.bundle['model_input']['information'] if unit['information_id'] == evidence['information_id'])
            self.assertEqual(unit['content'][evidence['char_start']:evidence['char_end']], evidence['quote'])

    def test_block_citations_resolve_same_named_block_within_each_actual_source(self):
        response = proposal(self.bundle)
        original = normalize_proposals(response, self.bundle)['nodes'][0]
        response['nodes'][0]['evidence'] = [{'information_id': identifier,
            'source_block_id': '/page0/body', 'source_role': 'other'} for identifier in self.bundle['target_information_ids']]
        before = deepcopy((self.bundle, response))
        result = normalize_proposals(response, self.bundle)['nodes'][0]
        self.assertEqual([e['quote'] for e in result['evidence']],
                         [unit['content'] for unit in self.bundle['model_input']['information']])
        self.assertEqual([e['data_id'] for e in result['evidence']], ['1' * 64, '2' * 64])
        self.assertEqual(result['content_fingerprint'], original['content_fingerprint'])
        self.assertEqual(before, (self.bundle, response))

    def test_separate_block_citations_do_not_join_sentences_across_caption(self):
        packet_a = packet(1)
        unit = packet_a['model_input']['information'][0]
        pieces = ['First sentence with $\\mathrm{\\mu m}$ and Cafe\u0301.',
                  'Figure 1. An intervening caption.', 'Last sentence reporting the explicit result.']
        unit['content'] = '\n\n'.join(pieces)
        unit['content_fingerprint'] = sha256(unit['content'].encode()).hexdigest()
        unit['source_refs'], unit['source_assembly']['content_segments'] = [], []
        start = 0
        for index, text in enumerate(pieces):
            block, anchor = f'/body/{index}', sha256(text.encode()).hexdigest()
            unit['source_refs'].append({'block_id': block, 'page_index': 0, 'raw_locator': block, 'anchor_sha256': anchor})
            unit['source_assembly']['content_segments'].append({'source_block_id': block, 'page_index': 0,
                'raw_locator': block, 'anchor_sha256': anchor, 'source_char_range': [0, len(text)],
                'char_start': start, 'char_end': start + len(text), 'text_origin': 'parser_source'})
            start += len(text) + 2
        packet_a['input_sha256'] = digest({key: value for key, value in packet_a.items() if key != 'input_sha256'})
        bundle = combine_packets([packet_a, packet(2)])
        response = proposal(bundle)
        response['nodes'][0]['evidence'] = [{'information_id': uid(1), 'source_block_id': f'/body/{index}',
            'source_role': 'results'} for index in (0, 2)] + [response['nodes'][0]['evidence'][1]]
        evidence = normalize_proposals(response, bundle)['nodes'][0]['evidence']
        self.assertEqual([item['quote'] for item in evidence[:2]], [pieces[0], pieces[2]])
        self.assertGreater(evidence[1]['char_start'], evidence[0]['char_end'])
        response['nodes'][0]['evidence'][0]['information_id'] = uid(2)
        self.error('invalid_knowledge_block_reference', lambda: normalize_proposals(response, bundle))

    def test_preview_preserves_full_text_and_missing_assembly_keeps_quote_option(self):
        packet_a = packet(1)
        unit = packet_a['model_input']['information'][0]
        unit['content'] = 'a' * 120 + 'Middle content must remain delivered.' + 'z' * 80
        unit['content_fingerprint'] = sha256(unit['content'].encode()).hexdigest()
        unit['source_refs'][0]['anchor_sha256'] = unit['content_fingerprint']
        unit['source_assembly']['content_segments'][0].update(char_end=len(unit['content']),
            source_char_range=[0, len(unit['content'])], anchor_sha256=unit['content_fingerprint'])
        packet_a['input_sha256'] = digest({key: value for key, value in packet_a.items() if key != 'input_sha256'})
        bundle = combine_packets([packet_a, packet(2)])
        projected = source_input(bundle, bundle['media_assets'])
        self.assertEqual(projected['information'][0]['content'], unit['content'])
        self.assertEqual(projected['information'][0]['media'], unit['media'])
        self.assertEqual(projected['information'][0]['text_blocks'][0], {'source_block_id': '/page0/body',
            'char_start': 0, 'char_end': len(unit['content']), 'preview': 'a' * 120 + ' … ' + 'z' * 80})
        packets = [packet(1), packet(2)]
        for source in packets:
            del source['model_input']['information'][0]['source_assembly']
            source['input_sha256'] = digest({key: value for key, value in source.items() if key != 'input_sha256'})
        old_bundle = combine_packets(packets)
        self.assertEqual(len(normalize_proposals(proposal(old_bundle), old_bundle)['nodes']), 1)
        self.assertEqual(source_input(old_bundle, [])['information'][0]['text_blocks'], [])
        items = generation_schema(old_bundle)['properties']['nodes']['items']['properties']['evidence']['items']
        self.assertNotIn('anyOf', items)
        self.assertIn('quote', items['required'])

    def test_source_owner_needs_own_evidence_but_other_data_may_explicitly_supplement(self):
        response = proposal(self.bundle, source=True)
        node = normalize_proposals(response, self.bundle)['nodes'][0]
        self.assertEqual(node['source_data_id'], '1' * 64)
        self.assertEqual(len({e['data_id'] for e in node['evidence']}), 2)
        response['nodes'][0]['evidence'].pop(0)
        response['reviews'][0].update(disposition='context_only', candidate_keys=[])
        self.error('source_owner_evidence_required', lambda: normalize_proposals(response, self.bundle))

    def test_inferred_generation_and_unverified_validator_acceptance_are_forbidden(self):
        response = proposal(self.bundle)
        response['nodes'][0]['is_inferred'] = True
        self.error('i2k_novel_inference_forbidden', lambda: normalize_proposals(response, self.bundle))
        candidates = normalize_proposals(proposal(self.bundle), self.bundle)['nodes']
        for field in ('source_explicit', 'no_novel_inference', 'source_identity_preserved'):
            value = decisions(self.bundle)
            value['decisions'][0][field] = False
            self.error('i2k_explicit_source_acceptance_required', lambda: validate_decisions(value, candidates, [], self.bundle))
            value['decisions'][0]['verdict'] = 'needs_human'
            value['complete'] = False
            checked = validate_decisions(value, candidates, [], self.bundle)
            self.assertIs(checked['complete'], False)
            self.assertIs(checked['decisions']['claim'][field], False)

    def test_both_models_must_review_all_i_and_link_completion_never_changes_importance(self):
        response = proposal(self.bundle)
        response['reviews'][1]['candidate_keys'] = []
        normalized = normalize_proposals(response, self.bundle)
        self.assertEqual(normalized['link_completions'][0]['data_id'], '2' * 64)
        response['reviews'][1]['disposition'] = 'not_selected'
        self.error('selection_review_evidence_mismatch', lambda: normalize_proposals(response, self.bundle))
        value = decisions(self.bundle)
        value['reviews'].pop()
        self.error('selection_review_coverage_mismatch', lambda: validate_decisions(value, normalized['nodes'], [], self.bundle))

    def test_pdf_requests_bind_to_one_actual_source_and_its_page_count(self):
        request = {'data_id': '1' * 64, 'information_ids': [uid(1)], 'page_numbers': [2], 'question': 'Check the original symbol.'}
        self.assertEqual(normalize_source_requests([request], self.bundle), [request])
        request['information_ids'] = [uid(2)]
        self.error('invalid_multi_source_request', lambda: normalize_source_requests([request], self.bundle))
        request['information_ids'], request['page_numbers'] = [uid(1)], [3]
        self.error('invalid_multi_source_request', lambda: normalize_source_requests([request], self.bundle))

    def test_unicode_and_media_only_evidence_use_the_actual_information_owner(self):
        response = proposal(self.bundle)
        evidence = response['nodes'][0]['evidence'][0]
        evidence['quote'] = 'Cafe\u0301.'
        self.assertEqual(normalize_proposals(response, self.bundle)['nodes'][0]['evidence'][0]['quote'], 'Cafe\u0301.')
        evidence['quote'] = 'Café.'
        self.error('knowledge_quote_mismatch', lambda: normalize_proposals(response, self.bundle))
        evidence.update(quote='', media_sha256=self.bundle['media_assets'][0]['sha256'])
        result = normalize_proposals(response, self.bundle)['nodes'][0]['evidence'][0]
        self.assertEqual((result['char_start'], result['char_end'], result['data_id']), (0, 0, '1' * 64))
        evidence['media_sha256'] = 'f' * 64
        self.error('invalid_knowledge_evidence', lambda: normalize_proposals(response, self.bundle))

    def test_scope_reuse_preserves_owner_even_when_external_evidence_exists(self):
        source = normalize_proposals(proposal(self.bundle, source=True), self.bundle)['nodes'][0]
        existing = {'kind': 'observation', 'identity_scope': 'source', 'source_data_id': '1' * 64}
        self.assertTrue(check_scope_reuse(source, existing))
        existing['source_data_id'] = '2' * 64
        self.error('knowledge_scope_reuse_conflict', lambda: check_scope_reuse(source, existing))

    def test_schemas_are_closed_and_prompt_contains_every_data_i_and_explicitness_policy(self):
        def check(schema):
            for branch in schema.get('anyOf', []):
                check(branch)
            if schema.get('type') == 'object':
                self.assertIs(schema['additionalProperties'], False)
                self.assertEqual(set(schema['required']), set(schema['properties']))
                for child in schema['properties'].values():
                    check(child)
            if schema.get('type') == 'array':
                check(schema['items'])
        check(generation_schema(self.bundle))
        branches = generation_schema(self.bundle)['properties']['nodes']['items']['properties']['evidence']['items']['anyOf']
        self.assertEqual(len(branches), 2)
        self.assertEqual(set(branches[0]['required']), {'information_id', 'quote', 'media_sha256', 'source_role'})
        self.assertEqual(set(branches[1]['required']), {'information_id', 'source_block_id', 'source_role'})
        self.assertEqual(branches[1]['properties']['source_block_id']['enum'], ['/page0/body'])
        schema = validation_schema(['claim'], [uid(70)], self.bundle)
        check(schema)
        for branch in schema['properties']['decisions']['items']['anyOf']:
            self.assertIn('source_identity_preserved', branch['required'])
        snapshot = {'input': self.bundle, 'existing_nodes': [], 'existing_edges': []}
        context = {'input_snapshot': snapshot, 'candidates': [], 'validation_context_sha': 'c' * 64}
        for prompt in (generation(snapshot, self.bundle['media_assets']), validation(context, self.bundle['media_assets'])):
            for unit in self.bundle['model_input']['information']:
                self.assertIn(unit['information_id'], prompt)
                self.assertIn(unit['data_id'], prompt)
                self.assertIn(unit['content'], prompt)
            self.assertIn('each Data need NOT independently repeat the entire claim', prompt)
            self.assertIn('Do not translate Korean source prose into English', prompt)
            self.assertIn('reject gratuitous translation away from the cited source', prompt)
            self.assertNotIn('artifact_path', prompt)

    def test_validator_reads_full_source_without_repeating_block_quotes(self):
        response = proposal(self.bundle)
        for evidence in response['nodes'][0]['evidence']:
            identifier,role=evidence['information_id'],evidence['source_role']
            evidence.clear()
            evidence.update(information_id=identifier,source_block_id='/page0/body',source_role=role)
        candidates=normalize_proposals(response,self.bundle)['nodes']
        snapshot={'input':self.bundle,'existing_nodes':[],'existing_edges':[]}
        context={'input_snapshot':snapshot,'candidates':candidates,'validation_context_sha':'c'*64}
        before=deepcopy(context)
        prompt=validation(context,self.bundle['media_assets'])
        raw,projected=prompt.split('\nSOURCE_JSON:\n',1)[1].split('\nVALIDATION_CONTEXT_JSON:\n',1)
        source=json.loads(raw); exposed=json.loads(projected)
        self.assertEqual([u['content'] for u in source['information']],
                         [u['content'] for u in self.bundle['model_input']['information']])
        self.assertEqual([u['media'] for u in source['information']],
                         [u['media'] for u in self.bundle['model_input']['information']])
        for original,citation in zip(candidates[0]['evidence'],exposed['candidates'][0]['evidence']):
            self.assertNotIn('quote',citation)
            self.assertEqual(citation['quote_sha256'],sha256(original['quote'].encode()).hexdigest())
            self.assertEqual((citation['char_start'],citation['char_end']),
                             (original['char_start'],original['char_end']))
        self.assertEqual(context,before)


if __name__ == '__main__':
    unittest.main()
