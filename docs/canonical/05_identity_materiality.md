## 11. Fingerprint와 중복 억제

### 11.1 네 가지 fingerprint와 rejection scope

| 이름 | 계산 시점 | 포함하는 핵심 | 목적 |
|---|---|---|---|
| `attempt_fingerprint` | Generator 또는 결정적 처리 전 | Operation, semantic trigger kind, frozen input/state/profile; opaque cause/root ID는 별도 | 같은 고정 입력 처리 또는 LLM 재호출 방지 |
| `identity_fingerprint` | candidate 구조화 후 | 논리 객체 identity projection | 새 객체인지 기존 객체인지 판정 |
| `content_fingerprint` | candidate 구조화 후 | profile별 source payload 또는 canonical semantic payload | 정확히 같은 accepted/rejected 내용 탐지 |
| `context_fingerprint` | Validator 실행 전 | frozen content + exact inputs + 전달한 authoritative context + deterministic-check 결과/version + policy/model/schema versions | 범위가 있는 기각·재검토 판정 |

모든 fingerprint envelope는 최소한 algorithm, domain, projection version, canonicalization version, digest를 가진다. U11 source I는 Data·grounding·source content projection을 사용하며 semantic near-duplicate나 정보 가치로 원문을 억제하지 않는다. 아래 semantic/contextual rejection 규칙은 K와 과거 semantic profile에 적용하고 D2I 기술적 실패를 epistemic rejection으로 바꾸지 않는다.

### 11.2 처리 순서

```text
1. 실행 eligibility/terminal 상태와 domain identity 확인
   → failed/pending/needs_human은 성공 cache가 아님; 같은 완료된 semantic work만 재사용

2. I는 같은 D/locus, K는 current usable identity, Decision은 같은 confirmation event/W인지 확인
   → 그 뒤 같은 accepted content만 reused; historical match는 current rollback 명령이 아님

3. 같은 유효한 rejection scope + FP
   → 해당 범위에서만 suppressed; 수정된 locator/schema/policy는 재검증

4. frozen candidate/input/context/check/profile digest로 contextual cache 확인
   → 사후 used refs는 attribution이며 사전 suppression key를 대신하지 않음

5. same eligible identity + material content delta
   → K는 새 immutable Revision 후보; I는 explicit repair의 replacement set 후보
   → semantic 재사용이어도 새 grounding은 별도로 validation

6. new identity 또는 다른 Decision event/다른 Data의 I
   → 새 논리 객체 후보; content만으로 병합하지 않음
```

rejection reason은 최소 다음 scope를 구분한다.

- `invariant_hard`: context와 무관한 동일 불법 표현에만 한정한다. locator 오류는 D/extractor/locator, schema 오류는 schema version, forbidden Operation-kind는 registry/policy version을 포함한 범위에서 검사한다.
- `contextual`: insufficient evidence, conflict, ambiguity처럼 주변 evidence 변화로 달라질 수 있음
- `policy_scoped`: 특정 validator/policy version에서만 유효
- `temporary`: provider/외부 상태나 시간 조건 때문에 재검토 가능

content-only 전역 suppression은 context와 무관함이 확인된 동일 invariant-hard 표현에만 적용한다. locator를 고친 같은 content를 이전 기각으로 막지 않는다. contextual/policy-scoped rejection은 context fingerprint가 같을 때만 suppress한다.

동시 요청에서도 중복 canonical 객체가 생기지 않도록 DB unique constraint 또는 동등한 atomic guard를 사용한다.

### 11.3 Semantic near-duplicate

Fingerprint는 exact canonical equality를 다룬다. 의미적으로 비슷하지만 byte-level canonical payload가 다른 후보는 accepted RAG와 새 Validator 검토로 판정한다. rejected 이력은 exact scoped FP만 조회하며 다른 표현을 의미 유사도만으로 억제하지 않는다.

다음 조건만으로 자동 suppression하지 않는다.

- embedding score가 높음
- 자연어 문장이 비슷함
- 같은 entity 이름을 포함함

accepted 근접 후보와 exact scope/FP가 일치한 rejected Record만 Validator에 제공하고, kind별 material-delta schema로 차이를 판정한다.

---

## 12. K Material delta와 Revision 규칙

### 12.1 원칙

> K Revision은 표현 변경이 아니라 의미 변경이다.

| 변화 | canonical effect |
|---|---|
| 공백·문체·문장 순서만 변경 | `no_material_delta` |
| 같은 의미의 새 독립 근거 추가 | `disposition=reused` 가능; append-only Grounding 추가; semantic Revision 없음 |
| accepted content와 동일 | `reused` |
| 같은 K identity이지만 scope·조건·극성·시간 범위 변경 | 새 K Revision 후보 |
| identity 자체가 달라짐 | 새 KNode/KEdge 후보 |
| 기존 K 객체가 더 이상 유효하지 않음 | invalidate 또는 supersede; 과거 K Revision 삭제 금지 |

semantic disposition과 canonical effect를 혼동하지 않는다. 예를 들어 `reused`여도 `grounding_added`가 발생할 수 있다.

Information에는 이 Revision 규칙을 적용하지 않는다. materially corrected Information은 새 Information으로 승인하고 기존 I와 `InformationSupersession` 관계를 맺는다.

### 12.2 Structured semantic payload

자연어 문장 전체를 semantic identity로 사용하면 LLM paraphrase가 무한 Revision을 만든다. kind별 구조화 payload를 fingerprint projection으로 사용한다.

proposition 예:

```text
subject
relation
object
polarity
quantifier
scope
conditions
time_range
```

proposition payload 필드 각주:

| 필드 | 설명 |
|---|---|
| `subject` | 주장이 대상으로 삼는 entity·개념이다. |
| `relation` | subject와 object 사이에 주장되는 정규화된 관계다. |
| `object` | relation의 대상 또는 주장되는 값이다. |
| `polarity` | 긍정·부정 여부다. 부정어 누락으로 반대 의미가 되는 것을 막는다. |
| `quantifier` | 전체, 일부, 단일 사례처럼 주장의 수량 범위를 표현한다. |
| `scope` | 주장이 적용되는 domain·대상·상황의 경계다. |
| `conditions` | 주장이 성립하기 위해 필요한 전제·예외 조건이다. |
| `time_range` | 주장이 유효하다고 말하는 시간 범위다. |

procedure 예:

```text
goal
ordered_steps
preconditions
postconditions
exceptions
```

procedure payload 필드 각주:

| 필드 | 설명 |
|---|---|
| `goal` | 절차가 완료했을 때 달성하려는 결과다. |
| `ordered_steps` | 실행 순서가 보존되어야 하는 단계 목록이다. |
| `preconditions` | 절차를 시작하기 전에 충족돼야 하는 조건이다. |
| `postconditions` | 절차가 성공적으로 끝났다고 판단할 수 있는 결과 조건이다. |
| `exceptions` | 일반 순서를 따르지 않거나 중단·대체해야 하는 예외 상황이다. |

decision 예:

```text
subject
decision_action
selected_option
scope
constraints
effective_at
decided_by
```

decision K payload 필드 각주:

| 필드 | 설명 |
|---|---|
| `subject` | 결정이 적용되는 대상·문제·프로젝트다. |
| `decision_action` | select, defer, decline 중 실제로 수행한 결정 행위다. |
| `selected_option` | select에서 채택한 선택지다. 다른 action에서는 비어 있거나 별도 의미를 가질 수 있다. |
| `scope` | 결정이 적용되는 조직, 시스템, 기간 또는 문제 범위다. |
| `constraints` | 결정이 유효한 전제, 제한 또는 준수 조건이다. |
| `effective_at` | 결정이 효력을 갖기 시작하는 시각이다. 기록 생성 시각과 다를 수 있다. |
| `decided_by` | 결정을 확정한 권한 있는 사람 또는 actor의 안정적인 참조다. |

사람이 읽는 문장은 semantic payload에서 생성되는 presentation projection으로 취급할 수 있다.

---

