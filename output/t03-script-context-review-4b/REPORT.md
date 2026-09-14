# 같은 스크립트 초안에서 4B와 9B 비교

2026-09-10. 사용자 요청에 따라 기존 **Qwen3.5-4B Q4_0**를 직전 **Qwen3.5-9B Q8_0**와 비교했다. 정상 초안의 최종 문맥 구성은 같았지만, 의도적으로 잘못 만든 Figure 캡션 연결을 4B가 놓쳤다. 따라서 문맥 구성의 재현성과 오류 검출의 동등성을 구분해야 한다.

## 동일하게 유지한 조건

Test_Paper.pdf 1편의 229개 source I, 스크립트 초안, 검토 후보, 정책, 출력 스키마, 평가 기준을 이전 9B 실험에서 바이트 그대로 복사했다. 모델명 외 실제 요청 차이가 없도록 비교했다. 스크립트를 다시 조정하거나 4B 응답을 보고 프롬프트를 바꾸지 않았다.

20개 검토 이슈를 7개 입력으로 나눠 3회 반복했다. 총 21회가 정식 비교이며, 실행 확인 1회와 동일한 오류 주입 대조 1회는 따로 기록했다. Context 32,768, thinking budget 설정 2,048, output limit 4,096, temperature 0, seed 42, cache off를 유지했다. Thinking의 실제 토큰 수를 별도로 측정한 것은 아니다.

모델은 후보 검토에 필요한 83개 고유 I의 텍스트·종류·페이지 정보를 받았다. 229개 I 전체의 보존은 스크립트가 담당했다. 원본 페이지와 Figure 이미지의 참조는 보존하지만 이 실험에서 모델에 이미지 픽셀을 전달하지 않았다.

## 정상 초안 결과

| 항목 | 4B Q4_0 | 9B Q8_0 |
|---|---:|---:|
| 정식 호출 구조 검증 | 21/21 | 21/21 |
| 반복 횟수 | 3 | 3 |
| 최종 문맥 그룹 | 매회 19개 | 매회 19개 |
| I 정확히 1회 배정 | 매회 229/229 | 매회 229/229 |
| 누락·중복·알 수 없는 I | 0 | 0 |
| 초안에서 변경한 역할 | Abstract 1개 분리 | Abstract 1개 분리 |
| 추가 경계 병합·미해결 항목 | 0 | 0 |
| 주 평가 대상 103개 I의 pairwise F1 | 0.96635 | 0.96635 |
| 7개 입력을 처리한 1회분 시간 중앙값 | 86.85초 | 486.73초 |

3회 모두 그룹 소속·역할·Figure 참조·전체 Figure companion 정보가 9B와 같다. Abstract, Introduction, Results 소절, Discussion, Methods 소절 등의 구성도 같다. 기존 [문맥 그룹 상세](../t03-script-context-review/CONTEXT_GROUPS.md)를 그대로 비교 자료로 사용할 수 있다.

사전 probe 18개 중 16개를 양쪽이 통과했다. 나머지 2개는 Figure 1 관련 실제 두 소절을 한 그룹에 넣는 수동 참조 묶음의 선호와 다르기 때문이다. 원문 누락이나 28개의 의미 오류로 해석하지 않는다. 스크립트만으로도 primary pairwise F1은 같았고, 모델의 관찰된 개선은 metadata에 있던 Abstract를 별도 역할로 분리한 것이다.

전체 응답이 같은 것은 아니다. 정식 결정 60개에서 행동은 **60/60**, 근거 ID 집합은 **30/60**, 근거 배열 순서까지는 **24/60**, 이유 코드는 **33/60** 일치했다. 4B 내부의 3회 최종 projection은 반복 일치했지만 9B의 전체 projection과는 검토 기록이 다르다.

## 오류를 넣었을 때의 차이

9B에 사용했던 별도 대조 입력과 기대 판단을 그대로 사용했다. 기대 답안은 모델에 제공하지 않았다.

| 의도적으로 넣은 오류 | 4B | 9B |
|---|---|---|
| 페이지를 넘는 한 문장을 잘못 분리 | `merge_previous`: 감지 | `merge_previous`: 감지 |
| Figure 5 후보에 Figure 6의 캡션 계속 부분을 연결 | `keep`: 놓침 | `needs_context`: 감지 |

두 번째 후보는 Figure 5의 source 152에 Figure 6의 continuation 189를 잘못 묶었다. 올바른 Figure 5 continuation 158도 같은 입력에 있었다. 4B는 근거로 152와 158을 선택했지만 **판단은 `keep`**으로 반환했다. 근거 선택이 맞았다고 잘못된 후보 연결이 수정된 것은 아니다. 이 출력 계약에서 `keep`은 기존 후보를 유지한다.

결과는 **4B 1/2, 9B 2/2**다. 한 번 실행한 두 대조 사례의 관찰이며, 일반 정확도 50%와 100%라는 뜻은 아니다. 9B도 두 사례에서 오류를 감지했을 뿐, 모든 잘못된 연결을 자동 수정할 수 있다고 입증한 것은 아니다. 정식 21회 점수와 합산하지 않았다. 실패 출력은 재시도·수정 없이 보존했다.

## 이유 코드와 속도의 해석

이전 9B 평가에서 추가한 동일 진단으로 4B의 이유 코드 15/60개가 이슈 유형과 맞지 않았으며, 확정 판단에 `insufficient_context`를 붙인 경우도 9/60개였다. Abstract 판단에 `front_metadata`를 붙인 추가 문제는 [독립 검토](FINDINGS.md)에 별도로 기록했다. 양쪽 모두 이유 코드 자체를 신뢰할 수 있는 검증 근거로 취급하기 어렵다.

정식 21회의 입력 처리 시간을 더하면 4B는 260.55초, 9B는 1,482.78초였다. 호출별 중앙값은 12.41초와 71.16초다. 이는 실제 관찰값이며, 모델 크기만의 속도 차이가 아니다. 4B는 Q4_0, 9B는 Q8_0이고, 시작 시 GPU 부하도 10%와 91%로 달랐다. 모델 로딩, 실행 사이의 대기, 별도 smoke/control은 이 시간 합계에서 제외했다.

## 판단과 적용 범위

스크립트가 대부분의 구조를 확정하고 모델이 제한된 후보를 검토하는 현재 방식에서는 4B도 정상 초안의 같은 문맥 구성을 만들었다. 그러나 이번 오류 대조의 실패 때문에 **4B가 9B와 동등한 오류 검증기라는 결론은 내릴 수 없다.**

Figure 번호·caption/continuation 소속처럼 명시적인 값의 불일치는 스크립트 검사로 다룰 수 있는 후보이며, 의미적인 경계 검토와 구분할 필요가 있다. 이 보고서는 그 추가 검사나 자동 모델 승격 정책을 구현·선정한 것이 아니다. `keep`에도 오류 누락이 있었으므로 `needs_context`가 나온 경우만 큰 모델에 보내는 정책으로 이번 실패를 잡을 수 있다고 주장하지 않는다.

이 실험은 이미 알려진 논문 1편, 고정 후보 20개, 텍스트 입력의 비교다. 다른 논문, 후보로 수집되지 않은 경계, 파서/OCR의 문자 정확도, 실제 이미지 이해, I2K의 K 생성 품질은 검증하지 않았다. D/I/원본 이미지와 과거 9B 결과는 유지하고, DB·canonical·제품 기본값·T03/T04 acceptance 상태를 바꾸지 않았다.

## 실행·검증 기록

아래 Python 명령은 호스트의 Codex Python runtime에서 `-X utf8 -B`로 실행했다. 모델 호출은 고정된 기존 llama.cpp/Python Docker 이미지로 수행했다.

- `python tools/run_script_review_comparison.py prepare --root output/t03-script-context-review-4b`: exit 0. 동일 입력과 모델 선택만 바꾼 동결 runner 준비.
- `python output/t03-script-context-review-4b/check_comparison_transport.py`: exit 0, CPU 검사 8개 통과. HTTP mock이며 모델·DB 호출은 없다.
- `./output/t03-script-context-review-4b/runtime.ps1 -Mode server|smoke|run|control`: 각 mode를 별도로 실행했다. 실행 확인·정식·대조 client 모두 exit 0. 형식상 유효한 응답과 의미적인 대조 실패는 구분한다.
- `python tools/compare_script_review_models.py`: exit 0. 기존 평가기와 결속된 독립 비교를 수행하고 [metrics.json](metrics.json), [EVALUATION.md](EVALUATION.md)를 생성했다.
- `./output/t03-script-context-review-4b/runtime.ps1 -Mode cleanup`: exit 0. 이번 실험 라벨을 확인한 임시 컨테이너 4개만 로그를 보존하고 제거했다. 모델 다운로드나 새 이미지 생성은 없다.

하네스 변경은 [비교 runner](../../tools/run_script_review_comparison.py)와 [독립 비교기](../../tools/compare_script_review_models.py)이며 애플리케이션 소스는 변경하지 않았다. 전체 앱 또는 PostgreSQL integration 테스트의 결과가 아니다. 최종 원본·Docker 감사와 문서 검사 결과는 [실행 계획](../../progress/T03_script_context_review_4b_execplan.md)에 기록한다.
