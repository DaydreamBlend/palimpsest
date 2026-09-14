"""Synthetic archive contracts; no PostgreSQL, parser, or model calls."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.knowledge_runtime import MODEL
from palimpsest import paper_wiki as pages
from palimpsest.wiki_archive import PROFILE, build_archive, validate_archive_files
from palimpsest.wiki_projection_store import ProjectionStore
from test_multi_source_i2k import uid
from test_paper_wiki import source_packet, proposal, decisions


def encoded(value):
    # Deliberately retain whitespace unlike normalized JSON/JSONB serialization.
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def archive_fixture():
    packet, response, identifier = source_packet(), proposal(), uid(500)
    normalized = pages.normalize_proposal(response, packet, [])
    metadata = {'title': 'Synthetic archived paper', 'filename': 'synthetic.pdf'}
    empty = {'schema_version': PROFILE, 'version': 0, 'papers': {}, 'topics': {}, 'commits': {}}
    snapshot = {'input': packet, 'metadata': metadata, 'existing_topics': [], 'prior_feedback': None}
    context = {'input_snapshot': snapshot, 'proposal': normalized}
    request = {'source_execution_id': packet['source_execution_id'], 'metadata': metadata, 'feedback_request_id': None}
    assets = [{'relative_path': 'media/' + a['sha256'] + '.png',
               'sha256': a['sha256'], 'byte_size': a['byte_size']} for a in packet['media_assets']]
    job = {'request_id': identifier, 'schema_version': PROFILE, **request,
           'request_sha256': digest(request), 'source_data_id': packet['data_id'],
           'source_execution_id': packet['source_execution_id'], 'input_snapshot': snapshot,
           'input_digest': digest(snapshot), 'validation_context_sha256': digest(context),
           'assets': assets, 'profile': {'schema_version': PROFILE, 'model': deepcopy(MODEL),
                                       'implementation': {'historical-source.py': 'a' * 64}},
           'state': 'compiled', 'expected_catalog_sha256': digest(empty)}
    objects = {f'catalogs/{digest(empty)}.json': empty, f'jobs/{identifier}/proposal.json': normalized,
               f'jobs/{identifier}/validation-context.json': context}
    for phase, body, checksum in (('generator', response, digest(snapshot)),
                                 ('validator', decisions(normalized), digest(context))):
        request = {'prompt': 'Historical synthetic prompt. No real model was called.',
                   'schema': {'synthetic_test_only': True}, 'input_sha256': checksum,
                   'images': [{'path': '../../' + a['relative_path'], 'sha256': a['sha256']} for a in assets],
                   'output_file': phase + '-response.json',
                   'delivered_information_ids': packet['target_information_ids']}
        exchange = {'response': body, 'receipt': {'synthetic_test_only': True,
            'profile': deepcopy(MODEL), 'provider_ref': 'synthetic-no-call:' + phase,
            'actual_delivery': True, 'original_pdf_delivered': False,
            'input_sha256': checksum, 'output_sha256': digest(body),
            'prompt_sha256': sha256(request['prompt'].encode()).hexdigest(),
            'schema_sha256': digest(request['schema']),
            'delivered_information_ids': packet['target_information_ids'],
            'image_attachments': [{k: a[k] for k in ('sha256', 'byte_size')} for a in assets]}}
        objects[f'jobs/{identifier}/{phase}-request.json'] = request
        objects[f'jobs/{identifier}/{phase}-exchange.json'] = exchange
        objects[f'jobs/{identifier}/{phase}-response.json'] = deepcopy(exchange)
    objects[f'jobs/{identifier}/decision.json'] = pages.validate_decisions(decisions(normalized), normalized)

    def save(body, snapshot_id):
        value = {**body, 'snapshot_id': snapshot_id, 'body_sha256': digest(body),
                 'origin_request_id': identifier, 'projection_schema': PROFILE,
                 'previous_snapshot_id': None, 'previous_snapshot_sha256': None}
        objects[f'snapshots/{snapshot_id}.json'] = value
        return {'snapshot_id': snapshot_id, 'page_id': body['page_id'], 'title': body['title'],
                'body_sha256': digest(body), 'snapshot_sha256': digest(value)}

    paper = {'page_id': uid(100), 'kind': 'paper', 'title': metadata['title'], 'metadata': metadata,
             'items': normalized['items'], 'topics': normalized['topics'], 'data_id': packet['data_id'],
             'source_execution_id': packet['source_execution_id'], 'input_sha256': packet['input_sha256']}
    paper_entry = save(paper, uid(101))
    definition = normalized['topics'][0]
    topic = {'page_id': uid(200), 'kind': 'topic', **definition, 'active': True,
             'contributions': [{'paper_page_id': paper['page_id'], 'paper_data_id': packet['data_id'],
                                'paper_title': paper['title'], 'items': [normalized['items'][0]]}]}
    topic_entry = {**save(topic, uid(201)), **definition, 'active': True}
    job['result'] = {'request_id': identifier, 'state': 'compiled', 'paper_page_id': uid(100),
        'paper_snapshot_id': uid(101), 'paper_count': 1, 'topic_count': 1, 'catalog_version': 1,
        'canonical_writes': 0, 'new_d2i_calls': 0}
    catalog = {'schema_version': PROFILE, 'version': 1, 'papers': {packet['data_id']: paper_entry},
               'topics': {definition['topic_key']: topic_entry}, 'commits': {identifier: job['result']}}
    objects[f'jobs/{identifier}/job.json'] = job
    objects['catalog.json'] = catalog
    objects[f'catalogs/{digest(catalog)}.json'] = deepcopy(catalog)
    return {path: encoded(value) for path, value in objects.items()}


class WikiArchiveTests(unittest.TestCase):
    def setUp(self):
        self.files = archive_fixture()

    def alter(self, path, edit):
        value = json.loads(self.files[path])
        edit(value)
        self.files[path] = encoded(value)

    def rehash_current(self, snapshot_id):
        """Rehash an attacker-modified body to test relational, not hash-only, checks."""
        path = f'snapshots/{snapshot_id}.json'
        value = json.loads(self.files[path])
        metadata = {'snapshot_id', 'body_sha256', 'previous_snapshot_id', 'previous_snapshot_sha256',
                    'origin_request_id', 'projection_schema'}
        value['body_sha256'] = digest({k: v for k, v in value.items() if k not in metadata})
        self.files[path] = encoded(value)
        current = json.loads(self.files['catalog.json'])
        del self.files[f'catalogs/{digest(current)}.json']
        for entry in list(current['papers'].values()) + list(current['topics'].values()):
            if entry['snapshot_id'] == snapshot_id:
                entry.update(snapshot_sha256=digest(value), body_sha256=value['body_sha256'])
        self.files['catalog.json'] = encoded(current)
        self.files[f'catalogs/{digest(current)}.json'] = encoded(current)

    def rejects(self):
        with self.assertRaises(PalimpsestError):
            validate_archive_files(self.files)

    def test_exact_bytes_manifest_history_and_source_are_preserved(self):
        original = deepcopy(self.files)
        result = validate_archive_files(self.files)
        self.assertEqual(self.files, original)
        self.assertEqual(result['files'], original)
        self.assertEqual(len(result['catalogs']), 2)
        self.assertEqual(len(result['snapshots']), 2)
        self.assertEqual(len(result['jobs']), 1)
        self.assertEqual(result['source_packets'][source_packet()['source_execution_id']], source_packet())
        self.assertEqual(result['manifest_sha256'], digest(result['manifest']))
        for entry in result['manifest']['files']:
            raw = original[entry['path']]
            self.assertEqual((entry['sha256'], entry['byte_size']), (sha256(raw).hexdigest(), len(raw)))

    def test_historical_request_is_verified_without_current_prompt_regeneration(self):
        with patch('palimpsest.paper_wiki_prompts.generation', side_effect=AssertionError('Must not regenerate')):
            validate_archive_files(self.files)

    def test_orphan_snapshot_bytes_are_archived_without_relational_promotion(self):
        path = f'snapshots/{uid(999)}.json'
        self.files[path] = b'{ "uncommitted": true }\n'
        result = validate_archive_files(self.files)
        self.assertEqual(result['files'][path], self.files[path])
        self.assertNotIn(uid(999), result['snapshots'])

    def test_unknown_unsafe_paths_and_duplicate_json_keys_are_rejected(self):
        for path in ('../catalog.json', 'jobs/not-a-uuid/job.json', 'media/fake.png', 'jobs/' + uid(500) + '/unknown.json'):
            with self.subTest(path=path):
                files = dict(self.files, **{path: b'{}'})
                with self.assertRaises(PalimpsestError):
                    validate_archive_files(files)
        self.files['catalog.json'] = b'{"version":0,"version":1}'
        self.rejects()

    def test_body_rehashed_without_approved_proposal_is_rejected(self):
        self.alter(f'snapshots/{uid(101)}.json', lambda x: x['items'][0].update(text='Invented source claim.'))
        self.rehash_current(uid(101))
        self.rejects()

    def test_normalized_proposal_cannot_drift_from_generator_exchange(self):
        base = f'jobs/{uid(500)}/'
        self.alter(base + 'proposal.json', lambda x: x['items'][0].update(text='Tampered'))
        proposal_value = json.loads(self.files[base + 'proposal.json'])
        self.alter(base + 'validation-context.json', lambda x: x.update(proposal=proposal_value))
        context_sha = digest(json.loads(self.files[base + 'validation-context.json']))
        self.alter(base + 'job.json', lambda x: x.update(validation_context_sha256=context_sha))
        self.rejects()

    def test_topic_cannot_add_unvalidated_cross_paper_synthesis(self):
        self.alter(f'snapshots/{uid(201)}.json', lambda x: x['contributions'][0]['items'][0].update(text='Novel synthesis'))
        self.rehash_current(uid(201))
        self.rejects()

    def test_parent_must_be_same_page_and_hash_chain_cannot_cycle(self):
        topic = json.loads(self.files[f'snapshots/{uid(201)}.json'])
        self.alter(f'snapshots/{uid(101)}.json', lambda x: x.update(
            previous_snapshot_id=uid(201), previous_snapshot_sha256=digest(topic)))
        self.rehash_current(uid(101))
        self.rejects()
        self.files = archive_fixture()
        self.alter(f'snapshots/{uid(101)}.json', lambda x: x.update(
            previous_snapshot_id=uid(101), previous_snapshot_sha256='0' * 64))
        self.rehash_current(uid(101))
        self.rejects()

    def test_missing_history_commit_and_unaccepted_origin_are_rejected(self):
        base = f'jobs/{uid(500)}/'
        self.alter(base + 'job.json', lambda x: x.update(state='needs_review'))
        self.rejects()
        self.files = archive_fixture()
        oldest = next(path for path in self.files if path.startswith('catalogs/')
                      and json.loads(self.files[path])['version'] == 0)
        del self.files[oldest]
        self.rejects()

    def test_receipt_hash_model_delivery_and_exact_image_list_are_verified(self):
        for field, changed in (('output_sha256', '0' * 64), ('actual_delivery', False),
                               ('image_attachments', []), ('profile', {'model': 'unapproved'})):
            with self.subTest(field=field):
                self.files = archive_fixture()
                self.alter(f'jobs/{uid(500)}/validator-exchange.json', lambda x: x['receipt'].update({field: changed}))
                self.rejects()

    def test_validator_rejection_is_not_imported_as_accepted(self):
        base = f'jobs/{uid(500)}/'
        value = json.loads(self.files[base + 'validator-exchange.json'])
        value['response']['items'][0]['verdict'] = 'rejected'
        value['receipt']['output_sha256'] = digest(value['response'])
        self.files[base + 'validator-exchange.json'] = encoded(value)
        self.files[base + 'validator-response.json'] = encoded(value)
        self.files[base + 'decision.json'] = encoded(pages.validate_decisions(
            value['response'], json.loads(self.files[base + 'proposal.json'])))
        self.rejects()

    @unittest.skipUnless(sys.platform == 'linux', 'No-follow projection filesystem requires Linux')
    def test_store_archive_excludes_media_exports_and_worker_files_and_rejects_symlinks(self):
        with TemporaryDirectory(prefix='palimpsest-archive-') as temporary:
            store = ProjectionStore(Path(temporary) / 'wiki')
            for path, raw in self.files.items():
                store.write_bytes(path, raw)
            for path in ('media/not-archived.png', 'exports/cache.json',
                         f'jobs/{uid(500)}/worker-temporary/output.json'):
                store.write_bytes(path, b'{}')
            result = build_archive(store)
            self.assertEqual(result['files'], self.files)
            path = store.root / 'catalogs' / ('f' * 64 + '.json')
            path.symlink_to(store.root / 'catalog.json')
            with self.assertRaises(PalimpsestError):
                build_archive(store)


if __name__ == '__main__':
    unittest.main()
