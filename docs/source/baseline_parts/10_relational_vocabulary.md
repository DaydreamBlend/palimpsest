## 25. 최소 relational skeleton

SQL 세부 DDL은 migration 문서가 소유하지만 책임 경계는 다음과 같다.

### 25.1 Bibliotheca

```text
bibliotheca.data
bibliotheca.data_acquisitions

bibliotheca.information
bibliotheca.information_groundings
bibliotheca.information_supersessions
bibliotheca.information_invalidations

bibliotheca.knowledge_nodes
bibliotheca.knowledge_node_revisions
bibliotheca.knowledge_edges
bibliotheca.knowledge_edge_revisions
bibliotheca.knowledge_edge_applicability_events
bibliotheca.knowledge_groundings
bibliotheca.k_lifecycle_events

bibliotheca.wisdom
bibliotheca.wisdom_inputs
bibliotheca.wisdom_citations

bibliotheca.parchments
bibliotheca.books
bibliotheca.book_sections

bibliotheca.provenance
bibliotheca.embeddings
```

### 25.2 Scriptorium

```text
scriptorium.operation_executions
scriptorium.d2i_records

scriptorium.k_compilation_records
scriptorium.k_compilation_information_inputs
scriptorium.k_compilation_k_inputs
scriptorium.k_compilation_retrieval_hits

scriptorium.temporary_candidates
scriptorium.rejected_candidate_audit optional
scriptorium.model_calls
scriptorium.runtime_errors
scriptorium.outbox
```

Record의 핵심 FP, input refs, disposition, canonical refs, expected base revision, canonical effects와 propagation impact는 명시적 column/FK로 둔다. 유연한 model parameters와 bounded telemetry만 JSONB를 허용한다.

---

## 26. Canonical 용어

### 26.1 계층 객체

| 용어 | 의미 |
|---|---|
| `Data` | Horreum에 payload가 보존된 불변 원본과 Bibliotheca metadata |
| `Information` | one-Data/grounding-specific, validated, searchable immutable semantic snapshot |
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
| `D2I` | Data → validated Information set |
| `I2K` | exact Information set → KNode proposal |
| `N2E` | accepted KNodeRevision set → KEdge proposal |
| `K2K` | accepted KNode/KEdge revision subgraph → KNode proposal |
| `KQ2W` | accepted KGraph + Query + Context → Explanation/Recommendation Wisdom |
| `W2K` | confirmed Decision Wisdom → decision KNode |
| `W2P` | Wisdom set + composition instruction → Parchment |
| `P2B` | ordered Parchment IDs → Book |

Operation 이름은 실행되는 행위이며 DB 객체가 아니다.

### 26.4 Record와 임시 작업물

| 용어 | 의미 |
|---|---|
| `D2IRecord` | Information proposal 한 건의 FP·판정·canonical effect 원장; 같은 호출은 batch_id 공유 |
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

`Note`는 `Parchment`, `PalimLibrary`는 `Bibliotheca`로 대체한다.

---

