"""Revision hooks with real pure contracts and scripted SQL; no database runs."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace, ModuleType
import unittest
from unittest.mock import Mock, patch

from palimpsest import knowledge_revision_runtime as runtime
from palimpsest import knowledge_revision as revision
from palimpsest import multi_source_i2k as multi, k2k
from palimpsest.errors import PalimpsestError
from palimpsest.i2k_selection import selection_fingerprints
from palimpsest import cli, knowledge_requests
import test_knowledge_revision as fixture
import test_multi_source_i2k as multi_fixture
import test_k2k as inference_fixture


def decision(verdict='accepted', target=None):
    return {'candidate_key': 'change', 'verdict': verdict, 'equivalent_candidate_key': None,
        'equivalent_revision_id': target, 'reason_codes': ['synthetic_checked'],
        'reason': 'Independent ordinary validation has run.'}


class Cursor:
    def __init__(self, value):
        self.value = value

    def fetchone(self):
        return self.value

    def fetchall(self):
        return self.value


class ScriptedConnection:
    """Return an ordered query script; this is explicitly not a PG substitute."""
    def __init__(self, *results):
        self.results, self.calls = list(results), []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if not self.results:
            raise AssertionError('Unexpected SQL call')
        value = self.results.pop(0)
        if isinstance(value, Exception):
            raise value
        return Cursor(value)


class KnowledgeRevisionRuntimeTests(unittest.TestCase):
    def reject(self, callback, code):
        with self.assertRaises(PalimpsestError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_freeze_selects_exact_current_catalog_without_raw_source_context(self):
        row = {**fixture.target(), 'direct_data_groundings': [{'quote': 'RAW_PRIVATE'}]}
        target = runtime.freeze_request([row], operation='i2k', target_knode_id=fixture.uid(1),
                                        expected_revision_id=fixture.uid(2))
        self.assertEqual(target, fixture.comparison())
        self.assertNotIn('RAW_PRIVATE', json.dumps(target))
        for rows, expected in (([], fixture.uid(2)), ([row, row], fixture.uid(2)), ([row], fixture.uid(99))):
            self.reject(lambda: runtime.freeze_request(rows, operation='i2k',
                target_knode_id=fixture.uid(1), expected_revision_id=expected), 'knowledge_revision_target_changed')
        self.reject(lambda: runtime.freeze_request([row], operation='d2k', target_knode_id=fixture.uid(1),
            expected_revision_id=fixture.uid(2)), 'knowledge_revision_operation_unsupported')
        self.reject(lambda: runtime.bind_candidates([], fixture.comparison('d2k')), 'knowledge_revision_operation_unsupported')

    def test_ordinary_multi_wire_remains_strict_and_independently_validated(self):
        packet = multi.combine_packets([multi_fixture.packet(1), multi_fixture.packet(2)])
        raw = multi_fixture.proposal(packet)
        ordinary = multi.normalize_proposals(raw, packet)['nodes']
        old = {**fixture.target(), 'identity_scope': 'general', 'source_data_id': None}
        old.update(selection_fingerprints(old['kind'], old['semantic_payload'], 'general'))
        target = fixture.comparison(value=old)
        schema = multi.generation_schema(packet)
        before = deepcopy((schema, raw))
        prompt, wrapped = runtime.generation_request('ordinary source-only prompt', schema, target)
        self.assertEqual(wrapped['properties']['nodes']['maxItems'], 1)
        self.assertEqual(wrapped['properties']['nodes']['items'], schema['properties']['nodes']['items'])
        self.assertIn('EXPLICIT_TARGET_JSON', prompt)
        injected = deepcopy(raw); injected['nodes'][0]['revision_target'] = target
        with self.assertRaises(PalimpsestError):
            multi.normalize_proposals(injected, packet)
        candidates = runtime.bind_candidates(ordinary, target)
        self.assertEqual(candidates[0]['evidence'], ordinary[0]['evidence'])
        self.assertEqual(candidates[0]['identity_fingerprint'], old['identity_fingerprint'])
        response = {**multi_fixture.decisions(packet), 'revision_review': fixture.review()}
        validation_schema = multi.validation_schema(['claim'], [fixture.uid(2)], packet)
        _, wrapped_validation = runtime.validation_request('ordinary validation', validation_schema, target, candidates)
        self.assertEqual(wrapped_validation['properties']['revision_review'], revision.review_schema(target))
        self.assertEqual(set(wrapped_validation['required']), {*validation_schema['required'], 'revision_review'})
        base, reviewed = runtime.split_validation(response, target, candidates)
        checked = multi.validate_decisions(base, candidates, [fixture.uid(2)], packet)
        self.assertEqual(runtime.resolve_decisions(candidates, checked['decisions'], target, reviewed)['claim']['action'],
                         'accepted_revision')
        false_check = deepcopy(base); false_check['decisions'][0]['source_explicit'] = False
        with self.assertRaises(PalimpsestError):
            multi.validate_decisions(false_check, candidates, [fixture.uid(2)], packet)
        self.assertEqual((schema, raw), before)

    def test_k2k_ordinary_premise_checks_survive_wrapper_and_origin_is_actual_k2k(self):
        packet, raw = inference_fixture.packet(), inference_fixture.response()
        ordinary = k2k.normalize_proposals(raw, packet)
        old = {**fixture.target(), 'identity_scope': 'general', 'source_data_id': None}
        old.update(selection_fingerprints(old['kind'], old['semantic_payload'], 'general'))
        target = fixture.comparison('k2k', value=old)
        candidates = runtime.bind_candidates(ordinary, target)
        self.assertEqual(candidates[0]['premise_revision_ids'], ordinary[0]['premise_revision_ids'])
        self.assertNotIn('evidence', candidates[0])
        response = {'decisions': [inference_fixture.decision()], 'complete': True,
                    'revision_review': fixture.review()}
        base, reviewed = runtime.split_validation(response, target, candidates)
        checked = k2k.validate_decisions(base, candidates, [fixture.uid(2)])
        result = runtime.resolve_decisions(candidates, checked['decisions'], target, reviewed)['inference']
        self.assertEqual(result['origin'], {'mode': 'new_record', 'origin_operation': 'k2k', 'is_inferred': True})
        base['decisions'][0]['premises_sufficient'] = False
        with self.assertRaises(PalimpsestError):
            k2k.validate_decisions(base, candidates, [fixture.uid(2)])

    def test_zero_candidates_is_unresolved_and_cannot_carry_a_materiality_review(self):
        target = fixture.comparison()
        self.assertEqual(runtime.bind_candidates([], target), [])
        self.reject(lambda: runtime.bind_candidates([fixture.candidate(), fixture.candidate()], target),
                    'knowledge_revision_single_candidate_required')
        schema = k2k.validation_schema([], [fixture.uid(2)])
        _, wrapped = runtime.validation_request('prompt', schema, target, [])
        self.assertEqual(wrapped['properties']['revision_review'], {'type': 'null'})
        base, reviewed = runtime.split_validation({'decisions': [], 'complete': True, 'revision_review': None}, target, [])
        self.assertTrue(base['complete'])
        self.assertEqual(runtime.resolve_decisions([], {}, target, reviewed), {})
        self.reject(lambda: runtime.split_validation({'revision_review': fixture.review()}, target, []),
                    'invalid_knowledge_revision_review')
        self.reject(lambda: runtime.split_validation({}, target, []), 'invalid_knowledge_revision_review')

    def test_nonmaterial_reuses_target_and_never_overwrites_existing_origin(self):
        target, candidate = fixture.comparison(), fixture.candidate()
        for base in (decision(), decision('reused', fixture.uid(2))):
            result = runtime.resolve_decisions([candidate], {'change': base}, target, fixture.review(False))['change']
            self.assertEqual(result['action'], 'reused')
            self.assertEqual(result['result_content_fingerprint'], target['target']['content_fingerprint'])
            self.assertEqual(result['origin'], {'mode': 'preserve_existing', 'origin_record_id': fixture.uid(3)})
            self.assertEqual(result['decision'], base)

    def test_ordinary_hold_or_rejection_cannot_be_upgraded_by_materiality(self):
        for verdict in ('needs_human', 'rejected'):
            base = decision(verdict)
            result = runtime.resolve_decisions([fixture.candidate()], {'change': base}, fixture.comparison(), fixture.review())['change']
            self.assertEqual(result['action'], verdict)
            self.assertEqual(result['origin'], {'mode': 'no_publication'})
            self.assertEqual(result['decision'], base)
        for base, material, reason in (
                (decision('reused', fixture.uid(99)), False, 'knowledge_revision_reuse_target_mismatch'),
                (decision('reused', fixture.uid(2)), True, 'knowledge_revision_materiality_conflict')):
            result = runtime.resolve_decisions([fixture.candidate()], {'change': base}, fixture.comparison(), fixture.review(material))['change']
            self.assertEqual(result['action'], 'needs_human')
            self.assertIn(reason, result['reason_codes'])

    def commit_input(self):
        target = fixture.comparison()
        candidate = runtime.bind_candidates([fixture.candidate()], target)[0]
        record = {'record_id': fixture.uid(80), 'record_type': 'i2k', 'disposition': 'pending', 'body': candidate}
        result = runtime.resolve_decisions([candidate], {'change': decision()}, target, fixture.review())['change']
        row = {k: v for k, v in target['target'].items() if k != 'current_applicability'}
        return target, candidate, record, result, row

    def test_commit_inserts_only_successor_with_fixed_logical_identity_and_exact_cas(self):
        target, candidate, record, result, row = self.commit_input()
        conn = ScriptedConnection(row, {'knode_revision_id': fixture.uid(81)}, {'knode_id': fixture.uid(1)})
        node = runtime.commit_revision(conn, record, candidate, target, result)
        self.assertEqual(node['knode_id'], fixture.uid(1))
        self.assertEqual(node['knode_revision_id'], fixture.uid(81))
        self.assertEqual(node['current_revision_id'], fixture.uid(81))
        self.assertEqual(node['identity_fingerprint'], row['identity_fingerprint'])
        self.assertEqual(node['origin_record_id'], record['record_id'])
        self.assertEqual(node['supersedes_revision_id'], fixture.uid(2))
        self.assertIn('FOR UPDATE OF n', conn.calls[0][0])
        sql, params = conn.calls[1]
        self.assertIn('INSERT INTO canonical_store.knowledge_node_revisions', sql)
        self.assertEqual(params[0], fixture.uid(1))
        self.assertEqual(params[3], row['identity_fingerprint'])
        self.assertEqual(params[-1], fixture.uid(2))
        self.assertEqual(conn.calls[2][1], (fixture.uid(81), fixture.uid(1), fixture.uid(2)))
        self.assertNotIn('identity_fingerprint', conn.calls[2][0])
        self.assertFalse(any('groundings' in sql or 'k_outbox' in sql or 'INSERT INTO canonical_store.knowledge_nodes' in sql
                             for sql, _ in conn.calls))

    def test_stale_target_is_rejected_before_insert_and_failed_cas_raises(self):
        target, candidate, record, result, row = self.commit_input()
        for current in (None, {**row, 'current_revision_id': fixture.uid(99)},
                        {**row, 'content_fingerprint': 'f' * 64}):
            conn = ScriptedConnection(current)
            self.reject(lambda: runtime.commit_revision(conn, record, candidate, target, result),
                        'knowledge_revision_target_changed')
            self.assertEqual(len(conn.calls), 1)
        conn = ScriptedConnection(row, {'knode_revision_id': fixture.uid(81)}, None)
        self.reject(lambda: runtime.commit_revision(conn, record, candidate, target, result),
                    'knowledge_revision_target_changed')

    def test_commit_rejects_forged_resolution_record_operation_body_and_no_materiality(self):
        target, candidate, record, result, _ = self.commit_input()
        for field, value in (('record_type', 'k2k'), ('disposition', 'accepted_new'), ('body', fixture.candidate())):
            conn = ScriptedConnection()
            self.reject(lambda: runtime.commit_revision(conn, {**record, field: value}, candidate, target, result),
                        'invalid_knowledge_revision_record')
            self.assertEqual(conn.calls, [])
        changed = deepcopy(result); changed['origin']['is_inferred'] = True
        conn = ScriptedConnection()
        self.reject(lambda: runtime.commit_revision(conn, record, candidate, target, changed), 'knowledge_revision_not_accepted')
        reused = runtime.resolve_decisions([candidate], {'change': decision()}, target, fixture.review(False))['change']
        self.reject(lambda: runtime.commit_revision(conn, record, candidate, target, reused), 'knowledge_revision_not_accepted')
        self.assertEqual(conn.calls, [])

    def test_impacts_keep_all_historical_exact_refs_without_mutation_or_cutoff(self):
        rows = [{'record_id': fixture.uid(100 + i), 'result_node_revision_id': fixture.uid(6000 + i),
                 'premise_node_revision_id': fixture.uid(2), 'ordinal': 0} for i in range(3000)]
        edges = [{'kedge_id': fixture.uid(90), 'kedge_revision_id': fixture.uid(91),
                  'from_knode_revision_id': fixture.uid(2), 'to_knode_revision_id': fixture.uid(92)}]
        events = [{'applicability_event_id': fixture.uid(93), 'event_order': 1, 'applicable': False}]
        links = [{'link_id': fixture.uid(94), 'request_id': fixture.uid(95), 'wiki_id': fixture.uid(96),
                  'snapshot_id': fixture.uid(97), 'item_key': 'historical-item', 'knode_id': fixture.uid(1),
                  'node_revision_id': fixture.uid(2)}]
        conn = ScriptedConnection(rows, edges, events, {'available': True}, links)
        result = runtime.enumerate_impacts(conn, fixture.uid(2))
        self.assertEqual(result['derivations'], rows)
        self.assertEqual(result['edges'], edges)
        self.assertEqual(result['edge_applicability'], events)
        self.assertEqual(result['wiki_links'], links)
        self.assertTrue(result['wiki_available'])
        self.assertTrue(all(sql.lstrip().startswith('SELECT') for sql, _ in conn.calls))
        self.assertFalse(any('LIMIT' in sql or 'current_revision_id' in sql for sql, _ in conn.calls))
        self.assertEqual(conn.calls[-1][1], (fixture.uid(2),))

    def test_optional_wiki_absence_is_reported_but_read_errors_are_not_hidden(self):
        conn = ScriptedConnection([], [], [], {'available': False})
        result = runtime.enumerate_impacts(conn, fixture.uid(2))
        self.assertFalse(result['wiki_available'])
        self.assertEqual(result['wiki_links'], [])
        conn = ScriptedConnection([], [], [], {'available': True}, PermissionError('denied'))
        with self.assertRaises(PermissionError):
            runtime.enumerate_impacts(conn, fixture.uid(2))

    def test_pure_wrappers_do_not_read_source_or_call_providers_and_preserve_inputs(self):
        candidate, target = fixture.candidate(), fixture.comparison()
        before = deepcopy((candidate, target))
        with patch('builtins.open', side_effect=AssertionError('No source reads')), \
                patch('subprocess.run', side_effect=AssertionError('No model/process calls')):
            bound = runtime.bind_candidates([candidate], target)
            result = runtime.resolve_decisions(bound, {'change': decision()}, target, fixture.review())
        self.assertEqual(result['change']['action'], 'accepted_revision')
        self.assertEqual((candidate, target), before)

    def test_public_prompt_paths_only_add_revision_wire_for_explicit_snapshots(self):
        packet = multi.combine_packets([multi_fixture.packet(1)])
        assets = [{'sha256': asset['sha256'], 'byte_size': asset['byte_size']} for asset in packet['media_assets']]
        snapshot = {'input': packet, 'existing_nodes': [], 'existing_edges': []}
        ordinary = knowledge_requests.generation_request(snapshot, assets)
        explicit = knowledge_requests.generation_request({**snapshot, 'revision_target': fixture.comparison()}, assets)
        self.assertNotIn('EXPLICIT_TARGET_JSON', ordinary[0])
        self.assertIn('EXPLICIT_TARGET_JSON', explicit[0])
        self.assertNotIn('maxItems', ordinary[1]['properties']['nodes'])
        self.assertEqual(explicit[1]['properties']['nodes']['maxItems'], 1)
        inference = {'input': inference_fixture.packet(), 'existing_nodes': []}
        self.assertEqual(k2k.generation_request(inference),
                         (k2k.generation(inference), k2k.generation_schema(inference['input'])))
        wrapped = k2k.generation_request({**inference, 'revision_target': fixture.comparison('k2k')})
        self.assertIn('EXPLICIT_TARGET_JSON', wrapped[0])
        self.assertEqual(wrapped[1]['properties']['nodes']['maxItems'], 1)

    def test_cli_forwards_paired_target_without_changing_source_packet_and_exposes_request_export(self):
        provider = Mock()
        provider.request_profile.return_value = None
        provider.prepare.return_value = {'state': 'prepared'}
        module = ModuleType('palimpsest.knowledge_runtime')
        module.KnowledgeRuntime = Mock(return_value=provider)
        packet = multi_fixture.packet(1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.json'
            path.write_text(json.dumps(packet), encoding='utf-8')
            args = cli._parser().parse_args(['knowledge', 'prepare', '--operation', 'i2k',
                '--data-id', packet['data_id'], '--request-id', fixture.uid(80), '--input', str(path),
                '--target-knode-id', fixture.uid(1), '--expected-revision-id', fixture.uid(2)])
            with patch.dict('sys.modules', {'palimpsest.knowledge_runtime': module}):
                cli._knowledge(args, SimpleNamespace(database_dsn='unused'))
            self.assertEqual(provider.prepare.call_args.args[3], multi.combine_packets([packet]))
            self.assertEqual(provider.prepare.call_args.kwargs['target_knode_id'], fixture.uid(1))
            self.assertEqual(provider.prepare.call_args.kwargs['expected_revision_id'], fixture.uid(2))
            export = cli._parser().parse_args(['knowledge', 'revision-call', fixture.uid(81),
                '--phase', 'validator', '--directory', directory])
            self.assertEqual((export.action, export.phase), ('revision-call', 'validator'))

    def test_k2k_export_binds_target_without_images_and_rejects_coordinated_file_tamper(self):
        from palimpsest.wiki_projection_store import ProjectionStore
        from palimpsest.knowledge import _digest
        from contextlib import nullcontext
        target = fixture.comparison('k2k')
        snapshot = {'input': inference_fixture.packet(), 'existing_nodes': [], 'revision_target': target}
        job = {'execution_id': fixture.uid(82), 'operation': 'k2k', 'state': 'prepared',
               'input_snapshot': snapshot, 'input_digest': 'a' * 64,
               'profile': {'explicit_knowledge_revision': runtime.PROFILE}}
        service = Mock(); service.show.return_value = job
        documents = {}
        store = Mock(spec=ProjectionStore)
        store.root = Path('/synthetic-export')
        store.locked.side_effect = lambda: nullcontext()
        store.read_json.side_effect = lambda name: deepcopy(documents.get(name))
        store.write_json.side_effect = lambda name, value: documents.update({name: deepcopy(value)})
        with patch('palimpsest.wiki_projection_store.ProjectionStore', return_value=store), \
                patch('subprocess.run', side_effect=AssertionError('No model calls')):
            first = runtime.prepare_call(service, job['execution_id'], 'generator', '/unused')
            request = documents['generator-request.json']
            self.assertEqual(request['images'], [])
            self.assertEqual(request['delivered_revision_target_id'], fixture.uid(2))
            self.assertEqual(request['delivered_knowledge_revision_ids'], [fixture.uid(11), fixture.uid(12)])
            self.assertFalse(first['actual_delivery'])
            self.assertTrue(runtime.prepare_call(service, job['execution_id'], 'generator', '/unused')['replayed'])
            request['prompt'] += '\nUntrusted rewrite'
            documents['generator-binding.json']['request_sha256'] = _digest(request)
            self.reject(lambda: runtime.prepare_call(service, job['execution_id'], 'generator', '/unused'),
                        'knowledge_call_directory_conflict')


if __name__ == '__main__':
    unittest.main()
