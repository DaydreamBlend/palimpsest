"""Real Linux CAS sharing, no-follow reads and interrupted publication; no DB."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from palimpsest.artifact_store import ArtifactStore
from palimpsest import segmented_artifact_store as segmented
from palimpsest.errors import PalimpsestError


def uid(number):
    return f'019a5c1b-7f00-7000-8000-{number:012x}'


def boundaries(parts):
    spans, start = [], 0
    for part in parts:
        spans.append([start, start + len(part)])
        start += len(part)
    return spans


@unittest.skipUnless(sys.platform == 'linux', 'Requires the actual Linux filesystem adapter')
class SegmentedArtifactStoreTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix='segmented-artifacts-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / 'store'
        self.store = ArtifactStore(self.root)
        self.parts = [b'wrapper\n', b'shared raw bytes\r\n\x00\xff', b'old file body', b'\nfooter\n']

    def publish(self, parts=None, number=1, *, cleanup=True, store=None):
        parts = self.parts if parts is None else parts
        store = store or self.store
        source = self.base / f'source-{number}'
        source.write_bytes(b''.join(parts))
        with store.request_lock(uid(number)):
            payload = store.stage(source, uid(number))
            stats = store.publish_segments(uid(number), payload.data_id, payload.byte_size, boundaries(parts))
            if cleanup:
                store.cleanup(uid(number))
        return payload, stats

    def manifest_path(self, data_id):
        return self.root / 'manifests' / 'sha256' / data_id[:2] / (data_id + '.json')

    def blob_path(self, sha):
        return self.root / 'blobs' / 'sha256' / sha[:2] / sha

    def replace_manifest(self, identifier, value):
        value = deepcopy(value)
        value['manifest_sha256'] = segmented._digest({k: v for k, v in value.items() if k != 'manifest_sha256'})
        path = self.manifest_path(identifier)
        path.chmod(0o600)
        path.write_bytes(segmented._json(value))

    def error(self, code, call):
        with self.assertRaises(PalimpsestError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_two_versions_share_unchanged_file_bytes_and_preserve_raw_identity(self):
        first, stats_a = self.publish()
        parts_b = [*self.parts[:2], b'new file body with one change', self.parts[3]]
        second, stats_b = self.publish(parts_b, 2)
        self.assertNotEqual(first.data_id, second.data_id)
        self.assertEqual(stats_a['new_blob_count'], 4)
        self.assertEqual(stats_b['new_blob_count'], 1)
        self.assertEqual(stats_b['new_blob_bytes'], len(parts_b[2]))
        self.assertEqual(len(list((self.root / 'blobs/sha256').glob('*/*'))), 5)
        for payload, stats, parts in ((first, stats_a, self.parts), (second, stats_b, parts_b)):
            self.assertEqual(self.store.read(payload.data_id, payload.byte_size), b''.join(parts))
            self.assertEqual(hashlib.sha256(b''.join(parts)).hexdigest(), payload.data_id)
            self.assertFalse((self.root / stats['artifact_path']).exists())
            self.assertEqual(self.store.verify(payload.data_id, payload.byte_size), {
                'data_id': payload.data_id, 'byte_size': payload.byte_size,
                'artifact_path': stats['artifact_path'], 'verified': True})
        self.assertEqual((self.base / 'source-1').read_bytes(), b''.join(self.parts))
        self.assertFalse((self.root / 'staging' / uid(1)).exists())

    def test_retry_and_default_publish_reuse_segmented_artifact_without_raw_duplicate(self):
        payload, first = self.publish()
        _, repeated = self.publish(number=2)
        self.assertEqual(repeated['new_blob_count'], 0)
        self.assertEqual(first['manifest_sha256'], repeated['manifest_sha256'])
        with self.store.request_lock(uid(3)):
            self.store.stage(self.base / 'source-1', uid(3))
            relative = self.store.publish(uid(3), payload.data_id, payload.byte_size)
            self.store.cleanup(uid(3))
        self.assertFalse((self.root / relative).exists())
        self.assertEqual(self.store.read(payload.data_id, payload.byte_size), b''.join(self.parts))

    def test_raw_artifact_remains_raw_when_segmented_publication_is_requested(self):
        source = self.base / 'source'
        source.write_bytes(b''.join(self.parts))
        with self.store.request_lock(uid(1)):
            payload = self.store.stage(source, uid(1))
            relative = self.store.publish(uid(1), payload.data_id, payload.byte_size)
            inode = (self.root / relative).stat().st_ino
            stats = self.store.publish_segments(uid(1), payload.data_id, payload.byte_size, boundaries(self.parts))
        self.assertEqual(stats['storage'], 'raw')
        self.assertEqual((self.root / relative).stat().st_ino, inode)
        self.assertFalse(self.manifest_path(payload.data_id).exists())

    def test_gap_overlap_order_incomplete_bounds_wrong_hash_and_missing_lock_fail(self):
        source = self.base / 'source'
        source.write_bytes(b'abcdef')
        self.error('request_lock_required', lambda: self.store.publish_segments(uid(1), '0' * 64, 6, [[0, 6]]))
        with self.store.request_lock(uid(1)):
            payload = self.store.stage(source, uid(1))
            for spans in ([], [[1, 6]], [[0, 2], [3, 6]], [[0, 4], [3, 6]], [[0, 3]],
                          [[0, 7]], [[0, 0], [0, 6]], [[False, 6]], [[3, 6], [0, 3]]):
                with self.subTest(spans=spans):
                    self.error('invalid_artifact_segments', lambda: self.store.publish_segments(uid(1), payload.data_id, 6, spans))
            self.error('integrity_conflict', lambda: self.store.publish_segments(uid(1), '0' * 64, 6, [[0, 6]]))
        self.assertFalse((self.root / 'manifests').exists())

    def test_empty_raw_bytes_have_a_valid_empty_manifest(self):
        payload, stats = self.publish([])
        self.assertEqual(stats['chunk_count'], 0)
        self.assertEqual(self.store.read(payload.data_id, 0), b'')
        self.assertEqual(payload.data_id, hashlib.sha256(b'').hexdigest())

    def test_invalid_or_reordered_descriptor_cannot_change_original_bytes(self):
        payload, _ = self.publish()
        path = self.manifest_path(payload.data_id)
        original = json.loads(path.read_bytes())
        for mutation in ('hash', 'order', 'size', 'path', 'missing', 'field'):
            value = deepcopy(original)
            if mutation == 'hash': value['raw_data_id'] = '0' * 64
            if mutation == 'order': value['chunks'].reverse()
            if mutation == 'size': value['chunks'][0]['byte_size'] += 1
            if mutation == 'path': value['chunks'][0]['sha256'] = '../outside'
            if mutation == 'missing': value['chunks'].pop()
            if mutation == 'field': value['chunks'][0]['path'] = '/etc/passwd'
            self.replace_manifest(payload.data_id, value)
            with self.subTest(mutation=mutation):
                self.error('integrity_conflict', lambda: self.store.read(payload.data_id, payload.byte_size))
        path.chmod(0o600); path.write_bytes(b'{"incomplete":')
        self.error('integrity_conflict', lambda: self.store.verify(payload.data_id, payload.byte_size))

    def test_missing_corrupt_and_symlinked_blobs_fail_without_silent_repair(self):
        payload, _ = self.publish(cleanup=False)
        blob = self.blob_path(hashlib.sha256(self.parts[1]).hexdigest())
        original = blob.read_bytes()
        blob.chmod(0o600); blob.write_bytes(original[:-1])
        self.error('integrity_conflict', lambda: self.store.read(payload.data_id, payload.byte_size))
        with self.store.request_lock(uid(1)):
            self.error('integrity_conflict', lambda: self.store.publish_segments(uid(1), payload.data_id, payload.byte_size, boundaries(self.parts)))
        blob.unlink()
        self.error('artifact_missing', lambda: self.store.read(payload.data_id, payload.byte_size))
        blob.symlink_to(self.base / 'source-1')
        self.error('unsafe_path', lambda: self.store.verify(payload.data_id, payload.byte_size))

    def test_descriptor_and_store_ancestor_symlinks_are_not_followed(self):
        payload, _ = self.publish()
        manifest = self.manifest_path(payload.data_id)
        original = manifest.read_bytes()
        outside = self.base / 'outside.json'; outside.write_bytes(original)
        manifest.unlink(); manifest.symlink_to(outside)
        self.error('unsafe_path', lambda: self.store.read(payload.data_id, payload.byte_size))
        manifest.unlink()
        self.error('artifact_missing', lambda: self.store.read(payload.data_id, payload.byte_size))
        link = self.base / 'store-link'; link.symlink_to(self.root, target_is_directory=True)
        other = ArtifactStore(link)
        self.error('unsafe_path', lambda: other.verify(payload.data_id, payload.byte_size))

    def test_midpublication_failure_leaves_no_manifest_and_retry_reuses_verified_blobs(self):
        source = self.base / 'source'
        source.write_bytes(b''.join(self.parts))
        real = segmented._publish_blob
        count = 0
        def failing(*args):
            nonlocal count
            count += 1
            if count == 2:
                raise RuntimeError('injected interruption')
            return real(*args)
        with self.store.request_lock(uid(1)):
            payload = self.store.stage(source, uid(1))
            with patch.object(segmented, '_publish_blob', side_effect=failing), self.assertRaisesRegex(RuntimeError, 'interruption'):
                self.store.publish_segments(uid(1), payload.data_id, payload.byte_size, boundaries(self.parts))
            self.assertFalse(self.manifest_path(payload.data_id).exists())
            self.error('artifact_missing', lambda: self.store.verify(payload.data_id, payload.byte_size))
            stats = self.store.publish_segments(uid(1), payload.data_id, payload.byte_size, boundaries(self.parts))
            self.assertEqual(stats['new_blob_count'], 3)
            self.store.cleanup(uid(1))
        self.assertEqual(self.store.read(payload.data_id, payload.byte_size), b''.join(self.parts))
        self.assertEqual(len(list((self.root / 'blobs/sha256').glob('*/*'))), 4)

    def test_parallel_requests_publish_shared_CAS_without_overwriting(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.publish, number=number, store=ArtifactStore(self.root)) for number in (1, 2)]
            results = [future.result(timeout=10) for future in futures]
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(len(list((self.root / 'blobs/sha256').glob('*/*'))), 4)
        self.assertEqual(len(list((self.root / 'manifests/sha256').glob('*/*'))), 1)
        payload = results[0][0]
        self.assertEqual(self.store.read(payload.data_id, payload.byte_size), b''.join(self.parts))

    def test_reader_tolerates_only_harmless_temporary_link_removal(self):
        payload, _ = self.publish()
        blob = self.blob_path(hashlib.sha256(self.parts[0]).hexdigest())
        temporary = self.base / 'publisher-link'
        os.link(blob, temporary)
        inode, original_read, removed = blob.stat().st_ino, os.read, False
        def unlink_during_read(descriptor, size):
            nonlocal removed
            data = original_read(descriptor, size)
            if data and not removed and os.fstat(descriptor).st_ino == inode:
                removed = True
                temporary.unlink()
            return data
        with patch('palimpsest.artifact_store.os.read', side_effect=unlink_during_read):
            self.assertEqual(self.store.read(payload.data_id, payload.byte_size), b''.join(self.parts))
        self.assertTrue(removed)
        self.assertEqual(blob.stat().st_nlink, 1)

    def test_raw_and_segmented_representations_both_require_integrity(self):
        payload, stats = self.publish()
        raw = self.root / stats['artifact_path']
        raw.parent.mkdir(parents=True)
        raw.write_bytes(b''.join(self.parts))
        self.assertEqual(self.store.storage_stats(payload.data_id, payload.byte_size)['storage'], 'raw+segmented-v1')
        blob = self.blob_path(hashlib.sha256(self.parts[0]).hexdigest())
        blob.chmod(0o600); blob.write_bytes(b'corrupt')
        self.error('integrity_conflict', lambda: self.store.verify(payload.data_id, payload.byte_size))
        self.assertEqual(raw.read_bytes(), b''.join(self.parts))


if __name__ == '__main__':
    unittest.main()
