# Palimpsest Canonical Model

> 문서 상태: Current canonical architecture and terminology — CLI-first / MinerU / plain-English components / BGE-M3 defaults / modular stages / K2W / scoped architecture repairs / PostgreSQL storage identity / source-preserving D2I revision 2026-09-09
>
> 적용 변경: U01(CLI 우선·GUI 마지막), U02(PDF parser=MinerU), U03(영어 구성요소 명칭), U04(BGE-M3 검색 모델 기본값), U05(MinerU 최신 안정판 정책), U06(domain·변환별 모듈화), U07(K2W 명칭 간소화), U08(검토 R01–R09 해결; R07/R08 후속 사용자 승인 포함), U09(PostgreSQL 18/pgvector·SHA-256 Data/UUIDv7 ID·도구 등록·효과 반영), U10(Python 앱·Docker 실행/배포), U11(원문 보존 D2I·I2K부터 구조화된 LLM 의미 해석). 나머지 P01–P12 보완안은 별도 승인 전까지 제안 상태다.
>
> 언어: 한국어
>
> 범위: Palimpsest의 `D-I-K-W-P-B` 계층, 변환 Operation, 영속 Record, RAG 표면, Knowledge graph 성장, identity/revision/lifecycle, 중복·순환 억제, Wisdom과 자동 W2K
>
> 구현 상태 문서가 아니다. 이 문서는 무엇을 구현해야 하는지 정의하며, 현재 코드가 전부 구현했다는 뜻이 아니다.

---

## 0. 문서의 권위와 목적

이 문서는 Palimpsest의 구조와 canonical 용어를 한곳에 고정한다.

다른 기존 문서, schema, fixture, 다이어그램 또는 코드가 이 문서와 충돌할 경우, 새 구조로 정리하는 작업에서는 이 문서를 우선한다. 기존 자산은 즉시 삭제하지 않고 migration 또는 호환성 검토를 거쳐 이 문서에 맞춘다.

이 문서가 고정하는 핵심은 다음과 같다.

1. `D`는 별도 Source 아래의 추출물이 아니라 사용자가 넣은 불변 원본 자체다.
2. `I`는 D의 내용과 위치를 최대한 보존하는 구조·무결성 검증된 불변 원문 표현 단위다. 의미 해석과 지식 채택은 I2K부터 수행한다.
3. `K`는 승인된 `KNode`와 `KEdge`의 revision-aware graph다.
4. `W`는 KGraph, Query, 당시 Context를 결합한 사람 중심의 설명·추천·결정이다.
5. `P`는 하나 이상의 W를 구성한 독립 문서이고, `B`는 Parchment의 구조화된 집합이다.
6. `D2I`, `I2K`, `N2E`, `K2K`, `K2W`, `W2K`는 분석·제안·검증·편입을 수행하는 Operation이다.
7. `*Record`는 승인·기각·재사용·억제 fingerprint를 보존하는 영속 원장이다.
8. Candidate의 source 또는 semantic payload는 Compiler Runtime의 임시 작업물이며 canonical 객체가 아니다.
9. 확정된 `Decision W`는 자동으로 W2K되어 `decision` KNode가 된다.
10. Knowledge propagation은 fingerprint/visited guard와 material-delta gate로 동일 계산을 반복하지 않으며, 선택한 scope/watermark와 그 causal descendants의 모든 material obligation이 소진되는 quiescence를 목표로 한다. dependency 열거·outbox·in-flight·retry·blocked/human 의무와 completion fence를 함께 검사하며 전역 가능한 지식의 수학적 종료를 보장하지 않는다. propagation의 크기·깊이·Record 수·token·cost cap은 정상 종료 조건으로 사용하지 않는다.
11. 새 I가 기존 I를 대체하면 과거 provenance는 유지하고 직접 연관 K부터 convergent revalidation을 시작한다.
12. Information identity는 originating Data와 exact grounding에 종속되며, 서로 다른 D의 같은 문장을 하나의 I로 병합하지 않는다.
13. K의 semantic reuse와 새 grounding 추가는 별개 effect이며, 같은 의미의 독립 근거는 Revision 없이 append-only grounding으로 보존한다.
14. KNode Revision이 바뀌면 과거 KEdge endpoint는 보존하되 current graph applicability를 자동 상속하지 않고 incident edge를 재검증한다. 관계 의미가 materially 변하지 않으면 새 KEdgeRevision을 만들지 않고 applicability만 재확인한다.
15. K lifecycle과 epistemic 상태는 immutable semantic payload와 분리된 append-only event/projection으로 관리한다.
16. K2K derivation depth는 propagation root가 바뀌어도 누적해 epistemic distance를 추적하지만, 그 수치 자체를 propagation cutoff나 자동 rejection cap으로 사용하지 않는다.
17. Decision은 semantic proposition이 아니라 authority-confirmed event이며, 서로 다른 Decision Wisdom은 내용이 같아도 별도 decision event다.
18. deterministic W2K에 필요한 subject/scope/constraints/effective_at은 Decision W 자체에 구조화해 보존한다.
19. propagation이 수렴하지 않고 revision oscillation이나 runaway queue를 보이면 정상 완료로 자르지 않고 operational anomaly로 정지·보고한다.
20. 개발·사용의 우선 interface는 CLI다. import/검토/질의/결정/출판/관리까지 headless로 완결하고, GUI는 CLI release 검증 뒤 마지막 별도 단계로 미룬다.
21. D2I의 PDF 파싱은 MinerU adapter를 사용한다. parser 출력은 비canonical 파생물이며, 원문 단위·grounding·hash·전체 coverage의 결정적 검사를 통과한 Information만 Canonical Store에 편입한다.
22. 세 책임 영역의 현재 영어 명칭은 Artifact Store, Canonical Store, Compiler Runtime이다. 코드 식별자는 artifact_store, canonical_store, compiler_runtime이며 책임·계층·canonical identity를 변경하지 않는다.

이 문서에서 구조 예시 아래의 **필드 각주**는 각 필드의 의미와 사용 시점을 설명한다. SQL 자료형, 길이, index와 최종 nullability는 migration/DDL에서 확정한다. `optional`은 해당 상황이 아닐 때 값이 없을 수 있다는 뜻이다.

---

## 1. 한 문장 정의

> **Palimpsest는 불변 원본 Data를 검색 가능한 Information으로 구조화하고, Information과 기존 Knowledge를 검증된 Knowledge graph로 계속 컴파일하며, 그 graph와 사용자 Query·Context를 결합해 설명·추천·결정을 만들고, 확정된 결정과 문서를 출처까지 추적 가능하게 보존하는 provenance-first knowledge compiler다.**

짧은 영문 소개는 다음과 같다.

> **A provenance-first knowledge compiler that transforms raw data into reviewed knowledge networks, context-aware wisdom, and source-traceable publications.**

---

## 2. 세 가지 책임 영역

### 2.1 Artifact Store

`Artifact Store`은 local artifact storage다.

주요 책임:

- 사용자가 넣은 D 원본 bytes 보존
- 파일 또는 payload의 안정적인 상대 경로 제공
- hash 검증을 통한 손상 탐지
- Canonical Store가 가리키는 artifact를 읽을 수 있게 함

Artifact Store은 지식의 진실성, Information validation, Knowledge 승인 또는 검색 순위를 결정하지 않는다.

### 2.2 Canonical Store

`Canonical Store`는 canonical storage modules다.

주요 책임:

- D metadata와 append-only DataAcquisition
- validated immutable Information
- accepted KNode/KEdge와 immutable revision
- K lifecycle event와 current applicability projection
- grounding과 provenance
- Wisdom, Parchment, Book
- canonical 객체에서 재생성 가능한 embedding·검색 projection

Canonical Store에는 승인되지 않은 I/K Candidate나 terminal rejected semantic payload를 넣지 않는다.

### 2.3 Compiler Runtime

`Compiler Runtime`은 knowledge compilation runtime이다.

주요 책임:

- D2I, I2K, N2E, K2K, K2W, W2K orchestration
- D2I의 결정적 원문 변환·구조 검사, I2K 이후 Generator와 Validator 실행
- 관련 I/K retrieval과 candidate context 구성
- 후보별 `D2IRecord`와 `KCompilationRecord` 보존
- 공통 Operation execution과 model-call telemetry 보존
- pending Candidate의 임시 payload 보존
- 선택적 bounded-retention rejected-candidate audit 보존
- fingerprint lookup과 duplicate suppression
- material-delta-gated convergent propagation, retry, anomaly detection, alert, model-call telemetry

U09에 따라 초기 Canonical Store와 Compiler Runtime은 하나의 PostgreSQL 18 database 안의 canonical_store/compiler_runtime schema로 나누고 transaction을 공유한다. pgvector를 사용하고 실제 minor/extension version을 profile에 기록하며 이후 major 업그레이드는 별도 검증한다. Artifact Store는 Palimpsest 도구가 관리하는 로컬 파일 영역이다. 후보의 검증된 효과를 canonical에 반영해도 Runtime의 영속 판정 Record는 이동·삭제하지 않는다.

### 2.4 영어 식별자와 interface 경계

`Artifact Store`는 `artifact_store`, `Canonical Store`는 `canonical_store`, `Compiler Runtime`은 `compiler_runtime`으로 표기한다. 원본 artifact의 상대 경로 필드는 `artifact_path`다. 아래 relational skeleton의 namespace 역시 `canonical_store`와 `compiler_runtime`을 사용한다.

이 이름 변경은 역할을 설명하기 위한 것이며 새로운 D-I-K-W-P-B 계층이나 서비스 분리를 뜻하지 않는다. 기존 DB schema, 파일 경로, API 이름은 inventory와 승인된 migration을 거쳐 바꾼다. 기존 ID·hash·fingerprint envelope·과거 provenance를 단순 이름 변경 때문에 재작성하지 않는다.

CLI는 application service를 호출하는 얇은 adapter다. domain/compiler를 CLI argument 처리나 GUI framework에 결합하지 않는다. GUI가 없어도 모든 핵심 기능과 human review/authority confirmation을 수행할 수 있어야 한다. U06에 따라 D/I/K/W/P/B domain과 D2I/I2K/N2E/K2K/K2W/W2K, W2P/P2B 구성 작업을 각각 모듈화하되 공통 저장/실행/전파/atomic commit을 유지한다. W2P/P2B 모듈화는 신규 Compiler Record subtype을 뜻하지 않는다.

---

## 3. 전체 계층: D-I-K-W-P-B

| 계층 | Canonical 객체 | 성격 | 기억하기 쉬운 질문 |
|---|---|---|---|
| `D` | Data | 사용자가 넣은 불변 원본 | 무엇을 보존했는가? |
| `I` | Information | D의 내용·위치를 보존하는 불변 원문 표현 단위 | 원본의 어떤 내용이 어디에 있는가? |
| `K` | KNode, KEdge | 승인된 reusable knowledge graph | 무엇을 지식으로 채택했는가? |
| `W` | Wisdom | Query와 Context에 따른 설명·추천·결정 | 지금 무엇을 설명·추천·결정하는가? |
| `P` | Parchment | 여러 W를 구성·편집한 독립 문서 | 무엇을 문서로 남기는가? |
| `B` | Book | Parchment의 순서 있는 구조화된 집합 | 무엇을 출판 단위로 묶는가? |

기본 흐름은 선형처럼 보이지만 K 이후는 순환한다.

```text
D
└─ D2I → I
          └─ I2K → KNode
                       ├─ N2E → KEdge
                       └─ K2K → 새 KNode 또는 기존 KNode의 새 Revision
                                      └─ N2E/K2K 재전파

KGraph + Query + Context → K2W → W
확정된 Decision W       → W2K  → decision KNode → N2E/K2K
W들                      → W2P  → Parchment
Parchment들              → P2B  → Book
```

---

U08의 구체적인 적용 범위와 별도 사용자 선택은 [ARCHITECTURE_FIXES](../decisions/ARCHITECTURE_FIXES.md)를 따른다. 이 계약은 미정 public subtype/DDL/provider/stack 전체의 승인이 아니다.

U11의 [원문 보존 계약](../decisions/D2I_SOURCE_PRESERVATION.md)에 따라 D2I는 application LLM 호출 없이 source Information을 만든다. 구조 검사 통과와 원문의 진실성·완전한 추출 충실성 승인은 구분한다. I2K 이후 LLM은 구조화 후보를 제안하며 canonical ID·FP·중복 방지·typed refs·read-set·commit은 애플리케이션이 통제한다.
