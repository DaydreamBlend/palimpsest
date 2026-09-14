"""Segmented Data registration and real Markdown D2I in an isolated PG fixture.

Each test owns unique source bytes and a temporary Artifact Store. No migration,
provider, parser model, production source or canonical history is modified.
"""

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from palimpsest import code_snapshot
from palimpsest.artifact_store import ArtifactStore
from palimpsest.canonical_store import PostgresRepository, connection
from palimpsest.compiler_runtime import CompilerRuntime
from palimpsest.errors import PalimpsestError
from palimpsest.segmented_artifact_store import PROFILE
from palimpsest.service import DataService


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires the explicit Linux PostgreSQL fixture database palimpsest')
class SegmentedRegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['PALIMPSEST_TEST_DSN']
        with connection(cls.dsn) as conn:
            if conn.execute('SELECT current_database() AS name').fetchone()['name'] != 'palimpsest':
                raise RuntimeError('Segmented registration tests require the isolated database named palimpsest')

    def setUp(self):
        temporary = TemporaryDirectory(prefix='segmented-registration-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.code = self.base / 'repository'
        (self.code / 'src').mkdir(parents=True)
        self.common = (f'\ufeff# Unique fixture {uuid4()}\r\n'
                       'def shared():\r\n    return "μ 😀 Cafe\u0301"\r\n').encode('utf-8')
        self.changed = b'def changing():\n    return 1\n'
        (self.code / 'src/common.py').write_bytes(self.common)
        (self.code / 'src/changing.py').write_bytes(self.changed)
        self.paths = ['src/changing.py', 'src/common.py']
        self.directory = self.code / 'snapshots' / 'first'
        self.manifest = code_snapshot.snapshot(self.code, self.directory, paths=self.paths)
        self.raw = (self.directory / 'dossier.md').read_bytes()
        self.data_id = self.manifest['dossier_sha256']
        self.root = self.base / 'artifacts'
        self.repository = PostgresRepository(self.dsn)
        self.store = ArtifactStore(self.root)
        self.service = DataService(self.repository, self.store, actor_ref='local')
        self.runtime = CompilerRuntime(self.dsn, self.root)

    def row(self, sql, parameters=()):
        with connection(self.dsn) as conn:
            return conn.execute(sql, parameters).fetchone()

    def counts(self, data_id=None):
        identifier = data_id or self.data_id
        return self.row('''SELECT
            (SELECT count(*) FROM canonical_store.data WHERE data_id=%s) AS data,
            (SELECT count(*) FROM canonical_store.data_acquisitions WHERE data_id=%s) AS acquisitions,
            (SELECT count(*) FROM canonical_store.information WHERE data_id=%s) AS information,
            (SELECT count(*) FROM compiler_runtime.operation_executions WHERE data_id=%s AND operation='d2i') AS d2i''',
            (identifier,) * 4)

    def blobs(self):
        return {path.relative_to(self.root).as_posix(): (path.stat().st_ino, path.read_bytes())
                for path in (self.root / 'blobs' / 'sha256').glob('*/*')}

    def original_path(self, identifier=None):
        identifier = identifier or self.data_id
        return self.root / f'objects/sha256/{identifier[:2]}/{identifier}'

    def error(self, code, action):
        with self.assertRaises(PalimpsestError) as caught:
            action()
        self.assertEqual(caught.exception.code, code)

    def test_registered_segmented_data_keeps_raw_identity_metadata_and_journal_policy(self):
        result = self.service.import_code_snapshot(self.directory)
        self.assertEqual(result['data_id'], sha256(self.raw).hexdigest())
        self.assertEqual(result['state'], 'committed')
        self.assertFalse(self.original_path().exists())
        self.assertEqual(self.store.read(self.data_id, len(self.raw)), self.raw)
        self.assertEqual(self.service.verify(self.data_id)['artifact_path'],
                         f'objects/sha256/{self.data_id[:2]}/{self.data_id}')
        metadata = self.service.show(self.data_id)
        self.assertEqual(metadata['media_type'], 'text/markdown')
        self.assertEqual(metadata['byte_size'], len(self.raw))
        journal = self.repository.get_request(result['request_id'])
        self.assertEqual(journal['external_metadata']['storage_request'], {
            'profile': PROFILE, 'segments': code_snapshot.storage_segments(self.manifest)})
        self.assertEqual(self.counts(), {'data': 1, 'acquisitions': 1, 'information': 0, 'd2i': 0})
        self.assertEqual(self.store.storage_stats(self.data_id, len(self.raw))['storage'], 'segmented-v1')
        self.assertEqual((self.directory / 'dossier.md').read_bytes(), self.raw)

    def test_same_request_replay_and_ordinary_duplicate_do_not_add_data_or_blob_copies(self):
        result = self.service.import_code_snapshot(self.directory)
        before = self.blobs()
        repeated = self.service.import_code_snapshot(self.directory, request_id=result['request_id'])
        self.assertTrue(repeated['replayed'])
        self.assertEqual(repeated['acquisition_id'], result['acquisition_id'])
        self.error('duplicate_data', lambda: self.service.import_file(self.directory / 'dossier.md', media_type='text/markdown'))
        self.error('idempotency_conflict', lambda: self.service.import_file(self.directory / 'dossier.md',
            request_id=result['request_id'], media_type='text/markdown'))
        self.assertEqual(self.blobs(), before)
        self.assertEqual(self.counts(), {'data': 1, 'acquisitions': 1, 'information': 0, 'd2i': 0})
        self.assertFalse(self.original_path().exists())

    def test_after_publish_recovery_uses_frozen_segmented_bytes_without_original_or_staging(self):
        request_id = self.repository.allocate_id()
        def interrupt(stage, request):
            if stage == 'after_publish':
                self.assertEqual(request, request_id)
                raise RuntimeError('injected post-publication interruption')
        interrupted = DataService(self.repository, self.store, actor_ref='local', checkpoint=interrupt)
        with self.assertRaisesRegex(RuntimeError, 'post-publication interruption'):
            interrupted.import_code_snapshot(self.directory, request_id=request_id)
        self.assertEqual(self.counts()['data'], 0)
        self.assertEqual(self.repository.get_request(request_id)['state'], 'staged')
        before = self.blobs()
        (self.directory / 'dossier.md').rename(self.directory / 'dossier-unavailable.md')
        with self.store.request_lock(request_id):
            self.store.cleanup(request_id)
        result = self.service.recover(request_id)
        self.assertEqual(result['state'], 'committed')
        self.assertEqual(result['data_id'], self.data_id)
        self.assertEqual(self.store.read(self.data_id, len(self.raw)), self.raw)
        self.assertEqual(self.blobs(), before)
        self.assertTrue(self.service.recover(request_id)['replayed'])
        self.assertEqual(self.counts(), {'data': 1, 'acquisitions': 1, 'information': 0, 'd2i': 0})

    def test_real_markdown_d2i_reconstructs_all_segmented_bytes_and_exact_file_locations(self):
        self.service.import_code_snapshot(self.directory)
        result = self.runtime.compile_markdown(self.data_id)
        self.assertEqual((result['state'], result['llm_calls'], result['ocr_calls']), ('completed', 0, 0))
        execution = result['execution_id']
        packet = self.runtime.prepare_input(execution)
        units = packet['model_input']['information']
        self.assertEqual(''.join(unit['content'] for unit in units).encode('utf-8'), self.raw)
        reconstruction = self.runtime.reconstruct_source(execution)
        self.assertEqual(reconstruction['source_coverage'], 'exact_utf8_source_bytes')
        self.assertTrue(reconstruction['exact_retained_block_coverage'])
        self.assertFalse(self.original_path().exists())
        entry = next(file for file in self.manifest['files'] if file['path'] == 'src/common.py')
        source_text = self.common.decode('utf-8')
        a, b = source_text.index('μ'), source_text.index('μ') + len('μ 😀 Cafe\u0301')
        data_range = [entry['body_char_start'] + a, entry['body_char_start'] + b]
        unit = next(unit for unit in units if any(ref['text_range']['char_start'] <= data_range[0]
                    and data_range[1] <= ref['text_range']['char_end'] for ref in unit['source_refs']))
        ref = unit['source_refs'][0]
        relative = [position - ref['text_range']['char_start'] for position in data_range]
        located = self.runtime.locate_information(execution, unit['information_id'], char_range=relative)
        absolute_bytes = located['content_segments'][0]['matched_source_byte_range']
        mapped = code_snapshot.locate(self.directory, byte_range=absolute_bytes)
        self.assertEqual(mapped['matches'][0]['path'], 'src/common.py')
        self.assertEqual(mapped['matches'][0]['source_char_range'], [a, b])
        self.assertEqual(mapped['matches'][0]['line_range'], [3, 3])
        destination = self.base / 'restored-dossier.md'
        exported = self.runtime.export_source(execution, destination)
        self.assertTrue(exported['byte_identical'])
        self.assertEqual(destination.read_bytes(), self.raw)
        self.assertEqual(self.runtime.compile_markdown(self.data_id)['execution_id'], execution)

    def test_two_code_versions_share_body_blob_but_keep_distinct_D_and_I_history(self):
        first = self.service.import_code_snapshot(self.directory)
        first_execution = self.runtime.compile_markdown(first['data_id'])
        first_packet = deepcopy(self.runtime.prepare_input(first_execution['execution_id']))
        original_blobs = self.blobs()
        common_hash = sha256(self.common).hexdigest()
        common_blob = f'blobs/sha256/{common_hash[:2]}/{common_hash}'
        self.assertIn(common_blob, original_blobs)
        (self.code / 'src/changing.py').write_bytes(b'def changing():\n    return 2\n')
        second_directory = self.code / 'snapshots' / 'second'
        second_manifest = code_snapshot.snapshot(self.code, second_directory, paths=self.paths)
        second = self.service.import_code_snapshot(second_directory)
        self.assertNotEqual(first['data_id'], second['data_id'])
        updated_blobs = self.blobs()
        self.assertEqual(original_blobs[common_blob], updated_blobs[common_blob])
        self.assertTrue(set(original_blobs) < set(updated_blobs))
        second_execution = self.runtime.compile_markdown(second['data_id'])
        second_packet = self.runtime.prepare_input(second_execution['execution_id'])
        self.assertNotEqual(first_execution['execution_id'], second_execution['execution_id'])
        self.assertFalse(set(first_packet['target_information_ids']) & set(second_packet['target_information_ids']))
        self.assertEqual(self.runtime.prepare_input(first_execution['execution_id']), first_packet)
        self.assertEqual(self.store.read(first['data_id'], len(self.raw)), self.raw)
        self.assertEqual(self.store.read(second['data_id'], second_manifest['dossier_byte_size']),
                         (second_directory / 'dossier.md').read_bytes())
        self.assertFalse(self.original_path(first['data_id']).exists())
        self.assertFalse(self.original_path(second['data_id']).exists())

    def test_corrupt_segment_blocks_compilation_and_is_not_repaired_by_duplicate_import(self):
        self.service.import_code_snapshot(self.directory)
        common_hash = sha256(self.common).hexdigest()
        blob = self.root / f'blobs/sha256/{common_hash[:2]}/{common_hash}'
        blob.chmod(0o600); blob.write_bytes(b'corrupt source segment')
        self.error('integrity_conflict', lambda: self.runtime.compile_markdown(self.data_id))
        self.error('integrity_conflict', lambda: self.service.import_code_snapshot(self.directory))
        self.assertEqual(self.counts(), {'data': 1, 'acquisitions': 1, 'information': 0, 'd2i': 0})
        self.assertEqual(blob.read_bytes(), b'corrupt source segment')

    def test_wrong_frozen_hash_and_unsupported_segmented_PDF_are_rejected_before_registration(self):
        self.error('source_changed', lambda: self.service.import_file(self.directory / 'dossier.md',
            media_type='text/markdown', storage_segments=code_snapshot.storage_segments(self.manifest), expected_data_id='0' * 64))
        self.error('unsupported_segmented_import', lambda: self.service.import_file(self.directory / 'dossier.md',
            media_type='application/pdf', storage_segments=code_snapshot.storage_segments(self.manifest)))
        self.assertEqual(self.counts(), {'data': 0, 'acquisitions': 0, 'information': 0, 'd2i': 0})


if __name__ == '__main__':
    unittest.main()
