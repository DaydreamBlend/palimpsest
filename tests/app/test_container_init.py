"""Linux bootstrap crash checks on private temporary directories, not real secrets."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "container_init.py"
LINUX = sys.platform == "linux"
if LINUX:
    spec = importlib.util.spec_from_file_location("palimpsest_container_init_test", SCRIPT)
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)


@unittest.skipUnless(LINUX, "Bootstrap uses Linux file locks/fsync in the Docker runtime")
class ContainerInitTests(unittest.TestCase):
    def test_crash_before_and_after_publish_resumes_without_rotation(self):
        child = """
import importlib.util, os, pathlib, sys
spec = importlib.util.spec_from_file_location('bootstrap_child', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original_link = module.os.link
def crash_at_link(source, target, **kwargs):
    if sys.argv[3] == 'after':
        original_link(source, target, **kwargs)
    os._exit(73)
module.os.link = crash_at_link
module.write_secret(pathlib.Path(sys.argv[2]), 'bootstrap-test-value', 0o444)
"""
        for phase in ("before", "after"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "runtime_dsn"
                pending = Path(directory) / ".palimpsest-runtime_dsn.pending"
                unrelated = Path(directory) / "unrelated-file"
                unrelated.write_text("preserve", encoding="utf-8")
                crashed = subprocess.run([sys.executable, "-B", "-c", child, str(SCRIPT), str(target), phase],
                                         capture_output=True, text=True, timeout=15)
                self.assertEqual(crashed.returncode, 73)
                self.assertEqual(crashed.stdout + crashed.stderr, "")
                self.assertTrue(pending.is_file())
                self.assertEqual(target.exists(), phase == "after")
                previous_inode = target.stat().st_ino if target.exists() else None
                bootstrap.write_secret(target, "bootstrap-test-value", 0o444)
                self.assertEqual(target.read_text(encoding="utf-8"), "bootstrap-test-value\n")
                self.assertFalse(pending.exists())
                self.assertEqual(unrelated.read_text(encoding="utf-8"), "preserve")
                self.assertEqual(target.stat().st_mode & 0o777, 0o444)
                if previous_inode is not None:
                    self.assertEqual(target.stat().st_ino, previous_inode)

    def test_partial_pending_is_replaced_but_completed_secret_is_not(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "postgres_password"
            pending = Path(directory) / ".palimpsest-postgres_password.pending"
            pending.write_text("partial", encoding="utf-8")
            bootstrap.write_secret(target, "complete-test-value")
            inode = target.stat().st_ino
            bootstrap.write_secret(target, "complete-test-value")
            with self.assertRaises(RuntimeError):
                bootstrap.write_secret(target, "different-test-value")
            self.assertEqual(target.stat().st_ino, inode)
            self.assertEqual(target.read_text(encoding="utf-8"), "complete-test-value\n")
            self.assertFalse(pending.exists())

    def test_reserved_pending_symlink_does_not_touch_its_target(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "admin_dsn"
            unrelated = Path(directory) / "unrelated-file"
            unrelated.write_text("preserve", encoding="utf-8")
            pending = Path(directory) / ".palimpsest-admin_dsn.pending"
            pending.symlink_to(unrelated)
            with self.assertRaises(RuntimeError):
                bootstrap.write_secret(target, "test-value")
            self.assertTrue(pending.is_symlink())
            self.assertFalse(target.exists())
            self.assertEqual(unrelated.read_text(encoding="utf-8"), "preserve")


if __name__ == "__main__":
    unittest.main()
