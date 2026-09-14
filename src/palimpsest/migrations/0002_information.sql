-- T03: validated, source-specific Information and durable D2I execution.
-- Existing 0001_data and its identities are untouched.
CREATE TABLE compiler_runtime.profiles (
    profile_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(profile_id) IS NOT DISTINCT FROM 7),
    profile_hash text NOT NULL UNIQUE CHECK (profile_hash ~ '^[0-9a-f]{64}$'),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE compiler_runtime.operation_executions (
    execution_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(execution_id) IS NOT DISTINCT FROM 7),
    operation text NOT NULL CHECK (operation='d2i'),
    data_id text NOT NULL REFERENCES canonical_store.data,
    profile_id uuid NOT NULL REFERENCES compiler_runtime.profiles,
    generation integer NOT NULL CHECK (generation>0),
    state text NOT NULL DEFAULT 'prepared' CHECK (state IN
        ('prepared','parsed','proposed','completed','zero_output','needs_human','failed')),
    attempt integer NOT NULL DEFAULT 1 CHECK (attempt>0),
    error_code text,
    generator_receipt jsonb,
    validator_receipt jsonb,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (operation,data_id,profile_id,generation),
    UNIQUE (execution_id,data_id),
    CHECK ((state='failed')=(error_code IS NOT NULL))
);
CREATE TABLE compiler_runtime.parse_artifacts (
    parse_artifact_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(parse_artifact_id) IS NOT DISTINCT FROM 7),
    execution_id uuid NOT NULL UNIQUE,
    data_id text NOT NULL,
    manifest_hash text NOT NULL CHECK (manifest_hash ~ '^[0-9a-f]{64}$'),
    artifact_path text NOT NULL,
    manifest jsonb NOT NULL CHECK (jsonb_typeof(manifest)='object'),
    bundle jsonb NOT NULL CHECK (jsonb_typeof(bundle)='object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (execution_id,data_id) REFERENCES compiler_runtime.operation_executions(execution_id,data_id),
    UNIQUE (parse_artifact_id,data_id)
);
CREATE TABLE compiler_runtime.execution_events (
    event_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(event_id) IS NOT DISTINCT FROM 7),
    execution_id uuid NOT NULL REFERENCES compiler_runtime.operation_executions,
    attempt integer NOT NULL CHECK (attempt>0),
    state text NOT NULL,
    error_code text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE compiler_runtime.records (
    record_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(record_id) IS NOT DISTINCT FROM 7),
    subtype text NOT NULL CHECK (subtype='D2IRecord'),
    execution_id uuid NOT NULL,
    data_id text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal>=0),
    identity_fingerprint text NOT NULL CHECK (identity_fingerprint ~ '^[0-9a-f]{64}$'),
    content_fingerprint text NOT NULL CHECK (content_fingerprint ~ '^[0-9a-f]{64}$'),
    context_fingerprint text NOT NULL CHECK (context_fingerprint ~ '^[0-9a-f]{64}$'),
    disposition text CHECK (disposition IN ('accepted','rejected','needs_human')),
    reason_codes jsonb,
    result_information_id uuid,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at timestamptz,
    UNIQUE (execution_id,ordinal), UNIQUE (record_id,data_id),
    FOREIGN KEY (execution_id,data_id) REFERENCES compiler_runtime.operation_executions(execution_id,data_id),
    CHECK ((disposition IN ('accepted','rejected')) IS NOT DISTINCT FROM (resolved_at IS NOT NULL)
        OR (disposition IS NULL AND resolved_at IS NULL)),
    CHECK ((disposition IS NOT DISTINCT FROM 'accepted')=(result_information_id IS NOT NULL))
);
CREATE TABLE compiler_runtime.temporary_candidates (
    record_id uuid PRIMARY KEY REFERENCES compiler_runtime.records,
    body jsonb NOT NULL CHECK (jsonb_typeof(body)='object')
);
CREATE TABLE canonical_store.information (
    information_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(information_id) IS NOT DISTINCT FROM 7),
    data_id text NOT NULL REFERENCES canonical_store.data,
    origin_record_id uuid NOT NULL UNIQUE,
    kind text NOT NULL CHECK (kind IN ('text','image')),
    semantic_type text NOT NULL CHECK (semantic_type IN ('proposition','observation','procedure','definition','figure')),
    title text NOT NULL CHECK (length(title)>0),
    content text NOT NULL CHECK (length(content)>0),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
    identity_fingerprint text NOT NULL CHECK (identity_fingerprint ~ '^[0-9a-f]{64}$'),
    content_fingerprint text NOT NULL CHECK (content_fingerprint ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (information_id,data_id),
    FOREIGN KEY (origin_record_id,data_id) REFERENCES compiler_runtime.records(record_id,data_id)
        DEFERRABLE INITIALLY DEFERRED
);
ALTER TABLE compiler_runtime.records ADD FOREIGN KEY (result_information_id,data_id)
    REFERENCES canonical_store.information(information_id,data_id) DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE canonical_store.information_groundings (
    grounding_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(grounding_id) IS NOT DISTINCT FROM 7),
    information_id uuid NOT NULL,
    data_id text NOT NULL,
    parse_artifact_id uuid NOT NULL,
    block_id text NOT NULL,
    page_index integer NOT NULL CHECK (page_index>=0),
    bbox jsonb NOT NULL CHECK (jsonb_typeof(bbox)='array' AND jsonb_array_length(bbox)=4),
    page_size jsonb NOT NULL CHECK (jsonb_typeof(page_size)='array' AND jsonb_array_length(page_size)=2),
    raw_locator text NOT NULL CHECK (length(raw_locator)>0),
    anchor_sha256 text NOT NULL CHECK (anchor_sha256 ~ '^[0-9a-f]{64}$'),
    FOREIGN KEY (information_id,data_id) REFERENCES canonical_store.information(information_id,data_id),
    FOREIGN KEY (parse_artifact_id,data_id) REFERENCES compiler_runtime.parse_artifacts(parse_artifact_id,data_id),
    UNIQUE (information_id,block_id)
);
CREATE TABLE compiler_runtime.outbox (
    event_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(event_id) IS NOT DISTINCT FROM 7),
    record_id uuid NOT NULL UNIQUE REFERENCES compiler_runtime.records,
    information_id uuid NOT NULL UNIQUE REFERENCES canonical_store.information,
    operation text NOT NULL CHECK (operation='i2k'),
    state text NOT NULL DEFAULT 'pending' CHECK (state='pending'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX information_data_idx ON canonical_store.information(data_id);
CREATE INDEX records_rejected_fp_idx ON compiler_runtime.records
    (data_id,identity_fingerprint,content_fingerprint,context_fingerprint) WHERE disposition='rejected';

CREATE FUNCTION compiler_runtime.guard_execution() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.execution_id,NEW.operation,NEW.data_id,NEW.profile_id,NEW.generation,NEW.created_at)
       IS DISTINCT FROM (OLD.execution_id,OLD.operation,OLD.data_id,OLD.profile_id,OLD.generation,OLD.created_at)
       OR OLD.state IN ('completed','zero_output') THEN
        RAISE EXCEPTION 'Execution input and completed results are immutable';
    END IF;
    IF OLD.generator_receipt IS NOT NULL AND NEW.generator_receipt IS DISTINCT FROM OLD.generator_receipt THEN
        RAISE EXCEPTION 'Generator receipt is frozen';
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER execution_guard BEFORE UPDATE ON compiler_runtime.operation_executions
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_execution();
CREATE FUNCTION compiler_runtime.guard_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.disposition IN ('accepted','rejected') OR
       (to_jsonb(NEW)-ARRAY['disposition','reason_codes','result_information_id','resolved_at'])
       IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['disposition','reason_codes','result_information_id','resolved_at']) THEN
        RAISE EXCEPTION 'Record inputs and terminal disposition are immutable';
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER record_guard BEFORE UPDATE ON compiler_runtime.records
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_record();
CREATE FUNCTION canonical_store.guard_grounding_insert() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM canonical_store.information i
        JOIN compiler_runtime.records r ON r.record_id=i.origin_record_id
        JOIN compiler_runtime.parse_artifacts p ON p.execution_id=r.execution_id AND p.data_id=i.data_id,
        LATERAL jsonb_array_elements(p.bundle->'blocks') b
        WHERE i.information_id=NEW.information_id AND r.disposition IS NULL
          AND p.parse_artifact_id=NEW.parse_artifact_id AND p.data_id=NEW.data_id
          AND b->>'block_id'=NEW.block_id AND (b->>'page_index')::integer=NEW.page_index
          AND b->'bbox'=NEW.bbox AND b->'page_size'=NEW.page_size
          AND b->>'raw_locator'=NEW.raw_locator AND b->>'anchor_sha256'=NEW.anchor_sha256
    ) THEN RAISE EXCEPTION 'Grounding must match the original execution block before acceptance'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER grounding_insert_guard BEFORE INSERT ON canonical_store.information_groundings
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_grounding_insert();
CREATE FUNCTION compiler_runtime.guard_candidate_insert() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM compiler_runtime.records WHERE record_id=NEW.record_id AND disposition IS NULL)
    THEN RAISE EXCEPTION 'A terminal Record cannot receive new candidate content'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER candidate_insert_guard BEFORE INSERT ON compiler_runtime.temporary_candidates
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_candidate_insert();
CREATE FUNCTION canonical_store.check_information_commit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM canonical_store.information_groundings WHERE information_id=NEW.information_id)
       OR NOT EXISTS (SELECT 1 FROM compiler_runtime.records WHERE record_id=NEW.origin_record_id
           AND disposition='accepted' AND result_information_id=NEW.information_id)
       OR EXISTS (SELECT 1 FROM compiler_runtime.temporary_candidates WHERE record_id=NEW.origin_record_id)
       OR NOT EXISTS (SELECT 1 FROM compiler_runtime.outbox WHERE record_id=NEW.origin_record_id
           AND information_id=NEW.information_id) THEN
        RAISE EXCEPTION 'Information, grounding, accepted Record, cleanup and outbox must commit together';
    END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER information_commit_guard AFTER INSERT ON canonical_store.information
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION canonical_store.check_information_commit();
DO $$ DECLARE relation text; BEGIN
    FOREACH relation IN ARRAY ARRAY['canonical_store.information','canonical_store.information_groundings',
        'compiler_runtime.profiles','compiler_runtime.parse_artifacts','compiler_runtime.outbox',
        'compiler_runtime.execution_events'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON %s FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
        EXECUTE format('CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON %s FOR EACH STATEMENT EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
    END LOOP;
END; $$;
GRANT SELECT,INSERT ON compiler_runtime.profiles,compiler_runtime.parse_artifacts,
    canonical_store.information,canonical_store.information_groundings,compiler_runtime.outbox,
    compiler_runtime.execution_events TO palimpsest;
GRANT SELECT,INSERT,UPDATE ON compiler_runtime.operation_executions,compiler_runtime.records TO palimpsest;
GRANT SELECT,INSERT,DELETE ON compiler_runtime.temporary_candidates TO palimpsest;
