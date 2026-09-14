# 원본의 문구 충돌·정정 후보

> 이 검토의 원문/줄 번호/옛 구성요소명은 `docs/source/`의 수정 전 baseline 기준이다. 현재 개발 지시는 U01–U03을 반영한 `docs/canonical/`을 따른다. 검토 항목 자체를 이번 세 요청으로 승인한 것은 아니다.

> 상태: PROPOSED · P11. 아래는 원본에서 실제 확인한 잔재와 권장 replacement입니다. 원본 파일은 수정하지 않았습니다. 의미 선택이 필요한 부분은 연결된 P 항목의 승인이 먼저 필요합니다.

## E01 · §5.2 / 원본 L309

문구: “일반 D2I의 D당 1회 성공도 …”

권장: “동일 logical compilation generation의 exactly-once canonical effect도 execution log와 atomic idempotency guard로 보장한다.”

§5.1과 A24/A28의 generation 규칙에 맞춘 편집 정정입니다.

## E02 · §10 terminal 표

문구: `no_material_delta`의 Bibliotheca 열 = “변경 없음”.

권장: “semantic Revision 없음; 검증된 applicability/support receipt 등 non-material effect는 가능”.

§7.6에서 no_material_delta 결과로 applicability event를 append하는 규칙과 맞춥니다. P04/P06과 합의해야 합니다.

## E03 · §11.2 same accepted content FP

문구: “reused, 새 객체/Revision 금지”.

권장: “domain별 identity/reuse eligibility를 통과한 current usable accepted semantic state만 reuse; Information source-specific identity와 Decision event identity는 우선 적용”. P01에 연결합니다.

## E04 · §11.2 invariant-hard examples

문구: grounding out-of-bounds와 forbidden kind를 context 무관 전역 hard로 예시.

권장: locator/schema/policy 등 위반 결정 입력을 포함한 scope key를 사용하며 content-only global rejection과 구분. P01에 연결합니다.

## E05 · §14.2 changed

문구: predicate 변경도 새 KEdgeRevision 후보로 묶음.

권장: “동일 identity 안의 qualifier/scope material 변화는 새 Revision; predicate 변경은 old relation 처리 + 새 logical KEdge”. P06에 연결합니다.

## E06 · §14.3 DAG 범위

문구: “supersedes relation을 포함한 lifecycle/semantic transition graph에는 self-edge와 cycle을 허용하지 않는다.”

권장: DAG를 요구하는 relation registry와 causal provenance를 명시하고, 일반 semantic graph 전체에 무조건 DAG를 강제하지 않음. P06에 연결합니다.

## E07 · §20.4 code block

field 각주에는 origin_type이 있지만 code block에 없습니다.

권장: `origin_type = authority_confirmed`를 W2K payload 예시에 추가하고 reported route와 discriminated schema로 구분. action별 defer/시간 mapping은 P08 계약으로 별도 확정합니다.

## E08 · §18.4와 §21.1의 retrieval_mode

세 evidence surface enum과 decision_trace strategy가 같은 이름을 사용합니다.

권장: 두 축 분리 + 기존 field compatibility. 구체 이름과 migration은 P08 승인이 필요합니다.

## E09 · §9.1/§26 Operation·Record·용어 표

N2E의 applicability effect와 KEdgeApplicabilityEvent, KLifecycleEvent, DataAcquisition 등 새 객체/효과가 일부 요약 표에서 누락됩니다.

권장: 기존 baseline 이름을 유지하면서 실제 출력/용어 목록을 일치시킵니다. 미정 K revalidation subtype 이름은 확정된 것처럼 넣지 않습니다.

## E10 · §7.6 current applicability

A OR B 형태는 원래 endpoint가 같을 때 최신 negative를 무시할 수 있습니다.

권장: exact pair의 최신 explicit 판정 우선, 그다음 initial approval fallback. 단순 편집 문제가 아니라 P02 승인이 필요한 semantic 정정입니다.

## 적용 방법

원본 archive를 조용히 덮어쓰지 않습니다. T01에서 승인된 각 replacement와 근거를 별도 active addendum으로 기록합니다. 차후 통합본을 발행할 때는 새 source version/hash를 만들고 이전 archive를 남깁니다. split 파일을 손으로 독립 수정하지 않습니다.
