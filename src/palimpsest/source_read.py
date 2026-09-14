"""Read registered Data and exact source Information without requiring a Wiki.

The connection and artifact root are selected by the trusted host, never by a
request. These operations neither register/parse sources nor call any model.
"""

from base64 import b64encode
from collections import defaultdict
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256 as hash_bytes
import json

from psycopg.conninfo import conninfo_to_dict, make_conninfo

from .canonical_store import connection, MIGRATIONS, migration_source
from .compiler_runtime import CompilerRuntime, SOURCE_PROFILE
from .data import data_id as check_data_id, request_id
from .d2i import CODE_ALGORITHM, MARKDOWN_ALGORITHM
from .errors import PalimpsestError
from .i2k import digest
from .paper_wiki_runtime import _image_suffix


MAX_ARTIFACT_BYTES = 50 * 1024 * 1024
_OPERATIONS = {
    'source_catalog': (set(), set()),
    'source_detail': ({'data_id'}, set()),
    'source_information': ({'data_id', 'source_execution_id', 'information_id'}, set()),
    'source_artifact': ({'data_id'}, {'source_execution_id', 'sha256'}),
    'parchment_catalog': (set(), set()),
    'parchment_get': ({'parchment_id'}, set()),
}
_DATA_COLUMNS = 'data_id,media_type,byte_size,original_name AS filename,created_at'


def _json(value):
    return json.loads(json.dumps(value, ensure_ascii=False, default=str, allow_nan=False))


def _fail(code='invalid_source_read_request', status=2):
    raise PalimpsestError(code, '등록 자료·정확한 source 실행·원문 소유권을 확인하세요.', status)


def source_kind(data, executions=(), acquisitions=()):
    """Use registered MIME and explicit parser/acquisition provenance, not suffixes."""
    media_type = data['media_type'].split(';', 1)[0].strip().lower()
    if media_type == 'application/pdf':
        return 'pdf'
    code_uri = 'palimpsest:codebase-snapshot:sha256:' + data['data_id']
    algorithms = {row.get('profile', {}).get('transformation', {}).get('algorithm') for row in executions}
    if CODE_ALGORITHM in algorithms or any(row.get('origin_uri') == code_uri for row in acquisitions):
        return 'code'
    if media_type in ('text/html', 'application/xhtml+xml'):
        return 'web'
    if MARKDOWN_ALGORITHM in algorithms or media_type in ('text/markdown', 'text/x-markdown'):
        return 'markdown'
    if media_type.startswith('image/'):
        return 'image'
    if media_type in ('text/x-python', 'application/x-python-code', 'text/javascript', 'application/javascript'):
        return 'code'
    return 'text' if media_type.startswith('text/') or media_type in ('application/json', 'application/xml') else 'other'


class SourceReadService:
    def __init__(self, dsn, artifact_root):
        options = conninfo_to_dict(dsn).get('options', '')
        self.dsn = make_conninfo(dsn, options=options + ' -c default_transaction_read_only=on')
        self.runtime = CompilerRuntime(self.dsn, artifact_root)

    def dispatch(self, request):
        if (not isinstance(request, dict) or not isinstance(request.get('operation'), str)
                or request['operation'] not in _OPERATIONS):
            _fail()
        operation = request['operation']
        required, optional = _OPERATIONS[operation]
        if not required <= request.keys() or set(request) - {'operation'} - required - optional:
            _fail()
        if operation == 'source_artifact' and (('source_execution_id' in request) != ('sha256' in request)):
            _fail('source_media_execution_required')
        # Explicit nulls are not omitted arguments, nor alternative authority.
        for field, value in request.items():
            if field != 'operation':
                (check_data_id if field in ('data_id', 'sha256') else request_id)(value)
        return getattr(self, operation)(**{key: value for key, value in request.items() if key != 'operation'})

    @staticmethod
    def _ready(conn):
        if conn.execute('SHOW transaction_read_only').fetchone()['transaction_read_only'] != 'on':
            _fail('source_read_only_required', 3)
        version = conn.execute("SELECT current_setting('server_version_num')::integer AS version").fetchone()['version']
        extension = conn.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()
        if version // 10000 != 18 or extension is None or extension['extversion'] != '0.8.6':
            _fail('source_database_profile_mismatch', 3)
        if conn.execute("SELECT to_regclass('compiler_runtime.schema_migrations') AS name").fetchone()['name'] is None:
            _fail('source_database_not_initialized', 3)
        installed = _json(conn.execute('SELECT version,checksum FROM compiler_runtime.schema_migrations ORDER BY version').fetchall())
        expected = [{'version': name, 'checksum': migration_source(name)[1]} for name in MIGRATIONS]
        if (len(installed) < 6 or len(installed) > len(expected) or installed != expected[:len(installed)]):
            _fail('source_database_schema_mismatch', 3)
        return {'schema_version': installed[-1]['version'], 'registered_data': True,
            'source_information': True, 'wiki_projection': len(installed) >= 8,
            'knowledge_inference': len(installed) >= 11, 'data_versions': len(installed) >= 13,
            'data_grounding': len(installed) >= 14, 'effective_inference': len(installed) >= 20,
            'wisdom': len(installed) >= 21, 'parchment': len(installed) >= 22,
            'scope': 'all_registered_data_in_connection', 'max_artifact_bytes': MAX_ARTIFACT_BYTES,
            'read_only': True}

    @contextmanager
    def _read(self):
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            yield conn, self._ready(conn)

    @staticmethod
    def _data(conn, data_id):
        row = conn.execute('SELECT ' + _DATA_COLUMNS + ' FROM canonical_store.data WHERE data_id=%s', (data_id,)).fetchone()
        if row is None:
            _fail('source_data_not_registered')
        return _json(row)

    @staticmethod
    def _executions(conn, data_id=None):
        return _json(conn.execute('''SELECT e.execution_id,e.data_id,e.state,e.profile_id,p.profile_hash,p.payload AS profile,
            e.generation,e.attempt,e.error_code,e.created_at,e.updated_at,
            COALESCE(counts.information_count,0) AS information_count
            FROM compiler_runtime.operation_executions e JOIN compiler_runtime.profiles p USING(profile_id)
            LEFT JOIN (SELECT r.execution_id,count(*) AS information_count FROM canonical_store.information i
                JOIN compiler_runtime.records r ON r.record_id=i.origin_record_id GROUP BY r.execution_id) counts USING(execution_id)
            WHERE e.operation='d2i' ''' + ('AND e.data_id=%s ' if data_id else '') + 'ORDER BY e.created_at,e.execution_id',
            (data_id,) if data_id else ()).fetchall())

    @staticmethod
    def _acquisitions(conn, data_id=None):
        # Acquisition metadata is provenance, never authority to fetch its URI.
        return _json(conn.execute('''SELECT acquisition_id,data_id,origin_uri,import_method,retrieved_at,
            original_name,created_at FROM canonical_store.data_acquisitions '''
            + ('WHERE data_id=%s ' if data_id else '') + 'ORDER BY created_at,acquisition_id',
            (data_id,) if data_id else ()).fetchall())

    @staticmethod
    def _versions(conn, capabilities, data_id=None):
        if not capabilities['data_versions']:
            return []
        return _json(conn.execute('''SELECT v.version_id,v.series_id,v.parent_version_id,v.data_id,v.version_number,
            v.title,v.message,v.created_at,s.name AS series_name,s.head_version_id,
            (s.head_version_id=v.version_id) AS is_head
            FROM canonical_store.data_versions v JOIN canonical_store.data_series s USING(series_id) '''
            + ('WHERE v.data_id=%s ' if data_id else '') + 'ORDER BY v.series_id,v.version_number',
            (data_id,) if data_id else ()).fetchall())

    @staticmethod
    def _summary(data, executions, acquisitions, versions):
        return {**deepcopy(data), 'source_kind': source_kind(data, executions, acquisitions),
            'information_count': sum(row['information_count'] for row in executions),
            'source_execution_count': len(executions),
            'completed_source_execution_count': sum(row['state'] == 'completed' for row in executions),
            'acquisitions': deepcopy(acquisitions), 'versions': deepcopy(versions),
            'source_executions': [{key: row[key] for key in
                ('execution_id', 'state', 'profile_id', 'profile_hash', 'information_count', 'error_code')} | {
                    'profile_schema': row['profile'].get('schema_version'),
                    'algorithm': row['profile'].get('transformation', {}).get('algorithm')} for row in executions],
            'original_available_by_size': data['byte_size'] <= MAX_ARTIFACT_BYTES,
            'verification_status': 'registered_metadata_not_artifact_read'}

    def source_catalog(self):
        with self._read() as (conn, capabilities):
            data = _json(conn.execute('SELECT ' + _DATA_COLUMNS + ' FROM canonical_store.data ORDER BY created_at,data_id').fetchall())
            grouped = []
            for rows in (self._executions(conn), self._acquisitions(conn), self._versions(conn, capabilities)):
                values = defaultdict(list)
                for row in rows:
                    values[row['data_id']].append(row)
                grouped.append(values)
            return {'schema_version': 'source-catalog-v1',
                'data': [self._summary(row, *(values[row['data_id']] for values in grouped)) for row in data],
                'capabilities': capabilities, 'read_only': True}

    @staticmethod
    def _parchment_sources(conn, identifier):
        # Classify by the frozen delivered K scope, including Edge endpoints.
        # Later same-meaning K support must not add new source/Realm attribution.
        return [row['data_id'] for row in conn.execute('''SELECT DISTINCT d.data_id
            FROM canonical_store.parchment_wisdoms p
            JOIN canonical_store.wisdoms w USING(wisdom_id)
            JOIN compiler_runtime.w_inputs i USING(execution_id)
            CROSS JOIN LATERAL jsonb_array_elements_text(
                COALESCE(i.payload->'source_data_ids','[]'::jsonb)
                || COALESCE(i.payload->'grounding_data_ids','[]'::jsonb)
                || jsonb_build_array(i.payload->'source_data_id')) d(data_id)
            WHERE p.parchment_id=%s AND d.data_id IS NOT NULL ORDER BY d.data_id''', (identifier,)).fetchall()]

    def parchment_catalog(self):
        with self._read() as (conn, capabilities):
            pages = []
            if capabilities['parchment']:
                for row in conn.execute('''SELECT parchment_id,title,snapshot_sha256,
                        snapshot->'input_wisdom_ids' AS input_wisdom_ids
                        FROM canonical_store.parchments ORDER BY created_at,parchment_id''').fetchall():
                    pages.append({**_json(row), 'source_data_ids': self._parchment_sources(conn, row['parchment_id'])})
            return {'schema_version': 'parchment-catalog-v1', 'parchments': pages,
                    'supported': capabilities['parchment'], 'read_only': True}

    def parchment_get(self, parchment_id):
        from .parchment_runtime import ParchmentRuntime
        identifier = request_id(parchment_id)
        with self._read() as (conn, capabilities):
            if not capabilities['parchment']:
                _fail('parchment_schema_not_installed', 3)
            return {'parchment': ParchmentRuntime._parchment(conn, identifier),
                    'source_data_ids': self._parchment_sources(conn, identifier), 'read_only': True}

    def source_detail(self, data_id):
        owner = check_data_id(data_id)
        with self._read() as (conn, capabilities):
            data = self._data(conn, owner)
            executions = self._executions(conn, owner)
            acquisitions = self._acquisitions(conn, owner)
            versions = self._versions(conn, capabilities, owner)
            directory = _json(conn.execute('''SELECT i.information_id,i.data_id,i.origin_record_id,i.kind,i.unit_type,
                i.semantic_type,i.title,char_length(i.content) AS character_count,i.payload->>'schema_version' AS representation_schema,
                r.execution_id AS source_execution_id,r.ordinal FROM canonical_store.information i
                JOIN compiler_runtime.records r ON r.record_id=i.origin_record_id
                WHERE i.data_id=%s ORDER BY r.execution_id,r.ordinal''', (owner,)).fetchall())
            refs = defaultdict(list)
            for grounding in _json(conn.execute('''SELECT g.* FROM canonical_store.information_groundings g
                WHERE g.data_id=%s ORDER BY g.information_id,g.grounding_id''', (owner,)).fetchall()):
                refs[grounding['information_id']].append(grounding)
            for unit in directory:
                unit['source_refs'] = refs[unit['information_id']]
            return {'schema_version': 'source-detail-v1',
                'data': self._summary(data, executions, acquisitions, versions),
                'executions': executions, 'information': directory, 'versions': versions,
                'knowledge': self._knowledge(conn, owner, capabilities),
                'i2k_executions': self._compilations(conn, owner),
                'acquisitions': acquisitions, 'capabilities': capabilities, 'read_only': True}

    @staticmethod
    def _compilations(conn, owner):
        # Membership comes from actual delivered-input refs, not a representative D.
        return _json(conn.execute('''SELECT e.execution_id,e.state,e.created_at,
            p.payload->>'schema_version' AS profile_schema,
            (SELECT count(*) FROM compiler_runtime.k_model_calls calls
                WHERE calls.execution_id=e.execution_id AND calls.status='succeeded') AS successful_model_calls,
            (SELECT count(*) FROM compiler_runtime.k_model_calls calls
                WHERE calls.execution_id=e.execution_id AND calls.status<>'succeeded') AS other_model_calls,
            (SELECT count(DISTINCT r.result_node_id) FROM compiler_runtime.k_compilation_records r
                WHERE r.execution_id=e.execution_id AND r.disposition IN ('accepted_new','accepted_revision')) AS created_or_revised_nodes,
            (SELECT count(*) FROM compiler_runtime.k_compilation_records r
                WHERE r.execution_id=e.execution_id AND r.disposition='reused') AS reused_records
            FROM compiler_runtime.operation_executions e JOIN compiler_runtime.profiles p USING(profile_id)
            WHERE e.operation='i2k' AND EXISTS(SELECT 1 FROM compiler_runtime.k_input_information input
                JOIN canonical_store.information i USING(information_id)
                WHERE input.execution_id=e.execution_id AND i.data_id=%s)
            ORDER BY e.created_at,e.execution_id''', (owner,)).fetchall())

    @staticmethod
    def _knowledge(conn, owner, capabilities):
        source_clause = ('''EXISTS(SELECT 1 FROM canonical_store.derivation_source_data(r.knode_revision_id) source(data_id)
            WHERE source.data_id=%s)''' if capabilities['knowledge_inference'] else '''EXISTS(
            SELECT 1 FROM canonical_store.knowledge_node_groundings g
            JOIN canonical_store.information i USING(information_id)
            WHERE g.node_revision_id=r.knode_revision_id AND i.data_id=%s)''')
        current_clause = (',compiler_runtime.current_k2k_premise(r.knode_revision_id) AS current_usable'
                          if capabilities['knowledge_inference'] else '')
        nodes = _json(conn.execute('''SELECT r.knode_revision_id,r.knode_id,r.semantic_payload,r.statement,
            r.origin_record_id,r.supersedes_revision_id,r.created_at,n.kind,n.current_revision_id,
            c.record_type AS origin_operation,c.disposition AS record_disposition,
            s.identity_scope,s.source_data_id''' + current_clause + '''
            FROM canonical_store.knowledge_node_revisions r
            JOIN canonical_store.knowledge_nodes n USING(knode_id)
            JOIN compiler_runtime.k_compilation_records c ON c.record_id=r.origin_record_id
            LEFT JOIN canonical_store.knowledge_node_scopes s USING(knode_id)
            WHERE c.disposition IN ('accepted_new','accepted_revision')
                AND c.result_node_revision_id=r.knode_revision_id AND c.result_node_id=r.knode_id
                AND ''' + source_clause + ' ORDER BY r.knode_id,r.created_at,r.knode_revision_id', (owner,)).fetchall())
        refs = [node['knode_revision_id'] for node in nodes]
        if not refs:
            return []
        grounds = defaultdict(list)
        for row in _json(conn.execute('''SELECT g.*,i.data_id,source_record.execution_id AS source_execution_id
            FROM canonical_store.knowledge_node_groundings g JOIN canonical_store.information i USING(information_id)
            JOIN compiler_runtime.records source_record ON source_record.record_id=i.origin_record_id
            WHERE i.data_id=%s AND g.node_revision_id=ANY(%s::uuid[]) ORDER BY g.grounding_id''', (owner, refs)).fetchall()):
            grounds[row['node_revision_id']].append(row)
        direct_data = defaultdict(list)
        if capabilities['data_grounding']:
            for row in _json(conn.execute('''SELECT grounding_id,node_revision_id,data_id,view_id,origin_record_id,evidence
                FROM canonical_store.knowledge_data_groundings WHERE data_id=%s AND node_revision_id=ANY(%s::uuid[])
                ORDER BY grounding_id''', (owner, refs)).fetchall()):
                direct_data[row['node_revision_id']].append(row)
        for node in nodes:
            operation = node.pop('origin_operation')
            node.update(is_current_revision=node['knode_revision_id'] == node['current_revision_id'],
                generation_origin={'origin_operation': operation, 'is_inferred': operation == 'k2k',
                    'origin_record_id': node['origin_record_id']},
                groundings=grounds[node['knode_revision_id']],
                source_relation='direct_or_transitive_grounding', evidence_scope_data_id=owner)
            if capabilities['knowledge_inference']:
                node['current_applicability'] = 'current_premises' if node.pop('current_usable') else 'needs_revalidation'
            if direct_data[node['knode_revision_id']]:
                node['data_groundings'] = direct_data[node['knode_revision_id']]
        return nodes

    @staticmethod
    def _execution(conn, owner, identifier):
        row = conn.execute('''SELECT e.execution_id,e.data_id,e.operation,e.state,p.payload AS profile
            FROM compiler_runtime.operation_executions e JOIN compiler_runtime.profiles p USING(profile_id)
            WHERE e.execution_id=%s''', (identifier,)).fetchone()
        if row is None or row['data_id'] != owner or row['operation'] != 'd2i':
            _fail('source_execution_owner_mismatch')
        return _json(row)

    def _packet(self, owner, execution):
        if execution['state'] != 'completed' or execution['profile'].get('schema_version') != SOURCE_PROFILE:
            _fail('source_verified_packet_unavailable')
        packet = self.runtime.prepare_input(execution['execution_id'])
        if (packet.get('data_id') != owner or packet.get('source_execution_id') != execution['execution_id']
                or packet.get('model_input', {}).get('data_id') != owner
                or packet.get('actual_delivery') is not False
                or packet.get('input_sha256') != digest({key: value for key, value in packet.items() if key != 'input_sha256'})):
            _fail('source_packet_binding_changed', 6)
        return packet

    def source_information(self, data_id, source_execution_id, information_id):
        owner, execution_id, identifier = check_data_id(data_id), request_id(source_execution_id), request_id(information_id)
        with self._read() as (conn, _):
            data = self._data(conn, owner)
            execution = self._execution(conn, owner, execution_id)
            stored = conn.execute('''SELECT i.*,r.execution_id AS source_execution_id,r.disposition,
                r.result_information_id FROM canonical_store.information i
                JOIN compiler_runtime.records r ON r.record_id=i.origin_record_id WHERE i.information_id=%s''', (identifier,)).fetchone()
            if (stored is None or stored['data_id'] != owner or str(stored['source_execution_id']) != execution_id
                    or stored['disposition'] != 'accepted' or str(stored['result_information_id']) != identifier):
                _fail('source_information_owner_mismatch')
            stored = _json(stored)
            groundings = _json(conn.execute('''SELECT * FROM canonical_store.information_groundings
                WHERE information_id=%s ORDER BY grounding_id''', (identifier,)).fetchall())
            if any(row['data_id'] != owner or row['information_id'] != identifier for row in groundings):
                _fail('source_information_owner_mismatch')
        if execution['profile'].get('schema_version') == SOURCE_PROFILE:
            packet = self._packet(owner, execution)
            matches = [unit for unit in packet['model_input']['information'] if unit['information_id'] == identifier]
            if len(matches) != 1 or any(matches[0].get(key) != stored[key] for key in
                    ('origin_record_id', 'kind', 'unit_type', 'title', 'content', 'identity_fingerprint', 'content_fingerprint')):
                _fail('source_information_snapshot_changed', 6)
            unit = deepcopy(matches[0])
            verification = {'method': 'verified_complete_source_packet', 'input_sha256': packet['input_sha256']}
            source_format = packet['model_input'].get('source_format', 'pdf')
        elif execution['profile'].get('schema_version') == 'd2i-v1':
            # Historical semantic extraction is readable history, not a claim of
            # complete source coverage or a replacement for the later source I.
            unit = {key: deepcopy(stored[key]) for key in ('information_id', 'origin_record_id', 'kind',
                'unit_type', 'semantic_type', 'title', 'content', 'identity_fingerprint', 'content_fingerprint', 'payload')}
            unit.update(source_refs=groundings, media=[])
            verification = {'method': 'stored_legacy_information', 'source_packet_verified': False,
                            'media_preview': 'use_registered_original'}
            source_format = source_kind(data, [execution])
        else:
            _fail('source_information_profile_unavailable')
        return {**unit, 'data_id': owner, 'source_execution_id': execution_id, 'source_format': source_format,
            'original': {'sha256': owner, 'byte_size': data['byte_size'], 'media_type': data['media_type']},
            'verification': verification, 'read_only': True}

    def source_artifact(self, data_id, source_execution_id=None, sha256=None):
        owner = check_data_id(data_id)
        identifier = request_id(source_execution_id) if source_execution_id is not None else None
        checksum = check_data_id(sha256) if sha256 is not None else owner
        if (sha256 is not None) != (identifier is not None):
            _fail('source_media_execution_required')
        with self._read() as (conn, _):
            data = self._data(conn, owner)
            execution = self._execution(conn, owner, identifier) if identifier else None
        size, media_type, store = data['byte_size'], data['media_type'], self.runtime.store
        if sha256 is not None:
            packet = self._packet(owner, execution)
            assets = [asset for unit in packet['model_input']['information'] for asset in unit['media'] if asset['sha256'] == checksum]
            if not assets or len({asset['byte_size'] for asset in assets}) != 1:
                _fail('source_media_owner_mismatch')
            size, media_type, store = assets[0]['byte_size'], None, self.runtime.derived
        if size > MAX_ARTIFACT_BYTES:
            _fail('source_artifact_too_large')
        raw = store.read(checksum, size)
        if len(raw) != size or hash_bytes(raw).hexdigest() != checksum:
            _fail('source_artifact_changed', 6)
        if sha256 is not None:
            media_type = {'.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp'}[_image_suffix(raw)]
        textual = media_type.split(';', 1)[0].strip().lower()
        if textual == 'application/pdf' and b'%PDF-' not in raw[:1024]:
            _fail('source_artifact_changed', 6)
        result = {'data_id': owner, 'sha256': checksum, 'byte_size': size, 'media_type': media_type,
                  'source_execution_id': identifier, 'verified': True, 'read_only': True}
        if textual.startswith('text/') or textual in ('application/json', 'application/xml', 'application/xhtml+xml', 'application/javascript'):
            try:
                text = raw.decode('utf-8')
                if '\x00' not in text:
                    result.update(text=text, encoding='utf-8', representation='original_utf8_text')
                    if len(json.dumps(result, ensure_ascii=False)) > 90 * 1024 * 1024:
                        _fail('source_artifact_too_large')
                    return result
            except UnicodeDecodeError:
                pass
        return {**result, 'base64': b64encode(raw).decode('ascii'), 'representation': 'original_bytes'}
