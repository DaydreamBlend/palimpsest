"""I-first preparation checks; synthetic canonical snapshots, no provider or DB."""

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.i2k import build_input, digest, validate_source_request
from palimpsest.information import fingerprints
from palimpsest.source_units import build_source_units


def uid(number):
    return f'019947e2-1234-7000-8000-{number:012x}'


def fixture(*, include_original_image=False):
    data = 'a' * 64
    image_hash, full_hash = sha256(b'panel').hexdigest(), sha256(b'full').hexdigest()
    def block(ref, page, index, text, kind='text', image=None):
        return {'block_id': ref, 'type': kind, 'page_index': page, 'page_size': [600, 800],
            'bbox': [0, 0, 200, 100], 'raw_locator': ref, 'source_collection': 'preproc_blocks',
            'anchor_sha256': sha256(ref.encode()).hexdigest(), 'supported': True, 'unsupported': [],
            'text': text, 'image_paths': ([{'path': image[0], 'sha256': image[1]}] if image else []),
            'upstream_metadata': {'index': index, 'PRIVATE_RAW_TREE': 'DO_NOT_SEND'},
            'grounding_regions': [{'type': 'span', 'raw_locator': ref + '/span/0',
                'bbox': [0, 0, 200, 100], 'upstream_metadata': {'PRIVATE_REGION_TREE': 'DO_NOT_SEND'}}]}
    bundle = {'schema_version': 1, 'data_id': data, 'coordinate_system': 'pdf_points_top_left',
        'extraction_scope': 'whole_document', 'pages': [
            {'page_index': n, 'page_size': [600, 800],
             'source_page_image': {'path': f'ORIGINAL_PAGE_{n}.png', 'sha256': 'e' * 64}}
            for n in range(3)],
        'blocks': [block('/body', 0, 2, '  μ = 3\r\nCafe\u0301  '),
            block('/heading', 0, 1, 'Abstract', 'title'),
            block('/table', 0, 3, '<table>Exact table</table>', 'table', ('images/panel.png', image_hash)),
            block('/panel', 1, 1, '', 'image', ('images/panel.png', image_hash)),
            block('/caption', 2, 1, 'Figure 1. A cross-page caption.'),
            block('/figures/0', 1, None, 'SYNTHETIC_LABEL', 'image', ('images/full.png', full_hash))],
        'required_figures': [{'figure_id': 'figure:1', 'number': 1, 'block_id': '/figures/0',
                             'member_block_ids': ['/panel'], 'caption_block_ids': ['/caption']}]}
    if include_original_image:
        bundle['blocks'].append(block('/original-image', 2, 2, '  Original μ label\r\n',
                                      'image', ('images/panel.png', image_hash)))
    by_ref = {b['block_id']: b for b in bundle['blocks']}
    artifacts = {image['path']: {'sha256': image['sha256'], 'byte_size': 23,
        'artifact_path': f"derived/objects/sha256/{image['sha256'][:2]}/{image['sha256']}"}
        for b in bundle['blocks'] for image in b['image_paths']}
    rows = []
    for ordinal, proposal in enumerate(build_source_units(bundle)):
        refs, primary = proposal['block_ids'], proposal['image_block_id']
        rows.append({'information_id': uid(ordinal + 1), 'origin_record_id': uid(ordinal + 100),
            'data_id': data, **{k: proposal[k] for k in ('kind', 'unit_type', 'semantic_type', 'title', 'content')},
            **{k: v for k, v in fingerprints(data, proposal, by_ref).items() if k != 'context_fingerprint'},
            'payload': {'schema_version': 'source-information-v1', 'source_bundle_sha256': digest(bundle),
                'parse_manifest_sha256': 'f' * 64, 'validation_basis': 'source_structure',
                'semantic_checked': False, 'empty_content': proposal['content'] == '',
                'primary_block_id': primary, 'source_blocks': [deepcopy(by_ref[r]) for r in refs],
                'source_artifacts': {a['path']: deepcopy(artifacts[a['path']]) for r in refs for a in by_ref[r]['image_paths']},
                'images': [deepcopy(artifacts[a['path']]) for a in by_ref[primary]['image_paths']] if primary else []},
            'groundings': [{'grounding_id': uid(500 + ordinal * 10 + n), 'parse_artifact_id': uid(900),
                'information_id': uid(ordinal + 1), 'data_id': data,
                **{k: deepcopy(by_ref[r][k]) for k in ('block_id', 'page_index', 'bbox', 'page_size', 'raw_locator', 'anchor_sha256')}}
                for n, r in enumerate(refs)]})
    return bundle, rows


class I2KInputTests(unittest.TestCase):
    def setUp(self):
        self.bundle, self.rows = fixture()

    def build(self, **kwargs):
        return build_input(self.bundle, self.rows, execution_id=uid(1000), profile_id=uid(1001), **kwargs)

    def error(self, code, action):
        with self.assertRaises(PalimpsestError) as caught:
            action()
        self.assertEqual(caught.exception.code, code)
        self.assertNotIn('PRIVATE', json.dumps(caught.exception.details))

    def test_exact_canonical_content_order_and_image_i_media_without_original_companions(self):
        before = deepcopy((self.bundle, self.rows))
        packet = self.build()
        units = packet['model_input']['information']
        self.assertEqual([u['title'] for u in units][:2], ['Abstract', self.rows[0]['title']])
        self.assertEqual(units[1]['content'], self.rows[0]['content'])
        figure = next(u for u in units if u['unit_type'] == 'figure')
        self.assertEqual(figure['content'], 'Figure 1. A cross-page caption.')
        self.assertEqual({r['page_index'] for r in figure['source_refs']}, {1, 2})
        self.assertEqual(len(figure['media']), 2)
        self.assertTrue(all(r['grounding_id'] and r['parse_artifact_id'] for r in figure['source_refs']))
        serialized = json.dumps(packet['model_input'])
        for forbidden in ('ORIGINAL_PAGE_', 'PRIVATE_RAW_TREE', 'PRIVATE_REGION_TREE', 'artifact_path', 'SYNTHETIC_LABEL'):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(packet['state'], 'prepared_not_delivered')
        self.assertIs(packet['actual_delivery'], False)
        self.assertEqual(packet['llm_calls'], 0)
        self.assertEqual(packet['canonical_writes'], 0)
        self.assertEqual(packet['model_input']['quality_evidence']['status'], 'not_supplied')
        self.assertEqual(before, (self.bundle, self.rows))
        self.rows.reverse()
        self.assertEqual(self.build(), packet)

    def test_table_media_and_shared_attachment_keep_all_source_mappings(self):
        packet = self.build()
        table = next(u for u in packet['model_input']['information'] if u['unit_type'] == 'table')
        self.assertEqual(table['kind'], 'text')
        self.assertEqual(table['media'][0]['source_block_id'], '/table')
        self.assertEqual(len(packet['media_assets']), 2)
        shared = table['media'][0]['sha256']
        refs = [m['source_block_id'] for u in packet['model_input']['information'] for m in u['media'] if m['sha256'] == shared]
        self.assertCountEqual(refs, ['/table', '/panel'])

    def test_original_image_primary_retains_source_text_range_only_synthetic_figure_is_derived(self):
        self.bundle, self.rows = fixture(include_original_image=True)
        packet = self.build()
        image = next(unit for unit in packet['model_input']['information'] if unit['unit_type'] == 'image')
        ref = image['source_refs'][0]
        self.assertFalse(ref['derived_primary'])
        self.assertEqual(image['content'], '  Original μ label\r\n')
        self.assertEqual(ref['source_text_range'], {'char_start': 0, 'char_end': len(image['content']),
                                                   'offsets': 'unicode_codepoints_half_open'})
        figure = next(unit for unit in packet['model_input']['information'] if unit['unit_type'] == 'figure')
        primary = next(ref for ref in figure['source_refs'] if ref['block_id'] == '/figures/0')
        self.assertTrue(primary['derived_primary'])
        self.assertIsNone(primary['source_text_range'])
        self.assertTrue(all(not ref['derived_primary'] and ref['source_text_range'] is not None
                            for ref in figure['source_refs'] if ref['block_id'] != '/figures/0'))

    def test_selected_and_context_information_stay_whole_ordered_and_have_distinct_roles(self):
        figure, heading = self.rows[-1]['information_id'], self.rows[1]['information_id']
        packet = self.build(selected_information_ids=[figure], context_information_ids=[figure, heading])
        self.assertEqual(packet['target_information_ids'], [figure])
        self.assertEqual(packet['context_information_ids'], [heading])
        self.assertEqual([u['role'] for u in packet['model_input']['information']], ['context', 'target'])
        self.assertEqual(len(packet['excluded_information_ids']), 2)
        self.assertEqual(len(packet['model_input']['information'][-1]['source_refs']), 3)
        self.error('i2k_information_scope_mismatch', lambda: self.build(selected_information_ids=[uid(9999)]))
        self.error('invalid_i2k_input', lambda: self.build(selected_information_ids=[figure, figure]))

    def test_tampered_canonical_content_fingerprint_or_source_media_cannot_prepare(self):
        mutations = [lambda r: r[0].update(content='Invented source'),
            lambda r: r[0].update(title='Changed title'),
            lambda r: r[0].update(content_fingerprint='0' * 64),
            lambda r: r[2]['payload']['source_artifacts'].clear(),
            lambda r: r[-1]['payload']['images'].clear(),
            lambda r: r[0]['groundings'][0].update(raw_locator='/wrong')]
        for change in mutations:
            with self.subTest(change=change):
                self.bundle, self.rows = fixture()
                change(self.rows)
                self.error('invalid_i2k_input', self.build)
        self.bundle, self.rows = fixture()
        self.rows[0]['payload']['primary_block_id'] = '/heading'
        self.error('invalid_page_projection', self.build)
        self.bundle, self.rows = fixture()
        next(iter(self.rows[2]['payload']['source_artifacts'].values()))['artifact_path'] = '/tmp/not-canonical.png'
        self.error('invalid_i2k_input', self.build)

    def test_missing_cross_data_legacy_or_modified_blocks_are_not_canonical_i(self):
        changes = [lambda r: r.pop(), lambda r: r[0].update(data_id='b' * 64),
            lambda r: r[0]['payload'].update(schema_version='information-v1'),
            lambda r: r[0]['payload']['source_blocks'][0].update(text='changed')]
        for change in changes:
            self.bundle, self.rows = fixture()
            change(self.rows)
            self.error('invalid_page_projection', self.build)

    def test_optional_quality_signals_bind_exact_snapshot_without_forwarding_alternate_text(self):
        evidence = {'source_bundle': deepcopy(self.bundle), 'manifest_sha256': 'c' * 64,
            'text_analysis': {'heading_candidates': [], 'discrepancies': [
                {'discrepancy_id': 'd1', 'page_index': 0, 'kind': 'region_text_difference',
                 'parser_refs': [{'raw_locator': '/body'}], 'native_text': 'PRIVATE_ALTERNATE_TEXT'},
                {'discrepancy_id': 'd2', 'page_index': 2, 'kind': 'region_text_difference',
                 'parser_refs': [{'raw_locator': '/caption'}]}]},
            'paragraphs': {'paragraphs': []}, 'visuals': {'figures': [], 'pages': [], 'panels': []}}
        packet = self.build(selected_information_ids=[self.rows[0]['information_id']], evidence=evidence)
        quality = packet['model_input']['quality_evidence']
        self.assertEqual([x['discrepancy_id'] for x in quality['issues'] if x['code'] == 'transcription_discrepancy'], ['d1'])
        self.assertFalse(quality['source_fidelity_verified'])
        self.assertNotIn('PRIVATE_ALTERNATE_TEXT', json.dumps(packet))
        evidence['source_bundle']['data_id'] = 'b' * 64
        self.error('i2k_evidence_mismatch', lambda: self.build(evidence=evidence))

    def test_requests_bind_snapshot_question_and_visible_information_without_claiming_model_delivery(self):
        packet = self.build(selected_information_ids=[self.rows[0]['information_id']],
                            context_information_ids=[self.rows[1]['information_id']])
        request = {'schema_version': 'i2k-source-request-v1', 'input_sha256': packet['input_sha256'],
                   'information_ids': packet['context_information_ids'], 'question': 'μ의 첨자를 확인할 수 있나요?',
                   'page_numbers': [1]}
        result = validate_source_request(request, packet)
        self.assertEqual(result['data_id'], self.bundle['data_id'])
        self.assertEqual(result['state'], 'validated_not_delivered')
        self.assertIs(result['actual_delivery'], False)
        self.assertIs(result['model_request_observed'], False)
        for key, value in [('provider', 'invented'), ('artifact_path', '/tmp/source.pdf'), ('actual_delivery', True)]:
            self.error('invalid_i2k_source_request', lambda: validate_source_request({**request, key: value}, packet))
        self.error('i2k_input_changed', lambda: validate_source_request({**request, 'input_sha256': '0' * 64}, packet))
        self.error('i2k_information_scope_mismatch', lambda: validate_source_request(
            {**request, 'information_ids': [self.rows[-1]['information_id']]}, packet))
        for change in ({'question': ''}, {'question': 'x' * 4097}, {'page_numbers': [True]},
                       {'page_numbers': [4]}, {'page_numbers': [1, 1]}, {'information_ids': []}):
            self.error('invalid_i2k_source_request', lambda: validate_source_request({**request, **change}, packet))
        changed = deepcopy(packet)
        changed['model_input']['information'][0]['content'] = 'changed'
        self.error('i2k_input_changed', lambda: validate_source_request(request, changed))


if __name__ == '__main__':
    unittest.main()
