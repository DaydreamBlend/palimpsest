"""Durable K2W over explicit accepted K, without source or provider operations.

W has no representative Data. Its small pending-job table shares profile storage
and the existing K commit lock, without coercing W into source-owned K jobs.
"""
from copy import deepcopy
from hashlib import sha256
from importlib.resources import files
import json

from psycopg.types.json import Jsonb

from . import edge_projection, k2w, k2w_prompts
from .canonical_store import connection
from .data import request_id
from .errors import PalimpsestError
from .i2k import digest
from .knowledge_runtime import KnowledgeRuntime, MODEL
from .codex_provider import PROFILE as CODEX_PROFILE


def _fail(code):
    raise PalimpsestError(code, 'K2W의 입력·독립 검증·현재 K Revision을 확인하세요.', 6)


def _plain(value):
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False, default=str))


def _json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _implementation():
    return {name: sha256(files('palimpsest').joinpath(name).read_bytes()).hexdigest()
            for name in ('k2w.py', 'k2w_prompts.py', 'wisdom.py', 'wisdom_runtime.py')}


class WisdomRuntime:
    def __init__(self, dsn):
        self.dsn = dsn

    @staticmethod
    def _job(conn, execution_id, *, lock=False):
        row = conn.execute('''SELECT j.*,p.payload AS profile FROM compiler_runtime.w_jobs j
            JOIN compiler_runtime.profiles p USING(profile_id) WHERE execution_id=%s'''
            + (' FOR UPDATE OF j' if lock else ''), (request_id(execution_id),)).fetchone()
        if row is None:
            _fail('wisdom_job_not_found')
        return _plain(row)

    @staticmethod
    def _event(conn, execution_id, state, detail=None):
        conn.execute('INSERT INTO compiler_runtime.w_events(execution_id,state,detail) VALUES (%s,%s,%s)',
                     (execution_id, state, Jsonb(detail or {})))

    @staticmethod
    def _fresh(conn, job):
        if job['profile']['implementation_sha256'] != _implementation():
            _fail('wisdom_implementation_changed')
        version = conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton FOR UPDATE').fetchone()['version']
        if version != job['expected_state_version']:
            _fail('wisdom_knowledge_state_changed')
        if not conn.execute('SELECT compiler_runtime.w_inputs_current(%s) AS ok', (job['execution_id'],)).fetchone()['ok']:
            _fail('wisdom_premises_changed')

    @staticmethod
    def _resolve(conn, revision_ids, edge_revision_ids):
        refs = [request_id(value) for value in revision_ids]
        edge_refs = [request_id(value) for value in edge_revision_ids]
        if len(set(refs)) != len(refs) or len(set(edge_refs)) != len(edge_refs):
            _fail('wisdom_duplicate_input')
        nodes = KnowledgeRuntime._nodes(conn)
        edges = KnowledgeRuntime._edges(conn)
        conflicts = edge_projection.resolve(conn, nodes, [edge for edge in edges if edge['predicate'] == 'contradicts'])
        nodes = edge_projection.derive_contested(nodes, conflicts)
        by_revision = {node['knode_revision_id']: node for node in nodes}
        indexed_edges = {edge['kedge_revision_id']: edge for edge in edges}
        if any(ref not in indexed_edges for ref in edge_refs):
            _fail('wisdom_edge_changed')
        selected_edges = edge_projection.resolve(conn, nodes, [indexed_edges[ref] for ref in edge_refs])
        inputs = []
        for edge in selected_edges:
            if not edge['usable']:
                _fail('wisdom_edge_unavailable')
            pair = [edge['effective_from_revision_id'], edge['effective_to_revision_id']]
            for ref in pair:
                if ref not in refs:
                    refs.append(ref)
            inputs.append({key: deepcopy(edge[key]) for key in ('kedge_id', 'predicate', 'qualifiers')})
            inputs[-1].update(original_from_revision_id=edge['from_knode_revision_id'],
                original_to_revision_id=edge['to_knode_revision_id'], effective_edge_ref=deepcopy(edge['effective_edge_ref']),
                endpoint_support_signatures=[by_revision[ref]['current_support_signature'] for ref in pair])
        selected = []
        for ref in refs:
            if ref not in by_revision or not conn.execute('SELECT compiler_runtime.current_k2k_premise(%s) AS ok', (ref,)).fetchone()['ok']:
                _fail('wisdom_premise_unavailable')
            selected.append(by_revision[ref])
        return selected, inputs

    def prepare(self, identifier, *, query, context_snapshot, revision_ids, edge_revision_ids=(),
                wisdom_kind='explanation', model_profile=None, retrieval_snapshot=None):
        identifier = request_id(identifier)
        if not isinstance(revision_ids, (list, tuple)) or not isinstance(edge_revision_ids, (list, tuple)):
            _fail('invalid_wisdom_input')
        model = deepcopy(MODEL if model_profile is None else model_profile)
        if not isinstance(model, dict) or model not in (MODEL, CODEX_PROFILE):
            _fail('invalid_wisdom_model_profile')
        requested = {'query': query, 'context_snapshot': context_snapshot, 'revision_ids': list(revision_ids),
            'edge_revision_ids': list(edge_revision_ids), 'wisdom_kind': wisdom_kind, 'model': model,
            'retrieval_snapshot': retrieval_snapshot}
        fingerprint = digest(requested)
        with connection(self.dsn) as conn, conn.transaction():
            # Same-request serialization preserves successful replay before freshness checks.
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('k2w:' + identifier,))
            old = conn.execute('SELECT execution_id,request_fingerprint FROM compiler_runtime.w_jobs WHERE request_id=%s', (identifier,)).fetchone()
            if old:
                if old['request_fingerprint'] != fingerprint:
                    _fail('idempotency_conflict')
                return {**self._job(conn, old['execution_id']), 'replayed': True}
            state = conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton FOR UPDATE').fetchone()['version']
            nodes, edges = self._resolve(conn, requested['revision_ids'], requested['edge_revision_ids'])
            packet = k2w.build_input(nodes, edges, query=query, context_snapshot=context_snapshot,
                wisdom_kind=wisdom_kind, knowledge_state_version=state, retrieval_snapshot=retrieval_snapshot)
            profile = {'schema_version': k2w.PROFILE, 'model': model, 'implementation_sha256': _implementation()}
            profile_id = KnowledgeRuntime._profile(conn, profile)
            prompt, schema = k2w_prompts.generation_request(packet)
            request = self._request(packet, prompt, schema, packet['input_sha256'])
            row = conn.execute('''INSERT INTO compiler_runtime.w_jobs
                (request_id,request_fingerprint,profile_id,input_snapshot,input_json,expected_state_version,generator_request)
                VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING execution_id''',
                (identifier, fingerprint, profile_id, Jsonb(packet),
                 _json_text({key: value for key, value in packet.items() if key != 'input_sha256'}), state, Jsonb(request))).fetchone()
            execution = str(row['execution_id'])
            for ordinal, node in enumerate(packet['nodes']):
                conn.execute('''INSERT INTO compiler_runtime.w_inputs
                    (execution_id,ordinal,knode_revision_id,support_signature,payload) VALUES (%s,%s,%s,%s,%s)''',
                    (execution, ordinal, node['knode_revision_id'], nodes[ordinal]['current_support_signature'], Jsonb(node)))
            for ordinal, edge in enumerate(packet['effective_edges']):
                ref = edge['effective_edge_ref']
                event = ref['applicability_basis_ref'] if ref['applicability_basis_type'] == 'applicability_event' else None
                origin = (str(conn.execute('SELECT origin_record_id FROM canonical_store.knowledge_edge_applicability_events WHERE applicability_event_id=%s',
                    (event,)).fetchone()['origin_record_id']) if event else ref['applicability_basis_ref'])
                conn.execute('''INSERT INTO compiler_runtime.w_edge_inputs
                    (execution_id,ordinal,kedge_id,semantic_kedge_revision_id,from_knode_revision_id,to_knode_revision_id,
                     basis_type,basis_origin_record_id,applicability_event_id,relation_read_state_token,
                     from_support_signature,to_support_signature,payload)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (execution, ordinal, edge['kedge_id'], ref['semantic_kedge_revision_id'], ref['from_knode_revision_id'],
                     ref['to_knode_revision_id'], ref['applicability_basis_type'], origin, event,
                     ref['relation_read_state_token'], *edge['endpoint_support_signatures'], Jsonb(edge)))
            self._event(conn, execution, 'prepared')
            return {**self._job(conn, execution), 'replayed': False}

    @staticmethod
    def _request(packet, prompt, schema, input_sha):
        return {'prompt': prompt, 'schema': schema, 'schema_json': _json_text(schema), 'schema_sha256': digest(schema), 'images': [], 'input_sha256': input_sha,
            'delivered_knowledge_revision_ids': [node['knode_revision_id'] for node in packet['nodes']],
            'delivered_effective_edge_refs': [deepcopy(edge['effective_edge_ref']) for edge in packet['effective_edges']]}

    @staticmethod
    def _receipt(job, phase, response, receipt):
        request = job[phase + '_request']
        provider_ref = (receipt.get('provider_ref') or receipt.get('thread_ref')) if isinstance(receipt, dict) else None
        if (not isinstance(receipt, dict) or not isinstance(receipt.get('profile'), dict)
                or any(receipt['profile'].get(key) != value for key, value in job['profile']['model'].items())
                or receipt.get('actual_delivery') is not True
                or not isinstance(provider_ref, str) or not provider_ref.strip() or '\x00' in provider_ref
                or receipt.get('input_sha256') != request['input_sha256']
                or receipt.get('output_sha256') != digest(response)
                or receipt.get('prompt_sha256') != sha256(request['prompt'].encode()).hexdigest()
                or receipt.get('schema_sha256') != digest(request['schema'])
                or receipt.get('image_attachments', []) != []
                or any(receipt.get(key) != request[key] for key in ('delivered_knowledge_revision_ids', 'delivered_effective_edge_refs'))):
            _fail('wisdom_provider_receipt_mismatch')
        if phase == 'validator':
            previous = job['generator_receipt']
            if (receipt.get('provider_ref') or receipt.get('thread_ref')) == (previous.get('provider_ref') or previous.get('thread_ref')):
                _fail('wisdom_validator_not_independent')

    @staticmethod
    def _call(conn, job, phase, response, receipt):
        conn.execute('''INSERT INTO compiler_runtime.w_calls(execution_id,phase,response,response_json,receipt)
            VALUES (%s,%s,%s,%s,%s)''', (job['execution_id'], phase, Jsonb(response), _json_text(response), Jsonb(receipt)))

    def stage(self, execution_id, response, receipt):
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton FOR UPDATE')
            job = self._job(conn, execution_id, lock=True)
            self._receipt(job, 'generator', response, receipt)
            if job['state'] != 'prepared':
                if job['generator_response'] == response and job['generator_receipt'] == receipt:
                    return {**job, 'replayed': True}
                _fail('invalid_wisdom_state')
            self._fresh(conn, job)
            answer = k2w.normalize_answer(response, job['input_snapshot'])
            prompt, schema = k2w_prompts.validation_request(job['input_snapshot'], answer)
            context_sha = digest({'input': job['input_snapshot'], 'answer': answer})
            request = self._request(job['input_snapshot'], prompt, schema, context_sha)
            request['validation_context_json'] = _json_text({'input': job['input_snapshot'], 'answer': answer})
            self._call(conn, job, 'generator', response, receipt)
            conn.execute('''UPDATE compiler_runtime.w_jobs SET state='proposed',generator_response=%s,
                generator_receipt=%s,answer=%s,validator_request=%s WHERE execution_id=%s''',
                (Jsonb(response), Jsonb(receipt), Jsonb(answer), Jsonb(request), job['execution_id']))
            self._event(conn, execution_id, 'proposed')
            return self._job(conn, execution_id)

    def validate(self, execution_id, response, receipt):
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton FOR UPDATE')
            job = self._job(conn, execution_id, lock=True)
            if job['validator_request'] is None:
                _fail('invalid_wisdom_state')
            self._receipt(job, 'validator', response, receipt)
            if job['state'] != 'proposed':
                if job['validator_response'] == response and job['validator_receipt'] == receipt:
                    return {**job, 'replayed': True}
                _fail('invalid_wisdom_state')
            self._fresh(conn, job)
            verdict = k2w.validate_answer(response, job['answer'])
            state = 'validated' if verdict['verdict'] == 'accepted' else 'needs_human'
            self._call(conn, job, 'validator', response, receipt)
            conn.execute('''UPDATE compiler_runtime.w_jobs SET state=%s,validator_response=%s,
                validator_receipt=%s,validation=%s WHERE execution_id=%s''',
                (state, Jsonb(response), Jsonb(receipt), Jsonb(verdict), job['execution_id']))
            self._event(conn, execution_id, state)
            return self._job(conn, execution_id)

    def commit(self, execution_id):
        from .wisdom import build_snapshot
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton FOR UPDATE')
            job = self._job(conn, execution_id, lock=True)
            if job['state'] == 'completed':
                return {**self._wisdom(conn, job['wisdom_id']), 'replayed': True}
            if job['state'] != 'validated':
                _fail('wisdom_not_validated')
            self._fresh(conn, job)
            allocated = conn.execute('SELECT uuidv7() AS id,CURRENT_TIMESTAMP AS created_at').fetchone()
            snapshot = build_snapshot(wisdom_id=str(allocated['id']), execution_id=job['execution_id'],
                created_at=allocated['created_at'].isoformat(), packet=job['input_snapshot'], answer=job['answer'],
                validation=job['validation'], generation_profile=job['profile'])
            conn.execute('''INSERT INTO canonical_store.wisdoms(wisdom_id,execution_id,wisdom_kind,snapshot,snapshot_json,snapshot_sha256,created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s)''', (snapshot['wisdom_id'], job['execution_id'], snapshot['wisdom_kind'],
                Jsonb(snapshot), _json_text({key: value for key, value in snapshot.items() if key != 'snapshot_sha256'}),
                snapshot['snapshot_sha256'], allocated['created_at']))
            conn.execute("UPDATE compiler_runtime.w_jobs SET state='completed',wisdom_id=%s WHERE execution_id=%s",
                         (snapshot['wisdom_id'], job['execution_id']))
            self._event(conn, execution_id, 'completed', {'wisdom_id': snapshot['wisdom_id']})
            return {**self._wisdom(conn, snapshot['wisdom_id']), 'replayed': False}

    @staticmethod
    def _wisdom(conn, wisdom_id):
        result = conn.execute('SELECT snapshot,snapshot_sha256 FROM canonical_store.wisdoms WHERE wisdom_id=%s',
                              (request_id(wisdom_id),)).fetchone()
        if result is None:
            _fail('wisdom_not_found')
        if (digest({key: value for key, value in result['snapshot'].items() if key != 'snapshot_sha256'}) != result['snapshot_sha256']
                or result['snapshot'].get('snapshot_sha256') != result['snapshot_sha256']):
            _fail('wisdom_snapshot_changed')
        return result['snapshot']

    def wisdom(self, wisdom_id):
        with connection(self.dsn) as conn:
            return self._wisdom(conn, wisdom_id)

    def show(self, execution_id):
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            job = self._job(conn, execution_id)
            job['events'] = _plain(conn.execute('SELECT * FROM compiler_runtime.w_events WHERE execution_id=%s ORDER BY created_at,event_id',
                                               (job['execution_id'],)).fetchall())
            return job

    def prepare_call(self, execution_id, phase, directory):
        from .wiki_projection_store import ProjectionStore
        if phase not in ('generator', 'validator'):
            _fail('invalid_wisdom_phase')
        with connection(self.dsn) as conn, conn.transaction():
            job = self._job(conn, execution_id)
            if job['state'] != ('prepared' if phase == 'generator' else 'proposed'):
                _fail('invalid_wisdom_state')
            self._fresh(conn, job)
        request = {**job[phase + '_request'], 'output_file': phase + '-response.json'}
        binding = {'execution_id': job['execution_id'], 'phase': phase, 'profile': job['profile'], 'request_sha256': digest(request)}
        store = ProjectionStore(directory)
        with store.locked():
            prior = store.read_json(phase + '-binding.json')
            if prior is not None and prior != binding:
                _fail('wisdom_call_directory_conflict')
            store.write_json(phase + '-request.json', request)
            store.write_json(phase + '-binding.json', binding)
        return {**binding, 'request_file': str(store.root / (phase + '-request.json')),
                'actual_delivery': False, 'replayed': prior is not None}
