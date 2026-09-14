# T04 — D2I 재실행 금지와 Wiki 근거 경로 점검

2026-09-11 사용자 후속 지시. I2K의 근거 공백 때문에 D2I를 재실행하지 않는다. 기존 I에서 충분한 근거를 찾지 못하면 등록 원본 D에서 확인하고 직접 D 근거와 누락/불일치 이력을 남기는 정책을 적용한다. 사용자는 여러 논문에서 SuperMApo 제작 방법을 K → I → D로 찾는 LLM Wiki 구조의 가능성도 질문했다. 작업 중 이어진 지시로 K 사전 생성/I embedding/D 조회의 계층, K2K의 귀납·연역 지식 생성, 추론 생성 K의 필수 기원 metadata를 함께 문서화했다.

## 범위와 완료 동작

이번 작업은 최신 정책을 저장하고 충돌하는 현재 작업 지침을 바로잡으며, 실제 저장 graph의 역추적 경로와 미구현 기능을 확인한다. 새로운 논문이나 모델 실행을 요청한 것으로 확대하지 않는다. 원본 직접 근거의 canonical 저장/모델 전달, 자연어 검색·답변 생성은 현재 상태와 필요한 후속 구현으로 구분한다. D2I, source 재조립, K/I/Revision/DB migration 변경은 수행하지 않는다.

## 확인한 근거와 현재 구현

- 읽음: AGENTS, PLANS, CODE_REVIEW, USER_OVERRIDES, INDEX, DECISION_REGISTER, T04/T11, FULL_SOURCE_LLM_SELECTION, I2K_I_FIRST_SOURCE_ON_DEMAND, KNOWLEDGE_RUNTIME, T04_INPUT, FULL_SOURCE_SELECTION, RETRIEVAL_PROFILE.
- `knowledge_runtime.py`는 원본 요청을 durable `k_source_requests`에 저장하지만 현재 provider의 `native_pdf_unsupported` 때문에 unavailable로 기록하고 관련 후보를 보류한다. D2I 호출 경로는 없다.
- `knowledge_node_groundings`는 exact I FK/quote/media 기반이다. 직접 D grounding이나 원본 전달·사용·검증의 완성된 원장은 없다. 기존 완료 migration을 수정하지 않는다.
- 현재 구현된 source 조회와 graph를 이용한다. BGE-M3 검색 adapter/index와 자연어 질의·K2W 답변 runtime은 미구현이다.
- U01–U11/R07/R08와 전체 I 선택·source scope·Revision 원칙을 유지한다. 새 지시는 이전 I-first 문서의 D2I 보완 요구에만 우선하며 미승인 P 범위를 확대하지 않는다.
- Ponytail의 기존 경로 재사용 원칙을 적용한다. 별도 검색 framework나 사용되지 않는 schema scaffolding을 추가하지 않는다.

## 작업 순서

1. 모델 요청/grounding 코드와 활성 문서의 충돌을 read-only로 감사한다. 독립 검토자는 실제 SuperMApo K/I 경로와 구현 한계를 조사한다.
2. 최신 결정 문서와 해당 작업/구현/색인 안내를 수정한다. 정확 원본 전달과 직접 D 근거 저장의 acceptance를 명시한다.
3. 보존된 graph와 I snapshot, 가능하면 현재 PostgreSQL의 읽기 CLI로 제작 K의 exact Revision → I 문자 범위 → D 페이지/영역 연결을 확인한다. 이를 실제 의미 검색 성능으로 보고하지 않는다.
4. 문서 validator의 오류 집합을 기존 12개와 비교하고 변경 파일을 검토한다. 코드 변경이 없으므로 앱 회귀/LLM 시험을 새로 수행한 것으로 보고하지 않는다.

## 검증과 결과

정책 반영과 실제 저장 근거 점검 완료. [보고서](../output/t04-direct-source-policy/REPORT.md)에 재현 명령을 기록했다. `verify_wiki_trace.py`를 현재 app image의 읽기 API로 실행해 exact KRevision → 역사 I substring → 원본 10페이지를 검증했다. 같은 그룹에서 mouse 문맥 10페이지와 human 문맥 12페이지를 구별했다. 선택 source는 36 I, graph는 32 K/26 Edge. DB 전체 I 287, execution 16, NodeRevision 32, EdgeRevision 26과 graph 내용이 전후 동일하다. D2I/LLM/canonical 쓰기 0. 이 조회는 실제 semantic retrieval 또는 K2K 검증이 아니다.

문서 validator는 exit 1이며 보존된 raw Markdown의 기존 12개 오류가 남는다. 오류 집합 비교와 diff 검토는 output 검증 결과에 기록한다. 앱 코드·schema 변경이 없으므로 앱 회귀·live 모델 호출은 재실행하지 않았다. 문서 링크/정책 검증을 T04/T07의 앱 acceptance 통과로 보고하지 않는다.

활성 문서에서 근거 공백을 D2I 보완으로 처리하던 세 곳을 수정했다. 두 새 결정 문서, AGENTS, INDEX, USER_OVERRIDES, DECISION_REGISTER, I-first/FULL_SOURCE_LLM_SELECTION, T04_INPUT, KNOWLEDGE_RUNTIME, FULL_SOURCE_SELECTION, DIKW_CURRENT, I2K_CONTEXT_POLICY, T04/T07 작업서에 최신 요구/상태를 반영했다. 설치된 canonical snapshot과 migration은 수정하지 않았다. 기존 문서 13개는 변경 전 bytes/SHA를 보존했다.

도구 점검 중 Windows에서 `rg ... tasks/T*.md` wildcard 전달이 오류 123을 반환했다. `rg ... tasks -g 'T*.md'`로 다시 읽어 확인했으며 앱 오류가 아니다. source 디렉터리에서 K2K/retrieval 관련 파일명 검색의 결과 없음도 구현 미존재 관찰로 구분했다.

독립 문서 검토에서 이전 명칭 `retrieval_mode` 대신 현재 U08/R09의 `evidence_mode`를 쓰도록 바로잡았고, 직접 D 근거 문서에도 K2K의 전제 Revision을 통한 역추적 경로를 명시했다. 네 사용자 요구 반영과 실제 구현 상태 구분을 확인했다.

## 복구와 다음 경계

변경 전 문서 bytes는 작업 output의 `.snapshot` 파일과 SHA manifest로 보존한다. 원상 복구는 그 문서만 복구하며 canonical source slices, 앱/DB/모델 profile은 변경하지 않는다. 직접 D grounding은 추가 migration과 delivery/verification 증거를 함께 구현해야 한다. 그 전에 I 없는 근거를 기존 I에 억지로 연결하거나 미제공 원본을 읽었다고 기록하지 않는다.
