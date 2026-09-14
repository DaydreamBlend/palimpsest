"""Thin CLI argument/receipt routing; mocked services are not database tests."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

from palimpsest import cli
from palimpsest import code_snapshot
from palimpsest.errors import PalimpsestError


def uid(number):
    return f'019947e2-1234-7000-8000-{number:012x}'


DATA = 'a' * 64
DSN = 'postgresql://test.invalid/version-cli'


class DataVersionCLITests(unittest.TestCase):
    def setUp(self):
        self.versions, self.runtime, self.service, self.store = Mock(), Mock(), Mock(), Mock()
        versions_module = ModuleType('palimpsest.data_versions')
        versions_module.DataVersions = self.versions_factory = Mock(return_value=self.versions)
        runtime_module = ModuleType('palimpsest.knowledge_runtime')
        runtime_module.KnowledgeRuntime = Mock(return_value=self.runtime)
        storage_module = ModuleType('palimpsest.artifact_store')
        storage_module.ArtifactStore = self.store_factory = Mock(return_value=self.store)
        self.patches = [patch.dict('sys.modules', {'palimpsest.data_versions': versions_module,
            'palimpsest.knowledge_runtime': runtime_module, 'palimpsest.artifact_store': storage_module}),
            patch.dict(os.environ, {'PALIMPSEST_DATABASE_DSN': DSN, 'PALIMPSEST_ACTOR': 'operator'}, clear=True),
            patch.object(cli, '_service', return_value=self.service)]
        for context in self.patches:
            context.start()
            self.addCleanup(context.stop)

    def invoke(self, args):
        output, errors = io.StringIO(), io.StringIO()
        with patch('builtins.input', side_effect=AssertionError('CLI must not prompt')), \
                redirect_stdout(output), redirect_stderr(errors):
            code = cli.main([*args, '--json', '--non-interactive'])
        return code, json.loads(output.getvalue()), errors.getvalue()

    def test_snapshot_registration_uses_verified_service_and_request_callback(self):
        product = Mock()
        product.import_code_snapshot.return_value = {'data_id': DATA, 'request_id': uid(1), 'state': 'committed'}
        with patch('palimpsest.realm_registration.configured_service', return_value=product) as registration:
            code, result, errors = self.invoke(['data', 'import-code-snapshot', 'snapshot-folder',
                '--request-id', uid(1), '--realm-id', uid(2)])
        registration.assert_called_once()
        self.assertEqual(code, 0)
        self.assertEqual(errors, '')
        product.import_code_snapshot.assert_called_once_with(Path('snapshot-folder'), request_id=uid(1),
            on_request_id=cli._request_started, realm_id=uid(2), reason='자료 등록')
        self.service.import_code_snapshot.assert_not_called()
        self.service.import_file.assert_not_called()
        self.assertEqual(result['result_refs']['data_id'], DATA)

    def test_series_create_and_reads_forward_exact_ids_and_configured_actor(self):
        self.versions.create.return_value = {'series_id': uid(2), 'request_id': uid(1), 'outcome': 'created'}
        code, result, _ = self.invoke(['data', 'series-create', '코드 이력', '--request-id', uid(1)])
        self.assertEqual(code, 0)
        self.versions.create.assert_called_once_with('코드 이력', uid(1), actor_ref='operator')
        self.versions_factory.assert_called_with(DSN, None)
        self.store_factory.assert_not_called()
        self.assertEqual(result['result_refs']['series_id'], uid(2))
        for action, method, identifier in [('series-show', 'show', uid(2)),
                                           ('series-history', 'history', uid(2)), ('version', 'version', uid(3))]:
            getattr(self.versions, method).return_value = {'version_id': uid(3)}
            code, result, _ = self.invoke(['data', action, identifier])
            self.assertEqual(code, 0)
            getattr(self.versions, method).assert_called_once_with(identifier)
            self.assertEqual(result['result_refs']['version_id'], uid(3))

    def test_append_forwards_expected_head_without_fetching_or_guessing_it(self):
        self.versions.append.return_value = {'series_id': uid(2), 'version_id': uid(3), 'outcome': 'created'}
        code, _, _ = self.invoke(['data', 'series-append', uid(2), DATA, '--request-id', uid(1),
                                  '--expected-head', uid(4), '--title', '수정본', '--message', '설정 값 수정'])
        self.assertEqual(code, 0)
        self.versions.append.assert_called_once_with(uid(2), DATA, uid(1), uid(4),
                                                     title='수정본', message='설정 값 수정', actor_ref='operator')
        self.versions_factory.assert_called_with(DSN, self.store)
        self.versions.show.assert_not_called()
        self.versions.append.reset_mock()
        code, _, _ = self.invoke(['data', 'series-append', uid(2), DATA, '--request-id', uid(1)])
        self.assertEqual(code, 0)
        self.versions.append.assert_called_once_with(uid(2), DATA, uid(1), None, title='', message='', actor_ref='operator')

    def test_stale_head_errors_preserve_safe_machine_refs_without_private_details(self):
        self.versions.append.side_effect = PalimpsestError('data_version_head_changed', 'do-not-print-private', 6,
            {'series_id': uid(2), 'expected_head': uid(3), 'current_head': uid(4), 'sql': 'do-not-print-private'})
        code, result, errors = self.invoke(['data', 'series-append', uid(2), DATA, '--request-id', uid(1),
                                           '--expected-head', uid(3)])
        self.assertEqual(code, 6)
        self.assertEqual(result['error']['details'], {'series_id': uid(2), 'expected_head': uid(3), 'current_head': uid(4)})
        self.assertEqual(result['result_refs'], {'series_id': uid(2)})
        self.assertNotIn('do-not-print-private', json.dumps(result) + errors)

    def test_storage_stats_gets_authoritative_size_and_verified_store_result(self):
        self.service.show.return_value = {'data_id': DATA, 'byte_size': 123}
        self.service.artifact_store.storage_stats.return_value = {'storage': 'segmented-v1', 'logical_bytes': 123,
                                                                 'unique_blob_bytes': 100}
        code, result, _ = self.invoke(['data', 'storage-stats', DATA])
        self.assertEqual(code, 0)
        self.service.show.assert_called_once_with(DATA)
        self.service.artifact_store.storage_stats.assert_called_once_with(DATA, 123)
        self.assertEqual(result['result']['logical_bytes'], 123)
        self.assertEqual(result['result_refs']['data_id'], DATA)

    def test_knowledge_version_context_preserves_order_mode_and_input_bytes(self):
        with tempfile.TemporaryDirectory(prefix='palim-version-cli-') as directory:
            source = Path(directory) / 'input.json'
            raw = b'{"schema_version":"k2k-input-v1","nodes":[]}'
            source.write_bytes(raw)
            self.runtime.prepare.return_value = {'execution_id': uid(7), 'state': 'prepared'}
            code, _, _ = self.invoke(['knowledge', 'prepare', '--operation', 'k2k', '--data-id', DATA,
                '--request-id', uid(1), '--input', str(source), '--data-version-id', uid(4),
                '--data-version-id', uid(3), '--data-version-mode', 'pinned'])
            self.assertEqual(code, 0)
            self.runtime.prepare.assert_called_once_with('k2k', DATA, uid(1), json.loads(raw), selection=None,
                feedback_execution_id=None, data_version_ids=[uid(4), uid(3)], data_version_mode='pinned')
            self.assertEqual(source.read_bytes(), raw)
        self.runtime.graph.return_value = {'nodes': [], 'selected_data_version': {'version_id': uid(3)}}
        code, _, _ = self.invoke(['knowledge', 'graph', '--data-version-id', uid(3)])
        self.assertEqual(code, 0)
        self.runtime.graph.assert_called_once_with(None, data_version_id=uid(3))

    def test_invalid_version_arguments_fail_before_service_calls_and_are_not_echoed(self):
        private = 'postgresql://private:password@hidden/db'
        for args in [['data', 'series-append', uid(2), DATA],
                     ['data', 'series-append', uid(2), DATA, '--request-id', uid(1), '--expected-head', private],
                     ['data', 'version', private], ['knowledge', 'graph', '--data-version-id', private]]:
            code, result, errors = self.invoke(args)
            self.assertEqual(code, 2)
            self.assertNotIn(private, json.dumps(result) + errors)
        self.versions_factory.assert_not_called()
        self.runtime.graph.assert_not_called()

    def test_stored_code_versions_compare_and_restore_through_exact_artifact_reads(self):
        with tempfile.TemporaryDirectory(prefix='palim-version-restore-cli-') as directory:
            root = Path(directory)
            original = root / 'src' / 'example.py'
            original.parent.mkdir()
            first_bytes, second_bytes = b'value = 1\r\n', 'value = "한글"\r\n'.encode('utf-8')
            original.write_bytes(first_bytes)
            first = code_snapshot.snapshot(root, root / 'v1', paths=['src/example.py'])
            original.write_bytes(second_bytes)
            second = code_snapshot.snapshot(root, root / 'v2', paths=['src/example.py'])
            bodies = {first['dossier_sha256']: (root / 'v1/dossier.md').read_bytes(),
                      second['dossier_sha256']: (root / 'v2/dossier.md').read_bytes()}
            records = {uid(1): {'version_id': uid(1), 'series_id': uid(7), 'data_id': first['dossier_sha256'], 'title': 'V1'},
                       uid(2): {'version_id': uid(2), 'series_id': uid(7), 'data_id': second['dossier_sha256'], 'title': 'V2'}}
            self.versions.version.side_effect = records.__getitem__
            self.service.show.side_effect = lambda identifier: {'data_id': identifier, 'byte_size': len(bodies[identifier])}
            self.service.artifact_store.read.side_effect = lambda identifier, size: bodies[identifier]
            code, result, _ = self.invoke(['data', 'compare-code-versions', uid(1), uid(2)])
            self.assertEqual(code, 0)
            self.assertEqual(result['result']['changed'], ['src/example.py'])
            self.assertEqual(result['result']['before_version'], records[uid(1)])
            self.assertEqual(result['result']['after_version'], records[uid(2)])
            self.assertEqual(result['result']['before_data_id'], first['dossier_sha256'])
            self.service.artifact_store.read.assert_any_call(first['dossier_sha256'], first['dossier_byte_size'])
            self.service.artifact_store.read.assert_any_call(second['dossier_sha256'], second['dossier_byte_size'])
            restored = root / 'restored'
            code, result, _ = self.invoke(['data', 'restore-code-version', uid(1), str(restored)])
            self.assertEqual(code, 0)
            self.assertEqual(result['result']['data_version'], records[uid(1)])
            self.assertEqual((restored / 'src/example.py').read_bytes(), first_bytes)
            self.assertEqual(original.read_bytes(), second_bytes)
            (restored / 'keep.txt').write_bytes(b'preserve existing files')
            code, result, _ = self.invoke(['data', 'restore-code-version', uid(2), str(restored)])
            self.assertEqual(code, 4)
            self.assertEqual((restored / 'src/example.py').read_bytes(), first_bytes)
            self.assertEqual((restored / 'keep.txt').read_bytes(), b'preserve existing files')

    def test_code_version_restore_rejects_an_ordinary_markdown_data_before_writing(self):
        with tempfile.TemporaryDirectory(prefix='palim-noncode-restore-cli-') as directory:
            target = Path(directory) / 'restored'
            self.versions.version.return_value = {'version_id': uid(1), 'data_id': DATA}
            self.service.show.return_value = {'data_id': DATA, 'byte_size': 16}
            self.service.artifact_store.read.return_value = b'# Ordinary notes'
            code, _, _ = self.invoke(['data', 'restore-code-version', uid(1), str(target)])
            self.assertEqual(code, 4)
            self.assertFalse(target.exists())

    def test_new_help_is_available_without_loading_configuration_or_services(self):
        with patch.object(cli, 'load_config', side_effect=AssertionError('help must not load config')):
            for args in [['data', 'import-code-snapshot'], ['data', 'series-append'], ['knowledge', 'prepare']]:
                code, result, _ = self.invoke([*args, '--help'])
                self.assertEqual(code, 0)
                self.assertIn('help', result['result'])
        self.versions_factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
