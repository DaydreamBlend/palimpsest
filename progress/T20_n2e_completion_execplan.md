# N2E 관계 생성·재검토 완성

2026-09-14. 사용자는 `N2E 완성해줘`라고 요청했다. 현재 실제 저장 가능한 Proposition·Observation의 관계 생성, 독립 검증, logical Edge/semantic Revision, 현재 적용성, CLI/읽기·전파 연결을 끝낸다. 기존 supports-only 실행의 profile/request/SQL0001–0016/원문/ID/Revision은 보존한다.

## 적용 계약과 범위

T06, current canonical graph/operations, R01–R03/R05/R06, U09/U11, source-only I2K와 K2K inference 경계를 적용한다. supports(P/O→P), contradicts(P/O↔P/O), qualifies(P/O→P), composes(P/O→P/O)를 strict proposal로 다룬다. contradicts는 logical UUID 순서로 정규화하며 두 주장의 같은 scope·조건·시점에서의 양립 불가능성을 독립 검증한다. 서로 다른 실험이라는 사실만으로 모순으로 만들지 않는다. composes는 명시적인 전체 명제의 진부분이며 근거 관계와 다르다. 현재 usable/applicable composes에만 DAG를 적용한다.

supersedes는 기존 R06의 authority-confirmed W2K 소유권을 유지한다. 아직 구현되지 않은 Decision/Procedure/Question/Entity, lifecycle 전체, Edge를 실제 전제로 쓰는 K2K/W/P 및 Edge embedding retrieval을 완료했다고 표시하지 않는다. Node-only K2K의 self-premise 금지는 유지한다. T06의 이 후속 소비자 AT는 실제 검사 범위와 구분한다.

새 n2e-relations-v1 프로필은 같은 identity의 material qualifier 변경에만 semantic Edge Revision을 만든다. 표현 변경/endpoint만 바뀐 경우 기존 semantic revision과 새 exact applicability를 쓴다. predicate·방향 identity 변경은 새 logical Edge이며 기존 관계의 true/false/unknown 판정은 별도 Record다. 빠진 candidate를 false로 해석하지 않는다. source 읽기/D2I/D2K/Node 생성은 N2E에 없다.

재검토 시작은 exact semantic revision/current endpoint pair에 durable pending fence를 열고 knowledge state를 갱신한다. unknown은 pending으로 남으며 새 confirmed event가 이를 해제한다. current endpoint support가 stale인 관계는 usable이 아니다. 확인된 contradicts의 contested는 읽기 projection이며 Node 내용/lifecycle/revision을 바꾸지 않는다. 반복은 T19처럼 advisory이고 의미 변화/근거 유지 의무로 전파를 판단한다.

## 구현·검사 계획

1. 순수 registry/schema/normalization/prompt는 n2e_relations; 공통 KnowledgeRuntime/Store/Record/commit을 재사용하는 runtime helper를 연결한다.
2. 추가0017은 predicate/type/symmetry, exact review fence/decision, 현재 applicability, composes cycle guard를 제공한다. Root만 새 template0 기반 격리 테스트 DB를 생성·마이그레이션한다. 사용자 원본 DB에는 쓰지 않는다.
3. shared effective relation projection을 graph/Wiki/Desktop에 연결하고 historical와 current refs를 구분한다. source scope 밖 내용이나 상대 Node 본문을 검색 입력에 누출하지 않는다.
4. 실제 PG로 네 관계, 반대 방향 dedupe, material qualifier revision, endpoint reuse, predicate change와 old 판정, unknown/pending/negative precedence, composes cycle/rollback/CAS, atomic outbox와 contested를 검사한다. 기존 실행/자료 history는 read-only로 확인한다.
5. 필요한 model 검사는 assistant-authored 합성 자료만 사용하며 structural fixture와 실제 Terra 생성·독립 검증 결과를 따로 기록한다. 새 사용자 원문 전송이나 D2I 재실행은 없다.

## 진행

계약/SQL/소비 경로를 병렬 검토했고 현재 구현 중이다. Root는 KnowledgeRuntime/commit/CLI/전파/DB/release, contract agent는 새 순수 모듈과 tests, SQL agent는0017, consumer agent는 shared edge projection/Wiki/Desktop을 담당한다. 신규 production dependency나 broker를 추가하지 않는다. 실제 commands와 실패·수정·검사 결과는 아래에 누적한다.

## 구현과 검증 진행 기록

- 새 `n2e_relations.py`와 공통 Runtime을 사용하는 `n2e_runtime.py`를 연결했다. 새 CLI는 edge-input/edge-revalidate/edge-call이다. 기존 generic prepare/stage/decide/show/graph와 worker를 재사용한다.
- 입력을 보강하기 전 실제 request input을 따로 동결하여 범위가 제한된 재시도도 같은 fingerprint를 유지한다. 같은 request의 다른 prior_pair는 거부한다. model의 실제 이유는 `model_decision`, script의 보류 이유는 별도 validation/Record 이유로 보존한다.
- composes positive batch를 한꺼번에 검사하여 후보 배열 순서가 순환 중 어느 관계를 먼저 살릴지 결정하지 않게 했다. 재검토 중 가려진 target의 positive 복원을 prospective graph에 포함한다. target 재검토 묶음의 순환은 전체를 보류하고 독립 discovery의 다른 predicate는 검증 결과에 따라 반영할 수 있다.
- 빈 template0에서 새 `palimpsest_n2e_checks`를 만들었다. 첫 관리자 초기화는 앱UID10001이 관리자 전용 파일을 읽지 못해 PermissionError였다. 일회성 initializer만 root로 실행해 해결했고 credential 값·role·비밀번호는 출력하거나 변경하지 않았다. 기존 사용자 DB는 마이그레이션하지 않았다.
- `0017_n2e_relations`가 실제 설치되어 11개 PG 검사를 통과했다. 이어 DB 방어 검토에서 적용성의 Generator/Validator 일치·materiality=null·decision/Record 원자성을 추가0018로 보강했다. 설치된0017 bytes는 유지했다. 이후 old Record나 legacy profile로 새 pending을 지우지 못하도록 추가0019를 검토 중이다. 기존0001–0016은 그대로다.
- 실제 Terra Medium 4회: 합성 D1/I9에서 합성 receipt로 준비한 K8을 대상으로 새 관계5개(supports1/contradicts1/qualifies1/composes2)를 생성·독립 검증하여 저장했다. 다른 실험 Gamma40C는 Alpha20C의 모순으로 만들지 않았다. 같은 contradicts를 다시 검토한 두 호출은 명시적 true 평가와 독립 확인으로 `no_material_delta`를 저장했다. source K 생성은 실제 LLM 평가가 아닌 명시된 fixture다. 기존 source D2I 재실행·사용자 원문 전송은0이다.
- 이 실제 실험의 원문 bytes/정확한 I 인용/Node·Edge Revision/모델 전달 hash/독립성/당시 Runtime bytes 등23개 read-only 검사를 통과했다. 실제 실행 때의 두 Runtime 파일은 live/discovery-runtime.py와 live/review-runtime.py로 보존했다. 후속 repeated-negative outbox 보강은 별도 회귀 검사의 대상이다.
- 순수·소비·기존 K/N2E/재검토/전파 지침114개 통과, renderer20개 통과. 새 Runtime13개+worker3개 실제PG16개 통과. 이전schema0016의 Runtime6개도35.660초에 통과했다. AT17 반복 negative의 추가 검사와 SQL 우회 방어 검사를 최종 집계에 추가할 예정이다.
- 실제 사용자 코드 DB의 보존137검사, 이전T16 실제Terra/Wiki 실험18검사를 read-only로 통과했다. 신규 provider 호출로 이 과거 실험을 재실행하지 않았다.

주요 명령은 `output/t20-n2e-completion/run-tests.py`의 module 목록과 report JSON에 보존한다. 실제 모델 호출은 `tools/run_knowledge_model.py <준비 request> --codex <기존0.153.4 executable>`의 네 번이다. 초기 아직 생성되지 않은 순수 test 모듈 조회는 ModuleNotFoundError였고 파일 작성 후19개 검사로 해결됐다. 존재하지 않는 경로 glob/문서 patch anchor 실패는 실제 파일 확인 후 수정했으며 데이터 변경은 없었다.

## 최종 완료 상태

현재 P/O N2E의 요청·독립 검증·저장·revision·적용성·전파·조회 연결을 완료했다. 추가0019는 old Record 재게시, 최신 exact fence보다 오래된 준비, modern review의 legacy downgrade와 중복 event를 차단한다. 이미 설치한0017/0018을 다시 쓰지 않았다. 기존0001–0016도 보존한0.18 이미지와 byte 비교해16개 모두 일치했다.

최종 새PG22개는 Runtime14/worker3/SQL5다. 처음22검사에서21개는pass,1개는 legacy measurement K를 strict K2K 입력으로 사용한 fixture 오류였다. 정상 structured I2K fixture를 재사용해 테스트만 수정하고 SQL5를7.648초에 통과했다. 잘못된 초기 결과는 final-postgres-tests.json에 유지한다. 이후 실제 배포 이미지에 설치된 앱으로 새PG22+순수/소비/기존계약115, 총137개를29.709초에 모두 통과했다. 기존schema0016의6개를 포함해 중복 없는 관련Python143개/renderer20개 통과, 미해결 실패/skip0. 전체 앱suite 재실행은 아니다.

Docker image는 `palimpsest-n2e:0.19.0`, ID는 `sha256:f886005d40683d8abcee9e1d15ac2076b3b24d20d65913c6d6a5b6c700e4754f`다. shipped source·설치된 package·SQL105파일과 tests110파일이 final workspace와 일치한다. 새 배포 이미지는1개이며 테스트 컨테이너는모두--rm이었다. 실제 사용자 DB의schema0013과기존Electron패키지는보존했다. model weights나 source artifact를삭제/다운로드하지않았다.

AT11/AT14/AT17은 실제 PG검사로 충족했다. AT09/10/13/15/16의 생산·읽기·현재 support/worker 부분은 검사했지만, Edge-consuming K2K/W/P·Edge embeddings·일반lifecycle이 필요한 전체 AT09–17을 완료로표시하지않는다. Node-only K2K·source I 기반Wiki본문·T19 반복advisory 경계는유지된다. userDB activation·새사용자원문실험은별도이며 이때현재관계/RAG동기화단계를함께검토한다.

[최종 결과](../output/t20-n2e-completion/REPORT.md)와 [기계 판독 집계](../output/t20-n2e-completion/verification-summary.json)에 실제검사와미구현경계를기록했다. 문서검사의첫실행949개중1개는아직생성되지않은bundle-summary 링크였고결과파일작성후다시확인한다. 기존third-party/archive948오류는이번변경과분리한다.

문서 재검사 결과는 기존948오류/이번작성범위0오류였다. 배포이미지와최종workspace의bytes검증도pass이며이미지에설치된코드로137개를실행한최종보고서를저장했다. 이범위에서추가로필요한구현·미해결테스트실패는없다. 기존사용자자료로의활성화와별도Edge소비단계는완료로대신표시하지않는다.
