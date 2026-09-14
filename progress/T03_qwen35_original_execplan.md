# T03 후속 — 공식 Qwen3.5-4B 원본·새 논문 평가

## 승인·목표·경계

사용자 지시: “Qwen 3.5 4B 원본을 쓰도록 하고, 예산 2k로 해서 다른 논문에 대해서도 실험해줘.” 공식 `Qwen/Qwen3.5-4B` 원본 safetensors를 고정·보존하고 저비트 양자화 없이 BF16/F32 GGUF 실행본으로 직접 변환한다. 기존 b10380 runtime과 v2 prompt/schema, thinking budget 2048, 전체 출력 4096, temperature 0, seed 42를 유지한다. 이전 개발 문서와 겹치지 않는 Nassar/PNAS 2017, Torchinsky/Nature 2009, Wallet/JEM 2008을 각 3회 평가한다.

AGENTS, USER_OVERRIDES(U01–U11), INDEX, DECISION_REGISTER, PLANS, T03, CODE_REVIEW, D2I/I canonical 및 MinerU adapter 계약을 확인했다. 기존 HF CLI/평가·ponytail 절차와 PDF skill을 적용한다. 공식 모델 다운로드와 허가된 bibliography의 로컬 추론만 수행한다. 원문은 읽기 전용이며 원격 추론, canonical I/DB 변경, D2I 기본 LLM 활성화, 새로운 P 제안 승인, I2K 완료는 범위 밖이다.

## 실행·복구 계획

1. [x] 공식 revision/weights 확인, 기존 runtime/GPU와 평가 harness 확인.
2. [x] Docker 자원/소스 해시 snapshot. 공식 원본 다운로드와 b10380 변환 소스 pin, BF16 변환 및 해시 검증.
3. [x] 새 PDF 3편을 기존 offline MinerU 3.4.5로 파싱. 별도 검토자들이 원문만 보고 전체 제목 oracle 작성. 모델 호출 전에 title ID 매핑과 기대치 manifest 고정.
4. [x] 내부 전용 서버에서 같은 고정 조건으로 각 3회 실행. 실패/누락과 불일치를 보존하며 평가 자료를 본 뒤 프롬프트를 튜닝하지 않는다.
5. [x] 입력 후보 coverage, level/role/parent, 반복 일치, 지연 및 메모리 관찰을 독립 검토. 원시 요청/응답·모델/런타임/원문 provenance 보존.
6. [x] 결과 보고 및 적절한 도구·문서 검사. 이번 실험 소유 컨테이너/network만 제거하고 기존 자원과 원문 불변 확인.

Root는 모델/runtime/실행/보고 및 평가 코드 소유자다. 두 독립 검토자가 새 PDF oracle을 작성하고, runtime 검토자는 공식 모델·변환 경로를 조사한다. 출력은 `output/t03-qwen35-original/`에만 추가한다. 원본/기존 실험은 덮어쓰지 않는다. 재시도는 새 경로로 기록한다. 이미지와 DB/schema를 새로 만들 필요가 없으면 기존 것을 재사용한다.

## 검증·진행 기록

- 공식 revision: `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`. 원본 두 shard 합계 9,319,828,096 bytes. 소수 F32 요소도 포함하므로 모든 원본 tensor가 BF16이라고 주장하지 않는다.
- 기존 llama.cpp b10380 (`0b1bad14ff204627636aeb1de22ddcd5acb859d4`)는 Qwen3.5 변환·추론·2048 reasoning budget·JSON Schema를 지원한다. 변환은 tensor 배치/표현을 바꾸며 native Transformers와 bitwise 동일하다는 뜻은 아니다.
- 기존 container 7개와 이미지 9개, volume 19개 확인. GPU는 RTX5080/RTX4060Ti 각16GB. 기존 다른 workload의 메모리 사용을 포함하므로 isolated peak로 보고하지 않는다.
- PowerShell에서 rg 경로 wildcard를 직접 넘긴 읽기 검색은 exit1이었다. 디렉터리+glob 필터로 재검색했다. 앱 동작 실패와 무관하다.
- 첫 parser 컨테이너는 Docker의 GPU UUID 옵션에도 torch가 둘 이상의 GPU를 감지해 실제 PDF 처리 전에 assert로 중단했다. 실패 log/state를 보존하고 새 컨테이너에서 `CUDA_VISIBLE_DEVICES=1`로 명시했다. 이후 RTX4060Ti 한 개로 Nassar10p/39.230초, Torchinsky5p/33.416초, Wallet14p/35.731초 모두 exit0. 네트워크0B, page_idx 전체 연속과 원본 SHA 불변을 확인했다.
- 후보 수는 각각5/3/9개다. 독립 원문 검토에서 문단 첫머리의 굵은 소제목이 title-only 입력에 누락되는 문제가 확인됐다. 모델 분류 정확도와 전체 제목 coverage를 구분하고, 문서 텍스트에 남은 내용을 소실로 보고하지 않는다.
- `python -B tools/run_title_experiment.py check` exit0. 공유 harness는 변경 없이 exact 복사했고 새 cohort용 실행·freeze·score 도구는 산출물 내부에만 추가했다.
- 2026-09-09T15:14:46Z에 입력/oracle/매핑/실행 코드 해시를 `runtime/frozen-evaluation.json`으로 고정했다. 새 논문3편/9회와 별도로 기존 Test_Paper 입력·기대치를 byte-identical 복사해3회 대조한다. 이는 개발 문서 재시험이며 holdout 점수에 합치지 않는다. 전체 예정 호출은12회다.
- 새 원문 중 사전 모호 항목(Torchinsky의 Supplementary Information, Wallet의 Online supplemental material)은 각각 별도로 기록한다. 명확한 원문 제목은26/5/23개, title 후보로 들어온 실제 제목은5/2/8개다. 날짜 metadata2개가추가후보이며 source관찰상 비목차 항목을 고정v2의 `front_matter`로 계약 매핑했다. 모델 출력 전에 완료했다.
- 공식 두 shard의 byte/SHA와738개 tensor/index를 검증했다. b10380 converter는 CPU4/8GiB/network none에서79.340초/exit0. 새 package/image설치0. GGUF8,665,620,128bytes/SHA`700fb7c10d19cc72c61bc7e55549f6becf1262b3412358cacaf66525a2cc213a`, BF16 257/F32 184 tensors만확인했다. MTP보조층blk.32 unused는standard main-pass비사용이며 trunk0–31누락이아님을upstream근거로기록했다.
- 원본 model card README는bytes그대로 `model-card.txt`로이름만옮기고path map/SHA를보존했다. 전체downloadlog/state기록은자동승인검토에서민감한URL가능성으로거절되어선택된종료상태와제한된완료메시지만보존했다. 대체경로로완료했고미해결승인장애는없다.
- 서버는내부network/localhost/hostport미공개로실행중이며RTX5080전체메모리표본13,559–13,560MiB이다(타작업포함,isolated peak아님). 첫두문서6회는모두valid/문서별출력동일. 전체실행과독립QA후최종점수를발행한다.

## 완료·인계

12회 실행과 독립 검토를 완료했다. 새논문9회는전달후보level/role17/17·실제간선12/12이며기존Test_Paper3회는23/23·26/27·22/22이다. ONLINE METHODS의역할오류1개가반복됐다. 지연중앙값52.66/38.63/42.77/69.98초이며각문서3회출력동일. JSON구문/중복키/schema/관계계약/단일root/jump/요청전체/iteration/raw-output/부모계산과score의독립대조불일치0이다. [상세 보고](T03_qwen35_original_experiment.md)에실제결과와원문후보누락39개+모호2개를분리했다.

공식원본두shard와BF16파일을보존했고임시컨테이너6개/network1개를제거했다. 기존Docker container7/image9/volume19 집합은불변이다. 전체T03 AT gate, PDF전체목차복원, I2K지식추출, PostgreSQL통합검증은이번실험으로완료처리하지않는다. 새승인대기결정은없다. 다음보완은raw text문단첫머리의제목후보수집과원문서식/grounding대조이며,기본sourceD2I의LLM0정책을유지한다.

최종검사: `build_profile.py` exit0/모델·원본PDF·동결해시·정리검증성공, 산출물manifest364개재대조성공. `validate_bundle.py` exit0/오류0(Markdown125개/상대링크865개). 공유harness SHA불변. 원시12회·독립QA·점수의불일치0이며실행/스코어/원문coverage자료를보존했다.
