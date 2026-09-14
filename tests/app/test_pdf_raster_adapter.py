"""Original Data/page grounding survives rasterization; no GPU or PDF library."""
from copy import deepcopy
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.pdf_raster_adapter import ADAPTER_VERSION,map_to_original
from palimpsest.source_units import build_source_units,verify_source_units


class RasterAdapterTests(unittest.TestCase):
    def fixture(self):
        block={'block_id':'/pdf_info/0/preproc_blocks/0','type':'text','page_index':0,
            'page_size':[600,800],'bbox':[30,40,600,800],'upstream_bbox':[30,40,600,800],
            'text':'1 μM FBG','image_paths':[],'raw_locator':'/pdf_info/0/preproc_blocks/0',
            'segments':[{'type':'text','content':'1 μM FBG','bbox':[30,40,60,80],
                'raw_locator':'/pdf_info/0/preproc_blocks/0/lines/0/spans/0'}],
            'children':[{'type':'text','bbox':[30,40,60,80]}],
            'line_regions':[{'type':'line','bbox':None}],
            'grounding_regions':[{'type':'text','bbox':[30,40,600,800],'raw_locator':'/pdf_info/0/preproc_blocks/0'}],
            'supported':True,'unsupported':[],'empty':False,'raw_block_sha256':'b'*64,'anchor_sha256':'c'*64}
        bundle={'schema_version':1,'data_id':'a'*64,'profile':{'adapter_version':ADAPTER_VERSION},
            'coordinate_system':'pdf_points_top_left','block_collection':'preproc_blocks',
            'pages':[{'page_index':0,'page_size':[600,800]}],'blocks':[block],'unsupported_block_ids':[]}
        manifest={'source':{'data_id':'a'*64,'page_count':1},'pages':[{
            'source_page_index':0,'derived_page_index':0,
            'source_geometry':{'size':[599.76,799.9],'effective_bbox':[10,20,609.76,819.9],
                'crop_box':[9,19,611,821],'rotation':0},
            'derived_geometry':{'size':[600,800],'rotation':0}}]}
        return bundle,manifest

    def test_every_region_maps_to_original_while_source_text_and_raw_refs_stay(self):
        bundle,manifest=self.fixture(); before=deepcopy(bundle)
        mapped=map_to_original(bundle,manifest,manifest_sha256='d'*64); block=mapped['blocks'][0]
        self.assertEqual(bundle,before)
        self.assertEqual([599.76,799.9],mapped['pages'][0]['page_size'])
        self.assertEqual([599.76,799.9],block['bbox'][2:])
        self.assertEqual([30,40,600,800],block['upstream_bbox'])
        for field in ('segments','children','grounding_regions'):
            self.assertEqual(before['blocks'][0][field][0]['bbox'],block[field][0]['raw_bbox'])
            self.assertNotEqual(block[field][0]['raw_bbox'],block[field][0]['bbox'])
        self.assertIsNone(block['line_regions'][0]['bbox'])
        self.assertEqual('1 μM FBG',block['text'])
        self.assertEqual(before['blocks'][0]['raw_block_sha256'],block['raw_block_sha256'])
        self.assertNotEqual(before['blocks'][0]['anchor_sha256'],block['anchor_sha256'])
        units=build_source_units(mapped)
        self.assertEqual('complete',verify_source_units(mapped,units)['status'])
        self.assertEqual(mapped,map_to_original(bundle,manifest,manifest_sha256='d'*64))

    def test_partial_pages_wrong_identity_and_outside_derived_regions_are_rejected(self):
        for change in ('identity','source_page','derived_page','count','outside','rotated'):
            bundle,manifest=self.fixture()
            if change=='identity':manifest['source']['data_id']='e'*64
            if change=='source_page':manifest['pages'][0]['source_page_index']=2
            if change=='derived_page':manifest['pages'][0]['derived_page_index']=2
            if change=='count':manifest['source']['page_count']=3
            if change=='outside':bundle['blocks'][0]['segments'][0]['bbox']=[0,0,601,20]
            if change=='rotated':manifest['pages'][0]['source_geometry']['rotation']=90
            with self.subTest(change=change),self.assertRaises(PalimpsestError):
                map_to_original(bundle,manifest,manifest_sha256='d'*64)

    def test_actual_fractional_derived_geometry_is_used_instead_of_rounded_parser_size(self):
        bundle,manifest=self.fixture()
        manifest['pages'][0]['derived_geometry']['size']=[600.28,800.16]
        mapped=map_to_original(bundle,manifest,manifest_sha256='d'*64)
        block=mapped['blocks'][0]
        self.assertAlmostEqual(600*599.76/600.28,block['bbox'][2],places=12)
        self.assertAlmostEqual(800*799.9/800.16,block['bbox'][3],places=12)
        self.assertLess(block['bbox'][2],599.76)
        self.assertEqual([30,40,600,800],block['raw_bbox'])
        self.assertEqual([600,800],block['raw_page_size'])
        self.assertEqual([600.28,800.16],block['coordinate_transform']['source_size'])
        self.assertEqual(bundle['blocks'][0]['segments'][0]['raw_locator'],
                         block['segments'][0]['raw_locator'])
        self.assertEqual(bundle['blocks'][0]['raw_block_sha256'],block['raw_block_sha256'])

    def test_rounding_tolerance_does_not_clip_a_region_outside_actual_derived_page(self):
        bundle,manifest=self.fixture()
        manifest['pages'][0]['derived_geometry']['size']=[599.75,799.9]
        # The raw box passes the rounded600x800parserbounds, but not actualPDFbounds.
        with self.assertRaises(PalimpsestError):
            map_to_original(bundle,manifest,manifest_sha256='d'*64)

    def test_mapped_bundle_wrong_block_page_or_unbound_manifest_cannot_be_remapped(self):
        bundle,manifest=self.fixture()
        mapped=map_to_original(bundle,manifest,manifest_sha256='d'*64)
        with self.assertRaises(PalimpsestError):
            map_to_original(mapped,manifest,manifest_sha256='d'*64)
        for value in (-1,1,True):
            invalid=deepcopy(bundle)
            invalid['blocks'][0]['page_index']=value
            with self.subTest(page=value),self.assertRaises(PalimpsestError):
                map_to_original(invalid,manifest,manifest_sha256='d'*64)
        with self.assertRaises(PalimpsestError):
            map_to_original(bundle,manifest,manifest_sha256='unbound')


if __name__=='__main__':unittest.main()
