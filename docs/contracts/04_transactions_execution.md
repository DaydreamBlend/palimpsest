# Transaction·execution·재시도·generation

> 상태: PROPOSED IMPLEMENTATION CONTRACT · 주 승인 항목 P05.
> U08 부분 적용: R03/R04/R05/R06의 실행 cache/의무 보존, commit까지 보호되는 read-set, replacement-set 및 명시적 결정 대체 atomicity은 [해결 계약](../decisions/ARCHITECTURE_FIXES.md)의 정확한 범위에서 현재 규칙이다. 나머지 P 세부 제안/enum/DDL은 미승인이다.
> U09 부분 적용: PostgreSQL 18의 같은 database에서 Runtime Record와 canonical effects를 원자적으로 저장하며 등록 journal/retry는 [저장 계약](../decisions/STORAGE_IDENTITY.md)을 따른다. 승인된 U 범위 밖의 새 필드·enum·명칭은 관련 P의 구체 승인 전 production canonical 계약으로 사용하지 않습니다.


## 원본에서 유지하는 규칙

canonical acceptance와 Record, provenance, Candidate 처리, outbox는 atomic해야 합니다. 기존 K Revision은 expected-base CAS로 교체합니다. D2I의 단위는 logical generation이며 provider 호출마다 여러 proposal Record가 있을 수 있습니다. 근거: baseline §5, §6.6, §7.3, §9, §20.3.

## 이번에 제안하는 구현 계약

### 1. 호출과 후보의 별도 identity

`operation_executions`가 zero-output, provider 오류, retry와 호출 grouping을 소유합니다. candidate별 Record는 실행 결과에서 생성됩니다. 같은 batch의 후보들은 attempt fingerprint가 같을 수 있습니다. 따라서 Record 테이블의 attempt/content FP 전역 UNIQUE로 호출 중복을 해결하지 않습니다.

작업 claim은 실행용 idempotency/lease key로, canonical semantic identity 경쟁은 authoritative object identity와 current pointer CAS로 보호합니다. 정확한 unique/index DDL은 approved schema가 소유합니다. failed/pending/needs_human은 completed cache entry가 아닙니다.

### 2. 입력 snapshot과 short commit

LLM 호출 전 exact inputs, applicability basis, evidence state, policy와 authority snapshot을 고정합니다. 네트워크 호출 중 장기 DB transaction/lock을 잡지 않습니다. commit에서는 target expected base뿐 아니라 승인에 중요한 read-set state token의 유효성도 확인합니다.

순서 제안: validate read-set → lock/compare target base → insert immutable revision 또는 validated effect → update current projection → append provenance/support receipts → terminal Record → candidate cleanup/audit → outbox. 하나라도 실패하면 canonical effect가 부분 반영되어서는 안 됩니다.

다른 worker가 새 base를 승인했다면 후보를 새 base 기준으로 재검증합니다. semantic content가 현재 값과 같아진 경우 reused/no_material_delta로 종료할 수 있습니다. 이미 superseded/invalidated된 입력으로 새 accepted K를 만들지 않습니다.

### 3. Outbox·lease·fan-in

producer commit과 outbox insert는 원자적입니다. consumer는 event redelivery를 허용하고 처리 효과를 deduplicate합니다. lease expiry, heartbeat, crash recovery, ACK-before/after-commit failpoint를 테스트합니다. provider 비용/호출 횟수의 exactly-once는 보장 범위가 아닙니다.

여러 root가 같은 의미 작업을 요청하면 한 실행을 공유할 수 있지만 모든 incoming cause/obligation을 보존합니다. root_record_id/parent_record_id는 대표 인과 연결일 수 있으므로 fan-in 연결은 typed runtime rows로 추가 제안합니다. 새 root를 만드는 것으로 failed obligation을 잊어서는 안 됩니다.

### 4. Split/merge publication barrier

한 I의 split replacement set 전체가 validation을 통과해야 old I를 retire합니다. 여러 I의 merge도 입력 그룹을 완전하게 확정합니다. replacement set activation과 supersession rows는 같은 commit입니다. staged replacement는 active RAG에 섞지 않습니다.

모든 D2I 결과를 하나의 거대한 transaction으로 묶으라는 뜻은 아닙니다. 서로 독립적인 extraction은 개별 commit할 수 있으며, **같은 교체 의미 단위**에 속하는 경우에만 group publication barrier를 적용합니다. 실패 시 old I를 usable로 유지하거나 명시적 invalidation 정책을 따릅니다. generation 증가만으로 이전 generation 전체를 폐기하지 않습니다.

### 5. History/ordering

current pointer/lifecycle/applicability/support projection을 재구성할 수 있게 commit sequence 또는 동등한 ordering receipt를 정의합니다. wall-clock created_at 동률만으로 last-writer를 결정하지 않습니다. history read와 current read를 분리하며 generic object_id JSON 안에 exact FK 관계를 숨기지 않습니다.

### 6. 완료 조건

AT28–36이 실제 PostgreSQL transaction/복수 worker로 실행되어야 합니다. SQLite나 mock DB 통과만으로 경쟁 조건 검증을 대체하지 않습니다. 최초 DB major는 U09의 18이며 실제 minor/pgvector profile, driver/migration runner와 DDL 적용 결과는 별도로 기록합니다.

## U09 — 잠정 판정과 영속 반영

후보 본문·잠정 검증은 Compiler Runtime에서 준비하고 canonical effects/provenance/current support + terminal Record + candidate cleanup + outbox를 한 PostgreSQL transaction에 저장한다. 확정 후에도 판정·reason·exact refs·FP의 Runtime Record는 영속 보존한다. Record를 Canonical Store로 이동·삭제하거나 compiler_runtime를 TEMP/UNLOGGED 저장소로 구현하지 않는다. 기술 실패/needs_human은 rejected가 아니며 commit rollback 시 효과와 cleanup 모두 취소한다.

Data 등록의 새 duplicate request와 동일 성공 retry는 별도 결과다. Data/acquisition/committed journal은 같은 commit이며 파일 publish와 DB 사이 복구는 관리 staging/journal로 수행한다. [T02 SQL 초안](../schema/T02_STORAGE_SCHEMA.md)은 이 최소 경계를 제안한 미적용 SQL이며 general Compiler Record/effect enum의 전체 동결이 아니다.
