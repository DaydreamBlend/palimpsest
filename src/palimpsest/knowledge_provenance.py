"""Read exact derivation dependencies without manufacturing direct I grounding."""

from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
import json

from .errors import PalimpsestError


EFFECTIVE_INFERENCE_PROFILE = 'knowledge-inference-effective-v1'


def data_reference_metadata(node):
    """Keep D2K references in generic K catalogs without exporting raw D quotes.

    Existing I fields and statements are unchanged. Explicit D2K/query delivery
    uses verified views separately; this helper is only a provenance projection.
    """
    result = deepcopy(node)
    for field in ('direct_data_groundings', 'transitive_data_refs', 'current_transitive_data_refs'):
        for reference in result.get(field, []):
            if not isinstance(reference, dict):
                continue
            for value in (reference, reference.get('evidence', {})):
                if isinstance(value, dict) and isinstance(value.get('quote'), str):
                    quote = value.pop('quote')
                    value.update(quote_sha256=sha256(quote.encode('utf-8')).hexdigest(), quote_character_count=len(quote))
    return result


def data_grounding(row):
    """Expose a standalone D2K support leaf, never an Information reference."""
    evidence = deepcopy(row['evidence'])
    if evidence['data_id'] != row['data_id'] or evidence['view_id'] != row['view_id']:
        raise PalimpsestError('data_grounding_binding_changed', '원문 근거의 Data·view 결속이 다릅니다.', 6)
    return {**evidence, **{key: row[key] for key in ('grounding_id', 'node_revision_id', 'origin_record_id')},
            'grounding_type': 'data'}


def verify_data_grounding(row, view, raw, *, image=None):
    """Verify immutable bytes and the canonical citation without D2I or writes.

    PDF renderer verification belongs to the accepted D2K preparation. This
    consumer checks that the exact retained original and rendered asset still
    match that canonical view; it does not substitute a new rendering.
    """
    from . import d2k
    source = d2k.check_view(view)
    if len(raw) != source['original_byte_size'] or sha256(raw).hexdigest() != source['data_id']:
        raise PalimpsestError('data_grounding_original_changed', '등록 원본의 hash·크기가 다릅니다.', 6)
    proposal = {'view_id': source['view_id'], 'source_role': row['evidence']['source_role']}
    if source['kind'] == 'text':
        if d2k.text_view(raw, view_id=source['view_id'], data_id=source['data_id'],
                byte_start=source['locator']['byte_start'], byte_end=source['locator']['byte_end']) != source:
            raise PalimpsestError('data_grounding_view_changed', '보존된 원문 범위가 원본과 다릅니다.', 6)
        proposal.update({key: row['evidence'][key] for key in ('char_start', 'char_end')})
    elif (b'%PDF-' not in raw[:1024] or image is None or len(image) != source['image_byte_size']
            or sha256(image).hexdigest() != source['image_sha256']):
        raise PalimpsestError('data_grounding_image_changed', '보존된 PDF 원문 이미지가 다릅니다.', 6)
    packet = d2k.build_input(source['data_id'], media_type='application/pdf' if source['kind'] == 'pdf_page' else 'text/plain',
                            original_byte_size=source['original_byte_size'], views=[source])
    if d2k.normalize_evidence(proposal, packet) != row['evidence']:
        raise PalimpsestError('data_grounding_citation_changed', '보존된 원문 인용이 다릅니다.', 6)
    return data_grounding(row), source


def load(conn):
    if conn.execute("SELECT to_regclass('canonical_store.knowledge_derivations') AS relation").fetchone()['relation'] is None:
        return None
    def rows(sql):
        return json.loads(json.dumps(conn.execute(sql).fetchall(), default=str, ensure_ascii=False))
    revisions = rows('''SELECT r.knode_revision_id,r.knode_id,r.origin_record_id,n.current_revision_id
        FROM canonical_store.knowledge_node_revisions r JOIN canonical_store.knowledge_nodes n USING(knode_id)''')
    derivations = rows('SELECT * FROM canonical_store.knowledge_derivations ORDER BY record_id')
    premises = rows('SELECT * FROM canonical_store.knowledge_derivation_premises ORDER BY record_id,ordinal')
    groundings = rows('''SELECT g.*,i.data_id,r.execution_id AS source_execution_id
        FROM canonical_store.knowledge_node_groundings g JOIN canonical_store.information i USING(information_id)
        JOIN compiler_runtime.records r ON r.record_id=i.origin_record_id ORDER BY grounding_id''')
    data_rows = (rows('SELECT * FROM canonical_store.knowledge_data_groundings ORDER BY grounding_id')
        if conn.execute("SELECT to_regclass('canonical_store.knowledge_data_groundings') AS relation").fetchone()['relation'] else None)
    by_record, by_result, edges, grounding_map = {}, defaultdict(list), defaultdict(list), defaultdict(list)
    for row in derivations:
        row['premise_revision_ids'] = []
        by_record[row['record_id']] = row
        by_result[row['result_node_revision_id']].append(row)
    for row in premises:
        derivation = by_record[row['record_id']]
        derivation['premise_revision_ids'].append(row['premise_node_revision_id'])
        edges[derivation['result_node_revision_id']].append(row['premise_node_revision_id'])
    for row in groundings:
        grounding_map[row['node_revision_id']].append(row)
    result = {'revisions': {r['knode_revision_id']: r for r in revisions}, 'by_record': by_record,
              'by_result': by_result, 'edges': edges, 'groundings': grounding_map}
    if data_rows is not None:
        result['data_groundings'] = defaultdict(list)
        for row in data_rows:
            result['data_groundings'][row['node_revision_id']].append(data_grounding(row))
    if conn.execute("SELECT to_regclass('canonical_store.knowledge_current_supports') AS relation").fetchone()['relation']:
        result['current_supports'] = {}
        for row in rows('SELECT * FROM canonical_store.knowledge_current_supports ORDER BY event_order'):
            result['current_supports'][row['node_revision_id']] = row
        result['support_refs'] = defaultdict(dict)
        for row in rows('SELECT * FROM canonical_store.knowledge_derivation_support_refs ORDER BY record_id,premise_node_revision_id'):
            result['support_refs'][row['record_id']][row['premise_node_revision_id']] = row['support_record_id']
    if conn.execute("SELECT to_regclass('canonical_store.knowledge_derivation_edge_premises') AS relation").fetchone()['relation']:
        result['edge_current'] = {}
        for row in rows('''SELECT p.record_id,p.ordinal,p.execution_id,p.input_ordinal,i.payload,
            compiler_runtime.k2k_edge_input_current(p.execution_id,p.input_ordinal) AS current
            FROM canonical_store.knowledge_derivation_edge_premises p
            JOIN compiler_runtime.k_input_effective_edges i
                ON i.execution_id=p.execution_id AND i.ordinal=p.input_ordinal
            ORDER BY p.record_id,p.ordinal'''):
            premise = {**row['payload'], **{key: row[key] for key in ('ordinal', 'execution_id', 'input_ordinal')}}
            by_record[row['record_id']].setdefault('effective_edge_premises', []).append(premise)
            result['edge_current'][(row['execution_id'], row['input_ordinal'])] = row['current'] is True
    return result


def ancestors(state, revision_id):
    """All recorded premise dependencies; no depth/size cutoff or proof by count."""
    found, pending = set(), list(state['edges'].get(revision_id, []))
    while pending:
        current = pending.pop()
        if current in found:
            continue
        found.add(current)
        pending.extend(state['edges'].get(current, []))
    return found


def _origin_stale(state, revision_id):
    stale, seen, pending = set(), set(), [revision_id]
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        revision = state['revisions'][current]
        if revision['current_revision_id'] != current:
            stale.add(current)
        origin = state['by_record'].get(revision['origin_record_id'])
        if origin:
            pending.extend(origin['premise_revision_ids'])
    return sorted(stale)


def support_record(state, revision_id):
    """Current explicit support is separate from the immutable generation origin."""
    explicit = state.get('current_supports', {}).get(revision_id)
    if explicit:
        return explicit['record_id']
    origin = state['revisions'][revision_id]['origin_record_id']
    return origin if origin in state['by_record'] else None


def current_route(state, revision_id, *, record_id=None):
    """Trace exact active support, detecting stale consumed support and cycles.

    A changed receipt is a dependency change even when its KRevision is unchanged.
    Historical derivations without receipt refs retain their original premise route.
    """
    seen, active, stale, route, edge_refs, stale_edges = set(), set(), set(), {}, [], []
    root_record_id = record_id
    pending = [(revision_id, False)]
    while pending:
        current, leaving = pending.pop()
        if leaving:
            active.discard(current)
            continue
        if current in active:
            stale.add(current)
            continue
        if current in seen:
            continue
        seen.add(current)
        active.add(current)
        pending.append((current, True))
        revision = state['revisions'].get(current)
        if revision is None or revision['current_revision_id'] != current:
            stale.add(current)
        if revision is None:
            continue
        record_id = root_record_id if current == revision_id and root_record_id is not None else support_record(state, current)
        route[current] = record_id
        derivation = state['by_record'].get(record_id)
        if derivation:
            for edge in derivation.get('effective_edge_premises', []):
                frozen_edge = {'record_id': record_id, **deepcopy(edge)}
                edge_refs.append(frozen_edge)
                if state.get('edge_current', {}).get((edge['execution_id'], edge['input_ordinal'])) is not True:
                    stale_edges.append(frozen_edge)
            frozen = state.get('support_refs', {}).get(record_id)
            for premise in derivation['premise_revision_ids']:
                # None and no row differ: old history predates support binding.
                if frozen is not None and (premise not in frozen or frozen[premise] != support_record(state, premise)):
                    stale.add(premise)
                elif frozen is None and support_record(state, premise) != (
                        state['revisions'][premise]['origin_record_id'] if state['revisions'][premise]['origin_record_id'] in state['by_record'] else None):
                    stale.add(premise)
                pending.append((premise, False))
    result = {'records': route, 'stale_revision_ids': sorted(stale)}
    if edge_refs:
        key = lambda value: (value['record_id'], value['ordinal'])
        result.update(effective_edge_refs=sorted(edge_refs, key=key), stale_effective_edge_refs=sorted(stale_edges, key=key))
    return result


def describe(state, revision_id):
    revision = state['revisions'][revision_id]
    origin = state['by_record'].get(revision['origin_record_id'])
    upstream = ancestors(state, revision_id)
    edge_history = any(row.get('effective_edge_premises') for ref in upstream | {revision_id}
                       for row in state['by_result'].get(ref, []))
    transitive = [deepcopy(g) for ref in sorted(upstream) for g in state['groundings'].get(ref, [])]
    direct = deepcopy(state['groundings'].get(revision_id, []))
    derivations = []
    for row in state['by_result'].get(revision_id, []):
        stale = sorted({ref for premise in row['premise_revision_ids'] for ref in _origin_stale(state, premise)})
        projected = {**deepcopy(row), 'stale_premise_revision_ids': stale,
                     'current_applicability': 'needs_revalidation' if stale else 'current_premises'}
        if edge_history and 'edge_current' in state:
            selected = current_route(state, revision_id, record_id=row['record_id'])
            projected['current_applicability'] = ('needs_revalidation' if selected['stale_revision_ids']
                or selected.get('stale_effective_edge_refs') else 'current_premises')
            if selected.get('effective_edge_refs'):
                projected['stale_effective_edge_refs'] = selected['stale_effective_edge_refs']
        derivations.append(projected)
    result = {'direct_groundings': direct, 'transitive_source_refs': transitive,
              'derivations': derivations, 'derivation_depth': origin['derivation_depth'] if origin else 0,
              'source_data_ids': sorted({g['data_id'] for g in direct + transitive}),
              'stale_premise_revision_ids': _origin_stale(state, revision_id) if origin else []}
    result['current_applicability'] = ('needs_revalidation' if result['stale_premise_revision_ids'] else 'current_premises')
    if 'current_supports' in state:
        active = current_route(state, revision_id)
        current_refs = sorted(set(active['records']) - {revision_id})
        result.update(current_support_record_id=support_record(state, revision_id),
            current_support_event=deepcopy(state['current_supports'].get(revision_id)),
            current_support_signature=sha256(json.dumps(active['records'], sort_keys=True).encode()).hexdigest(),
            current_stale_premise_revision_ids=active['stale_revision_ids'],
            current_transitive_source_refs=[deepcopy(g) for ref in current_refs for g in state['groundings'].get(ref, [])],
            current_transitive_data_refs=[deepcopy(g) for ref in current_refs for g in state.get('data_groundings', {}).get(ref, [])])
        result['current_applicability'] = ('needs_revalidation' if active['stale_revision_ids']
            or active.get('stale_effective_edge_refs') else 'current_premises')
        if active.get('effective_edge_refs'):
            result.update(current_effective_edge_refs=active['effective_edge_refs'],
                          current_stale_effective_edge_refs=active['stale_effective_edge_refs'])
    if 'data_groundings' in state:
        data = state['data_groundings']
        result.update(direct_data_groundings=deepcopy(data.get(revision_id, [])),
            transitive_data_refs=[deepcopy(g) for ref in sorted(upstream) for g in data.get(ref, [])])
        result['source_data_ids'] = sorted(set(result['source_data_ids']) | {
            g['data_id'] for g in result['direct_data_groundings'] + result['transitive_data_refs']})
        if origin is None and any(g['origin_record_id'] == revision['origin_record_id'] for g in result['direct_data_groundings']):
            result['generation_origin'] = {'origin_operation': 'd2k', 'is_inferred': False,
                'origin_record_id': revision['origin_record_id'], 'claim_basis': 'explicit_source_content'}
    if origin:
        result['generation_origin'] = {'origin_operation': 'k2k', 'is_inferred': True,
            'origin_record_id': origin['record_id'], 'inference_type': origin['inference_type'],
            'premise_revision_ids': list(origin['premise_revision_ids']),
            'assumptions': deepcopy(origin['assumptions']), 'limitations': deepcopy(origin['limitations']),
            'derivation_basis': origin['derivation_basis'], 'validation': deepcopy(origin['validation'])}
        if origin.get('effective_edge_premises'):
            result['origin_effective_edge_refs'] = deepcopy(origin['effective_edge_premises'])
            result['generation_origin'].update(knowledge_inference_profile=EFFECTIVE_INFERENCE_PROFILE,
                effective_edge_premises=deepcopy(origin['effective_edge_premises']))
    if result.get('origin_effective_edge_refs') or result.get('current_effective_edge_refs'):
        result['knowledge_inference_profile'] = EFFECTIVE_INFERENCE_PROFILE
        result.setdefault('current_effective_edge_refs', [])
        result.setdefault('current_stale_effective_edge_refs', [])
    return result
