# 교체 가능한 Embedding/Reranker profile

상태: U04의 기본값·교체 가능성과 U09의 PostgreSQL 18/pgvector 선택을 구체화하는 구현 계약. 실제 model adapter/설치/DB index는 아직 없다. 근거는 [사용자 변경](../decisions/USER_OVERRIDES.md)이며 P09/P12의 나머지 계약을 승인하지 않는다.

2026-09-10 I2K 후속: [문서 구조별 입력·provenance 검색 정책](../implementation/I2K_CONTEXT_POLICY.md)에 따라 exact I/source range에 profile별 파생 embedding을 연결하고, same-D의 관련 문맥과 corpus의 관련·상충 근거를 함께 찾는다. 입력 그룹, embedding 검색 단위, canonical I는 구분한다. 같은 D 또는 높은 similarity를 진실·identity·독립 support의 승인으로 취급하지 않으며, 기존 I/IDs/FP를 벡터 모델 교체 때문에 수정하지 않는다. 이 문서의 실제 adapter/index 미구현 상태는 그대로다.

## 현재 기본값과 향후 후보

| 역할 | 현재 기본값 | 향후 교체 후보 |
|---|---|---|
| Embedding | `BAAI/bge-m3`, dense 1024 | `Qwen/Qwen3-Embedding-4B`, `Qwen/Qwen3-Embedding-8B` |
| Reranker | `BAAI/bge-m3` 자체 multi-vector ColBERT late-interaction | `Qwen/Qwen3-Reranker-4B`, `Qwen/Qwen3-Reranker-8B` |

Qwen은 향후 지원 후보이며 아직 선택·설치·구현하지 않았다. 4B/8B 중 기본값이나 실제 출력 차원을 미리 선택하지 않는다. 전용 `BAAI/bge-reranker-v2-m3`는 현재 Reranker가 아니다.

## 최소 교체 경계

application service가 embedding profile과 reranking profile을 독립적으로 선택한다. 한 역할의 모델 변경이 다른 역할의 모델 변경을 강제하지 않는다. 모델별 tokenizer, input instruction, pooling, vector 생성 및 점수 계산은 adapter가 맡는다. domain/compiler와 CLI에 모델 이름이나 dimension 1024를 고정하지 않는다.

- Embedding 입력: 텍스트 묶음과 query/document 역할. 출력: 선택된 profile 식별자, 해당 profile 차원의 dense vectors. query와 저장된 문서 벡터는 동일한 embedding 공간/profile을 사용한다.
- Reranking 입력: query text와 안정된 candidate ID/text의 묶음. 출력: candidate ID별 관련성 점수와 사용한 profile/점수 방식. 큰 값이 더 높은 관련성을 뜻하도록 adapter가 방향을 맞춘다. 동일 요청 내 점수는 같은 profile로 계산하며 개수·ID 대응과 유한한 수치를 검사한다.
- 공통 Reranker 입력을 BGE의 token vectors로 고정하지 않는다. BGE adapter 내부에서 multi-vector를 계산/재사용할 수 있고, 향후 Qwen adapter는 query/document를 함께 처리할 수 있다.
- 점수를 확률이나 0–1로 공통 가정하지 않는다. 모델/score transform이 다르면 수치와 threshold를 직접 비교·재사용하지 않는다.

이 경계는 역할별 설정과 adapter의 책임을 정하는 것이다. 현재 모든 후보용 class/factory/service를 scaffold하거나 모델들을 동시에 preload하지 않는다. 실제 adapter는 해당 지원을 구현할 때 추가한다.

## 기록할 profile 정보

| Profile | 재현·호환성 확인 정보 |
|---|---|
| 공통 | model ID, resolved revision/artifact digest, runtime/adapter version, precision, input projection/tokenizer/instruction version, 길이 처리 정책 |
| Embedding | 실제 output dimensions, pooling, normalization, distance metric, query/document 역할별 전처리, 저장/ANN index 표현과 pgvector version |
| Reranking | scoring method, score transform, query/document template, 입력 길이 처리, 모델별 score 의미 |

현재 reranking method는 `colbert_late_interaction`이다. BGE-M3의 dense similarity나 dense/sparse/ColBERT 혼합 점수로 대체하지 않는다. sparse retrieval, fusion weight, top-K, score threshold, 전체 corpus multi-vector index의 채택은 아직 별도 미정이다.

실행 환경이 profile을 지원하지 않으면 구체적인 오류를 반환한다. 미지원 모델을 BGE 기본값으로 조용히 바꾸거나 일부분의 결과만 전체 완료로 표시하지 않는다.

## 모델 교체와 검색 projection

Embedding 모델/revision/dimension/pooling/normalization/input projection 변경은 새 embedding 공간으로 취급한다. 해당 profile로 query와 문서 벡터를 다시 만들고 검증한 뒤 검색에 사용한다. 차원이 우연히 같더라도 다른 profile의 벡터를 섞지 않는다. 필요한 재색인은 파생 검색 projection을 대상으로 하며 canonical D/I/K 의미, ID, 과거 provenance를 다시 쓰지 않는다.

Reranker만 바뀌면 dense index를 자동 재작성하지 않는다. 새 reranking profile로 재점수화하고 관련 cache를 분리한다. BGE multi-vector cache를 유지한다면 그 cache도 모델/revision/input profile에 귀속한다.

과거 실행은 당시 사용한 profile을 가리킨다. 모델 교체로 과거 점수나 결과를 새 모델 값으로 덮어쓰지 않는다. 새 index의 준비 상태·전환·동시 읽기 및 exact replay wire 설계는 P09의 미승인 세부 계약과 별개로 남긴다.

## U09 — pgvector 저장과 ANN 경계

초기 dense projection은 PostgreSQL 18의 pgvector를 사용한다. pgvector 0.8.6에서 vector/halfvec 저장 한도는 16,000차원이지만 HNSW/IVFFlat ANN은 vector 최대 2,000, halfvec 최대 4,000차원이다. 가변 차원 vector 컬럼은 가능하나 인덱스는 같은 profile/차원에 맞춰 분리한다. [pgvector 공식 README](https://github.com/pgvector/pgvector/blob/v0.8.6/README.md)

따라서 BGE 1024용 ANN 구성을 Qwen의 최대 차원에 그대로 적용하지 않는다. 향후 4B의 2560차원은 vector ANN 한도를, 8B의 4096차원은 halfvec ANN 한도도 넘는다. 실제 선택 차원·exact 검색/ANN·half precision/차원 축소/양자화는 교체 시 평가하며 자동 절삭하지 않는다. 이 경계는 BGE multi-vector ColBERT 재순위화를 dense 거리로 대체하지 않는다.

T02 [저장 스키마 초안](../schema/T02_STORAGE_SCHEMA.md)은 extension 요구만 다루며 embedding/profile 테이블과 인덱스는 해당 검색 기능의 실제 구현 때 추가한다. [U09 계약](../decisions/STORAGE_IDENTITY.md)을 따르며 pgvector 채택이 fusion/top-K/threshold 결정을 포함하지 않는다.

## 공식 모델 사양과 검증 한계

`BAAI/bge-m3`는 dense 1024 및 multi-vector ColBERT scoring을 제공한다. `Qwen3-Embedding-4B`는 최대 2560, `Qwen3-Embedding-8B`는 최대 4096 dense dimension이며 둘 다 32부터 최대값까지 output dimension 선택을 지원한다. 이는 upstream 사양이고 Palimpsest의 실제 선택 차원은 아니다. [BGE-M3](https://huggingface.co/BAAI/bge-m3), [Qwen3-Embedding-4B](https://huggingface.co/Qwen/Qwen3-Embedding-4B), [Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-8B)

Qwen3-Reranker는 instruction/query/document를 함께 입력하고 yes/no logits를 이용해 관련성 점수를 산출한다. raw logit difference와 sigmoid/softmax 점수는 다른 score transform이므로 실제 사용 방식을 profile에 남긴다. [Qwen3-Reranker-4B](https://huggingface.co/Qwen/Qwen3-Reranker-4B), [Qwen3-Reranker-8B](https://huggingface.co/Qwen/Qwen3-Reranker-8B)

실제 구현 시 모델별 한국어 query/document 순위, batch별 ID 대응, dimension/profile 불일치, Reranker 단독 교체, 필요한 embedding 재색인, unsupported profile 오류와 history 보존을 검사한다. 현재 검증은 문서/승인 정책 무결성만이며 model loading·성능·검색 품질 검증은 미실행이다.
