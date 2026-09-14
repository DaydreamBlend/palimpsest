# T03 후속 — Gemma 4 제목 계층 로컬 실험

실행일: 2026-09-09. 상태: **E2B·E4B·추가 요청한12B 비교 완료.** 12B Q4는 RTX5080 16GB에서 실행 가능했지만 이번 입력·정책·runtime에서는 E4B보다 나은 계층 품질을 보이지 않았다. 실험 기본값은 E4B/thinking/v2로 유지한다. 어느 모델도 완전한 절 복원 품질을 입증하지 못했다.

## 실험 범위와 원문 보존

사용자는 E2B 시험과 성능 부족 시 E4B 다운로드·비교를 승인했다. 이 실험은 MinerU가 검출한 제목들의 계층과 역할을 분류하는 **비canonical projection**이다. PDF 전체 독해, 이미지 이해, I2K 지식 생성 성능 시험은 아니다. D2I의 결정적 source I 생성 정책은 유지하고 앱·DB·canonical 문서·migration은 변경하지 않았다. 추가 논문도 source DB에 새로 등록하지 않고 offline parser 산출물만 만들었다.

Test_Paper의 기존 MinerU 3.4.5 middle JSON을 재사용했다. 허용받은 Desktop/졸업논문 참고문헌에서 MCM 제조법.pdf와 Penteado et al., Immunology, 2017.pdf를 골라 같은 MinerU 이미지의 local pipeline으로 파싱했다. 입력 PDF는 읽기 전용 mount이며 외부에는 공개 모델 다운로드 요청만 보냈다.

## 입력과 기준

| 문서 | 페이지 | MinerU 제목 후보 | 레벨 채점 대상 | 부모 채점 대상 | 제목 후보 단계의 한계 |
|---|---:|---:|---:|---:|---|
| Test_Paper | 14 | 27 | 23 | 22 | 출판 metadata 4개의 레벨·부모는 모호하여 제외하고 역할만 채점 |
| MCM 제조법 | 15 | 29 | 26 | 25 | 실제 제목 3개가 text로 분류되어 입력에서 빠짐; 그림 표제 3개가 title로 포함됨 |
| Penteado 2017 | 10 | 28 | 28 | 27 | 독립 기대치의 제목 28개 모두 입력과 대응 |

기대 계층은 독립 agent가 모델 출력을 보기 전에 원문과 레이아웃을 검토해 동결했다. 사람 승인 gold가 아니다. Test_Paper의 문서 제목=1, 본문 주절·독립 후주=2, 소절=3이라는 공통 표기 규칙으로 매핑했다. Test_Paper는 역할27개도 평가한다. MCM 그림 표제3개는 계층 점수의 분모에 섞지 않고 별도 제외 정확도로 평가한다.

- [Test_Paper 사전 기대치](../output/t03-e2b/review/Test_Paper_expected.json)
- [추가 PDF 선정과 검토](../output/t03-e2b/review/additional_selection.md)
- [MCM 사전 기대치와 입력 매핑](../output/t03-e2b/review/mcm_fixture_mapping.json)
- [Penteado 사전 기대치와 입력 매핑](../output/t03-e2b/review/penteado_fixture_mapping.json)

## 방법

기존 llama.cpp CUDA b10380 이미지를 재사용했다. RTX 5080에서 text-only GGUF를 실행했고 ctx8192/parallel1/temperature0/seed42/max_tokens4096을 사용했다. JSON Schema는 모든 입력 title_id를 정확히 한 번 요구하며 원문 텍스트를 다시 생성하지 않는다. level과 role을 검사한 뒤 부모 관계는 Python 스택으로 결정적으로 계산한다. 입력에는 제목 텍스트·line height·페이지를 전달하고 정답은 전달하지 않았다.

E2B/E4B 각 조건을 3회 반복했다. 추가12B의 반복 횟수는 해당 결과 표에서 구분한다. `cache_prompt=false`이며 response에 별도 reasoning 본문이 오면 저장 전 제거하고 길이만 기록했다. thinking 여부, 입력 hash, request, schema, 최종 응답, token usage, latency와 실패를 남겼다. 각 run 입력 hash와 사전 fixture 입력 hash를 채점 전에 대조한다. 동일 결과 3회는 이 하드웨어·모델·입력·설정의 관찰이며 범용 결정론을 보장하지 않는다.

세 가지 prompt 조건을 보존했다.

1. **mineru**: 설치된 MinerU 3.4.5의 `_build_title_optimize_prompt` 결과를 그대로 사용한다. 단, local 서버·temperature0·스키마 제약·thinking 설정은 이 harness의 것이므로 MinerU의 선택적 LLM 기능 전체를 기본 설정으로 실행한 결과가 아니다. upstream prompt는 레벨1–4를 요구하고 article-root convention을 별도로 강제하지 않아 절대 레벨 점수의 직접 비교에도 한계가 있다.
2. **structured v1**: article title, publisher metadata, body, back matter를 분리한다. Test_Paper non-thinking의 의미 오류를 확인한 뒤 thinking을 켰다.
3. **structured v2**: v1의 Abstract 모호성을 본 뒤 Abstract/Summary를 body level2로 명시하고 figure panel/table cell/running header에 `non_outline=0`을 허용했다. **동일 개발 PDF에서 지침을 보완한 결과이며 blind holdout 성능이 아니다.** 원본 기대치를 사전 동결했다는 사실과 별개다.

## E2B 관찰

| 조건·문서 | 레벨 일치 | 부모 일치 | 그림 표제 제외 | 응답 시간 중앙값 |
|---|---:|---:|---|---:|
| v1 non-thinking · Test_Paper | 17/23 | 7/22 | 대상 없음 | 3.31초 |
| v1 thinking · Test_Paper | 23/23 | 22/22 | 대상 없음 | 11.51초 |
| v1 thinking · MCM | 25/26 | 24/25 | schema에 비제목 역할 없음 | 13.28초 |
| v1 thinking · Penteado | 28/28 | 27/27 | 대상 없음 | 9.44초 |
| v2 thinking · Test_Paper | 23/23 | 22/22 | 대상 없음 | 13.50초 |
| v2 thinking · MCM | 26/26 | 25/25 | 0/3 | 11.91초 |
| v2 thinking · Penteado | 28/28 | 27/27 | 대상 없음 | 11.65초 |

각 행의 세 반복에서 점수와 출력 mapping이 같았다. v2의 실제 제목77/77과 부모74/74는 높지만 완전한 절 목록 복원을 뜻하지 않는다. MCM의 `(a) CONTROLS`, `(b) LINEAGE RESTRICTED ANTIGENS`, `(c) COSTIMULATORS / ADHESINS`는 v2에서도 본문 하위절로 남았다. 이 오류 때문에 사용자 승인 조건을 적용하여 E4B로 같은 v2 입력을 비교한다. Test_Paper non-thinking은 OPEN ACCESS를 논문 제목으로 취급하고 Methods 소절의 부모도 잘못 연결하므로 이 조건을 채택할 근거가 없다.

[E2B 원래 조건 점수](../output/t03-e2b/e2b-initial-scores.json)와 [v2 및 비제목 지표를 추가한 점수](../output/t03-e2b/e2b-v2-scores.json)에 모든 오답을 보존했다.

## E4B 비교

공식 파일을 다운로드한 뒤 크기·SHA를 확인하고, **E2B v2와 model 별칭을 제외한 request 전체가 동일함을 프로그램으로 대조**했다. 각 문서3회, 총9회의 E4B 응답은 모두 구조 검사를 통과했고 문서별 출력은 매회 동일했다.

| 문서 | E4B 레벨 일치 | E4B 부모 일치 | 그림 표제 제외 | E2B v2 시간 | E4B 시간 |
|---|---:|---:|---|---:|---:|
| Test_Paper | 23/23 | 22/22 | 대상 없음 | 13.50초 | 16.71초 |
| MCM 제조법 | 26/26 | 25/25 | 3/3 | 11.91초 | 15.66초 |
| Penteado 2017 | 26/28 | 25/27 | 대상 없음 | 11.65초 | 19.02초 |

시간은 각3회의 요청 벽시계 중앙값이며 파싱·모델 다운로드·서버 로딩은 포함하지 않는다. E4B는 실제 제목75/77, 부모72/74를 맞췄다. MCM의 비제목 표제는 모두 level0/non_outline으로 제외했지만 Penteado의 `Generation of bone-marrow-derived dendritic cells`와 `Generation of sterile ACs and IACs`를 Methods(level2)의 소절(level3)이 아닌 앞선 `Mice` 소절의 하위(level4)로 중첩했다. E2B v2는 두 경우의 계층을 맞췄다.

원문 재확인에서도 세 소절은 물리2쪽(인쇄305쪽)의 같은 x0=305.291pt, 폰트GHLEOE+AdvMINION-I, 크기9.963pt이며 추가 들여쓰기가 없다. `Materials and methods`는 다른 굵은 폰트다. [해당 원문 페이지 렌더](../output/t03-e2b/review/penteado-hierarchy-page.png)를 보존했고 사전 기대치는 수정하지 않았다.

반면 모델에 전달한 MinerU `line_height`는 세 소절이 각각12.0·9.0·10.0이다. 이 값은 원문 글꼴 크기와 같지 않으므로 서식의 대용치로만 사용해야 한다. 추가 PDF 추출은 원문 QA에만 사용했으며 앱 parser를 대체하지 않았다.

따라서 **큰 모델이 일관되게 우월하다는 결론은 아니다.** E4B로 후속 실험을 진행할 준비는 되었지만 제목·높이·페이지만으로 논문 전체 절 구조를 자동 확정할 근거는 부족하다. E2B/E4B 조건을 합친39회 추론은 JSON 구조 검사에 통과했고 각 조건3회 결과가 같았으나 의미 오류도 같은 형태로 반복됐다. [당시 점수와 오답](../output/t03-e2b/final-scores.json), [당시 입력·request·모델·코드 해시 프로필](../output/t03-e2b/runtime-profile.json)을 보존했다.

## 추가 요청한 Gemma 4 12B

사용자가 “Gemma4 12B는 너무 큰가? 그래도 이걸로도 실험 한번 부탁할게.”라고 요청해 동일3편의 비교를 추가했다. 공식 QAT Q4_0 파일6,975,879,296bytes를 검증해 기존 CUDA 이미지에서 로딩했다. 서버 로그상 로딩32.87초, ctx8192/parallel1/RTX5080이며 RTX4060Ti는 이 LLM 실행에 쓰지 않았다.

**현재 하드웨어에 지나치게 큰 모델은 아니다.** 실행 중 전체 RTX5080 메모리 표본은9,610·9,635·9,644MiB /16,303MiB였다. 기존 서비스가 함께 있으므로 모델 단독 사용량이나 peak가 아니다. container memory 표본은7.818GiB이며 마지막 서버 상태에서 OOMKilled=false였다. 이 결과를 BF16, 256K 문맥, 이미지 입력, 대량 동시 요청에 확대 적용하지 않는다.

먼저 E4B와 model 별칭만 다른 thinking/max_tokens4096 조건을 Test_Paper에서3회 실행했으나 모두46초대에 `finish_reason=length`로 끝났고 최종 content는 비어 있었다. 따라서 미완료로 남겼다. 같은8K 문맥에서 출력만6144로 늘린 탐색 시험도3편 각각1회 수행했지만 모두69~70초 후 같은 이유로 미완료였다. 판단 오류로 기각하거나 성공으로 강제 처리하지 않았다. 이는 해당 runtime/template/profile의 관찰이며 모든12B runtime의 고유 성능이라고 단정하지 않는다.

다음으로 non-thinking을3회씩, 별도 thinking 예산2048/전체출력4096을1회씩 시험했다. 후자는 [b10380의 공식 요청 필드](https://github.com/ggml-org/llama.cpp/blob/b10380/tools/server/server-common.cpp#L1050) `reasoning_budget_tokens`를 사용해 최종 JSON 출력 여유를 남긴 구성이다. prompt·schema·seed·temperature·입력은 그대로이고 모델·thinking·출력 한도·thinking 예산 외에는 request가 같음을 프로그램으로 대조했다.

| 12B 설정·문서 | 반복 | 레벨 일치 | 부모 일치 | 그림 표제 제외 | 요청 시간 |
|---|---:|---:|---:|---|---:|
| non-thinking · Test_Paper | 3 | 19/23 | 18/22 | 대상 없음 | 6.54초 중앙값 |
| non-thinking · MCM | 3 | 26/26 | 25/25 | 3/3 | 9.61초 중앙값 |
| non-thinking · Penteado | 3 | 21/28 | 20/27 | 대상 없음 | 6.74초 중앙값 |
| thinking2048 · Test_Paper | 1 | 23/23 | 22/22 | 대상 없음 | 30.07초 단일 측정 |
| thinking2048 · MCM | 1 | 26/26 | 25/25 | 3/3 | 33.09초 단일 측정 |
| thinking2048 · Penteado | 1 | 19/28 | 18/27 | 대상 없음 | 32.76초 단일 측정 |

non-thinking은66/77 레벨·63/74 부모로 빠르지만 계층 품질이 낮았고, thinking2048도68/77·65/74로 E4B의75/77·72/74보다 낮았다. 두12B 설정은 MCM의 그림 표제3개를 제외했지만 동급 소절을 과도하게 중첩하는 오류가 남았다. non-thinking의 Test_Paper OPEN ACCESS 역할도 사전 기대치front_matter 대신non_outline이었다(역할26/27). 원문을 삭제한 오류는 아니지만 역할 일치로 계산하지 않는다.

non-thinking의 문서별3회 출력은 같았다. thinking2048은 각 문서1회이므로 반복 일관성을 검증했다고 말하지 않는다. 동일 개발 문서에서 실행 설정을 보완한 시험이며 새로운 holdout도 아니다. 전체 실험은57회(구조 유효51/출력 미완료6)다. [모든 모델의 최종 점수](../output/t03-e2b/final-all-model-scores.json), [12B 포함 해시·조건 프로필](../output/t03-e2b/runtime-profile-12b.json), [12B 실행 설정](../output/t03-e2b/runtime/12b-server-config.json), [서버 props](../output/t03-e2b/runtime/12b-server-props.json)를 보존했다.

이번 결과만으로12B를 기본 절 보조 모델로 올릴 근거는 부족하다. E4B 실험 기본값을 유지하고 다음 개선은 raw 후보 coverage·좌표·서식·주변 Figure 근거를 입력에 반영하는 쪽으로 둔다. 모델 파일은 재시험 가능하게 남겼다.

## 모델·런타임 고정

| 모델 | 공식 revision | 파일 | bytes | SHA-256 |
|---|---|---|---:|---|
| E2B | 675cff42a74c774d6cb76f76d8eacb49b48c9b93 | gemma-4-E2B_q4_0-it.gguf | 3349516256 | fa401b55b07ee70a54c6dae3903c783a6e65064312529ea57175cb5f8dec6634 |
| E4B | 4b4a2c1d584be7264f87aac328a1bc739ce81b6c | gemma-4-E4B_q4_0-it.gguf | 5154941280 | 676c35070db6dbe52f93e9c864ee0fba4eddea94b9c875d9cb10daff453fbaee |
| 12B | 29d097773436b69ff9feafd636ab4cf873786537 | gemma-4-12b-it-qat-q4_0.gguf | 6975879296 | 93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b |

E2B/E4B 모두 다운로드 완료 후 실제 파일 크기·SHA를 공식 LFS 값과 대조해 일치했다. 각 공식 Google [E2B 모델](https://huggingface.co/google/gemma-4-E2B-it-qat-q4_0-gguf/tree/675cff42a74c774d6cb76f76d8eacb49b48c9b93), [E4B 모델](https://huggingface.co/google/gemma-4-E4B-it-qat-q4_0-gguf/tree/4b4a2c1d584be7264f87aac328a1bc739ce81b6c)을 받았고 mmproj는 받지 않았다. effective parameter 수와 GGUF 저장 크기는 다르므로 E2B/E4B 이름을 전체 저장 파라미터 수로 해석하지 않는다.

추가 [12B 공식 파일](https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf/tree/29d097773436b69ff9feafd636ab4cf873786537)도 실제bytes/SHA를 대조했다. 12B의 mmproj는 받지 않았다.

- llama.cpp image: `sha256:a50b12bb92de0253d2737824ca1887f410e07b4dd3e3028f74a5a0a67c789e4b`, b10380, commit `0b1bad14ff204627636aeb1de22ddcd5acb859d4`.
- MinerU image: `sha256:fdab78016483e1dbf0f416c9f74941a1242a91dae58fa2cc9617488ceb338854`, distribution3.4.5.
- HTTP client image: `palimpsest-t03:0.2.0`, `sha256:594c68dcf8b7ebab5461f45a041e78dce407b8c44368aabc645978c268ceb528`.
- `/props`의 inherited sampling: top_k64, top_p0.95, min_p0.05, repeat_penalty1.0; request temperature0과 seed42가 server 기본값을 덮어쓴다. 공식 권장 temperature1.0의 모델 성능 시험은 아니다.
- [E2B 실행 인자·mount·GPU·network](../output/t03-e2b/runtime/e2b-server-config.json), [서버 props와 실제 chat template](../output/t03-e2b/runtime/e2b-server-props.json).
- [E4B 실행 설정](../output/t03-e2b/runtime/e4b-server-config.json)과 [E4B props](../output/t03-e2b/runtime/e4b-server-props.json)도 보존했다. 모델별 inherited sampling이 동일함을 확인했다.
- 저장한 표본의 전체 RTX5080 사용은 E2B 실행 중3,805MiB, E4B 실행 중5,259MiB였다. container 메모리 표본은 각각1.944GiB/2.893GiB다. 기존 GPU 서비스가 함께 존재하므로 모델 단독 사용량·증분의 정확한 인과효과·peak로 해석하지 않는다.

## 실행·검증·정리

실행 도구는 [run_title_experiment.py](../tools/run_title_experiment.py)다. 추가 앱 의존성 없이 stdlib를 사용하고 prepare만 고정된 MinerU 이미지 내부의 설치 package를 호출한다.

```text
python tools/run_title_experiment.py check
python tools/run_title_experiment.py score --root output/t03-e2b --output output/t03-e2b/final-scores.json
python tools/run_title_experiment.py score --root output/t03-e2b --output output/t03-e2b/final-all-model-scores.json
python tools/validate_bundle.py
```

현재 host의 Python PATH 대신 `C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`를 사용한다. 각 run의 `request.json`과 서버 설정 파일로 정확한 추론 요청을 복원할 수 있다. v2 실행 코드는 `output/t03-e2b/runtime/harness-v2-executed.py`에도 고정했다. 초기 v1 실행 당시 harness 전체 hash는 기록하지 못했으며, 정확한 request·input·upstream module hash와 최종 출력으로 추적한다.

E4B 실행 코드는 `runtime/harness-e4b-executed.py`에 별도로 고정했다. 최종 도구의 `run` 기본값은 `--model gemma4-e4b-headings --policy-version v2 --thinking --base-url http://127.0.0.1:8080`이다. 기존 E2B/non-thinking 조건을 재현하려면 `--model gemma4-e2b-headings --policy-version v1 --no-thinking`을 명시한다. Docker 내부 전용 network의 server namespace에서 client를 실행하는 로컬 실험용 기본값이며 Palimpsest 앱 D2I 기본값 변경이 아니다.

12B 세 실행 코드도 `runtime/harness-12b-*-executed.py` 및 `harness-12b-executed.py`에 보존했다. 최종 harness는 `--max-tokens`(기본4096), `--reasoning-budget`(미지정이면 원래서버설정)를 받아 실험 조건을 숨기지 않고 request와run에 기록한다. 출력이 이미 있으면 덮어쓰지 않으므로 재시험에는 새 output 경로가 필요하다. 음수 reasoning budget과 thinking을 끈 상태의 reasoning budget은 거부한다.

첫 bundle 검사는 외부 모델 README의 빈 표 셀8개 때문에 exit1이었다. 외부 모델 카드 bytes는 변경하지 않고 `.txt`로 보관하여 저장소가 작성한 Markdown과 구분한다. Penteado 첫 mount의 exit125와 재시도 exit0, 모델 다운로드의 Windows chmod 경고도 로그로 남긴다. 앱 코드·문서 validator 구현이 바뀌지 않아 기존 앱202개와 validator43개 suite는 이번 실험에서 재실행하지 않았다. 실험 check와 직접 bundle 검사는 별도 기록한다. 새 application AT를 통과 처리하지 않는다.

최종 `check`와 전체모델 `score`는exit0, bundle검사는exit0/오류0이었다. 다른 input hash를 넣은 run이 채점 전에 거부되는 negative integrity smoke도 통과했다. 실제명령과로그는 [실행 계획](T03_e2b_execplan.md)에 있다.

완료 후 E2B/E4B 서버를 종료·자동 제거하고 다운로드·parser/client 컨테이너는 `--rm`으로 제거했다. 만든 internal network도 제거했다. 새 Docker 이미지를 만들거나 받지 않았으며 기존 이미지·volume·다른 프로젝트 container 보존을 전후 대조했다. 두 모델 GGUF와 성공·실패 실험 산출물은 재현용으로 유지한다.

추가12B 서버·network도 소유ID/label 확인 후 제거했다. 기존container7개·전체image ID set·volume name set이 그대로이고 실험container0개다. [12B 이후 정리 확인](../output/t03-e2b/runtime/cleanup-12b.json)을 남겼다. 세 모델 GGUF와 실험 결과는 보존한다.

## 최소 후속 과제

MCM의 누락된 3.1·3.3·4.1은 raw text에 그대로 있으므로 title-only 입력에 큰 모델을 붙여도 복원 대상 자체가 없다. 후보를 수집할 때 절 번호로 시작하는 text도 포함하고, bbox·주변 블록 type·인접 Figure caption과 거리 정보를 보존하는 것이 필요하다. 그림 표제 아래3·5·8pt 거리의 image/chart, Fig.2 및 continued caption은 스크립트로 추출 가능한 근거다. 다만 근접성만으로 모든 문서의 소속을 단정해서는 안 된다.

후속 절 projection은 `section_heading / figure_label / uncertain`의 결과를 검증하고, 불확실한 경우 페이지 문맥을 유지할 수 있어야 한다. outline에서 제외해도 source I나 text를 삭제하지 않는다. 원문 후보 coverage와 계층 정확도를 따로 검증하고, 절 경계를 유일한 I2K 입력 경계로 강제하지 않는 것이 이 실험의 다음 구현 방향이다.
