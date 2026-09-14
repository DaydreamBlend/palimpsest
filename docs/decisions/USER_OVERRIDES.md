# 승인된 사용자 변경 — CLI / MinerU / 구성요소 명칭 / 검색 모델 / 모듈화

**2026-09-14 전파 정정:** 사용자는 반복 구조만으로 자동 중단하지 말고 의미 변화가 미미하면 전파를 멈추도록 요청했다. [의미 변화 우선 정책](MATERIALITY_FIRST_PROPAGATION.md)은 새 run의 반복을 advisory로 기록하며 기존 independent materiality/reuse와 provenance maintenance를 기준으로 처리한다. 과거 frozen policy·SQL·판정 이력은 보존한다.

**2026-09-13 가장 최신 승인 — 사용자 요청 독립 D2K:** 사용자는 D2I 실패 시 사용자 요청에 한해 LLM D2K를 허용하는 제안을 승인하고 후속 구현을 요청했다. [독립 예외 규약](USER_REQUESTED_D2K.md)을 따른다. 아래 I2K의 자동 원문 우회 금지는 유지하며, 명시적인 별도 d2k 작업·원본/범위/모델 확인·실제 전달/독립 검증만 추가한다. 특정 실제 자료의 새 전송을 추정하지 않는다.

**2026-09-13 최신 정정 — 직접 D2K 금지:** 사용자는 원문 D에서 직접 K를 만드는 예외를 규약에 없는 D2K로 명시적으로 거부했다. [I만 근거로 사용하고 D2I 오류를 보고](I2K_INFORMATION_ERRORS.md)하는 결정이 이전 직접 D grounding 허용보다 최신이다. I2K에서 I 부족/오류를 발견하면 사용자에게 알리고 관련 K를 보류한다. 원문 K 우회 생성·D2I 자동 재실행·I 변경은 금지하며 단순 K 선택 누락과 구분한다.

**2026-09-13 후속 구현·D2I 경계 재확인:** 사용자는 권고 순서에 따른 구현 진행과 함께 production D2I에 Terra 등 application LLM이 개입하지 않음을 재확인했다. Python native parser와 검토 재개·Wiki 읽기 연결은 [0.13 계약](../interfaces/CODE_REVIEW_WIKI.md)을 따른다. MinerU 내부 OCR/layout VLM은 기존 범위이고, 원문 청킹·보존 검증은 스크립트다. 개발 중 추출 평가와 production I 생성의 필수 의존성을 구분한다. 기존 승인 코드 V1의 준비된 28I Wiki 생성·독립 검증·재검토도 별도 명시 승인했다.

**2026-09-12 구현 착수:** 사용자가 이전 논문 묶음으로 논문별 Wiki와 BMDC 같은 별도 주제 문서의 구현을 요청했다. [착수 범위](PAPER_WIKI_PROJECTION.md), [CLI](../interfaces/PAPER_WIKI_PROJECTION.md)에 따라 기존 D/I를 읽는 비canonical 문서 projection을 먼저 구현한다. 아래 설계 당시의 미착수 상태보다 최신이며, 정식 P 입력/DB 변경·GUI·crawler 승인은 포함하지 않는다.

**2026-09-12 제품 목표 명확화:** 자료를 넣으면 자동 분류해 관련 내용을 일관된 백과사전형 페이지로 만들고 갱신하는 **자동 확장 Obsidian 스타일 Wiki**가 중심 목표다. 장기적으로 인터넷 자동 수집과 웹사이트를 제공하고 개인 생각·결정도 함께 정리한다. D/I/K는 그 결과의 규격·근거를 지키는 내부 구조이며 연구용 실험이나 ADR 기록만으로 목표를 좁히지 않는다. I의 원문 보존·semantic search, 원문 명시 I2K/새 추론 K2K, K 통합 비필수 원칙은 유지한다. [자동 Wiki 설계안](../../progress/AUTOMATIC_WIKI_DESIGN.md)의 page schema/편집/renderer/P 입력 확장은 제안이며 아직 구현·migration·공개 배포를 승인하거나 실행한 기록은 아니다. 최종 사이트 목표를 현재 GUI 착수 또는 주기 수집 job 생성 지시로 해석하지 않는다.

**2026-09-11 후속 명확화: K 통합은 필수가 아니다.** 사용자는 “꼭 K가 통합이 될 필요는 없어”라고 정정했다. 다중 D를 지원하더라도 K를 반드시 합치거나 공통 K 개수를 성공 기준으로 삼지 않는다. 기존의 검증된 동일 의미 reuse와 서로 다른 실험의 source identity 보존은 유지한다. 이전 실험의 multi-Data 근거 K 0개는 그 자체로 실패가 아니며, 원문 범위 오류·불충분한 인용·기존 오류 K의 재검토에 집중한다. [개선 설계안](../../progress/T04_I2K_reliability_proposal.md)의 검증 필드·구현 순서는 제안이며 아직 적용하지 않았다.

**2026-09-11 다중 Data 구현 상태:** [Runtime 안내](../implementation/MULTI_SOURCE_RUNTIME.md)의 새 profile/0007·코드/격리 PG 검증과 [실제 모델 결과](../../output/t04-multi-source/REPORT.md)를 확인한다. 두 추가 논문에서 새 K 11개와 같은 의미 재사용을 확인했지만 실제 multi-Data 근거 K·기존 오류 K 재검토·의미 완전성은 미충족이다. 기존 보존 DB의 schema 적용 승인 대기와 source 준비 오류 이력을 구현 상태와 구분해 기록한다.

**2026-09-11 최신 정정과 실행 요청:** [I2K는 원문 정리, 새 결론은 K2K](I2K_SOURCE_ONLY_K2K_INFERENCE.md)를 적용한다. I2K의 원문에 없는 결론·추측은 금지하며 신규 I2K-origin Revision은 `is_inferred=false`다. 여러 D의 I를 사용하는 구현·실제 실험이 요청됐고 [실행 계획](../../progress/T04_multi_source_runtime_execplan.md)에 결과를 기록한다. 문서 변경을 구현 완료로 보고하지 않는다.

**2026-09-11 I2K 입력 명확화:** [서로 다른 D의 I 1개 이상 → K 하나](MULTI_SOURCE_I2K.md)를 허용한다. 후보별 exact I 근거는 다중 출처일 수 있으며 I의 원문 소유권과 실험별 K의 구분은 유지한다. 전체 문서 검토와 관련 I 조회를 구분한다. 원문에 명시된 내용의 통합·동일 의미 재사용은 I2K이며 새로운 추론 결론은 K2K다. 기존 단일 Data 구현을 다중 출처 지원 완료로 해석하지 않는다.

**2026-09-11 제품 관점 명확화:** [LLM Wiki의 D/I/K 계층 검색](LLM_WIKI_RETRIEVAL.md)을 따른다. LLM이 미리 선택한 K를 우선 조회하고, 드문 내용은 보존된 I embedding 검색, 그 뒤에는 원본 D 확인으로 내려간다. I 직접 답변과 canonical K 승인은 구분하며 provenance·Revision 보존을 유지한다.

동일 후속 지시는 K2K가 귀납·연역으로 새로운 지식을 만들 수 있는 K 계층을 명시한다. I는 D2I의 원문 표현이며 추론 결과를 저장하지 않는다. 파생 K는 정확한 전제 KRevision·도출/검증 기록·transitive I/D 근거를 유지한다. 현재 I 기반 K 저장 실험과 K2K 미구현 상태를 구분한다.

추론 생성 여부는 필수로 저장·표시한다. 새 I2K-origin Revision은 `is_inferred=false`이며 K2K가 새로 도출한 Revision은 `true`다. 실제 생성 Record와 허용된 경계를 검증하고 K2K의 귀납/연역 유형·accepted K 전제·검증을 보존한다. 원문 근거 추가나 재사용 작업으로 기존 Revision의 최초 기원을 덮어쓰지 않는다. 원문 저자가 보고한 추론은 시스템이 새로 도출한 것이 아니다.

**2026-09-11 최신 근거 공백 지시:** [I2K의 D2I 재실행 금지·직접 D 근거와 오류 이력](I2K_DIRECT_SOURCE_EVIDENCE.md)을 적용한다. I에서 근거를 확보하지 못하면 등록 원본 D를 검증하고 직접 근거로 기록하며, D2I를 재호출하거나 기존 I를 고쳐 근거를 만들지 않는다. 이전 D2I 보완 지침에 이 범위에서 우선한다. 실제 원본 전달·직접 grounding 구현 상태와 정책 승인은 구별한다.

**2026-09-11 최신 후속:** [양방향 원문 대응과 전체 I의 LLM 선택](FULL_SOURCE_LLM_SELECTION.md)을 적용한다. D↔I의 구간 주소와 원본 복원을 보존하고, 전체 I를 LLM이 검토해 중요성을 선택한다. 일반 명제의 의미 중복은 K 재사용, 서로 다른 D의 실험 결과 등 source-specific K는 보존한다.

**2026-09-11 최신 저장 단위 후속:** [스크립트 그룹 I의 영속 저장](GROUPED_INFORMATION_STORAGE.md)을 적용한다. 새 source 실행은 절 본문과 별도 page furniture 그룹을 I로 저장하며, 작은 block은 payload/grounding/raw에 보존하고 별도 I 행으로 복제하지 않는다. `source-information-v1` schema와 모든 원문·이미지·provenance를 유지하며 새 알고리즘은 `source-groups-v1`이다. 기존 I/ID/hash/receipt를 재작성하지 않고 재조립은 부모 실행/profile/parse hash에 결속한 새 실행으로 기록한다. 이전 “조회 그룹만 변경한다”는 제한은 새 저장 단위 범위에서 대체되며 MinerU·LLM 없는 조립·I 우선 원본 추가 조회와 범위 밖 승인 상태는 유지한다.

**2026-09-11 최신 후속:** [D2I 스크립트 청킹·I2K I 우선·필요 시 원본 PDF](I2K_I_FIRST_SOURCE_ON_DEMAND.md)를 적용한다. 별도 청킹 LLM을 사용하지 않고, 최초 I2K는 Text/Image I 등 I 자체의 content와 provenance를 받는다. 원본 PDF/전체 페이지 이미지는 자동 동봉하지 않으며 필요 판단 후 같은 Data의 원본 PDF를 제공한다. 아래 이전 동시 이미지 입력 계약의 해당 부분보다 우선한다. image200 MinerU 내부 OCR/layout 모델과 원문·역사 보존은 유지한다.

2026-09-10 I2K 입력 후속 선호: [절·Figure/Markdown heading 입력과 semantic/provenance 검색](../implementation/I2K_CONTEXT_POLICY.md)에 기록했다. Abstract와 Introduction은 각각 하나의 논리적 그룹으로, Results는 소절·관련 Figure를 연결해 읽는다. 원문 I를 보존하며 profile별 embedding과 same-D 문맥 우선/corpus 검색을 결합한다. 이번 작업은 길이 측정·입력 시안·계약 구체화이며 모델/index·K runtime 완료나 P 전체 승인이 아니다.

2026-09-10 최신 후속: [MinerU 이미지 OCR 기본값과 PDF I2K 멀티모달 입력](MINERU_IMAGE_DEFAULT.md)을 적용한다. 새 기본은 원본 PDF를 200 DPI 이미지화한 단일 OCR 전사이며, I2K 입력에는 파싱 I와 대응하는 원본 페이지/Figure 이미지를 함께 제공한다. 직전 dual 합성은 명시 옵션과 이력으로 보존한다. 이번 구현은 T03 source/evidence 범위이며 T04 의미 모델 실행·K/W schema 완료를 뜻하지 않는다. 아래 과거 parser 선택보다 이 문장이 우선한다.

2026-09-10 가장 최근 후속 승인: 사용자는 비교 결과를 읽은 뒤 **MinerU Hybrid + Pro2605 1.2B high와 PDF 원문 근거 보완**을 선택했다. [후속 승인 부록](MINERU_HYBRID_SELECTION.md)이 아래 이전 Paddle 선택의 새 parser 범위에 우선한다. 병합 전 source page/span 보존, 조회용 문단 통합, native PDF 제목 후보·전체 Figure/페이지·전사 차이 검출을 적용하고 원문/과거 이력·U01–U11과 P 상태는 유지한다.

> 적용일: 2026-09-09. U01–U11의 승인 범위와 근거를 각각 기록한다. P01–P12를 일괄 승인한 기록이 아니다.

2026-09-10 후속 선택: 사용자의 조건부 진행 지시와 공식 그림 분리·저장 지원 확인에 따라 새 PDF 파서는 [로컬 PaddleOCR-VL-1.6 전체 파이프라인](PADDLEOCR_SELECTION.md)으로 진행한다. 아래 U02/U05/U11의 MinerU 제품 지정과 충돌하는 새 parser 선택 범위에는 이 후속 부록이 우선한다. 원문 보존·application 의미 처리의 I2K 경계와 과거 승인·raw/I/ID/hash 이력은 유지한다. 실제 품질·통합 검증 결과는 실행 기록에서 별도로 확인한다.

## 승인 근거

사용자 요청 원문:

> 일단 GUI 구현은 마지막에 하고, CLI 구현만 우선시하도록 해줘. 그리고 D2I에서 PDF를 파싱할 땐, MinerU를 이용하도록 해줘. 그리고 Horreum, Bibliotheca와 Scriptorium에서, 너무 오래된 말이라 약간 라틴어/그리스어병에 걸린 거 같기도 해. 이름 영어로 적당히 바꿔줘.

## U01 — CLI 우선, GUI 마지막

상태: accepted. 현재 구현 범위는 headless CLI다. CLI를 T11에 몰아서 만들지 않고 T02부터 각 vertical slice의 기능을 CLI로 실행 가능하게 연결한다. T11은 review/운영 흐름의 통합·완성 단계다. T12는 CLI release gate이고 GUI가 없다는 이유로 blocked되지 않는다.

GUI는 T13에 별도 분리하며 초기 상태는 deferred다. T12 완료와 이후 사용자의 GUI 착수 지시가 모두 있어야 시작한다. CLI가 끝나기 전에 React/Electron/웹 대시보드/GUI 전용 API를 scaffold하지 않는다. MinerU가 내부적으로 사용하는 local API는 parser adapter의 구현 세부사항이지 GUI 착수가 아니다.

## U02 — PDF D2I는 MinerU

상태: accepted. D2I PDF parser 제품은 MinerU로 선택되었다. 제품 선택을 다시 미정으로 돌리지 않는다. U05의 최신 안정판 선택 정책에 따라 package/backend/model artifact/hardware profile과 실제 설치 명령을 검증해 고정한다.

MinerU가 만든 Markdown/JSON/images는 raw PDF D와 구분되는 parser 파생물이다. U11 이후에는 결정적 source-unit 조립과 구조·위치·무결성·전체 coverage 검사를 거쳐 canonical I가 된다. U11 이전 Generator–Validator 경로는 과거 profile의 기록으로 보존한다. 실패 시 다른 parser로 자동 대체하지 않는다. 기본 운영 계획은 로컬 실행이며 원격 전송은 별도 권한이 필요하다.

## U03 — 영어 구성요소 명칭

상태: accepted_by_delegated_naming(기계 판독 status는 accepted). 사용자가 적절한 영어 이름을 선택하도록 위임한 범위에서 아래 이름을 적용했다. 사용자가 이 정확한 문자열을 직접 제안했다는 뜻은 아니다.

- Horreum → **Artifact Store**; identifier `artifact_store`.
- Bibliotheca → **Canonical Store**; identifier `canonical_store`.
- Scriptorium → **Compiler Runtime**; identifier `compiler_runtime`.

`horreum_path`는 현재 field naming에서 `artifact_path`로 바꾼다. 과거 명칭은 원본 archive·검토 근거·migration/compatibility mapping에서만 사용한다. 기존 운영 DB/파일을 즉시 rename하거나 historical digest를 재계산하지 않는다.

## 권위와 범위

U01–U11가 명시적으로 선택한 범위에서는 이 변경이 우선한다. active canonical과 개발 지시서는 이를 반영한 현재판이다. `../source/`의 archived source와 baseline slices는 원본 근거로 유지한다. U08의 구조 수정과 U09의 DB/ID/등록·반영은 아래 각 계약에 명시한 범위에서 적용한다. P01–P12 전체와 범위 밖 세부 계약은 여전히 proposed다. U10의 Python/Docker와 U11의 D2I 경계는 확정이다. 나머지 framework·I2K 이후 Generator/Validator 모델 및 P 계약을 일괄 승인하지 않는다.

명령 문법·parser adapter 내부 필드의 세부 설계는 [CLI 계약](../interfaces/CLI_CONTRACT.md)과 [MinerU adapter](../interfaces/MINERU_ADAPTER.md)의 구현 초안이다. 새 domain 계층을 추가하는 결정이 아니다.

## U04 — BGE-M3 기본 Embedding/Reranker

상태: accepted (Embedding과 다중 벡터 Reranker 모두 BGE-M3). 추가 사용자 요청 원문:

> Embedding/Reranker는 BGE-M3을 기본으로 쓰고, MinerU는 최신 버전을 쓰도록 하자.

Embedding 기본 모델은 `BAAI/bge-m3`다. 공식 모델 카드의 dense output dimension은 **1024**다. 이 수치는 모델 특성의 확인이며 기존 DB schema를 생성/변경한 것이 아니다. [공식 embedding 모델 카드](https://huggingface.co/BAAI/bge-m3)

후속 질문은 전용 `BAAI/bge-reranker-v2-m3` 모델과 `bge-m3` 자체 다중 벡터 scoring 중 선택이었다. 사용자 답변 원문:

> bge-m3 자체의 다중 벡터 점수로 재순위화

따라서 Reranker도 **`BAAI/bge-m3`**를 사용하며, 해당 모델의 **multi-vector ColBERT late-interaction 점수**로 검색 후보를 재순위화한다. 전용 `BAAI/bge-reranker-v2-m3`는 선택하지 않았다. dense similarity나 dense/sparse/ColBERT 가중합을 이 Reranker 기본값으로 대체하지 않는다. sparse/hybrid 검색의 채택 여부는 별도다. [공식 BGE-M3 multi-vector 및 pair scoring 설명](https://huggingface.co/BAAI/bge-m3)

모델 revision/digest, runtime/library, precision, dense metric/normalization, 입력 길이·batch, sparse 검색과 multi-vector의 1차 검색 index 사용 여부, fusion weights, retrieval/rerank top-K는 이번 선택으로 고정하지 않는다. 재순위화의 multi-vector scoring은 확정되어 있다. 설치 및 실제 한국어 retrieval/rerank 평가는 미실행이다.

### U04 추가 — 향후 모델 교체

후속 사용자 요청 원문:

> 나중엔 Qwen3-Embedding 4B or 8B, Qwen3-Reranker 4B or 8B도 지원할 수도 있으니까, 교체 가능성을 염두에 둬야 해

Embedding과 Reranker는 각각 교체 가능한 profile/adapter 경계로 설계한다. 현재 BGE-M3 기본값은 유지한다. 향후 후보는 `Qwen/Qwen3-Embedding-4B`, `Qwen/Qwen3-Embedding-8B`, `Qwen/Qwen3-Reranker-4B`, `Qwen/Qwen3-Reranker-8B`이며 실제 지원 완료나 4B/8B 선택을 뜻하지 않는다.

교체 시 모델별 dimension, input projection과 scoring 방식의 호환성을 확인한다. 필요한 embedding 재생성은 파생 검색 projection에 한정하고 canonical 의미/ID/history를 바꾸지 않는다. 구체 경계와 공식 사양은 [RETRIEVAL_PROFILE](../interfaces/RETRIEVAL_PROFILE.md)을 따른다. P09/P12의 나머지 구현 세부사항은 미정이다.

## U05 — MinerU 최신 안정 릴리스

상태: accepted. 승인 근거는 U04 절의 추가 사용자 요청 원문이다. prerelease를 명시하지 않은 “최신 버전”은 **설치 또는 명시적 업그레이드 시점의 공식 최신 안정 릴리스**로 해석한다. 재현 가능한 실행을 위해 선택 후 exact package version/artifact digest, reported version, backend, model revision과 adapter version을 profile에 기록한다. 매 작업의 실행 환경을 자동 갱신하는 정책은 아니다.

2026-09-09 공식 PyPI 조회에서 최신 안정판은 **3.4.5**(업로드 2026-08-14), 4.0.0a6는 prerelease다. 이 값은 확인일이 있는 조사 결과이며 영구적인 최신 버전 상수나 설치 성공 기록이 아니다. 실제 설치할 때 다시 조회한다. [공식 PyPI 배포](https://pypi.org/project/mineru/)

T00에서 관찰한 release tag 내부 version.py의 3.4.4 표기와 배포 metadata 3.4.5의 차이는 설치 시 대조할 항목으로 유지한다. 최신판 선택 승인이 backend/model 준비 완료나 외부 원문 전송 권한을 뜻하지 않는다. 실패 시 parser fallback 금지 및 원문 provenance 보존은 U02대로 유지한다.

## U06 — D/I/K/W/P/B와 변환 작업의 모듈화

상태: accepted. 사용자 원문:

> 각 단계를 모듈식으로 작성해줄래? 그러니까, D I K W P B와 각 단계를 잇는 D2I, I2K 등 역시 모듈화해서, 향후 유지보수가 쉽도록 해줘.

하나의 애플리케이션 안에서 D/I/K/W/P/B를 각각 `data`, `information`, `knowledge`, `wisdom`, `parchment`, `book`의 독립 domain 코드 책임으로 나눈다. `d2i`, `i2k`, `n2e`, `k2k`, `k2w`, `w2k`는 각 변환의 입력 선택·정책·효과를 소유하는 모듈로 분리하고, `w2p`, `p2b`는 별도 publication application 모듈로 둔다. 유지보수를 위한 이 배치는 새 public Operation/Record subtype이나 microservice 분할을 의미하지 않는다.

Domain 규칙은 parser/model/DB adapter에서 독립시키고 공개 refs/snapshot 계약으로 연결한다. 공통 실행 기록·전파·transaction 구현을 재사용하며 모듈 간 직접 재귀 호출이나 모듈별 commit 분할을 만들지 않는다. W2K는 LLM 호출 없이 실제 권위가 확인된 Decision만 처리한다. D/I/W/P/B immutability와 K materiality/provenance 규칙은 그대로다.

실제 모듈별 책임·입력/출력·의존성·공통 atomic commit·단계별 테스트 소유권은 [MODULE_BOUNDARIES](../implementation/MODULE_BOUNDARIES.md)에 기록한다. 현재는 설계 계약이며 앱 구현이나 설치 완료가 아니다. 언어/물리 패키지 문법과 P03/P05/P06/P12의 미정 세부 계약은 별도다. T02부터 해당 단계의 필요한 모듈과 실제 테스트를 함께 구현한다.


## U07 — K2W 명칭 간소화

상태: accepted. 사용자 원문:

> kq2w는 k2w로 이름을 간소화하자. 다른 문서에도 반영해줘.

현재 Operation 이름은 `KQ2W` → `K2W`, 모듈 식별자는 `kq2w` → `k2w`로 변경한다. U06의 모듈 목록에도 이 이름을 적용한다. 입력은 여전히 **accepted KGraph + Query + Context**, 출력은 Explanation/Recommendation Wisdom이다. Query/Context 임시 overlay, direct Information 사용 시 retrieval_mode/epistemic_basis, 과거 Query 자동 재실행 금지 및 권위 확인 규칙은 유지한다.

이 승인은 명칭 변경에 한정한다. 새 Operation/Record subtype을 추가하거나 P01–P12의 미정 계약을 승인하지 않는다. 현재 문서·task·모듈 계약·acceptance 명칭·정책 검사와 canonical full/slices/map을 동기화한다. docs/source와 baseline_parts, 원본 invariant 인용, 과거 실행 기록의 이전 이름과 IDs/hashes는 보존한다. 실제 앱/DB가 없으므로 alias나 migration 구현은 만들지 않는다.


## U08 — 구조 검토 항목의 위임 수정

상태: accepted within scoped delegated repairs. 사용자 원문:

> 각 문제를 해결해주되, 중대해서 내 승인이 필요한 경우 나한테 요청해줘.

앞서 제시한 R01–R06/R09의 구체 권고를 기존 불변조건 안에서 반영하도록 위임받았다. 최신 applicability 우선, 현재 support/소비 dependency, scope별 완료, identity/rejection 순서, read-set freshness/replacement barrier, 명시적 Decision supersedes의 결정론적 atomic effect, evidence_mode/retrieval_strategy 분리를 적용한다. [해결 계약](ARCHITECTURE_FIXES.md)과 [항목별 상태](architecture_fixes.json)가 정확한 범위다.

R07/R08은 중대한 동작 선택으로 별도 요청했고, 후속 답변으로 늦은 Decision 재확인과 기각 exact scoped FP 조회를 승인받았다. P01–P12의 나머지 내용, public K 재검증 subtype 명칭, DDL/stack/provider·실행 profile을 일괄 승인하지 않는다. 앱 구현·live 실행·DB migration 완료도 아니다. original source 및 이전 canonical snapshot은 보존한다.


U08 후속 선택 근거:

- R07 사용자 답변: “뒤늦은 요청은 새 결정을 저장하지 않고 현재 상태를 보여준 뒤 재확인받기 (권고)”. 준비한 scope/head 상태가 바뀌면 새 canonical W/K를 저장하지 않고 실제 현재 상태로 재확인한다. 같은 event/payload의 기존 성공은 idempotent하게 반환한다.
- R08 사용자 답변: “기각 이력은 정확한 fingerprint로만 조회하고, 다른 표현의 후보는 다시 검증하기 (권고)”. 기각된 semantic payload의 유사 검색 보존은 추가하지 않는다. scope가 맞는 exact FP만 억제 판단에 사용하며 다른 표현·수정된 locator는 필요한 새 검증으로 처리한다.

이로써 R01–R09의 설계 해결 범위가 모두 확정되었다. 앱 구현/실행·나머지 P 계약의 상태는 별개다.

## U09 — PostgreSQL 18·pgvector·ID·관리 등록·canonical 반영

상태: accepted within recorded scope. 사용자 원문:

> 1. PostgreSQL은 최신 안정 버전인 18 버전 이상으로 해줘. 아마 곧 PG19가 나올 거긴 한데, 일단 임시로 18 쓰다가 나중에 업그레이드 하자. pgvector도 사용해야 하고.
> 2. data\_id는 content hash로, 나머지는 UUID V7이 나을 거 같아. 같은 Data가 중복되어서 들어오면 이건 거부해야지. 예를 들어 까먹고 같은 논문을 두 번 제공하면 이건 걸러야 하니까.
> 3. Data 원본 파일은 직접 폴더에 추가하지 말고, Palimpsest 도구를 이용해서 직접 등록하게 하면 실패 시 복구가 쉬워지지 않을까?
> 4. 판정은 Compiler Runtime에서 임시로 저장하고, 반영되면 Canonical Storage에 옮기는 방식으로 하면 되지 않을까?
> 
> 내 생각 반영해서 작업 계속해줘.

PostgreSQL은 최소 major 18, 최초 18 계열과 pgvector로 확정한다. Data ID는 원본 bytes SHA-256, 신규 opaque 객체/Record/revision/acquisition/request ID는 UUIDv7이다. 같은 Data의 새 등록 요청은 거부하고 도구를 통한 관리 등록·복구를 사용한다.

[STORAGE_IDENTITY](STORAGE_IDENTITY.md)에 구체 동작과 해석을 기록했다. 동일 성공 request는 기존 결과를 반환한다. 평범한 duplicate는 acquisition을 자동 추가하지 않으며 명시적 독립 출처 기록은 보존한다. 임시 후보·잠정 판정을 준비한 뒤 검증된 payload/effects를 canonical에 atomic하게 반영하며 최종 판정 Record는 Runtime에 영속 보존한다. 사용자 원문을 영속 Record 삭제 지시로 해석하지 않는다.

SQL 자료형·경로·등록 journal은 이 동작을 위한 T01 초안이다. 앱 언어/driver/migration runner·DB 실행 위치, 나머지 P06 enum/이름과 전체 P10 보존·삭제·backup 정책은 미정이다. 실제 DB 설치/적용, 원문 외부 전송은 수행하지 않았다.

## U10 — Python 앱과 Docker 기반 실행·배포

상태: accepted. 사용자 원문:

> 앱 언어는 Python으로 작성해주고, 배포 용이성을 위해 Docker 기반으로 작동하면 좋겠어. Docker 접근 권한 너한테 있나 지금?

앱 언어 Python, 실행·배포 기반 Docker를 선택했다. CLI 우선과 모듈 경계, PostgreSQL 18/pgvector를 유지한다. exact Python version, CLI library/dependency manager, driver/migration runner, image digest와 service/volume/port profile은 실행안을 구체화하며 정한다. [ENVIRONMENT](../implementation/ENVIRONMENT.md)에 실제 접근 관찰과 남은 범위를 기록한다. Docker read 성공은 모든 변경 작업의 무제한 권한이나 앱/DB 배포 완료를 뜻하지 않는다.

## U11 — 원문 보존 D2I와 구조화된 지식 compilation

상태: accepted scoped policy. 기존 D2I semantic 선별보다 우선한다.

사용자 메시지 전문:

> 일단 D2I 자체는 PDF등 LLM이 읽기 어려운 파일을 읽기 쉬운 형태로 바꾸는 것에 의의가 있어. 그러니까 D2I는 최대한 D 원본을 보존하면서, 페이지 정보나 위치 정보 등을 포함해야 해.
>
> Terra Medium 등 LLM 부분은 I2K 단계부터 적용하는 방식으로 해야해.

후속 사용자 메시지 전문:

> 지금 우리가 만드는 건 일종의 LLM wiki인데, 구조화된 출력을 사용해서 최대한 결정론적인 결과가 나오는 거야. Provenance도 보존되어야 하고.
>
> 그러니까 D2I는 최대한 스크립트 기반의 결정론적인 작업이어야 해. I2K나 N2E, K2K, K2W는 어쩔 수 없이 LLM이 관여해서 상황에 따라 달라질 수도 있겠지만, 이것도 출력을 최대한 구조화해서 중복 노드 생성이나 주관 개입 등을 피해야 해.
>
> 이 부분을 잘 생각해서 작업해주면 좋겠어.


D2I는 local MinerU와 script 기반의 결정적 처리로 원문 content·구조·page/region·raw locator·hash 및 전체 block coverage를 보존한다. LLM 의미 해석은 I2K부터 시작한다. 새 source Information의 profile은 `source-information-v1`, 처리 profile은 `source-d2i-v1`이며 source `unit_type`과 `semantic_type=null`을 구분한다. 구조적 acceptance는 진실성·semantic-fidelity 승인과 다르다.

Figure 전체/panel/caption/continuation, header/footer/reference text를 정보 가치로 버리지 않는다. 모델 context chunk와 retrieval filter는 exact I/source range에 결합한 별도 projection이다. 이전 semantic I·Record·profile·hash·migration은 immutable history로 보존하고 새 source schema는 additive migration으로 다룬다.

I2K/N2E/K2K/K2W의 LLM은 strict structured proposals와 exact provenance를 사용한다. canonical ID·FP·dedupe/reuse·typed refs·read-set·atomic commit은 애플리케이션이 통제한다. 구조화 출력만으로 의미적 동등성이나 완전한 결정론을 주장하지 않는다. [상세 계약](D2I_SOURCE_PRESERVATION.md)을 따른다. P01–P12의 나머지 제안과 미정 public subtype은 그대로이며 앱 완료나 I2K 착수 승인을 뜻하지 않는다.
