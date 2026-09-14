"""Synthetic Figure inventory contract tests, without PDF/model/DB execution.

The fixture has six reviewed Figure regions and 249 normalized source blocks.
Crop bytes are integrity fixtures, not rendered or visually reviewed images.
These checks cannot establish a human inventory's semantic completeness.
"""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.figure_adapter import INVENTORY_NAME, attach_figures


DATA_ID = sha256(b"synthetic source PDF bytes").hexdigest()
MIDDLE_SHA256 = sha256(b"synthetic retained MinerU middle JSON bytes").hexdigest()


@unittest.skipUnless(sys.platform == "linux", "Secure asset reads require the Linux Docker runtime")
class FigureAdapterTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix="palimpsest-figure-adapter-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "parser-output"
        (self.root / "images").mkdir(parents=True)
        self.path = self.root / INVENTORY_NAME
        self.bundle = {"schema_version": 1, "data_id": DATA_ID,
                       "profile": {"provider": "mineru", "fixture": "synthetic"},
                       "coordinate_system": "pdf_points_top_left", "zero_output": False,
                       "pages": [{"page_index": index, "page_size": [600, 800]} for index in range(6)],
                       "blocks": [], "unsupported_block_ids": []}
        self.inventory = {"schema_version": "figure-inventory-v1", "data_id": DATA_ID,
                          "middle_sha256": MIDDLE_SHA256, "extraction_scope": "figures_only",
                          "source": "reviewed_original_pdf_regions",
                          "renderer": {"name": "synthetic-no-renderer-called", "dpi": 300}, "figures": []}
        for page in range(6):
            members = []
            for panel, bbox in enumerate(([50, 60, 200, 180], [220, 60, 370, 180])):
                block = self._block(f"/pdf_info/{page}/preproc_blocks/{panel}", page, "chart", bbox)
                asset = self._asset(f"panel-{page}-{panel}.png", f"synthetic panel {page}/{panel}".encode())
                block["image_paths"] = [{"path": asset["path"], "sha256": asset["sha256"]}]
                block["children"] = [{"type": "chart_body", "bbox": list(bbox),
                                      "raw_locator": block["raw_locator"] + "/blocks/0"}]
                self.bundle["blocks"].append(block)
                members.append(block["block_id"])
            caption = self._block(f"/pdf_info/{page}/preproc_blocks/2", page, "text", [40, 210, 380, 250],
                                  f"Figure {page + 1}: synthetic caption with context.")
            self.bundle["blocks"].append(caption)
            self.inventory["figures"].append({
                "number": page + 1, "page_index": page, "bbox": [40, 50, 380, 190],
                "member_block_ids": members, "caption_block_ids": [caption["block_id"]],
                "image": self._asset(f"figure-{page + 1}.png", f"synthetic full Figure {page + 1}".encode()),
                "source_region": {"coordinate_system": "pdf_points_top_left", "review": "synthetic fixture"},
            })
        for ordinal in range(231):
            self.bundle["blocks"].append(self._block(f"/synthetic_context/{ordinal}", 0, "text", [10, 300, 590, 320],
                                                     "Synthetic unrelated source context."))

    @staticmethod
    def _block(identifier, page, kind, bbox, text=""):
        return {"block_id": identifier, "raw_locator": identifier, "page_index": page,
                "type": kind, "bbox": list(bbox), "upstream_bbox": list(bbox), "page_size": [600, 800],
                "bbox_policy": "explicit_region_envelope", "image_paths": [], "text": text,
                "children": [], "supported": True, "unsupported": [], "empty": False,
                "anchor_sha256": sha256(identifier.encode()).hexdigest()}

    def _asset(self, name, data):
        relative = "images/" + name
        (self.root / relative).write_bytes(data)
        return {"path": relative, "sha256": sha256(data).hexdigest(), "byte_size": len(data)}

    def _write(self, inventory=None):
        value = self.inventory if inventory is None else inventory
        data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.path.write_bytes(data)
        return sha256(data).hexdigest()

    def _attach(self, inventory=None, *, expected_sha256=None, middle_sha256=MIDDLE_SHA256, root=None):
        expected_sha256 = expected_sha256 or self._write(inventory)
        return attach_figures(self.bundle, artifact_root=self.root if root is None else root,
                              expected_sha256=expected_sha256, middle_sha256=middle_sha256)

    def _assert_rejected(self, action):
        with self.assertRaises(PalimpsestError) as caught:
            action()
        self.assertIn(caught.exception.code, {"invalid_figure_inventory", "invalid_parser_output"})
        self.assertNotEqual(0, caught.exception.exit_code)

    def test_six_figures_are_additive_and_original_249_blocks_are_unchanged(self):
        original = deepcopy(self.bundle)
        inventory = deepcopy(self.inventory)
        result = self._attach()
        self.assertEqual(original, self.bundle)
        self.assertEqual(inventory, self.inventory)
        self.assertEqual(original["blocks"], result["blocks"][:249])
        self.assertEqual(255, len(result["blocks"]))
        self.assertEqual([f"figure:{number}" for number in range(1, 7)],
                         [group["figure_id"] for group in result["required_figures"]])
        self.assertEqual("figures_only", result["extraction_scope"])
        self.assertEqual(sha256(self.path.read_bytes()).hexdigest(), result["figure_inventory_sha256"])
        for index, block in enumerate(result["blocks"][249:]):
            figure = self.inventory["figures"][index]
            self.assertEqual(f"/figures/{index}", block["block_id"])
            self.assertEqual("image", block["type"])
            self.assertEqual(figure["bbox"], block["bbox"])
            self.assertEqual("reviewed_original_pdf_figure_region", block["bbox_policy"])
            self.assertIsNone(block["upstream_bbox"])
            self.assertEqual(figure["member_block_ids"], block["member_block_ids"])
            self.assertEqual(figure["caption_block_ids"], block["caption_block_ids"])
            self.assertEqual(DATA_ID, block["figure_provenance"]["data_id"])
            self.assertEqual(MIDDLE_SHA256, block["figure_provenance"]["middle_sha256"])
            self.assertEqual(self.inventory["renderer"], block["figure_provenance"]["renderer"])
            self.assertEqual(result["figure_inventory_sha256"], block["figure_provenance"]["inventory_sha256"])
            self.assertEqual(figure["image"]["sha256"], block["image_paths"][0]["sha256"])
            self.assertEqual(f"{INVENTORY_NAME}#/figures/{index}", block["raw_locator"])
            self.assertEqual([{ "raw_locator": block["raw_locator"], "type": "image", "bbox": figure["bbox"]}],
                             block["grounding_regions"])
        result["blocks"][0]["bbox"][0] = 999
        self.assertEqual(original, self.bundle)

    def test_same_exact_inventory_replays_deterministically_and_changed_inventory_changes_anchor(self):
        first = self._attach()
        self.assertEqual(first, self._attach())
        changed = deepcopy(self.inventory)
        changed["renderer"]["dpi"] = 301
        second = self._attach(changed)
        self.assertNotEqual(first["figure_inventory_sha256"], second["figure_inventory_sha256"])
        self.assertNotEqual(first["blocks"][249]["anchor_sha256"], second["blocks"][249]["anchor_sha256"])

    def test_each_of_six_figures_rejects_a_missing_panel_member(self):
        for index in range(6):
            inventory = deepcopy(self.inventory)
            inventory["figures"][index]["member_block_ids"].pop()
            with self.subTest(figure=index + 1):
                self._assert_rejected(lambda: self._attach(inventory))

    def test_visual_body_centers_are_used_instead_of_caption_inflated_parent_boxes(self):
        for block in self.bundle["blocks"][:18]:
            if block["image_paths"]:
                block["bbox"] = [0, 0, 600, 800]
                block["upstream_bbox"] = [0, 0, 600, 800]
        self.assertEqual(6, len(self._attach()["required_figures"]))

    def test_caption_remains_a_separate_exact_ref_and_can_continue_on_another_page(self):
        figure = self.inventory["figures"][0]
        caption_id = figure["caption_block_ids"][0]
        continuation = self._block("/pdf_info/1/preproc_blocks/continued_caption", 1, "text", [40, 20, 550, 70],
                                   "Synthetic Figure 1 caption continued on the next page.")
        self.bundle["blocks"].append(continuation)
        figure["caption_block_ids"].append(continuation["block_id"])
        original = deepcopy(self.bundle)
        block = self._attach()["blocks"][250]
        self.assertEqual(original, self.bundle)
        self.assertEqual(0, block["page_index"])
        self.assertEqual([40, 50, 380, 190], block["bbox"])
        self.assertEqual([caption_id, continuation["block_id"]], block["caption_block_ids"])
        self.assertNotIn(continuation["text"], block["text"])
        self.assertEqual(1, original["blocks"][-1]["page_index"])

    def test_missing_duplicate_unknown_or_wrong_typed_refs_are_rejected(self):
        for field in ("member_block_ids", "caption_block_ids"):
            for refs in ([], None, "not-an-array", ["/unknown"], [True],
                         [self.inventory["figures"][0][field][0]] * 2):
                inventory = deepcopy(self.inventory)
                inventory["figures"][0][field] = refs
                with self.subTest(field=field, refs=refs):
                    self._assert_rejected(lambda: self._attach(inventory))

    def test_caption_refs_require_source_text_instead_of_body_only_visuals(self):
        inventory = deepcopy(self.inventory)
        inventory["figures"][0]["caption_block_ids"] = [inventory["figures"][0]["member_block_ids"][0]]
        self._assert_rejected(lambda: self._attach(inventory))

    def test_wrong_page_and_visual_reuse_across_figures_are_rejected(self):
        inventory = deepcopy(self.inventory)
        inventory["figures"][0]["member_block_ids"].append(inventory["figures"][1]["member_block_ids"][0])
        self._assert_rejected(lambda: self._attach(inventory))
        inventory = deepcopy(self.inventory)
        inventory["figures"][1] = {**deepcopy(inventory["figures"][0]), "number": 2}
        self._assert_rejected(lambda: self._attach(inventory))

    def test_source_middle_and_exact_inventory_bytes_are_bound(self):
        inventory = deepcopy(self.inventory)
        inventory["data_id"] = "0" * 64
        self._assert_rejected(lambda: self._attach(inventory))
        self._assert_rejected(lambda: self._attach(middle_sha256="0" * 64))
        expected = self._write()
        truncated = deepcopy(self.inventory)
        truncated["figures"].pop()
        self._write(truncated)
        self._assert_rejected(lambda: self._attach(expected_sha256=expected))

    def test_partial_or_malformed_inventory_never_becomes_success(self):
        for field in ("schema_version", "data_id", "middle_sha256", "extraction_scope", "source", "renderer", "figures"):
            inventory = deepcopy(self.inventory)
            del inventory[field]
            with self.subTest(missing=field):
                self._assert_rejected(lambda: self._attach(inventory))
        for value in ({}, [], {**self.inventory, "figures": []}, {**self.inventory, "renderer": {}},
                      {**self.inventory, "figures": [None]}, {**self.inventory, "extraction_scope": "all_content"}):
            self._assert_rejected(lambda: self._attach(value))
        invalid = b"{not JSON"
        self.path.write_bytes(invalid)
        self._assert_rejected(lambda: self._attach(expected_sha256=sha256(invalid).hexdigest()))

    def test_figure_numbers_pages_and_geometry_are_validated(self):
        for field, value in (("number", 0), ("number", True), ("number", 1.0), ("number", 2),
                             ("page_index", -1), ("page_index", 6), ("page_index", True),
                             ("bbox", [0, 0, 601, 190]), ("bbox", [0, 0, 380, 0]),
                             ("bbox", [380, 50, 40, 190]), ("bbox", [0, 0, float("nan"), 190])):
            inventory = deepcopy(self.inventory)
            inventory["figures"][0][field] = value
            with self.subTest(field=field, value=value):
                self._assert_rejected(lambda: self._attach(inventory))

    def test_image_hash_size_and_integer_size_type_are_required(self):
        for field, value in (("sha256", "0" * 64), ("byte_size", 999), ("byte_size", -1),
                             ("byte_size", 23.0), ("byte_size", "23")):
            inventory = deepcopy(self.inventory)
            inventory["figures"][0]["image"][field] = value
            with self.subTest(field=field, value=value):
                self._assert_rejected(lambda: self._attach(inventory))
        inventory = deepcopy(self.inventory)
        inventory["figures"][0]["image"] = self._asset("one-byte.png", b"x")
        inventory["figures"][0]["image"]["byte_size"] = True
        self._assert_rejected(lambda: self._attach(inventory))
        (self.root / self.inventory["figures"][0]["image"]["path"]).write_bytes(b"changed crop")
        self._assert_rejected(self._attach)

    def test_missing_unsafe_and_symlink_assets_are_rejected(self):
        for path in ("images/missing.png", "../outside.png", "/tmp/outside.png", "C:/outside.png",
                     "images\\figure-1.png", "images/../figure-1.png", "https://host/image.png"):
            inventory = deepcopy(self.inventory)
            inventory["figures"][0]["image"]["path"] = path
            with self.subTest(path=path):
                self._assert_rejected(lambda: self._attach(inventory))
        image_path = self.root / self.inventory["figures"][0]["image"]["path"]
        outside = self.base / "outside-crop.png"
        outside.write_bytes(image_path.read_bytes())
        image_path.unlink()
        image_path.symlink_to(outside)
        self._assert_rejected(self._attach)

    def test_inventory_or_managed_root_symlinks_are_rejected(self):
        expected = self._write()
        outside = self.base / "outside-inventory.json"
        outside.write_bytes(self.path.read_bytes())
        self.path.unlink()
        self.path.symlink_to(outside)
        self._assert_rejected(lambda: self._attach(expected_sha256=expected))
        self.path.unlink()
        self._write()
        linked = self.base / "linked-parser-output"
        linked.symlink_to(self.root, target_is_directory=True)
        self._assert_rejected(lambda: self._attach(expected_sha256=expected, root=linked))

    def test_new_figure_ids_cannot_overwrite_an_existing_source_block(self):
        self.bundle["blocks"].append(self._block("/figures/0", 0, "text", [1, 1, 20, 20], "Existing source."))
        before = deepcopy(self.bundle)
        self._assert_rejected(self._attach)
        self.assertEqual(before, self.bundle)


if __name__ == "__main__":
    unittest.main()
