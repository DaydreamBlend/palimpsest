# CLI-first 구현 로드맵

> U01: GUI는 마지막. U02: PDF는 MinerU. U03: 영어 구성요소명. P01–P12의 미승인 설계는 별도다.

후속 U04/U05의 모델·버전 정책과 U06의 단계별 모듈화를 적용한다. 각 단계는 [MODULE_BOUNDARIES](MODULE_BOUNDARIES.md)의 해당 domain/변환 모듈 및 독립 테스트를 함께 구현한다. 전체 미래 모듈을 빈 패키지로 미리 만들거나 각 모듈을 별도 DB/서비스로 분리하지 않는다.

## 1. T00/T01 — 조사와 계약

실제 repository/toolchain/test 상태를 확인한다. CLI 우선, MinerU 사용, 새 이름은 재승인 대상이 아니다. 나머지 P 계약과 실제 MinerU version/backend/hardware profile, CLI detailed contract를 확정한다. existing frontend가 있어도 지우지 않고 개발 범위에서 동결한다.

## 2. T02 — CLI를 처음부터 만든다

help/version/doctor, Data import/show/verify를 Artifact Store와 Canonical Store에 연결한다. browser/display/GUI dependency 없이 실제 파일·DB 기반 small slice를 검증한다. CLI를 마지막에 덧붙이는 계획이 아니다.

## 3. T03 — MinerU PDF → D2I → I

로컬 MinerU adapter, parser artifacts/page coverage/anchor, execution/proposal/validation 경계를 구현한다. compile data, jobs status, information show를 CLI로 제공한다. 실제 parser smoke와 mock semantic generation을 구분해 기록한다.

## 4. T04–T07 — K와 cap 없는 propagation

I2K/Node → support·repair·lifecycle → N2E/Edge/applicability → K2K/scheduler 순서로 확장한다. 각 stage를 CLI로 호출하고 exact provenance/partial/blocked/resume을 관찰할 수 있게 한다. no-material branch stopping과 operational resource controls를 혼동하지 않는다.

## 5. T08–T10 — query·decision·publication

CLI query와 citation inspection, explicit decision confirmation/trace, Parchment/Book compose/export를 연결한다. authority는 GUI 클릭을 전제로 하지 않으며 CLI에서도 실제 actor와 exact payload에 결합된 evidence를 요구한다.

## 6. T11 — CLI review·운영 완성

human review, provenance inspection, job pause/resume/cancel, 실패 처리와 noninteractive automation을 통합한다. 여기서 web/desktop GUI를 시작하지 않는다. T02부터 존재한 command들을 실제 end-to-end 사용자 workflow로 완성한다.

## 7. T12 — CLI release gate

headless e2e, pinned MinerU 실제 PDF parsing, PostgreSQL integration, restore/crash/redelivery, security와 semantic eval을 검증한다. mock·문서 검사·live 결과를 별도로 보고한다. GUI 미구현은 이 gate의 실패 사유가 아니다.

## 8. T13 — GUI는 마지막

초기 상태 deferred. T12 완료와 이후 사용자의 GUI 착수 지시를 모두 확인한 후에만 진행한다. 그때 framework/화면/API 필요성을 결정하고 이미 검증된 application services를 재사용한다. T00–T12는 T13에 의존하지 않는다.

## 병렬 작업

shared schema/effect/migration은 동시에 수정하지 않는다. interface 확정 후 독립 adapter/tests/read-only review를 병렬화할 수 있다. GUI 작업을 병렬화 명목으로 앞당기지 않는다.
