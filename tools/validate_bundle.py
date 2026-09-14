#!/usr/bin/env python3
"""Validate bundle integrity and approved U01-U11 policy, not the application. Stdlib only."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote
from policy_checks import validate_release_policy

EXCLUDED_DIRS = frozenset({'.git', '.local', '.venv', 'node_modules', '__pycache__', 'tmp', 'output', 'build', 'dist'})


def markdown_files(root: Path):
    """Check authored project docs, not dependency docs or generated source outputs."""
    for directory, children, names in os.walk(root, followlinks=False):
        children[:] = [name for name in children if name not in EXCLUDED_DIRS
                       and not (Path(directory) / name).is_symlink()
                       and not (Path(directory) / name).is_junction()]
        for name in names:
            path = Path(directory) / name
            if path.suffix.lower() == '.md' and not path.is_symlink():
                yield path


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def outside_fences(text: str) -> tuple[list[tuple[int, str]], list[str]]:
    visible: list[tuple[int, str]] = []
    errors: list[str] = []
    fence_char: str | None = None
    fence_length = 0
    opened_at = 0
    for number, line in enumerate(text.splitlines(), 1):
        m = re.match(r'^\s{0,3}(`{3,}|~{3,})(.*)$', line)
        if m:
            marker, suffix = m.groups()
            if fence_char is None:
                fence_char, fence_length, opened_at = marker[0], len(marker), number
                continue
            if marker[0] == fence_char and len(marker) >= fence_length and not suffix.strip():
                fence_char = None
                continue
        if fence_char is None:
            visible.append((number, line))
    if fence_char is not None:
        errors.append(f'unclosed fence at line {opened_at}')
    return visible, errors


def table_cells(line: str) -> list[str]:
    s = line.strip()
    cuts = []
    for i, ch in enumerate(s):
        if ch != '|':
            continue
        slashes, j = 0, i - 1
        while j >= 0 and s[j] == '\\':
            slashes += 1
            j -= 1
        if slashes % 2 == 0:
            cuts.append(i)
    parts, last = [], 0
    for pos in cuts:
        parts.append(s[last:pos].strip())
        last = pos + 1
    parts.append(s[last:].strip())
    if cuts and cuts[0] == 0:
        parts = parts[1:]
    if cuts and cuts[-1] == len(s) - 1:
        parts = parts[:-1]
    return parts


def inspect_markdown(text: str) -> dict:
    visible, errors = outside_fences(text)
    blocks: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    previous_line = -1
    for number, line in visible:
        is_row = line.lstrip().startswith('|')
        if current and (not is_row or number != previous_line + 1):
            blocks.append(current)
            current = []
        if is_row:
            current.append((number, line))
        previous_line = number
    if current:
        blocks.append(current)
    tables = rows = cells = 0
    for block in blocks:
        parsed = [(n, table_cells(l)) for n, l in block]
        if len(parsed) < 2 or not all(re.fullmatch(r':?-{3,}:?', x) for x in parsed[1][1]):
            errors.append(f'table missing valid delimiter at line {block[0][0]}')
            continue
        tables += 1
        width = len(parsed[0][1])
        for idx, (number, cs) in enumerate(parsed):
            if len(cs) != width:
                errors.append(f'table column mismatch at line {number}: {len(cs)} != {width}')
            if idx == 1:
                continue
            rows += 1
            cells += len(cs)
            if any(not c.strip() for c in cs):
                errors.append(f'empty table cell at line {number}')
    links = []
    for number, line in visible:
        for m in re.finditer(r'(?<!!)\[[^\]]+\]\(([^)]+)\)', line):
            target = m.group(1).strip().split(' "', 1)[0]
            if target and not re.match(r'^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|#)', target):
                links.append((number, unquote(target.split('#', 1)[0])))
    return {'tables': tables, 'rows': rows, 'cells': cells, 'links': links, 'errors': errors}


def validate(root: Path) -> dict:
    root = root.resolve()
    errors: list[str] = []
    counts = {'markdown_files': 0, 'table_occurrences': 0, 'table_cells': 0, 'relative_links': 0}

    def load(path: str):
        try:
            return json.loads((root / path).read_text(encoding='utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f'{path}: {exc}')
            return None

    def exists(path: str, owner: str):
        p = (root / path).resolve()
        if not p.is_relative_to(root) or not p.is_file():
            errors.append(f'{owner}: missing or unsafe path {path}')

    sm = load('docs/source/source_map.json')
    raw = b''
    if sm:
        try:
            raw = (root / sm['source_path']).read_bytes()
            lines = raw.decode('utf-8').splitlines(keepends=True)
            if sha(raw) != sm['source_sha256']:
                errors.append('source hash mismatch')
            if len(lines) != sm['source_lines']:
                errors.append('source line count mismatch')
            cursor = 1
            pieces = []
            for part in sm['parts']:
                if part['start_line'] != cursor:
                    errors.append(f"source partition gap/overlap: {part['path']}")
                data = (root / part['path']).read_bytes()
                expected = ''.join(lines[part['start_line'] - 1:part['end_line']]).encode('utf-8')
                if data != expected or sha(data) != part['sha256']:
                    errors.append(f"split hash/content mismatch: {part['path']}")
                pieces.append(data)
                cursor = part['end_line'] + 1
            if cursor != len(lines) + 1 or b''.join(pieces) != raw:
                errors.append('source reconstruction mismatch')
            counts['source_lines'] = len(lines)
            counts['source_parts'] = len(sm['parts'])
        except (OSError, UnicodeError, KeyError, TypeError) as exc:
            errors.append(f'source validation: {exc}')

    for p in sorted(markdown_files(root)):
        counts['markdown_files'] += 1
        rel = p.relative_to(root).as_posix()
        try:
            check = inspect_markdown(p.read_text(encoding='utf-8'))
        except (OSError, UnicodeError) as exc:
            errors.append(f'{rel}: {exc}')
            continue
        counts['table_occurrences'] += check['tables']
        counts['table_cells'] += check['cells']
        for err in check['errors']:
            errors.append(f'{rel}: {err}')
        for line, target in check['links']:
            counts['relative_links'] += 1
            linked = (p.parent / target).resolve()
            if not linked.is_relative_to(root) or not linked.exists():
                errors.append(f'{rel}:{line}: missing local link {target}')

    proposals = load('docs/decisions/decisions.json')
    catalog = load('tests/specs/acceptance_catalog.json')
    inv = load('tests/specs/invariant_traceability.json')
    findings = load('docs/review/findings.json')
    tasks = load('tasks/task_graph.json')

    ps = {x['id']: x for x in proposals['proposals']} if proposals else {}
    ts = {x['id']: x for x in catalog['tests']} if catalog else {}
    fs = {x['id']: x for x in findings['findings']} if findings else {}
    jobs = {x['id']: x for x in tasks['tasks']} if tasks else {}
    for owner, items, keyed in [('proposals', proposals.get('proposals', []) if proposals else [], ps),
                                ('tests', catalog.get('tests', []) if catalog else [], ts),
                                ('findings', findings.get('findings', []) if findings else [], fs),
                                ('tasks', tasks.get('tasks', []) if tasks else [], jobs)]:
        if len(items) != len(keyed):
            errors.append(f'duplicate IDs in {owner}')
    counts.update(proposals=len(ps), acceptance_specs=len(ts), findings=len(fs), tasks=len(jobs))
    for p in ps.values():
        exists(p['contract_path'], p['id'])
        if p['status'] == 'accepted' and (not p.get('approval_ref') or not p.get('selected_details')):
            errors.append(f"accepted proposal lacks approval/details: {p['id']}")
        if p['status'] not in {'proposed', 'accepted', 'rejected', 'deferred'}:
            errors.append(f"invalid proposal status: {p['id']}")
        for f in p['finding_ids']:
            if f not in fs:
                errors.append(f"unknown finding {f} in {p['id']}")
    for f in fs.values():
        if f['decision'] not in ps:
            errors.append(f"unknown decision in {f['id']}")
        if not f['tests']:
            errors.append(f"finding without tests: {f['id']}")
        for t in f['tests']:
            if t not in ts:
                errors.append(f"unknown test {t} in {f['id']}")
    for t in ts.values():
        for field in ['given', 'when', 'then', 'implementation_status']:
            if not t.get(field):
                errors.append(f"test {t['id']} lacks {field}")
        for pid in t['proposal_dependencies']:
            if pid not in ps:
                errors.append(f"unknown proposal {pid} in {t['id']}")
    if inv:
        ivs = inv['invariants']
        counts['baseline_invariants'] = len(ivs)
        if {x['id'] for x in ivs} != {f'I{i:02d}' for i in range(1, 46)}:
            errors.append('invariant ID coverage mismatch')
        srclines = raw.decode('utf-8').splitlines() if raw else []
        for v in ivs:
            if not v['test_ids']:
                errors.append(f"invariant without tests: {v['id']}")
            for tid in v['test_ids']:
                if tid not in ts:
                    errors.append(f"unknown test {tid} in {v['id']}")
            idx = v['source_line'] - 1
            if idx >= len(srclines) or re.sub(r'^\d+\. ', '', srclines[idx]) != v['text']:
                errors.append(f"invariant text/source mismatch: {v['id']}")
    for job in jobs.values():
        exists(job['path'], job['id'])
        for path in job['read_paths']:
            exists(path, job['id'])
        for tid in job['acceptance_ids']:
            if tid not in ts:
                errors.append(f"unknown test {tid} in {job['id']}")
        for pid in job['required_decisions']:
            if pid not in ps:
                errors.append(f"unknown proposal {pid} in {job['id']}")
        for dep in job['depends_on']:
            if dep not in jobs:
                errors.append(f"unknown task dependency {dep} in {job['id']}")
    visiting, visited = set(), set()
    def visit(jid: str):
        if jid in visiting:
            errors.append(f'task dependency cycle at {jid}')
            return
        if jid in visited or jid not in jobs:
            return
        visiting.add(jid)
        for dep in jobs[jid]['depends_on']:
            visit(dep)
        visiting.remove(jid)
        visited.add(jid)
    for jid in jobs:
        visit(jid)
    for p in sorted((root / 'fixtures').glob('S*.json')):
        sc = load(p.relative_to(root).as_posix())
        if sc:
            for tid in sc['tests']:
                if tid not in ts:
                    errors.append(f'unknown fixture test {tid} in {p.name}')
    for p in sorted((root / 'tools').glob('*.py')):
        try:
            ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
        except (OSError, SyntaxError) as exc:
            errors.append(f'Python syntax error: {p.name}: {exc}')
    policy_counts, policy_errors = validate_release_policy(root)
    counts.update(policy_counts)
    errors.extend(policy_errors)
    counts['root_agents_bytes'] = (root / 'AGENTS.md').stat().st_size if (root / 'AGENTS.md').exists() else 0
    return {'status': 'passed' if not errors else 'failed',
            'scope': 'handoff document integrity; NOT application/runtime/LLM tests',
            'counts': counts, 'errors': errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    result = validate(args.root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result['status'].upper() + ': ' + result['scope'])
        for key, value in result['counts'].items():
            print(f'{key}: {value}')
        for error in result['errors']:
            print('ERROR: ' + error)
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
