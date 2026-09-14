"""Real fixture PostgreSQL retrieval contracts, with synthetic 3D embeddings.

This verifies storage, coverage, cosine plumbing and stale inputs, not BGE-M3
quality. Only the explicit fixture DB named palimpsest may be used. No test
migrates, calls a model, or commits negative SQL mutations.
"""
from copy import deepcopy
from hashlib import sha256
import os
import sys
import unittest

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.wiki_retrieval import WikiRetrieval
import test_wiki_database as fixtures


PROFILE = {'model_id': 'synthetic/storage-contract-only',
           'revision': digest({'fixture': 'wiki-retrieval-v1'}), 'dimensions': 3}


def encoded(documents, profile=None):
    profile = deepcopy(PROFILE if profile is None else profile)
    request = {'schema_version': 'wiki-embedding-request-v1', 'documents': documents}
    return {'schema_version': 'wiki-embedding-result-v1', 'input_sha256': digest(request),
            'profile': profile, 'documents': [
                {'document_id': doc['document_id'], 'text_sha256': sha256(doc['text'].encode()).hexdigest(),
                 'chunks': [{'char_start': 0, 'char_end': len(doc['text']),
                             'text_sha256': sha256(doc['text'].encode()).hexdigest(),
                             'dense': [1.0] + [0.0] * (profile['dimensions'] - 1)}]}
                for doc in documents]}


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires Linux and explicit default fixture PostgreSQL DSN')
class WikiRetrievalDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['PALIMPSEST_TEST_DSN']
        with psycopg.connect(cls.dsn) as conn:
            if conn.execute('SELECT current_database()').fetchone()[0] != 'palimpsest':
                raise RuntimeError('Retrieval fixtures must run only against the database named palimpsest')
            if not conn.execute("SELECT 1 FROM compiler_runtime.schema_migrations WHERE version='0010_wiki_retrieval'").fetchone():
                raise RuntimeError('Provision 0010 only in the default fixture DB before these tests')

    def fixture(self, *, knowledge=False):
        fixture = fixtures.WikiDatabaseTests(methodName='runTest')
        fixture.dsn = self.dsn
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        knowledge_fixture = fixture._use_real_k_source() if knowledge else None
        fixture.import_current()
        return fixture, knowledge_fixture

    def setUp(self):
        self.fixture_wiki, _ = self.fixture()
        self.retrieval = WikiRetrieval(self.dsn, self.fixture_wiki.base / 'artifacts')
        self.corpus = self.retrieval.corpus(self.fixture_wiki.wiki_id)
        self.index_id = self.fixture_wiki.repository.allocate_id()
        self.result = encoded(self.retrieval.embedding_request(self.corpus)['documents'])

    def connection(self):
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def assert_error(self, code, operation):
        with self.assertRaises(PalimpsestError) as caught:
            operation()
        self.assertEqual(caught.exception.code, code)

    def install(self):
        return self.retrieval.install(self.index_id, self.corpus, self.result)

    def test_all_source_i_and_unicode_survive_install_and_exact_replay(self):
        source = self.fixture_wiki
        with self.connection() as conn:
            canonical = conn.execute('SELECT i.information_id,i.content FROM canonical_store.information i '
                'JOIN compiler_runtime.records r ON r.record_id=i.origin_record_id WHERE r.execution_id=%s',
                (source.execution,)).fetchall()
        self.assertGreater(len(canonical), 1)
        documents = {doc['document_id']: doc for doc in self.corpus['documents']}
        self.assertEqual({unit['information_id'] for unit in self.corpus['information']},
                         {str(row['information_id']) for row in canonical})
        for row in canonical:
            self.assertEqual(documents['i/' + str(row['information_id'])]['text'], row['content'])
        self.assertTrue(any('μ' in row['content'] for row in canonical))
        before = fixtures.wiki_fixtures.PaperWikiPostgresTests.canonical_state(source)
        created = self.install()
        self.assertFalse(created['replayed'])
        self.assertEqual(created['documents'], len(documents))
        self.assertTrue(self.install()['replayed'])
        self.assertEqual(fixtures.wiki_fixtures.PaperWikiPostgresTests.canonical_state(source), before)
        stored = self.retrieval.index(self.index_id)
        self.assertEqual(stored['corpus'], self.corpus)
        self.assertEqual(stored['profile'], PROFILE)
        with self.connection() as conn:
            counts = conn.execute('SELECT count(*) AS chunks,min(vector_dims(embedding)) AS dimensions '
                                  'FROM wiki_retrieval.chunks WHERE index_id=%s', (self.index_id,)).fetchone()
        self.assertEqual(counts, {'chunks': len(documents), 'dimensions': 3})
        changed = deepcopy(self.result)
        changed['documents'][0]['chunks'][0]['dense'] = [0.0, 1.0, 0.0]
        self.assert_error('idempotency_conflict', lambda: self.retrieval.install(self.index_id, self.corpus, changed))

    def test_install_refuses_missing_documents_bad_unicode_text_and_invalid_vectors(self):
        cases = [
            ('missing_document', 'embedding_document_mismatch'),
            ('text', 'embedding_text_mismatch'),
            ('hole', 'embedding_coverage_gap'),
            ('zero_vector', 'invalid_embedding_vector'),
            ('wrong_dimensions', 'invalid_embedding_vector'),
        ]
        for mutation, code in cases:
            result = deepcopy(self.result)
            if mutation == 'missing_document':
                result['documents'].pop()
            elif mutation == 'text':
                result['documents'][0]['chunks'][0]['text_sha256'] = '0' * 64
            elif mutation == 'hole':
                result['documents'][0]['chunks'][0]['char_start'] = 1
            elif mutation == 'zero_vector':
                result['documents'][0]['chunks'][0]['dense'] = [0.0, 0.0, 0.0]
            else:
                result['documents'][0]['chunks'][0]['dense'] = [1.0, 0.0]
            with self.subTest(mutation=mutation):
                self.assert_error(code, lambda: self.retrieval.install(self.index_id, self.corpus, result))
        with self.connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM wiki_retrieval.indexes WHERE index_id=%s',
                                          (self.index_id,)).fetchone()['n'], 0)

    def test_search_layers_scores_and_query_profile_refusal(self):
        self.install()
        query = 'synthetic μm'
        query_result = encoded([{'document_id': 'query', 'text': query}])
        for layer, prefix in (('information', 'i/'), ('knowledge', 'wiki/')):
            result = self.retrieval.search(self.index_id, query, query_result, layer=layer)
            self.assertGreater(len(result['matches']), 0)
            self.assertTrue(all(row['document_id'].startswith(prefix) for row in result['matches']))
            self.assertTrue(all(abs(row['dense_score'] - 1.0) < 1e-6 for row in result['matches']))
            self.assertFalse(result['search_complete'])
            self.assertEqual(len(result['rerank_request']['passages']), len(result['matches']))
            corpus_docs = {doc['document_id']: doc['text'] for doc in self.corpus['documents']}
            for row in result['matches']:
                self.assertEqual(row['text'], corpus_docs[row['document_id']][row['char_start']:row['char_end']])
        wrong = deepcopy(query_result)
        wrong['profile']['revision'] = digest({'other_model': True})
        self.assert_error('query_embedding_mismatch', lambda: self.retrieval.search(self.index_id, query, wrong))
        self.assert_error('query_embedding_mismatch', lambda: self.retrieval.search(self.index_id, query + ' changed', query_result))

    def test_new_wiki_import_makes_old_index_stale_but_preserves_historical_read(self):
        self.install()
        source = self.fixture_wiki
        source.database.import_archive(source.wiki_id, source.repository.allocate_id(), source.archive,
                                       expected_head=source.import_id)
        self.assert_error('retrieval_index_stale', lambda: self.retrieval.index(self.index_id))
        historical = self.retrieval.index(self.index_id, current=False)
        self.assertEqual(historical['import_id'], source.import_id)
        self.assertEqual(historical['corpus'], self.corpus)
        self.assert_error('retrieval_corpus_changed', self.install)

    def test_real_k_revision_enters_corpus_and_its_successor_marks_index_stale(self):
        source, (knowledge_fixture, first) = self.fixture(knowledge=True)
        retrieval = WikiRetrieval(self.dsn, source.base / 'artifacts')
        corpus = retrieval.corpus(source.wiki_id)
        self.assertEqual({node['knode_revision_id'] for node in corpus['knowledge']}, {str(first['revision_id'])})
        self.assertTrue(all(grounding['node_revision_id'] == str(first['revision_id'])
                            for node in corpus['knowledge'] for grounding in node['groundings']))
        index_id = source.repository.allocate_id()
        result = encoded(retrieval.embedding_request(corpus)['documents'])
        retrieval.install(index_id, corpus, result)
        with knowledge_fixture.connection() as conn:
            knowledge_fixture.revise(conn,first,value=4)
        self.assert_error('retrieval_index_stale', lambda: retrieval.index(index_id))
        self.assert_error('wiki_import_refresh_required', lambda: retrieval.corpus(source.wiki_id))
        self.assertEqual(retrieval.index(index_id, current=False)['corpus'], corpus)

    def _sql_fixture(self, mutation=None):
        """Raw SQL fixture tests only SQL shape/ranges; the runtime owns source verification."""
        corpus = {**self.corpus, 'documents': [
            {'document_id': 'synthetic-a', 'kind': 'information', 'text': '가🙂μZ'},
            {'document_id': 'synthetic-b', 'kind': 'wiki', 'text': 'Second document'}]}
        documents = corpus['documents']
        index_id = self.fixture_wiki.repository.allocate_id()
        chunks = [(doc['document_id'], 0, len(doc['text'])) for doc in documents]
        if mutation == 'duplicate_document':
            documents[1]['document_id'] = documents[0]['document_id']
        elif mutation == 'empty_document':
            documents[0]['text'] = ''
        elif mutation == 'coverage_hole':
            chunks = [('synthetic-a', 0, 1), ('synthetic-a', 2, 4), chunks[1]]
        elif mutation == 'missing_document':
            chunks.pop()
        elif mutation == 'unicode_range':
            chunks[0] = ('synthetic-a', 0, len(documents[0]['text'].encode()))
        elif mutation == 'overlap':
            chunks = [('synthetic-a', 0, 3), ('synthetic-a', 1, 4), chunks[1]]
        index = {'index_id': index_id, 'wiki_id': self.corpus['wiki_id'], 'import_id': self.corpus['import_id'],
                 'corpus_sha256': digest(corpus), 'corpus': corpus, 'profile_sha256': digest(PROFILE),
                 'profile': PROFILE, 'embedding_result_sha256': digest({'synthetic': index_id}),
                 'document_count': len(documents), 'chunk_count': len(chunks) + (mutation == 'declared_count')}
        if mutation == 'owner':
            index['wiki_id'] = self.fixture_wiki.repository.allocate_id()
        output = []
        for ordinal, (identifier, start, end) in enumerate(chunks):
            text = next((doc['text'] for doc in documents if doc['document_id'] == identifier), 'unused')
            output.append({'index_id': index_id, 'chunk_id': digest({'index': index_id, 'ordinal': ordinal}),
                'document_id': identifier, 'char_start': start, 'char_end': end,
                'text_sha256': '0' * 64 if mutation == 'substring_hash' else sha256(text[start:end].encode()).hexdigest(),
                'embedding': '[1,0]' if mutation == 'vector_dimensions' else '[1,0,0]'})
        return index, output

    @staticmethod
    def _insert(conn, table, row):
        conn.execute(sql.SQL('INSERT INTO wiki_retrieval.{} ({}) VALUES ({})').format(
            sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, row)),
            sql.SQL(',').join(sql.Placeholder() for _ in row)),
            [Jsonb(value) if isinstance(value, (dict, list)) else value for value in row.values()])

    def test_direct_sql_overlap_control_and_nine_negative_guards(self):
        index, chunks = self._sql_fixture('overlap')
        with self.connection() as conn:
            try:
                self._insert(conn, 'indexes', index)
                for row in chunks:
                    self._insert(conn, 'chunks', row)
                conn.execute('SET CONSTRAINTS ALL IMMEDIATE')
            finally:
                conn.rollback()
        for mutation in ('owner', 'duplicate_document', 'empty_document', 'substring_hash', 'unicode_range',
                         'vector_dimensions', 'coverage_hole', 'declared_count', 'missing_document'):
            index, chunks = self._sql_fixture(mutation)
            with self.subTest(mutation=mutation), self.connection() as conn:
                try:
                    with self.assertRaises(psycopg.Error) as caught:
                        self._insert(conn, 'indexes', index)
                        for row in chunks:
                            self._insert(conn, 'chunks', row)
                        conn.execute('SET CONSTRAINTS ALL IMMEDIATE')
                    self.assertNotEqual(caught.exception.sqlstate, '23505')
                finally:
                    conn.rollback()

    def test_stored_index_and_chunks_are_immutable_and_late_chunks_fail(self):
        self.install()
        with self.connection() as conn:
            row = dict(conn.execute('SELECT * FROM wiki_retrieval.chunks WHERE index_id=%s LIMIT 1',
                                    (self.index_id,)).fetchone())
        row['chunk_id'] = digest({'late': self.index_id})
        with self.connection() as conn:
            try:
                with self.assertRaises(psycopg.Error):
                    self._insert(conn, 'chunks', row)
                    conn.execute('SET CONSTRAINTS ALL IMMEDIATE')
            finally:
                conn.rollback()
        for table in ('indexes', 'chunks'):
            for operation in ('UPDATE', 'DELETE', 'TRUNCATE'):
                with self.subTest(table=table, operation=operation), self.connection() as conn:
                    try:
                        with self.assertRaises(psycopg.Error):
                            if operation == 'UPDATE':
                                statement = sql.SQL('UPDATE wiki_retrieval.{} SET index_id=index_id WHERE index_id=%s')
                            elif operation == 'DELETE':
                                statement = sql.SQL('DELETE FROM wiki_retrieval.{} WHERE index_id=%s')
                            else:
                                statement = sql.SQL('TRUNCATE wiki_retrieval.{}')
                            conn.execute(statement.format(sql.Identifier(table)),
                                         () if operation == 'TRUNCATE' else (self.index_id,))
                    finally:
                        conn.rollback()


if __name__ == '__main__':
    unittest.main()
