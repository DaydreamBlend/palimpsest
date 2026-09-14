"""Synthetic native-PDF visual evidence tests; no model inference or fidelity claim."""

from copy import deepcopy
from hashlib import sha256
import importlib.util
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zlib

from palimpsest.errors import PalimpsestError
from palimpsest.pdf_visual_evidence import build_pdf_visuals


AVAILABLE = all(importlib.util.find_spec(name) is not None for name in ("pypdfium2", "pypdf", "PIL"))


def synthetic_pdf(*, image=True, rotation=0, cropbox=None):
    from pypdf import PdfWriter
    from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject,
                               EncodedStreamObject, NameObject, NumberObject)

    writer = PdfWriter()
    for index in range(2):
        page = writer.add_blank_page(width=300, height=400)
        if cropbox:
            page[NameObject("/CropBox")] = ArrayObject([NumberObject(n) for n in cropbox])
        if rotation:
            page.rotate(rotation)
        content = DecodedStreamObject()
        if index == 0 and image:
            raster = EncodedStreamObject()
            raster.update({NameObject("/Type"): NameObject("/XObject"),
                NameObject("/Subtype"): NameObject("/Image"), NameObject("/Width"): NumberObject(12),
                NameObject("/Height"): NumberObject(12), NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
                NameObject("/BitsPerComponent"): NumberObject(8), NameObject("/Filter"): NameObject("/FlateDecode")})
            raster._data = zlib.compress(bytes([200, 40, 20, 10, 40, 200]) * 72)
            page[NameObject("/Resources")] = DictionaryObject({NameObject("/XObject"):
                DictionaryObject({NameObject("/Im1"): writer._add_object(raster)})})
            content.set_data(b"q 200 0 0 170 50 150 cm /Im1 Do Q")
        else:
            content.set_data(b"q 0.2 0.3 0.8 rg 50 150 200 170 re f Q")
        page[NameObject("/Contents")] = writer._add_object(content)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


@unittest.skipUnless(AVAILABLE, "Native PDF projection tests require the existing PDFium Docker runtime")
class PdfVisualEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.pdf = self.root / "source.pdf"
        self.pdf.write_bytes(synthetic_pdf())
        self.artifacts = self.root / "raw"
        (self.artifacts / "images").mkdir(parents=True)
        # Original parser bytes must never be re-encoded, even in this synthetic fixture.
        self.original = b"synthetic original parser crop bytes"
        (self.artifacts / "images" / "panel.jpg").write_bytes(self.original)
        self.ref = {"path": "images/panel.jpg", "sha256": sha256(self.original).hexdigest()}
        self.bundle = {"schema_version": 1, "data_id": sha256(self.pdf.read_bytes()).hexdigest(),
            "coordinate_system": "pdf_points_top_left", "profile": {"fixture": "synthetic"},
            "pages": [{"page_index": i, "page_size": [300, 400]} for i in range(2)],
            "blocks": [self.block("panel-a", 0, [55, 90, 145, 160]),
                       self.block("panel-b", 0, [155, 90, 245, 160]),
                       self.block("caption", 0, [45, 265, 260, 290], "FIGURE 1 | Synthetic caption. (Continued)"),
                       self.block("continuation", 1, [45, 30, 260, 55], "FIGURE 1 | Caption continuation.")]}

    def block(self, name, page, bbox, text=None):
        locator = f"/pages/{page}/{name}"
        result = {"block_id": locator, "raw_locator": locator, "page_index": page, "bbox": bbox,
                  "type": "image" if text is None else "text", "text": text or ""}
        if text is None:
            result.update({"image_paths": [self.ref], "segments": [{"raw_locator": locator + "/image",
                "bbox": bbox, "type": "image", "image_path": self.ref}]})
        return result

    def build(self, name="export", bundle=None, pdf=None, artifacts=True):
        return build_pdf_visuals(pdf or self.pdf, bundle or self.bundle, self.root / name,
                                 artifact_root=self.artifacts if artifacts else None)

    def test_native_whole_figure_preserves_panels_captions_page_and_exact_inputs(self):
        frozen = deepcopy(self.bundle)
        manifest = self.build()
        self.assertEqual(frozen, self.bundle)
        self.assertEqual(2, len(manifest["pages"]))
        self.assertEqual(2, len(manifest["panels"]))
        self.assertEqual(1, len(manifest["figures"]))
        figure = manifest["figures"][0]
        self.assertEqual("1", figure["number"])
        self.assertEqual([50, 80, 250, 250], figure["region_proposal"]["bbox"])
        self.assertEqual("native_image_object", figure["region_proposal"]["method"])
        self.assertEqual("proposal", figure["certainty"])
        self.assertEqual([0, 1], [c["page_index"] for c in figure["caption_anchors"]])
        self.assertEqual("explicit_continuation_on_adjacent_page", figure["caption_anchors"][1]["association"])
        self.assertEqual([1], [p["page_index"] for p in figure["continuation_page_fallbacks"]])
        for panel in manifest["panels"]:
            asset = panel["parser_asset"]["copied_asset"]
            self.assertEqual(self.original, (self.root / "export" / asset["path"]).read_bytes())
            self.assertEqual(self.ref["sha256"], asset["sha256"])
            self.assertEqual(manifest["pages"][0]["page_image"], panel["whole_page_fallback"])
            self.assertTrue(panel["raw_locator"].startswith(panel["source_block_id"]))
        self.assertEqual(manifest, json.loads((self.root / "export" / "manifest.json").read_text()))
        self.assertEqual(manifest, self.build("replay"))

    def test_vector_or_missing_native_figure_is_uncertain_with_full_page_fallback(self):
        self.pdf.write_bytes(synthetic_pdf(image=False))
        self.bundle["data_id"] = sha256(self.pdf.read_bytes()).hexdigest()
        manifest = self.build()
        figure = manifest["figures"][0]
        self.assertEqual("parser_panel_union", figure["region_proposal"]["method"])
        self.assertEqual([55, 90, 245, 160], figure["region_proposal"]["bbox"])
        self.assertIn("may_omit_labels_or_panels", figure["warnings"][0])
        self.assertEqual(manifest["pages"][0]["page_image"], figure["whole_page_fallback"])

    def test_cropbox_rotation_transform_and_original_page_indices(self):
        self.pdf.write_bytes(synthetic_pdf(rotation=90, cropbox=[20, 30, 280, 390]))
        self.bundle["data_id"] = sha256(self.pdf.read_bytes()).hexdigest()
        self.bundle["pages"] = [{"page_index": i, "page_size": [360, 260]} for i in range(2)]
        self.bundle["blocks"] = [self.block("rotated-panel", 0, [140, 50, 220, 180])]
        manifest = self.build()
        page = manifest["pages"][0]
        self.assertEqual([360, 260], page["page_size"])
        self.assertEqual([20, 30, 280, 390], page["cropbox"])
        self.assertEqual(90, page["rotation"])
        self.assertEqual([120, 30, 290, 230], page["native_images"][0]["bbox"])
        self.assertEqual([720, 520], page["page_image"]["pixel_size"])
        self.assertEqual([0, 1], [p["page_index"] for p in manifest["pages"]])
        self.assertEqual("panels_without_numbered_figure_caption", manifest["warnings"][0]["code"])

    def test_bad_identity_geometry_and_artifact_integrity_fail_without_manifest(self):
        cases = []
        bad = deepcopy(self.bundle); bad["data_id"] = "0" * 64; cases.append(bad)
        bad = deepcopy(self.bundle); bad["pages"][0]["page_index"] = 1; cases.append(bad)
        bad = deepcopy(self.bundle); bad["pages"][0]["page_size"] = [302, 400]; cases.append(bad)
        bad = deepcopy(self.bundle); bad["blocks"][0]["bbox"][0] = -1; cases.append(bad)
        bad = deepcopy(self.bundle); bad["blocks"][0]["bbox"][2] = float("nan"); cases.append(bad)
        bad = deepcopy(self.bundle); bad["blocks"][0]["segments"][0]["image_path"]["path"] = "../escape.jpg"; cases.append(bad)
        bad = deepcopy(self.bundle); bad["blocks"][0]["segments"][0]["image_path"]["sha256"] = "0" * 64; cases.append(bad)
        for i, bundle in enumerate(cases):
            with self.subTest(i=i), self.assertRaises(PalimpsestError):
                self.build(f"bad-{i}", bundle=bundle)
            self.assertFalse((self.root / f"bad-{i}" / "manifest.json").exists())

    def test_existing_output_is_never_overwritten_and_unsafe_symlink_is_rejected(self):
        self.build()
        frozen = (self.root / "export" / "manifest.json").read_bytes()
        with self.assertRaises(PalimpsestError):
            self.build()
        self.assertEqual(frozen, (self.root / "export" / "manifest.json").read_bytes())
        outside = self.root / "external.jpg"
        outside.write_bytes(self.original)
        link = self.artifacts / "images" / "escape.jpg"
        link.symlink_to(outside)
        self.bundle["blocks"][0]["segments"][0]["image_path"]["path"] = "images/escape.jpg"
        with self.assertRaises(PalimpsestError):
            self.build("symlink")

    def test_body_reference_is_not_a_caption_and_missing_assets_remain_explicit_refs(self):
        self.bundle["blocks"][-2]["text"] = "Figure 1 shows the result in the body text."
        self.bundle["blocks"][-1]["text"] = "No caption here."
        result = self.build(artifacts=False)
        self.assertEqual([], result["figures"])
        self.assertEqual(2, len(result["panels"]))
        self.assertIsNone(result["panels"][0]["parser_asset"]["copied_asset"])
        self.assertEqual(self.ref["sha256"], result["panels"][0]["parser_asset"]["sha256"])

    def test_explicit_caption_type_accepts_missing_separator_without_accepting_body_refs(self):
        caption = self.bundle["blocks"][-2]
        locator = caption["raw_locator"] + "/child"
        caption["text"] = "Panel label and a caption"
        caption["children"] = [{"raw_locator": locator, "bbox": caption["bbox"], "type": "image_caption"}]
        caption["segments"] = [{"raw_locator": locator + "/span", "type": "text",
                                "content": "FIGuRE 1 U Synthetic caption (Continued)"}]
        result = self.build()
        self.assertEqual(1, len(result["figures"]))
        self.assertEqual("1", result["figures"][0]["number"])
        anchor = result["figures"][0]["caption_anchors"][0]
        self.assertEqual("FIGuRE 1 U Synthetic caption (Continued)", anchor["text"])
        self.assertEqual("explicit_image_caption_type_and_prefix", anchor["recognition_basis"])


if __name__ == "__main__":
    unittest.main()
