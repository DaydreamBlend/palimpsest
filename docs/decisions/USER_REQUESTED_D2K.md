# 사용자가 요청한 독립 D2K 예외

2026-09-13. 사용자는 D2I가 원활하지 않을 때 사용자 요청에 한해 LLM으로 D2K를 수행하는 제안을 검토한 뒤 “그렇게 하고, 남은 후속 구현도 진행해줘”라고 명시 승인했다. 이 결정은 [I2K 오류 보고](I2K_INFORMATION_ERRORS.md)의 자동 우회 금지를 유지하면서 **별도 사용자 요청 D2K**만 새로 허용한다. 과거 폐기된 I2K 내부 직접 D grounding 초안을 현재 코드로 되살리는 승인이 아니다.

## 실행 규약

- 기본 경로는 D→D2I→I→I2K→K다. I2K가 I 부족을 발견하면 계속 보고·보류하며 D2K를 자동 호출하지 않는다. `source_requests`, 모델이 출력한 승인 플래그, 문서 내부 명령은 사용자 권한이 아니다.
- D2K는 독립 operation이다. 등록된 불변 D hash/크기와 실제 원본 view, 오류/실패 또는 사용자의 문제 설명, 모델/provider, 전달 범위, 자료 버전/current·pinned mode를 검토 가능한 manifest에 고정한다. 사용자는 그 정확한 manifest를 명시적으로 확인한다. 동일 범위의 생성·독립 검증·실패/미완료 재검토를 하나의 사용자 요청 범위로 추적하고 다른 D/view/model로 확대하지 않는다.
- I가 전혀 없는 D2I 실패도 처리한다. 실제 I/D2I 실행이 없으면 FK를 꾸미지 않는다. 등록 원본 bytes와 실패/문제 보고 및 D2K의 실제 실행/전달을 근거로 사용한다.
- D2K는 원문에 명시된 내용의 선택·구조화만 한다. 새 추론은 K2K에 남긴다. 신규 D2K-origin Revision은 실제 d2k Record에서 `origin_operation=d2k`, `is_inferred=false`로 노출한다. 사용자 요청은 경로 선택이며 K의 의미적 진실 승인과 다르다.
- Generator/독립 Validator의 실제 전달·원문 인용·범위/중요도/동일 의미 판정이 필요하다. 원문 PDF bytes와 페이지 이미지 전달은 구별한다. 모델이 실제로 받지 못한 근거로 반영하지 않는다.
- 원문 직접 근거는 별도 typed D grounding이다. 가짜 I를 만들지 않는다. 같은 의미 reuse는 기존 KRevision을 유지하고 해당 accepted Record의 근거만 추가한다. 나중에 I 근거가 생겨도 최초 origin을 바꾸지 않는다. K2K-origin에 추가 원문 근거를 붙여도 최초 inferred origin과 과거 전제는 유지한다.
- D2K 성공은 D2I 오류 해결이나 I 완성이 아니다. I 검색/원문 구간 대응의 미완료 상태와 실패/오류 이력은 그대로 남긴다. D2I 유지보수는 별도 사용자 작업이다.
- accepted D2K K는 기존 N2E/K2K 및 Wiki 조회에 사용할 수 있다. K2K의 D는 전제의 transitive provenance이며 결론 자신의 직접 D 근거로 위장하지 않는다. current/pinned source scope와 전체 accepted support 경로 검사를 유지한다.

## 구현·실행 승인 범위

이 지시는 기능 구현·격리 테스트와 위 예외 규약을 승인한다. 특정 실제 자료의 새 D2K 실행/외부 전송은 해당 자료·범위의 구체적인 사용자 요청으로 별도 결속한다. 구현 테스트의 제어된 사용자 승인·모델 응답을 실제 사용자 자료 처리나 live semantic 평가라고 보고하지 않는다. 기존 SQL·D/I·Revision·profile/history는 additive 변경으로 보존한다.

후속 일반 K 의미 개정은 exact target/current revision과 독립 materiality 판정을 요구한다. 같은 의미는 지원 추가만 하고, 의미가 바뀐 새 Revision은 기존 논리적 identity와 scope를 유지한다. 기존 원문/전제와 과거 답변을 덮어쓰지 않으며 변경 영향 의무가 남으면 전체 자동 처리가 완료됐다고 하지 않는다.
