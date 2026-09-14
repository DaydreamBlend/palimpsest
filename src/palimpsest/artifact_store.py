"""Durable, request-scoped file registration for the Linux Docker runtime."""

from contextlib import contextmanager
import errno
import hashlib
import os
from pathlib import Path
import stat
import sys
import threading

try:
    import fcntl
except ImportError:  # Import remains possible for an explicit platform diagnostic.
    fcntl = None

from .data import Payload, data_id as _data_id, request_id as _request_id
from .errors import PalimpsestError


_CHUNK_SIZE = 1024 * 1024


def _absolute(path: Path) -> Path:
    path = Path(path)
    if ".." in path.parts:
        raise PalimpsestError("unsafe_path", "상위 경로 이동은 허용하지 않습니다.")
    return Path(os.path.abspath(path))


def _stamp(value: os.stat_result) -> tuple:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _directory_child(parent: int, name: str, create: bool) -> int:
    if create:
        try:
            os.mkdir(name, 0o700, dir_fd=parent)
            os.fsync(parent)
        except FileExistsError:
            pass
    try:
        return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            raise PalimpsestError("unsafe_path", "경로에 링크 또는 디렉터리가 아닌 항목이 있습니다.") from None
        raise


@contextmanager
def _directory(path: Path, create: bool = False):
    """Walk from / using no-follow directory descriptors, including ancestors."""
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = _directory_child(descriptor, part, create)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


@contextmanager
def _file(parent: int, name: str, flags: int = os.O_RDONLY, mode: int = 0o600):
    try:
        descriptor = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, mode, dir_fd=parent)
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise PalimpsestError("unsafe_path", "심볼릭 링크는 허용하지 않습니다.") from None
        raise
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise PalimpsestError("unsafe_path", "일반 파일만 허용합니다.")
        yield descriptor
    finally:
        os.close(descriptor)


def _read_payload(descriptor: int, parent: int, name: str, *, output: int | None = None,
                  changed_code: str = "integrity_conflict", chunks: list[bytes] | None = None,
                  aggregate_hash=None, allow_link_changes: bool = False) -> Payload:
    before = os.fstat(descriptor)
    digest = hashlib.sha256()
    byte_size = 0
    os.lseek(descriptor, 0, os.SEEK_SET)
    while chunk := os.read(descriptor, _CHUNK_SIZE):
        digest.update(chunk)
        if aggregate_hash is not None:
            aggregate_hash.update(chunk)
        byte_size += len(chunk)
        if chunks is not None:
            chunks.append(chunk)
        if output is not None:
            remaining = memoryview(chunk)
            while remaining:
                written = os.write(output, remaining)
                if not written:
                    raise OSError(errno.EIO, "File write made no progress")
                remaining = remaining[written:]
    after = os.fstat(descriptor)
    try:
        named = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        raise PalimpsestError(changed_code, "읽는 동안 파일이 변경됐습니다.") from None
    stamps = [_stamp(value) for value in (before, after, named)]
    if allow_link_changes and len({value.st_nlink for value in (before, after, named)}) > 1:
        # A CAS publisher may remove its temporary hardlink while another reader
        # verifies the shared inode. Keep identity/size/mtime and full-byte hashes.
        stamps = [value[:-1] for value in stamps]
    if (stamps[0] != stamps[1] or stamps[1] != stamps[2]
            or byte_size != after.st_size or not stat.S_ISREG(named.st_mode)):
        raise PalimpsestError(changed_code, "읽는 동안 파일이 변경됐습니다.")
    return Payload(data_id=digest.hexdigest(), byte_size=byte_size)


class ArtifactStore:
    def __init__(self, root: Path):
        if sys.platform != "linux" or fcntl is None:
            raise PalimpsestError("unsupported_platform", "Artifact Store는 Linux Docker 환경에서 실행해야 합니다.")
        self.root = _absolute(root)
        self._locked: dict[str, int] = {}

    @contextmanager
    def _io_errors(self):
        try:
            yield
        except OSError as error:
            raise PalimpsestError("storage_error", "Artifact Store 파일 입출력에 실패했습니다.",
                                  details={"errno": error.errno}) from error

    def _require_lock(self, request_id: str) -> str:
        request_id = _request_id(request_id)
        if self._locked.get(request_id) != threading.get_ident():
            raise PalimpsestError("request_lock_required", "staging 접근 전에 해당 요청의 잠금이 필요합니다.")
        return request_id

    @contextmanager
    def request_lock(self, request_id: str):
        request_id = _request_id(request_id)
        if self._locked.get(request_id) == threading.get_ident():
            raise PalimpsestError("request_lock_required", "같은 요청의 잠금을 중첩할 수 없습니다.")
        with self._io_errors(), _directory(self.root / "locks", create=True) as directory:
            # Lock files persist: unlinking them would let waiters lock different inodes.
            with _file(directory, request_id + ".lock", os.O_RDWR | os.O_CREAT) as descriptor:
                os.fsync(directory)
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                self._locked[request_id] = threading.get_ident()
                try:
                    yield
                finally:
                    self._locked.pop(request_id, None)
                    fcntl.flock(descriptor, fcntl.LOCK_UN)

    def stage(self, source: Path, request_id: str) -> Payload:
        request_id = self._require_lock(request_id)
        source = _absolute(source)
        if source.is_relative_to(self.root):
            raise PalimpsestError("unsafe_path", "관리 Artifact Store 외부의 원본 파일을 제공해 주세요.")
        with self._io_errors(), _directory(source.parent) as source_parent:
            with _file(source_parent, source.name) as source_file:
                with _directory(self.root / "staging" / request_id, create=True) as staging:
                    try:
                        with _file(staging, "payload") as existing:
                            saved = _read_payload(existing, staging, "payload")
                    except FileNotFoundError:
                        saved = None
                    if saved is not None:
                        incoming = _read_payload(source_file, source_parent, source.name,
                                                 changed_code="source_changed")
                        if incoming != saved:
                            raise PalimpsestError("idempotency_conflict", "이 요청에는 이미 다른 내용의 파일이 준비되어 있습니다.", 6)
                        return saved
                    # Only this request's interrupted, unpublished copy may be removed.
                    try:
                        partial = os.stat("payload.partial", dir_fd=staging, follow_symlinks=False)
                    except FileNotFoundError:
                        partial = None
                    if partial is not None:
                        if not stat.S_ISREG(partial.st_mode):
                            raise PalimpsestError("unsafe_path", "미완성 staging 항목이 일반 파일이 아닙니다.")
                        os.unlink("payload.partial", dir_fd=staging)
                        os.fsync(staging)
                    with _file(staging, "payload.partial", os.O_WRONLY | os.O_CREAT | os.O_EXCL) as target:
                        payload = _read_payload(source_file, source_parent, source.name,
                                                output=target, changed_code="source_changed")
                        os.fchmod(target, 0o400)
                        os.fsync(target)
                    # Link publishes a complete staging payload without overwriting one.
                    os.link("payload.partial", "payload", src_dir_fd=staging,
                            dst_dir_fd=staging, follow_symlinks=False)
                    os.fsync(staging)
                    os.unlink("payload.partial", dir_fd=staging)
                    os.fsync(staging)
                    return payload

    def staged(self, request_id: str) -> Payload:
        request_id = self._require_lock(request_id)
        with self._io_errors():
            try:
                with _directory(self.root / "staging" / request_id) as staging:
                    with _file(staging, "payload") as descriptor:
                        return _read_payload(descriptor, staging, "payload")
            except FileNotFoundError:
                raise PalimpsestError("staging_missing", "이 요청의 완성된 staging 파일이 없습니다.") from None

    def publish(self, request_id: str, data_id: str, byte_size: int, *, segments=None) -> str:
        if segments is not None:
            return self.publish_segments(request_id, data_id, byte_size, segments)['artifact_path']
        request_id = self._require_lock(request_id)
        data_id = _data_id(data_id)
        relative = f"objects/sha256/{data_id[:2]}/{data_id}"
        with self._io_errors(), _directory(self.root / "staging" / request_id) as staging:
            with _file(staging, "payload") as source:
                staged = _read_payload(source, staging, "payload")
                if staged != Payload(data_id=data_id, byte_size=byte_size):
                    raise PalimpsestError("integrity_conflict", "staging 파일이 준비된 요청의 hash·크기와 일치하지 않습니다.")
                if self._read_verified(data_id, byte_size, allow_missing=True) is not None:
                    return relative
                with _directory(self.root / "objects" / "sha256" / data_id[:2], create=True) as objects:
                    try:
                        os.link("payload", data_id, src_dir_fd=staging,
                                dst_dir_fd=objects, follow_symlinks=False)
                    except FileExistsError:
                        pass
                    with _file(objects, data_id) as published:
                        saved = _read_payload(published, objects, data_id)
                        if saved != staged:
                            raise PalimpsestError("integrity_conflict", "공유 원본 파일이 Data ID·크기와 일치하지 않습니다.")
                        os.fsync(published)
                    os.fsync(objects)
        return relative

    def publish_segments(self, request_id: str, data_id: str, byte_size: int, segments) -> dict:
        """Publish exact staged bytes as shared blobs, keeping the raw Data identity."""
        from .segmented_artifact_store import publish
        return publish(self, request_id, data_id, byte_size, segments)

    def _read_verified(self, data_id, byte_size, *, chunks=None, allow_missing=False):
        from .segmented_artifact_store import read as read_segmented
        data_id = _data_id(data_id)
        if type(byte_size) is not int or byte_size < 0:
            raise PalimpsestError('integrity_conflict', '등록된 파일 크기를 확인하세요.')
        with self._io_errors():
            payload = None
            try:
                with _directory(self.root / 'objects' / 'sha256' / data_id[:2]) as objects:
                    with _file(objects, data_id) as descriptor:
                        payload = _read_payload(descriptor, objects, data_id, chunks=chunks)
            except FileNotFoundError:
                pass
            if payload is not None and payload != Payload(data_id=data_id, byte_size=byte_size):
                raise PalimpsestError('integrity_conflict', '등록된 원본 파일의 hash·크기가 일치하지 않습니다.')
            segmented = read_segmented(self.root, data_id, byte_size, chunks=chunks if payload is None else None)
            if payload is None:
                if segmented is None and not allow_missing:
                    raise PalimpsestError('artifact_missing', '등록된 원본 파일이 없습니다.')
                return segmented
            result = {'storage': 'raw', 'logical_bytes': byte_size, 'raw_bytes': byte_size,
                      'manifest_bytes': 0, 'chunk_count': 0, 'unique_blob_count': 0, 'unique_blob_bytes': 0}
            if segmented is not None:
                result.update(segmented, storage='raw+segmented-v1', raw_bytes=byte_size)
            return result

    def storage_stats(self, data_id: str, byte_size: int) -> dict:
        """Verified physical references, separate from canonical Data metadata."""
        return self._read_verified(data_id, byte_size)

    def verify(self, data_id: str, byte_size: int) -> dict:
        data_id = _data_id(data_id)
        relative = f"objects/sha256/{data_id[:2]}/{data_id}"
        self._read_verified(data_id, byte_size)
        return {"data_id": data_id, "byte_size": byte_size, "artifact_path": relative, "verified": True}

    def read(self, data_id: str, byte_size: int) -> bytes:
        """Return exactly the bytes verified through a single no-follow file read."""
        chunks: list[bytes] = []
        self._read_verified(data_id, byte_size, chunks=chunks)
        return b"".join(chunks)

    def cleanup(self, request_id: str) -> None:
        request_id = self._require_lock(request_id)
        with self._io_errors():
            try:
                with _directory(self.root / "staging") as parent:
                    try:
                        staging = _directory_child(parent, request_id, create=False)
                    except FileNotFoundError:
                        return
                    try:
                        for name in ("payload.partial", "payload", "segment.partial", "segments.partial"):
                            try:
                                entry = os.stat(name, dir_fd=staging, follow_symlinks=False)
                            except FileNotFoundError:
                                continue
                            if not stat.S_ISREG(entry.st_mode):
                                raise PalimpsestError("unsafe_path", "staging 정리 중 일반 파일이 아닌 항목을 발견했습니다.")
                            os.unlink(name, dir_fd=staging)
                        os.fsync(staging)
                    finally:
                        os.close(staging)
                    os.rmdir(request_id, dir_fd=parent)
                    os.fsync(parent)
            except FileNotFoundError:
                return

    def doctor(self) -> dict:
        """Inspect configuration without creating files or changing permissions."""
        result = {"root": str(self.root), "platform": sys.platform, "exists": False, "ready": False}

        def check_access(descriptor: int, root: bool = False):
            access = {
                "writable": os.access(".", os.W_OK, dir_fd=descriptor, effective_ids=True),
                "searchable": os.access(".", os.X_OK, dir_fd=descriptor, effective_ids=True),
                "read_only_filesystem": bool(os.fstatvfs(descriptor).f_flag & os.ST_RDONLY),
            }
            if root:
                result.update(access)
            if access["read_only_filesystem"]:
                raise PalimpsestError("storage_read_only", "Artifact Store 파일시스템이 읽기 전용입니다.")
            if not access["writable"] or not access["searchable"]:
                raise PalimpsestError("storage_permission_denied", "Artifact Store에 쓰기·탐색 권한이 필요합니다.")

        try:
            with self._io_errors(), _directory(self.root) as directory:
                result.update(exists=True, device=os.fstat(directory).st_dev)
                check_access(directory, root=True)
                for name in ("locks", "staging", "objects", "blobs", "manifests"):
                    try:
                        child = _directory_child(directory, name, create=False)
                    except FileNotFoundError:
                        continue
                    try:
                        check_access(child)
                    finally:
                        os.close(child)
                result["ready"] = True
        except PalimpsestError as error:
            result.update(ready=False, error_code=error.code)
        return result
