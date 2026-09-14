# Decision register

**2026-09-14 최신 전파 정정:** [반복 관찰·의미 변화 기준](MATERIALITY_FIRST_PROPAGATION.md). 신규 run에서 반복만으로 자동 보류하지 않고, 독립 nonmaterial 판정으로 새 의미 branch를 멈춘다. 근거 maintenance·accepted 비교 기준·불확실성·완료 fence는 유지하며 수렴 보장이나 Contradict predicate 구현으로 확대하지 않는다.

**2026-09-13 최신 승인:** [사용자가 요청한 별도 D2K](USER_REQUESTED_D2K.md). D2I 실패/오류 시 사용자에게 먼저 보고하며 사용자가 특정 원본/범위를 선택한 독립 작업만 허용한다. I2K 자동 D우회는 여전히 금지다. 구현 및 K개정/영향처리 후속은[T15계획](../../progress/T15_explicit_d2k_execplan.md)에실제결과를기록한다.

**2026-09-13 최신 I2K 경계:** [I-only와 D2I 오류 보고](I2K_INFORMATION_ERRORS.md). 사용자는 direct-D canonical grounding을 규약에 없는 D2K로 거부하고, I2K가 I 부족을 발견하면 사용자에게 D2I 오류를 알려야 한다고 정정했다. 이전 direct-source 예외는 철회됐고 개발 초안도 DB 적용 전에 중단·복원했다. 기존 I 근거·K2K 전제·불변 이력과 오류/선택 누락의 구분을 유지한다.

**2026-09-13 후속 착수:** 사용자가 권고한 구현 순서의 진행을 요청했다. [코드 D2I·검토 재개·Wiki 연결](../interfaces/CODE_REVIEW_WIKI.md)의 Python native parser 착수는 이전 parser-deferred 범위보다 최신이다. production D2I에 application LLM이 없어야 한다는 사용자 재확인과 기존 MinerU 내부 모델 예외를 유지한다. 준비된 승인 코드 V1의 Wiki 생성·독립 검증·재검토 전송은 사용자의 별도 명시 승인으로 진행한다. 실제 결과는 [실행 계획](../../progress/T13_code_review_wiki_execplan.md)에 기록하며 이후 roadmap 전체 승인을 완료 처리하지 않는다.

**2026-09-13 자료 버전·공유 저장 승인:** 사용자는 [불변 D·자료 이력·공유 blob 권고](../implementation/DATA_VERSION_STORAGE_PROPOSAL.md)를 승인하고 코드 변경 후 K2K까지 exact Revision provenance를 확인하도록 요청했다. [구현 계약](../interfaces/DATA_VERSIONS.md)의 additive 0013은 data_series/data_versions와 current/pinned compilation 문맥을 추가한다. 기존 raw D/I/KRevision과 migration은 보존한다. 후속 확인에서 코드 V1·V2의 기존 OAuth Terra Medium I2K 생성·독립 검증·재검토와 N2E/K2K 생성·독립 검증 전송도 각각 명시 승인했다. 적용 결과와 과거 자동 승인 검토 거절은 [실행 계획](../../progress/T07_versioned_code_execplan.md)에 보존한다. 코드 parser·검색/crawler·전체 scheduler 변경 승인이 아니다.

**2026-09-13 코드 데이터셋 선택:** 사용자는 현재 코드베이스를 K2K용 D로 선택한 뒤 “일단 현재는 그렇게 진행하고, 나중에 코드 전용 D2I parser도 만들자”라고 명시했다. [원문 코드 dossier](../interfaces/CODEBASE_SNAPSHOT.md)는 임시 표현으로 승인됐으며 raw code file을 Markdown으로 위장하지 않는다. [첫 K2K 실행 단위](../interfaces/K2K_RUNTIME.md)는 기존 추론/원문 경계와 exact provenance 결정을 구현한다. 전체 scheduler, 원래 source DB의 미승인 migration, 실제 provider 전송·semantic 평가가 모두 완료됐다는 뜻은 아니다.

**2026-09-13 범용 검토 지시:** 사용자는 Figure subpanel의 K 표현 부족을 지적한 뒤 특정 논문에 과적합하지 않고 모든 D/I/K에 적용하도록 명시했다. [공통 source review 계약](../interfaces/SOURCE_REVIEW.md)은 원문 주소 열거와 LLM 의미 항목·중요성 판단, 독립 검토와 exact KRevision 연결을 구현한다. 패널 수만큼 신규 K를 강제하거나 I를 다시 쪼개는 승인으로 해석하지 않는다. 기존 원문·Record·재사용·K2K 경계와 live migration 승인 상태를 유지한다.

**2026-09-13 Electron 구현 지시:** 사용자는 Electron 비용을 고려한 뒤 직접 구현하도록 명시했다. [첫 GUI 착수](ELECTRON_UI_START.md)가 이전 GUI-last 순서에 이 수직 구현 범위에서 우선한다. 기존 Python 서비스를 통한 읽기·원문·이력 UI와 실제 Windows package를 구현했으며 T12 완료·canonical 쓰기·모델 호출·공개 배포를 승인한 것으로 확대하지 않는다. [실행 결과](../../output/t09-electron/REPORT.md).

**2026-09-13 Electron 조사 요청:** 사용자는 Electron 직접 UI의 적합성 조사를 요청했다. [후속 판단](../implementation/ELECTRON_UI_ASSESSMENT.md)은 주 작업 앱의 전용 UI와 읽기/게시 UI를 구분한다. 이는 선택 권고이며 Electron 채택·GUI 착수·Python backend 재작성·T13 gate 해제의 승인 기록이 아니다.

**2026-09-12 사용자 후속:** 직전 제안한 Wiki/K→I→D 질의 흐름을 구현하면서 기존 Wiki UI 재사용을 동시에 조사하도록 요청했다. [현재 질의 계약](../interfaces/WIKI_QUERY.md)과 [UI 권고](../implementation/WIKI_UI_INTEGRATION.md)를 연결한다. UI 후보 조사는 제품 선택·GUI 착수·인터넷 게시 승인으로 해석하지 않는다. 기존 공개 논문·Terra OAuth·BGE 기본값과 별도 실험 DB 범위에서 검증했으며 canonical K/W/P 생성과 구분한다.

**2026-09-12 Wiki 후속 진행:** 사용자의 계속 진행 요청에 따라 [Wiki DB projection과 K 탐색](../interfaces/WIKI_DATABASE.md)을 구현했다. 기존 paper/topic snapshot·인용·검토 이력을 별도 PostgreSQL schema에 저장하고 exact source evidence로 관련 KRevision을 조회한다. canonical P의 W 입력 요구를 수정하거나 source의 live migration을 승인한 것으로 해석하지 않는다. 실험 DB 적용 및 실제 복원은 [결과](../../output/t06-wiki-postgres/REPORT.md)에서 확인한다.

**2026-09-12 Wiki 착수:** [논문별 페이지·주제 문서 구현 범위](PAPER_WIKI_PROJECTION.md). 기존 전체 I를 읽는 비canonical Wiki projection, 고정 renderer, 출처별 주제 집계와 snapshot 이력을 구현한다. 정식 P 입력과 canonical DB migration의 별도 승인 상태는 유지하며 실제 결과는 [실행 계획](../../progress/T05_paper_wiki_execplan.md)에서 구분한다.

**2026-09-11 구현 상태 연결:** [다중 Data Runtime](../implementation/MULTI_SOURCE_RUNTIME.md)의 코드·격리 PG 검사와 두 추가 논문 실제 I2K/N2E 실험을 수행했다. [결과](../../output/t04-multi-source/REPORT.md)는 신규 K 11개·동일 Revision 재사용 9개·Edge 1개와 의미 품질 미통과를 구분한다. 기존 보존 DB의 0007 설치는 자동 승인 검토 거절 후 사용자 승인 대기다. 이 상태는 사용자 요구의 승인 자체나 P01–P12 전체 승인과 구분한다.

**2026-09-11 최신 정정:** [I2K 원문 정리·K2K만 새 결론 생성](I2K_SOURCE_ONLY_K2K_INFERENCE.md). I2K는 원문에 명시된 내용만 정리·통합하고 새로운 결론·추측은 만들지 않는다. 신규 I2K-origin Revision은 `is_inferred=false`다. 사용자가 요청한 다중 Data 구현·실제 실험은 [실행 계획](../../progress/T04_multi_source_runtime_execplan.md)에서 별도로 확인한다.

**2026-09-11 다중 입력 승인:** [다중 Data의 I를 함께 쓰는 I2K](MULTI_SOURCE_I2K.md). 후보 단위는 I 1개 이상 → K 하나이며 I는 서로 다른 D에서 올 수 있다. 각 출처/근거를 유지하고 별개 실험을 병합하지 않는다. 전체 I 검토는 처리 의무, 후보별 evidence는 실제 지식 근거로 구분한다. 다중 출처를 사용해도 새 추론은 I2K의 허용 효과가 아니다.

**2026-09-11 제품 방향 후속 승인:** [LLM Wiki 계층 검색](LLM_WIKI_RETRIEVAL.md). 자주 쓸 것으로 판단한 K의 사전 생성·조회, 드문 정보의 I embedding 검색, 부족할 때 D 원본 조회를 순서대로 적용한다. K 미선택은 I 삭제나 D2I 재실행 사유가 아니다. 검색·답변 runtime의 실제 구현 상태는 별도로 기록한다.

후속 명확화: K2K는 귀납·연역으로 새 K를 생성하며 I는 원문 표현으로 유지한다. K2K의 정확 전제 Revision·추론 유형/가정/한계·검증 및 transitive I/D 근거를 보존한다. 새로운 Observation이나 실제 Decision을 추론으로 만들어내지 않는 기존 경계와 semantic Revision 규칙은 유지한다.

추가 승인: 추론으로 생성된 K는 그 사실을 필수 metadata로 보존·노출한다. 새 K2K 추론 Revision의 실제 생성 Record, 추론 유형, 전제 refs/검증을 연결하고 나중에 원문 근거가 추가되어도 최초 기원을 지우지 않는다. 신규 I2K origin의 `is_inferred`는 false이며, 저자가 보고한 추론을 시스템의 새 추론으로 분류하지 않는다. 실제 물리 schema와 runtime은 해당 구현 결과로 확인한다.

**2026-09-11 최신 후속 승인:** [I2K 근거 공백 시 D2I 재실행 금지와 직접 D 근거](I2K_DIRECT_SOURCE_EVIDENCE.md). 등록 원본을 확인한 K와 source 누락/불일치 이력을 연결하며, 기존 I를 자동 보완하지 않는다. 이전 I-first의 D2I 보완 요구에 우선한다. P01–P12의 범위 밖 항목을 일괄 승인하지 않으며 구현 완료와 구분한다.

**2026-09-11 최신 후속 승인:** [D↔I 대응·전체 I의 LLM 선택·출처별 K 보존](FULL_SOURCE_LLM_SELECTION.md). 기존 principal-claims 실험에 이 전체 입력/선택/scope 규칙을 추가하며 과거 이력을 재작성하지 않는다.

**2026-09-11 최신 저장 후속 승인:** [스크립트 그룹 I의 영속 저장](GROUPED_INFORMATION_STORAGE.md). 사용자는 수백 개 block I 대신 스크립트로 묶은 I를 저장하도록 지시했다. 새 `source-groups-v1` 조립은 기존 source schema에 원문·이미지·정확한 provenance를 유지하고, 기존 I/UUID/hash/receipt/raw는 보존한다. 완료 source의 재조립은 부모 실행/profile/parse hash를 명시한 새 실행이다. 이 저장 단위 범위에서 이전 projection-only 문구보다 우선하며 I-first 정책과 MinerU 선택, 범위 밖 U/P 상태는 유지한다. 실물 저장·회귀 검증은 별도 실행 기록으로 확인한다.

**2026-09-11 최신 입력 후속 승인:** [스크립트 청킹·I 우선·원본 PDF 추가 조회](I2K_I_FIRST_SOURCE_ON_DEMAND.md). I2K 최초 입력은 I 자체의 content/provenance이고, 원문 확인이 필요할 때 등록된 동일 Data의 PDF를 제공한다. 이전의 원본 페이지 이미지 필수 동시 첨부만 대체하며 MinerU image200 선택·I immutability·이전 P/U 상태는 유지한다. 실제 I2K 전송/원본 요청 runtime는 T04 미구현 범위다.

2026-09-10 가장 최근 parser 후속 승인: [MinerU Hybrid + Pro 및 PDF 근거 보완](MINERU_HYBRID_SELECTION.md). 앞선 Paddle 선택 후 사용자가 비교 결과에 따라 새 MinerU 조합과 원문/projection 분리를 선택했다. P 제안 일괄 승인이나 전체 품질 통과는 아니다.

> 상태: 모든 P01–P12는 PROPOSED. 사용자에게 검토와 파일 분리를 요청받았다는 사실은 보완 설계의 일괄 승인이 아닙니다.

## 권위와 변경

원본의 A1–A40은 baseline으로 보존합니다. P 항목은 별도 제안 ID이며 A41 등으로 자동 승격하지 않습니다. 실제 사용자가 승인한 항목만 decisions.json의 status를 accepted로 바꾸고 approval_ref와 선택된 상세 내용을 기록합니다. 거부/보류 항목은 rejected/deferred로 표시하며 관련 task만 blocked로 유지합니다. 참조 위치를 만들었다는 이유만으로 승인 증거가 생기지 않습니다.

accepted된 addendum만 그 항목에서 원본보다 우선합니다. 미승인 contract와 원본이 충돌하면 Codex가 취향대로 선택하지 않고 해당 변경을 보류합니다. 비영향 작업은 계속할 수 있습니다. docs/source와 baseline_parts는 byte-identical 원본으로 보존합니다. current canonical 변경은 승인된 범위에서 full/slices/current_map을 동기화해 새 snapshot으로 발행합니다.

2026-09-10 parser 후속 승인: 사용자가 그림 인식·분리 기능이 있으면 1번 후보로 진행하도록 지시했고, 공식 crop·image export 지원을 확인했다. 새 선택은 [PaddleOCR-VL-1.6 로컬 전체 파이프라인](PADDLEOCR_SELECTION.md)이며 이전 MinerU 제품 지정과 충돌하는 범위에 우선한다. U01–U11의 기존 JSON/canonical snapshot과 P01–P12의 status는 재작성하지 않고 날짜가 명시된 승인 부록으로 연결한다. parser 내부 VLM 추출은 허용하지만 application의 의미 생성은 I2K부터이며, 실제 품질·앱 연결·T03 완료는 별도 검증이다.

## 제안 항목

후속 실행 profile 선택(2026-09-10): 사용자의 “그럼 Q4를 쓰도록 하자”에 따라 optional heading projection은 [Qwen3.5-4B Q4_0 / thinking2048](../implementation/HEADING_MODEL_PROFILE.md)을 기본으로 사용한다. U11 경계나 아래 P 제안들의 승인 상태를 변경하는 선택은 아니다.

### P01 — Identity/FP/materiality registry

상태: proposed. 연결 finding: F02, F09, F10, F16.

kind별 identity projection, rejection key scope, materiality 판정 필드와 domain-specific duplicate 순서. 수치 tolerance 값은 별도 평가.

명세: [01_identity_materiality.md](../contracts/01_identity_materiality.md).

### P02 — Effective edge와 dependency contract

상태: proposed. 연결 finding: F03, F04, F05, F06.

EffectiveEdgeRef, 최신 negative 우선, pending/unknown, 실제 endpoint 소비 의존성. semantic EdgeRevision 없는 rebasing 유지.

명세: [02_effective_relations_dependencies.md](../contracts/02_effective_relations_dependencies.md).

### P03 — Propagation completion receipt

상태: proposed. 연결 finding: F01.

의무 dependency revalidation과 discovery 구분, watermark/coverage/미완료 obligation 기준 quiescence. hard propagation cap 없음.

명세: [03_propagation_completion.md](../contracts/03_propagation_completion.md).

### P04 — 현재 support와 material evidence state

상태: proposed. 연결 finding: F07, F08.

creation provenance와 current support receipt 분리. no-material 재검증 후에도 새 support/dependency 보존.

명세: [05_compiler_validation_evidence.md](../contracts/05_compiler_validation_evidence.md).

### P05 — Atomic commit/retry/publication barrier

상태: proposed. 연결 finding: F11, F12, F13.

read-set freshness, execution/proposal 분리, outbox/lease/fan-in, replacement-set publication, commit ordering.

명세: [04_transactions_execution.md](../contracts/04_transactions_execution.md).

### P06 — Operation/effect/subtype registry

상태: proposed. 연결 finding: F14, F15.

정보 기반 K revalidation public subtype 이름, effect-only 승인 표현, N2E predicate 변경 처리, DAG 범위. 정확한 이름은 승인 과정에서 선택.

명세: [08_interfaces_schema_plan.md](../contracts/08_interfaces_schema_plan.md).

### P07 — Evidence independence와 생성물 lineage

상태: proposed. 연결 finding: F17, F24.

source work/study/derived origin metadata, leaf support dedup, P/B 재수입의 authority/독립 근거 세탁 방지.

명세: [08_interfaces_schema_plan.md](../contracts/08_interfaces_schema_plan.md).

### P08 — Decision command와 Wisdom retrieval 축

상태: proposed. 연결 finding: F18, F19, F20.

confirmation-event idempotency, payload binding, action mapping, temporal supersession, reported trace, evidence mode/strategy 분리.

명세: [06_decision_wisdom_publication.md](../contracts/06_decision_wisdom_publication.md).

### P09 — Read snapshot/projection/replay

상태: proposed. 연결 finding: F21.

effective state projection key, authoritative filtering, index watermark, historical read receipt와 재실행 한계.

명세: [07_storage_retrieval_security.md](../contracts/07_storage_retrieval_security.md).

### P10 — Storage/security/operational controls

상태: proposed. 연결 finding: F22, F23.

file/DB publish/reconciliation, trust boundary, secret/privacy/backup, 명시적 pause/resume/cancel과 partial 상태.

명세: [07_storage_retrieval_security.md](../contracts/07_storage_retrieval_security.md).

### P11 — 본문 편집 잔재 정정

상태: proposed. 연결 finding: F25.

충돌 문장을 승인된 규칙에 맞춰 정정. 원본 archive는 그대로 보존하고 승인 overlay에 정확한 replacement를 기록.

명세: [ERRATA.md](../review/ERRATA.md).

### P12 — 실제 repository 기반 구현 profile

상태: proposed. 연결 finding: F26.

기존 repo 언어/DB 도구/test commands를 조사한 후 stack 및 실행 profile 확정. 모델/embedding/provider/UI 임의 고정 금지.

명세: [ENVIRONMENT.md](../implementation/ENVIRONMENT.md).

## 승인 시 결정해야 할 항목

P06의 public revalidation subtype/effect disposition 이름과 P12의 stack/commands는 문서가 아직 답을 확정하지 않았습니다. “제안 방향 승인”만으로 null placeholder를 production schema에 넣지 않습니다. 기존 repo에 명확한 선택이 있으면 유지하는 안을 먼저 제시합니다. 새 유료 provider 연결, DB 파괴적 migration, root AGENTS 교체는 설계 승인과 별개인 실행 권한입니다.


## 이번에 적용된 사용자 변경 U01–U03

[USER_OVERRIDES](USER_OVERRIDES.md)와 `user_overrides.json`에 CLI-first/GUI-last, MinerU PDF parser, Artifact Store/Canonical Store/Compiler Runtime 명칭을 기록했다. 이 세 선택은 accepted다. 위 P01–P12의 proposed 상태는 유지한다.

따라서 P12에서는 CLI/GUI 우선순위나 PDF parser 제품을 다시 선택하지 않는다. 실제 언어·CLI library·MinerU 버전/backend·DB/test 실행 profile을 조사·확정한다. GUI framework 선택은 T13 이전에 하지 않는다. 기존 schema/path 변경은 U03의 이름 선택과 별개로 migration 실행 승인이 필요하다.

## 추가 사용자 변경 U04–U05

[USER_OVERRIDES](USER_OVERRIDES.md)에 추가 원문과 후속 답변을 기록했다. U04는 embedding `BAAI/bge-m3`(공식 dense dimension 1024)와 동일 모델의 multi-vector ColBERT 점수를 사용하는 재순위화다. 전용 cross-encoder reranker 모델은 선택하지 않았다. U05는 MinerU의 설치/명시적 업그레이드 시 최신 안정판 선택 및 실제 실행 profile의 exact version 기록이다.

P12 전체는 proposed를 유지한다. 위 두 항목은 실제 사용자 선택으로 우선하며, 언어/CLI/DB 도구/Generator·Validator 모델 및 나머지 P 계약은 미정이다. runtime 설치·모델 준비·실제 평가 결과와 선택 승인을 구분한다.

후속 사용자 요청으로 두 역할의 독립 교체 가능성도 U04에 포함했다. Qwen3-Embedding/Reranker 4B·8B는 향후 후보이며 실제 모델 활성화나 구현 완료가 아니다. [교체 경계](../interfaces/RETRIEVAL_PROFILE.md)를 따른다.

## 추가 사용자 변경 U06

[USER_OVERRIDES](USER_OVERRIDES.md)에 D/I/K/W/P/B 및 각 변환의 모듈화 승인을 기록했다. [MODULE_BOUNDARIES](../implementation/MODULE_BOUNDARIES.md)의 domain 6개·Compiler 변환 6개·publication 작업 2개와 공통 저장/실행 경계를 따른다. W2P/P2B의 모듈화는 신규 Compiler Record subtype 채택이 아니다. W2K 결정론성과 모듈 간 atomic commit은 기존 canonical대로 유지한다.

U06은 코드 책임 분리이며 P03/P05/P06의 미정 completion/effect/transaction 상세나 P12의 언어·toolchain을 일괄 승인하지 않는다.


## 추가 사용자 변경 U07

[USER_OVERRIDES](USER_OVERRIDES.md)의 U07은 현재 Operation/모듈 명칭을 K2W/k2w로 통일한다. KGraph + Query + Context → Wisdom 의미와 원본 인용·이력은 유지한다. P01–P12의 미정 세부 계약 상태는 바꾸지 않는다.


## U08 — 구조 수정의 부분 적용

[ARCHITECTURE_FIXES](ARCHITECTURE_FIXES.md)의 R01–R06/R09는 사용자 위임에 따라 기존 invariant를 지키는 구체 수정으로 적용했다. 각 P 항목의 관련 문장에 한해 우선하며 P01–P12의 status를 전체 accepted로 바꾸지 않는다. R07/R08은 후속 사용자 선택으로 늦은 결정 재확인·기각 exact scoped FP 조회를 적용했다. [해결 상태](architecture_fixes.json)에 실제 답변 근거를 보존한다. public K revalidation subtype, 나머지 effect registry/DDL/stack/runtime는 여전히 미정이다.

## U09 — DB·ID·등록·반영의 부분 확정

[STORAGE_IDENTITY](STORAGE_IDENTITY.md)의 PostgreSQL 초기 18/pgvector, Data raw SHA-256·기타 신규 opaque UUIDv7, 도구 등록·duplicate/retry와 검증된 효과의 atomic 반영·Runtime Record 보존을 적용한다. 관련 P01/P05/P10/P12의 충돌하는 범위만 우선하며 P 전체는 proposed로 유지한다. [T02 SQL 초안](../schema/T02_STORAGE_SCHEMA.md)은 DB 적용·통합 검증 전의 검토 산출물이다.

## U10 — Python/Docker 부분 확정

[사용자 변경](USER_OVERRIDES.md)에 따라 앱 언어 Python과 Docker 기반 실행·배포를 확정했다. P12의 언어·배포 선택에 우선하며 나머지 exact runtime/toolchain/driver/migration profile은 별도다. 일반 sandbox의 Docker 접근 실패와 승인 실행 경로의 서버 조회 성공은 [ENVIRONMENT](../implementation/ENVIRONMENT.md)에 구분해 기록한다.

## U11 — 원문 보존 D2I와 구조화된 후속 의미 처리

[사용자 원문과 적용 계약](D2I_SOURCE_PRESERVATION.md)에 따라 D2I는 local MinerU + script 기반의 결정적 source-unit 조립·구조 검사를 수행한다. 원문 text/구조·page/region·raw locator·hash·전체 block 및 Figure/panel/caption/continuation coverage를 보존하고 정보 가치로 원문을 선별하지 않는다. LLM 의미 해석은 I2K부터 적용하며 strict structured proposals와 exact provenance를 사용한다. ID/FP/중복·재사용/typed refs/read-set/atomic commit은 애플리케이션 책임이다. JSON 구조만으로 의미의 진실이나 완전한 결정론을 보장하지 않는다.

새 `source-information-v1`은 source `unit_type`과 `semantic_type=null`을 사용하며 `source-d2i-v1`에는 D2I semantic model/prompt profile이 없다. 기존 semantic I/Record/ID/hash와 설치 migration은 과거 이력으로 보존하고 새 schema는 additive migration으로 처리한다. 기존 P01/P05/P07/P12 등의 충돌 문장에 이 승인 범위만 우선하며 P01–P12 전체 status와 미정 public subtype은 유지한다. 구현·회귀·실물 coverage 통과 여부는 실행 기록에서 별도로 확인한다.


## 2026-09-10 후속 — MinerU 이중 전사

[사용자 승인](MINERU_DUAL_TRANSCRIPTION.md)은 원본 PDF auto + 200 DPI 이미지 OCR을 신규 기본으로 고정한다. 일반 문자 native, 그리스 문자·첨자·특수문자 OCR 우선의 국소 선택과 두 raw의 불변 보존을 적용한다. 기존 P/U 전체 상태와 과거 I/ID/hash는 바꾸지 않는다.

## 2026-09-10 최신 후속 — 이미지 OCR 기본값·PDF I2K 원본 이미지

[최신 사용자 승인](MINERU_IMAGE_DEFAULT.md)이 직전 dual 선택의 신규 기본 text 경로를 대체한다. `mineru-hybrid-image200-v1`은 같은 고정 MinerU/model로 이미지 OCR만 실행하고 원본·파생 페이지 좌표와 raster bytes를 보존한다. PDF I2K의 입력에는 파싱 I와 대응하는 원본 페이지/Figure 이미지를 함께 제공한다. T03 구현과 T04 입력 계약을 구분하며 과거 profile/I/IDs/hashes 및 P/U의 범위 밖 상태는 유지한다.

## 2026-09-10 후속 — I2K 입력 그룹·semantic/provenance 검색

사용자는 각 I의 길이 확인, Abstract/Introduction·Results Figure·Markdown heading별 입력과 semantic embedding/provenance에 따른 same-D 우선 관련 I 사용을 요청했다. [입력 정책](../implementation/I2K_CONTEXT_POLICY.md)은 원문 I를 유지한 조회 그룹과 profile별 파생 index로 이 선호를 적용한다. 실제 모델/tokenizer·가중치/top-K/index·kind registry를 새로 확정하지 않는다. [측정과 입력 시안](../../progress/T03_information_context_execplan.md)은 의미 모델·검색 runtime 실행 완료와 별개다.
