"""Deterministic source units with exhaustive block accounting and no inference.

Blocks are the conversion units, independent of future model batch sizes. Raw
parser structures remain in the frozen bundle and canonical source payload.
This module verifies conversion equality, not parser accuracy or world truth.
"""

from collections import Counter
from hashlib import sha256
import json

from .data import data_id as validate_data_id
from .errors import PalimpsestError
from .figure_coverage import figure_coverage
from .information import validate_proposal


SOURCE_UNITS_VERSION = "source-units-v1"


def _fail(rule, code="invalid_source_units"):
    raise PalimpsestError(code, "Source-preserving conversion could not be verified.", 4,
                          {"validation_rule": rule})


def _digest(value):
    try:
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
        return sha256(encoded).hexdigest()
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError):
        _fail("Source conversion requires finite UTF-8 JSON values.")


def _blocks(bundle):
    if (not isinstance(bundle, dict) or bundle.get("schema_version") != 1
            or bundle.get("coordinate_system") != "pdf_points_top_left"):
        _fail("A normalized bundle with original PDF coordinates is required.")
    validate_data_id(bundle.get("data_id"))
    pages, blocks = bundle.get("pages"), bundle.get("blocks")
    if not isinstance(pages, list) or not pages or not isinstance(blocks, list):
        _fail("The complete page and block inventory is required.")
    indices = [page.get("page_index") if isinstance(page, dict) else None for page in pages]
    if (any(type(index) is not int for index in indices)
            or sorted(indices) != list(range(len(pages)))):
        _fail("Original page indices must be complete and unique.")
    by_id = {}
    if bundle.get("unsupported_block_ids"):
        _fail("Unsupported source structures must not be silently omitted.", "unsupported_parser_output")
    for block in blocks:
        if (not isinstance(block, dict) or not isinstance(block.get("block_id"), str)
                or not block["block_id"] or block["block_id"] in by_id
                or type(block.get("page_index")) is not int or block["page_index"] not in indices
                or not isinstance(block.get("type"), str) or not block["type"]
                or not isinstance(block.get("text"), str) or not isinstance(block.get("image_paths"), list)):
            _fail("Each source block requires a unique ID, source type, page, text, and image list.")
        if block.get("supported") is not True or block.get("unsupported"):
            _fail("Unsupported source structures must not be silently omitted.", "unsupported_parser_output")
        if block.get("page_size") != pages[indices.index(block["page_index"])].get("page_size"):
            _fail("Each block must retain its original page size.")
        by_id[block["block_id"]] = block
    _digest(bundle)
    return blocks, by_id


def _proposal(unit_type, title, content, refs, image_id=None):
    return {"kind": "image" if unit_type in ("image", "figure") else "text",
            "semantic_type": None, "unit_type": unit_type, "title": title,
            "content": content, "block_ids": refs, "image_block_id": image_id}


def build_source_units(bundle):
    """Preserve every original block, grouping only explicitly inventoried Figures.

    The historical figures_only scope never removes other source material here.
    Group captions are joined in original block order. All other text is copied
    exactly, including empty content, whitespace, line endings, and Unicode form.
    """
    blocks, by_id = _blocks(bundle)
    figure_coverage({**bundle, "extraction_scope": "whole_document"}, None)
    required = bundle.get("required_figures", [])
    grouped, consumed, primaries, assigned = [], {}, set(), set()
    for index, figure in enumerate(required):
        primary = figure["block_id"]
        primaries.add(primary)
        originals = set(figure["member_block_ids"]) | set(figure["caption_block_ids"])
        if originals & assigned:
            _fail("An original source block must not be assigned to multiple Figure units.")
        assigned.update(originals)
        refs = [block["block_id"] for block in blocks if block["block_id"] in originals]
        caption_ids = set(figure["caption_block_ids"])
        caption_texts = [block["text"] for block in blocks if block["block_id"] in caption_ids]
        caption = "\n".join(caption_texts) if any(caption_texts) else ""
        title = f"Figure {figure['number']}"
        grouped.append(_proposal("figure", title, caption, [primary] + refs, primary))
        for ref in refs + [primary]:
            consumed[ref] = index
    if any(set(figure["member_block_ids"] + figure["caption_block_ids"]) & primaries for figure in required):
        _fail("Figure members and captions must refer to original blocks, not synthetic Figures.")

    proposals, emitted = [], set()
    for ordinal, block in enumerate(blocks):
        ref = block["block_id"]
        if ref in consumed:
            index = consumed[ref]
            if index not in emitted:
                proposals.append(grouped[index])
                emitted.add(index)
            continue
        source_type = block["type"]
        if source_type in ("table", "table_body"):
            unit_type = "table"
        elif source_type in ("equation", "interline_equation", "inline_equation"):
            unit_type = "equation"
        else:
            unit_type = "image" if block["image_paths"] else "text"
        title = (block["text"] if source_type in ("title", "doc_title", "paragraph_title") and block["text"]
                 else f"Page {block['page_index'] + 1}, {source_type}, block {ordinal + 1}")
        proposals.append(_proposal(unit_type, title, block["text"], [ref], ref if unit_type == "image" else None))
    return [validate_proposal(proposal, by_id) for proposal in proposals]


def verify_source_units(bundle, proposals):
    """Verify exact conversion and all-block accounting; return a body-free ledger."""
    expected = build_source_units(bundle)
    if not isinstance(proposals, list) or proposals != expected or _digest(proposals) != _digest(expected):
        _fail("Converted units must exactly match every source unit in original order.", "source_unit_mismatch")
    provided = [block["block_id"] for block in bundle["blocks"]]
    covered = Counter(ref for proposal in proposals for ref in proposal["block_ids"])
    if covered != Counter(provided):
        _fail("Every original and synthetic primary block must be accounted for exactly once.", "incomplete_source_coverage")
    primaries = {figure["block_id"] for figure in bundle.get("required_figures", [])}
    result = {"status": "complete", "version": SOURCE_UNITS_VERSION,
            "source_bundle_sha256": _digest(bundle), "proposal_set_sha256": _digest(proposals),
            "proposal_count": len(proposals), "original_block_count": len(set(provided) - primaries),
            "provided_block_ids": provided, "covered_block_ids": [ref for ref in provided if ref in covered],
            "unit_manifest": [{"ordinal": ordinal, **{key: list(proposal[key]) if key == "block_ids" else proposal[key] for key in (
                "kind", "unit_type", "block_ids", "image_block_id")}}
                for ordinal, proposal in enumerate(proposals)]}
    if selection := bundle.get('transcription_selection'):
        result['transcription_review'] = {
            'comparison_status':selection['status'], 'selection_version':selection['version'],
            'selection_sha256':_digest(selection), 'source_fidelity_verified':False,
            'unresolved_block_ids':[r['block_id'] for r in selection['unresolved']],
            'unmatched_ocr_block_ids':selection['unmatched_ocr_block_ids'],
            'selected_change_count':sum(len(r['changes']) for r in selection['blocks']),
            'storage_policy':'preserve native on ambiguity; retain both raw inputs and unresolved comparison inventory',
            'completion_scope':'source assembly and persistence only; not transcription fidelity approval'}
    return result
