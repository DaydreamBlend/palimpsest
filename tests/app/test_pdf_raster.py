"""Native pixel/provenance checks for the fixed OCR renderer; no inference or DB."""

from contextlib import closing
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from palimpsest import pdf_raster


AVAILABLE = all(importlib.util.find_spec(name) is not None for name in ("pypdfium2", "PIL"))


def pdf_bytes(*, boxes=None, rotation=0):
    """Native text and colored vectors, with fractional geometry and crop offsets."""
    boxes = boxes or [([0, 0, 210.37, 230.29], [10.13, 20.17, 200.31, 225.23]),
                      ([0, 0, 201.41, 227.19], [-10, -20, 300, 400])]
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(len(boxes)))
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               f"<< /Type /Pages /Kids [{kids}] /Count {len(boxes)} >>".encode(),
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    for index, (media, crop) in enumerate(boxes):
        media, crop = " ".join(map(str, media)), " ".join(map(str, crop))
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [{media}] /CropBox [{crop}] /Rotate {rotation} /Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * index} 0 R >>".encode())
        content = (b"q 0.8 0.1 0.2 rg 15 25 135 140 re f Q "
                   b"q 0.1 0.4 0.8 rg 50 70 130 100 re f Q "
                   b"BT /F1 12 Tf 20 180 Td (Exact source text.) Tj ET")
        objects.append(b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream")
    raw, offsets = b"%PDF-1.4\n", [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(raw))
        raw += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    start = len(raw)
    raw += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    raw += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    return raw + f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()


def transform(matrix, point):
    a, b, c, d, e, f = matrix
    x, y = point
    return [a * x + c * y + e, b * x + d * y + f]


@unittest.skipUnless(AVAILABLE, "Native raster tests require the pinned PDFium Docker runtime")
class PdfRasterTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "original.pdf"
        self.original = pdf_bytes()
        self.source.write_bytes(self.original)

    def render(self, name="render", **kwargs):
        output = self.root / name
        return output, pdf_raster.render_pdf(self.source, output, **kwargs)

    def write_manifest(self, output, manifest):
        (output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_fractional_effective_pages_keep_pixels_original_identity_and_inverse_maps(self):
        import pypdfium2 as pdfium
        from PIL import Image

        output, manifest = self.render()
        self.assertEqual(self.original, self.source.read_bytes())
        self.assertEqual(sha256(self.original).hexdigest(), manifest["source"]["data_id"])
        self.assertNotEqual(manifest["source"]["data_id"], manifest["derived_pdf"]["sha256"])
        self.assertEqual([0, 1], [p["source_page_index"] for p in manifest["pages"]])
        self.assertEqual(manifest, pdf_raster.verify_render(output, self.source))
        self.assertEqual(manifest, pdf_raster.verify_render(output))
        self.assertNotEqual(manifest["pages"][1]["source_geometry"]["crop_box"],
                            manifest["pages"][1]["source_geometry"]["effective_bbox"])
        with pdfium.PdfDocument(str(self.source)) as native, pdfium.PdfDocument(str(output / "image-only.pdf")) as raster:
            for index, entry in enumerate(manifest["pages"]):
                with closing(native[index]) as page, closing(page.get_textpage()) as text:
                    self.assertGreater(text.count_chars(), 0)
                with closing(raster[index]) as page, closing(page.get_textpage()) as text:
                    self.assertEqual(0, text.count_chars())
                size = entry["source_geometry"]["size"]
                forward = entry["transforms"]["source_effective_page_top_left_to_derived_page_top_left"]
                inverse = entry["transforms"]["derived_page_top_left_to_source_effective_page_top_left"]
                for point in ([0, 0], size, [size[0] / 3, size[1] / 7]):
                    restored = transform(inverse, transform(forward, point))
                    for actual, expected in zip(restored, point):
                        self.assertAlmostEqual(actual, expected, places=10)
                left, _, _, top = entry["source_geometry"]["effective_bbox"]
                self.assertEqual([0, 0], transform(entry["transforms"]["source_pdf_bottom_left_to_pixel_top_left"], [left, top]))
                with Image.open(output / entry["png"]["path"]) as image:
                    self.assertGreater(len(set(image.getdata())), 2)

    def test_png_only_and_embedded_mode_produce_identical_source_png_bytes(self):
        first, full = self.render("full")
        second, png = self.render("png", emit_pdf=False)
        self.assertIsNone(png["derived_pdf"])
        self.assertFalse((second / "image-only.pdf").exists())
        self.assertEqual(full["pages"], png["pages"])
        for page in full["pages"]:
            name = page["png"]["path"]
            self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())

    def test_changed_source_nonempty_output_and_rotated_pages_fail_without_overwriting(self):
        output, _ = self.render()
        frozen = (output / "manifest.json").read_bytes()
        with self.assertRaises(ValueError):
            pdf_raster.render_pdf(self.source, output)
        self.assertEqual(frozen, (output / "manifest.json").read_bytes())
        self.source.write_bytes(self.original + b"\n% changed source bytes")
        with self.assertRaises(ValueError):
            pdf_raster.verify_render(output, self.source)
        self.source.write_bytes(pdf_bytes(rotation=90))
        with self.assertRaises(ValueError):
            self.render("rotated")
        self.assertFalse((self.root / "rotated/manifest.json").exists())

    def test_png_affine_page_order_and_undeclared_assets_are_rejected(self):
        output, manifest = self.render()
        path = output / manifest["pages"][0]["png"]["path"]
        original_png = path.read_bytes()
        path.write_bytes(original_png + b"changed")
        with self.assertRaises(ValueError):
            pdf_raster.verify_render(output, self.source)
        path.write_bytes(original_png)
        original_manifest = deepcopy(manifest)
        manifest["pages"][0]["transforms"]["derived_page_top_left_to_source_effective_page_top_left"][0] += .1
        self.write_manifest(output, manifest)
        with self.assertRaises(ValueError):
            pdf_raster.verify_render(output, self.source)
        manifest = original_manifest
        manifest["pages"].reverse()
        self.write_manifest(output, manifest)
        with self.assertRaises(ValueError):
            pdf_raster.verify_render(output, self.source)
        manifest["pages"].reverse()
        self.write_manifest(output, manifest)
        (output / "undeclared.txt").write_text("retained unexpected content")
        with self.assertRaises(ValueError):
            pdf_raster.verify_render(output, self.source)

    def test_rehashed_text_pdf_cannot_masquerade_as_image_only(self):
        output, manifest = self.render()
        path = output / "image-only.pdf"
        path.write_bytes(self.original)
        manifest["derived_pdf"].update(sha256=sha256(self.original).hexdigest(), bytes=len(self.original))
        self.write_manifest(output, manifest)
        with self.assertRaises(ValueError):
            pdf_raster.verify_render(output)

    def test_cap_records_actual_dpi_and_preserves_the_full_physical_page(self):
        self.source.write_bytes(pdf_bytes(boxes=[([0, 0, 30.25, 1500.75], [0, 0, 30.25, 1500.75])]))
        output, manifest = self.render(emit_pdf=False)
        page = manifest["pages"][0]
        self.assertEqual(3500, max(page["png"]["pixel_size"]))
        self.assertEqual(200, page["png"]["dpi_requested"])
        self.assertLess(page["png"]["dpi_effective"], 200)
        self.assertEqual(manifest, pdf_raster.verify_render(output, self.source))

    def test_wrong_engine_version_is_rejected_before_writing(self):
        with patch.object(pdf_raster.importlib.metadata, "version", return_value="0.0"):
            with self.assertRaises(ValueError):
                self.render()
        self.assertFalse((self.root / "render").exists())

    def test_hash_metadata_attach_needs_no_pdf_libraries_and_binds_frozen_renderer(self):
        output, manifest = self.render()
        frozen_hash = "a" * 64
        manifest["renderer"]["script_sha256"] = frozen_hash
        self.write_manifest(output, manifest)
        with patch.object(pdf_raster, "_dependencies", side_effect=AssertionError("Native imports are forbidden")):
            self.assertEqual(manifest, pdf_raster.verify_render(output, self.source,
                check_pixels=False, expected_script_sha256=frozen_hash))
            with self.assertRaises(ValueError):
                pdf_raster.verify_render(output, self.source,
                    check_pixels=False, expected_script_sha256="b" * 64)
        with self.assertRaises(ValueError):
            pdf_raster.verify_render(output, self.source)


if __name__ == "__main__":
    unittest.main()
