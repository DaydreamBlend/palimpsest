"""One explicit local GLM call for a structured knowledge worker exchange.

This host worker has no database authority. Runtime stages and validates every
response separately. It never claims a source descriptor was delivered.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from palimpsest.local_glm_provider import LocalGLMProvider
from palimpsest.errors import PalimpsestError


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('request', type=Path)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding='utf-8'))
    root = args.request.resolve().parent
    name = request['output_file']
    if (not isinstance(name, str) or not name or name in ('.', '..')
            or Path(name).name != name or '/' in name or '\\' in name):
        raise ValueError('The response filename must be a local basename')
    destination = root / name
    failure_file = destination.with_suffix('.failure.json')
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('A model response already exists; choose a new attempt filename')
    if failure_file.exists():
        raise FileExistsError('This attempt already failed; choose a new attempt filename')
    images = []
    attachments = []
    for item in request['images']:
        path = (root / item['path']).resolve(strict=True)
        raw = path.read_bytes()
        if sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('Knowledge attachment hash mismatch')
        images.append(path)
        attachments.append({'sha256': item['sha256'], 'byte_size': len(raw)})
    start = time.monotonic()
    try:
        result = LocalGLMProvider(timeout_seconds=1200).generate(
            prompt=request['prompt'], schema=request['schema'], images=images, cwd=root)
    except PalimpsestError as exc:
        failure = {'error_code':exc.code,'diagnostic':exc.details,
            'input_sha256':request['input_sha256'],
            'prompt_sha256':sha256(request['prompt'].encode()).hexdigest(),
            'schema_sha256':digest(request['schema']),
            'request_file_sha256':sha256(args.request.read_bytes()).hexdigest(),
            'planned_image_attachments':attachments,
            'planned_information_ids':request.get('delivered_information_ids',[]),
            'planned_knowledge_revision_ids':request.get('delivered_knowledge_revision_ids',[]),
            'planned_data_view_ids':request.get('delivered_data_view_ids',[]),
            'planned_revision_target_id':request.get('delivered_revision_target_id'),
            'planned_revalidation_target_sha256':request.get('delivered_revalidation_target_sha256'),
            'planned_edge_review_target_sha256':request.get('delivered_edge_review_target_sha256'),
            'planned_effective_edge_refs':request.get('delivered_effective_edge_refs',[]),
            'planned_effective_input_sha256':request.get('delivered_effective_input_sha256'),
            'planned_effective_edge_premises':request.get('delivered_effective_edge_premises',[]),
            'planned_data_version_ids':request.get('delivered_data_version_ids',[]),
            'actual_delivery':None,'output_sha256':None,
            'elapsed_seconds':round(time.monotonic()-start,3)}
        with failure_file.open('x',encoding='utf-8') as stream:
            json.dump({'failure':failure},stream,ensure_ascii=False,indent=2)
        print(json.dumps({'failure_file':str(failure_file),'error_code':exc.code,'diagnostic':exc.details}),flush=True)
        raise SystemExit(exc.exit_code) from None
    receipt = {
        'profile': result.profile, 'input_sha256': request['input_sha256'],
        'output_sha256': digest(result.output), 'provider_ref': result.thread_ref,
        'actual_delivery': True, 'usage': result.usage or {},
        'prompt_sha256': sha256(request['prompt'].encode()).hexdigest(),
        'schema_sha256': digest(request['schema']), 'image_attachments': attachments,
        'original_pdf_delivered': False, 'elapsed_seconds': round(time.monotonic()-start, 3),
    }
    if 'delivered_information_ids' in request:
        receipt['delivered_information_ids'] = request['delivered_information_ids']
    for field in ('delivered_source_target_ids', 'batch_id'):
        if field in request:
            receipt[field] = request[field]
    if 'delivered_knowledge_revision_ids' in request:
        receipt['delivered_knowledge_revision_ids'] = request['delivered_knowledge_revision_ids']
    if 'delivered_data_view_ids' in request:
        receipt['delivered_data_view_ids'] = request['delivered_data_view_ids']
    if 'delivered_revision_target_id' in request:
        receipt['delivered_revision_target_id'] = request['delivered_revision_target_id']
    if 'delivered_revalidation_target_sha256' in request:
        receipt['delivered_revalidation_target_sha256'] = request['delivered_revalidation_target_sha256']
    if 'delivered_edge_review_target_sha256' in request:
        receipt['delivered_edge_review_target_sha256'] = request['delivered_edge_review_target_sha256']
    for field in ('delivered_effective_edge_refs', 'delivered_effective_input_sha256', 'delivered_effective_edge_premises'):
        if field in request:
            receipt[field] = request[field]
    if 'delivered_data_version_ids' in request:
        receipt['delivered_data_version_ids'] = request['delivered_data_version_ids']
    with destination.open('x', encoding='utf-8') as stream:
        json.dump({'response': result.output, 'receipt': receipt}, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'file': str(destination), 'usage': result.usage,
                      'elapsed_seconds': receipt['elapsed_seconds'],
                      'model': result.profile['model']}), flush=True)


if __name__ == '__main__':
    main()
