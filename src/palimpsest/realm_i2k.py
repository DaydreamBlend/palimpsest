"""Bind product I2K starts to verified, immutable Realm/source scope.

Trusted host configuration binds store_id to source_dsn. A scope hash or an LLM
flag is not authority to select a connection or to transmit source content.
No D/I/K migration, parser call, provider call, or cross-store write is performed.
"""

import os

from .data import data_id, request_id
from .errors import PalimpsestError
from .realms import RealmCatalog, SCOPE_PROFILE, freeze_scope


PROFILE = SCOPE_PROFILE
_NODE_COMPARISON = ('knode_id', 'kind', 'knode_revision_id', 'current_revision_id', 'statement',
    'semantic_payload', 'identity_fingerprint', 'content_fingerprint', 'origin_record_id',
    'supersedes_revision_id', 'identity_scope', 'source_data_id', 'grounding_data_ids', 'source_data_ids',
    'current_applicability', 'current_support_record_id', 'current_support_signature')
_EDGE_COMPARISON = ('kedge_id', 'kedge_revision_id', 'predicate', 'from_knode_id', 'to_knode_id',
    'from_knode_revision_id', 'to_knode_revision_id', 'current_revision_id', 'semantic_payload',
    'qualifiers', 'identity_fingerprint', 'content_fingerprint', 'origin_record_id', 'supersedes_revision_id')


def _fail(code, message, status=6):
    raise PalimpsestError(code, message, status)


def comparison_catalog(nodes, edges):
    """Global K meaning remains comparable without transmitting its source I/D."""
    from copy import deepcopy
    if any(not isinstance(items, list) or any(not isinstance(item, dict) for item in items) for items in (nodes, edges)):
        _fail('realm_comparison_catalog_mismatch', '기존 K 비교 목록을 확인하세요.')
    return tuple([{key: deepcopy(item[key]) for key in fields if key in item} for item in items]
                 for items, fields in ((nodes, _NODE_COMPARISON), (edges, _EDGE_COMPARISON)))


def _sources(packet):
    if not isinstance(packet, dict):
        _fail('realm_i2k_source_mismatch', 'Realm에 연결할 실제 I2K 입력이 필요합니다.')
    if packet.get('schema_version') == 'multi-source-i2k-input-v1':
        sources = packet.get('sources')
    elif packet.get('schema_version') == 'i2k-input-v1':
        sources = [packet]
    else:
        _fail('realm_i2k_source_mismatch', 'Realm I2K는 정확한 source execution이 있는 I 입력을 요구합니다.')
    if not isinstance(sources, list) or not sources:
        _fail('realm_i2k_source_mismatch', 'Realm I2K source 목록이 비어 있습니다.')
    result, seen, units = [], set(), []
    for source in sources:
        if not isinstance(source, dict) or source.get('schema_version') != 'i2k-input-v1':
            _fail('realm_i2k_source_mismatch', 'I2K source 형식이 일치하지 않습니다.')
        owner, execution = data_id(source.get('data_id')), request_id(source.get('source_execution_id'))
        model_input = source.get('model_input')
        if not isinstance(model_input, dict):
            _fail('realm_i2k_source_mismatch', '실제 전달할 I2K source 입력이 필요합니다.')
        information = model_input.get('information')
        if owner in seen or not isinstance(information, list) or not information:
            _fail('realm_i2k_source_mismatch', '한 Data의 정확한 source 실행과 I 목록을 확인하세요.')
        seen.add(owner)
        identifiers = [request_id(item.get('information_id')) for item in information if isinstance(item, dict)]
        if len(identifiers) != len(information) or len(set(identifiers)) != len(identifiers):
            _fail('realm_i2k_source_mismatch', '실제 전달할 Information 목록이 중복되거나 누락되었습니다.')
        units.extend(identifiers)
        result.append((owner, execution, identifiers))
    model_input = packet.get('model_input')
    actual = model_input.get('information') if isinstance(model_input, dict) else None
    if (not isinstance(actual, list) or any(not isinstance(unit, dict) for unit in actual)
            or [unit.get('information_id') for unit in actual] != units):
        _fail('realm_i2k_source_mismatch', '전달된 I 전체와 Realm source 목록이 일치해야 합니다.')
    return result


class RealmI2KGuard:
    def __init__(self, catalog, store_id, source_dsn, *, realm_ids=(), explicit_cross=False, actor='local'):
        self.catalog, self.store_id, self.source_dsn = catalog, request_id(store_id), source_dsn
        self.realm_ids = [request_id(value) for value in realm_ids]
        if len(set(self.realm_ids)) != len(self.realm_ids) or type(explicit_cross) is not bool:
            _fail('invalid_realm_selection', '명시적인 Realm 선택을 확인하세요.', 2)
        self.explicit_cross, self.actor = explicit_cross, actor

    def source_refs(self, conn, packet, version_ids=()):
        """Check actual source database ownership, never caller-declared hashes alone."""
        from .realm_registration import verify_ready
        verify_ready(conn, [owner for owner, _, _ in _sources(packet)], self.catalog, self.store_id)
        versions = {}
        if version_ids:
            if conn.execute("SELECT to_regclass('canonical_store.data_versions') AS name").fetchone()['name'] is None:
                _fail('realm_source_version_unavailable', '이 저장소에는 요청한 Data version이 없습니다.')
            identifiers = [request_id(value) for value in version_ids]
            rows = conn.execute('SELECT version_id,series_id,data_id FROM canonical_store.data_versions WHERE version_id=ANY(%s::uuid[])',
                                (identifiers,)).fetchall()
            if len(rows) != len(identifiers):
                _fail('realm_source_version_mismatch', '정확한 Data version을 찾을 수 없습니다.')
            for row in rows:
                if row['data_id'] in versions:
                    _fail('realm_source_version_ambiguous', 'Realm source 하나에는 정확한 series/version 하나를 지정하세요.')
                versions[row['data_id']] = {'version_id': str(row['version_id']), 'series_id': str(row['series_id'])}
        sources = []
        for owner, execution, information in _sources(packet):
            row = conn.execute('''SELECT e.data_id,e.operation,e.state FROM compiler_runtime.operation_executions e
                JOIN canonical_store.data d USING(data_id) WHERE e.execution_id=%s''', (execution,)).fetchone()
            if row is None or row['data_id'] != owner or row['operation'] != 'd2i' or row['state'] != 'completed':
                _fail('realm_i2k_source_mismatch', 'Realm source가 실제 완료된 D2I/Data와 일치하지 않습니다.')
            rows = conn.execute('''SELECT i.information_id,i.data_id,r.execution_id
                FROM canonical_store.information i JOIN compiler_runtime.records r ON r.record_id=i.origin_record_id
                WHERE i.information_id=ANY(%s::uuid[])''', (information,)).fetchall()
            if (len(rows) != len(information) or any(row['data_id'] != owner or str(row['execution_id']) != execution for row in rows)):
                _fail('realm_i2k_information_owner_mismatch', '실제 I의 Data/source execution이 Realm 범위를 벗어납니다.')
            sources.append({'store_id': self.store_id, 'data_id': owner, 'source_execution_id': execution,
                            **versions.get(owner, {'version_id': None, 'series_id': None})})
        if set(versions) - {source['data_id'] for source in sources}:
            _fail('realm_source_version_mismatch', '입력에 없는 Data version을 Realm 범위로 추가할 수 없습니다.')
        return sources

    def verify(self, conn, scope, packet, version_ids=()):
        if (not isinstance(scope, dict) or scope.get('schema_version') != PROFILE
                or not isinstance(scope.get('realm_revisions'), list)):
            _fail('realm_i2k_scope_mismatch', '보존된 Realm scope 형식을 확인하세요.')
        revisions = []
        for reference in scope['realm_revisions']:
            if not isinstance(reference, dict) or set(reference) != {'realm_id', 'revision_id'}:
                _fail('realm_i2k_scope_mismatch', '정확한 Realm revision 참조가 필요합니다.')
            revision = self.catalog.revision(request_id(reference['revision_id']))
            if revision['realm_id'] != request_id(reference['realm_id']):
                _fail('realm_i2k_scope_mismatch', 'Realm과 revision의 소유권이 일치하지 않습니다.')
            revisions.append(revision)
        sources = self.source_refs(conn, packet, version_ids)
        actual = freeze_scope(revisions, sources, explicit_cross=scope.get('explicit_cross'), actor=scope.get('actor'))
        if actual != scope:
            _fail('realm_i2k_scope_mismatch', 'Realm revision·source·scope hash가 준비된 입력과 일치하지 않습니다.')
        return actual

    def prepare(self, conn, packet, *, scope=None, feedback_scope=None, version_ids=()):
        if scope is not None:
            references = scope.get('realm_revisions', []) if isinstance(scope, dict) else []
            if not isinstance(references, list):
                _fail('realm_i2k_scope_mismatch', '정확한 Realm revision 목록이 필요합니다.')
            if (len(references) > 1 or scope.get('explicit_cross') is True) and not self.explicit_cross and scope != feedback_scope:
                _fail('realm_crossing_requires_explicit_selection', '새 교차 I2K에는 trusted 호출자의 명시적 선택이 필요합니다.', 2)
            if self.realm_ids and {ref.get('realm_id') for ref in references if isinstance(ref, dict)} != set(self.realm_ids):
                _fail('realm_i2k_scope_mismatch', '제공된 scope가 실제 선택한 Realm 집합과 다릅니다.')
            return self.verify(conn, scope, packet, version_ids)
        if self.realm_ids:
            sources = self.source_refs(conn, packet, version_ids)
            return self.catalog.build_scope(self.realm_ids, sources, explicit_cross=self.explicit_cross, actor=self.actor)
        if feedback_scope is not None:
            return self.verify(conn, feedback_scope, packet, version_ids)
        from .realm_automation import default_i2k_realm
        sources = self.source_refs(conn, packet, version_ids)
        revision = default_i2k_realm(conn, self.catalog, sources)
        return freeze_scope([revision], sources, explicit_cross=False, actor=self.actor)


def verify_job(runtime, conn, job):
    scope = job['input_snapshot'].get('realm_scope')
    marker = job['profile'].get('realm_i2k_policy')
    if scope is None and marker is None:
        return
    if job['operation'] != 'i2k' or marker != PROFILE or scope is None:
        _fail('realm_i2k_scope_mismatch', 'Realm profile과 실제 I2K 입력 scope가 일치하지 않습니다.')
    guard = runtime.realm_guard
    if guard is None:
        _fail('realm_configuration_required', '이 실행의 Realm catalog와 trusted source store 설정이 필요합니다.', 3)
    actual_catalog = (job['input_snapshot'].get('existing_nodes'), job['input_snapshot'].get('existing_edges'))
    if comparison_catalog(*actual_catalog) != actual_catalog:
        _fail('realm_comparison_catalog_mismatch', 'Realm I2K 비교 목록에 원문 I/D가 포함될 수 없습니다.')
    guard.verify(conn, scope, job['input_snapshot']['input'],
                 [version['version_id'] for version in job['input_snapshot'].get('data_versions', [])])


def configured_guard(source_dsn, *, realm_ids=(), explicit_cross=False, actor='local', database_name=None):
    """Trusted CLI/host configuration only; no connection selector in model input."""
    store = os.environ.get('PALIMPSEST_STORE_ID')
    configured = os.environ.get('PALIMPSEST_REALM_DSN') is not None or os.environ.get('PALIMPSEST_REALM_DSN_FILE') is not None
    if not store and not configured and not realm_ids and not explicit_cross and database_name is None:
        return None
    if not store:
        _fail('realm_configuration_required', 'trusted PALIMPSEST_STORE_ID 설정이 필요합니다.', 3)
    from .config import load_dsn, select_database
    catalog_dsn = (select_database(load_dsn('PALIMPSEST_REALM_DSN'), database_name) if configured
                   else select_database(source_dsn, database_name or 'palimpsest_realms'))
    return RealmI2KGuard(RealmCatalog(catalog_dsn), store, source_dsn, realm_ids=realm_ids,
                         explicit_cross=explicit_cross, actor=actor)


def execution_guard_configured(source_dsn, execution_id, *, actor='local', database_name=None):
    """Do not make unrelated N2E/K2K or legacy replay depend on Realm settings."""
    if not any(os.environ.get(key) is not None for key in ('PALIMPSEST_STORE_ID', 'PALIMPSEST_REALM_DSN', 'PALIMPSEST_REALM_DSN_FILE')) and database_name is None:
        return None
    from .canonical_store import connection
    with connection(source_dsn) as conn:
        row = conn.execute('''SELECT c.input_snapshot ? 'realm_scope' OR p.payload ? 'realm_i2k_policy' AS scoped
            FROM compiler_runtime.k_execution_contexts c JOIN compiler_runtime.operation_executions e USING(execution_id)
            JOIN compiler_runtime.profiles p USING(profile_id) WHERE c.execution_id=%s''', (request_id(execution_id),)).fetchone()
    return configured_guard(source_dsn, actor=actor, database_name=database_name) if row and row['scoped'] else None
