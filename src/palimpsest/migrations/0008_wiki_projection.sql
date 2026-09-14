-- Noncanonical Wiki archive/read projection. No canonical D/I/K/P/W effects.
-- Python owns canonical JSON digests; PostgreSQL verifies exact raw bytes,
-- source coordinates, typed historical links and the atomic current selection.
CREATE SCHEMA wiki_projection;

CREATE TABLE wiki_projection.wikis (
    wiki_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(wiki_id) IS NOT DISTINCT FROM 7),
    current_import_id uuid,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE wiki_projection.blobs (
    sha256 text PRIMARY KEY CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    content bytea NOT NULL,
    CHECK (encode(pg_catalog.sha256(content),'hex')=sha256)
);
CREATE TABLE wiki_projection.pages (
    wiki_id uuid NOT NULL REFERENCES wiki_projection.wikis,
    page_id uuid NOT NULL CHECK (uuid_extract_version(page_id) IS NOT DISTINCT FROM 7),
    kind text NOT NULL CHECK (kind IN ('paper','topic')),
    data_id text REFERENCES canonical_store.data,
    topic_key text CHECK (topic_key ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND length(topic_key)<=80),
    PRIMARY KEY (wiki_id,page_id), UNIQUE (wiki_id,data_id), UNIQUE (wiki_id,topic_key),
    CHECK ((kind='paper' AND data_id IS NOT NULL AND topic_key IS NULL)
        OR (kind='topic' AND data_id IS NULL AND topic_key IS NOT NULL))
);
CREATE TABLE wiki_projection.snapshots (
    wiki_id uuid NOT NULL,
    snapshot_id uuid NOT NULL CHECK (uuid_extract_version(snapshot_id) IS NOT DISTINCT FROM 7),
    page_id uuid NOT NULL,
    previous_snapshot_id uuid,
    previous_snapshot_sha256 text CHECK (previous_snapshot_sha256 ~ '^[0-9a-f]{64}$'),
    snapshot_sha256 text NOT NULL CHECK (snapshot_sha256 ~ '^[0-9a-f]{64}$'),
    body_sha256 text NOT NULL CHECK (body_sha256 ~ '^[0-9a-f]{64}$'),
    origin_request_id uuid NOT NULL CHECK (uuid_extract_version(origin_request_id) IS NOT DISTINCT FROM 7),
    source_execution_id uuid,
    data_id text REFERENCES canonical_store.data,
    raw_sha256 text NOT NULL REFERENCES wiki_projection.blobs,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
    PRIMARY KEY (wiki_id,snapshot_id),
    UNIQUE (wiki_id,snapshot_id,page_id),
    UNIQUE (wiki_id,snapshot_id,page_id,snapshot_sha256),
    FOREIGN KEY (wiki_id,page_id) REFERENCES wiki_projection.pages,
    FOREIGN KEY (wiki_id,previous_snapshot_id,page_id,previous_snapshot_sha256)
        REFERENCES wiki_projection.snapshots(wiki_id,snapshot_id,page_id,snapshot_sha256)
        DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (source_execution_id,data_id)
        REFERENCES compiler_runtime.operation_executions(execution_id,data_id),
    CHECK ((previous_snapshot_id IS NULL)=(previous_snapshot_sha256 IS NULL)),
    CHECK (previous_snapshot_id IS DISTINCT FROM snapshot_id),
    CHECK ((source_execution_id IS NULL)=(data_id IS NULL))
);
CREATE TABLE wiki_projection.items (
    wiki_id uuid NOT NULL,
    snapshot_id uuid NOT NULL,
    item_key text NOT NULL CHECK (length(item_key)>0),
    item_text_sha256 text NOT NULL CHECK (item_text_sha256 ~ '^[0-9a-f]{64}$'),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
    PRIMARY KEY (wiki_id,snapshot_id,item_key),
    FOREIGN KEY (wiki_id,snapshot_id) REFERENCES wiki_projection.snapshots
);
CREATE TABLE wiki_projection.citations (
    wiki_id uuid NOT NULL,
    snapshot_id uuid NOT NULL,
    item_key text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal>=0),
    information_id uuid NOT NULL,
    data_id text NOT NULL,
    source_execution_id uuid NOT NULL,
    char_start integer NOT NULL CHECK (char_start>=0),
    char_end integer NOT NULL CHECK (char_end>=char_start),
    quote text NOT NULL,
    media_sha256 text CHECK (media_sha256 ~ '^[0-9a-f]{64}$'),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
    PRIMARY KEY (wiki_id,snapshot_id,item_key,ordinal),
    FOREIGN KEY (wiki_id,snapshot_id,item_key) REFERENCES wiki_projection.items,
    FOREIGN KEY (information_id,data_id) REFERENCES canonical_store.information(information_id,data_id),
    FOREIGN KEY (source_execution_id,data_id)
        REFERENCES compiler_runtime.operation_executions(execution_id,data_id),
    CHECK (length(quote)=char_end-char_start),
    CHECK (char_end>char_start OR media_sha256 IS NOT NULL)
);
CREATE TABLE wiki_projection.catalogs (
    wiki_id uuid NOT NULL REFERENCES wiki_projection.wikis,
    catalog_sha256 text NOT NULL CHECK (catalog_sha256 ~ '^[0-9a-f]{64}$'),
    version bigint NOT NULL CHECK (version>=0),
    raw_sha256 text NOT NULL REFERENCES wiki_projection.blobs,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
    PRIMARY KEY (wiki_id,catalog_sha256), UNIQUE (wiki_id,version)
);
CREATE TABLE wiki_projection.members (
    wiki_id uuid NOT NULL,
    catalog_sha256 text NOT NULL,
    page_id uuid NOT NULL,
    snapshot_id uuid NOT NULL,
    PRIMARY KEY (wiki_id,catalog_sha256,page_id),
    FOREIGN KEY (wiki_id,catalog_sha256) REFERENCES wiki_projection.catalogs,
    FOREIGN KEY (wiki_id,snapshot_id,page_id)
        REFERENCES wiki_projection.snapshots(wiki_id,snapshot_id,page_id)
);
CREATE TABLE wiki_projection.imports (
    request_id uuid PRIMARY KEY CHECK (uuid_extract_version(request_id) IS NOT DISTINCT FROM 7),
    wiki_id uuid NOT NULL REFERENCES wiki_projection.wikis,
    request_fingerprint text NOT NULL CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
    expected_head uuid,
    catalog_sha256 text NOT NULL,
    manifest_sha256 text NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    manifest jsonb NOT NULL CHECK (jsonb_typeof(manifest)='object'),
    knowledge_state_version bigint NOT NULL CHECK (knowledge_state_version>=0),
    graph_sha256 text NOT NULL CHECK (graph_sha256 ~ '^[0-9a-f]{64}$'),
    graph_payload jsonb NOT NULL CHECK (jsonb_typeof(graph_payload)='object'),
    review_annotations jsonb NOT NULL CHECK (jsonb_typeof(review_annotations)='array'),
    result jsonb NOT NULL CHECK (jsonb_typeof(result)='object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (wiki_id,request_id),
    FOREIGN KEY (wiki_id,catalog_sha256) REFERENCES wiki_projection.catalogs,
    FOREIGN KEY (wiki_id,expected_head) REFERENCES wiki_projection.imports(wiki_id,request_id),
    CHECK (expected_head IS DISTINCT FROM request_id)
);
ALTER TABLE wiki_projection.wikis ADD FOREIGN KEY (wiki_id,current_import_id)
    REFERENCES wiki_projection.imports(wiki_id,request_id) DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE wiki_projection.files (
    request_id uuid NOT NULL REFERENCES wiki_projection.imports,
    path text NOT NULL CHECK (length(path)>0 AND path !~ '(^/|(^|/)\.{1,2}(/|$)|//|/$|:)' AND strpos(path,chr(92))=0),
    raw_sha256 text NOT NULL REFERENCES wiki_projection.blobs,
    PRIMARY KEY (request_id,path)
);
CREATE TABLE wiki_projection.knowledge_links (
    link_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(link_id) IS NOT DISTINCT FROM 7),
    request_id uuid NOT NULL,
    wiki_id uuid NOT NULL,
    snapshot_id uuid NOT NULL,
    item_key text NOT NULL,
    knode_id uuid NOT NULL,
    node_revision_id uuid NOT NULL,
    content_fingerprint text NOT NULL CHECK (content_fingerprint ~ '^[0-9a-f]{64}$'),
    link_sha256 text NOT NULL CHECK (link_sha256 ~ '^[0-9a-f]{64}$'),
    review_required boolean NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
    UNIQUE (request_id,snapshot_id,item_key,node_revision_id),
    FOREIGN KEY (wiki_id,request_id) REFERENCES wiki_projection.imports(wiki_id,request_id),
    FOREIGN KEY (wiki_id,snapshot_id,item_key) REFERENCES wiki_projection.items,
    FOREIGN KEY (node_revision_id,knode_id)
        REFERENCES canonical_store.knowledge_node_revisions(knode_revision_id,knode_id)
);
CREATE TABLE wiki_projection.knowledge_matches (
    link_id uuid NOT NULL REFERENCES wiki_projection.knowledge_links,
    ordinal integer NOT NULL CHECK (ordinal>=0),
    wiki_evidence_index integer NOT NULL CHECK (wiki_evidence_index>=0),
    grounding_id uuid NOT NULL REFERENCES canonical_store.knowledge_node_groundings,
    information_id uuid NOT NULL,
    data_id text NOT NULL,
    overlap_start integer,
    overlap_end integer,
    quote text NOT NULL,
    media_sha256 text CHECK (media_sha256 ~ '^[0-9a-f]{64}$'),
    match_kind text NOT NULL CHECK (match_kind IN ('exact_text_range','overlapping_text_range','shared_image')),
    PRIMARY KEY (link_id,ordinal),
    FOREIGN KEY (information_id,data_id) REFERENCES canonical_store.information(information_id,data_id),
    CHECK ((match_kind='shared_image' AND overlap_start IS NULL AND overlap_end IS NULL
            AND quote='' AND media_sha256 IS NOT NULL)
        OR (match_kind<>'shared_image' AND overlap_start IS NOT NULL AND overlap_end IS NOT NULL
            AND overlap_start>=0 AND overlap_end>overlap_start AND length(quote)=overlap_end-overlap_start))
);

CREATE FUNCTION wiki_projection.guard_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner wiki_projection.pages; raw jsonb;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended(NEW.wiki_id::text||':'||NEW.page_id::text, 8008));
    SELECT * INTO STRICT owner FROM wiki_projection.pages WHERE wiki_id=NEW.wiki_id AND page_id=NEW.page_id;
    SELECT convert_from(content,'UTF8')::jsonb INTO STRICT raw FROM wiki_projection.blobs WHERE sha256=NEW.raw_sha256;
    IF raw IS DISTINCT FROM NEW.payload
        OR NEW.payload->>'projection_schema' IS DISTINCT FROM 'paper-topic-wiki-projection-v1'
        OR NEW.payload->>'snapshot_id' IS DISTINCT FROM NEW.snapshot_id::text
        OR NEW.payload->>'page_id' IS DISTINCT FROM NEW.page_id::text
        OR NEW.payload->>'body_sha256' IS DISTINCT FROM NEW.body_sha256
        OR NEW.payload->>'origin_request_id' IS DISTINCT FROM NEW.origin_request_id::text
        OR NEW.payload->>'previous_snapshot_id' IS DISTINCT FROM NEW.previous_snapshot_id::text
        OR NEW.payload->>'previous_snapshot_sha256' IS DISTINCT FROM NEW.previous_snapshot_sha256
        OR NEW.payload->>'source_execution_id' IS DISTINCT FROM NEW.source_execution_id::text
        OR NEW.payload->>'data_id' IS DISTINCT FROM NEW.data_id
        OR NEW.payload->>'kind' IS DISTINCT FROM owner.kind
        OR NEW.data_id IS DISTINCT FROM owner.data_id
        OR NEW.payload->>'topic_key' IS DISTINCT FROM owner.topic_key
    THEN RAISE EXCEPTION 'Wiki snapshot raw payload and stable page identity must agree'; END IF;
    IF owner.kind='paper' AND (NEW.source_execution_id IS NULL OR NOT EXISTS (
        SELECT 1 FROM compiler_runtime.operation_executions WHERE execution_id=NEW.source_execution_id
            AND data_id=NEW.data_id AND operation='d2i' AND state='completed'))
    THEN RAISE EXCEPTION 'A paper snapshot must retain its completed canonical source'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER snapshot_guard BEFORE INSERT ON wiki_projection.snapshots
    FOR EACH ROW EXECUTE FUNCTION wiki_projection.guard_snapshot();
CREATE FUNCTION wiki_projection.check_snapshot_cycle() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (WITH RECURSIVE ancestors(id) AS (
        SELECT previous_snapshot_id FROM wiki_projection.snapshots
            WHERE wiki_id=NEW.wiki_id AND snapshot_id=NEW.snapshot_id
        UNION
        SELECT s.previous_snapshot_id FROM wiki_projection.snapshots s JOIN ancestors a ON s.snapshot_id=a.id
            WHERE s.wiki_id=NEW.wiki_id AND s.page_id=NEW.page_id)
        SELECT 1 FROM ancestors WHERE id=NEW.snapshot_id)
    THEN RAISE EXCEPTION 'Wiki snapshot history cannot contain a cycle'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER snapshot_cycle_guard AFTER INSERT ON wiki_projection.snapshots
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION wiki_projection.check_snapshot_cycle();

CREATE FUNCTION wiki_projection.guard_item() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.payload->>'item_key' IS DISTINCT FROM NEW.item_key
        OR NEW.item_text_sha256 IS DISTINCT FROM encode(pg_catalog.sha256(convert_to(NEW.payload->>'text','UTF8')),'hex')
        OR NOT EXISTS (SELECT 1 FROM wiki_projection.snapshots s,
            LATERAL jsonb_array_elements(s.payload->'items') i
            WHERE s.wiki_id=NEW.wiki_id AND s.snapshot_id=NEW.snapshot_id
                AND s.payload->>'kind'='paper' AND i=NEW.payload)
    THEN RAISE EXCEPTION 'Wiki items must exactly project their paper snapshot'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER item_guard BEFORE INSERT ON wiki_projection.items
    FOR EACH ROW EXECUTE FUNCTION wiki_projection.guard_item();
CREATE FUNCTION wiki_projection.guard_citation() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE source canonical_store.information; evidence jsonb; paper wiki_projection.snapshots;
BEGIN
    SELECT * INTO STRICT source FROM canonical_store.information WHERE information_id=NEW.information_id;
    SELECT * INTO STRICT paper FROM wiki_projection.snapshots WHERE wiki_id=NEW.wiki_id AND snapshot_id=NEW.snapshot_id;
    SELECT payload->'evidence'->NEW.ordinal INTO STRICT evidence FROM wiki_projection.items
        WHERE wiki_id=NEW.wiki_id AND snapshot_id=NEW.snapshot_id AND item_key=NEW.item_key;
    IF evidence IS DISTINCT FROM NEW.payload
        OR NEW.payload->>'information_id' IS DISTINCT FROM NEW.information_id::text
        OR NEW.payload->>'data_id' IS DISTINCT FROM NEW.data_id
        OR NEW.payload->>'source_execution_id' IS DISTINCT FROM NEW.source_execution_id::text
        OR NEW.payload->'char_start' IS DISTINCT FROM to_jsonb(NEW.char_start)
        OR NEW.payload->'char_end' IS DISTINCT FROM to_jsonb(NEW.char_end)
        OR NEW.payload->>'quote' IS DISTINCT FROM NEW.quote
        OR NEW.payload->>'media_sha256' IS DISTINCT FROM NEW.media_sha256
        OR source.data_id IS DISTINCT FROM NEW.data_id
        OR paper.data_id IS DISTINCT FROM NEW.data_id
        OR paper.source_execution_id IS DISTINCT FROM NEW.source_execution_id
        OR NOT EXISTS (SELECT 1 FROM compiler_runtime.records WHERE record_id=source.origin_record_id
            AND execution_id=NEW.source_execution_id AND data_id=NEW.data_id AND disposition='accepted')
        OR NEW.char_end>length(source.content)
        OR substring(source.content FROM NEW.char_start+1 FOR NEW.char_end-NEW.char_start) IS DISTINCT FROM NEW.quote
        OR (NEW.media_sha256 IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM jsonb_each(COALESCE(source.payload->'source_artifacts','{}'::jsonb)) a
                WHERE a.value->>'sha256'=NEW.media_sha256))
    THEN RAISE EXCEPTION 'Wiki citation must resolve to the exact original I, source execution and text/image'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER citation_guard BEFORE INSERT ON wiki_projection.citations
    FOR EACH ROW EXECUTE FUNCTION wiki_projection.guard_citation();

CREATE FUNCTION wiki_projection.guard_catalog() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE raw jsonb;
BEGIN
    SELECT convert_from(content,'UTF8')::jsonb INTO STRICT raw FROM wiki_projection.blobs WHERE sha256=NEW.raw_sha256;
    IF raw IS DISTINCT FROM NEW.payload OR NEW.payload->'version' IS DISTINCT FROM to_jsonb(NEW.version)
        OR NEW.payload->>'schema_version' IS DISTINCT FROM 'paper-topic-wiki-projection-v1'
        OR jsonb_typeof(NEW.payload->'papers') IS DISTINCT FROM 'object'
        OR jsonb_typeof(NEW.payload->'topics') IS DISTINCT FROM 'object'
    THEN RAISE EXCEPTION 'Wiki catalog raw payload and version must agree'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER catalog_guard BEFORE INSERT ON wiki_projection.catalogs
    FOR EACH ROW EXECUTE FUNCTION wiki_projection.guard_catalog();
CREATE FUNCTION wiki_projection.guard_member() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner wiki_projection.pages; snapshot wiki_projection.snapshots; entry jsonb;
BEGIN
    SELECT * INTO STRICT owner FROM wiki_projection.pages WHERE wiki_id=NEW.wiki_id AND page_id=NEW.page_id;
    SELECT * INTO STRICT snapshot FROM wiki_projection.snapshots WHERE wiki_id=NEW.wiki_id AND snapshot_id=NEW.snapshot_id;
    SELECT CASE owner.kind WHEN 'paper' THEN payload->'papers'->owner.data_id ELSE payload->'topics'->owner.topic_key END
        INTO STRICT entry FROM wiki_projection.catalogs WHERE wiki_id=NEW.wiki_id AND catalog_sha256=NEW.catalog_sha256;
    IF entry->>'page_id' IS DISTINCT FROM NEW.page_id::text
        OR entry->>'snapshot_id' IS DISTINCT FROM NEW.snapshot_id::text
        OR entry->>'snapshot_sha256' IS DISTINCT FROM snapshot.snapshot_sha256
        OR entry->>'body_sha256' IS DISTINCT FROM snapshot.body_sha256
        OR entry->>'title' IS DISTINCT FROM snapshot.payload->>'title'
    THEN RAISE EXCEPTION 'Wiki catalog member must select its exact same-page snapshot'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER member_guard BEFORE INSERT ON wiki_projection.members
    FOR EACH ROW EXECUTE FUNCTION wiki_projection.guard_member();

CREATE FUNCTION wiki_projection.guard_import() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.graph_payload->>'schema_version' IS DISTINCT FROM 'knowledge-graph-v1'
        OR NEW.graph_payload->'state_version' IS DISTINCT FROM to_jsonb(NEW.knowledge_state_version)
        OR NEW.manifest->>'schema_version' IS DISTINCT FROM 'wiki-archive-v1'
        OR jsonb_typeof(NEW.manifest->'files') IS DISTINCT FROM 'array'
    THEN RAISE EXCEPTION 'Wiki import must retain its exact archive and Knowledge state'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER import_guard BEFORE INSERT ON wiki_projection.imports
    FOR EACH ROW EXECUTE FUNCTION wiki_projection.guard_import();
CREATE FUNCTION wiki_projection.guard_file() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM wiki_projection.imports i,
        LATERAL jsonb_array_elements(i.manifest->'files') f,
        wiki_projection.blobs b WHERE i.request_id=NEW.request_id AND f->>'path'=NEW.path
            AND f->>'sha256'=NEW.raw_sha256 AND b.sha256=NEW.raw_sha256
            AND f->'byte_size'=to_jsonb(octet_length(b.content)))
    THEN RAISE EXCEPTION 'Archived file bytes must match the frozen import manifest'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER file_guard BEFORE INSERT ON wiki_projection.files
    FOR EACH ROW EXECUTE FUNCTION wiki_projection.guard_file();

CREATE FUNCTION wiki_projection.guard_knowledge_link() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE item wiki_projection.items; snapshot wiki_projection.snapshots; imported wiki_projection.imports;
BEGIN
    SELECT * INTO STRICT item FROM wiki_projection.items
        WHERE wiki_id=NEW.wiki_id AND snapshot_id=NEW.snapshot_id AND item_key=NEW.item_key;
    SELECT * INTO STRICT snapshot FROM wiki_projection.snapshots WHERE wiki_id=NEW.wiki_id AND snapshot_id=NEW.snapshot_id;
    SELECT * INTO STRICT imported FROM wiki_projection.imports WHERE request_id=NEW.request_id AND wiki_id=NEW.wiki_id;
    IF NEW.payload->>'snapshot_id' IS DISTINCT FROM NEW.snapshot_id::text
        OR NEW.payload->>'page_id' IS DISTINCT FROM snapshot.page_id::text
        OR NEW.payload->>'data_id' IS DISTINCT FROM snapshot.data_id
        OR NEW.payload->>'item_key' IS DISTINCT FROM NEW.item_key
        OR NEW.payload->>'item_text_sha256' IS DISTINCT FROM item.item_text_sha256
        OR NEW.payload->>'knode_id' IS DISTINCT FROM NEW.knode_id::text
        OR NEW.payload->>'knode_revision_id' IS DISTINCT FROM NEW.node_revision_id::text
        OR NEW.payload->>'content_fingerprint' IS DISTINCT FROM NEW.content_fingerprint
        OR NEW.payload->>'link_sha256' IS DISTINCT FROM NEW.link_sha256
        OR NEW.payload->'review_required' IS DISTINCT FROM to_jsonb(NEW.review_required)
        OR NEW.payload->>'relation' IS DISTINCT FROM 'shared_source_evidence'
        OR NEW.payload->'semantic_support_validated' IS DISTINCT FROM 'false'::jsonb
        OR NEW.payload->'knowledge_state_version' IS DISTINCT FROM to_jsonb(imported.knowledge_state_version)
        OR NOT EXISTS (SELECT 1 FROM canonical_store.knowledge_node_revisions
            WHERE knode_revision_id=NEW.node_revision_id AND knode_id=NEW.knode_id
                AND content_fingerprint=NEW.content_fingerprint)
        OR NOT EXISTS (SELECT 1 FROM wiki_projection.members WHERE wiki_id=NEW.wiki_id
            AND catalog_sha256=imported.catalog_sha256 AND snapshot_id=NEW.snapshot_id)
    THEN RAISE EXCEPTION 'Related Knowledge must bind an exact archived item and canonical Revision, without asserting support'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER knowledge_link_guard BEFORE INSERT ON wiki_projection.knowledge_links
    FOR EACH ROW EXECUTE FUNCTION wiki_projection.guard_knowledge_link();
CREATE FUNCTION wiki_projection.guard_knowledge_match() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE link wiki_projection.knowledge_links; citation wiki_projection.citations;
    grounding canonical_store.knowledge_node_groundings; expected jsonb; start_at integer; end_at integer;
BEGIN
    SELECT * INTO STRICT link FROM wiki_projection.knowledge_links WHERE link_id=NEW.link_id;
    SELECT * INTO STRICT citation FROM wiki_projection.citations WHERE wiki_id=link.wiki_id
        AND snapshot_id=link.snapshot_id AND item_key=link.item_key AND ordinal=NEW.wiki_evidence_index;
    SELECT * INTO STRICT grounding FROM canonical_store.knowledge_node_groundings WHERE grounding_id=NEW.grounding_id;
    expected:=link.payload->'matches'->NEW.ordinal;
    IF expected->'wiki_evidence_index' IS DISTINCT FROM to_jsonb(NEW.wiki_evidence_index)
        OR expected->>'grounding_id' IS DISTINCT FROM NEW.grounding_id::text
        OR expected->>'information_id' IS DISTINCT FROM NEW.information_id::text
        OR expected->>'data_id' IS DISTINCT FROM NEW.data_id
        OR expected->>'overlap_start' IS DISTINCT FROM NEW.overlap_start::text
        OR expected->>'overlap_end' IS DISTINCT FROM NEW.overlap_end::text
        OR expected->>'quote' IS DISTINCT FROM NEW.quote
        OR expected->>'quote_sha256' IS DISTINCT FROM encode(pg_catalog.sha256(convert_to(NEW.quote,'UTF8')),'hex')
        OR expected->>'media_sha256' IS DISTINCT FROM NEW.media_sha256
        OR expected->>'match_kind' IS DISTINCT FROM NEW.match_kind
        OR grounding.node_revision_id IS DISTINCT FROM link.node_revision_id
        OR grounding.information_id IS DISTINCT FROM NEW.information_id
        OR citation.information_id IS DISTINCT FROM NEW.information_id
        OR citation.data_id IS DISTINCT FROM NEW.data_id
    THEN RAISE EXCEPTION 'Related Knowledge match must bind the stored Revision grounding and Wiki citation'; END IF;
    IF NEW.match_kind='shared_image' THEN
        IF NEW.media_sha256 IS DISTINCT FROM citation.media_sha256 OR NEW.media_sha256 IS DISTINCT FROM grounding.media_sha256
        THEN RAISE EXCEPTION 'A shared image must be present in both exact source citations'; END IF;
    ELSE
        start_at:=greatest(citation.char_start,grounding.char_start);
        end_at:=least(citation.char_end,grounding.char_end);
        IF NEW.overlap_start IS DISTINCT FROM start_at OR NEW.overlap_end IS DISTINCT FROM end_at
            OR start_at>=end_at OR btrim(NEW.quote)=''
            OR substring(citation.quote FROM start_at-citation.char_start+1 FOR end_at-start_at) IS DISTINCT FROM NEW.quote
            OR substring(grounding.quote FROM start_at-grounding.char_start+1 FOR end_at-start_at) IS DISTINCT FROM NEW.quote
            OR ((citation.char_start,citation.char_end)=(grounding.char_start,grounding.char_end))
                IS DISTINCT FROM (NEW.match_kind='exact_text_range')
            OR (NEW.media_sha256 IS NOT NULL AND (NEW.media_sha256 IS DISTINCT FROM citation.media_sha256
                OR NEW.media_sha256 IS DISTINCT FROM grounding.media_sha256))
        THEN RAISE EXCEPTION 'Shared text must equal the exact nonempty source-range intersection'; END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER knowledge_match_guard BEFORE INSERT ON wiki_projection.knowledge_matches
    FOR EACH ROW EXECUTE FUNCTION wiki_projection.guard_knowledge_match();

CREATE FUNCTION wiki_projection.guard_head() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE next_import wiki_projection.imports; old_version bigint; next_version bigint; old_catalog text;
BEGIN
    IF TG_OP='INSERT' THEN
        IF NEW.current_import_id IS NOT NULL THEN RAISE EXCEPTION 'A Wiki starts without a selected import'; END IF;
        RETURN NEW;
    END IF;
    IF (NEW.wiki_id,NEW.created_at) IS DISTINCT FROM (OLD.wiki_id,OLD.created_at) OR NEW.current_import_id IS NULL
    THEN RAISE EXCEPTION 'Only the Wiki current import may change'; END IF;
    SELECT * INTO STRICT next_import FROM wiki_projection.imports WHERE wiki_id=NEW.wiki_id AND request_id=NEW.current_import_id;
    IF next_import.expected_head IS DISTINCT FROM OLD.current_import_id
    THEN RAISE EXCEPTION 'Stale Wiki import cannot overwrite the current selection'; END IF;
    IF OLD.current_import_id IS NOT NULL THEN
        SELECT i.catalog_sha256,c.version INTO STRICT old_catalog,old_version
            FROM wiki_projection.imports i JOIN wiki_projection.catalogs c USING(wiki_id,catalog_sha256)
            WHERE i.request_id=OLD.current_import_id AND i.wiki_id=OLD.wiki_id;
        SELECT version INTO STRICT next_version FROM wiki_projection.catalogs
            WHERE wiki_id=NEW.wiki_id AND catalog_sha256=next_import.catalog_sha256;
        IF next_version<old_version OR (next_version=old_version AND next_import.catalog_sha256<>old_catalog)
        THEN RAISE EXCEPTION 'Wiki catalog selection cannot move backwards or fork a version'; END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER wiki_head_guard BEFORE INSERT OR UPDATE ON wiki_projection.wikis
    FOR EACH ROW EXECUTE FUNCTION wiki_projection.guard_head();

DO $$ DECLARE relation text; BEGIN
    FOREACH relation IN ARRAY ARRAY['blobs','pages','snapshots','items','citations','catalogs','members',
        'imports','files','knowledge_links','knowledge_matches'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON wiki_projection.%I FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
        EXECUTE format('CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON wiki_projection.%I FOR EACH STATEMENT EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
    END LOOP;
END; $$;
CREATE TRIGGER wiki_no_delete BEFORE DELETE ON wiki_projection.wikis
    FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation();
CREATE TRIGGER wiki_no_truncate BEFORE TRUNCATE ON wiki_projection.wikis
    FOR EACH STATEMENT EXECUTE FUNCTION canonical_store.reject_snapshot_mutation();
GRANT USAGE ON SCHEMA wiki_projection TO palimpsest;
GRANT SELECT,INSERT ON ALL TABLES IN SCHEMA wiki_projection TO palimpsest;
GRANT UPDATE (current_import_id) ON wiki_projection.wikis TO palimpsest;
