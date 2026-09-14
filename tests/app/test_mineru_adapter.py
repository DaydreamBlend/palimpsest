"""Synthetic output-contract checks, separate from real MinerU parsing."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.mineru_adapter import normalize_middle


DATA_ID = "a" * 64
PROFILE = {"parser": "MinerU", "version": "3.4.5", "backend": "pipeline"}


def text_block(text="Native caption", kind="text", bbox=None):
    return {"type": kind, "bbox": bbox or [10, 20, 200, 60],
            "lines": [{"bbox": bbox or [10, 20, 200, 60],
                       "spans": [{"type": "text", "content": text}]}]}


def middle(*blocks):
    return {"pdf_info": [{"page_idx": 0, "page_size": [600, 800], "para_blocks": list(blocks)}]}


@unittest.skipUnless(sys.platform == "linux", "Secure artifact I/O requires the Linux Docker runtime")
class MinerUAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "images").mkdir()
        self.image = b"synthetic image bytes: file integrity fixture, not an image decoder fixture"
        (self.root / "images/figure.jpg").write_bytes(self.image)

    def normalize(self, value, expected_pages=1):
        return normalize_middle(value, data_id=DATA_ID, artifact_root=self.root,
                                expected_pages=expected_pages, profile=PROFILE)

    def assert_invalid(self, value, expected_pages=1):
        with self.assertRaises(PalimpsestError) as caught:
            self.normalize(value, expected_pages)
        self.assertEqual("invalid_parser_output", caught.exception.code)
        self.assertNotEqual(0, caught.exception.exit_code)

    def image_block(self, image_path="figure.jpg"):
        return {"type": "image", "bbox": [10, 10, 590, 300], "index": 7,
                "blocks": [
                    {"type": "image_body", "bbox": [10, 10, 590, 240],
                     "lines": [{"spans": [{"type": "image", "image_path": image_path}]}]},
                    text_block("FIGURE 1 | caption, n = 3", "image_caption", [10, 250, 590, 300]),
                ]}

    def test_image_parent_aggregates_caption_and_keeps_original_child_pointers(self):
        raw = middle(self.image_block())
        frozen = deepcopy(raw)
        bundle = self.normalize(raw)
        self.assertEqual(frozen, raw)
        self.assertEqual(PROFILE, bundle["profile"])
        self.assertEqual(1, len(bundle["blocks"]))
        block = bundle["blocks"][0]
        self.assertEqual("image", block["type"])
        self.assertEqual([10, 10, 590, 300], block["bbox"])
        self.assertEqual([10, 10, 590, 300], block["upstream_bbox"])
        self.assertEqual("explicit_region_envelope", block["bbox_policy"])
        self.assertIn("n = 3", block["text"])
        self.assertEqual(["image_body", "image_caption"], [child["type"] for child in block["children"]])
        self.assertEqual("/pdf_info/0/para_blocks/0/blocks/1", block["children"][1]["raw_locator"])
        self.assertEqual([10, 250, 590, 300], block["children"][1]["bbox"])
        self.assertEqual([{"path": "images/figure.jpg", "sha256": sha256(self.image).hexdigest()}], block["image_paths"])
        self.assertTrue(block["supported"])
        self.assertFalse(bundle["zero_output"])

    def test_chart_caption_outside_parent_is_grounded_by_explicit_region_envelope(self):
        parent_bbox, caption_bbox = [288, 480, 401, 587], [46, 640, 547, 698]
        raw = {"type": "chart", "bbox": parent_bbox, "index": 7, "blocks": [
            {"type": "chart_body", "bbox": [288, 480, 401, 570], "lines": [
                {"spans": [{"type": "chart", "image_path": "figure.jpg"}]}]},
            text_block("FIGURE 5 | Caption outside the chart.", "chart_caption", caption_bbox),
        ]}
        frozen = deepcopy(raw)
        block = self.normalize(middle(raw))["blocks"][0]
        locator = "/pdf_info/0/para_blocks/0"
        self.assertEqual(frozen, raw)
        self.assertEqual(parent_bbox, block["upstream_bbox"])
        self.assertEqual([46, 480, 547, 698], block["bbox"])
        self.assertEqual("explicit_region_envelope", block["bbox_policy"])
        self.assertEqual([
            {"raw_locator": locator, "type": "chart", "bbox": parent_bbox},
            {"raw_locator": locator + "/blocks/0", "type": "chart_body", "bbox": [288, 480, 401, 570]},
            {"raw_locator": locator + "/blocks/1", "type": "chart_caption", "bbox": caption_bbox},
        ], block["grounding_regions"])
        self.assertEqual(caption_bbox, block["children"][1]["bbox"])
        self.assertEqual(caption_bbox, block["line_regions"][-1]["bbox"])
        self.assertEqual(7, block["upstream_metadata"]["index"])
        self.assertIn("Caption outside the chart", block["text"])

        def digest(value):
            return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()

        self.assertEqual(digest(raw), block["raw_block_sha256"])
        anchor_input = {key: value for key, value in block.items() if key != "anchor_sha256"}
        self.assertEqual(digest({"data_id": DATA_ID, **anchor_input}), block["anchor_sha256"])
        raw["blocks"][1]["bbox"] = [45, 640, 548, 699]
        changed = self.normalize(middle(raw))["blocks"][0]
        self.assertEqual([45, 480, 548, 699], changed["bbox"])
        self.assertNotEqual(block["anchor_sha256"], changed["anchor_sha256"])

    def test_envelope_includes_nested_descendant_blocks_and_preserves_their_pointers(self):
        raw = self.image_block()
        footnote = text_block("Nested footnote", "image_footnote", [5, 500, 595, 550])
        raw["blocks"][1]["blocks"] = [footnote]
        block = self.normalize(middle(raw))["blocks"][0]
        self.assertEqual([5, 10, 595, 550], block["bbox"])
        self.assertEqual([10, 10, 590, 300], block["upstream_bbox"])
        self.assertEqual({"raw_locator": "/pdf_info/0/para_blocks/0/blocks/1/blocks/0",
                          "type": "image_footnote", "bbox": footnote["bbox"]}, block["grounding_regions"][-1])
        self.assertEqual(4, len(block["grounding_regions"]))
        self.assertIn("Nested footnote", block["text"])

    def test_envelope_never_clamps_or_accepts_invalid_descendant_geometry(self):
        for bbox in ([0, 500, 601, 550], [5, 500, 595, float("inf")], [5, 550, 595, 500]):
            raw = self.image_block()
            raw["blocks"][1]["bbox"] = bbox
            with self.subTest(bbox=bbox):
                self.assert_invalid(middle(raw))

    def test_table_html_and_equation_content_remain_structured(self):
        html = "<table><tr><td>dose</td><td>1 μg</td></tr></table>"
        table = {"type": "table", "bbox": [1, 1, 500, 400], "blocks": [
            {"type": "table_body", "bbox": [1, 1, 500, 300], "lines": [
                {"spans": [{"type": "table", "html": html, "image_path": "images/figure.jpg"}]}]},
            text_block("Table 1 caption", "table_caption", [1, 310, 500, 400]),
        ]}
        equation = {"type": "interline_equation", "bbox": [10, 420, 400, 450], "lines": [
            {"spans": [{"type": "interline_equation", "content": r"E = mc^{2}"}]}]}
        blocks = self.normalize(middle(table, equation))["blocks"]
        self.assertEqual(html, blocks[0]["segments"][0]["html"])
        self.assertIn(html, blocks[0]["text"])
        self.assertEqual(r"E = mc^{2}", blocks[1]["segments"][0]["content"])
        self.assertEqual("interline_equation", blocks[1]["segments"][0]["type"])

    def test_anchor_is_repeatable_and_changes_with_bytes_or_text(self):
        raw = middle(self.image_block())
        first = self.normalize(raw)["blocks"][0]["anchor_sha256"]
        self.assertEqual(first, self.normalize(raw)["blocks"][0]["anchor_sha256"])
        (self.root / "images/figure.jpg").write_bytes(b"different image")
        self.assertNotEqual(first, self.normalize(raw)["blocks"][0]["anchor_sha256"])
        first_text = self.normalize(middle(text_block("A")))["blocks"][0]["anchor_sha256"]
        self.assertNotEqual(first_text, self.normalize(middle(text_block("B")))["blocks"][0]["anchor_sha256"])

    def test_unsafe_or_missing_image_paths_fail_without_fallback(self):
        for path in ("../figure.jpg", "/tmp/figure.jpg", "C:/figure.jpg", "https://host/figure.jpg",
                     "images/../figure.jpg", "images\\figure.jpg", "images//figure.jpg", "missing.jpg", "bad\x00.jpg"):
            with self.subTest(path=path):
                self.assert_invalid(middle(self.image_block(path)))

    def test_symlink_image_and_image_directory_are_rejected(self):
        outside = self.root / "outside.jpg"
        outside.write_bytes(self.image)
        (self.root / "images/link.jpg").symlink_to(outside)
        self.assert_invalid(middle(self.image_block("link.jpg")))
        outside_dir = self.root / "outside"
        outside_dir.mkdir()
        (outside_dir / "nested.jpg").write_bytes(self.image)
        (self.root / "images/linked-directory").symlink_to(outside_dir, target_is_directory=True)
        self.assert_invalid(middle(self.image_block("linked-directory/nested.jpg")))

    def test_page_coverage_requires_exact_original_indexes(self):
        self.assert_invalid({})
        self.assert_invalid(middle(text_block()), expected_pages=2)
        for index in (1, -1, True, "0"):
            raw = middle(text_block())
            raw["pdf_info"][0]["page_idx"] = index
            with self.subTest(index=index):
                self.assert_invalid(raw)
        duplicated = middle(text_block())
        duplicated["pdf_info"].append(deepcopy(duplicated["pdf_info"][0]))
        self.assert_invalid(duplicated, expected_pages=2)

    def test_geometry_is_checked_without_clamping_or_inventing(self):
        for bbox in ([0, 0, 601, 20], [-1, 0, 20, 20], [40, 0, 20, 20],
                     [0, 0, float("nan"), 20], [0, True, 20, 20], None):
            raw = middle(text_block())
            raw["pdf_info"][0]["para_blocks"][0]["bbox"] = bbox
            with self.subTest(bbox=bbox):
                self.assert_invalid(raw)
        for size in ([0, 800], [600, float("inf")], [10 ** 1000, 800], [600], None):
            raw = middle(text_block())
            raw["pdf_info"][0]["page_size"] = size
            with self.subTest(size=size):
                self.assert_invalid(raw)

    def test_missing_visual_payload_is_not_hidden_by_its_caption(self):
        raw = self.image_block()
        del raw["blocks"][0]["lines"][0]["spans"][0]["image_path"]
        self.assert_invalid(middle(raw))

    def test_unknown_types_are_retained_and_explicitly_unsupported(self):
        raw = text_block("Unrecognized producer content", "future_block")
        raw["future_metadata"] = {"verbatim": [1, 2, 3]}
        bundle = self.normalize(middle(raw))
        block = bundle["blocks"][0]
        self.assertEqual("future_block", block["type"])
        self.assertEqual("Unrecognized producer content", block["text"])
        self.assertEqual({"verbatim": [1, 2, 3]}, block["upstream_metadata"]["future_metadata"])
        self.assertFalse(block["supported"])
        self.assertEqual([block["block_id"]], bundle["unsupported_block_ids"])

    def test_cross_page_merge_uses_explicit_preproc_original_page_blocks(self):
        first = text_block("first page")
        moved = text_block("second page")
        merged = deepcopy(first)
        merged["lines"] += deepcopy(moved["lines"])
        merged["lines"][1]["spans"][0]["cross_page"] = True
        emptied = {"type": "text", "bbox": [10, 20, 200, 60], "lines": [], "lines_deleted": True}
        raw = {"pdf_info": [
            {"page_idx": 0, "page_size": [600, 800], "para_blocks": [merged], "preproc_blocks": [first]},
            {"page_idx": 1, "page_size": [600, 800], "para_blocks": [emptied], "preproc_blocks": [moved]},
        ]}
        bundle = self.normalize(raw, expected_pages=2)
        self.assertEqual("preproc_blocks", bundle["block_collection"])
        self.assertEqual([0, 1], [block["page_index"] for block in bundle["blocks"]])
        self.assertEqual(["first page", "second page"], [block["text"] for block in bundle["blocks"]])
        self.assertEqual("/pdf_info/1/preproc_blocks/0", bundle["blocks"][1]["raw_locator"])
        del raw["pdf_info"][1]["preproc_blocks"]
        self.assert_invalid(raw, expected_pages=2)

    def test_same_caption_label_on_two_pages_is_never_automatically_merged(self):
        raw = {"pdf_info": [
            {"page_idx": number, "page_size": [600, 800],
             "para_blocks": [text_block("FIGURE 5 | " + part, "image_caption")]}
            for number, part in enumerate(("continued", "remaining description"))
        ]}
        bundle = self.normalize(raw, expected_pages=2)
        self.assertEqual(2, len(bundle["blocks"]))
        self.assertEqual([0, 1], [block["page_index"] for block in bundle["blocks"]])

    def test_discarded_blocks_are_preserved_and_zero_output_is_explicit(self):
        raw = middle(text_block("Body"))
        raw["pdf_info"][0]["discarded_blocks"] = [text_block("Running header", "header")]
        blocks = self.normalize(raw)["blocks"]
        self.assertEqual(["para_blocks", "discarded_blocks"], [b["source_collection"] for b in blocks])
        self.assertEqual("Running header", blocks[1]["text"])
        self.assertTrue(self.normalize(middle())["zero_output"])
        del raw["pdf_info"][0]["para_blocks"]
        self.assert_invalid(raw)


if __name__ == "__main__":
    unittest.main()
