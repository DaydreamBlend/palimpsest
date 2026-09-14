"""Versioned Wiki/K/I retrieval projections. Similarity never approves evidence."""
from copy import deepcopy
from hashlib import sha256
from importlib.resources import files
import json
import math

from psycopg.types.json import Jsonb

from .canonical_store import connection
from .data import data_id as validate_data_id, request_id
from .errors import PalimpsestError
from .i2k import digest
from .knowledge_runtime import KnowledgeRuntime, _json
from .wiki_archive import validate_archive_files
from .wiki_database import WikiDatabase
from . import d2k, knowledge_provenance, version_provenance, edge_projection


PROJECTION = 'wiki-accepted-support-v1'


def projection_profile():
    return {'schema_version': PROJECTION, 'version_mode': 'current', 'implementation': {
        name: sha256(files('palimpsest').joinpath(name).read_bytes()).hexdigest()
        for name in ('wiki_retrieval.py', 'wiki_database.py', 'knowledge_runtime.py',
                     'knowledge_provenance.py', 'version_provenance.py', 'd2k.py', 'edge_projection.py')}}


def source_version_snapshot(state, data_ids, context_series=()):
    """Freeze relevant membership and heads separately from immutable K origins."""
    versions = [] if state is None else [deepcopy(v) for v in state['versions'].values()
                                        if v['data_id'] in data_ids]
    series = sorted({v['series_id'] for v in versions} | set(context_series))
    return {'versions': sorted(versions, key=lambda v: v['version_id']),
            'heads': {key: state['heads'].get(key) for key in series}}


def source_version_status(state, data_id):
    versions = [] if state is None else [v for v in state['versions'].values() if v['data_id'] == data_id]
    if not versions:
        return 'untracked'
    return 'current' if all(any(v['series_id'] == series and
        state['heads'].get(series) == v['version_id'] for v in versions)
        for series in {v['series_id'] for v in versions}) else 'historical'


def information_document(unit):
    """Make empty source units findable without inventing source transcription."""
    text, origin = unit['content'], 'information_content'
    if not text.strip():
        if unit['media']:
            # BGE is a text encoder; this is a retained title, not visual content.
            text = (unit.get('title') or 'Image Information') + '\n[Image media; no source transcription]'
            origin = 'retained_media_title_descriptor'
        else:
            description = 'empty' if not text else 'whitespace-only'
            text = (unit.get('title') or 'Information') + f'\n[Information metadata; {description} source text]'
            origin = 'retained_source_metadata_descriptor'
    return {'document_id': 'i/' + unit['information_id'], 'kind': 'information',
            'text': text, 'text_origin': origin, 'information_ids': [unit['information_id']]}


def _edge_history_metadata(edge):
    """Retain historical refs without delivering an unselected relation's text."""
    result = deepcopy(edge)
    if 'qualifiers' in result:
        result['qualifiers_sha256'] = digest(result.pop('qualifiers'))
    return result


def knowledge_projection(graph, units, records, versions, excluded, *, data_sources=(), data_views=()):
    """Select complete accepted routes; a shared leaf alone cannot support K.

    No new grounding is created. A derived result retains the actual premise
    revision on each leaf and records every selected derivation/terminal Record.
    """
    data_ids = {unit['data_id'] for unit in units.values()} | {source['data_id'] for source in data_sources}
    views = {view['view_id']: d2k.check_view(view) for view in data_views}
    data_groundings = {row['grounding_id']: knowledge_provenance.data_grounding(row)
                       for row in graph.get('data_groundings', [])}
    nodes = {node['knode_revision_id']: node for node in graph['nodes']
             if node['knode_revision_id'] not in excluded
             and node['current_revision_id'] == node['knode_revision_id']
             and node.get('current_applicability', 'current_premises') == 'current_premises'
             and (node.get('identity_scope') != 'source' or node.get('source_data_id') in data_ids)}
    by_revision = {}
    for grounding in graph['groundings']:
        by_revision.setdefault(grounding['node_revision_id'], []).append(grounding)
    routes, pending = {}, list(records)
    # ponytail: fixed-point scans suit the current small corpus; use a dependency
    # queue if profiling warrants it. This imposes no inference-depth cutoff.
    while pending:
        remaining = []
        for record in pending:
            revision, record_id = record['result_node_revision_id'], record['record_id']
            if revision not in nodes or revision in routes:
                continue
            node = nodes[revision]
            contexts = node.get('data_version_supports', [])
            context = next((entry['versions'] for entry in contexts if entry['record_id'] == record_id), [])
            if (contexts and not context) or any(versions is None
                    or versions['heads'].get(v['series_id']) != v['version_id']
                    or (record['record_type'] == 'k2k' and v['data_id'] not in data_ids) for v in context):
                continue
            details = {'record_id': record_id, 'knode_revision_id': revision,
                       'operation': record['record_type'], 'premise_revision_ids': [],
                       'information_ids': [], 'data_versions': deepcopy(context)}
            data_leaves = []
            if record['record_type'] == 'i2k':
                if record.get('data_grounding_ids'):
                    continue
                used = set(record['information_ids'])
                if (not used or not used <= units.keys() or any(
                        source_version_status(versions, units[key]['data_id']) == 'historical' for key in used)):
                    continue
                if context and not {units[key]['data_id'] for key in used} <= {v['data_id'] for v in context}:
                    continue
                groundings = [g for g in by_revision.get(revision, []) if g['information_id'] in used]
                if {g['information_id'] for g in groundings} != used:
                    continue
                details['information_ids'] = sorted(used)
                route_records = {record_id: details}
            elif record['record_type'] == 'd2k':
                identifiers = record.get('data_grounding_ids', [])
                if record['information_ids'] or not identifiers or any(key not in data_groundings for key in identifiers):
                    continue
                data_leaves = [data_groundings[key] for key in identifiers]
                if any(row['node_revision_id'] != revision or row['origin_record_id'] != record_id
                       or row['data_id'] not in data_ids or row['view_id'] not in views
                       or views[row['view_id']]['data_id'] != row['data_id']
                       or source_version_status(versions, row['data_id']) == 'historical' for row in data_leaves):
                    continue
                for row in data_leaves:
                    view = views[row['view_id']]
                    packet = d2k.build_input(row['data_id'], media_type='application/pdf' if view['kind'] == 'pdf_page' else 'text/plain',
                                            original_byte_size=view['original_byte_size'], views=[view])
                    citation = {'view_id': view['view_id'], 'source_role': row['source_role']}
                    if view['kind'] == 'text':
                        citation.update(char_start=row['char_start'], char_end=row['char_end'])
                    expected = d2k.normalize_evidence(citation, packet)
                    if any(row.get(key) != value for key, value in expected.items()):
                        fail('retrieval_data_grounding_changed')
                if context and not {row['data_id'] for row in data_leaves} <= {v['data_id'] for v in context}:
                    continue
                details['data_grounding_ids'] = list(identifiers)
                used, groundings = set(), []
                route_records = {record_id: details}
            elif record['record_type'] == 'k2k':
                if record.get('information_ids') or record.get('data_grounding_ids'):
                    continue
                derivation = next((d for d in node.get('derivations', []) if d['record_id'] == record_id), None)
                if not derivation or derivation['current_applicability'] != 'current_premises':
                    continue
                premises = derivation['premise_revision_ids']
                if not premises or not set(premises) <= nodes.keys():
                    continue
                edge_premises = derivation.get('effective_edge_premises', [])
                if (derivation.get('stale_effective_edge_refs') or any(
                        not {edge['effective_edge_ref']['from_knode_revision_id'],
                             edge['effective_edge_ref']['to_knode_revision_id']} <= set(premises)
                        for edge in edge_premises)):
                    continue
                if not set(premises) <= routes.keys():
                    remaining.append(record)
                    continue
                details['premise_revision_ids'] = list(premises)
                details['derivation'] = deepcopy(derivation)
                route_records = {entry['record_id']: entry for premise in premises
                                 for entry in routes[premise]['records']}
                route_records[record_id] = details
                groundings = list({g['grounding_id']: g for premise in premises
                                   for g in routes[premise]['groundings']}.values())
                used = {g['information_id'] for g in groundings}
                data_leaves = list({g['grounding_id']: g for premise in premises
                    for g in routes[premise].get('data_groundings', [])}.values())
            else:
                continue
            routes[revision] = {'record_id': record_id, 'operation': record['record_type'],
                'premise_revision_ids': details['premise_revision_ids'], 'information_ids': sorted(used),
                'source_data_ids': sorted({units[key]['data_id'] for key in used} | {row['data_id'] for row in data_leaves}),
                'records': [route_records[key] for key in sorted(route_records)],
                'groundings': sorted(groundings, key=lambda g: g['grounding_id'])}
            if views:
                routes[revision]['data_groundings'] = sorted(data_leaves, key=lambda row: row['grounding_id'])
            selected_edges = [{'record_id': entry['record_id'], **deepcopy(edge)}
                for entry in routes[revision]['records']
                for edge in entry.get('derivation', {}).get('effective_edge_premises', [])]
            if selected_edges or node.get('knowledge_inference_profile') == knowledge_provenance.EFFECTIVE_INFERENCE_PROFILE:
                routes[revision]['effective_edge_premises'] = selected_edges
        if len(remaining) == len(pending):
            break
        pending = remaining
    documents, knowledge = [], []
    for revision, route in sorted(routes.items()):
        node = nodes[revision]
        origin = node.get('generation_origin', {})
        inferred = origin.get('is_inferred') is True
        # Other accepted direct supports remain canonical history. The query
        # receives only the I in this selected complete route, so do not leak
        # extra undelivered I quotes through Knowledge metadata.
        direct = [g for g in by_revision.get(revision, []) if g['information_id'] in route['information_ids']]
        basis = ('system_inference' if inferred else 'source_content'
                 if origin.get('is_inferred') is False else 'legacy_unclassified')
        projected = {key: deepcopy(value) for key, value in node.items()
                     if key not in ('direct_data_groundings', 'transitive_data_refs',
                                    'current_transitive_source_refs', 'current_transitive_data_refs',
                                    'current_effective_edge_refs', 'current_stale_effective_edge_refs')}
        selected_records = {entry['record_id'] for entry in route['records']}
        for derivation in projected.get('derivations', []):
            if derivation['record_id'] not in selected_records and 'effective_edge_premises' in derivation:
                derivation['effective_edge_premises'] = list(map(_edge_history_metadata, derivation['effective_edge_premises']))
            if 'stale_effective_edge_refs' in derivation:
                derivation['stale_effective_edge_refs'] = list(map(_edge_history_metadata, derivation['stale_effective_edge_refs']))
        if origin.get('origin_record_id') not in selected_records:
            if 'effective_edge_premises' in projected.get('generation_origin', {}):
                projected['generation_origin']['effective_edge_premises'] = list(map(
                    _edge_history_metadata, projected['generation_origin']['effective_edge_premises']))
            if 'origin_effective_edge_refs' in projected:
                projected['origin_effective_edge_refs'] = list(map(_edge_history_metadata, projected['origin_effective_edge_refs']))
        if projected.get('epistemic_projection') not in (None, 'contested', 'uncontested'):
            fail('retrieval_epistemic_projection_invalid')
        knowledge.append({**projected, 'groundings': deepcopy(direct),
            'direct_groundings': deepcopy(direct), 'retrieval_basis': basis,
            'transitive_source_refs': [deepcopy(g) for g in route['groundings'] if g['node_revision_id'] != revision],
            'retrieval_support': {key: deepcopy(value) for key, value in route.items() if key not in ('groundings', 'data_groundings')},
            **version_provenance.graph_view(versions, node)})
        if views:
            data = route['data_groundings']
            knowledge[-1].update(direct_data_groundings=[deepcopy(g) for g in data if g['node_revision_id'] == revision],
                transitive_data_refs=[deepcopy(g) for g in data if g['node_revision_id'] != revision])
        documents.append({'document_id': 'k/' + revision, 'kind': 'knowledge',
            'text': node['statement'], 'knode_revision_id': revision, 'retrieval_basis': basis,
            'information_ids': route['information_ids']})
    return documents, knowledge


def fail(code='invalid_wiki_retrieval'):
    raise PalimpsestError(code, '검색 profile·현재 snapshot·원문 범위와 실행 결과를 확인하세요.', 4)


def vector(value, dimensions):
    if (not isinstance(value, list) or len(value) != dimensions or not value
            or any(type(v) not in (float, int) or not math.isfinite(v) for v in value)
            or not any(value)):
        fail('invalid_embedding_vector')
    return '[' + ','.join(str(float(v)) for v in value) + ']'


class WikiRetrieval:
    def __init__(self, dsn, artifact_root):
        self.dsn = dsn
        self.database = WikiDatabase(dsn, artifact_root)

    @staticmethod
    def _source_versions(conn, corpus, *, lock=False):
        data_ids = {source['data_id'] for source in corpus['sources']} | set(corpus.get('include_data_ids', []))
        context_series = list(corpus.get('source_version_snapshot', {}).get('heads', {}))
        if lock and conn.execute("SELECT to_regclass('canonical_store.data_versions') AS relation").fetchone()['relation']:
            conn.execute('''SELECT series_id FROM canonical_store.data_series
                WHERE series_id=ANY(%s::uuid[]) OR series_id IN (
                    SELECT series_id FROM canonical_store.data_versions WHERE data_id=ANY(%s::text[]))
                ORDER BY series_id FOR SHARE''', (context_series, sorted(data_ids))).fetchall()
        return source_version_snapshot(version_provenance.load(conn), data_ids, context_series)

    def corpus(self, wiki_id, include_data_ids=None):
        wiki_id = request_id(wiki_id)
        if include_data_ids is not None:
            if not isinstance(include_data_ids, (list, tuple)):
                fail('invalid_retrieval_data_scope')
            include_data_ids = [validate_data_id(value) for value in include_data_ids]
            if len(include_data_ids) != len(set(include_data_ids)):
                fail('invalid_retrieval_data_scope')
            include_data_ids = sorted(include_data_ids)
        with connection(self.dsn) as conn, conn.transaction():
            # The graph reader takes a shared K-state lock; this transaction performs no writes.
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            self.database._ready(conn)
            selected = self.database._import(conn, wiki_id)
            rows = conn.execute('''SELECT f.path,b.content FROM wiki_projection.files f
                JOIN wiki_projection.blobs b ON b.sha256=f.raw_sha256 WHERE f.request_id=%s''',
                (selected['request_id'],)).fetchall()
            archive = validate_archive_files({row['path']: bytes(row['content']) for row in rows})
            catalog = archive['catalogs'][selected['catalog_sha256']]
            selected_executions = {archive['snapshots'][entry['snapshot_id']]['source_execution_id']
                                   for entry in catalog['papers'].values()}
            packets = [packet for key, packet in archive['source_packets'].items() if key in selected_executions]
            units = {}
            for packet in packets:
                KnowledgeRuntime._verify_i(conn, packet['data_id'], packet)
                for unit in packet['model_input']['information']:
                    units[unit['information_id']] = {**unit, 'data_id': packet['data_id'],
                        'source_execution_id': packet['source_execution_id']}
            graph = self.database._graph(conn, units)
            if graph['state_version'] != selected['knowledge_state_version']:
                fail('wiki_import_refresh_required')
            self.database._verify_graph_groundings(graph, units)
            owners = {unit['data_id'] for unit in units.values()} | set(include_data_ids or [])
            metadata = {row['data_id']: row for row in _json(conn.execute(
                'SELECT data_id,byte_size,media_type FROM canonical_store.data WHERE data_id=ANY(%s::text[])',
                (sorted(owners),)).fetchall())}
            if set(metadata) != owners:
                fail('retrieval_data_not_registered')
            data_views = {}
            has_data_groundings = conn.execute("SELECT to_regclass('canonical_store.knowledge_data_groundings') AS relation").fetchone()['relation'] is not None
            if has_data_groundings:
                graph['data_groundings'] = _json(conn.execute(
                    'SELECT * FROM canonical_store.knowledge_data_groundings ORDER BY grounding_id').fetchall())
                originals, images = {}, {}
                for grounding in graph['data_groundings']:
                    owner = grounding['data_id']
                    if owner not in owners:
                        continue
                    stored = _json(conn.execute('SELECT body FROM compiler_runtime.d2k_source_views WHERE view_id=%s',
                                               (grounding['view_id'],)).fetchone())
                    if stored is None:
                        fail('retrieval_data_view_missing')
                    view = stored['body']
                    if owner not in originals:
                        originals[owner] = self.database.source.store.read(owner, metadata[owner]['byte_size'])
                    image = None
                    if view['kind'] == 'pdf_page':
                        key = view['image_sha256']
                        if key not in images:
                            images[key] = self.database.source.derived.read(key, view['image_byte_size'])
                        image = images[key]
                    _, verified = knowledge_provenance.verify_data_grounding(grounding, view, originals[owner], image=image)
                    data_views[verified['view_id']] = verified
            excluded = {note['node_revision_id'] for note in selected['review_annotations']}
            # Count each accepted Record's entire actual I route before applying
            # the selected-source filter; a partial multi-Data match is unsafe.
            data_columns = (''', ARRAY(SELECT g.grounding_id FROM canonical_store.knowledge_data_groundings g
                WHERE g.node_revision_id=r.result_node_revision_id AND g.origin_record_id=r.record_id
                ORDER BY g.grounding_id) AS data_grounding_ids''' if has_data_groundings else '')
            records = _json(conn.execute('''SELECT r.record_id,r.record_type,r.result_node_revision_id,
                COALESCE(NULLIF(ARRAY(SELECT l.information_id FROM compiler_runtime.k_information_review_records l
                    WHERE l.record_id=r.record_id ORDER BY l.information_id),'{}'::uuid[]),
                    ARRAY(SELECT DISTINCT g.information_id FROM canonical_store.knowledge_node_groundings g
                        WHERE g.node_revision_id=r.result_node_revision_id AND g.origin_record_id=r.record_id
                        ORDER BY g.information_id)) AS information_ids''' + data_columns + '''
                FROM compiler_runtime.k_compilation_records r WHERE r.result_node_revision_id IS NOT NULL
                    AND r.disposition IN ('accepted_new','accepted_revision','reused','no_material_delta')
                ORDER BY r.record_id''').fetchall())
            versions = version_provenance.load(conn)
            data_sources = [{**metadata[owner], 'source_version_status': source_version_status(versions, owner)}
                            for owner in sorted(owners)]
            documents, knowledge = knowledge_projection(graph, units, records, versions, excluded,
                data_sources=data_sources, data_views=list(data_views.values()))
            catalog = archive['catalogs'][selected['catalog_sha256']]
            sources, wiki_items = [], []
            for entry in catalog['papers'].values():
                paper = archive['snapshots'][entry['snapshot_id']]
                packet = archive['source_packets'][paper['source_execution_id']]
                page_numbers = [ref.get('page_index', -1) + 1 for unit in packet['model_input']['information']
                                for ref in unit['source_refs']]
                sources.append({'data_id': paper['data_id'], 'title': paper['title'],
                    'source_execution_id': paper['source_execution_id'], 'page_count': max(page_numbers, default=0),
                    'source_version_status': source_version_status(versions, paper['data_id'])})
                for item in paper['items']:
                    identifier = 'wiki/' + paper['snapshot_id'] + '/' + item['item_key']
                    wiki_items.append({'document_id': identifier, 'page_id': paper['page_id'],
                        'snapshot_id': paper['snapshot_id'], 'data_id': paper['data_id'], 'item': item})
                    documents.append({'document_id': identifier, 'kind': 'wiki',
                        'text': paper['title'] + '\n' + item['text'],
                        'information_ids': sorted({e['information_id'] for e in item['evidence']})})
            documents.extend(information_document(unit) for unit in units.values())
            documents.sort(key=lambda doc: doc['document_id'])
            result = {'schema_version': 'wiki-retrieval-corpus-v1', 'wiki_id': wiki_id,
                'projection_profile': projection_profile(),
                'source_version_snapshot': source_version_snapshot(versions,
                    owners,
                    {version['series_id'] for node in knowledge for route in node['retrieval_support']['records']
                     for version in route['data_versions']}),
                'import_id': selected['request_id'], 'catalog_sha256': selected['catalog_sha256'],
                'knowledge_state_version': graph['state_version'], 'documents': documents,
                'information': list(units.values()), 'knowledge': knowledge, 'wiki_items': wiki_items,
                'sources': sources, 'source_packets': packets, 'review_annotations': selected['review_annotations']}
            if graph.get('epistemic_projection_profile') == edge_projection.PROFILE:
                result['epistemic_projection_profile'] = edge_projection.PROFILE
            if any('effective_edge_premises' in node['retrieval_support'] for node in knowledge):
                result['knowledge_inference_profile'] = knowledge_provenance.EFFECTIVE_INFERENCE_PROFILE
            if include_data_ids is not None:
                result['include_data_ids'] = include_data_ids
            used_views = {grounding['view_id'] for node in knowledge
                         for grounding in node.get('direct_data_groundings', []) + node.get('transitive_data_refs', [])}
            if used_views:
                result.update(data_citations_supported=True, data_sources=data_sources,
                              data_views=[data_views[key] for key in sorted(used_views)])
            return result

    @staticmethod
    def embedding_request(corpus):
        return {'schema_version': 'wiki-embedding-request-v1',
                'documents': [{'document_id': doc['document_id'], 'text': doc['text']} for doc in corpus['documents']]}

    def install(self, index_id, corpus, result):
        index_id = request_id(index_id)
        current = self.corpus(corpus['wiki_id'], include_data_ids=corpus.get('include_data_ids'))
        if current != corpus:
            fail('retrieval_corpus_changed')
        expected = self.embedding_request(corpus)
        if (result.get('schema_version') != 'wiki-embedding-result-v1'
                or result.get('input_sha256') != digest(expected)):
            fail('embedding_input_mismatch')
        profile = result.get('profile', {})
        dimensions = profile.get('dimensions')
        if type(dimensions) is not int or dimensions <= 0 or not profile.get('model_id') or not profile.get('revision'):
            fail('invalid_embedding_profile')
        documents = {doc['document_id']: doc for doc in corpus['documents']}
        seen, chunks = set(), []
        for encoded in result.get('documents', []):
            identifier = encoded.get('document_id')
            if identifier not in documents or identifier in seen:
                fail('embedding_document_mismatch')
            seen.add(identifier)
            text = documents[identifier]['text']
            if encoded.get('text_sha256') != sha256(text.encode()).hexdigest():
                fail('embedding_text_mismatch')
            covered = 0
            prior = -1
            for chunk in encoded.get('chunks', []):
                start, end = chunk.get('char_start'), chunk.get('char_end')
                if (type(start) is not int or type(end) is not int or start < 0 or start <= prior
                        or start > covered or end <= start or end > len(text)):
                    fail('embedding_coverage_gap')
                if chunk.get('text_sha256') != sha256(text[start:end].encode()).hexdigest():
                    fail('embedding_text_mismatch')
                prior, covered = start, max(covered, end)
                value = vector(chunk.get('dense'), dimensions)
                key = digest({'document_id': identifier, 'profile_sha256': digest(profile),
                              'char_start': start, 'char_end': end, 'text_sha256': chunk['text_sha256']})
                chunks.append((index_id, key, identifier, start, end, chunk['text_sha256'], value))
            if covered != len(text):
                fail('embedding_coverage_gap')
        if seen != set(documents):
            fail('embedding_document_mismatch')
        with connection(self.dsn) as conn, conn.transaction():
            self.database._ready(conn)
            # Pin current Wiki and K state across installation; do not create a stale index silently.
            head = conn.execute('SELECT current_import_id FROM wiki_projection.wikis WHERE wiki_id=%s FOR SHARE',
                                (corpus['wiki_id'],)).fetchone()['current_import_id']
            state = conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton FOR SHARE').fetchone()['version']
            if str(head) != corpus['import_id'] or state != corpus['knowledge_state_version']:
                fail('retrieval_corpus_changed')
            if self._source_versions(conn, corpus, lock=True) != corpus['source_version_snapshot']:
                fail('retrieval_corpus_changed')
            old = conn.execute('SELECT corpus_sha256,embedding_result_sha256 FROM wiki_retrieval.indexes WHERE index_id=%s',
                               (index_id,)).fetchone()
            if old:
                if old['corpus_sha256'] != digest(corpus) or old['embedding_result_sha256'] != digest(result):
                    fail('idempotency_conflict')
                return {'index_id': index_id, 'replayed': True}
            conn.execute('''INSERT INTO wiki_retrieval.indexes(index_id,wiki_id,import_id,corpus_sha256,corpus,
                profile_sha256,profile,embedding_result_sha256,document_count,chunk_count)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (index_id, corpus['wiki_id'], corpus['import_id'],
                digest(corpus), Jsonb(corpus), digest(profile), Jsonb(profile), digest(result), len(documents), len(chunks)))
            for values in chunks:
                conn.execute('''INSERT INTO wiki_retrieval.chunks(index_id,chunk_id,document_id,char_start,char_end,
                    text_sha256,embedding) VALUES (%s,%s,%s,%s,%s,%s,%s::vector)''', values)
        return {'index_id': index_id, 'replayed': False, 'documents': len(documents), 'chunks': len(chunks),
                'information': len(corpus['information']), 'profile': profile, 'canonical_writes': 0}

    def index(self, index_id, *, current=True):
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            self.database._ready(conn)
            row = conn.execute('SELECT * FROM wiki_retrieval.indexes WHERE index_id=%s', (request_id(index_id),)).fetchone()
            if row is None:
                fail('retrieval_index_missing')
            result = _json(row)
            if digest(result['corpus']) != result['corpus_sha256'] or digest(result['profile']) != result['profile_sha256']:
                fail('retrieval_index_changed')
            if current:
                head = self.database._head(conn, result['wiki_id'])
                state = conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton').fetchone()['version']
                if head != result['import_id'] or state != result['corpus']['knowledge_state_version']:
                    fail('retrieval_index_stale')
                if (result['corpus'].get('projection_profile') != projection_profile()
                        or result['corpus'].get('source_version_snapshot') != self._source_versions(conn, result['corpus'])):
                    fail('retrieval_index_stale')
            return result

    def search(self, index_id, query, encoded, *, layer='knowledge', limit=24):
        if layer not in ('knowledge', 'information') or type(limit) is not int or not 1 <= limit <= 100:
            fail('invalid_retrieval_window')
        index = self.index(index_id)
        expected = {'schema_version': 'wiki-embedding-request-v1', 'documents': [{'document_id': 'query', 'text': query}]}
        if (encoded.get('schema_version') != 'wiki-embedding-result-v1' or encoded.get('input_sha256') != digest(expected)
                or encoded.get('profile') != index['profile'] or len(encoded.get('documents', [])) != 1):
            fail('query_embedding_mismatch')
        doc = encoded['documents'][0]
        if (doc.get('document_id') != 'query' or doc.get('text_sha256') != sha256(query.encode()).hexdigest()
                or len(doc.get('chunks', [])) != 1 or doc['chunks'][0].get('char_start') != 0
                or doc['chunks'][0].get('char_end') != len(query)):
            fail('query_context_limit')
        if doc['chunks'][0].get('text_sha256') != sha256(query.encode()).hexdigest():
            fail('query_embedding_mismatch')
        values = vector(doc['chunks'][0].get('dense'), index['profile']['dimensions'])
        documents = {d['document_id']: d for d in index['corpus']['documents']
                     if (d['kind'] == 'information') == (layer == 'information')}
        with connection(self.dsn) as conn:
            rows = conn.execute('''SELECT chunk_id,document_id,char_start,char_end,text_sha256,
                1-(embedding <=> %s::vector) AS dense_score FROM wiki_retrieval.chunks
                WHERE index_id=%s AND document_id=ANY(%s::text[])
                ORDER BY embedding <=> %s::vector,chunk_id LIMIT %s''',
                (values, index_id, list(documents), values, limit)).fetchall()
        matches = [{**_json(row), 'text': documents[row['document_id']]['text'][row['char_start']:row['char_end']]}
                   for row in rows]
        rerank = {'schema_version': 'wiki-rerank-request-v1', 'query': query,
                  'passages': [{'chunk_id': row['chunk_id'], 'text': row['text']} for row in matches],
                  'profile': index['profile']}
        return {'index_id': index_id, 'layer': layer, 'query': query, 'matches': matches, 'rerank_request': rerank,
                'search_complete': False, 'note': 'Retrieved candidates only; LLM determines evidence sufficiency.'}
