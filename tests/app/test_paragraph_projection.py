"""Cross-page reading joins must retain source pages and uncertain matches."""
from copy import deepcopy
import unittest

from palimpsest.paragraph_projection import build_paragraphs, select_evidence_context
from palimpsest.pdf_raster_adapter import ADAPTER_VERSION, map_to_original


class ParagraphProjectionTests(unittest.TestCase):
    def fixture(self):
        first = {'type': 'text', 'bbox': [10, 10, 40, 20], 'content': 'First'}
        second = {'type': 'text', 'bbox': [10, 30, 40, 40], 'content': 'Next'}
        def block(span):
            return {'type': 'text', 'bbox': span['bbox'], 'lines': [{'spans': [span]}]}
        middle = {'pdf_info': [
            {'page_idx': 0, 'preproc_blocks': [block(first)], 'para_blocks':
                [{'type': 'text', 'lines': [{'spans': [deepcopy(first), {**second, 'cross_page': True}]}]}]},
            {'page_idx': 1, 'preproc_blocks': [block(second)], 'para_blocks': []}]}
        bundle = {'data_id': 'a' * 64, 'block_collection': 'preproc_blocks', 'blocks': []}
        for page, span in enumerate((first, second)):
            pointer = f'/pdf_info/{page}/preproc_blocks/0'
            bundle['blocks'].append({'block_id': pointer, 'page_index': page,
                'segments': [{'raw_locator': pointer + '/lines/0/spans/0', **span}]})
        return middle, bundle

    def test_join_maps_to_original_pages_without_mutation(self):
        middle, bundle = self.fixture()
        before = deepcopy((middle, bundle))
        result = build_paragraphs(middle, bundle)
        paragraph = result['paragraphs'][0]
        self.assertEqual(paragraph['source_pages'], [0, 1])
        self.assertTrue(paragraph['cross_page'])
        self.assertEqual(paragraph['text'], 'First\nNext')
        self.assertEqual(paragraph['segments'][1]['page_index'], 1)
        self.assertEqual(paragraph['segments'][1]['char_start'], 6)
        self.assertEqual(result['matched_source_segment_count'], 2)
        self.assertEqual((middle, bundle), before)
        self.assertEqual(build_paragraphs(middle, bundle), result)

    def test_ambiguous_cross_page_occurrence_never_guesses(self):
        middle, bundle = self.fixture()
        other = deepcopy(middle['pdf_info'][1])
        other['page_idx'] = 2
        middle['pdf_info'].append(other)
        source = deepcopy(bundle['blocks'][1])
        source['page_index'] = 2
        source['block_id'] = source['block_id'].replace('/1/', '/2/')
        source['segments'][0]['raw_locator'] = source['segments'][0]['raw_locator'].replace('/1/', '/2/')
        bundle['blocks'].append(source)
        result = build_paragraphs(middle, bundle)
        segment = result['paragraphs'][0]['segments'][1]
        self.assertEqual(segment['match_status'], 'ambiguous')
        self.assertNotIn('page_index', segment)
        self.assertEqual(len(segment['possible_source_refs']), 2)
        self.assertFalse(result['paragraphs'][0]['source_mapping_complete'])

    def test_changed_transcription_is_unmatched_not_replaced(self):
        middle, bundle = self.fixture()
        middle['pdf_info'][0]['para_blocks'][0]['lines'][0]['spans'][1]['content'] = 'Changed'
        result = build_paragraphs(middle, bundle)
        segment = result['paragraphs'][0]['segments'][1]
        self.assertEqual(segment['match_status'], 'unmatched')
        self.assertEqual(segment['parser_text'], 'Changed')
        self.assertNotIn('raw_locator', segment)

    def test_image_cross_page_paragraphs_keep_ocr_and_original_geometry_with_raw_boxes(self):
        middle, bundle = self.fixture()
        bundle.update(profile={'adapter_version':ADAPTER_VERSION}, coordinate_system='pdf_points_top_left',
                      pages=[{'page_index':i, 'page_size':[600,800]} for i in range(2)])
        for block in bundle['blocks']:
            block.update(page_size=[600,800], bbox=deepcopy(block['segments'][0]['bbox']),
                         children=[], line_regions=[], grounding_regions=[], anchor_sha256='b'*64)
        manifest = {'source':{'data_id':bundle['data_id'], 'page_count':2}, 'pages':[{
            'source_page_index':i, 'derived_page_index':i,
            'source_geometry':{'size':[599.76,799.9], 'rotation':0,
                              'effective_bbox':[10,20,609.76,819.9], 'crop_box':[9,19,611,821]},
            'derived_geometry':{'size':[600.28,800.16], 'rotation':0}} for i in range(2)]}
        mapped = map_to_original(bundle, manifest, manifest_sha256='c'*64)
        before = deepcopy((middle, bundle, mapped))
        result = build_paragraphs(middle, mapped)
        paragraph = result['paragraphs'][0]
        self.assertEqual(paragraph['text'], 'First\nNext')
        self.assertNotIn('selected_text', paragraph)
        self.assertEqual(paragraph['source_pages'], [0,1])
        self.assertTrue(paragraph['source_mapping_complete'])
        for page, segment in enumerate(paragraph['segments']):
            source = mapped['blocks'][page]['segments'][0]
            self.assertEqual(segment['page_index'], page)
            self.assertEqual(segment['raw_locator'], source['raw_locator'])
            self.assertEqual(segment['bbox'], source['bbox'])
            self.assertNotEqual(segment['bbox'], segment['raw_bbox'])
            self.assertEqual(segment['raw_bbox'], bundle['blocks'][page]['segments'][0]['bbox'])
            self.assertEqual(segment['coordinate_transform'], mapped['pages'][page]['coordinate_transform'])
            self.assertEqual(paragraph['text'][segment['char_start']:segment['char_end']], segment['source_text'])
        self.assertEqual(result['matched_source_segment_count'], 2)
        self.assertEqual((middle, bundle, mapped), before)
        self.assertEqual(build_paragraphs(middle, mapped), result)

    def test_context_resolves_copied_asset_without_rewriting_raw_path(self):
        source = {'path': 'images/source.jpg', 'sha256': 'b' * 64}
        copied = {'path': 'panels/p-original.jpg', 'sha256': 'b' * 64}
        evidence = {'manifest_sha256': 'c' * 64, 'asset_base_directory': '/evidence/visuals',
            'source_bundle': {'data_id': 'a' * 64, 'pages': [{'page_index': 0}], 'blocks': []},
            'text_analysis': {'heading_candidates': [], 'discrepancies': []},
            'paragraphs': {'paragraphs': [{'source_pages': [0], 'segments': [{'source_asset': source}]}]},
            'visuals': {'pages': [], 'figures': [], 'panels': [{'page_index': 0, 'parser_asset':
                        {'original_path': source['path'], 'sha256': source['sha256'], 'copied_asset': copied}}]}}
        result = select_evidence_context(evidence, 1)
        self.assertEqual(result['paragraphs'][0]['segments'][0]['source_asset'], source)
        self.assertEqual(result['paragraphs'][0]['segments'][0]['display_asset'], copied)
        self.assertNotIn('display_asset', evidence['paragraphs']['paragraphs'][0]['segments'][0])
        self.assertNotIn('rendered_source_pages', result)

    def test_image_context_exposes_original_200dpi_pngs_for_only_neighbor_pages(self):
        pages = [{'page_index':i, 'source_page_image':{
            'path':f'raster/page-{i+1:04d}.png', 'sha256':str(i+1)*64,
            'bytes':2000+i, 'pixel_size':[1667,2223], 'mode':'RGB', 'dpi_requested':200, 'dpi_effective':200},
            'coordinate_transform':{'original_page_index':i, 'scale':[0.9996,0.999875]}} for i in range(4)]
        evidence = {'manifest_sha256':'a'*64, 'asset_base_directory':'/evidence/visuals',
            'parser_artifact_base_directory':'/evidence/parser_raw/parser/source/hybrid_ocr',
            'source_bundle':{'data_id':'b'*64, 'profile':{'adapter_version':ADAPTER_VERSION},
                             'pages':pages, 'blocks':[]},
            'paragraphs':{'paragraphs':[]}, 'text_analysis':{'heading_candidates':[], 'discrepancies':[]},
            'visuals':{'panels':[], 'pages':[{'page_index':i, 'page_image':{'path':f'page-{i}.png'}}
                                          for i in range(4)], 'figures':[]}}
        before = deepcopy(evidence)
        result = select_evidence_context(evidence, 2)
        self.assertEqual(result['page_indices'], [0,1,2])
        self.assertEqual(result['rendered_source_pages'], [{'page_index':p['page_index'],
            'page_image':p['source_page_image'], 'coordinate_transform':p['coordinate_transform']} for p in pages[:3]])
        self.assertEqual(result['preferred_page_image_collection'], 'rendered_source_pages')
        self.assertEqual(result['parser_artifact_base_directory'], evidence['parser_artifact_base_directory'])
        self.assertEqual(result['asset_base_directory'], '/evidence/visuals')
        self.assertEqual([p['page_index'] for p in result['page_images']], [0,1,2])
        self.assertNotIn('transcription_selection', result)
        self.assertEqual(result['semantic_llm_calls'], 0)
        self.assertEqual(select_evidence_context(evidence, 2), result)
        result['rendered_source_pages'][0]['page_image']['path'] = 'changed.png'
        result['rendered_source_pages'][0]['coordinate_transform']['scale'][0] = 2
        self.assertEqual(evidence, before)

    def dual_fixture(self):
        middle, bundle = self.fixture()
        for page, (native, selected, interval) in enumerate((
                ('1 mg/ml', '1 μg/ml', [2, 3]), ('cm2', 'cm<sup>2</sup>', [2, 3]))):
            span = middle['pdf_info'][page]['preproc_blocks'][0]['lines'][0]['spans'][0]
            span['content'] = native
            middle['pdf_info'][0]['para_blocks'][0]['lines'][0]['spans'][page]['content'] = native
            block = bundle['blocks'][page]
            block['segments'][0]['content'] = native
            ref = {'raw_locator':block['segments'][0]['raw_locator'], 'field_locator':block['segments'][0]['raw_locator']+'/content',
                   'page_index':page, 'bbox':span['bbox'], 'character_range':interval, 'channel':'ocr',
                   'raw_artifact':{'artifact_path':'ocr/middle.json', 'sha256':'c'*64}}
            block.update(text=selected, native_text=native,
                native_raw_artifact={'artifact_path':'source_middle.json', 'sha256':'b'*64},
                transcription_selection={'status':'selected', 'issues':[], 'changes':[{
                    'native_range':interval, 'native_text':native[2:3],
                    'selected_text':'μ' if page == 0 else '<sup>2</sup>', 'ocr_refs':[ref]}]})
        bundle['transcription_selection'] = {'version':'test'}
        return middle, bundle

    def test_selected_cross_page_text_has_separate_offsets_and_exact_ocr_refs(self):
        middle, bundle = self.dual_fixture()
        original = deepcopy((middle, bundle))
        paragraph = build_paragraphs(middle, bundle)['paragraphs'][0]
        self.assertEqual(paragraph['text'], '1 mg/ml\ncm2')
        self.assertEqual(paragraph['selected_text'], '1 μg/ml\ncm<sup>2</sup>')
        self.assertTrue(paragraph['selected_mapping_complete'])
        self.assertEqual(paragraph['source_pages'], [0, 1])
        for segment in paragraph['segments']:
            view = segment['transcription_projection']
            self.assertEqual(paragraph['text'][segment['char_start']:segment['char_end']], segment['parser_text'])
            self.assertEqual(paragraph['selected_text'][view['selected_char_start']:view['selected_char_end']], view['selected_text'])
            self.assertEqual(view['changes'][0]['ocr_refs'][0]['page_index'], segment['page_index'])
            self.assertEqual(view['changes'][0]['ocr_refs'][0]['raw_artifact']['artifact_path'], 'ocr/middle.json')
        self.assertEqual((middle, bundle), original)

    def test_ambiguous_native_range_and_cross_boundary_edits_keep_raw_text(self):
        for text, interval, issue in [('1 mg/ml 1 mg/ml', [2,3], 'native_segment_range_not_unique'),
                                    ('x1 mg/ml', [0,2], 'selection_crosses_segment_boundary')]:
            middle, bundle = self.dual_fixture()
            block = bundle['blocks'][0]
            block['native_text'] = text
            block['transcription_selection']['changes'][0]['native_range'] = interval
            paragraph = build_paragraphs(middle, bundle)['paragraphs'][0]
            projection = paragraph['segments'][0]['transcription_projection']
            self.assertEqual(projection['selected_text'], '1 mg/ml')
            self.assertEqual(projection['issue'], issue)
            self.assertEqual(projection['changes'], [])
            self.assertFalse(paragraph['selected_mapping_complete'])

    def test_unmatched_paragraph_content_is_visible_and_flagged_in_selected_view(self):
        middle, bundle = self.dual_fixture()
        middle['pdf_info'][0]['para_blocks'][0]['lines'][0]['spans'][1]['content'] = 'Changed'
        paragraph = build_paragraphs(middle, bundle)['paragraphs'][0]
        self.assertEqual(paragraph['selected_text'], '1 μg/ml\nChanged')
        self.assertEqual(paragraph['segments'][1]['transcription_projection']['issue'], 'source_segment_not_unique')
        self.assertFalse(paragraph['selected_mapping_complete'])

    def test_dual_context_filters_ocr_evidence_and_retains_asset_base(self):
        rows = [{'block_id':f'/b/{i}', 'page_index':i} for i in range(4)]
        evidence = {'manifest_sha256':'a'*64, 'parser_artifact_base_directory':'/evidence/parser_raw/native',
            'source_bundle':{'data_id':'b'*64, 'pages':[{'page_index':i} for i in range(4)], 'blocks':rows,
                'ocr_bundle':{'blocks':rows}, 'transcription_selection':{'blocks':rows, 'unresolved':rows,
                    'unmatched_ocr_blocks':rows, 'unmatched_ocr_block_ids':[r['block_id'] for r in rows]}},
            'paragraphs':{'paragraphs':[]}, 'text_analysis':{'heading_candidates':[], 'discrepancies':[]},
            'visuals':{'panels':[], 'pages':[], 'figures':[]}}
        result = select_evidence_context(evidence, 1)
        self.assertEqual(result['page_indices'], [0, 1])
        self.assertEqual([b['page_index'] for b in result['ocr_source_blocks']], [0, 1])
        self.assertEqual(result['transcription_selection']['unmatched_ocr_block_ids'], ['/b/0', '/b/1'])
        self.assertEqual(result['parser_artifact_base_directory'], '/evidence/parser_raw/native')
        self.assertNotIn('rendered_source_pages', result)
        result['ocr_source_blocks'][0]['page_index'] = 99
        self.assertEqual(rows[0]['page_index'], 0)
