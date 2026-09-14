"""A reversible generated Markdown dossier, not a claim that raw code is Markdown.

The embedded manifest maps dossier offsets to immutable copies of source bytes.
No parser, model, database, or source-file mutation occurs here. The manifest is
published last; an interrupted output is incomplete and cannot verify.
"""

from bisect import bisect_right
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat


PROFILE = 'codebase-markdown-snapshot-v1'
ROOT_FILES = {'README.md', 'pyproject.toml', 'requirements.lock', 'Dockerfile', 'compose.yaml',
              '.gitignore', '.dockerignore', 'Palimpsest.cmd'}
TREES = ('src', 'tests/app', 'tools', 'desktop/test', 'deploy')
EXCLUDED_DIRS = {'output', '.local', 'node_modules', 'cache', '__pycache__', '.git', '.venv',
                 'build', 'dist', '.pytest_cache', '.mypy_cache', '.ruff_cache'}
BINARY_SUFFIXES = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.pdf', '.zip', '.gz', '.7z',
                   '.exe', '.dll', '.so', '.pyc', '.pyo', '.bin', '.pt', '.safetensors', '.woff', '.woff2'}
FOOTER = b'\n## Snapshot manifest\n\n```json\n'
ENDING = b'\n```\n'
INTRODUCTION = b'# Codebase source snapshot\n\nGenerated Markdown dossier containing exact source file bytes. Paths and offsets are recorded in the embedded manifest.\n\n'


def _fail(message):
    raise ValueError(message)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _path(value):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value or '\x00' in value
            or value.startswith('/') or any(part in ('', '.', '..') for part in value.split('/'))):
        _fail('invalid_snapshot_member_path')
    return PurePosixPath(value)


def _reparse(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def _checked(path, base=None):
    path = Path(os.path.abspath(path))
    if base is not None and not path.is_relative_to(base):
        _fail('snapshot_path_outside_root')
    for part in reversed([path, *path.parents]):
        try:
            if _reparse(part.lstat()):
                _fail('snapshot_reparse_point_forbidden')
        except FileNotFoundError:
            continue
    return path


def _signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _read_stable(path):
    path = _checked(path)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        _fail('snapshot_regular_file_required')
    with path.open('rb') as handle:
        opened = os.fstat(handle.fileno())
        raw = handle.read()
        after = os.fstat(handle.fileno())
    if _signature(before) != _signature(opened) or _signature(opened) != _signature(after) or _signature(after) != _signature(path.lstat()):
        _fail('snapshot_source_changed')
    return raw


def _secret(name):
    value = name.casefold()
    return (value == '.env' or value.startswith('.env.') or value.startswith(('credentials', 'secrets'))
            or value in ('id_rsa', 'id_ed25519', 'id_ecdsa', 'auth.json', 'token.json', 'tokens.json',
                         '.npmrc', '.pypirc', 'password', 'service-account.json')
            or value.endswith(('.pem', '.key', '.p12', '.pfx', '_password', '-password')))


def _line_count(text):
    breaks = list(re.finditer(r'\r\n|\r|\n', text))
    return max(1, len(breaks) + int(not breaks or breaks[-1].end() != len(text)))


def _framing(name, text):
    fence = '`' * max(3, 1 + max((len(match.group()) for match in re.finditer(r'`+', text)), default=0))
    return (('## File: ' + json.dumps(name, ensure_ascii=False) + '\n\n' + fence + '\n').encode('utf-8'),
            ('\n' + fence + '\n\n').encode('utf-8'))


def _select(root, paths):
    excluded, selected = [], []
    def consider(path):
        relative = path.relative_to(root).as_posix()
        _path(relative)
        if any(part in EXCLUDED_DIRS or _secret(part) for part in path.relative_to(root).parts):
            excluded.append({'path': relative, 'reason': 'excluded_generated_or_sensitive_name'})
            return
        _checked(path, root)
        if path.suffix.casefold() in BINARY_SUFFIXES:
            if paths is not None:
                _fail('explicit_snapshot_file_is_binary')
            excluded.append({'path': relative, 'reason': 'binary_file_type'})
        else:
            selected.append(relative)
    if paths is not None:
        if not isinstance(paths, (list, tuple)) or not paths:
            _fail('snapshot_paths_required')
        for name in paths:
            consider(root.joinpath(*_path(name).parts))
    else:
        for name in sorted(ROOT_FILES):
            if (root / name).exists():
                consider(root / name)
        if (root / 'desktop').exists():
            _checked(root / 'desktop', root)
            for path in sorted((root / 'desktop').iterdir()):
                if path.is_file() or path.is_symlink():
                    consider(path)
        for name in TREES:
            directory = _checked(root / name, root)
            if not directory.exists():
                continue
            for current, dirs, files in os.walk(directory, followlinks=False):
                for name in list(dirs):
                    path = Path(current) / name
                    if name in EXCLUDED_DIRS or _secret(name):
                        excluded.append({'path': path.relative_to(root).as_posix(), 'reason': 'excluded_generated_directory'})
                        dirs.remove(name)
                    else:
                        _checked(path, root)
                for name in files:
                    consider(Path(current) / name)
    if len(selected) != len(set(name.casefold() for name in selected)):
        _fail('snapshot_duplicate_or_case_colliding_paths')
    return sorted(selected), sorted(excluded, key=lambda row: row['path'])


def snapshot(root, output_dir, paths=None):
    root = _checked(root)
    if not root.is_dir():
        _fail('snapshot_root_required')
    output = _checked(output_dir, root)
    if output.exists():
        _fail('snapshot_output_exists')
    selected, excluded = _select(root, paths)
    initial_selection = (list(selected), list(excluded))
    chunks = [INTRODUCTION]
    size, characters = len(chunks[0]), len(chunks[0].decode())
    entries, originals = [], {}
    for name in selected:
        raw = _read_stable(root / name)
        try:
            text = raw.decode('utf-8')
            if '\x00' in text:
                raise UnicodeError('NUL')
        except UnicodeError:
            if paths is not None:
                _fail('explicit_snapshot_file_requires_utf8_without_nul')
            excluded.append({'path': name, 'reason': 'non_utf8_or_nul'})
            continue
        header, closing = _framing(name, text)
        chunks.append(header); size += len(header); characters += len(header.decode('utf-8'))
        entry = {'path': name, 'sha256': sha256(raw).hexdigest(), 'byte_size': len(raw),
            'character_count': len(text), 'line_count': _line_count(text), 'body_byte_start': size,
            'body_byte_end': size + len(raw), 'body_char_start': characters, 'body_char_end': characters + len(text)}
        entries.append(entry); originals[name] = raw; chunks.append(raw)
        chunks.append(closing); size += len(raw) + len(closing); characters += len(text) + len(closing)
    if not entries:
        _fail('snapshot_has_no_text_files')
    embedded = {'schema_version': PROFILE, 'representation': 'generated_markdown_dossier_not_original_repository_files',
        'selection': 'explicit_paths' if paths is not None else 'maintained_source_roots',
        'selection_policy': {'root_files': sorted(ROOT_FILES), 'trees': list(TREES),
            'desktop': 'own_top_level_files_and_test_tree', 'excluded_directory_names': sorted(EXCLUDED_DIRS),
            'explicit_paths': list(paths) if paths is not None else None},
        'files': entries, 'excluded': sorted(excluded, key=lambda row: row['path'])}
    dossier = b''.join([*chunks, FOOTER, _json(embedded), ENDING])
    result = {**embedded, 'dossier_sha256': sha256(dossier).hexdigest(), 'dossier_byte_size': len(dossier)}
    for name, raw in originals.items():
        if _read_stable(root / name) != raw:
            _fail('snapshot_source_changed')
    if _select(root, paths) != initial_selection:
        _fail('snapshot_source_changed')
    output.parent.mkdir(parents=True, exist_ok=True)
    _checked(output.parent, root)
    output.mkdir()  # Exclusive reservation: existing output is never overwritten.
    for name, raw in (('dossier.md', dossier), ('manifest.json', _json(result) + b'\n')):
        # Inherit the destination directory ACL. A Windows private temporary
        # directory's ACL survives a hard link and can block Docker bind reads.
        staged = output / ('.snapshot-' + os.urandom(16).hex())
        try:
            with staged.open('xb') as handle:
                handle.write(raw); handle.flush(); os.fsync(handle.fileno())
            os.link(staged, output / name)  # Atomic file publication, refusing existing targets.
        finally:
            staged.unlink(missing_ok=True)
    return verify(output)


def manifest_from_bytes(dossier, expected_sha256=None):
    """Validate a retained complete Data artifact without a filesystem sidecar."""
    if not isinstance(dossier, bytes):
        _fail('snapshot_bytes_required')
    marker = dossier.rfind(FOOTER)
    if marker < 0 or not dossier.endswith(ENDING) or not dossier.startswith(INTRODUCTION):
        _fail('snapshot_footer_missing')
    embedded = json.loads(dossier[marker + len(FOOTER):-len(ENDING)])
    if (not isinstance(embedded, dict) or embedded.get('schema_version') != PROFILE
            or embedded.get('representation') != 'generated_markdown_dossier_not_original_repository_files'
            or not isinstance(embedded.get('files'), list) or not embedded['files']
            or _json(embedded) != dossier[marker + len(FOOTER):-len(ENDING)]):
        _fail('snapshot_manifest_mismatch')
    actual = {**embedded, 'dossier_sha256': sha256(dossier).hexdigest(), 'dossier_byte_size': len(dossier)}
    if expected_sha256 is not None and actual['dossier_sha256'] != expected_sha256:
        _fail('snapshot_manifest_mismatch')
    text = dossier.decode('utf-8')
    seen, previous = set(), len(INTRODUCTION)
    for entry in actual['files']:
        if not isinstance(entry, dict) or not {'path', 'sha256', 'byte_size', 'character_count', 'line_count',
                'body_byte_start', 'body_byte_end', 'body_char_start', 'body_char_end'} <= entry.keys():
            _fail('snapshot_manifest_mismatch')
        path = _path(entry['path'])
        if path.as_posix().casefold() in seen:
            _fail('snapshot_duplicate_or_case_colliding_paths')
        seen.add(path.as_posix().casefold())
        start, end = entry['body_byte_start'], entry['body_byte_end']
        char_start, char_end = entry['body_char_start'], entry['body_char_end']
        if (any(type(value) is not int for value in (start, end, char_start, char_end))
                or not previous <= start <= end <= marker or not 0 <= char_start <= char_end <= len(text)):
            _fail('snapshot_member_range_mismatch')
        raw = dossier[start:end]; content = raw.decode('utf-8')
        if (len(raw) != entry['byte_size'] or sha256(raw).hexdigest() != entry['sha256'] or '\x00' in content
                or len(content) != entry['character_count'] or _line_count(content) != entry['line_count']
                or len(dossier[:start].decode('utf-8')) != char_start or text[char_start:char_end] != content):
            _fail('snapshot_member_content_mismatch')
        header, closing = _framing(entry['path'], content)
        if dossier[previous:start] != header or dossier[end:end + len(closing)] != closing:
            _fail('snapshot_member_header_mismatch')
        previous = end + len(closing)
    if previous != marker:
        _fail('snapshot_member_header_mismatch')
    return actual


def verify(directory, expected_sha256=None):
    directory = _checked(directory)
    actual = manifest_from_bytes(_read_stable(directory / 'dossier.md'), expected_sha256)
    if json.loads(_read_stable(directory / 'manifest.json')) != actual:
        _fail('snapshot_manifest_mismatch')
    return actual


def compare(before, after):
    """Compare captured paths and exact file hashes; never infer renames/deletions outside this scope."""
    first, second = manifest_from_bytes(before), manifest_from_bytes(after)
    old = {entry['path']: entry for entry in first['files']}
    new = {entry['path']: entry for entry in second['files']}
    shared = old.keys() & new.keys()
    changed = {name for name in shared if (old[name]['sha256'], old[name]['byte_size'])
               != (new[name]['sha256'], new[name]['byte_size'])}
    return {'before_data_id': first['dossier_sha256'], 'after_data_id': second['dossier_sha256'],
        'scope': 'captured_snapshot_members', 'added': sorted(new.keys() - old.keys()),
        'removed': sorted(old.keys() - new.keys()), 'changed': sorted(changed), 'unchanged': sorted(shared - changed)}


def locate(directory, *, byte_range=None, char_range=None):
    manifest = verify(directory)
    if (byte_range is None) == (char_range is None):
        _fail('snapshot_choose_one_coordinate_range')
    raw = _read_stable(Path(directory) / 'dossier.md')
    if sha256(raw).hexdigest() != manifest['dossier_sha256']:
        _fail('snapshot_source_changed')
    text = raw.decode('utf-8')
    interval = byte_range if byte_range is not None else char_range
    maximum = len(raw) if byte_range is not None else len(text)
    if (not isinstance(interval, (list, tuple)) or len(interval) != 2
            or any(type(value) is not int for value in interval) or not 0 <= interval[0] < interval[1] <= maximum):
        _fail('snapshot_invalid_range')
    matches, gaps, cursor = [], [], interval[0]
    for entry in manifest['files']:
        field = 'body_byte_' if byte_range is not None else 'body_char_'
        lo, hi = max(interval[0], entry[field + 'start']), min(interval[1], entry[field + 'end'])
        if lo >= hi:
            continue
        if cursor < lo:
            gaps.append([cursor, lo])
        content = raw[entry['body_byte_start']:entry['body_byte_end']]
        if byte_range is not None:
            a, b = lo - entry['body_byte_start'], hi - entry['body_byte_start']
            char_a, char_b = len(content[:a].decode('utf-8')), len(content[:b].decode('utf-8'))
        else:
            char_a, char_b = lo - entry['body_char_start'], hi - entry['body_char_start']
            original = content.decode('utf-8')
            a, b = len(original[:char_a].encode('utf-8')), len(original[:char_b].encode('utf-8'))
        original = content.decode('utf-8')
        line_ends = [match.end() for match in re.finditer(r'\r\n|\r|\n', original)]
        line_a = bisect_right(line_ends, char_a) + 1
        line_b = bisect_right(line_ends, max(char_a, char_b - 1)) + 1
        matches.append({'path': entry['path'], 'sha256': entry['sha256'], 'dossier_range': [lo, hi],
            'source_byte_range': [a, b], 'source_char_range': [char_a, char_b], 'line_range': [line_a, line_b]})
        cursor = hi
    if cursor < interval[1]:
        gaps.append([cursor, interval[1]])
    return {'coordinate': 'bytes' if byte_range is not None else 'unicode_codepoints', 'matches': matches,
            'unmapped_ranges': gaps, 'dossier_sha256': manifest['dossier_sha256']}


def storage_segments(manifest):
    """Share file bodies and retain every wrapper byte; no source/I regrouping."""
    if manifest.get('schema_version') != PROFILE:
        _fail('snapshot_manifest_mismatch')
    boundaries = {0, manifest['dossier_byte_size']}
    for entry in manifest['files']:
        boundaries.update((entry['body_byte_start'], entry['body_byte_end']))
    positions = sorted(boundaries)
    from .segmented_artifact_store import validate_segments
    return [list(span) for span in validate_segments(list(zip(positions, positions[1:])), manifest['dossier_byte_size'])]


def restore(directory, target_dir):
    manifest = verify(directory)
    raw = _read_stable(Path(directory) / 'dossier.md')
    if sha256(raw).hexdigest() != manifest['dossier_sha256']:
        _fail('snapshot_source_changed')
    return _restore(raw, manifest, target_dir)


def restore_bytes(dossier, target_dir, expected_sha256=None):
    """Restore exact source files directly from ArtifactStore.read output."""
    return _restore(dossier, manifest_from_bytes(dossier, expected_sha256), target_dir)


def _restore(raw, manifest, target_dir):
    target = _checked(target_dir)
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        _fail('snapshot_restore_requires_empty_directory')
    for entry in manifest['files']:
        _checked(target.joinpath(*_path(entry['path']).parts), target)
    target.mkdir(parents=True, exist_ok=True)
    restored = []
    for entry in manifest['files']:
        destination = _checked(target.joinpath(*_path(entry['path']).parts), target)
        destination.parent.mkdir(parents=True, exist_ok=True)
        _checked(destination.parent, target)
        with destination.open('xb') as handle:
            handle.write(raw[entry['body_byte_start']:entry['body_byte_end']])
        if sha256(_read_stable(destination)).hexdigest() != entry['sha256']:
            _fail('snapshot_restoration_mismatch')
        restored.append(entry['path'])
    return {'files': restored, 'count': len(restored), 'dossier_sha256': manifest['dossier_sha256']}
