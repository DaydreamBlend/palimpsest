## 17. Convergent propagation

I2K, N2E, K2K, W2K와 Information supersession/invalidation 기반 K 재검증은 서로 후속 작업을 만들 수 있다. Palimpsest는 이를 recursion이나 고정 크기 budget으로 자르지 않고, **material effect의 필수 dependency를 모두 열거하고 scoped quiescence를 확인하는 event propagation**으로 실행한다.

### 17.1 Causality와 관찰 가능성

모든 KCompilationRecord는 다음을 가진다.

```text
root_record_id
parent_record_id
propagation_depth
```

필드 각주:

| 필드 | 설명 |
|---|---|
| `root_record_id` | 하나의 연쇄적 Knowledge compilation을 처음 시작한 Record다. 해당 root/scope의 causal obligation과 scoped completion을 추적하는 기준이다. |
| `parent_record_id` | 현재 Record를 직접 발생시킨 직전 Record다. |
| `propagation_depth` | root에서 현재 Record까지의 실행 단계를 기록하는 causality/observability metadata다. 값이 커졌다는 이유만으로 branch를 종료하지 않는다. |

root 아래의 Record chain은 cycle 없이 재구성 가능해야 한다. `propagation_depth`와 `derivation_depth`는 추적과 설명을 위한 값이지 hard cutoff가 아니다.

### 17.2 Material-delta gate

후속 propagation은 disposition 이름만으로 결정하지 않고 `canonical_effects`와 `propagation_impact`를 함께 본다.

```text
propagation_impact = material
→ affected downstream object를 재검증

propagation_impact = non_material | none
→ 새 downstream branch를 만들지 않음
→ 새 semantic branch만 종료; support/dependency maintenance·기존 의무 release는 보존
```

대표적인 `material` effect:

- 새 KNode/KEdge의 acceptance
- KNode/KEdge의 material semantic Revision acceptance
- usable object의 invalidation/supersession처럼 current graph 의미를 바꾸는 lifecycle effect
- `KEdgeApplicabilityEvent(not_applicable)`처럼 current graph에서 관계의 적용 여부가 materially 달라지는 effect

대표적인 `non_material` effect:

- `no_material_delta`
- style/paraphrase-only 차이
- 동일 semantic K에 대한 `grounding_added`
- endpoint 변경 뒤 relation semantic이 그대로임을 확인한 `KEdgeApplicabilityEvent(applicable)`
- 검색 projection/embedding 재생성처럼 canonical semantic graph를 바꾸지 않는 effect

따라서 **재검증 결과의 차이가 무시 가능하면 Node/Edge semantic Revision을 만들지 않고 그 객체에서 propagation branch를 종료한다.**

### 17.3 Scoped quiescence — propagation hard cap 없음

정상 종료는 명시된 scope/source watermark/policy와 그 입력이 유발한 causal descendants에 대해 다음을 함께 만족할 때다.

> **필수 dependency 열거가 완료되고 pending outbox·ready·leased/in-flight·retry·blocked/human 의무가 없으며, 동시 obligation 등록과 충돌하는 completion fence/checkpoint로 그 상태를 확인했다.**

maintenance/revalidation은 exact reverse dependencies를 누락 없이 page 단위로 열거한다. discovery/context의 top-K가 필수 의무를 제한하지 않는다. scope/watermark·정책·열거 coverage·미완료 의무·종료 사유를 receipt로 남긴다. watermark 뒤에 commit된 causal descendant도 원래 scope의 의무이며 제외하지 않는다. 외부 새 입력은 새 scope가 될 수 있다. discovery zero-output은 그 context의 결과이며 전역 가능한 지식의 수학적 fixed point 증명이 아니다.

즉 다음과 같은 propagation-level hard cap을 정상 completion 조건으로 두지 않는다.

```text
max_depth
max_records
max_generator_calls
max_validator_calls
max_total_tokens
max_total_cost
propagation_deadline
per_logical_object_revision_limit
max_epistemic_derivation_depth
```

실제 변화가 10단계 뒤까지 이어지면 10단계까지, 100,000개의 객체에 material 영향이 있으면 그 scope의 모든 영향 의무가 소진될 때까지 재검증한다. 반대로 바로 다음 객체에서 `no_material_delta`가 나오면 새 semantic branch는 끝나지만 검증된 support/dependency 갱신과 이미 존재하는 의무는 보존한다.

한 번의 LLM 호출에는 provider/context-window 한계와 timeout이 있을 수 있다. 이는 해당 Operation attempt의 기술적 실행 제한이며, 전체 propagation을 “충분히 처리했다”고 간주해 잘라내는 semantic cap이 아니다. 기술 실패는 retry/resume 대상으로 남긴다.

### 17.4 Visited/idempotency guard

cap을 없애더라도 동일 graph state의 동일 계산을 반복해서는 안 된다. 같은 compiler profile 안에서 다음 조합은 재실행하지 않는다.

- 동일 attempt fingerprint
- 동일 N2E semantic edge + exact current endpoint revision pair + policy
- 동일 K2K input subgraph fingerprint
- 동일 logical object가 동일한 effective input/context fingerprint에서 이미 terminal 검토됨

visited guard는 propagation 범위를 임의로 줄이는 heuristic이 아니라 **동일 상태에 대한 중복 계산 방지**다. input revision, relevant validation context 또는 policy가 materially 달라지면 새 attempt가 될 수 있다.

### 17.5 Derivation depth의 역할

`derivation_depth`와 evidence distance는 root를 넘어 누적한다. 그러나 특정 숫자를 넘었다는 이유만으로 K를 거부하거나 propagation을 중단하지 않는다.

```text
derivation_depth
→ provenance/uncertainty/inspection metadata
→ Validator가 근거의 간접성을 이해하는 신호
→ hard cutoff 아님
```

간접 derivation이 길수록 transitive grounding, 독립 Data support, scope drift와 uncertainty를 더 면밀히 평가할 수 있지만 최종 판단은 근거와 semantic validity에 의해 이루어진다.

### 17.6 Operational anomaly와 비수렴

고정 cap을 제거했다고 해서 실제 버그나 oscillation을 무한 실행해야 한다는 뜻은 아니다. 다음 현상은 정상적인 semantic convergence가 아니라 operational anomaly다.

- 같은 logical object의 Revision이 앞뒤 의미로 반복 oscillation
- queue frontier가 장기간 줄지 않고 동일 component를 반복 순환
- CAS conflict/retry가 비정상적으로 반복
- 동일 causal component에서 예상할 수 없는 revision churn이 지속
- model/provider 오류 때문에 같은 기술 attempt가 계속 실패

이 경우 runtime은 작업을 성공 완료로 자르지 않고 예를 들어 `suspended_anomaly` 또는 동등한 명시적 오류 상태로 정지·보고한다. 운영자가 원인을 수정한 뒤 같은 causal root를 resume할 수 있어야 한다.

anomaly detector에는 운영상 threshold가 필요할 수 있지만, 그 threshold는 **Knowledge가 충분히 전파되었다고 판정하는 epistemic cap이 아니다.**

### 17.7 Profile 변경

model/prompt/policy version이 바뀌었다는 이유만으로 모든 과거 입력 조합을 자동 재실행하지 않는다. 새 D/I/K trigger 또는 명시적 recompile 요청이 있을 때만 다시 탐색한다.

---

