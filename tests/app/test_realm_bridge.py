"""Pure Realm bridge dispatch tests; no catalog DB or source store is opened."""

from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

from palimpsest.errors import PalimpsestError

_path = Path(__file__).resolve().parents[2] / 'tools' / 'realm_bridge.py'
_spec = importlib.util.spec_from_file_location('realm_bridge_contract_fixture', _path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
RealmService = _module.RealmService


def uid(number):
    return f'019af000-0000-7000-8000-{number:012x}'


class FakeCatalog:
    def __init__(self):
        self.calls = []

    def call(self, operation, arguments):
        self.calls.append((operation, deepcopy(arguments)))
        return {'operation': operation, **arguments}

    def catalog(self):
        return self.call('catalog', {})

    def history(self, **arguments):
        return self.call('history', arguments)

    def create(self, **arguments):
        return self.call('create', arguments)

    def revise(self, **arguments):
        return self.call('revise', arguments)


class RealmBridgeTests(unittest.TestCase):
    def setUp(self):
        self.catalog = FakeCatalog()
        self.service = RealmService(self.catalog)
        self.create = {'operation': 'create', 'name': 'Source project', 'description': '',
            'actor': 'test-user', 'reason': 'Synthetic classification', 'request_id': uid(1)}

    def test_nested_canonical_request_id_is_preserved_independently_of_outer_transport(self):
        outer = {'request_id': 'transport-correlation-only', 'payload': self.create}
        # Existing desktop JSONL serve removes only this outer transport field.
        result = self.service.dispatch({key: value for key, value in outer.items() if key != 'request_id'})
        self.assertEqual(result['request_id'], uid(1))
        self.assertEqual(self.create['request_id'], uid(1))
        self.assertEqual(len(self.catalog.calls), 1)

    def test_catalog_and_history_keep_existing_catalog_result_shapes(self):
        self.assertEqual(self.service.dispatch({'payload': {'operation': 'catalog'}}), {'operation': 'catalog'})
        self.assertEqual(self.service.dispatch({'payload': {'operation': 'history', 'realm_id': uid(2)}}),
                         {'operation': 'history', 'realm_id': uid(2)})

    def test_revise_normalizes_exact_store_qualified_members_without_mutating_input(self):
        request = {**self.create, 'operation': 'revise', 'realm_id': uid(2), 'expected_revision_id': uid(3),
            'members': [{'store_id': uid(5), 'member_kind': 'data_series', 'member_id': uid(6)},
                        {'store_id': uid(4), 'member_kind': 'data', 'member_id': 'a' * 64}]}
        before = deepcopy(request)
        result = self.service.dispatch({'payload': request})
        self.assertEqual(request, before)
        self.assertEqual(result['members'], list(reversed(before['members'])))
        self.assertEqual(result['expected_revision_id'], uid(3))

    def test_unknown_operations_flat_envelopes_extra_authority_and_paths_never_dispatch(self):
        for envelope in [self.create, {'payload': self.create, 'database': 'source_database'},
            {'payload': {'operation': 'compile'}}, {'payload': {'operation': ['catalog']}},
            {'payload': {**self.create, 'members': []}}, {'payload': {**self.create, 'members_verified': True}},
            {'payload': {**self.create, 'dsn': 'untrusted'}}, {'payload': {**self.create, 'artifact_path': '../private'}},
            {'payload': {**self.create, 'request_id': 'transport-correlation-only'}},
            {'payload': {**self.create, 'actor': ''}}, {'payload': {**self.create, 'name': '\x00'}}]:
            with self.subTest(envelope=envelope), self.assertRaises(PalimpsestError):
                self.service.dispatch(envelope)
        self.assertEqual(self.catalog.calls, [])


if __name__ == '__main__':
    unittest.main()
