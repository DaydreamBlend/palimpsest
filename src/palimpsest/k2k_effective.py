"""Pure K2K contracts for complete, exact Node/effective-Edge input bundles.

Runtime owns acceptance, actual applicability/read-set checks, endpoint expansion,
typed persistence and current-support activation. No source/model/storage calls.
"""

from copy import deepcopy
import json

from . import k2k as legacy
from .data import data_id as check_digest
from .knowledge import _array, _enum, _fail, _keys, _object, _uuid
from .n2e import _qualifiers
from .n2e_relations import canonical_pair
from .i2k import digest
from .version_context import prompt_suffix


PROFILE = 'knowledge-inference-effective-v1'
INPUT_SCHEMA = 'k2k-effective-input-v1'
EDGE_FIELDS = ('kedge_id', 'predicate', 'qualifiers', 'original_from_revision_id',
               'original_to_revision_id', 'effective_edge_ref', 'endpoint_support_signatures')
REF_FIELDS = ('semantic_kedge_revision_id', 'from_knode_revision_id', 'to_knode_revision_id',
              'applicability_basis_type', 'applicability_basis_ref', 'relation_read_state_token')
FIELDS = (*legacy.FIELDS, 'premise_edge_revision_ids')


def check_ref(value):
    _keys(value, REF_FIELDS, 'invalid_k2k_effective_ref')
    for field in ('semantic_kedge_revision_id', 'from_knode_revision_id', 'to_knode_revision_id',
                  'applicability_basis_ref'):
        _uuid(value[field], 'invalid_k2k_effective_ref')
    if (value['from_knode_revision_id'] == value['to_knode_revision_id']
            or value['applicability_basis_type'] not in ('origin_acceptance', 'applicability_event')):
        _fail('invalid_k2k_effective_ref')
    check_digest(value['relation_read_state_token'])
    return deepcopy(value)


def build_input(nodes, effective_edges, data_id):
    """One selected Edge is supported only with both actual endpoint Node values.

    Order is part of the frozen bundle. These are not independent source counts.
    """
    base = legacy.build_input(nodes, data_id)
    if not isinstance(effective_edges, list) or not effective_edges:
        _fail('k2k_effective_edges_required')
    by_revision = {node['knode_revision_id']: node for node in base['nodes']}
    logical, revisions, pairs = set(), set(), set()
    for edge in effective_edges:
        _keys(edge, EDGE_FIELDS, 'invalid_k2k_effective_edge')
        identifier = _uuid(edge['kedge_id'], 'invalid_k2k_effective_edge')
        ref = check_ref(edge['effective_edge_ref'])
        for field in ('original_from_revision_id', 'original_to_revision_id'):
            _uuid(edge[field], 'invalid_k2k_effective_edge')
        if edge['original_from_revision_id'] == edge['original_to_revision_id']:
            _fail('invalid_k2k_effective_edge')
        source, target = (by_revision.get(ref[field]) for field in ('from_knode_revision_id', 'to_knode_revision_id'))
        if source is None or target is None:
            _fail('k2k_effective_endpoint_missing')
        ordered = canonical_pair(edge['predicate'], source, target)
        if ordered != (source, target):
            _fail('k2k_effective_edge_not_canonical')
        pair = (edge['predicate'], source['knode_id'], target['knode_id'])
        if identifier in logical or ref['semantic_kedge_revision_id'] in revisions or pair in pairs:
            _fail('duplicate_k2k_effective_edge')
        logical.add(identifier)
        revisions.add(ref['semantic_kedge_revision_id'])
        pairs.add(pair)
        if _qualifiers(edge['qualifiers']) != edge['qualifiers']:
            _fail('k2k_effective_qualifiers_changed')
        signatures = edge['endpoint_support_signatures']
        if not isinstance(signatures, list) or len(signatures) != 2:
            _fail('invalid_k2k_effective_support')
        for signature in signatures:
            check_digest(signature)
        if signatures != [node.get('current_support_signature') for node in (source, target)]:
            _fail('k2k_effective_support_changed')
        if (ref['applicability_basis_type'] == 'origin_acceptance'
                and [ref['from_knode_revision_id'], ref['to_knode_revision_id']]
                != [edge['original_from_revision_id'], edge['original_to_revision_id']]):
            _fail('k2k_effective_origin_pair_changed')
    result = {'schema_version': INPUT_SCHEMA, 'data_id': data_id, 'nodes': base['nodes'],
              'effective_edges': deepcopy(effective_edges)}
    result['input_sha256'] = digest(result)
    return result


def check_input(packet):
    _keys(packet, ('schema_version', 'data_id', 'nodes', 'effective_edges', 'input_sha256'), 'invalid_k2k_effective_input')
    if (packet['schema_version'] != INPUT_SCHEMA
            or build_input(packet['nodes'], packet['effective_edges'], packet['data_id']) != packet):
        _fail('k2k_effective_input_changed')
    return [node['knode_revision_id'] for node in packet['nodes']]


def _legacy_input(packet):
    check_input(packet)
    return legacy.build_input(packet['nodes'], packet['data_id'])


def edge_revision_ids(packet):
    check_input(packet)
    return [edge['effective_edge_ref']['semantic_kedge_revision_id'] for edge in packet['effective_edges']]


def effective_refs(packet):
    check_input(packet)
    return [deepcopy(edge['effective_edge_ref']) for edge in packet['effective_edges']]


def _slot_keys(packet):
    check_input(packet)
    return [f'inference_{ordinal:04d}' for ordinal in range(1, len(packet['effective_edges']) + 1)]


def generation_schema(packet, *, fixed_slots=False):
    schema = legacy.generation_schema(_legacy_input(packet))
    item = schema['properties']['nodes']['items']
    node_ids, edge_ids = check_input(packet), edge_revision_ids(packet)
    item['properties']['premise_revision_ids'].update(minItems=len(node_ids), maxItems=len(node_ids))
    item['properties']['premise_edge_revision_ids'] = {
        **_array(_enum(edge_ids)), 'minItems': len(edge_ids), 'maxItems': len(edge_ids)}
    item['required'].append('premise_edge_revision_ids')
    if fixed_slots:
        return _object({'candidate_slots': _object({
            key: {'anyOf': [deepcopy(item), {'type': 'null'}]} for key in _slot_keys(packet)}),
            'complete': {'type': 'boolean'},
            'coverage_notes': deepcopy(schema['properties']['coverage_notes'])})
    return schema


def normalize_proposals(response, packet):
    base = _legacy_input(packet)
    if isinstance(response, dict) and 'candidate_slots' in response:
        _keys(response, ('candidate_slots', 'complete', 'coverage_notes'), 'invalid_k2k_proposal')
        keys = _slot_keys(packet)
        _keys(response['candidate_slots'], keys, 'invalid_k2k_proposal')
        response = {'nodes': [response['candidate_slots'][key] for key in keys
                              if response['candidate_slots'][key] is not None],
                    'complete': response['complete'], 'coverage_notes': response['coverage_notes']}
    _keys(response, ('nodes', 'complete', 'coverage_notes'), 'invalid_k2k_proposal')
    if not isinstance(response['nodes'], list):
        _fail('invalid_k2k_proposal')
    node_ids, edge_ids, refs = check_input(packet), edge_revision_ids(packet), effective_refs(packet)
    stripped = deepcopy(response)
    for item in stripped['nodes']:
        _keys(item, FIELDS, 'invalid_k2k_effective_proposal')
        if item['premise_revision_ids'] != node_ids or item['premise_edge_revision_ids'] != edge_ids:
            _fail('k2k_effective_bundle_incomplete')
        del item['premise_edge_revision_ids']
    candidates = legacy.normalize_proposals(stripped, base)
    for candidate in candidates:
        candidate.update(premise_edge_revision_ids=list(edge_ids), premise_effective_edge_refs=deepcopy(refs))
    return candidates


def _checked_candidates(candidates, packet=None):
    """Check app-bound refs; packet supplies the authoritative full input when available."""
    if not isinstance(candidates, list):
        _fail('invalid_k2k_effective_proposal')
    expected = (check_input(packet), edge_revision_ids(packet), effective_refs(packet)) if packet is not None else None
    stripped = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            _fail('invalid_k2k_effective_proposal')
        nodes = candidate.get('premise_revision_ids')
        edges = candidate.get('premise_edge_revision_ids')
        refs = candidate.get('premise_effective_edge_refs')
        if (not isinstance(nodes, list) or len(nodes) < 2 or any(not isinstance(ref, str) for ref in nodes)
                or len(nodes) != len(set(nodes)) or not isinstance(edges, list) or not edges
                or any(not isinstance(ref, str) for ref in edges) or len(edges) != len(set(edges))
                or not isinstance(refs, list) or len(refs) != len(edges)):
            _fail('k2k_effective_bundle_incomplete')
        for identifier in nodes + edges:
            _uuid(identifier, 'invalid_k2k_effective_proposal')
        for ref in refs:
            check_ref(ref)
            if ref['from_knode_revision_id'] not in nodes or ref['to_knode_revision_id'] not in nodes:
                _fail('k2k_effective_endpoint_missing')
        if [ref['semantic_kedge_revision_id'] for ref in refs] != edges:
            _fail('k2k_effective_bundle_incomplete')
        binding = (nodes, edges, refs)
        if expected is None:
            expected = binding
        if binding != expected:
            _fail('k2k_effective_bundle_incomplete')
        stripped.append({key: deepcopy(value) for key, value in candidate.items()
                         if key not in ('premise_edge_revision_ids', 'premise_effective_edge_refs')})
    return stripped


def validation_schema(candidate_keys, existing_revision_ids, *, fixed_slots=False):
    schema = legacy.validation_schema(candidate_keys, existing_revision_ids)
    if not fixed_slots:
        return schema
    item = schema['properties']['decisions']['items']
    slots = {}
    for key in candidate_keys:
        value = deepcopy(item)
        branches = value.get('anyOf', [value])
        for branch in branches:
            branch['properties']['candidate_key'] = _enum((key,))
        slots[key] = value
    return _object({'decisions_by_key': _object(slots), 'complete': {'type': 'boolean'}})


def validate_decisions(value, candidates, existing_revision_ids, packet=None):
    if isinstance(value, dict) and 'decisions_by_key' in value:
        _keys(value, ('decisions_by_key', 'complete'), 'invalid_k2k_decision')
        keys = [candidate['candidate_key'] for candidate in candidates]
        _keys(value['decisions_by_key'], keys, 'invalid_k2k_decision')
        value = {'decisions': [value['decisions_by_key'][key] for key in keys],
                 'complete': value['complete']}
    return legacy.validate_decisions(value, _checked_candidates(candidates, packet), existing_revision_ids)


POLICY = '''
EFFECTIVE RELATION PREMISES: knowledge-inference-effective-v1.
Every candidate must declare ALL input Node revision IDs in packet.nodes order
and ALL semantic Edge revision IDs in packet.effective_edges order. This whole
delivered authoritative bundle is the dependency boundary even if your concise
derivation does not mention every endpoint value. Do not shrink it by attribution.
Existing-catalog and explicit-target values are comparison context, not additional
premises. Runtime binds each declared Edge to its exact effective endpoint pair,
applicability basis and read-state token; emit no invented or rewritten references.
One Edge includes two real endpoint Nodes. Neither their number nor the number of
relations establishes independent sources or independent experimental evidence.

An accepted supports relation is qualified evidence, not automatically a logical
implication. Do not treat supports chains as deductive transitivity without an
explicit rule in the supplied Node meanings. A contradicts relation identifies a
scoped incompatibility; it licenses neither arbitrary conclusions (explosion), a
winner, averaging the claims, nor automatically invalidating either Node.
qualifies retains its explicit restrictions. composes is a proper part/whole
relation, not proof that an unsupported measurement or logical rule is true.
Use exact predicate, conditions, scope, units, polarity and endpoint meanings.
Only current usable positive applicability is an inference input. A missing or
pending mandatory relation is unresolved, never false or silently dispensable.
Retain inferred/source attribution and every premise's assumptions and limits.
No D2I, D2K, external source fetching, new I, W/authority, Observation, automatic
Edge creation or automatic Node lifecycle change is permitted here.
'''


def _snapshot(snapshot):
    check_input(snapshot['input'])
    projected = legacy._prompt_snapshot(snapshot)
    # Only explicitly bound Edge inputs are authoritative relation context.
    projected.pop('existing_edges', None)
    return projected


def generation_request(snapshot, attachments=None):
    if attachments:
        _fail('k2k_direct_media_forbidden')
    fixed_slots = snapshot.get('comparison_catalog') is not None
    prompt = legacy.POLICY + POLICY + ('''
This bounded BGE comparison request has one nullable inference slot per effective
Edge. Fill each slot with at most one strongest genuinely new conclusion or null.
''' if fixed_slots else '') + '''
TASK: Generator. Derive justified propositions using the complete frozen bundle.
Return the supplied strict schema. Do not emit premise_effective_edge_refs:
Runtime owns this exact reference binding. Empty discovery can be appropriate;
a mandatory existing-conclusion review still needs its explicit supported result.
PREMISES_AND_CATALOG_JSON:
'''
    return (prompt + json.dumps(_snapshot(snapshot), ensure_ascii=False, sort_keys=True, allow_nan=False)
            + prompt_suffix(snapshot), generation_schema(snapshot['input'], fixed_slots=fixed_slots))


def validation_request(context, attachments=None):
    if attachments:
        _fail('k2k_direct_media_forbidden')
    snapshot = context['input_snapshot']
    _checked_candidates(context['candidates'], snapshot['input'])
    projected = {**deepcopy(context), 'input_snapshot': _snapshot(snapshot)}
    prompt = legacy.POLICY + POLICY + '''
TASK: Independent Validator. Assess inference_valid, premises_sufficient,
limits_preserved and novel_conclusion separately against the full delivered Node
and exact effective-Edge bundle. Edge applicability is necessary, not proof of
the proposed inference. Accepted new conclusions require all four checks true.
Same-meaning reuse may have novel_conclusion=false, with the other checks true.
Keep endpoint conditions and relation qualifiers; disagreement is not a license
to choose a winner. Return one decision per candidate, retaining uncertainty.
VALIDATION_CONTEXT_JSON:
'''
    schema = validation_schema([candidate['candidate_key'] for candidate in context['candidates']],
        [node['knode_revision_id'] for node in snapshot.get('existing_nodes', [])],
        fixed_slots=snapshot.get('comparison_catalog') is not None)
    return prompt + json.dumps(projected, ensure_ascii=False, sort_keys=True, allow_nan=False) + prompt_suffix(snapshot), schema
