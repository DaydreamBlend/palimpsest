## 29. 아직 확정하지 않은 구현값

이 문서는 다음 값을 임의로 확정하지 않는다.

- `data_id`가 content hash인지 UUIDv7인지
- Generator/Validator provider와 model
- embedding provider, model, dimensions, metric, normalization
- lexical/vector fusion 방식과 weight
- I2K/N2E/K2K retrieval top-K
- semantic near-duplicate threshold
- KEdge predicate 전체 registry와 endpoint matrix
- human review UI와 multi-review policy
- rejected candidate audit retention 기간, 암호화와 민감정보 정책
- K lifecycle/event enum과 decision status projection 규칙
- derivation/evidence-distance 표시 방식과 evidence support 평가 정책
- operational non-convergence/anomaly detection threshold와 resume 정책
- explicit D recompile/repair command, compilation_generation 증가 정책과 migration policy
- Information supersession 기반 K revalidation의 별도 public Operation/Record 명칭
- background scheduler와 worker 배치 전략

이 값들은 실제 evaluation과 구현 요구를 바탕으로 별도 승인한다.

---

## 30. 구현 순서 원칙

1. 이 문서에 맞춰 JSON/DB boundary schema를 먼저 고정한다.
2. D 등록, DataAcquisition, 공통 Operation execution log와 compilation_generation 기반 D2IRecord를 구현한다.
3. source-specific immutable Information, extractor-aware grounding, TemporaryCandidate, FP guard와 I RAG를 구현한다.
4. InformationSupersession/Invalidation DAG와 exact provenance를 구현한다.
5. KCompilationRecord, canonical_effects, K grounding과 expected-base CAS를 포함해 I2K accepted KNode vertical slice를 완성한다.
6. KLifecycleEvent, I supersession outbox와 직접 연관 K material-delta-gated revalidation을 구현한다.
7. KNode RAG와 N2E discovery/revalidation, KEdgeApplicabilityEvent와 current edge applicability projection을 구현한다.
8. KEdge RAG와 root-independent derivation_depth metadata를 가진 convergent K2K propagation을 구현한다.
9. retrieval_mode/epistemic_basis를 포함한 KQ2W Explanation/Recommendation을 구현한다.
10. 구조화 Decision W, event identity와 atomic automatic W2K를 구현한다.
11. decision trace를 구현한다.
12. W2P와 P2B를 구현한다.

각 단계는 다음 단계로 넘어가기 전에 duplicate, rejection, provenance, immutable-history test를 통과해야 한다.

---

## 결론

Palimpsest의 핵심은 많은 텍스트를 저장하는 것이 아니다.

```text
원본 D를 보존하고,
의미 있는 I를 검색 가능하게 만들고,
I가 교체되면 과거 근거를 보존한 채 연관 K를 재검증하고,
I와 기존 K를 반복 분석해 검증된 KGraph를 성장시키며,
Query와 Context에 맞춰 설명·추천·결정을 만들고,
확정된 결정을 다시 KGraph의 장기 기억으로 편입하고,
모든 결과가 어떤 입력과 판단에서 나왔는지 재현하는 것
```

이 구조에서 창의성은 K2K의 새로운 조합에서 나오고, 신뢰성은 Generator–Validator 분리, source-specific Information, Record/effect 원장, exact provenance, scoped fingerprint suppression, material-delta 검증, revision concurrency guard, edge applicability revalidation, root-independent derivation-depth 추적과 fixed-point convergent propagation에서 나온다.
