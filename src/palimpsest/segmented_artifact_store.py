"""Physical sharing of exact raw bytes; manifests never impersonate raw objects.

Only hash-addressed immutable blobs are shared. No semantic deduplication,
compression, delta dependencies, deletion or garbage collection is performed.
"""

import hashlib
import json
import os
import stat

from .artifact_store import _CHUNK_SIZE, _directory, _file, _read_payload, _stamp
from .data import Payload, data_id as validate_data_id
from .errors import PalimpsestError


PROFILE = 'segmented-artifact-v1'


def _fail(code='integrity_conflict'):
    raise PalimpsestError(code, '분할 원본의 범위·manifest·공유 blob 무결성을 확인하세요.')


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _digest(value):
    return hashlib.sha256(_json(value)).hexdigest()


def validate_segments(segments, byte_size):
    if type(byte_size) is not int or byte_size < 0 or not isinstance(segments, (list, tuple)):
        _fail('invalid_artifact_segments')
    position, result = 0, []
    for span in segments:
        if (not isinstance(span, (list, tuple)) or len(span) != 2
                or any(type(n) is not int for n in span) or span[0] != position
                or not position < span[1] <= byte_size):
            _fail('invalid_artifact_segments')
        position = span[1]
        result.append(tuple(span))
    if position != byte_size:
        _fail('invalid_artifact_segments')
    return result


def _manifest(root, identifier, byte_size):
    name = identifier + '.json'
    pieces = []
    try:
        with _directory(root / 'manifests' / 'sha256' / identifier[:2]) as directory:
            with _file(directory, name) as descriptor:
                _read_payload(descriptor, directory, name, chunks=pieces, allow_link_changes=True)
    except FileNotFoundError:
        return None
    raw = b''.join(pieces)
    try:
        value = json.loads(raw)
        if (not isinstance(value, dict) or set(value) != {'schema_version', 'raw_data_id', 'raw_byte_size', 'chunks', 'manifest_sha256'}
                or value['schema_version'] != PROFILE or value['raw_data_id'] != identifier
                or type(value['raw_byte_size']) is not int or value['raw_byte_size'] != byte_size
                or not isinstance(value['chunks'], list) or _json(value) != raw
                or value['manifest_sha256'] != _digest({key: item for key, item in value.items() if key != 'manifest_sha256'})):
            _fail()
        total = 0
        for chunk in value['chunks']:
            if not isinstance(chunk, dict) or set(chunk) != {'sha256', 'byte_size'} or type(chunk['byte_size']) is not int or chunk['byte_size'] <= 0:
                _fail()
            validate_data_id(chunk['sha256'])
            total += chunk['byte_size']
        if total != byte_size:
            _fail()
    except (ValueError, TypeError, UnicodeError, KeyError, PalimpsestError):
        _fail()
    return value, len(raw)


def read(root, identifier, byte_size, *, chunks=None):
    """Return None only when no descriptor exists; damaged dependencies must fail."""
    loaded = _manifest(root, identifier, byte_size)
    if loaded is None:
        return None
    manifest, manifest_size = loaded
    aggregate = hashlib.sha256()
    sizes = {}
    for chunk in manifest['chunks']:
        sha, size = chunk['sha256'], chunk['byte_size']
        if sha in sizes and sizes[sha] != size:
            _fail()
        sizes[sha] = size
        try:
            with _directory(root / 'blobs' / 'sha256' / sha[:2]) as directory:
                with _file(directory, sha) as descriptor:
                    saved = _read_payload(descriptor, directory, sha, chunks=chunks,
                                          aggregate_hash=aggregate, allow_link_changes=True)
        except FileNotFoundError:
            _fail('artifact_missing')
        if saved != Payload(data_id=sha, byte_size=size):
            _fail()
    if aggregate.hexdigest() != identifier:
        _fail()
    return {'storage': 'segmented-v1', 'logical_bytes': byte_size, 'manifest_bytes': manifest_size,
        'manifest_sha256': manifest['manifest_sha256'], 'chunk_count': len(manifest['chunks']),
        'unique_blob_count': len(sizes), 'unique_blob_bytes': sum(sizes.values())}


def _remove_partial(staging, name):
    try:
        entry = os.stat(name, dir_fd=staging, follow_symlinks=False)
    except FileNotFoundError:
        return
    if not stat.S_ISREG(entry.st_mode):
        _fail('unsafe_path')
    os.unlink(name, dir_fd=staging)
    os.fsync(staging)


def _write(descriptor, content):
    remaining = memoryview(content)
    while remaining:
        written = os.write(descriptor, remaining)
        if not written:
            raise OSError('File write made no progress')
        remaining = remaining[written:]


def _publish_blob(root, staging, source, start, end, aggregate):
    name = 'segment.partial'
    _remove_partial(staging, name)
    checksum = hashlib.sha256()
    with _file(staging, name, os.O_WRONLY | os.O_CREAT | os.O_EXCL) as target:
        os.lseek(source, start, os.SEEK_SET)
        remaining = end - start
        while remaining:
            data = os.read(source, min(remaining, _CHUNK_SIZE))
            if not data:
                _fail()
            checksum.update(data); aggregate.update(data); _write(target, data); remaining -= len(data)
        os.fchmod(target, 0o400); os.fsync(target)
    sha, size, created = checksum.hexdigest(), end - start, False
    with _directory(root / 'blobs' / 'sha256' / sha[:2], create=True) as blobs:
        try:
            os.link(name, sha, src_dir_fd=staging, dst_dir_fd=blobs, follow_symlinks=False)
            created = True
        except FileExistsError:
            pass
        with _file(blobs, sha) as descriptor:
            if _read_payload(descriptor, blobs, sha, allow_link_changes=True) != Payload(data_id=sha, byte_size=size):
                _fail()
            os.fsync(descriptor)
        os.fsync(blobs)
    _remove_partial(staging, name)
    return {'sha256': sha, 'byte_size': size}, created


def publish(store, request_id, identifier, byte_size, segments):
    request_id = store._require_lock(request_id)
    identifier = validate_data_id(identifier)
    spans = validate_segments(segments, byte_size)
    relative = f'objects/sha256/{identifier[:2]}/{identifier}'
    with store._io_errors(), _directory(store.root / 'staging' / request_id) as staging:
        with _file(staging, 'payload') as source:
            expected = Payload(data_id=identifier, byte_size=byte_size)
            if _read_payload(source, staging, 'payload') != expected:
                _fail()
            existing = store._read_verified(identifier, byte_size, allow_missing=True)
            if existing is not None:
                return {**existing, 'artifact_path': relative, 'new_blob_count': 0, 'new_blob_bytes': 0}
            before = _stamp(os.fstat(source))
            chunks, created, aggregate = [], [], hashlib.sha256()
            for start, end in spans:
                chunk, new = _publish_blob(store.root, staging, source, start, end, aggregate)
                chunks.append(chunk)
                if new:
                    created.append(chunk)
            if (aggregate.hexdigest() != identifier or before != _stamp(os.fstat(source))
                    or before != _stamp(os.stat('payload', dir_fd=staging, follow_symlinks=False))):
                _fail()
            manifest = {'schema_version': PROFILE, 'raw_data_id': identifier, 'raw_byte_size': byte_size, 'chunks': chunks}
            manifest['manifest_sha256'] = _digest(manifest)
            temporary = 'segments.partial'
            _remove_partial(staging, temporary)
            with _file(staging, temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL) as target:
                _write(target, _json(manifest)); os.fchmod(target, 0o400); os.fsync(target)
            name = identifier + '.json'
            with _directory(store.root / 'manifests' / 'sha256' / identifier[:2], create=True) as manifests:
                try:
                    os.link(temporary, name, src_dir_fd=staging, dst_dir_fd=manifests, follow_symlinks=False)
                except FileExistsError:
                    pass
                os.fsync(manifests)
            # A parallel writer may have chosen another valid partition of the
            # same Data. Verify its published bytes; never overwrite its layout.
            stats = store._read_verified(identifier, byte_size)
            _remove_partial(staging, temporary)
    return {**stats, 'artifact_path': relative, 'new_blob_count': len(created),
            'new_blob_bytes': sum(chunk['byte_size'] for chunk in created)}
