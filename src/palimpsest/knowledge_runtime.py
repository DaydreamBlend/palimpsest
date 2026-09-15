"""Durable first I2K/N2E execution with short, atomic PostgreSQL commits.

Providers run outside this module and outside database transactions. Input,
delivery receipts, pending proposals and accepted effects remain distinct.
"""

from copy import deepcopy
from hashlib import sha256
from importlib.resources import files
import json

from psycopg.types.json import Jsonb
from psycopg.errors import RaiseException

from .canonical_store import connection
from .data import data_id as validate_data_id, request_id
from .errors import PalimpsestError
from .i2k import build_input, digest
from .knowledge import PROFILE, normalize_nodes, validate_node_decisions
from .n2e import normalize_edges, validate_edge_decisions
from .i2k_selection import (PROFILE as SELECTION_PROFILE, check_selection_input,
                           normalize_selection, validate_selection_decisions, check_scope_reuse)
from . import multi_source_i2k as multi
from . import source_review as source_review_contract
from .knowledge_requests import (generation_request, validation_request,
                                 edge_generation_request, edge_validation_request)
from . import d2k, k2k, knowledge_provenance, version_provenance
from . import information_errors
from . import revalidation
from . import n2e_runtime, n2e_relations
from . import k2k_effective, k2k_effective_runtime
from . import knowledge_revision_runtime as revision_runtime
from .data_versions import immutable_versions
from .local_glm_provider import PROFILE as GLM_PROFILE


MODEL = deepcopy(GLM_PROFILE)


def _fail(code, exit_code=4):
    raise PalimpsestError(code, 'Knowledge 실행의 입력·판정·현재 Revision을 확인하세요.', exit_code)


def _json(value):
    return json.loads(json.dumps(value, default=str, ensure_ascii=False, allow_nan=False))


def _uuid(conn):
    return str(conn.execute('SELECT uuidv7() AS id').fetchone()['id'])


def _selection_implementation():
    return {name: sha256(files('palimpsest').joinpath(name).read_text(encoding='utf-8').encode('utf-8')).hexdigest()
            for name in ('selection_prompts.py', 'knowledge_prompts.py', 'i2k_selection.py')}


def _multi_implementation():
    return {name: sha256(files('palimpsest').joinpath(name).read_text(encoding='utf-8').encode()).hexdigest()
            for name in ('multi_source_i2k.py', 'multi_source_prompts.py', 'i2k_selection.py',
                         'knowledge.py', 'knowledge_prompts.py')}


def _source_review_implementation():
    return {name: sha256(files('palimpsest').joinpath(name).read_bytes()).hexdigest()
            for name in ('source_review.py', 'knowledge_requests.py')}


def _inference_implementation():
    return {name: sha256(files('palimpsest').joinpath(name).read_bytes()).hexdigest()
            for name in ('k2k.py', 'knowledge_provenance.py', 'knowledge_runtime.py')}


def _d2k_implementation():
    return {name: sha256(files('palimpsest').joinpath(name).read_bytes()).hexdigest()
            for name in ('d2k.py', 'd2k_runtime.py', 'knowledge_runtime.py', 'knowledge_provenance.py')}


def _version_implementation():
    return {name: sha256(files('palimpsest').joinpath(name).read_bytes()).hexdigest()
            for name in ('data_versions.py', 'version_provenance.py', 'version_context.py',
                         'knowledge_requests.py', 'knowledge_runtime.py')}


def _information_error_implementation():
    return {name: sha256(files('palimpsest').joinpath(name).read_bytes()).hexdigest()
            for name in ('information_errors.py','knowledge_runtime.py','knowledge_requests.py','multi_source_prompts.py')}


def _revision_implementation():
    return {name: sha256(files('palimpsest').joinpath(name).read_bytes()).hexdigest()
            for name in ('knowledge_revision.py', 'knowledge_revision_runtime.py',
                         'knowledge_runtime.py', 'knowledge_requests.py', 'k2k.py')}


def _revalidation_implementation():
    return {name: sha256(files('palimpsest').joinpath(name).read_bytes()).hexdigest()
            for name in ('revalidation.py', 'knowledge_provenance.py', 'knowledge_runtime.py', 'knowledge_requests.py')}


def _propagation_claim(conn, claim, execution_id=None):
    """Fence worker-bound jobs without changing ordinary historical executions."""
    if not conn.execute("SELECT to_regclass('compiler_runtime.propagation_execution_bindings') AS relation").fetchone()['relation']:
        if claim is not None:
            _fail('propagation_schema_required', 3)
        return None
    binding = (conn.execute('SELECT task_id FROM compiler_runtime.propagation_execution_bindings WHERE execution_id=%s',
        (execution_id,)).fetchone() if execution_id is not None else None)
    if claim is None:
        if binding is not None:
            _fail('propagation_claim_required', 6)
        return None
    if (not isinstance(claim, dict) or set(claim) != {'task_id', 'lease_token'}
            or (binding is not None and str(binding['task_id']) != claim['task_id'])):
        _fail('invalid_propagation_claim', 6)
    task_id, token = request_id(claim['task_id']), request_id(claim['lease_token'])
    try:
        conn.execute('SELECT compiler_runtime.assert_propagation_claim(%s,%s,%s)', (task_id, token, execution_id))
    except RaiseException:
        _fail('propagation_claim_lost', 6)
    row = conn.execute('''SELECT r.run_id,r.scope,r.policy FROM compiler_runtime.propagation_tasks t
        JOIN compiler_runtime.propagation_runs r USING(run_id) WHERE t.task_id=%s''', (task_id,)).fetchone()
    return {'run_id': str(row['run_id']), 'task_id': task_id, 'scope': _json(row['scope']), 'policy': _json(row['policy'])}


def _quote_metadata(value):
    if isinstance(value, list):
        return [_quote_metadata(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: deepcopy(item) if key == 'semantic_payload' else _quote_metadata(item)
              for key, item in value.items() if key != 'quote'}
    if isinstance(value.get('quote'), str):
        result.update(quote_sha256=sha256(value['quote'].encode()).hexdigest(), quote_character_count=len(value['quote']))
    return result


def _selection(job):
    return job['profile']['schema_version'] in (SELECTION_PROFILE, multi.PROFILE)


def _input_ids(packet):
    return multi.check_input(packet) if packet.get('schema_version') == multi.INPUT_SCHEMA else check_selection_input(packet)


class KnowledgeRuntime:
    def __init__(self, dsn, *, realm_guard=None, require_realm=False):
        self.dsn = dsn
        if type(require_realm) is not bool or (realm_guard is not None and realm_guard.source_dsn != dsn):
            _fail('realm_configuration_mismatch', 3)
        # False is the preserved low-level legacy API. Product entry points set
        # True; scoped stored jobs always require their guard in every mode.
        self.realm_guard, self.require_realm = realm_guard, require_realm

    def request_profile(self, request_id_value):
        """Read the original request's profile without creating or changing it."""
        identifier = request_id(str(request_id_value))
        with connection(self.dsn) as conn:
            row = conn.execute('''SELECT p.payload->>'schema_version' AS schema_version
                FROM compiler_runtime.k_execution_contexts c
                JOIN compiler_runtime.operation_executions e USING(execution_id)
                JOIN compiler_runtime.profiles p ON p.profile_id=e.profile_id
                WHERE c.request_id=%s''', (identifier,)).fetchone()
        return row['schema_version'] if row is not None else None

    @staticmethod
    def _event(conn, job, state, error=None):
        conn.execute('''INSERT INTO compiler_runtime.execution_events
            (execution_id,attempt,state,error_code) VALUES (%s,%s,%s,%s)''',
            (job['execution_id'], job['attempt'], state, error))

    @staticmethod
    def _job(conn, execution_id, lock=False):
        row = conn.execute('''SELECT e.*,c.request_id,c.request_fingerprint,c.work_fingerprint,
            c.input_digest,c.input_snapshot,c.expected_state_version,c.generator_profile_id,
            c.validator_profile_id,c.validation_context_sha,p.payload AS profile
            FROM compiler_runtime.operation_executions e
            JOIN compiler_runtime.k_execution_contexts c USING(execution_id)
            JOIN compiler_runtime.profiles p ON p.profile_id=e.profile_id
            WHERE e.execution_id=%s''' + (' FOR UPDATE OF e' if lock else ''),
            (request_id(str(execution_id)),)).fetchone()
        if row is None:
            _fail('knowledge_job_not_found', 2)
        return row

    @staticmethod
    def _nodes(conn):
        nodes = _json(conn.execute('''SELECT n.knode_id,n.kind,n.current_revision_id,
            r.knode_revision_id,r.semantic_payload,r.statement,r.identity_fingerprint,
            r.content_fingerprint,r.origin_record_id,r.supersedes_revision_id,
            s.identity_scope,s.source_data_id,
            COALESCE((SELECT jsonb_agg(DISTINCT i.data_id) FROM canonical_store.knowledge_node_groundings g
                JOIN canonical_store.knowledge_node_revisions gr ON gr.knode_revision_id=g.node_revision_id
                JOIN canonical_store.information i USING(information_id) WHERE gr.knode_id=n.knode_id),'[]'::jsonb) AS grounding_data_ids
            FROM canonical_store.knowledge_nodes n
            JOIN canonical_store.knowledge_node_revisions r ON r.knode_revision_id=n.current_revision_id
            LEFT JOIN canonical_store.knowledge_node_scopes s ON s.knode_id=n.knode_id
            ORDER BY n.knode_id''').fetchall())
        state = knowledge_provenance.load(conn)
        if state is not None:
            for node in nodes:
                if (node['knode_revision_id'] in state['by_result']
                        or node['knode_revision_id'] in state.get('data_groundings', {}) or 'current_supports' in state):
                    node.update(knowledge_provenance.describe(state, node['knode_revision_id']))
                    node['grounding_data_ids'] = sorted(set(node['grounding_data_ids']) | set(node['source_data_ids']))
                    node.update(knowledge_provenance.data_reference_metadata(node))
        versions = version_provenance.load(conn)
        if versions is not None:
            for node in nodes:
                node.update(version_provenance.annotate(versions, node))
        return nodes

    @staticmethod
    def _version_context(conn, operation, packet, versions, mode, *, lock=False):
        if not versions:
            return
        if mode not in ('current', 'pinned') or versions != immutable_versions(conn, [v['version_id'] for v in versions]):
            _fail('data_version_context_changed', 6)
        allowed = {v['data_id'] for v in versions}
        if operation in ('i2k', 'd2k'):
            actual = set(packet['source_data_ids']) if packet.get('schema_version') == multi.INPUT_SCHEMA else {packet['data_id']}
            if allowed != actual:
                _fail('data_version_source_mismatch', 6)
        else:
            actual = set()
            for node in packet['nodes']:
                revision = node['knode_revision_id']
                actual.update(row['data_id'] for row in conn.execute(
                    'SELECT canonical_store.derivation_source_data(%s) AS data_id', (revision,)).fetchall())
                if not conn.execute('SELECT canonical_store.k_revision_supported_by_version_data(%s,%s::text[]) AS ok',
                                    (revision, sorted(allowed))).fetchone()['ok']:
                    _fail('data_version_source_mismatch', 6)
            if not allowed <= actual:
                _fail('data_version_source_mismatch', 6)
        if mode == 'current':
            series_ids = [v['series_id'] for v in versions]
            if len(series_ids) != len(set(series_ids)):
                _fail('ambiguous_current_data_versions', 2)
            heads = conn.execute('SELECT series_id,head_version_id FROM canonical_store.data_series '
                'WHERE series_id=ANY(%s::uuid[]) ORDER BY series_id' + (' FOR SHARE' if lock else ''),
                (series_ids,)).fetchall()
            current = {str(row['series_id']): str(row['head_version_id']) if row['head_version_id'] else None for row in heads}
            for version in versions:
                if current.get(version['series_id']) != version['version_id']:
                    raise PalimpsestError('data_version_head_changed', '입력 자료의 현재 버전이 변경됐습니다.', 6,
                        {'series_id': version['series_id'], 'bound_version': version['version_id'],
                         'current_head': current.get(version['series_id'])})

    @classmethod
    def _inference_input(cls, conn, data_id, revision_ids, *, allowed_data_ids=None, edge_revision_ids=None):
        if edge_revision_ids is not None:
            return k2k_effective_runtime.build_input(conn, cls, data_id, revision_ids, edge_revision_ids,
                allowed_data_ids=allowed_data_ids)
        state = knowledge_provenance.load(conn)
        if state is None:
            _fail('k2k_schema_required', 3)
        current = {node['knode_revision_id']: node for node in cls._nodes(conn)}
        selected = []
        for identifier in revision_ids:
            identifier = request_id(identifier)
            if identifier not in current:
                _fail('knowledge_input_changed', 6)
            node = {**current[identifier], **knowledge_provenance.describe(state, identifier)}
            if node['current_applicability'] != 'current_premises':
                _fail('k2k_premise_needs_revalidation', 6)
            if allowed_data_ids is not None:
                if not conn.execute('SELECT canonical_store.k_revision_supported_by_version_data(%s,%s::text[]) AS ok',
                        (identifier, allowed_data_ids)).fetchone()['ok']:
                    _fail('propagation_data_scope_mismatch', 6)
                node = _quote_metadata(node)
            selected.append(node)
        packet = k2k.build_input(selected, data_id)
        if data_id not in {owner for node in selected for owner in node['source_data_ids']}:
            _fail('k2k_source_owner_unfounded')
        return packet

    def inference_input(self, data_id, revision_ids=(), *, edge_revision_ids=None):
        validate_data_id(data_id)
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            return self._inference_input(conn, data_id, revision_ids, edge_revision_ids=edge_revision_ids)

    @staticmethod
    def _edges(conn):
        edges = _json(conn.execute('''SELECT e.kedge_id,e.predicate,e.from_knode_id,e.to_knode_id,
            e.current_revision_id,r.kedge_revision_id,r.from_knode_revision_id,r.to_knode_revision_id,
            r.semantic_payload,r.qualifiers,r.rationale,r.identity_fingerprint,r.content_fingerprint,
            r.origin_record_id,r.supersedes_revision_id
            FROM canonical_store.knowledge_edges e
            JOIN canonical_store.knowledge_edge_revisions r ON r.kedge_revision_id=e.current_revision_id
            ORDER BY e.kedge_id''').fetchall())
        state = version_provenance.load(conn)
        for edge in edges:
            edge.update(version_provenance.annotate(state, edge))
        return edges

    @staticmethod
    def _profile(conn, value):
        profile_sha = digest(value)
        conn.execute('''INSERT INTO compiler_runtime.profiles(profile_hash,payload)
            VALUES (%s,%s) ON CONFLICT DO NOTHING''', (profile_sha, Jsonb(value)))
        return conn.execute('SELECT profile_id FROM compiler_runtime.profiles WHERE profile_hash=%s',
                            (profile_sha,)).fetchone()['profile_id']

    @staticmethod
    def _verify_i(conn, data_id, packet):
        if (not isinstance(packet, dict) or packet.get('schema_version') != 'i2k-input-v1'
                or packet.get('data_id') != data_id or not isinstance(packet.get('model_input'), dict)):
            _fail('invalid_knowledge_input')
        source_id = request_id(packet.get('source_execution_id'))
        source = conn.execute('''SELECT e.state,e.data_id,e.profile_id,p.payload,a.bundle
            FROM compiler_runtime.operation_executions e JOIN compiler_runtime.profiles p USING(profile_id)
            JOIN compiler_runtime.parse_artifacts a USING(execution_id) WHERE e.execution_id=%s''', (source_id,)).fetchone()
        if source is None or source['data_id'] != data_id or source['state'] != 'completed':
            _fail('knowledge_input_changed', 6)
        rows = conn.execute('''SELECT i.* FROM canonical_store.information i
            JOIN compiler_runtime.records r ON r.record_id=i.origin_record_id
            WHERE r.execution_id=%s ORDER BY r.ordinal''', (source_id,)).fetchall()
        for row in rows:
            row['groundings'] = conn.execute('SELECT * FROM canonical_store.information_groundings WHERE information_id=%s ORDER BY block_id',
                                            (row['information_id'],)).fetchall()
        expected = build_input(source['bundle'], _json(rows), execution_id=source_id,
            profile_id=str(source['profile_id']), selected_information_ids=packet.get('target_information_ids'),
            context_information_ids=packet.get('context_information_ids'),
            assembly_algorithm=source['payload']['transformation']['algorithm'])
        # Evidence review signals are retained as untrusted supplemental hints;
        # source I, page/byte locators, grouped ranges and media come from the DB.
        comparable = deepcopy(packet)
        comparable.get('model_input', {})['quality_evidence'] = expected['model_input']['quality_evidence']
        comparable.pop('input_sha256', None)
        expected.pop('input_sha256')
        if comparable != expected or packet.get('input_sha256') != digest({key: value for key, value in packet.items() if key != 'input_sha256'}):
            _fail('knowledge_input_changed', 6)
        return [unit['information_id'] for unit in packet['model_input']['information']]

    @classmethod
    def _verify_input(cls, conn, data_id, packet):
        if packet.get('schema_version') != multi.INPUT_SCHEMA:
            return cls._verify_i(conn, data_id, packet)
        ids = multi.check_input(packet)
        if packet['data_id'] != data_id:
            _fail('invalid_knowledge_input')
        actual = [identifier for source in packet['sources']
                  for identifier in cls._verify_i(conn, source['data_id'], source)]
        if actual != ids:
            _fail('knowledge_input_changed', 6)
        return ids

    def prepare(self, operation, data_id, request_id_value, input_snapshot, *, model_profile=None,
                selection=False, feedback_execution_id=None, source_review=None,
                data_version_ids=None, data_version_mode='current', authorization_id=None, retry_of_execution_id=None,
                target_knode_id=None, expected_revision_id=None, revalidation_target=None, propagation_claim=None,
                edge_review_target=None, n2e_policy=None, realm_scope=None):
        validate_data_id(data_id)
        identifier = request_id(str(request_id_value))
        if data_version_mode not in ('current', 'pinned') or (data_version_ids is None and data_version_mode != 'current'):
            _fail('invalid_data_version_context', 2)
        if data_version_ids is not None:
            if not isinstance(data_version_ids, (list, tuple)) or not data_version_ids:
                _fail('invalid_data_version_context', 2)
            data_version_ids = [request_id(value) for value in data_version_ids]
            if len(set(data_version_ids)) != len(data_version_ids):
                _fail('invalid_data_version_context', 2)
        if operation not in ('i2k', 'n2e', 'k2k', 'd2k'):
            _fail('invalid_knowledge_operation', 2)
        if realm_scope is not None and operation != 'i2k':
            _fail('invalid_realm_operation', 2)
        if propagation_claim is not None and operation not in ('n2e', 'k2k'):
            _fail('invalid_propagation_operation', 2)
        revision_requested = target_knode_id is not None or expected_revision_id is not None
        if edge_review_target is not None:
            n2e_relations.check_target(edge_review_target)
            if operation != 'n2e' or revalidation_target is not None or revision_requested:
                _fail('invalid_n2e_review_target', 2)
        if n2e_policy not in (None, PROFILE, n2e_relations.PROFILE) or (n2e_policy and operation != 'n2e'):
            _fail('invalid_n2e_policy', 2)
        if revalidation_target is not None:
            revalidation.check_target(revalidation_target)
            if ((operation == 'k2k' and (not revision_requested or revalidation_target['kind'] != 'node'))
                    or (operation == 'n2e' and (revision_requested or revalidation_target['kind'] != 'edge'))
                    or operation not in ('n2e', 'k2k')):
                _fail('invalid_revalidation_target', 2)
        if revision_requested:
            if target_knode_id is None or expected_revision_id is None or operation not in ('i2k', 'k2k'):
                _fail('invalid_knowledge_revision_request', 2)
            target_knode_id, expected_revision_id = request_id(target_knode_id), request_id(expected_revision_id)
            if feedback_execution_id is not None or source_review is True:
                _fail('invalid_knowledge_revision_request', 2)
            source_review = False
        if operation == 'd2k':
            if authorization_id is None:
                _fail('d2k_user_confirmation_required', 2)
            authorization_id = request_id(authorization_id)
            if retry_of_execution_id is not None:
                retry_of_execution_id = request_id(retry_of_execution_id)
        elif authorization_id is not None or retry_of_execution_id is not None:
            _fail('invalid_d2k_authorization_operation', 2)
        previous_profile = None
        if selection is None or source_review is None or operation in ('i2k', 'n2e'):
            with connection(self.dsn) as conn:
                previous_profile = conn.execute('''SELECT p.payload FROM compiler_runtime.k_execution_contexts c
                    JOIN compiler_runtime.operation_executions e USING(execution_id)
                    JOIN compiler_runtime.profiles p ON p.profile_id=e.profile_id WHERE c.request_id=%s''',
                    (identifier,)).fetchone()
                if operation == 'n2e' and n2e_policy is None:
                    n2e_policy = (previous_profile['payload']['schema_version'] if previous_profile else
                        n2e_relations.PROFILE if n2e_runtime.available(conn) and revalidation_target is None else PROFILE)
        modern_n2e = operation == 'n2e' and n2e_policy == n2e_relations.PROFILE
        if edge_review_target is not None and not modern_n2e:
            _fail('n2e_schema_required', 3)
        if selection is None:
            selection = (previous_profile['payload']['schema_version'] in (SELECTION_PROFILE, multi.PROFILE)
                         if previous_profile else operation == 'i2k')
        is_multi = isinstance(input_snapshot, dict) and input_snapshot.get('schema_version') == multi.INPUT_SCHEMA
        if revision_requested and operation == 'i2k' and not is_multi:
            _fail('knowledge_revision_explicit_source_required', 2)
        error_policy = is_multi and (previous_profile is None or
            previous_profile['payload'].get('information_error_policy') == information_errors.POLICY)
        if is_multi:
            selection = True
        if type(selection) is not bool or (selection and operation != 'i2k'):
            _fail('invalid_selection_operation', 2)
        if source_review is None:
            source_review = (previous_profile['payload'].get('source_review') == source_review_contract.PROFILE
                             if previous_profile else selection)
        if type(source_review) is not bool or (source_review and not selection):
            _fail('invalid_source_review_operation', 2)
        if feedback_execution_id is not None:
            if not selection:
                _fail('invalid_selection_feedback', 2)
            feedback_execution_id = request_id(str(feedback_execution_id))
        profile_name = d2k.PROFILE if operation == 'd2k' else k2k.PROFILE if operation == 'k2k' else multi.PROFILE if is_multi else SELECTION_PROFILE if selection else PROFILE
        effective_inference = operation == 'k2k' and input_snapshot.get('schema_version') == k2k_effective.INPUT_SCHEMA
        if effective_inference:
            profile_name = k2k_effective.PROFILE
        if modern_n2e:
            profile_name = n2e_relations.PROFILE
        model = deepcopy(MODEL if model_profile is None else model_profile)
        if not isinstance(model, dict) or model != MODEL:
            _fail('invalid_knowledge_profile', 2)
        supplied = _json(input_snapshot)
        request_payload = {'operation': operation, 'data_id': data_id, 'input': supplied,
                           'profile': profile_name, 'model': model}
        if revalidation_target is not None:
            request_payload['revalidation_target'] = revalidation_target
        if edge_review_target is not None:
            request_payload['edge_review_target'] = edge_review_target
        if revision_requested:
            request_payload.update(explicit_knowledge_revision=revision_runtime.PROFILE,
                target_knode_id=target_knode_id, expected_revision_id=expected_revision_id)
        if operation == 'd2k':
            request_payload.update(authorization_id=authorization_id, retry_of_execution_id=retry_of_execution_id)
        if source_review:
            request_payload['source_review'] = source_review_contract.PROFILE
        if error_policy:
            request_payload['information_error_policy'] = information_errors.POLICY
        if data_version_ids is not None:
            request_payload.update(data_version_ids=data_version_ids, data_version_mode=data_version_mode)
        bound_realm_scope = None
        with connection(self.dsn) as conn, conn.transaction():
            # ponytail: the small current K catalog and commits share one short lock.
            state = conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton FOR UPDATE').fetchone()['version']
            propagation_scope = _propagation_claim(conn, propagation_claim)
            if propagation_scope is not None:
                request_payload['propagation_scope'] = propagation_scope
                if data_id not in propagation_scope['scope']['allowed_data_ids']:
                    _fail('propagation_data_scope_mismatch', 6)
            feedback = None
            if feedback_execution_id is not None:
                prior = self._job(conn, feedback_execution_id)
                if (prior['operation'] != 'i2k' or prior['data_id'] != data_id
                        or prior['profile']['schema_version'] != profile_name
                        or (prior['input_snapshot']['input'].get('input_sha256') != supplied.get('input_sha256') if is_multi else
                            prior['input_snapshot']['input'].get('source_execution_id') != supplied.get('source_execution_id'))
                        or prior['state'] not in ('completed', 'zero_output', 'needs_human', 'failed')
                        or (prior['state'] != 'failed' and prior['validator_receipt'] is None)):
                    _fail('invalid_selection_feedback', 6)
                feedback = _json({'execution_id': feedback_execution_id, 'input_digest': prior['input_digest'],
                    'validation_context_sha': prior['validation_context_sha'], 'state': prior['state'],
                    'generator_reviews': conn.execute('''SELECT information_id,disposition,reason FROM compiler_runtime.k_information_reviews
                        WHERE execution_id=%s ORDER BY information_id''', (feedback_execution_id,)).fetchall(),
                    'validator_reviews': conn.execute('''SELECT information_id,verdict,reason_codes,reason FROM compiler_runtime.k_information_review_decisions
                        WHERE execution_id=%s ORDER BY information_id''', (feedback_execution_id,)).fetchall()})
                if prior['profile'].get('source_review') == source_review_contract.PROFILE:
                    feedback['source_review'] = {
                        'manifest': prior['input_snapshot']['source_review_manifest'],
                        'generator_reviews': (prior['generator_receipt'] or {}).get('source_reviews'),
                        'validation': (prior['validator_receipt'] or {}).get('source_review_result')}
                if prior['state'] == 'failed':
                    failed = conn.execute('''SELECT call_id,input_sha256,output_sha256,receipt FROM compiler_runtime.k_model_calls
                        WHERE execution_id=%s AND phase='generator' AND status='failed' ORDER BY call_id DESC LIMIT 1''',
                        (feedback_execution_id,)).fetchone()
                    if failed is None:
                        _fail('invalid_selection_feedback', 6)
                    feedback['failed_generator'] = _json({'call_id':failed['call_id'],
                        'input_sha256':failed['input_sha256'],'output_sha256':failed['output_sha256'],
                        'error_code':failed['receipt'].get('structural_error_code'),
                        'issues':failed['receipt'].get('structural_feedback',[])})
                    earlier = prior['input_snapshot'].get('selection_feedback')
                    if earlier:
                        semantic_review = earlier if earlier.get('validator_reviews') else earlier.get('prior_review')
                        if semantic_review:
                            feedback['prior_review'] = deepcopy(semantic_review)
                request_payload['selection_feedback'] = feedback
            previous = conn.execute('''SELECT c.execution_id,c.request_fingerprint,c.input_snapshot->'realm_scope' AS realm_scope,
                p.payload->>'realm_i2k_policy' AS realm_policy FROM compiler_runtime.k_execution_contexts c
                JOIN compiler_runtime.operation_executions e USING(execution_id)
                JOIN compiler_runtime.profiles p USING(profile_id) WHERE c.request_id=%s''', (identifier,)).fetchone()
            if operation == 'i2k':
                from . import realm_i2k
                feedback_scope = prior['input_snapshot'].get('realm_scope') if feedback_execution_id is not None else None
                if previous:
                    old_scope = previous['realm_scope']
                    if (old_scope is None) != (previous['realm_policy'] is None) or previous['realm_policy'] not in (None, realm_i2k.PROFILE):
                        _fail('realm_i2k_scope_mismatch', 6)
                    if self.realm_guard is not None and self.realm_guard.realm_ids:
                        if old_scope is None or set(self.realm_guard.realm_ids) != {ref['realm_id'] for ref in old_scope['realm_revisions']}:
                            _fail('idempotency_conflict', 6)
                    bound_realm_scope = realm_scope if realm_scope is not None else old_scope
                    if bound_realm_scope is not None:
                        if self.realm_guard is None:
                            _fail('realm_configuration_required', 3)
                        bound_realm_scope = self.realm_guard.verify(conn, bound_realm_scope, supplied, data_version_ids or ())
                elif self.realm_guard is not None:
                    bound_realm_scope = self.realm_guard.prepare(conn, supplied, scope=realm_scope,
                        feedback_scope=feedback_scope, version_ids=data_version_ids or ())
                elif realm_scope is not None or feedback_scope is not None:
                    _fail('realm_configuration_required', 3)
                elif self.require_realm:
                    raise PalimpsestError('realm_required', '새 I2K 실행에는 Realm 선택이 필요합니다.', 2)
                if bound_realm_scope is not None:
                    request_payload['realm_scope'] = bound_realm_scope
            fingerprint = digest(request_payload)
            if previous:
                if previous['request_fingerprint'] != fingerprint:
                    _fail('idempotency_conflict', 6)
                _propagation_claim(conn, propagation_claim, previous['execution_id'])
                return {**_json(self._job(conn, previous['execution_id'])), 'replayed': True}
            if feedback_execution_id is not None:
                active = conn.execute('''SELECT e.execution_id FROM compiler_runtime.k_execution_contexts c
                    JOIN compiler_runtime.operation_executions e USING(execution_id)
                    WHERE c.input_snapshot->'selection_feedback'->>'execution_id'=%s
                      AND e.state IN ('prepared','proposed') ORDER BY e.execution_id LIMIT 1''',
                    (feedback_execution_id,)).fetchone()
                if active is not None:
                    raise PalimpsestError('review_resume_in_progress', '같은 검토의 후속 실행이 이미 진행 중입니다.', 6,
                        {'execution_id': str(active['execution_id'])})
            nodes, edges = self._nodes(conn), self._edges(conn)
            if modern_n2e and not n2e_runtime.available(conn):
                _fail('n2e_schema_required', 3)
            actual_nodes = nodes
            allowed_data_ids = propagation_scope['scope']['allowed_data_ids'] if propagation_scope else None
            if allowed_data_ids is not None:
                nodes = [_quote_metadata(node) for node in nodes if conn.execute('''SELECT
                    canonical_store.k_revision_supported_by_version_data(%s,%s::text[])
                    AND compiler_runtime.current_k2k_premise(%s) AS ok''',
                    (node['knode_revision_id'], allowed_data_ids, node['knode_revision_id'])).fetchone()['ok']]
                allowed_nodes = {node['knode_id'] for node in nodes}
                edges = [_quote_metadata(edge) for edge in edges if edge['from_knode_id'] in allowed_nodes and edge['to_knode_id'] in allowed_nodes]
            authorization, d2k_feedback = None, None
            if operation == 'd2k':
                from .d2k_runtime import bind_execution
                d2k.check_input(supplied)
                if supplied['data_id'] != data_id:
                    _fail('d2k_authorization_scope_mismatch', 6)
                versions = immutable_versions(conn, data_version_ids) if data_version_ids else []
                authorization, nodes, d2k_feedback = bind_execution(conn, authorization_id, supplied,
                    model, versions, data_version_mode, nodes, retry_of_execution_id)
                refs, edges = [], []
            elif operation == 'i2k':
                refs = self._verify_input(conn, data_id, supplied)
                from .realm_registration import verify_ready
                owners = [source['data_id'] for source in supplied['sources']] if is_multi else [data_id]
                verify_ready(conn, owners, self.realm_guard.catalog if self.realm_guard else None,
                             self.realm_guard.store_id if self.realm_guard else None)
                if selection:
                    _input_ids(supplied)
                    for source in supplied['sources'] if is_multi else [supplied]:
                        media_type = conn.execute('SELECT media_type FROM canonical_store.data WHERE data_id=%s',
                                                  (source['data_id'],)).fetchone()['media_type']
                        if media_type == 'application/pdf' and source.get('source_assembly_algorithm') != 'source-groups-pages-v1':
                            _fail('source_page_information_required', 2)
            elif operation == 'k2k':
                refs = k2k.check_input(supplied)
                edge_refs = k2k_effective_runtime.edge_ids(supplied) if effective_inference else None
                if supplied != self._inference_input(conn, data_id, refs, edge_revision_ids=edge_refs):
                    _fail('knowledge_input_changed', 6)
                if allowed_data_ids is not None:
                    supplied = self._inference_input(conn, data_id, refs, allowed_data_ids=allowed_data_ids,
                        edge_revision_ids=edge_refs)
            else:
                if (not isinstance(supplied, dict) or supplied.get('schema_version') != 'n2e-input-v1'
                        or not isinstance(supplied.get('nodes'), list) or not supplied['nodes']):
                    _fail('invalid_knowledge_input')
                current = {node['knode_revision_id']: node for node in nodes}
                refs = []
                for node in supplied['nodes']:
                    revision = request_id(node['knode_revision_id'])
                    if (revision in refs or revision not in current or any(node.get(key) != current[revision][key]
                            for key in ('knode_id', 'kind', 'semantic_payload', 'statement', 'content_fingerprint'))):
                        _fail('knowledge_input_changed', 6)
                    refs.append(revision)
                evidence = _json(conn.execute('SELECT * FROM canonical_store.knowledge_node_groundings ORDER BY grounding_id').fetchall())
                supplied['nodes'] = [{**current[revision], 'groundings':
                    [grounding for grounding in evidence if grounding['node_revision_id'] == revision]}
                    for revision in refs]
                if allowed_data_ids is not None:
                    supplied['nodes'] = _quote_metadata(supplied['nodes'])
                if modern_n2e:
                    n2e_runtime.check_endpoints(conn, supplied['nodes'])
                    if data_id not in {owner for node in supplied['nodes'] for owner in
                                       node.get('source_data_ids', node['grounding_data_ids'])}:
                        _fail('n2e_source_owner_unfounded', 6)
                    selected_ids = {node['knode_id'] for node in supplied['nodes']}
                    edges = [edge for edge in edges if edge['from_knode_id'] in selected_ids and edge['to_knode_id'] in selected_ids]
            snapshot = {'input': supplied, 'existing_nodes': nodes, 'existing_edges': edges}
            if bound_realm_scope is not None:
                snapshot['realm_scope'] = deepcopy(bound_realm_scope)
                snapshot['existing_nodes'], snapshot['existing_edges'] = realm_i2k.comparison_catalog(nodes, edges)
            if modern_n2e:
                snapshot['n2e_policy'] = n2e_relations.PROFILE
                snapshot['n2e_request_input'] = _json(input_snapshot)
                if edge_review_target is not None:
                    frozen_edge = n2e_runtime.freeze(conn, edges, nodes, edge_review_target['target_revision_id'],
                        supplied, edge_review_target['prior_pair'])
                    if frozen_edge != edge_review_target:
                        _fail('n2e_review_target_changed', 6)
                    snapshot['edge_review_target'] = frozen_edge
            if propagation_scope is not None:
                snapshot['propagation_scope'] = propagation_scope
            if revalidation_target is not None:
                frozen = (revalidation.freeze_node(actual_nodes, knowledge_provenance.load(conn),
                    revalidation_target['target_revision_id'], supplied) if operation == 'k2k' else
                    revalidation.freeze_edge(conn, edges, nodes, revalidation_target['target_revision_id'],
                        supplied, revalidation_target['prior_pair']))
                if frozen != revalidation_target:
                    _fail('revalidation_target_changed', 6)
                snapshot['revalidation_target'] = frozen
            if revision_requested:
                target = revision_runtime.freeze_request(actual_nodes, operation=operation,
                    target_knode_id=target_knode_id, expected_revision_id=expected_revision_id)
                if allowed_data_ids is not None:
                    if not conn.execute('SELECT canonical_store.k_revision_supported_by_version_data(%s,%s::text[]) AS ok',
                            (expected_revision_id, allowed_data_ids)).fetchone()['ok']:
                        _fail('propagation_data_scope_mismatch', 6)
                    if expected_revision_id not in {node['knode_revision_id'] for node in nodes}:
                        # Stale target is comparison context, never an inference premise.
                        snapshot['existing_nodes'].append(_quote_metadata(next(n for n in actual_nodes if n['knode_revision_id'] == expected_revision_id)))
                if operation == 'k2k':
                    provenance = knowledge_provenance.load(conn)
                    if any(ref == expected_revision_id or expected_revision_id in
                           knowledge_provenance.ancestors(provenance, ref) for ref in refs):
                        _fail('knowledge_revision_premise_boundary', 2)
                if (operation == 'i2k' and target['target']['identity_scope'] == 'source'
                        and target['target']['source_data_id'] not in supplied['source_data_ids']):
                    _fail('knowledge_revision_identity_mismatch', 2)
                snapshot['revision_target'] = target
            if authorization is not None:
                snapshot['authorization'] = authorization
                if d2k_feedback is not None:
                    snapshot['prior_d2k_review'] = d2k_feedback
            if error_policy:
                snapshot['information_error_policy'] = information_errors.POLICY
            if (operation in ('k2k', 'n2e') and data_version_ids is None
                    and any(node.get('data_version_supports') for node in supplied['nodes'])):
                _fail('data_version_context_required', 2)
            if data_version_ids is not None:
                versions = immutable_versions(conn, data_version_ids)
                self._version_context(conn, operation, supplied, versions, data_version_mode, lock=True)
                snapshot.update(data_versions=versions, data_version_mode=data_version_mode)
            if source_review:
                snapshot['source_review_manifest'] = source_review_contract.build_manifest(supplied)
            if feedback is not None:
                snapshot['selection_feedback'] = feedback
            input_sha = digest(snapshot)
            profile = {'schema_version': profile_name, 'operation': operation, 'model': model,
                       'generator_prompt': operation + ('-source-complete-v1' if selection else '-paper-v1'),
                       'validator_prompt': operation + ('-source-complete-validator-v1' if selection else '-paper-validator-v1')}
            if selection:
                if is_multi:
                    profile['multi_source_implementation_sha256'] = _multi_implementation()
                    profile.update(generator_prompt='i2k-multi-explicit-v1', validator_prompt='i2k-multi-explicit-validator-v1')
                else:
                    profile['selection_implementation_sha256'] = _selection_implementation()
            if modern_n2e:
                profile.update(n2e_policy=n2e_relations.PROFILE, n2e_implementation_sha256=n2e_runtime.implementation(),
                    generator_prompt='n2e-relations-v1', validator_prompt='n2e-relations-validator-v1')
            if source_review:
                profile.update(source_review=source_review_contract.PROFILE,
                               source_review_implementation_sha256=_source_review_implementation())
            if bound_realm_scope is not None:
                profile['realm_i2k_policy'] = realm_i2k.PROFILE
            if operation == 'k2k':
                profile.update(generator_prompt='k2k-inference-v1', validator_prompt='k2k-inference-validator-v1',
                    input_scope='exact_node_premises', inference_implementation_sha256=_inference_implementation())
                if conn.execute("SELECT to_regclass('canonical_store.knowledge_current_supports') AS relation").fetchone()['relation']:
                    profile['current_support_binding'] = revalidation.SUPPORT_PROFILE
                if effective_inference:
                    profile.update(input_scope='exact_effective_bundle', effective_inputs=k2k_effective.PROFILE,
                        effective_inference_implementation_sha256=k2k_effective_runtime.implementation())
            if revalidation_target is not None:
                profile.update(targeted_revalidation=revalidation.PROFILE,
                               revalidation_implementation_sha256=_revalidation_implementation())
            if operation == 'd2k':
                profile.update(generator_prompt='d2k-explicit-source-v1', validator_prompt='d2k-explicit-source-validator-v1',
                    input_scope='user_confirmed_original_views', d2k_implementation_sha256=_d2k_implementation())
            if data_version_ids is not None:
                profile.update(data_version_context='data-version-context-v1',
                               data_version_implementation_sha256=_version_implementation())
            if error_policy:
                profile.update(information_error_policy=information_errors.POLICY,
                               information_error_implementation_sha256=_information_error_implementation())
            if revision_requested:
                profile.update(explicit_knowledge_revision=revision_runtime.PROFILE,
                               knowledge_revision_implementation_sha256=_revision_implementation())
            if propagation_scope and revision_runtime.materiality_guidance(snapshot, operation, 'generator'):
                profile['materiality_policy'] = revision_runtime.MATERIALITY_POLICY
            profile_id = self._profile(conn, profile)
            generator_profile = self._profile(conn, {'phase': 'generator', **profile})
            validator_profile = self._profile(conn, {'phase': 'validator', **profile})
            generation = conn.execute('''SELECT COALESCE(max(generation),0)+1 AS n
                FROM compiler_runtime.operation_executions WHERE operation=%s AND data_id=%s AND profile_id=%s''',
                (operation, data_id, profile_id)).fetchone()['n']
            job = conn.execute('''INSERT INTO compiler_runtime.operation_executions
                (operation,data_id,profile_id,generation) VALUES (%s,%s,%s,%s) RETURNING *''',
                (operation, data_id, profile_id, generation)).fetchone()
            if edge_review_target is not None:
                state = n2e_runtime.open_fence(conn, job['execution_id'], edge_review_target)
            conn.execute('''INSERT INTO compiler_runtime.k_execution_contexts
                (execution_id,request_id,request_fingerprint,work_fingerprint,input_digest,input_snapshot,
                 expected_state_version,generator_profile_id,validator_profile_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (job['execution_id'], identifier, fingerprint, fingerprint, input_sha, Jsonb(snapshot),
                 state, generator_profile, validator_profile))
            if operation == 'd2k':
                conn.execute('''INSERT INTO compiler_runtime.d2k_execution_authorizations
                    (execution_id,authorization_id,prior_execution_id) VALUES (%s,%s,%s)''',
                    (job['execution_id'], authorization_id, retry_of_execution_id))
            if revision_requested:
                conn.execute('''INSERT INTO compiler_runtime.k_revision_targets
                    (execution_id,target_knode_id,expected_revision_id,target_sha256,snapshot)
                    VALUES (%s,%s,%s,%s,%s)''', (job['execution_id'], target_knode_id,
                    expected_revision_id, target['target_sha256'], Jsonb(target)))
            if is_multi:
                for ordinal, source in enumerate(supplied['sources']):
                    conn.execute('''INSERT INTO compiler_runtime.k_execution_sources
                        (execution_id,ordinal,data_id,source_execution_id,input_sha256) VALUES (%s,%s,%s,%s,%s)''',
                        (job['execution_id'], ordinal, source['data_id'], source['source_execution_id'], source['input_sha256']))
            for ordinal, ref in enumerate(refs):
                if operation == 'i2k':
                    conn.execute('''INSERT INTO compiler_runtime.k_input_information
                        (execution_id,ordinal,information_id) VALUES (%s,%s,%s)''', (job['execution_id'], ordinal, ref))
                else:
                    conn.execute('''INSERT INTO compiler_runtime.k_input_node_revisions
                        (execution_id,ordinal,node_revision_id) VALUES (%s,%s,%s)''', (job['execution_id'], ordinal, ref))
            for version_id in data_version_ids or []:
                conn.execute('INSERT INTO compiler_runtime.k_execution_data_versions(execution_id,version_id) VALUES (%s,%s)',
                             (job['execution_id'], version_id))
            if effective_inference:
                k2k_effective_runtime.bind_inputs(conn, job['execution_id'], supplied)
            if revalidation_target is not None:
                conn.execute('INSERT INTO compiler_runtime.k_revalidation_targets(execution_id,snapshot) VALUES (%s,%s)',
                             (job['execution_id'], Jsonb(revalidation_target)))
            if propagation_claim is not None:
                conn.execute('''INSERT INTO compiler_runtime.propagation_execution_bindings
                    (execution_id,task_id,lease_token) VALUES (%s,%s,%s)''',
                    (job['execution_id'], propagation_claim['task_id'], propagation_claim['lease_token']))
            self._event(conn, job, 'prepared')
            return {**_json(self._job(conn, job['execution_id'])), 'replayed': False}

    @staticmethod
    def _receipt(receipt, job, phase, output, *, validation_context=None):
        from . import batched_i2k

        expected_input = job['input_digest'] if phase == 'generator' else job['validation_context_sha']
        batched = receipt.get('delivery_mode') == batched_i2k.PROFILE if isinstance(receipt, dict) else False
        if (not isinstance(receipt, dict) or 'source_review_result' in receipt or 'revision_result' in receipt or 'revalidation_result' in receipt
                or 'effective_validation_output' in receipt
                or not isinstance(receipt.get('profile'), dict)
                or any(receipt['profile'].get(key) != value for key, value in job['profile']['model'].items())
                or receipt.get('input_sha256') != expected_input
                or receipt.get('output_sha256') != digest(output) or receipt.get('actual_delivery') is not True
                or not (receipt.get('provider_ref') or receipt.get('thread_ref'))):
            _fail('knowledge_provider_receipt_mismatch')
        required = {}
        if n2e_runtime.modern(job['input_snapshot']):
            snapshot = job['input_snapshot']
            if (job['profile'].get('n2e_policy') != n2e_relations.PROFILE or
                    (job['validator_receipt'] is None and job['profile'].get('n2e_implementation_sha256') != n2e_runtime.implementation())):
                _fail('n2e_implementation_changed', 6)
            if receipt.get('delivered_knowledge_revision_ids') != [node['knode_revision_id'] for node in snapshot['input']['nodes']]:
                _fail('knowledge_premise_delivery_mismatch')
            if snapshot.get('edge_review_target') and receipt.get('delivered_edge_review_target_sha256') != snapshot['edge_review_target']['target_sha256']:
                _fail('n2e_review_target_delivery_mismatch')
            if phase == 'validator' and job['validator_receipt'] is not None:
                expected_prompt, expected_schema = (job['validator_receipt'][key] for key in ('prompt_sha256', 'schema_sha256'))
            else:
                if phase == 'validator' and validation_context is None:
                    _fail('knowledge_validation_context_changed', 6)
                prompt, schema = (edge_generation_request(snapshot) if phase == 'generator' else
                    edge_validation_request({**validation_context, 'validation_context_sha': job['validation_context_sha']}))
                expected_prompt, expected_schema = sha256(prompt.encode()).hexdigest(), digest(schema)
            if receipt.get('prompt_sha256') != expected_prompt or receipt.get('schema_sha256') != expected_schema:
                _fail('knowledge_prompt_delivery_mismatch')
        if job['operation'] == 'i2k':
            for unit in job['input_snapshot']['input']['model_input']['information']:
                for media in unit['media']:
                    required[media['sha256']] = media['byte_size']
        elif job['operation'] == 'd2k':
            required = {v['image_sha256']: v['image_byte_size'] for v in job['input_snapshot']['input']['views']
                        if v['kind'] == 'pdf_page'}
        attachments = receipt.get('image_attachments', [])
        if not isinstance(attachments, list):
            _fail('knowledge_image_delivery_mismatch')
        supplied = {}
        for attachment in attachments:
            if (not isinstance(attachment, dict) or set(attachment) != {'sha256', 'byte_size'}
                    or not isinstance(attachment['sha256'], str) or attachment['sha256'] in supplied
                    or type(attachment['byte_size']) is not int):
                _fail('knowledge_image_delivery_mismatch')
            supplied[attachment['sha256']] = attachment['byte_size']
        if required != supplied:
            _fail('knowledge_image_delivery_mismatch')
        if (_selection(job)
                and receipt.get('delivered_information_ids') != _input_ids(job['input_snapshot']['input'])):
            _fail('knowledge_information_delivery_mismatch')
        target = job['input_snapshot'].get('revision_target')
        review_target = job['input_snapshot'].get('revalidation_target')
        if review_target is not None or job['profile'].get('targeted_revalidation') is not None:
            revalidation.check_target(review_target)
            if (job['profile'].get('targeted_revalidation') != revalidation.PROFILE
                    or receipt.get('delivered_revalidation_target_sha256') != review_target['target_sha256']):
                _fail('revalidation_target_delivery_mismatch')
            if (job['validator_receipt'] is None
                    and job['profile'].get('revalidation_implementation_sha256') != _revalidation_implementation()):
                _fail('revalidation_implementation_changed', 6)
            if receipt.get('delivered_knowledge_revision_ids') != [n['knode_revision_id'] for n in job['input_snapshot']['input']['nodes']]:
                _fail('knowledge_premise_delivery_mismatch')
            if review_target['kind'] == 'edge':
                if phase == 'generator':
                    prompt, schema = edge_generation_request(job['input_snapshot'])
                    expected_prompt, expected_schema = sha256(prompt.encode()).hexdigest(), digest(schema)
                elif job['validator_receipt'] is not None:
                    expected_prompt, expected_schema = job['validator_receipt']['prompt_sha256'], job['validator_receipt']['schema_sha256']
                else:
                    if validation_context is None:
                        _fail('knowledge_validation_context_changed', 6)
                    prompt, schema = edge_validation_request({**validation_context, 'validation_context_sha': job['validation_context_sha']})
                    expected_prompt, expected_schema = sha256(prompt.encode()).hexdigest(), digest(schema)
                if receipt.get('prompt_sha256') != expected_prompt or receipt.get('schema_sha256') != expected_schema:
                    _fail('knowledge_prompt_delivery_mismatch')
        if target is not None or job['profile'].get('explicit_knowledge_revision') is not None:
            if (target is None or job['profile'].get('explicit_knowledge_revision') != revision_runtime.PROFILE
                    or target['operation'] != job['operation']):
                _fail('knowledge_revision_profile_changed', 6)
            revision_runtime.bind_candidates([], target)
            if receipt.get('delivered_revision_target_id') != target['expected_revision_id']:
                _fail('knowledge_revision_target_delivery_mismatch')
            if (job['validator_receipt'] is None
                    and job['profile'].get('knowledge_revision_implementation_sha256') != _revision_implementation()):
                _fail('knowledge_revision_implementation_changed', 6)
        if job['profile'].get('information_error_policy') is not None:
            if (job['profile']['information_error_policy'] != information_errors.POLICY
                    or job['input_snapshot'].get('information_error_policy') != information_errors.POLICY
                    or (job['validator_receipt'] is None and job['profile'].get('information_error_implementation_sha256')
                        != _information_error_implementation())):
                _fail('information_error_policy_changed',6)
        if _selection(job):
            is_multi = job['profile']['schema_version'] == multi.PROFILE
            key = 'multi_source_implementation_sha256' if is_multi else 'selection_implementation_sha256'
            implementation = _multi_implementation() if is_multi else _selection_implementation()
            if job['validator_receipt'] is None and job['profile'].get(key) != implementation:
                _fail('selection_implementation_changed', 6)
            if (job['validator_receipt'] is None and job['profile'].get('source_review') is not None
                    and job['profile'].get('source_review_implementation_sha256') != _source_review_implementation()):
                _fail('source_review_implementation_changed', 6)
            if batched:
                if job['operation'] != 'i2k' or not is_multi or job['profile'].get('source_review') != source_review_contract.PROFILE:
                    _fail('invalid_batched_i2k', 2)
                batched_i2k.verify_aggregate(receipt, output, job, phase,
                                             validation_context=validation_context)
            else:
                snapshot = job['input_snapshot']
                if phase == 'generator':
                    prompt, schema = generation_request(snapshot, attachments)
                    expected_prompt, expected_schema = sha256(prompt.encode('utf-8')).hexdigest(), digest(schema)
                elif job['validator_receipt'] is not None:
                    expected_prompt = job['validator_receipt']['prompt_sha256']
                    expected_schema = job['validator_receipt']['schema_sha256']
                else:
                    if validation_context is None:
                        _fail('knowledge_validation_context_changed', 6)
                    context = {**validation_context, 'validation_context_sha': job['validation_context_sha']}
                    prompt, schema = validation_request(context, attachments)
                    expected_prompt, expected_schema = sha256(prompt.encode('utf-8')).hexdigest(), digest(schema)
                if receipt.get('prompt_sha256') != expected_prompt or receipt.get('schema_sha256') != expected_schema:
                    _fail('knowledge_prompt_delivery_mismatch')
        elif batched:
            _fail('invalid_batched_i2k', 2)
        if job['operation'] == 'd2k':
            snapshot = job['input_snapshot']
            if receipt.get('delivered_data_view_ids') != d2k.check_input(snapshot['input']):
                _fail('d2k_view_delivery_mismatch')
            if receipt.get('delivered_knowledge_revision_ids') != [n['knode_revision_id'] for n in snapshot['existing_nodes']]:
                _fail('knowledge_premise_delivery_mismatch')
            if job['validator_receipt'] is None and job['profile'].get('d2k_implementation_sha256') != _d2k_implementation():
                _fail('d2k_implementation_changed', 6)
            if phase == 'generator':
                prompt, schema = d2k.generation(snapshot, attachments), d2k.generation_schema(snapshot['input'])
                expected_prompt, expected_schema = sha256(prompt.encode()).hexdigest(), digest(schema)
            elif job['validator_receipt'] is not None:
                expected_prompt, expected_schema = job['validator_receipt']['prompt_sha256'], job['validator_receipt']['schema_sha256']
            else:
                if validation_context is None:
                    _fail('knowledge_validation_context_changed', 6)
                context = {**validation_context, 'validation_context_sha': job['validation_context_sha']}
                prompt = d2k.validation(context, attachments)
                schema = d2k.validation_schema([n['candidate_key'] for n in context['candidates']],
                    [n['knode_revision_id'] for n in snapshot['existing_nodes']], snapshot['input'])
                expected_prompt, expected_schema = sha256(prompt.encode()).hexdigest(), digest(schema)
            if receipt.get('prompt_sha256') != expected_prompt or receipt.get('schema_sha256') != expected_schema:
                _fail('knowledge_prompt_delivery_mismatch')
        if job['operation'] == 'k2k':
            snapshot = job['input_snapshot']
            if snapshot['input'].get('schema_version') == k2k_effective.INPUT_SCHEMA:
                if (job['profile']['schema_version'] != k2k_effective.PROFILE
                        or (job['validator_receipt'] is None and job['profile'].get('effective_inference_implementation_sha256')
                            != k2k_effective_runtime.implementation())):
                    _fail('effective_k2k_implementation_changed', 6)
                if any(receipt.get(key) != value for key, value in k2k_effective_runtime.delivery(snapshot['input']).items()):
                    _fail('effective_k2k_delivery_mismatch')
            if receipt.get('delivered_knowledge_revision_ids') != k2k.check_input(snapshot['input']):
                _fail('knowledge_premise_delivery_mismatch')
            if (job['validator_receipt'] is None
                    and job['profile'].get('inference_implementation_sha256') != _inference_implementation()):
                _fail('inference_implementation_changed', 6)
            if phase == 'generator':
                prompt, schema = k2k.generation_request(snapshot, attachments)
                expected_prompt, expected_schema = sha256(prompt.encode()).hexdigest(), digest(schema)
            elif job['validator_receipt'] is not None:
                expected_prompt, expected_schema = job['validator_receipt']['prompt_sha256'], job['validator_receipt']['schema_sha256']
            else:
                if validation_context is None:
                    _fail('knowledge_validation_context_changed', 6)
                context = {**validation_context, 'validation_context_sha': job['validation_context_sha']}
                prompt, schema = k2k.validation_request(context, attachments)
                expected_prompt, expected_schema = sha256(prompt.encode()).hexdigest(), digest(schema)
            if receipt.get('prompt_sha256') != expected_prompt or receipt.get('schema_sha256') != expected_schema:
                _fail('knowledge_prompt_delivery_mismatch')
        if job['input_snapshot'].get('data_versions'):
            snapshot = job['input_snapshot']
            if receipt.get('delivered_data_version_ids') != [v['version_id'] for v in snapshot['data_versions']]:
                _fail('data_version_delivery_mismatch')
            if (job['validator_receipt'] is None
                    and job['profile'].get('data_version_implementation_sha256') != _version_implementation()):
                _fail('data_version_implementation_changed', 6)
            if job['operation'] == 'n2e':
                if receipt.get('delivered_knowledge_revision_ids') != [node['knode_revision_id'] for node in snapshot['input']['nodes']]:
                    _fail('knowledge_premise_delivery_mismatch')
                if phase == 'generator':
                    prompt, schema = edge_generation_request(snapshot)
                    expected_prompt, expected_schema = sha256(prompt.encode()).hexdigest(), digest(schema)
                elif job['validator_receipt'] is not None:
                    expected_prompt, expected_schema = job['validator_receipt']['prompt_sha256'], job['validator_receipt']['schema_sha256']
                else:
                    if validation_context is None:
                        _fail('knowledge_validation_context_changed', 6)
                    context = {**validation_context, 'validation_context_sha': job['validation_context_sha']}
                    prompt, schema = edge_validation_request(context)
                    expected_prompt, expected_schema = sha256(prompt.encode()).hexdigest(), digest(schema)
                if receipt.get('prompt_sha256') != expected_prompt or receipt.get('schema_sha256') != expected_schema:
                    _fail('knowledge_prompt_delivery_mismatch')
        if phase == 'validator':
            previous = job['generator_receipt']
            if (receipt.get('provider_ref') or receipt.get('thread_ref')) == (
                    previous.get('provider_ref') or previous.get('thread_ref')):
                _fail('knowledge_validator_not_independent')

    @staticmethod
    def _call(conn, job, phase, receipt):
        conn.execute('''INSERT INTO compiler_runtime.k_model_calls
            (execution_id,phase,profile_id,input_sha256,output_sha256,provider_ref,receipt,usage,status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'succeeded')''',
            (job['execution_id'], phase, job[phase + '_profile_id'], receipt['input_sha256'],
             receipt['output_sha256'], receipt.get('provider_ref') or receipt.get('thread_ref'),
             Jsonb(receipt), Jsonb(receipt.get('usage', {}))))

    @staticmethod
    def _records(conn, execution_id):
        return conn.execute('''SELECT r.*,c.body FROM compiler_runtime.k_compilation_records r
            LEFT JOIN compiler_runtime.k_temporary_candidates c USING(record_id)
            WHERE execution_id=%s ORDER BY ordinal''', (execution_id,)).fetchall()

    @staticmethod
    def _context(job, records):
        generator = job['generator_receipt']
        result = {'schema_version': 'knowledge-validation-v1', 'operation': job['operation'],
                'input_snapshot': deepcopy(job['input_snapshot']),
                'candidates': [deepcopy(record['body']) for record in records],
                'generator_complete': generator['generation_complete'],
                'source_requests': deepcopy(generator.get('source_requests', [])),
                'coverage_notes': deepcopy(generator.get('coverage_notes', []))}
        if _selection(job):
            result.update(selection_profile=job['profile']['schema_version'],
                          information_reviews=deepcopy(generator['information_reviews']),
                          profile=deepcopy(job['profile']),
                          generator_prompt_sha256=generator.get('prompt_sha256'),
                          generator_schema_sha256=generator.get('schema_sha256'),
                          generator_output_sha256=generator['output_sha256'])
        if 'source_review_manifest' in job['input_snapshot']:
            result['source_reviews'] = deepcopy(generator['source_reviews'])
        if job['operation'] == 'k2k':
            result.update(inference_profile=k2k.PROFILE, profile=deepcopy(job['profile']))
        if job['operation'] == 'd2k':
            result.update(view_reviews=deepcopy(generator['view_reviews']), profile=deepcopy(job['profile']))
        if job['input_snapshot'].get('revalidation_target') is not None:
            result['revalidation_target'] = deepcopy(job['input_snapshot']['revalidation_target'])
        return result

    def stage(self, execution_id, response, receipt, *, propagation_claim=None):
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton FOR UPDATE')
            _propagation_claim(conn, propagation_claim, execution_id)
            job = self._job(conn, execution_id, True)
            from .realm_i2k import verify_job
            verify_job(self, conn, job)
            self._receipt(receipt, job, 'generator', response)
            if job['generator_receipt'] is not None:
                if job['generator_receipt'].get('output_sha256') != receipt['output_sha256']:
                    _fail('idempotency_conflict', 6)
                if job['state'] != 'proposed':
                    _fail('knowledge_already_decided', 6)
                context = self._context(job, self._records(conn, execution_id))
                _propagation_claim(conn, propagation_claim, execution_id)
                return {**context, 'validation_context_sha': job['validation_context_sha']}
            if job['state'] != 'prepared':
                _fail('invalid_knowledge_state', 6)
            if job['input_snapshot'].get('data_versions'):
                self._version_context(conn, job['operation'], job['input_snapshot']['input'],
                    job['input_snapshot']['data_versions'], job['input_snapshot']['data_version_mode'], lock=True)
            source = job['input_snapshot']['input']
            selection = _selection(job)
            raw_response = deepcopy(response)
            manifest = job['input_snapshot'].get('source_review_manifest')
            if manifest is not None:
                raw_response.pop('source_reviews', None)
            if selection:
                normalized = (multi.normalize_proposals(raw_response, source) if job['profile']['schema_version'] == multi.PROFILE else
                              normalize_selection(raw_response, source))
                candidates = normalized['nodes']
            elif job['operation'] == 'd2k':
                normalized = d2k.normalize_proposals(response, source)
                candidates = normalized['nodes']
            elif job['operation'] == 'i2k':
                candidates = normalize_nodes(response, source)
            elif job['operation'] == 'k2k':
                candidates = k2k.normalize_proposals(response, source)
                depths = {node['knode_revision_id']: node['derivation_depth'] for node in source['nodes']}
                for candidate in candidates:
                    candidate['derivation_depth'] = 1 + max(depths[ref] for ref in candidate['premise_revision_ids'])
                    if (job['input_snapshot'].get('revalidation_target') is not None
                            and candidate['premise_revision_ids'] != job['input_snapshot']['revalidation_target']['premise_revision_ids']):
                        _fail('revalidation_premises_changed', 6)
            else:
                if n2e_runtime.modern(job['input_snapshot']):
                    candidates = n2e_relations.normalize_response(response, job['input_snapshot'])
                elif job['input_snapshot'].get('revalidation_target') is not None:
                    candidates, _ = revalidation.normalize_edge_response(response,
                        {node['knode_revision_id']: node for node in source['nodes']}, job['input_snapshot']['revalidation_target'])
                else:
                    candidates = normalize_edges(response, {node['knode_revision_id']: node for node in source['nodes']})
            target = job['input_snapshot'].get('revision_target')
            if target is not None:
                current = revision_runtime.freeze_request(self._nodes(conn), operation=job['operation'],
                    target_knode_id=target['target_knode_id'], expected_revision_id=target['expected_revision_id'])
                if current != target:
                    _fail('knowledge_revision_target_changed', 6)
                candidates = revision_runtime.bind_candidates(candidates, target)
            generator = {**deepcopy(receipt), 'generation_complete': response['complete'],
                         'source_requests': deepcopy(response.get('source_requests', [])),
                         'coverage_notes': deepcopy(response.get('coverage_notes', []))}
            if manifest is not None:
                generator['source_reviews'] = source_review_contract.normalize_generation(response, manifest, candidates)
            if job['operation'] == 'd2k':
                generator['view_reviews'] = normalized['reviews']
            if selection:
                if job['profile']['schema_version'] == multi.PROFILE:
                    generator['source_requests'] = normalized['source_requests']
                generator['information_reviews'] = normalized['reviews']
                generator['review_link_completions'] = normalized['link_completions']
                for review in normalized['reviews']:
                    conn.execute('''INSERT INTO compiler_runtime.k_information_reviews
                        (execution_id,information_id,disposition,reason) VALUES (%s,%s,%s,%s)''',
                        (execution_id, review['information_id'], review['disposition'], review['reason']))
            job['generator_receipt'] = generator
            context = self._context(job, [{'body': candidate} for candidate in candidates])
            context_sha = digest(context)
            for ordinal, candidate in enumerate(candidates):
                row = conn.execute('''INSERT INTO compiler_runtime.k_compilation_records
                    (execution_id,record_type,ordinal,identity_fingerprint,content_fingerprint,context_fingerprint)
                    VALUES (%s,%s,%s,%s,%s,%s) RETURNING record_id''',
                    (execution_id, job['operation'], ordinal, candidate['identity_fingerprint'],
                     candidate['content_fingerprint'], context_sha)).fetchone()
                conn.execute('INSERT INTO compiler_runtime.k_temporary_candidates(record_id,body) VALUES (%s,%s)',
                             (row['record_id'], Jsonb(candidate)))
                if selection:
                    for review in normalized['reviews']:
                        if candidate['candidate_key'] in review['candidate_keys']:
                            conn.execute('''INSERT INTO compiler_runtime.k_information_review_records
                                (execution_id,information_id,record_id) VALUES (%s,%s,%s)''',
                                (execution_id, review['information_id'], row['record_id']))
            for source_request in generator['source_requests']:
                error_receipt = {'actual_delivery':False,'reason_code':'native_pdf_unsupported',
                                 'source_input_sha256':job['input_digest']}
                if job['profile'].get('information_error_policy') == information_errors.POLICY:
                    error_receipt.update(reason_code='d2i_information_error',
                        action='notify_user_and_hold',status='reported_error',verification_status='verification_pending',
                        direct_source_compilation_allowed=False,d2i_calls=0)
                conn.execute('''INSERT INTO compiler_runtime.k_source_requests(execution_id,payload,status,receipt)
                    VALUES (%s,%s,'unavailable',%s)''', (execution_id, Jsonb(source_request),
                    Jsonb(error_receipt)))
            self._call(conn, job, 'generator', receipt)
            conn.execute('''UPDATE compiler_runtime.operation_executions SET state='proposed',generator_receipt=%s,
                updated_at=clock_timestamp() WHERE execution_id=%s''', (Jsonb(generator), execution_id))
            conn.execute('UPDATE compiler_runtime.k_execution_contexts SET validation_context_sha=%s WHERE execution_id=%s',
                         (context_sha, execution_id))
            self._event(conn, job, 'proposed')
            # A lease can expire while this short transaction performs work.
            # Recheck after every write, just before publication becomes durable.
            if propagation_claim is not None:
                conn.execute('SET CONSTRAINTS ALL IMMEDIATE')
            _propagation_claim(conn, propagation_claim, execution_id)
            return {**context, 'validation_context_sha': context_sha}

    def validation_context(self, execution_id):
        with connection(self.dsn) as conn:
            job = self._job(conn, execution_id)
            if job['state'] != 'proposed':
                _fail('invalid_knowledge_state', 6)
            context = self._context(job, self._records(conn, execution_id))
            if digest(context) != job['validation_context_sha']:
                _fail('knowledge_validation_context_changed', 6)
            return {**context, 'validation_context_sha': job['validation_context_sha']}

    @staticmethod
    def _resolve(conn, record, disposition, decision, node=None, edge=None):
        conn.execute('''UPDATE compiler_runtime.k_compilation_records
            SET disposition=%s,reason_codes=%s,reason=%s,result_node_id=%s,result_node_revision_id=%s,
            result_edge_id=%s,result_edge_revision_id=%s,
            resolved_at=CASE WHEN %s='needs_human' THEN NULL ELSE clock_timestamp() END
            WHERE record_id=%s''', (disposition, Jsonb(decision['reason_codes']), decision['reason'],
            node['knode_id'] if node else None, node['knode_revision_id'] if node else None,
            edge['kedge_id'] if edge else None, edge['kedge_revision_id'] if edge else None,
            disposition, record['record_id']))
        if disposition != 'needs_human':
            conn.execute('DELETE FROM compiler_runtime.k_temporary_candidates WHERE record_id=%s', (record['record_id'],))

    @staticmethod
    def _ground(conn, record, revision_id, evidence):
        for citation in evidence:
            duplicate = conn.execute('''SELECT 1 FROM canonical_store.knowledge_node_groundings
                WHERE node_revision_id=%s AND information_id=%s AND char_start=%s AND char_end=%s
                AND quote=%s AND media_sha256 IS NOT DISTINCT FROM %s AND source_role=%s''',
                (revision_id, citation['information_id'], citation['char_start'], citation['char_end'],
                 citation['quote'], citation['media_sha256'], citation['source_role'])).fetchone()
            if duplicate:
                continue
            conn.execute('''INSERT INTO canonical_store.knowledge_node_groundings
                (node_revision_id,information_id,char_start,char_end,quote,media_sha256,source_role,origin_record_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''', (revision_id, citation['information_id'],
                citation['char_start'], citation['char_end'], citation['quote'], citation['media_sha256'],
                citation['source_role'], record['record_id']))

    @staticmethod
    def _ground_data(conn, record, revision_id, evidence):
        for citation in evidence:
            conn.execute('''INSERT INTO canonical_store.knowledge_data_groundings
                (node_revision_id,data_id,view_id,evidence,origin_record_id) VALUES (%s,%s,%s,%s,%s)''',
                (revision_id,citation['data_id'],citation['view_id'],Jsonb(citation),record['record_id']))

    def _commit_nodes(self, conn, job, records, decisions, checkpoint):
        by_key = {record['body']['candidate_key']: record for record in records}
        existing = {node['knode_revision_id']: node for node in job['input_snapshot']['existing_nodes']}
        results = {}
        selection = _selection(job)
        inference = job['operation'] == 'k2k'
        direct = job['operation'] == 'd2k'
        scoped = selection or inference or direct
        is_multi = job['profile']['schema_version'] == multi.PROFILE
        for key, decision in decisions.items():
            record, verdict = by_key[key], decision['verdict']
            body = record['body']
            if verdict in ('rejected', 'needs_human'):
                self._resolve(conn, record, verdict, decision)
                continue
            if verdict == 'reused':
                if decision['equivalent_candidate_key'] is not None and decision['equivalent_candidate_key'] not in results:
                    self._resolve(conn, record, 'needs_human', {'reason_codes': ['reuse_target_unresolved'],
                        'reason': 'The earlier reused candidate requires review before dependent support can be published.'})
                    continue
                node = (results[decision['equivalent_candidate_key']] if decision['equivalent_candidate_key'] is not None
                        else existing[decision['equivalent_revision_id']])
                if node['kind'] != body['kind']:
                    _fail('invalid_knowledge_reuse')
                if scoped:
                    self._check_scope(conn, body, node, job)
                disposition = 'reused'
            else:
                duplicate = conn.execute('''SELECT n.knode_id,n.kind,r.knode_revision_id,r.content_fingerprint
                    FROM canonical_store.knowledge_nodes n JOIN canonical_store.knowledge_node_revisions r
                    ON r.knode_revision_id=n.current_revision_id WHERE n.kind=%s AND n.identity_fingerprint=%s''',
                    (body['kind'], body['identity_fingerprint'])).fetchone()
                if duplicate is None and scoped:
                    # Material successors retain their original logical FP.
                    # Exact current content/scope can therefore match a new
                    # ordinary candidate whose freshly computed FP differs.
                    matches = conn.execute('''SELECT n.knode_id,n.kind,r.knode_revision_id,r.content_fingerprint
                        FROM canonical_store.knowledge_nodes n JOIN canonical_store.knowledge_node_revisions r
                        ON r.knode_revision_id=n.current_revision_id JOIN canonical_store.knowledge_node_scopes s ON s.knode_id=n.knode_id
                        WHERE n.kind=%s AND r.content_fingerprint=%s AND s.identity_scope=%s
                          AND s.source_data_id IS NOT DISTINCT FROM %s ORDER BY n.knode_id''',
                        (body['kind'], body['content_fingerprint'], body['identity_scope'], body['source_data_id'])).fetchall()
                    if len(matches) > 1:
                        self._resolve(conn, record, 'needs_human', {'reason_codes': ['knowledge_exact_reuse_ambiguous'],
                            'reason': 'More than one logical Knowledge target has this exact current content and scope.'})
                        continue
                    duplicate = matches[0] if matches else None
                if duplicate:
                    if ((direct or job['input_snapshot'].get('propagation_scope')) and str(duplicate['knode_revision_id']) not in existing
                            and str(duplicate['knode_revision_id']) not in {
                                str(node['knode_revision_id']) for node in results.values()}):
                        self._resolve(conn, record, 'needs_human', {'reason_codes': ['propagation_catalog_scope_required' if job['input_snapshot'].get('propagation_scope') else 'd2k_catalog_confirmation_required'],
                            'reason': 'The exact matching Knowledge was created outside the confirmed catalog. '
                                      'Review a new manifest before reusing that revision.'})
                        continue
                    if duplicate['content_fingerprint'] != body['content_fingerprint']:
                        _fail('knowledge_revision_required', 6)
                    node, disposition = _json(duplicate), 'reused'
                    if scoped:
                        node = next(current for current in self._nodes(conn) if current['knode_id'] == str(duplicate['knode_id']))
                        self._check_scope(conn, body, node, job)
                else:
                    node = {'knode_id': _uuid(conn), 'knode_revision_id': _uuid(conn), 'kind': body['kind']}
                    conn.execute('''INSERT INTO canonical_store.knowledge_nodes
                        (knode_id,kind,identity_fingerprint,current_revision_id) VALUES (%s,%s,%s,%s)''',
                        (node['knode_id'], body['kind'], body['identity_fingerprint'], node['knode_revision_id']))
                    conn.execute('''INSERT INTO canonical_store.knowledge_node_revisions
                        (knode_revision_id,knode_id,semantic_payload,statement,identity_fingerprint,content_fingerprint,origin_record_id)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)''', (node['knode_revision_id'], node['knode_id'],
                        Jsonb(body['semantic_payload']), body['statement'], body['identity_fingerprint'],
                        body['content_fingerprint'], record['record_id']))
                    disposition = 'accepted_new'
                    conn.execute("INSERT INTO compiler_runtime.k_outbox(record_id,operation) VALUES (%s,'n2e')", (record['record_id'],))
            if inference:
                self._derive(conn, job, record, node, decision)
            elif direct:
                self._ground_data(conn, record, node['knode_revision_id'], body['direct_evidence'])
            else:
                self._ground(conn, record, node['knode_revision_id'], body['evidence'])
            if scoped:
                scope = conn.execute('SELECT * FROM canonical_store.knowledge_node_scopes WHERE knode_id=%s',
                                     (node['knode_id'],)).fetchone()
                if scope is None:
                    conn.execute('''INSERT INTO canonical_store.knowledge_node_scopes
                        (knode_id,identity_scope,source_data_id,origin_record_id) VALUES (%s,%s,%s,%s)''',
                        (node['knode_id'], body['identity_scope'], body['source_data_id'], record['record_id']))
                elif scope['identity_scope'] != body['identity_scope'] or scope['source_data_id'] != body['source_data_id']:
                    _fail('knowledge_scope_reuse_conflict')
                node.update(identity_scope=body['identity_scope'], source_data_id=body['source_data_id'],
                            grounding_data_ids=(sorted(set(node.get('grounding_data_ids', [])) |
                                {e['data_id'] for e in body['evidence']}) if is_multi else
                                [job['data_id']] if body['identity_scope'] == 'source' else node.get('grounding_data_ids', [])))
            if checkpoint:
                checkpoint('after_knowledge_effect')
            self._resolve(conn, record, disposition, decision, node=node)
            results[key] = node

    def _commit_revision_nodes(self, conn, job, records, decisions, review, checkpoint):
        target = job['input_snapshot']['revision_target']
        candidates = [record['body'] for record in records]
        resolutions = revision_runtime.resolve_decisions(candidates, decisions, target, review)
        stale = False
        try:
            current = revision_runtime.freeze_request(self._nodes(conn), operation=job['operation'],
                target_knode_id=target['target_knode_id'], expected_revision_id=target['expected_revision_id'])
            stale = current != target
        except PalimpsestError as error:
            if error.code != 'knowledge_revision_target_changed':
                raise
            stale = True
        for record in records:
            body = record['body']
            resolution = resolutions[body['candidate_key']]
            if stale:
                resolution.update(action='needs_human', result_content_fingerprint=None,
                    origin={'mode': 'no_publication'},
                    reason_codes=list(dict.fromkeys([*resolution['reason_codes'], 'knowledge_revision_target_changed'])))
            conn.execute('''INSERT INTO compiler_runtime.k_revision_decisions
                (record_id,target_sha256,validation) VALUES (%s,%s,%s)''',
                (record['record_id'], target['target_sha256'], Jsonb(resolution)))
            decision = deepcopy(resolution['decision'])
            action = resolution['action']
            revalidation_target = job['input_snapshot'].get('revalidation_target')
            if revalidation_target is not None:
                confirmation = {'kind': 'node', 'target_sha256': revalidation_target['target_sha256'],
                    'confirmed': action in ('accepted_revision', 'reused'),
                    'material_change': resolution['review']['material_change'],
                    'same_identity': resolution['review']['same_identity'], 'grounding_valid': resolution['review']['grounding_valid'],
                    'premise_revision_ids': list(body['premise_revision_ids']),
                    'prior_support_record_id': revalidation_target['prior_support_record_id'],
                    'reason_codes': list(resolution['review']['reason_codes']), 'reason': resolution['review']['reason']}
                conn.execute('INSERT INTO compiler_runtime.k_revalidation_decisions(record_id,validation) VALUES (%s,%s)',
                             (record['record_id'], Jsonb(confirmation)))
            if action in ('needs_human', 'rejected'):
                decision.update(reason_codes=list(dict.fromkeys([*decision['reason_codes'], *resolution['reason_codes']])),
                    reason=decision['reason'] + ' Explicit revision: ' + resolution['review']['reason'])
                self._resolve(conn, record, action, decision)
                continue
            if action == 'accepted_revision':
                node = revision_runtime.commit_revision(conn, record, body, target, resolution)
            else:
                node = deepcopy(target['target'])
                decision.update(verdict='reused', equivalent_candidate_key=None,
                                equivalent_revision_id=target['expected_revision_id'])
                self._check_scope(conn, body, node, job)
            if job['operation'] == 'k2k':
                self._derive(conn, job, record, node, decision)
            else:
                self._ground(conn, record, node['knode_revision_id'], body['evidence'])
            if revalidation_target is not None:
                conn.execute('''INSERT INTO canonical_store.knowledge_current_supports
                    (record_id,node_revision_id,previous_support_record_id) VALUES (%s,%s,%s)''',
                    (record['record_id'], node['knode_revision_id'], revalidation_target['prior_support_record_id']))
            self._resolve(conn, record, action, decision, node=node)
            if action == 'accepted_revision':
                impacts = revision_runtime.enumerate_impacts(conn, target['expected_revision_id'])
                conn.execute('''INSERT INTO compiler_runtime.k_revision_impacts
                    (record_id,source_revision_id,impacts) VALUES (%s,%s,%s)''',
                    (record['record_id'], target['expected_revision_id'], Jsonb(impacts)))
                for operation in ('n2e', 'k2k'):
                    conn.execute('INSERT INTO compiler_runtime.k_outbox(record_id,operation) VALUES (%s,%s)',
                                 (record['record_id'], operation))
            if checkpoint:
                checkpoint('after_knowledge_effect')
        return {'target': deepcopy(target), 'resolutions': resolutions,
            'requires_user_review': not resolutions or stale or any(
                result['action'] == 'needs_human' or (job['input_snapshot'].get('revalidation_target') is not None
                    and result['action'] not in ('accepted_revision', 'reused')) for result in resolutions.values()),
            'propagation_status': 'outbox_pending_not_converged' if any(
                result['action'] == 'accepted_revision' for result in resolutions.values()) else 'no_new_semantic_branch'}

    @staticmethod
    def _derive(conn, job, record, node, decision):
        body = record['body']
        state = knowledge_provenance.load(conn)
        target = node['knode_revision_id']
        for premise in body['premise_revision_ids']:
            if target == premise or target in knowledge_provenance.ancestors(state, premise):
                _fail('k2k_derivation_cycle')
        owners = {owner for premise in body['premise_revision_ids']
                  for owner in knowledge_provenance.describe(state, premise)['source_data_ids']}
        if body['identity_scope'] == 'source' and body['source_data_id'] not in owners:
            _fail('k2k_source_owner_unfounded')
        conn.execute('''INSERT INTO canonical_store.knowledge_derivations
            (record_id,result_node_revision_id,inference_type,assumptions,limitations,derivation_basis,derivation_depth,validation)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''', (record['record_id'], target, body['inference_type'],
                Jsonb(body['assumptions']), Jsonb(body['limitations']), body['derivation_basis'],
                body['derivation_depth'], Jsonb(decision)))
        for ordinal, premise in enumerate(body['premise_revision_ids']):
            conn.execute('''INSERT INTO canonical_store.knowledge_derivation_premises
                (record_id,premise_node_revision_id,ordinal) VALUES (%s,%s,%s)''', (record['record_id'], premise, ordinal))
            if job['profile'].get('current_support_binding') == revalidation.SUPPORT_PROFILE:
                frozen = next(n for n in job['input_snapshot']['input']['nodes'] if n['knode_revision_id'] == premise)
                conn.execute('''INSERT INTO canonical_store.knowledge_derivation_support_refs
                    (record_id,premise_node_revision_id,support_record_id) VALUES (%s,%s,%s)''',
                    (record['record_id'], premise, frozen['current_support_record_id']))
        k2k_effective_runtime.bind_derivation(conn, job, record)

    @staticmethod
    def _check_scope(conn, body, node, job):
        if job['profile']['schema_version'] != multi.PROFILE:
            return check_scope_reuse(body, node, job['data_id'])
        if node.get('identity_scope') is None and body['identity_scope'] == 'source':
            # Legacy I2K used one Data. Preserve that original attribution while
            # allowing later papers to explicitly corroborate the same study.
            origin = conn.execute('''SELECT e.data_id FROM canonical_store.knowledge_node_revisions n
                JOIN compiler_runtime.k_compilation_records r ON r.record_id=n.origin_record_id
                JOIN compiler_runtime.operation_executions e ON e.execution_id=r.execution_id
                WHERE n.knode_revision_id=%s''', (node['knode_revision_id'],)).fetchone()
            if origin is None or origin['data_id'] != body['source_data_id']:
                _fail('knowledge_scope_reuse_conflict')
        return multi.check_scope_reuse(body, node)

    def _guard_legacy_reuse(self, conn, job, candidates, decisions):
        """New legacy requests cannot merge unknown source identities across D.

        Successful old requests replay before this boundary. A new request can
        use the selection profile to classify an unbound legacy node explicitly.
        """
        current = self._nodes(conn)
        revisions = {node['knode_revision_id']: node for node in current}
        exact = {(node['kind'], node['identity_fingerprint']): node for node in current}
        by_key = {candidate['candidate_key']: candidate for candidate in candidates}
        for key, decision in decisions.items():
            if decision['verdict'] not in ('accepted', 'reused'):
                continue
            target_key = decision['equivalent_candidate_key']
            blocked_parent = target_key is not None and decisions[target_key]['verdict'] == 'needs_human'
            node = (revisions.get(decision['equivalent_revision_id']) if decision['verdict'] == 'reused'
                    else exact.get((by_key[key]['kind'], by_key[key]['identity_fingerprint'])))
            if target_key is not None and not blocked_parent:
                continue
            blocked_scope = node is not None and (
                (node['identity_scope'] is None and set(node['grounding_data_ids']) != {job['data_id']})
                or (node['identity_scope'] == 'source' and node['source_data_id'] != job['data_id']))
            if blocked_parent or blocked_scope:
                decisions[key] = {**decision, 'verdict': 'needs_human', 'equivalent_candidate_key': None,
                    'equivalent_revision_id': None, 'reason_codes': ['identity_scope_classification_required'],
                    'reason': 'Cross-source reuse requires a compatible explicit Knowledge identity scope.'}

    def _commit_edges(self, conn, job, records, decisions, checkpoint):
        nodes = {node['knode_revision_id']: node for node in job['input_snapshot']['input']['nodes']}
        for record in records:
            body = record['body']
            decision = decisions[body['candidate_key']]
            verdict = decision['verdict']
            if verdict in ('rejected', 'needs_human'):
                self._resolve(conn, record, verdict, decision)
                continue
            source, target = nodes[body['from_revision_id']], nodes[body['to_revision_id']]
            edge = conn.execute('''SELECT e.kedge_id,r.kedge_revision_id,r.content_fingerprint,
                r.from_knode_revision_id,r.to_knode_revision_id FROM canonical_store.knowledge_edges e
                JOIN canonical_store.knowledge_edge_revisions r ON r.kedge_revision_id=e.current_revision_id
                WHERE e.predicate=%s AND e.from_knode_id=%s AND e.to_knode_id=%s''',
                (body['predicate'], source['knode_id'], target['knode_id'])).fetchone()
            if edge:
                if edge['content_fingerprint'] != body['content_fingerprint']:
                    self._resolve(conn, record, 'needs_human', {'reason_codes': ['edge_revision_required'],
                        'reason': 'A material qualifier change requires an explicit revision proposal.'})
                    continue
                disposition = 'reused'
                latest = conn.execute('''SELECT applicable FROM canonical_store.knowledge_edge_applicability_events
                    WHERE semantic_kedge_revision_id=%s AND from_knode_revision_id=%s AND to_knode_revision_id=%s
                    ORDER BY event_order DESC LIMIT 1''', (edge['kedge_revision_id'], body['from_revision_id'],
                                                          body['to_revision_id'])).fetchone()
                original_pair = (str(edge['from_knode_revision_id']) == body['from_revision_id']
                                 and str(edge['to_knode_revision_id']) == body['to_revision_id'])
                if (latest and not latest['applicable']) or (latest is None and not original_pair):
                    conn.execute('''INSERT INTO canonical_store.knowledge_edge_applicability_events
                        (kedge_id,semantic_kedge_revision_id,from_knode_revision_id,to_knode_revision_id,
                         applicable,origin_record_id) VALUES (%s,%s,%s,%s,true,%s)''',
                        (edge['kedge_id'], edge['kedge_revision_id'], body['from_revision_id'], body['to_revision_id'], record['record_id']))
                    disposition = 'no_material_delta'
                    conn.execute("INSERT INTO compiler_runtime.k_outbox(record_id,operation) VALUES (%s,'k2k')", (record['record_id'],))
            else:
                edge = {'kedge_id': _uuid(conn), 'kedge_revision_id': _uuid(conn)}
                conn.execute('''INSERT INTO canonical_store.knowledge_edges
                    (kedge_id,predicate,from_knode_id,to_knode_id,identity_fingerprint,current_revision_id)
                    VALUES (%s,%s,%s,%s,%s,%s)''', (edge['kedge_id'], body['predicate'], source['knode_id'],
                    target['knode_id'], body['identity_fingerprint'], edge['kedge_revision_id']))
                conn.execute('''INSERT INTO canonical_store.knowledge_edge_revisions
                    (kedge_revision_id,kedge_id,from_knode_revision_id,to_knode_revision_id,semantic_payload,
                     qualifiers,rationale,identity_fingerprint,content_fingerprint,origin_record_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (edge['kedge_revision_id'], edge['kedge_id'],
                    body['from_revision_id'], body['to_revision_id'], Jsonb({'predicate': body['predicate']}),
                    Jsonb(body['qualifiers']), body['rationale'], body['identity_fingerprint'],
                    body['content_fingerprint'], record['record_id']))
                conn.execute("INSERT INTO compiler_runtime.k_outbox(record_id,operation) VALUES (%s,'k2k')", (record['record_id'],))
                disposition = 'accepted_new'
            if checkpoint:
                checkpoint('after_knowledge_effect')
            self._resolve(conn, record, disposition, decision, edge=edge)

    def _commit_edge_revalidation(self, conn, job, records, decisions, checkpoint):
        target = job['input_snapshot']['revalidation_target']
        current = revalidation.freeze_edge(conn, self._edges(conn), self._nodes(conn), target['target_revision_id'],
            job['input_snapshot']['input'], target['prior_pair'])
        if current != target:
            _fail('revalidation_target_changed', 6)
        state = knowledge_provenance.load(conn)
        for ref in (target['from_revision_id'], target['to_revision_id']):
            if knowledge_provenance.describe(state, ref)['current_applicability'] != 'current_premises':
                _fail('revalidation_dependency_pending', 6)
        validated, result = revalidation.edge_decisions(decisions, [r['body'] for r in records], target)
        if not job['generator_receipt']['generation_complete']:
            result.update(confirmed=False, material_change=False)
        for record in records:
            decision = validated[record['body']['candidate_key']]
            conn.execute('INSERT INTO compiler_runtime.k_revalidation_decisions(record_id,validation) VALUES (%s,%s)',
                         (record['record_id'], Jsonb(result)))
            if not result['confirmed']:
                self._resolve(conn, record, 'needs_human', {**decision, 'reason_codes': ['edge_applicability_unresolved'],
                    'reason': result['reason']})
                continue
            conn.execute('''INSERT INTO canonical_store.knowledge_edge_applicability_events
                (kedge_id,semantic_kedge_revision_id,from_knode_revision_id,to_knode_revision_id,applicable,origin_record_id)
                VALUES (%s,%s,%s,%s,%s,%s)''', (target['target_kedge_id'], target['target_revision_id'],
                target['from_revision_id'], target['to_revision_id'], result['applicable'], record['record_id']))
            self._resolve(conn, record, 'no_material_delta', decision,
                edge={'kedge_id': target['target_kedge_id'], 'kedge_revision_id': target['target_revision_id']})
            if result['material_change']:
                conn.execute("INSERT INTO compiler_runtime.k_outbox(record_id,operation) VALUES (%s,'k2k')", (record['record_id'],))
            if checkpoint:
                checkpoint('after_knowledge_effect')
        return {**result, 'requires_user_review': not result['confirmed']}

    def decide(self, execution_id, decisions, receipt, *, checkpoint=None, propagation_claim=None):
        with connection(self.dsn) as conn, conn.transaction():
            # Lock order matches prepare: state, then execution. Never hold this over a model call.
            version = conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton FOR UPDATE').fetchone()['version']
            _propagation_claim(conn, propagation_claim, execution_id)
            job = self._job(conn, execution_id, True)
            from .realm_i2k import verify_job
            verify_job(self, conn, job)
            validation_context = None
            if (_selection(job) or job['operation'] in ('k2k', 'd2k') or job['input_snapshot'].get('data_versions')
                    or job['input_snapshot'].get('revalidation_target') or n2e_runtime.modern(job['input_snapshot'])) and job['validator_receipt'] is None:
                validation_context = self._context(job, self._records(conn, execution_id)) if job['generator_receipt'] else None
            self._receipt(receipt, job, 'validator', decisions, validation_context=validation_context)
            if job['validator_receipt'] is not None:
                original_receipt = {key: value for key, value in job['validator_receipt'].items()
                                    if key not in ('source_review_result', 'd2k_view_reviews', 'revision_result', 'revalidation_result', 'effective_validation_output')}
                if original_receipt != receipt:
                    _fail('idempotency_conflict', 6)
                _propagation_claim(conn, propagation_claim, execution_id)
                return _json(job)
            if job['state'] != 'proposed':
                _fail('invalid_knowledge_state', 6)
            if version != job['expected_state_version'] and job['input_snapshot'].get('revision_target') is None:
                _fail('knowledge_state_changed', 6)
            if job['input_snapshot'].get('data_versions'):
                self._version_context(conn, job['operation'], job['input_snapshot']['input'],
                    job['input_snapshot']['data_versions'], job['input_snapshot']['data_version_mode'], lock=True)
            records = self._records(conn, execution_id)
            context = self._context(job, records)
            if digest(context) != job['validation_context_sha']:
                _fail('knowledge_validation_context_changed', 6)
            candidates = [record['body'] for record in records]
            selection = _selection(job)
            is_multi = job['profile']['schema_version'] == multi.PROFILE
            selection_pending = set()
            validator_complete = True
            manifest = job['input_snapshot'].get('source_review_manifest')
            raw_decisions = deepcopy(decisions)
            revision_target = job['input_snapshot'].get('revision_target')
            revision_review, revision_result = None, None
            revalidation_result = None
            if revision_target is not None:
                raw_decisions, revision_review = revision_runtime.split_validation(raw_decisions, revision_target, candidates)
            if manifest is not None:
                raw_decisions.pop('source_review_decisions', None)
            checked_source_review = None
            checked_d2k = None
            if job['operation'] == 'd2k':
                checked_d2k = d2k.validate_decisions(decisions,candidates,
                    [n['knode_revision_id'] for n in job['input_snapshot']['existing_nodes']],job['input_snapshot']['input'])
                validated, validator_complete = checked_d2k['decisions'], checked_d2k['complete']
                selection_pending = {r['view_id'] for r in job['generator_receipt']['view_reviews'] if r['disposition']=='needs_review'}
                selection_pending.update(r['view_id'] for r in checked_d2k['reviews'] if r['verdict']=='needs_review')
                for key, decision in validated.items():
                    body = next(r['body'] for r in records if r['body']['candidate_key']==key)
                    parent = decision['equivalent_candidate_key']
                    affected = any(e['view_id'] in selection_pending for e in body['direct_evidence'])
                    if decision['verdict'] in ('accepted','reused') and (affected or (parent and validated[parent]['verdict']=='needs_human')):
                        validated[key] = {**decision,'verdict':'needs_human','equivalent_candidate_key':None,'equivalent_revision_id':None,
                            'reason_codes':['d2k_source_review_required'],'reason':'The original source view or reuse target still requires review.'}
                for record in records:
                    conn.execute('INSERT INTO compiler_runtime.d2k_decisions(record_id,validation) VALUES (%s,%s)',
                        (record['record_id'],Jsonb(validated[record['body']['candidate_key']])))
                self._commit_nodes(conn,job,records,validated,checkpoint)
            elif job['operation'] == 'i2k':
                self._verify_input(conn, job['data_id'], job['input_snapshot']['input'])
                existing_ids = [node['knode_revision_id'] for node in job['input_snapshot']['existing_nodes']]
                if selection:
                    checked = (multi.validate_decisions(raw_decisions, candidates, existing_ids, job['input_snapshot']['input']) if is_multi else
                        validate_selection_decisions(raw_decisions, candidates, existing_ids,
                            check_selection_input(job['input_snapshot']['input'])))
                    validator_complete = checked['complete']
                    validated = checked['decisions']
                    selection_pending = {review['information_id'] for review in job['generator_receipt']['information_reviews']
                                         if review['disposition'] == 'needs_review'}
                    for review in checked['reviews']:
                        if review['verdict'] == 'needs_review':
                            selection_pending.add(review['information_id'])
                        conn.execute('''INSERT INTO compiler_runtime.k_information_review_decisions
                            (execution_id,information_id,verdict,reason_codes,reason) VALUES (%s,%s,%s,%s,%s)''',
                            (execution_id, review['information_id'], review['verdict'], Jsonb(review['reason_codes']), review['reason']))
                else:
                    validated = validate_node_decisions(decisions, candidates, existing_ids)
                    self._guard_legacy_reuse(conn, job, candidates, validated)
                if is_multi:
                    for candidate in candidates:
                        decision = validated[candidate['candidate_key']]
                        conn.execute('''INSERT INTO compiler_runtime.k_explicit_source_decisions
                            (record_id,identity_scope,source_data_id,source_explicit,no_novel_inference,source_identity_preserved)
                            VALUES (%s,%s,%s,%s,%s,%s)''',
                            (next(r['record_id'] for r in records if r['body']['candidate_key'] == candidate['candidate_key']),
                             candidate['identity_scope'], candidate['source_data_id'], decision['source_explicit'],
                             decision['no_novel_inference'], decision['source_identity_preserved']))
                unresolved_i = {identifier for source_request in job['generator_receipt']['source_requests']
                                for identifier in source_request['information_ids']}
                information_error_policy = job['profile'].get('information_error_policy') == information_errors.POLICY
                if information_error_policy:
                    unresolved_i.update(information_errors.affected_information_ids(
                        job['generator_receipt']['source_requests'],checked['reviews']))
                    selection_pending.update(unresolved_i)
                by_key = {candidate['candidate_key']: candidate for candidate in candidates}
                for key, decision in validated.items():
                    # An unfinished I review can report other missing claims;
                    # it does not invalidate an independently accepted candidate.
                    # Unavailable requested original evidence is a separate hold.
                    affected = any(citation['information_id'] in unresolved_i for citation in by_key[key]['evidence'])
                    target = decision['equivalent_candidate_key']
                    if (decision['verdict'] in ('accepted', 'reused') and
                            (affected or (target is not None and validated[target]['verdict'] == 'needs_human'))):
                        validated[key] = {**decision, 'verdict': 'needs_human',
                            'equivalent_candidate_key': None, 'equivalent_revision_id': None,
                            'reason_codes': [('d2i_information_error' if information_error_policy else 'original_pdf_unavailable')
                                             if affected else 'reuse_target_unresolved'],
                            'reason': ('Required Information has a reported D2I error. User review is required; '
                                       'direct D compilation and automatic D2I repair are forbidden.' if information_error_policy and affected
                                       else 'The required original evidence or reused candidate remains unresolved.')}
                if manifest is not None:
                    checked_source_review = source_review_contract.validate_decisions(
                        decisions, manifest, job['generator_receipt']['source_reviews'], validated)
                    selection_pending.update(checked_source_review['pending_target_ids'])
                if revision_target is not None:
                    revision_result = self._commit_revision_nodes(conn, job, records, validated, revision_review, checkpoint)
                else:
                    self._commit_nodes(conn, job, records, validated, checkpoint)
            elif job['operation'] == 'k2k':
                packet = job['input_snapshot']['input']
                if packet != self._inference_input(conn, job['data_id'], k2k.check_input(packet), allowed_data_ids=
                        job['input_snapshot'].get('propagation_scope', {}).get('scope', {}).get('allowed_data_ids'),
                        edge_revision_ids=k2k_effective_runtime.edge_ids(packet) if packet.get('schema_version') == k2k_effective.INPUT_SCHEMA else None):
                    _fail('knowledge_input_changed', 6)
                if job['input_snapshot'].get('revalidation_target') is not None:
                    frozen = job['input_snapshot']['revalidation_target']
                    if frozen != revalidation.freeze_node(self._nodes(conn), knowledge_provenance.load(conn),
                            frozen['target_revision_id'], packet):
                        _fail('revalidation_target_changed', 6)
                checked = k2k.validate_decisions(raw_decisions, candidates,
                    [node['knode_revision_id'] for node in job['input_snapshot']['existing_nodes']])
                if packet.get('schema_version') == k2k_effective.INPUT_SCHEMA:
                    checked = k2k_effective.validate_decisions(raw_decisions, candidates,
                        [node['knode_revision_id'] for node in job['input_snapshot']['existing_nodes']], packet)
                validator_complete, validated = checked['complete'], checked['decisions']
                if revision_target is not None:
                    revision_result = self._commit_revision_nodes(conn, job, records, validated, revision_review, checkpoint)
                else:
                    self._commit_nodes(conn, job, records, validated, checkpoint)
            else:
                current = {node['knode_revision_id'] for node in self._nodes(conn)}
                if any(node['knode_revision_id'] not in current for node in job['input_snapshot']['input']['nodes']):
                    _fail('knowledge_input_changed', 6)
                if n2e_runtime.modern(job['input_snapshot']):
                    validator_complete = decisions['complete']
                    n2e_runtime.commit(self, conn, job, records, decisions, checkpoint)
                elif job['input_snapshot'].get('revalidation_target') is not None:
                    revalidation_result = self._commit_edge_revalidation(conn, job, records, decisions, checkpoint)
                else:
                    validated = validate_edge_decisions(decisions, candidates)
                    self._commit_edges(conn, job, records, validated, checkpoint)
            current_records = self._records(conn, execution_id)
            unresolved = (not job['generator_receipt']['generation_complete']
                          or not validator_complete
                          or bool(job['generator_receipt']['source_requests'])
                          or bool(selection_pending)
                          or bool(revision_result and revision_result['requires_user_review'])
                          or bool(revalidation_result and revalidation_result['requires_user_review'])
                          or any(record['disposition'] in ('pending', 'needs_human') for record in current_records))
            state = 'needs_human' if unresolved else ('completed' if current_records else 'zero_output')
            stored_receipt = deepcopy(receipt)
            if job['input_snapshot']['input'].get('schema_version') == k2k_effective.INPUT_SCHEMA:
                stored_receipt['effective_validation_output'] = deepcopy(decisions)
            if revision_result is not None:
                stored_receipt['revision_result'] = revision_result
            if revalidation_result is not None:
                stored_receipt['revalidation_result'] = revalidation_result
            if checked_d2k is not None:
                stored_receipt['d2k_view_reviews'] = checked_d2k['reviews']
            if checked_source_review is not None:
                resolved = {str(record['record_id']): record for record in current_records}
                by_key = {record['body']['candidate_key']: resolved[str(record['record_id'])] for record in records}
                bindings = []
                for review in job['generator_receipt']['source_reviews']:
                    for item in review['items']:
                        links = []
                        for key in item['candidate_keys']:
                            record = by_key[key]
                            links.append({'candidate_key': key, 'record_id': str(record['record_id']),
                                'disposition': record['disposition'],
                                'knode_id': str(record['result_node_id']) if record['result_node_id'] else None,
                                'knode_revision_id': str(record['result_node_revision_id']) if record['result_node_revision_id'] else None})
                        bindings.append({'target_id': review['target_id'], 'item_key': item['item_key'], 'records': links})
                stored_receipt['source_review_result'] = {**checked_source_review, 'bindings': bindings}
            self._call(conn, job, 'validator', receipt)
            if checkpoint:
                checkpoint('before_knowledge_commit')
            conn.execute('''UPDATE compiler_runtime.operation_executions SET state=%s,validator_receipt=%s,
                updated_at=clock_timestamp() WHERE execution_id=%s''', (state, Jsonb(stored_receipt), execution_id))
            self._event(conn, job, state)
            if propagation_claim is not None:
                conn.execute('SET CONSTRAINTS ALL IMMEDIATE')
            _propagation_claim(conn, propagation_claim, execution_id)
        return self.show(execution_id)

    def show(self, execution_id):
        with connection(self.dsn) as conn:
            job = self._job(conn, execution_id)
            records = self._records(conn, execution_id)
            result = {**job, 'records': records,
                'model_calls': conn.execute('SELECT * FROM compiler_runtime.k_model_calls WHERE execution_id=%s ORDER BY call_id', (execution_id,)).fetchall(),
                'source_requests': conn.execute('SELECT * FROM compiler_runtime.k_source_requests WHERE execution_id=%s ORDER BY request_id', (execution_id,)).fetchall(),
                'events': conn.execute('SELECT * FROM compiler_runtime.execution_events WHERE execution_id=%s ORDER BY event_id', (execution_id,)).fetchall()}
            if _selection(job):
                result.update(information_reviews=conn.execute('SELECT * FROM compiler_runtime.k_information_reviews WHERE execution_id=%s ORDER BY information_id', (execution_id,)).fetchall(),
                    information_review_decisions=conn.execute('SELECT * FROM compiler_runtime.k_information_review_decisions WHERE execution_id=%s ORDER BY information_id', (execution_id,)).fetchall(),
                    information_review_records=conn.execute('SELECT * FROM compiler_runtime.k_information_review_records WHERE execution_id=%s ORDER BY information_id,record_id', (execution_id,)).fetchall())
            if 'source_review_manifest' in job['input_snapshot']:
                result['source_review'] = {'manifest': job['input_snapshot']['source_review_manifest'],
                    'generator_reviews': (job['generator_receipt'] or {}).get('source_reviews'),
                    'validation': (job['validator_receipt'] or {}).get('source_review_result')}
            if job['profile']['schema_version'] == multi.PROFILE:
                result.update(sources=conn.execute('SELECT * FROM compiler_runtime.k_execution_sources WHERE execution_id=%s ORDER BY ordinal', (execution_id,)).fetchall(),
                    explicit_source_decisions=conn.execute('''SELECT d.* FROM compiler_runtime.k_explicit_source_decisions d
                        JOIN compiler_runtime.k_compilation_records r USING(record_id) WHERE r.execution_id=%s ORDER BY r.ordinal''', (execution_id,)).fetchall())
            if job['operation'] == 'k2k':
                state = knowledge_provenance.load(conn)
                record_ids = {str(record['record_id']) for record in records}
                result['derivations'] = [row for key, row in state['by_record'].items() if key in record_ids]
                result['propagation_status'] = 'outbox_pending_not_converged'
            if n2e_runtime.modern(job['input_snapshot']):
                result['relation_decisions'] = conn.execute('''SELECT d.* FROM compiler_runtime.n2e_review_decisions d
                    JOIN compiler_runtime.k_compilation_records r USING(record_id)
                    WHERE d.execution_id=%s ORDER BY r.ordinal''', (execution_id,)).fetchall()
            if job['operation'] == 'd2k':
                result['data_groundings'] = conn.execute('''SELECT g.* FROM canonical_store.knowledge_data_groundings g
                    JOIN compiler_runtime.k_compilation_records r ON r.record_id=g.origin_record_id
                    WHERE r.execution_id=%s ORDER BY g.grounding_id''',(execution_id,)).fetchall()
                result['d2i_status_changed'] = False
            if job['input_snapshot'].get('revision_target') is not None:
                result['revision'] = {'target': deepcopy(job['input_snapshot']['revision_target']),
                    'result': (job['validator_receipt'] or {}).get('revision_result'),
                    'decisions': conn.execute('''SELECT d.* FROM compiler_runtime.k_revision_decisions d
                        JOIN compiler_runtime.k_compilation_records r USING(record_id)
                        WHERE r.execution_id=%s ORDER BY r.ordinal''', (execution_id,)).fetchall(),
                    'impacts': conn.execute('''SELECT i.* FROM compiler_runtime.k_revision_impacts i
                        JOIN compiler_runtime.k_compilation_records r USING(record_id)
                        WHERE r.execution_id=%s ORDER BY r.ordinal''', (execution_id,)).fetchall()}
            if job['input_snapshot'].get('data_versions'):
                result['data_versions'] = job['input_snapshot']['data_versions']
                result['data_version_mode'] = job['input_snapshot']['data_version_mode']
                heads = conn.execute('SELECT series_id,head_version_id FROM canonical_store.data_series '
                    'WHERE series_id=ANY(%s::uuid[]) ORDER BY series_id',
                    ([v['series_id'] for v in result['data_versions']],)).fetchall()
                result['current_data_version_heads'] = _json(heads)
            result = _json(result)
            if job['profile'].get('information_error_policy') == information_errors.POLICY:
                result['information_errors'] = information_errors.report(result)
            return result

    def graph(self, data_id=None, *, data_version_id=None):
        if data_id is not None:
            validate_data_id(data_id)
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            selected_version = immutable_versions(conn, [data_version_id])[0] if data_version_id else None
            if selected_version:
                if data_id is not None and data_id != selected_version['data_id']:
                    _fail('data_version_source_mismatch', 2)
                data_id = selected_version['data_id']
            nodes, edges = self._nodes(conn), self._edges(conn)
            version_state = version_provenance.load(conn)
            for node in nodes:
                node.update(version_provenance.graph_view(version_state, node))
            for edge in edges:
                edge.update(version_provenance.graph_view(version_state, edge))
            from .edge_projection import resolve as resolve_edges, derive_contested
            edges = resolve_edges(conn, nodes, edges)
            # Compute before source filtering so a restricted view cannot turn a
            # known conflict into an assertion of no conflict. No opponent text
            # or identity is placed in this node-level annotation.
            nodes = derive_contested(nodes, edges)
            origin_records = _json(conn.execute('''SELECT record_id,source_explicit,no_novel_inference,source_identity_preserved
                FROM compiler_runtime.k_explicit_source_decisions''').fetchall())
            source_origins = {r['record_id']:r for r in origin_records}
            for node in nodes:
                if node['origin_record_id'] in source_origins:
                    node['generation_origin'] = {'origin_operation':'i2k','is_inferred':False,
                        'claim_basis':'explicit_source_content','origin_record_id':node['origin_record_id'],
                        'validation':source_origins[node['origin_record_id']]}
            groundings = _json(conn.execute('''SELECT g.*,i.data_id FROM canonical_store.knowledge_node_groundings g
                JOIN canonical_store.information i USING(information_id) ORDER BY grounding_id''').fetchall())
            revisions = _json(conn.execute('SELECT * FROM canonical_store.knowledge_node_revisions ORDER BY knode_revision_id').fetchall())
            edge_revisions = _json(conn.execute('SELECT * FROM canonical_store.knowledge_edge_revisions ORDER BY kedge_revision_id').fetchall())
            provenance = knowledge_provenance.load(conn)
            derived = list(provenance['by_record'].values()) if provenance else []
            data_groundings = [g for values in (provenance or {}).get('data_groundings',{}).values() for g in values]
            if data_id is not None:
                grounded = {g['node_revision_id'] for g in groundings if g['data_id'] == data_id}
                grounded.update(g['node_revision_id'] for g in data_groundings if g['data_id']==data_id)
                if provenance:
                    grounded.update(ref for ref in provenance['by_result']
                        if data_id in knowledge_provenance.describe(provenance, ref)['source_data_ids'])
                node_ids = {r['knode_id'] for r in revisions if r['knode_revision_id'] in grounded}
                nodes = [node for node in nodes if node['knode_id'] in node_ids]
                revisions = [r for r in revisions if r['knode_id'] in node_ids]
                revision_ids = {r['knode_revision_id'] for r in revisions}
                groundings = [g for g in groundings if g['node_revision_id'] in revision_ids]
                data_groundings = [g for g in data_groundings if g['node_revision_id'] in revision_ids]
                edges = [edge for edge in edges if edge['from_knode_id'] in node_ids and edge['to_knode_id'] in node_ids]
                edge_ids = {edge['kedge_id'] for edge in edges}
                edge_revisions = [r for r in edge_revisions if r['kedge_id'] in edge_ids]
            else:
                edge_ids = {edge['kedge_id'] for edge in edges}
            applicability = _json(conn.execute('SELECT * FROM canonical_store.knowledge_edge_applicability_events ORDER BY event_order').fetchall())
            return {'schema_version': 'knowledge-graph-v1', 'data_id': data_id,
                    'selected_data_version': selected_version,
                    'state_version': conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton').fetchone()['version'],
                    'nodes': nodes, 'edges': edges, 'node_revisions': revisions,
                    'edge_revisions': edge_revisions, 'groundings': groundings,
                    **({'data_groundings':data_groundings} if data_groundings else {}),
                    'derivations': [row for row in derived
                                    if row['result_node_revision_id'] in {r['knode_revision_id'] for r in revisions}],
                    'applicability_events': [event for event in applicability if event['kedge_id'] in edge_ids],
                    'usable_edges': [edge for edge in edges if edge['usable']],
                    'propagation_status': 'outbox_pending_not_converged'}

    def fail_execution(self, execution_id, code):
        if not isinstance(code, str) or not code or len(code) > 128:
            _fail('invalid_error_code', 2)
        with connection(self.dsn) as conn, conn.transaction():
            job = self._job(conn, execution_id, True)
            if job['state'] in ('completed', 'zero_output'):
                _fail('knowledge_already_decided', 6)
            conn.execute('''UPDATE compiler_runtime.operation_executions SET state='failed',error_code=%s,
                updated_at=clock_timestamp() WHERE execution_id=%s''', (code, execution_id))
            self._event(conn, job, 'failed', code)
        return self.show(execution_id)

    def record_call_failure(self, execution_id, phase, receipt, code, *, response=None):
        """Retain a delivered but structurally invalid response before repair.

        The response hash and transport receipt survive; this is execution
        failure evidence, not an epistemic rejection or a staged candidate.
        """
        if phase not in ('generator', 'validator') or not isinstance(code, str) or not code:
            _fail('invalid_error_code', 2)
        with connection(self.dsn) as conn, conn.transaction():
            job = self._job(conn, execution_id, True)
            expected = job['input_digest'] if phase == 'generator' else job['validation_context_sha']
            if (job['state'] in ('completed', 'zero_output') or not isinstance(receipt, dict)
                    or receipt.get('input_sha256') != expected or receipt.get('actual_delivery') is not True
                    or not isinstance(receipt.get('profile'), dict)
                    or any(receipt['profile'].get(key) != value for key, value in job['profile']['model'].items())
                    or not (receipt.get('provider_ref') or receipt.get('thread_ref'))):
                _fail('knowledge_provider_receipt_mismatch')
            validate_data_id(receipt.get('output_sha256'))
            previous_call = conn.execute('''SELECT call_id,receipt FROM compiler_runtime.k_model_calls
                WHERE execution_id=%s AND phase=%s AND status='failed' AND input_sha256=%s
                  AND output_sha256=%s AND provider_ref=%s ORDER BY call_id LIMIT 1''',
                (execution_id,phase,expected,receipt['output_sha256'],
                 receipt.get('provider_ref') or receipt.get('thread_ref'))).fetchone()
            if previous_call:
                if previous_call['receipt'].get('structural_error_code') != code:
                    _fail('idempotency_conflict', 6)
                return {'call_id':str(previous_call['call_id']),'status':'failed','state':job['state'],'replayed':True}
            if job['state'] == 'failed' and phase != 'validator':
                _fail('invalid_knowledge_state', 6)
            details = []
            if response is not None:
                validation_context = (self._context(job, self._records(conn, execution_id))
                    if phase == 'validator' and (_selection(job) or job['operation'] in ('d2k','k2k'))
                    and job['generator_receipt'] is not None else None)
                self._receipt(receipt, job, phase, response, validation_context=validation_context)
                if phase == 'generator' and job['operation'] == 'i2k':
                    units = {item['information_id']:item for item in job['input_snapshot']['input']['model_input']['information']}
                    for candidate in response.get('nodes', []):
                        for citation in candidate.get('evidence', []):
                            quote = citation.get('quote')
                            unit = units.get(citation.get('information_id'))
                            if unit and isinstance(quote,str) and quote and unit['content'].count(quote) != 1:
                                issue = {'code':'quote_not_unique_in_information',
                                    'candidate_key':candidate.get('candidate_key'),
                                    'information_id':unit['information_id'],'proposed_quote':quote}
                                prefix = next((quote[:width] for width in (32,24,16)
                                               if len(quote)>=width and unit['content'].count(quote[:width])==1), None)
                                start = unit['content'].find(prefix) if prefix else -1
                                if start >= 0:
                                    end = min(len(unit['content']),start+len(quote)+100)
                                    issue.update(source_excerpt=unit['content'][start:end],source_char_range=[start,end])
                                details.append(issue)
                    for review in response.get('reviews', []):
                        if review.get('disposition') == 'selected' and not review.get('candidate_keys'):
                            details.append({'code':'selected_review_has_no_candidate',
                                'information_id':review.get('information_id')})
            row = conn.execute('''INSERT INTO compiler_runtime.k_model_calls
                (execution_id,phase,profile_id,input_sha256,output_sha256,provider_ref,receipt,usage,status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'failed') RETURNING call_id''',
                (execution_id, phase, job[phase + '_profile_id'], expected, receipt['output_sha256'],
                 receipt.get('provider_ref') or receipt.get('thread_ref'),
                 Jsonb({**receipt, 'structural_error_code': code, 'structural_feedback':details}), Jsonb(receipt.get('usage', {})))).fetchone()
            return {'call_id': str(row['call_id']), 'status': 'failed', 'state': job['state']}

    def record_dispatch_failure(self, execution_id, phase, failure):
        """Record an unsuccessful dispatch without fabricating output/delivery.

        This is failure telemetry only. It cannot accept a candidate, resolve a
        source request, or stand in for an actual Generator/Validator receipt.
        """
        if (phase not in ('generator','validator') or not isinstance(failure,dict)
                or failure.get('actual_delivery') is not None or failure.get('output_sha256') is not None
                or failure.get('error_code') not in ('codex_execution_failed','codex_timeout','codex_unavailable',
                    'codex_output_invalid','codex_unexpected_tool','codex_workspace_failed')):
            _fail('invalid_knowledge_dispatch_failure')
        for key in ('input_sha256','prompt_sha256','schema_sha256','request_file_sha256'):
            validate_data_id(failure.get(key))
        fingerprint = digest(failure)
        with connection(self.dsn) as conn,conn.transaction():
            job = self._job(conn,execution_id,True)
            previous = conn.execute('''SELECT call_id FROM compiler_runtime.k_model_calls
                WHERE execution_id=%s AND phase=%s AND receipt->>'dispatch_failure_sha256'=%s''',
                (execution_id,phase,fingerprint)).fetchone()
            if previous:
                return {'call_id':str(previous['call_id']),'status':'failed','replayed':True}
            expected = job['input_digest'] if phase=='generator' else job['validation_context_sha']
            if failure['input_sha256']!=expected or job['state']!=('prepared' if phase=='generator' else 'proposed'):
                _fail('invalid_knowledge_state',6)
            stored = {**deepcopy(failure),'dispatch_failure_sha256':fingerprint,
                      'structural_error_code':failure['error_code'],'structural_feedback':[]}
            row = conn.execute('''INSERT INTO compiler_runtime.k_model_calls
                (execution_id,phase,profile_id,input_sha256,output_sha256,provider_ref,receipt,usage,status)
                VALUES (%s,%s,%s,%s,NULL,NULL,%s,'{}'::jsonb,'failed') RETURNING call_id''',
                (execution_id,phase,job[phase+'_profile_id'],expected,Jsonb(stored))).fetchone()
            return {'call_id':str(row['call_id']),'status':'failed','replayed':False,'state':job['state']}
