# 전파의 반복 결론 진단과 운영 병목 후속

2026-09-14. 사용자는 완료된 전파 worker 이후의 다음 구현도 진행하도록 요청했다. T16/app0.16/schema0016을 보존하고 T07의 남은 AT05 중 결정론적으로 판별 가능한 반복 결론의 운영상 중단·재개를 다음 수직 구현으로 선택했다. 논문/코드 live DB migration, 새로운 원문 전송, D2I/D2K, K 폐기 정책, public Record subtype이나 전체 P 제안을 승인한 것으로 확대하지 않는다.

## 구현 목표

검증·반영된 같은 logical K가 정확히 같은 외부 K 전제와 현재 support·자료 버전·모델 profile에서 A→B→A로 되돌아가면, 추가 전파 전에 이를 진단하고 run을 미완료/검토 상태로 보존한다. Edge의 같은 semantic Revision·endpoint pair·현재 support에서 true→false→true도 구분한다. 비교 대상 자신의 Revision/이전 적용성/현재 근거, task/claim/전역 watermark 때문에 기준 hash가 매번 바뀌지 않게 한다. 단순 표현 차이를 새 의미라고 판별하는 LLM을 추가하지 않으며 exact normalized fingerprint/판정 반복만 자동 감지한다.

이미 독립 검증되어 반영된 K/관계는 과거 이력으로 유지한다. 진단은 그 판정을 거짓으로 재분류하거나 canonical rollback하지 않고 outbox 작업과 미처리 후속 의무를 보존한 채 다음 dispatch·Wiki 게시를 멈춘다. 사용자의 명시적 재시도는 해당 진단만 확인한 것으로 기록하고, 현재 전제/target/source version을 다시 확인한다. 변경된 범위에 옛 확인을 재사용하지 않는다. 깊이·개수·비용 성공 cutoff는 없다.

안전한 부속 수정으로 maintenance-only 실행에서 사용하지 않는 discovery 전체 그래프 조회를 제거한다. 대규모 paging은 실제 병목과 필요한 durable cursor/coverage 계약을 따로 검토하며, 한 번에 모든 T07/100001 fanout 완료를 주장하지 않는다.

## 계약·소유권

읽은 계약: USER_OVERRIDES, DECISION_REGISTER, T07, canonical07의 운영 anomaly, contracts03/R03, PLANS, CODE_REVIEW, 현재 전파/명시 개정/재검증 구현. ponytail 원칙에 따라 기존 불변 propagation_events/task states/lease/commit을 사용한다. Root가 새 진단 모듈·Runtime/queue 통합과 실제PG를 소유한다. contract agent는 fingerprint/재개 의미를 독립 검토하고 SQL agent는 paging 병목을 읽기 전용으로 검토한다. 기존0016 및 모든 이전 migration bytes를 수정하지 않는다.

## 검증과 완료 조건

순수 검사: 같은 전제의 A→B→A, 같은 결과 반복/no-material, 전제 Revision·support·DataVersion·profile 변화, 독립 logical K, 최신 적용성 false와 pending 구별, 진단 idempotency/명시 재시도/freshness, maintenance-only 조회 방지.

실제PG: synthetic로 명시한 accepted revision trajectory에서 저장된 outbox를 처리해 진단/남은 의무·기존Revision보존, pause/resume만으로 해제되지 않음, 이유를 둔 정확한 재시도와 stale 거절, 재시작 후 같은 진단 유지, 새 근거의 정상 A→B→A 오탐 방지. 현재 node-only/DAG 구조 때문에 이 fixture를 일반 live LLM 무한루프 재현이라고 표현하지 않는다. 새 actual provider 호출은 필요하지 않으며 T16의 실제8회 검증 이력을 읽기 전용으로 확인한다.

## 완료 결과

앱0.17/schema0016에서 구현했다. `propagation_anomalies.py`는 exact canonical 전이와 연속 입력 구간을 읽어 witness를 만들고, 기존queue/run/events로dispatch를중단한다. CLI는 `retry --acknowledge-anomaly`와actor/reason을받으며 scope/premise/support/version확인과ack/task재시도를동일transaction에기록한다. oldpolicy는변경하지않는다.

초기pure11와실제PG4가통과했다. 독립검토에서 needs_human전환의epoch증가가0016guard와충돌하는부분을제거하고, 다른blocked task의retry로run보류를우회하지못하도록보완했다. 두수정은새SQL없이현재상태규칙안에서처리했다. Edge연속성은같은pair만찾아중간다른pair평가를건너뛰지않고semanticEdge의전역직전event를확인한다.

최종집중회귀64/64(161.709초),배포이미지내순수/controller30/30,기존사용자코드이력read-only137/137,저장된합성진단/확인/완료대조5/5,T16실제Terra/Wiki이력호환18/18이통과했다. 새provider0,새migration0,사용자DB쓰기0이다. 실제PG trajectory는합성판정으로만든3-revision상황이며liveLLM무한루프실험으로표현하지않는다. 순수151-step목록검사도실제128canonicalchain또는100001fanout검증으로확대하지않는다.

이미지는 `palimpsest-propagation:0.17.0`, SHA는 `sha256:2731f2c99086add58ceb7ce39cffbab60c1f7851bc9fbc927ea891aea3a4bd8e`다. 기존0001–0016SQLbytes·usercode/paperDB·원문·과거Wiki와T16실험파일을보존했다. 이번범위는완료했고 [결과](../output/t17-propagation-anomaly/REPORT.md)에기록했다. [T18paging후속안](T18_dependency_paging_proposal.md)은별도제안이며아직구현/실행하지않았다.
