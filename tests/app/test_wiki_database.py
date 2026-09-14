"""Real PostgreSQL Wiki contracts with synthetic sources and model receipts.

Only the explicitly configured fixture database named `palimpsest` is allowed.
No test migrates, deletes history, calls a model, or modifies a real paper DB.
"""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from threading import Barrier
import unittest
from unittest.mock import patch

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from palimpsest.compiler_runtime import CompilerRuntime
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.paper_wiki_runtime import PaperWikiRuntime
from palimpsest.wiki_archive import build_archive
from palimpsest.wiki_database import WikiDatabase
from palimpsest.wiki_projection_store import ProjectionStore
from test_paper_wiki import decisions
import test_paper_wiki_runtime as wiki_fixtures
import test_knowledge_postgres as knowledge_fixtures
from test_paper_wiki_runtime import exchange, synthetic_proposal


def _insert(conn, table, row):
    conn.execute(sql.SQL('INSERT INTO wiki_projection.{} ({}) VALUES ({})').format(
        sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, row)),
        sql.SQL(',').join(sql.Placeholder() for _ in row)),
        [Jsonb(value) if isinstance(value, (dict, list)) else value for value in row.values()])


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires Linux and explicit default fixture PostgreSQL DSN')
class WikiDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['PALIMPSEST_TEST_DSN']
        with psycopg.connect(cls.dsn) as conn:
            if conn.execute('SELECT current_database()').fetchone()[0] != 'palimpsest':
                raise RuntimeError('Wiki fixtures must run only against the database named palimpsest')
            if not conn.execute("SELECT 1 FROM compiler_runtime.schema_migrations WHERE version='0008_wiki_projection'").fetchone():
                raise RuntimeError('Provision migration 0008 in the default fixture DB before running tests')

    def setUp(self):
        wiki_fixtures.PaperWikiPostgresTests.setUp(self)
        self.database = WikiDatabase(self.dsn, self.base / 'artifacts')
        self.wiki_id = self.repository.allocate_id()
        self.import_id = self.repository.allocate_id()
        self.compile()
        self.archive = build_archive(self.runtime.store)

    def connection(self):
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def compile(self, suffix=''):
        generator = exchange(self.runtime, self.identifier, 'generator', synthetic_proposal(self.packet, text_suffix=suffix))
        context = self.runtime.stage(self.identifier, generator)
        validator = exchange(self.runtime, self.identifier, 'validator', decisions(context['proposal']))
        self.compiled = self.runtime.decide(self.identifier, validator)
        return self.compiled

    def edit_paper(self, suffix='Updated synthetic wording.'):
        self.identifier = self.repository.allocate_id()
        self.runtime.prepare(self.execution, self.identifier,
                             {'title': 'Synthetic Markdown paper', 'filename': 'fixture.md'})
        self.compile(suffix)
        self.archive = build_archive(self.runtime.store)

    def import_current(self, **kwargs):
        return self.database.import_archive(self.wiki_id, self.import_id, self.archive, **kwargs)

    def assert_error(self, code, operation):
        with self.assertRaises(PalimpsestError) as caught:
            operation()
        self.assertEqual(caught.exception.code, code)

    def test_real_source_import_replay_and_changed_request_preserve_canonical_state(self):
        before = wiki_fixtures.PaperWikiPostgresTests.canonical_state(self)
        result = self.import_current()
        self.assertFalse(result['replayed'])
        self.assertEqual(result['canonical_writes'], 0)
        self.assertEqual(result['new_d2i_calls'], 0)
        self.assertEqual(result['model_calls'], 0)
        self.assertEqual(result['paper_count'], 1)
        self.assertTrue(self.import_current()['replayed'])
        self.assertEqual(wiki_fixtures.PaperWikiPostgresTests.canonical_state(self), before)
        self.assertEqual(self.database.catalog(self.wiki_id)['import_id'], self.import_id)
        self.assert_error('idempotency_conflict', lambda: self.import_current(expected_head=self.import_id))
        changed = deepcopy(self.archive)
        changed['snapshots'] = {}  # Parsed objects are rebuilt from exact files.
        self.assertTrue(self.database.import_archive(self.wiki_id, self.import_id, changed)['replayed'])
        self.edit_paper()
        self.assert_error('idempotency_conflict', self.import_current)

    def test_before_current_rolls_back_and_after_commit_lost_reply_replays(self):
        def fail_before(phase):
            if phase == 'before_current':
                raise RuntimeError('Synthetic interruption before current selection')
        with self.assertRaises(RuntimeError):
            self.import_current(checkpoint=fail_before)
        with self.connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM wiki_projection.wikis WHERE wiki_id=%s',
                                          (self.wiki_id,)).fetchone()['n'], 0)
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM wiki_projection.imports WHERE request_id=%s',
                                          (self.import_id,)).fetchone()['n'], 0)
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM wiki_projection.snapshots WHERE wiki_id=%s',
                                          (self.wiki_id,)).fetchone()['n'], 0)
        def fail_after(phase):
            if phase == 'after_commit':
                raise RuntimeError('Synthetic lost reply after committed selection')
        with self.assertRaises(RuntimeError):
            self.import_current(checkpoint=fail_after)
        self.assertEqual(self.database.catalog(self.wiki_id)['import_id'], self.import_id)
        recovered = self.import_current()
        self.assertTrue(recovered['replayed'])
        with self.connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM wiki_projection.imports WHERE wiki_id=%s',
                                          (self.wiki_id,)).fetchone()['n'], 1)

    def test_concurrent_same_expected_head_accepts_one_and_preserves_loser(self):
        first = self.import_current()
        barrier = Barrier(2)
        identifiers = [self.repository.allocate_id(), self.repository.allocate_id()]
        def attempt(identifier):
            barrier.wait(timeout=10)
            try:
                return self.database.import_archive(self.wiki_id, identifier, self.archive,
                                                     expected_head=first['request_id'])
            except PalimpsestError as error:
                return {'error_code': error.code, 'request_id': identifier}
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(attempt, identifier) for identifier in identifiers]
            results = [future.result(timeout=30) for future in futures]
        accepted = [result for result in results if 'error_code' not in result]
        rejected = [result for result in results if 'error_code' in result]
        self.assertEqual(len(accepted), 1)
        self.assertEqual([result['error_code'] for result in rejected], ['wiki_database_head_changed'])
        self.assertEqual(self.database.catalog(self.wiki_id)['import_id'], accepted[0]['request_id'])
        with self.connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM wiki_projection.imports WHERE request_id=%s',
                                          (rejected[0]['request_id'],)).fetchone()['n'], 0)

    def test_restore_preserves_exact_files_and_old_catalog_export(self):
        old_archive = self.archive
        old_catalog = self.archive['current_catalog_sha256']
        self.import_current()
        self.edit_paper()
        new_import = self.repository.allocate_id()
        self.database.import_archive(self.wiki_id, new_import, self.archive, expected_head=self.import_id)
        page_id = self.compiled['paper_page_id']
        history = self.database.history(self.wiki_id, page_id)
        self.assertEqual(len(history['snapshots']), 2)
        old_history = self.database.history(self.wiki_id, page_id, import_id=self.import_id)
        self.assertEqual(len(old_history['snapshots']), 1)
        restored = self.base / 'restored'
        self.database.restore(self.wiki_id, restored, import_id=self.import_id)
        for path, raw in old_archive['files'].items():
            self.assertEqual((restored / path).read_bytes(), raw)
        current_restored = self.base / 'restored-current'
        self.database.restore(self.wiki_id, current_restored)
        self.assertEqual(build_archive(self.runtime.store)['manifest_sha256'], self.archive['manifest_sha256'])
        old_export = self.runtime.export(catalog_sha256=old_catalog)
        exported = self.database.export(self.wiki_id, self.base / 'db-export', catalog_sha256=old_catalog)['export']
        self.assertEqual(exported['catalog_sha256'], old_export['catalog_sha256'])
        for entry in old_export['files']:
            self.assertEqual((Path(exported['directory']) / entry['path']).read_bytes(),
                             (Path(old_export['directory']) / entry['path']).read_bytes())
        self.assertEqual((Path(exported['directory']) / 'index.md').read_bytes(),
                         (Path(old_export['directory']) / 'index.md').read_bytes())

    def test_coherently_rehashed_forged_i_archive_is_refused_by_real_source_db(self):
        forged = deepcopy(self.packet)
        unit = forged['model_input']['information'][0]
        unit['content'] = ('X' if unit['content'][0] != 'X' else 'Y') + unit['content'][1:]
        unit['content_fingerprint'] = sha256(unit['content'].encode()).hexdigest()
        forged['input_sha256'] = digest({k: v for k, v in forged.items() if k != 'input_sha256'})
        runtime = PaperWikiRuntime(self.dsn, self.base / 'artifacts', self.base / 'forged-wiki')
        identifier = self.repository.allocate_id()
        # Deliberately bypass only the file Wiki's canonical checks to construct
        # an internally consistent hostile archive. PG import is never mocked.
        with patch.object(runtime, '_source', return_value=forged), patch.object(runtime, '_verify_source'):
            runtime.prepare(self.execution, identifier, {'title': 'Synthetic forged input', 'filename': 'fixture.md'})
            generator = exchange(runtime, identifier, 'generator', synthetic_proposal(forged))
            context = runtime.stage(identifier, generator)
            runtime.decide(identifier, exchange(runtime, identifier, 'validator', decisions(context['proposal'])))
        archive = build_archive(runtime.store)
        before = wiki_fixtures.PaperWikiPostgresTests.canonical_state(self)
        self.assert_error('knowledge_input_changed', lambda: self.database.import_archive(
            self.wiki_id, self.import_id, archive))
        self.assertEqual(wiki_fixtures.PaperWikiPostgresTests.canonical_state(self), before)
        with self.connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM wiki_projection.wikis WHERE wiki_id=%s',
                                         (self.wiki_id,)).fetchone()['n'], 0)

    def test_restore_conflict_preflight_preserves_existing_payload_without_partial_writes(self):
        self.import_current()
        target = ProjectionStore(self.base / 'occupied-restore-target')
        existing = b'{ "different_existing_catalog": true }\n'
        target.write_bytes('catalog.json', existing)
        def payloads():
            return {path.relative_to(target.root).as_posix(): path.read_bytes()
                    for path in target.root.rglob('*') if path.is_file()
                    and path.relative_to(target.root).parts[0] not in ('locks', '.paper-wiki.json')}
        before = payloads()
        self.assertEqual(before, {'catalog.json': existing})
        self.assert_error('wiki_database_restore_conflict', lambda: self.database.restore(
            self.wiki_id, target.root))
        self.assertEqual(payloads(), before)
        self.assertFalse((target.root / 'snapshots').exists())
        self.assertFalse((target.root / 'jobs').exists())
        self.assertFalse((target.root / 'media').exists())
        self.assertEqual(self.database.catalog(self.wiki_id)['import_id'], self.import_id)

    def _copied_snapshot(self, conn, **changes):
        row = dict(conn.execute('SELECT * FROM wiki_projection.snapshots WHERE wiki_id=%s AND snapshot_id=%s',
                               (self.wiki_id, self.compiled['paper_snapshot_id'])).fetchone())
        row.update(snapshot_id=self.repository.allocate_id(), **changes)
        payload = deepcopy(row['payload'])
        for key in ('snapshot_id', 'source_execution_id', 'data_id', 'previous_snapshot_id', 'previous_snapshot_sha256'):
            value = row[key]
            payload[key] = str(value) if value is not None else None
        row['payload'] = payload
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')
        row.update(raw_sha256=sha256(raw).hexdigest(), snapshot_sha256=digest(payload))
        _insert(conn, 'blobs', {'sha256': row['raw_sha256'], 'content': raw})
        _insert(conn, 'snapshots', row)

    def test_direct_sql_citation_source_owner_parent_and_immutability_reject(self):
        self.import_current()
        with self.connection() as conn:
            citation = dict(conn.execute('SELECT * FROM wiki_projection.citations WHERE wiki_id=%s LIMIT 1',
                                        (self.wiki_id,)).fetchone())
            topic = conn.execute("SELECT snapshot_id,snapshot_sha256 FROM wiki_projection.snapshots WHERE wiki_id=%s AND data_id IS NULL LIMIT 1",
                                 (self.wiki_id,)).fetchone()
        for change in ({'quote': 'x' * len(citation['quote'])}, {'data_id': 'f' * 64},
                       {'source_execution_id': self.repository.allocate_id()}):
            with self.subTest(change=list(change)), self.assertRaises(psycopg.Error) as caught, self.connection() as conn:
                row = {**citation, **change}
                _insert(conn, 'citations', row)
            self.assertNotEqual(caught.exception.sqlstate, '23505')  # Not merely a duplicate primary key.
        with self.assertRaises(psycopg.Error), self.connection() as conn:
            _insert(conn, 'pages', {'wiki_id': self.wiki_id, 'page_id': self.repository.allocate_id(),
                                  'kind': 'paper', 'data_id': 'f' * 64, 'topic_key': None})
        with self.assertRaises(psycopg.Error), self.connection() as conn:
            self._copied_snapshot(conn, source_execution_id=self.repository.allocate_id())
        with self.assertRaises(psycopg.Error), self.connection() as conn:
            self._copied_snapshot(conn, previous_snapshot_id=topic['snapshot_id'],
                                  previous_snapshot_sha256=topic['snapshot_sha256'])
        for table in ('snapshots', 'items', 'citations', 'catalogs', 'pages', 'imports'):
            with self.subTest(table=table), self.assertRaises(psycopg.Error), self.connection() as conn:
                conn.execute(sql.SQL('DELETE FROM wiki_projection.{} WHERE wiki_id=%s').format(sql.Identifier(table)),
                             (self.wiki_id,))
        with self.assertRaises(psycopg.Error), self.connection() as conn:
            conn.execute('UPDATE wiki_projection.snapshots SET payload=payload WHERE wiki_id=%s', (self.wiki_id,))
        self.assertEqual(self.database.catalog(self.wiki_id)['import_id'], self.import_id)

    def _use_real_k_source(self):
        fixture = knowledge_fixtures.KnowledgePostgresTests(methodName='runTest')
        fixture.dsn = self.dsn
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.base, self.owner = fixture.root, fixture.data_id
        self.database = WikiDatabase(self.dsn, self.base / 'artifacts')
        with fixture.connection() as conn:
            self.execution = str(conn.execute('SELECT execution_id FROM compiler_runtime.records r '
                'JOIN canonical_store.information i ON i.origin_record_id=r.record_id WHERE information_id=%s',
                (fixture.information_id,)).fetchone()['execution_id'])
            first = fixture.classified_node(conn)
        self.packet = CompilerRuntime(self.dsn, self.base / 'artifacts').prepare_input(self.execution)
        self.runtime = PaperWikiRuntime(self.dsn, self.base / 'artifacts', self.base / 'wiki')
        self.identifier = self.repository.allocate_id()
        self.runtime.prepare(self.execution, self.identifier, {'title': 'Synthetic Markdown paper', 'filename': 'fixture.md'})
        self.compile()
        self.archive = build_archive(self.runtime.store)
        return fixture, first

    def test_real_k_revision_links_are_historical_navigation_not_semantic_support(self):
        fixture, first = self._use_real_k_source()
        first_import = self.import_current()
        first_related = self.database.related(self.wiki_id, self.compiled['paper_page_id'])
        self.assertGreater(len(first_related['links']), 0)
        self.assertEqual(first_related['relation'], 'shared_source_evidence')
        self.assertFalse(first_related['semantic_support_validated'])
        self.assertEqual({link['knode_revision_id'] for link in first_related['links']}, {str(first['revision_id'])})
        flagged_id = self.repository.allocate_id()
        annotation = {'node_revision_id': str(first['revision_id']), 'reason': 'Synthetic explicit review requirement.'}
        self.database.import_archive(self.wiki_id, flagged_id, self.archive, expected_head=self.import_id,
                                     review_annotations=[annotation])
        hidden = self.database.related(self.wiki_id, self.compiled['paper_page_id'])
        self.assertEqual(hidden['links'], [])
        self.assertGreater(hidden['review_required_links'], 0)
        flagged = self.database.related(self.wiki_id, self.compiled['paper_page_id'], include_review_required=True)
        self.assertEqual(flagged['links'][0]['review_annotations'], [annotation])
        self.assertFalse(flagged['semantic_support_validated'])
        refreshed_id = self.repository.allocate_id()
        refreshed = self.database.import_archive(self.wiki_id, refreshed_id, self.archive, expected_head=flagged_id)
        self.assertEqual(refreshed['knowledge_state_version'], first_import['knowledge_state_version'])
        still_hidden = self.database.related(self.wiki_id, self.compiled['paper_page_id'])
        self.assertEqual(still_hidden['links'], [])
        self.assertEqual(still_hidden['review_required_links'], hidden['review_required_links'])
        retained = self.database.related(self.wiki_id, self.compiled['paper_page_id'], include_review_required=True)
        self.assertTrue(all(link['review_annotations'] == [annotation] for link in retained['links']))
        self.assertTrue(self.database.import_archive(self.wiki_id, refreshed_id, self.archive,
                                                    expected_head=flagged_id)['replayed'])
        with self.connection() as conn:
            self.assertEqual(conn.execute('SELECT review_annotations FROM wiki_projection.imports WHERE request_id=%s',
                                          (refreshed_id,)).fetchone()['review_annotations'], [annotation])
        with self.connection() as conn:
            link_row = dict(conn.execute('SELECT * FROM wiki_projection.knowledge_links WHERE request_id=%s LIMIT 1',
                                         (self.import_id,)).fetchone())
        link_row['payload']['semantic_support_validated'] = True
        with self.assertRaises(psycopg.Error) as caught, self.connection() as conn:
            _insert(conn, 'knowledge_links', link_row)
        self.assertNotEqual(caught.exception.sqlstate, '23505')
        with fixture.connection() as conn:
            later = fixture.revise(conn, first, value=4)
        old = self.database.related(self.wiki_id, self.compiled['paper_page_id'], import_id=self.import_id)
        self.assertEqual({link['knode_revision_id'] for link in old['links']}, {str(first['revision_id'])})
        self.assertTrue(all(not link['is_current_now'] for link in old['links']))
        old_flagged = self.database.related(self.wiki_id, self.compiled['paper_page_id'],
                                           import_id=refreshed_id, include_review_required=True)
        self.assertTrue(all(link['knode_revision_id'] == str(first['revision_id'])
                            and link['review_annotations'] == [annotation] and not link['is_current_now']
                            for link in old_flagged['links']))
        self.assertTrue(self.import_current()['replayed'])
        with self.connection() as conn:
            saved = conn.execute('SELECT payload FROM wiki_projection.knowledge_links WHERE request_id=%s LIMIT 1',
                                 (self.import_id,)).fetchone()['payload']
        self.assertEqual(saved['knode_revision_id'], str(first['revision_id']))
        self.edit_paper()
        new_import = self.repository.allocate_id()
        result = self.database.import_archive(self.wiki_id, new_import, self.archive,
                                              expected_head=refreshed_id, review_annotations=[annotation])
        self.assertGreater(result['knowledge_state_version'], first_import['knowledge_state_version'])
        current = self.database.related(self.wiki_id, self.compiled['paper_page_id'])
        self.assertEqual({link['knode_revision_id'] for link in current['links']}, {str(later['revision_id'])})
        self.assertTrue(all(link['is_current_now'] for link in current['links']))
        self.assertFalse(current['semantic_support_validated'])
        self.assertEqual(current['review_required_links'], 0)
        self.assertTrue(all(link['review_annotations'] == [] for link in current['links']))
        with self.connection() as conn:
            self.assertEqual(conn.execute('SELECT review_annotations FROM wiki_projection.imports WHERE request_id=%s',
                                          (new_import,)).fetchone()['review_annotations'], [annotation])

    def _copy_import_transaction(self, conn, mutation):
        """Uncommitted direct SQL copy with fresh IDs, for negative DB guards."""
        copied = dict(conn.execute('SELECT * FROM wiki_projection.imports WHERE request_id=%s',
                                   (self.import_id,)).fetchone())
        new_id = str(conn.execute('SELECT uuidv7() AS id').fetchone()['id'])
        copied.update(request_id=new_id, expected_head=self.import_id)
        copied['result']['request_id'] = new_id
        if mutation == 'forged_graph_node':
            for node in copied['graph_payload']['nodes']:
                if node['knode_revision_id'] == self.guard_revision:
                    node['statement'] += ' Fabricated statement not in canonical K.'
            copied['graph_sha256'] = digest(copied['graph_payload'])
        copied['request_fingerprint'] = digest({'schema_version': 'wiki-postgres-projection-v1',
            'wiki_id': self.wiki_id, 'expected_head': self.import_id,
            'manifest_sha256': copied['manifest_sha256'], 'catalog_sha256': copied['catalog_sha256'],
            'review_annotations': copied['review_annotations']})
        _insert(conn, 'imports', copied)
        files = conn.execute('SELECT * FROM wiki_projection.files WHERE request_id=%s ORDER BY path',
                             (self.import_id,)).fetchall()
        for index, row in enumerate(files):
            if mutation == 'missing_file' and index == 0:
                continue
            _insert(conn, 'files', {**row, 'request_id': new_id})
        links = conn.execute('SELECT * FROM wiki_projection.knowledge_links WHERE request_id=%s ORDER BY link_id',
                             (self.import_id,)).fetchall()
        self.assertGreater(len(links), 0)
        for index, original in enumerate(links):
            if mutation == 'missing_link' and index == 0:
                continue
            link = deepcopy(dict(original))
            link['link_id'] = conn.execute('SELECT uuidv7() AS id').fetchone()['id']
            link['request_id'] = new_id
            if index == 0:
                if mutation in ('fake_node', 'forged_graph_node'):
                    link['payload']['node_snapshot']['statement'] += ' Fabricated statement not in canonical K.'
                elif mutation == 'removed_annotation':
                    link['payload'].update(review_annotations=[], review_required=False)
                    link['review_required'] = False
                elif mutation == 'duplicated_annotation':
                    link['payload']['review_annotations'] *= 2
                elif mutation == 'empty_matches':
                    link['payload']['matches'] = []
                link['link_sha256'] = digest({k: v for k, v in link['payload'].items() if k != 'link_sha256'})
                link['payload']['link_sha256'] = link['link_sha256']
            _insert(conn, 'knowledge_links', link)
            matches = conn.execute('SELECT * FROM wiki_projection.knowledge_matches WHERE link_id=%s ORDER BY ordinal',
                                   (original['link_id'],)).fetchall()
            self.assertGreater(len(matches), 0)
            for ordinal, match in enumerate(matches):
                if index == 0 and (mutation == 'empty_matches' or (mutation == 'missing_match' and ordinal == 0)):
                    continue
                _insert(conn, 'knowledge_matches', {**match, 'link_id': link['link_id']})
        conn.execute('SET CONSTRAINTS ALL IMMEDIATE')

    def test_direct_sql_frozen_node_annotations_and_declared_coverage_are_enforced(self):
        _, node = self._use_real_k_source()
        self.guard_revision = str(node['revision_id'])
        annotation = {'node_revision_id': str(node['revision_id']), 'reason': 'Synthetic SQL review requirement.'}
        self.import_current(review_annotations=[annotation])
        # A complete fresh SQL copy is valid; none of these probes is committed.
        with self.connection() as conn:
            try:
                self._copy_import_transaction(conn, 'valid')
            finally:
                conn.rollback()
        for mutation in ('fake_node', 'forged_graph_node', 'removed_annotation', 'duplicated_annotation', 'empty_matches',
                         'missing_match', 'missing_file', 'missing_link'):
            with self.subTest(mutation=mutation), self.connection() as conn:
                try:
                    with self.assertRaises(psycopg.Error) as caught:
                        self._copy_import_transaction(conn, mutation)
                    self.assertNotEqual(caught.exception.sqlstate, '23505')
                finally:
                    conn.rollback()
        with self.connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM wiki_projection.imports WHERE wiki_id=%s',
                                         (self.wiki_id,)).fetchone()['n'], 1)


if __name__ == '__main__':
    unittest.main()
