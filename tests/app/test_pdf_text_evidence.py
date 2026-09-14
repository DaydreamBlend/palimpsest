"""Native character provenance and deterministic review signals; no inference."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.pdf_text_evidence import analyze_pdf_text, extract_pdf_text


DATA = "a" * 64


def evidence(lines):
    chars = []
    for y, segments in lines:
        x = 10
        for text, font, weight, size in segments:
            for value in text:
                index = len(chars)
                chars.append({"index": index, "text": value, "unicode": ord(value),
                    "font": font, "weight": weight, "size": size, "flags": 0, "angle": 0,
                    "bbox": [x, y, x+5, y+10], "inside_crop": True, "generated": 0,
                    "unicode_map_error": 0, "raw_locator": f"/pages/0/chars/{index}"})
                x += 5
        index = len(chars)
        chars.append({"index": index, "text": "\n", "unicode": 10, "font": None,
            "weight": -1, "size": 0, "flags": None, "angle": 0, "bbox": None,
            "inside_crop": False, "generated": 1, "unicode_map_error": 0,
            "raw_locator": f"/pages/0/chars/{index}"})
    return {"schema_version": "pdf-native-text-v1", "data_id": DATA,
        "pages": [{"page_index": 0, "page_size": [500, 500], "rotation": 0,
                   "cropbox": [0, 0, 500, 500], "source_box": "crop", "chars": chars,
                   "native_text_status": "available", "native_mapping_warning_count": 0}]}


def bundle(text="", box=None):
    blocks = [] if not text else [{"page_index": 0, "text": text, "raw_locator": "/pdf_info/0/preproc_blocks/0",
        "raw_block_sha256": "b" * 64, "upstream_bbox": box or [10, 10, 490, 30],
        "line_regions": [], "grounding_regions": []}]
    return {"data_id": DATA, "coordinate_system": "pdf_points_top_left",
            "pages": [{"page_index": 0, "page_size": [500, 500]}], "blocks": blocks}


def pdf_bytes(*, rotate=0, crop="0 0 200 200", text=True, scaled=False):
    # Minimal synthetic native-text PDF; standard-library fixture, no renderer.
    content = b"BT /F1 12 Tf 20 150 Td (Exact PDF text.) Tj ET" if text else b""
    if text and scaled:
        content = b"BT /F1 1 Tf 12 0 0 12 20 150 Tm (Exact PDF text.) Tj ET"
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /CropBox [{crop}] /Rotate {rotate} /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"]
    raw, offsets = b"%PDF-1.4\n", [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(raw)); raw += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    start = len(raw)
    raw += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    raw += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    return raw + f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()


class PdfTextEvidenceTests(unittest.TestCase):
    def test_regular_font_weight_is_not_a_bold_signal_and_subset_b_suffix_is(self):
        native = evidence([(10, [("Body remains regular.", "MinionPro-Regular", 712, 10)]),
                           (35, [("Methods.", "AdvOT6c1def61.B", 0, 10)])])
        candidates = analyze_pdf_text(native, bundle())["heading_candidates"]
        self.assertEqual(["Methods."], [c["text"] for c in candidates])

    def test_inline_bold_boundary_keeps_body_and_exact_source_range(self):
        native = evidence([(10, [("Methods. ", "Body-Bold", 700, 10), ("The body remains here.", "Body", 400, 10)]),
                           (30, [("More ordinary body text.", "Body", 400, 10)])])
        original = deepcopy(native)
        result = analyze_pdf_text(native, bundle())
        self.assertEqual(["Methods."], [c["text"] for c in result["heading_candidates"]])
        heading = result["heading_candidates"][0]
        self.assertEqual([[0, 8]], heading["char_ranges"])
        self.assertIn("inline_emphasis_boundary", heading["signals"])
        self.assertEqual("candidate_only", heading["authority"])
        self.assertEqual(original, native)

    def test_mixed_font_math_keeps_beta_inside_bold_heading(self):
        native = evidence([(10, [("TGF-", "Body-Bold", 700, 10), ("β", "Symbol", 400, 10),
                                 (" response", "Body-Bold", 700, 10)]),
                           (35, [("An ordinary body paragraph sets the body size.", "Body", 400, 10)])])
        result = analyze_pdf_text(native, bundle())
        self.assertEqual("TGF-β response", result["heading_candidates"][0]["text"])
        self.assertEqual([[0, 14]], result["heading_candidates"][0]["char_ranges"])

    def test_spatial_alignment_excludes_other_column_and_retains_raw_symbol_diff(self):
        native = evidence([(10, [("P</ β α", "Body", 400, 10)])])
        # Add a competing column at the same vertical position.
        extra = deepcopy(native["pages"][0]["chars"][:3])
        for c in extra:
            c["index"] = len(native["pages"][0]["chars"])
            c["raw_locator"] = f"/pages/0/chars/{c['index']}"
            c["bbox"] = [300, 10, 305, 20]
            native["pages"][0]["chars"].append(c)
        result = analyze_pdf_text(native, bundle("P</ - \x03", [9, 9, 50, 21]))
        row = result["discrepancies"][0]
        self.assertEqual("P</ β α", row["native_text"])
        self.assertEqual("P</ - \x03", row["parser_text"])
        self.assertIn("parser_control_characters", row["warnings"])
        self.assertEqual("spatial_candidate_uncertain", row["alignment_status"])
        codepoints = [point for change in row["raw_diff"] for point in change["native_codepoints"]]
        self.assertIn("U+03B2", codepoints)
        self.assertIn("U+03B1", codepoints)
        self.assertTrue(row["parser_refs"][0]["raw_block_sha256"])

    def test_rotated_or_mismatched_crop_geometry_is_not_silently_aligned(self):
        native = evidence([(10, [("Body", "Body", 400, 10)])])
        for key, value in (("rotation", 90), ("cropbox", [0, 0, 499, 500])):
            changed = deepcopy(native); changed["pages"][0][key] = value
            with self.assertRaises(PalimpsestError) as caught:
                analyze_pdf_text(changed, bundle())
            self.assertEqual("unsupported_pdf_geometry", caught.exception.code)

    def test_native_unavailable_is_explicit_without_ocr(self):
        native = evidence([])
        native["pages"][0]["native_text_status"] = "native_text_unavailable"
        result = analyze_pdf_text(native, bundle("OCR may have transcribed this."))
        self.assertEqual([], result["heading_candidates"])
        self.assertEqual("native_text_unavailable", result["page_status"][0]["status"])
        self.assertEqual("native_text_unavailable_in_region", result["discrepancies"][0]["kind"])

    @unittest.skipUnless(importlib.util.find_spec("pypdfium2"), "PDFium integration runs in the existing Hybrid image")
    def test_real_pdfium_character_indices_fonts_hash_and_crop_coordinates(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.pdf"
            payload = pdf_bytes(crop="10 20 190 190")
            path.write_bytes(payload)
            native = extract_pdf_text(path, data_id=sha256(payload).hexdigest())
            page = native["pages"][0]
            self.assertEqual([180, 170], page["page_size"])
            self.assertEqual([10, 20, 190, 190], page["cropbox"])
            self.assertEqual("Exact PDF text.", "".join(c["text"] for c in page["chars"]))
            self.assertEqual(list(range(15)), [c["index"] for c in page["chars"]])
            self.assertTrue(all(c["font"] == "Helvetica" and c["size"] == 12 for c in page["chars"]))
            char = page["chars"][0]
            self.assertAlmostEqual(char["bbox_pdf"][0]-10, char["bbox"][0])
            self.assertAlmostEqual(190-char["bbox_pdf"][3], char["bbox"][1])
            self.assertEqual([[0, 15]], [span["char_range"] for span in page["spans"]])
            payload = pdf_bytes(scaled=True); path.write_bytes(payload)
            scaled = extract_pdf_text(path, data_id=sha256(payload).hexdigest())["pages"][0]["chars"][0]
            self.assertEqual(1, scaled["size"])
            self.assertEqual(12, scaled["effective_size"])
            self.assertEqual([12, 0, 0, 12], scaled["text_matrix"][:4])
            with self.assertRaises(PalimpsestError) as caught:
                extract_pdf_text(path, data_id=DATA)
            self.assertEqual("integrity_conflict", caught.exception.code)
            payload = pdf_bytes(rotate=90); path.write_bytes(payload)
            with self.assertRaises(PalimpsestError) as caught:
                extract_pdf_text(path, data_id=sha256(payload).hexdigest())
            self.assertEqual("unsupported_pdf_geometry", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
