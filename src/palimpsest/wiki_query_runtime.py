"""Auditable query-time Wiki/K → I → original-page reading, without canonical writes."""
from copy import deepcopy
from hashlib import sha256
from importlib.resources import files
import math
from pathlib import Path

from .canonical_store import PostgresRepository
from .compiler_runtime import CompilerRuntime
from .data import request_id
from .errors import PalimpsestError
from .i2k import digest
from .knowledge_runtime import MODEL
from .paper_wiki_runtime import _image_suffix
from .wiki_projection_store import ProjectionStore
from .wiki_retrieval import WikiRetrieval, fail, PROJECTION
from . import wiki_query as answers


class WikiQueryRuntime:
    def __init__(self, dsn, artifact_root, directory):
        self.retrieval = WikiRetrieval(dsn, artifact_root)
        self.source = CompilerRuntime(dsn, artifact_root)
        self.repository = PostgresRepository(dsn)
        self.store = ProjectionStore(Path(directory))

    def prepare_index(self, wiki_id, index_id, *, include_data_ids=None):
        index_id = request_id(index_id)
        corpus = self.retrieval.corpus(wiki_id, include_data_ids=include_data_ids)
        with self.store.locked():
            self.store.write_json(f'indexes/{index_id}/corpus.json', corpus)
            self.store.write_json(f'indexes/{index_id}/embedding-request.json', self.retrieval.embedding_request(corpus))
        return {'index_id': index_id, 'documents': len(corpus['documents']), 'information': len(corpus['information']),
                'request_file': str(self.store.root / f'indexes/{index_id}/embedding-request.json')}

    def install_index(self, index_id, result):
        corpus = self.store.read_json(f'indexes/{request_id(index_id)}/corpus.json')
        if corpus is None:
            fail('retrieval_preparation_missing')
        return self.retrieval.install(index_id, corpus, result)

    def _job(self, identifier):
        identifier = request_id(identifier)
        job = self.store.read_json(f'queries/{identifier}/job.json')
        if job is None or job.get('query_id') != identifier:
            fail('wiki_query_missing')
        if job.get('request_sha256') != digest({'index_id': job.get('index_id'), 'question': job.get('question')}):
            fail('wiki_query_request_changed')
        return job

    def _save(self, job):
        self.store.replace_json(f"queries/{job['query_id']}/job.json", job)

    def _index(self, job):
        index = self.retrieval.index(job['index_id'])
        if any(index.get(key) != job.get(key) for key in ('wiki_id', 'import_id')):
            fail('wiki_query_index_binding_mismatch')
        return index

    @staticmethod
    def _round(job):
        return f"queries/{job['query_id']}/rounds/{job['round']}"

    def _write_search_request(self, job):
        path = self._round(job) + '/query-embedding-request.json'
        self.store.write_json(path, {'schema_version': 'wiki-embedding-request-v1',
            'documents': [{'document_id': 'query', 'text': job['search_query']}]})
        return str(self.store.root / path)

    def prepare(self, index_id, identifier, question):
        identifier = request_id(identifier)
        if not isinstance(question, str) or not question.strip() or '\x00' in question:
            fail('invalid_wiki_question')
        index = self.retrieval.index(index_id)
        value = {'index_id': index_id, 'question': question}
        with self.store.locked():
            old = self.store.read_json(f'queries/{identifier}/job.json')
            if old:
                if old['request_sha256'] != digest(value):
                    fail('idempotency_conflict')
                return {**old, 'replayed': True}
            job = {'schema_version': 'wiki-query-run-v1', 'query_id': identifier, **value,
                'request_sha256': digest(value), 'wiki_id': index['wiki_id'], 'import_id': index['import_id'],
                'round': 0, 'layer': 'knowledge', 'search_query': question, 'state': 'search_pending',
                'context_path': None, 'canonical_writes': 0, 'd2i_calls': 0}
            path = self._write_search_request(job)
            self._save(job)
            return {**job, 'embedding_request_file': path, 'replayed': False}

    def search(self, identifier, encoded):
        with self.store.locked():
            job = self._job(identifier)
            if job['state'] not in ('search_pending', 'rerank_pending'):
                fail('invalid_wiki_query_state')
            result = self.retrieval.search(job['index_id'], job['search_query'], encoded, layer=job['layer'])
            root = self._round(job)
            self.store.write_json(root + '/query-embedding-result.json', encoded)
            self.store.write_json(root + '/search.json', result)
            self.store.write_json(root + '/rerank-request.json', result['rerank_request'])
            job['state'] = 'rerank_pending'
            self._save(job)
            return {'query_id': identifier, 'state': job['state'], 'candidates': len(result['matches']),
                    'rerank_request_file': str(self.store.root / root / 'rerank-request.json')}

    def _assets(self, context):
        assets = {}
        for unit in context['information']:
            for asset in unit['media']:
                assets[asset['sha256']] = asset
        for image in context['source_images']:
            assets[image['image_sha256']] = {'sha256': image['image_sha256'], 'byte_size': image['byte_size']}
        for view in context.get('data_views', []):
            if view['kind'] != 'pdf_page':
                continue
            key = view['image_sha256']
            if key in assets and assets[key]['byte_size'] != view['image_byte_size']:
                fail('wiki_query_data_image_changed')
            assets[key] = {'sha256': key, 'byte_size': view['image_byte_size']}
        result = []
        for key, asset in sorted(assets.items()):
            raw = self.source.derived.read(key, asset['byte_size'])
            result.append({'sha256': key, 'byte_size': len(raw), 'path': 'media/' + key + _image_suffix(raw)})
        return result

    def _context(self, job):
        context = self.store.read_json(job['context_path']) if job['context_path'] else None
        if context is None or digest(context) != job.get('context_sha256'):
            fail('wiki_query_context_changed')
        if any(context.get(key) != job.get(key) for key in ('query_id', 'question', 'wiki_id', 'import_id', 'index_id')):
            fail('wiki_query_context_changed')
        return context

    def _set_context(self, job, context):
        root = self._round(job)
        assets = self._assets(context)
        for asset in assets:
            self.store.write_bytes(root + '/' + asset['path'], self.source.derived.read(asset['sha256'], asset['byte_size']))
        context['image_attachments'] = assets
        self.store.write_json(root + '/context.json', context)
        job.update(context_path=root + '/context.json', context_sha256=digest(context), state='input_ready')
        self._save(job)

    def context(self, identifier, reranked):
        with self.store.locked():
            job = self._job(identifier)
            if job['state'] != 'rerank_pending':
                fail('invalid_wiki_query_state')
            index = self._index(job)
            search = self.store.read_json(self._round(job) + '/search.json')
            if (reranked.get('schema_version') != 'wiki-rerank-result-v1'
                    or reranked.get('input_sha256') != digest(search['rerank_request'])
                    or reranked.get('profile') != index['profile']):
                fail('rerank_input_mismatch')
            scores = {}
            matches = {item['chunk_id']: item for item in search['matches']}
            for item in reranked.get('scores', []):
                key, score = item.get('chunk_id'), item.get('score')
                if (key not in matches or key in scores or type(score) not in (int, float) or not math.isfinite(score)):
                    fail('invalid_rerank_score')
                scores[key] = score
            if set(scores) != set(matches):
                fail('rerank_coverage_mismatch')
            # A per-call retrieval window, not an evidence sufficiency verdict or loop cutoff.
            selected = list(dict.fromkeys(matches[key]['document_id'] for key in
                            sorted(scores, key=lambda key: (-scores[key], key))))[:8]
            corpus = index['corpus']
            documents = {doc['document_id']: doc for doc in corpus['documents']}
            information_ids = {identifier for key in selected for identifier in documents[key]['information_ids']}
            previous = self._context(job) if job['context_path'] else None
            if previous:
                information_ids.update(unit['information_id'] for unit in previous['information'])
            selected_knowledge = {documents[key]['knode_revision_id'] for key in selected if documents[key]['kind'] == 'knowledge'}
            if previous:
                selected_knowledge.update(node['knode_revision_id'] for node in previous['knowledge'])
            by_revision = {node['knode_revision_id']: node for node in corpus['knowledge']}
            pending = list(selected_knowledge)
            while pending:
                node = by_revision[pending.pop()]
                for support in node.get('retrieval_support', {}).get('records', []):
                    revision = support['knode_revision_id']
                    if revision not in by_revision:
                        fail('retrieval_premise_unavailable')
                    if revision not in selected_knowledge:
                        selected_knowledge.add(revision)
                        pending.append(revision)
                information_ids.update(node.get('retrieval_support', {}).get('information_ids', []))
            context = {'schema_version': 'wiki-query-context-v1', 'query_id': identifier,
                'question': job['question'], 'wiki_id': job['wiki_id'], 'import_id': job['import_id'],
                'index_id': job['index_id'], 'knowledge_state_version': corpus['knowledge_state_version'],
                'round': job['round'], 'layer': 'source' if previous and previous['source_images'] else job['layer'],
                'knowledge': [node for node in corpus['knowledge'] if node['knode_revision_id'] in selected_knowledge],
                'wiki_items': [item for item in corpus['wiki_items'] if item['document_id'] in selected],
                'information': [unit for unit in corpus['information'] if unit['information_id'] in information_ids],
                'sources': corpus['sources'], 'source_images': previous['source_images'] if previous else [],
                'retrieval': {'search_query': job['search_query'], 'selected_documents': selected,
                              'information_search_performed': job['layer'] == 'information' or bool(
                                  previous and previous.get('retrieval', {}).get('information_search_performed')),
                              'available_information': len(corpus['information']), 'evidence_sufficiency': 'not_determined'}}
            if 'epistemic_projection_profile' in corpus:
                context['epistemic_projection_profile'] = corpus['epistemic_projection_profile']
            if 'knowledge_inference_profile' in corpus:
                context['knowledge_inference_profile'] = corpus['knowledge_inference_profile']
                supplied_edges = {digest(edge): edge for node in context['knowledge']
                    for edge in node.get('retrieval_support', {}).get('effective_edge_premises', [])}
                context['effective_edge_premises'] = [deepcopy(supplied_edges[key]) for key in sorted(supplied_edges)]
            if corpus.get('projection_profile', {}).get('schema_version') == PROJECTION:
                context.update(inference_citations_supported=True,
                    source_version_snapshot=deepcopy(corpus['source_version_snapshot']))
            if corpus.get('data_citations_supported') is True:
                selected_views = {grounding['view_id'] for node in context['knowledge']
                    for grounding in node.get('direct_data_groundings', []) + node.get('transitive_data_refs', [])}
                context.update(data_citations_supported=True, data_sources=deepcopy(corpus['data_sources']),
                    data_views=[deepcopy(view) for view in corpus['data_views'] if view['view_id'] in selected_views])
            self.store.write_json(self._round(job) + '/rerank-result.json', reranked)
            self._set_context(job, context)
            return {'query_id': identifier, 'state': job['state'], 'information': len(context['information']),
                    'knowledge': len(context['knowledge']), 'images': len(context['image_attachments'])}

    def model_request(self, identifier, phase):
        if phase not in ('generator', 'validator'):
            fail('invalid_wiki_query_phase')
        with self.store.locked():
            job = self._job(identifier)
            self._index(job)
            root = self._round(job)
            path = root + '/' + phase + '-request.json'
            previous = self.store.read_json(path)
            if previous is not None:
                return {'query_id': identifier, 'request_file': str(self.store.root / path), 'replayed': True}
            if job['state'] != ('input_ready' if phase == 'generator' else 'proposed'):
                fail('invalid_wiki_query_state')
            context = self._context(job)
            if phase == 'generator':
                prompt, schema = answers.generation_prompt(context), answers.generation_schema(context)
                input_hash = digest(context)
            else:
                proposal = self.store.read_json(root + '/proposal.json')
                prompt, schema = answers.validation_prompt(context, proposal), answers.validation_schema(proposal)
                input_hash = digest({'context': context, 'answer': proposal})
            value = {'prompt': prompt, 'schema': schema, 'input_sha256': input_hash,
                'images': context['image_attachments'],
                'delivered_information_ids': [unit['information_id'] for unit in context['information']],
                'output_file': phase + '-response.json'}
            if context.get('inference_citations_supported') is True:
                value['delivered_knowledge_revision_ids'] = [node['knode_revision_id'] for node in context['knowledge']]
            if 'knowledge_inference_profile' in context:
                value['delivered_effective_edge_premises'] = deepcopy(context['effective_edge_premises'])
            if context.get('data_citations_supported') is True:
                value['delivered_data_view_ids'] = [view['view_id'] for view in context['data_views']]
            self.store.write_json(path, value)
            self.store.write_json(root + '/' + phase + '-binding.json', {
                'request_sha256': digest(value), 'query_policy_sha256': sha256(
                    files('palimpsest').joinpath('wiki_query.py').read_bytes()).hexdigest()})
            return {'query_id': identifier, 'request_file': str(self.store.root / path),
                    'information': len(context['information']), 'images': len(value['images']), 'replayed': False}

    def _receipt(self, job, phase, exchange):
        if not isinstance(exchange, dict) or set(exchange) != {'receipt', 'response'}:
            fail('invalid_wiki_query_exchange')
        expected = self.store.read_json(self._round(job) + '/' + phase + '-request.json')
        binding = self.store.read_json(self._round(job) + '/' + phase + '-binding.json')
        receipt = exchange['receipt']
        context = self._context(job)
        if phase == 'generator':
            bound_hash = digest(context)
            bound_prompt, bound_schema = answers.generation_prompt(context), answers.generation_schema(context)
        else:
            proposal = self.store.read_json(self._round(job) + '/proposal.json')
            generated = self.store.read_json(self._round(job) + '/generator-exchange.json')
            if generated is None or proposal != answers.normalize_answer(generated['response'], context):
                fail('wiki_query_proposal_changed')
            self._receipt(job, 'generator', generated)
            bound_hash = digest({'context': context, 'answer': proposal})
            bound_prompt, bound_schema = answers.validation_prompt(context, proposal), answers.validation_schema(proposal)
        if (expected is None or not isinstance(receipt, dict) or not isinstance(receipt.get('profile'), dict)
                or expected.get('input_sha256') != bound_hash
                or (binding is not None and binding.get('request_sha256') != digest(expected))
                or (binding is None and (expected.get('prompt') != bound_prompt or expected.get('schema') != bound_schema))
                or expected.get('images') != context['image_attachments']
                or expected.get('delivered_information_ids') != [unit['information_id'] for unit in context['information']]
                or expected.get('output_file') != phase + '-response.json'
                or any(receipt['profile'].get(k) != v for k, v in MODEL.items())
                or receipt.get('actual_delivery') is not True or receipt.get('original_pdf_delivered') is not False
                or not receipt.get('provider_ref') or receipt.get('input_sha256') != expected['input_sha256']
                or receipt.get('output_sha256') != digest(exchange['response'])
                or receipt.get('prompt_sha256') != sha256(expected['prompt'].encode()).hexdigest()
                or receipt.get('schema_sha256') != digest(expected['schema'])
                or receipt.get('delivered_information_ids') != expected['delivered_information_ids']
                or receipt.get('image_attachments') != [{k: a[k] for k in ('sha256', 'byte_size')} for a in expected['images']]):
            fail('wiki_query_delivery_mismatch')
        if phase == 'validator':
            generated = self.store.read_json(self._round(job) + '/generator-exchange.json')
            if receipt['provider_ref'] == generated['receipt']['provider_ref']:
                fail('wiki_query_validator_not_independent')
        if context.get('inference_citations_supported') is True:
            revisions = [node['knode_revision_id'] for node in context['knowledge']]
            if (expected.get('delivered_knowledge_revision_ids') != revisions
                    or receipt.get('delivered_knowledge_revision_ids') != revisions):
                fail('wiki_query_knowledge_delivery_mismatch')
        if 'knowledge_inference_profile' in context:
            edges = context['effective_edge_premises']
            if (expected.get('delivered_effective_edge_premises') != edges
                    or receipt.get('delivered_effective_edge_premises') != edges):
                fail('wiki_query_edge_delivery_mismatch')
        if context.get('data_citations_supported') is True:
            views = [view['view_id'] for view in context['data_views']]
            delivered_images = {asset['sha256']: asset['byte_size'] for asset in expected['images']}
            if (len(views) != len(set(views)) or expected.get('delivered_data_view_ids') != views
                    or receipt.get('delivered_data_view_ids') != views
                    or any(delivered_images.get(view['image_sha256']) != view['image_byte_size']
                           for view in context['data_views'] if view['kind'] == 'pdf_page')):
                fail('wiki_query_data_delivery_mismatch')

    def stage(self, identifier, exchange):
        with self.store.locked():
            job = self._job(identifier)
            self._index(job)
            root = self._round(job)
            if (job.get('last_generator_exchange_path')
                    and self.store.read_json(job['last_generator_exchange_path']) == exchange):
                return job
            if job['state'] != 'input_ready':
                prior = self.store.read_json(root + '/generator-exchange.json')
                if prior == exchange:
                    return job
                fail('invalid_wiki_query_state')
            self._receipt(job, 'generator', exchange)
            try:
                normalized = answers.normalize_answer(exchange['response'], self._context(job))
            except PalimpsestError as error:
                failure_path = root + '/failures/' + digest(exchange) + '.json'
                self.store.write_json(failure_path,
                                      {'error': error.code, 'exchange': exchange})
                job.update(state='invalid_response', last_failure_path=failure_path)
                self._save(job)
                raise
            self.store.write_json(root + '/generator-exchange.json', exchange)
            self.store.write_json(root + '/proposal.json', normalized)
            status = exchange['response']['status']
            job.update(state='proposed', last_proposal_path=root + '/proposal.json',
                       last_generator_exchange_path=root + '/generator-exchange.json')
            if status == 'needs_information':
                job.update(round=job['round'] + 1, layer='information', state='search_pending',
                           search_query=exchange['response']['search_query'])
                job['embedding_request_file'] = self._write_search_request(job)
            elif status == 'needs_source':
                job.update(state='source_pending', source_requests=exchange['response']['source_requests'])
            self._save(job)
            return job

    def source_pages(self, identifier):
        with self.store.locked():
            job = self._job(identifier)
            if job['state'] != 'source_pending':
                fail('invalid_wiki_query_state')
            index = self._index(job)
            context = deepcopy(self._context(job))
            packets = {(packet['data_id'], packet['source_execution_id']): packet
                       for packet in index['corpus']['source_packets']}
            sources = {source['data_id']: source for source in context['sources']}
            images = {image['evidence_id']: image for image in context['source_images']}
            records = []
            for request in job['source_requests']:
                source = sources.get(request['data_id'])
                packet = packets.get((request['data_id'], source['source_execution_id'])) if source else None
                if packet is None:
                    fail('original_source_execution_mismatch')
                registered = self.source.data.get_data(request['data_id'])
                if registered is None or registered['media_type'] != 'application/pdf':
                    fail('original_pdf_required')
                raw = self.source.store.read(request['data_id'], registered['byte_size'])
                if sha256(raw).hexdigest() != request['data_id'] or b'%PDF-' not in raw[:1024]:
                    fail('original_pdf_changed')
                self.store.write_bytes(f"queries/{identifier}/originals/{request['data_id']}.pdf", raw)
                found = set()
                for unit in packet['model_input']['information']:
                    for ref in unit['source_refs']:
                        provenance = ref.get('facsimile_provenance')
                        if not provenance or ref.get('page_index', -1) + 1 not in request['page_numbers']:
                            continue
                        page = ref['page_index'] + 1
                        owned = [a for a in unit['media'] if a['sha256'] == provenance['image_sha256']]
                        if (provenance['data_id'] != request['data_id'] or provenance['page_index'] + 1 != page
                                or len(owned) != 1):
                            fail('original_page_binding_mismatch')
                        key = 'd/' + request['data_id'] + '/page/' + str(page)
                        images[key] = {'evidence_id': key, 'data_id': request['data_id'], 'page_number': page,
                            'image_sha256': provenance['image_sha256'], 'byte_size': owned[0]['byte_size'],
                            'original_sha256': request['data_id'], 'source_execution_id': packet['source_execution_id'],
                            'provenance': provenance, 'original_pdf_delivered': False,
                            'delivery_form': 'retained_original_page_image'}
                        found.add(page)
                if found != set(request['page_numbers']):
                    fail('original_page_unavailable')
                records.append({'request': request, 'original_sha256': request['data_id'], 'byte_size': len(raw),
                    'original_pdf_read_locally': True, 'original_pdf_delivered': False,
                    'prepared_pages': sorted(found), 'actual_model_delivery': False,
                    'source_gap_classification': 'inspection_requested_not_confirmed_omission'})
            job.update(round=job['round'] + 1, layer='source')
            context.update(round=job['round'], layer='source', source_images=list(images.values()))
            self.store.write_json(self._round(job) + '/source-inspection.json', records)
            self._set_context(job, context)
            return {'query_id': identifier, 'state': job['state'], 'source_images': len(images),
                    'original_pdf_delivered': False, 'd2i_calls': 0}

    def decide(self, identifier, exchange):
        with self.store.locked():
            job = self._job(identifier)
            self._index(job)
            root = self._round(job)
            if job['state'] != 'proposed':
                if self.store.read_json(root + '/validator-exchange.json') == exchange:
                    return job
                fail('invalid_wiki_query_state')
            self._receipt(job, 'validator', exchange)
            proposal = self.store.read_json(root + '/proposal.json')
            validation = answers.validate_answer(exchange['response'], proposal)
            self.store.write_json(root + '/validator-exchange.json', exchange)
            self.store.write_json(root + '/validation.json', validation)
            accepted = validation.get('verdict') == 'accepted'
            job.update(state='answered' if accepted else 'needs_review',
                       answer_path=root + '/answer.md', validation_path=root + '/validation.json')
            self.store.write_bytes(job['answer_path'], answers.render_answer(proposal, validation).encode())
            self._save(job)
            return job

    def revise(self, identifier, review_notes=None):
        notes = [] if review_notes is None else review_notes
        if not isinstance(notes, list) or any(not isinstance(note, str) or not note.strip() for note in notes):
            fail('invalid_wiki_query_feedback')
        with self.store.locked():
            job = self._job(identifier)
            self._index(job)
            if job['state'] not in ('answered', 'needs_review', 'invalid_response') or (job['state'] == 'answered' and not notes):
                fail('invalid_wiki_query_state')
            context = deepcopy(self._context(job))
            previous = self._round(job)
            feedback = {'answer': self.store.read_json(previous + '/proposal.json'),
                'validation': self.store.read_json(previous + '/validation.json'), 'review_notes': notes,
                'structural_failure': (self.store.read_json(job['last_failure_path'])
                                       if job['state'] == 'invalid_response' else None),
                'authority': 'review_feedback_not_source_evidence'}
            job.update(round=job['round'] + 1)
            for key in ('answer_path', 'validation_path'):
                if key in job:
                    job['prior_' + key] = job.pop(key)
            context.update(round=job['round'], prior_feedback=feedback)
            self._set_context(job, context)
            return job

    def pause(self, identifier, reason):
        if not isinstance(reason, str) or not reason.strip() or '\x00' in reason:
            fail('invalid_wiki_query_attention_reason')
        with self.store.locked():
            job = self._job(identifier)
            if job['state'] == 'needs_attention':
                if job['attention_reason'] != reason:
                    fail('idempotency_conflict')
                return job
            if job['state'] in ('answered', 'needs_review'):
                fail('invalid_wiki_query_state')
            record = {'query_id': identifier, 'round': job['round'], 'previous_state': job['state'],
                      'reason': reason, 'completed': False, 'canonical_writes': 0}
            self.store.write_json(self._round(job) + '/attention.json', record)
            job.update(state='needs_attention', attention_reason=reason, paused_state=job['state'])
            self._save(job)
            return job

    def show(self, identifier):
        job = self._job(identifier)
        if job.get('answer_path'):
            job['answer'] = self.store.read_bytes(job['answer_path']).decode()
        return job
