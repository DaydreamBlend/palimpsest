-- Current P/O relation registry. Supersedes remains reserved for authority-confirmed W2K.
ALTER TABLE canonical_store.knowledge_edges DROP CONSTRAINT knowledge_edges_predicate_check;
ALTER TABLE canonical_store.knowledge_edges ADD CONSTRAINT knowledge_edges_predicate_registry
    CHECK (predicate IN ('supports','contradicts','qualifies','composes'));
ALTER TABLE canonical_store.knowledge_edge_applicability_events ADD COLUMN detail jsonb NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(detail)='object');

CREATE TABLE compiler_runtime.n2e_review_targets (
    execution_id uuid PRIMARY KEY REFERENCES compiler_runtime.operation_executions,
    semantic_kedge_revision_id uuid NOT NULL REFERENCES canonical_store.knowledge_edge_revisions,
    from_knode_revision_id uuid NOT NULL REFERENCES canonical_store.knowledge_node_revisions,
    to_knode_revision_id uuid NOT NULL REFERENCES canonical_store.knowledge_node_revisions,
    fence_order bigint NOT NULL UNIQUE CHECK (fence_order>0),
    target jsonb NOT NULL CHECK (jsonb_typeof(target)='object')
);
CREATE INDEX n2e_review_target_pair ON compiler_runtime.n2e_review_targets
    (semantic_kedge_revision_id,from_knode_revision_id,to_knode_revision_id,fence_order DESC);
CREATE TABLE compiler_runtime.n2e_review_decisions (
    record_id uuid PRIMARY KEY REFERENCES compiler_runtime.k_compilation_records,
    execution_id uuid NOT NULL REFERENCES compiler_runtime.operation_executions,
    candidate_key text NOT NULL CHECK (candidate_key ~ '^[A-Za-z][A-Za-z0-9_.-]{0,127}$'),
    role text NOT NULL CHECK (role IN ('relation','target_assessment')),
    validation jsonb NOT NULL CHECK (jsonb_typeof(validation)='object'),
    action text NOT NULL CHECK (action IN ('accepted_new','accepted_revision','reused','no_material_delta','rejected','needs_human')),
    material_change boolean NOT NULL,
    before_applicable boolean,
    after_applicable boolean,
    UNIQUE(execution_id,candidate_key)
);

CREATE FUNCTION compiler_runtime.is_n2e_relations(id uuid) RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT EXISTS(SELECT 1 FROM compiler_runtime.operation_executions e
        JOIN compiler_runtime.profiles p USING(profile_id) WHERE e.execution_id=id AND e.operation='n2e'
            AND COALESCE(p.payload->>'n2e_policy',p.payload->>'profile')='n2e-relations-v1')
$$;
CREATE FUNCTION canonical_store.n2e_predicate_compatible(predicate text,source_kind text,target_kind text)
RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
    SELECT COALESCE(source_kind IN ('proposition','observation') AND target_kind IN ('proposition','observation')
        AND (predicate IN ('contradicts','composes') OR
            (predicate IN ('supports','qualifies') AND target_kind='proposition')),false)
$$;

CREATE FUNCTION canonical_store.current_knowledge_support_signature(id uuid) RETURNS text LANGUAGE sql STABLE AS $$
    WITH RECURSIVE ancestry(revision_id) AS (
        SELECT id UNION
        SELECT p.premise_node_revision_id FROM ancestry a
        JOIN canonical_store.knowledge_derivation_premises p
            ON p.record_id=canonical_store.current_k_support_record(a.revision_id))
    -- UUID strings all have equal length: JSONB order/spacing matches Python's
    -- json.dumps(route, sort_keys=True), and this map contains only ASCII/null.
    SELECT encode(sha256(convert_to(jsonb_object_agg(revision_id::text,
        canonical_store.current_k_support_record(revision_id)::text ORDER BY revision_id)::text,'UTF8')),'hex') FROM ancestry
$$;

CREATE FUNCTION compiler_runtime.n2e_review_pending(revision uuid,source_revision uuid,target_revision uuid)
RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT COALESCE((SELECT max(fence_order) FROM compiler_runtime.n2e_review_targets
        WHERE semantic_kedge_revision_id=revision AND from_knode_revision_id=source_revision AND to_knode_revision_id=target_revision),-1)
        > COALESCE((SELECT max(event_order) FROM canonical_store.knowledge_edge_applicability_events
        WHERE semantic_kedge_revision_id=revision AND from_knode_revision_id=source_revision AND to_knode_revision_id=target_revision),-1)
$$;

CREATE FUNCTION canonical_store.current_knowledge_edge_applicability(revision uuid)
RETURNS text LANGUAGE plpgsql STABLE AS $$
DECLARE selected record; explicit_event canonical_store.knowledge_edge_applicability_events;
        basis_record uuid; basis_nodes jsonb; stored_signature text; endpoint uuid; has_event boolean;
BEGIN
    SELECT e.kedge_id,e.current_revision_id,v.origin_record_id,
        v.from_knode_revision_id AS original_from,v.to_knode_revision_id AS original_to,
        source_node.current_revision_id AS current_from,target_node.current_revision_id AS current_to,
        r.disposition,r.result_edge_revision_id,r.result_edge_id
        INTO selected FROM canonical_store.knowledge_edge_revisions v
        JOIN canonical_store.knowledge_edges e USING(kedge_id)
        JOIN canonical_store.knowledge_nodes source_node ON source_node.knode_id=e.from_knode_id
        JOIN canonical_store.knowledge_nodes target_node ON target_node.knode_id=e.to_knode_id
        JOIN compiler_runtime.k_compilation_records r ON r.record_id=v.origin_record_id
        WHERE v.kedge_revision_id=revision;
    IF NOT FOUND OR selected.current_revision_id IS DISTINCT FROM revision
        OR selected.disposition NOT IN ('accepted_new','accepted_revision')
        OR selected.result_edge_revision_id IS DISTINCT FROM revision OR selected.result_edge_id IS DISTINCT FROM selected.kedge_id
    THEN RETURN 'historical'; END IF;
    IF NOT compiler_runtime.current_k2k_premise(selected.current_from)
        OR NOT compiler_runtime.current_k2k_premise(selected.current_to)
    THEN RETURN 'endpoint_unusable'; END IF;
    IF compiler_runtime.n2e_review_pending(revision,selected.current_from,selected.current_to)
    THEN RETURN 'pending'; END IF;
    SELECT * INTO explicit_event FROM canonical_store.knowledge_edge_applicability_events
        WHERE semantic_kedge_revision_id=revision AND from_knode_revision_id=selected.current_from
            AND to_knode_revision_id=selected.current_to ORDER BY event_order DESC LIMIT 1;
    has_event:=FOUND;
    IF has_event THEN
        IF explicit_event.detail->>'n2e_policy'='n2e-relations-v1'
            AND explicit_event.detail->'endpoint_support_signatures' IS DISTINCT FROM jsonb_build_array(
                canonical_store.current_knowledge_support_signature(selected.current_from),
                canonical_store.current_knowledge_support_signature(selected.current_to))
        THEN RETURN 'pending'; END IF;
        IF explicit_event.detail->>'n2e_policy'='n2e-relations-v1'
        THEN RETURN (CASE WHEN explicit_event.applicable THEN 'applicable' ELSE 'inapplicable' END); END IF;
        basis_record:=explicit_event.origin_record_id;
    ELSE
        IF selected.original_from<>selected.current_from OR selected.original_to<>selected.current_to THEN RETURN 'pending'; END IF;
        basis_record:=selected.origin_record_id;
        IF compiler_runtime.is_n2e_relations((SELECT execution_id FROM compiler_runtime.k_compilation_records
            WHERE record_id=basis_record)) THEN RETURN 'pending'; END IF;
    END IF;
    SELECT context.input_snapshot->'input'->'nodes' INTO basis_nodes
        FROM compiler_runtime.k_compilation_records r JOIN compiler_runtime.k_execution_contexts context USING(execution_id)
        WHERE r.record_id=basis_record;
    FOREACH endpoint IN ARRAY ARRAY[selected.current_from,selected.current_to] LOOP
        SELECT node->>'current_support_signature' INTO stored_signature
            FROM jsonb_array_elements(COALESCE(basis_nodes,'[]'::jsonb)) node WHERE node->>'knode_revision_id'=endpoint::text;
        IF (stored_signature IS NOT NULL AND stored_signature<>canonical_store.current_knowledge_support_signature(endpoint))
            OR (stored_signature IS NULL AND canonical_store.current_k_support_record(endpoint) IS NOT NULL)
        THEN RETURN 'pending'; END IF;
    END LOOP;
    RETURN (CASE WHEN has_event AND NOT explicit_event.applicable THEN 'inapplicable' ELSE 'applicable' END);
END; $$;

CREATE FUNCTION canonical_store.guard_n2e_logical_relation() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE source_kind text; target_kind text;
BEGIN
    SELECT kind INTO STRICT source_kind FROM canonical_store.knowledge_nodes WHERE knode_id=NEW.from_knode_id;
    SELECT kind INTO STRICT target_kind FROM canonical_store.knowledge_nodes WHERE knode_id=NEW.to_knode_id;
    IF NOT canonical_store.n2e_predicate_compatible(NEW.predicate,source_kind,target_kind)
        OR (NEW.predicate='contradicts' AND NEW.from_knode_id>=NEW.to_knode_id)
    THEN RAISE EXCEPTION 'Relation predicate, endpoint kinds and symmetric logical ordering must match the registry'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER n2e_logical_relation_guard BEFORE INSERT ON canonical_store.knowledge_edges
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_n2e_logical_relation();

CREATE FUNCTION compiler_runtime.guard_n2e_review_target() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE target_edge jsonb; actual_pair jsonb; prior_event jsonb; current_version bigint;
BEGIN
    SELECT version INTO STRICT current_version FROM compiler_runtime.knowledge_state WHERE singleton FOR UPDATE;
    SELECT to_jsonb(selected) INTO target_edge FROM (
        SELECT e.kedge_id,v.kedge_revision_id,e.predicate,e.from_knode_id,e.to_knode_id,
            v.from_knode_revision_id,v.to_knode_revision_id,v.qualifiers,v.identity_fingerprint,v.content_fingerprint
        FROM canonical_store.knowledge_edges e JOIN canonical_store.knowledge_edge_revisions v ON v.kedge_revision_id=e.current_revision_id
        WHERE v.kedge_revision_id=NEW.semantic_kedge_revision_id) selected;
    SELECT jsonb_build_array(source_node.current_revision_id::text,target_node.current_revision_id::text) INTO actual_pair
        FROM canonical_store.knowledge_edges e JOIN canonical_store.knowledge_nodes source_node ON source_node.knode_id=e.from_knode_id
        JOIN canonical_store.knowledge_nodes target_node ON target_node.knode_id=e.to_knode_id
        WHERE e.kedge_id::text=target_edge->>'kedge_id';
    IF NOT compiler_runtime.is_n2e_relations(NEW.execution_id)
        OR NOT EXISTS(SELECT 1 FROM compiler_runtime.operation_executions WHERE execution_id=NEW.execution_id AND state='prepared')
        OR EXISTS(SELECT 1 FROM compiler_runtime.k_execution_contexts WHERE execution_id=NEW.execution_id)
        OR NEW.fence_order IS DISTINCT FROM current_version OR target_edge IS NULL
        OR NEW.target->>'schema_version' IS DISTINCT FROM 'n2e-relations-v1' OR NEW.target->>'kind' IS DISTINCT FROM 'edge'
        OR NEW.target->>'target_revision_id' IS DISTINCT FROM NEW.semantic_kedge_revision_id::text
        OR NEW.target->>'target_kedge_id' IS DISTINCT FROM target_edge->>'kedge_id'
        OR NEW.target->'target' IS DISTINCT FROM target_edge
        OR COALESCE(NEW.target->>'target_sha256','') !~ '^[0-9a-f]{64}$'
        OR NEW.target->>'from_revision_id' IS DISTINCT FROM NEW.from_knode_revision_id::text
        OR NEW.target->>'to_revision_id' IS DISTINCT FROM NEW.to_knode_revision_id::text
        OR actual_pair IS DISTINCT FROM jsonb_build_array(NEW.from_knode_revision_id::text,NEW.to_knode_revision_id::text)
        OR NOT compiler_runtime.current_k2k_premise(NEW.from_knode_revision_id)
        OR NOT compiler_runtime.current_k2k_premise(NEW.to_knode_revision_id)
        OR NEW.target->'endpoint_support_signatures' IS DISTINCT FROM jsonb_build_array(
            canonical_store.current_knowledge_support_signature(NEW.from_knode_revision_id),
            canonical_store.current_knowledge_support_signature(NEW.to_knode_revision_id))
        OR NEW.target->'endpoint_support_record_ids' IS DISTINCT FROM jsonb_build_array(
            canonical_store.current_k_support_record(NEW.from_knode_revision_id)::text,
            canonical_store.current_k_support_record(NEW.to_knode_revision_id)::text)
        OR jsonb_typeof(NEW.target->'prior_pair') IS DISTINCT FROM 'array' OR jsonb_array_length(NEW.target->'prior_pair')<>2
        OR NOT EXISTS(SELECT 1 FROM canonical_store.knowledge_node_revisions source_revision
            JOIN canonical_store.knowledge_node_revisions target_revision
                ON target_revision.knode_revision_id::text=NEW.target->'prior_pair'->>1
            WHERE source_revision.knode_revision_id::text=NEW.target->'prior_pair'->>0
                AND source_revision.knode_id::text=target_edge->>'from_knode_id'
                AND target_revision.knode_id::text=target_edge->>'to_knode_id')
    THEN RAISE EXCEPTION 'N2E review fence must precede context freeze and bind exact current endpoints, semantic target and support'; END IF;
    SELECT jsonb_build_object('event_id',applicability_event_id::text,'applicable',applicable) INTO prior_event
        FROM canonical_store.knowledge_edge_applicability_events WHERE semantic_kedge_revision_id=NEW.semantic_kedge_revision_id
            AND from_knode_revision_id::text=NEW.target->'prior_pair'->>0
            AND to_knode_revision_id::text=NEW.target->'prior_pair'->>1 ORDER BY event_order DESC LIMIT 1;
    IF NEW.target->>'prior_basis_event_id' IS DISTINCT FROM prior_event->>'event_id'
        OR NEW.target->'prior_applicable' IS DISTINCT FROM COALESCE(prior_event->'applicable',
            (CASE WHEN NEW.target->'prior_pair'=jsonb_build_array(target_edge->'from_knode_revision_id',target_edge->'to_knode_revision_id')
                THEN 'true'::jsonb ELSE 'null'::jsonb END))
    THEN RAISE EXCEPTION 'N2E prior applicability must retain its actual exact-pair event, original acceptance or unknown basis'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER n2e_review_target_guard BEFORE INSERT ON compiler_runtime.n2e_review_targets
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_n2e_review_target();

CREATE FUNCTION compiler_runtime.check_n2e_review_context() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE context_row compiler_runtime.k_execution_contexts; modern boolean; frozen compiler_runtime.n2e_review_targets;
BEGIN
    SELECT * INTO STRICT context_row FROM compiler_runtime.k_execution_contexts WHERE execution_id=NEW.execution_id;
    modern:=compiler_runtime.is_n2e_relations(NEW.execution_id);
    IF NOT modern AND NOT context_row.input_snapshot ? 'edge_review_target'
        AND NOT context_row.input_snapshot ? 'n2e_policy' THEN RETURN NULL; END IF;
    IF NOT modern OR context_row.input_snapshot->>'n2e_policy' IS DISTINCT FROM 'n2e-relations-v1'
    THEN RAISE EXCEPTION 'Modern N2E profile and snapshot markers must match'; END IF;
    IF context_row.input_snapshot ? 'edge_review_target' THEN
        SELECT * INTO frozen FROM compiler_runtime.n2e_review_targets WHERE execution_id=NEW.execution_id;
        IF frozen.execution_id IS NULL OR frozen.target IS DISTINCT FROM context_row.input_snapshot->'edge_review_target'
            OR context_row.expected_state_version<frozen.fence_order
        THEN RAISE EXCEPTION 'N2E context must freeze after its own exact review fence'; END IF;
    ELSIF EXISTS(SELECT 1 FROM compiler_runtime.n2e_review_targets WHERE execution_id=NEW.execution_id) THEN
        RAISE EXCEPTION 'A review fence cannot be omitted from the frozen N2E input';
    END IF;
    IF EXISTS(SELECT 1 FROM compiler_runtime.k_input_information WHERE execution_id=NEW.execution_id)
        OR NOT EXISTS(SELECT 1 FROM compiler_runtime.k_input_node_revisions WHERE execution_id=NEW.execution_id)
        OR EXISTS(SELECT 1 FROM compiler_runtime.k_input_node_revisions x WHERE x.execution_id=NEW.execution_id
            AND NOT compiler_runtime.current_k2k_premise(x.node_revision_id))
    THEN RAISE EXCEPTION 'N2E consumes accepted usable exact K endpoints, never fabricated I or source repair'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER n2e_review_context_commit AFTER INSERT ON compiler_runtime.k_execution_contexts
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_n2e_review_context();
CREATE CONSTRAINT TRIGGER n2e_review_fence_commit AFTER INSERT ON compiler_runtime.n2e_review_targets
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_n2e_review_context();

CREATE FUNCTION canonical_store.guard_n2e_revision_body() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_record compiler_runtime.k_compilation_records; logical_edge canonical_store.knowledge_edges; candidate jsonb;
BEGIN
    SELECT * INTO STRICT actual_record FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.origin_record_id;
    SELECT * INTO STRICT logical_edge FROM canonical_store.knowledge_edges WHERE kedge_id=NEW.kedge_id;
    IF NOT compiler_runtime.is_n2e_relations(actual_record.execution_id) THEN
        IF logical_edge.predicate<>'supports' THEN RAISE EXCEPTION 'New predicates require the versioned N2E relation profile'; END IF;
        RETURN NEW;
    END IF;
    SELECT body INTO candidate FROM compiler_runtime.k_temporary_candidates WHERE record_id=actual_record.record_id;
    IF actual_record.record_type<>'n2e' OR actual_record.disposition NOT IN ('pending','needs_human')
        OR candidate IS NULL OR candidate->>'role' IS DISTINCT FROM 'relation'
        OR candidate->>'predicate' IS DISTINCT FROM logical_edge.predicate
        OR candidate->>'from_revision_id' IS DISTINCT FROM NEW.from_knode_revision_id::text
        OR candidate->>'to_revision_id' IS DISTINCT FROM NEW.to_knode_revision_id::text
        OR candidate->>'comparison_base_revision_id' IS DISTINCT FROM NEW.supersedes_revision_id::text
        OR candidate->'qualifiers' IS DISTINCT FROM NEW.qualifiers
        OR candidate->>'rationale' IS DISTINCT FROM NEW.rationale
        OR NEW.semantic_payload IS DISTINCT FROM jsonb_build_object('predicate',logical_edge.predicate)
        OR candidate->>'identity_fingerprint' IS DISTINCT FROM NEW.identity_fingerprint
        OR candidate->>'content_fingerprint' IS DISTINCT FROM NEW.content_fingerprint
        OR NOT compiler_runtime.current_k2k_premise(NEW.from_knode_revision_id)
        OR NOT compiler_runtime.current_k2k_premise(NEW.to_knode_revision_id)
    THEN RAISE EXCEPTION 'Modern N2E revisions must match their exact staged relation, comparison base and usable endpoints'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER n2e_revision_body_guard BEFORE INSERT ON canonical_store.knowledge_edge_revisions
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_n2e_revision_body();

CREATE FUNCTION compiler_runtime.guard_n2e_review_decision() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_record compiler_runtime.k_compilation_records; candidate jsonb; target_row compiler_runtime.n2e_review_targets;
        published boolean; review jsonb;
BEGIN
    SELECT * INTO STRICT actual_record FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.record_id;
    SELECT body INTO candidate FROM compiler_runtime.k_temporary_candidates WHERE record_id=NEW.record_id;
    published:=NEW.action IN ('accepted_new','accepted_revision','reused','no_material_delta');
    IF actual_record.execution_id<>NEW.execution_id OR actual_record.record_type<>'n2e'
        OR NOT compiler_runtime.is_n2e_relations(NEW.execution_id)
        OR actual_record.disposition NOT IN ('pending','needs_human') OR candidate IS NULL
        OR NOT EXISTS(SELECT 1 FROM compiler_runtime.operation_executions WHERE execution_id=NEW.execution_id AND state='proposed')
        OR candidate->>'candidate_key' IS DISTINCT FROM NEW.candidate_key OR candidate->>'role' IS DISTINCT FROM NEW.role
        OR (NEW.role='target_assessment') IS DISTINCT FROM (NEW.candidate_key='review_existing_relation')
        OR NEW.validation->>'candidate_key' IS DISTINCT FROM NEW.candidate_key
        OR NEW.validation->'comparison_base_revision_id' IS DISTINCT FROM candidate->'comparison_base_revision_id'
        OR COALESCE(NEW.validation->>'verdict','') NOT IN ('accepted','rejected','needs_human')
        OR jsonb_typeof(NEW.validation->'relation_valid') IS DISTINCT FROM 'boolean'
        OR jsonb_typeof(NEW.validation->'scope_compatible') IS DISTINCT FROM 'boolean'
        OR COALESCE(jsonb_typeof(NEW.validation->'material_change'),'') NOT IN ('boolean','null')
        OR jsonb_typeof(NEW.validation->'reason_codes') IS DISTINCT FROM 'array'
        OR jsonb_array_length(NEW.validation->'reason_codes')=0 OR COALESCE(length(btrim(NEW.validation->>'reason')),0)=0
        OR NEW.validation ?| ARRAY['_n2e_candidate','_n2e_candidate_sha256']
        OR (NEW.action='rejected' AND NEW.validation->>'verdict'<>'rejected')
        OR (NOT published AND (NEW.material_change OR NEW.before_applicable IS NOT NULL OR NEW.after_applicable IS NOT NULL))
    THEN RAISE EXCEPTION 'N2E decisions require the exact staged candidate and independent normalized verdict'; END IF;
    IF published THEN
        IF NEW.validation->>'verdict' IS DISTINCT FROM 'accepted'
            OR NEW.validation->'relation_valid' IS DISTINCT FROM 'true'::jsonb
            OR NEW.validation->'scope_compatible' IS DISTINCT FROM 'true'::jsonb
            OR NEW.after_applicable IS NULL
        THEN RAISE EXCEPTION 'Published N2E relations require independent relation and scope acceptance'; END IF;
        IF NEW.role='target_assessment' THEN
            SELECT * INTO target_row FROM compiler_runtime.n2e_review_targets WHERE execution_id=NEW.execution_id;
            review:=NEW.validation->'applicability_review';
            IF target_row.execution_id IS NULL OR NEW.action<>'no_material_delta'
                OR candidate->>'comparison_base_revision_id' IS DISTINCT FROM target_row.semantic_kedge_revision_id::text
                OR candidate->>'predicate' IS DISTINCT FROM target_row.target->'target'->>'predicate'
                OR candidate->'qualifiers' IS DISTINCT FROM target_row.target->'target'->'qualifiers'
                OR candidate->>'from_revision_id' IS DISTINCT FROM target_row.from_knode_revision_id::text
                OR candidate->>'to_revision_id' IS DISTINCT FROM target_row.to_knode_revision_id::text
                OR review->'confirmed' IS DISTINCT FROM 'true'::jsonb
                OR review->'applicable' IS DISTINCT FROM to_jsonb(NEW.after_applicable)
                OR COALESCE(to_jsonb(NEW.before_applicable),'null'::jsonb) IS DISTINCT FROM target_row.target->'prior_applicable'
                OR NEW.material_change IS DISTINCT FROM (NEW.before_applicable IS DISTINCT FROM NEW.after_applicable)
            THEN RAISE EXCEPTION 'Existing relation assessment must preserve its exact target and explicit true/false/unknown prior basis'; END IF;
        ELSE
            IF NEW.action NOT IN ('accepted_new','accepted_revision','reused') OR NOT NEW.after_applicable
                OR jsonb_typeof(NEW.validation->'material_change') IS DISTINCT FROM 'boolean'
                OR (NEW.action='accepted_new' AND (candidate->>'comparison_base_revision_id' IS NOT NULL OR NOT NEW.material_change
                    OR NEW.validation->'material_change' IS DISTINCT FROM 'true'::jsonb))
                OR (NEW.action='accepted_revision' AND (candidate->>'comparison_base_revision_id' IS NULL
                    OR NEW.validation->'material_change' IS DISTINCT FROM 'true'::jsonb OR NOT NEW.material_change))
                OR (NEW.action='reused' AND (candidate->>'comparison_base_revision_id' IS NULL
                    OR NEW.validation->'material_change' IS DISTINCT FROM 'false'::jsonb
                    OR NEW.material_change IS DISTINCT FROM (NEW.before_applicable IS DISTINCT FROM true)))
            THEN RAISE EXCEPTION 'N2E identity/materiality must distinguish new relation, exact successor and equivalent reuse'; END IF;
        END IF;
        -- This DB-owned witness remains after temporary candidate cleanup. It
        -- contains only accepted relation content; rejected content is hash-only.
        NEW.validation:=NEW.validation||jsonb_build_object('_n2e_candidate',candidate-ARRAY['rationale','uncertainties']);
    END IF;
    NEW.validation:=NEW.validation||jsonb_build_object('_n2e_candidate_sha256',encode(sha256(convert_to(candidate::text,'UTF8')),'hex'));
    RETURN NEW;
END; $$;
CREATE TRIGGER n2e_review_decision_guard BEFORE INSERT ON compiler_runtime.n2e_review_decisions
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_n2e_review_decision();

CREATE FUNCTION canonical_store.guard_n2e_applicability_detail() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_execution uuid; context_nodes jsonb; expected_signatures jsonb;
BEGIN
    SELECT execution_id INTO STRICT actual_execution FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.origin_record_id;
    IF NOT compiler_runtime.is_n2e_relations(actual_execution) THEN
        IF NEW.detail<>'{}'::jsonb THEN RAISE EXCEPTION 'Legacy applicability retains its legacy evidence profile'; END IF;
        RETURN NEW;
    END IF;
    SELECT input_snapshot->'input'->'nodes' INTO STRICT context_nodes
        FROM compiler_runtime.k_execution_contexts WHERE execution_id=actual_execution;
    expected_signatures:=jsonb_build_array(
        canonical_store.current_knowledge_support_signature(NEW.from_knode_revision_id),
        canonical_store.current_knowledge_support_signature(NEW.to_knode_revision_id));
    IF NEW.detail->>'n2e_policy' IS DISTINCT FROM 'n2e-relations-v1'
        OR NEW.detail->'endpoint_support_signatures' IS DISTINCT FROM expected_signatures
        OR NEW.detail->'endpoint_support_record_ids' IS DISTINCT FROM jsonb_build_array(
            canonical_store.current_k_support_record(NEW.from_knode_revision_id)::text,
            canonical_store.current_k_support_record(NEW.to_knode_revision_id)::text)
        OR NOT compiler_runtime.current_k2k_premise(NEW.from_knode_revision_id)
        OR NOT compiler_runtime.current_k2k_premise(NEW.to_knode_revision_id)
        OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(context_nodes) node
            WHERE node->>'knode_revision_id'=NEW.from_knode_revision_id::text
                AND node->>'current_support_signature'=expected_signatures->>0)
        OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(context_nodes) node
            WHERE node->>'knode_revision_id'=NEW.to_knode_revision_id::text
                AND node->>'current_support_signature'=expected_signatures->>1)
    THEN RAISE EXCEPTION 'Modern applicability binds actual delivered and current endpoint support, including transitive support changes'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER n2e_applicability_detail_guard BEFORE INSERT ON canonical_store.knowledge_edge_applicability_events
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_n2e_applicability_detail();

CREATE OR REPLACE FUNCTION canonical_store.check_k_applicability_commit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_record compiler_runtime.k_compilation_records;
BEGIN
    SELECT * INTO STRICT actual_record FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.origin_record_id;
    IF compiler_runtime.is_n2e_relations(actual_record.execution_id) THEN
        IF actual_record.record_type<>'n2e' OR actual_record.disposition NOT IN ('accepted_new','accepted_revision','reused','no_material_delta')
            OR actual_record.result_edge_revision_id IS DISTINCT FROM NEW.semantic_kedge_revision_id
            OR actual_record.result_edge_id IS DISTINCT FROM NEW.kedge_id
            OR NOT EXISTS(SELECT 1 FROM compiler_runtime.n2e_review_decisions decision WHERE decision.record_id=actual_record.record_id
                AND decision.action=actual_record.disposition AND decision.after_applicable=NEW.applicable)
        THEN RAISE EXCEPTION 'Modern applicability requires its own resolved N2E result and confirmed independent decision'; END IF;
    ELSIF actual_record.record_type<>'n2e' OR actual_record.disposition NOT IN ('no_material_delta','reused')
        OR actual_record.result_edge_revision_id IS DISTINCT FROM NEW.semantic_kedge_revision_id THEN
        RAISE EXCEPTION 'Applicability requires a resolved N2E Record and exact endpoint inputs';
    END IF;
    IF NOT EXISTS(SELECT 1 FROM compiler_runtime.k_input_node_revisions WHERE execution_id=actual_record.execution_id
        AND node_revision_id=NEW.from_knode_revision_id)
        OR NOT EXISTS(SELECT 1 FROM compiler_runtime.k_input_node_revisions WHERE execution_id=actual_record.execution_id
        AND node_revision_id=NEW.to_knode_revision_id)
    THEN RAISE EXCEPTION 'Applicability requires exact authoritative endpoint inputs'; END IF;
    RETURN NULL;
END; $$;

CREATE FUNCTION compiler_runtime.check_n2e_record_commit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_record compiler_runtime.k_compilation_records; decision compiler_runtime.n2e_review_decisions;
        context_row compiler_runtime.k_execution_contexts; candidate jsonb; target_row compiler_runtime.n2e_review_targets;
        result_revision canonical_store.knowledge_edge_revisions; logical_edge canonical_store.knowledge_edges;
        delivered jsonb;
BEGIN
    SELECT * INTO STRICT actual_record FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.record_id;
    IF NOT compiler_runtime.is_n2e_relations(actual_record.execution_id) OR actual_record.disposition='pending' THEN RETURN NULL; END IF;
    SELECT * INTO decision FROM compiler_runtime.n2e_review_decisions WHERE record_id=actual_record.record_id;
    SELECT * INTO STRICT context_row FROM compiler_runtime.k_execution_contexts WHERE execution_id=actual_record.execution_id;
    IF decision.record_id IS NULL OR decision.action IS DISTINCT FROM actual_record.disposition
        OR decision.execution_id<>actual_record.execution_id
    THEN RAISE EXCEPTION 'Every resolved modern N2E Record requires its exact immutable decision'; END IF;
    SELECT jsonb_agg(node_revision_id::text ORDER BY ordinal) INTO delivered
        FROM compiler_runtime.k_input_node_revisions WHERE execution_id=actual_record.execution_id;
    IF NOT EXISTS(SELECT 1 FROM compiler_runtime.k_model_calls generator
        JOIN compiler_runtime.k_model_calls validator ON validator.execution_id=generator.execution_id
        WHERE generator.execution_id=actual_record.execution_id AND generator.phase='generator' AND validator.phase='validator'
            AND generator.status='succeeded' AND validator.status='succeeded'
            AND generator.profile_id=context_row.generator_profile_id AND validator.profile_id=context_row.validator_profile_id
            AND length(btrim(generator.provider_ref))>0 AND length(btrim(validator.provider_ref))>0
            AND generator.provider_ref<>validator.provider_ref
            AND generator.receipt->'actual_delivery'='true'::jsonb AND validator.receipt->'actual_delivery'='true'::jsonb
            AND generator.receipt->'delivered_knowledge_revision_ids'=delivered
            AND validator.receipt->'delivered_knowledge_revision_ids'=delivered
            AND (NOT context_row.input_snapshot ? 'edge_review_target' OR (
                generator.receipt->>'delivered_edge_review_target_sha256'=context_row.input_snapshot->'edge_review_target'->>'target_sha256'
                AND validator.receipt->>'delivered_edge_review_target_sha256'=context_row.input_snapshot->'edge_review_target'->>'target_sha256')))
    THEN RAISE EXCEPTION 'Modern N2E decisions require actual independent delivery of all exact inputs and any review target'; END IF;
    IF actual_record.disposition IN ('rejected','needs_human') THEN
        IF EXISTS(SELECT 1 FROM canonical_store.knowledge_edge_applicability_events WHERE origin_record_id=actual_record.record_id)
            OR EXISTS(SELECT 1 FROM canonical_store.knowledge_edge_revisions WHERE origin_record_id=actual_record.record_id)
            OR EXISTS(SELECT 1 FROM compiler_runtime.k_outbox WHERE record_id=actual_record.record_id)
        THEN RAISE EXCEPTION 'Unresolved or rejected relation decisions cannot publish canonical effects'; END IF;
        RETURN NULL;
    END IF;
    candidate:=decision.validation->'_n2e_candidate';
    SELECT * INTO result_revision FROM canonical_store.knowledge_edge_revisions WHERE kedge_revision_id=actual_record.result_edge_revision_id;
    SELECT * INTO logical_edge FROM canonical_store.knowledge_edges WHERE kedge_id=actual_record.result_edge_id;
    IF candidate IS NULL OR result_revision.kedge_revision_id IS NULL OR logical_edge.kedge_id IS NULL
        OR result_revision.kedge_id<>logical_edge.kedge_id
        OR (logical_edge.current_revision_id<>result_revision.kedge_revision_id AND NOT (
            decision.role='target_assessment' AND EXISTS(
                SELECT 1 FROM compiler_runtime.n2e_review_decisions replacement
                JOIN compiler_runtime.k_compilation_records replacement_record USING(record_id)
                JOIN canonical_store.knowledge_edge_revisions successor
                    ON successor.kedge_revision_id=replacement_record.result_edge_revision_id
                WHERE replacement.execution_id=actual_record.execution_id AND replacement.role='relation'
                    AND replacement.action='accepted_revision' AND replacement_record.disposition='accepted_revision'
                    AND successor.kedge_id=logical_edge.kedge_id AND successor.kedge_revision_id=logical_edge.current_revision_id
                    AND successor.supersedes_revision_id=result_revision.kedge_revision_id)))
        OR candidate->>'predicate' IS DISTINCT FROM logical_edge.predicate
        OR candidate->>'identity_fingerprint' IS DISTINCT FROM logical_edge.identity_fingerprint
        OR NOT EXISTS(SELECT 1 FROM canonical_store.knowledge_node_revisions source_revision
            JOIN canonical_store.knowledge_node_revisions target_revision
                ON target_revision.knode_revision_id::text=candidate->>'to_revision_id'
            WHERE source_revision.knode_revision_id::text=candidate->>'from_revision_id'
                AND source_revision.knode_id=logical_edge.from_knode_id AND target_revision.knode_id=logical_edge.to_knode_id)
        OR NOT compiler_runtime.current_k2k_premise((candidate->>'from_revision_id')::uuid)
        OR NOT compiler_runtime.current_k2k_premise((candidate->>'to_revision_id')::uuid)
        OR NOT EXISTS(SELECT 1 FROM canonical_store.knowledge_edge_applicability_events event
            WHERE event.origin_record_id=actual_record.record_id AND event.kedge_id=logical_edge.kedge_id
                AND event.semantic_kedge_revision_id=result_revision.kedge_revision_id
                AND event.from_knode_revision_id::text=candidate->>'from_revision_id'
                AND event.to_knode_revision_id::text=candidate->>'to_revision_id'
                AND event.applicable=decision.after_applicable AND event.detail->>'n2e_policy'='n2e-relations-v1')
    THEN RAISE EXCEPTION 'Accepted N2E result must preserve its exact logical relation, usable endpoints and supported applicability event'; END IF;
    IF actual_record.disposition IN ('accepted_new','accepted_revision') THEN
        IF result_revision.origin_record_id<>actual_record.record_id
            OR result_revision.semantic_payload IS DISTINCT FROM jsonb_build_object('predicate',candidate->>'predicate')
            OR result_revision.qualifiers IS DISTINCT FROM candidate->'qualifiers'
            OR result_revision.content_fingerprint IS DISTINCT FROM candidate->>'content_fingerprint'
            OR result_revision.supersedes_revision_id::text IS DISTINCT FROM candidate->>'comparison_base_revision_id'
            OR NOT decision.material_change
        THEN RAISE EXCEPTION 'A new relation revision must match the validated semantic proposal and exact comparison base'; END IF;
    ELSE
        IF result_revision.kedge_revision_id::text IS DISTINCT FROM candidate->>'comparison_base_revision_id'
        THEN RAISE EXCEPTION 'Same-meaning relation support preserves the existing semantic revision'; END IF;
    END IF;
    IF decision.role='target_assessment' THEN
        SELECT * INTO STRICT target_row FROM compiler_runtime.n2e_review_targets WHERE execution_id=actual_record.execution_id;
        IF actual_record.result_edge_revision_id<>target_row.semantic_kedge_revision_id
        THEN RAISE EXCEPTION 'An old relation assessment cannot be laundered into the new predicate result'; END IF;
    END IF;
    IF decision.material_change AND NOT EXISTS(SELECT 1 FROM compiler_runtime.k_outbox
        WHERE record_id=actual_record.record_id AND operation='k2k')
        OR EXISTS(SELECT 1 FROM compiler_runtime.k_outbox WHERE record_id=actual_record.record_id AND operation<>'k2k')
    THEN RAISE EXCEPTION 'N2E material relation effects and their downstream obligation must commit together'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER n2e_record_commit_guard AFTER INSERT OR UPDATE ON compiler_runtime.k_compilation_records
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_n2e_record_commit();
CREATE CONSTRAINT TRIGGER n2e_decision_commit_guard AFTER INSERT ON compiler_runtime.n2e_review_decisions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_n2e_record_commit();

CREATE FUNCTION compiler_runtime.check_n2e_review_completion() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.state IN ('completed','zero_output') AND compiler_runtime.is_n2e_relations(NEW.execution_id)
        AND EXISTS(SELECT 1 FROM compiler_runtime.n2e_review_targets WHERE execution_id=NEW.execution_id)
        AND NOT EXISTS(SELECT 1 FROM compiler_runtime.n2e_review_decisions decision
            JOIN compiler_runtime.k_compilation_records r USING(record_id)
            WHERE decision.execution_id=NEW.execution_id AND decision.role='target_assessment'
                AND decision.action='no_material_delta' AND r.disposition='no_material_delta'
                AND decision.after_applicable IS NOT NULL)
    THEN RAISE EXCEPTION 'An explicit old-relation review remains unresolved until a confirmed applicability assessment exists'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER n2e_review_completion_guard AFTER UPDATE ON compiler_runtime.operation_executions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_n2e_review_completion();

CREATE FUNCTION canonical_store.check_composes_acyclic() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE logical_edge canonical_store.knowledge_edges;
BEGIN
    SELECT * INTO STRICT logical_edge FROM canonical_store.knowledge_edges WHERE kedge_id=NEW.kedge_id;
    IF logical_edge.predicate<>'composes'
        OR canonical_store.current_knowledge_edge_applicability(logical_edge.current_revision_id)<>'applicable'
    THEN RETURN NULL; END IF;
    IF EXISTS(WITH RECURSIVE reachable(node_id) AS (
        SELECT logical_edge.to_knode_id UNION
        SELECT e.to_knode_id FROM reachable path JOIN canonical_store.knowledge_edges e ON e.from_knode_id=path.node_id
            WHERE e.predicate='composes' AND e.kedge_id<>logical_edge.kedge_id
                AND canonical_store.current_knowledge_edge_applicability(e.current_revision_id)='applicable')
        SELECT 1 FROM reachable WHERE node_id=logical_edge.from_knode_id)
    THEN RAISE EXCEPTION 'Current usable applicable proper-component relations must be acyclic'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER composes_revision_acyclic AFTER INSERT ON canonical_store.knowledge_edge_revisions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION canonical_store.check_composes_acyclic();
CREATE CONSTRAINT TRIGGER composes_applicability_acyclic AFTER INSERT ON canonical_store.knowledge_edge_applicability_events
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION canonical_store.check_composes_acyclic();

DO $$ DECLARE relation text; BEGIN
    FOREACH relation IN ARRAY ARRAY['compiler_runtime.n2e_review_targets','compiler_runtime.n2e_review_decisions'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON %s FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
        EXECUTE format('CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON %s FOR EACH STATEMENT EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
    END LOOP;
END; $$;
GRANT SELECT,INSERT ON compiler_runtime.n2e_review_targets,compiler_runtime.n2e_review_decisions TO palimpsest;
