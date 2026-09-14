-- Standalone catalog: explicitly provision in a new PostgreSQL 18 database.
-- Never run this as an application migration against an existing source store.
CREATE SCHEMA realm_store;
CREATE FUNCTION realm_store.schema_version() RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT 'realm-catalog-v1'::text
$$;
CREATE TABLE realm_store.requests (
    request_id uuid PRIMARY KEY CHECK (uuid_extract_version(request_id) IS NOT DISTINCT FROM 7),
    request_fingerprint text NOT NULL CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
    operation text NOT NULL CHECK (operation IN ('create','revise')),
    request_json text NOT NULL CHECK (jsonb_typeof(request_json::jsonb)='object'),
    realm_id uuid NOT NULL CHECK (uuid_extract_version(realm_id) IS NOT DISTINCT FROM 7),
    expected_revision_id uuid CHECK (expected_revision_id IS NULL OR uuid_extract_version(expected_revision_id) IS NOT DISTINCT FROM 7),
    result_revision_id uuid NOT NULL CHECK (uuid_extract_version(result_revision_id) IS NOT DISTINCT FROM 7),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((operation='create')=(expected_revision_id IS NULL)),
    CHECK (request_fingerprint=encode(sha256(convert_to(request_json,'UTF8')),'hex'))
);
CREATE TABLE realm_store.realms (
    realm_id uuid PRIMARY KEY CHECK (uuid_extract_version(realm_id) IS NOT DISTINCT FROM 7),
    current_revision_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE realm_store.realm_revisions (
    revision_id uuid PRIMARY KEY CHECK (uuid_extract_version(revision_id) IS NOT DISTINCT FROM 7),
    realm_id uuid NOT NULL REFERENCES realm_store.realms,
    parent_revision_id uuid,
    revision_no bigint NOT NULL CHECK (revision_no>0),
    name text NOT NULL CHECK (length(btrim(name))>0),
    description text NOT NULL,
    actor text NOT NULL CHECK (length(btrim(actor))>0),
    reason text NOT NULL CHECK (length(btrim(reason))>0),
    request_id uuid NOT NULL UNIQUE REFERENCES realm_store.requests,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(revision_id,realm_id), UNIQUE(realm_id,revision_no),
    FOREIGN KEY(parent_revision_id,realm_id) REFERENCES realm_store.realm_revisions(revision_id,realm_id),
    CHECK (parent_revision_id IS DISTINCT FROM revision_id),
    CHECK ((parent_revision_id IS NULL)=(revision_no=1))
);
ALTER TABLE realm_store.realms ADD FOREIGN KEY(current_revision_id,realm_id)
    REFERENCES realm_store.realm_revisions(revision_id,realm_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE realm_store.requests ADD FOREIGN KEY(realm_id) REFERENCES realm_store.realms DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE realm_store.requests ADD FOREIGN KEY(result_revision_id,realm_id)
    REFERENCES realm_store.realm_revisions(revision_id,realm_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE realm_store.requests ADD FOREIGN KEY(expected_revision_id,realm_id)
    REFERENCES realm_store.realm_revisions(revision_id,realm_id) DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE realm_store.realm_members (
    revision_id uuid NOT NULL REFERENCES realm_store.realm_revisions,
    store_id uuid NOT NULL CHECK (uuid_extract_version(store_id) IS NOT DISTINCT FROM 7),
    member_kind text NOT NULL CHECK (member_kind IN ('data','data_series')),
    member_id text NOT NULL,
    PRIMARY KEY(revision_id,store_id,member_kind,member_id),
    CHECK ((member_kind='data' AND member_id ~ '^[0-9a-f]{64}$') OR
        (member_kind='data_series' AND member_id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'))
);
CREATE INDEX realm_member_lookup ON realm_store.realm_members(store_id,member_kind,member_id);

CREATE FUNCTION realm_store.reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Realm requests, revisions and membership snapshots are immutable'; END; $$;
CREATE FUNCTION realm_store.guard_request() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE payload jsonb;
BEGIN
    payload:=NEW.request_json::jsonb;
    IF payload->>'schema_version' IS DISTINCT FROM 'realm-catalog-v1'
        OR payload->>'operation' IS DISTINCT FROM NEW.operation
        OR payload-ARRAY['schema_version','operation','realm_id','expected_revision_id','name','description','members','actor','reason']<>'{}'::jsonb
        OR (NEW.operation='create' AND (payload->'realm_id' IS DISTINCT FROM 'null'::jsonb
            OR payload->'expected_revision_id' IS DISTINCT FROM 'null'::jsonb OR payload->'members' IS DISTINCT FROM '[]'::jsonb))
        OR (NEW.operation='revise' AND (payload->>'realm_id' IS DISTINCT FROM NEW.realm_id::text
            OR payload->>'expected_revision_id' IS DISTINCT FROM NEW.expected_revision_id::text))
        OR jsonb_typeof(payload->'name') IS DISTINCT FROM 'string' OR COALESCE(length(btrim(payload->>'name')),0)=0
        OR jsonb_typeof(payload->'description') IS DISTINCT FROM 'string'
        OR jsonb_typeof(payload->'actor') IS DISTINCT FROM 'string' OR COALESCE(length(btrim(payload->>'actor')),0)=0
        OR jsonb_typeof(payload->'reason') IS DISTINCT FROM 'string' OR COALESCE(length(btrim(payload->>'reason')),0)=0
        OR jsonb_typeof(payload->'members') IS DISTINCT FROM 'array'
    THEN RAISE EXCEPTION 'Realm request must preserve its exact action, expected head and complete metadata'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER realm_request_guard BEFORE INSERT ON realm_store.requests
    FOR EACH ROW EXECUTE FUNCTION realm_store.guard_request();

CREATE FUNCTION realm_store.guard_realm() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='INSERT' THEN
        IF NOT EXISTS(SELECT 1 FROM realm_store.requests WHERE realm_id=NEW.realm_id
            AND result_revision_id=NEW.current_revision_id AND operation='create')
        THEN RAISE EXCEPTION 'Realm creation needs its immutable creation request'; END IF;
    ELSIF to_jsonb(NEW)-'current_revision_id' IS DISTINCT FROM to_jsonb(OLD)-'current_revision_id'
        OR (NEW.current_revision_id IS DISTINCT FROM OLD.current_revision_id AND NOT EXISTS(
            SELECT 1 FROM realm_store.realm_revisions WHERE realm_id=NEW.realm_id
                AND revision_id=NEW.current_revision_id AND parent_revision_id=OLD.current_revision_id))
    THEN RAISE EXCEPTION 'Realm head changes require the exact current parent revision'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER realm_head_guard BEFORE INSERT OR UPDATE ON realm_store.realms
    FOR EACH ROW EXECUTE FUNCTION realm_store.guard_realm();

CREATE FUNCTION realm_store.guard_revision() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE request_row realm_store.requests; payload jsonb; current_id uuid; previous_no bigint;
BEGIN
    SELECT * INTO STRICT request_row FROM realm_store.requests WHERE request_id=NEW.request_id;
    payload:=request_row.request_json::jsonb;
    SELECT current_revision_id INTO STRICT current_id FROM realm_store.realms WHERE realm_id=NEW.realm_id FOR UPDATE;
    IF request_row.realm_id IS DISTINCT FROM NEW.realm_id OR request_row.result_revision_id IS DISTINCT FROM NEW.revision_id
        OR request_row.expected_revision_id IS DISTINCT FROM NEW.parent_revision_id
        OR NEW.name IS DISTINCT FROM payload->>'name' OR NEW.description IS DISTINCT FROM payload->>'description'
        OR NEW.actor IS DISTINCT FROM payload->>'actor' OR NEW.reason IS DISTINCT FROM payload->>'reason'
    THEN RAISE EXCEPTION 'Realm revision must match its exact immutable request'; END IF;
    IF request_row.operation='create' THEN
        IF NEW.parent_revision_id IS NOT NULL OR NEW.revision_no<>1 OR current_id IS DISTINCT FROM NEW.revision_id
        THEN RAISE EXCEPTION 'A Realm has exactly one initial revision'; END IF;
    ELSE
        SELECT revision_no INTO previous_no FROM realm_store.realm_revisions
            WHERE realm_id=NEW.realm_id AND revision_id=NEW.parent_revision_id;
        IF current_id IS DISTINCT FROM NEW.parent_revision_id OR NEW.revision_no IS DISTINCT FROM previous_no+1
        THEN RAISE EXCEPTION 'Realm comparison head changed before revision publication'; END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER realm_revision_guard BEFORE INSERT ON realm_store.realm_revisions
    FOR EACH ROW EXECUTE FUNCTION realm_store.guard_revision();

CREATE FUNCTION realm_store.guard_member() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM realm_store.realm_revisions revision
        JOIN realm_store.requests request USING(request_id)
        CROSS JOIN LATERAL jsonb_array_elements(request.request_json::jsonb->'members') member
        WHERE revision.revision_id=NEW.revision_id AND member=jsonb_build_object(
            'store_id',NEW.store_id::text,'member_kind',NEW.member_kind,'member_id',NEW.member_id))
    THEN RAISE EXCEPTION 'Realm membership must be explicitly declared by its immutable revision request'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER realm_member_guard BEFORE INSERT ON realm_store.realm_members
    FOR EACH ROW EXECUTE FUNCTION realm_store.guard_member();

CREATE FUNCTION realm_store.check_publication() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE request_row realm_store.requests; revision_row realm_store.realm_revisions; members jsonb;
BEGIN
    IF TG_TABLE_NAME='requests' THEN
        SELECT * INTO STRICT request_row FROM realm_store.requests WHERE request_id=NEW.request_id;
    ELSE
        SELECT request.* INTO STRICT request_row FROM realm_store.requests request
            JOIN realm_store.realm_revisions revision USING(request_id) WHERE revision.revision_id=NEW.revision_id;
    END IF;
    SELECT * INTO STRICT revision_row FROM realm_store.realm_revisions WHERE revision_id=request_row.result_revision_id;
    SELECT COALESCE(jsonb_agg(jsonb_build_object('store_id',store_id::text,'member_kind',member_kind,'member_id',member_id)
        ORDER BY store_id,member_kind,member_id),'[]'::jsonb) INTO members
        FROM realm_store.realm_members WHERE revision_id=revision_row.revision_id;
    IF revision_row.request_id IS DISTINCT FROM request_row.request_id
        OR members IS DISTINCT FROM request_row.request_json::jsonb->'members'
        OR NOT EXISTS(WITH RECURSIVE lineage(revision_id,parent_revision_id) AS (
            SELECT v.revision_id,v.parent_revision_id FROM realm_store.realms r
                JOIN realm_store.realm_revisions v ON v.revision_id=r.current_revision_id WHERE r.realm_id=request_row.realm_id
            UNION SELECT v.revision_id,v.parent_revision_id FROM lineage prior
                JOIN realm_store.realm_revisions v ON v.revision_id=prior.parent_revision_id)
            SELECT 1 FROM lineage WHERE revision_id=request_row.result_revision_id)
    THEN RAISE EXCEPTION 'Realm request, complete membership snapshot and published head must commit together'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER realm_request_publication AFTER INSERT ON realm_store.requests
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION realm_store.check_publication();
CREATE CONSTRAINT TRIGGER realm_revision_publication AFTER INSERT ON realm_store.realm_revisions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION realm_store.check_publication();
-- Request/revision triggers check the complete set once per publication. The
-- member guard and primary key prevent later additions to an immutable snapshot.

DO $$ DECLARE relation text; BEGIN
    FOREACH relation IN ARRAY ARRAY['realm_store.requests','realm_store.realm_revisions','realm_store.realm_members'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON %s FOR EACH ROW EXECUTE FUNCTION realm_store.reject_mutation()',relation);
    END LOOP;
    FOREACH relation IN ARRAY ARRAY['realm_store.requests','realm_store.realms','realm_store.realm_revisions','realm_store.realm_members'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON %s FOR EACH STATEMENT EXECUTE FUNCTION realm_store.reject_mutation()',relation);
    END LOOP;
END; $$;
CREATE TRIGGER realm_no_delete BEFORE DELETE ON realm_store.realms
    FOR EACH ROW EXECUTE FUNCTION realm_store.reject_mutation();
GRANT USAGE ON SCHEMA realm_store TO palimpsest;
GRANT SELECT,INSERT ON realm_store.requests,realm_store.realms,realm_store.realm_revisions,realm_store.realm_members TO palimpsest;
GRANT UPDATE(current_revision_id) ON realm_store.realms TO palimpsest;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA realm_store TO palimpsest;
