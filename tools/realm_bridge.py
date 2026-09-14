"""Private JSONL adapter for the separately provisioned Realm metadata catalog."""

import argparse
import sys

from palimpsest.data import request_id as uuid7
from palimpsest.errors import PalimpsestError
from palimpsest.realms import RealmCatalog, normalize_members, _text


FIELDS = {
    'catalog': set(), 'history': {'realm_id'},
    'create': {'name', 'description', 'actor', 'reason', 'request_id'},
    'revise': {'realm_id', 'expected_revision_id', 'name', 'description', 'members', 'actor', 'reason', 'request_id'},
}


class RealmService:
    """Host validates actual source membership; this adapter accepts no source paths.

    The nested payload preserves the canonical UUIDv7 idempotency request_id.
    The outer JSONL request_id belongs exclusively to transport correlation.
    """
    def __init__(self, catalog):
        self.catalog = catalog

    def dispatch(self, envelope):
        if not isinstance(envelope, dict) or set(envelope) != {'payload'}:
            self._invalid()
        value = envelope['payload']
        operation = value.get('operation') if isinstance(value, dict) else None
        if not isinstance(operation, str) or operation not in FIELDS or set(value) != FIELDS[operation] | {'operation'}:
            self._invalid()
        arguments = {key: item for key, item in value.items() if key != 'operation'}
        for key, item in arguments.items():
            if key in ('realm_id', 'expected_revision_id', 'request_id'):
                uuid7(item)
            elif key == 'members':
                arguments[key] = normalize_members(item)
            else:
                _text(item, key, empty=key == 'description')
        return getattr(self.catalog, operation)(**arguments)

    @staticmethod
    def _invalid():
        raise PalimpsestError('invalid_realm_request', 'Realm metadata 요청의 작업·정확한 ID·필드를 확인하세요.', 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-name', required=True)
    args = parser.parse_args()
    try:
        # Shared transport performs bounded JSONL decoding and fixed-code error
        # replies. Loading it here leaves pure adapter tests independent of DBs.
        from desktop_bridge import serve
        from palimpsest.config import load_config, select_database
        config = load_config()
        catalog = RealmCatalog(select_database(config.database_dsn, args.database_name))
        serve(RealmService(catalog), sys.stdin, sys.stdout)
    except Exception:
        print('Realm bridge initialization failed; verify its separately provisioned metadata connection.', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
