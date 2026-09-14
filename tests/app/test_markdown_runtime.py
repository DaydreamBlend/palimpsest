"""Real Markdown D/D2I/I persistence in an explicitly disposable PostgreSQL DB.

Fixtures use unique UTF-8 bytes and a private Artifact Store. This suite never
migrates, resets or deletes database history, and never fetches linked sources.
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import tempfile
from threading import Barrier
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from palimpsest import cli
from palimpsest.artifact_store import ArtifactStore
from palimpsest.canonical_store import PostgresRepository
from palimpsest.compiler_runtime import CompilerRuntime, digest
from palimpsest.errors import PalimpsestError
from palimpsest.service import DataService


@unittest.skipUnless(os.environ.get("PALIMPSEST_TEST_DSN"),
                     "Requires explicitly provisioned PALIMPSEST_TEST_DSN")
class MarkdownRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["PALIMPSEST_TEST_DSN"]
        with psycopg.connect(cls.dsn) as conn:
            if int(conn.execute("SHOW server_version_num").fetchone()[0]) // 10000 != 18:
                raise RuntimeError("Markdown integration requires PostgreSQL 18")
            if not conn.execute("SELECT 1 FROM pg_extension WHERE extname='vector'").fetchone():
                raise RuntimeError("Provision pgvector before Markdown integration tests")
            if not conn.execute("SELECT 1 FROM compiler_runtime.schema_migrations "
                                "WHERE version='0004_text_groundings'").fetchone():
                raise RuntimeError("Provision the reviewed 0004_text_groundings migration first")

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="palimpsest-markdown-integration-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "artifacts"
        self.source = self.base / "source.md"
        self.raw = ("\ufeff# 문서\r\n\r\n## 소개\r\n"
                    f"고유 원문 {uuid4()} — μ² Cafe\u0301 😀\r\n\r\n"
                    "```powershell\r\n# This is source code, not a heading\r\n"
                    "Remove-Item 'not-to-be-executed'\r\n```\r\n\r\n"
                    "## 결과\r\n| 값 | 단위 |\r\n| --- | --- |\r\n| 3 | μm |\r\n\r\n"
                    "![참조](../unregistered.png)\r\n\r\n## 결론\r\n마지막 원문.\r\n").encode("utf-8")
        self.source.write_bytes(self.raw)
        self.data_id = sha256(self.raw).hexdigest()
        self.repository = PostgresRepository(self.dsn)
        self.store = ArtifactStore(self.root)
        self.service = DataService(self.repository, self.store, actor_ref="local")
        self.runtime = CompilerRuntime(self.dsn, self.root)

    def _register(self):
        return self.service.import_file(self.source, media_type="text/markdown")

    def _row(self, query, parameters=()):
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            return conn.execute(query, parameters).fetchone()

    def _counts(self, execution_id):
        return self._row("""SELECT
            (SELECT count(*) FROM compiler_runtime.records WHERE execution_id=%s) AS records,
            (SELECT count(*) FROM compiler_runtime.temporary_candidates c JOIN compiler_runtime.records r
                USING(record_id) WHERE r.execution_id=%s) AS candidates,
            (SELECT count(*) FROM canonical_store.information i JOIN compiler_runtime.records r
                ON r.record_id=i.origin_record_id WHERE r.execution_id=%s) AS information,
            (SELECT count(*) FROM canonical_store.information_groundings g JOIN canonical_store.information i
                USING(information_id) JOIN compiler_runtime.records r ON r.record_id=i.origin_record_id
                WHERE r.execution_id=%s) AS groundings,
            (SELECT count(*) FROM compiler_runtime.outbox o JOIN compiler_runtime.records r
                USING(record_id) WHERE r.execution_id=%s) AS outbox""", (execution_id,) * 5)

    def _assert_error(self, code, action):
        with self.assertRaises(PalimpsestError) as caught:
            action()
        self.assertEqual(code, caught.exception.code)

    def _interrupt(self):
        def crash(stage):
            self.assertEqual("before_commit", stage)
            raise RuntimeError("injected Markdown commit failure")
        with self.assertRaisesRegex(RuntimeError, "injected Markdown commit failure"):
            self.runtime.compile_markdown(self.data_id, checkpoint=crash)
        return self._row("SELECT execution_id FROM compiler_runtime.operation_executions "
                         "WHERE data_id=%s", (self.data_id,))["execution_id"]

    def test_registered_markdown_preserves_groups_ranges_receipts_and_i_only_input(self):
        registered = self._register()
        result = self.runtime.compile_markdown(self.data_id)
        execution_id = result["execution_id"]
        self.assertEqual(result["state"], "completed")
        self.assertEqual(result["source_algorithm"], "markdown-groups-v1")
        self.assertEqual((result["llm_calls"], result["ocr_calls"]), (0, 0))
        self.assertEqual(self.store.read(self.data_id, len(self.raw)), self.raw)
        self.assertEqual(self._counts(execution_id),
                         {"records": 3, "candidates": 0, "information": 3, "groundings": 3, "outbox": 3})
        job = self.runtime.show(execution_id, include_input=True)
        self.assertEqual([event["state"] for event in job["events"]], ["prepared", "parsed", "proposed", "completed"])
        parsed = job["parse"]
        self.assertEqual(parsed["bundle"]["pages"], [])
        for role in ("generator", "validator"):
            receipt = job[role + "_receipt"]
            self.assertEqual(receipt["receipt_kind"], "deterministic_source_check")
            self.assertEqual(receipt["checks"]["version"], "markdown-groups-v1")
            self.assertEqual(receipt["llm_calls"], 0)
        rows = self.runtime.information(data_id=self.data_id)["information"]
        rows.sort(key=lambda row: row["payload"]["source_blocks"][0]["text_range"]["byte_start"])
        self.assertEqual([row["title"] for row in rows], ["소개", "결과", "결론"])
        self.assertEqual("".join(row["content"] for row in rows).encode("utf-8"), self.raw)
        for row in rows:
            self.assertEqual(UUID(str(row["information_id"])).version, 7)
            self.assertEqual(row["kind"], "text")
            self.assertIsNone(row["semantic_type"])
            payload = row["payload"]
            self.assertEqual(payload["source_bundle_sha256"], digest(parsed["bundle"]))
            self.assertEqual(payload["parse_manifest_sha256"], parsed["manifest_hash"])
            self.assertFalse(payload["semantic_checked"])
            self.assertEqual(payload["source_artifacts"], {})
            block, = payload["source_blocks"]
            grounding, = row["groundings"]
            self.assertEqual(grounding["locator_type"], "text_range")
            self.assertEqual(grounding["text_range"], block["text_range"])
            self.assertEqual(grounding["data_id"], registered["data_id"])
            for key in ("page_index", "bbox", "page_size"):
                self.assertIsNone(grounding[key])
            source_range = grounding["text_range"]
            self.assertEqual(self.raw[source_range["byte_start"]:source_range["byte_end"]],
                             row["content"].encode("utf-8"))
        before = self._counts(execution_id)
        packet = self.runtime.prepare_input(execution_id)
        self.assertEqual("".join(unit["content"] for unit in packet["model_input"]["information"]).encode("utf-8"), self.raw)
        self.assertEqual(packet["page_count"], 0)
        self.assertFalse(packet["actual_delivery"])
        self.assertFalse(packet["model_input"]["original_pdf_request_supported"])
        self.assertEqual(packet["media_assets"], [])
        references = []
        for unit in packet["model_input"]["information"]:
            self.assertEqual(unit["media"], [])
            for ref in unit["source_refs"]:
                self.assertEqual(ref["locator_type"], "text_range")
                self.assertNotIn("page_index", ref)
                self.assertNotIn("bbox", ref)
                self.assertIn("grounding_id", ref)
                references.extend(ref["referenced_images"])
        self.assertEqual(len(references), 1)
        self.assertEqual(references[0]["url"], "../unregistered.png")
        self.assertFalse(references[0]["fetched"])
        self._assert_error("pdf_page_view_required", lambda: self.runtime.page_view(execution_id))
        request = {"schema_version": "i2k-source-request-v1", "input_sha256": packet["input_sha256"],
                   "information_ids": packet["target_information_ids"][:1], "question": "원문 확인", "page_numbers": []}
        self._assert_error("original_pdf_required", lambda: self.runtime.prepare_source(execution_id, request))
        self.assertEqual(before, self._counts(execution_id))

    def test_compile_retries_and_two_simultaneous_requests_reuse_same_ids(self):
        registered = self._register()
        barrier = Barrier(2)
        def run(_):
            barrier.wait(timeout=10)
            return CompilerRuntime(self.dsn, self.root).compile_markdown(self.data_id)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, range(2)))
        self.assertEqual(results[0]["execution_id"], results[1]["execution_id"])
        self.assertEqual(results[0]["information_ids"], results[1]["information_ids"])
        replay = self.runtime.compile_markdown(self.data_id)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["information_ids"], results[0]["information_ids"])
        self.assertEqual(self.runtime.materialize_source(replay["execution_id"])["information_ids"], replay["information_ids"])
        self._assert_error("duplicate_data", self._register)
        data_replay = self.service.import_file(self.source, media_type="text/markdown", request_id=registered["request_id"])
        self.assertTrue(data_replay["replayed"])
        self.assertEqual(data_replay["acquisition_id"], registered["acquisition_id"])
        self.assertEqual(self._counts(replay["execution_id"]),
                         {"records": 3, "candidates": 0, "information": 3, "groundings": 3, "outbox": 3})
        self.assertEqual(self._row("SELECT count(*) AS count FROM canonical_store.data_acquisitions WHERE data_id=%s",
                                   (self.data_id,))["count"], 1)

    def test_commit_failure_rolls_back_all_canonical_effects_and_retries_records(self):
        self._register()
        execution_id = self._interrupt()
        before = self.runtime.show(execution_id, include_input=True)
        self.assertEqual(before["state"], "proposed")
        self.assertIsNone(before["validator_receipt"])
        self.assertEqual(self._counts(execution_id),
                         {"records": 3, "candidates": 3, "information": 0, "groundings": 0, "outbox": 0})
        result = self.runtime.materialize_source(execution_id)
        self.assertEqual(result["state"], "completed")
        after = self.runtime.show(execution_id)
        self.assertEqual([record["record_id"] for record in before["records"]],
                         [record["record_id"] for record in after["records"]])
        self.assertEqual(self._counts(execution_id),
                         {"records": 3, "candidates": 0, "information": 3, "groundings": 3, "outbox": 3})

    def test_database_grounding_guard_rejects_changed_ranges_without_committing_probes(self):
        self._register()
        execution_id = self._interrupt()
        job = self.runtime.show(execution_id, include_input=True)
        record, proposal, parsed = job["records"][0], job["proposals"][0], job["parse"]
        original = parsed["bundle"]["blocks"][0]
        payload = {"schema_version": "source-information-v1", "validation_basis": "source_structure",
                   "semantic_checked": False, "empty_content": False, "source_blocks": [original]}
        def insert_information(conn):
            return conn.execute("""INSERT INTO canonical_store.information
                (data_id,origin_record_id,kind,semantic_type,unit_type,title,content,payload,identity_fingerprint,content_fingerprint)
                VALUES (%s,%s,'text',NULL,'text',%s,%s,%s,%s,%s) RETURNING information_id""",
                (self.data_id, record["record_id"], proposal["title"], proposal["content"], Jsonb(payload),
                 record["identity_fingerprint"], record["content_fingerprint"])).fetchone()[0]
        def insert_grounding(conn, identifier, block):
            conn.execute("""INSERT INTO canonical_store.information_groundings
                (information_id,data_id,parse_artifact_id,block_id,page_index,bbox,page_size,raw_locator,
                 anchor_sha256,locator_type,text_range) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (identifier, self.data_id, parsed["parse_artifact_id"], block["block_id"], block["page_index"],
                 Jsonb(block["bbox"]) if block["bbox"] is not None else None,
                 Jsonb(block["page_size"]) if block["page_size"] is not None else None,
                 block["raw_locator"], block["anchor_sha256"], block["locator_type"], Jsonb(block["text_range"])))
        with psycopg.connect(self.dsn) as conn:
            try:
                identifier = insert_information(conn)
                insert_grounding(conn, identifier, original)  # A matching pending grounding really is insertable.
                self.assertEqual(conn.execute("SELECT count(*) FROM canonical_store.information_groundings "
                                              "WHERE information_id=%s", (identifier,)).fetchone()[0], 1)
            finally:
                conn.rollback()
        for field in ("byte_end", "char_end", "line_end", "locator_type", "page_index", "bool_offset"):
            changed = deepcopy(original)
            if field in ("byte_end", "char_end", "line_end"):
                changed["text_range"][field] += 1
            elif field == "bool_offset":
                changed["text_range"]["char_start"] = False
            elif field == "locator_type":
                changed[field] = "pdf_region"
            else:
                changed[field] = 0
            with self.subTest(field=field), psycopg.connect(self.dsn) as conn:
                try:
                    identifier = insert_information(conn)
                    # Assert the INSERT itself fails, not a later incomplete-commit constraint.
                    with self.assertRaises(psycopg.Error):
                        insert_grounding(conn, identifier, changed)
                finally:
                    conn.rollback()
        self.assertEqual(self._counts(execution_id),
                         {"records": 3, "candidates": 3, "information": 0, "groundings": 0, "outbox": 0})

    def test_input_rejects_altered_canonical_ranges_and_corrupt_registered_bytes(self):
        self._register()
        execution_id = self.runtime.compile_markdown(self.data_id)["execution_id"]
        before = self._counts(execution_id)
        snapshot = self.runtime._source_snapshot(execution_id)
        changed = deepcopy(snapshot)
        changed[2][0]["payload"]["source_blocks"][0]["text_range"]["char_end"] += 1
        with patch.object(self.runtime, "_source_snapshot", return_value=changed):
            self._assert_error("input_grounding_mismatch", lambda: self.runtime.prepare_input(execution_id))
        artifact = self.root / self.repository.get_data(self.data_id)["artifact_path"]
        old_mode = artifact.stat().st_mode
        try:
            artifact.chmod(0o600)
            artifact.write_bytes(bytes([self.raw[0] ^ 1]) + self.raw[1:])
            self._assert_error("integrity_conflict", lambda: self.runtime.prepare_input(execution_id))
        finally:
            artifact.write_bytes(self.raw)
            artifact.chmod(old_mode)
        self.assertEqual(self.runtime.prepare_input(execution_id)["state"], "prepared_not_delivered")
        self.assertEqual(before, self._counts(execution_id))

    def test_cli_import_compile_input_and_duplicate_errors_are_structured(self):
        environment = {"PALIMPSEST_DATABASE_DSN": self.dsn, "PALIMPSEST_ARTIFACT_ROOT": str(self.root)}
        def invoke(arguments):
            output, errors = io.StringIO(), io.StringIO()
            with patch.dict(os.environ, environment, clear=True), redirect_stdout(output), redirect_stderr(errors):
                code = cli.main([*arguments, "--json", "--non-interactive"])
            return code, json.loads(output.getvalue())
        code, envelope = invoke(["data", "import", str(self.source), "--media-type", "text/markdown"])
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["result"]["data_id"], self.data_id)
        code, envelope = invoke(["compile", "markdown", self.data_id])
        self.assertEqual(code, 0, envelope)
        result = envelope["result"]
        self.assertEqual(result["state"], "completed")
        self.assertEqual(len(result["information_ids"]), 3)
        code, envelope = invoke(["compile", "markdown", self.data_id])
        self.assertEqual(code, 0, envelope)
        self.assertTrue(envelope["result"]["replayed"])
        self.assertEqual(envelope["result"]["information_ids"], result["information_ids"])
        code, envelope = invoke(["information", "prepare-input", "--execution-id", result["execution_id"]])
        self.assertEqual(code, 0, envelope)
        self.assertEqual(len(envelope["result"]["model_input"]["information"]), 3)
        code, envelope = invoke(["data", "import", str(self.source), "--media-type", "text/markdown"])
        self.assertNotEqual(code, 0)
        self.assertEqual(envelope["error"]["code"], "duplicate_data")
        self.assertEqual(envelope["command_status"], "failed")


if __name__ == "__main__":
    unittest.main()
