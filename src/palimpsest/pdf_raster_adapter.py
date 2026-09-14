"""Map a new raster parse to original PDF coordinates without rewriting raw data."""
from copy import deepcopy
from hashlib import sha256
import json
import math

from .errors import PalimpsestError

ADAPTER_VERSION = 'mineru-hybrid-image200-v1'


def _digest(value):
    return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
        separators=(',', ':'),allow_nan=False).encode()).hexdigest()


def _require(condition):
    if not condition:
        raise PalimpsestError('invalid_raster_mapping','원본 PDF와 렌더 페이지의 좌표 결속을 확인하세요.',4)


def map_to_original(bundle, manifest, *, manifest_sha256):
    """The caller first verifies the frozen renderer manifest and artifact hashes.

    MinerU regions are points in the derived PDF, even when its reported page
    size is rounded. Use actual derived geometry, never the rounded page width,
    for the affine. Keep raw rectangles, locators and block hashes unchanged.
    """
    _require(bundle['profile'].get('adapter_version')==ADAPTER_VERSION
             and bundle.get('block_collection')=='preproc_blocks'
             and bundle.get('coordinate_system')=='pdf_points_top_left'
             and 'raster_manifest_sha256' not in bundle)
    _require(isinstance(manifest_sha256,str) and len(manifest_sha256)==64
             and all(c in '0123456789abcdef' for c in manifest_sha256))
    _require(manifest['source']['data_id']==bundle['data_id'])
    pages=manifest['pages']; count=len(bundle['pages'])
    _require(len(pages)==count==manifest['source']['page_count'])
    _require([p['source_page_index'] for p in pages]==list(range(count)))
    _require([p['derived_page_index'] for p in pages]==list(range(count)))
    _require([p['page_index'] for p in bundle['pages']]==list(range(count)))
    result=deepcopy(bundle)
    result['raster_manifest_sha256']=manifest_sha256
    result['selection_reason']='explicit_image200_preproc_mapped_to_original_pdf'
    transforms=[]
    for page,mapped in zip(result['pages'],pages):
        original=mapped['source_geometry']['size']; derived=mapped['derived_geometry']['size']
        _require(all(type(n) in (int,float) and math.isfinite(n) and n>0 for n in original+derived))
        _require(mapped['source_geometry']['rotation']==mapped['derived_geometry']['rotation']==0)
        _require(all(abs(a-b)<=1 for a,b in zip(page['page_size'],derived)))
        scale=[original[i]/derived[i] for i in (0,1)]
        transform={'source_coordinate_system':'derived_pdf_points_top_left',
            'target_coordinate_system':'pdf_points_top_left','source_size':derived,
            'target_size':original,'scale':scale,'rotation':0,
            'source_page_index':mapped['derived_page_index'],
            'original_page_index':mapped['source_page_index'],
            'original_effective_bbox':mapped['source_geometry']['effective_bbox'],
            'original_crop_box':mapped['source_geometry']['crop_box'],
            'raster_manifest_sha256':manifest_sha256}
        transforms.append(transform)
        page.update(raw_page_size=page['page_size'],page_size=deepcopy(original),
            coordinate_transform=deepcopy(transform))

    def mapped_box(box,transform):
        if box is None:return None
        _require(isinstance(box,list) and len(box)==4 and all(
            type(n) in (int,float) and math.isfinite(n) for n in box))
        size=transform['source_size']; target=transform['target_size']
        _require(0<=box[0]<=box[2]<=size[0] and 0<=box[1]<=box[3]<=size[1])
        # Preserve exact endpoints instead of allowing floating-point overshoot.
        return [target[i%2] if value==size[i%2] else value*transform['scale'][i%2]
                for i,value in enumerate(box)]

    for block in result['blocks']:
        _require(type(block.get('page_index')) is int and 0<=block['page_index']<count
                 and 'coordinate_transform' not in block and 'raw_bbox' not in block)
        transform=transforms[block['page_index']]
        _require(block['page_size']==bundle['pages'][block['page_index']]['page_size'])
        block['raw_bbox']=deepcopy(block['bbox'])
        block['bbox']=mapped_box(block['bbox'],transform)
        block['raw_page_size']=block['page_size']
        block['page_size']=deepcopy(transform['target_size'])
        block['coordinate_transform']=deepcopy(transform)
        block['upstream_coordinate_system']='derived_pdf_points_top_left'
        block['bbox_policy']='mapped_explicit_region_envelope'
        for field in ('segments','children','line_regions','grounding_regions'):
            for descriptor in block[field]:
                descriptor['raw_bbox']=deepcopy(descriptor.get('bbox'))
                descriptor['bbox']=mapped_box(descriptor.get('bbox'),transform)
        block.pop('anchor_sha256')
        block['anchor_sha256']=_digest({'data_id':result['data_id'],**block})
    return result
