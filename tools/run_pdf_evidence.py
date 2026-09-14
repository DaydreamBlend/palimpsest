"""Build local PDF evidence with the existing, pinned MinerU Hybrid image."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'sha256:3f9361035fa4d601d54ed524410d89871fe2524047b04a821594485aae93e0d4'


def docker_command(parse_result, output, pdf=None):
    parse_result = Path(parse_result).resolve(strict=True)
    output = Path(output).resolve()
    if (not parse_result.is_relative_to(ROOT) or not output.is_relative_to(ROOT) or output.exists()
            or output.is_relative_to(parse_result.parent) or parse_result.is_relative_to(output)):
        raise ValueError('Use a retained parser receipt and a new output directory within the repository')
    output.parent.mkdir(parents=True, exist_ok=True)
    command = ['docker', 'run', '--rm', '--network', 'none', '--read-only', '--tmpfs', '/tmp',
               '--volume', f'{ROOT.as_posix()}:/repo:ro',
               '--volume', f'{output.parent.as_posix()}:/result',
               '--env', 'PYTHONPATH=/repo/src', '--workdir', '/repo', '--entrypoint', 'python',
               IMAGE, '-B', '-m', 'palimpsest.pdf_evidence', 'build',
               '--parse-result', '/repo/' + parse_result.relative_to(ROOT).as_posix(),
               '--output', '/result/' + output.name]
    if pdf:
        pdf = Path(pdf).resolve(strict=True)
        if not pdf.is_relative_to(ROOT):
            # An explicitly supplied original is a read-only file, never a broad Desktop mount.
            marker = command.index('--env')
            command[marker:marker] = ['--volume', f'{pdf.as_posix()}:/input/source.pdf:ro']
            location = '/input/source.pdf'
        else:
            location = '/repo/' + pdf.relative_to(ROOT).as_posix()
        command.extend(['--pdf', location])
    return command


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parse-result', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pdf', type=Path)
    args = parser.parse_args(argv)
    try:
        return subprocess.run(docker_command(args.parse_result, args.output, args.pdf), cwd=ROOT).returncode
    except (ValueError, OSError):
        print(json.dumps({'state': 'failed', 'error': 'invalid_evidence_worker_input'}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
