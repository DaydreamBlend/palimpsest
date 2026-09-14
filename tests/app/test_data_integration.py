"""T02 integration checks against an explicitly provisioned disposable PG18 DB.

The suite never resets, truncates, deletes, or migrates database records. Each
case uses unique bytes and a private temporary Artifact Store. The caller owns
database provisioning and disposal; PALIMPSEST_TEST_DSN must not be a live DB.
"""

from hashlib import sha256
import multiprocessing
import os
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from palimpsest.artifact_store import ArtifactStore
from palimpsest.canonical_store import PostgresRepository
from palimpsest.errors import PalimpsestError
from palimpsest.service import DataService


def _import_child(dsn, root, source, request_id, results, *, crash_at=None,
                  start_barrier=None, prepared_barrier=None):
    """Fresh process/connection: a real crash cannot be caught by the service."""
    def checkpoint(name, current_request):
        if name == crash_at:
            os._exit(77)
        if name == "after_prepare" and prepared_barrier is not None:
            prepared_barrier.wait(timeout=15)

    service = DataService(PostgresRepository(dsn), ArtifactStore(Path(root)),
                          actor_ref="local", checkpoint=checkpoint)
    try:
        if start_barrier is not None:
            start_barrier.wait(timeout=15)
        result = service.import_file(Path(source), request_id=request_id,
                                     media_type="application/pdf")
        results.put({"kind": "success", "result": result})
    except PalimpsestError as error:
        results.put({"kind": "error", "code": error.code})
    except Exception as error:
        results.put({"kind": "unexpected", "type": type(error).__name__})
        raise


@unittest.skipUnless(os.environ.get("PALIMPSEST_TEST_DSN"),
                     "Requires explicitly provisioned PALIMPSEST_TEST_DSN")
class DataIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["PALIMPSEST_TEST_DSN"]
        with psycopg.connect(cls.dsn) as connection:
            version = int(connection.execute("SHOW server_version_num").fetchone()[0])
            if version // 10000 != 18:
                raise RuntimeError("T02 integration profile requires PostgreSQL 18")
            if connection.execute(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            ).fetchone() is None:
                raise RuntimeError("Provision the vector extension before running tests")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="palimpsest-t02-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "artifacts"
        self.payload = b"%PDF-1.7\nPalimpsest integration fixture\n" + uuid4().bytes
        self.source = self.base / "논문 원본.pdf"
        self.source.write_bytes(self.payload)
        self.data_id = sha256(self.payload).hexdigest()
        self.repository = PostgresRepository(self.dsn)
        self.service = DataService(self.repository, ArtifactStore(self.root), actor_ref="local")
        self.process_context = multiprocessing.get_context("spawn")

    def _import(self, **kwargs):
        return self.service.import_file(self.source, media_type="application/pdf", **kwargs)

    def _row(self, query, parameters):
        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            return connection.execute(query, parameters).fetchone()

    def _counts(self):
        return self._row(
            "SELECT (SELECT count(*) FROM canonical_store.data WHERE data_id = %s) AS data, "
            "(SELECT count(*) FROM canonical_store.data_acquisitions WHERE data_id = %s) AS acquisitions",
            (self.data_id, self.data_id),
        )

    def _request(self, request_id):
        return self._row(
            "SELECT * FROM compiler_runtime.data_import_requests WHERE request_id = %s",
            (request_id,),
        )

    def _assert_error(self, code, action):
        with self.assertRaises(PalimpsestError) as caught:
            action()
        self.assertEqual(caught.exception.code, code)
        self.assertNotEqual(caught.exception.exit_code, 0)
        return caught.exception

    def _artifact(self):
        row = self._row("SELECT artifact_path FROM canonical_store.data WHERE data_id = %s",
                        (self.data_id,))
        return self.root / row["artifact_path"]

    def _start_child(self, request_id, results, **kwargs):
        process = self.process_context.Process(
            target=_import_child,
            args=(self.dsn, str(self.root), str(self.source), request_id, results),
            kwargs=kwargs,
        )
        process.start()
        self.addCleanup(self._stop_child, process)
        return process

    @staticmethod
    def _stop_child(process):
        if process.is_alive():
            process.terminate()
        process.join(timeout=5)

    def _finish_child(self, process, expected_exit=0):
        process.join(timeout=25)
        self.assertFalse(process.is_alive(), "Import child did not terminate; possible lock deadlock")
        self.assertEqual(process.exitcode, expected_exit)

    def _child_result(self, results):
        try:
            return results.get(timeout=5)
        except queue.Empty:
            self.fail("Import child returned no result")

    def _crash(self, checkpoint):
        request_id = self.repository.allocate_id()
        results = self.process_context.Queue()
        self.addCleanup(results.close)
        process = self._start_child(request_id, results, crash_at=checkpoint)
        self._finish_child(process, expected_exit=77)
        return request_id

    def _assert_registered(self, result):
        self.assertEqual(str(result["data_id"]), self.data_id)
        self.assertEqual(result["state"], "committed")
        self.assertEqual(UUID(str(result["request_id"])).version, 7)
        self.assertEqual(UUID(str(result["acquisition_id"])).version, 7)
        self.assertEqual(self._artifact().read_bytes(), self.payload)
        self.assertEqual(self._counts(), {"data": 1, "acquisitions": 1})

    def test_registration_preserves_bytes_and_exposes_readable_metadata(self):
        allocated = []
        result = self._import(on_request_id=allocated.append)
        self._assert_registered(result)
        self.assertEqual([str(value) for value in allocated], [str(result["request_id"])])
        self.assertFalse(result["replayed"])
        self.assertEqual(self.source.read_bytes(), self.payload)
        shown = self.service.show(self.data_id)
        self.assertEqual(shown["data_id"], self.data_id)
        self.assertEqual(shown["sha256"], self.data_id)
        self.assertEqual(shown["byte_size"], len(self.payload))
        verified = self.service.verify(self.data_id)
        self.assertTrue(verified["verified"])
        self.assertEqual(verified["byte_size"], len(self.payload))
        # Changing a user's original after registration cannot mutate stored D.
        self.source.write_bytes(b"changed source after successful import")
        self.assertEqual(self._artifact().read_bytes(), self.payload)
        self.service.verify(self.data_id)

    def test_doctor_reports_storage_readiness_and_unconfigured_parser(self):
        self.root.mkdir()
        report = self.service.doctor()
        self.assertTrue(report["ready"])
        self.assertIsInstance(report["database"], dict)
        self.assertIsInstance(report["artifact_store"], dict)
        self.assertEqual(report["parser"]["name"], "MinerU Hybrid + Pro high")
        self.assertFalse(report["parser"]["ready"])
        self.assertEqual(report["parser"]["status"], "not_probed")

    def test_changed_original_registers_new_data_without_mutating_old_snapshot(self):
        """AT67: changed bytes submitted as a new request become a separate D."""
        original = self._import()
        old_snapshot = self.service.show(self.data_id)
        changed_payload = self.payload + b"revised original bytes"
        changed_id = sha256(changed_payload).hexdigest()
        self.source.write_bytes(changed_payload)
        registered = self._import()
        self.assertEqual(registered["state"], "committed")
        self.assertEqual(registered["data_id"], changed_id)
        self.assertNotEqual(registered["data_id"], original["data_id"])
        self.assertNotEqual(registered["request_id"], original["request_id"])
        self.assertNotEqual(registered["acquisition_id"], original["acquisition_id"])
        self.assertEqual(self.service.show(self.data_id), old_snapshot)
        self.assertEqual(self._artifact().read_bytes(), self.payload)
        new_snapshot = self.service.show(changed_id)
        self.assertEqual((self.root / new_snapshot["artifact_path"]).read_bytes(), changed_payload)
        self.assertEqual(self.source.read_bytes(), changed_payload)
        self.assertTrue(self.service.verify(self.data_id)["verified"])
        self.assertTrue(self.service.verify(changed_id)["verified"])
        self.assertEqual(self._counts(), {"data": 1, "acquisitions": 1})
        self.assertEqual(len(new_snapshot["acquisitions"]), 1)

    def test_explicit_acquisition_insert_is_visible_without_duplicate_import_side_effects(self):
        """AT70 storage+show coverage; a separate acquisition CLI is not implemented."""
        original = self._import(origin_uri="publisher:example")
        # This deliberate provenance INSERT uses the configured runtime DB role;
        # no append-only record is updated/deleted and no CLI feature is simulated.
        with psycopg.connect(self.dsn) as connection:
            acquisition_id = connection.execute(
                "INSERT INTO canonical_store.data_acquisitions "
                "(data_id, origin_uri, import_method, actor_ref) "
                "VALUES (%s, %s, %s, %s) RETURNING acquisition_id",
                (self.data_id, "email:example", "explicit_provenance", "local"),
            ).fetchone()[0]
        self.assertEqual(UUID(str(acquisition_id)).version, 7)
        self.assertNotEqual(str(acquisition_id), str(original["acquisition_id"]))
        acquisitions = self.service.show(self.data_id)["acquisitions"]
        self.assertCountEqual([item["origin_uri"] for item in acquisitions],
                              ["publisher:example", "email:example"])
        self._assert_error("duplicate_data", self._import)
        self.assertEqual(self._counts(), {"data": 1, "acquisitions": 2})
        self.assertEqual(self.service.show(self.data_id)["acquisitions"], acquisitions)
        self.assertEqual(self._artifact().read_bytes(), self.payload)

    def test_new_duplicate_request_does_not_add_data_or_acquisition(self):
        original = self._import()
        request_id = self.repository.allocate_id()
        self._assert_error("duplicate_data", lambda: self._import(request_id=request_id))
        self.assertEqual(self._counts(), {"data": 1, "acquisitions": 1})
        receipt = self._request(request_id)
        self.assertEqual(receipt["state"], "duplicate")
        self.assertEqual(receipt["result_data_id"], self.data_id)
        self.assertIsNone(receipt["result_acquisition_id"])
        self.assertEqual(self.source.read_bytes(), self.payload)
        self.assertEqual(self._request(original["request_id"])["state"], "committed")

    def test_success_retry_replays_receipt_but_changed_command_conflicts(self):
        original = self._import()
        replay = self._import(request_id=original["request_id"])
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["acquisition_id"], original["acquisition_id"])
        self._assert_error("idempotency_conflict", lambda: self._import(
            request_id=original["request_id"], origin_uri="changed:origin"))
        self.source.write_bytes(self.payload + b"new bytes")
        self._assert_error("idempotency_conflict", lambda: self._import(request_id=original["request_id"]))
        self._assert_registered(original)

    def test_wrong_bytes_retry_cannot_poison_later_success_replay(self):
        original = self._import()
        receipt = self._request(original["request_id"])
        self.source.write_bytes(self.payload + b"wrong retry bytes")
        self._assert_error("idempotency_conflict", lambda: self._import(request_id=original["request_id"]))
        self.source.write_bytes(self.payload)
        replay = self._import(request_id=original["request_id"])
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["acquisition_id"], original["acquisition_id"])
        self.assertEqual(self._request(original["request_id"]), receipt)
        self._assert_registered(replay)

    def test_service_rejects_canonical_size_mismatch_from_repository_stub(self):
        """Service fault injection only; never corrupt the append-only DB fixture."""
        self._import()
        actual = self.repository.get_data(self.data_id)
        inconsistent = {**actual, "byte_size": actual["byte_size"] + 1}
        with patch.object(self.repository, "get_data", return_value=inconsistent):
            self._assert_error("integrity_conflict", self._import)
        self.assertEqual(self.repository.get_data(self.data_id), actual)
        self.assertEqual(self._counts(), {"data": 1, "acquisitions": 1})
        self.assertTrue(self.service.verify(self.data_id)["verified"])

    def test_missing_artifact_is_not_reported_as_valid_or_normal_duplicate(self):
        self._import()
        self._artifact().unlink()
        self._assert_error("artifact_missing", lambda: self.service.verify(self.data_id))
        self._assert_error("artifact_missing", self._import)
        self.assertEqual(self._counts(), {"data": 1, "acquisitions": 1})

    def test_corrupt_artifact_is_not_reported_as_valid_or_normal_duplicate(self):
        self._import()
        artifact = self._artifact()
        artifact.chmod(0o600)
        artifact.write_bytes(b"corruption" + self.payload[10:])
        self._assert_error("integrity_conflict", lambda: self.service.verify(self.data_id))
        self._assert_error("integrity_conflict", self._import)
        self.assertEqual(self._counts(), {"data": 1, "acquisitions": 1})

    def test_request_status_and_recovery_require_original_actor(self):
        request_id = self._crash("after_prepare")
        other = DataService(PostgresRepository(self.dsn), ArtifactStore(self.root), actor_ref="other")
        self._assert_error("permission_denied", lambda: other.request_status(request_id))
        self._assert_error("permission_denied", lambda: other.recover(request_id))
        self.assertEqual(self._counts(), {"data": 0, "acquisitions": 0})
        self.assertEqual(self.service.request_status(request_id)["state"], "staged")
        self._assert_registered(self.service.recover(request_id))

    def test_two_requests_race_for_same_content_and_only_one_registers(self):
        results = self.process_context.Queue()
        self.addCleanup(results.close)
        barrier = self.process_context.Barrier(2)
        requests = [self.repository.allocate_id(), self.repository.allocate_id()]
        processes = [self._start_child(request_id, results, prepared_barrier=barrier)
                     for request_id in requests]
        for process in processes:
            self._finish_child(process)
        outcomes = [self._child_result(results), self._child_result(results)]
        self.assertCountEqual([item["kind"] for item in outcomes], ["success", "error"])
        success = next(item["result"] for item in outcomes if item["kind"] == "success")
        self.assertEqual(next(item["code"] for item in outcomes if item["kind"] == "error"), "duplicate_data")
        self._assert_registered(success)
        self.assertCountEqual([self._request(value)["state"] for value in requests], ["committed", "duplicate"])

    def test_same_request_race_returns_one_receipt_and_one_replay(self):
        request_id = self.repository.allocate_id()
        results = self.process_context.Queue()
        self.addCleanup(results.close)
        barrier = self.process_context.Barrier(2)
        processes = [self._start_child(request_id, results, start_barrier=barrier) for _ in range(2)]
        for process in processes:
            self._finish_child(process)
        outcomes = [self._child_result(results), self._child_result(results)]
        self.assertEqual([item["kind"] for item in outcomes], ["success", "success"])
        receipts = [item["result"] for item in outcomes]
        self.assertEqual(receipts[0]["acquisition_id"], receipts[1]["acquisition_id"])
        self.assertCountEqual([item["replayed"] for item in receipts], [False, True])
        self._assert_registered(receipts[0])

    def test_crash_after_prepare_recovers_without_original_source(self):
        request_id = self._crash("after_prepare")
        self.assertEqual(self._request(request_id)["state"], "staged")
        self.assertEqual(self._counts(), {"data": 0, "acquisitions": 0})
        self.source.unlink()
        self._assert_registered(self.service.recover(request_id))

    def test_crash_after_publish_recovers_one_registration_without_source(self):
        request_id = self._crash("after_publish")
        self.assertIn(self._request(request_id)["state"], ("staged", "published"))
        self.assertEqual(self._counts(), {"data": 0, "acquisitions": 0})
        self.source.unlink()
        self._assert_registered(self.service.recover(request_id))
        self.assertTrue(self.service.recover(request_id)["replayed"])

    def test_crash_after_commit_recovers_durable_success_receipt(self):
        request_id = self._crash("after_commit")
        before = self._request(request_id)
        self.assertEqual(before["state"], "committed")
        self.source.unlink()
        recovered = self.service.recover(request_id)
        self._assert_registered(recovered)
        self.assertTrue(recovered["replayed"])
        self.assertEqual(str(recovered["acquisition_id"]), str(before["result_acquisition_id"]))

    def test_crash_before_journal_requires_original_request_resubmission(self):
        request_id = self._crash("after_stage")
        self.assertIsNone(self._request(request_id))
        self.assertEqual(self._counts(), {"data": 0, "acquisitions": 0})
        self._assert_error("request_not_found", lambda: self.service.recover(request_id))
        self.assertEqual(self.source.read_bytes(), self.payload)
        self._assert_registered(self._import(request_id=request_id))

    def test_changed_original_cannot_replace_prepared_payload_during_retry(self):
        request_id = self._crash("after_prepare")
        prepared = self._request(request_id)
        self.source.write_bytes(self.payload + b"changed during interrupted import")
        self._assert_error("idempotency_conflict", lambda: self._import(request_id=request_id))
        self.assertEqual(self._request(request_id)["request_fingerprint"], prepared["request_fingerprint"])
        self._assert_registered(self.service.recover(request_id))


if __name__ == "__main__":
    unittest.main()
