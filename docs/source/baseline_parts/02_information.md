## 6. I — Information

### 6.1 정의

Information은 다음을 모두 만족하는 객체다.

1. D의 특정 내용에 근거한다.
2. 독립적으로 이해 가능한 의미를 가진다.
3. 검색하거나 다른 I와 결합할 가치가 있다.
4. RAG corpus에 포함할 수 있다.
5. KNode를 만드는 입력으로 사용할 수 있다.

Information validation은 “세계에서 참인가”를 결정하는 단계가 아니다. D가 실제로 말하는 내용을 충실하게 표현하는지, grounding이 유효한지, 의미 단위로 사용할 수 있는지를 검증한다.

### 6.2 불변 Information

```text
Information
- information_id
- data_id
- kind
- semantic_payload
- human_readable_content
- locator/grounding
- identity_fingerprint
- content_fingerprint
- created_at
```

필드 각주:

| 필드 | 설명 |
|---|---|
| `information_id` | 승인된 Information snapshot 하나의 canonical ID다. 내용은 이후 수정하지 않는다. |
| `data_id` | 이 Information이 직접 근거로 삼는 불변 Data ID다. |
| `kind` | proposition, observation, procedure처럼 Information의 구조와 검색 방식을 선택하는 통제된 type이다. 정확한 registry는 schema에서 확정한다. |
| `semantic_payload` | D가 말하는 의미를 기계가 비교·검증할 수 있도록 정규화한 구조화 내용이다. 단순 표시 문장보다 fingerprint와 compiler 판단의 중심이 된다. |
| `human_readable_content` | 사람이 읽기 위한 표현이다. semantic payload에서 생성할 수 있으며 문체만 달라진 것을 새 Information으로 보지 않는다. |
| `locator/grounding` | page, byte/character offset, region처럼 이 의미가 D의 어디에서 나왔는지 보여 주는 exact 근거 묶음이다. extractor/parser에 따라 locator가 달라질 수 있으므로 `extractor_profile_id/version`과 `anchored_text_hash` 또는 동등한 stable anchor를 함께 보존한다. 물리 schema에서는 별도 grounding rows로 나눈다. |
| `identity_fingerprint` | **같은 D의 같은 evidence locus에서 같은 의미 단위인지** 비교하는 digest다. 최소 `data_id + grounding identity + semantic identity projection`을 포함하며 cross-Data semantic merge에 사용하지 않는다. |
| `content_fingerprint` | 정규화된 Information 의미 전체가 정확히 같은지 확인하는 digest다. |
| `created_at` | Validator 승인을 거쳐 Bibliotheca에 immutable Information으로 편입된 시각이다. |

승인된 Information 자체가 immutable semantic snapshot이다. `InformationRevision` wrapper는 두지 않는다.

embedding model, 검색 index, reranker, 표시용 projection 또는 telemetry가 바뀌어도 새 Information을 만들지 않는다. 이러한 값은 canonical Information에서 재생성 가능한 projection 또는 운영 metadata다.

의미·범위·grounding 오류를 교정하거나 명시적으로 D를 재추출한 결과가 기존 I와 materially 다르면 기존 I를 수정하지 않고 새 Information을 만든다.

서로 다른 Data가 동일한 proposition을 말하더라도 각 D의 독립 provenance를 보존하기 위해 별도 Information snapshot을 만든다. semantic 합의·중복 통합은 I가 아니라 K compilation에서 수행한다.

### 6.3 교체와 무효화

새 Information이 기존 Information을 교정하거나 대체하면 append-only 관계를 남긴다.

```text
InformationSupersession
- old_information_id
- new_information_id
- reason_codes
- origin_record_id
- created_at
```

필드 각주:

| 필드 | 설명 |
|---|---|
| `old_information_id` | 교정·재추출 결과에 의해 기본 사용 대상에서 물러나는 기존 Information ID다. 과거 기록에서는 계속 유효한 historical input이다. |
| `new_information_id` | 기존 I를 대체하도록 새로 승인된 immutable Information ID다. |
| `reason_codes` | 오추출, 잘못된 grounding, split/merge 같은 대체 이유를 기계 판독 코드로 기록한다. |
| `origin_record_id` | 새 I와 supersession 관계를 만든 D2IRecord 또는 승인된 교정 Record를 가리킨다. |
| `created_at` | supersession 관계가 canonical commit된 시각이다. |

관계 table은 다대다를 허용한다. 재추출 과정에서 I 하나가 여러 I로 분리되거나 여러 I가 하나로 합쳐질 수 있기 때문이다. 다만 supersession relation은 directed acyclic graph(DAG)여야 하며 self-edge와 cycle을 허용하지 않는다.

대체 객체 없이 오류만 확인된 경우에는 별도 append-only `InformationInvalidation`을 남긴다.

```text
InformationInvalidation
- information_id
- reason_codes
- origin_record_id
- created_at
```

필드 각주:

| 필드 | 설명 |
|---|---|
| `information_id` | 대체 I 없이 더 이상 일반 검색·새 I2K 입력에 사용하지 않기로 한 Information ID다. 원본 행은 삭제하지 않는다. |
| `reason_codes` | invalidation을 정당화하는 안정적인 오류·정책 코드다. |
| `origin_record_id` | 무효화 결정을 만든 검증 또는 교정 Record를 가리킨다. |
| `created_at` | invalidation이 append-only 기록으로 확정된 시각이다. |

superseded/invalidated I는 기본 RAG와 새 I2K 입력에서 제외하지만, 역사 재현과 과거 K provenance를 위해 삭제하지 않는다. 새 I가 생겼다고 과거 K의 input ref를 새 I로 치환하지도 않는다.

### 6.4 같은 D에서 나온 I

같은 D에 속한 Information은 `data_id`로 즉시 찾을 수 있어야 한다.

새 I를 중심으로 관련 I를 찾을 때 다음을 함께 사용한다.

1. 같은 `data_id`를 가진 sibling Information
2. 원문 locator의 인접도
3. Information kind
4. lexical similarity
5. vector similarity
6. 다양성 또는 중복 제거 정책

같은 D의 모든 I를 무조건 LLM context에 넣지 않는다. 문서가 클 경우 비용과 잡음이 커지므로 top-K와 context budget을 적용한다.

### 6.5 Information RAG

기본 검색 corpus는 validated usable Information이다. superseded/invalidated I는 일반 검색에서 제외하고 history/replay에서만 명시적으로 요청할 수 있다.

Embedding은 canonical truth가 아니라 versioned projection이다.

```text
Information
→ embedding projection
→ retrieval hit
```

embedding projection은 새 모델이나 projection version으로 재생성할 수 있으며 이 과정은 Information identity를 바꾸지 않는다.

### 6.6 Information supersession에 따른 K 재검증

새 I가 기존 I를 supersede하면 Scriptorium은 기존 I를 exact provenance input으로 사용하는 K를 재검증 대상으로 등록한다.

```text
new Information I2 accepted
+ I2 supersedes I1
→ I1을 직접 사용한 accepted KNodeRevision 조회
→ 각 current KNodeRevision에 대해 revalidation 예약
→ 새 I2와 관련 usable I를 근거로 Validator 재검증
```

재검증 원칙:

1. 기존 KNodeRevision과 그 `information_id=I1` provenance는 수정·삭제하지 않는다.
2. 새 I2가 생겼다는 이유만으로 기존 K를 자동 무효화하거나 Revision을 만들지 않는다.
3. I2K는 I2와 관련 I를 사용해 새 K 또는 기존 K의 material Revision 가능성을 검토한다.
4. 기존 K가 여전히 유효하면 `no_material_delta` 또는 동등한 terminal 결과만 기록한다.
5. 같은 K identity의 의미가 materially 바뀌면 새 immutable KNodeRevision 후보를 검증한다.
6. 기존 K가 더 이상 성립하지 않으면 invalidation/supersession 또는 semantic KEdge 후보를 검증한다.
7. 직접 영향받은 K에서 material graph delta가 실제로 발생한 경우에만 그 K를 입력으로 사용하는 간접 downstream K를 재검증한다. `no_material_delta` 또는 non-material effect에서 해당 branch는 종료한다.
8. 각 재검증 attempt에는 FP, causal root, propagation depth metadata와 visited guard를 적용해 동일 exact state/input을 반복 검증하지 않는다. propagation size/depth/Record/token/cost hard cap은 정상적인 semantic 종료 조건으로 사용하지 않는다.

각 재검증 Record는 trigger가 된 supersession/invalidation ref, 영향받은 exact KNodeRevision, 새 replacement I 또는 남아 있는 usable Information IDs, validator profile, FP, terminal outcome과 canonical effect를 보존한다. retrieval snapshot만으로 이 input들을 대신하지 않는다.

Information과 supersession 관계의 commit, 그리고 K 재검증 event의 outbox 등록은 같은 transaction에서 수행한다. worker가 지연되거나 재시도되더라도 event를 잃지 않아야 한다. 재검증 attempt는 `KCompilationRecord`의 FP·causality·terminal-disposition contract를 따르되 기존 I2KRecord나 K2KRecord에 억지로 분류하지 않는다. 별도 public Operation/Record subtype 명칭은 실제 schema 설계 전에 사용자 승인을 받아 결정한다.

대체 I 없이 기존 I만 invalidated된 경우에도 같은 직접 연관 K 재검증을 수행한다. 이때 Validator는 invalidated I를 새 근거로 사용하지 않고, 남아 있는 usable I와 기존 K provenance를 기준으로 K가 여전히 성립하는지 평가한다.

---

