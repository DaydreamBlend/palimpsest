-- Effective K2K consumes complete endpoint values plus immutable relation refs.
-- Existing node-only profiles, source routes and 0001-0019 remain unchanged.
CREATE TABLE compiler_runtime.k_input_effective_edges (
    execution_id uuid NOT NULL REFERENCES compiler_runtime.k_execution_contexts,
    ordinal integer NOT NULL CHECK (ordinal>=0),
    kedge_id uuid NOT NULL REFERENCES canonical_store.knowledge_edges,
    semantic_kedge_revision_id uuid NOT NULL,
    from_knode_revision_id uuid NOT NULL REFERENCES canonical_store.knowledge_node_revisions,
    to_knode_revision_id uuid NOT NULL REFERENCES canonical_store.knowledge_node_revisions,
    basis_type text NOT NULL CHECK (basis_type IN ('origin_acceptance','applicability_event')),
    basis_origin_record_id uuid NOT NULL REFERENCES compiler_runtime.k_compilation_records,
    applicability_event_id uuid REFERENCES canonical_store.knowledge_edge_applicability_events,
    relation_read_state_token text NOT NULL CHECK (relation_read_state_token ~ '^[0-9a-f]{64}$'),
    from_support_signature text NOT NULL CHECK (from_support_signature ~ '^[0-9a-f]{64}$'),
    to_support_signature text NOT NULL CHECK (to_support_signature ~ '^[0-9a-f]{64}$'),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
    PRIMARY KEY(execution_id,ordinal), UNIQUE(execution_id,semantic_kedge_revision_id),
    FOREIGN KEY(semantic_kedge_revision_id,kedge_id)
        REFERENCES canonical_store.knowledge_edge_revisions(kedge_revision_id,kedge_id),
    CHECK ((basis_type='applicability_event')=(applicability_event_id IS NOT NULL)),
    CHECK (from_knode_revision_id<>to_knode_revision_id)
);
CREATE INDEX k_effective_edge_logical ON compiler_runtime.k_input_effective_edges(kedge_id);
CREATE INDEX k_effective_edge_semantic ON compiler_runtime.k_input_effective_edges(semantic_kedge_revision_id);
CREATE TABLE canonical_store.knowledge_derivation_edge_premises (
    record_id uuid NOT NULL REFERENCES canonical_store.knowledge_derivations,
    ordinal integer NOT NULL CHECK (ordinal>=0),
    execution_id uuid NOT NULL,
    input_ordinal integer NOT NULL CHECK (input_ordinal>=0),
    PRIMARY KEY(record_id,ordinal), UNIQUE(record_id,execution_id,input_ordinal),
    FOREIGN KEY(execution_id,input_ordinal) REFERENCES compiler_runtime.k_input_effective_edges(execution_id,ordinal)
);
CREATE INDEX knowledge_derivation_edge_input ON canonical_store.knowledge_derivation_edge_premises(execution_id,input_ordinal);

CREATE FUNCTION compiler_runtime.is_effective_k2k(id uuid) RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT EXISTS(SELECT 1 FROM compiler_runtime.operation_executions e
        JOIN compiler_runtime.profiles p USING(profile_id) WHERE e.execution_id=id
            AND e.operation='k2k' AND p.payload->>'schema_version'='knowledge-inference-effective-v1')
$$;
CREATE OR REPLACE FUNCTION compiler_runtime.is_k2k_execution(id uuid) RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT EXISTS(SELECT 1 FROM compiler_runtime.operation_executions e
        JOIN compiler_runtime.profiles p USING(profile_id) WHERE e.execution_id=id AND e.operation='k2k'
            AND p.payload->>'schema_version' IN ('knowledge-inference-v1','knowledge-inference-effective-v1'))
$$;

-- Local relation check only. The caller walks all delivered endpoint Node
-- premises, avoiding Node -> Edge resolver -> Node mutual recursion.
CREATE FUNCTION compiler_runtime.k2k_effective_edge_current(edge_input compiler_runtime.k_input_effective_edges)
RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE selected record; basis_event canonical_store.knowledge_edge_applicability_events;
        basis_nodes jsonb; endpoint uuid; stored_signature text; basis_record uuid;
BEGIN
    SELECT e.current_revision_id,v.from_knode_revision_id AS original_from,v.to_knode_revision_id AS original_to,
        source_node.current_revision_id AS current_from,target_node.current_revision_id AS current_to,
        v.origin_record_id,r.disposition,r.result_edge_id,r.result_edge_revision_id
        INTO selected FROM canonical_store.knowledge_edge_revisions v
        JOIN canonical_store.knowledge_edges e USING(kedge_id)
        JOIN canonical_store.knowledge_nodes source_node ON source_node.knode_id=e.from_knode_id
        JOIN canonical_store.knowledge_nodes target_node ON target_node.knode_id=e.to_knode_id
        JOIN compiler_runtime.k_compilation_records r ON r.record_id=v.origin_record_id
        WHERE v.kedge_revision_id=edge_input.semantic_kedge_revision_id AND v.kedge_id=edge_input.kedge_id;
    IF NOT FOUND OR selected.current_revision_id IS DISTINCT FROM edge_input.semantic_kedge_revision_id
        OR selected.current_from IS DISTINCT FROM edge_input.from_knode_revision_id
        OR selected.current_to IS DISTINCT FROM edge_input.to_knode_revision_id
        OR selected.disposition NOT IN ('accepted_new','accepted_revision')
        OR selected.result_edge_id IS DISTINCT FROM edge_input.kedge_id
        OR selected.result_edge_revision_id IS DISTINCT FROM edge_input.semantic_kedge_revision_id
        OR compiler_runtime.n2e_review_pending(edge_input.semantic_kedge_revision_id,
            edge_input.from_knode_revision_id,edge_input.to_knode_revision_id)
        OR edge_input.from_support_signature IS DISTINCT FROM canonical_store.current_knowledge_support_signature(edge_input.from_knode_revision_id)
        OR edge_input.to_support_signature IS DISTINCT FROM canonical_store.current_knowledge_support_signature(edge_input.to_knode_revision_id)
    THEN RETURN false; END IF;
    SELECT * INTO basis_event FROM canonical_store.knowledge_edge_applicability_events
        WHERE semantic_kedge_revision_id=edge_input.semantic_kedge_revision_id
            AND from_knode_revision_id=edge_input.from_knode_revision_id
            AND to_knode_revision_id=edge_input.to_knode_revision_id ORDER BY event_order DESC LIMIT 1;
    IF FOUND THEN
        IF edge_input.basis_type<>'applicability_event' OR NOT basis_event.applicable
            OR basis_event.applicability_event_id IS DISTINCT FROM edge_input.applicability_event_id
            OR basis_event.origin_record_id IS DISTINCT FROM edge_input.basis_origin_record_id
        THEN RETURN false; END IF;
        IF basis_event.detail->>'n2e_policy'='n2e-relations-v1' THEN
            RETURN COALESCE(basis_event.detail->'endpoint_support_signatures'=jsonb_build_array(
                edge_input.from_support_signature,edge_input.to_support_signature),false);
        END IF;
        basis_record:=basis_event.origin_record_id;
    ELSE
        IF edge_input.basis_type<>'origin_acceptance' OR edge_input.applicability_event_id IS NOT NULL
            OR edge_input.basis_origin_record_id IS DISTINCT FROM selected.origin_record_id
            OR selected.original_from IS DISTINCT FROM edge_input.from_knode_revision_id
            OR selected.original_to IS DISTINCT FROM edge_input.to_knode_revision_id
            OR compiler_runtime.is_n2e_relations((SELECT execution_id FROM compiler_runtime.k_compilation_records
                WHERE record_id=selected.origin_record_id))
        THEN RETURN false; END IF;
        basis_record:=selected.origin_record_id;
    END IF;
    -- Preserve the same conservative compatibility behavior as the N2E resolver.
    SELECT c.input_snapshot->'input'->'nodes' INTO basis_nodes
        FROM compiler_runtime.k_compilation_records r JOIN compiler_runtime.k_execution_contexts c USING(execution_id)
        WHERE r.record_id=basis_record;
    FOREACH endpoint IN ARRAY ARRAY[edge_input.from_knode_revision_id,edge_input.to_knode_revision_id] LOOP
        SELECT node->>'current_support_signature' INTO stored_signature
            FROM jsonb_array_elements(COALESCE(basis_nodes,'[]'::jsonb)) node WHERE node->>'knode_revision_id'=endpoint::text;
        IF (stored_signature IS NOT NULL AND stored_signature<>canonical_store.current_knowledge_support_signature(endpoint))
            OR (stored_signature IS NULL AND canonical_store.current_k_support_record(endpoint) IS NOT NULL)
        THEN RETURN false; END IF;
    END LOOP;
    RETURN true;
END; $$;
CREATE FUNCTION compiler_runtime.k2k_edge_input_current(execution uuid,input_ordinal integer)
RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT COALESCE((SELECT compiler_runtime.k2k_effective_edge_current(edge_input)
        FROM compiler_runtime.k_input_effective_edges edge_input
        WHERE edge_input.execution_id=execution AND edge_input.ordinal=input_ordinal),false)
$$;

CREATE FUNCTION compiler_runtime.guard_effective_k2k_input() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE context_row compiler_runtime.k_execution_contexts; selected record; expected_ref jsonb;
        current_version bigint; expected_token text;
BEGIN
    SELECT version INTO STRICT current_version FROM compiler_runtime.knowledge_state WHERE singleton FOR UPDATE;
    SELECT * INTO STRICT context_row FROM compiler_runtime.k_execution_contexts WHERE execution_id=NEW.execution_id;
    SELECT e.predicate,v.qualifiers,v.from_knode_revision_id,v.to_knode_revision_id INTO selected
        FROM canonical_store.knowledge_edge_revisions v JOIN canonical_store.knowledge_edges e USING(kedge_id)
        WHERE v.kedge_revision_id=NEW.semantic_kedge_revision_id AND v.kedge_id=NEW.kedge_id;
    expected_ref:=jsonb_build_object('semantic_kedge_revision_id',NEW.semantic_kedge_revision_id::text,
        'from_knode_revision_id',NEW.from_knode_revision_id::text,'to_knode_revision_id',NEW.to_knode_revision_id::text,
        'applicability_basis_type',NEW.basis_type,'applicability_basis_ref',
            COALESCE(NEW.applicability_event_id,NEW.basis_origin_record_id)::text,
        'relation_read_state_token',NEW.relation_read_state_token);
    -- These fields are UUID/SHA/integer/null, so this fixed compact encoding is
    -- exactly edge_projection's sorted JSON read-state digest, without rewriting it.
    expected_token:=encode(sha256(convert_to(format(
        '{"applicability_status":"applicable","endpoint_support_signatures":["%s","%s"],"knowledge_state_version":%s,"pending_execution_id":null,"pending_fence_order":null}',
        NEW.from_support_signature,NEW.to_support_signature,context_row.expected_state_version),'UTF8')),'hex');
    IF NOT compiler_runtime.is_effective_k2k(NEW.execution_id)
        OR NOT EXISTS(SELECT 1 FROM compiler_runtime.operation_executions WHERE execution_id=NEW.execution_id AND state='prepared')
        OR context_row.expected_state_version IS DISTINCT FROM current_version
        OR NEW.relation_read_state_token IS DISTINCT FROM expected_token
        OR NEW.payload IS DISTINCT FROM context_row.input_snapshot->'input'->'effective_edges'->NEW.ordinal
        OR NEW.payload IS DISTINCT FROM jsonb_build_object('kedge_id',NEW.kedge_id::text,'predicate',selected.predicate,
            'qualifiers',selected.qualifiers,'original_from_revision_id',selected.from_knode_revision_id::text,
            'original_to_revision_id',selected.to_knode_revision_id::text,'effective_edge_ref',expected_ref,
            'endpoint_support_signatures',jsonb_build_array(NEW.from_support_signature,NEW.to_support_signature))
        OR NOT compiler_runtime.k2k_effective_edge_current(NEW)
        OR NOT EXISTS(SELECT 1 FROM compiler_runtime.k_input_node_revisions
            WHERE execution_id=NEW.execution_id AND node_revision_id=NEW.from_knode_revision_id)
        OR NOT EXISTS(SELECT 1 FROM compiler_runtime.k_input_node_revisions
            WHERE execution_id=NEW.execution_id AND node_revision_id=NEW.to_knode_revision_id)
    THEN RAISE EXCEPTION 'Effective K2K input must freeze its actual current relation basis and both delivered endpoint values'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER effective_k2k_input_guard BEFORE INSERT ON compiler_runtime.k_input_effective_edges
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_effective_k2k_input();

CREATE OR REPLACE FUNCTION compiler_runtime.check_k2k_context_commit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_execution compiler_runtime.operation_executions; packet jsonb; effective boolean;
BEGIN
    SELECT * INTO STRICT actual_execution FROM compiler_runtime.operation_executions WHERE execution_id=NEW.execution_id;
    IF actual_execution.operation<>'k2k' THEN RETURN NULL; END IF;
    effective:=compiler_runtime.is_effective_k2k(actual_execution.execution_id);
    SELECT input_snapshot->'input' INTO packet FROM compiler_runtime.k_execution_contexts WHERE execution_id=actual_execution.execution_id;
    IF NOT compiler_runtime.is_k2k_execution(actual_execution.execution_id)
        OR packet->>'schema_version' IS DISTINCT FROM (CASE WHEN effective THEN 'k2k-effective-input-v1' ELSE 'k2k-input-v1' END)
        OR packet->>'data_id' IS DISTINCT FROM actual_execution.data_id
        OR jsonb_typeof(packet->'nodes') IS DISTINCT FROM 'array'
        OR COALESCE(packet->'edges','[]'::jsonb)<>'[]'::jsonb
        OR (SELECT count(*) FROM compiler_runtime.k_input_node_revisions WHERE execution_id=actual_execution.execution_id)<2
        OR jsonb_array_length(packet->'nodes') IS DISTINCT FROM
            (SELECT count(*) FROM compiler_runtime.k_input_node_revisions WHERE execution_id=actual_execution.execution_id)
        OR EXISTS(SELECT 1 FROM compiler_runtime.k_input_information WHERE execution_id=actual_execution.execution_id)
        OR (effective AND (jsonb_typeof(packet->'effective_edges') IS DISTINCT FROM 'array'
            OR jsonb_array_length(packet->'effective_edges')=0
            OR COALESCE(packet->>'input_sha256','') !~ '^[0-9a-f]{64}$'
            OR jsonb_array_length(packet->'effective_edges') IS DISTINCT FROM
                (SELECT count(*) FROM compiler_runtime.k_input_effective_edges WHERE execution_id=actual_execution.execution_id)
            OR NOT EXISTS(SELECT 1 FROM compiler_runtime.profiles WHERE profile_id=actual_execution.profile_id
                AND payload->>'current_support_binding'='knowledge-current-support-v1')))
        OR (NOT effective AND (packet ? 'effective_edges' OR EXISTS(
            SELECT 1 FROM compiler_runtime.k_input_effective_edges WHERE execution_id=actual_execution.execution_id)))
    THEN RAISE EXCEPTION 'K2K requires its frozen input profile, all typed inputs and at least two real Node values'; END IF;
    IF EXISTS(SELECT 1 FROM compiler_runtime.k_input_node_revisions x
        JOIN canonical_store.knowledge_node_revisions v ON v.knode_revision_id=x.node_revision_id
        JOIN canonical_store.knowledge_nodes n USING(knode_id)
        WHERE x.execution_id=actual_execution.execution_id AND (
            packet->'nodes'->x.ordinal->>'knode_revision_id' IS DISTINCT FROM x.node_revision_id::text
            OR packet->'nodes'->x.ordinal->>'knode_id' IS DISTINCT FROM v.knode_id::text
            OR packet->'nodes'->x.ordinal->>'statement' IS DISTINCT FROM v.statement
            OR packet->'nodes'->x.ordinal->'semantic_payload' IS DISTINCT FROM v.semantic_payload
            OR packet->'nodes'->x.ordinal->>'content_fingerprint' IS DISTINCT FROM v.content_fingerprint
            OR packet->'nodes'->x.ordinal->>'kind' IS DISTINCT FROM n.kind
            OR (effective AND (NOT ((packet->'nodes'->x.ordinal) ? 'current_support_record_id')
                OR packet->'nodes'->x.ordinal->>'current_support_record_id' IS DISTINCT FROM canonical_store.current_k_support_record(x.node_revision_id)::text
                OR packet->'nodes'->x.ordinal->>'current_support_signature' IS DISTINCT FROM canonical_store.current_knowledge_support_signature(x.node_revision_id)))
            OR NOT compiler_runtime.current_k2k_premise(x.node_revision_id)))
        OR EXISTS(SELECT 1 FROM compiler_runtime.k_input_effective_edges x WHERE x.execution_id=actual_execution.execution_id
            AND (x.payload IS DISTINCT FROM packet->'effective_edges'->x.ordinal
                OR NOT compiler_runtime.k2k_effective_edge_current(x)))
    THEN RAISE EXCEPTION 'K2K frozen values and effective relations must remain exact accepted current inputs'; END IF;
    IF NOT EXISTS(SELECT 1 FROM compiler_runtime.k_input_node_revisions x
        CROSS JOIN LATERAL canonical_store.derivation_source_data(x.node_revision_id) source(data_id)
        WHERE x.execution_id=actual_execution.execution_id AND source.data_id=actual_execution.data_id)
    THEN RAISE EXCEPTION 'K2K operational Data must occur in its actual transitive source provenance'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER effective_k2k_input_complete AFTER INSERT ON compiler_runtime.k_input_effective_edges
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_k2k_context_commit();

CREATE FUNCTION compiler_runtime.guard_effective_k2k_target() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE prior_edges jsonb; next_edges jsonb; next_refs jsonb; effective boolean;
BEGIN
    IF NEW.snapshot->>'kind' IS DISTINCT FROM 'node' THEN RETURN NEW; END IF;
    effective:=compiler_runtime.is_effective_k2k(NEW.execution_id);
    SELECT jsonb_agg(x.kedge_id::text ORDER BY p.ordinal) INTO prior_edges
        FROM canonical_store.knowledge_derivation_edge_premises p
        JOIN compiler_runtime.k_input_effective_edges x ON x.execution_id=p.execution_id AND x.ordinal=p.input_ordinal
        WHERE p.record_id=(NEW.snapshot->>'prior_support_record_id')::uuid;
    IF prior_edges IS NULL THEN
        IF effective OR NEW.snapshot ? 'effective_edge_refs'
        THEN RAISE EXCEPTION 'Target revalidation cannot invent a different effective-edge support bundle'; END IF;
        RETURN NEW;
    END IF;
    SELECT jsonb_agg(kedge_id::text ORDER BY ordinal),jsonb_agg(payload->'effective_edge_ref' ORDER BY ordinal)
        INTO next_edges,next_refs FROM compiler_runtime.k_input_effective_edges WHERE execution_id=NEW.execution_id;
    IF NOT effective OR next_edges IS DISTINCT FROM prior_edges
        OR NEW.snapshot->'effective_edge_refs' IS DISTINCT FROM next_refs
    THEN RAISE EXCEPTION 'Target revalidation must preserve every previous logical Edge and freeze its exact new effective reference'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER effective_k2k_target_guard BEFORE INSERT ON compiler_runtime.k_revalidation_targets
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_effective_k2k_target();

CREATE FUNCTION canonical_store.guard_effective_k2k_derivation() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_record compiler_runtime.k_compilation_records; candidate jsonb; node_refs jsonb; edge_refs jsonb; effective_refs jsonb;
BEGIN
    SELECT * INTO STRICT actual_record FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.record_id;
    IF NOT compiler_runtime.is_effective_k2k(actual_record.execution_id) THEN
        IF TG_TABLE_NAME='knowledge_derivation_edge_premises' THEN RAISE EXCEPTION 'Legacy K2K cannot add undeclared effective edge premises'; END IF;
        RETURN NEW;
    END IF;
    SELECT body INTO candidate FROM compiler_runtime.k_temporary_candidates WHERE record_id=NEW.record_id;
    SELECT jsonb_agg(node_revision_id::text ORDER BY ordinal) INTO node_refs
        FROM compiler_runtime.k_input_node_revisions WHERE execution_id=actual_record.execution_id;
    SELECT jsonb_agg(semantic_kedge_revision_id::text ORDER BY ordinal),
        jsonb_agg(payload->'effective_edge_ref' ORDER BY ordinal) INTO edge_refs,effective_refs
        FROM compiler_runtime.k_input_effective_edges WHERE execution_id=actual_record.execution_id;
    IF actual_record.record_type<>'k2k' OR actual_record.disposition NOT IN ('pending','needs_human')
        OR NOT EXISTS(SELECT 1 FROM compiler_runtime.operation_executions WHERE execution_id=actual_record.execution_id AND state='proposed')
        OR candidate IS NULL OR candidate->'premise_revision_ids' IS DISTINCT FROM node_refs
        OR candidate->'premise_edge_revision_ids' IS DISTINCT FROM edge_refs
        OR candidate->'premise_effective_edge_refs' IS DISTINCT FROM effective_refs
    THEN RAISE EXCEPTION 'Every effective K2K result must depend on the complete actually delivered Node and Edge bundle'; END IF;
    IF TG_TABLE_NAME='knowledge_derivations' THEN
        IF NEW.validation ?| ARRAY['_premise_edge_revision_ids','_premise_effective_edge_refs']
        THEN RAISE EXCEPTION 'Effective derivation witnesses are owned by the database'; END IF;
        NEW.validation:=NEW.validation||jsonb_build_object('_premise_edge_revision_ids',edge_refs,
            '_premise_effective_edge_refs',effective_refs);
    ELSIF NEW.execution_id IS DISTINCT FROM actual_record.execution_id OR NEW.ordinal IS DISTINCT FROM NEW.input_ordinal
        OR NOT compiler_runtime.k2k_edge_input_current(NEW.execution_id,NEW.input_ordinal)
    THEN RAISE EXCEPTION 'An edge premise must link its own execution and still-current exact delivered input'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER effective_k2k_derivation_guard BEFORE INSERT ON canonical_store.knowledge_derivations
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_effective_k2k_derivation();
CREATE TRIGGER effective_k2k_edge_premise_guard BEFORE INSERT ON canonical_store.knowledge_derivation_edge_premises
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_effective_k2k_derivation();

CREATE FUNCTION canonical_store.check_effective_k2k_derivation() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_record compiler_runtime.k_compilation_records; derivation canonical_store.knowledge_derivations;
        context_row compiler_runtime.k_execution_contexts; node_refs jsonb; edge_refs jsonb; effective_refs jsonb;
BEGIN
    SELECT * INTO STRICT actual_record FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.record_id;
    IF NOT compiler_runtime.is_effective_k2k(actual_record.execution_id) THEN RETURN NULL; END IF;
    SELECT * INTO STRICT derivation FROM canonical_store.knowledge_derivations WHERE record_id=NEW.record_id;
    SELECT * INTO STRICT context_row FROM compiler_runtime.k_execution_contexts WHERE execution_id=actual_record.execution_id;
    SELECT jsonb_agg(node_revision_id::text ORDER BY ordinal) INTO node_refs
        FROM compiler_runtime.k_input_node_revisions WHERE execution_id=actual_record.execution_id;
    SELECT jsonb_agg(semantic_kedge_revision_id::text ORDER BY ordinal),jsonb_agg(payload->'effective_edge_ref' ORDER BY ordinal)
        INTO edge_refs,effective_refs FROM compiler_runtime.k_input_effective_edges WHERE execution_id=actual_record.execution_id;
    IF actual_record.disposition NOT IN ('accepted_new','accepted_revision','reused','no_material_delta')
        OR actual_record.result_node_revision_id IS DISTINCT FROM derivation.result_node_revision_id
        OR derivation.validation->'_premise_revision_ids' IS DISTINCT FROM node_refs
        OR derivation.validation->'_premise_edge_revision_ids' IS DISTINCT FROM edge_refs
        OR derivation.validation->'_premise_effective_edge_refs' IS DISTINCT FROM effective_refs
        OR (SELECT count(*) FROM canonical_store.knowledge_derivation_edge_premises WHERE record_id=NEW.record_id)
            IS DISTINCT FROM jsonb_array_length(edge_refs)
        OR EXISTS(SELECT 1 FROM compiler_runtime.k_input_effective_edges x
            LEFT JOIN canonical_store.knowledge_derivation_edge_premises p
                ON p.record_id=NEW.record_id AND p.execution_id=x.execution_id AND p.input_ordinal=x.ordinal AND p.ordinal=x.ordinal
            WHERE x.execution_id=actual_record.execution_id AND (p.record_id IS NULL OR NOT compiler_runtime.k2k_effective_edge_current(x)))
        OR NOT EXISTS(SELECT 1 FROM compiler_runtime.k_model_calls generator
            JOIN compiler_runtime.k_model_calls validator ON validator.execution_id=generator.execution_id
            WHERE generator.execution_id=actual_record.execution_id AND generator.phase='generator' AND validator.phase='validator'
                AND generator.status='succeeded' AND validator.status='succeeded'
                AND generator.profile_id=context_row.generator_profile_id AND validator.profile_id=context_row.validator_profile_id
                AND length(btrim(generator.provider_ref))>0 AND length(btrim(validator.provider_ref))>0
                AND generator.provider_ref<>validator.provider_ref
                AND generator.input_sha256=context_row.input_digest AND validator.input_sha256=context_row.validation_context_sha
                AND generator.receipt->'actual_delivery'='true'::jsonb AND validator.receipt->'actual_delivery'='true'::jsonb
                AND generator.receipt->'delivered_knowledge_revision_ids'=node_refs
                AND validator.receipt->'delivered_knowledge_revision_ids'=node_refs
                AND generator.receipt->'delivered_effective_edge_refs'=effective_refs
                AND validator.receipt->'delivered_effective_edge_refs'=effective_refs
                AND generator.receipt->>'delivered_effective_input_sha256'=context_row.input_snapshot->'input'->>'input_sha256'
                AND validator.receipt->>'delivered_effective_input_sha256'=context_row.input_snapshot->'input'->>'input_sha256')
    THEN RAISE EXCEPTION 'Effective K2K result, complete current dependencies and independent actual bundle deliveries must commit together'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER effective_k2k_derivation_complete AFTER INSERT ON canonical_store.knowledge_derivations
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION canonical_store.check_effective_k2k_derivation();
CREATE CONSTRAINT TRIGGER effective_k2k_edge_premises_complete AFTER INSERT ON canonical_store.knowledge_derivation_edge_premises
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION canonical_store.check_effective_k2k_derivation();

CREATE FUNCTION compiler_runtime.check_effective_k2k_completion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_execution compiler_runtime.operation_executions; context_row compiler_runtime.k_execution_contexts;
        node_refs jsonb; effective_refs jsonb; validated jsonb; record_count bigint;
BEGIN
    SELECT * INTO STRICT actual_execution FROM compiler_runtime.operation_executions WHERE execution_id=NEW.execution_id;
    IF actual_execution.state NOT IN ('completed','zero_output')
        OR NOT compiler_runtime.is_effective_k2k(actual_execution.execution_id) THEN RETURN NULL; END IF;
    -- This also fences the zero-candidate path, which has no canonical insertion
    -- to take the shared knowledge lock on its behalf.
    PERFORM 1 FROM compiler_runtime.knowledge_state WHERE singleton FOR UPDATE;
    SELECT * INTO STRICT context_row FROM compiler_runtime.k_execution_contexts WHERE execution_id=NEW.execution_id;
    SELECT jsonb_agg(node_revision_id::text ORDER BY ordinal) INTO node_refs
        FROM compiler_runtime.k_input_node_revisions WHERE execution_id=NEW.execution_id;
    SELECT jsonb_agg(payload->'effective_edge_ref' ORDER BY ordinal) INTO effective_refs
        FROM compiler_runtime.k_input_effective_edges WHERE execution_id=NEW.execution_id;
    SELECT count(*) INTO record_count FROM compiler_runtime.k_compilation_records WHERE execution_id=NEW.execution_id;
    validated:=actual_execution.validator_receipt->'effective_validation_output';
    IF actual_execution.generator_receipt->'generation_complete' IS DISTINCT FROM 'true'::jsonb
        OR COALESCE(actual_execution.generator_receipt->'source_requests','[]'::jsonb)<>'[]'::jsonb
        OR validated->'complete' IS DISTINCT FROM 'true'::jsonb
        OR jsonb_typeof(validated->'decisions') IS DISTINCT FROM 'array'
        OR jsonb_array_length(validated->'decisions') IS DISTINCT FROM record_count
        OR (SELECT count(DISTINCT item->>'candidate_key') FROM jsonb_array_elements(validated->'decisions') item)
            IS DISTINCT FROM record_count
        OR (actual_execution.state='zero_output') IS DISTINCT FROM (record_count=0)
        OR EXISTS(SELECT 1 FROM compiler_runtime.k_compilation_records WHERE execution_id=NEW.execution_id
            AND disposition IN ('pending','needs_human'))
        OR EXISTS(SELECT 1 FROM compiler_runtime.k_input_node_revisions x WHERE x.execution_id=NEW.execution_id
            AND (NOT compiler_runtime.current_k2k_premise(x.node_revision_id)
                OR context_row.input_snapshot->'input'->'nodes'->x.ordinal->>'current_support_signature'
                    IS DISTINCT FROM canonical_store.current_knowledge_support_signature(x.node_revision_id)))
        OR EXISTS(SELECT 1 FROM compiler_runtime.k_input_effective_edges x WHERE x.execution_id=NEW.execution_id
            AND NOT compiler_runtime.k2k_effective_edge_current(x))
        OR NOT EXISTS(SELECT 1 FROM compiler_runtime.k_model_calls generator
            JOIN compiler_runtime.k_model_calls validator ON validator.execution_id=generator.execution_id
            WHERE generator.execution_id=NEW.execution_id AND generator.phase='generator' AND validator.phase='validator'
                AND generator.status='succeeded' AND validator.status='succeeded'
                AND generator.profile_id=context_row.generator_profile_id AND validator.profile_id=context_row.validator_profile_id
                AND length(btrim(generator.provider_ref))>0 AND length(btrim(validator.provider_ref))>0
                AND generator.provider_ref<>validator.provider_ref
                AND generator.input_sha256=context_row.input_digest AND validator.input_sha256=context_row.validation_context_sha
                AND generator.output_sha256=actual_execution.generator_receipt->>'output_sha256'
                AND validator.output_sha256=actual_execution.validator_receipt->>'output_sha256'
                AND generator.receipt->'actual_delivery'='true'::jsonb AND validator.receipt->'actual_delivery'='true'::jsonb
                AND generator.receipt->'delivered_knowledge_revision_ids'=node_refs
                AND validator.receipt->'delivered_knowledge_revision_ids'=node_refs
                AND generator.receipt->'delivered_effective_edge_refs'=effective_refs
                AND validator.receipt->'delivered_effective_edge_refs'=effective_refs
                AND generator.receipt->>'delivered_effective_input_sha256'=context_row.input_snapshot->'input'->>'input_sha256'
                AND validator.receipt->>'delivered_effective_input_sha256'=context_row.input_snapshot->'input'->>'input_sha256')
    THEN RAISE EXCEPTION 'Effective K2K completion requires exhaustive resolved results and independent actual delivery of the still-current whole bundle'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER effective_k2k_execution_complete AFTER UPDATE ON compiler_runtime.operation_executions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_effective_k2k_completion();

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
        AND NOT EXISTS(SELECT 1 FROM ancestry a
            JOIN canonical_store.knowledge_derivation_edge_premises p
                ON p.record_id=canonical_store.current_k_support_record(a.revision_id)
            WHERE NOT compiler_runtime.k2k_edge_input_current(p.execution_id,p.input_ordinal))
$$;

-- A positive refreshed basis with actual current consumers needs maintenance
-- even when it creates no semantic revision. Repeated negative decisions do not.
CREATE FUNCTION compiler_runtime.check_effective_edge_maintenance() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_record compiler_runtime.k_compilation_records; decision compiler_runtime.n2e_review_decisions;
BEGIN
    SELECT * INTO STRICT actual_record FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.origin_record_id;
    IF NOT compiler_runtime.is_n2e_relations(actual_record.execution_id) THEN RETURN NULL; END IF;
    SELECT * INTO STRICT decision FROM compiler_runtime.n2e_review_decisions WHERE record_id=NEW.origin_record_id;
    IF NEW.applicable AND EXISTS(SELECT 1 FROM compiler_runtime.k_input_effective_edges x
        JOIN canonical_store.knowledge_derivation_edge_premises p ON p.execution_id=x.execution_id AND p.input_ordinal=x.ordinal
        JOIN canonical_store.knowledge_derivations d USING(record_id)
        JOIN canonical_store.knowledge_node_revisions v ON v.knode_revision_id=d.result_node_revision_id
        JOIN canonical_store.knowledge_nodes n USING(knode_id)
        WHERE x.kedge_id=NEW.kedge_id AND n.current_revision_id=v.knode_revision_id
            AND canonical_store.current_k_support_record(v.knode_revision_id)=p.record_id)
        AND NOT EXISTS(SELECT 1 FROM compiler_runtime.k_outbox WHERE record_id=NEW.origin_record_id AND operation='k2k')
    THEN RAISE EXCEPTION 'A refreshed positive edge basis must retain maintenance for every actual current consumer'; END IF;
    IF NOT decision.material_change AND decision.before_applicable=false AND decision.after_applicable=false
        AND EXISTS(SELECT 1 FROM compiler_runtime.k_outbox WHERE record_id=NEW.origin_record_id)
    THEN RAISE EXCEPTION 'Repeated negative edge assessment cannot create a new propagation branch'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER effective_edge_maintenance_commit AFTER INSERT ON canonical_store.knowledge_edge_applicability_events
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_effective_edge_maintenance();

DO $$ DECLARE relation text; BEGIN
    FOREACH relation IN ARRAY ARRAY['compiler_runtime.k_input_effective_edges','canonical_store.knowledge_derivation_edge_premises'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON %s FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
        EXECUTE format('CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON %s FOR EACH STATEMENT EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
    END LOOP;
END; $$;
CREATE TRIGGER a_knowledge_state BEFORE INSERT ON canonical_store.knowledge_derivation_edge_premises
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.advance_knowledge_state();
GRANT SELECT,INSERT ON compiler_runtime.k_input_effective_edges,canonical_store.knowledge_derivation_edge_premises TO palimpsest;
