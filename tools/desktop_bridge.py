"""Long-lived stdin/stdout JSON bridge for Electron; run inside the app container."""

import argparse
import json
import sys

from palimpsest.config import load_config, select_database
from palimpsest.desktop_read import DesktopReadService
from palimpsest.errors import PalimpsestError
from palimpsest.source_read import SourceReadService


class DesktopServices:
    """Route only typed read operations within the host-selected connection."""
    def __init__(self, sources, wiki=None, knowledge=None):
        self.sources, self.wiki, self.knowledge = sources, wiki, knowledge or wiki

    def dispatch(self, request):
        operation = request.get('operation') if isinstance(request, dict) else None
        if isinstance(operation, str) and (operation.startswith('source_') or operation in ('parchment_catalog', 'parchment_get')):
            return self.sources.dispatch(request)
        if operation in ('knowledge_catalog', 'knowledge_node', 'data_grounding') and self.knowledge is not None:
            return self.knowledge.dispatch(request)
        if self.wiki is None:
            raise PalimpsestError('desktop_wiki_not_configured', '이 연결에는 Wiki가 설정되지 않았습니다.', 2)
        return self.wiki.dispatch(request)


def serve(service, source, destination):
    for line in source:
        identifier = None
        try:
            if len(line) > 65536:
                raise PalimpsestError('invalid_desktop_request', '요청이 너무 큽니다.', 2)
            envelope = json.loads(line)
            if (not isinstance(envelope, dict) or not isinstance(envelope.get('request_id'), str)
                    or not 1 <= len(envelope['request_id']) <= 128
                    or any(ord(c) < 32 for c in envelope['request_id'])):
                raise PalimpsestError('invalid_desktop_request', '요청 형식을 확인하세요.', 2)
            identifier = envelope['request_id']
            request = {key: value for key, value in envelope.items() if key != 'request_id'}
            result = {'request_id': identifier, 'result': service.dispatch(request), 'error': None}
        except PalimpsestError as error:
            result = {'request_id': identifier, 'result': None, 'error': {'code': error.code, 'message': error.message}}
        except Exception:
            # Exception text may contain DSNs or document-controlled paths.
            result = {'request_id': identifier, 'result': None,
                      'error': {'code': 'desktop_read_failed', 'message': '읽기를 완료하지 못했습니다.'}}
        destination.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + '\n')
        destination.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wiki-id')
    parser.add_argument('--query-directory', default='/query')
    parser.add_argument('--database-name', required=True)
    parser.add_argument('--include-data-id', action='append', default=None)
    args = parser.parse_args()
    try:
        config = load_config()
        dsn = select_database(config.database_dsn, args.database_name)
        sources = SourceReadService(dsn, config.artifact_root)
        knowledge = DesktopReadService(dsn, config.artifact_root, args.wiki_id, args.query_directory,
                                       include_data_ids=args.include_data_id)
        wiki = knowledge if args.wiki_id else None
        service = DesktopServices(sources, wiki, knowledge)
        serve(service, sys.stdin, sys.stdout)
    except Exception:
        print('Desktop read bridge initialization failed; verify local configuration.', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
