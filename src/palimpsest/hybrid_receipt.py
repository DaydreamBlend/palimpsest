"""Database-free verification of retained MinerU runtime/source receipts."""
from hashlib import sha256
import json
import math
from pathlib import PurePosixPath
import re

from .errors import PalimpsestError
from .d2i import SOURCE_ALGORITHMS
from .hybrid_profile import matches_hybrid_parser, matches_dual_parser, matches_image_parser


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                            separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def fail(code, exit_code=4):
    raise PalimpsestError(code, 'D2I 실행 profile과 원본 근거를 확인하세요.', exit_code)


def validate_hybrid_receipt(receipt, *, profile, data_id, middle_name, expected_pages):
    """Bind source checks to this compilation before retaining any canonical I."""
    if (not isinstance(profile, dict) or profile.get('schema_version') != 'source-d2i-v1'
            or not (matches_hybrid_parser(profile.get('parser')) or matches_dual_parser(profile.get('parser'))
                    or matches_image_parser(profile.get('parser')))
            or profile.get('transformation') not in [
                {'algorithm': algorithm, 'schema_version': 'source-information-v1'} for algorithm in SOURCE_ALGORITHMS]
            or profile.get('policy', {}).get('llm_calls') != 0
            or profile.get('policy', {}).get('source_fidelity') != 'source_preserving'
            or profile.get('policy', {}).get('extraction_scope') != 'whole_document'):
        fail('invalid_compilation_profile', 2)
    parser = profile['parser']
    dual = matches_dual_parser(parser)
    image = matches_image_parser(parser)
    expected = {
        'schema_version':'mineru-hybrid-source-v1', 'status':'complete',
        'data_id':data_id, 'document':data_id,
        'source_sha256_before':data_id, 'source_sha256_after':data_id,
        'compilation_profile_sha256':digest(profile),
        'page_count':expected_pages, 'completed_pages':expected_pages,
        'retained_middle_name':middle_name, 'source_relative_path':'source.pdf',
        'image_digest':parser['image_digest'], 'runner_sha256':parser['runner_sha256'],
        'adapter_version':'mineru-hybrid-preproc-v1', 'source_fidelity_verified':False,
        'models_manifest_sha256':parser['models_manifest_sha256'],
        'pro_models_manifest_sha256':parser['models_manifest_sha256'],
        'pipeline_models_manifest_sha256':parser['pipeline_models_manifest_sha256'],
        'pro_repository':parser['model_repository'], 'pro_revision':parser['model_revision'],
        'pro_weight_sha256':parser['model_weight_sha256'],
        'backend':'hybrid-engine', 'effort':'high', 'resolved_engine':'transformers',
        'image_analysis':False, 'formula':True, 'table':True, 'method':'auto', 'language':'ch',
        'device':'cuda', 'gpu_uuid':parser['gpu_uuid'], 'network':'none',
        'network_interfaces':['lo'], 'parser_exit_code':0,
        'cuda_version':'12.8', 'torch_runtime_version':'2.8.0+cu128',
        'geometry_tolerance_points':1.0, 'origin_box_tolerance_points':0.03,
    }
    if dual:
        expected.update(schema_version='mineru-hybrid-dual-source-v1',
            adapter_version='mineru-hybrid-dual200-v1', transcription_mode='native_plus_image200',
            native_input_sha256=data_id, renderer_sha256=parser['renderer_sha256'],
            ocr_enable=True, ocr_parser_exit_code=0, ocr_completed_pages=expected_pages)
    if image:
        expected.update(schema_version='mineru-hybrid-image-source-v1',
            adapter_version='mineru-hybrid-image200-v1', transcription_mode='image200',
            input_mode='image_only_pdf', renderer_sha256=parser['renderer_sha256'], ocr_enable=True)
    if (type(expected_pages) is not int or expected_pages < 1 or not isinstance(receipt, dict)
            or any(receipt.get(key) != value or type(receipt.get(key)) is not type(value)
                   for key, value in expected.items())):
        fail('parser_profile_mismatch')
    for key in ('original_pages', 'parser_origin_pages', 'parser_page_sizes'):
        if not isinstance(receipt.get(key), list) or len(receipt[key]) != expected_pages:
            fail('invalid_parser_output')
    def vector(value, count):
        try:
            return (isinstance(value, list) and len(value) == count
                    and all(type(n) in (int, float) and math.isfinite(n) for n in value))
        except OverflowError:
            return False
    source_pages = receipt['original_pages']
    if image:
        source_pages = receipt.get('parser_input_pages')
        if not isinstance(source_pages, list) or len(source_pages) != expected_pages:
            fail('invalid_parser_output')
        for index, original in enumerate(receipt['original_pages']):
            if (not isinstance(original, dict) or type(original.get('page_index')) is not int
                    or original['page_index'] != index or type(original.get('rotation')) is not int
                    or original['rotation'] != 0
                    or any(not vector(original.get(field), count) for field, count in
                           (('size',2), ('media_box',4), ('crop_box',4)))
                    or min(original['size']) <= 0):
                fail('invalid_parser_output')
    for index, (original, origin, size) in enumerate(zip(source_pages,
            receipt['parser_origin_pages'], receipt['parser_page_sizes'])):
        if (not isinstance(original, dict) or not isinstance(origin, dict)
                or type(original.get('page_index')) is not int or type(origin.get('page_index')) is not int
                or original.get('page_index') != index or origin.get('page_index') != index
                or original.get('rotation') != 0 or origin.get('rotation') != 0
                or not vector(size, 2) or min(size) <= 0):
            fail('invalid_parser_output')
        for field, count in (('size',2), ('media_box',4), ('crop_box',4)):
            if (not vector(original.get(field), count) or not vector(origin.get(field), count)
                    or any(abs(a-b) > 0.03 for a,b in zip(original[field], origin[field]))):
                fail('invalid_parser_output')
        if min(original['size']) <= 0 or any(abs(a-b) > 1.0 for a,b in zip(original['size'], size)):
            fail('invalid_parser_output')
    if not isinstance(receipt.get('versions'), dict) or any(receipt['versions'].get(key) != value for key, value in {
            'mineru':'3.4.5', 'mineru-vl-utils':'1.2.1', 'transformers':'4.57.6', 'accelerate':'1.15.0'}.items()):
        fail('parser_profile_mismatch')
    artifacts = receipt.get('retained_artifacts')
    if not isinstance(artifacts, list):
        fail('invalid_parser_output')
    result = {}
    for item in artifacts:
        if not isinstance(item, dict):
            fail('invalid_parser_output')
        name = item.get('path')
        if (not isinstance(name, str) or not name or '\\' in name or ':' in name
                or name.startswith('/') or any(p in ('', '.', '..') for p in name.split('/'))
                or name in result or type(item.get('bytes')) is not int or item['bytes'] < 0
                or not isinstance(item.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', item['sha256'])):
            fail('invalid_parser_output')
        result[name] = item
    required = {'source.pdf':data_id, 'palimpsest_runner.py':parser['runner_sha256'],
                'mineru.json':receipt.get('config_sha256'),
                'palimpsest_pro_models_manifest.json':parser['models_manifest_sha256'],
                'palimpsest_pipeline_models_manifest.json':parser['pipeline_models_manifest_sha256']}
    if dual:
        required.update({'palimpsest_renderer.py':parser['renderer_sha256'],
                         'raster/manifest.json':receipt.get('raster_manifest_sha256'),
                         'raster/image-only.pdf':receipt.get('ocr_input_sha256')})
        if (type(receipt.get('native_ocr_enable')) is not bool
                or receipt.get('retained_raster_manifest_name') != 'raster/manifest.json'
                or not {receipt.get('retained_ocr_middle_name'), 'mineru_ocr.log'} <= result.keys()):
            fail('parser_profile_mismatch')
        def safe_relative(value):
            return (isinstance(value, str) and value and not any(c in value for c in ('\\', ':', '\x00'))
                    and not value.startswith('/') and all(p not in ('', '.', '..') for p in value.split('/')))
        primary = receipt.get('middle_relative_path')
        secondary = receipt.get('retained_ocr_middle_name')
        if (not safe_relative(primary) or PurePosixPath(primary).name != middle_name
                or not middle_name.endswith('_middle.json') or not safe_relative(secondary)
                or not secondary.startswith('ocr/') or not secondary.endswith('_middle.json')):
            fail('parser_profile_mismatch')
        parent = PurePosixPath(primary).parent
        for role, suffix in (('middle','_middle.json'), ('model','_model.json'), ('origin','_origin.pdf')):
            native_name = middle_name.removesuffix('_middle.json') + suffix
            ocr_name = secondary.removesuffix('_middle.json') + suffix
            if (native_name not in result or ocr_name not in result
                    or receipt.get(role + '_relative_path') != str(parent / native_name)
                    or receipt.get('retained_ocr_' + role + '_name') != ocr_name
                    or receipt.get('ocr_' + role + '_relative_path') != str(parent / ocr_name)):
                fail('parser_profile_mismatch')
        if receipt.get('raster_manifest_relative_path') != str(parent / 'raster/manifest.json'):
            fail('parser_profile_mismatch')
    if image:
        required.update({'palimpsest_renderer.py':parser['renderer_sha256'],
                         'raster/manifest.json':receipt.get('raster_manifest_sha256'),
                         'raster/image-only.pdf':receipt.get('ocr_input_sha256')})
        primary = receipt.get('middle_relative_path')
        if (not isinstance(primary, str) or not primary or any(c in primary for c in ('\\', ':', '\x00'))
                or primary.startswith('/') or any(p in ('', '.', '..') for p in primary.split('/'))
                or PurePosixPath(primary).name != middle_name or not middle_name.endswith('_middle.json')
                or receipt.get('retained_raster_manifest_name') != 'raster/manifest.json'
                or any(key in receipt for key in ('native_input_sha256', 'native_ocr_enable', 'retained_ocr_middle_name'))):
            fail('parser_profile_mismatch')
        parent = PurePosixPath(primary).parent
        for role, suffix in (('middle','_middle.json'), ('model','_model.json'), ('origin','_origin.pdf')):
            name = middle_name.removesuffix('_middle.json') + suffix
            if (name not in result or receipt.get('retained_' + role + '_name') != name
                    or receipt.get(role + '_relative_path') != str(parent / name)):
                fail('parser_profile_mismatch')
        if receipt.get('raster_manifest_relative_path') != str(parent / 'raster/manifest.json'):
            fail('parser_profile_mismatch')
    if (any(result.get(name, {}).get('sha256') != value for name, value in required.items())
            or not {middle_name, 'palimpsest_profile.json', 'mineru.json', 'mineru.log'} <= result.keys()
            or 'palimpsest_source_check.json' in result):
        fail('parser_profile_mismatch')
    return result

