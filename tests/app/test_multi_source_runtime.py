"""Real isolated PG multi-source I2K, with synthetic/no-model receipts.

The source fixtures, semantic proposals and validator verdicts are synthetic.
These checks establish persistence and boundary enforcement, not entailment or
LLM quality. The caller provisions PALIMPSEST_TEST_DSN; this suite never migrates,
resets a database, modifies a user paper, or calls a model.
"""

from copy import deepcopy
from hashlib import sha256
import os
import unittest
from uuid import uuid4

from palimpsest.canonical_store import connection
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.knowledge import source_block_ranges
from palimpsest import multi_source_i2k as multi
from palimpsest import multi_source_prompts as prompts

import test_selection_runtime as source_fixtures


@unittest.skipUnless(os.environ.get('PALIMPSEST_TEST_DSN'), 'Requires explicitly provisioned PALIMPSEST_TEST_DSN')
class MultiSourceRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.fixture_owner = source_fixtures.SelectionRuntimeTests('runTest')
        self.addCleanup(self.fixture_owner.doCleanups)
        self.first = self.fixture_owner._fixture()
        self.second = self.fixture_owner._fixture()
        self.runtime, self.dsn = self.first.runtime, self.first.dsn
        self.bundle = multi.combine_packets([self.first.packet, self.second.packet])
        self.data_ids = {self.first.data_id, self.second.data_id}
        self.subject = 'Synthetic isolated fixture ' + self.first.data_id

    def prepare(self, *, bundle=None, request=None):
        selected = bundle or self.bundle
        return self.runtime.prepare('i2k', selected['data_id'], request or self.first.repo.allocate_id(),
                                    selected, selection=True, source_review=False)

    def response(self, *, general_only=False):
        def citation(helper):
            return {'information_id': helper.text['information_id'], 'quote': helper.text['content'],
                    'media_sha256': None, 'source_role': 'results'}

        def proposal(key, kind, owner, citations):
            return {'candidate_key': key, 'kind': kind, 'statement': 'Synthetic source-explicit storage assertion.',
                'semantic_payload': {'subject': self.subject, 'relation': 'reports a fixture value',
                    'object': '2-9', 'polarity': 'positive', 'quantifier': 'reported fixture',
                    'scope': 'synthetic persistence check only', 'conditions': [], 'time_range': ''},
                'evidence': citations, 'uncertainties': [],
                'identity_scope': 'general' if owner is None else 'source', 'source_data_id': owner,
                'selection_reason': 'Synthetic useful statement; semantic acceptance is an explicit fixture.',
                'claim_basis': 'explicit_source_content', 'is_inferred': False}

        nodes = [proposal('shared_general', 'proposition', None, [citation(self.first), citation(self.second)])]
        if not general_only:
            # Identical semantic values still describe two distinct source-owned observations.
            nodes.extend([proposal('observation_a', 'observation', self.first.data_id, [citation(self.first)]),
                          proposal('observation_b', 'observation', self.second.data_id, [citation(self.second)])])
        result = {'nodes': nodes, 'source_requests': [], 'complete': True,
                  'coverage_notes': ['Synthetic/no-model storage fixture; not a scientific quality result.'], 'reviews': []}
        for unit in self.bundle['model_input']['information']:
            keys = [node['candidate_key'] for node in nodes
                    if any(item['information_id'] == unit['information_id'] for item in node['evidence'])]
            result['reviews'].append({'information_id': unit['information_id'], 'candidate_keys': keys,
                'disposition': 'selected' if keys else 'context_only',
                'reason': 'Synthetic selected evidence.' if keys else 'Synthetic reviewed context.'})
        return result

    @staticmethod
    def decisions(response):
        return {'complete': True, 'decisions': [{'candidate_key': node['candidate_key'], 'verdict': 'accepted',
            'equivalent_candidate_key': None, 'equivalent_revision_id': None,
            'reason_codes': ['synthetic_fixture'], 'reason': 'Synthetic acceptance; no semantic model was called.',
            'scope_correct': True, 'importance_justified': True,
            'source_explicit': True, 'no_novel_inference': True, 'source_identity_preserved': True}
            for node in response['nodes']],
            'reviews': [{'information_id': review['information_id'], 'verdict': 'confirmed',
                         'reason_codes': ['synthetic_review'], 'reason': 'Synthetic independent review receipt.'}
                        for review in response['reviews']]}

    def receipt(self, job, output, phase):
        current = self.runtime.show(job['execution_id'])
        snapshot = current['input_snapshot']
        bundle = snapshot['input']
        attachments = [{'sha256': asset['sha256'], 'byte_size': asset['byte_size']}
                       for asset in bundle['media_assets']]
        if phase == 'generator':
            input_sha = current['input_digest']
            prompt = prompts.generation(snapshot, attachments)
            schema = multi.generation_schema(bundle)
        else:
            context = self.runtime.validation_context(job['execution_id'])
            input_sha = context['validation_context_sha']
            prompt = prompts.validation(context, attachments)
            schema = multi.validation_schema([node['candidate_key'] for node in context['candidates']],
                [node['knode_revision_id'] for node in snapshot['existing_nodes']], bundle)
        return {'profile': {**current['profile']['model'], 'synthetic_receipt': True},
                'input_sha256': input_sha, 'output_sha256': digest(output),
                'prompt_sha256': sha256(prompt.encode('utf-8')).hexdigest(), 'schema_sha256': digest(schema),
                'provider_ref': 'synthetic-no-model-' + str(uuid4()), 'actual_delivery': True,
                'delivered_information_ids': multi.check_input(bundle), 'image_attachments': attachments,
                'usage': {}, 'test_only': True, 'original_pdf_delivered': False}

    def stage(self, job, response):
        return self.runtime.stage(job['execution_id'], response, self.receipt(job, response, 'generator'))

    def accept(self, job, response, decisions=None):
        self.stage(job, response)
        decisions = decisions or self.decisions(response)
        return self.runtime.decide(job['execution_id'], decisions, self.receipt(job, decisions, 'validator'))

    def error(self, expected, call):
        with self.assertRaises(PalimpsestError) as caught:
            call()
        self.assertEqual(caught.exception.code, expected)

    def _no_graph(self):
        self.assertEqual(self.runtime.graph(self.first.data_id)['nodes'], [])
        self.assertEqual(self.runtime.graph(self.second.data_id)['nodes'], [])

    def test_one_general_k_commits_exact_groundings_from_two_data(self):
        response, job = self.response(general_only=True), self.prepare()
        result = self.accept(job, response)
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(len(result['records']), 1)
        record = result['records'][0]
        with connection(self.dsn) as conn:
            sources = conn.execute('SELECT * FROM compiler_runtime.k_execution_sources WHERE execution_id=%s ORDER BY ordinal',
                                   (job['execution_id'],)).fetchall()
            grounding = conn.execute('''SELECT g.*,i.data_id FROM canonical_store.knowledge_node_groundings g
                JOIN canonical_store.information i USING(information_id) WHERE g.node_revision_id=%s''',
                (record['result_node_revision_id'],)).fetchall()
            scope = conn.execute('SELECT * FROM canonical_store.knowledge_node_scopes WHERE knode_id=%s',
                                 (record['result_node_id'],)).fetchone()
        self.assertEqual([source['data_id'] for source in sources], [self.first.data_id, self.second.data_id])
        self.assertEqual({row['data_id'] for row in grounding}, self.data_ids)
        self.assertEqual(len(grounding), 2)
        self.assertEqual(scope['identity_scope'], 'general')
        self.assertIsNone(scope['source_data_id'])
        self.assertEqual({str(row['information_id']) for row in grounding},
                         {self.first.text['information_id'], self.second.text['information_id']})
        for row in grounding:
            helper = self.first if row['data_id'] == self.first.data_id else self.second
            self.assertEqual(helper.text['content'][row['char_start']:row['char_end']], row['quote'])
            self.assertEqual(str(row['origin_record_id']), record['record_id'])

    def block_response(self):
        response = self.response(general_only=True)
        expected = {}
        response['nodes'][0]['evidence'] = []
        for helper in (self.first, self.second):
            unit = helper.text
            ranges = source_block_ranges(unit)
            self.assertTrue(ranges, 'The actual source fixture must expose at least one grounded text block')
            block, span = next(iter(ranges.items()))
            response['nodes'][0]['evidence'].append({'information_id': unit['information_id'],
                'source_block_id': block, 'source_role': 'results'})
            expected[unit['information_id']] = {'block': block, 'start': span[0], 'end': span[1],
                'quote': unit['content'][span[0]:span[1]], 'data_id': helper.data_id}
        return response, expected

    def test_block_addresses_resolve_two_data_exact_quotes_and_commit(self):
        response, expected = self.block_response()
        job = self.prepare()
        context = self.stage(job, response)
        citations = context['candidates'][0]['evidence']
        self.assertEqual(len(citations), 2)
        for citation in citations:
            target = expected[citation['information_id']]
            self.assertEqual((citation['source_block_id'], citation['char_start'], citation['char_end'], citation['quote']),
                             (target['block'], target['start'], target['end'], target['quote']))
            self.assertEqual(citation['data_id'], target['data_id'])
            self.assertIsNone(citation['media_sha256'])
        decisions = self.decisions(response)
        result = self.runtime.decide(job['execution_id'], decisions, self.receipt(job, decisions, 'validator'))
        self.assertEqual(result['state'], 'completed')
        revision_id = result['records'][0]['result_node_revision_id']
        with connection(self.dsn) as conn:
            rows = conn.execute('''SELECT g.*,i.data_id,i.content FROM canonical_store.knowledge_node_groundings g
                JOIN canonical_store.information i USING(information_id) WHERE node_revision_id=%s''', (revision_id,)).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual({row['data_id'] for row in rows}, self.data_ids)
        for row in rows:
            target = expected[str(row['information_id'])]
            self.assertEqual(row['quote'], row['content'][row['char_start']:row['char_end']])
            self.assertEqual((row['char_start'], row['char_end'], row['quote']),
                             (target['start'], target['end'], target['quote']))
            self.assertEqual(row['data_id'], target['data_id'])
        node = self.runtime.graph(self.first.data_id)['nodes'][0]
        self.assertEqual(node['identity_scope'], 'general')
        self.assertIsNone(node['source_data_id'])
        self.assertIs(node['generation_origin']['is_inferred'], False)

    def test_unowned_block_and_model_supplied_offsets_cannot_create_canonical_k(self):
        response, _ = self.block_response()
        job = self.prepare()
        spoofed = deepcopy(response)
        spoofed['nodes'][0]['evidence'][0]['source_block_id'] = '/unowned/source/block'
        self.error('invalid_knowledge_block_reference', lambda: self.stage(job, spoofed))
        supplied_offsets = deepcopy(response)
        supplied_offsets['nodes'][0]['evidence'][0].update(char_start=0, char_end=1)
        self.error('invalid_knowledge_evidence', lambda: self.stage(job, supplied_offsets))
        current = self.runtime.show(job['execution_id'])
        self.assertEqual(current['state'], 'prepared')
        self.assertEqual(current['records'], [])
        self.assertEqual(current['information_reviews'], [])
        self._no_graph()

    def test_same_values_from_distinct_source_owners_remain_separate_observations(self):
        response = self.response()
        result = self.accept(self.prepare(), response)
        self.assertEqual(result['state'], 'completed')
        record_ids = [record['record_id'] for record in result['records']]
        with connection(self.dsn) as conn:
            observations = conn.execute('''SELECT n.knode_id,r.knode_revision_id,r.semantic_payload,r.identity_fingerprint,
                s.identity_scope,s.source_data_id FROM canonical_store.knowledge_nodes n
                JOIN canonical_store.knowledge_node_revisions r ON r.knode_revision_id=n.current_revision_id
                JOIN canonical_store.knowledge_node_scopes s ON s.knode_id=n.knode_id
                WHERE r.origin_record_id=ANY(%s::uuid[]) AND n.kind='observation' ''', (record_ids,)).fetchall()
            checks = conn.execute('SELECT * FROM compiler_runtime.k_explicit_source_decisions WHERE record_id=ANY(%s::uuid[])',
                                  (record_ids,)).fetchall()
        self.assertEqual(len(observations), 2)
        self.assertEqual(observations[0]['semantic_payload'], observations[1]['semantic_payload'])
        self.assertNotEqual(observations[0]['knode_id'], observations[1]['knode_id'])
        self.assertNotEqual(observations[0]['identity_fingerprint'], observations[1]['identity_fingerprint'])
        self.assertEqual({row['source_data_id'] for row in observations}, self.data_ids)
        self.assertEqual(len(checks), 3)
        self.assertTrue(all(row['source_explicit'] and row['no_novel_inference'] and row['source_identity_preserved']
                            for row in checks))
        self.assertTrue(all(node['is_inferred'] is False for node in response['nodes']))
        displayed = {node['knode_id']: node for owner in self.data_ids
                     for node in self.runtime.graph(owner)['nodes']}
        self.assertEqual(len(displayed), 3)
        for node in displayed.values():
            origin = node['generation_origin']
            self.assertEqual(origin['origin_operation'], 'i2k')
            self.assertIs(origin['is_inferred'], False)
            self.assertEqual(origin['claim_basis'], 'explicit_source_content')
            self.assertEqual(origin['origin_record_id'], node['origin_record_id'])
            self.assertTrue(origin['validation']['no_novel_inference'])

    def test_successful_request_replays_and_same_meaning_reuses_without_revision(self):
        response, job = self.response(), self.prepare()
        first = self.accept(job, response)
        replay = self.prepare(request=job['request_id'])
        self.assertTrue(replay['replayed'])
        self.assertEqual(replay['execution_id'], job['execution_id'])
        before = self.runtime.graph(self.first.data_id)
        other_before = self.runtime.graph(self.second.data_id)
        changed = deepcopy(response)
        for node in changed['nodes']:
            node['statement'] = 'A presentation-only paraphrase of the synthetic source assertion.'
        decisions = self.decisions(changed)
        for item, record in zip(decisions['decisions'], first['records']):
            item.update(verdict='reused', equivalent_revision_id=record['result_node_revision_id'])
        second = self.accept(self.prepare(), changed, decisions)
        self.assertEqual([record['disposition'] for record in second['records']], ['reused'] * 3)
        self.assertEqual([r['result_node_revision_id'] for r in second['records']],
                         [r['result_node_revision_id'] for r in first['records']])
        after, other_after = self.runtime.graph(self.first.data_id), self.runtime.graph(self.second.data_id)
        for old, new in ((before, after), (other_before, other_after)):
            self.assertEqual(old['node_revisions'], new['node_revisions'])
            self.assertEqual(old['groundings'], new['groundings'])
            self.assertEqual({node['knode_id']: node['generation_origin'] for node in old['nodes']},
                             {node['knode_id']: node['generation_origin'] for node in new['nodes']})

    def test_legacy_scope_authority_uses_original_record_not_evidence_projection(self):
        """Authority check with a real legacy origin and a synthetic projection.

        The two-Data projection is intentionally supplied to the scope helper;
        this test does not claim that historical cross-source evidence was saved.
        """
        legacy = self.first.accept(self.first.prepare())
        revision_id = legacy['records'][0]['result_node_revision_id']
        node = next(row for row in self.runtime.graph(self.first.data_id)['nodes']
                    if row['knode_revision_id'] == revision_id)
        self.assertIsNone(node['identity_scope'])
        projected = {**deepcopy(node), 'grounding_data_ids': sorted(self.data_ids)}
        candidate = next(row for row in multi.normalize_proposals(self.response(), self.bundle)['nodes']
                         if row['candidate_key'] == 'observation_a')
        job = {'profile': {'schema_version': multi.PROFILE}, 'data_id': self.bundle['data_id']}
        with connection(self.dsn) as conn:
            origin = conn.execute('''SELECT r.record_type,e.data_id FROM canonical_store.knowledge_node_revisions n
                JOIN compiler_runtime.k_compilation_records r ON r.record_id=n.origin_record_id
                JOIN compiler_runtime.operation_executions e USING(execution_id)
                WHERE n.knode_revision_id=%s''', (revision_id,)).fetchone()
            self.assertEqual((origin['record_type'], origin['data_id']), ('i2k', self.first.data_id))
            self.assertTrue(self.runtime._check_scope(conn, candidate, projected, job))
            wrong_owner = {**deepcopy(candidate), 'source_data_id': self.second.data_id}
            self.error('knowledge_scope_reuse_conflict',
                       lambda: self.runtime._check_scope(conn, wrong_owner, projected, job))
        self.assertEqual(self.runtime.graph(self.first.data_id)['nodes'][0]['identity_scope'], None)

    def test_supplementary_data_grounding_preserves_source_owner_and_revision(self):
        response = self.response()
        initial = self.accept(self.prepare(), response)
        owner_record = initial['records'][1]
        node_id, revision_id = owner_record['result_node_id'], owner_record['result_node_revision_id']
        with connection(self.dsn) as conn:
            before_scope = conn.execute('SELECT * FROM canonical_store.knowledge_node_scopes WHERE knode_id=%s',
                                        (node_id,)).fetchone()
            before_revision = conn.execute('SELECT * FROM canonical_store.knowledge_node_revisions WHERE knode_revision_id=%s',
                                           (revision_id,)).fetchone()
        changed = deepcopy(response)
        observation_a = next(node for node in changed['nodes'] if node['candidate_key'] == 'observation_a')
        observation_b = next(node for node in changed['nodes'] if node['candidate_key'] == 'observation_b')
        supplementary = deepcopy(observation_b['evidence'][0])
        observation_a['evidence'].append(supplementary)
        next(review for review in changed['reviews'] if review['information_id'] == supplementary['information_id'])[
            'candidate_keys'].append('observation_a')
        decisions = self.decisions(changed)
        for item, record in zip(decisions['decisions'], initial['records']):
            item.update(verdict='reused', equivalent_revision_id=record['result_node_revision_id'])
        result = self.accept(self.prepare(), changed, decisions)
        self.assertEqual(result['records'][1]['result_node_revision_id'], revision_id)
        self.assertEqual(result['records'][1]['disposition'], 'reused')
        with connection(self.dsn) as conn:
            after_scope = conn.execute('SELECT * FROM canonical_store.knowledge_node_scopes WHERE knode_id=%s',
                                       (node_id,)).fetchone()
            after_revision = conn.execute('SELECT * FROM canonical_store.knowledge_node_revisions WHERE knode_revision_id=%s',
                                          (revision_id,)).fetchone()
            owners = conn.execute('''SELECT DISTINCT i.data_id FROM canonical_store.knowledge_node_groundings g
                JOIN canonical_store.information i USING(information_id) WHERE g.node_revision_id=%s''',
                (revision_id,)).fetchall()
        self.assertEqual(after_scope, before_scope)
        self.assertEqual(after_scope['source_data_id'], self.first.data_id)
        self.assertEqual(after_revision, before_revision)
        self.assertEqual({row['data_id'] for row in owners}, self.data_ids)

    def test_packet_hash_changed_content_and_foreign_i_are_rejected(self):
        tampered = deepcopy(self.bundle)
        tampered['input_sha256'] = '0' * 64
        self.error('multi_source_input_changed', lambda: self.prepare(bundle=tampered))
        fake = deepcopy(self.first.packet)
        fake['model_input']['information'][0]['content'] += ' fabricated source text'
        fake['input_sha256'] = digest({k: v for k, v in fake.items() if k != 'input_sha256'})
        self.error('knowledge_input_changed', lambda: self.prepare(bundle=multi.combine_packets([fake, self.second.packet])))
        foreign = deepcopy(self.first.packet)
        original_id = foreign['target_information_ids'][0]
        stolen = self.second.packet['target_information_ids'][0]
        foreign['model_input']['information'][0]['information_id'] = stolen
        foreign['target_information_ids'][0] = stolen
        self.assertNotEqual(original_id, stolen)
        foreign['input_sha256'] = digest({k: v for k, v in foreign.items() if k != 'input_sha256'})
        with self.assertRaises(PalimpsestError) as caught:
            self.prepare(bundle=multi.combine_packets([foreign]))
        self.assertIn(caught.exception.code, ('knowledge_input_changed', 'i2k_information_scope_mismatch'))
        self._no_graph()

    def test_novel_inference_cannot_be_staged_or_accepted(self):
        response, job = self.response(), self.prepare()
        inferred = deepcopy(response)
        inferred['nodes'][0]['is_inferred'] = True
        self.error('i2k_novel_inference_forbidden', lambda: self.stage(job, inferred))
        self.assertEqual(self.runtime.show(job['execution_id'])['records'], [])
        self.stage(job, response)
        decisions = self.decisions(response)
        decisions['decisions'][0]['no_novel_inference'] = False
        self.error('i2k_explicit_source_acceptance_required', lambda: self.runtime.decide(
            job['execution_id'], decisions, self.receipt(job, decisions, 'validator')))
        self._no_graph()
        self.assertTrue(all(record['disposition'] == 'pending' for record in self.runtime.show(job['execution_id'])['records']))

    def test_failpoint_rolls_back_effects_but_keeps_durable_staged_records(self):
        response, job = self.response(), self.prepare()
        self.stage(job, response)
        decisions = self.decisions(response)
        receipt = self.receipt(job, decisions, 'validator')

        def fail(stage):
            if stage == 'after_knowledge_effect':
                raise RuntimeError('multi-source injected commit failure')

        with self.assertRaisesRegex(RuntimeError, 'injected commit failure'):
            self.runtime.decide(job['execution_id'], decisions, receipt, checkpoint=fail)
        self._no_graph()
        staged = self.runtime.show(job['execution_id'])
        self.assertEqual(staged['state'], 'proposed')
        self.assertEqual(len(staged['records']), 3)
        self.assertTrue(all(record['disposition'] == 'pending' and record['body'] is not None for record in staged['records']))
        with connection(self.dsn) as conn:
            saved = conn.execute('''SELECT count(*) AS n FROM compiler_runtime.k_explicit_source_decisions d
                JOIN compiler_runtime.k_compilation_records r USING(record_id) WHERE r.execution_id=%s''',
                (job['execution_id'],)).fetchone()['n']
        self.assertEqual(saved, 0)
        self.assertEqual(self.runtime.decide(job['execution_id'], decisions, receipt)['state'], 'completed')

    def test_second_frozen_readset_cannot_commit_after_first_graph_change(self):
        first, second = self.prepare(), self.prepare()
        response = self.response()
        self.stage(second, response)
        decisions = self.decisions(response)
        second_receipt = self.receipt(second, decisions, 'validator')
        self.accept(first, response)
        self.error('knowledge_state_changed', lambda: self.runtime.decide(second['execution_id'], decisions, second_receipt))
        staged = self.runtime.show(second['execution_id'])
        self.assertEqual(staged['state'], 'proposed')
        self.assertTrue(all(record['disposition'] == 'pending' for record in staged['records']))

    def dispatch_failure(self, job, *, phase='generator'):
        """Planned-request metadata only: no provider response or delivery claim."""
        current = self.runtime.show(job['execution_id'])
        snapshot = current['input_snapshot']
        attachments = [{'sha256': item['sha256'], 'byte_size': item['byte_size']}
                       for item in snapshot['input']['media_assets']]
        if phase == 'generator':
            input_sha = current['input_digest']
            prompt, schema = prompts.generation(snapshot, attachments), multi.generation_schema(snapshot['input'])
        else:
            context = self.runtime.validation_context(job['execution_id'])
            input_sha = context['validation_context_sha']
            prompt = prompts.validation(context, attachments)
            schema = multi.validation_schema([node['candidate_key'] for node in context['candidates']],
                [node['knode_revision_id'] for node in snapshot['existing_nodes']], snapshot['input'])
        planned = {'prompt': prompt, 'schema': schema, 'images': attachments, 'input_sha256': input_sha}
        return {'input_sha256': input_sha, 'prompt_sha256': sha256(prompt.encode('utf-8')).hexdigest(),
                'schema_sha256': digest(schema), 'request_file_sha256': digest(planned),
                'error_code': 'codex_execution_failed', 'actual_delivery': None, 'output_sha256': None,
                'test_only': True, 'description': 'Synthetic dispatch failure; no model called.'}

    def test_dispatch_failure_preserves_unknown_delivery_and_allows_safe_retry(self):
        job = self.prepare()
        failure = self.dispatch_failure(job)
        saved = self.runtime.record_dispatch_failure(job['execution_id'], 'generator', failure)
        replay = self.runtime.record_dispatch_failure(job['execution_id'], 'generator', failure)
        self.assertEqual(saved['call_id'], replay['call_id'])
        self.assertFalse(saved['replayed'])
        self.assertTrue(replay['replayed'])
        current = self.runtime.show(job['execution_id'])
        self.assertEqual(current['state'], 'prepared')
        self.assertEqual(current['records'], [])
        self.assertIsNone(current['generator_receipt'])
        self.assertEqual(len(current['model_calls']), 1)
        call = current['model_calls'][0]
        self.assertEqual(call['status'], 'failed')
        self.assertIsNone(call['output_sha256'])
        self.assertIsNone(call['provider_ref'])
        self.assertIsNone(call['receipt']['actual_delivery'])
        self.assertIsNone(call['receipt']['output_sha256'])
        self.assertEqual(call['receipt']['request_file_sha256'], failure['request_file_sha256'])
        self.assertEqual(call['usage'], {})
        self._no_graph()
        # A later successful synthetic retry may proceed; historical failure replay adds no call.
        completed = self.accept(job, self.response())
        self.assertEqual(completed['state'], 'completed')
        historical = self.runtime.record_dispatch_failure(job['execution_id'], 'generator', failure)
        self.assertEqual(historical['call_id'], saved['call_id'])
        self.assertEqual(len(self.runtime.show(job['execution_id'])['model_calls']), 3)

    def test_dispatch_failure_rejects_wrong_input_delivery_claim_and_completed_phase(self):
        job = self.prepare()
        failure = self.dispatch_failure(job)
        self.error('invalid_knowledge_state', lambda: self.runtime.record_dispatch_failure(
            job['execution_id'], 'generator', {**failure, 'input_sha256': '0' * 64}))
        for changed in ({'actual_delivery': True}, {'output_sha256': 'a' * 64}, {'error_code': 'unregistered_failure'}):
            with self.subTest(changed=changed):
                self.error('invalid_knowledge_dispatch_failure', lambda: self.runtime.record_dispatch_failure(
                    job['execution_id'], 'generator', {**failure, **changed}))
        self.assertEqual(self.runtime.show(job['execution_id'])['model_calls'], [])
        response = self.response()
        self.stage(job, response)
        self.error('invalid_knowledge_state', lambda: self.runtime.record_dispatch_failure(job['execution_id'], 'generator', failure))
        validator_failure = self.dispatch_failure(job, phase='validator')
        decisions = self.decisions(response)
        self.runtime.decide(job['execution_id'], decisions, self.receipt(job, decisions, 'validator'))
        self.error('invalid_knowledge_state', lambda: self.runtime.record_dispatch_failure(
            job['execution_id'], 'validator', validator_failure))
        self.assertEqual(len(self.runtime.show(job['execution_id'])['model_calls']), 2)


if __name__ == '__main__':
    unittest.main()
