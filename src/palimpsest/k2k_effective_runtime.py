"""Exact effective relation inputs within the existing K2K transaction path."""

from copy import deepcopy
from hashlib import sha256
from importlib.resources import files

from psycopg.types.json import Jsonb

from .canonical_store import connection
from .data import request_id
from .errors import PalimpsestError
from .i2k import digest
from . import edge_projection
from . import k2k_effective as effective


def _fail(code):
    raise PalimpsestError(code, 'K2K가 소비할 관계의 정확한 Revision·현재 판정·endpoint 근거를 확인하세요.', 6)


def available(conn):
    return bool(conn.execute("SELECT to_regclass('compiler_runtime.k_input_effective_edges') AS relation").fetchone()['relation'])


def implementation():
    return {name: sha256(files('palimpsest').joinpath(name).read_bytes()).hexdigest()
            for name in ('k2k_effective.py', 'k2k_effective_runtime.py', 'edge_projection.py')}


def edge_ids(packet):
    return [edge['effective_edge_ref']['semantic_kedge_revision_id'] for edge in packet['effective_edges']]


def delivery(packet):
    effective.check_input(packet)
    return {'delivered_effective_edge_refs': [deepcopy(edge['effective_edge_ref']) for edge in packet['effective_edges']],
            'delivered_effective_input_sha256': packet['input_sha256']}


def _usable(edge):
    if edge['usable']:
        return
    if edge['applicability_status'] == 'inapplicable':
        _fail('k2k_edge_premise_inapplicable')
    if edge['applicability_status'] == 'historical':
        _fail('k2k_edge_revision_changed')
    _fail('k2k_edge_premise_pending')


def build_input(conn, runtime, owner, node_revisions, edge_revisions, *, allowed_data_ids=None):
    if not available(conn):
        _fail('effective_k2k_schema_required')
    selected_ids = [request_id(ref) for ref in edge_revisions]
    if not selected_ids or len(selected_ids) != len(set(selected_ids)):
        _fail('invalid_effective_k2k_edges')
    nodes = runtime._nodes(conn)
    current_edges = {edge['kedge_revision_id']: edge for edge in runtime._edges(conn)}
    if any(ref not in current_edges for ref in selected_ids):
        _fail('k2k_edge_revision_changed')
    resolved = edge_projection.resolve(conn, nodes, [current_edges[ref] for ref in selected_ids])
    by_revision = {node['knode_revision_id']: node for node in nodes}
    refs = [request_id(ref) for ref in node_revisions]
    if len(refs) != len(set(refs)):
        _fail('k2k_distinct_premises_required')
    inputs = []
    for edge in resolved:
        _usable(edge)
        pair = [edge['effective_from_revision_id'], edge['effective_to_revision_id']]
        for ref in pair:
            if ref not in refs:
                refs.append(ref)
        inputs.append({'kedge_id': edge['kedge_id'], 'predicate': edge['predicate'], 'qualifiers': deepcopy(edge['qualifiers']),
            'original_from_revision_id': edge['from_knode_revision_id'], 'original_to_revision_id': edge['to_knode_revision_id'],
            'effective_edge_ref': deepcopy(edge['effective_edge_ref']),
            'endpoint_support_signatures': [by_revision[ref]['current_support_signature'] for ref in pair]})
    # The legacy builder verifies accepted/current Node values, source ownership
    # and allowed source versions; every delivered endpoint is a real Node input.
    packet = runtime._inference_input(conn, owner, refs, allowed_data_ids=allowed_data_ids)
    return effective.build_input(packet['nodes'], inputs, owner)


def bind_inputs(conn, execution_id, packet):
    effective.check_input(packet)
    for ordinal, edge in enumerate(packet['effective_edges']):
        ref = edge['effective_edge_ref']
        event_id = ref['applicability_basis_ref'] if ref['applicability_basis_type'] == 'applicability_event' else None
        origin = (conn.execute('SELECT origin_record_id FROM canonical_store.knowledge_edge_applicability_events WHERE applicability_event_id=%s',
            (event_id,)).fetchone()['origin_record_id'] if event_id else ref['applicability_basis_ref'])
        conn.execute('''INSERT INTO compiler_runtime.k_input_effective_edges
            (execution_id,ordinal,kedge_id,semantic_kedge_revision_id,from_knode_revision_id,to_knode_revision_id,
             basis_type,basis_origin_record_id,applicability_event_id,relation_read_state_token,
             from_support_signature,to_support_signature,payload)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (execution_id, ordinal, edge['kedge_id'],
            ref['semantic_kedge_revision_id'], ref['from_knode_revision_id'], ref['to_knode_revision_id'],
            ref['applicability_basis_type'], origin, event_id, ref['relation_read_state_token'],
            *edge['endpoint_support_signatures'], Jsonb(edge)))


def bind_derivation(conn, job, record):
    packet = job['input_snapshot']['input']
    if packet.get('schema_version') != effective.INPUT_SCHEMA:
        return
    for ordinal in range(len(packet['effective_edges'])):
        conn.execute('''INSERT INTO canonical_store.knowledge_derivation_edge_premises
            (record_id,ordinal,execution_id,input_ordinal) VALUES (%s,%s,%s,%s)''',
            (record['record_id'], ordinal, job['execution_id'], ordinal))


def current_edge_revisions(conn, record_id):
    """Refresh the same logical relations; a new predicate never replaces one."""
    if not available(conn):
        return []
    return [str(row['current_revision_id']) for row in conn.execute('''SELECT e.current_revision_id
        FROM canonical_store.knowledge_derivation_edge_premises p
        JOIN compiler_runtime.k_input_effective_edges i ON i.execution_id=p.execution_id AND i.ordinal=p.input_ordinal
        JOIN canonical_store.knowledge_edges e USING(kedge_id)
        WHERE p.record_id=%s ORDER BY p.ordinal''', (record_id,)).fetchall()]


def consumers(conn, kedge_id):
    if not available(conn):
        return []
    return conn.execute('''SELECT DISTINCT d.record_id,d.result_node_revision_id,n.knode_id
        FROM canonical_store.knowledge_derivation_edge_premises p
        JOIN compiler_runtime.k_input_effective_edges i ON i.execution_id=p.execution_id AND i.ordinal=p.input_ordinal
        JOIN canonical_store.knowledge_derivations d USING(record_id)
        JOIN canonical_store.knowledge_node_revisions r ON r.knode_revision_id=d.result_node_revision_id
        JOIN canonical_store.knowledge_nodes n ON n.knode_id=r.knode_id
        WHERE i.kedge_id=%s AND n.current_revision_id=r.knode_revision_id
            AND canonical_store.current_k_support_record(r.knode_revision_id)=d.record_id ORDER BY d.record_id''',
        (kedge_id,)).fetchall()


def stable_edges(conn, runtime, node_ids):
    """Work identity uses meaning/pair/basis/support, never a global read token."""
    if not available(conn):
        return []
    allowed = set(node_ids)
    edges = [edge for edge in runtime._edges(conn) if edge['from_knode_id'] in allowed and edge['to_knode_id'] in allowed]
    projected = edge_projection.resolve(conn, runtime._nodes(conn), edges)
    return [{'kedge_id': edge['kedge_id'], 'semantic_kedge_revision_id': edge['kedge_revision_id'],
        'from_knode_revision_id': edge['effective_from_revision_id'], 'to_knode_revision_id': edge['effective_to_revision_id'],
        'applicability_basis_type': edge['applicability_basis_type'], 'applicability_basis_ref': edge['applicability_basis_ref']}
        for edge in projected if edge['usable']]


def required_edge_state(conn, runtime, record_id):
    """Retain required relations even when unavailable; never drop a premise."""
    refs = current_edge_revisions(conn, record_id)
    if not refs:
        return []
    indexed = {edge['kedge_revision_id']: edge for edge in runtime._edges(conn)}
    return [{'kedge_id': edge['kedge_id'], 'semantic_kedge_revision_id': edge['kedge_revision_id'],
        'from_knode_revision_id': edge['effective_from_revision_id'], 'to_knode_revision_id': edge['effective_to_revision_id'],
        'status': edge['applicability_status'], 'basis_type': edge['applicability_basis_type'],
        'basis_ref': edge['applicability_basis_ref']} for edge in edge_projection.resolve(
            conn, runtime._nodes(conn), [indexed[ref] for ref in refs])]


def prepare_call(runtime, execution_id, phase, directory):
    from . import k2k
    from .wiki_projection_store import ProjectionStore
    job = runtime.show(execution_id)
    if job['operation'] != 'k2k' or phase not in ('generator', 'validator') or job['state'] != ('prepared' if phase == 'generator' else 'proposed'):
        _fail('knowledge_call_not_ready')
    context = runtime.validation_context(execution_id) if phase == 'validator' else None
    packet = job['input_snapshot']['input']
    prompt, schema = k2k.generation_request(job['input_snapshot']) if phase == 'generator' else k2k.validation_request(context)
    request = {'prompt': prompt, 'schema': schema, 'images': [], 'output_file': phase + '-response.json',
        'input_sha256': job['input_digest'] if phase == 'generator' else context['validation_context_sha'],
        'delivered_knowledge_revision_ids': k2k.check_input(packet)}
    if packet.get('schema_version') == effective.INPUT_SCHEMA:
        request.update(delivery(packet))
    if job['input_snapshot'].get('revision_target'):
        request['delivered_revision_target_id'] = job['input_snapshot']['revision_target']['expected_revision_id']
    if job['input_snapshot'].get('revalidation_target'):
        request['delivered_revalidation_target_sha256'] = job['input_snapshot']['revalidation_target']['target_sha256']
    if job['input_snapshot'].get('data_versions'):
        request['delivered_data_version_ids'] = [value['version_id'] for value in job['input_snapshot']['data_versions']]
    binding = {'execution_id': job['execution_id'], 'phase': phase, 'input_digest': job['input_digest'],
               'profile': job['profile'], 'request_sha256': digest(request)}
    store = ProjectionStore(directory)
    with store.locked():
        prior = store.read_json(phase + '-binding.json')
        if prior is not None:
            if prior != binding or store.read_json(phase + '-request.json') != request:
                _fail('knowledge_call_directory_conflict')
        else:
            store.write_json(phase + '-request.json', request)
            store.write_json(phase + '-binding.json', binding)
    return {'execution_id': execution_id, 'phase': phase, 'request_file': str(store.root / (phase + '-request.json')),
            'request_sha256': digest(request), 'actual_delivery': False, 'replayed': prior is not None}
