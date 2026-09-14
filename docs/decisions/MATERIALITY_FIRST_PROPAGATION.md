# 반복 패턴보다 의미 변화로 전파 종료 판단

2026-09-14 사용자 정정. 사용자는 “단순히 루프가 있다고 중단하지 말고” 의미 변화가 미미해지면 전파를 멈추도록 요청했다. 이는 T17의 신규 run에서 exact 반복만으로 자동 보류하고 확인받던 기본 정책을 대체한다. 과거 frozen policy·판정·진단·확인 이력은 그대로 보존한다.

새 run은 `repeated_outcome=observe`, `materiality_policy=accepted-state-materiality-v1`을 동결한다. 같은 결과로 돌아오면 진단을 기록하지만 반복 횟수나 모양만으로 중단·기각·승인·reuse하지 않는다. 실제 전파는 독립 Validator의 materiality/equivalence 판정과 저장된 효과를 기준으로 한다.

현재 accepted snapshot과 비교해 의미·truth condition·사용 가능한 추론·판단·절차에 실질적인 변화가 없고, 현재 근거가 그 unchanged claim을 여전히 지지하면 기존 Revision을 재사용하고 새 semantic branch를 만들지 않는다. 무시한 candidate를 다음 비교 기준으로 이동시키지 않는다. 새로운 discovery도 다른 FP라는 이유만으로 새 K가 되지 않으며, 같은 의미의 current usable K로 재사용한다. 불확실한 판정을 false로 축소하지 않는다.

공통 numeric epsilon, embedding 거리나 강제 평균을 진실·materiality 기준으로 만들지 않는다. 정밀도·허용 오차는 실제 근거나 명시된 domain policy가 있어야 한다. 작은 극성·단위·범위·조건·양화사·절차 순서의 변화도 중요할 수 있다. 서로 다른 실험 및 상충하는 주장을 지워 수렴을 만들지 않는다.

R02/R03의 provenance maintenance와 완료 조건은 유지한다. 같은 결론이라도 premise/current support가 바뀌면 exact 지원 경로와 소비자의 재검증·Wiki 갱신이 필요하다. 이미 현재이고 유효한 원래 derivation은 불필요하게 다시 검증하지 않는다. N2E의 true↔false applicability 변화는 semantic EdgeRevision 보존과 별개로 material 효과다. K2K의 직접·간접 자기 전제 금지는 그대로다.

감쇠나 수렴은 자동 보장되지 않는다. 작은 입력 변화가 임계 판단을 크게 바꿀 수 있고, 모순이 없어도 새 결론을 계속 생성할 수 있다. Contradict Edge는 상충 관계를 보존하지만 선택·보류·수축 조건을 대신하지 않는다. 현재 실제 N2E는 supports를 지원하며 새 predicate/충돌 처리 정책은 이번 승인 범위에서 추가하지 않는다.

운영상 pause/cancel, lease/transport failure, 근거 불충분 및 미완료 의무는 계속 유지한다. 끝나지 않은 일을 비용·깊이·개수 cap으로 성공 처리하지 않는다. 신규 정책과 실제 검사는 [T19 결과](../../output/t19-materiality-convergence/REPORT.md), [운영 안내](../interfaces/PROPAGATION_WORKER.md)에 기록한다.
