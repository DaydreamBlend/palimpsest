## 7. K — Knowledge graph

### 7.1 정의

Knowledge는 승인된 KNode와 KEdge의 revision-aware graph다.

```text
KGraph
= current usable accepted KNodeRevisions
+ current-applicable usable accepted KEdgeRevisions
```

`KGraph`는 별도 canonical 단일 객체나 mutable blob이 아니다. Bibliotheca의 KNode/KEdge 논리 객체, current revision pointer, append-only lifecycle events와 edge applicability 규칙에서 재구성되는 projection이다.

### 7.2 KNode

KNode는 reusable한 지식 단위의 논리 identity다.

MVP canonical kind:

| kind | 의미 |
|---|---|
| `proposition` | 검증·반박·한정 가능한 주장 |
| `observation` | 관찰 또는 측정 결과 |
| `procedure` | 실행 가능한 절차 |
| `question` | 해결되지 않았거나 추적할 질문 |
| `entity` | 사람, 개념, 조직, 물질, 프로젝트 등 식별 대상 |
| `decision` | 특정 actor의 decision event. `origin_type=reported`와 `authority_confirmed`를 구분한다. |

```text
KNode
- knode_id
- kind
- current_revision_id
- lifecycle
- epistemic_projection
- evidence_projection
- created_at
```

필드 각주:

| 필드 | 설명 |
|---|---|
| `knode_id` | 여러 Revision을 묶는 KNode의 안정적인 logical ID다. 의미 snapshot 하나를 식별하는 Revision ID와 구분한다. |
| `kind` | proposition, observation, procedure, question, entity, decision 중 어떤 구조와 검증 규칙을 사용할지 정하는 통제된 Node type이다. |
| `current_revision_id` | 일반 검색·표시에서 기본으로 사용할 현재 KNodeRevision을 가리키는 pointer다. 과거 provenance나 KEdge endpoint는 이 pointer를 자동 추종하지 않는다. |
| `lifecycle` | append-only `KLifecycleEvent`에서 계산한 현재 관리 상태의 cache/projection이다. overwrite 자체가 역사 기록을 대체하지 않는다. |
| `epistemic_projection` | accepted, contested처럼 현재 graph에서 이 지식이 어떤 인식론적 상태로 보이는지 계산한 projection이다. semantic payload가 아니며 과거 Revision을 변경하지 않는다. |
| `evidence_projection` | current Revision을 지지하는 direct/transitive Information, 독립 Data 수, 최소 derivation depth 등 evidence distance를 계산한 재생성 가능한 projection이다. 새 근거 추가만으로 semantic Revision을 만들지 않는다. |
| `created_at` | logical KNode가 최초 승인되어 만들어진 시각이다. 새 Revision의 생성 시각과는 다르다. |

### 7.3 KNodeRevision

KNodeRevision은 KNode의 특정 시점 semantic snapshot이다.

```text
KNodeRevision
- knode_revision_id
- knode_id
- semantic_payload
- human_readable_projection
- identity_fingerprint
- content_fingerprint
- supersedes_revision_id optional
- origin_record_id
- created_at
```

필드 각주:

| 필드 | 설명 |
|---|---|
| `knode_revision_id` | KNode의 특정 immutable semantic snapshot ID다. provenance와 KEdge endpoint는 이 ID를 정확히 참조한다. |
| `knode_id` | 이 Revision이 속한 logical KNode ID다. |
| `semantic_payload` | Node kind별로 정규화된 의미 구조다. material delta와 fingerprint 판정의 기준이 된다. |
| `human_readable_projection` | semantic payload를 사람이 읽을 수 있게 표현한 문장·요약이다. 문체 변화만으로 새 Revision을 만들지 않는다. |
| `identity_fingerprint` | 이 후보가 어느 logical KNode에 속하는지 판정하는 digest다. |
| `content_fingerprint` | 이 Revision의 정규화된 의미 내용이 exact duplicate인지 확인하는 digest다. |
| `supersedes_revision_id` | 같은 KNode에서 이 Revision이 직접 대체하는 이전 Revision ID다. 첫 Revision이면 비어 있다. |
| `origin_record_id` | 이 Revision을 제안·검증·승인한 I2KRecord, K2KRecord 또는 W2KRecord를 가리킨다. |
| `created_at` | 이 immutable Revision이 승인된 시각이다. |

KNodeRevision은 문체 변화가 아니라 material semantic delta에만 생성한다. current revision 갱신은 `expected_base_revision_id`를 확인하는 atomic compare-and-swap으로 수행해 concurrent sibling Revision을 방지한다. base가 이미 바뀌었으면 candidate를 새 current revision 기준으로 재검증한다.

### 7.3.1 K lifecycle event

KNode/KEdge의 invalidation, supersession, reactivation 같은 관리 상태 변화는 mutable semantic payload가 아니라 append-only event로 남긴다.

```text
KLifecycleEvent
- event_id
- object_type   # knode | kedge
- object_id
- event_type
- origin_record_id optional
- reason_codes
- created_at
```

`KNode.lifecycle`, `KEdge.lifecycle`, `epistemic_projection`은 이 event ledger와 current graph에서 계산한 projection/cache다. 과거 시점 graph를 재현할 때 당시까지의 event만 적용한다.

### 7.4 KEdge

KEdge는 두 KNode 사이의 semantic relation에 대한 논리 identity다.

최소 predicate family:

| predicate | 의미 |
|---|---|
| `supports` | 한 Node가 다른 Node를 지지함 |
| `contradicts` | 두 Node의 현재 의미가 양립하기 어려움 |
| `qualifies` | 조건·범위·예외를 한정함 |
| `composes` | 한 Node가 다른 Node의 구성 요소임 |
| `supersedes` | 새 결정·객체가 이전 결정을 대체함 |

정확한 predicate registry와 endpoint-kind compatibility matrix는 별도 확장 가능한 규약으로 둔다. 임의 문자열 predicate는 허용하지 않는다.

```text
KEdge
- kedge_id
- predicate
- from_knode_id
- to_knode_id
- current_revision_id
- lifecycle
- created_at
```

필드 각주:

| 필드 | 설명 |
|---|---|
| `kedge_id` | 여러 KEdgeRevision을 묶는 semantic relation의 안정적인 logical ID다. |
| `predicate` | supports, contradicts, qualifies, composes, supersedes 같은 통제된 관계 종류다. 임의 문자열을 허용하지 않는다. |
| `from_knode_id` | 방향성 관계의 출발 logical KNode ID다. |
| `to_knode_id` | 방향성 관계의 도착 logical KNode ID다. 대칭 predicate라면 별도 canonical ordering 규칙을 적용한다. |
| `current_revision_id` | 일반 graph projection에서 기본으로 사용할 현재 KEdgeRevision ID다. historical endpoint를 자동 변경하지 않는다. |
| `lifecycle` | append-only KLifecycleEvent에서 계산한 관리 상태 cache/projection이다. |
| `created_at` | logical KEdge가 최초 승인된 시각이다. |

### 7.5 KEdgeRevision

```text
KEdgeRevision
- kedge_revision_id
- kedge_id
- from_knode_revision_id
- to_knode_revision_id
- qualifiers
- semantic_payload
- identity_fingerprint
- content_fingerprint
- supersedes_revision_id optional
- origin_record_id
- created_at
```

필드 각주:

| 필드 | 설명 |
|---|---|
| `kedge_revision_id` | 관계의 특정 immutable snapshot ID다. |
| `kedge_id` | 이 Revision이 속한 logical KEdge ID다. |
| `from_knode_revision_id` | 관계를 승인할 당시 출발점으로 사용한 exact KNodeRevision ID다. |
| `to_knode_revision_id` | 관계를 승인할 당시 도착점으로 사용한 exact KNodeRevision ID다. |
| `qualifiers` | 관계가 성립하는 조건, 범위, 강도, 시점 같은 한정 정보다. |
| `semantic_payload` | predicate, 방향, relation qualifier와 logical endpoint role을 정규화한 관계 의미다. current endpoint의 자연어 문장 자체를 복제하지 않으며 endpoint Revision rebasing만으로 이 payload를 바꾸지 않는다. |
| `identity_fingerprint` | predicate, 방향과 logical endpoint IDs를 바탕으로 같은 관계 identity인지 판정하는 digest다. |
| `content_fingerprint` | logical endpoint IDs, predicate와 정규화된 relation semantic/qualifiers를 대상으로 한 digest다. exact endpoint Revision IDs만 달라진 경우는 새 semantic KEdgeRevision content로 보지 않으며, 그 적용 여부는 KEdgeApplicabilityEvent가 담당한다. |
| `supersedes_revision_id` | 같은 KEdge에서 직접 대체하는 이전 KEdgeRevision ID다. 첫 Revision이면 비어 있다. |
| `origin_record_id` | 이 관계 Revision을 제안·승인한 N2ERecord 등 정확한 compiler Record를 가리킨다. |
| `created_at` | 이 immutable KEdgeRevision이 승인된 시각이다. |

KEdgeRevision은 관계의 **material semantic snapshot**이며 승인 당시 사용한 exact endpoint revision을 보존한다. KNode의 current revision이 변해도 과거 KEdgeRevision의 endpoint를 자동으로 바꾸지 않는다. 다만 endpoint revision이 달라졌다는 사실만으로 새 KEdgeRevision을 만들지는 않는다.

### 7.6 KEdge applicability revalidation

endpoint KNode의 current Revision이 바뀌면 기존 incident KEdgeRevision은 historical provenance를 유지한 채 새 current endpoint pair에 대해 `pending_revalidation` 상태가 된다. 이때 N2E revalidation 결과가 **관계 의미에 material delta가 없음**이라면 새 KEdgeRevision을 생성하지 않고 append-only applicability event만 남긴다.

```text
KEdgeApplicabilityEvent
- applicability_event_id
- kedge_id
- semantic_kedge_revision_id
- from_knode_revision_id
- to_knode_revision_id
- applicability   # applicable | not_applicable
- origin_record_id
- created_at
```

필드 각주:

| 필드 | 설명 |
|---|---|
| `applicability_event_id` | 특정 current endpoint pair에 대한 edge applicability 판정의 append-only event ID다. |
| `kedge_id` | 재검증한 logical KEdge ID다. |
| `semantic_kedge_revision_id` | 의미를 재사용한 기존 immutable KEdgeRevision ID다. 관계 의미가 바뀌지 않았다면 이 Revision을 그대로 사용한다. |
| `from_knode_revision_id` | applicability를 재검증한 당시의 exact current 출발 KNodeRevision ID다. |
| `to_knode_revision_id` | applicability를 재검증한 당시의 exact current 도착 KNodeRevision ID다. |
| `applicability` | 기존 relation semantic이 이 exact current endpoint pair에도 적용되는지 나타내는 `applicable` 또는 `not_applicable` 판정이다. |
| `origin_record_id` | 이 판정을 만든 exact N2E revalidation Record다. |
| `created_at` | applicability 판정이 append-only로 확정된 시각이다. |

current KGraph에서 edge가 current-applicable하려면 lifecycle이 usable하고, 다음 둘 중 하나를 만족해야 한다.

```text
A. current KEdgeRevision의 exact endpoint revisions가 current KNode revisions와 일치
OR
B. current KEdgeRevision의 semantic relation에 대해
   exact current endpoint revisions를 대상으로 한 최신 applicability event가 applicable
```

endpoint가 바뀐 뒤 아직 revalidation이 끝나지 않았으면 해당 edge는 current KGraph에서 일시 제외한다.

revalidation 결과가 다음과 같을 때 canonical effect와 propagation은 구분한다.

```text
relation semantic unchanged + applicable
→ KEdgeRevision 생성 없음
→ KEdgeApplicabilityEvent(applicable)
→ disposition = no_material_delta
→ propagation_impact = non_material
→ branch 종료

relation semantic materially changed
→ 새 KEdgeRevision 후보
→ 승인되면 propagation_impact = material
→ downstream 전파

relation no longer applicable
→ KEdgeRevision 생성 없음
→ KEdgeApplicabilityEvent(not_applicable)
→ current graph에서 edge 제외
→ propagation_impact = material
→ 이 edge를 사용한 downstream K 재검증
```

즉 **Revision 생성 여부와 graph applicability 변화 여부를 분리**한다. endpoint rebasing만을 이유로 semantic KEdgeRevision을 증식시키지 않는다.

---

