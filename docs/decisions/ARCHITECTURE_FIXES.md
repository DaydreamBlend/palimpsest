# R01–R09 구조 검토 해결 계약

상태: U08의 위임 수정 범위와 후속 명시적 승인 범위를 구분한다. 사용자 요청은 “각 문제를 해결해주되, 중대해서 내 승인이 필요한 경우 나한테 요청해줘.”이다. R01–R06/R09는 이전 보고서의 구체 권고를 기존 불변조건 안에서 반영한다. R07/R08은 후속 사용자 답변으로 각각 reconfirm_stale/exact_scoped_only를 승인받아 적용했다. 아래 대안 B는 선택되지 않은 검토 기록이다. P01–P12 전체 승인, 앱 stack/DDL/provider 선택, public K 재검증 subtype 명명은 포함하지 않는다.

검토 근거는 [T01 검토](../../progress/T01_architecture_review.md)이며 변경 전 통합본은 [이전 snapshot](../history/2026-09-09_pre_architecture_fixes.md)에 보존한다. 기계 판독 상태는 [architecture_fixes.json](architecture_fixes.json)을 따른다. 여기서 resolved는 설계 충돌 해소이고 앱 구현/실행 완료가 아니다.

| 항목 | 설계 상태 | 관련 P 범위 |
|---|---|---|
| R01 | 적용: 최신 명시적 applicability 우선 | P02 중 판정 순서 |
| R02 | 적용: 현재 support·effective input dependency·maintenance | P02/P04 중 참조·근거·전파 경계 |
| R03 | 적용: scope/watermark와 미완료 의무를 기준으로 완료 | P03/P05 중 완료·fence 요구 |
| R04 | 적용: domain identity 우선, 사전 cache와 사후 attribution 분리 | P01 중 reuse/rejection 순서 |
| R05 | 적용: input freshness의 atomic 검증과 replacement-set barrier | P05 중 commit 일관성 |
| R06 | 적용: 명시적 supersedes를 W2K의 결정론적 atomic effect로 기록 | P05/P06/P08 중 명시적 대체 효과 |
| R07 | 적용: 늦은 결정 요청은 저장 전 재확인 | P05/P08의 추가 선택 |
| R08 | 적용: 기각 이력은 정확한 scoped FP 조회 | P01/P09의 추가 선택 |
| R09 | 적용: evidence_mode와 retrieval_strategy 분리 | P08/P11 중 두 축 구분 |

## R01 — Current applicability

읽으려는 exact semantic edge revision과 current endpoint pair를 먼저 고정한다. edge와 양 endpoint가 현재 usable인지 검사한다. 같은 revision/pair의 최신 명시적 판정이 있으면 그 판정이 initial acceptance보다 우선한다. 최신 not_applicable은 endpoint가 초기 pair와 같아도 제외한다. 명시적 판정이 없고 initial pair와 같을 때만 최초 승인을 사용한다. 그 밖은 pending/unknown이며 관계 부정으로 해석하지 않는다.

최신 순서는 transaction이 보장하는 commit order/token으로 정한다. wall-clock timestamp 동률이나 다른 endpoint pair의 이벤트를 이용해 덮어쓰지 않는다. history read는 당시 pair/basis/상태를 사용한다. physical sequence/lock 구현은 P05/P12에서 선택하되 이 순서는 바꾸지 않는다.

## R02 — Current support와 소비한 effective inputs

최초 origin provenance는 immutable이다. 재검증한 K의 의미가 같아도 target exact revision, 검증된 current input I/K/effective-edge bundle, origin Record, 이전 support와의 연결 및 commit ordering을 append-only current support receipt로 보존한다. active support와 reverse dependency projection은 그 receipt에서 계산한다. 새로 활성화한 I2→K dependency와 기존 근거의 비활성화·Record/receipt를 같은 commit unit으로 처리한다. 새 근거가 항상 의미적 material change라는 뜻은 아니다.

EffectiveEdgeRef는 semantic_kedge_revision_id, 실제 소비한 from/to revision IDs, applicability basis type/ref 및 read-state token을 묶은 공개 값 계약이다. 물리 참조는 typed FK rows로 보존하며 semantic edge의 원래 endpoint를 치환하지 않는다. Generator/Validator에 전달한 authoritative endpoint 값은 모델이 인용하지 않았다는 이유로 dependency에서 제거하지 않는다. 기본 경계는 전달한 effective input bundle 전체이며 field-level 최적화는 후속 평가 대상이다.

관계의 true→true rebasing은 semantic Revision/새 semantic branch를 만들지 않는다. endpoint 변경 때문에 이미 존재하는 consumer obligation, current support 갱신, projection 재생성, blocked 작업 release는 유지한다. 필수 입력 pending은 blocked/unknown이다. before/after confirmed applicability가 false→false이면 새 material cascade가 없고 true↔false이면 실제 적용 변화의 영향 범위를 평가한다.

## R03 — 완료 범위와 의무

필수 maintenance/revalidation은 exact reverse dependencies를 누락 없이 페이지 단위로 열거한다. RAG top-K는 한 번의 discovery/context 구성에만 사용하며 필수 대상을 제거하지 않는다. discovery의 후보 부재는 평가한 context에서 후보가 없다는 뜻이다.

완료 receipt에는 root/scope, source watermark, policy snapshot, dependency enumeration coverage/cursor, 아직 처리하지 않은 outbox·ready·leased/in-flight·retry·blocked/human obligation과 실제 종료 사유를 기록한다. 해당 watermark의 직접 입력뿐 아니라 그 입력이 유발한 모든 후속 material obligation이 끝나야 한다. 뒤늦은 descendant event는 commit sequence가 watermark보다 크다는 이유로 제외하지 않는다.

새 obligation 등록과 완료 상태 갱신은 서로 충돌을 검출할 수 있는 runtime fence/checkpoint 계약을 공유한다. 완료 확인 뒤 동시에 material effect가 commit되어 작업이 유실되는 구조는 허용하지 않는다. 외부 새 입력은 다음 scope로 넘길 수 있지만 원래 scope의 causal descendants는 계속 추적한다. 전역 가능한 모든 지식의 수학적 고정점을 보장하지 않으며, depth/크기/총 token/cost cap으로 성공 종료하지 않는다. pause/cancel/anomaly/실패는 미완료 의무와 함께 보존한다.

## R04 — Identity/reuse와 cache

순서는 eligibility → domain identity → exact content → materiality이다. I는 같은 D·grounding locus·의미 snapshot에서만 재사용한다. 일반 K는 current usable state를 비교하며 과거 content 일치는 history lookup일 뿐 current rollback 명령이 아니다. Decision은 같은 confirmation event/W retry만 재사용하고 다른 사건은 내용이 같아도 별개다.

attempt cache는 같은 semantic work의 실제 terminal 완료 여부를 확인한다. failed/pending/needs_human은 성공 cache가 아니며 처리되지 않은 proposal/obligation을 suppression으로 지우지 않는다. 여러 proposal이 같은 호출 FP를 공유할 수 있으므로 Record 전체의 attempt/content FP에 전역 UNIQUE를 두지 않는다. object identity 경쟁과 실행 claim을 각각 atomic guard로 보호한다.

context_fingerprint는 Validator 호출 전에 frozen candidate/input/context/check/profile로 계산한다. 사후 used refs는 attribution/audit이고 사전 key를 대체하지 않는다. 전달한 반증을 모델이 인용하지 않아도 cache scope에는 포함한다. schema 오류에는 schema version, locator 오류에는 D/extractor/locator, Operation×kind 오류에는 registry/policy version을 포함한다. context와 무관한 동일 불법 표현만 invariant-hard 전역 suppression 대상이다. provider 실패는 epistemic rejection이 아니다. accepted content 일치도 새 grounding의 validation을 생략시키지 않는다.

## R05 — Commit freshness와 교체 집합

모델 호출 전에 exact inputs와 관련 lifecycle/applicability/evidence/authority state token을 고정한다. commit은 target expected-base뿐 아니라 이 read-set을 검증하고, 검사 이후 commit 사이에 해당 입력 상태를 바꾸는 writer와 충돌을 검출해야 한다. stale read-set은 새 current state에서 재검증하거나 필요한 권한 확인으로 돌아간다. 단순 pre-commit SELECT만으로 이 보장을 주장하지 않는다. 구체 isolation/lock/version 전략은 실제 PostgreSQL 통합 검증에서 확정한다.

canonical 효과·Record·provenance/current support·Candidate 처리·outbox는 한 short commit unit이다. LLM/파싱 대기나 전체 전파를 장기 DB transaction으로 감싸지 않는다.

I split/merge는 같은 교체 의미 단위의 모든 replacement가 검증된 뒤, activation·supersession·old-I retirement·관련 Record와 outbox를 atomic하게 publish한다. 일부 replacement 실패 때 전체 교체를 활성화하지 않고 기존 I를 유지한다. 기존 I 자체가 틀렸다고 별도로 확인한 invalidation은 그 명시적 검증 경로를 사용한다. 서로 독립적인 신규 extraction은 개별 commit 가능하다. generation 증가만으로 과거 generation 전체를 폐기하지 않는다.

## R06 — 명시적 Decision supersedes의 소유권

ConfirmDecision application service는 실제 actor/payload-bound confirmation을 검증하고 W2K의 결정론적 projection을 호출한다. 같은 confirmation event와 같은 payload의 retry는 같은 결과를 반환하며, 같은 key의 다른 payload는 conflict다. 다른 정상 결정 사건은 내용으로 병합하지 않는다.

W2K는 확인된 payload에 명시된 supersedes_decision_id에 한해서 이전 Decision의 존재·origin·권한·scope·효력·DAG를 검증하고 해당 supersedes KEdge/첫 revision을 결정론적 부수 효과로 만든다. primary 결과는 새 decision KNode이며, 관계의 origin_record_id와 typed effect refs는 같은 W2KRecord를 가리킨다. 새 public Record subtype을 만들지 않는다. N2E는 discovery/일반 관계 revalidation을 계속 소유하고 명시적 결정 대체를 뒤늦게 추측하지 않는다.

한 transaction에 Decision W, W2KRecord, decision KNode/첫 revision, 요청된 supersedes 관계와 current 상태 효과, exact provenance 및 downstream outbox를 넣는다. 어떤 단계든 실패하면 전체 rollback이다. 관계 qualifiers와 status projection은 확인된 부분 scope·effective_at을 보존하므로 미래 효력 결정을 즉시 전면 적용하지 않는다. W2K의 LLM 호출은 0이며 payload에 없는 대체 대상을 내용 유사도로 찾아 추가하지 않는다. 같은 범위를 병렬 확정할 때는 R07의 승인된 재확인 정책을 적용한다.

## R07 — 승인 완료: 늦은 Decision 요청 재확인

상태: accepted — reconfirm_stale. 사용자 답변: “뒤늦은 요청은 새 결정을 저장하지 않고 현재 상태를 보여준 뒤 재확인받기 (권고)”. 예: 하나의 배타적 선택을 뜻하는 같은 subject/scope에서 D1을 보고 준비한 D2(A 선택), D3(B 선택)를 서로 다른 실제 확인으로 동시에 확정한다. event identity와 DAG만으로는 둘의 현행 상태를 정할 수 없다.

**선택 A: 늦은 요청 재확인.** prepare/confirm은 해당 범위의 current decision head 집합과 state token을 payload binding에 포함한다. commit에서 바뀌었으면 뒤늦은 요청을 conflict/needs_confirmation으로 돌려 canonical W/K를 만들지 않는다. 실행/확인 시도 이력은 남긴다. 사용자가 갱신된 현재 상태를 보고 다시 확정하면 새로운 event를 생성한다. 호출자의 인증/조회 권한 및 key/payload 일치를 확인한 같은 event의 성공 retry는 새 freshness 판정보다 먼저 기존 결과를 돌려준다. 다른 payload는 conflict다. 같은 scope라는 판단에 자유 텍스트 유사도를 사용하지 않는다.

**미선택 대안 B: 두 사건 보존 + 명시적 충돌.** 실제 확인된 두 event의 W/K를 보존하되 겹치는 배타적 scope에서 active projection을 conflict로 표시하고 자동 단일 결정 사용을 막는다. 후속 사용자가 충돌을 해소하는 새 결정을 확인해야 한다. 조용한 last-write-wins는 제안하지 않는다. 부분 scope·서로 독립인 결정은 일괄 충돌시키지 않는다.

검증 시나리오: 병렬 두 confirm, 같은 event retry, 같은 key의 다른 payload, 부분 scope 비충돌, 사용자 재확인, future-effective head 변경을 다룬다. R07은 선택 A만 활성 계약이다. 확인 시도는 실행/audit 이력으로 보존하되 stale 시도 자체를 canonical Decision W로 확정하지 않는다. head/state 확인과 새 W/K/대체 관계 commit은 같은 conflict boundary여야 한다.

## R08 — 승인 완료: 기각 이력은 exact scoped FP 조회

상태: accepted — exact_scoped_only. 사용자 답변: “기각 이력은 정확한 fingerprint로만 조회하고, 다른 표현의 후보는 다시 검증하기 (권고)”. 기존의 rejected semantic similarity 의무를 제거하고 terminal cleanup 원칙을 유지한다.

**선택 A: 기각 이력은 정확한 scoped FP 조회.** accepted payload에는 semantic similarity를 적용하고 rejected Record는 정확한 rejection scope/FP로 조회한다. 다른 FP의 새 표현은 이전 기각을 의미만으로 추정하지 않고 다시 검증한다. 기존 비canonical audit는 선택적 조사 용도로 유지하고 검색 기능을 위해 보존 범위를 늘리지 않는다. privacy와 구현 복잡도가 작지만 비슷한 기각에 모델 호출이 다시 발생할 수 있다.

**미선택 대안 B: 기각 내용의 별도 유사 검색 보존.** canonical corpus와 분리된 비canonical payload/index를 일정 기간 보존해 이전 기각을 Validator 참고 문맥으로만 제공한다. similarity만으로 자동 기각하지 않는다. 만료/사용 불가 시 정확한 FP 조회와 새 validation으로 돌아간다. 이 안은 보존 내용·기간·삭제/암호화 정책을 함께 결정해야 하므로 그 상세 전에는 활성화하지 않는다.

검증 시나리오: cleanup 뒤 같은 FP, 다른 FP의 paraphrase, locator를 고친 같은 semantic content, optional audit 비활성/만료, 모델/profile 변경을 포함한다. R08 선택은 모델·원문 다운로드/외부 전송 승인이 아니다.

## R09 — 두 retrieval 축

새 current 계약은 evidence_mode = knowledge_only / knowledge_plus_evidence / evidence_only, retrieval_strategy = standard / decision_trace / history다. epistemic_basis는 실제 사용한 accepted K/direct I의 근거 분류를 별도로 보존한다. query_intent=explain_decision은 Explanation W이며 retrieval_strategy=decision_trace와 evidence_mode를 함께 기록한다.

authority_confirmed trace는 origin W/실제 confirmation으로, reported trace는 exact I/D로 거슬러 올라간다. reported event를 사용자 commitment로 바꾸지 않는다. 과거 snapshot의 retrieval_mode 값은 재작성하지 않는다. 과거 세 evidence 값은 evidence_mode로 해석할 수 있지만 decision_trace 값만으로 evidence_mode를 추정하지 않는다. 정확한 inputs/기록으로 복원 불가하면 legacy read에서 unknown으로 표시하고 exact replay 불가를 명시한다. 새 W는 두 축을 모두 저장한다. 현재 DB가 없으므로 migration code는 생성하지 않는다.

## 검증·적용 경계

R01: AT14/15. R02: AT09–19/AT53. R03: AT01–05. R04: AT22–27/AT45–47. R05: AT28–36. R06: AT45–50/AT66. R09: AT51/52. R07/R08은 사용자 선택을 AT106/AT107과 연결했으며 실제 구현 시 해당 반례를 실행한다. 문서 정책/승인 상태 검증은 앱 동작 증명이 아니다.

이 계약의 나머지 P 세부 enum, materiality 수치, effect-only revalidation public subtype, 실제 schema/DB lock strategy, provider/stack/MinerU runtime 선택은 별도 미정이다. 지금은 설계 문제를 해소하는 범위이며 T01 전체나 앱 acceptance 완료를 뜻하지 않는다.
