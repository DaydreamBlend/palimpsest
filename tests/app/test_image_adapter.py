"""Image OCR provenance on synthetic retained bytes; no native PDF/GPU/DB calls."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zlib

from palimpsest.errors import PalimpsestError
from palimpsest.hybrid_profile import IMAGE_PARSER
from palimpsest.image_adapter import normalize_image, digest
from palimpsest.pdf_raster import _page_metadata, RENDER_PROFILE
from palimpsest.source_units import build_source_units, verify_source_units
from test_dual_adapter import middle, write_json
from test_hybrid_runtime import image_source_profile, image_source_receipt


ROOT = Path(__file__).resolve().parents[2]


def png(width, height):
    def chunk(kind, content):
        return struct.pack('>I',len(content)) + kind + content + struct.pack('>I',zlib.crc32(kind+content))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))
            + chunk(b'IDAT',zlib.compress((b'\0'+b'\xff\xff\xff'*width)*height)) + chunk(b'IEND',b''))


@unittest.skipUnless(sys.platform == 'linux', 'Secure retained-artifact I/O requires Linux Docker')
class ImageAdapterTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        pro, pipeline = b'{"files":[]}', b'{"files":[],"pipeline":true}'
        # Only model-manifest pins use synthetic bytes in this scoped fixture.
        # Fixed production profile matching is separately tested without mocks.
        pins = patch.dict(IMAGE_PARSER, models_manifest_sha256=sha256(pro).hexdigest(),
                          pipeline_models_manifest_sha256=sha256(pipeline).hexdigest())
        pins.start()
        self.addCleanup(pins.stop)
        self.profile = image_source_profile()
        self.receipt = image_source_receipt(self.profile)
        self.source = b'Synthetic original PDF bytes; this fixture makes no pixel-fidelity claim.'
        self.data_id = sha256(self.source).hexdigest()
        self.raw = middle(r'*P < 0.05; OVARMA received 1 \mu M; CD4^{+}.', ocr=True)
        write_json(self.root/'image-only_middle.json',self.raw)
        write_json(self.root/'image-only_model.json',[{}])
        (self.root/'image-only_origin.pdf').write_bytes(b'Synthetic retained derived origin PDF')
        (self.root/'source.pdf').write_bytes(self.source)
        (self.root/'palimpsest_renderer.py').write_bytes((ROOT/'src/palimpsest/pdf_raster.py').read_bytes())
        (self.root/'palimpsest_runner.py').write_bytes((ROOT/'deploy/mineru-hybrid/run_parser.py').read_bytes())
        (self.root/'palimpsest_pro_models_manifest.json').write_bytes(pro)
        (self.root/'palimpsest_pipeline_models_manifest.json').write_bytes(pipeline)
        (self.root/'mineru.json').write_bytes(b'{}')
        (self.root/'mineru.log').write_bytes(b'Synthetic retained parser log')
        write_json(self.root/'palimpsest_profile.json',self.profile)
        images = self.root/'images'
        images.mkdir()
        (images/'panel.jpg').write_bytes(b'Synthetic parser image, retained unchanged')
        raster = self.root/'raster'
        raster.mkdir()
        (raster/'page-0001.png').write_bytes(png(201,201))
        (raster/'image-only.pdf').write_bytes(b'Synthetic verified upstream image-only PDF')
        geometry = {'size':[72.12,72.24], 'media_box':[0,0,100,100], 'crop_box':[5,7,77.12,79.24],
                    'effective_bbox':[5,7,77.12,79.24], 'rotation':0,
                    'render_box_policy':'PDFium effective bbox; raw CropBox is retained, not rewritten'}
        page = _page_metadata(geometry,0,[201,201])
        page['png'] = {**page.pop('png_geometry'),**self.asset(raster/'page-0001.png')}
        self.manifest = {'schema_version':'pdf-raster-v1','state':'verified_image_only_input',
            'source':{'data_id':self.data_id,'sha256':self.data_id,'bytes':len(self.source),'page_count':1},
            'renderer':{**RENDER_PROFILE,'script_sha256':self.profile['parser']['renderer_sha256']},
            'pages':[page], 'derived_pdf':{**self.asset(raster/'image-only.pdf'),'is_original_data':False}}
        write_json(raster/'manifest.json',self.manifest)
        for field in ('data_id','document','source_sha256_before','source_sha256_after'):
            self.receipt[field] = self.data_id
        self.receipt['config_sha256'] = sha256((self.root/'mineru.json').read_bytes()).hexdigest()
        original = {'page_index':0,**{k:geometry[k] for k in ('size','media_box','crop_box','rotation')}}
        derived = {'page_index':0,**{k:page['derived_geometry'][k] for k in ('size','media_box','crop_box','rotation')}}
        self.receipt.update(original_pages=[original],parser_input_pages=[derived],
            parser_origin_pages=[deepcopy(derived)],parser_page_sizes=[[72,72]],
            ocr_input_sha256=self.manifest['derived_pdf']['sha256'])
        self.refresh_records()

    def asset(self,path):
        raw = path.read_bytes()
        return {'path':path.name,'bytes':len(raw),'sha256':sha256(raw).hexdigest()}

    def refresh_records(self):
        self.receipt['retained_artifacts'] = [{**self.asset(p),'path':p.relative_to(self.root).as_posix()}
            for p in sorted(self.root.rglob('*')) if p.is_file()]
        self.receipt['raster_manifest_sha256'] = sha256((self.root/'raster/manifest.json').read_bytes()).hexdigest()

    def normalize(self, raw=None, data_id=None):
        return normalize_image(self.raw if raw is None else raw,data_id=data_id or self.data_id,
            artifact_root=self.root,expected_pages=1,profile=self.profile['parser'],receipt=self.receipt)

    def test_exact_ocr_text_raw_hashes_original_coordinates_and_page_pixels_are_preserved(self):
        before = {p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        raw_before = deepcopy(self.raw)
        result = self.normalize()
        block = result['blocks'][0]
        self.assertEqual(self.raw['pdf_info'][0]['preproc_blocks'][0]['lines'][0]['spans'][0]['content'],block['text'])
        self.assertEqual(self.data_id,result['data_id'])
        self.assertEqual('mineru-hybrid-image200-v1',result['profile']['adapter_version'])
        self.assertNotIn('transcription_selection',result)
        self.assertNotIn('native_text',block)
        self.assertFalse(result['source_fidelity_verified'])
        self.assertEqual(digest(self.raw['pdf_info'][0]['preproc_blocks'][0]),block['raw_block_sha256'])
        self.assertEqual([5,5,65,20],block['raw_bbox'])
        self.assertEqual([72,72],block['raw_page_size'])
        self.assertEqual([72.12,72.24],block['page_size'])
        derived = self.manifest['pages'][0]['derived_geometry']['size']
        self.assertAlmostEqual(5*72.12/derived[0],block['bbox'][0])
        self.assertAlmostEqual(5*72.24/derived[1],block['bbox'][1])
        expected_image = {**self.manifest['pages'][0]['png'],'path':'raster/page-0001.png'}
        self.assertEqual(expected_image,result['pages'][0]['source_page_image'])
        self.assertEqual('images/panel.jpg',result['blocks'][1]['image_paths'][0]['path'])
        self.assertEqual('image-only_middle.json',block['raw_artifact']['artifact_path'])
        self.assertEqual('complete',verify_source_units(result,build_source_units(result))['status'])
        self.assertEqual(result,self.normalize())
        self.assertEqual(raw_before,self.raw)
        self.assertEqual(before,{p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_original_identity_and_unretained_input_are_rejected(self):
        with self.assertRaises(PalimpsestError):
            self.normalize(data_id='b'*64)
        changed = deepcopy(self.raw)
        changed['pdf_info'][0]['preproc_blocks'][0]['lines'][0]['spans'][0]['content']='unretained text'
        with self.assertRaises(PalimpsestError):
            self.normalize(changed)
        (self.root/'source.pdf').write_bytes(self.source+b'changed')
        self.refresh_records()
        with self.assertRaises(PalimpsestError):
            self.normalize()

    def test_native_route_or_partial_raw_model_pages_never_fall_back(self):
        for field,value in (('_ocr_enable',False),('_effort','medium'),('_backend','pipeline'),('pdf_info',[])):
            invalid = deepcopy(self.raw)
            invalid[field] = value
            write_json(self.root/'image-only_middle.json',invalid)
            self.refresh_records()
            with self.subTest(field=field),self.assertRaises(PalimpsestError):
                self.normalize(invalid)
        write_json(self.root/'image-only_middle.json',self.raw)
        for model in ([],{},[{},{}]):
            write_json(self.root/'image-only_model.json',model)
            self.refresh_records()
            with self.subTest(model=model),self.assertRaises(PalimpsestError):
                self.normalize()

    def test_missing_or_changed_raw_origin_pixels_and_crops_are_rejected(self):
        for name in ('image-only_model.json','image-only_origin.pdf','raster/page-0001.png','images/panel.jpg'):
            path = self.root/name
            before = path.read_bytes()
            path.write_bytes(before+b'changed')
            with self.subTest(name=name,change='bytes'),self.assertRaises((PalimpsestError,ValueError)):
                self.normalize()
            path.unlink()
            with self.subTest(name=name,change='missing'),self.assertRaises((PalimpsestError,OSError)):
                self.normalize()
            path.write_bytes(before)
        (self.root/'unlisted-middle.json').write_bytes(b'Unlisted raw artifact')
        with self.assertRaises(PalimpsestError):
            self.normalize()

    def test_rehashed_wrong_raster_mapping_or_source_geometry_are_rejected(self):
        original = deepcopy(self.manifest)
        invalid = deepcopy(original)
        invalid['pages'][0]['transforms']['derived_page_top_left_to_source_effective_page_top_left'][0]=2
        write_json(self.root/'raster/manifest.json',invalid)
        self.refresh_records()
        with self.assertRaises(ValueError):
            self.normalize()
        write_json(self.root/'raster/manifest.json',original)
        self.refresh_records()
        self.receipt['original_pages'][0]['crop_box'][0] += 1
        with self.assertRaises(PalimpsestError):
            self.normalize()


if __name__ == '__main__':
    unittest.main()
