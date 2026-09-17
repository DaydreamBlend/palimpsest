"""Read-only desktop views over preserved Wiki imports and saved query rounds."""

from base64 import b64encode
from hashlib import sha256 as hash_bytes
import json
import os
from pathlib import Path

from psycopg.conninfo import conninfo_to_dict, make_conninfo

from .artifact_store import _absolute, _directory
from .canonical_store import connection
from .data import data_id as validate_data_id, request_id
from .errors import PalimpsestError
from .i2k import digest
from .knowledge_runtime import KnowledgeRuntime, _json
from .knowledge_review import KnowledgeReview, review_status
from . import knowledge_provenance, version_provenance, edge_projection
from .paper_wiki_runtime import _image_suffix
from .wiki_archive import validate_archive_files
from .wiki_database import WikiDatabase
from .wiki_projection_store import _read, _json_bytes, _MARKER, _PROFILE
from .wiki_query import render_answer


def _fail(code='invalid_desktop_request'):
    raise PalimpsestError(code, '문서·원문 소유권과 저장된 조회 이력을 확인하세요.', 2)


class DesktopReadService:
    """No migrations, provider calls, lock files, or canonical write operations."""

    def __init__(self, dsn, artifact_root, wiki_id=None, query_directory=None, *, include_data_ids=None):
        options = conninfo_to_dict(dsn).get('options', '')
        self.dsn = make_conninfo(dsn, options=options + ' -c default_transaction_read_only=on')
        self.database = WikiDatabase(self.dsn, artifact_root)
        self.wiki_id = request_id(wiki_id) if wiki_id is not None else None
        self.query_root = _absolute(Path(query_directory)) if query_directory is not None else None
        self._archives = {}
        if include_data_ids is not None and not isinstance(include_data_ids, (list, tuple)):
            _fail('invalid_desktop_data_scope')
        self.include_data_ids = sorted({validate_data_id(value) for value in include_data_ids or []})
        if len(self.include_data_ids) != len(include_data_ids or []):
            _fail('invalid_desktop_data_scope')

    def dispatch(self, request):
        fields = {
            'catalog': set(), 'page': {'page_id', 'snapshot_id'},
            'information': {'information_id', 'source_execution_id'},
            'queries': set(), 'query': {'query_id'},
            'artifact': {'kind', 'data_id', 'sha256', 'source_execution_id'},
            'knowledge_catalog': set(), 'knowledge_node': {'node_revision_id'},
            'review_catalog': set(), 'review_status': {'execution_id'},
            'data_grounding': {'grounding_id'},
        }
        if (not isinstance(request, dict) or not isinstance(request.get('operation'), str)
                or request['operation'] not in fields):
            _fail()
        operation = request['operation']
        if set(request) - {'operation'} - fields[operation]:
            _fail()
        try:
            return getattr(self, operation)(**{k: v for k, v in request.items() if k != 'operation'})
        except TypeError:
            _fail()

    def _archive(self, import_id):
        # ponytail: immutable import cache; add bounded eviction if a session opens many imports.
        if import_id not in self._archives:
            with connection(self.dsn) as conn, conn.transaction():
                conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                self.database._ready(conn)
                self.database._import(conn, self.wiki_id, import_id)
                rows = conn.execute('''SELECT f.path,b.content FROM wiki_projection.files f
                    JOIN wiki_projection.blobs b ON b.sha256=f.raw_sha256
                    WHERE f.request_id=%s''', (import_id,)).fetchall()
                archive = validate_archive_files({row['path']: bytes(row['content']) for row in rows})
                for packet in archive['source_packets'].values():
                    KnowledgeRuntime._verify_i(conn, packet['data_id'], packet)
                self._archives[import_id] = archive
        return self._archives[import_id]

    def catalog(self):
        selected = self.database.catalog(self.wiki_id)
        archive = self._archive(selected['import_id'])
        pages = []
        for collection in ('papers', 'topics'):
            for entry in selected['catalog'][collection].values():
                page = archive['snapshots'][entry['snapshot_id']]
                summary = {key: page[key] for key in
                           ('page_id', 'snapshot_id', 'kind', 'title', 'data_id', 'topic_key', 'scope') if key in page}
                if page['kind'] == 'paper':
                    packet = archive['source_packets'][page['source_execution_id']]
                    summary.update(source_execution_id=page['source_execution_id'],
                                   information_count=len(packet['model_input']['information']),
                                   source_format=packet['model_input'].get('source_format', 'pdf'))
                summary['source_data_ids'] = ([page['data_id']] if page['kind'] == 'paper' else
                    sorted({item['paper_data_id'] for item in page['contributions']}))
                pages.append(summary)
        return {**selected, 'pages': pages, 'read_only': True}

    def page(self, page_id, snapshot_id=None):
        page_id = request_id(page_id)
        snapshot_id = request_id(snapshot_id) if snapshot_id is not None else None
        history = self.database.history(self.wiki_id, page_id)
        page = next((item for item in history['snapshots']
                     if snapshot_id is None or item['snapshot_id'] == snapshot_id), None)
        if page is None:
            _fail('wiki_page_snapshot_not_found')
        selected_import = history['import_id']
        if page['snapshot_id'] != history['snapshots'][0]['snapshot_id']:
            with connection(self.dsn) as conn:
                rows = conn.execute('''SELECT i.request_id,c.payload FROM wiki_projection.imports i
                    JOIN wiki_projection.catalogs c ON c.wiki_id=i.wiki_id
                        AND c.catalog_sha256=i.catalog_sha256
                    WHERE i.wiki_id=%s ORDER BY i.created_at DESC''', (self.wiki_id,)).fetchall()
            selected_import = next((str(row['request_id']) for row in rows if any(
                item['snapshot_id'] == page['snapshot_id'] for collection in ('papers', 'topics')
                for item in row['payload'][collection].values())), None)
        related = (self.database.related(self.wiki_id, page_id, import_id=selected_import)
                   if selected_import else {'links': [], 'review_required_links': 0,
                       'relation': 'shared_source_evidence', 'semantic_support_validated': False,
                       'unavailable_reason': 'snapshot_has_no_import_checkpoint'})
        topic_sources = []
        if page['kind'] == 'topic':
            archive = self._archive(history['import_id'])
            matching_catalogs = [catalog for catalog in archive['catalogs'].values() if any(
                entry['snapshot_id'] == page['snapshot_id'] for entry in catalog['topics'].values())]
            if not matching_catalogs:
                _fail('wiki_database_snapshot_changed')
            catalog = matching_catalogs[0]
            topic_sources = [{'data_id': c['paper_data_id'], 'page_id': c['paper_page_id'],
                              'snapshot_id': catalog['papers'][c['paper_data_id']]['snapshot_id']}
                             for c in page['contributions']]
        if page['kind'] == 'paper':
            page = {**page, 'source_format': self._packet(page['source_execution_id'])['model_input'].get('source_format', 'pdf')}
        return {'page': page, 'import_id': selected_import, 'current_snapshot_id': history['snapshots'][0]['snapshot_id'],
                'topic_sources': topic_sources,
                'history': [{key: item[key] for key in ('snapshot_id', 'title', 'kind', 'previous_snapshot_id',
                            'source_execution_id', 'data_id') if key in item} for item in history['snapshots']],
                'related': related, 'canonical': False}

    def _packets(self):
        selected = self.database.catalog(self.wiki_id)
        return self._archive(selected['import_id'])['source_packets'].values()

    def _packet(self, source_execution_id):
        identifier = request_id(source_execution_id)
        packet = next((p for p in self._packets() if p['source_execution_id'] == identifier), None)
        if packet is None:
            owners = {packet['data_id'] for packet in self._packets()}
            with connection(self.dsn) as conn:
                source = conn.execute("SELECT data_id,state,operation FROM compiler_runtime.operation_executions WHERE execution_id=%s",
                                      (identifier,)).fetchone()
            if source is None or source['data_id'] not in owners or source['operation'] != 'd2i' or source['state'] != 'completed':
                _fail('desktop_source_not_in_wiki')
            packet = self.database.source.prepare_input(identifier)
        return packet

    def information(self, information_id, source_execution_id):
        identifier = request_id(information_id)
        packet = self._packet(source_execution_id)
        unit = next((u for u in packet['model_input']['information'] if u['information_id'] == identifier), None)
        if unit is None:
            _fail('desktop_information_owner_mismatch')
        registered = self.database.source.data.get_data(packet['data_id'])
        if registered is None:
            _fail('desktop_original_missing')
        return {**unit, 'data_id': packet['data_id'], 'source_execution_id': packet['source_execution_id'],
                'source_format': packet['model_input'].get('source_format', 'pdf'),
                'original': {'sha256': packet['data_id'], 'media_type': registered['media_type'],
                             'byte_size': registered['byte_size']}}

    def _knowledge_scope(self):
        if self.wiki_id is None:
            with connection(self.dsn) as conn, conn.transaction():
                conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                owners = [row['data_id'] for row in conn.execute(
                    ('SELECT data_id FROM canonical_store.data WHERE data_id=ANY(%s::text[]) ORDER BY data_id'
                     if self.include_data_ids else 'SELECT data_id FROM canonical_store.data ORDER BY data_id'),
                    (self.include_data_ids,) if self.include_data_ids else ()).fetchall()]
                if self.include_data_ids and set(owners) != set(self.include_data_ids):
                    _fail('desktop_data_not_registered')
            return [], owners
        packets = list(self._packets())
        if self.include_data_ids:
            with connection(self.dsn) as conn:
                registered = {row['data_id'] for row in conn.execute(
                    'SELECT data_id FROM canonical_store.data WHERE data_id=ANY(%s::text[])',
                    (self.include_data_ids,)).fetchall()}
            if registered != set(self.include_data_ids):
                _fail('desktop_data_not_registered')
        return packets, sorted({packet['data_id'] for packet in packets} | set(self.include_data_ids))

    @staticmethod
    def _allowed_knowledge(conn, revision, owners):
        function = conn.execute("SELECT to_regprocedure('canonical_store.k_revision_supported_by_version_data(uuid,text[],uuid[])') AS name").fetchone()['name']
        if function:
            # This detail view exposes the full historical origin/support graph,
            # so one in-library alternative alone is not enough for disclosure.
            outside = conn.execute('''SELECT EXISTS(SELECT 1 FROM canonical_store.derivation_source_data(%s) s(data_id)
                    WHERE NOT s.data_id=ANY(%s::text[])) OR EXISTS(
                SELECT 1 FROM compiler_runtime.k_compilation_records r
                JOIN compiler_runtime.k_execution_data_versions x USING(execution_id)
                JOIN canonical_store.data_versions v USING(version_id)
                WHERE r.result_node_revision_id=%s AND NOT v.data_id=ANY(%s::text[])) AS outside''',
                (revision, owners, revision, owners)).fetchone()['outside']
            if outside:
                return False
            return conn.execute('SELECT canonical_store.k_revision_supported_by_version_data(%s,%s) AS allowed',
                                (revision, owners)).fetchone()['allowed']
        # Legacy databases have direct source Knowledge only. Never expose a
        # claim unless all of its recorded source Data belong to this library.
        data = conn.execute('''SELECT DISTINCT i.data_id FROM canonical_store.knowledge_node_groundings g
            JOIN canonical_store.information i USING(information_id) WHERE node_revision_id=%s''', (revision,)).fetchall()
        return bool(data) and {row['data_id'] for row in data} <= set(owners)

    def knowledge_catalog(self):
        packets, owners = self._knowledge_scope()
        graph = KnowledgeRuntime(self.dsn).graph()
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            nodes = [node for node in graph['nodes']
                if (set(node.get('source_data_ids', [])) | set(node.get('grounding_data_ids', []))) & set(owners)
                and self._allowed_knowledge(conn, node['knode_revision_id'], owners)]
            versions = version_provenance.load(conn)
        fields = ('knode_id', 'knode_revision_id', 'kind', 'statement', 'generation_origin',
                  'source_version_status', 'current_applicability', 'source_data_id', 'origin_data_versions',
                  'epistemic_projection')
        summaries = [{**{key: node[key] for key in fields if key in node},
            'source_data_ids': node.get('source_data_ids', node.get('grounding_data_ids', []))} for node in nodes]
        sources = [{'data_id': packet['data_id'], 'source_execution_id': packet['source_execution_id'],
                    'source_format': packet['model_input'].get('source_format', 'pdf')}
                   for packet in packets]
        sources.extend({'data_id': owner, 'source_format': 'original_data', 'source_execution_id': None}
                       for owner in owners if owner not in {source['data_id'] for source in sources})
        data_versions = [] if versions is None else [{**version,
            'is_head': versions['heads'].get(version['series_id']) == version['version_id']}
            for version in versions['versions'].values() if version['data_id'] in owners]
        return {'nodes': summaries, 'sources': sources, 'data_versions': data_versions, 'read_only': True}

    def knowledge_node(self, node_revision_id):
        revision = request_id(node_revision_id)
        _, owners = self._knowledge_scope()
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            if not self._allowed_knowledge(conn, revision, owners):
                _fail('desktop_knowledge_not_in_wiki')
            node = _json(conn.execute('''SELECT r.*,n.kind,n.current_revision_id,s.identity_scope,s.source_data_id
                FROM canonical_store.knowledge_node_revisions r
                JOIN canonical_store.knowledge_nodes n USING(knode_id)
                LEFT JOIN canonical_store.knowledge_node_scopes s USING(knode_id)
                WHERE knode_revision_id=%s''', (revision,)).fetchone())
            if node is None:
                _fail('desktop_knowledge_not_in_wiki')
            provenance = knowledge_provenance.load(conn)
            if provenance is not None:
                node.update(knowledge_provenance.describe(provenance, revision))
            explicit = conn.execute('SELECT * FROM compiler_runtime.k_explicit_source_decisions WHERE record_id=%s',
                                    (node['origin_record_id'],)).fetchone()
            if explicit:
                node['generation_origin'] = {'origin_operation': 'i2k', 'is_inferred': False,
                    'claim_basis': 'explicit_source_content', 'origin_record_id': node['origin_record_id'],
                    'validation': _json(explicit)}
            versions = version_provenance.load(conn)
            node.update(version_provenance.annotate(versions, node))
            node.update(version_provenance.graph_view(versions, node))
            node['is_current_revision'] = node['current_revision_id'] == revision
            if node['is_current_revision']:
                current_nodes = KnowledgeRuntime._nodes(conn)
                relations = edge_projection.resolve(conn, current_nodes, KnowledgeRuntime._edges(conn))
                annotated = edge_projection.derive_contested(current_nodes, relations)
                projected = next((item for item in annotated if item['knode_revision_id'] == revision), None)
                if projected is not None:
                    node['epistemic_projection'] = projected['epistemic_projection']
                    node['epistemic_projection_scope'] = 'current_graph'
            direct = _json(conn.execute('''SELECT g.*,i.data_id,r.execution_id AS source_execution_id
                FROM canonical_store.knowledge_node_groundings g JOIN canonical_store.information i USING(information_id)
                JOIN compiler_runtime.records r ON r.record_id=i.origin_record_id WHERE g.node_revision_id=%s
                ORDER BY g.grounding_id''', (revision,)).fetchall())
            node['direct_groundings'] = [row for row in direct if row['data_id'] in owners]
            transitive = [row for row in node.get('transitive_source_refs', []) if row.get('data_id') in owners]
            node['transitive_source_refs'] = transitive
            evidence, seen = [], set()
            for basis, rows in (('direct', node['direct_groundings']), ('transitive', transitive)):
                for row in rows:
                    source = conn.execute('''SELECT i.data_id,r.execution_id FROM canonical_store.information i
                        JOIN compiler_runtime.records r ON r.record_id=i.origin_record_id WHERE i.information_id=%s''',
                        (row['information_id'],)).fetchone()
                    if source is None or source['data_id'] not in owners:
                        continue
                    key = (row['information_id'], row['char_start'], row['char_end'], row.get('media_sha256'))
                    if key in seen:
                        continue
                    seen.add(key)
                    evidence.append({**row, 'data_id': source['data_id'],
                        'source_execution_id': str(source['execution_id']), 'evidence_basis': basis})
            refs = list(dict.fromkeys(ref for derivation in node.get('derivations', []) for ref in derivation['premise_revision_ids']))
            premise_edges = [{'record_id': derivation['record_id'], **edge}
                for derivation in node.get('derivations', []) for edge in derivation.get('effective_edge_premises', [])]
            edge_endpoints = {edge['effective_edge_ref'][key] for edge in premise_edges
                for key in ('from_knode_revision_id', 'to_knode_revision_id')}
            if not edge_endpoints <= set(refs):
                _fail('desktop_inference_endpoint_missing')
            if any(not self._allowed_knowledge(conn, ref, owners) for ref in refs):
                _fail('desktop_knowledge_not_in_wiki')
            premises = _json(conn.execute('''SELECT r.knode_revision_id,r.knode_id,r.statement,n.kind
                FROM canonical_store.knowledge_node_revisions r JOIN canonical_store.knowledge_nodes n USING(knode_id)
                WHERE r.knode_revision_id=ANY(%s::uuid[]) ORDER BY r.knode_revision_id''', (refs,)).fetchall()) if refs else []
        data_evidence = [{**row, 'evidence_basis': basis}
            for basis, rows in (('direct', node.get('direct_data_groundings', [])),
                                ('transitive', node.get('transitive_data_refs', []))) for row in rows]
        return {'node': node, 'premise_nodes': premises, 'evidence': evidence,
                **({'premise_edges': premise_edges} if premise_edges else {}),
                **({'data_evidence': data_evidence} if data_evidence else {}), 'read_only': True}

    def data_grounding(self, grounding_id):
        identifier = request_id(grounding_id)
        _, owners = self._knowledge_scope()
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            if conn.execute("SELECT to_regclass('canonical_store.knowledge_data_groundings') AS relation").fetchone()['relation'] is None:
                _fail('desktop_data_grounding_missing')
            row = _json(conn.execute('''SELECT g.*,v.body AS view,v.preparation_id
                FROM canonical_store.knowledge_data_groundings g
                JOIN compiler_runtime.d2k_source_views v USING(view_id) WHERE grounding_id=%s''',
                (identifier,)).fetchone())
            if row is None or row['data_id'] not in owners or not self._allowed_knowledge(conn, row['node_revision_id'], owners):
                _fail('desktop_data_grounding_not_in_scope')
        registered = self.database.source.data.get_data(row['data_id'])
        if registered is None:
            _fail('desktop_original_missing')
        view = row['view']
        raw = self.database.source.store.read(row['data_id'], registered['byte_size'])
        image = (self.database.source.derived.read(view['image_sha256'], view['image_byte_size'])
                 if view['kind'] == 'pdf_page' else None)
        grounding, view = knowledge_provenance.verify_data_grounding(row, view, raw, image=image)
        result = {'grounding': grounding, 'view': view, 'preparation_id': row['preparation_id'],
            'source_info': None, 'media_kind': 'pdf' if image is not None else 'text',
            'original': {'sha256': row['data_id'], 'byte_size': registered['byte_size'],
                         'media_type': registered['media_type']}, 'read_only': True}
        if image is not None:
            if len(image) > 50 * 1024 * 1024:
                _fail('desktop_artifact_too_large')
            result['image'] = {'sha256': view['image_sha256'], 'byte_size': len(image),
                              'media_type': 'image/png', 'base64': b64encode(image).decode('ascii')}
        return result

    def _review_owned(self, job, owners):
        packet = job['input_snapshot']['input']
        return (job['operation'] == 'i2k' and bool(packet.get('model_input', {}).get('information'))
                and {row['data_id'] for row in packet.get('sources', [packet])} <= set(owners))

    def review_catalog(self):
        _, owners = self._knowledge_scope()
        with connection(self.dsn) as conn:
            identifiers = conn.execute('''SELECT c.execution_id FROM compiler_runtime.k_execution_contexts c
                JOIN compiler_runtime.operation_executions e USING(execution_id)
                WHERE e.operation='i2k' AND e.data_id=ANY(%s::text[]) ORDER BY e.execution_id DESC''', (owners,)).fetchall()
        runtime, results = KnowledgeRuntime(self.dsn), []
        for row in identifiers:
            job = runtime.show(str(row['execution_id']))
            if not self._review_owned(job, owners) or job['profile']['schema_version'] not in ('source-complete-i2k-v1', 'multi-source-explicit-i2k-v1'):
                continue
            reviewed = review_status(job)
            results.append({key: reviewed[key] for key in ('execution_id', 'state', 'data_id')} | {
                'operation': 'i2k', 'review_action': reviewed['next_action'],
                'pending_information_count': len(reviewed['pending_information_ids']),
                'pending_target_count': len(reviewed['pending_target_ids']),
                'pending_item_count': len(reviewed['pending_item_keys']),
                'source_data_ids': sorted({source['data_id'] for source in reviewed['sources']}),
                'version_ids': [version['version_id'] for version in reviewed['data_versions']]})
        return {'executions': results, 'read_only': True}

    def review_status(self, execution_id):
        identifier = request_id(execution_id)
        _, owners = self._knowledge_scope()
        runtime = KnowledgeRuntime(self.dsn)
        job = runtime.show(identifier)
        if not self._review_owned(job, owners):
            _fail('desktop_review_not_in_wiki')
        result = KnowledgeReview(runtime).status(identifier)
        # The UI needs review events and refs, not copies of every old model input.
        for item in [result, *result['history']]:
            item.pop('selection_feedback', None)
        return {**result, 'read_only': True}

    def artifact(self, kind, data_id, sha256=None, source_execution_id=None):
        identifier = validate_data_id(data_id)
        media_id = validate_data_id(sha256) if sha256 is not None else identifier
        if kind not in ('original', 'image'):
            _fail()
        packets = ([self._packet(source_execution_id)] if source_execution_id is not None else self._packets())
        packets = [packet for packet in packets if packet['data_id'] == identifier]
        if not packets:
            _fail('desktop_source_not_in_wiki')
        if kind == 'original':
            if media_id != identifier:
                _fail('desktop_original_hash_mismatch')
            metadata = self.database.source.data.get_data(identifier)
            if metadata is None:
                _fail('desktop_original_missing')
            byte_size, media_type = metadata['byte_size'], metadata['media_type']
            store = self.database.source.store
        else:
            owned = [media for packet in packets for unit in packet['model_input']['information']
                     for media in unit['media'] if media['sha256'] == media_id]
            if not owned or len({media['byte_size'] for media in owned}) != 1:
                _fail('desktop_artifact_owner_mismatch')
            byte_size, media_type = owned[0]['byte_size'], None
            store = self.database.source.derived
        if byte_size > 50 * 1024 * 1024:
            _fail('desktop_artifact_too_large')
        raw = store.read(media_id, byte_size)
        if hash_bytes(raw).hexdigest() != media_id:
            _fail('desktop_artifact_changed')
        if kind == 'image':
            media_type = {'.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp'}[_image_suffix(raw)]
        if media_type == 'application/pdf' and b'%PDF-' not in raw[:1024]:
            _fail('desktop_original_hash_mismatch')
        return {'sha256': media_id, 'data_id': identifier, 'media_type': media_type,
                'byte_size': byte_size, 'base64': b64encode(raw).decode('ascii')}

    def _query_file(self, relative, *, optional=False):
        """Descriptor-based reads reuse the cache's no-symlink and stable-byte guards."""
        path = self.query_root / relative
        try:
            with _directory(self.query_root) as root:
                if _read(root, _MARKER) != _json_bytes(_PROFILE):
                    _fail('wiki_projection_unmanaged_root')
            with _directory(path.parent) as parent:
                raw = _read(parent, path.name)
            return json.loads(raw)
        except FileNotFoundError:
            if optional:
                return None
            _fail('wiki_query_missing')
        except (UnicodeError, ValueError):
            _fail('wiki_query_file_invalid')

    def _job(self, query_id):
        identifier = request_id(query_id)
        job = self._query_file(f'queries/{identifier}/job.json')
        if (not isinstance(job, dict) or job.get('query_id') != identifier or job.get('wiki_id') != self.wiki_id
                or job.get('schema_version') != 'wiki-query-run-v1'
                or type(job.get('round')) is not int or job['round'] < 0
                or job.get('request_sha256') != digest({'index_id': job.get('index_id'), 'question': job.get('question')})):
            _fail('wiki_query_request_changed')
        with connection(self.dsn) as conn:
            row = conn.execute("SELECT wiki_id,import_id,corpus->'include_data_ids' AS include_data_ids FROM wiki_retrieval.indexes WHERE index_id=%s",
                               (request_id(job['index_id']),)).fetchone()
        if row is None or str(row['wiki_id']) != self.wiki_id or str(row['import_id']) != job.get('import_id'):
            _fail('wiki_query_index_binding_mismatch')
        if row.get('include_data_ids'):
            _, owners = self._knowledge_scope()
            if not set(row['include_data_ids']) <= set(owners):
                _fail('desktop_query_data_not_in_scope')
        return job

    @staticmethod
    def _summary(job):
        return {key: job[key] for key in ('query_id', 'question', 'state', 'round', 'layer', 'wiki_id', 'import_id',
                                        'index_id', 'request_sha256', 'context_sha256',
                                        'attention_reason', 'paused_state', 'source_requests') if key in job}

    def queries(self):
        try:
            with _directory(self.query_root / 'queries') as folder:
                names = sorted(os.listdir(folder), reverse=True)
        except FileNotFoundError:
            return {'queries': [], 'issues': []}
        queries, issues = [], []
        for name in names:
            try:
                request_id(name)
            except PalimpsestError:
                continue
            try:
                job = self._job(name)
                summary = self._summary(job)
                with connection(self.dsn) as conn:
                    row = conn.execute("SELECT corpus->'source_packets' AS packets FROM wiki_retrieval.indexes WHERE index_id=%s",
                        (job['index_id'],)).fetchone()
                summary['source_data_ids'] = sorted({packet['data_id'] for packet in row['packets']})
                queries.append(summary)
            except (PalimpsestError, OSError) as error:
                issues.append({'query_id': name, 'error_code': getattr(error, 'code', 'storage_error')})
        return {'queries': queries, 'issues': issues}

    def query(self, query_id):
        job = self._job(query_id)
        identifier = job['query_id']
        rounds = []
        for number in range(job['round'] + 1):
            root = f'queries/{identifier}/rounds/{number}'
            proposal = self._query_file(root + '/proposal.json', optional=True)
            validation = self._query_file(root + '/validation.json', optional=True)
            if proposal is not None and any(proposal.get(k) != v for k, v in {
                'query_id': identifier, 'wiki_id': self.wiki_id, 'import_id': job['import_id'],
                'index_id': job['index_id'], 'question': job['question'], 'round': number}.items()):
                _fail('wiki_query_answer_changed')
            if validation is not None:
                if proposal is None:
                    _fail('wiki_query_answer_changed')
                render_answer(proposal, validation)
            failures = []
            try:
                with _directory(self.query_root / root / 'failures') as folder:
                    names = sorted(os.listdir(folder))
                for name in names:
                    if len(name) == 69 and name.endswith('.json'):
                        validate_data_id(name[:-5])
                        failures.append(self._query_file(root + '/failures/' + name))
            except FileNotFoundError:
                pass
            rounds.append({'round': number, 'proposal': proposal, 'validation': validation,
                           'failures': failures, 'attention': self._query_file(root + '/attention.json', optional=True)})
        latest = rounds[-1]
        accepted = (job['state'] == 'answered' and latest['validation'] is not None
                    and latest['validation']['verdict'] == 'accepted')
        return {'job': self._summary(job), 'proposal': latest['proposal'], 'validation': latest['validation'],
                'answer': render_answer(latest['proposal'], latest['validation']) if accepted else None,
                'accepted': accepted, 'rounds': rounds, 'canonical': False}
