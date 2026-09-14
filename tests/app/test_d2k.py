"""Standalone D2K pure source-view contracts; no authority, I, DB, or provider."""

from copy import deepcopy
from hashlib import sha256
import json
import math
import unittest
from unittest.mock import patch

from palimpsest import d2k
from palimpsest.errors import PalimpsestError
from palimpsest.i2k_selection import selection_fingerprints
from palimpsest.pdf_raster import _page_metadata


def uid(number):
    return f'019947e2-1234-7000-8000-{number:012x}'


def text_packet(text='\ufeffFirst source statement.\r\nμ 😀 Cafe\u0301.\r\nSecond source statement.\n', *, split=False):
    raw = text.encode('utf-8')
    owner = sha256(raw).hexdigest()
    bounds = [0, text.index('Second')] if split else [0]
    ends = [*bounds[1:], len(text)]
    views = [d2k.text_view(raw, view_id=uid(index + 1), data_id=owner,
        byte_start=len(text[:start].encode('utf-8')), byte_end=len(text[:end].encode('utf-8')))
        for index, (start, end) in enumerate(zip(bounds, ends))]
    return d2k.build_input(owner, media_type='text/plain', original_byte_size=len(raw), views=views)


def pdf_view(number=0):
    geometry = {'media_box': [0, 0, 620, 840], 'crop_box': [5, 11, 618, 832],
        'effective_bbox': [5, 11, 618, 832], 'size': [613, 821], 'rotation': 0,
        'render_box_policy': 'PDFium effective bbox; raw CropBox is retained, not rewritten'}
    pixels = [math.ceil(size * 200 / 72) for size in geometry['size']]
    metadata = _page_metadata(geometry, number, pixels)
    transforms = {key: value for key, value in metadata['transforms'].items() if key in (
        'matrix_convention', 'source_pdf_bottom_left_to_pixel_top_left', 'pixel_top_left_to_source_pdf_bottom_left',
        'source_effective_page_top_left_to_pixel_top_left')}
    image = b'Synthetic pixel descriptor only; not an actual renderer result.'
    return {'kind': 'pdf_page', 'view_id': uid(100 + number), 'data_id': 'a' * 64,
        'original_byte_size': 1234, 'page_index': number, 'page_count': 2, 'page_size': [613, 821],
        'image_sha256': sha256(image).hexdigest(), 'image_byte_size': len(image),
        'source_geometry': geometry, 'transforms': transforms, 'renderer': {
            'schema_version': 'd2k-pdf-renderer-v1', 'engine': 'pypdfium2', 'engine_version': '5.10.1',
            'pillow_version': '12.3.0', 'pdfium_version': 'synthetic-version', 'dpi': 200,
            'long_side_cap_pixels': 3500, 'pixel_mode': 'RGB', 'rotation_policy': 'zero_only',
            'required_image_digest': 'sha256:' + 'b' * 64,
            'implementation_sha256': {'pdf_raster.py': 'c' * 64, 'd2k_pdf.py': 'd' * 64}}}


def pdf_packet():
    return d2k.build_input('a' * 64, media_type='application/pdf', original_byte_size=1234,
                           views=[pdf_view(0), pdf_view(1)])


def response(packet, *, empty=False):
    node = {'candidate_key': 'source-claim', 'kind': 'proposition', 'statement': 'The source explicitly states this fixture fact.',
        'semantic_payload': {'subject': 'Fixture source entity', 'relation': 'has a property', 'object': 'explicit property',
            'polarity': 'positive', 'quantifier': 'source-reported', 'scope': 'fixture only', 'conditions': [], 'time_range': ''},
        'identity_scope': 'source', 'source_data_id': packet['data_id'], 'selection_reason': 'An explicit useful source fact.',
        'claim_basis': 'explicit_source_content', 'is_inferred': False, 'uncertainties': [],
        'direct_evidence': [{'view_id': view['view_id'], 'source_role': 'other',
            **({'char_start': 0, 'char_end': len(view['text'])} if view['kind'] == 'text' else {})}
            for view in packet['views']]}
    return {'nodes': [] if empty else [node], 'complete': True, 'coverage_notes': ['Synthetic contract fixture.'],
        'reviews': [{'view_id': view['view_id'], 'disposition': 'context_only' if empty else 'selected',
            'candidate_keys': [] if empty else ['source-claim'], 'reason': 'Reviewed the supplied view.'}
            for view in packet['views']]}


def decisions(packet, keys=('source-claim',)):
    return {'complete': True, 'decisions': [{'candidate_key': key, 'verdict': 'accepted',
        'equivalent_candidate_key': None, 'equivalent_revision_id': None, 'reason_codes': ['source_supported'],
        'reason': 'Independent synthetic source check.', **{field: True for field in d2k.CHECKS}} for key in keys],
        'reviews': [{'view_id': view['view_id'], 'verdict': 'confirmed', 'reason_codes': ['source_reviewed'],
            'reason': 'Independent synthetic view review.'} for view in packet['views']]}


class D2KSourceViewTests(unittest.TestCase):
    def reject(self, callback):
        with self.assertRaises(PalimpsestError): callback()

    def test_text_every_codepoint_boundary_keeps_BOM_CRLF_and_original_ranges(self):
        text = '\ufeffA\r\nμ😀\rZ\n'
        raw, lines = text.encode('utf-8'), [1, 1, 1, 1, 2, 2, 2, 3, 3]
        for start in range(len(text)):
            for end in range(start + 1, len(text) + 1):
                a, b = len(text[:start].encode('utf-8')), len(text[:end].encode('utf-8'))
                view = d2k.text_view(raw, view_id=uid(1), data_id=sha256(raw).hexdigest(), byte_start=a, byte_end=b)
                self.assertEqual(view['text'], text[start:end])
                self.assertEqual(view['locator'], {'byte_start': a, 'byte_end': b, 'char_start': start, 'char_end': end,
                    'line_start': lines[start], 'line_end': lines[end - 1]})
                self.assertEqual(d2k.check_view(view), view)

    def test_non_UTF8_binary_PDF_NUL_wrong_hash_and_mid_character_views_are_rejected(self):
        raw = '\ufeffμ😀\n'.encode('utf-8')
        for a, b in ((1, len(raw)), (0, 1), (3, 4), (0, 0), (False, len(raw)), (-1, 3), (0, len(raw) + 1)):
            self.reject(lambda: d2k.text_view(raw, view_id=uid(1), data_id=sha256(raw).hexdigest(), byte_start=a, byte_end=b))
        self.reject(lambda: d2k.text_view(raw, view_id=uid(1), data_id='f' * 64, byte_start=0, byte_end=len(raw)))
        for raw in (b'\xff', b'x\x00y', b'%PDF-1.7\nASCII PDF'):
            self.reject(lambda: d2k.text_view(raw, view_id=uid(1), data_id=sha256(raw).hexdigest(), byte_start=0, byte_end=len(raw)))

    def test_input_needs_no_I_D2I_or_model_auth_flag_and_rejects_scope_tampering(self):
        packet = text_packet()
        self.assertEqual(d2k.check_input(packet), [uid(1)])
        self.assertEqual(set(packet), {'schema_version', 'data_id', 'media_type', 'original_byte_size', 'views', 'input_sha256'})
        for field in ('information', 'source_execution_id', 'authorized', 'direct_sources'):
            self.reject(lambda: d2k.check_input({**packet, field: True}))
        for change in ('text', 'hash', 'byte_end', 'bool', 'owner', 'size', 'duplicate', 'media'):
            changed = deepcopy(packet)
            view = changed['views'][0]
            if change == 'text': view['text'] += ' invented'
            elif change == 'hash': view['text_sha256'] = 'f' * 64
            elif change == 'byte_end': view['locator']['byte_end'] += 1
            elif change == 'bool': view['locator']['char_start'] = False
            elif change == 'owner': view['data_id'] = 'f' * 64
            elif change == 'size': view['original_byte_size'] += 1
            elif change == 'duplicate': changed['views'].append(deepcopy(view))
            else: changed['media_type'] = 'application/pdf'
            self.reject(lambda: d2k.check_input(changed))

    def test_partial_prefix_requires_Runtime_original_recheck(self):
        raw = b'abcdefghi'
        view = d2k.text_view(raw, view_id=uid(1), data_id=sha256(raw).hexdigest(), byte_start=1, byte_end=3)
        shifted = deepcopy(view)
        for field in ('byte_start', 'byte_end', 'char_start', 'char_end'): shifted['locator'][field] += 1
        self.assertEqual(d2k.check_view(shifted), shifted)
        actual = d2k.text_view(raw, view_id=uid(1), data_id=sha256(raw).hexdigest(), byte_start=2, byte_end=4)
        self.assertNotEqual(shifted, actual)  # Runtime must compare against actual registered bytes.

    def test_PDF_whole_cropped_page_preserves_nonuniform_pixel_transforms(self):
        packet = pdf_packet()
        view = packet['views'][0]
        self.assertNotEqual(view['transforms']['source_pdf_bottom_left_to_pixel_top_left'][0],
                            -view['transforms']['source_pdf_bottom_left_to_pixel_top_left'][3])
        citation = d2k.normalize_evidence({'view_id': view['view_id'], 'source_role': 'figure'}, packet)
        self.assertEqual(citation['representation'], 'original_pdf_page_image')
        self.assertEqual(citation['quote'], '')
        self.assertEqual((citation['char_start'], citation['char_end']), (0, 0))
        self.assertEqual(citation['quote_sha256'], sha256(b'').hexdigest())
        self.assertEqual(citation['media_sha256'], view['image_sha256'])
        self.assertEqual(citation['locator']['bbox'], [0, 0, 613, 821])
        self.assertEqual(citation['locator']['source_geometry'], view['source_geometry'])
        self.assertEqual(citation['locator']['transforms'], view['transforms'])
        self.assertNotIn('byte_start', citation['locator'])
        self.assertNotIn('information_id', citation)

    def test_PDF_unknown_rotated_outside_boolean_and_forged_matrix_metadata_fail(self):
        for field in ('rotation', 'size', 'box', 'matrix', 'inverse', 'nan', 'page', 'count', 'image', 'renderer'):
            view = pdf_view()
            if field == 'rotation': view['source_geometry']['rotation'] = 90
            elif field == 'size': view['page_size'][0] += 1
            elif field == 'box': view['source_geometry']['crop_box'][0] += 1
            elif field == 'matrix': view['transforms']['source_pdf_bottom_left_to_pixel_top_left'][4] = 0
            elif field == 'inverse': view['transforms']['pixel_top_left_to_source_pdf_bottom_left'][4] += 1
            elif field == 'nan': view['source_geometry']['media_box'][0] = float('nan')
            elif field == 'page': view['page_index'] = True
            elif field == 'count': view['page_count'] = 0
            elif field == 'image': view['image_sha256'] = 'invalid'
            else: view['renderer']['implementation_sha256']['d2k_pdf.py'] = 'invalid'
            with self.subTest(field=field): self.reject(lambda: d2k.check_view(view))
        view, other = pdf_view(), pdf_view()
        other['view_id'] = uid(999)
        self.reject(lambda: d2k.build_input('a' * 64, media_type='application/pdf', original_byte_size=1234, views=[view, other]))

    def test_text_repeated_quote_uses_explicit_range_and_never_accepts_model_global_locator(self):
        packet = text_packet('repeat μ\r\nrepeat μ\n')
        citation = {'view_id': uid(1), 'char_start': 10, 'char_end': 18, 'source_role': 'results'}
        normalized = d2k.normalize_evidence(citation, packet)
        self.assertEqual(normalized['quote'], 'repeat μ')
        self.assertEqual(normalized['locator']['line_start'], 2)
        self.assertEqual(normalized['locator']['line_end'], 2)
        for extra in ({'quote': 'invention'}, {'information_id': uid(1)}, {'data_id': packet['data_id']},
                      {'bbox': [0, 0, 1, 1]}, {'byte_start': 0}, {'char_end': True}):
            self.reject(lambda: d2k.normalize_evidence({**citation, **extra}, packet))
        page = pdf_packet()
        for extra in ({'quote': 'invented PDF text'}, {'char_start': 0, 'char_end': 3}, {'bbox': [1, 2, 3, 4]}):
            self.reject(lambda: d2k.normalize_evidence({'view_id': uid(100), 'source_role': 'figure', **extra}, page))


class D2KProposalTests(unittest.TestCase):
    def setUp(self):
        self.packet = text_packet(split=True)

    def reject(self, callback):
        with self.assertRaises(PalimpsestError): callback()

    def test_source_only_candidate_has_exact_D_refs_and_existing_selection_fingerprints(self):
        proposed = response(self.packet)
        before = deepcopy(proposed)
        result = d2k.normalize_proposals(proposed, self.packet)
        node, = result['nodes']
        expected = selection_fingerprints(node['kind'], node['semantic_payload'], node['identity_scope'], node['source_data_id'])
        self.assertEqual({key: node[key] for key in expected}, expected)
        self.assertFalse(node['is_inferred'])
        self.assertEqual({citation['data_id'] for citation in node['direct_evidence']}, {self.packet['data_id']})
        self.assertNotIn('evidence', node)
        self.assertTrue(all('information_id' not in citation for citation in node['direct_evidence']))
        self.assertEqual(proposed, before)
        paraphrase = deepcopy(proposed)
        paraphrase['nodes'][0]['statement'] = 'Same structured meaning, different display wording.'
        repeated = d2k.normalize_proposals(paraphrase, self.packet)['nodes'][0]
        self.assertEqual(repeated['content_fingerprint'], node['content_fingerprint'])

    def test_no_inference_fake_I_auth_revision_target_or_empty_evidence_can_enter(self):
        for change in ('inferred', 'basis', 'fake_I', 'premises', 'authorized', 'revision', 'empty', 'duplicate', 'owner', 'observation'):
            proposed = response(self.packet)
            node = proposed['nodes'][0]
            if change == 'inferred': node['is_inferred'] = True
            elif change == 'basis': node['claim_basis'] = 'system_inference'
            elif change == 'fake_I': node['evidence'] = [{'information_id': uid(99)}]
            elif change == 'premises': node['premise_revision_ids'] = [uid(99)]
            elif change == 'authorized': node['user_authorized'] = True
            elif change == 'revision': node['expected_revision_id'] = uid(99)
            elif change == 'empty': node['direct_evidence'] = []
            elif change == 'duplicate': node['direct_evidence'].append(deepcopy(node['direct_evidence'][0]))
            elif change == 'owner': node['source_data_id'] = 'f' * 64
            else: node.update(kind='observation', identity_scope='general', source_data_id=None)
            with self.subTest(change=change): self.reject(lambda: d2k.normalize_proposals(proposed, self.packet))

    def test_every_supplied_view_and_cited_candidate_is_reviewed(self):
        original = response(self.packet)
        for change in ('missing', 'duplicate', 'unknown', 'empty_selected', 'uncited', 'context_citation', 'unresolved_complete'):
            proposed = deepcopy(original)
            if change == 'missing': proposed['reviews'].pop()
            elif change == 'duplicate': proposed['reviews'].append(deepcopy(proposed['reviews'][0]))
            elif change == 'unknown': proposed['reviews'][0]['view_id'] = uid(999)
            elif change == 'empty_selected': proposed['reviews'][0]['candidate_keys'] = []
            elif change == 'uncited': proposed['nodes'][0]['direct_evidence'].pop()
            elif change == 'context_citation': proposed['reviews'][0]['disposition'] = 'context_only'
            else: proposed['reviews'][0]['disposition'] = 'needs_review'
            with self.subTest(change=change): self.reject(lambda: d2k.normalize_proposals(proposed, self.packet))
        unresolved = deepcopy(original)
        unresolved.update(complete=False)
        unresolved['reviews'][0]['disposition'] = 'needs_review'
        self.assertFalse(d2k.normalize_proposals(unresolved, self.packet)['complete'])

    def test_zero_candidates_is_valid_after_view_review_without_empty_schema_enums(self):
        normalized = d2k.normalize_proposals(response(self.packet, empty=True), self.packet)
        self.assertEqual(normalized['nodes'], [])
        self.assertEqual(d2k.validate_decisions(decisions(self.packet, ()), [], [], self.packet)['decisions'], {})
        def walk(value):
            if isinstance(value, dict):
                if 'enum' in value: self.assertTrue(value['enum'])
                if value.get('type') == 'object':
                    self.assertFalse(value['additionalProperties'])
                    self.assertEqual(set(value['required']), set(value['properties']))
                for child in value.values(): walk(child)
            elif isinstance(value, list):
                for child in value: walk(child)
        for schema in (d2k.generation_schema(self.packet), d2k.validation_schema([], [], self.packet),
                       d2k.validation_schema(['source-claim'], [uid(88)], self.packet)):
            walk(schema)

    def test_independent_decisions_require_all_explicitness_checks_and_every_view(self):
        candidates = d2k.normalize_proposals(response(self.packet), self.packet)['nodes']
        original = decisions(self.packet)
        self.assertEqual(d2k.validate_decisions(original, candidates, [], self.packet)['decisions']['source-claim']['verdict'], 'accepted')
        for check in d2k.CHECKS:
            changed = deepcopy(original)
            changed['decisions'][0][check] = False
            self.reject(lambda: d2k.validate_decisions(changed, candidates, [], self.packet))
        changed = deepcopy(original)
        changed['reviews'].pop()
        self.reject(lambda: d2k.validate_decisions(changed, candidates, [], self.packet))
        changed = deepcopy(original)
        changed['complete'] = False
        changed['reviews'][0]['verdict'] = 'needs_review'
        self.assertFalse(d2k.validate_decisions(changed, candidates, [], self.packet)['complete'])
        changed['decisions'][0].update(verdict='needs_human', source_explicit=False)
        self.assertEqual(d2k.validate_decisions(changed, candidates, [], self.packet)['decisions']['source-claim']['verdict'], 'needs_human')

    def test_exact_existing_and_batch_reuse_keep_shared_reuse_guards(self):
        proposed = response(self.packet)
        alias = deepcopy(proposed['nodes'][0]); alias['candidate_key'] = 'alias'
        proposed['nodes'].append(alias)
        for review in proposed['reviews']: review['candidate_keys'].append('alias')
        candidates = d2k.normalize_proposals(proposed, self.packet)['nodes']
        result = decisions(self.packet, ('alias', 'source-claim'))
        result['decisions'][0].update(verdict='reused', equivalent_candidate_key='source-claim')
        checked = d2k.validate_decisions(result, candidates, [], self.packet)
        self.assertEqual(list(checked['decisions']), ['source-claim', 'alias'])
        result['decisions'][0]['equivalent_candidate_key'] = 'alias'
        self.reject(lambda: d2k.validate_decisions(result, candidates, [], self.packet))
        result['decisions'][0].update(equivalent_candidate_key=None, equivalent_revision_id=uid(88))
        self.reject(lambda: d2k.validate_decisions(result, candidates, [], self.packet))
        self.assertEqual(d2k.validate_decisions(result, candidates, [uid(88)], self.packet)['decisions']['alias']['verdict'], 'reused')

    def test_prompts_include_exact_views_and_separate_authority_without_any_IO(self):
        snapshot = {'input': self.packet, 'existing_nodes': [], 'authorization': {'grant_id': uid(77), 'actor': 'user'}}
        candidates = d2k.normalize_proposals(response(self.packet), self.packet)['nodes']
        context = {'input_snapshot': snapshot, 'candidates': candidates}
        original = deepcopy((snapshot, context))
        with patch('builtins.open', side_effect=AssertionError('No source file access')), \
                patch('urllib.request.urlopen', side_effect=AssertionError('No source fetch')), \
                patch('subprocess.Popen', side_effect=AssertionError('No model or D2I')):
            for prompt in (d2k.generation(snapshot, []), d2k.validation(context, [])):
                for view in self.packet['views']:
                    self.assertIn(view['view_id'], prompt)
                    self.assertIn(json.dumps(view['text'], ensure_ascii=False), prompt)
                self.assertIn('Runtime, not you', prompt)
        self.assertEqual((snapshot, context), original)

    def test_PDF_prompt_requires_exact_owned_images_and_maps_shared_bytes_to_both_pages(self):
        packet = pdf_packet()
        asset = {'sha256': packet['views'][0]['image_sha256'], 'byte_size': packet['views'][0]['image_byte_size']}
        snapshot = {'input': packet, 'existing_nodes': []}
        self.reject(lambda: d2k.generation(snapshot, []))
        self.reject(lambda: d2k.generation(snapshot, [{**asset, 'sha256': 'f' * 64}]))
        self.reject(lambda: d2k.generation(snapshot, [asset, asset]))
        prompt = d2k.generation(snapshot, [asset])
        self.assertIn('"view_ids": ["' + uid(100) + '", "' + uid(101) + '"]', prompt)
        self.assertIn('not delivery\nof native PDF bytes', prompt)
        normalized = d2k.normalize_proposals(response(packet), packet)
        self.assertEqual(len(normalized['nodes'][0]['direct_evidence']), 2)

    def test_catalog_projection_retains_core_semantics_without_foreign_source_quotes(self):
        node = {'knode_id': uid(71), 'kind': 'proposition', 'current_revision_id': uid(72),
            'knode_revision_id': uid(72), 'statement': 'A retained existing Knowledge statement.',
            'semantic_payload': response(self.packet)['nodes'][0]['semantic_payload'],
            'identity_fingerprint': 'a' * 64, 'content_fingerprint': 'b' * 64,
            'identity_scope': 'source', 'source_data_id': 'c' * 64,
            'origin_record_id': uid(73), 'current_applicability': 'current_premises'}
        raw_marker = 'FOREIGN_RAW_SOURCE_TEXT_MUST_NOT_BE_IN_THE_MODEL_CATALOG'
        full = {**deepcopy(node), 'direct_groundings': [{'quote': raw_marker, 'information_id': uid(90)}],
            'direct_data_groundings': [{'evidence': {'quote': raw_marker}}],
            'transitive_source_refs': [{'quote': raw_marker}], 'transitive_data_refs': [{'quote': raw_marker}],
            'generation_origin': {'premise_revision_ids': [uid(99)], 'validation': {'quote': raw_marker}},
            'derivations': [{'retained_original': raw_marker}]}
        second = {'knode_id': uid(74), 'kind': 'proposition', 'statement': 'Second catalog node.'}
        catalog = d2k.catalog_nodes([full, second])
        self.assertEqual(catalog, [node, {**second,'current_applicability':'current_premises'}])
        self.assertEqual(d2k.catalog_nodes([second]),d2k.catalog_nodes([{**second,'current_applicability':'current_premises'}]))
        self.assertNotIn(raw_marker, json.dumps(catalog))
        self.assertNotIn(uid(90), json.dumps(catalog))
        self.assertNotIn(uid(99), json.dumps(catalog))
        snapshot = {'input': self.packet, 'existing_nodes': [full, second]}
        context = {'input_snapshot': snapshot, 'candidates': [], 'existing_nodes': [full]}
        before = deepcopy((snapshot, context))
        for prompt in (d2k.generation(snapshot, []), d2k.validation(context, [])):
            self.assertNotIn(raw_marker, prompt)
            self.assertNotIn(uid(99), prompt)
            for field in ('knode_id', 'knode_revision_id', 'semantic_payload', 'content_fingerprint',
                          'source_data_id', 'origin_record_id', 'current_applicability'):
                self.assertIn(json.dumps(node[field], ensure_ascii=False, sort_keys=True), prompt)
        self.assertEqual((snapshot, context), before)
        catalog[0]['semantic_payload']['conditions'].append('changed only in projection')
        self.assertEqual((snapshot, context), before)
        self.reject(lambda: d2k.catalog_nodes([None]))

    def test_prior_review_is_preserved_as_untrusted_feedback_in_both_model_phases(self):
        snapshot = {'input': self.packet, 'existing_nodes': [], 'prior_d2k_review': {
            'execution_id': uid(80), 'review_notes': ['Recheck the exact qualifier in view one.'],
            'source_requests': ['Untrusted suggestion to expand scope; not permission.']}}
        before = deepcopy(snapshot)
        context = {'input_snapshot': snapshot, 'candidates': []}
        for prompt in (d2k.generation(snapshot, []), d2k.validation(context, [])):
            self.assertIn('PRIOR_D2K_REVIEW_JSON:', prompt)
            self.assertIn('not source evidence or authorization', prompt)
            self.assertIn('do not expand the authorized source scope', prompt)
            self.assertIn('Recheck the exact qualifier in view one.', prompt)
        self.assertEqual(snapshot, before)
        without = {key: value for key, value in snapshot.items() if key != 'prior_d2k_review'}
        self.assertNotIn('PRIOR_D2K_REVIEW_JSON:', d2k.generation(without, []))


if __name__ == '__main__':
    unittest.main()
