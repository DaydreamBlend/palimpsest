"""Thin adapters for durable propagation preparation, control and worker steps."""
import json
from pathlib import Path
from .data import data_id,request_id


def configure(commands,common):
    actions=commands.add_parser('propagation',parents=[common],help='변경 영향·outbox 전파와 Wiki 갱신').add_subparsers(dest='action',required=True)
    for name in ('prepare','start','show','next','advance','accept','renew','call-failed','retry','pause','resume','cancel'):
        child=actions.add_parser(name,parents=[common])
        child.add_argument('--directory',type=Path,required=True)
        child.add_argument('--database-name',required=True)
        if name=='prepare':
            child.add_argument('--request-id',type=request_id,required=True)
            child.add_argument('--record-id',type=request_id,action='append',required=True)
            child.add_argument('--allow-data-id',type=data_id,action='append')
            child.add_argument('--wiki-id',type=request_id,action='append')
            child.add_argument('--data-version-id',type=request_id,action='append')
            child.add_argument('--data-version-mode',choices=('current','pinned'),default='current')
            child.add_argument('--maintenance-only',action='store_true',help='명시적으로 discovery를 제외한 기존 의존 관계만 처리')
            child.add_argument('--realm-id',type=request_id,action='append',help='자동 전파의 Realm; 생략하면 시작 실행의 단일 Realm')
            child.add_argument('--allow-cross-realm',action='store_true',help='선택한 여러 Realm의 이번 자동 전파를 명시')
            child.add_argument('--realm-database',help='trusted Realm catalog DB 이름')
            child.add_argument('--provider',choices=('local-glm','codex-terra'),default='local-glm')
        elif name in ('advance','accept','renew','call-failed','retry'):
            child.add_argument('task_id',type=request_id)
            if name!='retry': child.add_argument('--lease-token',type=request_id,required=True)
        else:
            child.add_argument('run_id',type=request_id)
        if name=='start':
            child.add_argument('--confirm',type=data_id,required=True)
            child.add_argument('--actor-ref',required=True)
        if name in ('pause','resume','cancel','retry'):
            child.add_argument('--reason',required=True)
            child.add_argument('--actor-ref',default='local')
        if name=='retry': child.add_argument('--acknowledge-anomaly',type=data_id)
        if name in ('next','renew'): child.add_argument('--lease-seconds',type=int,default=180)
        if name in ('accept','call-failed'):
            child.add_argument('--phase',choices=('generator','validator'),required=True)
            child.add_argument('--exchange' if name=='accept' else '--failure',type=Path,required=True)


def run(args,config):
    from .config import select_database
    from .propagation_runtime import PropagationRuntime
    dsn=select_database(config.database_dsn,args.database_name)
    guard=None
    if args.action=='prepare':
        from .realm_automation import configured_guard
        guard=configured_guard(dsn,realm_ids=args.realm_id or (),explicit_cross=args.allow_cross_realm,
            actor=config.actor_ref,database_name=args.realm_database)
    model_profile=None
    if args.action=='prepare' and args.provider=='codex-terra':
        from .codex_provider import PROFILE as model_profile
    service=PropagationRuntime(dsn,config.artifact_root,args.directory,realm_guard=guard,require_realm=True,
        model_profile=model_profile)
    queue=service.queue
    if args.action=='prepare':
        return service.prepare(args.request_id,args.record_id,allowed_data_ids=args.allow_data_id,wiki_ids=args.wiki_id,
            data_version_ids=args.data_version_id,data_version_mode=args.data_version_mode,discovery=not args.maintenance_only)
    if args.action=='start': return queue.start(args.run_id,args.confirm,args.actor_ref)
    if args.action=='show': return queue.show(args.run_id)
    if args.action=='next': return service.next(args.run_id,args.lease_seconds)
    if args.action in ('pause','resume','cancel'): return queue.control(args.run_id,args.action,args.actor_ref,args.reason)
    if args.action=='retry': return service.retry(args.task_id,args.reason,
        acknowledge_anomaly=args.acknowledge_anomaly,actor_ref=args.actor_ref)
    if args.action=='renew': return queue.renew(args.task_id,args.lease_token,args.lease_seconds)
    if args.action=='advance': return service.advance(args.task_id,args.lease_token)
    if args.action=='accept':
        return service.accept(args.task_id,args.lease_token,args.phase,json.loads(args.exchange.read_text(encoding='utf-8')))
    return service.call_failed(args.task_id,args.lease_token,args.phase,json.loads(args.failure.read_text(encoding='utf-8')))
