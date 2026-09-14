"""Normalize retained MinerU middle JSON; this does not validate Information."""

from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path, PurePosixPath

from .artifact_store import _absolute, _directory, _file, _read_payload
from .data import data_id as validate_data_id
from .errors import PalimpsestError


_BLOCK_TYPES = {
    "text", "title", "image", "image_body", "image_caption", "image_footnote",
    "table", "table_body", "table_caption", "table_footnote", "interline_equation",
    "equation", "list", "index", "discarded", "code", "code_body", "code_caption",
    "code_footnote", "algorithm", "ref_text", "phonetic", "header", "footer",
    "page_number", "aside_text", "page_footnote", "abstract", "chart", "chart_body",
    "chart_caption", "chart_footnote", "doc_title", "paragraph_title", "vertical_text",
    "header_image", "footer_image", "formula_number", "caption", "footnote",
}
_SPAN_TYPES = {"text", "image", "table", "chart", "inline_equation", "interline_equation", "equation", "hyperlink"}


def _invalid(message: str, locator: str = ""):
    raise PalimpsestError("invalid_parser_output", message, details={"raw_locator": locator})


def _canonical(value) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError):
        _invalid("MinerU 출력은 유한한 값으로 구성된 JSON이어야 합니다.")


def _array(value, locator: str) -> list:
    if not isinstance(value, list):
        _invalid("MinerU 배열 필드가 없거나 형식이 다릅니다.", locator)
    return value


def _object(value, locator: str) -> dict:
    if not isinstance(value, dict):
        _invalid("MinerU 객체 필드 형식이 다릅니다.", locator)
    return value


def _numbers(value, count: int, locator: str) -> list:
    try:
        valid = (isinstance(value, list) and len(value) == count
                 and all(type(n) in (int, float) and math.isfinite(n) for n in value))
    except OverflowError:
        valid = False
    if not valid:
        _invalid("페이지 크기·좌표는 유한한 숫자 배열이어야 합니다.", locator)
    return list(value)


def _bbox(value, page_size: list, locator: str) -> list:
    box = _numbers(value, 4, locator)
    x0, y0, x1, y1 = box
    width, height = page_size
    if not (0 <= x0 <= x1 <= width and 0 <= y0 <= y1 <= height):
        _invalid("MinerU bbox가 페이지 범위를 벗어나거나 순서가 잘못됐습니다.", locator)
    return box


def _cross_page(value) -> bool:
    if isinstance(value, dict):
        return bool(value.get("cross_page") or value.get("lines_deleted")) or any(
            _cross_page(child) for child in value.values())
    if isinstance(value, list):
        return any(_cross_page(child) for child in value)
    return False


def _asset(root: Path, value, locator: str) -> dict:
    if not isinstance(value, str) or not value or any(char in value for char in ("\\", ":", "\x00")):
        _invalid("MinerU 이미지 경로는 안전한 상대 경로여야 합니다.", locator)
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in value.split("/")):
        _invalid("MinerU 이미지 경로의 절대 경로·상위 이동은 허용하지 않습니다.", locator)
    # Pipeline middle JSON stores paths relative to its images output directory.
    relative = path if path.parts[0] == "images" else PurePosixPath("images") / path
    try:
        with _directory(root.joinpath(*relative.parts[:-1])) as parent:
            with _file(parent, relative.name) as descriptor:
                payload = _read_payload(descriptor, parent, relative.name)
    except (OSError, PalimpsestError):
        _invalid("MinerU 이미지 파일이 없거나 경로·무결성 검사를 통과하지 못했습니다.", locator)
    return {"path": str(relative), "sha256": payload.data_id}


def _normalize_block(raw: dict, locator: str, *, page_index: int, page_size: list,
                     root: Path, data_id: str, collection: str) -> dict:
    _object(raw, locator)
    block_type = raw.get("type")
    if not isinstance(block_type, str) or not block_type:
        _invalid("MinerU block type이 없습니다.", locator)
    upstream_bbox = _bbox(raw.get("bbox"), page_size, locator + "/bbox")
    block = {"block_id": locator, "type": block_type, "page_index": page_index,
             "bbox": list(upstream_bbox), "upstream_bbox": upstream_bbox,
             "bbox_policy": "explicit_region_envelope", "grounding_regions": [],
             "page_size": list(page_size), "text": "", "image_paths": [],
             "raw_locator": locator, "source_collection": collection,
             "segments": [], "children": [], "line_regions": [], "unsupported": []}

    def visit(node, pointer: str, parent: str | None, node_kind: str):
        _object(node, pointer)
        if _cross_page(node):
            _invalid("원래 페이지를 복원할 수 없는 cross-page block은 normalize할 수 없습니다.", pointer)
        kind = node.get("type") if node_kind != "line" else "line"
        if not isinstance(kind, str) or not kind:
            _invalid("MinerU block/span type이 없습니다.", pointer)
        known = _SPAN_TYPES if node_kind == "span" else _BLOCK_TYPES
        if node_kind != "line" and kind not in known:
            block["unsupported"].append({"type": kind, "raw_locator": pointer})
        if node_kind == "span" and kind in {"image", "table", "chart"} and not any(
                node.get(key) for key in ("image_path", "content", "html")):
            _invalid("MinerU visual span에 이미지나 구조화된 내용이 없습니다.", pointer)
        region = _bbox(node["bbox"], page_size, pointer + "/bbox") if "bbox" in node else None
        if node_kind == "block" and region is None:
            _invalid("MinerU block bbox가 없습니다.", pointer)
        if "page_idx" in node and node["page_idx"] != page_index:
            _invalid("하위 block의 원래 페이지가 parent page와 다릅니다.", pointer)
        metadata = deepcopy({key: value for key, value in node.items()
                             if key not in {"type", "bbox", "blocks", "lines", "spans",
                                            "content", "html", "latex", "image_path"}})
        descriptor = {"type": kind, "raw_locator": pointer, "parent_locator": parent,
                      "bbox": region, "upstream_metadata": metadata}
        if node_kind == "block":
            block["grounding_regions"].append({"raw_locator": pointer, "type": kind, "bbox": region})
            if pointer == locator:
                block["upstream_metadata"] = metadata
            else:
                block["children"].append(descriptor)
        elif node_kind == "line":
            block["line_regions"].append(descriptor)
        texts = []
        if any(key in node for key in ("content", "html", "latex", "image_path")):
            segment = dict(descriptor)
            for key in ("content", "html", "latex"):
                if key not in node:
                    continue
                value = node[key]
                if not isinstance(value, str) and not (key == "content" and isinstance(value, list)
                                                       and all(isinstance(item, str) for item in value)):
                    _invalid("MinerU 내용 필드의 구조를 지원하지 않습니다.", pointer + "/" + key)
                segment[key] = deepcopy(value)
                if value:
                    texts.append(value if isinstance(value, str) else "\n".join(value))
            if node.get("image_path"):
                asset = _asset(root, node["image_path"], pointer + "/image_path")
                segment["image_path"] = asset
                if asset not in block["image_paths"]:
                    block["image_paths"].append(asset)
            elif "image_path" in node and node["image_path"] not in (None, ""):
                _invalid("MinerU image_path 형식이 잘못됐습니다.", pointer + "/image_path")
            block["segments"].append(segment)
        for field, child_kind in (("blocks", "block"), ("lines", "line"), ("spans", "span")):
            if field not in node:
                continue
            children = _array(node[field], pointer + "/" + field)
            child_texts = [visit(child, f"{pointer}/{field}/{index}", pointer, child_kind)
                           for index, child in enumerate(children)]
            joiner = " " if field == "spans" else "\n"
            if any(child_texts):
                texts.append(joiner.join(child_texts))
        return "\n".join(texts)

    block["text"] = visit(raw, locator, None, "block")
    # Captions can be outside their upstream parent's rectangle. The envelope
    # covers explicit observed block regions; it is not an inferred raw bbox.
    # Keep every exact region and the original parent separately for provenance.
    boxes = [region["bbox"] for region in block["grounding_regions"]]
    block["bbox"] = [min(box[0] for box in boxes), min(box[1] for box in boxes),
                     max(box[2] for box in boxes), max(box[3] for box in boxes)]
    block["supported"] = not block["unsupported"]
    block["empty"] = not block["text"] and not block["image_paths"]
    block["raw_block_sha256"] = sha256(_canonical(raw)).hexdigest()
    block["anchor_sha256"] = sha256(_canonical({"data_id": data_id, **block})).hexdigest()
    return block


def normalize_middle(middle: dict, *, data_id: str, artifact_root: Path,
                     expected_pages: int, profile: dict) -> dict:
    """Preserve source page coordinates and raw JSON pointers from complete output.

    Coordinates remain MinerU PDF points, upper-left origin. Each block's bbox
    envelopes its explicit parent/descendant block regions; upstream_bbox and
    grounding_regions retain the exact original rectangles. No clipping, page
    joining, dehyphenation or semantic interpretation occurs. The caller verifies
    actual PDF CropBox/rotation and retains the middle JSON and image artifacts.
    """
    validate_data_id(data_id)
    _object(middle, "")
    _object(profile, "/profile")
    _canonical(middle)
    _canonical(profile)
    if type(expected_pages) is not int or expected_pages < 1:
        _invalid("요청한 원문 페이지 수가 올바르지 않습니다.")
    pages = _array(middle.get("pdf_info"), "/pdf_info")
    if len(pages) != expected_pages:
        _invalid("MinerU 출력의 페이지 수가 요청한 원문과 다릅니다.", "/pdf_info")
    try:
        root = _absolute(Path(artifact_root))
        with _directory(root):
            pass
    except (OSError, PalimpsestError):
        _invalid("MinerU 산출물 디렉터리가 없거나 안전하지 않습니다.")
    # This version is an explicit new profile. Legacy profiles retain their
    # historical para/cross-page selection and therefore their existing hashes.
    explicit_preproc = profile.get("adapter_version") == "mineru-hybrid-preproc-v1"
    if explicit_preproc and (profile.get("provider") != "mineru"
                             or profile.get("backend") != "hybrid-engine"):
        _invalid("Hybrid preproc adapter와 parser profile이 일치하지 않습니다.")
    indexed = []
    for position, page in enumerate(pages):
        pointer = f"/pdf_info/{position}"
        _object(page, pointer)
        index = page.get("page_idx")
        if type(index) is not int or not 0 <= index < expected_pages:
            _invalid("원래 page_idx가 없거나 요청 범위를 벗어납니다.", pointer)
        size = _numbers(page.get("page_size"), 2, pointer + "/page_size")
        if min(size) <= 0:
            _invalid("페이지 크기는 양수여야 합니다.", pointer)
        required = "preproc_blocks" if explicit_preproc else "para_blocks"
        _array(page.get(required), pointer + "/" + required)
        indexed.append((index, position, size, page))
    if len({item[0] for item in indexed}) != expected_pages:
        _invalid("원래 page_idx가 중복되거나 빠져 있습니다.", "/pdf_info")
    use_preproc = explicit_preproc or any(_cross_page(item[3]["para_blocks"]) for item in indexed)
    collection = "preproc_blocks" if use_preproc else "para_blocks"
    bundle = {"schema_version": 1, "data_id": data_id, "profile": deepcopy(profile),
              "coordinate_system": "pdf_points_top_left", "pages": [], "blocks": [],
              "block_collection": collection,
              "selection_reason": "explicit_hybrid_preproc_profile" if explicit_preproc else
                                  "preserve_original_pages_before_upstream_cross_page_merge" if use_preproc
                                  else "upstream_paragraph_blocks"}
    for index, position, size, page in sorted(indexed):
        bundle["pages"].append({"page_index": index, "page_size": size,
                                "raw_locator": f"/pdf_info/{position}"})
        for field in (collection, "discarded_blocks"):
            raw_blocks = _array(page.get(field, [] if field == "discarded_blocks" else None),
                                f"/pdf_info/{position}/{field}")
            for number, raw in enumerate(raw_blocks):
                pointer = f"/pdf_info/{position}/{field}/{number}"
                bundle["blocks"].append(_normalize_block(raw, pointer, page_index=index, page_size=size,
                                                         root=root, data_id=data_id, collection=field))
    bundle["zero_output"] = not any(not block["empty"] for block in bundle["blocks"])
    bundle["unsupported_block_ids"] = [block["block_id"] for block in bundle["blocks"] if not block["supported"]]
    return bundle
