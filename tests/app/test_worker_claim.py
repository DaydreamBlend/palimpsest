"""Real PG18 sessions/processes; no provider or parser is invoked.

The caller provisions PALIMPSEST_TEST_DSN and the reviewed migrations in a
dedicated test database. Fixtures append unique data and execution history;
this suite never resets, deletes, truncates, or migrates database tables.
"""

import io
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
from time import monotonic, sleep
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

import psycopg

from palimpsest.artifact_store import ArtifactStore
from palimpsest.canonical_store import PostgresRepository
from palimpsest.compiler_runtime import CompilerRuntime
from palimpsest.source_units import SOURCE_UNITS_VERSION
from palimpsest.information import SOURCE_SCHEMA_VERSION
from palimpsest.errors import PalimpsestError
from palimpsest.service import DataService
from palimpsest.worker_claim import CLAIM_SEED, hold_claim


_CHILD = """
import json, os, sys
from palimpsest.errors import PalimpsestError
from palimpsest.worker_claim import hold_claim
try:
    hold_claim(os.environ['PALIMPSEST_TEST_DSN'], sys.argv[1],
               lambda: print(json.dumps({'acquired': True}), flush=True))
except PalimpsestError as exc:
    print(json.dumps({'error': exc.code, 'exit_code': exc.exit_code}), flush=True)
    raise SystemExit(exc.exit_code)
print(json.dumps({'released': True}), flush=True)
"""


@unittest.skipUnless(os.environ.get("PALIMPSEST_TEST_DSN"),
                     "Requires explicitly provisioned disposable PG18 test database")
class WorkerClaimIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["PALIMPSEST_TEST_DSN"]
        with psycopg.connect(cls.dsn) as conn:
            if int(conn.execute("SHOW server_version_num").fetchone()[0]) // 10000 != 18:
                raise RuntimeError("Worker claim tests require PostgreSQL 18")
            if not conn.execute("SELECT 1 FROM compiler_runtime.schema_migrations WHERE version='0002_information'").fetchone():
                raise RuntimeError("Provision the reviewed T03 migration before testing")

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="palim-worker-claim-")
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        root = base / "artifacts"
        source = base / "source.pdf"
        source.write_bytes(b"%PDF-1.7\nUnique worker claim fixture, not parsed\n" + uuid4().bytes)
        self.repository = PostgresRepository(self.dsn)
        registered = DataService(self.repository, ArtifactStore(root), actor_ref="local").import_file(
            source, media_type="application/pdf")
        self.data_id = registered["data_id"]
        self.runtime = CompilerRuntime(self.dsn, root)
        self.profile = {
            "schema_version": "source-d2i-v1",
            "parser": {"provider": "mineru", "version": "3.4.5", "backend": "pipeline",
                       "image_digest": "sha256:" + "a" * 64, "models_manifest_sha256": "b" * 64},
            "transformation": {"algorithm": SOURCE_UNITS_VERSION, "schema_version": SOURCE_SCHEMA_VERSION},
            "policy": {"fixture": "worker_claim_no_model_calls",
                       "llm_calls": 0, "source_fidelity": "source_preserving", "extraction_scope": "whole_document"},
        }
        self.execution_id = str(self.runtime.start(self.data_id, self.profile)["execution_id"])

    def _start(self, execution_id=None):
        process = subprocess.Popen(
            [sys.executable, "-B", "-c", _CHILD, execution_id or self.execution_id],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env=dict(os.environ),
        )
        self.addCleanup(self._close, process)
        return process

    @staticmethod
    def _close(process):
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        if process.stdout is not None:
            process.stdout.close()

    def _message(self, process):
        # Docker/Linux pipe readiness prevents a broken holder from hanging tests.
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            self.assertTrue(selector.select(timeout=10), "Worker did not acknowledge or fail")
        line = process.stdout.readline()
        self.assertTrue(line, "Worker exited without a response")
        message = json.loads(line)
        self.assertNotIn(self.dsn, line.decode("utf-8"))
        return message

    def _probe(self, execution_id=None):
        with psycopg.connect(self.dsn, autocommit=True) as conn:
            return conn.execute("SELECT pg_try_advisory_lock(hashtextextended(%s,%s))",
                                (execution_id or self.execution_id, CLAIM_SEED)).fetchone()[0]
        # Closing this independent session releases a successfully acquired probe.

    def test_second_process_is_busy_until_first_receives_eof(self):
        owner = self._start()
        self.assertEqual(self._message(owner), {"acquired": True})
        self.assertIsNone(owner.poll())
        self.assertFalse(self._probe())
        contender = self._start()
        self.assertEqual(self._message(contender), {"error": "job_busy", "exit_code": 6})
        self.assertEqual(contender.wait(timeout=5), 6)
        self.assertIsNone(owner.poll())

        owner.stdin.close()
        self.assertEqual(self._message(owner), {"released": True})
        self.assertEqual(owner.wait(timeout=5), 0)
        self.assertTrue(self._probe())
        replacement = self._start()
        self.assertEqual(self._message(replacement), {"acquired": True})

    def test_two_processes_racing_have_exactly_one_owner(self):
        workers = [self._start(), self._start()]
        results = [self._message(worker) for worker in workers]
        self.assertEqual(sum(result.get("acquired", False) for result in results), 1)
        self.assertEqual(sum(result.get("error") == "job_busy" for result in results), 1)
        self.assertFalse(self._probe())

    def test_different_execution_ids_can_be_held_concurrently(self):
        other_id = str(self.runtime.start(self.data_id, self.profile, generation=2)["execution_id"])
        first, second = self._start(), self._start(other_id)
        self.assertEqual(self._message(first), {"acquired": True})
        self.assertEqual(self._message(second), {"acquired": True})
        self.assertFalse(self._probe())
        self.assertFalse(self._probe(other_id))

    def test_callback_exception_releases_claim_without_reading_stdin(self):
        failure = RuntimeError("synthetic callback failure")
        callback = Mock(side_effect=failure)
        source = Mock(fileno=Mock(return_value=0))
        with patch("palimpsest.worker_claim.sys.stdin", source):
            with self.assertRaises(RuntimeError) as caught:
                hold_claim(self.dsn, self.execution_id, callback)
        self.assertIs(caught.exception, failure)
        callback.assert_called_once_with()
        source.fileno.assert_not_called()
        self.assertTrue(self._probe())

    def test_stdin_exception_releases_claim_after_acknowledgment(self):
        failure = OSError("synthetic pipe read failure")
        callback = Mock()
        source = Mock(fileno=Mock(return_value=0))
        with patch("palimpsest.worker_claim.sys.stdin", source), \
                patch("palimpsest.worker_claim.os.read", side_effect=failure):
            with self.assertRaises(OSError) as caught:
                hold_claim(self.dsn, self.execution_id, callback)
        self.assertIs(caught.exception, failure)
        callback.assert_called_once_with()
        self.assertTrue(self._probe())

    def test_killed_owner_releases_postgresql_session_claim(self):
        owner = self._start()
        self.assertEqual(self._message(owner), {"acquired": True})
        self.assertFalse(self._probe())
        owner.kill()
        owner.wait(timeout=5)
        deadline = monotonic() + 5
        while not self._probe():
            if monotonic() >= deadline:
                self.fail("PostgreSQL did not release the killed worker session")
            sleep(0.02)
        replacement = self._start()
        self.assertEqual(self._message(replacement), {"acquired": True})

    def test_lost_database_session_stops_holder_while_stdin_is_still_open(self):
        owner = self._start()
        self.assertEqual(self._message(owner), {"acquired": True})
        with psycopg.connect(self.dsn, autocommit=True) as conn:
            # Find only this test's unique execution lock, not another app session.
            rows = conn.execute("""WITH claim AS (
                SELECT hashtextextended(%s,%s) AS key
            ) SELECT l.pid FROM pg_locks l, claim
              WHERE l.locktype='advisory' AND l.granted AND l.objsubid=1
                AND l.classid=((claim.key >> 32) & 4294967295)::oid
                AND l.objid=(claim.key & 4294967295)::oid
                AND l.database=(SELECT oid FROM pg_database WHERE datname=current_database())""",
                (self.execution_id, CLAIM_SEED)).fetchall()
            self.assertEqual(len(rows), 1)
            self.assertTrue(conn.execute("SELECT pg_terminate_backend(%s)", (rows[0][0],)).fetchone()[0])
        self.assertFalse(owner.stdin.closed)
        self.assertEqual(self._message(owner), {"error": "database_unavailable", "exit_code": 3})
        self.assertEqual(owner.wait(timeout=5), 3)
        replacement = self._start()
        self.assertEqual(self._message(replacement), {"acquired": True})

    def test_invalid_or_missing_execution_never_calls_on_acquired(self):
        for execution_id, code in (("not-uuid", "invalid_request_id"),
                                   (str(uuid4()), "invalid_request_id"),
                                   ("01992d33-1020-7123-0123-123456789abc", "invalid_request_id"),
                                   (self.repository.allocate_id(), "job_not_found")):
            with self.subTest(code=code):
                callback = Mock()
                with patch("palimpsest.worker_claim.sys.stdin", SimpleNamespace(buffer=io.BytesIO())):
                    with self.assertRaises(PalimpsestError) as caught:
                        hold_claim(self.dsn, execution_id, callback)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(caught.exception.exit_code, 2)
                callback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
