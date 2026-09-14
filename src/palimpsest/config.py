"""Explicit local configuration; secret values never appear in object reprs."""

from dataclasses import dataclass, field
import os
from pathlib import Path

from .errors import PalimpsestError


def select_database(dsn: str, database_name: str | None = None) -> str:
    """Select a named database without exposing or copying its credential file."""
    if database_name is None:
        return dsn
    if (not isinstance(database_name, str) or not database_name.strip()
            or len(database_name.encode('utf-8')) > 63 or any(ord(c) < 32 for c in database_name)):
        raise PalimpsestError('invalid_database_name', '명시할 데이터베이스 이름을 확인하세요.', 2)
    from psycopg.conninfo import make_conninfo
    from psycopg import ProgrammingError
    try:
        return make_conninfo(dsn, dbname=database_name)
    except ProgrammingError:
        raise PalimpsestError('invalid_configuration', '데이터베이스 연결 설정을 확인하세요.', 2) from None


def load_dsn(name: str = "PALIMPSEST_DATABASE_DSN") -> str:
    direct, file_name = os.environ.get(name), os.environ.get(name + "_FILE")
    if direct is not None and file_name is not None:
        raise PalimpsestError("ambiguous_configuration", "DSN과 DSN_FILE 중 하나만 설정하세요.", 2)
    if direct is None and file_name is None:
        code = "admin_database_not_configured" if name == "PALIMPSEST_ADMIN_DSN" else "database_not_configured"
        raise PalimpsestError(code, "데이터베이스 연결 설정이 필요합니다.", 2)
    if file_name is not None:
        try:
            # Read only the explicitly configured secret file, with a bounded size.
            with Path(file_name).open("r", encoding="utf-8") as secret_file:
                direct = secret_file.read(16385)
        except (OSError, UnicodeError, ValueError):
            raise PalimpsestError("secret_file_unreadable", "DSN secret 파일을 읽을 수 없습니다.", 2) from None
    if not direct or not direct.strip() or len(direct) > 16384 or "\x00" in direct:
        raise PalimpsestError("invalid_configuration", "DSN 설정이 비어 있거나 유효하지 않습니다.", 2)
    return direct.strip()


@dataclass(frozen=True)
class Config:
    database_dsn: str = field(repr=False)
    artifact_root: Path
    actor_ref: str


def load_config() -> Config:
    dsn = load_dsn()
    artifact_root = os.environ.get("PALIMPSEST_ARTIFACT_ROOT", "/var/lib/palimpsest/artifacts")
    actor = os.environ.get("PALIMPSEST_ACTOR", "local")
    if not artifact_root.strip() or "\x00" in artifact_root or not actor.strip() or "\x00" in actor:
        raise PalimpsestError("invalid_configuration", "Artifact Store 또는 actor 설정을 확인하세요.", 2)
    return Config(dsn, Path(artifact_root), actor)
