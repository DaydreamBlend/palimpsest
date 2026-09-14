"""Attach explicitly reviewed original-PDF Figure regions to retained MinerU blocks.

This is an additive repair input, not an alternative document parser. The pinned
inventory records reviewed region boundaries; structural checks cannot prove the
reviewer's completeness or the semantic correctness of a caption association.
"""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from .artifact_store import _directory, _file, _read_payload
from .data import data_id as validate_digest
from .errors import PalimpsestError
from .mineru_adapter import _asset, _bbox, _canonical


INVENTORY_NAME = 'palimpsest_figures.json'


def _fail():
    raise PalimpsestError('invalid_figure_inventory', 'Figure inventory 또는 원문 근거가 일치하지 않습니다.', 4)


def attach_figures(bundle, *, artifact_root, expected_sha256, middle_sha256):
    """Return additive Figure blocks; leave original normalized blocks untouched."""
    validate_digest(expected_sha256)
    validate_digest(middle_sha256)
    root = Path(artifact_root)
    path = root / INVENTORY_NAME
    if path.is_symlink() or not path.is_file():
        _fail()
    data = path.read_bytes()
    if sha256(data).hexdigest() != expected_sha256:
        _fail()
    try:
        inventory = json.loads(data)
    except (ValueError, UnicodeError):
        _fail()
    if (not isinstance(inventory, dict) or inventory.get('schema_version') != 'figure-inventory-v1'
            or inventory.get('data_id') != bundle['data_id']
            or inventory.get('middle_sha256') != middle_sha256
            or inventory.get('extraction_scope') not in ('figures_only', 'whole_document')
            or inventory.get('source') != 'reviewed_original_pdf_regions'
            or not isinstance(inventory.get('renderer'), dict)
            or not inventory['renderer']
            or not isinstance(inventory.get('figures'), list) or not inventory['figures']):
        _fail()
    output = deepcopy(bundle)
    blocks = {b['block_id']: b for b in bundle['blocks']}
    pages = {p['page_index']: p['page_size'] for p in bundle['pages']}
    required, numbers, used_visuals = [], set(), set()
    for index, figure in enumerate(inventory['figures']):
        if not isinstance(figure, dict):
            _fail()
        number, page = figure.get('number'), figure.get('page_index')
        if (type(number) is not int or number < 1 or number in numbers
                or type(page) is not int or page not in pages):
            _fail()
        numbers.add(number)
        locator = f'{INVENTORY_NAME}#/figures/{index}'
        bbox = _bbox(figure.get('bbox'), pages[page], locator)
        if bbox[0] == bbox[2] or bbox[1] == bbox[3]:
            _fail()
        members, captions = figure.get('member_block_ids'), figure.get('caption_block_ids')
        for refs in (members, captions):
            if (not isinstance(refs, list) or not refs
                    or any(not isinstance(ref, str) or ref not in blocks for ref in refs)
                    or len(set(refs)) != len(refs)):
                _fail()
        if any(blocks[ref]['page_index'] != page for ref in members):
            _fail()
        if any(not isinstance(blocks[ref].get('text'), str) or not blocks[ref]['text'].strip()
               for ref in captions):
            _fail()
        visuals = {ref for ref in members if blocks[ref]['image_paths']}
        if not visuals or used_visuals & visuals:
            _fail()
        used_visuals.update(visuals)
        # All visual block centers in the declared full-body region must belong
        # to this Figure. This catches a dropped panel without guessing labels.
        enclosed = set()
        for ref, block in blocks.items():
            if block['page_index'] != page or not block['image_paths']:
                continue
            boxes = [child['bbox'] for child in block.get('children', [])
                     if child.get('type') in ('image_body', 'chart_body', 'table_body')]
            box = boxes[0] if boxes else block.get('upstream_bbox', block['bbox'])
            x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            if bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]:
                enclosed.add(ref)
        if enclosed != visuals:
            _fail()
        image = figure.get('image')
        if (not isinstance(image, dict) or type(image.get('byte_size')) is not int
                or image['byte_size'] < 1):
            _fail()
        actual = _asset(root, image.get('path'), locator + '/image')
        image_path = root / actual['path']
        with _directory(image_path.parent) as parent, _file(parent, image_path.name) as descriptor:
            measured = _read_payload(descriptor, parent, image_path.name)
        if (actual['sha256'] != image.get('sha256') or measured.data_id != image['sha256']
                or measured.byte_size != image['byte_size']):
            _fail()
        block_id, figure_id = f'/figures/{index}', f'figure:{number}'
        if block_id in blocks:
            _fail()
        group = {'figure_id': figure_id, 'number': number, 'block_id': block_id,
                 'member_block_ids': members, 'caption_block_ids': captions}
        block = {
            'block_id': block_id, 'type': 'image', 'page_index': page,
            'bbox': bbox, 'page_size': pages[page], 'upstream_bbox': None,
            'bbox_policy': 'reviewed_original_pdf_figure_region',
            'grounding_regions': [{'raw_locator': locator, 'type': 'image', 'bbox': bbox}],
            'raw_locator': locator, 'source_collection': 'original_pdf_figure_regions',
            'text': f'Figure {number}: complete graphical body; read the linked caption/context blocks.',
            'image_paths': [actual], 'supported': True, 'unsupported': [], 'empty': False,
            'figure_id': figure_id, 'figure_number': number,
            'member_block_ids': members, 'caption_block_ids': captions,
            'figure_provenance': {'inventory_sha256': expected_sha256,
                                  'data_id': bundle['data_id'], 'middle_sha256': middle_sha256,
                                  'renderer': inventory['renderer'],
                                  'source_region': figure.get('source_region', {})},
        }
        block['anchor_sha256'] = sha256(_canonical(block)).hexdigest()
        output['blocks'].append(block)
        required.append(group)
    output['required_figures'] = required
    output['extraction_scope'] = inventory['extraction_scope']
    output['figure_inventory_sha256'] = expected_sha256
    return output
