"""Export a reviewable K2K request. No provider call or database mutation."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from palimpsest import k2k


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('generator', 'validator'))
    parser.add_argument('--context', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--response-name', required=True)
    args = parser.parse_args()
    if (not args.response_name or args.response_name in ('.', '..')
            or Path(args.response_name).name != args.response_name or '/' in args.response_name or '\\' in args.response_name):
        raise ValueError('The response filename must be a local basename')
    context = json.loads(args.context.read_text(encoding='utf-8'))
    if 'command_status' in context:
        if context['command_status'] != 'succeeded':
            raise ValueError('The Runtime context must be successful')
        context = context['result']
    if context.get('operation') != 'k2k' or context.get('profile', {}).get('schema_version') != k2k.PROFILE:
        raise ValueError('An actual K2K Runtime context is required')
    snapshot = context['input_snapshot']
    refs = k2k.check_input(snapshot['input'])
    if args.phase == 'generator':
        prompt, schema = k2k.generation(snapshot), k2k.generation_schema(snapshot['input'])
        input_sha = context['input_digest']
    else:
        prompt = k2k.validation(context)
        schema = k2k.validation_schema([node['candidate_key'] for node in context['candidates']],
            [node['knode_revision_id'] for node in snapshot['existing_nodes']])
        input_sha = context['validation_context_sha']
    request = {'prompt': prompt, 'schema': schema, 'images': [], 'input_sha256': input_sha,
        'output_file': args.response_name, 'delivered_knowledge_revision_ids': refs}
    if snapshot.get('data_versions'):
        request['delivered_data_version_ids'] = [v['version_id'] for v in snapshot['data_versions']]
    with args.request.open('x', encoding='utf-8') as stream:
        json.dump(request, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'premise_revisions': len(refs), 'prompt_characters': len(prompt), 'provider_calls': 0}))


if __name__ == '__main__':
    main()
