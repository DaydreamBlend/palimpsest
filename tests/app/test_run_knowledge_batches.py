import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
import importlib.util
SPEC = importlib.util.spec_from_file_location("batch_runner", ROOT / "tools/run_knowledge_batches.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class KnowledgeBatchRunnerTests(unittest.TestCase):
    def test_pending_skips_completed_and_failed_attempts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("b0001", "b0002", "b0003"):
                directory = root / name
                directory.mkdir()
                (directory / "request.json").write_text(
                    json.dumps({"output_file": "response.json"}), encoding="utf-8")
            (root / "b0002/response.json").write_text("{}", encoding="utf-8")
            (root / "b0003/response.failure.json").write_text("{}", encoding="utf-8")
            self.assertEqual([root / "b0001/request.json"], runner.pending(root))

    def test_retry_archives_failure_before_reusing_output_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "b0001"
            root.mkdir()
            request = root / "request.json"
            request.write_text(json.dumps({"output_file": "response.json"}), encoding="utf-8")
            failure = root / "response.failure.json"
            failure.write_text('{"attempt":1}', encoding="utf-8")
            self.assertEqual([request], runner.pending(root.parent, retry_failures=True))
            runner.archive_failure(request)
            self.assertFalse(failure.exists())
            self.assertEqual('{"attempt":1}', (root / "response.attempt1.failure.json").read_text(encoding="utf-8"))

    def test_pending_can_be_limited_to_current_manifest_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("g0001", "g0001-r2"):
                directory = root / name
                directory.mkdir()
                (directory / "request.json").write_text(
                    json.dumps({"output_file": "response.json"}), encoding="utf-8")
            self.assertEqual(
                [root / "g0001-r2/request.json"], runner.pending(root, names=["g0001-r2"]))
            self.assertEqual([], runner.pending(root, names=[]))
            with self.assertRaisesRegex(ValueError, "invalid_job_directory"):
                runner.pending(root, names=["../g0001"])


if __name__ == "__main__":
    unittest.main()
