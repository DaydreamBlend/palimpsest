"""Explicit K2W preparation, delivery and immutable W commands."""
import json
from pathlib import Path

from .data import request_id


def configure(commands, common):
    actions = commands.add_parser('wisdom', parents=[common], help='정확한 K에서 설명·추천 W 생성').add_subparsers(dest='action', required=True)
    prepare = actions.add_parser('prepare', parents=[common], help='호출 없이 Query·Context·현재 K를 고정')
    prepare.add_argument('--request-id', type=request_id, required=True)
    prepare.add_argument('--query', required=True)
    prepare.add_argument('--context', type=Path, required=True, help='당시 사용자 조건 JSON 객체')
    prepare.add_argument('--revision-id', type=request_id, action='append', default=[])
    prepare.add_argument('--edge-revision-id', type=request_id, action='append', default=[])
    prepare.add_argument('--kind', choices=('explanation', 'recommendation'), default='explanation')
    actions.add_parser('get', parents=[common]).add_argument('wisdom_id', type=request_id)
    for action in ('show', 'request', 'stage', 'validate', 'commit'):
        child = actions.add_parser(action, parents=[common])
        child.add_argument('execution_id', type=request_id)
        if action == 'request':
            child.add_argument('--phase', choices=('generator', 'validator'), required=True)
            child.add_argument('--directory', type=Path, required=True)
        elif action in ('stage', 'validate'):
            child.add_argument('--response', type=Path, required=True, help='response와 실제 delivery receipt를 담은 JSON')


def run(args, config):
    from .wisdom_runtime import WisdomRuntime
    runtime = WisdomRuntime(config.database_dsn)
    if args.action == 'prepare':
        return runtime.prepare(args.request_id, query=args.query,
            context_snapshot=json.loads(args.context.read_text(encoding='utf-8')),
            revision_ids=args.revision_id, edge_revision_ids=args.edge_revision_id, wisdom_kind=args.kind)
    if args.action == 'get':
        return runtime.wisdom(args.wisdom_id)
    if args.action == 'show':
        return runtime.show(args.execution_id)
    if args.action == 'request':
        return runtime.prepare_call(args.execution_id, args.phase, args.directory)
    if args.action == 'commit':
        return runtime.commit(args.execution_id)
    payload = json.loads(args.response.read_text(encoding='utf-8'))
    return getattr(runtime, args.action)(args.execution_id, payload['response'], payload['receipt'])
