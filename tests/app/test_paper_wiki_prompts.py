"""Synthetic prompt-delivery contracts only; no models, PDFs or database."""

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.knowledge import source_block_ranges
from palimpsest.paper_wiki_prompts import citation_repair, generation, validation, source_input
from test_multi_source_i2k import packet, uid


def fixture():
    source = packet(1)
    unit = source['model_input']['information'][0]
    blocks = ['The experiment used mouse BMDCs, not monocyte-derived DCs.',
              'Reported measurement: ' + 'unchanged source text ' * 80 + 'μg/mL. Cafe\u0301. x^{2}.',
              'The control did not receive that treatment.']
    unit['content'] = '\n\n'.join(blocks)
    unit['content_fingerprint'] = sha256(unit['content'].encode()).hexdigest()
    unit['source_refs'], segments = [], []
    offset = 0
    for index, content in enumerate(blocks):
        identifier = f'/page0/body{index}'
        anchor = sha256(content.encode()).hexdigest()
        locator = f'/pdf_info/0/preproc_blocks/{index}'
        unit['source_refs'].append({'block_id': identifier, 'page_index': 0,
            'bbox': [0, index * 50, 300, index * 50 + 40], 'raw_locator': locator,
            'anchor_sha256': anchor, 'page_size': [600, 800]})
        segments.append({'source_block_id': identifier, 'page_index': 0,
            'char_start': offset, 'char_end': offset + len(content),
            'source_char_range': [0, len(content)], 'text_origin': 'parser_source',
            'raw_locator': locator, 'anchor_sha256': anchor})
        offset += len(content) + 2
    unit['source_assembly'] = {'algorithm': 'source-groups-v1', 'content_segments': segments}
    unit['media'][0]['source_block_id'] = '/page0/body1'
    image = deepcopy(unit)
    image.update(information_id=uid(2), origin_record_id=uid(12), kind='image',
                 unit_type='image', title='Page image', content='', content_fingerprint=sha256(b'').hexdigest())
    image.pop('source_assembly')
    image['source_refs'] = [{'block_id': '/original_page_facsimile/1', 'page_index': 1,
                            'facsimile_provenance': {'source_data_id': source['data_id']}}]
    image_sha = sha256(b'original page raster').hexdigest()
    image['media'] = [{'sha256': image_sha, 'byte_size': 20, 'page_index': 1,
                       'source_block_id': '/original_page_facsimile/1'}]
    source['model_input']['information'].append(image)
    source['target_information_ids'].append(image['information_id'])
    source['media_assets'].append({'sha256': image_sha, 'byte_size': 20,
        'artifact_path': f'derived/objects/sha256/{image_sha[:2]}/{image_sha}'})
    source['input_sha256'] = digest({key: value for key, value in source.items() if key != 'input_sha256'})
    snapshot = {'input': source, 'metadata': {'title': 'Synthetic paper', 'filename': 'fixture.pdf'},
        'existing_topics': [{'topic_key': 'mouse-bone-marrow-derived-dendritic-cells',
            'title': 'Mouse bone-marrow-derived dendritic cells (BMDCs)', 'scope': 'mouse BMDC preparations'}],
        'prior_feedback': {'issues': ['Check the exact reported measurement.']}}
    return snapshot, list(reversed(source['media_assets']))


def projected_source(prompt):
    return json.loads(prompt.split('\nSOURCE_JSON:\n', 1)[1].split('\nVALIDATION_CONTEXT_JSON:\n', 1)[0])


def normalized_proposal(source):
    unit = source['model_input']['information'][0]
    start, end = source_block_ranges(unit)['/page0/body1']
    citation = {'information_id': unit['information_id'], 'source_block_id': '/page0/body1',
        'source_role': 'results', 'quote': unit['content'][start:end],
        'char_start': start, 'char_end': end, 'media_sha256': None, 'data_id': source['data_id'],
        'source_execution_id': source['source_execution_id'], 'page_numbers': [1],
        'source_refs': [unit['source_refs'][1]]}
    return {'items': [{'item_key': key, 'section': 'findings', 'text': '가상의 보고 문장.',
                      'evidence': [deepcopy(citation)], 'topic_keys': []} for key in ('result-a', 'result-b')],
            'topics': [], 'reviews': [], 'complete': False, 'issues': ['Synthetic test only.']}


class PaperWikiPromptTests(unittest.TestCase):
    def test_generator_preserves_complete_i_unicode_media_and_attachment_order(self):
        snapshot, attachments = fixture()
        before = deepcopy((snapshot, attachments))
        delivered = projected_source(generation(snapshot, attachments))
        self.assertEqual((snapshot, attachments), before)
        self.assertEqual(delivered['input_sha256'], snapshot['input']['input_sha256'])
        self.assertEqual(delivered['data_id'], snapshot['input']['data_id'])
        for actual, original in zip(delivered['information'], snapshot['input']['model_input']['information'], strict=True):
            for key in ('information_id', 'content', 'content_fingerprint', 'media', 'source_refs'):
                self.assertEqual(actual[key], original[key])
        self.assertGreater(len(delivered['information'][0]['content']), 1500)
        self.assertLess(len(delivered['information'][0]['text_blocks'][1]['preview']), 210)
        self.assertEqual(delivered['information'][1]['content'], '')
        self.assertEqual(delivered['information'][1]['text_blocks'], [])
        self.assertEqual(delivered['image_attachment_order'], [
            {'image_number': index + 1, 'sha256': item['sha256']} for index, item in enumerate(attachments)])

    def test_missing_duplicate_and_foreign_images_fail_before_prompt_delivery(self):
        snapshot, attachments = fixture()
        for invalid in (attachments[:1], attachments + attachments[:1], [{'sha256': '0' * 64}], None):
            with self.subTest(attachments=invalid), self.assertRaises(PalimpsestError) as caught:
                generation(snapshot, invalid)
            self.assertEqual(caught.exception.code, 'invalid_paper_wiki_attachments')

    def test_changed_packet_and_incomplete_source_are_rejected(self):
        snapshot, attachments = fixture()
        snapshot['input']['model_input']['information'][0]['content'] += 'Unhashed addition.'
        with self.assertRaises(PalimpsestError):
            generation(snapshot, attachments)
        snapshot, attachments = fixture()
        snapshot['input']['excluded_information_ids'] = [uid(99)]
        with self.assertRaises(PalimpsestError):
            generation(snapshot, attachments)

    def test_prompt_hash_is_deterministic_for_equivalent_json_order(self):
        snapshot, attachments = fixture()
        reordered = json.loads(json.dumps(snapshot, sort_keys=True))
        first = generation(snapshot, attachments)
        self.assertEqual(sha256(first.encode()).hexdigest(), sha256(generation(reordered, attachments).encode()).hexdigest())
        reordered['metadata']['doi'] = '10.0000/synthetic'
        self.assertNotEqual(sha256(first.encode()).hexdigest(), sha256(generation(reordered, attachments).encode()).hexdigest())

    def test_only_topic_identity_metadata_and_feedback_prime_generation(self):
        snapshot, attachments = fixture()
        snapshot['existing_nodes'] = [{'statement': 'DO_NOT_PRIME_WITH_ACCEPTED_K'}]
        snapshot['existing_topics'][0]['accepted_claims'] = ['DO_NOT_IMPORT_TOPIC_TRUTH']
        prompt = generation(snapshot, attachments)
        self.assertNotIn('DO_NOT_PRIME_WITH_ACCEPTED_K', prompt)
        self.assertNotIn('DO_NOT_IMPORT_TOPIC_TRUTH', prompt)
        context = json.loads(prompt.split('\nPAGE_CONTEXT_JSON:\n', 1)[1].split('\nSOURCE_JSON:\n', 1)[0])
        self.assertEqual(set(context['existing_topics'][0]), {'topic_key', 'title', 'scope'})
        self.assertEqual(context['prior_feedback'], snapshot['prior_feedback'])

    def test_validator_shows_full_exact_evidence_once_with_context_only_neighbors(self):
        snapshot, attachments = fixture()
        proposal = normalized_proposal(snapshot['input'])
        context = {'input_snapshot': snapshot, 'proposal': proposal}
        before = deepcopy(context)
        prompt = validation(context, attachments)
        audit = json.loads(prompt.split('\nVALIDATION_CONTEXT_JSON:\n', 1)[1])
        self.assertEqual(context, before)
        self.assertEqual(len(audit['evidence_catalog']), 1)
        entry = audit['evidence_catalog'][0]
        original = proposal['items'][0]['evidence'][0]
        self.assertEqual(entry['quote'], original['quote'])
        self.assertEqual(entry['quote_sha256'], sha256(original['quote'].encode()).hexdigest())
        self.assertEqual(entry['source_refs'], original['source_refs'])
        self.assertEqual([neighbor['position'] for neighbor in entry['context_only_neighbors']], ['previous', 'following'])
        unit = snapshot['input']['model_input']['information'][0]
        for neighbor in entry['context_only_neighbors']:
            self.assertEqual(neighbor['text'], unit['content'][neighbor['char_start']:neighbor['char_end']])
        for item in audit['proposal']['items']:
            self.assertEqual(item['evidence'], [{'evidence_key': entry['evidence_key'], 'source_role': 'results'}])
        self.assertEqual(projected_source(prompt), source_input(snapshot['input'], attachments))
        self.assertEqual(sha256(prompt.encode()).hexdigest(), sha256(validation(before, attachments).encode()).hexdigest())

    def test_validator_media_only_evidence_preserves_owned_hash_without_fake_quote(self):
        snapshot, attachments = fixture()
        proposal = normalized_proposal(snapshot['input'])
        image = snapshot['input']['model_input']['information'][1]
        proposal['items'][0]['evidence'] = [{'information_id': image['information_id'], 'quote': '',
            'char_start': None, 'char_end': None, 'media_sha256': image['media'][0]['sha256'],
            'source_role': 'figure', 'data_id': snapshot['input']['data_id']}]
        prompt = validation({'input_snapshot': snapshot, 'proposal': proposal}, attachments)
        entry = json.loads(prompt.split('\nVALIDATION_CONTEXT_JSON:\n', 1)[1])['evidence_catalog'][0]
        self.assertEqual(entry['quote'], '')
        self.assertEqual(entry['media_sha256'], image['media'][0]['sha256'])
        self.assertEqual(entry['context_only_neighbors'], [])

    def test_citation_repair_keeps_full_source_and_frozen_evidence_without_mutation(self):
        snapshot, attachments = fixture()
        base = normalized_proposal(snapshot['input'])
        snapshot['prior_feedback'] = {'request_id': uid(80), 'proposal': base,
            'result': {'complete': False, 'issues': ['The subject needs an exact citation.']},
            'review_notes': ['Recheck the full source, not only the short preview.']}
        before = deepcopy((snapshot, attachments))
        prompt = citation_repair(snapshot, attachments)
        delivered, raw_context = prompt.split('\nSOURCE_JSON:\n', 1)[1].split('\nCITATION_REPAIR_CONTEXT_JSON:\n', 1)
        self.assertEqual(json.loads(delivered), source_input(snapshot['input'], attachments))
        context = json.loads(raw_context)
        self.assertEqual(context['base_proposal_sha256'], digest(base))
        self.assertEqual(len(context['evidence_catalog']), 1)
        self.assertEqual(context['evidence_catalog'][0]['quote'], base['items'][0]['evidence'][0]['quote'])
        self.assertEqual(context['proposal']['topics'], base['topics'])
        for actual, original in zip(context['proposal']['items'], base['items'], strict=True):
            self.assertEqual({k: v for k, v in actual.items() if k != 'evidence'},
                             {k: v for k, v in original.items() if k != 'evidence'})
        self.assertNotIn('proposal', context['prior_feedback'])
        self.assertEqual(context['prior_feedback']['result'], snapshot['prior_feedback']['result'])
        self.assertEqual(context['prior_feedback']['review_notes'], snapshot['prior_feedback']['review_notes'])
        self.assertEqual((snapshot, attachments), before)

    def test_citation_repair_rejects_missing_base_or_incomplete_image_delivery(self):
        snapshot, attachments = fixture()
        with self.assertRaises(PalimpsestError) as caught:
            citation_repair(snapshot, attachments)
        self.assertEqual(caught.exception.code, 'invalid_wiki_citation_repair_context')
        snapshot['prior_feedback']['proposal'] = normalized_proposal(snapshot['input'])
        with self.assertRaises(PalimpsestError) as caught:
            citation_repair(snapshot, attachments[:1])
        self.assertEqual(caught.exception.code, 'invalid_paper_wiki_attachments')

    def test_citation_repair_prompt_binds_base_and_notes_and_requires_unresolved_report(self):
        snapshot, attachments = fixture()
        snapshot['prior_feedback'] = {'proposal': normalized_proposal(snapshot['input']),
                                     'review_notes': ['Check subject.']}
        first = citation_repair(snapshot, attachments)
        self.assertEqual(first, citation_repair(json.loads(json.dumps(snapshot, sort_keys=True)), attachments))
        snapshot['prior_feedback']['review_notes'] = ['Check timing.']
        self.assertNotEqual(first, citation_repair(snapshot, attachments))
        snapshot['prior_feedback']['proposal']['items'][0]['text'] = 'Changed proposed claim.'
        changed = citation_repair(snapshot, attachments)
        context = json.loads(changed.split('\nCITATION_REPAIR_CONTEXT_JSON:\n', 1)[1])
        self.assertEqual(context['base_proposal_sha256'], digest(snapshot['prior_feedback']['proposal']))
        self.assertIn('return complete=false', changed)
        self.assertIn('additions array may be empty with complete=false', changed)
        self.assertIn('requires at least one genuinely new citation', changed)
        self.assertIn('union of preserved base citations and valid additions', changed)
        self.assertNotIn('Write concise, readable Korean paragraphs/items', changed)

    def test_editable_repair_preserves_legacy_bytes_and_binds_only_explicit_keys(self):
        snapshot, attachments = fixture()
        snapshot['prior_feedback'] = {'proposal': normalized_proposal(snapshot['input'])}
        legacy = citation_repair(snapshot, attachments)
        self.assertEqual(sha256(legacy.encode()).hexdigest(),
                         'a7771dcaba5e5259ee818192a2e8180a67b2729f13bda5dad7b096114a30f18f')
        snapshot['editable_item_keys'] = None
        self.assertEqual(citation_repair(snapshot, attachments), legacy)
        snapshot['editable_item_keys'] = ['result-a']
        before = deepcopy(snapshot)
        prompt = citation_repair(snapshot, attachments)
        source, raw_context = prompt.split('\nSOURCE_JSON:\n', 1)[1].split('\nCITATION_REPAIR_CONTEXT_JSON:\n', 1)
        context = json.loads(raw_context)
        self.assertEqual(snapshot, before)
        self.assertEqual(context['editable_item_keys'], ['result-a'])
        self.assertEqual(context['base_proposal_sha256'], digest(snapshot['prior_feedback']['proposal']))
        self.assertEqual(context['proposal']['items'][1]['text'], '가상의 보고 문장.')
        self.assertEqual(json.loads(source), source_input(snapshot['input'], attachments))
        self.assertIn('schema: additions, text_changes, reviews, complete and issues.', prompt)
        self.assertIn('Only the text field of\nthose exact item keys may change.', prompt)
        self.assertIn('Both additions and text_changes may be empty with complete=false', prompt)
        self.assertIn('actual permitted text change', prompt)
        self.assertNotIn('Your only proposed content change is adding', prompt)

    def test_editable_repair_rejects_empty_duplicate_or_unknown_scope(self):
        snapshot, attachments = fixture()
        snapshot['prior_feedback'] = {'proposal': normalized_proposal(snapshot['input'])}
        for invalid in ([], 'result-a', ['unknown'], ['result-a', 'result-a'], [None]):
            with self.subTest(editable=invalid), self.assertRaises(PalimpsestError) as caught:
                citation_repair({**snapshot, 'editable_item_keys': invalid}, attachments)
            self.assertEqual(caught.exception.code, 'invalid_wiki_citation_repair_context')


if __name__ == '__main__':
    unittest.main()
