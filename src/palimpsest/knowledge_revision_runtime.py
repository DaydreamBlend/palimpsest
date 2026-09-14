"""Small hooks for explicit I2K/K2K revisions inside the ordinary transaction.

The caller owns authorization, profile/request hashes, ordinary normalization
and validation, exact input checks, grounding/derivation, Record resolution and
durable impact obligations. D2K revision grants are not implemented here.
"""

from copy import deepcopy
import json

from . import knowledge_revision as contract
from .knowledge import _fail, _uuid


PROFILE = contract.PROFILE
MATERIALITY_POLICY = 'accepted-state-materiality-v1'
_OPERATIONS = ('i2k', 'k2k')


def materiality_guidance(snapshot, operation, phase):
    """Only the new frozen propagation policy adds these instructions.

    This supplements existing schemas and independent reviews; it supplies no
    numerical tolerance, inference result, authority or convergence guarantee.
    Legacy/unbound request bytes remain unchanged.
    """
    scope = snapshot.get('propagation_scope')
    policy = scope.get('policy') if isinstance(scope, dict) else None
    if (operation not in ('k2k', 'n2e') or not isinstance(policy, dict) or policy.get('materiality_policy') != MATERIALITY_POLICY
            or policy.get('repeated_outcome') != 'observe'):
        return ''
    if phase not in ('generator', 'validator'):
        _fail('invalid_materiality_guidance_phase')
    text = '''
ACCEPTED-STATE MATERIALITY POLICY: accepted-state-materiality-v1.
Compare with the exact current accepted snapshot supplied for this review.
Keep that accepted snapshot as the comparison base after an ignored, rejected,
or nonmaterial candidate; never substitute the last generated candidate as base.
Several individually small differences must not drift away from the last
accepted meaning through transitive near-equality assumptions.

Assess meaning and source support, not edit distance or embedding similarity.
Use precision, units, uncertainty and tolerances only when explicitly grounded
in the supplied source or an applicable stated domain policy. There is no
universal numeric epsilon or embedding threshold. A tiny change to polarity,
units, scope, quantifiers, conditions or ordered procedure steps can be material.
Do not average contradictory facts, erase separate experimental records, or
weaken conditions merely to make the process appear to converge.

Revisiting a logical object or repeating a normalized result is diagnostic
context only. Repetition is not a reason to stop, reject, accept, or reuse a
claim. Do not claim guaranteed damping or mathematical convergence. Preserve
ordinary grounding, inference, identity and source-scope requirements.
Use only the existing output schema and its concise reasons/reason codes;
do not add a convergence score, tolerance, control action or authority field.
'''
    if operation == 'k2k':
        if snapshot.get('revision_target') is not None:
            text += '''For this explicit target, independently set
revision_review.material_change=false only when the unchanged accepted claim
remains supported by the current exact premises and its truth conditions,
usable inferences, decision consequences and procedural obligations are not
materially changed. Supporting a slightly different candidate alone does not
establish that the unchanged accepted claim is still supported.
Use material_change=true for a supported material successor. Use null when
materiality cannot be justified; null remains unresolved and is never false.
Explain why the difference is minor or meaningful relative to the accepted base.
A valid same-meaning result reuses the exact target, with novel_conclusion=false;
its updated support is still independently validated. Empty output does not
resolve a mandatory target review.
'''
        else:
            text += '''For discovery, compare candidates with the supplied current
accepted K catalog. A semantically equivalent candidate uses the ordinary reused
verdict, its exact equivalent_revision_id and novel_conclusion=false; a different
fingerprint or wording alone does not justify accepted/new Knowledge. Do not
merge source-specific experimental records. The schema has no revision_review
unless an explicit target is supplied; use ordinary unresolved verdicts when
equivalence or support is uncertain. Discovery may return no justified new
candidate without asserting exhaustion of all possible Knowledge.
'''
    else:
        text += '''For N2E, assess the retained relation against the exact current
endpoint pair. Preserve its original semantic revision and historical endpoints.
applicable=false describes a negative relation status and can be a material
change from a previously confirmed positive result. Uncertain/pending is not a
negative result. An unchanged confirmed applicability or endpoint rebasing alone
does not create a new semantic relation revision. Preserve all actual endpoint
meaning and conditions; do not hide a material applicability change behind a
same-worded predicate. For a mandatory target use null/unconfirmed for uncertainty
and retain its unresolved review; omission is not a successful no-change result.
'''
    if phase == 'generator':
        text += '''Generator: provide the best grounded ordinary candidate or
assessment. The independent Validator decides materiality and reuse; repetition
or a desire to finish supplies neither evidence nor approval.
'''
    else:
        text += '''Independent Validator: verify these conditions yourself and
record concise reasons. Nonmaterial semantic judgment does not waive support
refresh, dependency maintenance, or any other already pending obligation;
Runtime tracks those obligations separately from new semantic branches.
'''
    return text


def _target(snapshot):
    target = contract.check_target(snapshot)
    if snapshot['operation'] not in _OPERATIONS:
        _fail('knowledge_revision_operation_unsupported')
    return target


def freeze_request(current_nodes, *, operation, target_knode_id, expected_revision_id):
    """Select one exact current catalog row; caller verified accepted authority."""
    if operation not in _OPERATIONS or not isinstance(current_nodes, list):
        _fail('knowledge_revision_operation_unsupported')
    selected = [node for node in current_nodes if node.get('knode_id') == target_knode_id]
    if len(selected) != 1:
        _fail('knowledge_revision_target_changed')
    return contract.freeze_target(selected[0], operation=operation,
        target_knode_id=target_knode_id, expected_revision_id=expected_revision_id)


def bind_candidates(candidates, target):
    _target(target)
    if not isinstance(candidates, list) or len(candidates) > 1:
        _fail('knowledge_revision_single_candidate_required')
    return [contract.bind_candidate(candidate, target) for candidate in candidates]


def _append(prompt, target, phase):
    _target(target)
    policy = '''
EXPLICIT KNOWLEDGE REVISION: Compare only the exact manually selected current
Knowledge target below. It is comparison context, not additional source evidence,
an inference premise, or authority. Preserve its logical identity, kind and source
scope. Return at most one ordinary candidate using only this operation's actual
delivered I evidence or accepted K premises. Do not invent a candidate when the
input cannot support a change. Keep all ordinary input review obligations.
Do not emit target IDs, fingerprints or a new Record type in the candidate.
The application binds the ordinary normalized candidate to the selected target.
'''
    if phase == 'validator':
        policy += '''Independently assess same_identity, material_change and
grounding_valid in revision_review against the exact comparison base. Different
wording or semantic JSON alone does not prove a material meaning change. Set
material_change=false for equivalent meaning; null means undecidable. Ordinary
source/inference validation still applies. A nonmaterial result reuses the exact
target without a new revision or changing its origin. Any reuse suggestion must
name this target's exact expected revision. If there is no candidate, return
revision_review=null; the explicit revision request remains unresolved.
'''
    return prompt + policy + '\nEXPLICIT_TARGET_JSON:\n' + json.dumps(
        {'explicit_target': target}, ensure_ascii=False, sort_keys=True, allow_nan=False)


def generation_request(prompt, schema, target):
    """Wrap the ordinary request; preserve its candidate and review wire shapes."""
    _target(target)
    result = deepcopy(schema)
    nodes = result.get('properties', {}).get('nodes')
    if not isinstance(nodes, dict) or nodes.get('type') != 'array':
        _fail('invalid_knowledge_revision_schema')
    nodes['maxItems'] = 1
    return _append(prompt, target, 'generator'), result


def validation_request(prompt, schema, target, candidates):
    bound = bind_candidates(candidates, target)
    result = deepcopy(schema)
    if (result.get('type') != 'object' or not isinstance(result.get('properties'), dict)
            or not isinstance(result.get('required'), list)
            or 'revision_review' in result['properties']):
        _fail('invalid_knowledge_revision_schema')
    result['properties']['revision_review'] = contract.review_schema(target) if bound else {'type': 'null'}
    result['required'].append('revision_review')
    return _append(prompt, target, 'validator'), result


def split_validation(response, target, candidates):
    """Remove only the new field before passing to the unchanged base validator."""
    bound = bind_candidates(candidates, target)
    if not isinstance(response, dict) or 'revision_review' not in response:
        _fail('invalid_knowledge_revision_review')
    ordinary = deepcopy(response)
    review = ordinary.pop('revision_review')
    if not bound:
        if review is not None:
            _fail('invalid_knowledge_revision_review')
    else:
        review = contract.resolve(bound[0], target, review)['review']
    return ordinary, review


def resolve_decisions(candidates, validated_decisions, target, review):
    """Combine independent materiality with already validated ordinary decisions.

An empty mapping means the target request is unresolved, never successful zero
output. The caller must retain that obligation even if model complete is true.
"""
    bound = bind_candidates(candidates, target)
    if not isinstance(validated_decisions, dict) or set(validated_decisions) != {c['candidate_key'] for c in bound}:
        _fail('invalid_knowledge_revision_decision')
    if not bound:
        if review is not None:
            _fail('invalid_knowledge_revision_review')
        return {}
    candidate = bound[0]
    decision = validated_decisions[candidate['candidate_key']]
    if (not isinstance(decision, dict) or decision.get('candidate_key') != candidate['candidate_key']
            or decision.get('verdict') not in ('accepted', 'reused', 'rejected', 'needs_human')):
        _fail('invalid_knowledge_revision_decision')
    result = contract.resolve(candidate, target, review)
    hold = None
    if decision['verdict'] in ('rejected', 'needs_human'):
        hold = 'knowledge_revision_base_validation_required'
    elif decision['verdict'] == 'reused':
        if (decision.get('equivalent_candidate_key') is not None
                or decision.get('equivalent_revision_id') != target['expected_revision_id']):
            hold = 'knowledge_revision_reuse_target_mismatch'
        elif review['material_change'] is True:
            hold = 'knowledge_revision_materiality_conflict'
    elif decision.get('equivalent_candidate_key') is not None or decision.get('equivalent_revision_id') is not None:
        _fail('invalid_knowledge_revision_decision')
    if hold:
        result.update(action='rejected' if decision['verdict'] == 'rejected' else 'needs_human',
                      result_content_fingerprint=None, origin={'mode': 'no_publication'},
                      reason_codes=list(dict.fromkeys([*result['reason_codes'], hold])))
    return {candidate['candidate_key']: {**result, 'decision': deepcopy(decision)}}


def _json(value):
    return json.loads(json.dumps(value, default=str, ensure_ascii=False, allow_nan=False))


def commit_revision(conn, record, candidate, target, resolution):
    """Insert and CAS only; caller must use its enclosing atomic transaction.

No new connection, transaction or commit is opened. Grounding, derivation,
Record disposition and durable dependency obligations must share this commit.
"""
    frozen = _target(target)
    bound = bind_candidates([candidate], target)[0]
    if not isinstance(resolution, dict) or 'decision' not in resolution or 'review' not in resolution:
        _fail('invalid_knowledge_revision_decision')
    checked = resolve_decisions([bound], {bound['candidate_key']: resolution['decision']}, target,
                                resolution['review'])[bound['candidate_key']]
    if checked != resolution or checked['action'] != 'accepted_revision':
        _fail('knowledge_revision_not_accepted')
    if (not isinstance(record, dict) or record.get('record_type') != target['operation']
            or record.get('disposition') not in ('pending', 'needs_human') or record.get('body') != bound):
        _fail('invalid_knowledge_revision_record')
    _uuid(str(record.get('record_id')), 'invalid_knowledge_revision_record')
    current = conn.execute('''SELECT n.knode_id,n.kind,n.current_revision_id,
        r.knode_revision_id,r.semantic_payload,r.statement,r.identity_fingerprint,
        r.content_fingerprint,r.origin_record_id,s.identity_scope,s.source_data_id
        FROM canonical_store.knowledge_nodes n
        JOIN canonical_store.knowledge_node_revisions r ON r.knode_revision_id=n.current_revision_id
        JOIN canonical_store.knowledge_node_scopes s ON s.knode_id=n.knode_id
        WHERE n.knode_id=%s FOR UPDATE OF n''', (target['target_knode_id'],)).fetchone()
    if current is None or _json(current) != {k: v for k, v in frozen.items() if k != 'current_applicability'}:
        _fail('knowledge_revision_target_changed')
    row = conn.execute('''INSERT INTO canonical_store.knowledge_node_revisions
        (knode_id,semantic_payload,statement,identity_fingerprint,content_fingerprint,
         origin_record_id,supersedes_revision_id) VALUES (%s,%s::jsonb,%s,%s,%s,%s,%s)
        RETURNING knode_revision_id''', (target['target_knode_id'], json.dumps(bound['semantic_payload'], ensure_ascii=False, allow_nan=False),
        bound['statement'], frozen['identity_fingerprint'], bound['content_fingerprint'],
        record['record_id'], target['expected_revision_id'])).fetchone()
    identifier = str(row['knode_revision_id'])
    updated = conn.execute('''UPDATE canonical_store.knowledge_nodes SET current_revision_id=%s
        WHERE knode_id=%s AND current_revision_id=%s RETURNING knode_id''',
        (identifier, target['target_knode_id'], target['expected_revision_id'])).fetchone()
    if updated is None:
        _fail('knowledge_revision_target_changed')
    return {**{k: deepcopy(v) for k, v in frozen.items() if k != 'current_applicability'},
        'knode_revision_id': identifier, 'current_revision_id': identifier,
        'semantic_payload': deepcopy(bound['semantic_payload']), 'statement': bound['statement'],
        'content_fingerprint': bound['content_fingerprint'], 'origin_record_id': str(record['record_id']),
        'supersedes_revision_id': target['expected_revision_id']}


def enumerate_impacts(conn, revision_id):
    """Enumerate every exact direct reference, including historical references.

No depth/size cutoff and no mutation. This is one adjacency step: the durable
Runtime queue must traverse downstream obligations, not call it propagation done.
Optional Wiki absence is recorded; permission/query failures propagate normally.
"""
    _uuid(revision_id, 'invalid_knowledge_revision_target')
    derivations = conn.execute('''SELECT d.record_id,d.result_node_revision_id,
        p.premise_node_revision_id,p.ordinal FROM canonical_store.knowledge_derivation_premises p
        JOIN canonical_store.knowledge_derivations d USING(record_id)
        WHERE p.premise_node_revision_id=%s ORDER BY d.record_id,p.ordinal''', (revision_id,)).fetchall()
    edges = conn.execute('''SELECT kedge_id,kedge_revision_id,from_knode_revision_id,to_knode_revision_id
        FROM canonical_store.knowledge_edge_revisions
        WHERE from_knode_revision_id=%s OR to_knode_revision_id=%s
        ORDER BY kedge_id,kedge_revision_id''', (revision_id, revision_id)).fetchall()
    applicability = conn.execute('''SELECT applicability_event_id,event_order,kedge_id,
        semantic_kedge_revision_id,from_knode_revision_id,to_knode_revision_id,applicable
        FROM canonical_store.knowledge_edge_applicability_events
        WHERE from_knode_revision_id=%s OR to_knode_revision_id=%s ORDER BY event_order''',
        (revision_id, revision_id)).fetchall()
    available = conn.execute("SELECT to_regclass('wiki_projection.knowledge_links') IS NOT NULL AS available").fetchone()['available']
    links = (conn.execute('''SELECT link_id,request_id,wiki_id,snapshot_id,item_key,knode_id,node_revision_id
        FROM wiki_projection.knowledge_links WHERE node_revision_id=%s
        ORDER BY wiki_id,request_id,snapshot_id,item_key,link_id''', (revision_id,)).fetchall() if available else [])
    return _json({'source_revision_id': revision_id, 'derivations': derivations, 'edges': edges,
        'edge_applicability': applicability, 'wiki_links': links, 'wiki_available': available})


def prepare_call(runtime, execution_id, phase, directory, derived_store=None):
    """Export an explicit revision request; provider execution is separate."""
    from .knowledge_review import KnowledgeReview
    from .wiki_projection_store import ProjectionStore
    from . import k2k
    from .knowledge import _digest

    job = runtime.show(execution_id)
    if job['input_snapshot']['input'].get('schema_version') == 'k2k-effective-input-v1':
        from .k2k_effective_runtime import prepare_call as effective_call
        return effective_call(runtime, execution_id, phase, directory)
    target = job['input_snapshot'].get('revision_target')
    if target is None or job['profile'].get('explicit_knowledge_revision') != PROFILE:
        _fail('knowledge_revision_request_required')
    _target(target)
    if job['operation'] != target['operation']:
        _fail('knowledge_revision_profile_changed')
    if job['operation'] == 'i2k':
        return KnowledgeReview(runtime).prepare_call(execution_id, phase, directory, derived_store)
    if phase not in ('generator', 'validator') or job['state'] != ('prepared' if phase == 'generator' else 'proposed'):
        _fail('knowledge_call_not_ready')
    context = job if phase == 'generator' else runtime.validation_context(execution_id)
    prompt, schema = (k2k.generation_request(job['input_snapshot'], []) if phase == 'generator'
                      else k2k.validation_request(context, []))
    request = {'prompt': prompt, 'schema': schema, 'images': [],
        'input_sha256': job['input_digest'] if phase == 'generator' else context['validation_context_sha'],
        'output_file': phase + '-response.json',
        'delivered_knowledge_revision_ids': k2k.check_input(job['input_snapshot']['input']),
        'delivered_revision_target_id': target['expected_revision_id']}
    if job['input_snapshot'].get('data_versions'):
        request['delivered_data_version_ids'] = [v['version_id'] for v in job['input_snapshot']['data_versions']]
    binding = {'execution_id': job['execution_id'], 'phase': phase, 'input_digest': job['input_digest'],
               'profile': job['profile'], 'request_sha256': _digest(request)}
    output = ProjectionStore(directory)
    with output.locked():
        prior = output.read_json(phase + '-binding.json')
        if prior is not None:
            if prior != binding or output.read_json(phase + '-request.json') != request:
                _fail('knowledge_call_directory_conflict')
        else:
            output.write_json(phase + '-request.json', request)
            output.write_json(phase + '-binding.json', binding)
    return {'execution_id': job['execution_id'], 'phase': phase,
        'request_file': str(output.root / (phase + '-request.json')), 'request_sha256': _digest(request),
        'actual_delivery': False, 'replayed': prior is not None}
