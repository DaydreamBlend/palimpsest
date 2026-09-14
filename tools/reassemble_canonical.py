#!/usr/bin/env python3
"""Reassemble current canonical text, or --baseline for the archived source; no app code is run."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys


def reassemble(root: Path, baseline: bool = False) -> bytes:
    map_path = 'docs/source/source_map.json' if baseline else 'docs/canonical/current_map.json'
    manifest = json.loads((root / map_path).read_text(encoding='utf-8'))
    parts = []
    cursor = 1
    for p in manifest['parts']:
        if p['start_line'] != cursor:
            raise ValueError('Source parts have a gap or overlap')
        data = (root / p['path']).read_bytes()
        if hashlib.sha256(data).hexdigest() != p['sha256']:
            raise ValueError(f"Part changed: {p['path']}")
        parts.append(data)
        cursor = p['end_line'] + 1
    data = b''.join(parts)
    if hashlib.sha256(data).hexdigest() != manifest['source_sha256']:
        raise ValueError('Reassembled source hash mismatch')
    if data != (root / manifest['source_path']).read_bytes():
        raise ValueError('Reassembled bytes differ from archived source')
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', action='store_true', help='Reassemble the pre-change archived source')
    args = parser.parse_args()
    try:
        data = reassemble(args.root.resolve(), baseline=args.baseline)
        out = args.output.resolve()
        if out.exists():
            raise FileExistsError(f'Refusing to overwrite: {out}')
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open('xb') as stream:
            stream.write(data)
        print(f'Wrote {len(data)} bytes; sha256={hashlib.sha256(data).hexdigest()}')
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
