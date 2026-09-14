-- Explicit material revision over one exact current K; D2K grants do not permit revision.
CREATE TABLE compiler_runtime.k_revision_targets (
    execution_id uuid PRIMARY KEY REFERENCES compiler_runtime.k_execution_contexts,
    target_knode_id uuid NOT NULL REFERENCES canonical_store.knowledge_nodes,
    expected_revision_id uuid NOT NULL REFERENCES canonical_store.knowledge_node_revisions,
    target_sha256 text NOT NULL CHECK (target_sha256 ~ '^[0-9a-f]{64}$'),
    snapshot jsonb NOT NULL CHECK (jsonb_typeof(snapshot)='object')
);
CREATE TABLE compiler_runtime.k_revision_decisions (
    record_id uuid PRIMARY KEY REFERENCES compiler_runtime.k_compilation_records,
    target_sha256 text NOT NULL CHECK (target_sha256 ~ '^[0-9a-f]{64}$'),
    validation jsonb NOT NULL CHECK (jsonb_typeof(validation)='object')
);
CREATE TABLE compiler_runtime.k_revision_impacts (
    record_id uuid PRIMARY KEY REFERENCES compiler_runtime.k_compilation_records,
    source_revision_id uuid NOT NULL REFERENCES canonical_store.knowledge_node_revisions,
    impacts jsonb NOT NULL CHECK (jsonb_typeof(impacts)='object')
);

CREATE FUNCTION compiler_runtime.is_explicit_k_revision(id uuid) RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT EXISTS(SELECT 1 FROM compiler_runtime.operation_executions e
        JOIN compiler_runtime.profiles p USING(profile_id) WHERE e.execution_id=id
        AND e.operation IN ('i2k','k2k')
        AND p.payload->>'explicit_knowledge_revision'='explicit-knowledge-revision-v1')
$$;
CREATE FUNCTION compiler_runtime.guard_k_revision_target() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE e compiler_runtime.operation_executions; actual jsonb; frozen jsonb;
BEGIN
    SELECT * INTO STRICT e FROM compiler_runtime.operation_executions WHERE execution_id=NEW.execution_id;
    SELECT to_jsonb(selected) INTO actual FROM (
        SELECT n.knode_id,n.kind,n.current_revision_id,v.knode_revision_id,v.semantic_payload,v.statement,
            v.identity_fingerprint,v.content_fingerprint,v.origin_record_id,s.identity_scope,s.source_data_id
        FROM canonical_store.knowledge_nodes n
        JOIN canonical_store.knowledge_node_revisions v ON v.knode_revision_id=n.current_revision_id
        JOIN canonical_store.knowledge_node_scopes s ON s.knode_id=n.knode_id
        JOIN compiler_runtime.k_compilation_records r ON r.record_id=v.origin_record_id
        WHERE n.knode_id=NEW.target_knode_id AND v.knode_revision_id=NEW.expected_revision_id
            AND r.disposition IN ('accepted_new','accepted_revision')
            AND r.result_node_id=n.knode_id AND r.result_node_revision_id=v.knode_revision_id) selected;
    frozen:=NEW.snapshot->'target';
    IF e.state<>'prepared' OR NOT compiler_runtime.is_explicit_k_revision(e.execution_id) OR actual IS NULL
        OR NEW.snapshot->>'schema_version' IS DISTINCT FROM 'knowledge-revision-target-v1'
        OR NEW.snapshot->>'operation' IS DISTINCT FROM e.operation
        OR NEW.snapshot->>'target_knode_id' IS DISTINCT FROM NEW.target_knode_id::text
        OR NEW.snapshot->>'expected_revision_id' IS DISTINCT FROM NEW.expected_revision_id::text
        OR NEW.snapshot->>'target_sha256' IS DISTINCT FROM NEW.target_sha256
        OR frozen-'current_applicability' IS DISTINCT FROM actual
        OR (frozen ? 'current_applicability' AND frozen->>'current_applicability' IS DISTINCT FROM
            CASE WHEN compiler_runtime.current_k2k_premise(NEW.expected_revision_id)
                THEN 'current_premises' ELSE 'needs_revalidation' END)
        OR NEW.snapshot IS DISTINCT FROM (SELECT input_snapshot->'revision_target'
            FROM compiler_runtime.k_execution_contexts WHERE execution_id=e.execution_id)
    THEN RAISE EXCEPTION 'Explicit revision must freeze its caller-selected accepted current target'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER k_revision_target_guard BEFORE INSERT ON compiler_runtime.k_revision_targets
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_k_revision_target();

CREATE FUNCTION compiler_runtime.check_k_revision_context() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE context_snapshot jsonb; marker text;
BEGIN
    SELECT c.input_snapshot,p.payload->>'explicit_knowledge_revision' INTO context_snapshot,marker
        FROM compiler_runtime.k_execution_contexts c JOIN compiler_runtime.operation_executions e USING(execution_id)
        JOIN compiler_runtime.profiles p USING(profile_id) WHERE c.execution_id=NEW.execution_id;
    IF context_snapshot ? 'revision_target' OR marker IS NOT NULL THEN
        IF NOT compiler_runtime.is_explicit_k_revision(NEW.execution_id) OR NOT EXISTS(
            SELECT 1 FROM compiler_runtime.k_revision_targets t WHERE t.execution_id=NEW.execution_id
                AND t.snapshot=context_snapshot->'revision_target')
        THEN RAISE EXCEPTION 'Explicit revision context requires its immutable target and exact operation profile'; END IF;
    END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER k_revision_context_guard AFTER INSERT ON compiler_runtime.k_execution_contexts
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_k_revision_context();

CREATE FUNCTION compiler_runtime.guard_k_revision_candidate() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r compiler_runtime.k_compilation_records; t compiler_runtime.k_revision_targets;
BEGIN
    SELECT * INTO STRICT r FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.record_id;
    IF NOT compiler_runtime.is_explicit_k_revision(r.execution_id) THEN
        IF NEW.body ? 'revision_target' THEN RAISE EXCEPTION 'An ordinary candidate cannot select a revision target'; END IF;
        RETURN NEW;
    END IF;
    SELECT * INTO STRICT t FROM compiler_runtime.k_revision_targets WHERE execution_id=r.execution_id;
    IF r.ordinal<>0 OR NEW.body->'revision_target' IS DISTINCT FROM jsonb_build_object(
            'knode_id',t.target_knode_id::text,'expected_revision_id',t.expected_revision_id::text,'target_sha256',t.target_sha256)
        OR NEW.body->>'identity_fingerprint' IS DISTINCT FROM t.snapshot->'target'->>'identity_fingerprint'
        OR r.identity_fingerprint IS DISTINCT FROM NEW.body->>'identity_fingerprint'
        OR r.content_fingerprint IS DISTINCT FROM NEW.body->>'content_fingerprint'
        OR NEW.body->>'kind' IS DISTINCT FROM t.snapshot->'target'->>'kind'
        OR NEW.body->'identity_scope' IS DISTINCT FROM t.snapshot->'target'->'identity_scope'
        OR NEW.body->'source_data_id' IS DISTINCT FROM t.snapshot->'target'->'source_data_id'
    THEN RAISE EXCEPTION 'Revision candidate must retain one exact logical identity, kind and source scope'; END IF;
    IF r.record_type='i2k' THEN
        IF NEW.body->>'claim_basis' IS DISTINCT FROM 'explicit_source_content'
            OR NEW.body->'is_inferred' IS DISTINCT FROM 'false'::jsonb
            OR jsonb_typeof(NEW.body->'evidence') IS DISTINCT FROM 'array' OR jsonb_array_length(NEW.body->'evidence')=0
            OR NEW.body ?| ARRAY['direct_evidence','premise_revision_ids']
        THEN RAISE EXCEPTION 'I2K revision remains explicit source content grounded only in I'; END IF;
    ELSE
        IF NEW.body->>'kind' IS DISTINCT FROM 'proposition'
            OR (NEW.body ? 'is_inferred' AND NEW.body->'is_inferred' IS DISTINCT FROM 'true'::jsonb)
            OR NEW.body ?| ARRAY['evidence','direct_evidence']
            OR jsonb_typeof(NEW.body->'premise_revision_ids') IS DISTINCT FROM 'array'
            OR jsonb_array_length(NEW.body->'premise_revision_ids')<2
            OR NEW.body->'premise_revision_ids' ? t.expected_revision_id::text
        THEN RAISE EXCEPTION 'K2K revision requires independent exact K premises, not its comparison target'; END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER k_revision_candidate_guard BEFORE INSERT ON compiler_runtime.k_temporary_candidates
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_k_revision_candidate();

CREATE FUNCTION compiler_runtime.guard_k_revision_decision() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r compiler_runtime.k_compilation_records; t compiler_runtime.k_revision_targets;
        candidate jsonb; review jsonb; decision jsonb; action text; expected_origin jsonb;
BEGIN
    SELECT * INTO STRICT r FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.record_id;
    SELECT * INTO STRICT t FROM compiler_runtime.k_revision_targets WHERE execution_id=r.execution_id;
    SELECT body INTO STRICT candidate FROM compiler_runtime.k_temporary_candidates WHERE record_id=r.record_id;
    review:=NEW.validation->'review'; decision:=NEW.validation->'decision'; action:=NEW.validation->>'action';
    IF NOT compiler_runtime.is_explicit_k_revision(r.execution_id) OR r.disposition NOT IN ('pending','needs_human')
        OR NEW.validation ? '_i_evidence_hashes'
        OR NOT EXISTS(SELECT 1 FROM compiler_runtime.operation_executions WHERE execution_id=r.execution_id AND state='proposed')
        OR NEW.target_sha256<>t.target_sha256 OR NEW.validation->'revision_target' IS DISTINCT FROM candidate->'revision_target'
        OR NEW.validation->>'identity_fingerprint' IS DISTINCT FROM r.identity_fingerprint
        OR NEW.validation->>'candidate_content_fingerprint' IS DISTINCT FROM r.content_fingerprint
        OR decision->>'candidate_key' IS DISTINCT FROM candidate->>'candidate_key'
        OR COALESCE(action,'') NOT IN ('accepted_revision','reused','rejected','needs_human')
        OR COALESCE(decision->>'verdict','') NOT IN ('accepted','reused','rejected','needs_human')
        OR review->>'comparison_base_revision_id' IS DISTINCT FROM t.expected_revision_id::text
        OR jsonb_typeof(review->'same_identity') IS DISTINCT FROM 'boolean'
        OR jsonb_typeof(review->'grounding_valid') IS DISTINCT FROM 'boolean'
        OR COALESCE(jsonb_typeof(review->'material_change'),'') NOT IN ('boolean','null')
        OR jsonb_typeof(review->'reason_codes') IS DISTINCT FROM 'array' OR jsonb_array_length(review->'reason_codes')=0
        OR COALESCE(length(btrim(review->>'reason')),0)=0
    THEN RAISE EXCEPTION 'Revision decision requires the exact staged candidate and independent materiality review'; END IF;
    IF action IN ('accepted_revision','reused') THEN
        IF review->'same_identity' IS DISTINCT FROM 'true'::jsonb OR review->'grounding_valid' IS DISTINCT FROM 'true'::jsonb
            OR review->'material_change' IS DISTINCT FROM to_jsonb(action='accepted_revision')
            OR decision->>'verdict' NOT IN ('accepted','reused')
            OR decision->>'equivalent_candidate_key' IS NOT NULL
            OR (decision->>'verdict'='accepted' AND decision->>'equivalent_revision_id' IS NOT NULL)
            OR (decision->>'verdict'='reused' AND (action<>'reused'
                OR decision->>'equivalent_revision_id' IS DISTINCT FROM t.expected_revision_id::text))
            OR NOT EXISTS(SELECT 1 FROM canonical_store.knowledge_nodes
                WHERE knode_id=t.target_knode_id AND current_revision_id=t.expected_revision_id)
            OR (r.record_type='i2k' AND (decision->'source_explicit' IS DISTINCT FROM 'true'::jsonb
                OR decision->'no_novel_inference' IS DISTINCT FROM 'true'::jsonb
                OR decision->'source_identity_preserved' IS DISTINCT FROM 'true'::jsonb
                OR decision->'scope_correct' IS DISTINCT FROM 'true'::jsonb
                OR decision->'importance_justified' IS DISTINCT FROM 'true'::jsonb))
            OR (r.record_type='k2k' AND (decision->'inference_valid' IS DISTINCT FROM 'true'::jsonb
                OR decision->'premises_sufficient' IS DISTINCT FROM 'true'::jsonb
                OR decision->'limits_preserved' IS DISTINCT FROM 'true'::jsonb))
        THEN RAISE EXCEPTION 'Revision publication requires current identity, materiality and ordinary source/inference acceptance'; END IF;
    END IF;
    expected_origin:=CASE WHEN action='accepted_revision' THEN jsonb_build_object(
        'mode','new_record','origin_operation',r.record_type,'is_inferred',r.record_type='k2k')
        WHEN action='reused' THEN jsonb_build_object('mode','preserve_existing','origin_record_id',t.snapshot->'target'->'origin_record_id')
        ELSE jsonb_build_object('mode','no_publication') END;
    IF NEW.validation->'origin' IS DISTINCT FROM expected_origin
        OR NEW.validation->'result_content_fingerprint' IS DISTINCT FROM (CASE
            WHEN action='accepted_revision' THEN to_jsonb(r.content_fingerprint)
            WHEN action='reused' THEN t.snapshot->'target'->'content_fingerprint' ELSE 'null'::jsonb END)
        OR (action='accepted_revision' AND (candidate->'semantic_payload'=t.snapshot->'target'->'semantic_payload'
            OR r.content_fingerprint=t.snapshot->'target'->>'content_fingerprint'))
    THEN RAISE EXCEPTION 'Material revision changes content and origin; equivalent support preserves the exact existing revision'; END IF;
    IF r.record_type='i2k' THEN
        -- A DB-owned hash witness allows exact existing grounding reuse without duplicating source quotes or rows.
        NEW.validation:=NEW.validation||jsonb_build_object('_i_evidence_hashes',(
            SELECT jsonb_agg(encode(sha256(convert_to(jsonb_build_object(
                'information_id',item->'information_id','char_start',item->'char_start','char_end',item->'char_end',
                'quote',item->'quote','media_sha256',item->'media_sha256','source_role',item->'source_role')::text,'UTF8')),'hex'))
            FROM jsonb_array_elements(candidate->'evidence') item));
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER k_revision_decision_guard BEFORE INSERT ON compiler_runtime.k_revision_decisions
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_k_revision_decision();

CREATE FUNCTION canonical_store.guard_explicit_k_successor() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r compiler_runtime.k_compilation_records; t compiler_runtime.k_revision_targets; candidate jsonb;
BEGIN
    IF NEW.supersedes_revision_id IS NULL THEN RETURN NEW; END IF;
    SELECT * INTO STRICT r FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.origin_record_id;
    SELECT * INTO t FROM compiler_runtime.k_revision_targets WHERE execution_id=r.execution_id;
    SELECT body INTO candidate FROM compiler_runtime.k_temporary_candidates WHERE record_id=r.record_id;
    IF t.execution_id IS NULL OR NOT compiler_runtime.is_explicit_k_revision(r.execution_id)
        OR NEW.knode_id IS DISTINCT FROM t.target_knode_id OR NEW.supersedes_revision_id IS DISTINCT FROM t.expected_revision_id
        OR NEW.identity_fingerprint IS DISTINCT FROM t.snapshot->'target'->>'identity_fingerprint'
        OR NEW.semantic_payload IS DISTINCT FROM candidate->'semantic_payload'
        OR NEW.statement IS DISTINCT FROM candidate->>'statement'
        OR NEW.content_fingerprint IS DISTINCT FROM candidate->>'content_fingerprint'
        OR NOT EXISTS(SELECT 1 FROM compiler_runtime.k_revision_decisions d WHERE d.record_id=r.record_id
            AND d.target_sha256=t.target_sha256 AND d.validation->>'action'='accepted_revision')
    THEN RAISE EXCEPTION 'A K successor requires an explicit I2K/K2K target and accepted material revision decision'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER explicit_k_successor_guard BEFORE INSERT ON canonical_store.knowledge_node_revisions
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_explicit_k_successor();

CREATE FUNCTION compiler_runtime.k_revision_impact_snapshot(revision uuid) RETURNS jsonb LANGUAGE sql STABLE AS $$
    SELECT jsonb_build_object('source_revision_id',revision::text,
        'derivations',(SELECT COALESCE(jsonb_agg(to_jsonb(entry) ORDER BY entry.record_id,entry.ordinal),'[]'::jsonb) FROM (
            SELECT d.record_id,d.result_node_revision_id,p.premise_node_revision_id,p.ordinal
            FROM canonical_store.knowledge_derivation_premises p JOIN canonical_store.knowledge_derivations d USING(record_id)
            WHERE p.premise_node_revision_id=revision) entry),
        'edges',(SELECT COALESCE(jsonb_agg(to_jsonb(entry) ORDER BY entry.kedge_id,entry.kedge_revision_id),'[]'::jsonb) FROM (
            SELECT kedge_id,kedge_revision_id,from_knode_revision_id,to_knode_revision_id
            FROM canonical_store.knowledge_edge_revisions WHERE from_knode_revision_id=revision OR to_knode_revision_id=revision) entry),
        'edge_applicability',(SELECT COALESCE(jsonb_agg(to_jsonb(entry) ORDER BY entry.event_order),'[]'::jsonb) FROM (
            SELECT applicability_event_id,event_order,kedge_id,semantic_kedge_revision_id,from_knode_revision_id,to_knode_revision_id,applicable
            FROM canonical_store.knowledge_edge_applicability_events WHERE from_knode_revision_id=revision OR to_knode_revision_id=revision) entry),
        'wiki_links',(SELECT COALESCE(jsonb_agg(to_jsonb(entry) ORDER BY entry.wiki_id,entry.request_id,entry.snapshot_id,entry.item_key,entry.link_id),'[]'::jsonb) FROM (
            SELECT link_id,request_id,wiki_id,snapshot_id,item_key,knode_id,node_revision_id
            FROM wiki_projection.knowledge_links WHERE node_revision_id=revision) entry),'wiki_available',true)
$$;
CREATE FUNCTION compiler_runtime.guard_k_revision_impact() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM compiler_runtime.k_revision_decisions d
        JOIN compiler_runtime.k_compilation_records r USING(record_id)
        JOIN compiler_runtime.k_revision_targets t USING(execution_id)
        WHERE r.record_id=NEW.record_id AND r.disposition='accepted_revision'
            AND d.validation->>'action'='accepted_revision' AND t.expected_revision_id=NEW.source_revision_id)
        OR NEW.impacts IS DISTINCT FROM compiler_runtime.k_revision_impact_snapshot(NEW.source_revision_id)
    THEN RAISE EXCEPTION 'Material revision must retain all exact direct dependency references as unresolved impact'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER k_revision_impact_guard BEFORE INSERT ON compiler_runtime.k_revision_impacts
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_k_revision_impact();

CREATE FUNCTION compiler_runtime.check_explicit_k_record_commit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r compiler_runtime.k_compilation_records; t compiler_runtime.k_revision_targets; resolution jsonb;
        context compiler_runtime.k_execution_contexts;
BEGIN
    SELECT * INTO STRICT r FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.record_id;
    IF NOT compiler_runtime.is_explicit_k_revision(r.execution_id) THEN RETURN NULL; END IF;
    SELECT * INTO STRICT t FROM compiler_runtime.k_revision_targets WHERE execution_id=r.execution_id;
    SELECT * INTO STRICT context FROM compiler_runtime.k_execution_contexts WHERE execution_id=r.execution_id;
    IF r.ordinal<>0 THEN RAISE EXCEPTION 'An explicit revision request permits at most one candidate'; END IF;
    IF r.disposition='pending' THEN RETURN NULL; END IF;
    SELECT validation INTO resolution FROM compiler_runtime.k_revision_decisions WHERE record_id=r.record_id;
    IF resolution IS NULL OR r.disposition IS DISTINCT FROM resolution->>'action'
        OR (r.result_node_id IS NOT NULL AND r.result_node_id IS DISTINCT FROM t.target_knode_id)
    THEN RAISE EXCEPTION 'Explicit revision Record must retain its exact publication or unresolved decision'; END IF;
    IF r.disposition NOT IN ('accepted_revision','reused') THEN RETURN NULL; END IF;
    IF NOT EXISTS(SELECT 1 FROM canonical_store.knowledge_node_revisions v
        JOIN canonical_store.knowledge_nodes n USING(knode_id) WHERE v.knode_revision_id=r.result_node_revision_id
            AND n.current_revision_id=v.knode_revision_id AND n.knode_id=t.target_knode_id
            AND v.content_fingerprint=resolution->>'result_content_fingerprint'
            AND ((r.disposition='accepted_revision' AND v.supersedes_revision_id=t.expected_revision_id AND v.origin_record_id=r.record_id)
                OR (r.disposition='reused' AND v.knode_revision_id=t.expected_revision_id
                    AND v.origin_record_id::text=t.snapshot->'target'->>'origin_record_id')))
        OR NOT EXISTS(SELECT 1 FROM compiler_runtime.k_model_calls generator
            JOIN compiler_runtime.k_model_calls validator ON validator.execution_id=generator.execution_id
            WHERE generator.execution_id=r.execution_id AND generator.phase='generator' AND validator.phase='validator'
                AND generator.status='succeeded' AND validator.status='succeeded'
                AND generator.profile_id=context.generator_profile_id AND validator.profile_id=context.validator_profile_id
                AND length(btrim(generator.provider_ref))>0 AND length(btrim(validator.provider_ref))>0
                AND generator.provider_ref<>validator.provider_ref
                AND generator.receipt->'actual_delivery'='true'::jsonb AND validator.receipt->'actual_delivery'='true'::jsonb
                AND generator.receipt->>'delivered_revision_target_id'=t.expected_revision_id::text
                AND validator.receipt->>'delivered_revision_target_id'=t.expected_revision_id::text)
        OR (r.record_type='i2k' AND (EXISTS(
            SELECT 1 FROM jsonb_array_elements_text(resolution->'_i_evidence_hashes') witness
            WHERE NOT EXISTS(SELECT 1 FROM canonical_store.knowledge_node_groundings g
                JOIN compiler_runtime.k_input_information x USING(information_id)
                WHERE g.node_revision_id=r.result_node_revision_id AND x.execution_id=r.execution_id
                    AND (r.disposition='reused' OR g.origin_record_id=r.record_id)
                    AND witness=encode(sha256(convert_to(jsonb_build_object(
                        'information_id',g.information_id::text,'char_start',g.char_start,'char_end',g.char_end,
                        'quote',g.quote,'media_sha256',g.media_sha256,'source_role',g.source_role)::text,'UTF8')),'hex')))
            OR EXISTS(SELECT 1 FROM canonical_store.knowledge_derivations WHERE record_id=r.record_id)))
        OR EXISTS(SELECT 1 FROM canonical_store.knowledge_data_groundings WHERE origin_record_id=r.record_id)
    THEN RAISE EXCEPTION 'Revision result, actual independent target deliveries and original evidence boundary must commit together'; END IF;
    IF r.disposition='accepted_revision' THEN
        IF NOT EXISTS(SELECT 1 FROM compiler_runtime.k_revision_impacts WHERE record_id=r.record_id AND source_revision_id=t.expected_revision_id)
            OR (SELECT count(DISTINCT operation) FROM compiler_runtime.k_outbox WHERE record_id=r.record_id AND operation IN ('n2e','k2k'))<>2
        THEN RAISE EXCEPTION 'Material revision requires complete durable impact and pending N2E/K2K obligations'; END IF;
    ELSIF EXISTS(SELECT 1 FROM compiler_runtime.k_revision_impacts WHERE record_id=r.record_id)
        OR EXISTS(SELECT 1 FROM compiler_runtime.k_outbox WHERE record_id=r.record_id) THEN
        RAISE EXCEPTION 'Same-meaning support cannot create a material revision propagation branch';
    END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER explicit_k_record_commit_guard AFTER INSERT OR UPDATE ON compiler_runtime.k_compilation_records
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_explicit_k_record_commit();

CREATE FUNCTION compiler_runtime.check_k_revision_completion() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.state IN ('completed','zero_output') AND compiler_runtime.is_explicit_k_revision(NEW.execution_id)
        AND NOT EXISTS(SELECT 1 FROM compiler_runtime.k_compilation_records WHERE execution_id=NEW.execution_id
            AND disposition IN ('accepted_revision','reused','rejected'))
    THEN RAISE EXCEPTION 'An empty or undecidable revision request remains unresolved, not successful zero output'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER k_revision_completion_guard AFTER UPDATE ON compiler_runtime.operation_executions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_k_revision_completion();

DO $$ DECLARE relation text; BEGIN
    FOREACH relation IN ARRAY ARRAY['compiler_runtime.k_revision_targets','compiler_runtime.k_revision_decisions',
        'compiler_runtime.k_revision_impacts'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON %s FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
        EXECUTE format('CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON %s FOR EACH STATEMENT EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
    END LOOP;
END; $$;
GRANT SELECT,INSERT ON compiler_runtime.k_revision_targets,compiler_runtime.k_revision_decisions,
    compiler_runtime.k_revision_impacts TO palimpsest;
