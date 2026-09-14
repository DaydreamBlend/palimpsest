-- Additional modern N2E review checks. Published 0001-0017 bytes remain unchanged.
CREATE FUNCTION compiler_runtime.guard_n2e_assessment_agreement() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE candidate jsonb; generation_complete jsonb;
BEGIN
    IF NEW.role<>'target_assessment' THEN RETURN NEW; END IF;
    IF NEW.validation->'material_change' IS DISTINCT FROM 'null'::jsonb
    THEN RAISE EXCEPTION 'An applicability assessment leaves semantic materiality to Runtime'; END IF;
    IF NEW.action='no_material_delta' THEN
        SELECT body INTO candidate FROM compiler_runtime.k_temporary_candidates WHERE record_id=NEW.record_id;
        SELECT generator_receipt->'generation_complete' INTO generation_complete
            FROM compiler_runtime.operation_executions WHERE execution_id=NEW.execution_id;
        IF candidate IS NULL OR generation_complete IS DISTINCT FROM 'true'::jsonb
            OR candidate->'applicability_proposal'->'applicable'
                IS DISTINCT FROM NEW.validation->'applicability_review'->'applicable'
        THEN RAISE EXCEPTION 'Confirmed applicability requires completed Generator and agreeing independent assessment'; END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER n2e_assessment_agreement_guard BEFORE INSERT ON compiler_runtime.n2e_review_decisions
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_n2e_assessment_agreement();

CREATE FUNCTION compiler_runtime.check_n2e_decision_resolution() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM compiler_runtime.k_compilation_records
        WHERE record_id=NEW.record_id AND execution_id=NEW.execution_id AND disposition=NEW.action)
    THEN RAISE EXCEPTION 'An immutable N2E decision and its resolved Record must commit together'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER n2e_decision_resolution_guard AFTER INSERT ON compiler_runtime.n2e_review_decisions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_n2e_decision_resolution();
