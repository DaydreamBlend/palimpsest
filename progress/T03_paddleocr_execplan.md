# T03 — PaddleOCR-VL-1.6 전환 검증

2026-09-10 시작. 사용자: “1번이 그림 인식/분리 기능 있다면 1번으로 진행해줘”.
공식 PaddleOCR-VL 문서의 layout crop 및 Markdown image export 지원을 확인했다.
이 후속 지시가 이번 parser 선택에서 이전 U02/MinerU 선택보다 우선한다.
원문 보존, Python/Docker, CLI 우선, I2K부터 의미 생성, 과거 provenance 불변은 유지한다.

## 목표와 범위

- PaddleOCR-VL-1.6 full pipeline을 로컬 Docker에서 고정 profile로 실행한다.
- Test_Paper.pdf 14페이지와 주 Figure 6개·캡션·좌표·이미지 crop을 확인한다.
- 이전 소제목 누락을 평가한 Nassar/Torchinsky/Wallet의 동결 기준과 비교한다.
- raw 결과와 원본 PDF를 보존하고, 파서 출력을 기존 source Information 경계에 연결할 최소 경로를 검토한다.
- Q4 의미/제목 보정 없이 파서 자체를 먼저 평가한다. I2K·K 생성이나 과거 canonical I의 자동 변경은 하지 않는다.

## 읽은 계약과 현재 구현

AGENTS.md, PLANS.md, USER_OVERRIDES, INDEX, DECISION_REGISTER, T03,
CODE_REVIEW, D2I_SOURCE_PRESERVATION, current canonical D2I 및 MinerU adapter.
현재 실행 경로는 tools/run_d2i.py → mineru_adapter → d2i/source_units → 기존 원자적 commit이다.
기존 실험 raw/profile은 immutable 비교 근거이며 새 output/t03-paddleocr-vl16에서 작업한다.
DB migration은 이번 parser 실험의 선행 조건이 아니다.

## 순서와 복구

1. 기능·공식 model revision/패키지·실행환경·Docker 기존자원 기록.
2. 기존 이미지 재사용 가능성을 확인해 필요한 의존성만 격리 설치, 공식 모델 다운로드.
3. 평가 oracle을 inference 전에 동결하고 network 없는 컨테이너에서 PDF 파싱.
4. 페이지·이미지·본문·제목·좌표 검증과 실제 Figure 시각 검토.
5. 관찰한 형식에 맞춘 최소 어댑터/실행 문서와 의미 있는 검사 추가.
6. 실행한 검증 결과·실패·제약 기록, 이 작업 소유 실패 Docker 자원만 정리.

원본은 read-only mount한다. 실패 산출물/로그는 별도 attempt로 보존한다.
새 파서는 기존 canonical snapshot/ID/hash를 덮어쓰지 않는다.
승인된 로컬 작업이며 원문 원격 API 전송은 없다.

## 검증과 완료 상태

T03 진행 중. 이번 Paddle 실험의 43페이지 parser 실행, 고정 제목 평가, Test_Paper 시각 QA와 격리 PostgreSQL 저장 검증을 마쳤다. 실제 parser/시각 QA, adapter unit, 문서 검사, PostgreSQL 검사는 각각 구분한다.
AT68/69/71/76 및 source coverage 관련 AT104/105에 대한 부분 근거를 기록하며,
전체 T03 또는 후속 task 완료로 확대하지 않는다.

## 실행 중 관찰과 수정

- 공식 모델 2개를 revision/hash 고정하여 다운로드했다. PaddleOCR 3.7.0 / PaddleX 3.7.2 / Transformers 5.17.0 / Torch 2.8.0 CUDA 12.8, layout FP32/VL BF16이다. `output/t03-paddleocr-vl16/runtime/`에 설치 및 이미지 로그를 보존했다.
- 평가 oracle은 추론 전 28개 입력 해시로 동결했다. 추가 논문 54개 명확한 제목과 기존 누락 39개를 같은 기준으로 평가한다. 평가 파일은 변경하지 않는다.
- 최초 Test_Paper a1은 선택적 SDK 시각화가 폰트 다운로드를 시도해 네트워크 차단 상태에서 실패했다. SDK box annotation 호출을 제거하고 원본 페이지 PNG/JSON/실제 crop을 보존한다. 실패 산출물은 남겼다.
- Test_Paper a2는 14페이지/708.743초, Nassar a1은 10페이지/304.685초에 파싱 완료했지만 기본 `merge_layout_blocks=true`가 열 간 텍스트를 첫 영역 bbox에 합치는 오류를 발견했다. 병합 금지와 adapter 거부 검사를 추가했고 이 시도들은 저장용으로 채택하지 않는다.
- 수정된 Nassar a2는 10페이지/312.069초, 261 blocks→source 제안261(Text197/Image64), raw/crop/좌표/문구 보존 검사 통과다. 제목은 26개 중 독립 경계5개, 기존 누락21개 중 복구0개다. 이는 파서 교체만으로 inline 소제목 문제가 해결되지 않는 실제 반례다. exact source string24/26의 두 미일치는 Gas6−/−의 LaTeX 전사 차이였고 실제 문구는 남았다. 동결 점수는 바꾸지 않는다.
- Test_Paper a3·Wallet a1 실행과 Torchinsky 대기 상태를 거쳐 최종 네 문서 43페이지를 모두 완료했다. 채택한 모든 페이지에서 merge=false다. application 의미 LLM/Q4 호출은 없다. source 제안 검증과 별도 실제 저장 검증을 구분한다.
- Figure 6개 존재와 crop 충실성은 별도다. Test_Paper a2에서 패널별 분리·캡션 다음 페이지 이어짐은 확인했으나 일부 범례/패널 crop이 잘렸다. 전체 페이지 PNG는 보존된다. SDK auto polygon crop은 chart 계열을 마스킹할 수 있다. image 라벨은 Markdown export가 원본 사각 crop으로 저장하는 예외가 있다.
- adapter/CLI/page projection/worker를 기존 Compiler Runtime 경로에 연결했다. 불변 image digest로 실제 실행하고 worker runner hash/profile을 추론 전에 검증한다. 모델 tag 변경이나 merge 설정 누락을 성공으로 처리하지 않는다.
- 첫 전체 앱 검사: 별도 PG18/pgvector DB에서 207개/28.876초/exit0. 후속 검사는209개/30.763초에 doctor 기대값1건과 test image의 host worker 파일 누락1건으로 실패했다. 기대값과 Docker COPY 수정 후 최종 210개/35.590초/OK를 확인했다. 실패 로그는 보존한다. 문서 validator는 최종 보고서 포함 exit0, 두 보고서 상대 링크 누락0이다.

사용자 application/개발 DB의 기존 canonical I, 과거 MinerU/모델 실험, 원본 PDF는 변경하지 않았다. 별도 `palimpsest-t03-paddle-verify` PG18/pgvector 프로젝트에는 실제 Test_Paper a3 출력으로 308 I를 저장하고 재시도·조회·export를 검증했다. 이 격리 저장 결과와 source proposal 검사, synthetic integration을 구분한다.

## 최종 관찰과 보고서

- [Paddle 실험 최종 보고서](T03_paddleocr_experiment.md)에 실행값, 실패 이력, 평가 분모, 실제 저장 범위와 남은 품질 문제를 기록했다. T03는 `in_progress`이며 후속 task는 시작하지 않는다.
- 완료 attempt: Test_Paper a3 14p/394.001초/308제안, Nassar a2 10p/312.069초/261제안, Torchinsky a1 5p/228.349초/110제안, Wallet a1 14p/613.443초/228제안. 합계 907제안(Text737/Image170), raw block 대응 검사는 모두 complete다.
- 고정 평가 입력·코드28개 SHA는 불변이다. 최종43페이지 score exit0, 구조오류0, 누락0. 추가3편 명확한 제목54개에서 source 문구49/54, 제목 label13/54, 정확한 제목 경계13/54다. 기존39miss 복구는0/39이며 전체 절 계층은 평가하지 않았다.
- strict 문자열 미일치6개는 raw의 대응 문구와 LaTeX/공백 차이를 따로 확인했다. 동결 점수는 변경하지 않았다. Wallet p8 block3의 `KD/KD` 상첨자→`⁰/¹⁰K⁺` 반복 오전사는 원본 페이지 시각 대조로 확인한 별개의 실제 충실도 문제다.
- Test_Paper 주Figure6개·캡션8조각·이어짐2개 확인. 전체Figure SDK crop0개, 패널/plot 조각63개와 비도표2개로 나뉜다. a3의14 render·65 crop 실제 SHA/bbox는 a2와 전부 동일하여 기존 Figure5A/5F/6H 잘림이 남는다. merge text/bbox 오류는 a3에서 수정됐고 비시각 빈 block8→0이다.
- 실제 PDF 저장 receipt는 `output/t03-paddleocr-vl16/actual-storage/result.json`: 격리 PG18에 Text243/Image65 저장, UUIDv7·중복 Data 거부·idempotent replay·14페이지·앞뒤페이지·125파일 export/raw-crop hash 통과. application LLM0, semantic_checked=false, 사용자 개발DB 불변이다.
- source 제안/고정 score 명령과 실행 GPU, 출력 SHA는 `output/t03-paddleocr-vl16/inspection/final-evaluation-receipt.json`에 남겼다. 이 보고서 작업에서 제품 기본값이나 oracle/scorer를 수정하지 않았다. 사용자 추가 요청의 MinerU Hybrid + Pro 실험은 별도 실행 범위로 비교한다.

## 후속 검증과 정리

- 최종 앱210tests/35.590초/exit0까지의 로그를 모두 보존했다. 중간 app-tests03의 진단 fixture 들여쓰기 오류1건도 app-tests04 전에 수정했다.
- 문서 mutation tests가 저장소 전체의 모델/실험 파일을 복사하는 기존 동작을 발견해 root 실행을 중단했다. `tools/test_validate_bundle.py`의 clone은 output/tmp 비Markdown은 존재 경로만 만들고 모든 문서·실제 source/config는 독립 복사하도록 수정했다. 무변형 clone과 원본 validator 결과가 완전히 동일하고 source가 같은 파일이 아님을 새 테스트로 확인했다. validator나 기존 assertion/skip은 바꾸지 않았다.
- 최종 `python -X utf8 -B -m unittest discover -s tools -p 'test_*.py' -v`:44tests/213.159초/exit0/OK. UTF-8 없이 실행한 별도 CP949 실패10건도 로그로 남겼다. 중단된 원래 테스트의 임시 clone 두 개(약56GB)는 정확한 Temp 절대경로·Palimpsest marker·생성시각을 확인해 제거했다.
- Paddle 종료 컨테이너8개와 별도 시험 프로젝트 컨테이너3개/network1개를 제거했다. 최종 이미지2개와 모델/raw, 기존 개발DB/Honcho 및 모든 볼륨을 보존했다. 빌드 로그로 추적한 중간 image12개는 이미 없는 상태였다. [Docker 정리 receipt](../output/t03-paddleocr-vl16/runtime/cleanup-result.json).
