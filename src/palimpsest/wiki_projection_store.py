"""Linux file cache for read-only Wiki projections, never canonical storage."""

from contextlib import contextmanager
import json
import os
from pathlib import Path

from .artifact_store import ArtifactStore, _absolute, _directory, _file, _read_payload, fcntl
from .errors import PalimpsestError


_MARKER = ".paper-wiki.json"
_PROFILE = {"schema_version": "paper-wiki-projection-store-v1",
            "purpose": "read-only-wiki-export-cache", "canonical": False}
# A technical lock namespace, not an identity assigned to a canonical entity.
_LOCK_KEY = "019a5c1b-7f00-7000-8000-000000000005"


def _json_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _read(parent: int, name: str) -> bytes:
    chunks = []
    with _file(parent, name) as descriptor:
        _read_payload(descriptor, parent, name, chunks=chunks,
                      changed_code="wiki_projection_conflict")
    return b"".join(chunks)


def _write(parent: int, name: str, content: bytes, *, replace: bool = False):
    temporary = ".wiki-write-" + os.urandom(16).hex()
    try:
        with _file(parent, temporary, os.O_RDWR | os.O_CREAT | os.O_EXCL) as descriptor:
            remaining = memoryview(content)
            while remaining:
                written = os.write(descriptor, remaining)
                if not written:
                    raise OSError("Wiki projection write made no progress")
                remaining = remaining[written:]
            os.fsync(descriptor)
            saved = _read_payload(descriptor, parent, temporary)
        if replace:
            try:
                with _file(parent, name):
                    pass
            except FileNotFoundError:
                pass
            os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
        else:
            try:
                os.link(temporary, name, src_dir_fd=parent, dst_dir_fd=parent,
                        follow_symlinks=False)
            except FileExistsError:
                pass
            with _file(parent, name) as existing:
                if _read_payload(existing, parent, name) != saved:
                    raise PalimpsestError("wiki_projection_conflict",
                                          "같은 Wiki 출력 경로에 다른 내용이 있습니다.", 6)
        os.fsync(parent)
    finally:
        try:
            os.unlink(temporary, dir_fd=parent)
            os.fsync(parent)
        except FileNotFoundError:
            pass


class ProjectionStore:
    def __init__(self, root: Path):
        self._store = ArtifactStore(root)
        self.root = _absolute(root)
        with self._store._io_errors(), _directory(self.root, create=True) as directory:
            # Directory locking creates no file in a possibly unmanaged root.
            fcntl.flock(directory, fcntl.LOCK_EX)
            try:
                try:
                    marker = _read(directory, _MARKER)
                except FileNotFoundError:
                    if os.listdir(directory):
                        raise PalimpsestError("wiki_projection_unmanaged_root",
                                              "비어 있지 않은 미관리 폴더는 Wiki 출력에 사용할 수 없습니다.")
                    _write(directory, _MARKER, _json_bytes(_PROFILE))
                else:
                    if marker != _json_bytes(_PROFILE):
                        raise PalimpsestError("wiki_projection_unmanaged_root",
                                              "Wiki 출력 폴더의 관리 profile이 다릅니다.")
            finally:
                fcntl.flock(directory, fcntl.LOCK_UN)

    def _path(self, relative) -> Path:
        raw = os.fspath(relative)
        path = Path(raw)
        if (not raw or path.is_absolute() or not path.parts or ".." in path.parts
                or "\\" in raw or ":" in raw
                or path.parts[0] in {_MARKER, "locks"}
                or any(part.startswith(".wiki-write-") for part in path.parts)):
            raise PalimpsestError("unsafe_path", "관리 폴더 안의 상대 파일 경로가 필요합니다.")
        return self.root / path

    @contextmanager
    def locked(self):
        # ponytail: one cache-wide lock; split only if short metadata writes contend.
        with self._store.request_lock(_LOCK_KEY):
            yield

    def read_bytes(self, relative) -> bytes:
        path = self._path(relative)
        with self._store._io_errors():
            try:
                with _directory(path.parent) as parent:
                    return _read(parent, path.name)
            except FileNotFoundError:
                raise PalimpsestError("wiki_projection_missing", "Wiki 출력 파일이 없습니다.") from None

    def read_json(self, relative, default=None):
        try:
            content = self.read_bytes(relative)
        except PalimpsestError as error:
            if error.code == "wiki_projection_missing":
                return default
            raise
        try:
            return json.loads(content)
        except (UnicodeDecodeError, ValueError):
            raise PalimpsestError("wiki_projection_conflict", "Wiki 출력 JSON이 손상됐습니다.") from None

    def write_bytes(self, relative, content: bytes):
        path = self._path(relative)
        with self._store._io_errors(), _directory(path.parent, create=True) as parent:
            _write(parent, path.name, content)

    def write_json(self, relative, value):
        self.write_bytes(relative, _json_bytes(value))

    def replace_json(self, relative, value):
        path = self._path(relative)
        content = _json_bytes(value)
        with self._store._io_errors(), _directory(path.parent, create=True) as parent:
            _write(parent, path.name, content, replace=True)
