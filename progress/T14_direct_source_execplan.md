# I2K의 등록 원문 직접 근거 — 실행 계획

**중단·전제 철회:** 2026-09-13 사용자가 직접 D→K는 규약에 없는 D2K이며 허용하지 않는다고 정정했다. 아래는 폐기된 초안 기록이다. [최신 I-only/오류 보고 결정](../docs/decisions/I2K_INFORMATION_ERRORS.md)과 [대체 실행 계획](T14_source_issues_execplan.md)을 따른다. DB/provider 실행 전 초안을 중단했고 이번 턴의 code/schema 변경을 복원했다. 아래 계획을 현재 승인으로 해석하지 않는다.

2026-09-13 사용자 지시: 다음 구현을 계속하고, 먼저 현재 전체 코드가 agent context에 들어가는지 설명한다. 기존0.13의 다음 미완성인 직접 D canonical grounding을 첫 수직 범위로 선택한다. [승인된 직접 D 계약](../docs/decisions/I2K_DIRECT_SOURCE_EVIDENCE.md), [전체 I 검토](../docs/decisions/FULL_SOURCE_LLM_SELECTION.md), [I2K source-only](../docs/decisions/I2K_SOURCE_ONLY_K2K_INFERENCE.md), [이전 결과](../output/t13-code-review-wiki/REPORT.md)를 따른다.

## 목표와 경계

등록 원문 UTF-8 텍스트/코드 dossier에서 확인한 정확 구간을 I2K의 추가 증거로 전달·독립 검증하고, I를 만들거나 바꾸지 않은 채 KRevision에 직접 D grounding과 source 품질 이력을 원자적으로 저장한다. 기존 전체 I packet과 실제 원본 요청을 유지한다. I는 없는 근거의 대용 FK로 쓰지 않는다. 새 결론은 K2K만 만든다. K 검증과 source 누락/불일치 품질 문제의 해소를 분리한다.

첫 형식은 exact UTF-8 원문 byte/char/line이다. Code dossier도 등록된 동일 D의 원문 bytes를 읽는다. native PDF 전달은 현재 provider가 미지원하므로 준비·미지원 이유를 보존하며 이 범위의 성공으로 가장하지 않는다. retained page image를 native PDF 전달이라고 기록하지 않는다. PDF/MinerU source 실행·원문·I/profile/SQL0001–0013은 재작성하지 않는다.

## 구현 계약

- 기존 multi-source I2K profile의 opt-in `direct_source_evidence` capability와 구현 hash를 추가한다. 이전 profile/input/receipt JSON은 그대로 해석한다. 원래 `input`은 변경하지 않고 `input_snapshot.direct_sources`에 application-owned snapshot을 붙인다.
- immutable prepared original source는 UUIDv7 evidence_id, 원래 k_source_requests/request execution, 선택 source execution, registered raw D SHA/size/type, exact UTF-8 excerpt/locator/hash, 실제 조회 출발 I/question을 가진다. model은 임의 원본 경로나 evidence snapshot을 작성할 수 없다.
- candidate는 실제 I `evidence`와 별도 `direct_evidence`를 가진다. 둘 중 하나 이상의 검증 가능한 실제 근거가 필수다. direct-only 후보에 가짜 I citation을 만들지 않는다. direct source 주소 검토 target은 information_id=null인 명시적 D target으로 전체 기존 I target에 추가한다.
- Generator/Validator prompt/schema/전달 receipt 모두 exact direct evidence IDs/hash와 결속한다. 원본 제공·사용·검증, 이전 unavailable 요청, source 품질 분류/보류 이력을 구분한다.
- additive0014로 immutable 원문 inspection/input binding/직접 K grounding/품질 판정을 추가한다. accepted Record의 실제 I+D 전체 근거를 commit/source-scope/version/derivation closure가 검사한다. I2K origin은 source-created이며 K2K origin은 actual premises를 보존한다. 같은 의미 reuse는 기존 Revision에 새 근거만 추가한다.
- 조회는 실제 직접/전이 D 근거를 구분한다. current source/version의 완전한 accepted support route가 필요하며 I+D 혼합 경로의 다른 D를 누락하지 않는다. Wiki/query/읽기 UI도 직접 원문 citation과 추론 citation을 구별한다.

## 소유권과 실행 순서

Root는 공통0014 SQL, KnowledgeRuntime/source preparation service, request/CLI 연결과 최종검증을 소유한다. pure source/candidate/review contract 및 downstream조회 모듈은 구체 API를 공유한 후 독립 agent에 분리한다. fixture DB 테스트는 단일 소유자가 순차 실행하고 기존 실제 code/paper DB는 migration 대상으로 사용하지 않는다. 실제 provider 호출은 필요할 때 구체 요청 파일과 기존 승인 범위를 대조하며 mock 결과를 live라고 하지 않는다.

1. 원문 snapshot/locator/citation과 full-I+D review 계약·거부 시나리오.
2. 추가 SQL/Runtime 준비·전달·판정·reuse·실패 원자성 및 source issue 영속화.
3. 정확 K2K/버전/provenance, 선택된 Wiki/query와 원문 조회 연결.
4. 별도 fixture/recovery DB에서 실제 PG 및 read-only 이력/CLI/e2e 검사, image와 전체회귀. 본문/설정/규약/진행 보고서를 갱신한다.

## 검증

wrong D/request/source execution, 잘못된 byte·UTF-8 경계/CRLF/BOM, 유효범위의잘못된인용, snapshot/receipt/input변조, 미전달/미검증, 허위I, source scope이탈, I+D혼합버전근거누락, 동시prepare/replay/stalehead, commit failpoint와retry, 추가근거시Revision0증가, K2K직접I/D0, downstream정확원문예외표시를 검사한다. I2K/조회 과정의 D2I/source 재조립 호출0과 I/원문 불변성도 검사한다.

## 현황

읽기 전용 코드 크기 측정과 source/consumer contract audit를 완료했다. 전체 코드가현재context에실제로들어있지않음을사용자에게설명했다. 이번범위의code/SQL/provider/DB변경·테스트는아직시작전이다.
