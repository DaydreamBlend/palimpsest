## 18. W — Wisdom

### 18.1 정의

Wisdom은 accepted KGraph와 사용자 Query, 당시 Context를 결합해 사람이 사용할 수 있는 설명·추천·결정을 표현한 immutable artifact다.

Wisdom은 일반적인 영구 진리를 의미하지 않는다. 특정 질문, 시점, Context, Knowledge snapshot에 종속된다.

### 18.2 QueryContextGraph

Query와 Memory를 canonical KGraph에 직접 삽입하지 않는다. K2W 동안만 임시 overlay를 만든다.

```text
accepted KGraph
+ User Query
+ Context/Memory snapshot
→ QueryContextGraph
→ K2W
→ Wisdom
```

QueryContextGraph는 canonical 객체가 아니다.

K2W evidence_mode는 epistemic boundary를 명시하고 retrieval_strategy는 standard/decision_trace/history 조회 전략을 별도로 기록한다.

```text
knowledge_only            # accepted K만 사용
knowledge_plus_evidence   # K와 아직 K로 컴파일되지 않은 validated I를 직접 사용
evidence_only             # validated I 중심; K 부재/비활성 상황의 제한 모드
```

직접 Information을 사용한 경우 Wisdom은 이를 accepted Knowledge와 구분해 표시해야 한다.

### 18.3 Wisdom kind

Canonical Wisdom kind는 세 가지다.

| kind | 대표 질문·사건 | authority | 자동 W2K |
|---|---|---|---|
| `explanation` | “X가 뭐야?”, “왜 X를 선택했어?” | 주로 LLM synthesis | 아니요 |
| `recommendation` | “A와 B 중 무엇이 좋아?” | LLM의 advisory output | 아니요 |
| `decision` | “A를 선택한다”, “일단 보류한다” | 사람 또는 권한 있는 actor | 예 |

`decision_replay`는 Wisdom kind가 아니다.

### 18.4 Wisdom 공통 필드

```text
wisdom_id
wisdom_kind
query
context_snapshot
used_k_revision_ids
used_effective_edge_refs optional
used_information_ids optional
retrieval_snapshot
evidence_mode
retrieval_strategy
epistemic_basis
answer_or_payload
citations
uncertainty
generation_profile
created_at
```

필드 각주:

| 필드 | 설명 |
|---|---|
| `wisdom_id` | 특정 Query·Context·Knowledge snapshot에서 만들어진 immutable Wisdom artifact ID다. |
| `wisdom_kind` | explanation, recommendation, decision 중 이 W가 수행하는 역할이다. |
| `query` | 사용자가 요청한 질문이나 판단 과제다. 재현을 위해 당시 표현 또는 정규화된 원문 참조를 보존한다. |
| `context_snapshot` | 생성 당시의 시간, session memory, 사용자 조건 등 비canonical Context를 고정한 snapshot이다. 이후 Context 변화가 과거 W를 바꾸지 않는다. |
| `used_k_revision_ids` | 답변·추천·결정 근거로 실제 사용한 exact KNodeRevision/KEdgeRevision IDs다. 검색됐지만 사용하지 않은 K와 구분한다. |
| `used_effective_edge_refs` | 소비한 semantic edge revision·실제 endpoint pair·applicability basis/read-state token을 보존한다. exact citation과 당시 해석을 복원하며 used_k_revision_ids만으로 대체하지 않는다. |
| `used_information_ids` | K를 거치지 않고 직접 인용·검토한 exact Information IDs다. 필요하지 않으면 비어 있다. |
| `retrieval_snapshot` | 당시 검색 후보, score, filter, retrieval profile을 재현하기 위한 snapshot이다. 실제 사용 근거는 `used_*` 필드가 별도로 고정한다. |
| `evidence_mode` | `knowledge_only`, `knowledge_plus_evidence`, `evidence_only` 중 어떤 epistemic surface를 허용했는지 기록한다. |
| `retrieval_strategy` | standard, decision_trace, history 중 조회 목적/전략이며 evidence_mode와 독립적이다. |
| `epistemic_basis` | 최종 answer의 근거가 accepted Knowledge인지, direct validated Information인지, 둘의 혼합인지 구조화해 기록한다. |
| `answer_or_payload` | kind별 최종 설명문 또는 구조화된 recommendation/decision 내용이다. |
| `citations` | 답변의 구체 문장·주장을 exact K/I/Data grounding과 연결하는 인용 정보다. |
| `uncertainty` | 근거 부족, 상충, 가정과 신뢰 한계를 구조화해 표현한다. 단일 임의 확률값만을 뜻하지 않는다. |
| `generation_profile` | 사용한 prompt, model, synthesis policy와 출력 schema version을 재현할 수 있는 profile 참조다. Decision은 actor 구조화 profile을 가리킬 수 있다. |
| `created_at` | immutable Wisdom이 생성·확정된 시각이다. 결정 효력 시각인 `effective_at`과는 다르다. |

Wisdom은 그 자체가 immutable snapshot이며 `WisdomRevision`을 두지 않는다.

---

## 19. Recommendation과 Decision

### 19.1 Recommendation W

Recommendation은 K에 근거한 LLM의 제안이다.

```text
Recommendation W
- options
- criteria
- comparison
- recommended_option
- supporting and opposing K refs
- uncertainty
```

Recommendation 필드 각주:

| 필드 | 설명 |
|---|---|
| `options` | 비교 대상으로 실제 검토한 선택지 목록이다. |
| `criteria` | 비용, 품질, 위험처럼 선택지를 평가한 기준과 필요하면 가중치·우선순위를 담는다. |
| `comparison` | 각 선택지가 criteria를 어떻게 충족하는지 근거와 함께 구조화한 비교 결과다. |
| `recommended_option` | LLM이 K에 근거해 가장 적합하다고 제안한 선택지다. 사용자의 확정 결정은 아니다. |
| `supporting and opposing K refs` | 추천을 지지하거나 반대하는 exact K Revision refs다. 양쪽 근거를 모두 보존한다. |
| `uncertainty` | 정보 부족, 상충하는 K, 조건 변화에 따른 추천의 한계를 표현한다. |

Recommendation 자체는 사용자의 commitment가 아니므로 자동 W2K하지 않는다.

### 19.2 Decision W

Decision은 권한 있는 actor가 실제로 선택·보류·거부한 사건이다.

Canonical decision action:

| action | 의미 |
|---|---|
| `select` | 특정 선택지를 채택 |
| `defer` | 조건 또는 시점까지 보류 |
| `decline` | 제안된 선택지를 모두 거부 |

최소 필드:

```text
wisdom_id
wisdom_kind = decision
origin_type = authority_confirmed
subject
scope
constraints
effective_at
decision_action
decision_statement
selected_option optional
defer_until optional
defer_condition optional
basis_recommendation_wisdom_id optional
decision_reason
decided_by
confirmation_ref
decided_at
supersedes_decision_id optional
```

Decision W 필드 각주:

| 필드 | 설명 |
|---|---|
| `wisdom_id` | 이 확정 결정 사건을 나타내는 immutable Wisdom ID다. |
| `wisdom_kind` | 반드시 `decision`이다. Recommendation과 authority 경계를 구분한다. |
| `origin_type` | Decision W에서는 항상 `authority_confirmed`다. 외부 자료가 보고한 결정은 Decision W가 아니라 D→I→I2K의 reported decision 경로를 사용한다. |
| `subject` | 결정이 적용되는 문제·대상·프로젝트의 구조화 identity다. deterministic W2K의 source field다. |
| `scope` | 결정이 유효한 조직·시스템·기간·문제 범위다. |
| `constraints` | 결정이 유효한 전제와 제한 조건이다. |
| `effective_at` | 결정이 효력을 갖기 시작하는 시각이다. `decided_at`과 다를 수 있다. |
| `decision_action` | `select`, `defer`, `decline` 중 actor가 실제로 확정한 행위다. |
| `decision_statement` | 사람이 읽을 수 있는 확정 결정문이다. 구조화 필드를 대체하지 않고 함께 보존한다. |
| `selected_option` | `select`에서 채택한 선택지다. defer/decline에서는 없을 수 있다. |
| `defer_until` | 특정 시점까지 보류한 경우 그 시각이다. |
| `defer_condition` | 특정 조건이 충족될 때까지 보류한 경우 그 조건이다. |
| `basis_recommendation_wisdom_id` | 이 결정이 참고한 Recommendation W ID다. 직접 결정이면 비어 있을 수 있다. |
| `decision_reason` | actor가 밝힌 결정 이유다. LLM이 임의로 사후 생성한 설명과 구분한다. |
| `decided_by` | 결정을 확정할 권한이 있는 사람 또는 actor의 안정적인 참조다. |
| `confirmation_ref` | CLI에서 actor가 exact payload를 확인한 승인 event 또는 검증된 서명 등 실제 결정 증거다. 향후 GUI 클릭도 같은 authority 계약을 따라야 하며 단순 플래그만으로 증거를 만들어내지 않는다. |
| `decided_at` | actor가 결정을 확정한 시각이다. Wisdom row insert 시각과 다를 수 있다. |
| `supersedes_decision_id` | 이 결정이 명시적으로 대체하는 이전 Decision Wisdom ID다. 단순 오탈자 수정용 Revision 필드가 아니다. |

직접 내린 결정은 basis Recommendation이 없어도 된다. Decision W는 항상 `origin_type=authority_confirmed`로 취급하며, 외부 문서가 보고한 decision event는 D→I→I2K 경로에서 `decision` KNode `origin_type=reported`로 표현한다.

LLM만으로 Decision W를 확정할 수 없다. LLM은 Recommendation을 만들거나 사용자의 decision intent를 구조화할 수 있지만, `decided_by`와 유효한 authority/confirmation evidence가 필요하다.

---

## 20. 자동 W2K

### 20.1 Invariant

`wisdom_kind=decision`이고 authority/confirmation 검증을 통과한 Wisdom은 저장될 때 자동으로 W2K되어 `origin_type=authority_confirmed` decision KNode가 된다.

```text
Decision W
→ deterministic W2K projection
→ schema/authority validation
→ W2KRecord
→ decision KNode + first KNodeRevision
```

별도의 “K에 저장” 사용자 동작은 요구하지 않는다. W2K는 primary decision KNode 외에 실제 확인된 payload에 명시된 supersedes만 결정론적 부수 효과로 처리하고 그 외 관계를 생성하지 않는다. 전체 W/K/Record/provenance/관계/outbox는 atomic이며 N2E discovery에 대체 관계 생성을 맡기지 않는다.

### 20.2 LLM 비사용

Decision W가 `subject/scope/constraints/effective_at`까지 구조화되어 있으므로 W2K에서 Generator LLM을 다시 호출하지 않는다.

```text
generator = deterministic projection
validator = schema + policy + authority confirmation
```

이는 비용을 줄이고 사용자가 확정한 결정을 LLM이 다시 해석해 바꾸는 일을 막는다.

### 20.3 원자적 commit

다음을 하나의 PostgreSQL transaction으로 처리한다.

```text
1. Decision Wisdom insert
2. W2KRecord insert
3. decision KNode/KNodeRevision insert; 동일 `origin_wisdom_id` retry만 exact reuse
4. Wisdom↔K provenance insert
5. 확인된 supersedes 요청의 대상/권한/scope/효력/DAG 검증 후 관계·첫 revision/current 상태 효과 insert; 같은 W2KRecord의 typed effect/origin refs 보존
6. downstream N2E/K2K outbox event insert
```

필수 guard:

```text
UNIQUE(origin_wisdom_id for W2K)
```

같은 confirmation event의 같은 payload retry는 같은 W/K 결과를 반환하고 같은 key의 다른 payload는 conflict다. 확인 시도와 성공된 event를 구분한다. 같은 Decision W가 retry되어도 decision KNode를 중복 생성하지 않는다. 반대로 서로 다른 `wisdom_id`의 Decision은 semantic payload가 같아도 별도 decision event이므로 기존 decision KNode로 content-based reuse하지 않는다.

### 20.4 Decision KNode payload

```text
kind = decision
subject
decision_action
selected_option
scope
constraints
effective_at
decided_by
origin_wisdom_id
```

Decision KNode payload 필드 각주:

| 필드 | 설명 |
|---|---|
| `kind` | 항상 `decision`이며 일반 proposition과 다른 authority·검색 정책을 적용한다. |
| `origin_type` | W2K에서 생성된 경우 `authority_confirmed`다. 외부 Data에서 I2K로 생성된 decision은 `reported`를 사용한다. |
| `subject` | 결정이 적용되는 문제, 대상 또는 프로젝트다. |
| `decision_action` | select, defer, decline 중 확정된 행위다. |
| `selected_option` | 실제로 채택한 선택지다. action에 따라 비어 있을 수 있다. |
| `scope` | 결정이 유효한 조직, 시스템, 기간 또는 문제 범위다. |
| `constraints` | 결정이 유지되는 전제와 제한 조건이다. |
| `effective_at` | 결정이 효력을 갖기 시작하는 시각이다. |
| `decided_by` | 결정을 확정한 authority actor 참조다. |
| `origin_wisdom_id` | 이 KNode를 결정론적으로 만든 exact Decision Wisdom ID다. W2K 중복 방지의 핵심 origin key다. |

명시적 supersedes 관계의 scope/effective_at은 확인된 payload에서 보존한다. future-effective/부분 scope를 즉시 전면 비활성화로 축약하지 않는다. active/superseded/expired 같은 `decision_status`는 semantic payload에 저장하지 않고 supersedes KEdge, lifecycle event, effective time을 이용해 계산하는 current projection으로 둔다.

Decision KNode가 표현하는 것은 선택지가 객관적으로 참이라는 주장이 아니다.

> 특정 actor가 특정 시점과 조건에서 이 결정을 내렸다는 사실이다.

상세한 대안·비교·당시 rationale은 origin Decision W와 basis Recommendation W에 남는다.

### 20.5 결정 변경

실제 결정을 바꾸는 것은 기존 decision KNode의 semantic Revision이 아니다.

```text
Decision D1: PostgreSQL을 선택
Decision D2: 이후 SQLite로 변경

D2 --supersedes--> D1
```

- 같은 결정 사건 기록의 오탈자·범위 정정 → 같은 KNode의 새 Revision
- 실제로 다른 결정을 내림 → 새 decision KNode + `supersedes` KEdge
- 과거와 동일한 선택지로 다시 결정함 → semantic 내용이 같아도 새 decision event + 필요 시 이전 active decision을 supersedes

Decision supersession graph는 DAG여야 하며 cycle을 허용하지 않는다.

---

## 21. Decision trace

### 21.1 별도 Wisdom kind가 아니다

과거 결정 이유를 묻는 결과는 `Explanation W`다.

```text
“왜 PostgreSQL을 선택했지?”
→ output wisdom_kind = explanation
```

다만 일반 설명과 retrieval 방식이 다르므로 runtime intent/mode를 구분한다.

```text
query_intent = explain_decision
retrieval_strategy = decision_trace
evidence_mode = 당시 허용한 evidence surface
```

### 21.2 Retrieval 순서

```text
1. decision KNode
2. origin Decision W
3. basis Recommendation W
4. 당시 사용한 exact K revisions
5. 당시 Query와 Context snapshot
6. 필요할 때만 현재 K와 별도 비교
```

현재 K를 사용해 과거 결정을 새로 정당화해서는 안 된다. 과거 결정 설명과 현재 관점 평가는 명시적으로 구분한다.

### 21.3 Memory 경계

별도 canonical 장기 Memory 계층을 두지 않는다.

| 기억 종류 | 저장 위치 |
|---|---|
| 확정된 장기 결정 | decision KNode + origin Decision W |
| 당시 추천·대안·rationale | Recommendation/Decision Wisdom |
| 현재 대화·일시 조건 | K2W Context snapshot |
| 장기 재사용할 외부 사실 | D→I→K 경로 |

Memory module이 존재하더라도 canonical truth store가 아니라 K2W에 임시 Context를 공급하는 runtime component다.

---

## 22. W2K 순환 억제

자동 W2K가 무한 순환을 만들지 않도록 다음을 지킨다.

1. `decision` W만 W2K한다.
2. `explanation`, `recommendation` W는 자동 W2K하지 않는다.
3. decision trace Explanation은 W2K하지 않는다.
4. Wisdom 하나당 W2KRecord는 최대 하나다.
5. W2K decision KNode의 material graph delta는 N2E/K2K convergent propagation을 트리거한다.
6. KGraph 변화가 과거 Query의 K2W를 자동 재실행하지 않는다.
7. 동일 `origin_wisdom_id`의 retry만 reuse한다. 서로 다른 Decision Wisdom은 semantic payload가 같아도 event identity가 다르므로 content-based reuse하지 않는다.

---

U08: reported decision trace는 origin W가 아닌 exact I/D로 추적한다. 새 W에는 evidence_mode/retrieval_strategy를 모두 기록한다. 과거 retrieval_mode 값/bytes를 다시 쓰지 않으며 decision_trace만 남은 과거 기록의 evidence_mode는 exact inputs로 확인 불가하면 unknown/replay 제한을 표시한다. R07 사용자 선택: prepare가 읽은 배타적 scope의 head 집합/state token을 확인 payload와 결합하고 canonical commit까지 충돌 검출한다. current head가 바뀐 늦은 요청은 새 W/K를 저장하지 않고 현재 상태로 재확인한다. 확인/실행 시도 이력은 보존한다. 인증/조회 권한과 key/payload가 같은 기존 성공 retry는 새 freshness 검사 전에 기존 결과를 반환한다. 자유 텍스트 유사도나 timestamp로 배타적 scope/승자를 추정하지 않는다.
