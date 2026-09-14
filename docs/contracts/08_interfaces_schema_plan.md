# Schema·port·effect registry의 확정 순서

> 상태: PROPOSED IMPLEMENTATION CONTRACT · 주 승인 항목 P06.
> U08 부분 적용: R02/R05/R06/R09의 공개 ref 값·commit 경계·한정된 W2K 부수 효과·retrieval 두 축은 [해결 계약](../decisions/ARCHITECTURE_FIXES.md)의 정확한 범위에서 현재 규칙이다. 나머지 P 세부 제안/enum/DDL은 미승인이다.
> U09 부분 적용: PostgreSQL 18/pgvector, 신규 ID, 관리 등록과 영속 Runtime Record 경계는 [저장 계약](../decisions/STORAGE_IDENTITY.md)을 따른다. 승인된 U 범위 밖의 새 필드·enum·명칭은 관련 P의 구체 승인 전 production canonical 계약으로 사용하지 않습니다.


## 원본에서 유지하는 규칙

I2K/K2K는 Node 계열, N2E는 Edge 계열, W2K는 authority-confirmed decision을 처리합니다. Record, exact FK inputs, immutable revisions, separate projections를 유지합니다. 정보 기반 K 재검증 public subtype은 원본이 명시적으로 미정입니다. 근거: baseline §6.6, §8.4, §9, §25, §29–30.

## 확정 전 이름의 의미

아래 포트/command 이름은 권장 application interface이며 새로운 canonical domain 이름을 승인한 것이 아닙니다. 기존 코드가 있으면 그 언어·관례에 맞춰 어댑터로 구현합니다. endpoint URL, JSON Schema dialect, enum 추가도 T01에서 결정합니다.

### Port 후보

`ArtifactStore`: stage/read/verify/publish; `CanonicalRepository`: exact read/current read/atomic commit; `CompilationExecutor`: claim execution/record provider outcome/fan-out proposals; `Generator`와 `Validator`: structured input/output만 교환; `RetrievalService`: candidate hits+snapshot; `DependencyRepository`: exact consumer enumeration+receipt; `PropagationScheduler`: enqueue/lease/coalesce/pause/resume/receipt; `AuthorityService`: confirmation 검증; `PublicationService`: immutable composition.

runtime은 직접 임의 SQL로 canonical state를 덮어쓰지 않고 승인된 commit boundary를 호출합니다. provider 코드는 canonical repository에 write 권한을 갖지 않습니다. ingestion/retrieval service가 tool output 안의 instruction을 실행하지 않습니다.

### Command 후보

`RegisterData`, `StartD2ICompilation`, `PublishInformationReplacement`, `CommitKnowledgeProposal`, `RevalidateEdgeApplicability`, `ConfirmDecision`, `ExplainDecision`, `ComposeParchment`, `PublishBook`, `PausePropagation`, `ResumePropagation`.

모든 consequential command는 actor/idempotency/correlation를 검증하고 canonical effects와 정확한 result refs를 반환합니다. `StartD2ICompilation`은 generation/reason을 명시합니다. `ConfirmDecision`은 same event retry와 새 사건을 구분합니다. 위 naming을 기존 public API에 무조건 강제하지 않습니다.

### State/effect registry

schema 동결 전에 다음 질문을 결정하십시오.

- 정보 기반 K 재검증 subtype의 공개 이름과 candidate 없는 effect 표현 방식은 무엇입니까?
- approved applicability loss/lifecycle effect를 어떤 disposition으로 보존합니까?
- N2E relation outcome과 proposal rejection의 차이를 어떻게 나타냅니까?
- edge predicate 변경은 old relation effect + new logical edge로 atomic하게 표현됩니까?
- runtime pause/blocked/retry 상태와 proposal disposition은 별도입니까?
- latest event precedence와 current/history read 계약은 무엇입니까?

`propagation_impact`는 validated effect diff에서 계산하며 임의 free-text enum을 허용하지 않습니다. 판정·효과·전파를 하나의 succeeded bool로 합치지 않습니다.

### Schema 산출물 요구사항

approved field/type registry, versioned JSON schemas, migration files, constraint/index rationale, status transition matrix, forward/backward migration policy, representative positive/negative fixtures를 함께 만드십시오. FK 대상과 composite consistency(예: revision이 해당 logical object 소속인지)를 명시합니다. 모든 JSON metadata가 관계를 대체하지 않게 합니다.

U09의 [T02 schema 초안](../schema/T02_STORAGE_SCHEMA.md)은 Data SHA-256 PK, acquisition/request UUIDv7, typed FK와 상태 전이를 PostgreSQL 18로 표현한다. 실제 DB 적용·앱 integration 결과가 아니며 driver/migration runner·DB 실행 위치는 아직 미정이다. I/K/W/P/B·general Compiler Record·embedding 테이블은 해당 단계에서 추가한다. 관리 등록은 새 duplicate request를 거부하되 같은 성공 request retry를 재생하고, 반영은 canonical effects와 영속 Runtime Record/cleanup/outbox를 한 transaction으로 묶는다. 이 선택으로 위 미정 public subtype/effect enum을 임의 확정하지 않는다.

### Evidence lineage 계약 — P07 제안

DataAcquisition과 별도로 외부 work/study linkage 또는 derived_artifact_origin metadata를 사용할 수 있습니다. 새 Source 계층이 아닙니다. 동일 실험/내부 생성 lineage는 leaf support 중복 계산에서 제외합니다. independent status unknown을 1개의 독립 실험으로 강제 변환하지 않습니다. 내부 publication을 D로 다시 가져와도 새 독립 evidence나 authority가 생기지 않습니다.


### 현재 확정된 interface/parser/name 경계

U01–U03은 이 P06/P07 내부 schema 제안의 승인 여부와 독립적으로 적용된다. 현재 user adapter는 CLI, PDF parser는 MinerU, 세 구성요소명은 Artifact Store/Canonical Store/Compiler Runtime이다. `ArtifactStore` 같은 port type과 `artifact_store` 모듈은 같은 역할의 naming conventions이며 새 domain 계층이 아니다.

CLI 명령 문법은 [CLI 계약](../interfaces/CLI_CONTRACT.md), PDF parsing 구현 경계는 [MinerU adapter](../interfaces/MINERU_ADAPTER.md)를 참고한다. Generator/Validator model provider나 non-PDF parser까지 MinerU로 통일하는 결정은 아니다.
