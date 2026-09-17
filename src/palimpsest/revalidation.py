"""Mandatory target reviews inside ordinary N2E/K2K executions.

No public operation or Record subtype is introduced. A missing or uncertain
assessment leaves the caller's durable obligation unresolved.
"""

from copy import deepcopy
import json

from .data import request_id
from .errors import PalimpsestError
from .i2k import digest
from .knowledge import _array, _enum, _keys, _object, _text, _uuid, REASON_PATTERN
from . import knowledge_provenance as provenance
from . import n2e


PROFILE = 'knowledge-revalidation-v1'
SUPPORT_PROFILE = 'knowledge-current-support-v1'


def _fail(code):
    raise PalimpsestError(code, '필수 Knowledge 재검토의 정확한 대상·현재 근거를 확인하세요.', 6)


def _json(value):
    return json.loads(json.dumps(value, default=str, ensure_ascii=False, allow_nan=False))


def check_target(value):
    common = ('schema_version', 'kind', 'target_revision_id', 'target_sha256')
    if not isinstance(value, dict) or value.get('kind') not in ('node', 'edge'):
        _fail('invalid_revalidation_target')
    extra = (('target_knode_id', 'prior_support_record_id', 'premise_revision_ids') if value['kind'] == 'node'
        else ('target_kedge_id', 'from_revision_id', 'to_revision_id', 'prior_applicable',
              'prior_basis_event_id', 'prior_pair', 'target'))
    if value['kind'] == 'node' and 'effective_edge_refs' in value:
        extra = (*extra, 'effective_edge_refs')
    _keys(value, (*common, *extra), 'invalid_revalidation_target')
    if value['schema_version'] != PROFILE or value['target_sha256'] != digest({k: v for k, v in value.items() if k != 'target_sha256'}):
        _fail('revalidation_target_changed')
    _uuid(value['target_revision_id'])
    _uuid(value['target_knode_id'] if value['kind'] == 'node' else value['target_kedge_id'])
    if value['kind'] == 'node':
        if value['prior_support_record_id'] is not None:
            _uuid(value['prior_support_record_id'])
        refs = value['premise_revision_ids']
        if not isinstance(refs, list) or len(refs) < 2 or len(refs) != len(set(refs)):
            _fail('revalidation_premises_required')
        for ref in refs:
            _uuid(ref)
        if 'effective_edge_refs' in value:
            from .k2k_effective import check_ref
            if not isinstance(value['effective_edge_refs'], list) or not value['effective_edge_refs']:
                _fail('invalid_revalidation_target')
            for ref in value['effective_edge_refs']:
                check_ref(ref)
    else:
        for field in ('from_revision_id', 'to_revision_id'):
            _uuid(value[field])
        if type(value['prior_applicable']) is not bool:
            _fail('invalid_revalidation_target')
        if value['prior_basis_event_id'] is not None:
            _uuid(value['prior_basis_event_id'])
        if not isinstance(value['prior_pair'], list) or len(value['prior_pair']) != 2:
            _fail('invalid_revalidation_target')
        for ref in value['prior_pair']:
            _uuid(ref)
    return deepcopy(value)


def freeze_node(nodes, state, revision_id, packet):
    target = next((n for n in nodes if n['knode_revision_id'] == revision_id), None)
    if target is None or target['kind'] != 'proposition':
        _fail('revalidation_target_changed')
    record_id = provenance.support_record(state, revision_id)
    prior = state['by_record'].get(record_id)
    if prior is None:
        # Source K needs actual I review, not fabricated K premises or D2K.
        _fail('revalidation_source_review_required')
    by_logical = {n['knode_id']: n for n in nodes}
    refs = [by_logical[state['revisions'][ref]['knode_id']]['knode_revision_id'] for ref in prior['premise_revision_ids']]
    if refs != [n['knode_revision_id'] for n in packet['nodes']] or revision_id in refs:
        _fail('revalidation_premises_changed')
    body = {'schema_version': PROFILE, 'kind': 'node', 'target_revision_id': revision_id,
        'target_knode_id': target['knode_id'], 'prior_support_record_id': record_id, 'premise_revision_ids': refs}
    if prior.get('effective_edge_premises'):
        from . import k2k_effective
        if (packet.get('schema_version') != k2k_effective.INPUT_SCHEMA
                or [edge['kedge_id'] for edge in packet['effective_edges']] !=
                   [edge['kedge_id'] for edge in prior['effective_edge_premises']]):
            _fail('revalidation_effective_premises_changed')
        body['effective_edge_refs'] = k2k_effective.effective_refs(packet)
    return check_target({**body, 'target_sha256': digest(body)})


def freeze_edge(conn, edges, nodes, revision_id, packet, prior_pair=None):
    edge = next((e for e in edges if e['kedge_revision_id'] == revision_id), None)
    if edge is None or edge['predicate'] != 'supports':
        _fail('revalidation_target_changed')
    by_logical = {n['knode_id']: n for n in nodes}
    pair = [by_logical[edge[field]]['knode_revision_id'] for field in ('from_knode_id', 'to_knode_id')]
    if pair != [n['knode_revision_id'] for n in packet['nodes']]:
        _fail('revalidation_endpoints_changed')
    original = [edge['from_knode_revision_id'], edge['to_knode_revision_id']]
    prior_pair = original if prior_pair is None else prior_pair
    if not isinstance(prior_pair, list) or len(prior_pair) != 2:
        _fail('invalid_revalidation_target')
    latest = conn.execute('''SELECT applicability_event_id,applicable FROM canonical_store.knowledge_edge_applicability_events
        WHERE semantic_kedge_revision_id=%s AND from_knode_revision_id=%s AND to_knode_revision_id=%s
        ORDER BY event_order DESC LIMIT 1''', (revision_id, *prior_pair)).fetchone()
    if latest is None and prior_pair != original:
        _fail('revalidation_prior_applicability_unknown')
    keys = ('kedge_id', 'kedge_revision_id', 'predicate', 'from_knode_id', 'to_knode_id',
            'from_knode_revision_id', 'to_knode_revision_id', 'qualifiers', 'content_fingerprint', 'identity_fingerprint')
    body = {'schema_version': PROFILE, 'kind': 'edge', 'target_revision_id': revision_id,
        'target_kedge_id': edge['kedge_id'], 'from_revision_id': pair[0], 'to_revision_id': pair[1],
        'prior_applicable': latest['applicable'] if latest else True,
        'prior_basis_event_id': str(latest['applicability_event_id']) if latest else None,
        'prior_pair': list(prior_pair), 'target': {key: deepcopy(edge[key]) for key in keys}}
    return check_target({**body, 'target_sha256': digest(body)})


def prepare_node(runtime, target_revision_id, identifier, *, data_id=None, data_version_ids=None,
                 data_version_mode='current', propagation_claim=None, model_profile=None):
    from .canonical_store import connection
    revision_id = request_id(target_revision_id)
    with connection(runtime.dsn) as conn, conn.transaction():
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        state, nodes = provenance.load(conn), runtime._nodes(conn)
        target = next((n for n in nodes if n['knode_revision_id'] == revision_id), None)
        if target is None or state is None:
            _fail('revalidation_target_changed')
        support = state['by_record'].get(provenance.support_record(state, revision_id))
        if support is None:
            _fail('revalidation_source_review_required')
        by_logical = {n['knode_id']: n for n in nodes}
        refs = [by_logical[state['revisions'][r]['knode_id']]['knode_revision_id'] for r in support['premise_revision_ids']]
        owners = sorted({owner for ref in refs for owner in provenance.describe(state, ref)['source_data_ids']})
        owner = data_id or target.get('source_data_id') or (owners[0] if owners else None)
        if owner is None:
            _fail('revalidation_source_owner_required')
        from .k2k_effective_runtime import current_edge_revisions
        edge_refs = current_edge_revisions(conn, support['record_id'])
        packet = runtime._inference_input(conn, owner, refs, edge_revision_ids=edge_refs or None)
        frozen = freeze_node(nodes, state, revision_id, packet)
    return runtime.prepare('k2k', owner, identifier, packet, target_knode_id=target['knode_id'],
        expected_revision_id=revision_id, revalidation_target=frozen,
        data_version_ids=data_version_ids, data_version_mode=data_version_mode, propagation_claim=propagation_claim,
        model_profile=model_profile)


def prepare_edge(runtime, edge_revision_id, identifier, *, data_id=None, prior_pair=None,
                 data_version_ids=None, data_version_mode='current', propagation_claim=None, model_profile=None):
    from .canonical_store import connection
    revision_id = request_id(edge_revision_id)
    with connection(runtime.dsn) as conn, conn.transaction():
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        nodes, edges, state = runtime._nodes(conn), runtime._edges(conn), provenance.load(conn)
        edge = next((e for e in edges if e['kedge_revision_id'] == revision_id), None)
        if edge is None:
            _fail('revalidation_target_changed')
        by_logical = {n['knode_id']: n for n in nodes}
        selected = [by_logical[edge[field]] for field in ('from_knode_id', 'to_knode_id')]
        for node in selected:
            if provenance.describe(state, node['knode_revision_id'])['current_applicability'] != 'current_premises':
                _fail('revalidation_dependency_pending')
        owners = sorted({owner for n in selected for owner in provenance.describe(state, n['knode_revision_id'])['source_data_ids']})
        owner = data_id or (owners[0] if owners else None)
        if owner is None:
            _fail('revalidation_source_owner_required')
        packet = {'schema_version': 'n2e-input-v1', 'nodes': selected}
        frozen = freeze_edge(conn, edges, nodes, revision_id, packet, prior_pair)
    return runtime.prepare('n2e', owner, identifier, packet, revalidation_target=frozen,
        data_version_ids=data_version_ids, data_version_mode=data_version_mode, propagation_claim=propagation_claim,
        model_profile=model_profile)


def _assessment_schema(*, validator):
    fields = {'applicable': {'type': ['boolean', 'null']},
        'reason_codes': _array({'type': 'string', 'pattern': REASON_PATTERN}, nonempty=True),
        'reason': {'type': 'string', 'minLength': 1}}
    if validator:
        fields['confirmed'] = {'type': 'boolean'}
    return _object(fields)


def node_request(prompt, schema, target, *, validator=False):
    """A mandatory review can succeed by validated reuse, without new novelty."""
    check_target(target)
    if target['kind'] != 'node':
        _fail('invalid_revalidation_target')
    policy = '''
MANDATORY EXISTING CONCLUSION REVIEW: This task is not discovery of novel K.
Reassess the exact existing conclusion against ALL refreshed accepted premises.
When the conclusion is still supported with the same meaning, emit one ordinary
candidate preserving its statement, semantic payload, identity and source scope,
with the refreshed premise IDs and updated concise derivation basis. A changed
numeric premise can leave a comparison conclusion unchanged. Lack of novelty
alone is never a reason for empty output in this mandatory review.
When support justifies a material successor, propose it for independent review.
When the target cannot be justified, report uncertainty; never invent evidence.
Empty output remains unresolved, not a successful no-change assessment.
'''
    if validator:
        policy += '''Independent Validator: for a supported unchanged conclusion,
use verdict=reused with the exact comparison target revision, novel_conclusion=false,
and revision_review.material_change=false. The inference_valid, premises_sufficient,
limits_preserved, same_identity and grounding_valid checks still require independent
verification. Keep the immutable generation origin; only active support is updated.
'''
    return prompt + policy, schema


def edge_request(prompt, schema, target, *, validator=False):
    check_target(target)
    if target['kind'] != 'edge':
        _fail('invalid_revalidation_target')
    schema = deepcopy(schema)
    schema['properties']['applicability'] = _assessment_schema(validator=validator)
    schema['required'].append('applicability')
    field = 'decisions' if validator else 'edges'
    schema['properties'][field]['maxItems'] = 1
    policy = '''
MANDATORY EXACT EDGE REVIEW: Assess the existing supports relation below for
its exact current endpoint pair. Its original edge meaning, qualifiers and
historical endpoints are immutable. This is not relation discovery. Emit the
one supplied relation as the ordinary candidate to identify the review target,
even when applicability is false or uncertain; do not change qualifiers.
applicability.applicable=true means that exact relation still applies; false
means it does not; null means unresolved. Empty output never finishes this task.
The candidate is an assessment target, not an assertion that supports is true.
Independent Validator: assess applicability yourself. confirmed=true requires
valid exact inputs and agreement with a definite Generator assessment. Use the
ordinary accepted verdict for a valid assessment, including confirmed false;
hold uncertainty or disagreement. Do not infer false from candidate omission.
No node creation, source reading, D2I, D2K or new edge semantic revision.
'''
    return prompt + policy + '\nREVALIDATION_TARGET_JSON:\n' + json.dumps(target, ensure_ascii=False, sort_keys=True), schema


def _assessment(value, *, validator=False):
    keys = ('applicable', 'reason_codes', 'reason') + (('confirmed',) if validator else ())
    _keys(value, keys, 'invalid_revalidation_assessment')
    if value['applicable'] is not None and type(value['applicable']) is not bool:
        _fail('invalid_revalidation_assessment')
    if validator and type(value['confirmed']) is not bool:
        _fail('invalid_revalidation_assessment')
    from .knowledge import _decision_reason
    _decision_reason(value, 'invalid_revalidation_assessment')
    return deepcopy(value)


def normalize_edge_response(response, nodes, target):
    check_target(target)
    _keys(response, ('edges', 'complete', 'applicability'), 'invalid_revalidation_assessment')
    assessment = _assessment(response['applicability'])
    candidates = n2e.normalize_edges({k: v for k, v in response.items() if k != 'applicability'}, nodes)
    if len(candidates) > 1:
        _fail('revalidation_single_target_required')
    for candidate in candidates:
        if (candidate['from_revision_id'] != target['from_revision_id'] or candidate['to_revision_id'] != target['to_revision_id']
                or candidate['content_fingerprint'] != target['target']['content_fingerprint']):
            _fail('revalidation_target_changed')
        candidate['applicability_proposal'] = assessment
    return candidates, assessment


def edge_decisions(response, candidates, target):
    check_target(target)
    _keys(response, ('decisions', 'complete', 'applicability'), 'invalid_revalidation_assessment')
    assessment = _assessment(response['applicability'], validator=True)
    ordinary = n2e.validate_edge_decisions({k: v for k, v in response.items() if k != 'applicability'}, candidates)
    resolved = bool(candidates) and assessment['confirmed'] and assessment['applicable'] is not None
    if candidates:
        candidate = candidates[0]
        resolved = resolved and candidate['applicability_proposal']['applicable'] is assessment['applicable']
        resolved = resolved and ordinary[candidate['candidate_key']]['verdict'] == 'accepted'
    result = {'kind': 'edge', 'target_sha256': target['target_sha256'], **assessment,
        'confirmed': bool(resolved), 'material_change': bool(resolved and target['prior_applicable'] != assessment['applicable'])}
    return ordinary, result


def prepare_call(runtime, execution_id, phase, directory):
    from . import k2k
    from .knowledge_requests import edge_generation_request, edge_validation_request
    from .wiki_projection_store import ProjectionStore
    job = runtime.show(execution_id)
    if job['input_snapshot']['input'].get('schema_version') == 'k2k-effective-input-v1':
        from .k2k_effective_runtime import prepare_call as effective_call
        return effective_call(runtime, execution_id, phase, directory)
    target = check_target(job['input_snapshot'].get('revalidation_target'))
    if phase not in ('generator', 'validator') or job['state'] != ('prepared' if phase == 'generator' else 'proposed'):
        _fail('knowledge_call_not_ready')
    context = job if phase == 'generator' else runtime.validation_context(execution_id)
    if target['kind'] == 'node':
        prompt, schema = (k2k.generation_request(job['input_snapshot'], []) if phase == 'generator'
                          else k2k.validation_request(context, []))
    else:
        prompt, schema = (edge_generation_request(job['input_snapshot']) if phase == 'generator'
                          else edge_validation_request(context))
    request = {'prompt': prompt, 'schema': schema, 'images': [], 'output_file': phase + '-response.json',
        'input_sha256': job['input_digest'] if phase == 'generator' else context['validation_context_sha'],
        'delivered_knowledge_revision_ids': [n['knode_revision_id'] for n in job['input_snapshot']['input']['nodes']],
        'delivered_revalidation_target_sha256': target['target_sha256']}
    if target['kind'] == 'node':
        request['delivered_revision_target_id'] = target['target_revision_id']
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
    return {'execution_id': job['execution_id'], 'phase': phase, 'request_file': str(store.root / (phase + '-request.json')),
        'request_sha256': digest(request), 'actual_delivery': False, 'replayed': prior is not None}
