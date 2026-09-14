"""Synthetic Paddle output-contract checks; no live parser/model/DB evaluation."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.paddle_adapter import normalize_paddle
from palimpsest.source_units import build_source_units, verify_source_units


DATA_ID = "a" * 64
PROFILE = {"provider": "paddleocr-vl", "adapter_version": "paddleocr-raw-v1", "version": "3.7.0",
           "models_manifest_sha256": "b" * 64,
           "fixture": "synthetic; not a verified runtime profile"}


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@unittest.skipUnless(sys.platform == "linux", "Secure artifact I/O requires the Linux Docker runtime")
class PaddleAdapterTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "crops").mkdir()
        self.image = b"synthetic crop integrity fixture; not a decoded image"
        (self.root / "crops" / "figure.png").write_bytes(self.image)
        labels = ["header", "doc_title", "paragraph_title", "text", "image",
                  "figure_title", "table", "formula", "reference", "footer", "number"]
        contents = ["Header", "Paper", "Results", "  Cafe\u0301\r\n본문  ", "",
                    "Figure 1. Exact caption", "<table><tr><td>1</td></tr></table>",
                    r"x^2=1", "Reference", "Footer", "1"]
        blocks = [{"block_id": i, "block_label": label, "block_content": text,
                   "block_bbox": [20, i * 100, 1000, i * 100 + 90],
                   "block_order": None if i == 0 else i, "unexpected_metadata": {"keep": True}}
                  for i, (label, text) in enumerate(zip(labels, contents))]
        self.raw = {"schema_version": "paddleocr-raw-v1", "data_id": DATA_ID, "page_count": 2,
            "models_manifest_sha256": "b" * 64, "versions": {"paddleocr": "3.7.0"}, "pages": [
            {"page_index": 0, "pdf_size": [600, 800], "render_size": [1200, 1600],
             "rotation": 0, "cropbox": [10, 20, 610, 820], "source_box": "crop",
             "result": {"width": 1200, "height": 1600, "parsing_res_list": blocks,
                        "model_settings": {"use_doc_preprocessor": False, "merge_layout_blocks": False}},
             "image_assets": [{"block_id": 4, "path": "crops/figure.png",
                               "sha256": sha256(self.image).hexdigest(), "bbox": blocks[4]["block_bbox"]}]},
            {"page_index": 1, "pdf_size": [600, 800], "render_size": [1200, 1600],
             "rotation": 0, "cropbox": [0, 0, 600, 800], "source_box": "crop",
             "result": {"width": 1200, "height": 1600, "parsing_res_list": [],
                        "model_settings": {"use_doc_preprocessor": False, "merge_layout_blocks": False}}, "image_assets": []}]}

    def normalize(self, raw):
        return normalize_paddle(raw, data_id=DATA_ID, artifact_root=self.root,
                                expected_pages=2, profile=PROFILE)

    def test_source_units_retain_every_raw_block_crop_and_original_page(self):
        frozen = deepcopy(self.raw)
        bundle = self.normalize(self.raw)
        self.assertEqual(frozen, self.raw)
        self.assertEqual(bundle, self.normalize(self.raw))
        self.assertEqual([0, 1], [page["page_index"] for page in bundle["pages"]])
        self.assertEqual(len(frozen["pages"][0]["result"]["parsing_res_list"]), len(bundle["blocks"]))
        for i, block in enumerate(bundle["blocks"]):
            original = frozen["pages"][0]["result"]["parsing_res_list"][i]
            self.assertEqual(f"/pages/0/result/parsing_res_list/{i}", block["raw_locator"])
            self.assertEqual(original["block_content"], block["text"])
            self.assertEqual(original["block_bbox"], block["upstream_bbox"])
            for expected, actual in zip([n / 2 for n in original["block_bbox"]], block["bbox"]):
                self.assertAlmostEqual(expected, actual, places=10)
            self.assertEqual(original["unexpected_metadata"], block["upstream_metadata"]["unexpected_metadata"])
            self.assertEqual(digest(original), block["raw_block_sha256"])
            self.assertEqual(digest({"data_id": DATA_ID, **{k: v for k, v in block.items() if k != "anchor_sha256"}}),
                             block["anchor_sha256"])
        proposals = build_source_units(bundle)
        ledger = verify_source_units(bundle, proposals)
        self.assertEqual("complete", ledger["status"])
        self.assertEqual(11, ledger["original_block_count"])
        self.assertEqual("image", proposals[4]["unit_type"])
        self.assertEqual("table", proposals[6]["unit_type"])
        self.assertEqual("equation", proposals[7]["unit_type"])
        self.assertEqual([{ "path": "crops/figure.png", "sha256": sha256(self.image).hexdigest()}],
                         bundle["blocks"][4]["image_paths"])

    def test_invalid_geometry_missing_blocks_and_unsafe_crops_cannot_be_accepted(self):
        mutations = [
            lambda r: r.update(models_manifest_sha256="c" * 64),
            lambda r: r.update(page_count=14),
            lambda r: r["versions"].update(paddleocr="3.6.0"),
            lambda r: r["pages"].pop(),
            lambda r: r["pages"][0].update(rotation=90),
            lambda r: r["pages"][0].update(cropbox=[10, 20, 609, 820]),
            lambda r: r["pages"][0]["result"].update(width=1199),
            lambda r: r["pages"][0]["result"]["model_settings"].update(use_doc_preprocessor=True),
            lambda r: r["pages"][0]["result"]["model_settings"].pop("merge_layout_blocks"),
            lambda r: r["pages"][0]["result"]["parsing_res_list"][1].update(block_id=0),
            lambda r: r["pages"][0]["result"]["parsing_res_list"][0].update(block_bbox=[-1, 0, 20, 20]),
            lambda r: r["pages"][0]["image_assets"].clear(),
            lambda r: r["pages"][0]["image_assets"][0].update(block_id=99),
            lambda r: r["pages"][0]["image_assets"][0].update(bbox=[0, 0, 20, 20]),
            lambda r: r["pages"][0]["image_assets"][0].update(path="../figure.png"),
            lambda r: r["pages"][0]["image_assets"][0].update(path="crops/missing.png"),
            lambda r: r["pages"][0]["image_assets"][0].update(sha256="b" * 64),
        ]
        for change in mutations:
            raw = deepcopy(self.raw)
            change(raw)
            with self.subTest(change=change), self.assertRaises(PalimpsestError) as caught:
                self.normalize(raw)
            self.assertEqual("invalid_parser_output", caught.exception.code)
        raw = deepcopy(self.raw)
        raw["pages"][0]["result"]["parsing_res_list"][0]["block_label"] = "future_structure"
        bundle = self.normalize(raw)
        self.assertEqual("future_structure", bundle["blocks"][0]["upstream_label"])
        with self.assertRaises(PalimpsestError) as caught:
            build_source_units(bundle)
        self.assertEqual("unsupported_parser_output", caught.exception.code)

    def test_crop_symlinks_and_changed_bytes_are_rejected(self):
        (self.root / "crops" / "link.png").symlink_to(self.root / "crops" / "figure.png")
        raw = deepcopy(self.raw)
        raw["pages"][0]["image_assets"][0]["path"] = "crops/link.png"
        with self.assertRaises(PalimpsestError):
            self.normalize(raw)
        (self.root / "crops" / "figure.png").write_bytes(b"changed crop")
        with self.assertRaises(PalimpsestError):
            self.normalize(self.raw)

    def test_merged_text_cannot_be_accepted_under_an_unrelated_retained_bbox(self):
        # Regression for the live SDK merging distinct columns, placing both
        # strings in the first region while retaining an empty second block.
        raw = deepcopy(self.raw)
        result = raw["pages"][1]["result"]
        result["model_settings"]["merge_layout_blocks"] = True
        result["parsing_res_list"] = [
            {"block_id": 0, "block_label": "text", "block_order": 1,
             "block_content": "Reviewed by:\nAuthor from the other column",
             "block_bbox": [20, 20, 300, 200]},
            {"block_id": 1, "block_label": "text", "block_order": 2,
             "block_content": "", "block_bbox": [600, 20, 1180, 200]},
        ]
        with self.assertRaises(PalimpsestError) as caught:
            self.normalize(raw)
        self.assertEqual("invalid_parser_output", caught.exception.code)
        self.assertEqual("/pages/1/result/model_settings/merge_layout_blocks",
                         caught.exception.details["raw_locator"])


if __name__ == "__main__":
    unittest.main()
