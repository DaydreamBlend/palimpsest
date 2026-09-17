"""Hybrid profile/receipt and preproc contracts; no model, provider, or DB calls."""

from argparse import Namespace
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from palimpsest.compiler_runtime import HYBRID_PARSER, digest, validate_profile, validate_hybrid_receipt
from palimpsest.errors import PalimpsestError
from palimpsest.mineru_adapter import normalize_middle
from palimpsest.hybrid_profile import DUAL_PARSER, IMAGE_PARSER, matches_dual_parser, matches_hybrid_parser, matches_image_parser


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('hybrid_runner', ROOT / 'deploy/mineru-hybrid/run_parser.py')
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
DATA_ID = 'a' * 64


def source_profile():
    return {'schema_version':'source-d2i-v1',
            'parser':{**HYBRID_PARSER, 'gpu_uuid':'GPU-ae1e4ffa-2dba-7ba3-f9f7-1bae0ab26f57',
                      'runner_sha256':runner.digest(ROOT / 'deploy/mineru-hybrid/run_parser.py')},
            'transformation':{'algorithm':'source-units-v1', 'schema_version':'source-information-v1'},
            'policy':{'llm_calls':0, 'source_fidelity':'source_preserving', 'extraction_scope':'whole_document'}}


def source_receipt(profile):
    parser = profile['parser']
    receipt = {'schema_version':'mineru-hybrid-source-v1', 'status':'complete',
        'data_id':DATA_ID, 'document':DATA_ID, 'source_sha256_before':DATA_ID, 'source_sha256_after':DATA_ID,
        'compilation_profile_sha256':digest(profile), 'page_count':1, 'completed_pages':1,
        'retained_middle_name':'source_middle.json', 'source_relative_path':'source.pdf',
        'image_digest':parser['image_digest'], 'runner_sha256':parser['runner_sha256'],
        'adapter_version':'mineru-hybrid-preproc-v1', 'source_fidelity_verified':False,
        'models_manifest_sha256':parser['models_manifest_sha256'],
        'pro_models_manifest_sha256':parser['models_manifest_sha256'],
        'pipeline_models_manifest_sha256':parser['pipeline_models_manifest_sha256'],
        'pro_repository':parser['model_repository'], 'pro_revision':parser['model_revision'],
        'pro_weight_sha256':parser['model_weight_sha256'], 'backend':'hybrid-engine', 'effort':'high',
        'resolved_engine':'transformers', 'image_analysis':False, 'formula':True, 'table':True,
        'method':'auto', 'language':'ch', 'device':'cuda', 'gpu_uuid':parser['gpu_uuid'],
        'network':'none', 'network_interfaces':['lo'], 'parser_exit_code':0, 'cuda_version':'12.8',
        'torch_runtime_version':'2.8.0+cu128',
        'geometry_tolerance_points':1.0, 'origin_box_tolerance_points':0.03,
        'parser_page_sizes':[[600,800]], 'config_sha256':'c' * 64,
        'versions':{'mineru':'3.4.5', 'mineru-vl-utils':'1.2.1', 'transformers':'4.57.6', 'accelerate':'1.15.0'}}
    receipt['original_pages'] = [{'page_index':0, 'size':[600,800], 'media_box':[0,0,600,800],
                                  'crop_box':[0,0,600,800], 'rotation':0}]
    receipt['parser_origin_pages'] = deepcopy(receipt['original_pages'])
    files = {'source.pdf':DATA_ID, 'palimpsest_runner.py':parser['runner_sha256'],
             'palimpsest_pro_models_manifest.json':parser['models_manifest_sha256'],
             'palimpsest_pipeline_models_manifest.json':parser['pipeline_models_manifest_sha256'],
             'source_middle.json':'b' * 64, 'palimpsest_profile.json':'b' * 64,
             'mineru.json':'c' * 64, 'mineru.log':'b' * 64}
    receipt['retained_artifacts'] = [{'path':name, 'sha256':value, 'bytes':1} for name, value in files.items()]
    return receipt


def dual_source_profile():
    profile = source_profile()
    profile['parser'] = {**DUAL_PARSER, 'gpu_uuid':profile['parser']['gpu_uuid'],
                         'runner_sha256':profile['parser']['runner_sha256']}
    return profile


def dual_source_receipt(profile):
    """Synthetic receipt fixture; this does not assert live parsing or pixel proof."""
    receipt = source_receipt(profile)
    receipt.update(schema_version='mineru-hybrid-dual-source-v1', adapter_version='mineru-hybrid-dual200-v1',
        transcription_mode='native_plus_image200', native_input_mode='original_pdf_auto',
        native_input_sha256=DATA_ID, native_ocr_enable=False, renderer_sha256=profile['parser']['renderer_sha256'],
        raster_manifest_sha256='d' * 64, retained_raster_manifest_name='raster/manifest.json',
        raster_manifest_relative_path='parser/source/hybrid_auto/raster/manifest.json',
        middle_relative_path='parser/source/hybrid_auto/source_middle.json',
        model_relative_path='parser/source/hybrid_auto/source_model.json',
        origin_relative_path='parser/source/hybrid_auto/source_origin.pdf',
        ocr_input_sha256='e' * 64, ocr_enable=True, ocr_parser_exit_code=0, ocr_completed_pages=1,
        ocr_parser_origin_pages=deepcopy(receipt['original_pages']), ocr_parser_page_sizes=[[600,800]])
    files = {'source_model.json':'b' * 64, 'source_origin.pdf':'b' * 64,
             'raster/manifest.json':'d' * 64, 'raster/image-only.pdf':'e' * 64,
             'raster/page-0001.png':'f' * 64, 'mineru_ocr.log':'b' * 64,
             'palimpsest_renderer.py':profile['parser']['renderer_sha256']}
    for key, suffix in (('middle','_middle.json'), ('model','_model.json'), ('origin','_origin.pdf')):
        relative = 'ocr/image-only/hybrid_auto/image-only' + suffix
        receipt['retained_ocr_' + key + '_name'] = relative
        receipt['ocr_' + key + '_relative_path'] = 'parser/source/hybrid_auto/' + relative
        files[relative] = 'b' * 64
    receipt['retained_artifacts'].extend({'path':name,'sha256':value,'bytes':1} for name,value in files.items())
    return receipt


def image_source_profile():
    profile = source_profile()
    profile['parser'] = {**IMAGE_PARSER, 'gpu_uuid':profile['parser']['gpu_uuid'],
                         'runner_sha256':profile['parser']['runner_sha256']}
    return profile


def image_source_receipt(profile):
    """Synthetic runtime metadata; exact file and pixel checks have separate tests."""
    receipt = source_receipt(profile)
    parent = 'parser/image-only/hybrid_auto/'
    receipt.update(schema_version='mineru-hybrid-image-source-v1', adapter_version='mineru-hybrid-image200-v1',
        transcription_mode='image200', input_mode='image_only_pdf', ocr_enable=True,
        renderer_sha256=profile['parser']['renderer_sha256'], raster_manifest_sha256='d' * 64,
        ocr_input_sha256='e' * 64, retained_raster_manifest_name='raster/manifest.json',
        raster_manifest_relative_path=parent+'raster/manifest.json',
        parser_input_pages=deepcopy(receipt['original_pages']))
    for record in receipt['retained_artifacts']:
        if record['path'] == 'source_middle.json':
            record['path'] = 'image-only_middle.json'
    for role, suffix in (('middle','_middle.json'), ('model','_model.json'), ('origin','_origin.pdf')):
        name = 'image-only' + suffix
        receipt['retained_' + role + '_name'] = name
        receipt[role + '_relative_path'] = parent + name
    files = {'image-only_model.json':'b'*64, 'image-only_origin.pdf':'b'*64,
             'raster/manifest.json':'d'*64, 'raster/image-only.pdf':'e'*64,
             'raster/page-0001.png':'f'*64, 'palimpsest_renderer.py':profile['parser']['renderer_sha256']}
    receipt['retained_artifacts'].extend({'path':name,'sha256':value,'bytes':1} for name,value in files.items())
    return receipt


class HybridRuntimeTests(unittest.TestCase):
    def test_grouped_profile_is_bound_to_fresh_receipt_and_runner(self):
        profile = source_profile()
        old_receipt = source_receipt(profile)
        profile['transformation']['algorithm'] = 'source-groups-v1'
        self.assertEqual(profile, validate_profile(profile))
        with patch.dict(sys.modules, {'palimpsest.d2i': None}):
            self.assertEqual(digest(profile), runner.validate_profile(profile, DATA_ID, DATA_ID,
                             HYBRID_PARSER['image_digest'], profile['parser']['runner_sha256']))
            profile['transformation']['algorithm'] = 'source-groups-v2'
            self.assertEqual(digest(profile), runner.validate_profile(profile, DATA_ID, DATA_ID,
                             HYBRID_PARSER['image_digest'], profile['parser']['runner_sha256']))
        validate_hybrid_receipt(source_receipt(profile), profile=profile, data_id=DATA_ID,
                                middle_name='source_middle.json', expected_pages=1)
        with self.assertRaises(PalimpsestError):
            validate_hybrid_receipt(old_receipt, profile=profile, data_id=DATA_ID,
                                    middle_name='source_middle.json', expected_pages=1)

    def test_image_profile_is_separate_from_historical_modes_and_fixes_rendering(self):
        profile = image_source_profile()
        self.assertTrue(matches_image_parser(profile['parser']))
        self.assertFalse(matches_dual_parser(profile['parser']))
        self.assertFalse(matches_hybrid_parser(profile['parser']))
        self.assertFalse(matches_image_parser(source_profile()['parser']))
        self.assertFalse(matches_image_parser(dual_source_profile()['parser']))
        self.assertEqual(digest(profile), runner.validate_profile(profile, DATA_ID, DATA_ID,
            HYBRID_PARSER['image_digest'], profile['parser']['runner_sha256']))
        for field, wrong in (('renderer_sha256','b'*64), ('input_mode','original_pdf'),
                             ('transcription_mode','native_plus_image200')):
            invalid = deepcopy(profile)
            invalid['parser'][field] = wrong
            with self.subTest(field=field), self.assertRaises(ValueError):
                runner.validate_profile(invalid, DATA_ID, DATA_ID,
                    HYBRID_PARSER['image_digest'], profile['parser']['runner_sha256'])
        invalid = deepcopy(profile)
        invalid['parser']['renderer']['dpi'] = 144
        self.assertFalse(matches_image_parser(invalid['parser']))

    def test_image_receipt_requires_ocr_complete_raw_and_separate_input_geometry(self):
        profile = image_source_profile()
        receipt = image_source_receipt(profile)
        # A derived page can differ from the original by raster-grid rounding.
        receipt['original_pages'][0]['size'] = [600.2,800.2]
        receipt['original_pages'][0]['crop_box'] = [0,0,600.2,800.2]
        receipt['original_pages'][0]['media_box'] = [0,0,600.2,800.2]
        def validate(value):
            return validate_hybrid_receipt(value, profile=profile, data_id=DATA_ID,
                                           middle_name='image-only_middle.json', expected_pages=1)
        self.assertEqual(len(receipt['retained_artifacts']), len(validate(receipt)))
        for field, wrong in (('ocr_enable',False), ('transcription_mode','native_plus_image200'),
                             ('parser_input_pages',[]), ('source_fidelity_verified',True),
                             ('retained_origin_name','source_origin.pdf'),
                             ('model_relative_path','other/image-only_model.json'),
                             ('raster_manifest_relative_path','other/manifest.json'),
                             ('native_ocr_enable',False)):
            invalid = deepcopy(receipt)
            invalid[field] = wrong
            with self.subTest(field=field), self.assertRaises(PalimpsestError):
                validate(invalid)
        for name in ('image-only_model.json','image-only_origin.pdf','raster/image-only.pdf','palimpsest_renderer.py'):
            invalid = deepcopy(receipt)
            invalid['retained_artifacts'] = [r for r in invalid['retained_artifacts'] if r['path'] != name]
            with self.subTest(missing=name), self.assertRaises(PalimpsestError):
                validate(invalid)

    def test_single_image_parser_call_requires_ocr_without_creating_secondary_fields(self):
        original = source_receipt(source_profile())['original_pages']
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / 'parser'
            directory.mkdir()
            raw = {'_ocr_enable':True, '_backend':'hybrid', '_effort':'high', '_version_name':'3.4.5',
                   'pdf_info':[{'page_idx':0,'page_size':[600,800],'preproc_blocks':[]}]}
            (directory/'image-only_middle.json').write_text(json.dumps(raw), encoding='utf-8')
            (directory/'image-only_model.json').write_text('[{}]', encoding='utf-8')
            (directory/'image-only_origin.pdf').write_bytes(b'Synthetic geometry fixture')
            def execute(command, *, stdout, **kwargs):
                stdout.write('Using transformers as the inference engine for VLM.')
                return Namespace(returncode=0)
            receipt = {}
            with patch.object(runner.subprocess, 'run', side_effect=execute) as invoke, \
                    patch.object(runner, 'geometry', return_value=original):
                runner.parse_pdf(root/'image-only.pdf', directory, root/'mineru.log', original=original,
                    receipt=receipt, status_path=root/'status.json', image_input=True)
                self.assertEqual(1, invoke.call_count)
                self.assertEqual(str(root/'image-only.pdf'), receipt['command'][2])
                self.assertEqual(0, receipt['parser_exit_code'])
                self.assertNotIn('ocr_command', receipt)
                self.assertNotIn('ocr_parser_exit_code', receipt)
                self.assertEqual('image200_ocr', receipt['phase'])
                raw['_ocr_enable'] = False
                (directory/'image-only_middle.json').write_text(json.dumps(raw), encoding='utf-8')
                with self.assertRaises(ValueError):
                    runner.parse_pdf(root/'image-only.pdf', directory, root/'invalid.log', original=original,
                        receipt=receipt, status_path=root/'status.json', image_input=True)

    def test_dual_receipt_requires_both_complete_raw_trees_and_consistent_outer_paths(self):
        profile = dual_source_profile()
        receipt = dual_source_receipt(profile)
        def validate(value):
            return validate_hybrid_receipt(value, profile=profile, data_id=DATA_ID,
                                           middle_name='source_middle.json', expected_pages=1)
        self.assertEqual(len(receipt['retained_artifacts']), len(validate(receipt)))
        mandatory = ['source_model.json', 'source_origin.pdf', receipt['retained_ocr_middle_name'],
                     receipt['retained_ocr_model_name'], receipt['retained_ocr_origin_name']]
        for name in mandatory:
            invalid = deepcopy(receipt)
            invalid['retained_artifacts'] = [r for r in invalid['retained_artifacts'] if r['path'] != name]
            with self.subTest(missing=name), self.assertRaises(PalimpsestError):
                validate(invalid)
        for field, wrong in (
                ('middle_relative_path','other/changed_middle.json'),
                ('model_relative_path','other/source_model.json'),
                ('origin_relative_path','other/source_origin.pdf'),
                ('retained_ocr_model_name','ocr/other_model.json'),
                ('retained_ocr_origin_name','../source_origin.pdf'),
                ('ocr_middle_relative_path','other/image-only_middle.json'),
                ('ocr_model_relative_path','other/image-only_model.json'),
                ('ocr_origin_relative_path','other/image-only_origin.pdf'),
                ('raster_manifest_relative_path','other/manifest.json')):
            invalid = deepcopy(receipt)
            invalid[field] = wrong
            with self.subTest(field=field), self.assertRaises(PalimpsestError):
                validate(invalid)

    def test_dual_profile_is_distinct_and_binds_the_exact_unchanged_renderer(self):
        profile = dual_source_profile()
        self.assertTrue(matches_dual_parser(profile['parser']))
        self.assertFalse(matches_hybrid_parser(profile['parser']))
        self.assertTrue(matches_hybrid_parser(source_profile()['parser']))
        self.assertEqual(runner.digest(ROOT / 'src/palimpsest/pdf_raster.py'), profile['parser']['renderer_sha256'])
        self.assertEqual(digest(profile), runner.validate_profile(profile, DATA_ID, DATA_ID,
            HYBRID_PARSER['image_digest'], profile['parser']['runner_sha256']))
        for field, wrong in (('renderer_sha256','b' * 64), ('native_input_mode','ocr'),
                             ('transcription_mode','image_only'), ('ocr_adapter_version','mineru-middle-v2')):
            invalid = deepcopy(profile)
            invalid['parser'][field] = wrong
            with self.subTest(field=field):
                self.assertFalse(matches_dual_parser(invalid['parser']))
                with self.assertRaises(ValueError):
                    runner.validate_profile(invalid, DATA_ID, DATA_ID,
                        HYBRID_PARSER['image_digest'], profile['parser']['runner_sha256'])
        invalid = deepcopy(profile)
        invalid['parser']['renderer']['dpi'] = 144
        with self.assertRaises(ValueError):
            runner.validate_profile(invalid, DATA_ID, DATA_ID,
                HYBRID_PARSER['image_digest'], profile['parser']['runner_sha256'])

    def test_shared_parser_call_preserves_both_scopes_and_requires_actual_secondary_ocr(self):
        original = source_receipt(source_profile())['original_pages']
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source.pdf'
            source.write_bytes(b'Synthetic parse call input, never sent to a parser')
            native = root / 'native'
            secondary = root / 'secondary'
            def fixture(directory, ocr):
                directory.mkdir()
                raw = {'_ocr_enable':ocr, '_backend':'hybrid', '_effort':'high', '_version_name':'3.4.5',
                       'pdf_info':[{'page_idx':0,'page_size':[600,800],'preproc_blocks':[]}]}
                (directory / 'input_middle.json').write_text(json.dumps(raw), encoding='utf-8')
                (directory / 'input_model.json').write_text('[[]]', encoding='utf-8')
                (directory / 'input_origin.pdf').write_bytes(b'Synthetic geometry fixture')
            fixture(native, False)
            fixture(secondary, True)
            receipt = {}
            def execute(command, *, stdout, **kwargs):
                stdout.write('Using transformers as the inference engine for VLM.')
                return Namespace(returncode=0)
            with patch.object(runner.subprocess, 'run', side_effect=execute) as invoke, \
                    patch.object(runner, 'geometry', return_value=original):
                runner.parse_pdf(source, native, root / 'native.log', original=original,
                    receipt=receipt, status_path=root / 'status.json')
                frozen = (native / 'input_middle.json').read_bytes()
                runner.parse_pdf(source, secondary, root / 'secondary.log', original=original,
                    receipt=receipt, status_path=root / 'status.json', secondary=True)
                self.assertEqual(2, invoke.call_count)
                self.assertEqual(0, receipt['parser_exit_code'])
                self.assertEqual(0, receipt['ocr_parser_exit_code'])
                self.assertEqual(str(native), receipt['command'][receipt['command'].index('-o') + 1])
                self.assertEqual(str(secondary), receipt['ocr_command'][receipt['ocr_command'].index('-o') + 1])
                self.assertEqual(frozen, (native / 'input_middle.json').read_bytes())
                raw_path = secondary / 'input_middle.json'
                raw = json.loads(raw_path.read_text())
                raw['_ocr_enable'] = False
                raw_path.write_text(json.dumps(raw), encoding='utf-8')
                with self.assertRaises(ValueError):
                    runner.parse_pdf(source, secondary, root / 'secondary-invalid.log', original=original,
                        receipt=receipt, status_path=root / 'status.json', secondary=True)

    def test_secondary_failure_never_reports_a_complete_dual_run_or_falls_back(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt = {'parser_exit_code':0, 'completed_pages':0}
            with patch.object(runner.subprocess, 'run', return_value=Namespace(returncode=9)) as invoke:
                with self.assertRaises(RuntimeError):
                    runner.parse_pdf(root / 'image-only.pdf', root / 'secondary', root / 'failure.log',
                        original=[], receipt=receipt, status_path=root / 'status.json', secondary=True)
                self.assertEqual(1, invoke.call_count)
            self.assertEqual('running', receipt['status'])
            self.assertEqual(9, receipt['ocr_parser_exit_code'])
            self.assertEqual(0, receipt['completed_pages'])
            self.assertFalse((root / 'parse_result.json').exists())

    def test_dual_tree_retention_preserves_all_raw_bytes_and_rejects_overwrite(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, retained = root / 'sdk', root / 'retained'
            (source / 'images').mkdir(parents=True)
            (source / 'images/panel.jpg').write_bytes(b'original image bytes')
            (source / 'source_middle.json').write_bytes(b'{"original":"raw"}')
            runner.retain_tree(source, retained)
            self.assertEqual({p.relative_to(source):p.read_bytes() for p in source.rglob('*') if p.is_file()},
                             {p.relative_to(retained):p.read_bytes() for p in retained.rglob('*') if p.is_file()})
            with self.assertRaises(ValueError):
                runner.retain_tree(source, retained)

    def test_real_torch_uuid_and_nvidia_profile_prefix_represent_the_same_gpu(self):
        raw = 'ae1e4ffa-2dba-7ba3-f9f7-1bae0ab26f57'
        requested = 'GPU-' + raw
        for torch_value in (raw, requested):
            for profile_value in (raw, requested):
                with self.subTest(torch=torch_value, profile=profile_value):
                    self.assertEqual(requested, runner.verified_gpu_uuid(torch_value, profile_value))
        with self.assertRaises(ValueError):
            runner.verified_gpu_uuid(raw, 'GPU-9fbbd689-092e-9dc9-cf2e-a6b51f66dcf8')
        for invalid in ('unavailable', '', None, 'GPU-not-a-uuid'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                runner.verified_gpu_uuid(invalid, requested)

    def test_profile_and_runner_share_exact_pins_and_reject_alternates(self):
        profile = source_profile()
        self.assertEqual(profile, validate_profile(deepcopy(profile)))
        self.assertEqual(digest(profile), runner.validate_profile(profile, DATA_ID, DATA_ID,
            HYBRID_PARSER['image_digest'], profile['parser']['runner_sha256']))
        for key, wrong in [('backend','pipeline'), ('effort','medium'), ('engine','vllm'),
                           ('image_digest','sha256:' + 'b' * 64), ('models_manifest_sha256','b' * 64),
                           ('pipeline_models_manifest_sha256','b' * 64), ('image_analysis',True),
                           ('image_analysis',0), ('adapter_version','mineru-middle-v2')]:
            invalid = deepcopy(profile)
            invalid['parser'][key] = wrong
            with self.subTest(key=key), self.assertRaises(PalimpsestError):
                validate_profile(invalid)
            with self.subTest(runner_key=key), self.assertRaises(ValueError):
                runner.validate_profile(invalid, DATA_ID, DATA_ID, HYBRID_PARSER['image_digest'],
                                        profile['parser']['runner_sha256'])

    def test_receipt_binds_data_profile_runner_models_and_all_safe_paths(self):
        profile = source_profile()
        receipt = source_receipt(profile)
        def validate(value):
            return validate_hybrid_receipt(value, profile=profile, data_id=DATA_ID,
                                           middle_name='source_middle.json', expected_pages=1)
        self.assertEqual(8, len(validate(receipt)))
        for key, wrong in [('data_id','b' * 64), ('source_sha256_after','b' * 64),
                           ('compilation_profile_sha256','b' * 64), ('runner_sha256','b' * 64),
                           ('pipeline_models_manifest_sha256','b' * 64), ('source_fidelity_verified',True),
                           ('completed_pages',0), ('retained_middle_name','other_middle.json'),
                           ('original_pages',[{}]), ('parser_page_sizes',[[600,798]])]:
            invalid = deepcopy(receipt)
            invalid[key] = wrong
            with self.subTest(key=key), self.assertRaises(PalimpsestError):
                validate(invalid)
        for name in ('../source.pdf', '/source.pdf', 'C:/source.pdf', 'images\\figure.jpg'):
            invalid = deepcopy(receipt)
            invalid['retained_artifacts'][0]['path'] = name
            with self.subTest(path=name), self.assertRaises(PalimpsestError):
                validate(invalid)
        duplicate = deepcopy(receipt)
        duplicate['retained_artifacts'].append(deepcopy(duplicate['retained_artifacts'][0]))
        with self.assertRaises(PalimpsestError):
            validate(duplicate)

    def test_runner_fails_before_inference_with_durable_status_and_preserves_attempt(self):
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / 'input.pdf'
            source.write_bytes(b'Synthetic failure fixture; never parsed')
            profile_path = base / 'profile.json'
            profile_path.write_text(json.dumps(source_profile()), encoding='utf-8')
            args = Namespace(input=source, output=base / 'attempt', document=DATA_ID,
                             models_dir=base / 'missing-models', profile=profile_path,
                             image_digest=HYBRID_PARSER['image_digest'])
            with patch.object(runner, 'verify_manifest') as verify, self.assertRaises(ValueError):
                runner.run(args)
            verify.assert_not_called()
            before = (args.output / 'status.json').read_bytes()
            receipt = json.loads(before)
            self.assertEqual('failed', receipt['status'])
            self.assertEqual(sha256(source.read_bytes()).hexdigest(), receipt['source_sha256_before'])
            self.assertEqual(receipt['source_sha256_before'], receipt['source_sha256_after'])
            with self.assertRaises(ValueError):
                runner.run(args)
            self.assertEqual(before, (args.output / 'status.json').read_bytes())

    def test_runner_requires_every_preproc_page_and_original_geometry(self):
        original = [{'page_index':i, 'size':[595.26,779.52], 'media_box':[0,0,595.26,779.52],
                     'crop_box':[0,0,595.26,779.52], 'rotation':0} for i in range(2)]
        parsed = [{'page_idx':i, 'page_size':[595,780], 'preproc_blocks':[]} for i in range(2)]
        runner.validate_pages(original, parsed, deepcopy(original))
        for field, value in [('preproc_blocks',None), ('page_size',[595,778]), ('page_idx',0)]:
            invalid = deepcopy(parsed)
            invalid[1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                runner.validate_pages(original, invalid, original)


@unittest.skipUnless(sys.platform == 'linux', 'Secure artifact I/O requires Linux Docker')
class HybridPreprocTests(unittest.TestCase):
    def test_explicit_preproc_even_without_merge_flags_preserves_legacy_selection(self):
        def block(text):
            return {'type':'text', 'bbox':[10,20,100,40], 'lines':[{'spans':[{'type':'text', 'content':text}]}]}
        raw = {'pdf_info':[{'page_idx':i, 'page_size':[600,800], 'preproc_blocks':[block(f'original page {i}')],
                            'para_blocks':[block(f'paragraph projection {i}')]} for i in range(2)]}
        frozen = deepcopy(raw)
        with TemporaryDirectory() as temporary:
            def normalize(value, profile):
                return normalize_middle(value, data_id=DATA_ID, artifact_root=Path(temporary),
                                        expected_pages=2, profile=profile)
            hybrid = normalize(raw, source_profile()['parser'])
            legacy = normalize(raw, {'provider':'mineru', 'version':'3.4.5', 'backend':'pipeline',
                                     'adapter_version':'mineru-middle-v2'})
            self.assertEqual('preproc_blocks', hybrid['block_collection'])
            self.assertEqual('para_blocks', legacy['block_collection'])
            self.assertEqual(['original page 0','original page 1'], [b['text'] for b in hybrid['blocks']])
            self.assertEqual(['paragraph projection 0','paragraph projection 1'], [b['text'] for b in legacy['blocks']])
            self.assertEqual([0,1], [b['page_index'] for b in hybrid['blocks']])
            self.assertEqual('/pdf_info/1/preproc_blocks/0', hybrid['blocks'][1]['raw_locator'])
            self.assertEqual(digest(raw['pdf_info'][1]['preproc_blocks'][0]), hybrid['blocks'][1]['raw_block_sha256'])
            self.assertEqual(frozen, raw)
            missing = deepcopy(raw)
            del missing['pdf_info'][1]['preproc_blocks']
            with self.assertRaises(PalimpsestError):
                normalize(missing, source_profile()['parser'])
            # Raw per-page output is sufficient; postprocessed paragraphs are not required.
            for page in raw['pdf_info']:
                del page['para_blocks']
            self.assertEqual(hybrid, normalize(raw, source_profile()['parser']))


if __name__ == '__main__':
    unittest.main()
