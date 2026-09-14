-- Preserve installed 0011 and repair its shared Node/Edge trigger additively.
-- PL/pgSQL plans an IF expression before SQL boolean short-circuit evaluation;
-- only a separate Node branch may reference fields absent from an Edge record.
CREATE OR REPLACE FUNCTION canonical_store.guard_k_revision_insert() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE current_id uuid; previous_payload jsonb; previous_qualifiers jsonb; previous_fp text; same_payload boolean;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM compiler_runtime.k_compilation_records WHERE record_id=NEW.origin_record_id
        AND disposition IN ('pending','needs_human')
        AND ((TG_TABLE_NAME='knowledge_node_revisions' AND record_type IN ('i2k','k2k'))
            OR (TG_TABLE_NAME='knowledge_edge_revisions' AND record_type='n2e')))
    THEN RAISE EXCEPTION 'K revision requires its unresolved operation Record'; END IF;
    IF TG_TABLE_NAME='knowledge_node_revisions' THEN
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
