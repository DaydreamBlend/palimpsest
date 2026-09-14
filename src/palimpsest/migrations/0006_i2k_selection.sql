-- Source-complete I selection and explicit source/general Knowledge identity.
-- All prior Data, Information, Knowledge IDs, revisions and fingerprints remain unchanged.
CREATE TABLE canonical_store.knowledge_node_scopes (
    knode_id uuid PRIMARY KEY REFERENCES canonical_store.knowledge_nodes,
    identity_scope text NOT NULL CHECK (identity_scope IN ('general','source')),
    source_data_id text REFERENCES canonical_store.data,
    origin_record_id uuid NOT NULL REFERENCES compiler_runtime.k_compilation_records,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((identity_scope='general' AND source_data_id IS NULL)
        OR (identity_scope='source' AND source_data_id IS NOT NULL))
);
ALTER TABLE compiler_runtime.k_compilation_records ADD UNIQUE (record_id,execution_id);
CREATE TABLE compiler_runtime.k_information_reviews (
    execution_id uuid NOT NULL REFERENCES compiler_runtime.k_execution_contexts,
    information_id uuid NOT NULL REFERENCES canonical_store.information,
    disposition text NOT NULL CHECK (disposition IN ('selected','context_only','not_selected','needs_review')),
    reason text NOT NULL CHECK (length(btrim(reason))>0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (execution_id,information_id),
    FOREIGN KEY (execution_id,information_id)
        REFERENCES compiler_runtime.k_input_information(execution_id,information_id)
);
CREATE TABLE compiler_runtime.k_information_review_records (
    execution_id uuid NOT NULL,
    information_id uuid NOT NULL,
    record_id uuid NOT NULL,
    PRIMARY KEY (execution_id,information_id,record_id),
    FOREIGN KEY (execution_id,information_id)
        REFERENCES compiler_runtime.k_information_reviews(execution_id,information_id),
    FOREIGN KEY (record_id,execution_id)
        REFERENCES compiler_runtime.k_compilation_records(record_id,execution_id)
);
CREATE TABLE compiler_runtime.k_information_review_decisions (
    execution_id uuid NOT NULL,
    information_id uuid NOT NULL,
    verdict text NOT NULL CHECK (verdict IN ('confirmed','needs_review')),
    reason_codes jsonb NOT NULL CHECK (jsonb_typeof(reason_codes)='array' AND jsonb_array_length(reason_codes)>0),
    reason text NOT NULL CHECK (length(btrim(reason))>0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (execution_id,information_id),
    FOREIGN KEY (execution_id,information_id)
        REFERENCES compiler_runtime.k_information_reviews(execution_id,information_id)
);

CREATE FUNCTION canonical_store.guard_knowledge_scope() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE node_kind text; execution_data text;
BEGIN
    SELECT kind INTO STRICT node_kind FROM canonical_store.knowledge_nodes WHERE knode_id=NEW.knode_id;
    SELECT e.data_id INTO execution_data FROM compiler_runtime.k_compilation_records r
        JOIN compiler_runtime.operation_executions e USING(execution_id)
        JOIN compiler_runtime.profiles p ON p.profile_id=e.profile_id
        WHERE r.record_id=NEW.origin_record_id AND r.record_type='i2k'
          AND e.state IN ('prepared','proposed','needs_human')
          AND p.payload->>'schema_version'='source-complete-i2k-v1';
    IF execution_data IS NULL
    THEN RAISE EXCEPTION 'Scope binding requires a live validated selection execution'; END IF;
    IF node_kind='observation' AND NEW.identity_scope<>'source'
    THEN RAISE EXCEPTION 'A reported observation must preserve source identity'; END IF;
    IF NEW.identity_scope='source' THEN
        IF NEW.source_data_id IS DISTINCT FROM execution_data OR EXISTS (
            SELECT 1 FROM canonical_store.knowledge_node_revisions v
            JOIN canonical_store.knowledge_node_groundings g ON g.node_revision_id=v.knode_revision_id
            JOIN canonical_store.information i USING(information_id)
            WHERE v.knode_id=NEW.knode_id AND i.data_id<>NEW.source_data_id)
        THEN RAISE EXCEPTION 'Source scope must match the execution and all historical grounding Data'; END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER a_knowledge_state BEFORE INSERT ON canonical_store.knowledge_node_scopes
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.advance_knowledge_state();
CREATE TRIGGER knowledge_scope_guard BEFORE INSERT ON canonical_store.knowledge_node_scopes
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_knowledge_scope();
CREATE FUNCTION canonical_store.check_knowledge_scope_commit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM compiler_runtime.k_compilation_records r
        WHERE r.record_id=NEW.origin_record_id AND r.record_type='i2k' AND r.result_node_id=NEW.knode_id
          AND r.disposition IN ('accepted_new','accepted_revision','reused','no_material_delta')
          AND EXISTS (SELECT 1 FROM canonical_store.knowledge_node_groundings g
              JOIN compiler_runtime.k_input_information x ON x.information_id=g.information_id
              WHERE x.execution_id=r.execution_id AND g.node_revision_id=r.result_node_revision_id))
    THEN RAISE EXCEPTION 'Scope and exact validated Knowledge reuse/creation must commit together'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER knowledge_scope_commit_guard AFTER INSERT ON canonical_store.knowledge_node_scopes
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION canonical_store.check_knowledge_scope_commit();
CREATE FUNCTION canonical_store.guard_scoped_grounding() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM canonical_store.knowledge_node_revisions v
        JOIN canonical_store.knowledge_node_scopes s USING(knode_id)
        JOIN canonical_store.information i ON i.information_id=NEW.information_id
        WHERE v.knode_revision_id=NEW.node_revision_id AND s.identity_scope='source'
          AND s.source_data_id<>i.data_id)
    THEN RAISE EXCEPTION 'Source-scoped Knowledge cannot acquire another Data as equivalent source evidence'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER knowledge_scoped_grounding_guard BEFORE INSERT ON canonical_store.knowledge_node_groundings
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_scoped_grounding();
CREATE FUNCTION compiler_runtime.check_selection_scope_commit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r compiler_runtime.k_compilation_records;
BEGIN
    SELECT * INTO STRICT r FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.record_id;
    IF r.result_node_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM compiler_runtime.operation_executions e
        JOIN compiler_runtime.profiles p ON p.profile_id=e.profile_id
        WHERE e.execution_id=r.execution_id AND p.payload->>'schema_version'='source-complete-i2k-v1')
        AND NOT EXISTS (SELECT 1 FROM canonical_store.knowledge_node_scopes WHERE knode_id=r.result_node_id)
    THEN RAISE EXCEPTION 'Selection Knowledge effects require an immutable identity scope'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER selection_scope_commit_guard AFTER INSERT OR UPDATE ON compiler_runtime.k_compilation_records
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_selection_scope_commit();

CREATE FUNCTION compiler_runtime.guard_information_review() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected_state text;
BEGIN
    expected_state:=CASE WHEN TG_TABLE_NAME='k_information_review_decisions' THEN 'proposed' ELSE 'prepared' END;
    IF NOT EXISTS (SELECT 1 FROM compiler_runtime.operation_executions e
        JOIN compiler_runtime.profiles p ON p.profile_id=e.profile_id
        WHERE e.execution_id=NEW.execution_id AND e.operation='i2k' AND e.state=expected_state
          AND p.payload->>'schema_version'='source-complete-i2k-v1')
    THEN RAISE EXCEPTION 'I selection reviews must be recorded in the matching model phase'; END IF;
    IF TG_TABLE_NAME='k_information_review_records' THEN
        IF NOT EXISTS (SELECT 1 FROM compiler_runtime.k_information_reviews r
            JOIN compiler_runtime.k_compilation_records c ON c.execution_id=r.execution_id
            JOIN compiler_runtime.k_temporary_candidates t ON t.record_id=c.record_id
            WHERE r.execution_id=NEW.execution_id AND r.information_id=NEW.information_id
              AND r.disposition IN ('selected','needs_review') AND c.record_id=NEW.record_id
              AND c.record_type='i2k' AND c.disposition IN ('pending','needs_human')
              AND EXISTS (SELECT 1 FROM jsonb_array_elements(t.body->'evidence') evidence
                  WHERE evidence->>'information_id'=NEW.information_id::text))
        THEN RAISE EXCEPTION 'An I selection link must reference its actual candidate evidence'; END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER information_review_guard BEFORE INSERT ON compiler_runtime.k_information_reviews
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_information_review();
CREATE TRIGGER information_review_record_guard BEFORE INSERT ON compiler_runtime.k_information_review_records
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_information_review();
CREATE TRIGGER information_review_decision_guard BEFORE INSERT ON compiler_runtime.k_information_review_decisions
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_information_review();

CREATE FUNCTION compiler_runtime.check_information_selection_commit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE e compiler_runtime.operation_executions; source_execution uuid;
BEGIN
    SELECT * INTO STRICT e FROM compiler_runtime.operation_executions WHERE execution_id=NEW.execution_id;
    IF e.operation<>'i2k' OR e.state NOT IN ('completed','zero_output') OR NOT EXISTS (
        SELECT 1 FROM compiler_runtime.profiles WHERE profile_id=e.profile_id
        AND payload->>'schema_version'='source-complete-i2k-v1') THEN RETURN NULL; END IF;
    SELECT (input_snapshot->'input'->>'source_execution_id')::uuid INTO source_execution
        FROM compiler_runtime.k_execution_contexts WHERE execution_id=e.execution_id;
    IF source_execution IS NULL OR NOT EXISTS (SELECT 1 FROM compiler_runtime.operation_executions
        WHERE execution_id=source_execution AND operation='d2i' AND state='completed' AND data_id=e.data_id)
    THEN RAISE EXCEPTION 'Complete I selection requires its exact completed source execution'; END IF;
    IF NOT EXISTS (SELECT 1 FROM compiler_runtime.k_input_information WHERE execution_id=e.execution_id)
        OR EXISTS (
            (SELECT i.information_id FROM canonical_store.information i
                JOIN compiler_runtime.records r ON r.record_id=i.origin_record_id WHERE r.execution_id=source_execution
             EXCEPT SELECT information_id FROM compiler_runtime.k_input_information WHERE execution_id=e.execution_id)
            UNION ALL
            (SELECT information_id FROM compiler_runtime.k_input_information WHERE execution_id=e.execution_id
             EXCEPT SELECT i.information_id FROM canonical_store.information i
                JOIN compiler_runtime.records r ON r.record_id=i.origin_record_id WHERE r.execution_id=source_execution))
    THEN RAISE EXCEPTION 'Complete I selection cannot omit or substitute source Information'; END IF;
    IF EXISTS (SELECT 1 FROM compiler_runtime.k_input_information x
        LEFT JOIN compiler_runtime.k_information_reviews r USING(execution_id,information_id)
        LEFT JOIN compiler_runtime.k_information_review_decisions d USING(execution_id,information_id)
        WHERE x.execution_id=e.execution_id AND (r.information_id IS NULL OR d.information_id IS NULL
            OR r.disposition='needs_review' OR d.verdict='needs_review'))
    THEN RAISE EXCEPTION 'Every delivered I needs a resolved Generator and Validator selection review'; END IF;
    IF EXISTS (SELECT 1 FROM compiler_runtime.k_information_reviews r
        WHERE r.execution_id=e.execution_id AND r.disposition='selected' AND NOT EXISTS (
            SELECT 1 FROM compiler_runtime.k_information_review_records l
            WHERE l.execution_id=r.execution_id AND l.information_id=r.information_id))
        OR EXISTS (SELECT 1 FROM compiler_runtime.k_compilation_records r
            WHERE r.execution_id=e.execution_id AND (r.disposition IN ('pending','needs_human') OR NOT EXISTS (
                SELECT 1 FROM compiler_runtime.k_information_review_records l WHERE l.record_id=r.record_id)))
    THEN RAISE EXCEPTION 'Completed selection needs traceable resolved proposals for every selected I'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER information_selection_commit_guard AFTER INSERT OR UPDATE ON compiler_runtime.operation_executions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_information_selection_commit();
DO $$ DECLARE relation text; BEGIN
    FOREACH relation IN ARRAY ARRAY['canonical_store.knowledge_node_scopes','compiler_runtime.k_information_reviews',
        'compiler_runtime.k_information_review_records','compiler_runtime.k_information_review_decisions'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON %s FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
        EXECUTE format('CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON %s FOR EACH STATEMENT EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
    END LOOP;
END; $$;
GRANT SELECT,INSERT ON canonical_store.knowledge_node_scopes,compiler_runtime.k_information_reviews,
    compiler_runtime.k_information_review_records,compiler_runtime.k_information_review_decisions TO palimpsest;
