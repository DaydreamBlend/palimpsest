# T01 — 현재 전체 구조 설계 검토

> 후속 U08 수정 상태는 [구조 해결 계약](../docs/decisions/ARCHITECTURE_FIXES.md)을 따른다. 아래 반례와 줄 번호는 검토 당시 [이전 통합 snapshot](../docs/history/2026-09-09_pre_architecture_fixes.md) 기준이며 수정 후 current 상태를 뜻하지 않는다.

검토일: 2026-09-09. 대상: U01–U07이 반영된 current canonical, 모듈/CLI/MinerU/retrieval 계약, P01–P12 제안, task/acceptance 명세. 현재 canonical SHA-256: `d22dddeabb21b222c3b81c00deebdb7141715223c53fed7be806527cb849f2fb`.

## 판단과 범위

D/I/K/W/P/B domain과 각 변환을 분리하고, 공통 저장·실행·transaction을 공유하는 큰 구조를 다시 나눌 근거는 찾지 못했다. 가장 큰 문제는 **현재 본문의 간략한 규칙과 이를 보완하는 미승인 계약이 서로 다른 실행 결과를 허용한다는 점**이다. 모듈 이름보다 current graph 판정, dependency 보존, 완료·commit 기준을 먼저 맞춰야 한다.

아래 R01–R09는 이 보고서 안의 식별자다. 기존 F/A/P ID나 승인 상태를 바꾸지 않는다. 7개 항목은 이전 F01–F26의 미해결 사항을 현재판에서 재확인·통합한 것이고, R07은 기존 동시성/Decision 문제를 확장한 새 경쟁 반례, R08은 새로 확인한 검색·보존 계약 불일치다. 실행 코드가 없으므로 관측된 앱 버그나 실제 데이터 손상으로 보고하지 않는다.

우선순위 P1은 해당 모듈의 schema/상태 전이를 구현하기 전에 확정할 계약, P2는 해당 검색/interface를 구현하기 전에 정리할 불일치를 뜻한다. 당장 운영 중인 시스템의 장애 등급이 아니다.

| 항목 | 우선순위 | 구분 | 관련 기존 계약 |
|---|---|---|---|
| R01 최신 부정 applicability 우선순위 | P1 | 기존 F05 재확인 | P02 |
| R02 semantic 무변화와 현재 dependency 갱신 분리 | P1 | 기존 F03/F04/F06/F07 재확인 | P02/P04 |
| R03 전파 완료의 관찰 범위 | P1 | 기존 F01 재확인 | P03/P05 |
| R04 identity 및 rejection cache 적용 순서 | P1 | 기존 F09/F10 재확인 | P01 |
| R05 commit freshness와 replacement 원자성 | P1 | 기존 F11/F13 재확인 | P05 |
| R06 명시적 Decision 대체의 atomic effect | P1 | 기존 F19 재확인 | P05/P06/P08 |
| R07 같은 Decision 범위의 병렬 대체 | P1 | F11/F19의 새 경쟁 반례 | P05/P08 |
| R08 rejected similarity와 payload cleanup | P2 | 새 설계 불일치 | P01/P09 보완 후보 |
| R09 retrieval_mode의 두 가지 의미 | P2 | 기존 F20 재확인 | P08/P11 |

## R01 — 최신 not_applicable을 초기 승인 조건이 무시할 수 있다

근거: [현재 KGraph](../docs/canonical/03_knowledge_graph.md), L206–212 및 L232–237. current edge 조건은 최초 endpoint가 current와 일치하거나 최신 applicability가 applicable이면 된다. 하지만 뒤에서는 not_applicable 결과가 edge를 current graph에서 제외한다고 규정한다.

반례: E1(A1, B1)을 같은 endpoint pair에 대해 not_applicable로 재판정한다. endpoint 일치 조건이 계속 참이므로 OR 규칙을 그대로 구현하면 E1이 검색·추론에 남는다.

최소 권고: exact semantic edge revision + endpoint pair의 최신 명시적 판정을 먼저 적용한다. 판정이 없을 때만 최초 승인으로 fallback하고 양 endpoint의 usability를 확인한다. [P02 제안](../docs/contracts/02_effective_relations_dependencies.md), L30–36에 이미 방향이 있으나 current canonical에 승인·동기화되지 않았다.

검증: AT14·AT15. 같은 pair의 positive→negative→positive, endpoint invalidation을 current/history 조회로 구분해 검사해야 한다.

## R02 — 의미가 그대로여도 현재 근거와 소비 의존성은 갱신해야 한다

근거: [Information 재검증](../docs/canonical/02_information.md), L129–150; [edge 무변화 처리](../docs/canonical/03_knowledge_graph.md), L220–225; [K2K의 endpoint 포함 projection](../docs/canonical/06_knowledge_operations.md), L143–152.

첫 반례: I1에서 K1을 만들고 I2가 I1을 대체한다. I2로 K1을 재검증해 의미가 같아 Record만 남긴 뒤 I2가 invalidated된다. 최초 provenance가 I1에 고정된 채 현재 I2→K1 dependency를 등록하지 않으면 두 번째 변경에서 K1을 찾지 못한다. 재검증 Record에 I2가 있다는 사실만으로 어떤 Record가 현재 support인지 정해지지는 않는다.

두 번째 반례: K2K가 관계와 함께 endpoint의 임계값 5를 읽어 결론 C를 만들었다. 임계값이 10으로 바뀌어도 supports 관계의 의미는 그대로일 수 있다. 관계만 dependency로 추적하고 non-material에서 끝내면 C는 오래된 값을 유지한다. pending edge를 최종적인 부정으로 해석해도 잘못된 invalidation이 생길 수 있다.

최소 권고: 최초 생성 provenance를 보존하면서 검증된 current support membership/receipt를 append-only로 갱신한다. 실제로 소비한 endpoint bundle을 추적하고, 이미 생긴 material input 변경 의무를 edge의 무변화 결과가 없애지 못하게 한다. 필수 입력 pending은 unknown/blocked로 다룬다. semantic Revision을 억지로 만드는 해결책은 필요하지 않다. [P04](../docs/contracts/05_compiler_validation_evidence.md), L15–17 및 [P02](../docs/contracts/02_effective_relations_dependencies.md), L40–48에 해결 방향이 있다.

검증: AT12·AT13·AT16·AT17·AT18·AT19. 특히 I1→I2→I3의 연속 교체, 의미 유지 후 근거 invalidation, endpoint 값을 소비한 경우와 관계만 소비한 경우를 나눈다.

## R03 — 현재 frontier만 비어서는 정상 완료를 증명할 수 없다

근거: [전파 완료 규칙](../docs/canonical/07_propagation.md), L55–59. 정상 완료 조건이 현재 frontier에 후속 material delta가 없다는 한 문장으로 제시되어 있다.

반례: A의 정확한 downstream C가 한 호출의 retrieval top-K 밖에 있거나, canonical effect는 commit됐지만 outbox가 아직 dispatch되지 않았다. 보이는 queue/frontier는 비어도 C의 검증 의무는 남는다. 반대로 생성기가 계속 새로운 명제를 만들면 fingerprint만으로 종료가 보장되지 않는다.

최소 권고: 의무 dependency revalidation과 새 지식 discovery를 분리한다. 특정 watermark/policy 범위에서 dependency 열거 완료, outbox·lease/in-flight·retry·blocked/human obligation 부재를 확인한 완료 receipt를 정의한다. 완료 확인과 동시 commit의 race도 막아야 한다. depth/크기/비용 cap을 성공 종료 조건으로 추가하는 권고가 아니다. [P03 제안](../docs/contracts/03_propagation_completion.md), L15–17 및 L38–46이 이 방향이다.

검증: AT01–AT05 및 실제 outbox/worker 통합. discovery에 후보가 없다는 결과와 모든 의무 작업 완료를 같은 상태로 합치지 않아야 한다.

## R04 — content fingerprint가 identity와 유효성보다 먼저 적용된다

근거: [Fingerprint 순서](../docs/canonical/05_identity_materiality.md), L10 및 L17–44. 같은 accepted content면 새 객체/Revision을 금지하고, grounding out-of-bounds를 전역 hard suppression 예시로 든다. context FP에는 Validator가 실제 사용한 refs가 들어간다.

반례: 같은 문장이 다른 D에서 나왔거나 서로 다른 Decision 사건에 속하면 별도 identity여야 한다. 과거의 동일 content가 현재도 usable하다는 보장도 없다. 또한 잘못된 locator로 기각된 후보와 locator를 고친 후보는 semantic content가 같아도 유효성이 다르다. 사후 used refs를 사전 cache key의 필수 입력으로 요구하면 Validator 실행 전에 key를 완성할 수 없다.

최소 권고: eligibility → domain identity → exact content → materiality 순서를 확정한다. source-specific I와 Decision event identity를 먼저 적용하고 historical match를 current reuse로 취급하지 않는다. 사전 frozen input/context/profile digest와 사후 used-ref audit을 분리하며 locator/schema/policy에 의존한 기각은 그 입력을 key에 포함한다. [P01 제안](../docs/contracts/01_identity_materiality.md), L21–39에 해결 방향이 있다.

검증: AT22–AT27 및 AT45·AT46. cache hit가 canonical validation/authority를 우회해서는 안 된다.

## R05 — 대상 CAS와 후보별 transaction만으로는 일관성이 부족하다

근거: [대상 revision CAS](../docs/canonical/03_knowledge_graph.md), L84; [D2I 후보 commit](../docs/canonical/01_data_d2i.md), L237; [다대다 I supersession](../docs/canonical/02_information.md), L75.

첫 반례: I1으로 K 후보를 검증하는 동안 다른 worker가 I1을 invalidated한다. 대상 K의 base가 그대로이면 target CAS는 성공하므로 이미 무효인 입력으로 새 K가 승인될 수 있다. 단순히 commit 전에 한 번 조회하는 것만으로는 그 조회 이후의 race까지 막는 계약이 되지 않는다.

두 번째 반례: I1을 I2+I3으로 split할 때 I2와 I1 supersession을 먼저 commit하고 I3 검증이 실패한다. I1이 이미 검색에서 빠지면 일부 의미가 사라진다.

최소 권고: 승인에 영향을 준 input lifecycle/applicability/evidence/authority의 read-set을 commit과 충돌 검출이 연결되는 방식으로 검증한다. 같은 교체 의미 단위의 replacement set은 전체 검증 뒤 activation과 old-I retirement를 한 transaction으로 수행한다. 모든 문서·모델 호출을 장기 transaction으로 묶거나 모든 D2I 후보를 일괄 commit하라는 뜻은 아니다. [P05 제안](../docs/contracts/04_transactions_execution.md), L21–25 및 L35–39를 구체화해야 한다.

검증: AT28·AT29·AT30·AT35·AT36을 실제 PostgreSQL/복수 worker/failpoint로 실행한다. split barrier와 AT35의 task 소유권은 이미 T05에 있어 작업 배치 자체가 누락된 것은 아니다.

## R06 — 사용자가 확정한 Decision 대체 관계가 commit unit에서 빠져 있다

근거: [Decision](../docs/canonical/08_wisdom_decisions.md), L173, L210–218, L257, L273–280. W에는 supersedes_decision_id가 있고 current decision status는 supersedes 관계에서 계산하지만, W2K atomic commit 목록에는 그 관계 생성이 없다.

반례: D1 대신 D2를 선택한다는 실제 확인을 받았다. W/K/Record는 저장됐지만 이후 N2E가 실패하거나 supersedes edge를 발견하지 못한다. 승인된 대체가 current graph에 반영되지 않아 두 결정이 모두 현행처럼 보일 수 있다.

최소 권고: 명시적으로 승인된 supersedes 요청의 대상·scope·시간 효력과 해당 관계/effect를 결정론적 command 경로 및 atomic unit에 포함한다. 누가 어떤 Record/effect로 기록하는지 P06/P08과 함께 정한다. W2K를 자유로운 관계 생성기로 확대하거나 LLM discovery에 의존할 필요는 없다. [P08 제안](../docs/contracts/06_decision_wisdom_publication.md), L29–33이 이미 해당 경로를 요구한다.

검증: AT49·AT50·AT66에 더해 supersedes 저장 직전 실패 시 전체 rollback, N2E 불가 상태에서의 명시적 대체 보존을 확인한다. future-effective/부분 scope는 전면적인 즉시 비활성화로 축약하지 않는다.

## R07 — 같은 범위의 병렬 Decision 대체에 대한 의미가 미정이다

근거: [Decision DAG](../docs/canonical/08_wisdom_decisions.md), L280; [confirmation event별 identity](../docs/contracts/06_decision_wisdom_publication.md), L15–17 및 시간·scope L31–33; [일반 identity/CAS guard](../docs/contracts/04_transactions_execution.md), L17.

새 경쟁 반례: 하나의 배타적 선택을 뜻하는 같은 subject/scope에서 D1을 기준으로 D2(A 선택)와 D3(B 선택)를 준비하고 서로 다른 유효한 confirmation event로 병렬 확정한다. D2와 D3는 서로 다른 새 Node여서 target revision CAS가 충돌하지 않고, D2→D1 및 D3→D1도 DAG다. 현재 계약에는 이때 단일 현행 결정, 병렬 현행 결정 또는 명시적 conflict 중 무엇을 반환할지 없다.

최소 권고: 해당 decision 범위와 준비 시 읽은 active-head 집합을 기준으로 stale confirmation을 재확인할지, 두 사건을 보존하면서 conflict로 노출할지 정한다. 모든 scope에 단일 active decision을 강제할 필요는 없다. 다만 배타적 선택 충돌을 timestamp로 조용히 덮거나 정상적인 단일 결론처럼 표시하지 않도록 해야 한다.

검증: AT28·AT29·AT49 인접 범위에 같은 head를 병렬 대체하는 transaction 시나리오를 추가할 필요가 있다. 기존 AT49는 미래 효력·부분 scope를 다루며 이 경쟁 사례를 직접 명시하지 않는다. 이는 F11/F19의 확장 반례이며 새 DB enum/constraint를 승인한 결과가 아니다.

## R08 — 기각 후보 삭제와 기각 후보 의미 유사도 검색 요구가 충돌한다

근거: [Compiler pipeline](../docs/canonical/04_compiler_records.md), L13·L44; 같은 파일의 terminal cleanup L284 및 audit 제한 L293–304; [임시 index cleanup](../docs/canonical/09_publication_retrieval.md), L98–99.

pipeline은 accepted/rejected similarity lookup과 근접 결과를 Validator 입력으로 요구한다. 그러나 rejected payload는 삭제하고 FP+reason만 남기며, 선택적 audit store는 RAG corpus가 아니고 임시 similarity index도 terminal cleanup한다.

반례: 과거 후보를 기각하고 cleanup한 뒤 FP는 다르지만 의미가 같은 표현으로 새 후보가 들어온다. exact FP lookup은 실패하고, 과거 후보와 의미를 비교할 보장된 데이터원이 없다. 선택적인 model_calls raw output 역시 지속 보존이나 검색 용도가 보장되어 있지 않아, 영속적인 rejected 근접 검색 계약을 대신하지 않는다. fingerprint에서 원문이나 의미 비교용 payload를 복원할 수는 없다.

최소 권고: 초기 구현은 rejected lookup을 정확한 scoped fingerprint에 한정하고 semantic similarity는 accepted 대상으로 명시하는 편이 작다. rejected 근접 검색이 필수라면 별도의 비canonical index/payload 보존 범위, 만료, 검색 불가 시 재검증 동작을 정해야 한다. 어느 쪽이든 기각된 내용을 canonical knowledge로 승격시키지 않는다.

검증: AT68·AT55는 cleanup/retention을 다루지만 cleanup 뒤 rejected near-duplicate의 동작은 별도 명세가 필요하다. F10/F21과 인접하나 기존 F01–F26에 이 데이터원 부재가 직접 등록되어 있지는 않다. 이번 리뷰에서 선택지를 확정하거나 보존 정책을 바꾸지는 않았다.

## R09 — retrieval_mode가 근거 종류와 조회 전략을 동시에 표현한다

근거: [Wisdom retrieval_mode](../docs/canonical/08_wisdom_decisions.md), L76과 L299. 앞에서는 knowledge_only/knowledge_plus_evidence/evidence_only를 허용하고, decision trace에서는 같은 필드에 decision_trace를 요구한다.

반례: 과거 결정을 추적하면서 K와 직접 I를 함께 사용한다. decision_trace만 저장하면 근거 surface를 잃고, knowledge_plus_evidence만 저장하면 trace 모드를 표현하지 못한다. reported decision은 origin Decision W가 없으므로 trace 경로도 구분해야 한다.

최소 권고: [P08 제안](../docs/contracts/06_decision_wisdom_publication.md), L37–41처럼 evidence surface와 retrieval strategy를 독립 축으로 정하고 current canonical/schema/CLI 결과를 함께 맞춘다. 새 필드 이름은 승인 전 제안이다. U07의 K2W 명칭 변경이 이 충돌을 만든 것은 아니다.

검증: AT51·AT52. decision_trace와 direct-I 사용을 동시에 기록하는 경우, reported/authority_confirmed 양쪽 trace를 포함한다.

## 유지해도 되는 구조와 적용 순서

- D/I/K/W/P/B는 의미·불변조건 경계이고 Artifact Store/Canonical Store/Compiler Runtime은 저장·실행 경계다. [모듈 계약](../docs/implementation/MODULE_BOUNDARIES.md)은 이 두 축을 구분하고 단일 애플리케이션·공통 commit을 유지하므로 domain마다 DB나 서비스를 추가할 필요가 없다.
- MinerU parse artifacts와 canonical I를 분리하고 원본 page/region provenance를 요구하는 경계는 일관된다. parser success를 I의 진실성 승인으로 취급하지 않는다.
- [검색 profile](../docs/interfaces/RETRIEVAL_PROFILE.md)은 Embedding과 Reranker를 독립 교체하고 BGE token vectors를 공통 인터페이스로 고정하지 않는다. embedding 공간 분리·파생 재색인·과거 결과 보존이 명시되어 있어 향후 Qwen 교체를 위해 domain을 재설계할 이유는 찾지 못했다. 실제 모델 성능·메모리·품질은 평가하지 않았다.
- CLI를 얇은 adapter로 두고 W2K를 결정론적으로 유지하며 W2P/P2B를 publication application 모듈로 분리한 방향도 일관된다. 새 Compiler Record subtype이나 GUI 선행 구현을 추가할 근거는 없다.
- 파일/DB dual write, 사용자 원문·모델 출력의 trust boundary, publication 재수입 lineage, 같은 모델의 Validator 오류 상관 문제는 제안 계약에 보완 방향이 이미 있다. 설계가 전혀 없다는 별도 finding으로 중복 등록하지 않았다.

T01에서는 우선 P01/P02/P04/P05의 identity·현재 상태·effect/commit 계약과 P06 registry를 맞추고, 전파 연결 전 P03 완료 계약을 확정하는 순서를 권고한다. Decision 기능 전에는 P08의 명시적 supersession·동시 결정·retrieval 축을 잠가야 한다. R08의 기각 검색 범위는 compiler/retrieval 구현 전에 작게 선택할 수 있다. U01–U07은 재승인 대상이 아니고, 이 보고서가 P 전체 승인이나 미정 stack 선택을 대신하지 않는다.

## 검증과 한계

root와 세 개의 독립 읽기 전용 검토가 위 범위를 나눠 확인했다. 근거 줄·반례·기존 F/P/AT 연결을 root가 대조했다. 문서 검증 결과와 정확한 명령은 [T01 실행 기록](T01_execplan.md)의 이번 검토 절에 남긴다.

현재 앱 구현이 없어 domain/모델 mock 실행, 실제 PostgreSQL 동시성, MinerU parsing, end-to-end, live semantic evaluation은 수행하지 않았다. 모든 앱 acceptance 105개는 spec_only이며 본 리뷰로 pass/complete 처리하지 않는다. 기존 문서 도구 테스트 33개는 직전 U07 작업에서 통과했고, 이번에는 도구 코드 변경이 없어 재실행하지 않는다.

변경은 이 보고서, T01 실행 기록 및 STATUS의 검토 링크에 한정한다. 원본/현재 canonical·결정 JSON·코드·task/acceptance 상태는 바꾸지 않는다.
