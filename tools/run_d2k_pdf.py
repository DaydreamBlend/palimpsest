"""Prepare selected original PDF views using the existing pinned local image.

This is not a provider or a D2I command. The application separately verifies
registration, grants manual D2K authority and binds generated view IDs/manifest.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from palimpsest.d2k_pdf import (IMAGE, _hash, _path, _require, _selection, _source,
                                render_source, verify_source)
from palimpsest.errors import PalimpsestError


def docker_command(source, output, *, data_id, byte_size, page_numbers):
    source, output = _path(source, required=True), _path(output)
    pages = _selection(page_numbers)
    _source(source, data_id, byte_size)
    _require(source.is_relative_to(ROOT) and output.is_relative_to(ROOT)
             and not source.is_relative_to(output) and (not output.exists()
             or (output.is_dir() and not any(output.iterdir()))), 'source_view_workspace_scope_required')
    output.mkdir(parents=True, exist_ok=True)
    command = ['docker', 'run', '--rm', '--pull', 'never', '--network', 'none', '--read-only', '--tmpfs', '/tmp',
        '--volume', f'{ROOT.as_posix()}:/repo:ro', '--volume', f'{output.as_posix()}:/result',
        '--env', 'PYTHONPATH=/repo/src', '--workdir', '/repo', '--entrypoint', 'python', IMAGE,
        '-B', '/repo/tools/run_d2k_pdf.py', '--worker', '--pdf', '/repo/' + source.relative_to(ROOT).as_posix(),
        '--output', '/result', '--data-id', data_id, '--byte-size', str(byte_size)]
    for number in pages:
        command.extend(['--page', str(number)])
    return command


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--data-id', required=True)
    parser.add_argument('--byte-size', type=int, required=True)
    parser.add_argument('--page', type=int, action='append', required=True)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--verify', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.worker:
            result = (verify_source(args.pdf, args.output, args.data_id, expected_byte_size=args.byte_size) if args.verify else
                render_source(args.pdf, args.output, args.data_id, args.page, expected_byte_size=args.byte_size))
            _require(result['source']['data_id'] == args.data_id and result['source']['byte_size'] == args.byte_size
                     and result['selected_page_numbers'] == _selection(args.page), 'source_view_request_changed')
            print(json.dumps({'state': 'verified', 'manifest': str(args.output / 'manifest.json'),
                'manifest_sha256': _hash(args.output / 'manifest.json'), 'data_id': args.data_id,
                'selected_page_numbers': result['selected_page_numbers'], 'd2i_calls': 0, 'model_calls': 0}))
            return 0
        _require(not args.verify, 'verification_requires_pinned_worker')
        return subprocess.run(docker_command(args.pdf, args.output, data_id=args.data_id,
            byte_size=args.byte_size, page_numbers=args.page), cwd=ROOT, check=False).returncode
    except (PalimpsestError, ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({'state': 'failed', 'error': getattr(error, 'code', str(error)), 'd2i_calls': 0, 'model_calls': 0}))
        return getattr(error, 'exit_code', 2)


if __name__ == '__main__':
    sys.exit(main())
