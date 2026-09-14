"""Exact W2P checks; optional isolated PG uses synthetic W model receipts."""

from copy import deepcopy
import json
import os
import unittest

from palimpsest import parchment, wisdom
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
import test_k2w as wfixtures


def source(number=81):
    answer = wfixtures.answer()
    return wisdom.build_snapshot(wisdom_id=wfixtures.uid(number), execution_id=wfixtures.uid(number + 100),
        created_at='2026-09-14T12:00:00+00:00', packet=wfixtures.packet(), answer=answer,
        validation=wfixtures.validation(answer), generation_profile={'schema_version': 'knowledge-wisdom-v1'})


def compose(inputs):
    return parchment.build_snapshot(inputs, parchment_id=wfixtures.uid(95), title='A source-grounded article',
        actor='test-user', created_at='2026-09-14T13:00:00+00:00', implementation_sha256={'parchment.py': 'a' * 64})


class ParchmentTests(unittest.TestCase):
    def test_order_exact_text_context_uncertainty_and_claim_citations_preserved(self):
        inputs = [source(82), source(81)]
        before = deepcopy(inputs)
        result = compose(inputs)
        self.assertEqual(result['input_wisdom_ids'], [value['wisdom_id'] for value in inputs])
        for index, value in enumerate(inputs):
            section = result['body']['sections'][index]
            for name in parchment.SECTION_FIELDS:
                self.assertEqual(section[name], value[name])
            self.assertEqual(result['citations'][index]['claims'], value['citations'])
            self.assertEqual(section['wisdom_snapshot_sha256'], value['snapshot_sha256'])
        self.assertEqual(inputs, before)
        self.assertEqual(result['direct_k_revision_ids'], [])
        self.assertEqual(result['direct_information_ids'], [])
        self.assertEqual(result['provenance']['operation'], 'w2p')
        self.assertIsNone(result['supersedes_parchment_id'])
        self.assertEqual(parchment.check_snapshot(result), result)

    def test_absent_duplicate_mutated_or_unaccepted_w_cannot_become_parchment(self):
        for inputs in ([], [source(), source()], [{'schema_version': 'legacy-wiki-page'}]):
            with self.assertRaises(PalimpsestError):
                compose(inputs)
        for mutate in (lambda v: v['answer_or_payload']['claims'][0].update(text='Unrecorded prose'),
                       lambda v: v['validation'].update(verdict='needs_human'),
                       lambda v: v.update(validation=[])):
            value = source()
            mutate(value)
            with self.assertRaises(PalimpsestError):
                compose([value])
        value = compose([source()])
        value['title'] = 'Changed title'
        with self.assertRaises(PalimpsestError):
            parchment.check_snapshot(value)


@unittest.skipUnless(os.environ.get('PALIMPSEST_TEST_DSN'), 'Requires dedicated W/P PostgreSQL')
class ParchmentRuntimeTests(unittest.TestCase):
    def setUp(self):
        from palimpsest.parchment_runtime import ParchmentRuntime
        from test_wisdom_runtime import WisdomRuntimeTests
        self.f = WisdomRuntimeTests('runTest')
        self.addCleanup(self.f.doCleanups)
        self.f.setUp()  # Asserts exact palimpsest_wisdom_checks, never a user DB.
        self.service = ParchmentRuntime(self.f.dsn)
        self.first = self.f.accept(self.f.prepare())
        self.second = self.f.accept(self.f.prepare())

    def test_create_exact_order_replay_new_request_and_historical_w_after_k_state_changes(self):
        from palimpsest.canonical_store import connection
        identifier = self.f.repo.allocate_id()
        refs = [self.second['wisdom_id'], self.first['wisdom_id']]
        before = self.f.counts()
        result = self.service.compose(identifier, title='Test article', wisdom_ids=refs, actor='test-user')
        self.assertFalse(result['replayed'])
        self.assertEqual(result['input_wisdom_ids'], refs)
        self.assertEqual(self.service.parchment(result['parchment_id']), {k: v for k, v in result.items() if k != 'replayed'})
        with connection(self.f.dsn) as conn:
            links = conn.execute('SELECT wisdom_id FROM canonical_store.parchment_wisdoms WHERE parchment_id=%s ORDER BY ordinal',
                                 (result['parchment_id'],)).fetchall()
            self.assertEqual([str(row['wisdom_id']) for row in links], refs)
        self.assertEqual(self.f.counts(), before)
        from palimpsest.source_read import SourceReadService
        reader = SourceReadService(self.f.dsn, self.f.f.root)
        catalog = reader.dispatch({'operation': 'parchment_catalog'})
        listed = next(page for page in catalog['parchments'] if page['parchment_id'] == result['parchment_id'])
        self.assertEqual(listed['input_wisdom_ids'], refs)
        self.assertIn(self.f.f.data_id, listed['source_data_ids'])
        document = reader.dispatch({'operation': 'parchment_get', 'parchment_id': result['parchment_id']})
        self.assertEqual(document['parchment'], self.service.parchment(result['parchment_id']))
        self.assertTrue(document['read_only'])
        with connection(self.f.dsn) as conn:
            conn.execute('UPDATE compiler_runtime.knowledge_state SET version=version+1 WHERE singleton')
        replay = self.service.compose(identifier, title='Test article', wisdom_ids=refs, actor='test-user')
        self.assertTrue(replay['replayed'])
        self.assertEqual(replay['parchment_id'], result['parchment_id'])
        another = self.service.compose(self.f.repo.allocate_id(), title='Test article', wisdom_ids=refs, actor='test-user')
        self.assertNotEqual(another['parchment_id'], result['parchment_id'])
        with self.assertRaises(PalimpsestError) as caught:
            self.service.compose(identifier, title='Changed article', wisdom_ids=refs, actor='test-user')
        self.assertEqual(caught.exception.code, 'idempotency_conflict')
        self.assertEqual(self.f.f.source_state(), self.f.f.source_before)

    def test_database_rejects_changed_prose_missing_typed_link_and_wrong_w_hash(self):
        import psycopg
        from psycopg.types.json import Jsonb
        original = self.service.compose(self.f.repo.allocate_id(), title='Exact article',
                                        wisdom_ids=[self.first['wisdom_id']], actor='test-user')
        def insert(conn, snapshot):
            raw = json.dumps({k: v for k, v in snapshot.items() if k != 'snapshot_sha256'}, ensure_ascii=False,
                             sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
            conn.execute('''INSERT INTO canonical_store.parchments
                (parchment_id,request_id,request_fingerprint,title,actor,snapshot,snapshot_bytes,snapshot_sha256,created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (snapshot['parchment_id'], self.f.repo.allocate_id(),
                    digest('fixture'), snapshot['title'], 'test-user', Jsonb(snapshot), raw,
                    snapshot['snapshot_sha256'], snapshot['created_at']))
        for fault in ('changed_prose', 'missing_link', 'wrong_w_hash'):
            snapshot = {k: deepcopy(v) for k, v in original.items() if k not in ('replayed', 'snapshot_sha256')}
            snapshot['parchment_id'] = self.f.repo.allocate_id()
            if fault == 'changed_prose':
                snapshot['body']['sections'][0]['answer_or_payload']['claims'][0]['text'] = 'Invented extra text.'
            snapshot['snapshot_sha256'] = digest(snapshot)
            with self.subTest(fault=fault), self.assertRaises(psycopg.Error):
                with psycopg.connect(self.f.dsn) as conn:
                    insert(conn, snapshot)
                    if fault == 'wrong_w_hash':
                        conn.execute('''INSERT INTO canonical_store.parchment_wisdoms
                            (parchment_id,ordinal,wisdom_id,wisdom_snapshot_sha256) VALUES (%s,0,%s,%s)''',
                            (snapshot['parchment_id'], self.first['wisdom_id'], '0' * 64))
                    conn.execute('SET CONSTRAINTS ALL IMMEDIATE')
        self.assertEqual(self.service.parchment(original['parchment_id'])['body'], original['body'])


if __name__ == '__main__':
    unittest.main()
