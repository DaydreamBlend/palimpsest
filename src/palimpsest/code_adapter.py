"""Parse retained Python dossier members without executing or rewriting source.

UTF-8 byte and Unicode character ranges are half-open. As in other text source
adapters, line ranges are one-based and inclusive, counting only CR/LF/CRLF.
AST syntax is structural metadata, never a claim about executed behavior.
"""

import ast
from bisect import bisect_right
from copy import deepcopy
from hashlib import sha256
from io import StringIO
import platform
from pathlib import PurePosixPath
import re
import tokenize

from .code_snapshot import manifest_from_bytes
from .data import data_id as validate_data_id
from .errors import PalimpsestError
from .information import validate_proposal
from .source_units import _digest


CODE_ALGORITHM = "python-code-groups-v1"
CODE_SCHEMA = "python-code-source-v1"
CODE_PARSER = {"provider": "python-stdlib-ast", "version": platform.python_version(),
    "implementation": platform.python_implementation(), "adapter_version": CODE_SCHEMA,
    "encoding": "utf-8", "ast_mode": "exec", "type_comments": True,
    "target_characters": 6000, "source_execution": False, "semantic_llm_calls": 0}
_DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _fail(message, code="invalid_code_source"):
    raise PalimpsestError(code, message, 4)


def _locations(text):
    ends = [match.end() for match in re.finditer(r"\r\n|\r|\n", text)]
    starts = [0, *ends]
    byte_starts = [0]
    for start, end in zip(starts, starts[1:]):
        byte_starts.append(byte_starts[-1] + len(text[start:end].encode("utf-8")))

    def span(start, end):
        first = bisect_right(ends, start)
        last = bisect_right(ends, max(start, end - 1))
        finish = bisect_right(ends, end)
        return {"byte_start": byte_starts[first] + len(text[starts[first]:start].encode("utf-8")),
            "byte_end": byte_starts[finish] + len(text[starts[finish]:end].encode("utf-8")),
            "char_start": start, "char_end": end, "line_start": first + 1, "line_end": last + 1}

    count = max(1, len(ends) + int(not ends or ends[-1] != len(text)))
    return starts, span, count


def _python_groups(text, entry, global_span):
    starts, member_span, _ = _locations(text)
    base = entry["body_char_start"]
    try:
        tree = ast.parse(text.removeprefix("\ufeff"), filename=entry["path"], mode="exec", type_comments=True)
    except SyntaxError as error:
        return [{"start": 0, "end": len(text), "group_kind": "unparsed_python",
            "enclosing_symbols": []}], [], "syntax_error", {
                "message": error.msg, "line": error.lineno, "offset": error.offset,
                "end_line": error.end_lineno, "end_offset": error.end_offset,
                "coordinate_system": "python_syntax_error_one_based_character_offsets_bom_removed"}

    # AST decorator expressions may start below a parenthesized `@(` line.
    # Tokenization locates the actual decorator statement without inspecting strings.
    decorators, statement_start = [], True
    normalized = text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    for token in tokenize.generate_tokens(StringIO(normalized).readline):
        if token.type == tokenize.NEWLINE:
            statement_start = True
        elif token.type not in (tokenize.NL, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER):
            if statement_start and token.string == "@":
                decorators.append(token.start)
            statement_start = False

    def first_position(node):
        if node.decorator_list:
            candidates = [position for position in decorators
                if position[0] < node.lineno and position[1] == node.col_offset]
            return candidates[-len(node.decorator_list)]
        return node.lineno, node.col_offset

    def start(node):
        return starts[first_position(node)[0] - 1]

    def exact_span(node):
        first, column = first_position(node)
        # AST columns count UTF-8 bytes; the BOM was removed only for parsing.
        prefix = int(first == 1 and text.startswith("\ufeff"))
        line_start = starts[first - 1] + prefix
        line_end = starts[first] if first < len(starts) else len(text)
        begin = line_start + len(text[line_start:line_end].encode("utf-8")[:column].decode("utf-8"))
        prefix = int(node.end_lineno == 1 and text.startswith("\ufeff"))
        line_start = starts[node.end_lineno - 1] + prefix
        line_end = starts[node.end_lineno] if node.end_lineno < len(starts) else len(text)
        end = line_start + len(text[line_start:line_end].encode("utf-8")[:node.end_col_offset].decode("utf-8"))
        return member_span(begin, end)

    symbols, by_node = [], {}

    def visit(node, parents):
        if isinstance(node, _DEFINITIONS):
            location = exact_span(node)
            symbol = {"name": node.name, "qualified_name": ".".join([*parents, node.name]),
                "kind": "class" if isinstance(node, ast.ClassDef) else (
                    "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"),
                "member_text_range": location,
                "text_range": global_span(base + location["char_start"], base + location["char_end"])}
            symbols.append(symbol)
            by_node[id(node)] = symbol
            parents = [*parents, node.name]
        for child in ast.iter_child_nodes(node):
            visit(child, parents)

    visit(tree, [])
    target = CODE_PARSER["target_characters"]

    def partition(nodes, begin, end, enclosing):
        definitions = [node for node in nodes if isinstance(node, _DEFINITIONS)]
        if not definitions:
            return [{"start": begin, "end": end, "group_kind": "class_preamble" if enclosing else "module_content",
                "enclosing_symbols": enclosing}]
        result = []
        if begin < start(definitions[0]):
            result.append({"start": begin, "end": start(definitions[0]),
                "group_kind": "class_preamble" if enclosing else "module_preamble", "enclosing_symbols": enclosing})
        for index, node in enumerate(definitions):
            left = start(node)
            right = start(definitions[index + 1]) if index + 1 < len(definitions) else end
            if isinstance(node, ast.ClassDef) and right - left > target:
                result.extend(partition(node.body, left, right, [*enclosing, by_node[id(node)]]))
            elif (result and result[-1]["group_kind"] == "definitions"
                    and result[-1]["enclosing_symbols"] == enclosing
                    and right - result[-1]["start"] <= target):
                result[-1]["end"] = right
            else:
                result.append({"start": left, "end": right, "group_kind": "definitions",
                    "enclosing_symbols": enclosing})
        return result

    return partition(tree.body, 0, len(text), []), symbols, "parsed", None


def parse_code_snapshot(raw: bytes, *, data_id: str):
    """Verify a registered dossier, then group Python syntax and preserve all gaps."""
    validate_data_id(data_id)
    if not isinstance(raw, bytes) or sha256(raw).hexdigest() != data_id:
        _fail("Code dossier bytes must match the registered Data SHA-256.", "integrity_conflict")
    try:
        manifest = manifest_from_bytes(raw, expected_sha256=data_id)
        text = raw.decode("utf-8")
    except (ValueError, TypeError, KeyError, UnicodeError):
        _fail("Code D2I requires a complete verified UTF-8 code snapshot dossier.")
    _, global_span, line_count = _locations(text)
    blocks = []

    def append(start, end, title, context):
        location = global_span(start, end)
        byte_start, byte_end = location["byte_start"], location["byte_end"]
        blocks.append({"block_id": f"/text/{start}:{end}/bytes/{byte_start}:{byte_end}",
            "type": "text", "text": text[start:end], "supported": True, "unsupported": [],
            "image_paths": [], "page_index": None, "bbox": None, "page_size": None,
            "locator_type": "text_range", "text_range": location,
            "raw_locator": f"data:{data_id}#bytes={byte_start}:{byte_end};chars={start}:{end};lines={location['line_start']}:{location['line_end']}",
            "anchor_sha256": sha256(raw[byte_start:byte_end]).hexdigest(),
            "title": title, "heading_path": [], "headings": [], "referenced_images": [],
            "code_context": deepcopy(context)})

    cursor = 0
    for entry in manifest["files"]:
        begin, end = entry["body_char_start"], entry["body_char_end"]
        if cursor < begin:
            append(cursor, begin, "Dossier metadata", {"representation_role": "dossier_metadata"})
        content = text[begin:end]
        _, member_span, _ = _locations(content)
        python = PurePosixPath(entry["path"]).suffix.casefold() in (".py", ".pyi")
        if python:
            groups, symbols, status, error = _python_groups(content, entry, global_span)
        else:
            groups = [{"start": 0, "end": len(content), "group_kind": "opaque_member", "enclosing_symbols": []}]
            symbols, status, error = [], "not_python", None
        for group in groups:
            left, right = group["start"], group["end"]
            contained = [symbol for symbol in symbols if left <= symbol["member_text_range"]["char_start"] < right]
            names = [symbol["qualified_name"] for symbol in contained if not any(
                other["member_text_range"]["char_start"] <= symbol["member_text_range"]["char_start"]
                < other["member_text_range"]["char_end"] and other is not symbol for other in contained)]
            # Names are display metadata; the full exact symbol inventory stays in code_context.
            title = entry["path"] + (" — " + ", ".join(names) if names else " — " + group["group_kind"])
            append(begin + left, begin + right, title, {
                "representation_role": "source_member", "member_path": entry["path"],
                "member_sha256": entry["sha256"], "member_byte_size": entry["byte_size"],
                "member_text_range": member_span(left, right), "language": "python" if python else "opaque",
                "parse_status": status, "parse_error": error, "group_kind": group["group_kind"],
                "symbols": contained, "enclosing_symbols": group["enclosing_symbols"]})
        cursor = end
    if cursor < len(text):
        append(cursor, len(text), "Dossier metadata and snapshot manifest", {"representation_role": "dossier_metadata"})
    return {"schema_version": CODE_SCHEMA, "data_id": data_id, "encoding": "utf-8",
        "coordinate_system": "text_ranges", "pages": [], "blocks": blocks,
        "source_byte_size": len(raw), "source_character_count": len(text), "source_line_count": line_count,
        "profile": deepcopy(CODE_PARSER), "snapshot_manifest": manifest}


def _verified_blocks(bundle):
    try:
        raw = "".join(block["text"] for block in bundle["blocks"]).encode("utf-8")
        expected = parse_code_snapshot(raw, data_id=bundle["data_id"])
    except (TypeError, KeyError, UnicodeEncodeError):
        _fail("Code source requires exact UTF-8 blocks and provenance.")
    if bundle != expected or _digest(bundle) != _digest(expected):
        _fail("Code source structure or provenance differs from its registered bytes.")
    return {block["block_id"]: block for block in bundle["blocks"]}


def _proposal(block):
    return {"kind": "text", "semantic_type": None, "unit_type": "text", "title": block["title"],
        "content": block["text"], "block_ids": [block["block_id"]], "image_block_id": None}


def build_code_units(bundle):
    blocks = _verified_blocks(bundle)
    return [validate_proposal(_proposal(block), blocks) for block in blocks.values()]


def _segments(block):
    return [{"source_block_id": block["block_id"], "page_index": None,
        "raw_locator": block["raw_locator"], "anchor_sha256": block["anchor_sha256"],
        "source_char_range": [0, len(block["text"])], "char_start": 0, "char_end": len(block["text"]),
        "text_origin": "registered_source", "source_text_range": deepcopy(block["text_range"]),
        "code_context": deepcopy(block["code_context"])}]


def code_content_segments(bundle, proposal):
    blocks = _verified_blocks(bundle)
    proposal = validate_proposal(proposal, blocks)
    if len(proposal["block_ids"]) != 1 or proposal != _proposal(blocks[proposal["block_ids"][0]]):
        _fail("Code Information must retain its exact original source group.", "source_group_mismatch")
    return _segments(blocks[proposal["block_ids"][0]])


def verify_code_units(bundle, proposals):
    expected = build_code_units(bundle)
    if not isinstance(proposals, list) or proposals != expected or _digest(proposals) != _digest(expected):
        _fail("Code proposals must match deterministic source groups.", "source_group_mismatch")
    refs = [block["block_id"] for block in bundle["blocks"]]
    return {"status": "complete", "version": CODE_ALGORITHM,
        "source_bundle_sha256": _digest(bundle), "proposal_set_sha256": _digest(proposals),
        "proposal_count": len(proposals), "original_block_count": len(refs),
        "provided_block_ids": list(refs), "covered_block_ids": list(refs),
        "source_byte_size": bundle["source_byte_size"], "source_character_count": bundle["source_character_count"],
        "source_line_count": bundle["source_line_count"],
        "grouping_policy": {"boundary": "python_ast_definitions_and_class_members",
            "target_characters": CODE_PARSER["target_characters"], "target_is_soft": True,
            "separator": "", "offsets": "utf8_bytes_and_unicode_codepoints_half_open",
            "line_ranges": "one_based_inclusive", "semantic_llm_calls": 0,
            "non_python": "preserved_opaque", "syntax_error": "preserved_whole_member"},
        "unit_manifest": [{"ordinal": ordinal,
            **{key: deepcopy(proposal[key]) for key in ("kind", "unit_type", "block_ids", "image_block_id")},
            "content_segments": _segments(bundle["blocks"][ordinal])}
            for ordinal, proposal in enumerate(proposals)]}
