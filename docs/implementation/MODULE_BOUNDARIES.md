# 모듈 책임과 code ownership

2026-09-14 [K2W](../interfaces/K2W.md)는 `k2w`/`k2w_prompts`의 구조화 계약, `wisdom`의 불변 W, `wisdom_runtime`의 정확한 K 입력·생성·독립 검증·원자적 저장으로 나눈다. `parchment`/`parchment_runtime`은 [W2P](../interfaces/PARCHMENT.md)의 문서 구성을 맡는다. Wiki가 표시하는 문서는 P이며 K는 별도 조회한다. 기존 I 기반 Wiki 이력은 그대로 보존한다. Realm 등록 coordinator와 자동 실행 범위는 `realm_registration`/`realm_automation`이 담당하며 source/Realm DB의 복구 기록과 실행 당시 범위를 유지한다.

2026-09-13 [사용자 요청 D2K](../interfaces/D2K.md)는 `d2k.py` 원문 계약, `d2k_pdf.py` 고정 페이지 renderer, `d2k_runtime.py` 원문 준비·확인, `d2k_cli.py` 명시적 CLI로 나눈다. 기존 KnowledgeRuntime의 검증·원자적 commit을 재사용한다. [K 의미 개정](../interfaces/KNOWLEDGE_REVISION.md)은 `knowledge_revision.py`의 의미 비교 규칙과 `knowledge_revision_runtime.py`의 exact target·CAS·영향 열거를 공유한다. 새로운 I2K/K2K Record subtype이나 D2I LLM을 추가하지 않는다.

2026-09-13 [Electron UI](../interfaces/DESKTOP_UI.md)는 호스트 `desktop/`의 main/preload/renderer와 Docker의 `desktop_read.py`/`desktop_bridge.py` 읽기 adapter로 나눈다. 입력은 허용된 typed read operation뿐이며 원문·query 저장소와 DB를 읽기 전용으로 사용한다. canonical commit·model·D2I·K/W 정책은 UI에서 구현하거나 우회하지 않는다.

2026-09-12 [Wiki query 후속](../interfaces/WIKI_QUERY.md)은 `wiki_retrieval`의 source/PG index·검색, `bge_retrieval`의 local 모델 adapter, `wiki_query`의 schema/인용/검증, `wiki_query_runtime`의 단계·전달·이력으로 나눈다. embedding/검색 창·query 답변은 원문 I나 canonical K/W/P를 생성·수정하지 않는다. 외부 UI는 이 결과를 표시하는 연결 계층으로 조사했으며 의미 처리를 UI에 중복 구현하지 않는다.

2026-09-12 Wiki 후속은 [별도 비canonical 문서 projection 모듈](../interfaces/WIKI_DATABASE.md)로 구현한다. `wiki_archive`는 원래 JSON/source/receipt 검증, `wiki_knowledge_links`는 exact 원문 범위 기반 탐색, `wiki_database`는 PG import/current/복원을 담당한다. 기존 문서 생성/renderer와 단계별 K·W·P 의미 변환의 소유권은 유지하며, Wiki page snapshot을 K semantic Revision 또는 정식 P로 취급하지 않는다.

> U03의 구성요소명과 U06의 단계별 모듈화, U07의 K2W/k2w 명칭, U08의 [구조 수정](../decisions/ARCHITECTURE_FIXES.md), U09의 [저장 계약](../decisions/STORAGE_IDENTITY.md)을 적용한다. 아래는 단계별 논리 모듈/의존성 계약이다. T02/T03의 Data·source Information·Runtime·CLI는 Python/Docker로 구현됐고 PostgreSQL 18/pgvector를 사용한다. 이후 단계는 해당 task에서 구현한다.

## Artifact Store — artifact_store

D 원본 bytes의 stage/publish/read/verify/reconcile을 소유한다. 사용자가 제공한 원본을 도구 관리 영역으로 복사하고 보존 bytes의 SHA-256을 계산한다. 관리 폴더에 직접 놓인 파일을 자동 등록하거나 사용자 원본을 이동·삭제하지 않는다. 원본과 분리한 namespace에 참조되는 MinerU derived parse artifacts도 저장할 수 있다. parser 출력이 D나 I로 자동 승격되는 것은 아니다. 지식 승인/authority/ranking은 하지 않는다. Data metadata commit은 Canonical Store adapter와 협력한다.

## Canonical Store — canonical_store

D metadata, validated I, KNode/KEdge revisions, W/P/B, exact provenance와 accepted lifecycle/applicability/grounding을 보존한다. K만 담는 저장소가 아니므로 명칭을 Knowledge Store로 좁히지 않는다. canonical mutation은 명시적 transaction 함수로 제한하고 arbitrary overwrite를 허용하지 않는다.

## Compiler Runtime — compiler_runtime

D2I/I2K/N2E/K2K/K2W/W2K execution, proposal Records, TemporaryCandidate, MinerU parser orchestration, Generator–Validator, input snapshots, scheduler/outbox/telemetry를 소유한다. Data 등록의 durable request journal도 runtime 책임이다. 후보 본문·잠정 판정은 임시로 유지하고, 반영 후에도 terminal Record와 exact refs/판정/reason은 영속 보존한다. provider/parser가 직접 canonical commit을 수행하지 않는다.

## CLI adapter — 첫 사용자 interface

argument parsing, UTF-8 terminal output, JSON result, stderr log, exit status, interactive/noninteractive 확인 흐름을 담당한다. application services와 command/result contracts를 재사용한다. T02부터 각 기능을 CLI로 연결한다. CLI argument 객체나 stdout을 domain에 전달하지 않는다.

## MinerU parser adapter — PDF 전용 선택

PDF parser 제품은 최신 [MinerU Hybrid 후속 승인](../decisions/MINERU_HYBRID_SELECTION.md)을 따른다. U10에 따라 Palimpsest 앱은 Python/Docker이며 MinerU 실행환경을 별도 컨테이너로 격리한다. parser version/backend/config/output schema와 원문 anchor를 검증한다. non-PDF parser 선택은 별도다. [MinerU adapter](../interfaces/MINERU_ADAPTER.md)를 따른다.

T03의 native PDF text/visual 근거와 문단 조회는 `pdf_text_evidence`, `pdf_visual_evidence`, `paragraph_projection`에서 구현하며 `pdf_evidence`가 검증·읽기를 결합한다. 이 모듈들은 canonical commit이나 의미 판정을 소유하지 않는다. source refs와 profile에 연결한 재생성 가능한 조회 projection이며 [PDF_EVIDENCE](../interfaces/PDF_EVIDENCE.md)에 공개 읽기 경계를 기록한다.

## GUI adapter — 마지막, deferred

T12 CLI release 뒤 T13에서만 설계·구현한다. import/review/authority/compilation 로직을 GUI로 옮기거나 복제하지 않는다. 같은 application services를 재사용한다. GUI가 없다고 CLI release를 blocked로 표시하지 않는다.

## 실제 경로와 migration

신규 책임 식별자는 `artifact_store`, `canonical_store`, `compiler_runtime`이고 path field는 `artifact_path`다. 신규 SQL 예시는 `canonical_store.*` / `compiler_runtime.*`를 사용한다. 기존 경로/schema는 inventory→mapping→검증된 migration 뒤에 바꾸며 ID/hash/history는 유지한다. 자세한 legacy mapping은 [MIGRATION](MIGRATION.md)을 읽는다.

공통 registry/migration chain은 한 task가 소유한다. worktree마다 DB/artifact root를 격리한다. 별도 microservice/message broker/graph DB를 필수로 추가하지 않는다.

U09의 초기 저장은 같은 PostgreSQL 18 database의 canonical_store/compiler_runtime schema와 도구 관리 Artifact Store를 사용한다. 신규 data_id는 원본 SHA-256, 나머지 신규 opaque ID는 UUIDv7이다. 새 중복 등록은 거부하고 동일 성공 request retry는 기존 결과를 반환하는 구분을 등록 application service가 소유한다. [T02 SQL 초안](../schema/T02_STORAGE_SCHEMA.md)은 Data/acquisition/request만 다루며 미래 domain·embedding 테이블을 빈 scaffold로 생성하지 않는다.

## U06 — Domain 6개와 변환 모듈의 분리

하나의 애플리케이션 안에서 domain과 변환 작업의 코드 책임을 분리한다. D/I/K/W/P/B는 의미·불변조건의 경계이고, Artifact Store/Canonical Store/Compiler Runtime은 저장·실행 책임의 경계다. 두 분류를 같은 축으로 취급하거나 각 domain마다 별도 DB·worker·서비스를 만들지 않는다.

| Domain | 논리 모듈 | 소유하는 데이터와 규칙 | 맡기지 않을 책임 |
|---|---|---|---|
| D | `data` | immutable Data metadata, acquisition, 원본 식별·참조 | 원본 bytes I/O, PDF parsing |
| I | `information` | Data-specific immutable source I, 전체 block coverage·exact grounding, supersession/invalidation | MinerU 실행, 의미 선별·요약, 서로 다른 Data의 I 병합 |
| K | `knowledge` | KNode/KEdge, semantic revision/materiality, lifecycle/applicability 규칙 | 모델 호출, retrieval top-K에 의한 필수 dependency 제한 |
| W | `wisdom` | immutable W, explanation/recommendation/decision 구분, Decision payload·authority 규칙 | LLM 추천을 실제 결정으로 확정하는 행위 |
| P | `parchment` | immutable P, W 및 허용된 K/I 인용, 새 문서 supersession | 원본 W/K/I 수정, 강제 compiler Record 생성 |
| B | `book` | immutable B, exact P 참조와 순서·구조 | 포함된 P 수정, BookRevision 추가 |

`knowledge` 안에서 node/edge/revision 기능을 나눌 수 있으나 K는 하나의 domain 책임으로 유지한다. 각 논리 모듈은 작은 파일로 시작하고 필요한 크기가 되었을 때 패키지로 나눈다. 모든 객체에 service/repository/factory 계층을 반복 생성할 필요는 없다.

| 변환 모듈 | 입력 경계 | 결과와 소유할 동작 | 핵심 제한 |
|---|---|---|---|
| `d2i` | exact D와 parser/profile refs | 결정적 source-unit 조립, 전체 page/block coverage·구조/무결성 검사 | PDF는 local MinerU. application LLM 호출 0, 임의 요약·가치 선별 금지 |
| `i2k` | usable exact source I(1개 이상) | 구조화된 LLM 의미 해석 시작, KNode 제안 및 validation | I의 Data 출처 보존. reported decision을 authority-confirmed 사건으로 변경 금지 |
| `n2e` | accepted KNode revisions | KEdge 제안·관계 재검증·applicability 효과 | endpoint refs 덮어쓰기 금지. 관계 의미가 같으면 semantic revision 없음 |
| `k2k` | accepted/current-applicable K subgraph | KNode 제안·material effect 계산 | 추론으로 observation/사용자 commitment 생성 금지 |
| `k2w` | Query/Context snapshot, K 및 허용된 I | 임시 overlay와 Wisdom synthesis | 직접 I와 accepted K 구분. recommendation 자동 확정 금지 |
| `w2k` | 실제 authority-confirmed Decision W | decision K와 명시적 supersedes의 deterministic atomic effect | LLM 호출 0. 서로 다른 결정 사건을 내용으로 병합 금지 |
| `w2p` | exact W들 및 선택적 K/I 인용 | 독립 P 구성·편집 및 citation 보존 | publication application 모듈. 신규 compiler subtype/Record를 추가하지 않음 |
| `p2b` | 순서·구조를 가진 exact P들 | 독립 B 구성 및 참조 보존 | publication application 모듈. 신규 compiler subtype/Record를 추가하지 않음 |

변환 모듈은 입력 선택, prompt/schema/policy와 허용된 effect의 의미를 소유한다. 확정된 출력은 승인된 commit 이후의 canonical refs로 반환하며 proposal, disposition, 실제 effects, propagation impact, execution status를 하나의 success 값으로 합치지 않는다. 미승인 P06의 public subtype/effect enum은 이 모듈 이름에서 자동 생성하지 않는다.

I2K의 관련 K 조회는 identity/materiality/reuse 비교와 Validator context용 refs다. I2K의 직접 근거 입력인 exact I와 구분하며, 새로운 결론을 도출하는 작업은 accepted K를 전제로 하는 K2K가 담당한다. [다중 source I2K](../decisions/MULTI_SOURCE_I2K.md)에 따라 한 후보의 I들은 서로 다른 D에 속할 수 있지만 원문에 명시된 내용만 통합·정리한다. 개별 I/Data의 provenance를 유지하고 원문 I들을 새 의미 I로 병합하지 않는다. [최신 경계](../decisions/I2K_SOURCE_ONLY_K2K_INFERENCE.md)에 따라 신규 I2K-origin Revision은 `is_inferred=false`이며, 추론 flag를 붙이는 것으로 I2K의 새 결론을 허용하지 않는다.

## 구현할 코드 배치

아래 경로는 논리적인 배치 예시이며 해당 파일의 존재를 뜻하지 않는다. U10의 Python/Docker를 적용하며 실제 package/file 경로와 검증된 도구는 task별 inventory를 따른다. slash는 논리 grouping이다.

```text
domain/
  data, information, knowledge, wisdom, parchment, book
compiler_runtime/
  d2i, i2k, n2e, k2k, k2w, w2k
  execution, propagation
publication/
  w2p, p2b
artifact_store/
canonical_store/
adapters/
  mineru, embedding, reranking, generator, validator
cli/
```

`domain`은 순수 의미 규칙과 공개 값/참조 계약을 둔다. `compiler_runtime`과 `publication`은 application service를 구현한다. Data 등록·조회나 Decision confirmation처럼 단일 변환보다 넓은 use case는 얇은 application service에서 조합하며 domain에 I/O를 넣지 않는다. composition entrypoint에서 선택한 store/model adapter를 연결한다.

W2P/P2B는 canonical 흐름도에 있는 구성 작업이지만 기존 6개 Compiler Operation 및 KCompilationRecord subtype과 구분한다. 사람이 작성하거나 deterministic script/LLM을 조합할 수 있다는 P/B의 기존 성격을 유지한다. module path가 새로운 영속 domain/type을 뜻하지 않는다.

## 의존성과 공개 계약

1. CLI는 application service의 입력/결과만 변환한다. CLI parser/stdout/exit code가 domain/compiler 내부로 들어가지 않는다.
2. Domain은 DB driver, filesystem, MinerU, Embedding/Reranker 및 Generator/Validator 구현을 import하지 않는다. 서로 연결되는 정보는 exact ID/ref와 필요한 공개 snapshot 값으로 전달한다. 다른 domain 내부 객체 전체를 중첩하거나 private storage 함수를 호출하지 않는다.
3. 변환 모듈은 필요한 domain의 공개 계약과 공통 runtime 서비스를 조합한다. adapter를 직접 생성하거나 provider SDK를 직접 호출하지 않는다. 좁은 함수/프로토콜 경계의 실제 문법은 선택된 언어에 맞춘다.
4. 저장/model/parser adapter는 외부 포맷을 검증하고 application 계약으로 변환한다. adapter가 판단 권한을 얻거나 canonical commit을 임의로 수행하지 않는다.
5. 서로 다른 변환 모듈은 직접 재귀 호출하지 않는다. N2E/K2K의 후속 material 작업은 공통 propagation scheduler를 통해 진행한다. code import 순환을 막는 것과 semantic graph를 DAG로 제한하는 것은 다르다.
6. 공통 코드에는 실제 공유되는 refs, hashing, execution/Record, Candidate 수명, telemetry, scheduling/commit plumbing만 둔다. Operation별 authority·validation 정책을 범용 pipeline 옵션에 숨기지 않는다. execution/FP/Record/commit을 재사용하더라도 D2I의 source 구조 검사와 W2K의 authority-confirmed 효과는 LLM 없이 수행한다.

BGE-M3 및 향후 Qwen3 교체는 [검색 profile](../interfaces/RETRIEVAL_PROFILE.md)의 adapter 경계에서 처리한다. MinerU 버전 변경도 [PDF adapter](../interfaces/MINERU_ADAPTER.md)에 한정하며 I/K/W 의미 규칙을 모델 구현에 종속시키지 않는다.

## 모듈을 가로지르는 commit과 전파

모듈화 때문에 domain마다 독립 commit하지 않는다. 승인된 하나의 commit unit 안에서 여러 domain payload, Record, provenance, Candidate 처리와 outbox를 함께 저장할 수 있어야 한다. Canonical Store의 transaction 구현과 migration chain은 공통 소유자 한 명이 관리한다. 파싱/모델 호출 전체나 graph 수렴 전체를 하나의 장기 DB transaction으로 묶는 뜻이 아니다.

특히 confirmed Decision W, W2KRecord, decision KNode/첫 revision, 확인된 supersedes 관계/effect, provenance와 outbox는 canonical §20.3의 단일 transaction을 유지한다. `wisdom`을 먼저 저장한 뒤 `knowledge`를 별도 저장하는 방식으로 경계를 찢지 않는다. W2K의 권위 확인은 CLI 또는 application의 실제 actor/payload-bound evidence에서 오며 provider 출력이 대신하지 않는다.

Non-material 결과는 새 semantic branch를 만들지 않는다. 공통 propagation은 depth/크기/Record 수/token/cost로 성공 종료하지 않으며 pending/failed 의무를 보존한다. 이 요구는 각 변환 모듈에 서로 다른 반복/완료 규칙을 복제하지 않도록 한다. P03/P05의 미정 receipt/read-set/retry 세부값을 이번 모듈 설계로 확정하지 않는다.

## 테스트 소유권과 단계별 구현

| 단계 | 구현할 모듈 범위 | 해당 단계에서 실제 확인할 경계 |
|---|---|---|
| T02 | data, artifact_store/canonical_store 기초, CLI/application 연결 | 원본 등록·exact read·verify, domain과 I/O 분리 |
| T03 | information, d2i, MinerU adapter, 공통 execution | 원문 content·Figure/panel/caption/전체 block coverage, 구조 acceptance·grounding·실패·재시도 |
| T04–T05 | knowledge node/revision, i2k, I repair/support | materiality, immutable history, 승인된 commit. 미정 public revalidation subtype 유지 |
| T06–T07 | knowledge edge/applicability, n2e, k2k, propagation | effective refs, 후속 작업을 통한 전파, code import cycle 부재 |
| T08–T09 | wisdom, k2w, w2k, authority 연결 | retrieval profile 교체 경계, 실제 confirmation, deterministic W2K/atomicity |
| T10 | parchment, book, w2p, p2b | exact citations·구성·supersession, 새 compiler Record subtype 부재 |
| T11–T12 | CLI 통합·운영·release | 모듈 조합 e2e, 실제 DB/parser 복구·보안·semantic 평가 |

Domain별 순수 규칙 테스트, 변환별 입력/효과 및 fake-port 테스트, adapter별 실제 integration test를 분리한다. 실제 Python 모듈의 import/build 검사로 domain→adapter 역의존성과 module cycle을 검출한다. 문서의 모듈 목록이 맞다는 검사로 실제 코드 의존성을 검증했다고 보고하지 않는다.

이 문서는 모듈의 책임 계약이며 구현 현황은 task별 실행 기록을 따른다. 미정 계약을 확인하고 각 단계에서 필요한 모듈만 구현한다. 빈 future package/성공 stub/GUI는 생성하지 않는다.

U08에서 변환 모듈은 actual effect와 current support/dependency maintenance를 구분한다. Canonical Store는 input read-set을 commit까지 충돌 검출하며 propagation runtime은 scoped completion fence를 소유한다. 새 semantic branch 종료는 이미 남은 다른 의무를 삭제하지 않는다. R07의 scope/head freshness는 confirmation service와 atomic store가 함께 보호한다. R08은 accepted semantic similarity와 rejected exact scoped FP 조회를 분리한다. 미정 public revalidation subtype은 자동 결정하지 않는다.

U09의 반영 단위는 canonical effects/provenance/current support + Runtime terminal Record + candidate cleanup + outbox의 한 transaction이다. Runtime Record를 Canonical Store로 이동·삭제하지 않으며 compiler_runtime schema는 PostgreSQL TEMP/UNLOGGED 저장소가 아니다.

U10으로 실제 앱 언어는 Python, 실행·배포는 Docker로 확정됐다. 논리 모듈과 shared transaction 경계는 유지한다. 구체 Python package/import 검사, CLI/DB adapter 도구와 container profile은 실제 기능 slice에서 검증한다.

U11의 source I와 context projection을 구분한다. 원문 단위·page/region/raw locator·profile/hash·전체 coverage는 information/d2i가 보존하고, chunk/overlap/embedding/retrieval filter는 adapter 또는 입력 선택 projection이 exact I/source range에 결합해 만든다. model 교체로 canonical I를 재작성하지 않는다. I2K/N2E/K2K/K2W의 strict structured output은 후보 제약이며 semantic determinism의 증명이 아니다. canonical ID·FP·dedupe/reuse·typed refs·read-set·atomic commit은 공통 application/store 규칙이 통제한다. 새 의미 없는 K revision을 만들지 않는 materiality 및 exact provenance 규칙을 유지한다. [U11 상세](../decisions/D2I_SOURCE_PRESERVATION.md)를 따른다.


## T04 I2K 입력 준비

[여러 입력 형식의 설계](D2I_INPUT_FORMATS.md)는 수집/형식별 구조 파싱/그룹 조립/검증/atomic 저장을 구분한다. Artifact Store·Canonical Store·Compiler Runtime은 공유하고 실제 source 위치는 형식별로 보존한다. HTML/code 확장 때 Runtime/I2K의 PDF/Markdown 분기를 실제 기능과 함께 추출하며 빈 registry·미구현 adapter scaffolding을 먼저 추가하지 않는다.

[Markdown source 변환](MARKDOWN_RUNTIME.md)은 `markdown_adapter.py`가 원문 구조·그룹·text 범위를 소유한다. `d2i.py`는 format/algorithm별 변환 검사를 선택하고, Runtime/CLI가 기존 Data 등록·durable 실행·atomic I/grounding 저장을 재사용한다. `information._locus`는 Markdown에만 text_range를 추가해 PDF FP를 보존한다. `0004_text_groundings`는 실제 저장 위치의 타입과 parse bundle 일치를 검사한다. PDF 페이지 projection은 Markdown 입력을 명시적으로 거부한다.

최신 [그룹 I 저장](GROUPED_INFORMATION.md)은 `source_groups.py`가 소유한다. `section_projection.group_source_blocks`의 순수 원문 경계 규칙을 재사용하며 `d2i.py`가 frozen algorithm별 builder/checker를 선택한다. Compiler Runtime은 새 그룹 수만큼 I/Record/outbox를 atomic 반영하고 모든 block grounding을 보존한다. `regroup_source`는 parent 실행/profile/parse manifest를 명시해 frozen source를 재조립하며 CLI가 직접 저장 규칙을 구현하지 않는다. 기존 `source_units.py`와 SQL/schema·과거 profile은 보존한다.

T04의 후속 입력 경계는 [I2K 입력 준비](T04_INPUT.md)에 구현했다. `i2k.py`는 검증된 source bundle/canonical I로 허용된 최초 입력 필드와 원본 요청의 구조·snapshot 결속을 구성하는 순수 모듈이다. DB·파일·provider를 호출하지 않는다. `CompilerRuntime.prepare_input/prepare_source`가 완료된 단일 source 실행 조회·artifact/grounding 확인과 원본 bytes 준비를 소유하고, `ArtifactStore.read`가 동일 FD로 bytes와 hash를 검증한다. CLI는 인자/JSON 전달만 맡는다. 새 I2K durable Record·K domain/semantic commit은 후속 slice에서 실제 동작과 함께 추가한다.

## T03 페이지 조회 projection

`page_projection.py`는 source I와 frozen parser bundle을 페이지별 읽기 및 인접 context로 투영하는 순수 모듈이다. DB·모델 adapter를 import하지 않는다. `CompilerRuntime.page_view`는 선택한 완료 source 실행의 immutable 입력만 읽고 산출물 무결성을 확인하며, `cli.py`는 pages/context 인자를 전달한다. 새 I/Record나 I2K 효과는 만들지 않는다. 페이지 순서·문자 offset·원문 참조·단일 target 소유권은 [PAGE_CONTEXT](PAGE_CONTEXT.md)를 따른다.

## T04/T06 첫 K 저장 slice

[지식 Runtime](KNOWLEDGE_RUNTIME.md)은 knowledge/n2e의 순수 후보 검사, knowledge_prompts의 의미 정책, knowledge_runtime의 공통 실행·atomic 저장, codex_provider의 실제 모델 호출을 분리한다. 새 0005 스키마가 논리 K/immutable Revision/정확 endpoint/grounding/Record/outbox를 연결한다. 전체 K2K 전파나 일반 material revision workflow 완료는 후속 범위다.

## 전체 source 주소·LLM 선택 후속

[FULL_SOURCE_SELECTION](FULL_SOURCE_SELECTION.md)의 source_pages/source_reconstruction은 원문 페이지 I와 위치·복원 규칙을 담당합니다. i2k_selection은 전체 I·scope·참조 구조를 검사하고 selection_prompts는 LLM 선택 정책을 담당합니다. 중요성 판단은 스크립트에 두지 않습니다. CompilerRuntime/KnowledgeRuntime이 실제 I·K·Record·review·scope·outbox를 공통 PostgreSQL 실행 경계에 저장하며, CLI와 host OAuth worker는 이 서비스를 호출합니다.

2026-09-13 [범용 source review](../interfaces/SOURCE_REVIEW.md)는 `source_review.py`가 기존 I 주소의 manifest 및 의미 검토 구조를 순수 함수로 검사한다. `knowledge_requests.py`는 Runtime/요청 export가 공유하는 prompt/schema를 구성하고, `knowledge_runtime.py`는 기존 JSONB·atomic K commit으로 exact 검토 결과를 저장한다. 형식별 D2I adapter, 중요성 LLM, canonical 저장 역할을 혼합하지 않는다.

2026-09-13 [코드 snapshot](../interfaces/CODEBASE_SNAPSHOT.md)은 `code_snapshot.py`가 파일/manifest/위치 복원을 담당하고 기존 Markdown D2I로 연결한다. [K2K](../interfaces/K2K_RUNTIME.md)는 `k2k.py`가 순수 입력/후보/검증·prompt를, `knowledge_provenance.py`가 exact 도출 근거의 조회를, 기존 `KnowledgeRuntime`이 공통 atomic 실행·Record·저장을 담당한다. K2K가 I 생성이나 N2E의 semantic Edge 생성을 대신하지 않는다.

2026-09-13 [자료 버전](../interfaces/DATA_VERSIONS.md)은 `segmented_artifact_store.py`가 물리적인 공유 blob·manifest를, `data_versions.py`가 등록된 D 위의 버전 이력·CAS·요청 replay를 담당한다. `version_context.py`는 모델 입력의 version 정책, `version_provenance.py`는 K 최초 origin과 후속 support 문맥 및 별도 head projection을 담당한다. 기존 `DataService`가 관리 등록·복구를, `KnowledgeRuntime`이 exact 입력 검증·head 검사·atomic commit을 계속 소유한다. 파일 버전 비교/복원은 code_snapshot의 순수 bytes API를 호출하며 D2I를 다시 실행하지 않는다.
