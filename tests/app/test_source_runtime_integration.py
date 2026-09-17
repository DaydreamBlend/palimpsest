"""U11 source conversion against an explicitly provisioned disposable PG18 DB.

MinerU blocks, PDF bytes and image bytes below are synthetic storage fixtures.
No parser or provider is invoked. These checks establish persistence contracts,
not visual extraction accuracy. The caller provisions and disposes the test DB;
this module never migrates, truncates or resets existing database history.
"""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import stat
import tempfile
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
from palimpsest.source_units import build_source_units, verify_source_units


@unittest.skipUnless(os.environ.get("PALIMPSEST_TEST_DSN"),
                     "Requires explicitly provisioned PALIMPSEST_TEST_DSN")
class SourceRuntimeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["PALIMPSEST_TEST_DSN"]
        with psycopg.connect(cls.dsn) as conn:
            if int(conn.execute("SHOW server_version_num").fetchone()[0]) // 10000 != 18:
                raise RuntimeError("Source integration profile requires PostgreSQL 18")
            if not conn.execute("SELECT 1 FROM pg_extension WHERE extname='vector'").fetchone():
                raise RuntimeError("Provision pgvector before source integration tests")
            if not conn.execute("SELECT 1 FROM compiler_runtime.schema_migrations "
                                "WHERE version='0003_source_information'").fetchone():
                raise RuntimeError("Provision the reviewed source Information migration first")

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="palimpsest-source-integration-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "artifacts"
        source = self.base / "source.pdf"
        source.write_bytes(b"%PDF-1.7\nSynthetic source persistence fixture\n" + uuid4().bytes)
        self.data_id = sha256(source.read_bytes()).hexdigest()
        DataService(PostgresRepository(self.dsn), ArtifactStore(self.root), actor_ref="local").import_file(
            source, media_type="application/pdf")
        self.runtime = CompilerRuntime(self.dsn, self.root)
        self.directory = self.base / "synthetic-parser-output"
        (self.directory / "images").mkdir(parents=True)
        self.assets = {"logo.png": b"synthetic logo integrity bytes",
                       "panel.png": b"synthetic individual panel integrity bytes",
                       "full-figure.png": b"synthetic complete figure integrity bytes"}
        for name, body in self.assets.items():
            (self.directory / "images" / name).write_bytes(body)
        self.source_text = "  e\u0301 / 숫자 2-9\r\n원문 공백과 Unicode 보존  "
        self.table_html = "<table><tr><td>2-9</td></tr></table>"
        self.equation = r"x = 2 \cdot 9"
        blocks = [
            self._text_block("text", [10, 10, 300, 60], self.source_text),
            {"type": "text", "bbox": [10, 70, 300, 80], "lines": []},
            self._image_block([10, 100, 50, 140], "logo.png"),
            {"type": "table", "bbox": [10, 170, 300, 210], "lines": [
                {"spans": [{"type": "table", "html": self.table_html}]}]},
            self._text_block("interline_equation", [10, 240, 300, 260], self.equation,
                             span_type="interline_equation"),
            self._image_block([10, 300, 300, 450], "panel.png"),
        ]
        blocks[-1]["blocks"].append({"type": "image_caption", "bbox": [10, 460, 300, 490],
                                     "lines": [{"spans": [{"type": "text", "content": "FIGURE 1 | 原文 caption."}]}]})
        for index, block in enumerate(blocks):
            block['index'] = index
        self.middle = self.directory / "fixture_middle.json"
        self.middle.write_text(json.dumps({"pdf_info": [
            {"page_idx": 0, "page_size": [600, 800], "para_blocks": blocks}]}), encoding="utf-8")
        inventory = {
            "schema_version": "figure-inventory-v1", "data_id": self.data_id,
            "middle_sha256": sha256(self.middle.read_bytes()).hexdigest(),
            "extraction_scope": "whole_document", "source": "reviewed_original_pdf_regions",
            "renderer": {"name": "synthetic_fixture_not_pdf_render"},
            "figures": [{"number": 1, "page_index": 0, "bbox": [10, 300, 300, 450],
                         "member_block_ids": ["/pdf_info/0/para_blocks/5"],
                         "caption_block_ids": ["/pdf_info/0/para_blocks/5"],
                         "image": {"path": "images/full-figure.png",
                                   "sha256": sha256(self.assets["full-figure.png"]).hexdigest(),
                                   "byte_size": len(self.assets["full-figure.png"])}}],
        }
        inventory_path = self.directory / "palimpsest_figures.json"
        inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
        self.profile = {
            "schema_version": "source-d2i-v1",
            "parser": {"provider": "mineru", "version": "3.4.5", "backend": "pipeline",
                       "image_digest": "sha256:" + "a" * 64, "models_manifest_sha256": "b" * 64},
            "transformation": {"algorithm": "source-units-v1", "schema_version": "source-information-v1"},
            "policy": {"version": "source-d2i-v1", "llm_calls": 0,
                       "source_fidelity": "source_preserving", "extraction_scope": "whole_document",
                       "figure_inventory_sha256": sha256(inventory_path.read_bytes()).hexdigest()},
        }

    @staticmethod
    def _text_block(kind, bbox, content, *, span_type="text"):
        return {"type": kind, "bbox": bbox,
                "lines": [{"spans": [{"type": span_type, "content": content}]}]}

    @staticmethod
    def _image_block(bbox, name):
        return {"type": "image", "bbox": bbox, "blocks": [
            {"type": "image_body", "bbox": bbox,
             "lines": [{"spans": [{"type": "image", "image_path": name}]}]}]}

    def _prepared(self):
        execution_id = self.runtime.start(self.data_id, self.profile)["execution_id"]
        self.runtime.attach_parser(execution_id, self.directory, self.middle.name, 1)
        return execution_id

    def _row(self, query, params=()):
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            return conn.execute(query, params).fetchone()

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
        self.assertNotEqual(0, caught.exception.exit_code)

    def _interrupt_commit(self, execution_id):
        def crash(stage):
            self.assertEqual("before_commit", stage)
            raise RuntimeError("injected source commit failure")
        with self.assertRaisesRegex(RuntimeError, "injected source commit failure"):
            self.runtime.materialize_source(execution_id, checkpoint=crash)

    def test_source_units_preserve_payload_groundings_empty_text_and_all_unit_types(self):
        execution_id = self._prepared()
        parsed = self.runtime.show(execution_id, include_input=True)["parse"]
        original_blocks = {b["block_id"]: b for b in parsed["bundle"]["blocks"]}
        with patch("palimpsest.codex_provider.CodexProvider.generate",
                   side_effect=AssertionError("D2I must not call an LLM")) as provider:
            result = self.runtime.materialize_source(execution_id)
        provider.assert_not_called()
        self.assertEqual("completed", result["state"])
        self.assertEqual({"records": 6, "candidates": 0, "information": 6, "groundings": 7, "outbox": 6},
                         self._counts(execution_id))
        rows = self.runtime.information(data_id=self.data_id)["information"]
        self.assertEqual(Counter({"text": 2, "image": 1, "table": 1, "equation": 1, "figure": 1}),
                         Counter(row["unit_type"] for row in rows))
        covered = []
        for row in rows:
            self.assertEqual(7, UUID(str(row["information_id"])).version)
            self.assertIsNone(row["semantic_type"])
            payload = row["payload"]
            self.assertEqual("source-information-v1", payload["schema_version"])
            self.assertEqual("source_structure", payload["validation_basis"])
            self.assertIs(payload["semantic_checked"], False)
            self.assertEqual(row["content"] == "", payload["empty_content"])
            self.assertEqual(digest(parsed["bundle"]), payload["source_bundle_sha256"])
            self.assertEqual(parsed["manifest_hash"], payload["parse_manifest_sha256"])
            refs = [block["block_id"] for block in payload["source_blocks"]]
            self.assertEqual([original_blocks[ref] for ref in refs], payload["source_blocks"])
            self.assertEqual(set(refs), {g["block_id"] for g in row["groundings"]})
            covered.extend(refs)
        self.assertCountEqual(list(original_blocks), covered)
        texts = [row["content"] for row in rows if row["unit_type"] == "text"]
        self.assertCountEqual([self.source_text, ""], texts)
        self.assertEqual(self.table_html, next(row for row in rows if row["unit_type"] == "table")["content"])
        self.assertEqual(self.equation, next(row for row in rows if row["unit_type"] == "equation")["content"])
        figure = next(row for row in rows if row["unit_type"] == "figure")
        # The normalized image body contributes an empty line before its
        # caption; source conversion must preserve that separator as well.
        self.assertEqual("\nFIGURE 1 | 原文 caption.", figure["content"])
        self.assertEqual({"/figures/0", "/pdf_info/0/para_blocks/5"},
                         {b["block_id"] for b in figure["payload"]["source_blocks"]})
        self.assertEqual(self.assets["full-figure.png"],
                         (self.root / figure["payload"]["images"][0]["artifact_path"]).read_bytes())
        for name, artifact in figure["payload"]["source_artifacts"].items():
            self.assertEqual(self.assets[Path(name).name], (self.root / artifact["artifact_path"]).read_bytes())
        job = self.runtime.show(execution_id)
        for role in ("generator", "validator"):
            self.assertEqual("deterministic_source_check", job[role + "_receipt"]["receipt_kind"])
            self.assertEqual(0, job[role + "_receipt"]["llm_calls"])
            self.assertNotIn("thread_ref", job[role + "_receipt"])

    def test_completed_materialize_retry_returns_same_information_ids_without_new_effects(self):
        execution_id = self._prepared()
        first = self.runtime.materialize_source(execution_id)
        snapshot = self.runtime.information(data_id=self.data_id)
        counts = self._counts(execution_id)
        retry = self.runtime.materialize_source(execution_id)
        self.assertFalse(first["replayed"])
        self.assertTrue(retry["replayed"])
        self.assertEqual(first["information_ids"], retry["information_ids"])
        self.assertEqual(snapshot, self.runtime.information(data_id=self.data_id))
        self.assertEqual(counts, self._counts(execution_id))
        self.assertEqual(["prepared", "parsed", "proposed", "completed"],
                         [event["state"] for event in self.runtime.show(execution_id)["events"]])

    def test_before_commit_failure_keeps_candidates_and_rolls_back_all_canonical_effects(self):
        execution_id = self._prepared()
        self._interrupt_commit(execution_id)
        self.assertEqual({"records": 6, "candidates": 6, "information": 0, "groundings": 0, "outbox": 0},
                         self._counts(execution_id))
        interrupted = self.runtime.show(execution_id, include_input=True)
        self.assertEqual("proposed", interrupted["state"])
        self.assertIsNone(interrupted["validator_receipt"])
        self.assertTrue(all(record["disposition"] is None for record in interrupted["records"]))
        self.assertEqual(6, len(interrupted["proposals"]))
        self.assertEqual("completed", self.runtime.materialize_source(execution_id)["state"])
        completed = self.runtime.show(execution_id)
        self.assertEqual([r["record_id"] for r in interrupted["records"]],
                         [r["record_id"] for r in completed["records"]])
        self.assertEqual({"records": 6, "candidates": 0, "information": 6, "groundings": 7, "outbox": 6},
                         self._counts(execution_id))

    def test_altered_source_proposals_are_rejected_before_records_are_staged(self):
        execution_id = self._prepared()
        bundle = self.runtime.show(execution_id, include_input=True)["parse"]["bundle"]
        original = build_source_units(bundle)
        checks = verify_source_units(bundle, original)
        altered = deepcopy(original)
        altered[0]["content"] = "An inferred summary cannot replace original text."
        receipt = self.runtime._source_receipt("generator", bundle, altered, checks)
        self._assert_error("source_unit_mismatch", lambda: self.runtime.propose(execution_id, altered, receipt))
        self.assertEqual("parsed", self.runtime.show(execution_id)["state"])
        self.assertEqual({"records": 0, "candidates": 0, "information": 0, "groundings": 0, "outbox": 0},
                         self._counts(execution_id))

    def test_corrupted_retained_crop_blocks_commit_then_recovers_from_original_bytes(self):
        execution_id = self._prepared()
        parsed = self.runtime.show(execution_id, include_input=True)["parse"]
        reference = parsed["manifest"]["files"]["images/full-figure.png"]
        crop = self.root / reference["artifact_path"]
        original = crop.read_bytes()
        original_mode = stat.S_IMODE(crop.stat().st_mode)
        self.assertEqual(sha256(original).hexdigest(), reference["sha256"])
        try:
            # Fault injection affects only this test's private Artifact Store.
            # Keep the same length so a size-only check cannot pass the test.
            crop.chmod(original_mode | stat.S_IWUSR)
            crop.write_bytes(bytes([original[0] ^ 1]) + original[1:])
            self.assertEqual(reference["byte_size"], crop.stat().st_size)
            self._assert_error("integrity_conflict", lambda: self.runtime.materialize_source(execution_id))
            staged = self.runtime.show(execution_id, include_input=True)
            self.assertEqual("proposed", staged["state"])
            self.assertIsNone(staged["validator_receipt"])
            self.assertEqual(6, len(staged["proposals"]))
            self.assertEqual({"records": 6, "candidates": 6, "information": 0, "groundings": 0, "outbox": 0},
                             self._counts(execution_id))
            self.assertTrue(all(record["disposition"] is None for record in staged["records"]))
        finally:
            crop.write_bytes(original)
            crop.chmod(original_mode)
        self.assertEqual(reference["sha256"], sha256(crop.read_bytes()).hexdigest())
        self.assertEqual("completed", self.runtime.materialize_source(execution_id)["state"])
        completed = self.runtime.show(execution_id)
        self.assertEqual([record["record_id"] for record in staged["records"]],
                         [record["record_id"] for record in completed["records"]])
        self.assertEqual({"records": 6, "candidates": 0, "information": 6, "groundings": 7, "outbox": 6},
                         self._counts(execution_id))

    def test_replaced_pending_candidate_cannot_be_promoted_by_materialize_retry(self):
        execution_id = self._prepared()
        self._interrupt_commit(execution_id)
        staged = self.runtime.show(execution_id, include_input=True)
        record_id = staged["records"][0]["record_id"]
        altered = deepcopy(staged["proposals"][0])
        altered["content"] = "Changed while the source execution was interrupted."
        # The application role cannot UPDATE candidates. Replacing one pending
        # row uses its permitted DELETE/INSERT path without touching history.
        with psycopg.connect(self.dsn) as conn:
            conn.execute("DELETE FROM compiler_runtime.temporary_candidates WHERE record_id=%s", (record_id,))
            conn.execute("INSERT INTO compiler_runtime.temporary_candidates(record_id,body) VALUES (%s,%s)",
                         (record_id, Jsonb(altered)))
        self._assert_error("provider_source_mismatch", lambda: self.runtime.materialize_source(execution_id))
        self.assertEqual("proposed", self.runtime.show(execution_id)["state"])
        self.assertEqual({"records": 6, "candidates": 6, "information": 0, "groundings": 0, "outbox": 0},
                         self._counts(execution_id))

    def test_i2k_preparation_reads_canonical_i_and_registered_pdf_without_effects(self):
        execution_id = self._prepared()
        self.runtime.materialize_source(execution_id)
        before = self._counts(execution_id)
        packet = self.runtime.prepare_input(execution_id)
        self.assertEqual('prepared_not_delivered', packet['state'])
        self.assertFalse(packet['actual_delivery'])
        self.assertEqual(6, len(packet['target_information_ids']))
        self.assertEqual(3, len(packet['media_assets']))
        self.assertEqual({sha256(value).hexdigest() for value in self.assets.values()},
                         {asset['sha256'] for asset in packet['media_assets']})
        self.assertNotIn('rendered_source_pages', packet['model_input'])
        self.assertNotIn('artifact_path', json.dumps(packet['model_input']))
        units = packet['model_input']['information']
        self.assertEqual(self.source_text, units[0]['content'])
        self.assertTrue(all(ref['parse_artifact_id'] and ref['grounding_id'] for unit in units for ref in unit['source_refs']))
        selected = self.runtime.prepare_input(execution_id, information_ids=[packet['target_information_ids'][0]])
        self.assertEqual(1, len(selected['target_information_ids']))
        self.assertEqual(5, len(selected['excluded_information_ids']))
        request = {'schema_version':'i2k-source-request-v1', 'input_sha256':packet['input_sha256'],
                   'information_ids':[packet['target_information_ids'][0]],
                   'question':'원본에서 숫자와 단위를 확인합니다.', 'page_numbers':[1]}
        result = self.runtime.prepare_source(execution_id, request)
        self.assertEqual(self.data_id, result['original_pdf']['sha256'])
        self.assertEqual('not_delivered', result['delivery_status'])
        self.assertEqual([], result['actual_citations'])
        self.assertEqual(0, result['llm_calls'])
        self.assertEqual(before, self._counts(execution_id))
        self._assert_error('i2k_input_changed', lambda: self.runtime.prepare_source(execution_id,
            {**request, 'input_sha256':'0' * 64}))
        self._assert_error('invalid_i2k_source_request', lambda: self.runtime.prepare_source(execution_id,
            {**request, 'path':'/private/other.pdf'}))
        data = self.runtime.data.get_data(self.data_id)
        with patch.object(self.runtime.data, 'get_data', return_value={**data, 'media_type':'text/plain'}):
            self._assert_error('original_pdf_required', lambda: self.runtime.prepare_source(execution_id, request))
        job, parsed, rows = self.runtime._source_snapshot(execution_id)
        altered = deepcopy(rows)
        image_row = next(row for row in altered if row['payload']['source_artifacts'])
        next(iter(image_row['payload']['source_artifacts'].values()))['byte_size'] += 1
        with patch.object(self.runtime, '_source_snapshot', return_value=(job, parsed, altered)):
            self._assert_error('input_media_mismatch', lambda: self.runtime.prepare_input(execution_id))
        source_path = self.root / result['original_pdf']['artifact_path']
        original = source_path.read_bytes()
        source_path.chmod(0o600)
        source_path.write_bytes(b'X' * len(original))
        self._assert_error('integrity_conflict', lambda: self.runtime.prepare_source(execution_id, request))
        source_path.write_bytes(original)
        source_path.chmod(0o400)

    def test_i2k_cli_input_and_source_preparation_are_json_and_not_provider_delivery(self):
        execution_id = self._prepared()
        self.runtime.materialize_source(execution_id)
        environment = {'PALIMPSEST_DATABASE_DSN':self.dsn, 'PALIMPSEST_ARTIFACT_ROOT':str(self.root)}

        def invoke(arguments):
            output, errors = io.StringIO(), io.StringIO()
            with patch.dict(os.environ, environment, clear=True), redirect_stdout(output), redirect_stderr(errors):
                code = cli.main(['information', *arguments, '--execution-id', str(execution_id), '--json'])
            return code, json.loads(output.getvalue())

        code, envelope = invoke(['prepare-input'])
        self.assertEqual(0, code)
        packet = envelope['result']
        request = {'schema_version':'i2k-source-request-v1', 'input_sha256':packet['input_sha256'],
                   'information_ids':[packet['target_information_ids'][0]], 'question':'기호 확인', 'page_numbers':[]}
        request_file = self.base / 'source-request.json'
        request_file.write_text(json.dumps(request), encoding='utf-8')
        code, envelope = invoke(['prepare-source', '--request', str(request_file)])
        self.assertEqual(0, code)
        self.assertEqual('not_delivered', envelope['result']['delivery_status'])
        request_file.write_text('{"schema_version":"bad","schema_version":"duplicate"}', encoding='utf-8')
        code, envelope = invoke(['prepare-source', '--request', str(request_file)])
        self.assertNotEqual(0, code)
        self.assertEqual('failed', envelope['command_status'])

    def test_regroup_creates_only_group_records_preserves_legacy_and_replays_cli(self):
        execution_id = self._prepared()
        legacy = self.runtime.materialize_source(execution_id)
        before = [self.runtime.information(information_id=identifier) for identifier in legacy['information_ids']]
        old_packet = self.runtime.prepare_input(execution_id)
        result = self.runtime.regroup_source(execution_id)
        grouped_id = result['execution_id']
        self.assertNotEqual(str(execution_id), str(grouped_id))
        self.assertEqual({'records':2, 'candidates':0, 'information':2, 'groundings':7, 'outbox':2},
                         self._counts(grouped_id))
        self.assertEqual(before, [self.runtime.information(information_id=i) for i in legacy['information_ids']])
        self.assertEqual(old_packet, self.runtime.prepare_input(execution_id))
        packet = self.runtime.prepare_input(grouped_id)
        self.assertEqual('source-groups-v2', packet['source_assembly_algorithm'])
        self.assertEqual(2, len(packet['model_input']['information']))
        self.assertEqual(old_packet['media_assets'], packet['media_assets'])
        self.assertEqual(2, len(self.runtime.page_view(grouped_id)['pages'][0]['images']))
        parsed = self.runtime.show(grouped_id, include_input=True)['parse']
        old_parsed = self.runtime.show(execution_id, include_input=True)['parse']
        self.assertEqual(old_parsed['bundle'], parsed['bundle'])
        self.assertEqual(old_parsed['manifest']['files'], parsed['manifest']['files'])
        self.assertEqual(old_parsed['manifest_hash'], parsed['manifest']['source_reassembly']['source_parse_manifest_sha256'])
        for unit in packet['model_input']['information']:
            by_id = {b['block_id']: b for b in parsed['bundle']['blocks']}
            for span in unit['source_assembly']['content_segments']:
                if span['char_start'] is not None:
                    self.assertEqual(by_id[span['source_block_id']]['text'],
                                     unit['content'][span['char_start']:span['char_end']])
        replay = self.runtime.regroup_source(execution_id)
        self.assertEqual(result['information_ids'], replay['information_ids'])
        self.assertTrue(replay['replayed'])
        output, errors = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {'PALIMPSEST_DATABASE_DSN':self.dsn, 'PALIMPSEST_ARTIFACT_ROOT':str(self.root)}, clear=True), redirect_stdout(output), redirect_stderr(errors):
            code = cli.main(['compile', 'regroup', '--execution-id', str(execution_id), '--json'])
        self.assertEqual(0, code)
        self.assertEqual([str(i) for i in result['information_ids']], json.loads(output.getvalue())['result']['information_ids'])
        changed = deepcopy(parsed)
        changed['manifest']['source_reassembly']['source_profile_sha256'] = '0' * 64
        changed['manifest_hash'] = digest(changed['manifest'])
        self._assert_error('source_reassembly_mismatch', lambda: self.runtime._verify_source_artifacts(
            self.runtime.show(grouped_id), changed))
        self._assert_error('retained_source_required', lambda: self.runtime.attach_parser(
            grouped_id, self.directory, self.middle.name, 1))

    def test_regroup_commit_failure_rolls_back_groups_then_resumes_same_execution(self):
        source = self._prepared()
        self.runtime.materialize_source(source)
        def crash(stage):
            self.assertEqual('before_commit', stage)
            raise RuntimeError('injected grouped commit failure')
        with self.assertRaisesRegex(RuntimeError, 'injected grouped commit failure'):
            self.runtime.regroup_source(source, checkpoint=crash)
        target = self._row('''SELECT execution_id FROM compiler_runtime.operation_executions e
            JOIN compiler_runtime.profiles p USING(profile_id) WHERE e.data_id=%s
            AND p.payload->'policy'->'source_reassembly'->>'source_execution_id'=%s''',
            (self.data_id, str(source)))['execution_id']
        self.assertEqual({'records':2, 'candidates':2, 'information':0, 'groundings':0, 'outbox':0}, self._counts(target))
        result = self.runtime.regroup_source(source)
        self.assertEqual(str(target), str(result['execution_id']))
        self.assertEqual(2, len(result['information_ids']))
        self.assertEqual(6, self._counts(source)['information'])

    def test_new_grouped_profile_stores_groups_directly_and_rejects_old_receipt(self):
        self.profile['transformation']['algorithm'] = 'source-groups-v1'
        execution_id = self._prepared()
        self.assertEqual(0, self._counts(execution_id)['information'])
        with patch('palimpsest.codex_provider.CodexProvider.generate', side_effect=AssertionError('No D2I LLM')):
            result = self.runtime.materialize_source(execution_id)
        self.assertEqual({'records':2, 'candidates':0, 'information':2, 'groundings':7, 'outbox':2},
                         self._counts(execution_id))
        job = self.runtime.show(execution_id, include_input=True)
        receipt = deepcopy(job['generator_receipt'])
        receipt['algorithm'] = 'source-units-v1'
        self._assert_error('invalid_source_receipt', lambda: self.runtime.propose(execution_id, [], receipt))
        self.assertEqual(result['information_ids'], self.runtime.regroup_source(execution_id)['information_ids'])
        parsed, rows = job['parse'], self.runtime._source_snapshot(execution_id)[2]
        altered = deepcopy(rows)
        altered[0]['payload']['source_assembly']['content_segments'][0]['char_end'] += 1
        with patch.object(self.runtime, '_source_snapshot', return_value=(job, parsed, altered)):
            self._assert_error('invalid_i2k_input', lambda: self.runtime.prepare_input(execution_id))

    def test_two_regroup_callers_receive_same_ids_and_one_set_of_effects(self):
        source = self._prepared()
        self.runtime.materialize_source(source)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.runtime.regroup_source(source), range(2)))
        self.assertEqual(results[0]['execution_id'], results[1]['execution_id'])
        self.assertEqual(results[0]['information_ids'], results[1]['information_ids'])
        self.assertEqual({'records':2, 'candidates':0, 'information':2, 'groundings':7, 'outbox':2},
                         self._counts(results[0]['execution_id']))

    def test_additive_page_i_location_and_original_export_preserve_prior_i(self):
        import struct
        import zlib
        from test_source_reconstruction import visuals_for
        self.profile['transformation']['algorithm'] = 'source-groups-v1'
        execution = self._prepared()
        self.runtime.materialize_source(execution)
        old = self.runtime.prepare_input(execution)
        _, parsed, _ = self.runtime._source_snapshot(execution)
        visuals = visuals_for(parsed['bundle'])
        visuals['source']['pdf_size_bytes'] = (self.base/'source.pdf').stat().st_size
        visuals['pages'][0]['page_image']['pixel_size'] = [1200,1600]
        width,height = visuals['pages'][0]['page_image']['pixel_size']
        def chunk(kind, body):
            return struct.pack('>I',len(body))+kind+body+struct.pack('>I',zlib.crc32(kind+body))
        png = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))
        png += chunk(b'IDAT',zlib.compress((b'\x00'+b'\xff\xff\xff'*width)*height))+chunk(b'IEND',b'')
        image = visuals['pages'][0]['page_image']
        image.update(sha256=sha256(png).hexdigest(),size_bytes=len(png))
        directory = self.base/'page-evidence'
        (directory/'pages').mkdir(parents=True)
        (directory/image['path']).write_bytes(png)
        evidence = {'source_bundle':parsed['bundle'],'visuals':visuals,'manifest_sha256':'e'*64,
                    'asset_base_directory':str(directory)}
        before = self._counts(execution)
        with patch('palimpsest.pdf_evidence.read_evidence',return_value=evidence):
            added = self.runtime.add_source_pages(execution,directory)
            replay = self.runtime.add_source_pages(execution,directory)
        self.assertEqual(added['information_ids'],replay['information_ids'])
        self.assertEqual(before,self._counts(execution))
        self.assertEqual(old,self.runtime.prepare_input(execution))
        current = self.runtime.prepare_input(added['execution_id'])
        self.assertEqual(len(current['target_information_ids']),len(old['target_information_ids'])+1)
        self.assertFalse(set(current['target_information_ids']) & set(old['target_information_ids']))
        query = {'page_number':1,'bbox':[590,780,599,790]}
        self.assertEqual(self.runtime.lookup_source(execution,**query)['status'],'unmapped_region')
        match = self.runtime.lookup_source(added['execution_id'],**query)
        self.assertEqual(match['status'],'visible_page_region_available')
        back = self.runtime.locate_information(added['execution_id'],match['page_image_information_ids'][0])
        self.assertEqual(back['source_refs'][0]['facsimile_provenance']['image_sha256'],sha256(png).hexdigest())
        report = self.runtime.reconstruct_source(added['execution_id'])
        self.assertEqual(report['source_coverage'],'all_rendered_visible_pages_in_information')
        self.assertEqual(report['original_page_image_information_count'],1)
        destination = self.base/'exports'/'original.pdf'
        exported = self.runtime.export_source(added['execution_id'],destination)
        self.assertTrue(exported['byte_identical'])
        self.assertEqual(destination.read_bytes(),(self.base/'source.pdf').read_bytes())
        self.assertTrue(self.runtime.export_source(added['execution_id'],destination)['replayed'])
        destination.write_bytes(b'preserve existing output')
        self._assert_error('export_conflict',lambda:self.runtime.export_source(added['execution_id'],destination))
        self.assertEqual(destination.read_bytes(),b'preserve existing output')
        link = self.base/'output-link.pdf'
        link.symlink_to(destination)
        self._assert_error('unsafe_path',lambda:self.runtime.export_source(added['execution_id'],link))
        self.assertEqual(destination.read_bytes(),b'preserve existing output')
        artifact = self.root/'objects'/'sha256'/self.data_id[:2]/self.data_id
        artifact.chmod(0o600)  # Deliberate corruption of this disposable test artifact.
        artifact.write_bytes(b'corrupt original')
        self._assert_error('integrity_conflict',lambda:self.runtime.export_source(added['execution_id'],self.base/'blocked.pdf'))
        self.assertFalse((self.base/'blocked.pdf').exists())

    def test_public_compile_rejects_legacy_llm_profile_without_creating_execution(self):
        provider = {"provider": "codex_cli", "model": "gpt-5.6-terra", "reasoning_effort": "medium",
                    "auth": "chatgpt_oauth", "cli_version": "0.153.4"}
        legacy = {"schema_version": "d2i-v1", "parser": self.profile["parser"],
                  "generator": provider, "validator": provider, "policy": {"fixture": "historical_only"}}
        profile_path = self.base / "legacy-profile.json"
        profile_path.write_text(json.dumps(legacy), encoding="utf-8")
        output, errors = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {"PALIMPSEST_DATABASE_DSN": self.dsn,
                                     "PALIMPSEST_ARTIFACT_ROOT": str(self.root)}, clear=True):
            with redirect_stdout(output), redirect_stderr(errors):
                code = cli.main(["compile", "data", self.data_id, "--profile", str(profile_path),
                                 "--json", "--non-interactive"])
        self.assertEqual(2, code)
        envelope = json.loads(output.getvalue())
        self.assertEqual("llm_d2i_disabled", envelope["error"]["code"])
        self.assertEqual("failed", envelope["command_status"])
        self.assertEqual(0, self._row("SELECT count(*) AS count FROM compiler_runtime.operation_executions "
                                      "WHERE data_id=%s", (self.data_id,))["count"])


if __name__ == "__main__":
    unittest.main()
