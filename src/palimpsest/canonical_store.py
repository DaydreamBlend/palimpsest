"""PostgreSQL Data storage; each method owns a short transaction."""

from contextlib import contextmanager
from hashlib import sha256
from importlib.resources import files
import os
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .errors import PalimpsestError


MIGRATIONS = ("0001_data", "0002_information", "0003_source_information", "0004_text_groundings", "0005_knowledge", "0006_i2k_selection", "0007_multi_source_i2k", "0008_wiki_projection", "0009_wiki_binding_guards", "0010_wiki_retrieval", "0011_k2k", "0012_k2k_revision_guard", "0013_data_versions", "0014_user_requested_d2k", "0015_explicit_knowledge_revision", "0016_propagation_worker", "0017_n2e_relations", "0018_n2e_review_agreement", "0019_n2e_effect_fence", "0020_effective_k2k", "0021_wisdom", "0022_parchment", "0023_wisdom_snapshot_guards")
MIGRATION_VERSION = MIGRATIONS[-1]

def migration_source(version=MIGRATION_VERSION):
    """UTF-8 text with LF newlines gives the same checksum on Windows/Linux."""
    text = files("palimpsest").joinpath(f"migrations/{version}.sql").read_text(encoding="utf-8")
    return text, sha256(text.encode("utf-8")).hexdigest()


@contextmanager
def connection(dsn):
    try:
        with psycopg.connect(dsn, autocommit=True, row_factory=dict_row,
                             connect_timeout=5) as conn:
            yield conn
    except psycopg.OperationalError:
        raise PalimpsestError("database_unavailable", "PostgreSQL에 연결할 수 없습니다.", 3) from None
    except psycopg.Error:
        raise PalimpsestError("database_error", "데이터베이스 작업을 완료하지 못했습니다.", 4) from None


def migrate(admin_dsn):
    """Append reviewed migrations; verify every installed predecessor checksum."""
    sources = {version: migration_source(version) for version in MIGRATIONS}
    expected = [{"version": version, "checksum": sources[version][1]} for version in MIGRATIONS]
    with connection(admin_dsn) as conn, conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(74291602)")
        major = conn.execute("SHOW server_version_num").fetchone()["server_version_num"]
        if int(major) // 10000 != 18:
            raise PalimpsestError("database_version_mismatch", "초기 실행은 PostgreSQL 18을 요구합니다.", 3)
        installed = conn.execute("SELECT to_regclass('compiler_runtime.schema_migrations') AS table_name").fetchone()
        if installed["table_name"]:
            rows = conn.execute("SELECT version, checksum FROM compiler_runtime.schema_migrations ORDER BY version").fetchall()
            if not rows or rows != expected[:len(rows)]:
                raise PalimpsestError("migration_conflict", "설치된 migration과 실행 파일이 다릅니다.", 6)
            version = conn.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()
            if not version or version["extversion"] != "0.8.6":
                raise PalimpsestError("extension_version_mismatch", "pgvector 버전이 실행 profile과 다릅니다.", 3)
            for pending in MIGRATIONS[len(rows):]:
                migration, digest = sources[pending]
                conn.execute(migration, prepare=False)
                conn.execute("INSERT INTO compiler_runtime.schema_migrations(version,checksum) VALUES (%s,%s)", (pending,digest))
            return {"schema_version": MIGRATION_VERSION, "applied": len(rows)<len(MIGRATIONS)}
        existing = conn.execute("SELECT nspname FROM pg_namespace WHERE nspname IN ('canonical_store','compiler_runtime')").fetchall()
        if existing:
            raise PalimpsestError("migration_conflict", "기존 schema가 있어 자동 초기화할 수 없습니다.", 6)
        password_file = os.environ.get("PALIMPSEST_DB_PASSWORD_FILE")
        password = Path(password_file).read_text().strip() if password_file else os.environ.get("PALIMPSEST_DB_PASSWORD")
        if not password:
            raise PalimpsestError("missing_configuration", "앱 DB 역할의 비밀번호 설정이 필요합니다.", 2)
        if conn.execute("SELECT 1 FROM pg_roles WHERE rolname='palimpsest'").fetchone():
            raise PalimpsestError("migration_conflict", "이미 존재하는 앱 DB 역할을 변경하지 않습니다.", 6)
        conn.execute(sources[MIGRATIONS[0]][0], prepare=False)
        conn.execute(sql.SQL("CREATE ROLE palimpsest LOGIN PASSWORD {}").format(sql.Literal(password)))
        conn.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        conn.execute("GRANT USAGE ON SCHEMA canonical_store, compiler_runtime TO palimpsest")
        conn.execute("GRANT SELECT, INSERT ON canonical_store.data, canonical_store.data_acquisitions TO palimpsest")
        conn.execute("GRANT SELECT, INSERT, UPDATE ON compiler_runtime.data_import_requests TO palimpsest")
        conn.execute("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA canonical_store, compiler_runtime TO palimpsest")
        conn.execute("CREATE TABLE compiler_runtime.schema_migrations (version text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        conn.execute("INSERT INTO compiler_runtime.schema_migrations(version,checksum) VALUES (%s,%s)", (MIGRATIONS[0],sources[MIGRATIONS[0]][1]))
        conn.execute("GRANT SELECT ON compiler_runtime.schema_migrations TO palimpsest")
        for pending in MIGRATIONS[1:]:
            migration, digest = sources[pending]
            conn.execute(migration, prepare=False)
            conn.execute("INSERT INTO compiler_runtime.schema_migrations(version,checksum) VALUES (%s,%s)", (pending,digest))
    return {"schema_version": MIGRATION_VERSION, "applied": True}


class PostgresRepository:
    def __init__(self, dsn):
        self._dsn = dsn

    def allocate_id(self):
        with connection(self._dsn) as conn:
            return str(conn.execute("SELECT uuidv7() AS id").fetchone()["id"])

    def get_request(self, request_id):
        with connection(self._dsn) as conn:
            return conn.execute("SELECT * FROM compiler_runtime.data_import_requests WHERE request_id=%s", (request_id,)).fetchone()

    def get_data(self, data_id):
        with connection(self._dsn) as conn:
            return conn.execute("SELECT * FROM canonical_store.data WHERE data_id=%s", (data_id,)).fetchone()

    def get_acquisitions(self, data_id):
        with connection(self._dsn) as conn:
            return conn.execute("SELECT * FROM canonical_store.data_acquisitions WHERE data_id=%s ORDER BY created_at, acquisition_id", (data_id,)).fetchall()

    def prepare(self, request_id, payload, fingerprint, metadata):
        values = dict(metadata, request_id=request_id, payload_sha256=payload.data_id,
                      byte_size=payload.byte_size, request_fingerprint=fingerprint)
        values["external_metadata"] = Jsonb(values["external_metadata"]) if values["external_metadata"] is not None else None
        with connection(self._dsn) as conn, conn.transaction():
            conn.execute("""INSERT INTO compiler_runtime.data_import_requests
                (request_id, request_fingerprint, payload_sha256, byte_size, media_type,
                 origin_uri, import_method, retrieved_at, original_name, external_metadata, actor_ref)
                VALUES (%(request_id)s,%(request_fingerprint)s,%(payload_sha256)s,%(byte_size)s,
                        %(media_type)s,%(origin_uri)s,%(import_method)s,%(retrieved_at)s,
                        %(original_name)s,%(external_metadata)s,%(actor_ref)s)
                ON CONFLICT (request_id) DO NOTHING""", values)
            row = conn.execute("SELECT * FROM compiler_runtime.data_import_requests WHERE request_id=%s FOR UPDATE", (request_id,)).fetchone()
            if row["request_fingerprint"] != fingerprint:
                raise PalimpsestError("idempotency_conflict", "같은 요청 ID의 입력이 변경되었습니다.", 6,
                                      {"request_id": request_id})
            return row

    def mark_published(self, request_id):
        with connection(self._dsn) as conn, conn.transaction():
            conn.execute("UPDATE compiler_runtime.data_import_requests SET state='staged', error_code=NULL, resolved_at=NULL WHERE request_id=%s AND state='failed'", (request_id,))
            conn.execute("UPDATE compiler_runtime.data_import_requests SET state='published' WHERE request_id=%s AND state='staged'", (request_id,))

    def mark_failed(self, request_id, code):
        with connection(self._dsn) as conn:
            conn.execute("UPDATE compiler_runtime.data_import_requests SET state='failed',error_code=%s,resolved_at=CURRENT_TIMESTAMP WHERE request_id=%s AND state IN ('staged','published')", (code, request_id))

    def mark_duplicate(self, request_id, data_id):
        with connection(self._dsn) as conn, conn.transaction():
            conn.execute("UPDATE compiler_runtime.data_import_requests SET state='staged',error_code=NULL,resolved_at=NULL WHERE request_id=%s AND state='failed'", (request_id,))
            conn.execute("""UPDATE compiler_runtime.data_import_requests SET state='duplicate',
                result_data_id=%s, error_code='duplicate_data',resolved_at=CURRENT_TIMESTAMP
                WHERE request_id=%s AND state IN ('staged','published')""", (data_id,request_id))

    def commit_import(self, request_id):
        with connection(self._dsn) as conn, conn.transaction():
            row = conn.execute("SELECT * FROM compiler_runtime.data_import_requests WHERE request_id=%s FOR UPDATE", (request_id,)).fetchone()
            if row["state"] == "committed":
                return row
            if row["state"] != "published":
                raise PalimpsestError("request_not_ready", "등록 요청이 게시 준비 상태가 아닙니다.", 7)
            data_id = row["payload_sha256"]
            inserted = conn.execute("""INSERT INTO canonical_store.data
                (data_id,media_type,byte_size,artifact_path,original_name)
                VALUES (%s,%s,%s,%s,%s) ON CONFLICT (data_id) DO NOTHING RETURNING data_id""",
                (data_id,row["media_type"],row["byte_size"],
                 f"objects/sha256/{data_id[:2]}/{data_id}",row["original_name"])).fetchone()
            if not inserted:
                return None
            acquisition = conn.execute("""INSERT INTO canonical_store.data_acquisitions
                (data_id,origin_uri,import_method,retrieved_at,original_name,external_metadata,actor_ref)
                VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING acquisition_id""",
                (data_id,row["origin_uri"],row["import_method"],row["retrieved_at"],row["original_name"],
                 Jsonb(row["external_metadata"]) if row["external_metadata"] is not None else None,
                 row["actor_ref"])).fetchone()
            return conn.execute("""UPDATE compiler_runtime.data_import_requests SET
                state='committed',result_data_id=%s,result_acquisition_id=%s,
                error_code=NULL,resolved_at=CURRENT_TIMESTAMP WHERE request_id=%s RETURNING *""",
                (data_id,acquisition["acquisition_id"],request_id)).fetchone()

    def doctor(self):
        with connection(self._dsn) as conn:
            version = conn.execute("SELECT current_setting('server_version') AS server_version, current_setting('server_version_num')::int AS server_version_num").fetchone()
            extension = conn.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()
            table = conn.execute("SELECT to_regclass('compiler_runtime.schema_migrations') AS name").fetchone()
            schema = conn.execute("SELECT version,checksum FROM compiler_runtime.schema_migrations ORDER BY version").fetchall() if table["name"] else []
            expected = [{"version": name, "checksum": migration_source(name)[1]} for name in MIGRATIONS]
            ready = (version["server_version_num"] // 10000 == 18 and extension is not None
                     and extension["extversion"] == "0.8.6"
                     and schema == expected)
            return {"ready":ready, **version, "pgvector_version":extension["extversion"] if extension else None,
                    "schema_version":schema[-1]["version"] if schema else None}
