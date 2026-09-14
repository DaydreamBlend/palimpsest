"""Explicit original-source exception commands, separate from I2K adapters."""
import json
from pathlib import Path

from .data import data_id, request_id


def configure(commands, common):
    actions = commands.add_parser('d2k', parents=[common], help='사용자가 요청한 D2I 오류 예외: 원문 D에서 K 생성').add_subparsers(dest='action',required=True)
    export = actions.add_parser('export-source',parents=[common])
    export.add_argument('data_id',type=data_id)
    export.add_argument('destination',type=Path)
    draft = actions.add_parser('draft',parents=[common],help='모델 호출 없이 전송 범위와 확인 manifest 준비')
    draft.add_argument('data_id',type=data_id)
    draft.add_argument('--request-id',type=request_id,required=True)
    draft.add_argument('--reason',required=True)
    draft.add_argument('--failure-execution-id',type=request_id)
    views = draft.add_mutually_exclusive_group()
    views.add_argument('--byte-range',type=int,nargs=2,action='append')
    views.add_argument('--pdf-directory',type=Path)
    draft.add_argument('--data-version-id',type=request_id,action='append')
    draft.add_argument('--data-version-mode',choices=('current','pinned'),default='current')
    actions.add_parser('preparation',parents=[common]).add_argument('preparation_id',type=request_id)
    authorize = actions.add_parser('authorize',parents=[common],help='사용자의 명시적인 정확한 manifest 확인 기록')
    authorize.add_argument('preparation_id',type=request_id)
    authorize.add_argument('--authorization-id',type=request_id,required=True)
    authorize.add_argument('--confirm-manifest-sha256',type=data_id,required=True)
    authorize.add_argument('--actor-ref',required=True)
    prepare = actions.add_parser('prepare',parents=[common])
    prepare.add_argument('authorization_id',type=request_id)
    prepare.add_argument('--request-id',type=request_id,required=True)
    prepare.add_argument('--prior-execution-id',type=request_id)
    for action in ('show','request','stage','decide','fail'):
        child = actions.add_parser(action,parents=[common])
        child.add_argument('execution_id',type=request_id)
        if action=='request':
            child.add_argument('--phase',choices=('generator','validator'),required=True)
            child.add_argument('--directory',type=Path,required=True)
        elif action in ('stage','decide'):
            child.add_argument('--response',type=Path,required=True)
        elif action=='fail':
            child.add_argument('--code',required=True)


def run(args, config):
    from .d2k_runtime import D2KRuntime
    from .knowledge_runtime import KnowledgeRuntime
    from .errors import PalimpsestError
    service = D2KRuntime(config.database_dsn,config.artifact_root)
    if args.action=='export-source':
        return service.export_source(args.data_id,args.destination)
    if args.action=='draft':
        return service.draft(args.data_id,args.request_id,reason=args.reason,failure_execution_id=args.failure_execution_id,
            byte_ranges=args.byte_range,pdf_directory=args.pdf_directory,data_version_ids=args.data_version_id,
            data_version_mode=args.data_version_mode)
    if args.action=='preparation':
        return service.preparation(args.preparation_id)
    if args.action=='authorize':
        return service.authorize(args.preparation_id,args.authorization_id,args.confirm_manifest_sha256,actor_ref=args.actor_ref)
    if args.action=='prepare':
        return service.prepare(args.authorization_id,args.request_id,prior_execution_id=args.prior_execution_id)
    runtime = KnowledgeRuntime(config.database_dsn)
    job = runtime.show(args.execution_id)
    if job['operation']!='d2k':
        raise PalimpsestError('invalid_d2k_operation','명시적으로 요청한 D2K 실행 ID를 지정하세요.',2)
    if args.action=='show':
        return job
    if args.action=='request':
        return service.prepare_call(args.execution_id,args.phase,args.directory)
    if args.action=='fail':
        return runtime.fail_execution(args.execution_id,args.code)
    payload = json.loads(args.response.read_text(encoding='utf-8'))
    return (runtime.stage if args.action=='stage' else runtime.decide)(args.execution_id,payload['response'],payload['receipt'])
