"""Verified dual MinerU transcription, preserving both immutable raw inputs."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath

from .artifact_store import _directory, _file, _read_payload
from .errors import PalimpsestError
from .mineru_adapter import normalize_middle
from .pdf_raster import verify_render
from .pdf_raster_adapter import map_to_original, ADAPTER_VERSION
from .transcription_selection import select_transcription


DUAL_ADAPTER = 'mineru-hybrid-dual200-v1'


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                            separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def require(condition):
    if not condition:
        raise PalimpsestError('invalid_dual_transcription', '두 MinerU 전사와 원본 근거의 결속을 확인하세요.', 4)


def read_retained(root, name, records):
    require(isinstance(name, str) and name and not any(c in name for c in ('\\', ':', '\x00'))
            and not PurePosixPath(name).is_absolute()
            and all(p not in ('', '.', '..') for p in name.split('/')) and name in records)
    path = root.joinpath(*name.split('/'))
    with _directory(path.parent) as parent:
        with _file(parent, path.name) as descriptor:
            payload = _read_payload(descriptor, parent, path.name)
    require(payload.data_id == records[name]['sha256'] and path.stat().st_size == records[name]['bytes'])
    # Re-read below is checked against the same frozen hash, including a racing writer.
    raw = path.read_bytes()
    require(sha256(raw).hexdigest() == payload.data_id)
    return raw


def normalize_dual(middle, *, data_id, artifact_root, expected_pages, profile, receipt):
    """The receipt's runtime/profile fields are checked by Compiler Runtime.

    This shared adapter additionally checks retained bytes, raster identity and
    original/derived geometry before aligning any characters. It also serves
    read-only evidence export, using the identical selection implementation.
    """
    root = Path(artifact_root)
    require(profile.get('adapter_version') == DUAL_ADAPTER
            and receipt.get('schema_version') == 'mineru-hybrid-dual-source-v1'
            and receipt.get('adapter_version') == DUAL_ADAPTER
            and receipt.get('data_id') == data_id
            and receipt.get('native_input_sha256') == data_id
            and type(receipt.get('native_ocr_enable')) is bool
            and receipt.get('ocr_enable') is True
            and type(receipt.get('ocr_parser_exit_code')) is int and receipt['ocr_parser_exit_code'] == 0
            and type(receipt.get('ocr_completed_pages')) is int and receipt['ocr_completed_pages'] == expected_pages
            and receipt.get('renderer_sha256') == profile.get('renderer_sha256'))
    records = {r['path']: r for r in receipt['retained_artifacts']}
    require(len(records) == len(receipt['retained_artifacts']))
    # No SDK image, raw text, or rendering artifact is silently excluded.
    for name in records:
        read_retained(root, name, records)
    for name in (receipt['retained_middle_name'].removesuffix('_middle.json') + '_model.json',
                 receipt['retained_ocr_model_name']):
        model = json.loads(read_retained(root, name, records))
        require(isinstance(model, list) and len(model) == expected_pages)
    raw_native = json.loads(read_retained(root, receipt['retained_middle_name'], records))
    require(raw_native == middle)
    require(type(middle.get('_ocr_enable')) is bool and middle['_ocr_enable'] == receipt['native_ocr_enable'])
    require(all(middle.get(k) == v for k,v in {'_backend':'hybrid', '_effort':'high', '_version_name':'3.4.5'}.items()))
    raster_name = receipt['retained_raster_manifest_name']
    require(raster_name == 'raster/manifest.json')
    raster_bytes = read_retained(root, raster_name, records)
    require(sha256(raster_bytes).hexdigest() == receipt['raster_manifest_sha256'])
    require(records['palimpsest_renderer.py']['sha256'] == profile['renderer_sha256'])
    manifest = verify_render(root / 'raster', root / 'source.pdf', check_pixels=False,
                             expected_script_sha256=profile['renderer_sha256'])
    require(manifest == json.loads(raster_bytes) and manifest['source']['data_id'] == data_id
            and manifest['source']['page_count'] == expected_pages
            and manifest['derived_pdf']['sha256'] == receipt['ocr_input_sha256'])
    for name in ('original_pages', 'ocr_parser_origin_pages', 'ocr_parser_page_sizes'):
        require(isinstance(receipt.get(name), list) and len(receipt[name]) == expected_pages)
    for index, page in enumerate(manifest['pages']):
        original = receipt['original_pages'][index]
        derived = receipt['ocr_parser_origin_pages'][index]
        require(original['page_index'] == derived['page_index'] == index
                and original['rotation'] == derived['rotation'] == 0)
        for field in ('size', 'media_box', 'crop_box'):
            require(len(original[field]) == len(page['source_geometry'][field])
                    and all(abs(a-b) <= 0.03 for a,b in zip(original[field], page['source_geometry'][field])))
            require(len(derived[field]) == len(page['derived_geometry'][field])
                    and all(abs(a-b) <= 0.03 for a,b in zip(derived[field], page['derived_geometry'][field])))
        require(len(receipt['ocr_parser_page_sizes'][index]) == 2 and all(abs(a-b) <= 1.0
                for a,b in zip(receipt['ocr_parser_page_sizes'][index], page['derived_geometry']['size'])))
    native = normalize_middle(middle, data_id=data_id, artifact_root=root,
        expected_pages=expected_pages, profile={**profile, 'adapter_version':'mineru-hybrid-preproc-v1'})
    for page, mapped in zip(native['pages'], manifest['pages']):
        page['raw_page_size'] = page['page_size']
        page['page_size'] = deepcopy(mapped['source_geometry']['size'])
    for block in native['blocks']:
        block['raw_artifact'] = {'artifact_path':receipt['retained_middle_name'],
                                 'sha256':records[receipt['retained_middle_name']]['sha256']}
        block['raw_page_size'] = block['page_size']
        block['page_size'] = deepcopy(native['pages'][block['page_index']]['page_size'])
        for region in [block, *block['segments'], *block['children'], *block['line_regions'], *block['grounding_regions']]:
            if region.get('bbox') is not None:
                x0,y0,x1,y1 = region['bbox']
                require(0 <= x0 <= x1 <= block['page_size'][0] and 0 <= y0 <= y1 <= block['page_size'][1])
        block.pop('anchor_sha256')
        block['anchor_sha256'] = digest({'data_id':data_id, **block})
    ocr_name = receipt['retained_ocr_middle_name']
    require(ocr_name.startswith('ocr/') and ocr_name.endswith('_middle.json'))
    ocr_middle = json.loads(read_retained(root, ocr_name, records))
    require(ocr_middle.get('_ocr_enable') is True and all(ocr_middle.get(k) == v
            for k,v in {'_backend':'hybrid', '_effort':'high', '_version_name':'3.4.5'}.items()))
    require([p['page_idx'] for p in ocr_middle['pdf_info']] == list(range(expected_pages))
            and [p['page_size'] for p in ocr_middle['pdf_info']] == receipt['ocr_parser_page_sizes'])
    ocr = normalize_middle(ocr_middle, data_id=data_id, artifact_root=(root / ocr_name).parent,
        expected_pages=expected_pages, profile={**profile, 'adapter_version':'mineru-hybrid-preproc-v1'})
    ocr['profile']['adapter_version'] = ADAPTER_VERSION
    ocr = map_to_original(ocr, manifest, manifest_sha256=receipt['raster_manifest_sha256'])
    prefix = PurePosixPath(ocr_name).parent
    ocr_source = {'artifact_path':ocr_name, 'sha256':records[ocr_name]['sha256']}
    for block in ocr['blocks']:
        block['raw_artifact'] = deepcopy(ocr_source)
        assets = [*block['image_paths'], *(s['image_path'] for s in block['segments'] if 'image_path' in s)]
        seen = set()
        for asset in assets:
            if id(asset) not in seen:
                seen.add(id(asset))
                asset['path'] = str(prefix / asset['path'])
        block.pop('anchor_sha256')
        block['anchor_sha256'] = digest({'data_id':data_id, **block})
    projection = select_transcription(native, ocr, ocr_source=ocr_source)
    selected = deepcopy(native)
    selected['profile'] = deepcopy(profile)
    selected['selection_reason'] = 'original_pdf_auto_with_localized_image_ocr_glyph_preference'
    selected['native_bundle_sha256'] = digest(native)
    selected['native_raw_artifact'] = {'artifact_path':receipt['retained_middle_name'],
                                      'sha256':records[receipt['retained_middle_name']]['sha256']}
    selected['ocr_bundle'] = ocr
    selected['transcription_selection'] = projection
    choices = {r['block_id']: r for r in projection['blocks']}
    require(len(choices) == len(selected['blocks']))
    for block in selected['blocks']:
        choice = choices[block['block_id']]
        require(choice['native_text'] == block['text'])
        block['native_text'] = block['text']
        block['native_anchor_sha256'] = block.pop('anchor_sha256')
        block['native_raw_artifact'] = deepcopy(selected['native_raw_artifact'])
        block['transcription_selection'] = deepcopy(choice)
        block['text'] = choice['selected_text']
        block['anchor_sha256'] = digest({'data_id':data_id, **block})
    return selected
