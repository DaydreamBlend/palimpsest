# Test_Paper subpanel → K 감사

2026-09-13. 사용자가 논문 Figure의 각 subpanel에 적어도 하나의 K가 필요하지 않은지, 현재 내용이 빈약하지 않은지 질문했다. Electron 첫 읽기 UI 구현에 이어 실제 저장 상태와 추출 정책을 읽기 전용으로 확인한다.

## 범위와 완료 동작

- 주 Figure/subpanel 목록과 현재 선택 source의 정확한 I/원문 참조를 확인한다.
- 실제 DB의 K와 Wiki 요약 항목·UI 관련 K·검색 index 수를 구별한다.
- 기존 I 전체 검토 계약이 subpanel별 의미 회수를 보장하는지 코드에서 확인한다.
- 강제 신규 K 수와 패널별 검토/근거 연결을 구분한 후속 설계를 보고한다.

이번 감사는 D2I, 모델 호출, K/Edge 생성, schema 변경을 실행하지 않는다. 사용자 질문을 패널마다 무조건 새 K를 만드는 규칙의 확정 승인으로 기록하지 않는다. 기존 I/원문/Revision을 변경하지 않는다.

## 읽은 계약과 현재 구현

PLANS, CODE_REVIEW, USER_OVERRIDES, INDEX, DECISION_REGISTER, T13의 Electron 착수 범위, FULL_SOURCE_LLM_SELECTION, I2K_SOURCE_ONLY_K2K_INFERENCE 및 이전 T04 실제 보고서를 읽었다. I2K의 전체 I 입력·LLM 중요성 선택, 같은 실험의 동일 의미 K 재사용, 다른 실험 분리, K2K만 새 추론이라는 경계를 유지한다. GUI 완료와 지식의 의미적 충분성을 혼동하지 않는다.

`selection_prompts.py`는 음성 결과·대조군·시간 비교를 빠뜨리지 않도록 지시하지만, `i2k_selection.py`의 exhaustive review 검사는 information_id 단위다. Figure caption의 각 panel label에 대한 별도 완료 계약은 없다.

## 작업 분담과 순서

1. source 감사: 보존된 Figure inventory, 현재 source packet과 exact caption/이미지 참조를 비교한다.
2. K 감사: 별도 wiki_pg에 read-only SQL을 사용해 32개 K와 grounding을 확인한다. 기존 source DB는 변경하지 않는다.
3. 루트 검토: 코드·기존 semantic review와 위 두 결과를 대조하고 설계 권고를 작성한다.
4. 생성한 감사 JSON의 구조·수·참조와 문서 링크를 검사한다. 의미적 회수율을 기계적 label match로 주장하지 않는다.

감사 산출물만 `output/t10-panel-coverage/`에 추가한다. 복구가 필요한 DB 효과는 없다. 기존 raw와 실패 기록을 삭제하지 않는다.

## 진행

- source inventory: 주 Figure 6개, label 46개 확인. parser crop 36개와 label 46개는 서로 다른 단위다.
- 실제 DB: Test_Paper K 32개(Observation 24, Proposition 8), 현재 선택 I 실행 grounding 보유 21개, 이전 실행 grounding만 보유 11개 확인.
- 의미 단위 한계: 기존 검토에서 24시간 neutrophil/apoptosis 대비가 충분히 회수되지 않았다고 기록했다. 모든 패널의 완전성 평가가 수행된 것은 아니다.
- [감사 결과](../output/t10-panel-coverage/REPORT.md)와 source/K별 JSON/Markdown을 작성했다. 이후 사용자가 모든 D/I/K로 일반화하도록 지시해 [공통 Runtime 구현](T04_source_review_execplan.md)으로 이어갔다. 감사와 구현의 검증 범위는 구분한다.

## 후속 구현의 경계

기존 I를 세분화하거나 다시 만들지 않고 I2K Runtime의 검토 의무로 패널별 evidence/review 참조를 추가하는 것이 최소 변경이다. 실제 적용 시 기존 profile/과거 Record를 보존하고 새 profile로 구분해야 한다. 신규 K의 수를 46개에 맞추는 목표나 모든 과거 결과를 재작성하는 목표는 아니다. 미검토 패널을 완료로 표시하지 않으며 같은 결과의 대표 이미지와 정량 그래프를 독립 실험으로 세지 않는다.
