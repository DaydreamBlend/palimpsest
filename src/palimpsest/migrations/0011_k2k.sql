-- K2K adds derived provenance; 0001-0010 and every prior row remain unchanged.
-- This node-only profile consumes accepted current K revisions, never candidate I.
ALTER TABLE compiler_runtime.operation_executions DROP CONSTRAINT operation_executions_operation_check;
ALTER TABLE compiler_runtime.operation_executions ADD CHECK (operation IN ('d2i','i2k','n2e','k2k'));
ALTER TABLE compiler_runtime.k_compilation_records DROP CONSTRAINT k_compilation_records_record_type_check;
ALTER TABLE compiler_runtime.k_compilation_records ADD CHECK (record_type IN ('i2k','n2e','k2k'));
DO $$ DECLARE name text; BEGIN
    SELECT conname INTO STRICT name FROM pg_constraint
      WHERE conrelid='compiler_runtime.k_compilation_records'::regclass AND contype='c'
        AND conkey @> ARRAY(SELECT attnum FROM pg_attribute
          WHERE attrelid='compiler_runtime.k_compilation_records'::regclass
            AND attname IN ('record_type','result_node_id','result_edge_id'));
    EXECUTE format('ALTER TABLE compiler_runtime.k_compilation_records DROP CONSTRAINT %I',name);
END; $$;
ALTER TABLE compiler_runtime.k_compilation_records ADD CONSTRAINT k_record_result_kind
    CHECK ((record_type IN ('i2k','k2k') AND result_edge_id IS NULL)
        OR (record_type='n2e' AND result_node_id IS NULL));

CREATE TABLE canonical_store.knowledge_derivations (
    record_id uuid PRIMARY KEY REFERENCES compiler_runtime.k_compilation_records,
    result_node_revision_id uuid NOT NULL REFERENCES canonical_store.knowledge_node_revisions,
    inference_type text NOT NULL CHECK (inference_type IN ('inductive','deductive')),
    assumptions jsonb NOT NULL CHECK (jsonb_typeof(assumptions)='array'),
    limitations jsonb NOT NULL CHECK (jsonb_typeof(limitations)='array'),
    derivation_basis text NOT NULL CHECK (length(btrim(derivation_basis))>0),
    derivation_depth integer NOT NULL CHECK (derivation_depth>0),
    validation jsonb NOT NULL CHECK (jsonb_typeof(validation)='object')
);
CREATE INDEX knowledge_derivation_result ON canonical_store.knowledge_derivations(result_node_revision_id);
CREATE TABLE canonical_store.knowledge_derivation_premises (
    record_id uuid NOT NULL REFERENCES canonical_store.knowledge_derivations,
    premise_node_revision_id uuid NOT NULL REFERENCES canonical_store.knowledge_node_revisions,
    ordinal integer NOT NULL CHECK (ordinal>=0),
    PRIMARY KEY(record_id,premise_node_revision_id), UNIQUE(record_id,ordinal)
);
CREATE INDEX knowledge_derivation_input ON canonical_store.knowledge_derivation_premises(premise_node_revision_id);

CREATE FUNCTION compiler_runtime.is_k2k_execution(id uuid) RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT EXISTS(SELECT 1 FROM compiler_runtime.operation_executions e
        JOIN compiler_runtime.profiles p USING(profile_id) WHERE e.execution_id=id
        AND e.operation='k2k' AND p.payload->>'schema_version'='knowledge-inference-v1')
$$;
CREATE FUNCTION compiler_runtime.current_k2k_premise(id uuid) RETURNS boolean LANGUAGE sql STABLE AS $$
    WITH RECURSIVE ancestry(revision_id) AS (
        SELECT id UNION
        SELECT p.premise_node_revision_id FROM ancestry a
        JOIN canonical_store.knowledge_node_revisions v ON v.knode_revision_id=a.revision_id
        JOIN canonical_store.knowledge_derivations d ON d.record_id=v.origin_record_id
        JOIN canonical_store.knowledge_derivation_premises p USING(record_id))
    SELECT NOT EXISTS(SELECT 1 FROM ancestry a
        LEFT JOIN canonical_store.knowledge_node_revisions v ON v.knode_revision_id=a.revision_id
        LEFT JOIN canonical_store.knowledge_nodes n USING(knode_id)
        LEFT JOIN compiler_runtime.k_compilation_records r ON r.record_id=v.origin_record_id
        WHERE v.knode_revision_id IS NULL OR n.current_revision_id IS DISTINCT FROM a.revision_id
          OR r.disposition NOT IN ('accepted_new','accepted_revision')
          OR r.result_node_revision_id IS DISTINCT FROM a.revision_id
          OR r.result_node_id IS DISTINCT FROM v.knode_id)
$$;
CREATE FUNCTION canonical_store.derivation_source_data(id uuid) RETURNS SETOF text LANGUAGE sql STABLE AS $$
    WITH RECURSIVE ancestry(revision_id) AS (
        SELECT id UNION
        SELECT p.premise_node_revision_id FROM ancestry a
        JOIN canonical_store.knowledge_derivations d ON d.result_node_revision_id=a.revision_id
        JOIN canonical_store.knowledge_derivation_premises p USING(record_id))
    SELECT DISTINCT i.data_id FROM ancestry a
        JOIN canonical_store.knowledge_node_groundings g ON g.node_revision_id=a.revision_id
        JOIN canonical_store.information i USING(information_id)
$$;

CREATE FUNCTION compiler_runtime.check_k2k_context_commit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE e compiler_runtime.operation_executions; snapshot jsonb;
BEGIN
    SELECT * INTO STRICT e FROM compiler_runtime.operation_executions WHERE execution_id=NEW.execution_id;
    IF e.operation<>'k2k' THEN RETURN NULL; END IF;
    SELECT input_snapshot->'input' INTO snapshot FROM compiler_runtime.k_execution_contexts WHERE execution_id=e.execution_id;
    IF NOT compiler_runtime.is_k2k_execution(e.execution_id)
        OR snapshot->>'schema_version' IS DISTINCT FROM 'k2k-input-v1'
        OR snapshot->>'data_id' IS DISTINCT FROM e.data_id
        OR jsonb_typeof(snapshot->'nodes') IS DISTINCT FROM 'array'
        OR COALESCE(snapshot->'edges','[]'::jsonb)<>'[]'::jsonb
        OR (SELECT count(*) FROM compiler_runtime.k_input_node_revisions WHERE execution_id=e.execution_id)<2
        OR jsonb_array_length(snapshot->'nodes') IS DISTINCT FROM
            (SELECT count(*) FROM compiler_runtime.k_input_node_revisions WHERE execution_id=e.execution_id)
        OR EXISTS(SELECT 1 FROM compiler_runtime.k_input_information WHERE execution_id=e.execution_id)
    THEN RAISE EXCEPTION 'K2K requires its exact node-only input profile and at least two distinct premises'; END IF;
    IF EXISTS(SELECT 1 FROM compiler_runtime.k_input_node_revisions x
        JOIN canonical_store.knowledge_node_revisions v ON v.knode_revision_id=x.node_revision_id
        JOIN canonical_store.knowledge_nodes n USING(knode_id)
        WHERE x.execution_id=e.execution_id AND (
            snapshot->'nodes'->x.ordinal->>'knode_revision_id' IS DISTINCT FROM x.node_revision_id::text
            OR snapshot->'nodes'->x.ordinal->>'knode_id' IS DISTINCT FROM v.knode_id::text
            OR snapshot->'nodes'->x.ordinal->>'statement' IS DISTINCT FROM v.statement
            OR snapshot->'nodes'->x.ordinal->'semantic_payload' IS DISTINCT FROM v.semantic_payload
            OR snapshot->'nodes'->x.ordinal->>'content_fingerprint' IS DISTINCT FROM v.content_fingerprint
            OR snapshot->'nodes'->x.ordinal->>'kind' IS DISTINCT FROM n.kind
            OR NOT compiler_runtime.current_k2k_premise(x.node_revision_id)))
    THEN RAISE EXCEPTION 'K2K frozen nodes must match accepted current canonical premises'; END IF;
    IF NOT EXISTS(SELECT 1 FROM compiler_runtime.k_input_node_revisions x
        CROSS JOIN LATERAL canonical_store.derivation_source_data(x.node_revision_id) source(data_id)
        WHERE x.execution_id=e.execution_id AND source.data_id=e.data_id)
    THEN RAISE EXCEPTION 'K2K operational Data must occur in its actual transitive source provenance'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER k2k_context_commit_guard AFTER INSERT ON compiler_runtime.k_execution_contexts
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_k2k_context_commit();

CREATE FUNCTION canonical_store.guard_knowledge_derivation() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r compiler_runtime.k_compilation_records; candidate jsonb; e compiler_runtime.operation_executions;
BEGIN
    SELECT * INTO STRICT r FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.record_id;
    SELECT * INTO STRICT e FROM compiler_runtime.operation_executions WHERE execution_id=r.execution_id;
    SELECT body INTO candidate FROM compiler_runtime.k_temporary_candidates WHERE record_id=r.record_id;
    IF r.record_type<>'k2k' OR NOT compiler_runtime.is_k2k_execution(r.execution_id)
        OR e.state<>'proposed' OR r.disposition NOT IN ('pending','needs_human') OR candidate IS NULL
    THEN RAISE EXCEPTION 'Derived provenance must be staged by its unresolved K2K Record'; END IF;
    IF TG_TABLE_NAME='knowledge_derivations' THEN
        IF candidate->>'kind' IS DISTINCT FROM 'proposition'
            OR NOT EXISTS(SELECT 1 FROM canonical_store.knowledge_node_revisions v
                JOIN canonical_store.knowledge_nodes n USING(knode_id)
                WHERE v.knode_revision_id=NEW.result_node_revision_id AND n.kind='proposition')
            OR candidate->>'inference_type' IS DISTINCT FROM NEW.inference_type
            OR candidate->'assumptions' IS DISTINCT FROM NEW.assumptions
            OR candidate->'limitations' IS DISTINCT FROM NEW.limitations
            OR candidate->>'derivation_basis' IS DISTINCT FROM NEW.derivation_basis
            OR candidate->'derivation_depth' IS DISTINCT FROM to_jsonb(NEW.derivation_depth)
            OR NEW.validation->>'candidate_key' IS DISTINCT FROM candidate->>'candidate_key'
            OR jsonb_typeof(candidate->'premise_revision_ids') IS DISTINCT FROM 'array'
            OR jsonb_array_length(candidate->'premise_revision_ids')<2
            OR EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.assumptions||NEW.limitations) item
                WHERE jsonb_typeof(item)<>'string' OR length(btrim(item#>>'{}'))=0)
            OR NEW.validation->'inference_valid' IS DISTINCT FROM 'true'::jsonb
            OR NEW.validation->'premises_sufficient' IS DISTINCT FROM 'true'::jsonb
            OR NEW.validation->'limits_preserved' IS DISTINCT FROM 'true'::jsonb
            OR jsonb_typeof(NEW.validation->'novel_conclusion') IS DISTINCT FROM 'boolean'
            OR COALESCE(NEW.validation->>'verdict','') NOT IN ('accepted','reused')
            OR (NEW.validation->>'verdict'='accepted'
                AND NEW.validation->'novel_conclusion' IS DISTINCT FROM 'true'::jsonb)
            OR (NEW.validation->>'equivalent_revision_id' IS NOT NULL
                AND NEW.validation->>'equivalent_revision_id' IS DISTINCT FROM NEW.result_node_revision_id::text)
            OR NEW.validation ? '_premise_revision_ids'
            OR EXISTS(SELECT 1 FROM canonical_store.knowledge_node_revisions v
                JOIN canonical_store.knowledge_node_scopes s USING(knode_id)
                WHERE v.knode_revision_id=NEW.result_node_revision_id AND (
                    candidate->>'identity_scope' IS DISTINCT FROM s.identity_scope
                    OR candidate->>'source_data_id' IS DISTINCT FROM s.source_data_id))
        THEN RAISE EXCEPTION 'K2K derivation must bind the actual proposition, inference and independent decision'; END IF;
        -- Preserve the declared complete input list after temporary candidate cleanup.
        -- This witness is supplied by the database, not by a provider decision.
        NEW.validation:=NEW.validation||jsonb_build_object('_premise_revision_ids',candidate->'premise_revision_ids');
    ELSE
        IF NOT EXISTS(SELECT 1 FROM compiler_runtime.k_input_node_revisions
            WHERE execution_id=r.execution_id AND node_revision_id=NEW.premise_node_revision_id)
            OR candidate->'premise_revision_ids'->>NEW.ordinal IS DISTINCT FROM NEW.premise_node_revision_id::text
            OR NOT compiler_runtime.current_k2k_premise(NEW.premise_node_revision_id)
        THEN RAISE EXCEPTION 'A derivation premise must match the candidate and its frozen accepted current input'; END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER knowledge_derivation_guard BEFORE INSERT ON canonical_store.knowledge_derivations
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_knowledge_derivation();
CREATE TRIGGER knowledge_derivation_premise_guard BEFORE INSERT ON canonical_store.knowledge_derivation_premises
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_knowledge_derivation();

CREATE FUNCTION canonical_store.check_knowledge_derivation_commit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r compiler_runtime.k_compilation_records; d canonical_store.knowledge_derivations; expected_depth integer;
BEGIN
    SELECT * INTO STRICT r FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.record_id;
    SELECT * INTO STRICT d FROM canonical_store.knowledge_derivations WHERE record_id=r.record_id;
    IF r.record_type<>'k2k' OR r.disposition NOT IN ('accepted_new','accepted_revision','reused','no_material_delta')
        OR r.result_node_revision_id IS DISTINCT FROM d.result_node_revision_id
        OR NOT EXISTS(SELECT 1 FROM canonical_store.knowledge_node_revisions v
            JOIN canonical_store.knowledge_nodes n USING(knode_id)
            JOIN canonical_store.knowledge_node_scopes s USING(knode_id)
            WHERE v.knode_revision_id=d.result_node_revision_id AND v.knode_id=r.result_node_id
                AND n.kind='proposition' AND n.current_revision_id=v.knode_revision_id)
        OR (r.disposition IN ('accepted_new','accepted_revision') AND (
            d.validation->'novel_conclusion' IS DISTINCT FROM 'true'::jsonb
            OR d.validation->>'verdict' IS DISTINCT FROM 'accepted'))
        OR (SELECT count(*) FROM canonical_store.knowledge_derivation_premises WHERE record_id=r.record_id)<2
        OR (SELECT max(ordinal)+1 FROM canonical_store.knowledge_derivation_premises WHERE record_id=r.record_id)
            IS DISTINCT FROM (SELECT count(*) FROM canonical_store.knowledge_derivation_premises WHERE record_id=r.record_id)
        OR d.validation->'_premise_revision_ids' IS DISTINCT FROM
            (SELECT jsonb_agg(premise_node_revision_id::text ORDER BY ordinal)
             FROM canonical_store.knowledge_derivation_premises WHERE record_id=r.record_id)
        OR EXISTS(SELECT 1 FROM canonical_store.knowledge_node_groundings WHERE origin_record_id=r.record_id)
    THEN RAISE EXCEPTION 'K2K result, validated derivation and at least two exact premises must commit together'; END IF;
    IF EXISTS(SELECT 1 FROM canonical_store.knowledge_derivation_premises p
        WHERE p.record_id=r.record_id AND NOT compiler_runtime.current_k2k_premise(p.premise_node_revision_id))
    THEN RAISE EXCEPTION 'K2K premise became stale before commit'; END IF;
    SELECT 1+max(COALESCE(parent.derivation_depth,0)) INTO expected_depth
        FROM canonical_store.knowledge_derivation_premises p
        JOIN canonical_store.knowledge_node_revisions v ON v.knode_revision_id=p.premise_node_revision_id
        LEFT JOIN canonical_store.knowledge_derivations parent ON parent.record_id=v.origin_record_id
        WHERE p.record_id=r.record_id;
    IF d.derivation_depth IS DISTINCT FROM expected_depth
    THEN RAISE EXCEPTION 'Derivation depth must preserve the exact premise origin depths'; END IF;
    IF EXISTS(WITH RECURSIVE ancestry(revision_id) AS (
        SELECT premise_node_revision_id FROM canonical_store.knowledge_derivation_premises WHERE record_id=r.record_id
        UNION SELECT p.premise_node_revision_id FROM ancestry a
          JOIN canonical_store.knowledge_derivations parent ON parent.result_node_revision_id=a.revision_id
          JOIN canonical_store.knowledge_derivation_premises p ON p.record_id=parent.record_id)
        SELECT 1 FROM ancestry WHERE revision_id=d.result_node_revision_id)
    THEN RAISE EXCEPTION 'A reused conclusion cannot become its own transitive premise'; END IF;
    IF EXISTS(SELECT 1 FROM canonical_store.knowledge_node_scopes s WHERE s.knode_id=r.result_node_id
        AND s.identity_scope='source' AND NOT EXISTS(SELECT 1 FROM canonical_store.knowledge_derivation_premises p
            CROSS JOIN LATERAL canonical_store.derivation_source_data(p.premise_node_revision_id) source(data_id)
            WHERE p.record_id=r.record_id AND source.data_id=s.source_data_id))
    THEN RAISE EXCEPTION 'Source-scoped K2K must retain actual source provenance for its attributed Data'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER knowledge_derivation_commit_guard AFTER INSERT ON canonical_store.knowledge_derivations
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION canonical_store.check_knowledge_derivation_commit();
CREATE CONSTRAINT TRIGGER knowledge_derivation_premise_commit_guard AFTER INSERT ON canonical_store.knowledge_derivation_premises
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION canonical_store.check_knowledge_derivation_commit();

DO $$ DECLARE relation text; BEGIN
    FOREACH relation IN ARRAY ARRAY['canonical_store.knowledge_derivations','canonical_store.knowledge_derivation_premises'] LOOP
        EXECUTE format('CREATE TRIGGER a_knowledge_state BEFORE INSERT ON %s FOR EACH ROW EXECUTE FUNCTION compiler_runtime.advance_knowledge_state()',relation);
        EXECUTE format('CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON %s FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
        EXECUTE format('CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON %s FOR EACH STATEMENT EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
    END LOOP;
END; $$;
GRANT SELECT,INSERT ON canonical_store.knowledge_derivations,canonical_store.knowledge_derivation_premises TO palimpsest;

-- Existing guards retain their I2K/N2E branches; only K2K cases are added.

CREATE OR REPLACE FUNCTION compiler_runtime.guard_k_context() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='INSERT' THEN
        IF NOT EXISTS (SELECT 1 FROM compiler_runtime.operation_executions
            WHERE execution_id=NEW.execution_id AND operation IN ('i2k','n2e','k2k') AND state='prepared')
        THEN RAISE EXCEPTION 'K context requires a prepared I2K/N2E execution'; END IF;
    ELSIF to_jsonb(NEW)-'validation_context_sha' IS DISTINCT FROM to_jsonb(OLD)-'validation_context_sha'
        OR OLD.validation_context_sha IS NOT NULL THEN
        RAISE EXCEPTION 'K execution input is frozen';
    END IF;
    RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION compiler_runtime.guard_k_input() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM compiler_runtime.operation_executions e
        WHERE e.execution_id=NEW.execution_id AND e.state='prepared'
          AND ((TG_TABLE_NAME='k_input_information' AND e.operation='i2k')
            OR (TG_TABLE_NAME='k_input_node_revisions' AND e.operation IN ('n2e','k2k'))))
    THEN RAISE EXCEPTION 'Authoritative K inputs are frozen before model execution'; END IF;
    IF TG_TABLE_NAME='k_input_node_revisions' AND EXISTS(SELECT 1 FROM compiler_runtime.operation_executions
        WHERE execution_id=NEW.execution_id AND operation='k2k') THEN
        IF NOT compiler_runtime.is_k2k_execution(NEW.execution_id)
            OR NOT compiler_runtime.current_k2k_premise(NEW.node_revision_id)
        THEN RAISE EXCEPTION 'K2K input must be an accepted current premise'; END IF;
    END IF;
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

CREATE OR REPLACE FUNCTION canonical_store.guard_k_revision_insert() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE current_id uuid; previous_payload jsonb; previous_qualifiers jsonb; previous_fp text; same_payload boolean;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.origin_record_id
        AND disposition IN ('pending','needs_human')
        AND ((TG_TABLE_NAME='knowledge_node_revisions' AND record_type IN ('i2k','k2k'))
            OR (TG_TABLE_NAME='knowledge_edge_revisions' AND record_type='n2e')))
    THEN RAISE EXCEPTION 'K revision requires its unresolved operation Record'; END IF;
    IF TG_TABLE_NAME='knowledge_node_revisions' AND EXISTS(SELECT 1 FROM compiler_runtime.k_compilation_records
        WHERE record_id=NEW.origin_record_id AND record_type='k2k') AND NOT EXISTS(
            SELECT 1 FROM canonical_store.knowledge_nodes WHERE knode_id=NEW.knode_id AND kind='proposition')
    THEN RAISE EXCEPTION 'K2K cannot synthesize an Observation'; END IF;
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

CREATE OR REPLACE FUNCTION canonical_store.check_k_revision_commit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r compiler_runtime.k_compilation_records; node_case boolean; revision_id uuid; object_id uuid;
BEGIN
    node_case:=TG_TABLE_NAME='knowledge_node_revisions';
    SELECT * INTO STRICT r FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.origin_record_id;
    IF node_case THEN
        revision_id:=NEW.knode_revision_id; object_id:=NEW.knode_id;
        IF r.record_type NOT IN ('i2k','k2k') OR r.result_node_revision_id IS DISTINCT FROM revision_id
            OR r.result_node_id IS DISTINCT FROM object_id
            OR (r.record_type='i2k' AND NOT EXISTS (
                SELECT 1 FROM canonical_store.knowledge_node_groundings
                WHERE node_revision_id=revision_id AND origin_record_id=r.record_id))
            OR (r.record_type='k2k' AND NOT EXISTS (
                SELECT 1 FROM canonical_store.knowledge_derivations
                WHERE result_node_revision_id=revision_id AND record_id=r.record_id))
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

CREATE OR REPLACE FUNCTION compiler_runtime.check_k_record_commit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r compiler_runtime.k_compilation_records;
BEGIN
    SELECT * INTO STRICT r FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.record_id;
    IF r.record_type='k2k' AND r.result_node_revision_id IS NOT NULL AND NOT EXISTS(
        SELECT 1 FROM canonical_store.knowledge_derivations
        WHERE record_id=r.record_id AND result_node_revision_id=r.result_node_revision_id)
    THEN RAISE EXCEPTION 'Every K2K result, including reuse, requires its own validated derivation'; END IF;
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
        IF r.record_type IN ('i2k','k2k') AND NOT EXISTS (SELECT 1 FROM canonical_store.knowledge_node_revisions
            WHERE knode_revision_id=r.result_node_revision_id AND origin_record_id=r.record_id)
        THEN RAISE EXCEPTION 'Accepted I2K Record must originate its result revision'; END IF;
        IF r.record_type='n2e' AND NOT EXISTS (SELECT 1 FROM canonical_store.knowledge_edge_revisions
            WHERE kedge_revision_id=r.result_edge_revision_id AND origin_record_id=r.record_id)
        THEN RAISE EXCEPTION 'Accepted N2E Record must originate its result revision'; END IF;
    END IF;
    RETURN NULL;
END; $$;

CREATE OR REPLACE FUNCTION canonical_store.guard_knowledge_scope() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE node_kind text; execution_data text; execution uuid; multi boolean; candidate jsonb;
BEGIN
    IF EXISTS(SELECT 1 FROM compiler_runtime.k_compilation_records r
        WHERE r.record_id=NEW.origin_record_id AND r.record_type='k2k') THEN
        SELECT t.body INTO candidate FROM compiler_runtime.k_compilation_records r
            JOIN compiler_runtime.k_temporary_candidates t USING(record_id)
            JOIN compiler_runtime.operation_executions e USING(execution_id)
            WHERE r.record_id=NEW.origin_record_id AND r.disposition IN ('pending','needs_human')
                AND e.state='proposed' AND compiler_runtime.is_k2k_execution(e.execution_id);
        IF candidate IS NULL OR candidate->>'kind' IS DISTINCT FROM 'proposition'
            OR candidate->>'identity_scope' IS DISTINCT FROM NEW.identity_scope
            OR candidate->>'source_data_id' IS DISTINCT FROM NEW.source_data_id
            OR NOT EXISTS(SELECT 1 FROM canonical_store.knowledge_nodes
                WHERE knode_id=NEW.knode_id AND kind='proposition')
        THEN RAISE EXCEPTION 'K2K scope must bind its staged proposition and declared source ownership'; END IF;
        RETURN NEW;
    END IF;
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

CREATE OR REPLACE FUNCTION canonical_store.check_knowledge_scope_commit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS(SELECT 1 FROM compiler_runtime.k_compilation_records
        WHERE record_id=NEW.origin_record_id AND record_type='k2k') THEN
        IF NOT EXISTS(SELECT 1 FROM compiler_runtime.k_compilation_records r
            JOIN canonical_store.knowledge_derivations d USING(record_id)
            WHERE r.record_id=NEW.origin_record_id AND r.result_node_id=NEW.knode_id
              AND d.result_node_revision_id=r.result_node_revision_id
              AND r.disposition IN ('accepted_new','accepted_revision','reused','no_material_delta'))
        THEN RAISE EXCEPTION 'K2K scope and exact validated derivation must commit together'; END IF;
        RETURN NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM compiler_runtime.k_compilation_records r
        WHERE r.record_id=NEW.origin_record_id AND r.record_type='i2k' AND r.result_node_id=NEW.knode_id
          AND r.disposition IN ('accepted_new','accepted_revision','reused','no_material_delta')
          AND EXISTS (SELECT 1 FROM canonical_store.knowledge_node_groundings g
              JOIN compiler_runtime.k_input_information x ON x.information_id=g.information_id
              WHERE x.execution_id=r.execution_id AND g.node_revision_id=r.result_node_revision_id))
    THEN RAISE EXCEPTION 'Scope and exact validated Knowledge reuse/creation must commit together'; END IF;
    RETURN NULL;
END; $$;
