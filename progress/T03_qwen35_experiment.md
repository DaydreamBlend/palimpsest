# Qwen3.5-4B 제목 계층 실험

## 범위와 재현 조건

2026-09-09 사용자 요청 “Qwen 3.5 4B로 실험해줘”에 따라 기존 Gemma E4B와 같은 Test_Paper/MCM/Penteado의 고정 MinerU 입력을 로컬에서 비교했다. **Thinking 예산2048/전체출력4096 조건은 9/9회 유효, 제목77/77·부모74/74·그림표제제외3/3으로 기존 E4B보다 좋은 결과를 보였다.** 원문 D2I/canonical I/앱/DB에는 변경이 없다. 결과는 제목 계층 projection이며 I2K 지식 추출 성능이 아니다.

입력은 기존 [Gemma 실험](T03_heading_experiment.md)의 MinerU 3.4.5 산출물이다. Test_Paper 27개, MCM 29개, Penteado 28개 후보의 title_id/text/line_height/page만 전달했다. bbox/raw locator는 증거에 보존하지만 이번 prompt에는 추가하지 않았다. 프롬프트와 정답은 Qwen 결과를 본 뒤 수정하지 않았다.

- 평가 분모: 실제 제목 level 77개, 그 제목들의 root 제외 parent 74개. 두 점수는 독립된 151개 문제의 합계가 아니다.
- MCM의 그림 패널 표제 3개는 outline 제외(level0) 여부를 별도로 평가한다. 전체 role 정답 평가는 Test_Paper 27개에만 있다.
- MCM의 실제 소절 3개가 MinerU title-only 후보에 없다는 기존 한계를 유지한다. source text 소실이 아니라 후보 입력 coverage의 한계다.
- 기대치는 모델 실행 전에 독립 agent가 원문을 검토해 만든 자료이며 사람 승인 gold가 아니다. 세 문서는 v2 prompt 개발에 사용됐으므로 holdout 평가가 아니다.

## 모델과 실행 환경

| 항목 | 고정값 |
|---|---|
| 원본 모델 | `Qwen/Qwen3.5-4B` |
| 양자화 배포자 | `unsloth/Qwen3.5-4B-GGUF` — 제3자 변환 |
| revision | `e87f176479d0855a907a41277aca2f8ee7a09523` |
| 파일 | `Qwen3.5-4B-Q4_0.gguf` |
| bytes | 2,583,221,408 |
| SHA-256 | `298fcb5fe7a77ccc79745ae24751560c5ac56874caff4bb39b1f2055bd72b8bb` |
| 서버 | 기존 llama.cpp b10380 CUDA, `a50b12bb92de0253d2737824ca1887f410e07b4dd3e3028f74a5a0a67c789e4b` |
| GPU | RTX 5080 16GB, CUDA_VISIBLE_DEVICES=0 |
| 문맥·병렬 | 8192 tokens / parallel1 |
| 요청 | v2 / temperature0 / seed42 / max_tokens4096 / cache_prompt=false |
| 출력 | JSON Schema로 정확한 모든 title_id와 level/role 필드 요구; 기존 Python 검증 후 부모 계산 |
| 추가 조건 | thinking 예산 2048, 전체 출력 한도 4096 |

[고정 GGUF 파일](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/blob/e87f176479d0855a907a41277aca2f8ee7a09523/Qwen3.5-4B-Q4_0.gguf)의 metadata SHA와 실제 파일 hash를 대조했다. mmproj는 받지 않았고 text-only로 실행했다. 앞선 Gemma는 Google QAT Q4_0이므로 이름이 같은 4비트라도 양자화 방식이 동일한 비교가 아니다.

[Qwen 공식 카드](https://huggingface.co/Qwen/Qwen3.5-4B)는 thinking을 기본 활성화하고 `enable_thinking=false`로 끄는 방법을 설명한다. 이번 temperature0은 기존 Gemma와의 공통 조건이며 공식 권장 sampling 평가가 아니다. 실제 request가 seed/temperature/max_tokens/schema를 지정한다. 서버 props의 기본 temperature는 Qwen0.8/Gemma1.0이지만 요청0으로 덮어쓴다. top_k 기본은40/64로 다르며 온도0 greedy 비교와 양의 온도 sampling 비교를 구분해야 한다. 그 밖에 top_p0.95/min_p0.05/repeat_penalty1/presence_penalty0/frequency_penalty0 및 sampler 순서는 같다.

서버는 12.779초에 정상 로딩했고 `/health`가 ok였다. 내부 전용 Docker network와 서버 network namespace를 공유하는 local client를 사용했다. 호스트 포트 publish가 없고 논문 내용의 외부 전송은 없다. 별도 API credential은 사용하지 않았다. GPU 전체 사용량은 다른 서비스·화면 프로세스를 포함한 표본이며 모델 단독 peak VRAM으로 해석하지 않는다.

## 실행 기록과 검사 경계

초기 non-thinking Test_Paper는 JSON 자체를 끝까지 출력했지만 `Specialty section:`과 `Citation:`을 role front_matter/level2로 내어 기존 `front_matter_level_mismatch` 검사에 실패했다. 검증기는 front_matter/non_outline을 level0으로 요구한다. 틀린 값을 사후 수정하거나 성공으로 바꾸지 않았다. 초기 smoke runner는 여기서 멈췄고, 실패를 보존한 별도 runner로 비교를 이어갔다.

Thinking에는 같은 max_tokens4096 조건을 먼저 적용했다. 최종 JSON이 미완료되는 경우 `generation_incomplete`로 기록하며 reasoning 예산2048을 별도 조건으로 평가한다. 예산 조건을 추가한 결과와 원래 조건을 섞어서 모델 우열을 주장하지 않는다. 사용한 모든 request/실행 harness/command와 출력 실패는 [실험 산출물](../output/t03-qwen35/model-profile.json)에 연결된 동일 폴더에 보존한다.

검증은 순서대로 종료 사유, JSON 구조, ID coverage와 role-level 관계, level/parent 기대치, MCM 그림표제 제외, 반복 일치로 구분한다. `unique_valid_outputs=1`만으로 세 번 모두 성공했다고 판단하지 않는다. 기존 checker가 모든 단일-root/level-jump 규칙까지 보장하는 것은 아니므로 실제 출력을 별도로 검토한다.

## 최종 결과

총27회: 공통 non-thinking9회, 공통 thinking9회, 별도 thinking 예산2048 조건9회다. 기존 검증 통과15회/실패12회이며 실패는 출력미완료9회와 role-level 불일치3회로 나뉜다. 모두 원시 결과에 남겼다.

| 조건 | 기존 계약 검증 통과 | 제목 깊이·부모 | 그림 내부 표제3개 | 해석 |
|---|---|---|---|---|
| Qwen non-thinking | 6/9회 | Test_Paper는 검증 실패로 채점 제외. 나머지2편 level54/54, parent52/52 | 제외0/3 | 약3초지만 metadata 관계 오류와 그림표제 오분류가 있어 현 상태의 기본값으로 부적합 |
| Qwen thinking, 별도 예산 없음 | 0/9회 | 채점 가능한 최종JSON 없음 | 미평가 | 전체4096토큰을 소진해 출력미완료 |
| **Qwen thinking 예산2048** | **9/9회** | **level77/77, parent74/74** | **제외3/3** | 세 문서 각3회 유효 출력 동일 |
| 기존 E4B thinking | 9/9회 | level75/77, parent72/74 | 제외3/3 | 같은 입력·prompt·schema, 다른 모델/양자화이며 별도thinking예산은 없었음 |

점수 분모는 문서 집합당 값이며 동일 문서를3회 반복했다고77을231로 늘려 독립 표본처럼 계산하지 않는다. Qwen의 예산2048 조건에서 Test_Paper의 role27/27도 모두 일치했다. MCM 제외3개의 실제 role은 매회 `non_outline`이었음을 raw output으로 추가 확인했다. 일반 role 전체의 평가는 다른 두 문서에 없으므로 세 문서의 모든 role이 맞았다는 주장은 하지 않는다.

| 문서 | Qwen 예산2048 level / parent | Qwen 문서별 중앙값 | 기존 E4B 중앙값 |
|---|---|---|---|
| Test_Paper | 23/23 · 22/22 | 13.26초 | 16.71초 |
| MCM | 26/26 · 25/25 | 13.77초 | 15.66초 |
| Penteado | 28/28 · 27/27 | 13.52초 | 19.02초 |

각 시간은3회 wall-clock 중앙값이다. 기존 E4B가 잘못 연결했던 Penteado의 두 Generation 소절을 Qwen 예산 조건은 level3으로 같은 Materials and methods 아래에 배치했다. 임의 정답 교정이나 출력 후 role/level 수정을 하지 않았다. 프롬프트·입력·schema·seed·temperature·전체출력한도는 프로그램으로 대조했으며 model/thinking 및 해당 조건의 reasoning_budget_tokens 외 request 차이가 없다.

이번 구성에서는 Qwen3.5-4B + thinking 예산2048이 다음 검증의 우선 후보가 된다. 기존 standalone 도구 기본값이나 본 앱 모델은 자동 변경하지 않았다. 모델 크기만으로 선택하기보다 thinking 제어와 출력 계약을 profile에 함께 묶어야 한다. source I를 손대지 않고 더 많은 새 논문에서 후보 누락·번호 없는 제목·Figure 주변 근거를 검증하는 작업이 남는다.

## 검증·산출물·정리

- [전체27회 점수](../output/t03-qwen35/scores.json), [동등성 검사와 기존 E4B 비교](../output/t03-qwen35/comparison.json), [모델 profile](../output/t03-qwen35/model-profile.json), [실행 계획](T03_qwen35_execplan.md).
- `tools/run_title_experiment.py`는 수정하지 않았다. 실제 실행한 동일 bytes를 `output/t03-qwen35/runtime/harness-executed.py`에 보존했다. 초기 smoke와 후속 runner의 인자·exit와 컨테이너 상태도 보존했다. `run_remaining.py`의 exit1은 보존된 미완료 조건을 반영하며, 성공한 예산 조건을 실패로 덮은 것이 아니다.
- 모델 로딩 후 GPU 전체 표본4988MiB, 실행 표본5000MiB(약4.88GiB), 컨테이너 메모리 표본2.495GiB. 공유 GPU의 표본이며 모델 단독 peak는 아니다. 기존 E4B GPU전체표본은5259MiB였다.
- [정리 증거](../output/t03-qwen35/runtime/cleanup.json): 이번 persistent 임시 컨테이너5개와 internal network1개를 ID/label 대조 후 제거했다. CLI/probe의 `--rm` 임시 컨테이너도 잔존하지 않는다. 기존 container7개/image ID 집합/volume 이름 집합은 보존됐고 새 Docker 이미지는0개다. Qwen 모델 파일과 모든 결과는 유지했다.
- 실행 명령은 아래와 같다. Host에서는 inventory의 번들 Python 절대경로를 사용한다. 본 앱/DB 코드 변화가 없어 기존 앱202개·문서도구43개 unit suite는 재실행하지 않으며, 이 실험 검사를 PG integration/앱 release gate 통과로 표현하지 않는다.

```text
python -B tools/run_title_experiment.py check
python -B tools/run_title_experiment.py score --root output/t03-qwen35 --output output/t03-qwen35/scores.json
python -B output/t03-qwen35/runtime/verify_comparison.py
python -B tools/validate_bundle.py
```

독립 검토자는 harness/scorer를 import하지 않고 원시27개를 중복 JSON key 검사·역방향 parent 계산으로 재검증했다. 기존점수와 불일치0이며 예산2048의9개 출력 모두 단일document root와 level jump 없음도 확인했다. [독립검토 증거](../output/t03-qwen35/runtime/independent-result-review.json)를 보존한다. 예산2048은 같은 개발 문서에서 기본조건 실패를 본 뒤 선택한 후속 설정이며 독립 holdout으로 검증한 최적값이라는 뜻이 아니다.

원본 PDF3개와 실행 harness의 SHA를 재검증했다. 위 harness check·score·comparison verification·bundle validator는 모두 exit0이며 문서검사 오류0이다. [최종 runtime profile](../output/t03-qwen35/runtime-profile.json)에 실제모델·요청·해시·실행건수·정리결과를 집계한다. T03 전체 미완료 AT와 이후 I2K/KNode 등의 task 상태는 변경하지 않는다.
