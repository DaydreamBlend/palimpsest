"""Deterministic grouped Information, retaining exact blocks and text offsets.

Headings supply boundaries, not semantic approval. Figures with an explicit
inventory keep their historical unit shape; other media stays with its text.
"""

from collections import Counter

from .figure_coverage import figure_coverage
from .information import validate_proposal
from .section_projection import _ordered, group_source_blocks
from .source_units import _digest, _fail, _proposal, build_source_units, verify_source_units


SOURCE_GROUPS_VERSION = "source-groups-v1"
SOURCE_GROUPS_V2_VERSION = "source-groups-v2"
FURNITURE_TYPES = frozenset(("header", "footer", "page_number"))
MAX_GROUP_CHARACTERS = 12000
MAX_GROUP_PAGES = 2


def build_source_groups(bundle):
    """Assemble sections and one page-furniture group without discarding blocks."""
    legacy = build_source_units(bundle)
    ordered, primary, _ = _ordered(bundle)
    figures = [proposal for proposal in legacy if proposal["unit_type"] == "figure"]
    figure_refs = {ref for proposal in figures for ref in proposal["block_ids"]}
    furniture = [block for block in ordered
                 if block["block_id"] not in figure_refs and block["type"] in FURNITURE_TYPES]
    body = [block for block in ordered
            if block["block_id"] not in figure_refs and block["type"] not in FURNITURE_TYPES]
    proposals = [_proposal("text", group["title"] or "Unclassified source content",
                           group["text"], group["source_block_ids"])
                 for group in group_source_blocks(body, set())]
    positions = {block["block_id"]: index for index, block in enumerate(ordered)}
    proposals.extend(figures)
    proposals.sort(key=lambda proposal: min(positions[ref] for ref in proposal["block_ids"]
                                             if ref not in primary))
    if furniture:
        proposals.append(_proposal("text", "Document page furniture",
            "\n\n".join(block["text"] for block in furniture),
            [block["block_id"] for block in furniture]))
    by_id = {block["block_id"]: block for block in ordered}
    return [validate_proposal(proposal, by_id) for proposal in proposals]


def build_source_groups_v2(bundle):
    """Keep heading groups, but bound titleless/large groups at page boundaries."""
    by_id = {block["block_id"]: block for block in bundle["blocks"]}
    result = []
    for proposal in build_source_groups(bundle):
        pages = {by_id[ref]["page_index"] for ref in proposal["block_ids"]}
        page_limit = 1 if proposal["title"] == "Unclassified source content" else MAX_GROUP_PAGES
        if (proposal["title"] == "Document page furniture" or proposal["unit_type"] != "text"
                or (len(proposal["content"]) <= MAX_GROUP_CHARACTERS and len(pages) <= page_limit)):
            result.append(proposal)
            continue
        chunks, current, characters, current_pages = [], [], 0, set()
        for ref in proposal["block_ids"]:
            block = by_id[ref]
            added = len(block["text"]) + (2 if current else 0)
            next_pages = current_pages | {block["page_index"]}
            if current and (characters + added > MAX_GROUP_CHARACTERS or len(next_pages) > page_limit):
                chunks.append(current)
                current, characters, current_pages = [], 0, set()
                added = len(block["text"])
            current.append(ref)
            characters += added
            current_pages.add(block["page_index"])
        if current:
            chunks.append(current)
        for refs in chunks:
            chunk_pages = sorted({by_id[ref]["page_index"] + 1 for ref in refs})
            page_label = str(chunk_pages[0]) if len(chunk_pages) == 1 else f"{chunk_pages[0]}-{chunk_pages[-1]}"
            result.append(_proposal("text", f"{proposal['title']} · p.{page_label}",
                                    "\n\n".join(by_id[ref]["text"] for ref in refs), refs))
    positions = {block["block_id"]: index for index, block in enumerate(_ordered(bundle)[0])}
    result.sort(key=lambda proposal: min(positions[ref] for ref in proposal["block_ids"]))
    return [validate_proposal(proposal, by_id) for proposal in result]


def group_content_segments(bundle, proposal):
    """Map a verified group's content to source block codepoint ranges.

    Null content offsets mean a retained block is not transcribed in content.
    This distinguishes synthetic Figure labels and caption-only Figure content
    from original panel text that remains available in the source blocks.
    """
    by_id = {block["block_id"]: block for block in bundle["blocks"]}
    proposal = validate_proposal(proposal, by_id)
    figure = next((item for item in bundle.get("required_figures", [])
                   if item["block_id"] == proposal["image_block_id"]), None)
    if proposal["unit_type"] not in ("text", "figure") or (proposal["unit_type"] == "figure" and not figure):
        _fail("Content ranges require a grouped source proposal.", "source_group_mismatch")
    primary = figure["block_id"] if figure else None
    content_refs = ([block["block_id"] for block in bundle["blocks"]
                     if block["block_id"] in figure["caption_block_ids"]] if figure else proposal["block_ids"])
    separator = "\n" if figure else "\n\n"
    texts = [by_id[ref]["text"] for ref in content_refs]
    if figure and not any(texts):
        separator = ""
    if separator.join(texts) != proposal["content"]:
        _fail("Grouped content must retain exact original text and separators.", "source_group_mismatch")
    offsets, position = {}, 0
    for index, ref in enumerate(content_refs):
        if index:
            position += len(separator)
        offsets[ref] = (position, position + len(by_id[ref]["text"]))
        position = offsets[ref][1]
    return [{"source_block_id": ref, "page_index": by_id[ref]["page_index"],
             "raw_locator": by_id[ref]["raw_locator"], "anchor_sha256": by_id[ref]["anchor_sha256"],
             "source_char_range": None if ref == primary else [0, len(by_id[ref]["text"])],
             "char_start": offsets.get(ref, (None, None))[0],
             "char_end": offsets.get(ref, (None, None))[1],
             "text_origin": ("derived_visual_reference" if ref == primary else
                             "parser_source" if ref in offsets else "source_block_only")}
            for ref in proposal["block_ids"]]


def _verify_source_groups(bundle, proposals, builder, version):
    """Check exact deterministic grouping, all-block coverage and Figure shape."""
    expected = builder(bundle)
    if not isinstance(proposals, list) or proposals != expected or _digest(proposals) != _digest(expected):
        _fail("Converted groups must exactly match the script's source grouping.", "source_group_mismatch")
    provided = [block["block_id"] for block in bundle["blocks"]]
    if Counter(ref for proposal in proposals for ref in proposal["block_ids"]) != Counter(provided):
        _fail("Every original and synthetic block must be assigned exactly once.", "incomplete_source_coverage")
    figure_coverage({**bundle, "extraction_scope": "whole_document"}, proposals)
    # Reuse the established ledger and transcription review, preserving its scope.
    ledger = verify_source_units(bundle, build_source_units(bundle))
    ledger.update(version=version, proposal_count=len(proposals),
                  proposal_set_sha256=_digest(proposals),
                  grouping_policy={"boundary": ("explicit_title_and_major_hint_v1" if version == SOURCE_GROUPS_VERSION
                                                  else "explicit_title_then_page_and_character_bounds_v2"),
                      "page_furniture": "one_separate_group", "separator": "\n\n",
                      "required_figures": "source_units_v1_unchanged",
                      "maximum_group_characters": (None if version == SOURCE_GROUPS_VERSION else MAX_GROUP_CHARACTERS),
                      "maximum_group_pages": (None if version == SOURCE_GROUPS_VERSION else MAX_GROUP_PAGES),
                      "titleless_group_pages": (None if version == SOURCE_GROUPS_VERSION else 1),
                      "offsets": "unicode_codepoints_half_open", "semantic_llm_calls": 0},
                  unit_manifest=[{"ordinal": ordinal,
                      **{key: list(proposal[key]) if key == "block_ids" else proposal[key]
                         for key in ("kind", "unit_type", "block_ids", "image_block_id")},
                      "content_segments": group_content_segments(bundle, proposal)}
                     for ordinal, proposal in enumerate(proposals)])
    return ledger


def verify_source_groups(bundle, proposals):
    return _verify_source_groups(bundle, proposals, build_source_groups, SOURCE_GROUPS_VERSION)


def verify_source_groups_v2(bundle, proposals):
    return _verify_source_groups(bundle, proposals, build_source_groups_v2, SOURCE_GROUPS_V2_VERSION)
