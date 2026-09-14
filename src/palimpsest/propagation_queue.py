"""Durable, token-fenced propagation work; model calls live outside this module.

The immutable outbox records effects. Task causes record delivery into a frozen
workflow, including causal descendants committed after its initial watermark.
"""

from contextlib import contextmanager
import json

from psycopg.errors import RaiseException
from psycopg.types.json import Jsonb

from .canonical_store import connection
from .data import data_id, request_id
from .errors import PalimpsestError
from .i2k import digest


PROFILE = 'propagation-worker-v1'
KINDS = ('outbox', 'support_refresh', 'node_revalidate', 'edge_revalidate', 'n2e', 'k2k', 'wiki_refresh')
STATES = ('pending', 'leased', 'awaiting_model', 'retry', 'blocked', 'done')
TRANSPORT_FAILURE_LIMIT = 3


def _fail(code, exit_code=6):
    raise PalimpsestError(code, '전파 작업의 승인 범위·상태·lease와 남은 처리 의무를 확인하세요.', exit_code)


def _json(value):
    return json.loads(json.dumps(value, default=str, ensure_ascii=False, allow_nan=False))


def _uuid(conn):
    return str(conn.execute('SELECT uuidv7() AS id').fetchone()['id'])


def _text(value, code):
    if not isinstance(value, str) or not value.strip():
        _fail(code, 2)
    return value


def _seconds(value):
    if type(value) is not int or value <= 0:
        _fail('invalid_propagation_delay', 2)
    return value


def _counts(tasks):
    return {'total': len(tasks), **{state: sum(task['state'] == state for task in tasks) for state in STATES}}


def _transport_streak(events, phase):
    """Count the next failure from the newest-first journal, never semantic work."""
    streak = 1
    for event in events:
        if event['event_type'] in ('retry_requested', 'transport_succeeded'):
            break
        if event['event_type'] == 'retry':
            if event['payload'].get('details', {}).get('phase') != phase:
                break
            streak += 1
    return streak


class PropagationQueue:
    def __init__(self, dsn):
        self.dsn = dsn

    @staticmethod
    def _fence(conn):
        # ponytail: shared canonical fence; narrower fences only when measured contention warrants them.
        return conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton FOR UPDATE').fetchone()['version']

    @staticmethod
    def _run(conn, identifier, *, lock=False):
        row = conn.execute('SELECT * FROM compiler_runtime.propagation_runs WHERE run_id=%s' +
            (' FOR UPDATE' if lock else ''), (request_id(identifier),)).fetchone()
        if row is None:
            _fail('propagation_run_not_found', 2)
        return _json(row)

    @staticmethod
    def _event(conn, run_id, event_type, payload, task_id=None):
        conn.execute('''INSERT INTO compiler_runtime.propagation_events(event_id,run_id,task_id,event_type,payload)
            VALUES (%s,%s,%s,%s,%s)''', (_uuid(conn), run_id, task_id, event_type, Jsonb(_json(payload))))

    @staticmethod
    def _assert(conn, task_id, token):
        try:
            conn.execute('SELECT compiler_runtime.assert_propagation_claim(%s,%s)',
                         (request_id(task_id), request_id(token)))
        except RaiseException:
            _fail('propagation_claim_lost')
        return _json(conn.execute('SELECT * FROM compiler_runtime.propagation_tasks WHERE task_id=%s',
                                 (task_id,)).fetchone())

    def prepare(self, identifier, scope, policy):
        identifier = request_id(identifier)
        if not isinstance(scope, dict) or not isinstance(policy, dict):
            _fail('invalid_propagation_scope', 2)
        scope, policy = _json(scope), _json(policy)
        for name in ('root_record_ids', 'allowed_data_ids', 'wiki_ids'):
            values = scope.get(name)
            if not isinstance(values, list):
                _fail('invalid_propagation_scope', 2)
            for value in values:
                (data_id if name == 'allowed_data_ids' else request_id)(value)
            if len(values) != len(set(values)):
                _fail('invalid_propagation_scope', 2)
        if not scope['root_record_ids'] or not scope['allowed_data_ids']:
            _fail('invalid_propagation_scope', 2)
        fingerprint = digest({'schema_version': PROFILE, 'scope': scope, 'policy': policy})
        with connection(self.dsn) as conn, conn.transaction():
            watermark = self._fence(conn)
            existing = conn.execute('SELECT * FROM compiler_runtime.propagation_runs WHERE run_id=%s', (identifier,)).fetchone()
            if existing is not None:
                if existing['request_fingerprint'] != fingerprint:
                    _fail('propagation_request_conflict')
                return _json(existing)
            conn.execute('''INSERT INTO compiler_runtime.propagation_runs
                (run_id,request_fingerprint,scope,policy,initial_watermark) VALUES (%s,%s,%s,%s,%s)''',
                (identifier, fingerprint, Jsonb(scope), Jsonb(policy), watermark))
            self._event(conn, identifier, 'prepared', {'request_fingerprint': fingerprint, 'initial_watermark': watermark})
            return self._run(conn, identifier)

    def start(self, run_id, confirmed_fingerprint, actor_ref):
        actor_ref = _text(actor_ref, 'propagation_actor_required')
        with connection(self.dsn) as conn, conn.transaction():
            self._fence(conn)
            run = self._run(conn, run_id, lock=True)
            if confirmed_fingerprint != run['request_fingerprint']:
                _fail('propagation_confirmation_changed')
            if run['state'] == 'running':
                prior = conn.execute('''SELECT payload FROM compiler_runtime.propagation_events
                    WHERE run_id=%s AND event_type='started' ORDER BY created_at,event_id LIMIT 1''', (run_id,)).fetchone()
                if prior is None or prior['payload'].get('actor_ref') != actor_ref:
                    _fail('propagation_confirmation_changed')
                return run
            if run['state'] != 'prepared':
                _fail('propagation_run_not_prepared')
            conn.execute("UPDATE compiler_runtime.propagation_runs SET state='running',lease_epoch=lease_epoch+1,updated_at=clock_timestamp() WHERE run_id=%s", (run_id,))
            self._event(conn, run_id, 'started', {'request_fingerprint': confirmed_fingerprint,
                'actor_ref': actor_ref, 'confirmation_method': 'explicit_local_manifest'})
            run = self._run(conn, run_id)
            self.harvest(conn, run)
            return self._run(conn, run_id)

    def show(self, run_id):
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            run = self._run(conn, run_id)
            tasks = _json(conn.execute('SELECT * FROM compiler_runtime.propagation_tasks WHERE run_id=%s ORDER BY created_at,task_id',
                                      (run_id,)).fetchall())
            run.update(tasks=tasks, counts=_counts(tasks))
            run['anomalies'] = _json(conn.execute('''SELECT event_id,event_type,task_id,payload,created_at
                FROM compiler_runtime.propagation_events WHERE run_id=%s
                AND event_type IN ('semantic_anomaly','semantic_anomaly_acknowledged','semantic_return_observed','transport_anomaly')
                ORDER BY created_at,event_id''', (run_id,)).fetchall())
            return run

    @contextmanager
    def transaction(self, task_id, token):
        with connection(self.dsn) as conn, conn.transaction():
            self._fence(conn)
            task = self._assert(conn, task_id, token)
            yield conn, task, self._run(conn, task['run_id'])

    def claim(self, run_id, lease_seconds=180):
        lease_seconds = _seconds(lease_seconds)
        with connection(self.dsn) as conn, conn.transaction():
            self._fence(conn)
            run = self._run(conn, run_id, lock=True)
            if run['state'] != 'running':
                return None
            self.harvest(conn, run)
            if conn.execute('''SELECT 1 FROM compiler_runtime.propagation_tasks WHERE run_id=%s
                AND state='leased' AND lease_expires>clock_timestamp() AND lease_epoch=%s LIMIT 1''', (run_id, run['lease_epoch'])).fetchone():
                return None
            previous = conn.execute('''SELECT * FROM compiler_runtime.propagation_tasks WHERE run_id=%s AND (
                state IN ('pending','awaiting_model') OR (state='retry' AND retry_after<=clock_timestamp())
                OR (state='leased' AND (lease_expires<=clock_timestamp() OR lease_epoch<>%s)))
                ORDER BY CASE kind WHEN 'outbox' THEN 0 WHEN 'support_refresh' THEN 0 WHEN 'node_revalidate' THEN 1 WHEN 'edge_revalidate' THEN 1
                    WHEN 'n2e' THEN 2 WHEN 'k2k' THEN 2 ELSE 3 END,created_at,task_id LIMIT 1 FOR UPDATE SKIP LOCKED''', (run_id, run['lease_epoch'])).fetchone()
            if previous is None:
                return None
            token = _uuid(conn)
            row = conn.execute('''UPDATE compiler_runtime.propagation_tasks SET state='leased',attempt=attempt+1,
                lease_token=%s,lease_epoch=%s,lease_expires=clock_timestamp()+(%s*interval '1 second'),retry_after=NULL,
                error_code=NULL,updated_at=clock_timestamp() WHERE task_id=%s RETURNING *''',
                (token, run['lease_epoch'], lease_seconds, previous['task_id'])).fetchone()
            task = _json(row)
            self._event(conn, run_id, 'claimed', {'attempt': task['attempt'], 'lease_token': token,
                'lease_epoch': task['lease_epoch'], 'lease_expires': task['lease_expires'], 'request_id': task['request_id'],
                'previous_state': previous['state'], 'previous_lease_token': previous['lease_token']}, task['task_id'])
            return task

    def renew(self, task_id, token, lease_seconds=180):
        lease_seconds = _seconds(lease_seconds)
        with self.transaction(task_id, token) as (conn, task, run):
            row = conn.execute('''UPDATE compiler_runtime.propagation_tasks
                SET lease_expires=clock_timestamp()+(%s*interval '1 second'),updated_at=clock_timestamp()
                WHERE task_id=%s RETURNING *''', (lease_seconds, task_id)).fetchone()
            self._event(conn, run['run_id'], 'renewed', {'lease_token': token, 'lease_expires': row['lease_expires'],
                'attempt': row['attempt'], 'request_id': row['request_id']}, task_id)
            return _json(row)

    def control(self, run_id, action, actor_ref, reason):
        actor_ref, reason = _text(actor_ref, 'propagation_actor_required'), _text(reason, 'propagation_reason_required')
        if action not in ('pause', 'resume', 'cancel'):
            _fail('invalid_propagation_control', 2)
        with connection(self.dsn) as conn, conn.transaction():
            # Pause/cancel need only this row, so in-flight provider processes hold no blocking DB lock.
            run = self._run(conn, run_id, lock=True)
            if run['state'] in ('completed', 'cancelled'):
                _fail('propagation_run_terminal')
            if action == 'resume' and run['state'] not in ('paused', 'needs_human'):
                _fail('propagation_run_not_paused')
            if action == 'resume' and conn.execute('''SELECT 1 FROM compiler_runtime.propagation_tasks
                    WHERE run_id=%s AND state='blocked' AND error_code='propagation_semantic_oscillation' LIMIT 1''',
                    (run_id,)).fetchone():
                _fail('propagation_anomaly_acknowledgement_required')
            if action == 'pause' and run['state'] not in ('running', 'needs_human', 'paused'):
                _fail('propagation_run_not_started')
            state = {'pause': 'paused', 'resume': 'running', 'cancel': 'cancelled'}[action]
            if state != run['state']:
                conn.execute('UPDATE compiler_runtime.propagation_runs SET state=%s,lease_epoch=lease_epoch+1,updated_at=clock_timestamp() WHERE run_id=%s', (state, run_id))
                self._event(conn, run_id, action, {'actor_ref': actor_ref, 'reason': reason, 'previous_state': run['state']})
            return self._run(conn, run_id)

    def enqueue(self, conn, run_id, kind, payload, *, cause_record_id=None, outbox_id=None, parent_task_id=None):
        if kind not in KINDS or not isinstance(payload, dict):
            _fail('invalid_propagation_task', 2)
        run, payload = self._run(conn, run_id), _json(payload)
        if run['state'] in ('completed', 'cancelled'):
            _fail('propagation_run_terminal')
        key = digest({'kind': kind, 'payload': payload})
        row = conn.execute('SELECT * FROM compiler_runtime.propagation_tasks WHERE run_id=%s AND task_key=%s', (run_id, key)).fetchone()
        if row is None:
            row = conn.execute('''INSERT INTO compiler_runtime.propagation_tasks(task_id,run_id,task_key,kind,payload,request_id)
                VALUES (%s,%s,%s,%s,%s,%s) RETURNING *''', (_uuid(conn), run_id, key, kind, Jsonb(payload), _uuid(conn))).fetchone()
            self._event(conn, run_id, 'enqueued', {'kind': kind, 'task_key': key}, str(row['task_id']))
        task = _json(row)
        roots = [cause_record_id] if any(value is not None for value in (cause_record_id, outbox_id, parent_task_id)) else run['scope']['root_record_ids']
        for root in roots:
            cause = {name: request_id(value) if value is not None else None for name, value in
                (('cause_record_id', root), ('outbox_id', outbox_id), ('parent_task_id', parent_task_id))}
            conn.execute('''INSERT INTO compiler_runtime.propagation_task_causes
                (task_id,cause_key,cause_record_id,outbox_id,parent_task_id) VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT(task_id,cause_key) DO NOTHING''', (task['task_id'], digest(cause),
                cause['cause_record_id'], cause['outbox_id'], cause['parent_task_id']))
        return task

    def finish(self, conn, task, token, outcome):
        if not isinstance(outcome, dict):
            _fail('invalid_propagation_outcome', 2)
        current = self._assert(conn, task['task_id'], token)
        row = conn.execute('''UPDATE compiler_runtime.propagation_tasks SET state='done',lease_token=NULL,lease_expires=NULL,
            retry_after=NULL,error_code=NULL,outcome=%s,updated_at=clock_timestamp() WHERE task_id=%s RETURNING *''',
            (Jsonb(_json(outcome)), current['task_id'])).fetchone()
        self._event(conn, current['run_id'], 'finished', {'attempt': current['attempt'], 'lease_token': token,
            'request_id': current['request_id'], 'outcome': outcome}, current['task_id'])
        return _json(row)

    def awaiting_model(self, task_id, token, details):
        return self._release(task_id, token, 'awaiting_model', None, details)

    def block(self, task_id, token, code, details):
        return self._release(task_id, token, 'blocked', _text(code, 'propagation_error_required'), details)

    def suspend_anomaly(self, conn, task, witness):
        """Stop causal dispatch atomically; accepted Knowledge history remains intact."""
        task = self._assert(conn, task['task_id'], task['lease_token'])
        run = self._run(conn, task['run_id'])
        prior = conn.execute('''SELECT event_id FROM compiler_runtime.propagation_events
            WHERE run_id=%s AND event_type='semantic_anomaly' AND payload->>'witness_sha256'=%s''',
            (run['run_id'], witness['witness_sha256'])).fetchone()
        if prior is None:
            self._event(conn, run['run_id'], 'semantic_anomaly', witness, task['task_id'])
        self._release_locked(conn, task, run, 'blocked', 'propagation_semantic_oscillation',
            {'witness_sha256': witness['witness_sha256'], 'record_id': witness['record_id']})
        conn.execute("""UPDATE compiler_runtime.propagation_runs SET state='needs_human',
            updated_at=clock_timestamp() WHERE run_id=%s""", (run['run_id'],))

    def transport_retry(self, task_id, token, code, details, backoff_seconds=30):
        code, delay = _text(code, 'propagation_error_required'), _seconds(backoff_seconds)
        if not isinstance(details, dict) or details.get('phase') not in (None, 'generator', 'validator'):
            _fail('invalid_propagation_outcome', 2)
        with self.transaction(task_id, token) as (conn, task, run):
            # The durable model-call boundary also handles a process dying after
            # a successful phase commit but before the workflow journal update.
            success = conn.execute('''SELECT max(m.created_at) AS created_at FROM compiler_runtime.k_model_calls m
                JOIN compiler_runtime.propagation_execution_bindings b USING(execution_id)
                WHERE b.task_id=%s AND m.status='succeeded' ''', (task_id,)).fetchone()['created_at']
            events = conn.execute('''SELECT event_type,payload FROM compiler_runtime.propagation_events
                WHERE task_id=%s AND event_type IN ('retry','retry_requested','transport_succeeded')
                    AND (%s::timestamptz IS NULL OR created_at>%s)
                ORDER BY created_at DESC,event_id DESC''', (task_id, success, success)).fetchall()
            streak = _transport_streak(events, details.get('phase'))
            recorded = {**_json(details), 'transport_error_code': code, 'consecutive_transport_failures': streak,
                'transport_failure_streak_limit': TRANSPORT_FAILURE_LIMIT}
            if streak >= TRANSPORT_FAILURE_LIMIT:
                self._event(conn, run['run_id'], 'transport_anomaly', recorded, task_id)
                return self._release_locked(conn, task, run, 'blocked', 'propagation_transport_anomaly', recorded)
            return self._release_locked(conn, task, run, 'retry', code, recorded, delay)

    def transport_succeeded(self, task_id, token, phase):
        if phase not in ('generator', 'validator'):
            _fail('invalid_propagation_phase', 2)
        with self.transaction(task_id, token) as (conn, task, run):
            self._event(conn, run['run_id'], 'transport_succeeded', {'phase': phase, 'attempt': task['attempt'],
                'lease_token': token, 'request_id': task['request_id']}, task_id)
            return task

    def _release(self, task_id, token, state, code, details, delay=None):
        if not isinstance(details, dict):
            _fail('invalid_propagation_outcome', 2)
        with self.transaction(task_id, token) as (conn, task, run):
            return self._release_locked(conn, task, run, state, code, details, delay)

    def _release_locked(self, conn, task, run, state, code, details, delay=None):
        row = conn.execute('''UPDATE compiler_runtime.propagation_tasks SET state=%s,lease_token=NULL,lease_expires=NULL,
            retry_after=CASE WHEN %s::integer IS NULL THEN NULL ELSE clock_timestamp()+(%s*interval '1 second') END,
            error_code=%s,updated_at=clock_timestamp() WHERE task_id=%s RETURNING *''',
            (state, delay, delay, code, task['task_id'])).fetchone()
        self._event(conn, run['run_id'], state, {'lease_token': task['lease_token'], 'attempt': task['attempt'],
            'request_id': task['request_id'], 'error_code': code, 'details': details, 'retry_after': row['retry_after']}, task['task_id'])
        return _json(row)

    def retry(self, task_id, reason, *, actor_ref='local', precondition=None):
        reason = _text(reason, 'propagation_reason_required')
        actor_ref = _text(actor_ref, 'propagation_actor_required')
        with connection(self.dsn) as conn, conn.transaction():
            self._fence(conn)
            owned = conn.execute('SELECT run_id FROM compiler_runtime.propagation_tasks WHERE task_id=%s', (request_id(task_id),)).fetchone()
            if owned is None:
                _fail('propagation_task_not_found', 2)
            run = self._run(conn, owned['run_id'], lock=True)
            task = conn.execute('SELECT * FROM compiler_runtime.propagation_tasks WHERE task_id=%s FOR UPDATE', (task_id,)).fetchone()
            if run['state'] in ('completed', 'cancelled', 'prepared') or task['state'] not in ('blocked', 'retry'):
                _fail('propagation_task_not_retryable')
            semantic_holds = conn.execute('''SELECT 1 FROM compiler_runtime.propagation_tasks
                WHERE run_id=%s AND state='blocked' AND error_code='propagation_semantic_oscillation' LIMIT 1''',
                (run['run_id'],)).fetchone()
            if semantic_holds and task['error_code'] != 'propagation_semantic_oscillation':
                _fail('propagation_anomaly_acknowledgement_required')
            if task['error_code'] == 'propagation_semantic_oscillation' and precondition is None:
                _fail('propagation_anomaly_acknowledgement_required')
            if precondition is not None:
                precondition(conn, run, _json(task))
            conn.execute("UPDATE compiler_runtime.propagation_tasks SET state='pending',retry_after=NULL,error_code=NULL,updated_at=clock_timestamp() WHERE task_id=%s", (task_id,))
            remaining_holds = conn.execute('''SELECT 1 FROM compiler_runtime.propagation_tasks
                WHERE run_id=%s AND state='blocked' AND error_code='propagation_semantic_oscillation' LIMIT 1''',
                (run['run_id'],)).fetchone()
            if run['state'] == 'needs_human' and not remaining_holds:
                conn.execute("UPDATE compiler_runtime.propagation_runs SET state='running',lease_epoch=lease_epoch+1,updated_at=clock_timestamp() WHERE run_id=%s", (run['run_id'],))
            self._event(conn, run['run_id'], 'retry_requested', {'reason': reason, 'previous_state': task['state'],
                'request_id': task['request_id'], 'previous_error_code': task['error_code'], 'actor_ref': actor_ref}, task_id)
            return _json(conn.execute('SELECT * FROM compiler_runtime.propagation_tasks WHERE task_id=%s', (task_id,)).fetchone())

    def rotate_request(self, conn, task, reason):
        reason = _text(reason, 'propagation_reason_required')
        current = self._assert(conn, task['task_id'], task['lease_token'])
        identifier = _uuid(conn)
        row = conn.execute('''UPDATE compiler_runtime.propagation_tasks SET request_id=%s,updated_at=clock_timestamp()
            WHERE task_id=%s RETURNING *''', (identifier, current['task_id'])).fetchone()
        self._event(conn, current['run_id'], 'request_rotated', {'previous_request_id': current['request_id'],
            'request_id': identifier, 'reason': reason, 'lease_token': current['lease_token'], 'attempt': current['attempt']}, current['task_id'])
        return _json(row)

    def harvest(self, conn, run):
        if run['state'] in ('completed', 'cancelled'):
            return []
        events = conn.execute('''SELECT o.* FROM compiler_runtime.k_outbox o WHERE (
            %s::jsonb ? o.record_id::text OR EXISTS(SELECT 1 FROM compiler_runtime.k_compilation_records r
                JOIN compiler_runtime.propagation_execution_bindings b USING(execution_id)
                JOIN compiler_runtime.propagation_tasks t USING(task_id)
                WHERE r.record_id=o.record_id AND t.run_id=%s))
            AND NOT EXISTS(SELECT 1 FROM compiler_runtime.propagation_task_causes c
                JOIN compiler_runtime.propagation_tasks t USING(task_id) WHERE c.outbox_id=o.event_id AND t.run_id=%s)
            ORDER BY o.created_at,o.event_id''', (Jsonb(run['scope']['root_record_ids']), run['run_id'], run['run_id'])).fetchall()
        tasks = [self.enqueue(conn, run['run_id'], 'outbox', {'event_id': str(event['event_id']),
            'record_id': str(event['record_id']), 'operation': event['operation']},
            cause_record_id=str(event['record_id']), outbox_id=str(event['event_id'])) for event in events]
        supports = conn.execute('''SELECT s.* FROM canonical_store.knowledge_current_supports s WHERE (
            %s::jsonb ? s.record_id::text OR EXISTS(SELECT 1 FROM compiler_runtime.k_compilation_records r
                JOIN compiler_runtime.propagation_execution_bindings b USING(execution_id)
                JOIN compiler_runtime.propagation_tasks t USING(task_id)
                WHERE r.record_id=s.record_id AND t.run_id=%s))
            AND NOT EXISTS(SELECT 1 FROM compiler_runtime.propagation_task_causes c
                JOIN compiler_runtime.propagation_tasks t USING(task_id)
                WHERE c.cause_record_id=s.record_id AND t.run_id=%s AND t.kind='support_refresh'
                    AND t.payload->>'support_record_id'=s.record_id::text)
            ORDER BY s.event_order''', (Jsonb(run['scope']['root_record_ids']), run['run_id'], run['run_id'])).fetchall()
        tasks.extend(self.enqueue(conn, run['run_id'], 'support_refresh', {'record_id': str(support['record_id']),
            'support_record_id': str(support['record_id']), 'node_revision_id': str(support['node_revision_id']), 'operation': 'k2k'},
            cause_record_id=str(support['record_id'])) for support in supports)
        return tasks

    def settle(self, run_id):
        with connection(self.dsn) as conn, conn.transaction():
            watermark = self._fence(conn)
            run = self._run(conn, run_id, lock=True)
            if run['state'] != 'running':
                return {**run, 'status': run['state']}
            self.harvest(conn, run)
            tasks = conn.execute('''SELECT *,retry_after>clock_timestamp() AS retry_future
                FROM compiler_runtime.propagation_tasks WHERE run_id=%s ORDER BY created_at,task_id''', (run_id,)).fetchall()
            counts = _counts(tasks)
            if counts['total'] == counts['done']:
                receipt = {'root_record_ids': run['scope']['root_record_ids'], 'scope': run['scope'], 'policy': run['policy'],
                    'initial_watermark': run['initial_watermark'], 'completion_watermark': watermark, 'task_counts': counts,
                    'dependency_coverage': {'undispatched_outbox': 0, 'undispatched_supports': 0, 'enumeration_complete': True},
                    'completion_scope': 'frozen_roots_and_all_causal_descendants', 'reason': 'all_scoped_obligations_resolved'}
                self._event(conn, run_id, 'completed', receipt)
                conn.execute("UPDATE compiler_runtime.propagation_runs SET state='completed',updated_at=clock_timestamp() WHERE run_id=%s", (run_id,))
                return {**self._run(conn, run_id), 'status': 'completed', 'counts': counts, 'receipt': receipt}
            unfinished = [task for task in tasks if task['state'] != 'done']
            if all(task['state'] == 'blocked' for task in unfinished):
                self._event(conn, run_id, 'needs_human', {'counts': counts,
                    'task_ids': [str(task['task_id']) for task in unfinished]})
                conn.execute("UPDATE compiler_runtime.propagation_runs SET state='needs_human',updated_at=clock_timestamp() WHERE run_id=%s", (run_id,))
                return {**self._run(conn, run_id), 'status': 'needs_human', 'counts': counts}
            waiting = all(task['state'] == 'blocked' or (task['state'] == 'retry' and task['retry_future']) for task in unfinished)
            return {**run, 'status': 'retry_wait' if waiting else 'running', 'counts': counts}
