"""Generic source-address review contracts; no parser, model, database or I write."""

from copy import deepcopy
from hashlib import sha256
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.source_review import (build_manifest, extend_generation, extend_validation,
                                     normalize_generation, validate_decisions)


def uid(number):
    return f'019947e2-1234-7000-8000-{number:012x}'


def packet(text='A source states one fact. Another fact is distinct.', *, number=1, media=False):
    block, anchor = '/source/block', sha256(text.encode()).hexdigest()
    unit = {'information_id': uid(number), 'content': text,
        'source_refs': [{'block_id': block, 'raw_locator': block, 'anchor_sha256': anchor, 'page_index': None}],
        'source_assembly': {'content_segments': [{'source_block_id': block, 'raw_locator': block,
            'anchor_sha256': anchor, 'page_index': None, 'char_start': 0, 'char_end': len(text),
            'source_char_range': [0, len(text)], 'text_origin': 'registered_source'}]},
        'media': [{'source_block_id': block, 'sha256': 'a' * 64}] if media else []}
    return {'data_id': str(number) * 64, 'source_execution_id': uid(100 + number),
            'model_input': {'information': [unit]}}


def generation(manifest, *, selected=True):
    reviews, candidates = [], []
    for index, target in enumerate(manifest['targets']):
        key = f'fact{index}'
        if target['char_ranges']:
            start, end = target['char_ranges'][0]
            anchor = {'char_start': start, 'char_end': end, 'media_sha256': None}
        elif target['media_sha256s']:
            anchor = {'char_start': None, 'char_end': None, 'media_sha256': target['media_sha256s'][0]}
        else:
            anchor = None
        disposition = ('selected' if selected and anchor else
                       'needs_review' if target['mapping_status'] == 'unmapped' else 'context_only')
        item = {'item_key': key, 'label': 'A source-addressed item', 'disposition': disposition,
            'candidate_keys': [key] if disposition == 'selected' else [], 'anchors': [anchor] if anchor else [],
            'reason': 'Model review fixture; no semantic evaluation was run.'}
        reviews.append({'target_id': target['target_id'], 'items': [item]})
        if disposition == 'selected':
            candidates.append({'candidate_key': key, 'evidence': [{
                'information_id': target['information_id'], 'data_id': target['data_id'],
                'source_execution_id': target['source_execution_id'], **anchor}]})
    return {'source_reviews': reviews, 'complete': not any(
        item['disposition'] == 'needs_review' for row in reviews for item in row['items'])}, candidates


def decisions(manifest, reviews):
    return {'source_review_decisions': {
        'targets': [{'target_id': t['target_id'], 'verdict': 'confirmed', 'reason': 'Independent target review.'}
                    for t in manifest['targets']],
        'items': [{'item_key': item['item_key'], 'verdict': 'confirmed', 'reason': 'Independent item review.'}
                  for row in reviews for item in row['items']]}}


class SourceReviewTests(unittest.TestCase):
    def reject(self, fn):
        with self.assertRaises(PalimpsestError):
            fn()

    def test_generic_text_formats_preserve_exact_addresses_without_semantic_splitting(self):
        for text in ('PDF caption (A) and (B).', '# Markdown\r\nFirst fact. Second fact.\r\n',
                     '<article><p>A</p><p>B</p></article>', 'def f(x):\n    return x + 1\n',
                     '😀 Cafe\u0301. CR\rLF\n'):
            with self.subTest(text=text):
                source = packet(text)
                before = deepcopy(source)
                manifest = build_manifest(source)
                self.assertEqual(build_manifest(source), manifest)
                self.assertEqual(len(manifest['targets']), 1)
                self.assertEqual(manifest['targets'][0]['char_ranges'], [[0, len(text)]])
                self.assertEqual(manifest['targets'][0]['source_refs'], source['model_input']['information'][0]['source_refs'])
                response, candidates = generation(manifest)
                self.assertEqual(len(normalize_generation(response, manifest, candidates)), 1)
                self.assertEqual(source, before)

    def test_same_block_and_media_in_two_data_keep_distinct_ownership(self):
        first, second = packet(media=True), packet(number=2, media=True)
        sources = [first, second]
        bundle = {'sources': sources, 'model_input': {'information': [
            {**s['model_input']['information'][0], 'data_id': s['data_id'], 'source_execution_id': s['source_execution_id']}
            for s in sources]}}
        manifest = build_manifest(bundle)
        self.assertEqual(len({t['target_id'] for t in manifest['targets']}), 2)
        self.assertEqual([t['data_id'] for t in manifest['targets']], ['1' * 64, '2' * 64])
        response, candidates = generation(manifest)
        candidates[0]['evidence'][0]['data_id'] = '2' * 64
        self.reject(lambda: normalize_generation(response, manifest, candidates))
        bundle['model_input']['information'][0]['data_id'] = '2' * 64
        self.reject(lambda: build_manifest(bundle))

    def test_each_retained_block_is_reviewed_even_without_a_candidate(self):
        source = packet()
        source['model_input']['information'][0]['source_refs'].append({'block_id': '/unmapped', 'raw_locator': '/unmapped'})
        manifest = build_manifest(source)
        self.assertEqual(len(manifest['targets']), 2)
        self.assertEqual(manifest['targets'][1]['mapping_status'], 'unmapped')
        response, candidates = generation(manifest)
        self.assertFalse(response['complete'])
        normalize_generation(response, manifest, candidates)
        response['source_reviews'].pop()
        self.reject(lambda: normalize_generation(response, manifest, candidates))

    def test_no_refs_fallback_and_empty_source_do_not_invent_source_locations(self):
        source = packet('legacy content')
        source['model_input']['information'][0]['source_refs'] = []
        target = build_manifest(source)['targets'][0]
        self.assertIsNone(target['source_block_id'])
        self.assertEqual(target['source_refs'], [])
        self.assertEqual(target['mapping_status'], 'information_only')
        self.assertEqual(target['char_ranges'], [[0, len('legacy content')]])
        manifest = build_manifest(packet(''))
        response, candidates = generation(manifest)
        self.assertEqual(manifest['targets'][0]['mapping_status'], 'empty')
        self.assertEqual(candidates, [])
        normalize_generation(response, manifest, candidates)

    def test_model_can_subdivide_one_target_without_one_candidate_per_I(self):
        manifest = build_manifest(packet('First. Second.'))
        response, candidates = generation(manifest)
        first = response['source_reviews'][0]['items'][0]
        first['anchors'][0]['char_end'] = 6
        second = deepcopy(first)
        second.update(item_key='second', label='Second explicit item')
        second['anchors'] = [{'char_start': 7, 'char_end': 14, 'media_sha256': None}]
        response['source_reviews'][0]['items'].append(second)
        normalized = normalize_generation(response, manifest, candidates)
        self.assertEqual(len(normalized[0]['items']), 2)
        response['source_reviews'][0]['items'][1]['item_key'] = first['item_key']
        self.reject(lambda: normalize_generation(response, manifest, candidates))

    def test_anchor_requires_exact_range_owned_media_and_supported_candidate(self):
        manifest = build_manifest(packet('😀 abc', media=True))
        baseline, candidates = generation(manifest)
        for mutation in ('outside', 'boolean', 'wrong_media', 'missing_anchor', 'unknown_candidate', 'cross_I'):
            response, changed = deepcopy((baseline, candidates))
            item = response['source_reviews'][0]['items'][0]
            if mutation == 'outside': item['anchors'][0]['char_end'] = 100
            if mutation == 'boolean': item['anchors'][0]['char_start'] = False
            if mutation == 'wrong_media': item['anchors'] = [{'char_start': None, 'char_end': None, 'media_sha256': 'b' * 64}]
            if mutation == 'missing_anchor': item['anchors'] = []
            if mutation == 'unknown_candidate': item['candidate_keys'] = ['unknown']
            if mutation == 'cross_I': changed[0]['evidence'][0]['information_id'] = uid(2)
            with self.subTest(mutation=mutation): self.reject(lambda: normalize_generation(response, manifest, changed))
        changed = deepcopy(candidates)
        changed[0]['evidence'][0]['char_end'] = 2
        self.reject(lambda: normalize_generation(baseline, manifest, changed))

    def test_image_only_target_requires_actual_owned_media_citation(self):
        manifest = build_manifest(packet('', media=True))
        response, candidates = generation(manifest)
        normalize_generation(response, manifest, candidates)
        candidates[0]['evidence'][0]['media_sha256'] = 'b' * 64
        self.reject(lambda: normalize_generation(response, manifest, candidates))

    def test_every_candidate_and_each_cited_source_modality_has_a_review_link(self):
        manifest = build_manifest(packet(media=True))
        response, candidates = generation(manifest, selected=False)
        unused_response, emitted = generation(manifest)
        self.reject(lambda: normalize_generation(response, manifest, emitted))
        response, candidates = generation(manifest)
        candidates[0]['evidence'][0]['media_sha256'] = 'a' * 64
        self.reject(lambda: normalize_generation(response, manifest, candidates))
        response['source_reviews'][0]['items'][0]['anchors'].append({
            'char_start': None, 'char_end': None, 'media_sha256': 'a' * 64})
        normalize_generation(response, manifest, candidates)
        sources = [packet(), packet(number=2)]
        bundle = {'sources': sources, 'model_input': {'information': [
            {**s['model_input']['information'][0], 'data_id': s['data_id'], 'source_execution_id': s['source_execution_id']}
            for s in sources]}}
        manifest = build_manifest(bundle)
        response, candidates = generation(manifest)
        candidates[0]['evidence'].extend(candidates[1]['evidence'])
        self.reject(lambda: normalize_generation(response, manifest, candidates))
        response['source_reviews'][1]['items'][0]['candidate_keys'].append('fact0')
        normalize_generation(response, manifest, candidates)

    def test_validator_semantic_gap_and_rejected_candidate_keep_coverage_pending(self):
        manifest = build_manifest(packet())
        response, candidates = generation(manifest)
        reviews = normalize_generation(response, manifest, candidates)
        validation = decisions(manifest, reviews)
        accepted = {'fact0': {'verdict': 'accepted'}}
        self.assertEqual(validate_decisions(validation, manifest, reviews, accepted)['pending_target_ids'], [])
        validation['source_review_decisions']['targets'][0].update(verdict='needs_review', reason='A distinct source fact was omitted.')
        checked = validate_decisions(validation, manifest, reviews, accepted)
        self.assertEqual(checked['pending_target_ids'], [manifest['targets'][0]['target_id']])
        validation = decisions(manifest, reviews)
        for verdict in ('rejected', 'needs_human'):
            checked = validate_decisions(validation, manifest, reviews, {'fact0': {'verdict': verdict}})
            self.assertEqual(checked['pending_item_keys'], ['fact0'])
        response['source_reviews'][0]['items'][0]['disposition'] = 'needs_review'
        self.reject(lambda: normalize_generation(response, manifest, candidates))

    def test_schema_extensions_are_additive_and_frozen_manifest_is_checked(self):
        base = {'type': 'object', 'properties': {'complete': {'type': 'boolean'}}, 'required': ['complete']}
        before = deepcopy(base)
        manifest = build_manifest(packet())
        response, candidates = generation(manifest)
        reviews = normalize_generation(response, manifest, candidates)
        self.assertIn('source_reviews', extend_generation(base, manifest)['required'])
        self.assertIn('source_review_decisions', extend_validation(base, manifest, reviews)['required'])
        self.assertEqual(base, before)
        changed = deepcopy(manifest)
        changed['targets'][0]['char_ranges'][0][1] = 999
        self.reject(lambda: extend_generation(base, changed))
        validation = decisions(manifest, reviews)
        validation['source_review_decisions']['items'] = []
        self.reject(lambda: validate_decisions(validation, manifest, reviews, {'fact0': {'verdict': 'accepted'}}))


if __name__ == '__main__':
    unittest.main()
