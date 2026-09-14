## 6. I — Information

### 6.1 정의

Information은 exact D의 내용과 위치를 최대한 보존하는 불변 원문 표현 단위다. U11의 `source-information-v1`은 Text/Image 및 필요한 Table/Equation 같은 source type을 사용한다. 독립적인 의미나 검색 가치가 있다는 판단을 편입 조건으로 요구하지 않는다. header/footer/reference text와 figure의 panel/caption/continuation도 보존 대상이다.

D2I는 application LLM 없이 parser 추출 표현을 정규화·조립하고 schema/grounding/hash/전체 source-block coverage를 검사한다. 이 구조적 acceptance는 내용의 진실성·의미 해석·사람의 원문 충실성 승인과 다르다. PDF bytes의 완전한 원본은 D에 남으며 I에는 parser 오류 가능성과 해당 flags를 보존한다. 명백한 구조 누락은 기술적 실패로 처리한다.

### 6.2 불변 Information

아래는 의미 계약이며 설치된 SQL schema의 변경 완료를 뜻하지 않는다. 새 source profile은 additive migration으로 표현하고 기존 semantic v1 I/Record는 과거 profile 그대로 보존한다.

| 필드/참조 | 설명 |
|---|---|
| `information_id` | 구조·무결성 검사를 거쳐 commit된 immutable I의 opaque UUIDv7 |
| `data_id` | 직접 근거인 불변 Data의 원본 bytes SHA-256 |
| `schema/profile` | `source-information-v1`과 해당 source assembly/schema version |
| `unit_type` | Text/Image 및 필요한 Table/Equation 같은 source 표현의 종류 |
| `semantic_type` | 새 source Information에서는 null. 의미 분류는 I2K 이후의 책임 |
| `source content` | parser extracted text/구조와 image refs. 임의 요약·해석·문체 변경으로 대체하지 않음 |
| `source block refs / coverage` | 해당 I가 보존하는 exact blocks, parent/child/caption/continuation과 순서 |
| `locator/grounding` | original page index/size/coordinate convention, page별 regions, raw artifact locator, parser profile/version과 stable anchor |
| `identity_fingerprint` | 같은 D와 evidence locus의 source-unit identity projection. cross-Data semantic merge 금지 |
| `content_fingerprint` | versioned source content·구조·grounding의 exact canonical digest. semantic 동등성 판정이 아님 |
| `flags / provenance` | 추출 불확실성, exact input/output/manifest hashes, processing profile·origin Record |
| `created_at` | canonical commit 시각이며 사람의 의미 승인 시각이 아님 |

Information 자체가 immutable snapshot이며 `InformationRevision` wrapper를 두지 않는다. embedding/reranker/model/context chunk/display projection/telemetry의 변경은 canonical I identity를 바꾸지 않는다. 긴 문서용 chunk와 overlap은 I/source ranges로 역추적되는 versioned projection이며 원문 단위의 편입 범위를 제한하지 않는다.

원문 내용·구조·grounding의 오류를 교정하거나 명시적으로 재추출한 결과가 기존 I와 실질적으로 다르면 새 Information을 만들고 명시적 replacement 관계를 기록한다. 서로 다른 Data의 같은 text도 독립 provenance를 위해 별도 I로 남는다. 의미 합의·중복 통합과 지식 채택은 I2K/K compilation에서 수행한다.

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
3. source unit_type과 parser 원문 type
4. lexical similarity
5. vector similarity
6. 다양성 또는 중복 제거 정책

같은 D의 모든 I를 무조건 LLM context에 넣지 않는다. 문서가 클 경우 비용과 잡음이 커지므로 top-K와 context budget을 적용한다.

### 6.5 Information RAG

기본 검색 corpus는 구조·무결성 검증된 usable Information의 검색 projection이다. source I 전체 보존과 retrieval 선택을 구분하며, header/footer 등을 검색에서 제외해도 canonical I는 삭제하지 않는다. superseded/invalidated I는 일반 검색에서 제외하고 history/replay에서만 명시적으로 요청할 수 있다.

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

