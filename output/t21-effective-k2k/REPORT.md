# Edge를 전제로 사용하는 K2K 완료 결과

2026-09-14. 앱0.20/schema0020에서 K2K가 exact Node 값과 N2E의 실제 EffectiveEdgeRef를 함께 소비하도록 구현했다. [계약·CLI](../../docs/interfaces/EFFECTIVE_K2K.md), [실행 계획](../../progress/T21_effective_edge_k2k_execplan.md).

## 완료한 동작

선택한 Edge는 current endpoint Node 두 개와 함께 입력된다. 추가 Node를 포함할 수 있으며, 모든 결과가 실제 전달한 Node·Edge 묶음 전체를 의존성으로 기록한다. Global read token은 전달/read-set 증거로만 사용하고, 영구 currentness는 실제 semantic Revision·pair·basis·pending·support를 검사한다. SQL의 Node ancestry 순회와 Edge 로컬 검사를 분리해 상호 재귀를 피했다.

새 추론 K는 Proposition/is_inferred=true이며 원래 exact Node/Edge 근거와 가정·한계·검증을 보존한다. 동일 의미 재검증은 같은 KRevision에 새 current-support를 연결한다. 관계가 pending이면 기다리고, confirmed false이면 근거 부족 상태를 유지한다. 필수 Edge를 자동으로 버리거나 K를 삭제하지 않는다. 이후 관계가 복구되면 남아 있던 의무를 다시 처리할 수 있다.

Node 값 변경, Edge 의미/적용성 변경, 동일 의미의 positive basis 갱신이 실제 consumer를 깨우도록 worker를 연결했다. 유지보수와 새 의미 discovery를 구분한다. source query와 Desktop에는 원래 Edge 근거와 현재 지원 경로를 구분해 제공하며, 실제 전달되지 않은 Edge를 인용하지 못하게 한다.

## 실제 모델 시험

새로 작성한 [가상 캐시 사양](live/fictional-cache-configuration.md)의 D/I와 synthetic receipt로 준비한 K3·qualifies Edge1을 사용했다. 이 캐시/세션 수는 Palimpsest 설정이나 GPT 병렬 세션 수가 아니다.

Terra Medium의 실제 Generator는 세션 최대32개, 세션마다 독립 캐시1개, 각 캐시의 용량 최대64항목이라는 조건에서 **전체 최대2,048항목**이라는 새 조건부 명제를 도출했다. 독립 Validator가 추론·근거 충족·한계·신규성을 확인했고, DB에 새 inferred K1을 저장했다. 실제 호출은2회이며 source K/N2E seed는 별도의 명시된 합성 판정이다. 가상 조건의 계산 검증을 일반 과학 추론 정확도나 실제 소프트웨어 성능으로 확대하지 않는다.

결과 KRevision: `01a09db4-b9b9-795d-b477-f8a9904fa54f`.

원본 bytes, 정확한 typed Edge, 세 Node 참조, 직접 I 근거 위조 없음, 과거 Revision 보존, 실제 두 호출의 hash·전달·독립성 및 자기 commit 이후 현재 유효성을 [읽기 전용11검사](live-verification.json)로 확인했다. [실제 결과](live/result.json), [graph](live/graph.json).

## 검증과 배포

- 실제 PG: Runtime7, SQL 음성5, worker3, 총15개 통과. 잘못된 pair/basis, typed Edge 누락, receipt 없는 빈 완료, target 전제 누락, stale basis 완료를 거부한다. endpoint 변경·N2E→K2K 재검증·negative 보류 후 복구를 포함한다.
- 최종 설치된 이미지: 관련138 tests를32.930초에 통과, 실패/skip0. [전체 목록](package-final.json). 전체 앱 suite의 일괄 재실행을 의미하지 않는다.
- 순수/consumer 별도 중간 검사는 보고된 모듈별 실행 결과와 구분한다. 신규 pure12, consumer14를 포함한다.
- 이미지의 앱·SQL108파일과 tests115파일, 설치된 package가 당시 workspace와 일치했다. [byte 검증](release-verification.json).

이미지: `palimpsest-effective-k2k:0.20.0`.

Image ID: `sha256:73a5d393571a1422edef213d6c76681f9f019dc9e187890d944e0cf79ae3013e`.

추가0020은 `palimpsest_effective_k2k_checks` 및 별도 `palimpsest_effective_k2k_demo`에만 적용했다. 기존 사용자 DB, 과거 SQL0001–0019, D/I와 이전 모델 실행을 다시 쓰지 않았다. 검사·모델 호출 명령은 `run-tests.py`, `live-demo.py`, 실제 request/response files에 재현 가능한 형태로 보존했다. 이번 application 기능은 source parsing이나 원문 재생성을 요청하지 않는다.

## 후속 범위

K2K의 EffectiveEdge 소비, endpoint-value 의무, pending release, nonmaterial support와 exact history를 구현했다. W/P Edge 소비·일반 lifecycle·대규모 paging은 별도다. 이후 사용자가 요청한 [모든 자료의 단일 Electron 앱](../../progress/T22_unified_electron_execplan.md)과 [Realm R의 I2K 기본 분리/명시적 교차](../../docs/decisions/REALM_SCOPE.md)를 진행한다.

사용자의 요청으로 기존 코드 Electron과 논문 Electron을 각각 실행했으며 화면 조작은 하지 않았다. 이 기존 창/패키지는 통합 UI를 검증하기 전까지 보존한다.
