"""Whole-source reading plans keep context proposals separate from authority."""

from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from palimpsest.cli import main
from palimpsest.errors import PalimpsestError
from palimpsest.paragraph_projection import digest
from palimpsest.section_projection import build_sections, document_context, section_context as read_section_context


def section_context(source, identifier, *, canonical_pages=None):
    view = build_sections(source, canonical_pages=canonical_pages)
    return read_section_context(source, identifier, canonical_pages=canonical_pages,
                                expected_projection_sha256=view['projection_sha256'])


def block(ref, page, index, text, kind='text'):
    return {'block_id': ref, 'page_index': page, 'type': kind, 'text': text,
            'bbox': [10, 20, 200, 100], 'raw_locator': ref,
            'anchor_sha256': digest(ref), 'upstream_metadata': {'index': index},
            'source_collection': 'preproc_blocks', 'segments': [], 'children': []}


def evidence():
    blocks = [block('/h', 0, 0, 'PRIVATE HEADER', 'header'),
              block('/title', 0, 1, 'Paper title', 'title'),
              block('/abstract', 0, 2, 'Actual abstract without a heading.\r\n'),
              block('/significance', 0, 3, 'Significance', 'title'),
              block('/sig-body', 0, 4, 'A significance paragraph.'),
              block('/intro', 0, 5, 'Introduction', 'title'),
              block('/intro-body', 0, 6, '  Introduction Cafe\u0301 μ\n'),
              block('/results', 1, 0, 'Results', 'title'),
              block('/sub', 1, 1, 'First result', 'title'),
              block('/result-body', 1, 2, 'See Figs. 1 and 2. Additional text.'),
              block('/ref', 2, 0, 'References', 'title'),
              block('/f1', 2, 1, 'Fig. 1. First figure caption.'),
              block('/f2', 2, 2, 'Figure 2. Second figure caption.'),
              block('/f1-tail', 3, 0, 'Fig. 1 (continued) Further explanation.'),
              block('/img', 3, 1, '', 'image')]
    bundle = {'schema_version': 1, 'data_id': 'a' * 64,
              'coordinate_system': 'pdf_points_top_left', 'profile': {'adapter_version': 'image-test'},
              'pages': [{'page_index': p, 'page_size': [600, 800],
                         'source_page_image': {'path': f'page-{p}.png', 'sha256': digest(p)},
                         'coordinate_transform': {'scale': [1, 1]}} for p in range(4)],
              'blocks': blocks}
    return {'source_bundle': bundle, 'manifest_sha256': 'b' * 64,
            'text_analysis': {'heading_candidates': [], 'discrepancies': []},
            'paragraphs': {'paragraphs': []},
            'visuals': {'pages': [], 'panels': [], 'figures': []},
            'asset_base_directory': '/evidence/visuals',
            'parser_artifact_base_directory': '/evidence/parser_raw'}


class SectionProjectionTests(unittest.TestCase):
    def test_exact_source_coverage_text_offsets_no_mutation_and_repeatability(self):
        source = evidence()
        before = deepcopy(source)
        view = build_sections(source)
        self.assertEqual(view, build_sections(source))
        self.assertEqual(source, before)
        source_blocks = {b['block_id']: b for b in source['source_bundle']['blocks']}
        refs = [ref for g in view['sections'] for ref in g['source_block_ids']]
        self.assertCountEqual(refs, source_blocks)
        self.assertEqual(len(refs), len(set(refs)))
        for group in view['sections']:
            for span in group['spans']:
                self.assertEqual(group['text'][span['char_start']:span['char_end']],
                                 source_blocks[span['source_block_id']]['text'])
        self.assertEqual(view['canonical_information_binding'], 'not_requested')
        self.assertNotIn('execution_id', view)
        self.assertFalse(view['semantic_revision'])
        self.assertEqual(view['semantic_llm_calls'], 0)
        self.assertEqual(view['coverage']['actual_model_delivery'], 'not_performed')
        self.assertEqual(view['projection_sha256'], digest({k: v for k, v in view.items() if k != 'projection_sha256'}))

    def test_unlabeled_abstract_and_significance_remain_without_forced_reclassification(self):
        view = build_sections(evidence())
        owner = {ref: g for g in view['sections'] for ref in g['source_block_ids']}
        self.assertEqual(owner['/abstract']['role_hint'], 'unclassified')
        self.assertEqual(owner['/sig-body']['role_hint'], 'significance')
        self.assertEqual(owner['/intro-body']['role_hint'], 'introduction')
        self.assertEqual(owner['/result-body']['heading_path'][0]['text'], 'Results')
        self.assertEqual(owner['/results']['section_id'], owner['/sub']['section_id'])

    def test_distant_multiple_figures_and_continuation_have_original_pages_and_images(self):
        source = evidence()
        view = build_sections(source)
        group = next(g for g in view['sections'] if '/result-body' in g['source_block_ids'])
        self.assertEqual(set(group['figure_keys']), {'main:1', 'main:2'})
        context = section_context(source, group['section_id'])
        self.assertTrue({'/f1', '/f2', '/f1-tail'} <= set(context['context_source_block_ids']))
        self.assertTrue({1, 2, 3} <= set(context['page_indices']))
        self.assertEqual(context['page_indices'], [p['page_index'] for p in context['rendered_source_pages']])
        self.assertFalse(set(context['target_source_block_ids']) & set(context['context_source_block_ids']))
        self.assertEqual(context['model_input_status'], 'not_budgeted_or_delivered')

    def test_wrong_visual_caption_number_is_not_authoritative_association(self):
        source = evidence()
        source['visuals']['figures'] = [{'figure_id': 'wrong', 'number': '2',
            'caption_anchors': [{'source_block_id': '/f1', 'raw_locator': '/f1'}]}]
        view = build_sections(source)
        self.assertEqual(view['warnings'][0]['code'], 'visual_caption_number_conflict')
        self.assertTrue(all(not f['visual_proposals'] for f in view['figures']))
        self.assertEqual(view['coverage']['source_block_count'], len(source['source_bundle']['blocks']))

    def test_incomplete_images_and_paragraphs_are_explicit_not_successful_model_validation(self):
        source = evidence()
        source['source_bundle']['pages'][0].pop('source_page_image')
        source['paragraphs']['paragraphs'] = [{'paragraph_id': 'p', 'source_mapping_complete': False,
            'segments': [{'source_block_id': '/abstract'}, {'possible_source_refs': []}]}]
        context = section_context(source, 'section-1')
        codes = {i['code'] for i in context['unresolved_context']}
        self.assertTrue({'retained_ocr_page_image_unavailable', 'paragraph_source_mapping_incomplete'} <= codes)

    def test_missing_order_duplicate_refs_and_cross_execution_binding_fail(self):
        for change in ('index', 'duplicate', 'pages'):
            with self.subTest(change=change):
                source = evidence()
                if change == 'index':
                    source['source_bundle']['blocks'][0]['upstream_metadata']['index'] = None
                elif change == 'duplicate':
                    source['source_bundle']['blocks'].append(deepcopy(source['source_bundle']['blocks'][0]))
                else:
                    source['source_bundle']['pages'][0]['page_index'] = 10
                with self.assertRaises(PalimpsestError):
                    build_sections(source)
        source = evidence()
        with self.assertRaises(PalimpsestError):
            build_sections(source, canonical_pages={'data_id': 'a' * 64, 'source_bundle_sha256': 'c' * 64})
        with self.assertRaises(PalimpsestError):
            section_context(source, 'section-unknown')

    def test_ambiguous_and_unmatched_paragraphs_remain_visible_with_uncertainty(self):
        source = evidence()
        source['paragraphs']['paragraphs'] = [
            {'paragraph_id': 'ambiguous', 'parser_container_page_index': 3, 'source_mapping_complete': False,
             'segments': [{'possible_source_refs': [{'source_block_id': '/abstract'}, {'source_block_id': '/f1-tail'}]}]},
            {'paragraph_id': 'unmatched', 'parser_container_page_index': 0, 'source_mapping_complete': False,
             'segments': [{'possible_source_refs': []}]}]
        context = section_context(source, 'section-1')
        self.assertEqual({p['paragraph_id'] for p in context['paragraphs']}, {'ambiguous', 'unmatched'})
        self.assertIn('/f1-tail', context['context_source_block_ids'])
        self.assertEqual(len([i for i in context['unresolved_context']
                              if i['code'] == 'paragraph_source_mapping_incomplete']), 2)

    def test_projection_version_and_source_binding_change_digest_not_semantic_revision(self):
        source = evidence()
        view = build_sections(source)
        changed = deepcopy(source)
        changed['manifest_sha256'] = 'd' * 64
        next_view = build_sections(changed)
        self.assertNotEqual(view['projection_sha256'], next_view['projection_sha256'])
        self.assertFalse(next_view['semantic_revision'])
        self.assertEqual(view['sections'], next_view['sections'])

    def test_cli_offline_read_does_not_open_database(self):
        source = evidence()
        for args in (['sections'], ['document-context', '--projection-sha256', build_sections(source)['projection_sha256']],
                     ['section-context', '--section-id', 'section-1',
                                   '--projection-sha256', build_sections(source)['projection_sha256']]):
            with self.subTest(action=args[0]), patch('palimpsest.cli.load_config', side_effect=AssertionError('no DB')):
                with patch('palimpsest.pdf_evidence.read_evidence', return_value=source) as read:
                    output = io.StringIO()
                    with redirect_stdout(output):
                        code = main(['information', *args, '--directory', 'evidence', '--json'])
                    self.assertEqual(code, 0)
                    self.assertEqual(json.loads(output.getvalue())['result']['semantic_llm_calls'], 0)
                    read.assert_called_once_with(Path('evidence'))

    def test_whole_document_text_once_exact_offsets_every_page_and_unknown_caption_tail(self):
        source = evidence()
        source['source_bundle']['blocks'].append(block('/unlabeled-tail', 3, 2, 'continued detail without a number'))
        before = deepcopy(source)
        projection = build_sections(source)
        result = document_context(source, expected_projection_sha256=projection['projection_sha256'])
        refs = {b['block_id']: b for b in source['source_bundle']['blocks']}
        self.assertCountEqual(result['target_source_block_ids'], refs)
        self.assertEqual(len(result['spans']), len(refs))
        for span in result['spans']:
            self.assertEqual(result['text'][span['char_start']:span['char_end']], refs[span['source_block_id']]['text'])
        self.assertEqual(result['page_indices'], [0, 1, 2, 3])
        self.assertEqual(len(result['rendered_source_pages']), 4)
        self.assertEqual(result['text'].count('continued detail without a number'), 1)
        self.assertEqual(result['context_source_block_ids'], [])
        self.assertTrue(all('text' not in g for g in result['section_outline']))
        self.assertEqual(source, before)
        self.assertEqual(result['model_input_status'], 'not_budgeted_or_delivered')
        with self.assertRaises(PalimpsestError):
            document_context(source, expected_projection_sha256='0' * 64)

    def test_stale_group_handle_is_rejected_instead_of_showing_new_content(self):
        source = evidence()
        before = build_sections(source)['projection_sha256']
        source['manifest_sha256'] = 'd' * 64
        for expected in (None, before):
            with self.subTest(expected=expected), self.assertRaises(PalimpsestError) as failure:
                read_section_context(source, 'section-1', expected_projection_sha256=expected)
            self.assertEqual(failure.exception.code, 'section_projection_changed')

    def test_derived_figure_label_is_not_source_text_and_keeps_canonical_mapping(self):
        import test_page_projection as fixtures
        from palimpsest.page_projection import build_pages
        fixture = fixtures.PageProjectionTests()
        fixture.setUp()
        source = evidence()
        source['source_bundle'] = fixture.bundle
        pages = build_pages(fixture.bundle, fixture.rows)
        pages.update(execution_id='execution', profile_id='profile')
        pages['projection_sha256'] = digest({k: v for k, v in pages.items() if k != 'projection_sha256'})
        view = build_sections(source, canonical_pages=pages)
        self.assertNotIn('SYNTHETIC_DISPLAY_LABEL', ''.join(g['text'] for g in view['sections']))
        span = next(s for g in view['sections'] for s in g['spans'] if s['source_block_id'] == '/figures/0')
        self.assertIsNone(span['source_char_range'])
        self.assertEqual(span['information_id'], fixture.figure_id)

    def test_completed_execution_binding_uses_page_view_and_rejects_other_parser_snapshot(self):
        from palimpsest.compiler_runtime import CompilerRuntime
        source = evidence()
        bundle = source['source_bundle']
        pages = {'schema_version': 'source-pages-v1', 'data_id': bundle['data_id'],
                 'source_bundle_sha256': digest(bundle), 'execution_id': 'source-execution', 'profile_id': 'profile',
                 'pages': [{'blocks': [{'block_id': b['block_id'], 'information_id': 'I-' + b['block_id']}
                                      for b in bundle['blocks']]}]}
        pages['projection_sha256'] = digest(pages)
        runtime = object.__new__(CompilerRuntime)
        with patch.object(runtime, 'page_view', return_value=pages) as page_read:
            with patch('palimpsest.pdf_evidence.read_evidence', return_value=source):
                result = runtime.section_view('source-execution', Path('evidence'))
                page_read.assert_called_once_with('source-execution')
        self.assertEqual(result['execution_id'], 'source-execution')
        self.assertTrue(all('information_id' in s for g in result['sections'] for s in g['spans']))
        context = section_context(source, 'section-1', canonical_pages=pages)
        self.assertEqual(set(context['source_information_ids']),
                         set(context['target_source_block_ids']) | set(context['context_source_block_ids']))
        changed = deepcopy(source)
        changed['source_bundle']['profile']['adapter_version'] = 'other-parser'
        with self.assertRaises(PalimpsestError):
            build_sections(changed, canonical_pages=pages)


if __name__ == '__main__':
    unittest.main()
