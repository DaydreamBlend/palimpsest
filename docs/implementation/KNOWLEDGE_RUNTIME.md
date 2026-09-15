# Test_Paper 지식 생성 실행 범위

2026-09-14 N2E 후속: 현재 P/O의 supports·contradicts·qualifies·composes, exact target revalidation, 의미 개정/endpoint rebasing, 독립 판정과 effective graph는 [N2E 계약](../interfaces/N2E_RELATIONS.md)을 따른다. 앱0.19의 새 프로필과 추가0017–0019를 사용하며 아래 첫 supports-only 실행과 그 원문·Revision·receipt는 보존한다. [실제 검사/모델 결과](../../output/t20-n2e-completion/REPORT.md).

2026-09-11 최신 상태: [다중 Data Runtime](MULTI_SOURCE_RUNTIME.md)의 입력·저장 코드는 구현되어 격리 PG 검사를 통과했다. [I2K 원문 정리·새 결론은 K2K](../decisions/I2K_SOURCE_ONLY_K2K_INFERENCE.md)를 따르며 신규 I2K-origin Revision은 `is_inferred=false`다. 실제 세 논문 의미 실험은 첫 모델 실행 오류 이후 진행 중이며 기존 보존 DB의 0007 설치는 승인 대기다. 아래 첫 slice의 설명과 현재 다중 Data 구현·의미 실험 상태를 구분하며 [실행 계획](../../progress/T04_multi_source_runtime_execplan.md)을 확인한다.

2026-09-11 최신 지시: [LLM Wiki 계층 검색](../decisions/LLM_WIKI_RETRIEVAL.md)은 미리 선택한 K → I embedding 검색 → D 확인 순서다. [원문 근거 공백](../decisions/I2K_DIRECT_SOURCE_EVIDENCE.md) 때문에 D2I를 재호출하지 않는다. 아래 I 기반 grounding/원본 요청 보류는 현재 구현이며, 직접 D grounding과 실제 원본 전달·사용·검증의 후속 이벤트는 추가 구현해야 한다. 요청이 존재한다는 사실과 미해결 요청이 남았다는 사실을 그 구현에서 구별한다.

2026-09-11 사용자는 새 D2I 작업을 보류하고, 기존 Test_Paper의 I로 Terra Medium I2K와 N2E를 실제 실행하여 KNode/KEdge 및 각각의 Revision을 PostgreSQL에 저장하도록 요청했다. [실행 기록](../../progress/T04_knowledge_execplan.md)이 측정·통과·미완료 상태의 기준이다. T04/T06 전체 acceptance나 K2K 전파 완료를 뜻하지 않는다.

## 변환과 저장

`knowledge.py`는 proposition/observation의 구조화 후보, 정확 I 인용과 equality fingerprint를 검사한다. `n2e.py`는 accepted NodeRevision 사이의 supports 후보를 검사한다. `knowledge_prompts.py`는 이 첫 논문 profile의 생성·독립 검증 정책을 소유한다. `knowledge_runtime.py`가 기존 Compiler Runtime 실행/profile을 이용해 후보·판정·canonical 반영을 관리하며 CLI는 인자/결과를 전달한다.

I2K는 Node를 생성하고 독립 Validator가 근거·조건·의미 중복을 판정한 뒤 반영한다. 그 결과의 정확 NodeRevision을 N2E에 전달하여 Edge를 별도로 생성·검증한다. Abstract/Results/Figure는 grounding 역할이다. 같은 주장은 Node를 재사용하고 근거를 추가하며, 더 좁은 실험적 결론과 더 넓은 논문 결론이 실제로 다를 때만 구별한다. 그래프의 모양을 위해 중복 Node를 만들지 않는다.

새 `0005_knowledge`는 기존 Data/I와 migration을 보존하는 추가 설치다. `knowledge_nodes`/`knowledge_edges`의 논리 ID와 `knowledge_node_revisions`/`knowledge_edge_revisions`의 immutable Revision ID를 분리한다. EdgeRevision은 source/target NodeRevision과 그 소유 논리 Node를 복합 FK로 연결한다. current와 supersedes 참조 역시 같은 논리 객체의 Revision만 가리킨다. 새 opaque ID는 PostgreSQL UUIDv7이다.

Node grounding은 canonical I, 0-based half-open 문자 범위, exact quote, 선택적 media SHA와 역할을 가진다. I의 Data/page/bbox/raw/segment 근거는 I를 통해 이어진다. LLM이 보내는 UUID·FP·offset을 권위로 삼지 않고 Runtime이 검증·생성한다. 모델의 JSON 형식 준수는 의미 정확성 보장이 아니다.

최초 equality fingerprint는 자동 의미 판정기가 아니다. 이번 작은 graph는 모든 기존 current Node를 Validator에 제시해 표현 차이를 판정한다. BGE-M3 검색·profile별 index와 일반적인 material revision 제안/판정은 후속 범위다. 의미 Revision과 endpoint applicability는 별개다.

## 반영과 이력

모델 호출 전에 실행 입력·profile·K state version을 고정하고, 검증 때 후보와 입력의 context hash를 결속한다. 짧은 반영 transaction이 global K state를 잠그고 freshness를 재확인한다. 새로운 K/grounding·terminal Record·후보 cleanup·후속 outbox를 같은 transaction에서 반영한다. 이 global lock은 첫 graph의 단순한 동시성 경계이며 규모가 커져 충돌이 측정되면 세분화한다.

동일한 의미의 근거 추가는 Revision 증가가 아니다. 기존 Edge의 endpoint가 바뀌어도 과거 EdgeRevision endpoint를 덮어쓰지 않는다. 같은 관계 의미의 새 endpoint 조합에는 별도 applicability evidence가 필요하다. 새 조합의 검증이 없으면 pending이며, 이를 거짓 관계로 표시하거나 historical 관계를 현재 유효 관계처럼 내보내지 않는다.

기각 후보의 본문은 terminal 반영과 함께 Runtime 임시 후보에서 제거한다. durable Record는 fingerprint·disposition·판정 이유·result refs를 유지한다. 모델 호출 원장은 profile·입력/출력 hash·실제 전달 receipt·usage를 보존한다. 해결되지 않은 후보/원문 요청/후속 의무는 성공으로 지우지 않는다.

## 모델 입력과 CLI

현재 Generator와 Validator는 [로컬 GLM provider](MODEL_PROVIDER.md)를 사용한다. 모델·endpoint·context·sampling 설정은 profile과 receipt에 고정하고, 매 호출은 별도 provider response ID를 가진 독립 structured response다.

`tools/run_knowledge_model.py`는 준비한 prompt/schema와 hash가 검증된 I 이미지들을 실제 호출하고 metadata receipt를 만든다. 이 host worker에는 DB 권한이 없다. 최초 입력은 I text와 I media이며 원본 PDF/전체 페이지 이미지는 자동 첨부하지 않는다. 원문이 필요하면 정확한 I/page와 질문을 기록한다. 현재 CLI 이미지 입력은 원본 PDF 전달 기능이 아니므로 지원되지 않는 원본 요청을 처리했다고 기록하지 않는다.

`palim knowledge prepare --operation i2k|n2e --data-id SHA256 --request-id UUIDv7 --input input.json --json`은 실행 준비다. `knowledge stage EXECUTION --response generator.json`은 구조검사를 거쳐 후보를 저장하고 Validator context를 반환한다. `knowledge decide EXECUTION --response validator.json`이 판정을 atomic 반영한다. response 파일은 `response`와 실제 `receipt`를 포함하는 worker 교환 형식이다.

`knowledge show EXECUTION`, `knowledge validation-context EXECUTION`, `knowledge graph --data-id SHA256`은 상태/검증 입력/저장 graph 조회다. 실제 명령과 결과는 실행 기록에 보존한다. synthetic provider receipt를 쓴 DB 검사는 실제 semantic evaluation과 구별한다.
