-- Markdown has text ranges, never fabricated PDF pages or coordinates.
-- Existing PDF snapshots and fingerprints remain unchanged.
ALTER TABLE canonical_store.information_groundings
    ADD COLUMN locator_type text NOT NULL DEFAULT 'pdf_region',
    ADD COLUMN text_range jsonb,
    ALTER COLUMN page_index DROP NOT NULL,
    ALTER COLUMN bbox DROP NOT NULL,
    ALTER COLUMN page_size DROP NOT NULL;

ALTER TABLE canonical_store.information_groundings ADD CONSTRAINT grounding_locator_check CHECK (
    ((locator_type='pdf_region' AND page_index IS NOT NULL AND bbox IS NOT NULL
       AND page_size IS NOT NULL AND text_range IS NULL)
    OR (locator_type='text_range' AND page_index IS NULL AND bbox IS NULL AND page_size IS NULL
       AND jsonb_typeof(text_range)='object'
       AND text_range ?& ARRAY['byte_start','byte_end','char_start','char_end','line_start','line_end']
       AND text_range-ARRAY['byte_start','byte_end','char_start','char_end','line_start','line_end']='{}'::jsonb
       AND jsonb_typeof(text_range->'byte_start')='number' AND (text_range->>'byte_start') ~ '^[0-9]+$'
       AND jsonb_typeof(text_range->'byte_end')='number' AND (text_range->>'byte_end') ~ '^[0-9]+$'
       AND jsonb_typeof(text_range->'char_start')='number' AND (text_range->>'char_start') ~ '^[0-9]+$'
       AND jsonb_typeof(text_range->'char_end')='number' AND (text_range->>'char_end') ~ '^[0-9]+$'
       AND jsonb_typeof(text_range->'line_start')='number' AND (text_range->>'line_start') ~ '^[1-9][0-9]*$'
       AND jsonb_typeof(text_range->'line_end')='number' AND (text_range->>'line_end') ~ '^[1-9][0-9]*$'
       AND (text_range->>'byte_start')::numeric <= (text_range->>'byte_end')::numeric
       AND (text_range->>'char_start')::numeric <= (text_range->>'char_end')::numeric
       AND (text_range->>'line_start')::numeric <= (text_range->>'line_end')::numeric)) IS TRUE
);

CREATE OR REPLACE FUNCTION canonical_store.guard_grounding_insert() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM canonical_store.information i
        JOIN compiler_runtime.records r ON r.record_id=i.origin_record_id
        JOIN compiler_runtime.parse_artifacts p ON p.execution_id=r.execution_id AND p.data_id=i.data_id
        CROSS JOIN LATERAL jsonb_array_elements(p.bundle->'blocks') b
        WHERE i.information_id=NEW.information_id AND r.disposition IS NULL
          AND p.parse_artifact_id=NEW.parse_artifact_id AND p.data_id=NEW.data_id
          AND b->>'block_id'=NEW.block_id
          AND COALESCE(b->>'locator_type','pdf_region')=NEW.locator_type
          AND b->>'raw_locator'=NEW.raw_locator AND b->>'anchor_sha256'=NEW.anchor_sha256
          AND ((NEW.locator_type='pdf_region' AND (b->>'page_index')::integer=NEW.page_index
                AND b->'bbox'=NEW.bbox AND b->'page_size'=NEW.page_size AND NEW.text_range IS NULL)
            OR (NEW.locator_type='text_range' AND b->'text_range'=NEW.text_range
                AND b->>'page_index' IS NULL AND b->>'bbox' IS NULL AND b->>'page_size' IS NULL
                AND NEW.page_index IS NULL AND NEW.bbox IS NULL AND NEW.page_size IS NULL))
    ) THEN RAISE EXCEPTION 'Grounding must match the original execution block before acceptance'; END IF;
    RETURN NEW;
END; $$;
