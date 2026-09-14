"""Preserve one image200 OCR transcription with exact original-PDF provenance."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath

from .artifact_store import _directory, _file, _read_payload
from .errors import PalimpsestError
from .hybrid_profile import matches_image_parser
from .hybrid_receipt import digest, validate_hybrid_receipt
from .mineru_adapter import normalize_middle
from .pdf_raster import verify_render
from .pdf_raster_adapter import ADAPTER_VERSION, map_to_original


def _require(condition):
    if not condition:
        raise PalimpsestError('invalid_image_transcription', '이미지 OCR과 원본 PDF 근거의 결속을 확인하세요.', 4)


def _read_retained(root, name, records):
    _require(isinstance(name, str) and name and not any(c in name for c in ('\\', ':', '\x00'))
             and not PurePosixPath(name).is_absolute()
             and all(p not in ('', '.', '..') for p in name.split('/')) and name in records)
    record = records[name]
    _require(type(record.get('bytes')) is int and record['bytes'] >= 0)
    path = root.joinpath(*name.split('/'))
    with _directory(path.parent) as parent:
        with _file(parent, path.name) as descriptor:
            payload = _read_payload(descriptor, parent, path.name)
    raw = path.read_bytes()
    _require(len(raw) == record['bytes'] and sha256(raw).hexdigest() == payload.data_id == record.get('sha256'))
    return raw


def normalize_image(middle, *, data_id, artifact_root, expected_pages, profile, receipt):
    """Verify retained bytes and affine metadata; do not alter OCR transcription.

    The frozen runner performs native PDF/pixel checks. This application-side
    verification intentionally uses hashes and metadata without importing PDF
    libraries or claiming a new pixel check.
    """
    _require(matches_image_parser(profile) and isinstance(receipt, dict))
    root = Path(artifact_root)
    artifacts = receipt.get('retained_artifacts')
    _require(isinstance(artifacts, list) and all(isinstance(r, dict) for r in artifacts))
    records = {}
    for record in artifacts:
        name = record.get('path')
        _require(isinstance(name, str) and name not in records)
        records[name] = record
    retained_profile = json.loads(_read_retained(root, 'palimpsest_profile.json', records))
    _require(retained_profile.get('parser') == profile)
    middle_name = receipt.get('retained_middle_name')
    validate_hybrid_receipt(receipt, profile=retained_profile, data_id=data_id,
                            middle_name=middle_name, expected_pages=expected_pages)
    observed = set()
    for path in root.rglob('*'):
        _require(not path.is_symlink())
        if path.is_file():
            observed.add(path.relative_to(root).as_posix())
    _require(observed - {'palimpsest_source_check.json'} == set(records))
    for name in records:
        _read_retained(root, name, records)
    raw = json.loads(_read_retained(root, middle_name, records))
    _require(raw == middle and middle.get('_ocr_enable') is True
             and all(middle.get(key) == value for key, value in
                     {'_backend':'hybrid', '_effort':'high', '_version_name':'3.4.5'}.items()))
    model = json.loads(_read_retained(root, receipt['retained_model_name'], records))
    _require(isinstance(model, list) and len(model) == expected_pages)
    pages = middle.get('pdf_info')
    _require(isinstance(pages, list) and all(isinstance(page, dict) for page in pages)
             and [page.get('page_idx') for page in pages] == list(range(expected_pages))
             and all(type(page.get('page_idx')) is int for page in pages)
             and [page.get('page_size') for page in pages] == receipt['parser_page_sizes'])
    manifest_bytes = _read_retained(root, 'raster/manifest.json', records)
    _require(sha256(manifest_bytes).hexdigest() == receipt['raster_manifest_sha256'])
    manifest = verify_render(root / 'raster', root / 'source.pdf', check_pixels=False,
                             expected_script_sha256=profile['renderer_sha256'])
    _require(manifest == json.loads(manifest_bytes) and manifest['source']['data_id'] == data_id
             and manifest['source']['page_count'] == expected_pages
             and isinstance(manifest['derived_pdf'], dict)
             and manifest['derived_pdf']['sha256'] == receipt['ocr_input_sha256'])
    for index, page in enumerate(manifest['pages']):
        for geometry, expected in ((receipt['original_pages'][index], page['source_geometry']),
                                   (receipt['parser_input_pages'][index], page['derived_geometry']),
                                   (receipt['parser_origin_pages'][index], page['derived_geometry'])):
            _require(type(geometry['page_index']) is int and geometry['page_index'] == index
                     and type(geometry['rotation']) is int and geometry['rotation'] == 0)
            for field in ('size', 'media_box', 'crop_box'):
                _require(len(geometry[field]) == len(expected[field])
                         and all(abs(a-b) <= 0.03 for a,b in zip(geometry[field], expected[field])))
    parsed = normalize_middle(middle, data_id=data_id, artifact_root=root, expected_pages=expected_pages,
                              profile={**profile, 'adapter_version':'mineru-hybrid-preproc-v1'})
    parsed['profile'] = deepcopy(profile)
    _require(parsed['profile']['adapter_version'] == ADAPTER_VERSION)
    result = map_to_original(parsed, manifest, manifest_sha256=receipt['raster_manifest_sha256'])
    result['source_fidelity_verified'] = False
    for page, rendered in zip(result['pages'], manifest['pages']):
        page['source_page_image'] = {**deepcopy(rendered['png']), 'path':'raster/' + rendered['png']['path']}
    raw_artifact = {'artifact_path':middle_name, 'sha256':records[middle_name]['sha256']}
    for block in result['blocks']:
        block['raw_artifact'] = deepcopy(raw_artifact)
        block.pop('anchor_sha256')
        block['anchor_sha256'] = digest({'data_id':data_id, **block})
    return result
