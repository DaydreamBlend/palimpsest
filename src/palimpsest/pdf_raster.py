"""Fixed PDFium page rasters for local OCR; original Data is never replaced.

This is the pixel-grid conversion tested in the 200 DPI parser comparison.
Only image embedding is optional. Every physical page and its source mapping
is retained, including a raw CropBox that extends beyond the effective page.
"""

from contextlib import closing, ExitStack
from hashlib import file_digest
import importlib.metadata
import json
import math
from pathlib import Path
import struct


SCHEMA = "pdf-raster-v1"
RENDER_PROFILE = {
    "engine": "pypdfium2", "engine_version": "5.10.1",
    "pillow_version": "12.3.0",
    "conversion_version": "image-only-pixel-grid-v1", "dpi": 200,
    "long_side_cap_pixels": 3500,
    "embedding": "PdfImage.set_bitmap; RGB 8-bit pixels, lossless Flate",
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _hash(path):
    with Path(path).open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def _dependencies():
    import pypdfium2 as pdfium
    from PIL import Image

    _require(importlib.metadata.version("pypdfium2") == RENDER_PROFILE["engine_version"],
             "Use the pinned PDFium 5.10.1 runtime")
    _require(importlib.metadata.version("Pillow") == RENDER_PROFILE["pillow_version"],
             "Use the pinned Pillow 12.3.0 runtime")
    return pdfium, Image


def _floor_float32(value):
    bits = struct.unpack("<I", struct.pack("<f", value))[0]
    rounded = struct.unpack("<f", struct.pack("<I", bits))[0]
    return struct.unpack("<f", struct.pack("<I", bits - int(rounded > value)))[0]


def _raster(page, scale):
    bitmap = page.render(scale=scale)
    try:
        return bitmap.to_pil().convert("RGB").copy()
    finally:
        bitmap.close()


def _geometry(page):
    return {"media_box": list(page.get_mediabox()), "crop_box": list(page.get_cropbox()),
            "effective_bbox": list(page.get_bbox()), "size": list(page.get_size()),
            "rotation": page.get_rotation(),
            "render_box_policy": "PDFium effective bbox; raw CropBox is retained, not rewritten"}


def _page_metadata(geometry, index, pixels):
    for key, length in (("media_box", 4), ("crop_box", 4), ("effective_bbox", 4), ("size", 2)):
        values = geometry.get(key)
        _require(isinstance(values, list) and len(values) == length
                 and all(type(v) in (int, float) and math.isfinite(v) for v in values),
                 "Invalid PDF geometry")
    _require(type(geometry.get("rotation")) is int and geometry["rotation"] == 0,
             "Rotated PDF pages require a separately verified render profile")
    width, height = geometry["size"]
    left, bottom, right, top = geometry["effective_bbox"]
    _require(min(width, height) > 0 and abs(width - right + left) < .001
             and abs(height - top + bottom) < .001, "Effective bbox and page size differ")
    media, crop = geometry["media_box"], geometry["crop_box"]
    intersection = [max(media[0], crop[0]), max(media[1], crop[1]),
                    min(media[2], crop[2]), min(media[3], crop[3])]
    _require(all(abs(a - b) < .001 for a, b in zip(intersection, geometry["effective_bbox"])),
             "Effective page is not the MediaBox/CropBox intersection")
    dpi, cap = RENDER_PROFILE["dpi"], RENDER_PROFILE["long_side_cap_pixels"]
    scale = min(dpi / 72, cap / max(width, height))
    while max(math.ceil(width * scale), math.ceil(height * scale)) > cap:
        scale = math.nextafter(scale, 0)
    _require(isinstance(pixels, list) and len(pixels) == 2
             and all(type(p) is int and 0 < p <= cap for p in pixels)
             and pixels == [math.ceil(width * scale), math.ceil(height * scale)],
             "Raster dimensions differ from the fixed render profile")
    sx, sy = pixels[0] / width, pixels[1] / height
    nominal = [p * 72 / dpi for p in pixels]
    dw, dh = map(_floor_float32, nominal)
    dx, dy = dw / width, dh / height
    return {
        "source_page_index": index, "source_page_number": index + 1,
        "derived_page_index": index, "derived_page_number": index + 1,
        "source_geometry": geometry,
        "derived_geometry": {"size": [dw, dh], "nominal_pixel_grid_size": nominal,
            "media_box": [0, 0, dw, dh], "crop_box": [0, 0, dw, dh], "rotation": 0,
            "size_delta_from_original": [dw - width, dh - height],
            "float32_delta_from_nominal": [dw - nominal[0], dh - nominal[1]],
            "policy": "PNG pixels * 72/200, greatest float32 not above nominal; explicit derived geometry, not original page size"},
        "transforms": {
            "matrix_convention": "[a,b,c,d,e,f]: x'=a*x+c*y+e; y'=b*x+d*y+f",
            "source_pdf_bottom_left_to_pixel_top_left": [sx, 0, 0, -sy, -left * sx, top * sy],
            "pixel_top_left_to_source_pdf_bottom_left": [1 / sx, 0, 0, -1 / sy, left, top],
            "source_effective_page_top_left_to_pixel_top_left": [sx, 0, 0, sy, 0, 0],
            "source_pdf_bottom_left_to_derived_pdf_bottom_left": [dx, 0, 0, dy, -left * dx, -bottom * dy],
            "derived_pdf_bottom_left_to_source_pdf_bottom_left": [1 / dx, 0, 0, 1 / dy, left, bottom],
            "source_effective_page_top_left_to_derived_page_top_left": [dx, 0, 0, dy, 0, 0],
            "derived_page_top_left_to_source_effective_page_top_left": [1 / dx, 0, 0, 1 / dy, 0, 0],
            "image_unit_square_to_derived_pdf_bottom_left": [dw, 0, 0, dh, 0, 0]},
        "png_geometry": {"pixel_size": pixels, "mode": "RGB", "dpi_requested": dpi,
            "dpi_effective": scale * 72, "actual_pixels_per_inch_axes": [sx * 72, sy * 72],
            "render_scale": scale, "long_side_cap_pixels": cap}}


def _asset(path, **fields):
    return {"path": path.name, "sha256": _hash(path), "bytes": path.stat().st_size, **fields}


def _asset_check(output, asset, name):
    _require(isinstance(asset, dict) and asset.get("path") == name, "Unexpected render asset path")
    path = output / name
    _require(path.is_file() and not path.is_symlink(), "Missing or unsafe render asset")
    _require(asset.get("sha256") == _hash(path) and asset.get("bytes") == path.stat().st_size,
             "Render asset changed")
    return path


def validate_manifest(manifest, *, expected_script_sha256=None):
    """Check fixed metadata and affines with stdlib; this is not pixel validation.

    Attach/replay should supply the renderer hash from its frozen compilation
    profile. Historical manifests need not match the current implementation.
    """
    _require(isinstance(manifest, dict) and manifest.get("schema_version") == SCHEMA
             and manifest.get("state") == "verified_image_only_input",
             "Unknown or incomplete PDF raster manifest")
    renderer = manifest.get("renderer", {})
    _require(isinstance(renderer, dict)
             and all(renderer.get(k) == v and type(renderer.get(k)) is type(v) for k, v in RENDER_PROFILE.items())
             and isinstance(renderer.get("script_sha256"), str) and len(renderer["script_sha256"]) == 64
             and all(c in "0123456789abcdef" for c in renderer["script_sha256"])
             and (expected_script_sha256 is None or renderer["script_sha256"] == expected_script_sha256),
             "Raster implementation or profile changed")
    pages, original = manifest.get("pages"), manifest.get("source", {})
    _require(isinstance(pages, list) and pages and isinstance(original, dict)
             and type(original.get("page_count")) is int
             and original["page_count"] == len(pages) and original.get("data_id") == original.get("sha256")
             and isinstance(original.get("sha256"), str) and len(original["sha256"]) == 64
             and all(c in "0123456789abcdef" for c in original["sha256"])
             and type(original.get("bytes")) is int and original["bytes"] > 0,
             "Original Data and complete physical pages are required")
    for index, entry in enumerate(pages):
        _require(isinstance(entry, dict) and isinstance(entry.get("png"), dict)
                 and isinstance(entry.get("source_geometry"), dict)
                 and all(type(entry.get(k)) is int for k in
                         ("source_page_index", "source_page_number", "derived_page_index", "derived_page_number")),
                 "Original page metadata is missing")
        expected = _page_metadata(entry["source_geometry"], index, entry["png"].get("pixel_size"))
        png_geometry = expected.pop("png_geometry")
        _require(all(entry.get(k) == v for k, v in expected.items())
                 and all(entry["png"].get(k) == v for k, v in png_geometry.items()),
                 "Page geometry or affine provenance changed")
        for matrix in entry["transforms"].values():
            if isinstance(matrix, list):
                _require(all(type(value) in (int, float) and math.isfinite(value) for value in matrix),
                         "Invalid affine number")
    asset = manifest.get("derived_pdf")
    _require(asset is None or (isinstance(asset, dict) and asset.get("is_original_data") is False
                               and asset.get("sha256") != original["sha256"]),
             "Raster PDF must not replace original Data")
    return manifest


def _verify(manifest, output, source, *, check_pixels=True, expected_script_sha256=None):
    validate_manifest(manifest, expected_script_sha256=expected_script_sha256)
    pages, original = manifest["pages"], manifest["source"]
    if source is not None:
        _require(_hash(source) == original["sha256"] and source.stat().st_size == original["bytes"],
                 "Original PDF changed")
    expected_files = {"manifest.json", *(f"page-{i + 1:04d}.png" for i in range(len(pages)))}
    png_paths = []
    for index, entry in enumerate(pages):
        path = _asset_check(output, entry["png"], f"page-{index + 1:04d}.png")
        with path.open("rb") as stream:
            header = stream.read(33)
        _require(len(header) == 33 and header[:16] == b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
                 and list(struct.unpack(">II", header[16:24])) == entry["png"]["pixel_size"]
                 and header[24:29] == b"\x08\x02\x00\x00\x00", "PNG header does not match its RGB geometry")
        png_paths.append(path)
    derived_path = None
    if manifest.get("derived_pdf") is not None:
        derived_path = _asset_check(output, manifest["derived_pdf"], "image-only.pdf")
        expected_files.add(derived_path.name)
    _require(not any(p.is_symlink() for p in output.iterdir())
             and {p.name for p in output.iterdir()} <= expected_files, "Unexpected render artifacts")
    if not check_pixels:
        return manifest
    pdfium, Image = _dependencies()
    with ExitStack() as stack:
        source_pdf = None
        if source is not None:
            source_pdf = stack.enter_context(pdfium.PdfDocument(str(source)))
            _require(len(source_pdf) == len(pages), "Original PDF pages changed")
        derived = None
        if derived_path is not None:
            derived = stack.enter_context(pdfium.PdfDocument(str(derived_path)))
            _require(len(derived) == len(pages), "Derived PDF physical pages changed")
        for index, (entry, path) in enumerate(zip(pages, png_paths)):
            with Image.open(path) as image:
                _require(image.mode == "RGB" and image.format == "PNG", "Expected lossless RGB PNG")
                if source_pdf is not None:
                    with closing(source_pdf[index]) as page:
                        _require(_geometry(page) == entry["source_geometry"], "Original page geometry changed")
                        with _raster(page, entry["png"]["render_scale"]) as original_image:
                            _require(original_image.size == image.size and original_image.tobytes() == image.tobytes(),
                                     "PNG pixels do not reproduce the original page")
                if derived is not None:
                    with closing(derived[index]) as page:
                        with closing(page.get_textpage()) as text:
                            _require(text.count_chars() == 0, "Raster PDF contains native text")
                        objects = list(page.get_objects())
                        _require(list(page.get_size()) == entry["derived_geometry"]["size"]
                                 and len(objects) == 1 and isinstance(objects[0], pdfium.PdfImage),
                                 "Raster PDF is not the declared one-image page")
                        bitmap = objects[0].get_bitmap()
                        try:
                            with bitmap.to_pil().convert("RGB") as embedded:
                                _require(embedded.size == image.size and embedded.tobytes() == image.tobytes(),
                                         "Embedded image pixels changed")
                        finally:
                            bitmap.close()
                        with _raster(page, RENDER_PROFILE["dpi"] / 72) as rerender:
                            _require(rerender.size == image.size and rerender.tobytes() == image.tobytes(),
                                     "Image-only PDF rerender changed pixels")
    if source is not None:
        _require(_hash(source) == original["sha256"], "Original PDF changed during verification")
    return manifest


def render_pdf(source, output, *, emit_pdf=True):
    """Render every original page; return and retain a verified manifest.

    PNG-only mode feeds the same pixels directly to an image parser. The optional
    PDF contains those exact pixels without text. Failed attempts stay on disk.
    """
    pdfium, _ = _dependencies()
    source, output = Path(source), Path(output)
    _require(type(emit_pdf) is bool and not source.is_symlink() and not output.is_symlink(),
             "Use explicit regular input/output paths and a boolean PDF mode")
    source, output = source.resolve(strict=True), output.resolve()
    _require(source.is_file() and not source.is_relative_to(output), "Input must be a file outside the output")
    _require(not output.exists() or (output.is_dir() and not any(output.iterdir())),
             "Output must be empty; preserve previous and failed attempts")
    output.mkdir(parents=True, exist_ok=True)
    source_hash, script_hash = _hash(source), _hash(__file__)
    manifest = {"schema_version": SCHEMA, "state": "verified_image_only_input",
        "source": {"data_id": source_hash, "sha256": source_hash, "bytes": source.stat().st_size},
        "renderer": {**RENDER_PROFILE, "pillow_version": importlib.metadata.version("Pillow"),
                     "script_sha256": script_hash, "pdf_byte_reproducibility": "not asserted; exact file SHA binds this run"},
        "pages": [], "derived_pdf": None, "canonical_writes": 0, "semantic_llm_calls": 0}
    with ExitStack() as stack:
        original = stack.enter_context(pdfium.PdfDocument(str(source)))
        derived = stack.enter_context(pdfium.PdfDocument.new()) if emit_pdf else None
        _require(len(original) > 0, "Original PDF has no pages")
        manifest["source"]["page_count"] = len(original)
        for index in range(len(original)):
            with closing(original[index]) as page:
                geometry = _geometry(page)
                width, height = geometry["size"]
                _require(all(math.isfinite(v) and v > 0 for v in (width, height)), "Invalid page size")
                scale = min(RENDER_PROFILE["dpi"] / 72, RENDER_PROFILE["long_side_cap_pixels"] / max(width, height))
                while max(math.ceil(width * scale), math.ceil(height * scale)) > RENDER_PROFILE["long_side_cap_pixels"]:
                    scale = math.nextafter(scale, 0)
                metadata = _page_metadata(geometry, index, [math.ceil(width * scale), math.ceil(height * scale)])
                with _raster(page, scale) as image:
                    _require(list(image.size) == metadata["png_geometry"]["pixel_size"], "Unexpected PDFium dimensions")
                    path = output / f"page-{index + 1:04d}.png"
                    image.save(path, format="PNG", dpi=(scale * 72, scale * 72))
                    metadata["png"] = _asset(path, **metadata.pop("png_geometry"))
                    if derived is not None:
                        dw, dh = metadata["derived_geometry"]["size"]
                        with closing(derived.new_page(dw, dh)) as target:
                            obj = pdfium.PdfImage.new(derived)
                            bitmap = pdfium.PdfBitmap.from_pil(image)
                            try:
                                obj.set_bitmap(bitmap)
                            finally:
                                bitmap.close()
                            obj.set_matrix(pdfium.PdfMatrix(a=dw, d=dh))
                            target.insert_obj(obj)
                            target.gen_content()
                manifest["pages"].append(metadata)
        if derived is not None:
            path = output / "image-only.pdf"
            derived.save(path)
            manifest["derived_pdf"] = _asset(path, is_original_data=False,
                role="noncanonical OCR input; original Data identity remains source.data_id")
    _require(_hash(source) == source_hash and _hash(__file__) == script_hash, "Input or renderer changed during rendering")
    _verify(manifest, output, source, expected_script_sha256=script_hash)
    temporary = output / "manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(output / "manifest.json")
    return manifest


def verify_render(output, source=None, *, check_pixels=True, expected_script_sha256=None):
    """Verify retained renders; supplying source also proves its pixels by default.

    ``check_pixels=False`` needs no PDF libraries and checks hashes/metadata only.
    Callers must not label that path a new pixel check. Pass the frozen renderer
    hash for historical attach/replay; native checks default to the current one.
    """
    _require(type(check_pixels) is bool, "Pixel verification mode must be explicit")
    output = Path(output)
    _require(not output.is_symlink(), "Raster directory must not be a symlink")
    output = output.resolve(strict=True)
    manifest_path = output / "manifest.json"
    _require(manifest_path.is_file() and not manifest_path.is_symlink(), "Missing raster manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = Path(source).resolve(strict=True) if source is not None else None
    if check_pixels and expected_script_sha256 is None:
        expected_script_sha256 = _hash(__file__)
    return _verify(manifest, output, source, check_pixels=check_pixels,
                   expected_script_sha256=expected_script_sha256)
