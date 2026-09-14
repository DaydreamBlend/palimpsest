-- A separate explicitly confirmed D2K operation. I2K remains I-only.
ALTER TABLE compiler_runtime.operation_executions DROP CONSTRAINT operation_executions_operation_check;
ALTER TABLE compiler_runtime.operation_executions ADD CHECK (operation IN ('d2i','i2k','n2e','k2k','d2k'));
ALTER TABLE compiler_runtime.k_compilation_records DROP CONSTRAINT k_compilation_records_record_type_check;
ALTER TABLE compiler_runtime.k_compilation_records ADD CHECK (record_type IN ('i2k','n2e','k2k','d2k'));
ALTER TABLE compiler_runtime.k_compilation_records DROP CONSTRAINT k_record_result_kind;
ALTER TABLE compiler_runtime.k_compilation_records ADD CONSTRAINT k_record_result_kind
    CHECK ((record_type IN ('i2k','k2k','d2k') AND result_edge_id IS NULL)
        OR (record_type='n2e' AND result_node_id IS NULL));

CREATE TABLE compiler_runtime.d2k_preparations (
    preparation_id uuid PRIMARY KEY CHECK (uuid_extract_version(preparation_id) IS NOT DISTINCT FROM 7),
    request_fingerprint text NOT NULL CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
    data_id text NOT NULL REFERENCES canonical_store.data,
    packet jsonb NOT NULL CHECK (jsonb_typeof(packet)='object'),
    manifest jsonb NOT NULL CHECK (jsonb_typeof(manifest)='object'),
    manifest_sha256 text NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE compiler_runtime.d2k_source_views (
    view_id uuid PRIMARY KEY CHECK (uuid_extract_version(view_id) IS NOT DISTINCT FROM 7),
    preparation_id uuid NOT NULL REFERENCES compiler_runtime.d2k_preparations,
    ordinal integer NOT NULL CHECK (ordinal>=0),
    body jsonb NOT NULL CHECK (jsonb_typeof(body)='object'),
    UNIQUE(preparation_id,ordinal)
);
CREATE TABLE compiler_runtime.d2k_authorizations (
    authorization_id uuid PRIMARY KEY CHECK (uuid_extract_version(authorization_id) IS NOT DISTINCT FROM 7),
    preparation_id uuid NOT NULL REFERENCES compiler_runtime.d2k_preparations,
    manifest_sha256 text NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    actor_ref text NOT NULL CHECK (length(btrim(actor_ref))>0),
    confirmation_method text NOT NULL CHECK (confirmation_method='explicit_local_cli_manifest'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE compiler_runtime.d2k_execution_authorizations (
    execution_id uuid PRIMARY KEY REFERENCES compiler_runtime.operation_executions,
    authorization_id uuid NOT NULL REFERENCES compiler_runtime.d2k_authorizations,
    prior_execution_id uuid REFERENCES compiler_runtime.operation_executions,
    CHECK (prior_execution_id IS DISTINCT FROM execution_id)
);
CREATE UNIQUE INDEX d2k_one_initial_execution ON compiler_runtime.d2k_execution_authorizations(authorization_id)
    WHERE prior_execution_id IS NULL;
CREATE TABLE compiler_runtime.d2k_decisions (
    record_id uuid PRIMARY KEY REFERENCES compiler_runtime.k_compilation_records,
    validation jsonb NOT NULL CHECK (jsonb_typeof(validation)='object')
);
CREATE TABLE canonical_store.knowledge_data_groundings (
    grounding_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(grounding_id) IS NOT DISTINCT FROM 7),
    node_revision_id uuid NOT NULL REFERENCES canonical_store.knowledge_node_revisions,
    data_id text NOT NULL REFERENCES canonical_store.data,
    view_id uuid NOT NULL REFERENCES compiler_runtime.d2k_source_views,
    evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence)='object'),
    origin_record_id uuid NOT NULL REFERENCES compiler_runtime.k_compilation_records,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX knowledge_data_record_citation ON canonical_store.knowledge_data_groundings
    (origin_record_id,view_id,(evidence->'locator'),(evidence->>'source_role'));
CREATE INDEX knowledge_data_revision ON canonical_store.knowledge_data_groundings(node_revision_id);
CREATE INDEX knowledge_data_owner ON canonical_store.knowledge_data_groundings(data_id);

CREATE FUNCTION compiler_runtime.is_d2k_execution(id uuid) RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT EXISTS(SELECT 1 FROM compiler_runtime.operation_executions e JOIN compiler_runtime.profiles p USING(profile_id)
        WHERE e.execution_id=id AND e.operation='d2k' AND p.payload->>'schema_version'='explicit-source-d2k-v1')
$$;
CREATE FUNCTION compiler_runtime.guard_d2k_preparation() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE original canonical_store.data;
BEGIN
    SELECT * INTO STRICT original FROM canonical_store.data WHERE data_id=NEW.data_id;
    IF NEW.packet->>'schema_version' IS DISTINCT FROM 'd2k-input-v1'
        OR NEW.packet->>'data_id' IS DISTINCT FROM NEW.data_id
        OR NEW.packet->>'media_type' IS DISTINCT FROM original.media_type
        OR (NEW.packet->>'original_byte_size')::bigint IS DISTINCT FROM original.byte_size
        OR jsonb_typeof(NEW.packet->'views') IS DISTINCT FROM 'array' OR jsonb_array_length(NEW.packet->'views')=0
        OR NEW.manifest->>'schema_version' IS DISTINCT FROM 'user-requested-d2k-v1'
        OR NEW.manifest->>'operation' IS DISTINCT FROM 'd2k'
        OR NEW.manifest->>'preparation_id' IS DISTINCT FROM NEW.preparation_id::text
        OR NEW.manifest->>'data_id' IS DISTINCT FROM NEW.data_id OR NEW.manifest->'input' IS DISTINCT FROM NEW.packet
        OR NEW.manifest->>'claim_policy' IS DISTINCT FROM 'explicit_source_content_only'
        OR NEW.manifest->'new_inference_allowed' IS DISTINCT FROM 'false'::jsonb
        OR NEW.manifest->'d2i_repair_allowed' IS DISTINCT FROM 'false'::jsonb
        OR NEW.manifest->'information_created' IS DISTINCT FROM '0'::jsonb
        OR NEW.manifest->'allowed_phases' IS DISTINCT FROM '["generator","validator","same_scope_review"]'::jsonb
        OR jsonb_typeof(NEW.manifest->'model') IS DISTINCT FROM 'object'
        OR jsonb_typeof(NEW.manifest->'failure') IS DISTINCT FROM 'object'
        OR jsonb_typeof(NEW.manifest->'existing_knowledge') IS DISTINCT FROM 'array'
    THEN RAISE EXCEPTION 'D2K preparation must bind original Data, source-only scope and reviewable intent'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER d2k_preparation_guard BEFORE INSERT ON compiler_runtime.d2k_preparations
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_d2k_preparation();
CREATE FUNCTION compiler_runtime.guard_d2k_view() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE packet jsonb;
BEGIN
    SELECT p.packet INTO STRICT packet FROM compiler_runtime.d2k_preparations p WHERE preparation_id=NEW.preparation_id;
    IF packet->'views'->NEW.ordinal IS DISTINCT FROM NEW.body
        OR NEW.body->>'view_id' IS DISTINCT FROM NEW.view_id::text
        OR NEW.body->>'data_id' IS DISTINCT FROM packet->>'data_id'
        OR NEW.body->'original_byte_size' IS DISTINCT FROM packet->'original_byte_size'
        OR COALESCE(NEW.body->>'kind','') NOT IN ('text','pdf_page')
    THEN RAISE EXCEPTION 'D2K views must be exact prepared original-source views'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER d2k_view_guard BEFORE INSERT ON compiler_runtime.d2k_source_views
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_d2k_view();
CREATE FUNCTION compiler_runtime.guard_d2k_authorization() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM compiler_runtime.d2k_preparations p WHERE p.preparation_id=NEW.preparation_id
        AND p.manifest_sha256=NEW.manifest_sha256
        AND jsonb_array_length(p.packet->'views')=(SELECT count(*) FROM compiler_runtime.d2k_source_views v WHERE v.preparation_id=p.preparation_id))
    THEN RAISE EXCEPTION 'Explicit D2K confirmation must match the fully prepared exact manifest'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER d2k_authorization_guard BEFORE INSERT ON compiler_runtime.d2k_authorizations
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_d2k_authorization();

-- Model-safe catalog projection: no raw I/D quotes or hidden provenance reach the model catalog.
CREATE FUNCTION compiler_runtime.d2k_catalog_projection(input_node jsonb) RETURNS jsonb LANGUAGE sql IMMUTABLE AS $$
    SELECT COALESCE(jsonb_object_agg(entry.key,entry.value),'{}'::jsonb)
        || jsonb_build_object('current_applicability',COALESCE(input_node->'current_applicability','"current_premises"'::jsonb))
    FROM jsonb_each(input_node) entry WHERE entry.key=ANY(ARRAY['knode_id','kind','current_revision_id',
        'knode_revision_id','semantic_payload','statement','identity_fingerprint','content_fingerprint',
        'identity_scope','source_data_id','origin_record_id','current_applicability'])
$$;
CREATE FUNCTION compiler_runtime.d2k_current_catalog_node(revision uuid) RETURNS jsonb LANGUAGE sql STABLE AS $$
    SELECT jsonb_build_object('knode_id',n.knode_id::text,'kind',n.kind,'current_revision_id',n.current_revision_id::text,
        'knode_revision_id',v.knode_revision_id::text,'semantic_payload',v.semantic_payload,'statement',v.statement,
        'identity_fingerprint',v.identity_fingerprint,'content_fingerprint',v.content_fingerprint,
        'identity_scope',s.identity_scope,'source_data_id',s.source_data_id,'origin_record_id',v.origin_record_id::text,
        'current_applicability',CASE WHEN compiler_runtime.current_k2k_premise(v.knode_revision_id)
            THEN 'current_premises' ELSE 'needs_revalidation' END)
    FROM canonical_store.knowledge_nodes n JOIN canonical_store.knowledge_node_revisions v ON v.knode_revision_id=n.current_revision_id
    LEFT JOIN canonical_store.knowledge_node_scopes s ON s.knode_id=n.knode_id
    JOIN compiler_runtime.k_compilation_records r ON r.record_id=v.origin_record_id
    WHERE v.knode_revision_id=revision AND r.result_node_id=n.knode_id AND r.result_node_revision_id=v.knode_revision_id
        AND r.disposition IN ('accepted_new','accepted_revision')
$$;

CREATE FUNCTION compiler_runtime.guard_d2k_execution() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE grant_row compiler_runtime.d2k_authorizations; preparation compiler_runtime.d2k_preparations;
        snapshot jsonb; e compiler_runtime.operation_executions; allowed_catalog jsonb; entry jsonb;
        current_node jsonb; own_result record;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('d2k-grant:'||NEW.authorization_id::text,0));
    SELECT * INTO STRICT grant_row FROM compiler_runtime.d2k_authorizations WHERE authorization_id=NEW.authorization_id;
    SELECT * INTO STRICT preparation FROM compiler_runtime.d2k_preparations WHERE preparation_id=grant_row.preparation_id;
    SELECT * INTO STRICT e FROM compiler_runtime.operation_executions WHERE execution_id=NEW.execution_id;
    SELECT input_snapshot INTO STRICT snapshot FROM compiler_runtime.k_execution_contexts WHERE execution_id=NEW.execution_id;
    IF NOT compiler_runtime.is_d2k_execution(e.execution_id) OR e.state<>'prepared' OR e.data_id<>preparation.data_id
        OR snapshot->'input' IS DISTINCT FROM preparation.packet
        OR snapshot->'authorization'->>'authorization_id' IS DISTINCT FROM NEW.authorization_id::text
        OR snapshot->'authorization'->>'manifest_sha256' IS DISTINCT FROM preparation.manifest_sha256
        OR snapshot->'authorization'->>'actor_ref' IS DISTINCT FROM grant_row.actor_ref
        OR snapshot->'authorization'->>'preparation_id' IS DISTINCT FROM preparation.preparation_id::text
        OR COALESCE(snapshot->'data_versions','[]'::jsonb) IS DISTINCT FROM preparation.manifest->'data_versions'
        OR COALESCE(snapshot->>'data_version_mode','current') IS DISTINCT FROM preparation.manifest->>'data_version_mode'
        OR NOT EXISTS(SELECT 1 FROM compiler_runtime.profiles p WHERE p.profile_id=e.profile_id AND p.payload->'model'=preparation.manifest->'model')
        OR EXISTS(SELECT 1 FROM compiler_runtime.k_input_information WHERE execution_id=e.execution_id)
        OR EXISTS(SELECT 1 FROM compiler_runtime.k_input_node_revisions WHERE execution_id=e.execution_id)
    THEN RAISE EXCEPTION 'D2K needs exact user-confirmed original scope, not I or inferred-premise input'; END IF;
    IF snapshot->'authorization' IS DISTINCT FROM jsonb_build_object(
        'authorization_id',NEW.authorization_id::text,'preparation_id',preparation.preparation_id::text,
        'manifest_sha256',preparation.manifest_sha256,'actor_ref',grant_row.actor_ref,'failure',preparation.manifest->'failure')
        OR jsonb_typeof(snapshot->'existing_nodes') IS DISTINCT FROM 'array'
    THEN RAISE EXCEPTION 'D2K authorization context and catalog must preserve the exact confirmed scope'; END IF;
    allowed_catalog:=preparation.manifest->'existing_knowledge';
    FOR entry IN SELECT value FROM jsonb_array_elements(allowed_catalog) LOOP
        IF entry IS DISTINCT FROM compiler_runtime.d2k_catalog_projection(entry)
            OR entry IS DISTINCT FROM compiler_runtime.d2k_current_catalog_node((entry->>'knode_revision_id')::uuid)
        THEN RAISE EXCEPTION 'The approved D2K Knowledge catalog changed or contains unapproved metadata'; END IF;
    END LOOP;
    FOR own_result IN SELECT DISTINCT r.result_node_revision_id FROM compiler_runtime.k_compilation_records r
        JOIN compiler_runtime.d2k_execution_authorizations x USING(execution_id)
        WHERE x.authorization_id=NEW.authorization_id
            AND r.disposition IN ('accepted_new','accepted_revision','reused','no_material_delta') LOOP
        current_node:=compiler_runtime.d2k_current_catalog_node(own_result.result_node_revision_id);
        IF current_node IS NULL THEN RAISE EXCEPTION 'Prior results of this D2K request are no longer current'; END IF;
        IF NOT EXISTS(SELECT 1 FROM jsonb_array_elements(allowed_catalog) item
            WHERE item->>'knode_revision_id'=own_result.result_node_revision_id::text)
        THEN allowed_catalog:=allowed_catalog||jsonb_build_array(current_node); END IF;
    END LOOP;
    IF jsonb_array_length(snapshot->'existing_nodes')<>jsonb_array_length(allowed_catalog)
        OR (SELECT count(DISTINCT item->>'knode_revision_id') FROM jsonb_array_elements(snapshot->'existing_nodes') item)
            <>jsonb_array_length(snapshot->'existing_nodes')
        OR EXISTS(SELECT 1 FROM jsonb_array_elements(snapshot->'existing_nodes') item
            WHERE NOT EXISTS(SELECT 1 FROM jsonb_array_elements(allowed_catalog) approved
                WHERE approved=compiler_runtime.d2k_catalog_projection(item)))
        OR EXISTS(SELECT 1 FROM jsonb_array_elements(allowed_catalog) approved
            WHERE NOT EXISTS(SELECT 1 FROM jsonb_array_elements(snapshot->'existing_nodes') item
                WHERE approved=compiler_runtime.d2k_catalog_projection(item)))
    THEN RAISE EXCEPTION 'D2K may expose only its approved catalog and exact current results from this same request'; END IF;
    IF NEW.prior_execution_id IS NULL AND EXISTS(SELECT 1 FROM compiler_runtime.d2k_execution_authorizations
        WHERE authorization_id=NEW.authorization_id)
    THEN RAISE EXCEPTION 'A used D2K grant cannot start a second independent execution'; END IF;
    IF NEW.prior_execution_id IS NOT NULL AND EXISTS(SELECT 1 FROM compiler_runtime.d2k_execution_authorizations
        WHERE authorization_id=NEW.authorization_id AND prior_execution_id=NEW.prior_execution_id)
    THEN RAISE EXCEPTION 'D2K retry must continue the latest grant leaf, not branch from earlier history'; END IF;
    IF NEW.prior_execution_id IS NOT NULL AND NOT EXISTS(
        SELECT 1 FROM compiler_runtime.d2k_execution_authorizations previous_link JOIN compiler_runtime.operation_executions prior USING(execution_id)
        WHERE previous_link.execution_id=NEW.prior_execution_id AND previous_link.authorization_id=NEW.authorization_id AND prior.state IN ('needs_human','failed'))
    THEN RAISE EXCEPTION 'A D2K continuation needs an unresolved execution in the same user request'; END IF;
    IF EXISTS(SELECT 1 FROM compiler_runtime.d2k_execution_authorizations x JOIN compiler_runtime.operation_executions active USING(execution_id)
        WHERE x.authorization_id=NEW.authorization_id AND active.state IN ('prepared','proposed'))
    THEN RAISE EXCEPTION 'The authorized D2K request already has an active execution'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER d2k_execution_guard BEFORE INSERT ON compiler_runtime.d2k_execution_authorizations
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_d2k_execution();
CREATE FUNCTION compiler_runtime.check_d2k_context() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF compiler_runtime.is_d2k_execution(NEW.execution_id) AND NOT EXISTS(
        SELECT 1 FROM compiler_runtime.d2k_execution_authorizations WHERE execution_id=NEW.execution_id)
    THEN RAISE EXCEPTION 'D2K cannot execute without a real manifest confirmation record'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER d2k_context_guard AFTER INSERT ON compiler_runtime.k_execution_contexts
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION compiler_runtime.check_d2k_context();

CREATE FUNCTION compiler_runtime.guard_d2k_decision() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE candidate jsonb;
BEGIN
    SELECT c.body INTO candidate FROM compiler_runtime.k_compilation_records r
        JOIN compiler_runtime.operation_executions e USING(execution_id)
        JOIN compiler_runtime.k_temporary_candidates c USING(record_id)
        WHERE r.record_id=NEW.record_id AND r.record_type='d2k' AND e.state='proposed'
            AND r.disposition IN ('pending','needs_human') AND compiler_runtime.is_d2k_execution(e.execution_id)
            AND NEW.validation->>'candidate_key'=c.body->>'candidate_key'
            AND c.body->>'claim_basis'='explicit_source_content' AND c.body->'is_inferred'='false'::jsonb;
    IF candidate IS NULL OR NEW.validation ?| ARRAY['_direct_evidence_hashes','_candidate_kind','_identity_scope','_source_data_id']
        OR jsonb_typeof(candidate->'direct_evidence') IS DISTINCT FROM 'array'
        OR jsonb_array_length(candidate->'direct_evidence')=0
    THEN RAISE EXCEPTION 'D2K validation must bind its actual source-only proposal; DB witnesses are not provider input'; END IF;
    NEW.validation:=NEW.validation||jsonb_build_object(
        '_candidate_kind',candidate->'kind','_identity_scope',candidate->'identity_scope','_source_data_id',candidate->'source_data_id',
        '_direct_evidence_hashes',(SELECT jsonb_agg(fingerprint ORDER BY fingerprint) FROM (
            SELECT encode(sha256(convert_to(item::text,'UTF8')),'hex') AS fingerprint
            FROM jsonb_array_elements(candidate->'direct_evidence') item) hashes));
    RETURN NEW;
END; $$;
CREATE TRIGGER d2k_decision_guard BEFORE INSERT ON compiler_runtime.d2k_decisions
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.guard_d2k_decision();
CREATE FUNCTION canonical_store.d2k_line_breaks_before(body text,offset_chars integer) RETURNS integer LANGUAGE sql IMMUTABLE AS $$
    SELECT regexp_count(left(body,offset_chars),E'\r\n|\r|\n')
        - CASE WHEN offset_chars>0 AND substring(body FROM offset_chars FOR 2)=E'\r\n' THEN 1 ELSE 0 END
$$;

CREATE FUNCTION canonical_store.guard_data_grounding() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r compiler_runtime.k_compilation_records; candidate jsonb; source_view jsonb; expected_locator jsonb;
        start_char integer; end_char integer;
BEGIN
    SELECT * INTO STRICT r FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.origin_record_id;
    SELECT body INTO candidate FROM compiler_runtime.k_temporary_candidates WHERE record_id=r.record_id;
    SELECT v.body INTO source_view FROM compiler_runtime.d2k_source_views v
        JOIN compiler_runtime.d2k_authorizations a USING(preparation_id)
        JOIN compiler_runtime.d2k_execution_authorizations x USING(authorization_id)
        WHERE x.execution_id=r.execution_id AND v.view_id=NEW.view_id;
    IF r.record_type<>'d2k' OR r.disposition NOT IN ('pending','needs_human') OR candidate IS NULL OR source_view IS NULL
        OR NOT compiler_runtime.is_d2k_execution(r.execution_id)
        OR NOT EXISTS(SELECT 1 FROM compiler_runtime.operation_executions WHERE execution_id=r.execution_id AND state='proposed')
        OR NEW.evidence->>'view_id' IS DISTINCT FROM NEW.view_id::text
        OR NEW.evidence->>'data_id' IS DISTINCT FROM NEW.data_id OR source_view->>'data_id' IS DISTINCT FROM NEW.data_id
        OR NEW.evidence-ARRAY['view_id','data_id','representation','quote','quote_sha256','char_start','char_end','locator','media_sha256','source_role']<>'{}'::jsonb
        OR COALESCE(NEW.evidence->>'source_role','') NOT IN ('abstract','results','methods','figure','discussion','other')
        OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(candidate->'direct_evidence') item WHERE item=NEW.evidence)
        OR NOT EXISTS(SELECT 1 FROM compiler_runtime.d2k_decisions d WHERE d.record_id=r.record_id
            AND d.validation->>'verdict' IN ('accepted','reused')
            AND d.validation->'source_explicit'='true'::jsonb AND d.validation->'no_novel_inference'='true'::jsonb
            AND d.validation->'source_identity_preserved'='true'::jsonb AND d.validation->'scope_correct'='true'::jsonb
            AND d.validation->'importance_justified'='true'::jsonb)
        OR EXISTS(SELECT 1 FROM canonical_store.knowledge_node_revisions v
            JOIN canonical_store.knowledge_nodes n USING(knode_id)
            LEFT JOIN canonical_store.knowledge_node_scopes scope USING(knode_id)
            WHERE v.knode_revision_id=NEW.node_revision_id AND (n.kind IS DISTINCT FROM candidate->>'kind'
                OR (scope.knode_id IS NOT NULL AND (scope.identity_scope IS DISTINCT FROM candidate->>'identity_scope'
                    OR scope.source_data_id IS DISTINCT FROM candidate->>'source_data_id'))
                OR (scope.identity_scope='source' AND scope.source_data_id IS DISTINCT FROM NEW.data_id)))
    THEN RAISE EXCEPTION 'Direct D grounding requires an authorized D2K view and independent source-only validation'; END IF;
    IF source_view->>'kind'='text' THEN
        IF NEW.evidence->>'representation' IS DISTINCT FROM 'original_utf8_excerpt'
            OR NEW.evidence->'media_sha256' IS DISTINCT FROM 'null'::jsonb
            OR COALESCE(NEW.evidence->>'char_start','') !~ '^[0-9]+$'
            OR COALESCE(NEW.evidence->>'char_end','') !~ '^[0-9]+$'
            OR COALESCE(NEW.evidence->>'quote','') !~ '[^[:space:]]'
        THEN RAISE EXCEPTION 'D2K text citation requires a nonempty exact Unicode range'; END IF;
        start_char:=(NEW.evidence->>'char_start')::integer; end_char:=(NEW.evidence->>'char_end')::integer;
        expected_locator:=jsonb_build_object(
            'byte_start',(source_view->'locator'->>'byte_start')::bigint+octet_length(left(source_view->>'text',start_char)),
            'byte_end',(source_view->'locator'->>'byte_start')::bigint+octet_length(left(source_view->>'text',end_char)),
            'char_start',(source_view->'locator'->>'char_start')::bigint+start_char,
            'char_end',(source_view->'locator'->>'char_start')::bigint+end_char,
            'line_start',(source_view->'locator'->>'line_start')::integer+canonical_store.d2k_line_breaks_before(source_view->>'text',start_char),
            'line_end',(source_view->'locator'->>'line_start')::integer+canonical_store.d2k_line_breaks_before(source_view->>'text',end_char-1));
        IF start_char<0 OR end_char<=start_char OR end_char>length(source_view->>'text')
            OR NEW.evidence->>'quote' IS DISTINCT FROM substring(source_view->>'text' FROM start_char+1 FOR end_char-start_char)
            OR NEW.evidence->'locator' IS DISTINCT FROM expected_locator
        THEN RAISE EXCEPTION 'Original text grounding must match exact byte, character and line coordinates'; END IF;
    ELSE
        expected_locator:=jsonb_build_object('coordinate_system','pdf_points_top_left',
            'page_index',source_view->'page_index','page_count',source_view->'page_count','page_size',source_view->'page_size',
            'bbox',jsonb_build_array(0,0,source_view->'page_size'->0,source_view->'page_size'->1),
            'source_geometry',source_view->'source_geometry','transforms',source_view->'transforms');
        IF source_view->>'kind' IS DISTINCT FROM 'pdf_page'
            OR NEW.evidence->>'representation' IS DISTINCT FROM 'original_pdf_page_image'
            OR NEW.evidence->>'quote' IS DISTINCT FROM '' OR NEW.evidence->'char_start' IS DISTINCT FROM '0'::jsonb
            OR NEW.evidence->'char_end' IS DISTINCT FROM '0'::jsonb
            OR NEW.evidence->>'media_sha256' IS DISTINCT FROM source_view->>'image_sha256'
            OR NEW.evidence->'locator' IS DISTINCT FROM expected_locator
        THEN RAISE EXCEPTION 'Original PDF grounding must retain its exact page image, bounds and renderer geometry'; END IF;
    END IF;
    IF NEW.evidence->>'quote_sha256' IS DISTINCT FROM encode(sha256(convert_to(NEW.evidence->>'quote','UTF8')),'hex')
    THEN RAISE EXCEPTION 'D grounding quote hash differs from its retained quote'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER data_grounding_guard BEFORE INSERT ON canonical_store.knowledge_data_groundings
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_data_grounding();
CREATE FUNCTION canonical_store.check_data_grounding_commit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r compiler_runtime.k_compilation_records; e compiler_runtime.operation_executions;
        context compiler_runtime.k_execution_contexts; decision jsonb; actual_hashes jsonb; delivered_views jsonb;
BEGIN
    SELECT * INTO STRICT r FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.origin_record_id;
    SELECT * INTO STRICT e FROM compiler_runtime.operation_executions WHERE execution_id=r.execution_id;
    SELECT * INTO STRICT context FROM compiler_runtime.k_execution_contexts WHERE execution_id=r.execution_id;
    SELECT validation INTO STRICT decision FROM compiler_runtime.d2k_decisions WHERE record_id=r.record_id;
    SELECT jsonb_agg(encode(sha256(convert_to(g.evidence::text,'UTF8')),'hex')
        ORDER BY encode(sha256(convert_to(g.evidence::text,'UTF8')),'hex')) INTO actual_hashes
        FROM canonical_store.knowledge_data_groundings g WHERE g.origin_record_id=r.record_id;
    SELECT jsonb_agg(item->'view_id' ORDER BY ordinal) INTO delivered_views
        FROM jsonb_array_elements(context.input_snapshot->'input'->'views') WITH ORDINALITY items(item,ordinal);
    IF r.record_type<>'d2k' OR r.result_node_revision_id IS DISTINCT FROM NEW.node_revision_id
        OR r.disposition NOT IN ('accepted_new','reused','no_material_delta')
        OR decision->'_direct_evidence_hashes' IS DISTINCT FROM actual_hashes
        OR NOT EXISTS(SELECT 1 FROM canonical_store.knowledge_node_revisions v
            JOIN canonical_store.knowledge_nodes n USING(knode_id)
            JOIN canonical_store.knowledge_node_scopes scope USING(knode_id)
            WHERE v.knode_revision_id=NEW.node_revision_id AND n.current_revision_id=v.knode_revision_id
                AND n.knode_id=r.result_node_id AND n.kind=decision->>'_candidate_kind'
                AND scope.identity_scope=decision->>'_identity_scope'
                AND scope.source_data_id IS NOT DISTINCT FROM decision->>'_source_data_id'
                AND (v.origin_record_id=r.record_id
                    OR EXISTS(SELECT 1 FROM jsonb_array_elements(context.input_snapshot->'existing_nodes') item
                        WHERE item->>'knode_revision_id'=v.knode_revision_id::text)
                    OR EXISTS(SELECT 1 FROM compiler_runtime.k_compilation_records created
                        WHERE created.record_id=v.origin_record_id AND created.execution_id=r.execution_id
                            AND created.disposition='accepted_new')))
        OR NOT EXISTS(SELECT 1 FROM compiler_runtime.k_model_calls generator
            JOIN compiler_runtime.k_model_calls validator ON validator.execution_id=generator.execution_id
            WHERE generator.execution_id=r.execution_id AND generator.phase='generator' AND validator.phase='validator'
                AND generator.status='succeeded' AND validator.status='succeeded'
                AND generator.profile_id=context.generator_profile_id AND validator.profile_id=context.validator_profile_id
                AND length(btrim(generator.provider_ref))>0 AND length(btrim(validator.provider_ref))>0
                AND generator.provider_ref<>validator.provider_ref
                AND generator.receipt->'actual_delivery'='true'::jsonb AND validator.receipt->'actual_delivery'='true'::jsonb
                AND generator.receipt->'delivered_data_view_ids'=delivered_views
                AND validator.receipt->'delivered_data_view_ids'=delivered_views)
        OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(e.generator_receipt->'view_reviews') review
            WHERE review->>'view_id'=NEW.view_id::text AND review->>'disposition'='selected'
                AND review->'candidate_keys' ? (decision->>'candidate_key'))
        OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(e.validator_receipt->'d2k_view_reviews') review
            WHERE review->>'view_id'=NEW.view_id::text AND review->>'verdict'='confirmed')
    THEN RAISE EXCEPTION 'D2K support requires its complete validated citation set, approved result scope and both independent actual deliveries'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER data_grounding_commit_guard AFTER INSERT ON canonical_store.knowledge_data_groundings
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION canonical_store.check_data_grounding_commit();

DO $$ DECLARE relation text; BEGIN
    FOREACH relation IN ARRAY ARRAY['compiler_runtime.d2k_preparations','compiler_runtime.d2k_source_views',
        'compiler_runtime.d2k_authorizations','compiler_runtime.d2k_execution_authorizations',
        'compiler_runtime.d2k_decisions','canonical_store.knowledge_data_groundings'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON %s FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
        EXECUTE format('CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON %s FOR EACH STATEMENT EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
    END LOOP;
END; $$;
GRANT SELECT,INSERT ON compiler_runtime.d2k_preparations,compiler_runtime.d2k_source_views,
    compiler_runtime.d2k_authorizations,compiler_runtime.d2k_execution_authorizations,
    compiler_runtime.d2k_decisions,canonical_store.knowledge_data_groundings TO palimpsest;


-- Shared guard integration: unchanged legacy branches, explicit D2K additions only.

CREATE OR REPLACE FUNCTION compiler_runtime.guard_k_context() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='INSERT' THEN
        IF NOT EXISTS (SELECT 1 FROM compiler_runtime.operation_executions
            WHERE execution_id=NEW.execution_id AND operation IN ('i2k','n2e','k2k','d2k') AND state='prepared'
                AND (operation<>'d2k' OR compiler_runtime.is_d2k_execution(execution_id)))
        THEN RAISE EXCEPTION 'K context requires a prepared I2K/N2E execution'; END IF;
    ELSIF to_jsonb(NEW)-'validation_context_sha' IS DISTINCT FROM to_jsonb(OLD)-'validation_context_sha'
        OR OLD.validation_context_sha IS NOT NULL THEN
        RAISE EXCEPTION 'K execution input is frozen';
    END IF;
    RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION canonical_store.guard_k_revision_insert() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE current_id uuid; previous_payload jsonb; previous_qualifiers jsonb; previous_fp text; same_payload boolean;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.origin_record_id
        AND disposition IN ('pending','needs_human')
        AND ((TG_TABLE_NAME='knowledge_node_revisions' AND record_type IN ('i2k','k2k','d2k'))
            OR (TG_TABLE_NAME='knowledge_edge_revisions' AND record_type='n2e')))
    THEN RAISE EXCEPTION 'K revision requires its unresolved operation Record'; END IF;
    IF TG_TABLE_NAME='knowledge_node_revisions' THEN
        IF NEW.supersedes_revision_id IS NOT NULL AND EXISTS(SELECT 1 FROM compiler_runtime.k_compilation_records
            WHERE record_id=NEW.origin_record_id AND record_type='d2k')
        THEN RAISE EXCEPTION 'D2K source grants permit creation or same-meaning support, not material revision'; END IF;
        IF EXISTS(SELECT 1 FROM compiler_runtime.k_compilation_records
            WHERE record_id=NEW.origin_record_id AND record_type='k2k') AND NOT EXISTS(
                SELECT 1 FROM canonical_store.knowledge_nodes WHERE knode_id=NEW.knode_id AND kind='proposition')
        THEN RAISE EXCEPTION 'K2K cannot synthesize an Observation'; END IF;
    END IF;
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
        IF r.record_type NOT IN ('i2k','k2k','d2k') OR r.result_node_revision_id IS DISTINCT FROM revision_id
            OR r.result_node_id IS DISTINCT FROM object_id
            OR (r.record_type='i2k' AND NOT EXISTS (
                SELECT 1 FROM canonical_store.knowledge_node_groundings
                WHERE node_revision_id=revision_id AND origin_record_id=r.record_id))
            OR (r.record_type='d2k' AND NOT EXISTS (
                SELECT 1 FROM canonical_store.knowledge_data_groundings
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
        IF r.record_type IN ('i2k','k2k','d2k') AND NOT EXISTS (SELECT 1 FROM canonical_store.knowledge_node_revisions
            WHERE knode_revision_id=r.result_node_revision_id AND origin_record_id=r.record_id)
        THEN RAISE EXCEPTION 'Accepted I2K Record must originate its result revision'; END IF;
        IF r.record_type='n2e' AND NOT EXISTS (SELECT 1 FROM canonical_store.knowledge_edge_revisions
            WHERE kedge_revision_id=r.result_edge_revision_id AND origin_record_id=r.record_id)
        THEN RAISE EXCEPTION 'Accepted N2E Record must originate its result revision'; END IF;
    END IF;
    IF r.record_type='d2k' AND r.result_node_revision_id IS NOT NULL THEN
        IF NOT EXISTS(SELECT 1 FROM canonical_store.knowledge_data_groundings
            WHERE origin_record_id=r.record_id AND node_revision_id=r.result_node_revision_id)
            OR EXISTS(SELECT 1 FROM canonical_store.knowledge_node_groundings WHERE origin_record_id=r.record_id)
            OR EXISTS(SELECT 1 FROM canonical_store.knowledge_derivations WHERE record_id=r.record_id)
        THEN RAISE EXCEPTION 'D2K results need their own direct Data support, never fabricated I or inference origin'; END IF;
    END IF;
    RETURN NULL;
END; $$;

CREATE OR REPLACE FUNCTION canonical_store.guard_knowledge_scope() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE node_kind text; execution_data text; execution uuid; multi boolean; candidate jsonb;
BEGIN
    IF EXISTS(SELECT 1 FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.origin_record_id AND record_type='d2k') THEN
        SELECT c.body,e.data_id INTO candidate,execution_data FROM compiler_runtime.k_compilation_records r
            JOIN compiler_runtime.k_temporary_candidates c USING(record_id)
            JOIN compiler_runtime.operation_executions e USING(execution_id)
            JOIN compiler_runtime.d2k_decisions d USING(record_id)
            WHERE r.record_id=NEW.origin_record_id AND r.disposition IN ('pending','needs_human')
                AND e.state='proposed' AND compiler_runtime.is_d2k_execution(e.execution_id)
                AND d.validation->>'verdict' IN ('accepted','reused')
                AND d.validation->'source_explicit'='true'::jsonb AND d.validation->'no_novel_inference'='true'::jsonb
                AND d.validation->'source_identity_preserved'='true'::jsonb AND d.validation->'scope_correct'='true'::jsonb
                AND d.validation->'importance_justified'='true'::jsonb;
        SELECT kind INTO STRICT node_kind FROM canonical_store.knowledge_nodes WHERE knode_id=NEW.knode_id;
        IF candidate IS NULL OR candidate->>'kind' IS DISTINCT FROM node_kind
            OR candidate->>'identity_scope' IS DISTINCT FROM NEW.identity_scope
            OR candidate->>'source_data_id' IS DISTINCT FROM NEW.source_data_id
            OR (node_kind='observation' AND NEW.identity_scope<>'source')
            OR (NEW.identity_scope='source' AND NEW.source_data_id IS DISTINCT FROM execution_data)
        THEN RAISE EXCEPTION 'D2K scope must match its validated source-only candidate and reported observation owner'; END IF;
        RETURN NEW;
    END IF;
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
    IF EXISTS(SELECT 1 FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.origin_record_id AND record_type='d2k') THEN
        IF NOT EXISTS(SELECT 1 FROM compiler_runtime.k_compilation_records r
            JOIN canonical_store.knowledge_data_groundings g ON g.origin_record_id=r.record_id
            WHERE r.record_id=NEW.origin_record_id AND r.result_node_id=NEW.knode_id
                AND r.result_node_revision_id=g.node_revision_id
                AND r.disposition IN ('accepted_new','accepted_revision','reused','no_material_delta'))
        THEN RAISE EXCEPTION 'D2K scope and exact accepted direct Data support must commit together'; END IF;
        RETURN NULL;
    END IF;
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

CREATE OR REPLACE FUNCTION canonical_store.derivation_source_data(id uuid) RETURNS SETOF text LANGUAGE sql STABLE AS $$
    WITH RECURSIVE ancestry(revision_id) AS (
        SELECT id UNION
        SELECT p.premise_node_revision_id FROM ancestry a
        JOIN canonical_store.knowledge_derivations d ON d.result_node_revision_id=a.revision_id
        JOIN canonical_store.knowledge_derivation_premises p USING(record_id))
    SELECT DISTINCT i.data_id FROM ancestry a
        JOIN canonical_store.knowledge_node_groundings g ON g.node_revision_id=a.revision_id
        JOIN canonical_store.information i USING(information_id)
    UNION SELECT g.data_id FROM ancestry a
        JOIN canonical_store.knowledge_data_groundings g ON g.node_revision_id=a.revision_id
$$;

CREATE OR REPLACE FUNCTION compiler_runtime.execution_version_source_data(id uuid) RETURNS SETOF text LANGUAGE sql STABLE AS $$
    SELECT DISTINCT i.data_id FROM compiler_runtime.k_input_information x
        JOIN canonical_store.information i USING(information_id) WHERE x.execution_id=id
    UNION SELECT source.data_id FROM compiler_runtime.k_input_node_revisions x
        CROSS JOIN LATERAL canonical_store.derivation_source_data(x.node_revision_id) source(data_id)
        WHERE x.execution_id=id
    UNION SELECT e.data_id FROM compiler_runtime.operation_executions e
        WHERE e.execution_id=id AND compiler_runtime.is_d2k_execution(e.execution_id)
$$;

CREATE OR REPLACE FUNCTION canonical_store.k_revision_supported_by_version_data(
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
    FOR compilation IN SELECT r.record_id,r.record_type FROM compiler_runtime.k_compilation_records r
        WHERE r.result_node_revision_id=revision AND r.record_type IN ('i2k','d2k')
            AND r.disposition IN ('accepted_new','accepted_revision','reused','no_material_delta') LOOP
        IF compilation.record_type='d2k' THEN
            SELECT ARRAY(SELECT DISTINCT g.data_id FROM canonical_store.knowledge_data_groundings g
                WHERE g.node_revision_id=revision AND g.origin_record_id=compilation.record_id) INTO used_data;
        ELSE
        SELECT ARRAY(SELECT DISTINCT i.data_id FROM compiler_runtime.k_information_review_records l
            JOIN canonical_store.information i USING(information_id)
            WHERE l.record_id=compilation.record_id) INTO used_data;
        IF cardinality(used_data)=0 THEN
            SELECT ARRAY(SELECT DISTINCT i.data_id FROM canonical_store.knowledge_node_groundings g
                JOIN canonical_store.information i USING(information_id)
                WHERE g.node_revision_id=revision AND g.origin_record_id=compilation.record_id) INTO used_data;
        END IF;
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

CREATE OR REPLACE FUNCTION compiler_runtime.guard_execution_data_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM compiler_runtime.operation_executions e
        JOIN compiler_runtime.k_execution_contexts c USING(execution_id)
        JOIN canonical_store.data_versions v ON v.version_id=NEW.version_id
        WHERE e.execution_id=NEW.execution_id AND e.operation IN ('i2k','n2e','k2k','d2k') AND e.state='prepared'
            AND EXISTS(SELECT 1 FROM jsonb_array_elements(COALESCE(c.input_snapshot->'data_versions','[]'::jsonb)) declared
                WHERE compiler_runtime.data_version_snapshot_matches(declared,v.version_id))
            AND v.data_id IN (SELECT compiler_runtime.execution_version_source_data(e.execution_id)))
    THEN RAISE EXCEPTION 'Execution version must bind a frozen exact version of actual input Data'; END IF;
    RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION compiler_runtime.check_execution_data_versions() RETURNS trigger LANGUAGE plpgsql AS $$
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
    IF operation IN ('i2k','d2k') THEN
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

CREATE TRIGGER a_knowledge_state BEFORE INSERT ON canonical_store.knowledge_data_groundings
    FOR EACH ROW EXECUTE FUNCTION compiler_runtime.advance_knowledge_state();
