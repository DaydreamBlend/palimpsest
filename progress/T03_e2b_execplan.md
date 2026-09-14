# T03 후속 — Gemma 4 E2B 제목 계층 실험

## 승인과 범위

2026-09-09 사용자: “E2B로 실험해줘. 필요하다면 Desktop 하위 졸업논문 참고문헌의 논문 pdf 파일들도 써도 돼.”

후속 사용자: “성능이 별로 좋지 않으면 E4B를 다운로드해서 그걸로 진행해줘.” E2B의 실패 사례를 확인하면 같은 입력과 조건의 E4B 비교를 허용했다. 원문 외부 전송 허가는 아니다.

기존 Test_Paper의 고정 MinerU 3.4.5 산출물과 필요시 허용한 폴더의 추가 논문을 사용해 **로컬 Gemma 4 E2B**의 제목 계층 보정을 시험한다. 이는 U11의 기본 source D2I에 LLM을 자동 활성화하거나 canonical I를 바꾸는 작업이 아니다. 원본 PDF와 source I는 불변이고 모델 결과는 실험 projection이다. 외부에는 공개 모델/런타임 다운로드 요청만 보내고 논문은 로컬에서 처리한다. I2K/KNode 생성은 이번 범위 밖이다.

## 재사용 환경과 소유권

- root: 실행 환경, 모델 다운로드/해시, 최소 실험 harness, 결과/보고/정리.
- i2k_input_tradeoff: 모델 출력을 보기 전에 Test_Paper 제목 27개의 독립 기대 계층 fixture.
- page_context_review: 허용된 참고문헌 폴더의 추가 PDF 2개 선정과 원문 구조 QA.
- e2b_runtime_review: 공식 모델/런타임 지원 조사만.
- 현재 앱/DB/원문/canonical/migration 변경 없음. standalone 도구와 실험 산출물만 추가한다.

읽은 계약: AGENTS, USER_OVERRIDES, INDEX, DECISION_REGISTER, T03, PLANS, CODE_REVIEW, PAGE_CONTEXT, MINERU_ADAPTER, U11. Ponytail/HF CLI/로컬 평가/PDF 지침을 적용한다. 공개 벤치마크용 프레임워크를 앱 의존성으로 추가하지 않고 이 좁은 계층 작업의 구조·정답·반복 비교를 실행 가능한 작은 harness로 남긴다.

## 순서와 완료 기준

1. [x] 기존 Docker/모델 runtime 재사용 가능성 확인, exact model revision/file/hash 고정.
2. [x] 로컬 text-only E2B 서버 smoke, JSON Schema/non-thinking/샘플링 설정 검증.
3. [x] Test_Paper 원문 기대 계층을 모델 실행 전에 고정.
4. [x] A: 실제 설치 MinerU의 제목 계층 prompt를 기준선으로 실행. B: 출판 metadata와 본문 역할을 구분하는 구조화된 projection prompt 비교. 입력/출력과 실패를 모두 보존.
5. [x] 제목 ID 전체 보존·정수 수준·정답 일치·반복 일관성·실제 지연/메모리 표본 측정. peak 메모리 주장은 하지 않음.
6. [x] 추가 문서 2개를 같은 MinerU로 로컬 파싱해 고정된 정책의 별도 검증.
7. [x] 적절한 harness 검사와 문서 integrity, 결과 보고 및 임시 컨테이너 정리.
8. [x] E2B의 남은 비제목 분류 오류에 대해 승인된 E4B 비교를 수행하고 최종 권고를 기록.

모델의 오류를 canonical 기각으로 기록하지 않는다. 계층 분류의 성공과 PDF parsing coverage/I2K 의미 품질은 별도다. Test_Paper만으로 범용 정확도를 주장하지 않는다. 실패한 시도도 원인/결과에 남긴다. 사용자 원문과 기존 volume·무관 Docker 자원은 삭제하지 않는다.

## 실행 기록

- 일반 sandbox Docker 조회는 named pipe 권한 오류. 승인 경로 조회는 성공. 기존 llama.cpp b10380 CUDA 이미지가 있어 새 이미지를 받기 전에 재사용을 확인한다.
- 로컬 GPU 현재 조회: RTX 5080 16GB, RTX 4060 Ti 16GB. 기존 서비스의 GPU 할당과 데이터는 변경하지 않는다.
- 기존 llama.cpp CUDA b10380 이미지와 MinerU 3.4.5/app 0.2.0 이미지를 재사용했다. E2B official QAT Q4_0 3,349,516,256 bytes의 SHA-256을 대조했다. mmproj는 받지 않았다.
- 내부 전용 Docker network의 publish 포트에 host에서 접속 불가. 외부 노출 없이 client를 서버 network namespace에 넣고 localhost:8080으로 시험했다. 논문 전달은 local container 안에서만 이루어진다.
- MCM 15페이지와 Penteado 10페이지를 offline MinerU pipeline으로 파싱했다. Penteado 첫 Docker mount 시도는 파일명의 쉼표 때문에 exit125; `--volume` 인자로 고쳐 exit0. 원본/실패 로그 모두 보존.
- Test_Paper 27, MCM 29, Penteado 28개의 제목 후보를 전달했다. 독립 agent가 모델 출력을 보기 전에 원문 기대 계층을 고정했고 입력/기대치 해시와 매핑을 남겼다. 사람 승인 gold가 아니다.
- E2B v1 structured thinking에서 실제 제목 76/77 레벨, 73/74 부모 일치. Test_Paper/Penteado는 전부 일치하고 MCM Abstract만 level0이었다. 각 조건 3회 출력 동일. non-thinking은 Test_Paper 부모7/22로 부적합.
- v2는 Abstract/Summary를 body level2로 명시하고 non_outline 역할을 추가했다. 3편의 실제 제목77/77과 부모74/74는 일치했지만 MCM 그림 표제3개를 여전히 본문 하위절로 분류했다. v2는 결과를 본 뒤 개선한 development set 실험이며 held-out 검증으로 주장하지 않는다.
- MCM은 true heading3개가 raw text로 남아 title-only 입력에서 빠졌고 figure panel3개가 title로 들어왔다. source 내용 소실과 계층 LLM 오류를 구분한다. 사용자 후속 승인에 따라 E4B 공식 QAT Q4_0 다운로드를 시작했다.
- harness 독립 검토에서 repeat0 허용과 run/input 해시 대조 누락을 수정했다. scorer는 genuine heading hierarchy와 비제목 제외 정확도를 별도로 계산한다.
- 첫 bundle 검사 exit1: 다운로드한 외부 모델 README의 빈 표 셀8개가 저장소 문서 규칙에 걸렸다. 외부 원문 내용은 수정하지 않고 model-card.txt로 보관해 출처 자료와 authored Markdown을 구분할 예정.
- E4B 5,154,941,280bytes 다운로드와 공식 SHA 대조 성공. 같은 v2 request에서 model 별칭만 다름을 검증했고 9회 모두 JSON 구조 통과/각 문서3회 동일이다. MCM 비제목3개는 모두 제외했지만 Penteado 소절2개의 부모·깊이가 잘못되어 레벨75/77, 부모72/74였다. 더 큰 모델의 무조건 우월성이나 자동 절 확정 품질을 주장하지 않는다.
- 현재 standalone 실험 도구만 E4B/thinking/v2를 기본값으로 설정했다. 원문 D2I는 LLM0 정책 그대로이며 정답으로 강제 편집하거나 main app에 자동 활성화하지 않았다. 다음 보완은 좌표·서식·주변블록과 누락 후보 복구다.
- 전체39회 추론 기록·실패 로그·모델2개·고정 입력·독립 기대치·runtime profile을 보존했다. 원본 PDF3개의 hash 재검증 성공. E2B/E4B 임시 서버와 네트워크 제거 완료. 기존 Docker 자원 보존 대조와 최종 문서 검사를 마무리한다.
- E2B/E4B 경계 최종 검사: `run_title_experiment.py check` exit0, `score --root output/t03-e2b --output output/t03-e2b/final-scores.json` exit0, `validate_bundle.py` exit0/오류0. 기존 container7개·image ID set·volume name set 불변, 실험 컨테이너0개를 확인했다. 외부 모델 README는 bytes 그대로 .txt로 보존했다.

## 후속 승인 — Gemma 4 12B

진행 중 사용자: “Gemma4 12B는 너무 큰가? 그래도 이걸로도 실험 한번 부탁할게.” 12B의 공식 모델/양자화/runtime 지원과 16GB GPU 적합성을 확인한 뒤 동일3편/v2/thinking/3회로 비교하는 범위가 추가됐다. E2B/E4B 결과와 위 완료 검사를 보존하고, 12B를 자동 운영 기본값으로 선정하거나 D2I 정책을 변경하지 않는다.

9. [x] 공식 Gemma4 12B model/revision/file/hash와 runtime 호환성 확인 및 다운로드.
10. [x] 같은 입력·request 조건의 12B 실행, 의미/구조/재현성/latency/메모리 비교.
11. [x] 12B 결과·실제 명령·한계 기록, 새 임시 자원 정리와 최종 문서 검사.

- 공식 Gemma4 12B Unified를 확인했다. QAT repo `google/gemma-4-12B-it-qat-q4_0-gguf`, revision `29d097773436b69ff9feafd636ab4cf873786537`, file `gemma-4-12b-it-qat-q4_0.gguf`, 기대 bytes6,975,879,296 / SHA256 `93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b`로 고정하여 다운로드 중이다. 제목 실험이므로 mmproj는 제외했다.
- b10380의 gemma4 graph는 GGUF layer 설정을 소비한다. 48층의 표시용 type 분기가 없다는 사실만으로 미지원이라고 단정하지 않으며 실제 기존 이미지 smoke로 확인한다. 새 이미지나 GPU 서비스 설정 변경은 아직 없다.
- 12B 실행 전 RTX5080 사용표본1,961/16,303MiB, RTX4060Ti1,125/16,380MiB. 메모리 추정과 실제 로딩 성공을 구분한다.
- Penteado 오답2개 원문 재확인: `Mice`와 두 Generation 소절의 font9.963pt와x0가 동일하다. MinerU line_height12/9/10은 실제font크기와 다름을 기록했다. 기대치hash를 유지하고 PNG 원문QA를 보존했다.
- negative integrity smoke: 잘못된 input_sha256를 가진 복제run은 `run_input_hash_mismatch`로 채점 게시 전에 거부됨. 실제입력/기대치/기존run은 변경하지 않았다.
- 12B 다운로드 bytes/SHA 일치. b10380 기존 이미지에서32.87초 후 정상 로딩했다. 첫 즉시 health조회503은 로딩 중 상태였고 이후health=ok였다. 실행 GPU 표본9,610~9,644/16,303MiB, OOMKilled=false다.
- 같은4096출력 thinking은Test_Paper3회모두generation_incomplete(약46초);6144출력 탐색은3편각1회모두같은미완료(약69~70초). 원문/결과를위조해성공처리하지않았다.
- 12B non-thinking은3편각3회유효/동일, 레벨66/77·부모63/74·그림표제제외3/3, 시간중앙값6.54/9.61/6.74초였다.
- 공식b10380 per-request `reasoning_budget_tokens=2048`/전체출력4096의 추가탐색은3편각1회로 제한했다. 최종JSON은모두완성했으나 레벨68/77·부모65/74·그림표제제외3/3, 시간30.07/33.09/32.76초였다. 이변형은3회반복일관성이나holdout평가를주장하지않는다.
- 12B는하드웨어에서실행가능하지만이입력/runtime/config에서는E4B보다나은품질근거가없다. 실험defaultE4B유지. 전체57호출중구조유효51·출력미완료6이며source/canonical쓰기0이다. `final-all-model-scores.json`과`runtime-profile-12b.json`에조건·해시·오답을보존했다.
- 12B서버와internal network소유ID/label검증후정리. 기존container7개/image ID set/volume name set불변, 실험container0. 모델3개와증거는유지한다. 다음작업은제목후보누락복구·좌표·서식·주변Figure근거의projection설계이며T04/I2K완료처리하지않는다.
- 최종검사: `python tools/run_title_experiment.py check` exit0; `python tools/run_title_experiment.py score --root output/t03-e2b --output output/t03-e2b/final-all-model-scores.json` exit0; `python tools/validate_bundle.py` exit0/오류0. 실제host실행은번들Python절대경로를사용했다. `runtime/harness-check-all-models.log`, `bundle-validation-all-models.log`에보존했다. 기존앱202개·validator43개suite는이번앱/validator코드변경이없어재실행하지않았다. 문서검사를실제PG통합/애플리케이션/의미평가의대용으로표현하지않는다.
- 최종독립검토: 실제run57개의입력SHA·레벨·부모·비제목점수를독립재계산해통합점수와대조했으며불일치/blocking finding없음. 보고서반복횟수문구를E2B/E4B와12B탐색조건으로분명히구분했다.
