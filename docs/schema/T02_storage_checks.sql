-- T01 REVIEW FIXTURE / NOT EXECUTED against PostgreSQL.
-- Run after T02_storage_draft.sql in a NEW disposable PostgreSQL 18 database.
-- Use psql -X --set=ON_ERROR_STOP=1. Successful checks end in ROLLBACK.
-- These checks cover SQL constraints only: no filesystem, application, crash,
-- concurrent-session, idempotent response replay, or semantic-model test.
BEGIN;

-- Each rejected statement runs in its own subtransaction. An unexpected error
-- is rethrown unchanged; the no-error assertion is outside the catch block.
CREATE FUNCTION pg_temp.expect_sqlstate(statement text, expected_state text)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    actual_state text;
BEGIN
    BEGIN
        EXECUTE statement;
    EXCEPTION WHEN OTHERS THEN
        GET STACKED DIAGNOSTICS actual_state = RETURNED_SQLSTATE;
        IF actual_state <> expected_state THEN
            RAISE;
        END IF;
        RETURN;
    END;
    RAISE EXCEPTION 'Expected SQLSTATE %, but statement succeeded: %',
        expected_state, statement USING ERRCODE = 'P0001';
END;
$$;

DO $$
DECLARE
    data_a text := repeat('a', 64);
    data_b text := repeat('b', 64);
    acquisition_a uuid;
    acquisition_a_second uuid;
    acquisition_b uuid;
    committed_request uuid;
    duplicate_request uuid;
    published_duplicate_request uuid;
    retry_request uuid;
    mutation text;
    bad_uuid text;
    result_count bigint;
BEGIN
    IF current_setting('server_version_num')::integer / 10000 <> 18 THEN
        RAISE EXCEPTION 'Fixture requires PostgreSQL major 18';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_extension WHERE extname = 'vector') THEN
        RAISE EXCEPTION 'Required vector extension is missing';
    END IF;
    IF EXISTS (SELECT FROM canonical_store.data)
       OR EXISTS (SELECT FROM canonical_store.data_acquisitions)
       OR EXISTS (SELECT FROM compiler_runtime.data_import_requests) THEN
        RAISE EXCEPTION 'Fixture requires empty tables in a disposable test database';
    END IF;

    INSERT INTO canonical_store.data
        (data_id, media_type, byte_size, artifact_path, original_name)
    VALUES
        (data_a, 'application/pdf', 123, 'objects/sha256/aa/' || data_a, 'paper.pdf'),
        (data_b, 'text/plain', 0, 'objects/sha256/bb/' || data_b, 'empty.txt');
    IF EXISTS (SELECT FROM canonical_store.data WHERE sha256 IS DISTINCT FROM data_id) THEN
        RAISE EXCEPTION 'Generated sha256 does not match Data identity';
    END IF;

    -- Reject malformed hashes, a path outside the content address, negative
    -- size, empty media type, and byte-identical Data under a second insert.
    PERFORM pg_temp.expect_sqlstate(
        'INSERT INTO canonical_store.data (data_id, media_type, byte_size, artifact_path) '
        || 'VALUES (repeat(''C'', 64), ''text/plain'', 1, ''objects/sha256/CC/'' || repeat(''C'', 64))', '23514');
    PERFORM pg_temp.expect_sqlstate(
        'INSERT INTO canonical_store.data (data_id, media_type, byte_size, artifact_path) '
        || 'VALUES (repeat(''c'', 63), ''text/plain'', 1, ''objects/sha256/cc/'' || repeat(''c'', 63))', '23514');
    PERFORM pg_temp.expect_sqlstate(
        'INSERT INTO canonical_store.data (data_id, media_type, byte_size, artifact_path) '
        || 'VALUES (repeat(''c'', 64), ''text/plain'', 1, ''../outside'')', '23514');
    PERFORM pg_temp.expect_sqlstate(
        'INSERT INTO canonical_store.data (data_id, media_type, byte_size, artifact_path) '
        || 'VALUES (repeat(''c'', 64), ''text/plain'', -1, ''objects/sha256/cc/'' || repeat(''c'', 64))', '23514');
    PERFORM pg_temp.expect_sqlstate(
        'INSERT INTO canonical_store.data (data_id, media_type, byte_size, artifact_path) '
        || 'VALUES (repeat(''c'', 64), '''', 1, ''objects/sha256/cc/'' || repeat(''c'', 64))', '23514');
    PERFORM pg_temp.expect_sqlstate(format(
        'INSERT INTO canonical_store.data (data_id, media_type, byte_size, artifact_path) '
        || 'VALUES (%L, ''application/pdf'', 123, %L)', data_a, 'objects/sha256/aa/' || data_a), '23505');
    PERFORM pg_temp.expect_sqlstate(
        'INSERT INTO canonical_store.data (data_id, sha256, media_type, byte_size, artifact_path) '
        || 'VALUES (repeat(''c'', 64), repeat(''d'', 64), ''text/plain'', 1, '
        || '''objects/sha256/cc/'' || repeat(''c'', 64))', '428C9');

    -- Multiple explicitly recorded origins share one D. A missing parent is
    -- rejected; version 4 and a version-7 nibble with a non-RFC variant fail.
    INSERT INTO canonical_store.data_acquisitions (data_id, import_method, origin_uri)
    VALUES (data_a, 'file', 'publisher:example') RETURNING acquisition_id INTO acquisition_a;
    INSERT INTO canonical_store.data_acquisitions (data_id, import_method, origin_uri)
    VALUES (data_a, 'explicit_provenance', 'email:example') RETURNING acquisition_id INTO acquisition_a_second;
    INSERT INTO canonical_store.data_acquisitions (data_id, import_method)
    VALUES (data_b, 'file') RETURNING acquisition_id INTO acquisition_b;
    IF uuid_extract_version(acquisition_a) IS DISTINCT FROM 7
       OR acquisition_a = acquisition_a_second THEN
        RAISE EXCEPTION 'Acquisition defaults must produce distinct UUIDv7 IDs';
    END IF;
    PERFORM pg_temp.expect_sqlstate(
        'INSERT INTO canonical_store.data_acquisitions (data_id, import_method) '
        || 'VALUES (repeat(''d'', 64), ''file'')', '23503');
    FOREACH bad_uuid IN ARRAY ARRAY[
        '00000000-0000-4000-8000-000000000001',
        '00000000-0000-7000-0000-000000000001'
    ] LOOP
        PERFORM pg_temp.expect_sqlstate(format(
            'INSERT INTO canonical_store.data_acquisitions (acquisition_id, data_id, import_method) '
            || 'VALUES (%L, %L, ''file'')', bad_uuid, data_a), '23514');
        PERFORM pg_temp.expect_sqlstate(format(
            'INSERT INTO compiler_runtime.data_import_requests '
            || '(request_id, request_fingerprint, payload_sha256, byte_size, media_type, import_method) '
            || 'VALUES (%L, %L, %L, 123, ''application/pdf'', ''file'')', bad_uuid, data_a, data_a), '23514');
    END LOOP;
    PERFORM pg_temp.expect_sqlstate(format(
        'INSERT INTO canonical_store.data_acquisitions (data_id, import_method, external_metadata) '
        || 'VALUES (%L, ''file'', ''[]''::jsonb)', data_a), '23514');

    INSERT INTO compiler_runtime.data_import_requests
        (request_fingerprint, payload_sha256, byte_size, media_type, import_method)
    VALUES (data_a, data_a, 123, 'application/pdf', 'file')
    RETURNING request_id INTO committed_request;
    INSERT INTO compiler_runtime.data_import_requests
        (request_fingerprint, payload_sha256, byte_size, media_type, import_method)
    VALUES (data_a, data_a, 123, 'application/pdf', 'file')
    RETURNING request_id INTO duplicate_request;
    INSERT INTO compiler_runtime.data_import_requests
        (request_fingerprint, payload_sha256, byte_size, media_type, import_method)
    VALUES (data_b, data_b, 0, 'text/plain', 'file')
    RETURNING request_id INTO published_duplicate_request;
    INSERT INTO compiler_runtime.data_import_requests
        (request_fingerprint, payload_sha256, byte_size, media_type, import_method)
    VALUES (data_a, data_a, 123, 'application/pdf', 'file')
    RETURNING request_id INTO retry_request;
    IF uuid_extract_version(committed_request) IS DISTINCT FROM 7
       OR committed_request = duplicate_request THEN
        RAISE EXCEPTION 'Request IDs must be distinct UUIDv7; fingerprints are not globally unique';
    END IF;

    PERFORM pg_temp.expect_sqlstate(format(
        'INSERT INTO compiler_runtime.data_import_requests '
        || '(request_id, request_fingerprint, payload_sha256, byte_size, media_type, import_method) '
        || 'VALUES (%L, %L, %L, 123, ''application/pdf'', ''file'')', committed_request, data_a, data_a), '23505');
    PERFORM pg_temp.expect_sqlstate(format(
        'INSERT INTO compiler_runtime.data_import_requests '
        || '(request_fingerprint, payload_sha256, byte_size, media_type, import_method, state) '
        || 'VALUES (%L, %L, 123, ''application/pdf'', ''file'', ''published'')', data_a, data_a), '23514');

    -- Frozen command inputs cannot be rewritten even before publication.
    FOREACH mutation IN ARRAY ARRAY[
        'request_id = uuidv7()',
        'request_fingerprint = repeat(''c'', 64)',
        'payload_sha256 = repeat(''c'', 64)',
        'byte_size = 124',
        'media_type = ''text/plain''',
        'origin_uri = ''changed:origin''',
        'import_method = ''changed_method''',
        'retrieved_at = CURRENT_TIMESTAMP',
        'original_name = ''renamed.pdf''',
        'external_metadata = ''{"changed":true}''::jsonb',
        'actor_ref = ''different_actor''',
        'created_at = created_at + interval ''1 second'''
    ] LOOP
        PERFORM pg_temp.expect_sqlstate(format(
            'UPDATE compiler_runtime.data_import_requests SET state = ''published'', %s '
            || 'WHERE request_id = %L', mutation, committed_request), '23514');
    END LOOP;

    -- A complete result cannot skip publication. While published, both the
    -- payload/Data equality and acquisition/Data membership must be enforced.
    PERFORM pg_temp.expect_sqlstate(format(
        'UPDATE compiler_runtime.data_import_requests SET state = ''committed'', '
        || 'result_data_id = %L, result_acquisition_id = %L, resolved_at = CURRENT_TIMESTAMP '
        || 'WHERE request_id = %L', data_a, acquisition_a, committed_request), '23514');
    UPDATE compiler_runtime.data_import_requests SET state = 'published'
    WHERE request_id = committed_request;
    PERFORM pg_temp.expect_sqlstate(format(
        'UPDATE compiler_runtime.data_import_requests SET state = ''committed'', '
        || 'result_data_id = %L, result_acquisition_id = %L, resolved_at = CURRENT_TIMESTAMP '
        || 'WHERE request_id = %L', data_b, acquisition_b, committed_request), '23514');
    PERFORM pg_temp.expect_sqlstate(format(
        'UPDATE compiler_runtime.data_import_requests SET state = ''committed'', '
        || 'result_data_id = %L, result_acquisition_id = %L, resolved_at = CURRENT_TIMESTAMP '
        || 'WHERE request_id = %L', data_a, acquisition_b, committed_request), '23503');
    PERFORM pg_temp.expect_sqlstate(format(
        'UPDATE compiler_runtime.data_import_requests SET state = ''committed'', '
        || 'result_data_id = %L, resolved_at = CURRENT_TIMESTAMP WHERE request_id = %L',
        data_a, committed_request), '23514');
    UPDATE compiler_runtime.data_import_requests
    SET state = 'committed', result_data_id = data_a,
        result_acquisition_id = acquisition_a, resolved_at = CURRENT_TIMESTAMP
    WHERE request_id = committed_request;

    -- Both allowed duplicate paths reference existing D and create no acquisition.
    PERFORM pg_temp.expect_sqlstate(format(
        'UPDATE compiler_runtime.data_import_requests SET state = ''duplicate'', '
        || 'result_data_id = %L, resolved_at = CURRENT_TIMESTAMP '
        || 'WHERE request_id = %L', data_a, duplicate_request), '23514');
    PERFORM pg_temp.expect_sqlstate(format(
        'UPDATE compiler_runtime.data_import_requests SET state = ''duplicate'', '
        || 'result_data_id = %L, error_code = ''other_error'', resolved_at = CURRENT_TIMESTAMP '
        || 'WHERE request_id = %L', data_a, duplicate_request), '23514');
    PERFORM pg_temp.expect_sqlstate(format(
        'UPDATE compiler_runtime.data_import_requests SET state = ''duplicate'', '
        || 'result_data_id = %L, result_acquisition_id = %L, error_code = ''duplicate_data'', '
        || 'resolved_at = CURRENT_TIMESTAMP WHERE request_id = %L',
        data_a, acquisition_a, duplicate_request), '23514');
    UPDATE compiler_runtime.data_import_requests
    SET state = 'duplicate', result_data_id = data_a,
        error_code = 'duplicate_data', resolved_at = CURRENT_TIMESTAMP
    WHERE request_id = duplicate_request;
    UPDATE compiler_runtime.data_import_requests SET state = 'published'
    WHERE request_id = published_duplicate_request;
    UPDATE compiler_runtime.data_import_requests
    SET state = 'duplicate', result_data_id = data_b,
        error_code = 'duplicate_data', resolved_at = CURRENT_TIMESTAMP
    WHERE request_id = published_duplicate_request;

    -- Failed work can return to staged only after its failure receipt is cleared;
    -- fixed request inputs survive both pre-publication and post-publication failure.
    PERFORM pg_temp.expect_sqlstate(format(
        'UPDATE compiler_runtime.data_import_requests SET state = ''failed'', '
        || 'resolved_at = CURRENT_TIMESTAMP WHERE request_id = %L', retry_request), '23514');
    UPDATE compiler_runtime.data_import_requests
    SET state = 'failed', error_code = 'publish_failed', resolved_at = CURRENT_TIMESTAMP
    WHERE request_id = retry_request;
    PERFORM pg_temp.expect_sqlstate(format(
        'UPDATE compiler_runtime.data_import_requests SET state = ''staged'' WHERE request_id = %L',
        retry_request), '23514');
    UPDATE compiler_runtime.data_import_requests
    SET state = 'staged', error_code = NULL, resolved_at = NULL WHERE request_id = retry_request;
    UPDATE compiler_runtime.data_import_requests SET state = 'published'
    WHERE request_id = retry_request;
    UPDATE compiler_runtime.data_import_requests
    SET state = 'failed', error_code = 'commit_failed', resolved_at = CURRENT_TIMESTAMP
    WHERE request_id = retry_request;
    UPDATE compiler_runtime.data_import_requests
    SET state = 'staged', error_code = NULL, resolved_at = NULL WHERE request_id = retry_request;

    -- Terminal receipts are read for retry, not updated (even to identical values).
    PERFORM pg_temp.expect_sqlstate(format(
        'UPDATE compiler_runtime.data_import_requests SET state = state WHERE request_id = %L',
        committed_request), '23514');
    PERFORM pg_temp.expect_sqlstate(format(
        'UPDATE compiler_runtime.data_import_requests SET result_acquisition_id = %L WHERE request_id = %L',
        acquisition_a_second, committed_request), '23514');
    PERFORM pg_temp.expect_sqlstate(format(
        'UPDATE compiler_runtime.data_import_requests SET state = ''staged'', result_data_id = NULL, '
        || 'error_code = NULL, resolved_at = NULL WHERE request_id = %L', duplicate_request), '23514');

    -- Explicitly include referencing tables for TRUNCATE so FK prechecks do not
    -- mask the expected immutable-table trigger with a different SQLSTATE.
    PERFORM pg_temp.expect_sqlstate(
        'UPDATE canonical_store.data SET byte_size = byte_size + 1', '55000');
    PERFORM pg_temp.expect_sqlstate('DELETE FROM canonical_store.data', '55000');
    PERFORM pg_temp.expect_sqlstate(
        'TRUNCATE canonical_store.data, canonical_store.data_acquisitions, compiler_runtime.data_import_requests', '55000');
    PERFORM pg_temp.expect_sqlstate(
        'UPDATE canonical_store.data_acquisitions SET origin_uri = ''changed:origin''', '55000');
    PERFORM pg_temp.expect_sqlstate('DELETE FROM canonical_store.data_acquisitions', '55000');
    PERFORM pg_temp.expect_sqlstate(
        'TRUNCATE canonical_store.data_acquisitions, compiler_runtime.data_import_requests', '55000');
    PERFORM pg_temp.expect_sqlstate('DELETE FROM compiler_runtime.data_import_requests', '55000');
    PERFORM pg_temp.expect_sqlstate('TRUNCATE compiler_runtime.data_import_requests', '55000');

    SELECT count(*) INTO result_count FROM canonical_store.data;
    IF result_count <> 2 THEN RAISE EXCEPTION 'Unexpected Data count: %', result_count; END IF;
    SELECT count(*) INTO result_count FROM canonical_store.data_acquisitions;
    IF result_count <> 3 THEN RAISE EXCEPTION 'Unexpected acquisition count: %', result_count; END IF;
    SELECT count(*) INTO result_count FROM compiler_runtime.data_import_requests;
    IF result_count <> 4 THEN RAISE EXCEPTION 'Unexpected request count: %', result_count; END IF;
    IF NOT EXISTS (
        SELECT FROM compiler_runtime.data_import_requests
        WHERE request_id = committed_request AND state = 'committed'
          AND result_data_id = data_a AND result_acquisition_id = acquisition_a
    ) OR NOT EXISTS (
        SELECT FROM compiler_runtime.data_import_requests
        WHERE request_id = retry_request AND state = 'staged'
          AND payload_sha256 = data_a AND byte_size = 123
          AND error_code IS NULL AND resolved_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Expected preserved success receipt and retry inputs';
    END IF;
    RAISE NOTICE 'T02 SQL constraint fixture completed; all fixture changes will be rolled back';
END;
$$;

ROLLBACK;
