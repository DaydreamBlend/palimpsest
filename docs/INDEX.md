# 문서 인덱스 — 현재판과 원본 구분

**2026-09-14 W/P 구분과 구현:** [Wiki=Explanation W를 구성한 P](decisions/WIKI_WISDOM_PARCHMENT.md), [K2W 계약](interfaces/K2W.md), [W2P/불변 P](interfaces/PARCHMENT.md), [등록 시 Realm](interfaces/REALM_REGISTRATION.md), [T24 진행 기록](../progress/T24_wisdom_realm_execplan.md). 아래의 과거 noncanonical Wiki 구현과 새 canonical W/P를 구분한다.

**2026-09-14 다음 구현:** [0.22 기준 남은 기능과 등록 시 Realm·정정 영향](../progress/IMPLEMENTATION_BACKLOG_2026_09_14.md). 이전0.12 backlog의 미구현 표기와 현재 완료된 N2E/K2K/worker를 구분한다.

**2026-09-14 UI·Realm 후속:** [직접 Realm 지정과 일관된 탐색](interfaces/UI_REALM_ASSIGNMENT.md), [UI0.6/용량 정리 결과](../output/t23-ui-realm/REPORT.md), [output 보존·압축 기록 안내](../output/README.md).

**2026-09-14 통합 자료 공간:** [Electron 통합 읽기](interfaces/UNIFIED_DESKTOP.md), [Realm metadata/IPC](interfaces/REALM_DESKTOP.md), [구현·검증 기록](../progress/T22_unified_electron_execplan.md). 모든 등록 D의 source 읽기와 기존 Wiki 읽기를 구분하고, 같은 SHA의 다른 보존 위치도 정확하게 선택한다.

Realm의 [I2K Runtime/CLI 경계](interfaces/REALM_I2K.md), [0.21 완료 결과](../output/t22-unified-electron/REPORT.md)와 [통합 앱 실행](../Palimpsest.cmd).

**2026-09-14 후속:** [EffectiveEdge K2K](interfaces/EFFECTIVE_K2K.md), [0.20 결과](../output/t21-effective-k2k/REPORT.md), [통합 Electron 계획](../progress/T22_unified_electron_execplan.md), [승인된 Realm R/I2K 범위](decisions/REALM_SCOPE.md).

**2026-09-14 N2E 후속:** [네 관계의 생성·재검토·CLI·현재 적용성](interfaces/N2E_RELATIONS.md), [실행 기록](../progress/T20_n2e_completion_execplan.md), [0.19 실제 결과](../output/t20-n2e-completion/REPORT.md). 현재 P/O에 typed relations·대칭 dedupe·semantic Edge Revision·pending·contested 읽기 상태를 연결한다. 아래 supports-only 설명은 과거 profile의 범위다. Supersedes의 W2K 소유권과 Edge를 소비하는 별도 K2K/W/P 작업은 유지한다.

**2026-09-14 최신 전파 정정:** [의미 변화 기준·반복 advisory](decisions/MATERIALITY_FIRST_PROPAGATION.md), [0.18 실제 검사](../output/t19-materiality-convergence/REPORT.md). 새 run은 반복으로 중단하지 않고 independent nonmaterial/reuse로 semantic frontier를 멈추며 필요한 provenance/Wiki maintenance를 유지한다. 과거 T17의 halt policy는 이력으로 보존한다.

**2026-09-14 전파 진단 후속:** 앱0.17/schema0016의 [exact 반복 결과 진단과 확인](../output/t17-propagation-anomaly/REPORT.md), [운영 안내](interfaces/PROPAGATION_WORKER.md), [실행 계획](../progress/T17_propagation_anomaly_execplan.md). 같은 authoritative 전제의 정규화된 결과 복귀를 운영상 보류하며 canonical 판정을 뒤집지 않는다. [T18 paging](../progress/T18_dependency_paging_proposal.md)은 제안 상태다.

**2026-09-14 전파·Wiki 갱신:** [worker 운영·완료 경계](interfaces/PROPAGATION_WORKER.md), [실행 계획](../progress/T16_propagation_execplan.md), [실제 결과](../output/t16-propagation/REPORT.md). 앱0.16/schema0016은 저장된 변경 영향과 causal outbox를 처리하며 현재 근거·관계 재검증과 독립 검증된 Wiki 갱신을 연결한다. 기존 사용자 DB migration·D2I 재처리·자동 D2K·전체 T07 완료와 구분한다.

**2026-09-13 구현 계약:** [독립 D2K](interfaces/D2K.md), [명시적 K 의미 개정](interfaces/KNOWLEDGE_REVISION.md). 앱0.15/schema0014·0015의 실제 검증 결과는 [진행 기록](../progress/T15_explicit_d2k_execplan.md)에 누적한다.

**2026-09-13 최신 승인·착수:** [사용자 요청 독립 D2K](decisions/USER_REQUESTED_D2K.md), [구현 계획](../progress/T15_explicit_d2k_execplan.md). I2K 자동 우회 금지는 유지하며 별도 사용자 확인·원문 view·직접 D 근거·source-only 검증을 추가하고 K 개정 후속을 진행한다. 아래의 전면 D2K 금지는 이 명시적 사용자 예외에 한해 후속 승인으로 수정됐다.

**2026-09-13 최신 정정·후속:** [직접 D2K 금지와 I 부족의 D2I 오류 보고](decisions/I2K_INFORMATION_ERRORS.md), [0.14 Runtime·CLI·UI 계약](interfaces/INFORMATION_ERRORS.md), [수정된 실행 계획](../progress/T14_source_issues_execplan.md). 이전 direct-source 예외와 구현 초안은 철회됐다. 새 정보 오류 보고·관련 K 보류는 기존 I와 schema0013을 유지하며, 일반 K 선택 누락과 구별한다.

**2026-09-13 코드 D2I·검토 재개·Wiki 후속:** [0.13 구현 계약](interfaces/CODE_REVIEW_WIKI.md), [실제 결과](../output/t13-code-review-wiki/REPORT.md), [실행 계획](../progress/T13_code_review_wiki_execplan.md). Python AST/tokenizer로 원문과 파일 위치를 보존하고, 전체 I2K 검토 재개·exact K2K/버전 검색·Electron 읽기를 연결한다. production D2I application LLM은 0이며 아래 native parser 보류보다 최신이다. 직접 D canonical grounding·전체 scheduler·개인 Decision·온라인 수집은 후속이다.

**2026-09-13 후속 구현 목록:** [0.12 이후 현황·권고 순서](../progress/IMPLEMENTATION_BACKLOG_2026_09_13.md). 코드 D2I, I2K 검토·직접 원문 근거, K 개정/상충/시간, 변경 재검토, 최신 K·버전의 Wiki/RAG/UI 연결, 개인 결정, 인터넷 수집과 운영을 구분한다. 사용자가 추가한 공유 글은 설계 참고로 읽었으며 새 계약이나 migration을 자동 승인한 기록이 아니다.

**2026-09-13 D 버전·공유 저장 구현·검증:** [승인된 설계](implementation/DATA_VERSION_STORAGE_PROPOSAL.md), [자료 버전 계약·CLI](interfaces/DATA_VERSIONS.md), [실제 결과](../output/t12-versioned-code/REPORT.md), [실행 계획](../progress/T07_versioned_code_execplan.md). rawSHA D를보존하며공유blob·자료이력·exactversion I2K/N2E/K2K를구현했다. 두모듈의V1/V2에서25K/7Edge/2추론을저장하고208개읽기전용검사와자료A→B→A를검증했다. I2K전체의미검토는보류항목을유지한다. 적용DB는격리fixture/code의0013이며기존source/WikiDB는보존했다.

**2026-09-13 코드베이스 D/I·첫 K2K:** [코드 원문 snapshot·등록·위치 복원](interfaces/CODEBASE_SNAPSHOT.md), [K2K 실행·기원·전제·저장 경계](interfaces/K2K_RUNTIME.md), [실제 결과](../output/t11-codebase-k2k/REPORT.md), [계획](../progress/T07_codebase_k2k_execplan.md). 실제 코드202파일을 D1/I204로 저장했다. K2K는 합성 판정으로 실제 PG 검증했고 코드 기반 live 추론은 아직 수행하지 않았다. 코드 전용 D2I parser와 전체 자동 전파는 후속이다.

**2026-09-13 범용 D/I/K 검토 구현:** [원문 구간·LLM 의미 항목·exact KRevision 연결](interfaces/SOURCE_REVIEW.md), [실제 구조/PG 검사와 한계](../output/t10-source-review/REPORT.md), [실행 계획](../progress/T04_source_review_execplan.md). 특정 논문/패널 수를 하드코딩하지 않고 새 전체-source I2K에 적용한다. 기존 I/Revision과 migration은 보존하며 실제 의미 회수율 평가와 구분한다.

**2026-09-13 Electron UI 구현:** [실행·기능·보존 경계](interfaces/DESKTOP_UI.md), [명시적 착수 승인](decisions/ELECTRON_UI_START.md), [실제 앱·패키지 결과](../output/t09-electron/REPORT.md), [실행 계획](../progress/T09_electron_ui_execplan.md). 첫 읽기·원문 대조·검토 UI를 구현하고 Windows exe에서 검증했다. 아래 조사-only 상태보다 최신이며 기존 core 규칙과 schema0010은 유지한다.

**2026-09-13 Electron 직접 UI 조사:** [적합성·Python/Docker 연결·웹 공유·부품·배포 부담](implementation/ELECTRON_UI_ASSESSMENT.md). 전용 지식 작업 앱은 Electron, 읽기/게시는 Quartz의 역할로 구분하는 후속 권고다. [조사 계획과 검증 범위](../progress/T08_electron_research_execplan.md). 앱·GUI scaffold·DB 변경·성능 시험은 수행하지 않았다.

**2026-09-12 Wiki 검색·UI 조사:** [질문 CLI·BGE/pgvector·원문 근거 답변](interfaces/WIKI_QUERY.md), [실제 성공/보류/품질 수정](../output/t07-wiki-query-ui/REPORT.md), [기존 UI 비교·연결 설계](implementation/WIKI_UI_INTEGRATION.md), [실행 계획](../progress/T07_wiki_query_ui_execplan.md). source I와 K/Page 이력을 보존하는 비canonical query runtime을 구현했다. Quartz/Obsidian, Wiki.js, Outline, BookStack은 공식 조사만 수행했으며 GUI 설치·공개 게시·W/P 전체 구현과 구분한다.

**2026-09-12 Wiki DB 후속:** [PostgreSQL 저장·복원·K 탐색 CLI](interfaces/WIKI_DATABASE.md), [실제 검증](../output/t06-wiki-postgres/REPORT.md), [실행 계획](../progress/T06_wiki_postgres_execplan.md). 비canonical Wiki schema 0008/0009에 기존 문서와 원래 JSON을 보존하고 exact KRevision source 탐색을 추가했다. 파일 편집 후 DB sync는 명시적인 별도 transaction이다. 정식 P/W 계약·원본 live DB migration·GUI/crawler와 구분한다.

**2026-09-12 논문별 Wiki 착수:** [논문·주제 문서 CLI](interfaces/PAPER_WIKI_PROJECTION.md), [사용자 요청과 첫 구현 범위](decisions/PAPER_WIKI_PROJECTION.md), [실행 계획·실제 결과](../progress/T05_paper_wiki_execplan.md). 기존 전체 I에서 논문별 페이지와 출처별 주제 문서를 만드는 비canonical read/export projection을 구현했다. 고정 renderer·stable page IDs·snapshot 이력과 모델 검토를 포함하며 정식 P/DB 확장·GUI·crawler와 구별한다.

**실제 결과:** [3편·논문3/주제22·인용72·공통 페이지 이력](../output/t05-paper-wiki/REPORT.md). BMDC별도페이지와Clarke/Dejani의MoDC·Th17공통페이지를만들었다. 기존DB32tables/4,427rows hash불변, 최종앱555tests(539pass/16skip)를확인했다. 실제22회모델호출·독립피드백·보류이력을포함하며무인정확도나canonical P완료로해석하지않는다.

**2026-09-12 자동 Wiki 제품 목표:** [자동 분류·정형 페이지·증분 갱신·향후 웹 수집 설계](../progress/AUTOMATIC_WIKI_DESIGN.md). D/I/K 위에 고정 page schema와 renderer, 편집·current 문서 선택을 두는 제안이다. 다음 사용자 관찰 목표는 첫 자료가 일정한 페이지를 만들고 다음 자료가 그 페이지를 정확히 갱신하는 것이다. 앱/DB/웹 UI/crawler를 구현한 상태가 아니며, 기존 source·Knowledge·authority·publication 계약의 구체 변경은 별도 검토한다.

**2026-09-11 LLM Wiki 외부 참조:** [공식 문서·실제 코드 비교](../output/t04-llm-wiki-references/REPORT.md). 원문에서 wiki 페이지/링크를 만드는 패턴과 GraphRAG·Graphiti의 인접 구조를 조사했다. I는 독립적인 원문 근거와 semantic search 대상으로 유지하며, wiki 탐색 링크를 supports로 간주하지 않는다. 외부 앱 실행·벤치마크나 Palimpsest 구현 변경은 하지 않았다.

**2026-09-11 최신 검토 방향:** 사용자는 K 통합을 필수로 요구하지 않는다고 명확히 했다. 공통 K 개수 대신 개별 K의 원문 충실성·인용 충분성·기존 오류 정정을 우선한다. [I2K 신뢰성 개선안](../progress/T04_I2K_reliability_proposal.md)은 설계 제안이며 새 코드/DB/모델 검증 완료를 뜻하지 않는다. 아래 실험의 multi-Data K 0개는 이후 지시에 따라 실패 기준에서 제외한다.

**2026-09-11 다중 Data Runtime 구현 상태:** [입력 결합·명시 원문 검증·저장·CLI 안내](implementation/MULTI_SOURCE_RUNTIME.md). `palimpsest-multi:0.5.0` 고정 이미지 검사 484개 중 468 pass/16 skip. 두 추가 논문의 전체 51 I/44 이미지 실제 Terra 실험에서 새 K 11개·Edge 1개와 기존 Revision 재사용 9개를 확인했다. 실제 multi-Data 근거 K는 0개이고 의미 오류와 미완료 검토가 남았다. [결과 보고서](../output/t04-multi-source/REPORT.md)는 구조 검사와 의미 품질을 구분한다. 기존 DB 0007 승인 대기, 격리 DB, 준비 과정의 중간 I 오류도 보존한다.

**2026-09-11 최신 정정과 실제 실험 요청:** [I2K 원문 정리·새 결론은 K2K](decisions/I2K_SOURCE_ONLY_K2K_INFERENCE.md). I2K에서 원문에 없는 결론·추측은 만들지 않으며 신규 I2K-origin Revision은 `is_inferred=false`다. 다중 Data 구현·실제 실험의 상태는 [현재 실행 계획](../progress/T04_multi_source_runtime_execplan.md)에서 확인한다.

**2026-09-11 여러 D의 I2K:** [I 1개 이상 → K 하나와 다중 출처 근거](decisions/MULTI_SOURCE_I2K.md)를 적용한다. 서로 다른 D에 명시된 내용을 함께 사용하며 전체 I 검토·후보별 근거·출처별 실험 구분을 유지한다. [이전 문서 점검](../progress/T04_multi_source_i2k_execplan.md)은 실제 다중 Data 실행 결과와 구분한다.

**2026-09-11 LLM Wiki 방향:** [K → I embedding 검색 → D 원본 확인](decisions/LLM_WIKI_RETRIEVAL.md)을 제품의 조회 구조로 삼는다. LLM은 자주 사용할 것으로 판단한 내용을 K로 미리 정리하며, K에 선택하지 않은 I도 검색에 사용한다. 각 단계의 부족을 이유로 D2I를 재실행하지 않는다.

같은 승인에는 K2K의 귀납·연역 지식 생성도 포함한다. K는 원문 정리와 새 추론을 모두 축적하며, I는 D2I의 원문 표현으로 유지한다. 파생 K의 전제 Revision·가정/한계·검증·I/D 계보를 [T07](../tasks/T07.md)에 명시했다. 실제 K2K 실행은 아직 미구현이다.

**2026-09-11 최신 근거 공백 정책:** [D2I 재실행 금지와 직접 D 근거](decisions/I2K_DIRECT_SOURCE_EVIDENCE.md). I2K는 I의 근거 부족을 D2I 재호출로 보완하지 않는다. 등록 원본을 직접 검증한 K와 누락/불일치 이력을 연결하는 요구를 적용한다. [현재 K 저장·전체 I 선택](implementation/FULL_SOURCE_SELECTION.md)은 실행되었으며, 원본 직접 grounding과 자연어 Wiki 검색·답변은 미구현이다. [이번 상태 점검](../progress/T04_direct_source_policy_execplan.md).

**2026-09-11 최신 진행:** [D↔I 대응과 전체 I의 LLM 선택](decisions/FULL_SOURCE_LLM_SELECTION.md), [실행 계획](../progress/T04_full_source_selection_execplan.md). 일반 명제 재사용과 다른 Data의 실험 결과 보존을 구분한다.

## 먼저 읽기

**여러 형식의 D2I 설계 — 2026-09-11:** [공통 수집·검증·저장과 형식별 구조 파서](implementation/D2I_INPUT_FORMATS.md)는 URL/PDF/HTML/Markdown/코드 파일을 원문 근거가 있는 문맥 그룹 I로 만드는 방향과 구현 순서를 정리한다. PDF/Markdown의 실제 구현, HTML 검토, 코드 미구현을 구분하며 별도 D2I 의미 LLM을 도입하지 않는다.

**HTML 수집·D2I 검토 — 2026-09-11:** [지정 GeekNews HTML의 검토 결과](../output/t03-html-review/REPORT.md)는 응답 bytes55,612개를 실제D로등록하고 원문 매핑이 있는12개 읽기그룹 시안을 검증했다. HTTP수집metadata/원글·댓글출처/CSS·JS/같은URL의다른snapshot을구분한다. 앱HTML runtime·canonical I는아직미구현이며이번결과를HTML지원완료로해석하지않는다.

**Markdown D→D2I→I — 2026-09-11:** [실행 안내](implementation/MARKDOWN_RUNTIME.md)는 도구 등록한 UTF-8 Markdown의 heading 그룹과 exact byte/char/line grounding을 설명한다. [실제54KB문서의24 I 저장·PDF migration 호환성](../output/t03-markdown/REPORT.md)을 확인한다. 기존 PDF 좌표를 가장하지 않으며 모델·OCR·외부 링크 fetch는0이다.

**최신 그룹 I 저장 — 2026-09-11:** [승인 부록](decisions/GROUPED_INFORMATION_STORAGE.md)에 따라 새 D2I는 스크립트로 묶은 단위를 canonical I로 저장한다. [그룹 저장·기존 parser 재조립 CLI](implementation/GROUPED_INFORMATION.md)는 exact block/페이지/문자 범위/이미지를 유지하며 과거 I와 raw를 재작성하지 않는다. 아래 조회-only 그룹화 설명은 과거 상태이며 새 영속 단위는 이 변경을 따른다.

**T04 첫 구현 — 2026-09-11:** [I2K 입력 준비·원본 PDF 요청 CLI](implementation/T04_INPUT.md)는 완료된 source 실행의 canonical I를 검증해 text/media/provenance 입력을 구성하고, 같은 입력 hash의 구조화 요청에 등록 원본 PDF를 로컬 준비한다. [Test_Paper 실물 검증](../output/t04-input/REPORT.md)과 [후속 계획](../progress/T04_input_execplan.md)을 확인한다. 실제 모델 전달·판단·K 저장은 후속 단계다.

**최신 I2K 입력 정책 — 2026-09-11 후속:** [D2I 스크립트 청킹·I 우선·필요 시 원본 PDF](decisions/I2K_I_FIRST_SOURCE_ON_DEMAND.md)를 적용한다. I의 text/media/provenance를 먼저 보내고, 원문이 필요하다고 판단되면 동일 Data의 등록된 PDF를 제공한다. 이전의 원본 페이지 이미지 일괄 동시 입력을 대체한다. MinerU 내부 OCR/layout 모델과 source 보존은 유지하며 별도 청킹 LLM은 사용하지 않는다. [현재 변경과 검증](../progress/T03_i_first_policy_execplan.md).

**전체 문서·절 읽기 snapshot과 결정/Revision 이력 — 2026-09-11:** [스크립트 전체 문서·절 읽기·Figure 참조](implementation/SECTION_CONTEXT.md)는 LLM wiki/RAG의 입력 기반을 조회한다. 일반 논문은 실제 한도가 허용하면 전체 I를 순차 제공하고, 절/문단은 탐색·RAG·부분 재검증·긴 문서 분할에 사용한다. source/evidence·완료된 단일 execution·projection SHA를 결속하고, 변경된 묶음에 예전 section 번호를 적용하면 거부한다. 조회 결과의 원본 페이지 descriptor는 보존된 근거이며 자동 모델 전송이 아니다. [이전 구현 결과](../progress/T03_section_projection_execplan.md)는 원문 순회·실제 CLI·Docker 검사와 미실행 I2K/RAG/K/W 저장을 구분한다.

**최신 문맥 구성 설계 — 2026-09-10:** [스크립트 우선 입력 정책](implementation/I2K_CONTEXT_POLICY.md)은 PDF의 완벽한 절 분류보다 I2K가 필요한 원문·문맥을 빠짐없이 읽도록 하는 설계다. 경미한 경계 차이는 원문·이미지·추가 조회로 해석하고, 입력 누락·잘못된 Figure 확정 연결은 코드로 막는다. 별도 소형 LLM 사전 검토는 기본 경로에서 생략하는 안이다. [계획과 검증](../progress/T03_script_context_design_execplan.md)은 후속 구현·실제 I2K 비교가 아직 미실행임을 구분한다.

**I 길이와 문서 구조별 I2K 입력 — 2026-09-10:** [입력 그룹·semantic/provenance 검색 정책](implementation/I2K_CONTEXT_POLICY.md)은 Abstract/Introduction 각각의 논리적 그룹, Results 소절·Figure 연결, Markdown heading, same-D 문맥 우선과 corpus 관련 근거 검색, profile별 embedding index를 다룬다. [Test_Paper229 I 길이·검토된18그룹](../output/t03-information-context/REPORT.md), [측정·검증 범위](../progress/T03_information_context_execplan.md)를 확인한다. 실제 embedding·I2K runtime 구현 완료를 뜻하지 않는다.

**PDF 기본값 — 2026-09-10:** [MinerU 이미지 OCR 기본값](decisions/MINERU_IMAGE_DEFAULT.md)이 아래 dual 기본값을 대체한다. 단일 image200 OCR 원문 I와 원본·파생 좌표/raster를 보존한다. 당시 원본 이미지 동시 I2K 입력은 위의 2026-09-11 I 우선 정책으로 대체됐다. [현재 D/I/K/W 구조](implementation/DIKW_CURRENT.md)는 구현된 D/I와 설계 단계 K/W를 구분한다. [당시 실행 계획·검증](../progress/T03_image_default_execplan.md)을 확인한다.

**직전 PDF 기본값 — 2026-09-10 후속 승인:** [MinerU 이중 전사](decisions/MINERU_DUAL_TRANSCRIPTION.md)는 원본 PDF auto + 200 DPI 이미지 OCR을 함께 사용하고 일반 문자 native/특수문자 OCR 우선의 새 선택 I와 양쪽 exact provenance를 보존한다. 구현·실험 상태는 [실행 계획](../progress/T03_paddle200_execplan.md)과 [최종 실물·PG·근거 조회 검증](../progress/T03_dual_transcription_result.md)에서 구분한다.

**이미지 전용 전사 비교 — 2026-09-10:** [17편의 고정51페이지 OCR 실험](../progress/T03_image_transcription_result.md)은 실제 text0 이미지 입력과 동일 Hybrid high/Pro2605를 비교했다. 알려진 Greek 오류5건 및 표적 micro 단위16곳을 복구했으며 strict 문장은32/51→41/51이다. 하이픈 소실·Figure crop 잘림·OCR 위치 정밀도 한계를 함께 기록했고 제품 기본값과 기존 canonical I는 변경하지 않았다. [계획](../progress/T03_image_transcription_execplan.md), [기계판독 결과](../progress/T03_image_transcription_result.json).

**현재 방식의 추가 평가 — 2026-09-10:** [새 논문17편243페이지 평가](../progress/T03_expanded_papers_result.md)와 [기계판독 결과](../progress/T03_expanded_papers_result.json)는 아래 선택된 Hybrid high 구현을 변경하지 않은 확대 코호트 결과다. 파싱/source 제안 검증17/17과 근거 package16/17, 고정51페이지의 Figure·제목·전사 품질을 구분한다. 모델/기본값 변경이나 T03 전체 완료 승인은 아니다.

**가장 최근 parser/원문 보완 승인 — 2026-09-10:** [MinerU Hybrid + Pro와 PDF 근거 projection](decisions/MINERU_HYBRID_SELECTION.md)이 아래 이전 Paddle 선택보다 뒤에 승인됐다. 새 실행은 Hybrid high를 사용하고 원래 페이지·leaf span 근거와 조회용 문단 통합을 분리한다. [실행 계획](../progress/T03_pdf_evidence_execplan.md), [실제 결과](../progress/T03_pdf_evidence_result.md), [CLI·모듈 계약](interfaces/PDF_EVIDENCE.md)에서 구현·실물 검증 범위를 확인한다.

**최신 parser 선택 — 2026-09-10:** [PaddleOCR-VL-1.6 후속 승인](decisions/PADDLEOCR_SELECTION.md)을 먼저 읽는다. 공식 그림 분리·저장 지원을 확인한 뒤 로컬 전체 파이프라인으로 진행하는 선택이다. 아래 MinerU 관련 문서의 제품 지정과 충돌하는 새 실행 범위에는 이 부록이 우선하며, U11의 원문 보존·I2K부터 의미 처리·과거 이력 불변은 유지한다. 실제 추출 품질과 연결 상태는 [진행 기록](../progress/T03_paddleocr_execplan.md)에서 확인한다.

[사용자 변경 U01–U11](decisions/USER_OVERRIDES.md)은 CLI 우선·GUI 마지막, PDF parser=MinerU, 영어 구성요소명, BGE-M3 임베딩 및 같은 모델의 multi-vector ColBERT 재순위화, MinerU 최신 안정판 정책과 domain/변환별 모듈화, K2W/k2w 명칭 및 [U08 구조 수정](decisions/ARCHITECTURE_FIXES.md)의 명시된 범위를 확정한다. R07/R08도 후속 승인에 따라 늦은 결정 재확인·기각 exact FP 조회로 확정했다. [Decision register](decisions/DECISION_REGISTER.md)의 나머지 P01–P12는 proposed다.

## Current canonical

[현재 통합본](canonical/PALIMPSEST_CANONICAL_MODEL.md)은 아래 13개 현재 분할본을 재결합한 snapshot이다. `canonical/current_map.json`이 현재 line ranges와 hashes를 관리한다. 아래 줄 번호는 archived source가 아니라 현재판 기준이다.

- [00_foundation.md](canonical/00_foundation.md) — 문서 권위·정의·책임 영역·계층 (§0–3); current L1–L150.

- [01_data_d2i.md](canonical/01_data_d2i.md) — Data·수집 이력·D2I (§4–5); current L151–L304.

- [02_information.md](canonical/02_information.md) — Information·교정·재검증 (§6); current L305–L441.

- [03_knowledge_graph.md](canonical/03_knowledge_graph.md) — KNode·KEdge·Revision·Applicability (§7); current L442–L686.

- [04_compiler_records.md](canonical/04_compiler_records.md) — Compiler·Record·Candidate (§8–10); current L687–L997.

- [05_identity_materiality.md](canonical/05_identity_materiality.md) — Fingerprint·Material delta (§11–12); current L998–L1155.

- [06_knowledge_operations.md](canonical/06_knowledge_operations.md) — I2K·N2E·K2K·반박 (§13–16); current L1156–L1387.

- [07_propagation.md](canonical/07_propagation.md) — Convergent propagation (§17); current L1388–L1511.

- [08_wisdom_decisions.md](canonical/08_wisdom_decisions.md) — Wisdom·Decision·W2K·Trace (§18–22); current L1512–L1861.

- [09_publication_retrieval.md](canonical/09_publication_retrieval.md) — Parchment·Book·RAG (§23–24); current L1862–L1965.

- [10_relational_vocabulary.md](canonical/10_relational_vocabulary.md) — Relational skeleton·용어 (§25–26); current L1966–L2108.

- [11_invariants_decisions.md](canonical/11_invariants_decisions.md) — 불변조건 45개·A1–A40 (§27–28); current L2109–L2205.

- [12_open_implementation.md](canonical/12_open_implementation.md) — 미정값·구현 순서·결론 (§29–30); current L2206–L2267.

## Archived baseline

[수정 전 원본](source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md)은 2,331줄/114,329 bytes를 그대로 보존했다. `source/source_map.json`과 `source/baseline_parts/`로 byte-identical 복원이 가능하다. [REVIEW](review/REVIEW.md), [ERRATA](review/ERRATA.md)와 원본 invariant 인용의 줄 번호는 이 archived source를 가리킨다. 옛 구성요소명은 역사 근거이지 현재 지시가 아니다.

## 새 실행 interface

[T03 실행 안내](implementation/T03_RUNTIME.md), [원문 보존 PDF→I 결과](../progress/T03_source_result.json), [페이지 조회·인접 문맥](implementation/PAGE_CONTEXT.md), [페이지 조회 실물 결과](../progress/T03_page_result.json), [실행·검증 기록](../progress/T03_execplan.md)을 참고한다. U11 원문 보존 D2I의 제공 PDF 시험과 읽기 전용 페이지 projection은 검증됐다. 이전 semantic D2I 결과는 과거 profile의 실험이다. T03 전체 gate와 I2K는 아직 완료되지 않았다.

[CLI 계약](interfaces/CLI_CONTRACT.md), [MinerU adapter](interfaces/MINERU_ADAPTER.md), [MinerU 공식 자료](interfaces/MINERU_REFERENCES.md)를 읽는다. CLI/MinerU 선택은 확정이나 detailed command/wire profile은 구현 초안이다.

[검색 모델 profile](interfaces/RETRIEVAL_PROFILE.md)은 BGE-M3 기본 embedding/multi-vector reranking과 향후 Qwen3 4B·8B 교체 경계를 설명한다.

## 기존 보완 계약 — 승인 상태 별도

- [01_identity_materiality.md](contracts/01_identity_materiality.md)

- [02_effective_relations_dependencies.md](contracts/02_effective_relations_dependencies.md)

- [03_propagation_completion.md](contracts/03_propagation_completion.md)

- [04_transactions_execution.md](contracts/04_transactions_execution.md)

- [05_compiler_validation_evidence.md](contracts/05_compiler_validation_evidence.md)

- [06_decision_wisdom_publication.md](contracts/06_decision_wisdom_publication.md)

- [07_storage_retrieval_security.md](contracts/07_storage_retrieval_security.md)

- [08_interfaces_schema_plan.md](contracts/08_interfaces_schema_plan.md)

## 개발/검증

[선택적 제목 실험의 모델](implementation/HEADING_MODEL_PROFILE.md)은 사용자가 선택한 Qwen3.5-4B Q4_0와 thinking2048의 재현용 실행 profile이다. 과거 E4B/BF16 실험 기록을 보존하며, 최신 스크립트 우선 설계의 필수 사전 단계나 source D2I 모델로 활성화한 것은 아니다.

[문맥 묶음 모델 비교](../progress/T03_context_models_execplan.md)는 Qwen3.5-4B Q4_0, Gemma 4 E4B Q4_0 및 사용자 추가 승인 Qwen3.5-9B Q8의 비canonical I2K 입력 projection 실험이다. 원문 I 보존·출력 coverage와 문맥 품질을 따로 평가하며 [I2K 입력 정책](implementation/I2K_CONTEXT_POLICY.md)을 따른다.

[스크립트 초안 + 9B 재검토](../progress/T03_script_context_review_execplan.md)는 후속 사용자 지시에 따라 원문 구조로 먼저 나눈 뒤 Qwen3.5-9B Q8_0가 지정된 후보만 검토하는 실험이다. 전체 source 보존, 모델의 개선·회귀 및 미검토 범위를 별도로 기록한다.

[같은 초안의 4B 비교](../progress/T03_script_context_review_4b_execplan.md)는 Qwen3.5-4B Q4_0에 동일한 원문·후보·정책·출력 구조를 제공해 9B와 결과를 대조한다. 새 파서/제품 기본값 선정이나 K runtime 완료가 아니다.

[Qwen3.5-9B NVFP4 마지막 비교](../progress/T03_script_context_review_nvfp4_execplan.md)는 사용자 추가 지시에 따라 NVFP4 체크포인트의 실행 가능성을 확인하고 같은 스크립트 초안으로 Q8_0 및 4B 결과와 비교한다. 양자화 형식·변환 출처·실제 실행 조건을 기록하며 원본과 이전 결과를 보존한다.

[9B Q8 추가 검토](../progress/T03_qwen9b_extended_execplan.md)는 후속 사용자 요청으로 논문 3편 53쪽을 현재 image200 방식으로 파싱하고 자연 초안 18호출, 균형 사례 36호출, 기존 회귀 1호출을 평가했다. [결과](../output/t03-qwen9b-extended/REPORT.md)는 선택 33/36, 선택과 근거 30/36 및 반복된 Figure 연결 오류를 기록한다. 522개 원문 보존과 실제 자연 검토 범위 154개, 후보 생성 누락과 모델 오분류를 구분한다.

[ROADMAP](implementation/ROADMAP.md), [모듈 경계](implementation/MODULE_BOUNDARIES.md), [ENVIRONMENT](implementation/ENVIRONMENT.md), [MIGRATION](implementation/MIGRATION.md), [EVALUATION](implementation/EVALUATION.md), [tasks](../tasks/README.md)를 따른다.

[112개 acceptance specs](../tests/specs/ACCEPTANCE.md)와 [원본 invariant traceability](../tests/specs/TRACEABILITY.md)는 명세다. 실제 T02 실행/부분 검증/미실행은 [T02 실행 기록](../progress/T02_execplan.md)과 catalog의 상태를 따른다. current/baseline 재결합과 문서 검사는 package tools의 별도 결과다.

[변경 전 current snapshot](history/2026-09-09_pre_architecture_fixes.md)은 이전 구조 검토의 exact 근거이며 현재 구현 규칙은 아니다. [해결 상태](decisions/architecture_fixes.json)에 위임 수정 범위와 후속 사용자 선택 근거를 기록한다.

[U09 저장·ID 계약](decisions/STORAGE_IDENTITY.md)과 [T02 DB 스키마 초안](schema/T02_STORAGE_SCHEMA.md)은 PostgreSQL 18/pgvector, ID, 등록·복구와 Runtime→canonical 반영을 구체화한다. [변경 전 snapshot](history/2026-09-09_pre_storage_identity.md)은 U08 완료 시점의 exact bytes다.

[D/I/K/W 저장 스키마 v1](schema/DIKW_STORAGE_SCHEMA_V1.md)은 ERD, 필드·typed FK·제약, Runtime/검색 profile, 확정 transaction과 단계별 migration 계획을 연결한 T01 review draft다. 현재 canonical의 의미를 유지하며 P06 등의 미정 항목을 별도로 표시한다. 실제 DB migration 적용 결과가 아니다.

U10의 Python 앱·Docker 실행/배포 및 실제 접근 결과는 [실행 환경](implementation/ENVIRONMENT.md)을 따른다. [U10 직전 snapshot](history/2026-09-09_pre_python_docker.md)은 이전 current bytes를 보존한다.

[T02 실행 안내](implementation/T02_RUNTIME.md)는 구현한 Python/Docker CLI, 고정 버전·이미지, 초기 migration, Data 등록·검증·요청 복구와 테스트 명령을 제공한다. 전체 D/I/K/W schema v1의 구현 완료가 아니라 첫 Data slice다.

[U11 원문 보존 D2I](decisions/D2I_SOURCE_PRESERVATION.md)는 local MinerU + 결정적 source-unit 조립·구조/전체 coverage 검사를 적용하고 LLM 의미 해석을 I2K부터 시작한다. source I와 context projection을 구분하며 ID/FP/중복·재사용/atomic commit은 애플리케이션이 관리한다. [U11 직전 snapshot](history/2026-09-09_pre_d2i_source_preservation.md)은 이전 canonical과 semantic I 정의의 exact 근거다. 과거 구현·schema 결과는 재작성하지 않는다.

[Test_Paper K 저장 실행](implementation/KNOWLEDGE_RUNTIME.md)은 기존 I의 Terra Medium I2K와 accepted NodeRevision의 N2E를 분리한다. 측정·한계·실제 DB 상태는 [실행 기록](../progress/T04_knowledge_execplan.md)을 따른다.

[전체 source 주소·LLM 선택 구현](implementation/FULL_SOURCE_SELECTION.md)은 D↔I 조회, 전체 I 검토, 일반 K 재사용과 source K 보존을 실제 연결합니다. [최종 실험](../output/t04-full-selection/REPORT.md)에 원문 복원·32 K·후속 N2E와 한계를 기록합니다.
