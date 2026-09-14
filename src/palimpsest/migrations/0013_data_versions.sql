-- Version history names exact immutable Data; storage representation stays separate.
-- No existing Data, Information, revision, source receipt or artifact is rewritten.
CREATE TABLE canonical_store.data_series (
    series_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(series_id) IS NOT DISTINCT FROM 7),
    name text NOT NULL CHECK (length(btrim(name))>0),
    actor_ref text NOT NULL CHECK (length(btrim(actor_ref))>0),
    head_version_id uuid,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE canonical_store.data_versions (
    version_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(version_id) IS NOT DISTINCT FROM 7),
    series_id uuid NOT NULL REFERENCES canonical_store.data_series,
    parent_version_id uuid,
    data_id text NOT NULL REFERENCES canonical_store.data,
    version_number bigint NOT NULL CHECK (version_number>0),
    title text NOT NULL DEFAULT '',
    message text NOT NULL DEFAULT '',
    actor_ref text NOT NULL CHECK (length(btrim(actor_ref))>0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(version_id,series_id), UNIQUE(series_id,version_number),
    FOREIGN KEY(parent_version_id,series_id) REFERENCES canonical_store.data_versions(version_id,series_id),
    CHECK (parent_version_id IS DISTINCT FROM version_id)
);
ALTER TABLE canonical_store.data_series ADD FOREIGN KEY(head_version_id,series_id)
    REFERENCES canonical_store.data_versions(version_id,series_id) DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX data_version_content ON canonical_store.data_versions(data_id);

CREATE TABLE compiler_runtime.data_version_requests (
    request_id uuid PRIMARY KEY CHECK (uuid_extract_version(request_id) IS NOT DISTINCT FROM 7),
    request_fingerprint text NOT NULL CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
    operation text NOT NULL CHECK (operation IN ('create','append')),
    series_id uuid NOT NULL REFERENCES canonical_store.data_series,
    expected_head uuid,
    data_id text REFERENCES canonical_store.data,
    actor_ref text NOT NULL CHECK (length(btrim(actor_ref))>0),
    result_version_id uuid,
    outcome text NOT NULL CHECK (outcome IN ('created','no_op')),
    request_payload jsonb NOT NULL CHECK (jsonb_typeof(request_payload)='object'),
    result jsonb NOT NULL CHECK (jsonb_typeof(result)='object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(expected_head,series_id) REFERENCES canonical_store.data_versions(version_id,series_id),
    FOREIGN KEY(result_version_id,series_id) REFERENCES canonical_store.data_versions(version_id,series_id),
    CHECK ((operation='create' AND expected_head IS NULL AND data_id IS NULL
                AND result_version_id IS NULL AND outcome='created')
        OR (operation='append' AND data_id IS NOT NULL AND result_version_id IS NOT NULL))
);
CREATE UNIQUE INDEX data_series_creation_request ON compiler_runtime.data_version_requests(series_id)
    WHERE operation='create';
CREATE UNIQUE INDEX data_version_creation_request ON compiler_runtime.data_version_requests(result_version_id)
    WHERE operation='append' AND outcome='created';

CREATE FUNCTION canonical_store.guard_data_series() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='INSERT' THEN
        IF NEW.head_version_id IS NOT NULL THEN RAISE EXCEPTION 'A new Data series starts without a version'; END IF;
    ELSE
        IF to_jsonb(NEW)-'head_version_id' IS DISTINCT FROM to_jsonb(OLD)-'head_version_id'
        THEN RAISE EXCEPTION 'Data series identity and creator are immutable'; END IF;
        IF NEW.head_version_id IS DISTINCT FROM OLD.head_version_id AND NOT EXISTS(
            SELECT 1 FROM canonical_store.data_versions v WHERE v.version_id=NEW.head_version_id
                AND v.series_id=NEW.series_id AND v.parent_version_id IS NOT DISTINCT FROM OLD.head_version_id)
        THEN RAISE EXCEPTION 'Data head moves only to a newly appended direct successor'; END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER data_series_guard BEFORE INSERT OR UPDATE ON canonical_store.data_series
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_data_series();
CREATE FUNCTION canonical_store.guard_data_version() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE series canonical_store.data_series; parent canonical_store.data_versions;
BEGIN
    SELECT * INTO STRICT series FROM canonical_store.data_series WHERE series_id=NEW.series_id FOR UPDATE;
    IF NEW.actor_ref IS DISTINCT FROM series.actor_ref OR NEW.parent_version_id IS DISTINCT FROM series.head_version_id
    THEN RAISE EXCEPTION 'Data version must retain its creator and expected series head'; END IF;
    IF series.head_version_id IS NULL THEN
        IF NEW.version_number<>1 THEN RAISE EXCEPTION 'The first Data version number is one'; END IF;
    ELSE
        SELECT * INTO STRICT parent FROM canonical_store.data_versions WHERE version_id=series.head_version_id;
        IF NEW.version_number<>parent.version_number+1 OR NEW.data_id=parent.data_id
        THEN RAISE EXCEPTION 'Data versions append sequentially; unchanged head content is a no-op'; END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER data_version_guard BEFORE INSERT ON canonical_store.data_versions
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_data_version();

CREATE FUNCTION compiler_runtime.guard_data_version_request() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE series canonical_store.data_series; version canonical_store.data_versions;
BEGIN
    SELECT * INTO STRICT series FROM canonical_store.data_series WHERE series_id=NEW.series_id;
    IF NEW.actor_ref IS DISTINCT FROM series.actor_ref
        OR NEW.request_payload->>'operation' IS DISTINCT FROM NEW.operation
        OR NEW.request_payload->>'actor_ref' IS DISTINCT FROM NEW.actor_ref
        OR NEW.result->>'request_id' IS DISTINCT FROM NEW.request_id::text
        OR NEW.result->>'series_id' IS DISTINCT FROM NEW.series_id::text
        OR NEW.result->>'actor_ref' IS DISTINCT FROM NEW.actor_ref
        OR NEW.result->>'outcome' IS DISTINCT FROM NEW.outcome
    THEN RAISE EXCEPTION 'Version request must bind its actor and exact result'; END IF;
    IF NEW.operation='create' THEN
        IF series.head_version_id IS NOT NULL OR NEW.request_payload->>'name' IS DISTINCT FROM series.name
            OR NEW.result->>'name' IS DISTINCT FROM series.name
        THEN RAISE EXCEPTION 'Series creation receipt must match the new empty series'; END IF;
    ELSE
        SELECT * INTO STRICT version FROM canonical_store.data_versions WHERE version_id=NEW.result_version_id;
        IF version.data_id IS DISTINCT FROM NEW.data_id OR version.version_id IS DISTINCT FROM series.head_version_id
            OR NEW.request_payload->>'series_id' IS DISTINCT FROM NEW.series_id::text
            OR NEW.request_payload->>'data_id' IS DISTINCT FROM NEW.data_id
            OR NEW.request_payload->>'expected_head' IS DISTINCT FROM NEW.expected_head::text
            OR NEW.result->>'version_id' IS DISTINCT FROM version.version_id::text
            OR NEW.result->>'data_id' IS DISTINCT FROM version.data_id
            OR NEW.result->>'parent_version_id' IS DISTINCT FROM version.parent_version_id::text
            OR NEW.result->'version_number' IS DISTINCT FROM to_jsonb(version.version_number)
            OR NEW.result->>'actor_ref' IS DISTINCT FROM version.actor_ref
            OR NEW.result->>'title' IS DISTINCT FROM version.title
            OR NEW.result->>'message' IS DISTINCT FROM version.message
            OR (NEW.outcome='created' AND version.parent_version_id IS DISTINCT FROM NEW.expected_head)
            OR (NEW.outcome='created' AND (version.title IS DISTINCT FROM NEW.request_payload->>'title'
                OR version.message IS DISTINCT FROM NEW.request_payload->>'message'))
            OR (NEW.outcome='no_op' AND NEW.result_version_id IS DISTINCT FROM NEW.expected_head)
        THEN RAISE EXCEPTION 'Append receipt must match the original CAS request and resulting version'; END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER data_version_request_guard BEFORE INSERT ON compiler_runtime.data_version_requests
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_data_version_request();

CREATE FUNCTION canonical_store.check_data_series_creation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM compiler_runtime.data_version_requests
        WHERE series_id=NEW.series_id AND operation='create' AND actor_ref=NEW.actor_ref)
    THEN RAISE EXCEPTION 'Data series and its durable creation request must commit together'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER data_series_creation_guard AFTER INSERT ON canonical_store.data_series
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION canonical_store.check_data_series_creation();
CREATE FUNCTION canonical_store.check_data_version_commit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM compiler_runtime.data_version_requests
        WHERE result_version_id=NEW.version_id AND operation='append' AND outcome='created'
            AND data_id=NEW.data_id AND actor_ref=NEW.actor_ref)
        OR NOT EXISTS(WITH RECURSIVE chain(version_id,parent_version_id) AS (
            SELECT v.version_id,v.parent_version_id FROM canonical_store.data_series s
            JOIN canonical_store.data_versions v ON v.version_id=s.head_version_id WHERE s.series_id=NEW.series_id
            UNION SELECT v.version_id,v.parent_version_id FROM chain c
            JOIN canonical_store.data_versions v ON v.version_id=c.parent_version_id)
            SELECT 1 FROM chain WHERE version_id=NEW.version_id)
    THEN RAISE EXCEPTION 'A Data version, head publication and creation receipt must commit together'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER data_version_commit_guard AFTER INSERT ON canonical_store.data_versions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION canonical_store.check_data_version_commit();

CREATE TABLE compiler_runtime.k_execution_data_versions (
    execution_id uuid NOT NULL REFERENCES compiler_runtime.k_execution_contexts,
    version_id uuid NOT NULL REFERENCES canonical_store.data_versions,
    PRIMARY KEY(execution_id,version_id)
);
CREATE INDEX k_execution_version_dependencies ON compiler_runtime.k_execution_data_versions(version_id);
CREATE FUNCTION compiler_runtime.execution_version_source_data(id uuid) RETURNS SETOF text LANGUAGE sql STABLE AS $$
    SELECT DISTINCT i.data_id FROM compiler_runtime.k_input_information x
        JOIN canonical_store.information i USING(information_id) WHERE x.execution_id=id
    UNION SELECT source.data_id FROM compiler_runtime.k_input_node_revisions x
        CROSS JOIN LATERAL canonical_store.derivation_source_data(x.node_revision_id) source(data_id)
        WHERE x.execution_id=id
$$;
CREATE FUNCTION compiler_runtime.data_version_snapshot_matches(value jsonb, id uuid) RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT EXISTS(SELECT 1 FROM canonical_store.data_versions v WHERE v.version_id=id
        AND value-'created_at'=to_jsonb(v)-'created_at'
        AND (value->>'created_at')::timestamptz=v.created_at)
$$;
CREATE FUNCTION canonical_store.k_revision_supported_by_version_data(
    revision uuid, allowed_data text[], seen uuid[] DEFAULT ARRAY[]::uuid[])
RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE owner text; scope text; compilation record; used_data text[];
        derivation record; premise record; supported boolean;
BEGIN
    IF revision IS NULL OR allowed_data IS NULL OR cardinality(allowed_data)=0
        OR array_position(allowed_data,NULL) IS NOT NULL
        OR revision=ANY(seen) THEN RETURN false; END IF;
    SELECT s.identity_scope,s.source_data_id INTO scope,owner
        FROM canonical_store.knowledge_node_revisions v
        LEFT JOIN canonical_store.knowledge_node_scopes s USING(knode_id)
        WHERE v.knode_revision_id=revision;
    IF NOT FOUND OR (scope='source' AND NOT COALESCE(owner=ANY(allowed_data),false)) THEN RETURN false; END IF;
    seen:=array_append(seen,revision);

    -- Each terminal I2K record describes one complete accepted/reused support
    -- route. Other historical groundings are alternatives, not mandatory inputs.
    FOR compilation IN SELECT r.record_id FROM compiler_runtime.k_compilation_records r
        WHERE r.result_node_revision_id=revision AND r.record_type='i2k'
            AND r.disposition IN ('accepted_new','accepted_revision','reused','no_material_delta') LOOP
        SELECT ARRAY(SELECT DISTINCT i.data_id FROM compiler_runtime.k_information_review_records l
            JOIN canonical_store.information i USING(information_id)
            WHERE l.record_id=compilation.record_id) INTO used_data;
        IF cardinality(used_data)=0 THEN
            SELECT ARRAY(SELECT DISTINCT i.data_id FROM canonical_store.knowledge_node_groundings g
                JOIN canonical_store.information i USING(information_id)
                WHERE g.node_revision_id=revision AND g.origin_record_id=compilation.record_id) INTO used_data;
        END IF;
        IF cardinality(used_data)>0 AND used_data<@allowed_data THEN RETURN true; END IF;
    END LOOP;

    -- A K2K route needs every actual premise, recursively. Bound versions are
    -- frozen execution context; they are not a claim that every context Data
    -- supplied direct evidence to every resulting K.
    FOR derivation IN SELECT d.record_id,r.execution_id FROM canonical_store.knowledge_derivations d
        JOIN compiler_runtime.k_compilation_records r USING(record_id)
        WHERE d.result_node_revision_id=revision AND r.result_node_revision_id=revision
            AND r.record_type='k2k' AND r.disposition IN ('accepted_new','accepted_revision','reused','no_material_delta') LOOP
        IF EXISTS(SELECT 1 FROM compiler_runtime.k_execution_data_versions x
            JOIN canonical_store.data_versions v USING(version_id)
            WHERE x.execution_id=derivation.execution_id AND NOT v.data_id=ANY(allowed_data)) THEN CONTINUE; END IF;
        supported:=false;
        FOR premise IN SELECT premise_node_revision_id FROM canonical_store.knowledge_derivation_premises
            WHERE record_id=derivation.record_id ORDER BY ordinal LOOP
            supported:=canonical_store.k_revision_supported_by_version_data(
                premise.premise_node_revision_id,allowed_data,seen);
            IF NOT supported THEN EXIT; END IF;
        END LOOP;
        IF supported THEN RETURN true; END IF;
    END LOOP;
    RETURN false;
END; $$;
CREATE FUNCTION compiler_runtime.guard_execution_data_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM compiler_runtime.operation_executions e
        JOIN compiler_runtime.k_execution_contexts c USING(execution_id)
        JOIN canonical_store.data_versions v ON v.version_id=NEW.version_id
        WHERE e.execution_id=NEW.execution_id AND e.operation IN ('i2k','n2e','k2k') AND e.state='prepared'
            AND EXISTS(SELECT 1 FROM jsonb_array_elements(COALESCE(c.input_snapshot->'data_versions','[]'::jsonb)) declared
                WHERE compiler_runtime.data_version_snapshot_matches(declared,v.version_id))
            AND v.data_id IN (SELECT compiler_runtime.execution_version_source_data(e.execution_id)))
    THEN RAISE EXCEPTION 'Execution version must bind a frozen exact version of actual input Data'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER execution_data_version_guard BEFORE INSERT ON compiler_runtime.k_execution_data_versions
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_execution_data_version();
CREATE FUNCTION compiler_runtime.check_execution_data_versions() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE snapshot jsonb; declared jsonb; operation text; allowed_data text[];
BEGIN
    SELECT input_snapshot INTO STRICT snapshot FROM compiler_runtime.k_execution_contexts WHERE execution_id=NEW.execution_id;
    declared:=COALESCE(snapshot->'data_versions','[]'::jsonb);
    IF declared='[]'::jsonb AND NOT EXISTS(SELECT 1 FROM compiler_runtime.k_execution_data_versions
        WHERE execution_id=NEW.execution_id) THEN RETURN NULL; END IF;
    IF jsonb_typeof(declared) IS DISTINCT FROM 'array'
        OR COALESCE(snapshot->>'data_version_mode','') NOT IN ('current','pinned')
        OR jsonb_array_length(declared) IS DISTINCT FROM
            (SELECT count(*) FROM compiler_runtime.k_execution_data_versions WHERE execution_id=NEW.execution_id)
        OR EXISTS(SELECT 1 FROM jsonb_array_elements(declared) item
            WHERE NOT EXISTS(SELECT 1 FROM compiler_runtime.k_execution_data_versions x
                JOIN canonical_store.data_versions v USING(version_id) WHERE x.execution_id=NEW.execution_id
                    AND compiler_runtime.data_version_snapshot_matches(item,v.version_id)))
    THEN RAISE EXCEPTION 'Every declared version must have an exact immutable execution link'; END IF;
    SELECT e.operation INTO STRICT operation FROM compiler_runtime.operation_executions e WHERE e.execution_id=NEW.execution_id;
    SELECT ARRAY(SELECT DISTINCT v.data_id FROM compiler_runtime.k_execution_data_versions x
        JOIN canonical_store.data_versions v USING(version_id) WHERE x.execution_id=NEW.execution_id) INTO allowed_data;
    IF operation='i2k' THEN
        IF EXISTS(SELECT 1 FROM compiler_runtime.execution_version_source_data(NEW.execution_id) source(data_id)
            WHERE NOT source.data_id=ANY(allowed_data))
        THEN RAISE EXCEPTION 'Every I2K input Data needs an exact version binding'; END IF;
    ELSE
        IF EXISTS(SELECT 1 FROM compiler_runtime.k_input_node_revisions x WHERE x.execution_id=NEW.execution_id
            AND NOT canonical_store.k_revision_supported_by_version_data(x.node_revision_id,allowed_data))
        THEN RAISE EXCEPTION 'Each input K needs a complete valid support route under the bound version Data'; END IF;
    END IF;
    IF snapshot->>'data_version_mode'='current' THEN
        IF EXISTS(SELECT v.series_id FROM compiler_runtime.k_execution_data_versions x
            JOIN canonical_store.data_versions v USING(version_id) WHERE x.execution_id=NEW.execution_id
            GROUP BY v.series_id HAVING count(*)>1)
        THEN RAISE EXCEPTION 'Current mode accepts only one version per Data series'; END IF;
        -- Only new context/link insertions run this guard. Historical immutable
        -- contexts are not rechecked when unrelated records are later updated.
        PERFORM 1 FROM canonical_store.data_series s WHERE s.series_id IN (
            SELECT v.series_id FROM compiler_runtime.k_execution_data_versions x
            JOIN canonical_store.data_versions v USING(version_id) WHERE x.execution_id=NEW.execution_id)
            ORDER BY s.series_id FOR SHARE;
        IF EXISTS(SELECT 1 FROM compiler_runtime.k_execution_data_versions x
            JOIN canonical_store.data_versions v USING(version_id)
            JOIN canonical_store.data_series s USING(series_id)
            WHERE x.execution_id=NEW.execution_id AND s.head_version_id IS DISTINCT FROM v.version_id)
        THEN RAISE EXCEPTION 'A new current-mode context must bind the actual locked series heads'; END IF;
    END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER execution_versions_context_guard AFTER INSERT ON compiler_runtime.k_execution_contexts
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_execution_data_versions();
CREATE CONSTRAINT TRIGGER execution_versions_commit_guard AFTER INSERT ON compiler_runtime.k_execution_data_versions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_execution_data_versions();

DO $$ DECLARE relation text; BEGIN
    FOREACH relation IN ARRAY ARRAY['canonical_store.data_versions','compiler_runtime.data_version_requests',
            'compiler_runtime.k_execution_data_versions'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON %s FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
        EXECUTE format('CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON %s FOR EACH STATEMENT EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
    END LOOP;
END; $$;
CREATE TRIGGER data_series_no_delete BEFORE DELETE ON canonical_store.data_series
    FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation();
CREATE TRIGGER data_series_no_truncate BEFORE TRUNCATE ON canonical_store.data_series
    FOR EACH STATEMENT EXECUTE FUNCTION canonical_store.reject_snapshot_mutation();
GRANT SELECT,INSERT,UPDATE ON canonical_store.data_series TO palimpsest;
GRANT SELECT,INSERT ON canonical_store.data_versions,compiler_runtime.data_version_requests,
    compiler_runtime.k_execution_data_versions TO palimpsest;
