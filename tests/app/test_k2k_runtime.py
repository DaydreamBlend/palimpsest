"""K2K persistence in the explicitly isolated PG fixture, using synthetic receipts.

These checks exercise exact dependencies, origins, holds and transaction rollback.
They do not execute a provider, establish semantic quality or complete a scheduler.
"""

from copy import deepcopy
from hashlib import sha256
import os
import sys
import unittest
from uuid import uuid4

import psycopg

from palimpsest import k2k
from palimpsest.canonical_store import connection
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest

import test_selection_runtime as selection_fixtures


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires the explicitly provisioned Linux PostgreSQL fixture database palimpsest')
class K2KRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with connection(os.environ['PALIMPSEST_TEST_DSN']) as conn:
            if conn.execute('SELECT current_database() AS name').fetchone()['name'] != 'palimpsest':
                raise RuntimeError('K2K tests require the isolated database named palimpsest')
            if conn.execute("SELECT to_regclass('canonical_store.knowledge_derivations') AS name").fetchone()['name'] is None:
                raise RuntimeError('K2K tests require explicit migration 0011 in the isolated fixture')

    def setUp(self):
        self.fixture = selection_fixtures.SelectionRuntimeTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.runtime, self.helper = self.fixture.runtime, self.fixture.helper
        self.dsn, self.data_id = self.fixture.dsn, self.fixture.data_id
        self.seed = self.fixture.commit(self.fixture.prepare(), self.fixture.response())
        self.premises = [row['result_node_revision_id'] for row in self.seed['records']]
        self.assertEqual(len(self.premises), 2)

    def prepare(self, premises=None, packet=None):
        packet = packet or self.runtime.inference_input(self.data_id, premises or self.premises)
        return self.runtime.prepare('k2k', self.data_id, self.helper.repo.allocate_id(), packet)

    def response(self, job, *, name='result', existing=None):
        existing = existing or {}
        return {'nodes': [{'candidate_key': name, 'kind': 'proposition',
            'statement': existing.get('statement', f'Synthetic inferred fixture {name}; not a model result.'),
            'semantic_payload': deepcopy(existing.get('semantic_payload', {
                'subject': 'Synthetic inference ' + self.data_id, 'relation': 'has derived fixture property',
                'object': name, 'polarity': 'positive', 'quantifier': 'conditional fixture',
                'scope': 'isolated persistence test', 'conditions': ['assumed fixture rule'], 'time_range': ''})),
            'identity_scope': existing.get('identity_scope', 'source'),
            'source_data_id': existing.get('source_data_id', self.data_id),
            'premise_revision_ids': [node['knode_revision_id'] for node in job['input_snapshot']['input']['nodes']],
            'inference_type': 'deductive', 'assumptions': ['Synthetic rule, not real semantic validation.'],
            'limitations': ['Persistence fixture only; source facts and tests were not inferred as observations.'],
            'derivation_basis': 'Synthetic derivation over the supplied exact premise revisions.'}],
            'complete': True, 'coverage_notes': ['One explicit fixture request; not global inference exhaustion.']}

    @staticmethod
    def decisions(response, *, verdict='accepted', equivalent=None, complete=True):
        return {'complete': complete, 'decisions': [{
            'candidate_key': node['candidate_key'], 'verdict': verdict,
            'equivalent_candidate_key': None, 'equivalent_revision_id': equivalent,
            'reason_codes': ['synthetic_fixture'], 'reason': 'Synthetic independent storage verdict; no provider called.',
            'inference_valid': verdict not in ('rejected', 'needs_human'),
            'premises_sufficient': verdict != 'needs_human', 'limits_preserved': True,
            'novel_conclusion': verdict == 'accepted'} for node in response['nodes']]}

    def receipt(self, job, response, phase):
        current = self.runtime.show(job['execution_id'])
        if phase == 'generator':
            prompt = k2k.generation(current['input_snapshot'], [])
            schema = k2k.generation_schema(current['input_snapshot']['input'])
            input_sha = current['input_digest']
        else:
            context = self.runtime.validation_context(job['execution_id'])
            prompt = k2k.validation(context, [])
            schema = k2k.validation_schema([node['candidate_key'] for node in context['candidates']],
                [node['knode_revision_id'] for node in current['input_snapshot']['existing_nodes']])
            input_sha = context['validation_context_sha']
        return {'profile': {**current['profile']['model'], 'synthetic_receipt': True},
            'input_sha256': input_sha, 'output_sha256': digest(response),
            'prompt_sha256': sha256(prompt.encode('utf-8')).hexdigest(), 'schema_sha256': digest(schema),
            'provider_ref': 'synthetic-k2k-no-model-' + str(uuid4()), 'actual_delivery': True,
            'delivered_knowledge_revision_ids': [node['knode_revision_id'] for node in current['input_snapshot']['input']['nodes']],
            'image_attachments': [], 'usage': {}, 'test_only': True}

    def stage(self, job, response):
        return self.runtime.stage(job['execution_id'], response, self.receipt(job, response, 'generator'))

    def commit(self, job, response, decisions=None):
        self.stage(job, response)
        decisions = decisions or self.decisions(response)
        return self.runtime.decide(job['execution_id'], decisions, self.receipt(job, decisions, 'validator'))

    def source_state(self):
        with connection(self.dsn) as conn:
            return conn.execute('''SELECT (SELECT count(*) FROM canonical_store.information WHERE data_id=%s) AS information,
                (SELECT count(*) FROM compiler_runtime.operation_executions WHERE data_id=%s AND operation='d2i') AS d2i,
                (SELECT count(*) FROM canonical_store.data WHERE data_id=%s) AS data''',
                (self.data_id, self.data_id, self.data_id)).fetchone()

    def node(self, revision):
        return next(node for node in self.runtime.graph(self.data_id)['nodes'] if node['knode_revision_id'] == revision)

    def test_fresh_inference_preserves_exact_premises_origin_and_transitive_source(self):
        before = self.source_state()
        job = self.prepare()
        self.assertNotIn('source_review_manifest', job['input_snapshot'])
        result = self.commit(job, self.response(job))
        self.assertEqual(result['state'], 'completed')
        record = result['records'][0]
        self.assertEqual(record['record_type'], 'k2k')
        self.assertEqual(record['disposition'], 'accepted_new')
        node = self.node(record['result_node_revision_id'])
        self.assertEqual(node['generation_origin']['origin_operation'], 'k2k')
        self.assertTrue(node['generation_origin']['is_inferred'])
        self.assertEqual(node['generation_origin']['origin_record_id'], record['record_id'])
        self.assertEqual(node['generation_origin']['premise_revision_ids'], self.premises)
        self.assertEqual(node['derivation_depth'], 1)
        self.assertEqual(node['direct_groundings'], [])
        self.assertEqual({ref['data_id'] for ref in node['transitive_source_refs']}, {self.data_id})
        self.assertEqual({ref['node_revision_id'] for ref in node['transitive_source_refs']}, set(self.premises))
        self.assertTrue(all(ref['information_id'] and ref['source_execution_id'] for ref in node['transitive_source_refs']))
        self.assertEqual(node['source_data_ids'], [self.data_id])
        self.assertEqual(result['derivations'][0]['premise_revision_ids'], self.premises)
        self.assertEqual(self.source_state(), before)
        self.assertEqual(self.runtime.graph(self.data_id)['propagation_status'], 'outbox_pending_not_converged')

    def test_same_meaning_reuse_preserves_origin_revision_and_appends_derivation(self):
        first_job = self.prepare()
        first = self.commit(first_job, self.response(first_job))
        first_record = first['records'][0]
        revision = first_record['result_node_revision_id']
        before = self.runtime.graph(self.data_id)
        job = self.prepare()
        response = self.response(job)
        again = self.commit(job, response, self.decisions(response, verdict='reused', equivalent=revision))
        self.assertEqual(again['records'][0]['disposition'], 'reused')
        after = self.runtime.graph(self.data_id)
        self.assertEqual(before['node_revisions'], after['node_revisions'])
        self.assertEqual(before['groundings'], after['groundings'])
        node = self.node(revision)
        self.assertEqual(node['origin_record_id'], first_record['record_id'])
        self.assertEqual(node['generation_origin']['origin_record_id'], first_record['record_id'])
        self.assertEqual(len(node['derivations']), 2)

    def test_depth_two_derivation_has_transitive_I_without_direct_I(self):
        first_job = self.prepare()
        first = self.commit(first_job, self.response(first_job))
        first_revision = first['records'][0]['result_node_revision_id']
        job = self.prepare([first_revision, self.premises[0]])
        result = self.commit(job, self.response(job, name='second_level'))
        node = self.node(result['records'][0]['result_node_revision_id'])
        self.assertEqual(node['derivation_depth'], 2)
        self.assertEqual(node['generation_origin']['premise_revision_ids'], [first_revision, self.premises[0]])
        self.assertEqual(node['direct_groundings'], [])
        self.assertEqual({ref['node_revision_id'] for ref in node['transitive_source_refs']}, set(self.premises))

    def test_source_created_proposition_reuse_does_not_relabel_its_origin(self):
        source = self.fixture.response()
        source['nodes'] = [deepcopy(source['nodes'][1])]
        source['nodes'][0].update(candidate_key='source_third', statement='Another source-created fixture proposition.')
        source['nodes'][0]['semantic_payload']['object'] = 'third explicitly sourced property'
        self.fixture.reviews(source, self.fixture.packet)
        third = self.fixture.commit(self.fixture.prepare(), source)['records'][0]
        original = self.node(third['result_node_revision_id'])
        job = self.prepare()
        response = self.response(job, existing=original)
        result = self.commit(job, response, self.decisions(response, verdict='reused', equivalent=original['knode_revision_id']))
        reused = self.node(original['knode_revision_id'])
        self.assertEqual(result['records'][0]['disposition'], 'reused')
        self.assertEqual(reused['origin_record_id'], third['record_id'])
        self.assertEqual(reused.get('generation_origin'), original.get('generation_origin'))
        self.assertEqual(reused['derivation_depth'], 0)
        self.assertTrue(reused['direct_groundings'])
        self.assertEqual(len(reused['derivations']), 1)

    def test_rejected_held_and_incomplete_review_never_claim_global_completion(self):
        for verdict, expected in (('rejected', 'completed'), ('needs_human', 'needs_human')):
            with self.subTest(verdict=verdict):
                before = len(self.runtime.graph(self.data_id)['nodes'])
                job = self.prepare()
                response = self.response(job, name='held_' + verdict)
                result = self.commit(job, response, self.decisions(response, verdict=verdict))
                self.assertEqual(result['state'], expected)
                self.assertEqual(result['derivations'], [])
                self.assertEqual(len(self.runtime.graph(self.data_id)['nodes']), before)
        job = self.prepare()
        response = self.response(job, name='partial')
        result = self.commit(job, response, self.decisions(response, complete=False))
        self.assertEqual(result['state'], 'needs_human')
        self.assertEqual(result['records'][0]['disposition'], 'accepted_new')

    def test_wrong_ownership_direct_I_observation_and_injected_metadata_fail(self):
        with self.assertRaises(PalimpsestError):
            self.runtime.inference_input('0' * 64, self.premises)
        packet = self.runtime.inference_input(self.data_id, self.premises)
        forged = deepcopy(packet)
        forged['nodes'][0]['statement'] = 'Forged canonical premise.'
        forged['input_sha256'] = digest({k: v for k, v in forged.items() if k != 'input_sha256'})
        with self.assertRaises(PalimpsestError):
            self.prepare(packet=forged)
        for mutation in ('direct_I', 'observation', 'origin', 'wrong_owner', 'one_premise'):
            with self.subTest(mutation=mutation):
                job = self.prepare()
                response = self.response(job)
                node = response['nodes'][0]
                if mutation == 'direct_I': node['evidence'] = [{'information_id': self.helper.text['information_id']}]
                if mutation == 'observation': node['kind'] = 'observation'
                if mutation == 'origin': node['is_inferred'] = True
                if mutation == 'wrong_owner': node['source_data_id'] = '0' * 64
                if mutation == 'one_premise': node['premise_revision_ids'].pop()
                with self.assertRaises(PalimpsestError):
                    self.stage(job, response)
                self.assertEqual(self.runtime.show(job['execution_id'])['records'], [])

    def test_delivered_exact_K_ids_independent_validator_and_stale_readset(self):
        job = self.prepare()
        response = self.response(job)
        bad = self.receipt(job, response, 'generator')
        bad['delivered_knowledge_revision_ids'].pop()
        with self.assertRaises(PalimpsestError):
            self.runtime.stage(job['execution_id'], response, bad)
        good = self.receipt(job, response, 'generator')
        self.runtime.stage(job['execution_id'], response, good)
        decisions = self.decisions(response)
        validator = self.receipt(job, decisions, 'validator')
        validator['provider_ref'] = good['provider_ref']
        with self.assertRaises(PalimpsestError):
            self.runtime.decide(job['execution_id'], decisions, validator)
        validator = self.receipt(job, decisions, 'validator')
        other = self.prepare()
        self.commit(other, self.response(other, name='concurrent_change'))
        with self.assertRaises(PalimpsestError) as caught:
            self.runtime.decide(job['execution_id'], decisions, validator)
        self.assertEqual(caught.exception.code, 'knowledge_state_changed')
        self.assertEqual(self.runtime.show(job['execution_id'])['state'], 'proposed')

    def test_late_rollback_retry_and_immutable_derivation_rows(self):
        job = self.prepare()
        response = self.response(job)
        self.stage(job, response)
        decisions = self.decisions(response)
        receipt = self.receipt(job, decisions, 'validator')
        before = self.runtime.graph(self.data_id)
        def fail(stage):
            if stage == 'before_knowledge_commit':
                raise RuntimeError('injected late K2K rollback')
        with self.assertRaisesRegex(RuntimeError, 'injected late K2K rollback'):
            self.runtime.decide(job['execution_id'], decisions, receipt, checkpoint=fail)
        self.assertEqual(self.runtime.graph(self.data_id)['node_revisions'], before['node_revisions'])
        self.assertEqual(self.runtime.show(job['execution_id'])['derivations'], [])
        self.assertEqual(self.runtime.show(job['execution_id'])['records'][0]['disposition'], 'pending')
        result = self.runtime.decide(job['execution_id'], decisions, receipt)
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(self.runtime.decide(job['execution_id'], decisions, receipt)['state'], 'completed')
        record = result['records'][0]['record_id']
        with self.assertRaises(PalimpsestError), connection(self.dsn) as conn, conn.transaction():
            conn.execute('UPDATE canonical_store.knowledge_derivations SET derivation_depth=99 WHERE record_id=%s', (record,))
        self.assertEqual(self.node(result['records'][0]['result_node_revision_id'])['derivation_depth'], 1)

    def test_reuse_of_a_premise_as_its_own_derived_result_is_a_cycle(self):
        original = next(self.node(ref) for ref in self.premises if self.node(ref)['kind'] == 'proposition')
        job = self.prepare()
        response = self.response(job, existing=original)
        self.stage(job, response)
        decisions = self.decisions(response, verdict='reused', equivalent=original['knode_revision_id'])
        with self.assertRaises((PalimpsestError, psycopg.Error)):
            self.runtime.decide(job['execution_id'], decisions, self.receipt(job, decisions, 'validator'))
        self.assertEqual(self.runtime.show(job['execution_id'])['derivations'], [])
        self.assertEqual(len(self.runtime.graph(self.data_id)['nodes']), 2)


if __name__ == '__main__':
    unittest.main()
