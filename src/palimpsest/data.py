"""Data identity and command values; no database, CLI, or parser imports."""

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from uuid import UUID, RFC_4122

from .errors import PalimpsestError


@dataclass(frozen=True)
class Payload:
    data_id: str
    byte_size: int


def data_id(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise PalimpsestError("invalid_data_id", "Data ID는 소문자 SHA-256 64자리여야 합니다.", 2)
    return value


def request_id(value: str) -> str:
    try:
        parsed = UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise PalimpsestError("invalid_request_id", "요청 ID는 UUIDv7이어야 합니다.", 2) from None
    if parsed.version != 7 or parsed.variant != RFC_4122:
        raise PalimpsestError("invalid_request_id", "요청 ID는 UUIDv7이어야 합니다.", 2)
    return str(parsed)


def fingerprint(payload: Payload, metadata: dict) -> str:
    envelope = {"command": "data.import", "version": 1,
                "payload_sha256": payload.data_id, "byte_size": payload.byte_size,
                "metadata": metadata}
    return sha256(json.dumps(envelope, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
