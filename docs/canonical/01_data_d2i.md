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

## 5. D2I — 원본 표현을 Information으로 보존

### 5.1 목적과 단계 경계

U11에 따라 D2I는 PDF처럼 읽기 어려운 D를 읽기 쉬운 구조로 변환한다. 원문의 내용을 임의로 요약·해석하거나 정보 가치에 따라 선택하지 않는다. Palimpsest의 LLM 의미 해석은 I2K부터 적용한다.

```text
exact immutable D + pinned parser/normalization profile
→ local MinerU raw artifacts + normalized source blocks
→ deterministic source-unit assembly
→ schema / Data / page / region / hash / complete block-coverage checks
→ immutable source Information + grounding + durable D2IRecord
```

MinerU OCR/layout/model inference는 parser의 추출 과정이다. D2I의 application Generator/Validator LLM을 호출하는 경로가 아니며, 같은 bytes의 parser 실행이 모든 backend에서 bit-for-bit 같다는 보장도 아니다. exact artifacts와 처리 profile에 대한 결정적 normalization/assembly 결과를 재현한다. PDF 원본 bytes는 D에 그대로 남는다.

### 5.2 Logical compilation과 retry

D2I exactly-once의 범위는 `data_id + extraction_profile_family + compilation_generation`이다. logical compilation, 실행 attempt와 source unit을 구분한다. 별도 D2IRun/D2IOutput domain은 만들지 않는다.

일반 retry는 같은 generation과 고정된 input/profile을 사용하며 성공한 canonical 효과를 재생한다. 명시적 recompile/repair만 새 generation을 시작한다. parser/package/backend/model/config/adapter 또는 source-unit schema·assembly·검사 version 변화는 profile identity에 반영한다. 기존 parse artifacts나 canonical I를 덮어쓰지 않는다.

새 처리 profile은 `source-d2i-v1`, 새 Information profile은 `source-information-v1`이다. 새 D2I에는 semantic model/prompt profile이 필요하지 않다. 버전별 구체 physical schema는 additive migration이 소유하고 기존 schema/ID/hash/Record는 재작성하지 않는다.

### 5.3 원문 단위와 전체 coverage

Text/Image 및 필요한 Table/Equation 같은 source `unit_type`을 사용한다. 원문 block의 type, 추출 text/구조, reading order, parent/child, raw locator와 image artifact hash를 보존한다. 새 source I의 `semantic_type`은 null이다. Text에 proposition/observation 같은 의미 분류를 강제하지 않는다.

header/footer/page number/reference text도 원문 단위에 포함한다. Figure 전체와 panel/caption/continuation을 보존하며, 제공 PDF의 Figure 6개 모두를 대조한다. caption이 다른 페이지에 있으면 page별 exact refs로 연결하고 좌표나 관계를 추정하지 않는다. 검토된 full-figure crop을 보완할 때 exact D·parser output·inventory hash와 raw block coverage에 결합하며 기존 blocks를 삭제하지 않는다.

모든 요청 page와 모든 normalized source block이 unit coverage map에 포함되어야 한다. 하나의 unit이 여러 source block을 묶거나 여러 unit이 caption 근거를 공유할 수 있으므로 block 수와 I 수의 단순 일치를 요구하지 않는다. 누락된 block, invalid/unknown ref, 잘못된 geometry 또는 손상 artifact는 기술적 실패이며 전체 성공으로 표시하지 않는다. unsupported 원문 type도 조용히 제외하지 않는다.

canonical source units와 모델 context chunk는 다르다. context·embedding·retrieval을 위한 chunk/overlap/선택은 exact I/source ranges를 가진 versioned projection으로 만든다. 모델 또는 context 길이가 바뀌어도 I를 다시 작성하지 않는다.

### 5.4 D2IRecord와 구조 검사

D2IRecord는 source-unit 처리 한 건의 input/output fingerprint, 고정된 profile, exact source refs, 검사 결과와 canonical 효과를 영속 보존한다. `batch_id`는 하나의 결정적 처리에서 나온 Record를 묶는 값이며 LLM 호출의 존재를 뜻하지 않는다. 최소 의미 계약은 다음과 같다.

| 항목 | 보존할 의미 |
|---|---|
| Record / execution / batch / generation | 신규 opaque ID는 UUIDv7, retry와 처리 묶음 및 logical compilation을 구분 |
| Data / source-unit refs | exact Data와 page별 source block·raw artifact locator 및 anchor |
| processing profile | exact parser/profile·schema·assembly·검사 version, `source-d2i-v1` |
| fingerprints / manifest hashes | frozen source input·정규화 content·grounding·검사 scope에 결합한 digest |
| structural outcome / execution status | 기술적 검사·처리 상태이며 의미의 참·거짓 판정과 구분 |
| canonical refs / effects / timestamps | 실제 commit된 source I와 grounding/provenance 및 처리 시각 |

`accepted_new`는 구조·무결성·전체 coverage 검사를 통과하고 원문 I가 commit되었다는 뜻이다. `reused`는 같은 Data/locus/source content의 적격 exact 결과를 재사용한다는 뜻이다. 어떤 경우도 세계의 진실이나 사람의 semantic-fidelity 승인을 뜻하지 않는다. 새 source D2I에서 가치 판단에 따른 epistemic `rejected`를 생성하지 않는다. 기존 semantic D2I의 accepted/rejected/suppressed와 model receipt는 해당 과거 profile의 immutable history다.

parser confidence/추출 불확실성은 flags와 provenance로 남긴다. hash가 맞아도 OCR/text/읽기 순서가 원문과 완전히 같다고 단정하지 않는다. 명백한 구조 누락은 flags만 붙이고 완료하지 않는다. partial/zero-output/failure/blocked는 전체 성공이 아니다. 실패한 실행은 원문 내용의 기각이 아니며 retry에 필요한 미완료 상태와 임시 후보를 보존한다.

### 5.5 저장과 교정

전체 대상의 검증된 I·grounding·provenance, Runtime terminal Record, 필요한 temporary candidate cleanup과 outbox를 하나의 승인된 PostgreSQL commit 경계에서 반영한다. parse/파일 작업은 장기 DB transaction 안에 넣지 않고 immutable manifest/hash로 commit에 결합한다. 응답 유실·동시 요청에서도 unique constraint 또는 동등한 atomic guard로 중복 효과를 막는다.

source candidate는 commit 전 비canonical 작업물이며 완료 뒤에도 영속 Record는 Compiler Runtime에 남는다. 교정 또는 split/merge replacement set은 전부 검증한 뒤 같은 commit에서 활성화하며 부분 replacement를 기본 검색에 섞지 않는다. 기존 I와 과거 K provenance를 수정하지 않는다.

U11 이전 semantic I를 source I로 재분류하거나 자동 supersede하지 않는다. 명시적인 repair/supersession은 §6의 append-only 관계와 current support revalidation을 사용한다. D와 committed grounding을 복원하는 parser artifacts는 임시 candidate cleanup과 분리하여 보존한다.

### 5.6 PDF parser 경계

PDF D2I는 local MinerU adapter를 사용한다. raw parser JSON/Markdown/images는 profile/hash를 가진 비canonical artifacts이고, 그 위에서 검증된 source-unit snapshot이 canonical I가 된다. MinerU 실패를 다른 parser 또는 LLM의 조용한 대체 성공으로 감추지 않는다. 문서 외부 전송은 별도 승인 범위를 따른다.

[MINERU_ADAPTER](../interfaces/MINERU_ADAPTER.md)와 [U11](../decisions/D2I_SOURCE_PRESERVATION.md)의 original page index/size, coordinate space, crop/rotation, exact regions와 raw locators를 지킨다. 실제 parent/descendant bbox의 포락영역은 `explicit_region_envelope`로 표시하고 원래 `upstream_bbox`와 `grounding_regions`를 별도 보존한다.

---

