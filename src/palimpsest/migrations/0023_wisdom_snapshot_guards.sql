-- Correct the PL/pgSQL column alias and bind derived W metadata exactly.
CREATE OR REPLACE FUNCTION canonical_store.guard_wisdom() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE job compiler_runtime.w_jobs; ref text; edge_ref jsonb; claim jsonb; current_version bigint;
        actual_refs jsonb; expected_refs jsonb; expected_citations jsonb;
        actual_edges jsonb; expected_edges jsonb; expected_uncertainty jsonb;
BEGIN
    SELECT version INTO STRICT current_version FROM compiler_runtime.knowledge_state WHERE singleton FOR UPDATE;
    SELECT * INTO STRICT job FROM compiler_runtime.w_jobs WHERE execution_id=NEW.execution_id FOR UPDATE;
    IF job.state<>'validated' OR current_version<>job.expected_state_version OR NOT compiler_runtime.w_inputs_current(job.execution_id)
        OR job.validation->>'verdict' IS DISTINCT FROM 'accepted'
        OR job.validation->'query_addressed' IS DISTINCT FROM 'true'::jsonb
        OR job.validation->'advisory_boundary_preserved' IS DISTINCT FROM 'true'::jsonb
        OR NEW.snapshot->>'wisdom_id' IS DISTINCT FROM NEW.wisdom_id::text
        OR NEW.snapshot->>'execution_id' IS DISTINCT FROM NEW.execution_id::text
        OR NEW.snapshot->>'wisdom_kind' IS DISTINCT FROM NEW.wisdom_kind
        OR NEW.snapshot->>'wisdom_kind' IS DISTINCT FROM job.input_snapshot->>'wisdom_kind'
        OR NEW.snapshot->>'schema_version' IS DISTINCT FROM 'wisdom-v1'
        OR NEW.snapshot->>'snapshot_sha256' IS DISTINCT FROM NEW.snapshot_sha256
        OR (NEW.snapshot->>'created_at')::timestamptz IS DISTINCT FROM NEW.created_at
        OR NEW.snapshot->>'input_sha256' IS DISTINCT FROM job.input_snapshot->>'input_sha256'
        OR NEW.snapshot->>'query' IS DISTINCT FROM job.input_snapshot->>'query'
        OR NEW.snapshot->'context_snapshot' IS DISTINCT FROM job.input_snapshot->'context_snapshot'
        OR NEW.snapshot->'retrieval_snapshot' IS DISTINCT FROM job.input_snapshot->'retrieval_snapshot'
        OR NEW.snapshot->>'retrieval_strategy' IS DISTINCT FROM 'standard'
        OR NEW.snapshot->'answer_or_payload' IS DISTINCT FROM job.answer
        OR NEW.snapshot->'validation' IS DISTINCT FROM job.validation
        OR NEW.snapshot->>'evidence_mode' IS DISTINCT FROM 'knowledge_only'
        OR NEW.snapshot->>'epistemic_basis' IS DISTINCT FROM 'accepted_knowledge'
        OR NEW.snapshot->'used_information_ids' IS DISTINCT FROM '[]'::jsonb
        OR NEW.snapshot->'generation_profile' IS DISTINCT FROM (SELECT payload FROM compiler_runtime.profiles WHERE profile_id=job.profile_id)
    THEN RAISE EXCEPTION 'W requires frozen exact inputs and accepted independent validation'; END IF;
    SELECT COALESCE(jsonb_agg(value ORDER BY value),'[]'::jsonb) INTO actual_refs
        FROM jsonb_array_elements_text(NEW.snapshot->'used_k_revision_ids');
    SELECT COALESCE(jsonb_agg(refs.ref ORDER BY refs.ref),'[]'::jsonb) INTO expected_refs FROM (
        SELECT DISTINCT jsonb_array_elements_text(c->'k_revision_ids') AS ref FROM jsonb_array_elements(job.answer->'claims') c
        UNION SELECT DISTINCT jsonb_array_elements_text(c->'effective_edge_revision_ids') AS ref FROM jsonb_array_elements(job.answer->'claims') c) refs;
    IF actual_refs IS DISTINCT FROM expected_refs
    THEN RAISE EXCEPTION 'W used references must equal actual claim citations'; END IF;
    SELECT COALESCE(jsonb_agg(jsonb_build_object('claim_key',c->>'claim_key','epistemic_basis',c->>'epistemic_basis',
        'k_revision_ids',c->'k_revision_ids','effective_edge_refs',COALESCE((SELECT jsonb_agg(e.payload->'effective_edge_ref' ORDER BY r.ordinality)
            FROM jsonb_array_elements_text(c->'effective_edge_revision_ids') WITH ORDINALITY r(value,ordinality)
            JOIN compiler_runtime.w_edge_inputs e ON e.execution_id=job.execution_id AND e.semantic_kedge_revision_id=r.value::uuid),'[]'::jsonb)) ORDER BY n),'[]'::jsonb)
        INTO expected_citations FROM jsonb_array_elements(job.answer->'claims') WITH ORDINALITY claims(c,n);
    IF NEW.snapshot->'citations' IS DISTINCT FROM expected_citations
        OR (SELECT COALESCE(jsonb_agg(c->>'claim_key' ORDER BY c->>'claim_key'),'[]'::jsonb) FROM jsonb_array_elements(job.answer->'claims') c)
            IS DISTINCT FROM (SELECT COALESCE(jsonb_agg(c->>'claim_key' ORDER BY c->>'claim_key'),'[]'::jsonb) FROM jsonb_array_elements(job.validation->'claims') c)
    THEN RAISE EXCEPTION 'W citations and validation must cover every claim'; END IF;
    SELECT COALESCE(jsonb_agg(e.ref ORDER BY e.ref),'[]'::jsonb) INTO expected_edges FROM (
        SELECT DISTINCT r.value AS ref FROM jsonb_array_elements(expected_citations) c
            CROSS JOIN LATERAL jsonb_array_elements(c->'effective_edge_refs') r) e;
    SELECT COALESCE(jsonb_agg(r.value ORDER BY r.value),'[]'::jsonb) INTO actual_edges
        FROM jsonb_array_elements(NEW.snapshot->'used_effective_edge_refs') r;
    expected_uncertainty:=jsonb_build_object('unresolved',job.answer->'unresolved','claims',
        (SELECT COALESCE(jsonb_agg(jsonb_build_object('claim_key',c->'claim_key',
            'assumptions',c->'assumptions','limitations',c->'limitations') ORDER BY n),'[]'::jsonb)
         FROM jsonb_array_elements(job.answer->'claims') WITH ORDINALITY claims(c,n)));
    IF jsonb_typeof(NEW.snapshot->'used_effective_edge_refs') IS DISTINCT FROM 'array'
        OR actual_edges IS DISTINCT FROM expected_edges
        OR NEW.snapshot->'uncertainty' IS DISTINCT FROM expected_uncertainty
    THEN RAISE EXCEPTION 'W must preserve actual used Edge references and uncertainty'; END IF;
    FOR claim IN SELECT value FROM jsonb_array_elements(job.validation->'claims') LOOP
        IF claim->'supported' IS DISTINCT FROM 'true'::jsonb OR claim->'citations_sufficient' IS DISTINCT FROM 'true'::jsonb
            OR claim->'scope_preserved' IS DISTINCT FROM 'true'::jsonb OR claim->'limits_preserved' IS DISTINCT FROM 'true'::jsonb
            OR claim->'no_unattributed_inference' IS DISTINCT FROM 'true'::jsonb
        THEN RAISE EXCEPTION 'W claim has unresolved validation'; END IF;
    END LOOP;
    FOR ref IN SELECT jsonb_array_elements_text(NEW.snapshot->'used_k_revision_ids') LOOP
        IF NOT EXISTS(SELECT 1 FROM compiler_runtime.w_inputs WHERE execution_id=job.execution_id AND knode_revision_id=ref::uuid)
            AND NOT EXISTS(SELECT 1 FROM compiler_runtime.w_edge_inputs WHERE execution_id=job.execution_id AND semantic_kedge_revision_id=ref::uuid)
        THEN RAISE EXCEPTION 'W cites an undelivered K revision'; END IF;
    END LOOP;
    FOR edge_ref IN SELECT value FROM jsonb_array_elements(NEW.snapshot->'used_effective_edge_refs') LOOP
        IF NOT EXISTS(SELECT 1 FROM compiler_runtime.w_edge_inputs WHERE execution_id=job.execution_id AND payload->'effective_edge_ref'=edge_ref)
        THEN RAISE EXCEPTION 'W cites an undelivered effective Edge'; END IF;
    END LOOP;
    RETURN NEW;
END; $$;
