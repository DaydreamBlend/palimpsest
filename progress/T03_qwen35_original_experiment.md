# Qwen3.5-4B 공식 원본 · thinking 2048 · 새 논문 평가

2026-09-10 KST. 사용자 요청에 따라 공식 `Qwen/Qwen3.5-4B` 원본 가중치를 받아 저비트 양자화 없이 실행했다. 새로운 논문 세 편을 각 3회 평가하고, 기존 Test_Paper를 3회 대조했다. 12회 모두 JSON과 구조 계약을 통과했으며 문서별 출력은 반복 간 동일했다. 새 논문의 **전달된 후보**는 모두 기대값에 맞았고, Test_Paper에는 역할 오분류 1개가 남았다. 원문 제목 후보 수집의 누락은 별도로 측정했다.

이 결과는 제목 계층 projection의 로컬 실험이다. 새 논문을 Canonical Store에 등록하거나 I/K를 생성한 결과가 아니다. D2I의 application LLM 0 정책, 원본 PDF, 기존 source I, DB, 앱 코드와 공유 harness는 변경하지 않았다. 새 실험 runner에 공식 BF16 모델과 2048 reasoning budget을 명시했다. T03 전체 gate나 I2K 완료를 뜻하지 않는다.

## 모델과 고정 조건

공식 원본은 [Qwen revision 851bf6e…](https://huggingface.co/Qwen/Qwen3.5-4B/tree/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a)에서 받았다. 두 safetensors shard 합계는 9,319,828,096 bytes이며 공개 SHA-256과 일치한다. 실제 header/index의 738개 tensor도 대조했다. 원본은 BF16 690개와 F32 48개 tensor이므로 전부 BF16이라고 표현하지 않는다.

기존 llama.cpp b10380 / commit `0b1bad14ff204627636aeb1de22ddcd5acb859d4`의 공식 변환기로 `--outtype bf16`을 적용했다. CPU4/메모리8GiB/네트워크 없음 환경의 변환은 79.340초, exit0이었다. 새 패키지나 Docker 이미지는 설치하지 않았다. 최종 GGUF는 **8,665,620,128 bytes**, SHA-256 `700fb7c10d19cc72c61bc7e55549f6becf1262b3412358cacaf66525a2cc213a`다. BF16 257개와 F32 184개 tensor만 있으며 저비트 양자화 tensor는 없다. [원본 검증](../output/t03-qwen35-original/runtime/converter/original-verification.json), [실행 파일 검증](../output/t03-qwen35-original/runtime/converter/gguf-profile.json).

이 파일은 공식 원본에서 직접 변환한 텍스트 실행용 BF16/F32 표현이다. upstream의 norm/A_log 처리와 tensor 재배열을 포함하므로 native Transformers와 비트 단위 동일성을 주장하지 않는다. 원본의 vision weights는 보존했으나 이번 텍스트 GGUF에는 포함하지 않는다. `blk.32 unused tensor`는 MTP 보조층을 main pass에서 사용하지 않는 정상 경로이며, 본체 0–31층 누락이 아님을 [고정 upstream 코드](../output/t03-qwen35-original/runtime/converter/mtp-compatibility-note.json)와 대조했다.

| 항목 | 실제 설정 |
|---|---|
| 모델 별칭 | qwen35-4b-official-bf16 |
| GPU / 서버 | RTX 5080 16GB / 기존 llama.cpp CUDA b10380 |
| Thinking | 명시적으로 활성화 |
| Thinking budget | 2,048 tokens |
| 전체 출력 상한 | 4,096 tokens, thinking과 최종 JSON 포함 |
| Prompt / schema | 기존 structured v2, 모든 입력 ID 보존 |
| Sampling | temperature 0, seed 42 |
| Context / 동시 처리 | 8,192 tokens / 1 |
| 반복 | 새 논문3편×3회 + 기존 문서1편×3회 |
| 네트워크 | 내부 Docker network, localhost, host port 미공개 |

원본 PDF 세 편은 읽기 전용으로 전달해 기존 offline MinerU 3.4.5 pipeline으로 파싱했다. Nassar10p/39.230초, Torchinsky5p/33.416초, Wallet14p/35.731초 모두 exit0이며 전체 page_idx와 원본 hash를 확인했다. 명령은 `pipeline / auto / ch / formula=true / table=true`로 기존 profile을 유지했다. MinerU 내부 local API도 network none 컨테이너 안에서만 사용했다. [Parser profile](../output/t03-qwen35-original/runtime/parser-profile.json).

## 모델 평가와 반복 결과

새 논문 oracle은 모델 출력과 MinerU 후보를 보기 전에 PDF 텍스트·폰트·페이지 렌더링으로 작성했다. 이후 raw 후보와 매핑하고 2026-09-09T15:14:46Z에 입력·기대치·코드 14개 해시를 고정했다. 실제 추론은 15:20:41Z 이후 시작했다. 이 기준은 독립 agent 검토이며 사람이 승인한 gold dataset은 아니다. Test_Paper는 기존 개발 문서의 입력과 기대치를 byte-identical 복사한 대조군으로 분리했다. [동결 manifest](../output/t03-qwen35-original/runtime/frozen-evaluation.json).

아래 점수는 문서별 각 반복에서 같았다. 부모 연결은 실제 non-null 간선 수이며, 루트와 제외 항목의 null 검사를 간선 수에 더하지 않았다.

| 문서 | 후보 수 | Level 기대값 일치 | Role 기대값 일치 | 실제 부모 연결 | 3회 출력 | 지연 중앙값 |
|---|---:|---:|---:|---:|---|---:|
| Nassar · PNAS 2017, 새 평가 | 5 | 5/5 | 5/5 | 4/4 | 동일 | 52.66초 |
| Torchinsky · Nature 2009, 새 평가 | 3 | 3/3 | 3/3 | 1/1 | 동일 | 38.63초 |
| Wallet · JEM 2008, 새 평가 | 9 | 9/9 | 9/9 | 7/7 | 동일 | 42.77초 |
| Test_Paper, 기존 개발 문서 대조 | 27 | 23/23 | **26/27** | 22/22 | 동일 | 69.98초 |

새 세 문서의 후보 level/role/null 포함 부모 판정은 각각17/17, 실제 간선은12/12이다. 날짜 metadata 두 후보는 `front_matter / level0 / parent=null`로 올바르게 분류했다. 기존 Test_Paper는 종전 기준을 유지해 front matter4개의 level과 null parent를 점수에서 제외한다.

Test_Paper의 ID15 **ONLINE METHODS**는 3회 모두 level2와 부모는 맞았으나, 역할이 기대값 `body_section` 대신 `back_matter`였다. 이전 Unsloth Q4_0 + 2048 조건에서는 같은 항목이 `body_section`이었다. 공식 원본 실행에서도 의미 분류 오류가 발생했으므로 JSON/schema 통과를 의미의 타당성으로 간주할 수 없다. 출력은 수정하지 않았다.

독립 검토자는 raw 응답을 중복 키 거부 방식으로 다시 파싱하고, schema·role/level 관계·단일 root·level jump·모든 ID·반복1/2/3·저장 output·부모 계산을 재검사했다. 요청 messages와 schema 전체도 고정 harness로 재구성해 비교했다. 12회 모두 구조 검사 통과이고, 발행 score와 불일치는0이다. 공유 harness의 valid 플래그만으로 모든 검사가 보장되는 것은 아니며 이번 실제 응답에서 추가 확인한 결과다. [점수](../output/t03-qwen35-original/scores.json), [독립 검증](../output/t03-qwen35-original/runtime/independent-result-review.json).

## 원문 제목 발견율은 별도 문제

| 문서 | 명확한 원문 제목·소절 | 입력에 포함된 실제 제목 | 명확한 후보 누락 | 별도 모호 항목 |
|---|---:|---:|---:|---:|
| Nassar | 26 | 5, 19.2% | 21 | 0 |
| Torchinsky | 5 | 2, 40.0% | 3 | 1 |
| Wallet | 23 | 8, 34.8% | 15 | 1 |
| 합계 | **54** | **15, 27.8%** | **39** | **2** |

원문 기대 항목은 모호한 두 개까지 포함하면56개다. 그중41개가 title 후보에 없으며 **41개 모두 raw의 일반 text 블록에 남아 있음을 확인했다.** 따라서 내용 전체 소실이나 Qwen의 삭제가 아니라 title 후보 선택 누락이다. Nassar의 Results 소절8개·Methods 소절12개·ACKNOWLEDGMENTS, Wallet의 Results 소절1개·문단 앞의 Methods 소제목15개 등이 해당한다. 각 항목의 raw locator·bbox·excerpt를 보존했다. [Nassar 매핑](../output/t03-qwen35-original/review/nassar-mapping.json), [Torchinsky 매핑](../output/t03-qwen35-original/review/torchinsky-mapping.json), [Wallet 매핑](../output/t03-qwen35-original/review/wallet-mapping.json).

Torchinsky의 Supplementary Information과 Wallet의 Online supplemental material은 출력 열람 전부터 모호함으로 표시했으며 명확한 제목 발견율의 분모에서 제외했다. 같은 형식의 원문 내용은 모두 보존 대상이다. Wallet의 제목 한 줄 중복과 β의 '-' 인식, Nassar의 일부 수식 표현 변형 등은 별도 텍스트 충실성 문제로 기록했다. 이번 후보 분류 만점을 PDF 전체 목차 복원이나 완전한 OCR 충실성으로 확대할 수 없다.

다음 구현은 일반 text 블록의 문단 첫머리와 원문 서식을 활용해 제목 후보를 더 수집하고, page/bbox/raw locator를 유지하는 것이다. 그 후 Qwen에 후보 역할·계층 분류를 맡기는 방식으로 진행할 수 있다. 모델의 목차 제외 결정이 원문 I 삭제나 I2K 입력의 무조건 제외로 연결되어서는 안 된다.

## 이전 Q4 비교의 범위와 자원

Test_Paper 요청은 이전 Q4와 model 값만 다르고, 입력·기대치·서버 build·기본 sampler도 동일하다. 기존 Q4 중앙 지연13.2648초에 비해 이번 BF16은69.9756초였다. 다만 실행 시점과 동시 GPU 부하는 통제하지 않았고, 제삼자 Q4와 직접 변환한 BF16 산출물을 비교한 것이므로 순수 정밀도만의 인과 효과로 단정하지 않는다.

전체 chat template는 두 곳이 다르지만 이번 명시적 thinking=true·단일 user 문자열·도구 없음 경로는 정적 분석 및 Jinja2 동적 렌더에서 같았다. 동적 렌더4,573 bytes/SHA`63d20221c00ee2e825f99158b281e2f9656ef3b61b344ed992e0185cc1770e78`를 확인했다. Token 목록·종류·merges·EOS와 실효 BOS 설정도 같지만 padding token metadata 차이는 남는다. llama.cpp 최종 입력 token ID 전체를 직접 비교한 것은 아니다. [Tokenizer/렌더 비교](../output/t03-qwen35-original/runtime/tokenizer-comparison.json).

RTX5080 전체 GPU 사용량은 추론 전4,844MiB, 실행 중 표본13,559–13,590MiB(약13.2–13.3GiB)였다. 다른 작업의 사용량을 포함하며 isolated peak가 아니다. 실제 로딩과12회 추론에서 OOM은 없었다. 따라서 이 환경의16GB GPU에서 실행 가능하지만, 이번 지연과 남은 역할 오류를 감안해 자동 채택의 근거를 과장하지 않는다.

## 검사·정리·재현 기록

실행 명령은 기존 이미지3개를 재사용하며 [서버 명령](../output/t03-qwen35-original/runtime/server-command.json), [파싱 명령](../output/t03-qwen35-original/runtime/parse-retry-command.json), [문서별 추론 명령](../output/t03-qwen35-original/runtime/inference-execution.json)에 보존했다. 모든 실행 산출물은 write-once 경로이며 재시험에는 새 출력 디렉터리가 필요하다.

- `python -B tools/run_title_experiment.py check`: exit0.
- 실험 parse/evaluate/harness 세 스크립트 AST 검사: 성공.
- `python -B output/t03-qwen35-original/runtime/evaluate_holdout.py freeze`: exit0.
- 동일 도구의 `run`: 전체12회, client exit0.
- 동일 도구의 `score`: exit0; raw 재계산과 불일치0.
- `python -B output/t03-qwen35-original/runtime/build_profile.py`: exit0. 원본 두 shard/실행 모델·동결 입력·기대치·원본 PDF·정리 결과를 재검증했다. 최종 profile의 산출물364개 해시도 별도로 재대조해 모두 일치했다.
- `python -B tools/validate_bundle.py`: exit0/오류0, Markdown125개·상대링크865개 검사. 문서 integrity 검사이며 앱·PG·LLM 정확도 검사가 아니다.

첫 parser는 GPU UUID 지정 후에도 두 GPU를 감지해 PDF 처리 전 중단했다. 실패 로그를 보존하고 새 컨테이너에 CUDA_VISIBLE_DEVICES=1을 명시해 정상 완료했다. 전체 다운로드 로그·상태 보존은 자동 승인 검토의 민감한 URL 가능성 지적으로 거절돼 선택된 종료 상태와 제한된 완료 메시지로 대체했다. 해결되지 않은 승인 장애는 없다.

실험 전용 컨테이너6개(변환기1개 선행 제거 포함)와 내부 network1개를 제거했다. 짧은 CPU probe는 --rm으로 종료됐다. 새 이미지0개이며 기존 container7개·image9개·volume19개의 집합은 변하지 않았다. 공식 safetensors와 검증된 BF16 실행본, 기존 성공 모델과 모든 결과는 보존했다. [정리 기록](../output/t03-qwen35-original/runtime/cleanup.json), [최종 실행 profile](../output/t03-qwen35-original/runtime-profile.json).

앱 source, 공통 schema/DB/migration, 기존 202개 앱 테스트의 상태는 변경하지 않았다. 이번에는 앱 회귀·실제 PostgreSQL 통합·I2K 의미 추출·T03의 전체 미충족 AT gate를 재실행하거나 통과로 표시하지 않는다. 신규 승인 대기 결정은 없다. [실행 계획](T03_qwen35_original_execplan.md).
