# 현재 근거·compiler 검증·판정과 effect

> 상태: PROPOSED IMPLEMENTATION CONTRACT · 주 승인 항목 P04.
> U08 부분 적용: R02/R04의 current support receipt/dependency, no-material maintenance 및 사전 cache와 사후 attribution 분리은 [해결 계약](../decisions/ARCHITECTURE_FIXES.md)의 정확한 범위에서 현재 규칙이다. 나머지 P 세부 제안/enum/DDL은 미승인이다.
> 기존 canonical 규칙을 요약한 부분과 이번 제안을 구분합니다. 관련 P 항목이 accepted되기 전에는 본문의 새 필드·enum·명칭을 production canonical 계약으로 사용하지 않습니다.


## 원본에서 유지하는 규칙

Information은 source fidelity를 검증한 것이지 세계적 진실 인증이 아닙니다. Candidate는 승인 전 canonical이 아닙니다. K의 같은 의미에 새 근거가 생기면 semantic Revision 없이 grounding을 추가합니다. origin provenance는 immutable입니다. 근거: baseline §6, §8–12, §17.

## 이번에 제안하는 구현 계약

### 1. Creation provenance와 current support

최초 KRevision을 만든 입력 refs는 절대 치환하지 않습니다. 별도로 current validity를 뒷받침한 revalidation receipt와 active support membership을 append-only로 보존하는 안입니다. 새 I로 재검증해 의미가 그대로여도 해당 I→K dependency를 등록해야 다음 변경이 전달됩니다.

support receipt의 제안 내용은 target exact revision, 검증에 사용한 current I/K/effective-edge refs, superseded support receipt, outcome, validator profile, origin Record, commit sequence입니다. 이것을 새로운 InformationRevision이나 KNodeRevision으로 만들지 않습니다. 현재 grounding이 참이라는 것은 검증 결과이지 append만으로 자동 성립하는 사실이 아닙니다.

### 2. Evidence-state impact

단순 근거 행 추가는 non-material입니다. 그러나 usable→unsupported 같은 actual evidence/validity state 변화는 별도 승인 effect가 될 수 있습니다. 어느 상태 변화가 downstream이 소비하는 의미 상태인지 registry로 정합니다. 강도/독립성 값을 임의 확률로 만들지 않습니다.

derived knowledge에 대한 검증은 leaf evidence, 적용 범위, 상충 근거, source lineage를 확인합니다. same-model independent prompt는 별도 inference일 뿐 오류 독립성의 보증으로 기술하지 않습니다. 회귀 평가에 과잉 승인과 과잉 기각을 모두 포함합니다.

### 3. Output authority

Operation×kind registry를 structural check에서 강제합니다. K2K는 새 observation과 authority_confirmed decision을 만들지 않습니다. observation의 단순 정정·추론 산출량의 분류는 approved kind schema를 따릅니다. 가설을 관찰로 위장하지 않습니다.

### 4. Result envelope와 state transition

P06 승인이 필요한 제안입니다. `mode`, `validation_outcome`, `disposition`, `canonical_effects`, `propagation_impact`의 조합을 registry로 고정합니다. LLM이 propagation_impact를 마음대로 선언하게 하지 않고 검증된 before/after effect에서 deterministic하게 산출합니다.

`no_material_delta`는 semantic Revision이 없다는 뜻이며 검증 receipt/applicability/grounding effect가 없다는 뜻은 아닙니다. 명시적으로 승인된 invalidation/applicability-loss effect를 rejected candidate와 혼동하지 않습니다. effect 승인용 disposition 추가 여부와 I 기반 K revalidation의 public subtype 이름은 P06의 승인 항목입니다.

### 5. Prompt contracts

Generator 입력은 operation, schemas, exact inputs, bounded per-call context와 policy입니다. 출력은 structured candidate/effect proposal이며 tool instruction이나 authority confirmation이 아닙니다. Validator는 raw chain-of-thought를 근거로 사용하지 않고 candidate, exact evidence, structural checks, context를 검사합니다.

validator finding은 짧은 검증 가능한 이유, reason code, cited refs, materiality/authority 판단을 담습니다. 실제 provider/model/prompt version 선택은 P12 뒤에 합니다. prompt template이 assertion을 증명하지는 않으므로 independent gold cases가 필요합니다.

### 6. Audit

terminal payload 정책, optional noncanonical audit retention, model_calls raw-output 정책을 하나로 맞춥니다. raw payload가 없으면 hash로 내용을 복원할 수 있다고 말하지 않습니다. 보존 종료 후 replay의 제한을 명시하며 private chain-of-thought를 저장하지 않습니다.
