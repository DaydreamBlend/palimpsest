"""CLI adapter for deterministic W2P and immutable document reads."""

from .data import request_id


def configure(commands, common):
    actions = commands.add_parser('parchment', parents=[common], help='정확한 Wisdom으로 문서 P 구성').add_subparsers(dest='action', required=True)
    compose = actions.add_parser('compose', parents=[common], help='모델 호출 없이 W 문구와 근거를 순서대로 구성')
    compose.add_argument('--request-id', type=request_id, required=True)
    compose.add_argument('--title', required=True)
    compose.add_argument('--wisdom-id', type=request_id, action='append', required=True)
    compose.add_argument('--actor', required=True)
    show = actions.add_parser('show', parents=[common])
    show.add_argument('parchment_id', type=request_id)
    actions.add_parser('list', parents=[common])


def run(args, config):
    from .parchment_runtime import ParchmentRuntime
    service = ParchmentRuntime(config.database_dsn)
    if args.action == 'compose':
        return service.compose(args.request_id, title=args.title, wisdom_ids=args.wisdom_id, actor=args.actor)
    if args.action == 'show':
        return service.parchment(args.parchment_id)
    return service.catalog()
