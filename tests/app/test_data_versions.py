"""Version CAS and immutable history using real isolated PG and managed files.

These fixtures only register synthetic bytes. They do not parse sources, call
models, migrate databases, or access any real code/paper collection.
"""

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg

from palimpsest.artifact_store import ArtifactStore
from palimpsest.canonical_store import PostgresRepository, connection
from palimpsest.data_versions import DataVersions, immutable_versions
from palimpsest.errors import PalimpsestError
from palimpsest.service import DataService


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires the explicit Linux fixture database palimpsest')
class DataVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['PALIMPSEST_TEST_DSN']
        with connection(cls.dsn) as conn:
            if conn.execute('SELECT current_database() AS name').fetchone()['name'] != 'palimpsest':
                raise RuntimeError('Data version tests require the isolated database named palimpsest')
            if conn.execute("SELECT to_regclass('canonical_store.data_versions') AS name").fetchone()['name'] is None:
                raise RuntimeError('Provision migration 0013 in the isolated fixture first')

    def setUp(self):
        temporary = TemporaryDirectory(prefix='palimpsest-versions-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.store = ArtifactStore(self.base / 'artifacts')
        self.repo = PostgresRepository(self.dsn)
        self.versions = DataVersions(self.dsn, self.store)
        self.data = []
        for letter in ('A', 'B', 'C'):
            path = self.base / f'{letter}.txt'
            path.write_text(f'Synthetic version {letter}: {uuid4()}\n', encoding='utf-8')
            self.data.append(DataService(self.repo, self.store).import_file(path)['data_id'])
        self.series = self.versions.create('Synthetic maintained document')['series_id']

    def append(self, data=0, head=None, *, identifier=None, **kwargs):
        return self.versions.append(self.series, self.data[data], identifier or self.repo.allocate_id(), head, **kwargs)

    def rows(self):
        return self.versions.history(self.series)['versions']

    def request_count(self, identifier):
        with connection(self.dsn) as conn:
            return conn.execute('SELECT count(*) AS n FROM compiler_runtime.data_version_requests WHERE request_id=%s',
                                (identifier,)).fetchone()['n']

    def test_creation_replays_original_result_even_after_a_head_is_published(self):
        identifier = self.repo.allocate_id()
        created = self.versions.create('Another synthetic document', identifier)
        version = self.versions.append(created['series_id'], self.data[0], self.repo.allocate_id(), None)
        replay = self.versions.create('Another synthetic document', identifier)
        self.assertEqual(replay, {**created, 'replayed': True})
        self.assertIsNone(replay['head_version_id'])
        self.assertEqual(self.versions.show(created['series_id'])['head_version_id'], version['version_id'])
        with self.assertRaises(PalimpsestError) as caught:
            self.versions.create('Different input', identifier)
        self.assertEqual(caught.exception.code, 'idempotency_conflict')

    def test_same_head_content_is_no_op_and_replay_does_not_follow_a_new_head(self):
        first = self.append(title='Version A', message='Initial content')
        identifier = self.repo.allocate_id()
        checked = self.append(head=first['version_id'], identifier=identifier,
                              title='Must not replace original title', message='Checked unchanged bytes')
        self.assertEqual(checked['outcome'], 'no_op')
        self.assertEqual(checked['version_id'], first['version_id'])
        self.assertEqual(checked['title'], first['title'])
        self.assertEqual(checked['message'], first['message'])
        self.assertEqual(len(self.rows()), 1)
        second = self.append(1, first['version_id'])
        replay = self.append(head=first['version_id'], identifier=identifier,
                             title='Must not replace original title', message='Checked unchanged bytes')
        self.assertEqual(replay, {**checked, 'replayed': True})
        self.assertEqual(self.versions.show(self.series)['head_version_id'], second['version_id'])
        with connection(self.dsn) as conn:
            saved = conn.execute('SELECT request_payload FROM compiler_runtime.data_version_requests WHERE request_id=%s',
                                 (identifier,)).fetchone()['request_payload']
        self.assertEqual(saved['message'], 'Checked unchanged bytes')

    def test_revert_reuses_original_data_but_appends_a_distinct_version(self):
        first = self.append()
        second = self.append(1, first['version_id'])
        reverted = self.append(0, second['version_id'], message='Return to exact original bytes')
        self.assertEqual(reverted['data_id'], first['data_id'])
        self.assertNotEqual(reverted['version_id'], first['version_id'])
        self.assertEqual(reverted['parent_version_id'], second['version_id'])
        self.assertEqual([row['version_number'] for row in self.rows()], [3, 2, 1])
        self.assertEqual([row['data_id'] for row in self.rows()], [self.data[0], self.data[1], self.data[0]])
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM canonical_store.data WHERE data_id=ANY(%s)',
                                         (self.data,)).fetchone()['n'], 3)
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM canonical_store.information WHERE data_id=ANY(%s)',
                                         (self.data,)).fetchone()['n'], 0)
        self.assertEqual(self.store.read(self.data[0], (self.base / 'A.txt').stat().st_size),
                         (self.base / 'A.txt').read_bytes())

    def test_stale_expected_head_cannot_create_a_version_or_receipt(self):
        first = self.append()
        second = self.append(1, first['version_id'])
        before = self.rows()
        identifier = self.repo.allocate_id()
        with self.assertRaises(PalimpsestError) as caught:
            self.append(2, first['version_id'], identifier=identifier)
        self.assertEqual(caught.exception.code, 'data_version_head_changed')
        self.assertEqual(caught.exception.details['current_head'], second['version_id'])
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.request_count(identifier), 0)

    def test_two_concurrent_updates_have_one_winner_and_no_branch(self):
        first = self.append()
        barrier = Barrier(2)
        identifiers = [self.repo.allocate_id(), self.repo.allocate_id()]
        def compete(number):
            barrier.wait(timeout=10)
            try:
                return self.append(number + 1, first['version_id'], identifier=identifiers[number])
            except PalimpsestError as error:
                return {'error_code': error.code}
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(compete, number) for number in range(2)]
            results = [future.result(timeout=30) for future in futures]
        self.assertEqual(sum(row.get('outcome') == 'created' for row in results), 1)
        self.assertEqual([row['error_code'] for row in results if 'error_code' in row], ['data_version_head_changed'])
        self.assertEqual(len(self.rows()), 2)
        self.assertEqual(self.rows()[0]['parent_version_id'], first['version_id'])

    def test_concurrent_same_request_returns_one_original_version(self):
        identifier = self.repo.allocate_id()
        barrier = Barrier(2)
        def same_request():
            barrier.wait(timeout=10)
            return self.append(identifier=identifier)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(same_request) for _ in range(2)]
            results = [future.result(timeout=30) for future in futures]
        self.assertEqual(len({row['version_id'] for row in results}), 1)
        self.assertEqual(sorted(row['replayed'] for row in results), [False, True])
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.request_count(identifier), 1)

    def test_actor_cannot_change_another_series_or_replay_another_request(self):
        identifier = self.repo.allocate_id()
        created = self.versions.create('Actor-owned synthetic history', identifier, actor_ref='alice')
        with self.assertRaises(PalimpsestError) as caught:
            self.versions.create('Actor-owned synthetic history', identifier, actor_ref='bob')
        self.assertEqual(caught.exception.code, 'permission_denied')
        with self.assertRaises(PalimpsestError) as caught:
            self.versions.append(created['series_id'], self.data[0], self.repo.allocate_id(), None, actor_ref='bob')
        self.assertEqual(caught.exception.code, 'permission_denied')
        self.assertIsNone(self.versions.show(created['series_id'])['head_version_id'])

    def test_failure_after_head_update_rolls_back_version_head_and_request(self):
        first = self.append()
        identifier = self.repo.allocate_id()
        before = self.rows()
        with patch.object(self.versions, '_save_request', side_effect=RuntimeError('Synthetic lost transaction')):
            with self.assertRaisesRegex(RuntimeError, 'Synthetic lost transaction'):
                self.append(1, first['version_id'], identifier=identifier)
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.versions.show(self.series)['head_version_id'], first['version_id'])
        self.assertEqual(self.request_count(identifier), 0)
        recovered = self.append(1, first['version_id'], identifier=identifier)
        self.assertEqual(recovered['version_number'], 2)

    def test_missing_or_unverified_data_has_no_version_effect(self):
        with self.assertRaises(PalimpsestError) as caught:
            self.versions.append(self.series, 'a' * 64, self.repo.allocate_id(), None)
        self.assertEqual(caught.exception.code, 'data_not_found')
        identifier = self.repo.allocate_id()
        with patch.object(self.store, 'verify', side_effect=PalimpsestError('integrity_conflict', 'Synthetic verification failure')) as verify:
            with self.assertRaises(PalimpsestError) as caught:
                self.append(identifier=identifier)
            self.assertEqual(caught.exception.code, 'integrity_conflict')
            verify.assert_called_once_with(self.data[0], (self.base / 'A.txt').stat().st_size)
        self.assertEqual(self.rows(), [])
        self.assertEqual(self.request_count(identifier), 0)

    def test_version_rows_parent_ownership_and_head_cannot_be_rewritten(self):
        first = self.append()
        second = self.append(1, first['version_id'])
        other = self.versions.create('Another series')
        foreign = self.versions.append(other['series_id'], self.data[0], self.repo.allocate_id(), None)
        changes = [
            ('UPDATE canonical_store.data_versions SET data_id=%s WHERE version_id=%s', (self.data[2], first['version_id'])),
            ('UPDATE canonical_store.data_series SET head_version_id=%s WHERE series_id=%s', (first['version_id'], self.series)),
            ('''INSERT INTO canonical_store.data_versions(series_id,parent_version_id,data_id,version_number,actor_ref)
                VALUES (%s,%s,%s,3,'local')''', (self.series, foreign['version_id'], self.data[2])),
            ('''INSERT INTO canonical_store.data_versions(series_id,parent_version_id,data_id,version_number,actor_ref)
                VALUES (%s,%s,%s,3,'local')''', (self.series, second['version_id'], second['data_id'])),
        ]
        for query, params in changes:
            with self.subTest(query=query), self.assertRaises(psycopg.Error), psycopg.connect(self.dsn) as conn:
                conn.execute(query, params)
        self.assertEqual(self.versions.show(self.series)['head_version_id'], second['version_id'])
        self.assertEqual(self.versions.version(first['version_id'])['data_id'], self.data[0])

    def test_immutable_snapshot_reader_keeps_requested_order_without_live_head_fields(self):
        first = self.append()
        second = self.append(1, first['version_id'])
        with connection(self.dsn) as conn:
            rows = immutable_versions(conn, [second['version_id'], first['version_id']])
            self.assertEqual([row['version_id'] for row in rows], [second['version_id'], first['version_id']])
            self.assertTrue(all('head_version_id' not in row and 'replayed' not in row for row in rows))
            with self.assertRaises(PalimpsestError):
                immutable_versions(conn, [first['version_id'], first['version_id']])
        self.assertEqual(self.versions.version(first['version_id']), rows[1])

    def test_current_b_can_use_a_complete_b_reuse_route_without_requiring_historical_a(self):
        import test_multi_source_runtime as multi_fixtures
        import test_k2k_runtime as inference_fixtures

        fixture = multi_fixtures.MultiSourceRuntimeTests('runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        first_data, second_data = fixture.first.data_id, fixture.second.data_id
        seed_response = fixture.response()
        seed = fixture.accept(fixture.prepare(), seed_response)
        general, observation_a, observation_b = [row['result_node_revision_id'] for row in seed['records']]
        versions_a = DataVersions(self.dsn, fixture.first.fixture.runtime.store)
        versions_b = DataVersions(self.dsn, fixture.second.fixture.runtime.store)
        series = versions_a.create('Synthetic A then B support history')['series_id']
        version_a = versions_a.append(series, first_data, self.repo.allocate_id(), None)
        version_b = versions_b.append(series, second_data, self.repo.allocate_id(), version_a['version_id'])
        self.assertEqual(versions_b.show(series)['head_version_id'], version_b['version_id'])

        def supported(revision, data):
            with connection(self.dsn) as conn:
                return conn.execute('''SELECT canonical_store.k_revision_supported_by_version_data(
                    %s::uuid,%s::text[]) AS supported''', (revision, data)).fetchone()['supported']

        # This first full claim was accepted with a composite A+B evidence set.
        self.assertTrue(supported(general, [first_data, second_data]))
        self.assertFalse(supported(general, [first_data]))
        self.assertFalse(supported(general, [second_data]))
        self.assertTrue(supported(observation_a, [first_data]))
        self.assertFalse(supported(observation_a, [second_data]))

        # Reuse the established K2K fixture methods over these existing premises;
        # no additional source fixture or provider is needed for the derivation.
        inference = inference_fixtures.K2KRuntimeTests('runTest')
        inference.runtime, inference.helper = fixture.runtime, fixture.second
        inference.dsn, inference.data_id = self.dsn, second_data
        inference.premises = [general, observation_b]
        inference_job = inference.prepare()
        derived = inference.commit(inference_job, inference.response(inference_job))['records'][0]['result_node_revision_id']
        self.assertFalse(supported(derived, [second_data]), 'Every actual premise needs its own complete route')

        b_only = fixture.response(general_only=True)
        b_only['nodes'][0]['evidence'] = [citation for citation in b_only['nodes'][0]['evidence']
                                        if citation['information_id'] == fixture.second.text['information_id']]
        for review in b_only['reviews']:
            selected = review['information_id'] == fixture.second.text['information_id']
            review.update(disposition='selected' if selected else 'context_only',
                          candidate_keys=['shared_general'] if selected else [])
        verdict = fixture.decisions(b_only)
        verdict['decisions'][0].update(verdict='reused', equivalent_revision_id=general)
        reused = fixture.accept(fixture.prepare(), b_only, verdict)['records'][0]
        self.assertEqual(reused['result_node_revision_id'], general)
        with connection(self.dsn) as conn:
            new_groundings = conn.execute('SELECT count(*) AS n FROM canonical_store.knowledge_node_groundings WHERE origin_record_id=%s',
                                          (reused['record_id'],)).fetchone()['n']
            used = conn.execute('''SELECT DISTINCT i.data_id FROM compiler_runtime.k_information_review_records l
                JOIN canonical_store.information i USING(information_id) WHERE l.record_id=%s''',
                (reused['record_id'],)).fetchall()
        self.assertEqual(new_groundings, 0, 'Existing exact B grounding is deduplicated')
        self.assertEqual([row['data_id'] for row in used], [second_data])
        self.assertTrue(supported(general, [version_b['data_id']]))
        self.assertTrue(supported(derived, [version_b['data_id']]))
        self.assertFalse(supported(observation_a, [version_b['data_id']]), 'A source scope still requires A')


if __name__ == '__main__':
    unittest.main()
