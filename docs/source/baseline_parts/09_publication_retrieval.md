## 23. P — Parchment와 B — Book

### 23.1 Parchment

Parchment는 하나 이상의 Wisdom을 사람, LLM, deterministic script 또는 그 조합이 구성·편집한 독립 문서다.

```text
Parchment
- parchment_id
- title
- body
- input_wisdom_ids
- direct K revision refs / Information IDs optional
- citations
- actor/tool/model/script provenance
- supersedes_parchment_id optional
- created_at
```

필드 각주:

| 필드 | 설명 |
|---|---|
| `parchment_id` | 하나의 완성된 immutable 문서 artifact ID다. |
| `title` | 사람이 문서를 식별할 수 있는 제목이다. identity 자체로 사용하지 않는다. |
| `body` | 여러 Wisdom과 인용을 구성해 만든 최종 문서 내용이다. |
| `input_wisdom_ids` | 문서 구성에 실제 사용한 exact immutable Wisdom IDs다. |
| `direct K revision refs / Information IDs` | Wisdom을 거치지 않고 문서가 직접 인용·사용한 exact K Revision 또는 Information 참조다. 필요하지 않으면 비어 있다. |
| `citations` | body의 구절을 W/K/I/Data grounding으로 연결하는 인용 mapping이다. |
| `actor/tool/model/script provenance` | 사람, LLM, deterministic script 중 누가 어떤 방식으로 문서를 구성·편집했는지 재현하는 provenance 묶음이다. |
| `supersedes_parchment_id` | 이 문서가 대체하는 이전 Parchment ID다. 이전 Parchment는 수정·삭제하지 않는다. |
| `created_at` | 이 immutable Parchment가 생성된 시각이다. |

Parchment는 그 자체가 immutable artifact다. `ParchmentRevision`을 두지 않는다. 편집하면 새 Parchment를 만들고 `supersedes_parchment_id`로 연결한다.

### 23.2 Book

Book은 Parchment를 순서와 구조에 따라 묶은 immutable publication artifact다.

```text
Book
- book_id
- title
- description
- ordered sections
- exact parchment_ids
- supersedes_book_id optional
- created_at
```

필드 각주:

| 필드 | 설명 |
|---|---|
| `book_id` | 하나의 immutable publication 구성을 식별하는 canonical ID다. |
| `title` | Book의 표시 제목이다. |
| `description` | Book의 목적, 독자 또는 포함 범위를 설명한다. |
| `ordered sections` | section 제목, 순서와 포함 Parchment 배치를 정의하는 구조다. |
| `exact parchment_ids` | Book에 실제 포함된 immutable Parchment IDs다. current 문서를 암묵적으로 따라가지 않는다. |
| `supersedes_book_id` | 새 구성이 대체하는 이전 Book ID다. 이전 Book도 역사적 publication으로 남긴다. |
| `created_at` | 이 Book 구성이 생성·발행된 시각이다. |

`BookRevision`을 두지 않는다. 구성이 바뀌면 새 Book을 만든다.

---

## 24. RAG와 projection

### 24.1 기본 검색 대상

필수 RAG corpus:

1. usable validated Information
2. current usable accepted KNodeRevision
3. current-applicable usable accepted KEdgeRevision

Wisdom은 KGraph의 대체 검색 corpus가 아니다. decision trace, Parchment composition, history 탐색을 위해 별도 W 검색 projection을 둘 수 있다.

### 24.2 KEdge projection

KEdge embedding input은 predicate 한 단어만 사용하지 않는다.

```text
from-node semantic projection
+ predicate
+ to-node semantic projection
+ edge qualifier projection
```

Retrieval 결과는 exact KEdgeRevision과 endpoint revision IDs를 반환한다.

### 24.3 Projection 원칙

- embedding은 canonical truth가 아니다.
- model/profile/dimensions/normalization/input projection version을 기록한다.
- 새 Information 또는 새 K Revision은 새 projection을 만든다.
- stale-endpoint KEdgeRevision은 history/revalidation 검색에는 사용할 수 있지만 기본 current KGraph RAG에서는 제외한다.
- candidate/rejected embedding은 canonical corpus에 넣지 않는다.
- temporary candidate similarity index는 terminal cleanup 대상이다.

---

