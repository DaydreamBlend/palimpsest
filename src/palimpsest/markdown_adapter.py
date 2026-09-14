"""Group Markdown by parsed headings while retaining every original UTF-8 byte.

Only CR/LF/CRLF delimit source lines. Byte and character ranges are half-open;
line numbers are one-based and inclusive. A terminal newline belongs to its
preceding line, and an empty document has the single empty location line 1.
Parser-normalized text is used for structure only, never as Information content.
"""

from bisect import bisect_right
from copy import deepcopy
from hashlib import sha256
import re

from .data import data_id as validate_data_id
from .errors import PalimpsestError
from .information import validate_proposal
from .source_units import _digest


MARKDOWN_ALGORITHM = "markdown-groups-v1"
MARKDOWN_SCHEMA = "markdown-source-v1"
MARKDOWN_PARSER = {"provider": "markdown-it-py", "version": "4.2.0",
    "adapter_version": MARKDOWN_SCHEMA, "preset": "commonmark", "extensions": ["table"],
    "encoding": "utf-8", "external_resources": "references_only"}


def _fail(message, code="invalid_markdown_source"):
    raise PalimpsestError(code, message, 4)


def parse_markdown(raw: bytes, *, data_id: str):
    """Parse registered bytes without opening files, fetching links or rendering."""
    import markdown_it
    from markdown_it import MarkdownIt

    validate_data_id(data_id)
    if not isinstance(raw, bytes) or sha256(raw).hexdigest() != data_id:
        _fail("Markdown bytes must match the registered Data SHA-256.", "integrity_conflict")
    if markdown_it.__version__ != MARKDOWN_PARSER["version"]:
        _fail("The Markdown parser must match its recorded version.", "markdown_parser_version_mismatch")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        _fail("Markdown requires strict UTF-8 encoding.", "invalid_markdown_encoding")
    if "\x00" in text:
        _fail("Markdown containing NUL cannot be stored as source text.", "invalid_markdown_encoding")
    ends = [match.end() for match in re.finditer(r"\r\n|\r|\n", text)]
    if not ends or ends[-1] != len(text):
        ends.append(len(text))
    char_offsets = [0, *ends]
    byte_offsets = [0]
    for start, end in zip(char_offsets, char_offsets[1:]):
        byte_offsets.append(byte_offsets[-1] + len(text[start:end].encode("utf-8")))

    def span(start_line, end_line):
        return {"byte_start": byte_offsets[start_line], "byte_end": byte_offsets[end_line],
                "char_start": char_offsets[start_line], "char_end": char_offsets[end_line],
                "line_start": start_line + 1, "line_end": max(start_line + 1, end_line)}

    # The BOM is retained in source bytes/content, but must not hide the first heading.
    normalized = text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    environment = {}
    tokens = MarkdownIt("commonmark", {"store_labels": True}).enable("table").parse(normalized, environment)
    headings, stack, images = [], [], []
    for index, token in enumerate(tokens):
        if token.type == "heading_open" and token.level == 0:
            level = int(token.tag[1:])
            title = tokens[index + 1].content or "Untitled section"
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            headings.append({"level": level, "title": title,
                "text_range": span(*token.map), "heading_path": [item[1] for item in stack],
                "start_line": token.map[0], "end_line": token.map[1]})
        if token.type == "inline" and token.map:
            pending = list(reversed(token.children or []))
            while pending:
                child = pending.pop()
                pending.extend(reversed(child.children or []))
                if child.type == "image":
                    locator = span(*token.map)
                    reference = child.meta.get("label")
                    definition = environment.get("references", {}).get(reference)
                    definition_locator = span(*definition["map"]) if definition else None
                    images.append({"url": child.attrGet("src"), "alt": child.content,
                        "url_origin": "parser_normalized", "title": child.attrGet("title"), "reference": reference,
                        "fetched": False, "text_range": locator,
                        "range_scope": "containing_inline_lines",
                        "reference_definition": ({"text_range": definition_locator,
                            "raw_markdown": text[definition_locator["char_start"]:definition_locator["char_end"]]}
                            if definition_locator else None),
                        "raw_markdown": text[locator["char_start"]:locator["char_end"]]})

    groups = []
    if not headings:
        groups.append({"start_line": 0, "end_line": len(ends), "headings": []})
    else:
        first_start = headings[0]["start_line"]
        preamble = text[:char_offsets[first_start]].removeprefix("\ufeff")
        if preamble.strip():
            groups.append({"start_line": 0, "end_line": first_start, "headings": []})
        index = 0
        while index < len(headings):
            begin = index
            # Only a title-only ancestor joins the following child; empty siblings stay distinct.
            while index + 1 < len(headings):
                current, following = headings[index:index + 2]
                between = text[char_offsets[current["end_line"]]:char_offsets[following["start_line"]]]
                if current["level"] >= following["level"] or between.strip():
                    break
                index += 1
            groups.append({"start_line": 0 if begin == 0 and not preamble.strip() else headings[begin]["start_line"],
                "end_line": headings[index + 1]["start_line"] if index + 1 < len(headings) else len(ends),
                "headings": headings[begin:index + 1]})
            index += 1

    blocks = []
    for group in groups:
        locator = span(group["start_line"], group["end_line"])
        start, end = locator["char_start"], locator["char_end"]
        byte_start, byte_end = locator["byte_start"], locator["byte_end"]
        selected_headings = group["headings"]
        blocks.append({"block_id": f"/text/{start}:{end}/bytes/{byte_start}:{byte_end}",
            "type": "text", "text": text[start:end], "supported": True, "unsupported": [],
            "image_paths": [], "page_index": None, "bbox": None, "page_size": None,
            "locator_type": "text_range", "text_range": locator,
            "raw_locator": f"data:{data_id}#bytes={byte_start}:{byte_end};chars={start}:{end};lines={locator['line_start']}:{locator['line_end']}",
            "anchor_sha256": sha256(raw[byte_start:byte_end]).hexdigest(),
            "title": selected_headings[-1]["title"] if selected_headings else "Unheaded source content",
            "heading_path": selected_headings[-1]["heading_path"] if selected_headings else [],
            "headings": [{key: value for key, value in item.items() if key in ("level", "title", "text_range")}
                         for item in selected_headings], "referenced_images": []})
    starts = [block["text_range"]["char_start"] for block in blocks]
    for image in images:
        blocks[bisect_right(starts, image["text_range"]["char_start"]) - 1]["referenced_images"].append(image)
    return {"schema_version": MARKDOWN_SCHEMA, "data_id": data_id, "encoding": "utf-8",
        "coordinate_system": "text_ranges", "pages": [], "blocks": blocks,
        "source_byte_size": len(raw), "source_character_count": len(text),
        "source_line_count": len(ends), "profile": deepcopy(MARKDOWN_PARSER)}


def _verified_blocks(bundle):
    try:
        raw = "".join(block["text"] for block in bundle["blocks"]).encode("utf-8")
        expected = parse_markdown(raw, data_id=bundle["data_id"])
    except (TypeError, KeyError, UnicodeEncodeError):
        _fail("Markdown source requires exact UTF-8 blocks and provenance.")
    if bundle != expected or _digest(bundle) != _digest(expected):
        _fail("Markdown source structure or provenance differs from its registered bytes.")
    return {block["block_id"]: block for block in bundle["blocks"]}


def _proposal(block):
    return {"kind": "text", "semantic_type": None, "unit_type": "text", "title": block["title"],
            "content": block["text"], "block_ids": [block["block_id"]], "image_block_id": None}


def build_markdown_units(bundle):
    """Return one exact source proposal for each script-grouped Markdown block."""
    blocks = _verified_blocks(bundle)
    return [validate_proposal(_proposal(block), blocks) for block in blocks.values()]


def _segments(block):
    return [{"source_block_id": block["block_id"], "page_index": None,
        "raw_locator": block["raw_locator"], "anchor_sha256": block["anchor_sha256"],
        "source_char_range": [0, len(block["text"])], "char_start": 0, "char_end": len(block["text"]),
        "text_origin": "registered_source", "source_text_range": deepcopy(block["text_range"])}]


def markdown_content_segments(bundle, proposal):
    blocks = _verified_blocks(bundle)
    proposal = validate_proposal(proposal, blocks)
    if len(proposal["block_ids"]) != 1 or proposal != _proposal(blocks[proposal["block_ids"][0]]):
        _fail("Markdown Information must retain its exact original section.", "source_group_mismatch")
    return _segments(blocks[proposal["block_ids"][0]])


def verify_markdown_units(bundle, proposals):
    expected = build_markdown_units(bundle)
    if not isinstance(proposals, list) or proposals != expected or _digest(proposals) != _digest(expected):
        _fail("Markdown proposals must match deterministic source groups.", "source_group_mismatch")
    refs = [block["block_id"] for block in bundle["blocks"]]
    return {"status": "complete", "version": MARKDOWN_ALGORITHM,
        "source_bundle_sha256": _digest(bundle), "proposal_set_sha256": _digest(proposals),
        "proposal_count": len(proposals), "original_block_count": len(refs),
        "provided_block_ids": list(refs), "covered_block_ids": list(refs),
        "source_byte_size": bundle["source_byte_size"],
        "source_character_count": bundle["source_character_count"],
        "source_line_count": bundle["source_line_count"],
        "grouping_policy": {"boundary": "top_level_commonmark_heading",
            "title_only_ancestors": "merge_with_first_child", "separator": "",
            "offsets": "utf8_bytes_and_unicode_codepoints_half_open", "semantic_llm_calls": 0,
            "external_resources": "references_only"},
        "unit_manifest": [{"ordinal": ordinal,
            **{key: deepcopy(proposal[key]) for key in ("kind", "unit_type", "block_ids", "image_block_id")},
            "content_segments": _segments(bundle["blocks"][ordinal])}
            for ordinal, proposal in enumerate(proposals)]}
