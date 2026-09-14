"""Export an exact N2E request; this tool has no provider or database authority."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from palimpsest.knowledge_requests import edge_generation_request, edge_validation_request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('generator', 'validator'))
    parser.add_argument('--context', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--response-name', required=True)
    args = parser.parse_args()
    if (not args.response_name or args.response_name in ('.', '..')
            or Path(args.response_name).name != args.response_name
            or '/' in args.response_name or '\\' in args.response_name):
        raise ValueError('The response filename must be a local basename')
    context = json.loads(args.context.read_text(encoding='utf-8'))
    if 'command_status' in context:
        if context['command_status'] != 'succeeded':
            raise ValueError('The Runtime context must be successful')
        context = context['result']
    if context.get('operation') != 'n2e':
        raise ValueError('An actual N2E Runtime context is required')
    snapshot = context['input_snapshot']
    if args.phase == 'generator':
        prompt, schema = edge_generation_request(snapshot)
        input_sha = context['input_digest']
    else:
        prompt, schema = edge_validation_request(context)
        input_sha = context['validation_context_sha']
    refs = [node['knode_revision_id'] for node in snapshot['input']['nodes']]
    request = {'prompt': prompt, 'schema': schema, 'images': [], 'input_sha256': input_sha,
        'output_file': args.response_name, 'delivered_knowledge_revision_ids': refs}
    if snapshot.get('data_versions'):
        request['delivered_data_version_ids'] = [v['version_id'] for v in snapshot['data_versions']]
    with args.request.open('x', encoding='utf-8') as stream:
        json.dump(request, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'node_revisions': len(refs), 'prompt_characters': len(prompt), 'provider_calls': 0}))


if __name__ == '__main__':
    main()
