# Decision·Wisdom·publication 계약

> 상태: PROPOSED IMPLEMENTATION CONTRACT · 주 승인 항목 P08.
> U08 부분 적용: R06의 명시적 supersedes 결정론적 W2KRecord effect/atomic commit 및 R09의 두 retrieval 축은 [해결 계약](../decisions/ARCHITECTURE_FIXES.md)의 정확한 범위에서 현재 규칙이다. 나머지 P 세부 제안/enum/DDL은 미승인이다.
> 기존 canonical 규칙을 요약한 부분과 이번 제안을 구분합니다. 관련 P 항목이 accepted되기 전에는 본문의 새 필드·enum·명칭을 production canonical 계약으로 사용하지 않습니다.


## 원본에서 유지하는 규칙

LLM recommendation은 commitment가 아닙니다. confirmed Decision W만 deterministic W2K됩니다. W/K/Record/provenance/outbox는 원자적이며, 진짜 재결정은 같은 선택이어도 새 event입니다. W/P/B는 immutable snapshot입니다. 근거: baseline §18–23, A12/A14/A15/A16/A18/A36–A40.

## 이번에 제안하는 구현 계약

### 1. Confirmation command

제안 입력: confirmation_event_id, actor_ref, confirmed_payload_digest, authoritative scope, decided_at, idempotency key. 사용자가 실제 확인한 structured payload와 digest를 결합합니다. LLM이 만든 confirmation_ref 문자열은 authority evidence가 아닙니다.

같은 confirmation event retry는 같은 Wisdom/K result를 반환합니다. 같은 key에 다른 payload는 conflict로 처리합니다. 새로운 confirmation event는 같은 선택이라도 새로운 decision입니다. `origin_wisdom_id` unique guard는 계속 유지합니다.

### 2. Action validation과 deterministic mapping

select는 selected_option이 필요합니다. defer는 defer_until 또는 defer_condition 같은 명시적인 보류 조건을 요구하는 안입니다. decline은 거부 대상/범위를 보존합니다. optional 필드 null과 미제공의 의미를 schema로 고정하고 actor 이유를 LLM이 채워 넣지 않습니다.

Decision K에는 origin_type을 명시하고, decided_at/effective_at 및 defer 조건 중 검색·적용 판정에 필요한 필드는 구조화 projection으로 전달하는 안입니다. 전체 원문 이유와 alternatives는 W에 남겨도 됩니다. mapping test는 W를 입력받아 정확히 같은 K payload가 나오는지 확인하며 LLM 호출 수 0을 요구합니다.

### 3. 정정과 재결정

표시 오탈자만 고치면 presentation projection입니다. 동일 사건의 material 기록 정정은 새 authority-bound correction evidence를 필요로 하며, 어떤 immutable W/confirmation의 내용을 어떻게 바로잡았는지 보존합니다. 실제 결정을 바꾸는 작업은 새 Decision W/K입니다. K만 수정해 사용자가 확인한 W와 불일치하게 만들지 않습니다.

명시적 supersedes 요청을 확정한 경우 결정의 존재/권한/scope를 확인하고 누락 없이 관계를 기록할 deterministic command 경로를 정합니다. N2E discovery가 우연히 edge를 만들기를 기다리지 않습니다. U08에서 명시적 supersedes는 primary decision KNode와 같은 W2KRecord에 연결된 typed effect로 고정했습니다. 새 public subtype 없이 같은 transaction에서 저장하며 나머지 P06 registry는 미정입니다.

### 4. 시간·부분 scope

future-effective D2는 유효 시점 전에는 D1을 즉시 inactive로 만들지 않습니다. 부분 scope 교체와 완전 교체를 구분합니다. 현재 active 상태는 as_of와 event history의 projection이며 immutable payload에 저장하지 않습니다. 시간 경과가 중요하면 time-triggered projection/revalidation obligation을 만들 수 있지만 과거 W를 자동 재작성하지 않습니다.

### 5. Retrieval의 두 축

제안: `evidence_mode = knowledge_only | knowledge_plus_evidence | evidence_only`, `retrieval_strategy = standard | decision_trace | history`.

원본의 retrieval_mode와 A18은 이 두 의미를 혼용합니다. U08은 새 current wire의 evidence_mode/retrieval_strategy 두 이름을 적용합니다. 과거 retrieval_mode는 immutable legacy read로 보존하며 evidence surface를 복원할 수 없으면 unknown/replay 제한을 표시합니다. 실제 DB migration은 없습니다. authority_confirmed trace는 origin W/confirmation을, reported trace는 I/D를 따릅니다. reported event를 사용자 commitment로 바꾸지 않습니다.

### 6. Wisdom·Parchment 품질

W 생성은 used effective refs, graph read receipt, claim-level citation mapping, direct-I 여부, pending/conflict/근거 부족을 저장합니다. “문헌에 그렇게 쓰였다”와 “현재 K로 채택했다”를 구분합니다. 오래된 W 자체를 덮어쓰지 않고 현재 관점 평가는 별도 W로 생성합니다.

P/B 편집에서 새 주장이나 citation 이동이 생기면 근거를 재검증하고 author-added/ungrounded를 표시합니다. immutable publication과 편집 중 draft workspace는 분리할 수 있지만 신규 public domain 이름은 이 패키지가 확정하지 않습니다. 생성물 재수입 lineage는 P07 계약을 따릅니다.

U08/R07 사용자 선택: 같은 배타적 decision 범위에서 prepare가 읽은 head 집합/state token을 확인 payload에 결합하고 commit까지 충돌 검출한다. 상태가 바뀐 늦은 요청은 canonical W/K를 만들지 않고 재확인하며 실행/확인 시도 이력은 보존한다. 권한 및 key/payload가 같은 기존 성공 retry는 저장된 결과를 반환한다. 별도 정상 사건을 내용으로 병합하거나 last-write-wins로 덮어쓰지 않는다.
