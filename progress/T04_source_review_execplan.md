# 모든 D/I/K의 원문 구간·의미 항목 검토

2026-09-13 사용자 후속: “그 논문 하나에만 과적합되게 수정하지 말고, 전반적인 모든 D I K 사슬에 적용되게 해줘.” 앞선 [Test_Paper 감사](T04_panel_coverage_audit_execplan.md)는 구체적 문제 사례이며 새 기능의 적용 범위를 논문으로 제한하지 않는다.

## 목표와 경계

모든 새 전체-source I2K가 보존된 원문 주소의 목록과 그 내부의 LLM 의미 항목을 검토하고, 후보·실제 KRevision·미선택/보류 이유를 추적한다. 원문 D와 I snapshot은 유지한다. D2I 재실행/LLM 청킹/새 canonical I 행/임의 panel crop/새 과학적 추론은 없다. 동일 의미 K 재사용과 별개 실험 보존을 유지한다.

기존 source_refs/content_segments/media 주소를 재사용한다. 스크립트는 원문 주소와 소유권을 열거하고 LLM이 중요성·의미 단위를 판단한다. 큰 절/그림 하나의 주소가 하나의 claim이라고 가정하지 않는다. 같은 계약이 PDF, Markdown, HTML, 코드 등으로부터 생성된 I에 적용되지만, 아직 없는 형식별 D2I adapter가 구현됐다는 뜻은 아니다.

## 구현 경로와 소유권

- `source_review.py`: 순수 manifest/schema/검토 검증. 형식 이름·논문 ID·Figure 수 하드코딩 없음.
- `knowledge_requests.py`: Runtime과 provider request 도구가 공유하는 실제 prompt/schema. 원문 목록과 Generator/Validator 의미 검토 계약.
- `knowledge_runtime.py`: frozen input/profile, Generator/Validator receipt, 기존 atomic K commit에 exact 결과 refs 저장. 기존 JSONB를 사용해 migration 없음.
- `prepare_selection_call.py`: 동일 request builder 사용.
- 새 순수 단위 검사와 별도 PG fixture 통합 검사. 이전 selection/multi tests는 explicit legacy 옵션으로 당시 계약 보존을 계속 검사한다.

## 실행 순서와 복구

1. Test_Paper source/K read-only 감사 완료: source46label와 K32/UI21의 차이를 확인.
2. 범용 manifest와 source_reviews/독립 validation 구현 중.
3. 새 실행 기본 적용, 기존 request replay와 과거 profile/FP/Revision 보존.
4. PDF/Markdown/HTML/code 형태의 source contract 단위 검사 및 실제 격리 PG 원자성/재사용/보류 검사.
5. 실제 기존 PDF·Markdown·HTML 준비 산출물로 읽기 전용 manifest 검증, 전체 앱 suite, 새 Docker 이미지 검증.
6. 결과·한계·실행 명령을 `output/t10-source-review/REPORT.md`에 기록.

복구는 새 이미지 사용을 중지하고 보존된0.9.0 이미지를 쓰면 된다. 기존 source DB·wiki_pg·원본 artifact·기존 migration은 변경하지 않는다. 테스트는 `palimpsest-multi-checks` 기본 fixture DB에만 쓰고 사용자 논문 DB를 fixture로 쓰지 않는다. 새 실패 산출물과 감사 기록은 보존한다.

## 검증해야 할 실제 조건

- target 누락/중복, 잘못된 anchor·다른 Data/I/media 소유권은 구조 오류.
- selected 의미 항목은 해당 근거를 사용하는 후보에 연결.
- Validator가 원래 target의 내부 누락을 지적하면 외부 complete=true여도 성공 완료 금지.
- 독립 검증된 K 반영과 전체 검토 미완료는 구분.
- Validator 판정·canonical 결과·exact KRevision 연결은 같은 transaction으로 저장/rollback.
- 재사용은 새 의미 Revision을 만들지 않으며 새 review에서 기존 exact Revision으로 연결.
- request replay는 원래 profile/manifest를 유지. 기존 완료 이력을 새 규칙으로 재채점하지 않음.

실제 LLM의 의미 분할/회수율 평가는 이번 구조·DB 검사와 구별한다. Test_Paper46은 회수율 분모나 모든 문서의 고정 요구 수가 아니다.

## 현재 실행 상태

구현 완료. 새 `palimpsest-source-review:0.10.0` 이미지에서 전체669 tests 중653 pass/16 skip, 실패0, 134.631초, exit0을 확인했다. 새 순수 검사10개와 실제 격리 PG 검사10개를 포함한다. 실제 LLM semantic 평가는 수행하지 않았다.

세 PDF와 실제 기존 Markdown packet은 모두 원문 주소 manifest를 만들 수 있었으며 합친 네 Data의 I111개/target576개가 소유권을 보존했다. source packet bytes/digest와 반복 manifest hash가 동일했다. 후보가 source item에서 빠질 수 있던 초기 역방향 연결 허점을 발견하고 guard/회귀 검사로 해결했다. [최종 결과](../output/t10-source-review/REPORT.md), [입력별 검증](../output/t10-source-review/existing-source-checks.json)을 따른다.

새 migration·원본/Wiki DB canonical 변경·D2I·provider 호출은0회다. 아직 없는 HTML/code D2I adapter, direct-D canonical grounding과 live 의미 평가를 완료로 표시하지 않는다. 다음 단계는 이 공통 profile을 사용한 여러 형식의 실제 모델 평가이며 Test_Paper에 고정한 최저 K 개수는 없다.
