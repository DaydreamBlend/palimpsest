# D/I/K/W의 현재 구조와 구현 범위

2026-09-11 최신 명확화: [I2K는 서로 다른 D의 I 1개 이상을 근거로 K 하나를 만들 수 있다](../decisions/MULTI_SOURCE_I2K.md). 한 I가 여러 K에 사용될 수도 있다. source별 전체 검토와 후보별 실제 근거를 구분하고 각 I의 원본 위치를 보존한다. 현재 실행 구현은 단일 Data에 제한돼 있어 이 계약의 runtime 확장은 후속이다.

2026-09-11 최신 제품 방향: [LLM Wiki의 D/I/K 계층 검색](../decisions/LLM_WIKI_RETRIEVAL.md). LLM이 예상 활용도를 판단해 미리 K를 만들고, 드문 내용은 I embedding 검색, 그 뒤에는 D 원본 확인을 사용한다. [I2K의 근거 공백](../decisions/I2K_DIRECT_SOURCE_EVIDENCE.md) 때문에 D2I를 다시 수행하지 않는다. 직접 D grounding과 검색·답변 runtime은 미구현이다.

K에는 I2K로 정리한 지식뿐 아니라 K2K가 기존 K에서 귀납·연역한 지식도 축적한다. 파생 K는 전제의 정확 Revision과 추론·검증 기록을 거쳐 I/D까지 역추적한다. I에는 새로운 추론 결과를 저장하지 않는다. 이 K2K 생성/전파 runtime은 후속 T07이며 현재 I2K/N2E 실험과 구분한다.

2026-09-11 Markdown 추가: [Markdown D2I](MARKDOWN_RUNTIME.md)는 원본 UTF-8 bytes를 D로 등록하고 heading 그룹 I를 저장한다. 실제 시험 문서는24개 I가 되었으며 그룹 수는 문서 구조에 따른다. 위치는 PDF page/bbox 대신 text_range의 원문byte/char/line이며 기존 PDF I/FP와 구분한다. 아래 Markdown미구현 설명은 이 source 변환·저장 범위에서 대체됐다.

2026-09-11 최신 저장 변경: [스크립트 그룹 I 저장](GROUPED_INFORMATION.md)을 적용한다. 새 canonical I는 절의 본문과 media를 함께 담는 그룹 단위이며, 세부 block은 각 I의 source payload/grounding과 문자 범위에 보존한다. 과거의 작은 I/ID/hash는 그대로 유지한다. 아래229 I·입력-only 묶음 설명은 당시 측정/구조이며 새 기본 저장 단위는 이 변경을 따른다.

작성일: 2026-09-10, 현재 상태 갱신: 2026-09-11. 사용자 설명용 현재 구조 안내다. **D 등록, source I 저장·조회, 전체 I의 LLM 선택, I2K/N2E와 KNode/KEdge Revision의 PostgreSQL 저장은 구현·실험되어 있다.** [실행 안내](FULL_SOURCE_SELECTION.md)를 기준으로 하며 K2K/K2W/W2K·검색/답변 runtime과 전체 task 완료는 구분한다.

후속으로 [I2K 입력 그룹·검색 정책](I2K_CONTEXT_POLICY.md)을 기록했다. 작은 원문 I들을 Abstract/Introduction·Results 소절/Figure·Markdown heading에 맞는 입력으로 묶으며 semantic embedding은 immutable I와 연결된 별도 profile index로 다룬다. [Test_Paper I229개 길이·입력 시안](../../output/t03-information-context/REPORT.md)은 실제 원문 기준의 측정이며 embedding/I2K 실행은 아니다.

기준은 [사용자 승인](../decisions/USER_OVERRIDES.md), [원문 보존 D2I](../decisions/D2I_SOURCE_PRESERVATION.md), [저장·ID 계약](../decisions/STORAGE_IDENTITY.md), [PDF 이미지 방식 기본값](../decisions/MINERU_IMAGE_DEFAULT.md), [최신 I 우선·필요 시 원본 PDF 제공](../decisions/I2K_I_FIRST_SOURCE_ON_DEMAND.md)이다. 최신 입력 계약이 이전의 원본 페이지 이미지 상시 동반 계약에 우선하며, 이전 parser 결과, I, ID, hash와 semantic 실험 이력은 보존한다.

| 계층 | 저장하는 것 | 종류 | 구현 범위 |
|---|---|---|---|
| D — Data | 등록한 원본 bytes와 수집 provenance | PDF, text/Markdown, 웹 snapshot, 이미지 등 MIME으로 구분 | 관리 등록·중복 거부·hash 검증·PG metadata 저장 구현 |
| I — Information | D를 읽을 수 있게 만든 원문 표현과 정확한 위치 | text, image, figure, table, equation | PDF source I 저장·grounding·페이지/문단/이미지 조회 구현 |
| K — Knowledge | 사전 생성한 지식 Node와 의미 관계 Edge | 현재 구현은 Proposition/Observation 및 supports | I2K/N2E·Node/Edge Revision·I grounding·검증/atomic 저장 구현. 전체 kind registry·K2K는 후속 |
| W — Wisdom | 특정 질문·상황·지식 snapshot의 설명·추천·결정 | explanation, recommendation, decision | 의미 계약 확정 범위 존재. K2W/W2K runtime과 W migration은 후속 작업 |

Data의 개념적 형식 범위와 실제 D2I parser 지원 범위는 다르다. 현재 구현·실험의 중심은 PDF이며 다른 모든 형식의 parser가 구현됐다는 뜻은 아니다.

**D: 원본 파일은 Artifact Store, metadata는 PostgreSQL에 저장한다.**

실제 `canonical_store.data` 필드는 다음과 같다. [구현 migration](../../src/palimpsest/migrations/0001_data.sql)을 기준으로 한다.

| 필드 | 실제 표현·의미 |
|---|---|
| `data_id` | `text` PK. 실제 원본 bytes 전체의 SHA-256, 소문자 hex 64자리 |
| `sha256` | `data_id`와 같은 generated 값 |
| `media_type`, `byte_size` | MIME type과 원본 byte 수 |
| `artifact_path` | `objects/sha256/<앞 2자리>/<hash>`의 관리 경로 |
| `original_name`, `created_at` | 선택적 원래 파일명과 등록 시각 |

`data_acquisitions`는 UUIDv7 `acquisition_id`, `data_id`, `origin_uri`, `import_method`, `retrieved_at`, `original_name`, `external_metadata`, `actor_ref`, `created_at`으로 수집 provenance를 보존한다. 사용자는 Palimpsest 도구로 등록하며 사용자 원본을 이동·삭제하지 않는다.

같은 bytes를 새 request로 등록하면 중복을 거부한다. 같은 성공 request의 retry는 기존 결과를 재생한다. 파일명이 달라도 bytes가 같으면 같은 D이고, 같은 논문이라도 bytes가 다르면 다른 D다. 의미적으로 같은 논문인지까지 자동 기각하는 기능은 아니다. D는 불변이며 원본이 바뀌면 새 D를 등록한다. 별도 Data Revision은 없다.

**I: 의미를 채택하기 전의 원문 표현이다.**

현재 source I의 schema는 `source-information-v1`이며 `semantic_type=null`이다. `kind`는 저장상의 큰 분류이고 `unit_type`은 원문 표현의 구체 종류다.

| `unit_type` | `kind` | 내용 |
|---|---|---|
| `text` | `text` | 본문·제목·caption·header/footer·참고문헌 등의 parser text |
| `image` | `image` | 이미지 artifact가 있는 원문 block. 개별 panel도 포함 가능 |
| `figure` | `image` | 명시적으로 확인한 inventory에 따라 전체 Figure와 member/caption 근거를 묶은 단위 |
| `table` | `text` | table HTML/text 등 구조 표현과 관련 원문 artifact refs |
| `equation` | `text` | parser의 수식 text/LaTeX 등 원문 표현 |

따라서 Image I 개수와 논문의 main Figure 개수는 같지 않을 수 있다. 전체 Figure·panel·caption·page image의 역할과 연결을 따로 보존해야 한다. 원문을 정보 가치로 버리지 않으며 빈 text를 가진 image block도 보존할 수 있다. [원문 단위 조립 코드](../../src/palimpsest/source_units.py)

실제 `canonical_store.information`은 `information_id uuid`, `data_id`, `origin_record_id`, `kind`, `unit_type`, `semantic_type`, `title`, `content`, `payload jsonb`, `identity_fingerprint`, `content_fingerprint`, `created_at`을 저장한다. `information_id`는 UUIDv7이다. [기반 migration](../../src/palimpsest/migrations/0002_information.sql)과 [source I 추가 migration](../../src/palimpsest/migrations/0003_source_information.sql)이 실제 구조다.

`payload`에는 `validation_basis=source_structure`, `semantic_checked=false`, `source_blocks`, `source_bundle_sha256`, `parse_manifest_sha256`, image/source artifact refs와 빈 content 여부를 보존한다. `information_groundings`는 exact `information_id`, `data_id`, `parse_artifact_id`, `block_id`, `page_index`, `bbox`, `page_size`, `raw_locator`, `anchor_sha256`를 연결한다. `page_index`는 0부터 시작하며 사용자에게 표시하는 물리 페이지 번호와 구분한다. [실제 payload·grounding 저장](../../src/palimpsest/compiler_runtime.py)

과거 `information-v1`의 `proposition/observation/procedure/definition/figure` semantic 분류는 이전 실험 이력이다. 현재 source I를 이 종류로 분류하지 않고, 과거 row를 새 profile로 재작성하지 않는다. 현재 I의 의미 해석은 I2K부터 수행한다.

I 자체가 immutable snapshot이므로 `InformationRevision`은 없다. 원문 content·grounding 교정은 새 I와 명시적 supersession/invalidation 관계로 표현하는 설계이며, 교정 lifecycle runtime은 [T05](../../tasks/T05.md) 후속 범위다. 페이지 묶음, 문단 연결, chunk·overlap, embedding·표시 변경은 exact I/source range를 가리키는 조회 projection이므로 I를 재작성하지 않는다. [I 의미 계약](../canonical/02_information.md)

**PDF D2I는 이미지 기반 MinerU와 스크립트 청킹을 사용한다. I2K는 I를 먼저 읽고 원문이 필요하면 원본 PDF를 추가로 받는다.**

새 PDF 처리의 기본 정책은 원본 PDF를 200 DPI 이미지로 렌더링하고, 그 이미지 기반 입력을 MinerU Hybrid + Pro2605 1.2B high로 OCR·layout parsing하는 것이다. 정확한 버전·profile과 실행 검증 상태는 [최신 승인 문서](../decisions/MINERU_IMAGE_DEFAULT.md)를 따른다. 이전 native/dual 처리 결과를 새 기본값으로 덮어쓰지 않는다.

```text
불변 PDF D
→ 원본 페이지 이미지 + 렌더링/좌표 변환 manifest
→ MinerU 이미지 기반 OCR·layout raw 결과
→ script 정규화·source-unit 조립·구조/위치/hash/coverage 검사
→ source I + exact grounding + 영속 D2IRecord
→ script 기반 절·문단·전체 문서 읽기 projection
```

MinerU 내부에는 추출용 소형 VLM이 관여할 수 있다. D2I의 원문 조립·청킹·구조 검사는 application LLM 없이 스크립트로 수행한다. 결정적 재현 범위는 보존한 parser raw와 고정된 profile에 대한 정규화·조립이며, 모든 parser 재실행이 bit-for-bit 동일하거나 OCR이 정확하다는 보장은 아니다. 원문 heading·읽기 순서·명시적 Figure 참조를 우선하고 모호한 경계는 exact 원문 범위와 함께 남긴다. 구조적 acceptance와 원문 충실성 검토를 구분하고 불일치·불확실성은 근거와 함께 남긴다.

PDF-derived I의 최초 I2K 입력은 **선택한 I의 content/media와 exact provenance**다. Text I뿐 아니라 Image I 자체의 이미지·Figure/panel content도 포함하므로 I 우선은 text-only를 뜻하지 않는다. 문단·절이 걸치면 관련 I와 앞뒤 context를 연결하며, 전체 논문 I를 한 번에 읽을지 나눌지는 실제 입력 한도와 source coverage에 따라 정한다. 원본 PDF와 전체 원본 페이지 companion을 기본으로 동봉하지 않는다.

I2K에서 수치·기호·Figure 소속·누락 의심 등의 이유로 원문이 필요하다고 판단하면, 같은 Data에 등록된 **원본 PDF bytes**를 추가 제공한다. 원본 요청 이유, Data/I refs·hash, 실제 제공 여부와 사용한 page/region·인용을 남긴다. PDF를 확보하거나 읽지 못하면 영향 받는 K 후보를 미해결 상태로 유지한다. 원본에서 새 근거를 읽어도 과거 I를 자동 수정하지 않으며, 저장된 원본·raster·근거 조회는 그대로 보존한다.

아래는 입력에 필요한 정보를 보여주는 **개념 예시**이며 확정 JSON schema가 아니다.

```text
I2K input projection
- exact information_ids + source_bundle/profile hash
- I text/structure/media + block/raw locators
- original data_id + page index + bbox + coordinate mapping
- Image I artifact refs + hashes
- 필요한 paragraph/section context와 Figure/panel refs
- extraction discrepancy/uncertainty flags
- 원본 필요 시: 등록된 original PDF bytes/hash + 요청 이유·실제 제공·사용 범위
```

[페이지 조회](../../src/palimpsest/page_projection.py)는 I ID와 block text range를 연결하고, [PDF evidence context](../../src/palimpsest/paragraph_projection.py)와 [전체 문서·절 조회](SECTION_CONTEXT.md)는 보존된 원본 page image·panel·Figure·문단 근거를 제공한다. 이러한 available evidence descriptor와 실제 모델에 전달한 입력은 구분한다. **I text/media를 제공하는 실제 I2K runtime은 구현됐으나 원본 PDF bytes의 provider 전달과 직접 D grounding은 미구현이다.** 원본에서 새로운 근거를 사용하더라도 해당 D/page/region을 정확히 인용해야 하며 과거 I content를 조용히 고쳐 쓰지 않는다.

**K: Node와 Edge의 의미를 구조화하고 Revision으로 이력을 보존한다.**

확정된 KNode 종류는 다음 여섯 가지다. [K 의미 계약](../canonical/03_knowledge_graph.md)과 [Operation별 허용 종류](../canonical/04_compiler_records.md)를 따른다.

| KNode kind | 의미 | 생성 경로 |
|---|---|---|
| `proposition` | 검증·반박·한정 가능한 주장 | I2K, K2K |
| `observation` | 자료가 보고하는 관찰·측정 결과 | I2K |
| `procedure` | 실행 가능한 절차 | I2K, K2K |
| `question` | 해결되지 않았거나 추적할 질문 | I2K, K2K |
| `entity` | 사람·개념·조직·물질·프로젝트 등 식별 대상 | I2K, K2K |
| `decision` | 특정 actor의 결정 사건 | I2K의 `reported`, W2K의 `authority_confirmed` |

Logical Node는 `knode_id`, `kind`, `current_revision_id`를 갖고, immutable Revision은 `knode_revision_id`, `knode_id`, `semantic_payload`, 읽기 표현, identity/content FP, 이전 Revision ref, origin Record를 보존하는 설계다. 예를 들어 proposition payload의 `subject/relation/object/polarity/scope/conditions`는 구조화 방식의 예시이며, 여섯 kind 전체의 상세 registry가 이미 구현·동결된 것은 아니다.

KEdge의 최소 predicate family는 `supports`, `contradicts`, `qualifies`, `composes`, `supersedes`다. Logical Edge는 `kedge_id`, 통제된 `predicate`, 출발·도착 logical Node IDs, current Revision ref를 갖는다. EdgeRevision에는 당시의 exact endpoint Revision IDs, `qualifiers`, `semantic_payload`, FP와 origin Record가 남는다. 전체 predicate registry와 endpoint-kind matrix는 아직 후속 설계 범위다.

문체·paraphrase·같은 의미의 근거 추가는 새 K semantic Revision의 사유가 아니다. 같은 identity에서 조건·범위·극성·시간 등 의미가 실질적으로 달라질 때만 새 Revision 후보가 된다. 기존 의미에 새 근거가 생기면 grounding/support를 추가한다. 과거 Revision과 최초 provenance는 수정하지 않는다. [Materiality 계약](../canonical/05_identity_materiality.md)

Node의 current Revision이 바뀌어도 과거 Edge endpoint를 덮어쓰지 않는다. 관계 의미가 같다면 새 EdgeRevision 대신 새 endpoint pair에 대한 applicability event를 추가하는 설계다. 반박은 먼저 `contradicts` 관계로 남기며 상대 Node를 자동 수정하지 않는다. KGraph는 이러한 usable Node/Edge·Revision·applicability에서 재구성하는 graph projection이며 하나의 mutable 문서 blob이 아니다.

**W: 질문에 대한 답변·추천과 실제 결정을 구분한다.**

| Wisdom kind | 역할 | 권위와 W2K |
|---|---|---|
| `explanation` | 설명·답변·과거 결정 이유 설명 | LLM synthesis. 자동 W2K 없음 |
| `recommendation` | 선택지·기준·지지/반대 근거를 비교한 추천 | LLM advisory output. 자동 W2K 없음 |
| `decision` | 실제 선택·보류·거부 사건 | 권한 있는 actor의 확인 필요. deterministic W2K 수행 |

W 공통 구조는 `wisdom_id`, `wisdom_kind`, `query`, `context_snapshot`, 실제 사용한 exact K Revision/EffectiveEdge/I refs, retrieval snapshot, `evidence_mode`, `retrieval_strategy`, `epistemic_basis`, `answer_or_payload`, citations, uncertainty, generation profile과 생성 시각이다. 특정 질문·시점·입력에 종속된 immutable snapshot이며 `WisdomRevision`은 없다. 직접 I를 사용한 답변은 accepted K만 사용한 답변과 근거 종류를 구분한다. [W 의미 계약](../canonical/08_wisdom_decisions.md)

Decision action은 `select/defer/decline`이다. Decision에는 `subject/scope/constraints/effective_at`, 선택 또는 보류 내용, 실제 이유, `decided_by`, payload에 결속된 `confirmation_ref`, 결정 시각과 명시적 supersedes ref가 필요하다. LLM이 확인 증거를 만들 수 없으며, 문서가 보고하는 decision KNode는 사용자의 실제 commitment와 다르다.

확인된 Decision W의 W2K는 LLM 없이 decision KNode와 명시된 supersedes 효과를 만든다. 같은 성공 결정 사건의 retry는 같은 W/K를 재생하지만, 실제 재결정은 새 사건이다. 같은 내용의 별도 결정 사건을 content FP로 병합하지 않는다. 준비한 결정 상태가 바뀐 늦은 요청은 새 W/K를 저장하지 않고 현재 상태를 보여준 뒤 재확인한다.

**각 변환의 책임과 공통 보존 규칙**

| 변환 | 입력 → 결과 | 경계 |
|---|---|---|
| D2I | exact D → source I 집합 | 원문 표현 보존·구조 검사. 애플리케이션 의미 LLM 없음 |
| I2K | exact I 집합·관련 원문 context → KNode 후보 | 의미 해석 시작. Edge를 직접 생성하지 않음 |
| N2E | accepted Node Revision들 → KEdge 후보·관계 재검증 | Node 생성과 분리 |
| K2K | accepted Node/Edge subgraph → KNode·의미 Revision 후보 | 추론만으로 새로운 observation이나 사용자 확정 decision 생성 금지 |
| K2W | accepted KGraph + Query + Context → Explanation/Recommendation W | 당시 사용한 입력·citation·불확실성 보존 |
| W2K | authority-confirmed Decision W → decision KNode와 명시적 supersedes | LLM 없는 결정적·원자적 반영 |

이 변환들은 [분리된 모듈 책임](MODULE_BOUNDARIES.md)을 따르며, 공통 execution·Record·commit 기반을 공유한다. [I2K/N2E/K2K 계약](../canonical/06_knowledge_operations.md)을 현재 실행 완료와 혼동하지 않는다.

- Provenance는 `W의 citation → exact K Revision/직접 I → origin Record·exact input I → D2IRecord·parse artifact·원본 D/page/region`으로 추적할 수 있어야 한다. 새 입력으로 재검증해도 과거 입력 ref를 현재 것으로 치환하지 않는다.
- Data만 원본 SHA-256 ID이고 나머지 신규 opaque 객체·Revision·Record ID는 UUIDv7이다. FP는 ID와 다르며 versioned content/identity/context 비교에 사용한다. Source I의 동일성은 exact Data와 grounding에 종속되고 cross-Data로 병합하지 않는다.
- K의 LLM은 구조화된 후보를 제안한다. ID·FP·dedupe/reuse·typed refs·권한·read-set freshness·atomic commit은 애플리케이션 책임이다. JSON schema 통과만으로 의미적 진실이나 완전한 결정론을 주장하지 않는다.
- 후보와 잠정 결과는 Compiler Runtime에서 준비하고 검증된 snapshot/effect를 Canonical Store에 반영한다. Terminal Record는 반영 후에도 Runtime에 영속 보존한다. 기술 실패를 내용 기각으로 처리하지 않으며, 기각 이력은 승인된 exact scoped FP 정책으로 조회한다.

현재 실행 migration은 [0001 Data](../../src/palimpsest/migrations/0001_data.sql), [0002 Information/Runtime](../../src/palimpsest/migrations/0002_information.sql), [0003 source I](../../src/palimpsest/migrations/0003_source_information.sql)다. [D/I/K/W 저장 스키마 v1](../schema/DIKW_STORAGE_SCHEMA_V1.md)의 K/W 테이블은 물리 구현 예정안이며, 그 문서의 U11 이전 semantic I 표는 최신 source I의 실행 schema를 대체하지 않는다. KNode 상세 registry·전체 Edge predicate/endpoint matrix·public K revalidation subtype·후속 model/profile 등 미정 사항은 [승인 register](../decisions/DECISION_REGISTER.md)와 각 task에서 구체화한다. 이 문서가 P 제안 전체를 승인하거나 [T04](../../tasks/T04.md)부터 [T09](../../tasks/T09.md)까지 완료 처리하지 않는다.
