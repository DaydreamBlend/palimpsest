# T04 — 원문 명시 지식의 다중 Data I2K 실험

2026-09-11 사용자는 I2K에서 원문에 없는 결론을 도출하지 말고 새 결론은 K2K에서만 만들도록 정정했으며, 예시 논문 몇 편을 추가해 다중 D의 실제 작동을 검증하도록 요청했다. 기존 Codex OAuth Terra Medium, image200 MinerU + 스크립트, 전체 I 검토, Revision/원문/판정 보존과 D2I 재실행 금지 정책을 유지한다.

## 목표와 범위

기존 Test_Paper와 추가 공개 논문 2편의 실제 D/I를 사용한다. 출처별 전체 I를 전달하는 다중 source I2K에서 원문에 명시된 지식만 구조화·독립 검증하고 PostgreSQL에 K와 정확 I grounding/Revision/Record를 저장한다. 공통 명제의 다중 출처 근거, 별개 실험 Observation 분리, 같은 의미 reuse와 replay를 확인한다. K2K 추론 runtime이나 자연어 검색/전체 전파 완료를 이번에 구현했다고 하지 않는다.

## 현재 코드와 소유권

- `knowledge_runtime.py`, CLI, model-request 준비, 신규 `0007` migration과 PG integration은 root 소유다. 기존 0001–0006 bytes/checksum은 보존한다.
- 독립 구현자는 새 `multi_source_i2k.py`/`multi_source_prompts.py`와 pure tests를 소유한다. 기존 selection profile의 prompt/schema 파일과 hashes는 변경하지 않는다.
- 독립 문서 담당자는 활성 docs/AGENTS/T04/T07의 I2K 추론 허용 문구를 최신 경계로 정정한다. canonical slices와 역사 output/progress는 유지한다.
- source 담당자는 실제 논문 2편과 이미 보존된 전체 image200 파싱을 조사하고 재사용 가능한 등록·source 조립을 준비한다. 실제 live source 쓰기와 root migration은 순서를 조율한다.

## 구현 순서

1. 현재 단일 source 입력·SQL guards·model receipt/검증·scope/재사용 경로를 읽고 기존 상태를 보존한다. 문서 최신 정정을 적용한다.
2. 각 단일 source packet을 검증하여 묶는 `multi-source-explicit-i2k-v1`을 추가한다. Data별 source/profile/hash와 전체 I review를 동결한다. 새 I2K는 explicit source 내용만 허용하고 새로운 논리적 결론은 검증에서 거부/보류한다.
3. source 입력 관계와 원문 명시 검증 원장을 추가한다. source identity의 Data는 실험 귀속이며 다른 D의 보완 근거와 구분한다. 별개 실험을 merge하지 않고 같은 의미 grounding 추가로 semantic Revision을 늘리지 않는다.
4. 격리 PostgreSQL에서 입력/출처 spoof, no-novel-inference 판정, scope/reuse, failure atomicity와 replay를 검증한다. 기존 앱 회귀를 실행한다.
5. 기존 full image200 raw를 검증해 추가 논문을 등록·I로 조립하고, 실제 multi-source input/prompt/media/schema를 준비한다. 승인된 같은 Terra Medium의 생성·독립 Validator를 호출한다. 원본/이미지를 실제 전달한 것과 descriptor를 구별한다.
6. 검증된 K를 DB에 반영하고 정확 Revision/grounding/전후 보존·재실행 결과를 확인한다. 모델 결론은 임의 수작업으로 고쳐 통과시키지 않는다. 실패/수정 시도와 비용·처리 의무를 기록한다.
7. 최종 code review/문서 검사, release image 검증 후 이번 작업의 실패한 임시 Palimpsest 컨테이너/image만 정리한다. 사용자 DB·원본·기존 모델/역사는 보존한다.

## 검증과 복구

실제 모델의 semantic 검증, 스크립트 단위 검사, 격리 DB 테스트와 사용자 DB의 실제 결과를 따로 보고한다. 오류 시 canonical 반영을 원자적으로 거부하며 durable 실패/판정 기록을 유지한다. 변경 전 앱/문서/DB 읽기 snapshot과 필요 시 DB 백업을 output에 보존한다. migration은 isolated DB에서 먼저 검사하며 기존 live source 등록 중 실행하지 않는다.

문서 validator의 이전 raw Markdown 오류 12개를 기준으로 새 오류를 비교한다. 신규 acceptance와 실제 commands/결과/남은 범위는 진행 중 계속 추가한다. 이 plan을 전체 T04/T07 완료 증거로 취급하지 않는다.

## 진행

- 구현: `multi_source_i2k.py`, `multi_source_prompts.py`, Runtime/CLI/request builder 확장과 `0007_multi_source_i2k` 추가. 각 source를 canonical I로 재검증하고 source 입력 관계와 explicit-source/no-novel-inference/source-identity 판정을 원자적으로 저장한다. 기존 0001–0006 및 과거 prompt/profile/IDs는 유지한다.
- 독립 감사에서 legacy 미분류 K의 외부 보완 근거를 과도하게 막는 부분을 발견해, Data 집합 대신 원래 I2K Record의 source owner를 확인하도록 수정했다. 이를 포함한 다중 source 실제 PG 대상 검사 9/9 통과. 최초 test JOIN 오류 1건은 fixture 조회를 고쳤으며 초기 로그를 보존했다.
- 최종 이미지 `palimpsest-multi:0.5.0`를 source/test bind 없이 검사해 450개 중 434 pass, 16 기존 PDFium 환경 skip, 오류/실패 0(66.173초). 그 전 초기 전체448 및 대상7 결과도 보존했다.
- 실제 source 준비: Test_Paper 36 I + Clarke 35 I + Dejani 16 I, 총87 I/94media/38pages. 두 추가논문의 원본export·모든I 역조회·모든page corner 대응과미디어hash 확인. 새 parser/의미D2I LLM 호출0.
- 준비 과정의 오류: 과거 source-units profile을 재사용한 helper가 부모 canonical block I를 Clarke159+Dejani126=285개 추가한 뒤 최종group/page I를 만들었다. 최신groups저장원칙에맞지않는중간행이다. 숨기거나삭제/ID재작성하지않고 sources-summary에명시했다. 실제model입력에는최종87I만포함한다. 실행helper는historical snapshot을남기고로컬검증전용으로바꿔새등록/재생성경로를제거했다. 직접group단계로의retainedparse등록은후속source입구개선사항이다.
- 기존 DB는 migration전3,162,307byte custom pg_dump로백업했다(SHA `1dfea3f4a7973ec8a2f57275eb0474ba1e3525c732665ca2a834d4f96a9f3bf7`). 자동승인검토가공유DB의영속schema/security변경을거부하여기존`palimpsest-knowledge`0007적용은실행되지않았고사용자승인질문이대기중이다.
- 안전한대안: 전용`palimpsest-multi-checks`서버안에별도`palimpsest_multi_papers`DB를만들어백업복원·0007설치성공. 기존DBschema는0006유지. 그격리DB에서87I 입력을동결한실행`01a08ffb-36db-7546-8824-7c9dc897f059`를준비했다. 현재실제Generator요청파일은`output/t04-multi-source/attempt-01/generator-request.json`, 입력digest는`aedc9b36fb4ab4c33d2e454f798b1df1eb33e1563da38ccba90c588e48dc6f39`이다.
- 모델 출력을 읽기 전에 별도 평가 기준을 `evaluation/rubric.json`에 고정했다(직접 공통 명제 2, 각 논문 실험 2씩 6, 허용되지 않는 종합/실험 혼동 2). 이는 Generator에 제공하거나 중요도 script로 사용하지 않는다.

## 실제 실행과 추가 발견

- attempt-01의 87 I/94 이미지 호출은 응답 확보에 실패했다. 당시 제한된 진단으로 원인을 확인할 수 없으며 context 초과라고 단정하지 않는다. 전송/출력 미확인 실패 원장을 남겼다.
- attempt-02의 51 I/44 이미지 호출에서 Codex CLI의 재시도 가능한 transport error 뒤 정상 완료를 잘못 실패 처리하는 provider 문제를 발견했다. 공식 0.153.4 event 구현을 확인하고, exit 0·새 final JSON·뒤따른 turn.completed를 모두 요구하는 좁은 복구를 구현했다. 실제 실패 응답을 사후 복원한 것은 아니다.
- attempt-02 재시도와 attempt-03은 각각 8개/12개 후보를 생성했지만 원문 인용 검사에서 실패했다. Unicode/LaTeX를 다시 쓴 인용과 Figure caption을 건너뛴 비연속 문장 인용이다. 실행 실패로 기록했으며 D2I를 재실행하거나 I를 수정하지 않았다.
- 이를 해결하기 위해 새 profile의 block citation을 추가했다. 모델은 보존된 I의 `source_block_id`를 고르고, runtime은 실제 source segment와 grounding의 일치를 검사해 정확한 quote/char range를 만든다. 인용 위치의 정확성이 의미 지지까지 보장하는 것은 아니다.
- attempt-04는 전체 51 I/44 이미지를 전달해 10개 후보(일반 Proposition 1, source Observation 9)를 생성했고 블록 인용 19개가 모두 구조 검사를 통과했다. Generator 247,099 input/6,578 output tokens, 161.312초; Validator 254,314 input/3,943 output tokens, 116.531초다.
- 독립 Validator는 10개를 승인했으나 R848 자극 autologous MLR의 누락을 이유로 I 하나를 needs_review로 남겼다. 격리 `palimpsest_multi_papers` DB에 10개 K를 원자 저장했고 실행 상태는 `needs_human`이다. source 51개 검토와 의미 추출 완료는 다르다. 이 시점에 여러 Data를 근거로 갖는 실제 후보는 0개다.
- Validator 전송은 처음 자동 검토가 거부했다. 세 논문의 공식 공개 PMC 전문, Test_Paper의 공식 PDF와 동일 SHA, PDF 주석/첨부 및 payload 경로/비밀 검사라는 새 사실을 제출한 뒤 동일 요청 재검토가 허용됐다. 우회나 다른 제공자 사용은 없었다. 기존 DB migration 승인 대기는 별개로 유지된다.
- 승인 후 별도 원문 감사에서 처치군별 결과를 과도하게 합친 후보와 앞 블록이 빠진 인용을 발견했다. canonical 모델 승인을 의미 정확성의 확정으로 보고하지 않는다. 상세 감사와 후속 검토를 남기며 기존 승인 Record/Revision을 임의로 지우지 않는다.
- attempt-05는 같은 51 I를 이전 검토와 현재 K에 연결해 누락·공유 명시 지식을 다시 검토한다. 공통 배경과 실험 동일성을 구분하고, 각 처치/측정 항목 조합의 원문 지지를 따로 검사하도록 일반 prompt 규칙을 강화했다. 고정 평가 기준의 정답을 주입하지 않는다.

## 최종 확인 결과

- attempt-05의 실제 Generator는 11개 후보를 냈으나 컨테이너 source bind에 PYTHONPATH가 없어 prepare가 설치된 이전 prompt profile을 사용했다. 실제 요청과 profile이 달라 stage는 정확히 거부됐다. 원래 실행은 실패와 실제 receipt를 보존했다. 올바른 코드 경로의 attempt-06을 준비한 뒤 request bytes·input snapshot/digest가 완전히 같음을 확인해 동일 응답 bytes를 재사용했다. 재호출 0이며 새 profile에 대한 Runtime prompt/schema/media 검사는 통과했다. 기존 profile/ID/hash를 고치지 않았다.
- attempt-06 독립 Validator는 1 accepted, 9 reused, 1 rejected를 반환했다. R848의 별도 실험 K만 추가되고 같은 의미 9개는 기존 Revision을 유지했다. 처치군별 결과를 과도하게 묶은 후보는 이번에는 기각됐다. 기존에 승인된 오류 K를 자동 취소하지 않으므로 `review-required.json`에 exact Revision을 연결했다. I2K 상태는 needs_human이다. 동일 request replay는 같은 실행을 반환했다.
- 실제 N2E는 43개 승인 NodeRevision과 근거·기존 Edge·독립 감사로 진행해 2개 제안 중 1개 승인, 1개 기각했다. 승인 관계는 Test_Paper의 기존 K 사이에서 제한된 저자 해석을 지지하는 Edge다. 새 논문 사이 관계나 다중 Data K 생성의 증거로 해석하지 않는다. N2E 실행은 completed이나 전체 전파는 미완료다.
- 최종 격리 DB: K 43/NodeRevision 43, Edge 27/EdgeRevision 27, grounding 91. 기존 32 NodeRevision·26 EdgeRevision·69 grounding의 SHA는 변하지 않았다. exact quote/endpoint owner 오류 0. 실제 multi-Data 근거를 갖는 K는 0개이며 synthetic PG 검사와 구분한다.
- 고정 최종 이미지 ID는 `sha256:87730e28a1d03dd295ea55905dfa25205881cfc840281ee7a0b8486a48304753`이다. source/test bind 없이 전체 484개 검사: 468 pass, 기존 환경 skip 16, 실패/오류 0, 77.305초. 중간 테스트 파일 indent 오류 1건은 테스트 1줄을 수정했고 실패 로그도 보존했다. 신규 단일 CLI routing은 엄격한 profile을 사용하며 기존 request replay는 유지한다. 직접 Runtime의 legacy 호환 API 제한은 문서에 남겼다.
- 문서 validator는 최종 보고서 추가 후에도 기존 12개 오류이며 새 오류 0이다. 실제 DB 백업은 5,141,480 bytes custom dump로 남겼고 header/pg_restore list를 확인했다. Docker 조사에서 이번 작업의 제거 가능한 실패 자원·dangling image는 0개였다. 실제 실험 DB/원본 볼륨을 보존했다.
- 결과·명령·한계: `output/t04-multi-source/REPORT.md`, `summary.json`, `database-verification.json`, `review-required.json`, `app-tests-frozen-final.json`, `final-backup.json`. 의미 release acceptance는 false. 기존 DB 0007 적용 승인은 계속 대기 중이며 T04 전체나 K2K를 완료로 표시하지 않는다.
