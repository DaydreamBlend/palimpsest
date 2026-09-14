## 8. 공통 Knowledge Compiler

### 8.1 공통 구조

I2K, N2E, K2K는 아래 Generator–Validator compiler skeleton을 사용한다. U11의 D2I는 결정적 원문 단위 조립·구조 검사로, W2K는 실제 authority-confirmed Decision의 결정적 효과로 수행한다. 두 경로는 fingerprint, execution, Record와 atomic commit을 공유하되 application LLM Generator·Validator를 호출하지 않는다.

```text
Trigger
→ relevant-object retrieval
→ attempt fingerprint precheck
→ Generator
→ deterministic structural checks
→ accepted semantic similarity + rejected exact scoped fingerprint lookup
→ Validator
→ terminal disposition
→ atomic canonical commit or suppression
→ material-delta propagation + 의무 열거/receipt/fence로 scoped quiescence 확인
```

### 8.2 Generator와 Validator

LLM 의미 해석은 I2K부터 적용한다. 하나의 Generator LLM과 하나의 Validator LLM을 I2K/N2E/K2K Operation이 공유할 수 있으며 K2W도 구조화된 출력과 exact provenance를 사용한다. D2I의 원문 추출·편입은 이 LLM 선택과 독립이다.

Operation마다 다음은 별도 profile로 둔다.

- system prompt와 prompt version
- input selection policy
- structured output schema
- validation policy
- 허용되는 canonical effect
- token/context budget

여기서 token/context budget은 **한 번의 Generator/Validator 호출에 제공할 입력 context의 크기**를 제한하는 실행 설정이다. 전체 propagation의 거리, branch 수, Record 수, 총 token 또는 총 cost를 잘라 정상 완료로 만드는 propagation cap이 아니다.

canonical 용어는 `Generator–Validator` 또는 `Proposer–Verifier` pipeline이다. strict structured output은 허용 schema와 refs를 제한하지만 의미적 진실·동등성이나 완전한 결정론을 보장하지 않는다. 애플리케이션이 canonical ID, canonicalization/FP, exact retry/replay, dedupe/reuse, typed refs, 권한, read-set freshness와 atomic commit을 통제한다. 모델의 제안만으로 새 node/revision을 확정하지 않는다.

### 8.3 Validator의 독립성

Validator는 Generator의 자유 형식 내부 추론을 승인 근거로 사용하지 않는다. 다음을 입력으로 받는다.

- 정규화된 candidate payload
- 정확한 input refs
- grounding/provenance
- accepted 근접 결과와 rejection scope/FP가 정확히 일치한 과거 기각 Record
- deterministic check 결과
- Operation별 policy

가능하면 Generator와 다른 prompt/profile을 사용한다. 같은 foundation model을 사용하더라도 별도 inference와 제한된 입력을 사용한다.

### 8.4 Operation × KNode kind compatibility

Operation은 출력 KNode kind에 authority 경계를 적용한다. 최소 규칙은 다음과 같다.

| Operation | 허용되는 대표 KNode kind | 금지/주의 |
|---|---|---|
| `I2K` | proposition, observation, procedure, question, entity, reported decision | Data가 보고한 decision은 `origin_type=reported` |
| `K2K` | proposition, procedure, question, entity | 새로운 observation 또는 authority-confirmed decision 생성 금지 |
| `W2K` | decision | `origin_type=authority_confirmed`만 허용 |

K2K는 추론만으로 새로운 관찰 사실이나 사용자 commitment를 만들 수 없다. predicate endpoint compatibility와 함께 이 matrix를 deterministic check에서 먼저 검증한다.

### 8.5 KReviewRun 제거

별도 `KReviewRun`은 canonical 영속 객체로 두지 않는다.

semantic Validator의 최종 decision/effect는 해당 `I2KRecord`, `N2ERecord`, `K2KRecord`에 기록한다. D2I의 결정적 source 검사/effect는 `D2IRecord`, 결정론적인 W2K effect는 `W2KRecord`에 기록한다. 과거 semantic D2IRecord의 Validator receipt는 해당 profile의 immutable history로 남는다.

사람 판단이 필요한 경우 Record의 disposition을 `needs_human`으로 유지한다. 다중 reviewer, 의견, 재심이 실제로 필요해질 때에만 별도 `ReviewEvent`를 추가한다.

---

## 9. KCompilationRecord

### 9.1 목적

`KCompilationRecord`는 Knowledge compiler가 어떤 입력 조합을 시도했고, 무엇을 제안했으며, 최종적으로 승인·기각·재사용·억제되었는지 보존하는 영속 원장이다.

논리 subtype:

| subtype | 입력 | 제안 출력 |
|---|---|---|
| `I2KRecord` | 1개 이상의 exact Information | KNode 또는 기존 KNode의 새 Revision |
| `N2ERecord` | accepted KNodeRevisions | KEdge 또는 기존 KEdge의 새 Revision |
| `K2KRecord` | accepted KNode/KEdge revisions | KNode 또는 기존 KNode의 새 Revision |
| `W2KRecord` | confirmed Decision Wisdom | decision KNode 및 payload에 명시된 supersedes의 결정론적 atomic effect |

6.6절의 Information supersession/invalidation 기반 K 재검증도 이 parent contract를 사용한다. 다만 현재 subtype 중 하나로 간주하지 않으며 별도 subtype 이름은 아직 확정하지 않았다.

PostgreSQL에서는 공통 parent table을 권장한다.

```text
compiler_runtime.k_compilation_records
```

초기 `record_type`은 `i2k | n2e | k2k | w2k`다. Information 기반 K 재검증 subtype은 이름 승인 후 추가한다. 필요하면 typed SQL view 또는 application type으로 `I2KRecord` 등을 노출한다.

공통 테이블은 I2K/K2K의 domain identity 기반 경쟁 보호와 공통 Record/effect 계약을 공유한다. 같은 호출의 여러 proposal과 반복 근거 검토를 허용하므로 attempt/content FP 전체에 전역 UNIQUE를 두지 않는다. 실행 claim과 canonical identity 경쟁은 별도 atomic guard로 보호한다.

### 9.2 최소 필드

```text
record_id
record_type
batch_id

root_record_id
parent_record_id
propagation_depth
derivation_depth

trigger_ref
ordered_input_refs
retrieval_snapshot_ref
expected_base_revision_id optional

generator_profile_id
validator_profile_id

attempt_fingerprint
identity_fingerprint
content_fingerprint
context_fingerprint

execution_status
disposition

canonical_object_id optional
canonical_revision_id optional
matched_record_id optional
canonical_effects
propagation_impact

reason_codes
created_at
resolved_at
```

다중 input refs는 JSON 배열에만 숨기지 않고 FK가 있는 typed relation row로 저장한다.

필드 각주:

| 필드 | 설명 |
|---|---|
| `record_id` | K proposal 또는 canonical effect 한 건의 영속 원장 ID다. KNode/KEdge ID와는 별개다. |
| `record_type` | `i2k`, `n2e`, `k2k`, `w2k` 중 어떤 Operation contract로 생성됐는지 나타낸다. |
| `batch_id` | Generator 호출 또는 결정론적 처리 한 번에서 함께 나온 Record들을 묶는다. 별도 Batch domain 객체는 아니다. |
| `root_record_id` | 연쇄 propagation을 처음 시작한 Record ID다. 해당 root/scope의 causal obligation과 scoped completion을 추적하는 기준이다. |
| `parent_record_id` | 이 작업을 직접 유발한 직전 Record ID다. root이면 비어 있을 수 있다. |
| `propagation_depth` | root에서 현재 Record까지 내려온 실행 단계 수를 기록하는 observability/causality metadata다. 이 값 자체로 propagation을 차단하지 않는다. |
| `derivation_depth` | 제안되는 K가 source-grounded Information에서 몇 단계의 semantic derivation을 거쳤는지 나타내는 epistemic metadata다. 새 root에서 리셋되지 않지만 hard cutoff로 사용하지 않는다. |
| `trigger_ref` | 새 Information, 새 K Revision, Decision Wisdom, supersession event처럼 이 작업을 시작시킨 exact 객체·사건 참조다. |
| `ordered_input_refs` | Generator/Validator에 전달한 authoritative exact Information/K/effective-edge bundle이다. 사후 인용 여부만으로 dependency에서 제거하지 않으며 실제 used refs attribution은 별도 보존한다. 순서가 의미에 영향을 줄 수 있으므로 canonical order와 FK rows를 보존한다. |
| `retrieval_snapshot_ref` | 당시 검색된 후보, score, retrieval profile과 filtering 결과를 재현할 수 있는 snapshot을 가리킨다. exact input refs를 대신하지 않는다. |
| `expected_base_revision_id` | 기존 K의 Revision 후보를 commit할 때 candidate가 검토한 base current revision이다. atomic CAS가 실패하면 stale candidate로 보고 재검증한다. |
| `generator_profile_id` | proposal 생성에 사용한 prompt/model/input-selection 설정 bundle을 가리킨다. W2K에서는 deterministic projection profile이 될 수 있다. |
| `validator_profile_id` | 독립 검증에 사용한 schema·policy·authority 설정 bundle을 가리킨다. |
| `attempt_fingerprint` | Operation·semantic trigger kind·frozen ordered input/state/profile을 호출 전에 정규화한 work digest다. opaque event/root ID·시각·attempt counter는 별도 인과/실행 기록이며 동일 의미 작업 key를 바꾸지 않는다. 같은 분석 호출을 반복하지 않게 한다. |
| `identity_fingerprint` | 후보가 새 logical K인지 기존 K identity인지 판정하는 digest다. |
| `content_fingerprint` | 정규화된 KNode/KEdge semantic payload가 정확히 같은지 찾는 digest다. |
| `context_fingerprint` | Validator 실행 전 frozen 후보 content·exact inputs·전달한 neighbor context·deterministic-check result/version·model/policy/schema version을 결합한 digest다. 사후 used refs는 attribution이며 사전 key를 대신하지 않는다. contextual/policy-scoped rejection suppression에 사용한다. |
| `execution_status` | 실행의 기술적 성공·실패 상태다. 지식적 승인·기각과 분리한다. |
| `disposition` | accepted_new, accepted_revision, reused, rejected, suppressed, no_material_delta, needs_human 중 최종 지식적 처리 결과다. |
| `canonical_object_id` | 승인·재사용 결과가 연결된 logical KNode 또는 KEdge ID다. terminal effect가 없으면 비어 있다. |
| `canonical_revision_id` | 새로 승인되었거나 exact reuse된 KNodeRevision/KEdgeRevision ID다. effect가 Revision을 만들지 않으면 비어 있을 수 있다. |
| `matched_record_id` | reuse, suppression, duplicate 또는 비교 판정의 근거가 된 이전 Record ID다. |
| `canonical_effects` | disposition과 분리된 실제 side effect 목록이다. 예: `revision_created`, `grounding_added`, `lifecycle_event_added`, `edge_revalidation_queued`, `edge_applicability_confirmed`, `edge_became_not_applicable`, `none`. |
| `propagation_impact` | 이 Record의 canonical effect가 downstream 의미 재검증을 요구하는지를 `material`, `non_material`, `none`으로 표시한다. `material`만 새 downstream branch를 만든다. |
| `reason_codes` | 기각·억제·무변화·human review 등의 이유를 안정적인 코드로 남긴다. 비공개 chain-of-thought는 저장하지 않는다. |
| `created_at` | Record가 만들어진 시각이다. |
| `resolved_at` | terminal disposition이 확정된 시각이다. pending/needs_human 동안에는 비어 있을 수 있다. |

### 9.3 실행 상태와 disposition

기술적 실행 상태와 지식적 처리 결과를 분리한다.

```text
execution_status
- pending
- running
- succeeded
- failed
- cancelled
```

`execution_status` 값 각주:

| 값 | 설명 |
|---|---|
| `pending` | K compilation Record는 생성됐지만 아직 실행되지 않았다. |
| `running` | retrieval, Generator, 구조 검사 또는 Validator가 진행 중이다. |
| `succeeded` | 기술적 pipeline이 정상 종료됐다. K 승인 여부는 `disposition`으로 판단한다. |
| `failed` | 기술 오류로 validator decision까지 도달하지 못했다. retry 대상이 될 수 있다. |
| `cancelled` | 사용자 요청, operator 조치, shutdown 또는 명시적 job cancellation로 의도적으로 중단됐다. 비수렴 anomaly 정지는 정상 completion이 아니라 별도 suspended/error 상태로 기록하는 것을 권장한다. |

```text
disposition
- pending
- accepted_new
- accepted_revision
- reused
- rejected
- suppressed
- no_material_delta
- needs_human
```

`disposition` 값 각주:

| 값 | 설명 |
|---|---|
| `pending` | 지식적 terminal decision이 아직 없다. |
| `accepted_new` | 새 logical KNode/KEdge와 첫 Revision을 승인한다. |
| `accepted_revision` | 기존 logical K에 material semantic delta가 있어 새 Revision을 승인한다. |
| `reused` | exact accepted K semantic content가 이미 있어 새 semantic object/Revision을 만들지 않는다. 새 독립 Information 근거가 있으면 같은 disposition에서도 `grounding_added` effect를 가질 수 있다. Decision event에는 별도 W2K identity 규칙을 적용한다. |
| `rejected` | Validator가 정확성, 가치, provenance 또는 정책 기준을 충족하지 못한다고 판정했다. |
| `suppressed` | accepted/rejected FP guard가 같은 시도를 찾아 expensive pipeline을 생략했다. |
| `no_material_delta` | 비교 결과가 문체·표현 차이이거나 기존 K 의미를 바꿀 만큼 중요하지 않다. |
| `needs_human` | 자동 Validator가 결정할 수 없어 candidate와 route를 보존하고 사람 판단을 기다린다. |

예:

```text
execution_status=failed, disposition=pending
→ 기술 실패. 지식적 판정 없음.

execution_status=succeeded, disposition=rejected
→ Validator가 정상적으로 검토하고 기각함.
```

### 9.4 Batch

Generator 호출 하나가 후보 여러 개를 만들면 후보마다 Record를 만든다.

```text
I2KRecord A ┐
I2KRecord B ├─ same batch_id
I2KRecord C ┘
```

별도 `I2KRun`, `I2KRunItem`, `I2KBatch` domain 객체를 만들지 않는다. `batch_id`는 그룹화 값이다. 후보가 하나도 나오기 전의 provider 오류 등은 공통 runtime/model-call log에 남긴다.

---

## 10. Temporary Candidate workspace

Candidate는 canonical 객체가 아니다.

pending/needs_human 또는 잠정 검증 후 canonical atomic commit이 끝나지 않은 상태에서 Compiler Runtime에 full semantic payload를 임시 보존한다. Runtime 자체는 영속 저장소이며 TEMP/UNLOGGED 테이블이 아니다.

```text
TemporaryCandidate
- candidate_record_type
- candidate_record_id
- proposed_object_type
- proposed_kind_or_predicate
- proposed_semantic_payload
- proposed_grounding
- temporary_embedding optional
- expires/cleanup metadata
```

필드 각주:

| 필드 | 설명 |
|---|---|
| `candidate_record_type` | 이 임시 payload를 소유한 Record 계열이 D2IRecord인지 KCompilationRecord인지 구분한다. |
| `candidate_record_id` | 후보의 별도 public ID 대신 사용하는 소유 Record ID다. `candidate_record_type`과 합쳐 작업 identity가 된다. |
| `proposed_object_type` | 승인되면 Information, KNode 또는 KEdge 중 무엇으로 승격될 후보인지 나타낸다. |
| `proposed_kind_or_predicate` | source Information의 unit_type, KNode kind 또는 KEdge predicate처럼 적용할 구조화 schema를 선택하는 값이다. |
| `proposed_semantic_payload` | K와 과거 semantic D2I 후보의 구조화 의미다. 새 source D2I는 versioned source payload를 사용하며 semantic 내용으로 위장하지 않는다. 임시 payload의 terminal cleanup과 영속 Record/provenance 보존을 구분한다. |
| `proposed_grounding` | 후보가 의존하는 exact Data locator, Information IDs, K revision refs 등 제안 근거다. 승인 시 canonical provenance로 옮긴다. |
| `temporary_embedding` | pending 후보를 accepted 근접 결과와 비교하기 위한 선택적 임시 vector다. rejected semantic similarity에는 사용하지 않는다. canonical 검색 corpus에는 들어가지 않는다. |
| `expires/cleanup metadata` | 보류 기한, cleanup 가능 시점, 보존 사유 등 임시 payload 수명주기를 관리하는 값 묶음이다. |

별도 public Candidate ID namespace는 만들지 않는다. `candidate_record_type + candidate_record_id`가 작업 identity이며 D2IRecord 또는 KCompilationRecord를 가리킨다.

terminal 처리:

| disposition | Candidate payload | Record | Canonical Store |
|---|---|---|---|
| accepted_new | 삭제 | FP + canonical refs 보존 | Information 또는 새 K 객체+첫 K Revision |
| accepted_revision | 삭제 | FP + canonical refs 보존 | 기존 K 객체의 새 Revision; D2I에는 사용하지 않음 |
| reused | 삭제 | matched refs + effect 보존 | semantic Revision 없음; 필요 시 grounding append |
| rejected | 삭제 | FP + reason 보존 | 변경 없음 |
| suppressed | 생성하지 않거나 즉시 삭제 | matched Record 보존 | 변경 없음 |
| no_material_delta | 삭제 | 비교 결과·검증 receipt 보존 | semantic Revision 없음; 검증된 support/applicability·dependency maintenance는 가능 |
| needs_human | 유지 | pending route 보존 | 변경 없음 |

별도 `InformationCandidate`, `KNodeCandidate`, `KEdgeCandidate`, `KRejectionRecord` canonical 객체를 두지 않는다.

### 10.1 Rejected candidate audit retention

terminal rejected payload를 canonical Canonical Store에는 보존하지 않는 원칙은 유지한다. 다만 Generator/Validator regression, false-rejection 분석이 필요하면 Compiler Runtime의 비canonical bounded-retention audit store에 normalized payload와 validator finding을 일정 기간 보존할 수 있다.

```text
RejectedCandidateAudit
- record_id
- normalized_payload
- validator_findings
- retention_until
- created_at
```

이 audit store는 RAG corpus, fingerprint truth source 또는 canonical provenance가 아니다. 보존 기간과 암호화/민감정보 정책은 별도 운영 설정으로 둔다. `model_calls`가 raw output을 보존하는 경우 동일 정보를 중복 장기 보존하지 않는다.

---


U08: W2KRecord의 primary 결과는 decision KNode다. 확인된 supersedes 요청에 한한 관계/effect의 origin과 typed refs를 같은 Record에 연결하며 새 public subtype을 만들지 않는다. R08 사용자 선택에 따라 rejected semantic similarity는 수행하지 않는다. scoped FP가 다른 후보는 새 검증을 진행하고 optional audit/raw output은 기각 검색 corpus로 쓰지 않는다.

U09: 옮기는 대상은 검증된 semantic payload/effects이며 판정 Record가 아니다. canonical 효과·provenance/support·terminal Record·candidate cleanup·outbox를 같은 PostgreSQL transaction에 반영한다. 실패하면 잠정 결과를 canonical 승인으로 노출하지 않고 준비 상태를 유지하며, commit 후 응답 유실은 같은 request/effect key의 결과를 조회한다.
