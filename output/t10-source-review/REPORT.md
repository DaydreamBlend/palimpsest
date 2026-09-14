# 범용 D→I→K 원문·의미 항목 검토 구현 결과

2026-09-13. 사용자가 특정 논문의 Figure에 과적합하지 않고 모든 D/I/K에 적용하도록 요청하여 **새 전체-source I2K의 공통 검토·저장 계약을 구현했다.** 기존 I의 원문 주소를 빠짐없이 열거하고, LLM이 그 내부의 독립적인 의미 항목과 중요성을 판단하며, 독립 Validator가 누락을 확인한다. 검토 결과는 실제 KNode/정확 KRevision까지 연결한다.

실제 구현 계약은 [SOURCE_REVIEW](../../docs/interfaces/SOURCE_REVIEW.md), 실행 과정은 [계획](../../progress/T04_source_review_execplan.md)에 있다. 기존 [Test_Paper 감사](../t10-panel-coverage/REPORT.md)는 문제 발견 사례다. Figure 수를 K 개수나 모든 문서의 규칙으로 고정하지 않는다.

## 무엇이 달라졌는가

이전에는 큰 I 하나를 reviewed/selected로 처리하면 그 안의 독립적인 내용이 모두 검토됐는지 별도로 추적할 수 없었다. 이제 기존 원문 block/문자/media별 target과 그 안의 LLM 의미 item을 구분한다. 한 개의 Markdown 절이나 Figure에 여러 item이 들어갈 수 있다. 반대로 동일한 의미의 여러 표현은 기존 K를 재사용할 수 있다.

`source_reviews`의 selected item은 실제 후보를 인용하고, 모든 후보의 각 I/text/media 근거도 검토 item에 역으로 연결되어야 한다. 독립 Validator는 target 내부의 누락과 각 item을 각각 확인한다. target/item이 미해결이거나 연결된 후보가 보류/기각된 채 남으면, 일부 K가 검증되어 저장됐더라도 실행 전체는 성공 완료로 표시하지 않는다.

후보의 결과는 application이 실제 commit된 Compiler Record와 exact KRevision에서 가져온다. provider가 결과 ID를 임의로 제출해 근거를 꾸밀 수 없다. 검토 결과와 K는 같은 PostgreSQL transaction으로 반영되고 실패하면 함께 rollback한다. 같은 의미를 재사용할 때 새 의미 Revision이나 중복 grounding을 만들지 않는 기존 규칙을 유지했다.

## 실제 검사

| 검사 | 결과 |
|---|---|
| 새 이미지 전체 앱 suite | **669 tests / 653 pass / 16 skip / 실패0**, 134.631초, exit0 |
| 새 순수 source review tests | 10개 pass, 형식 무관 주소·소유권·내부 item·누락/변조 검사 |
| 새 실제 PostgreSQL tests | 10개 pass, exact 결과 연결·미완료 상태·재사용·rollback·replay |
| 보존된 PDF 3개와 Markdown 1개 입력 | 모든 입력 digest와 source packet 전후 bytes 동일, manifest 반복 생성 동일 |
| 서로 다른 네 source의 합친 입력 | I111개, 원문 검토 target576개, source별 unique target 소유권 유지 |
| Docker build / 실제 CLI | exit0, `palim 0.10.0` |
| 이번 실제 provider/D2I/새 migration | **0 / 0 / 0** |

16 skip은 기존 native PDF 검사 환경 조건이다. 전체 앱 suite에는 기존 Electron read service 검사가 포함되며 실제 Electron 창 검사를 이번 core 변경 때문에 다시 실행한 것은 아니다. 앞선0.9.0 GUI 실물·portable package 검증은 [별도 결과](../t09-electron/REPORT.md)에 보존했다.

실제 PG 테스트는 `palimpsest-multi-checks` 프로젝트의 별도 fixture DB `palimpsest`에서 합성 후보·합성 판정을 사용했다. 원본 source DB와 `palimpsest_wiki_pg`를 fixture로 쓰거나 canonical 논문 데이터를 변경하지 않았다. 테스트는 semantic LLM 호출의 성공률 측정이 아니다.

### 기존 자료로 확인한 공통 적용

| 보존 입력 | 기존 I | 원문 검토 target | 위치 상태 |
|---|---:|---:|---|
| Test_Paper PDF | 36 | 243 | 모두 mapped |
| Clarke PDF | 35 | 173 | 모두 mapped |
| Dejani PDF | 16 | 136 | 모두 mapped |
| 프로젝트의 큰 Markdown | 24 | 24 | 모두 mapped |
| 서로 다른 네 Data의 합친 입력 | 111 | 576 | 소유 Data/I/실행이 구분됨 |

target은 실행의 검토 주소이며 새 I나 K가 아니다. mapped는 보존된 문자/이미지 주소의 연결 상태로, OCR 정답률이나 중요한 주장의 회수율이 아니다. 원문 파일을 다시 등록하거나 MinerU를 실행하지 않고 기존 source packet만 읽었다. [재현 script](check_existing_sources.py), [입력별 hash와 수](existing-source-checks.json), [혼합 source manifest](mixed-sources-manifest.json).

HTML·코드 형태의 fixture에도 같은 검토 함수를 적용했지만, 현재 실제 D2I adapter 지원은 PDF·Markdown이다. 새 HTML/code 파서를 구현하거나 그 형식의 실제 전체 D2I→K 모델 실험을 완료했다고 보고하지 않는다.

## 검토에서 발견하고 해결한 문제

초기 구현에서는 모든 의미 item을 context_only로 기록하면서 다른 곳에서 K 후보를 accepted로 저장할 수 있었다. 이 경우 새 source review에 해당 K 결과가 연결되지 않았다. 리뷰어가 순수 함수로 재현했고, 후보의 각 I/text/media 근거가 실제 source item에 역으로 연결되는 검사를 추가해 차단했다. `source_review_candidate_unrepresented` 회귀 검사가 통과한다.

Validator의 바깥 `complete=true`와 내부 target/item `needs_review`가 함께 오면, 유효한 미완료 검토로 저장하면서 전체 성공을 차단한다. 일부 독립적으로 승인된 K를 버리는 방식으로 구현하지 않았다. 각 결과의 exact Revision 연결과 중간 commit 실패의 rollback도 실제 PG에서 확인했다.

기존 selection/multi fixture는 `source_review=False`를 명시해 당시 계약의 회귀 검사를 계속한다. 새 기본 profile, 기존 request의 자동 replay, 기존 완료/실패 history와 frozen 입력은 구분한다. 과거 실행을 새 검토를 받은 것처럼 바꾸지 않는다.

## 파일과 운영

- `src/palimpsest/source_review.py`: 원문 주소 manifest, strict schema 확장, 양방향 evidence 결속과 미해결 판정.
- `src/palimpsest/knowledge_requests.py`: 같은 prompt/schema를 Runtime receipt 검증과 provider request export에서 재사용.
- `src/palimpsest/knowledge_runtime.py`: 새 기본값과 과거 replay, frozen manifest, durable Generator/Validator 결과, 원자적 exact Record/KRevision binding.
- `tools/prepare_selection_call.py`: 공통 request builder 사용.
- `tests/app/test_source_review.py`, `tests/app/test_source_review_runtime.py`: 새로운20개 검사. 기존 selection/multi tests는 legacy 범위 명시.
- 앱 version0.10.0, 계약/계획/인덱스/AGENTS/README 갱신. schema0010과 과거 migration bytes는 변경하지 않음.

성공 이미지: **`palimpsest-source-review:0.10.0`**  
digest: `sha256:2b99bd48e72c0c21ace3b914c50332b54a4df31933680d5fa0a13707d8dcdc61`.

기존 Compose default0.4.0은 원본 DB의 미승인 migration을 자동 실행하지 않도록 유지했다. 새 구현 사용은 새 이미지를 명시하는 방식이다. Electron portable 앱은 검증했던0.9.0 읽기 backend를 계속 사용하며, 이번 원문 검토 UI나 새 질문 실행 UI를 추가하지 않았다. 기존 성공 이미지와 사용자 원본/volume을 보존했고 검사 컨테이너는 `--rm`으로 종료했다.

실행 명령:

```powershell
docker build --tag palimpsest-source-review:0.10.0 .
$env:PALIMPSEST_APP_IMAGE='palimpsest-source-review:0.10.0'
docker compose -p palimpsest-multi-checks run --rm --no-deps -T test
docker run --rm --network none palimpsest-source-review:0.10.0 --version
```

[빌드 로그](build.log), [전체 앱 로그](app-tests.log), [검사 요약](verification.json)을 보존한다. 앞서 기존 이미지에 수정 중 소스를 mount한 중간 PG10tests도 통과했지만 최종 이미지669tests와 중복 계산하지 않는다. 코드 읽기 중 존재하지 않는 `docker-compose.yml`, `output/t03-html` 경로를 확인하려던 조회는 실패했고 실제 `compose.yaml`, `output/t03-html-review` 경로로 바로잡았다. 이 조회 오류를 앱 검사 실패나 성공으로 세지 않는다.

문서 bundle validator는 이번에도 exit1/820개 오류다. Electron/npm third-party 문서808개와 보존된 이전 raw 문서12개로, 앞선 GUI 검사 때와 같은 범주다. 이번에 작성·수정한 문서12개는 같은 inspector의 구조·로컬 링크 검사에서 오류0이었다. [전체 로그](document-validation.log), [분류·작성 문서 검사](document-validation-summary.json). 전체 validator 통과로 보고하지 않으며 이를 숨기기 위해 parser raw나 third-party 문서를 수정하지 않았다.

## 남은 검증과 영향

이 기능은 원문 내용이 어떻게 검토되고 어떤 K로 반영됐는지를 규격화한다. **새 실제 LLM 실험은 수행하지 않았으므로 의미 분할·누락 탐지·중복 판단의 개선률은 아직 모른다.** 기존 Test_Paper는 K32개로 유지되며 source review manifest를 만들었다고 새 K를 생성한 것으로 세지 않는다.

모델이 큰 target을 너무 거칠게 묶거나 독립 Validator도 누락을 놓칠 가능성은 남는다. 다음 실제 평가에서는 문서 종류가 다른 여러 source에서 내부 누락, false split/merge, 원문 근거 충분성, 재사용, source 요청과 실패 이력을 확인해야 한다. 구조적인 완료와 의미적인 완전성을 구별해서 보고한다. D2I 재실행 없이 직접 D 근거를 보완하는 기존 미구현 provider/grounding 범위 역시 이번 검토 기록만으로 해결됐다고 주장하지 않는다.
