# Wiki/K → I → D 검색·근거 답변 CLI

**0.13 후속:** [코드·검토·Wiki 계약](CODE_REVIEW_WIKI.md)은 source-version head와 완전한 accepted support 경로로 K2K를 검색에 포함하고, 기존 추론의 exact KRevision 인용을 `wiki-query-answer-v2`로 구분한다. 원문 직접 인용을 만들거나 query-time 새 추론을 수행하지 않는다. 아래0.8의 source-only 동작·과거 index/답변 bytes는 보존된다.

2026-09-12. 앱 `palimpsest-query:0.8.0`, additive `0010_wiki_retrieval`, 로컬 embedding worker `palimpsest-retrieval-bge:0.1.0`의 구현 계약이다. [Wiki DB 저장](WIKI_DATABASE.md) 위에 검색과 query-time 답변을 추가한다. [실물 결과](../../output/t07-wiki-query-ui/REPORT.md), [UI 비교·연결 설계](../implementation/WIKI_UI_INTEGRATION.md), [계획](../../progress/T07_wiki_query_ui_execplan.md)을 함께 확인한다.

## 검색 corpus와 index

현재 Wiki catalog가 선택한 논문의 완료 source execution을 고정한다. 같은 D의 과거 source 실행을 섞지 않는다. 모든 선택된 I를 보존하며, 해당 I에 실제 grounding이 있는 current accepted K와 검증된 Wiki 본문 항목을 검색 문서로 만든다. 알려진 검토 필요 KRevision은 제외한다. 이 첫 corpus는 현재 Wiki collection의 source 범위이며, 그 밖의 모든 역사 K/KEdge를 자동 탐색하는 전역 graph 검색은 아니다.

실제 세 논문 index에는 I 87개, K 30개, Wiki 항목 37개의 총 154개 문서가 있다. I 49개는 원문 text, 38개는 text가 없는 Image I의 보존된 제목과 명시적인 image descriptor다. **BGE-M3는 텍스트 encoder이므로 38개 이미지의 시각 의미 embedding을 수행한 것은 아니다.** 이미지 자체와 원래 I는 보존하며, 선택된 I를 모델에 줄 때 실제 media를 첨부한다.

`BAAI/bge-m3` revision `5617a9f61b028005a4858fdac845db406aefb181`의 dense 1024차원 벡터를 `wiki_retrieval.indexes/chunks`에 저장한다. tokenizer의 최대 512-token/64-token overlap 검색 창은 모든 문자 범위를 덮고 exact substring hash를 보존한다. 이 검색 창은 canonical I를 분할·재저장하는 작업이 아니다. 실제 154개 문서가 261개 검색 창으로 변환됐다.

PostgreSQL pgvector exact cosine으로 후보를 찾고 **같은 BGE-M3의 ColBERT late-interaction 점수**로 다시 정렬한다. 전용 bge-reranker 모델이나 다른 점수로 대체하지 않는다. 모델 파일 hash·revision·차원·normalization·청킹·정밀도·장치·library·adapter hash를 profile에 저장한다. 다른 profile의 query vector나 rerank 결과는 거부한다. [worker profile·Docker 실행](../../deploy/retrieval/README.md).

현재 corpus 규모에서는 ANN index를 만들지 않고 정확한 거리 계산을 한다. vector column은 index profile별 차원을 검사하므로 다른 차원의 후속 adapter를 연결할 수 있지만, 실제 제공·검증한 worker는 BGE-M3다. Qwen embedding/reranker 지원 완료로 보고하지 않는다.

Wiki head 또는 K state가 바뀌면 새 검색 작업에서 stale index를 거부한다. 먼저 Wiki DB import를 refresh하고 새 index UUID로 색인한다. 이전 index·벡터·corpus bytes는 수정하지 않는다. 새 전체 index를 만드는 현재 방식에서 문서별 증분 embedding 재사용은 후속 최적화다.

## 질문의 실행

1. 현재 index, Wiki import, K state, 질문과 UUIDv7 request를 고정한다.
2. Wiki/K를 먼저 검색한다. 선택된 K와 Wiki 항목은 탐색 문맥으로 제공하고 그 항목에 연결된 실제 I를 full content/refs/media로 읽는다.
3. Generator가 근거가 부족하다고 판단하면 `needs_information`과 검색 문구를 반환한다. 전체 I corpus에서 다시 검색하고 이전에 본 근거를 유지한다.
4. 원문 확인이 필요하면 `needs_source`에 정확한 Data·page numbers·이유를 명시한다. 등록 원본 bytes를 검증하고 요청한 원본 페이지 이미지를 준비한다. 이 읽기는 D2I나 새로운 I 생성이 아니다.
5. 답변 후보는 주장별 I 또는 실제 전달된 원본 이미지 근거를 인용한다. 별도 Validator 세션이 주장·조건·인용 충분성·질문 충족을 판정한다. 통과한 답변만 확정된 출력으로 보여준다.

top-k는 한 번의 조회 창이며 충분성 판정이 아니다. 모델은 추가 검색을 요청할 수 있다. runner는 동일 문구·동일 근거를 반복 요청해 진전이 없는 경우 unresolved로 중단하며, 성공 완료로 바꾸지 않는다. 일반적인 token/cost/depth 상한으로 canonical 전파를 완료 처리하는 기능은 없다.

반복 무진전은 `query-pause`로 `needs_attention`과 이유, `completed=false`를 영속 기록한다. 구조적으로 모순된 Generator 응답은 `invalid_response`로 보존하고 `query-revise`에서 실패 내용을 참고하는 새 round로 재개할 수 있다. 이전 오류를 삭제하거나 유효한 모델 판정으로 바꾸지 않는다. `needs_attention`의 미등록 자료는 현재 query가 임의로 다운로드·등록하지 않는다.

검색 실패나 일부 인용의 정보 부재를 전체 D의 부재로 단정하지 않는다. 답변은 확인한 근거 범위를 명시해야 한다. 조회 중 새로운 결론·실험값·사용자 결정·개인 기억을 만들지 않는다. 새로운 추론 K는 별도 K2K의 책임이고 이 query 결과가 자동으로 canonical K/W/P가 되지 않는다.

## 원본 전달의 실제 형태

현재 CodexProvider는 이미지 입력을 지원하며 native PDF bytes 입력은 없다. `query-source`는 등록 PDF 원본의 SHA-256을 검증하고 로컬 query 폴더에 정확한 bytes를 보존한다. 그 원본의 retained renderer receipt, Data/source execution/page와 결속된 페이지 이미지를 모델에 전달한다. `original_pdf_read_locally=true`, `original_pdf_delivered=false`를 구분한다.

source-inspection에는 요청 이유·원본 hash·byte size·선택한 page를 준비 기록으로 남긴다. 실제 전달은 별도의 Generator/Validator receipt에서 exact image hash·size로 확인한다. descriptor가 있다는 사실만으로 모델이 이미지를 본 것으로 처리하지 않는다. 원본 페이지 이미지가 없다면 오류·미해결 상태로 남고 재파싱이나 임의 이미지 대체를 하지 않는다. 원본 조회만으로 D2I 누락이 확정됐다고 기록하지 않는다.

## 구조화 응답과 이력

Generator는 `answered / needs_information / needs_source / insufficient`, `claims`, `search_query`, `source_requests`, `unresolved`를 반환한다. 각 claim에는 exact I block 또는 unique quote/media citation, 또는 전달된 source page evidence ID가 필요하다. 스크립트는 원문 Unicode를 정규화해서 인용 위치를 바꾸지 않는다.

Validator는 claim별 supported/citations_sufficient/scope_preserved/no_new_inference와 overall question_answered/conflicts_resolved/information_sufficient를 판정한다. `accepted`는 모든 요구가 충족될 때만 가능하다. `needs_review` renderer는 보류 본문을 확정 답변으로 표시하지 않는다. source-supported 표시도 의미적 진실의 절대 보증은 아니며 실물 결과의 독립 품질 검토와 구분한다.

`query-revise`는 이전 답변·인용·모델 receipt·판정을 그대로 두고 새 round를 만든다. 보류된 답변은 Validator 지적을 제공하고, 이미 answered인 답변의 재검토에는 명시적인 review-notes가 필요하다. feedback은 다시 확인할 지점이며 원문 근거 또는 사실 확정 권위가 아니다. 피드백으로 source/I/기존 K를 수정하지 않는다.

검색 index는 PostgreSQL에, query 진행 이력은 별도 관리 파일 폴더에 저장한다. 각 `queries/<uuid>/rounds/<n>/`에 embedding/search/rerank/context/model request/response/exchange/proposal/validation/answer가 남는다. 후속 요청은 request hash·exact context·policy request binding·I 목록·실제 이미지 전달·독립 provider ref를 검사한다. 신규 model request에는 당시 query policy hash와 request hash를 별도로 보존해 이후 prompt 변경과 역사 응답을 구분한다. 원래 파일 Wiki와 query 폴더를 섞지 않는다.

## 공개 CLI

아래 명령은 DB 설정과 Artifact Store가 연결된 앱 내부에서 실행한다. opaque IDs는 실제 UUIDv7로 대체한다. 같은 성공 요청의 재전송과 다른 내용의 같은 ID 충돌을 구분한다.

```text
palim wiki retrieval-prepare --wiki-id <wiki> --index-id <new-index> --directory /results/query-store --database-name <db> --json
palim wiki retrieval-install --index-id <index> --embedding /results/embedding-result.json --directory /results/query-store --database-name <db> --json
palim wiki query-prepare --index-id <index> --request-id <query> --question <question> --directory /results/query-store --database-name <db> --json
palim wiki query-search --request-id <query> --embedding <query-embedding-result> --directory /results/query-store --database-name <db> --json
palim wiki query-context --request-id <query> --rerank <rerank-result> --directory /results/query-store --database-name <db> --json
palim wiki query-request --request-id <query> --phase generator --directory /results/query-store --database-name <db> --json
palim wiki query-stage --request-id <query> --response <generator-response> --directory /results/query-store --database-name <db> --json
palim wiki query-source --request-id <query> --directory /results/query-store --database-name <db> --json
palim wiki query-request --request-id <query> --phase validator --directory /results/query-store --database-name <db> --json
palim wiki query-decide --request-id <query> --response <validator-response> --directory /results/query-store --database-name <db> --json
palim wiki query-show --request-id <query> --directory /results/query-store --database-name <db> --json
palim wiki query-revise --request-id <query> --review-notes <optional-json-string-list> --directory /results/query-store --database-name <db> --json
```

CLI는 `query-source`를 원문 요청이 보류된 경우에만 허용한다. query-show는 과거 파일 결과를 읽을 수 있고, 새 검색/모델 작업은 현재 index 상태를 확인한다. embedding worker와 실제 Codex 호출은 별도 명령이며 요청 JSON 준비를 전달 receipt로 간주하지 않는다.

## 한 질문을 실행하는 host runner

`tools/ask_wiki.py`가 위 CLI, 네트워크 없는 BGE Docker, 기존 `tools/run_knowledge_model.py`의 Terra Medium OAuth 호출을 순서대로 실행한다. 다음은 이미 색인된 실험 환경의 예시다. `--request-id`는 새로운 실제 UUIDv7를 넣는다.

```powershell
python tools/ask_wiki.py --directory output/t07-wiki-query-ui --project palimpsest-multi-checks --database-name palimpsest_wiki_pg --artifact-volume palimpsest-knowledge_artifacts --model-directory .local/models/bge-m3-5617a9f61b028005a4858fdac845db406aefb181 --index-id 01a095c9-16b1-74ef-8660-7ac02483e46e --request-id <new-uuidv7> --question "SuperMApo 제조 방법은?" --codex <approved-codex-executable> --allow-model-calls
```

runner는 Docker 프로젝트·DB·Artifact volume·로컬 model·OAuth executable을 명시적으로 받는다. 새 key/provider를 만들지 않으며 일반 query 명령이 자동으로 모델을 실행하지도 않는다. 동일한 요청의 재실행은 이미 저장된 worker response를 재사용한다. 보류 답변의 후속 시도는 `--revise`, accepted 답변 재검토에는 `--revise --review-notes <file>`을 사용한다. controller 명령·exit/stdout/stderr는 query별 journal에 남긴다. worker 전송 실패나 반복 무진전은 정상 답변으로 위장하지 않는다. 완전한 T11 실패 재개·취소 운영 기능은 별도 범위다.

## 모듈과 후속 경계

- `wiki_retrieval.py`: 현재 source/K/corpus 결속, index 설치·profile 검사·PG 검색.
- `bge_retrieval.py`, `run_wiki_embeddings.py`, `deploy/retrieval`: 선택 모델과 tokenizer/late-interaction worker.
- `wiki_query.py`: strict schema·질문/원문 중심 prompt·인용 정규화·독립 검증·renderer.
- `wiki_query_runtime.py`: query/round/실제 전달/source 요청·재검토 이력, canonical 쓰기 없는 서비스.
- `ask_wiki.py`: 명시적인 host orchestration; 앱 DB credential은 읽거나 출력하지 않음.

GUI와 HTTP API는 이번에 scaffold하지 않았다. formal W/P, effective KEdge 전역 RAG, 새 K2K 추론, query의 canonical 승격, 전역 incremental index, CPU 실물 추론은 이번 완료 범위가 아니다.
