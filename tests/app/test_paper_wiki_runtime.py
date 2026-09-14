"""Real Linux Wiki cache, synthetic model receipts; canonical mocks are explicit.

The final class additionally checks actual PostgreSQL D/I rows through a dedicated
PALIMPSEST_TEST_DSN. No test calls a model, reparses a PDF or migrates/deletes a DB.
"""

from copy import deepcopy
from hashlib import sha256
from itertools import count
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg

from palimpsest.artifact_store import ArtifactStore
from palimpsest.canonical_store import PostgresRepository
from palimpsest.compiler_runtime import CompilerRuntime
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.knowledge_runtime import MODEL
from palimpsest.multi_source_i2k import combine_packets
from palimpsest.paper_wiki_runtime import PaperWikiRuntime
from palimpsest.service import DataService
from test_multi_source_i2k import uid
from test_paper_wiki import source_packet, decisions


PNG = b'\x89PNG\r\n\x1a\nsynthetic image payload; not a real paper image'
TOPIC = {'topic_key': 'synthetic-sequences', 'title': 'Synthetic sequences',
         'scope': 'Synthetic test source definitions only.'}


def synthetic_source(number=1):
    packet = source_packet()
    packet['data_id'] = sha256(f'synthetic source {number}'.encode()).hexdigest()
    packet['source_execution_id'] = uid(number * 100 + 20)
    packet['model_input']['data_id'] = packet['data_id']
    image_sha = sha256(PNG).hexdigest()
    for index, unit in enumerate(packet['model_input']['information']):
        unit['information_id'] = uid(number * 100 + index + 1)
        unit['origin_record_id'] = uid(number * 100 + index + 11)
        for media in unit['media']:
            media.update(sha256=image_sha, byte_size=len(PNG))
    packet['target_information_ids'] = [unit['information_id'] for unit in packet['model_input']['information']]
    packet['media_assets'] = [{'sha256': image_sha, 'byte_size': len(PNG),
        'artifact_path': f'derived/objects/sha256/{image_sha[:2]}/{image_sha}'}]
    packet['input_sha256'] = digest({key: value for key, value in packet.items() if key != 'input_sha256'})
    return packet


def synthetic_proposal(packet, *, text_suffix=''):
    units = packet['model_input']['information']
    return {'items': [{'item_key': f'item-{index}', 'section': 'overview' if index == 0 else 'findings',
        'text': '합성 검사용 원문 표현. ' + text_suffix,
        'evidence': [{'information_id': unit['information_id'], 'quote': unit['content'],
                      'media_sha256': None, 'source_role': 'other'}],
        'topic_keys': [TOPIC['topic_key']] if index == 0 else []}
        for index, unit in enumerate(units)], 'topics': [deepcopy(TOPIC)],
        'reviews': [{'information_id': unit['information_id'], 'disposition': 'used',
                     'reason': 'Synthetic source selected for a storage contract test.'} for unit in units],
        'complete': True, 'issues': []}


def exchange(runtime, identifier, phase, response):
    """Fabricate a labelled test receipt, never provider-delivery evidence."""
    info = runtime.model_request(identifier, phase)
    request = json.loads(Path(info['request_file']).read_text(encoding='utf-8'))
    job = runtime.show(identifier)
    return {'response': deepcopy(response), 'receipt': {
        'synthetic_test_only': True, 'profile': deepcopy(MODEL),
        'actual_delivery': True, 'original_pdf_delivered': False,
        'provider_ref': f'synthetic-no-model:{identifier}:{phase}',
        'input_sha256': request['input_sha256'], 'output_sha256': digest(response),
        'prompt_sha256': sha256(request['prompt'].encode()).hexdigest(),
        'schema_sha256': digest(request['schema']),
        'delivered_information_ids': request['delivered_information_ids'],
        'image_attachments': [{key: asset[key] for key in ('sha256', 'byte_size')} for asset in job['assets']]}}


class MockCanonicalRuntime(PaperWikiRuntime):
    """Actual projection files/locks, mock Data allocation and canonical source checks."""
    def __init__(self, base, packets):
        super().__init__('postgresql://synthetic-unused', base / 'artifacts', base / 'wiki')
        self.packets = {packet['source_execution_id']: deepcopy(packet) for packet in packets}
        identifiers = count(10000)
        self.repository = SimpleNamespace(allocate_id=lambda: uid(next(identifiers)),
            get_data=lambda identifier: {'data_id': identifier, 'byte_size': 123, 'media_type': 'application/pdf'})
        self.source = SimpleNamespace(derived=SimpleNamespace(read=self._media))
        self.source_checks = 0

    def _media(self, identifier, size):
        assert identifier == sha256(PNG).hexdigest() and size == len(PNG)
        return PNG

    def _source(self, identifier):
        packet = deepcopy(self.packets[identifier])
        combine_packets([packet])
        return packet

    def _verify_source(self, packet):
        self.source_checks += 1
        if packet != self.packets[packet['source_execution_id']]:
            raise PalimpsestError('synthetic_canonical_input_changed', 'Synthetic canonical mismatch.')


@unittest.skipUnless(sys.platform == 'linux', 'Requires actual Linux projection filesystem')
class PaperWikiRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix='palimpsest-wiki-runtime-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.sources = [synthetic_source(1), synthetic_source(2)]
        self.runtime = MockCanonicalRuntime(self.base, self.sources)

    def prepare(self, identifier=uid(500), source=0, **kwargs):
        return self.runtime.prepare(self.sources[source]['source_execution_id'], identifier,
            {'title': f'Synthetic paper {source + 1}', 'filename': f'fixture{source + 1}.pdf'}, **kwargs)

    def stage(self, identifier=uid(500), source=0, response=None):
        result = exchange(self.runtime, identifier, 'generator', response or synthetic_proposal(self.sources[source]))
        context = self.runtime.stage(identifier, result)
        return context, result

    def compile(self, identifier=uid(500), source=0, response=None):
        self.prepare(identifier, source)
        context, generator = self.stage(identifier, source, response)
        validator = exchange(self.runtime, identifier, 'validator', decisions(context['proposal']))
        return self.runtime.decide(identifier, validator), generator, validator

    def assert_code(self, code, callback):
        with self.assertRaises(PalimpsestError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_prepare_delivery_stage_commit_and_all_replays_preserve_source_and_ids(self):
        before = deepcopy(self.sources)
        result, generator, validator = self.compile()
        self.assertEqual(self.sources, before)
        self.assertEqual(self.runtime.source_checks, 2)
        self.assertEqual((result['canonical_writes'], result['new_d2i_calls']), (0, 0))
        self.assertTrue(self.prepare()['replayed'])
        first_context = self.runtime.stage(uid(500), generator)
        self.assertEqual(first_context['input_snapshot']['input'], before[0])
        repeated = self.runtime.decide(uid(500), validator)
        self.assertTrue(repeated['replayed'])
        self.assertEqual(repeated['paper_snapshot_id'], result['paper_snapshot_id'])
        self.assertEqual(self.runtime.catalog()['version'], 1)
        self.assert_code('idempotency_conflict', lambda: self.runtime.prepare(
            before[0]['source_execution_id'], uid(500), {'title': 'Changed', 'filename': 'fixture1.pdf'}))
        job = self.runtime.show(uid(500))
        self.assertEqual(self.runtime.store.read_bytes(job['assets'][0]['relative_path']), PNG)

    def test_second_request_versions_same_paper_and_second_data_aggregates_same_topic(self):
        first, _, _ = self.compile()
        first_catalog = self.runtime.catalog()
        first_paper = self.runtime._snapshot(first_catalog['papers'][self.sources[0]['data_id']])
        second, _, _ = self.compile(uid(501), response=synthetic_proposal(self.sources[0], text_suffix='갱신 표현'))
        self.assertEqual(first['paper_page_id'], second['paper_page_id'])
        self.assertNotEqual(first['paper_snapshot_id'], second['paper_snapshot_id'])
        current = self.runtime._snapshot(self.runtime.catalog()['papers'][self.sources[0]['data_id']])
        self.assertEqual(current['previous_snapshot_id'], first['paper_snapshot_id'])
        self.assertEqual(self.runtime.store.read_json('snapshots/' + first['paper_snapshot_id'] + '.json'), first_paper)
        third, _, _ = self.compile(uid(502), source=1)
        catalog = self.runtime.catalog()
        topic = self.runtime._snapshot(catalog['topics'][TOPIC['topic_key']])
        self.assertEqual(topic['page_id'], first_catalog['topics'][TOPIC['topic_key']]['page_id'])
        self.assertEqual((third['paper_count'], third['topic_count']), (2, 1))
        self.assertEqual({c['paper_data_id'] for c in topic['contributions']}, {s['data_id'] for s in self.sources})
        for contribution in topic['contributions']:
            self.assertEqual(contribution['items'][0]['evidence'][0]['data_id'], contribution['paper_data_id'])

    def test_stale_catalog_refuses_late_commit_without_overwriting_first_paper(self):
        self.prepare(uid(500), 0)
        self.prepare(uid(501), 1)
        for identifier, source in ((uid(500), 0), (uid(501), 1)):
            context, _ = self.stage(identifier, source)
            response = exchange(self.runtime, identifier, 'validator', decisions(context['proposal']))
            if source == 0:
                self.runtime.decide(identifier, response)
            else:
                self.assert_code('wiki_catalog_changed', lambda: self.runtime.decide(identifier, response))
        catalog = self.runtime.catalog()
        self.assertEqual(list(catalog['papers']), [self.sources[0]['data_id']])
        self.assertEqual(catalog['version'], 1)
        self.assertEqual(self.runtime.show(uid(501))['state'], 'proposed')

    def test_validator_rejection_holds_page_and_feedback_uses_original_snapshot(self):
        self.prepare()
        context, _ = self.stage()
        result = decisions(context['proposal'])
        result['items'][0].update(verdict='rejected', citations_sufficient=False)
        result['issues'] = ['Synthetic incomplete citation.']
        validator = exchange(self.runtime, uid(500), 'validator', result)
        self.assertEqual(self.runtime.decide(uid(500), validator)['state'], 'needs_review')
        self.assertEqual(self.runtime.catalog()['papers'], {})
        self.assertTrue(self.runtime.decide(uid(500), validator)['replayed'])
        prepared = self.prepare(uid(501), feedback_request_id=uid(500))
        feedback = prepared['input_snapshot']['prior_feedback']
        self.assertEqual(feedback['proposal'], context['proposal'])
        self.assertEqual(feedback['result']['items'][0]['verdict'], 'rejected')
        self.assertEqual(prepared['input_snapshot']['input'], self.sources[0])

    def test_delivery_hash_profile_media_and_validator_independence_are_enforced(self):
        self.prepare()
        generator = exchange(self.runtime, uid(500), 'generator', synthetic_proposal(self.sources[0]))
        mutations = [lambda r: r.update(input_sha256='0' * 64),
                     lambda r: r.update(output_sha256='0' * 64),
                     lambda r: r.update(prompt_sha256='0' * 64),
                     lambda r: r.update(schema_sha256='0' * 64),
                     lambda r: r.update(image_attachments=[]),
                     lambda r: r.update(delivered_information_ids=[]),
                     lambda r: r['profile'].update(model='synthetic-wrong-model')]
        for mutate in mutations:
            changed = deepcopy(generator)
            mutate(changed['receipt'])
            self.assert_code('wiki_delivery_mismatch', lambda: self.runtime.stage(uid(500), changed))
            self.assertEqual(self.runtime.show(uid(500))['state'], 'prepared')
        context = self.runtime.stage(uid(500), generator)
        validator = exchange(self.runtime, uid(500), 'validator', decisions(context['proposal']))
        validator['receipt']['provider_ref'] = generator['receipt']['provider_ref']
        self.assert_code('wiki_validator_not_independent', lambda: self.runtime.decide(uid(500), validator))
        self.assertEqual(self.runtime.catalog()['version'], 0)

    def test_changed_implementation_and_validation_context_are_rejected(self):
        self.prepare()
        with patch('palimpsest.paper_wiki_runtime._profile', return_value={'changed': True}):
            self.assert_code('wiki_implementation_changed', lambda: self.runtime.model_request(uid(500), 'generator'))
        self.stage()
        context = self.runtime.store.read_json(f'jobs/{uid(500)}/validation-context.json')
        context['proposal']['items'][0]['text'] += ' changed'
        self.runtime.store.replace_json(f'jobs/{uid(500)}/validation-context.json', context)
        self.assert_code('wiki_context_changed', lambda: self.runtime.model_request(uid(500), 'validator'))

    def test_crash_after_catalog_recovers_committed_ids_without_a_second_version(self):
        self.prepare()
        context, _ = self.stage()
        validator = exchange(self.runtime, uid(500), 'validator', decisions(context['proposal']))
        def crash(phase):
            if phase == 'after_catalog':
                raise RuntimeError('synthetic post-publication crash')
        with self.assertRaisesRegex(RuntimeError, 'synthetic post-publication crash'):
            self.runtime.decide(uid(500), validator, checkpoint=crash)
        saved = self.runtime.catalog()['commits'][uid(500)]
        self.assertEqual(self.runtime.show(uid(500))['state'], 'proposed')
        replay = self.runtime.decide(uid(500), validator)
        self.assertEqual(replay['paper_snapshot_id'], saved['paper_snapshot_id'])
        self.assertTrue(replay['replayed'])
        self.assertEqual(self.runtime.catalog()['version'], 1)
        self.assertEqual(self.runtime.show(uid(500))['state'], 'compiled')

    def test_stage_replay_recovers_after_exchange_written_before_job_update(self):
        self.prepare()
        generator = exchange(self.runtime, uid(500), 'generator', synthetic_proposal(self.sources[0]))
        with patch.object(self.runtime, '_save_job', side_effect=RuntimeError('synthetic stage interruption')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic stage interruption'):
                self.runtime.stage(uid(500), generator)
        self.assertEqual(self.runtime.show(uid(500))['state'], 'prepared')
        context = self.runtime.stage(uid(500), generator)
        self.assertEqual(self.runtime.show(uid(500))['state'], 'proposed')
        self.assertEqual(self.runtime.show(uid(500))['validation_context_sha256'], digest(context))
        self.assertEqual(self.runtime.model_request(uid(500), 'validator')['phase'], 'validator')

    def test_dispatch_failure_preserves_staged_proposal_and_cannot_change_compiled_state(self):
        prepared = self.prepare()
        def failure(phase):
            info = self.runtime.model_request(uid(500), phase)
            request = json.loads(Path(info['request_file']).read_text())
            return {'input_sha256': info['input_sha256'], 'prompt_sha256': info['prompt_sha256'],
                    'schema_sha256': digest(request['schema']), 'actual_delivery': None,
                    'output_sha256': None, 'error_code': 'synthetic_dispatch_failure'}
        generator_failure = failure('generator')
        self.assertEqual(self.runtime.call_failed(uid(500), 'generator', generator_failure)['state'], 'failed')
        self.assertEqual(self.runtime.show(uid(500))['input_snapshot'], prepared['input_snapshot'])
        context, _ = self.stage()
        validator_failure = failure('validator')
        self.assertEqual(self.runtime.call_failed(uid(500), 'validator', validator_failure)['state'], 'proposed')
        self.assertEqual(self.runtime.store.read_json(f'jobs/{uid(500)}/proposal.json'), context['proposal'])
        self.assertEqual(self.runtime.catalog()['papers'], {})
        validator = exchange(self.runtime, uid(500), 'validator', decisions(context['proposal']))
        self.runtime.decide(uid(500), validator)
        self.assert_code('invalid_wiki_state', lambda: self.runtime.call_failed(uid(500), 'generator', generator_failure))
        self.assertEqual(self.runtime.show(uid(500))['state'], 'compiled')

    def test_proposal_file_cannot_diverge_from_the_exact_validator_input(self):
        self.prepare()
        context, _ = self.stage()
        validator = exchange(self.runtime, uid(500), 'validator', decisions(context['proposal']))
        changed = deepcopy(context['proposal'])
        changed['items'][0]['text'] = 'Fabricated text never delivered to Validator.'
        self.runtime.store.replace_json(f'jobs/{uid(500)}/proposal.json', changed)
        with self.assertRaises(PalimpsestError):
            self.runtime.decide(uid(500), validator)
        self.assertEqual(self.runtime.catalog()['papers'], {})
        self.assertEqual(self.runtime.show(uid(500))['state'], 'proposed')

    def test_job_source_owner_cannot_diverge_from_frozen_input_snapshot(self):
        self.prepare()
        context, _ = self.stage()
        validator = exchange(self.runtime, uid(500), 'validator', decisions(context['proposal']))
        job = self.runtime.show(uid(500))
        job['source_data_id'] = '0' * 64
        self.runtime.store.replace_json(f'jobs/{uid(500)}/job.json', job)
        with self.assertRaises(PalimpsestError):
            self.runtime.decide(uid(500), validator)
        self.assertEqual(self.runtime.catalog()['papers'], {})

    def test_changed_media_bytes_are_rejected_before_a_model_request_is_written(self):
        job = self.prepare()
        path = self.runtime.store.root / job['assets'][0]['relative_path']
        changed = PNG[:-1] + bytes([PNG[-1] ^ 1])
        self.assertEqual(len(changed), len(PNG))
        path.write_bytes(changed)  # Simulate external damage to the derived cache.
        self.assert_code('wiki_media_changed', lambda: self.runtime.model_request(uid(500), 'generator'))
        self.assertFalse((self.runtime.store.root / f'jobs/{uid(500)}/generator-request.json').exists())
        self.assertEqual(self.runtime.show(uid(500))['state'], 'prepared')
        self.assertEqual(self.runtime.catalog()['papers'], {})

    def test_topic_disappearance_and_reappearance_preserve_page_identity_and_history(self):
        self.compile()
        initial = self.runtime.catalog()['topics'][TOPIC['topic_key']]
        without_topic = synthetic_proposal(self.sources[0])
        without_topic['topics'] = []
        for item in without_topic['items']:
            item['topic_keys'] = []
        removed, _, _ = self.compile(uid(501), response=without_topic)
        dormant = self.runtime.catalog()['topics'][TOPIC['topic_key']]
        self.assertEqual(removed['topic_count'], 0)
        self.assertFalse(dormant['active'])
        self.assertEqual(dormant['page_id'], initial['page_id'])
        self.assertEqual(self.runtime._snapshot(dormant)['contributions'], [])
        self.assertEqual(self.runtime._snapshot(dormant)['previous_snapshot_id'], initial['snapshot_id'])
        restored, _, _ = self.compile(uid(502))
        active = self.runtime.catalog()['topics'][TOPIC['topic_key']]
        self.assertEqual(restored['topic_count'], 1)
        self.assertTrue(active['active'])
        self.assertEqual(active['page_id'], initial['page_id'])
        self.assertEqual(self.runtime._snapshot(active)['previous_snapshot_id'], dormant['snapshot_id'])
        history = self.runtime.history(active['page_id'])['snapshots']
        self.assertEqual([snapshot['snapshot_id'] for snapshot in history],
                         [active['snapshot_id'], dormant['snapshot_id'], initial['snapshot_id']])
        self.assertEqual(len({snapshot['page_id'] for snapshot in history}), 1)

    def test_compiled_paper_can_be_reedited_with_bound_review_notes_without_changing_publication(self):
        published, _, _ = self.compile()
        prior_job = self.runtime.show(uid(500))
        catalog = deepcopy(self.runtime.catalog())
        old_request = {'source_execution_id': self.sources[0]['source_execution_id'],
                       'metadata': prior_job['metadata'], 'feedback_request_id': None}
        self.assertNotIn('review_notes', prior_job)
        self.assertEqual(prior_job['request_sha256'], digest(old_request))
        notes = ['Check whether 24 h starts at treatment or challenge.',
                 'Check the source block containing the time reference; do not assume the correction.']
        prepared = self.prepare(uid(501), feedback_request_id=uid(500), review_notes=notes)
        expected = {**old_request, 'feedback_request_id': uid(500), 'review_notes': notes}
        self.assertEqual(prepared['request_sha256'], digest(expected))
        self.assertEqual(prepared['input_snapshot']['prior_feedback']['review_notes'], notes)
        self.assertEqual(prepared['input_snapshot']['prior_feedback']['state'], 'compiled')
        self.assertEqual(prepared['input_snapshot']['input'], self.sources[0])
        self.assertEqual(self.runtime.catalog(), catalog)
        self.assertEqual(self.runtime.show(uid(500)), prior_job)
        request_info = self.runtime.model_request(uid(501), 'generator')
        request = json.loads(Path(request_info['request_file']).read_text())
        context = json.loads(request['prompt'].split('\nPAGE_CONTEXT_JSON:\n', 1)[1].split('\nSOURCE_JSON:\n', 1)[0])
        self.assertEqual(context['prior_feedback']['review_notes'], notes)
        self.assertTrue(self.prepare(uid(501), feedback_request_id=uid(500), review_notes=notes)['replayed'])
        self.assert_code('idempotency_conflict', lambda: self.prepare(uid(501),
            feedback_request_id=uid(500), review_notes=notes + ['Additional check.']))
        self.assertEqual(self.runtime.catalog()['papers'][self.sources[0]['data_id']]['snapshot_id'],
                         published['paper_snapshot_id'])

    def test_review_notes_cannot_be_injected_or_changed_outside_the_request_fingerprint(self):
        self.compile()
        self.prepare(uid(501), feedback_request_id=uid(500), review_notes=['Check the time anchor.'])
        original = self.runtime.show(uid(501))
        catalog = deepcopy(self.runtime.catalog())
        for mutation in ('top_level', 'snapshot', 'both'):
            changed = deepcopy(original)
            if mutation in ('top_level', 'both'):
                changed['review_notes'] = ['Injected replacement.']
            if mutation in ('snapshot', 'both'):
                changed['input_snapshot']['prior_feedback']['review_notes'] = ['Injected replacement.']
                changed['input_digest'] = digest(changed['input_snapshot'])
            self.runtime.store.replace_json(f'jobs/{uid(501)}/job.json', changed)
            with self.subTest(mutation=mutation):
                self.assert_code('wiki_projection_integrity',
                                 lambda: self.runtime.model_request(uid(501), 'generator'))
                self.assertEqual(self.runtime.catalog(), catalog)
        self.runtime.store.replace_json(f'jobs/{uid(501)}/job.json', original)
        self.assertEqual(self.runtime.show(uid(501)), original)

    def test_review_notes_require_nonempty_strings_and_same_source_feedback(self):
        self.compile()
        for notes in ([], [''], [' '], ['bad\x00note'], [None], {'note': 'Wrong shape'}, 'not a list'):
            with self.subTest(notes=notes):
                self.assert_code('invalid_wiki_review_notes', lambda: self.prepare(
                    uid(501), feedback_request_id=uid(500), review_notes=notes))
        self.assert_code('invalid_wiki_review_notes', lambda: self.prepare(uid(501), review_notes=['Check timing.']))
        self.assert_code('invalid_wiki_feedback', lambda: self.prepare(uid(501), feedback_request_id=uid(500)))
        self.assert_code('invalid_wiki_feedback', lambda: self.prepare(
            uid(501), source=1, feedback_request_id=uid(500), review_notes=['Check timing.']))
        self.prepare(uid(502))
        invalid = synthetic_proposal(self.sources[0])
        invalid['items'] = []
        response = exchange(self.runtime, uid(502), 'generator', invalid)
        with self.assertRaises(PalimpsestError):
            self.runtime.stage(uid(502), response)
        self.assertEqual(self.runtime.show(uid(502))['state'], 'failed')
        retry = self.prepare(uid(503), feedback_request_id=uid(502))
        self.assertEqual(retry['input_snapshot']['prior_feedback']['state'], 'failed')
        self.assertNotIn('review_notes', retry)

    def test_citation_repair_preserves_six_items_and_requires_a_new_full_validator(self):
        self.prepare()
        response = synthetic_proposal(self.sources[0])
        response['items'] = [{**deepcopy(response['items'][index % 2]),
                              'item_key': f'fixed-{index}', 'text': f'합성 검사 고정 본문 {index}.'}
                             for index in range(6)]
        parent, _ = self.stage(response=response)
        base = deepcopy(parent['proposal'])
        parent_job = deepcopy(self.runtime.show(uid(500)))
        parent_validator = exchange(self.runtime, uid(500), 'validator', decisions(base))
        notes = ['Add the missing source predicate without rewriting existing items.']
        prepared = self.prepare(uid(501), feedback_request_id=uid(500),
                                review_notes=notes, citation_repair=True)
        self.assertTrue(prepared['citation_repair'])
        self.assertTrue(prepared['input_snapshot']['citation_repair'])
        self.assertEqual(prepared['input_snapshot']['prior_feedback']['proposal'], base)
        repair = {'additions': [{'item_key': 'fixed-0', 'evidence': [{
            'information_id': self.sources[0]['target_information_ids'][1],
            'source_block_id': '/page1/result', 'source_role': 'results'}]}],
            'reviews': deepcopy(base['reviews']), 'complete': True, 'issues': []}
        repaired = self.runtime.stage(uid(501), exchange(self.runtime, uid(501), 'generator', repair))
        actual = repaired['proposal']
        self.assertEqual(len(actual['items']), 6)
        self.assertEqual(actual['topics'], base['topics'])
        for index, (item, old) in enumerate(zip(actual['items'], base['items'], strict=True)):
            self.assertEqual({k: v for k, v in item.items() if k != 'evidence'},
                             {k: v for k, v in old.items() if k != 'evidence'})
            self.assertEqual(item['evidence'][:len(old['evidence'])], old['evidence'])
            self.assertEqual(len(item['evidence']), len(old['evidence']) + (index == 0))
        self.assertEqual(self.runtime.store.read_json(f'jobs/{uid(500)}/proposal.json'), base)
        self.assertEqual(self.runtime.show(uid(500)), parent_job)
        self.assertEqual(self.runtime.catalog()['papers'], {})
        self.assert_code('wiki_delivery_mismatch', lambda: self.runtime.decide(uid(501), parent_validator))
        validator = exchange(self.runtime, uid(501), 'validator', decisions(actual))
        result = self.runtime.decide(uid(501), validator)
        self.assertEqual(result['state'], 'compiled')
        paper = self.runtime._snapshot(self.runtime.catalog()['papers'][self.sources[0]['data_id']])
        self.assertEqual(paper['items'], actual['items'])
        self.assertEqual(self.runtime.show(uid(500))['state'], 'proposed')

    def test_citation_repair_refuses_unreviewed_drafts_or_changed_base_input(self):
        original = self.prepare()
        self.assertNotIn('citation_repair', original)
        self.assertNotIn('citation_repair', original['input_snapshot'])
        replay = self.prepare(citation_repair=False)
        self.assertTrue(replay['replayed'])
        self.assertEqual(original['request_sha256'], replay['request_sha256'])
        self.stage()
        self.assert_code('invalid_wiki_citation_repair', lambda: self.prepare(uid(501), citation_repair=True))
        self.assert_code('invalid_wiki_feedback', lambda: self.prepare(
            uid(501), feedback_request_id=uid(500), citation_repair=True))
        self.assert_code('invalid_wiki_feedback', lambda: self.prepare(
            uid(501), source=1, feedback_request_id=uid(500), citation_repair=True, review_notes=['Review.']))
        execution = self.sources[0]['source_execution_id']
        different = deepcopy(self.sources[0])
        different['page_count'] += 1
        different['input_sha256'] = digest({k: v for k, v in different.items() if k != 'input_sha256'})
        self.runtime.packets[execution] = different  # Mock a changed preparation; canonical DB stays untouched.
        self.assert_code('invalid_wiki_citation_repair', lambda: self.prepare(
            uid(501), feedback_request_id=uid(500), citation_repair=True, review_notes=['Review.']))
        self.runtime.packets[execution] = deepcopy(self.sources[0])
        changed = self.runtime.store.read_json(f'jobs/{uid(500)}/proposal.json')
        changed['items'][0]['text'] = 'Base was externally changed.'
        self.runtime.store.replace_json(f'jobs/{uid(500)}/proposal.json', changed)
        self.assert_code('wiki_context_changed', lambda: self.prepare(
            uid(501), feedback_request_id=uid(500), citation_repair=True, review_notes=['Review.']))
        self.assertFalse((self.runtime.store.root / f'jobs/{uid(501)}/job.json').exists())

    def test_citation_repair_flag_is_bound_and_full_rewrites_cannot_use_the_patch_path(self):
        self.prepare()
        self.stage()
        notes = ['Only add exact missing citations.']
        original = self.prepare(uid(501), feedback_request_id=uid(500),
                                review_notes=notes, citation_repair=True)
        expected = {'source_execution_id': self.sources[0]['source_execution_id'], 'metadata': original['metadata'],
                    'feedback_request_id': uid(500), 'review_notes': notes, 'citation_repair': True}
        self.assertEqual(original['request_sha256'], digest(expected))
        self.assert_code('idempotency_conflict', lambda: self.prepare(
            uid(501), feedback_request_id=uid(500), review_notes=notes, citation_repair=False))
        for location in ('job', 'snapshot', 'both'):
            changed = deepcopy(original)
            changed.pop('replayed')
            if location in ('job', 'both'):
                changed['citation_repair'] = False
            if location in ('snapshot', 'both'):
                changed['input_snapshot']['citation_repair'] = False
                changed['input_digest'] = digest(changed['input_snapshot'])
            self.runtime.store.replace_json(f'jobs/{uid(501)}/job.json', changed)
            self.assert_code('wiki_projection_integrity', lambda: self.runtime.model_request(uid(501), 'generator'))
        original.pop('replayed')
        self.runtime.store.replace_json(f'jobs/{uid(501)}/job.json', original)
        rewrite = exchange(self.runtime, uid(501), 'generator', synthetic_proposal(self.sources[0]))
        self.assert_code('invalid_paper_wiki_citation_repair', lambda: self.runtime.stage(uid(501), rewrite))
        self.assertEqual(self.runtime.show(uid(501))['state'], 'failed')
        self.assertEqual(self.runtime.catalog()['papers'], {})

    def test_scoped_text_repair_changes_only_one_item_and_requires_fresh_validation(self):
        self.prepare()
        parent, _ = self.stage()
        base = deepcopy(parent['proposal'])
        parent_validator = exchange(self.runtime, uid(500), 'validator', decisions(base))
        prepared = self.prepare(uid(501), feedback_request_id=uid(500), review_notes=['Review only item-0 wording.'],
                                citation_repair=True, editable_item_keys=['item-0'])
        self.assertEqual(prepared['editable_item_keys'], ['item-0'])
        self.assertEqual(prepared['input_snapshot']['editable_item_keys'], ['item-0'])
        correction = '합성 검사에서 명시적으로 허용한 항목의 문구만 교정했습니다.'
        response = {'additions': [], 'text_changes': [{'item_key': 'item-0', 'text': correction}],
                    'reviews': deepcopy(base['reviews']), 'complete': True, 'issues': []}
        repaired = self.runtime.stage(uid(501), exchange(self.runtime, uid(501), 'generator', response))
        actual = repaired['proposal']
        self.assertEqual(actual['items'][0], {**base['items'][0], 'text': correction})
        self.assertEqual(actual['items'][1:], base['items'][1:])
        self.assertEqual(actual['topics'], base['topics'])
        self.assertEqual([item['evidence'] for item in actual['items']], [item['evidence'] for item in base['items']])
        self.assertEqual(self.runtime.store.read_json(f'jobs/{uid(500)}/proposal.json'), base)
        self.assertEqual(self.runtime.catalog()['papers'], {})
        self.assert_code('wiki_delivery_mismatch', lambda: self.runtime.decide(uid(501), parent_validator))
        validator = exchange(self.runtime, uid(501), 'validator', decisions(actual))
        self.assertEqual(self.runtime.decide(uid(501), validator)['state'], 'compiled')
        paper = self.runtime._snapshot(self.runtime.catalog()['papers'][self.sources[0]['data_id']])
        self.assertEqual(paper['items'], actual['items'])
        self.assertEqual(self.runtime.show(uid(500))['state'], 'proposed')

    def test_editable_keys_require_repair_and_bind_scope_without_changing_legacy_requests(self):
        self.prepare()
        parent, _ = self.stage()
        options = {'feedback_request_id': uid(500), 'review_notes': ['Review fixed item wording.'],
                   'citation_repair': True}
        self.assert_code('invalid_wiki_editable_items', lambda: self.prepare(uid(501), editable_item_keys=['item-0']))
        for keys in (['missing'], ['item-0', 'item-0'], 'item-0', [''], [None]):
            with self.subTest(keys=keys):
                self.assert_code('invalid_wiki_editable_items', lambda: self.prepare(
                    uid(501), **options, editable_item_keys=keys))
        legacy = self.prepare(uid(502), **options)
        request_info = self.runtime.model_request(uid(502), 'generator')
        request_before = Path(request_info['request_file']).read_bytes()
        for keys in (None, []):
            replay = self.prepare(uid(502), **options, editable_item_keys=keys)
            self.assertTrue(replay['replayed'])
            self.assertEqual(replay['request_sha256'], legacy['request_sha256'])
            self.assertNotIn('editable_item_keys', replay)
            self.assertNotIn('editable_item_keys', replay['input_snapshot'])
            info = self.runtime.model_request(uid(502), 'generator')
            self.assertEqual(Path(info['request_file']).read_bytes(), request_before)
        self.assertNotIn('text_changes', json.loads(request_before)['schema']['properties'])
        original = self.prepare(uid(501), **options, editable_item_keys=['item-0'])
        self.assert_code('idempotency_conflict', lambda: self.prepare(uid(501), **options, editable_item_keys=['item-1']))
        for location in ('job', 'snapshot', 'both'):
            changed = deepcopy(original)
            changed.pop('replayed')
            if location in ('job', 'both'):
                changed['editable_item_keys'] = ['item-1']
            if location in ('snapshot', 'both'):
                changed['input_snapshot']['editable_item_keys'] = ['item-1']
                changed['input_digest'] = digest(changed['input_snapshot'])
            self.runtime.store.replace_json(f'jobs/{uid(501)}/job.json', changed)
            self.assert_code('wiki_projection_integrity', lambda: self.runtime.model_request(uid(501), 'generator'))
        original.pop('replayed')
        self.runtime.store.replace_json(f'jobs/{uid(501)}/job.json', original)
        outside_scope = {'additions': [], 'text_changes': [{'item_key': 'item-1', 'text': 'Unpermitted rewrite.'}],
                         'reviews': deepcopy(parent['proposal']['reviews']), 'complete': True, 'issues': []}
        response = exchange(self.runtime, uid(501), 'generator', outside_scope)
        self.assert_code('paper_wiki_repair_item_mismatch', lambda: self.runtime.stage(uid(501), response))
        self.assertEqual(self.runtime.show(uid(501))['state'], 'failed')
        self.assertEqual(self.runtime.catalog()['papers'], {})


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires Linux and an explicitly provisioned disposable PostgreSQL DSN')
class PaperWikiPostgresTests(unittest.TestCase):
    def setUp(self):
        self.dsn = os.environ['PALIMPSEST_TEST_DSN']
        temporary = TemporaryDirectory(prefix='palimpsest-wiki-pg-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        root = self.base / 'artifacts'
        self.repository = PostgresRepository(self.dsn)
        raw = (f'# Synthetic source {uuid4()}\n\n## Methods\n'
               'Synthetic treatment A used mouse BMDCs.\n\n## Results\n'
               'Only treatment A had the recorded readout of 3 μm.\n').encode()
        path = self.base / 'fixture.md'
        path.write_bytes(raw)
        service = DataService(self.repository, ArtifactStore(root), actor_ref='synthetic-test')
        self.owner = service.import_file(path, media_type='text/markdown')['data_id']
        compiler = CompilerRuntime(self.dsn, root)
        self.execution = compiler.compile_markdown(self.owner)['execution_id']
        self.packet = compiler.prepare_input(self.execution)
        self.runtime = PaperWikiRuntime(self.dsn, root, self.base / 'wiki')
        self.identifier = self.repository.allocate_id()
        self.runtime.prepare(self.execution, self.identifier,
                             {'title': 'Synthetic Markdown paper', 'filename': 'fixture.md'})

    def canonical_state(self):
        with psycopg.connect(self.dsn) as conn:
            return conn.execute('''SELECT
                (SELECT count(*) FROM canonical_store.information WHERE data_id=%s),
                (SELECT count(*) FROM canonical_store.information_groundings WHERE data_id=%s),
                (SELECT count(*) FROM compiler_runtime.operation_executions WHERE data_id=%s),
                (SELECT count(*) FROM canonical_store.knowledge_nodes),
                (SELECT count(*) FROM canonical_store.knowledge_edges)''', (self.owner,) * 3).fetchone()

    def test_real_registered_markdown_commits_wiki_with_exact_i_and_no_canonical_effects(self):
        before = self.canonical_state()
        generator = exchange(self.runtime, self.identifier, 'generator', synthetic_proposal(self.packet))
        context = self.runtime.stage(self.identifier, generator)
        validator = exchange(self.runtime, self.identifier, 'validator', decisions(context['proposal']))
        result = self.runtime.decide(self.identifier, validator)
        self.assertEqual(result['state'], 'compiled')
        self.assertEqual(self.canonical_state(), before)
        paper = self.runtime._snapshot(self.runtime.catalog()['papers'][self.owner])
        units = {unit['information_id']: unit for unit in self.packet['model_input']['information']}
        for item in paper['items']:
            for citation in item['evidence']:
                self.assertEqual(citation['data_id'], self.owner)
                self.assertEqual(citation['quote'], units[citation['information_id']]['content'][
                    citation['char_start']:citation['char_end']])
                self.assertEqual(citation['page_numbers'], [])

    def test_actual_canonical_check_rejects_rehashed_forged_i_without_db_mutation(self):
        before = self.canonical_state()
        forged = deepcopy(self.packet)
        forged['model_input']['information'][0]['content'] += ' Fabricated source text.'
        forged['model_input']['information'][0]['content_fingerprint'] = sha256(
            forged['model_input']['information'][0]['content'].encode()).hexdigest()
        forged['input_sha256'] = digest({key: value for key, value in forged.items() if key != 'input_sha256'})
        # Structural hashes can be recomputed; the actual canonical DB must still disagree.
        combine_packets([forged])
        with self.assertRaises(PalimpsestError) as caught:
            self.runtime._verify_source(forged)
        self.assertEqual(caught.exception.code, 'knowledge_input_changed')
        self.assertEqual(self.canonical_state(), before)
        self.assertEqual(self.runtime.catalog()['papers'], {})


if __name__ == '__main__':
    unittest.main()
