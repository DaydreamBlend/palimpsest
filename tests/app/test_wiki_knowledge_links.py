"""Shared source evidence is navigation, not a semantic support verdict."""

from copy import deepcopy
from hashlib import sha256
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.wiki_knowledge_links import build_related_links


def uid(number):
    return f'00000000-0000-7000-8000-{number:012x}'


def fixtures():
    source = '1' * 64
    evidence = {'data_id': source, 'information_id': uid(1),
        'char_start': 10, 'char_end': 20, 'quote': 'A μm café.', 'media_sha256': None}
    paper = {'kind': 'paper', 'snapshot_id': uid(2), 'page_id': uid(3), 'data_id': source,
        'items': [{'item_key': 'test-result', 'text': 'A fixture sentence.', 'evidence': [evidence]}]}
    node = {'knode_id': uid(4), 'knode_revision_id': uid(5), 'current_revision_id': uid(5),
        'content_fingerprint': '2' * 64, 'statement': 'A different fixture sentence.',
        'identity_scope': None, 'semantic_payload': {'scope': 'synthetic experiment'}}
    graph = {'schema_version': 'knowledge-graph-v1', 'state_version': 7,
        'nodes': [node], 'groundings': [{**deepcopy(evidence), 'grounding_id': uid(6), 'node_revision_id': uid(5)}]}
    return [paper], graph


class WikiKnowledgeLinkTests(unittest.TestCase):
    def test_exact_unicode_range_is_navigation_and_preserves_unknown_origin(self):
        papers, graph = fixtures()
        before = deepcopy((papers, graph))
        links = build_related_links(papers, graph)
        self.assertEqual(len(links), 1)
        link = links[0]
        self.assertEqual(link['relation'], 'shared_source_evidence')
        self.assertIs(link['semantic_support_validated'], False)
        self.assertIs(link['review_required'], False)
        self.assertEqual(link['match_kind'], 'exact_text_range')
        self.assertEqual(link['matches'][0]['quote'], 'A μm café.')
        self.assertEqual(link['matches'][0]['quote_sha256'], sha256('A μm café.'.encode()).hexdigest())
        self.assertEqual(link['node_snapshot'], graph['nodes'][0])
        self.assertNotIn('generation_origin', link['node_snapshot'])
        self.assertEqual(link['link_sha256'], digest({k: v for k, v in link.items() if k != 'link_sha256'}))
        self.assertEqual((papers, graph), before)
        link['node_snapshot']['semantic_payload']['scope'] = 'changed output'
        self.assertEqual((papers, graph), before)

    def test_partial_overlap_preserves_exact_substring_and_offsets(self):
        papers, graph = fixtures()
        graph['groundings'][0].update(char_start=12, char_end=23, quote='μm café.+++')
        match = build_related_links(papers, graph)[0]['matches'][0]
        self.assertEqual((match['overlap_start'], match['overlap_end'], match['quote']), (12, 20, 'μm café.'))
        self.assertEqual(match['match_kind'], 'overlapping_text_range')

    def test_same_topic_or_text_without_same_source_is_not_a_link(self):
        for field, value in [('information_id', uid(99)), ('data_id', '9' * 64)]:
            papers, graph = fixtures()
            graph['groundings'][0][field] = value
            self.assertEqual(build_related_links(papers, graph), [])

    def test_disjoint_adjacent_and_empty_text_do_not_match(self):
        for start, end, quote in [(20, 30, 'A μm café.'), (50, 60, 'A μm café.'), (10, 10, '')]:
            papers, graph = fixtures()
            graph['groundings'][0].update(char_start=start, char_end=end, quote=quote)
            self.assertEqual(build_related_links(papers, graph), [])

    def test_same_owned_image_works_without_text_overlap(self):
        papers, graph = fixtures()
        papers[0]['items'][0]['evidence'][0].update(char_start=0, char_end=0, quote='', media_sha256='a' * 64)
        graph['groundings'][0].update(media_sha256='a' * 64)
        match = build_related_links(papers, graph)[0]['matches'][0]
        self.assertEqual(match['match_kind'], 'shared_image')
        self.assertEqual((match['overlap_start'], match['overlap_end'], match['quote']), (None, None, ''))
        graph['groundings'][0]['information_id'] = uid(99)
        self.assertEqual(build_related_links(papers, graph), [])

    def test_source_page_label_is_not_text_evidence_but_owned_image_can_match(self):
        papers, graph = fixtures()
        evidence = papers[0]['items'][0]['evidence'][0]
        evidence['source_refs'] = [{'source_collection': 'original_page_facsimile'}]
        self.assertEqual(build_related_links(papers, graph), [])
        evidence['media_sha256'] = graph['groundings'][0]['media_sha256'] = 'a' * 64
        self.assertEqual(build_related_links(papers, graph)[0]['match_kind'], 'shared_image')

    def test_corrupt_overlap_is_rejected_even_when_image_matches(self):
        papers, graph = fixtures()
        graph['groundings'][0]['quote'] = 'B μm café.'
        papers[0]['items'][0]['evidence'][0]['media_sha256'] = 'a' * 64
        graph['groundings'][0]['media_sha256'] = 'a' * 64
        with self.assertRaises(PalimpsestError):
            build_related_links(papers, graph)

    def test_invalid_ranges_quotes_and_source_owner_are_rejected(self):
        for field, value in [('char_start', -1), ('char_start', True), ('char_end', 19),
                             ('quote', 'tampered'), ('quote', 42), ('media_sha256', 'not a hash')]:
            for side in ('paper', 'graph'):
                papers, graph = fixtures()
                target = papers[0]['items'][0]['evidence'][0] if side == 'paper' else graph['groundings'][0]
                target[field] = value
                with self.subTest(side=side, field=field, value=value), self.assertRaises(PalimpsestError):
                    build_related_links(papers, graph)
        papers, graph = fixtures()
        papers[0]['items'][0]['evidence'][0]['data_id'] = '9' * 64
        with self.assertRaises(PalimpsestError):
            build_related_links(papers, graph)

    def test_historical_groundings_are_excluded_and_inconsistent_current_nodes_fail(self):
        papers, graph = fixtures()
        graph['groundings'].append({**graph['groundings'][0], 'node_revision_id': uid(99), 'quote': 'old bytes'})
        self.assertEqual(len(build_related_links(papers, graph)[0]['matches']), 1)
        graph['nodes'][0]['current_revision_id'] = uid(99)
        with self.assertRaises(PalimpsestError):
            build_related_links(papers, graph)

    def test_multiple_matches_group_by_revision_and_order_deterministically(self):
        papers, graph = fixtures()
        graph['groundings'].append({**graph['groundings'][0], 'grounding_id': uid(7)})
        graph['nodes'].append({**deepcopy(graph['nodes'][0]), 'knode_id': uid(8),
            'knode_revision_id': uid(9), 'current_revision_id': uid(9)})
        graph['groundings'].append({**graph['groundings'][0], 'grounding_id': uid(10), 'node_revision_id': uid(9)})
        expected = build_related_links(papers, graph)
        graph['nodes'].reverse()
        graph['groundings'].reverse()
        self.assertEqual(build_related_links(papers, graph), expected)
        self.assertEqual(len(expected), 2)
        self.assertEqual([m['grounding_id'] for m in expected[0]['matches']], [uid(6), uid(7)])

    def test_annotations_are_copied_only_to_their_revision_without_altering_truth_status(self):
        papers, graph = fixtures()
        annotations = [{'node_revision_id': uid(5), 'knode_id': uid(4),
                        'reason': 'Synthetic source issue', 'metadata': {'unresolved': True}},
                       {'node_revision_id': uid(99), 'reason': 'Historical issue'}]
        before = deepcopy(annotations)
        link = build_related_links(papers, graph, annotations)[0]
        self.assertEqual(link['review_annotations'], [annotations[0]])
        self.assertTrue(link['review_required'])
        self.assertFalse(link['semantic_support_validated'])
        link['review_annotations'][0]['metadata']['unresolved'] = False
        self.assertEqual(annotations, before)
        annotations[0]['knode_id'] = uid(99)
        with self.assertRaises(PalimpsestError):
            build_related_links(papers, graph, annotations)

    def test_duplicate_snapshot_item_node_or_grounding_is_rejected(self):
        for duplicate in ('snapshot', 'item', 'node', 'grounding'):
            papers, graph = fixtures()
            collection = {'snapshot': papers, 'item': papers[0]['items'],
                          'node': graph['nodes'], 'grounding': graph['groundings']}[duplicate]
            collection.append(deepcopy(collection[0]))
            with self.subTest(duplicate=duplicate), self.assertRaises(PalimpsestError):
                build_related_links(papers, graph)


if __name__ == '__main__':
    unittest.main()
