-- Noncanonical, rebuildable retrieval indexes over one frozen Wiki import.
-- Python verifies canonical-JSON/profile/result hashes and actual source data.
-- Exact cosine retrieval deliberately has no ANN index in this first slice.
CREATE SCHEMA wiki_retrieval;

CREATE TABLE wiki_retrieval.indexes (
    index_id uuid PRIMARY KEY DEFAULT uuidv7() CHECK (uuid_extract_version(index_id) IS NOT DISTINCT FROM 7),
    wiki_id uuid NOT NULL REFERENCES wiki_projection.wikis,
    import_id uuid NOT NULL,
    corpus_sha256 text NOT NULL CHECK (corpus_sha256 ~ '^[0-9a-f]{64}$'),
    corpus jsonb NOT NULL CHECK (jsonb_typeof(corpus)='object'),
    profile_sha256 text NOT NULL CHECK (profile_sha256 ~ '^[0-9a-f]{64}$'),
    profile jsonb NOT NULL CHECK (jsonb_typeof(profile)='object'),
    embedding_result_sha256 text NOT NULL CHECK (embedding_result_sha256 ~ '^[0-9a-f]{64}$'),
    document_count integer NOT NULL CHECK (document_count>=0),
    chunk_count integer NOT NULL CHECK (chunk_count>=0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wiki_id,import_id) REFERENCES wiki_projection.imports(wiki_id,request_id)
);
CREATE TABLE wiki_retrieval.chunks (
    index_id uuid NOT NULL REFERENCES wiki_retrieval.indexes,
    chunk_id text NOT NULL CHECK (chunk_id ~ '^[0-9a-f]{64}$'),
    document_id text NOT NULL CHECK (length(document_id)>0),
    char_start integer NOT NULL CHECK (char_start>=0),
    char_end integer NOT NULL CHECK (char_end>char_start),
    text_sha256 text NOT NULL CHECK (text_sha256 ~ '^[0-9a-f]{64}$'),
    embedding vector NOT NULL,
    PRIMARY KEY (index_id,chunk_id)
);
CREATE INDEX wiki_retrieval_chunk_document ON wiki_retrieval.chunks(index_id,document_id,char_start,char_end);

CREATE FUNCTION wiki_retrieval.guard_index() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE imported wiki_projection.imports;
BEGIN
    SELECT * INTO STRICT imported FROM wiki_projection.imports
        WHERE request_id=NEW.import_id AND wiki_id=NEW.wiki_id;
    IF NEW.corpus->>'schema_version' IS DISTINCT FROM 'wiki-retrieval-corpus-v1'
        OR NEW.corpus->>'wiki_id' IS DISTINCT FROM NEW.wiki_id::text
        OR NEW.corpus->>'import_id' IS DISTINCT FROM NEW.import_id::text
        OR NEW.corpus->'knowledge_state_version' IS DISTINCT FROM to_jsonb(imported.knowledge_state_version)
        OR jsonb_typeof(NEW.corpus->'documents') IS DISTINCT FROM 'array'
        OR jsonb_typeof(NEW.profile->'dimensions') IS DISTINCT FROM 'number'
        OR (NEW.profile->>'dimensions' ~ '^[1-9][0-9]*$') IS DISTINCT FROM true
    THEN RAISE EXCEPTION 'Retrieval index must bind one exact Wiki import and a positive integer embedding dimension'; END IF;
    IF jsonb_array_length(NEW.corpus->'documents') IS DISTINCT FROM NEW.document_count
        OR EXISTS (SELECT 1 FROM jsonb_array_elements(NEW.corpus->'documents') doc
            WHERE jsonb_typeof(doc) IS DISTINCT FROM 'object'
                OR jsonb_typeof(doc->'document_id') IS DISTINCT FROM 'string'
                OR length(doc->>'document_id')=0
                OR jsonb_typeof(doc->'text') IS DISTINCT FROM 'string'
                OR length(doc->>'text')=0
                OR (doc->>'kind' IN ('wiki','knowledge','information')) IS DISTINCT FROM true)
        OR (SELECT count(DISTINCT doc->>'document_id') FROM jsonb_array_elements(NEW.corpus->'documents') doc)
            IS DISTINCT FROM NEW.document_count::bigint
    THEN RAISE EXCEPTION 'Retrieval corpus must declare every uniquely identified nonempty source document'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER retrieval_index_guard BEFORE INSERT ON wiki_retrieval.indexes
    FOR EACH ROW EXECUTE FUNCTION wiki_retrieval.guard_index();

CREATE FUNCTION wiki_retrieval.guard_chunk() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE stored wiki_retrieval.indexes; document_text text;
BEGIN
    SELECT * INTO STRICT stored FROM wiki_retrieval.indexes WHERE index_id=NEW.index_id;
    SELECT doc->>'text' INTO STRICT document_text FROM jsonb_array_elements(stored.corpus->'documents') doc
        WHERE doc->>'document_id'=NEW.document_id;
    IF NEW.char_start<0 OR NEW.char_end<=NEW.char_start OR NEW.char_end>length(document_text)
        OR NEW.text_sha256 IS DISTINCT FROM encode(pg_catalog.sha256(convert_to(
            substring(document_text FROM NEW.char_start+1 FOR NEW.char_end-NEW.char_start),'UTF8')),'hex')
        OR to_jsonb(vector_dims(NEW.embedding)) IS DISTINCT FROM stored.profile->'dimensions'
    THEN RAISE EXCEPTION 'Retrieval chunk must preserve the exact corpus Unicode range, text hash and embedding dimension'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER retrieval_chunk_guard BEFORE INSERT ON wiki_retrieval.chunks
    FOR EACH ROW EXECUTE FUNCTION wiki_retrieval.guard_chunk();

CREATE FUNCTION wiki_retrieval.check_index_coverage() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE stored wiki_retrieval.indexes;
BEGIN
    SELECT * INTO STRICT stored FROM wiki_retrieval.indexes WHERE index_id=NEW.index_id;
    IF (SELECT count(*) FROM wiki_retrieval.chunks WHERE index_id=NEW.index_id)
        IS DISTINCT FROM stored.chunk_count::bigint
    THEN RAISE EXCEPTION 'Retrieval index must persist its declared chunk count atomically'; END IF;
    -- ponytail: per-row deferred scans suit the small initial corpus; consolidate
    -- the validation schedule if measurements show this dominates import time.
    IF EXISTS (WITH documents AS (
            SELECT doc->>'document_id' AS document_id,length(doc->>'text') AS text_length
                FROM jsonb_array_elements(stored.corpus->'documents') doc),
        windows AS (
            SELECT document_id,char_start,char_end,
                max(char_end) OVER (PARTITION BY document_id ORDER BY char_start,char_end,chunk_id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS previous_end
                FROM wiki_retrieval.chunks WHERE index_id=NEW.index_id)
        SELECT 1 FROM documents doc LEFT JOIN windows win USING(document_id)
        GROUP BY doc.document_id,doc.text_length
        HAVING count(win.char_start)=0 OR min(win.char_start) IS DISTINCT FROM 0
            OR max(win.char_end) IS DISTINCT FROM doc.text_length
            OR bool_or(win.previous_end IS NOT NULL AND win.char_start>win.previous_end))
    THEN RAISE EXCEPTION 'Every retrieval document must have complete contiguous chunk coverage without omitted characters'; END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER retrieval_index_coverage_guard AFTER INSERT ON wiki_retrieval.indexes
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION wiki_retrieval.check_index_coverage();
CREATE CONSTRAINT TRIGGER retrieval_chunk_coverage_guard AFTER INSERT ON wiki_retrieval.chunks
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION wiki_retrieval.check_index_coverage();

DO $$ DECLARE relation text; BEGIN
    FOREACH relation IN ARRAY ARRAY['indexes','chunks'] LOOP
        EXECUTE format('CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON wiki_retrieval.%I FOR EACH ROW EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
        EXECUTE format('CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON wiki_retrieval.%I FOR EACH STATEMENT EXECUTE FUNCTION canonical_store.reject_snapshot_mutation()',relation);
    END LOOP;
END; $$;
GRANT USAGE ON SCHEMA wiki_retrieval TO palimpsest;
GRANT SELECT,INSERT ON ALL TABLES IN SCHEMA wiki_retrieval TO palimpsest;
