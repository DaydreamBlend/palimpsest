# Acceptance catalog

> 아래 112개는 Given/When/Then 명세다. 현재 catalog는 9 passed/28 partially_tested/75 spec_only이며, [T02 실행 근거](../../progress/T02_execplan.md)와 [T03 회귀·실제 실행 근거 및 한계](../../progress/T03_execplan.md)를 따른다. 최종 앱 이미지의 139개 회귀가 통과했고 native-text PDF 1건의 실제 D→D2I→I 실행을 완료했다. 전체 T03 gate는 미완료이며, 단일 모델 판정·입력 coverage나 package validator 통과가 모든 PDF/LLM 품질과 의미적 완전성을 입증하지 않는다.


실제 실행 범위: MinerU 3.4.5/pipeline/adapter `mineru-middle-v2`, 로컬 parser network=none으로 native-text PDF 14페이지를 처리했다. Generator `d2i-generator-v2`와 Validator `d2i-validator-v3`는 Codex OAuth의 `gpt-5.6-terra`/medium을 서로 다른 thread에서 사용했고 동일한 source/proposal digest를 기록했다. 각 호출에 249 blocks와 63 images를 제공하여 29개 후보 중 28개를 승인하고 1개를 기각했다. 조회된 Information은 text 23개/image 5개, grounding은 51개다. 미참조 source block 205개이며 전체 의미 추출의 완전성은 보장하지 않는다. [최종 job receipt](../../output/t03/job_result.json), [Information 조회](../../output/t03/information.json), [원문 preflight](../../progress/T03_source_preflight.json), [실물 QA의 최초 발견 기록](../../progress/T03_parser_observations.json)을 근거로 하며 scanned/OCR 등 다른 유형과 미승인 원격 전송 차단은 별도 검증이 필요하다.

U01–U10은 적용된 사용자 요구이며, P01–P12의 제안 세부사항은 별도 승인 후 적용한다. mock, 실제 MinerU, PostgreSQL integration, headless e2e, live semantic eval을 구분한다.

U08 적용 사례와 선택 대기는 [해결 계약](../../docs/decisions/ARCHITECTURE_FIXES.md) 및 acceptance_catalog.json의 user_override_dependencies를 함께 따른다.

## AT01 — 깊이·크기 cap 없는 material chain

Given: 128단계 material chain과 100001 fanout을 생성 가능한 synthetic fixture

When: worker를 충분한 batch로 진행

Then: depth/record 수 때문에 정상 완료로 잘리지 않고 모든 필수 target의 처리 여부가 receipt에 남음

제안 의존성: P03. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT02 — no-material branch barrier

Given: A→B→C에서 A는 material, B는 동일 semantic/validity

When: B 재검증 commit

Then: B Revision 없음; B에서 새 C semantic job 없음; 다른 parent obligation은 보존

제안 의존성: P03. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT03 — RAG 밖의 필수 dependency

Given: B가 exact dependent이나 retrieval top-K 밖

When: A가 material 변경

Then: paged dependency enumeration으로 B를 예약; discovery 결과가 B를 누락시켜도 의무 검증은 실행

제안 의존성: P03. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT04 — 거짓 quiescence 방지

Given: ready queue는 비었지만 outbox/lease/human/dependency obligation 중 하나 존재

When: completion 계산

Then: quiescent가 아니며 미완료 이유와 refs를 반환

제안 의존성: P03. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT05 — 비수렴은 성공이 아님

Given: stable input에서 A→B→A oscillation 또는 반복 provider failure

When: anomaly 조건 충족

Then: suspended_anomaly/명시적 failure; 남은 obligation 보존; resume 후 freshness 확인

제안 의존성: P03. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT06 — 누적 작은 변화

Given: accepted 수치 1.0, 연속 작은 delta 후보들

When: 각 candidate 판정

Then: 직전 rejected candidate가 아니라 accepted 1.0 기준 비교; policy 경계 이후 material 판정 가능

제안 의존성: P01. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT07 — 중요 필드 변화

Given: polarity/quantifier/scope/action/step order가 달라진 후보

When: materiality 검증

Then: 문자열 유사도가 높아도 중요 차이를 보존; 임의 epsilon으로 무시하지 않음

제안 의존성: P01. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT08 — paraphrase revision 금지

Given: semantic payload가 같은 문체만 다른 후보

When: compiler 완료

Then: semantic Revision 없음; non-material/none; 필요한 Record는 남음

제안 의존성: P01. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT09 — EffectiveEdgeRef exact replay

Given: E1의 original=A1/B1, applicable=A2/B1

When: C와 W가 E1을 사용

Then: 실제 A2/B1과 applicability basis ref를 저장; replay에 A1로 치환하지 않음

제안 의존성: P02. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT10 — 재검증 후 projection key

Given: E1 semantic은 같지만 A1→A2

When: embedding projection 준비

Then: effective pair/profile별 새 projection; E1 semantic Revision은 추가되지 않음

제안 의존성: P02. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT11 — historical endpoint 불변

Given: E1 original A1/B1과 새 applicability event

When: current/history read

Then: original endpoint는 A1/B1 그대로; current effective read만 A2/B1

제안 의존성: P02. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT12 — endpoint 값 소비 dependency

Given: C가 E1을 통해 A1의 값 5를 소비

When: A2 값 10, supports 관계 유지

Then: C가 A material change의 direct obligation에 포함; edge unchanged만으로 C 검증 취소 금지

제안 의존성: P02. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT13 — 관계만 소비한 branch

Given: consumer가 검증된 동일 relation projection만 소비

When: valid→valid endpoint rebasing

Then: 새 semantic cascade/Revision 없음; maintenance receipt는 허용

제안 의존성: P02. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT14 — 최신 negative 우선

Given: current pair가 initial pair와 같고 최신 exact-pair 판정은 not_applicable

When: current edge read

Then: initial endpoint equality로 edge를 부활시키지 않음

제안 의존성: P02. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT15 — endpoint lifecycle 검사

Given: edge lifecycle usable지만 endpoint 하나 invalidated

When: current graph 조회

Then: 기본 reasoning edge 제외; history 조회는 명시적으로 원래 snapshot 제공

제안 의존성: P02. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT16 — pending은 false가 아님

Given: E pending_revalidation, consumer가 해당 edge 필요

When: consumer 실행 후 E applicable

Then: consumer는 blocked 후 release; pending 부재를 근거로 invalidation하지 않음

제안 의존성: P02. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT17 — 반복 negative impact

Given: 이미 confirmed false인 exact pair

When: 같은 not_applicable 재전달

Then: 새 material delta 없음; 중복 downstream enqueue 없음

제안 의존성: P02. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT18 — no-material support 교체

Given: I1→K1; I2 supersedes I1; K1 의미 유지

When: I2로 재검증

Then: K Revision 없음; origin I1 보존; current receipt/dependency는 I2 보존

제안 의존성: P04. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT19 — 교체 근거의 다음 invalidation

Given: AT18 완료 상태

When: I2 invalidated

Then: K1이 직접 영향 대상에 포함; origin I1만 조회해 누락하지 않음

제안 의존성: P04. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT20 — grounding-only 변화

Given: current K와 동일 의미의 새 검증된 I

When: support 추가

Then: grounding append+projection maintenance; semantic Revision과 불필요한 cascade 없음

제안 의존성: P04. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT21 — 문장 불변·support 상실

Given: 유일한 usable support가 사라짐

When: K 재검증

Then: 지원 상태/lifecycle 효과를 검증; 실제 상태 변화가 material이면 dependent 재검증

제안 의존성: P04. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT22 — cross-Data I 동문 중복

Given: D1/D2에서 같은 semantic 문장

When: 각 D2I commit

Then: I1/I2 별도 canonical ID와 Data grounding; K 통합은 별도

제안 의존성: P01. 사용자 요구: baseline/P contract. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_information.py](../../tests/app/test_information.py), [tests/app/test_information_integration.py](../../tests/app/test_information_integration.py).

검증 범위·한계: 다른 Data의 identity/context FP 구분과 cross-Data FK 거부를 검증했다. 같은 문장을 두 Data에서 각각 승인하는 DB 시나리오는 미실행이다.


## AT23 — 동일 D/locus I reuse

Given: 같은 D와 stable anchor 및 semantic payload

When: retry 또는 같은 generation candidate

Then: 동일 I reuse; 횟수만큼 새 I 생성 금지

제안 의존성: P01. 사용자 요구: baseline/P contract. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_information_integration.py](../../tests/app/test_information_integration.py).

검증 범위·한계: 동일 작업의 start/propose/decide 재생과 동시 요청의 canonical effect 한 번만 반영을 검증했다. 같은 generation의 별도 동등 후보에 대한 I reuse는 미검증이다.


## AT24 — historical duplicate

Given: current K=A2, candidate content는 historical A1 또는 invalidated K

When: FP lookup

Then: current eligibility 확인 없이 재활성/current pointer 이동 금지

제안 의존성: P01. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT25 — corrected grounding 재검증

Given: bad locator 후보를 기각한 뒤 같은 문장에 good locator

When: suppression precheck

Then: bad locator의 content-only global key가 good candidate를 막지 않음

제안 의존성: P01. 사용자 요구: baseline/P contract. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_information.py](../../tests/app/test_information.py).

검증 범위·한계: corrected anchor가 identity/context FP를 바꾸는 단언을 실행했다. 실제 suppression precheck와 corrected locator 재검증 흐름은 미실행이다.


## AT26 — validation context 변경

Given: same candidate이나 relevant counterevidence/state token 변경

When: precheck

Then: 새 frozen context로 재검증; unrelated timestamp만 바뀌면 동일 work 유지

제안 의존성: P01. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT27 — provider 오류는 지식 기각 아님

Given: provider timeout/response decoding failure

When: 실행 결과 저장

Then: execution failed/retry state; rejected semantic suppression 기록을 만들지 않음

제안 의존성: P01. 사용자 요구: baseline/P contract. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_codex_provider.py](../../tests/app/test_codex_provider.py), [tests/app/test_d2i.py](../../tests/app/test_d2i.py), [tests/app/test_information_integration.py](../../tests/app/test_information_integration.py).

실물 근거: [output/t03/job_result.json](../../output/t03/job_result.json), [output/t03/information.json](../../output/t03/information.json).

검증 범위·한계: mock timeout/response decoding 오류, D2I 기술 실패 전파와 실제 PG의 미판정 Record·후보 보존·같은 작업 재시도를 검증했다. 실제 host worker의 provider 실패부터 durable 실패 기록까지 연결한 장애 시험은 미실행이다. 실제 실행의 초기 parser/runtime 및 invalid_candidate 기술 실패도 failed 이력으로 보존했고 그 시점 I/semantic rejected Record를 만들지 않았다. 이후 별도 수정 profile의 성공과 구분한다.

## AT28 — target CAS 경쟁

Given: 두 worker가 같은 base에서 서로 다른 Revision 후보

When: concurrent commit

Then: 하나만 current CAS 성공; 다른 것은 새 base로 재검증; lost update 없음

제안 의존성: P05. 사용자 요구: U08, U09. 구현/실행 상태: spec_only / 미실행.

## AT29 — input freshness 경쟁

Given: Validator 실행 중 input I가 invalidated; target base 불변

When: commit

Then: target CAS만으로 승인 금지; stale read-set 감지 후 재검증; freshness 검사 이후 commit 이전의 동시 input 변경도 충돌 검출

제안 의존성: P05. 사용자 요구: U08, U09. 구현/실행 상태: spec_only / 미실행.

## AT30 — canonical commit 원자성

Given: revision/provenance/Record/outbox/candidate 각 단계 failpoint

When: 각 failpoint crash

Then: 부분 canonical effect 없음; retry 결과와 기존 accepted state 일관

제안 의존성: P05. 사용자 요구: U08, U09. 구현/실행 상태: spec_only / 미실행.

## AT31 — outbox redelivery

Given: producer commit 후 ACK 전 crash

When: event 재전달

Then: canonical effect/downstream work의 duplicate 없음

제안 의존성: P05. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT32 — lease 복구

Given: worker가 lease 획득 후 crash

When: lease 만료와 새 worker claim

Then: 작업 유실 없음; stale worker의 뒤늦은 ACK가 새 결과를 덮지 않음

제안 의존성: P05. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT33 — multi-proposal/zero-output

Given: 한 호출에서 3 proposals 또는 0 proposal

When: execution fan-out

Then: 3개 Record가 same batch 공유; zero-output은 execution log에 정상 보존; FP unique 충돌 없음

제안 의존성: P05. 사용자 요구: baseline/P contract. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_information.py](../../tests/app/test_information.py), [tests/app/test_d2i.py](../../tests/app/test_d2i.py), [tests/app/test_information_integration.py](../../tests/app/test_information_integration.py).

실물 근거: [output/t03/job_result.json](../../output/t03/job_result.json), [output/t03/information.json](../../output/t03/information.json).

검증 범위·한계: 다중 후보 판정 coverage, 같은 execution 내 Record 처리, zero-output의 로그 보존 및 Record/I 미생성을 검증했다. 실제 한 Generator 호출에서 29 proposals를 같은 execution의 29 Records로 처리하여 28 accepted/1 rejected를 남겼다. zero-output 근거는 합성 회귀이다.

## AT34 — multi-root fan-in

Given: 서로 다른 root가 같은 effective-input job을 요청

When: 작업 coalesce

Then: 실행 공유 가능; 두 root의 원인과 completion obligation 모두 보존

제안 의존성: P05. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT35 — split replacement 실패

Given: I1을 I2+I3으로 분리, I3 실패

When: I2 결과 처리

Then: I1을 불완전 replacement로 조기 retire하지 않음; partial 활성화 규칙 준수

제안 의존성: P05. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT36 — merge/generation 재시도

Given: 명시적 새 generation의 merge 또는 zero-output

When: retry/commit

Then: 같은 generation idempotent; 새 generation 구분; zero-output으로 기존 I 전량 폐기 금지

제안 의존성: P05. 사용자 요구: baseline/P contract. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_information_integration.py](../../tests/app/test_information_integration.py).

검증 범위·한계: 동일 generation 작업 재생, 다른 generation의 별도 parser execution, zero-output의 명시적 상태를 검증했다. merge와 새 generation zero-output 후 기존 I 보존 시나리오는 미실행이다.


## AT37 — effect-only 승인 저장

Given: N2E explicit no_longer_valid와 info K revalidation

When: Record 저장

Then: approved effect와 rejected candidate 구분; 합법 enum/mode 조합만 저장

제안 의존성: P06. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT38 — no-material의 nonsemantic 효과

Given: unchanged relation에서 applicability event 필요

When: terminal 처리

Then: no_material_delta와 event append 공존; 새 semantic Revision 없음

제안 의존성: P06. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT39 — predicate identity 변경

Given: A supports B에서 A qualifies B로 변경

When: 승인된 relation effect commit

Then: supports edge ID에 predicate overwrite 금지; new logical edge+old 처리

제안 의존성: P06. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT40 — DAG 범위

Given: Information/Decision supersession cycle과 일반 semantic cycle

When: 각 관계 검증

Then: supersession/self-cycle 거부; 일반 관계 cycle은 registry에 따라 처리하며 blanket DAG 강제 금지

제안 의존성: P06. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT41 — 공존하는 조건별 주장

Given: adult X와 pediatric not X

When: identity 판정

Then: 정정 근거 없이 둘을 같은 current revision으로 소거하지 않음

제안 의존성: P01. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT42 — 동명이인·alias

Given: 동일 이름의 다른 entity 및 한 entity의 다른 alias

When: identity resolver

Then: 이름만으로 merge하지 않음; approved identifier/alias 정책 사용

제안 의존성: P01. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT43 — 독립 evidence 수

Given: 한 실험의 preprint/final/review/요약

When: support aggregation

Then: Data 수를 독립 실험 수로 그대로 세지 않음; lineage unknown은 unknown

제안 의존성: P07. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT44 — derivation 순환 double count

Given: 같은 leaf evidence에서 파생한 K들이 서로 지지

When: support projection 계산

Then: leaf support 집합 dedup; circular derivation이 새 독립 evidence를 만들지 않음

제안 의존성: P07. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT45 — confirmation retry

Given: 동일 승인 event의 같은 payload가 두 번 도착

When: ConfirmDecision

Then: 동일 W/K result; W 생성 전 idempotency 유지

제안 의존성: P08. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT46 — 진짜 재결정

Given: 서로 다른 승인 event가 같은 option 선택

When: 각 ConfirmDecision

Then: 별도 W/K event; semantic duplicate reuse 금지

제안 의존성: P08. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT47 — authority payload binding

Given: same key different payload 또는 위조된 confirmation_ref

When: ConfirmDecision

Then: 명시적 conflict/authority rejection; canonical W/K partial 생성 없음

제안 의존성: P08. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT48 — decision action schema

Given: select/defer/decline의 필수·금지 필드 조합

When: schema/mapping validation

Then: 부적절 조합 거부; defer condition/time 정보 유실 없음

제안 의존성: P08. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT49 — 미래 효력·부분 supersession

Given: D2는 미래 효력이고 D1 일부 scope만 대체

When: as-of status 조회

Then: 즉시 전면 D1 inactive 금지; 승인된 시간/scope 규칙 적용

제안 의존성: P08. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT50 — decision 정정과 재결정

Given: typo 또는 material record correction 또는 실제 선택 변경

When: 변경 요청 처리

Then: presentation/authority correction/new event 경계를 구분; immutable W와 provenance 유지

제안 의존성: P08. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT51 — retrieval 두 축

Given: decision_trace에서 K와 direct I 필요

When: Wisdom 저장

Then: evidence surface와 strategy 모두 재현 가능; 충돌하는 single enum 강제 없음

제안 의존성: P08. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT52 — reported decision trace

Given: I2K reported decision에 origin W 없음

When: explain_decision

Then: I/D로 추적; 사용자 confirmation이나 이유를 만들어내지 않음

제안 의존성: P08. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT53 — stale RAG hit

Given: index는 A1, authoritative current는 A2 또는 invalid

When: retrieval hit 반환

Then: exact current filtering과 lag 표시; stale를 현재 근거로 조용히 사용하지 않음

제안 의존성: P09. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT54 — as-of graph receipt

Given: 나중 grounding/lifecycle/applicability event가 추가됨

When: 과거 W/graph 재현

Then: 당시 event/read receipt 사용; 최신 상태를 과거에 주입하지 않음

제안 의존성: P09. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT55 — replay 한계

Given: provider unavailable 또는 raw rejected payload retention 만료

When: historical replay/재실행 요청

Then: 복원 가능한 accepted evidence와 재실행 불가 범위 구분; 동일 모델 출력 보장 주장 금지

제안 의존성: P09. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT56 — artifact/DB crash

Given: staging/write/publish/DB commit 각 failpoint

When: recovery

Then: unreadable D ready 상태 금지; orphan reconcile; hash 검증

제안 의존성: P10. 사용자 요구: U09. 구현/실행 상태: passed / 2026-09-09.

실행 근거: [progress/T02_execplan.md](../../progress/T02_execplan.md).

검증 경로: [tests/app/test_artifact_store.py](../../tests/app/test_artifact_store.py), [tests/app/test_data_integration.py](../../tests/app/test_data_integration.py).

## AT57 — backup restore

Given: DB snapshot과 artifact manifest 및 outbox backup

When: 빈 환경에서 restore

Then: exact IDs/hashes/provenance 복원, redelivery 안전, missing artifact 명시

제안 의존성: P10. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT58 — 문서 prompt injection

Given: D 내용에 시스템 명령/승인문/내부 URL 존재

When: D2I와 K2W

Then: 자료로만 해석; unauthorized tool/confirmation/fetch/파일 접근 없음

제안 의존성: P10. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT59 — secret와 외부 전송

Given: API key env와 민감 원본, 외부 provider 비허용

When: 로그/fixture/실행 검토

Then: secret 미출력/미커밋; 허가 없는 live transmission 없음

제안 의존성: P10. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT60 — 사용자 중단과 부분 상태

Given: 큰 정상 propagation 실행 중 사용자 pause/cancel

When: 중단 및 resume

Then: 미완료 obligation/사유 표시; success/quiescent로 위장하지 않음

제안 의존성: P10. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT61 — 자체 생성물 재수입

Given: P/B를 export 후 D로 import

When: I2K/support 평가

Then: derived origin lineage 유지; 새 독립 evidence 또는 authority로 세탁되지 않음

제안 의존성: P07. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT62 — 출판 편집의 새 주장

Given: W composition 중 출처 없는 새 문장 추가

When: Parchment 생성

Then: citation 재검증 또는 author-added/ungrounded 표시; W와 동일 근거라고 날조하지 않음

제안 의존성: P07. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT63 — 명세 정합성

Given: baseline와 승인 addenda/registry

When: schema/doc validation

Then: D당 lifetime 1회, mode/effect 충돌 등 승인된 errata를 다시 구현하지 않음

제안 의존성: P11. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT64 — 미확인 repo·명령 방지

Given: 기존 repo 또는 빈 폴더, 실행 도구 미확인

When: T00/T01

Then: 관찰한 stack/commands만 보고; repo 미검사 상태를 구현 완료라고 주장하지 않음

제안 의존성: P12. 사용자 요구: U04, U05, U06. 구현/실행 상태: spec_only / 미실행. 모델·버전·모듈 계약 승인과 실제 설치/실행/import 의존성 검증을 구분한다.

## AT65 — 평가 게이트 분리

Given: mock/unit 통과하지만 DB 또는 live eval 미실행

When: 마일스톤 보고

Then: 실행하지 않은 suite는 not run; mock 통과를 LLM 정확성/e2e 통과로 기록하지 않음

제안 의존성: P12. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT66 — deterministic W2K

Given: authority-confirmed structured W

When: W2K 생성과 retry

Then: LLM call count 0; W/K/Record/provenance/outbox atomic; 확인된 supersedes 관계/effect도 같은 W2KRecord와 transaction에 포함하며 관계 저장 실패 시 전체 rollback

제안 의존성: 없음. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.


## AT67 — 원본 payload 불변

Given: 등록된 D의 bytes

When: payload 변경 요청

Then: 기존 D 수정 거부; 달라진 bytes는 새 D

제안 의존성: . 사용자 요구: U09. 구현/실행 상태: passed / 2026-09-09.

실행 근거: [progress/T02_execplan.md](../../progress/T02_execplan.md).

검증 경로: [tests/app/test_data_integration.py](../../tests/app/test_data_integration.py), [docs/schema/T02_storage_checks.sql](../../docs/schema/T02_storage_checks.sql).

## AT68 — Candidate 경계와 cleanup

Given: pending/needs_human/accepted/rejected/suppressed 후보

When: canonical 검색 및 terminal 처리

Then: 미승인 payload canonical corpus 제외; needs_human 유지; terminal cleanup/audit 정책 적용

제안 의존성: . 사용자 요구: U09. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_information_integration.py](../../tests/app/test_information_integration.py).

실물 근거: [output/t03/job_result.json](../../output/t03/job_result.json), [output/t03/information.json](../../output/t03/information.json).

검증 범위·한계: 미승인 후보의 canonical 제외, accepted/rejected cleanup, needs_human 후보 및 미완료 상태 보존을 실제 PG에서 검증했다. suppressed 후보와 canonical 검색 전체는 미구현 범위이다. 실제 결과에서 승인된 I 28개만 조회되고 기각 Record 1개가 남았다. 실제 needs_human/suppressed 사례는 이번 PDF에서 나오지 않았다.

## AT69 — I immutable 교정

Given: Information 오추출 정정

When: repair

Then: InformationRevision/기존 row overwrite 없음; 새 I+supersession/invalidation

제안 의존성: 없음. 사용자 요구: baseline/P contract. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_information_integration.py](../../tests/app/test_information_integration.py).

검증 범위·한계: 확정 Information UPDATE와 grounding 추가 거부를 검증했다. 교정용 새 I와 supersession/invalidation 흐름은 미실행이다.

## AT70 — acquisition 다중성

Given: 같은 D bytes에 실제 독립 origin 두 개와 평범한 duplicate import 요청

When: 두 번째 origin을 명시적 acquisition 기록으로 추가하고 평범한 duplicate를 별도로 요청

Then: Data는 하나이며 명시적 독립 acquisition 두 개는 보존한다. 평범한 duplicate는 거부하고 acquisition/D2I를 자동 추가하지 않는다. Source 계층은 없다.

제안 의존성: . 사용자 요구: U09. 구현/실행 상태: passed / 2026-09-09.

실행 근거: [progress/T02_execplan.md](../../progress/T02_execplan.md).

검증 경로: [tests/app/test_data_integration.py](../../tests/app/test_data_integration.py), [docs/schema/T02_storage_checks.sql](../../docs/schema/T02_storage_checks.sql).

## AT71 — usable I 검색 경계

Given: superseded/invalidated I와 historical provenance 존재

When: current RAG/I2K vs history

Then: current에서 제외, history에서 exact old I 유지; 입력 ref 자동 치환 금지

제안 의존성: 없음. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT72 — immutable publication

Given: P/B 구성·문장 변경

When: save/publish

Then: 새 P/B snapshot+supersedes; 기존 artifact/포함 parchment refs 보존

제안 의존성: 없음. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT73 — 근거 append provenance

Given: 기존 K에 새로운 독립 support accepted

When: grounding commit

Then: semantic Revision 없음; old origin refs 보존; 새 grounded ref/effect 기록

제안 의존성: 없음. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT74 — Operation×kind

Given: K2K가 observation/authority decision 제안 또는 I2K가 edge 제안

When: structural validation

Then: 금지 조합 거부; W2K decision, N2E edge 경계 유지

제안 의존성: 없음. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT75 — 반박과 수정 분리

Given: A1과 양립 어려운 B1

When: N2E contradiction 승인

Then: A1 자동 수정/삭제 없음; contested projection 후 별도 K2K 평가

제안 의존성: 없음. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT76 — canonicalization version

Given: 동등 payload key order/Unicode/unit representation 및 다른 schema

When: fingerprint 생성

Then: versioned envelope 유지; 승인된 normalization만 equality; 미승인 표현 합치기 금지

제안 의존성: 없음. 사용자 요구: baseline/P contract. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_information.py](../../tests/app/test_information.py), [tests/app/test_d2i.py](../../tests/app/test_d2i.py).

검증 범위·한계: Unicode/개행 정규화, 내부 공백 보존, 좌표 숫자 표현 및 opaque parser ref에 대한 FP 단언, 정규화 출력 digest를 검증했다. schema version 교체와 단위 표현 정규화는 미검증이다.

## AT77 — traceable Record와 이유

Given: approval/rejection/suppression/reuse

When: audit 조회

Then: input/profile/disposition/effects/canonical refs/reason 추적; private chain-of-thought 저장 요구 없음

제안 의존성: 없음. 사용자 요구: baseline/P contract. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_information_integration.py](../../tests/app/test_information_integration.py), [tests/app/test_d2i.py](../../tests/app/test_d2i.py), [tests/app/test_codex_provider.py](../../tests/app/test_codex_provider.py).

실물 근거: [output/t03/job_result.json](../../output/t03/job_result.json), [output/t03/information.json](../../output/t03/information.json).

검증 범위·한계: accepted/rejected/needs_human Record, source/profile/receipt와 canonical grounding/effect 참조, 분류형 reason code, private reasoning 비반환을 검증했다. suppression/reuse audit 전체는 미실행이다. 실제 Generator v2/Validator v3는 서로 다른 thread에서 같은 source_bundle/proposal_set digest를 소비했고, 29 Records와 28 I/51 groundings의 결과 참조를 남겼다. 실제 live 결과와 mock quality 단언을 구분한다.

## AT78 — 자동 W2K/질의 재실행 제한

Given: explanation/recommendation/decision_trace W와 graph 변화

When: event dispatch

Then: 일반 W→K 자동 승격 없음; 과거 K2W 자동 재실행 없음

제안 의존성: 없음. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT79 — depth는 metadata

Given: 여러 causal root를 거친 K2K derivation

When: projection/acceptance

Then: derivation 누적; 숫자만으로 reject/cutoff 금지; causal chain과 구분

제안 의존성: 없음. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT80 — QueryContextGraph 경계

Given: 사용자 Query/session memory가 포함된 K2W

When: 답 생성

Then: context snapshot으로 보존하되 canonical K 자동 insert 없음

제안 의존성: 없음. 사용자 요구: baseline/P contract. 구현/실행 상태: spec_only / 미실행.

## AT81 — grounding source fidelity

Given: D가 틀린 주장을 실제로 포함한 경우

When: D2I validation

Then: 출처가 말한 내용과 위치 검증; I acceptance를 세계에서 참이라고 표현하지 않음

제안 의존성: 없음. 사용자 요구: baseline/P contract. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_information.py](../../tests/app/test_information.py), [tests/app/test_d2i.py](../../tests/app/test_d2i.py).

실물 근거: [output/t03/job_result.json](../../output/t03/job_result.json), [output/t03/information.json](../../output/t03/information.json).

검증 범위·한계: 구조 적합성이 source fidelity 승인이 아니라는 단언과 원문 주장을 world truth로 인증하지 않는 prompt 계약을 mock으로 검증했다. 실제 의미 판정 품질은 평가하지 않았다. 실제 별도 Validator 추론을 수행했지만 문서 속 거짓 주장을 world truth와 구분하는 별도 평가셋이나 전체 I의 독립적 정답 평가는 수행하지 않았다.

## AT82 — T02부터 headless CLI

Given: display/browser/GUI가 없는 test environment

When: help/version/data import/show/verify를 실행

Then: application services와 실제 파일/DB로 동작하며 GUI package를 요구하지 않음

제안 의존성: P12. 사용자 요구: U01. 구현/실행 상태: passed / 2026-09-09.

실행 근거: [progress/T02_execplan.md](../../progress/T02_execplan.md).

검증 경로: [tests/app/test_cli_integration.py](../../tests/app/test_cli_integration.py).

## AT83 — 기계 출력과 로그 분리

Given: CLI --json mode와 progress/error 발생

When: stdout/stderr를 각각 capture

Then: stdout은 versioned JSON만 포함하고 logs/progress는 stderr; error에도 machine-readable result

제안 의존성: P12. 사용자 요구: U01. 구현/실행 상태: passed / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md). 이전 근거: [progress/T02_execplan.md](../../progress/T02_execplan.md).

검증 경로: [tests/app/test_cli_integration.py](../../tests/app/test_cli_integration.py), [tests/app/test_cli_unit.py](../../tests/app/test_cli_unit.py).

검증 범위·한계: 기존 T02 공통 CLI JSON/stdout/stderr/오류·progress 분리 근거를 보존하며 최종 앱 이미지 전체 회귀에서 재검증했다.

## AT84 — 비TTY 확인 입력 누락

Given: stdin이 pipe/EOF이고 승인 정보가 없음

When: review/decision consequence command 실행

Then: 무한 prompt나 자동 승인 없이 needs_confirmation/권한 오류와 명시적 nonzero 결과

제안 의존성: P08, P12. 사용자 요구: U01. 구현/실행 상태: spec_only / 미실행.

## AT85 — 명령 성공과 workflow 완료 구분

Given: 비동기 compilation request가 접수됨

When: CLI result와 jobs show 조회

Then: request 접수를 propagation completed로 표시하지 않으며 실제 pending/partial/blocked와 job ref 반환

제안 의존성: P03, P12. 사용자 요구: U01. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_information_integration.py](../../tests/app/test_information_integration.py).

실물 근거: [output/t03/job_result.json](../../output/t03/job_result.json), [output/t03/information.json](../../output/t03/information.json).

검증 범위·한계: prepared/proposed/failed/needs_human/zero_output/completed 구분과 pending 작업 재시도를 검증했다. 실제 CLI worker의 prepared→parsed→proposed→completed 상태와 최종 jobs 결과를 확인했다. pending I2K 이후 전파 완료를 의미하지 않으며 부분·blocked 전체 경로는 별도이다.

## AT86 — 관찰 종료와 durable job 상태

Given: watch 실행 중 durable job이 running

When: 사용자가 Ctrl-C로 watch를 중단한 뒤 resume 조회

Then: 관찰 종료만으로 job 삭제/성공/취소를 위조하지 않고 실제 lifecycle 보존

제안 의존성: P03, P10, P12. 사용자 요구: U01. 구현/실행 상태: spec_only / 미실행.

## AT87 — CLI authority와 payload binding

Given: LLM recommendation과 새 decision payload, --yes 옵션

When: decision confirm/retry 수행

Then: 실제 actor/payload-bound evidence 없이 commitment 생성 금지; 같은 승인 event retry는 idempotent

제안 의존성: P08. 사용자 요구: U01. 구현/실행 상태: spec_only / 미실행.

## AT88 — 현재 구성요소·Operation naming

Given: 현재 canonical/tasks/code contracts

When: 구성요소 label/module/schema examples 검사

Then: Artifact Store/artifact_store, Canonical Store/canonical_store, Compiler Runtime/compiler_runtime 및 K2W/k2w 사용; 과거 이름은 archive/원본 인용/변경 근거/migration에서 보존

제안 의존성: 없음. 사용자 요구: U03, U07. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T02_execplan.md](../../progress/T02_execplan.md).

검증 경로: [tools/test_validate_bundle.py](../../tools/test_validate_bundle.py).

## AT89 — 이름 migration과 identity 보존

Given: 기존 schema/파일/ID/hash/fingerprint가 있는 fixture

When: U03 mapping migration rehearsal

Then: accepted bytes/IDs/history digest 불변; 새 이름 때문에 duplicate canonical object나 destructive rename 없음

제안 의존성: P10, P12. 사용자 요구: U03. 구현/실행 상태: spec_only / 미실행.

## AT90 — PDF routing은 MinerU

Given: media_type application/pdf의 immutable D

When: CLI compile data로 parser 선택

Then: MinerU adapter가 선택되고 다른 parser가 조용히 대신 실행되지 않음

제안 의존성: 없음. 사용자 요구: U02. 구현/실행 상태: passed / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tools/run_d2i.py](../../tools/run_d2i.py), [deploy/mineru/run_parser.py](../../deploy/mineru/run_parser.py).

실물 근거: [output/t03/job_result.json](../../output/t03/job_result.json), [output/t03/information.json](../../output/t03/information.json), [progress/T03_source_preflight.json](../../progress/T03_source_preflight.json), [progress/T03_parser_observations.json](../../progress/T03_parser_observations.json).

검증 범위·한계: 실제 immutable PDF Data를 compile data CLI로 시작하고 MinerU 3.4.5/pipeline/adapter v2로 14/14페이지 처리하여 completed에 도달했다. 해당 native-text PDF 1건의 MinerU routing과 별도 의미 검증 연결을 확인했으며 다른 PDF 유형의 parsing 품질까지 뜻하지 않는다.

## AT91 — Parser success와 I acceptance 분리

Given: MinerU는 성공했지만 추출이 원문 의미와 불일치

When: D2I 검증

Then: parse artifact는 유지 가능하나 잘못된 I는 승인되지 않음; parser exit code로 canonical truth 확정 금지

제안 의존성: P01. 사용자 요구: U02. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_information.py](../../tests/app/test_information.py), [tests/app/test_d2i.py](../../tests/app/test_d2i.py), [tests/app/test_information_integration.py](../../tests/app/test_information_integration.py).

실물 근거: [output/t03/job_result.json](../../output/t03/job_result.json), [output/t03/information.json](../../output/t03/information.json).

검증 범위·한계: 합성 parser artifact 보존과 mocked rejected/needs_human의 canonical I 미생성, 구조 검증과 의미 승인 분리를 검증했다. 실제 오추출을 모델이 기각하는 품질 평가는 미실행이다. 실제 parser 성공 뒤 29개 제안에 독립 Validator를 실행하여 28개만 canonical I로 반영하고 1개를 기각했다. 이 단일 모델 판정을 오추출 탐지 품질이나 모든 I의 정확성 확증으로 취급하지 않는다.

## AT92 — Parse artifact와 grounding 보존

Given: MinerU structured output/Markdown/이미지와 원본 PDF

When: I anchor 생성 후 provenance 조회

Then: 원본 D hash/page/region과 parser output hash/profile/raw locator를 연결; Markdown offset을 PDF offset으로 사용하지 않음

제안 의존성: P10. 사용자 요구: U02. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_mineru_adapter.py](../../tests/app/test_mineru_adapter.py), [tests/app/test_information_integration.py](../../tests/app/test_information_integration.py), [tests/app/test_d2i.py](../../tests/app/test_d2i.py).

실물 근거: [output/t03/job_result.json](../../output/t03/job_result.json), [output/t03/information.json](../../output/t03/information.json), [progress/T03_source_preflight.json](../../progress/T03_source_preflight.json), [progress/T03_parser_observations.json](../../progress/T03_parser_observations.json).

검증 범위·한계: 합성 structured text/image/table/formula의 raw locator 및 Data/page/bbox/anchor와 parser manifest hash/profile 연결, durable 파일 복구를 검증했다. 실제 14페이지 PDF의 parse manifest와 Data hash, page/region/raw locator, 63개 crop hash를 연결하고 28개 I의 grounding 51개를 조회했다. Fig5H bbox는 upstream raw parent와 구분되는 explicit envelope이며 exact grounding_regions를 별도로 보존한다.

## AT93 — 페이지·좌표 normalization

Given: 부분 page range/rotation/crop과 backend별 다른 좌표를 포함한 출력

When: adapter가 original PDF anchor를 생성

Then: 0/1-based와 page offset/coordinate system을 검증해 mapping; 근거 없는 bbox 추정 금지

제안 의존성: P12. 사용자 요구: U02. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_mineru_adapter.py](../../tests/app/test_mineru_adapter.py), [tests/app/test_information.py](../../tests/app/test_information.py), [tests/app/test_information_integration.py](../../tests/app/test_information_integration.py).

실물 근거: [output/t03/job_result.json](../../output/t03/job_result.json), [output/t03/information.json](../../output/t03/information.json), [progress/T03_source_preflight.json](../../progress/T03_source_preflight.json), [progress/T03_parser_observations.json](../../progress/T03_parser_observations.json).

검증 범위·한계: 정확한 원본 page index 범위, finite bbox, page 경계, cross-page preproc 보존과 잘못된 grounding 거부를 검증했다. 단일 실제 PDF에서 원본과 MinerU origin의 MediaBox/CropBox/rotation, 정수 page-size 반올림, 14개 원문 page index를 대조했다. 부모 밖 caption을 개별 관측 영역 union으로 포함했으며 다른 rotation/backend/page-window fixture는 여전히 미검증이다.

## AT94 — 미지원 MinerU output schema

Given: 선택한 parser가 adapter가 모르는 구조를 반환

When: decode/normalize

Then: 명시적 unsupported schema로 중단; 빈 내용이나 fabricated anchors로 성공하지 않음

제안 의존성: 없음. 사용자 요구: U02. 구현/실행 상태: passed / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_mineru_adapter.py](../../tests/app/test_mineru_adapter.py), [tests/app/test_d2i.py](../../tests/app/test_d2i.py).

검증 범위·한계: structural contract passed: 합성 unknown parser type을 supported=False로 보존하고 D2I가 unsupported_parser_output으로 중단함을 검증했다. 누락 visual payload도 실패하며 빈 내용이나 추정 anchor로 성공하지 않는다. 실제 MinerU 품질 평가를 뜻하지 않는다.

## AT95 — MinerU 미설치와 silent fallback 금지

Given: MinerU executable 또는 모델이 없고 다른 parser는 설치됨

When: doctor/compile data 실행

Then: readiness/error 원인 보고; 다른 parser로 성공 대체하지 않음

제안 의존성: 없음. 사용자 요구: U02. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_cli_unit.py](../../tests/app/test_cli_unit.py), [tests/app/test_data_integration.py](../../tests/app/test_data_integration.py).

검증 범위·한계: 미설정 MinerU의 readiness 경고와 doctor의 구조화 응답을 검증했다. 실제 executable/model 부재 시 compile 실패 및 대체 parser 미호출은 미실행이다.

## AT96 — 로컬 parser와 문서 전송 권한

Given: remote document transfer 권한 없음

When: 기본 PDF D2I 실행

Then: local/loopback profile만 사용; hosted API 전송 요청은 별도 승인 전 차단

제안 의존성: P10. 사용자 요구: U02. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tools/run_d2i.py](../../tools/run_d2i.py), [deploy/mineru/run_parser.py](../../deploy/mineru/run_parser.py).

실물 근거: [output/t03/job_result.json](../../output/t03/job_result.json), [output/t03/information.json](../../output/t03/information.json), [progress/T03_source_preflight.json](../../progress/T03_source_preflight.json), [progress/T03_parser_observations.json](../../progress/T03_parser_observations.json).

검증 범위·한계: 실제 parser는 Docker network=none, 로컬 모델 및 읽기 전용 Data로 실행했다. 후속 Codex 원문 전달에는 이 PDF에 대한 사용자 승인이 있었다. 전송 권한이 없는 경우 hosted API 요청을 차단하는 부정 시나리오는 실행하지 않아 전체 권한 계약 통과가 아니다.

## AT97 — Parser artifact retry idempotency

Given: 동일 D/profile/generation의 검증된 parse artifact가 존재

When: 실패한 downstream attempt를 retry

Then: artifact 무결성 확인 후 재사용 가능; 원본/parse outputs 덮어쓰기나 duplicate canonical effects 없음

제안 의존성: P05. 사용자 요구: U02. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_information_integration.py](../../tests/app/test_information_integration.py).

실물 근거: [output/t03/job_result.json](../../output/t03/job_result.json), [output/t03/information.json](../../output/t03/information.json).

검증 범위·한계: 동일 parser artifact 재생, durable CAS hash/size 복구, 다른 bytes의 export 충돌 거부, downstream 실패 후 같은 작업 재시도와 중복 effect 방지를 검증했다. 실제 parser/host worker crash 복구를 연결한 시험은 별도이다. 실제 retained parser artifacts를 CAS에서 별도 host 폴더로 복원하여 모델 입력에 제공했고 completed 작업의 CLI replay를 확인했다. source/profile을 바꾼 실행은 동일 retry와 구분한다.

## AT98 — MinerU version/profile 변경

Given: 과거 parser output과 I가 보존됨

When: 명시적 새 parser profile로 recompile

Then: 새 parse execution/generation 관계를 기록; D hash/old I provenance 불변; 자동 과거 전량 재실행 없음

제안 의존성: P05. 사용자 요구: U02. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tools/run_d2i.py](../../tools/run_d2i.py), [tests/app/test_information_integration.py](../../tests/app/test_information_integration.py).

실물 근거: [output/t03/job_result.json](../../output/t03/job_result.json), [output/t03/information.json](../../output/t03/information.json), [progress/T03_source_preflight.json](../../progress/T03_source_preflight.json), [progress/T03_parser_observations.json](../../progress/T03_parser_observations.json).

검증 범위·한계: 이전 실패 execution/parse artifact를 보존하고 명시적으로 달라진 parser image·adapter v2·prompt profile을 새 execution으로 실행했다. Data hash는 동일하고 과거 오류를 성공으로 재기록하지 않았다. 이전 실행에는 canonical I가 없어 old I provenance를 유지하는 profile 교체 시나리오는 미검증이다.

## AT99 — 전체 PDF page coverage

Given: 큰 PDF 요청을 여러 page window로 처리 중 한 window 실패

When: job completion 판정

Then: 누락 page와 partial/retry 상태 표시; 처리 창 크기를 총 페이지 성공 cap으로 사용하지 않음

제안 의존성: P03, P05. 사용자 요구: U02. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_mineru_adapter.py](../../tests/app/test_mineru_adapter.py), [tests/app/test_d2i.py](../../tests/app/test_d2i.py).

실물 근거: [output/t03/job_result.json](../../output/t03/job_result.json), [output/t03/information.json](../../output/t03/information.json).

검증 범위·한계: 정확한 전체 page index range와 누락/중복 page 거부, 입력 coverage와 의미적 완전성 구분을 합성 fixture로 검증했다. page window 중간 실패와 durable partial/retry 시나리오는 미실행이다. 실제 두 모델 receipt는 각 14페이지·249 blocks·63 images, 제외 input block 0개를 기록했다. 미참조 source block 205개이며 입력 coverage는 의미적 완전성을 입증하지 않는다. page window 실패 시험은 미실행이다.

## AT100 — 손상·암호화·timeout의 기술 실패

Given: corrupt/encrypted PDF 또는 parser timeout

When: D2I 실행

Then: 실패 원인/원본을 보존하고 epistemic rejected와 구분; provider/parser 교체로 오류 은폐하지 않음

제안 의존성: P05. 사용자 요구: U02. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_codex_provider.py](../../tests/app/test_codex_provider.py), [tests/app/test_d2i.py](../../tests/app/test_d2i.py), [tests/app/test_information_integration.py](../../tests/app/test_information_integration.py).

실물 근거: [output/t03/job_result.json](../../output/t03/job_result.json), [output/t03/information.json](../../output/t03/information.json).

검증 범위·한계: 기술 오류를 semantic rejection으로 바꾸지 않고 후보를 보존하는 mock/실제 PG 경계를 검증했다. 실제 corrupt/encrypted PDF와 MinerU timeout 시나리오는 미실행이다. 실제 초기 parser의 누락 runtime dependency 및 wrapper 오류가 기술 실패로 남고 canonical I나 의미적 rejection으로 처리되지 않았음을 실행 기록에서 확인했다. corrupt/encrypted PDF와 MinerU timeout은 미실행이다.

## AT101 — 실제 MinerU PDF integration

Given: 선택한 버전/backend와 합법적 native/scanned/mixed PDF test set

When: 실제 parser를 실행하고 원문과 page/table/formula anchors 대조

Then: 버전/profile/coverage/assertions와 결과를 남김; synthetic fixture만으로 real parser 통과 주장 금지

제안 의존성: P12. 사용자 요구: U02. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tools/run_d2i.py](../../tools/run_d2i.py), [deploy/mineru/run_parser.py](../../deploy/mineru/run_parser.py), [tests/app/test_mineru_adapter.py](../../tests/app/test_mineru_adapter.py).

실물 근거: [output/t03/job_result.json](../../output/t03/job_result.json), [output/t03/information.json](../../output/t03/information.json), [progress/T03_source_preflight.json](../../progress/T03_source_preflight.json), [progress/T03_parser_observations.json](../../progress/T03_parser_observations.json).

검증 범위·한계: 사용자 제공 native-text/figure PDF 1건을 실제 MinerU 3.4.5/pipeline으로 처리했다. 14/14페이지, 249 blocks, 63 JPEG crop과 원본 geometry를 확인했고 대표 figure/caption을 시각 대조하여 Fig5 부모 밖 caption을 explicit envelope로 수정·재검증했다. scanned/mixed OCR·한국어·표/수식 test set 전체 및 의미적 완전성은 미검증이다.

## AT102 — doctor는 진단만 수행

Given: MinerU runtime/model readiness 또는 endpoint가 미설정

When: CLI doctor 실행

Then: secret 없이 구체 readiness 보고; 자동 다운로드/문서 업로드/환경 변경을 수행하지 않음

제안 의존성: P10, P12. 사용자 요구: U01, U02, U09. 구현/실행 상태: passed / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md). 이전 근거: [progress/T02_execplan.md](../../progress/T02_execplan.md).

검증 경로: [tests/app/test_cli_integration.py](../../tests/app/test_cli_integration.py), [tests/app/test_artifact_store.py](../../tests/app/test_artifact_store.py), [tests/app/test_cli_unit.py](../../tests/app/test_cli_unit.py), [tests/app/test_data_integration.py](../../tests/app/test_data_integration.py).

검증 범위·한계: 기존 T02 doctor 통과 근거와 상태를 보존하고 진단 응답·비변경 동작을 전체 회귀에서 재검증했다. 이번 T03 회귀는 실제 MinerU 모델 준비나 다운로드 경로의 통과를 추가 주장하지 않는다.

## AT103 — GUI는 release 뒤 deferred

Given: T00–T12 CLI 구현/평가 진행 중

When: task scheduling/build dependency 확인

Then: T13은 deferred이며 T12와 이후 착수 지시 전 시작 금지; CLI release는 GUI에 의존하지 않음

제안 의존성: 없음. 사용자 요구: U01. 구현/실행 상태: spec_only / 미실행.

## AT104 — 한국어 경로·인자·terminal safety

Given: 공백/quote/한국어/escape sequence 포함 filename

When: CLI import와 MinerU subprocess 실행

Then: argument array/안전 경로 검증; UTF-8 보존 및 terminal escape 처리; shell injection 없음

제안 의존성: P10, P12. 사용자 요구: U01, U02, U09. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md). 이전 근거: [progress/T02_execplan.md](../../progress/T02_execplan.md).

검증 경로: [tests/app/test_cli_integration.py](../../tests/app/test_cli_integration.py), [tests/app/test_artifact_store.py](../../tests/app/test_artifact_store.py), [tests/app/test_cli_unit.py](../../tests/app/test_cli_unit.py).

검증 범위·한계: 기존 T02 한국어/공백/quote/terminal escape 경로와 안전한 출력 근거를 보존하고 재검증했다. 해당 경로의 실제 MinerU subprocess 실행은 미실행이다.

## AT105 — 실효 parser config와 원격 endpoint

Given: 환경 변수/config가 요청 backend 또는 endpoint를 덮어쓸 수 있음

When: local profile로 실행 준비

Then: resolved config를 기록/검증하고 미승인 remote egress를 차단; secret을 fingerprint/log에 넣지 않음

제안 의존성: P10, P12. 사용자 요구: U02. 구현/실행 상태: spec_only / 미실행.

## AT106 — 같은 Decision 범위의 병렬 대체 정책

Given: 같은 배타적 subject/scope와 head에서 준비된 서로 다른 confirmation event 2개

When: 동시에 confirm commit을 시도

Then: R07 reconfirm_stale: head/state 검사와 commit을 한 충돌 경계로 보호한다. 늦은 요청은 새 canonical W/K/대체 관계를 저장하지 않고 현재 상태와 재확인 필요를 반환한다. 확인 시도 이력은 남기며 같은 성공 event/payload의 retry는 기존 결과다.

제안 의존성: P05, P08. 사용자 요구: U08. 구현/실행 상태: spec_only / 미실행.

## AT107 — 기각 payload cleanup 뒤 후보 조회

Given: 기각 후 payload/임시 index를 정리한 과거 후보와 다른 FP의 paraphrase 또는 corrected locator 후보

When: 다시 lookup/validation

Then: R08 exact_scoped_only: rejected Record는 정확한 rejection scope/FP로만 조회한다. 다른 FP의 표현과 corrected locator는 필요한 새 validation으로 처리한다. accepted semantic similarity는 유지하며 audit/raw payload를 기각 검색 데이터원으로 쓰지 않는다.

제안 의존성: P01, P09. 사용자 요구: U08, U09. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_information.py](../../tests/app/test_information.py), [tests/app/test_information_integration.py](../../tests/app/test_information_integration.py).

검증 범위·한계: corrected grounding의 FP 구분과 기각 본문 cleanup 뒤 Record 보존을 검증했다. exact scoped rejected-FP lookup 및 다른 FP의 새 validation 흐름은 미실행이다.

## AT108 — PostgreSQL 18·pgvector와 신규 ID 규칙

Given: 독립 PG18 test DB와 vector extension, 원본 bytes 및 신규 객체/Record/acquisition ID

When: 실제 server/extension profile과 schema 제약을 검사

Then: 최초 major는 18이고 실제 minor/extversion이 기록된다. Data ID=raw-byte SHA-256이며 UUIDv7/variant 위반·ID/hash 불일치를 거부한다. UUID를 commit ordering으로 사용하지 않고 PG19 자동 전환도 하지 않는다.

제안 의존성: P12. 사용자 요구: U09. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md). 이전 근거: [progress/T02_execplan.md](../../progress/T02_execplan.md).

검증 경로: [tests/app/test_data_integration.py](../../tests/app/test_data_integration.py), [docs/schema/T02_storage_checks.sql](../../docs/schema/T02_storage_checks.sql), [tests/app/test_information_integration.py](../../tests/app/test_information_integration.py).

검증 범위·한계: T03 실제 PG18/vector 존재와 신규 I UUIDv7, opaque ID 보유 8개 테이블의 비 RFC variant 거부 및 정확한 CHECK constraint를 검증했다. 기존 T02 SQL/ID 근거와 부분 상태를 보존한다.

## AT109 — 중복 Data·성공 retry·병렬 import

Given: 동일 bytes의 새 요청 둘과 commit 후 응답 유실된 기존 성공 request

When: 새 요청 import, 동일 request replay, 동일 key의 다른 payload, 병렬 동일 bytes 등록을 실행

Then: Data와 최초 acquisition은 하나다. 새 중복 요청은 duplicate_data+기존 ID와 nonzero 결과이며 D2I/자동 acquisition을 추가하지 않는다. 동일 성공 request/입력은 원래 성공을 반환하고 다른 입력은 conflict다.

제안 의존성: P10, P12. 사용자 요구: U09. 구현/실행 상태: passed / 2026-09-09.

실행 근거: [progress/T02_execplan.md](../../progress/T02_execplan.md).

검증 경로: [tests/app/test_data_integration.py](../../tests/app/test_data_integration.py), [tests/app/test_cli_integration.py](../../tests/app/test_cli_integration.py).

## AT110 — 도구 관리 등록·staging 경쟁·파일/DB 복구

Given: 독립 임시 Artifact Store·DB와 copy/publish/commit failpoint, 같은 request 동시 실행 및 object만 존재하는 상태

When: 도구 import·중단·reconcile·직접 관리 폴더 복사를 수행

Then: staging은 request별 배타 소유이고 덮어쓰지 않는다. 보존 bytes를 해시하고 shared object 존재만으로 duplicate 처리하지 않는다. prepared journal만 검증 재개하며 수동 파일을 자동 등록하지 않는다. 원본/공유 object를 실패 cleanup으로 삭제하지 않고 Data/acquisition/성공 receipt는 atomic하다.

제안 의존성: P10, P12. 사용자 요구: U09. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T02_execplan.md](../../progress/T02_execplan.md).

검증 경로: [tests/app/test_data_integration.py](../../tests/app/test_data_integration.py), [tests/app/test_artifact_store.py](../../tests/app/test_artifact_store.py).

## AT111 — 잠정 판정 승격과 영속 Runtime Record

Given: 잠정 accepted/rejected/no-material/needs-human 후보와 canonical commit failpoint

When: 같은 PG transaction에서 효과·Record·provenance·cleanup·outbox를 반영하고 retry

Then: 검증된 효과만 canonical에 반영되며 최종 판정·FP·reason·exact refs는 Runtime Record에 남는다. 실패 시 잠정 결과를 canonical 승인으로 노출하지 않고 원자적으로 rollback한다. 기각 본문 정리 후에도 exact scoped FP는 조회 가능하다.

제안 의존성: P05. 사용자 요구: U08, U09. 구현/실행 상태: partially_tested / 2026-09-09.

실행 근거: [progress/T03_execplan.md](../../progress/T03_execplan.md).

검증 경로: [tests/app/test_information_integration.py](../../tests/app/test_information_integration.py).

실물 근거: [output/t03/job_result.json](../../output/t03/job_result.json), [output/t03/information.json](../../output/t03/information.json).

검증 범위·한계: I/grounding/accepted Record/cleanup/outbox의 실제 PG 원자성, 구성요소 누락 commit 거부, before_commit rollback과 retry, terminal 불변 및 needs_human 보존을 검증했다. no-material과 기각 후 exact scoped lookup은 미실행이다. 실제 최종 결과는 accepted 28/rejected 1의 영속 Records, text I 23/image I 5 및 grounding 51개다. 원자성·failpoint는 별도 실제 PG 합성 회귀로 검증했고 전체 I2K 전파 gate와 no-material/scoped lookup까지 완료한 것은 아니다.

## AT112 — pgvector profile 교체와 ANN 차원 경계

Given: BGE-M3 1024 profile과 차원/정밀도/거리함수가 다른 향후 embedding profile

When: projection 저장·검색/index 호환성 검증과 Reranker 단독 교체

Then: pgvector dense 검색과 BGE multi-vector reranking을 구분한다. profile/source별 typed refs·차원을 검증하며 미지원 ANN 차원을 자동 절삭/half precision으로 바꾸지 않는다. 새 profile 검증 뒤 파생 projection만 전환하고 canonical ID/history를 보존한다.

제안 의존성: P09, P12. 사용자 요구: U04, U09. 구현/실행 상태: spec_only / 미실행.

U10: AT64/AT82/AT108은 Python 앱·Docker 실행 profile도 따른다. Docker 읽기 접근 확인과 실제 앱 container/DB integration 검증을 구분하며, 실행 상태는 각 항목의 기록을 따른다.


## U11 적용 범위

D2I는 원문 보존용 source unit을 스크립트로 조립·구조 검증한다. AT22/AT23의 I payload와 AT81/AT91의 판정 경계를 이에 맞췄으며 변경 전 Given/When/Then은 catalog의 pre_U11_contract로 보존했다. source_structure_verified는 의미 승인이나 세계의 참이 아니다. 같은 입력의 재시도, 원문 exact 구조·위치·이미지, 빈 Text, 변조/누락/손상 거부 및 atomic commit을 source 전용 앱/PG 테스트로 검증한다. 이전 LLM 실험 증거는 historical_t03_evidence로 분리하며 상태를 일괄 승격하지 않는다.
