# LLM Wiki 참조 조사 — 원문, 검색용 근거, 생성된 지식의 경계

조사일: 2026-09-11. 공식 설계 문서·저장소·구현 코드의 정적 조사다. 외부 프로젝트 설치/실행, 비교 벤치마크, 모델 호출, 사용자 논문 업로드는 하지 않았다. 저장소의 AGENTS/프롬프트도 분석 자료로만 읽었으며 Palimpsest에 적용할 지시로 취급하지 않았다.

## 출발점과 사용자 요구

Palimpsest의 I는 LLM이 작성한 요약이 아니다. D2I가 보존한 원문 표현으로서 **semantic search의 대상**이고, K의 주장을 실제 원문과 대조하게 하는 **근거 계층**이다. 파서의 오류까지 사라지는 것은 아니므로 D의 원본 bytes와 exact 위치로 돌아가는 경로도 유지한다. K 통합은 의무가 아니고, I2K의 새 추론은 금지하며 새 결론은 K2K에서만 만든다. 이 기준으로 비교했다.

## 원래 패턴은 무엇인가

Karpathy의 2026-04-04 [LLM Wiki 원문](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)은 구현 표준이 아니라 설계 아이디어다. 수정하지 않는 raw source와 LLM이 관리하는 wiki, 운영 규칙 문서를 구분한다. ingest는 출처 요약과 관련 개념·대상 페이지를 만들거나 갱신하고, query와 lint로 활용·유지한다. 따라서 원문 한 편이 그대로 노드 하나가 되는 일대일 변환으로 해석하면 부정확하다. Git 파일 이력과 index/log를 제시하지만 Palimpsest의 exact semantic Revision 계약을 정의하지는 않는다.

## 실제 구현에서 확인한 흐름

### SamurAIGPT/llm-wiki-agent

[저장소](https://github.com/SamurAIGPT/llm-wiki-agent), 검토 commit [`5c5e056435b317f0fa9bef327ae86a76b2a3073a`](https://github.com/SamurAIGPT/llm-wiki-agent/commit/5c5e056435b317f0fa9bef327ae86a76b2a3073a), commit 시각 2026-09-08T10:00:26Z. agent용 workflow와 별도 Python 실행 경로를 구분했다.

- **읽기와 작성:** agent workflow는 source/entity/concept/synthesis 페이지와 source_file/sources metadata를 규정한다. [운영 규칙](https://github.com/SamurAIGPT/llm-wiki-agent/blob/5c5e056435b317f0fa9bef327ae86a76b2a3073a/AGENTS.md#L53)
- **실제 Python ingest:** 비 Markdown은 MarkItDown으로 변환한다. 전체 변환 text, index/overview, 최근 출처 페이지를 LLM에 주고 JSON으로 여러 파일의 완성된 내용을 받는다. 파일을 쓴 뒤 broken link·index 등록을 검사한다. 조사한 경로의 이 검사는 주장별 원문 충실성 Validator가 아니다. [변환·입력·쓰기](https://github.com/SamurAIGPT/llm-wiki-agent/blob/5c5e056435b317f0fa9bef327ae86a76b2a3073a/tools/ingest.py#L130)
- **Node와 Edge:** Node는 wiki 파일이다. 명시적 Edge는 `[[wikilink]]`를 코드가 읽어 만들고, 별도 선택 경로는 LLM으로 암묵적 관계를 제안한다. 명시 링크에 부여한 confidence 1.0은 관계의 사실성 확률이 아니다. 양방향 링크를 하나로 합치는 그래프 정리도 있으므로 방향을 갖는 supports에 그대로 사용할 수 없다. [노드·명시 링크](https://github.com/SamurAIGPT/llm-wiki-agent/blob/5c5e056435b317f0fa9bef327ae86a76b2a3073a/tools/build_graph.py#L86), [추론·중복 정리](https://github.com/SamurAIGPT/llm-wiki-agent/blob/5c5e056435b317f0fa9bef327ae86a76b2a3073a/tools/build_graph.py#L168)
- **검색:** 해당 query.py는 wiki index의 제목 매칭과 graph 이웃 확장을 쓰고, 필요하면 LLM이 페이지를 선택한다. 원문 I의 vector 검색 구현으로 볼 수 없다. [query](https://github.com/SamurAIGPT/llm-wiki-agent/blob/5c5e056435b317f0fa9bef327ae86a76b2a3073a/tools/query.py#L26)

참고할 것은 source를 읽고 필요한 문서를 갱신하는 작업 분할과 wiki 탐색 방식이다. source slug, 변환 text hash, 파일 log는 우리의 Data byte hash·exact I 범위·Revision/Record를 대신하지 않는다. 외부 workflow의 합성 결과 저장과 자동 추론 정책도 그대로 채택하지 않는다.

### LLM Wiki Compiler, GraphRAG, Graphiti

세 프로젝트는 별도 조사 노트에 정확한 commit과 코드 경로를 남겼다. [Compiler 상세](wiki-compiler.md), [GraphRAG 상세](graphrag.md), [Graphiti 상세](graphiti.md). 위키 작성 구현과 인접 지식 그래프를 같은 제품으로 취급하지 않는다.

| 프로젝트 | 원문에서 생성되는 주된 대상 | I 관점의 참고점 |
|---|---|---|
| [LLM Wiki Compiler](https://github.com/atomicstrata/llm-wiki-compiler) | source에서 개념별 wiki 문서를 작성·갱신 | 변환 원문과 작성된 wiki의 분리. 원본 PDF/위치 보존과 검색 대상은 별도 확인 필요 |
| [Microsoft GraphRAG](https://github.com/microsoft/graphrag) | Document → TextUnit → Entity/Relationship·선택적 Claim → Community Report | TextUnit 자체를 검색하고 추출 지식과 원문 단위를 연결하는 구조 |
| [Graphiti](https://github.com/getzep/graphiti) | Episode → Entity와 사실 Edge | 원천 episode와 생성 사실의 분리, 시간상 변화와 출처 관계 |

LLM Wiki Compiler는 [`34ca1df97b3e60a6700048c48c7cf70c92a9bfdb`](https://github.com/atomicstrata/llm-wiki-compiler/commit/34ca1df97b3e60a6700048c48c7cf70c92a9bfdb)를 확인했다. 입력을 source Markdown으로 만든 뒤 개념을 추출하고, 같은 slug에 해당하는 자료로 wiki 본문을 작성한다. 구조 검사·review·write 경로가 분리돼 있어 운영 흐름을 참고할 수 있다. [compile 흐름](https://github.com/atomicstrata/llm-wiki-compiler/blob/34ca1df97b3e60a6700048c48c7cf70c92a9bfdb/src/compiler/index.ts#L103), [review](https://github.com/atomicstrata/llm-wiki-compiler/blob/34ca1df97b3e60a6700048c48c7cf70c92a9bfdb/src/compiler/review-pipeline.ts#L60)

이 compiler의 기본 embedding 대상은 작성된 wiki다. `include-sources`는 검색된 페이지의 인용을 따라 원문 줄을 읽는 기능이므로 독립적인 I semantic search와 다르다. source-entailment를 검사하는 LLM judge도 있으나 optional eval이며 기본 compile의 필수 의미 검증으로 해석할 수 없다. [검색 대상](https://github.com/atomicstrata/llm-wiki-compiler/blob/34ca1df97b3e60a6700048c48c7cf70c92a9bfdb/src/utils/embeddings-collect.ts#L50), [원문 조회](https://github.com/atomicstrata/llm-wiki-compiler/blob/34ca1df97b3e60a6700048c48c7cf70c92a9bfdb/src/context/provenance.ts#L118), [별도 인용 지지 평가](https://github.com/atomicstrata/llm-wiki-compiler/blob/34ca1df97b3e60a6700048c48c7cf70c92a9bfdb/src/eval/citation-support.ts#L33)

GraphRAG는 TextUnit을 graph extraction의 입력과 provenance 대상으로 두며 text unit text도 embedding 대상으로 삼는다. 이는 I의 두 역할과 관련된 설계 참고다. 하지만 Entity는 보통 사람·장소·사건 등의 대상이며, 우리의 Proposition/Observation K와 일대일 대응하지 않는다. [공식 dataflow](https://microsoft.github.io/graphrag/index/default_dataflow/)

TextUnit을 검색할 수 있다는 사실은 원본 PDF의 그림·기호·페이지 위치가 빠짐없이 보존됐다는 검증이 아니다. Palimpsest의 PDF 보존과 exact I↔D 대응 요구는 별도로 유지한다.

Graphiti의 조사한 Episode 검색은 full-text와 선택적 cross-encoder를 사용한다. 생성된 Entity/Fact 검색과 원문 검색을 구분해야 한다. 해당 구현의 시간 속성 갱신을 불변 semantic Revision으로 해석해서도 안 된다. [Episode 검색 코드](https://github.com/getzep/graphiti/blob/c64e45c111fd43ca7f5536a7f84a73f6acafd5b1/graphiti_core/search/search.py#L632), [동일 UUID 저장 코드](https://github.com/getzep/graphiti/blob/c64e45c111fd43ca7f5536a7f84a73f6acafd5b1/graphiti_core/models/edges/edge_db_queries.py#L96)

### 보조 문헌: Retrieval as Reasoning / LLM-Wiki

2026-05의 [arXiv v2 논문](https://arxiv.org/html/2605.25480v2)은 source passage에서 관련 wiki page를 선택해 문서·링크·index를 갱신하고, 구조·내용 오류를 Error Book에 기록하는 알고리즘을 설명한다. 원문 archive와 source digest를 함께 두고 검색·읽기·링크 탐색을 도구로 노출한다. 코드로 다룰 구조 오류와 LLM이 다룰 의미 오류를 구분하는 참고다. 논문의 요약·source digest를 Palimpsest의 무손실 원문 I로 바꾸어 부르지는 않는다. 이번 조사에서 그 논문의 공개 실행기를 검증하지 않았고, 보고된 QA 점수를 PDF 원문 보존이나 우리 I2K 정확도의 증거로 사용하지 않았다.

## Palimpsest에 대한 해석과 적용 제안

이 절은 외부 프로젝트가 증명한 사실이 아니라, 위 조사와 현재 사용자 계약을 연결한 설계 판단이다.

### 1. I는 계속 독립적인 원문·검색 계층이어야 한다

일반 wiki의 source page는 이미 LLM이 선택·요약한 내용일 수 있다. 그것만 검색하면 K 생성 때 놓친 내용도 함께 놓칠 수 있다. 우리는 K에 선택되지 않은 I까지 검색해야 한다. 따라서 `I의 원문 content 검색 → exact I 읽기 → D의 해당 위치 확인` 경로를 wiki 문서 검색과 별도로 유지한다.

Embedding은 I와 model/profile/hash를 참조하는 검색 index다. 모델 교체나 검색용 window 변경이 원문 I를 다시 쓰는 이유가 되어서는 안 된다. 이미지의 의미 검색 방식은 text embedding과 구분해 검증해야 하며, 텍스트 embedding을 만들었다고 이미지 내용을 모두 검색할 수 있다고 하지 않는다. 현재 BGE-M3 기본 선택과 교체 가능한 모델 경계는 그대로다.

I는 환각을 자동으로 제거하는 장치라기보다 **생성된 주장과 독립적으로 보존된 증거를 대조할 수 있게 하는 장치**다. K 인용이 I에 존재하는지와 그 인용이 K의 모든 중요한 내용을 지지하는지는 별도 검사다. I/OCR에 모호함이 있으면 등록 원본 D를 읽고 실제 사용·결손을 기록한다. 그 이유로 D2I를 다시 돌리지 않는다.

### 2. 읽는 문서의 크기와 K의 논리적 identity를 분리한다

wiki에서 읽기 좋은 논문·주제 페이지가 필요하다는 점과 모든 내용을 K 하나로 통합해야 한다는 주장은 다르다. 기존 K와 관련 I를 읽기 순서대로 모은 조회 결과를 만들면 출처별 K를 유지하면서도 사용자는 문서 형태로 볼 수 있다. 이것은 새 canonical domain이나 W의 의미 변경을 제안하는 것이 아니다. CLI-first 범위에서 읽기 projection으로 검토할 수 있다.

### 3. 탐색 링크, 근거 링크, 의미 관계는 목적이 다르다

| 연결 | 용도 | 생성·검증 책임 |
|---|---|---|
| 제목·태그·같은 Data·참조된 Figure·관련 문서 | 필요한 문맥으로 이동 | 보존 metadata/검색 projection. 과학적 지지로 해석하지 않음 |
| K의 특정 Revision → I의 정확 범위 → D | 주장의 근거와 원문 확인 | I2K의 명시적 evidence와 source locator 검사 |
| KRevision A supports KRevision B | 의미상 지지 관계 | N2E 제안·검증·exact endpoint/applicability |

한 wiki 문서가 다른 문서를 링크했다고 supports를 만들지 않는다. 또한 N2E로 의미 관계를 생성하는 것과 K2K로 새 결론 K를 도출하는 것을 구분한다. K2K의 도출 의존성을 임의의 새 semantic Edge 이름으로 바꾸지 않는다.

### 4. 기존 wiki의 작업 방식은 가져오되 쓰기 권한을 좁힌다

- 출처별 ingest와 source/주제별 탐색, 미해결 모순·누락 기록을 참고한다.
- LLM에는 기존 canonical 문서를 자유롭게 덮어쓰게 하지 않고, 구조화된 후보·근거·수정 제안을 받는다.
- Runtime이 정확 refs, 허용 operation, identity, 현재 Revision, 실제 모델 전달과 검증, atomic commit을 담당한다.
- 원문 지지 검증과 기존 K 동일성 검증을 분리한다. 기존 K와 같다는 이유로 불충분한 새 I 인용을 추가하지 않는다.
- 새 source가 들어와도 K 통합을 의무화하지 않는다. 같은 의미가 검증된 경우만 재사용하고 별개 실험은 보존한다.
- query의 표시·요약·정렬은 새로운 지식 명제의 도출과 구별한다. I의 명시 내용과 기존 K를 출처별로 구성하고, 새 명제 도출이 필요하면 별도 K2K 경로로 다룬다. 조회 문서에 썼다는 이유로 canonical 지식으로 자동 승격하지 않는다.

## 이번 조사 다음에 할 검증

1. 외부 프로젝트를 통째로 교체 도입하지 않고 기존 [I2K 신뢰성 개선안](../../progress/T04_I2K_reliability_proposal.md)의 두 실패 사례에 source-grounding 검증을 적용한다.
2. K를 만들지 않은 I에서도 사용자가 묻는 방법·조건을 semantic search로 찾아 exact 원문 인용까지 반환하는지 시험한다. K 개수나 wiki link 수를 이 검증의 대체 지표로 쓰지 않는다.
3. wiki 읽기 projection에서 원문 보고 내용, 검증된 K, K2K 추론을 구별하고 각각의 provenance를 표시하는지 확인한다.
4. 새 근거 추가·잘못된 K 정정·source 상태 변화가 기존 Revision/Record를 보존하면서 반영되는지 검증한다.

이번에는 조사 문서만 작성했다. I semantic index나 새 조회 도구, K 재검토, 새 migration을 구현하거나 실행했다고 보고하지 않는다.
