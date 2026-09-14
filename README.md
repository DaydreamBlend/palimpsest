# Palimpsest — Python/Docker CLI / MinerU

**2026-09-14 UI0.6/backend0.22:** [참고안 기반 UI·직접 Realm 지정](docs/interfaces/UI_REALM_ASSIGNMENT.md), [완료 결과·용량 정리](output/t23-ui-realm/REPORT.md), [실행](Palimpsest.cmd). Realm을 유지하는 탐색, 자료별 소속 변경, 기존 코드 K42개와 I 역추적을 연결했다. 새 I2K/모델 호출은 없으며 전체코드 스냅샷의 준비 상태를 구분한다. 이전 Electron 실행본과 불필요한 로그/캐시는 사용자 승인에 따라 정리했고 새 UI는 공용 Electron 엔진을 사용한다.

**2026-09-14 통합 자료 공간·0.21:** [통합 Electron](docs/interfaces/UNIFIED_DESKTOP.md)은 논문·코드와 Wiki 없는 등록 D를 같은 앱에서 읽는다. 원본이 같은 자료는 목록에서 묶되 저장소별 I·K·Revision은 구분한다. [Realm metadata](docs/interfaces/REALM_DESKTOP.md)는 별도 catalog에 보존하며, 승인된 I2K 기본 분리·명시적 교차 선택을 연결한다. [구현·검증 진행](progress/T22_unified_electron_execplan.md). 기존 source DB schema와 원본은 재작성하지 않는다.

[통합 앱 실행](Palimpsest.cmd) · [실제 검증·배포 결과](output/t22-unified-electron/REPORT.md) · [Realm I2K CLI](docs/interfaces/REALM_I2K.md). 소스/패키지 UI17개, JS63개, 관련Python92개와추가호환9개, 기존코드이력137개검사를각각통과했다. 상세한검사범위와별도실행기록은보고서를따른다.

**2026-09-14 EffectiveEdge K2K·0.20:** [정확한 Node/Edge 묶음으로 추론](docs/interfaces/EFFECTIVE_K2K.md), 현재 근거·관계 변경 후 유지보수와 재검증을 연결했다. 관련138검사와 실제Terra2회가 통과했으며, 가상 사양의 조건부 계산 결과를 저장했다. [실제 결과](output/t21-effective-k2k/REPORT.md). 다음 작업은 [통합 Electron](progress/T22_unified_electron_execplan.md)과 승인된 [Realm I2K 범위](docs/decisions/REALM_SCOPE.md)다.

**2026-09-14 N2E 관계·0.19:** 현재 Proposition/Observation에 supports·contradicts·qualifies·composes의 생성·독립 검증·semantic Edge Revision·현재 적용성·전파를 연결했다. exact review pending, 대칭 중복 제거, 현재 composes 순환 검사, stale 판정 방지와 원래 모델의 판정 이유를 보존한다. [N2E 계약·CLI](docs/interfaces/N2E_RELATIONS.md), [실행 기록](progress/T20_n2e_completion_execplan.md), [실제 결과](output/t20-n2e-completion/REPORT.md). 추가0017–0019는 새 격리 N2E DB에만 적용하며 사용자 원본 DB와 과거 실행을 보존한다. supersedes의 W2K 권한 소유권, Edge를 전제로 쓰는 K2K/W/P와 Edge embedding 검색은 별도 범위다.

**2026-09-14 의미 변화 기준·0.18:** 사용자의 정정에 따라 새 run은 반복을 관찰만 하고, 독립 materiality/equivalence 판정으로 새 의미 전파를 결정한다. accepted 기준 누적 비교, discovery의 같은 의미 재사용, 근거 maintenance와 applicability 변화 처리를 유지한다. [현재 정책](docs/decisions/MATERIALITY_FIRST_PROPAGATION.md), [실제 검사](output/t19-materiality-convergence/REPORT.md). 아래0.17의 반복 자동 보류는 과거 frozen policy의 동작이다.

**2026-09-14 반복 결과 진단·0.17:** 같은 exact 전제의 A→B→A/A→B→C→A 복귀를 감지해 후속 전파를 멈추고, 정확한 진단 확인과 freshness 검사 후 재개한다. 기존 K·Revision·outbox와 schema0016을 유지한다. [검증 결과](output/t17-propagation-anomaly/REPORT.md), [운영 안내](docs/interfaces/PROPAGATION_WORKER.md). 다음 대규모 의존 관계 paging은 [별도 제안](progress/T18_dependency_paging_proposal.md)이다.

**2026-09-14 전파 worker·Wiki 재검증:** 앱0.16/schema0016에서 [중단·재개 가능한 전파 CLI](docs/interfaces/PROPAGATION_WORKER.md)를 구현했다. 저장된 변경 영향/outbox와 후속 근거 갱신을 처리하고 exact K 재검증, 기존 Revision 재사용, Wiki 전체 I 생성·독립 검증·DB 반영을 이어 준다. [실제 실행 결과와 한계](output/t16-propagation/REPORT.md), [진행 기록](progress/T16_propagation_execplan.md). 기존 원문·과거 Wiki·실제 코드/논문 DB와 Electron 패키지는 유지하며, worker에는 새 이미지와 검증한 DB를 명시한다.

**2026-09-13 사용자 요청 D2K·K 개정 후속:** 앱0.15/UI0.4/schema0014·0015. [독립 D2K](docs/interfaces/D2K.md)는 사용자가 확인한 원문 범위에서만 source-only K를 생성하며 I2K의 자동 우회는 계속 금지한다. [명시적 K 의미 개정](docs/interfaces/KNOWLEDGE_REVISION.md)은 exact target·독립 materiality 판정·과거 이력·변경 영향 의무를 보존한다. [실제 검증 기록](output/t15-manual-d2k/REPORT.md), [실행 계획](progress/T15_explicit_d2k_execplan.md). 아래0.14의 전면 금지는 이 별도 사용자 예외에 한해 후속 승인으로 수정됐다.

**2026-09-13 최신 규약·0.14 구현:** [I2K는 I만 근거로 사용](docs/decisions/I2K_INFORMATION_ERRORS.md)한다. 직접 D→K 예외는 사용자가 철회했다. I가 부족하거나 잘못되면 D2I 정보 오류로 사용자에게 알리고 관련 K를 보류하며 자동 D2I 재실행·원문 K 우회 생성은 하지 않는다. [실제 결과](output/t14-source-issues/REPORT.md),[CLI/UI계약](docs/interfaces/INFORMATION_ERRORS.md),[새UI실행](output/t14-source-issues/ui/Open-Code-Wiki.ps1),[실행계획](progress/T14_source_issues_execplan.md).

**2026-09-13 코드 parser·검토·Wiki 연결:** 앱0.13/UI0.2/schema0013의 [실제 결과](output/t13-code-review-wiki/REPORT.md), [구현/CLI 계약](docs/interfaces/CODE_REVIEW_WIKI.md). 승인 코드 A를 application D2I LLM0회로28 I에 보존했고, 두 I2K 검토에서16개새K·7개재사용, 새K2K1개, 코드Wiki1페이지, 추론을구분한실제검색답변을검증했다. 기존source/자료버전/판정이력은보존한다. [코드 Wiki 실행](output/t13-code-review-wiki/Open-Code-Wiki.ps1)은 별도 연결을 사용한다. [사용자 승인 모델 정리](output/t13-code-review-wiki/model-cleanup.md)로 미사용Qwen/Gemma가중치47.395GiB를제거했고MinerU/BGE/원문·기록은유지했다.

**2026-09-13 공유 원문·자료 버전 후속:** [자료 버전·비교·복원 CLI](docs/interfaces/DATA_VERSIONS.md), [실제 결과](output/t12-versioned-code/REPORT.md), [실행 계획](progress/T07_versioned_code_execplan.md). raw SHA D를 유지하면서 파일 blob을 공유하고 UUIDv7 자료 이력을 추가했다. 두 모듈 전체를 담은 V1/V2의 실제 Terra I2K/N2E/K2K에서25개K·7개Edge·2개추론을저장했고,208개원문/Revision검사와자료A→B→A이력을검증했다. I2K의전체코드의미검토는보류항목을유지한다. 기존202파일D/I와논문/Wiki저장소를보존한다. [전체 코드 저장 측정](output/t12-versioned-code/storage-benchmark/REPORT.md)은증분내용크기와실제파일할당을구분한다. 앱0.12.0을사용하며아래0.11의코드K0개상태는후속실험전결과다.

**2026-09-13 코드베이스 snapshot·K2K:** [원문 코드 D/I](docs/interfaces/CODEBASE_SNAPSHOT.md), [첫 K2K Runtime](docs/interfaces/K2K_RUNTIME.md)을 구현했다. 코드202개 파일을 하나의 exact Markdown snapshot D와204 I로 저장했고, 첫 K2K의 exact premise·추론 origin·재사용·transitive provenance를 합성 PG 검사로 검증했다. 실제 코드 기반 K/추론은 아직0개이며 I2K 입력 준비 상태다. 앱 `palimpsest-inference:0.11.0`/격리 schema0012, 기존 원문/Wiki DB와 Compose default는 유지한다. [실제 결과](output/t11-codebase-k2k/REPORT.md).

**2026-09-13 범용 원문 검토:** 새 전체-source I2K는 보존된 원문 주소와 그 안의 LLM 의미 항목을 검토하고 실제 KRevision까지 연결한다. 특정 논문/패널 수를 하드코딩하거나 I를 재분할하지 않는다. [공통 계약](docs/interfaces/SOURCE_REVIEW.md), [실제 검증](output/t10-source-review/REPORT.md). 앱 `palimpsest-source-review:0.10.0` 전체669 tests는653 pass/16 skip이며 실제 LLM 회수율 평가는 별개다. 기존 Compose 기본 이미지·원본 DB migration은 자동 변경하지 않는다.

**2026-09-13 Electron 첫 UI:** [Palimpsest.cmd](Palimpsest.cmd)로 로컬 데스크톱 앱을 실행할 수 있다. 기존 논문·주제 25개, 인용 I·원본 PDF, 문서 snapshot과 관련 KRevision, 저장된 질문의 검증/보류 이력을 읽는다. Electron44.3.0/PDF.js6.3.289와 기존 Python/Docker read service(앱0.9.0/schema0010)를 연결했다. 새 모델 호출·D2I·canonical 쓰기는 없다. [실행 안내](docs/interfaces/DESKTOP_UI.md), [실물·패키지 검증](output/t09-electron/REPORT.md). 사용자 명시 GUI 착수 범위이며 T12·전체T13 또는 새 질의/편집 기능 완료와 구분한다.

**2026-09-12 검색·답변 후속:** [Wiki/K → I → D 질의 CLI](docs/interfaces/WIKI_QUERY.md)를 구현했다. 고정 BGE-M3의 154개 검색 문서·261개 구간을 PG pgvector에 저장하고 동일 모델 ColBERT rerank, Terra Medium의 구조 답변·독립검증, 요청 시 원본 페이지 확인과 재검토 이력을 연결했다. 현재 image는 `palimpsest-query:0.8.0`, 격리 wiki_pg schema는 0010이다. [실제 성공·보류·수정 내역](output/t07-wiki-query-ui/REPORT.md)과 [Quartz/Wiki.js 등 UI 비교](docs/implementation/WIKI_UI_INTEGRATION.md)를 확인한다. UI 설치·배포와 정식 P/W 계약 변경은 수행하지 않았다.

**2026-09-12 후속 구현:** [Wiki PostgreSQL 저장·복원·K Revision 탐색](docs/interfaces/WIKI_DATABASE.md)을 추가했다. 기존 논문 3편·주제 22개의 문서와 snapshot 27개를 원래 JSON bytes·인용·검토 이력과 함께 별도 실험 DB에 저장했다. K와 원문 근거를 공유하는 탐색 링크 35개를 만들고, 알려진 검토 필요 3개는 기본 조회에서 보류한다. 이는 의미상 `supports` 판정이 아니다. 현재 이미지 `palimpsest-wiki-pg:0.7.0`과 명시적 `--database-name`을 사용하며 원본 source DB와 기존 파일 Wiki는 보존한다. [검증 결과](output/t06-wiki-postgres/REPORT.md), [진행 기록](progress/T06_wiki_postgres_execplan.md).

**2026-09-12 최신 구현:** [논문·주제 Wiki CLI](docs/interfaces/PAPER_WIKI_PROJECTION.md)를 추가했다. 기존 완료 source의 전체 I를 읽어 고정 형식의 논문 페이지를 만들고, 검증된 항목을 출처별로 나눈 주제 페이지와 연결한다. UUIDv7 page ID, immutable JSON snapshots, 검토·실패 이력, Obsidian Markdown export를 제공한다. 이 첫 단계는 canonical D/I를 읽는 비canonical 문서 projection이며 새 K/P/W를 저장하지 않는다. 현재 실험·검사·보류 내역은 [실행 계획](progress/T05_paper_wiki_execplan.md)을 확인한다. 아래 날짜가 더 이른 설명은 당시 구현 상태다.

Wiki 실행에는 `PALIMPSEST_APP_IMAGE=palimpsest-wiki:0.6.0`을 명시한다. 기존 source DB를 사용할 때는 `docker compose ... run --rm --no-deps ... app wiki ...`로 종속 migration을 자동 실행하지 않는다. 저장·본문 교정·인용 보완의 명령과 mount 예시는 위 CLI 문서에 있다.

[실제 Wiki 결과](output/t05-paper-wiki/REPORT.md): Test_Paper·Clarke·Dejani의 전체87 I로 논문 페이지3개와 주제 페이지22개를 저장했다. BMDC를 따로 분류하고 MoDC·Th17의 두논문별근거와snapshot갱신을확인했다. 인용72개·링크73개·원본복원과기존DB전후hash가검증됐으며최종앱555tests는539pass/16skip이다. 의미검증의보류·재편집및수동feedback을포함한실험이고완전자동정확도보장은아니다.

2026-09-11 Markdown 지원: 등록한 UTF-8 `.md`를 heading 기반 그룹 I로 저장하는 [Markdown D2I CLI](docs/implementation/MARKDOWN_RUNTIME.md)를 추가했다. OCR/LLM 없이 원문 byte·문자·줄 범위를 보존하며, 작업 중 작성한54KB문서가 실제 PostgreSQL의24 I로 변환됐다. [실물 검증](output/t03-markdown/REPORT.md). PDF의 기존 MinerU 경로와 과거 FP는 유지한다.

2026-09-11 최신 저장 변경: 새 D2I는 **스크립트로 묶은 I를 영속 저장**한다. 절의 본문·이미지와 exact block/page/range/hash를 함께 보존하고, 머리말·꼬리말·페이지 번호는 별도 한 그룹에 모은다. 세부 block별 I 행은 새로 만들지 않으며 기존 I/ID/hash는 이력으로 유지한다. [새 승인](docs/decisions/GROUPED_INFORMATION_STORAGE.md), [저장 방식과 CLI](docs/implementation/GROUPED_INFORMATION.md), [실행 계획](progress/T03_grouped_information_execplan.md).

2026-09-11 후속 구현: [I2K 입력 준비·원본 PDF 요청 CLI](docs/implementation/T04_INPUT.md)를 추가했다. canonical I의 text/media/provenance를 먼저 구성하고, 입력 hash와 같은 Data에 결속된 요청에 등록 원본 PDF를 로컬 준비한다. [Test_Paper 검증 결과](output/t04-input/REPORT.md), [다음 단계 계획](progress/T04_input_execplan.md). 실제 모델 전달·K 생성·저장은 후속 단계다.

2026-09-11 최신 입력 정책은 **D2I의 스크립트 청킹 → I2K에 I를 먼저 제공 → 원문이 필요하다고 판단되면 등록된 원본 PDF 추가 제공**이다. 초기 I에는 Text I뿐 아니라 Image I 자체의 media/content와 exact provenance도 포함한다. 원본 PDF와 전체 페이지 companion은 자동 동봉하지 않는다. 기존 전체 문서·절·페이지 조회는 보존된 근거를 제공하는 기능이며 실제 모델 전송과 구분한다. [최신 승인](docs/decisions/I2K_I_FIRST_SOURCE_ON_DEMAND.md), [현재 D/I/K/W 구조](docs/implementation/DIKW_CURRENT.md), [읽기 projection](docs/implementation/SECTION_CONTEXT.md)을 따른다. 실제 I2K provider·K/W 실행은 후속 작업이다.

PDF 기본값은 **원본 PDF → 200 DPI 이미지 → MinerU3.4.5 Hybrid high + Pro2605 1.2B OCR**로 유지한다. 새 source I는 OCR 원문을 보존하고 application LLM 없이 스크립트로 원문 단위·읽기 그룹을 구성한다. MinerU 내부 OCR/layout VLM은 이 청킹 LLM 금지와 구분한다. [파서 승인](docs/decisions/MINERU_IMAGE_DEFAULT.md), [이미지 기본값 실행 계획·검증](progress/T03_image_default_execplan.md)을 확인한다. Compose 앱 기본 image는 `palimpsest-markdown:0.2.0`이며 `docker compose build app`으로 현재 코드를 빌드한다.

직전 이중 전사 구현은 `--parser mineru-hybrid-dual`로 남겨 둔다. native 일반 문자/OCR 특수문자의 국소 선택과 양쪽 raw·native text·좌표/hash는 과거 profile 규칙대로 보존한다. 모호한 대응은 review 대상이지만 모든 누락을 자동으로 검출하지는 않는다. [과거 승인](docs/decisions/MINERU_DUAL_TRANSCRIPTION.md), [200 DPI 비교](progress/T03_paddle200_result.md), [이중 전사·PG 검증](progress/T03_dual_transcription_result.md). 아래 수치들은 명시한 과거 실행 결과이며 새 profile의 결과와 구분한다.

새 이미지 기본값 실물 검증: Test_Paper14페이지, source I229개(Text193/Image36), 전체 Figure companion6개, 격리 PG18.6/pgvector0.8.6 저장·동일 ID 재시도 통과. 원본 페이지 PNG14장은 실제 OCR 입력과 byte-identical하다. [PG 검증](output/t03-image-default/store/verification.json), [근거 패키지](output/t03-image-default/evidence/README.md), [원문 재현 검증](output/t03-image-default/evidence-review/verification.json). 앱307tests(16skip)와 별도 native PDF22tests가 실패 없이 끝났다. 원문 전사 전체의 충실성 승인이나 I2K 실행은 아니다.


2026-09-10 직전 단독 Hybrid 실행 기록: 새 D2I 기본값은 **MinerU 3.4.5 Hybrid high + Pro2605 1.2B / local Transformers**다. 병합 전 페이지·span의 원문 I를 보존하고, PDF 글꼴 기반 소제목 후보·전체 Figure/페이지 이미지·전사 차이·페이지를 넘는 문단은 별도 읽기 projection으로 제공한다. Test_Paper의 새 GPU 실행에서 격리 PG18에 **229 I(Text193/Image36)**를 저장했고, 전체 Figure 6개와 페이지 14개를 확인했다. 추가 3편을 포함한 43페이지의 기존 누락 제목 39개 중 32개를 정확한 후보 경계로 수집했다. application semantic LLM 호출은 0이며 parser 내부 VLM 전사는 사용한다. [최신 결과](progress/T03_pdf_evidence_result.md), [사용법](docs/interfaces/PDF_EVIDENCE.md). 아래 189 I/202 tests는 이전 실행 기록이다.

> 2026-09-09 · 사용자 변경 U01–U11를 반영한 설계 문서와 Python/Docker D→D2I→I CLI 구현. 제공 PDF의 실제 시험을 마쳤으며 T03 전체 acceptance와 이후 지식 단계는 미완료다.

## 실행 가능한 범위

Python CLI·Docker·PostgreSQL 18.6/pgvector 0.8.6 기반 Data 등록/조회/검증/복구와 원문 보존 D2I를 구현했다. **U11에 따라 D2I의 원문 조립·청킹·구조 검사는 application LLM 호출 없이 작동한다.** Test_Paper.pdf의 기존 MinerU 3.4.5 결과를 재사용해 **source I 189개(Text182/전체Figure6/로고Image1)**를 저장했다. 14페이지의 원문249블록을 빠짐없이 연결하고 위치·raw 구조·이미지·해시를 보존했다. 전체 앱 테스트202개 통과. [source 결과](progress/T03_source_result.json), [전체 I 출력](output/t03-source/INFORMATION.md), [실행 기록](progress/T03_execplan.md), [실행 안내](docs/implementation/T03_RUNTIME.md)를 참고한다.

[페이지별 읽기 출력](output/t03-pages/PAGES.md)과 [앞뒤 페이지 문맥](docs/implementation/PAGE_CONTEXT.md)을 추가했다. 기존 I는 그대로 두고 MinerU index 순서의14페이지 조회를 제공한다. 중앙페이지±1 문맥은 주 처리 대상/참고 I와 창 밖 근거 페이지를 명시한다. [실행 결과](progress/T03_page_result.json).

기존 LLM 실험28개와 Figure 정정6개는 별도 immutable 이력이다. 새로운 source I는 semantic_type=null, source_structure 검증이며 의미의 참·거짓을 판정한 결과가 아니다. I2K는 실행하지 않았다.

```powershell
docker compose -p palimpsest-dev build app
docker compose -p palimpsest-dev up -d db
docker compose -p palimpsest-dev run --rm migrate
docker compose -p palimpsest-dev run --rm app doctor --json
```

입력 폴더를 읽기 전용 mount하고 `app data import <container-path> --json`으로 등록한다. Data ID는 보존 bytes의 SHA-256이며 신규 opaque ID는 UUIDv7이다. 일반 중복은 exit 6, 같은 성공 요청의 재시도는 원래 결과를 반환한다. T03 host worker는 별도 로컬 MinerU Docker와 스크립트 기반 source materialization을 연결한다. 앱 컨테이너의 `doctor`는 아직 이 외부 worker의 readiness를 검사하지 못해 parser 미구성 경고를 출력한다. 실제 parser 상태는 T03 profile/실행 결과를 따른다. K/W/P/B·GUI는 아직 구현하지 않았다. T02 당시 결과·등록 안내는 [T02 실행 기록](progress/T02_execplan.md)과 [T02 실행 안내](docs/implementation/T02_RUNTIME.md)에 보존했다.

## 이번 변경

현재 interface는 **CLI 우선**, **GUI는 마지막 T13**이다. T02부터 기능별 CLI를 붙이고 T11에서 검토/운영 workflow를 완성하며 T12에서 headless release를 검증한다.

PDF D2I parser는 **MinerU**다. parser output은 비canonical 파생물이며 원본 grounding과 D2I validation을 통과해야 Information이 된다. 다른 parser로 조용히 fallback하지 않는다.

구성요소명은 **Artifact Store (`artifact_store`) / Canonical Store (`canonical_store`) / Compiler Runtime (`compiler_runtime`)**이다. D-I-K-W-P-B와 책임은 유지한다.

[USER_OVERRIDES](docs/decisions/USER_OVERRIDES.md)에 승인 범위를 기록했다. 후속 U04는 embedding `BAAI/bge-m3`(dense 1024)와 같은 모델의 multi-vector ColBERT 점수 재순위화를 기본으로 선택하고, U05는 MinerU 최신 안정판을 선택한 뒤 exact runtime profile을 기록하도록 한다. P01–P12의 나머지 보완안은 여전히 proposed다.

Embedding과 Reranker는 독립 교체 가능하도록 설계한다. 향후 Qwen3-Embedding/Reranker 4B·8B는 지원 후보이며, [profile 경계](docs/interfaces/RETRIEVAL_PROFILE.md)에 dimension·scoring·재색인 요구를 기록했다.

U06의 모듈화와 U07의 K2W 명칭에 따라 D/I/K/W/P/B domain과 D2I/I2K/N2E/K2K/K2W/W2K, W2P/P2B 작업을 각각 모듈화한다. [모듈 책임·입출력·의존성](docs/implementation/MODULE_BOUNDARIES.md)에 단계별 구현 범위를 기록했다. 저장·전파·atomic commit은 공유한다. T02는 Data·파일 저장·DB·서비스·CLI의 실제 모듈을 만들었으며 미래 단계는 해당 작업에서 구현한다.

## 시작

[Codex 시작 안내](codex/START_HERE.md), [복사할 프롬프트](codex/PROMPTS.md), [문서 인덱스](docs/INDEX.md), [CLI 계약](docs/interfaces/CLI_CONTRACT.md), [MinerU adapter](docs/interfaces/MINERU_ADAPTER.md)를 읽는다. 이미 작업 중이면 PROMPTS의 ‘이번 변경만 적용’을 사용하고, 처음 시작이면 T00만 지시한다.

## 현재판과 원본

[현재 통합 canonical](docs/canonical/PALIMPSEST_CANONICAL_MODEL.md)과 13개 current slices는 `docs/canonical/current_map.json`으로 검증된다. `docs/source/`에는 수정 전 원본과 13개 exact baseline slices를 별도로 보존했다. review와 원본 invariant의 줄 번호는 archived source 기준이다. source와 current를 혼동하지 않는다.

26개 검토 항목, 12개 P 제안과 8개 보완 계약을 유지하며 U01–U11의 명시된 범위만 우선 적용한다. 초기 acceptance는 105개였고 U08에서 AT106/AT107, U09에서 AT108–AT112를 더해 현재 112개다. 기존 합성 fixture 12개와 별도로 T02 SQL constraint fixture를 작성했고 T02에서 독립 PostgreSQL로 실행했다. T03은 이전 의미 실험 및 U11의 한 native PDF source 변환·DB 경로와 별도 회귀 검증을 추가했으며 전체 acceptance 완료를 뜻하지 않는다.

## 기존 프로젝트에 넣을 때

별도 폴더에서 충돌을 비교하고 필요한 파일을 병합한다. 기존 AGENTS/README/PLANS/code/manifests/user changes를 덮어쓰지 않는다. 새 이름이 선택되었다고 live schema/physical directories를 바로 rename하지 않는다. 기존 GUI는 삭제하지 않고 동결한다. API keys/외부 전송/실제 사용자 DB는 별도 권한이다.

## 검증 도구

```text
python tools/validate_bundle.py
python -m unittest discover -s tools -p "test_*.py"
python tools/reassemble_canonical.py --output current_reassembled.md
python tools/reassemble_canonical.py --baseline --output baseline_reassembled.md
```

reassemble은 기존 output file을 덮어쓰지 않는다. current가 기본이며 --baseline은 수정 전 원본이다. 결과를 [PACKAGE_VERIFICATION](PACKAGE_VERIFICATION.md)에 기록했다. 이 도구는 문서·분할·link·ID·요구 정책의 일관성을 검사하며 실제 CLI/MinerU/DB/LLM 기능 테스트가 아니다.

## 구조 검토 후 수정

U08로 R01–R06/R09의 current-state/dependency/completion/commit/identity/Decision/retrieval 계약을 고쳤다. [구체 해결 계약과 선택 근거](docs/decisions/ARCHITECTURE_FIXES.md), [항목별 상태](docs/decisions/architecture_fixes.json)를 따른다. R07은 늦은 결정 요청 재확인, R08은 기각 exact scoped FP 조회로 사용자 승인을 받아 적용했다. 실제 앱 구현과 별개인 설계 수정이다.

U09로 PostgreSQL 초기 18/pgvector, Data=원본 bytes SHA-256·기타 신규 opaque ID=UUIDv7, 도구 관리 등록·중복 거부와 검증된 효과의 canonical 반영을 확정했다. [저장 계약](docs/decisions/STORAGE_IDENTITY.md)과 [T02 SQL 초안](docs/schema/T02_STORAGE_SCHEMA.md)을 따른다. 영속 판정 Record는 Runtime에 남는다. 원래 SQL 초안과 T02의 `0001_data`를 보존하고 T03에서 별도 `0002_information` migration을 추가했다. D2I Record·I·grounding·후보 정리·outbox의 atomic 반영을 실제 PostgreSQL로 검증했다.

U10으로 앱 언어 Python과 Docker 기반 실행·배포를 확정했다. T02에서 승인 실행 경로로 image pull/build·독립 컨테이너·DB 연결·CLI 실행까지 검증했다. [실행 환경](docs/implementation/ENVIRONMENT.md)은 과거 접근 관찰과 현재 profile을 구분한다.


U11은 원문 보존 D2I와 I2K 이후의 구조화된 LLM 후보를 분리했다. [승인 계약](docs/decisions/D2I_SOURCE_PRESERVATION.md)을 따르며 ID·중복/재사용·근거·검증·atomic 저장은 애플리케이션이 담당한다. 새 0003_source_information migration은 기존 0001/0002와 이전 I/Record를 변경하지 않고 source 표현을 추가한다.

## Test_Paper K graph 실험 (2026-09-11)

[실제 I2K/N2E 결과](output/t04-knowledge/REPORT.md): Terra Medium과 기존 22개 I를 이용해 KNode 27개, KEdge 21개 및 각각의 exact Revision을 PostgreSQL에 저장했습니다. 성공 DB는 Compose 프로젝트 palimpsest-knowledge에 보존되어 있습니다. [CLI/저장 계약](docs/implementation/KNOWLEDGE_RUNTIME.md)과 [독립 의미 감사](output/t04-knowledge/semantic-audit.md)를 참고하세요. 전체 논문 coverage와 K2K 전파 완료를 뜻하지 않습니다.

## 전체 source I 선택과 양방향 원문 조회 (2026-09-11 최신)

[구현·실험 보고서](output/t04-full-selection/REPORT.md): 원본 PDF 14쪽을 36개 I로 보존하고 D↔I 위치 조회·원본 exact 복원을 확인했습니다. 전체 I를 Terra Medium이 검토해 중요성을 선택하고 일반 명제 재사용과 다른 Data의 실험 K 보존을 검사했습니다. 실제 Test_Paper graph는 K 32개·Edge 26개이며 모든 Revision과 이력을 DB에 보존합니다. [CLI 안내](docs/implementation/FULL_SOURCE_SELECTION.md)를 참고하세요. 기본 Docker 앱은 palimpsest-selection:0.4.0입니다.
