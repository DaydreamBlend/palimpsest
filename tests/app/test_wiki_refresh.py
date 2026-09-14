"""Real Linux Wiki files and synthetic exchanges; no provider or PostgreSQL writes."""

from copy import deepcopy
from contextlib import contextmanager
from itertools import count
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.wiki_archive import build_archive
from palimpsest.wiki_projection_store import ProjectionStore
from palimpsest.wiki_refresh import PROFILE, WikiRefreshRuntime, select_targets, change_snapshot
from palimpsest import wiki_refresh
from test_multi_source_i2k import uid
from test_paper_wiki import decisions
from test_paper_wiki_runtime import MockCanonicalRuntime, exchange, synthetic_proposal, synthetic_source


def page_fixture():
    owner = 'a' * 64
    page = {'kind': 'paper', 'data_id': owner, 'page_id': uid(1), 'snapshot_id': uid(2),
        'source_execution_id': uid(3), 'origin_request_id': uid(4),
        'metadata': {'title': 'Synthetic', 'filename': 'synthetic.md'}, 'items': [{'item_key': 'item'}]}
    entry = {'snapshot_id': page['snapshot_id'], 'page_id': page['page_id'], 'snapshot_sha256': digest(page)}
    link = {'wiki_id': uid(5), 'request_id': uid(6), 'snapshot_id': uid(2), 'item_key': 'item',
        'link_id': uid(7), 'knode_id': uid(8), 'node_revision_id': uid(9)}
    return page, {'papers': {owner: entry}, 'topics': {}}, link


class WikiRefreshSelectionTests(unittest.TestCase):
    def test_new_node_and_current_support_use_actual_receipts_without_invented_impacts(self):
        row = {'record_id': uid(1), 'result_node_id': uid(2), 'result_node_revision_id': uid(3),
            'disposition': 'accepted_new', 'outbox_present': True, 'impacts': None, 'current_support_receipt': None}
        description = {'direct_groundings': [], 'transitive_source_refs': [{'data_id': 'a' * 64}],
            'current_transitive_source_refs': [{'data_id': 'b' * 64}], 'current_transitive_data_refs': []}
        new = change_snapshot(row, description)
        self.assertEqual(new['change_kind'], 'new_node')
        self.assertFalse(new['stored_impact_present'])
        self.assertEqual(new['source_data_ids'], ['b' * 64])
        self.assertEqual(new['impact_projection']['wiki_links'], [])
        support = {**row, 'disposition': 'reused', 'outbox_present': False,
            'current_support_receipt': {'record_id': uid(1), 'node_revision_id': uid(3), 'event_order': 15}}
        actual = change_snapshot(support, description)
        self.assertEqual(actual['change_kind'], 'current_support')
        self.assertEqual(actual['current_support_receipt'], support['current_support_receipt'])
        with self.assertRaises(PalimpsestError):
            change_snapshot({**row, 'disposition': 'reused'}, description)

    def test_stored_material_impacts_are_preserved_and_active_support_changes_are_stale(self):
        saved = {'source_revision_id': uid(4), 'wiki_links': [], 'derivations': [{'record_id': uid(5)}]}
        row = {'record_id': uid(1), 'result_node_id': uid(2), 'result_node_revision_id': uid(3),
            'disposition': 'accepted_revision', 'outbox_present': True, 'impacts': saved,
            'current_support_receipt': None}
        actual = change_snapshot(row, {'direct_groundings': [], 'transitive_source_refs': []})
        self.assertEqual(actual['impact_projection'], saved)
        self.assertTrue(actual['stored_impact_present'])
        self.assertEqual(actual['change_kind'], 'material_revision')
        plan = {'current_revisions': [{'knode_id': uid(2), 'current_revision_id': uid(3),
            'current_support_signature': 'old'}]}
        cursor = SimpleNamespace(fetchall=lambda: [{'knode_id': uid(2), 'current_revision_id': uid(3)}])
        conn = SimpleNamespace(execute=lambda *args: cursor)
        with patch.object(wiki_refresh.knowledge_provenance, 'load', return_value={}), \
                patch.object(wiki_refresh.knowledge_provenance, 'describe', return_value={'current_support_signature': 'new'}), \
                self.assertRaises(PalimpsestError) as raised:
            WikiRefreshRuntime.__new__(WikiRefreshRuntime)._bindings(conn, plan)
        self.assertEqual(raised.exception.code, 'wiki_refresh_revision_changed')

    def test_selects_current_exact_links_once_preserving_old_imports(self):
        page, catalog, link = page_fixture()
        old = {**link, 'link_id': uid(17), 'request_id': uid(16)}
        other = {**link, 'link_id': uid(27), 'wiki_id': uid(25)}
        impact = {'source_revision_id': uid(9), 'wiki_links': [old, link, other]}
        result = select_targets(impact, uid(5), uid(6), catalog, {page['snapshot_id']: page})
        self.assertEqual(len(result['targets']), 1)
        self.assertEqual(result['targets'][0]['impact_links'], [link])
        self.assertEqual(result['historical_only_links'], [old])
        self.assertEqual(result['targets'][0]['source_execution_id'], page['source_execution_id'])

    def test_source_expansion_uses_only_selected_pages(self):
        page, catalog, _ = page_fixture()
        result = select_targets({'wiki_links': []}, uid(5), uid(6), catalog,
            {page['snapshot_id']: page}, source_data_ids=[page['data_id'], 'b' * 64])
        self.assertEqual([item['data_id'] for item in result['targets']], [page['data_id']])
        self.assertEqual(result['targets'][0]['impact_links'], [])

    def test_tampered_snapshot_and_invented_item_are_rejected(self):
        page, catalog, link = page_fixture()
        for altered_page, altered_link in (({**page, 'metadata': {}}, link),
                                           (page, {**link, 'item_key': 'invented'})):
            with self.assertRaises(PalimpsestError) as raised:
                select_targets({'source_revision_id': uid(9), 'wiki_links': [altered_link]},
                    uid(5), uid(6), catalog, {page['snapshot_id']: altered_page})
            self.assertEqual(raised.exception.code, 'wiki_refresh_impact_changed')


class MockRefresh(WikiRefreshRuntime):
    def __init__(self, base, original, sources):
        super().__init__('postgresql://synthetic-unused', base / 'artifacts', base / 'refresh')
        self.original, self.sources, self.runtimes = original, sources, {}
        self.ids = count(50000)
        self.repository.allocate_id = lambda: uid(next(self.ids))
        self.stale = None
        self.imported = None
        self.fail_after_import = False
        self.restore_count = 0
        self.database = SimpleNamespace(restore=self._restore)

    def _restore(self, wiki_id, directory, *, import_id):
        self.restore_count += 1
        source, dest = self.original.store, ProjectionStore(Path(directory))
        for path in source.root.rglob('*'):
            relative = path.relative_to(source.root).as_posix()
            if path.is_file() and not relative.startswith(('locks/', '.')):
                dest.write_bytes(relative, source.read_bytes(relative))

    def _runtime(self, identifier):
        if identifier not in self.runtimes:
            runtime = MockCanonicalRuntime(self.store.root / f'refreshes/{identifier}', self.sources)
            runtime.repository.allocate_id = lambda: uid(next(self.ids))
            self.runtimes[identifier] = runtime
        return self.runtimes[identifier]

    def _current(self, plan):
        if self.stale:
            raise PalimpsestError(self.stale, 'Synthetic stale current reference.')

    def _publish(self, plan, runtime, *, transaction_guard=None):
        if transaction_guard:
            transaction_guard('synthetic_connection')
        if self.imported is None:
            self.imported = {'request_id': plan['sync_request_id'], 'wiki_id': plan['wiki_id'],
                'manifest_sha256': build_archive(runtime.store)['manifest_sha256']}
        if self.fail_after_import:
            self.fail_after_import = False
            raise RuntimeError('Synthetic lost DB import acknowledgement')
        # Actual WikiDatabase returns a transport replay flag which it does not
        # store in imports.result. Recovery reads that immutable bare receipt.
        return {**self.imported, 'replayed': False}

    def _committed(self, plan, state):
        if self.imported:
            assert state['sync_manifest_sha256'] == self.imported['manifest_sha256']
            return self.imported
        return None


@unittest.skipUnless(sys.platform == 'linux', 'Requires actual Linux projection filesystem')
class WikiRefreshRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix='palimpsest-wiki-refresh-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.sources = [synthetic_source(1), synthetic_source(2)]
        self.original = MockCanonicalRuntime(self.base / 'original', self.sources)
        for index, packet in enumerate(self.sources):
            identifier = uid(20000 + index)
            self.original.prepare(packet['source_execution_id'], identifier,
                {'title': f'Synthetic source {index}', 'filename': f'synthetic-{index}.pdf'})
            context = self.original.stage(identifier, exchange(self.original, identifier, 'generator',
                                                               synthetic_proposal(packet)))
            self.original.decide(identifier, exchange(self.original, identifier, 'validator',
                                                       decisions(context['proposal'])))
        self.original_archive = build_archive(self.original.store)
        self.refresh = MockRefresh(self.base, self.original, self.sources)
        self.identifier = uid(30000)
        self.plan = self.install_plan()

    def install_plan(self):
        catalog = self.original.catalog()
        targets = []
        for index, (owner, entry) in enumerate(sorted(catalog['papers'].items())):
            page = self.original._snapshot(entry)
            targets.append({'data_id': owner, 'page_id': page['page_id'],
                'snapshot_id': page['snapshot_id'], 'snapshot_sha256': entry['snapshot_sha256'],
                'source_execution_id': page['source_execution_id'], 'metadata': page['metadata'],
                'feedback_request_id': page['origin_request_id'], 'impact_links': [], 'request_id': uid(31000 + index)})
        plan = {'schema_version': PROFILE, 'refresh_id': self.identifier, 'wiki_id': uid(30001),
            'impact_record_ids': [uid(30002)], 'source_data_ids': [p['data_id'] for p in self.sources],
            'changes': [{'record_id': uid(30002), 'source_revision_id': uid(30003),
                'result_knode_id': uid(30004), 'result_revision_id': uid(30005)}],
            'current_revisions': [], 'source_version_heads': [],
            'base_import_id': uid(30006), 'base_catalog_sha256': digest(catalog),
            'targets': targets, 'historical_only_links': [], 'sync_request_id': uid(30007)}
        plan['plan_sha256'] = digest(plan)
        self.refresh.store.write_json(f'refreshes/{self.identifier}/plan.json', plan)
        return plan

    def submit_generator(self, current, *, suffix=''):
        runtime = self.refresh._runtime(self.identifier)
        job = runtime.show(current['request_id'])
        response = synthetic_proposal(job['input_snapshot']['input'], text_suffix=suffix)
        delivery = exchange(runtime, current['request_id'], 'generator', response)
        return delivery, self.refresh.accept(self.identifier, 'generator', delivery)

    def validator(self, current):
        runtime = self.refresh._runtime(self.identifier)
        context = runtime._context(runtime.show(current['request_id']))
        return exchange(runtime, current['request_id'], 'validator', decisions(context['proposal']))

    def test_two_pages_regenerate_sequentially_validate_and_import_once(self):
        current = self.refresh.advance(self.identifier)
        self.assertEqual(current['state'], 'awaiting_generator')
        for index in range(2):
            generator, current = self.submit_generator(current, suffix='new rendering')
            self.assertEqual(current['state'], 'awaiting_validator')
            self.assertEqual(self.refresh.accept(self.identifier, 'generator', generator), current)
            self.assertIsNone(self.refresh.imported)
            current = self.refresh.accept(self.identifier, 'validator', self.validator(current))
        self.assertEqual(current['state'], 'completed')
        self.assertEqual(current['regenerated_pages'], 2)
        self.assertEqual(self.refresh.restore_count, 1)
        self.assertEqual(self.refresh.advance(self.identifier), current)
        self.assertEqual(build_archive(self.original.store)['files'], self.original_archive['files'])
        archive = build_archive(self.refresh._runtime(self.identifier).store)
        for identifier, snapshot in self.original_archive['snapshots'].items():
            self.assertEqual(archive['snapshots'][identifier], snapshot)
        self.assertGreater(len(archive['snapshots']), len(self.original_archive['snapshots']))

    def test_validator_independence_and_rejection_hold_database(self):
        _, current = self.submit_generator(self.refresh.advance(self.identifier))
        runtime = self.refresh._runtime(self.identifier)
        delivery = self.validator(current)
        wrong = deepcopy(delivery)
        wrong['receipt']['provider_ref'] = runtime.store.read_json(
            f"jobs/{current['request_id']}/generator-exchange.json")['receipt']['provider_ref']
        with self.assertRaises(PalimpsestError) as raised:
            self.refresh.accept(self.identifier, 'validator', wrong)
        self.assertEqual(raised.exception.code, 'wiki_validator_not_independent')
        response = delivery['response']
        response['complete'] = False
        delivery = exchange(runtime, current['request_id'], 'validator', response)
        held = self.refresh.accept(self.identifier, 'validator', delivery)
        self.assertEqual(held['state'], 'needs_review')
        self.assertIsNone(self.refresh.imported)
        self.assertEqual(self.refresh.advance(self.identifier)['state'], 'needs_review')

    def test_recovers_after_catalog_publication_without_another_model_exchange(self):
        _, current = self.submit_generator(self.refresh.advance(self.identifier), suffix='changed')
        delivery = self.validator(current)
        def crash(phase):
            if phase == 'after_catalog':
                raise RuntimeError('Synthetic interruption after file catalog publication')
        with self.assertRaises(RuntimeError):
            self.refresh.accept(self.identifier, 'validator', delivery, checkpoint=crash)
        next_page = self.refresh.advance(self.identifier)
        self.assertEqual(next_page['state'], 'awaiting_generator')
        self.assertNotEqual(next_page['request_id'], current['request_id'])
        self.assertEqual(self.refresh.accept(self.identifier, 'validator', delivery), next_page)

    def test_recovers_committed_import_even_after_later_current_changes(self):
        current = self.refresh.advance(self.identifier)
        for index in range(2):
            _, current = self.submit_generator(current)
            if index == 0:
                current = self.refresh.accept(self.identifier, 'validator', self.validator(current))
        self.refresh.fail_after_import = True
        with self.assertRaises(RuntimeError):
            self.refresh.accept(self.identifier, 'validator', self.validator(current))
        self.refresh.stale = 'wiki_refresh_revision_changed'
        result = self.refresh.advance(self.identifier)
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(result['import'], self.refresh.imported)

    def test_stale_head_blocks_before_another_call_or_publication(self):
        self.refresh.advance(self.identifier)
        self.refresh.stale = 'wiki_refresh_head_changed'
        with self.assertRaises(PalimpsestError) as raised:
            self.refresh.advance(self.identifier)
        self.assertEqual(raised.exception.code, 'wiki_refresh_head_changed')
        self.assertIsNone(self.refresh.imported)

    def test_explicit_transport_retry_preserves_failure_and_frozen_input(self):
        current = self.refresh.advance(self.identifier)
        request = json.loads(Path(current['request_file']).read_text())
        failure = {'input_sha256': request['input_sha256'], 'actual_delivery': None,
            'output_sha256': None, 'prompt_sha256': sha256(request['prompt'].encode()).hexdigest(),
            'schema_sha256': digest(request['schema']), 'error_code': 'synthetic_transport_interruption'}
        held = self.refresh.call_failed(self.identifier, 'generator', failure)
        self.assertEqual(held['state'], 'failed')
        self.assertEqual(self.refresh.advance(self.identifier)['state'], 'failed')
        retried = self.refresh.advance(self.identifier, retry_failed=True)
        self.assertEqual(retried['state'], 'awaiting_generator')
        self.assertNotEqual(retried['request_id'], current['request_id'])
        retried_request = json.loads(Path(retried['request_file']).read_text())
        self.assertEqual(retried_request['delivered_information_ids'], request['delivered_information_ids'])
        self.assertEqual(json.loads(Path(current['request_file']).read_text()), request)
        _, validating = self.submit_generator(retried)
        self.assertEqual(validating['state'], 'awaiting_validator')
        runtime = self.refresh._runtime(self.identifier)
        self.assertEqual(runtime.store.read_json(
            f"jobs/{current['request_id']}/failures/{digest(failure)}.json"), failure)
        retry_job = runtime.show(retried['request_id'])
        self.assertEqual(retry_job['input_snapshot']['prior_feedback']['request_id'], current['request_id'])
        self.assertEqual(retry_job['input_snapshot']['prior_feedback']['failure']['code'], failure['error_code'])
        next_page = self.refresh.accept(self.identifier, 'validator', self.validator(validating))
        _, validating = self.submit_generator(next_page)
        completed = self.refresh.accept(self.identifier, 'validator', self.validator(validating))
        self.assertEqual(completed['state'], 'completed')
        archive = build_archive(runtime.store)
        self.assertEqual(archive['jobs'][current['request_id']]['state'], 'failed')
        self.assertEqual(archive['jobs'][retried['request_id']]['state'], 'compiled')

    def test_publication_guard_prevents_stale_claim_from_promoting_file_catalog(self):
        _, current = self.submit_generator(self.refresh.advance(self.identifier))
        runtime = self.refresh._runtime(self.identifier)
        before = runtime.catalog()
        @contextmanager
        def denied():
            raise PalimpsestError('synthetic_claim_expired', 'Synthetic publication fence.')
            yield
        with self.assertRaises(PalimpsestError) as raised:
            self.refresh.accept(self.identifier, 'validator', self.validator(current), publication_guard=denied)
        self.assertEqual(raised.exception.code, 'synthetic_claim_expired')
        self.assertEqual(runtime.catalog(), before)
        self.assertIsNone(self.refresh.imported)

    def test_validator_transport_retry_uses_new_path_and_reuses_exact_generator_call(self):
        generator, current = self.submit_generator(self.refresh.advance(self.identifier))
        request = json.loads(Path(current['request_file']).read_text())
        failure = {'input_sha256': request['input_sha256'], 'actual_delivery': None,
            'output_sha256': None, 'prompt_sha256': sha256(request['prompt'].encode()).hexdigest(),
            'schema_sha256': digest(request['schema']), 'error_code': 'synthetic_validator_transport_interruption'}
        self.refresh.call_failed(self.identifier, 'validator', {'failure': failure})
        self.assertEqual(self.refresh.advance(self.identifier)['state'], 'failed')
        retried = self.refresh.advance(self.identifier, retry_failed=True)
        self.assertEqual(retried['state'], 'awaiting_validator')
        self.assertNotEqual(retried['request_id'], current['request_id'])
        self.assertNotEqual(retried['request_file'], current['request_file'])
        runtime = self.refresh._runtime(self.identifier)
        self.assertEqual(runtime.store.read_json(f"jobs/{retried['request_id']}/generator-exchange.json"), generator)
        self.assertEqual(json.loads(Path(retried['request_file']).read_text())['input_sha256'], request['input_sha256'])
        next_page = self.refresh.accept(self.identifier, 'validator', self.validator(retried))
        _, validating = self.submit_generator(next_page)
        self.assertEqual(self.refresh.accept(self.identifier, 'validator', self.validator(validating))['state'], 'completed')
        archive = build_archive(runtime.store)
        self.assertEqual(archive['jobs'][current['request_id']]['state'], 'proposed')
        self.assertEqual(archive['jobs'][retried['request_id']]['state'], 'compiled')
        self.assertEqual(runtime.store.read_json(f"jobs/{current['request_id']}/failures/{digest(failure)}.json"), failure)

    def test_only_operator_semantic_retry_adds_attempt_and_preserves_source_and_hold(self):
        _, current = self.submit_generator(self.refresh.advance(self.identifier))
        runtime = self.refresh._runtime(self.identifier)
        held_id = current['request_id']
        rejected = self.validator(current)
        rejected['response']['complete'] = False
        rejected = exchange(runtime, held_id, 'validator', rejected['response'])
        self.assertEqual(self.refresh.accept(self.identifier, 'validator', rejected)['state'], 'needs_review')
        self.assertEqual(self.refresh.advance(self.identifier, retry_failed=True)['state'], 'needs_review')
        self.assertNotIn('attempts', self.refresh.show(self.identifier)['progress'])
        files = {name: runtime.store.read_bytes(f'jobs/{held_id}/{name}') for name in
                 ('job.json', 'generator-exchange.json', 'validator-exchange.json', 'decision.json')}
        old_input = deepcopy(runtime.show(held_id)['input_snapshot']['input'])
        before_catalog = runtime.catalog()
        requested = self.refresh.retry_review(self.identifier, 'Recheck the exact source wording after the held review.')
        self.assertEqual(requested['state'], 'review_requested')
        self.assertEqual(requested['canonical_writes'], 0)
        self.assertEqual(requested['new_d2i_calls'], 0)
        self.assertEqual(requested['provider_calls'], 0)
        current = self.refresh.advance(self.identifier)
        self.assertEqual(current['state'], 'awaiting_generator')
        self.assertNotEqual(current['request_id'], held_id)
        new_job = runtime.show(current['request_id'])
        self.assertEqual(new_job['input_snapshot']['input'], old_input)
        self.assertEqual(new_job['input_snapshot']['prior_feedback']['request_id'], held_id)
        self.assertIn(requested['reason'], new_job['input_snapshot']['prior_feedback']['review_notes'])
        self.assertEqual(runtime.catalog(), before_catalog)
        for name, raw in files.items():
            self.assertEqual(runtime.store.read_bytes(f'jobs/{held_id}/{name}'), raw)
        # Even a later transport retry retains the operator's notes and reuses
        # only the exact source generator call, never a D or K creation path.
        _, current = self.submit_generator(current)
        request = json.loads(Path(current['request_file']).read_text())
        failure = {'input_sha256': request['input_sha256'], 'actual_delivery': None, 'output_sha256': None,
            'prompt_sha256': sha256(request['prompt'].encode()).hexdigest(), 'schema_sha256': digest(request['schema']),
            'error_code': 'synthetic_validator_transport_interruption'}
        self.refresh.call_failed(self.identifier, 'validator', failure)
        current = self.refresh.advance(self.identifier, retry_failed=True)
        self.assertEqual(current['state'], 'awaiting_validator')
        self.assertIn(requested['reason'], runtime.show(current['request_id'])['input_snapshot']['prior_feedback']['review_notes'])
        next_page = self.refresh.accept(self.identifier, 'validator', self.validator(current))
        _, current = self.submit_generator(next_page)
        finished = self.refresh.accept(self.identifier, 'validator', self.validator(current))
        self.assertEqual(finished['state'], 'completed')
        self.assertEqual(finished['canonical_writes'], 0)
        self.assertEqual(finished['new_d2i_calls'], 0)
        self.assertEqual(build_archive(runtime.store)['jobs'][held_id]['state'], 'needs_review')

    def test_structural_response_retry_is_explicit_and_stale_scope_cannot_be_reopened(self):
        current = self.refresh.advance(self.identifier)
        runtime = self.refresh._runtime(self.identifier)
        original = runtime.show(current['request_id'])
        invalid = synthetic_proposal(original['input_snapshot']['input'])
        invalid['items'][0]['evidence'][0]['quote'] = 'A quote not present in this retained source.'
        delivery = exchange(runtime, current['request_id'], 'generator', invalid)
        with self.assertRaises(PalimpsestError):
            self.refresh.accept(self.identifier, 'generator', delivery)
        self.assertEqual(self.refresh.advance(self.identifier, retry_failed=True)['state'], 'failed')
        self.assertEqual(runtime.show(current['request_id'])['failure']['response'], invalid)
        self.refresh.stale = 'wiki_refresh_head_changed'
        with self.assertRaises(PalimpsestError) as raised:
            self.refresh.retry_review(self.identifier, 'Review this failed source-only proposal.')
        self.assertEqual(raised.exception.code, 'wiki_refresh_head_changed')
        self.assertNotIn('attempts', self.refresh.show(self.identifier)['progress'])
        self.refresh.stale = None
        retry = self.refresh.retry_review(self.identifier, 'Review this failed source-only proposal.')
        upcoming = self.refresh.advance(self.identifier)
        self.assertEqual(upcoming['request_id'], retry['request_id'])
        job = runtime.show(upcoming['request_id'])
        self.assertEqual(job['input_snapshot']['input'], original['input_snapshot']['input'])
        self.assertEqual(job['input_snapshot']['prior_feedback']['failure']['response'], invalid)
        with self.assertRaises(PalimpsestError) as raised:
            self.refresh.retry_review(self.identifier, 'Do not create another attempt while this one is pending.')
        self.assertEqual(raised.exception.code, 'wiki_refresh_no_held_review')

    def test_cached_completed_flag_without_committed_import_is_not_authority(self):
        self.refresh.store.replace_json(f'refreshes/{self.identifier}/state.json',
            {'restored': False, 'result': {'state': 'completed', 'regenerated_pages': 2}})
        with self.assertRaises(PalimpsestError) as raised:
            self.refresh.advance(self.identifier)
        self.assertEqual(raised.exception.code, 'wiki_refresh_completion_missing')
        self.assertIsNone(self.refresh.imported)

    def test_cached_completion_ignores_only_transient_import_replay_flag(self):
        current = self.refresh.advance(self.identifier)
        for _ in range(2):
            _, current = self.submit_generator(current)
            current = self.refresh.accept(self.identifier, 'validator', self.validator(current))
        self.assertIs(current['import']['replayed'], False)
        self.assertNotIn('replayed', self.refresh.imported)
        self.assertEqual(self.refresh.advance(self.identifier), current)
        state = self.refresh._state(self.identifier)
        state['result']['import']['unverified_extra_effect'] = 999
        self.refresh._save(self.identifier, state)
        with self.assertRaises(PalimpsestError) as raised:
            self.refresh.advance(self.identifier)
        self.assertEqual(raised.exception.code, 'wiki_refresh_completion_changed')


if __name__ == '__main__':
    unittest.main()
