# K2W — 질문·Context에 대한 설명과 추천

사용자의 2026-09-14 구현 요청에 따른 첫 범위는 `knowledge_only` 설명·추천 W다.
이 문서는 pure contract와 Runtime 연결을 설명한다. 실제 DB·배포·모델 검증 결과는
해당 실행 계획과 보고서에 따로 기록한다. T08 전체나 미승인 P08 세부 정책의 완료를 뜻하지 않는다.

## K, W, P의 경계

- K는 accepted 지식과 exact semantic Revision이다. K2W가 K 문구나 Revision을 바꾸지 않는다.
- W는 특정 Query·Context·당시 K snapshot을 사용한 설명 또는 조건부 추천이다.
- P는 Wiki에 표시할 문서다. 서로 다른 설명 W를 문서 목적에 맞게 구성할 수 있다.
  W2P에서 선택한 W와 구체 claim을 그대로 구성하는 것은 새 Knowledge 추론과 다르다.

예를 들어 여러 논문의 accepted K로 특정 주제를 설명하면 explanation W가 된다.
논문별 W나 주제별 W를 모아 만든 Wiki 문서는 P다. 과거 I에서 직접 생성한 Wiki의
실제 I citations와 generation history를 새 K2W 결과인 것처럼 소급해서 바꾸지 않는다.

## 현재 입력

`k2w-input-v1`은 정확한 KNode Revision, 선택적인 EffectiveEdge, Query, Context,
Knowledge state version, retrieval snapshot을 digest와 함께 고정한다.
첫 구현은 `evidence_mode=knowledge_only`, `retrieval_strategy=standard`다.

Runtime이 accepted/current K를 조회하고 current support signature를 고정한다.
한 Node만으로도 설명할 수 있다. Edge를 사용하면 semantic revision·실제 endpoint pair·
applicability basis·read-state token을 가진 EffectiveEdgeRef와 양쪽 실제 Node를 포함한다.
이 pure 계약의 구조 검증은 DB에서의 acceptance/currentness 검사를 대체하지 않는다.

Query와 Context는 사용자의 조건과 선호를 표현하는 임시 입력이다. 이를 사실 근거나
authority로 승격하지 않는다. 모든 입력의 원래 bytes/내용은 frozen packet에서 추적한다.
모델에 주는 projection은 K 문구·의미·추론 기원·가정·한계를 보존하고, I/D 원문 인용과
임의 nested provenance는 제외한다. retrieval metadata는 hash만 전달한다.

## 구조화된 출력과 독립 검증

Generator는 `status`, `claims`, `recommendation`, `unresolved`만 출력한다.
각 claim은 `claim_key`, `text`, `epistemic_basis`, `k_revision_ids`,
`effective_edge_revision_ids`, `assumptions`, `limitations`를 갖는다.
인용할 수 있는 ID는 실제 전달한 snapshot에 존재하는 정확한 Revision뿐이다.
Edge 인용은 양 endpoint의 Node 인용도 필요하며 전체 EffectiveEdgeRef는 앱이 연결한다.

추천 W는 실제 options·criteria와 각 option/criterion의 claim 참조를 보존한다.
추천은 `advisory_recommendation`으로 표시하며, 추천할 근거가 없으면 선택지를 강제로 고르지 않는다.
Context에 따른 조건부 조언은 허용하지만 원문 K에 없는 새로운 일반 사실을 확정하지 않는다.
새 canonical 지식 추론은 K2K에서 수행한다. Explanation은 recommendation을 갖지 않는다.

독립 Validator는 모든 claim에 대해 지원 근거, 인용 충분성, scope, 한계,
출처 없는 새 추론 여부를 각각 판정한다. 전체 질문 대응과 추천/authority 경계도 판정한다.
accepted에는 모든 검사가 true여야 한다. 필요한 지식이 부족한 정직한 설명도 W가 될 수 있지만
`insufficient`와 `unresolved`를 숨기지 않는다. 검증 보류·실패는 accepted W가 아니다.

## 불변 저장

`wisdom-v1`의 ID와 생성 시각은 앱이 부여한다. 동일한 문구가 나와도 별도의 새 synthesis는
다른 W다. 성공 요청의 idempotent replay만 기존 W를 반환한다. `WisdomRevision`은 만들지 않는다.
스냅샷에는 Query·Context·retrieval·generation profile·input hash·답변·독립 검증·실제 사용한
Node/Edge refs·claim별 citations·uncertainty를 보존한다.

`used_k_revision_ids`는 실제 인용한 Node Revision과 semantic Edge Revision의 합집합이다.
`used_effective_edge_refs`는 실제 Edge 해석의 전체 exact ref를 보존한다.
검색/전달됐으나 쓰이지 않은 K는 input에 남고 used refs에는 들어가지 않는다.

## 첫 구현에 포함하지 않는 기능

직접 I를 사용하는 `knowledge_plus_evidence`/`evidence_only`, 자동 retrieval·Query 재실행,
Decision authority·W2K, 새 provider 전송 승인은 별도 범위다. recommendation은 사용자의 확정 결정이
아니며 자동 K 생성이나 W2K를 발생시키지 않는다. K2W에서 D2I·D2K를 호출하지 않는다.

구현: `src/palimpsest/k2w.py`, `k2w_prompts.py`, `wisdom.py`.
pure 검사: `PYTHONPATH=src;tests/app python -m unittest test_k2w` — 실제 provider 호출은 없다.

## Runtime과 CLI

`WisdomRuntime`은 `prepare → request(generator) → stage → request(validator) → validate → commit`으로 실행한다. Request 파일 내보내기는 전송이 아니다. 실제 모델 호출의 exact prompt/schema/input/output hash·전달한 K/Edge·모델 profile·독립 provider ref가 일치하는 receipt가 필요하다. 보류된 판정은 W가 되지 않는다. 현재 K 상태·근거 signature·실행 코드가 변하면 미완료 실행은 그대로 commit할 수 없다. 완료 요청의 재시도는 과거 W를 돌려준다.

```text
palim wisdom prepare --request-id UUIDv7 --query "Th17을 설명해 줘" --context context.json --revision-id UUIDv7 --kind explanation
palim wisdom request EXECUTION_UUID --phase generator --directory run-directory
palim wisdom stage EXECUTION_UUID --response generator-exchange.json
palim wisdom request EXECUTION_UUID --phase validator --directory run-directory
palim wisdom validate EXECUTION_UUID --response validator-exchange.json
palim wisdom commit EXECUTION_UUID
palim wisdom get WISDOM_UUID
```

동일 DB의 `compiler_runtime.w_jobs/w_inputs/w_edge_inputs/w_calls/w_events`와 `canonical_store.wisdoms`를 사용한다. W에 가짜 대표 D를 붙이지 않는다. SQL0021과 추가0023은 실제 response→answer→독립 validation→W, exact Node/Edge 입력, 사용한 Edge의 합집합과 가정·한계 보존을 검사한다. 함수 이름 충돌 수정도0023에 추가하며 설치된0021을 덮어쓰지 않았다. 신규 스키마는 이번에 격리 검사 DB에만 설치했다.

Source hash·실험 구분·정확한 자료 version metadata는 모델에 전달하며 raw I/D 인용은 추가하지 않는다. 실제 검증 결과는 [T24 보고서](../../output/t24-wisdom-realm/REPORT.md)를 따른다.
