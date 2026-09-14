-- Fresh N2E effects cannot replay an old approval past a newly opened review.
-- Keep published 0001-0018 migration bytes and every prior event unchanged.
CREATE FUNCTION canonical_store.guard_n2e_effect_fence() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_record compiler_runtime.k_compilation_records; execution_state text; prepared_version bigint; latest_fence bigint;
        modern boolean; semantic_modern boolean; predicate text;
BEGIN
    SELECT * INTO STRICT actual_record FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.origin_record_id;
    modern:=compiler_runtime.is_n2e_relations(actual_record.execution_id);
    SELECT max(fence_order) INTO latest_fence FROM compiler_runtime.n2e_review_targets
        WHERE semantic_kedge_revision_id=NEW.semantic_kedge_revision_id
            AND from_knode_revision_id=NEW.from_knode_revision_id AND to_knode_revision_id=NEW.to_knode_revision_id;
    SELECT e.predicate,compiler_runtime.is_n2e_relations(r.execution_id) INTO STRICT predicate,semantic_modern
        FROM canonical_store.knowledge_edge_revisions v JOIN canonical_store.knowledge_edges e USING(kedge_id)
        JOIN compiler_runtime.k_compilation_records r ON r.record_id=v.origin_record_id
        WHERE v.kedge_revision_id=NEW.semantic_kedge_revision_id;
    IF NOT modern THEN
        IF latest_fence IS NOT NULL OR semantic_modern OR predicate<>'supports'
        THEN RAISE EXCEPTION 'A modern relation or review fence cannot be downgraded to legacy N2E evidence'; END IF;
        RETURN NEW;
    END IF;
    SELECT e.state,c.expected_state_version INTO STRICT execution_state,prepared_version
        FROM compiler_runtime.operation_executions e JOIN compiler_runtime.k_execution_contexts c USING(execution_id)
        WHERE e.execution_id=actual_record.execution_id;
    IF actual_record.disposition NOT IN ('pending','needs_human') OR execution_state<>'proposed'
        OR (latest_fence IS NOT NULL AND prepared_version<latest_fence)
    THEN RAISE EXCEPTION 'Modern N2E effects require a fresh pending Record and proposed execution after the exact review fence'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER n2e_effect_fence_guard BEFORE INSERT ON canonical_store.knowledge_edge_applicability_events
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_n2e_effect_fence();

CREATE UNIQUE INDEX n2e_one_modern_applicability_per_record
    ON canonical_store.knowledge_edge_applicability_events(origin_record_id)
    WHERE (detail->>'n2e_policy')='n2e-relations-v1';
