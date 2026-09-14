## 4. D — Data

### 4.1 정의

Data는 사용자가 Palimpsest에 넣은 원본 그 자체다.

예:

- PDF
- Markdown 또는 text 파일
- 웹페이지를 보존한 snapshot
- 이미지
- 오디오 또는 영상
- 사용자가 직접 입력한 원문 payload

별도의 `Source` domain layer를 두지 않는다. 외부 시스템의 URL, 파일명, import method는 D의 provenance 또는 import metadata일 뿐 독립 계층이 아니다.

### 4.2 불변성

D payload는 등록 후 수정하지 않는다.

```text
원본 bytes 변경
→ 기존 D 수정 금지
→ 새 D 등록
```

D는 revision 객체를 갖지 않는다. 잘못된 metadata를 바로잡는 방식과 실제 payload가 바뀌는 방식은 구분해야 한다.

### 4.3 최소 metadata

```text
data_id
sha256
media_type
byte_size
horreum_path
original_name optional
created_at
```

필드 각주:

| 필드 | 설명 |
|---|---|
| `data_id` | Bibliotheca에서 Data를 변하지 않게 식별하는 canonical ID다. SHA-256 자체를 쓸지 UUIDv7을 쓸지는 아직 별도 결정이다. |
| `sha256` | Horreum에 보존된 원본 bytes 전체의 SHA-256 digest다. 파일 손상 확인과 완전히 동일한 bytes 탐지에 사용하며 의미적 유사성을 뜻하지 않는다. |
| `media_type` | `application/pdf`, `text/markdown` 같은 MIME type이다. 어떤 parser 또는 D2I profile을 적용할지 선택하는 기본 단서다. |
| `byte_size` | 원본 payload의 byte 단위 크기다. 저장·전송 검증과 운영 한도 확인에 사용한다. |
| `horreum_path` | Horreum 안에서 원본을 찾는 안정적인 상대 경로 또는 storage key다. 사용자의 임의 절대 경로를 canonical identity로 사용하지 않는다. |
| `original_name` | 가져올 당시의 파일명이나 표시 이름이다. 사람이 알아보기 위한 선택 필드이며 identity나 중복 판정에는 사용하지 않는다. |
| `created_at` | Data가 Palimpsest에 canonical 등록된 시각이다. 원문이 작성되거나 파일이 외부에서 생성된 시각과는 다르다. |

SHA-256은 payload 무결성과 동일 bytes 비교에 필수다. `data_id`를 SHA-256 자체로 할지 UUIDv7로 할지는 별도 identity 결정으로 남긴다. 동일 bytes가 여러 경로에서 들어와도 artifact identity와 acquisition provenance를 혼동하지 않는다.

### 4.4 관리 범위

D는 원본이므로 복잡한 lifecycle을 두지 않는다. 필요한 관리는 다음 정도다.

- 존재 여부
- bytes/hash 일치 여부
- Horreum 접근 가능 여부
- D2I logical compilation 처리 여부

### 4.5 DataAcquisition

별도 Source 계층은 두지 않지만, 동일한 D bytes가 언제·어디서·누구에 의해 들어왔는지는 append-only acquisition provenance로 보존한다.

```text
DataAcquisition
- acquisition_id
- data_id
- origin_uri optional
- import_method
- retrieved_at optional
- original_name optional
- external_metadata optional
- actor_ref optional
- created_at
```

`DataAcquisition`은 새로운 S 계층이 아니다. D의 semantic identity를 바꾸지 않는 수집 사건 record이며, 동일 SHA-256 artifact의 여러 독립 acquisition을 모두 남길 수 있다. `data_id=sha256`을 선택하더라도 acquisition provenance는 소실되지 않는다.

---

## 5. D2I — 원본 하나를 Information으로 구조화

### 5.1 Operation

`D2I`는 새 D가 들어왔을 때 그 D를 구조화된 Information 후보들로 바꾸는 Operation이다.

일반 경로에서는 동일한 **logical D2I compilation request**에 대해 exactly-once canonical effect를 보장한다. D 자체가 평생 한 번만 분석된다는 뜻은 아니다.

```text
D
+ D2I profile
+ structured output schema
+ optional model/prompt configuration
→ Information proposals[]
→ validation
→ Information commit
```

logical compilation identity는 최소 `data_id + extraction_profile_family + compilation_generation`을 포함한다. 같은 generation의 평범한 retry는 새 논리 작업을 만들지 않고 동일 attempt를 재개하거나 기존 terminal 결과를 재사용한다. parser/schema/policy 변화, 새로운 extraction kind, 오류 교정을 위해 과거 D를 다시 처리할 때는 명시적 recompile/repair로 새 `compilation_generation`을 시작한다. 이때도 별도 `D2IRun` domain 객체는 만들지 않는다.

### 5.2 D2IRecord

`D2IRecord`는 Information proposal 한 건의 FP, 판정, canonical effect를 기록한다. Generator 호출 하나가 후보 여러 개를 만들면 후보마다 Record를 만들고 같은 `batch_id`로 묶는다.

```text
record_id
batch_id
data_id
compilation_generation
logical_compilation_fingerprint

output_ordinal
generator_profile_id
validator_profile_id
structured_output_schema_version

attempt_fingerprint
identity_fingerprint
content_fingerprint
context_fingerprint

execution_status
disposition

information_id optional
matched_record_id optional
canonical_effects
superseded_information_ids optional

reason_codes
created_at
resolved_at
```

필드 각주:

| 필드 | 설명 |
|---|---|
| `record_id` | Information proposal 한 건의 영속 기록 ID다. 생성될 Information의 ID와는 별개다. |
| `batch_id` | 하나의 D2I Generator 호출에서 함께 나온 proposal들을 묶는 값이다. 별도 Batch domain 객체를 뜻하지 않는다. |
| `data_id` | 이 proposal을 만들 때 사용한 exact Data ID다. 모든 D2IRecord는 하나의 D로 provenance가 고정된다. |
| `compilation_generation` | 같은 D를 명시적으로 recompile/repair할 때 증가시키는 logical generation이다. 평범한 retry는 같은 값을 유지한다. |
| `logical_compilation_fingerprint` | `data_id + extraction_profile_family + compilation_generation`의 canonical digest다. 동일 logical compilation의 exactly-once effect guard다. |
| `output_ordinal` | 같은 batch 안에서 proposal이 나온 안정적인 순번이다. 후보의 의미나 우선순위를 뜻하지 않으며 batch 결과를 재현·대조할 때 사용한다. |
| `generator_profile_id` | 사용한 model, prompt version, 입력 선택 정책과 생성 설정을 묶어 가리킨다. 모델 이름만 저장하는 필드가 아니다. |
| `validator_profile_id` | 후보를 승인·기각할 때 사용한 독립 Validator 정책과 prompt/schema 설정을 가리킨다. |
| `structured_output_schema_version` | Generator 출력이 따라야 했던 구조화 schema의 version이다. 시간이 지나 schema가 바뀌어도 당시 출력을 해석할 수 있게 한다. |
| `attempt_fingerprint` | Generator 호출 전에 D, Operation, profile/schema version 같은 실행 입력을 정규화해 계산한다. 완전히 같은 분석을 LLM에 다시 요청하지 않도록 막는다. |
| `identity_fingerprint` | Information evidence identity를 비교하는 digest다. 최소 exact `data_id`, grounding identity와 semantic identity projection을 포함한다. 서로 다른 D의 같은 semantic content를 하나의 I로 병합하는 전역 key로 사용하지 않는다. |
| `content_fingerprint` | 후보의 정규화된 semantic payload 전체를 대상으로 계산한 digest다. 이미 승인되거나 기각된 정확히 같은 내용을 찾는다. 원문 파일 hash와는 다르다. |
| `context_fingerprint` | content와 exact Data/input, 실제 Validator 판단에 사용된 neighbor refs, deterministic-check version/result, model·policy·schema version을 함께 묶은 digest다. contextual rejection과 재검토 범위를 구분한다. |
| `execution_status` | 실행이 pending/running/succeeded/failed/cancelled 중 어디까지 진행됐는지를 나타내는 기술 상태다. 후보의 가치 판정과는 별개다. |
| `disposition` | 후보가 accepted_new/reused/rejected/suppressed/needs_human 중 어떻게 처리됐는지를 나타내는 지식적 판정이다. |
| `information_id` | `accepted_new` 또는 `reused`일 때 연결되는 exact canonical Information ID다. 승인 전이나 기각 시에는 비어 있다. |
| `matched_record_id` | 중복, 재사용 또는 suppression 판정의 근거가 된 이전 Record를 가리킨다. `reused`는 같은 Data와 같은 grounding identity 안의 exact accepted duplicate에 한정한다. |
| `canonical_effects` | disposition과 별개인 실제 canonical side effect 목록이다. 예: `information_created`, `grounding_added`, `supersession_added`, `none`. |
| `superseded_information_ids` | 명시적 교정·재추출에서 새 I가 대체하는 기존 Information IDs다. 실제 DB에서는 배열 하나가 아니라 FK relation rows로 보존한다. |
| `reason_codes` | 기각·억제·재사용·보류 이유를 안정적인 기계 판독 코드로 기록한다. LLM의 비공개 chain-of-thought를 저장하는 필드가 아니다. |
| `created_at` | 이 proposal Record가 생성된 시각이다. |
| `resolved_at` | terminal disposition이 확정된 시각이다. 아직 검토 중이면 비어 있을 수 있으며 batch 전체의 종료 시각과 반드시 같지는 않다. |

```text
D2IRecord A ┐
D2IRecord B ├─ same batch_id, same data_id
D2IRecord C ┘
```

`D2IOutput`, `D2IRun`, `D2IRunItem`, `D2IBatch`는 canonical domain 객체로 사용하지 않는다. `batch_id`는 호출 묶음을 나타내는 값이다.

후보가 하나도 나오기 전의 provider 오류, 정상적인 zero-output 완료, retry와 전체 호출 timing은 공통 Scriptorium Operation execution log에 남긴다. 이 log는 기술적 실행 기반시설이며 별도의 공개 D2I domain 객체가 아니다. 일반 D2I의 D당 1회 성공도 이 execution log의 atomic idempotency guard로 보장한다.

### 5.3 실행 상태와 disposition

기술적 실행 상태와 Information 판정을 구분한다.

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
| `pending` | 실행할 Record는 만들어졌지만 Generator/Validator 처리가 아직 시작되지 않았다. |
| `running` | Generator, 구조 검사 또는 Validator 작업이 진행 중이다. |
| `succeeded` | 기술적 pipeline이 오류 없이 끝났다. 승인 여부는 반드시 `disposition`을 따로 확인한다. |
| `failed` | provider, timeout, schema decoding 같은 기술 오류로 지식적 판정을 완료하지 못했다. |
| `cancelled` | 사용자·정책·shutdown 등에 의해 실행을 의도적으로 중단했다. |

```text
disposition
- pending
- accepted_new
- reused
- rejected
- suppressed
- needs_human
```

`disposition` 값 각주:

| 값 | 설명 |
|---|---|
| `pending` | Information으로서의 최종 판정이 아직 없다. |
| `accepted_new` | 새 canonical Information을 만들 가치가 있다고 승인됐다. |
| `reused` | **같은 Data와 같은 grounding identity**에서 exact accepted Information이 이미 있어 기존 I를 참조한다. 다른 Data가 같은 내용을 말한 경우에는 새 source-specific Information을 만든다. |
| `rejected` | Validator가 근거·의미·품질 정책을 만족하지 못한다고 정상 판정했다. |
| `suppressed` | 기존 FP 기록으로 결과가 이미 알려져 Generator/Validator 재실행을 생략했다. |
| `needs_human` | 자동 판정만으로 확정할 수 없어 candidate payload를 유지한 채 사람 판단을 기다린다. |

`execution_status=failed, disposition=pending`은 기술 실패라서 아직 Information 판정이 없다는 뜻이다. `execution_status=succeeded, disposition=rejected`는 Validator가 정상적으로 검토한 뒤 Information 승격을 기각했다는 뜻이다.

### 5.4 Information 후보 보존

검증 중에는 후보 content, locator, structured payload를 Scriptorium의 `TemporaryCandidate` workspace에 둔다.

terminal 결과:

- accepted_new: candidate payload를 삭제하고 canonical Information에 내용을 보존하며 Record에 exact `information_id`를 남긴다.
- reused: candidate payload를 삭제하고 기존 canonical Information과 matched Record를 참조한다.
- rejected: candidate payload를 삭제하고 Record에 FP envelope와 `reason_codes`만 남긴다.
- suppressed: candidate를 만들지 않거나 즉시 삭제하고 suppression 근거 Record를 참조한다.
- needs_human: terminal 판정 전까지 candidate payload를 유지한다.

Record에는 semantic payload를 장기 보존하지 않지만 FP만 단독으로 두지도 않는다. 어떤 D와 profile에서 무엇이 승인·재사용·기각되었는지 재현할 수 있도록 input, policy/profile version, disposition, canonical/matched refs와 reason을 함께 보존한다.

accepted Information, D2IRecord의 terminal 갱신, optional InformationSupersession, Candidate 삭제와 downstream outbox event 등록은 하나의 DB transaction으로 처리한다. 서로 다른 D에서 semantic content가 동일하다는 이유만으로 기존 Information을 재사용하지 않는다. 여러 superseded Information ref는 JSON 배열에만 숨기지 않고 FK가 있는 relation row로 저장한다.

---

