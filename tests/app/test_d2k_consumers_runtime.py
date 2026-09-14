"""Real isolated PG D2K consumers with synthetic grants, vectors and receipts.

These composed tests do not inherit the D2K suite, migrate a database, run a
provider or render a PDF. Root alone runs them after provisioning the fixture.
"""

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

from palimpsest import d2k, multi_source_i2k
from palimpsest.canonical_store import connection
from palimpsest.compiler_runtime import CompilerRuntime
from palimpsest.desktop_read import DesktopReadService
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.knowledge_requests import generation_request, validation_request
from palimpsest.knowledge_runtime import MODEL
from palimpsest.paper_wiki_runtime import PaperWikiRuntime
from palimpsest.wiki_archive import PROFILE
from palimpsest.wiki_database import WikiDatabase
from palimpsest.wiki_projection_store import ProjectionStore
from palimpsest.wiki_query import ANSWER_WITH_DATA_SCHEMA
from palimpsest.wiki_query_runtime import WikiQueryRuntime
from palimpsest.wiki_retrieval import WikiRetrieval

import test_d2k_runtime as source_fixtures
import test_d2k as source_contract
import test_k2k_runtime as inference_fixtures
import test_multi_source_runtime as i2k_fixtures
import test_paper_wiki_runtime as wiki_fixtures
from test_paper_wiki import decisions as wiki_decisions
from test_wiki_query_inference import decision as query_decision
from test_wiki_retrieval_db import encoded


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires explicitly provisioned Linux PostgreSQL D2K fixture')
class D2KConsumerRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['PALIMPSEST_TEST_DSN']
        with connection(cls.dsn) as conn:
            if conn.execute('SELECT current_database() AS name').fetchone()['name'] not in ('palimpsest', 'palimpsest_d2k_checks'):
                raise RuntimeError('D2K consumer tests require the isolated fixture database')
            for table in ('canonical_store.knowledge_data_groundings', 'compiler_runtime.d2k_source_views',
                          'wiki_projection.wikis', 'wiki_retrieval.indexes'):
                if conn.execute('SELECT to_regclass(%s) AS name', (table,)).fetchone()['name'] is None:
                    raise RuntimeError('Root must provision the reviewed D2K/Wiki fixture migrations')

    def setUp(self):
        self.helper = self.make_helper()
        self.base, self.root = self.helper.base, self.helper.root
        self.repo, self.runtime = self.helper.repo, self.helper.runtime
        self.data_id = self.helper.data_id
        self.database = WikiDatabase(self.dsn, self.root)
        self.retrieval = WikiRetrieval(self.dsn, self.root)
        self.wiki_id = self.repo.allocate_id()

    def make_helper(self):
        helper = source_fixtures.D2KRuntimeTests('runTest')
        helper.dsn = self.dsn
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        return helper

    def create_knowledge(self):
        _, preparation, grant = self.helper.grant()
        job = self.helper.prepare(grant)
        result = self.helper.commit(job)
        return preparation, grant, job, result

    def empty_wiki(self):
        store = ProjectionStore(self.base / 'empty-wiki')
        catalog = {'schema_version': PROFILE, 'version': 0, 'papers': {}, 'topics': {}, 'commits': {}}
        with store.locked():
            store.write_json('catalog.json', catalog)
            store.write_json('catalogs/' + digest(catalog) + '.json', catalog)
        result = self.database.sync(self.wiki_id, self.repo.allocate_id(), store.root)
        self.assertEqual((result['paper_count'], result['topic_count'], result['snapshot_count']), (0, 0, 0))
        return result

    def assert_no_information(self):
        counts = self.helper.counts()
        self.assertEqual((counts['information'], counts['d2i'], counts['information_groundings']), (0, 0, 0))

    def desktop(self, include=None, directory=None):
        return DesktopReadService(self.dsn, self.root, self.wiki_id, directory or self.base / 'queries',
                                  include_data_ids=include)

    def test_empty_wiki_needs_explicit_data_scope_and_preserves_i_free_complete_d2k_route(self):
        preparation, _, _, result = self.create_knowledge()
        self.empty_wiki()
        self.assert_no_information()
        with source_fixtures.no_d2i():
            legacy = self.retrieval.corpus(self.wiki_id)
            corpus = self.retrieval.corpus(self.wiki_id, include_data_ids=[self.data_id])
        self.assertEqual(legacy['knowledge'], [])
        self.assertNotIn('include_data_ids', legacy)
        self.assertNotIn('data_citations_supported', legacy)
        self.assertEqual(corpus['include_data_ids'], [self.data_id])
        self.assertTrue(corpus['data_citations_supported'])
        self.assertEqual(corpus['information'], [])
        self.assertEqual(corpus['source_packets'], [])
        node = corpus['knowledge'][0]
        self.assertEqual(len(corpus['knowledge']), 1)
        self.assertEqual(node['knode_revision_id'], result['records'][0]['result_node_revision_id'])
        self.assertEqual(node['generation_origin']['origin_operation'], 'd2k')
        self.assertIs(node['generation_origin']['is_inferred'], False)
        self.assertEqual(node['direct_groundings'], [])
        self.assertEqual(node['retrieval_support']['operation'], 'd2k')
        self.assertEqual(node['retrieval_support']['information_ids'], [])
        self.assertEqual(node['retrieval_support']['source_data_ids'], [self.data_id])
        self.assertEqual({row['grounding_id'] for row in node['direct_data_groundings']},
                         set(node['retrieval_support']['records'][0]['data_grounding_ids']))
        self.assertEqual({view['view_id']: view for view in corpus['data_views']},
                         {view['view_id']: view for view in preparation['packet']['views']})
        self.assert_no_information()

    def test_same_data_second_grant_retains_origin_and_each_accepted_record_support(self):
        _, grant, first_job, first = self.create_knowledge()
        revision = first['records'][0]['result_node_revision_id']
        original_record = first['records'][0]['record_id']
        _, _, second_grant = self.helper.grant()
        second_job = self.helper.prepare(second_grant)
        decisions = source_contract.decisions(second_job['input_snapshot']['input'])
        decisions['decisions'][0].update(verdict='reused', equivalent_revision_id=revision)
        second = self.helper.commit(second_job, decisions=decisions)
        self.assertEqual(second['records'][0]['result_node_revision_id'], revision)
        self.assertEqual(second['records'][0]['disposition'], 'reused')
        self.assertTrue(self.helper.prepare(grant, identifier=first_job['request_id'])['replayed'])
        with connection(self.dsn) as conn:
            rows = conn.execute('''SELECT grounding_id,origin_record_id FROM canonical_store.knowledge_data_groundings
                WHERE node_revision_id=%s ORDER BY grounding_id''', (revision,)).fetchall()
            count = conn.execute('SELECT count(*) AS n FROM canonical_store.knowledge_node_revisions WHERE knode_id=%s',
                                 (first['records'][0]['result_node_id'],)).fetchone()['n']
        self.assertEqual(count, 1)
        self.assertEqual({str(row['origin_record_id']) for row in rows}, {original_record, second['records'][0]['record_id']})
        self.empty_wiki()
        corpus = self.retrieval.corpus(self.wiki_id, include_data_ids=[self.data_id])
        node = corpus['knowledge'][0]
        self.assertEqual(node['generation_origin']['origin_record_id'], original_record)
        chosen = node['retrieval_support']['record_id']
        self.assertEqual({row['origin_record_id'] for row in node['direct_data_groundings']}, {chosen})
        self.assertEqual({row['grounding_id'] for row in node['direct_data_groundings']},
                         {str(row['grounding_id']) for row in rows if str(row['origin_record_id']) == chosen})
        self.assert_no_information()

    def test_desktop_reads_exact_original_and_denies_unselected_data_before_reading_bytes(self):
        _, _, _, result = self.create_knowledge()
        outside = self.make_helper()
        _, _, grant = outside.grant()
        other = outside.commit(outside.prepare(grant))
        self.empty_wiki()
        service = self.desktop([self.data_id])
        node = service.knowledge_node(result['records'][0]['result_node_revision_id'])
        reference = node['data_evidence'][0]
        with source_fixtures.no_d2i():
            shown = service.data_grounding(reference['grounding_id'])
        self.assertEqual(shown['grounding']['data_id'], self.data_id)
        self.assertIsNone(shown['source_info'])
        self.assertEqual(shown['media_kind'], 'text')
        locator = shown['grounding']['locator']
        self.assertEqual(shown['grounding']['quote'], self.helper.raw[locator['byte_start']:locator['byte_end']].decode('utf-8'))
        with connection(self.dsn) as conn:
            other_id = str(conn.execute('SELECT grounding_id FROM canonical_store.knowledge_data_groundings WHERE node_revision_id=%s LIMIT 1',
                                       (other['records'][0]['result_node_revision_id'],)).fetchone()['grounding_id'])
        with patch.object(service.database.source.store, 'read', side_effect=AssertionError('No outside Data read')), self.assertRaises(PalimpsestError) as denied:
            service.data_grounding(other_id)
        self.assertEqual(denied.exception.code, 'desktop_data_grounding_not_in_scope')
        with self.assertRaises(PalimpsestError):
            self.desktop().data_grounding(reference['grounding_id'])
        artifact = self.root / self.repo.get_data(self.data_id)['artifact_path']
        mode = artifact.stat().st_mode
        try:
            artifact.chmod(0o600)
            artifact.write_bytes(bytes([self.helper.raw[0] ^ 1]) + self.helper.raw[1:])
            with self.assertRaises(PalimpsestError) as changed:
                service.data_grounding(reference['grounding_id'])
            self.assertEqual(changed.exception.code, 'integrity_conflict')
        finally:
            artifact.write_bytes(self.helper.raw)
            artifact.chmod(mode)
        self.assertEqual(service.data_grounding(reference['grounding_id']), shown)
        self.assert_no_information()

    def make_i_premise_and_wiki(self):
        path = self.base / 'information-source.md'
        path.write_text(f'# Separate I source {uuid4()}\n\nThis fixture explicitly reports a source fact.\n', encoding='utf-8')
        owner = self.helper.data.import_file(path, media_type='text/markdown')['data_id']
        source = CompilerRuntime(self.dsn, self.root)
        compiled = source.compile_markdown(owner)
        packet = source.prepare_input(compiled['execution_id'])
        bundle = multi_source_i2k.combine_packets([packet])
        unit = next(unit for unit in bundle['model_input']['information'] if unit['content'].strip())
        candidate = {'candidate_key': 'source_i', 'kind': 'proposition', 'statement': 'Synthetic I-grounded fixture fact.',
            'semantic_payload': {'subject': 'Synthetic I source ' + owner, 'relation': 'reports a fixture fact', 'object': 'I source',
                'polarity': 'positive', 'quantifier': 'source-reported', 'scope': 'storage fixture', 'conditions': [], 'time_range': ''},
            'identity_scope': 'source', 'source_data_id': owner, 'selection_reason': 'Synthetic useful explicit fact.',
            'claim_basis': 'explicit_source_content', 'is_inferred': False, 'uncertainties': [],
            'evidence': [{'information_id': unit['information_id'], 'quote': unit['content'], 'media_sha256': None, 'source_role': 'other'}]}
        response = {'nodes': [candidate], 'complete': True, 'source_requests': [], 'coverage_notes': ['Synthetic fixture.'],
            'reviews': [{'information_id': row['information_id'], 'disposition': 'selected' if row['information_id'] == unit['information_id'] else 'context_only',
                        'candidate_keys': ['source_i'] if row['information_id'] == unit['information_id'] else [], 'reason': 'Synthetic full I review.'}
                       for row in bundle['model_input']['information']]}
        job = self.runtime.prepare('i2k', owner, self.repo.allocate_id(), bundle, selection=True, source_review=False)
        def receipt(output, phase):
            current = self.runtime.show(job['execution_id'])
            if phase == 'generator':
                prompt, schema = generation_request(current['input_snapshot'], [])
                bound = current['input_digest']
            else:
                context = self.runtime.validation_context(job['execution_id'])
                prompt, schema = validation_request(context, [])
                bound = context['validation_context_sha']
            return {'profile': dict(MODEL), 'actual_delivery': True, 'original_pdf_delivered': False,
                'provider_ref': 'synthetic-consumer-' + str(uuid4()), 'input_sha256': bound, 'output_sha256': digest(output),
                'prompt_sha256': sha256(prompt.encode()).hexdigest(), 'schema_sha256': digest(schema),
                'delivered_information_ids': bundle['target_information_ids'], 'image_attachments': [], 'usage': {}, 'test_only': True}
        self.runtime.stage(job['execution_id'], response, receipt(response, 'generator'))
        decisions = i2k_fixtures.MultiSourceRuntimeTests.decisions(response)
        accepted = self.runtime.decide(job['execution_id'], decisions, receipt(decisions, 'validator'))
        wiki = PaperWikiRuntime(self.dsn, self.root, self.base / 'mixed-wiki')
        request = self.repo.allocate_id()
        wiki.prepare(compiled['execution_id'], request, {'title': 'Synthetic I source Wiki', 'filename': path.name})
        proposed = wiki.stage(request, wiki_fixtures.exchange(wiki, request, 'generator', wiki_fixtures.synthetic_proposal(packet)))
        wiki.decide(request, wiki_fixtures.exchange(wiki, request, 'validator', wiki_decisions(proposed['proposal'])))
        return owner, accepted['records'][0]['result_node_revision_id'], wiki

    def test_mixed_k2k_corpus_requires_the_complete_selected_i_and_d_routes(self):
        _, _, _, direct = self.create_knowledge()
        data_revision = direct['records'][0]['result_node_revision_id']
        i_owner, i_revision, wiki = self.make_i_premise_and_wiki()
        packet = self.runtime.inference_input(self.data_id, [data_revision, i_revision])
        job = self.runtime.prepare('k2k', self.data_id, self.repo.allocate_id(), packet)
        response = inference_fixtures.K2KRuntimeTests.response(self.helper, job, name='consumer_mixed_route')
        self.runtime.stage(job['execution_id'], response, self.helper.receipt(job, response, 'generator'))
        decisions = inference_fixtures.K2KRuntimeTests.decisions(response)
        result = self.runtime.decide(job['execution_id'], decisions, self.helper.receipt(job, decisions, 'validator'))
        revision = result['records'][0]['result_node_revision_id']
        self.database.sync(self.wiki_id, self.repo.allocate_id(), wiki.store.root)
        with source_fixtures.no_d2i():
            partial = self.retrieval.corpus(self.wiki_id)
            complete = self.retrieval.corpus(self.wiki_id, include_data_ids=[self.data_id])
        self.assertNotIn(revision, {node['knode_revision_id'] for node in partial['knowledge']})
        inferred = next(node for node in complete['knowledge'] if node['knode_revision_id'] == revision)
        self.assertEqual(inferred['direct_groundings'], [])
        self.assertEqual(inferred['direct_data_groundings'], [])
        self.assertEqual({row['data_id'] for row in inferred['transitive_source_refs']}, {i_owner})
        self.assertEqual({row['data_id'] for row in inferred['transitive_data_refs']}, {self.data_id})
        self.assertEqual({row['operation'] for row in inferred['retrieval_support']['records']}, {'i2k', 'd2k', 'k2k'})
        self.assertTrue(inferred['generation_origin']['is_inferred'])
        self.assert_no_information()

    def test_real_index_query_delivery_and_saved_desktop_answer_need_selected_d_without_i(self):
        self.create_knowledge()
        self.empty_wiki()
        query = WikiQueryRuntime(self.dsn, self.root, self.base / 'query')
        index_id, query_id = self.repo.allocate_id(), self.repo.allocate_id()
        with source_fixtures.no_d2i():
            query.prepare_index(self.wiki_id, index_id, include_data_ids=[self.data_id])
            corpus = query.store.read_json(f'indexes/{index_id}/corpus.json')
            query.install_index(index_id, encoded(query.retrieval.embedding_request(corpus)['documents']))
            question = '등록 원문에서 제공된 합성 시험 문구는 무엇인가?'
            query.prepare(index_id, query_id, question)
            searched = query.search(query_id, encoded([{'document_id': 'query', 'text': question}]))
            rerank = json.loads(Path(searched['rerank_request_file']).read_text())
            query.context(query_id, {'schema_version': 'wiki-rerank-result-v1', 'input_sha256': digest(rerank),
                'profile': query.retrieval.index(index_id)['profile'],
                'scores': [{'chunk_id': row['chunk_id'], 'score': 1.0} for row in rerank['passages']]})
        job = query.show(query_id)
        context = query._context(job)
        self.assertEqual(context['information'], [])
        grounding = context['knowledge'][0]['direct_data_groundings'][0]
        response = {'status': 'answered', 'claims': [{'claim_key': 'source', 'text': grounding['quote'],
            'evidence': [], 'source_evidence': [], 'knowledge_evidence': [], 'data_evidence': [{'grounding_id': grounding['grounding_id']}]}],
            'search_query': None, 'source_requests': [], 'unresolved': []}
        def exchange(output, phase):
            exported = query.model_request(query_id, phase)
            request = json.loads(Path(exported['request_file']).read_text())
            return {'response': output, 'receipt': {'profile': dict(MODEL), 'actual_delivery': True, 'original_pdf_delivered': False,
                'provider_ref': 'synthetic-query-' + str(uuid4()), 'input_sha256': request['input_sha256'], 'output_sha256': digest(output),
                'prompt_sha256': sha256(request['prompt'].encode()).hexdigest(), 'schema_sha256': digest(request['schema']),
                'image_attachments': [], 'delivered_information_ids': [], 'delivered_data_view_ids': request['delivered_data_view_ids'],
                'delivered_knowledge_revision_ids': request['delivered_knowledge_revision_ids'], 'usage': {}, 'test_only': True}}
        with source_fixtures.no_d2i():
            staged = query.stage(query_id, exchange(response, 'generator'))
            answer = query.store.read_json(staged['last_proposal_path'])
            query.decide(query_id, exchange(query_decision(answer), 'validator'))
            saved = self.desktop([self.data_id], query.store.root).query(query_id)
        self.assertEqual(answer['schema_version'], ANSWER_WITH_DATA_SCHEMA)
        self.assertEqual(answer['claims'][0]['epistemic_basis'], 'direct_source')
        self.assertEqual(answer['claims'][0]['data_evidence'][0], grounding)
        self.assertTrue(saved['accepted'])
        self.assertIn(self.data_id, saved['answer'])
        with self.assertRaises(PalimpsestError) as denied:
            self.desktop(directory=query.store.root).query(query_id)
        self.assertEqual(denied.exception.code, 'desktop_query_data_not_in_scope')
        self.assert_no_information()


if __name__ == '__main__':
    unittest.main()
