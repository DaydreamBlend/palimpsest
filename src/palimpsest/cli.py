"""Thin, noninteractive adapters for Data and Compiler Runtime services."""

import argparse
from datetime import date, datetime
import json
from pathlib import Path
import re
import sys
import unicodedata
from uuid import UUID

from . import __version__
from .config import load_config, load_dsn, select_database
from .data import data_id, request_id
from .errors import PalimpsestError


class _OutputRequested(Exception):
    def __init__(self, result):
        self.result = result


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse errors may contain arbitrary argument values, including secrets.
        raise PalimpsestError("invalid_arguments", "명령과 인자를 확인하세요. palim --help로 사용법을 볼 수 있습니다.", 2)

    def print_help(self, file=None):
        raise _OutputRequested({"help": self.format_help()})


class _VersionAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        raise _OutputRequested({"version": __version__})


def _parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="JSON 결과 출력")
    common.add_argument("--non-interactive", action="store_true", default=argparse.SUPPRESS, help="대화형 입력 없이 실행")
    common.add_argument("--version", action=_VersionAction, nargs=0, help="버전 출력")
    parser = _Parser(prog="palim", parents=[common], description="Palimpsest 원본 등록·조회 CLI")
    commands = parser.add_subparsers(dest="command")
    from .d2k_cli import configure as configure_d2k
    configure_d2k(commands,common)
    from .propagation_cli import configure as configure_propagation
    configure_propagation(commands,common)
    from .wisdom_cli import configure as configure_wisdom
    configure_wisdom(commands,common)
    from .parchment_cli import configure as configure_parchment
    configure_parchment(commands,common)
    commands.add_parser("doctor", parents=[common], help="저장소 준비 상태 진단")
    code = commands.add_parser('code', parents=[common], help='원문 코드의 Markdown snapshot·위치·복원 도구')
    code_actions = code.add_subparsers(dest='action', required=True)
    snapshot = code_actions.add_parser('snapshot', parents=[common])
    snapshot.add_argument('root', type=Path)
    snapshot.add_argument('directory', type=Path)
    snapshot.add_argument('--include', action='append', help='명시적으로 포함할 root 상대 파일 경로')
    for action in ('verify', 'locate', 'restore'):
        child = code_actions.add_parser(action, parents=[common])
        child.add_argument('directory', type=Path)
        if action == 'verify':
            child.add_argument('--data-id', type=data_id)
        elif action == 'locate':
            ranges = child.add_mutually_exclusive_group(required=True)
            ranges.add_argument('--byte-range', nargs=2, type=int)
            ranges.add_argument('--char-range', nargs=2, type=int)
        else:
            child.add_argument('target', type=Path)
    data = commands.add_parser("data", parents=[common], help="Data 등록·조회·검증")
    data_commands = data.add_subparsers(dest="action", required=True)
    register = data_commands.add_parser("import", parents=[common], help="원본을 복사하여 등록")
    register.add_argument("path", type=Path)
    register.add_argument("--request-id", type=request_id)
    register.add_argument("--media-type")
    register.add_argument("--origin-uri")
    register_snapshot = data_commands.add_parser('import-code-snapshot', parents=[common], help='검증된 코드 dossier를 저장·등록')
    register_snapshot.add_argument('directory', type=Path)
    register_snapshot.add_argument('--request-id', type=request_id)
    for child in (register, register_snapshot):
        child.add_argument('--realm-id', type=request_id, help='신규 Data 등록 시 반드시 선택할 Realm')
        child.add_argument('--realm-reason', default='자료 등록', help='최초 분류의 이유')
        child.add_argument('--realm-database', help='trusted Realm catalog DB 이름')
    for action in ("show", "verify", "storage-stats"):
        child = data_commands.add_parser(action, parents=[common])
        child.add_argument("data_id", type=data_id)
    create_series = data_commands.add_parser('series-create', parents=[common], help='새 자료 버전 이력 생성')
    create_series.add_argument('name')
    create_series.add_argument('--request-id', type=request_id)
    for action in ('series-show', 'series-history'):
        data_commands.add_parser(action, parents=[common]).add_argument('series_id', type=request_id)
    append_version = data_commands.add_parser('series-append', parents=[common], help='현재 head를 확인하고 등록 Data의 새 버전 추가')
    append_version.add_argument('series_id', type=request_id)
    append_version.add_argument('data_id', type=data_id)
    append_version.add_argument('--request-id', type=request_id, required=True)
    append_version.add_argument('--expected-head', type=request_id, help='조회한 현재 version ID; 생략은 빈 이력만 허용')
    append_version.add_argument('--title', default='')
    append_version.add_argument('--message', default='')
    data_commands.add_parser('version', parents=[common]).add_argument('version_id', type=request_id)
    compare_versions = data_commands.add_parser('compare-code-versions', parents=[common], help='저장된 두 코드 dossier 버전의 파일 hash 비교')
    compare_versions.add_argument('before_version', type=request_id)
    compare_versions.add_argument('after_version', type=request_id)
    restore_version = data_commands.add_parser('restore-code-version', parents=[common], help='저장된 코드 버전의 원문 파일을 빈 폴더로 복원')
    restore_version.add_argument('version_id', type=request_id)
    restore_version.add_argument('directory', type=Path)
    requests = commands.add_parser("requests", parents=[common], help="등록 요청 조회·복구")
    request_commands = requests.add_subparsers(dest="action", required=True)
    for action in ("show", "recover"):
        child = request_commands.add_parser(action, parents=[common])
        child.add_argument("request_id", type=request_id)
        child.add_argument('--realm-database', help='Realm 연결 대기 요청의 catalog DB 이름')
    database = commands.add_parser("db", parents=[common], help="명시적 스키마 설치")
    migration = database.add_subparsers(dest="action", required=True).add_parser("migrate", parents=[common])
    migration.add_argument('--database-name', help='기존 credential로 접속할 DB를 명시')
    compile_command = commands.add_parser('compile', parents=[common], help='Data compilation 실행 준비')
    compile_actions = compile_command.add_subparsers(dest='action', required=True)
    prepare = compile_actions.add_parser('data', parents=[common])
    prepare.add_argument('data_id', type=data_id)
    prepare.add_argument('--profile', type=Path, required=True)
    prepare.add_argument('--generation', type=int, default=1)
    regroup = compile_actions.add_parser('regroup', parents=[common], help='완료된 원문 실행을 새 그룹 I로 저장')
    regroup.add_argument('--execution-id', type=request_id, required=True)
    source_pages = compile_actions.add_parser('source-pages', parents=[common], help='원본 페이지 이미지 I를 추가한 새 source 실행')
    source_pages.add_argument('--execution-id', type=request_id, required=True)
    source_pages.add_argument('--directory', type=Path, required=True)
    markdown = compile_actions.add_parser('markdown', parents=[common], help='등록된 Markdown을 그룹 I로 저장')
    markdown.add_argument('data_id', type=data_id)
    markdown.add_argument('--generation', type=int, default=1)
    code = compile_actions.add_parser('code', parents=[common], help='등록 코드 snapshot을 Python 문법 기반 I로 저장')
    code.add_argument('data_id', type=data_id)
    code.add_argument('--generation', type=int, default=1)
    jobs = commands.add_parser('jobs', parents=[common], help='실행 조회 및 worker 단계 반영')
    stages = jobs.add_subparsers(dest='action', required=True)
    for action in ('show','retry','parsed','materialize','fail','export-parser','hold'):
        child = stages.add_parser(action, parents=[common])
        child.add_argument('execution_id', type=request_id)
        if action == 'show':
            child.add_argument('--include-input', action='store_true', help='worker 복구용 원문·임시 후보 포함')
        elif action == 'parsed':
            child.add_argument('--directory', type=Path, required=True)
            child.add_argument('--raw', '--middle', dest='middle', required=True,
                               help='Retained parser entry JSON filename')
            child.add_argument('--expected-pages', type=int, required=True)
        elif action == 'fail':
            child.add_argument('--code', required=True)
        elif action == 'export-parser':
            child.add_argument('--directory',type=Path,required=True)
    information = commands.add_parser('information', parents=[common], help='검증된 Information 조회')
    reads = information.add_subparsers(dest='action', required=True)
    reads.add_parser('show', parents=[common]).add_argument('information_id', type=request_id)
    reads.add_parser('list', parents=[common]).add_argument('--data-id', type=data_id, required=True)
    for action in ('reconstruct', 'locate', 'locate-information', 'export-source'):
        child = reads.add_parser(action, parents=[common], help='양방향 원문 대응·원본 복원')
        child.add_argument('--execution-id', type=request_id, required=True)
        if action == 'locate':
            child.add_argument('--page', type=int)
            child.add_argument('--bbox', type=float, nargs=4)
            child.add_argument('--byte-range', type=int, nargs=2)
            child.add_argument('--line-range', type=int, nargs=2)
        if action == 'locate-information':
            child.add_argument('--information-id', type=request_id, required=True)
            child.add_argument('--char-range', type=int, nargs=2)
        if action == 'export-source':
            child.add_argument('--destination', type=Path, required=True)
    for action in ('prepare-input', 'prepare-source'):
        child = reads.add_parser(action, parents=[common], help='I2K 입력·원본 요청의 로컬 준비 (모델 전송 없음)')
        child.add_argument('--execution-id', type=request_id, required=True)
        child.add_argument('--information-id', type=request_id, action='append', dest='information_ids')
        child.add_argument('--directory', type=Path, help='같은 source bundle의 검증된 PDF evidence')
        child.add_argument('--section-id', help='sections 조회 결과의 절 식별자')
        child.add_argument('--projection-sha256', help='같은 execution으로 조회한 sections SHA-256')
        if action == 'prepare-source':
            child.add_argument('--request', type=Path, required=True, help='input SHA에 결속한 원본 확인 요청 JSON')
    evidence = reads.add_parser('evidence-context', parents=[common], help='원문 보완 projection의 인접 페이지 조회')
    evidence.add_argument('--directory', type=Path, required=True)
    evidence.add_argument('--page', type=int, required=True, help='원본 물리 페이지 번호 (1부터)')
    for action in ('sections', 'section-context', 'document-context'):
        child = reads.add_parser(action, parents=[common], help='원문 보존 절 읽기 projection 조회')
        child.add_argument('--directory', type=Path, required=True)
        child.add_argument('--execution-id', type=request_id, help='완료된 단일 source 실행의 I와 결속')
        if action == 'section-context':
            child.add_argument('--section-id', required=True, help='sections 결과의 projection 내부 식별자')
        if action in ('section-context', 'document-context'):
            child.add_argument('--projection-sha256', required=True, help='sections 결과의 정확한 projection SHA-256')
    for action in ('pages', 'context'):
        child = reads.add_parser(action, parents=[common])
        child.add_argument('--execution-id', type=request_id, required=True)
        if action == 'context':
            child.add_argument('--page', type=int, required=True, help='원본의 물리 페이지 번호 (1부터)')
    knowledge = commands.add_parser('knowledge', parents=[common], help='I2K/N2E/K2K 준비·검증·Revision graph 조회')
    actions = knowledge.add_subparsers(dest='action', required=True)
    combine = actions.add_parser('combine-inputs', parents=[common], help='검증된 여러 source 입력 JSON을 하나의 I2K 입력으로 결합')
    combine.add_argument('inputs', nargs='+', type=Path)
    prepare = actions.add_parser('prepare', parents=[common])
    prepare.add_argument('--operation', choices=('i2k', 'n2e', 'k2k'), required=True)
    prepare.add_argument('--data-id', type=data_id, required=True)
    prepare.add_argument('--request-id', type=request_id, required=True)
    prepare.add_argument('--input', type=Path, required=True)
    prepare.add_argument('--realm-id', type=request_id, action='append', help='새 I2K의 Realm; 여러 Realm은 명시적 교차 선택 필요')
    prepare.add_argument('--allow-cross-realm', action='store_true', help='선택한 여러 Realm의 이번 I2K 결합을 명시')
    prepare.add_argument('--realm-database', help='trusted 연결의 Realm catalog DB 이름; 기본 palimpsest_realms')
    prepare.add_argument('--selection', action='store_true', help='전체 source I를 LLM이 검토·선택하는 I2K profile')
    prepare.add_argument('--feedback-execution-id', type=request_id, help='같은 source의 이전 선택 검토 결과를 새 실행에 반영')
    prepare.add_argument('--target-knode-id', type=request_id, help='명시적으로 의미 개정을 검토할 기존 K; expected-revision-id와 함께 사용')
    prepare.add_argument('--expected-revision-id', type=request_id, help='비교 기준인 K의 정확한 현재 revision; I2K/K2K만 지원')
    prepare.add_argument('--data-version-id', type=request_id, action='append', help='입력의 정확한 자료 버전; 반복 가능')
    prepare.add_argument('--data-version-mode', choices=('current', 'pinned'), default='current',
                         help='current는 반영 시 head 재확인, pinned는 명시적 과거·비교 범위')
    inference = actions.add_parser('inference-input', parents=[common], help='현재 KRevision을 정확한 추론 입력으로 고정')
    inference.add_argument('--data-id', type=data_id, required=True)
    inference.add_argument('--node-revision-id', type=request_id, action='append', default=[])
    inference.add_argument('--edge-revision-id', type=request_id, action='append', help='정확한 현재 Edge와 양 endpoint를 K2K 전제로 포함')
    inference_call = actions.add_parser('inference-call', parents=[common], help='K2K 생성·독립 검증의 정확한 전송 요청 저장')
    inference_call.add_argument('execution_id', type=request_id)
    inference_call.add_argument('--phase', choices=('generator', 'validator'), required=True)
    inference_call.add_argument('--directory', type=Path, required=True)
    edge_input = actions.add_parser('edge-input', parents=[common], help='현재 accepted KRevision으로 N2E 입력 구성')
    edge_input.add_argument('--data-id', type=data_id, required=True)
    edge_input.add_argument('--node-revision-id', type=request_id, action='append', required=True)
    edge_review = actions.add_parser('edge-revalidate', parents=[common], help='기존 Edge의 현재 적용성·관계 의미 재검토')
    edge_review.add_argument('--edge-revision-id', type=request_id, required=True)
    edge_review.add_argument('--request-id', type=request_id, required=True)
    edge_review.add_argument('--data-id', type=data_id)
    edge_review.add_argument('--data-version-id', type=request_id, action='append')
    edge_review.add_argument('--data-version-mode', choices=('current', 'pinned'), default='current')
    edge_call = actions.add_parser('edge-call', parents=[common], help='N2E 생성·독립 검증의 정확한 전송 요청 저장')
    edge_call.add_argument('execution_id', type=request_id)
    edge_call.add_argument('--phase', choices=('generator', 'validator'), required=True)
    edge_call.add_argument('--directory', type=Path, required=True)
    for action in ('show', 'stage', 'decide', 'validation-context', 'call-failed', 'dispatch-failed', 'fail', 'review-status', 'review-resume', 'review-call', 'revision-call', 'source-issues'):
        child = actions.add_parser(action, parents=[common])
        child.add_argument('execution_id', type=request_id)
        if action == 'review-resume':
            child.add_argument('--request-id', type=request_id, required=True)
            child.add_argument('--realm-id', type=request_id, action='append', help='기존 scope가 없는 새 I2K 검토의 Realm')
            child.add_argument('--allow-cross-realm', action='store_true')
            child.add_argument('--realm-database')
        if action in ('review-call', 'revision-call'):
            child.add_argument('--phase', choices=('generator', 'validator'), required=True)
            child.add_argument('--directory', type=Path, required=True)
        if action in ('stage', 'decide', 'call-failed','dispatch-failed'):
            child.add_argument('--response', type=Path, required=True,
                               help='worker의 response와 실제 호출 receipt JSON')
        if action in ('stage', 'decide'):
            child.add_argument('--realm-database', help='보존된 scope의 Realm catalog DB 이름')
        if action == 'call-failed':
            child.add_argument('--phase', choices=('generator', 'validator'), required=True)
            child.add_argument('--code', required=True)
        if action == 'dispatch-failed':
            child.add_argument('--phase',choices=('generator','validator'),required=True)
        if action == 'fail':
            child.add_argument('--code', required=True)
    graph = actions.add_parser('graph', parents=[common])
    graph.add_argument('--data-id', type=data_id)
    graph.add_argument('--data-version-id', type=request_id)
    wiki = commands.add_parser('wiki', parents=[common], help='논문·주제 Wiki 읽기 projection 생성·검증·내보내기')
    wiki_actions = wiki.add_subparsers(dest='action', required=True)
    for action in ('prepare', 'request', 'stage', 'decide', 'show', 'catalog', 'history', 'export', 'call-failed'):
        child = wiki_actions.add_parser(action, parents=[common])
        child.add_argument('--directory', type=Path, required=True, help='도구가 관리하는 비canonical Wiki 저장 폴더')
        if action in ('prepare', 'request', 'stage', 'decide', 'show', 'call-failed'):
            child.add_argument('--request-id', type=request_id, required=True)
        if action == 'prepare':
            child.add_argument('--execution-id', type=request_id, required=True)
            child.add_argument('--metadata', type=Path, required=True, help='title/filename/선택 doi JSON')
            child.add_argument('--feedback-request-id', type=request_id)
            child.add_argument('--review-notes', type=Path, help='이전 요청의 추가 검토 지적 JSON 문자열 목록')
            child.add_argument('--citation-repair', action='store_true', help='본문·주제·기존 인용을 보존하며 근거만 추가')
            child.add_argument('--repair-item', action='append', help='repair에서 명시한 item의 문구 수정도 허용; 반복 가능')
        if action in ('request', 'call-failed'):
            child.add_argument('--phase', choices=('generator', 'validator'), required=True)
        if action in ('stage', 'decide', 'call-failed'):
            child.add_argument('--response', type=Path, required=True)
        if action == 'show':
            child.add_argument('--include-input', action='store_true')
        if action == 'history':
            child.add_argument('--page-id', type=request_id, required=True)
        if action == 'export':
            child.add_argument('--catalog-sha256', type=data_id)
    for action in ('database-sync', 'database-catalog', 'database-history', 'database-related',
                   'database-restore', 'database-export'):
        child = wiki_actions.add_parser(action, parents=[common])
        child.add_argument('--wiki-id', type=request_id, required=True)
        child.add_argument('--database-name', help='기존 credential로 접속할 DB를 명시')
        if action in ('database-sync', 'database-restore', 'database-export'):
            child.add_argument('--directory', type=Path, required=True)
        if action == 'database-sync':
            child.add_argument('--request-id', type=request_id, required=True)
            child.add_argument('--expected-head', type=request_id)
            child.add_argument('--review-annotations', type=Path)
        else:
            child.add_argument('--import-id', type=request_id)
        if action in ('database-history', 'database-related'):
            child.add_argument('--page-id', type=request_id, required=True)
        if action == 'database-related':
            child.add_argument('--include-review-required', action='store_true')
        if action == 'database-export':
            child.add_argument('--catalog-sha256', type=data_id)
    for action in ('retrieval-prepare', 'retrieval-install', 'query-prepare', 'query-search',
                   'query-context', 'query-request', 'query-stage', 'query-source', 'query-decide', 'query-show', 'query-revise', 'query-pause'):
        child = wiki_actions.add_parser(action, parents=[common])
        child.add_argument('--directory', type=Path, required=True)
        child.add_argument('--database-name')
        if action in ('retrieval-prepare', 'retrieval-install', 'query-prepare'):
            child.add_argument('--index-id', type=request_id, required=True)
        if action == 'retrieval-prepare':
            child.add_argument('--wiki-id', type=request_id, required=True)
            child.add_argument('--include-data-id', type=data_id, action='append', default=None)
        if action.startswith('query-'):
            child.add_argument('--request-id', type=request_id, required=True)
        if action == 'query-prepare':
            child.add_argument('--question', required=True)
        if action in ('retrieval-install', 'query-search'):
            child.add_argument('--embedding', type=Path, required=True)
        if action == 'query-context':
            child.add_argument('--rerank', type=Path, required=True)
        if action == 'query-request':
            child.add_argument('--phase', choices=('generator', 'validator'), required=True)
        if action in ('query-stage', 'query-decide'):
            child.add_argument('--response', type=Path, required=True)
        if action == 'query-revise':
            child.add_argument('--review-notes', type=Path)
        if action == 'query-pause':
            child.add_argument('--reason', required=True)
    return parser


def _wiki(args, config):
    if args.action.startswith(('retrieval-', 'query-')):
        return _wiki_query(args, config)
    if args.action.startswith('database-'):
        return _wiki_database(args, config)
    from .paper_wiki_runtime import PaperWikiRuntime
    runtime = PaperWikiRuntime(config.database_dsn, config.artifact_root, args.directory)
    if args.action == 'prepare':
        result = runtime.prepare(args.execution_id, args.request_id,
            json.loads(args.metadata.read_text(encoding='utf-8')), feedback_request_id=args.feedback_request_id,
            review_notes=json.loads(args.review_notes.read_text(encoding='utf-8')) if args.review_notes else None,
            citation_repair=args.citation_repair, editable_item_keys=args.repair_item)
        return {key: result[key] for key in ('request_id', 'state', 'source_data_id', 'source_execution_id',
                                            'input_digest', 'canonical_writes', 'replayed')}
    if args.action == 'request':
        return runtime.model_request(args.request_id, args.phase)
    if args.action == 'catalog':
        return runtime.catalog()
    if args.action == 'history':
        return runtime.history(args.page_id)
    if args.action == 'export':
        return runtime.export(catalog_sha256=args.catalog_sha256)
    if args.action == 'show':
        result = runtime.show(args.request_id)
        if not args.include_input:
            result.pop('input_snapshot', None)
        return result
    exchange = json.loads(args.response.read_text(encoding='utf-8'))
    if args.action == 'call-failed':
        return runtime.call_failed(args.request_id, args.phase, exchange['failure'])
    if args.action == 'stage':
        result = runtime.stage(args.request_id, exchange)
        return {'request_id': args.request_id, 'state': runtime.show(args.request_id)['state'],
                'items': len(result['proposal']['items']), 'topics': len(result['proposal']['topics'])}
    return runtime.decide(args.request_id, exchange)


def _wiki_query(args, config):
    from .wiki_query_runtime import WikiQueryRuntime
    runtime = WikiQueryRuntime(select_database(config.database_dsn, args.database_name), config.artifact_root, args.directory)
    if args.action == 'retrieval-prepare':
        return runtime.prepare_index(args.wiki_id, args.index_id, include_data_ids=args.include_data_id)
    if args.action == 'retrieval-install':
        return runtime.install_index(args.index_id, json.loads(args.embedding.read_text(encoding='utf-8')))
    if args.action == 'query-prepare':
        return runtime.prepare(args.index_id, args.request_id, args.question)
    if args.action == 'query-search':
        return runtime.search(args.request_id, json.loads(args.embedding.read_text(encoding='utf-8')))
    if args.action == 'query-context':
        return runtime.context(args.request_id, json.loads(args.rerank.read_text(encoding='utf-8')))
    if args.action == 'query-request':
        return runtime.model_request(args.request_id, args.phase)
    if args.action == 'query-stage':
        return runtime.stage(args.request_id, json.loads(args.response.read_text(encoding='utf-8')))
    if args.action == 'query-source':
        return runtime.source_pages(args.request_id)
    if args.action == 'query-decide':
        return runtime.decide(args.request_id, json.loads(args.response.read_text(encoding='utf-8')))
    if args.action == 'query-revise':
        return runtime.revise(args.request_id, json.loads(args.review_notes.read_text(encoding='utf-8')) if args.review_notes else None)
    if args.action == 'query-pause':
        return runtime.pause(args.request_id, args.reason)
    return runtime.show(args.request_id)


def _wiki_database(args, config):
    from .wiki_database import WikiDatabase
    runtime = WikiDatabase(select_database(config.database_dsn, args.database_name), config.artifact_root)
    if args.action == 'database-sync':
        annotations = json.loads(args.review_annotations.read_text(encoding='utf-8')) if args.review_annotations else None
        return runtime.sync(args.wiki_id, args.request_id, args.directory,
                            expected_head=args.expected_head, review_annotations=annotations)
    options = {'import_id': args.import_id}
    if args.action == 'database-catalog':
        return runtime.catalog(args.wiki_id, **options)
    if args.action == 'database-history':
        return runtime.history(args.wiki_id, args.page_id, **options)
    if args.action == 'database-related':
        return runtime.related(args.wiki_id, args.page_id, include_review_required=args.include_review_required, **options)
    if args.action == 'database-restore':
        return runtime.restore(args.wiki_id, args.directory, **options)
    return runtime.export(args.wiki_id, args.directory, catalog_sha256=args.catalog_sha256, **options)


def _knowledge(args, config):
    if args.action == 'combine-inputs':
        from .multi_source_i2k import combine_packets
        return combine_packets([json.loads(path.read_text(encoding='utf-8')) for path in args.inputs])
    from .knowledge_runtime import KnowledgeRuntime
    from .realm_i2k import configured_guard, execution_guard_configured
    selected_realms = getattr(args, 'realm_id', None) or []
    explicit_cross = getattr(args, 'allow_cross_realm', False)
    if args.action == 'prepare' and args.operation != 'i2k' and (selected_realms or explicit_cross):
        raise PalimpsestError('invalid_realm_operation', '이 Realm 입력 제한은 I2K에만 적용됩니다.', 2)
    guard = None
    if args.action == 'review-resume' or (args.action == 'prepare' and args.operation == 'i2k'):
        guard = configured_guard(config.database_dsn, realm_ids=selected_realms, explicit_cross=explicit_cross,
                                 actor=getattr(config, 'actor_ref', 'local'), database_name=getattr(args, 'realm_database', None))
    elif args.action in ('stage', 'decide'):
        guard = execution_guard_configured(config.database_dsn, args.execution_id,
            actor=getattr(config, 'actor_ref', 'local'), database_name=getattr(args, 'realm_database', None))
    runtime = KnowledgeRuntime(config.database_dsn, realm_guard=guard, require_realm=True)
    if args.action == 'inference-call':
        from .k2k_effective_runtime import prepare_call
        return prepare_call(runtime, args.execution_id, args.phase, args.directory)
    if args.action in ('edge-input', 'edge-revalidate', 'edge-call'):
        from . import n2e_runtime
        if args.action == 'edge-input':
            return n2e_runtime.input_packet(runtime, args.data_id, args.node_revision_id)
        if args.action == 'edge-call':
            return n2e_runtime.prepare_call(runtime, args.execution_id, args.phase, args.directory)
        return n2e_runtime.prepare_review(runtime, args.edge_revision_id, args.request_id, data_id=args.data_id,
            data_version_ids=args.data_version_id, data_version_mode=args.data_version_mode)
    if args.action == 'revision-call':
        from .knowledge_revision_runtime import prepare_call
        from .artifact_store import ArtifactStore
        return prepare_call(runtime, args.execution_id, args.phase, args.directory,
                            ArtifactStore(config.artifact_root / 'derived'))
    if args.action in ('review-status', 'review-resume', 'review-call', 'source-issues'):
        from .knowledge_review import KnowledgeReview
        review = KnowledgeReview(runtime)
        if args.action == 'source-issues':
            from .information_errors import report
            return report(runtime.show(args.execution_id))
        if args.action == 'review-call':
            from .artifact_store import ArtifactStore
            return review.prepare_call(args.execution_id, args.phase, args.directory,
                                       ArtifactStore(config.artifact_root/'derived'))
        return (review.status(args.execution_id) if args.action == 'review-status'
                else review.prepare_resume(args.execution_id, args.request_id))
    if args.action == 'inference-input':
        return runtime.inference_input(args.data_id, args.node_revision_id, edge_revision_ids=args.edge_revision_id)
    if args.action == 'prepare':
        packet = json.loads(args.input.read_text(encoding='utf-8'))
        if args.operation == 'i2k' and isinstance(packet, dict) and packet.get('schema_version') == 'i2k-input-v1':
            from .multi_source_i2k import PROFILE, combine_packets
            # New single-document work uses the same source-explicit contract.
            # Rebuild that wrapper on retry, while preserving old request bytes.
            if runtime.request_profile(args.request_id) in (None, PROFILE):
                packet = combine_packets([packet])
        versions = ({'data_version_ids': args.data_version_id, 'data_version_mode': args.data_version_mode}
                    if args.data_version_id is not None or args.data_version_mode != 'current' else {})
        revision = ({'target_knode_id': args.target_knode_id, 'expected_revision_id': args.expected_revision_id}
                    if args.target_knode_id is not None or args.expected_revision_id is not None else {})
        return runtime.prepare(args.operation, args.data_id, args.request_id,
                               packet, selection=True if args.selection else None,
                               feedback_execution_id=args.feedback_execution_id, **versions, **revision)
    if args.action == 'graph':
        return runtime.graph(args.data_id, **({'data_version_id': args.data_version_id} if args.data_version_id else {}))
    if args.action == 'show':
        return runtime.show(args.execution_id)
    if args.action == 'validation-context':
        return runtime.validation_context(args.execution_id)
    if args.action == 'fail':
        return runtime.fail_execution(args.execution_id, args.code)
    payload = json.loads(args.response.read_text(encoding='utf-8'))
    if args.action == 'dispatch-failed':
        return runtime.record_dispatch_failure(args.execution_id,args.phase,payload['failure'])
    if args.action == 'call-failed':
        return runtime.record_call_failure(args.execution_id, args.phase, payload['receipt'], args.code,
                                           response=payload['response'])
    if args.action == 'stage':
        return runtime.stage(args.execution_id, payload['response'], payload['receipt'])
    return runtime.decide(args.execution_id, payload['response'], payload['receipt'])


def _service(config):
    # Help/version/config diagnostics remain usable without a database driver.
    from .artifact_store import ArtifactStore
    from .canonical_store import PostgresRepository
    from .service import DataService

    return DataService(PostgresRepository(config.database_dsn), ArtifactStore(config.artifact_root), config.actor_ref)


def _registration_service(service, args, config):
    from .realm_registration import configured_service, registration
    identifier = getattr(args, 'request_id', None)
    row = service.repository.get_request(identifier) if identifier else None
    if args.command == 'requests':
        if registration(row) is None:
            return service
    elif getattr(args, 'realm_id', None) is None:
        # An existing old request replays its actual unscoped contract. A fresh
        # product registration cannot acquire that compatibility exception.
        if isinstance(row, dict) and row and registration(row) is None:
            return service
        raise PalimpsestError('realm_required', '자료를 등록하기 전에 --realm-id로 Realm을 선택하세요.', 2)
    return configured_service(service, config.database_dsn, database_name=getattr(args, 'realm_database', None))


def _migrate(admin_dsn):
    from .canonical_store import migrate

    return migrate(admin_dsn)


def _data_versions(args, config):
    from .data_versions import DataVersions
    from .artifact_store import ArtifactStore
    store = ArtifactStore(config.artifact_root) if args.action == 'series-append' else None
    versions = DataVersions(config.database_dsn, store)
    if args.action == 'series-create':
        return versions.create(args.name, args.request_id, actor_ref=config.actor_ref)
    if args.action == 'series-append':
        return versions.append(args.series_id, args.data_id, args.request_id, args.expected_head,
                               message=args.message, title=args.title, actor_ref=config.actor_ref)
    if args.action == 'version':
        return versions.version(args.version_id)
    if args.action in ('compare-code-versions', 'restore-code-version'):
        from . import code_snapshot
        service = _service(config)
        identifiers = ([args.before_version, args.after_version] if args.action == 'compare-code-versions'
                       else [args.version_id])
        stored = []
        for identifier in identifiers:
            version = versions.version(identifier)
            row = service.show(version['data_id'])
            raw = service.artifact_store.read(version['data_id'], row['byte_size'])
            stored.append((version, raw))
        if args.action == 'compare-code-versions':
            return {**code_snapshot.compare(stored[0][1], stored[1][1]),
                    'before_version': stored[0][0], 'after_version': stored[1][0]}
        version, raw = stored[0]
        return {**code_snapshot.restore_bytes(raw, args.directory, expected_sha256=version['data_id']),
                'data_version': version, 'version_id': version['version_id'], 'data_id': version['data_id']}
    return getattr(versions, 'show' if args.action == 'series-show' else 'history')(args.series_id)


def _compile(args, config):
    from .compiler_runtime import CompilerRuntime
    runtime = CompilerRuntime(config.database_dsn, config.artifact_root)
    if args.command == 'compile':
        if args.action == 'source-pages':
            return runtime.add_source_pages(args.execution_id, args.directory)
        if args.action == 'markdown':
            return runtime.compile_markdown(args.data_id, generation=args.generation)
        if args.action == 'code':
            return runtime.compile_code(args.data_id, generation=args.generation)
        if args.action == 'regroup':
            return runtime.regroup_source(args.execution_id)
        profile = json.loads(args.profile.read_text(encoding='utf-8'))
        if profile.get('schema_version') != 'source-d2i-v1':
            raise PalimpsestError('llm_d2i_disabled', 'D2I는 원문 보존용 source profile을 요구합니다.', 2)
        return runtime.start(args.data_id, profile, args.generation)
    if args.command == 'information':
        if args.action == 'reconstruct':
            return runtime.reconstruct_source(args.execution_id)
        if args.action == 'locate':
            return runtime.lookup_source(args.execution_id, page_number=args.page, bbox=args.bbox,
                                         byte_range=args.byte_range, line_range=args.line_range)
        if args.action == 'locate-information':
            return runtime.locate_information(args.execution_id, args.information_id, char_range=args.char_range)
        if args.action == 'export-source':
            return runtime.export_source(args.execution_id, args.destination)
        if args.action in ('prepare-input', 'prepare-source'):
            selection = {'information_ids':args.information_ids, 'directory':args.directory,
                         'section_id':args.section_id, 'expected_projection_sha256':args.projection_sha256}
            if args.action == 'prepare-input':
                return runtime.prepare_input(args.execution_id, **selection)
            from .pdf_evidence import read_json
            if args.request.stat().st_size > 65536:
                raise PalimpsestError('invalid_source_request', '원본 요청 JSON의 크기를 확인하세요.', 2)
            return runtime.prepare_source(args.execution_id, read_json(args.request), **selection)
        if args.action in ('sections', 'section-context', 'document-context'):
            return runtime.section_view(args.execution_id, args.directory,
                section_id=args.section_id if args.action == 'section-context' else None,
                expected_projection_sha256=args.projection_sha256 if args.action != 'sections' else None,
                whole_document=args.action == 'document-context')
        if args.action in ('pages', 'context'):
            return runtime.page_view(args.execution_id, page_number=args.page if args.action=='context' else None)
        return runtime.information(information_id=args.information_id) if args.action == 'show' else runtime.information(data_id=args.data_id)
    if args.action == 'show':
        return runtime.show(args.execution_id, include_input=args.include_input)
    if args.action == 'parsed':
        return runtime.attach_parser(args.execution_id, args.directory, args.middle, args.expected_pages)
    if args.action == 'retry':
        return runtime.retry(args.execution_id)
    if args.action == 'materialize':
        return runtime.materialize_source(args.execution_id)
    if args.action == 'export-parser':
        return runtime.export_parser(args.execution_id,args.directory)
    if args.action == 'hold':
        from .worker_claim import hold_claim
        hold_claim(config.database_dsn,args.execution_id,
                   lambda: _emit(_envelope({'execution_id':args.execution_id,'state':'claimed'}),True))
        return {'execution_id':args.execution_id,'state':'released'}
    if args.action == 'fail':
        return runtime.mark_failed(args.execution_id, args.code)
    raise PalimpsestError('invalid_arguments', '지원하지 않는 작업입니다.', 2)


def _json_value(value):
    if isinstance(value, (date, datetime, UUID, Path)):
        return value.isoformat() if isinstance(value, (date, datetime)) else str(value)
    raise TypeError("Unsupported result type")


def _safe_json(value, *, indent=None):
    rendered = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=indent, default=_json_value)
    # JSON already escapes C0 controls; escape C1, bidi and surrogate controls too.
    return "".join(json.dumps(char, ensure_ascii=True)[1:-1]
                   if unicodedata.category(char) in {"Cc", "Cf", "Cs"} and char != "\n"
                   else char for char in rendered)


def _request_started(value):
    print(_safe_json({"schema_version": 1, "event": "request_started", "request_id": request_id(value)}),
          file=sys.stderr, flush=True)


def _refs(result):
    if not isinstance(result, dict):
        return {}
    return {key: result[key] for key in ("data_id", "request_id", "acquisition_id", "execution_id", "information_id",
                                        "series_id", "version_id") if result.get(key) is not None}


def _envelope(result=None, *, error=None, warnings=None):
    return {"schema_version": 1, "command_status": "failed" if error else "succeeded",
            "job_status": result.get('state') if isinstance(result,dict) and (result.get('execution_id') or result.get('query_id')) else None,
            "result_refs": _refs(result), "result": result,
            "warnings": warnings or [], "error": error}


_MESSAGES = {
    "invalid_arguments": "명령과 인자를 확인하세요. palim --help로 사용법을 볼 수 있습니다.",
    "invalid_data_id": "Data ID는 소문자 SHA-256 64자리여야 합니다.",
    "invalid_request_id": "요청 ID는 UUIDv7이어야 합니다.",
    "database_not_configured": "PALIMPSEST_DATABASE_DSN 또는 PALIMPSEST_DATABASE_DSN_FILE을 설정하세요.",
    "admin_database_not_configured": "PALIMPSEST_ADMIN_DSN 또는 PALIMPSEST_ADMIN_DSN_FILE을 설정하세요.",
    "ambiguous_configuration": "DSN과 DSN_FILE 중 하나만 설정하세요.",
    "secret_file_unreadable": "설정한 DSN secret 파일을 읽을 수 없습니다.",
    "invalid_configuration": "환경 설정을 확인하세요.",
    "duplicate_data": "이미 등록된 원본입니다. 기존 Data ID를 확인하세요.",
    "idempotency_conflict": "같은 요청 ID에 다른 입력을 사용할 수 없습니다.",
    "integrity_conflict": "저장된 원본의 무결성을 확인할 수 없습니다.",
    "not_ready": "실행 환경이 준비되지 않았습니다. 진단 결과를 확인하세요.",
    "interrupted": "명령 관찰을 중단했습니다. 진행 중인 요청은 요청 ID로 확인하세요.",
}


def _public_error(exc):
    code = exc.code if isinstance(exc.code, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", exc.code) else "technical_failure"
    messages = {2: "명령 또는 환경 설정을 확인하세요.", 3: "실행 환경을 확인하세요.",
                4: "요청을 처리하지 못했습니다. 요청 상태를 확인하세요.", 5: "이 작업에 필요한 권한이 없습니다.",
                6: "현재 저장 상태와 요청이 충돌합니다.", 7: "요청이 아직 해결되지 않았습니다."}
    error = {"code": code, "message": _MESSAGES.get(code, messages.get(exc.exit_code, messages[4])), "details": {}}
    if isinstance(exc.details, dict):
        for key in ("data_id", "request_id", "acquisition_id", "state", "retryable",
                    "series_id", "version_id", "expected_head", "current_head", "bound_version"):
            value = exc.details.get(key)
            if isinstance(value, bool) and key == "retryable":
                error["details"][key] = value
            elif key == "state" and isinstance(value, str) and re.fullmatch(r"[a-z_]{1,64}", value):
                error["details"][key] = value
            elif key in {"data_id", "request_id", "acquisition_id", "series_id", "version_id",
                         "expected_head", "current_head", "bound_version"} and isinstance(value, (str, UUID)):
                try:
                    error["details"][key] = data_id(str(value)) if key == "data_id" else request_id(str(value))
                except PalimpsestError:
                    pass
    return error


def _emit(envelope, json_mode):
    warning_lines = [_safe_json({"warning": warning}) for warning in envelope["warnings"]]
    if json_mode:
        print(_safe_json(envelope), flush=True)
    elif envelope["error"]:
        print(_safe_json(envelope["error"], indent=2), file=sys.stderr, flush=True)
        if envelope["result"] is not None:
            print(_safe_json(envelope["result"], indent=2), flush=True)
    else:
        result = envelope["result"]
        if isinstance(result, dict) and set(result) == {"help"}:
            print(result["help"], end="", flush=True)  # Generated help has no user-supplied values.
        elif isinstance(result, dict) and set(result) == {"version"}:
            print("palim " + result["version"], flush=True)
        else:
            print(_safe_json(result, indent=2), flush=True)
    for warning in warning_lines:
        print(warning, file=sys.stderr, flush=True)


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    option_args = arguments[:arguments.index("--")] if "--" in arguments else arguments
    json_mode = "--json" in option_args
    doctor = False
    try:
        parser = _parser()
        args = parser.parse_args(arguments)
        doctor = args.command == "doctor"
        if args.command is None:
            raise _OutputRequested({"help": parser.format_help()})
        if args.command == "db":
            result = _migrate(select_database(load_dsn("PALIMPSEST_ADMIN_DSN"), args.database_name))
        elif args.command == 'code':
            from . import code_snapshot
            if args.action == 'snapshot':
                result = code_snapshot.snapshot(args.root, args.directory, paths=args.include)
            elif args.action == 'verify':
                result = code_snapshot.verify(args.directory, expected_sha256=args.data_id)
            elif args.action == 'locate':
                result = code_snapshot.locate(args.directory, byte_range=args.byte_range, char_range=args.char_range)
            else:
                result = code_snapshot.restore(args.directory, args.target)
        elif args.command == 'information' and args.action == 'evidence-context':
            from .pdf_evidence import read_evidence
            from .paragraph_projection import select_evidence_context
            result = select_evidence_context(read_evidence(args.directory), args.page)
        elif (args.command == 'information' and args.action in ('sections', 'section-context', 'document-context')
              and args.execution_id is None):
            from .pdf_evidence import read_evidence
            from .section_projection import build_sections, section_context, document_context
            evidence = read_evidence(args.directory)
            if args.action == 'document-context':
                result = document_context(evidence, expected_projection_sha256=args.projection_sha256)
            else:
                result = (build_sections(evidence) if args.action == 'sections'
                          else section_context(evidence, args.section_id, expected_projection_sha256=args.projection_sha256))
        elif args.command == 'wiki':
            result = _wiki(args, load_config())
        elif args.command == 'knowledge':
            result = _knowledge(args, load_config())
        elif args.command == 'd2k':
            from .d2k_cli import run as run_d2k
            result = run_d2k(args,load_config())
        elif args.command == 'wisdom':
            from .wisdom_cli import run as run_wisdom
            result = run_wisdom(args,load_config())
        elif args.command == 'parchment':
            from .parchment_cli import run as run_parchment
            result = run_parchment(args,load_config())
        elif args.command == 'propagation':
            from .propagation_cli import run as run_propagation
            result = run_propagation(args,load_config())
        elif args.command in ('compile','jobs','information'):
            result = _compile(args, load_config())
        elif args.command == 'data' and args.action in ('series-create', 'series-show', 'series-history', 'series-append',
                                                     'version', 'compare-code-versions', 'restore-code-version'):
            result = _data_versions(args, load_config())
        else:
            config = load_config()
            service = _service(config)
            if args.command == 'requests' or (args.command == 'data' and args.action in ('import', 'import-code-snapshot')):
                original_service = service
                service = _registration_service(service, args, config)
                registration_options = ({'realm_id': args.realm_id, 'reason': args.realm_reason}
                    if args.command == 'data' and service is not original_service else {})
            if doctor:
                result = service.doctor()
            elif args.command == "data" and args.action == "import":
                result = service.import_file(args.path, request_id=args.request_id, media_type=args.media_type,
                                             origin_uri=args.origin_uri, on_request_id=_request_started, **registration_options)
            elif args.command == 'data' and args.action == 'import-code-snapshot':
                result = service.import_code_snapshot(args.directory, request_id=args.request_id,
                                                       on_request_id=_request_started, **registration_options)
            elif args.command == 'data' and args.action == 'storage-stats':
                row = service.show(args.data_id)
                result = {'data_id': args.data_id, **service.artifact_store.storage_stats(args.data_id, row['byte_size'])}
            elif args.command == "data":
                result = getattr(service, args.action)(args.data_id)
            elif args.action == "show":
                result = service.request_status(args.request_id)
            else:
                result = service.recover(args.request_id)
        warnings = result.get("warnings", []) if isinstance(result, dict) else []
        if doctor and result.get("ready") is not True:
            error = _public_error(PalimpsestError("not_ready", "", 3))
            _emit(_envelope(result, error=error, warnings=warnings), json_mode)
            return 3
        _emit(_envelope(result, warnings=warnings), json_mode)
        if args.command in ('jobs', 'knowledge', 'd2k') and args.action == 'decide' and result.get('state') == 'needs_human':
            return 7
        if args.command == 'wiki' and args.action == 'decide' and result.get('state') == 'needs_review':
            return 7
        return 0
    except _OutputRequested as output:
        _emit(_envelope(output.result), json_mode)
        return 0
    except PalimpsestError as exc:
        error = _public_error(exc)
        result = None
        if doctor:
            result = {"ready": False, "database": {"ready": False, "code": error["code"]}}
        envelope = _envelope(result, error=error)
        envelope["result_refs"] = _refs(error["details"])
        _emit(envelope, json_mode)
        return 3 if doctor and exc.exit_code == 2 else exc.exit_code
    except KeyboardInterrupt:
        _emit(_envelope(error=_public_error(PalimpsestError("interrupted", "", 130))), json_mode)
        return 130
    except Exception:
        _emit(_envelope(error=_public_error(PalimpsestError("technical_failure", "", 4))), json_mode)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
