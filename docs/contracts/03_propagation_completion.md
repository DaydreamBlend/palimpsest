# Cap 없는 전파·완료 판정·중단과 재개

> 상태: PROPOSED IMPLEMENTATION CONTRACT · 주 승인 항목 P03.
> U08 부분 적용: R03의 scope/causal-descendant 의무 열거·receipt·completion fence·비성공 중단 요구은 [해결 계약](../decisions/ARCHITECTURE_FIXES.md)의 정확한 범위에서 현재 규칙이다. 나머지 P 세부 제안/enum/DDL은 미승인이다.
> 기존 canonical 규칙을 요약한 부분과 이번 제안을 구분합니다. 관련 P 항목이 accepted되기 전에는 본문의 새 필드·enum·명칭을 production canonical 계약으로 사용하지 않습니다.


## 원본에서 유지하는 규칙

전파의 크기·깊이·Record 수·총 token·총 비용을 정상 semantic completion cap으로 쓰지 않습니다. material delta만 다음 의미 재검증을 유발하며 non-material 결과는 그 객체에서 branch를 멈춥니다. derivation depth는 metadata입니다. 근거: baseline §17와 A10/A25/A34.

## 이번에 제안하는 구현 계약

### 1. 두 종류의 work

`maintenance/revalidation`은 기존에 알고 있는 exact dependency에 대한 의무적인 영향 평가입니다. reverse dependency index를 누락 없이 페이지 단위로 열거합니다. RAG top-K로 의무 대상을 버리지 않습니다. paging/chunking/worker concurrency는 메모리와 처리율 관리이며 전파 범위 cap이 아닙니다.

`discovery`는 아직 없는 관련 K/관계 후보의 탐색입니다. policy와 retrieval context의 범위를 명시합니다. discovery zero-output은 평가한 context에서 후보가 없었다는 뜻이지 모든 가능한 지식의 완전성을 뜻하지 않습니다. 두 work의 완료 정보를 분리하고, discovery 때문에 이미 확정된 사용자 질의를 자동 재생성하지 않습니다.

### 2. Revalidation loop

```text
material canonical effect commit + outbox
→ enumerate exact affected subscriptions (paged, no target truncation)
→ claim/coalesce work with frozen relevant input state
→ evaluate and validate
→ compare with current accepted state
→ short transaction: freshness + base CAS + effects + outbox
→ material effect: enumerate next obligations
→ non-material/none: update receipts/projections, no new semantic branch
```

새 근거 receipt, projection rebuild, blocked work release는 maintenance입니다. 이를 지식 생성 branch와 혼동하지 않습니다. 한 대상의 no_material_delta는 다른 부모로부터 들어온 별도의 material obligation까지 없애지 않습니다.

### 3. Completion receipt

새 canonical domain 계층이 아니라 runtime execution receipt로 다음을 기록하는 안입니다.

- 관찰한 source/event watermark와 policy snapshot.
- 의무 dependency enumeration의 완료 cursor/coverage.
- pending outbox, ready job, leased/in-flight job, retryable job, blocked dependency/human review의 수와 식별 근거.
- 처리한 root와 합쳐진 모든 root obligation.
- 실제 종료 상태와 미완료 이유.

정상 quiescence는 해당 scope/watermark에서 enumeration이 끝났고, commit됐으나 아직 dispatch되지 않은 material event가 없으며, in-flight 작업과 미완료 의무가 없을 때만 선언합니다. queue length=0 하나로 판단하지 않습니다. completion 판정과 concurrent commit 사이의 race를 막는 fence/checkpoint 검사를 P05와 함께 구현합니다.

이것은 “전역 가능한 KGraph의 수학적 fixed point를 증명했다”는 뜻이 아닙니다. 외부 입력이 계속 유입되는 상황에서는 특정 watermark까지의 완료만 보고하고 다음 입력은 새 obligation으로 처리합니다.

### 4. Runtime 상태 제안

`queued`, `running`, `blocked_dependency`, `blocked_human`, `retry_wait`, `paused_user`, `suspended_anomaly`, `failed`, `cancelled`, `quiescent`를 runtime 레벨에서 구분하는 안입니다. 기존 proposal의 execution_status/disposition enum을 조용히 바꾸지 않습니다. resume은 current freshness를 확인하며 stale 결과를 무조건 재commit하지 않습니다.

### 5. 비수렴과 운영 제어

LLM 생성·revision이 비단조적이므로 종료는 자동 보장되지 않습니다. stable-input 상태에서 A→B→A 반복, 반복 CAS 실패, provider 연속 실패, 동일 work의 재enqueue를 진단합니다. 단순히 정상적인 큰 fanout이나 오래 걸리는 queue라는 이유로 anomaly로 단정하지 않습니다.

pause/cancel은 허용되며 남은 obligation과 미완료 상태를 보존합니다. 자원 부족, API 제한, 수동 중단은 성공으로 표시하지 않습니다. provider per-call timeout, rate limiting, backpressure는 유지하되 작업을 버리지 않습니다. anomaly threshold는 운영 설정이고 지식 완성도 cap이 아닙니다.

### 6. 필수 반례

AT01: 긴 material chain은 depth 값 때문에 잘리지 않습니다.
AT02: 중간 non-material target에서는 새 semantic descendant job이 없습니다.
AT03: direct dependency가 RAG 밖에 있어도 평가합니다.
AT04: outbox/lease/human pending이면 quiescent가 아닙니다.
AT05: oscillation은 진단/중단/재개로 처리하며 cap-success로 바꾸지 않습니다.
AT79: root가 바뀌어도 derivation metadata가 리셋되지 않습니다.
