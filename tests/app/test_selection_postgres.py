"""Explicitly isolated PostgreSQL selection/scope fixtures, without model calls."""
import os
import unittest
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb

import test_knowledge_postgres as base_fixture
from palimpsest.artifact_store import ArtifactStore
from palimpsest.canonical_store import PostgresRepository
from palimpsest.compiler_runtime import CompilerRuntime
from palimpsest.service import DataService


@unittest.skipUnless(os.environ.get('PALIMPSEST_TEST_DSN'), 'Requires explicitly provisioned PALIMPSEST_TEST_DSN')
class SelectionPostgresTests(unittest.TestCase):
    def setUp(self):
        self.dsn = os.environ['PALIMPSEST_TEST_DSN']
        self.fixture = self.new_fixture()
        with self.fixture.connection() as conn:
            if not conn.execute("SELECT 1 FROM compiler_runtime.schema_migrations WHERE version='0006_i2k_selection'").fetchone():
                raise RuntimeError('Provision the reviewed selection migration in an isolated DB first')
            profile = {'schema_version': 'source-complete-i2k-v1', 'synthetic': str(uuid4())}
            self.profile_id = conn.execute('INSERT INTO compiler_runtime.profiles(profile_hash,payload) VALUES (%s,%s) RETURNING profile_id',
                                           (base_fixture.fingerprint(profile), Jsonb(profile))).fetchone()['profile_id']

    def new_fixture(self):
        fixture = base_fixture.KnowledgePostgresTests('runTest')
        fixture.dsn = self.dsn
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def execution(self, conn, *, fixture=None):
        fixture = fixture or self.fixture
        execution_id = fixture.allocate(conn)
        version = conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton FOR UPDATE').fetchone()['version']
        source = conn.execute('SELECT r.execution_id FROM canonical_store.information i '
                              'JOIN compiler_runtime.records r ON r.record_id=i.origin_record_id WHERE i.information_id=%s',
                              (fixture.information_id,)).fetchone()['execution_id']
        generation = conn.execute("SELECT COALESCE(max(generation),0)+1 AS n FROM compiler_runtime.operation_executions "
                                  "WHERE operation='i2k' AND data_id=%s AND profile_id=%s",
                                  (fixture.data_id, self.profile_id)).fetchone()['n']
        conn.execute("INSERT INTO compiler_runtime.operation_executions(execution_id,operation,data_id,profile_id,generation) "
                     "VALUES (%s,'i2k',%s,%s,%s)", (execution_id, fixture.data_id, self.profile_id, generation))
        fp = base_fixture.fingerprint(str(execution_id))
        conn.execute('INSERT INTO compiler_runtime.k_execution_contexts(execution_id,request_id,request_fingerprint,work_fingerprint,'
                     'input_digest,input_snapshot,expected_state_version,generator_profile_id,validator_profile_id) '
                     'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                     (execution_id, fixture.allocate(conn), fp, fp, fp,
                      Jsonb({'input': {'source_execution_id': str(source)}}), version, self.profile_id, self.profile_id))
        conn.execute('INSERT INTO compiler_runtime.k_input_information VALUES (%s,0,%s)', (execution_id, fixture.information_id))
        return execution_id

    def review(self, conn, execution, disposition='selected', *, fixture=None):
        fixture = fixture or self.fixture
        conn.execute('INSERT INTO compiler_runtime.k_information_reviews(execution_id,information_id,disposition,reason) '
                     'VALUES (%s,%s,%s,%s)', (execution, fixture.information_id, disposition, 'Synthetic selection reason.'))

    def proposed(self, conn, execution):
        conn.execute("UPDATE compiler_runtime.operation_executions SET state='proposed' WHERE execution_id=%s", (execution,))

    def decision(self, conn, execution, verdict='confirmed', *, fixture=None):
        fixture = fixture or self.fixture
        conn.execute('INSERT INTO compiler_runtime.k_information_review_decisions '
                     '(execution_id,information_id,verdict,reason_codes,reason) VALUES (%s,%s,%s,%s,%s)',
                     (execution, fixture.information_id, verdict, Jsonb(['synthetic_fixture']), 'Synthetic independent review.'))

    def complete(self, conn, execution, state='completed'):
        conn.execute('UPDATE compiler_runtime.operation_executions SET state=%s WHERE execution_id=%s', (state, execution))

    def node(self, conn, execution, *, kind='observation', identity_scope='source', bind=True):
        fixture = self.fixture
        finalize = fixture.finalize
        fixture.finalize = lambda *args, **kwargs: None
        try:
            node = fixture.node(conn, execution, kind=kind)
        finally:
            fixture.finalize = finalize
        conn.execute('DELETE FROM compiler_runtime.k_temporary_candidates WHERE record_id=%s', (node['record_id'],))
        conn.execute('INSERT INTO compiler_runtime.k_temporary_candidates VALUES (%s,%s)',
                     (node['record_id'], Jsonb({'evidence': [{'information_id': str(fixture.information_id)}]})))
        conn.execute('INSERT INTO compiler_runtime.k_information_review_records VALUES (%s,%s,%s)',
                     (execution, fixture.information_id, node['record_id']))
        if bind:
            conn.execute('INSERT INTO canonical_store.knowledge_node_scopes(knode_id,identity_scope,source_data_id,origin_record_id) '
                         'VALUES (%s,%s,%s,%s)', (node['node_id'], identity_scope,
                                                fixture.data_id if identity_scope == 'source' else None, node['record_id']))
        finalize(conn, node['record_id'], node['node_id'], node['revision_id'], 'i2k')
        return node

    def test_complete_selection_scope_and_reviews_commit_atomically(self):
        with self.fixture.connection() as conn:
            execution = self.execution(conn)
            self.review(conn, execution)
            node = self.node(conn, execution)
            self.proposed(conn, execution)
            self.decision(conn, execution)
            self.complete(conn, execution)
        with self.fixture.connection() as conn:
            scope = conn.execute('SELECT * FROM canonical_store.knowledge_node_scopes WHERE knode_id=%s', (node['node_id'],)).fetchone()
            self.assertEqual(('source', self.fixture.data_id), (scope['identity_scope'], scope['source_data_id']))
            self.assertEqual(1, conn.execute('SELECT count(*) AS n FROM compiler_runtime.k_information_review_records WHERE execution_id=%s',
                                            (execution,)).fetchone()['n'])
        for table in ('canonical_store.knowledge_node_scopes', 'compiler_runtime.k_information_reviews',
                      'compiler_runtime.k_information_review_decisions'):
            with self.subTest(table=table), self.assertRaises(psycopg.Error), self.fixture.connection() as conn:
                conn.execute('DELETE FROM ' + table)

    def test_new_selection_node_needs_scope_and_observation_cannot_be_general(self):
        for options in ({'bind': False}, {'identity_scope': 'general'}):
            with self.subTest(options=options), self.assertRaises(psycopg.Error), self.fixture.connection() as conn:
                execution = self.execution(conn)
                self.review(conn, execution)
                self.node(conn, execution, **options)

    def test_all_i_review_and_validator_coverage_required_for_success(self):
        for missing in ('generator', 'validator', 'unresolved_generator', 'unresolved_validator', 'selected_without_record'):
            with self.subTest(missing=missing), self.assertRaises(psycopg.Error), self.fixture.connection() as conn:
                execution = self.execution(conn)
                if missing != 'generator':
                    self.review(conn, execution, 'needs_review' if missing == 'unresolved_generator' else
                                ('selected' if missing == 'selected_without_record' else 'not_selected'))
                self.proposed(conn, execution)
                if missing not in ('generator', 'validator'):
                    self.decision(conn, execution, 'needs_review' if missing == 'unresolved_validator' else 'confirmed')
                self.complete(conn, execution, 'zero_output')

    def test_explicit_not_selected_can_complete_without_inventing_k(self):
        with self.fixture.connection() as conn:
            execution = self.execution(conn)
            self.review(conn, execution, 'not_selected')
            self.proposed(conn, execution)
            self.decision(conn, execution)
            self.complete(conn, execution, 'zero_output')
        with self.fixture.connection() as conn:
            self.assertEqual(0, conn.execute('SELECT count(*) AS n FROM compiler_runtime.k_compilation_records WHERE execution_id=%s',
                                            (execution,)).fetchone()['n'])
        with self.assertRaises(psycopg.Error), self.fixture.connection() as conn:
            self.review(conn, execution, 'selected')

    def test_source_complete_profile_rejects_a_partial_source_input(self):
        from hashlib import sha256
        source = self.fixture.root / 'two-sections.md'
        source.write_text(f'# First {uuid4()}\n\nFirst result.\n\n# Second\n\nIndependent second result.\n', encoding='utf-8')
        store = ArtifactStore(self.fixture.root / 'second-artifacts')
        DataService(PostgresRepository(self.dsn), store, actor_ref='local').import_file(source, media_type='text/markdown')
        self.fixture.data_id = sha256(source.read_bytes()).hexdigest()
        source_result = CompilerRuntime(self.dsn, store.root).compile_markdown(self.fixture.data_id)
        self.assertEqual(len(source_result['information_ids']), 2)
        # Deliberately deliver and review only the first of the source's two I.
        self.fixture.information_id = source_result['information_ids'][0]
        with self.assertRaisesRegex(psycopg.Error, 'omit or substitute'), self.fixture.connection() as conn:
            execution = self.execution(conn)
            self.review(conn, execution, 'not_selected')
            self.proposed(conn, execution)
            self.decision(conn, execution)
            self.complete(conn, execution, 'zero_output')

    def test_source_scope_rejects_other_data_grounding_and_invalid_review_links(self):
        with self.fixture.connection() as conn:
            execution = self.execution(conn)
            self.review(conn, execution)
            node = self.node(conn, execution)
            self.proposed(conn, execution)
            self.decision(conn, execution)
            self.complete(conn, execution)
        other = self.new_fixture()
        with self.assertRaises(psycopg.Error), self.fixture.connection() as conn:
            other_execution = self.execution(conn, fixture=other)
            record = other.record(conn, other_execution, 0, 'i2k', node['identity'], base_fixture.fingerprint('same meaning'))
            conn.execute('INSERT INTO canonical_store.knowledge_node_groundings(node_revision_id,information_id,char_start,char_end,'
                         'quote,source_role,origin_record_id) VALUES (%s,%s,0,%s,%s,%s,%s)',
                         (node['revision_id'], other.information_id, len(other.content), other.content, 'results', record))
        with self.assertRaises(psycopg.Error), self.fixture.connection() as conn:
            other_execution = self.execution(conn, fixture=other)
            self.review(conn, other_execution, fixture=other)
            conn.execute('INSERT INTO compiler_runtime.k_information_review_records VALUES (%s,%s,%s)',
                         (other_execution, other.information_id, node['record_id']))
        with self.assertRaises(psycopg.Error), self.fixture.connection() as conn:
            fresh = self.execution(conn)
            self.review(conn, fresh, 'context_only')
            self.node(conn, fresh)

    def test_legacy_general_scope_binding_preserves_ids_revision_and_fingerprints(self):
        with self.fixture.connection() as conn:
            legacy = self.fixture.node(conn, self.fixture.execution(conn, 'i2k'), kind='proposition')
        with self.fixture.connection() as conn:
            before = conn.execute('SELECT * FROM canonical_store.knowledge_node_revisions WHERE knode_revision_id=%s',
                                  (legacy['revision_id'],)).fetchone()
            execution = self.execution(conn)
            self.review(conn, execution)
            record = self.fixture.record(conn, execution, 0, 'i2k', legacy['identity'], before['content_fingerprint'])
            conn.execute('DELETE FROM compiler_runtime.k_temporary_candidates WHERE record_id=%s', (record,))
            conn.execute('INSERT INTO compiler_runtime.k_temporary_candidates VALUES (%s,%s)',
                         (record, Jsonb({'evidence': [{'information_id': str(self.fixture.information_id)}]})))
            conn.execute('INSERT INTO compiler_runtime.k_information_review_records VALUES (%s,%s,%s)',
                         (execution, self.fixture.information_id, record))
            conn.execute("INSERT INTO canonical_store.knowledge_node_scopes(knode_id,identity_scope,origin_record_id) VALUES (%s,'general',%s)",
                         (legacy['node_id'], record))
            conn.execute("UPDATE compiler_runtime.k_compilation_records SET disposition='reused',result_node_id=%s,"
                         'result_node_revision_id=%s,resolved_at=CURRENT_TIMESTAMP WHERE record_id=%s',
                         (legacy['node_id'], legacy['revision_id'], record))
            conn.execute('DELETE FROM compiler_runtime.k_temporary_candidates WHERE record_id=%s', (record,))
            self.proposed(conn, execution)
            self.decision(conn, execution)
            self.complete(conn, execution)
        with self.fixture.connection() as conn:
            after = conn.execute('SELECT * FROM canonical_store.knowledge_node_revisions WHERE knode_revision_id=%s',
                                 (legacy['revision_id'],)).fetchone()
            self.assertEqual(before, after)
            self.assertEqual(1, conn.execute('SELECT count(*) AS n FROM canonical_store.knowledge_node_revisions WHERE knode_id=%s',
                                            (legacy['node_id'],)).fetchone()['n'])
        other = self.new_fixture()
        with self.fixture.connection() as conn:
            execution = self.execution(conn, fixture=other)
            self.review(conn, execution, fixture=other)
            record = other.record(conn, execution, 0, 'i2k', legacy['identity'], before['content_fingerprint'])
            conn.execute('DELETE FROM compiler_runtime.k_temporary_candidates WHERE record_id=%s', (record,))
            conn.execute('INSERT INTO compiler_runtime.k_temporary_candidates VALUES (%s,%s)',
                         (record, Jsonb({'evidence': [{'information_id': str(other.information_id)}]})))
            conn.execute('INSERT INTO compiler_runtime.k_information_review_records VALUES (%s,%s,%s)',
                         (execution, other.information_id, record))
            conn.execute('INSERT INTO canonical_store.knowledge_node_groundings(node_revision_id,information_id,char_start,char_end,'
                         'quote,source_role,origin_record_id) VALUES (%s,%s,0,%s,%s,%s,%s)',
                         (legacy['revision_id'], other.information_id, len(other.content), other.content, 'results', record))
            conn.execute("UPDATE compiler_runtime.k_compilation_records SET disposition='reused',result_node_id=%s,"
                         'result_node_revision_id=%s,resolved_at=CURRENT_TIMESTAMP WHERE record_id=%s',
                         (legacy['node_id'], legacy['revision_id'], record))
            conn.execute('DELETE FROM compiler_runtime.k_temporary_candidates WHERE record_id=%s', (record,))
            self.proposed(conn, execution)
            self.decision(conn, execution, fixture=other)
            self.complete(conn, execution)
        with self.fixture.connection() as conn:
            self.assertEqual(before, conn.execute('SELECT * FROM canonical_store.knowledge_node_revisions WHERE knode_revision_id=%s',
                                                  (legacy['revision_id'],)).fetchone())
            data = conn.execute('SELECT DISTINCT i.data_id FROM canonical_store.knowledge_node_groundings g '
                                'JOIN canonical_store.information i USING(information_id) WHERE g.node_revision_id=%s',
                                (legacy['revision_id'],)).fetchall()
            self.assertEqual({self.fixture.data_id, other.data_id}, {row['data_id'] for row in data})


if __name__ == '__main__':
    unittest.main()
