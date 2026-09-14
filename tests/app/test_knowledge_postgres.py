"""Real PostgreSQL K constraints, using synthetic claims and a disposable DB.

The caller explicitly provisions PALIMPSEST_TEST_DSN. These tests never migrate,
truncate, delete history, contact a provider, or modify any real paper claim.
"""

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from threading import Barrier
import unittest
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from palimpsest.artifact_store import ArtifactStore
from palimpsest.canonical_store import PostgresRepository
from palimpsest.compiler_runtime import CompilerRuntime
from palimpsest.i2k import digest
from palimpsest.knowledge_revision_runtime import enumerate_impacts
from palimpsest.service import DataService


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@unittest.skipUnless(os.environ.get('PALIMPSEST_TEST_DSN'), 'Requires explicitly provisioned PALIMPSEST_TEST_DSN')
class KnowledgePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['PALIMPSEST_TEST_DSN']
        with psycopg.connect(cls.dsn) as conn:
            if not conn.execute("SELECT 1 FROM compiler_runtime.schema_migrations WHERE version='0005_knowledge'").fetchone():
                raise RuntimeError('Provision the reviewed K migration in an isolated DB first')

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='palimpsest-k-sql-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        source = self.root / 'fixture.md'
        source.write_text(f'# Synthetic study {uuid4()}\n\nMeasured 3 μm; this is a storage fixture.\n', encoding='utf-8')
        self.data_id = sha256(source.read_bytes()).hexdigest()
        store = ArtifactStore(self.root / 'artifacts')
        DataService(PostgresRepository(self.dsn), store, actor_ref='local').import_file(source, media_type='text/markdown')
        result = CompilerRuntime(self.dsn, store.root).compile_markdown(self.data_id)
        self.information_id = result['information_ids'][0]
        with self.connection() as conn:
            self.content = conn.execute('SELECT content FROM canonical_store.information WHERE information_id=%s',
                                        (self.information_id,)).fetchone()['content']
            profile = {'kind': 'synthetic-sql-fixture', 'fixture_id': str(uuid4())}
            self.profile_id = conn.execute('INSERT INTO compiler_runtime.profiles(profile_hash,payload) VALUES (%s,%s) RETURNING profile_id',
                                           (fingerprint(profile), Jsonb(profile))).fetchone()['profile_id']

    def connection(self):
        return psycopg.connect(self.dsn, row_factory=dict_row)

    @staticmethod
    def allocate(conn):
        return conn.execute('SELECT uuidv7() AS id').fetchone()['id']

    def execution(self, conn, operation, inputs=(), *, profile_id=None, snapshot=None):
        profile_id = self.profile_id if profile_id is None else profile_id
        version = conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton FOR UPDATE').fetchone()['version']
        execution_id = self.allocate(conn)
        generation = conn.execute('SELECT COALESCE(max(generation),0)+1 AS generation FROM compiler_runtime.operation_executions '
                                  'WHERE operation=%s AND data_id=%s AND profile_id=%s',
                                  (operation, self.data_id, profile_id)).fetchone()['generation']
        conn.execute('INSERT INTO compiler_runtime.operation_executions(execution_id,operation,data_id,profile_id,generation) '
                     'VALUES (%s,%s,%s,%s,%s)', (execution_id, operation, self.data_id, profile_id, generation))
        unique = fingerprint(str(execution_id))
        conn.execute('INSERT INTO compiler_runtime.k_execution_contexts(execution_id,request_id,request_fingerprint,'
                     'work_fingerprint,input_digest,input_snapshot,expected_state_version,generator_profile_id,validator_profile_id) '
                     'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                     (execution_id, self.allocate(conn), unique, unique, unique,
                      Jsonb({'synthetic': True} if snapshot is None else snapshot), version, profile_id, profile_id))
        if operation == 'i2k':
            conn.execute('INSERT INTO compiler_runtime.k_input_information VALUES (%s,0,%s)', (execution_id, self.information_id))
        else:
            for ordinal, node in enumerate(inputs):
                conn.execute('INSERT INTO compiler_runtime.k_input_node_revisions VALUES (%s,%s,%s)',
                             (execution_id, ordinal, node['revision_id']))
        return execution_id

    def record(self, conn, execution_id, ordinal, operation, identity, content, *, body=None):
        record_id = self.allocate(conn)
        conn.execute('INSERT INTO compiler_runtime.k_compilation_records(record_id,execution_id,record_type,ordinal,'
                     'identity_fingerprint,content_fingerprint,context_fingerprint) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                     (record_id, execution_id, operation, ordinal, identity, content, fingerprint('checks')))
        conn.execute('INSERT INTO compiler_runtime.k_temporary_candidates VALUES (%s,%s)',
                     (record_id, Jsonb({'synthetic': True} if body is None else body)))
        return record_id

    def finalize(self, conn, record_id, object_id, revision_id, operation, *, successor=False, outbox=True):
        prefix = 'node' if operation == 'i2k' else 'edge'
        conn.execute(f'UPDATE compiler_runtime.k_compilation_records SET disposition=%s,result_{prefix}_id=%s,'
                     f'result_{prefix}_revision_id=%s,resolved_at=CURRENT_TIMESTAMP WHERE record_id=%s',
                     ('accepted_revision' if successor else 'accepted_new', object_id, revision_id, record_id))
        conn.execute('DELETE FROM compiler_runtime.k_temporary_candidates WHERE record_id=%s', (record_id,))
        if outbox:
            conn.execute('INSERT INTO compiler_runtime.k_outbox(record_id,operation) VALUES (%s,%s)',
                         (record_id, 'n2e' if operation == 'i2k' else 'k2k'))

    def node(self, conn, execution_id, ordinal=0, *, existing=None, value=3, kind='observation', outbox=True,
             quote=None, media=None, classified=False):
        node_id = existing['node_id'] if existing else self.allocate(conn)
        revision_id = self.allocate(conn)
        identity = existing['identity'] if existing else fingerprint(str(node_id))
        payload = {'subject': 'synthetic specimen', 'measurement': value, 'unit': 'μm'}
        content = fingerprint(payload)
        record_id = self.record(conn, execution_id, ordinal, 'i2k', identity, content)
        if not existing:
            conn.execute('INSERT INTO canonical_store.knowledge_nodes(knode_id,kind,identity_fingerprint,current_revision_id) '
                         'VALUES (%s,%s,%s,%s)', (node_id, kind, identity, revision_id))
        conn.execute('INSERT INTO canonical_store.knowledge_node_revisions(knode_revision_id,knode_id,semantic_payload,'
                     'statement,identity_fingerprint,content_fingerprint,origin_record_id,supersedes_revision_id) '
                     'VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                     (revision_id, node_id, Jsonb(payload), f'Synthetic value {value} μm', identity, content,
                      record_id, existing['revision_id'] if existing else None))
        if existing:
            conn.execute('UPDATE canonical_store.knowledge_nodes SET current_revision_id=%s WHERE knode_id=%s',
                         (revision_id, node_id))
        selected_quote = self.content if quote is None else quote
        conn.execute('INSERT INTO canonical_store.knowledge_node_groundings(node_revision_id,information_id,char_start,'
                     'char_end,quote,media_sha256,source_role,origin_record_id) VALUES (%s,%s,0,%s,%s,%s,%s,%s)',
                     (revision_id, self.information_id, len(selected_quote), selected_quote, media,
                      'results' if kind == 'observation' else 'abstract', record_id))
        if classified:
            conn.execute('INSERT INTO canonical_store.knowledge_node_scopes '
                         '(knode_id,identity_scope,source_data_id,origin_record_id) VALUES (%s,%s,%s,%s)',
                         (node_id, 'source', self.data_id, record_id))
        self.finalize(conn, record_id, node_id, revision_id, 'i2k', successor=existing is not None, outbox=outbox)
        return {'node_id': node_id, 'revision_id': revision_id, 'identity': identity, 'record_id': record_id}

    def classified_profile(self, conn):
        profile = {'schema_version': 'source-complete-i2k-v1', 'synthetic': str(uuid4())}
        return conn.execute('INSERT INTO compiler_runtime.profiles(profile_hash,payload) VALUES (%s,%s) RETURNING profile_id',
                            (fingerprint(profile), Jsonb(profile))).fetchone()['profile_id']

    def classified_node(self, conn, **options):
        """Opt in only: selection guard tests still create unclassified legacy nodes."""
        return self.node(conn, self.execution(conn, 'i2k', profile_id=self.classified_profile(conn)),
                         classified=True, **options)

    def revise(self, conn, existing, *, value=4):
        """Low-level SQL successor fixture with complete explicit revision evidence.

        Preserve the original legacy semantic JSON. This tests storage guards;
        Runtime/model semantic normalization is exercised in the separate suite.
        """
        row = conn.execute('''SELECT n.knode_id,n.kind,n.current_revision_id,r.knode_revision_id,
            r.semantic_payload,r.statement,r.identity_fingerprint,r.content_fingerprint,r.origin_record_id,
            s.identity_scope,s.source_data_id FROM canonical_store.knowledge_nodes n
            JOIN canonical_store.knowledge_node_revisions r ON r.knode_revision_id=n.current_revision_id
            JOIN canonical_store.knowledge_node_scopes s ON s.knode_id=n.knode_id WHERE n.knode_id=%s''',
            (existing['node_id'],)).fetchone()
        if row is None:
            raise AssertionError('A positive revision fixture needs an explicitly classified initial target')
        target = {'schema_version': 'knowledge-revision-target-v1', 'operation': 'i2k',
            'target_knode_id': str(existing['node_id']), 'expected_revision_id': str(existing['revision_id']),
            'target': json.loads(json.dumps(row, default=str))}
        target['target_sha256'] = digest(target)
        profile = {'kind': 'synthetic-sql-revision-fixture', 'fixture_id': str(uuid4()),
                   'explicit_knowledge_revision': 'explicit-knowledge-revision-v1'}
        profile_id = conn.execute('INSERT INTO compiler_runtime.profiles(profile_hash,payload) VALUES (%s,%s) RETURNING profile_id',
                                  (fingerprint(profile), Jsonb(profile))).fetchone()['profile_id']
        execution = self.execution(conn, 'i2k', profile_id=profile_id, snapshot={'revision_target': target})
        conn.execute('INSERT INTO compiler_runtime.k_revision_targets '
            '(execution_id,target_knode_id,expected_revision_id,target_sha256,snapshot) VALUES (%s,%s,%s,%s,%s)',
            (execution, existing['node_id'], existing['revision_id'], target['target_sha256'], Jsonb(target)))
        payload = {'subject': 'synthetic specimen', 'measurement': value, 'unit': 'μm'}
        content = fingerprint(payload)
        binding = {'knode_id': str(existing['node_id']), 'expected_revision_id': str(existing['revision_id']),
                   'target_sha256': target['target_sha256']}
        candidate = {'candidate_key': 'revision', 'kind': row['kind'],
            'identity_scope': row['identity_scope'], 'source_data_id': row['source_data_id'],
            'semantic_payload': payload, 'statement': f'Synthetic value {value} μm',
            'identity_fingerprint': existing['identity'], 'content_fingerprint': content,
            'revision_target': binding, 'claim_basis': 'explicit_source_content', 'is_inferred': False,
            'evidence': [{'information_id': str(self.information_id), 'char_start': 0, 'char_end': len(self.content),
                'quote': self.content, 'media_sha256': None,
                'source_role': 'results' if row['kind'] == 'observation' else 'abstract'}]}
        record = self.record(conn, execution, 0, 'i2k', existing['identity'], content, body=candidate)
        conn.execute("UPDATE compiler_runtime.operation_executions SET state='proposed' WHERE execution_id=%s", (execution,))
        decision = {'candidate_key': 'revision', 'verdict': 'accepted',
            'equivalent_candidate_key': None, 'equivalent_revision_id': None,
            'source_explicit': True, 'no_novel_inference': True, 'source_identity_preserved': True,
            'scope_correct': True, 'importance_justified': True,
            'reason_codes': ['synthetic_fixture'], 'reason': 'Synthetic ordinary source acceptance.'}
        validation = {'action': 'accepted_revision', 'revision_target': binding,
            'identity_fingerprint': existing['identity'], 'candidate_content_fingerprint': content,
            'result_content_fingerprint': content,
            'origin': {'mode': 'new_record', 'origin_operation': 'i2k', 'is_inferred': False},
            'review': {'comparison_base_revision_id': str(existing['revision_id']), 'same_identity': True,
                'material_change': True, 'grounding_valid': True, 'reason_codes': ['synthetic_material_review'],
                'reason': 'Synthetic independent material meaning change verdict.'},
            'reason_codes': [], 'decision': decision}
        conn.execute('INSERT INTO compiler_runtime.k_revision_decisions(record_id,target_sha256,validation) VALUES (%s,%s,%s)',
                     (record, target['target_sha256'], Jsonb(validation)))
        revision = self.allocate(conn)
        conn.execute('''INSERT INTO canonical_store.knowledge_node_revisions
            (knode_revision_id,knode_id,semantic_payload,statement,identity_fingerprint,content_fingerprint,
             origin_record_id,supersedes_revision_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
            (revision, existing['node_id'], Jsonb(payload), candidate['statement'], existing['identity'],
             content, record, existing['revision_id']))
        conn.execute('UPDATE canonical_store.knowledge_nodes SET current_revision_id=%s WHERE knode_id=%s',
                     (revision, existing['node_id']))
        evidence = candidate['evidence'][0]
        conn.execute('''INSERT INTO canonical_store.knowledge_node_groundings
            (node_revision_id,information_id,char_start,char_end,quote,media_sha256,source_role,origin_record_id)
            VALUES (%s,%s,0,%s,%s,NULL,%s,%s)''',
            (revision, self.information_id, len(self.content), self.content, evidence['source_role'], record))
        self.finalize(conn, record, existing['node_id'], revision, 'i2k', successor=True)
        conn.execute("INSERT INTO compiler_runtime.k_outbox(record_id,operation) VALUES (%s,'k2k')", (record,))
        conn.execute('INSERT INTO compiler_runtime.k_revision_impacts(record_id,source_revision_id,impacts) VALUES (%s,%s,%s)',
                     (record, existing['revision_id'], Jsonb(enumerate_impacts(conn, str(existing['revision_id'])))))
        for phase in ('generator', 'validator'):
            receipt = {'actual_delivery': True, 'delivered_revision_target_id': str(existing['revision_id']),
                       'delivered_information_ids': [str(self.information_id)], 'test_only': True}
            conn.execute('''INSERT INTO compiler_runtime.k_model_calls
                (execution_id,phase,profile_id,input_sha256,output_sha256,provider_ref,receipt,status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'succeeded')''',
                (execution, phase, profile_id, target['target_sha256'], digest(candidate if phase == 'generator' else validation),
                 'synthetic-' + phase + '-' + str(uuid4()), Jsonb(receipt)))
        conn.execute("UPDATE compiler_runtime.operation_executions SET state='completed' WHERE execution_id=%s", (execution,))
        return {'node_id': existing['node_id'], 'revision_id': revision, 'identity': existing['identity'], 'record_id': record}

    def edge(self, conn, execution_id, source, target):
        edge_id, revision_id = self.allocate(conn), self.allocate(conn)
        identity = fingerprint([str(source['node_id']), 'supports', str(target['node_id'])])
        payload = {'relation': 'supports', 'scope': 'synthetic fixture only'}
        content = fingerprint(payload)
        record_id = self.record(conn, execution_id, 0, 'n2e', identity, content)
        conn.execute('INSERT INTO canonical_store.knowledge_edges(kedge_id,predicate,from_knode_id,to_knode_id,'
                     'identity_fingerprint,current_revision_id) VALUES (%s,%s,%s,%s,%s,%s)',
                     (edge_id, 'supports', source['node_id'], target['node_id'], identity, revision_id))
        conn.execute('INSERT INTO canonical_store.knowledge_edge_revisions(kedge_revision_id,kedge_id,from_knode_revision_id,'
                     'to_knode_revision_id,semantic_payload,qualifiers,rationale,identity_fingerprint,content_fingerprint,origin_record_id) '
                     'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                     (revision_id, edge_id, source['revision_id'], target['revision_id'], Jsonb(payload), Jsonb({}),
                      'A synthetic directed support.', identity, content, record_id))
        self.finalize(conn, record_id, edge_id, revision_id, 'n2e')
        return {'edge_id': edge_id, 'revision_id': revision_id, 'record_id': record_id}

    def initial_graph(self, *, classified=False):
        with self.connection() as conn:
            execution = self.execution(conn, 'i2k', profile_id=self.classified_profile(conn) if classified else None)
            observation = self.node(conn, execution, classified=classified)
            proposition = self.node(conn, execution, 1, kind='proposition', classified=classified)
        with self.connection() as conn:
            edge = self.edge(conn, self.execution(conn, 'n2e', (observation, proposition)), observation, proposition)
        return observation, proposition, edge

    def test_initial_graph_exact_endpoint_ownership_and_typed_inputs(self):
        source, target, edge = self.initial_graph()
        with self.connection() as conn:
            row = conn.execute('SELECT * FROM canonical_store.knowledge_edge_revisions WHERE kedge_revision_id=%s',
                               (edge['revision_id'],)).fetchone()
            self.assertEqual(source['revision_id'], row['from_knode_revision_id'])
            self.assertEqual(target['revision_id'], row['to_knode_revision_id'])
            self.assertEqual(source['node_id'], row['from_knode_id'])
            self.assertIsNone(row['supersedes_revision_id'])
            self.assertEqual(2, conn.execute('SELECT count(*) AS n FROM compiler_runtime.k_input_node_revisions x '
                                            'JOIN compiler_runtime.k_compilation_records r USING(execution_id) WHERE r.record_id=%s',
                                            (edge['record_id'],)).fetchone()['n'])
        with self.assertRaises(psycopg.Error), self.connection() as conn:
            conn.execute('UPDATE canonical_store.knowledge_nodes SET current_revision_id=%s WHERE knode_id=%s',
                         (target['revision_id'], source['node_id']))
        with self.assertRaises(psycopg.Error), self.connection() as conn:
            conn.execute('UPDATE canonical_store.knowledge_edge_revisions SET from_knode_revision_id=%s WHERE kedge_revision_id=%s',
                         (target['revision_id'], edge['revision_id']))

    def test_same_payload_refused_and_material_successor_preserves_history(self):
        source, target, edge = self.initial_graph(classified=True)
        with self.assertRaises(psycopg.Error), self.connection() as conn:
            self.revise(conn, source, value=3)
        with self.connection() as conn:
            revised = self.revise(conn, source, value=4)
        with self.assertRaises(psycopg.Error), self.connection() as conn:
            self.revise(conn, source, value=5)
        with self.assertRaises(psycopg.Error), self.connection() as conn:
            # An ordinary execution cannot bypass explicit revision authorization.
            self.node(conn, self.execution(conn, 'i2k'), existing=revised, value=5)
        with self.connection() as conn:
            old = conn.execute('SELECT semantic_payload FROM canonical_store.knowledge_node_revisions WHERE knode_revision_id=%s',
                               (source['revision_id'],)).fetchone()
            self.assertEqual(3, old['semantic_payload']['measurement'])
            new = conn.execute('SELECT supersedes_revision_id FROM canonical_store.knowledge_node_revisions WHERE knode_revision_id=%s',
                               (revised['revision_id'],)).fetchone()
            self.assertEqual(source['revision_id'], new['supersedes_revision_id'])
            old_edge = conn.execute('SELECT from_knode_revision_id FROM canonical_store.knowledge_edge_revisions WHERE kedge_revision_id=%s',
                                    (edge['revision_id'],)).fetchone()
            self.assertEqual(source['revision_id'], old_edge['from_knode_revision_id'])
            self.assertEqual(1, conn.execute('SELECT count(*) AS n FROM canonical_store.knowledge_edge_revisions WHERE kedge_id=%s',
                                            (edge['edge_id'],)).fetchone()['n'])

    def test_missing_outbox_rolls_back_canonical_and_runtime_effects(self):
        with self.connection() as conn:
            before = conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton').fetchone()['version']
        created = None
        with self.assertRaises(psycopg.Error), self.connection() as conn:
            created = self.node(conn, self.execution(conn, 'i2k'), outbox=False)
        with self.connection() as conn:
            self.assertIsNone(conn.execute('SELECT 1 FROM canonical_store.knowledge_nodes WHERE knode_id=%s',
                                           (created['node_id'],)).fetchone())
            self.assertIsNone(conn.execute('SELECT 1 FROM compiler_runtime.k_compilation_records WHERE record_id=%s',
                                           (created['record_id'],)).fetchone())
            self.assertEqual(before, conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton').fetchone()['version'])

    def test_false_quote_unknown_media_and_wrong_edge_owner_are_rejected(self):
        for quote, media in [('not present in I', None), ('', 'a'*64)]:
            with self.subTest(quote=quote, media=media), self.assertRaises(psycopg.Error), self.connection() as conn:
                self.node(conn, self.execution(conn, 'i2k'), quote=quote, media=media)
        source, target, unused = self.initial_graph()
        with self.connection() as conn:
            third = self.node(conn, self.execution(conn, 'i2k'), kind='proposition')
        with self.assertRaises(psycopg.errors.ForeignKeyViolation), self.connection() as conn:
            execution = self.execution(conn, 'n2e', (source, target, third))
            # The claimed logical source and exact revision belong to different Nodes.
            bad_source = {**source, 'revision_id': target['revision_id']}
            self.edge(conn, execution, bad_source, third)

    def test_concurrent_synthetic_revisions_have_one_winner(self):
        with self.connection() as conn:
            source = self.classified_node(conn)
        barrier = Barrier(2)

        def worker(value):
            barrier.wait(timeout=15)
            try:
                with self.connection() as conn:
                    result = self.revise(conn, source, value=value)
                return result
            except psycopg.Error:
                return None

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(worker, (4, 5)))
        self.assertEqual(1, sum(result is not None for result in results))
        with self.connection() as conn:
            self.assertEqual(2, conn.execute('SELECT count(*) AS n FROM canonical_store.knowledge_node_revisions WHERE knode_id=%s',
                                            (source['node_id'],)).fetchone()['n'])

    def test_applicability_rebases_without_edge_revision_and_is_append_only(self):
        source, target, edge = self.initial_graph(classified=True)
        with self.connection() as conn:
            revised = self.revise(conn, source, value=4)
        orders = []
        for applicable in (True, False):
            with self.connection() as conn:
                execution = self.execution(conn, 'n2e', (revised, target))
                record = self.record(conn, execution, 0, 'n2e', fingerprint('same relation'), fingerprint('same relation'))
                event = conn.execute('INSERT INTO canonical_store.knowledge_edge_applicability_events(kedge_id,'
                                     'semantic_kedge_revision_id,from_knode_revision_id,to_knode_revision_id,applicable,origin_record_id) '
                                     'VALUES (%s,%s,%s,%s,%s,%s) RETURNING event_order',
                                     (edge['edge_id'], edge['revision_id'], revised['revision_id'], target['revision_id'], applicable, record)).fetchone()
                orders.append(event['event_order'])
                conn.execute("UPDATE compiler_runtime.k_compilation_records SET disposition='no_material_delta',"
                             'result_edge_id=%s,result_edge_revision_id=%s,resolved_at=CURRENT_TIMESTAMP WHERE record_id=%s',
                             (edge['edge_id'], edge['revision_id'], record))
                conn.execute('DELETE FROM compiler_runtime.k_temporary_candidates WHERE record_id=%s', (record,))
                if not applicable:
                    # This fixture explicitly changes the preceding true result to false.
                    conn.execute("INSERT INTO compiler_runtime.k_outbox(record_id,operation) VALUES (%s,'k2k')", (record,))
        self.assertLess(orders[0], orders[1])
        with self.connection() as conn:
            latest = conn.execute('SELECT * FROM canonical_store.knowledge_edge_applicability_events '
                                  'WHERE semantic_kedge_revision_id=%s ORDER BY event_order DESC LIMIT 1',
                                  (edge['revision_id'],)).fetchone()
            self.assertFalse(latest['applicable'])
            self.assertEqual(revised['revision_id'], latest['from_knode_revision_id'])
            self.assertIsNotNone(conn.execute("SELECT 1 FROM compiler_runtime.k_outbox WHERE record_id=%s AND operation='k2k'",
                                             (latest['origin_record_id'],)).fetchone())
            self.assertEqual(1, conn.execute('SELECT count(*) AS n FROM canonical_store.knowledge_edge_revisions WHERE kedge_id=%s',
                                            (edge['edge_id'],)).fetchone()['n'])
        with self.assertRaises(psycopg.Error), self.connection() as conn:
            conn.execute('DELETE FROM canonical_store.knowledge_edge_applicability_events WHERE kedge_id=%s', (edge['edge_id'],))


if __name__ == '__main__':
    unittest.main()
