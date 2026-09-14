-- Additive multi-source, explicit-content-only I2K. Historical rows are unchanged.
CREATE TABLE compiler_runtime.k_execution_sources (
    execution_id uuid NOT NULL REFERENCES compiler_runtime.k_execution_contexts,
    ordinal integer NOT NULL CHECK (ordinal>=0),
    data_id text NOT NULL REFERENCES canonical_store.data,
    source_execution_id uuid NOT NULL REFERENCES compiler_runtime.operation_executions,
    input_sha256 text NOT NULL CHECK (input_sha256 ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY(execution_id,source_execution_id),
    UNIQUE(execution_id,data_id), UNIQUE(execution_id,ordinal)
);
CREATE TABLE compiler_runtime.k_explicit_source_decisions (
    record_id uuid PRIMARY KEY REFERENCES compiler_runtime.k_compilation_records,
    identity_scope text NOT NULL CHECK (identity_scope IN ('general','source')),
    source_data_id text REFERENCES canonical_store.data,
    source_explicit boolean NOT NULL,
    no_novel_inference boolean NOT NULL,
    source_identity_preserved boolean NOT NULL,
    CHECK ((identity_scope='general' AND source_data_id IS NULL)
        OR (identity_scope='source' AND source_data_id IS NOT NULL))
);
CREATE FUNCTION compiler_runtime.is_multi_source_i2k(id uuid) RETURNS boolean
LANGUAGE sql STABLE AS $$
    SELECT EXISTS (SELECT 1 FROM compiler_runtime.operation_executions e
        JOIN compiler_runtime.profiles p USING(profile_id)
        WHERE e.execution_id=id AND e.operation='i2k'
          AND p.payload->>'schema_version'='multi-source-explicit-i2k-v1')
$$;
CREATE FUNCTION compiler_runtime.guard_k_execution_source() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT compiler_runtime.is_multi_source_i2k(NEW.execution_id) OR NOT EXISTS (
        SELECT 1 FROM compiler_runtime.operation_executions e
        JOIN compiler_runtime.k_execution_contexts c USING(execution_id)
        JOIN compiler_runtime.operation_executions s ON s.execution_id=NEW.source_execution_id
        WHERE e.execution_id=NEW.execution_id AND e.state='prepared'
          AND s.operation='d2i' AND s.state='completed' AND s.data_id=NEW.data_id
          AND c.input_snapshot->'input'->'sources'->NEW.ordinal->>'data_id'=NEW.data_id
          AND c.input_snapshot->'input'->'sources'->NEW.ordinal->>'source_execution_id'=NEW.source_execution_id::text
          AND c.input_snapshot->'input'->'sources'->NEW.ordinal->>'input_sha256'=NEW.input_sha256)
    THEN RAISE EXCEPTION 'Multi-source inputs must bind the exact frozen completed source snapshots'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER k_execution_source_guard BEFORE INSERT ON compiler_runtime.k_execution_sources
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_k_execution_source();

CREATE OR REPLACE FUNCTION compiler_runtime.guard_k_input() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM compiler_runtime.operation_executions e
        WHERE e.execution_id=NEW.execution_id AND e.state='prepared'
          AND e.operation=CASE WHEN TG_TABLE_NAME='k_input_information' THEN 'i2k' ELSE 'n2e' END)
    THEN RAISE EXCEPTION 'Authoritative K inputs are frozen before model execution'; END IF;
    IF TG_TABLE_NAME='k_input_information' THEN
        IF compiler_runtime.is_multi_source_i2k(NEW.execution_id) THEN
            IF NOT EXISTS (SELECT 1 FROM compiler_runtime.k_execution_sources s
                JOIN compiler_runtime.records r ON r.execution_id=s.source_execution_id
                JOIN canonical_store.information i ON i.origin_record_id=r.record_id AND i.data_id=s.data_id
                WHERE s.execution_id=NEW.execution_id AND i.information_id=NEW.information_id)
            THEN RAISE EXCEPTION 'Information must belong to one frozen multi-source snapshot'; END IF;
        ELSIF NOT EXISTS (SELECT 1 FROM canonical_store.information i
            JOIN compiler_runtime.operation_executions e ON e.data_id=i.data_id
            WHERE e.execution_id=NEW.execution_id AND i.information_id=NEW.information_id)
        THEN RAISE EXCEPTION 'This first I2K profile accepts only its registered Data'; END IF;
    END IF;
    RETURN NEW;
END; $$;

CREATE FUNCTION compiler_runtime.guard_explicit_source_decision() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r compiler_runtime.k_compilation_records; candidate jsonb;
BEGIN
    SELECT * INTO STRICT r FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.record_id;
    SELECT body INTO candidate FROM compiler_runtime.k_temporary_candidates WHERE record_id=NEW.record_id;
    IF NOT compiler_runtime.is_multi_source_i2k(r.execution_id) OR NOT EXISTS (
        SELECT 1 FROM compiler_runtime.operation_executions WHERE execution_id=r.execution_id AND state='proposed')
        OR r.record_type<>'i2k' OR candidate IS NULL
        OR candidate->>'claim_basis' IS DISTINCT FROM 'explicit_source_content'
        OR candidate->'is_inferred' IS DISTINCT FROM 'false'::jsonb
        OR candidate->>'identity_scope' IS DISTINCT FROM NEW.identity_scope
        OR candidate->>'source_data_id' IS DISTINCT FROM NEW.source_data_id
    THEN RAISE EXCEPTION 'Explicit-source validation must bind the actual I2K proposal'; END IF;
    IF NEW.source_data_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM jsonb_array_elements(candidate->'evidence') v
        JOIN canonical_store.information i ON i.information_id=(v->>'information_id')::uuid
        JOIN compiler_runtime.k_input_information x ON x.information_id=i.information_id
        WHERE x.execution_id=r.execution_id AND i.data_id=NEW.source_data_id)
    THEN RAISE EXCEPTION 'A source claim needs actual evidence from its attributed experiment Data'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER explicit_source_decision_guard BEFORE INSERT ON compiler_runtime.k_explicit_source_decisions
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_explicit_source_decision();

CREATE OR REPLACE FUNCTION canonical_store.guard_knowledge_scope() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE node_kind text; execution_data text; execution uuid; multi boolean;
BEGIN
    SELECT kind INTO STRICT node_kind FROM canonical_store.knowledge_nodes WHERE knode_id=NEW.knode_id;
    SELECT e.data_id,e.execution_id INTO execution_data,execution FROM compiler_runtime.k_compilation_records r
        JOIN compiler_runtime.operation_executions e USING(execution_id)
        JOIN compiler_runtime.profiles p ON p.profile_id=e.profile_id
        WHERE r.record_id=NEW.origin_record_id AND r.record_type='i2k'
          AND e.state IN ('prepared','proposed','needs_human')
          AND p.payload->>'schema_version' IN ('source-complete-i2k-v1','multi-source-explicit-i2k-v1');
    IF execution_data IS NULL
    THEN RAISE EXCEPTION 'Scope binding requires a live validated selection execution'; END IF;
    IF node_kind='observation' AND NEW.identity_scope<>'source'
    THEN RAISE EXCEPTION 'A reported observation must preserve source identity'; END IF;
    multi:=compiler_runtime.is_multi_source_i2k(execution);
    IF multi THEN
        IF NOT EXISTS (SELECT 1 FROM compiler_runtime.k_explicit_source_decisions d
            WHERE d.record_id=NEW.origin_record_id AND d.identity_scope=NEW.identity_scope
              AND d.source_data_id IS NOT DISTINCT FROM NEW.source_data_id
              AND d.source_explicit AND d.no_novel_inference AND d.source_identity_preserved)
        THEN RAISE EXCEPTION 'Multi-source scope needs explicit source and attribution validation'; END IF;
    ELSIF NEW.identity_scope='source' THEN
        IF NEW.source_data_id IS DISTINCT FROM execution_data OR EXISTS (
            SELECT 1 FROM canonical_store.knowledge_node_revisions v
            JOIN canonical_store.knowledge_node_groundings g ON g.node_revision_id=v.knode_revision_id
            JOIN canonical_store.information i USING(information_id)
            WHERE v.knode_id=NEW.knode_id AND i.data_id<>NEW.source_data_id)
        THEN RAISE EXCEPTION 'Source scope must match the execution and all historical grounding Data'; END IF;
    END IF;
    RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION canonical_store.guard_scoped_grounding() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner text; execution uuid;
BEGIN
    SELECT s.source_data_id INTO owner FROM canonical_store.knowledge_node_revisions v
        JOIN canonical_store.knowledge_node_scopes s USING(knode_id)
        WHERE v.knode_revision_id=NEW.node_revision_id AND s.identity_scope='source';
    IF owner IS NOT NULL AND owner IS DISTINCT FROM (SELECT data_id FROM canonical_store.information WHERE information_id=NEW.information_id) THEN
        SELECT execution_id INTO execution FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.origin_record_id;
        IF NOT compiler_runtime.is_multi_source_i2k(execution) OR NOT EXISTS (
            SELECT 1 FROM compiler_runtime.k_explicit_source_decisions d
            WHERE d.record_id=NEW.origin_record_id AND d.identity_scope='source' AND d.source_data_id=owner
              AND d.source_explicit AND d.no_novel_inference AND d.source_identity_preserved)
        THEN RAISE EXCEPTION 'Source-scoped Knowledge needs validated same-experiment supplemental evidence'; END IF;
    END IF;
    RETURN NEW;
END; $$;

CREATE FUNCTION compiler_runtime.check_multi_explicit_commit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r compiler_runtime.k_compilation_records;
BEGIN
    SELECT * INTO STRICT r FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.record_id;
    IF compiler_runtime.is_multi_source_i2k(r.execution_id) AND r.result_node_id IS NOT NULL THEN
        IF NOT EXISTS (SELECT 1 FROM compiler_runtime.k_explicit_source_decisions d
            JOIN canonical_store.knowledge_node_scopes s ON s.knode_id=r.result_node_id
            WHERE d.record_id=r.record_id AND d.source_explicit AND d.no_novel_inference AND d.source_identity_preserved
              AND d.identity_scope=s.identity_scope AND d.source_data_id IS NOT DISTINCT FROM s.source_data_id
              AND (d.source_data_id IS NULL OR EXISTS (
                  SELECT 1 FROM canonical_store.knowledge_node_groundings g
                  JOIN canonical_store.information i USING(information_id)
                  JOIN compiler_runtime.k_input_information x ON x.information_id=i.information_id
                  WHERE g.node_revision_id=r.result_node_revision_id AND x.execution_id=r.execution_id
                    AND i.data_id=d.source_data_id)))
        THEN RAISE EXCEPTION 'I2K publication requires source-explicit, non-inferred, scope-preserving validation'; END IF;
    END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER multi_explicit_commit_guard AFTER INSERT OR UPDATE ON compiler_runtime.k_compilation_records
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_multi_explicit_commit();

CREATE FUNCTION compiler_runtime.check_multi_source_selection(id uuid) RETURNS void LANGUAGE plpgsql AS $$
DECLARE e compiler_runtime.operation_executions;
BEGIN
    SELECT * INTO STRICT e FROM compiler_runtime.operation_executions WHERE execution_id=id;
    IF e.state NOT IN ('completed','zero_output') THEN RETURN; END IF;
    IF NOT EXISTS (SELECT 1 FROM compiler_runtime.k_execution_sources WHERE execution_id=id)
       OR (SELECT count(*) FROM compiler_runtime.k_execution_sources WHERE execution_id=id) IS DISTINCT FROM
          (SELECT jsonb_array_length(input_snapshot->'input'->'sources') FROM compiler_runtime.k_execution_contexts WHERE execution_id=id)
       OR EXISTS (SELECT 1 FROM compiler_runtime.k_execution_sources s
          JOIN compiler_runtime.operation_executions d ON d.execution_id=s.source_execution_id
          WHERE s.execution_id=id AND (d.operation<>'d2i' OR d.state<>'completed' OR d.data_id<>s.data_id))
    THEN RAISE EXCEPTION 'Multi-source completion needs every frozen completed source'; END IF;
    IF NOT EXISTS (SELECT 1 FROM compiler_runtime.k_input_information WHERE execution_id=id) OR EXISTS (
        (SELECT i.information_id FROM canonical_store.information i
            JOIN compiler_runtime.records r ON r.record_id=i.origin_record_id
            JOIN compiler_runtime.k_execution_sources s ON s.source_execution_id=r.execution_id WHERE s.execution_id=id
         EXCEPT SELECT information_id FROM compiler_runtime.k_input_information WHERE execution_id=id)
        UNION ALL
        (SELECT information_id FROM compiler_runtime.k_input_information WHERE execution_id=id
         EXCEPT SELECT i.information_id FROM canonical_store.information i
            JOIN compiler_runtime.records r ON r.record_id=i.origin_record_id
            JOIN compiler_runtime.k_execution_sources s ON s.source_execution_id=r.execution_id WHERE s.execution_id=id))
    THEN RAISE EXCEPTION 'Every selected source Information must enter the multi-source review'; END IF;
    IF EXISTS (SELECT 1 FROM compiler_runtime.k_input_information x
        LEFT JOIN compiler_runtime.k_information_reviews r USING(execution_id,information_id)
        LEFT JOIN compiler_runtime.k_information_review_decisions d USING(execution_id,information_id)
        WHERE x.execution_id=id AND (r.information_id IS NULL OR d.information_id IS NULL
            OR r.disposition='needs_review' OR d.verdict='needs_review'))
    THEN RAISE EXCEPTION 'Every multi-source I requires resolved independent reviews'; END IF;
    IF EXISTS (SELECT 1 FROM compiler_runtime.k_information_reviews r WHERE r.execution_id=id AND r.disposition='selected'
        AND NOT EXISTS (SELECT 1 FROM compiler_runtime.k_information_review_records l
            WHERE l.execution_id=r.execution_id AND l.information_id=r.information_id))
       OR EXISTS (SELECT 1 FROM compiler_runtime.k_compilation_records r WHERE r.execution_id=id
           AND (r.disposition IN ('pending','needs_human') OR NOT EXISTS (
                SELECT 1 FROM compiler_runtime.k_information_review_records l WHERE l.record_id=r.record_id)))
    THEN RAISE EXCEPTION 'Multi-source selection needs traceable resolved proposals'; END IF;
END; $$;

DO $$ DECLARE relation text; BEGIN
    FOREACH relation IN ARRAY ARRAY['compiler_runtime.k_execution_sources','compiler_runtime.k_explicit_source_decisions'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON %s FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
        EXECUTE format('CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON %s FOR EACH STATEMENT EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
    END LOOP;
END; $$;
GRANT SELECT,INSERT ON compiler_runtime.k_execution_sources,compiler_runtime.k_explicit_source_decisions TO palimpsest;


CREATE OR REPLACE FUNCTION compiler_runtime.guard_information_review() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected_state text;
BEGIN
    expected_state:=CASE WHEN TG_TABLE_NAME='k_information_review_decisions' THEN 'proposed' ELSE 'prepared' END;
    IF NOT EXISTS (SELECT 1 FROM compiler_runtime.operation_executions e
        JOIN compiler_runtime.profiles p ON p.profile_id=e.profile_id
        WHERE e.execution_id=NEW.execution_id AND e.operation='i2k' AND e.state=expected_state
          AND p.payload->>'schema_version' IN ('source-complete-i2k-v1','multi-source-explicit-i2k-v1'))
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


CREATE OR REPLACE FUNCTION compiler_runtime.check_information_selection_commit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE e compiler_runtime.operation_executions; source_execution uuid;
BEGIN
    IF compiler_runtime.is_multi_source_i2k(NEW.execution_id) THEN
        PERFORM compiler_runtime.check_multi_source_selection(NEW.execution_id);
        RETURN NULL;
    END IF;
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
