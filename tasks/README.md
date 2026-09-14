# Task queue

T00 환경 inventory는 completed, T01 계약/profile 작업은 in_progress, T02–T12는 planned다. T13 GUI는 deferred이며 T12 뒤 사용자의 별도 착수 지시가 필요하다. U01–U09의 선택 범위는 확정이고 나머지 P01–P12의 미정 계약은 해당 task에서 확인한다. CLI는 T02부터 기능별로 구현한다. 각 단계의 domain/변환 모듈은 [MODULE_BOUNDARIES](../docs/implementation/MODULE_BOUNDARIES.md)를 따른다. 현재 결과는 [STATUS](../progress/STATUS.md)를 따른다.

## [T00](./T00.md) — CLI-first repository·MinerU 환경 inventory

상태: completed (inventory). 선행: 없음. 요구 P: 없음. 검증: AT64/AT88 문서·수동 확인, AT102 실제 doctor 미실행.

## [T01](./T01.md) — 사용자 변경 적용과 미정 계약 동결

상태: in_progress (모델·모듈·구조 수정과 U09 저장/ID·T02 SQL 초안 반영). 선행: T00. 요구 P: 없음. 검증: 5개, 앱 AT는 미실행.

## [T02](./T02.md) — CLI skeleton·Artifact Store·Data vertical slice

상태: planned. 선행: T01. 요구 P: P10, P12의 U09 범위 밖 미정 사항. 검증: 13개.

## [T03](./T03.md) — MinerU PDF·Execution·D2I·Information

상태: planned. 선행: T02. 요구 P: P01, P05, P10, P12의 승인 범위 밖 사항. 검증: 32개.

## [T04](./T04.md) — I2K·KNode·materiality·CAS

상태: planned. 선행: T03. 요구 P: P01, P04, P05, P06, P07, P12의 승인 범위 밖 사항. 검증: 20개.

## [T05](./T05.md) — I repair·K lifecycle·support revalidation

상태: planned. 선행: T04. 요구 P: P03, P04, P05, P06. 검증: 12개.

## [T06](./T06.md) — N2E·KEdge·Applicability

상태: planned. 선행: T05. 요구 P: P01, P02, P05, P06, P09. 검증: 15개.

## [T07](./T07.md) — Cap 없는 K2K·scheduler·quiescence

상태: planned. 선행: T06. 요구 P: P02, P03, P04, P05, P06, P07. 검증: 15개.

## [T08](./T08.md) — Retrieval·K2W·citation snapshots

상태: planned. 선행: T07. 요구 P: P02, P08, P09, P10, P12. 검증: 14개.

## [T09](./T09.md) — Confirmation·Decision W2K·decision trace

상태: planned. 선행: T08. 요구 P: P05, P06, P08, P10. 검증: 13개.

## [T10](./T10.md) — Parchment·Book·재수입 lineage

상태: planned. 선행: T09. 요구 P: P07, P08, P09, P10. 검증: 7개.

## [T11](./T11.md) — CLI human review·진행 상태·관리 흐름 완성

상태: planned. 선행: T10. 요구 P: P03, P08, P10, P12. 검증: 15개.

## [T12](./T12.md) — CLI release·MinerU 평가·복구·보안 gate

상태: planned. 선행: T11. 요구 P: P01, P03, P05, P07, P09, P10, P12의 승인 범위 밖 사항. 검증: 112개 spec_only.

## [T13](./T13.md) — GUI — CLI release 이후 마지막 단계

상태: deferred. 선행: T12. 요구 P: P12. 검증: 1개.

U08 적용 범위와 후속 선택 근거는 [ARCHITECTURE_FIXES](../docs/decisions/ARCHITECTURE_FIXES.md)를 따른다. AT106/AT107은 추가 정책 시나리오이며 실제 실행 전 spec_only다.

U09는 [STORAGE_IDENTITY](../docs/decisions/STORAGE_IDENTITY.md)를 따른다. PostgreSQL 최초 18/pgvector와 신규 ID·관리 등록·Runtime Record 보존은 확정되었으며 [T02 SQL 초안](../docs/schema/T02_STORAGE_SCHEMA.md)은 DB 미적용이다. 앱 언어/driver/migration runner·DB 실행 위치와 P10 전체 보존·삭제·backup은 미정이다. AT108–AT112의 명세 연결이 뒤 task의 구현 완료를 뜻하지 않는다.
