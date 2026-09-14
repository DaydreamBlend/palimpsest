"""Select current Realm defaults once, then retain exact execution scope."""

from copy import deepcopy

from .data import data_id, request_id
from .errors import PalimpsestError
from .realms import _digest, _text, normalize_members


PROFILE = 'realm-automation-scope-v1'


def _fail(code, message):
    raise PalimpsestError(code, message, 2)


def common_realm(revisions, sources, preferred=()):
    """One current common collection; initial classification breaks ties only."""
    eligible = []
    for revision in revisions:
        members = {(m['store_id'], m['member_kind'], m['member_id'])
                   for m in normalize_members(revision['members'])}
        if sources and all((source['store_id'], 'data', source['data_id']) in members
                or (source.get('series_id') and (source['store_id'], 'data_series', source['series_id']) in members)
                for source in sources):
            eligible.append(revision)
    if len(eligible) == 1:
        return eligible[0]
    if not eligible:
        _fail('realm_source_outside_scope', '입력 자료가 함께 속한 Realm이 없습니다. 교차할 Realm을 명시적으로 선택하세요.')
    preferred = [revision for revision in eligible if revision['realm_id'] in preferred]
    if len(preferred) == 1:
        return preferred[0]
    _fail('realm_selection_ambiguous', '공통 Realm이 여러 개입니다. 이번 작업의 Realm을 선택하세요.')


def default_i2k_realm(conn, catalog, sources):
    owners = sorted({source['data_id'] for source in sources})
    rows = conn.execute('''SELECT data_id,external_metadata FROM canonical_store.data_acquisitions
        WHERE data_id=ANY(%s::text[]) AND external_metadata ? 'realm_registration' ''', (owners,)).fetchall()
    from .realm_registration import registration
    initial = {}
    for row in rows:
        selection = registration(row)
        if selection and any(source['data_id'] == row['data_id'] and source['store_id'] == selection['store_id'] for source in sources):
            initial.setdefault(row['data_id'], set()).add(selection['realm_id'])
    preferred = set.intersection(*(initial.get(owner, set()) for owner in owners)) if owners else set()
    return common_realm(catalog.catalog()['realms'], sources, preferred)


def root_realm_ids(snapshots):
    """Infer only a single Realm present in every root's actual execution scope."""
    chosen = set()
    for snapshot in snapshots:
        scope = snapshot.get('realm_scope') or snapshot.get('propagation_scope', {}).get('scope', {}).get('realm_scope')
        refs = scope.get('realm_revisions') if isinstance(scope, dict) else None
        if not isinstance(refs, list) or len(refs) != 1:
            _fail('realm_required', '자동 전파의 Realm을 확인할 수 없습니다. --realm-id로 선택하세요.')
        chosen.add(request_id(refs[0]['realm_id']))
    if len(chosen) != 1:
        _fail('realm_crossing_requires_explicit_selection', '서로 다른 Realm의 전파는 교차할 Realm을 명시적으로 선택하세요.')
    return sorted(chosen)


class PropagationRealmGuard:
    def __init__(self, catalog, store_id, source_dsn, *, realm_ids=(), explicit_cross=False, actor='local'):
        self.catalog, self.store_id, self.source_dsn = catalog, request_id(store_id), source_dsn
        self.realm_ids = [request_id(value) for value in realm_ids]
        if len(self.realm_ids) != len(set(self.realm_ids)) or type(explicit_cross) is not bool:
            _fail('invalid_realm_selection', '정확한 Realm 선택을 확인하세요.')
        self.explicit_cross, self.actor = explicit_cross, _text(actor, 'actor')

    def prepare(self, conn, root_records, *, allowed_data_ids=None, version_ids=None, version_mode='current'):
        if version_mode not in ('current', 'pinned'):
            _fail('invalid_data_version_mode', '자료 버전 선택을 확인하세요.')
        selected = self.realm_ids
        if not selected:
            rows = conn.execute('''SELECT c.input_snapshot FROM compiler_runtime.k_compilation_records r
                JOIN compiler_runtime.k_execution_contexts c USING(execution_id)
                WHERE r.record_id=ANY(%s::uuid[]) ORDER BY r.record_id''', (root_records,)).fetchall()
            if len(rows) != len(root_records):
                _fail('propagation_root_not_accepted', '정확한 전파 시작 Record를 확인하세요.')
            selected = root_realm_ids([row['input_snapshot'] for row in rows])
        if len(selected) > 1 and not self.explicit_cross:
            _fail('realm_crossing_requires_explicit_selection', '여러 Realm의 자동 전파에는 명시적인 교차 선택이 필요합니다.')
        current = {revision['realm_id']: revision for revision in self.catalog.catalog()['realms']}
        if any(identifier not in current for identifier in selected):
            _fail('realm_not_found', '선택한 Realm을 찾을 수 없습니다.')
        revisions = [current[identifier] for identifier in sorted(selected)]
        members = [member for revision in revisions for member in normalize_members(revision['members'])
                   if member['store_id'] == self.store_id]
        direct = {member['member_id'] for member in members if member['member_kind'] == 'data'}
        series = {member['member_id'] for member in members if member['member_kind'] == 'data_series'}
        from .data_versions import immutable_versions
        explicit_versions = immutable_versions(conn, version_ids or [])
        heads = conn.execute('''SELECT s.series_id,s.head_version_id,v.data_id FROM canonical_store.data_series s
            LEFT JOIN canonical_store.data_versions v ON v.version_id=s.head_version_id
            WHERE s.series_id=ANY(%s::uuid[]) ORDER BY s.series_id''', (sorted(series),)).fetchall() if series else []
        if {str(row['series_id']) for row in heads} != series:
            _fail('realm_member_not_found', 'Realm의 자료 계열이 선택한 저장소에 없습니다.')
        resolved = []
        for head in heads:
            chosen = [version for version in explicit_versions if version['series_id'] == str(head['series_id'])]
            if version_mode == 'current' and any(version['version_id'] != str(head['head_version_id']) for version in chosen):
                _fail('data_version_head_changed', '현재 모드에는 자료 계열의 현재 버전을 선택해야 합니다.')
            if chosen:
                resolved.extend(chosen)
            elif head['head_version_id'] is not None:
                resolved.extend(immutable_versions(conn, [str(head['head_version_id'])]))
        eligible = direct | {version['data_id'] for version in resolved}
        registered = conn.execute('SELECT data_id FROM canonical_store.data WHERE data_id=ANY(%s::text[])',
                                  (sorted(eligible),)).fetchall()
        if {row['data_id'] for row in registered} != eligible:
            _fail('realm_member_not_found', 'Realm의 Data가 선택한 저장소에 없습니다.')
        allowed = sorted(eligible if allowed_data_ids is None else {data_id(owner) for owner in allowed_data_ids})
        if not allowed or not set(allowed) <= eligible:
            _fail('realm_source_outside_scope', '전파할 자료는 선택한 Realm에 속해야 합니다.')
        if allowed_data_ids is not None and len(allowed_data_ids) != len(allowed):
            _fail('duplicate_propagation_scope', '동일한 Data를 중복 선택할 수 없습니다.')
        if any(version['data_id'] not in allowed for version in explicit_versions):
            _fail('propagation_version_scope_mismatch', '선택한 자료 밖의 버전이 포함됐습니다.')
        from .realm_registration import verify_ready
        verify_ready(conn, allowed, self.catalog, self.store_id)
        scope = {'schema_version': PROFILE, 'store_id': self.store_id,
            'realm_revisions': [{'realm_id': revision['realm_id'], 'revision_id': revision['revision_id']} for revision in revisions],
            'allowed_data_ids': allowed, 'series_versions': sorted(
                [{'series_id': version['series_id'], 'version_id': version['version_id'], 'data_id': version['data_id']}
                 for version in resolved if version['data_id'] in allowed], key=lambda value: (value['series_id'], value['version_id'])),
            'requested_data_version_ids': sorted(version_ids) if version_ids is not None else None,
            'explicit_cross': self.explicit_cross, 'actor': self.actor}
        return {**scope, 'scope_sha256': _digest(scope)}


def configured_guard(source_dsn, **kwargs):
    from .realm_i2k import configured_guard as configured_i2k_guard
    guard = configured_i2k_guard(source_dsn, **kwargs)
    return (PropagationRealmGuard(guard.catalog, guard.store_id, source_dsn, realm_ids=guard.realm_ids,
        explicit_cross=guard.explicit_cross, actor=guard.actor) if guard else None)


def replay_scope(run, *, roots, allowed_data_ids, wiki_ids, version_ids, version_mode, discovery, guard=None):
    """A retry reuses frozen scope even after membership/head/projection changes."""
    scope = run['scope']
    requested_versions = scope.get('realm_scope', {}).get('requested_data_version_ids')
    comparisons = [(roots, scope['root_record_ids']), (allowed_data_ids, scope['allowed_data_ids']),
                   (wiki_ids, scope['wiki_ids']),
                   (version_ids, requested_versions if requested_versions is not None
                    else [version['version_id'] for version in scope['data_versions']])]
    if (any(actual is not None and sorted(actual) != sorted(expected) for actual, expected in comparisons)
            or version_mode != scope['data_version_mode'] or discovery != run['policy']['discovery']):
        _fail('propagation_request_conflict', '동일한 전파 요청의 입력 선택이 변경됐습니다.')
    selected = scope.get('realm_scope')
    if guard is not None:
        if guard.realm_ids and (not selected or sorted(guard.realm_ids) != sorted(ref['realm_id'] for ref in selected['realm_revisions'])):
            _fail('propagation_request_conflict', '동일한 전파 요청의 Realm을 변경할 수 없습니다.')
        if selected and (guard.store_id != selected['store_id'] or (guard.explicit_cross and not selected['explicit_cross'])):
            _fail('propagation_request_conflict', '동일한 전파 요청의 저장소·교차 범위를 변경할 수 없습니다.')
        if guard.explicit_cross and selected is None:
            _fail('propagation_request_conflict', '과거 요청에 새 Realm 정책을 덧붙일 수 없습니다.')
    return deepcopy(scope), deepcopy(run['policy'])
