# LLM Wiki의 D/I/K 계층 검색

2026-09-12 제품 목표 명확화: 핵심은 입력 자료를 자동 분류해 일정한 형식의 백과사전 페이지를 작성·갱신하는 Wiki다. I 검색과 K 조회는 이 자동 편집·탐색을 뒷받침한다. 문서 형식은 D/I/K의 분리만으로 고정되지 않으므로 별도 page schema/renderer가 필요하다는 [설계 제안](../../progress/AUTOMATIC_WIKI_DESIGN.md)을 기록했다. 인터넷 자동 수집·웹 게시와 개인 생각·결정도 최종 목표이며, 이 후속 문장이 기존 보존·추론·authority 경계나 미실행 GUI/수집을 완료로 바꾸지는 않는다.

2026-09-11 후속 명확화: 사용자는 Palimpsest를 더 엄격하게 규격화한 LLM Wiki로 보고, **I가 환각 대조를 위한 안전장치이자 semantic search의 대상**임을 강조했다. I를 LLM이 작성한 wiki 요약으로 대체하지 않으며, K가 선택하지 않은 내용도 원문 I에서 검색한다. I의 존재만으로 의미적 정확성이 보장되는 것은 아니므로 exact 인용과 주장 지지를 별도로 검사하고 필요하면 D로 내려간다. K 통합은 필수가 아니다. 외부 구현은 [참조 조사](../../output/t04-llm-wiki-references/REPORT.md)에 기록했으며 그곳의 적용 제안은 기능 도입·새 schema 승인이나 구현 완료를 뜻하지 않는다.

2026-09-11 최신 정정: [I2K 원문 정리·새 결론은 K2K](I2K_SOURCE_ONLY_K2K_INFERENCE.md)를 적용한다. [여러 D의 I 1개 이상 → K 하나](MULTI_SOURCE_I2K.md)는 원문에 명시된 내용의 통합·재사용이며 I2K의 새 추론을 허용하지 않는다. 새 I2K-origin Revision은 `is_inferred=false`다. 단일 Data 구현의 확장과 실제 다중 Data 실험은 [실행 계획](../../progress/T04_multi_source_runtime_execplan.md)에서 확인한다.

2026-09-11 사용자 후속 지시. 이 프로젝트의 D/I/K는 RAG의 계층이다. LLM이 자주 사용할 것 같은 내용을 미리 K로 정리하고, 더 드문 내용은 I embedding 검색으로 찾으며, 그래도 충분하지 않으면 D 원본을 확인한다. 이어 사용자는 **K2K가 귀납·연역으로 새로운 지식을 만들 수 있고, I는 D2I로만 만들어지는 원문 표현**임을 명시했다. 이 해석은 [전체 I의 LLM 선택](FULL_SOURCE_LLM_SELECTION.md)과 [D2I 재실행 없는 원본 근거](I2K_DIRECT_SOURCE_EVIDENCE.md)를 함께 적용한다.

## 각 계층의 책임

| 계층 | 보존 내용과 역할 | 조회 시 역할 |
|---|---|---|
| D | 도구로 등록한 원본 bytes와 acquisition provenance. 동일 bytes의 Data 중복 등록 거부 | I로 충분히 확인되지 않는 근거를 원본에서 최종 확인 |
| I | 원문 내용을 충실하게 보존한 그룹과 text/image·정확 source 위치 | K에 미리 선택되지 않은 세부 사항까지 embedding 검색하고 관련 문맥 읽기 |
| K | I2K가 선택·검증한 지식과 K2K가 기존 K로부터 귀납·연역한 새 지식, N2E로 검증한 관계 | 직접 정리된 지식과 추론 지식을 조회하고, 전제 K 및 I/D로 근거 역추적 |

I2K가 전체 I를 검토한다는 것은 모든 내용을 K로 복사한다는 뜻이 아니다. LLM은 K 선택/문맥 사용/미선택/검토 필요와 이유를 각 I에 남긴다. 미선택 I도 보존·검색한다. 예상 활용도는 LLM 판단이며 실제 사용 빈도가 측정되었다고 주장하지 않는다. 스크립트의 빈도/길이 임계값으로 K 중요성을 대신 결정하지 않는다.

K는 짧은 답변 캐시나 원문 전체의 대체물이 아니다. 기존 general/source scope, 의미 동등성 재사용, material Revision, exact 근거와 N2E 계약을 유지한다. 같은 뜻의 반복에서 K를 늘리지 않으며 서로 다른 D의 실험 결과는 구분한다. source 수나 D/I의 중복 표현을 독립적인 근거 수로 부풀리지 않는다.

## K2K의 지식 생성

I는 D2I가 보존한 원문 표현이다. 원문에 보고된 주장이나 추론 문장을 담을 수 있지만 시스템이 새로 추론한 내용을 I로 저장하지 않는다. 그룹/조회 projection, embedding, 원본 조회용 rendering도 새로운 의미를 I에 추가하는 경로가 아니다.

K는 두 생성 경로를 모두 갖는다. I2K는 원문에 근거한 지식을 선택·구조화하며, K2K는 accepted/current-applicable KNodeRevision과 KEdge의 정확한 effective refs를 전제로 새로운 K 후보를 만든다. 원문에 결론 문장이 그대로 없더라도 전제와 추론이 타당하면 파생 K가 될 수 있다. 이를 가짜 I 인용으로 원문에 직접 쓰인 지식처럼 만들지 않는다.

| 추론 | 생성하는 지식 | 검증에 필요한 것 |
|---|---|---|
| 연역 | 명시한 전제·규칙·가정이 성립할 때 따라오는 결론 | 전제의 정확 Revision, 적용한 규칙, 조건·범위의 일치, 논리적 비약 여부 |
| 귀납 | 여러 관측·결과로부터 얻은 조건부 일반화 또는 가설 | 전제의 출처/조건과 독립성, 반례·상충 결과, 일반화 범위와 불확실성 |

두 경우 모두 구조화 제안과 독립 Validator 검증을 거쳐 canonical K로 반영한다. 연역도 전제가 경험적·불확실하면 그 전제의 한계를 지우지 않으며, 귀납을 보편적 확정 사실이나 새로운 Observation으로 위장하지 않는다. 단순한 `supports` edge 연결은 논리적 함의의 증명이 아니므로 연결 경로만으로 연역을 승인하지 않는다. K2K가 실제 관측·실험 수행이나 사용자의 결정을 만들어내지 않는 기존 kind 경계를 유지한다.

K2K의 파생 K에는 origin K2KRecord, 실제 사용한 전제 KNodeRevision/EffectiveEdgeRef, 추론 유형, 명시적 가정·한계, 간결한 도출 근거와 Validator 결과를 남긴다. 전제에서 기존 I grounding 또는 직접 D grounding으로 이어지는 transitive provenance를 조회할 수 있어야 한다. 이는 검토 가능한 논거와 입력 의존성의 기록이며 모델의 내부 사고과정을 저장하라는 요구가 아니다.

사용자의 추가 지시에 따라 **추론으로 생성된 K라는 표시는 필수**다. KNodeRevision의 immutable 생성 기원과 실제 생성·검증 Record에 구조화해서 저장하고, CLI/검색/답변의 K 표현에도 노출한다. 신규 I2K 결과는 원문 정리로, 새로운 추론 결과는 K2K의 accepted K 전제와 연결한다. 실제 Record의 operation과 해당 경계의 검증을 확인하며 모델이 임의로 추론 flag를 붙였다고 I2K 새 결론을 허용하지 않는다. 실제 물리 schema/조회 projection은 해당 T04/T07 구현에서 추가하되 다음 조회 의미를 충족해야 한다.

| 필수 정보 | 저장·조회 의미 |
|---|---|
| `origin_operation` | 해당 Revision을 생성한 실제 operation. 명시 원문 정리는 `i2k`, accepted K 전제의 새 결론은 `k2k` |
| `is_inferred` | 새 I2K-origin Revision은 `false`, K2K가 새로 도출한 Revision은 `true`. 실제 origin Record와 허용된 생성 경계에서 산출하며 재사용·추가 근거로 덮어쓰지 않음 |
| `inference_type` | K2K 추론의 `inductive` 또는 `deductive`. 검증되지 않은 유형을 임의 확정하지 않으며 신규 I2K에는 적용하지 않음 |
| `origin_record_id` / premise refs | 생성·검증 Record와 실제 전제를 연결. I2K는 exact I/source 근거, K2K는 KNodeRevision/실제 EffectiveEdgeRef |
| assumptions / limits / validation | 명시적 가정, 적용 범위·불확실성, 간결한 논거와 검증 결과 |

`is_inferred`는 최초 생성 경로의 표시이며 참/거짓 또는 신뢰 점수가 아니다. 귀납·연역을 섞은 도출에서 임의로 한 유형을 단정하지 말고 실제 도출 단계와 각 유형을 구분하는 구조를 후속 계약에서 검증한다. 분류 불명확성을 숨겨 승인하지 않는다.

추론으로 생성된 Revision에 나중에 원문 I/D 근거가 추가돼도 기존 `origin_operation`/`is_inferred`와 추론 이력을 바꾸지 않는다. 반대로 직접 원문 정리로 생성된 기존 K를 새로운 추론이 뒷받침하면 최초 생성 기원은 유지하고 추가 K2K 근거/Record를 연결한다. 생성 기원과 현재 근거 종류는 별개이며 근거가 혼합될 수 있다. 기원 metadata나 동일 의미의 근거 추가를 이유로 semantic Revision을 늘리지 않는다. 논문 저자가 보고한 추론을 I2K로 정리한 경우와 시스템 자체가 K2K에서 새로 도출한 경우를 구별한다.

전제 Revision이나 사용한 관계의 적용성이 바뀌면 정확 dependency를 따라 관련 파생 K를 재검증한다. 과거 파생 K와 당시 전제는 그대로 보존한다. 같은 결론에 새 근거나 다른 도출 경로가 생겼으면 기존 K를 재사용하고 도출/근거 기록을 추가하며, 의미가 실질적으로 바뀌었을 때만 Revision을 만든다. origin과 general/source 의미 scope는 별개이며, 서로 다른 D를 종합한 결론을 가짜 단일 실험 결과로 저장하지 않는다. 그 결론의 범위와 실제 모든 전제를 유지한다.

K2K의 입력/도출 관계는 Compiler Record의 의존성이다. 자동으로 `generates` semantic Edge를 만들지 않는다. 새 K가 승인되면 N2E가 다른 K와의 의미 관계를 별도로 제안·검증한다. 기존 scheduler를 통한 후속 K2K에서는 의미 변화가 없는 가지를 종료하고, depth/비용/개수 상한으로 미해결 전파를 성공 완료 처리하지 않는다. 순환 참조나 같은 근거의 재서술을 독립 증거 증가로 취급하지 않는다.

이 규칙은 [기존 K2K 의미 계약](../canonical/06_knowledge_operations.md)과 [모듈 경계](../implementation/MODULE_BOUNDARIES.md)를 구체화한다. 현재 I 기반 저장 slice가 모든 새 K에 direct I grounding을 요구하는 제약은 K2K까지 그대로 확대할 수 없다. 후속 구현은 direct I, direct D, 전제 K를 통한 derived provenance를 구별해 검증해야 하며 K2K 때문에 새 I를 만들지 않는다.

## 질의의 진행

1. 질문과 맥락에 맞는 K를 조회한다. 관련 K의 정확 Revision, 실제 사용할 수 있는 Edge와 근거를 가져온다. 충분한 경우 원문 인용을 갖춘 답변을 구성한다. 이미 찾은 K에 직접 연결된 I를 확인하는 것은 의미 검색 실패 여부와 무관한 provenance 조회다.
2. K만으로 부족하면 I embedding 검색을 수행한다. K에 연결된 출처가 있으면 같은 D의 방법·조건·인접 문단을 우선 읽고 다른 D의 관련·상충 근거도 찾을 수 있어야 한다. K를 전혀 못 찾았어도 corpus I 검색으로 진입한다. BGE-M3 embedding/동일 모델 multi-vector reranking 기본값과 교체 가능한 profile을 유지한다.
3. I와 추가 문맥에서도 부족하거나 전사가 의심되면 등록 원본 D로 내려간다. 실제 원본 hash·위치·모델에 제공된 증거를 결속하며, 원본에서도 찾지 못하면 답을 만들지 않고 확인되지 않은 항목으로 남긴다. 이 조회는 D2I 실행이나 새로운 I 저장을 유발하지 않는다.

단계 이동의 기준은 답에 필요한 주장·조건·인용이 충분한지에 대한 판단이다. 유사도 한 개나 높은 검색 점수만으로 근거 충분성을 확정하지 않는다. K 검색 실패는 드문 내용에 대한 정상 동작이며 I 검색 실패도 즉시 D2I 누락을 뜻하지 않는다. D에서 확인한 후 실제 누락·전사 불일치·검색 실패·원래 없는 정보를 구별한다. 검색 실패로 D를 확인한 경로는 조회 이력에 남기고, 확인된 source 문제는 오류/품질 이력으로 남긴다.

## 답변, K 저장, Revision

I에서 찾은 내용을 답변에 사용할 수 있다. 이때 검증된 K 기반 부분과 원문 I를 직접 읽은 부분을 `evidence_mode`/`epistemic_basis`와 실제 인용으로 구분하는 기존 K2W 계약을 따른다. D 직접 읽기도 직접 source 근거임을 표시한다. 읽은 I/D가 있다는 이유로 K가 자동으로 승인되는 것은 아니다.

명시적으로 `knowledge_only`를 요청하면 I/D 근거로 조용히 확장하지 않는다. 일반 계층 조회는 evidence를 허용하는 mode로 기록하며 `standard/decision_trace/history` 조회 전략과 구별한다. 기존 K/I 중심 `epistemic_basis`와 used-ref 계약에는 직접 D 및 혼합 근거의 typed 표현을 추가해야 한다. 기존 canonical snapshot을 독립적으로 고쳐 설치된 계약처럼 보이게 하지 않는다.

조회 중 발견한 유용한 내용은 후속 I2K의 후보가 될 수 있다. K로 반영하려면 기존 구조화 제안·독립 검증·의미 중복 판정·atomic commit을 거친다. 단순 조회가 기존 K/I를 덮어쓰거나 원문에 없는 근거를 만들지 않는다. 직접 D 근거가 필요한 I2K는 [원본 예외 계약](I2K_DIRECT_SOURCE_EVIDENCE.md)을 따른다.

답변에는 실제 사용한 K/Edge Revision, 각 I/source 실행·범위, 각 D SHA·원문 위치, 검색 profile 및 실제 모델 입력·인용을 결속한다. 하나의 K에 여러 D의 I가 연결돼도 모든 근거를 유지한다. 같은 질문의 과거 답변과 결정 이유를 현재 K 상태로 덮어쓰지 않는다. Explanation 답변을 별도의 권위 확인 없이 Decision으로 승격하지 않는다.

## SuperMApo 사례

제작 관련 K를 찾은 뒤 exact grounding I와 같은 D의 충분한 Methods 문맥을 읽으면 논문에 보고된 방법을 설명할 수 있는 구조다. K가 제작 조건을 충분히 담지 않았으면 I 검색·문맥 조회로 보완하며, 모든 절차를 미리 K로 만들 필요는 없다. 같은 I에 mouse/human 실험이나 제조/투여 설명이 함께 있을 수 있으므로 실제 실험 조건과 source 구간을 구별한다.

문헌만 등록되어 있으면 답변은 문헌에 보고된 방법에 귀속한다. 개인 실험 수행 여부는 사용자의 실험 기록 D로 확인해야 한다. 파일 등록 행위자를 실험 수행자로 해석하지 않는다.

## 현재 상태와 후속 구현 순서

현재 저장된 Test_Paper는 선택된 source의 36 I, 32 KNode, 26 KEdge와 각각의 Revision·근거를 갖는다. [실행 결과](../../output/t04-full-selection/REPORT.md)는 한 문서의 실제 I2K/N2E 및 PostgreSQL 검증이다. 현재 K → I → D의 명시적 ID 조회는 가능하다. K2K 귀납/연역 실행·전파, BGE-M3 실행 adapter·I/K 검색 index·자연어 질문의 단계 이동·K2W 답변/이력 저장은 아직 미구현이다.

다음 구현은 (1) I2K 직접 D 근거·전달·오류 원장 및 K2K의 전제 Revision 의존성을 구분하는 저장 계약, (2) exact I/Revision·profile에 결속한 BGE-M3 검색과 재색인, (3) N2E/applicability 선행 조건을 충족한 K2K 생성·검증·전파, (4) K → I → D 질의 실행과 문맥 확장, (5) 인용과 Revision을 보존하는 답변 기록으로 분리한다. 이는 작업 경계이며 모두 이번에 구현되었다는 뜻이 아니다. 이미 구현된 조회·compiler·identity 기능을 재사용하며 별도 D2K 도메인이나 GUI를 먼저 만들지 않는다.

후속 검색 평가에는 K만으로 답하는 질의, K에 없지만 I에 있는 질의, 직접 D 확인이 필요한 질의, 어느 층에도 근거가 없는 질의, 여러 논문의 서로 다른 실험 조건, 과거 Revision 재현을 포함한다. 이번 설계 반영을 이 평가나 검색 성능 통과로 보고하지 않는다.
