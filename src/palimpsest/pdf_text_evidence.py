"""Native PDF character evidence and deterministic, noncanonical review signals.

PDFium extraction is independent of the selected layout parser. No OCR, source
correction, title promotion, oracle lookup, or semantic model is used here.
"""

from bisect import bisect_left, bisect_right
from collections import Counter
from ctypes import c_double, c_int, create_string_buffer
from difflib import SequenceMatcher
from hashlib import sha256
import html
import importlib.metadata
import math
from pathlib import Path
import re
import unicodedata

from .data import data_id as validate_data_id
from .errors import PalimpsestError


EVIDENCE_SCHEMA = "pdf-native-text-v1"
ANALYSIS_SCHEMA = "pdf-text-analysis-v1"


def _fail(message, locator="", code="invalid_pdf_text_evidence"):
    raise PalimpsestError(code, message, details={"raw_locator": locator})


def _hash(path):
    with path.open("rb") as stream:
        return sha256(stream.read()).hexdigest()


def _box(box, locator):
    if (not isinstance(box, (list, tuple)) or len(box) != 4
            or any(type(x) not in (float, int) or not math.isfinite(x) for x in box)
            or box[0] > box[2] or box[1] > box[3]):
        _fail("A finite, ordered source rectangle is required.", locator)
    return list(box)


def _union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def _ranges(indices):
    ranges = []
    for index in indices:
        if ranges and ranges[-1][1] == index:
            ranges[-1][1] = index + 1
        else:
            ranges.append([index, index + 1])
    return ranges


def _style(char):
    return tuple(char[key] for key in ("font", "size", "flags", "weight", "angle")) + (_size(char),)


def _size(char):
    return char.get("effective_size", char["size"])


def _spans(chars, page_index):
    spans = []
    for char in chars:
        if not spans or _style(char) != _style(spans[-1]):
            spans.append({key: char[key] for key in ("font", "size", "flags", "weight", "angle")})
            spans[-1]["effective_size"] = _size(char)
            spans[-1].update(char_range=[char["index"], char["index"]], text="", bbox=None,
                             raw_locator=f"/pages/{page_index}/spans/{len(spans)-1}")
        span = spans[-1]
        span["char_range"][1] += 1
        span["text"] += char["text"]
        if char["bbox"] is not None:
            span["bbox"] = char["bbox"] if span["bbox"] is None else _union([span["bbox"], char["bbox"]])
    return spans


def extract_pdf_text(pdf_path: Path, *, data_id: str) -> dict:
    """Retain PDFium's character array, including generated and unmapped chars.

    Raw Unicode codepoints are used instead of get_text_range(), whose text
    indices can insert/exclude characters. Spans are an explicit projection of
    consecutive characters with identical font/size/style, not native PDF objects.
    """
    validate_data_id(data_id)
    path = Path(pdf_path).resolve(strict=True)
    if _hash(path) != data_id:
        _fail("PDF bytes do not match the requested Data.", code="integrity_conflict")
    try:
        import pypdfium2 as pdfium
        import pypdfium2.raw as raw
    except ImportError:
        _fail("Native PDF evidence requires the selected PDFium runtime.", code="pdf_text_runtime_unavailable")
    evidence = {"schema_version": EVIDENCE_SCHEMA, "data_id": data_id,
                "engine": "pypdfium2", "engine_version": importlib.metadata.version("pypdfium2"),
                "coordinate_system": "pdf_points_top_left", "source_box": "crop",
                "character_policy": "FPDFText_GetUnicode; exact PDFium char indices; no OCR or correction",
                "span_policy": "consecutive equal font,size,descriptor_flags,weight,angle characters",
                "effective_size_policy": "raw FontSize multiplied by hypot(text_matrix.c,text_matrix.d); raw size and matrix retained",
                "font_flags_convention": "PDF 1.7 Font Descriptor flags", "pages": []}
    document = pdfium.PdfDocument(str(path))
    try:
        for index in range(len(document)):
            page = document[index]
            try:
                crop = _box(page.get_cropbox(), f"/pages/{index}/cropbox")
                bounds = _box(page.get_bbox(), f"/pages/{index}/bounds")
                size = list(page.get_size())
                if (page.get_rotation() != 0 or any(abs(a-b) > .001 for a, b in zip(crop, bounds))
                        or any(abs(a-b) > .001 for a, b in zip(size, (crop[2]-crop[0], crop[3]-crop[1])))):
                    _fail("Only unrotated, valid original CropBox coordinates are supported.",
                          f"/pages/{index}", "unsupported_pdf_geometry")
                record = {"page_index": index, "page_size": size, "rotation": 0,
                          "cropbox": crop, "media_box": list(page.get_mediabox()), "source_box": "crop",
                          "pdf_to_crop_top_left": [1, 0, 0, -1, -crop[0], crop[3]], "chars": []}
                text_page = page.get_textpage()
                try:
                    for char_index in range(text_page.count_chars()):
                        locator = f"/pages/{index}/chars/{char_index}"
                        codepoint = int(raw.FPDFText_GetUnicode(text_page, char_index))
                        if not 0 <= codepoint <= 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
                            _fail("PDFium returned an unsupported Unicode scalar.", locator)
                        flags = c_int()
                        length = raw.FPDFText_GetFontInfo(text_page, char_index, None, 0, flags)
                        font, font_bytes = None, None
                        if length:
                            buffer = create_string_buffer(length)
                            actual = raw.FPDFText_GetFontInfo(text_page, char_index, buffer, length, flags)
                            if actual != length:
                                _fail("Font metadata changed during character extraction.", locator)
                            font_bytes = bytes(buffer.raw[:-1])
                            font = font_bytes.decode("utf-8", errors="replace")
                        try:
                            pdf_box = _box(text_page.get_charbox(char_index), locator + "/bbox_pdf")
                        except pdfium.PdfiumError:
                            pdf_box = None
                        box = None if pdf_box is None else [pdf_box[0]-crop[0], crop[3]-pdf_box[3],
                                                           pdf_box[2]-crop[0], crop[3]-pdf_box[1]]
                        font_size = float(raw.FPDFText_GetFontSize(text_page, char_index))
                        angle = float(raw.FPDFText_GetCharAngle(text_page, char_index))
                        matrix = raw.FS_MATRIX()
                        has_matrix = raw.FPDFText_GetMatrix(text_page, char_index, matrix)
                        text_matrix = [float(getattr(matrix, key)) for key in ("a", "b", "c", "d", "e", "f")] if has_matrix else None
                        effective_size = font_size * math.hypot(matrix.c, matrix.d) if has_matrix else font_size
                        origin_x, origin_y = c_double(), c_double()
                        has_origin = raw.FPDFText_GetCharOrigin(text_page, char_index, origin_x, origin_y)
                        if (not all(math.isfinite(value) for value in (font_size, angle, effective_size))
                                or (text_matrix is not None and not all(math.isfinite(value) for value in text_matrix))):
                            _fail("Non-finite character typography.", locator)
                        record["chars"].append({"index": char_index, "text": chr(codepoint), "unicode": codepoint,
                            "font": font, "font_utf8_hex": None if font_bytes is None else font_bytes.hex(),
                            "size": font_size, "flags": flags.value if length else None,
                            "effective_size": effective_size, "text_matrix": text_matrix,
                            "weight": int(raw.FPDFText_GetFontWeight(text_page, char_index)), "angle": angle,
                            "bbox_pdf": pdf_box, "bbox": box,
                            "origin_pdf": [origin_x.value, origin_y.value] if has_origin else None,
                            "inside_crop": box is not None and 0 <= box[0] <= box[2] <= size[0] and 0 <= box[1] <= box[3] <= size[1],
                            "generated": int(raw.FPDFText_IsGenerated(text_page, char_index)),
                            "unicode_map_error": int(raw.FPDFText_HasUnicodeMapError(text_page, char_index)),
                            "raw_locator": locator})
                finally:
                    text_page.close()
                record["spans"] = _spans(record["chars"], index)
                record["native_text_status"] = "available" if any(
                    c["text"].strip() and c["unicode"] >= 32 for c in record["chars"]) else "native_text_unavailable"
                record["native_mapping_warning_count"] = sum(c["unicode_map_error"] != 0 or
                    (c["unicode"] < 32 and c["text"] not in "\r\n\t") for c in record["chars"])
                evidence["pages"].append(record)
            finally:
                page.close()
    finally:
        document.close()
    if _hash(path) != data_id:
        _fail("PDF bytes changed while extracting evidence.", code="integrity_conflict")
    evidence["page_count"] = len(evidence["pages"])
    return evidence


def _bold(char):
    # Embedded FontWeight values are not consistently calibrated: a Regular
    # font may report 712 while a Bold font reports 615. Keep that raw evidence,
    # but use explicit descriptor/name styles for this candidate signal.
    return (bool((char["flags"] or 0) & (1 << 18))
            or re.search(r"bold|black|demi|heavy|[.-](?:b|bd|sb)(?:[+.,-]|$)", char["font"] or "", re.I) is not None)


def _eligible(char):
    angle = (char["angle"] + math.pi) % math.tau - math.pi
    return char["inside_crop"] and char["bbox"] is not None and abs(angle) < .05


def _lines(chars):
    lines, current = [], []
    for char in chars:
        if char["text"] in "\r\n":
            if current:
                lines.append(current)
                current = []
        else:
            current.append(char)
    if current:
        lines.append(current)
    return lines


def _heading_ranges(chars, body_size):
    prefixes = []
    for line in _lines(chars):
        content = [c for c in line if c["text"].strip()]
        if not content or any(not _eligible(c) for c in content):
            continue
        emphasized = lambda c: _bold(c) or _size(c) >= body_size * 1.12
        # A math-font run between emphasized text keeps its own exact glyphs.
        math_char = lambda c: (re.search(r"symbol|math|cmsy|cmmi", c["font"] or "", re.I) is not None
                               or bool(re.fullmatch(r"[\u0370-\u03ff\u2070-\u209f+−=/_{}0-9]", c["text"])))
        if not emphasized(content[0]):
            continue
        end = 0
        for position, char in enumerate(line):
            if not char["text"].strip() or emphasized(char):
                end = position + 1
                continue
            if math_char(char) and any(emphasized(c) for c in line[position+1:] if c["text"].strip()):
                end = position + 1
                continue
            break
        chosen = line[:end]
        while chosen and not chosen[-1]["text"].strip():
            chosen.pop()
        while chosen and not chosen[0]["text"].strip():
            chosen.pop(0)
        if not chosen:
            continue
        box = _union([c["bbox"] for c in chosen if c["bbox"] is not None])
        prefixes.append({"start": chosen[0]["index"], "end": chosen[-1]["index"]+1,
                         "full_line": end == len(line), "bbox": box,
                         "signals": sorted({"bold_font" for c in chosen if _bold(c)} |
                            {"larger_than_body" for c in chosen if _size(c) >= body_size * 1.12} |
                            ({"inline_emphasis_boundary"} if end < len(line) else {"emphasized_line"}))})
    merged = []
    for prefix in prefixes:
        previous = merged[-1] if merged else None
        between = [] if previous is None else chars[previous["end"]:prefix["start"]]
        if (previous is not None and previous["full_line"] and between and all(c["text"].isspace() for c in between)
                and abs(previous["bbox"][0]-prefix["bbox"][0]) <= body_size * 1.5
                and 0 <= prefix["bbox"][1]-previous["bbox"][3] <= body_size * 1.5):
            previous.update(end=prefix["end"], bbox=_union([previous["bbox"], prefix["bbox"]]),
                            full_line=prefix["full_line"], signals=sorted(set(previous["signals"] + prefix["signals"] + ["wrapped_emphasis"])))
        else:
            merged.append(prefix)
    return merged


def _normalized(text):
    # Preserve case, Greek letters, control characters, math and punctuation.
    text = re.sub(r"</?(?:sup|sub|b|strong|i|em)>|<br\s*/?>", "", text, flags=re.I)
    return " ".join(unicodedata.normalize("NFC", html.unescape(text)).split())


def _diff(native, parser):
    return [{"operation": tag, "native_range": [a, b], "parser_range": [c, d],
             "native_text": native[a:b], "parser_text": parser[c:d],
             "native_codepoints": [f"U+{ord(x):04X}" for x in native[a:b]],
             "parser_codepoints": [f"U+{ord(x):04X}" for x in parser[c:d]]}
            for tag, a, b, c, d in SequenceMatcher(None, native, parser, autojunk=False).get_opcodes()
            if tag != "equal"]


def analyze_pdf_text(pdf_evidence: dict, bundle: dict) -> dict:
    """Return review candidates and region-aligned differences, never corrections."""
    if (not isinstance(pdf_evidence, dict) or not isinstance(bundle, dict)
            or pdf_evidence.get("schema_version") != EVIDENCE_SCHEMA
            or bundle.get("data_id") != pdf_evidence.get("data_id")
            or bundle.get("coordinate_system") != "pdf_points_top_left"):
        _fail("Native evidence and parser bundle must share Data and coordinates.")
    validate_data_id(pdf_evidence["data_id"])
    pages = pdf_evidence["pages"]
    if ([p["page_index"] for p in pages] != list(range(len(pages)))
            or [p["page_index"] for p in bundle["pages"]] != list(range(len(pages)))):
        _fail("Original pages are missing, duplicated or reordered.")
    for page, parser_page in zip(pages, bundle["pages"]):
        _box(page["cropbox"], f"/pages/{page['page_index']}/cropbox")
        if any(not isinstance(size, list) or len(size) != 2 or
               any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in size)
               for size in (page["page_size"], parser_page["page_size"])):
            _fail("Native and parser page sizes must be finite positive pairs.")
        if (page["rotation"] != 0 or page["source_box"] != "crop"
                or any(abs(a-b) > 1 for a, b in zip(page["page_size"], parser_page["page_size"]))
                or any(abs((page["cropbox"][i+2]-page["cropbox"][i])-page["page_size"][i]) > .001 for i in (0, 1))
                or ("cropbox" in parser_page and parser_page["cropbox"] != page["cropbox"])):
            _fail("Parser and native PDF CropBox mapping do not agree.", code="unsupported_pdf_geometry")
        for index, char in enumerate(page["chars"]):
            if char["index"] != index or char["raw_locator"] != f"/pages/{page['page_index']}/chars/{index}":
                _fail("Native character indices or locators changed.")
            if type(char["unicode"]) is not int or not 0 <= char["unicode"] <= 0x10FFFF or char["text"] != chr(char["unicode"]):
                _fail("Native character text does not match its retained Unicode scalar.", char["raw_locator"])
            if char["bbox"] is not None:
                _box(char["bbox"], char["raw_locator"])
                if char.get("bbox_pdf") is not None:
                    box, crop = _box(char["bbox_pdf"], char["raw_locator"] + "/bbox_pdf"), page["cropbox"]
                    mapped = [box[0]-crop[0], crop[3]-box[3], box[2]-crop[0], crop[3]-box[1]]
                    if any(abs(a-b) > 1e-6 for a, b in zip(mapped, char["bbox"])):
                        _fail("Retained native character coordinates have changed.", char["raw_locator"])
    sizes = Counter(round(_size(c), 1) for p in pages for c in p["chars"]
                    if _eligible(c) and c["text"].strip() and _size(c) > 0 and not _bold(c))
    if not sizes:
        sizes = Counter(round(_size(c), 1) for p in pages for c in p["chars"]
                        if _eligible(c) and c["text"].strip() and _size(c) > 0)
    body_size = min(sizes, key=lambda size: (-sizes[size], size)) if sizes else None
    result = {"schema_version": ANALYSIS_SCHEMA, "data_id": pdf_evidence["data_id"],
              "authority": "review_signals_only", "body_size_points": body_size,
              "normalization": "NFC, whitespace, HTML entities and explicit presentation tags only; no case/math/Greek correction",
              "heading_candidates": [], "discrepancies": [], "page_status": [], "compared_blocks": 0,
              "native_text_equivalent_blocks": 0}
    for page in pages:
        index, chars = page["page_index"], page["chars"]
        result["page_status"].append({"page_index": index, "status": page["native_text_status"],
                                      "mapping_warning_count": page["native_mapping_warning_count"]})
        if body_size is not None:
            for candidate in _heading_ranges(chars, body_size):
                start, end = candidate["start"], candidate["end"]
                refs = [{"data_id": pdf_evidence["data_id"], "page_index": index,
                         "raw_locator": f"/pages/{index}/chars", "char_range": [start, end]}]
                result["heading_candidates"].append({"candidate_id": f"pdf-heading:{index}:{start}:{end}",
                    "page_index": index, "text": "".join(c["text"] for c in chars[start:end]),
                    "bbox": candidate["bbox"], "char_ranges": [[start, end]], "source_refs": refs,
                    "signals": candidate["signals"], "authority": "candidate_only"})
        centers = sorted(((c["bbox"][1]+c["bbox"][3])/2, c["index"]) for c in chars if _eligible(c))
        ys = [v[0] for v in centers]
        for block in (b for b in bundle["blocks"] if b["page_index"] == index and b["text"]):
            result["compared_blocks"] += 1
            regions = [r for r in block.get("line_regions", []) if r["bbox"] is not None]
            region_policy = "explicit_parser_line_regions"
            if not regions:
                regions = block.get("grounding_regions", []) or [{"bbox": block["upstream_bbox"], "raw_locator": block["raw_locator"]}]
                regions = [r for r in regions if not any(other["raw_locator"].startswith(r["raw_locator"] + "/") for other in regions)]
                region_policy = "explicit_parser_leaf_block_regions"
            selected = set()
            for region in regions:
                box = _box(region["bbox"], region["raw_locator"])
                for _, char_index in centers[bisect_left(ys, box[1]-.5):bisect_right(ys, box[3]+.5)]:
                    char = chars[char_index]
                    cx = (char["bbox"][0]+char["bbox"][2])/2
                    if box[0]-.5 <= cx <= box[2]+.5:
                        selected.add(char_index)
            ordered = sorted(selected)
            for a, b in zip(ordered, ordered[1:]):
                if all(c["text"].isspace() for c in chars[a+1:b]):
                    selected.update(range(a+1, b))
            ordered = sorted(selected)
            native = "".join(chars[i]["text"] for i in ordered)
            parser = block["text"]
            if native and _normalized(native) == _normalized(parser):
                result["native_text_equivalent_blocks"] += 1
                continue
            warnings = []
            if any(chars[i]["unicode_map_error"] != 0 for i in ordered):
                warnings.append("native_unicode_mapping_uncertain")
            for label, text in (("native", native), ("parser", parser)):
                if any(ord(c) < 32 and c not in "\r\n\t" for c in text):
                    warnings.append(label + "_control_characters")
            result["discrepancies"].append({"discrepancy_id": f"pdf-diff:{index}:{block['raw_locator']}",
                "page_index": index, "kind": "region_text_difference" if native else "native_text_unavailable_in_region",
                "alignment_status": "spatial_candidate_uncertain", "region_policy": region_policy,
                "native_text": native, "parser_text": parser,
                "native_char_ranges": _ranges(ordered), "native_text_char_indices": ordered,
                "native_refs": [{"data_id": pdf_evidence["data_id"], "page_index": index,
                                  "raw_locator": f"/pages/{index}/chars", "char_range": pair} for pair in _ranges(ordered)],
                "parser_refs": [{"raw_locator": block["raw_locator"], "raw_block_sha256": block["raw_block_sha256"]}],
                "parser_regions": regions, "warnings": warnings, "raw_diff": _diff(native, parser),
                "assessment": "requires_review; neither text source is corrected or assumed authoritative"})
    return result
