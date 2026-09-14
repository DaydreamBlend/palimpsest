# K2K 첫 실행 단위 — 정확한 K 전제와 파생 provenance

후속 2026-09-14: 앱0.16/schema0016의 [중단·재개 전파](PROPAGATION_WORKER.md)는 exact K 전제 변경을 재검증하고 같은 Revision의 active support를 갱신한다. 최초 origin과 실제 소비한 현재 premise/support를 분리하며 후속 의무와 Wiki 검증까지 연결한다. [실제 결과](../../output/t16-propagation/REPORT.md)는 node-only 범위의 구현·PG·모델 검사이며 전체 T07의 대규모/의미적 진동 acceptance와 구분한다.

후속 2026-09-13: [자료 버전 코드 실험](../../output/t12-versioned-code/REPORT.md)에서 앱0.12/0013의 current/pinned version binding과 실제 Terra K2K 두 건을 검증했다. 아래의0.11·provider0회 상태는첫실행단위의당시결과다. 신규versioncontext는exactmetadata/전달목록을추가하고최초K생성version,추가support,현재headprojection을구분한다. K2Kprompt에는원문인용본문대신근거hash/위치를전달하며실제전제는acceptedK로한정한다. 과거전제/원문근거를새head로치환하지않고전체자동전파완료를주장하지않는다.

2026-09-13. 앱0.11.0, additive0011/0012의 **node-only K2K 실행 단위**를 구현했다. [I2K 원문 정리·K2K 새 결론](../decisions/I2K_SOURCE_ONLY_K2K_INFERENCE.md)과 [추론 기원·전제 보존](../decisions/LLM_WIKI_RETRIEVAL.md)을 적용한다. [실제 검사](../../output/t11-codebase-k2k/REPORT.md)는 합성 의미 판정을 사용한 PG 검증과 실제 코드 D/I 등록을 구별한다. 전체 T07 자동 scheduler·수렴 완료는 아니다.

## 입력·제안·검증

`knowledge inference-input --data-id <D> --node-revision-id <R1> --node-revision-id <R2> --json`은 실제 current accepted KRevision 두 개 이상을 고정한다. 한 논리 K의 여러 Revision을 독립 전제로 세지 않는다. 이번 profile은 KEdge를 입력·출력으로 소비하지 않는다. operational Data는 실제 전제의 transitive source provenance 안에 있어야 한다.

`knowledge prepare --operation k2k ...`는 이 입력을 다시 DB에서 확인하고 `knowledge-inference-v1`/`k2k-input-v1`으로 저장한다. 준비 후 graph read-set이 바뀌거나 전제/원 전제 계보가 stale하면 반영을 거부한다. Generator/Validator receipt는 실제 exact KRevision 전달 목록과 prompt/schema/input/output hash에 결속하며 서로 다른 provider 세션이어야 한다.

Generator는 Proposition만 제안한다. candidate_key, statement, semantic_payload, identity scope, 정확한 premise_revision_ids, inductive/deductive 유형, assumptions, limitations, 간결한 derivation_basis를 반환한다. 직접 I citation·Observation·KEdge·임의 canonical ID/origin/depth는 받지 않는다. 코드의 선언·주석이나 테스트 정의를 실제 실행 결과로 바꾸지 않는다.

독립 Validator는 각 후보의 inference_valid, premises_sufficient, limits_preserved, novel_conclusion을 확인한다. 신규 accepted는 네 항목 모두 true가 필요하다. 같은 의미 reuse는 novel_conclusion=false일 수 있지만 나머지 검증과 실제 기존 Revision 연결이 필요하다. 단순 원문 정리/병치는 새 추론으로 승인하지 않도록 지시한다. `complete=false`의 유효한 판정은 저장하되 전체 실행은 보류할 수 있다.

## 저장과 기원

기존 KnowledgeRuntime의 profile·Record·짧은 transaction·identity/reuse·outbox를 재사용한다. 새 `canonical_store.knowledge_derivations`와 `knowledge_derivation_premises`는 actual Compiler Record, 결과 KRevision, 추론/검증 metadata와 ordered exact premise Revision을 저장한다. provider가 선언한 기원 flag를 믿는 방식이 아니다.

- 실제 origin Record가 K2K인 새 Revision은 `origin_operation=k2k`, `is_inferred=true`로 조회한다.
- 기존 source-created K를 재사용하면 최초 origin을 유지하고 추가 도출 이력만 붙인다.
- 기존 inferred K에 후속 원문 근거를 더해도 최초 K2K origin을 바꾸지 않는다.
- depth는 `1 + max(전제의 immutable origin depth)`로 application/DB가 계산·검사하며 성공 종료 cap으로 쓰지 않는다.
- 파생 K의 직접 I grounding을 만들지 않는다. 전제 Revision을 거쳐 `transitive_source_refs`로 실제 I/D에 도달한다.

SQL은 실제 staged candidate와 inference metadata/validation/candidate key를 확인한다. 후보 내용이 삭제된 뒤에도 전체 전제 목록을 검사할 수 있도록 validation에 DB 소유 `_premise_revision_ids` witness를 보존한다. 실제 premise 행·순서·depth·결과/Record·scope·N2E outbox가 함께 commit되어야 한다. 전제 일부 누락, 자기 참조/재사용 순환, 잘못된 depth, 직접 I 근거 위조와 완료 후 이력 변경·추가는 거부한다.

신규 K 수·표현 차이로 semantic Revision을 늘리지 않는다. 기존 K의 material semantic revision을 일반적으로 수정하는 작업은 이번 실행기에 추가하지 않았다. 새 accepted K의 후속 N2E 의무는 남기며 `generates` 같은 semantic Edge를 도출 이력 대신 자동 생성하지 않는다.

## 조회와 현재성의 한계

`knowledge show`는 실행별 derivations/premise IDs를, `knowledge graph`는 derived node의 기원·depth·direct_groundings·transitive_source_refs·도출 이력을 반환한다. Data별 graph에도 전이된 source provenance를 가진 파생 K가 포함된다. raw node_revisions의 저장 내용은 변경하지 않는다.

원 전제 계보가 바뀌면 기존 origin derivation을 보존하면서 `needs_revalidation`으로 노출하고 새 K2K 입력 사용을 보류한다. **이번에는 별도 dependency revalidation 실행기를 구현하지 않았다.** 나중에 다른 support를 추가했다는 이유만으로 원 도출의 현재성을 자동 회복시키지 않는다. 전체 current-evidence 판정·전파를 완료한 것으로 해석하지 않는다.

Wiki/RAG의 기존 직접-I 기반 projection은 이번 새 transitive provenance 전체를 아직 색인하지 않는다. 기존 Wiki 링크에 가짜 direct I grounding을 끼워 넣지 않았다. 첫 완료 기준은 K2K Runtime/DB/graph CLI이며 GUI와 전체 retrieval 지원은 별도 후속이다.

## Migration·검사·실험 구분

0001–0010을 보존하고0011을 추가했다. 최초 전체 검사에서 공유 revision trigger가 Edge에도 Node 전용 필드를 읽는 회귀가 발견돼, 설치된0011도 보존한 채0012에서 분기를 고쳤다. 수정 후 기존 N2E와 새 K2K를 포함한 전체 suite가 통과했다.

원래 논문/Wiki DB는 migrate하지 않았다. 적용 대상은 기존 격리 fixture와 새 `palimpsest_codebase_k2k` DB다. 코드 원문은 [Markdown snapshot](CODEBASE_SNAPSHOT.md)으로 D/I 등록했으며 실제 코드 기반 K나 새 결론을 모델로 생성한 상태는 아니다. 현재 실제 코드 DB의 K/derivation은0개이고 I2K가 prepared_not_delivered 상태다.

`tools/prepare_inference_call.py`는 실제 K2K Runtime context의 요청 JSON을 준비하고, 기존 `run_knowledge_model.py`는 승인된 호출에서 exact K 전달 receipt를 전달한다. 이번 결과에서 실제 provider 호출은0회다. 합성 fixture의 accepted 판정은 추론의 과학적·논리적 품질을 검증한 live 모델 결과가 아니다.
