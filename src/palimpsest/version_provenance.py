"""Explicit execution/version support, separate from generation and applicability.

Version membership of a Data alone never backfills a Knowledge origin. Immutable
bindings can enter frozen Runtime packets; moving series heads are graph views.
"""

from collections import defaultdict
from copy import deepcopy
import json


def load(conn):
    if conn.execute("SELECT to_regclass('canonical_store.data_versions') AS relation").fetchone()['relation'] is None:
        return None

    def rows(sql):
        return json.loads(json.dumps(conn.execute(sql).fetchall(), default=str, ensure_ascii=False))

    versions = rows('SELECT * FROM canonical_store.data_versions ORDER BY version_id')
    series = rows('SELECT series_id,head_version_id FROM canonical_store.data_series ORDER BY series_id')
    links = rows('''SELECT r.record_id,r.result_node_revision_id,r.result_edge_revision_id,e.operation,b.version_id
        FROM compiler_runtime.k_compilation_records r
        JOIN compiler_runtime.operation_executions e USING(execution_id)
        JOIN compiler_runtime.k_execution_data_versions b USING(execution_id)
        WHERE (r.result_node_revision_id IS NOT NULL OR r.result_edge_revision_id IS NOT NULL)
          AND r.disposition IN ('accepted_new','accepted_revision','reused','no_material_delta')
        ORDER BY r.record_id,b.version_id''')
    by_revision, by_edge_revision = defaultdict(list), defaultdict(list)
    supports = {}
    for row in links:
        node_case = row.get('result_node_revision_id') is not None
        revision = row['result_node_revision_id'] if node_case else row['result_edge_revision_id']
        key = (node_case, revision, row['record_id'])
        if key not in supports:
            support = {'record_id': row['record_id'], 'operation': row['operation'], 'version_ids': []}
            supports[key] = support
            (by_revision if node_case else by_edge_revision)[revision].append(support)
        supports[key]['version_ids'].append(row['version_id'])
    return {'versions': {row['version_id']: row for row in versions},
            'heads': {row['series_id']: row['head_version_id'] for row in series},
            'by_revision': dict(by_revision), 'by_edge_revision': dict(by_edge_revision)}


def annotate(state, node):
    """Return immutable annotations for the exact Revision without changing node."""
    supports = []
    if state is not None:
        if ('knode_revision_id' in node) == ('kedge_revision_id' in node):
            raise ValueError('exact_typed_knowledge_revision_required')
        node_case = 'knode_revision_id' in node
        mapping = state['by_revision'] if node_case else state.get('by_edge_revision', {})
        identifier = node['knode_revision_id'] if node_case else node['kedge_revision_id']
        for support in mapping.get(identifier, []):
            supports.append({**deepcopy(support),
                'versions': [deepcopy(state['versions'][identifier]) for identifier in support['version_ids']]})
    origin = next((support['versions'] for support in supports
                   if support['record_id'] == node['origin_record_id']), [])
    return {'origin_data_versions': deepcopy(origin), 'data_version_supports': supports}


def graph_view(state, node):
    """Source-version currentness is not Knowledge truth or premise applicability."""
    supports = annotate(state, node)['data_version_supports']
    current = any(support['versions'] and all(
        state['heads'].get(version['series_id']) == version['version_id'] for version in support['versions'])
        for support in supports)
    series = sorted({version['series_id'] for support in supports for version in support['versions']})
    return {'source_version_status': 'current' if current else 'historical' if supports else 'untracked',
            'source_version_current_heads': [{'series_id': identifier, 'version_id': state['heads'].get(identifier)}
                                             for identifier in series]}
