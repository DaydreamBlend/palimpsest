-- T01 REVIEW DRAFT: apply only to a new, disposable PostgreSQL 18 test database.
-- Not an installed migration chain or a production deployment command.
-- pgvector server binaries must already be installed for this PostgreSQL build.
BEGIN;

DO $$
BEGIN
    IF current_setting('server_version_num')::integer / 10000 <> 18 THEN
        RAISE EXCEPTION 'This initial schema draft requires PostgreSQL major 18';
    END IF;
END;
$$;

-- Observed stable version on 2026-09-09; recheck the approved runtime profile
-- before installation. No IF NOT EXISTS: do not silently accept another layout.
CREATE EXTENSION vector VERSION '0.8.6';
CREATE SCHEMA canonical_store;
CREATE SCHEMA compiler_runtime;

CREATE TABLE canonical_store.data (
    data_id text COLLATE "C" PRIMARY KEY,
    sha256 text GENERATED ALWAYS AS (data_id) STORED,
    media_type text NOT NULL CHECK (length(media_type) > 0),
    byte_size bigint NOT NULL CHECK (byte_size >= 0),
    artifact_path text NOT NULL UNIQUE,
    original_name text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT data_sha256_format CHECK (data_id ~ '^[0-9a-f]{64}$'),
    CONSTRAINT data_artifact_address CHECK (
        artifact_path = 'objects/sha256/' || left(data_id, 2) || '/' || data_id
    )
);

CREATE TABLE canonical_store.data_acquisitions (
    acquisition_id uuid PRIMARY KEY DEFAULT uuidv7(),
    data_id text COLLATE "C" NOT NULL REFERENCES canonical_store.data(data_id),
    origin_uri text,
    import_method text NOT NULL CHECK (length(import_method) > 0),
    retrieved_at timestamptz,
    original_name text,
    external_metadata jsonb,
    actor_ref text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT acquisition_uuidv7 CHECK (uuid_extract_version(acquisition_id) IS NOT DISTINCT FROM 7),
    CONSTRAINT acquisition_metadata_object CHECK (
        external_metadata IS NULL OR jsonb_typeof(external_metadata) = 'object'
    ),
    -- Required for the composite result FK: an acquisition must belong to its Data.
    UNIQUE (acquisition_id, data_id)
);
CREATE INDEX data_acquisitions_data_idx
    ON canonical_store.data_acquisitions (data_id);

-- A prepared import exists after staging/hash verification, before publication.
-- It is durable runtime state, not a public Data or Compiler Record subtype.
CREATE TABLE compiler_runtime.data_import_requests (
    request_id uuid PRIMARY KEY DEFAULT uuidv7(),
    request_fingerprint text COLLATE "C" NOT NULL,
    payload_sha256 text COLLATE "C" NOT NULL,
    byte_size bigint NOT NULL CHECK (byte_size >= 0),
    media_type text NOT NULL CHECK (length(media_type) > 0),
    origin_uri text,
    import_method text NOT NULL CHECK (length(import_method) > 0),
    retrieved_at timestamptz,
    original_name text,
    external_metadata jsonb,
    actor_ref text,
    state text NOT NULL DEFAULT 'staged',
    result_data_id text COLLATE "C" REFERENCES canonical_store.data(data_id),
    result_acquisition_id uuid,
    error_code text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at timestamptz,
    CONSTRAINT import_request_uuidv7 CHECK (uuid_extract_version(request_id) IS NOT DISTINCT FROM 7),
    CONSTRAINT import_request_fp CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
    CONSTRAINT import_payload_sha256 CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT import_metadata_object CHECK (
        external_metadata IS NULL OR jsonb_typeof(external_metadata) = 'object'
    ),
    CONSTRAINT import_state CHECK (state IN ('staged', 'published', 'committed', 'duplicate', 'failed')),
    CONSTRAINT import_result_acquisition FOREIGN KEY (result_acquisition_id, result_data_id)
        REFERENCES canonical_store.data_acquisitions (acquisition_id, data_id),
    CONSTRAINT import_result_matches_payload CHECK (
        result_data_id IS NULL OR result_data_id = payload_sha256
    ),
    CONSTRAINT import_result_state CHECK ((
        (state = 'committed' AND result_data_id IS NOT NULL AND result_acquisition_id IS NOT NULL
            AND error_code IS NULL AND resolved_at IS NOT NULL)
        OR (state = 'duplicate' AND result_data_id IS NOT NULL AND result_acquisition_id IS NULL
            AND error_code = 'duplicate_data' AND resolved_at IS NOT NULL)
        OR (state IN ('staged', 'published') AND result_data_id IS NULL AND result_acquisition_id IS NULL
            AND error_code IS NULL AND resolved_at IS NULL)
        OR (state = 'failed' AND result_data_id IS NULL AND result_acquisition_id IS NULL
            AND error_code IS NOT NULL AND resolved_at IS NOT NULL)
    ) IS TRUE)
);
CREATE INDEX import_requests_recovery_idx
    ON compiler_runtime.data_import_requests (state, created_at)
    WHERE state IN ('staged', 'published', 'failed');

CREATE FUNCTION canonical_store.reject_snapshot_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Immutable snapshot: %.%', TG_TABLE_SCHEMA, TG_TABLE_NAME
        USING ERRCODE = '55000';
END;
$$;

CREATE TRIGGER data_immutable BEFORE UPDATE OR DELETE ON canonical_store.data
    FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation();
CREATE TRIGGER data_no_truncate BEFORE TRUNCATE ON canonical_store.data
    FOR EACH STATEMENT EXECUTE FUNCTION canonical_store.reject_snapshot_mutation();
CREATE TRIGGER acquisitions_append_only BEFORE UPDATE OR DELETE ON canonical_store.data_acquisitions
    FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation();
CREATE TRIGGER acquisitions_no_truncate BEFORE TRUNCATE ON canonical_store.data_acquisitions
    FOR EACH STATEMENT EXECUTE FUNCTION canonical_store.reject_snapshot_mutation();

CREATE FUNCTION compiler_runtime.guard_import_request()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.state <> 'staged' THEN
            RAISE EXCEPTION 'Import must begin in staged state' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;

    IF ROW(NEW.request_id, NEW.request_fingerprint, NEW.payload_sha256, NEW.byte_size,
           NEW.media_type, NEW.origin_uri, NEW.import_method, NEW.retrieved_at,
           NEW.original_name, NEW.external_metadata, NEW.actor_ref, NEW.created_at)
       IS DISTINCT FROM
       ROW(OLD.request_id, OLD.request_fingerprint, OLD.payload_sha256, OLD.byte_size,
           OLD.media_type, OLD.origin_uri, OLD.import_method, OLD.retrieved_at,
           OLD.original_name, OLD.external_metadata, OLD.actor_ref, OLD.created_at) THEN
        RAISE EXCEPTION 'Prepared import input is immutable' USING ERRCODE = '23514';
    END IF;

    IF NOT (
        (OLD.state = 'staged' AND NEW.state IN ('published', 'duplicate', 'failed'))
        OR (OLD.state = 'published' AND NEW.state IN ('committed', 'duplicate', 'failed'))
        OR (OLD.state = 'failed' AND NEW.state = 'staged')
    ) THEN
        RAISE EXCEPTION 'Invalid import transition: % -> %', OLD.state, NEW.state
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER import_request_transition
    BEFORE INSERT OR UPDATE ON compiler_runtime.data_import_requests
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_import_request();
CREATE TRIGGER import_request_no_delete
    BEFORE DELETE ON compiler_runtime.data_import_requests
    FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation();
CREATE TRIGGER import_request_no_truncate
    BEFORE TRUNCATE ON compiler_runtime.data_import_requests
    FOR EACH STATEMENT EXECUTE FUNCTION canonical_store.reject_snapshot_mutation();

REVOKE ALL ON SCHEMA canonical_store, compiler_runtime FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA canonical_store, compiler_runtime FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA canonical_store, compiler_runtime FROM PUBLIC;
COMMIT;
