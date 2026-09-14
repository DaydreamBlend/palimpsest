# 명시적 Knowledge 의미 개정

2026-09-14 최신: [materiality 우선 전파](../decisions/MATERIALITY_FIRST_PROPAGATION.md)는 새 propagation 요청에서 현재 accepted target을 기준으로 의미 변화와 기존 주장에 대한 근거를 독립 검증한다. nonmaterial 후보로 비교 base를 이동시키지 않고, 반복만으로 중단하지 않는다. 구조화된 기존 material_change/reuse 필드와 역사 보존은 유지한다.

2026-09-14 후속: 저장된 변경 영향/outbox를 소비하는 [전파 worker](PROPAGATION_WORKER.md)가 앱0.16/schema0016에서 기존 node/edge 의무 재검증과 Wiki 갱신을 연결한다. 같은 의미는 원래 Revision/기원을 유지하고 current support를 추가한다. 아래의 explicit target 개정과 실제 현재 전제 검사는 계속 적용되며 자동 D2I/D2K 복구를 허용하지 않는다.

새 I2K/K2K 요청에서 사용자가 지정한 KNode와 현재 Revision을 비교 대상으로 고정한다. 기존 연산의 후보·Record·근거·commit을 재사용하며 새 public operation을 만들지 않는다. [사용자 승인](../decisions/USER_REQUESTED_D2K.md)의 후속 의미 개정 원칙을 따른다.

```text
palim knowledge prepare --operation i2k --data-id DATA_SHA --request-id REQUEST_UUID --input COMPLETE_I_INPUT_JSON --target-knode-id KNODE_UUID --expected-revision-id CURRENT_REVISION_UUID --json
palim knowledge revision-call EXECUTION_UUID --phase generator --directory CALL_DIRECTORY --json
palim knowledge stage EXECUTION_UUID --response GENERATOR_RESULT_JSON --json
palim knowledge revision-call EXECUTION_UUID --phase validator --directory CALL_DIRECTORY --json
palim knowledge decide EXECUTION_UUID --response VALIDATOR_RESULT_JSON --json
palim knowledge show EXECUTION_UUID --json
```

K2K도 같은 옵션을 사용하되 실제 accepted K 전제를 입력한다. 비교 대상은 추가 근거나 추론 전제가 아니며, 대상을 직접 또는 간접 전제로 사용해 자기 successor를 만들 수 없다. I2K는 source-only multi profile로 전체 원문 I 검토를 유지한다. I2K의 I 부족 오류·보류 규칙도 그대로 적용된다. D2K의 현재 사용자 확인은 생성·재사용·근거 추가만 허용하며, 이 옵션으로 의미 개정을 실행할 수 없다.

## 판정

Generator는 기존 연산 schema로 최대 한 후보를 반환한다. 정상 정규화 후 Runtime이 exact target과 고정 논리 FP를 연결한다. 후보가 없으면 비교가 해결되지 않았으므로 `needs_human`으로 남는다. 모델이 target ID·FP·canonical ID를 지정하지 않는다.

독립 Validator는 일반 원문/추론 검증에 더해 `revision_review`를 반환한다. 필드는 정확한 `comparison_base_revision_id`, `same_identity`, `material_change`, `grounding_valid`, 이유와 reason codes다. `material_change=null`은 판정 불가이며 false와 다르다. 문장이나 JSON 값이 달라졌다는 사실만으로 의미 변화를 인정하지 않는다.

| 판정 | canonical 결과 |
|---|---|
| 같은 의미·근거 유효 | 기존 Revision·생성 origin 유지, 유효한 support 추가 |
| 같은 논리적 K·실질적 의미 변화·근거 유효 | 같은 KNode·논리 FP 아래 새 content FP·Revision·origin Record |
| 정체성·근거·변화 불확실 | 후보와 이유를 남기고 보류 |
| 준비 이후 대상이 개정됨 | 옛 비교로 두 번째 개정을 만들지 않고 재검토 필요를 기록 |

두 요청이 같은 Revision으로 준비되더라도 먼저 반영된 개정만 현재 참조를 바꾼다. 뒤의 요청은 exact target 검사에서 보류한다. 실제 I 입력·K2K 전제·자료 버전의 유효성 검사도 유지한다.

## 이력·영향

새 Revision, I grounding 또는 K2K derivation, 판정 Record, 현재 포인터 CAS, N2E/K2K outbox와 이전 Revision의 변경 영향 목록을 같은 트랜잭션에 반영한다. 도중 실패하면 함께 rollback하고 원래 후보로 재시도한다. 과거 Revision·원문 위치·과거 답변 인용을 덮어쓰지 않는다.

`k_revision_targets`, `k_revision_decisions`, `k_revision_impacts`는 추가-only Compiler Runtime 기록이다. 직접 K2K 전제, 원래 KEdge Revision, 적용성 event의 endpoint, Wiki snapshot의 K 링크를 제한 없이 열거한다. 전체 자동 전파 완료는 아니며 `outbox_pending_not_converged`를 유지한다. 자동 scheduler와 Wiki 재생성·검증은 별도 후속이다.

개정 후에도 논리 identity FP는 바뀌지 않는다. 일반 I2K/K2K에서 현재 content FP·kind·scope가 정확히 같은 후보가 나오면 현재 Revision을 재사용한다. 서로 다른 source의 실험 결과를 합치지 않는다. 여러 논리적 K가 같은 현재 내용으로 조회되면 임의로 선택하지 않고 중복 검토를 남긴다.
