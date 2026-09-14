# 같은 스크립트 초안의 Qwen3.5-4B 재검토 비교

2026-09-10 사용자 요청: 스크립트가 있으면 4B도 직전 9B와 같은 결과를 내는지 확인한다. 앞서 정정·사용한 **Qwen3.5-4B Q4_0**를 선택했다. 기존 모델과 Docker 이미지를 재사용하며 다운로드나 외부 추론 호출은 필요하지 않았다.

## 범위와 동결

AGENTS, USER_OVERRIDES, INDEX, DECISION_REGISTER, T03/T04, MINERU_IMAGE_DEFAULT, PLANS, CODE_REVIEW, I2K_CONTEXT_POLICY를 확인했다. Ponytail 및 로컬 community-evals 방식을 적용해 기존 stdlib 도구와 Docker 이미지를 재사용했다. 원문 D/I/페이지/이미지/ID/해시 및 9B 실험을 보존한다. K 실행·PG·canonical·제품 기본값을 변경하지 않는다.

9B의 source/draft/packets/평가 기준과 별도 오류 대조 packet/expected를 바이트 그대로 복사했다. 동일한 20개 이슈, 7개 입력, 3회 반복이며 thinking 설정 2,048/context 32,768/output 4,096/temperature 0/seed 42/cache off/text-only를 유지했다. 기존 동결 runner의 request.model을 protocol.model에서 읽도록 새 복사본의 한 줄만 바꾸고 원본·변형의 해시와 차이를 기록했다. 기존 9B 코드와 산출물은 변경하지 않았다. 실제 요청은 model 필드 외에 동일해야 한다.

모델은 지정된 후보에 필요한 83개 고유 I를 검토한다. 229개 I 전체의 보존과 Figure companion 연결은 스크립트의 책임이다. 원본 이미지 참조는 보존하지만 이번 모델 입력은 텍스트다. 모델 응답을 자동 수리하거나 실패를 보고 prompt를 바꾸지 않는다.

## 실행 및 검증

- [x] 기존 4B 모델의 전체 파일 SHA-256 `298fcb5fe7a77ccc79745ae24751560c5ac56874caff4bb39b1f2055bd72b8bb`와 크기 2,583,221,408 bytes를 확인했다. 모델 revision은 `e87f176479d0855a907a41277aca2f8ee7a09523`이다.
- [x] 시작 Docker baseline은 7 containers/15 images/35 volumes였다. 5080의 시작 GPU 부하는 4B 10%, 이전 9B 91%로 달랐다. Q4_0와 Q8_0 차이도 있어 시간 차이를 모델 크기만으로 설명하지 않는다.
- [x] `python -X utf8 -B tools/run_script_review_comparison.py prepare --root output/t03-script-context-review-4b`: exit 0. 공유 artifact 7개를 그대로 복사하고 protocol/lineage를 동결했다.
- [x] `python -X utf8 -B output/t03-script-context-review-4b/check_comparison_transport.py`: exit 0, 8 tests/0 failures/0 errors/0 skips. 실제 모델 선택, 요청 동일성, 같은 결정의 적용, 잘못된 응답 기록, 기대 답안 변조 시 호출 전 거부와 모듈 경로를 검증했다. HTTP mock/CPU 검사이며 모델·DB 호출은 0이다.
- [x] `./output/t03-script-context-review-4b/runtime.ps1 -Mode server`, `-Mode smoke`, `-Mode run`, `-Mode control`을 순차 실행했다. Client 3개는 모두 exit 0. 실제 Qwen3.5-4B Q4_0, context 32,768, slot 1이며 모델 로드에는 13.39초가 걸렸다.
- [x] 별도 smoke 1회, 정식 21회, 동일 오류 대조 1회로 실제 호출은 23회다. Smoke는 11.295초, 구조상 유효했다. Smoke/control은 정식 품질 점수와 시간에서 제외했다.
- [x] `python -X utf8 -B tools/compare_script_review_models.py`: exit 0. 기존 평가기에 결속된 독립 비교를 한 번 실행해 metrics/EVALUATION을 기록했다. Scorer의 요청 변조·근거 집합/순서 분리·누락 usage·전체 synthetic lifecycle·최종 결과 변조·덮어쓰기 거부도 별도로 확인했다.
- [x] `./output/t03-script-context-review-4b/runtime.ps1 -Mode cleanup`: exit 0. 이번 실험 라벨의 임시 컨테이너 4개만 로그를 보존한 뒤 제거했다. 모든 최종 exit code는 0이다. 기존 이미지나 볼륨을 지우지 않았다.

호스트 Python은 `C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`이며 `-X utf8 -B`를 사용했다. 모델 실행은 고정된 기존 llama.cpp b10380 및 Python Docker 이미지에서 수행했다. 명령과 로그는 [실험 폴더](../output/t03-script-context-review-4b/)에 보존했다.

## 결과

3회 모두 **19개 문맥 그룹·229개 I 각각 1회·누락/중복/미해결 0**이다. 그룹 소속·역할·Figure 참조와 companion 정보가 9B와 같다. 매회 초안의 Abstract 하나를 metadata에서 분리했으며, 그 외 경계 병합은 없다. 정식 60개 판단은 모두 같지만 근거 집합은 30/60, 배열 순서까지는 24/60, 이유 코드는 33/60만 일치했다.

주 평가 대상 103개 I의 pairwise F1은 양쪽 0.96635다. 사전 probe는 16/18이며, 남은 2개는 Figure 1의 실제 두 소절을 유지한 것과 수동 묶음 선호의 차이다. 스크립트의 초안 대비 primary pairwise F1은 그대로였고 Abstract 역할 판별이 개선됐다. 구조 통과를 전체 의미 정확성으로 확대하지 않는다.

별도 오류 대조에서 4B는 페이지를 넘는 문장의 잘못된 분할을 `merge_previous`로 감지했다. 그러나 Figure 5 후보에 Figure 6 continuation 189를 잘못 연결한 경우 `keep`을 반환했다. 올바른 Figure 5 근거 152/158을 선택했어도 후보 자체를 수정하거나 거부한 것이 아니다. 결과는 **4B 1/2, 9B 2/2**이며 재시도하지 않았다. 두 대조 사례의 관찰을 일반 오류율로 표현하지 않는다.

4B의 이유 코드에는 유형 불일치 15/60과 확정 판단에 `insufficient_context`를 붙인 9/60이 있다. Abstract에 `front_metadata`를 붙인 3건은 기존 rubric을 바꾸지 않고 별도 정성 진단으로 기록했다. 같은 정상 초안의 문맥 구성은 재현됐지만 오류 검출까지 동등하다고 결론내릴 수 없다.

정식 21회 처리 시간 합계는 4B 260.55초, 9B 1,482.78초다. 7개 입력으로 구성된 1회분의 중앙값은 86.85초와 486.73초다. 모델 로드와 실행 사이 대기는 제외한다. 양자화·GPU 부하 차이가 있으므로 통제된 속도 비교가 아니다.

## 산출물과 변경

- [결과 보고서](../output/t03-script-context-review-4b/REPORT.md), [독립 평가](../output/t03-script-context-review-4b/EVALUATION.md), [정성 검토](../output/t03-script-context-review-4b/FINDINGS.md), [metrics](../output/t03-script-context-review-4b/metrics.json), [최종 projection](../output/t03-script-context-review-4b/final/repeat-1/projection.json).
- [비교 실행 도구](../tools/run_script_review_comparison.py)와 [비교기](../tools/compare_script_review_models.py)를 추가했다. 기존 9B runner는 그대로 두고 새 실험 폴더 안에 모델 선택만 변경한 동결 복사본을 만들었다.
- docs/INDEX.md와 I2K_CONTEXT_POLICY.md에 같은 입력의 4B 비교 범위를 연결했다. 변경 전 바이트는 새 실험의 docs-before에 보존했다.

## 한계 및 완료 경계

이미 알려진 논문 1편과 정해진 후보의 텍스트 실험이다. 후보로 수집하지 못한 제목·경계, 다른 논문·Markdown, 파서/OCR fidelity, 실제 이미지 이해, K 생성 품질은 검증하지 않았다. 명시적 Figure 번호 불일치의 스크립트 검사나 모델 승격 정책은 제안에 해당하며 이번에 새로 구현하지 않았다. 4B가 잘못된 후보에도 `keep`을 반환했으므로 `needs_context`만 승격하는 정책으로 이 실패를 잡을 수 있다고 보지 않는다.

미해결 승인 결정은 없다. T03/T04 acceptance 상태를 승격하지 않으며 앱/PG integration 테스트를 실행한 것으로 보고하지 않는다. 원본 및 Docker 최종 감사와 문서 검사는 아래에 별도로 기록한다.

## 최종 보존 감사

2026-09-10 19:49:05 KST에 기록된 [최종 runtime 감사](../output/t03-script-context-review-4b/runtime/final-integrity-audit.json)는 `verified=true`다. 정리 전후의 기존 컨테이너 7개·이미지 15개·볼륨 35개가 개수뿐 아니라 identity 집합까지 정확히 같고, 추가·제거된 기존 자원은 없다. source artifact 8개의 SHA-256은 시작 시점 및 이전 9B 최종 기록과 일치한다. 기존 source/draft/packet/control 입력과 9B 동결 파일도 보존되었다.

실제 호출 23회(정식 21·smoke 1·control 1)의 요청은 9B와 `model` 필드 외에 동일하며, 서버 release 23건 모두 `truncated=0`이다. 고정 모델·이미지·GPU, 텍스트 전용, context 32,768, cache 0, context shift 비활성화와 읽기 전용 모델 mount를 확인했다. 모델 파일은 시작 전에 전체 SHA-256을 확인했고, 종료 후에는 크기와 읽기 전용 mount를 확인했으며 전체 파일을 다시 해시하지는 않았다. Thinking 2,048은 설정값이며 실제 reasoning 토큰 수를 별도로 검증한 값이 아니다.

이 감사는 실행·보존 정합성 검사다. 구조상 valid였지만 잘못된 Figure 제안을 놓친 4B control 결과를 의미적으로 통과한 것으로 바꾸지 않는다. 새 NVFP4 후속 실험의 완료나 자원 상태를 포함하는 기록도 아니다.

## 최종 문서 및 파일 검증

- 2026-09-10 19:52:42 KST, `python -X utf8 -B tools/validate_bundle.py --json`을 **정확히 한 번** 실행했다. Validator exit 1, 전체 상태 `failed`, 오류 11개다. [이번 원문 출력](../output/t03-script-context-review-4b/document-validation-complete.json)을 exclusive create로 보존하고 [이전 9B 완료 시점 출력](../output/t03-script-context-review/document-validation-complete.json)과 오류 문자열 집합을 비교했다. 기존 raw Markdown 표 delimiter 오류 11개와 정확히 같으며 **신규 오류 0·제거 오류 0**이다. 따라서 전체 문서 검사 통과라고 표시하지 않는다.
- 새 실행 도구와 비교기 2개의 Python AST 파싱이 성공했다. metrics가 결속한 231개 파일의 SHA-256 불일치는 0이며 현재 comparator 해시도 기록과 일치한다. [compact verification](../output/t03-script-context-review-4b/verification.json)에 실제 interpreter·명령·exit code·실행 시각·오류 집합 비교·해시를 보존했다. 기존 source나 문서를 검사를 통과시키려고 수정하지 않았다.

이는 NVFP4 후속 문서 작업 전의 **4B 완료 시점** 검사다. 이 결과를 이후 NVFP4 문서·모델 실행의 검증으로 재사용하지 않는다. 위 확인 뒤에는 본 계획에 결과만 기록했으며 validator를 다시 실행하지 않았다. AST·문서·파일 해시 확인은 모델 의미 평가나 앱/PG integration 테스트가 아니다.
