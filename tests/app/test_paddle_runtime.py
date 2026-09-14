"""Synthetic Paddle persistence contracts; no OCR/model or visual evaluation.

The caller provisions a disposable PG18/pgvector database. Each test imports
unique synthetic PDF bytes and uses a private Artifact Store; this module never
migrates, truncates, or resets database history.
"""

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

import psycopg

from palimpsest.artifact_store import ArtifactStore
from palimpsest.canonical_store import PostgresRepository
from palimpsest.compiler_runtime import CompilerRuntime, digest, validate_profile
from palimpsest.errors import PalimpsestError
from palimpsest.service import DataService


def source_profile():
    return {
        "schema_version": "source-d2i-v1",
        "parser": {"provider": "paddleocr-vl", "version": "3.7.0", "backend": "transformers",
                   "pipeline_version": "v1.6", "adapter_version": "paddleocr-raw-v1",
                   "image_digest": "sha256:" + "a" * 64, "models_manifest_sha256": "b" * 64,
                   "fixture": "synthetic storage contract; not a verified live model profile"},
        "transformation": {"algorithm": "source-units-v1", "schema_version": "source-information-v1"},
        "policy": {"version": "source-d2i-v1", "llm_calls": 0,
                   "source_fidelity": "source_preserving", "extraction_scope": "whole_document"},
    }


class PaddleProfileTests(unittest.TestCase):
    def test_only_explicit_source_profile_is_allowed(self):
        profile = source_profile()
        self.assertEqual(profile, validate_profile(deepcopy(profile)))
        for section, key, value in (
            ("parser", "provider", "automatic_fallback"),
            ("parser", "version", "3.6.0"),
            ("parser", "pipeline_version", "v1.5"),
            ("parser", "backend", "pipeline"),
            ("parser", "adapter_version", "unknown"),
            ("policy", "llm_calls", 1),
        ):
            invalid = deepcopy(profile)
            invalid[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(PalimpsestError) as caught:
                validate_profile(invalid)
            self.assertEqual("invalid_compilation_profile", caught.exception.code)
        invalid = deepcopy(profile)
        invalid["schema_version"] = "d2i-v1"
        with self.assertRaises(PalimpsestError) as caught:
            validate_profile(invalid)
        self.assertEqual("invalid_compilation_profile", caught.exception.code)


@unittest.skipUnless(sys.platform == "linux" and os.environ.get("PALIMPSEST_TEST_DSN"),
                     "Requires Linux and explicitly provisioned disposable PALIMPSEST_TEST_DSN")
class PaddleRuntimeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["PALIMPSEST_TEST_DSN"]
        with psycopg.connect(cls.dsn) as conn:
            if int(conn.execute("SHOW server_version_num").fetchone()[0]) // 10000 != 18:
                raise RuntimeError("Paddle integration profile requires PostgreSQL 18")
            if not conn.execute("SELECT 1 FROM pg_extension WHERE extname='vector'").fetchone():
                raise RuntimeError("Provision pgvector before running integration tests")
            if not conn.execute("SELECT 1 FROM compiler_runtime.schema_migrations "
                                "WHERE version='0003_source_information'").fetchone():
                raise RuntimeError("Provision the reviewed source Information migration first")

    def test_source_attach_materialize_retry_export_and_page_provenance(self):
        with TemporaryDirectory(prefix="palimpsest-paddle-integration-") as directory:
            base = Path(directory)
            root = base / "artifacts"
            source = base / "source.pdf"
            source.write_bytes(b"%PDF-1.7\nSynthetic Paddle storage fixture\n" + uuid4().bytes)
            data_id = sha256(source.read_bytes()).hexdigest()
            DataService(PostgresRepository(self.dsn), ArtifactStore(root), actor_ref="local").import_file(
                source, media_type="application/pdf")
            parser_output = base / "synthetic-parser-output"
            (parser_output / "images").mkdir(parents=True)
            image = b"synthetic crop integrity bytes; not a decoded Figure"
            (parser_output / "images/figure.png").write_bytes(image)
            source_text = "  e\u0301 / 원문\r\n공백 그대로  "
            blocks = [
                {"block_id": 9, "block_label": "header", "block_content": "Repeated header",
                 "block_bbox": [20, 180, 500, 200], "block_order": 9},
                {"block_id": 4, "block_label": "doc_title", "block_content": "Paper",
                 "block_bbox": [20, 0, 500, 40], "block_order": 1},
                {"block_id": 8, "block_label": "image", "block_content": "",
                 "block_bbox": [20, 400, 600, 800], "block_order": None},
                {"block_id": 3, "block_label": "figure_title", "block_content": "Figure 1. Caption",
                 "block_bbox": [20, 820, 600, 860], "block_order": 0},
                {"block_id": 1, "block_label": "text", "block_content": source_text,
                 "block_bbox": [620, 100, 1100, 200], "block_order": 2},
            ]
            second = [{"block_id": 0, "block_label": "header", "block_content": "Repeated header",
                       "block_bbox": [20, 0, 500, 40], "block_order": None}]
            raw = {"schema_version": "paddleocr-raw-v1", "data_id": data_id, "page_count": 2,
                   "models_manifest_sha256": "b" * 64, "versions": {"paddleocr": "3.7.0"}, "pages": [
                {"page_index": index, "pdf_size": [600, 800], "render_size": [1200, 1600],
                 "rotation": 0, "cropbox": [10, 20, 610, 820], "source_box": "crop",
                 "result": {"width": 1200, "height": 1600, "parsing_res_list": items,
                            "model_settings": {"use_doc_preprocessor": False, "merge_layout_blocks": False}},
                 "image_assets": ([{"block_id": 8, "path": "images/figure.png",
                                    "sha256": sha256(image).hexdigest(), "bbox": blocks[2]["block_bbox"]}]
                                  if index == 0 else [])}
                for index, items in enumerate((blocks, second))]}
            raw_path = parser_output / "paddle_raw.json"
            raw_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            runtime = CompilerRuntime(self.dsn, root)
            execution_id = runtime.start(data_id, source_profile())["execution_id"]
            self.assertFalse(runtime.attach_parser(execution_id, parser_output, raw_path.name, 2)["replayed"])
            self.assertTrue(runtime.attach_parser(execution_id, parser_output, raw_path.name, 2)["replayed"])
            parsed = runtime.show(execution_id, include_input=True)["parse"]
            self.assertEqual("paddle_raw.json", parsed["manifest"]["middle"])
            self.assertEqual("paddleocr", parsed["bundle"]["reading_order_source"])
            with patch("palimpsest.codex_provider.CodexProvider.generate",
                       side_effect=AssertionError("Source assembly must not call an application LLM")) as provider:
                completed = runtime.materialize_source(execution_id)
            provider.assert_not_called()
            self.assertEqual("completed", completed["state"])
            rows = runtime.information(data_id=data_id)["information"]
            self.assertEqual(6, len(rows))
            self.assertEqual(6, len({row["information_id"] for row in rows}))
            covered = []
            for row in rows:
                self.assertEqual(7, UUID(str(row["information_id"])).version)
                self.assertIsNone(row["semantic_type"])
                self.assertEqual(digest(parsed["bundle"]), row["payload"]["source_bundle_sha256"])
                self.assertFalse(row["payload"]["semantic_checked"])
                self.assertEqual("source_structure", row["payload"]["validation_basis"])
                covered.extend(block["block_id"] for block in row["payload"]["source_blocks"])
                self.assertEqual({block["block_id"] for block in row["payload"]["source_blocks"]},
                                 {g["block_id"] for g in row["groundings"]})
            self.assertCountEqual([b["block_id"] for b in parsed["bundle"]["blocks"]], covered)
            self.assertEqual(2, sum(row["content"] == "Repeated header" for row in rows))
            self.assertIn(source_text, [row["content"] for row in rows])
            replay = runtime.materialize_source(execution_id)
            self.assertTrue(replay["replayed"])
            self.assertEqual(completed["information_ids"], replay["information_ids"])
            self.assertEqual(rows, runtime.information(data_id=data_id)["information"])
            self.assertEqual(["prepared", "parsed", "proposed", "completed"],
                             [event["state"] for event in runtime.show(execution_id)["events"]])
            projection = runtime.page_view(execution_id)
            self.assertEqual([0, 1], [page["page_index"] for page in projection["pages"]])
            for index, page in enumerate(projection["pages"]):
                original = raw["pages"][index]["result"]["parsing_res_list"]
                self.assertEqual("paddleocr_array_order", page["reading_order"])
                self.assertEqual("\n\n".join(block["block_content"] for block in original), page["content"])
                self.assertEqual(list(range(len(original))), [b["paddleocr_index"] for b in page["blocks"]])
                for ordinal, block in enumerate(page["blocks"]):
                    self.assertNotIn("mineru_index", block)
                    self.assertEqual(f"/pages/{index}/result/parsing_res_list/{ordinal}", block["raw_locator"])
                    self.assertEqual(original[ordinal]["block_content"],
                                     page["content"][block["char_start"]:block["char_end"]])
            context = runtime.page_view(execution_id, page_number=1)
            self.assertEqual(["target", "context"], [p["role"] for p in context["pages"]])
            self.assertEqual(0, context["llm_calls"])
            restored = base / "restored"
            self.assertEqual(2, runtime.export_parser(execution_id, restored)["file_count"])
            self.assertEqual(raw_path.read_bytes(), (restored / "paddle_raw.json").read_bytes())
            self.assertEqual(image, (restored / "images/figure.png").read_bytes())


if __name__ == "__main__":
    unittest.main()
