# Palimpsest Canonical Model

> 문서 상태: Current canonical architecture and terminology — CLI-first / MinerU / plain-English components / BGE-M3 defaults / modular stages / K2W / scoped architecture repairs / PostgreSQL storage identity revision 2026-09-09
>
> 적용 변경: U01(CLI 우선·GUI 마지막), U02(PDF parser=MinerU), U03(영어 구성요소 명칭), U04(BGE-M3 검색 모델 기본값), U05(MinerU 최신 안정판 정책), U06(domain·변환별 모듈화), U07(K2W 명칭 간소화), U08(검토 R01–R09 해결; R07/R08 후속 사용자 승인 포함), U09(PostgreSQL 18/pgvector·SHA-256 Data/UUIDv7 ID·도구 등록·효과 반영). 나머지 P01–P12 보완안은 별도 승인 전까지 제안 상태다.
>
> 언어: 한국어
>
> 범위: Palimpsest의 `D-I-K-W-P-B` 계층, 변환 Operation, 영속 Record, RAG 표면, Knowledge graph 성장, identity/revision/lifecycle, 중복·순환 억제, Wisdom과 자동 W2K
>
> 구현 상태 문서가 아니다. 이 문서는 무엇을 구현해야 하는지 정의하며, 현재 코드가 전부 구현했다는 뜻이 아니다.

---

## 0. 문서의 권위와 목적

이 문서는 Palimpsest의 구조와 canonical 용어를 한곳에 고정한다.

다른 기존 문서, schema, fixture, 다이어그램 또는 코드가 이 문서와 충돌할 경우, 새 구조로 정리하는 작업에서는 이 문서를 우선한다. 기존 자산은 즉시 삭제하지 않고 migration 또는 호환성 검토를 거쳐 이 문서에 맞춘다.

이 문서가 고정하는 핵심은 다음과 같다.

1. `D`는 별도 Source 아래의 추출물이 아니라 사용자가 넣은 불변 원본 자체다.
2. `I`는 D에 근거하며 독립적인 의미와 검색 가치를 가진 검증된 불변 객체다.
3. `K`는 승인된 `KNode`와 `KEdge`의 revision-aware graph다.
4. `W`는 KGraph, Query, 당시 Context를 결합한 사람 중심의 설명·추천·결정이다.
5. `P`는 하나 이상의 W를 구성한 독립 문서이고, `B`는 Parchment의 구조화된 집합이다.
6. `D2I`, `I2K`, `N2E`, `K2K`, `K2W`, `W2K`는 분석·제안·검증·편입을 수행하는 Operation이다.
7. `*Record`는 승인·기각·재사용·억제 fingerprint를 보존하는 영속 원장이다.
8. Candidate의 semantic payload는 Compiler Runtime의 임시 작업물이며 canonical 객체가 아니다.
9. 확정된 `Decision W`는 자동으로 W2K되어 `decision` KNode가 된다.
10. Knowledge propagation은 fingerprint/visited guard와 material-delta gate로 동일 계산을 반복하지 않으며, 선택한 scope/watermark와 그 causal descendants의 모든 material obligation이 소진되는 quiescence를 목표로 한다. dependency 열거·outbox·in-flight·retry·blocked/human 의무와 completion fence를 함께 검사하며 전역 가능한 지식의 수학적 종료를 보장하지 않는다. propagation의 크기·깊이·Record 수·token·cost cap은 정상 종료 조건으로 사용하지 않는다.
11. 새 I가 기존 I를 대체하면 과거 provenance는 유지하고 직접 연관 K부터 convergent revalidation을 시작한다.
12. Information identity는 originating Data와 exact grounding에 종속되며, 서로 다른 D의 같은 문장을 하나의 I로 병합하지 않는다.
13. K의 semantic reuse와 새 grounding 추가는 별개 effect이며, 같은 의미의 독립 근거는 Revision 없이 append-only grounding으로 보존한다.
14. KNode Revision이 바뀌면 과거 KEdge endpoint는 보존하되 current graph applicability를 자동 상속하지 않고 incident edge를 재검증한다. 관계 의미가 materially 변하지 않으면 새 KEdgeRevision을 만들지 않고 applicability만 재확인한다.
15. K lifecycle과 epistemic 상태는 immutable semantic payload와 분리된 append-only event/projection으로 관리한다.
16. K2K derivation depth는 propagation root가 바뀌어도 누적해 epistemic distance를 추적하지만, 그 수치 자체를 propagation cutoff나 자동 rejection cap으로 사용하지 않는다.
17. Decision은 semantic proposition이 아니라 authority-confirmed event이며, 서로 다른 Decision Wisdom은 내용이 같아도 별도 decision event다.
18. deterministic W2K에 필요한 subject/scope/constraints/effective_at은 Decision W 자체에 구조화해 보존한다.
19. propagation이 수렴하지 않고 revision oscillation이나 runaway queue를 보이면 정상 완료로 자르지 않고 operational anomaly로 정지·보고한다.
20. 개발·사용의 우선 interface는 CLI다. import/검토/질의/결정/출판/관리까지 headless로 완결하고, GUI는 CLI release 검증 뒤 마지막 별도 단계로 미룬다.
21. D2I의 PDF 파싱은 MinerU adapter를 사용한다. parser 출력은 비canonical 파생물이며, D-grounded validation을 통과한 Information만 Canonical Store에 편입한다.
22. 세 책임 영역의 현재 영어 명칭은 Artifact Store, Canonical Store, Compiler Runtime이다. 코드 식별자는 artifact_store, canonical_store, compiler_runtime이며 책임·계층·canonical identity를 변경하지 않는다.

이 문서에서 구조 예시 아래의 **필드 각주**는 각 필드의 의미와 사용 시점을 설명한다. SQL 자료형, 길이, index와 최종 nullability는 migration/DDL에서 확정한다. `optional`은 해당 상황이 아닐 때 값이 없을 수 있다는 뜻이다.

---

## 1. 한 문장 정의

> **Palimpsest는 불변 원본 Data를 검색 가능한 Information으로 구조화하고, Information과 기존 Knowledge를 검증된 Knowledge graph로 계속 컴파일하며, 그 graph와 사용자 Query·Context를 결합해 설명·추천·결정을 만들고, 확정된 결정과 문서를 출처까지 추적 가능하게 보존하는 provenance-first knowledge compiler다.**

짧은 영문 소개는 다음과 같다.

> **A provenance-first knowledge compiler that transforms raw data into reviewed knowledge networks, context-aware wisdom, and source-traceable publications.**

---

## 2. 세 가지 책임 영역

### 2.1 Artifact Store

`Artifact Store`은 local artifact storage다.

주요 책임:

- 사용자가 넣은 D 원본 bytes 보존
- 파일 또는 payload의 안정적인 상대 경로 제공
- hash 검증을 통한 손상 탐지
- Canonical Store가 가리키는 artifact를 읽을 수 있게 함

Artifact Store은 지식의 진실성, Information validation, Knowledge 승인 또는 검색 순위를 결정하지 않는다.

### 2.2 Canonical Store

`Canonical Store`는 canonical storage modules다.

주요 책임:

- D metadata와 append-only DataAcquisition
- validated immutable Information
- accepted KNode/KEdge와 immutable revision
- K lifecycle event와 current applicability projection
- grounding과 provenance
- Wisdom, Parchment, Book
- canonical 객체에서 재생성 가능한 embedding·검색 projection

Canonical Store에는 승인되지 않은 I/K Candidate나 terminal rejected semantic payload를 넣지 않는다.

### 2.3 Compiler Runtime

`Compiler Runtime`은 knowledge compilation runtime이다.

주요 책임:

- D2I, I2K, N2E, K2K, K2W, W2K orchestration
- Generator와 Validator 실행
- 관련 I/K retrieval과 candidate context 구성
- 후보별 `D2IRecord`와 `KCompilationRecord` 보존
- 공통 Operation execution과 model-call telemetry 보존
- pending Candidate의 임시 payload 보존
- 선택적 bounded-retention rejected-candidate audit 보존
- fingerprint lookup과 duplicate suppression
- material-delta-gated convergent propagation, retry, anomaly detection, alert, model-call telemetry

U09에 따라 초기 Canonical Store와 Compiler Runtime은 하나의 PostgreSQL 18 database 안의 canonical_store/compiler_runtime schema로 나누고 transaction을 공유한다. pgvector를 사용하고 실제 minor/extension version을 profile에 기록하며 이후 major 업그레이드는 별도 검증한다. Artifact Store는 Palimpsest 도구가 관리하는 로컬 파일 영역이다. 후보의 검증된 효과를 canonical에 반영해도 Runtime의 영속 판정 Record는 이동·삭제하지 않는다.

### 2.4 영어 식별자와 interface 경계

`Artifact Store`는 `artifact_store`, `Canonical Store`는 `canonical_store`, `Compiler Runtime`은 `compiler_runtime`으로 표기한다. 원본 artifact의 상대 경로 필드는 `artifact_path`다. 아래 relational skeleton의 namespace 역시 `canonical_store`와 `compiler_runtime`을 사용한다.

이 이름 변경은 역할을 설명하기 위한 것이며 새로운 D-I-K-W-P-B 계층이나 서비스 분리를 뜻하지 않는다. 기존 DB schema, 파일 경로, API 이름은 inventory와 승인된 migration을 거쳐 바꾼다. 기존 ID·hash·fingerprint envelope·과거 provenance를 단순 이름 변경 때문에 재작성하지 않는다.

CLI는 application service를 호출하는 얇은 adapter다. domain/compiler를 CLI argument 처리나 GUI framework에 결합하지 않는다. GUI가 없어도 모든 핵심 기능과 human review/authority confirmation을 수행할 수 있어야 한다. U06에 따라 D/I/K/W/P/B domain과 D2I/I2K/N2E/K2K/K2W/W2K, W2P/P2B 구성 작업을 각각 모듈화하되 공통 저장/실행/전파/atomic commit을 유지한다. W2P/P2B 모듈화는 신규 Compiler Record subtype을 뜻하지 않는다.

---

## 3. 전체 계층: D-I-K-W-P-B

| 계층 | Canonical 객체 | 성격 | 기억하기 쉬운 질문 |
|---|---|---|---|
| `D` | Data | 사용자가 넣은 불변 원본 | 무엇을 보존했는가? |
| `I` | Information | D에서 검증된 검색 가능한 의미 단위 | 원본이 무엇을 말하는가? |
| `K` | KNode, KEdge | 승인된 reusable knowledge graph | 무엇을 지식으로 채택했는가? |
| `W` | Wisdom | Query와 Context에 따른 설명·추천·결정 | 지금 무엇을 설명·추천·결정하는가? |
| `P` | Parchment | 여러 W를 구성·편집한 독립 문서 | 무엇을 문서로 남기는가? |
| `B` | Book | Parchment의 순서 있는 구조화된 집합 | 무엇을 출판 단위로 묶는가? |

기본 흐름은 선형처럼 보이지만 K 이후는 순환한다.

```text
D
└─ D2I → I
          └─ I2K → KNode
                       ├─ N2E → KEdge
                       └─ K2K → 새 KNode 또는 기존 KNode의 새 Revision
                                      └─ N2E/K2K 재전파

KGraph + Query + Context → K2W → W
확정된 Decision W       → W2K  → decision KNode → N2E/K2K
W들                      → W2P  → Parchment
Parchment들              → P2B  → Book
```

---

U08의 구체적인 적용 범위와 별도 사용자 선택은 [ARCHITECTURE_FIXES](../decisions/ARCHITECTURE_FIXES.md)를 따른다. 이 계약은 미정 public subtype/DDL/provider/stack 전체의 승인이 아니다.
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
artifact_path
original_name optional
created_at
```

필드 각주:

| 필드 | 설명 |
|---|---|
| `data_id` | 원본 전체 bytes의 SHA-256으로 확정된 canonical ID다(U09). wire/SQL 초안은 64자리 소문자 hex이며 sha256 metadata와 동일하다. |
| `sha256` | Artifact Store에 보존된 원본 bytes 전체의 SHA-256 digest다. 파일 손상 확인과 완전히 동일한 bytes 탐지에 사용하며 의미적 유사성을 뜻하지 않는다. |
| `media_type` | `application/pdf`, `text/markdown` 같은 MIME type이다. 어떤 parser 또는 D2I profile을 적용할지 선택하는 기본 단서다. |
| `byte_size` | 원본 payload의 byte 단위 크기다. 저장·전송 검증과 운영 한도 확인에 사용한다. |
| `artifact_path` | Artifact Store 안에서 원본을 찾는 안정적인 상대 경로 또는 storage key다. 사용자의 임의 절대 경로를 canonical identity로 사용하지 않는다. |
| `original_name` | 가져올 당시의 파일명이나 표시 이름이다. 사람이 알아보기 위한 선택 필드이며 identity나 중복 판정에는 사용하지 않는다. |
| `created_at` | Data가 Palimpsest에 canonical 등록된 시각이다. 원문이 작성되거나 파일이 외부에서 생성된 시각과는 다르다. |

U09: data_id는 실제 보존한 원본 bytes의 SHA-256이다. 새 request로 동일 bytes를 등록하면 duplicate_data와 기존 ID를 반환하고 새 Data/acquisition/D2I를 만들지 않는다. 같은 request와 입력의 성공 retry는 기존 결과를 반환한다. 파일명 변경은 identity를 바꾸지 않지만 같은 논문의 다른 bytes는 별도 D이며 자동 의미 중복 기각은 하지 않는다. 나머지 신규 opaque 객체·revision·Record·execution·acquisition ID는 UUIDv7이고 fingerprint/외부 ID/version/counter/commit token은 그대로다.

### 4.4 관리 범위

D는 원본이므로 복잡한 lifecycle을 두지 않는다. 필요한 관리는 다음 정도다.

- 존재 여부
- bytes/hash 일치 여부
- Artifact Store 접근 가능 여부
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

`DataAcquisition`은 새로운 S 계층이 아니다. 동일 SHA-256 Data의 독립 수집 사건을 명시적으로 기록하면 append-only acquisition을 추가할 수 있다. 평범한 duplicate import에는 자동 추가하지 않는다. 반복 등록 실수와 실제 독립 출처 provenance를 혼동하지 않는다.

U09: 원본은 CLI/application service로 제공하고 도구가 관리 root 내부 staging으로 복사·해시·검증한다. 사용자 원본을 이동·삭제하지 않는다. 준비한 등록 journal, overwrite 없는 content-addressed publish, Data/acquisition/성공 receipt의 atomic DB commit과 reconcile을 사용한다. 직접 폴더에 복사한 파일은 자동 등록하지 않는다. 같은 request staging의 배타 소유, 공유 object 무결성 검증, 실패한 요청이 다른 요청의 원본을 삭제하지 않는 cleanup 경계를 보장한다.

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
| `context_fingerprint` | Validator 호출 전 frozen content·exact Data/input·전달한 authoritative neighbor refs·deterministic-check version/result·model/policy/schema version을 묶은 digest다. 사후 used refs는 별도 attribution이며 이 key를 대체하지 않는다. contextual rejection과 재검토 범위를 구분한다. |
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

후보가 하나도 나오기 전의 provider 오류, 정상적인 zero-output 완료, retry와 전체 호출 timing은 공통 Compiler Runtime Operation execution log에 남긴다. 이 log는 기술적 실행 기반시설이며 별도의 공개 D2I domain 객체가 아니다. 일반 D2I의 D당 1회 성공도 이 execution log의 atomic idempotency guard로 보장한다.

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

검증 중에는 후보 content, locator, structured payload를 Compiler Runtime의 `TemporaryCandidate` workspace에 둔다.

terminal 결과:

- accepted_new: candidate payload를 삭제하고 canonical Information에 내용을 보존하며 Record에 exact `information_id`를 남긴다.
- reused: candidate payload를 삭제하고 기존 canonical Information과 matched Record를 참조한다.
- rejected: candidate payload를 삭제하고 Record에 FP envelope와 `reason_codes`만 남긴다.
- suppressed: candidate를 만들지 않거나 즉시 삭제하고 suppression 근거 Record를 참조한다.
- needs_human: terminal 판정 전까지 candidate payload를 유지한다.

Record에는 semantic payload를 장기 보존하지 않지만 FP만 단독으로 두지도 않는다. 어떤 D와 profile에서 무엇이 승인·재사용·기각되었는지 재현할 수 있도록 input, policy/profile version, disposition, canonical/matched refs와 reason을 함께 보존한다.

독립 extraction은 accepted Information, D2IRecord terminal 갱신, Candidate 처리와 downstream outbox를 한 short transaction으로 처리한다. split/merge는 같은 교체 의미 단위의 replacement set 전체를 검증한 뒤 activation·supersession·old-I retirement·관련 Records·outbox를 하나의 commit unit으로 publish한다. 일부 replacement 실패 때 old I를 조기 퇴역시키지 않는다. 입력 상태 검증은 동시 writer와 commit까지 충돌 검출되어야 하며 generation 증가만으로 과거 I 전체를 폐기하지 않는다. 서로 다른 D에서 semantic content가 동일하다는 이유만으로 기존 Information을 재사용하지 않는다. 여러 superseded Information ref는 JSON 배열에만 숨기지 않고 FK가 있는 relation row로 저장한다.

---


### 5.5 PDF parser — MinerU

PDF D의 파싱 엔진은 MinerU로 고정한다. 다른 형식의 parser와 Generator/Validator model은 이 결정으로 고정되지 않는다. 입력은 Artifact Store에 보존한 exact D bytes이며 parser가 만든 Markdown/JSON/images는 새로운 사용자 원본 D나 승인된 I로 자동 승격하지 않는다.

실행 흐름은 `PDF D → MinerU adapter → 비canonical parse artifact/정규화된 layout blocks → D2I proposal → grounding/semantic validation → Information commit`이다. MinerU 성공과 D2I semantic acceptance는 독립된 결과다.

버전·backend·model artifact 식별자·실효 설정·페이지 처리 범위·출력 hash를 parser execution과 함께 기록한다. source page/region을 보존한 structured output을 grounding에 사용하며 Markdown의 문자 offset을 원본 PDF의 exact anchor로 착각하지 않는다. 출력 형식과 좌표 계약은 선택한 MinerU 버전에 대해 adapter가 검증한다.

현재 구현은 로컬 MinerU CLI 또는 같은 머신의 loopback worker를 기본으로 계획한다. 공개 hosted API/외부 inference endpoint로 문서를 보내는 것은 별도 전송 승인 없이는 허용하지 않는다. 설치 실패·지원하지 않는 출력·부분 파싱은 명시적인 실행 실패/partial로 남긴다. 다른 parser로 조용히 fallback하거나 일부 페이지만 읽고 전체 성공으로 표시하지 않는다.

파싱 단계의 page window/concurrency/timeout은 처리 단위와 기술적 제한일 뿐, Knowledge propagation을 정상 완료로 자르는 size/depth/cost cap이 아니다. 구체적인 MinerU 버전/backend/hardware profile과 adapter wire schema는 T00/T01에서 확인하고 고정한다.

---
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
| `created_at` | Validator 승인을 거쳐 Canonical Store에 immutable Information으로 편입된 시각이다. |

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

같은 split/merge replacement set은 전체 검증 후 한 commit에서 활성화하며 partial set을 기본 RAG에 섞지 않는다. 관계 table은 다대다를 허용한다. 재추출 과정에서 I 하나가 여러 I로 분리되거나 여러 I가 하나로 합쳐질 수 있기 때문이다. 다만 supersession relation은 directed acyclic graph(DAG)여야 하며 self-edge와 cycle을 허용하지 않는다.

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

새 I가 기존 I를 supersede하면 Compiler Runtime은 기존 I를 현재 active support/dependency로 사용하는 K를 누락 없이 재검증 대상으로 등록한다. 최초 생성 provenance도 보존하되 현재 support와 구분한다.

```text
new Information I2 accepted
+ I2 supersedes I1
→ I1의 current active support/dependency에 연결된 accepted KNodeRevision 조회
→ 각 current KNodeRevision에 대해 revalidation 예약
→ 새 I2와 관련 usable I를 근거로 Validator 재검증
```

재검증 원칙:

1. 기존 KNodeRevision과 그 `information_id=I1` provenance는 수정·삭제하지 않는다.
2. 새 I2가 생겼다는 이유만으로 기존 K를 자동 무효화하거나 Revision을 만들지 않는다.
3. I2K는 I2와 관련 I를 사용해 새 K 또는 기존 K의 material Revision 가능성을 검토한다.
4. 기존 K가 여전히 유효하면 semantic Revision 없이 `no_material_delta`와 검증된 current support receipt를 append하고, 새 I2→K dependency 및 이전 support의 활성 상태를 같은 commit에서 갱신한다. 최초 provenance는 치환하지 않는다.
5. 같은 K identity의 의미가 materially 바뀌면 새 immutable KNodeRevision 후보를 검증한다.
6. 기존 K가 더 이상 성립하지 않으면 invalidation/supersession 또는 semantic KEdge 후보를 검증한다.
7. 직접 영향받은 K에서 material graph delta가 실제로 발생한 경우에만 그 K를 입력으로 사용하는 간접 downstream K를 재검증한다. `no_material_delta` 또는 non-material effect는 새 semantic branch를 만들지 않는다. support/dependency 갱신, projection 및 기존 blocked obligation release는 maintenance로 수행하며 다른 material input에서 이미 생긴 의무를 삭제하지 않는다.
8. 각 재검증 attempt에는 FP, causal root, propagation depth metadata와 visited guard를 적용해 동일 exact state/input을 반복 검증하지 않는다. propagation size/depth/Record/token/cost hard cap은 정상적인 semantic 종료 조건으로 사용하지 않는다.

current support receipt는 target exact revision, 검증된 current I/K/effective-edge refs, 이전 receipt와의 연결, outcome/Validator profile/origin Record/commit order를 보존하고 active support·reverse dependency를 재구성한다. 각 재검증 Record는 trigger가 된 supersession/invalidation ref, 영향받은 exact KNodeRevision, 새 replacement I 또는 남아 있는 usable Information IDs, validator profile, FP, terminal outcome과 canonical effect를 보존한다. retrieval snapshot만으로 이 input들을 대신하지 않는다.

Information과 supersession 관계의 commit, 그리고 K 재검증 event의 outbox 등록은 같은 transaction에서 수행한다. worker가 지연되거나 재시도되더라도 event를 잃지 않아야 한다. 재검증 attempt는 `KCompilationRecord`의 FP·causality·terminal-disposition contract를 따르되 기존 I2KRecord나 K2KRecord에 억지로 분류하지 않는다. 별도 public Operation/Record subtype 명칭은 실제 schema 설계 전에 사용자 승인을 받아 결정한다.

대체 I 없이 기존 I만 invalidated된 경우에도 같은 직접 연관 K 재검증을 수행한다. 이때 Validator는 invalidated I를 새 근거로 사용하지 않고, 남아 있는 usable I와 기존 K provenance를 기준으로 K가 여전히 성립하는지 평가한다.

---

## 7. K — Knowledge graph

### 7.1 정의

Knowledge는 승인된 KNode와 KEdge의 revision-aware graph다.

```text
KGraph
= current usable accepted KNodeRevisions
+ current-applicable usable accepted KEdgeRevisions
```

`KGraph`는 별도 canonical 단일 객체나 mutable blob이 아니다. Canonical Store의 KNode/KEdge 논리 객체, current revision pointer, append-only lifecycle events와 edge applicability 규칙에서 재구성되는 projection이다.

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

KNodeRevision은 문체 변화가 아니라 material semantic delta에만 생성한다. current revision 갱신은 `expected_base_revision_id`를 확인하는 atomic compare-and-swap으로 수행해 concurrent sibling Revision을 방지한다. target base뿐 아니라 검증에 사용한 input lifecycle/applicability/evidence/authority read-set도 같은 commit의 충돌 검출 범위에 포함한다. 상태 확인 이후 commit 사이의 writer를 놓치는 단순 사전 SELECT는 충분하지 않다. base/read-set이 바뀌면 새 current state에서 재검증한다.

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

current KGraph는 edge와 양 endpoint의 usability를 검사한 뒤 exact semantic edge revision + current endpoint pair에 다음 순서를 적용한다.

```text
1. 동일 revision/pair의 최신 명시적 applicability 판정이 있으면 우선 적용
2. 최신 not_applicable이면 initial endpoint가 일치해도 제외
3. 명시적 판정이 없고 initial approved endpoint pair와 일치할 때만 최초 승인 사용
4. 그 밖은 pending/unknown; 관계 부정으로 해석하지 않음
```

최신 순서는 commit order/token으로 정하며 다른 pair/과거 semantic revision의 판정이나 timestamp 동률로 대체하지 않는다. EffectiveEdgeRef는 semantic_kedge_revision_id, 실제 from/to revision IDs, applicability basis type/ref, read-state token을 묶고 exact input/citation/projection key에 보존한다.

endpoint가 바뀐 뒤 아직 revalidation이 끝나지 않았으면 해당 edge는 current KGraph에서 일시 제외한다.

revalidation 결과가 다음과 같을 때 canonical effect와 propagation은 구분한다.

```text
relation semantic unchanged + applicable
→ KEdgeRevision 생성 없음
→ KEdgeApplicabilityEvent(applicable)
→ disposition = no_material_delta
→ propagation_impact = non_material
→ 새 semantic branch 없음; current support/projection 및 기존 blocked 의무 release는 maintenance

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

같은 confirmed true→true rebasing은 non-material이고 이미 endpoint 변경으로 생성된 consumer obligation을 없애지 않는다. false→false 반복 부정은 새 material cascade를 만들지 않으며 실제 true↔false 적용 변화는 영향 범위를 검증한다. 필수 입력 pending은 blocked/unknown이며 negative로 간주하지 않는다. 즉 **Revision 생성 여부와 graph applicability 변화 여부를 분리**한다. endpoint rebasing만을 이유로 semantic KEdgeRevision을 증식시키지 않는다.

---

## 8. 공통 Knowledge Compiler

### 8.1 공통 구조

D2I, I2K, N2E, K2K는 입력과 출력 종류가 다르지만 같은 Generator–Validator compiler skeleton을 사용한다. 결정론적인 W2K는 이 중 fingerprint, Record와 atomic commit 부분을 재사용하되 LLM Generator·Validator를 호출하지 않는다.

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

하나의 Generator LLM과 하나의 Validator LLM을 D2I/I2K/N2E/K2K Operation이 공유할 수 있다.

Operation마다 다음은 별도 profile로 둔다.

- system prompt와 prompt version
- input selection policy
- structured output schema
- validation policy
- 허용되는 canonical effect
- token/context budget

여기서 token/context budget은 **한 번의 Generator/Validator 호출에 제공할 입력 context의 크기**를 제한하는 실행 설정이다. 전체 propagation의 거리, branch 수, Record 수, 총 token 또는 총 cost를 잘라 정상 완료로 만드는 propagation cap이 아니다.

이 구조는 비유적으로 GAN과 닮았지만 학습 방식의 GAN은 아니다. canonical 용어로는 `Generator–Validator` 또는 `Proposer–Verifier` pipeline을 사용한다.

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

Validator가 review boundary를 담당하고, 최종 validator decision과 effect는 해당 `D2IRecord`, `I2KRecord`, `N2ERecord`, `K2KRecord`에 기록한다. 결정론적인 W2K effect는 `W2KRecord`에 기록한다.

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
| `proposed_kind_or_predicate` | Information/KNode의 kind 또는 KEdge predicate처럼 적용할 구조화 schema를 선택하는 값이다. |
| `proposed_semantic_payload` | Generator가 제안하고 Validator가 검토할 전체 구조화 의미다. terminal 처리 후 Record에 장기 보존하지 않는다. |
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
## 11. Fingerprint와 중복 억제

### 11.1 네 가지 fingerprint와 rejection scope

| 이름 | 계산 시점 | 포함하는 핵심 | 목적 |
|---|---|---|---|
| `attempt_fingerprint` | Generator 호출 전 | Operation, semantic trigger kind, frozen input/state/profile; opaque cause/root ID는 별도 | 같은 분석 조합의 LLM 재호출 방지 |
| `identity_fingerprint` | candidate 구조화 후 | 논리 객체 identity projection | 새 객체인지 기존 객체인지 판정 |
| `content_fingerprint` | candidate 구조화 후 | canonical semantic payload | 정확히 같은 accepted/rejected 내용 탐지 |
| `context_fingerprint` | Validator 실행 전 | frozen content + exact inputs + 전달한 authoritative context + deterministic-check 결과/version + policy/model/schema versions | 범위가 있는 기각·재검토 판정 |

모든 fingerprint envelope는 최소한 algorithm, domain, projection version, canonicalization version, digest를 가진다.

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

## 13. I2K

### 13.1 Trigger와 입력

새 validated usable Information이 생기면 I2K를 실행한다.

```text
seed Information
+ same-D related Information
+ corpus RAG related Information
→ context-bounded Information set
→ I2K Generator
→ KNode proposal(s)
```

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

## 17. Convergent propagation

I2K, N2E, K2K, W2K와 Information supersession/invalidation 기반 K 재검증은 서로 후속 작업을 만들 수 있다. Palimpsest는 이를 recursion이나 고정 크기 budget으로 자르지 않고, **material effect의 필수 dependency를 모두 열거하고 scoped quiescence를 확인하는 event propagation**으로 실행한다.

### 17.1 Causality와 관찰 가능성

모든 KCompilationRecord는 다음을 가진다.

```text
root_record_id
parent_record_id
propagation_depth
```

필드 각주:

| 필드 | 설명 |
|---|---|
| `root_record_id` | 하나의 연쇄적 Knowledge compilation을 처음 시작한 Record다. 해당 root/scope의 causal obligation과 scoped completion을 추적하는 기준이다. |
| `parent_record_id` | 현재 Record를 직접 발생시킨 직전 Record다. |
| `propagation_depth` | root에서 현재 Record까지의 실행 단계를 기록하는 causality/observability metadata다. 값이 커졌다는 이유만으로 branch를 종료하지 않는다. |

root 아래의 Record chain은 cycle 없이 재구성 가능해야 한다. `propagation_depth`와 `derivation_depth`는 추적과 설명을 위한 값이지 hard cutoff가 아니다.

### 17.2 Material-delta gate

후속 propagation은 disposition 이름만으로 결정하지 않고 `canonical_effects`와 `propagation_impact`를 함께 본다.

```text
propagation_impact = material
→ affected downstream object를 재검증

propagation_impact = non_material | none
→ 새 downstream branch를 만들지 않음
→ 새 semantic branch만 종료; support/dependency maintenance·기존 의무 release는 보존
```

대표적인 `material` effect:

- 새 KNode/KEdge의 acceptance
- KNode/KEdge의 material semantic Revision acceptance
- usable object의 invalidation/supersession처럼 current graph 의미를 바꾸는 lifecycle effect
- `KEdgeApplicabilityEvent(not_applicable)`처럼 current graph에서 관계의 적용 여부가 materially 달라지는 effect

대표적인 `non_material` effect:

- `no_material_delta`
- style/paraphrase-only 차이
- 동일 semantic K에 대한 `grounding_added`
- endpoint 변경 뒤 relation semantic이 그대로임을 확인한 `KEdgeApplicabilityEvent(applicable)`
- 검색 projection/embedding 재생성처럼 canonical semantic graph를 바꾸지 않는 effect

따라서 **재검증 결과의 차이가 무시 가능하면 Node/Edge semantic Revision을 만들지 않고 그 객체에서 propagation branch를 종료한다.**

### 17.3 Scoped quiescence — propagation hard cap 없음

정상 종료는 명시된 scope/source watermark/policy와 그 입력이 유발한 causal descendants에 대해 다음을 함께 만족할 때다.

> **필수 dependency 열거가 완료되고 pending outbox·ready·leased/in-flight·retry·blocked/human 의무가 없으며, 동시 obligation 등록과 충돌하는 completion fence/checkpoint로 그 상태를 확인했다.**

maintenance/revalidation은 exact reverse dependencies를 누락 없이 page 단위로 열거한다. discovery/context의 top-K가 필수 의무를 제한하지 않는다. scope/watermark·정책·열거 coverage·미완료 의무·종료 사유를 receipt로 남긴다. watermark 뒤에 commit된 causal descendant도 원래 scope의 의무이며 제외하지 않는다. 외부 새 입력은 새 scope가 될 수 있다. discovery zero-output은 그 context의 결과이며 전역 가능한 지식의 수학적 fixed point 증명이 아니다.

즉 다음과 같은 propagation-level hard cap을 정상 completion 조건으로 두지 않는다.

```text
max_depth
max_records
max_generator_calls
max_validator_calls
max_total_tokens
max_total_cost
propagation_deadline
per_logical_object_revision_limit
max_epistemic_derivation_depth
```

실제 변화가 10단계 뒤까지 이어지면 10단계까지, 100,000개의 객체에 material 영향이 있으면 그 scope의 모든 영향 의무가 소진될 때까지 재검증한다. 반대로 바로 다음 객체에서 `no_material_delta`가 나오면 새 semantic branch는 끝나지만 검증된 support/dependency 갱신과 이미 존재하는 의무는 보존한다.

한 번의 LLM 호출에는 provider/context-window 한계와 timeout이 있을 수 있다. 이는 해당 Operation attempt의 기술적 실행 제한이며, 전체 propagation을 “충분히 처리했다”고 간주해 잘라내는 semantic cap이 아니다. 기술 실패는 retry/resume 대상으로 남긴다.

### 17.4 Visited/idempotency guard

cap을 없애더라도 동일 graph state의 동일 계산을 반복해서는 안 된다. 같은 compiler profile 안에서 다음 조합은 재실행하지 않는다.

- 동일 attempt fingerprint
- 동일 N2E semantic edge + exact current endpoint revision pair + policy
- 동일 K2K input subgraph fingerprint
- 동일 logical object가 동일한 effective input/context fingerprint에서 이미 terminal 검토됨

visited guard는 propagation 범위를 임의로 줄이는 heuristic이 아니라 **동일 상태에 대한 중복 계산 방지**다. input revision, relevant validation context 또는 policy가 materially 달라지면 새 attempt가 될 수 있다.

### 17.5 Derivation depth의 역할

`derivation_depth`와 evidence distance는 root를 넘어 누적한다. 그러나 특정 숫자를 넘었다는 이유만으로 K를 거부하거나 propagation을 중단하지 않는다.

```text
derivation_depth
→ provenance/uncertainty/inspection metadata
→ Validator가 근거의 간접성을 이해하는 신호
→ hard cutoff 아님
```

간접 derivation이 길수록 transitive grounding, 독립 Data support, scope drift와 uncertainty를 더 면밀히 평가할 수 있지만 최종 판단은 근거와 semantic validity에 의해 이루어진다.

### 17.6 Operational anomaly와 비수렴

고정 cap을 제거했다고 해서 실제 버그나 oscillation을 무한 실행해야 한다는 뜻은 아니다. 다음 현상은 정상적인 semantic convergence가 아니라 operational anomaly다.

- 같은 logical object의 Revision이 앞뒤 의미로 반복 oscillation
- queue frontier가 장기간 줄지 않고 동일 component를 반복 순환
- CAS conflict/retry가 비정상적으로 반복
- 동일 causal component에서 예상할 수 없는 revision churn이 지속
- model/provider 오류 때문에 같은 기술 attempt가 계속 실패

이 경우 runtime은 작업을 성공 완료로 자르지 않고 예를 들어 `suspended_anomaly` 또는 동등한 명시적 오류 상태로 정지·보고한다. 운영자가 원인을 수정한 뒤 같은 causal root를 resume할 수 있어야 한다.

anomaly detector에는 운영상 threshold가 필요할 수 있지만, 그 threshold는 **Knowledge가 충분히 전파되었다고 판정하는 epistemic cap이 아니다.**

### 17.7 Profile 변경

model/prompt/policy version이 바뀌었다는 이유만으로 모든 과거 입력 조합을 자동 재실행하지 않는다. 새 D/I/K trigger 또는 명시적 recompile 요청이 있을 때만 다시 탐색한다.

---

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
## 23. P — Parchment와 B — Book

### 23.1 Parchment

Parchment는 하나 이상의 Wisdom을 사람, LLM, deterministic script 또는 그 조합이 구성·편집한 독립 문서다.

```text
Parchment
- parchment_id
- title
- body
- input_wisdom_ids
- direct K revision refs / Information IDs optional
- citations
- actor/tool/model/script provenance
- supersedes_parchment_id optional
- created_at
```

필드 각주:

| 필드 | 설명 |
|---|---|
| `parchment_id` | 하나의 완성된 immutable 문서 artifact ID다. |
| `title` | 사람이 문서를 식별할 수 있는 제목이다. identity 자체로 사용하지 않는다. |
| `body` | 여러 Wisdom과 인용을 구성해 만든 최종 문서 내용이다. |
| `input_wisdom_ids` | 문서 구성에 실제 사용한 exact immutable Wisdom IDs다. |
| `direct K revision refs / Information IDs` | Wisdom을 거치지 않고 문서가 직접 인용·사용한 exact K Revision 또는 Information 참조다. 필요하지 않으면 비어 있다. |
| `citations` | body의 구절을 W/K/I/Data grounding으로 연결하는 인용 mapping이다. |
| `actor/tool/model/script provenance` | 사람, LLM, deterministic script 중 누가 어떤 방식으로 문서를 구성·편집했는지 재현하는 provenance 묶음이다. |
| `supersedes_parchment_id` | 이 문서가 대체하는 이전 Parchment ID다. 이전 Parchment는 수정·삭제하지 않는다. |
| `created_at` | 이 immutable Parchment가 생성된 시각이다. |

Parchment는 그 자체가 immutable artifact다. `ParchmentRevision`을 두지 않는다. 편집하면 새 Parchment를 만들고 `supersedes_parchment_id`로 연결한다.

### 23.2 Book

Book은 Parchment를 순서와 구조에 따라 묶은 immutable publication artifact다.

```text
Book
- book_id
- title
- description
- ordered sections
- exact parchment_ids
- supersedes_book_id optional
- created_at
```

필드 각주:

| 필드 | 설명 |
|---|---|
| `book_id` | 하나의 immutable publication 구성을 식별하는 canonical ID다. |
| `title` | Book의 표시 제목이다. |
| `description` | Book의 목적, 독자 또는 포함 범위를 설명한다. |
| `ordered sections` | section 제목, 순서와 포함 Parchment 배치를 정의하는 구조다. |
| `exact parchment_ids` | Book에 실제 포함된 immutable Parchment IDs다. current 문서를 암묵적으로 따라가지 않는다. |
| `supersedes_book_id` | 새 구성이 대체하는 이전 Book ID다. 이전 Book도 역사적 publication으로 남긴다. |
| `created_at` | 이 Book 구성이 생성·발행된 시각이다. |

`BookRevision`을 두지 않는다. 구성이 바뀌면 새 Book을 만든다.

---

## 24. RAG와 projection

### 24.1 기본 검색 대상

필수 RAG corpus:

1. usable validated Information
2. current usable accepted KNodeRevision
3. current-applicable usable accepted KEdgeRevision

Wisdom은 KGraph의 대체 검색 corpus가 아니다. decision trace, Parchment composition, history 탐색을 위해 별도 W 검색 projection을 둘 수 있다.

### 24.2 KEdge projection

KEdge embedding input은 predicate 한 단어만 사용하지 않는다.

```text
from-node semantic projection
+ predicate
+ to-node semantic projection
+ edge qualifier projection
```

Retrieval 결과는 exact semantic KEdgeRevision·실제 endpoint revision pair·applicability basis/read-state token의 EffectiveEdgeRef를 반환한다. embedding/input profile과 함께 projection key에 포함하고 과거 refs는 보존한다.

### 24.3 Projection 원칙

- embedding은 canonical truth가 아니다.
- model/profile/dimensions/normalization/input projection version을 기록한다.
- 새 Information 또는 새 K Revision은 새 projection을 만든다.
- stale-endpoint KEdgeRevision은 history/revalidation 검색에는 사용할 수 있지만 기본 current KGraph RAG에서는 제외한다.
- candidate/rejected embedding은 canonical corpus에 넣지 않는다.
- temporary candidate similarity index는 terminal cleanup 대상이다.

---

## 25. 최소 relational skeleton

SQL 세부 DDL은 단계별 migration이 소유하며 T02의 현재 표현은 docs/schema/T02_storage_draft.sql 검토 초안이다. U09는 최초 PostgreSQL 18 + pgvector, Data ID=원본 bytes SHA-256, 기타 신규 opaque ID=UUIDv7를 확정한다. 과거 ID나 fingerprint/version/commit ordering을 재작성하지 않는다. 책임 경계는 다음과 같다.

### 25.1 Canonical Store

```text
canonical_store.data
canonical_store.data_acquisitions

canonical_store.information
canonical_store.information_groundings
canonical_store.information_supersessions
canonical_store.information_invalidations

canonical_store.knowledge_nodes
canonical_store.knowledge_node_revisions
canonical_store.knowledge_edges
canonical_store.knowledge_edge_revisions
canonical_store.knowledge_edge_applicability_events
canonical_store.knowledge_groundings
canonical_store.k_lifecycle_events

canonical_store.wisdom
canonical_store.wisdom_inputs
canonical_store.wisdom_citations

canonical_store.parchments
canonical_store.books
canonical_store.book_sections

canonical_store.provenance
canonical_store.embeddings
```

### 25.2 Compiler Runtime

```text
compiler_runtime.data_import_requests
compiler_runtime.operation_executions
compiler_runtime.d2i_records

compiler_runtime.k_compilation_records
compiler_runtime.k_compilation_information_inputs
compiler_runtime.k_compilation_k_inputs
compiler_runtime.k_compilation_retrieval_hits

compiler_runtime.temporary_candidates
compiler_runtime.rejected_candidate_audit optional
compiler_runtime.model_calls
compiler_runtime.runtime_errors
compiler_runtime.outbox
```

Record의 핵심 FP, input refs, disposition, canonical refs, expected base revision, canonical effects와 propagation impact는 명시적 column/FK로 둔다. 유연한 model parameters와 bounded telemetry만 JSONB를 허용한다.

---

## 26. Canonical 용어

### 26.1 계층 객체

| 용어 | 의미 |
|---|---|
| `Data` | Artifact Store에 payload가 보존된 불변 원본과 Canonical Store metadata |
| `Information` | one-Data/grounding-specific, validated, searchable immutable semantic snapshot |
| `KNode` | accepted Knowledge graph의 typed logical node; decision은 reported/authority-confirmed event origin을 구분 |
| `KEdge` | accepted KNode 사이의 typed semantic relation |
| `Wisdom` | Query·Context·KGraph에 종속된 immutable explanation/recommendation/decision |
| `Parchment` | Wisdom을 구성한 immutable 독립 문서 |
| `Book` | ordered immutable Parchment의 publication 집합 |

### 26.2 Revision과 Information 전이

| 용어 | 의미 |
|---|---|
| `InformationSupersession` | 새 Information이 기존 Information을 대체하는 append-only 다대다 관계 |
| `InformationInvalidation` | 대체 객체 없이 기존 Information을 사용 불가로 판정한 append-only 기록 |
| `KNodeRevision` | KNode의 immutable semantic snapshot |
| `KEdgeRevision` | exact endpoint revisions를 가진 KEdge의 immutable snapshot |

Information, Wisdom, Parchment, Book은 그 자체가 immutable이므로 별도 Revision wrapper를 두지 않는다.

### 26.3 Operation

| Operation | 입력 → 출력 |
|---|---|
| `D2I` | Data → validated Information set |
| `I2K` | exact Information set → KNode proposal |
| `N2E` | accepted KNodeRevision set → KEdge proposal |
| `K2K` | accepted KNode/KEdge revision subgraph → KNode proposal |
| `K2W` | accepted KGraph + Query + Context → Explanation/Recommendation Wisdom |
| `W2K` | confirmed Decision Wisdom → decision KNode와 명시적 supersedes의 atomic effect |
| `W2P` | Wisdom set + composition instruction → Parchment |
| `P2B` | ordered Parchment IDs → Book |

Operation 이름은 실행되는 행위이며 DB 객체가 아니다.

### 26.4 Record와 임시 작업물

| 용어 | 의미 |
|---|---|
| `D2IRecord` | Information proposal 한 건의 FP·판정·canonical effect 원장; 같은 호출은 batch_id 공유 |
| `KCompilationRecord` | K 생성/Revision 제안의 FP·입력·판정·canonical effect 원장 |
| `I2KRecord` | record_type=i2k인 KCompilationRecord |
| `N2ERecord` | record_type=n2e인 KCompilationRecord |
| `K2KRecord` | record_type=k2k인 KCompilationRecord |
| `W2KRecord` | record_type=w2k인 KCompilationRecord |
| `TemporaryCandidate` | pending review에만 존재하는 비canonical payload |

### 26.5 사용하지 않는 canonical 이름

다음은 새 모델의 canonical 이름으로 사용하지 않는다.

```text
Source layer
S2D
direct S2I
D2IRun
D2IRunItem
D2IBatch
D2IOutput
I2KRun
I2KRunItem
N2ERun
K2KRun
KReviewRun
InformationRevision
InformationCandidate domain object
KNodeCandidate domain object
KEdgeCandidate domain object
KRejectionRecord
DecisionReplay Wisdom kind
Note
PalimLibrary
```

`Note`는 `Parchment`, `PalimLibrary`는 `Canonical Store`로 대체한다.

---

## 27. 핵심 불변조건

1. D payload는 수정하지 않는다.
2. 동일 D bytes의 여러 수집 경로는 DataAcquisition으로 append-only 보존하며 별도 Source 계층을 만들지 않는다.
3. D2I의 exactly-once 단위는 D 전체 수명이 아니라 `data_id + extraction_profile_family + compilation_generation` logical compilation이다.
4. 평범한 retry는 같은 compilation generation을 재사용하고, 명시적 recompile/repair만 새 generation을 시작한다.
5. D2I proposal 한 건마다 D2IRecord 하나를 만들고 호출 묶음은 `batch_id`로 표현한다.
6. canonical I는 validated immutable Information뿐이며 `InformationRevision`을 두지 않는다.
7. Information identity는 exact originating Data와 grounding에 종속된다. 서로 다른 D의 동일 semantic content를 하나의 Information으로 병합하지 않는다.
8. Information grounding은 extractor/parser profile/version과 stable anchor를 보존해 locator 재현성을 확보한다.
9. Information 교정은 새 I와 append-only supersession/invalidation 관계로 표현한다.
10. Information supersession graph는 DAG이며 self-edge/cycle을 허용하지 않는다.
11. superseded/invalidated I는 삭제하지 않고 기본 RAG와 새 I2K 입력에서 제외한다.
12. 새 I가 기존 I를 supersede하면 현재 support/dependency로 기존 I를 사용하는 K를 누락 없이 재검증 대상으로 등록한다.
13. I supersession은 기존 K를 자동 수정하지 않으며 과거 K provenance는 exact old information_id를 유지한다.
14. 직접 K에서 material graph delta가 발생한 경우에만 간접 downstream K를 재검증하며, non-material/no-material은 새 semantic branch를 만들지 않되 current support/dependency maintenance와 기존 material 의무는 유지한다.
15. I2K/K2K는 허용된 KNode kind만 제안하며 K2K는 새 observation 또는 authority-confirmed decision을 만들 수 없다.
16. N2E는 KEdge semantic relation과 명시적 edge revalidation/lifecycle effect만 다룬다.
17. I/K 후보는 terminal acceptance 전까지 Canonical Store canonical 객체가 아니다.
18. accepted/rejected/suppressed FP는 해당 D2IRecord 또는 KCompilationRecord에 남는다.
19. terminal Candidate semantic payload는 accepted canonical 객체로 이동하거나 삭제한다. 선택적 audit 보존은 비canonical bounded-retention이다.
20. exact accepted semantic duplicate는 새 K semantic Revision을 만들지 않는다. 다만 새 독립 evidence는 grounding_added effect를 가질 수 있다.
21. disposition과 canonical effect는 분리한다. `reused`는 `grounding_added` 같은 side effect와 공존할 수 있다.
22. style-only 또는 paraphrase-only 변화는 K Revision을 만들지 않는다.
23. KNode/KEdge Revision과 과거 endpoint는 수정·삭제하지 않는다.
24. K current commit은 target expected base 및 input lifecycle/applicability/evidence/authority read-set을 commit까지 보호하는 atomic concurrency guard를 사용한다.
25. K lifecycle과 epistemic/decision status는 immutable semantic payload와 분리된 append-only event/projection이다.
26. 반박은 먼저 semantic KEdge로 표현하며 자동으로 상대 Node를 수정하지 않는다.
27. KNode Revision이 바뀌면 과거 incident edge는 historical provenance를 유지하고 새 current endpoint pair에 대해 applicability를 재검증한다.
28. endpoint만 바뀌고 relation semantic이 materially 동일하면 새 KEdgeRevision을 만들지 않고 KEdgeApplicabilityEvent(applicable)만 append하며 그 branch를 종료한다.
29. 기존 edge의 current applicability 상실은 “새 edge가 제안되지 않음”만으로 추론하지 않고 KEdgeApplicabilityEvent(not_applicable) 같은 명시적 revalidation decision을 요구한다. 이 material graph delta는 dependent downstream K 재검증을 유발한다.
30. 모든 propagation과 K revalidation은 causal root, propagation depth metadata, exact-input/context fingerprint와 visited guard를 가지며, size/depth/Record/token/cost hard cap을 정상 semantic completion 조건으로 사용하지 않는다.
31. K2K-derived K는 causal root와 독립적인 derivation_depth/evidence distance를 누적해 provenance와 uncertainty에 사용한다.
32. derivation_depth 값 자체는 K2K result의 자동 rejection 또는 propagation cutoff가 아니다. propagation은 scope/watermark의 causal 의무 열거·outbox·in-flight·retry·blocked/human 의무 부재와 completion fence를 확인한 quiescence에서 종료한다.
33. Query와 Context/Memory는 K2W의 임시 overlay이지 canonical K가 아니다.
34. K2W가 direct Information을 사용하면 Wisdom에 evidence_mode와 epistemic_basis를 남겨 accepted K와 구분한다.
35. Recommendation은 LLM의 제안이며 자동 W2K하지 않는다.
36. Decision W는 권한 있는 actor의 authority-confirmed event이며 deterministic W2K에 필요한 subject/scope/constraints/effective_at을 자체 보존한다.
37. 외부 Data가 보고한 decision event는 I2K의 `origin_type=reported` decision KNode로 표현하며 authority-confirmed W2K decision과 구분한다.
38. Decision W와 authority-confirmed decision KNode/W2KRecord 및 명시적으로 확인된 supersedes 효과는 원자적으로 일치해야 한다.
39. Decision event identity는 origin_wisdom_id에 고정되며 서로 다른 Wisdom은 semantic content가 같아도 같은 decision KNode로 병합하지 않는다.
40. Decision의 active/superseded/expired 상태는 semantic payload가 아니라 current projection이다.
41. Decision supersession graph는 DAG이며 실제 재결정은 새 decision event로 남긴다.
42. 과거 결정 이유는 Decision trace를 사용하는 Explanation W로 생성한다.
43. embedding과 retrieval hit는 canonical truth가 아니다.
44. global hard-rejection suppression은 invariant-hard reason에만 사용하고 contextual/policy rejection은 context fingerprint 범위에서만 억제한다.
45. 모든 파생 결과는 exact input Information/K revision, origin Record, 필요한 lifecycle/effect까지 추적할 수 있어야 한다.

---

## 28. 승인된 Architecture Decision A1–A40

| ID | 승인된 결정 |
|---|---|
| `A1` | Source를 별도 계층으로 두지 않고 D를 불변 원본으로 사용한다. |
| `A2` | D2IRecord는 Information proposal 한 건당 하나이며 D2IOutput을 두지 않고 batch_id로 호출 묶음을 표현한다. |
| `A3` | D2IRecord/I2KRecord/N2ERecord/K2KRecord/W2KRecord는 제안 한 건당 하나이며 batch_id로 호출 묶음을 표현한다. |
| `A4` | PostgreSQL에서는 공통 KCompilationRecord table과 typed record view/type을 사용한다. |
| `A5` | 승인·기각 FP와 결과를 해당 D2IRecord/KCompilationRecord에 보존하고 별도 rejection domain 객체를 두지 않는다. |
| `A6` | Generator와 Validator를 하나의 Operation pipeline에 두고 별도 KReviewRun을 두지 않는다. |
| `A7` | KNodeRevision은 material semantic delta에만 생성한다. |
| `A8` | 반박은 먼저 contradicts KEdge로 표현하고 기존 KNodeRevision을 자동 수정하지 않는다. |
| `A9` | 같은 identity의 실질적 수정만 기존 KNode의 새 Revision으로 승인한다. |
| `A10` | root/parent/depth로 causality를 추적하고 fingerprint/visited guard로 동일 상태의 중복 계산을 막되, propagation은 hard size/depth/cost cap이 아니라 scope와 causal descendants의 의무가 소진된 quiescence에서 종료한다. |
| `A11` | Query와 Memory는 임시 QueryContextGraph이며 canonical K에 직접 넣지 않는다. |
| `A12` | 확정된 Decision W만 W2K를 통해 decision KNode로 승격한다. |
| `A13` | 별도 canonical 장기 Memory 계층을 두지 않고 decision KNode와 immutable Wisdom이 장기 기억을 담당한다. |
| `A14` | Decision W 저장 시 W2K를 결정론적으로 자동 실행하여 decision KNode와 W2KRecord를 같은 transaction에서 생성한다. |
| `A15` | Wisdom kind는 explanation, recommendation, decision 세 종류다. |
| `A16` | Decision action은 select, defer, decline이다. |
| `A17` | decision_replay Wisdom kind를 제거한다. |
| `A18` | 과거 결정 설명은 query_intent=explain_decision, retrieval_strategy=decision_trace와 별도 evidence_mode를 사용하는 Explanation W다. |
| `A19` | Information은 그 자체가 immutable semantic snapshot이며 InformationRevision을 두지 않는다. |
| `A20` | Information 오류 교정·재추출은 기존 I를 수정하지 않고 새 Information을 만든다. |
| `A21` | Information 교체와 무효화는 append-only InformationSupersession/InformationInvalidation으로 기록한다. |
| `A22` | I2K와 K provenance는 exact information_id를 참조하며 supersession 뒤에도 과거 참조를 자동 치환하지 않는다. |
| `A23` | embedding·검색 index·reranker·표시 projection 변화는 새 Information을 만들지 않는다. |
| `A24` | 동일 logical D2I compilation generation은 exactly-once canonical effect를 가지며, 오류 교정·재추출은 새 compilation_generation의 명시적 recompile/repair로 수행한다. |
| `A25` | 새 I가 기존 I를 supersede하면 직접 연관 K를 재검증하고, 실제 material graph delta만 downstream convergent propagation을 이어간다. |
| `A26` | Information은 originating Data/grounding-specific evidence object이며 cross-Data semantic dedup을 하지 않는다. |
| `A27` | 동일 semantic K에 새 독립 근거가 추가되면 Revision 대신 grounding effect를 append하며 disposition과 effect를 분리한다. |
| `A28` | D2I exactly-once 단위는 logical compilation generation이며 explicit recompile/repair를 정상 경로로 모델링한다. |
| `A29` | Source layer 없이 append-only DataAcquisition으로 수집 provenance를 보존한다. |
| `A30` | K lifecycle/epistemic 상태는 append-only event와 projection으로 관리하며 semantic payload에 넣지 않는다. |
| `A31` | KNode current revision commit은 expected-base CAS를 사용한다. |
| `A32` | KNode revision 변화 후 incident KEdge는 새 current endpoint pair에 대해 N2E revalidation하며, relation semantic이 그대로면 KEdgeRevision을 만들지 않고 applicability event로 재확인한다. |
| `A33` | N2E는 discovery와 explicit edge revalidation mode를 가지며, material edge/applicability 변화만 downstream propagation을 만든다. |
| `A34` | K2K derivation depth는 propagation root와 독립적으로 누적해 epistemic distance를 추적하지만 hard depth budget이나 자동 cutoff로 사용하지 않는다. |
| `A35` | Operation×KNode-kind compatibility를 deterministic invariant로 둔다. |
| `A36` | decision KNode는 `reported`와 `authority_confirmed` origin type을 구분한다. |
| `A37` | Decision W는 deterministic W2K에 필요한 subject/scope/constraints/effective_at을 직접 보존한다. |
| `A38` | 서로 다른 Decision Wisdom은 semantic content가 같아도 별도 event이며 W2K content-based reuse를 금지한다. |
| `A39` | rejection suppression은 invariant-hard와 contextual/policy/temporary scope를 구분한다. |
| `A40` | K2W의 direct-I 사용은 evidence_mode/epistemic_basis로 명시한다. |

---

## 29. 아직 확정하지 않은 구현값

U04는 embedding 기본 BAAI/bge-m3(dense 1024)와 동일 모델의 multi-vector ColBERT 점수 재순위화를 선택했다. 두 역할은 독립 교체 가능하며 Qwen3-Embedding/Reranker 4B·8B는 향후 후보로 둔다. 필요한 재색인은 파생 projection에 한정하고 canonical history를 보존한다. U05는 MinerU의 설치/명시적 업그레이드 시 최신 안정판 선택과 exact 실행 profile 기록을 확정했다. U06은 domain/변환별 모듈화와 adapter 독립성, 공통 atomic commit 경계를 확정했다. U08은 R01–R09의 명시된 구조 수정을 적용했다. U09는 PostgreSQL 초기 major 18/pgvector와 raw-byte SHA-256 Data ID, 나머지 신규 opaque UUIDv7, 도구 관리 등록과 검증된 효과의 atomic 반영을 선택했다. 다음 값은 여전히 미정이다.

- Generator/Validator provider와 model
- embedding/reranker runtime·모델 revision/digest, dense metric, normalization; dense 기본 차원은 BGE-M3 공식 1024
- lexical/vector fusion 방식과 weight
- I2K/N2E/K2K retrieval top-K
- semantic near-duplicate threshold
- KEdge predicate 전체 registry와 endpoint matrix
- human review CLI flow와 multi-review policy; GUI 설계는 CLI release 이후 마지막 단계
- rejected candidate audit retention 기간, 암호화와 민감정보 정책
- K lifecycle/event enum과 decision status projection 규칙
- derivation/evidence-distance 표시 방식과 evidence support 평가 정책
- operational non-convergence/anomaly detection threshold와 resume 정책
- explicit D recompile/repair command, compilation_generation 증가 정책과 migration policy
- Information supersession 기반 K revalidation의 별도 public Operation/Record 명칭
- background scheduler와 worker 배치 전략
- MinerU 최신 안정판을 설치 시 다시 확인한 exact version/digest와 검증된 backend/model/hardware profile 및 출력 adapter 버전
- PostgreSQL 18의 실제 설치 minor/pgvector version·실행 위치, 앱 언어/driver/migration runner와 검증된 DB test 명령
- CLI framework·명령/옵션의 상세 문법; GUI framework는 마지막 단계 전까지 채택하지 않음

이 값들은 실제 evaluation과 구현 요구를 바탕으로 별도 승인한다.

---

## 30. 구현 순서 원칙

1. 이 문서에 맞춰 JSON/DB boundary schema와 CLI application-service 경계를 먼저 고정한다. D/I/K/W/P/B 및 변환별 모듈은 해당 단계의 실제 기능/테스트와 함께 만들고 공통 저장/실행 경계를 재사용한다. 현재 작업에서 GUI를 scaffold하지 않는다.
2. CLI skeleton/help/doctor와 D 등록·DataAcquisition·exact read/verify를 연결하고, 공통 Operation execution log와 compilation_generation 기반 D2IRecord를 구현한다.
3. PDF에는 MinerU adapter를 구현하고 CLI D2I를 연결한다. source-specific immutable Information, extractor-aware grounding, TemporaryCandidate, FP guard와 I RAG를 검증한다.
4. InformationSupersession/Invalidation DAG와 exact provenance를 구현한다.
5. KCompilationRecord, canonical_effects, K grounding과 expected-base CAS를 포함해 I2K accepted KNode vertical slice를 완성한다.
6. KLifecycleEvent, I supersession outbox와 직접 연관 K material-delta-gated revalidation을 구현한다.
7. KNode RAG와 N2E discovery/revalidation, KEdgeApplicabilityEvent와 current edge applicability projection을 구현한다.
8. KEdge RAG와 root-independent derivation_depth metadata를 가진 convergent K2K propagation을 구현한다.
9. evidence_mode/retrieval_strategy/epistemic_basis를 포함한 K2W Explanation/Recommendation을 구현한다.
10. 구조화 Decision W, event identity와 atomic automatic W2K를 구현한다.
11. decision trace를 구현한다.
12. W2P와 P2B를 CLI로 구현하고 review/provenance/job pause-resume/export까지 headless 사용자 흐름을 완결한다.
13. CLI release gate에서 실제 MinerU parsing, DB integration, 복구/보안/e2e를 검증한다. mock과 live 결과를 구분한다.
14. 위 단계가 완료된 뒤 GUI를 마지막 별도 작업으로 시작한다. GUI는 같은 application services를 재사용하며 CLI release의 선행 조건이 아니다.

각 단계는 다음 단계로 넘어가기 전에 duplicate, rejection, provenance, immutable-history test를 통과해야 한다.

---

## 결론

Palimpsest의 핵심은 많은 텍스트를 저장하는 것이 아니다.

```text
원본 D를 보존하고,
의미 있는 I를 검색 가능하게 만들고,
I가 교체되면 과거 근거를 보존한 채 연관 K를 재검증하고,
I와 기존 K를 반복 분석해 검증된 KGraph를 성장시키며,
Query와 Context에 맞춰 설명·추천·결정을 만들고,
확정된 결정을 다시 KGraph의 장기 기억으로 편입하고,
모든 결과가 어떤 입력과 판단에서 나왔는지 재현하는 것
```

이 구조에서 창의성은 K2K의 새로운 조합에서 나오고, 신뢰성은 Generator–Validator 분리, source-specific Information, Record/effect 원장, exact provenance, scoped fingerprint suppression, material-delta 검증, revision concurrency guard, edge applicability revalidation, root-independent derivation-depth 추적과 scope별 의무를 보존하는 convergent propagation에서 나온다.
