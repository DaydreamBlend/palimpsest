-- Add typed binding and commit coverage to the existing noncanonical Wiki.
-- Keep 0008 and every historical byte/row unchanged; no semantic status changes.
CREATE FUNCTION wiki_projection.guard_knowledge_binding() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE imported wiki_projection.imports; revision canonical_store.knowledge_node_revisions;
    node canonical_store.knowledge_nodes; frozen_node jsonb; matching_nodes bigint;
    frozen_reviews jsonb; supplied_reviews jsonb; supplied_node jsonb;
BEGIN
    SELECT * INTO STRICT imported FROM wiki_projection.imports
        WHERE request_id=NEW.request_id AND wiki_id=NEW.wiki_id;
    SELECT * INTO STRICT revision FROM canonical_store.knowledge_node_revisions
        WHERE knode_revision_id=NEW.node_revision_id AND knode_id=NEW.knode_id;
    SELECT * INTO STRICT node FROM canonical_store.knowledge_nodes WHERE knode_id=NEW.knode_id;
    IF jsonb_typeof(imported.graph_payload->'nodes') IS DISTINCT FROM 'array'
        OR jsonb_typeof(NEW.payload->'node_snapshot') IS DISTINCT FROM 'object'
        OR jsonb_typeof(NEW.payload->'review_annotations') IS DISTINCT FROM 'array'
        OR jsonb_typeof(NEW.payload->'matches') IS DISTINCT FROM 'array'
    THEN RAISE EXCEPTION 'Knowledge binding needs a frozen node, review list and match array'; END IF;
    IF jsonb_array_length(NEW.payload->'matches')=0
    THEN RAISE EXCEPTION 'A Knowledge navigation link must declare actual source matches'; END IF;
    SELECT count(*),jsonb_agg(entry.value)->0 INTO matching_nodes,frozen_node
        FROM jsonb_array_elements(imported.graph_payload->'nodes') entry(value)
        WHERE entry.value->>'knode_id'=NEW.knode_id::text
            AND entry.value->>'knode_revision_id'=NEW.node_revision_id::text;
    supplied_node:=NEW.payload->'node_snapshot';
    IF matching_nodes<>1 OR supplied_node IS DISTINCT FROM frozen_node
        OR supplied_node->>'knode_id' IS DISTINCT FROM node.knode_id::text
        OR supplied_node->>'knode_revision_id' IS DISTINCT FROM revision.knode_revision_id::text
        OR supplied_node->>'kind' IS DISTINCT FROM node.kind
        OR supplied_node->>'statement' IS DISTINCT FROM revision.statement
        OR supplied_node->'semantic_payload' IS DISTINCT FROM revision.semantic_payload
        OR supplied_node->>'identity_fingerprint' IS DISTINCT FROM revision.identity_fingerprint
        OR supplied_node->>'content_fingerprint' IS DISTINCT FROM revision.content_fingerprint
        OR supplied_node->>'origin_record_id' IS DISTINCT FROM revision.origin_record_id::text
        OR supplied_node->>'supersedes_revision_id' IS DISTINCT FROM revision.supersedes_revision_id::text
    THEN RAISE EXCEPTION 'Knowledge node snapshot must equal the frozen graph and exact canonical Revision'; END IF;
    -- JSONB ordering preserves duplicates and does not depend on Python hashing.
    SELECT COALESCE(jsonb_agg(entry.value ORDER BY entry.value),'[]'::jsonb) INTO frozen_reviews
        FROM jsonb_array_elements(imported.review_annotations) entry(value)
        WHERE entry.value->>'node_revision_id'=NEW.node_revision_id::text;
    SELECT COALESCE(jsonb_agg(entry.value ORDER BY entry.value),'[]'::jsonb) INTO supplied_reviews
        FROM jsonb_array_elements(NEW.payload->'review_annotations') entry(value);
    IF supplied_reviews IS DISTINCT FROM frozen_reviews
        OR NEW.review_required IS DISTINCT FROM (jsonb_array_length(frozen_reviews)>0)
    THEN RAISE EXCEPTION 'Knowledge link must preserve every frozen review annotation for its Revision'; END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER knowledge_link_typed_binding_guard BEFORE INSERT ON wiki_projection.knowledge_links
    FOR EACH ROW EXECUTE FUNCTION wiki_projection.guard_knowledge_binding();

CREATE FUNCTION wiki_projection.check_import_coverage() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE imported wiki_projection.imports; identifier uuid; file_count bigint; link_count bigint;
BEGIN
    IF TG_TABLE_NAME='knowledge_matches' THEN
        SELECT request_id INTO STRICT identifier FROM wiki_projection.knowledge_links WHERE link_id=NEW.link_id;
    ELSE
        identifier:=NEW.request_id;
    END IF;
    SELECT * INTO STRICT imported FROM wiki_projection.imports WHERE request_id=identifier;
    SELECT count(*) INTO file_count FROM wiki_projection.files WHERE request_id=identifier;
    SELECT count(*) INTO link_count FROM wiki_projection.knowledge_links WHERE request_id=identifier;
    IF file_count IS DISTINCT FROM jsonb_array_length(imported.manifest->'files')::bigint
        OR to_jsonb(link_count) IS DISTINCT FROM imported.result->'related_link_count'
    THEN RAISE EXCEPTION 'Wiki import must persist every declared file and Knowledge link atomically'; END IF;
    IF EXISTS (SELECT 1 FROM wiki_projection.knowledge_links link
        LEFT JOIN wiki_projection.knowledge_matches matched ON matched.link_id=link.link_id
        WHERE link.request_id=identifier GROUP BY link.link_id,link.payload
        HAVING count(matched.ordinal) IS DISTINCT FROM jsonb_array_length(link.payload->'matches')::bigint
            OR min(matched.ordinal) IS DISTINCT FROM 0
            OR max(matched.ordinal) IS DISTINCT FROM jsonb_array_length(link.payload->'matches')-1)
    THEN RAISE EXCEPTION 'Knowledge link must persist each declared source match once at its exact ordinal'; END IF;
    RETURN NULL;
END; $$;
DO $$ DECLARE relation text; BEGIN
    FOREACH relation IN ARRAY ARRAY['imports','files','knowledge_links','knowledge_matches'] LOOP
        EXECUTE format('CREATE CONSTRAINT TRIGGER wiki_import_coverage_guard AFTER INSERT ON wiki_projection.%I DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION wiki_projection.check_import_coverage()',relation);
    END LOOP;
END; $$;
