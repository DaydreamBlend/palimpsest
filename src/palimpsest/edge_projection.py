"""Read effective relations and ephemeral contradiction status without K writes.

Inputs are current accepted canonical node/edge rows. Exact old endpoints remain
on each edge; usable refs name the effective pair and its actual read-time basis.
Node annotations deliberately contain no opposing statement or source identity.
"""

from copy import deepcopy
import json

from .data import request_id
from .errors import PalimpsestError
from .i2k import digest


PROFILE = 'effective-relations-projection-v1'
_STATUSES = {'applicable', 'inapplicable', 'pending', 'endpoint_unusable', 'historical'}


def _plain(value):
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False, default=str))


def available(conn):
    row = conn.execute("""SELECT to_regprocedure('canonical_store.current_knowledge_edge_applicability(uuid)') AS name,
        EXISTS(SELECT 1 FROM compiler_runtime.schema_migrations WHERE left(version,5)='0017_') AS modern_schema""").fetchone()
    if row.get('modern_schema') and row['name'] is None:
        raise PalimpsestError('edge_projection_schema_incomplete', '새 관계 schema의 적용성 함수를 확인하세요.', 6)
    return row['name'] is not None


def _usable(node):
    return bool(node and node.get('current_revision_id', node['knode_revision_id']) == node['knode_revision_id']
        and node.get('lifecycle', 'accepted') == 'accepted'
        and node.get('record_disposition', 'accepted_new') in ('accepted_new', 'accepted_revision')
        and node.get('current_applicability', 'current_premises') == 'current_premises')


def resolve(conn, nodes, edges):
    """Resolve current pairs in the caller's consistent transaction; read only."""
    if not edges:
        return []
    modern = available(conn)
    state = conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton').fetchone()['version']
    by_node = {node['knode_id']: node for node in nodes}
    edge_ids = [request_id(edge['kedge_id']) for edge in edges]
    events = _plain(conn.execute('''SELECT * FROM canonical_store.knowledge_edge_applicability_events
        WHERE kedge_id=ANY(%s::uuid[]) ORDER BY event_order''', (edge_ids,)).fetchall())
    latest = {(row['semantic_kedge_revision_id'], row['from_knode_revision_id'], row['to_knode_revision_id']): row
              for row in events}
    fences = (_plain(conn.execute('''SELECT execution_id,semantic_kedge_revision_id,
        from_knode_revision_id,to_knode_revision_id,fence_order FROM compiler_runtime.n2e_review_targets
        WHERE semantic_kedge_revision_id=ANY(%s::uuid[]) ORDER BY fence_order''',
        ([edge['kedge_revision_id'] for edge in edges],)).fetchall()) if modern else [])
    pending = {(row['semantic_kedge_revision_id'], row['from_knode_revision_id'], row['to_knode_revision_id']): row
               for row in fences}
    result = []
    for edge in edges:
        source, target = by_node.get(edge['from_knode_id']), by_node.get(edge['to_knode_id'])
        source_ref = source['knode_revision_id'] if source else None
        target_ref = target['knode_revision_id'] if target else None
        revision = request_id(edge['kedge_revision_id'])
        pair = (revision, source_ref, target_ref)
        event, fence = latest.get(pair), pending.get(pair)
        original = (source_ref == edge['from_knode_revision_id'] and target_ref == edge['to_knode_revision_id'])
        endpoints_usable = _usable(source) and _usable(target)
        status = (conn.execute('SELECT canonical_store.current_knowledge_edge_applicability(%s) AS status',
            (revision,)).fetchone()['status'] if modern else
            ('applicable' if event['applicable'] else 'inapplicable') if event else
            'applicable' if original else 'pending')
        if status not in _STATUSES:
            raise PalimpsestError('edge_projection_status_invalid', '관계 적용성의 조회 상태를 확인하세요.', 6)
        if edge.get('current_revision_id', revision) != revision:
            status = 'historical'
        elif not endpoints_usable:
            status = 'endpoint_unusable'
        # The SQL resolver owns modern support checks. Keep an explicit fence
        # check here too: an uncertain/failed review is never a negative verdict.
        unresolved = bool(fence and fence['fence_order'] > (event['event_order'] if event else -1))
        if unresolved and status not in ('historical', 'endpoint_unusable'):
            status = 'pending'
        basis_type = 'applicability_event' if event else 'origin_acceptance' if original else None
        basis_ref = event['applicability_event_id'] if event else edge.get('origin_record_id') if original else None
        read_state = {'knowledge_state_version': state, 'applicability_status': status,
            'endpoint_support_signatures': [value.get('current_support_signature') if value else None for value in (source, target)],
            'pending_execution_id': fence['execution_id'] if unresolved else None,
            'pending_fence_order': fence['fence_order'] if unresolved else None}
        token = digest(read_state)
        effective_ref = ({'semantic_kedge_revision_id': revision,
            'from_knode_revision_id': request_id(source_ref), 'to_knode_revision_id': request_id(target_ref),
            'applicability_basis_type': basis_type, 'applicability_basis_ref': request_id(basis_ref),
            'relation_read_state_token': token} if status == 'applicable' and endpoints_usable
                             and source_ref and target_ref and basis_ref else None)
        applicable = True if status == 'applicable' else False if status == 'inapplicable' else None
        projection = {'schema_version': PROFILE, 'semantic_kedge_revision_id': revision,
            'effective_from_revision_id': source_ref, 'effective_to_revision_id': target_ref,
            'effective_edge_ref': effective_ref, 'applicability_basis_type': basis_type,
            'applicability_basis_ref': basis_ref, 'read_state': read_state}
        result.append({**deepcopy(edge), 'applicability_status': status, 'applicable': applicable,
            'usable': applicable is True and endpoints_usable and effective_ref is not None,
            'effective_from_revision_id': source_ref, 'effective_to_revision_id': target_ref,
            'effective_edge_ref': effective_ref, 'projection_key': digest(projection),
            'relation_read_state_token': token, 'pending_revalidation': unresolved,
            'pending_review_execution_id': fence['execution_id'] if unresolved else None,
            'applicability_event_id': event['applicability_event_id'] if event else None,
            'applicability_basis_type': basis_type, 'applicability_basis_ref': basis_ref,
            # Compatibility display fields; these never overwrite old endpoints.
            'applicability': 'not_applicable' if status == 'inapplicable' else status,
            'applicability_basis': 'event' if event else 'original_revision' if original else 'unverified_current_pair'})
    return result


def derive_contested(nodes, edges):
    """Both endpoints of a usable symmetric contradiction become contested.

    Uncontested means no such usable relation in this read, never accepted truth.
    This projection does not change lifecycle, payload, origin or revisions.
    """
    contested = {ref for edge in edges if edge.get('predicate') == 'contradicts'
                 and edge.get('usable') is True and edge.get('applicable') is True
                 for ref in (edge['effective_from_revision_id'], edge['effective_to_revision_id'])}
    return [{**deepcopy(node), 'epistemic_projection':
             'contested' if node['knode_revision_id'] in contested else 'uncontested'} for node in nodes]
