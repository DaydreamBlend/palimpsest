"""Paper/wiki projection contracts with synthetic I; no models or storage."""

from copy import deepcopy
from hashlib import sha256
import json
import re
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.paper_wiki import (generation_schema, normalize_proposal, validation_schema,
    validate_decisions, render_paper, render_topic, escape_text, ITEM_CHECKS,
    citation_repair_schema, normalize_citation_repair)
from test_multi_source_i2k import packet, uid


def source_packet():
    source = packet(1)
    unit = deepcopy(source['model_input']['information'][0])
    unit.update(information_id=uid(2), origin_record_id=uid(12), title='Synthetic result',
                content='A readout of 3 μm was reported only for treatment A. Cafe\u0301.', media=[])
    anchor = sha256(unit['content'].encode()).hexdigest()
    unit['content_fingerprint'] = anchor
    unit['source_refs'] = [{'block_id': '/page1/result', 'page_index': 1, 'bbox': [5, 6, 70, 80],
                           'raw_locator': '/page1/result', 'anchor_sha256': anchor}]
    unit['source_assembly']['content_segments'] = [{'source_block_id': '/page1/result',
        'page_index': 1, 'char_start': 0, 'char_end': len(unit['content']),
        'source_char_range': [0, len(unit['content'])], 'text_origin': 'parser_source',
        'raw_locator': '/page1/result', 'anchor_sha256': anchor}]
    source['model_input']['information'].append(unit)
    source['target_information_ids'].append(uid(2))
    source['input_sha256'] = digest({key: value for key, value in source.items() if key != 'input_sha256'})
    return source


def proposal():
    return {'items': [
        {'item_key': 'overview1', 'section': 'overview', 'text': 'The document reports an ordered sequence.',
         'evidence': [{'information_id': uid(1), 'source_block_id': '/page0/body', 'source_role': 'other'}],
         'topic_keys': ['ordered-sequences']},
        {'item_key': 'result1', 'section': 'findings', 'text': 'Treatment A had a reported readout of 3 μm.',
         'evidence': [{'information_id': uid(2), 'quote': 'A readout of 3 μm was reported only for treatment A.',
                       'media_sha256': None, 'source_role': 'results'}], 'topic_keys': []}],
        'topics': [{'topic_key': 'ordered-sequences', 'title': 'Ordered sequences', 'scope': 'Explicit ordered-sequence definitions.'}],
        'reviews': [{'information_id': uid(1), 'disposition': 'used', 'reason': 'Synthetic selected overview evidence.'},
                    {'information_id': uid(2), 'disposition': 'used', 'reason': 'Synthetic selected result evidence.'}],
        'complete': True, 'issues': []}


def decisions(normalized):
    return {'items': [{'item_key': item['item_key'], 'verdict': 'accepted',
                      **{name: True for name in ITEM_CHECKS}, 'reason': 'Synthetic supporting verdict.'}
                     for item in normalized['items']],
            'topics': [{'topic_key': topic['topic_key'], 'verdict': 'accepted', 'meaning_correct': True,
                        'reason': 'Synthetic topic classification.'} for topic in normalized['topics']],
            'complete': True, 'issues': []}


def render_fixture():
    normalized = normalize_proposal(proposal(), source_packet(), [])
    page = {'page_id': uid(100), 'snapshot_id': uid(101), 'data_id': '1' * 64,
            'title': 'Synthetic paper', 'metadata': {'authors': ['Fixture author'], 'year': 2026},
            'items': normalized['items'], 'topics': normalized['topics']}
    catalog = {'topics': {'ordered-sequences': {'page_id': uid(200), 'title': 'Ordered sequences', 'snapshot_id': uid(201)}},
               'papers': {'1' * 64: {'page_id': uid(100), 'title': 'Synthetic paper'}}}
    return page, catalog


class PaperWikiTests(unittest.TestCase):
    def error(self, code, call):
        with self.assertRaises(PalimpsestError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_exact_block_and_quote_evidence_keep_owned_locations_without_input_changes(self):
        source, response = source_packet(), proposal()
        before = deepcopy((source, response))
        normalized = normalize_proposal(response, source, response['topics'])
        for item, unit in zip(normalized['items'], source['model_input']['information']):
            citation = item['evidence'][0]
            self.assertEqual(citation['quote'], unit['content'][citation['char_start']:citation['char_end']])
            self.assertEqual(citation['source_refs'], unit['source_refs'])
            self.assertEqual(citation['data_id'], source['data_id'])
            self.assertEqual(citation['source_execution_id'], source['source_execution_id'])
        self.assertEqual(normalized['items'][1]['evidence'][0]['page_numbers'], [2])
        self.assertEqual((source, response), before)

    def test_packet_scope_hash_and_citation_ownership_are_enforced(self):
        source = source_packet()
        changed = deepcopy(source)
        changed['model_input']['information'][0]['content'] += 'tampered'
        self.error('multi_source_packet_changed', lambda: normalize_proposal(proposal(), changed, []))
        for field in ('context_information_ids', 'excluded_information_ids'):
            changed = deepcopy(source)
            changed[field] = [uid(9)]
            self.error('selection_requires_all_information', lambda: normalize_proposal(proposal(), changed, []))
        response = proposal()
        response['items'][0]['evidence'][0]['information_id'] = uid(2)
        self.error('invalid_knowledge_block_reference', lambda: normalize_proposal(response, source, []))
        response['items'][0]['evidence'][0]['information_id'] = uid(9)
        self.error('invalid_knowledge_evidence', lambda: normalize_proposal(response, source, []))
        response = proposal()
        response['items'][0]['evidence'][0]['char_start'] = 0
        self.error('invalid_knowledge_evidence', lambda: normalize_proposal(response, source, []))

    def test_all_information_is_reviewed_but_importance_is_not_chosen_by_script(self):
        response, source = proposal(), source_packet()
        response['items'].pop()
        response['reviews'][1]['disposition'] = 'context_only'
        self.assertEqual(len(normalize_proposal(response, source, [])['items']), 1)
        response['reviews'].pop()
        self.error('paper_wiki_review_coverage_mismatch', lambda: normalize_proposal(response, source, []))
        response = proposal()
        response['reviews'][0]['disposition'] = 'not_selected'
        self.error('paper_wiki_review_evidence_mismatch', lambda: normalize_proposal(response, source, []))
        response = proposal()
        response['reviews'].append(deepcopy(response['reviews'][0]))
        self.error('paper_wiki_review_coverage_mismatch', lambda: normalize_proposal(response, source, []))

    def test_incomplete_review_stays_incomplete_and_empty_or_unstructured_paper_fails(self):
        response, source = proposal(), source_packet()
        response['items'].pop()
        response['reviews'][1]['disposition'] = 'needs_review'
        self.error('paper_wiki_unresolved_review', lambda: normalize_proposal(response, source, []))
        response['complete'] = False
        response['issues'] = ['The second unit remains unresolved.']
        self.assertIs(normalize_proposal(response, source, [])['complete'], False)
        response['items'][0]['section'] = 'methods'
        self.error('paper_wiki_summary_required', lambda: normalize_proposal(response, source, []))
        response['items'] = []
        self.error('invalid_paper_wiki_proposal', lambda: normalize_proposal(response, source, []))

    def test_topic_keys_cannot_change_existing_identity_or_invent_paths(self):
        source, response = source_packet(), proposal()
        existing = deepcopy(response['topics'])
        response['topics'][0]['scope'] = 'Another subject entirely.'
        self.error('paper_wiki_topic_catalog_mismatch', lambda: normalize_proposal(response, source, existing))
        response = proposal()
        existing = deepcopy(response['topics'])
        existing[0]['title'] = 'Cafe\u0301'
        response['topics'][0]['title'] = 'Café'
        self.error('paper_wiki_topic_catalog_mismatch', lambda: normalize_proposal(response, source, existing))
        for key in ('../escape', 'UpperCase', 'a' * 81, 'two--dashes'):
            response = proposal()
            response['topics'][0]['topic_key'] = key
            self.error('invalid_paper_wiki_topic', lambda: normalize_proposal(response, source, []))
        response = proposal()
        response['items'][0]['topic_keys'] = ['missing-topic']
        self.error('paper_wiki_topic_reference_mismatch', lambda: normalize_proposal(response, source, []))
        response = proposal()
        response['topics'].append({'topic_key': 'unused', 'title': 'Unused', 'scope': 'Not cited by any item.'})
        self.error('paper_wiki_unused_topic', lambda: normalize_proposal(response, source, []))

    def test_duplicate_items_topics_and_citations_are_rejected(self):
        source = source_packet()
        for collection, error in (('items', 'invalid_paper_wiki_item'), ('topics', 'duplicate_paper_wiki_topic')):
            response = proposal()
            response[collection].append(deepcopy(response[collection][0]))
            self.error(error, lambda: normalize_proposal(response, source, []))
        response = proposal()
        response['items'][0]['evidence'] *= 2
        self.error('duplicate_paper_wiki_evidence', lambda: normalize_proposal(response, source, []))

    def test_media_only_retains_owned_ref_and_unicode_quote_is_not_repaired(self):
        source, response = source_packet(), proposal()
        image = source['media_assets'][0]['sha256']
        response['items'][0]['evidence'] = [{'information_id': uid(1), 'quote': '',
            'media_sha256': image, 'source_role': 'figure'}]
        citation = normalize_proposal(response, source, [])['items'][0]['evidence'][0]
        self.assertEqual((citation['char_start'], citation['char_end'], citation['quote']), (0, 0, ''))
        self.assertEqual([ref['block_id'] for ref in citation['source_refs']], ['/page0/body'])
        response['items'][0]['evidence'][0]['media_sha256'] = 'f' * 64
        self.error('invalid_knowledge_evidence', lambda: normalize_proposal(response, source, []))
        response = proposal()
        response['items'][1]['evidence'][0]['quote'] = 'Cafe\u0301.'
        self.assertEqual(normalize_proposal(response, source, [])['items'][1]['evidence'][0]['quote'], 'Cafe\u0301.')
        response['items'][1]['evidence'][0]['quote'] = 'Café.'
        self.error('knowledge_quote_mismatch', lambda: normalize_proposal(response, source, []))

    def test_quote_location_selects_only_its_actual_block_and_page(self):
        source, response = source_packet(), proposal()
        unit = source['model_input']['information'][0]
        first, second = 'First text block.', 'Second text block.'
        unit['content'] = first + '\n\n' + second
        unit['content_fingerprint'] = sha256(unit['content'].encode()).hexdigest()
        unit['source_refs'], unit['source_assembly']['content_segments'] = [], []
        for block, text, start, page in (('/page0/body', first, 0, 0), ('/page1/body', second, len(first) + 2, 1)):
            anchor = sha256(text.encode()).hexdigest()
            unit['source_refs'].append({'block_id': block, 'page_index': page, 'raw_locator': block, 'anchor_sha256': anchor})
            unit['source_assembly']['content_segments'].append({'source_block_id': block, 'page_index': page,
                'raw_locator': block, 'anchor_sha256': anchor, 'char_start': start, 'char_end': start + len(text),
                'source_char_range': [0, len(text)], 'text_origin': 'parser_source'})
        source['input_sha256'] = digest({key: value for key, value in source.items() if key != 'input_sha256'})
        response['items'][0]['evidence'] = [{'information_id': uid(1), 'quote': second, 'media_sha256': None, 'source_role': 'other'}]
        citation = normalize_proposal(response, source, [])['items'][0]['evidence'][0]
        self.assertEqual([ref['block_id'] for ref in citation['source_refs']], ['/page1/body'])
        self.assertEqual(citation['page_numbers'], [2])
        response['items'][0]['evidence'][0]['quote'] = unit['content']
        citation = normalize_proposal(response, source, [])['items'][0]['evidence'][0]
        self.assertEqual(citation['page_numbers'], [1, 2])

    def test_generic_page_label_cannot_substitute_for_image_evidence(self):
        source, response = source_packet(), proposal()
        unit = source['model_input']['information'][0]
        unit['content'] = 'Original page 1'
        unit['content_fingerprint'] = sha256(unit['content'].encode()).hexdigest()
        block = '/original_page_facsimile/0'
        unit['source_refs'] = [{'block_id': block, 'page_index': 0, 'raw_locator': block,
            'anchor_sha256': 'c' * 64, 'source_collection': 'original_page_facsimile'}]
        unit['source_assembly']['content_segments'] = [{'source_block_id': block, 'page_index': 0,
            'raw_locator': block, 'anchor_sha256': 'c' * 64, 'char_start': None, 'char_end': None,
            'source_char_range': None, 'text_origin': 'original_page_facsimile'}]
        unit['media'][0]['source_block_id'] = block
        source['input_sha256'] = digest({key: value for key, value in source.items() if key != 'input_sha256'})
        response['items'][0]['evidence'] = [{'information_id': uid(1), 'quote': unit['content'],
            'media_sha256': unit['media'][0]['sha256'], 'source_role': 'figure'}]
        self.error('paper_wiki_citation_locus_missing', lambda: normalize_proposal(response, source, []))
        response['items'][0]['evidence'][0]['quote'] = ''
        self.assertEqual(normalize_proposal(response, source, [])['items'][0]['evidence'][0]['source_refs'], unit['source_refs'])

    def test_validator_requires_every_item_topic_and_all_acceptance_checks(self):
        normalized = normalize_proposal(proposal(), source_packet(), [])
        for field in ITEM_CHECKS:
            response = decisions(normalized)
            response['items'][0][field] = False
            self.error('paper_wiki_acceptance_not_supported', lambda: validate_decisions(response, normalized))
            response['items'][0]['verdict'] = 'rejected'
            self.assertEqual(validate_decisions(response, normalized)['items'][0]['verdict'], 'rejected')
        response = decisions(normalized)
        response['topics'][0]['meaning_correct'] = False
        self.error('paper_wiki_acceptance_not_supported', lambda: validate_decisions(response, normalized))
        for collection in ('items', 'topics'):
            response = decisions(normalized)
            response[collection].pop()
            self.error('paper_wiki_decision_coverage_mismatch', lambda: validate_decisions(response, normalized))
            response = decisions(normalized)
            response[collection].append(deepcopy(response[collection][0]))
            self.error('paper_wiki_decision_coverage_mismatch', lambda: validate_decisions(response, normalized))

    def test_citation_repair_preserves_every_other_item_and_all_existing_content(self):
        source, raw = source_packet(), proposal()
        for n in range(4):
            raw['items'].append({**deepcopy(raw['items'][0]), 'item_key': f'untouched{n}'})
        base = normalize_proposal(raw, source, [])
        repair = {'additions': [{'item_key': 'overview1', 'evidence': [
            {'information_id': uid(2), 'source_block_id': '/page1/result', 'source_role': 'results'}]}],
            'reviews': deepcopy(base['reviews']), 'complete': True, 'issues': []}
        before = deepcopy((source, base, repair))
        result = normalize_citation_repair(repair, source, base)
        self.assertEqual((source, base, repair), before)
        self.assertEqual(result['topics'], base['topics'])
        self.assertEqual(result['items'][1:], base['items'][1:])
        self.assertEqual(result['items'][0]['evidence'][:-1], base['items'][0]['evidence'])
        for field in ('item_key', 'section', 'text', 'topic_keys'):
            self.assertEqual(result['items'][0][field], base['items'][0][field])
        added = result['items'][0]['evidence'][-1]
        self.assertEqual(added['quote'], source['model_input']['information'][1]['content'])
        self.assertEqual(added['data_id'], source['data_id'])
        self.assertEqual(added['source_execution_id'], source['source_execution_id'])
        self.assertEqual(added['page_numbers'], [2])
        # A repaired result receives the complete ordinary Validator contract.
        self.assertEqual(len(validate_decisions(decisions(result), result)['items']), 6)

    def test_citation_repair_new_information_requires_used_review_and_full_coverage(self):
        source, raw = source_packet(), proposal()
        raw['items'].pop()
        raw['reviews'][1]['disposition'] = 'context_only'
        base = normalize_proposal(raw, source, [])
        repair = {'additions': [{'item_key': 'overview1', 'evidence': [
            {'information_id': uid(2), 'source_block_id': '/page1/result', 'source_role': 'results'}]}],
            'reviews': deepcopy(base['reviews']), 'complete': True, 'issues': []}
        self.error('paper_wiki_review_evidence_mismatch', lambda: normalize_citation_repair(repair, source, base))
        repair['reviews'][1].update(disposition='used', reason='This source now supplies an additional citation.')
        result = normalize_citation_repair(repair, source, base)
        self.assertEqual([review['disposition'] for review in result['reviews']], ['used', 'used'])
        repair['reviews'].pop()
        self.error('paper_wiki_review_coverage_mismatch', lambda: normalize_citation_repair(repair, source, base))

    def test_citation_repair_cannot_modify_body_sections_topics_or_replace_evidence(self):
        source = source_packet()
        base = normalize_proposal(proposal(), source, [])
        repair = {'additions': [{'item_key': 'overview1', 'evidence': [
            {'information_id': uid(2), 'source_block_id': '/page1/result', 'source_role': 'results'}]}],
            'reviews': deepcopy(base['reviews']), 'complete': True, 'issues': []}
        before = deepcopy((source, base, repair))
        for field, value in (('text', 'Changed claim'), ('section', 'limitations'),
                             ('topic_keys', []), ('remove_evidence', [0])):
            changed = deepcopy(repair)
            changed['additions'][0][field] = value
            self.error('invalid_paper_wiki_citation_repair', lambda: normalize_citation_repair(changed, source, base))
        for field in ('items', 'topics', 'page_id'):
            changed = {**repair, field: []}
            self.error('invalid_paper_wiki_citation_repair', lambda: normalize_citation_repair(changed, source, base))
        self.assertEqual((source, base, repair), before)

    def test_citation_repair_rejects_unknown_item_and_duplicate_item_or_citation(self):
        source = source_packet()
        base = normalize_proposal(proposal(), source, [])
        addition = {'item_key': 'overview1', 'evidence': [
            {'information_id': uid(2), 'source_block_id': '/page1/result', 'source_role': 'results'}]}
        repair = {'additions': [addition], 'reviews': deepcopy(base['reviews']), 'complete': True, 'issues': []}
        changed = deepcopy(repair)
        changed['additions'][0]['item_key'] = 'missing-item'
        self.error('paper_wiki_repair_item_mismatch', lambda: normalize_citation_repair(changed, source, base))
        changed = deepcopy(repair)
        changed['additions'].append(deepcopy(addition))
        self.error('paper_wiki_repair_item_mismatch', lambda: normalize_citation_repair(changed, source, base))
        changed = deepcopy(repair)
        changed['additions'][0]['evidence'] *= 2
        self.error('duplicate_paper_wiki_evidence', lambda: normalize_citation_repair(changed, source, base))
        for role in ('other', 'methods'):
            changed = deepcopy(repair)
            changed['additions'][0]['evidence'] = [{'information_id': uid(1),
                'source_block_id': '/page0/body', 'source_role': role}]
            self.error('duplicate_paper_wiki_evidence', lambda: normalize_citation_repair(changed, source, base))
        # Quote spelling versus block syntax must not create a second copy of
        # the same exact locus already in the frozen base.
        changed = deepcopy(repair)
        old = base['items'][0]['evidence'][0]
        changed['additions'][0]['evidence'] = [{key: old[key] for key in
            ('information_id', 'quote', 'media_sha256', 'source_role')}]
        self.error('duplicate_paper_wiki_evidence', lambda: normalize_citation_repair(changed, source, base))

    def test_citation_repair_checks_media_and_information_ownership(self):
        source = source_packet()
        base = normalize_proposal(proposal(), source, [])
        repair = {'additions': [{'item_key': 'overview1', 'evidence': [
            {'information_id': uid(1), 'quote': '', 'media_sha256': source['media_assets'][0]['sha256'],
             'source_role': 'figure'}]}], 'reviews': deepcopy(base['reviews']), 'complete': True, 'issues': []}
        result = normalize_citation_repair(repair, source, base)
        self.assertEqual(result['items'][0]['evidence'][-1]['media_sha256'], source['media_assets'][0]['sha256'])
        repair['additions'][0]['evidence'][0]['information_id'] = uid(2)
        self.error('invalid_knowledge_evidence', lambda: normalize_citation_repair(repair, source, base))
        repair['additions'][0]['evidence'][0]['information_id'] = uid(99)
        self.error('invalid_knowledge_evidence', lambda: normalize_citation_repair(repair, source, base))
        repair['additions'][0]['evidence'][0].update(information_id=uid(1), media_sha256='f' * 64)
        self.error('invalid_knowledge_evidence', lambda: normalize_citation_repair(repair, source, base))

    def test_citation_repair_can_report_no_evidence_without_fabricating_completion(self):
        source = source_packet()
        base = normalize_proposal(proposal(), source, [])
        repair = {'additions': [], 'reviews': deepcopy(base['reviews']), 'complete': False,
                  'issues': ['The missing supporting evidence could not be located.']}
        result = normalize_citation_repair(repair, source, base)
        self.assertIs(result['complete'], False)
        self.assertEqual(result['items'], base['items'])
        self.assertEqual(result['topics'], base['topics'])
        self.assertEqual(result['issues'], repair['issues'])
        repair['complete'] = True
        self.error('invalid_paper_wiki_citation_repair', lambda: normalize_citation_repair(repair, source, base))
        repair['complete'] = False
        repair['additions'] = [{'item_key': 'overview1', 'evidence': []}]
        self.error('invalid_paper_wiki_citation_repair', lambda: normalize_citation_repair(repair, source, base))

    def test_citation_repair_schema_has_only_additions_and_whole_source_review(self):
        source = source_packet()
        base = normalize_proposal(proposal(), source, [])
        schema = citation_repair_schema(source, base)
        self.assertEqual(set(schema['properties']), {'additions', 'reviews', 'complete', 'issues'})
        self.assertIs(schema['additionalProperties'], False)
        self.assertNotIn('minItems', schema['properties']['additions'])
        self.assertNotIn('maxItems', schema['properties']['additions'])
        addition = schema['properties']['additions']['items']
        self.assertIs(addition['additionalProperties'], False)
        self.assertEqual(set(addition['properties']), {'item_key', 'evidence'})
        self.assertEqual(addition['properties']['item_key']['enum'], ['overview1', 'result1'])
        self.assertEqual(addition['properties']['evidence']['minItems'], 1)
        self.assertEqual(schema['properties']['reviews']['items']['properties']['information_id']['enum'], [uid(1), uid(2)])

    def test_scoped_text_repair_changes_only_authorized_text_and_keeps_all_citations(self):
        source = source_packet()
        base = normalize_proposal(proposal(), source, [])
        changed_text = 'The reported readout is scoped to treatment A.'
        repair = {'additions': [], 'text_changes': [{'item_key': 'result1', 'text': changed_text}],
                  'reviews': deepcopy(base['reviews']), 'complete': True, 'issues': []}
        before = deepcopy((source, base, repair))
        result = normalize_citation_repair(repair, source, base, editable_item_keys=['result1'])
        self.assertEqual((source, base, repair), before)
        self.assertEqual(result['items'][0], base['items'][0])
        self.assertEqual(result['topics'], base['topics'])
        self.assertEqual(result['items'][1], {**base['items'][1], 'text': changed_text})
        self.assertEqual([item['evidence'] for item in result['items']], [item['evidence'] for item in base['items']])
        self.assertIs(result['complete'], True)

    def test_scoped_text_repair_rejects_unauthorized_duplicate_keys_and_nontext_changes(self):
        source = source_packet()
        base = normalize_proposal(proposal(), source, [])
        repair = {'additions': [], 'text_changes': [{'item_key': 'overview1', 'text': 'A revised source summary.'}],
                  'reviews': deepcopy(base['reviews']), 'complete': True, 'issues': []}
        for keys in (['unknown'], ['overview1', 'overview1'], 'overview1', [None]):
            self.error('invalid_paper_wiki_editable_items', lambda: citation_repair_schema(source, base, editable_item_keys=keys))
            self.error('invalid_paper_wiki_editable_items', lambda: normalize_citation_repair(repair, source, base, editable_item_keys=keys))
        changed = deepcopy(repair)
        changed['text_changes'][0]['item_key'] = 'result1'
        self.error('paper_wiki_repair_item_mismatch', lambda: normalize_citation_repair(changed, source, base, editable_item_keys=['overview1']))
        changed = deepcopy(repair)
        changed['text_changes'] *= 2
        self.error('paper_wiki_repair_item_mismatch', lambda: normalize_citation_repair(changed, source, base, editable_item_keys=['overview1']))
        for field, value in (('evidence', []), ('section', 'methods'), ('topic_keys', [])):
            changed = deepcopy(repair)
            changed['text_changes'][0][field] = value
            self.error('invalid_paper_wiki_citation_repair', lambda: normalize_citation_repair(changed, source, base, editable_item_keys=['overview1']))
        changed = deepcopy(repair)
        changed['text_changes'][0]['text'] = '  '
        self.error('invalid_paper_wiki_citation_repair', lambda: normalize_citation_repair(changed, source, base, editable_item_keys=['overview1']))

    def test_scoped_text_repair_requires_actual_change_for_completion(self):
        source = source_packet()
        base = normalize_proposal(proposal(), source, [])
        repair = {'additions': [], 'text_changes': [{'item_key': 'overview1', 'text': base['items'][0]['text']}],
                  'reviews': deepcopy(base['reviews']), 'complete': True, 'issues': []}
        self.error('invalid_paper_wiki_citation_repair', lambda: normalize_citation_repair(repair, source, base, editable_item_keys=['overview1']))
        repair['complete'] = False
        result = normalize_citation_repair(repair, source, base, editable_item_keys=['overview1'])
        self.assertEqual(result['items'], base['items'])
        self.assertIs(result['complete'], False)
        repair.update(complete=True, additions=[{'item_key': 'overview1', 'evidence': [
            {'information_id': uid(2), 'source_block_id': '/page1/result', 'source_role': 'results'}]}])
        result = normalize_citation_repair(repair, source, base, editable_item_keys=['overview1'])
        self.assertEqual(result['items'][0]['text'], base['items'][0]['text'])
        self.assertEqual(len(result['items'][0]['evidence']), len(base['items'][0]['evidence']) + 1)

    def test_scoped_text_schema_is_opt_in_and_default_schema_bytes_are_unchanged(self):
        source = source_packet()
        base = normalize_proposal(proposal(), source, [])
        default = citation_repair_schema(source, base)
        schema_bytes = json.dumps(default, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        # Captured before adding editable_item_keys; order and default schema
        # bytes are part of the historical request/receipt binding.
        self.assertEqual(sha256(schema_bytes).hexdigest(), 'aca94156bfb318ad33caf1d0cef433f1e49565d356d497f7acf759084ea27650')
        self.assertEqual(default, citation_repair_schema(source, base, editable_item_keys=[]))
        schema = citation_repair_schema(source, base, editable_item_keys=['result1'])
        self.assertIn('text_changes', schema['required'])
        change = schema['properties']['text_changes']['items']
        self.assertEqual(set(change['properties']), {'item_key', 'text'})
        self.assertEqual(change['properties']['item_key']['enum'], ['result1'])
        self.assertIs(change['additionalProperties'], False)
        repair = {'additions': [], 'text_changes': [], 'reviews': deepcopy(base['reviews']), 'complete': False, 'issues': []}
        for keys in (None, []):
            self.error('invalid_paper_wiki_citation_repair', lambda: normalize_citation_repair(repair, source, base, editable_item_keys=keys))
        del repair['text_changes']
        self.error('invalid_paper_wiki_citation_repair', lambda: normalize_citation_repair(repair, source, base, editable_item_keys=['result1']))

    def test_validator_boolean_types_and_unresolved_status_are_not_silently_completed(self):
        normalized = normalize_proposal(proposal(), source_packet(), [])
        response = decisions(normalized)
        response['items'][0]['source_supported'] = 1
        self.error('invalid_paper_wiki_decision', lambda: validate_decisions(response, normalized))
        response = decisions(normalized)
        response['items'][0]['verdict'] = 'needs_review'
        self.error('paper_wiki_unresolved_review', lambda: validate_decisions(response, normalized))
        response['complete'] = False
        self.assertIs(validate_decisions(response, normalized)['complete'], False)
        response = decisions(normalized)
        response['items'].reverse()
        self.assertEqual([item['item_key'] for item in validate_decisions(response, normalized)['items']],
                         [item['item_key'] for item in normalized['items']])

    def test_schema_is_closed_with_no_model_path_or_offset_fields(self):
        source, response = source_packet(), proposal()
        normalized = normalize_proposal(response, source, [])
        def visit(schema):
            if schema.get('type') == 'object':
                self.assertIs(schema['additionalProperties'], False)
                self.assertEqual(set(schema['required']), set(schema['properties']))
                for child in schema['properties'].values():
                    visit(child)
            if schema.get('type') == 'array':
                visit(schema['items'])
            for branch in schema.get('anyOf', []):
                visit(branch)
        generated = generation_schema(source, [])
        visit(generated)
        visit(validation_schema(normalized))
        evidence = generated['properties']['items']['items']['properties']['evidence']['items']['anyOf']
        self.assertEqual(set(evidence[1]['properties']), {'information_id', 'source_block_id', 'source_role'})
        response['topics'] = []
        response['items'][0]['topic_keys'] = []
        empty_topics = normalize_proposal(response, source, [])
        self.assertEqual(validation_schema(empty_topics)['properties']['topics']['maxItems'], 0)

    def test_paper_render_is_deterministic_and_escapes_layout_html_and_links(self):
        page, catalog = render_fixture()
        page['items'][0]['text'] = '# injected\n<script>alert(1)</script> [[../../escape|click]] [click](javascript:alert(1)) μ²'
        page['metadata']['label'] = '<img src=x onerror=alert(1)>'
        before = deepcopy((page, catalog))
        rendered = render_paper(page, catalog)
        self.assertEqual(rendered, render_paper(page, catalog))
        self.assertEqual(before, (page, catalog))
        self.assertNotIn('\n# injected', rendered)
        self.assertNotIn('<script>', rendered)
        self.assertNotIn('<img', rendered)
        self.assertNotIn('[[../../escape', rendered)
        self.assertNotIn('[click](javascript:', rendered)
        self.assertIn('μ²', rendered)
        self.assertIn(f'[[topics/{uid(200)}|Ordered sequences]]', rendered)
        self.assertIn('## 개요\n', rendered)
        self.assertIn('## 주요 결과\n', rendered)
        self.assertIn('## 출처\n', rendered)
        self.assertIn(source_packet()['model_input']['information'][0]['content'], rendered)
        self.assertIn('chars `[0,', rendered)
        self.assertIn('page 2; block /page1/result', rendered)
        self.assertIn('../originals/' + '1' * 64 + '.pdf#page=2', rendered)
        for text in ('- an injected list', '+ another list', '1. numbered list', '---'):
            page['items'][0]['text'] = text
            self.assertNotIn('\n' + text + ' ', render_paper(page, catalog))

    def test_topic_render_preserves_per_paper_boundaries_without_new_synthesis(self):
        paper, catalog = render_fixture()
        item = paper['items'][0]
        topic = {'page_id': uid(200), 'title': 'Ordered sequences', 'scope': 'Explicit definitions.',
                 'topic_key': 'ordered-sequences', 'contributions': [{'paper_page_id': paper['page_id'],
                    'paper_data_id': paper['data_id'], 'paper_title': paper['title'], 'items': [item]}]}
        before = deepcopy(topic)
        rendered = render_topic(topic, catalog)
        self.assertEqual(before, topic)
        self.assertIn(f'[[papers/{uid(100)}|Synthetic paper]]', rendered)
        self.assertIn('### 개요\n', rendered)
        self.assertIn(item['text'].replace('.', r'\.'), rendered)
        self.assertEqual(re.findall(r'\[\[(papers|topics)/', rendered), ['papers'])
        topic['contributions'][0]['paper_page_id'] = uid(999)
        self.error('invalid_paper_wiki_catalog', lambda: render_topic(topic, catalog))

    def test_renderer_rejects_spoofed_citation_owner_or_catalog_target(self):
        page, catalog = render_fixture()
        page['items'][0]['evidence'][0]['data_id'] = '2' * 64
        self.error('paper_wiki_citation_owner_mismatch', lambda: render_paper(page, catalog))
        page, catalog = render_fixture()
        catalog['topics']['ordered-sequences']['page_id'] = '../../escape'
        self.error('invalid_paper_wiki_catalog', lambda: render_paper(page, catalog))

    def test_fixed_frontmatter_cannot_be_rewritten_by_title_and_keeps_snapshot_optional(self):
        page, catalog = render_fixture()
        page['title'] = '논문 "제목"\ncanonical: true\n---\n# override'
        rendered = render_paper(page, catalog)
        lines = rendered.splitlines()
        self.assertEqual(lines[0], '---')
        self.assertEqual(lines[6], '---')
        metadata = {line.split(': ', 1)[0]: json.loads(line.split(': ', 1)[1]) for line in lines[1:6]}
        self.assertEqual(set(metadata), {'page_id', 'snapshot_id', 'kind', 'title', 'canonical'})
        self.assertEqual(metadata['title'], page['title'])
        self.assertIs(metadata['canonical'], False)
        self.assertEqual(metadata['snapshot_id'], uid(101))
        self.assertEqual(metadata['kind'], 'paper')
        del page['snapshot_id']
        self.assertIn('snapshot_id: null\n', render_paper(page, catalog))
        self.assertEqual(escape_text('# title\n<script>[[bad]]</script>'), r'\# title &lt;script&gt;\[\[bad\]\]&lt;/script&gt;')


if __name__ == '__main__':
    unittest.main()
