"""Run the explicit local query CLI/embedding/GLM worker loop and retain receipts.

No database credentials enter this process: Docker uses its existing secret mount.
The caller supplies the dedicated project, artifact volume, model and query IDs.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
from uuid import UUID


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True, help='Host folder mounted as /results')
    parser.add_argument('--project', required=True)
    parser.add_argument('--database-name', required=True)
    parser.add_argument('--artifact-volume', required=True)
    parser.add_argument('--app-image', default='palimpsest-query:0.8.0',
                        help='Existing app image used for the selected database schema')
    parser.add_argument('--model-directory', type=Path, required=True)
    parser.add_argument('--index-id', required=True)
    parser.add_argument('--request-id', required=True)
    parser.add_argument('--question', required=True)
    parser.add_argument('--allow-model-calls', action='store_true', help='Explicitly invoke the configured local GLM worker')
    parser.add_argument('--revise', action='store_true', help='Start one new review attempt, preserving the previous answer')
    parser.add_argument('--review-notes', type=Path, help='JSON string list inside --directory for a reviewed answer')
    args = parser.parse_args()
    for identifier in (args.index_id, args.request_id):
        parsed = UUID(identifier)
        if parsed.version != 7 or str(parsed) != identifier:
            parser.error('Canonical UUIDv7 identifiers are required.')
    if not args.allow_model_calls:
        parser.error('This runner makes live model calls; explicitly enable them or use the separate preparation CLI.')
    repository = Path(__file__).resolve().parents[1]
    root = args.directory.resolve(strict=True)
    model = args.model_directory.resolve(strict=True)
    environment = dict(os.environ, PALIMPSEST_APP_IMAGE=args.app_image)
    base = ['docker', 'compose', '-p', args.project, 'run', '--rm', '--no-deps', '-T',
        '--volume', args.artifact_volume + ':/var/lib/palimpsest/artifacts:ro',
        '--volume', str(repository) + ':/workspace:ro', '--volume', str(root) + ':/results',
        '--env', 'PYTHONPATH=/workspace/src', '--entrypoint', 'python', 'app', '-m', 'palimpsest', 'wiki']
    common = ['--database-name', args.database_name, '--directory', '/results/query-store',
              '--request-id', args.request_id, '--json', '--non-interactive']
    # Keep controller attempts outside the runtime's immutable phase files.
    journal = root / 'controller' / args.request_id
    journal.mkdir(parents=True, exist_ok=True)

    def run(argv, kind):
        result = subprocess.run(argv, cwd=repository, env=environment, capture_output=True, encoding='utf-8')
        record = {'kind': kind, 'argv': argv, 'exit_code': result.returncode,
                  'stdout': result.stdout, 'stderr': result.stderr}
        path = journal / (f'{len(list(journal.glob("*.json"))):04d}-' + kind + '.json')
        with path.open('x', encoding='utf-8') as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
        if result.returncode:
            raise RuntimeError(f'{kind} failed; inspect {path}')
        return result.stdout

    def cli(action, *options):
        result = json.loads(run([*base, action, *common, *options], action))
        if result['command_status'] != 'succeeded':
            raise RuntimeError(f'{action}: {result.get("error")}')
        return result['result']

    def host(path):
        relative = PurePosixPath(path).relative_to('/results')
        if '..' in relative.parts:
            raise ValueError('Invalid worker path')
        return root.joinpath(*relative.parts)

    def embed(operation, request_path, result_path):
        if not host(result_path).exists():
            run(['docker', 'run', '--rm', '--gpus', 'all', '--network', 'none',
                '--mount', f'type=bind,source={repository},target=/workspace,readonly',
                '--mount', f'type=bind,source={model},target=/models,readonly',
                '--mount', f'type=bind,source={root},target=/results',
                'palimpsest-retrieval-bge:0.1.0', operation, '--input', request_path,
                '--output', result_path, '--model-path', '/models', '--device', 'cuda'], operation)
        return result_path

    def call(phase):
        request = cli('query-request', '--phase', phase)
        path = host(request['request_file'])
        payload = json.loads(path.read_text(encoding='utf-8'))
        response = path.parent / payload['output_file']
        if not response.exists():
            run([sys.executable, '-X', 'utf8', '-B', str(repository / 'tools/run_knowledge_model.py'), str(path)], phase)
        response_path = '/results/' + response.relative_to(root).as_posix()
        return cli('query-stage' if phase == 'generator' else 'query-decide', '--response', response_path)

    job = cli('query-prepare', '--index-id', args.index_id, '--question', args.question)
    if args.revise:
        options = []
        if args.review_notes:
            note_path = args.review_notes.resolve(strict=True)
            options = ['--review-notes', '/results/' + note_path.relative_to(root).as_posix()]
        job = cli('query-revise', *options)
    seen = set()
    while job['state'] not in ('answered', 'needs_review', 'needs_attention'):
        print(json.dumps({'query_id': args.request_id, 'state': job['state'], 'round': job['round']}, ensure_ascii=False), flush=True)
        folder = f"/results/query-store/queries/{args.request_id}/rounds/{job['round']}"
        if job['state'] == 'search_pending':
            output = embed('encode', folder + '/query-embedding-request.json', folder + '/query-embedding-result-worker.json')
            cli('query-search', '--embedding', output)
        elif job['state'] == 'rerank_pending':
            request = json.loads(host(folder + '/rerank-request.json').read_text())
            if not request['passages']:
                # No candidates is not a model score or a final negative answer.
                canonical = json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
                value = {'schema_version': 'wiki-rerank-result-v1', 'profile': request['profile'],
                         'input_sha256': sha256(canonical).hexdigest(), 'scores': []}
                empty = host(folder + '/rerank-result-empty.json')
                if not empty.exists():
                    empty.write_text(json.dumps(value), encoding='utf-8')
                output = folder + '/rerank-result-empty.json'
            else:
                output = embed('rerank', folder + '/rerank-request.json', folder + '/rerank-result-worker.json')
            cli('query-context', '--rerank', output)
        elif job['state'] == 'input_ready':
            context = json.loads(host('/results/query-store/' + job['context_path']).read_text(encoding='utf-8'))
            key = (job['search_query'], tuple(u['information_id'] for u in context['information']),
                   tuple(i['evidence_id'] for i in context['source_images']))
            if key in seen:
                job = cli('query-pause', '--reason', 'repeated_request_without_new_evidence; unresolved_source_or_search')
                continue
            seen.add(key)
            call('generator')
        elif job['state'] == 'source_pending':
            cli('query-source')
        elif job['state'] == 'proposed':
            call('validator')
        else:
            raise RuntimeError('Unresolved query state: ' + job['state'])
        job = cli('query-show')
    print(json.dumps({'query_id': args.request_id, 'state': job['state'], 'round': job['round'],
                     'answer_path': job.get('answer_path'), 'canonical_writes': 0, 'd2i_calls': 0}, ensure_ascii=False))
    return 0 if job['state'] == 'answered' else 6


if __name__ == '__main__':
    raise SystemExit(main())
