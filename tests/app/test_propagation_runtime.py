"""Scoped dispatcher end-to-end tests in the root-provisioned disposable PG DB.

All model exchanges are synthetic and use the actual exported request hashes.
These tests never migrate/reset a DB or invoke a provider. Loop bounds below are
test failure guards, not successful propagation completion policies.
"""

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

from palimpsest.canonical_store import connection
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.knowledge_runtime import MODEL
from palimpsest.paper_wiki_runtime import PaperWikiRuntime
from palimpsest.propagation_runtime import PropagationRuntime
from palimpsest.wiki_archive import build_archive
from palimpsest.wiki_database import WikiDatabase
import test_knowledge_revision_integration as revisions
import test_k2k_runtime as inference
from test_paper_wiki import decisions as wiki_decisions
from test_paper_wiki_runtime import exchange as wiki_exchange, synthetic_proposal
import test_revalidation_runtime as reviews


class InterruptedAfterCommit(RuntimeError):
    pass


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires the explicitly provisioned isolated Linux PostgreSQL fixture')
class PropagationRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        revisions.KnowledgeRevisionIntegrationTests.setUpClass()
        cls.dsn = os.environ['PALIMPSEST_TEST_DSN']
        with connection(cls.dsn) as conn:
            if not conn.execute("SELECT to_regclass('compiler_runtime.propagation_runs') AS relation").fetchone()['relation']:
                raise RuntimeError('Root must provision reviewed additive0016')

    def setUp(self):
        self.f = revisions.KnowledgeRevisionIntegrationTests('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.runtime = self.f.runtime
        self.target, _ = self.f.inference()
        # Reuse the independently tested relation fixture, not a hand-inserted edge.
        self.edge = reviews.RevalidationRuntimeTests.edge(self)
        self.paper = PaperWikiRuntime(self.dsn, self.f.root, self.f.base / 'wiki-original')
        self.wiki_id, self.base_import = self.f.repo.allocate_id(), self.f.repo.allocate_id()
        identifier = self.f.repo.allocate_id()
        self.paper.prepare(self.f.source_result['execution_id'], identifier,
            {'title': 'Synthetic end-to-end propagation Wiki', 'filename': 'source.md'})
        context = self.paper.stage(identifier, wiki_exchange(self.paper, identifier, 'generator', synthetic_proposal(self.f.packet)))
        self.paper.decide(identifier, wiki_exchange(self.paper, identifier, 'validator', wiki_decisions(context['proposal'])))
        self.original = build_archive(self.paper.store)
        self.database = WikiDatabase(self.dsn, self.f.root)
        self.database.sync(self.wiki_id, self.base_import, self.paper.store.root)
        self.worker = PropagationRuntime(self.dsn, self.f.root, self.f.base / 'propagation')
        self.generated, self.calls = {}, []

    def revise(self, target=None, *, kind='observation', value='four'):
        target = target or self.f.source_target
        job = self.f.prepare_source(target)
        result = self.f.commit(job, self.f.source_response([self.f.source_candidate(kind, kind, value)]))
        return result['records'][0]

    def start(self, roots=None, *, discovery=True, wiki=True):
        roots = roots or [self.revise()['record_id']]
        self.run = self.worker.prepare(self.f.repo.allocate_id(), roots,
            allowed_data_ids=[self.f.data_id], wiki_ids=[self.wiki_id] if wiki else [], discovery=discovery)
        self.worker.queue.start(self.run['run_id'], self.run['request_fingerprint'], 'synthetic-test-user')
        return self.run

    def synthetic_exchange(self, action, *, hold_node=False):
        request = json.loads(Path(action['request_file']).read_text(encoding='utf-8'))
        if action['operation'] == 'wiki':
            task = self.worker._task(action['task_id'])
            refresh = self.worker.wiki.advance(task['request_id'])
            runtime = self.worker.wiki._runtime(task['request_id'])
            job = runtime.show(refresh['request_id'])
            response = (synthetic_proposal(job['input_snapshot']['input'], text_suffix='Regenerated after validated Knowledge changes.')
                if action['phase'] == 'generator' else wiki_decisions(runtime._context(job)['proposal']))
        else:
            job = self.runtime.show(action['execution_id'])
            target = job['input_snapshot'].get('revalidation_target')
            if action['phase'] == 'generator':
                if target and target['kind'] == 'node':
                    response = inference.K2KRuntimeTests.response(self.f, job,
                        existing=job['input_snapshot']['revision_target']['target'])
                elif target:
                    response = reviews.RevalidationRuntimeTests.edge_response(job, True)
                elif job['operation'] == 'n2e':
                    response = {'edges': [], 'complete': True}
                else:
                    response = {'nodes': [], 'complete': True, 'coverage_notes': ['Synthetic scoped discovery found no new conclusion.']}
                self.generated[action['execution_id']] = deepcopy(response)
            elif target and target['kind'] == 'node':
                response = self.f.decisions(job, self.generated[action['execution_id']], material=False)
                response['decisions'][0].update(verdict='reused', equivalent_candidate_key=None,
                    equivalent_revision_id=target['target_revision_id'], novel_conclusion=False)
                if hold_node:
                    response['decisions'][0].update(verdict='needs_human', inference_valid=False, premises_sufficient=False,
                        equivalent_candidate_key=None, equivalent_revision_id=None, novel_conclusion=False,
                        reason_codes=['synthetic_uncertainty'], reason='Synthetic unresolved mandatory target.')
                    response['revision_review'].update(material_change=None, grounding_valid=False)
            elif target:
                response = reviews.RevalidationRuntimeTests.edge_decision(True)
            else:
                response = {'decisions': [], 'complete': True}
        result = {'response': response, 'receipt': {'profile': deepcopy(MODEL), 'synthetic_test_only': True,
            'actual_delivery': True, 'original_pdf_delivered': False, 'provider_ref': 'synthetic-propagation-' + str(uuid4()),
            'input_sha256': request['input_sha256'], 'output_sha256': digest(response),
            'prompt_sha256': sha256(request['prompt'].encode()).hexdigest(), 'schema_sha256': digest(request['schema']),
            'image_attachments': [], 'usage': {},
            **{key: deepcopy(value) for key, value in request.items() if key.startswith('delivered_')}}}
        self.calls.append({'task_id': action['task_id'], 'execution_id': action.get('execution_id'),
            'operation': action['operation'], 'phase': action['phase'], 'request_sha256': digest(request)})
        return result

    def drive(self, current=None, *, hold_node=False):
        current = current or self.worker.next(self.run['run_id'])
        for _ in range(2000):
            if current['action'] == 'model_request':
                current = self.worker.accept(current['task_id'], current['lease_token'], current['phase'],
                    self.synthetic_exchange(current, hold_node=hold_node))
            elif current['action'] in ('task_completed', 'blocked', 'running'):
                current = self.worker.next(self.run['run_id'])
            else:
                return current
        self.fail('Dispatcher did not settle; a test bound must never become successful completion.')

    def model_request(self):
        for _ in range(100):
            current = self.worker.next(self.run['run_id'])
            if current['action'] == 'model_request':
                return current
            self.assertEqual(current['action'], 'task_completed', current)
        self.fail('No model request reached in a small fixture.')

    def test_material_change_propagates_exact_supports_edges_and_validated_wiki(self):
        child_job = self.f.prepare_inference(premises=[self.target['knode_revision_id'], self.f.premises[1]])
        child = self.f.commit(child_job, inference.K2KRuntimeTests.response(self.f, child_job, name='child'))
        child_id = child['records'][0]['result_node_revision_id']
        self.start()
        result = self.drive()
        self.assertEqual(result['action'], 'completed', result)
        run = self.worker.queue.show(self.run['run_id'])
        self.assertTrue(all(task['state'] == 'done' for task in run['tasks']))
        kinds = [task['kind'] for task in run['tasks']]
        self.assertIn('node_revalidate', kinds)
        self.assertIn('edge_revalidate', kinds)
        self.assertIn('wiki_refresh', kinds)
        self.assertTrue(any(kind in kinds for kind in ('n2e', 'k2k')))
        for ref in (self.target['knode_revision_id'], child_id):
            node = self.f.node(ref)
            self.assertEqual(node['current_applicability'], 'current_premises')
            self.assertEqual(len(self.f.revision_rows(node['knode_id'])), 1)
            self.assertGreater(node['current_support_event']['event_order'], self.run['initial_watermark'])
        self.assertEqual(self.f.node(self.target['knode_revision_id'])['generation_origin'], self.target['generation_origin'])
        current_import = self.database.catalog(self.wiki_id)['import_id']
        self.assertNotEqual(current_import, self.base_import)
        page_id = self.original['catalogs'][self.original['current_catalog_sha256']]['papers'][self.f.data_id]['page_id']
        self.assertEqual(len(self.database.history(self.wiki_id, page_id)['snapshots']), 2)
        self.assertEqual(build_archive(self.paper.store)['files'], self.original['files'])
        self.assertEqual(self.f.source_state(), self.f.source_before)
        self.assertEqual(sum(call['operation'] == 'wiki' for call in self.calls), 2)

    def test_commit_before_ack_reclaims_same_execution_without_repeating_model(self):
        self.start(discovery=False)
        generator = self.model_request()
        self.assertEqual(self.worker._task(generator['task_id'])['kind'], 'node_revalidate')
        validator = self.worker.accept(generator['task_id'], generator['lease_token'], 'generator', self.synthetic_exchange(generator))
        self.assertEqual(validator['phase'], 'validator')
        with patch.object(self.worker, 'advance', side_effect=InterruptedAfterCommit('Synthetic process loss after canonical commit')):
            with self.assertRaises(InterruptedAfterCommit):
                self.worker.accept(validator['task_id'], validator['lease_token'], 'validator', self.synthetic_exchange(validator))
        self.assertEqual(self.runtime.show(validator['execution_id'])['state'], 'completed')
        self.assertEqual(self.worker._task(validator['task_id'])['state'], 'leased')
        self.worker.queue.control(self.run['run_id'], 'pause', 'synthetic-test-user', 'Process lost after commit.')
        self.worker.queue.control(self.run['run_id'], 'resume', 'synthetic-test-user', 'Recover without repeating a committed model call.')
        result = self.drive()
        self.assertEqual(result['action'], 'completed', result)
        self.assertEqual(sum(call['execution_id'] == validator['execution_id'] for call in self.calls), 2)
        self.assertEqual(self.worker._task(validator['task_id'])['state'], 'done')
        with connection(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM compiler_runtime.k_model_calls WHERE execution_id=%s',
                (validator['execution_id'],)).fetchone()['n'], 2)

    def test_pause_epoch_rejects_old_accept_and_retains_prepared_execution(self):
        self.start(discovery=False)
        original = self.model_request()
        prepared_exchange = self.synthetic_exchange(original)
        self.worker.queue.control(self.run['run_id'], 'pause', 'synthetic-test-user', 'Pause before response submission.')
        self.worker.queue.control(self.run['run_id'], 'resume', 'synthetic-test-user', 'Resume with a new lease epoch.')
        with self.assertRaises(PalimpsestError):
            self.worker.accept(original['task_id'], original['lease_token'], original['phase'], prepared_exchange)
        replacement = self.model_request()
        self.assertEqual(replacement['execution_id'], original['execution_id'])
        self.assertNotEqual(replacement['lease_token'], original['lease_token'])
        self.assertEqual(json.loads(Path(replacement['request_file']).read_text()), json.loads(Path(original['request_file']).read_text()))
        current = self.worker.accept(replacement['task_id'], replacement['lease_token'], replacement['phase'], prepared_exchange)
        self.assertEqual(self.drive(current)['action'], 'completed')

    def test_independent_unresolved_target_prevents_completion_and_wiki_publication(self):
        self.start(discovery=False)
        result = self.drive(hold_node=True)
        self.assertEqual(result['action'], 'needs_human', result)
        run = self.worker.queue.show(self.run['run_id'])
        self.assertGreater(run['counts']['blocked'], 0)
        self.assertNotEqual(run['counts']['done'], run['counts']['total'])
        self.assertEqual(self.database.catalog(self.wiki_id)['import_id'], self.base_import)
        self.assertEqual(self.f.node(self.target['knode_revision_id'])['current_applicability'], 'needs_revalidation')
        self.assertFalse(any(call['operation'] == 'wiki' for call in self.calls))

    def test_exact_chain_and_fanin_survive_empty_discovery_and_one_step_scheduling(self):
        chain = [self.target['knode_revision_id']]
        for ordinal in range(11):
            job = self.f.prepare_inference(premises=[chain[-1], self.f.premises[1]])
            result = self.f.commit(job, inference.K2KRuntimeTests.response(self.f, job, name='chain-' + str(ordinal)))
            chain.append(result['records'][0]['result_node_revision_id'])
        first = self.revise()
        second = self.revise(self.f.node(self.f.premises[1]), kind='proposition', value='revised controlled condition')
        self.start([first['record_id'], second['record_id']], discovery=True)
        # Simulate an empty discovery selection only. Exact dependency reads remain actual DB reads.
        with patch.object(self.worker, '_nodes', return_value=[]):
            result = self.drive()
        self.assertEqual(result['action'], 'completed', result)
        run = self.worker.queue.show(self.run['run_id'])
        self.assertEqual(len(run['scope']['root_record_ids']), 2)
        node_tasks = [task for task in run['tasks'] if task['kind'] == 'node_revalidate']
        self.assertGreaterEqual(len(node_tasks), len(chain))
        self.assertTrue(all(self.f.node(ref)['current_applicability'] == 'current_premises' for ref in chain))
        first_task = next(task for task in node_tasks if task['payload']['target_knode_id'] == self.target['knode_id'])
        with connection(self.dsn) as conn:
            causes = conn.execute('SELECT DISTINCT cause_record_id FROM compiler_runtime.propagation_task_causes WHERE task_id=%s',
                (first_task['task_id'],)).fetchall()
        self.assertGreaterEqual(len(causes), 2)
        self.assertEqual(self.f.source_state(), self.f.source_before)
