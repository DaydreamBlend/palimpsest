## 25. 최소 relational skeleton

SQL 세부 DDL은 단계별 migration이 소유하며 T02의 현재 표현은 docs/schema/T02_storage_draft.sql 검토 초안이다. U09는 최초 PostgreSQL 18 + pgvector, Data ID=원본 bytes SHA-256, 기타 신규 opaque ID=UUIDv7를 확정한다. 과거 ID나 fingerprint/version/commit ordering을 재작성하지 않는다. 책임 경계는 다음과 같다.

### 25.1 Canonical Store

```text
canonical_store.data
canonical_store.data_acquisitions

canonical_store.information
canonical_store.information_groundings
canonical_store.information_supersessions
canonical_store.information_invalidations

canonical_store.knowledge_nodes
canonical_store.knowledge_node_revisions
canonical_store.knowledge_edges
canonical_store.knowledge_edge_revisions
canonical_store.knowledge_edge_applicability_events
canonical_store.knowledge_groundings
canonical_store.k_lifecycle_events

canonical_store.wisdom
canonical_store.wisdom_inputs
canonical_store.wisdom_citations

canonical_store.parchments
canonical_store.books
canonical_store.book_sections

canonical_store.provenance
canonical_store.embeddings
```

### 25.2 Compiler Runtime

```text
compiler_runtime.data_import_requests
compiler_runtime.operation_executions
compiler_runtime.d2i_records

compiler_runtime.k_compilation_records
compiler_runtime.k_compilation_information_inputs
compiler_runtime.k_compilation_k_inputs
compiler_runtime.k_compilation_retrieval_hits

compiler_runtime.temporary_candidates
compiler_runtime.rejected_candidate_audit optional
compiler_runtime.model_calls
compiler_runtime.runtime_errors
compiler_runtime.outbox
```

U11 source I의 `unit_type`/`semantic_type=null`, source payload·coverage·profile은 additive migration으로 표현하며 기존 semantic I/Record와 설치된 migration을 재작성하지 않는다. 이 skeleton은 물리 schema의 적용 완료 기록이 아니다.

Record의 핵심 FP, input refs, disposition, canonical refs, expected base revision, canonical effects와 propagation impact는 명시적 column/FK로 둔다. 유연한 model parameters와 bounded telemetry만 JSONB를 허용한다.

---

## 26. Canonical 용어

### 26.1 계층 객체

| 용어 | 의미 |
|---|---|
| `Data` | Artifact Store에 payload가 보존된 불변 원본과 Canonical Store metadata |
| `Information` | one-Data/grounding-specific immutable source snapshot; 구조·무결성 acceptance와 의미 승인을 구분 |
| `KNode` | accepted Knowledge graph의 typed logical node; decision은 reported/authority-confirmed event origin을 구분 |
| `KEdge` | accepted KNode 사이의 typed semantic relation |
| `Wisdom` | Query·Context·KGraph에 종속된 immutable explanation/recommendation/decision |
| `Parchment` | Wisdom을 구성한 immutable 독립 문서 |
| `Book` | ordered immutable Parchment의 publication 집합 |

### 26.2 Revision과 Information 전이

| 용어 | 의미 |
|---|---|
| `InformationSupersession` | 새 Information이 기존 Information을 대체하는 append-only 다대다 관계 |
| `InformationInvalidation` | 대체 객체 없이 기존 Information을 사용 불가로 판정한 append-only 기록 |
| `KNodeRevision` | KNode의 immutable semantic snapshot |
| `KEdgeRevision` | exact endpoint revisions를 가진 KEdge의 immutable snapshot |

Information, Wisdom, Parchment, Book은 그 자체가 immutable이므로 별도 Revision wrapper를 두지 않는다.

### 26.3 Operation

| Operation | 입력 → 출력 |
|---|---|
| `D2I` | Data → 결정적 원문 조립·구조 검사 → source Information set; application LLM 호출 없음 |
| `I2K` | exact Information set → KNode proposal |
| `N2E` | accepted KNodeRevision set → KEdge proposal |
| `K2K` | accepted KNode/KEdge revision subgraph → KNode proposal |
| `K2W` | accepted KGraph + Query + Context → Explanation/Recommendation Wisdom |
| `W2K` | confirmed Decision Wisdom → decision KNode와 명시적 supersedes의 atomic effect |
| `W2P` | Wisdom set + composition instruction → Parchment |
| `P2B` | ordered Parchment IDs → Book |

Operation 이름은 실행되는 행위이며 DB 객체가 아니다.

### 26.4 Record와 임시 작업물

| 용어 | 의미 |
|---|---|
| `D2IRecord` | source-unit 처리 한 건의 FP·구조 검사·canonical effect 원장; 같은 처리의 batch_id 공유. 과거 semantic profile 이력 보존 |
| `KCompilationRecord` | K 생성/Revision 제안의 FP·입력·판정·canonical effect 원장 |
| `I2KRecord` | record_type=i2k인 KCompilationRecord |
| `N2ERecord` | record_type=n2e인 KCompilationRecord |
| `K2KRecord` | record_type=k2k인 KCompilationRecord |
| `W2KRecord` | record_type=w2k인 KCompilationRecord |
| `TemporaryCandidate` | pending review에만 존재하는 비canonical payload |

### 26.5 사용하지 않는 canonical 이름

다음은 새 모델의 canonical 이름으로 사용하지 않는다.

```text
Source layer
S2D
direct S2I
D2IRun
D2IRunItem
D2IBatch
D2IOutput
I2KRun
I2KRunItem
N2ERun
K2KRun
KReviewRun
InformationRevision
InformationCandidate domain object
KNodeCandidate domain object
KEdgeCandidate domain object
KRejectionRecord
DecisionReplay Wisdom kind
Note
PalimLibrary
```

`Note`는 `Parchment`, `PalimLibrary`는 `Canonical Store`로 대체한다.

---

