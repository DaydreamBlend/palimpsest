"""Add registered-original page images as new I, without rewriting parser I."""

from copy import deepcopy
import math

from .data import data_id
from .errors import PalimpsestError
from .source_groups import build_source_groups, group_content_segments
from .source_units import _digest, _proposal, build_source_units, verify_source_units


SOURCE_PAGE_GROUPS_VERSION = 'source-groups-pages-v1'
PAGE_COLLECTION = 'original_page_facsimile'


def _fail():
    raise PalimpsestError('source_page_mismatch', '원본 페이지 이미지의 Data·geometry·hash를 확인하세요.', 4)


def _geometry(page, renderer):
    scale = renderer.get('scale')
    if type(scale) not in (int,float) or not math.isfinite(scale) or scale <= 0:
        _fail()
    for key in ('source_box','cropbox','mediabox'):
        box = page.get(key)
        if (not isinstance(box,list) or len(box) != 4
                or any(type(n) not in (int,float) or not math.isfinite(n) for n in box)
                or box[2] <= box[0] or box[3] <= box[1]):
            _fail()
    media,crop,source = page['mediabox'],page['cropbox'],page['source_box']
    intersection = [max(media[0],crop[0]),max(media[1],crop[1]),min(media[2],crop[2]),min(media[3],crop[3])]
    rotation = page.get('rotation')
    if type(rotation) is not int or rotation not in (0,90,180,270) or any(abs(a-b)>1e-5 for a,b in zip(source,intersection)):
        _fail()
    size = [source[2]-source[0],source[3]-source[1]]
    if rotation in (90,270):
        size.reverse()
    if (len(page['page_size']) != 2 or any(abs(a-b)>1e-5 for a,b in zip(page['page_size'],size))
            or page['page_image']['pixel_size'] != [math.ceil(n*scale) for n in page['page_size']]):
        _fail()


def add_page_blocks(bundle, visuals, *, evidence_manifest_sha256):
    """Bind already-verified evidence page images; this function performs no I/O."""
    source = visuals.get('source', {})
    pages = visuals.get('pages', [])
    if (bundle.get('source_page_supplement') is not None
            or source.get('data_id') != bundle['data_id']
            or source.get('pdf_sha256') != bundle['data_id']
            or source.get('bundle_sha256') != _digest(bundle)
            or type(source.get('pdf_size_bytes')) is not int or source['pdf_size_bytes'] <= 0
            or [p.get('page_index') for p in pages] != list(range(len(bundle['pages'])))
            or source.get('renderer', {}).get('name') != 'pypdfium2'
            or source.get('renderer', {}).get('annotations') is not True):
        _fail()
    data_id(evidence_manifest_sha256)
    result = deepcopy(bundle)
    supplement = {'algorithm': SOURCE_PAGE_GROUPS_VERSION, 'parent_bundle_sha256': _digest(bundle),
        'evidence_manifest_sha256': evidence_manifest_sha256, 'renderer': deepcopy(source['renderer']),
        'renderer_sha256': _digest(source['renderer']), 'original_pdf_sha256': bundle['data_id'],
        'original_pdf_byte_size': source['pdf_size_bytes'], 'pages': deepcopy(pages)}
    result['source_page_supplement'] = supplement
    for page in pages:
        size, image = page['page_size'], page['page_image']
        expected_size = bundle['pages'][page['page_index']]['page_size']
        if (len(size) != 2 or any(type(n) not in (int, float) or not math.isfinite(n) or n <= 0 for n in size)
                or size != expected_size
                or type(image.get('size_bytes')) is not int or image['size_bytes'] <= 0
                or len(image.get('pixel_size', [])) != 2
                or any(type(n) is not int or n <= 0 for n in image['pixel_size'])):
            _fail()
        data_id(image['sha256'])
        _geometry(page, source['renderer'])
        ref = f"/original_page_facsimile/{page['page_index']}"
        provenance = {'data_id': bundle['data_id'], 'page_index': page['page_index'],
            'source_box': page['source_box'], 'cropbox': page['cropbox'], 'mediabox': page['mediabox'],
            'rotation': page['rotation'], 'pixel_size': image['pixel_size'],
            'renderer': deepcopy(source['renderer']), 'renderer_sha256': supplement['renderer_sha256'],
            'evidence_manifest_sha256': evidence_manifest_sha256, 'image_sha256': image['sha256'],
            'scope': 'rendered_visible_page_with_annotations', 'ocr_text_complete': False,
            'verification': 'retained_original_renderer_receipt_and_asset_hashes; not_new_pixel_rerender'}
        indices = [b.get('upstream_metadata', {}).get('index', 0) for b in bundle['blocks']
                   if b['page_index'] == page['page_index']]
        index = max((n for n in indices if type(n) in (int,float) and math.isfinite(n)), default=0) + 1
        result['blocks'].append({'block_id': ref, 'type': 'image', 'page_index': page['page_index'],
            'page_size': deepcopy(size), 'bbox': [0, 0, *size], 'raw_locator': ref,
            'source_collection': PAGE_COLLECTION, 'anchor_sha256': _digest(provenance),
            'text': '', 'supported': True, 'unsupported': [],
            'image_paths': [{'path': f"original_pages/page-{page['page_index']:04d}.png", 'sha256': image['sha256']}],
            'upstream_metadata': {'index': index}, 'facsimile_provenance': provenance,
            'grounding_regions': [{'type': PAGE_COLLECTION, 'bbox': [0, 0, *size], 'raw_locator': ref}]})
    return result


def parent_bundle(bundle):
    value = deepcopy(bundle)
    supplement = value.pop('source_page_supplement', None)
    if not isinstance(supplement, dict) or supplement.get('algorithm') != SOURCE_PAGE_GROUPS_VERSION:
        _fail()
    value['blocks'] = [b for b in value['blocks'] if b.get('source_collection') != PAGE_COLLECTION]
    if _digest(value) != supplement['parent_bundle_sha256']:
        _fail()
    expected = add_page_blocks(value, {'source': {'data_id': value['data_id'],
        'pdf_sha256': supplement['original_pdf_sha256'], 'pdf_size_bytes': supplement['original_pdf_byte_size'],
        'bundle_sha256': _digest(value), 'renderer': supplement['renderer']}, 'pages': supplement['pages']},
        evidence_manifest_sha256=supplement['evidence_manifest_sha256'])
    if expected != bundle:
        _fail()
    return value


def build_page_groups(bundle):
    original = parent_bundle(bundle)
    proposals = build_source_groups(original)
    for block in bundle['blocks']:
        if block.get('source_collection') == PAGE_COLLECTION:
            proposals.append(_proposal('image', f"Original page {block['page_index']+1}", '',
                                       [block['block_id']], block['block_id']))
    return proposals


def page_content_segments(bundle, proposal):
    if proposal['image_block_id'] and proposal['image_block_id'].startswith('/original_page_facsimile/'):
        block = next(b for b in bundle['blocks'] if b['block_id'] == proposal['image_block_id'])
        return [{'source_block_id': block['block_id'], 'page_index': block['page_index'],
            'raw_locator': block['raw_locator'], 'anchor_sha256': block['anchor_sha256'],
            'source_char_range': None, 'char_start': None, 'char_end': None,
            'text_origin': 'original_page_facsimile'}]
    return group_content_segments(parent_bundle(bundle), proposal)


def verify_page_groups(bundle, proposals):
    expected = build_page_groups(bundle)
    if proposals != expected:
        _fail()
    ledger = verify_source_units(bundle, build_source_units(bundle))
    original = parent_bundle(bundle)
    ledger.update(version=SOURCE_PAGE_GROUPS_VERSION, proposal_count=len(proposals),
        original_block_count=len(original['blocks'])-len(original.get('required_figures', [])),
        retained_block_count=len(bundle['blocks']),
        proposal_set_sha256=_digest(proposals), page_facsimile_count=len(bundle['pages']),
        source_coverage='all_rendered_visible_pages_preserved', ocr_text_complete=False,
        unit_manifest=[{'ordinal': n, **{k:p[k] for k in ('kind','unit_type','block_ids','image_block_id')},
                        'content_segments': page_content_segments(bundle,p)} for n,p in enumerate(proposals)])
    return ledger
