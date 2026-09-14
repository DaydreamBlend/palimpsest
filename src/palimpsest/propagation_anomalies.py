"""Recognize an accepted return to an earlier result under unchanged premises.

This is an operational checkpoint after canonical acceptance, not an epistemic
rejection or a compilation cache. Comparison catalogs may differ; their hashes
are retained without claiming full prompt equivalence. No state is changed here.
"""

from copy import deepcopy
import json

from .data import data_id, request_id
from .errors import PalimpsestError
from .i2k import digest


PROFILE = 'semantic-return-under-unchanged-premises-v1'


def _fail(code='propagation_anomaly_context_unavailable'):
    raise PalimpsestError(code, '반복 결과 진단의 정확한 전제·Revision·지원 경로·정책을 확인하세요.', 6)


def _plain(value):
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False, default=str))


def _enabled(run):
    policy = run.get('policy', {}).get('anomaly_detection')
    if policy is None:
        return False
    if policy != PROFILE:
        _fail('unsupported_propagation_anomaly_profile')
    return True


def premise_signature(node):
    """Only a complete new support binding can establish unchanged premises."""
    keys = ('knode_id', 'knode_revision_id', 'kind', 'content_fingerprint',
            'identity_scope', 'source_data_id', 'current_support_record_id', 'current_support_signature')
    if not isinstance(node, dict) or not set(keys) <= node.keys():
        _fail()
    for key in ('knode_id', 'knode_revision_id'):
        request_id(node[key])
    for key in ('content_fingerprint', 'current_support_signature'):
        data_id(node[key])
    if node['current_support_record_id'] is not None:
        request_id(node['current_support_record_id'])
    if node['source_data_id'] is not None:
        data_id(node['source_data_id'])
    if node['kind'] not in ('observation', 'proposition'):
        _fail()
    return {key: deepcopy(node[key]) for key in keys}


def basis(job, kind, logical_id, *, edge_revision_id=None, edge_content_fingerprint=None):
    """Exclude target comparison and catalog bookkeeping, not real premises."""
    snapshot = job['input_snapshot']
    if (kind not in ('node', 'edge') or job['operation'] != ('k2k' if kind == 'node' else 'n2e')
            or not isinstance(job.get('profile'), dict) or not isinstance(snapshot.get('input', {}).get('nodes'), list)):
        _fail()
    request_id(logical_id)
    data_id(job['data_id'])
    nodes = snapshot['input']['nodes']
    if len(nodes) < 2 or len({node['knode_id'] for node in nodes}) != len(nodes):
        _fail()
    value = {'schema_version': PROFILE, 'operation': job['operation'], 'target_kind': kind,
        'target_logical_id': logical_id, 'operation_data_id': job['data_id'],
        'profile': deepcopy(job['profile']), 'premises': [premise_signature(node) for node in nodes],
        'data_versions': deepcopy(snapshot.get('data_versions', [])),
        'data_version_mode': snapshot.get('data_version_mode')}
    if kind == 'node' and logical_id in {node['knode_id'] for node in nodes}:
        _fail()
    if kind == 'edge':
        request_id(edge_revision_id)
        data_id(edge_content_fingerprint)
        value.update(semantic_edge_revision_id=edge_revision_id, semantic_edge_content_fingerprint=edge_content_fingerprint)
    return _plain(value)


def _audit(job):
    snapshot = job['input_snapshot']
    return {'input_digest': job['input_digest'], 'profile_sha256': digest(job['profile']),
        'comparison_catalog_sha256': digest({'nodes': snapshot.get('existing_nodes', []),
                                             'edges': snapshot.get('existing_edges', [])})}


def detect_return(previous, current, bridges=()):
    """Two actual inverse material transitions, with verified intervening holds.

    Nonmaterial edge assessments may lie between the two material transitions.
    Node bridges are current-support assessments on the unchanged middle revision.
    Context changes break continuity; this is never a depth or iteration cap.
    """
    if previous is None or current is None:
        return False
    if (previous['target'] != current['target'] or previous['premise_key'] != current['premise_key']
            or previous['before_outcome'] == previous['after_outcome']
            or current['before_outcome'] == current['after_outcome']
            or previous['after_outcome'] != current['before_outcome']
            or previous['before_outcome'] != current['after_outcome']):
        return False
    ref = previous['after_ref']
    for bridge in bridges:
        if (bridge['target'] != current['target'] or bridge['premise_key'] != current['premise_key']
                or bridge['before_outcome'] != previous['after_outcome']
                or bridge['after_outcome'] != previous['after_outcome'] or bridge['before_ref'] != ref):
            return False
        ref = bridge['after_ref']
    return ref == current['before_ref']


def detect_cycle(transitions):
    """Any contiguous normalized return with at least two material changes."""
    if not isinstance(transitions, (list, tuple)) or len(transitions) < 2:
        return False
    first, last = transitions[0], transitions[-1]
    if (first['before_outcome'] != last['after_outcome']
            or sum(item['before_outcome'] != item['after_outcome'] for item in transitions) < 2):
        return False
    prior = None
    for item in transitions:
        if item['target'] != first['target'] or item['premise_key'] != first['premise_key']:
            return False
        if prior is not None and (prior['after_ref'] != item['before_ref'] or prior['after_outcome'] != item['before_outcome']):
            return False
        prior = item
    return True


def _load_record(conn, identifier):
    row = conn.execute('SELECT * FROM compiler_runtime.k_compilation_records WHERE record_id=%s', (identifier,)).fetchone()
    return _plain(row) if row is not None else None


def _load_job(conn, record):
    from .knowledge_runtime import KnowledgeRuntime
    return _plain(KnowledgeRuntime._job(conn, record['execution_id']))


def _node_transition(conn, record):
    if record is None or record.get('record_type') != 'k2k' or record.get('disposition') != 'accepted_revision':
        return None
    row = conn.execute('''SELECT newer.knode_id,newer.knode_revision_id,newer.content_fingerprint,
        newer.origin_record_id,newer.supersedes_revision_id,older.content_fingerprint AS previous_fingerprint,
        older.origin_record_id AS previous_record_id FROM canonical_store.knowledge_node_revisions newer
        JOIN canonical_store.knowledge_node_revisions older ON older.knode_revision_id=newer.supersedes_revision_id
            AND older.knode_id=newer.knode_id WHERE newer.knode_revision_id=%s''', (record['result_node_revision_id'],)).fetchone()
    if row is None:
        return None
    row = _plain(row)
    if row['origin_record_id'] != record['record_id'] or row['knode_id'] != record['result_node_id']:
        return None
    job = _load_job(conn, record)
    target = job['input_snapshot'].get('revision_target')
    if (not isinstance(target, dict) or target.get('target_knode_id') != row['knode_id']
            or target.get('expected_revision_id') != row['supersedes_revision_id']):
        return None
    key = basis(job, 'node', row['knode_id'])
    return {'record_id': record['record_id'], 'execution_id': record['execution_id'],
        'target': {'kind': 'node', 'logical_id': row['knode_id']}, 'basis': key, 'premise_key': digest(key),
        'before_ref': row['supersedes_revision_id'], 'after_ref': row['knode_revision_id'],
        'before_outcome': row['previous_fingerprint'], 'after_outcome': row['content_fingerprint'],
        'previous_record_id': row['previous_record_id'], **_audit(job)}


def _event(conn, identifier):
    row = conn.execute('SELECT * FROM canonical_store.knowledge_edge_applicability_events WHERE applicability_event_id=%s',
                       (identifier,)).fetchone()
    return _plain(row) if row is not None else None


def _edge_transition(conn, record, event=None):
    if record is None or record.get('record_type') != 'n2e' or record.get('disposition') not in ('reused', 'no_material_delta'):
        return None
    if event is None:
        rows = conn.execute('SELECT * FROM canonical_store.knowledge_edge_applicability_events WHERE origin_record_id=%s ORDER BY event_order',
                            (record['record_id'],)).fetchall()
        if len(rows) != 1:
            return None
        event = _plain(rows[0])
    if (event['origin_record_id'] != record['record_id'] or event['semantic_kedge_revision_id'] != record['result_edge_revision_id']
            or event['kedge_id'] != record['result_edge_id']):
        return None
    job = _load_job(conn, record)
    target = job['input_snapshot'].get('revalidation_target')
    pair = [event['from_knode_revision_id'], event['to_knode_revision_id']]
    if (not isinstance(target, dict) or target.get('kind') != 'edge' or target.get('target_revision_id') != event['semantic_kedge_revision_id']
            or target.get('prior_pair') != pair or [target.get('from_revision_id'), target.get('to_revision_id')] != pair):
        return None
    decision = conn.execute('SELECT validation FROM compiler_runtime.k_revalidation_decisions WHERE record_id=%s',
                            (record['record_id'],)).fetchone()
    if (decision is None or decision['validation'].get('confirmed') is not True
            or decision['validation'].get('applicable') is not event['applicable']
            or decision['validation'].get('material_change') is not (target['prior_applicable'] != event['applicable'])):
        return None
    prior = conn.execute('''SELECT * FROM canonical_store.knowledge_edge_applicability_events
        WHERE semantic_kedge_revision_id=%s AND event_order<%s
        ORDER BY event_order DESC LIMIT 1''', (event['semantic_kedge_revision_id'], event['event_order'])).fetchone()
    prior = _plain(prior) if prior is not None else None
    # A different effective pair is an intervening evaluation context. Do not
    # skip over it to find an older matching pair and fabricate continuity.
    if prior is not None and [prior['from_knode_revision_id'], prior['to_knode_revision_id']] != pair:
        return None
    if prior is None:
        original = [target['target']['from_knode_revision_id'], target['target']['to_knode_revision_id']]
        if pair != original or target.get('prior_basis_event_id') is not None or target.get('prior_applicable') is not True:
            return None
        before_ref = 'initial:' + event['semantic_kedge_revision_id']
    else:
        if (target.get('prior_basis_event_id') != prior['applicability_event_id']
                or target.get('prior_applicable') is not prior['applicable']):
            return None
        before_ref = prior['applicability_event_id']
    key = basis(job, 'edge', event['kedge_id'], edge_revision_id=event['semantic_kedge_revision_id'],
                edge_content_fingerprint=target['target']['content_fingerprint'])
    return {'record_id': record['record_id'], 'execution_id': record['execution_id'],
        'target': {'kind': 'edge', 'logical_id': event['kedge_id'], 'semantic_revision_id': event['semantic_kedge_revision_id']},
        'basis': key, 'premise_key': digest(key), 'before_ref': before_ref, 'after_ref': event['applicability_event_id'],
        'before_outcome': target['prior_applicable'], 'after_outcome': event['applicable'], 'event_order': event['event_order'],
        'previous_record_id': prior['origin_record_id'] if prior else None, **_audit(job)}


def _node_bridges(conn, previous, current):
    """Every support assessment on the middle revision predates its successor.

    New support cannot be appended to a no-longer-current historical result.
    Therefore this needs neither timestamp guesses nor a revision-count limit.
    """
    rows = conn.execute('''SELECT s.record_id FROM canonical_store.knowledge_current_supports s
        WHERE s.node_revision_id=%s ORDER BY s.event_order''', (current['before_ref'],)).fetchall()
    bridges = []
    for row in rows:
        identifier = str(row['record_id'])
        if identifier == previous['record_id']:
            continue
        record = _load_record(conn, identifier)
        if record is None or record['record_type'] != 'k2k' or record['disposition'] != 'reused':
            return None
        job = _load_job(conn, record)
        key = basis(job, 'node', current['target']['logical_id'])
        bridges.append({'record_id': identifier, 'execution_id': record['execution_id'], 'target': deepcopy(current['target']),
            'premise_key': digest(key), 'before_ref': current['before_ref'], 'after_ref': current['before_ref'],
            'before_outcome': current['before_outcome'], 'after_outcome': current['before_outcome'], **_audit(job)})
    return bridges


def inspect_record(conn, run, record):
    """Return an immutable diagnostic witness for the exact accepted record."""
    if not _enabled(run):
        return None
    record = _load_record(conn, record['record_id'])
    if record is None:
        return None
    if record['record_id'] not in run['scope']['root_record_ids'] and not conn.execute('''SELECT 1
        FROM compiler_runtime.propagation_execution_bindings b JOIN compiler_runtime.propagation_tasks t USING(task_id)
        WHERE b.execution_id=%s AND t.run_id=%s''', (record['execution_id'], run['run_id'])).fetchone():
        return None
    try:
        if record['record_type'] == 'k2k':
            current = _node_transition(conn, record)
            if current is None or current['before_outcome'] == current['after_outcome']:
                return None
            transitions, cursor, seen = [current], current, {current['after_ref']}
            while cursor['previous_record_id'] is not None:
                if cursor['before_ref'] in seen:
                    return None
                seen.add(cursor['before_ref'])
                older = _node_transition(conn, _load_record(conn, cursor['previous_record_id']))
                if older is None or older['premise_key'] != current['premise_key']:
                    return None
                bridges = _node_bridges(conn, older, cursor)
                if bridges is None:
                    return None
                additions = [older, *bridges]
                combined = [*additions, *transitions]
                # Every intermediate support review must preserve the same input
                # episode and the exact middle revision, even if its meaning held.
                if any(item['premise_key'] != current['premise_key'] for item in additions):
                    return None
                if any(left['after_ref'] != right['before_ref'] or left['after_outcome'] != right['before_outcome']
                       for left, right in zip(combined, combined[1:])):
                    return None
                transitions = combined
                if detect_cycle(transitions):
                    break
                cursor = older
        elif record['record_type'] == 'n2e':
            current = _edge_transition(conn, record)
            if current is None or current['before_outcome'] == current['after_outcome']:
                return None
            transitions, seen = [current], {current['after_ref']}
            cursor = current
            while cursor['previous_record_id'] is not None:
                if cursor['before_ref'] in seen:
                    return None  # Corrupt history is not proof of an ordinary oscillation.
                seen.add(cursor['before_ref'])
                event = _event(conn, cursor['before_ref'])
                older = _edge_transition(conn, _load_record(conn, cursor['previous_record_id']), event)
                if older is None or older['premise_key'] != current['premise_key']:
                    return None
                transitions = [older, *transitions]
                if detect_cycle(transitions):
                    break
                cursor = older
        else:
            return None
    except (KeyError, TypeError, ValueError, PalimpsestError):
        # Legacy/unsupported input has insufficient context for a deterministic
        # unchanged-premises claim. It is not automatically marked anomalous.
        return None
    if not detect_cycle(transitions):
        return None
    material = [item for item in transitions if item['before_outcome'] != item['after_outcome']]
    bridges = [item for item in transitions if item['before_outcome'] == item['after_outcome']]
    catalogs = [item['comparison_catalog_sha256'] for item in transitions]
    witness = {'schema_version': PROFILE, 'code': 'propagation_semantic_oscillation',
        'diagnosis': 'repeated_normalized_outcome_under_unchanged_premises',
        'context_claim': 'same_authoritative_premises_not_full_prompt_equality',
        'run_id': run['run_id'], 'record_id': record['record_id'], 'scope_sha256': digest(run['scope']), 'policy_sha256': digest(run['policy']),
        'target': current['target'], 'premise_key': current['premise_key'], 'basis': current['basis'],
        'previous_transition': material[-2], 'current_transition': current, 'material_transitions': material,
        'transition_sequence': transitions, 'intervening_assessments': bridges,
        'comparison_catalog_changed': len(set(catalogs)) > 1,
        'canonical_history_preserved': True, 'semantic_rejection': False}
    return {**witness, 'witness_sha256': digest(witness)}


def assert_fresh(conn, run, witness):
    """An explicit acknowledgement applies only to this still-current witness."""
    try:
        if (not _enabled(run) or not isinstance(witness, dict) or witness.get('schema_version') != PROFILE
                or witness.get('witness_sha256') != digest({k: v for k, v in witness.items() if k != 'witness_sha256'})
                or witness['run_id'] != run['run_id'] or witness['scope_sha256'] != digest(run['scope'])
                or witness['policy_sha256'] != digest(run['policy'])):
            _fail()
        current = witness['current_transition']
        record = _load_record(conn, current['record_id'])
        if record is None or inspect_record(conn, run, record) != witness:
            _fail()
        job = _load_job(conn, record)
        if run['policy'].get('model') != job['profile'].get('model'):
            _fail()
        from .knowledge_runtime import KnowledgeRuntime
        nodes = {node['knode_revision_id']: node for node in KnowledgeRuntime._nodes(conn)}
        for premise in witness['basis']['premises']:
            actual = nodes.get(premise['knode_revision_id'])
            if actual is None or premise_signature(actual) != premise or not conn.execute(
                    'SELECT compiler_runtime.current_k2k_premise(%s) AS usable', (premise['knode_revision_id'],)).fetchone()['usable']:
                _fail()
        snapshot = job['input_snapshot']
        if snapshot.get('data_versions'):
            KnowledgeRuntime._version_context(conn, job['operation'], snapshot['input'], snapshot['data_versions'], snapshot['data_version_mode'])
        elif any(nodes[p['knode_revision_id']].get('data_version_supports') for p in witness['basis']['premises']):
            _fail()
        if witness['target']['kind'] == 'node':
            selected = conn.execute('''SELECT n.current_revision_id,canonical_store.current_k_support_record(n.current_revision_id) AS support_record_id
                FROM canonical_store.knowledge_nodes n WHERE n.knode_id=%s''', (witness['target']['logical_id'],)).fetchone()
            if selected is None or str(selected['current_revision_id']) != current['after_ref'] or str(selected['support_record_id']) != record['record_id']:
                _fail()
        else:
            target = job['input_snapshot']['revalidation_target']
            row = conn.execute('''SELECT e.current_revision_id,source.current_revision_id AS source_revision_id,
                destination.current_revision_id AS destination_revision_id FROM canonical_store.knowledge_edges e
                JOIN canonical_store.knowledge_nodes source ON source.knode_id=e.from_knode_id
                JOIN canonical_store.knowledge_nodes destination ON destination.knode_id=e.to_knode_id WHERE e.kedge_id=%s''',
                (witness['target']['logical_id'],)).fetchone()
            latest = conn.execute('''SELECT applicability_event_id FROM canonical_store.knowledge_edge_applicability_events
                WHERE semantic_kedge_revision_id=%s AND from_knode_revision_id=%s AND to_knode_revision_id=%s
                ORDER BY event_order DESC LIMIT 1''', (target['target_revision_id'], target['from_revision_id'], target['to_revision_id'])).fetchone()
            if (row is None or latest is None or str(row['current_revision_id']) != target['target_revision_id']
                    or str(row['source_revision_id']) != target['from_revision_id']
                    or str(row['destination_revision_id']) != target['to_revision_id']
                    or str(latest['applicability_event_id']) != current['after_ref']):
                _fail()
    except (KeyError, TypeError, ValueError, PalimpsestError):
        _fail('propagation_anomaly_scope_changed')
