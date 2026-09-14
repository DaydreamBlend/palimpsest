"""Deterministic anomaly contracts with mock reads; no DB or provider calls."""

from copy import deepcopy
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

from palimpsest import propagation_anomalies as anomalies
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest


def uid(value):
    return f'019947e2-1234-7000-8000-{value:012x}'


def node(value):
    return {'knode_id': uid(value), 'knode_revision_id': uid(value + 10), 'kind': 'proposition',
        'content_fingerprint': str(value) * 64, 'identity_scope': 'source', 'source_data_id': '1' * 64,
        'current_support_record_id': None, 'current_support_signature': 'a' * 64}


def job():
    return {'operation': 'k2k', 'data_id': '1' * 64, 'input_digest': 'b' * 64,
        'profile': {'model': {'model': 'synthetic'}, 'implementation': {'runtime.py': 'c' * 64}},
        'input_snapshot': {'input': {'nodes': [node(1), node(2)]}, 'existing_nodes': [{'statement': 'Comparison context.'}],
            'existing_edges': [], 'revision_target': {'expected_revision_id': uid(300)}, 'expected_state_version': 10}}


def transition(number, before, after, before_ref, after_ref, *, previous_record=None, key='stable', kind='node'):
    return {'record_id': uid(400 + number), 'execution_id': uid(500 + number),
        'target': {'kind': kind, 'logical_id': uid(300)}, 'premise_key': key, 'basis': anomalies.basis(job(), 'node', uid(300)),
        'before_ref': before_ref, 'after_ref': after_ref, 'before_outcome': before, 'after_outcome': after,
        'previous_record_id': previous_record, 'input_digest': 'b' * 64, 'profile_sha256': 'c' * 64,
        'comparison_catalog_sha256': 'd' * 64}


def run(current):
    return {'run_id': uid(900), 'scope': {'root_record_ids': [current['record_id']], 'allowed_data_ids': ['1' * 64], 'wiki_ids': []},
        'policy': {'anomaly_detection': anomalies.PROFILE, 'model': {'model': 'synthetic'}}}


class PropagationAnomalyTests(unittest.TestCase):
    def test_basis_ignores_own_comparison_catalog_and_global_bookkeeping(self):
        first = job()
        second = deepcopy(first)
        second.update(input_digest='f' * 64, execution_id=uid(999))
        second['input_snapshot'].update(existing_nodes=[{'statement': 'Different comparison evidence.'}],
            revision_target={'expected_revision_id': uid(301)}, expected_state_version=888,
            revalidation_target={'prior_support_record_id': uid(700)})
        self.assertEqual(anomalies.basis(first, 'node', uid(300)), anomalies.basis(second, 'node', uid(300)))
        self.assertNotEqual(anomalies._audit(first)['comparison_catalog_sha256'], anomalies._audit(second)['comparison_catalog_sha256'])

    def test_actual_premise_version_support_and_policy_changes_break_basis(self):
        original = anomalies.basis(job(), 'node', uid(300))
        for change in ('revision', 'support', 'version', 'profile', 'order'):
            candidate = job()
            if change == 'revision':
                candidate['input_snapshot']['input']['nodes'][0]['knode_revision_id'] = uid(30)
            elif change == 'support':
                candidate['input_snapshot']['input']['nodes'][0]['current_support_signature'] = 'e' * 64
            elif change == 'version':
                candidate['input_snapshot'].update(data_versions=[{'version_id': uid(44), 'data_id': '1' * 64}], data_version_mode='pinned')
            elif change == 'profile':
                candidate['profile']['model']['model'] = 'other-model'
            else:
                candidate['input_snapshot']['input']['nodes'].reverse()
            with self.subTest(change=change):
                self.assertNotEqual(anomalies.basis(candidate, 'node', uid(300)), original)

    def test_unknown_legacy_support_is_not_assumed_unchanged(self):
        candidate = job()
        del candidate['input_snapshot']['input']['nodes'][0]['current_support_signature']
        with self.assertRaises(PalimpsestError):
            anomalies.basis(candidate, 'node', uid(300))

    def test_two_and_longer_returns_are_diagnostic_not_a_branch_size_cap(self):
        ab = transition(1, 'A', 'B', uid(1), uid(2))
        ba = transition(2, 'B', 'A', uid(2), uid(3), previous_record=ab['record_id'])
        self.assertTrue(anomalies.detect_cycle([ab, ba]))
        chain = [transition(n + 1, str(n), str(n + 1), uid(n + 1), uid(n + 2)) for n in range(150)]
        self.assertFalse(anomalies.detect_cycle(chain))
        chain.append(transition(151, '150', '0', uid(151), uid(152)))
        self.assertTrue(anomalies.detect_cycle(chain))
        chain[50]['premise_key'] = 'changed-real-source'
        self.assertFalse(anomalies.detect_cycle(chain))

    def test_nonmaterial_same_result_different_target_and_broken_chain_are_not_cycles(self):
        one = transition(1, 'A', 'B', uid(1), uid(2))
        for two in (transition(2, 'B', 'B', uid(2), uid(3)),
                    transition(2, 'B', 'A', uid(99), uid(3)),
                    transition(2, 'B', 'A', uid(2), uid(3), key='changed')):
            self.assertFalse(anomalies.detect_cycle([one, two]))
        other = transition(2, 'B', 'A', uid(2), uid(3))
        other['target']['logical_id'] = uid(301)
        self.assertFalse(anomalies.detect_cycle([one, other]))

    def test_old_policy_is_ignored_without_reading_any_record(self):
        conn = Mock()
        self.assertIsNone(anomalies.inspect_record(conn, {'policy': {}}, {'record_id': uid(1)}))
        conn.execute.assert_not_called()

    def test_node_witness_walks_long_cycle_and_keeps_full_context_caveat(self):
        ab = transition(1, 'A', 'B', uid(1), uid(2))
        bc = transition(2, 'B', 'C', uid(2), uid(3), previous_record=ab['record_id'])
        ca = transition(3, 'C', 'A', uid(3), uid(4), previous_record=bc['record_id'])
        ca['comparison_catalog_sha256'] = 'f' * 64
        transitions = {t['record_id']: t for t in (ab, bc, ca)}
        records = {key: {'record_id': key, 'record_type': 'k2k', 'execution_id': value['execution_id']} for key, value in transitions.items()}
        with patch.object(anomalies, '_load_record', side_effect=lambda conn, key: records.get(key)), \
                patch.object(anomalies, '_node_transition', side_effect=lambda conn, record: transitions.get(record['record_id']) if record else None), \
                patch.object(anomalies, '_node_bridges', return_value=[]):
            witness = anomalies.inspect_record(Mock(), run(ca), records[ca['record_id']])
            replay = anomalies.inspect_record(Mock(), run(ca), records[ca['record_id']])
        self.assertEqual(witness, replay)
        self.assertEqual(witness['record_id'], ca['record_id'])
        self.assertEqual(len(witness['material_transitions']), 3)
        self.assertTrue(witness['comparison_catalog_changed'])
        self.assertFalse(witness['semantic_rejection'])
        self.assertEqual(witness['context_claim'], 'same_authoritative_premises_not_full_prompt_equality')
        self.assertEqual(witness['witness_sha256'], digest({k: v for k, v in witness.items() if k != 'witness_sha256'}))

    def test_nonmaterial_target_support_with_changed_premises_breaks_node_episode(self):
        ab = transition(1, 'A', 'B', uid(1), uid(2))
        ba = transition(2, 'B', 'A', uid(2), uid(3), previous_record=ab['record_id'])
        bridge = transition(3, 'B', 'B', uid(2), uid(2), key='different-support-input')
        values = {t['record_id']: t for t in (ab, ba)}
        records = {key: {'record_id': key, 'record_type': 'k2k', 'execution_id': value['execution_id']} for key, value in values.items()}
        with patch.object(anomalies, '_load_record', side_effect=lambda conn, key: records.get(key)), \
                patch.object(anomalies, '_node_transition', side_effect=lambda conn, record: values[record['record_id']]), \
                patch.object(anomalies, '_node_bridges', return_value=[bridge]):
            self.assertIsNone(anomalies.inspect_record(Mock(), run(ba), records[ba['record_id']]))

    def test_edge_no_material_record_type_can_carry_material_false_true_return(self):
        first = transition(1, True, False, 'initial:edge', uid(2), kind='edge')
        same = transition(2, False, False, uid(2), uid(3), previous_record=first['record_id'], kind='edge')
        last = transition(3, False, True, uid(3), uid(4), previous_record=same['record_id'], kind='edge')
        values = {t['record_id']: t for t in (first, same, last)}
        records = {key: {'record_id': key, 'record_type': 'n2e', 'disposition': 'no_material_delta',
            'execution_id': value['execution_id']} for key, value in values.items()}
        with patch.object(anomalies, '_load_record', side_effect=lambda conn, key: records.get(key)), \
                patch.object(anomalies, '_edge_transition', side_effect=lambda conn, record, event=None: values[record['record_id']]), \
                patch.object(anomalies, '_event', return_value={}):
            witness = anomalies.inspect_record(Mock(), run(last), records[last['record_id']])
        self.assertEqual(len(witness['material_transitions']), 2)
        self.assertEqual(len(witness['intervening_assessments']), 1)
        self.assertEqual(witness['current_transition']['after_outcome'], True)

    def test_edge_transition_does_not_skip_an_intervening_different_pair(self):
        record = {'record_id': uid(401), 'execution_id': uid(501), 'record_type': 'n2e',
            'disposition': 'no_material_delta', 'result_edge_id': uid(300), 'result_edge_revision_id': uid(301)}
        event = {'origin_record_id': uid(401), 'kedge_id': uid(300), 'semantic_kedge_revision_id': uid(301),
            'from_knode_revision_id': uid(11), 'to_knode_revision_id': uid(12), 'event_order': 100,
            'applicable': True, 'applicability_event_id': uid(100)}
        target = {'kind': 'edge', 'target_revision_id': uid(301), 'prior_pair': [uid(11), uid(12)],
            'from_revision_id': uid(11), 'to_revision_id': uid(12), 'prior_applicable': False,
            'prior_basis_event_id': uid(98)}
        data = job()
        data['operation'] = 'n2e'
        data['input_snapshot']['revalidation_target'] = target
        different_pair = {'applicability_event_id': uid(99), 'from_knode_revision_id': uid(21),
            'to_knode_revision_id': uid(12), 'applicable': False, 'event_order': 99}
        conn = Mock()
        conn.execute.side_effect = [Mock(fetchone=lambda: {'validation': {'confirmed': True,
            'applicable': True, 'material_change': True}}), Mock(fetchone=lambda: different_pair)]
        with patch.object(anomalies, '_load_job', return_value=data):
            self.assertIsNone(anomalies._edge_transition(conn, record, event))
        sql, params = conn.execute.call_args_list[-1].args
        self.assertNotIn('from_knode_revision_id=%s', sql)
        self.assertNotIn('to_knode_revision_id=%s', sql)
        self.assertEqual(params, (uid(301), 100))

    def fresh_fixture(self):
        data = job()
        current = transition(2, 'B', 'A', uid(2), uid(3))
        current['basis'] = anomalies.basis(data, 'node', uid(300))
        workflow = run(current)
        witness = {'schema_version': anomalies.PROFILE, 'run_id': workflow['run_id'],
            'scope_sha256': digest(workflow['scope']), 'policy_sha256': digest(workflow['policy']),
            'target': current['target'], 'current_transition': current, 'basis': current['basis']}
        witness['witness_sha256'] = digest(witness)
        record = {'record_id': current['record_id'], 'execution_id': current['execution_id']}
        runtime = Mock()
        runtime._nodes.return_value = deepcopy(data['input_snapshot']['input']['nodes'])
        module = ModuleType('palimpsest.knowledge_runtime')
        module.KnowledgeRuntime = runtime
        conn = Mock()
        conn.execute.return_value.fetchone.return_value = {'usable': True, 'current_revision_id': current['after_ref'],
                                                           'support_record_id': current['record_id']}
        return workflow, witness, data, record, runtime, module, conn

    def test_acknowledgement_freshness_checks_current_support_and_never_creates_authority(self):
        workflow, witness, data, record, runtime, module, conn = self.fresh_fixture()
        with patch.object(anomalies, '_load_record', return_value=record), patch.object(anomalies, '_load_job', return_value=data), \
                patch.object(anomalies, 'inspect_record', return_value=witness), \
                patch.dict(sys.modules, {'palimpsest.knowledge_runtime': module}):
            self.assertIsNone(anomalies.assert_fresh(conn, workflow, witness))
            runtime._nodes.return_value[0]['current_support_signature'] = 'e' * 64
            with self.assertRaises(PalimpsestError) as caught:
                anomalies.assert_fresh(conn, workflow, witness)
        self.assertEqual(caught.exception.code, 'propagation_anomaly_scope_changed')
        self.assertTrue(all(call.args[0].lstrip().startswith('SELECT') for call in conn.execute.call_args_list))

    def test_changed_scope_policy_or_witness_needs_new_scope(self):
        workflow, witness, *_ = self.fresh_fixture()
        for field in ('policy', 'scope', 'witness'):
            changed_run, changed_witness = deepcopy(workflow), deepcopy(witness)
            if field == 'policy':
                changed_run['policy']['model']['model'] = 'new-model'
            elif field == 'scope':
                changed_run['scope']['allowed_data_ids'] = ['2' * 64]
            else:
                changed_witness['current_transition']['after_ref'] = uid(999)
            with self.subTest(field=field), self.assertRaises(PalimpsestError) as caught:
                anomalies.assert_fresh(Mock(), changed_run, changed_witness)
            self.assertEqual(caught.exception.code, 'propagation_anomaly_scope_changed')


if __name__ == '__main__':
    unittest.main()
