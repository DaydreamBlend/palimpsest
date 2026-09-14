"""Preserve PaddleOCR page results and crop artifacts in source bundle v1.

The runner supplies unrotated CropBox renders and retains the untouched model
result. This adapter scales pixel regions to PDF points; it does not infer
missing content, merge Figures, or assess extraction fidelity.
"""

from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path, PurePosixPath

from .artifact_store import _absolute, _directory, _file, _read_payload
from .data import data_id as validate_digest
from .errors import PalimpsestError


ADAPTER_VERSION = "paddleocr-raw-v1"
_LABELS = {
    "text": "text", "doc_title": "doc_title", "paragraph_title": "paragraph_title",
    "table": "table", "image": "image", "chart": "chart", "formula": "equation",
    "figure_title": "image_caption", "table_title": "table_caption",
    "header": "header", "footer": "footer", "number": "page_number",
    "footnote": "page_footnote", "aside_text": "aside_text", "reference": "ref_text",
    "abstract": "abstract", "algorithm": "algorithm", "seal": "image",
    "header_image": "header_image", "footer_image": "footer_image",
    "reference_content": "ref_text", "content": "content", "vision_footnote": "vision_footnote",
}


def _invalid(rule, locator=""):
    raise PalimpsestError("invalid_parser_output", "PaddleOCR 원문 산출물을 확인하세요.", 4,
                          {"validation_rule": rule, "raw_locator": locator})


def _digest(value):
    try:
        return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError):
        _invalid("Finite UTF-8 JSON is required.")


def _numbers(value, count, locator):
    if (not isinstance(value, list) or len(value) != count
            or any(type(n) not in (int, float) for n in value)):
        _invalid("Invalid coordinate shape.", locator)
    try:
        if any(not math.isfinite(n) for n in value):
            _invalid("Coordinates must be finite.", locator)
    except OverflowError:
        _invalid("Coordinates must be finite.", locator)
    return list(value)


def _box(value, size, locator):
    box = _numbers(value, 4, locator)
    if not (0 <= box[0] <= box[2] <= size[0] and 0 <= box[1] <= box[3] <= size[1]):
        _invalid("The region must remain within its source page.", locator)
    return box


def _asset(root, asset, locator):
    relative = asset.get("path")
    if (not isinstance(relative, str) or not relative or any(c in relative for c in ("\\", ":", "\x00"))
            or PurePosixPath(relative).is_absolute()
            or any(part in ("", ".", "..") for part in relative.split("/"))):
        _invalid("Crop paths must be safe relative paths.", locator)
    path = root.joinpath(*PurePosixPath(relative).parts)
    try:
        with _directory(path.parent) as parent, _file(parent, path.name) as descriptor:
            payload = _read_payload(descriptor, parent, path.name)
    except (OSError, PalimpsestError):
        _invalid("A crop is missing, unsafe, or changed while reading.", locator)
    if payload.byte_size < 1 or payload.data_id != asset.get("sha256"):
        _invalid("A crop does not match its declared hash.", locator)
    return {"path": relative, "sha256": payload.data_id}


def normalize_paddle(raw, *, data_id, artifact_root, expected_pages, profile):
    """Normalize a retained paddleocr-raw-v1 envelope without modifying it."""
    validate_digest(data_id)
    if (not isinstance(raw, dict) or raw.get("schema_version") != ADAPTER_VERSION
            or raw.get("data_id") != data_id or not isinstance(profile, dict)
            or type(expected_pages) is not int or expected_pages < 1):
        _invalid("A matching source Data, profile, and raw envelope are required.")
    _digest(raw)
    _digest(profile)
    if profile.get("provider") == "paddleocr-vl":
        manifest_hash, version = profile.get("models_manifest_sha256"), profile.get("version")
        if (not isinstance(manifest_hash, str) or len(manifest_hash) != 64
                or any(c not in "0123456789abcdef" for c in manifest_hash)
                or raw.get("models_manifest_sha256") != manifest_hash
                or not isinstance(version, str) or not version
                or not isinstance(raw.get("versions"), dict)
                or raw["versions"].get("paddleocr") != version):
            _invalid("The raw parser model manifest and package version must match the selected profile.")
        if type(raw.get("page_count")) is not int or raw["page_count"] != expected_pages:
            _invalid("The declared source page count must match the complete requested document.", "/page_count")
    pages = raw.get("pages")
    if (not isinstance(pages, list) or len(pages) != expected_pages
            or any(not isinstance(page, dict) for page in pages)
            or [page.get("page_index") for page in pages] != list(range(expected_pages))
            or any(type(page.get("page_index")) is not int for page in pages)):
        _invalid("Every original page must occur exactly once in source order.", "/pages")
    try:
        root = _absolute(Path(artifact_root))
        with _directory(root):
            pass
    except (OSError, PalimpsestError):
        _invalid("The parser artifact directory is unsafe or absent.")
    bundle = {"schema_version": 1, "data_id": data_id, "profile": deepcopy(profile),
              "coordinate_system": "pdf_points_top_left", "pages": [], "blocks": [],
              "block_collection": "parsing_res_list", "selection_reason": "complete_paddle_page_results",
              "reading_order_source": "paddleocr"}
    for page_index, page in enumerate(pages):
        pointer = f"/pages/{page_index}"
        pdf_size = _numbers(page.get("pdf_size"), 2, pointer + "/pdf_size")
        render_size = _numbers(page.get("render_size"), 2, pointer + "/render_size")
        cropbox = _numbers(page.get("cropbox"), 4, pointer + "/cropbox")
        if (min(pdf_size + render_size) <= 0 or page.get("rotation") != 0
                or type(page.get("rotation")) is not int or page.get("source_box") != "crop"
                or any(abs((cropbox[i + 2] - cropbox[i]) - pdf_size[i]) > 0.03 for i in (0, 1))):
            _invalid("Only verified unrotated CropBox geometry is supported.", pointer)
        result = page.get("result")
        if (not isinstance(result, dict) or [result.get("width"), result.get("height")] != render_size
                or not isinstance(result.get("parsing_res_list"), list)
                or not isinstance(page.get("image_assets"), list)):
            _invalid("The raw result must match the rendered page dimensions.", pointer)
        _numbers([result["width"], result["height"]], 2, pointer + "/result")
        if profile.get("provider") == "paddleocr-vl" and (
                not isinstance(result.get("model_settings"), dict)
                or result["model_settings"].get("use_doc_preprocessor") is not False):
            _invalid("An undeclared page orientation or warp transform is unsupported.", pointer + "/result/model_settings")
        if (profile.get("provider") == "paddleocr-vl"
                and result["model_settings"].get("merge_layout_blocks") is not False):
            _invalid("Layout merging can move text outside its retained block region and must be explicitly disabled.",
                     pointer + "/result/model_settings/merge_layout_blocks")
        scale = [pdf_size[i] / render_size[i] for i in (0, 1)]
        transform = {"source_coordinate_system": "pixels_top_left", "source_size": render_size,
                     "target_coordinate_system": "pdf_points_top_left", "scale": scale,
                     "rotation": 0, "source_box": "crop", "cropbox": cropbox}
        bundle["pages"].append({"page_index": page_index, "page_size": pdf_size,
                                "raw_locator": pointer, "coordinate_transform": transform})
        assets, used_assets = {}, set()
        for asset_index, asset in enumerate(page["image_assets"]):
            asset_pointer = f"{pointer}/image_assets/{asset_index}"
            if not isinstance(asset, dict) or type(asset.get("block_id")) is not int:
                _invalid("A crop must identify its original block.", asset_pointer)
            assets.setdefault(asset["block_id"], []).append((asset, asset_pointer))
        seen = set()
        for ordinal, block in enumerate(result["parsing_res_list"]):
            locator = f"{pointer}/result/parsing_res_list/{ordinal}"
            if (not isinstance(block, dict) or type(block.get("block_id")) is not int
                    or block["block_id"] in seen or not isinstance(block.get("block_label"), str)
                    or not block["block_label"] or not isinstance(block.get("block_content"), str)):
                _invalid("A source block requires a unique original ID, label, and text.", locator)
            seen.add(block["block_id"])
            pixel_box = _box(block.get("block_bbox"), render_size, locator + "/block_bbox")
            box = [pixel_box[i] / render_size[i % 2] * pdf_size[i % 2] for i in range(4)]
            order = block.get("block_order")
            if order is not None:
                _numbers([order], 1, locator + "/block_order")
            label = block["block_label"]
            images = []
            for asset, asset_pointer in assets.get(block["block_id"], []):
                if _box(asset.get("bbox"), render_size, asset_pointer + "/bbox") != pixel_box:
                    _invalid("The crop and its source block must have the same region.", asset_pointer)
                images.append(_asset(root, asset, asset_pointer))
                used_assets.add(asset_pointer)
            if label in {"image", "chart", "header_image", "footer_image"} and not images:
                _invalid("A visual source block requires its retained crop.", locator)
            if images and (pixel_box[0] == pixel_box[2] or pixel_box[1] == pixel_box[3]):
                _invalid("A retained crop requires a nonempty source region.", locator)
            supported = label in _LABELS
            kind = _LABELS.get(label, label)
            text = block["block_content"]
            # SDK block_order excludes visual and auxiliary blocks. The complete
            # parsing_res_list order includes them; preserve both representations.
            normalized = {"block_id": locator, "type": kind, "upstream_label": label,
                "page_index": page_index, "page_size": pdf_size, "bbox": box,
                "upstream_bbox": pixel_box, "bbox_policy": "scaled_upstream_region",
                "coordinate_transform": deepcopy(transform), "text": text, "image_paths": images,
                "raw_locator": locator, "source_collection": "parsing_res_list",
                "segments": [{"type": kind, "content": text, "bbox": box,
                              "raw_locator": locator + "/block_content", "parent_locator": locator}],
                "children": [], "line_regions": [],
                "grounding_regions": [{"raw_locator": locator, "type": kind, "bbox": box}],
                "upstream_metadata": {**deepcopy(block), "index": ordinal,
                                      "reading_order_source": "paddleocr", "original_block_order": order,
                                      "reading_order_basis": "parsing_res_list_position"},
                "supported": supported, "unsupported": [] if supported else [{"type": label, "raw_locator": locator}],
                "empty": not text and not images, "raw_block_sha256": _digest(block)}
            normalized["anchor_sha256"] = _digest({"data_id": data_id, **normalized})
            bundle["blocks"].append(normalized)
        if len(used_assets) != len(page["image_assets"]):
            _invalid("Every declared crop must refer to a retained source block.", pointer + "/image_assets")
    bundle["zero_output"] = not any(not block["empty"] for block in bundle["blocks"])
    bundle["unsupported_block_ids"] = [block["block_id"] for block in bundle["blocks"] if not block["supported"]]
    return bundle
