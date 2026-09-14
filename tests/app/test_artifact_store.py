"""Real Linux filesystem checks; PostgreSQL/application integration is separate."""

from concurrent.futures import ThreadPoolExecutor
import errno
import hashlib
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from palimpsest.artifact_store import ArtifactStore
from palimpsest.errors import PalimpsestError


REQUEST_A = "019a5c1b-7f00-7000-8000-000000000001"
REQUEST_B = "019a5c1b-7f00-7000-8000-000000000002"


@unittest.skipUnless(sys.platform == "linux", "Requires the actual Linux filesystem adapter")
class ArtifactStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "store"
        self.source = self.base / "paper.pdf"
        self.content = b"%PDF-1.7\noriginal bytes\x00\xff\n"
        self.source.write_bytes(self.content)
        self.store = ArtifactStore(self.root)

    def assert_code(self, code, function, *args):
        with self.assertRaises(PalimpsestError) as caught:
            function(*args)
        self.assertEqual(code, caught.exception.code)

    def publish(self, request_id=REQUEST_A):
        with self.store.request_lock(request_id):
            payload = self.store.stage(self.source, request_id)
            relative = self.store.publish(request_id, payload.data_id, payload.byte_size)
        return payload, self.root / relative

    def test_copy_publish_verify_and_cleanup_preserve_source_and_other_request(self):
        with self.store.request_lock(REQUEST_A):
            payload = self.store.stage(self.source, REQUEST_A)
            self.assertEqual(hashlib.sha256(self.content).hexdigest(), payload.data_id)
            self.assertEqual(len(self.content), payload.byte_size)
            self.assertEqual(payload, self.store.staged(REQUEST_A))
            relative = self.store.publish(REQUEST_A, payload.data_id, payload.byte_size)
            with self.store.request_lock(REQUEST_B):
                self.store.stage(self.source, REQUEST_B)
            self.store.cleanup(REQUEST_A)
        self.assertEqual(self.content, self.source.read_bytes())
        self.assertEqual(self.content, (self.root / relative).read_bytes())
        self.assertTrue((self.root / "staging" / REQUEST_B / "payload").is_file())
        self.assertTrue(self.store.verify(payload.data_id, payload.byte_size)["verified"])
        self.assertFalse((self.root / "staging" / REQUEST_A).exists())

    def test_same_request_reuses_complete_stage_but_rejects_different_bytes(self):
        with self.store.request_lock(REQUEST_A):
            payload = self.store.stage(self.source, REQUEST_A)
            staged_path = self.root / "staging" / REQUEST_A / "payload"
            inode = staged_path.stat().st_ino
            self.assertEqual(payload, self.store.stage(self.source, REQUEST_A))
            self.assertEqual(inode, staged_path.stat().st_ino)
            self.source.write_bytes(b"different source")
            with self.assertRaises(PalimpsestError) as caught:
                self.store.stage(self.source, REQUEST_A)
            self.assertEqual("idempotency_conflict", caught.exception.code)
            self.assertEqual(6, caught.exception.exit_code)
            self.assertEqual(self.content, staged_path.read_bytes())

    def test_verified_read_returns_exact_bytes_and_rejects_missing_size_hash_and_links(self):
        payload, path = self.publish()
        self.assertEqual(self.content, self.store.read(payload.data_id, payload.byte_size))
        self.assert_code('artifact_missing', self.store.read, 'f' * 64, payload.byte_size)
        self.assert_code('integrity_conflict', self.store.read, payload.data_id, payload.byte_size + 1)
        path.chmod(0o600)
        path.write_bytes(b'X' * payload.byte_size)
        self.assert_code('integrity_conflict', self.store.read, payload.data_id, payload.byte_size)
        path.unlink()
        path.symlink_to(self.source)
        self.assert_code('unsafe_path', self.store.read, payload.data_id, payload.byte_size)

    def test_verified_read_rejects_replacement_while_collecting_bytes(self):
        payload, path = self.publish()
        original_read = os.read
        changed = False

        def replacing_read(descriptor, size):
            nonlocal changed
            chunk = original_read(descriptor, size)
            if chunk and not changed:
                changed = True
                path.unlink()
                path.write_bytes(self.content)
            return chunk

        with patch('palimpsest.artifact_store.os.read', side_effect=replacing_read):
            self.assert_code('integrity_conflict', self.store.read, payload.data_id, payload.byte_size)

    def test_prejournal_partial_copy_is_not_recovered_as_a_complete_payload(self):
        with self.store.request_lock(REQUEST_A):
            with patch("palimpsest.artifact_store.os.write", side_effect=OSError(errno.ENOSPC, "disk full")):
                self.assert_code("storage_error", self.store.stage, self.source, REQUEST_A)
            self.assertTrue((self.root / "staging" / REQUEST_A / "payload.partial").exists())
            self.assert_code("staging_missing", self.store.staged, REQUEST_A)
            payload = self.store.stage(self.source, REQUEST_A)
            self.assertEqual(hashlib.sha256(self.content).hexdigest(), payload.data_id)
            self.assertFalse((self.root / "staging" / REQUEST_A / "payload.partial").exists())

    def test_source_change_during_copy_is_detected(self):
        original_read = os.read
        changed = False

        def changing_read(descriptor, count):
            nonlocal changed
            chunk = original_read(descriptor, count)
            if chunk and not changed:
                changed = True
                self.source.write_bytes(b"changed while reading")
            return chunk

        with self.store.request_lock(REQUEST_A):
            with patch("palimpsest.artifact_store.os.read", side_effect=changing_read):
                self.assert_code("source_changed", self.store.stage, self.source, REQUEST_A)
            self.assertFalse((self.root / "staging" / REQUEST_A / "payload").exists())

    def test_existing_shared_object_is_reused_without_overwrite(self):
        payload, path = self.publish()
        inode = path.stat().st_ino
        with self.store.request_lock(REQUEST_B):
            self.store.stage(self.source, REQUEST_B)
            self.store.publish(REQUEST_B, payload.data_id, payload.byte_size)
            self.store.cleanup(REQUEST_B)
        self.assertEqual(inode, path.stat().st_ino)
        self.assertEqual(self.content, path.read_bytes())

    def test_corrupt_shared_object_is_never_treated_as_duplicate_or_overwritten(self):
        payload, path = self.publish()
        path.chmod(0o600)
        path.write_bytes(b"x" * len(self.content))
        self.assert_code("integrity_conflict", self.store.verify, payload.data_id, payload.byte_size)
        with self.store.request_lock(REQUEST_B):
            self.store.stage(self.source, REQUEST_B)
            self.assert_code("integrity_conflict", self.store.publish,
                             REQUEST_B, payload.data_id, payload.byte_size)
            self.store.cleanup(REQUEST_B)
        self.assertEqual(b"x" * len(self.content), path.read_bytes())

    def test_wrong_prepared_hash_and_missing_artifact_fail(self):
        with self.store.request_lock(REQUEST_A):
            payload = self.store.stage(self.source, REQUEST_A)
            self.assert_code("integrity_conflict", self.store.publish, REQUEST_A, "0" * 64, payload.byte_size)
        self.assert_code("artifact_missing", self.store.verify, payload.data_id, payload.byte_size)

    def test_symlink_source_managed_component_and_object_are_rejected(self):
        link = self.base / "source-link"
        link.symlink_to(self.source)
        with self.store.request_lock(REQUEST_A):
            self.assert_code("unsafe_path", self.store.stage, link, REQUEST_A)
        payload, object_path = self.publish()
        object_path.unlink()
        object_path.symlink_to(self.source)
        self.assert_code("unsafe_path", self.store.verify, payload.data_id, payload.byte_size)
        (self.root / "staging" / REQUEST_A / "payload").unlink()
        (self.root / "staging" / REQUEST_A).rmdir()
        (self.root / "staging" / REQUEST_A).symlink_to(self.base, target_is_directory=True)
        with self.store.request_lock(REQUEST_A):
            self.assert_code("unsafe_path", self.store.stage, self.source, REQUEST_A)
            self.assert_code("unsafe_path", self.store.cleanup, REQUEST_A)
        self.assertEqual(self.content, self.source.read_bytes())

    def test_path_swap_during_verify_is_detected_even_when_open_inode_is_valid(self):
        payload, path = self.publish()
        original_read = os.read
        changed = False

        def swapping_read(descriptor, count):
            nonlocal changed
            chunk = original_read(descriptor, count)
            if chunk and not changed:
                changed = True
                path.rename(path.with_name("displaced"))
                path.symlink_to(self.source)
            return chunk

        with patch("palimpsest.artifact_store.os.read", side_effect=swapping_read):
            self.assert_code("integrity_conflict", self.store.verify, payload.data_id, payload.byte_size)

    def test_fifo_source_fails_without_waiting_for_a_writer(self):
        fifo = self.base / "fifo"
        os.mkfifo(fifo)
        with self.store.request_lock(REQUEST_A):
            self.assert_code("unsafe_path", self.store.stage, fifo, REQUEST_A)

    def test_lock_is_required_and_request_identity_cannot_escape(self):
        self.assert_code("request_lock_required", self.store.stage, self.source, REQUEST_A)
        self.assert_code("invalid_request_id", self.store.cleanup, "../outside")
        self.assert_code("invalid_data_id", self.store.verify, "../outside", 0)

    def test_same_request_lock_serializes_but_other_request_proceeds(self):
        trying = threading.Event()
        acquired = threading.Event()

        def contender():
            other_store = ArtifactStore(self.root)
            trying.set()
            with other_store.request_lock(REQUEST_A):
                acquired.set()

        with ThreadPoolExecutor(max_workers=1) as executor:
            with self.store.request_lock(REQUEST_A):
                future = executor.submit(contender)
                self.assertTrue(trying.wait(2))
                self.assertFalse(acquired.wait(0.1))
                with self.store.request_lock(REQUEST_B):
                    self.store.stage(self.source, REQUEST_B)
            future.result(timeout=2)
            self.assertTrue(acquired.is_set())

    def test_doctor_is_read_only_for_missing_root_and_rejects_symlink_root(self):
        diagnosis = self.store.doctor()
        self.assertFalse(diagnosis["exists"])
        self.assertFalse(self.root.exists())
        self.root.symlink_to(self.base, target_is_directory=True)
        self.assertFalse(self.store.doctor()["ready"])
        self.assertEqual(self.content, self.source.read_bytes())

    def test_doctor_checks_effective_write_and_search_permissions_without_changes(self):
        self.root.mkdir(mode=0o700)
        self.assertTrue(self.store.doctor()["ready"])
        for mode in (0o500, 0o600):
            with self.subTest(mode=oct(mode)):
                self.root.chmod(mode)
                try:
                    expected_access = os.access(self.root, os.W_OK | os.X_OK, effective_ids=True)
                    report = self.store.doctor()
                    self.assertEqual(expected_access, report["ready"])
                    if not expected_access:
                        self.assertEqual("storage_permission_denied", report["error_code"])
                    self.assertEqual(mode, self.root.stat().st_mode & 0o777)
                    self.assertEqual([], list(self.root.iterdir()))
                finally:
                    self.root.chmod(0o700)

    def test_doctor_checks_existing_managed_subdirectory_permissions(self):
        staging = self.root / "staging"
        staging.mkdir(parents=True)
        staging.chmod(0o500)
        try:
            expected_access = os.access(staging, os.W_OK | os.X_OK, effective_ids=True)
            self.assertEqual(expected_access, self.store.doctor()["ready"])
            self.assertEqual([], list(staging.iterdir()))
        finally:
            staging.chmod(0o700)

    def test_doctor_rejects_read_only_filesystem_even_when_access_checks_pass(self):
        self.root.mkdir()
        # Simulates the mount flag only; permission checks above use the real filesystem.
        with patch("palimpsest.artifact_store.os.fstatvfs", return_value=SimpleNamespace(f_flag=os.ST_RDONLY)):
            with patch("palimpsest.artifact_store.os.access", return_value=True):
                report = self.store.doctor()
        self.assertFalse(report["ready"])
        self.assertEqual("storage_read_only", report["error_code"])
        self.assertTrue(report["read_only_filesystem"])
        self.assertEqual([], list(self.root.iterdir()))


if __name__ == "__main__":
    unittest.main()
