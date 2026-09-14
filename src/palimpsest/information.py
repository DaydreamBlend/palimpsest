"""Source Information structure and retained legacy semantic fingerprints.

U11 source units preserve parser content and grounding without interpreting it.
The legacy schema remains available to verify historical semantic snapshots.
"""

from hashlib import sha256
import json
import math
from pathlib import PurePosixPath
import re
import unicodedata

from .errors import PalimpsestError


SCHEMA_VERSION = "information-v1"
SOURCE_SCHEMA_VERSION = "source-information-v1"
UNIT_TYPES = ("text", "figure", "image", "table", "equation")
KINDS = ("text", "image")
IMAGE_SOURCE_TYPES = ("image", "chart", "table")
SEMANTIC_TYPES = ("proposition", "observation", "procedure", "definition", "figure")
VERDICTS = ("accepted", "rejected", "needs_human")
REASON_CODE_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"

PROPOSAL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "kind": {"type": "string", "enum": list(KINDS)},
        "semantic_type": {"type": "string", "enum": list(SEMANTIC_TYPES)},
        "title": {"type": "string", "minLength": 1},
        "content": {
            "type": "string", "minLength": 1,
            "description": "An independently understandable, source-faithful statement; retain relevant conditions.",
        },
        "block_ids": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "image_block_id": {
            "type": ["string", "null"],
            "description": "For kind=image, the ID of an image/chart/table source block with an actual crop; null for text.",
        },
    },
    "required": ["kind", "semantic_type", "title", "content", "block_ids", "image_block_id"],
}
GENERATOR_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"proposals": {"type": "array", "items": PROPOSAL_SCHEMA}},
    "required": ["proposals"],
}
VALIDATOR_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "ordinal": {"type": "integer", "minimum": 0},
                    "verdict": {"type": "string", "enum": list(VERDICTS)},
                    "reason_codes": {"type": "array", "items": {
                        "type": "string", "pattern": REASON_CODE_PATTERN,
                        "description": "A short lower snake_case classification code; never source or candidate prose.",
                    }},
                    "reason": {
                        "type": "string", "minLength": 1,
                        "description": "A short, externally checkable decision explanation, not private chain-of-thought.",
                    },
                },
                "required": ["ordinal", "verdict", "reason_codes", "reason"],
            },
        },
    },
    "required": ["decisions"],
}


def _fail(message, code="invalid_candidate"):
    raise PalimpsestError(code, message, 4)


def _text(value, field, code="invalid_candidate"):
    if not isinstance(value, str):
        _fail(f"{field} must be a string.", code)
    value = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n")).strip()
    if not value or "\x00" in value:
        _fail(f"{field} must contain nonempty text without NUL.", code)
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        _fail(f"{field} contains invalid Unicode.", code)
    return value


def _digest_value(value, field):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        _fail(f"{field} must be a lowercase SHA-256 digest.")
    return value


def _coordinates(value, length, field):
    if not isinstance(value, list) or len(value) != length:
        _fail(f"{field} has an invalid shape.")
    result = []
    for number in value:
        if type(number) not in (int, float):
            _fail(f"{field} must contain finite numbers.")
        try:
            numeric = float(number)
        except (ValueError, OverflowError):
            _fail(f"{field} must contain finite numbers.")
        if not math.isfinite(numeric):
            _fail(f"{field} must contain finite numbers.")
        result.append(0.0 if numeric == 0 else numeric)
    return result


def _locus(block_id, blocks_by_id, *, source_unit=False):
    if not isinstance(block_id, str) or not block_id or block_id not in blocks_by_id:
        _fail("A proposal references an unknown block.")
    block = blocks_by_id[block_id]
    if not isinstance(block, dict) or block.get("block_id") != block_id:
        _fail("A block reference does not match its normalized block ID.")
    if block.get('locator_type') == 'text_range':
        location = block.get('text_range')
        fields = {'byte_start', 'byte_end', 'char_start', 'char_end', 'line_start', 'line_end'}
        if (not source_unit or not isinstance(location, dict) or set(location) != fields
                or any(type(location[key]) is not int for key in fields)
                or any(block.get(key) is not None for key in ('page_index', 'bbox', 'page_size'))
                or not 0 <= location['byte_start'] <= location['byte_end']
                or not 0 <= location['char_start'] <= location['char_end']
                or not 1 <= location['line_start'] <= location['line_end']):
            _fail('A text source requires exact byte, character and line ranges without PDF coordinates.')
        text = _source_text(block.get('text'), 'content', empty=True)
        raw = text.encode('utf-8')
        if (location['char_end'] - location['char_start'] != len(text)
                or location['byte_end'] - location['byte_start'] != len(raw)
                or block.get('anchor_sha256') != sha256(raw).hexdigest()):
            _fail('Text source range and anchor must match exact UTF-8 source bytes.')
        return {'locator_type': 'text_range', 'text_range': dict(location),
                'anchor_sha256': block['anchor_sha256']}
    page = block.get("page_index")
    if type(page) is not int or page < 0:
        _fail("A block must reference a nonnegative original page index.")
    bbox = _coordinates(block.get("bbox"), 4, "bbox")
    page_size = _coordinates(block.get("page_size"), 2, "page_size")
    x0, y0, x1, y1 = bbox
    width, height = page_size
    inside = (0 <= x0 <= x1 <= width and 0 <= y0 <= y1 <= height and width > 0 and height > 0)
    if not inside or (not source_unit and (x0 == x1 or y0 == y1)):
        _fail("A block region must be inside its original page.")
    return {
        "page_index": page, "bbox": bbox, "page_size": page_size,
        "anchor_sha256": _digest_value(block.get("anchor_sha256"), "anchor_sha256"),
    }


def _image_digests(block, *, source_unit=False):
    paths = block.get("image_paths")
    if ((not source_unit and block.get("type") not in IMAGE_SOURCE_TYPES)
            or not isinstance(paths, list) or not paths):
        _fail("An image proposal must reference an image, chart, or table block with an image artifact.")
    digests = []
    for artifact in paths:
        if not isinstance(artifact, dict):
            _fail("Image artifact metadata must be an object.")
        path = artifact.get("path")
        if (not isinstance(path, str) or not path or "\x00" in path or "\\" in path
                or ":" in path or PurePosixPath(path).is_absolute()
                or ".." in PurePosixPath(path).parts or path in (".", "..")):
            _fail("Image artifact paths must stay relative to the parser output root.")
        digests.append(_digest_value(artifact.get("sha256"), "image sha256"))
    return sorted(digests)


def _source_text(value, field, *, empty=False):
    if not isinstance(value, str) or (not empty and not value) or "\x00" in value:
        _fail(f"Source {field} must be a preservable string without NUL.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        _fail(f"Source {field} must contain valid UTF-8 text.")
    return value


def _validate_source_proposal(proposal, blocks_by_id):
    if set(proposal) != set(PROPOSAL_SCHEMA["required"]) | {"unit_type"}:
        _fail("Source proposal fields must exactly match the source Information schema.")
    if (not isinstance(blocks_by_id, dict) or proposal["unit_type"] not in UNIT_TYPES
            or proposal["semantic_type"] is not None):
        _fail("Source Information requires a supported unit type and null semantic_type.")
    kind = "image" if proposal["unit_type"] in ("image", "figure") else "text"
    if proposal["kind"] != kind:
        _fail("Source Information kind must match its structural unit type.")
    refs = proposal["block_ids"]
    if not isinstance(refs, list) or not refs:
        _fail("A source unit requires original block references.")
    seen = set()
    for ref in refs:
        _locus(ref, blocks_by_id, source_unit=True)
        if ref in seen:
            _fail("Source unit block references must not be duplicated.")
        seen.add(ref)
    image_id = proposal["image_block_id"]
    if kind == "image":
        if not isinstance(image_id, str) or image_id not in seen:
            _fail("A source image must reference its grounded primary image block.")
        _image_digests(blocks_by_id[image_id], source_unit=True)
    elif image_id is not None:
        _fail("Source text, table, and equation units require null image_block_id.")
    return {"kind": kind, "semantic_type": None, "unit_type": proposal["unit_type"],
            "title": _source_text(proposal["title"], "title"),
            "content": _source_text(proposal["content"], "content", empty=True),
            "block_ids": list(refs), "image_block_id": image_id}


def validate_proposal(proposal, blocks_by_id):
    """Return a normalized, structurally grounded proposal; do not accept it."""
    if isinstance(proposal, dict) and "unit_type" in proposal:
        return _validate_source_proposal(proposal, blocks_by_id)
    if not isinstance(proposal, dict) or set(proposal) != set(PROPOSAL_SCHEMA["required"]):
        _fail("Proposal fields must exactly match the Information schema.")
    if not isinstance(blocks_by_id, dict):
        _fail("Normalized source blocks must be a mapping.")
    if proposal["kind"] not in KINDS or proposal["semantic_type"] not in SEMANTIC_TYPES:
        _fail("Unsupported Information kind or semantic type.")
    block_ids = proposal["block_ids"]
    if not isinstance(block_ids, list) or not block_ids:
        _fail("A proposal must have at least one source block.")
    seen = set()
    for block_id in block_ids:
        _locus(block_id, blocks_by_id)
        if block_id in seen:
            _fail("Proposal block references must not be duplicated.")
        seen.add(block_id)
    image_id = proposal["image_block_id"]
    if proposal["kind"] == "image":
        if not isinstance(image_id, str) or image_id not in seen:
            _fail("The image block must be included in the proposal groundings.")
        _image_digests(blocks_by_id[image_id])
    elif image_id is not None:
        _fail("Text proposals must have a null image_block_id.")
    return {
        "kind": proposal["kind"], "semantic_type": proposal["semantic_type"],
        "title": _text(proposal["title"], "title"),
        "content": _text(proposal["content"], "content"),
        "block_ids": list(block_ids), "image_block_id": image_id,
    }


def _serialize(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def _fingerprint(domain, value, *, schema=SCHEMA_VERSION):
    try:
        envelope = _serialize({"schema": schema, "domain": domain, "value": value})
        return sha256(envelope.encode("utf-8")).hexdigest()
    except (TypeError, ValueError, UnicodeEncodeError):
        _fail("Fingerprint inputs must be finite, UTF-8 JSON values.")


def fingerprints(data_id, proposal, blocks_by_id):
    """Exact projections, not semantic equivalence or a global uniqueness rule.

    The returned context_fingerprint is a domain context digest only. The
    application must bind it to the actual frozen parser/Generator/Validator,
    policy/schema profiles and any additional authoritative context before using
    a final validation-cache/rejection key. Opaque parser execution IDs are not
    Information identity. Display title is absent from both semantic digests.
    """
    _digest_value(data_id, "data_id")
    proposal = validate_proposal(proposal, blocks_by_id)
    if "unit_type" in proposal:
        source = {key: proposal[key] for key in ("kind", "unit_type", "content")}
        source["groundings"] = [_locus(ref, blocks_by_id, source_unit=True) for ref in proposal["block_ids"]]
        source["image_sha256"] = [digest for ref in proposal["block_ids"]
                                  if blocks_by_id[ref].get("image_paths")
                                  for digest in _image_digests(blocks_by_id[ref], source_unit=True)]
        return {
            "identity_fingerprint": _fingerprint("source_information_identity", {
                "data_id": data_id, "source": source}, schema=SOURCE_SCHEMA_VERSION),
            "content_fingerprint": _fingerprint("source_information_content", source, schema=SOURCE_SCHEMA_VERSION),
            "context_fingerprint": _fingerprint("source_information_context", {
                "data_id": data_id, "proposal": proposal,
                "blocks": [blocks_by_id[ref] for ref in proposal["block_ids"]],
            }, schema=SOURCE_SCHEMA_VERSION),
        }
    loci = [_locus(block_id, blocks_by_id) for block_id in proposal["block_ids"]]
    loci.sort(key=_serialize)
    semantic = {key: proposal[key] for key in ("kind", "semantic_type", "content")}
    if proposal["kind"] == "image":
        semantic["image_sha256"] = _image_digests(blocks_by_id[proposal["image_block_id"]])
    return {
        "identity_fingerprint": _fingerprint("information_identity", {
            "data_id": data_id, "groundings": loci, "meaning": semantic,
        }),
        "content_fingerprint": _fingerprint("information_content", semantic),
        "context_fingerprint": _fingerprint("information_context", {
            "data_id": data_id, "proposal": proposal,
            "blocks": [blocks_by_id[block_id] for block_id in proposal["block_ids"]],
        }),
    }


def validate_decisions(decisions, count):
    """Require one explicit Validator result per zero-based proposal ordinal."""
    code = "invalid_validation"
    if type(count) is not int or count < 0 or not isinstance(decisions, list):
        _fail("Validator decisions and proposal count are invalid.", code)
    result = {}
    required = set(VALIDATOR_SCHEMA["properties"]["decisions"]["items"]["required"])
    for decision in decisions:
        if not isinstance(decision, dict) or set(decision) != required:
            _fail("Validator decision fields must exactly match the schema.", code)
        ordinal = decision["ordinal"]
        if type(ordinal) is not int or not 0 <= ordinal < count or ordinal in result:
            _fail("Validator ordinals must be unique and cover the proposal range.", code)
        if decision["verdict"] not in VERDICTS or not isinstance(decision["reason_codes"], list):
            _fail("Validator verdict or reason codes are invalid.", code)
        if any(not isinstance(value, str) or re.fullmatch(REASON_CODE_PATTERN, value) is None
               for value in decision["reason_codes"]):
            _fail("Reason codes must match [a-z][a-z0-9_]{0,63}; source prose is not a code.", code)
        result[ordinal] = {
            "ordinal": ordinal, "verdict": decision["verdict"],
            "reason_codes": list(decision["reason_codes"]),
            "reason": _text(decision["reason"], "reason", code),
        }
    if set(result) != set(range(count)):
        _fail("Validator decisions do not cover every proposal.", code)
    return result
