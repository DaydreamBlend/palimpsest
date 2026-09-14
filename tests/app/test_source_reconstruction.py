"""Exact source reconstruction and two-way lookup; no OCR/provider calls."""

from copy import deepcopy
from hashlib import sha256
import unittest

from palimpsest.d2i import build_units, assembly_payload, verify_units, SOURCE_PAGE_GROUPS_VERSION
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import build_input, digest
from palimpsest.information import fingerprints
from palimpsest.source_pages import add_page_blocks, parent_bundle
from palimpsest.source_reconstruction import build_reconstruction, lookup_source, locate_information

from test_i2k import uid
from test_source_groups import bundle as source_fixture


def rows_for(bundle, algorithm):
    blocks = {b['block_id']:b for b in bundle['blocks']}
    assets = {image['path']:{'sha256':image['sha256'],'byte_size':23,
        'artifact_path':f"derived/objects/sha256/{image['sha256'][:2]}/{image['sha256']}"}
        for block in blocks.values() for image in block['image_paths']}
    rows=[]
    for n,proposal in enumerate(build_units(bundle, algorithm)):
        refs=proposal['block_ids'];primary=proposal['image_block_id']
        rows.append({'information_id':uid(n+1),'origin_record_id':uid(n+100),'data_id':bundle['data_id'],
            **{k:proposal[k] for k in ('kind','unit_type','semantic_type','title','content')},
            **fingerprints(bundle['data_id'],proposal,blocks),
            'payload':{'schema_version':'source-information-v1','source_bundle_sha256':digest(bundle),
                'parse_manifest_sha256':'f'*64,'validation_basis':'source_structure','semantic_checked':False,
                'empty_content':proposal['content']=='','primary_block_id':primary,
                'source_blocks':[deepcopy(blocks[r]) for r in refs],
                'source_artifacts':{i['path']:assets[i['path']] for r in refs for i in blocks[r]['image_paths']},
                'images':[assets[i['path']] for i in blocks[primary]['image_paths']] if primary else [],
                **assembly_payload(bundle,proposal,algorithm)}})
    return rows


def visuals_for(source):
    return {'source':{'data_id':source['data_id'],'pdf_sha256':source['data_id'],'pdf_size_bytes':99,
        'bundle_sha256':digest(source),'renderer':{'name':'pypdfium2','version':'5.10.1','scale':2,'annotations':True}},
        'pages':[{'page_index':p['page_index'],'page_size':p['page_size'],
            'source_box':[0,0,*p['page_size']],'cropbox':[0,0,*p['page_size']],
            'mediabox':[0,0,*p['page_size']],'rotation':0,
            'page_image':{'path':f"pages/page-{p['page_index']:04d}.png",'pixel_size':[1224,1584],
                'sha256':sha256(str(p['page_index']).encode()).hexdigest(),'size_bytes':23}}
            for p in source['pages']]}


class SourceReconstructionTests(unittest.TestCase):
    def setUp(self):
        self.source=source_fixture();self.visuals=visuals_for(self.source)
        self.bundle=add_page_blocks(self.source,self.visuals,evidence_manifest_sha256='e'*64)
        self.rows=rows_for(self.bundle,SOURCE_PAGE_GROUPS_VERSION)
        self.packet=build_input(self.bundle,self.rows,execution_id=uid(1000),profile_id=uid(1001),
                                assembly_algorithm=SOURCE_PAGE_GROUPS_VERSION)

    def test_additive_full_page_information_and_exact_parent_preservation(self):
        self.assertEqual(parent_bundle(self.bundle),self.source)
        self.assertEqual(self.bundle['blocks'][:len(self.source['blocks'])],self.source['blocks'])
        original=build_units(self.source,'source-groups-v1')
        current=build_units(self.bundle,SOURCE_PAGE_GROUPS_VERSION)
        self.assertEqual(current[:len(original)],original)
        self.assertEqual(len(current),len(original)+2)
        self.assertEqual([n['kind'] for n in current[-2:]],['image','image'])
        checked=verify_units(self.bundle,current,SOURCE_PAGE_GROUPS_VERSION)
        self.assertEqual(checked['page_facsimile_count'],2)
        page=next(u for u in self.packet['model_input']['information'] if u['title']=='Original page 1')
        self.assertEqual(page['source_refs'][0]['facsimile_provenance']['data_id'],self.source['data_id'])
        self.assertIsNone(page['source_refs'][0]['source_text_range'])
        self.assertEqual(page['media'][0]['sha256'],self.visuals['pages'][0]['page_image']['sha256'])

    def test_reconstruction_uses_selected_complete_execution_not_history_union(self):
        original={'data_id':self.source['data_id'],'byte_size':99,'media_type':'application/pdf',
            'artifact_path':f"objects/sha256/{self.source['data_id'][:2]}/{self.source['data_id']}"}
        report=build_reconstruction(self.bundle,self.rows,self.packet,original)
        self.assertEqual(report['retained_blocks'],self.bundle['blocks'])
        self.assertEqual(report['source_coverage'],'all_rendered_visible_pages_in_information')
        self.assertFalse(report['ocr_text_complete'])
        with self.assertRaises(PalimpsestError):
            build_reconstruction(self.bundle,self.rows+self.rows,self.packet,original)
        bad=deepcopy(self.rows);bad[0]['content']='changed'
        with self.assertRaises(PalimpsestError):build_reconstruction(self.bundle,bad,self.packet,original)
        partial=build_input(self.bundle,self.rows,execution_id=uid(1000),profile_id=uid(1001),
            assembly_algorithm=SOURCE_PAGE_GROUPS_VERSION,selected_information_ids=[self.rows[0]['information_id']])
        with self.assertRaises(PalimpsestError):lookup_source(partial,page_number=1)

    def test_unparsed_area_has_actual_page_i_and_reverse_information_location(self):
        old_rows=rows_for(self.source,'source-groups-v1')
        old=build_input(self.source,old_rows,execution_id=uid(1000),profile_id=uid(1001),assembly_algorithm='source-groups-v1')
        query={'page_number':1,'bbox':[600,780,611,791]}
        self.assertEqual(lookup_source(old,**query)['status'],'unmapped_region')
        found=lookup_source(self.packet,**query)
        self.assertEqual(found['status'],'visible_page_region_available')
        self.assertFalse(found['parsed_information_ids'])
        page=locate_information(self.packet,found['page_image_information_ids'][0])
        self.assertEqual(page['source_refs'][0]['bbox'],[0,0,612,792])
        self.assertEqual(page['source_refs'][0]['page_index'],0)
        unit=next(u for u in self.packet['model_input']['information'] if u['title']=='Introduction')
        start=unit['content'].index('Cafe')
        location=locate_information(self.packet,unit['information_id'],char_range=[start,start+5])
        self.assertEqual(location['source_refs'][0]['block_id'],'/intro-text')
        self.assertEqual(location['content_segments'][0]['matched_source_char_range'],[2,7])
        self.assertEqual(locate_information(self.packet,unit['information_id'],char_range=[12,13])['status'],'assembly_separator')
        with self.assertRaises(PalimpsestError):lookup_source(self.packet,page_number=1,bbox=[0,0,9999,2])

    def test_wrong_pdf_missing_page_changed_pixels_and_old_source_are_rejected(self):
        for mutation in ('pdf','page','image','source'):
            with self.subTest(mutation=mutation):
                if mutation in ('pdf','page'):
                    v=deepcopy(self.visuals)
                    if mutation=='pdf':v['source']['pdf_sha256']='c'*64
                    else:v['pages'].pop()
                    with self.assertRaises(PalimpsestError):add_page_blocks(self.source,v,evidence_manifest_sha256='e'*64)
                else:
                    b=deepcopy(self.bundle)
                    if mutation=='image':b['blocks'][-1]['image_paths'][0]['sha256']='c'*64
                    else:b['blocks'][0]['text']='lost source text'
                    with self.assertRaises(PalimpsestError):parent_bundle(b)
        for key,value in (('rotation',45),('source_box',[0,0,611,792]),('cropbox',[0,0,1,float('inf')])):
            with self.subTest(geometry=key):
                v=deepcopy(self.visuals);v['pages'][0][key]=value
                with self.assertRaises(PalimpsestError):add_page_blocks(self.source,v,evidence_manifest_sha256='e'*64)
        v=deepcopy(self.visuals);v['source']['renderer']['scale']=3
        with self.assertRaises(PalimpsestError):add_page_blocks(self.source,v,evidence_manifest_sha256='e'*64)

    def test_markdown_exact_bytes_and_two_way_unicode_locations(self):
        from palimpsest.markdown_adapter import parse_markdown, MARKDOWN_ALGORITHM
        raw='# One\r\nα μ²\r\n\r\n# Two\nTail\n'.encode('utf-8')
        source=parse_markdown(raw,data_id=sha256(raw).hexdigest())
        rows=rows_for(source,MARKDOWN_ALGORITHM)
        packet=build_input(source,rows,execution_id=uid(1000),profile_id=uid(1001),assembly_algorithm=MARKDOWN_ALGORITHM)
        original={'data_id':source['data_id'],'byte_size':len(raw),'media_type':'text/markdown',
            'artifact_path':f"objects/sha256/{source['data_id'][:2]}/{source['data_id']}"}
        self.assertEqual(build_reconstruction(source,rows,packet,original)['source_coverage'],'exact_utf8_source_bytes')
        point=raw.index('μ'.encode('utf-8'))
        found=lookup_source(packet,byte_range=[point,point+2])
        unit=packet['model_input']['information'][0]
        self.assertEqual(found['parsed_information_ids'],[unit['information_id']])
        self.assertEqual(lookup_source(packet,line_range=[2,2])['parsed_information_ids'],[unit['information_id']])
        start=unit['content'].index('μ')
        location=locate_information(packet,unit['information_id'],char_range=[start,start+1])
        self.assertEqual(location['content_segments'][0]['matched_source_byte_range'],[point,point+2])

    def test_original_evidence_quality_requires_exact_parent_and_manifest(self):
        evidence={'source_bundle':deepcopy(self.source),'manifest_sha256':'e'*64,
            'text_analysis':{'heading_candidates':[],'discrepancies':[{'discrepancy_id':'retained-conflict',
                'page_index':0,'kind':'region_text_difference','parser_refs':[{'raw_locator':'/intro-text'}]}]},
            'paragraphs':{'paragraphs':[]},'visuals':{'figures':[],'pages':[],'panels':[]}}
        def build(value):
            return build_input(self.bundle,self.rows,execution_id=uid(1000),profile_id=uid(1001),
                               assembly_algorithm=SOURCE_PAGE_GROUPS_VERSION,evidence=value)
        packet=build(evidence)
        quality=packet['model_input']['quality_evidence']
        self.assertEqual(quality['status'],'supplied_review_signals')
        self.assertIn('retained-conflict',[i.get('discrepancy_id') for i in quality['issues']])
        self.assertEqual(packet['model_input']['information'],self.packet['model_input']['information'])
        for mutation in ('manifest','parent'):
            changed=deepcopy(evidence)
            if mutation=='manifest':changed['manifest_sha256']='d'*64
            else:changed['source_bundle']['blocks'][0]['text']='different source'
            with self.subTest(mutation=mutation),self.assertRaises(PalimpsestError) as caught:
                build(changed)
            self.assertEqual(caught.exception.code,'i2k_evidence_mismatch')


if __name__=='__main__':unittest.main()
