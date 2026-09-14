# Qwen3.5-9B NVFP4 마지막 문맥 검토 비교

2026-09-10 사용자 추가 요청: “9B NVFP4 양자화 있으면 그걸로 마지막으로 실험해줘.” 공개 체크포인트와 현재 RTX 5080 지원을 확인한 뒤, 가능하면 이전 스크립트 초안의 동일 입력으로 비교한다. 이전 4B 실험은 완료했으며 [결과](../output/t03-script-context-review-4b/REPORT.md)를 보존한다.

## 범위

기존 AGENTS/PLANS/T03/T04/I2K_CONTEXT_POLICY와 승인된 원문 보존 규칙을 따른다. HF CLI 및 로컬 평가 스킬을 적용하고, 기존 stdlib 하네스·고정 Docker 이미지를 재사용할 수 있는 경로를 우선한다. 체크포인트의 공개 존재는 실행 성공이나 품질 보증을 의미하지 않는다.

새 산출물은 `output/t03-script-context-review-nvfp4/`에 기록한다. 원본 D/I·8개 source artifact·이전 4B/9B 동결 입력과 결과·DB·canonical을 보존한다. 모델 다운로드는 이번 요청에 포함되며 공개 모델 파일만 받아 원문을 외부 추론 서비스에 보내지 않는다. 사용자가 요청한 마지막 실험 범위에서 실행하고 다른 모델 탐색으로 확장하지 않는다.

## 진행 계획

1. 원본 Qwen3.5-9B의 NVFP4 checkpoint를 확인하고 정확한 repository/revision/파일 크기/SHA를 고정한다. 모델 카드의 주장과 실제 tensor 형식·chat template을 구분한다. 다른 fine-tune 또는 Q4 파일로 대체하지 않는다.
2. 현재 llama.cpp b10380의 NVFP4/SM120 지원을 검토한다. 동일 runtime을 사용할 수 있으면 기존 context 32,768/thinking 설정 2,048/output 4,096/temp 0/seed 42/cache off를 유지한다. Native FP4 연산 경로와 NVFP4 저장 형식은 구분해 보고한다.
3. Docker/source baseline을 기록하고 다운로드 파일의 전체 해시 및 실제 GGUF metadata/tensor 종류를 확인한다. 모델과 필요한 실험 출력만 마운트한다.
4. 이전 source/draft/7 packets/평가 기준/별도 2-fault control을 바이트 그대로 사용한다. Smoke 1회 후 정식 7 inputs × 3 repeats와 동일 control 1회, 총 23회를 실행한다. Prompt 조정·실패 재시도로 결과를 바꾸지 않는다.
5. 그룹·229 I coverage·Figure companion·60 decisions·근거·이유 코드·control 오류 검출·시간을 9B Q8_0 및 4B Q4_0 결과와 비교한다. 모델 변환자, 양자화, template/tokenizer, GPU 부하 차이를 기록한다.
6. 독립 검증 후 이번 임시 컨테이너만 로그를 보존하고 정리한다. 새 이미지가 필요하면 provenance와 사용 여부를 기록하고 불필요한 이번 실패 자원만 제거한다. 기존 컨테이너·이미지·볼륨은 유지한다.

## 현재 상태

공개 NVFP4 체크포인트와 GGUF 변환 후보를 찾았다. `FreedomAISVR/Qwen3.5-9B-NVFP4-GGUF`는 원본 모델의 F16 변환 후 NVFP4 양자화와 약 5.31 GB text GGUF를 명시한다. 모델 카드만으로 선택을 확정하지 않고 파일 metadata와 runtime 지원을 병렬 확인 중이다. 별도 vLLM/ModelOpt 후보도 존재하지만 현재 runtime 재사용 여부를 먼저 확인한다.

한 논문·고정 후보·text-only context preparation의 실험이다. I2K K 생성, OCR 정확도, 일반적인 모든 논문에서의 성공률 또는 제품 기본값을 승인·구현하는 작업이 아니다.

## 준비 완료

- 공개 NVFP4 GGUF를 repository `FreedomAISVR/Qwen3.5-9B-NVFP4-GGUF`, revision `3db49b5e08fb84a2ead8d6407f38f6638c79d08a`로 고정했다. 파일은 `qwen3.5-9b-nvfp4.gguf`, 5,313,356,640 bytes, SHA-256 `0db703913b6a1b057d423e9815095e9dc16499596a986446918314a48c4d9bad`다.
- 기존 HF CLI Docker 이미지를 재사용해 388.05초에 다운로드했고, 전체 파일 해시가 공개 LFS 해시와 일치했다. 다운로드 컨테이너는 `--rm`으로 종료 시 제거됐다. 새 이미지·mmproj 다운로드 및 사용자 원문 업로드는 없다.
- 기존 `run_script_review_comparison.prepare(root, baseline, 'qwen35-9b-nvfp4')`를 Python에서 호출해 준비했다. 기존 도구 파일을 변경하지 않았으며 새 동결 driver도 4B와 바이트가 같다. 공통 artifact 7개·protocol 조건·동결 해시·Python AST 2개 검사는 통과했다. [준비 검사](../output/t03-script-context-review-nvfp4/runtime/preparation-checks.json)
- 시작 Docker baseline은 7 containers/15 images/35 volumes, 5080은 1,897/16,303 MiB와 25% 사용률이었다. NVFP4 지원 검토에서 고정 llama.cpp b10380의 Qwen3.5 loader 및 SM120 NVFP4 MMQ 경로를 확인했다. 단일 토큰 decode는 별도 MMVQ 경로를 사용할 수 있으므로 전체 native W4A4 실행으로 주장하지 않는다. [고정 소스 검토](../output/t03-script-context-review-nvfp4/runtime/runtime-support.json)
- 커뮤니티 카드의 FP4 설명에는 오류가 있고 원본 모델의 고정 revision·변환 도구 commit도 명시되지 않았다. 파일 해시 검증과 원본 모델 출처의 동일성 보증을 구분한다. 카드의 속도·VRAM 주장은 평가 결과로 사용하지 않는다.

## 실제 모델 확인 및 실행 시작

- [GGUF 독립 비교](../output/t03-script-context-review-nvfp4/runtime/gguf-comparison.json)에서 두 파일의 전체 SHA를 확인했다. 427개 tensor 이름·shape와 8,953,803,264개 파라미터가 같다. NVFP4 파일은 NVFP4 249개, Q6_K 출력층 1개, F32 177개 텐서로 구성된다. 모든 가중치가 FP4인 파일로 표현하지 않는다.
- vocab/merge/token type/EOS/pretokenizer는 같지만 padding ID, add_bos_token 명시 여부, chat template 일부가 다르다. 기존 실제 요청 23개는 모두 user 문자열 메시지 1개·enable_thinking=true·tool_calls 없음이므로 template 변경 분기가 적용되지 않는다는 정적 검토를 남겼다. Jinja 실행 비교를 수행했다고 주장하지 않으며 실제 preflight의 minja/tokenize 결과와 토큰 수를 별도로 비교한다.
- 공통 F32 177개 중 172개는 바이트가 같고, ssm_a 5개 tensor의 float32 값 6개는 각 1 ULP 다르다. 변환 반올림과 일관된 크기이나 출처 revision이 완전히 같다고 확정할 근거는 아니다.
- 서버는 기존 이미지·플래그로 25.215초에 로딩됐고 실제 props에서 model_ftype=NVFP4, alias=qwen35-9b-nvfp4, context=32,768, 모델 경로 일치를 확인했다.
- 제외용 smoke는 exit 0, 구조상 valid, 16.278초, prompt 387/completion 2,094 tokens였다. 판단은 keep/study_overview로 이전 Q8/4B의 needs_context와 달랐다. 실행 확인은 성공했으나 smoke 의미 판단이 같거나 맞았다고 표시하지 않는다.
- 정식 21개 호출을 시작했다. 중간 결과나 이유 코드만으로 최종 품질을 확정하지 않고, 3개 반복 및 별도 control이 끝난 뒤 평가한다.

## 모델 실행 완료

- `./output/t03-script-context-review-nvfp4/runtime.ps1 -Mode server|smoke|run|control`의 각 mode를 별도로 실행했다. 서버·smoke·정식 client·control client 모두 최종 exit 0이다. Smoke를 포함해 실제 모델 호출은 23회이며 재시도는 없다.
- 정식 21/21 응답이 구조상 유효했다. 세 반복 모두 229개 I를 정확히 한 번씩 19개 그룹에 배정했고, 그룹 소속·역할·Figure companion이 9B Q8_0 및 4B Q4_0와 같다. 매회 Abstract I57 분리만 적용했고 미해결·추가 병합·누락·중복은 없다.
- 정식 판단 60개는 양쪽과 같지만 Q8_0 대비 근거 집합/순서 일치는 33/60, 이유 코드는 42/60이다. 실제 캡션 I90/I103/I128을 선택하지 않고 짧은 패널 글자만 반환한 경우를 사후 근거 진단으로 분리했다. 원문 caption I 자체는 입력과 저장에 남아 있다.
- 마지막 control은 구조상 valid지만 의미 기대 판단은 **1/2**다. 실제 문장 분리 오류는 `merge_previous`로 감지했고, 잘못된 Figure 5/6 연결은 `keep`으로 놓쳤다. 이때 evidence `[152,158,183,189]`를 모두 제시했어도 틀린 후보 `[152,189]`를 거부한 것이 아니다. 기존 Q8_0는 2/2, 4B는 1/2다. Control을 정식 점수와 합산하거나 일반 성공률로 표현하지 않는다.
- NVFP4 정식 21회 시간 합계 363.6495초, 호출 중앙값 17.1570초, 세 회차 합계 121.6234/120.8887/121.1375초다. 입력 93,036/completion 45,897/total 138,933 tokens다. 별도 control은 16.8767초/2,559 prompt+2,137 completion tokens다.
- `./output/t03-script-context-review-nvfp4/runtime.ps1 -Mode cleanup`: exit 0. 이번 라벨의 실행 컨테이너 4개만 로그 보존 후 제거했다. 다운로드의 `--rm` 1개를 포함해 이번 임시 컨테이너는 총 5개다. 검증된 NVFP4 파일과 결과는 보존하며 새 Docker 이미지는 만들지 않았다.

## 비교기와 산출물

기존 runner/4B 비교기를 변경하지 않고 [NVFP4 비교기](../tools/compare_script_review_nvfp4.py)만 추가했다. 기존 검증·replay·assess·reason 진단·ledger 비교 함수를 재사용하며 기존 전역값을 바꾸지 않는다. 최종 SHA-256은 `8658a3355b5746e0f38f86593c704fc39fae1ad0fab6017228b800134f9d8e58`이며 실험의 frozen 폴더에도 같은 파일을 보존했다.

독립 검토에서 미완료 projection/normalized 쌍을 완료로 인정하는 경계와 재읽기 hash binding 덮어쓰기를 발견해 새 비교기 안에서 수정했다. Self-check 6건, 잘못된 failure receipt 4건, 실제 reference binding 248개가 통과했고 추가 blocking finding은 없다. 이는 CPU 검사이며 모델·DB 호출이 아니다. 실제 완료 결과는 이후 한 번만 채점해 exclusive 저장한다.

[결과 보고서](../output/t03-script-context-review-nvfp4/REPORT.md), [독립 평가](../output/t03-script-context-review-nvfp4/EVALUATION.md), [정성 검토](../output/t03-script-context-review-nvfp4/FINDINGS.md), [metrics](../output/t03-script-context-review-nvfp4/metrics.json), [최종 projection](../output/t03-script-context-review-nvfp4/final/repeat-1/projection.json)에 실험을 남긴다. docs/INDEX.md와 I2K_CONTEXT_POLICY.md에는 후속 요청과 범위를 연결했고 변경 전 바이트를 새 docs-before에 보존했다.

이번 한 논문의 정상 문맥 구성은 같지만 NVFP4가 Q8_0와 동등한 오류 검증기라고 판단할 수 없다. 제품 기본값은 변경하지 않았으며 T03/T04 acceptance를 승격하지 않는다. 미해결 승인 결정은 없고 추가 모델 실험을 시작하지 않는다. 최종 자원·원본·문서 검사 결과는 다음에 별도로 기록한다.

## 독립 채점 및 최종 보존 감사

- `python -X utf8 -B tools/compare_script_review_nvfp4.py`를 동결된 버전으로 **정확히 한 번** 실행했다. Exit 0이며 metrics/EVALUATION을 exclusive 생성했다. 정식 21/21 valid, 세 반복 complete, 두 비교 대상과 그룹/역할/Figure companion 및 60/60 행동 일치를 확인했다. Control은 구조 valid와 의미 기대 1/2를 구분했다. [CPU 검사 기록](../output/t03-script-context-review-nvfp4/checks.json)
- [최종 runtime 감사](../output/t03-script-context-review-nvfp4/runtime/final-integrity-audit.json)는 verified=true다. 전후 기존 컨테이너 ID 7개·이미지 ID 15개·볼륨 이름 35개의 집합이 정확히 같다. 이번 임시 컨테이너 5개가 모두 부재하며 원본 8개와 세 모델의 동결 입력은 보존됐다.
- 실제 23개 요청은 Q8_0/4B와 model 필드 외에 동일하고, 모두 finish_reason=stop/cache=0/truncated=0이다. 23개 입력의 preflight 토큰 수와 실제 usage prompt 수가 기존 두 모델과 같다. 최대 입력 7,146·출력 2,224·합계 9,362 tokens로 문맥 잘림은 없었다. 실제 모델 format=NVFP4, context=32,768, text-only, 모델 읽기 전용 mount 및 같은 이미지/실행 조건을 확인했다.
- 이 감사는 보존·실행 정합성의 결과다. 잘못된 Figure 연결을 keep한 NVFP4 응답을 품질 통과로 바꾸지 않는다. 추가 모델 호출이나 앱/PG integration 테스트는 실행하지 않았다. 요청된 마지막 모델 비교를 마쳤고 제품 기본값 변경이나 추가 실험을 시작하지 않았다.

## 최종 문서 검사

`python -X utf8 -B tools/validate_bundle.py --json`을 한 번 실행했다. Exit 1, 전체 상태 failed이며 기존 raw Markdown 표 delimiter 오류 11개가 남아 있다. 직전 4B 완료 기록과 오류 문자열 집합이 정확히 같아 신규 오류 0·제거 오류 0이다. 원문 파서 출력을 수정하거나 validator를 느슨하게 하지 않았다. [실제 검사 출력](../output/t03-script-context-review-nvfp4/document-validation-complete.json)

새 비교기 AST 및 동결 SHA 확인이 통과했고 metrics가 결속한 342개 파일의 해시 불일치는 0이다. docs-before와 현재 두 문서의 내용 차이 및 주요 산출물 해시도 [최종 verification](../output/t03-script-context-review-nvfp4/verification.json)에 기록했다. 이 검사 뒤에는 본 계획에 결과만 덧붙였고 동일 검사나 모델 호출을 반복하지 않았다. 전체 문서 검사가 통과했다고 표시하지 않으며 실제 모델 결과·CPU 검사·문서 검사·미실행 앱/PG 테스트를 구분한다.
