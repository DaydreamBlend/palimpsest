"""Real Linux filesystem checks for the noncanonical Wiki projection cache."""

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from palimpsest.errors import PalimpsestError
from palimpsest.wiki_projection_store import ProjectionStore


@unittest.skipUnless(sys.platform == "linux", "Requires the Linux filesystem adapter")
class ProjectionStoreTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "wiki"
        self.store = ProjectionStore(self.root)

    def assert_code(self, code, action, *args):
        with self.assertRaises(PalimpsestError) as caught:
            action(*args)
        self.assertEqual(code, caught.exception.code)

    def test_exclusive_snapshot_replay_preserves_bytes_and_rejects_changed_content(self):
        value = {"title": "논문", "count": 1}
        self.store.write_json("snapshots/a.json", value)
        saved = (self.root / "snapshots/a.json").stat()
        self.store.write_json("snapshots/a.json", {"count": 1, "title": "논문"})
        self.assertEqual(saved.st_ino, (self.root / "snapshots/a.json").stat().st_ino)
        self.assertEqual(value, self.store.read_json("snapshots/a.json"))
        self.assert_code("wiki_projection_conflict", self.store.write_json,
                         "snapshots/a.json", {"count": 2})
        self.assertEqual(value, self.store.read_json("snapshots/a.json"))
        self.store.write_bytes("exports/paper.md", b"complete\x00\xff")
        self.store.write_bytes("exports/paper.md", b"complete\x00\xff")
        self.assertEqual(b"complete\x00\xff", self.store.read_bytes("exports/paper.md"))
        self.assertEqual([], list(self.root.rglob(".wiki-write-*")))

    def test_atomic_replace_keeps_old_reader_and_failed_replace_keeps_current(self):
        self.store.replace_json("catalog.json", {"version": 1})
        with (self.root / "catalog.json").open("rb") as previous:
            self.store.replace_json("catalog.json", {"version": 2})
            self.assertEqual(b'{"version":1}', previous.read())
        self.assertEqual({"version": 2}, self.store.read_json("catalog.json"))
        with patch("palimpsest.wiki_projection_store.os.replace", side_effect=OSError("interrupted")):
            self.assert_code("storage_error", self.store.replace_json,
                             "catalog.json", {"version": 3})
        self.assertEqual({"version": 2}, self.store.read_json("catalog.json"))
        self.assertEqual([], list(self.root.rglob(".wiki-write-*")))

    def test_unmanaged_root_or_wrong_marker_is_rejected_without_side_effects(self):
        unmanaged = self.base / "unmanaged"
        unmanaged.mkdir()
        (unmanaged / "user.txt").write_bytes(b"user file")
        self.assert_code("wiki_projection_unmanaged_root", ProjectionStore, unmanaged)
        self.assertEqual(["user.txt"], os.listdir(unmanaged))
        marker = self.root / ".paper-wiki.json"
        marker.write_bytes(b'{"canonical":true}')
        self.assert_code("wiki_projection_unmanaged_root", ProjectionStore, self.root)
        self.assertEqual([".paper-wiki.json"], os.listdir(self.root))

    def test_paths_and_symlinks_cannot_reach_outside_or_overwrite_marker(self):
        for relative in ("", ".", "../outside", "/tmp/outside", "C:\\outside",
                         "a/../../outside", ".paper-wiki.json", "locks/anything"):
            with self.subTest(relative=relative):
                self.assert_code("unsafe_path", self.store.write_bytes, relative, b"changed")
                self.assert_code("unsafe_path", self.store.read_bytes, relative)
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "value.json").write_bytes(b'{"untouched":true}')
        (self.root / "linked").symlink_to(outside, target_is_directory=True)
        (self.root / "direct.json").symlink_to(outside / "value.json")
        for path in ("linked/value.json", "direct.json"):
            self.assert_code("unsafe_path", self.store.read_bytes, path)
            self.assert_code("unsafe_path", self.store.write_bytes, path, b"changed")
            self.assert_code("unsafe_path", self.store.replace_json, path, {})
        root_alias = self.base / "root-alias"
        root_alias.symlink_to(self.root, target_is_directory=True)
        self.assert_code("unsafe_path", ProjectionStore, root_alias)
        self.assert_code("unsafe_path", ProjectionStore, root_alias / "new-child")
        self.assertFalse((self.root / "new-child").exists())
        self.assertEqual(b'{"untouched":true}', (outside / "value.json").read_bytes())

    def test_json_missing_default_does_not_hide_corrupt_content(self):
        self.assertEqual({"new": True}, self.store.read_json("jobs/missing.json", {"new": True}))
        self.assertFalse((self.root / "jobs").exists())
        self.store.write_bytes("jobs/bad.json", b"{truncated")
        self.assert_code("wiki_projection_conflict", self.store.read_json, "jobs/bad.json")

    def test_concurrent_exclusive_writers_never_overwrite_the_winner(self):
        ready = threading.Barrier(2)

        def write(content):
            ready.wait(timeout=2)
            try:
                self.store.write_bytes("snapshots/race.json", content)
            except PalimpsestError as error:
                self.assertEqual("wiki_projection_conflict", error.code)
                return None
            return content

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, [b'{"version":1}', b'{"version":2}']))
        winner = [content for content in results if content is not None]
        self.assertEqual(1, len(winner))
        self.assertEqual(winner[0], self.store.read_bytes("snapshots/race.json"))
        self.assertEqual([], list(self.root.rglob(".wiki-write-*")))

    def test_concurrent_initialization_and_shared_lock_serialize_updates(self):
        concurrent_root = self.base / "concurrent"
        with ThreadPoolExecutor(max_workers=4) as pool:
            stores = list(pool.map(lambda _: ProjectionStore(concurrent_root), range(12)))
        self.assertEqual([".paper-wiki.json"], os.listdir(concurrent_root))
        attempting, acquired = threading.Event(), threading.Event()

        def contender():
            attempting.set()
            with stores[1].locked():
                acquired.set()
                value = stores[1].read_json("catalog.json")
                stores[1].replace_json("catalog.json", {"count": value["count"] + 1})

        with ThreadPoolExecutor(max_workers=1) as pool:
            with stores[0].locked():
                stores[0].replace_json("catalog.json", {"count": 1})
                future = pool.submit(contender)
                self.assertTrue(attempting.wait(2))
                self.assertFalse(acquired.wait(0.1))
            future.result(timeout=2)
        self.assertEqual({"count": 2}, stores[0].read_json("catalog.json"))
        self.assertEqual(1, len(list((concurrent_root / "locks").glob("*.lock"))))


if __name__ == "__main__":
    unittest.main()
