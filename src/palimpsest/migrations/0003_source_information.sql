-- U11: add a source-preserving representation; existing snapshots stay intact.
ALTER TABLE canonical_store.information ALTER COLUMN semantic_type DROP NOT NULL;
ALTER TABLE canonical_store.information ADD COLUMN unit_type text;
ALTER TABLE canonical_store.information DROP CONSTRAINT information_content_check;
ALTER TABLE canonical_store.information ADD CONSTRAINT information_representation_check CHECK (
    ((payload->>'schema_version' = 'information-v1'
        AND semantic_type IS NOT NULL AND unit_type IS NULL AND length(content)>0)
    OR (payload->>'schema_version' = 'source-information-v1'
        AND semantic_type IS NULL AND unit_type IN ('text','image','figure','table','equation')
        AND unit_type IS NOT NULL
        AND kind = CASE WHEN unit_type IN ('image','figure') THEN 'image' ELSE 'text' END
        AND payload->>'validation_basis' = 'source_structure'
        AND payload->'semantic_checked' = 'false'::jsonb
        AND jsonb_typeof(payload->'source_blocks') = 'array'
        AND jsonb_array_length(payload->'source_blocks')>0
        AND payload->'empty_content' = to_jsonb(length(content)=0))) IS TRUE
);
