"""Verified selected PDF page views for separately authorized manual D2K.

No database registration, user authorization, parsing, Information creation or
model invocation occurs here. Optional pinned PDF dependencies are imported only
when actually rendering/re-verifying. Metadata-only attachment is not supported.
"""
from contextlib import closing
from hashlib import file_digest
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import stat

from .errors import PalimpsestError

IMAGE = 'sha256:3f9361035fa4d601d54ed524410d89871fe2524047b04a821594485aae93e0d4'
SCHEMA = 'd2k-pdf-source-view-v1'
TRANSFORMS = ('matrix_convention', 'source_pdf_bottom_left_to_pixel_top_left',
              'pixel_top_left_to_source_pdf_bottom_left', 'source_effective_page_top_left_to_pixel_top_left')


def _dependencies(raster):
    try:
        return raster._dependencies()
    except (ImportError, ValueError) as error:
        raise PalimpsestError('d2k_pdf_runtime_required',
            'PDF source view에는 고정 PDFium 5.10.1/Pillow 12.3.0 실행 환경이 필요합니다.', 3) from error


def _require(condition, code):
    if not condition:
        raise PalimpsestError(code, 'D2K PDF 원문 보기의 원본 bytes·페이지·renderer를 확인하세요.', 4)


def _hash(path):
    with Path(path).open('rb') as stream:
        return file_digest(stream, 'sha256').hexdigest()


def _path(value, *, required=False):
    value = Path(value)
    _require('..' not in value.parts, 'unsafe_source_view_path')
    value = Path(os.path.abspath(value))
    for item in (value, *value.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        _require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                 'source_view_symlink_rejected')
    return value.resolve(strict=required)


def _selection(pages):
    _require(isinstance(pages, (list, tuple)) and pages
             and all(type(number) is int and number > 0 for number in pages)
             and len(set(pages)) == len(pages), 'invalid_pdf_page_selection')
    return sorted(pages)


def _source(path, data_id, byte_size):
    _require(isinstance(data_id, str) and re.fullmatch('[0-9a-f]{64}', data_id) is not None
             and type(byte_size) is int and byte_size > 0, 'invalid_original_identity')
    _require(path.is_file() and path.stat().st_size == byte_size and _hash(path) == data_id,
             'original_pdf_changed')
    with path.open('rb') as stream:
        _require(b'%PDF-' in stream.read(1024), 'original_pdf_required')


def _profile(pdfium, raster):
    return {'schema_version': 'd2k-pdf-renderer-v1', 'engine': 'pypdfium2',
        'engine_version': importlib.metadata.version('pypdfium2'), 'pdfium_version': str(pdfium.PDFIUM_INFO),
        'pillow_version': importlib.metadata.version('Pillow'), 'dpi': raster.RENDER_PROFILE['dpi'],
        'long_side_cap_pixels': raster.RENDER_PROFILE['long_side_cap_pixels'], 'pixel_mode': 'RGB',
        'rotation_policy': 'zero_only', 'required_image_digest': IMAGE,
        'implementation_sha256': {'pdf_raster.py': _hash(raster.__file__), 'd2k_pdf.py': _hash(__file__)}}


def _page_metadata(raster, page, index):
    geometry = raster._geometry(page)
    _require(geometry['rotation'] == 0, 'unsupported_pdf_page_rotation')
    width, height = geometry['size']
    _require(all(math.isfinite(value) and value > 0 for value in (width, height)), 'invalid_pdf_page_geometry')
    dpi, cap = raster.RENDER_PROFILE['dpi'], raster.RENDER_PROFILE['long_side_cap_pixels']
    scale = min(dpi / 72, cap / max(width, height))
    while max(math.ceil(width * scale), math.ceil(height * scale)) > cap:
        scale = math.nextafter(scale, 0)
    metadata = raster._page_metadata(geometry, index, [math.ceil(width * scale), math.ceil(height * scale)])
    return {'page_index': index, 'page_number': index + 1, 'page_size': geometry['size'],
        'source_geometry': metadata['source_geometry'],
        'transforms': {name: metadata['transforms'][name] for name in TRANSFORMS},
        'png': metadata['png_geometry']}


def _verify(manifest, source, output, raster, pdfium, Image):
    _require(isinstance(manifest, dict) and manifest.get('schema_version') == SCHEMA
             and manifest.get('state') == 'verified_selected_pages',
             'invalid_pdf_source_view')
    _require(manifest.get('renderer') == _profile(pdfium, raster), 'source_view_renderer_changed')
    original = manifest['source']
    _require(isinstance(original, dict) and original['data_id'] == original['sha256']
             and original['media_type'] == 'application/pdf' and type(original.get('page_count')) is int
             and original['page_count'] > 0,
             'invalid_original_identity')
    _source(source, original['data_id'], original['byte_size'])
    selected = _selection(manifest['selected_page_numbers'])
    _require(isinstance(manifest.get('pages'), list) and all(isinstance(entry, dict)
             and type(entry.get('page_number')) is int and type(entry.get('page_index')) is int
             and isinstance(entry.get('png'), dict) for entry in manifest['pages'])
             and selected == manifest['selected_page_numbers']
             and [entry['page_number'] for entry in manifest['pages']] == selected,
             'source_view_page_selection_changed')
    _require(manifest.get('coverage') == 'selected_physical_pages_only'
             and all(manifest.get(key) == 0 and type(manifest[key]) is int for key in
                     ('canonical_writes', 'd2i_calls', 'information_created', 'model_calls'))
             and manifest.get('actual_model_delivery') is False
             and manifest.get('source_registration_verified') is False, 'invalid_source_view_boundary')
    expected_files = {'manifest.json'}
    with pdfium.PdfDocument(str(source)) as document:
        _require(original['page_count'] == len(document) and max(selected) <= len(document), 'source_view_page_count_changed')
        for entry in manifest['pages']:
            number = entry['page_number']
            name = f'page-{number:04d}.png'
            expected_files.add(name)
            _require(entry['png']['path'] == name, 'unsafe_source_view_asset')
            png = _path(output / name, required=True)
            _require(png.parent == output and png.is_file(), 'unsafe_source_view_asset')
            with closing(document[number - 1]) as page:
                expected = _page_metadata(raster, page, number - 1)
                expected['png'].update(path=name, sha256=_hash(png), byte_size=png.stat().st_size)
                _require(entry == expected, 'source_view_asset_or_geometry_changed')
                with Image.open(png) as stored, raster._raster(page, entry['png']['render_scale']) as rendered:
                    _require(stored.format == 'PNG' and stored.mode == 'RGB' and stored.size == rendered.size
                             and stored.tobytes() == rendered.tobytes(), 'source_view_pixels_changed')
    _require({item.name for item in output.iterdir()} <= expected_files, 'unexpected_source_view_artifact')
    _source(source, original['data_id'], original['byte_size'])
    _require(manifest['renderer'] == _profile(pdfium, raster), 'source_view_renderer_changed')
    return manifest


def render_source(source_path, directory, expected_data_id, page_numbers, *, expected_byte_size=None):
    """Render/verify only the selected physical pages; publish the manifest last."""
    from . import pdf_raster as raster

    source, output = _path(source_path, required=True), _path(directory)
    data_id = expected_data_id
    byte_size = source.stat().st_size if expected_byte_size is None else expected_byte_size
    pages = _selection(page_numbers)
    _source(source, data_id, byte_size)
    _require(not source.is_relative_to(output) and (not output.exists()
             or (output.is_dir() and not any(output.iterdir()))), 'source_view_output_must_be_empty')
    pdfium, Image = _dependencies(raster)
    manifest = {'schema_version': SCHEMA, 'state': 'verified_selected_pages',
        'source': {'data_id': data_id, 'sha256': data_id, 'byte_size': byte_size, 'media_type': 'application/pdf'},
        'selected_page_numbers': pages, 'coverage': 'selected_physical_pages_only', 'renderer': _profile(pdfium, raster),
        'pages': [], 'canonical_writes': 0, 'd2i_calls': 0, 'information_created': 0, 'model_calls': 0,
        'actual_model_delivery': False, 'source_registration_verified': False}
    with pdfium.PdfDocument(str(source)) as document:
        _require(len(document) > 0 and max(pages) <= len(document), 'invalid_pdf_page_selection')
        manifest['source']['page_count'] = len(document)
        output.mkdir(parents=True, exist_ok=True)
        for number in pages:
            with closing(document[number - 1]) as page:
                metadata = _page_metadata(raster, page, number - 1)
                name = f'page-{number:04d}.png'
                with raster._raster(page, metadata['png']['render_scale']) as image:
                    image.save(output / name, format='PNG', dpi=(metadata['png']['dpi_effective'],) * 2)
                metadata['png'].update(path=name, sha256=_hash(output / name), byte_size=(output / name).stat().st_size)
                manifest['pages'].append(metadata)
    _verify(manifest, source, output, raster, pdfium, Image)
    partial = output / '.manifest.partial.json'
    with partial.open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    partial.replace(output / 'manifest.json')
    return manifest


def verify_source(source_path, directory, expected_data_id, *, expected_byte_size=None):
    from . import pdf_raster as raster

    source, output = _path(source_path, required=True), _path(directory, required=True)
    byte_size = source.stat().st_size if expected_byte_size is None else expected_byte_size
    _source(source, expected_data_id, byte_size)
    manifest_path = _path(output / 'manifest.json', required=True)
    _require(manifest_path.is_file(), 'source_view_manifest_missing')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    _require(isinstance(manifest, dict) and isinstance(manifest.get('source'), dict)
             and manifest['source'].get('data_id') == expected_data_id
             and manifest['source'].get('byte_size') == byte_size, 'source_view_request_changed')
    pdfium, Image = _dependencies(raster)
    return _verify(manifest, source, output, raster, pdfium, Image)


