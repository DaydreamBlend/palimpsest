"""Explicit Figure labels for read projections; never change source evidence.

Offsets are Unicode code points in the supplied text. Expanded list/range
members share the exact full label span. Scope and panel case are lookup keys,
not rewritten source text. Unsupported range expansion remains a warning.
"""

from copy import deepcopy
import re


_PREFIX = re.compile(
    r"(?<!\w)(?:(?P<supplement>supplementary|supplemental|supp\.)\s+)?"
    r"(?:figures?\b|figs?\.?(?![a-z_]))\s*", re.I)
_NUMBER = re.compile(r"(?P<s>S)?(?P<number>[1-9][0-9]*)(?P<panel>[a-z])?(?!\w)", re.I)
_CONNECTOR = re.compile(r"\s*(?:(?P<range>[-–—])|,(?:\s*and\b)?|\band\b|&)\s*", re.I)
_PANEL = re.compile(r"(?:\((?P<bracket>[a-z])\)|(?P<plain>[a-z]))(?!\w)", re.I)
_PANEL_GROUP = re.compile(r"\s*\((?P<panels>[a-z](?:\s*(?:[-–—,]|and\b|&)\s*[a-z])*)\)", re.I)
_CONTINUED = re.compile(r"^[\s.|:–—-]*(?:\(\s*)?(?:continued\b|cont\.(?!\w))", re.I)


def _panel_list(text):
    values = re.findall(r"[a-z]|[-–—]", re.sub(r"\band\b", "", text, flags=re.I).lower())
    panels, warnings = [], []
    for index, value in enumerate(values):
        if value in "-–—":
            if not panels or index + 1 == len(values) or values[index + 1] in "-–—":
                warnings.append("ambiguous_panel_range")
            elif panels[-1] > values[index + 1]:
                warnings.append("descending_panel_range")
            else:
                panels.extend(chr(n) for n in range(ord(panels[-1]) + 1, ord(values[index + 1])))
        elif value not in panels:
            panels.append(value)
    return panels, warnings


def _number(text, position, scope):
    match = _NUMBER.match(text, position)
    if not match:
        return None
    end = match.end()
    panels = [match["panel"].lower()] if match["panel"] else []
    warnings = []
    group = _PANEL_GROUP.match(text, end) if not panels else None
    if group:
        panels, warnings = _panel_list(group["panels"])
        end = group.end()
    return {"scope": "supplement" if match["s"] else scope,
            "number": match["number"], "panels": panels, "warnings": warnings}, end


def extract_figure_mentions(text):
    """Find explicit numbered labels, lists and short ascending ranges.

    Roman numerals, inferred labels and standalone panel letters are excluded.
    A range over 100 figures or one with mixed scopes/panels is not expanded;
    its explicit endpoints remain visible with a warning on the whole label.
    """
    if not isinstance(text, str):
        raise TypeError("Figure mention input must be text")
    mentions, consumed = [], 0
    for prefix in _PREFIX.finditer(text):
        if prefix.start() < consumed:
            continue
        first = _number(text, prefix.end(), "supplement" if prefix["supplement"] else "main")
        if first is None:
            continue
        item, end = first
        items = [item]
        warnings = list(item["warnings"])
        while separator := _CONNECTOR.match(text, end):
            previous = items[-1]
            next_number = _number(text, separator.end(), previous["scope"])
            if next_number:
                following, next_end = next_number
                warnings.extend(following["warnings"])
                if separator["range"]:
                    start, stop = int(previous["number"]), int(following["number"])
                    # ponytail: bound lookup expansion, flag larger ranges for explicit reading.
                    if (previous["scope"] != following["scope"] or previous["panels"]
                            or following["panels"] or not 0 < stop - start <= 100):
                        warnings.append("figure_range_not_expanded")
                    else:
                        items.extend({"scope": previous["scope"], "number": str(n),
                                      "panels": [], "warnings": []} for n in range(start + 1, stop))
                items.append(following)
                end = next_end
                continue
            panel = _PANEL.match(text, separator.end())
            if not panel:
                break
            letter = panel["bracket"] or panel["plain"]
            # A bare lowercase article after a whole Figure is prose, not a panel.
            if not previous["panels"] and not panel["bracket"] and letter.islower():
                break
            letter = letter.lower()
            if separator["range"]:
                if not previous["panels"] or previous["panels"][-1] >= letter:
                    warnings.append("panel_range_not_expanded")
                else:
                    previous["panels"].extend(chr(n) for n in range(ord(previous["panels"][-1]) + 1, ord(letter)))
            if letter not in previous["panels"]:
                previous["panels"].append(letter)
            end = panel.end()
        consumed = end
        for item in items:
            mentions.append({**item, "char_start": prefix.start(), "char_end": end,
                             "text": text[prefix.start():end], "warnings": sorted(set(warnings))})
    return mentions


def _caption_labels(text, typed):
    labels = extract_figure_mentions(text)
    if not labels or text[:labels[0]["char_start"]].strip():
        return []
    # Other Figure references inside the caption are not its own identity.
    labels = [label for label in labels if label["char_start"] == labels[0]["char_start"]]
    tail = text[labels[0]["char_end"]:]
    continued = bool(_CONTINUED.match(tail))
    if not typed and not continued and not re.match(r"^\s*[.|:]", tail):
        return []
    return [{**label, "is_continuation": continued,
             "continuation_basis": "explicit_continuation_marker" if continued else "absent"}
            for label in labels]


def extract_caption_anchors(block):
    """Read caption prefixes with original block/child provenance.

    Child text is joined only for recognizing a label. It has no claimed block
    offset: every retained text piece instead exposes its exact raw leaf ref.
    Label punctuation or an explicit continuation marker is required unless
    the parser supplied an image_caption/figure_title type.
    """
    anchors = []
    for child in block.get("children", []):
        if child.get("type") != "image_caption":
            continue
        pieces = [segment for segment in block.get("segments", [])
                  if segment.get("raw_locator", "").startswith(child["raw_locator"] + "/")
                  and isinstance(segment.get("content"), str)]
        text = " ".join(piece["content"] for piece in pieces)
        for label in _caption_labels(text, True):
            anchors.append({**label, "raw_locator": child["raw_locator"],
                "bbox": deepcopy(child["bbox"]), "text": text,
                "char_start": None, "char_end": None,
                "text_basis": "joined_child_source_segments",
                "segment_refs": [{"raw_locator": piece["raw_locator"], "text": piece["content"],
                                  "bbox": deepcopy(piece.get("bbox", child["bbox"]))} for piece in pieces],
                "recognition_basis": "explicit_image_caption_type_and_prefix"})
    if not anchors:
        text = block.get("text", "")
        typed = block.get("type") in ("image_caption", "figure_title")
        for label in _caption_labels(text, typed):
            anchors.append({**label, "raw_locator": block["raw_locator"],
                "bbox": deepcopy(block["bbox"]), "text": text,
                "char_start": 0, "char_end": len(text), "text_basis": "exact_block_text",
                "recognition_basis": "explicit_caption_type_and_prefix" if typed else (
                    "caption_prefix_with_continuation_marker" if label["is_continuation"]
                    else "caption_prefix_with_separator")})
    return [{**anchor, "source_block_id": block["block_id"], "page_index": block["page_index"]}
            for anchor in anchors]
