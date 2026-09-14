# 설계 재검토 — Codex 개발 인계 전

> 이 검토의 원문/줄 번호/옛 구성요소명은 `docs/source/`의 수정 전 baseline 기준이다. 현재 개발 지시는 U01–U03을 반영한 `docs/canonical/`을 따른다. 검토 항목 자체를 이번 세 요청으로 승인한 것은 아니다.

> 상태: REVIEW / 모든 보완안은 제안이며 기존 A1–A40의 승인 기록을 변경하지 않습니다.

## 판단

큰 구조를 다시 바꿀 필요는 없습니다. 다만 지금 파일을 그대로 구현 명령으로 사용하면, 같은 문서를 따른 두 구현이 서로 다른 current graph와 종료 판정을 만들 수 있습니다. 특히 cap 없는 propagation 자체보다 **검증해야 할 대상의 완전한 열거, materiality 기준, effective edge input, 재검증 후 현재 근거, commit 시점의 freshness**가 우선입니다.

이 검토는 최신 2026-09-09 기준본 전체 2,331줄을 대상으로 합니다. 실제 저장소·구현 코드·실험 결과는 제공되지 않아 확인하지 않았습니다. 아래 반례는 설계에서 도출한 모델의 분석이며, 관측된 구현 버그가 아닙니다. P0는 관련 DB/worker 계약을 확정하기 전 해결할 사항, P1은 해당 기능을 구현·운영하기 전 해결할 사항입니다.

“Convergent”는 운영 목표이지 현재 문서만으로 얻은 수학적 종료 증명이 아닙니다. 이번 보완안도 크기·깊이·비용 cap을 정상 종료 조건으로 복원하지 않습니다.

## F01 · P0 — 현재 명세의 “fixed point”는 전역 수렴 보장이 아닙니다

**근거:** §15.1, §17.3–17.6; [기준본 L1345–L1588](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 완료 조건 미정.

**문제:** RAG top-K로 찾은 후보의 처리가 끝난 것과 모든 필수 의존성의 영향 검증이 끝난 것은 다릅니다. 생성기가 항상 새로운 K를 제안할 수도 있어 fingerprint와 material-delta gate만으로 종료가 증명되지는 않습니다.

**반례:** A→B의 정확한 dependency가 있지만 B가 retrieval top-K 밖에 있으면 queue가 비어도 B는 미검증입니다. 반대로 서로 다른 새 proposition이 끝없이 생성되면 exact duplicate guard는 작동하지 않습니다.

**권고:** 의무적인 dependency revalidation과 선택적인 discovery를 구분하십시오. source watermark, 정책 snapshot, 미처리 outbox/leased job/blocked review 수와 dependency enumeration coverage를 기록한 “해당 범위의 quiescence”로 완료를 정의합니다. 전체 가능한 지식의 고정점을 찾았다고 주장하지 않습니다. 용량·깊이 cap은 추가하지 않습니다.

**연결:** 승인 후보 `P03`; 검증 시나리오 `AT01`, `AT02`, `AT03`, `AT04`, `AT05`.

## F02 · P0 — 무시 가능한 변화의 판정 기준이 구현 계약으로 내려오지 않았습니다

**근거:** §11.3, §12, §17.2; [기준본 L1129–L1238](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 구현 공백.

**문제:** Validator의 단일 boolean이나 embedding score로 materiality를 대신하면 scope·극성·권한 변화가 누락되거나 paraphrase revision이 증가합니다. 작은 변화가 누적되는 경우도 빠집니다.

**반례:** 수치 후보가 0.01씩 바뀔 때 직전 기각 후보를 기준으로 비교하면 누적 1.0의 변화도 영원히 무시될 수 있습니다.

**권고:** 항상 current accepted semantic snapshot과 비교하십시오. kind별 identity/payload schema, changed paths, 중요 필드, 단위와 수치 tolerance 정책을 정의합니다. policy version과 근거를 보존하고, 부정·적용범위·결정 actor/행위는 작은 문자열 차이로 무시하지 않습니다. tolerance의 실제 값은 평가 후 승인합니다.

**연결:** 승인 후보 `P01`; 검증 시나리오 `AT06`, `AT07`, `AT08`.

## F03 · P0 — Revision 없는 edge rebasing에 필요한 exact input 식별자가 빠져 있습니다

**근거:** §7.6, §9.2, §15.3, §18.4, §24; [기준본 L708–L771](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 참조 계약 불완전.

**문제:** 같은 E1을 A1/B1과 A2/B1에서 사용할 수 있는데 Record/Wisdom에 E1만 남으면 실제 사용한 관계 상태를 복원할 수 없습니다. embedding key도 E1만 사용하면 재생성 대상을 놓칩니다.

**반례:** E1의 원래 endpoint는 A1/B1입니다. applicability event가 A2/B1에서도 적용 가능하다고 승인했습니다. 새로운 W가 E1만 인용하면 과거 endpoint와 실제 endpoint 중 어느 것을 사용했는지 알 수 없습니다.

**권고:** EffectiveEdgeRef를 구현용 typed input bundle로 제안합니다: semantic edge revision + exact effective endpoint pair + applicability evidence ref. 새로운 canonical EdgeRevision을 만들지 않습니다. compiler inputs, W citations, retrieval projection key, replay에 이 묶음을 함께 보존합니다.

**연결:** 승인 후보 `P02`; 검증 시나리오 `AT09`, `AT10`, `AT11`.

## F04 · P0 — 관계가 그대로여도 그 관계를 이용한 결론이 그대로라고 보장할 수 없습니다

**근거:** §7.6, §15.3, §17.2; [기준본 L708–L771](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 전파 barrier의 전제 누락.

**문제:** K2K context에는 edge predicate뿐 아니라 endpoint 문장이 포함됩니다. supports가 유지됐다는 사실만으로 과거 결론이 소비한 endpoint 값까지 같다고 볼 수 없습니다.

**반례:** C가 E1의 from-node 문장에 있는 임계값 5를 사용했습니다. A2에서 그 값이 10으로 바뀌어도 supports 관계는 유지됩니다. edge-only dependency라면 C가 누락됩니다.

**권고:** 실제로 소비한 node revision/field projection도 의존성으로 등록하십시오. A의 material change가 C를 직접 재검증 대상으로 만들고, edge의 no_material_delta는 그 edge 자체에서 추가 semantic cascade를 만들지 않는 뜻으로 한정합니다. 무조건 모든 incident consumer를 재작성하지 않습니다.

**연결:** 승인 후보 `P02`; 검증 시나리오 `AT12`, `AT13`.

## F05 · P0 — Applicability의 OR 조건이 최신 부정 판정을 무시할 수 있습니다

**근거:** §7.6; [기준본 L737–L771](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 규칙 충돌 위험.

**문제:** 현재 조건 A(원래 endpoint와 현재 endpoint 일치) OR B(최신 applicable)는 원래 pair에 대한 최신 not_applicable event가 있어도 A만으로 edge를 살릴 수 있습니다. endpoint lifecycle 확인도 명시적으로 필요합니다.

**반례:** E1(A1,B1)이 처음 승인된 뒤 같은 pair가 not_applicable로 재판정되어도 current endpoint가 A1/B1이면 A가 참입니다.

**권고:** 동일 semantic revision + exact pair에 대한 최신 명시적 판정을 먼저 적용합니다. not_applicable은 초기 승인을 override합니다. 판정이 없을 때만 원래 approval을 fallback으로 사용합니다. logical edge와 양 endpoint의 현재 usability도 검사합니다.

**연결:** 승인 후보 `P02`; 검증 시나리오 `AT14`, `AT15`.

## F06 · P0 — 일시적인 edge 숨김과 최종적인 관계 소멸이 구분되어야 합니다

**근거:** §7.6, §14.2, §17.2; [기준본 L1276–L1343](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 비동기 상태 공백.

**문제:** pending_revalidation 동안 current graph에서 edge를 숨기면, consumer가 이를 “관계가 없다”는 새 근거로 오해해 불필요한 invalidation을 만들 수 있습니다. 이후 applicable은 non-material이므로 이미 발생한 잘못된 변경이 복구되지 않을 수도 있습니다.

**반례:** A2 commit 직후 E1은 잠시 숨겨집니다. C의 revalidation이 먼저 실행되어 “지지 edge 없음”으로 C를 무효화합니다. 이후 E1 applicable event는 branch를 종료합니다.

**권고:** pending은 false가 아니라 unknown입니다. 필수 edge 판정을 기다리는 consumer를 dependency-blocked로 두고, applicable 결과는 semantic propagation 없이 기존 blocked obligation을 해제합니다. not_applicable은 이전 confirmed state와 비교해 실제 변화일 때만 material event를 만듭니다.

**연결:** 승인 후보 `P02`; 검증 시나리오 `AT16`, `AT17`.

## F07 · P0 — I 교체 후 K가 그대로여도 현재 근거의 교체 이력은 필요합니다

**근거:** §6.6, §9.2, §17.2; [기준본 L501–L528](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 근거 추적 누락.

**문제:** K 의미가 그대로라서 no_material_delta로 끝내더라도 새 I가 그 K를 지지한다는 현재 dependency를 남기지 않으면 다음 I 교정에서 그 K를 찾을 수 없습니다.

**반례:** I1→K1, I2 supersedes I1, 재검증 결과 K1 유지. 이후 I2가 invalidated되었는데 K1의 origin input은 I1뿐이어서 직접 영향 조회에 잡히지 않습니다.

**권고:** 생성 당시 provenance는 그대로 유지하되, successful revalidation의 새 근거 refs와 현재 support/dependency 상태를 append-only certificate/effect로 남깁니다. semantic Revision은 만들지 않으며 새 I를 검증 없이 grounding으로 덧붙이지 않습니다.

**연결:** 승인 후보 `P04`; 검증 시나리오 `AT18`, `AT19`.

## F08 · P1 — 근거 변화가 항상 non-material이라는 분류는 너무 넓습니다

**근거:** §7.2, §12.1, §17.2; [기준본 L1507–L1532](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 정책 보완.

**문제:** 새 grounding 행은 비의미적 effect일 수 있지만 support의 상실·복구 또는 충분성 변화는 usability/epistemic projection을 바꿀 수 있습니다. downstream이 이 상태를 사용하는 경우 별도 영향이 생깁니다.

**반례:** K의 문장은 유지되지만 유일한 유효 근거가 철회되어 unsupported가 됩니다. 문장이 같다는 이유만으로 재검증을 모두 멈추면 recommendation이 과거 지지도를 그대로 사용할 수 있습니다.

**권고:** grounding row 추가와 evidence-state change를 구분합니다. projection maintenance는 semantic revision 없이 수행합니다. 실제 소비되는 validity/evidence state가 달라지는 경우만 명시적 material effect를 승인합니다. 단순 support 개수 증가만으로 무조건 전파하지 않습니다.

**연결:** 승인 후보 `P04`; 검증 시나리오 `AT20`, `AT21`.

## F09 · P0 — Fingerprint의 일반 규칙이 I/Decision의 예외를 다시 덮습니다

**근거:** §5.3, §11.2, §20.3; [기준본 L1095–L1127](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 본문 규칙 충돌.

**문제:** §11.2는 same accepted content FP이면 새 객체 금지라고 쓰지만 다른 D의 I와 다른 사건의 Decision은 예외여야 합니다. historical/invalidated 객체도 exact content가 같다고 현재 값으로 재사용할 수는 없습니다.

**반례:** D1/I1과 D2/I2는 동일 문장이어도 별도 I여야 합니다. 현재 K=A2인데 candidate가 과거 A1과 같다고 A1으로 무조건 재사용하면 current-state 의미가 불명확합니다.

**권고:** 전역 FP 조회보다 object-domain eligibility와 identity scope를 먼저 검사합니다. current usable reuse, historical match, reactivation/correction을 구분합니다. 후보 Record의 FP는 lookup index이며 모든 Record에 무조건 UNIQUE(content_fp)를 걸지 않습니다.

**연결:** 승인 후보 `P01`; 검증 시나리오 `AT22`, `AT23`, `AT24`.

## F10 · P1 — Hard rejection과 context fingerprint의 실행 시점이 맞지 않습니다

**근거:** §5.2, §9.2, §11.2; [기준본 L1082–L1127](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 검증 cache 설계 공백.

**문제:** grounding out-of-bounds는 D/locator에 종속되고 forbidden kind는 schema/policy에 종속됩니다. semantic content만으로 전역 영구 기각하면 정상 재시도까지 막힙니다. “Validator가 실제 사용한 refs”는 실행 후에야 알 수 있어 사전 suppression key로 바로 쓸 수 없습니다.

**반례:** 같은 주장에 잘못된 locator를 붙인 후보를 기각한 뒤 올바른 locator를 붙인 후보도 semantic content FP가 같아서 막힐 수 있습니다.

**권고:** 사전 검증용 frozen input/context snapshot digest와 사후 사용 근거를 분리합니다. deterministic failure key에는 위반을 결정하는 locator, D, schema, policy를 포함합니다. provider 오류는 epistemic rejection이 아니라 execution failure입니다. timestamp/Record ID만 달라서 semantic work key가 매번 달라지지 않게 합니다.

**연결:** 승인 후보 `P01`; 검증 시나리오 `AT25`, `AT26`, `AT27`.

## F11 · P0 — Expected-base CAS만으로 stale validation을 막을 수 없습니다

**근거:** §7.3, §9.2; [기준본 L594–L625](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 동시성 계약 부족.

**문제:** 수정 대상 current revision이 그대로여도 LLM 검증 중 입력 I/K/edge applicability/authority가 변경될 수 있습니다. 대상 CAS만 통과하면 오래된 근거로 승인될 수 있습니다.

**반례:** K1을 만들기 위해 읽은 I1이 Validator 실행 중 invalidated되었습니다. 대상 K의 base는 변하지 않아 CAS는 성공합니다.

**권고:** LLM 호출 전에 exact read-set과 관련 state tokens를 고정하고, 짧은 commit transaction에서 target base와 authoritative input freshness/authority를 함께 확인합니다. stale result는 성공 승인하지 않고 새 snapshot으로 재검증합니다. LLM 호출 동안 DB lock을 유지하지 않습니다.

**연결:** 승인 후보 `P05`; 검증 시나리오 `AT28`, `AT29`, `AT30`.

## F12 · P0 — Record·execution·outbox·root 사이의 재시도 계약이 미완성입니다

**근거:** §5.2, §9.4, §17; [기준본 L240–L371](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 실행 상태·원자성 공백.

**문제:** 한 LLM 호출에서 여러 proposal Record가 생깁니다. 같은 attempt FP를 Record별 unique로 두면 batch를 저장할 수 없습니다. failed/pending attempt를 visited라고 suppress해서도 안 됩니다. 한 job에 여러 causal roots가 합쳐질 수도 있습니다.

**반례:** canonical commit은 성공했지만 worker가 ACK 전에 종료되어 event가 재전달됩니다. 다른 경우에는 두 root가 같은 target 재검증을 동시에 요청합니다.

**권고:** 호출 단위 operation_executions와 proposal Record를 구분하고, commit/outbox 원자성·consumer dedup·lease 만료·재개·fan-in 원인 보존을 명세합니다. 동일 계산은 한 번 공유하되 대기 중인 모든 causal obligation을 완료시킵니다. logical exactly-once effect를 provider 호출 exactly-once로 표현하지 않습니다.

**연결:** 승인 후보 `P05`; 검증 시나리오 `AT31`, `AT32`, `AT33`, `AT34`.

## F13 · P0 — Information split/merge의 원자성 단위가 proposal보다 큽니다

**근거:** §5.4, §6.3; [기준본 L357–L449](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 다대다 교체의 원자성 공백.

**문제:** proposal별 commit에서 첫 replacement만 승인해 old I를 retire하면 나머지 replacement가 실패하는 동안 의미 일부가 검색과 K 근거에서 사라질 수 있습니다.

**반례:** I1을 I2+I3으로 split합니다. I2와 I1 supersession은 commit됐지만 I3 검증은 실패했습니다. I1은 이미 기본 검색에서 제외됩니다.

**권고:** 교체 집합의 coverage와 성공 여부를 검증한 뒤 replacement activation과 old-I retirement를 하나의 transaction으로 수행합니다. generation/교체 manifest는 runtime support 구조로 두고 금지된 D2IRun domain을 부활시키지 않습니다. 정상 zero-output을 기존 I 전량 삭제로 해석하지 않습니다.

**연결:** 승인 후보 `P05`; 검증 시나리오 `AT35`, `AT36`.

## F14 · P1 — 새 effect와 revalidation subtype이 Record schema에 완전히 반영되지 않았습니다

**근거:** §6.6, §9.1–9.3, §10, §14.2; [기준본 L846–L1016](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 명시적으로 미정인 schema blocker.

**문제:** 정보 기반 K 재검증 subtype 이름은 미정입니다. N2E는 edge 생성 외 applicability effect도 내지만 subtype 표는 Revision 출력만 나타냅니다. no_material_delta의 Bibliotheca 변경 없음도 applicability append와 충돌합니다.

**반례:** no_longer_valid를 rejected로 저장할지, approved effect로 저장할지 구현자마다 달라질 수 있습니다. candidate payload가 없는 effect에도 기존 Record 필수 필드를 강제로 채울 수 있습니다.

**권고:** Operation mode, 검증 결과, disposition, canonical effects, propagation impact의 합법 조합을 결정표로 확정하십시오. public subtype 이름과 새 disposition 추가는 승인 전에 가정하지 않습니다. 이름 미정의 기능은 port/test spec까지만 준비할 수 있습니다.

**연결:** 승인 후보 `P06`; 검증 시나리오 `AT37`, `AT38`.

## F15 · P1 — Predicate 변경과 graph cycle 금지 범위가 충돌합니다

**근거:** §7.4–7.5, §14.2–14.3; [기준본 L1276–L1343](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** identity·용어 충돌.

**문제:** predicate는 edge identity의 일부인데 changed 결과가 predicate 변경도 같은 edge Revision 후보로 기술합니다. “semantic transition graph의 cycle 금지” 문구는 일반 semantic graph 전체의 DAG 제약으로 오독될 수 있습니다.

**반례:** A supports B가 A qualifies B로 바뀌면 identity가 달라집니다. 반면 서로 다른 주장이 상호 supports하는 graph cycle은 supersession cycle과 동일한 오류가 아닙니다.

**권고:** predicate 변경은 old relation applicability/lifecycle 처리와 새 logical KEdge acceptance로 표현합니다. DAG 제약은 Information/Decision supersession 등 명시된 ordering 관계와 causal provenance에 한정합니다. 일반 semantic cycle은 evidence 순환 검토 대상이지 일괄 DB 금지 대상이 아닙니다.

**연결:** 승인 후보 `P06`; 검증 시나리오 `AT39`, `AT40`.

## F16 · P1 — K identity와 병렬 주장·entity resolution 기준이 아직 없습니다

**근거:** §7.2, §11, §12; [기준본 L546–L615](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** domain schema 공백.

**문제:** scope/시간이 달라진 주장을 항상 같은 Node Revision으로 만들면 동시에 유효한 조건별 지식 중 하나가 current graph에서 사라질 수 있습니다. 동명이인·별칭·단위도 FP 이전에 해결해야 합니다.

**반례:** “성인에서 X”와 “소아에서 not X”가 서로 대체 가능한 Revision인지, 공존해야 할 두 proposition인지 정의되어 있지 않습니다.

**권고:** kind별 stable identity projection, 별칭/외부 식별자, 조건별 공존과 정정의 구분을 예제 기반으로 고정합니다. entity merge는 historical IDs rewrite가 아니라 별도 검토 대상입니다. 구현 언어 선택보다 먼저 fixture로 경계를 확인합니다.

**연결:** 승인 후보 `P01`; 검증 시나리오 `AT41`, `AT42`.

## F17 · P1 — 서로 다른 Data 수는 독립 근거 수와 같지 않습니다

**근거:** §4.5, §7.2, §15.2; [기준본 L580–L591](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** epistemic 평가 공백.

**문제:** 동일 실험의 preprint·최종 논문·리뷰·웹 요약은 다른 bytes와 다른 D여도 독립 실험이 아닙니다. K2K가 파생 지식을 다시 세면 독립 support가 부풀려집니다.

**반례:** 논문 한 편, 그 논문을 인용한 리뷰 두 편, 사용자가 생성한 요약 하나를 네 개의 독립 근거로 계산합니다.

**권고:** Data identity는 유지하되 source-work/study/evidence-family linkage를 별도 provenance metadata로 제안합니다. transitive leaf evidence를 집합으로 합치고 독립성이 unknown이면 unknown으로 둡니다. derivation depth는 최소 경로와 결합 추론 경로를 구분하고 숫자를 진실성 점수로 쓰지 않습니다.

**연결:** 승인 후보 `P07`; 검증 시나리오 `AT43`, `AT44`.

## F18 · P0 — Decision confirmation의 중복 방지는 Wisdom 생성 전부터 필요합니다

**근거:** §19.2, §20.3; [기준본 L1720–L1817](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** authority·idempotency 공백.

**문제:** origin_wisdom_id UNIQUE는 W가 이미 만들어진 이후의 retry만 막습니다. 같은 승인 클릭을 두 번 수신해 W1/W2를 만들면 서로 다른 event로 잘못 기록됩니다.

**반례:** 사용자가 한 번 승인했는데 네트워크 retry로 두 개의 wisdom_id가 발급됩니다. 현재 규칙은 두 KNode를 만드는 것이 맞다고 해석합니다.

**권고:** confirmation event ID/idempotency key를 actor와 정확한 structured payload digest에 결합합니다. 같은 event 재전달은 같은 W를 반환하고, 내용이 다른 재사용 key는 거부합니다. 진짜 재결정은 새로운 confirmation event이므로 내용이 같아도 별도 W/K를 만듭니다.

**연결:** 승인 후보 `P08`; 검증 시나리오 `AT45`, `AT46`, `AT47`.

## F19 · P1 — Decision의 정정·보류·효력·supersession 적용 규칙이 부족합니다

**근거:** §19.2, §20.4–20.5; [기준본 L1720–L1871](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 시간·권한 계약 공백.

**문제:** K payload에 origin_type 코드 행이 빠져 있고 defer_until/defer_condition의 투영 방식도 명시되지 않았습니다. immutable W에서 파생된 K를 정정할 때 재승인 경계가 불명확합니다. 미래 효력의 새 결정이 이전 결정을 즉시 비활성화하면 안 됩니다.

**반례:** 10월 1일부터 적용할 D2가 9월에 승인됐을 때 D1을 즉시 superseded로 표시하거나, “보류” 조건을 K에서 잃어버릴 수 있습니다.

**권고:** action별 필수/금지 필드와 W→K mapping을 확정합니다. 실제 commitment 변경은 새 Decision이고 기록 정정은 authority-bound correction입니다. explicit supersession은 LLM discovery 실패로 누락되지 않도록 deterministic command path를 결정하고, partial scope/effective time/as-of 규칙을 따로 둡니다.

**연결:** 승인 후보 `P08`; 검증 시나리오 `AT48`, `AT49`, `AT50`.

## F20 · P1 — retrieval_mode가 두 가지 독립 축을 한 enum에 담습니다

**근거:** §18.2, §18.4, §21.1; [기준본 L1592–L1930](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 명시적 enum 충돌.

**문제:** Wisdom의 retrieval_mode는 knowledge_only/knowledge_plus_evidence/evidence_only라고 정의되지만 decision trace는 같은 필드에 decision_trace를 요구합니다. reported decision에는 origin Decision W가 없어 trace 순서도 그대로 적용되지 않습니다.

**반례:** 과거 결정을 설명하면서 당시 K와 직접 I를 동시에 볼 때 retrieval_mode를 하나만 고를 수 없습니다.

**권고:** evidence surface와 retrieval strategy를 두 축으로 분리하는 안을 제안합니다. 기존 이름의 migration/compatibility는 승인 후 확정합니다. authority_confirmed는 W/confirmation으로, reported는 I/D로 trace를 분기하며 사실과 사용자 이유를 혼동하지 않습니다.

**연결:** 승인 후보 `P08`; 검증 시나리오 `AT51`, `AT52`.

## F21 · P1 — Projection freshness와 historical replay 범위가 미정입니다

**근거:** §7.3.1, §15.3, §18.4, §24; [기준본 L2001–L2035](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 읽기 일관성·재현 공백.

**문제:** current pointer는 바뀌었는데 embedding이 아직 갱신되지 않았을 수 있습니다. event created_at만으로 동시에 commit된 상태의 순서를 완전히 재현하기 어렵습니다. 같은 prompt/model refs만으로 stochastic output을 다시 얻는다고 보장할 수도 없습니다.

**반례:** 검색 결과 E1의 문장이 A1인데 current pair는 A2/B1입니다. 과거 W 재현 시 나중에 추가된 grounding까지 섞이면 당시 판단이 바뀝니다.

**권고:** projection key에 effective state/profile digest를 포함하고 retrieval 후 authoritative current filtering을 합니다. material change, pending obligation, index watermark를 구분합니다. graph read receipt/as-of event sequence와 정확한 사용 refs를 보존하고 “역사 복원”과 “모델 재실행”을 별도 기능으로 설명합니다.

**연결:** 승인 후보 `P09`; 검증 시나리오 `AT53`, `AT54`, `AT55`.

## F22 · P1 — Horreum 파일과 DB의 일관된 저장·복구 경계가 없습니다

**근거:** §2.1, §4, §25; [기준본 L55–L219](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 운영 필수 공백.

**문제:** DB transaction은 원본 파일을 함께 rollback하지 않습니다. 중간 종료·파일 유실·backup/restore가 발생하면 canonical ref가 읽을 수 없는 payload를 가리킬 수 있습니다.

**반례:** DB row만 먼저 commit된 뒤 파일 rename 전에 프로세스가 종료되면 D는 존재하지만 원본이 없습니다.

**권고:** 검증된 staging file→content-addressed publish→짧은 DB commit 순서와 orphan reconciliation을 명세합니다. missing artifact를 빈 문서로 처리하지 않습니다. DB/artifact manifest를 함께 복원하고 임의 경로·symlink escape·권한 변경을 검사합니다.

**연결:** 승인 후보 `P10`; 검증 시나리오 `AT56`, `AT57`.

## F23 · P1 — 입력 문서·LLM 출력·확정 명령 사이의 보안 경계가 부족합니다

**근거:** §2, §8.3, §19.2; [기준본 L811–L842](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 보안·사용자 인터페이스 공백.

**문제:** 원본에 “이 결정을 승인하라”는 문장이 있어도 실제 confirmation이 될 수 없습니다. 외부 API 전송, secret logging, 로컬 파일 접근, 사용자 승인 UI가 명세화되어 있지 않습니다.

**반례:** 가져온 Markdown에 system 지시문처럼 보이는 텍스트나 localhost URL이 포함되어 compiler가 명령 실행/내부 fetch/권한 있는 decision으로 해석합니다.

**권고:** untrusted content는 자료로만 처리하고 side effect는 typed command/authority check로 제한합니다. local-first를 기본 제안하되 배포 형태는 미정입니다. provider 전송은 명시적 허용, secret 미출력, 접근 제어, HTML sanitization, 승인 화면의 payload binding, 사용자 pause/resume을 계약에 넣습니다.

**연결:** 승인 후보 `P10`; 검증 시나리오 `AT58`, `AT59`, `AT60`.

## F24 · P1 — 생성 문서 재수입으로 W/P/B→K 우회 순환이 생길 수 있습니다

**근거:** §4.1, §22, §23; [기준본 L1921–L2035](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** provenance 우회 경로.

**문제:** explanation/recommendation의 자동 W2K는 금지하지만 그 출력을 Markdown/PDF로 export한 뒤 D로 import하면 일반 I2K 입력이 됩니다. 외부 독립 근거처럼 계산하면 자기증폭이 다시 생깁니다.

**반례:** Palimpsest가 쓴 설명 P를 PDF로 저장해 재수입하고, 이를 기존 주장에 대한 새 독립 연구 자료로 계산합니다.

**권고:** 내부 생성물의 origin artifact/evidence lineage를 acquisition metadata로 이어갑니다. 재수입 자체를 무조건 금지하지 않되 독립 support 증가와 authority promotion을 금지합니다. P/B 편집의 새 주장에는 직접 근거 또는 author-added/ungrounded 표시를 요구합니다.

**연결:** 승인 후보 `P07`; 검증 시나리오 `AT61`, `AT62`.

## F25 · P1 — 원본에 이미 상충하는 문장과 누락된 field 설명이 남아 있습니다

**근거:** §5.2, §10, §11.2, §14.2, §20.4, §26; [기준본 L230–L2331](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 편집 잔재·규약 정합성.

**문제:** §5.2의 D당 1회 성공 문장이 generation 규칙과 충돌합니다. no_material_delta=Bibliotheca 변경 없음, predicate 변경=같은 edge Revision, 재사용 전역 규칙, retrieval_mode 충돌도 남아 있습니다. canonical 용어 표에 추가된 event가 누락되어 있습니다.

**반례:** 서로 다른 Codex 작업이 각각 다른 절을 읽으면 양쪽 모두 문서를 따른다고 주장하면서 상반된 코드를 생성할 수 있습니다.

**권고:** 원본은 그대로 보존하고 ERRATA.md에 정확한 정정 후보를 모았습니다. T01에서 기존 A1–A40과 대조해 승인된 문구만 기준본에 반영하고 분할본을 재생성합니다. 조용히 이전 결정을 덮어쓰지 않습니다.

**연결:** 승인 후보 `P11`; 검증 시나리오 `AT63`.

## F26 · P1 — 구현·평가·릴리스 경계가 없어 전체를 한 번에 맡기기 어렵습니다

**근거:** §29–30; [기준본 L2274–L2315](../source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md). **분류:** 개발 위임 공백.

**문제:** 언어/기존 repo 상태/DB migration 도구/provider/모델/UI가 확정되어 있지 않습니다. 또한 unit 통과, DB 경쟁 조건 통과, LLM 의미 평가 통과는 다른 완료 조건입니다.

**반례:** Codex가 빈 repo라고 가정하고 기존 코드를 교체하거나, mock 테스트만 통과한 것을 end-to-end/의미적 정확성 완료로 보고할 수 있습니다.

**권고:** 기존 repo inventory를 첫 작업으로 두고 환경을 먼저 확인합니다. 단계별 tasks, approved decision register, fixture/evaluation catalog, source-to-test traceability와 독립 review를 연결합니다. 실제 LLM 호출/운영 데이터 migration은 별도 승인하며 본 묶음의 validator는 문서 품질 검증일 뿐 앱 테스트가 아닙니다.

**연결:** 승인 후보 `P12`; 검증 시나리오 `AT64`, `AT65`.

## 권장 처리 순서

T00에서 실제 저장소를 조사하고, T01에서 P0와 본문 충돌을 계약으로 잠근 뒤 작은 D→I→K vertical slice를 구현하십시오. Edge/전파는 effective input과 completion contract가 잠긴 다음에 추가합니다. UI·실제 provider·대규모 ingestion·문서 출판을 첫 작업에 한꺼번에 묶지 않습니다. 모든 제안을 일괄 승인할 필요는 없으며, 거부된 제안의 관련 작업만 다시 계획하면 됩니다.
