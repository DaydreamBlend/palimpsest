"""Transactional PostgreSQL selection of preserved, noncanonical Wiki snapshots."""

from hashlib import sha256
from importlib.resources import files
import json
from pathlib import Path

from psycopg import sql
from psycopg.types.json import Jsonb

from .canonical_store import connection, migration_source, MIGRATIONS
from .compiler_runtime import CompilerRuntime
from .data import data_id, request_id
from .errors import PalimpsestError
from .i2k import digest
from .knowledge_runtime import KnowledgeRuntime, _json
from .paper_wiki_runtime import PaperWikiRuntime, _image_suffix
from .wiki_archive import build_archive, validate_archive_files
from .wiki_knowledge_links import build_related_links
from .wiki_projection_store import ProjectionStore
from . import edge_projection


PROFILE = 'wiki-postgres-projection-v1'


def _fail(code, status=6):
    raise PalimpsestError(code, 'Wiki DB의 요청·현재 checkpoint·원문/Revision 연결을 확인하세요.', status)


def _immutable(conn, table, values, keys):
    """Reuse identical rows; never turn ON CONFLICT into an overwrite."""
    columns = list(values)
    relation = sql.Identifier('wiki_projection', table)
    conn.execute(sql.SQL('INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO NOTHING').format(
        relation, sql.SQL(',').join(map(sql.Identifier, columns)),
        sql.SQL(',').join(sql.Placeholder() for _ in columns),
        sql.SQL(',').join(map(sql.Identifier, keys))),
        [Jsonb(value) if isinstance(value, (dict, list)) else value for value in values.values()])
    row = conn.execute(sql.SQL('SELECT {} FROM {} WHERE {}').format(
        sql.SQL(',').join(map(sql.Identifier, columns)), relation,
        sql.SQL(' AND ').join(sql.SQL('{}=%s').format(sql.Identifier(key)) for key in keys)),
        [values[key] for key in keys]).fetchone()
    if row is None or any((bytes(row[key]) if isinstance(value, bytes) else _json(row[key])) != value
                          for key, value in values.items()):
        _fail('wiki_database_identity_conflict')


class WikiDatabase:
    def __init__(self, dsn, artifact_root):
        self.dsn = dsn
        self.artifact_root = Path(artifact_root)
        self.source = CompilerRuntime(dsn, artifact_root)

    @staticmethod
    def _ready(conn):
        version = conn.execute("SELECT current_setting('server_version_num')::integer AS version").fetchone()['version']
        extension = conn.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()
        if version // 10000 != 18 or extension is None or extension['extversion'] != '0.8.6':
            _fail('wiki_database_profile_mismatch', 3)
        present = conn.execute("SELECT to_regclass('wiki_projection.imports') AS name").fetchone()['name']
        if present is None:
            _fail('wiki_database_not_initialized', 3)
        installed = conn.execute('SELECT version,checksum FROM compiler_runtime.schema_migrations ORDER BY version').fetchall()
        expected = [{'version': name, 'checksum': migration_source(name)[1]} for name in MIGRATIONS]
        if installed != expected:
            # Historical reads may use these verified prefixes; writes still need every migration.
            supported_prefix = (bool(installed) and installed[-1]['version'] in
                ('0010_wiki_retrieval', '0013_data_versions', '0014_user_requested_d2k', '0015_explicit_knowledge_revision',
                 '0016_propagation_worker', '0017_n2e_relations', '0018_n2e_review_agreement', '0019_n2e_effect_fence',
                 '0020_effective_k2k', '0021_wisdom', '0022_parchment')
                and installed == expected[:len(installed)])
            if (not supported_prefix or
                    conn.execute('SHOW transaction_read_only').fetchone()['transaction_read_only'] != 'on'):
                _fail('wiki_database_schema_mismatch', 3)

    @staticmethod
    def _head(conn, wiki_id):
        row = conn.execute('SELECT current_import_id FROM wiki_projection.wikis WHERE wiki_id=%s',
                           (wiki_id,)).fetchone()
        if row is None:
            _fail('wiki_database_not_found', 2)
        return str(row['current_import_id']) if row['current_import_id'] else None

    @staticmethod
    def _import(conn, wiki_id, identifier=None):
        identifier = identifier or WikiDatabase._head(conn, wiki_id)
        row = conn.execute('SELECT * FROM wiki_projection.imports WHERE request_id=%s AND wiki_id=%s',
                           (identifier, wiki_id)).fetchone()
        if row is None:
            _fail('wiki_database_import_not_found', 2)
        return _json(row)

    @staticmethod
    def _graph(conn, information_ids):
        # K writers advance this same row before committing. Keep one read set
        # through the Wiki transaction without editing any canonical K state.
        state = conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton FOR SHARE').fetchone()['version']
        accepted = {str(row['record_id']): row for row in conn.execute('''SELECT record_id,disposition,
            result_node_id,result_node_revision_id FROM compiler_runtime.k_compilation_records
            WHERE disposition IN ('accepted_new','accepted_revision')''').fetchall()}
        nodes = [node for node in KnowledgeRuntime._nodes(conn) if node['origin_record_id'] in accepted
                 and str(accepted[node['origin_record_id']]['result_node_revision_id']) == node['knode_revision_id']
                 and str(accepted[node['origin_record_id']]['result_node_id']) == node['knode_id']]
        origins = {str(row['record_id']): _json(row) for row in conn.execute('''SELECT record_id,
            source_explicit,no_novel_inference,source_identity_preserved
            FROM compiler_runtime.k_explicit_source_decisions''').fetchall()}
        for node in nodes:
            node['record_disposition'] = accepted[node['origin_record_id']]['disposition']
            if node['origin_record_id'] in origins:
                node['generation_origin'] = {'origin_operation': 'i2k', 'is_inferred': False,
                    'claim_basis': 'explicit_source_content', 'origin_record_id': node['origin_record_id'],
                    'validation': origins[node['origin_record_id']]}
        relations = edge_projection.resolve(conn, nodes, KnowledgeRuntime._edges(conn))
        nodes = edge_projection.derive_contested(nodes, relations)
        groundings = _json(conn.execute('''SELECT g.*,i.data_id
            FROM canonical_store.knowledge_node_groundings g JOIN canonical_store.information i USING(information_id)
            WHERE g.information_id=ANY(%s::uuid[]) ORDER BY g.grounding_id''', (list(information_ids),)).fetchall())
        return {'schema_version': 'knowledge-graph-v1', 'state_version': state,
                'nodes': nodes, 'groundings': groundings,
                'epistemic_projection_profile': edge_projection.PROFILE,
                'binding_profile': {'schema_version': PROFILE, 'implementation': {
                    name: sha256(files('palimpsest').joinpath(name).read_text(encoding='utf-8').encode()).hexdigest()
                    for name in ('wiki_database.py', 'wiki_knowledge_links.py', 'edge_projection.py')}}}

    @staticmethod
    def _verify_graph_groundings(graph, units):
        for grounding in graph['groundings']:
            unit = units[grounding['information_id']]
            start, end = grounding['char_start'], grounding['char_end']
            if (grounding['data_id'] != unit['data_id'] or not 0 <= start <= end <= len(unit['content'])
                    or grounding['quote'] != unit['content'][start:end]
                    or (grounding['media_sha256'] is not None and grounding['media_sha256'] not in {
                        media['sha256'] for media in unit['media']})):
                _fail('wiki_database_knowledge_source_changed')

    def sync(self, wiki_id, identifier, directory, *, expected_head=None, review_annotations=None, checkpoint=None,
             transaction_guard=None):
        archive = build_archive(ProjectionStore(Path(directory)))
        return self.import_archive(wiki_id, identifier, archive, expected_head=expected_head,
                                   review_annotations=review_annotations, checkpoint=checkpoint,
                                   transaction_guard=transaction_guard)

    def import_archive(self, wiki_id, identifier, archive, *, expected_head=None,
                       review_annotations=None, checkpoint=None, transaction_guard=None):
        wiki_id, identifier = request_id(wiki_id), request_id(identifier)
        expected_head = request_id(expected_head) if expected_head else None
        # Revalidate caller-supplied parsed data against the actual archived bytes.
        archive = validate_archive_files(archive['files'])
        annotations = [] if review_annotations is None else review_annotations
        if not isinstance(annotations, list):
            _fail('invalid_wiki_review_annotations', 2)
        request = {'schema_version': PROFILE, 'wiki_id': wiki_id, 'expected_head': expected_head,
                   'manifest_sha256': archive['manifest_sha256'],
                   'catalog_sha256': archive['current_catalog_sha256'], 'review_annotations': annotations}
        fingerprint = digest(request)
        with connection(self.dsn) as conn, conn.transaction():
            self._ready(conn)
            if transaction_guard:
                transaction_guard(conn)
            previous = conn.execute('SELECT wiki_id,request_fingerprint,result FROM wiki_projection.imports WHERE request_id=%s',
                                    (identifier,)).fetchone()
            if previous:
                if str(previous['wiki_id']) != wiki_id or previous['request_fingerprint'] != fingerprint:
                    _fail('idempotency_conflict')
                return {**previous['result'], 'replayed': True}
            conn.execute('INSERT INTO wiki_projection.wikis(wiki_id) VALUES (%s) ON CONFLICT DO NOTHING', (wiki_id,))
            row = conn.execute('SELECT current_import_id FROM wiki_projection.wikis WHERE wiki_id=%s FOR UPDATE',
                               (wiki_id,)).fetchone()
            head = str(row['current_import_id']) if row['current_import_id'] else None
            # Recheck after a simultaneous first import has released the Wiki row.
            previous = conn.execute('SELECT request_fingerprint,result FROM wiki_projection.imports WHERE request_id=%s',
                                    (identifier,)).fetchone()
            if previous:
                if previous['request_fingerprint'] != fingerprint:
                    _fail('idempotency_conflict')
                return {**previous['result'], 'replayed': True}
            if head != expected_head:
                _fail('wiki_database_head_changed')
            current = archive['catalogs'][archive['current_catalog_sha256']]
            if head:
                old = self._import(conn, wiki_id, head)
                old_catalog = conn.execute('SELECT payload FROM wiki_projection.catalogs WHERE wiki_id=%s AND catalog_sha256=%s',
                                           (wiki_id, old['catalog_sha256'])).fetchone()['payload']
                if (current['version'] < old_catalog['version']
                        or any(current['commits'].get(key) != value for key, value in old_catalog['commits'].items())
                        or (current['version'] == old_catalog['version'] and current != old_catalog)):
                    _fail('wiki_database_catalog_regression')
                # Review notes concern exact revisions. A routine refresh must
                # not silently drop an unresolved note when no file is supplied.
                annotations = list({digest(note): note for note in
                                    [*old['review_annotations'], *annotations]}.values())
            units = {}
            for packet in archive['source_packets'].values():
                KnowledgeRuntime._verify_i(conn, packet['data_id'], packet)
                for unit in packet['model_input']['information']:
                    units[unit['information_id']] = {**unit, 'data_id': packet['data_id']}
            graph = self._graph(conn, units)
            self._verify_graph_groundings(graph, units)
            # Bind current document/K pairs now. Historical associations come
            # from earlier DB checkpoints, never guessed retroactively.
            papers = [archive['snapshots'][entry['snapshot_id']] for entry in current['papers'].values()]
            links = build_related_links(papers, graph, annotations)
            for raw in archive['files'].values():
                _immutable(conn, 'blobs', {'sha256': sha256(raw).hexdigest(), 'content': raw}, ['sha256'])
            for snapshot in archive['snapshots'].values():
                _immutable(conn, 'pages', {'wiki_id': wiki_id, 'page_id': snapshot['page_id'],
                    'kind': snapshot['kind'], 'data_id': snapshot.get('data_id'),
                    'topic_key': snapshot.get('topic_key')}, ['wiki_id', 'page_id'])
            for snapshot in archive['snapshots'].values():
                raw = archive['files']['snapshots/' + snapshot['snapshot_id'] + '.json']
                _immutable(conn, 'snapshots', {'wiki_id': wiki_id, 'snapshot_id': snapshot['snapshot_id'],
                    'page_id': snapshot['page_id'], 'previous_snapshot_id': snapshot['previous_snapshot_id'],
                    'previous_snapshot_sha256': snapshot['previous_snapshot_sha256'],
                    'snapshot_sha256': digest(snapshot), 'body_sha256': snapshot['body_sha256'],
                    'origin_request_id': snapshot['origin_request_id'],
                    'source_execution_id': snapshot.get('source_execution_id'), 'data_id': snapshot.get('data_id'),
                    'raw_sha256': sha256(raw).hexdigest(), 'payload': snapshot}, ['wiki_id', 'snapshot_id'])
                if snapshot['kind'] != 'paper':
                    continue
                for item in snapshot['items']:
                    _immutable(conn, 'items', {'wiki_id': wiki_id, 'snapshot_id': snapshot['snapshot_id'],
                        'item_key': item['item_key'], 'item_text_sha256': sha256(item['text'].encode()).hexdigest(),
                        'payload': item}, ['wiki_id', 'snapshot_id', 'item_key'])
                    for ordinal, evidence in enumerate(item['evidence']):
                        _immutable(conn, 'citations', {'wiki_id': wiki_id, 'snapshot_id': snapshot['snapshot_id'],
                            'item_key': item['item_key'], 'ordinal': ordinal,
                            **{key: evidence[key] for key in ('information_id', 'data_id', 'source_execution_id',
                                'char_start', 'char_end', 'quote', 'media_sha256')},
                            'payload': evidence}, ['wiki_id', 'snapshot_id', 'item_key', 'ordinal'])
            for catalog_sha, catalog in sorted(archive['catalogs'].items(), key=lambda pair: pair[1]['version']):
                raw = archive['files'].get('catalogs/' + catalog_sha + '.json', archive['files']['catalog.json'])
                _immutable(conn, 'catalogs', {'wiki_id': wiki_id, 'catalog_sha256': catalog_sha,
                    'version': catalog['version'], 'raw_sha256': sha256(raw).hexdigest(), 'payload': catalog},
                    ['wiki_id', 'catalog_sha256'])
                for collection in ('papers', 'topics'):
                    for entry in catalog[collection].values():
                        _immutable(conn, 'members', {'wiki_id': wiki_id, 'catalog_sha256': catalog_sha,
                            'page_id': entry['page_id'], 'snapshot_id': entry['snapshot_id']},
                            ['wiki_id', 'catalog_sha256', 'page_id'])
            result = {'schema_version': PROFILE, 'wiki_id': wiki_id, 'request_id': identifier,
                'catalog_sha256': archive['current_catalog_sha256'], 'catalog_version': current['version'],
                'manifest_sha256': archive['manifest_sha256'], 'paper_count': len(current['papers']),
                'topic_count': sum(entry['active'] for entry in current['topics'].values()),
                'snapshot_count': len(archive['snapshots']), 'archived_file_count': len(archive['files']),
                'knowledge_state_version': graph['state_version'], 'related_link_count': len(links),
                'binding_profile_sha256': digest(graph['binding_profile']),
                'review_required_link_count': sum(link['review_required'] for link in links),
                'canonical_writes': 0, 'model_calls': 0, 'new_d2i_calls': 0}
            _immutable(conn, 'imports', {'request_id': identifier, 'wiki_id': wiki_id,
                'request_fingerprint': fingerprint, 'expected_head': expected_head,
                'catalog_sha256': archive['current_catalog_sha256'], 'manifest_sha256': archive['manifest_sha256'],
                'manifest': archive['manifest'], 'knowledge_state_version': graph['state_version'],
                'graph_sha256': digest(graph), 'graph_payload': graph, 'review_annotations': annotations,
                'result': result}, ['request_id'])
            for entry in archive['manifest']['files']:
                _immutable(conn, 'files', {'request_id': identifier, 'path': entry['path'],
                    'raw_sha256': entry['sha256']}, ['request_id', 'path'])
            for link in links:
                link_id = str(conn.execute('SELECT uuidv7() AS id').fetchone()['id'])
                _immutable(conn, 'knowledge_links', {'link_id': link_id, 'request_id': identifier,
                    'wiki_id': wiki_id, 'snapshot_id': link['snapshot_id'], 'item_key': link['item_key'],
                    'knode_id': link['knode_id'], 'node_revision_id': link['knode_revision_id'],
                    'content_fingerprint': link['content_fingerprint'], 'link_sha256': link['link_sha256'],
                    'review_required': link['review_required'], 'payload': link}, ['link_id'])
                for ordinal, match in enumerate(link['matches']):
                    _immutable(conn, 'knowledge_matches', {'link_id': link_id, 'ordinal': ordinal,
                        **{key: match[key] for key in ('wiki_evidence_index', 'grounding_id', 'information_id',
                            'data_id', 'overlap_start', 'overlap_end', 'quote', 'media_sha256', 'match_kind')}},
                        ['link_id', 'ordinal'])
            if checkpoint:
                checkpoint('before_current')
            conn.execute('UPDATE wiki_projection.wikis SET current_import_id=%s WHERE wiki_id=%s', (identifier, wiki_id))
            if transaction_guard:
                # Resolve deferred projection checks before the final lease
                # assertion. Expiry during the writes/checks rolls back the
                # head and every inserted projection row in this transaction.
                conn.execute('SET CONSTRAINTS ALL IMMEDIATE')
                transaction_guard(conn)
        if checkpoint:
            checkpoint('after_commit')
        return {**result, 'replayed': False}

    def catalog(self, wiki_id, *, import_id=None):
        wiki_id = request_id(wiki_id)
        import_id = request_id(import_id) if import_id else None
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            self._ready(conn)
            selected = self._import(conn, wiki_id, import_id)
            row = conn.execute('SELECT payload FROM wiki_projection.catalogs WHERE wiki_id=%s AND catalog_sha256=%s',
                               (wiki_id, selected['catalog_sha256'])).fetchone()
            return {'wiki_id': wiki_id, 'import_id': selected['request_id'], 'catalog': row['payload'],
                    'knowledge_state_version': selected['knowledge_state_version'], 'canonical': False}

    def history(self, wiki_id, page_id, *, import_id=None):
        selected = self.catalog(wiki_id, import_id=import_id)
        page_id = request_id(page_id)
        catalog = selected['catalog']
        entry = next((entry for collection in ('papers', 'topics') for entry in catalog[collection].values()
                      if entry['page_id'] == page_id), None)
        if entry is None:
            _fail('wiki_page_not_found', 2)
        history, seen = [], set()
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SET TRANSACTION READ ONLY')
            while entry:
                row = conn.execute('SELECT payload FROM wiki_projection.snapshots WHERE wiki_id=%s AND snapshot_id=%s',
                                   (wiki_id, entry['snapshot_id'])).fetchone()
                if (row is None or digest(row['payload']) != entry['snapshot_sha256']
                        or row['payload']['page_id'] != page_id or entry['snapshot_id'] in seen):
                    _fail('wiki_database_snapshot_changed')
                value = row['payload']
                seen.add(value['snapshot_id'])
                history.append(value)
                entry = ({'snapshot_id': value['previous_snapshot_id'],
                          'snapshot_sha256': value['previous_snapshot_sha256']} if value['previous_snapshot_id'] else None)
        return {'wiki_id': wiki_id, 'page_id': page_id, 'import_id': selected['import_id'],
                'snapshots': history, 'canonical': False}

    def related(self, wiki_id, page_id, *, import_id=None, include_review_required=False):
        selected = self.catalog(wiki_id, import_id=import_id)
        page_id = request_id(page_id)
        catalog = selected['catalog']
        entry = next((entry for collection in ('papers', 'topics') for entry in catalog[collection].values()
                      if entry['page_id'] == page_id), None)
        if entry is None:
            _fail('wiki_page_not_found', 2)
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            page = conn.execute('SELECT payload FROM wiki_projection.snapshots WHERE wiki_id=%s AND snapshot_id=%s',
                                (wiki_id, entry['snapshot_id'])).fetchone()['payload']
            if page['kind'] == 'paper':
                allowed = {(page['snapshot_id'], item['item_key']) for item in page['items']}
            else:
                allowed = {(catalog['papers'][c['paper_data_id']]['snapshot_id'], item['item_key'])
                           for c in page['contributions'] for item in c['items']}
            rows = conn.execute('''SELECT l.link_id,l.payload,n.current_revision_id
                FROM wiki_projection.knowledge_links l JOIN canonical_store.knowledge_nodes n USING(knode_id)
                WHERE l.request_id=%s AND l.wiki_id=%s AND l.snapshot_id=ANY(%s::uuid[])
                ORDER BY l.snapshot_id,l.item_key,l.node_revision_id''',
                (selected['import_id'], wiki_id, list({snapshot for snapshot, _ in allowed}))).fetchall()
            links = []
            held = 0
            for row in rows:
                link = row['payload']
                if (link['snapshot_id'], link['item_key']) not in allowed:
                    continue
                if link['review_required']:
                    held += 1
                    if not include_review_required:
                        continue
                links.append({**link, 'link_id': str(row['link_id']),
                              'is_current_now': str(row['current_revision_id']) == link['knode_revision_id']})
        return {'wiki_id': wiki_id, 'page_id': page_id, 'snapshot_id': entry['snapshot_id'],
                'import_id': selected['import_id'], 'relation': 'shared_source_evidence',
                'semantic_support_validated': False, 'review_required_links': held, 'links': links}

    def restore(self, wiki_id, directory, *, import_id=None):
        wiki_id = request_id(wiki_id)
        import_id = request_id(import_id) if import_id else None
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            self._ready(conn)
            selected = self._import(conn, wiki_id, import_id)
            rows = conn.execute('''SELECT f.path,f.raw_sha256,b.content FROM wiki_projection.files f
                JOIN wiki_projection.blobs b ON b.sha256=f.raw_sha256 WHERE f.request_id=%s ORDER BY f.path''',
                (selected['request_id'],)).fetchall()
            files = {}
            for row in rows:
                raw = bytes(row['content'])
                if sha256(raw).hexdigest() != row['raw_sha256']:
                    _fail('wiki_database_blob_changed')
                files[row['path']] = raw
        archive = validate_archive_files(files)
        if (archive['manifest'] != selected['manifest'] or archive['manifest_sha256'] != selected['manifest_sha256']
                or archive['current_catalog_sha256'] != selected['catalog_sha256']):
            _fail('wiki_database_archive_changed')
        # Read and validate all media before selecting a restored current catalog.
        media = []
        for asset in archive['media_assets']:
            raw = self.source.derived.read(asset['sha256'], asset['byte_size'])
            if asset['relative_path'] != 'media/' + asset['sha256'] + _image_suffix(raw):
                _fail('wiki_database_media_changed')
            media.append((asset['relative_path'], raw))
        store = ProjectionStore(Path(directory))
        with store.locked():
            # Refuse a conflicting destination before adding any payload files.
            # A fresh interrupted restore remains retryable with the same bytes.
            for path, raw in [*sorted(files.items()), *media]:
                try:
                    existing = store.read_bytes(path)
                except PalimpsestError as error:
                    if error.code != 'wiki_projection_missing':
                        raise
                else:
                    if existing != raw:
                        _fail('wiki_database_restore_conflict')
            for path, raw in sorted(files.items()):
                if path != 'catalog.json':
                    store.write_bytes(path, raw)
            for path, raw in media:
                store.write_bytes(path, raw)
            store.write_bytes('catalog.json', files['catalog.json'])
        return {'wiki_id': wiki_id, 'import_id': selected['request_id'], 'directory': str(store.root),
                'manifest_sha256': archive['manifest_sha256'], 'restored_files': len(files),
                'restored_media': len(media), 'canonical_writes': 0}

    def export(self, wiki_id, directory, *, import_id=None, catalog_sha256=None):
        restored = self.restore(wiki_id, directory, import_id=import_id)
        exported = PaperWikiRuntime(self.dsn, self.artifact_root, directory).export(catalog_sha256=catalog_sha256)
        return {**restored, 'export': exported}
