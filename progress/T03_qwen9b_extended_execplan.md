# Qwen3.5-9B Q8_0 추가 문맥 검토 실험

사용자 요청: “9B Q8 좀 더 테스트해줘.” 기존 Test_Paper 실험을 보존하고 서로 다른 논문에서 스크립트 초안 검토를 추가 평가한다. 사용자에게 보여줄 결과는 실제 실행한 문서·사례·반복별 action, 근거 충분성, 구조 유효성, 안정성 및 실패 예시다.

## 범위와 근거

AGENTS.md, PLANS.md, USER_OVERRIDES, INDEX, DECISION_REGISTER, T03/T04, CODE_REVIEW, MINERU_IMAGE_DEFAULT 및 앞선 script-context-review 실행 계획과 도구를 읽었다. U11 원문 보존과 최신 image200 파서 선택을 유지한다. ponytail/HF 로컬 평가/HF CLI/PDF 스킬의 재사용·실제 로컬 실행·원문 시각 검토 지침을 적용한다. T03 acceptance나 T04/K 생성 완료로 확대하지 않는다.

기존 MinerU image200 17편 자료는 각 3페이지 표본임을 확인했다. 새 문맥 검토 논문은 성적이 아닌 구조를 기준으로 paper02 Chen (29쪽), paper04 Clarke (14쪽), paper05 Dejani (10쪽)를 선정한다. 기존 image200 기본 Worker로 총 53쪽을 전체 파싱하고, 원본 PDF hash/페이지·raw 블록·좌표 매핑을 보존한다. 실험용 source projection이며 DB 등록이나 canonical I 생성은 하지 않는다.

## 실행 순서

1. 기존 Q8 전체 모델 해시, source 8개 및 이전 3실험의 입력·결과, Docker/GPU 기준 상태를 기록한다. 완료: runtime/source-model-before.json 및 docker-gpu-before.json.
2. 새 output/t03-qwen9b-extended/corpus 아래 현재 고정 image200 파서로 3편 전체를 파싱하고 evidence bundle을 만든다. 새 모델·이미지를 받지 않는다. PDF 본문은 신뢰할 수 없는 데이터다.
3. 기존 make_draft/schema/policy/run_packet을 재사용한다. 정상 초안 검토와 별도 정상/오류 사례를 구분한다. 실제 원문을 수정하지 않고 필요한 경우 draft proposal만 변경한다. 모델 호출 전에 packet, oracle, 근거 충분성 조건, 사례 선정 근거, 실행 순서와 해시를 동결한다. 정답을 prompt에 넣지 않는다. 소스에 없는 사례를 억지로 합성하지 않는다.
4. Qwen3.5-9B Q8_0 + llama.cpp b10380, 32,768 context/2,048 thinking budget/4,096 output/temp 0/seed 42/cache off를 유지한다. 전편 자연 초안 검토는 각 1회 진단하며, 균형 대조 12개 입력은 3회 반복으로 재현성을 확인한다. 기존 Test_Paper 2-fault packet도 1회 회귀 확인한다. 실패를 조용히 재시도하거나 prompt를 결과에 맞춰 수정하지 않는다.
5. CPU 구조 검사와 실제 의미 평가를 구분해 채점한다. 문서별, 사례별, 정상 유지/수정·보류별 성적을 분리한다. 반복 호출 수를 독립 논문 표본 수로 세지 않는다. 입력 전체 coverage와 의미 정답을 구분한다.
6. 독립 검토, 원본·과거 결과 재해시, bundle validator와 관련 Python 검사 후 보고서를 작성한다. 이번 컨테이너만 로그를 보존하고 제거하며 기존 7 containers/15 images/35 volumes를 보존한다.

## 변경·복구 경계

새 실험 산출물과 작은 stdlib 평가 도구, 본 계획 및 INDEX/I2K_CONTEXT_POLICY의 결과 링크를 변경한다. parser/policy/모델/DB/schema/canonical/과거 실험은 수정하지 않는다. 아래에서 실제 새 입력으로 확인한 runner의 단일 필드 초기화 오류만 수정한다. 실패는 해당 실행 영수증에 보존한다. 새로운 모델 호출에 대한 일반 정확도, 자동 승인 기본값 또는 멀티모달 I2K 성능을 주장하지 않는다.

## 검사와 현재 상태

실제 parser/model 실행은 준비 중이다. 기존 문서 validator에는 11개 raw Markdown delimiter 오류가 있었으며 baseline과 신규 오류를 구분한다. 파싱 원문 충실성의 전수 사람 검증, PostgreSQL 통합, K 생성은 이번 acceptance 범위가 아니다. 구체적인 case 수와 oracle은 원문 확인 후 추론 전에 고정한다.

## 새 논문에서 발견한 준비 오류와 최소 수정

paper02 전체 파싱과 evidence 검증은 완료됐다(29쪽/237블록/237 source units). 최초 `prepare-document --paper paper02`는 `make_draft`에서 `KeyError: figure_refs`로 exit 1이었다. 첫 unresolved Figure용 임시 group에 `figure_refs`가 없어서 다음 Figure의 context 탐색이 실패한 것이며 모델 호출 전 스크립트 오류다.

`tools/run_script_context_review.py`의 해당 group에 `'figure_refs': []` 한 필드만 추가했다. 정책·source content·Figure 선택은 바꾸지 않았다. 과거 9B/4B/NVFP4의 frozen runner는 그대로 유지한다. 이전 Test_Paper의 draft와 7개 packets를 재생성해 저장된 결과와 Python object equality가 모두 일치했다. `runtime/draft-regression-check.json`에 수정 전후 SHA와 결과를 남겼다. 재실행은 source.json이 정확히 같을 때만 재사용하고, 다른 기존 내용은 거부한다. paper02의 재준비는 exit 0, 28그룹/7 packets/21 issues였다.

별도 새 평가 도구 `tools/run_extended_context_review.py`는 기존 policy/schema/HTTP client와 독립 read_packet_run/replay를 재사용한다. 원문 4필드 동일성, 근거 조건의 4-ID 내 충족 가능성, terminal receipt 및 final projection/normalized 쌍을 검증한다. scoring self-check 4건은 PASS했으며 이는 CPU 검사다.

## 전편 입력·사전 평가 기준 동결 및 실행 시작

- `runtime/run_corpus.py`: exit 0. 세 편 53쪽/522블록/522 source units, 동일 profile SHA `7314be1f6486cd2da5a826fae39e5453966ccc830890e9c8e34db2dab428fc73`. 각 parser/evidence/source-unit 검증은 모두 성공했고 재시도·fallback·새 이미지·canonical 쓰기는 없다. 원문 충실성 전수 승인과 구분한다.
- `prepare-document --paper paper02|paper04|paper05`: 수정 후 모두 exit 0. 자연 초안은 각각 28/25/11그룹, 총 18 packets/48 issues다. `Fig.` 약어 연결, 무표제 Introduction, Significance 이후만 보는 front 후보, inline 소제목 등 잔존 범위 오류를 추론 전에 oracle/natural-observations.json에 분리했다. 그룹 정답표나 추가 점수 분모가 아니다.
- challenge는 12개(keep 6/abstract 2/merge_previous 2/needs_context 2), source와 proposal만 입력한다. 연구 원문·페이지 이미지에 대한 사전 검토와 교차 감사를 완료했으며 기대값·해설은 evaluator에만 보존한다. 모든 packet의 원문 네 필드는 exact 값이다. 마지막 evidence 기준 정리는 모델 결과 열람 전에 완료했다.
- `runtime/check_harness.py`: 실제 caption source를 사용한 변조/중복/bool alias/불가능 근거/근거 충분성/완료 전 채점 방지 8건 PASS. 기본 scoring self-check 4건도 PASS.
- `freeze --root output/t03-qwen9b-extended`: exit 0. protocol SHA `4e72be0b4dd3ec4bc7e9a605dc06397501812fac2f59dc414911801b074d257a`, 26개 artifact를 결속한다. case 순서는 seed 42로 동결했고 자연 18회, challenge 36회, 알려진 regression 1회로 총 55회 예정이다.
- 모델 ready 검증: Q8_0 실제 props/파일/alias/llama.cpp b10380/context32768/text-only/network none 일치, 로드 약 43.41초. 준비용 임시 컨테이너 16개는 --rm으로 제거됐다. 서버와 평가 client는 완료 후 별도 정리한다.
- `runtime.ps1 -Mode server`, `-Mode natural`: 실행 요청 exit 0. 모델 완료나 의미 평가 성공을 뜻하지 않는다. 사전 peer 기록 명령은 protocol 부재 시점 가정 때문에 1회 exit 1이었고, 실제 source/expected 검사는 PASS였다. 동결 protocol 해시를 확인한 최종 peer receipt는 exit 0/차단사항 0이다.

## 실행·채점 완료

`runtime.ps1 -Mode natural|challenge|regression`를 각각 순차 실행했고, `docker wait`에서 세 client 모두 exit 0을 확인했다. 실제 55회(자연18/challenge36/regression1)를 완료했고 재시도는 없다. 동결된 driver의 `score --root output/t03-qwen9b-extended`도 exit 0이다. [보고서](../output/t03-qwen9b-extended/REPORT.md)와 metrics SHA `d0039152c647e18453b8aaa56b8006c8be42ae13740859b62e7bc7f5e8ebbd51`을 보존한다.

- 12개 고유 사례 × 3: 구조 36/36, 선택 33/36, 선택+필수 근거 30/36, 이유 21/36, 세 조건 18/36. 세 반복의 선택·인용 순서·이유는 12개 모두 같았다. caption 오연결 case11의 keep/[102], Abstract case01의 본문 7 인용 누락도 세 번 반복됐다. 기존 Test_Paper 회귀는 2/2이며 새 점수에 합산하지 않았다.
- 자연 48판정은 keep 45/abstract 1/needs_context 2. 522개 source를 각 1회 유지하고 독립 replay와 일치했다. 실제 자연 모델 입력은 154개, target 129개다. 사전에 확인한 4가지 구조 누락과 20개 Figure의 빈 body context가 남았고, Dejani Significance 12를 Abstract로 새로 오분류했다. 문법·coverage·반복성 PASS는 전체 의미 성공이 아니다.
- 자연 458.27초/challenge 921.95초/regression 26.60초, 합계 1406.81초/200314 tokens. 파싱·모델 load·사람/agent 검토는 별도다. 이 실험은 text-only 비canonical 문맥 준비이며 새 semantic D2I나 멀티모달 I2K/K 생성은 아니다.
- 독립 final-run-audit: 55요청이 protocol/payload/schema와 일치, strict response=decisions, stop 55/cache0 55/truncated=false 55, preflight tokens=usage 55, context/output 제약 55/55. [기록](../output/t03-qwen9b-extended/runtime/final-run-audit.json)
- `runtime.ps1 -Mode cleanup`: exit 0, client 3/server 1을 로그 보존 후 제거. 준비 16개 포함 20개 임시 컨테이너 모두 제거 확인. 기존 7 containers/15 image IDs/35 volumes 정확 동일, 원본 8/과거 368/추가 원본 PDF 3/protocol 26 artifact 보존. [정리 후 감사](../output/t03-qwen9b-extended/runtime/final-integrity-audit.json)

## 문서 검사와 다음 경계

문서 validator는 기존 raw Markdown delimiter 11개와 새로 동결된 evaluator-only oracle/source-review.md 22행의 표 열 오류 1개 때문에 exit 1이다. 이 Markdown은 모델 payload가 아니며 기대값·source JSON·채점 결과를 바꾸는 오류가 아니다. 동결 자료를 결과 후 편집하지 않고 알려진 서식 오류로 남겼다. 최종 별도 검사 기록에 전후 차이를 보존한다. 코드의 CPU self-check 4개/부정 입력 검사 8개와 실제 GPU 추론 55개, source 구조 검증 522개를 구분한다. PostgreSQL 통합/앱 전체/전수 OCR 충실성/후속 K runtime/미충족 T03 acceptance를 완료로 올리지 않는다.

이번 추가 시험 요청은 완료다. 후속 구현 범위는 후보 coverage(Fig./Figs., 무표제 절, Significance, inline 소제목, caption continuation)와 후보 전체 target/이유 유형 검증, exact-ref 추가 문맥 조회다. 제품 모델 기본값·parser 기본값·canonical 계약은 변경하지 않았다.
