"""Actual raster/ArtifactStore/PostgreSQL integration; synthetic model receipts."""
from copy import deepcopy
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import unittest
from uuid import uuid4

from palimpsest import d2k, d2k_pdf
from palimpsest.errors import PalimpsestError
import test_d2k as pure
import test_d2k_runtime as fixtures
from test_d2k_runtime import no_d2i
from test_pdf_raster import pdf_bytes

try:
    PINNED = importlib.metadata.version('pypdfium2')=='5.10.1' and importlib.metadata.version('Pillow')=='12.3.0'
except importlib.metadata.PackageNotFoundError:
    PINNED = False


@unittest.skipUnless(PINNED and sys.platform=='linux' and os.environ.get('PALIMPSEST_TEST_DSN'),'Requires pinned native PDF and isolated PostgreSQL fixture')
class D2KPDFRuntimeTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.D2KRuntimeTests.setUpClass.__func__)
    setUp = fixtures.D2KRuntimeTests.setUp
    row = fixtures.D2KRuntimeTests.row
    counts = fixtures.D2KRuntimeTests.counts
    reject = fixtures.D2KRuntimeTests.reject

    def receipt(self, job, response, phase):
        current = self.runtime.show(job['execution_id'])
        packet = current['input_snapshot']['input']
        request = self.source.prepare_call(job['execution_id'],phase,self.base/phase)
        sent = json.loads(Path(request['request_file']).read_text())
        from palimpsest.i2k import digest
        from hashlib import sha256
        return {'profile':{**job['profile']['model'],'synthetic_receipt':True},
            'actual_delivery':True,'provider_ref':'synthetic-no-model-'+str(uuid4()),
            'input_sha256':sent['input_sha256'],'output_sha256':digest(response),
            'prompt_sha256':sha256(sent['prompt'].encode()).hexdigest(),'schema_sha256':digest(sent['schema']),
            'delivered_data_view_ids':sent['delivered_data_view_ids'],
            'delivered_knowledge_revision_ids':sent['delivered_knowledge_revision_ids'],
            'image_attachments':[{'sha256':v['image_sha256'],'byte_size':v['image_byte_size']} for v in packet['views']],
            'original_pdf_delivered':False,'test_only':True}

    def test_selected_native_PDF_views_commit_exact_direct_grounding_without_I_or_parser(self):
        self.raw = pdf_bytes()+b'\n% unique fixture '+str(uuid4()).encode()+b'\n'
        self.path = self.base/'source.pdf';self.path.write_bytes(self.raw)
        self.data_id = self.data.import_file(self.path,media_type='application/pdf')['data_id']
        with no_d2i():
            rendered = d2k_pdf.render_source(self.path,self.base/'pages',self.data_id,[1])
            draft = self.source.draft(self.data_id,self.repo.allocate_id(),reason=self.reason,pdf_directory=self.base/'pages')
            grant = self.source.authorize(draft['preparation_id'],self.repo.allocate_id(),draft['manifest_sha256'],actor_ref='synthetic-test-user')
            job = self.source.prepare(grant['authorization_id'],self.repo.allocate_id())
        packet = job['input_snapshot']['input']
        self.assertEqual(len(packet['views']),1)
        self.assertEqual(packet['views'][0]['page_count'],2)
        response = pure.response(packet)
        receipt = self.receipt(job,response,'generator')
        omitted = deepcopy(receipt);omitted['image_attachments']=[]
        self.reject(lambda:self.runtime.stage(job['execution_id'],response,omitted),'knowledge_image_delivery_mismatch')
        with no_d2i(no_source_reads=True):
            self.runtime.stage(job['execution_id'],response,receipt)
        decisions = pure.decisions(packet)
        validator = self.receipt(job,decisions,'validator')
        with no_d2i(no_source_reads=True):
            result = self.runtime.decide(job['execution_id'],decisions,validator)
        self.assertEqual(result['state'],'completed')
        self.assertEqual((self.counts()['information'],self.counts()['d2i'],self.counts()['data_groundings']),(0,0,1))
        evidence = result['data_groundings'][0]['evidence']
        self.assertEqual(evidence['locator']['page_index'],0)
        self.assertEqual(evidence['locator']['page_count'],2)
        self.assertEqual(evidence['representation'],'original_pdf_page_image')
        self.assertEqual((evidence['quote'],evidence['char_start'],evidence['char_end']),('',0,0))
        self.assertEqual(evidence['media_sha256'],rendered['pages'][0]['png']['sha256'])
        self.assertTrue(all(call['receipt']['original_pdf_delivered'] is False for call in result['model_calls']))
        self.assertEqual(self.store.read(self.data_id,len(self.raw)),self.raw)
        self.assertFalse(result['d2i_status_changed'])
