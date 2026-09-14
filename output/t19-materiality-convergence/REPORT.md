# 의미 변화 우선 전파 — 0.18

2026-09-14. 사용자의 정정에 따라 **새 run은 반복 자체로 멈추지 않고, 독립 materiality/equivalence 판정으로 새 의미 전파를 결정**하도록 수정했다. 앱0.18.0/schema0016 유지. [승인된 정정](../../docs/decisions/MATERIALITY_FIRST_PROPAGATION.md), [운영 안내](../../docs/interfaces/PROPAGATION_WORKER.md), [계획](../../progress/T19_materiality_convergence_execplan.md).

## 판단과 구현

감쇠나 수렴은 자동으로 보장되지 않는다. 작은 수치 변화가 threshold를 가로지르면 큰 논리 변화가 될 수 있고, 모순 없이도 새 결론을 무한히 추가하는 규칙이 가능하다. Contradict Edge는 상충을 보존하지만 수축 조건이나 어떤 주장을 선택할지까지 정하지 않는다. 현재 실제 N2E는 supports만 지원하며 Contradict predicate는 이번에 구현하지 않았다.

새 frozen policy는 `repeated_outcome=observe`, `materiality_policy=accepted-state-materiality-v1`이다. 반복 witness는 `semantic_return_observed`로 한 번 남기고 dispatch를 계속한다. 과거 T17의 halt policy·진단·확인 이력을 advisory였던 것처럼 바꾸지 않았다.

기존 structured `material_change`/reuse를 사용한다. 독립 Validator가 현재 accepted claim이 여전히 근거를 갖고 실질적 의미 변화가 없다고 확인하면 기존 Revision을 유지하고 새 semantic branch를 만들지 않는다. 다음 후보는 무시한 직전 후보가 아니라 마지막 accepted snapshot과 비교한다. discovery도 다른 FP라는 이유로 신규 K를 만들지 않으며, 같은 의미라면 current usable K를 재사용한다.

새 propagation request에만 K2K/N2E 지침을 추가했다. arbitrary numeric epsilon·embedding threshold·수렴 점수를 만들지 않고, 실제 근거나 명시된 domain precision/tolerance만 사용한다. 작은 polarity/unit/scope/quantifier/조건/절차 변경도 중요할 수 있다. uncertain/null을 false로 만들지 않으며, 상충 사실을 평균하거나 다른 실험 기록을 지워 수렴을 만들지 않는다. 기존 unbound/legacy prompt·schema 네 SHA 쌍은 변경 전과 byte-identical한 것을 확인했다.

의미 branch 종료와 provenance maintenance는 별개다. 바뀐 premise/current support를 소비한 후손의 재검증과 Wiki 갱신은 끝까지 유지한다. 이미 현재인 accepted 원래 derivation은 불필요한 LLM 재검증·지원 Record 회전 없이 exact support coverage로 처리한다. N2E applicability true↔false는 disposition이 no_material_delta여도 material effect임을 반영해, 그 node-only discovery 의무가 빠지지 않게 했다. EffectiveEdge를 직접 소비하는 K2K를 구현했다고 확대하지 않는다.

## 실제 검사

새 테스트7개는 실제 PostgreSQL에서 합성 Validator 판정을 입력해 다음을 확인했다.

| 상황 | 확인한 결과 |
|---|---|
| material A→B→A | advisory 한 번, 자동 보류/확인 요구 없이 scoped dispatch 완료 |
| 진폭이 줄어드는 수치 후보 뒤 nonmaterial | 마지막 승인 Revision 유지, 새 semantic outbox0 |
| 무시한 작은 변화 누적 | `0 → 0.004 → 0.008 → 0.012` 후보를 계속 accepted0과 비교; 마지막만 fixture의 material 판정으로 반영 |
| 다른 FP의 같은 의미 discovery 후보 | 기존 KRevision 재사용, 신규 K/outbox0 |
| 아주 작지만 독립적으로 material인 변화 | 숫자 크기로 억제하지 않고 Revision·outbox 생성 |
| 현재 유효한 원래 K2K support | LLM 재검증과 support 회전 없이 coverage 기록 |
| applicability true→false와 false→false | 전환은 material effect/후속 의무, 반복 negative는 새 outbox0 |

위0.01 기준은 **검사에만 있는 합성 독립 판정**이다. production에 입력한 허용 오차나 실제 LLM의 의미 판정 정확도 검증이 아니다. 감쇠/수렴 자체를 수학적으로 입증한 것도 아니다. [실제PG17개 — 새7개·기존전파/legacy10개](pg-first.log).

순수 지침·개정·K2K·N2E request 검사34개도 통과했다. 패키지 회귀44개의 개별 검사는 모두 통과했으나 K2K fixture class가 요구하는 DB 이름과 달라 setUpClass 오류가1개 있었다. 그9개 검사는 지정된 기존 합성 회귀 DB에서 다시 실행해 모두 통과했다. 명령 실패를 제거하지 않았다. 별도로 존재하지 않는 test_n2e 이름을 사용한 초기 명령 오류도 올바른 test_edge_requests로 수정했다.

- [순수34개](pure-guidance-final.log)
- [패키지44개와 fixture 설정 오류](package-regression.log)
- [K2K9개 후속](k2k-regression.log)
- [기존 사용자 코드 이력 read-only137개](history-proof.json)
- [T16 실제 Terra/Wiki 이력 호환18개](legacy-demo-compatibility.json)
- [배포 파일 일치](release-verification.json)

[집계](verification-summary.json)에서 중복을 제외한 관련 검사97개가 모두 통과했다. 첫 suite의 fixture 설정 오류와 후속 통과를 구분했다. [실제 반복 관찰 후 완료 기록](observed-return.json)은2개 outbox task가 보류·확인 없이 끝났음을 보여준다. 기존SQL16개SHA는모두동일하며 bundle 전체는기존948개문서오류로실패,이번수정문서범위오류는0개다.

새 provider 호출0, 새 migration0, 사용자 DB쓰기0이다. 집중 회귀와 기존 이력 대조를 수행했으며 전체 앱 suite를 새로 실행했다고 주장하지 않는다. 과거0001–0016SQLbytes와D/I/원문·Wiki 이력을 보존했다.

최종 이미지는 `palimpsest-propagation:0.18.0`, ID는 `sha256:82d81abe2b6bcb6d431e8fb9e53293fcc12cec5197ee830bd019d319c1424cb5`다. 앱/SQL99파일·검사104파일이 최종 workspace와 일치한다.

주요 실행은 `run-tests.py test_materiality_runtime test_propagation_runtime test_propagation_anomaly_runtime`이며, 기존 K2K class는 `run-tests.py --regression-database test_k2k_runtime`로 검증했다. 앱은 `docker build -t palimpsest-propagation:0.18.0 .`로 빌드했다. 새 수직 구현의 실제 사용자 자료/LLM 의미 품질 평가는 이번 합성 판정 검사와 별개다.
