# 로컬 모델 문맥 묶음 비교 — 2026-09-10

이 보고서는 **원문 I를 보존한 I2K 입력용 그룹 제안**을 비교한다. 원문 D2I·DB·K 생성·제품 모델 기본값은 변경하지 않았다. 구조화 출력의 유효성과 실제 문맥의 정확성을 구분한다.

**세 모델 모두 이번 전체 논문 입력에서 Figure·소절 단위 묶음을 자동 확정할 수준에는 도달하지 못했다.** [모델별 판정과 원문 오류 사례](FINDINGS.md)를 수치와 함께 읽는다.

## 입력과 조건

- 실제 논문은 이미 검토한 Test_Paper 1개다. image200 source I 229개(Text193/Image36)의 exact content·page·source_type을 짧은 정수 ID와 함께 제공했다. 이미지 pixels·bbox·검토된 정답 그룹은 모델 입력에 넣지 않았다. 원본 UUID·bbox·raw locator·hash는 source-map에 보존했다.
- Markdown은 코드 fence, 짧은 제목, main/supplementary Figure 다대다 참조를 포함한 합성 문서 3개(12/21/17행)다. 정답은 채점기에만 전달했다. Setext·전체 heading 계층·실제 이미지 이해는 미평가다.
- 같은 RTX 5080에서 순차 실행했다. llama.cpp b10380, context32768, parallel1, temperature0, seed42, thinking budget2048, 전체 출력8192, prompt cache off, context shift off. 실제 tokenizer preflight와 응답 usage를 기록했다.
- 기본 방식은 각 그룹이 source ID 목록을 반환한다. 후속 고정 ID 방식은 모든229개 key를 required로 강제하고 각 ID의 group_id를 선택하게 한다. 이 후속 방식에는 subsection 구분 지시도 재강조했으므로 schema만의 단일변수 비교는 아니다.
- 모델마다 기본 방식 4case×3회, 후속 방식 논문1case×3회: **정식45회**. 별도 smoke3회는 점수에서 제외했다. 실험 파일을 제외한 source/canonical writes는0이며 외부 inference provider 호출도0이다.
- 9B Q8은 Unsloth GGUF이고 E4B Q4는 Google QAT GGUF다. 모델 규모·가중치·양자화가 함께 다른 실행 조합의 비교다.

## 기본 방식: ID 목록을 모델이 다시 출력

| 모델 | 논문 구조 통과 | 누락 ID¹ | 중복 ID¹ | 논문 시간 중앙값 | Markdown 구조 통과 | Markdown 정확한 분할·kind |
|---|---:|---:|---:|---:|---:|---:|
| Gemma 4 E4B Q4_0 | 0/3 | 50 | 11 | 26.15초 | 9/9 | 3/9 |
| Qwen3.5-4B Q4_0 | 0/3 | 6 | 138 | 37.56초 | 6/9 | 3/9 |
| Qwen3.5-9B Q8_0 | 3/3 | 0 | 0 | 46.27초 | 9/9 | 3/9 |

¹ 첫 반복에서의 서로 다른 ID 수다. 상세 반복별 값은 metrics.json에 있다. 구조 실패 출력의 문맥 점수는 정상 품질 점수에 섞지 않았다. 빠른 실패가 더 좋은 성능을 의미하지 않는다.

## 후속 방식: 고정된 ID에 그룹 소속을 배정

| 모델 | 구조 통과 | 그룹 수² | 본문 pair P | 본문 pair R | 본문 pair F1 | Metadata F1 | 시간 중앙값 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Gemma 4 E4B Q4_0 | 0/3 | — | — | — | — | — | 34.31초 |
| Qwen3.5-4B Q4_0 | 3/3 | 15 | 0.501 | 0.626 | 0.556 | 0.627 | 31.88초 |
| Qwen3.5-9B Q8_0 | 3/3 | 7 | 0.239 | 0.893 | 0.377 | 0.992 | 60.02초 |

² 유효한 출력의 그룹 수다. 기준 시안은18그룹(본문17+metadata1)이지만 유일한 합법적 분할은 아니다.

**본문 F1은 검토한 primary103 I의 같은 그룹에 속하는 쌍을 비교한 reference agreement다.** Metadata126 I를 포함하면 metadata 쌍7875개가 본문 쌍430개를 압도하므로 대표 점수에서 분리했다. 이는 의미적 진실·K 정확도·파싱 충실성 점수가 아니다. 원문 근거와 충돌하는 잘못된 소속/Figure 번호도 별도로 검토한다.

## 반복 일치 및 세부 진단

| 모델 | 방식 | case | 유효 출력 | 유효 partition 종류 | 정확한 Markdown 분할 | 본문 F1 |
|---|---|---|---:|---:|---:|---:|
| Gemma 4 E4B Q4_0 | baseline | Test_Paper | 0/3 | 0 | — | — |
| Gemma 4 E4B Q4_0 | baseline | md-fenced-code | 3/3 | 1 | 3 | 1.000 |
| Gemma 4 E4B Q4_0 | baseline | md-main-supplementary-many-links | 3/3 | 1 | 0 | 0.393 |
| Gemma 4 E4B Q4_0 | baseline | md-literal-hashes-short-headings | 3/3 | 1 | 0 | 0.684 |
| Qwen3.5-4B Q4_0 | baseline | Test_Paper | 0/3 | 0 | — | — |
| Qwen3.5-4B Q4_0 | baseline | md-fenced-code | 3/3 | 1 | 3 | 1.000 |
| Qwen3.5-4B Q4_0 | baseline | md-main-supplementary-many-links | 0/3 | 0 | 0 | — |
| Qwen3.5-4B Q4_0 | baseline | md-literal-hashes-short-headings | 3/3 | 1 | 0 | 0.630 |
| Qwen3.5-9B Q8_0 | baseline | Test_Paper | 3/3 | 1 | — | 0.348 |
| Qwen3.5-9B Q8_0 | baseline | md-fenced-code | 3/3 | 1 | 3 | 1.000 |
| Qwen3.5-9B Q8_0 | baseline | md-main-supplementary-many-links | 3/3 | 1 | 0 | 0.393 |
| Qwen3.5-9B Q8_0 | baseline | md-literal-hashes-short-headings | 3/3 | 1 | 0 | 0.769 |
| Gemma 4 E4B Q4_0 | assignment | Test_Paper | 0/3 | 0 | — | — |
| Qwen3.5-4B Q4_0 | assignment | Test_Paper | 3/3 | 1 | — | 0.556 |
| Qwen3.5-9B Q8_0 | assignment | Test_Paper | 3/3 | 1 | — | 0.377 |

같은 설정에서3회 반복한 일치도다. 모든 하드웨어·스케줄·seed·문서에서의 결정론을 입증하지 않는다. 불완전 출력의 반복 일치가 성공으로 집계되지 않도록 유효 출력만 이 표의 hash에 포함했다.

## 검증과 재현

- [전체 metrics](metrics.json): source/request/response/result/scorer hash, invalid diagnostics, primary/metadata/Figure/Markdown 점수, 시간·usage·반복 hash.
- [입력](cases.json), [원문 ID·좌표 매핑](source-map.json), [기본 protocol](protocol.json), [고정 ID protocol](assignment-protocol.json), [계획된 모델·반복](planned-runs.json).
- [기존 두 모델 파일 검증](model-profile.json), [9B 파일·revision·해시 검증](runtime/qwen35-9b-q8/manifest.json).
- [기본 실행 도구](../../tools/run_context_grouping_experiment.py), [고정 ID 실행 도구](../../tools/run_context_assignment_experiment.py), [독립 채점기](../../tools/score_context_grouping_experiment.py). 실제 사용한 source hash는 각 protocol에 기록했다.
- [실제로 평가한 고정 하네스](runtime/frozen/tools/run_context_grouping_experiment.py)와 [고정 assignment 하네스](runtime/frozen/tools/run_context_assignment_experiment.py)는 protocol hash와 일치한다. 평가가 모두 끝난 뒤 현재 tools의 비정상 HTTP 응답 실패 기록 경로만 보완했고, 원래 하네스·요청·응답·점수는 보존했다. [모의 오류 응답6종·실패 receipt12개 검증](failure-receipt-checks.json)은 실제 모델 성능 평가와 별개다.
- [실행 계획·실패·범위](../../progress/T03_context_models_execplan.md). Gemma 서버 재로드 중 health503으로 client가 추론 전 한 번 종료됐고, 로그 보존 후 재시작했다. 이 runtime 준비 실패와 모델 출력 실패를 구분한다.
- 생산 앱·schema·DB는 변경하지 않아 전체 app/PG suite는 반복하지 않았다. T03/T04 acceptance 완료 또는 인간 원문 충실성 승인으로 표시하지 않는다.

## 해석의 한계

이 논문은 이전에 검토한 개발 사례이며 blind holdout이 아니다. 정답 ID·그룹을 모델에 보내지는 않았지만 이 작은 표본의 결과로 모든 논문·언어·문서 길이에 대한 순위를 정할 수 없다. 이번 입력은 전체 논문의 21–22K tokens 수준이며 더 짧은 후보/절 단위 입력의 성능은 별도 실험이 필요하다. 텍스트만 제공했으므로 PDF 원본 이미지를 함께 사용하는 실제 I2K의 멀티모달 품질도 평가하지 않았다.
