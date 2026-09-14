"""Pure orchestration regressions; no database, source files or provider calls."""

from contextlib import contextmanager, nullcontext
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from palimpsest.errors import PalimpsestError
from palimpsest.propagation_runtime import PropagationRuntime


class PropagationRuntimeUnitTests(unittest.TestCase):
    def runtime(self):
        worker = PropagationRuntime.__new__(PropagationRuntime)
        worker.dsn = 'never-connected'
        worker.queue, worker.knowledge = Mock(), Mock()
        return worker

    def test_discovery_dependency_release_requires_every_current_input_and_leaves_human_holds(self):
        worker = self.runtime()
        tasks = [{'task_id': operation, 'kind': operation, 'state': 'blocked',
            'error_code': 'propagation_dependency_waiting', 'payload': {'node_ids': ['node-a', 'node-b']}}
            for operation in ('n2e', 'k2k')]
        tasks.append({**deepcopy(tasks[0]), 'task_id': 'human', 'error_code': 'knowledge_needs_human'})
        worker.queue.show.return_value = {'state': 'running', 'tasks': tasks}
        nodes = [{'knode_id': 'node-a', 'knode_revision_id': 'revision-a'},
                 {'knode_id': 'node-b', 'knode_revision_id': 'revision-b'}]
        usable = {'revision-a': True, 'revision-b': True}
        conn = Mock()
        conn.execute.side_effect = lambda sql, params: SimpleNamespace(fetchone=lambda: {'ok': usable[params[0]]})
        with patch('palimpsest.propagation_runtime.connection', side_effect=lambda _: nullcontext(conn)):
            worker.knowledge._nodes.return_value = nodes[:1]
            worker._release_dependencies('run')
            worker.queue.retry.assert_not_called()
            worker.knowledge._nodes.return_value = nodes
            usable['revision-b'] = False
            worker._release_dependencies('run')
            worker.queue.retry.assert_not_called()
            usable['revision-b'] = True
            worker._release_dependencies('run')
            self.assertEqual([call.args[0] for call in worker.queue.retry.call_args_list], ['n2e', 'k2k'])
            worker.queue.retry.reset_mock()
            worker.queue.show.return_value['state'] = 'paused'
            worker._release_dependencies('run')
            worker.queue.retry.assert_not_called()

    def accept_fixture(self, error):
        worker = self.runtime()
        task = {'task_id': 'task', 'kind': 'k2k', 'request_id': 'old-request', 'run_id': 'run'}
        worker._task = Mock(return_value=task)
        worker._execution = Mock(return_value='execution')
        conn = Mock()
        order, entered = [], []

        @contextmanager
        def transaction(task_id, token):
            entered.append(True)
            order.append('transaction_entered')
            try:
                yield conn, task, {'run_id': 'run'}
            finally:
                order.append('transaction_exited')
                entered.pop()

        def transport_success(*args):
            self.assertFalse(entered, 'The public helper owns a new DB transaction and must not nest its locks.')
            order.append('transport_succeeded')

        worker.queue.transaction.side_effect = transaction
        worker.queue.transport_succeeded.side_effect = transport_success
        worker.queue.rotate_request.side_effect = lambda *args: order.append('request_rotated')
        worker.knowledge.stage.side_effect = error
        worker.advance = Mock(side_effect=lambda *args: (order.append('advanced') or {'action': 'model_request'}))
        exchange = {'response': {'nodes': []}, 'receipt': {'actual_delivery': True}}
        return worker, exchange, order

    def test_successful_transport_with_stale_semantic_input_resets_streak_after_fenced_rotation(self):
        worker, exchange, order = self.accept_fixture(PalimpsestError('knowledge_state_changed', 'Synthetic stale input.', 6))
        result = worker.accept('task', 'token', 'generator', exchange)
        self.assertEqual(result['action'], 'model_request')
        worker.queue.rotate_request.assert_called_once()
        worker.queue.transport_succeeded.assert_called_once_with('task', 'token', 'generator')
        self.assertLess(order.index('request_rotated'), order.index('transport_succeeded'))
        self.assertLess(order.index('transport_succeeded'), order.index('advanced'))
        worker.queue.block.assert_not_called()

    def test_invalid_receipt_does_not_claim_transport_success_or_automatically_retry(self):
        worker, exchange, _ = self.accept_fixture(PalimpsestError('knowledge_provider_receipt_mismatch', 'Synthetic malformed receipt.', 6))
        result = worker.accept('task', 'token', 'generator', exchange)
        self.assertEqual(result['action'], 'blocked')
        worker.queue.transport_succeeded.assert_not_called()
        worker.queue.rotate_request.assert_not_called()
        worker.advance.assert_not_called()
        self.assertEqual(worker.queue.block.call_args.args[2], 'knowledge_invalid_response')

    def test_lost_claim_cannot_reset_transport_streak_or_publish_retry(self):
        worker, exchange, _ = self.accept_fixture(PalimpsestError('propagation_claim_lost', 'Synthetic expired lease.', 6))
        with self.assertRaises(PalimpsestError) as caught:
            worker.accept('task', 'token', 'generator', exchange)
        self.assertEqual(caught.exception.code, 'propagation_claim_lost')
        worker.queue.transport_succeeded.assert_not_called()
        worker.queue.rotate_request.assert_not_called()
        worker.queue.block.assert_not_called()
        worker.advance.assert_not_called()
