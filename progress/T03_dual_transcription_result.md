# T03 — MinerU 이중 전사 기본값

2026-09-10. [사용자 승인](../docs/decisions/MINERU_DUAL_TRANSCRIPTION.md)에 따라 PDF D2I 기본값을 MinerU3.4.5 Hybrid high + Pro2605 1.2B / local Transformers로 고정했다. 원본 PDF auto와 200 DPI image-only OCR을 모두 실행하고 ordinary native / localized special OCR 우선 선택을 새 source I에 저장한다. 두 원시 전사와 모든 source/model/origin·renderer/PNG/PDF·profile·hash는 보존한다. 모든 application semantic LLM 호출은0이다.

## 현재 검증 상태

최종 v3의 전체 Test_Paper14페이지 이중 파싱과 격리 PostgreSQL18.6/pgvector0.8.6 저장 검증을 완료했다. 원본 경로 OCR=false, 이미지 경로 OCR=true를 실제 raw에서 확인했다. 전체 처리597.797초, raw/모델/renderer/profile 검증 뒤 source I229개(Text193/Image36)를 저장했다. 모든 I의 content·source block·grounding·bundle hash 일치, 같은 요청/작업 재시도에서 동일 I ID 재사용,14페이지 조회를 확인했다. 선택8곳, 비교검토14blocks이며 비교 상태는 needs_review로 그대로 공개한다. [실행](../output/t03-dual-transcription/Test_Paper-v3/execution.json), [PG 검증](../output/t03-dual-transcription/store-v3/verification.json), [전체 선택 bundle](../output/t03-dual-transcription/store-v3/bundle.json), [페이지 조회](../output/t03-dual-transcription/store-v3/pages.json). 이전 두 시도는 코드 검토 및 실물 오류 수정 중의 별도 profile/raw로 보존했으며 canonical에 반영하지 않았다.

## 구현과 동작

- `tools/run_d2i.py`: 기본 `mineru-hybrid`가 dual이고, 과거 native 단독은 `mineru-hybrid-native`다. immutable parser image/model·renderer·runner·선택 구현 hash를 profile에 결속한다. Compose 앱 기본은 `palimpsest-t03-pdf200:0.2.0`다.
- `pdf_raster.py`, `pdf_raster_adapter.py`: 원본 페이지 geometry와 200 DPI 픽셀·image-only PDF를 검증하고 OCR의 파생 bbox를 원래 Data/page 좌표로 변환한다. 긴 변3,500pixel 상한 및 실제 scale을 기록하며 rotate 미지원은 명시적으로 실패한다.
- `hybrid_receipt.py`, `dual_adapter.py`: 양쪽 필수 raw/model/origin 파일과 경로·hash·model 페이지 수·actual OCR route·renderer mapping을 검증한다. 하나의 실패를 다른 parser로 덮는 fallback은 없다.
- `transcription_selection.py`: `native-ordinary-ocr-special-v3`. 유일한 같은 페이지 block 대응과 국소 raw 문자 범위로 선택한다. 일반 identifier/URL의 underscore는 그대로, 불명확한 block은 native 전체를 유지한다. 공백 위치가 확정되는 경우에만 누락 기호를 삽입한다.
- `source_units.py`, `compiler_runtime.py`: 새 선택 content와 native_text/segments/anchor·OCR 근거를 보존한다. 구조 저장 완료와 comparison `needs_review`를 ledger·durable source receipt·materialize/replay 응답에서 구분한다. 기존 migration·I·ID·hash는 불변이다.
- `page_projection.py`, `paragraph_projection.py`, `pdf_evidence.py`: 페이지 선택 문자열에 exact dual refs를 제공한다. 문단 원시 text/offset은 남기고 selected_text/selected_segments를 별도로 읽는다. 전체 Figure·페이지·native heading 후보는 계속 evidence projection이다.

## 의미와 품질의 한계

두 전사가 일치하거나 선택 규칙을 통과해도 원문 정확성 승인을 뜻하지 않는다. [첫 실물의 선택8곳 시각 검토](../output/t03-dual-transcription/visual-review/review.md)에서는 실제 누락 β1곳, 이미맞은 micro/첨자표기 변경5곳, native minus보다 literal 충실성이 낮은 ASCII hyphen 선택2곳을 구분했다. β의 공백 삽입 오류는 v3에서 수정했다. 8곳을8개정확도개선으로세지않는다.

원본 p10 Figure5 caption의 `P <`3개는 원본·OCR에 있고 native에는 빠졌다. 일반 문자 우선 규칙상 자동 복구되지 않는다. 복잡한 LaTeX·script와 모호한 block 대응도 native 유지·검토 항목으로 남는다. 두 raw·원본 PDF·페이지 이미지에서 다시 확인할 수 있다. I2K 이후 의미 LLM을 실행하지 않았고 T03 전체 acceptance를 완료로 올리지 않는다.

## 실행한 검사

- 최종 앱 build: `docker compose -p palimpsest-t03-dual-verify build app`, exit0.
- 최종 앱/PG 회귀: `docker compose -p palimpsest-t03-dual-verify run --rm --no-deps test`, **296tests /30.724초 /failure0 /skip16 /exit0**. [로그](../output/t23-ui-realm/build-test-logs.zip#output/t03-dual-transcription/runtime/app-tests-final.log).
- PDF 의존성 별도 실행: 기존 Hybrid image에서 `python -B -m unittest -v test_pdf_raster test_pdf_text_evidence test_pdf_visual_evidence`, **22tests /0.775초 /failure0 /skip0 /exit0**. [명령과 receipt](../output/t03-dual-transcription/runtime/native-tests.receipt.json).
- Windows 문서 도구 suite: **44tests /352.372초 /failure1 /error70 /exit1**. 오류70은 clone 임시 경로275자에서의 Windows long-path 실패다. [로그](../output/t23-ui-realm/build-test-logs.zip#output/t03-dual-transcription/runtime/bundle-tests.log). 원본 소실이 아니다.
- 문서 validator의 남은 오류는 보존된 MinerU Markdown의 단독 pipe를 표 구문 오류로 판단한 것이다. raw를 고치거나 검증 규칙을 완화해 통과시키지 않는다. 최종 개수와 authored 문서 검증은 아래 후속 기록에 명시한다.

같은 200 DPI 입력에서의 Paddle 비교는 [별도 결과](T03_paddle200_result.md)를 따른다. 그 결과는 새 dual 선택의 전체 정확도 점수가 아니다.

## 최종 근거 조회와 보존 확인

[최종 원문 근거 패키지](../output/t03-dual-transcription/evidence-v3/README.md)에 원본 PDF, 14페이지 이미지, 전체 Figure companion 6개, 양쪽 parser raw, 소제목 후보 35개와 전사 불일치/검토 후보 72개를 생성했다. 후보 72개는 확정된 OCR 오류 수가 아니며, 선택 비교의 needs_review 14 blocks와 집계 범위가 다르다. 미대응 OCR 8 blocks도 raw와 비교 inventory에 남는다.

실제 evidence reader가 읽은 source bundle SHA가 격리 PG에 저장한 `c782d5907e338b4e8862a5eb2b3c2fc5cb1a31aba49c3d7c653c679697394e23`과 일치했다. source I와 문단 selected_text 모두 `TGF-β in addition`이며 p10 조회의 문맥은 p9–11이다. 읽기 검증의 canonical writes와 semantic LLM calls는 0이다. [조회 검증](../output/t03-dual-transcription/evidence-review-v3/verification.json).

[최종 v3 시각 근거 대조](../output/t03-dual-transcription/visual-review/v3-verification.json)에서 선택 8건의 양쪽 raw 문자열·leaf refs·hash·bbox를 확인했다. 7건은 앞선 시각 검토와 같고 β 1건만 올바른 공백 앞 위치로 바뀌었다. 14페이지 PNG hash와 geometry/transform은 앞선 렌더와 같았다. 파생 image-only PDF의 binary hash까지 같지는 않았으며, 그 직렬화 차이의 원인은 추정하지 않았다. 같은 raw의 결정적 조립·저장은 검증했지만 GPU 모델 재추론의 완전한 결정론성을 입증한 결과는 아니다.

## 최종 문서 검사와 Docker 정리

- Linux 공유 경로에서의 문서 suite는 파일 접근 지연으로 제어 종료했다. exit 137을 성공이나 OOM으로 해석하지 않으며 [중단 receipt](../output/t03-dual-transcription/runtime/bundle-tests-linux.receipt.json)에 사유를 남겼다.
- 기존 `BundleChecks.clone()`을 그대로 이용한 Linux 내부 fixture에서 `python -B -m unittest discover -s tools -p "test_*.py"`를 실행했다. **44 tests / 56.453초 / failure 1 / error 0 / skip 0 / exit 1**이다. 실제 저장소와 fixture의 validator 결과 전체, 테스트 bytes의 동일성을 확인했다. 원시 Markdown·code·config는 실제 복사하고 generated non-Markdown은 기존 fixture 규칙대로 경로만 유지한다. 이 결과는 원본 저장소 suite 완료와 구분한다. [fixture receipt](../output/t03-dual-transcription/runtime/bundle-tests-linux-fixture.receipt.json).
- 실제 저장소의 최종 `python tools/validate_bundle.py --json` 결과는 **exit 1, raw Markdown delimiter 오류 9건**이다. 모두 보존된 raw 원본/사본의 단독 pipe 판정이며 authored 문서·상대 링크·원본 보존 계약 관련 추가 오류는 없다. raw나 검사 규칙을 고치지 않았다. [최종 검사](../output/t03-dual-transcription/runtime/document-validation-final.json).
- `docker compose -p palimpsest-t03-dual-verify down --remove-orphans`는 exit 0이다. 임시 실험 컨테이너 잔여 0, 기존 7개 컨테이너·13개 이미지·27개 볼륨은 모두 보존했다. 이번에 추가로 남은 이미지는 검증한 `palimpsest-t03-pdf200:0.2.0` 하나다. 중간 앱 이미지는 이미 존재하지 않아 삭제 시도에서 No such image였으며 새로 삭제했다고 세지 않는다. 검증 Data/DB가 든 프로젝트 볼륨 4개는 유지했다. 전체 prune과 volume 삭제는 0이다. [최종 자원 대조](../output/t03-dual-transcription/runtime/final-resource-audit.json).

승인 대기 결정은 없다. 이번 default/dual source/evidence slice를 완료했으며, T03의 전체 native/scanned/mixed QA와 AT22/23/25/27/33/36/68/69/71/76/77/81/83/85/90–102/104/105/107/111/112를 일괄 pass로 올리지 않는다. 각 AT의 기존 검증 범위를 유지하며 이번 실행만으로 전체 acceptance를 충족했다고 주장하지 않는다. I2K 이후 단계는 실행하지 않았다.

로그 링크의 ZIP fragment는 T23 정리 때 보존한 원래 entry 경로다. 원문 내용은 archive와 cleanup manifest에서 확인한다.
