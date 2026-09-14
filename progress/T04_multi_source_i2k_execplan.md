# T04 — 여러 Data의 I를 근거로 하는 K

2026-09-11 사용자 명확화: I2K의 한 후보는 I 1개 이상 → K 하나이며 서로 다른 D의 I를 함께 사용할 수 있다. 이번 범위는 계약/현재 제한 점검과 문서 반영이다. 사용자가 새 다중 논문 모델 실험을 요청한 것은 아니며 앱/DB migration을 이번 정책 검증으로 완료 처리하지 않는다.

## 입력과 범위

AGENTS, USER_OVERRIDES, INDEX, DECISION_REGISTER, T04, PLANS, CODE_REVIEW, canonical §13 I2K, MODULE_BOUNDARIES, FULL_SOURCE_LLM_SELECTION, LLM_WIKI_RETRIEVAL를 읽고 knowledge_runtime/_verify_i/prepare, i2k_selection, 0005/0006 SQL의 입력/grounding/scope 검증을 확인한다. 기존 전체 I 검토, 출처별 실험 보존, 추론 기원 표시, D2I 재실행 금지, Revision 불변성과 U/R 승인 범위를 유지한다. Ponytail의 기존 계약·모듈 재사용 원칙을 따른다.

기존 §13은 seed I + same-D I + corpus related I를 이미 허용한다. 현재 런타임은 단일 `data_id`/`source_execution_id` packet을 검증하고, 0005 input guard와 0006 scope/완료 guard도 단일 Data를 요구한다. `evidence` 배열과 grounding 관계는 여러 I를 지원하지만 실제 다중 Data 입력 실행 지원을 뜻하지 않는다.

## 작업 순서와 복구

1. 독립 read-only 계약 감사와 로컬 코드 검토로 제한 위치를 확인한다.
2. 여러 source 입력/후보별 근거, full-source review 의무, source scope/중복, I2K/K2K와 추론 표시의 관계를 최신 결정 문서에 기록한다.
3. AGENTS/색인/사용자 승인/현재 구현 안내와 T04/T07에 관련 지침을 연결한다. 현재 canonical slice와 설치 migration은 변경하지 않는다.
4. 문서 validator와 이전 오류 집합 비교, 변경 문서 diff 검토를 수행한다. 실제 PG/모델/다중 source 컴파일 검증은 수행하지 않는다.

기존 수정 문서 bytes는 `output/t04-multi-source-policy/before`의 `.snapshot`과 SHA manifest로 보존한다. 복구는 해당 문서만 되돌리며 앱/원본/DB/기존 검증 artifact는 유지한다.

## 완료 기준과 결과

정책/점검 완료. [새 다중 source 계약](../docs/decisions/MULTI_SOURCE_I2K.md)은 여러 I/여러 D → 한 K를 허용하면서 exact I → D 대응과 출처별 관측 보존을 유지한다. 단일 실행·실제 제공·후보 근거·전체 검토 범위를 구별한다. 같은 의미의 새 근거만으로 K/Revision을 늘리지 않는다. 다중 입력을 막는 현재 runtime/SQL 제약과 후속 acceptance를 명시했다.

독립 감사에서도 단일 Data prepare/input/scope/완료 guard의 제한을 확인했다. 다중 I의 새 도출이 I2K에서도 발생할 수 있어, 이전 “추론이면 K2K” 표현을 실제 operation과 도출 방식의 분리로 수정했다. I2K는 exact I 전제, K2K는 accepted KRevision/EffectiveEdge를 사용한다. 별개 실험 결과 병합 금지와 같은 의미 reuse는 유지한다.

변경 파일: 새 MULTI_SOURCE_I2K 결정 문서, AGENTS, INDEX, USER_OVERRIDES, DECISION_REGISTER, FULL_SOURCE_LLM_SELECTION, LLM_WIKI_RETRIEVAL, I2K_DIRECT_SOURCE_EVIDENCE, FULL_SOURCE_SELECTION, KNOWLEDGE_RUNTIME, DIKW_CURRENT, MODULE_BOUNDARIES, T04/T07. 기존 수정 문서 13개를 snapshot/SHA로 보존했다. 앱/DB migration·model profile·canonical slices는 변경하지 않았다.

실행 명령과 검증 결과는 [보고서](../output/t04-multi-source-policy/REPORT.md) 및 output verification JSON에 남긴다. 앱·PostgreSQL·모델 호출은 하지 않았으며 이번 정책 검증으로 T04/T07 앱 acceptance를 완료 처리하지 않는다.

독립 최종 검토의 권고에 따라 I 1개 이상 규칙을 일반 I 기반 후보에 적용하고, 직접 D 예외에서는 지원하지 않는 I grounding을 강제하지 않도록 명시했다. 승인/재사용 결과와 기각/보류를 구분했다. 최초 문서 검사에서는 아직 생성 전인 결과 artifact 링크 오류가 함께 나타났으며 결과 파일을 작성한 뒤 재검사한다. 최종 오류 집합과 초기 관찰은 검증 기록에 구분해 보존한다.
