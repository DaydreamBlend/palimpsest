"""Data registration coordinates the filesystem and durable PostgreSQL journal."""

from pathlib import Path
import mimetypes

from . import data
from .errors import PalimpsestError


class DataService:
    def __init__(self, repository, artifact_store, actor_ref="local", checkpoint=None):
        self.repository = repository
        self.artifact_store = artifact_store
        self.actor_ref = actor_ref
        self.checkpoint = checkpoint or (lambda name, request_id: None)

    def _authorize(self, row):
        if row and row["actor_ref"] != self.actor_ref:
            raise PalimpsestError("permission_denied", "다른 actor의 등록 요청은 처리할 수 없습니다.", 5)

    @staticmethod
    def _result(row, replayed=False):
        return {"request_id":str(row["request_id"]), "data_id":row["result_data_id"],
                "acquisition_id":str(row["result_acquisition_id"]) if row["result_acquisition_id"] else None,
                "state":row["state"], "replayed":replayed}

    def import_file(self, path, request_id=None, media_type=None, origin_uri=None, on_request_id=None,
                    *, storage_segments=None, expected_data_id=None, realm_registration=None):
        source = Path(path)
        request_id = data.request_id(request_id) if request_id else self.repository.allocate_id()
        if on_request_id:
            on_request_id(request_id)
        metadata = {"media_type":media_type or mimetypes.guess_type(source.name)[0] or "application/octet-stream",
                    "origin_uri":origin_uri,"import_method":"cli","retrieved_at":None,
                    "original_name":source.name,"external_metadata":None,"actor_ref":self.actor_ref}
        if not metadata["media_type"].strip():
            raise PalimpsestError("invalid_media_type", "media type은 비어 있을 수 없습니다.", 2)
        if storage_segments is not None and metadata['media_type'] != 'text/markdown':
            raise PalimpsestError('unsupported_segmented_import', '이번 분할 등록은 Markdown 원문을 지원합니다.', 2)
        with self.artifact_store.request_lock(request_id):
            existing = self.repository.get_request(request_id)
            self._authorize(existing)
            if realm_registration is not None:
                from .realm_registration import validate_registration
                # The trusted coordinator resolves selection under this same
                # request lock, so concurrent retries freeze one UUID/snapshot.
                selection = realm_registration() if callable(realm_registration) else realm_registration
                selection = validate_registration(selection)
                if selection['actor'] != self.actor_ref:
                    raise PalimpsestError('permission_denied', '등록 actor와 Realm 선택 actor가 일치해야 합니다.', 5)
                metadata['external_metadata'] = {'realm_registration': selection}
            terminal = existing and existing["state"] in ("committed", "duplicate")
            if terminal:
                self.artifact_store.cleanup(request_id)
            try:
                payload = self.artifact_store.stage(source, request_id)
                if expected_data_id is not None and payload.data_id != data.data_id(expected_data_id):
                    raise PalimpsestError('source_changed', '검증한 snapshot과 등록할 원문 bytes가 달라졌습니다.', 6)
                if storage_segments is not None:
                    from .segmented_artifact_store import validate_segments, PROFILE
                    segments = [list(span) for span in validate_segments(storage_segments, payload.byte_size)]
                    metadata['external_metadata'] = {**(metadata['external_metadata'] or {}),
                        'storage_request': {'profile': PROFILE, 'segments': segments}}
                self.checkpoint("after_stage", request_id)
                row = self.repository.prepare(request_id, payload, data.fingerprint(payload,metadata), metadata)
                self.checkpoint("after_prepare", request_id)
                return self._finish(row)
            finally:
                # Terminal receipts no longer need staging, including invalid retries.
                # Prepared requests retain their original bytes for recovery.
                if terminal:
                    self.artifact_store.cleanup(request_id)

    def _duplicate(self, row):
        request_id, data_id = str(row["request_id"]), row["payload_sha256"]
        canonical = self.repository.get_data(data_id)
        if canonical is None or canonical["byte_size"] != row["byte_size"]:
            raise PalimpsestError("integrity_conflict", "기존 Data 크기가 등록 기록과 다릅니다.", 6)
        self.artifact_store.verify(data_id, row["byte_size"])
        self.repository.mark_duplicate(request_id, data_id)
        self.artifact_store.cleanup(request_id)
        raise PalimpsestError("duplicate_data", "이미 등록된 동일 Data입니다.", 6,
                              {"request_id":request_id,"data_id":data_id,"state":"duplicate"})

    def _finish(self, row):
        request_id, data_id = str(row["request_id"]), row["payload_sha256"]
        try:
            if row["state"] == "committed":
                self.artifact_store.verify(data_id, row["byte_size"])
                self.artifact_store.cleanup(request_id)
                return self._result(row, True)
            if row["state"] == "duplicate" or self.repository.get_data(data_id):
                return self._duplicate(row)
            try:
                staged = self.artifact_store.staged(request_id)
            except PalimpsestError as error:
                if error.code != "staging_missing":
                    raise
                # A published object can survive after staging/response loss.
                self.artifact_store.verify(data_id, row["byte_size"])
            else:
                if staged != data.Payload(data_id, row["byte_size"]):
                    raise PalimpsestError("integrity_conflict", "준비된 파일이 등록 기록과 다릅니다.", 6)
                storage = (row.get('external_metadata') or {}).get('storage_request')
                if storage is None:
                    self.artifact_store.publish(request_id, data_id, row["byte_size"])
                else:
                    from .segmented_artifact_store import PROFILE
                    if storage.get('profile') != PROFILE or row['media_type'] != 'text/markdown':
                        raise PalimpsestError('invalid_storage_request', '저장 요청의 분할 profile을 확인하세요.', 4)
                    self.artifact_store.publish(request_id, data_id, row['byte_size'], segments=storage['segments'])
            self.checkpoint("after_publish", request_id)
            self.repository.mark_published(request_id)
            self.artifact_store.verify(data_id, row["byte_size"])
            result = self.repository.commit_import(request_id)
            if result is None:
                return self._duplicate(row)
            self.checkpoint("after_commit", request_id)
            self.artifact_store.cleanup(request_id)
            return self._result(result)
        except PalimpsestError as error:
            if error.code != "duplicate_data":
                try:
                    self.repository.mark_failed(request_id, error.code)
                except PalimpsestError:
                    pass  # Durable prepared state remains recoverable during DB outages.
            raise

    def request_status(self, request_id):
        request_id = data.request_id(request_id)
        row = self.repository.get_request(request_id)
        if row is None:
            raise PalimpsestError("request_not_found", "준비된 등록 요청을 찾을 수 없습니다.", 4,
                                  {"request_id":request_id})
        self._authorize(row)
        return {**self._result(row), "payload_sha256":row["payload_sha256"],
                "byte_size":row["byte_size"],"error_code":row["error_code"]}

    def import_code_snapshot(self, directory, request_id=None, on_request_id=None, *, realm_registration=None):
        from .code_snapshot import verify, storage_segments
        manifest = verify(directory)
        return self.import_file(Path(directory) / 'dossier.md', request_id=request_id,
            media_type='text/markdown', origin_uri='palimpsest:codebase-snapshot:sha256:' + manifest['dossier_sha256'],
            on_request_id=on_request_id, storage_segments=storage_segments(manifest),
            expected_data_id=manifest['dossier_sha256'], realm_registration=realm_registration)

    def recover(self, request_id):
        request_id = data.request_id(request_id)
        with self.artifact_store.request_lock(request_id):
            row = self.repository.get_request(request_id)
            if row is None:
                raise PalimpsestError("request_not_found", "준비된 등록 요청이 없습니다. 원본과 같은 요청 ID로 다시 등록하십시오.", 4,
                                      {"request_id":request_id})
            self._authorize(row)
            return self._finish(row)

    def show(self, data_id):
        data_id = data.data_id(data_id)
        row = self.repository.get_data(data_id)
        if row is None:
            raise PalimpsestError("data_not_found", "등록된 Data를 찾을 수 없습니다.", 4)
        return {**row,"acquisitions":self.repository.get_acquisitions(data_id)}

    def verify(self, data_id):
        row = self.show(data_id)
        return self.artifact_store.verify(data_id,row["byte_size"])

    def doctor(self):
        try:
            database = self.repository.doctor()
        except PalimpsestError as error:
            database = {"ready":False,"error_code":error.code}
        store = self.artifact_store.doctor()
        return {"ready":bool(database["ready"] and store["ready"]), "database":database,
                "artifact_store":store,"parser":{"name":"MinerU Hybrid + Pro high","ready":False,"status":"not_probed"},
                "warnings":["외부 Docker 파서의 준비 상태는 이 진단에서 검사하지 않습니다. Data 등록은 파싱 완료를 뜻하지 않습니다."]}
