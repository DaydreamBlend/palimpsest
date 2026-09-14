"""Auditable, local glyph selection between two retained PDF transcriptions.

This returns a new projection, never edits parser bundles, and never interprets
scientific meaning. The caller owns original-page coordinate mapping and source
artifact verification. Ambiguous alignment is an unresolved result, not success.
"""
from collections import Counter
from copy import deepcopy
from difflib import SequenceMatcher
from hashlib import sha256
import html
import json
import math
import re
import unicodedata

from .data import data_id as validate_data_id
from .errors import PalimpsestError


SELECTION_VERSION = "native-ordinary-ocr-special-v3"
_GREEK = dict(zip(
    "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau upsilon phi chi psi omega".split(),
    "αβγδεζηθικλμνξοπρστυφχψω"))
_MACROS = {**_GREEK, **{name: value for name, value in zip(
    "Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega".split(), "ΓΔΘΛΞΠΣΥΦΨΩ")},
    "varepsilon": "ϵ", "vartheta": "ϑ", "varphi": "ϕ", "varrho": "ϱ", "varsigma": "ς",
    "pm": "±", "mp": "∓", "times": "×", "cdot": "·", "leq": "≤", "geq": "≥",
    "neq": "≠", "approx": "≈", "infty": "∞", "rightarrow": "→", "leftarrow": "←"}
_SCRIPT_BASE = dict(zip("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎", "0123456789+-=()0123456789+-=()"))
_SCRIPT = re.compile(r"([_^])\s*(?:\{([^{}]*)\}|([A-Za-z0-9+−=\-]))")
_HTML_SCRIPT = re.compile(r"<(sup|sub)>([^<>]*)</\1>")
_FORMAT = re.compile(r"\\(?:mathrm|textrm|text|mathbf|mathit|mathsf)\s*\{([^{}\\]*)\}")
_MACRO = re.compile(r"\\([A-Za-z]+)")
_MATH_REGION = re.compile(r"(?s)(?<!\\)(\${1,2})(.+?)(?<!\\)\1|\\\((.*?)\\\)|\\\[(.*?)\\\]")
_EQUATIONS = {"inline_equation", "interline_equation", "equation"}


def _fail(rule):
    raise PalimpsestError("invalid_transcription_selection", "두 전사의 원문 대응을 검증할 수 없습니다.",
                          4, {"validation_rule": rule})


def _digest(value):
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeEncodeError, RecursionError):
        _fail("Selection inputs must be finite UTF-8 JSON.")
    return sha256(encoded).hexdigest()


def _valid_text(text):
    return isinstance(text, str) and not any(unicodedata.category(c) in {"Cc", "Cs"} and c not in "\n\r\t" for c in text)


def _is_greek(char):
    return char == "µ" or "GREEK" in unicodedata.name(char, "")


def _box(box):
    return (isinstance(box, list) and len(box) == 4
            and all(type(v) in (int, float) and math.isfinite(v) for v in box)
            and box[0] <= box[2] and box[1] <= box[3])


def _overlaps(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    minimum = min((a[2]-a[0])*(a[3]-a[1]), (b[2]-b[0])*(b[3]-b[1]))
    return minimum > 0 and intersection / minimum >= 0.5


def _raw_map(block):
    """Locate ordered raw payloads; only explicit assembly whitespace may intervene."""
    text, cursor = block["text"], 0
    refs = [None] * len(text)
    for segment in block.get("segments", []):
        for field in ("content", "html", "latex"):
            if field not in segment:
                continue
            values = segment[field] if isinstance(segment[field], list) else [segment[field]]
            for item_index, value in enumerate(values):
                if not isinstance(value, str):
                    _fail("Raw payload fields must contain strings.")
                if not value:
                    continue
                start = text.find(value, cursor)
                if start < 0 or text[cursor:start].strip():
                    _fail("Block text does not reproduce its ordered raw payloads.")
                if not isinstance(segment.get("raw_locator"), str) or not _box(segment.get("bbox")):
                    _fail("Each textual raw payload needs its exact locator and original-page bbox.")
                field_locator = segment["raw_locator"] + "/" + field
                if isinstance(segment[field], list):
                    field_locator += f"/{item_index}"
                for index in range(len(value)):
                    refs[start + index] = {"raw_locator": segment["raw_locator"], "field_locator": field_locator,
                        "character_range": [index, index+1], "bbox": list(segment["bbox"]),
                        "raw_bbox": deepcopy(segment.get("raw_bbox")), "type": segment.get("type")}
                cursor = start + len(value)
    if text[cursor:].strip():
        _fail("Block text contains unbound raw content.")
    return refs


def _view(block):
    text, raw_refs = block["text"], _raw_map(block)
    chars, ranges, atoms, issues = [], [], [], []
    math_regions = [(match.start(), match.end()) for match in _MATH_REGION.finditer(text)]

    def math_context(offset):
        ref = raw_refs[offset]
        return (ref is not None and (ref["type"] in _EQUATIONS or ref["field_locator"].endswith("/latex"))
                or any(start <= offset < end for start, end in math_regions))

    def append(value, start, end, kind=None, selected=None):
        begin = len(chars)
        for char in value:
            if not char.isspace():
                chars.append(char)
                ranges.append([start, end])
        if kind and len(chars) > begin:
            atoms.append({"view_range": [begin, len(chars)], "text_range": [start, end],
                          "kind": kind, "selected": value if selected is None else selected})

    cursor = 0
    while cursor < len(text):
        match = _HTML_SCRIPT.match(text, cursor)
        if match is None:
            match = _SCRIPT.match(text, cursor)
            # An underscore/caret in ordinary prose, identifiers and URLs is a
            # literal character. Only typed or explicitly delimited math may
            # use the one-character TeX shorthand without braces.
            if match and match.group(2) is None and not math_context(cursor):
                match = None
        if match:
            marker, body = match.group(1), match.group(2)
            if body is None:
                body = match.group(3)
            if not body or any(c in "\\{}<>" for c in body):
                issues.append("unsupported_script_expression")
                append(text[cursor:match.end()], cursor, match.end())
            else:
                tag = "sup" if marker in ("sup", "^") else "sub"
                append(body, cursor, match.end(), "script", f"<{tag}>{html.escape(body)}</{tag}>")
            cursor = match.end()
            continue
        match = _FORMAT.match(text, cursor)
        if match:
            for index in range(match.start(1), match.end(1)):
                append(text[index], index, index+1, "greek" if _is_greek(text[index]) else None)
            cursor = match.end()
            continue
        match = _MACRO.match(text, cursor)
        if match:
            macro = match.group(1)
            if macro in _MACROS:
                append(_MACROS[macro], cursor, match.end(), "greek" if _is_greek(_MACROS[macro]) else "operator")
            else:
                issues.append("unsupported_latex_macro")
                append(match.group(), cursor, match.end())
            cursor = match.end()
            continue
        char = text[cursor]
        if char in _SCRIPT_BASE:
            append(_SCRIPT_BASE[char], cursor, cursor+1, "script", char)
        elif _is_greek(char):
            append(char, cursor, cursor+1, "greek")
        elif ord(char) > 127 and unicodedata.category(char) == "Sm":
            append(char, cursor, cursor+1, "operator")
        elif char in "+-=<>|*/" and raw_refs[cursor] and raw_refs[cursor]["type"] in _EQUATIONS:
            append(char, cursor, cursor+1, "operator")
        elif char in "${}":
            pass  # Explicit math delimiters have no displayed glyph.
        elif char in "_^":
            if math_context(cursor):
                issues.append("unsupported_script_expression")
            append(char, cursor, cursor+1)
        elif char == "\\" and cursor + 1 < len(text) and text[cursor+1] in ",;! ":
            cursor += 1  # TeX spacing only.
        else:
            append(char, cursor, cursor+1)
        cursor += 1
    return {"text": "".join(chars), "source_text": text, "ranges": ranges, "atoms": atoms,
            "issues": sorted(set(issues)), "raw_refs": raw_refs}


def _refs(block, view, interval, channel):
    a, b = interval
    result = []
    for offset, ref in enumerate(view["raw_refs"][a:b], a):
        if ref is None:
            if not block["text"][offset].isspace():
                _fail("Selected text has no raw provenance.")
            continue
        item = {**deepcopy(ref), "channel": channel, "page_index": block["page_index"],
                "raw_block_sha256": block["raw_block_sha256"]}
        if block.get("raw_artifact") is not None:
            item["raw_artifact"] = deepcopy(block["raw_artifact"])
        if (result and all(result[-1].get(k) == item.get(k) for k in item if k != "character_range")
                and result[-1]["character_range"][1] == item["character_range"][0]):
            result[-1]["character_range"][1] = item["character_range"][1]
        else:
            result.append(item)
    return result


def _text_range(view, start, end):
    if start == end:
        position = view["ranges"][start][0] if start < len(view["ranges"]) else (view["ranges"][-1][1] if view["ranges"] else 0)
        return [position, position]
    return [view["ranges"][start][0], view["ranges"][end-1][1]]


def _insertion_range(atom, boundary, native_view, ocr_view):
    """Choose an edge of native whitespace from actual OCR glyph adjacency.

    Compact alignment cannot distinguish TGF-β + space from space + μM. Keep
    every native whitespace byte and use the OCR atom's two raw gaps to decide
    which side receives the glyph. Equal/unknown gaps cannot establish a side.
    """
    previous = native_view["ranges"][boundary-1][1] if boundary else 0
    following = (native_view["ranges"][boundary][0] if boundary < len(native_view["ranges"])
                 else len(native_view["source_text"]))
    if previous > following:
        return None
    gap = native_view["source_text"][previous:following]
    if not gap:
        return [previous, previous]
    if not gap.isspace():
        return None
    start, end = atom["view_range"]
    raw_start, raw_end = atom["text_range"]
    left = ocr_view["ranges"][start-1][1] if start else 0
    right = (ocr_view["ranges"][end][0] if end < len(ocr_view["ranges"])
             else len(ocr_view["source_text"]))
    if left > raw_start or raw_end > right:
        return None
    left_gap = ocr_view["source_text"][left:raw_start]
    right_gap = ocr_view["source_text"][raw_end:right]
    if not left_gap and right_gap.isspace():
        return [previous, previous]
    if left_gap.isspace() and not right_gap:
        return [following, following]
    return None


def _aligned_atom(atom, opcodes, native_view, ocr_view):
    start, end = atom["view_range"]
    pieces = []
    for tag, a, b, x, y in opcodes:
        if min(end, y) <= max(start, x):
            continue
        if tag == "equal":
            pieces.append((a + max(start, x)-x, a + min(end, y)-x))
        elif x >= start and y <= end and tag in ("replace", "insert"):
            if tag == "replace" and atom["kind"] != "script" and b-a != 1:
                return None
            pieces.append((a, b))
        else:
            return None  # Mixed ordinary/special difference: never replace a whole phrase.
    if not pieces:
        return None
    a, b = min(v[0] for v in pieces), max(v[1] for v in pieces)
    if a == b:
        before = any(tag == "equal" and y == start and b0-a0 >= 1 for tag, a0, b0, x, y in opcodes)
        after = any(tag == "equal" and x == end and b0-a0 >= 1 for tag, a0, b0, x, y in opcodes)
        leading = a == 0 and start == 0 and after
        trailing = a == len(native_view["text"]) and end == len(ocr_view["text"]) and before
        if not (before and after or leading or trailing):
            return None
        return _insertion_range(atom, a, native_view, ocr_view)
    return _text_range(native_view, a, b)


def _select_block(native, ocr, left, right):
    opcodes = SequenceMatcher(None, left["text"], right["text"], autojunk=False).get_opcodes()
    edits, issues, ordinary = [], [], []

    def edit(native_range, ocr_range, selected, reason):
        a, b = native_range
        if native["text"][a:b] == selected:
            return
        if any(min(b, e["native_range"][1]) > max(a, e["native_range"][0])
               or a == b == e["native_range"][0] == e["native_range"][1] for e in edits):
            issues.append("overlapping_special_edits")
            return
        edits.append({"native_range": native_range, "ocr_range": ocr_range,
            "native_text": native["text"][a:b], "ocr_text": ocr["text"][ocr_range[0]:ocr_range[1]],
            "selected_text": selected, "reason": reason,
            "native_refs": _refs(native, left, native_range, "native"),
            "native_anchor_refs": (_refs(native, left, [max(0, a-1), min(len(native["text"]), b+1)], "native")
                                   if a == b else []),
            "ocr_refs": _refs(ocr, right, ocr_range, "ocr")})

    for atom in right["atoms"]:
        aligned = _aligned_atom(atom, opcodes, left, right)
        if aligned is None:
            issues.append("ambiguous_local_special_alignment")
        elif native["text"][aligned[0]:aligned[1]] == ocr["text"][atom["text_range"][0]:atom["text_range"][1]]:
            continue  # Equal raw text is not a reason to invent new formatting.
        else:
            edit(aligned, atom["text_range"], atom["selected"], "ocr_" + atom["kind"])
    for tag, a, b, x, y in opcodes:
        if tag == "equal":
            continue
        native_range, ocr_range = _text_range(left, a, b), _text_range(right, x, y)
        native_special = [atom for atom in left["atoms"] if atom["view_range"] == [a, b]]
        ocr_special = any(min(y, atom["view_range"][1]) > max(x, atom["view_range"][0]) for atom in right["atoms"])
        if native_special and not ocr_special:
            if tag == "replace" and b-a == y-x == 1 and right["text"][x:y].isascii() and right["text"][x:y].isalnum():
                edit(native_range, ocr_range, ocr["text"][ocr_range[0]:ocr_range[1]], "ocr_ascii_over_native_special")
            else:
                issues.append("unsupported_native_special_difference")
        elif not ocr_special:
            ordinary.append({"native_range": native_range, "ocr_range": ocr_range,
                "native_text": native["text"][native_range[0]:native_range[1]],
                "ocr_text": ocr["text"][ocr_range[0]:ocr_range[1]], "decision": "native_ordinary_preferred",
                "native_refs": _refs(native, left, native_range, "native"),
                "ocr_refs": _refs(ocr, right, ocr_range, "ocr")})
    if issues:
        return native["text"], [], ordinary, sorted(set(issues))
    ordered, delta = sorted(edits, key=lambda e: e["native_range"]), 0
    for change in ordered:
        a, b = change["native_range"]
        change["selected_range"] = [a + delta, a + delta + len(change["selected_text"])]
        delta += len(change["selected_text"]) - (b-a)
    selected = native["text"]
    for change in sorted(edits, key=lambda e: e["native_range"], reverse=True):
        a, b = change["native_range"]
        selected = selected[:a] + change["selected_text"] + selected[b:]
    if not _valid_text(selected):
        _fail("Selected content must not contain invalid control characters.")
    return selected, ordered, ordinary, sorted(set(issues))


def select_transcription(native_bundle, ocr_bundle, *, ocr_source):
    """Return an immutable-input projection with explicit unresolved alignments.

    Both bundles must already use the original Data identity, original physical
    page indices and original top-left PDF-point coordinates. ``ocr_source`` is
    a caller-verified ``{artifact_path, sha256}`` descriptor of retained OCR data.
    """
    validate_data_id(native_bundle.get("data_id"))
    if (native_bundle.get("data_id") != ocr_bundle.get("data_id")
            or any(b.get("schema_version") != 1 or b.get("coordinate_system") != "pdf_points_top_left"
                   for b in (native_bundle, ocr_bundle))):
        _fail("Both bundles must use the same original Data and coordinate system.")
    if (not isinstance(ocr_source, dict) or not isinstance(ocr_source.get("artifact_path"), str)
            or not ocr_source["artifact_path"] or "\x00" in ocr_source["artifact_path"]
            or not re.fullmatch(r"[a-f0-9]{64}", str(ocr_source.get("sha256", "")))):
        _fail("A verified retained OCR artifact descriptor is required.")
    page_sets = []
    for bundle in (native_bundle, ocr_bundle):
        pages = {p["page_index"]: p["page_size"] for p in bundle["pages"]}
        if len(pages) != len(bundle["pages"]):
            _fail("Original page indices must be unique.")
        ids = [b["block_id"] for b in bundle["blocks"]]
        if len(ids) != len(set(ids)):
            _fail("Block identifiers must be unique within each source.")
        for block in bundle["blocks"]:
            if (not isinstance(block.get("text"), str) or not _box(block.get("bbox"))
                    or block.get("page_index") not in pages or block.get("page_size") != pages[block["page_index"]]
                    or not re.fullmatch(r"[a-f0-9]{64}", str(block.get("raw_block_sha256", "")))):
                _fail("Source text, original-page geometry and raw block hashes are required.")
        page_sets.append(pages)
    if page_sets[0] != page_sets[1]:
        _fail("OCR must be explicitly mapped to the same original pages and sizes.")
    left = {b["block_id"]: _view(b) for b in native_bundle["blocks"]}
    right = {b["block_id"]: _view(b) for b in ocr_bundle["blocks"]}
    for block in ocr_bundle["blocks"]:
        if not _valid_text(block["text"]):
            right[block["block_id"]]["issues"].append("ocr_control_character")
    candidates = {}
    for native in native_bundle["blocks"]:
        candidates[native["block_id"]] = [ocr for ocr in ocr_bundle["blocks"]
            if native["page_index"] == ocr["page_index"] and _overlaps(native["bbox"], ocr["bbox"])
            and left[native["block_id"]]["text"] and right[ocr["block_id"]]["text"]
            and SequenceMatcher(None, left[native["block_id"]]["text"], right[ocr["block_id"]]["text"], autojunk=False).ratio() >= 0.5]
    usage = Counter(values[0]["block_id"] for values in candidates.values() if len(values) == 1)
    rows = []
    for native in native_bundle["blocks"]:
        choices, view = candidates[native["block_id"]], left[native["block_id"]]
        row = {"block_id": native["block_id"], "page_index": native["page_index"], "bbox": deepcopy(native["bbox"]),
            "native_text": native["text"], "ocr_text": None, "selected_text": native["text"],
            "changes": [], "ordinary_differences": [], "issues": [], "status": "native_only",
            "alignment": {"candidate_block_ids": [b["block_id"] for b in choices]}}
        if not view["text"]:
            rows.append(row)
            continue
        if len(choices) != 1 or usage[choices[0]["block_id"]] != 1:
            row.update(status="needs_review", issues=["ambiguous_block_alignment" if choices else "unmatched_block"])
        else:
            ocr = choices[0]
            ocr_view = right[ocr["block_id"]]
            row["ocr_text"] = ocr["text"]
            row["alignment"].update(ocr_block_id=ocr["block_id"], ocr_bbox=deepcopy(ocr["bbox"]),
                native_raw_block_sha256=native["raw_block_sha256"], ocr_raw_block_sha256=ocr["raw_block_sha256"],
                native_refs=_refs(native, view, [0, len(native["text"])], "native"),
                ocr_refs=_refs(ocr, ocr_view, [0, len(ocr["text"])], "ocr"))
            row["issues"] = sorted(set(view["issues"] + ocr_view["issues"]))
            if not row["issues"]:
                row["selected_text"], row["changes"], row["ordinary_differences"], row["issues"] = _select_block(native, ocr, view, ocr_view)
            row["status"] = "needs_review" if row["issues"] else "selected" if row["changes"] else "native_retained"
        rows.append(row)
    if any(not _valid_text(row["selected_text"]) for row in rows):
        _fail("Selected content must not contain invalid control characters.")
    for row in rows:
        groups = [row["alignment"].get("ocr_refs", [])]
        groups.extend(change["ocr_refs"] for change in row["changes"] + row["ordinary_differences"])
        for refs in groups:
            for ref in refs:
                ref["raw_artifact"] = deepcopy(ocr_source)
    unresolved = [{"block_id": r["block_id"], "page_index": r["page_index"], "issues": r["issues"]}
                  for r in rows if r["status"] == "needs_review"]
    used = {row["alignment"].get("ocr_block_id") for row in rows}
    unmatched_ocr = [{"block_id": block["block_id"], "page_index": block["page_index"],
                     "bbox": deepcopy(block["bbox"]), "text": block["text"],
                     "raw_block_sha256": block["raw_block_sha256"],
                     "has_visual": bool(block.get("image_paths")),
                     "reason": "unmatched_or_ambiguous_ocr_block"}
                    for block in ocr_bundle["blocks"] if block["block_id"] not in used]
    return {"schema_version": "transcription-selection-v1", "version": SELECTION_VERSION,
        "status": "needs_review" if unresolved or unmatched_ocr else "complete", "data_id": native_bundle["data_id"],
        "native_bundle_sha256": _digest(native_bundle), "ocr_bundle_sha256": _digest(ocr_bundle),
        "ocr_source": deepcopy(ocr_source), "coordinate_system": "pdf_points_top_left", "blocks": rows,
        "unresolved": unresolved, "unmatched_ocr_block_ids": [block["block_id"] for block in unmatched_ocr],
        "unmatched_ocr_blocks": unmatched_ocr,
        "rendering_rule": "whitelisted_greek_math_unicode_and_contextual_scripts_v2",
        "insertion_rule": "raw_neighbor_adjacency_preserving_native_whitespace_v1",
        "alignment_rule": "unique_same_page_half_minimum_bbox_overlap_and_lexical_ratio_at_least_half_v1",
        "meaning_validation": False, "llm_calls": 0}
