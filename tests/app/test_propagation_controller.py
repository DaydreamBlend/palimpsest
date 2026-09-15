"""Host controller contract checks with stub CLI/processes, no Docker/provider/DB."""

from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('palimpsest_run_propagation', ROOT / 'tools/run_propagation.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def fixture_request():
    return {'prompt': 'Synthetic fixture only.', 'schema': {'type': 'object'},
        'input_sha256': 'a' * 64, 'output_file': 'generator-response.json', 'images': [],
        'delivered_information_ids': ['synthetic-i'], 'delivered_revalidation_target_sha256': 'b' * 64}


def exchange(request):
    response = {'synthetic_test_only': True}
    return {'response': response, 'receipt': {'actual_delivery': True, 'original_pdf_delivered': False,
        'provider_ref': 'synthetic-no-provider', 'profile': deepcopy(worker.MODEL),
        'input_sha256': request['input_sha256'], 'prompt_sha256': sha256(request['prompt'].encode()).hexdigest(),
        'schema_sha256': worker.digest(request['schema']), 'output_sha256': worker.digest(response),
        'image_attachments': [], **{key: value for key, value in request.items() if key.startswith('delivered_')}}}


class StubController(worker.Controller):
    def __init__(self, args):
        super().__init__(args)
        self.calls, self.replies = [], []

    def app(self, *arguments):
        self.calls.append(arguments)
        if self.replies:
            value = self.replies.pop(0)
            if isinstance(value, BaseException):
                raise value
            return value
        if arguments[0] == 'renew':
            return {'state': 'running', 'lease_valid': True}
        return {'action': 'task_completed', 'task_state': 'done', 'run_state': 'running'}


class PropagationControllerTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix='propagation-controller-test-', dir=ROOT if os.name == 'nt' else None)
        self.base = Path(directory.name).resolve()
        if os.name == 'nt':
            self.assertTrue(self.base.is_relative_to(ROOT))
        self.addCleanup(directory.cleanup)
        # Stub process tests use an isolated writable repository on both the
        # Windows host and the read-only Linux test image.
        root_patch = patch.object(worker, 'ROOT', self.base)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        self.args = SimpleNamespace(directory=self.base / 'results', project='synthetic-project',
            database_name='synthetic-database', artifact_volume='synthetic-artifacts',
            app_image='palimpsest-propagation:0.16.0', docker='synthetic-docker',
            lease_seconds=180, allow_model_calls=False, once=False,
            run_id='019a5c1b-7f00-7000-8000-000000000001')
        self.controller = StubController(self.args)
        self.path = self.args.directory / 'call' / 'request.json'
        self.path.parent.mkdir()
        self.request = fixture_request()
        worker.write_json(self.path, self.request)
        self.output = self.path.parent / self.request['output_file']
        self.task = {'action': 'model_request', 'task_id': 'synthetic-task', 'lease_token': 'synthetic-lease',
            'request_file': '/results/call/request.json', 'operation': 'knowledge', 'phase': 'generator'}

    def test_missing_explicit_flag_prepares_only_and_never_starts_provider(self):
        with patch.object(worker.subprocess, 'Popen') as spawn:
            result = self.controller.model_turn(self.task)
        spawn.assert_not_called()
        self.assertEqual(result['state'], 'blocked')
        self.assertEqual(result['reason'], 'model_calls_require_explicit_flag')
        self.assertFalse(self.output.exists())
        self.assertEqual([call[0] for call in self.controller.calls], ['renew'])

    def test_exact_cached_exchange_is_accepted_without_a_new_model_call(self):
        worker.write_json(self.output, exchange(self.request))
        with patch.object(worker.subprocess, 'Popen') as spawn:
            result = self.controller.model_turn(self.task)
        spawn.assert_not_called()
        self.assertEqual(result['action'], 'task_completed')
        self.assertEqual(self.controller.calls[-1], ('accept', 'synthetic-task', '--lease-token', 'synthetic-lease',
            '--phase', 'generator', '--exchange', '/results/call/generator-response.json'))

    def test_tampered_cached_revalidation_delivery_is_never_accepted_or_overwritten(self):
        cached = exchange(self.request)
        cached['receipt']['delivered_revalidation_target_sha256'] = 'c' * 64
        worker.write_json(self.output, cached)
        original = self.output.read_bytes()
        with patch.object(worker.subprocess, 'Popen') as spawn, self.assertRaises(worker.PalimpsestError) as raised:
            self.controller.model_turn(self.task)
        self.assertEqual(raised.exception.code, 'propagation_cached_exchange_invalid')
        spawn.assert_not_called()
        self.assertEqual(self.output.read_bytes(), original)
        self.assertNotIn('accept', [call[0] for call in self.controller.calls])

    def test_wiki_uses_existing_generic_worker_and_only_accepts_after_renewal(self):
        self.args.allow_model_calls = True
        started = []
        def spawn(argv, **kwargs):
            started.append(argv)
            worker.write_json(self.output, exchange(self.request))
            return SimpleNamespace(pid=123456, returncode=0, poll=lambda: 0)
        with patch.object(worker.subprocess, 'Popen', side_effect=spawn):
            result = self.controller.model_turn({**self.task, 'operation': 'wiki'})
        self.assertEqual(len(started), 1)
        self.assertIn(str(worker.ROOT / 'tools/run_knowledge_model.py'), started[0])
        self.assertEqual(started[0][-1], str(self.path))
        self.assertEqual([call[0] for call in self.controller.calls], ['renew', 'renew', 'accept'])
        self.assertEqual(result['action'], 'task_completed')

    def test_lease_loss_stops_only_owned_model_and_never_submits_stale_exchange(self):
        self.args.allow_model_calls = True
        self.controller.replies = [{'state': 'running'}, {'state': 'paused'}]
        process = SimpleNamespace(pid=123456, returncode=1, stopped=False)
        process.poll = lambda: 1 if process.stopped else None
        stopped = []
        def stop(owned):
            if owned is not None:
                stopped.append(owned)
                owned.stopped = True
        actual_lease = worker.Lease
        with patch.object(worker, 'Lease', side_effect=lambda controller, task: actual_lease(controller, task, interval=0.01)), \
                patch.object(worker, 'stop_owned', side_effect=stop), \
                patch.object(worker.subprocess, 'Popen', return_value=process), \
                self.assertRaises(worker.PalimpsestError) as raised:
            self.controller.model_turn(self.task)
        self.assertEqual(raised.exception.code, 'propagation_lease_lost')
        self.assertTrue(stopped)
        self.assertTrue(all(item is process for item in stopped))
        self.assertNotIn('accept', [call[0] for call in self.controller.calls])
        failure = json.loads(self.output.with_suffix('.failure.json').read_text())['failure']
        self.assertIsNone(failure['actual_delivery'])
        self.assertIsNone(failure['output_sha256'])
        self.assertEqual(failure['planned_revalidation_target_sha256'], 'b' * 64)

    def test_nonzero_worker_without_receipt_records_unknown_delivery_failure(self):
        self.args.allow_model_calls = True
        process = SimpleNamespace(pid=123456, returncode=1, poll=lambda: 1)
        with patch.object(worker.subprocess, 'Popen', return_value=process):
            self.controller.model_turn(self.task)
        self.assertEqual(self.controller.calls[-1][0], 'call-failed')
        self.assertFalse(self.output.exists())
        failure = json.loads(self.output.with_suffix('.failure.json').read_text())['failure']
        self.assertEqual(failure['error_code'], 'propagation_model_worker_failed')
        self.assertIsNone(failure['actual_delivery'])

    def test_cached_failure_is_retained_and_forwarded_without_model_call(self):
        self.controller.interrupted_failure(self.path, self.request, self.output, [], 'synthetic_failure')
        failure_path = self.output.with_suffix('.failure.json')
        original = failure_path.read_bytes()
        with patch.object(worker.subprocess, 'Popen') as spawn:
            self.controller.model_turn(self.task)
        spawn.assert_not_called()
        self.assertEqual(failure_path.read_bytes(), original)
        self.assertEqual(self.controller.calls[-1][0], 'call-failed')

    def test_request_and_attachment_paths_cannot_escape_results(self):
        with self.assertRaises(worker.PalimpsestError):
            worker.checked_request(self.args.directory, '/results/../secret.json')
        outside = self.base / 'image.png'
        outside.write_bytes(b'synthetic')
        request = deepcopy(self.request)
        request['images'] = [{'path': '../../image.png', 'sha256': sha256(b'synthetic').hexdigest()}]
        self.path.write_text(json.dumps(request), encoding='utf-8')
        with self.assertRaises(worker.PalimpsestError) as raised:
            worker.checked_request(self.args.directory, self.task['request_file'])
        self.assertEqual(raised.exception.code, 'propagation_attachment_path_outside_workspace')

    def test_once_and_task_completion_do_not_claim_run_convergence(self):
        self.args.once = True
        self.controller.replies = [{'action': 'task_completed', 'task_state': 'done', 'run_state': 'running',
                                    'task_id': 'synthetic-task', 'lease_token': 'old-token'}]
        result = self.controller.run()
        self.assertEqual(result['state'], 'partial')
        self.assertEqual(len(self.controller.calls), 1)

    def test_task_completion_continues_until_explicit_whole_run_completion(self):
        self.controller.replies = [{'action': 'task_completed', 'task_state': 'done', 'run_state': 'running',
                'task_id': 'synthetic-task', 'lease_token': 'old-token'},
            {'state': 'completed', 'action': 'completed', 'run_state': 'completed'}]
        result = self.controller.run()
        self.assertEqual(result['state'], 'completed')
        self.assertEqual([call[0] for call in self.controller.calls], ['next', 'next'])

    def test_keyboard_interrupt_requests_durable_pause(self):
        self.controller.replies = [KeyboardInterrupt(), {'state': 'paused'}]
        result = self.controller.run()
        self.assertEqual(result['state'], 'partial')
        self.assertEqual(result['pause']['state'], 'paused')
        self.assertEqual(self.controller.calls[-1][0], 'pause')

    def test_unconfirmed_prepared_run_is_returned_without_starting_or_spinning(self):
        self.controller.replies = [{'state': 'prepared', 'action': 'prepared'}]
        result = self.controller.run()
        self.assertEqual(result['state'], 'prepared')
        self.assertEqual([call[0] for call in self.controller.calls], ['next'])

    def test_other_workers_inflight_frontier_is_polled_with_backpressure(self):
        self.controller.replies = [{'state': 'running', 'action': 'running'},
                                   {'state': 'completed', 'action': 'completed'}]
        with patch.object(worker.time, 'sleep') as sleep:
            result = self.controller.run()
        self.assertEqual(result['state'], 'completed')
        sleep.assert_called_once_with(5)

    def test_compose_command_has_readonly_artifact_repository_and_no_migration_start(self):
        controller = worker.Controller(self.args)
        captured = []
        def run(argv, **kwargs):
            captured.append((argv, kwargs))
            kwargs['stdout'].write(json.dumps({'command_status': 'succeeded', 'result': {'state': 'running'}}) + '\n')
            return SimpleNamespace(returncode=0)
        with patch.object(worker.subprocess, 'run', side_effect=run):
            result = controller.app('renew', 'synthetic-task', '--lease-token', 'sensitive-lease')
        argv, options = captured[0]
        self.assertEqual(result['state'], 'running')
        self.assertIn('--rm', argv)
        self.assertIn('--no-deps', argv)
        self.assertIn(f'{worker.ROOT.as_posix()}:/repo:ro', argv)
        self.assertIn('synthetic-artifacts:/var/lib/palimpsest/artifacts:ro', argv)
        self.assertEqual(options['env']['PALIMPSEST_APP_IMAGE'], 'palimpsest-propagation:0.16.0')
        recorded = (controller.journal.root / '000001/command.json').read_text()
        self.assertNotIn('sensitive-lease', recorded)
        self.assertIn(sha256(b'sensitive-lease').hexdigest(), recorded)
        self.assertFalse((self.args.directory / 'controller').exists())


if __name__ == '__main__':
    unittest.main()
