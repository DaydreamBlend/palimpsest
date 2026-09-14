"""Verify source bindings and safe, offline evidence read behavior."""
from contextlib import redirect_stdout
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from palimpsest.cli import main
from palimpsest.errors import PalimpsestError
from palimpsest.pdf_evidence import (PRO_REVISION, PRO_WEIGHT, local_file, verify_parse_result,
                                    read_evidence, file_hash, write_json, publish_manifest, create_pdf_evidence)
from palimpsest.paragraph_projection import digest, select_evidence_context


class PdfEvidenceTests(unittest.TestCase):
    def test_verified_receipt_rejects_changed_artifact_and_different_pdf(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source.pdf'
            source.write_bytes(b'fixed source bytes')
            data_id = sha256(source.read_bytes()).hexdigest()
            middle = root / 'middle.json'
            middle.write_bytes(b'{}')
            receipt = {'status': 'complete', 'backend': 'hybrid-engine', 'effort': 'high',
                'resolved_engine': 'transformers', 'versions': {'mineru': '3.4.5'},
                'pro_revision': PRO_REVISION, 'pro_weight_sha256': PRO_WEIGHT, 'network': 'none',
                'data_id': data_id, 'source_sha256_before': data_id, 'source_sha256_after': data_id,
                'middle_relative_path': 'middle.json',
                'artifacts': [{'path': 'middle.json', 'bytes': 2, 'sha256': sha256(b'{}').hexdigest()}]}
            path = root / 'receipt.json'
            path.write_text(json.dumps(receipt), encoding='utf-8')
            self.assertEqual(verify_parse_result(path, source)['data_id'], data_id)
            middle.write_bytes(b'[]')
            with self.assertRaises(PalimpsestError) as failure:
                verify_parse_result(path, source)
            self.assertEqual(failure.exception.code, 'evidence_artifact_changed')
            source.write_bytes(b'new PDF')
            with self.assertRaises(PalimpsestError) as failure:
                verify_parse_result(path, source)
            self.assertEqual(failure.exception.code, 'evidence_source_changed')

    def test_artifact_path_escape_is_rejected(self):
        with TemporaryDirectory() as temporary:
            for path in ('../source.pdf', '/source.pdf', 'images/../../source.pdf', 'C:/source.pdf'):
                with self.subTest(path=path), self.assertRaises(PalimpsestError):
                    local_file(Path(temporary), path)

    def test_context_cli_does_not_require_or_open_database(self):
        expected = {'data_id': 'a' * 64, 'page_number': 2, 'canonical_writes': 0}
        with patch('palimpsest.cli.load_config', side_effect=AssertionError('must not open DB')):
            with patch('palimpsest.pdf_evidence.read_evidence', return_value={}) as read:
                with patch('palimpsest.paragraph_projection.select_evidence_context', return_value=expected):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        code = main(['information', 'evidence-context', '--directory', 'evidence', '--page', '2', '--json'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())['result'], expected)
        read.assert_called_once_with(Path('evidence'))

    def test_valid_file_hashes_do_not_allow_cross_data_sidecars(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'visuals').mkdir()
            (root / 'source.pdf').write_bytes(b'fixed PDF')
            data_id = file_hash(root / 'source.pdf')
            write_json(root / 'source_middle.json', {})
            receipt = {'data_id': data_id, 'source_sha256_before': data_id, 'source_sha256_after': data_id,
                'middle_relative_path': 'parser/middle.json', 'artifacts': [{'path': 'parser/middle.json',
                    'sha256': file_hash(root / 'source_middle.json'), 'bytes': (root / 'source_middle.json').stat().st_size}]}
            write_json(root / 'parse_result.json', receipt)
            bundle = {'data_id': data_id, 'pages': [], 'blocks': [],
                      'profile': {'parse_result_sha256': file_hash(root / 'parse_result.json')}}
            payloads = {'source_bundle.json': bundle, 'source_middle.json': {},
                'pdf_native_text.json': {'data_id': data_id}, 'parse_result.json': receipt,
                'text_analysis.json': {'data_id': data_id},
                'paragraphs.json': {'data_id': data_id, 'source_bundle_sha256': digest(bundle),
                                    'source_middle_sha256': digest({})},
                'visuals/manifest.json': {'source': {'data_id': data_id, 'pdf_sha256': data_id,
                                                    'bundle_sha256': digest(bundle)}},
                'status.json': {'state': 'complete'}}
            for name, value in payloads.items():
                write_json(root / name, value)
            def publish():
                files = [{'path': p.relative_to(root).as_posix(), 'sha256': file_hash(p), 'bytes': p.stat().st_size}
                         for p in root.rglob('*') if p.is_file() and p != root / 'manifest.json']
                write_json(root / 'manifest.json', {'schema_version': 'pdf-evidence-v1', 'data_id': data_id,
                    'source_bundle_sha256': digest(bundle), 'parse_result_sha256': file_hash(root / 'parse_result.json'),
                    'files': files})
            publish()
            self.assertEqual(read_evidence(root)['source_bundle'], bundle)
            payloads['paragraphs.json']['data_id'] = 'b' * 64
            write_json(root / 'paragraphs.json', payloads['paragraphs.json'])
            publish()
            with self.assertRaises(PalimpsestError) as failure:
                read_evidence(root)
            self.assertEqual(failure.exception.code, 'evidence_source_changed')
            write_json(root / 'paragraphs.json', {**payloads['paragraphs.json'], 'data_id': data_id})
            for key in ('data_id', 'source_sha256_before', 'source_sha256_after', 'artifacts'):
                changed = dict(receipt)
                changed[key] = ([{**receipt['artifacts'][0], 'sha256': 'b' * 64}]
                                if key == 'artifacts' else 'b' * 64)
                write_json(root / 'parse_result.json', changed)
                bundle['profile']['parse_result_sha256'] = file_hash(root / 'parse_result.json')
                write_json(root / 'source_bundle.json', bundle)
                write_json(root / 'paragraphs.json', {**payloads['paragraphs.json'], 'data_id': data_id,
                                                     'source_bundle_sha256': digest(bundle)})
                write_json(root / 'visuals/manifest.json', {'source': {'data_id': data_id,
                    'pdf_sha256': data_id, 'bundle_sha256': digest(bundle)}})
                # Even a valid outer file manifest must not bind a different parser run.
                publish()
                with self.subTest(receipt_field=key), self.assertRaises(PalimpsestError) as failure:
                    read_evidence(root)
                self.assertEqual(failure.exception.code, 'evidence_source_changed')

    def test_failed_final_publish_has_no_completion_marker(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_json(root / 'status.json', {'state': 'artifacts_verified'})
            manifest = {'schema_version': 'pdf-evidence-v2', 'state': 'complete'}
            with patch('palimpsest.pdf_evidence.os.replace', side_effect=OSError('simulated failure')):
                with self.assertRaises(OSError):
                    publish_manifest(root, manifest)
            self.assertFalse((root / 'manifest.json').exists())
            self.assertNotEqual(json.loads((root / 'status.json').read_text())['state'], 'complete')
            publish_manifest(root, manifest)
            self.assertEqual(json.loads((root / 'manifest.json').read_text()), manifest)

    def test_dual_export_preserves_raw_trees_profile_and_rejects_rehashed_selected_text(self):
        self._assert_retained_export('mineru-hybrid-dual200-v1')

    def test_image_export_preserves_ocr_raster_and_rejects_rehashed_text_or_other_data(self):
        self._assert_retained_export('mineru-hybrid-image200-v1')

    def _assert_retained_export(self, adapter):
        """Exercise export/read binding with only parser/PDF boundaries mocked."""
        image_mode = adapter == 'mineru-hybrid-image200-v1'
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            parse = root / 'parse'
            retained = parse / 'parser/source/hybrid_auto'
            retained.mkdir(parents=True)
            (parse / 'source.pdf').write_bytes(b'original source PDF bytes')
            data_id = file_hash(parse / 'source.pdf')
            pointer = '/pdf_info/0/preproc_blocks/0'
            span = {'type':'text', 'bbox':[1,1,20,10], 'content':'1 μg/ml' if image_mode else '1 mg/ml'}
            raw = {'type':'text', 'bbox':span['bbox'], 'lines':[{'spans':[span]}]}
            middle = {'pdf_info':[{'page_idx':0, 'preproc_blocks':[raw], 'para_blocks':[raw]}]}
            write_json(retained / 'source_middle.json', middle)
            profile = {'schema_version':'source-d2i-v1', 'parser':{'adapter_version':adapter,
                       'renderer_sha256':'d'*64}, 'policy':{'llm_calls':0}}
            write_json(retained / 'palimpsest_profile.json', profile)
            (retained / 'ocr/images').mkdir(parents=True)
            (retained / 'ocr/images/panel.jpg').write_bytes(b'exact secondary crop pixels')
            write_json(retained / 'ocr/ocr_middle.json', {'raw':'1 μg/ml'})
            (retained / 'raster').mkdir()
            (retained / 'raster/page-0001.png').write_bytes(b'exact original 200 DPI pixels')
            write_json(retained / 'raster/manifest.json', {'source':{'data_id':data_id}, 'dpi':200})
            receipt = {'status':'complete', 'backend':'hybrid-engine', 'effort':'high',
                'resolved_engine':'transformers', 'versions':{'mineru':'3.4.5'},
                'pro_revision':PRO_REVISION, 'pro_weight_sha256':PRO_WEIGHT, 'network':'none',
                'data_id':data_id, 'source_sha256_before':data_id, 'source_sha256_after':data_id,
                'page_count':1, 'adapter_version':adapter, 'source_relative_path':'source.pdf',
                'middle_relative_path':'parser/source/hybrid_auto/source_middle.json',
                'artifacts':[{'path':p.relative_to(parse).as_posix(), 'sha256':file_hash(p), 'bytes':p.stat().st_size}
                             for p in parse.rglob('*') if p.is_file()]}
            write_json(retained / 'palimpsest_source_check.json', receipt)
            write_json(parse / 'parse_result.json', receipt)
            choice = {'block_id':pointer, 'page_index':0, 'native_text':'1 mg/ml', 'selected_text':'1 μg/ml',
                      'status':'selected', 'issues':[], 'changes':[{'native_range':[2,3], 'native_text':'m',
                      'selected_text':'μ', 'ocr_refs':[{'raw_artifact':{'artifact_path':'ocr/ocr_middle.json', 'sha256':'e'*64}}]}]}
            bundle = {'data_id':data_id, 'profile':profile['parser'], 'block_collection':'preproc_blocks',
                'unsupported_block_ids':[], 'pages':[{'page_index':0}], 'blocks':[{
                    'block_id':pointer, 'page_index':0, 'text':'1 μg/ml', 'native_text':'1 mg/ml',
                    'native_raw_artifact':{'artifact_path':'source_middle.json', 'sha256':file_hash(retained/'source_middle.json')},
                    'transcription_selection':choice, 'segments':[{'raw_locator':pointer+'/lines/0/spans/0', **span}]}],
                'ocr_bundle':{'blocks':[]}, 'transcription_selection':{'blocks':[choice], 'unresolved':[]}}
            if image_mode:
                bundle.pop('ocr_bundle')
                bundle.pop('transcription_selection')
                for field in ('native_text', 'native_raw_artifact', 'transcription_selection'):
                    bundle['blocks'][0].pop(field)
                raster = retained / 'raster/page-0001.png'
                bundle['raster_manifest_sha256'] = file_hash(retained / 'raster/manifest.json')
                bundle['pages'][0].update(source_page_image={
                    'path':'raster/page-0001.png', 'sha256':file_hash(raster), 'bytes':raster.stat().st_size,
                    'pixel_size':[200,200], 'mode':'RGB', 'dpi_requested':200, 'dpi_effective':200},
                    coordinate_transform={'scale':[1,1]})
            def visuals(pdf_path, selected, destination, **kwargs):
                destination.mkdir()
                result = {'source':{'data_id':data_id, 'pdf_sha256':data_id, 'bundle_sha256':digest(selected)},
                          'pages':[], 'panels':[], 'figures':[]}
                write_json(destination / 'manifest.json', result)
                return result
            before = {p.relative_to(parse):p.read_bytes() for p in parse.rglob('*') if p.is_file()}
            with patch('palimpsest.hybrid_receipt.validate_hybrid_receipt') as validate, \
                    patch('palimpsest.dual_adapter.normalize_dual', side_effect=(AssertionError('no dual fallback')
                        if image_mode else lambda *a, **kw: deepcopy(bundle))) as dual_normalize, \
                    patch('palimpsest.image_adapter.normalize_image', side_effect=(
                        (lambda *a, **kw: deepcopy(bundle)) if image_mode else AssertionError('no image fallback'))) as image_normalize, \
                    patch('palimpsest.pdf_text_evidence.extract_pdf_text', return_value={'data_id':data_id}), \
                    patch('palimpsest.pdf_text_evidence.analyze_pdf_text', return_value={
                        'data_id':data_id, 'heading_candidates':[], 'discrepancies':[]}) as analyze, \
                    patch('palimpsest.pdf_visual_evidence.build_pdf_visuals', side_effect=visuals):
                evidence = root / 'evidence'
                create_pdf_evidence(parse / 'parse_result.json', evidence)
                result = read_evidence(evidence)
                self.assertEqual(result['source_bundle'], bundle)
                self.assertEqual(result['paragraphs']['paragraphs'][0]['text'], span['content'])
                if image_mode:
                    self.assertNotIn('selected_text', result['paragraphs']['paragraphs'][0])
                    self.assertNotIn('transcription_selection', result['source_bundle'])
                    self.assertEqual(Path(result['parser_artifact_base_directory']),
                                     (evidence/'parser_raw/parser/source/hybrid_auto').resolve())
                    context = select_evidence_context(result, 1)
                    self.assertEqual(context['rendered_source_pages'][0]['page_image'], bundle['pages'][0]['source_page_image'])
                    self.assertEqual(context['parser_artifact_base_directory'], result['parser_artifact_base_directory'])
                else:
                    self.assertEqual(result['paragraphs']['paragraphs'][0]['selected_text'], '1 μg/ml')
                self.assertEqual(analyze.call_args.args[1]['blocks'][0]['text'], span['content'])
                normalize = image_normalize if image_mode else dual_normalize
                self.assertEqual(normalize.call_count, 3)
                (dual_normalize if image_mode else image_normalize).assert_not_called()
                for call in normalize.call_args_list:
                    self.assertEqual(call.kwargs['profile'], profile['parser'])
                    self.assertNotIn('parse_result_sha256', call.kwargs['profile'])
                self.assertEqual(validate.call_count, 3)
                self.assertEqual({p.relative_to(parse):p.read_bytes() for p in parse.rglob('*') if p.is_file()}, before)
                self.assertEqual((evidence/'parser_raw/parser/source/hybrid_auto/ocr/images/panel.jpg').read_bytes(), b'exact secondary crop pixels')
                self.assertEqual((evidence/'parser_raw/parser/source/hybrid_auto/raster/page-0001.png').read_bytes(),
                                 b'exact original 200 DPI pixels')
                manifest = json.loads((evidence/'manifest.json').read_text(encoding='utf-8'))
                def republish_export():
                    for record in manifest['files']:
                        path = evidence / record['path']
                        record.update(sha256=file_hash(path), bytes=path.stat().st_size)
                    write_json(evidence/'manifest.json', manifest)
                if image_mode:
                    self.assertEqual(manifest['image_transcription']['raster_manifest_sha256'], bundle['raster_manifest_sha256'])
                    self.assertNotIn('dual_transcription', manifest)
                    raster = Path(result['parser_artifact_base_directory']) / bundle['pages'][0]['source_page_image']['path']
                    pixels = raster.read_bytes()
                    raster.write_bytes(b'different rendered pixels')
                    republish_export()
                    with self.assertRaises(PalimpsestError) as failure:
                        read_evidence(evidence)
                    self.assertEqual(failure.exception.code, 'evidence_artifact_changed')
                    raster.write_bytes(pixels)
                    republish_export()
                    # A rehashed envelope does not make another PDF the original Data.
                    source = evidence/'source.pdf'
                    original = source.read_bytes()
                    source.write_bytes(b'different Data PDF bytes')
                    republish_export()
                    with self.assertRaises(PalimpsestError) as failure:
                        read_evidence(evidence)
                    self.assertEqual(failure.exception.code, 'evidence_source_changed')
                    source.write_bytes(original)
                # Rehashing the export envelope cannot replace retained source text.
                for disguise_as_native in (False, True):
                    with self.subTest(adapter=adapter, disguise_as_native=disguise_as_native):
                        changed = deepcopy(bundle)
                        changed['blocks'][0]['text'] = 'unbound text'
                        if disguise_as_native:
                            changed['profile'].update(adapter_version='mineru-hybrid-preproc-v1',
                                parse_result_sha256=file_hash(evidence/'parse_result.json'))
                        write_json(evidence/'source_bundle.json', changed)
                        paragraphs = json.loads((evidence/'paragraphs.json').read_text(encoding='utf-8'))
                        paragraphs['source_bundle_sha256'] = digest(changed)
                        write_json(evidence/'paragraphs.json', paragraphs)
                        visual = json.loads((evidence/'visuals/manifest.json').read_text(encoding='utf-8'))
                        visual['source']['bundle_sha256'] = digest(changed)
                        write_json(evidence/'visuals/manifest.json', visual)
                        manifest['source_bundle_sha256'] = digest(changed)
                        republish_export()
                        with self.assertRaises(PalimpsestError) as failure:
                            read_evidence(evidence)
                        self.assertEqual(failure.exception.code, 'evidence_source_changed')

    def test_dual_receipt_cannot_fall_back_when_retained_source_check_differs(self):
        from palimpsest.pdf_evidence import _normalize_evidence_bundle
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_json(root/'source_middle.json', {})
            write_json(root/'palimpsest_source_check.json', {'adapter_version':'mineru-hybrid-dual200-v1', 'data_id':'a'*64})
            write_json(root/'palimpsest_profile.json', {'parser':{'adapter_version':'mineru-hybrid-dual200-v1'}})
            with patch('palimpsest.pdf_evidence.normalize_middle', side_effect=AssertionError('no silent fallback')):
                with self.assertRaises(PalimpsestError) as failure:
                    _normalize_evidence_bundle(root/'source_middle.json', {'adapter_version':'mineru-hybrid-dual200-v1', 'data_id':'b'*64}, 'c'*64)
            self.assertEqual(failure.exception.code, 'evidence_source_changed')
