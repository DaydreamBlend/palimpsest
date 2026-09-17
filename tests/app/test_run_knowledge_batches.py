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


if __name__ == "__main__":
    unittest.main()
