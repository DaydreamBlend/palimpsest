"""Adversarial SQL below the Python inference writer, in the isolated fixture DB.

Fault injection deliberately bypasses _derive checks to verify database guards.
No provider is invoked and no test targets a real source/Wiki database.
"""

from copy import deepcopy
import os
import sys
import unittest
from unittest.mock import patch

import psycopg
from psycopg.types.json import Jsonb

from palimpsest.errors import PalimpsestError
import test_k2k_runtime as fixtures


def write_unchecked_derivation(conn, job, record, node, decision, *, omit_last=False,
                              wrong_depth=False, wrong_candidate=False):
    """Inject only the stated storage fault; keep the real stage/commit transaction."""
    body = record['body']
    validation = deepcopy(decision)
    if wrong_candidate:
        validation['candidate_key'] = 'a-different-candidate'
    conn.execute('''INSERT INTO canonical_store.knowledge_derivations
        (record_id,result_node_revision_id,inference_type,assumptions,limitations,
         derivation_basis,derivation_depth,validation) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
        (record['record_id'], node['knode_revision_id'], body['inference_type'],
         Jsonb(body['assumptions']), Jsonb(body['limitations']), body['derivation_basis'],
         body['derivation_depth'] + int(wrong_depth), Jsonb(validation)))
    premises = body['premise_revision_ids'][:-1] if omit_last else body['premise_revision_ids']
    for ordinal, premise in enumerate(premises):
        conn.execute('''INSERT INTO canonical_store.knowledge_derivation_premises
            (record_id,premise_node_revision_id,ordinal) VALUES (%s,%s,%s)''',
            (record['record_id'], premise, ordinal))


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires the explicitly provisioned PostgreSQL fixture database palimpsest')
class K2KSQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.K2KRuntimeTests.setUpClass.__func__(cls)

    def setUp(self):
        self.fixture = fixtures.K2KRuntimeTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.runtime, self.dsn = self.fixture.runtime, self.fixture.dsn

    def assert_database_rollback(self, job, before, operation):
        with self.assertRaises(PalimpsestError) as caught:
            operation()
        self.assertEqual(caught.exception.code, 'database_error', 'The injected write must reach a SQL guard')
        saved = self.runtime.show(job['execution_id'])
        self.assertEqual(saved['state'], 'proposed')
        self.assertIsNone(saved['validator_receipt'])
        self.assertEqual([record['disposition'] for record in saved['records']], ['pending'])
        self.assertEqual(saved['derivations'], [])
        self.assertEqual(self.runtime.graph(self.fixture.data_id), before)

    def test_declared_three_premises_cannot_commit_only_two_even_at_valid_depth(self):
        another = fixtures.K2KRuntimeTests('runTest')
        another.setUp()
        self.addCleanup(another.doCleanups)
        # All three are source-origin revisions, so dropping the third does not
        # alter the calculated depth or leave an ordinal gap. The full-set
        # witness, not the minimum-two or depth check, must reject this write.
        refs = [*self.fixture.premises, another.premises[0]]
        job = self.fixture.prepare(premises=refs)
        response = self.fixture.response(job)
        before = self.runtime.graph(self.fixture.data_id)
        def omit(conn, current, record, node, decision):
            write_unchecked_derivation(conn, current, record, node, decision, omit_last=True)
        with patch.object(self.runtime, '_derive', side_effect=omit):
            self.assert_database_rollback(job, before, lambda: self.fixture.commit(job, response))

    def test_depth_and_validation_candidate_identity_cannot_be_forged(self):
        for fault in ('wrong_depth', 'wrong_candidate'):
            with self.subTest(fault=fault):
                job = self.fixture.prepare()
                response = self.fixture.response(job, name=fault)
                before = self.runtime.graph(self.fixture.data_id)
                def forge(conn, current, record, node, decision):
                    write_unchecked_derivation(conn, current, record, node, decision, **{fault: True})
                with patch.object(self.runtime, '_derive', side_effect=forge):
                    self.assert_database_rollback(job, before, lambda: self.fixture.commit(job, response))

    def test_terminal_derivation_and_premise_history_cannot_be_changed_or_extended(self):
        job = self.fixture.prepare()
        committed = self.fixture.commit(job, self.fixture.response(job))
        record = committed['records'][0]
        before = self.runtime.show(job['execution_id'])['derivations']
        changes = [
            ('UPDATE canonical_store.knowledge_derivations SET derivation_basis=%s WHERE record_id=%s',
             ('Forged basis after acceptance', record['record_id'])),
            ('DELETE FROM canonical_store.knowledge_derivation_premises WHERE record_id=%s', (record['record_id'],)),
            ('''INSERT INTO canonical_store.knowledge_derivation_premises
                (record_id,premise_node_revision_id,ordinal) VALUES (%s,%s,2)''',
             (record['record_id'], record['result_node_revision_id'])),
        ]
        for query, params in changes:
            with self.subTest(query=query), self.assertRaises(psycopg.Error), psycopg.connect(self.dsn) as conn:
                conn.execute(query, params)
        self.assertEqual(self.runtime.show(job['execution_id'])['derivations'], before)

    def test_k2k_record_cannot_launder_premise_information_as_direct_grounding(self):
        job = self.fixture.prepare()
        response = self.fixture.response(job)
        before = self.runtime.graph(self.fixture.data_id)
        original = self.runtime._derive
        def forge(conn, current, record, node, decision):
            # Copy an actual accepted premise citation so that ownership, text,
            # size, and IDs are valid. Only its false K2K direct origin is wrong.
            source = conn.execute('''SELECT * FROM canonical_store.knowledge_node_groundings
                WHERE node_revision_id=%s ORDER BY grounding_id LIMIT 1''',
                (self.fixture.premises[0],)).fetchone()
            conn.execute('''INSERT INTO canonical_store.knowledge_node_groundings
                (node_revision_id,information_id,char_start,char_end,quote,media_sha256,source_role,origin_record_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
                (node['knode_revision_id'], source['information_id'], source['char_start'], source['char_end'],
                 source['quote'], source['media_sha256'], source['source_role'], record['record_id']))
            original(conn, current, record, node, decision)
        with patch.object(self.runtime, '_derive', side_effect=forge):
            self.assert_database_rollback(job, before, lambda: self.fixture.commit(job, response))


if __name__ == '__main__':
    unittest.main()
