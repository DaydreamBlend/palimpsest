"""Explicit offline BGE worker; emit a compact summary, write vectors to a file."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from palimpsest.bge_retrieval import BgeM3, digest, validate_request
from palimpsest.errors import PalimpsestError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('encode', 'rerank'))
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model-path', type=Path, required=True)
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cpu')
    args = parser.parse_args()
    try:
        if args.output.exists() or args.output.is_symlink():
            raise PalimpsestError('retrieval_output_exists', '새 결과 파일 경로를 지정하세요.', 6)
        request = json.loads(args.input.read_bytes())
        validate_request(request, args.operation)
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
        os.environ['TOKENIZERS_PARALLELISM'] = 'false'
        model = BgeM3(args.model_path, device=args.device)
        result = model.encode(request) if args.operation == 'encode' else model.rerank(request)
        raw = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(prefix='.bge-output-', dir=args.output.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, args.output)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        summary = {'status': 'succeeded', 'operation': args.operation, 'output': str(args.output),
                   'output_sha256': sha256(raw).hexdigest(), 'input_sha256': result['input_sha256'],
                   'profile_sha256': digest(result['profile']), 'device': args.device,
                   'documents': len(result.get('documents', [])),
                   'chunks': sum(len(row['chunks']) for row in result.get('documents', [])),
                   'scores': len(result.get('scores', []))}
        print(json.dumps(summary, ensure_ascii=False))
    except PalimpsestError as error:
        print(json.dumps({'status': 'failed', 'error_code': error.code}), file=sys.stderr)
        raise SystemExit(error.exit_code) from None
    except Exception:
        # Library exceptions may quote user inputs, file content or credentials.
        print(json.dumps({'status': 'failed', 'error_code': 'retrieval_worker_failed'}), file=sys.stderr)
        raise SystemExit(4) from None


if __name__ == '__main__':
    main()
