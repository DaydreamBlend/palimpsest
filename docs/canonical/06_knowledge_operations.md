## 13. I2K

### 13.1 Trigger와 입력

새 validated usable source Information이 생기면 I2K의 입력이 된다. I2K는 LLM 의미 해석·구조화된 지식 제안이 시작되는 단계다. D2I의 구조적 acceptance를 해당 내용의 진실성이나 지식 채택으로 간주하지 않는다. 실제 I2K 실행은 해당 task에서 구현하며 T03 완료와 구분한다.

```text
seed Information
+ same-D related Information
+ corpus RAG related Information
→ context-bounded Information set
→ I2K Generator
→ KNode proposal(s)
```

I2K는 versioned strict structured proposals와 exact I/source refs를 사용하며, chunk projection으로 전달해도 원래 I/page/region까지 추적한다. 모델이 제안한 canonical ID를 신뢰하지 않고 애플리케이션의 identity/FP/reuse 및 materiality 검사와 atomic commit을 거친다. 같은 표현의 변형이나 새로운 grounding만으로 K Revision을 만들지 않는다.

I2K 입력은 하나 이상이다. 새 I 하나만으로 충분한 KNode를 만들 수도 있고, 새 I와 기존 관련 I를 함께 사용해 더 가치 있는 KNode를 만들 수도 있다.

### 13.2 출력

I2K는 KNode 계열만 제안한다.

- 새 identity면 새 KNode 후보
- 기존 identity와 material delta면 기존 KNode의 새 Revision 후보
- 기존 content와 같으면 reused
- 가치 없거나 부정확하면 rejected

I2K가 KEdge를 직접 만들지 않는다. 관계 생성은 accepted KNode 이후 N2E가 담당한다.

### 13.3 Provenance

accepted KNodeRevision은 실제 사용한 exact Information IDs와 I2KRecord를 직접 참조한다. Information supersession이 생겨도 과거 K provenance를 새 I로 자동 치환하지 않는다.

seed Information이 기존 I를 supersede하면, 일반 I2K 탐색과 함께 6.6절의 직접 연관 K 재검증을 예약한다. 그 재검증에서 material graph delta가 발생한 경우에만 N2E/K2K convergent propagation을 이어간다.

---

## 14. N2E

### 14.1 Trigger와 검색

N2E에는 `discover`와 `revalidate` 두 mode가 있다. 새 KNode/Revision acceptance는 discovery를 트리거하고, endpoint Revision 변경은 기존 incident edge revalidation도 함께 트리거한다.

```text
seed accepted KNodeRevision
+ KNode RAG neighbors
→ context-bounded endpoint candidates
→ N2E Generator
→ KEdge proposal(s)
```

따라서 current accepted KNodeRevision은 RAG 검색 대상이어야 한다.

### 14.2 출력

N2E는 KEdge 계열의 semantic relation과 edge lifecycle effect만 다룬다.

`discover` mode는 새 KEdge/KEdgeRevision 후보를 제안한다. `revalidate` mode는 이전 relation semantic을 새 exact endpoint revisions에서 다시 평가하고 다음 terminal relation outcome을 낸다.

```text
still_valid
→ material relation delta 없음
→ 새 KEdgeRevision 생성 없음
→ KEdgeApplicabilityEvent(applicable)
→ no_material_delta / non_material
→ 새 semantic branch만 종료; 기존 material 의무와 maintenance는 보존

changed
→ qualifier/predicate/scope 등 material relation delta
→ 새 KEdgeRevision 후보
→ 승인된 material effect만 downstream 전파

no_longer_valid
→ 새 KEdgeRevision 생성 없음
→ KEdgeApplicabilityEvent(not_applicable)
→ current graph applicability의 material 변화
→ dependent downstream K 재검증

needs_human
→ current applicability 보류
→ 자동 branch 진행 중지
```

Generator가 새 edge를 제안하지 않았다는 사실만으로 `no_longer_valid`를 추론하지 않는다. current graph에서 edge를 제외하는 material effect에는 명시적 revalidation decision과 Record가 필요하다.

N2E는 KEdge 계열만 제안한다.

가능한 origin 조합:

```text
I2K-origin Node  ↔ I2K-origin Node
I2K-origin Node  ↔ K2K-origin Node
K2K-origin Node  ↔ K2K-origin Node
W2K decision Node ↔ any accepted Node
```

N2E는 Node의 생성 origin을 관계 허용 기준으로 사용하지 않는다. exact accepted endpoint revisions와 predicate compatibility를 검증한다.

### 14.3 Edge identity와 Revision

기본 edge identity는 predicate, 방향, logical endpoint IDs를 포함한다. 대칭 predicate는 canonical endpoint ordering 규칙을 별도로 가져야 한다.

같은 edge identity에서 **relation semantic payload 또는 qualifier가 material하게 달라질 때만** 새 KEdgeRevision 후보가 된다. endpoint KNodeRevision만 바뀌고 relation semantic이 유지되면 KEdgeApplicabilityEvent로 재확인하며 Revision을 만들지 않는다. supersedes relation을 포함한 lifecycle/semantic transition graph에는 self-edge와 cycle을 허용하지 않는다.

---

## 15. K2K

### 15.1 Trigger와 입력

새 KNode/KEdge 또는 material graph delta가 발생하면 K2K가 한 번의 model-call context에 맞춘 local subgraph를 분석한다.

```text
new accepted K revision
+ local graph neighborhood
+ KNode RAG hits
+ KEdge RAG hits
→ context-bounded K subgraph
→ K2K Generator
→ KNode proposal(s)
```

K2K 입력은 accepted current-applicable KNodeRevision과 KEdgeRevision이다. Candidate, rejected, suppressed, invalidated 또는 stale-endpoint edge를 기본 입력으로 사용하지 않는다.

### 15.2 출력

K2K는 KNode 계열만 제안한다.

- 새 지식이면 새 KNode
- 기존 KNode의 의미를 material하게 정정·한정하면 새 KNodeRevision
- 단순 paraphrase면 no_material_delta
- 기존 accepted content와 같으면 reused

K2K candidate의 `derivation_depth`는 입력 K의 누적 depth에서 계산하며 새 propagation root가 시작돼도 0으로 리셋하지 않는다. 이 값은 source-grounded Information에서 얼마나 멀리 derivation되었는지 설명하는 epistemic metadata이며, 특정 depth를 넘었다는 이유만으로 candidate를 자동 suppress/reject하거나 propagation을 자르지 않는다. 대신 Validator는 transitive Information grounding, 독립 Data support, scope와 uncertainty를 실제 근거로 평가해야 한다.

여기서 local subgraph와 retrieval top-K는 **한 번의 K2K 호출에 들어갈 context를 구성하기 위한 제한**이다. 한 propagation 전체에서 몇 개의 K가 연쇄적으로 재검증될 수 있는지를 제한하지 않는다.

K2K가 어떤 K를 사용해 새 결과를 만들었다는 사실은 provenance/Record다. 이를 자동으로 `generates` semantic KEdge로 만들지 않는다.

### 15.3 KEdge RAG

K2K가 graph pattern을 이해하려면 KEdge도 RAG 검색 대상이어야 한다.

KEdge 검색 projection 예:

```text
from KNode statement
+ predicate
+ to KNode statement
+ edge qualifiers
```

검색 projection은 semantic edge revision·실제 endpoint pair·applicability basis/read-state token의 EffectiveEdgeRef를 포함한다. 전달한 authoritative endpoint 값은 consumer dependency로 등록한다. 관계 무변화가 endpoint 변경으로 이미 생긴 의무를 지우지 않으며 필수 edge pending은 blocked/unknown이다.

---

## 16. 반박과 KNodeRevision

### 16.1 기본 예시

```text
KNode A current revision = A1
새 KNode B revision = B1
B1이 A1과 양립하기 어려움
```

### 16.2 먼저 관계를 기록한다

N2E가 다음 KEdge를 제안한다.

```text
B1 --contradicts--> A1
```

Validator가 승인하면 KEdge E1이 된다. 이 단계에서 A1을 수정하거나 삭제하지 않는다.

### 16.3 Contested projection

accepted contradiction edge가 있는 A는 다음처럼 표시할 수 있다.

```text
A.lifecycle = accepted
A.epistemic_projection = contested
```

`contested`는 graph에서 계산되는 검색·표시 projection이다. A의 semantic Revision이 아니다.

### 16.4 K2K가 후속 의미를 분석한다

```text
A1 + B1 + E1
→ K2K
```

가능한 결과:

1. A의 같은 identity를 더 정확히 수정함 → A2 Revision 후보
2. A/B를 종합한 다른 identity임 → 새 KNode C 후보
3. 표현만 다름 → no_material_delta
4. A가 사용할 수 없음 → invalidation/supersession effect 제안
5. 실제 모순이 아님 → no_op, 관계 후보 기각

### 16.5 A2가 승인되는 경우

```text
KNode A
├─ A1 historical immutable revision
└─ A2 current revision
   supersedes_revision_id = A1
   origin_record_id = K2KRecord
   exact inputs = A1, B1, E1
```

A1은 절대 수정하지 않는다.

### 16.6 기존 Edge

E1은 계속 `B1 contradicts A1`을 뜻한다. A2로 endpoint를 자동 이동하지 않는다.

A2의 acceptance가 N2E를 새로 트리거한다.

```text
A2 + B1
→ N2E
→ 현재도 contradicts인지 재검토
```

과거 graph와 당시 판단은 그대로 재현 가능하다.

---

