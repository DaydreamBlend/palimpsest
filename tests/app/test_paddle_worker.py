"""Worker profile/image binding regressions; Docker, GPU and DB are not run."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("paddle_worker_under_test", ROOT / "tools/run_d2i.py")
worker_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker_module)


class PaddleWorkerTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        root_patch = patch.object(worker_module, "ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        for name in (
            "src/palimpsest/mineru_adapter.py", "src/palimpsest/paddle_adapter.py",
            "src/palimpsest/information.py", "src/palimpsest/d2i.py",
            "src/palimpsest/source_units.py", "src/palimpsest/compiler_runtime.py",
            "src/palimpsest/source_groups.py", "src/palimpsest/section_projection.py",
            "src/palimpsest/figure_references.py",
            "src/palimpsest/figure_adapter.py", "src/palimpsest/figure_coverage.py",
            "deploy/mineru/run_parser.py", "deploy/paddleocr/run_parser.py",
        ):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"Synthetic implementation-hash fixture, not application source")
        self.manifest = self.root / "manifest.json"
        self.manifest.write_bytes('[\r\n  {"name": "layout", "note": "원문"}\r\n]\r\n'.encode())
        self.selected_digest = "sha256:" + "b" * 64
        self.rebuilt_digest = "sha256:" + "c" * 64
        self.tag_digest = self.selected_digest
        self.calls = []

    def fake_docker(self, arguments, **kwargs):
        self.calls.append(arguments)
        if arguments[:3] == ["docker", "image", "inspect"]:
            selected = self.tag_digest
            # Rebuild the same tag immediately after selection, before manifest loading.
            self.tag_digest = self.rebuilt_digest
            return selected + "\n"
        self.assertEqual(["docker", "run"], arguments[:2])
        entrypoint = arguments.index("--entrypoint")
        self.assertEqual(self.selected_digest, arguments[entrypoint + 2])
        if arguments[entrypoint + 1] == "cat":
            return self.manifest.read_text(encoding="utf-8")
        self.assertEqual("python", arguments[entrypoint + 1])
        # Run the worker's real byte-hashing snippet against a temporary fixture.
        # This executes no Docker command and makes no network or provider call.
        snippet = arguments[-1].replace('"/models/manifest.json"', repr(str(self.manifest)))
        result = subprocess.run([sys.executable, "-B", "-c", snippet],
                                capture_output=True, text=True, encoding="utf-8", check=True)
        return result.stdout

    def make_worker(self, provider="paddleocr-vl"):
        args = worker_module.parse_args([
            "--data-id", "a" * 64, "--work-dir", str(self.root / "work"),
            "--parser", provider, "--parser-image", "mutable-parser:latest",
        ])
        return worker_module.Worker(args)

    def test_paddle_manifest_hash_uses_exact_bytes_before_newline_translation(self):
        worker = self.make_worker()
        with patch.object(worker_module, "command", self.fake_docker):
            profile = worker.profile()
        expected = sha256(self.manifest.read_bytes()).hexdigest()
        translated = sha256(self.manifest.read_text(encoding="utf-8").encode()).hexdigest()
        self.assertNotEqual(expected, translated, "Fixture must exercise CRLF conversion")
        self.assertEqual(expected, profile["parser"]["models_manifest_sha256"])
        self.assertEqual(json.loads(self.manifest.read_bytes()), profile["parser"]["model_manifest"])
        self.assertEqual(self.selected_digest, profile["parser"]["image_digest"])

    def test_manifest_probe_and_parser_launch_keep_selected_image_after_tag_rebuild(self):
        for provider in ("paddleocr-vl", "mineru"):
            with self.subTest(provider=provider):
                self.tag_digest = self.selected_digest
                self.calls.clear()
                worker = self.make_worker(provider)
                with patch.object(worker_module, "command", self.fake_docker):
                    profile = worker.profile()
                self.assertEqual(self.rebuilt_digest, self.tag_digest)
                arguments = worker.parser_command(worker.work / "parser", "test-container")
                image = arguments[arguments.index("--entrypoint") + 2]
                self.assertEqual(profile["parser"]["image_digest"], image)
                self.assertEqual(self.selected_digest, image)
                self.assertNotIn("mutable-parser:latest", arguments)
                self.assertNotIn(self.rebuilt_digest, arguments)
                self.assertEqual(1, sum(call[:3] == ["docker", "image", "inspect"] for call in self.calls))


if __name__ == "__main__":
    unittest.main()
