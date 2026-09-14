"""Code review continuation and desktop isolation in the explicit PG fixture.

All I2K/K2K and Wiki verdicts use labelled synthetic test receipts. D2I uses the
real deterministic code/Markdown paths; provider subprocesses are forbidden.
"""

from base64 import b64decode
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest
from unittest.mock import patch
from uuid import uuid4

from palimpsest import code_snapshot
from palimpsest.artifact_store import ArtifactStore
from palimpsest.canonical_store import PostgresRepository, connection
from palimpsest.compiler_runtime import CompilerRuntime
from palimpsest.data_versions import DataVersions
from palimpsest.desktop_read import DesktopReadService
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.knowledge_review import KnowledgeReview
from palimpsest.knowledge_runtime import KnowledgeRuntime
from palimpsest.knowledge_requests import generation_request, validation_request
from palimpsest.paper_wiki_runtime import PaperWikiRuntime
from palimpsest.service import DataService
from palimpsest.wiki_archive import build_archive
from palimpsest.wiki_database import WikiDatabase
import test_k2k_runtime as k2k_fixtures
from test_paper_wiki import decisions as wiki_decisions
from test_paper_wiki_runtime import exchange, synthetic_proposal
import test_source_review_runtime as review_fixtures


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires the explicit Linux PostgreSQL fixture database palimpsest')
class CodeReviewDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['PALIMPSEST_TEST_DSN']
        with connection(cls.dsn) as conn:
            if conn.execute('SELECT current_database() AS name').fetchone()['name'] != 'palimpsest':
                raise RuntimeError('Code review/desktop tests require isolated database palimpsest')
            for table in ('canonical_store.data_versions', 'canonical_store.knowledge_derivations', 'wiki_projection.wikis'):
                if conn.execute('SELECT to_regclass(%s) AS name', (table,)).fetchone()['name'] is None:
                    raise RuntimeError('Provision the reviewed Wiki/K2K/version fixture migrations first')

    def setUp(self):
        for target in ('subprocess.Popen', 'subprocess.run', 'urllib.request.urlopen'):
            blocked = patch(target, side_effect=AssertionError('No provider, subprocess or network call in this fixture'))
            blocked.start()
            self.addCleanup(blocked.stop)
        temporary = TemporaryDirectory(prefix='code-review-desktop-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / 'artifacts'
        self.repo = PostgresRepository(self.dsn)
        self.store = ArtifactStore(self.root)
        self.data = DataService(self.repo, self.store)
        self.source = CompilerRuntime(self.dsn, self.root)
        self.runtime = KnowledgeRuntime(self.dsn)
        self.review = KnowledgeReview(self.runtime)
        self.directory, self.data_id, self.raw = self.new_source('owned')
        self.markdown = self.source.compile_markdown(self.data_id)
        self.native = self.source.compile_code(self.data_id)
        for result in (self.markdown, self.native):
            self.assertEqual((result['llm_calls'], result['ocr_calls']), (0, 0))
        self.execution = self.native['execution_id']
        self.packet = self.source.prepare_input(self.execution)
        self.versions = DataVersions(self.dsn, self.store)
        self.series = self.versions.create('Synthetic code desktop history')['series_id']
        self.version = self.versions.append(self.series, self.data_id, self.repo.allocate_id(), None)
        self.wiki = PaperWikiRuntime(self.dsn, self.root, self.base / 'wiki')
        wiki_request = self.repo.allocate_id()
        self.wiki.prepare(self.execution, wiki_request, {'title': 'Synthetic code library', 'filename': 'dossier.md'})
        context = self.wiki.stage(wiki_request, exchange(self.wiki, wiki_request, 'generator', synthetic_proposal(self.packet)))
        self.wiki.decide(wiki_request, exchange(self.wiki, wiki_request, 'validator', wiki_decisions(context['proposal'])))
        self.wiki_id = self.repo.allocate_id()
        self.database = WikiDatabase(self.dsn, self.root)
        self.database.import_archive(self.wiki_id, self.repo.allocate_id(), build_archive(self.wiki.store))
        self.desktop = DesktopReadService(self.dsn, self.root, self.wiki_id, self.base / 'queries')

    def new_source(self, name):
        directory = self.base / name
        directory.mkdir()
        raw = (f'\ufeff# Unique synthetic source {uuid4()}\r\nCONFIG = 7\r\n\r\n'
               'def declared():\r\n    return "μ 😀 Cafe\u0301"\r\n\r\n'
               'class Declaration:\r\n    value = 3\r\n').encode('utf-8')
        (directory / 'example.py').write_bytes(raw)
        snapshot = directory / 'snapshot'
        manifest = code_snapshot.snapshot(directory, snapshot, paths=['example.py'])
        self.data.import_code_snapshot(snapshot)
        return snapshot, manifest['dossier_sha256'], (snapshot / 'dossier.md').read_bytes()

    def source_counts(self):
        with connection(self.dsn) as conn:
            return conn.execute('''SELECT
                (SELECT count(*) FROM canonical_store.information WHERE data_id=%s) AS information,
                (SELECT count(*) FROM compiler_runtime.operation_executions WHERE data_id=%s AND operation='d2i') AS d2i,
                (SELECT count(*) FROM canonical_store.data WHERE data_id=%s) AS data''', (self.data_id,) * 3).fetchone()

    def prepare(self, packet=None):
        packet = packet or self.packet
        options = {'data_version_ids': [self.version['version_id']]} if packet['data_id'] == self.data_id else {}
        return self.runtime.prepare('i2k', packet['data_id'], self.repo.allocate_id(), packet, selection=True, **options)

    def response(self, job):
        packet = job['input_snapshot']['input']
        source_units = [unit for unit in packet['model_input']['information']
                        if unit['code_context'][0]['representation_role'] == 'source_member']
        self.assertEqual(len(source_units), 2)
        nodes = [{'candidate_key': 'source-' + str(index), 'kind': 'proposition',
            'statement': f'Synthetic source declaration {index}; no execution claimed.',
            'semantic_payload': {'subject': 'Synthetic source ' + packet['data_id'],
                'relation': 'declares a fixture property', 'object': str(index), 'polarity': 'positive',
                'quantifier': 'source fixture', 'scope': 'storage test only', 'conditions': [], 'time_range': ''},
            'evidence': [{'information_id': unit['information_id'], 'quote': unit['content'],
                          'media_sha256': None, 'source_role': 'other'}],
            'uncertainties': [], 'identity_scope': 'source', 'selection_reason': 'Synthetic persistence fixture.'}
            for index, unit in enumerate(source_units)]
        response = {'nodes': nodes, 'source_requests': [], 'complete': True, 'coverage_notes': ['Synthetic fixture; no model.'],
            'reviews': [{'information_id': unit['information_id'],
                'disposition': 'selected' if unit in source_units else 'context_only',
                'candidate_keys': [node['candidate_key'] for node in nodes
                                  if node['evidence'][0]['information_id'] == unit['information_id']],
                'reason': 'Synthetic source review; no semantic-quality result.'}
                for unit in packet['model_input']['information']]}
        return review_fixtures.SourceReviewRuntimeTests.reviewed_response(self, job, base=response)

    @staticmethod
    def decisions(response):
        return {'complete': True, 'decisions': [{'candidate_key': node['candidate_key'], 'verdict': 'accepted',
            'equivalent_candidate_key': None, 'equivalent_revision_id': None,
            'reason_codes': ['synthetic_fixture'], 'reason': 'Synthetic independent verdict; no provider called.',
            'scope_correct': True, 'importance_justified': True} for node in response['nodes']],
            'reviews': [{'information_id': review['information_id'], 'verdict': 'confirmed',
                'reason_codes': ['synthetic_fixture'], 'reason': 'Synthetic independent I review.'}
                for review in response['reviews']],
            'source_review_decisions': {
                'targets': [{'target_id': review['target_id'], 'verdict': 'confirmed', 'reason': 'Synthetic target review.'}
                            for review in response['source_reviews']],
                'items': [{'item_key': item['item_key'], 'verdict': 'confirmed', 'reason': 'Synthetic item review.'}
                          for review in response['source_reviews'] for item in review['items']]}}

    def receipt(self, job, response, phase):
        current = self.runtime.show(job['execution_id'])
        helper = (k2k_fixtures.K2KRuntimeTests.receipt if current['operation'] == 'k2k'
                  else review_fixtures.SourceReviewRuntimeTests.receipt)
        receipt = helper(self, job, response, phase)
        versions = current['input_snapshot'].get('data_versions', [])
        if versions:
            receipt['delivered_data_version_ids'] = [version['version_id'] for version in versions]
        return receipt

    stage = review_fixtures.SourceReviewRuntimeTests.stage
    commit = review_fixtures.SourceReviewRuntimeTests.commit

    def held(self):
        job = self.prepare()
        response = self.response(job)
        decisions = self.decisions(response)
        decisions['source_review_decisions']['targets'][0].update(verdict='needs_review', reason='Synthetic unresolved review target.')
        result = self.commit(job, response, decisions)
        self.assertEqual(result['state'], 'needs_human')
        return result

    def assert_error(self, code, action):
        with self.assertRaises(PalimpsestError) as caught:
            action()
        self.assertEqual(caught.exception.code, code)

    def test_review_status_recognizes_accepted_new_and_resume_replays_without_D2I(self):
        parent = self.held()
        before = self.source_counts()
        preserved = deepcopy(self.runtime.show(parent['execution_id']))
        status = self.review.status(parent['execution_id'])
        self.assertEqual(status['next_action'], 'resume_review')
        self.assertEqual(len(status['accepted_knowledge']), 2)
        self.assertEqual({record['disposition'] for record in status['accepted_knowledge']}, {'accepted_new'})
        self.assertTrue(status['pending_target_ids'])
        selected = [item for item in status['items'] if item['candidate_keys']]
        self.assertTrue(selected)
        self.assertTrue(all(item['status'] == 'reviewed' for item in selected))
        request = self.repo.allocate_id()
        prepared = self.review.prepare_resume(parent['execution_id'], request)
        replay = self.review.prepare_resume(parent['execution_id'], request)
        self.assertEqual((prepared['action'], replay['action']), ('prepared', 'replayed'))
        self.assertEqual(prepared['execution_id'], replay['execution_id'])
        self.assertEqual(prepared['job']['input_snapshot']['input'], self.packet)
        self.assertEqual(prepared['job']['input_snapshot']['data_versions'][0]['version_id'], self.version['version_id'])
        self.assertEqual(self.review.status(prepared['execution_id'])['history'][0]['execution_id'], parent['execution_id'])
        self.assertEqual(self.source_counts(), before)
        self.assertEqual(self.runtime.show(parent['execution_id']), preserved)
        self.assertEqual(self.runtime.show(prepared['execution_id'])['model_calls'], [])
        self.assertEqual(self.store.read(self.data_id, len(self.raw)), self.raw)

    def test_distinct_concurrent_resume_requests_have_one_prepared_successor(self):
        parent = self.held()
        before = self.source_counts()
        barrier = Barrier(2)
        requests = [self.repo.allocate_id(), self.repo.allocate_id()]
        def attempt(identifier):
            barrier.wait(timeout=10)
            try:
                return {'request_id': identifier, **KnowledgeReview(KnowledgeRuntime(self.dsn)).prepare_resume(parent['execution_id'], identifier)}
            except PalimpsestError as error:
                return {'request_id': identifier, 'error_code': error.code, 'details': error.details}
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(attempt, identifier) for identifier in requests]
            results = [future.result(timeout=45) for future in futures]
        successful, = [row for row in results if row.get('action') == 'prepared']
        failed, = [row for row in results if 'error_code' in row]
        self.assertEqual(failed['error_code'], 'review_resume_in_progress')
        self.assertEqual(failed['details']['execution_id'], successful['execution_id'])
        with connection(self.dsn) as conn:
            rows = conn.execute('SELECT request_id FROM compiler_runtime.k_execution_contexts WHERE request_id=ANY(%s::uuid[])',
                                (requests,)).fetchall()
        self.assertEqual([str(row['request_id']) for row in rows], [successful['request_id']])
        self.assertEqual(self.source_counts(), before)

    def test_desktop_historical_same_Data_source_is_visible_and_foreign_sources_are_denied(self):
        old = self.source.prepare_input(self.markdown['execution_id'])
        before = self.source_counts()
        first = old['model_input']['information'][0]
        result = self.desktop.information(first['information_id'], self.markdown['execution_id'])
        self.assertEqual(result['content'], first['content'])
        self.assertEqual(result['source_format'], 'markdown')
        native = next(unit for unit in self.packet['model_input']['information'] if unit['code_context'][0].get('language') == 'python')
        current = self.desktop.information(native['information_id'], self.execution)
        self.assertEqual(current['code_context'], native['code_context'])
        self.assertEqual(current['source_format'], 'code')
        self.assert_error('desktop_information_owner_mismatch', lambda: self.desktop.information(first['information_id'], self.execution))
        original = self.desktop.artifact('original', self.data_id, source_execution_id=self.markdown['execution_id'])
        self.assertEqual(b64decode(original['base64']), self.raw)
        _, foreign_id, _ = self.new_source('foreign')
        foreign = self.source.compile_code(foreign_id)
        foreign_packet = self.source.prepare_input(foreign['execution_id'])
        self.assert_error('desktop_source_not_in_wiki', lambda: self.desktop.information(
            foreign_packet['target_information_ids'][0], foreign['execution_id']))
        self.assert_error('desktop_source_not_in_wiki', lambda: self.desktop.artifact('original', foreign_id,
                          source_execution_id=foreign['execution_id']))
        self.assert_error('desktop_source_not_in_wiki', lambda: self.desktop.artifact('original', self.data_id,
                          source_execution_id=foreign['execution_id']))
        self.assertEqual(self.source_counts(), before)
        self.assertFalse((self.base / 'queries').exists())

    def test_desktop_review_and_knowledge_catalogs_do_not_leak_foreign_Data(self):
        parent = self.held()
        _, foreign_id, _ = self.new_source('foreign')
        foreign = self.source.compile_code(foreign_id)
        packet = self.source.prepare_input(foreign['execution_id'])
        foreign_job = self.prepare(packet)
        foreign_result = self.commit(foreign_job, self.response(foreign_job))
        foreign_revision = foreign_result['records'][0]['result_node_revision_id']
        before = deepcopy(self.runtime.show(parent['execution_id']))
        counts = self.source_counts()
        review = self.desktop.dispatch({'operation': 'review_status', 'execution_id': parent['execution_id']})
        self.assertTrue(review['read_only'])
        self.assertEqual(len(review['accepted_knowledge']), 2)
        catalog = self.desktop.dispatch({'operation': 'review_catalog'})
        self.assertTrue(catalog['read_only'])
        self.assertIn(parent['execution_id'], [row['execution_id'] for row in catalog['executions']])
        self.assertNotIn(foreign_job['execution_id'], [row['execution_id'] for row in catalog['executions']])
        knowledge = self.desktop.dispatch({'operation': 'knowledge_catalog'})
        self.assertTrue(knowledge['read_only'])
        self.assertTrue(knowledge['nodes'])
        self.assertNotIn(foreign_revision, [row['knode_revision_id'] for row in knowledge['nodes']])
        self.assertTrue(all(row['data_id'] == self.data_id for row in knowledge['sources']))
        self.assert_error('desktop_review_not_in_wiki', lambda: self.desktop.review_status(foreign_job['execution_id']))
        self.assert_error('desktop_knowledge_not_in_wiki', lambda: self.desktop.knowledge_node(foreign_revision))
        self.assert_error('invalid_desktop_request', lambda: self.desktop.dispatch({'operation': 'review_resume', 'execution_id': parent['execution_id']}))
        self.assert_error('invalid_desktop_request', lambda: self.desktop.dispatch({'operation': 'review_status', 'execution_id': parent['execution_id'], 'data_id': foreign_id}))
        with connection(self.desktop.dsn) as conn:
            self.assertEqual(conn.execute('SHOW default_transaction_read_only').fetchone()['default_transaction_read_only'], 'on')
        self.assertEqual(self.runtime.show(parent['execution_id']), before)
        self.assertEqual(self.source_counts(), counts)
        self.assertFalse((self.base / 'queries').exists())

    def test_desktop_inference_preserves_actual_origin_premises_and_historical_version(self):
        source_job = self.prepare()
        seed = self.commit(source_job, self.response(source_job))
        premises = [record['result_node_revision_id'] for record in seed['records']]
        packet = self.runtime.inference_input(self.data_id, premises)
        job = self.runtime.prepare('k2k', self.data_id, self.repo.allocate_id(), packet,
                                   data_version_ids=[self.version['version_id']])
        response = k2k_fixtures.K2KRuntimeTests.response(self, job)
        self.runtime.stage(job['execution_id'], response, self.receipt(job, response, 'generator'))
        decisions = k2k_fixtures.K2KRuntimeTests.decisions(response)
        derived = self.runtime.decide(job['execution_id'], decisions, self.receipt(job, decisions, 'validator'))
        record = derived['records'][0]
        revision = record['result_node_revision_id']
        _, later_data, _ = self.new_source('later-version')
        later = self.versions.append(self.series, later_data, self.repo.allocate_id(), self.version['version_id'])
        counts = self.source_counts()
        before = deepcopy(self.runtime.show(job['execution_id']))
        result = self.desktop.dispatch({'operation': 'knowledge_node', 'node_revision_id': revision})
        node = result['node']
        self.assertTrue(result['read_only'])
        self.assertEqual(node['generation_origin']['origin_operation'], 'k2k')
        self.assertTrue(node['generation_origin']['is_inferred'])
        self.assertEqual(node['generation_origin']['origin_record_id'], record['record_id'])
        self.assertEqual(node['generation_origin']['premise_revision_ids'], premises)
        self.assertEqual({premise['knode_revision_id'] for premise in result['premise_nodes']}, set(premises))
        self.assertEqual(node['direct_groundings'], [])
        self.assertTrue(result['evidence'])
        self.assertEqual({item['evidence_basis'] for item in result['evidence']}, {'transitive'})
        self.assertEqual({item['data_id'] for item in result['evidence']}, {self.data_id})
        self.assertEqual({item['source_execution_id'] for item in result['evidence']}, {self.execution})
        for item in result['evidence']:
            information = self.desktop.information(item['information_id'], item['source_execution_id'])
            self.assertEqual(information['content'][item['char_start']:item['char_end']], item['quote'])
        self.assertEqual(node['source_version_status'], 'historical')
        self.assertEqual([version['version_id'] for version in node['origin_data_versions']], [self.version['version_id']])
        self.assertEqual(node['source_version_current_heads'], [{'series_id': self.series, 'version_id': later['version_id']}])
        catalog = self.desktop.knowledge_catalog()
        version, = catalog['data_versions']
        self.assertEqual(version['version_id'], self.version['version_id'])
        self.assertFalse(version['is_head'])
        self.assertEqual(self.source_counts(), counts)
        self.assertEqual(self.runtime.show(job['execution_id']), before)
        self.assertEqual(self.store.read(self.data_id, len(self.raw)), self.raw)

    def test_alternative_owned_support_does_not_expose_foreign_general_K_provenance(self):
        _, foreign_id, _ = self.new_source('foreign-general')
        foreign = self.source.compile_code(foreign_id)
        foreign_job = self.prepare(self.source.prepare_input(foreign['execution_id']))
        foreign_response = self.response(foreign_job)
        for node in foreign_response['nodes']:
            node['identity_scope'] = 'general'
            node['semantic_payload']['subject'] = 'Synthetic reusable declaration fixture'
        accepted = self.commit(foreign_job, foreign_response)
        local_job = self.prepare()
        local_response = self.response(local_job)
        for node in local_response['nodes']:
            node['identity_scope'] = 'general'
            node['semantic_payload']['subject'] = 'Synthetic reusable declaration fixture'
        decisions = self.decisions(local_response)
        for decision, record in zip(decisions['decisions'], accepted['records']):
            decision.update(verdict='reused', equivalent_revision_id=record['result_node_revision_id'])
        reused = self.commit(local_job, local_response, decisions)
        self.assertEqual({record['disposition'] for record in reused['records']}, {'reused'})
        preserved = deepcopy(self.runtime.graph(self.data_id))
        # A local support route does not authorize exposing the other Data's
        # exact hashes, retained quotes or version metadata through this Wiki.
        catalog = self.desktop.knowledge_catalog()
        self.assertNotIn(foreign_id, json.dumps(catalog, default=str, ensure_ascii=False))
        for record in reused['records']:
            try:
                detail = self.desktop.knowledge_node(record['result_node_revision_id'])
            except PalimpsestError as error:
                self.assertEqual(error.code, 'desktop_knowledge_not_in_wiki')
            else:
                self.assertNotIn(foreign_id, json.dumps(detail, default=str, ensure_ascii=False))
                self.assertTrue(all(item['data_id'] == self.data_id for item in detail['evidence']))
        self.assertEqual(self.runtime.graph(self.data_id), preserved)

    def test_prepare_call_exports_exact_request_and_replays_without_D2I_or_model(self):
        job = self.prepare()
        directory = self.base / 'review-request'
        before = deepcopy(self.runtime.show(job['execution_id']))
        counts = self.source_counts()
        exported = self.review.prepare_call(job['execution_id'], 'generator', directory, self.source.derived)
        request_path = Path(exported['request_file'])
        raw = request_path.read_bytes()
        request = json.loads(raw)
        prompt, schema = generation_request(job['input_snapshot'], [])
        self.assertEqual((request['prompt'], request['schema']), (prompt, schema))
        self.assertEqual(request['input_sha256'], job['input_digest'])
        self.assertEqual(request['delivered_information_ids'], self.packet['target_information_ids'])
        self.assertEqual(request['delivered_data_version_ids'], [self.version['version_id']])
        self.assertEqual(request['images'], [])
        self.assertFalse(exported['actual_delivery'])
        self.assertFalse(exported['replayed'])
        replay = self.review.prepare_call(job['execution_id'], 'generator', directory, self.source.derived)
        self.assertTrue(replay['replayed'])
        self.assertFalse(replay['actual_delivery'])
        self.assertEqual(request_path.read_bytes(), raw)
        self.assertEqual(self.runtime.show(job['execution_id']), before)
        self.assertEqual(self.runtime.show(job['execution_id'])['model_calls'], [])
        self.assertEqual(self.source_counts(), counts)
        # Staging a labelled synthetic response is separate from exporting the
        # validator request. Export must not add another model-call receipt.
        self.stage(job, self.response(job))
        staged = deepcopy(self.runtime.show(job['execution_id']))
        validation = self.runtime.validation_context(job['execution_id'])
        exported = self.review.prepare_call(job['execution_id'], 'validator', directory, self.source.derived)
        request = json.loads(Path(exported['request_file']).read_bytes())
        prompt, schema = validation_request(validation, [])
        self.assertEqual((request['prompt'], request['schema']), (prompt, schema))
        self.assertEqual(request['input_sha256'], validation['validation_context_sha'])
        self.assertEqual(request['delivered_data_version_ids'], [self.version['version_id']])
        self.assertFalse(exported['actual_delivery'])
        self.assertEqual(self.runtime.show(job['execution_id']), staged)
        other = self.prepare()
        self.assert_error('knowledge_call_directory_conflict', lambda: self.review.prepare_call(
            other['execution_id'], 'generator', directory, self.source.derived))
        self.assert_error('invalid_knowledge_phase', lambda: self.review.prepare_call(
            job['execution_id'], 'd2i', directory, self.source.derived))
        self.assertEqual(self.source_counts(), counts)
        self.assertEqual(request_path.read_bytes(), raw)

    def test_prepare_call_rejects_request_and_coordinated_binding_tampering_before_delivery(self):
        job = self.prepare()
        directory = self.base / 'tamper-request'
        exported = self.review.prepare_call(job['execution_id'], 'generator', directory, self.source.derived)
        request_path = Path(exported['request_file'])
        binding_path = directory / 'generator-binding.json'
        original_request, original_binding = request_path.read_bytes(), binding_path.read_bytes()
        before = deepcopy(self.runtime.show(job['execution_id']))
        counts = self.source_counts()
        for change in ('prompt', 'prompt_and_binding_digest', 'delivered_scope_and_binding_digest', 'binding_execution'):
            request, binding = json.loads(original_request), json.loads(original_binding)
            if change in ('prompt', 'prompt_and_binding_digest'):
                request['prompt'] += '\nAltered synthetic request: this text was not in the frozen source request.'
            elif change == 'delivered_scope_and_binding_digest':
                request['delivered_information_ids'].pop()
                request['delivered_data_version_ids'] = []
            else:
                binding['execution_id'] = self.repo.allocate_id()
            if change in ('prompt_and_binding_digest', 'delivered_scope_and_binding_digest'):
                binding['request_sha256'] = digest(request)
            changed_request = json.dumps(request, ensure_ascii=False, sort_keys=True).encode('utf-8')
            changed_binding = json.dumps(binding, ensure_ascii=False, sort_keys=True).encode('utf-8')
            request_path.write_bytes(changed_request)
            binding_path.write_bytes(changed_binding)
            with self.subTest(change=change):
                self.assert_error('knowledge_call_directory_conflict', lambda: self.review.prepare_call(
                    job['execution_id'], 'generator', directory, self.source.derived))
                self.assertEqual(request_path.read_bytes(), changed_request)
                self.assertEqual(binding_path.read_bytes(), changed_binding)
                self.assertEqual(self.runtime.show(job['execution_id']), before)
                self.assertEqual(self.runtime.show(job['execution_id'])['model_calls'], [])
                self.assertEqual(self.source_counts(), counts)
        request_path.write_bytes(original_request)
        binding_path.write_bytes(original_binding)
        replay = self.review.prepare_call(job['execution_id'], 'generator', directory, self.source.derived)
        self.assertTrue(replay['replayed'])
        self.assertFalse(replay['actual_delivery'])
        self.assertEqual(replay['request_sha256'], exported['request_sha256'])
        self.assertEqual(self.runtime.show(job['execution_id']), before)
        self.assertEqual(self.runtime.show(job['execution_id'])['model_calls'], [])
        self.assertEqual(self.source_counts(), counts)


if __name__ == '__main__':
    unittest.main()
