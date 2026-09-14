"""Prepare an explicit full-I generation/validation request for the OAuth worker."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from palimpsest.knowledge_requests import generation_request, validation_request
from palimpsest import multi_source_i2k as multi


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('generator','validator'))
    parser.add_argument('--context', type=Path, required=True)
    parser.add_argument('--source-directory', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--response-name', required=True)
    args = parser.parse_args()
    if (not args.response_name or args.response_name in ('.', '..')
            or Path(args.response_name).name != args.response_name
            or '/' in args.response_name or '\\' in args.response_name):
        raise ValueError('The response filename must be a local basename')
    source_root = args.source_directory.resolve(strict=True)
    context = json.loads(args.context.read_text(encoding='utf-8'))
    if 'command_status' in context:
        if context['command_status'] != 'succeeded':
            raise ValueError('Cannot prepare a call from an unsuccessful Runtime response')
        context = context['result']
    snapshot = context['input_snapshot']
    packet = snapshot['input']
    is_multi = packet.get('schema_version') == multi.INPUT_SCHEMA
    if is_multi:
        multi.check_input(packet)
    ids = [unit['information_id'] for unit in packet['model_input']['information']]
    if packet['target_information_ids'] != ids or packet['context_information_ids'] or packet['excluded_information_ids']:
        raise ValueError('A full source selection call requires all Information')
    assets = json.loads((args.source_directory/'attachments.json').read_text(encoding='utf-8'))
    required = {item['sha256']:item['byte_size'] for item in packet['media_assets']}
    if {a['sha256']:a['byte_size'] for a in assets} != required or len(assets) != len(required):
        raise ValueError('Incomplete or duplicated source attachments')
    images = []
    for asset in assets:
        path = (args.source_directory/asset['relative_path']).resolve(strict=True)
        if not path.is_relative_to(source_root):
            raise ValueError('An attachment escaped the source directory')
        raw = path.read_bytes()
        if sha256(raw).hexdigest() != asset['sha256'] or len(raw) != asset['byte_size']:
            raise ValueError('Source attachment changed')
        images.append({'path':os.path.relpath(path,args.request.resolve().parent),'sha256':asset['sha256']})
    if args.phase == 'generator':
        prompt, schema = generation_request(snapshot, assets)
        input_sha = context['input_digest']
    else:
        prompt, schema = validation_request(context, assets)
        input_sha = context['validation_context_sha']
    request = {'prompt':prompt,'schema':schema,'images':images,'input_sha256':input_sha,
               'output_file':args.response_name,'delivered_information_ids':ids}
    if snapshot.get('data_versions'):
        request['delivered_data_version_ids'] = [v['version_id'] for v in snapshot['data_versions']]
    with args.request.open('x',encoding='utf-8') as stream:
        json.dump(request,stream,ensure_ascii=False,indent=2)
    print(json.dumps({'information_count':len(ids),'images':len(images),'prompt_characters':len(prompt)}))


if __name__ == '__main__':
    main()
