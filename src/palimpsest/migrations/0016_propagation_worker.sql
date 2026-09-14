-- Durable propagation consumes immutable outbox events; no prior source or SQL is rewritten.
-- Current support is a separate append-only applicability receipt, never revision origin.
CREATE TABLE compiler_runtime.k_revalidation_targets (
    execution_id uuid PRIMARY KEY REFERENCES compiler_runtime.k_execution_contexts,
    snapshot jsonb NOT NULL CHECK (jsonb_typeof(snapshot)='object')
);
CREATE TABLE compiler_runtime.k_revalidation_decisions (
    record_id uuid PRIMARY KEY REFERENCES compiler_runtime.k_compilation_records,
    validation jsonb NOT NULL CHECK (jsonb_typeof(validation)='object')
);
CREATE TABLE canonical_store.knowledge_current_supports (
    record_id uuid PRIMARY KEY REFERENCES canonical_store.knowledge_derivations,
    node_revision_id uuid NOT NULL REFERENCES canonical_store.knowledge_node_revisions,
    previous_support_record_id uuid REFERENCES canonical_store.knowledge_derivations,
    event_order bigint NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX knowledge_current_support_revision ON canonical_store.knowledge_current_supports
    (node_revision_id,event_order DESC);
CREATE TABLE canonical_store.knowledge_derivation_support_refs (
    record_id uuid NOT NULL REFERENCES canonical_store.knowledge_derivations,
    premise_node_revision_id uuid NOT NULL REFERENCES canonical_store.knowledge_node_revisions,
    support_record_id uuid REFERENCES canonical_store.knowledge_derivations,
    PRIMARY KEY(record_id,premise_node_revision_id),
    FOREIGN KEY(record_id,premise_node_revision_id)
        REFERENCES canonical_store.knowledge_derivation_premises(record_id,premise_node_revision_id)
);

CREATE FUNCTION canonical_store.current_k_support_record(id uuid) RETURNS uuid LANGUAGE sql STABLE AS $$
    SELECT COALESCE(
        (SELECT record_id FROM canonical_store.knowledge_current_supports
            WHERE node_revision_id=id ORDER BY event_order DESC LIMIT 1),
        (SELECT d.record_id FROM canonical_store.knowledge_node_revisions v
            JOIN canonical_store.knowledge_derivations d ON d.record_id=v.origin_record_id
            WHERE v.knode_revision_id=id))
$$;

CREATE TABLE compiler_runtime.propagation_runs (
    run_id uuid PRIMARY KEY CHECK (uuid_extract_version(run_id) IS NOT DISTINCT FROM 7),
    request_fingerprint text NOT NULL CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
    scope jsonb NOT NULL CHECK (jsonb_typeof(scope)='object'),
    policy jsonb NOT NULL CHECK (jsonb_typeof(policy)='object'),
    initial_watermark bigint NOT NULL CHECK (initial_watermark>=0),
    lease_epoch bigint NOT NULL DEFAULT 0 CHECK (lease_epoch>=0),
    state text NOT NULL DEFAULT 'prepared' CHECK (state IN
        ('prepared','running','paused','needs_human','completed','cancelled')),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE compiler_runtime.propagation_tasks (
    task_id uuid PRIMARY KEY CHECK (uuid_extract_version(task_id) IS NOT DISTINCT FROM 7),
    run_id uuid NOT NULL REFERENCES compiler_runtime.propagation_runs,
    task_key text NOT NULL CHECK (task_key ~ '^[0-9a-f]{64}$'),
    kind text NOT NULL CHECK (kind IN ('outbox','support_refresh','node_revalidate','edge_revalidate','n2e','k2k','wiki_refresh')),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
    state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','leased','awaiting_model','retry','blocked','done')),
    attempt integer NOT NULL DEFAULT 0 CHECK (attempt>=0),
    lease_token uuid,
    lease_epoch bigint NOT NULL DEFAULT 0 CHECK (lease_epoch>=0),
    lease_expires timestamptz,
    retry_after timestamptz,
    error_code text,
    outcome jsonb CHECK (jsonb_typeof(outcome)='object'),
    request_id uuid NOT NULL CHECK (uuid_extract_version(request_id) IS NOT DISTINCT FROM 7),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id,task_key),
    CHECK ((state='leased')=(lease_token IS NOT NULL AND lease_expires IS NOT NULL)),
    CHECK (state='leased' OR (lease_token IS NULL AND lease_expires IS NULL)),
    CHECK ((state='done')=(outcome IS NOT NULL))
);
CREATE INDEX propagation_tasks_ready ON compiler_runtime.propagation_tasks(run_id,state,retry_after,created_at);
CREATE TABLE compiler_runtime.propagation_events (
    event_id uuid PRIMARY KEY CHECK (uuid_extract_version(event_id) IS NOT DISTINCT FROM 7),
    run_id uuid NOT NULL REFERENCES compiler_runtime.propagation_runs,
    task_id uuid REFERENCES compiler_runtime.propagation_tasks,
    event_type text NOT NULL CHECK (length(btrim(event_type))>0),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX propagation_events_run ON compiler_runtime.propagation_events(run_id,created_at,event_id);
CREATE TABLE compiler_runtime.propagation_task_causes (
    task_id uuid NOT NULL REFERENCES compiler_runtime.propagation_tasks,
    cause_key text NOT NULL CHECK (cause_key ~ '^[0-9a-f]{64}$'),
    cause_record_id uuid REFERENCES compiler_runtime.k_compilation_records,
    outbox_id uuid REFERENCES compiler_runtime.k_outbox(event_id),
    parent_task_id uuid REFERENCES compiler_runtime.propagation_tasks,
    PRIMARY KEY(task_id,cause_key),
    CHECK (cause_record_id IS NOT NULL OR outbox_id IS NOT NULL OR parent_task_id IS NOT NULL)
);
CREATE INDEX propagation_causes_outbox ON compiler_runtime.propagation_task_causes(outbox_id);
CREATE TABLE compiler_runtime.propagation_execution_bindings (
    execution_id uuid PRIMARY KEY REFERENCES compiler_runtime.k_execution_contexts,
    task_id uuid NOT NULL REFERENCES compiler_runtime.propagation_tasks,
    lease_token uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX propagation_bindings_task ON compiler_runtime.propagation_execution_bindings(task_id);

CREATE FUNCTION compiler_runtime.assert_propagation_claim(task uuid, token uuid, execution uuid DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE owned_run uuid; run_state text; run_epoch bigint; claimed compiler_runtime.propagation_tasks;
BEGIN
    SELECT run_id INTO STRICT owned_run FROM compiler_runtime.propagation_tasks WHERE task_id=task;
    SELECT state,lease_epoch INTO STRICT run_state,run_epoch FROM compiler_runtime.propagation_runs WHERE run_id=owned_run FOR SHARE;
    SELECT * INTO STRICT claimed FROM compiler_runtime.propagation_tasks WHERE task_id=task FOR UPDATE;
    IF run_state<>'running' OR claimed.state<>'leased' OR claimed.lease_token IS DISTINCT FROM token
        OR claimed.lease_epoch<>run_epoch
        OR claimed.lease_expires<=clock_timestamp()
        OR (execution IS NOT NULL AND NOT EXISTS(SELECT 1 FROM compiler_runtime.propagation_execution_bindings
            WHERE execution_id=execution AND task_id=task))
    THEN RAISE EXCEPTION 'Propagation claim is paused, expired, superseded or belongs to another execution'; END IF;
END; $$;

CREATE FUNCTION compiler_runtime.guard_propagation_run() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='INSERT' THEN
        IF NEW.state<>'prepared' OR NEW.lease_epoch<>0
            OR jsonb_typeof(NEW.scope->'root_record_ids') IS DISTINCT FROM 'array'
            OR jsonb_array_length(NEW.scope->'root_record_ids')=0
            OR jsonb_typeof(NEW.scope->'allowed_data_ids') IS DISTINCT FROM 'array'
            OR jsonb_typeof(NEW.scope->'wiki_ids') IS DISTINCT FROM 'array'
            OR EXISTS(SELECT 1 FROM jsonb_array_elements_text(NEW.scope->'root_record_ids') root_id
                WHERE NOT EXISTS(SELECT 1 FROM compiler_runtime.k_compilation_records
                    WHERE record_id::text=root_id AND disposition IN ('accepted_new','accepted_revision','reused','no_material_delta')))
            OR NEW.initial_watermark IS DISTINCT FROM (SELECT version FROM compiler_runtime.knowledge_state WHERE singleton)
        THEN RAISE EXCEPTION 'Propagation scope requires exact accepted root records and the current source watermark'; END IF;
    ELSIF OLD.state IN ('completed','cancelled')
        OR to_jsonb(NEW)-ARRAY['state','updated_at','lease_epoch'] IS DISTINCT FROM to_jsonb(OLD)-ARRAY['state','updated_at','lease_epoch']
        OR NEW.lease_epoch IS DISTINCT FROM (OLD.lease_epoch+(CASE
            WHEN NEW.state<>OLD.state AND NEW.state IN ('running','paused','cancelled') THEN 1 ELSE 0 END))
        OR (NEW.state='completed' AND OLD.state<>'running')
    THEN RAISE EXCEPTION 'Propagation scope and terminal state are immutable'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER propagation_run_guard BEFORE INSERT OR UPDATE ON compiler_runtime.propagation_runs
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_propagation_run();

CREATE FUNCTION compiler_runtime.guard_propagation_task() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE run_state text; run_epoch bigint;
BEGIN
    SELECT state,lease_epoch INTO STRICT run_state,run_epoch FROM compiler_runtime.propagation_runs WHERE run_id=NEW.run_id FOR SHARE;
    IF run_state IN ('completed','cancelled') THEN RAISE EXCEPTION 'A terminal propagation run cannot gain or change work'; END IF;
    IF TG_OP='INSERT' THEN
        IF NEW.state<>'pending' OR NEW.attempt<>0 OR NEW.lease_epoch<>0 OR NEW.outcome IS NOT NULL
        THEN RAISE EXCEPTION 'Propagation tasks start pending without a completion receipt'; END IF;
    ELSE
        IF OLD.state='done' OR to_jsonb(NEW)-ARRAY['state','attempt','lease_token','lease_epoch','lease_expires','retry_after',
            'error_code','outcome','request_id','updated_at'] IS DISTINCT FROM
            to_jsonb(OLD)-ARRAY['state','attempt','lease_token','lease_epoch','lease_expires','retry_after',
            'error_code','outcome','request_id','updated_at']
        THEN RAISE EXCEPTION 'Propagation task identity, input and completion are immutable'; END IF;
        IF NEW.state='leased' THEN
            IF run_state<>'running' OR NEW.lease_expires<=clock_timestamp() OR NEW.lease_epoch<>run_epoch
                OR (OLD.state='leased' AND OLD.lease_token=NEW.lease_token
                    AND (NEW.attempt<>OLD.attempt OR OLD.lease_epoch<>run_epoch))
                OR (OLD.lease_token IS DISTINCT FROM NEW.lease_token AND NEW.attempt<>OLD.attempt+1)
                OR (OLD.state='leased' AND OLD.lease_token IS DISTINCT FROM NEW.lease_token
                    AND OLD.lease_expires>clock_timestamp() AND OLD.lease_epoch=run_epoch)
            THEN RAISE EXCEPTION 'A lease must be current, fenced and monotonically attempted'; END IF;
        ELSIF OLD.state='leased' THEN
            IF run_state<>'running' OR OLD.lease_expires<=clock_timestamp() OR NEW.attempt<>OLD.attempt
                OR OLD.lease_epoch<>run_epoch OR NEW.lease_epoch<>OLD.lease_epoch
            THEN RAISE EXCEPTION 'An expired or paused worker cannot acknowledge its task'; END IF;
        ELSIF NEW.state='done' OR NEW.attempt<>OLD.attempt OR NEW.lease_epoch<>OLD.lease_epoch THEN
            RAISE EXCEPTION 'Only a current lease can resolve a task or advance its attempt';
        END IF;
        IF NEW.state='done' AND EXISTS(SELECT 1 FROM compiler_runtime.propagation_execution_bindings
            WHERE task_id=NEW.task_id) AND NOT EXISTS(
                SELECT 1 FROM compiler_runtime.propagation_execution_bindings b
                JOIN compiler_runtime.operation_executions e USING(execution_id)
                WHERE b.task_id=NEW.task_id AND b.execution_id::text=NEW.outcome->>'execution_id'
                    AND e.state IN ('completed','zero_output'))
        THEN RAISE EXCEPTION 'A model-backed task can acknowledge only its own successful final execution'; END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER propagation_task_guard BEFORE INSERT OR UPDATE ON compiler_runtime.propagation_tasks
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_propagation_task();

CREATE FUNCTION compiler_runtime.guard_propagation_link() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_run uuid; owner_state text;
BEGIN
    SELECT t.run_id,r.state INTO STRICT owner_run,owner_state FROM compiler_runtime.propagation_tasks t
        JOIN compiler_runtime.propagation_runs r USING(run_id) WHERE t.task_id=NEW.task_id;
    IF TG_TABLE_NAME='propagation_execution_bindings' THEN
        PERFORM compiler_runtime.assert_propagation_claim(NEW.task_id,NEW.lease_token);
        IF NOT EXISTS(SELECT 1 FROM compiler_runtime.operation_executions e
            JOIN compiler_runtime.k_execution_contexts c USING(execution_id)
            JOIN compiler_runtime.propagation_tasks t ON t.task_id=NEW.task_id
            JOIN compiler_runtime.propagation_runs workflow USING(run_id)
            WHERE e.execution_id=NEW.execution_id AND e.state='prepared' AND c.request_id=t.request_id
                AND workflow.scope->'allowed_data_ids' ? e.data_id
                AND ((t.kind IN ('node_revalidate','k2k') AND e.operation='k2k')
                    OR (t.kind IN ('edge_revalidate','n2e') AND e.operation='n2e')))
        THEN RAISE EXCEPTION 'A causal execution must be prepared atomically for its claimed task and request'; END IF;
    ELSE
        IF owner_state IN ('completed','cancelled')
            OR (NEW.parent_task_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM compiler_runtime.propagation_tasks
                WHERE task_id=NEW.parent_task_id AND run_id=owner_run))
            OR (NEW.outbox_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM compiler_runtime.k_outbox
                WHERE event_id=NEW.outbox_id AND (NEW.cause_record_id IS NULL OR record_id=NEW.cause_record_id)))
        THEN RAISE EXCEPTION 'A propagation cause must preserve its exact outbox, record and workflow ownership'; END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER propagation_binding_guard BEFORE INSERT ON compiler_runtime.propagation_execution_bindings
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_propagation_link();
CREATE TRIGGER propagation_cause_guard BEFORE INSERT ON compiler_runtime.propagation_task_causes
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_propagation_link();

CREATE FUNCTION compiler_runtime.guard_propagation_event() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.task_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM compiler_runtime.propagation_tasks
        WHERE task_id=NEW.task_id AND run_id=NEW.run_id)
    THEN RAISE EXCEPTION 'Propagation event and task must belong to the same workflow'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER propagation_event_guard BEFORE INSERT ON compiler_runtime.propagation_events
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_propagation_event();

CREATE FUNCTION compiler_runtime.check_propagation_completion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE selected_run compiler_runtime.propagation_runs; completion jsonb; current_watermark bigint;
        counts jsonb; missing_outbox bigint; missing_supports bigint;
BEGIN
    SELECT * INTO STRICT selected_run FROM compiler_runtime.propagation_runs WHERE run_id=NEW.run_id;
    IF selected_run.state<>'completed' THEN
        IF TG_TABLE_NAME='propagation_events' THEN
            IF NEW.event_type='completed'
            THEN RAISE EXCEPTION 'A completion receipt cannot describe a non-completed workflow'; END IF;
        END IF;
        RETURN NULL;
    END IF;
    -- All writers use the same canonical state fence before run/task locks.
    SELECT version INTO STRICT current_watermark FROM compiler_runtime.knowledge_state WHERE singleton FOR UPDATE;
    SELECT payload INTO completion FROM compiler_runtime.propagation_events
        WHERE run_id=selected_run.run_id AND event_type='completed' ORDER BY created_at DESC,event_id DESC LIMIT 1;
    SELECT jsonb_build_object('total',count(*),'done',count(*) FILTER(WHERE state='done'),
        'pending',count(*) FILTER(WHERE state='pending'),'leased',count(*) FILTER(WHERE state='leased'),
        'awaiting_model',count(*) FILTER(WHERE state='awaiting_model'),'retry',count(*) FILTER(WHERE state='retry'),
        'blocked',count(*) FILTER(WHERE state='blocked')) INTO counts
        FROM compiler_runtime.propagation_tasks WHERE run_id=selected_run.run_id;
    SELECT count(*) INTO missing_outbox FROM compiler_runtime.k_outbox o
        WHERE (selected_run.scope->'root_record_ids' ? o.record_id::text OR EXISTS(
            SELECT 1 FROM compiler_runtime.k_compilation_records r
            JOIN compiler_runtime.propagation_execution_bindings b USING(execution_id)
            JOIN compiler_runtime.propagation_tasks t USING(task_id)
            WHERE r.record_id=o.record_id AND t.run_id=selected_run.run_id))
        AND NOT EXISTS(SELECT 1 FROM compiler_runtime.propagation_task_causes c
            JOIN compiler_runtime.propagation_tasks t USING(task_id)
            WHERE c.outbox_id=o.event_id AND t.run_id=selected_run.run_id);
    SELECT count(*) INTO missing_supports FROM canonical_store.knowledge_current_supports s
        WHERE (selected_run.scope->'root_record_ids' ? s.record_id::text OR EXISTS(
            SELECT 1 FROM compiler_runtime.k_compilation_records r
            JOIN compiler_runtime.propagation_execution_bindings b USING(execution_id)
            JOIN compiler_runtime.propagation_tasks t USING(task_id)
            WHERE r.record_id=s.record_id AND t.run_id=selected_run.run_id))
        AND NOT EXISTS(SELECT 1 FROM compiler_runtime.propagation_task_causes c
            JOIN compiler_runtime.propagation_tasks t USING(task_id)
            WHERE c.cause_record_id=s.record_id AND t.run_id=selected_run.run_id AND t.kind='support_refresh'
                AND t.payload->>'support_record_id'=s.record_id::text);
    IF completion IS NULL OR completion->'root_record_ids' IS DISTINCT FROM selected_run.scope->'root_record_ids'
        OR completion->'scope' IS DISTINCT FROM selected_run.scope OR completion->'policy' IS DISTINCT FROM selected_run.policy
        OR completion->'initial_watermark' IS DISTINCT FROM to_jsonb(selected_run.initial_watermark)
        OR completion->'completion_watermark' IS DISTINCT FROM to_jsonb(current_watermark)
        OR completion->'task_counts' IS DISTINCT FROM counts
        OR completion->'dependency_coverage'->'undispatched_outbox' IS DISTINCT FROM to_jsonb(missing_outbox)
        OR completion->'dependency_coverage'->'undispatched_supports' IS DISTINCT FROM to_jsonb(missing_supports)
        OR completion->'dependency_coverage'->'enumeration_complete' IS DISTINCT FROM 'true'::jsonb
        OR missing_outbox<>0 OR missing_supports<>0 OR EXISTS(SELECT 1 FROM compiler_runtime.propagation_tasks
            WHERE run_id=selected_run.run_id AND state<>'done')
        OR EXISTS(SELECT 1 FROM compiler_runtime.propagation_tasks t WHERE t.run_id=selected_run.run_id
            AND EXISTS(SELECT 1 FROM compiler_runtime.propagation_execution_bindings WHERE task_id=t.task_id)
            AND NOT EXISTS(SELECT 1 FROM compiler_runtime.propagation_execution_bindings b
                JOIN compiler_runtime.operation_executions e USING(execution_id)
                WHERE b.task_id=t.task_id AND b.execution_id::text=t.outcome->>'execution_id'
                    AND e.state IN ('completed','zero_output')))
    THEN RAISE EXCEPTION 'Propagation completion requires exact coverage, acknowledged descendants and no unfinished work'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER propagation_run_completion_guard AFTER UPDATE ON compiler_runtime.propagation_runs
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_propagation_completion();
CREATE CONSTRAINT TRIGGER propagation_event_completion_guard AFTER INSERT ON compiler_runtime.propagation_events
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_propagation_completion();

CREATE OR REPLACE FUNCTION compiler_runtime.current_k2k_premise(id uuid) RETURNS boolean LANGUAGE sql STABLE AS $$
    WITH RECURSIVE ancestry(revision_id) AS (
        SELECT id UNION
        SELECT p.premise_node_revision_id FROM ancestry a
        JOIN canonical_store.knowledge_derivation_premises p
            ON p.record_id=canonical_store.current_k_support_record(a.revision_id))
    SELECT NOT EXISTS(SELECT 1 FROM ancestry a
        LEFT JOIN canonical_store.knowledge_node_revisions v ON v.knode_revision_id=a.revision_id
        LEFT JOIN canonical_store.knowledge_nodes n USING(knode_id)
        LEFT JOIN compiler_runtime.k_compilation_records r ON r.record_id=v.origin_record_id
        WHERE v.knode_revision_id IS NULL OR n.current_revision_id IS DISTINCT FROM a.revision_id
            OR r.disposition NOT IN ('accepted_new','accepted_revision')
            OR r.result_node_revision_id IS DISTINCT FROM a.revision_id
            OR r.result_node_id IS DISTINCT FROM v.knode_id)
        AND NOT EXISTS(SELECT 1 FROM ancestry a
            JOIN canonical_store.knowledge_derivation_premises p
                ON p.record_id=canonical_store.current_k_support_record(a.revision_id)
            LEFT JOIN canonical_store.knowledge_derivation_support_refs consumed
                ON consumed.record_id=p.record_id AND consumed.premise_node_revision_id=p.premise_node_revision_id
            JOIN canonical_store.knowledge_node_revisions v ON v.knode_revision_id=p.premise_node_revision_id
            LEFT JOIN canonical_store.knowledge_derivations initial_support ON initial_support.record_id=v.origin_record_id
            WHERE (CASE WHEN consumed.record_id IS NULL THEN initial_support.record_id ELSE consumed.support_record_id END)
                IS DISTINCT FROM canonical_store.current_k_support_record(p.premise_node_revision_id))
$$;

CREATE FUNCTION canonical_store.guard_derivation_support_ref() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE context_snapshot jsonb; marker text; actual_record compiler_runtime.k_compilation_records; frozen_node jsonb;
BEGIN
    SELECT * INTO STRICT actual_record FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.record_id;
    SELECT c.input_snapshot,p.payload->>'current_support_binding' INTO context_snapshot,marker
        FROM compiler_runtime.k_execution_contexts c JOIN compiler_runtime.operation_executions e USING(execution_id)
        JOIN compiler_runtime.profiles p USING(profile_id) WHERE c.execution_id=actual_record.execution_id;
    SELECT item INTO frozen_node FROM jsonb_array_elements(context_snapshot->'input'->'nodes') item
        WHERE item->>'knode_revision_id'=NEW.premise_node_revision_id::text;
    IF marker IS DISTINCT FROM 'knowledge-current-support-v1' OR actual_record.record_type<>'k2k'
        OR actual_record.disposition NOT IN ('pending','needs_human') OR frozen_node IS NULL
        OR NOT frozen_node ? 'current_support_record_id'
        OR frozen_node->>'current_support_record_id' IS DISTINCT FROM NEW.support_record_id::text
        OR NEW.support_record_id IS DISTINCT FROM canonical_store.current_k_support_record(NEW.premise_node_revision_id)
        OR NOT compiler_runtime.current_k2k_premise(NEW.premise_node_revision_id)
    THEN RAISE EXCEPTION 'A derivation must retain the exact active support actually supplied for each premise'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER derivation_support_ref_guard BEFORE INSERT ON canonical_store.knowledge_derivation_support_refs
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_derivation_support_ref();

CREATE FUNCTION canonical_store.check_derivation_support_refs() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_record compiler_runtime.k_compilation_records; marker text;
BEGIN
    SELECT * INTO STRICT actual_record FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.record_id;
    SELECT p.payload->>'current_support_binding' INTO marker FROM compiler_runtime.operation_executions e
        JOIN compiler_runtime.profiles p USING(profile_id) WHERE e.execution_id=actual_record.execution_id;
    IF marker IS DISTINCT FROM 'knowledge-current-support-v1' THEN RETURN NULL; END IF;
    IF EXISTS(SELECT 1 FROM canonical_store.knowledge_derivation_premises p
        LEFT JOIN canonical_store.knowledge_derivation_support_refs consumed
            ON consumed.record_id=p.record_id AND consumed.premise_node_revision_id=p.premise_node_revision_id
        WHERE p.record_id=actual_record.record_id AND (consumed.record_id IS NULL
            OR consumed.support_record_id IS DISTINCT FROM canonical_store.current_k_support_record(p.premise_node_revision_id)
            OR NOT compiler_runtime.current_k2k_premise(p.premise_node_revision_id)))
    THEN RAISE EXCEPTION 'Every new derivation premise needs a complete, still-current support receipt'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER derivation_support_refs_complete AFTER INSERT ON canonical_store.knowledge_derivations
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION canonical_store.check_derivation_support_refs();
CREATE CONSTRAINT TRIGGER derivation_support_refs_current AFTER INSERT ON canonical_store.knowledge_derivation_support_refs
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION canonical_store.check_derivation_support_refs();

CREATE FUNCTION compiler_runtime.is_k_revalidation(id uuid) RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT EXISTS(SELECT 1 FROM compiler_runtime.operation_executions e
        JOIN compiler_runtime.profiles p USING(profile_id) WHERE e.execution_id=id AND e.operation IN ('n2e','k2k')
            AND p.payload->>'targeted_revalidation'='knowledge-revalidation-v1')
$$;
CREATE FUNCTION compiler_runtime.guard_k_revalidation_target() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_execution compiler_runtime.operation_executions; target jsonb; edge_snapshot jsonb; prior_basis jsonb;
BEGIN
    SELECT * INTO STRICT actual_execution FROM compiler_runtime.operation_executions WHERE execution_id=NEW.execution_id;
    target:=NEW.snapshot;
    IF actual_execution.state<>'prepared' OR NOT compiler_runtime.is_k_revalidation(NEW.execution_id)
        OR target->>'schema_version' IS DISTINCT FROM 'knowledge-revalidation-v1'
        OR COALESCE(target->>'target_sha256','') !~ '^[0-9a-f]{64}$'
        OR target IS DISTINCT FROM (SELECT input_snapshot->'revalidation_target'
            FROM compiler_runtime.k_execution_contexts WHERE execution_id=NEW.execution_id)
    THEN RAISE EXCEPTION 'Targeted revalidation must freeze its exact immutable target and profile'; END IF;
    IF target->>'kind'='node' THEN
        IF actual_execution.operation<>'k2k' OR NOT compiler_runtime.is_explicit_k_revision(NEW.execution_id)
            OR NOT EXISTS(SELECT 1 FROM compiler_runtime.k_revision_targets t
                WHERE t.execution_id=NEW.execution_id AND t.target_knode_id::text=target->>'target_knode_id'
                    AND t.expected_revision_id::text=target->>'target_revision_id')
            OR target->>'prior_support_record_id' IS DISTINCT FROM
                canonical_store.current_k_support_record((target->>'target_revision_id')::uuid)::text
            OR target->'premise_revision_ids' IS DISTINCT FROM (SELECT jsonb_agg(node_revision_id::text ORDER BY ordinal)
                FROM compiler_runtime.k_input_node_revisions WHERE execution_id=NEW.execution_id)
        THEN RAISE EXCEPTION 'Node revalidation must retain the current comparison target and its complete replacement premises'; END IF;
    ELSIF target->>'kind'='edge' THEN
        SELECT to_jsonb(actual) INTO edge_snapshot FROM (
            SELECT e.kedge_id,v.kedge_revision_id,e.predicate,e.from_knode_id,e.to_knode_id,
                v.from_knode_revision_id,v.to_knode_revision_id,v.qualifiers,v.content_fingerprint,v.identity_fingerprint
            FROM canonical_store.knowledge_edges e JOIN canonical_store.knowledge_edge_revisions v
                ON v.kedge_revision_id=e.current_revision_id
            WHERE v.kedge_revision_id::text=target->>'target_revision_id' AND e.kedge_id::text=target->>'target_kedge_id') actual;
        IF actual_execution.operation<>'n2e' OR edge_snapshot IS NULL OR target->'target' IS DISTINCT FROM edge_snapshot
            OR jsonb_typeof(target->'prior_applicable') IS DISTINCT FROM 'boolean'
            OR NOT EXISTS(SELECT 1 FROM canonical_store.knowledge_nodes source_node
                JOIN canonical_store.knowledge_nodes target_node ON target_node.knode_id::text=edge_snapshot->>'to_knode_id'
                WHERE source_node.knode_id::text=edge_snapshot->>'from_knode_id'
                    AND source_node.current_revision_id::text=target->>'from_revision_id'
                    AND target_node.current_revision_id::text=target->>'to_revision_id'
                    AND compiler_runtime.current_k2k_premise(source_node.current_revision_id)
                    AND compiler_runtime.current_k2k_premise(target_node.current_revision_id))
            OR NOT EXISTS(SELECT 1 FROM compiler_runtime.k_input_node_revisions
                WHERE execution_id=NEW.execution_id AND node_revision_id::text=target->>'from_revision_id')
            OR NOT EXISTS(SELECT 1 FROM compiler_runtime.k_input_node_revisions
                WHERE execution_id=NEW.execution_id AND node_revision_id::text=target->>'to_revision_id')
        THEN RAISE EXCEPTION 'Edge revalidation preserves exact semantic revision and freezes its current usable endpoint pair'; END IF;
        SELECT jsonb_build_object('event_id',applicability_event_id::text,'applicable',applicable) INTO prior_basis
            FROM canonical_store.knowledge_edge_applicability_events
            WHERE semantic_kedge_revision_id::text=target->>'target_revision_id'
                AND from_knode_revision_id::text=target->'prior_pair'->>0
                AND to_knode_revision_id::text=target->'prior_pair'->>1
            ORDER BY event_order DESC LIMIT 1;
        IF jsonb_typeof(target->'prior_pair') IS DISTINCT FROM 'array' OR jsonb_array_length(target->'prior_pair')<>2
            OR (prior_basis IS NULL AND (target->>'prior_basis_event_id' IS NOT NULL
                OR target->'prior_applicable' IS DISTINCT FROM 'true'::jsonb
                OR target->'prior_pair' IS DISTINCT FROM jsonb_build_array(edge_snapshot->'from_knode_revision_id',edge_snapshot->'to_knode_revision_id')))
            OR (prior_basis IS NOT NULL AND (target->>'prior_basis_event_id' IS DISTINCT FROM prior_basis->>'event_id'
                OR target->'prior_applicable' IS DISTINCT FROM prior_basis->'applicable'))
        THEN RAISE EXCEPTION 'Prior applicability must use the latest explicit decision for its exact historical pair'; END IF;
    ELSE RAISE EXCEPTION 'Unknown targeted revalidation kind'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER k_revalidation_target_guard BEFORE INSERT ON compiler_runtime.k_revalidation_targets
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_k_revalidation_target();

CREATE FUNCTION compiler_runtime.check_k_revalidation_context() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE context_snapshot jsonb;
BEGIN
    SELECT input_snapshot INTO STRICT context_snapshot FROM compiler_runtime.k_execution_contexts WHERE execution_id=NEW.execution_id;
    IF context_snapshot ? 'revalidation_target' OR compiler_runtime.is_k_revalidation(NEW.execution_id) THEN
        IF NOT compiler_runtime.is_k_revalidation(NEW.execution_id) OR NOT EXISTS(
            SELECT 1 FROM compiler_runtime.k_revalidation_targets WHERE execution_id=NEW.execution_id
                AND snapshot=context_snapshot->'revalidation_target')
        THEN RAISE EXCEPTION 'Revalidation context requires its immutable target and matching profile'; END IF;
    END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER k_revalidation_context_guard AFTER INSERT ON compiler_runtime.k_execution_contexts
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_k_revalidation_context();

CREATE FUNCTION compiler_runtime.guard_k_revalidation_decision() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_record compiler_runtime.k_compilation_records; target jsonb; candidate jsonb;
BEGIN
    SELECT * INTO STRICT actual_record FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.record_id;
    SELECT snapshot INTO STRICT target FROM compiler_runtime.k_revalidation_targets WHERE execution_id=actual_record.execution_id;
    SELECT body INTO STRICT candidate FROM compiler_runtime.k_temporary_candidates WHERE record_id=actual_record.record_id;
    IF NOT compiler_runtime.is_k_revalidation(actual_record.execution_id)
        OR actual_record.disposition NOT IN ('pending','needs_human') OR actual_record.ordinal<>0
        OR NOT EXISTS(SELECT 1 FROM compiler_runtime.operation_executions WHERE execution_id=actual_record.execution_id AND state='proposed')
        OR NEW.validation->>'target_sha256' IS DISTINCT FROM target->>'target_sha256'
        OR NEW.validation->>'kind' IS DISTINCT FROM target->>'kind'
        OR jsonb_typeof(NEW.validation->'confirmed') IS DISTINCT FROM 'boolean'
        OR jsonb_typeof(NEW.validation->'reason_codes') IS DISTINCT FROM 'array'
        OR COALESCE(length(btrim(NEW.validation->>'reason')),0)=0
    THEN RAISE EXCEPTION 'Target revalidation requires its actual staged candidate and independent structured decision'; END IF;
    IF NEW.validation->'confirmed'='true'::jsonb THEN
        IF jsonb_typeof(NEW.validation->'material_change') IS DISTINCT FROM 'boolean'
        THEN RAISE EXCEPTION 'A confirmed revalidation needs a definite materiality result'; END IF;
        IF target->>'kind'='node' THEN
            IF NEW.validation->'same_identity' IS DISTINCT FROM 'true'::jsonb
                OR NEW.validation->'grounding_valid' IS DISTINCT FROM 'true'::jsonb
                OR NEW.validation->'premise_revision_ids' IS DISTINCT FROM target->'premise_revision_ids'
                OR NEW.validation->'prior_support_record_id' IS DISTINCT FROM target->'prior_support_record_id'
                OR NOT EXISTS(SELECT 1 FROM compiler_runtime.k_revision_decisions d WHERE d.record_id=actual_record.record_id
                    AND d.validation->>'action' IN ('accepted_revision','reused')
                    AND d.validation->'review'->'material_change'=NEW.validation->'material_change')
            THEN RAISE EXCEPTION 'Node support requires accepted same-identity inference and exact replacement premises'; END IF;
        ELSE
            IF jsonb_typeof(NEW.validation->'applicable') IS DISTINCT FROM 'boolean'
                OR NEW.validation->'applicable' IS DISTINCT FROM candidate->'applicability_proposal'->'applicable'
                OR NEW.validation->'material_change' IS DISTINCT FROM to_jsonb(target->'prior_applicable'<>NEW.validation->'applicable')
            THEN RAISE EXCEPTION 'Edge applicability needs definite agreeing generation and validation over its exact prior basis'; END IF;
        END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER k_revalidation_decision_guard BEFORE INSERT ON compiler_runtime.k_revalidation_decisions
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_k_revalidation_decision();

CREATE FUNCTION canonical_store.guard_current_support() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_record compiler_runtime.k_compilation_records; target jsonb; next_order bigint;
BEGIN
    UPDATE compiler_runtime.knowledge_state SET version=version+1 WHERE singleton RETURNING version INTO next_order;
    NEW.event_order:=next_order;
    SELECT * INTO STRICT actual_record FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.record_id;
    SELECT snapshot INTO STRICT target FROM compiler_runtime.k_revalidation_targets WHERE execution_id=actual_record.execution_id;
    IF target->>'kind' IS DISTINCT FROM 'node' OR actual_record.record_type<>'k2k'
        OR actual_record.disposition NOT IN ('pending','needs_human')
        OR NEW.previous_support_record_id::text IS DISTINCT FROM target->>'prior_support_record_id'
        OR NEW.previous_support_record_id IS DISTINCT FROM canonical_store.current_k_support_record((target->>'target_revision_id')::uuid)
        OR NOT EXISTS(SELECT 1 FROM canonical_store.knowledge_derivations d
            JOIN canonical_store.knowledge_node_revisions v ON v.knode_revision_id=d.result_node_revision_id
            JOIN compiler_runtime.k_revalidation_decisions decision ON decision.record_id=d.record_id
            WHERE d.record_id=NEW.record_id AND d.result_node_revision_id=NEW.node_revision_id
                AND v.knode_id::text=target->>'target_knode_id'
                AND (v.knode_revision_id::text=target->>'target_revision_id' OR v.supersedes_revision_id::text=target->>'target_revision_id')
                AND decision.validation->'confirmed'='true'::jsonb)
    THEN RAISE EXCEPTION 'Current support must append the confirmed revalidation result while preserving its old support and revision origin'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER a_current_support_guard BEFORE INSERT ON canonical_store.knowledge_current_supports
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_current_support();

CREATE FUNCTION compiler_runtime.check_k_revalidation_commit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_record compiler_runtime.k_compilation_records; target jsonb; decision jsonb;
        context_row compiler_runtime.k_execution_contexts;
BEGIN
    SELECT * INTO STRICT actual_record FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.record_id;
    IF NOT compiler_runtime.is_k_revalidation(actual_record.execution_id) OR actual_record.disposition='pending' THEN RETURN NULL; END IF;
    SELECT snapshot INTO STRICT target FROM compiler_runtime.k_revalidation_targets WHERE execution_id=actual_record.execution_id;
    SELECT validation INTO decision FROM compiler_runtime.k_revalidation_decisions WHERE record_id=actual_record.record_id;
    IF decision IS NULL OR (decision->'confirmed'='true'::jsonb) IS DISTINCT FROM
        (actual_record.disposition IN ('accepted_revision','reused','no_material_delta'))
    THEN RAISE EXCEPTION 'Revalidation disposition must preserve its exact confirmed or unresolved result'; END IF;
    IF decision->'confirmed'<>'true'::jsonb THEN RETURN NULL; END IF;
    SELECT * INTO STRICT context_row FROM compiler_runtime.k_execution_contexts WHERE execution_id=actual_record.execution_id;
    IF NOT EXISTS(SELECT 1 FROM compiler_runtime.k_model_calls generator
        JOIN compiler_runtime.k_model_calls validator ON validator.execution_id=generator.execution_id
        WHERE generator.execution_id=actual_record.execution_id AND generator.phase='generator' AND validator.phase='validator'
            AND generator.status='succeeded' AND validator.status='succeeded'
            AND generator.profile_id=context_row.generator_profile_id AND validator.profile_id=context_row.validator_profile_id
            AND length(btrim(generator.provider_ref))>0 AND length(btrim(validator.provider_ref))>0
            AND generator.provider_ref<>validator.provider_ref
            AND generator.receipt->'actual_delivery'='true'::jsonb AND validator.receipt->'actual_delivery'='true'::jsonb
            AND generator.receipt->>'delivered_revalidation_target_sha256'=target->>'target_sha256'
            AND validator.receipt->>'delivered_revalidation_target_sha256'=target->>'target_sha256')
    THEN RAISE EXCEPTION 'Confirmed revalidation requires actual independent delivery of its exact target'; END IF;
    IF target->>'kind'='node' THEN
        IF actual_record.disposition NOT IN ('accepted_revision','reused') OR NOT EXISTS(
            SELECT 1 FROM canonical_store.knowledge_current_supports s WHERE s.record_id=actual_record.record_id
                AND s.node_revision_id=actual_record.result_node_revision_id)
        THEN RAISE EXCEPTION 'Confirmed node revalidation must publish its immutable current-support receipt'; END IF;
    ELSE
        IF actual_record.disposition<>'no_material_delta'
            OR actual_record.result_edge_revision_id::text IS DISTINCT FROM target->>'target_revision_id'
            OR actual_record.result_edge_id::text IS DISTINCT FROM target->>'target_kedge_id'
            OR NOT EXISTS(SELECT 1 FROM canonical_store.knowledge_edges e
                JOIN canonical_store.knowledge_nodes source_node ON source_node.knode_id=e.from_knode_id
                JOIN canonical_store.knowledge_nodes target_node ON target_node.knode_id=e.to_knode_id
                WHERE e.kedge_id=actual_record.result_edge_id AND e.current_revision_id=actual_record.result_edge_revision_id
                    AND source_node.current_revision_id::text=target->>'from_revision_id'
                    AND target_node.current_revision_id::text=target->>'to_revision_id'
                    AND compiler_runtime.current_k2k_premise(source_node.current_revision_id)
                    AND compiler_runtime.current_k2k_premise(target_node.current_revision_id))
            OR NOT EXISTS(SELECT 1 FROM canonical_store.knowledge_edge_applicability_events a
                WHERE a.origin_record_id=actual_record.record_id AND a.semantic_kedge_revision_id=actual_record.result_edge_revision_id
                    AND a.from_knode_revision_id::text=target->>'from_revision_id'
                    AND a.to_knode_revision_id::text=target->>'to_revision_id'
                    AND to_jsonb(a.applicable)=decision->'applicable')
            OR (decision->'material_change'='true'::jsonb) IS DISTINCT FROM EXISTS(
                SELECT 1 FROM compiler_runtime.k_outbox WHERE record_id=actual_record.record_id AND operation='k2k')
            OR EXISTS(SELECT 1 FROM compiler_runtime.k_outbox WHERE record_id=actual_record.record_id AND operation<>'k2k')
        THEN RAISE EXCEPTION 'Rebased relation retains its semantic revision and propagates only actual applicability change'; END IF;
    END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER k_revalidation_record_commit_guard AFTER INSERT OR UPDATE ON compiler_runtime.k_compilation_records
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_k_revalidation_commit();
CREATE CONSTRAINT TRIGGER current_support_commit_guard AFTER INSERT ON canonical_store.knowledge_current_supports
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_k_revalidation_commit();

CREATE FUNCTION compiler_runtime.check_k_revalidation_completion() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.state IN ('completed','zero_output') AND compiler_runtime.is_k_revalidation(NEW.execution_id)
        AND NOT EXISTS(SELECT 1 FROM compiler_runtime.k_compilation_records r
            JOIN compiler_runtime.k_revalidation_decisions d USING(record_id)
            WHERE r.execution_id=NEW.execution_id AND r.disposition IN ('accepted_revision','reused','no_material_delta')
                AND d.validation->'confirmed'='true'::jsonb)
    THEN RAISE EXCEPTION 'A missing or undecidable target review cannot complete its required obligation'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER k_revalidation_completion_guard AFTER UPDATE ON compiler_runtime.operation_executions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_k_revalidation_completion();

DO $$ DECLARE relation text; BEGIN
    FOREACH relation IN ARRAY ARRAY[
        'compiler_runtime.k_revalidation_targets','compiler_runtime.k_revalidation_decisions',
        'canonical_store.knowledge_current_supports','canonical_store.knowledge_derivation_support_refs',
        'compiler_runtime.propagation_events','compiler_runtime.propagation_task_causes',
        'compiler_runtime.propagation_execution_bindings'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON %s FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
        EXECUTE format('CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON %s FOR EACH STATEMENT EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
    END LOOP;
    FOREACH relation IN ARRAY ARRAY['compiler_runtime.propagation_runs','compiler_runtime.propagation_tasks'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_delete BEFORE DELETE ON %s FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
        EXECUTE format('CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON %s FOR EACH STATEMENT EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
    END LOOP;
END; $$;
CREATE TRIGGER a_support_ref_state BEFORE INSERT ON canonical_store.knowledge_derivation_support_refs
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.advance_knowledge_state();
GRANT SELECT,INSERT ON compiler_runtime.k_revalidation_targets,compiler_runtime.k_revalidation_decisions,
    canonical_store.knowledge_current_supports,canonical_store.knowledge_derivation_support_refs,
    compiler_runtime.propagation_events,compiler_runtime.propagation_task_causes,
    compiler_runtime.propagation_execution_bindings TO palimpsest;
GRANT SELECT,INSERT,UPDATE ON compiler_runtime.propagation_runs,compiler_runtime.propagation_tasks TO palimpsest;
