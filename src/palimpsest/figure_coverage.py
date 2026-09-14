"""Required Figure coverage, separate from semantic approval and persistence.

The caller supplies a verified, frozen Figure inventory. This module checks its
references and proposal coverage; it does not establish that the inventory or
the proposed descriptions faithfully represent the original document.
"""

from .errors import PalimpsestError
from .information import validate_decisions


def _fail(rule, ordinal=None):
    details = {"validation_rule": rule}
    if ordinal is not None:
        details["candidate_index"] = ordinal
    raise PalimpsestError("incomplete_figure_coverage",
                          "Required Figure coverage is incomplete or inconsistent.", 4, details)


def _references(value, known, *, nonempty=False):
    if (not isinstance(value, list) or (nonempty and not value)
            or any(not isinstance(item, str) or item not in known for item in value)
            or len(set(value)) != len(value)):
        _fail("Figure references must be unique known block IDs.")
    return set(value)


def figure_coverage(bundle, proposals, decisions=None):
    """Return a body-free coverage ledger, or reject structural incompleteness.

    ``proposals=None`` checks the inventory before model generation. With proposals
    but no decisions, coverage remains pending_validation even when all groups are
    present. Only explicit accepted decisions for every required Figure give
    ``complete``; rejected and needs_human decisions give ``incomplete`` unchanged.
    """
    if not isinstance(bundle, dict):
        _fail("A normalized source bundle is required.")
    required = bundle.get("required_figures", [])
    scope = bundle.get("extraction_scope", "whole_document")
    if scope not in ("whole_document", "figures_only") or not isinstance(required, list):
        _fail("Figure inventory and extraction scope must be explicit and valid.")
    if not required:
        if scope == "figures_only":
            _fail("The figures_only scope requires a nonempty Figure inventory.")
        return {"status": "not_required", "required_count": 0, "figures": []}

    blocks = bundle.get("blocks")
    if (not isinstance(blocks, list)
            or any(not isinstance(block, dict) or not isinstance(block.get("block_id"), str)
                   for block in blocks)):
        _fail("Figure inventory requires normalized source blocks.")
    by_id = {block["block_id"]: block for block in blocks}
    if len(by_id) != len(blocks):
        _fail("Source block IDs must be unique.")
    figures, expected_refs, seen_ids, seen_numbers, seen_blocks = [], [], set(), set(), set()
    for item in required:
        if not isinstance(item, dict):
            _fail("Each required Figure must be an inventory object.")
        figure_id, number, primary = item.get("figure_id"), item.get("number"), item.get("block_id")
        if (not isinstance(figure_id, str) or not figure_id or type(number) is not int or number < 1
                or not isinstance(primary, str) or primary not in by_id):
            _fail("Each Figure requires an ID, positive number, and known primary block.")
        if figure_id in seen_ids or number in seen_numbers or primary in seen_blocks:
            _fail("Figure IDs, numbers, and primary blocks must be unique.")
        seen_ids.add(figure_id)
        seen_numbers.add(number)
        seen_blocks.add(primary)
        block = by_id[primary]
        if (block.get("type") != "image" or not isinstance(block.get("image_paths"), list)
                or not block["image_paths"]):
            _fail("Each Figure primary must be an image block with an actual Figure artifact.")
        members = _references(item.get("member_block_ids"), by_id, nonempty=True)
        captions = _references(item.get("caption_block_ids"), by_id)
        if primary in members | captions:
            _fail("Figure source members must not refer to their own synthetic primary.")
        expected_refs.append({primary} | members | captions)
        figures.append({"figure_id": figure_id, "number": number, "block_id": primary,
                        "ordinal": None, "verdict": None})
    ledger = {"status": "pending_generation", "required_count": len(figures), "figures": figures}
    if proposals is None:
        if decisions is not None:
            _fail("Figure decisions require the corresponding proposal set.")
        return ledger
    if not isinstance(proposals, list):
        _fail("Figure coverage requires a proposal array.")
    primary_index = {figure["block_id"]: index for index, figure in enumerate(figures)}
    for ordinal, proposal in enumerate(proposals):
        if not isinstance(proposal, dict):
            _fail("Each Figure proposal must be an object.", ordinal)
        primary = proposal.get("image_block_id")
        if primary is not None and not isinstance(primary, str):
            _fail("A proposal image reference must be a block ID or null.", ordinal)
        if primary not in primary_index:
            if scope == "figures_only":
                _fail("The figures_only scope forbids text or unrelated image proposals.", ordinal)
            continue
        index = primary_index[primary]
        if proposal.get("kind") != "image" or not (
                proposal.get("semantic_type") == "figure" or
                (proposal.get("semantic_type") is None and proposal.get("unit_type") == "figure")):
            _fail("A required Figure must be represented by an Image Figure proposal.", ordinal)
        if figures[index]["ordinal"] is not None:
            _fail("Each required Figure must have exactly one proposal.", ordinal)
        refs = _references(proposal.get("block_ids"), by_id, nonempty=True)
        if not expected_refs[index].issubset(refs):
            _fail("A Figure proposal must cite its primary and every member and caption block.", ordinal)
        figures[index]["ordinal"] = ordinal
    if any(figure["ordinal"] is None for figure in figures):
        _fail("Every required Figure must have a proposal; count alone is insufficient.")
    ledger["status"] = "pending_validation"
    if decisions is not None:
        ordered = validate_decisions(decisions, len(proposals))
        for figure in figures:
            figure["verdict"] = ordered[figure["ordinal"]]["verdict"]
        ledger["status"] = ("complete" if all(figure["verdict"] == "accepted" for figure in figures)
                            else "incomplete")
    return ledger
