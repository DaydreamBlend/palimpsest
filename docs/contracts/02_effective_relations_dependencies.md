# Effective edge·applicability·의존성

> 상태: PROPOSED IMPLEMENTATION CONTRACT · 주 승인 항목 P02.
> U08 부분 적용: R01/R02의 최신 판정 우선, EffectiveEdgeRef 의미·현재 support/소비 dependency 및 pending/maintenance 경계은 [해결 계약](../decisions/ARCHITECTURE_FIXES.md)의 정확한 범위에서 현재 규칙이다. 나머지 P 세부 제안/enum/DDL은 미승인이다.
> 기존 canonical 규칙을 요약한 부분과 이번 제안을 구분합니다. 관련 P 항목이 accepted되기 전에는 본문의 새 필드·enum·명칭을 production canonical 계약으로 사용하지 않습니다.


## 원본에서 유지하는 규칙

KEdgeRevision의 원래 endpoint는 영구 보존합니다. endpoint만 달라지고 relation semantic이 같으면 Revision을 생성하지 않고 applicability event를 남깁니다. non-material edge에서 새로운 semantic cascade를 만들지 않습니다. 근거: baseline §7.5–7.6, §14–17, A32/A33.

## 이번에 제안하는 구현 계약

### 1. EffectiveEdgeRef

이것은 추가 canonical graph 객체가 아니라 exact input을 묶는 typed reference 계약입니다.

```text
semantic_kedge_revision_id
from_knode_revision_id       # 실제로 사용한 endpoint
to_knode_revision_id         # 실제로 사용한 endpoint
applicability_basis_type    # origin_acceptance 또는 applicability_event
applicability_basis_ref
relation_read_state_token
```

물리 schema에서는 typed FK rows로 강제합니다. semantic edge의 원래 endpoint와 effective pair를 동시에 복원할 수 있어야 합니다. KCompilationRecord, K2W/Wisdom, retrieval hit, citation와 projection key가 이 ref를 보존합니다. 역사적 E1 endpoint를 overwrite하지 않습니다.

### 2. Current applicability의 판정 순서

1. logical edge 및 양 endpoint의 lifecycle/usability를 검사합니다. 기본 reasoning graph와 history/decision registry의 읽기 목적은 구분합니다.
2. 조회하려는 exact semantic edge revision + current endpoint pair에 대한 가장 최신 명시적 판정이 있으면 그것을 사용합니다.
3. 최신 값이 `not_applicable`이면 초기 endpoint가 같아도 제외합니다.
4. 명시적 판정이 없고 initial approved endpoint pair와 정확히 같으면 initial acceptance를 사용합니다.
5. 나머지는 pending/unknown입니다. false로 간주하지 않습니다.

최신 순서는 단순 timestamp 정렬만으로 결정하지 않습니다. commit order/sequence 계약은 P05에서 잠급니다. 다른 endpoint pair나 과거 semantic edge revision의 이벤트가 현재 판정을 override할 수 없습니다.

### 3. Semantic relation과 소비된 입력을 분리

C가 E의 predicate만 소비했는지, E를 통해 A의 실제 값도 소비했는지 의존성을 남깁니다. endpoint 문장을 LLM context에 넣었다면 endpoint ref를 “사용 안 함”으로 낙관적으로 제거하지 않습니다. 최소 안전 구현은 전달된 authoritative effective input bundle을 의존성으로 등록하고, field-level 최적화는 별도 평가 후 도입합니다.

A의 material change는 A를 실제 입력으로 가진 C를 직접 예약합니다. E의 재검증이 unchanged이면 E에서 새 semantic branch를 만들지 않습니다. 이미 A 때문에 예약된 C의 obligation을 삭제하는 것도 아닙니다. 이것은 cap이나 무차별 revision cascade가 아닙니다.

### 4. Pending → confirmed 전이

pending_revalidation은 관계 부정이 아닙니다. 필수 edge가 pending인 consumer는 blocked obligation으로 남깁니다. old positive→pending→new positive는 일시 availability 변화이므로 semantic 삭제/재생성 연쇄를 일으키지 않습니다. 판정 완료 시 기존 blocked obligation을 release하는 maintenance event를 보낼 수 있습니다.

`applicable`/`not_applicable`이라는 이벤트 이름만으로 materiality를 결정하지 않습니다. 이전 confirmed effective relation과 비교하십시오. true→false는 material, false→false는 non-material입니다. false→true의 실제 relation 복구는 material일 수 있습니다. 단순 endpoint rebasing에서 true→true는 non-material입니다.

### 5. Projection·history

embedding projection key에는 semantic edge revision뿐 아니라 effective endpoint pair, applicability basis, embedding/input projection profile을 포함합니다. 갱신된 endpoint 문장으로 projection을 다시 만들 수 있지만 semantic edge Revision은 만들지 않습니다. historical read에서는 당시 basis를 사용하고 최신 pointer를 자동 추종하지 않습니다.

### 6. Acceptance

AT09–17 및 AT53을 통과해야 합니다. 특히 초기 endpoint 일치 + 최신 negative, pending 동안 consumer 실행, valid→valid rebasing, 실제 endpoint 값 소비, false→false 반복 이벤트를 서로 다른 테스트로 둡니다.
