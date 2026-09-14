"""Deterministic, noncanonical PDF page/panel/Figure evidence projections.

Parser crops are preserved verbatim. Figure bounds are proposals backed by native
PDF objects or parser regions; the complete source page is always available.
"""

from hashlib import sha256
import json
import math
from pathlib import Path, PurePosixPath
import re

from .errors import PalimpsestError


SCHEMA = "pdf-visual-evidence-v1"
_CAPTION = re.compile(r"^\s*(?:FIGURE|Fig\.?)\s+(\d+[A-Za-z]?)\s*[|.:]", re.I)
_TYPED_CAPTION = re.compile(r"^\s*(?:FIGURE|Fig\.?)\s+(\d+[A-Za-z]?)(?=\s|[|.:]|$)", re.I)
_SCALE = 2
_GEOMETRY_TOLERANCE = 1.0  # MinerU's page dimensions are rounded to PDF points.


def _fail(message):
    raise PalimpsestError("invalid_pdf_visual_evidence", message)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _id(kind, value):
    return kind + "-" + sha256(_json(value)).hexdigest()[:24]


def _bbox(value, size):
    if (not isinstance(value, (list, tuple)) or len(value) != 4
            or any(isinstance(n, bool) or not isinstance(n, (int, float))
                   or not math.isfinite(n) for n in value)):
        _fail("A source region must contain four finite PDF coordinates")
    x0, y0, x1, y1 = value
    if not (0 <= x0 < x1 <= size[0] and 0 <= y0 < y1 <= size[1]):
        _fail("A source region is outside its original page")
    return list(value)


def _area(box):
    return max(0, box[2] - box[0]) * max(0, box[3] - box[1])


def _intersection(a, b):
    return _area([max(a[0], b[0]), max(a[1], b[1]),
                  min(a[2], b[2]), min(a[3], b[3])])


def _union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def _page_box(bounds, source_box, rotation):
    """Native PDF bottom-left coordinates -> rotated CropBox top-left points."""
    left, bottom, right, top = source_box
    width, height = right - left, top - bottom
    points = []
    for px, py in ((bounds[0], bounds[1]), (bounds[0], bounds[3]),
                   (bounds[2], bounds[1]), (bounds[2], bounds[3])):
        x, y = px - left, py - bottom
        points.append({0: (x, height - y), 90: (y, x),
                       180: (width - x, y), 270: (height - y, width - x)}[rotation])
    return [min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points)]


def _asset(path, output_dir, **metadata):
    return {"path": path.relative_to(output_dir).as_posix(),
            "sha256": sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size, **metadata}


def _crop(image, box, size, path, output_dir):
    # Round outwards so the projection never cuts a fraction of the source pixel.
    pixel_box = [math.floor(box[0] * image.width / size[0]),
                 math.floor(box[1] * image.height / size[1]),
                 math.ceil(box[2] * image.width / size[0]),
                 math.ceil(box[3] * image.height / size[1])]
    cropped = image.crop(pixel_box)
    try:
        cropped.save(path, format="PNG")
        return _asset(path, output_dir, pixel_size=list(cropped.size),
                      page_pixel_bbox=pixel_box)
    finally:
        cropped.close()


def _captions(block):
    """Preserve explicit child captions, plus separately parsed caption blocks."""
    segments = block.get("segments", [])
    anchors = []
    for child in block.get("children", []):
        if child.get("type") != "image_caption":
            continue
        prefix = child["raw_locator"] + "/"
        text = " ".join(s.get("content", "") for s in segments
                        if s.get("raw_locator", "").startswith(prefix)).strip()
        match = _TYPED_CAPTION.match(text)
        if match:
            anchors.append({"raw_locator": child["raw_locator"],
                            "bbox": child["bbox"], "text": text, "number": match.group(1),
                            "recognition_basis": "explicit_image_caption_type_and_prefix"})
    text = block.get("text", "")
    typed = block.get("type") in ("image_caption", "figure_title")
    match = (_TYPED_CAPTION if typed else _CAPTION).match(text)
    if not anchors and match:
        anchors.append({"raw_locator": block["raw_locator"],
                        "bbox": block["bbox"], "text": text, "number": match.group(1),
                        "recognition_basis": "explicit_caption_type_and_prefix" if typed else "caption_prefix_with_separator"})
    return [{**a, "source_block_id": block["block_id"],
             "page_index": block["page_index"]} for a in anchors]


def _parser_asset(reference, panel_id, artifact_root, output_dir):
    if not isinstance(reference, dict):
        _fail("A parser image reference must include its path and SHA-256")
    relative, digest = reference.get("path"), reference.get("sha256")
    if (not isinstance(relative, str) or not relative or "\\" in relative
            or ":" in relative or PurePosixPath(relative).is_absolute()
            or ".." in PurePosixPath(relative).parts
            or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
        _fail("A parser image reference has an unsafe path or invalid SHA-256")
    result = {"original_path": relative, "sha256": digest, "copied_asset": None}
    if artifact_root is not None:
        root = Path(artifact_root).resolve(strict=True)
        source = (root / relative).resolve(strict=True)
        if not source.is_relative_to(root) or not source.is_file():
            _fail("A parser image reference escapes the artifact root")
        content = source.read_bytes()
        if sha256(content).hexdigest() != digest:
            _fail("Parser image bytes do not match their recorded SHA-256")
        # Keep arbitrary parser bytes verbatim; do not decode/re-encode originals.
        target = output_dir / "panels" / (panel_id + "-original" + source.suffix)
        target.write_bytes(content)
        result["copied_asset"] = _asset(target, output_dir)
    return result


def _figure_proposal(caption, members, native_images, page_record):
    """Prefer one native image containing the parser's visual evidence."""
    if not members:
        return None, ["no_associated_panel; use the whole source page"]
    union = _union([p["bbox"] for p in members])
    candidates = [obj for obj in native_images
                  if obj["bbox"][3] <= caption["bbox"][1] + 1
                  and _area(obj["bbox"]) < .90 * _area([0, 0, *page_record["page_size"]])
                  and .75 <= _area(obj["bbox"]) / _area(union) <= 5
                  and all(_intersection(obj["bbox"], p["bbox"]) / _area(p["bbox"]) >= .90
                          for p in members)]
    if candidates:
        chosen = min(candidates, key=lambda obj: (_area(obj["bbox"]), obj["object_index"]))
        return {"bbox": chosen["bbox"], "method": "native_image_object",
                "native_object": chosen}, ["native_image_association_is_a_proposal"]
    return {"bbox": union, "method": "parser_panel_union", "native_object": None}, [
        "parser_panel_union_may_omit_labels_or_panels; use the whole source page"]


def build_pdf_visuals(pdf_path: Path, bundle: dict, output_dir: Path, *, artifact_root=None) -> dict:
    """Export source pages, unchanged parser crops and conservative Figure views.

    This creates no I/semantic identity and never changes the supplied bundle.
    A fresh/empty output directory is required; manifest.json is written last.
    Optional artifact_root resolves the bundle's parser-relative image paths.
    """
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise PalimpsestError("pdf_renderer_unavailable", "The PDFium renderer is not installed") from exc

    pdf_path, output_dir = Path(pdf_path), Path(output_dir)
    pdf_bytes = pdf_path.read_bytes()
    digest = sha256(pdf_bytes).hexdigest()
    if (bundle.get("schema_version") != 1 or bundle.get("data_id") != digest
            or bundle.get("coordinate_system") != "pdf_points_top_left"):
        _fail("The normalized bundle must describe these exact PDF bytes in PDF points")
    try:
        bundle_bytes = _json(bundle)
    except (TypeError, ValueError) as exc:
        raise PalimpsestError("invalid_pdf_visual_evidence", "Bundle must be finite JSON") from exc
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        _fail("Visual export requires a new or empty output directory")
    pages = bundle.get("pages", [])
    blocks = bundle.get("blocks", [])
    if (not isinstance(pages, list) or not isinstance(blocks, list)
            or [p.get("page_index") for p in pages] != list(range(len(pages)))):
        _fail("The normalized bundle must retain every original page in order")
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in ("pages", "panels", "figures"):
        (output_dir / name).mkdir()
    (output_dir / "bundle.snapshot.json").write_bytes(bundle_bytes)
    manifest = {"schema_version": SCHEMA, "coordinate_system": "pdf_points_top_left",
                "source": {"data_id": digest, "pdf_sha256": digest,
                           "pdf_size_bytes": len(pdf_bytes), "bundle_sha256": sha256(bundle_bytes).hexdigest(),
                           "bundle_snapshot": _asset(output_dir / "bundle.snapshot.json", output_dir),
                           "parser_profile": bundle.get("profile"),
                           "renderer": {"name": "pypdfium2", "version": str(pdfium.PYPDFIUM_INFO),
                                        "pdfium_version": str(pdfium.PDFIUM_INFO), "scale": _SCALE,
                                        "algorithm_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
                                        "annotations": True}},
                "pages": [], "panels": [], "figures": [], "warnings": [],
                "semantic_validation": False, "figure_bounds_are_proposals": True}
    seen = set()
    for block in blocks:
        if (not isinstance(block, dict) or not isinstance(block.get("block_id"), str)
                or block["block_id"] in seen or not isinstance(block.get("page_index"), int)
                or isinstance(block["page_index"], bool) or not 0 <= block["page_index"] < len(pages)):
            _fail("Source block IDs and original page indices must be valid and unique")
        seen.add(block["block_id"])
    document = pdfium.PdfDocument(pdf_bytes)
    try:
        if len(document) != len(pages):
            _fail("The bundle page count differs from the original PDF")
        for page_index, parser_page in enumerate(pages):
            page = document[page_index]
            try:
                size = list(page.get_size())
                source_box, rotation = list(page.get_bbox()), page.get_rotation()
                parser_size = parser_page.get("page_size", [])
                if (len(parser_size) != 2 or rotation not in (0, 90, 180, 270)
                        or any(not isinstance(v, (int, float)) or isinstance(v, bool)
                               or not math.isfinite(v) or v <= 0 for v in parser_size)
                        or any(abs(a - b) > _GEOMETRY_TOLERANCE for a, b in zip(size, parser_size))):
                    _fail("Parser page geometry does not match the rotated source CropBox")
                page_record = {"page_index": page_index, "page_size": size,
                               "parser_page_size": parser_size, "rotation": rotation,
                               "cropbox": list(page.get_cropbox()), "mediabox": list(page.get_mediabox()),
                               "source_box": source_box, "source_box_policy": "media_crop_intersection",
                               "parser_geometry_policy": "no_rescaling; at most 1 point page-size rounding",
                               "native_objects_policy": "top_level_images_only; nested_forms_use_page_fallback"}
                native_images = []
                for object_index, obj in enumerate(page.get_objects(max_depth=1)):
                    if obj.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE:
                        native_box = list(obj.get_bounds())
                        box = _page_box(native_box, source_box, rotation)
                        clipped = [max(0, box[0]), max(0, box[1]), min(size[0], box[2]), min(size[1], box[3])]
                        if _area(clipped):
                            native_images.append({"object_index": object_index, "bbox": clipped,
                                                  "pdf_bbox_bottom_left": native_box,
                                                  "clipped_to_source_page": clipped != box})
                page_record["native_images"] = native_images
                bitmap = page.render(scale=_SCALE, draw_annots=True)
                image = bitmap.to_pil()
                try:
                    target = output_dir / "pages" / f"page-{page_index:04d}.png"
                    image.save(target, format="PNG")
                    page_record["page_image"] = _asset(target, output_dir, pixel_size=list(image.size))
                    manifest["pages"].append(page_record)
                    page_panels, captions = [], []
                    for block in (b for b in blocks if b["page_index"] == page_index):
                        _bbox(block["bbox"], size)
                        captions.extend(_captions(block))
                        segments = [s for s in block.get("segments", []) if s.get("image_path")]
                        # Preserve any top-level asset omitted from the segment projection as well.
                        represented = {s["image_path"]["path"] for s in segments}
                        segments += [{"image_path": ref, "bbox": block["bbox"],
                                      "raw_locator": block["raw_locator"], "fallback_bbox": True}
                                     for ref in block.get("image_paths", []) if ref["path"] not in represented]
                        for segment in segments:
                            box = _bbox(segment.get("bbox"), size)
                            panel_id = _id("panel", [digest, block["block_id"], segment["raw_locator"], segment["image_path"]])
                            panel = {"panel_id": panel_id, "page_index": page_index,
                                     "source_block_id": block["block_id"], "raw_locator": segment["raw_locator"],
                                     "bbox": box, "parser_asset": _parser_asset(segment["image_path"], panel_id, artifact_root, output_dir),
                                     "rendered_region": _crop(image, box, size, output_dir / "panels" / (panel_id + ".png"), output_dir),
                                     "whole_page_fallback": page_record["page_image"],
                                     "warnings": ["only_parent_block_bbox_available"] if segment.get("fallback_bbox") else []}
                            page_panels.append(panel)
                    manifest["panels"].extend(page_panels)
                    for caption in captions:
                        _bbox(caption["bbox"], size)
                    groups = {c["raw_locator"]: [] for c in captions}
                    for panel in page_panels:
                        eligible = [c for c in captions if panel["bbox"][3] <= c["bbox"][1] + 1
                                    and min(panel["bbox"][2], c["bbox"][2]) > max(panel["bbox"][0], c["bbox"][0])]
                        if eligible:
                            nearest = min(eligible, key=lambda c: (c["bbox"][1] - panel["bbox"][3], c["raw_locator"]))
                            groups[nearest["raw_locator"]].append(panel)
                    associated = set()
                    for caption in captions:
                        members = groups[caption["raw_locator"]]
                        previous = [f for f in manifest["figures"] if f["number"] == caption["number"]
                                    and f["caption_anchors"][-1]["page_index"] == page_index - 1]
                        if not members and len(previous) == 1 and any(
                                "continued" in a["text"].lower() for a in [caption, previous[0]["caption_anchors"][-1]]):
                            caption["association"] = "explicit_continuation_on_adjacent_page"
                            previous[0]["caption_anchors"].append(caption)
                            previous[0]["continuation_page_fallbacks"].append({"page_index": page_index, "page_image": page_record["page_image"]})
                            continue
                        figure_id = _id("figure", [digest, caption["raw_locator"]])
                        proposal, warnings = _figure_proposal(caption, members, native_images, page_record)
                        if proposal:
                            proposal["image"] = _crop(image, proposal["bbox"], size, output_dir / "figures" / (figure_id + ".png"), output_dir)
                        associated.update(p["panel_id"] for p in members)
                        manifest["figures"].append({"figure_id": figure_id, "number": caption["number"],
                            "page_index": page_index, "caption_anchors": [caption],
                            "member_panel_ids": [p["panel_id"] for p in members], "certainty": "proposal",
                            "region_proposal": proposal, "whole_page_fallback": page_record["page_image"],
                            "continuation_page_fallbacks": [], "warnings": warnings})
                    unassociated = [p["panel_id"] for p in page_panels if p["panel_id"] not in associated]
                    if unassociated:
                        manifest["warnings"].append({"page_index": page_index,
                            "code": "panels_without_numbered_figure_caption", "panel_ids": unassociated})
                finally:
                    image.close()
                    bitmap.close()
            finally:
                page.close()
    finally:
        document.close()
    (output_dir / "manifest.json").write_bytes(_json(manifest))
    return manifest
