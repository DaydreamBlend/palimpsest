# T04 첫 입력 구현 — 2026-09-11

canonical I 기반 최초 입력 준비와 등록 원본 PDF 요청의 로컬 검증을 구현했다. [사용법](../../docs/implementation/T04_INPUT.md), [후속 실행 계획](../../progress/T04_input_execplan.md). T04 전체 K 실행·저장 완료는 아니다.

## Test_Paper 실물 검증

기존 image200 MinerU 결과를 작업 전용 PostgreSQL18.6/pgvector0.8.6에 재생하고 설치된 CLI를 호출했다. 새 parser/LLM 호출은 각각 0회다. 원본과 과거 raw/I를 재작성하지 않고 격리 저장소에 새 test I를 생성했다. [전체 결과](paper-attempt-01/verification.json), [실행 로그](paper.log), [재현 스크립트](test_paper.py).

| 항목 | 관측 결과 |
|---|---|
| 입력 I | 229개: Text193 / Image36 |
| I content 문자 수 | 63,031 Unicode 문자, tokenizer 측정은 아님 |
| 고유 I media | 36개 실제 bytes/hash 검증 |
| 초기 원본 PDF·전체 페이지 raster 첨부 | 없음 |
| 선택 절 입력 | section-3: target4/context3/excluded222, 세 목록의 전체 I 분할 확인 |
| 알려진 검토 신호 | 88개 전달, 확정 오류 건수나 오류율이 아님 |
| 요청한 원본 | SHA a2268b37570f41bb07189cf083376e5823fae364165d5e0e256f796a0814cffe, 3,890,649 bytes |
| 오래된 절 hash / 입력 hash 요청 | CLI exit4로 각각 거부 |
| 등록·입력·요청 시험 소요 시간 | 87.89초, 모델 latency 측정은 아님 |

36은 Image I 수이며 논문의 주 Figure 수가 아니다. 패널 등을 포함한다. [전체 최초 입력](paper-attempt-01/whole-input.json), [선택 절 입력](paper-attempt-01/section-input.json), [원본 준비 결과](paper-attempt-01/prepared-source.json)를 보존했다. media는 실제 저장 bytes를 별도로 읽어 SHA를 확인했다. request는 스크립트가 만든 시험 fixture이며 모델이 필요성을 판단한 결과가 아니다. 원본은 `not_delivered`, 실제 원문 인용은 빈 목록이다.

측정 범위 정정: `verification.json`의 `canonical_i_changed_by_preparation=false`는 시험에서 준비 전후 canonical I **행 수가 동일함**을 확인한 항목이다. 별도 before/after 전체 행 digest 측정으로 확대하지 않는다. 구현의 read-only SQL과 canonical I content/FP/grounding 무결성 검사 및 immutable DB 계약은 별도 근거다.

## 앱 검사와 실패 기록

- 최종 Docker 앱 suite: **340 tests, failures0/errors0, skipped16**, unittest 실행27.175초, runner 전체27.485초, exit0. [기계판독 결과](app-tests.json), [전체 로그](app-tests.log). unit/실제 Linux 파일 접근/격리 PostgreSQL/CLI 검증을 포함한다.
- 16 skips는 PDFium 기반 raster/native text/visual projection 테스트다. 이번 앱 image에 해당 native PDF 라이브러리가 없으며 이 변경은 PDF renderer/parser 코드를 수정하지 않았다. 새 native PDF 재실행이나 의미 품질 평가로 보고하지 않는다.
- 첫 runner는 multiprocessing spawn의 main guard가 없어 자식이 전체 suite를 다시 실행했다. **340 tests, failures8/errors0/skipped16, exit1**을 [원래 로그](app-tests-harness-failed.log)와 [결과](app-tests-harness-failed.json)에 보존했다. 앱 검사를 제거하거나 threshold를 바꾸지 않고 runner에 main guard를 추가해 재실행했다.
- 진단 중 test container stop을 시도했으나 이미 실행 종료와 `--rm` 정리가 끝나 `No such container`, exit1이었다. 강제 중단/공유 DB 복구 작업은 발생하지 않았다.
- 독립 코드 검토에서 media의 byte_size와 실제 manifest descriptor 대조 누락, 일반 Image I를 파생 Figure로 잘못 표시하는 경우를 수정하고 최종 image에서 검증했다. 최종 읽기 검토에서 추가 blocking finding은 없었다.

## 실행 환경과 재현

새 migration/dependency는 없다. 최종 image `palimpsest-t04-input:0.2.0`의 ID는 `sha256:9638a950900d7419b461f09010ae5551f16b1f822053cf7a70c68f3ca5134918`이다. 아래는 작업 디렉터리의 PowerShell에서 사용한 명령의 핵심 부분이며 provider 호출은 없다. 새 프로젝트 DB는 기존 사용자 DB와 구분한다.

```powershell
$env:PALIMPSEST_APP_IMAGE='palimpsest-t04-input:0.2.0'
docker build -t palimpsest-t04-input:0.2.0 .
docker compose -p palimpsest-t04-input run --rm -T migrate
docker compose -p palimpsest-t04-input run --rm --no-deps -T --volume 'C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/output/t04-input:/results' --entrypoint python app -B /results/run_tests.py
docker compose -p palimpsest-t04-input run --rm --no-deps -T --volume 'C:/Users/DaydreamBlend/Desktop/Test_Paper.pdf:/source.pdf:ro' --volume 'C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/output/t03-image-default:/frozen:ro' --volume 'C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/output/t04-input:/results' --entrypoint python app -B /results/test_paper.py
```

실제 초기 migrate에는 이전 성공 앱 `palimpsest-t03-sections:0.3.0`을 사용했고 동일0003 source schema, PostgreSQL18.6/pgvector0.8.6을 확인했다. 최종 앱 image로 전체 suite와 Test_Paper CLI를 실행했다. 위 suite runner는 고정 결과 파일에 쓰므로 재현할 때는 새 output 디렉터리에 runner를 복사해 과거 로그를 보존한다. PDF runner는 새 `paper-attempt-NN`을 만들지만 로그 리다이렉션도 별도 경로로 둔다.

## 남은 범위

문서 validator는 exit1이며 [결과](document-validation.json)의 12개 오류가 이전 정책 변경 때와 동일하다. 과거 parser raw Markdown의 table delimiter11개와 과거 oracle 표1개가 원인이다. 이번 문서에서 추가된 오류는 없다. 원본 raw나 과거 oracle을 고치거나 검사 기준을 완화하지 않았다.

Docker는 [소유권 확인](cleanup-preflight.json) 후 `docker compose -p palimpsest-t04-input down --volumes`로 이번 테스트의 컨테이너2개·볼륨4개·네트워크1개를 정리했다. [최종 확인](cleanup-verification.json)에서 기존 컨테이너/이미지/볼륨은 모두 보존됐고, 이번 작업의 새 이미지로 최종 성공 image 하나만 남았다. 초기 중간 build image는 정리 전에도 목록에 없었다. 실험 DB는 제거했으므로 기록의 execution/I UUID는 그 격리 실험의 참조이며 사용자 live DB에서 조회 가능한 ID라고 제시하지 않는다. 새 재생은 새 test UUID를 생성하고 같은 원본 Data SHA를 유지한다.

실제 provider에 I/image/PDF를 보내는 adapter, 모델 예산 측정, durable I2K request/delivery/use/validation 이력, Generator/Validator 판단, 첫 K kind registry, duplicate reuse/Revision/atomic commit은 후속 slice다. [T04 acceptance 목록](../../tasks/T04.md)을 일괄 pass로 바꾸지 않는다. 기존 T03 전체 충실성 gate도 유지한다. 준비 단계에서 source fidelity를 승인하지 않는다.
