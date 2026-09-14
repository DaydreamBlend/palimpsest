# ExecPlan contract

이 파일은 Codex가 복잡한 task의 실행 계획을 만드는 규약입니다. `AGENTS.md`에서 명시적으로 참조하므로 작업 시작 시 읽습니다. 이름만으로 자동 실행되는 기능이나 background worker 설정이 아닙니다.

## 계획 파일

task마다 `progress/Txx_execplan.md`를 만듭니다. 다른 task의 기록을 덮어쓰지 않습니다. 다음 항목을 실제 내용으로 작성합니다.

1. 목표와 사용자가 관찰할 수 있는 완료 동작.
2. 현재 repository에서 확인한 구현 경로·실행 명령·제약.
3. 읽은 current canonical 절, 적용된 U01–U03, 실제 승인된 P 항목, archived 근거와 unresolved blocker.
4. 변경할 파일/모듈과 변경하지 않을 범위.
5. 작은 구현 순서와 rollback/recovery 방법.
6. AT 시나리오 및 실제 test 경로, red/green 관찰 결과.
7. 수행한 commands/결과, surprise, 설계 선택의 근거.
8. 남은 일, 검토 의견, 다음 task 인계.

계획은 구현에 따라 갱신하지만 이전 failed result를 지워 성공처럼 만들지 않습니다. 명령 실패, 환경 미구성, 테스트 미실행은 각각 구분합니다. 장기 작업이 중단되면 다른 세션이 이 파일만 읽어도 정확한 상태와 다음 검증을 알 수 있어야 합니다.

## Task 경계

하나의 task에 source 보존·schema·worker·CLI·모델 튜닝을 모두 몰아넣지 않습니다. 새 문제가 작업 범위를 넘으면 finding/decision으로 기록하고 필요한 단계만 다시 계획합니다. 사용자 승인이 필요한 변경은 해당 부분만 blocked로 남기고 독립적인 안전 작업을 수행할 수 있습니다.

## Completion report

요구 AT IDs, 실행 test paths, 실행 command와 exit 결과, 실제 관찰, 미실행/blocked 이유를 기록합니다. 단순 “구현 완료”나 “테스트 통과”만 적지 않습니다. 아래 package validator의 성공을 app 완료 증거로 사용하지 않습니다.
