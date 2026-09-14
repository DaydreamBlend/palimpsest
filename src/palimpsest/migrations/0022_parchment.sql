-- Exact immutable W2P composition. No model call, K mutation or publication Book.
CREATE TABLE canonical_store.parchments (
    parchment_id uuid PRIMARY KEY CHECK (uuid_extract_version(parchment_id)=7),
    request_id uuid NOT NULL UNIQUE CHECK (uuid_extract_version(request_id)=7),
    request_fingerprint text NOT NULL CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
    title text NOT NULL CHECK (length(btrim(title))>0),
    actor text NOT NULL CHECK (length(btrim(actor))>0),
    snapshot jsonb NOT NULL CHECK (jsonb_typeof(snapshot)='object'),
    snapshot_bytes bytea NOT NULL,
    snapshot_sha256 text NOT NULL CHECK (snapshot_sha256 ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL,
    CHECK (convert_from(snapshot_bytes,'UTF8')::jsonb = snapshot-'snapshot_sha256'),
    CHECK (encode(sha256(snapshot_bytes),'hex')=snapshot_sha256)
);
CREATE TABLE canonical_store.parchment_wisdoms (
    parchment_id uuid NOT NULL REFERENCES canonical_store.parchments,
    ordinal integer NOT NULL CHECK (ordinal>=0),
    wisdom_id uuid NOT NULL REFERENCES canonical_store.wisdoms,
    wisdom_snapshot_sha256 text NOT NULL CHECK (wisdom_snapshot_sha256 ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY(parchment_id,ordinal), UNIQUE(parchment_id,wisdom_id)
);

CREATE FUNCTION canonical_store.guard_parchment() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE identifier text; w canonical_store.wisdoms; section jsonb; expected_sections jsonb:='[]'::jsonb;
        expected_citations jsonb:='[]'::jsonb; input_ids jsonb; seen jsonb:='[]'::jsonb; position integer:=0;
BEGIN
    input_ids:=NEW.snapshot->'input_wisdom_ids';
    IF NEW.snapshot->>'schema_version' IS DISTINCT FROM 'parchment-v1'
        OR NEW.snapshot->>'parchment_id' IS DISTINCT FROM NEW.parchment_id::text
        OR NEW.snapshot->>'title' IS DISTINCT FROM NEW.title
        OR NEW.snapshot->>'snapshot_sha256' IS DISTINCT FROM NEW.snapshot_sha256
        OR (NEW.snapshot->>'created_at')::timestamptz IS DISTINCT FROM NEW.created_at
        OR NEW.snapshot->'direct_k_revision_ids' IS DISTINCT FROM '[]'::jsonb
        OR NEW.snapshot->'direct_information_ids' IS DISTINCT FROM '[]'::jsonb
        OR NEW.snapshot->'supersedes_parchment_id' IS DISTINCT FROM 'null'::jsonb
        OR NEW.snapshot->'provenance'->>'operation' IS DISTINCT FROM 'w2p'
        OR NEW.snapshot->'provenance'->>'actor' IS DISTINCT FROM NEW.actor
        OR NEW.snapshot->'provenance'->'profile'->>'schema_version' IS DISTINCT FROM 'w2p-exact-wisdom-v1'
        OR jsonb_typeof(NEW.snapshot->'provenance'->'profile'->'implementation_sha256') IS DISTINCT FROM 'object'
        OR jsonb_typeof(input_ids) IS DISTINCT FROM 'array' OR jsonb_array_length(input_ids)=0
        OR NEW.snapshot-ARRAY['schema_version','parchment_id','title','body','input_wisdom_ids',
            'direct_k_revision_ids','direct_information_ids','citations','provenance','supersedes_parchment_id',
            'created_at','snapshot_sha256'] <> '{}'::jsonb
    THEN RAISE EXCEPTION 'P requires an exact W2P snapshot'; END IF;
    FOR identifier IN SELECT jsonb_array_elements_text(input_ids) LOOP
        IF seen @> jsonb_build_array(identifier) THEN RAISE EXCEPTION 'Duplicate W in P'; END IF;
        seen:=seen || jsonb_build_array(identifier);
        SELECT * INTO STRICT w FROM canonical_store.wisdoms WHERE wisdom_id=identifier::uuid;
        section:=jsonb_build_object('wisdom_id',identifier,'wisdom_snapshot_sha256',w.snapshot_sha256,
            'wisdom_kind',w.snapshot->'wisdom_kind','query',w.snapshot->'query',
            'context_snapshot',w.snapshot->'context_snapshot','evidence_mode',w.snapshot->'evidence_mode',
            'epistemic_basis',w.snapshot->'epistemic_basis','answer_or_payload',w.snapshot->'answer_or_payload',
            'uncertainty',w.snapshot->'uncertainty');
        expected_sections:=expected_sections || jsonb_build_array(section);
        expected_citations:=expected_citations || jsonb_build_array(jsonb_build_object(
            'section_index',position,'wisdom_id',identifier,'wisdom_snapshot_sha256',w.snapshot_sha256,
            'claims',w.snapshot->'citations'));
        position:=position+1;
    END LOOP;
    IF NEW.snapshot->'body' IS DISTINCT FROM jsonb_build_object('sections',expected_sections)
        OR NEW.snapshot->'citations' IS DISTINCT FROM expected_citations
    THEN RAISE EXCEPTION 'W2P must preserve exact W content, context and citations'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER parchment_guard BEFORE INSERT ON canonical_store.parchments
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_parchment();

CREATE FUNCTION canonical_store.guard_parchment_wisdom() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p canonical_store.parchments; w canonical_store.wisdoms;
BEGIN
    SELECT * INTO STRICT p FROM canonical_store.parchments WHERE parchment_id=NEW.parchment_id;
    SELECT * INTO STRICT w FROM canonical_store.wisdoms WHERE wisdom_id=NEW.wisdom_id;
    IF p.snapshot->'input_wisdom_ids'->>NEW.ordinal IS DISTINCT FROM NEW.wisdom_id::text
        OR NEW.wisdom_snapshot_sha256 IS DISTINCT FROM w.snapshot_sha256
    THEN RAISE EXCEPTION 'P typed input must bind the exact ordered W'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER parchment_wisdom_guard BEFORE INSERT ON canonical_store.parchment_wisdoms
    FOR EACH ROW EXECUTE FUNCTION canonical_store.guard_parchment_wisdom();
CREATE FUNCTION canonical_store.parchment_inputs_complete() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (SELECT count(*) FROM canonical_store.parchment_wisdoms WHERE parchment_id=NEW.parchment_id)
        <> jsonb_array_length(NEW.snapshot->'input_wisdom_ids')
    THEN RAISE EXCEPTION 'P and all typed W inputs must commit atomically'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER parchment_inputs_atomic AFTER INSERT ON canonical_store.parchments
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION canonical_store.parchment_inputs_complete();
DO $$ DECLARE relation text; BEGIN
    FOREACH relation IN ARRAY ARRAY['canonical_store.parchments','canonical_store.parchment_wisdoms'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON %s FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
        EXECUTE format('CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON %s FOR EACH STATEMENT EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
    END LOOP;
END; $$;
GRANT SELECT,INSERT ON canonical_store.parchments,canonical_store.parchment_wisdoms TO palimpsest;
