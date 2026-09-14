"""Isolated PostgreSQL + real Wiki files; all model exchanges are synthetic."""

import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from palimpsest.artifact_store import ArtifactStore
from palimpsest.canonical_store import PostgresRepository, connection
from palimpsest.compiler_runtime import CompilerRuntime
from palimpsest.errors import PalimpsestError
from palimpsest.knowledge_runtime import KnowledgeRuntime
from palimpsest import multi_source_i2k
from palimpsest.paper_wiki_runtime import PaperWikiRuntime
from palimpsest.service import DataService
from palimpsest.wiki_archive import build_archive
from palimpsest.wiki_database import WikiDatabase
from palimpsest.wiki_refresh import WikiRefreshRuntime
import test_knowledge_revision_integration as revisions
from test_paper_wiki import decisions
from test_paper_wiki_runtime import exchange, synthetic_proposal


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires explicitly provisioned Linux PostgreSQL fixture')
class WikiRefreshIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        revisions.KnowledgeRevisionIntegrationTests.setUpClass()
        cls.dsn = os.environ['PALIMPSEST_TEST_DSN']

    def setUp(self):
        self.fixture = revisions.KnowledgeRevisionIntegrationTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.runtime = PaperWikiRuntime(self.dsn, f.root, f.base / 'wiki')
        self.wiki_id, self.base_import = f.repo.allocate_id(), f.repo.allocate_id()
        identifier = f.repo.allocate_id()
        self.runtime.prepare(f.source_result['execution_id'], identifier,
            {'title': 'Synthetic source Wiki for material revision', 'filename': 'source.md'})
        context = self.runtime.stage(identifier, exchange(self.runtime, identifier, 'generator',
                                                           synthetic_proposal(f.packet)))
        self.runtime.decide(identifier, exchange(self.runtime, identifier, 'validator', decisions(context['proposal'])))
        self.original = build_archive(self.runtime.store)
        self.database = WikiDatabase(self.dsn, f.root)
        self.database.sync(self.wiki_id, self.base_import, self.runtime.store.root)
        job = f.prepare_source(f.source_target)
        result = f.commit(job, f.source_response([f.source_candidate('observation', 'observation', 'four')]))
        self.impact_record_id = result['records'][0]['record_id']
        self.refresh = WikiRefreshRuntime(self.dsn, f.root, f.base / 'refresh')
        self.identifier = f.repo.allocate_id()

    def test_exact_impact_full_i_regeneration_independent_validation_and_atomic_import(self):
        plan = self.refresh.prepare([self.impact_record_id, self.impact_record_id], self.wiki_id,
                                    self.identifier, source_data_ids=[self.fixture.data_id])
        self.assertEqual(plan['impact_record_ids'], [self.impact_record_id])
        self.assertEqual(len(plan['targets']), 1)
        self.assertTrue(plan['targets'][0]['impact_links'])
        self.assertEqual(plan['base_import_id'], self.base_import)
        self.assertTrue(self.refresh.prepare(self.impact_record_id, self.wiki_id, self.identifier,
            source_data_ids=[self.fixture.data_id])['replayed'])
        current = self.refresh.advance(self.identifier)
        self.assertEqual(current['state'], 'awaiting_generator')
        runtime = self.refresh._runtime(self.identifier)
        job = runtime.show(current['request_id'])
        self.assertEqual(job['input_snapshot']['input'], self.fixture.packet)
        current = self.refresh.accept(self.identifier, 'generator', exchange(runtime, current['request_id'],
            'generator', synthetic_proposal(self.fixture.packet, text_suffix='Regenerated synthetic wording.')))
        self.assertEqual(current['state'], 'awaiting_validator')
        context = runtime._context(runtime.show(current['request_id']))
        validation = exchange(runtime, current['request_id'], 'validator', decisions(context['proposal']))
        guarded_connections, guarded_heads = [], []
        def fence(conn):
            guarded_connections.append(id(conn))
            row = conn.execute('SELECT current_import_id FROM wiki_projection.wikis WHERE wiki_id=%s',
                               (self.wiki_id,)).fetchone()
            guarded_heads.append(str(row['current_import_id']))
            if len(guarded_connections) == 2:
                raise PalimpsestError('synthetic_claim_expired', 'Synthetic lease expired before DB commit.')
        with self.assertRaises(PalimpsestError) as raised:
            self.refresh.accept(self.identifier, 'validator', validation, transaction_guard=fence)
        self.assertEqual(raised.exception.code, 'synthetic_claim_expired')
        self.assertEqual(len(set(guarded_connections)), 1)
        self.assertEqual(guarded_heads, [self.base_import, plan['sync_request_id']])
        self.assertEqual(self.database.catalog(self.wiki_id)['import_id'], self.base_import)
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS count FROM wiki_projection.imports WHERE request_id=%s',
                                          (plan['sync_request_id'],)).fetchone()['count'], 0)
        finished = self.refresh.advance(self.identifier)
        self.assertEqual(finished['state'], 'completed')
        self.assertEqual(self.database.catalog(self.wiki_id)['import_id'], plan['sync_request_id'])
        history = self.database.history(self.wiki_id, plan['targets'][0]['page_id'])
        self.assertEqual(len(history['snapshots']), 2)
        self.assertEqual(history['snapshots'][1], self.original['snapshots'][plan['targets'][0]['snapshot_id']])
        self.assertEqual(build_archive(self.runtime.store)['files'], self.original['files'])
        self.assertEqual(self.fixture.source_state(), self.fixture.source_before)
        self.assertEqual(self.refresh.advance(self.identifier), finished)

    def test_unrelated_source_expansion_and_stale_import_are_held(self):
        with self.assertRaises(PalimpsestError) as raised:
            self.refresh.prepare(self.impact_record_id, self.wiki_id, self.identifier,
                                 source_data_ids=['f' * 64])
        self.assertEqual(raised.exception.code, 'wiki_refresh_unrelated_source')
        self.refresh.prepare(self.impact_record_id, self.wiki_id, self.identifier)
        self.database.sync(self.wiki_id, self.fixture.repo.allocate_id(), self.runtime.store.root,
                           expected_head=self.base_import)
        with self.assertRaises(PalimpsestError) as raised:
            self.refresh.advance(self.identifier)
        self.assertEqual(raised.exception.code, 'wiki_refresh_head_changed')
        self.assertFalse(Path(self.refresh.store.root / f'refreshes/{self.identifier}/wiki/catalog.json').exists())


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires explicitly provisioned Linux PostgreSQL fixture')
class FirstKnowledgeWikiRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        revisions.KnowledgeRevisionIntegrationTests.setUpClass()
        cls.dsn = os.environ['PALIMPSEST_TEST_DSN']

    def test_first_new_k_refreshes_source_wiki_with_zero_previous_k_links(self):
        with TemporaryDirectory(prefix='palimpsest-wiki-first-k-') as directory:
            base = Path(directory)
            # Reuse the structured synthetic exchange helpers, without the
            # revision fixture's seed-K setup: this source starts with zero K.
            source = revisions.KnowledgeRevisionIntegrationTests('runTest')
            source.dsn, source.base, source.root = self.dsn, base, base / 'artifacts'
            source.repo, source.runtime = PostgresRepository(self.dsn), KnowledgeRuntime(self.dsn)
            path = base / 'source.md'
            path.write_text(f'# First Knowledge Wiki fixture {uuid4()}\n\nThe fixture explicitly reports one source condition.\n',
                            encoding='utf-8')
            source.data_id = DataService(source.repo, ArtifactStore(source.root), actor_ref='synthetic-user').import_file(
                path, media_type='text/markdown')['data_id']
            compiler = CompilerRuntime(self.dsn, source.root)
            source.source_result = compiler.compile_markdown(source.data_id)
            source.packet = compiler.prepare_input(source.source_result['execution_id'])
            source.bundle = multi_source_i2k.combine_packets([source.packet])
            source.unit = next(unit for unit in source.bundle['model_input']['information'] if unit['content'].strip())
            runtime = PaperWikiRuntime(self.dsn, source.root, base / 'wiki')
            identifier, wiki_id, old_import = [source.repo.allocate_id() for _ in range(3)]
            runtime.prepare(source.source_result['execution_id'], identifier,
                {'title': 'Synthetic Wiki before its first K', 'filename': 'source.md'})
            proposal = synthetic_proposal(source.packet)
            context = runtime.stage(identifier, exchange(runtime, identifier, 'generator', proposal))
            runtime.decide(identifier, exchange(runtime, identifier, 'validator', decisions(context['proposal'])))
            database = WikiDatabase(self.dsn, source.root)
            first = database.sync(wiki_id, old_import, runtime.store.root)
            self.assertEqual(first['related_link_count'], 0)
            with patch.object(CompilerRuntime, 'compile_markdown', side_effect=AssertionError('Refresh must not run D2I')):
                made = source.commit(source.prepare_source(), source.source_response([
                    source.source_candidate('first', 'proposition', 'one reported source condition')]))
                self.assertEqual(made['records'][0]['disposition'], 'accepted_new')
                refresh = WikiRefreshRuntime(self.dsn, source.root, base / 'refresh')
                request = source.repo.allocate_id()
                plan = refresh.prepare(made['records'][0]['record_id'], wiki_id, request,
                                       source_data_ids=[source.data_id])
                self.assertEqual(plan['changes'][0]['change_kind'], 'new_node')
                self.assertFalse(plan['changes'][0]['stored_impact_present'])
                self.assertEqual(plan['targets'][0]['impact_links'], [])
                current = refresh.advance(request)
                editing = refresh._runtime(request)
                current = refresh.accept(request, 'generator', exchange(editing, current['request_id'], 'generator', proposal))
                context = editing._context(editing.show(current['request_id']))
                finished = refresh.accept(request, 'validator', exchange(editing, current['request_id'],
                    'validator', decisions(context['proposal'])))
            self.assertEqual(finished['state'], 'completed')
            self.assertGreater(finished['import']['related_link_count'], 0)
            self.assertEqual(database.catalog(wiki_id)['import_id'], plan['sync_request_id'])


if __name__ == '__main__':
    unittest.main()
