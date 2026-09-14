# T18 후속 제안 — 정확한 의존 관계의 페이지별 처리

상태: **PROPOSAL / 미구현·미실행**. 2026-09-14 읽기 전용 코드 검토를 바탕으로 한 후속안이다. T17의 의미 진동 감지·불필요한 discovery 조회 제거와 구분한다. 새 migration 번호나 설치, 128 chain·100001 fanout 검증을 승인·완료한 기록이 아니다.

근거: [R02/R03](../docs/decisions/ARCHITECTURE_FIXES.md), [전파 완료 계약](../docs/contracts/03_propagation_completion.md), [T07](../tasks/T07.md), [AT01/03/04](../tests/specs/ACCEPTANCE.md). 페이지 크기는 한 번의 작업량이다. 마지막 페이지 전의 pause·crash·실패는 미완료이며, 알려진 의존 관계를 검색 top-K로 줄이지 않는다.

## 관찰한 병목

| 경로 | 현재 동작 | 영향 |
|---|---|---|
| `propagation_runtime._expanded` | 전체 `_nodes`, `knowledge_provenance.load`, 전체 `_edges`와 전체 impact를 읽는다. dependency마다 `next(... nodes ...)`도 반복한다. | 작은 adjacency를 처리해도 전체 DB 규모에 비용이 비례하며, fanout과 전체 node 수를 곱하는 탐색이 생긴다. |
| `KnowledgeRuntime._nodes` / `knowledge_provenance.load` | 현재 node뿐 아니라 모든 과거 Revision·derivation·I/D grounding·support refs를 읽고 JSON 복사한다. | worker에 필요 없는 원문 quote·과거 이력까지 메모리에 올라온다. `_inference_input`도 이 경로를 사용하므로 enqueue만 페이지화해서는 끝나지 않는다. |
| `enumerate_impacts` / schema0015 | 모든 direct dependency를 `fetchall()`하고 immutable JSONB snapshot을 저장한다. DB guard도 전체 snapshot을 다시 비교한다. | 이미 저장된 snapshot을 그대로 Python에 가져오면 큰 fanout에서 메모리와 하나의 transaction 시간이 커진다. |
| `queue.harvest` | 매번 전체 outbox/support 중 root·causal child를 찾고, 미수집 결과를 전부 가져온다. | unrelated DB 이력이 커지면 매 claim/settle마다 불필요한 스캔이 반복된다. |
| `queue.settle` / `_release_dependencies` | 모든 task payload를 읽어 개수를 세거나, `show()` 전체 결과에서 대기 항목을 찾는다. | 100001개 task의 이미 끝난 payload까지 계속 역직렬화한다. |
| `_expanded` 완료 이력 | 전체 impact 및 전체 child ID 목록을 event/outcome에 다시 넣는다. | 읽기만 페이지화해도 마지막에 큰 목록을 다시 구성하면 메모리 절감이 사라진다. |

현재 코드는 연결이 없는 과거 참고까지 보존한 뒤 active support를 판별한다. 최적화에서도 **historical/inactive로 제외한 이유**와 **현재 반드시 처리할 대상**을 구분해야 한다. scope 밖의 필수 대상은 보류 대상이지 조용히 생략할 대상이 아니다.

## 권고하는 작은 구현 순서

### 1. 결과를 바꾸지 않는 조회 축소

- worker용 `node_headers` / `edge_headers`를 정확한 ID 집합으로 조회한다. ID·current Revision·fingerprint·kind·scope·현재 support와 input signature에 필요한 값만 가져온다. 전체 graph UI/이력 조회의 기존 API는 유지한다.
- 실제 모델 요청에는 선택된 입력과 그에 필요한 정확한 provenance closure만 hydrate한다. ancestry의 깊이 cap은 두지 않는다. 원문 전체 grounding을 읽어 나중에 quote를 지우는 방식도 피한다.
- current consumer 확인은 `result_revision = node.current_revision`와 `dep.record_id = current_k_support_record(result_revision)`를 SQL에서 평가한다. 전체 node list에서 매번 선형 탐색하지 않는다.
- `settle`은 SQL `COUNT ... FILTER`와 `EXISTS`로 상태를 집계한다. 전체 task/blocked ID 목록은 별도 페이지 조회로 제공하고, 완료 receipt에는 정확한 집계와 조회 가능한 scope를 남긴다.
- `_release_dependencies`는 blocked dependency 항목만 페이지별로 읽는다. 중간 상태가 다시 바뀌면 실제 prepare/commit의 freshness 검사가 최종 판단한다.

이 단계만으로도 작은 scope가 unrelated graph를 읽는 비용을 줄일 수 있다. 아직 100001개를 한 번에 enqueue하는 transaction까지 해결한 것은 아니다.

### 2. durable enumeration 페이지

권고하는 최소 물리 구조는 기존 runtime event를 재사용하는 **enumeration header + immutable reference rows**다. 이름·DDL은 후속 검토 대상이며 공개 Operation/Record subtype이나 canonical domain을 추가하는 안이 아니다.

- header: parent `task_id`, source Record/snapshot 참조, 관찰한 knowledge-state version, profile/hash, stream별 정확한 총수.
- reference rows: `(task_id, stream, ordinal)` primary key와 원래 exact reference. `stream`은 derivation, semantic edge, applicability, Wiki link 및 별도로 정의한 discovery를 구분한다.
- page journal: 기존 `propagation_events`에 시작/끝 ordinal, source hash, enqueued/reused/held/historical 분류, child task/cause 연결을 남긴다. parent가 처리한 연속 범위를 복원할 수 있어야 한다.

material 변경은 기존 `k_revision_impacts`의 **불변 snapshot을 보존**하고 그 내용을 DB 안에서 reference rows로 전개한다. support maintenance는 최초 dispatch의 state fence 안에서 현재 exact reference 집합을 한 번만 snapshot한다. 후자는 effect commit 당시의 집합이었다고 표시하지 않는다. 이후 추가된 causal child는 기존 outbox/support harvest 의무로 계속 편입한다.

각 페이지는 다음 작업을 **하나의 짧은 fenced transaction**으로 처리한다.

1. 고정된 reference rows를 ordinal keyset으로 읽는다.
2. 해당 범위의 target/header만 hydrate하여 active/historical/blocked를 판별한다.
3. child task와 모든 cause를 등록하고 page checkpoint를 함께 commit한다.
4. 남은 stream이 있으면 parent를 pending으로 돌린다. 마지막 stream까지 처리한 뒤에만 parent를 완료한다.

crash가 commit 전이면 해당 페이지가 재실행되고, commit 후 ACK 전에 발생하면 저장된 checkpoint 다음부터 재개한다. 완료 guard는 header totals와 연속 처리 범위가 일치하는지 확인해야 한다. 일부 페이지의 child가 모두 끝났다는 이유만으로 root를 완료해서는 안 된다.

**주의:** `jsonb_array_elements(...) LIMIT 128`만 추가하는 것은 충분하지 않다. 큰 TOAST JSONB의 반복 해제·SRF materialization/scan은 서버에서 계속 발생할 수 있다. 먼저 DB에서 한 번 정규화한 immutable rows를 `(task_id, stream, ordinal)` index로 읽어야 반복 페이지 비용도 제한할 수 있다. 이전 snapshot JSONB는 삭제하거나 다시 쓰지 않는다.

### 3. harvest와 claim의 스캔 범위

- root JSON UUID 집합과 bound child execution의 Record 집합을 먼저 만든 뒤 `k_outbox(record_id, operation)`에 join한다. 전역 outbox 각 행에 root JSON membership을 검사하는 query 형태를 피한다.
- harvest는 한 번에 정해진 수만 등록하되 **anti-join을 유지**한다. UUID 배정 순서를 commit 순서로 보고 high-water cursor 뒤만 읽으면 늦게 commit한 이벤트를 놓칠 수 있다.
- bounded harvest 후에는 별도 `EXISTS`/count로 아직 수집하지 않은 outbox/support가 있는지 확인한다. 현재 completion fence를 유지하며, 나머지가 있으면 `running`이다.
- pending, due retry, expired/old-epoch lease의 가장 앞 후보를 index로 찾는다. 한 run당 한 유효 lease 정책은 유지한다.

## 검토할 additive index

기존 migration을 수정하지 않는다. 현재 schema 이후의 **별도 additive migration**이 필요하며 번호와 설치 대상은 확정하지 않았다. 먼저 격리 DB의 실행 계획으로 선택성을 확인한다.

- `knowledge_derivation_premises(premise_node_revision_id, record_id, ordinal)` — 기존 index는 premise 단일 열이다.
- `knowledge_edge_revisions(from_knode_revision_id, kedge_id, kedge_revision_id)`와 to 방향 대응 index.
- `knowledge_edge_applicability_events(from_knode_revision_id, event_order)`와 to 방향 대응 index. 기존 exact-pair index는 reverse lookup을 대체하지 않는다.
- `wiki_projection.knowledge_links(node_revision_id, link_id)` — 현재 unique key는 request가 앞이므로 reverse lookup에 적합하지 않다.
- `propagation_task_causes(cause_record_id, task_id)` — support harvest의 anti-join용. 기존 outbox index는 그대로 사용한다.
- `propagation_events(task_id, event_type, created_at DESC, event_id DESC)` — page/model/retry 이력을 전체 journal에서 찾지 않도록 한다.
- pending/awaiting task의 run·priority·created/id partial index와 leased/retry 조회 index는 실제 claim query를 바꾼 뒤 필요한 것만 추가한다.

초기에는 새로운 broker나 전역 dependency cache가 필요하지 않다. 위 조회 축소와 runtime reference snapshot으로도 해결되지 않는 비용을 측정한 뒤 다음 최적화를 결정한다.

## 128 / 100001 검증 계획과 한계

현재 `test_exact_chain_and_fanin_survive_empty_discovery_and_one_step_scheduling`는 초기 node와 `range(11)` 후속으로 **12개 chain**을 만든다. 이것은 128 chain 또는 100001 fanout의 실행 결과가 아니다.

1. **작은 실제 PG 회귀:** 페이지 크기를 작게 고정하고 경계를 넘는 fan-in/fanout을 만든다. 매 페이지 crash/rollback·commit 후 ACK 손실·pause/resume, inactive reference와 scope 밖 필수 대상, 마지막 페이지 전의 거짓 완료 거절을 확인한다.
2. **128 chain:** 현재 synthetic semantic helper를 확장하되 실제 provider 없이 기존 Generator/Validator receipt·canonical commit 경로를 사용한다. discovery를 끈 필수 dependency 검토부터 실행하고, 전체 128개 처리 상태·정확한 support/premise·누적 depth·원본 불변을 검사한다. 현재 2000-step test failure guard에 걸리면 실패로 보고할 뿐 runtime 성공 cap으로 바꾸지 않는다.
3. **100001 fanout transport/메모리 검사:** synthetic reference stream과 실제 runtime queue/page checkpoint를 분리해 대량 등록·페이지 복구·카운트·최대 batch 크기를 확인할 수 있다. 이를 실제 canonical K 100001개를 검증한 결과라고 부르지 않는다.
4. **100001개의 실제 canonical dependent:** 별도 opt-in stress fixture가 필요하다. 기존 one-node-per-execution helper는 매번 전체 catalog/history를 snapshot하여 seed 단계부터 제곱 비용이 발생한다. 먼저 bulk synthetic source/derivation fixture를 정상 제약 아래 준비하고, 파일/DB 크기·준비 시간·worker peak RSS·query 수를 측정한다. trigger를 끄거나 같은 dependent의 historical reference 100001개를 실제 fanout으로 세지 않는다.

모든 mandatory target을 끝까지 처리한 실제 결과가 나오기 전에는 AT01 전체를 통과로 바꾸지 않는다. 100001개 reference의 bounded enumeration 성공, 100001개 queue task의 상태 보존, 100001개 canonical target의 의미 검증 완료는 서로 다른 검증 결과다.
