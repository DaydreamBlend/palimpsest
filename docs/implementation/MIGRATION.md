# 기존 구현이 있을 때의 migration 계획

> 상태: PLAN. 기존 운영 DB의 schema/migration은 확인하지 않았습니다. U09에 따른 새 테스트 DB용 [T02 SQL 초안](../schema/T02_STORAGE_SCHEMA.md)은 별도로 있으며 미적용 상태입니다. 기존 DB의 upgrade/cutover migration으로 사용하지 않습니다.

## Inventory와 보존

old Source/Data/Information/Knowledge/Note/Run schema를 읽고 exact ID/FK/provenance 및 user files를 inventory합니다. deprecated 이름이 있다고 즉시 drop하지 않습니다. D hash와 accepted semantic payload의 export/backup을 검증한 후 mapping을 작성합니다.

## 특히 확인할 변환

Source layer→D/acquisition, Note→Parchment, InformationRevision→immutable I와 supersession, separate candidate/review objects→runtime Record/workspace, content-only Decision dedup→event identity, lifetime D2I once→logical generation, endpoint-only EdgeRevision→historical preservation + future applicability route, bounded propagation config→no semantic cap + explicit partial state.

기존 accepted record에 exact grounding이나 actor confirmation이 없다면 이를 새로 만들어낸 것처럼 backfill하지 않습니다. legacy 상태와 확인 불가능 범위를 표시하고 필요한 자료/검증을 별도 migration gate로 둡니다. invalidated/history ref를 새 current I/K로 일괄 치환하지 않습니다.

## 안전한 순서

read-only mapping/report → new schema/compatibility columns → fixture migration rehearsal → exact provenance assertions → staged backfill → approved cutover → old read compatibility/rollback window → 별도 승인된 cleanup 순서입니다.

materiality/fingerprint canonicalization version을 바꾸면 새 key namespace와 비교 mapping이 필요합니다. semantic identity를 조용히 전역 재해시해 object ID를 바꾸지 않습니다. source-specific I를 유지하면서 동일 K 근거를 연결합니다.

## 예전 cap으로 끝난 작업

과거 max_depth/max_records 등으로 “성공” 처리했던 job은 새 의미의 quiescence를 증명하지 못합니다. 해당 기록을 과거 실행 결과로 보존하고 명시적인 revalidation/recompile 대상으로 분류할 수 있습니다. 과거 전 작업을 자동 재실행하지 않습니다. 사용자 허가와 current input snapshot을 확인합니다.

## Release/rollback

검증 실패 시 old DB/원본 복구 또는 feature flag fallback을 사용합니다. destructive migration, irreversible canonical ID merge, cleanup은 별도 승인 없이는 수행하지 않습니다. 기존 DB의 실제 schema를 확인하기 전에는 새 테스트 DB 초안을 기존 데이터에 적용하지 않습니다.


## U03 — 이름만 바꾸는 migration

Horreum → Artifact Store / `artifact_store`; Bibliotheca → Canonical Store / `canonical_store`; Scriptorium → Compiler Runtime / `compiler_runtime`. `horreum_path` → `artifact_path`.

현재 docs/canonical과 새 코드 예시에는 새 이름을 쓴다. archived source/review의 과거 이름은 그 당시 근거이므로 보존한다. 이미 존재하는 `bibliotheca.*`/`scriptorium.*` SQL namespace나 root directories를 이 문서만 보고 drop/rename하지 않는다. schema-qualified views/FKs/functions/jobs/permissions/config와 external clients를 조사하고 호환 alias 또는 migration 계획을 선택한다.

사용자 파일의 물리 path, artifact bytes, D/I/K/W/P/B IDs, semantic payload와 과거 fingerprint envelopes를 이름 변경 때문에 재작성하지 않는다. historical fingerprint domain string도 보존한다. 새로운 envelope version이 필요하면 기존 identity와 명시적 mapping을 남기며 duplicate object를 만들지 않는다. backup과 rollback proof 뒤에 cutover한다.

## MinerU 도입과 기존 파싱 결과

기존 다른 parser 결과는 historical provenance로 유지한다. 새 PDF parsing 요청은 MinerU adapter로 처리하고, 과거 D를 다시 파싱할 때는 explicit recompile generation을 사용한다. 예전 I anchor를 MinerU output offset으로 조용히 치환하지 않는다. source-specific I와 supersession/validation 절차를 유지한다.

## 기존 GUI

기존 GUI 코드가 있다면 삭제하지 않고 동결한다. 핵심 application service를 CLI에서 재사용하도록 분리하되 GUI 로직을 새로 확장하지 않는다. T12 검증 후 T13에서 다시 연결한다.

## U09 — 신규 ID와 PostgreSQL 업그레이드

신규 data_id는 보존한 원본 bytes의 SHA-256, 그 밖의 신규 opaque ID는 UUIDv7이다. 이 선택으로 과거 ID/hash를 다시 발급하거나 기존 FK를 일괄 교체하지 않는다. 기존 DB가 있다면 mapping/호환 참조와 실제 원본 무결성을 먼저 검증한다. 평범한 중복 import는 새 Data/acquisition을 만들지 않으며, 별도 출처 기록과 동일 성공 request의 재시도는 구분한다. [저장 계약](../decisions/STORAGE_IDENTITY.md)을 따른다.

최초 PostgreSQL 18/pgvector에서 향후 19 이상으로 전환할 때 새 major용 extension binary, backup/restore, pg_upgrade 또는 dump/restore와 앱의 제약·동시성·복구 검증을 별도 테스트 사본에서 수행한다. source DB/data directory를 새 major로 바로 열거나 자동 latest 전환하지 않는다. 실제 업그레이드 경로와 실행 위치는 아직 미정이며 SQL 초안의 존재가 실행 승인을 대신하지 않는다.
