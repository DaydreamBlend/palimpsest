# Development status

2026-09-10 이미지 전용 전사 비교 완료: 이전17편의 고정51페이지를200DPI text0 image-only 입력으로 만들어 같은 Hybrid high/Pro2605에서 실행했다. Parser/source 구조 검증17/17, 제안631개(Text586/Image45), strict 전사32/51→41/51, 제목48/74→50/74다. 알려진 Greek5건과 오류페이지의 micro 단위16곳은 이미지/LaTeX 표현으로 복구됐으나 OVA-RMA 하이픈 소실1건과 paper10 F5 라벨 crop 잘림이 남았다. raw Figure 단일crop 전체15/19·crop집합16/19는 이전 numberedFigure 연결 지표와 구분한다. 원본·이전115파일/production/profile 불변, Docker7/13/27 동일·새이미지0·실험컨테이너0, application semantic LLM/canonical/사용자DB쓰기0이다. [상세 보고서](T03_image_transcription_result.md), [JSON](T03_image_transcription_result.json), [계획](T03_image_transcription_execplan.md). 전체문서검사는 raw source.md 단독pipe의 table 판정 오류1건으로exit1이며원시파일을수정하지않았다. 제품 기본값은 바꾸지 않았고 T03 in_progress/T04이후미실행 상태를 유지한다. 아래는 이전 코호트의 기록이다.

2026-09-10 추가 코호트 평가 완료: 현재 Hybrid high + Pro2605 1.2B 구현을 고정해 **새 논문17편243페이지**를 실행했다. 파싱/source 제안 검증17/17, 제안2,834개(Text2,599/Image235), 근거 package·전체 context 조회16/17이다. Manfredi는 CropBox 불일치로 거부됐으며 실패를 분모에 유지했다. 고정51페이지의 Figure16/19, parser 전사 exact32/51, native 제목 exact25/74와 후보 precision25/168을 기록했다. Figure 실패3개는 옆 caption 연결2개와 근거 package 실패1개로 raw 그림은 보존돼 있다. [전체 보고서](T03_expanded_papers_result.md), [JSON](T03_expanded_papers_result.json), [계획](T03_expanded_papers_execplan.md). 원본·고정 코드·oracle 해시54건과 Docker 기존 컨테이너7/이미지13/볼륨27의 동일성을 대조했다. 새 이미지0, application semantic LLM/DB 쓰기0, T03 in_progress 유지. 아래 수치는 이전 코호트·실행 시점의 기록이다.

2026-09-10 최신 사용자 승인 보완 완료: 새 기본 parser를 **MinerU3.4.5 Hybrid high + Pro2605 1.2B / local Transformers**로 연결했다. source I의 병합 전 page/span을 보존하고 native PDF 제목 후보·전체 Figure/페이지·전사 차이·문단 통합은 별도 projection이다. 4편43페이지에서 기존 누락 제목39개 중 정확한 후보32개, Test_Paper Figure6개/페이지14개를 확인했다. 새 GPU 파싱216.355초, 격리 PG18에서229I(Text193/Image36)·동일재생·중복Data거부·raw66파일복구를 검증했다. 최종앱241tests/26.205초/exit0(skip8은 native 이미지에서 별도 통과), native PDF19tests/0.298초/exit0, 문서도구44tests/221.099초/exit0. 전사차이301개는 검토 신호이며 교정 완료가 아니다. [결과](T03_pdf_evidence_result.md), [기계판독 결과](T03_pdf_evidence_result.json), [계획](T03_pdf_evidence_execplan.md). 시험 컨테이너3개·network1개를 정리하고 모델·볼륨·기존서비스를 보존했다. application semantic LLM 호출0, 사용자DB쓰기0, T03 in_progress와 후속 task 상태를 유지한다. 아래는 이전 비교/실행 당시의 기록이다.

2026-09-10 Hybrid+Pro 비교 완료: MinerU 3.4.5/Hybrid high/Pro2605 1.2B를 4편 43페이지에서 실행했다. 같은 고정 평가에서 추가 3편의 정확한 제목 경계는 Pipeline 11/54·Paddle 13/54·Pro 12/54이며 기존 누락 39개 복구는 모두 0이다. Pro는 Figure 5의 전체 crop을 보존했지만 Figure 6H 범례 잘림과 캡션 과학 표기 손실이 남았다. 페이지 provenance는 문단 병합 전 `preproc_blocks`를 기준으로 보존한다. 사용자 DB/canonical 쓰기 0, 제품 기본값 추가 변경 없음. [상세 보고서](T03_mineru_hybrid_experiment.md), [비교 JSON](../output/t03-mineru-hybrid-pro/evaluation/comparison.json). 전체 16개 실험/시험 컨테이너를 정리한 뒤 원래 7개 컨테이너·모든 볼륨 보존을 확인했다. 문서 fixture의 대용량 복사를 수정하고 44tests/213.159초/exit0를 확인했다. T03는 in_progress다. 아래 추가 비교 진행 문장은 당시 시작 기록이다.

2026-09-10 추가 비교 진행: 사용자가 **MinerU Hybrid + Pro 1.2B도 시험**하도록 요청했다. [별도 실행 계획](T03_mineru_hybrid_execplan.md)에 따라 공식 Pro2605 원본을 다운로드·검증하고 기존 MinerU3.4.5 CUDA 이미지에 최소 의존성만 더했다. 이전 MinerU도 RTX4060Ti/CUDA의 Pipeline 실행이었다. Hybrid 비교 요청만으로 제품 기본값이나 사용자 canonical I를 변경하지 않는다.

2026-09-10 PaddleOCR-VL-1.6 비교 완료: 4편43페이지, source 제안907개(Text737/Image170)의 raw→I 구조 검사 통과. 그러나 기존 소제목 누락39개 중 독립 제목 복구0개이며, Test_Paper Figure6/캡션8조각은 남았지만 Figure5/6 일부 crop 잘림과 Wallet 과학 표기 오독을 확인했다. SDK 기본 text merge의 좌표 오류는 비활성화/검증 거부로 해결했다. 실제 Test_Paper308I 저장·중복 Data 거부·같은 ID 재시도·14페이지 조회·125파일 exact export를 **격리 PG18 시험 DB**에서 확인했다. 사용자 개발DB 이력은 불변이다. 최종 앱210tests/35.590초/exit0, [상세 보고서](T03_paddleocr_experiment.md). 완료된 실험컨테이너8개+시험프로젝트3개/network1개를 정리했고 모든 볼륨·모델·raw·기존 서비스를 보존했다. 이 결과는 T03 전체 acceptance 완료나 파서 원문 충실도 승인이 아니다.

2026-09-10 현재 선택: 사용자 승인에 따라 **제목 계층 보조 모델을 Qwen3.5-4B Q4_0, thinking2048으로 확정**했다. [현재 profile](../docs/implementation/HEADING_MODEL_PROFILE.md)과 실행 도구 기본값에 반영한다. 아래 E4B/BF16 선택 문장은 각 실험 당시 기록이다. 새로운 source D2I/DB 변경이나 모델 재평가는 이번 기본값 변경에 포함하지 않는다.

2026-09-10 KST: **공식 Qwen3.5-4B 원본 BF16/F32 + thinking 2048의 새 논문 평가를 완료했다.** Nassar/Torchinsky/Wallet9회는 전달된후보 level·role·부모판정17/17, 실제간선12/12이며 각문서3회동일했다. 기존Test_Paper대조3회는level23/23·간선22/22·role26/27로ONLINE METHODS역할오류가반복됐다. 새원문에서명확한제목54개중15개만title입력에포함됐으며, 누락내용은raw text에보존돼후보선택문제로분리했다. [상세 결과](T03_qwen35_original_experiment.md), [계획](T03_qwen35_original_execplan.md), [12회 점수](../output/t03-qwen35-original/scores.json). 공식원본과직접변환한8.67GB모델을보존하고,실험컨테이너6개/network1개정리·새이미지0·기존자원불변을확인했다. 앱·canonical I·DB·공유harness는변경하지않았다. 아래과거기록은유지한다.

후속 **Qwen3.5-4B 실험을 완료했다.** 기존3편/v2/온도0/seed42에서 thinking 예산2048·전체출력4096 조건이9/9회 유효, level77/77·parent74/74·그림표제제외3/3이며 문서별3회 동일했다. 중앙 지연13.26–13.77초로 기존 E4B15.66–19.02초보다 짧았다. 예산 없는thinking은9회 모두 미완료, non-thinking은6/9회 유효였으므로 설정을 분리해 해석한다. [상세 결과](T03_qwen35_experiment.md), [계획](T03_qwen35_execplan.md), [전체27회 점수](../output/t03-qwen35/scores.json). 새 이미지0개, 실험 컨테이너·network정리 및 기존 자원 보존 대조 완료. 본 앱/canonical I/DB/기존 도구 기본값은 변경하지 않았다. 아래 과거 실험과 테스트 기록은 그대로 보존한다.

후속 **Gemma4 12B 실험도 완료했다.** QAT Q4_0약6.98GB를RTX5080 16GB에서정상실행했고GPU전체표본은약9.4GiB였다. 현재조건에서12B non-thinking은레벨66/77·부모63/74, thinking예산2048은68/77·65/74로E4B보다낮았다. thinking무제한은출력4096/6144한도를소진해미완료6건으로기록했다. 전체57회중구조유효51/미완료6이며추가thinking예산시험은문서별1회다. [통합보고서](T03_heading_experiment.md), [전체점수](../output/t03-e2b/final-all-model-scores.json), [12B프로필](../output/t03-e2b/runtime-profile-12b.json). 실험defaultE4B를유지하고canonical I·앱/DB는변경하지않았다. 시험서버와네트워크는모두정리했으며기존Docker자원은보존했다.

추가 실험: **Gemma4 E2B와 승인된 E4B의 제목 계층 비교를 완료했다.** 3편/39회 local 추론에서 JSON 구조는 모두 유효했지만 의미 오류는 남았다. 같은 structured-v2/thinking 조건에서 E2B는 실제제목77/77·부모74/74, MCM 그림표제 제외0/3; E4B는75/77·72/74·그림표제 제외3/3이었다. 후속 실험 도구의 기본값은 E4B이며 source D2I·canonical I·앱/DB 변경은 없다. [상세 결과와 한계](T03_heading_experiment.md), [실험 계획](T03_e2b_execplan.md). 아래202개 앱 테스트는 기존 페이지 구현 때의 결과로 이번 실험에서 재실행한 수치가 아니다.

현재 추가 기능: **페이지별 조회·LLM 입력 projection**을 구현했다. 기존189 source I/249원문블록은 유지하며 읽기 단위는14페이지다. MinerU index 정렬, 정확한 문자offset, 전체Figure6+로고1, 중앙±1페이지와 단일I소유권 및 창 밖 근거 표시를 제공한다. 새 canonical row0/LLM0회, 기존223개 I 이력 불변, 반복 조회 동일을 실제 CLI에서 확인했다. 최신 전체 앱 테스트는202개/24.832초/exit0/skip0이다. [페이지 결과](T03_page_result.json), [읽기 출력](../output/t03-pages/PAGES.md). 아래190개 시험은 source 생성 당시의 검증 기록이다.

갱신일: 2026-09-09. 현재 작업은 **T03 in_progress**다. U11은 D2I를 원문 보존 스크립트 변환으로 확정했고 LLM 사용을 I2K부터 적용한다. 제공 PDF의 새 D→D2I→I 실물 시험을 완료했다. T02 completed, T01 후속 계약 in_progress, T04–T12 planned, T13 deferred다. Git repository는 초기화되지 않았다.

새 execution `01a0856e-5610-70bd-9858-e03684a995b0`, generation3, profile source-d2i-v1은 completed다. 기존 MinerU3.4.5/local pipeline 파싱14페이지·249blocks·63crops를 exact 재사용해 **source I189(Text182/전체Figure6/로고Image1)**를 PostgreSQL18.6/pgvector0.8.6에 저장했다. 원문249+Figure primary6의 grounding255, source Record189, 후보0, pending I2K outbox189이다. LLM 호출0회이며 I2K/K는 실행하지 않았다.

기존 의미 실험28 I와 Figure 정정6 I, 총34개 snapshot은 변경되지 않았다. DB에는 역사와 새 source를 합해223 I가 있다. 자동 supersession/current view는 아직 없으므로 다음 단계는 새 source execution refs를 명시적으로 소비해야 한다. source I는 semantic_type=null, unit_type별 원문 표현이며 semantic_checked=false다.

최종 앱 회귀: **190 tests /27.582초/exit0/skip0**. 실제 PG18에서 rollback/retry·원문변조·파생이미지손상·공개 LLM profile 거부를 검증했다. 실물 QA는 원문 block hashes249·내부content fields1173·groundings255·보존파일79를 대조했고 재실행의 job/I IDs/events가 동일했다. [결과](T03_source_result.json), [실행 계획](T03_execplan.md), [독립 QA](T03_source_unit_expectations.json), [전체 I 출력](../output/t03-source/INFORMATION.md), [실행 안내](../docs/implementation/T03_RUNTIME.md).

문서 bundle 검사 오류0, 문서 도구43tests/115.940초/exit0도 별도로 통과했다. 변경 목록은 [T03_changes](T03_changes.json)에 있다.

Application acceptance112개는 기존9 passed/28 partially_tested/75 spec_only를 유지한다. 한 native PDF의 reviewed Figure map으로 범용 grouping·scanned/mixed PDF·완벽한 OCR을 입증하지 않는다. 원문 인식 차이4건을 QA로 보존했다. reconciliation/supersession/invalidation/보류 해결/일반 대형문서/worker scheduler·fencing 및 후속 K/W는 아직 남아 있다.

Docker 정리의 최종 추가 단계에서 시험 컨테이너2개와 network1개를 제거했다. 개발DB1개와 최종 앱/MinerU/PG18 이미지를 남겼고 모든 볼륨·다른프로젝트 컨테이너를 보존했다. 정리 후 원본hash도 정상이다. 이전 삭제 내역과 이번 단계를 [정리 기록](T03_docker_cleanup.json)에서 구분한다.

## T02 완료 당시 상태 — 역사 기록

아래 부재·미실행 및 다음 작업 표기는 T02 시점의 관찰이다. 현재 상태는 위 T03 결과를 따른다.

갱신일: 2026-09-09. T02 Data vertical slice를 완료했다. 설계 문서·문서 도구와 Python/Docker CLI·실제 DB/파일 테스트가 있다. Git repository는 초기화되지 않았다.

Current task: T02 completed (이번 작업 경계). Next task: T03 planned. T01 in_progress (후속 K/W 계약의 미정만 유지). Completed application tasks: T02.

Effective user changes: U01–U10 accepted within recorded scope — CLI-first/GUI-last, PDF D2I=MinerU, 영어 구성요소명, BGE-M3 embedding/multi-vector reranking 및 독립 모델 교체 경계, MinerU 최신 안정판 선택 정책, D/I/K/W/P/B 및 변환별 모듈화, K2W/k2w 명칭, R01–R09 구조 수정, PostgreSQL 초기 18/pgvector·raw SHA-256 Data/신규 opaque UUIDv7·도구 관리 등록·검증된 효과의 atomic 반영과 영속 Runtime Record 보존, Python 앱·Docker 실행/배포.

P01–P12: 나머지 전체 계약은 proposed. U04/U05는 모델/버전, U06은 모듈화, U08은 구조 수정, U09는 DB/ID/등록·반영, U10은 Python/Docker의 명시된 조항만 적용하며 P 전체의 일괄 승인이 아니다.

T00: completed (inventory). T01: in_progress (T02 Data/실행 profile 선행 범위 충족, 나머지 계약 미완료). T02: completed. T03–T12: planned. T13: deferred (T12+후속 GUI 착수 지시 필요).

Application acceptance: 112개 중 7개 passed, 4개 partially_tested, 101개 spec_only. 실제 테스트 코드 52개 통과(8.817초), 빈 독립 PG18 SQL constraint fixture 통과/ROLLBACK, migration 재실행 applied=false. PostgreSQL 18.6/pgvector 0.8.6 관찰. 실제 MinerU PDF·전체 DIKWPB e2e·live semantic evaluation·전체 backup/restore는 미실행이다. [T02 실행 기록](T02_execplan.md)에 AT별 실제 범위와 결과를 기록했다.

Python 3.12.14/psycopg 3.3.5, CLI `palim`, image digest·dependency lock·Compose·migration `0001_data`를 구현했다. 사용자 원본을 복사 등록하고 동일 bytes 새 요청 거부/동일 성공 요청 재생/중단 복구를 실제 파일·DB로 검증했다. [실행 안내](../docs/implementation/T02_RUNTIME.md)를 따른다.

T02 문서 validator errors 0/exit 0, 문서 도구 unit/mutation 39개 pass(40.805초). 변경은 새 파일 26개·기존 12개·삭제 0개이며 기존 canonical/원본/SQL/승인 자료는 보존했다. 검증 후 전용 `palimpsest-t02-test` DB 컨테이너를 중지하고 volumes는 남겼다. 개발용 `palimpsest-dev` project는 아직 생성하지 않았다.

## 이전 단계 실행 기록

아래 T00/T01/U09/U10의 부재·미실행 관찰은 각 당시 결과다. 이후 T02 검증으로 대체된 현재 상태는 위와 같다.

후속 산출물: [D/I/K/W 저장 스키마 v1](../docs/schema/DIKW_STORAGE_SCHEMA_V1.md) review draft를 작성했다. ERD·자료형/typed refs·D/I/K/W/Runtime/검색 profile·atomic commit·migration 순서·관련 AT 및 미정을 연결한다. 물리 단일 commit gate와 추가 내부 테이블은 검증 전 구현안이다. 공개 K 재검증 이름/전체 effect matrix 등 미정은 활성 enum으로 만들지 않았다.

Package checks: T00 당시 도구 unit/mutation test 26개, T01 모델 정책 반영 후 31개, U06 모듈 정책 반영 후 33개. U07 명칭 반영 후 33개(20.922초), U08 위임 수정 후 35개(26.185초), R07/R08 승인 반영 후 승인 경계 mutation을 포함한 **35개 테스트 통과**(24.851초). validator exit 0/errors 0, 구조 설계 해결 9개/선택 대기 0개. 번들 Python 3.12.14 절대 경로와 명령/결과는 [T01 실행 기록](T01_execplan.md)에 있다.

U09 검증: 문서 validator exit 0/errors 0, 도구 unit/mutation **38개 pass**(35.172초). PostgreSQL 적용·SQL fixture 실행은 psql 부재/Docker engine 접근 거부와 미정 실행 profile로 미실행이다.

U10 검증: 문서 validator exit 0/errors 0, 도구 unit/mutation **39개 pass**(37.785초). 일반 sandbox의 Docker 접근 거부 이후 승인 실행 경로에서 engine 29.7.2/Linux x86_64, Compose 5.5.1 조회에 성공했다. 컨테이너 생성·image pull·PostgreSQL 연결·SQL fixture·앱 실행 검증은 수행하지 않았다.

저장 스키마 v1 검증: 문서 validator exit 0/errors 0, 기존 도구 unit/mutation **39개 pass**(38.597초). 두 독립 검토에서 event 성공 유일성·retry 순서·검색 snapshot FK·worker commit fencing·fan-in cause·root 필수 참조의 여섯 누락을 문서 수준에서 보완했다. 기존 canonical/원본/SQL과 112개 spec_only 상태는 보존했으며 PostgreSQL 통합·앱 테스트는 미실행이다.

## 실제 관찰

- [Repository inventory](repository_inventory.md)에 실제 경로/누락 모듈, 하드웨어·도구, MinerU readiness와 공식 자료, 제한·승인 대상을 기록했다.
- AT64는 T00 수동 검토, AT88은 문서 명칭 및 policy 검증으로 구분했다. AT102 실제 CLI doctor는 부재로 미실행이다.
- MinerU 실행 파일/모델 profile 미준비. T00 당시 Docker engine/WSL/uv managed runtime은 접근 제한으로 unknown이었다. U10에서 Docker engine은 승인 실행 경로로 조회에 성공했으며 WSL/uv는 재검증하지 않았다. 사용자 설정/DB 변경이나 외부 원문 전송 없음.

## T01에서 반영한 선택

- Embedding: `BAAI/bge-m3`, 공식 dense dimension 1024.
- Reranker: 같은 `BAAI/bge-m3`의 multi-vector ColBERT late-interaction 점수. 전용 bge-reranker-v2-m3는 선택하지 않음.
- 두 역할은 독립 교체 가능. Qwen3-Embedding/Reranker 4B·8B는 향후 후보이며 미설치·미구현. dimension/score/profile 차이와 파생 projection 재생성은 [RETRIEVAL_PROFILE](../docs/interfaces/RETRIEVAL_PROFILE.md)에 기록함.
- MinerU: 설치/명시적 업그레이드 시 최신 안정판 선택 후 exact version/profile 기록. 2026-09-09 PyPI 관찰값은 3.4.5이며 실제 설치 버전이 아님.
- U06: D/I/K/W/P/B domain 6개, Compiler 변환 6개와 W2P/P2B publication 모듈 2개를 분리하는 [모듈 계약](../docs/implementation/MODULE_BOUNDARIES.md)을 작성함. 공통 실행/전파/atomic commit과 W2K 결정론성은 유지. 실제 앱 모듈은 아직 없음.

- U07: 현재 Operation/모듈 명칭을 K2W/k2w로 통일함. KGraph + Query + Context 입력·Wisdom 생성 의미와 원본 인용/이력은 유지. current full/slices/map, task/명세/정책 검사 동기화 및 검증 완료.

## 전체 구조 검토

[T01 현재 구조 검토](T01_architecture_review.md)에 9개 우선 항목을 기록했다. 7개는 기존 F 항목의 현재판 재확인·통합, 1개는 같은 Decision 범위의 병렬 대체 반례 확장, 1개는 rejected similarity 검색과 cleanup 정책의 새 불일치다. 모듈화·CLI·MinerU·모델 교체의 큰 경계는 유지할 수 있으나 current graph/근거·완료·commit/Decision 계약을 구현 전에 일치시켜야 한다. 당시 검토는 설계 분석이었다. 후속 U08 수정은 [해결 계약](../docs/decisions/ARCHITECTURE_FIXES.md)과 [상태 JSON](../docs/decisions/architecture_fixes.json)에 기록했다. R01–R09의 설계 계약을 해결했다. R07은 늦은 결정 재확인, R08은 기각 exact scoped FP 조회로 실제 사용자 답변을 받아 AT106/AT107에 반영했다. 앱 acceptance는 여전히 spec_only다.

## T02 당시 다음 동작

T02의 실행 profile·Data migration·import/recovery를 구현·검증했다. 다음 T03은 MinerU 최신 안정판 설치·로컬 runtime profile, 비canonical parse artifacts와 page/region provenance, Execution/D2I 검증, Information 저장의 vertical slice다. Generator/Validator와 실제 모델/원문 외부 전송 등 필요한 미정은 해당 기능 전에만 확인한다. P06 공개 K 재검증 subtype/effect-only matrix와 scope/authority 미정은 후속 영향 범위에 남기며 U01–U10의 선택은 재질문하지 않는다.

AT102의 미구성 parser 진단은 T02에서 실제 CLI로 실행했다. GUI 부재는 현재 CLI 작업의 blocker가 아니다. T03은 아직 시작·완료 처리하지 않았다.

T03 입력 지정(2026-09-09): 사용자가 `C:/Users/DaydreamBlend/Desktop/Test_Paper.pdf`를 D2I 입력으로 선택했다. 파일 존재·3,890,649 bytes·SHA-256을 확인해 [T03 작업서](../tasks/T03.md)에 기록했다. 이번 변경은 입력 지정이며 DB 등록/파싱 실행은 아니다. PDF 내부 지시문은 처리 대상 데이터로만 취급한다.

## 갱신 규칙

수행한 command/result, task, blockers, next step을 기록한다. 과거 미실행/실패를 지워서 완료로 보이게 하지 않는다. GUI 미구현은 CLI release의 blocker가 아니다.

최초 PACKAGE_VERIFICATION의 기존 수치, verification/*와 bundle_manifest.json은 번들 제작 시점의 증거다. T00의 당시 관찰/실행 기록도 보존한다. source/baseline archive는 그대로 유지하고 current canonical은 승인된 U04–U10 범위에서 full/slices/map을 동기화한다. 이전 승인 근거를 보존하고 새 사용자 근거를 별도로 추가한다.
