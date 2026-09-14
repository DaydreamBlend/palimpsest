# 현재 제목 계층 보조 모델 profile

2026-09-10 사용자 승인: “그럼 Q4를 쓰도록 하자.” 직전 공식 BF16 비교 후 기존 **Qwen3.5-4B Q4_0**를 선택했다. 이 문서가 제목 projection 실험의 현재 선택이며, 이전 E4B/BF16 실험 당시 기본값 기록은 역사로 보존한다.

| 항목 | 선택 |
|---|---|
| 모델 | Qwen3.5-4B, Q4_0 |
| 배포 저장소 | unsloth/Qwen3.5-4B-GGUF, 제삼자 양자화 산출물 |
| Revision | e87f176479d0855a907a41277aca2f8ee7a09523 |
| 파일 | Qwen3.5-4B-Q4_0.gguf |
| 크기 | 2,583,221,408 bytes, 약2.58GB |
| SHA-256 | 298fcb5fe7a77ccc79745ae24751560c5ac56874caff4bb39b1f2055bd72b8bb |
| 로컬 위치 | output/t03-qwen35/models/Qwen3.5-4B-Q4_0.gguf |
| 서버 별칭 | qwen35-4b-headings |
| Thinking / 예산 | true / 2048 tokens |
| 전체 출력 상한 | 4096 tokens, thinking과 최종 JSON 포함 |
| Prompt / sampling | structured v2 / temperature0 / seed42 |
| Runtime | 기존 llama.cpp CUDA b10380-0b1bad14f, context8192, parallel1 |

[모델 검증 기록](../../output/t03-qwen35/model-profile.json), [Q4 평가](../../progress/T03_qwen35_experiment.md), [공식 BF16 대조](../../progress/T03_qwen35_original_experiment.md)를 근거로 선택했다. Q4는 기존 개발 문서3편에서 평가했고, 새 Nassar/Torchinsky/Wallet3편의 직접 평가 결과는 BF16이다. 새 문서 BF16 점수를 Q4 성능으로 옮겨 적지 않는다.

[실행 도구](../../tools/run_title_experiment.py)의 run 기본 모델은 `qwen35-4b-headings`다. Thinking이 켜져 있고 예산을 생략하면2048을 실제 request/record에 기록한다. `--no-thinking`이면 별도 예산 필드는 생략한다. 명시적인 숫자(0 포함)와 `--model`은 우선하며, 과거 무제한 thinking 조건은 `--reasoning-budget none`으로 실행할 수 있다. 전체 출력4096 한도까지 제거하는 옵션은 아니다. Thinking을 끄면서 숫자 예산을 지정하는 모순은 기존처럼 거부한다.

모델 서버가 별도로 준비된 로컬 실험 환경에서 다음과 같이 실행한다. 이 도구는 서버를 자동 기동하거나 모델을 다운로드하지 않는다. 파일 경로는 새 입력/출력 위치로 바꾸며 기존 결과를 덮어쓰지 않는다.

```text
python tools/run_title_experiment.py run --input INPUT.json --output NEW_OUTPUT --mode structured
```

정확한 과거 실행 재현은 각 output 디렉터리의 frozen harness와 request를 사용한다. 현재 도구의 기본값 변경 때문에 과거 profile builder의 “현재 도구와 당시 frozen 코드 hash 동일” 검사는 더 이상 맞지 않을 수 있으며, 역사 코드를 수정해서 일치시키지 않는다.

이 선택은 원문을 삭제하지 않는 optional heading projection에 적용한다. 기본 source D2I는 MinerU+스크립트와 LLM0 정책을 유지하고, I2K/N2E/K2K/K2W의 의미 생성·검증 모델을 이번 선택으로 일괄 지정하지 않는다. 일반 text 블록의 문단 첫머리 소제목 후보 누락과 structured 출력의 역할 오분류는 계속 검증해야 한다. 기존 BF16·Gemma 모델과 평가 파일은 보존하며 새 컨테이너나 이미지를 만들지 않는다.
