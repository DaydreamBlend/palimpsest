"""Durable paper/topic read projections over immutable canonical Information.

This is not a Parchment or Knowledge write path. Model calls run separately from
the short projection lock; current catalog is the single atomic commit point.
"""
from copy import deepcopy
from hashlib import sha256
from importlib.resources import files
import json
from pathlib import Path

from .canonical_store import PostgresRepository, connection
from .compiler_runtime import CompilerRuntime
from .data import data_id, request_id
from .errors import PalimpsestError
from .i2k import digest
from .knowledge_runtime import KnowledgeRuntime, MODEL
from .multi_source_i2k import combine_packets
from . import paper_wiki as pages
from . import paper_wiki_prompts as prompts
from .wiki_projection_store import ProjectionStore


PROFILE = 'paper-topic-wiki-projection-v1'


def _fail(code, status=4):
    raise PalimpsestError(code, 'Wiki 입력·모델 판정·현재 문서 상태를 확인하세요.', status)


def _profile():
    names = ('paper_wiki.py', 'paper_wiki_prompts.py', 'knowledge.py',
             'multi_source_i2k.py', 'i2k_selection.py')
    return {'schema_version': PROFILE, 'model': dict(MODEL), 'implementation': {
        name: sha256(files('palimpsest').joinpath(name).read_text(encoding='utf-8').encode()).hexdigest()
        for name in names}}


def _image_suffix(raw):
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
        return '.png'
    if raw.startswith(b'\xff\xd8\xff'):
        return '.jpg'
    if raw.startswith(b'RIFF') and raw[8:12] == b'WEBP':
        return '.webp'
    _fail('unsupported_wiki_image')


class PaperWikiRuntime:
    def __init__(self, dsn, artifact_root, directory):
        self.dsn = dsn
        self.source = CompilerRuntime(dsn, artifact_root)
        self.repository = PostgresRepository(dsn)
        self.store = ProjectionStore(Path(directory))

    def _id(self):
        return self.repository.allocate_id()

    def _source(self, execution_id):
        packet = self.source.prepare_input(execution_id)
        combine_packets([packet])  # Full I/owned media/hash coverage, no compilation.
        return packet

    def _verify_source(self, packet):
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SET TRANSACTION READ ONLY')
            KnowledgeRuntime._verify_i(conn, packet['data_id'], packet)

    def _catalog(self):
        return self.store.read_json('catalog.json', default={
            'schema_version': PROFILE, 'version': 0, 'papers': {}, 'topics': {}, 'commits': {}})

    def _job(self, identifier):
        identifier = request_id(identifier)
        job = self.store.read_json(f'jobs/{identifier}/job.json')
        if job is None:
            _fail('wiki_job_not_found', 2)
        if (job['request_id'] != identifier or job['schema_version'] != PROFILE
                or job['input_digest'] != digest(job['input_snapshot'])):
            _fail('wiki_projection_integrity', 6)
        snapshot = job['input_snapshot']
        packet = snapshot['input']
        request = {'source_execution_id': packet['source_execution_id'],
                   'metadata': snapshot['metadata'], 'feedback_request_id': job.get('feedback_request_id')}
        notes = (snapshot.get('prior_feedback') or {}).get('review_notes')
        if notes is not None:
            request['review_notes'] = notes
        if snapshot.get('citation_repair'):
            request['citation_repair'] = True
        if snapshot.get('editable_item_keys'):
            request['editable_item_keys'] = snapshot['editable_item_keys']
        if (job['source_data_id'] != packet['data_id']
                or job['source_execution_id'] != packet['source_execution_id']
                or job['metadata'] != snapshot['metadata']
                or job.get('review_notes') != notes
                or type(job.get('citation_repair', False)) is not bool
                or type(snapshot.get('citation_repair', False)) is not bool
                or job.get('citation_repair', False) != snapshot.get('citation_repair', False)
                or job.get('editable_item_keys') != snapshot.get('editable_item_keys')
                or job['request_sha256'] != digest(request)
                or [{k: a[k] for k in ('sha256', 'byte_size')} for a in job['assets']]
                   != [{k: a[k] for k in ('sha256', 'byte_size')} for a in packet['media_assets']]):
            _fail('wiki_projection_integrity', 6)
        for asset in job['assets']:
            if asset['relative_path'] not in {'media/' + asset['sha256'] + suffix
                                              for suffix in ('.png', '.jpg', '.webp')}:
                _fail('wiki_projection_integrity', 6)
        return job

    def _context(self, job):
        context = self.store.read_json(f"jobs/{job['request_id']}/validation-context.json")
        if (context is None or digest(context) != job.get('validation_context_sha256')
                or context['input_snapshot'] != job['input_snapshot']
                or context['proposal'] != self.store.read_json(f"jobs/{job['request_id']}/proposal.json")):
            _fail('wiki_context_changed', 6)
        return context

    def _save_job(self, job):
        self.store.replace_json(f"jobs/{job['request_id']}/job.json", job)

    def _check_profile(self, job):
        if job['profile'] != _profile():
            _fail('wiki_implementation_changed', 6)

    def prepare(self, execution_id, identifier, metadata, *, feedback_request_id=None, review_notes=None,
                citation_repair=False, editable_item_keys=None):
        execution_id, identifier = request_id(execution_id), request_id(identifier)
        if (not isinstance(metadata, dict) or not set(metadata) <= {'title', 'filename', 'doi'}
                or not all(isinstance(v, str) and v.strip() and '\x00' not in v for v in metadata.values())
                or not {'title', 'filename'} <= set(metadata)):
            _fail('invalid_wiki_metadata', 2)
        request = {'source_execution_id': execution_id, 'metadata': metadata,
                   'feedback_request_id': request_id(feedback_request_id) if feedback_request_id else None}
        if review_notes is not None:
            if (not feedback_request_id or not isinstance(review_notes, list) or not review_notes
                    or any(not isinstance(note, str) or not note.strip() or '\x00' in note for note in review_notes)):
                _fail('invalid_wiki_review_notes', 2)
            request['review_notes'] = deepcopy(review_notes)
        if type(citation_repair) is not bool or (citation_repair and not feedback_request_id):
            _fail('invalid_wiki_citation_repair', 2)
        if citation_repair:
            request['citation_repair'] = True
        if editable_item_keys is not None and (not isinstance(editable_item_keys, list)
                or any(not isinstance(key, str) or not key.strip() for key in editable_item_keys)
                or len(set(editable_item_keys)) != len(editable_item_keys)):
            _fail('invalid_wiki_editable_items', 2)
        if editable_item_keys:
            if not citation_repair:
                _fail('invalid_wiki_editable_items', 2)
            request['editable_item_keys'] = deepcopy(editable_item_keys)
        request_sha = digest(request)
        # Replaying an existing request does not recompute its frozen context.
        with self.store.locked():
            previous = self.store.read_json(f'jobs/{identifier}/job.json')
            if previous is not None:
                if previous['request_sha256'] != request_sha:
                    _fail('idempotency_conflict', 6)
                return {**self._job(identifier), 'replayed': True}
        packet = self._source(execution_id)
        data = self.repository.get_data(packet['data_id'])
        if data is None:
            _fail('wiki_data_not_found', 2)
        assets = []
        for asset in packet['media_assets']:
            raw = self.source.derived.read(asset['sha256'], asset['byte_size'])
            path = 'media/' + asset['sha256'] + _image_suffix(raw)
            self.store.write_bytes(path, raw)
            assets.append({'sha256': asset['sha256'], 'byte_size': len(raw), 'relative_path': path})
        with self.store.locked():
            previous = self.store.read_json(f'jobs/{identifier}/job.json')
            if previous is not None:
                if previous['request_sha256'] != request_sha:
                    _fail('idempotency_conflict', 6)
                return {**self._job(identifier), 'replayed': True}
            catalog = self._catalog()
            feedback = None
            if feedback_request_id:
                prior = self._job(feedback_request_id)
                allowed = ('needs_review', 'failed', 'compiled') if review_notes else ('needs_review', 'failed')
                if citation_repair and review_notes:
                    allowed = (*allowed, 'proposed')
                if prior['source_execution_id'] != execution_id or prior['state'] not in allowed:
                    _fail('invalid_wiki_feedback', 6)
                feedback = {'request_id': feedback_request_id, 'state': prior['state'],
                            'result': self.store.read_json(f'jobs/{feedback_request_id}/decision.json'),
                            'proposal': self.store.read_json(f'jobs/{feedback_request_id}/proposal.json'),
                            'failure': prior.get('failure')}
                if review_notes is not None:
                    feedback['review_notes'] = deepcopy(review_notes)
                if citation_repair:
                    context = self._context(prior)
                    if (context['input_snapshot']['input'] != packet or feedback['proposal'] is None
                            or feedback['proposal'] != context['proposal']):
                        _fail('invalid_wiki_citation_repair', 6)
                    if editable_item_keys and not set(editable_item_keys) <= {
                            item['item_key'] for item in feedback['proposal']['items']}:
                        _fail('invalid_wiki_editable_items', 2)
            snapshot = {'input': packet, 'metadata': deepcopy(metadata),
                'existing_topics': [{k: t[k] for k in ('topic_key', 'title', 'scope')}
                                    for _, t in sorted(catalog['topics'].items())],
                'prior_feedback': feedback}
            if citation_repair:
                snapshot['citation_repair'] = True
            if editable_item_keys:
                snapshot['editable_item_keys'] = deepcopy(editable_item_keys)
            job = {'schema_version': PROFILE, 'request_id': identifier, **request,
                'request_sha256': request_sha, 'source_data_id': packet['data_id'],
                'source_byte_size': data['byte_size'], 'source_media_type': data['media_type'],
                'state': 'prepared', 'input_snapshot': snapshot, 'input_digest': digest(snapshot),
                'expected_catalog_sha256': digest(catalog), 'profile': _profile(),
                'assets': assets, 'canonical_writes': 0, 'new_d2i_calls': 0}
            self._save_job(job)
            return {**job, 'replayed': False}

    def _model_request(self, job, phase):
        self._check_profile(job)
        snapshot, assets = job['input_snapshot'], job['assets']
        packet = snapshot['input']
        for asset in assets:
            raw = self.store.read_bytes(asset['relative_path'])
            if (len(raw) != asset['byte_size'] or sha256(raw).hexdigest() != asset['sha256']
                    or asset['relative_path'] != 'media/' + asset['sha256'] + _image_suffix(raw)):
                _fail('wiki_media_changed', 6)
        if phase == 'generator':
            if snapshot.get('citation_repair'):
                prompt = prompts.citation_repair(snapshot, assets)
                schema = pages.citation_repair_schema(packet, snapshot['prior_feedback']['proposal'],
                                                      editable_item_keys=snapshot.get('editable_item_keys'))
            else:
                prompt = prompts.generation(snapshot, assets)
                schema = pages.generation_schema(packet, snapshot['existing_topics'])
            input_sha = job['input_digest']
        elif phase == 'validator':
            context = self._context(job)
            prompt = prompts.validation(context, assets)
            schema = pages.validation_schema(context['proposal'])
            input_sha = job['validation_context_sha256']
        else:
            _fail('invalid_wiki_phase', 2)
        return {'prompt': prompt, 'schema': schema,
            'images': [{'path': '../../' + a['relative_path'], 'sha256': a['sha256']} for a in assets],
            'input_sha256': input_sha, 'output_file': phase + '-response.json',
            'delivered_information_ids': packet['target_information_ids']}

    def model_request(self, identifier, phase):
        with self.store.locked():
            job = self._job(identifier)
            allowed = ('prepared', 'failed') if phase == 'generator' else ('proposed',)
            if job['state'] not in allowed:
                _fail('invalid_wiki_state', 6)
            request = self._model_request(job, phase)
            path = f'jobs/{identifier}/{phase}-request.json'
            self.store.write_json(path, request)
            return {'request_id': identifier, 'state': job['state'], 'phase': phase,
                    'request_file': str(self.store.root / path),
                    'information_count': len(request['delivered_information_ids']),
                    'image_count': len(request['images']), 'input_sha256': request['input_sha256'],
                    'prompt_sha256': sha256(request['prompt'].encode()).hexdigest()}

    def _receipt(self, job, phase, exchange):
        if not isinstance(exchange, dict) or set(exchange) != {'response', 'receipt'}:
            _fail('invalid_wiki_exchange')
        receipt = exchange['receipt']
        expected = self._model_request(job, phase)
        if (not isinstance(receipt, dict) or not isinstance(receipt.get('profile'), dict)
                or any(receipt['profile'].get(k) != v for k, v in MODEL.items())
                or receipt.get('actual_delivery') is not True
                or receipt.get('original_pdf_delivered') is not False
                or not receipt.get('provider_ref')
                or receipt.get('input_sha256') != expected['input_sha256']
                or receipt.get('output_sha256') != digest(exchange['response'])
                or receipt.get('prompt_sha256') != sha256(expected['prompt'].encode()).hexdigest()
                or receipt.get('schema_sha256') != digest(expected['schema'])
                or receipt.get('delivered_information_ids') != expected['delivered_information_ids']
                or receipt.get('image_attachments') != [
                    {k: a[k] for k in ('sha256', 'byte_size')} for a in job['assets']]):
            _fail('wiki_delivery_mismatch', 6)
        if phase == 'validator':
            generator = self.store.read_json(f"jobs/{job['request_id']}/generator-exchange.json")
            if receipt['provider_ref'] == generator['receipt']['provider_ref']:
                _fail('wiki_validator_not_independent', 6)

    def stage(self, identifier, exchange):
        with self.store.locked():
            job = self._job(identifier)
            prior = self.store.read_json(f'jobs/{identifier}/generator-exchange.json')
            if prior is not None:
                if prior != exchange:
                    _fail('idempotency_conflict', 6)
                self._receipt(job, 'generator', exchange)
                normalized = self._normalize_generator(job, exchange['response'])
                context = self.store.read_json(f'jobs/{identifier}/validation-context.json')
                if (context is None or context['input_snapshot'] != job['input_snapshot']
                        or context['proposal'] != normalized
                        or self.store.read_json(f'jobs/{identifier}/proposal.json') != normalized
                        or (job.get('validation_context_sha256') is not None
                            and job['validation_context_sha256'] != digest(context))):
                    _fail('wiki_context_changed', 6)
                if job['state'] in ('prepared', 'failed'):
                    job.update(state='proposed', validation_context_sha256=digest(context))
                    self._save_job(job)
                return context
            if job['state'] not in ('prepared', 'failed'):
                _fail('invalid_wiki_state', 6)
            self._receipt(job, 'generator', exchange)
            snapshot = job['input_snapshot']
            self._verify_source(snapshot['input'])
            try:
                proposal = self._normalize_generator(job, exchange['response'])
            except PalimpsestError as error:
                failure = {'phase': 'generator', 'code': error.code, 'exchange': exchange}
                self.store.write_json(f'jobs/{identifier}/failures/{digest(failure)}.json', failure)
                job.update(state='failed', failure={'phase': 'generator', 'code': error.code,
                                                   'response': exchange['response']})
                self._save_job(job)
                raise
            context = {'input_snapshot': snapshot, 'proposal': proposal}
            self.store.write_json(f'jobs/{identifier}/proposal.json', proposal)
            self.store.write_json(f'jobs/{identifier}/validation-context.json', context)
            self.store.write_json(f'jobs/{identifier}/generator-exchange.json', exchange)
            job.update(state='proposed', validation_context_sha256=digest(context))
            self._save_job(job)
            return context

    def _normalize_generator(self, job, response):
        snapshot = job['input_snapshot']
        if snapshot.get('citation_repair'):
            return pages.normalize_citation_repair(response, snapshot['input'],
                snapshot['prior_feedback']['proposal'], editable_item_keys=snapshot.get('editable_item_keys'))
        return pages.normalize_proposal(response, snapshot['input'], snapshot['existing_topics'])

    def decide(self, identifier, exchange, *, checkpoint=None):
        with self.store.locked():
            job = self._job(identifier)
            prior = self.store.read_json(f'jobs/{identifier}/validator-exchange.json')
            if prior is not None and prior != exchange:
                _fail('idempotency_conflict', 6)
            catalog = self._catalog()
            # A crash after catalog publication is recovered from the commit receipt.
            if identifier in catalog['commits']:
                if prior != exchange:
                    _fail('wiki_projection_integrity', 6)
                result = catalog['commits'][identifier]
                job.update(state='compiled', result=result)
                self._save_job(job)
                return {**result, 'replayed': True}
            if job['state'] == 'needs_review' and prior == exchange:
                return {'request_id': identifier, 'state': 'needs_review', 'replayed': True}
            if job['state'] != 'proposed':
                _fail('invalid_wiki_state', 6)
            self._receipt(job, 'validator', exchange)
            self._verify_source(job['input_snapshot']['input'])
            proposal = self._context(job)['proposal']
            try:
                decision = pages.validate_decisions(exchange['response'], proposal)
            except PalimpsestError as error:
                failure = {'phase': 'validator', 'code': error.code, 'exchange': exchange}
                self.store.write_json(f'jobs/{identifier}/failures/{digest(failure)}.json', failure)
                job.update(state='failed', failure={'phase': 'validator', 'code': error.code,
                                                   'response': exchange['response']})
                self._save_job(job)
                raise
            self.store.write_json(f'jobs/{identifier}/validator-exchange.json', exchange)
            self.store.write_json(f'jobs/{identifier}/decision.json', decision)
            accepted = (proposal['complete'] and decision['complete']
                        and all(x['verdict'] == 'accepted' for x in decision['items'] + decision['topics'])
                        and all(r['disposition'] != 'needs_review' for r in proposal['reviews']))
            if not accepted:
                job.update(state='needs_review')
                self._save_job(job)
                return {'request_id': identifier, 'state': 'needs_review', 'decision': decision, 'canonical_writes': 0}
            if digest(catalog) != job['expected_catalog_sha256']:
                _fail('wiki_catalog_changed', 6)
            changed = deepcopy(catalog)
            owner = job['source_data_id']
            previous = changed['papers'].get(owner)
            page_id = previous['page_id'] if previous else self._id()
            old_paper = self._snapshot(previous) if previous else None
            body = {'page_id': page_id, 'kind': 'paper', 'title': job['metadata']['title'],
                    'data_id': owner, 'metadata': job['metadata'], 'items': proposal['items'], 'topics': proposal['topics'],
                    'source_execution_id': job['source_execution_id'], 'input_sha256': job['input_snapshot']['input']['input_sha256']}
            if job['input_snapshot']['input']['model_input'].get('source_format') == 'code':
                body['source_format'] = 'code'
            paper_entry = self._save_snapshot(body, previous, identifier)
            changed['papers'][owner] = paper_entry
            affected = {t['topic_key'] for t in proposal['topics']}
            if old_paper:
                affected.update(t['topic_key'] for t in old_paper['topics'])
            definitions = {t['topic_key']: t for t in proposal['topics']}
            for key in sorted(affected):
                old = changed['topics'].get(key)
                definition = definitions.get(key) or {k: old[k] for k in ('topic_key', 'title', 'scope')}
                if old and any(definition[k] != old[k] for k in ('title', 'scope')):
                    _fail('wiki_topic_identity_changed', 6)
                contributions = []
                for source_id, entry in sorted(changed['papers'].items()):
                    paper = self._snapshot(entry)
                    items = [item for item in paper['items'] if key in item['topic_keys']]
                    if items:
                        contributions.append({'paper_page_id': entry['page_id'], 'paper_data_id': source_id,
                                              'paper_title': paper['title'], 'items': items})
                topic = {'page_id': old['page_id'] if old else self._id(), 'kind': 'topic',
                         **definition, 'contributions': contributions, 'active': bool(contributions)}
                changed['topics'][key] = {**self._save_snapshot(topic, old, identifier),
                                         **definition, 'active': bool(contributions)}
            changed['version'] += 1
            result = {'request_id': identifier, 'state': 'compiled', 'paper_page_id': page_id,
                'paper_snapshot_id': paper_entry['snapshot_id'], 'paper_count': len(changed['papers']),
                'topic_count': sum(t.get('active', True) for t in changed['topics'].values()),
                'catalog_version': changed['version'],
                'canonical_writes': 0, 'new_d2i_calls': 0}
            changed['commits'][identifier] = result
            self.store.write_json(f'catalogs/{digest(catalog)}.json', catalog)
            self.store.write_json(f'catalogs/{digest(changed)}.json', changed)
            if checkpoint:
                checkpoint('before_catalog')
            self.store.replace_json('catalog.json', changed)
            if checkpoint:
                checkpoint('after_catalog')
            job.update(state='compiled', result=result)
            self._save_job(job)
            return {**result, 'replayed': False}

    def _snapshot(self, entry):
        value = self.store.read_json('snapshots/' + request_id(entry['snapshot_id']) + '.json')
        if value is None or digest(value) != entry['snapshot_sha256']:
            _fail('wiki_snapshot_changed', 6)
        return value

    def _save_snapshot(self, body, previous, identifier):
        semantic = digest(body)
        if previous and previous['body_sha256'] == semantic:
            return previous
        snapshot = {**body, 'snapshot_id': self._id(), 'body_sha256': semantic,
                    'previous_snapshot_id': previous['snapshot_id'] if previous else None,
                    'previous_snapshot_sha256': previous['snapshot_sha256'] if previous else None,
                    'origin_request_id': identifier, 'projection_schema': PROFILE}
        self.store.write_json('snapshots/' + snapshot['snapshot_id'] + '.json', snapshot)
        return {'page_id': body['page_id'], 'snapshot_id': snapshot['snapshot_id'], 'title': body['title'],
                'snapshot_sha256': digest(snapshot), 'body_sha256': semantic}

    def show(self, identifier):
        with self.store.locked():
            return self._job(identifier)

    def catalog(self):
        with self.store.locked():
            return self._catalog()

    def call_failed(self, identifier, phase, failure):
        with self.store.locked():
            job = self._job(identifier)
            if (phase == 'generator' and job['state'] not in ('prepared', 'failed')) or (
                    phase == 'validator' and job['state'] != 'proposed'):
                _fail('invalid_wiki_state', 6)
            expected = self._model_request(job, phase)
            if (not isinstance(failure, dict) or failure.get('input_sha256') != expected['input_sha256']
                    or failure.get('actual_delivery') is not None or failure.get('output_sha256') is not None
                    or failure.get('prompt_sha256') != sha256(expected['prompt'].encode()).hexdigest()
                    or failure.get('schema_sha256') != digest(expected['schema'])):
                _fail('invalid_wiki_failure')
            self.store.write_json(f'jobs/{identifier}/failures/{digest(failure)}.json', failure)
            job.update(failure={'phase': phase, 'code': failure.get('error_code')})
            # Keep a staged proposal retryable; execution failure is not rejection.
            if phase == 'generator':
                job['state'] = 'failed'
            self._save_job(job)
            return {'request_id': identifier, 'state': job['state'], 'failure_recorded': True}

    def history(self, page_id):
        page_id = request_id(page_id)
        with self.store.locked():
            catalog = self._catalog()
            entry = next((e for e in list(catalog['papers'].values()) + list(catalog['topics'].values())
                          if e['page_id'] == page_id), None)
            if entry is None:
                _fail('wiki_page_not_found', 2)
            history = []
            while entry is not None:
                snapshot = self._snapshot(entry)
                if snapshot['page_id'] != page_id:
                    _fail('wiki_snapshot_changed', 6)
                history.append(snapshot)
                entry = ({'snapshot_id': snapshot['previous_snapshot_id'],
                          'snapshot_sha256': snapshot['previous_snapshot_sha256']}
                         if snapshot['previous_snapshot_id'] else None)
            return {'page_id': page_id, 'snapshots': history, 'canonical': False}

    def export(self, *, catalog_sha256=None):
        with self.store.locked():
            catalog = (self.store.read_json(f'catalogs/{data_id(catalog_sha256)}.json')
                       if catalog_sha256 else self._catalog())
            if catalog is None or (catalog_sha256 and digest(catalog) != catalog_sha256):
                _fail('wiki_catalog_changed', 6)
            key = digest(catalog)
            renderer_sha = _profile()['implementation']['paper_wiki.py']
            destination = 'exports/' + digest({'catalog': key, 'renderer': renderer_sha})
            output = []
            for kind, entries in (('papers', catalog['papers']), ('topics', catalog['topics'])):
                for _, entry in sorted(entries.items()):
                    if kind == 'topics' and not entry.get('active', True):
                        continue
                    page = self._snapshot(entry)
                    rendered = pages.render_paper(page, catalog) if kind == 'papers' else pages.render_topic(page, catalog)
                    path = f"{destination}/{kind}/{entry['page_id']}.md"
                    self.store.write_bytes(path, rendered.encode('utf-8'))
                    output.append({'path': f"{kind}/{entry['page_id']}.md", 'page_id': entry['page_id'],
                                   'snapshot_id': entry['snapshot_id'], 'sha256': sha256(rendered.encode()).hexdigest()})
                    if kind == 'papers':
                        data = self.repository.get_data(page['data_id'])
                        if data is None:
                            _fail('wiki_data_not_found', 2)
                        raw = self.source.store.read(page['data_id'], data['byte_size'])
                        suffix = '.pdf' if data['media_type'] == 'application/pdf' else '.txt'
                        self.store.write_bytes(destination + '/originals/' + page['data_id'] + suffix, raw)
                        output.append({'path': 'originals/' + page['data_id'] + suffix,
                                       'data_id': page['data_id'], 'sha256': sha256(raw).hexdigest()})
            index = ['# 논문 Wiki', '', '> 원문 I에 근거한 읽기용 문서입니다. K/P의 canonical 승격이 아닙니다.', '', '## 논문', '']
            for entry in catalog['papers'].values():
                index.append(f"- [[papers/{entry['page_id']}|{pages.escape_text(entry['title'])}]]")
            index += ['', '## 주제', '']
            for entry in catalog['topics'].values():
                if not entry.get('active', True):
                    continue
                index.append(f"- [[topics/{entry['page_id']}|{pages.escape_text(entry['title'])}]]")
            self.store.write_bytes(destination + '/index.md', ('\n'.join(index) + '\n').encode())
            manifest = {'schema_version': PROFILE, 'catalog_sha256': key, 'catalog_version': catalog['version'],
                        'renderer_sha256': renderer_sha,
                        'files': output, 'paper_count': len(catalog['papers']),
                        'topic_count': sum(t.get('active', True) for t in catalog['topics'].values()),
                        'visibility': 'local_private', 'canonical_writes': 0}
            self.store.write_json(destination + '/manifest.json', manifest)
            self.store.replace_json('latest-export.json', {'directory': destination, **manifest})
            return {'directory': str(self.store.root / destination), **manifest}
