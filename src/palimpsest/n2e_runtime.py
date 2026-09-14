"""N2E relation effects inside the shared KnowledgeRuntime transaction."""

from copy import deepcopy
from hashlib import sha256
from importlib.resources import files
import json

from psycopg.types.json import Jsonb

from .canonical_store import connection
from .data import request_id, data_id as check_data_id
from .errors import PalimpsestError
from .i2k import digest
from . import knowledge_provenance as provenance
from . import n2e_relations as relations


def _fail(code):
    raise PalimpsestError(code, 'N2E의 정확한 관계·현재 endpoint·검토 근거를 확인하세요.', 6)


def available(conn):
    return bool(conn.execute("SELECT to_regclass('compiler_runtime.n2e_review_targets') AS relation").fetchone()['relation'])


def modern(snapshot):
    return snapshot.get('n2e_policy') == relations.PROFILE


def implementation():
    return {name: sha256(files('palimpsest').joinpath(name).read_bytes()).hexdigest()
            for name in ('n2e_relations.py', 'n2e_runtime.py', 'knowledge_requests.py')}


def support_binding(nodes):
    return {'endpoint_support_record_ids': [node.get('current_support_record_id') for node in nodes],
            'endpoint_support_signatures': [node.get('current_support_signature', digest(None)) for node in nodes]}


def check_endpoints(conn, nodes):
    for node in nodes:
        if not conn.execute('SELECT compiler_runtime.current_k2k_premise(%s) AS ok',
                            (node['knode_revision_id'],)).fetchone()['ok']:
            _fail('n2e_endpoint_needs_revalidation')


def input_packet(runtime, data_id, revision_ids):
    check_data_id(data_id)
    refs = [request_id(ref) for ref in revision_ids]
    if len(refs) != len(set(refs)) or not refs:
        _fail('invalid_n2e_input')
    with connection(runtime.dsn) as conn, conn.transaction():
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        current = {node['knode_revision_id']: node for node in runtime._nodes(conn)}
        if any(ref not in current for ref in refs):
            _fail('knowledge_input_changed')
        selected = [current[ref] for ref in refs]
        check_endpoints(conn, selected)
        if data_id not in {owner for node in selected for owner in node.get('source_data_ids', node['grounding_data_ids'])}:
            _fail('n2e_source_owner_unfounded')
        return {'schema_version': 'n2e-input-v1', 'nodes': selected}


def freeze(conn, edges, nodes, revision_id, packet, prior_pair=None):
    edge = next((edge for edge in edges if edge['kedge_revision_id'] == revision_id), None)
    if edge is None:
        _fail('n2e_review_target_changed')
    current = {node['knode_id']: node for node in nodes}
    selected = [current[edge[key]] for key in ('from_knode_id', 'to_knode_id')]
    pair = [node['knode_revision_id'] for node in selected]
    if pair != [node['knode_revision_id'] for node in packet['nodes']]:
        _fail('n2e_review_endpoints_changed')
    check_endpoints(conn, selected)
    original = [edge['from_knode_revision_id'], edge['to_knode_revision_id']]
    prior_pair = list(prior_pair or pair)
    if len(prior_pair) != 2:
        _fail('invalid_n2e_review_target')
    for ref, owner in zip(prior_pair, (edge['from_knode_id'], edge['to_knode_id'])):
        if not conn.execute('SELECT 1 FROM canonical_store.knowledge_node_revisions WHERE knode_revision_id=%s AND knode_id=%s',
                            (request_id(ref), owner)).fetchone():
            _fail('invalid_n2e_prior_pair')
    latest = conn.execute('''SELECT applicability_event_id,applicable FROM canonical_store.knowledge_edge_applicability_events
        WHERE semantic_kedge_revision_id=%s AND from_knode_revision_id=%s AND to_knode_revision_id=%s
        ORDER BY event_order DESC LIMIT 1''', (revision_id, *prior_pair)).fetchone()
    prior = latest['applicable'] if latest else (True if prior_pair == original else None)
    keys = ('kedge_id', 'kedge_revision_id', 'predicate', 'from_knode_id', 'to_knode_id',
            'from_knode_revision_id', 'to_knode_revision_id', 'qualifiers', 'identity_fingerprint', 'content_fingerprint')
    body = {'schema_version': relations.PROFILE, 'kind': 'edge', 'target_revision_id': revision_id,
        'target_kedge_id': edge['kedge_id'], 'from_revision_id': pair[0], 'to_revision_id': pair[1],
        'prior_applicable': prior, 'prior_basis_event_id': str(latest['applicability_event_id']) if latest else None,
        'prior_pair': prior_pair, 'target': {key: deepcopy(edge[key]) for key in keys}, **support_binding(selected)}
    return relations.check_target({**body, 'target_sha256': digest(body)})


def prepare_review(runtime, revision_id, identifier, *, data_id=None, prior_pair=None,
                   data_version_ids=None, data_version_mode='current', propagation_claim=None):
    revision_id, identifier = request_id(revision_id), request_id(identifier)
    # A retry uses the original frozen target, including its pre-fence basis.
    with connection(runtime.dsn) as conn, conn.transaction():
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        prior_job = conn.execute('''SELECT c.execution_id,c.input_snapshot,e.data_id
            FROM compiler_runtime.k_execution_contexts c JOIN compiler_runtime.operation_executions e USING(execution_id)
            WHERE c.request_id=%s''', (identifier,)).fetchone()
        if prior_job:
            snapshot = prior_job['input_snapshot']
            target = snapshot.get('edge_review_target')
            if target is None or target['target_revision_id'] != revision_id or (data_id and prior_job['data_id'] != data_id):
                _fail('idempotency_conflict')
            if prior_pair is not None and list(prior_pair) != target['prior_pair']:
                _fail('idempotency_conflict')
            owner, packet = prior_job['data_id'], snapshot['n2e_request_input']
        else:
            nodes, edges = runtime._nodes(conn), runtime._edges(conn)
            edge = next((edge for edge in edges if edge['kedge_revision_id'] == revision_id), None)
            if edge is None:
                _fail('n2e_review_target_changed')
            by_logical = {node['knode_id']: node for node in nodes}
            selected = [by_logical[edge[key]] for key in ('from_knode_id', 'to_knode_id')]
            owners = sorted({owner for node in selected for owner in node.get('source_data_ids', node['grounding_data_ids'])})
            owner = data_id or (owners[0] if owners else None)
            if owner not in owners:
                _fail('n2e_source_owner_unfounded')
            packet = {'schema_version': 'n2e-input-v1', 'nodes': selected}
            target = freeze(conn, edges, nodes, revision_id, packet, prior_pair)
    return runtime.prepare('n2e', owner, identifier, packet, edge_review_target=target,
        data_version_ids=data_version_ids, data_version_mode=data_version_mode, propagation_claim=propagation_claim)


def open_fence(conn, execution_id, target):
    order = conn.execute('UPDATE compiler_runtime.knowledge_state SET version=version+1 WHERE singleton RETURNING version').fetchone()['version']
    conn.execute('''INSERT INTO compiler_runtime.n2e_review_targets
        (execution_id,semantic_kedge_revision_id,from_knode_revision_id,to_knode_revision_id,fence_order,target)
        VALUES (%s,%s,%s,%s,%s,%s)''', (execution_id, target['target_revision_id'], target['from_revision_id'],
        target['to_revision_id'], order, Jsonb(target)))
    return order


def _edge(conn, identity):
    return conn.execute('''SELECT e.kedge_id,r.kedge_revision_id,r.content_fingerprint,e.predicate,
        e.from_knode_id,e.to_knode_id FROM canonical_store.knowledge_edges e
        JOIN canonical_store.knowledge_edge_revisions r ON r.kedge_revision_id=e.current_revision_id
        WHERE e.identity_fingerprint=%s''', (identity,)).fetchone()


def _status(conn, revision):
    return conn.execute('SELECT canonical_store.current_knowledge_edge_applicability(%s) AS status', (revision,)).fetchone()['status']


def _cycle(conn, source, target, excluded=(), active_pairs=()):
    rows = conn.execute('''SELECT kedge_id,from_knode_id,to_knode_id FROM canonical_store.knowledge_edges
        WHERE predicate='composes' AND canonical_store.current_knowledge_edge_applicability(current_revision_id)='applicable' ''').fetchall()
    adjacency = {}
    for row in rows:
        if str(row['kedge_id']) not in excluded:
            adjacency.setdefault(str(row['from_knode_id']), set()).add(str(row['to_knode_id']))
    for left, right in active_pairs:
        adjacency.setdefault(left, set()).add(right)
    pending, seen = [target], set()
    while pending:
        node = pending.pop()
        if node == source:
            return True
        if node not in seen:
            seen.add(node)
            pending.extend(adjacency.get(node, ()))
    return False


def _event(conn, record, edge, body, applicable, nodes):
    conn.execute('''INSERT INTO canonical_store.knowledge_edge_applicability_events
        (kedge_id,semantic_kedge_revision_id,from_knode_revision_id,to_knode_revision_id,applicable,origin_record_id,detail)
        VALUES (%s,%s,%s,%s,%s,%s,%s)''', (edge['kedge_id'], edge['kedge_revision_id'], body['from_revision_id'],
        body['to_revision_id'], applicable, record['record_id'], Jsonb({'n2e_policy': relations.PROFILE,
            **support_binding([nodes[body['from_revision_id']], nodes[body['to_revision_id']]])})))


def commit(runtime, conn, job, records, response, checkpoint=None):
    snapshot = job['input_snapshot']
    target = snapshot.get('edge_review_target')
    candidates = [record['body'] for record in records]
    decisions = relations.validate_decisions(response, candidates, target)
    current_nodes = runtime._nodes(conn)
    nodes = {node['knode_revision_id']: node for node in current_nodes}
    selected = [nodes[node['knode_revision_id']] for node in snapshot['input']['nodes']]
    check_endpoints(conn, selected)
    if target and target != freeze(conn, runtime._edges(conn), current_nodes, target['target_revision_id'],
                                  snapshot['input'], target['prior_pair']):
        _fail('n2e_review_target_changed')
    review = decisions.get('review_existing_relation')
    hold_review = target and (not job['generator_receipt']['generation_complete'] or not response['complete'] or not review
        or not review.get('applicability_review', {}).get('confirmed')
        or any(d['verdict'] == 'needs_human' or (d['verdict'] == 'accepted' and
            (not d['relation_valid'] or not d['scope_compatible'] or
             (key != 'review_existing_relation' and d['material_change'] is None))) for key, d in decisions.items()))
    compositions = [body for body in candidates if body['role'] == 'relation' and body['predicate'] == 'composes'
        and decisions[body['candidate_key']]['verdict'] == 'accepted'
        and decisions[body['candidate_key']]['relation_valid'] and decisions[body['candidate_key']]['scope_compatible']
        and decisions[body['candidate_key']]['material_change'] is not None]
    prospective = [(nodes[body['from_revision_id']]['knode_id'], nodes[body['to_revision_id']]['knode_id'])
                   for body in compositions]
    excluded = ()
    if target and review and review.get('applicability_review', {}).get('confirmed'):
        if review['applicability_review']['applicable']:
            if target['target']['predicate'] == 'composes':
                prospective.append((target['target']['from_knode_id'], target['target']['to_knode_id']))
        else:
            excluded = (target['target_kedge_id'],)
    # Evaluate a positive composition batch together, before publishing a
    # prefix. Model array ordering must not choose which half of a cycle wins.
    composition_cycle = any(_cycle(conn, source, dest, excluded, prospective) for source, dest in prospective)
    composition_holds = {body['candidate_key'] for body in compositions} if composition_cycle else set()
    if target and composition_cycle:
        hold_review = True
    if target and not hold_review:
        assessment = review['applicability_review']['applicable']
        for body in candidates:
            decision = decisions[body['candidate_key']]
            if body['role'] != 'relation' or decision['verdict'] != 'accepted':
                continue
            # Reusing the same accepted meaning cannot simultaneously deny its
            # applicability. A material successor has its own semantic meaning.
            if (body['identity_fingerprint'] == target['target']['identity_fingerprint']
                    and not decision['material_change'] and assessment is False):
                hold_review = True
            existing = _edge(conn, body['identity_fingerprint'])
            if (existing and decision['material_change'] is True
                    and existing['content_fingerprint'] == body['content_fingerprint']):
                hold_review = True
            if body['predicate'] == 'composes':
                excluded = (target['target_kedge_id'],) if assessment is False else ()
                restored = ([(target['target']['from_knode_id'], target['target']['to_knode_id'])]
                    if assessment is True and target['target']['predicate'] == 'composes' else [])
                source, dest = nodes[body['from_revision_id']], nodes[body['to_revision_id']]
                if _cycle(conn, source['knode_id'], dest['knode_id'], excluded, restored):
                    hold_review = True
    for record in records:
        body = record['body']
        decision = decisions[body['candidate_key']]
        model_decision = deepcopy(decision)
        action = decision['verdict']
        edge = None
        before = after = None
        material = False
        if hold_review or (action == 'accepted' and (not decision['relation_valid'] or not decision['scope_compatible']
                or (body['role'] == 'relation' and decision['material_change'] is None))):
            action = 'needs_human'
            decision = {**decision, 'reason_codes': ['n2e_review_unresolved'],
                'reason': 'Independent scope, materiality or explicit applicability remains unresolved.'}
        if body['candidate_key'] in composition_holds:
            action = 'needs_human'
            decision = {**decision, 'reason_codes': ['composes_cycle_pending'],
                'reason': 'The proposed positive composition batch forms a cycle with the current applicable graph.'}
        if action == 'accepted':
            edge = _edge(conn, body['identity_fingerprint'])
            if (str(edge['kedge_revision_id']) if edge else None) != body['comparison_base_revision_id']:
                _fail('n2e_comparison_base_changed')
            source, dest = nodes[body['from_revision_id']], nodes[body['to_revision_id']]
            before_status = _status(conn, edge['kedge_revision_id']) if edge else None
            before = True if before_status == 'applicable' else False if before_status == 'inapplicable' else None
            if body['role'] == 'target_assessment':
                after = decision['applicability_review']['applicable']
                before = target['prior_applicable']
                material = before is not after
                action = 'no_material_delta'
            else:
                after = True
                changed = edge is not None and decision['material_change']
                if changed and edge['content_fingerprint'] == body['content_fingerprint']:
                    action = 'needs_human'
                    decision = {**decision, 'reason_codes': ['n2e_materiality_conflict'],
                        'reason': 'An identical accepted payload cannot produce a new semantic revision.'}
                else:
                    action = 'accepted_new' if edge is None else 'accepted_revision' if changed else 'reused'
                    material = action in ('accepted_new', 'accepted_revision') or before is not True
            if action != 'needs_human' and after and body['predicate'] == 'composes' and _cycle(
                    conn, source['knode_id'], dest['knode_id'], (str(edge['kedge_id']),) if edge else ()):
                action = 'needs_human'
                decision = {**decision, 'reason_codes': ['composes_cycle_pending'],
                    'reason': 'This proper-component relation would cycle in the current applicable graph. Reassess this context.'}
            if action in ('accepted_new', 'accepted_revision'):
                old_id = edge['kedge_revision_id'] if edge else None
                logical = edge['kedge_id'] if edge else str(conn.execute('SELECT uuidv7() AS id').fetchone()['id'])
                revision = str(conn.execute('SELECT uuidv7() AS id').fetchone()['id'])
                if edge is None:
                    conn.execute('''INSERT INTO canonical_store.knowledge_edges
                        (kedge_id,predicate,from_knode_id,to_knode_id,identity_fingerprint,current_revision_id)
                        VALUES (%s,%s,%s,%s,%s,%s)''', (logical, body['predicate'], source['knode_id'], dest['knode_id'],
                        body['identity_fingerprint'], revision))
                conn.execute('''INSERT INTO canonical_store.knowledge_edge_revisions
                    (kedge_revision_id,kedge_id,from_knode_revision_id,to_knode_revision_id,semantic_payload,qualifiers,rationale,
                     identity_fingerprint,content_fingerprint,origin_record_id,supersedes_revision_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (revision, logical, body['from_revision_id'], body['to_revision_id'],
                    Jsonb({'predicate': body['predicate']}), Jsonb(body['qualifiers']), body['rationale'],
                    body['identity_fingerprint'], body['content_fingerprint'], record['record_id'], old_id))
                if old_id:
                    count = conn.execute('UPDATE canonical_store.knowledge_edges SET current_revision_id=%s '
                        'WHERE kedge_id=%s AND current_revision_id=%s', (revision, logical, old_id)).rowcount
                    if count != 1:
                        _fail('n2e_comparison_base_changed')
                edge = {'kedge_id': logical, 'kedge_revision_id': revision}
            if action != 'needs_human':
                _event(conn, record, edge, body, after, nodes)
                # A changed effective/support basis must reach dependent readers,
                # even if the semantic revision is reused. Dispatcher distinguishes it.
                from .k2k_effective_runtime import consumers
                basis_maintenance = after is True and bool(consumers(conn, edge['kedge_id']))
                if material or (after is True and before_status in ('pending', 'endpoint_unusable')) or basis_maintenance:
                    conn.execute("INSERT INTO compiler_runtime.k_outbox(record_id,operation) VALUES (%s,'k2k')", (record['record_id'],))
                if checkpoint:
                    checkpoint('after_knowledge_effect')
        if action in ('needs_human', 'rejected'):
            edge, before, after, material = None, None, None, False
        conn.execute('''INSERT INTO compiler_runtime.n2e_review_decisions
            (record_id,execution_id,candidate_key,role,validation,action,material_change,before_applicable,after_applicable)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (record['record_id'], job['execution_id'], body['candidate_key'],
            body['role'], Jsonb({**decision, 'model_decision': model_decision}), action, material, before, after))
        runtime._resolve(conn, record, action, decision, edge=edge)


def prepare_call(runtime, execution_id, phase, directory):
    from .knowledge_requests import edge_generation_request, edge_validation_request
    from .wiki_projection_store import ProjectionStore
    job = runtime.show(execution_id)
    if job['operation'] != 'n2e' or phase not in ('generator', 'validator') or job['state'] != ('prepared' if phase == 'generator' else 'proposed'):
        _fail('knowledge_call_not_ready')
    context = job if phase == 'generator' else runtime.validation_context(execution_id)
    prompt, schema = (edge_generation_request(job['input_snapshot']) if phase == 'generator' else edge_validation_request(context))
    request = {'prompt': prompt, 'schema': schema, 'images': [], 'output_file': phase + '-response.json',
        'input_sha256': job['input_digest'] if phase == 'generator' else context['validation_context_sha'],
        'delivered_knowledge_revision_ids': [node['knode_revision_id'] for node in job['input_snapshot']['input']['nodes']]}
    for field in ('edge_review_target', 'revalidation_target'):
        if job['input_snapshot'].get(field):
            request['delivered_' + field + '_sha256'] = job['input_snapshot'][field]['target_sha256']
    if job['input_snapshot'].get('data_versions'):
        request['delivered_data_version_ids'] = [v['version_id'] for v in job['input_snapshot']['data_versions']]
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
    return {'execution_id': job['execution_id'], 'phase': phase,
        'request_file': str(store.root / (phase + '-request.json')), 'request_sha256': digest(request),
        'actual_delivery': False, 'replayed': prior is not None}
