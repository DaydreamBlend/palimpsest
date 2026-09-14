"""Public I2K routing and historical replay; synthetic inputs, no model calls."""

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import tempfile
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

from palimpsest import cli
from palimpsest.i2k_selection import PROFILE as SELECTION_PROFILE
from palimpsest.knowledge import PROFILE as LEGACY_PROFILE
from palimpsest.multi_source_i2k import PROFILE, combine_packets
from test_multi_source_i2k import packet, uid


def invoke_prepare(source, identifier, *, dsn='postgresql://test.invalid/routing',
                   selection=False, operation='i2k', feedback=None):
    with tempfile.TemporaryDirectory(prefix='palimpsest-knowledge-routing-') as directory:
        path = Path(directory) / 'input.json'
        path.write_text(json.dumps(source, ensure_ascii=False), encoding='utf-8')
        before = path.read_bytes()
        arguments = ['knowledge', 'prepare', '--operation', operation,
                     '--data-id', source.get('data_id', '1' * 64), '--request-id', identifier,
                     '--input', str(path), '--json', '--non-interactive']
        if selection:
            arguments.append('--selection')
        if feedback:
            arguments.extend(['--feedback-execution-id', feedback])
        output, errors = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {'PALIMPSEST_DATABASE_DSN': dsn}, clear=True), \
                redirect_stdout(output), redirect_stderr(errors):
            code = cli.main(arguments)
        if path.read_bytes() != before:
            raise AssertionError('Public routing rewrote the source packet')
        return code, json.loads(output.getvalue()), errors.getvalue()


class KnowledgeRoutingUnitTests(unittest.TestCase):
    def setUp(self):
        self.runtime = Mock()
        self.runtime.request_profile.return_value = None
        self.runtime.prepare.return_value = {'execution_id': uid(91), 'state': 'prepared'}
        module = ModuleType('palimpsest.knowledge_runtime')
        module.KnowledgeRuntime = Mock(return_value=self.runtime)
        self.module_patch = patch.dict('sys.modules', {'palimpsest.knowledge_runtime': module})
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)

    def test_new_single_source_uses_explicit_contract_with_or_without_selection_flag(self):
        source, identifier = packet(1), uid(90)
        before = deepcopy(source)
        for selection in (False, True):
            self.runtime.reset_mock()
            code, result, errors = invoke_prepare(source, identifier, selection=selection)
            self.assertEqual(code, 0)
            self.assertEqual(errors, '')
            self.assertEqual(result['command_status'], 'succeeded')
            self.runtime.request_profile.assert_called_once_with(identifier)
            self.runtime.prepare.assert_called_once_with('i2k', source['data_id'], identifier,
                combine_packets([source]), selection=True if selection else None, feedback_execution_id=None)
        self.assertEqual(source, before)

    def test_existing_multi_request_recreates_identical_single_source_wrapper(self):
        source, identifier = packet(1), uid(90)
        self.runtime.request_profile.return_value = PROFILE
        code, _, _ = invoke_prepare(source, identifier)
        self.assertEqual(code, 0)
        self.assertEqual(self.runtime.prepare.call_args.args[3], combine_packets([source]))

    def test_existing_legacy_and_selection_requests_keep_original_packet(self):
        source = packet(1)
        for profile in (LEGACY_PROFILE, SELECTION_PROFILE):
            with self.subTest(profile=profile):
                self.runtime.reset_mock()
                self.runtime.request_profile.return_value = profile
                code, _, _ = invoke_prepare(source, uid(90))
                self.assertEqual(code, 0)
                self.runtime.prepare.assert_called_once_with('i2k', source['data_id'], uid(90), source,
                    selection=None, feedback_execution_id=None)

    def test_already_combined_and_n2e_inputs_are_not_rewrapped(self):
        for operation, source in (('i2k', combine_packets([packet(1), packet(2)])),
                                  ('n2e', {'schema_version': 'n2e-input-v1', 'nodes': []})):
            with self.subTest(operation=operation):
                self.runtime.reset_mock()
                code, _, _ = invoke_prepare(source, uid(90), operation=operation)
                self.assertEqual(code, 0)
                self.runtime.request_profile.assert_not_called()
                self.assertEqual(self.runtime.prepare.call_args.args[3], source)

    def test_feedback_is_forwarded_without_changing_the_source_wrapper(self):
        source = packet(1)
        code, _, _ = invoke_prepare(source, uid(90), feedback=uid(89))
        self.assertEqual(code, 0)
        self.assertEqual(self.runtime.prepare.call_args.args[3], combine_packets([source]))
        self.assertEqual(self.runtime.prepare.call_args.kwargs['feedback_execution_id'], uid(89))


@unittest.skipUnless(os.environ.get('PALIMPSEST_TEST_DSN'), 'Requires explicitly provisioned isolated PG')
class KnowledgeRoutingPostgresTests(unittest.TestCase):
    def setUp(self):
        import test_selection_runtime as fixtures
        self.owner = fixtures.SelectionRuntimeTests('runTest')
        self.addCleanup(self.owner.doCleanups)
        self.helper = self.owner._fixture()
        self.runtime, self.source, self.dsn = self.helper.runtime, self.helper.packet, self.helper.dsn

    def call(self, identifier, **kwargs):
        code, envelope, errors = invoke_prepare(self.source, identifier, dsn=self.dsn, **kwargs)
        self.assertEqual(code, 0, envelope)
        self.assertEqual(errors, '')
        return envelope['result']

    def test_new_public_start_requires_realm_and_historical_multi_request_replays(self):
        identifier = self.helper.repo.allocate_id()
        self.assertIsNone(self.runtime.request_profile(identifier))
        code, envelope, _ = invoke_prepare(self.source, identifier, dsn=self.dsn)
        self.assertEqual(code, 2)
        self.assertEqual(envelope['error']['code'], 'realm_required')
        # Preserve the old raw-API profile's exact wrapper/replay regression.
        prepared = self.runtime.prepare('i2k', self.helper.data_id, identifier, combine_packets([self.source]))
        self.assertEqual(prepared['profile']['schema_version'], PROFILE)
        self.assertEqual(self.runtime.request_profile(identifier), PROFILE)
        self.assertEqual(prepared['input_snapshot']['input'], combine_packets([self.source]))
        replayed = self.call(identifier)
        self.assertTrue(replayed['replayed'])
        self.assertEqual(replayed['execution_id'], prepared['execution_id'])
        self.assertEqual(replayed['input_digest'], prepared['input_digest'])
        self.assertEqual(replayed['request_fingerprint'], prepared['request_fingerprint'])
        self.assertEqual(self.runtime.show(prepared['execution_id'])['model_calls'], [])

    def test_old_direct_api_requests_replay_without_a_new_profile_or_execution(self):
        for selection, profile in ((False, LEGACY_PROFILE), (True, SELECTION_PROFILE)):
            identifier = self.helper.repo.allocate_id()
            original = self.runtime.prepare('i2k', self.helper.data_id, identifier, self.source, selection=selection)
            self.assertEqual(self.runtime.request_profile(identifier), profile)
            replayed = self.call(identifier)
            self.assertTrue(replayed['replayed'])
            self.assertEqual(replayed['execution_id'], original['execution_id'])
            self.assertEqual(replayed['profile']['schema_version'], profile)
            self.assertEqual(replayed['input_snapshot']['input'], self.source)


if __name__ == '__main__':
    unittest.main()
