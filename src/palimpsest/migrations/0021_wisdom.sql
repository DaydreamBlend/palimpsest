-- K2W explanation/recommendation only. W has no representative Data owner.
-- Old source-owned execution enums and every previous migration stay unchanged.
CREATE TABLE compiler_runtime.w_jobs (
    execution_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(execution_id)=7),
    request_id uuid NOT NULL UNIQUE CHECK (uuid_extract_version(request_id)=7),
    request_fingerprint text NOT NULL CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
    profile_id uuid NOT NULL REFERENCES compiler_runtime.profiles,
    input_snapshot jsonb NOT NULL CHECK (jsonb_typeof(input_snapshot)='object'),
    input_json text NOT NULL,
    expected_state_version bigint NOT NULL CHECK (expected_state_version>=0),
    generator_request jsonb NOT NULL CHECK (jsonb_typeof(generator_request)='object'),
    state text NOT NULL DEFAULT 'prepared' CHECK (state IN ('prepared','proposed','validated','needs_human','completed')),
    generator_response jsonb, generator_receipt jsonb, answer jsonb,
    validator_request jsonb, validator_response jsonb, validator_receipt jsonb, validation jsonb,
    wisdom_id uuid,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((state='prepared')=(generator_response IS NULL)),
    CHECK ((generator_response IS NULL)=(generator_receipt IS NULL)),
    CHECK ((generator_response IS NULL)=(answer IS NULL)),
    CHECK ((generator_response IS NULL)=(validator_request IS NULL)),
    CHECK ((state IN ('prepared','proposed'))=(validator_response IS NULL)),
    CHECK ((validator_response IS NULL)=(validator_receipt IS NULL)),
    CHECK ((validator_response IS NULL)=(validation IS NULL)),
    CHECK ((state='completed')=(wisdom_id IS NOT NULL)),
    CHECK ((input_snapshot->>'schema_version'='k2w-input-v1') IS TRUE),
    CHECK ((input_snapshot->>'wisdom_kind' IN ('explanation','recommendation')) IS TRUE),
    CHECK ((input_snapshot->>'evidence_mode'='knowledge_only') IS TRUE),
    CHECK ((input_snapshot->>'retrieval_strategy'='standard') IS TRUE),
    CHECK ((input_snapshot->>'input_sha256' ~ '^[0-9a-f]{64}$') IS TRUE),
    CHECK (((input_snapshot->>'knowledge_state_version')::bigint=expected_state_version) IS TRUE),
    CHECK ((jsonb_typeof(input_snapshot->'nodes')='array' AND jsonb_array_length(input_snapshot->'nodes')>0) IS TRUE),
    CHECK ((jsonb_typeof(input_snapshot->'effective_edges')='array') IS TRUE),
    CHECK ((jsonb_typeof(input_snapshot->'context_snapshot')='object') IS TRUE),
    CHECK ((jsonb_typeof(input_snapshot->'retrieval_snapshot')='object') IS TRUE),
    CHECK ((jsonb_typeof(input_snapshot->'query')='string' AND length(input_snapshot->>'query')>0) IS TRUE),
    CHECK (input_json::jsonb=input_snapshot-'input_sha256'),
    CHECK (encode(sha256(convert_to(input_json,'UTF8')),'hex')=input_snapshot->>'input_sha256')
);
CREATE TABLE compiler_runtime.w_inputs (
    execution_id uuid NOT NULL REFERENCES compiler_runtime.w_jobs,
    ordinal integer NOT NULL CHECK (ordinal>=0),
    knode_revision_id uuid NOT NULL REFERENCES canonical_store.knowledge_node_revisions,
    support_signature text NOT NULL CHECK (support_signature ~ '^[0-9a-f]{64}$'),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
    PRIMARY KEY(execution_id,ordinal), UNIQUE(execution_id,knode_revision_id)
);
CREATE TABLE compiler_runtime.w_edge_inputs (
    execution_id uuid NOT NULL REFERENCES compiler_runtime.w_jobs,
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
    FOREIGN KEY(semantic_kedge_revision_id,kedge_id) REFERENCES canonical_store.knowledge_edge_revisions(kedge_revision_id,kedge_id),
    FOREIGN KEY(execution_id,from_knode_revision_id) REFERENCES compiler_runtime.w_inputs(execution_id,knode_revision_id),
    FOREIGN KEY(execution_id,to_knode_revision_id) REFERENCES compiler_runtime.w_inputs(execution_id,knode_revision_id),
    CHECK ((basis_type='applicability_event')=(applicability_event_id IS NOT NULL)),
    CHECK (from_knode_revision_id<>to_knode_revision_id)
);
CREATE TABLE compiler_runtime.w_calls (
    call_id uuid NOT NULL DEFAULT uuidv7() UNIQUE CHECK (uuid_extract_version(call_id)=7),
    execution_id uuid NOT NULL REFERENCES compiler_runtime.w_jobs,
    phase text NOT NULL CHECK (phase IN ('generator','validator')),
    response jsonb NOT NULL CHECK (jsonb_typeof(response)='object'),
    response_json text NOT NULL CHECK (response_json::jsonb=response),
    receipt jsonb NOT NULL CHECK (jsonb_typeof(receipt)='object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(execution_id,phase)
);
CREATE TABLE compiler_runtime.w_events (
    event_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(event_id)=7),
    execution_id uuid NOT NULL REFERENCES compiler_runtime.w_jobs,
    state text NOT NULL,
    detail jsonb NOT NULL CHECK (jsonb_typeof(detail)='object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE canonical_store.wisdoms (
    wisdom_id uuid PRIMARY KEY CHECK (uuid_extract_version(wisdom_id)=7),
    execution_id uuid NOT NULL UNIQUE REFERENCES compiler_runtime.w_jobs,
    wisdom_kind text NOT NULL CHECK (wisdom_kind IN ('explanation','recommendation')),
    snapshot jsonb NOT NULL CHECK (jsonb_typeof(snapshot)='object'),
    snapshot_json text NOT NULL CHECK (snapshot_json::jsonb=snapshot-'snapshot_sha256'),
    snapshot_sha256 text NOT NULL CHECK (snapshot_sha256 ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL,
    UNIQUE(wisdom_id,execution_id),
    CHECK (encode(sha256(convert_to(snapshot_json,'UTF8')),'hex')=snapshot_sha256)
);
ALTER TABLE compiler_runtime.w_jobs ADD FOREIGN KEY(wisdom_id,execution_id)
    REFERENCES canonical_store.wisdoms(wisdom_id,execution_id) DEFERRABLE INITIALLY DEFERRED;

-- Valid K2W output string fields use Python's NFC + str.strip policy. Keeping
-- exact JSON text separately avoids JSONB's numeric/escaping reserialization
-- changing Python's SHA; JSONB remains the typed query/constraint surface.
CREATE FUNCTION compiler_runtime.w_normalize_strings(value jsonb) RETURNS jsonb LANGUAGE plpgsql IMMUTABLE STRICT AS $$
DECLARE result jsonb;
BEGIN
    CASE jsonb_typeof(value)
    WHEN 'object' THEN SELECT COALESCE(jsonb_object_agg(key,compiler_runtime.w_normalize_strings(item)),'{}'::jsonb)
        INTO result FROM jsonb_each(value) fields(key,item);
    WHEN 'array' THEN SELECT COALESCE(jsonb_agg(compiler_runtime.w_normalize_strings(item) ORDER BY n),'[]'::jsonb)
        INTO result FROM jsonb_array_elements(value) WITH ORDINALITY fields(item,n);
    WHEN 'string' THEN result:=to_jsonb(btrim(normalize(value#>>'{}',NFC),
        chr(9)||chr(10)||chr(11)||chr(12)||chr(13)||chr(28)||chr(29)||chr(30)||chr(31)||chr(32)||chr(133)||chr(160)||
        chr(5760)||chr(8192)||chr(8193)||chr(8194)||chr(8195)||chr(8196)||chr(8197)||chr(8198)||chr(8199)||chr(8200)||
        chr(8201)||chr(8202)||chr(8232)||chr(8233)||chr(8239)||chr(8287)||chr(12288)));
    ELSE result:=value;
    END CASE;
    RETURN result;
END; $$;

CREATE FUNCTION compiler_runtime.w_inputs_current(execution uuid) RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT EXISTS(SELECT 1 FROM compiler_runtime.w_jobs j WHERE j.execution_id=execution
        AND jsonb_array_length(j.input_snapshot->'nodes')=(SELECT count(*) FROM compiler_runtime.w_inputs WHERE execution_id=execution)
        AND jsonb_array_length(j.input_snapshot->'effective_edges')=(SELECT count(*) FROM compiler_runtime.w_edge_inputs WHERE execution_id=execution))
        AND NOT EXISTS(SELECT 1 FROM compiler_runtime.w_inputs i WHERE i.execution_id=execution
            AND (NOT compiler_runtime.current_k2k_premise(i.knode_revision_id)
                OR i.support_signature IS DISTINCT FROM canonical_store.current_knowledge_support_signature(i.knode_revision_id)))
        AND NOT EXISTS(SELECT 1 FROM compiler_runtime.w_edge_inputs e WHERE e.execution_id=execution
            AND NOT compiler_runtime.k2k_effective_edge_current(
                jsonb_populate_record(NULL::compiler_runtime.k_input_effective_edges,to_jsonb(e))))
$$;
CREATE FUNCTION compiler_runtime.guard_w_input() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE job compiler_runtime.w_jobs; node canonical_store.knowledge_node_revisions;
        edge canonical_store.knowledge_edge_revisions; logical canonical_store.knowledge_edges; expected_ref jsonb; expected_token text;
BEGIN
    SELECT * INTO STRICT job FROM compiler_runtime.w_jobs WHERE execution_id=NEW.execution_id;
    IF job.state<>'prepared' THEN RAISE EXCEPTION 'K2W input is frozen'; END IF;
    IF TG_TABLE_NAME='w_inputs' THEN
        SELECT * INTO STRICT node FROM canonical_store.knowledge_node_revisions WHERE knode_revision_id=NEW.knode_revision_id;
        IF NEW.payload IS DISTINCT FROM job.input_snapshot->'nodes'->NEW.ordinal
            OR NEW.payload->>'knode_revision_id' IS DISTINCT FROM NEW.knode_revision_id::text
            OR NEW.payload->>'knode_id' IS DISTINCT FROM node.knode_id::text
            OR NEW.payload->>'kind' IS DISTINCT FROM (SELECT kind FROM canonical_store.knowledge_nodes WHERE knode_id=node.knode_id)
            OR NEW.payload->>'statement' IS DISTINCT FROM node.statement
            OR NEW.payload->'semantic_payload' IS DISTINCT FROM node.semantic_payload
            OR NEW.payload->>'current_support_signature' IS DISTINCT FROM NEW.support_signature
            OR NOT compiler_runtime.current_k2k_premise(NEW.knode_revision_id)
            OR NEW.support_signature IS DISTINCT FROM canonical_store.current_knowledge_support_signature(NEW.knode_revision_id)
        THEN RAISE EXCEPTION 'K2W Node input does not bind current accepted K'; END IF;
    ELSE
        SELECT * INTO STRICT edge FROM canonical_store.knowledge_edge_revisions WHERE kedge_revision_id=NEW.semantic_kedge_revision_id;
        SELECT * INTO STRICT logical FROM canonical_store.knowledge_edges WHERE kedge_id=NEW.kedge_id;
        expected_ref:=jsonb_build_object('semantic_kedge_revision_id',NEW.semantic_kedge_revision_id::text,
            'from_knode_revision_id',NEW.from_knode_revision_id::text,'to_knode_revision_id',NEW.to_knode_revision_id::text,
            'applicability_basis_type',NEW.basis_type,'applicability_basis_ref',COALESCE(NEW.applicability_event_id,NEW.basis_origin_record_id)::text,
            'relation_read_state_token',NEW.relation_read_state_token);
        expected_token:=encode(sha256(convert_to(format(
            '{"applicability_status":"applicable","endpoint_support_signatures":["%s","%s"],"knowledge_state_version":%s,"pending_execution_id":null,"pending_fence_order":null}',
            NEW.from_support_signature,NEW.to_support_signature,job.expected_state_version),'UTF8')),'hex');
        IF NEW.payload IS DISTINCT FROM job.input_snapshot->'effective_edges'->NEW.ordinal
            OR NEW.payload->>'kedge_id' IS DISTINCT FROM NEW.kedge_id::text
            OR NEW.payload->'effective_edge_ref' IS DISTINCT FROM expected_ref
            OR NEW.relation_read_state_token IS DISTINCT FROM expected_token
            OR NEW.payload->>'predicate' IS DISTINCT FROM logical.predicate
            OR NEW.payload->'qualifiers' IS DISTINCT FROM edge.qualifiers
            OR NEW.payload->>'original_from_revision_id' IS DISTINCT FROM edge.from_knode_revision_id::text
            OR NEW.payload->>'original_to_revision_id' IS DISTINCT FROM edge.to_knode_revision_id::text
            OR NEW.payload->'endpoint_support_signatures' IS DISTINCT FROM jsonb_build_array(NEW.from_support_signature,NEW.to_support_signature)
            OR NOT compiler_runtime.k2k_effective_edge_current(jsonb_populate_record(NULL::compiler_runtime.k_input_effective_edges,to_jsonb(NEW)))
        THEN RAISE EXCEPTION 'K2W Edge input does not bind current effective relation'; END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER w_input_guard BEFORE INSERT ON compiler_runtime.w_inputs FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_w_input();
CREATE TRIGGER w_edge_input_guard BEFORE INSERT ON compiler_runtime.w_edge_inputs FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_w_input();

CREATE FUNCTION compiler_runtime.guard_w_call() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE job compiler_runtime.w_jobs; expected jsonb; model jsonb; generator compiler_runtime.w_calls;
BEGIN
    SELECT * INTO STRICT job FROM compiler_runtime.w_jobs WHERE execution_id=NEW.execution_id;
    expected:=CASE WHEN NEW.phase='generator' THEN job.generator_request ELSE job.validator_request END;
    SELECT payload->'model' INTO model FROM compiler_runtime.profiles WHERE profile_id=job.profile_id;
    IF job.state IS DISTINCT FROM (CASE WHEN NEW.phase='generator' THEN 'prepared' ELSE 'proposed' END)
        OR expected IS NULL OR NOT compiler_runtime.w_inputs_current(NEW.execution_id)
        OR NEW.receipt->'actual_delivery' IS DISTINCT FROM 'true'::jsonb
        OR NOT COALESCE(NEW.receipt->'profile' @> model,false)
        OR COALESCE(NEW.receipt->>'provider_ref',NEW.receipt->>'thread_ref','')=''
        OR NEW.receipt->>'input_sha256' IS DISTINCT FROM expected->>'input_sha256'
        OR NEW.receipt->>'output_sha256' IS DISTINCT FROM encode(sha256(convert_to(NEW.response_json,'UTF8')),'hex')
        OR NEW.receipt->>'prompt_sha256' IS DISTINCT FROM encode(sha256(convert_to(expected->>'prompt','UTF8')),'hex')
        OR NEW.receipt->>'schema_sha256' IS DISTINCT FROM expected->>'schema_sha256'
        OR NEW.receipt->'delivered_knowledge_revision_ids' IS DISTINCT FROM expected->'delivered_knowledge_revision_ids'
        OR NEW.receipt->'delivered_effective_edge_refs' IS DISTINCT FROM expected->'delivered_effective_edge_refs'
        OR COALESCE(NEW.receipt->'image_attachments','[]'::jsonb)<>'[]'::jsonb
    THEN RAISE EXCEPTION 'K2W model delivery does not bind frozen request'; END IF;
    IF NEW.phase='validator' THEN
        SELECT * INTO STRICT generator FROM compiler_runtime.w_calls WHERE execution_id=NEW.execution_id AND phase='generator';
        IF COALESCE(NEW.receipt->>'provider_ref',NEW.receipt->>'thread_ref')=
            COALESCE(generator.receipt->>'provider_ref',generator.receipt->>'thread_ref')
        THEN RAISE EXCEPTION 'K2W validator must be independent'; END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER w_call_guard BEFORE INSERT ON compiler_runtime.w_calls FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_w_call();

CREATE FUNCTION compiler_runtime.guard_w_job() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE call compiler_runtime.w_calls; current_version bigint; claim jsonb; ref text; relation compiler_runtime.w_edge_inputs;
BEGIN
    IF TG_OP='INSERT' THEN
        IF NEW.state<>'prepared' OR (SELECT payload->>'schema_version' FROM compiler_runtime.profiles WHERE profile_id=NEW.profile_id)
            IS DISTINCT FROM 'knowledge-wisdom-v1'
        THEN RAISE EXCEPTION 'K2W must start prepared with an exact profile'; END IF;
        IF NEW.generator_request->>'input_sha256' IS DISTINCT FROM NEW.input_snapshot->>'input_sha256'
            OR jsonb_typeof(NEW.generator_request->'prompt') IS DISTINCT FROM 'string'
            OR jsonb_typeof(NEW.generator_request->'schema') IS DISTINCT FROM 'object'
            OR jsonb_typeof(NEW.generator_request->'schema_json') IS DISTINCT FROM 'string'
            OR COALESCE(NEW.generator_request->>'schema_sha256','') !~ '^[0-9a-f]{64}$'
            OR (NEW.generator_request->>'schema_json')::jsonb IS DISTINCT FROM NEW.generator_request->'schema'
            OR NEW.generator_request->>'schema_sha256' IS DISTINCT FROM encode(sha256(convert_to(NEW.generator_request->>'schema_json','UTF8')),'hex')
            OR NEW.generator_request->'delivered_knowledge_revision_ids' IS DISTINCT FROM
                (SELECT jsonb_agg(node->>'knode_revision_id' ORDER BY n) FROM jsonb_array_elements(NEW.input_snapshot->'nodes') WITH ORDINALITY nodes(node,n))
            OR NEW.generator_request->'delivered_effective_edge_refs' IS DISTINCT FROM
                (SELECT COALESCE(jsonb_agg(edge->'effective_edge_ref' ORDER BY n),'[]'::jsonb) FROM jsonb_array_elements(NEW.input_snapshot->'effective_edges') WITH ORDINALITY edges(edge,n))
        THEN RAISE EXCEPTION 'K2W generator request must bind exact input and schema'; END IF;
        RETURN NEW;
    END IF;
    IF (to_jsonb(NEW)-ARRAY['state','generator_response','generator_receipt','answer','validator_request','validator_response','validator_receipt','validation','wisdom_id'])
        IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','generator_response','generator_receipt','answer','validator_request','validator_response','validator_receipt','validation','wisdom_id'])
    THEN RAISE EXCEPTION 'K2W request is immutable'; END IF;
    SELECT version INTO STRICT current_version FROM compiler_runtime.knowledge_state WHERE singleton FOR UPDATE;
    IF NEW.expected_state_version<>current_version OR NOT compiler_runtime.w_inputs_current(NEW.execution_id)
    THEN RAISE EXCEPTION 'K2W read state changed'; END IF;
    IF OLD.state='prepared' AND NEW.state='proposed' THEN
        SELECT * INTO STRICT call FROM compiler_runtime.w_calls WHERE execution_id=NEW.execution_id AND phase='generator';
        IF NEW.generator_response IS DISTINCT FROM call.response OR NEW.generator_receipt IS DISTINCT FROM call.receipt
            OR NEW.answer IS DISTINCT FROM compiler_runtime.w_normalize_strings(call.response)
            OR jsonb_typeof(NEW.validator_request->'prompt') IS DISTINCT FROM 'string'
            OR jsonb_typeof(NEW.validator_request->'schema') IS DISTINCT FROM 'object'
            OR jsonb_typeof(NEW.validator_request->'schema_json') IS DISTINCT FROM 'string'
            OR COALESCE(NEW.validator_request->>'schema_sha256','') !~ '^[0-9a-f]{64}$'
            OR jsonb_typeof(NEW.validator_request->'validation_context_json') IS DISTINCT FROM 'string'
            OR (NEW.validator_request->>'validation_context_json')::jsonb IS DISTINCT FROM jsonb_build_object('input',NEW.input_snapshot,'answer',NEW.answer)
            OR NEW.validator_request->>'input_sha256' IS DISTINCT FROM encode(sha256(convert_to(NEW.validator_request->>'validation_context_json','UTF8')),'hex')
            OR (NEW.validator_request->>'schema_json')::jsonb IS DISTINCT FROM NEW.validator_request->'schema'
            OR NEW.validator_request->>'schema_sha256' IS DISTINCT FROM encode(sha256(convert_to(NEW.validator_request->>'schema_json','UTF8')),'hex')
            OR NEW.validator_request->'delivered_knowledge_revision_ids' IS DISTINCT FROM NEW.generator_request->'delivered_knowledge_revision_ids'
            OR NEW.validator_request->'delivered_effective_edge_refs' IS DISTINCT FROM NEW.generator_request->'delivered_effective_edge_refs'
        THEN RAISE EXCEPTION 'K2W proposal must retain actual generation'; END IF;
        IF NEW.answer-ARRAY['status','claims','recommendation','unresolved']<>'{}'::jsonb
            OR NOT COALESCE(NEW.answer->>'status' IN ('answered','insufficient'),false)
            OR jsonb_typeof(NEW.answer->'claims') IS DISTINCT FROM 'array'
            OR jsonb_typeof(NEW.answer->'unresolved') IS DISTINCT FROM 'array'
            OR (NEW.answer->>'status'='answered' AND jsonb_array_length(NEW.answer->'claims')=0)
            OR (NEW.answer->>'status'='insufficient' AND jsonb_array_length(NEW.answer->'unresolved')=0)
            OR (NEW.input_snapshot->>'wisdom_kind'='explanation' AND NEW.answer->'recommendation' IS DISTINCT FROM 'null'::jsonb)
        THEN RAISE EXCEPTION 'K2W answer has invalid fields or epistemic surface'; END IF;
        FOR claim IN SELECT value FROM jsonb_array_elements(NEW.answer->'claims') LOOP
            IF claim-ARRAY['claim_key','text','epistemic_basis','k_revision_ids','effective_edge_revision_ids','assumptions','limitations']<>'{}'::jsonb
                OR COALESCE(claim->>'claim_key','') !~ '^[A-Za-z][A-Za-z0-9_.-]{0,127}$'
                OR COALESCE(claim->>'text','')=''
                OR NOT COALESCE(claim->>'epistemic_basis' IN ('accepted_knowledge','advisory_recommendation'),false)
                OR (claim->>'epistemic_basis'='advisory_recommendation' AND NEW.input_snapshot->>'wisdom_kind'<>'recommendation')
                OR jsonb_typeof(claim->'k_revision_ids') IS DISTINCT FROM 'array'
                OR jsonb_array_length(claim->'k_revision_ids')=0
                OR jsonb_typeof(claim->'effective_edge_revision_ids') IS DISTINCT FROM 'array'
                OR jsonb_typeof(claim->'assumptions') IS DISTINCT FROM 'array'
                OR jsonb_typeof(claim->'limitations') IS DISTINCT FROM 'array'
            THEN RAISE EXCEPTION 'K2W claim has invalid fields'; END IF;
            FOR ref IN SELECT jsonb_array_elements_text(claim->'k_revision_ids') LOOP
                IF NOT EXISTS(SELECT 1 FROM compiler_runtime.w_inputs WHERE execution_id=NEW.execution_id AND knode_revision_id=ref::uuid)
                THEN RAISE EXCEPTION 'K2W claim cites an undelivered Node'; END IF;
            END LOOP;
            FOR ref IN SELECT jsonb_array_elements_text(claim->'effective_edge_revision_ids') LOOP
                SELECT * INTO relation FROM compiler_runtime.w_edge_inputs WHERE execution_id=NEW.execution_id AND semantic_kedge_revision_id=ref::uuid;
                IF NOT FOUND OR NOT (claim->'k_revision_ids' @> jsonb_build_array(relation.from_knode_revision_id::text,relation.to_knode_revision_id::text))
                THEN RAISE EXCEPTION 'K2W claim needs exact Edge and both endpoints'; END IF;
            END LOOP;
        END LOOP;
    ELSIF OLD.state='proposed' AND NEW.state IN ('validated','needs_human') THEN
        SELECT * INTO STRICT call FROM compiler_runtime.w_calls WHERE execution_id=NEW.execution_id AND phase='validator';
        IF NEW.validator_response IS DISTINCT FROM call.response OR NEW.validator_receipt IS DISTINCT FROM call.receipt
            OR NEW.validation IS DISTINCT FROM compiler_runtime.w_normalize_strings(call.response)
            OR (NEW.state='validated') IS DISTINCT FROM (NEW.validation->>'verdict'='accepted')
            OR NEW.generator_response IS DISTINCT FROM OLD.generator_response
            OR NEW.generator_receipt IS DISTINCT FROM OLD.generator_receipt OR NEW.answer IS DISTINCT FROM OLD.answer
            OR NEW.validator_request IS DISTINCT FROM OLD.validator_request
        THEN RAISE EXCEPTION 'K2W validation must retain actual independent review'; END IF;
    ELSIF OLD.state='validated' AND NEW.state='completed' THEN
        IF to_jsonb(NEW)-ARRAY['state','wisdom_id'] IS DISTINCT FROM to_jsonb(OLD)-ARRAY['state','wisdom_id']
        THEN RAISE EXCEPTION 'K2W completion only binds an immutable W'; END IF;
    ELSE RAISE EXCEPTION 'Invalid K2W state transition'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER w_job_guard BEFORE INSERT OR UPDATE ON compiler_runtime.w_jobs FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_w_job();

CREATE FUNCTION canonical_store.guard_wisdom() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE job compiler_runtime.w_jobs; ref text; edge_ref jsonb; claim jsonb; current_version bigint;
        actual_refs jsonb; expected_refs jsonb; expected_citations jsonb;
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
        OR NEW.snapshot->'used_information_ids' IS DISTINCT FROM '[]'::jsonb
        OR NEW.snapshot->'generation_profile' IS DISTINCT FROM (SELECT payload FROM compiler_runtime.profiles WHERE profile_id=job.profile_id)
    THEN RAISE EXCEPTION 'W requires frozen exact inputs and accepted independent validation'; END IF;
    SELECT COALESCE(jsonb_agg(value ORDER BY value),'[]'::jsonb) INTO actual_refs
        FROM jsonb_array_elements_text(NEW.snapshot->'used_k_revision_ids');
    SELECT COALESCE(jsonb_agg(ref ORDER BY ref),'[]'::jsonb) INTO expected_refs FROM (
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
CREATE TRIGGER wisdom_guard BEFORE INSERT ON canonical_store.wisdoms FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_wisdom();
CREATE FUNCTION compiler_runtime.w_completion_exists() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM compiler_runtime.w_jobs WHERE execution_id=NEW.execution_id AND state='completed' AND wisdom_id=NEW.wisdom_id)
    THEN RAISE EXCEPTION 'W and its completed execution must commit atomically'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER w_completion_atomic AFTER INSERT ON canonical_store.wisdoms DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.w_completion_exists();
CREATE TRIGGER wisdom_immutable BEFORE UPDATE OR DELETE ON canonical_store.wisdoms FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation();
CREATE TRIGGER w_job_no_delete BEFORE DELETE ON compiler_runtime.w_jobs FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation();
CREATE TRIGGER w_input_immutable BEFORE UPDATE OR DELETE ON compiler_runtime.w_inputs FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation();
CREATE TRIGGER w_edge_input_immutable BEFORE UPDATE OR DELETE ON compiler_runtime.w_edge_inputs FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation();
CREATE TRIGGER w_call_immutable BEFORE UPDATE OR DELETE ON compiler_runtime.w_calls FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation();
CREATE TRIGGER w_event_immutable BEFORE UPDATE OR DELETE ON compiler_runtime.w_events FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation();
GRANT SELECT,INSERT,UPDATE ON compiler_runtime.w_jobs TO palimpsest;
GRANT SELECT,INSERT ON compiler_runtime.w_inputs,compiler_runtime.w_edge_inputs,compiler_runtime.w_calls,compiler_runtime.w_events,canonical_store.wisdoms TO palimpsest;
GRANT EXECUTE ON FUNCTION compiler_runtime.w_inputs_current(uuid) TO palimpsest;
