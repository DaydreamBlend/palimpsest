"""Dual raw/projection integrity on synthetic retained files; no PDF/GPU/DB calls."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
import unittest
import zlib

from palimpsest.dual_adapter import normalize_dual, digest
from palimpsest.errors import PalimpsestError
from palimpsest.pdf_raster import _page_metadata, RENDER_PROFILE
from palimpsest.source_units import build_source_units, verify_source_units
from test_hybrid_runtime import dual_source_profile, dual_source_receipt


ROOT = Path(__file__).resolve().parents[2]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def png():
    def chunk(kind, content):
        return struct.pack('>I', len(content)) + kind + content + struct.pack('>I', zlib.crc32(kind + content))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 200,200,8,2,0,0,0))
            + chunk(b'IDAT', zlib.compress((b'\0' + b'\xff\xff\xff' * 200) * 200)) + chunk(b'IEND', b''))


def middle(text, *, ocr):
    return {'_backend':'hybrid', '_effort':'high', '_version_name':'3.4.5', '_ocr_enable':ocr,
        'pdf_info':[{'page_idx':0,'page_size':[72,72], 'preproc_blocks':[
            {'type':'text','bbox':[5,5,65,20], 'lines':[{'bbox':[5,5,65,20], 'spans':[
                {'type':'text','bbox':[5,5,65,20],'content':text}]}]},
            {'type':'image','bbox':[5,25,65,55], 'blocks':[
                {'type':'image_body','bbox':[5,25,65,55], 'lines':[{'spans':[
                    {'type':'image','bbox':[5,25,65,55],'image_path':'panel.jpg'}]}]}]}],
            'discarded_blocks':[], 'para_blocks':[]}]}


@unittest.skipUnless(sys.platform == 'linux', 'Secure retained-artifact checks require Linux Docker')
class DualAdapterTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.profile = dual_source_profile()
        self.receipt = dual_source_receipt(self.profile)
        self.source = b'Synthetic original Data bytes; pixel inference is not part of this fixture.'
        self.data_id = sha256(self.source).hexdigest()
        self.native = middle('OVA-RMA received 1 mM FBG.', ocr=False)
        self.ocr = middle(r'OVARMA received 1 \mu M FBG.', ocr=True)
        self.ocr_name = self.receipt['retained_ocr_middle_name']
        (self.root / 'source.pdf').write_bytes(self.source)
        (self.root / 'palimpsest_renderer.py').write_bytes((ROOT / 'src/palimpsest/pdf_raster.py').read_bytes())
        write_json(self.root / 'source_middle.json', self.native)
        write_json(self.root / self.ocr_name, self.ocr)
        write_json(self.root / 'source_model.json', [{}])
        write_json(self.root / self.receipt['retained_ocr_model_name'], [{}])
        for directory in (self.root / 'images', (self.root / self.ocr_name).parent / 'images'):
            directory.mkdir()
            (directory / 'panel.jpg').write_bytes(b'Synthetic unmodified parser crop bytes')
        raster = self.root / 'raster'
        raster.mkdir()
        (raster / 'page-0001.png').write_bytes(png())
        (raster / 'image-only.pdf').write_bytes(b'Synthetic derived PDF bytes; previously verified upstream in this fixture.')
        self.geometry = {'size':[72,72], 'media_box':[0,0,72,72], 'crop_box':[0,0,72,72],
                         'effective_bbox':[0,0,72,72], 'rotation':0,
                         'render_box_policy':'PDFium effective bbox; raw CropBox is retained, not rewritten'}
        page = _page_metadata(deepcopy(self.geometry), 0, [200,200])
        page['png'] = {**page.pop('png_geometry'), **self.asset(raster / 'page-0001.png')}
        self.manifest = {'schema_version':'pdf-raster-v1','state':'verified_image_only_input',
            'source':{'data_id':self.data_id,'sha256':self.data_id,'bytes':len(self.source),'page_count':1},
            'renderer':{**RENDER_PROFILE,'script_sha256':self.profile['parser']['renderer_sha256']},
            'pages':[page], 'derived_pdf':{**self.asset(raster / 'image-only.pdf'),'is_original_data':False}}
        write_json(raster / 'manifest.json', self.manifest)
        for field in ('data_id','document','native_input_sha256','source_sha256_before','source_sha256_after'):
            self.receipt[field] = self.data_id
        original = {'page_index':0,**{k:self.geometry[k] for k in ('size','media_box','crop_box','rotation')}}
        self.receipt.update(original_pages=[original], parser_origin_pages=[deepcopy(original)],
                            parser_page_sizes=[[72,72]], ocr_parser_origin_pages=[deepcopy(original)],
                            ocr_parser_page_sizes=[[72,72]], ocr_input_sha256=self.manifest['derived_pdf']['sha256'])
        self.refresh_records()

    def asset(self, path):
        raw = path.read_bytes()
        return {'path':path.name, 'sha256':sha256(raw).hexdigest(), 'bytes':len(raw)}

    def refresh_records(self):
        self.receipt['retained_artifacts'] = [{**self.asset(p), 'path':p.relative_to(self.root).as_posix()}
            for p in sorted(self.root.rglob('*')) if p.is_file()]
        self.receipt['raster_manifest_sha256'] = sha256((self.root / 'raster/manifest.json').read_bytes()).hexdigest()

    def normalize(self, native=None):
        return normalize_dual(self.native if native is None else native, data_id=self.data_id,
            artifact_root=self.root, expected_pages=1, profile=self.profile['parser'], receipt=self.receipt)

    def test_native_ordinary_and_ocr_special_selection_preserves_both_raw_sources(self):
        before = {p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        native_before, ocr_before = deepcopy(self.native), deepcopy(self.ocr)
        result = self.normalize()
        block = result['blocks'][0]
        self.assertEqual('OVA-RMA received 1 μM FBG.', block['text'])
        self.assertEqual('OVA-RMA received 1 mM FBG.', block['native_text'])
        self.assertEqual(r'OVARMA received 1 \mu M FBG.', result['ocr_bundle']['blocks'][0]['text'])
        self.assertEqual(self.data_id, result['data_id'])
        self.assertEqual(self.data_id, result['ocr_bundle']['data_id'])
        self.assertEqual([72,72], result['pages'][0]['page_size'])
        self.assertEqual(digest(self.native['pdf_info'][0]['preproc_blocks'][0]), block['raw_block_sha256'])
        ocr_block = result['ocr_bundle']['blocks'][0]
        self.assertEqual(digest(self.ocr['pdf_info'][0]['preproc_blocks'][0]), ocr_block['raw_block_sha256'])
        change = block['transcription_selection']['changes'][0]
        self.assertEqual('ocr_greek', change['reason'])
        self.assertTrue(change['native_refs'])
        self.assertTrue(change['ocr_refs'])
        self.assertEqual([5,5,65,20], change['ocr_refs'][0]['raw_bbox'])
        image = result['ocr_bundle']['blocks'][1]
        prefix = Path(self.ocr_name).parent.as_posix()
        self.assertEqual(prefix + '/images/panel.jpg', image['image_paths'][0]['path'])
        self.assertEqual(image['image_paths'][0], image['segments'][0]['image_path'])
        self.assertEqual('complete', verify_source_units(result, build_source_units(result))['status'])
        self.assertEqual(result, self.normalize())
        self.assertEqual(native_before, self.native)
        self.assertEqual(ocr_before, self.ocr)
        self.assertEqual(before, {p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_changed_or_missing_secondary_raw_and_crops_fail_before_selection(self):
        for relative in (self.ocr_name, (Path(self.ocr_name).parent / 'images/panel.jpg').as_posix()):
            path = self.root / relative
            before = path.read_bytes()
            path.write_bytes(before + b'changed')
            with self.subTest(relative=relative, change='bytes'), self.assertRaises(PalimpsestError):
                self.normalize()
            path.unlink()
            with self.subTest(relative=relative, change='missing'), self.assertRaises((PalimpsestError, OSError)):
                self.normalize()
            path.write_bytes(before)

    def test_changed_native_input_or_supplied_raw_or_duplicate_manifest_record_fails(self):
        wrong = deepcopy(self.native)
        wrong['pdf_info'][0]['preproc_blocks'][0]['lines'][0]['spans'][0]['content'] = 'unretained string'
        with self.assertRaises(PalimpsestError):
            self.normalize(wrong)
        self.receipt['retained_artifacts'].append(deepcopy(self.receipt['retained_artifacts'][0]))
        with self.assertRaises(PalimpsestError):
            self.normalize()
        self.receipt['retained_artifacts'].pop()
        (self.root / 'source.pdf').write_bytes(self.source + b'changed')
        self.refresh_records()
        with self.assertRaises(ValueError):
            self.normalize()

    def test_rehashed_raster_identity_or_affine_mismatch_still_fails(self):
        original = deepcopy(self.manifest)
        for field in ('identity','affine'):
            changed = deepcopy(original)
            if field == 'identity':
                changed['source']['data_id'] = 'a' * 64
                changed['source']['sha256'] = 'a' * 64
            else:
                changed['pages'][0]['transforms']['derived_page_top_left_to_source_effective_page_top_left'][0] = 2
            write_json(self.root / 'raster/manifest.json', changed)
            self.refresh_records()
            with self.subTest(field=field), self.assertRaises((ValueError, PalimpsestError)):
                self.normalize()

    def test_secondary_geometry_and_page_count_must_match_raster(self):
        for field, wrong in (('ocr_parser_page_sizes',[[71,72]]), ('ocr_completed_pages',0),
                             ('ocr_completed_pages',True), ('ocr_enable',False)):
            before = deepcopy(self.receipt[field])
            self.receipt[field] = wrong
            with self.subTest(field=field, wrong=wrong), self.assertRaises(PalimpsestError):
                self.normalize()
            self.receipt[field] = before

    def test_rehashed_raw_route_flags_cannot_disagree_with_receipt(self):
        for filename, raw in (('source_middle.json', self.native), (self.ocr_name, self.ocr)):
            changed = deepcopy(raw)
            changed['_ocr_enable'] = not changed['_ocr_enable']
            write_json(self.root / filename, changed)
            self.refresh_records()
            with self.subTest(file=filename), self.assertRaises(PalimpsestError):
                self.normalize(changed if filename == 'source_middle.json' else None)
            write_json(self.root / filename, raw)
            self.refresh_records()

    def test_rehashed_model_output_must_still_cover_every_page(self):
        for name in ('source_model.json', self.receipt['retained_ocr_model_name']):
            for invalid in ([], {}, [{}, {}]):
                write_json(self.root / name, invalid)
                self.refresh_records()
                with self.subTest(name=name, invalid=invalid), self.assertRaises(PalimpsestError):
                    self.normalize()
            write_json(self.root / name, [{}])
            self.refresh_records()


if __name__ == '__main__':
    unittest.main()
