## 29. 아직 확정하지 않은 구현값

U04는 embedding 기본 BAAI/bge-m3(dense 1024)와 동일 모델의 multi-vector ColBERT 점수 재순위화를 선택했다. 두 역할은 독립 교체 가능하며 Qwen3-Embedding/Reranker 4B·8B는 향후 후보로 둔다. 필요한 재색인은 파생 projection에 한정하고 canonical history를 보존한다. U05는 MinerU의 설치/명시적 업그레이드 시 최신 안정판 선택과 exact 실행 profile 기록을 확정했다. U06은 domain/변환별 모듈화와 adapter 독립성, 공통 atomic commit 경계를 확정했다. U08은 R01–R09의 명시된 구조 수정을 적용했다. U09는 PostgreSQL 초기 major 18/pgvector와 raw-byte SHA-256 Data ID, 나머지 신규 opaque UUIDv7, 도구 관리 등록과 검증된 효과의 atomic 반영을 선택했다. U10은 앱 언어 Python과 Docker 기반 실행·배포를 선택했다. U11은 결정적 원문 보존 D2I와 I2K부터의 구조화된 LLM 의미 해석을 선택했다. 실제 단계별 구현 profile은 실행 문서를 따르며 아래 전역/후속 범위는 별도다.

- I2K 이후 Generator/Validator provider와 model; D2I에는 application LLM profile을 두지 않음
- embedding/reranker runtime·모델 revision/digest, dense metric, normalization; dense 기본 차원은 BGE-M3 공식 1024
- lexical/vector fusion 방식과 weight
- I2K/N2E/K2K retrieval top-K
- semantic near-duplicate threshold
- KEdge predicate 전체 registry와 endpoint matrix
- human review CLI flow와 multi-review policy; GUI 설계는 CLI release 이후 마지막 단계
- rejected candidate audit retention 기간, 암호화와 민감정보 정책
- K lifecycle/event enum과 decision status projection 규칙
- derivation/evidence-distance 표시 방식과 evidence support 평가 정책
- operational non-convergence/anomaly detection threshold와 resume 정책
- explicit D recompile/repair command, compilation_generation 증가 정책과 migration policy
- Information supersession 기반 K revalidation의 별도 public Operation/Record 명칭
- background scheduler와 worker 배치 전략
- MinerU 최신 안정판을 설치 시 다시 확인한 exact version/digest와 검증된 backend/model/hardware profile 및 출력 adapter 버전
- Python exact version/packaging/CLI·DB driver/migration runner, Docker image/digest·service/volume/port profile, PostgreSQL 18의 실제 minor/pgvector version과 검증된 DB test 명령
- CLI framework·명령/옵션의 상세 문법; GUI framework는 마지막 단계 전까지 채택하지 않음

이 값들은 실제 evaluation과 구현 요구를 바탕으로 별도 승인한다.

---

## 30. 구현 순서 원칙

1. 이 문서에 맞춰 JSON/DB boundary schema와 CLI application-service 경계를 먼저 고정한다. D/I/K/W/P/B 및 변환별 모듈은 해당 단계의 실제 기능/테스트와 함께 만들고 공통 저장/실행 경계를 재사용한다. 현재 작업에서 GUI를 scaffold하지 않는다.
2. CLI skeleton/help/doctor와 D 등록·DataAcquisition·exact read/verify를 연결하고, 공통 Operation execution log와 compilation_generation 기반 D2IRecord를 구현한다.
3. PDF에는 local MinerU와 결정적 source-unit assembly를 연결한다. source-specific immutable Information, 전체 page/block/Figure coverage, exact grounding/hash, Record/FP/retry/atomic commit과 projection 경계를 검증한다. semantic LLM은 I2K부터 적용한다.
4. InformationSupersession/Invalidation DAG와 exact provenance를 구현한다.
5. KCompilationRecord, canonical_effects, K grounding과 expected-base CAS를 포함해 I2K accepted KNode vertical slice를 완성한다.
6. KLifecycleEvent, I supersession outbox와 직접 연관 K material-delta-gated revalidation을 구현한다.
7. KNode RAG와 N2E discovery/revalidation, KEdgeApplicabilityEvent와 current edge applicability projection을 구현한다.
8. KEdge RAG와 root-independent derivation_depth metadata를 가진 convergent K2K propagation을 구현한다.
9. evidence_mode/retrieval_strategy/epistemic_basis를 포함한 K2W Explanation/Recommendation을 구현한다.
10. 구조화 Decision W, event identity와 atomic automatic W2K를 구현한다.
11. decision trace를 구현한다.
12. W2P와 P2B를 CLI로 구현하고 review/provenance/job pause-resume/export까지 headless 사용자 흐름을 완결한다.
13. CLI release gate에서 실제 MinerU parsing, DB integration, 복구/보안/e2e를 검증한다. mock과 live 결과를 구분한다.
14. 위 단계가 완료된 뒤 GUI를 마지막 별도 작업으로 시작한다. GUI는 같은 application services를 재사용하며 CLI release의 선행 조건이 아니다.

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

이 구조에서 창의성은 K2K의 새로운 조합에서 나오고, 신뢰성은 Generator–Validator 분리, source-specific Information, Record/effect 원장, exact provenance, scoped fingerprint suppression, material-delta 검증, revision concurrency guard, edge applicability revalidation, root-independent derivation-depth 추적과 scope별 의무를 보존하는 convergent propagation에서 나온다.
