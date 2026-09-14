-- First approved I2K/N2E slice: reported observations, propositions and supports.
-- Runtime Records survive promotion; existing Data/Information history is unchanged.
ALTER TABLE compiler_runtime.operation_executions DROP CONSTRAINT operation_executions_operation_check;
ALTER TABLE compiler_runtime.operation_executions ADD CHECK (operation IN ('d2i','i2k','n2e'));

-- ponytail: a global row serializes short K commits; partition only when measured contention warrants it.
CREATE TABLE compiler_runtime.knowledge_state (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    version bigint NOT NULL DEFAULT 0 CHECK (version>=0)
);
INSERT INTO compiler_runtime.knowledge_state DEFAULT VALUES;
CREATE FUNCTION compiler_runtime.guard_knowledge_state() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.singleton IS DISTINCT FROM OLD.singleton OR NEW.version<>OLD.version+1
    THEN RAISE EXCEPTION 'Knowledge state version must advance monotonically by one'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER knowledge_state_guard BEFORE UPDATE ON compiler_runtime.knowledge_state
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_knowledge_state();
CREATE TRIGGER knowledge_state_no_delete BEFORE DELETE ON compiler_runtime.knowledge_state
    FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation();
CREATE TABLE compiler_runtime.k_execution_contexts (
    execution_id uuid PRIMARY KEY REFERENCES compiler_runtime.operation_executions,
    request_id uuid NOT NULL UNIQUE CHECK (uuid_extract_version(request_id) IS NOT DISTINCT FROM 7),
    request_fingerprint text NOT NULL CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
    work_fingerprint text NOT NULL CHECK (work_fingerprint ~ '^[0-9a-f]{64}$'),
    input_digest text NOT NULL CHECK (input_digest ~ '^[0-9a-f]{64}$'),
    input_snapshot jsonb NOT NULL CHECK (jsonb_typeof(input_snapshot)='object'),
    expected_state_version bigint NOT NULL CHECK (expected_state_version>=0),
    generator_profile_id uuid NOT NULL REFERENCES compiler_runtime.profiles,
    validator_profile_id uuid NOT NULL REFERENCES compiler_runtime.profiles,
    validation_context_sha text CHECK (validation_context_sha ~ '^[0-9a-f]{64}$'),
    -- Reserved input metadata; completion belongs to the execution receipt, never this flag.
    complete_scope boolean NOT NULL DEFAULT false CHECK (NOT complete_scope),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX k_execution_work_idx ON compiler_runtime.k_execution_contexts(work_fingerprint);
CREATE TABLE compiler_runtime.k_compilation_records (
    record_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(record_id) IS NOT DISTINCT FROM 7),
    execution_id uuid NOT NULL REFERENCES compiler_runtime.k_execution_contexts,
    record_type text NOT NULL CHECK (record_type IN ('i2k','n2e')),
    ordinal integer NOT NULL CHECK (ordinal>=0),
    identity_fingerprint text NOT NULL CHECK (identity_fingerprint ~ '^[0-9a-f]{64}$'),
    content_fingerprint text NOT NULL CHECK (content_fingerprint ~ '^[0-9a-f]{64}$'),
    context_fingerprint text NOT NULL CHECK (context_fingerprint ~ '^[0-9a-f]{64}$'),
    disposition text NOT NULL DEFAULT 'pending' CHECK (disposition IN
        ('pending','accepted_new','accepted_revision','reused','rejected','needs_human','no_material_delta')),
    result_node_id uuid,
    result_node_revision_id uuid,
    result_edge_id uuid,
    result_edge_revision_id uuid,
    reason_codes jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(reason_codes)='array'),
    reason text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at timestamptz,
    UNIQUE (execution_id,ordinal),
    CHECK ((disposition NOT IN ('pending','needs_human'))=(resolved_at IS NOT NULL)),
    CHECK ((result_node_id IS NULL)=(result_node_revision_id IS NULL)),
    CHECK ((result_edge_id IS NULL)=(result_edge_revision_id IS NULL)),
    CHECK ((record_type='i2k' AND result_edge_id IS NULL) OR (record_type='n2e' AND result_node_id IS NULL)),
    CHECK ((disposition IN ('accepted_new','accepted_revision','reused','no_material_delta'))=
           (result_node_id IS NOT NULL OR result_edge_id IS NOT NULL))
);
CREATE TABLE compiler_runtime.k_temporary_candidates (
    record_id uuid PRIMARY KEY REFERENCES compiler_runtime.k_compilation_records,
    body jsonb NOT NULL CHECK (jsonb_typeof(body)='object')
);
CREATE TABLE canonical_store.knowledge_nodes (
    knode_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(knode_id) IS NOT DISTINCT FROM 7),
    kind text NOT NULL CHECK (kind IN ('proposition','observation')),
    identity_fingerprint text NOT NULL CHECK (identity_fingerprint ~ '^[0-9a-f]{64}$'),
    current_revision_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (kind,identity_fingerprint), UNIQUE (knode_id,identity_fingerprint)
);
CREATE TABLE canonical_store.knowledge_node_revisions (
    knode_revision_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(knode_revision_id) IS NOT DISTINCT FROM 7),
    knode_id uuid NOT NULL,
    semantic_payload jsonb NOT NULL CHECK (jsonb_typeof(semantic_payload)='object'),
    statement text NOT NULL CHECK (length(statement)>0),
    identity_fingerprint text NOT NULL CHECK (identity_fingerprint ~ '^[0-9a-f]{64}$'),
    content_fingerprint text NOT NULL CHECK (content_fingerprint ~ '^[0-9a-f]{64}$'),
    origin_record_id uuid NOT NULL REFERENCES compiler_runtime.k_compilation_records DEFERRABLE INITIALLY DEFERRED,
    supersedes_revision_id uuid,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (knode_revision_id,knode_id),
    FOREIGN KEY (knode_id,identity_fingerprint) REFERENCES canonical_store.knowledge_nodes(knode_id,identity_fingerprint),
    FOREIGN KEY (supersedes_revision_id,knode_id) REFERENCES canonical_store.knowledge_node_revisions(knode_revision_id,knode_id)
        DEFERRABLE INITIALLY DEFERRED,
    CHECK (supersedes_revision_id IS DISTINCT FROM knode_revision_id)
);
ALTER TABLE canonical_store.knowledge_nodes ADD FOREIGN KEY (current_revision_id,knode_id)
    REFERENCES canonical_store.knowledge_node_revisions(knode_revision_id,knode_id) DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE canonical_store.knowledge_edges (
    kedge_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(kedge_id) IS NOT DISTINCT FROM 7),
    predicate text NOT NULL CHECK (predicate='supports'),
    from_knode_id uuid NOT NULL REFERENCES canonical_store.knowledge_nodes,
    to_knode_id uuid NOT NULL REFERENCES canonical_store.knowledge_nodes,
    identity_fingerprint text NOT NULL CHECK (identity_fingerprint ~ '^[0-9a-f]{64}$'),
    current_revision_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (predicate,from_knode_id,to_knode_id), UNIQUE (kedge_id,from_knode_id,to_knode_id),
    UNIQUE (kedge_id,identity_fingerprint),
    CHECK (from_knode_id<>to_knode_id)
);
CREATE TABLE canonical_store.knowledge_edge_revisions (
    kedge_revision_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(kedge_revision_id) IS NOT DISTINCT FROM 7),
    kedge_id uuid NOT NULL,
    from_knode_id uuid NOT NULL,
    to_knode_id uuid NOT NULL,
    from_knode_revision_id uuid NOT NULL,
    to_knode_revision_id uuid NOT NULL,
    semantic_payload jsonb NOT NULL CHECK (jsonb_typeof(semantic_payload)='object'),
    qualifiers jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(qualifiers)='object'),
    rationale text NOT NULL DEFAULT '',
    identity_fingerprint text NOT NULL CHECK (identity_fingerprint ~ '^[0-9a-f]{64}$'),
    content_fingerprint text NOT NULL CHECK (content_fingerprint ~ '^[0-9a-f]{64}$'),
    origin_record_id uuid NOT NULL REFERENCES compiler_runtime.k_compilation_records DEFERRABLE INITIALLY DEFERRED,
    supersedes_revision_id uuid,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (kedge_revision_id,kedge_id),
    FOREIGN KEY (kedge_id,from_knode_id,to_knode_id)
        REFERENCES canonical_store.knowledge_edges(kedge_id,from_knode_id,to_knode_id),
    FOREIGN KEY (kedge_id,identity_fingerprint) REFERENCES canonical_store.knowledge_edges(kedge_id,identity_fingerprint),
    FOREIGN KEY (from_knode_revision_id,from_knode_id)
        REFERENCES canonical_store.knowledge_node_revisions(knode_revision_id,knode_id),
    FOREIGN KEY (to_knode_revision_id,to_knode_id)
        REFERENCES canonical_store.knowledge_node_revisions(knode_revision_id,knode_id),
    FOREIGN KEY (supersedes_revision_id,kedge_id)
        REFERENCES canonical_store.knowledge_edge_revisions(kedge_revision_id,kedge_id) DEFERRABLE INITIALLY DEFERRED,
    CHECK (supersedes_revision_id IS DISTINCT FROM kedge_revision_id)
);
ALTER TABLE canonical_store.knowledge_edges ADD FOREIGN KEY (current_revision_id,kedge_id)
    REFERENCES canonical_store.knowledge_edge_revisions(kedge_revision_id,kedge_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE compiler_runtime.k_compilation_records ADD
    FOREIGN KEY (result_node_revision_id,result_node_id)
    REFERENCES canonical_store.knowledge_node_revisions(knode_revision_id,knode_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE compiler_runtime.k_compilation_records ADD
    FOREIGN KEY (result_edge_revision_id,result_edge_id)
    REFERENCES canonical_store.knowledge_edge_revisions(kedge_revision_id,kedge_id) DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE compiler_runtime.k_input_information (
    execution_id uuid NOT NULL REFERENCES compiler_runtime.k_execution_contexts,
    ordinal integer NOT NULL CHECK (ordinal>=0),
    information_id uuid NOT NULL REFERENCES canonical_store.information,
    PRIMARY KEY (execution_id,ordinal), UNIQUE (execution_id,information_id)
);
CREATE TABLE compiler_runtime.k_input_node_revisions (
    execution_id uuid NOT NULL REFERENCES compiler_runtime.k_execution_contexts,
    ordinal integer NOT NULL CHECK (ordinal>=0),
    node_revision_id uuid NOT NULL REFERENCES canonical_store.knowledge_node_revisions,
    PRIMARY KEY (execution_id,ordinal), UNIQUE (execution_id,node_revision_id)
);
CREATE TABLE canonical_store.knowledge_node_groundings (
    grounding_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(grounding_id) IS NOT DISTINCT FROM 7),
    node_revision_id uuid NOT NULL REFERENCES canonical_store.knowledge_node_revisions,
    information_id uuid NOT NULL REFERENCES canonical_store.information,
    char_start integer NOT NULL CHECK (char_start>=0),
    char_end integer NOT NULL CHECK (char_end>=char_start),
    quote text NOT NULL,
    media_sha256 text CHECK (media_sha256 ~ '^[0-9a-f]{64}$'),
    source_role text NOT NULL CHECK (source_role IN ('abstract','results','methods','figure','discussion','other')),
    origin_record_id uuid NOT NULL REFERENCES compiler_runtime.k_compilation_records,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (length(quote)=char_end-char_start),
    CHECK (char_end>char_start OR media_sha256 IS NOT NULL)
);
CREATE INDEX knowledge_groundings_information_idx ON canonical_store.knowledge_node_groundings(information_id);
CREATE INDEX knowledge_groundings_revision_idx ON canonical_store.knowledge_node_groundings(node_revision_id);
CREATE TABLE canonical_store.knowledge_edge_applicability_events (
    applicability_event_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(applicability_event_id) IS NOT DISTINCT FROM 7),
    event_order bigint NOT NULL UNIQUE,
    kedge_id uuid NOT NULL,
    semantic_kedge_revision_id uuid NOT NULL,
    from_knode_id uuid NOT NULL,
    to_knode_id uuid NOT NULL,
    from_knode_revision_id uuid NOT NULL,
    to_knode_revision_id uuid NOT NULL,
    applicable boolean NOT NULL,
    origin_record_id uuid NOT NULL REFERENCES compiler_runtime.k_compilation_records,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (semantic_kedge_revision_id,kedge_id)
        REFERENCES canonical_store.knowledge_edge_revisions(kedge_revision_id,kedge_id),
    FOREIGN KEY (kedge_id,from_knode_id,to_knode_id)
        REFERENCES canonical_store.knowledge_edges(kedge_id,from_knode_id,to_knode_id),
    FOREIGN KEY (from_knode_revision_id,from_knode_id)
        REFERENCES canonical_store.knowledge_node_revisions(knode_revision_id,knode_id),
    FOREIGN KEY (to_knode_revision_id,to_knode_id)
        REFERENCES canonical_store.knowledge_node_revisions(knode_revision_id,knode_id)
);
CREATE INDEX knowledge_applicability_pair_idx ON canonical_store.knowledge_edge_applicability_events
    (semantic_kedge_revision_id,from_knode_revision_id,to_knode_revision_id,event_order DESC);
CREATE TABLE compiler_runtime.k_outbox (
    event_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(event_id) IS NOT DISTINCT FROM 7),
    record_id uuid NOT NULL REFERENCES compiler_runtime.k_compilation_records,
    operation text NOT NULL CHECK (operation IN ('n2e','k2k')),
    state text NOT NULL DEFAULT 'pending' CHECK (state='pending'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (record_id,operation)
);
CREATE TABLE compiler_runtime.k_model_calls (
    call_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(call_id) IS NOT DISTINCT FROM 7),
    execution_id uuid NOT NULL REFERENCES compiler_runtime.k_execution_contexts,
    phase text NOT NULL CHECK (phase IN ('generator','validator','source')),
    profile_id uuid NOT NULL REFERENCES compiler_runtime.profiles,
    input_sha256 text NOT NULL CHECK (input_sha256 ~ '^[0-9a-f]{64}$'),
    output_sha256 text CHECK (output_sha256 ~ '^[0-9a-f]{64}$'),
    provider_ref text,
    receipt jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(receipt)='object'),
    usage jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(usage)='object'),
    status text NOT NULL CHECK (status IN ('succeeded','failed','unavailable')),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE compiler_runtime.k_source_requests (
    request_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(request_id) IS NOT DISTINCT FROM 7),
    execution_id uuid NOT NULL REFERENCES compiler_runtime.k_execution_contexts,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
    status text NOT NULL CHECK (status IN ('unavailable','pending','provided')),
    receipt jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(receipt)='object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE FUNCTION compiler_runtime.guard_k_context() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='INSERT' THEN
        IF NOT EXISTS (SELECT 1 FROM compiler_runtime.operation_executions
            WHERE execution_id=NEW.execution_id AND operation IN ('i2k','n2e') AND state='prepared')
        THEN RAISE EXCEPTION 'K context requires a prepared I2K/N2E execution'; END IF;
    ELSIF to_jsonb(NEW)-'validation_context_sha' IS DISTINCT FROM to_jsonb(OLD)-'validation_context_sha'
        OR OLD.validation_context_sha IS NOT NULL THEN
        RAISE EXCEPTION 'K execution input is frozen';
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER k_context_guard BEFORE INSERT OR UPDATE ON compiler_runtime.k_execution_contexts
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_k_context();
CREATE FUNCTION compiler_runtime.guard_k_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='INSERT' THEN
        IF NEW.disposition<>'pending' OR NOT EXISTS (SELECT 1 FROM compiler_runtime.operation_executions
            WHERE execution_id=NEW.execution_id AND operation=NEW.record_type AND state NOT IN ('completed','zero_output'))
        THEN RAISE EXCEPTION 'K Record must start pending in its matching operation'; END IF;
    ELSIF OLD.disposition NOT IN ('pending','needs_human') OR
        to_jsonb(NEW)-ARRAY['disposition','result_node_id','result_node_revision_id','result_edge_id',
            'result_edge_revision_id','reason_codes','reason','resolved_at'] IS DISTINCT FROM
        to_jsonb(OLD)-ARRAY['disposition','result_node_id','result_node_revision_id','result_edge_id',
            'result_edge_revision_id','reason_codes','reason','resolved_at'] THEN
        RAISE EXCEPTION 'K Record inputs and terminal results are immutable';
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER k_record_guard BEFORE INSERT OR UPDATE ON compiler_runtime.k_compilation_records
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_k_record();
CREATE FUNCTION compiler_runtime.guard_k_candidate() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM compiler_runtime.k_compilation_records
        WHERE record_id=NEW.record_id AND disposition IN ('pending','needs_human'))
    THEN RAISE EXCEPTION 'Only unresolved K Records may own candidate content'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER k_candidate_guard BEFORE INSERT ON compiler_runtime.k_temporary_candidates
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_k_candidate();
CREATE FUNCTION compiler_runtime.guard_k_input() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM compiler_runtime.operation_executions e
        WHERE e.execution_id=NEW.execution_id AND e.state='prepared'
        AND e.operation=CASE WHEN TG_TABLE_NAME='k_input_information' THEN 'i2k' ELSE 'n2e' END)
    THEN RAISE EXCEPTION 'Authoritative K inputs are frozen before model execution'; END IF;
    IF TG_TABLE_NAME='k_input_information' THEN
        IF NOT EXISTS (SELECT 1 FROM canonical_store.information i
            JOIN compiler_runtime.operation_executions e ON e.data_id=i.data_id
            WHERE e.execution_id=NEW.execution_id AND i.information_id=NEW.information_id)
        THEN RAISE EXCEPTION 'This first I2K profile accepts only its registered Data'; END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER k_information_input_guard BEFORE INSERT ON compiler_runtime.k_input_information
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_k_input();
CREATE TRIGGER k_node_input_guard BEFORE INSERT ON compiler_runtime.k_input_node_revisions
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_k_input();
CREATE FUNCTION canonical_store.guard_k_logical_update() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF to_jsonb(NEW)-'current_revision_id' IS DISTINCT FROM to_jsonb(OLD)-'current_revision_id'
    THEN RAISE EXCEPTION 'Logical K identity is immutable'; END IF;
    IF NEW.current_revision_id IS DISTINCT FROM OLD.current_revision_id THEN
        IF TG_TABLE_NAME='knowledge_nodes' THEN
            IF NOT EXISTS (SELECT 1 FROM canonical_store.knowledge_node_revisions
                WHERE knode_revision_id=NEW.current_revision_id AND knode_id=NEW.knode_id
                AND supersedes_revision_id=OLD.current_revision_id)
            THEN RAISE EXCEPTION 'Node current update requires a direct successor'; END IF;
        ELSE
            IF NOT EXISTS (SELECT 1 FROM canonical_store.knowledge_edge_revisions
                WHERE kedge_revision_id=NEW.current_revision_id AND kedge_id=NEW.kedge_id
                AND supersedes_revision_id=OLD.current_revision_id)
            THEN RAISE EXCEPTION 'Edge current update requires a direct successor'; END IF;
        END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER knowledge_node_update_guard BEFORE UPDATE ON canonical_store.knowledge_nodes
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_k_logical_update();
CREATE TRIGGER knowledge_edge_update_guard BEFORE UPDATE ON canonical_store.knowledge_edges
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_k_logical_update();
CREATE FUNCTION canonical_store.guard_k_revision_insert() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE current_id uuid; previous_payload jsonb; previous_qualifiers jsonb; previous_fp text; same_payload boolean;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.origin_record_id
        AND disposition IN ('pending','needs_human')
        AND record_type=CASE WHEN TG_TABLE_NAME='knowledge_node_revisions' THEN 'i2k' ELSE 'n2e' END)
    THEN RAISE EXCEPTION 'K revision requires its unresolved operation Record'; END IF;
    IF TG_TABLE_NAME='knowledge_node_revisions' THEN
        SELECT current_revision_id INTO STRICT current_id FROM canonical_store.knowledge_nodes WHERE knode_id=NEW.knode_id;
        IF NEW.supersedes_revision_id IS NULL THEN
            IF EXISTS (SELECT 1 FROM canonical_store.knowledge_node_revisions WHERE knode_id=NEW.knode_id)
            THEN RAISE EXCEPTION 'An existing Node cannot receive a second initial revision'; END IF;
        ELSE
            SELECT semantic_payload,content_fingerprint INTO STRICT previous_payload,previous_fp
                FROM canonical_store.knowledge_node_revisions WHERE knode_revision_id=NEW.supersedes_revision_id;
            same_payload:=previous_payload=NEW.semantic_payload;
        END IF;
    ELSE
        SELECT current_revision_id INTO STRICT current_id FROM canonical_store.knowledge_edges WHERE kedge_id=NEW.kedge_id;
        IF NEW.supersedes_revision_id IS NULL THEN
            IF EXISTS (SELECT 1 FROM canonical_store.knowledge_edge_revisions WHERE kedge_id=NEW.kedge_id)
            THEN RAISE EXCEPTION 'An existing Edge cannot receive a second initial revision'; END IF;
        ELSE
            SELECT semantic_payload,qualifiers,content_fingerprint INTO STRICT previous_payload,previous_qualifiers,previous_fp
                FROM canonical_store.knowledge_edge_revisions WHERE kedge_revision_id=NEW.supersedes_revision_id;
            same_payload:=previous_payload=NEW.semantic_payload AND previous_qualifiers=NEW.qualifiers;
        END IF;
    END IF;
    IF NEW.supersedes_revision_id IS NOT NULL THEN
        IF current_id IS DISTINCT FROM NEW.supersedes_revision_id
        THEN RAISE EXCEPTION 'K revision comparison base is stale'; END IF;
        IF same_payload OR previous_fp=NEW.content_fingerprint
        THEN RAISE EXCEPTION 'Equivalent content cannot create a semantic revision'; END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER knowledge_node_revision_guard BEFORE INSERT ON canonical_store.knowledge_node_revisions
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_k_revision_insert();
CREATE TRIGGER knowledge_edge_revision_guard BEFORE INSERT ON canonical_store.knowledge_edge_revisions
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_k_revision_insert();
CREATE FUNCTION canonical_store.guard_k_grounding() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM compiler_runtime.k_compilation_records r
        JOIN compiler_runtime.k_input_information x ON x.execution_id=r.execution_id
        JOIN canonical_store.information i ON i.information_id=x.information_id
        WHERE r.record_id=NEW.origin_record_id AND r.record_type='i2k'
          AND r.disposition IN ('pending','needs_human') AND i.information_id=NEW.information_id
          AND NEW.char_end<=length(i.content)
          AND substring(i.content FROM NEW.char_start+1 FOR NEW.char_end-NEW.char_start)=NEW.quote
          AND (NEW.media_sha256 IS NULL OR EXISTS (
              SELECT 1 FROM jsonb_each(COALESCE(i.payload->'source_artifacts','{}'::jsonb)) a
              WHERE a.value->>'sha256'=NEW.media_sha256)))
    THEN RAISE EXCEPTION 'K grounding must quote delivered I and its actual image descriptors'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER knowledge_grounding_guard BEFORE INSERT ON canonical_store.knowledge_node_groundings
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_k_grounding();
CREATE FUNCTION canonical_store.fill_k_edge_owners() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE source_id uuid; target_id uuid;
BEGIN
    SELECT from_knode_id,to_knode_id INTO STRICT source_id,target_id
        FROM canonical_store.knowledge_edges WHERE kedge_id=NEW.kedge_id;
    NEW.from_knode_id:=COALESCE(NEW.from_knode_id,source_id);
    NEW.to_knode_id:=COALESCE(NEW.to_knode_id,target_id);
    RETURN NEW;
END; $$;
CREATE TRIGGER knowledge_edge_owner_guard BEFORE INSERT ON canonical_store.knowledge_edge_revisions
    FOR EACH ROW EXECUTE FUNCTION canonical_store.fill_k_edge_owners();
CREATE TRIGGER knowledge_applicability_owner_guard BEFORE INSERT ON canonical_store.knowledge_edge_applicability_events
    FOR EACH ROW EXECUTE FUNCTION canonical_store.fill_k_edge_owners();

CREATE FUNCTION canonical_store.check_k_revision_commit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r compiler_runtime.k_compilation_records; node_case boolean; revision_id uuid; object_id uuid;
BEGIN
    node_case:=TG_TABLE_NAME='knowledge_node_revisions';
    SELECT * INTO STRICT r FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.origin_record_id;
    IF node_case THEN
        revision_id:=NEW.knode_revision_id; object_id:=NEW.knode_id;
        IF r.record_type<>'i2k' OR r.result_node_revision_id IS DISTINCT FROM revision_id
            OR r.result_node_id IS DISTINCT FROM object_id OR NOT EXISTS (
                SELECT 1 FROM canonical_store.knowledge_node_groundings
                WHERE node_revision_id=revision_id AND origin_record_id=r.record_id)
        THEN RAISE EXCEPTION 'Node revision needs its I2K Record and validated grounding'; END IF;
        IF NOT EXISTS (SELECT 1 FROM canonical_store.knowledge_nodes
            WHERE knode_id=object_id AND current_revision_id=revision_id)
        THEN RAISE EXCEPTION 'New Node revision must be the atomically published current revision'; END IF;
    ELSE
        revision_id:=NEW.kedge_revision_id; object_id:=NEW.kedge_id;
        IF r.record_type<>'n2e' OR r.result_edge_revision_id IS DISTINCT FROM revision_id
            OR r.result_edge_id IS DISTINCT FROM object_id
            OR NOT EXISTS (SELECT 1 FROM compiler_runtime.k_input_node_revisions
                WHERE execution_id=r.execution_id AND node_revision_id=NEW.from_knode_revision_id)
            OR NOT EXISTS (SELECT 1 FROM compiler_runtime.k_input_node_revisions
                WHERE execution_id=r.execution_id AND node_revision_id=NEW.to_knode_revision_id)
            OR NOT EXISTS (SELECT 1 FROM canonical_store.knowledge_nodes
                WHERE knode_id=NEW.from_knode_id AND current_revision_id=NEW.from_knode_revision_id)
            OR NOT EXISTS (SELECT 1 FROM canonical_store.knowledge_nodes
                WHERE knode_id=NEW.to_knode_id AND current_revision_id=NEW.to_knode_revision_id)
        THEN RAISE EXCEPTION 'Edge revision needs its N2E Record and exact authoritative endpoints'; END IF;
        IF NOT EXISTS (SELECT 1 FROM canonical_store.knowledge_edges
            WHERE kedge_id=object_id AND current_revision_id=revision_id)
        THEN RAISE EXCEPTION 'New Edge revision must be the atomically published current revision'; END IF;
    END IF;
    IF r.disposition IS DISTINCT FROM (CASE WHEN NEW.supersedes_revision_id IS NULL
            THEN 'accepted_new' ELSE 'accepted_revision' END)
        OR r.identity_fingerprint IS DISTINCT FROM NEW.identity_fingerprint
        OR r.content_fingerprint IS DISTINCT FROM NEW.content_fingerprint
        OR EXISTS (SELECT 1 FROM compiler_runtime.k_temporary_candidates WHERE record_id=r.record_id)
        OR NOT EXISTS (SELECT 1 FROM compiler_runtime.k_outbox WHERE record_id=r.record_id
            AND operation=CASE WHEN node_case THEN 'n2e' ELSE 'k2k' END)
    THEN RAISE EXCEPTION 'K revision, terminal Record, cleanup and downstream obligation must commit together'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER knowledge_node_commit_guard AFTER INSERT ON canonical_store.knowledge_node_revisions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION canonical_store.check_k_revision_commit();
CREATE CONSTRAINT TRIGGER knowledge_edge_commit_guard AFTER INSERT ON canonical_store.knowledge_edge_revisions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION canonical_store.check_k_revision_commit();
CREATE FUNCTION canonical_store.check_k_grounding_commit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM compiler_runtime.k_compilation_records r WHERE r.record_id=NEW.origin_record_id
        AND r.result_node_revision_id=NEW.node_revision_id
        AND r.disposition IN ('accepted_new','accepted_revision','reused','no_material_delta'))
    THEN RAISE EXCEPTION 'New grounding must be accepted for its exact revision'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER knowledge_grounding_commit_guard AFTER INSERT ON canonical_store.knowledge_node_groundings
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION canonical_store.check_k_grounding_commit();
CREATE FUNCTION compiler_runtime.check_k_record_commit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r compiler_runtime.k_compilation_records;
BEGIN
    SELECT * INTO STRICT r FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.record_id;
    IF r.disposition NOT IN ('pending','needs_human') AND EXISTS (
        SELECT 1 FROM compiler_runtime.k_temporary_candidates WHERE record_id=r.record_id)
    THEN RAISE EXCEPTION 'Terminal K candidate content must be cleaned in the same commit'; END IF;
    IF r.disposition='needs_human' AND NOT EXISTS (
        SELECT 1 FROM compiler_runtime.k_temporary_candidates WHERE record_id=r.record_id)
    THEN RAISE EXCEPTION 'Unresolved human review must retain its candidate content'; END IF;
    IF r.disposition IN ('accepted_new','accepted_revision') AND NOT EXISTS (
        SELECT 1 FROM compiler_runtime.k_outbox WHERE record_id=r.record_id)
    THEN RAISE EXCEPTION 'Accepted K requires a durable downstream obligation'; END IF;
    IF r.disposition IN ('accepted_new','accepted_revision') THEN
        IF r.record_type='i2k' AND NOT EXISTS (SELECT 1 FROM canonical_store.knowledge_node_revisions
            WHERE knode_revision_id=r.result_node_revision_id AND origin_record_id=r.record_id)
        THEN RAISE EXCEPTION 'Accepted I2K Record must originate its result revision'; END IF;
        IF r.record_type='n2e' AND NOT EXISTS (SELECT 1 FROM canonical_store.knowledge_edge_revisions
            WHERE kedge_revision_id=r.result_edge_revision_id AND origin_record_id=r.record_id)
        THEN RAISE EXCEPTION 'Accepted N2E Record must originate its result revision'; END IF;
    END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER k_record_commit_guard AFTER INSERT OR UPDATE ON compiler_runtime.k_compilation_records
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_k_record_commit();
CREATE FUNCTION canonical_store.check_k_applicability_commit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM compiler_runtime.k_compilation_records r
        WHERE r.record_id=NEW.origin_record_id AND r.record_type='n2e'
        AND r.disposition IN ('no_material_delta','reused')
        AND r.result_edge_revision_id=NEW.semantic_kedge_revision_id
        AND EXISTS (SELECT 1 FROM compiler_runtime.k_input_node_revisions
            WHERE execution_id=r.execution_id AND node_revision_id=NEW.from_knode_revision_id)
        AND EXISTS (SELECT 1 FROM compiler_runtime.k_input_node_revisions
            WHERE execution_id=r.execution_id AND node_revision_id=NEW.to_knode_revision_id))
    THEN RAISE EXCEPTION 'Applicability requires a resolved N2E Record and exact endpoint inputs'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER knowledge_applicability_commit_guard AFTER INSERT ON canonical_store.knowledge_edge_applicability_events
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION canonical_store.check_k_applicability_commit();
CREATE FUNCTION compiler_runtime.advance_knowledge_state() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE next_version bigint;
BEGIN
    UPDATE compiler_runtime.knowledge_state SET version=version+1 WHERE singleton RETURNING version INTO next_version;
    IF TG_TABLE_NAME='knowledge_edge_applicability_events' THEN
        -- Allocate after taking the common lock, not from a pre-lock sequence.
        NEW.event_order:=next_version;
    END IF;
    RETURN NEW;
END; $$;
DO $$ DECLARE relation text; BEGIN
    FOREACH relation IN ARRAY ARRAY['canonical_store.knowledge_nodes','canonical_store.knowledge_node_revisions',
        'canonical_store.knowledge_edges','canonical_store.knowledge_edge_revisions',
        'canonical_store.knowledge_node_groundings','canonical_store.knowledge_edge_applicability_events'] LOOP
        EXECUTE format('CREATE TRIGGER a_knowledge_state BEFORE INSERT OR UPDATE ON %s FOR EACH ROW EXECUTE FUNCTION compiler_runtime.advance_knowledge_state()',relation);
    END LOOP;
    FOREACH relation IN ARRAY ARRAY['canonical_store.knowledge_node_revisions','canonical_store.knowledge_edge_revisions',
        'canonical_store.knowledge_node_groundings','canonical_store.knowledge_edge_applicability_events',
        'compiler_runtime.k_input_information','compiler_runtime.k_input_node_revisions','compiler_runtime.k_outbox',
        'compiler_runtime.k_model_calls','compiler_runtime.k_source_requests'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON %s FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
    END LOOP;
    FOREACH relation IN ARRAY ARRAY['canonical_store.knowledge_nodes','canonical_store.knowledge_edges',
        'compiler_runtime.k_execution_contexts','compiler_runtime.k_compilation_records'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_delete BEFORE DELETE ON %s FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
    END LOOP;
    FOREACH relation IN ARRAY ARRAY['canonical_store.knowledge_nodes','canonical_store.knowledge_node_revisions',
        'canonical_store.knowledge_edges','canonical_store.knowledge_edge_revisions','canonical_store.knowledge_node_groundings',
        'canonical_store.knowledge_edge_applicability_events','compiler_runtime.k_execution_contexts',
        'compiler_runtime.k_compilation_records','compiler_runtime.k_input_information','compiler_runtime.k_input_node_revisions',
        'compiler_runtime.k_outbox','compiler_runtime.k_model_calls','compiler_runtime.k_source_requests','compiler_runtime.knowledge_state'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON %s FOR EACH STATEMENT EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
    END LOOP;
END; $$;
GRANT SELECT,INSERT ON canonical_store.knowledge_node_revisions,canonical_store.knowledge_edge_revisions,
    canonical_store.knowledge_node_groundings,canonical_store.knowledge_edge_applicability_events,
    compiler_runtime.k_input_information,compiler_runtime.k_input_node_revisions,compiler_runtime.k_outbox,
    compiler_runtime.k_model_calls,compiler_runtime.k_source_requests TO palimpsest;
GRANT SELECT,INSERT,UPDATE ON canonical_store.knowledge_nodes,canonical_store.knowledge_edges,
    compiler_runtime.k_execution_contexts,compiler_runtime.k_compilation_records TO palimpsest;
GRANT SELECT,UPDATE ON compiler_runtime.knowledge_state TO palimpsest;
GRANT SELECT,INSERT,DELETE ON compiler_runtime.k_temporary_candidates TO palimpsest;
