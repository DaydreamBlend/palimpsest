"""Registration recovery and compilation gate; in-memory journals, no provider."""

from contextlib import nullcontext
from copy import deepcopy
from hashlib import sha256
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from palimpsest import cli
from palimpsest.data import Payload
from palimpsest.errors import PalimpsestError
from palimpsest.realm_registration import RealmRegistration, registration, verify_ready
from palimpsest.service import DataService


def uid(number):
    return f'01992d33-1020-7123-8123-{number:012x}'


class Catalog:
    def __init__(self):
        self.head = {'realm_id': uid(1), 'revision_id': uid(2), 'name': 'Code', 'description': '', 'members': []}
        self.requests, self.fail = {}, False

    def current(self, identifier):
        if identifier != self.head['realm_id']:
            raise PalimpsestError('realm_not_found', 'Fixture Realm only')
        return deepcopy(self.head)

    def request_result(self, identifier):
        if self.fail:
            raise PalimpsestError('database_unavailable', 'Fixture outage')
        return deepcopy(self.requests.get(identifier))

    def revise(self, realm, expected, name, description, members, actor, reason, identifier):
        if expected != self.head['revision_id']:
            raise PalimpsestError('realm_revision_changed', 'Fixture CAS')
        request = dict(operation='revise', realm_id=realm, members=deepcopy(members), actor=actor, reason=reason)
        self.head = dict(realm_id=realm, revision_id=uid(200 + len(self.requests)), request_id=identifier,
                         name=name, description=description, members=deepcopy(members))
        self.requests[identifier] = {'request': request, 'revision': deepcopy(self.head)}
        return deepcopy(self.head)


class RealmRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.rows, self.stored = {}, {}
        self.owner = sha256(b'original source').hexdigest()
        payload = Payload(self.owner, len(b'original source'))
        repo = Mock()
        repo.allocate_id.side_effect = [uid(number) for number in range(10, 100)]
        repo.get_request.side_effect = self.rows.get
        repo.get_data.side_effect = self.stored.get
        def prepare(identifier, body, fingerprint, metadata):
            row = self.rows.get(identifier)
            if row and row['request_fingerprint'] != fingerprint:
                raise PalimpsestError('idempotency_conflict', 'Fixture fingerprint')
            if row is None:
                row = dict(metadata, request_id=identifier, payload_sha256=body.data_id, byte_size=body.byte_size,
                           request_fingerprint=fingerprint, state='staged', result_data_id=None,
                           result_acquisition_id=None, error_code=None)
                self.rows[identifier] = row
            return row
        repo.prepare.side_effect = prepare
        repo.mark_published.side_effect = lambda identifier: self.rows[identifier].update(state='published')
        repo.mark_duplicate.side_effect = lambda identifier, owner: self.rows[identifier].update(state='duplicate')
        def commit(identifier):
            row = self.rows[identifier]
            self.stored[row['payload_sha256']] = {'byte_size': row['byte_size']}
            row.update(state='committed', result_data_id=row['payload_sha256'], result_acquisition_id=uid(500))
            return row
        repo.commit_import.side_effect = commit
        artifacts = Mock()
        artifacts.request_lock.side_effect = lambda identifier: nullcontext()
        artifacts.stage.return_value = artifacts.staged.return_value = payload
        self.source = DataService(repo, artifacts, actor_ref='user')
        self.catalog = Catalog()
        self.product = RealmRegistration(self.source, self.catalog, uid(3))
        self.conn = Mock()
        self.conn.execute.return_value.fetchall.side_effect = lambda: [
            {'data_id': row['result_data_id'], 'external_metadata': row['external_metadata']}
            for row in self.rows.values() if row['state'] == 'committed']

    def test_pending_assignment_blocks_compile_and_recovers_without_rewriting_data(self):
        self.catalog.fail = True
        with self.assertRaises(PalimpsestError) as pending:
            self.product.import_file('source.txt', request_id=uid(90), realm_id=uid(1))
        self.assertEqual(pending.exception.code, 'realm_registration_pending')
        self.assertEqual(self.rows[uid(90)]['state'], 'committed')
        saved = deepcopy(self.rows[uid(90)])
        self.catalog.fail = False
        with self.assertRaises(PalimpsestError) as blocked:
            verify_ready(self.conn, [self.owner], self.catalog, uid(3))
        self.assertEqual(blocked.exception.code, 'realm_registration_pending')
        self.assertEqual(self.product.request_status(uid(90))['state'], 'realm_pending')
        recovered = self.product.recover(uid(90))
        self.assertEqual(recovered['realm_registration_state'], 'completed')
        self.assertEqual(self.rows[uid(90)], saved)
        self.assertEqual(self.source.repository.commit_import.call_count, 1)
        self.assertEqual(len(self.catalog.requests), 1)
        self.assertTrue(self.product.recover(uid(90))['replayed'])
        self.assertEqual(len(self.catalog.requests), 1)
        # Reclassification does not revoke historical registration completion.
        self.catalog.head['members'] = []
        self.catalog.head['revision_id'] = uid(999)
        verify_ready(self.conn, [self.owner], self.catalog, uid(3))

    def test_replay_preserves_selection_and_duplicate_does_not_assign_another_realm(self):
        original = self.product.import_file('source.txt', request_id=uid(90), realm_id=uid(1))
        replay = self.product.import_file('source.txt', request_id=uid(90), realm_id=uid(1))
        self.assertTrue(replay['replayed'])
        self.assertEqual(original['realm_revision_id'], replay['realm_revision_id'])
        with self.assertRaises(PalimpsestError) as changed:
            self.product.import_file('source.txt', request_id=uid(90), realm_id=uid(8))
        self.assertEqual(changed.exception.code, 'idempotency_conflict')
        with self.assertRaises(PalimpsestError) as duplicate:
            self.product.import_file('source.txt', request_id=uid(91), realm_id=uid(1))
        self.assertEqual(duplicate.exception.code, 'duplicate_data')
        self.assertEqual(len(self.catalog.requests), 1)

    def test_required_selection_and_wrong_receipt_fail_closed(self):
        with self.assertRaises(PalimpsestError) as missing:
            self.product.import_file('source.txt', realm_id=None)
        self.assertEqual(missing.exception.code, 'realm_required')
        self.source.artifact_store.stage.assert_not_called()
        self.product.import_file('source.txt', request_id=uid(90), realm_id=uid(1))
        key = registration(self.rows[uid(90)])['membership_request_id']
        self.catalog.requests[key]['request']['actor'] = 'another actor'
        with self.assertRaises(PalimpsestError) as changed:
            verify_ready(self.conn, [self.owner], self.catalog, uid(3))
        self.assertEqual(changed.exception.code, 'realm_registration_receipt_mismatch')

    def test_cli_requires_selection_but_preserves_exact_legacy_replay(self):
        args = SimpleNamespace(command='data', action='import', request_id=None, realm_id=None)
        with self.assertRaises(PalimpsestError) as missing:
            cli._registration_service(self.source, args, SimpleNamespace(database_dsn='unused'))
        self.assertEqual(missing.exception.code, 'realm_required')
        self.source.import_file('source.txt', request_id=uid(90))
        args.request_id = uid(90)
        self.assertIs(cli._registration_service(self.source, args, None), self.source)
        self.conn.execute.return_value.fetchall.side_effect = lambda: []
        verify_ready(self.conn, [self.owner])


@unittest.skipUnless(os.environ.get('PALIMPSEST_TEST_DSN') and os.environ.get('PALIMPSEST_REALM_TEST_DSN'),
                     'Requires separately provisioned disposable source and Realm databases')
class RealmRegistrationPostgresTests(unittest.TestCase):
    def test_actual_journal_and_realm_receipt_recover_after_partial_commit(self):
        from palimpsest.artifact_store import ArtifactStore
        from palimpsest.canonical_store import PostgresRepository, connection
        from palimpsest.realms import RealmCatalog
        repository = PostgresRepository(os.environ['PALIMPSEST_TEST_DSN'])
        catalog = RealmCatalog(os.environ['PALIMPSEST_REALM_TEST_DSN'])
        with catalog._connection() as conn:
            self.assertEqual(conn.execute('SELECT current_database() AS name').fetchone()['name'], 'palimpsest_realm_checks')
        with connection(os.environ['PALIMPSEST_TEST_DSN']) as conn:
            self.assertIn(conn.execute('SELECT current_database() AS name').fetchone()['name'],
                          ('palimpsest', 'palimpsest_effective_k2k_checks', 'palimpsest_wisdom_checks'))
        realm = catalog.create('Registration fixture', '', 'test-user', 'Synthetic recovery check', repository.allocate_id())
        store, identifier = repository.allocate_id(), repository.allocate_id()
        with tempfile.TemporaryDirectory(prefix='palimpsest-realm-registration-') as directory:
            path = Path(directory) / 'source.md'
            raw = ('# Synthetic registration\n' + identifier).encode()
            path.write_bytes(raw)
            service = DataService(repository, ArtifactStore(Path(directory) / 'artifacts'), actor_ref='test-user')
            product = RealmRegistration(service, catalog, store)
            with patch.object(catalog, 'request_result', side_effect=PalimpsestError('database_unavailable', 'Fixture outage')):
                with self.assertRaises(PalimpsestError) as pending:
                    product.import_file(path, realm_id=realm['realm_id'], request_id=identifier)
            self.assertEqual(pending.exception.code, 'realm_registration_pending')
            journal = deepcopy(repository.get_request(identifier))
            self.assertEqual(journal['state'], 'committed')
            owner = journal['result_data_id']
            with connection(os.environ['PALIMPSEST_TEST_DSN']) as conn:
                with self.assertRaises(PalimpsestError) as blocked:
                    verify_ready(conn, [owner], catalog, store)
                self.assertEqual(blocked.exception.code, 'realm_registration_pending')
            recovered = product.recover(identifier)
            self.assertEqual(recovered['realm_registration_state'], 'completed')
            self.assertEqual(repository.get_request(identifier), journal)
            self.assertEqual(service.artifact_store.read(owner, len(raw)), raw)
            current = catalog.current(realm['realm_id'])
            catalog.revise(current['realm_id'], current['revision_id'], current['name'], current['description'], [],
                           'test-user', 'Reclassification does not rewrite history', repository.allocate_id())
            with connection(os.environ['PALIMPSEST_TEST_DSN']) as conn:
                verify_ready(conn, [owner], catalog, store)
            self.assertTrue(product.recover(identifier)['replayed'])
            self.assertEqual(catalog.current(realm['realm_id'])['members'], [])
            self.assertEqual(len(repository.get_acquisitions(owner)), 1)


if __name__ == '__main__':
    unittest.main()
