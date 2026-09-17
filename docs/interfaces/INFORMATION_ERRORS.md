# I2K Information 오류 보고와 K 보류

앱0.14/schema0013. [최신 사용자 규약](../decisions/I2K_INFORMATION_ERRORS.md)에 따라 source K는 실제 I의 text/owned media를 통해서만 만든다. D2I의 충실성을 전제로 하며 I2K에서 I 자체의 부족·전사·이미지·provenance 문제를 발견하면 사용자에게 D2I 오류를 알린다. 직접 D2K, 원본 직접 grounding, 자동 D2I 재실행이나 I 수정은 없다.

## 모델 정책과 저장

새 multi-source I2K 실행은 `information_error_policy=i2k-information-required-v1`과 구현 hash를 profile/input에 고정한다. Generator/Validator는 전체 I와 실제 근거를 검토한다. 기존 JSON wire의 `source_requests`는 호환을 유지하되 원문 fetch 요청으로 처리하지 않고 D2I 정보 오류 보고로 사용한다. `information_ids`, `data_id`, page 힌트와 `question`의 문제 설명을 기존 immutable `k_source_requests`에 남긴다. 새 receipt는 `actual_delivery=false`, `action=notify_user_and_hold`, `reason_code=d2i_information_error`와 자동 작업 금지를 표시한다. `unavailable`이라는 기존 DB 상태를 원문 처리 작업의 대기로 해석하지 않는다.

Validator는 per-I review의 reason code로 아래를 보고할 수 있다.

| 코드 | 의미 |
|---|---|
| `d2i_information_error` | 필요한 I의 일반적인 문제 |
| `d2i_missing_information` | 필요한 내용이 I에 없다고 보고됨 |
| `d2i_transcription_error` | I 전사에 오류가 있다고 보고됨 |
| `d2i_missing_media` | 필요한 이미지/media가 I에 없다고 보고됨 |
| `d2i_provenance_error` | I의 근거 위치/연결에 문제가 있다고 보고됨 |

`missing_material_content` 같은 일반적인 K 선택 누락은 이 목록에 포함하지 않는다. I에 근거가 존재하지만 K로 충분히 선택되지 않은 것은 I2K의 의미 검토 의무로 남긴다. 스크립트가 중요도나 오류의 의미적 진위를 판정하지 않는다.

## 원자적 보류

새 정책의 Runtime은 Generator가 보고한 관련 I와 Validator의 위 코드에 연결된 I를 보류 대상으로 삼는다. 그 I를 인용한 K 후보와 그 보류 후보를 재사용하려던 후보는 `needs_human`이며 임시 후보·실제 이유를 보존한다. Validator가 후보를 accepted라고 썼거나 I verdict를 모순되게 confirmed로 썼어도 오류 코드가 있으면 통과시키지 않는다. 원래 Validator 출력과 review verdict는 변경하지 않고 별도 처리 결과를 남긴다.

다른 I에만 근거한 독립 검증 K는 기존 transaction 안에서 반영할 수 있다. 다만 미해결 오류가 있는 전체 실행을 completed로 표시하지 않는다. 오류 보고는 epistemic rejection이 아니며 관련 K를 rejected로 지우지 않는다.

## 읽기와 재개

```text
palim knowledge source-issues <execution-uuidv7> --json
palim knowledge review-status <execution-uuidv7> --json
```

`source-issues`는 현재·과거의 실제 보존된 요청/review를 읽는 순수 보고다. 새 정책 실행의 `knowledge show`와 `review-status`에도 `information_errors`가 포함된다. 과거 policy가 없는 `review-status`의 기존 모양은 유지한다.

보고 schema는 `i2k-information-errors-v1`이며 `requires_user_review`, 각 오류의 보고 주체·source request ID·정확한 Data/source execution/profile/input hash·관련 I/source refs·실제 이유를 포함한다. `reported_error / verification_pending`은 모델이 문제를 보고해 사용자 확인이 필요하다는 뜻이다. 원본을 읽어 누락을 입증했거나 I를 수리했다는 뜻이 아니다. 보고 함수는 D·DB·provider·parser에 접근하지 않는다.

오류가 있는 새 검토는 `next_action=review_d2i_error`다. 일반 `review-resume`은 `d2i_information_error_requires_review`로 중단하고 사용자 확인을 요구한다. 새 I가 필요하면 별도로 승인된 D2I 유지보수에서 해결하며, 이 오류 처리기가 재파싱·새 I·원문 K 생성을 수행하지 않는다. 단순 K 선택 미완료는 기존 검토 재개 경로로 계속 진행한다.

사용자가 오류를 확인하고 `review-resume --retain-information-errors`를 명시하면 이전 오류 요청을 새 실행의 frozen feedback에 누적해 전체 I를 다시 검토할 수 있다. 해당 페이지·block·media를 인용하는 K는 계속 보류하며, 오류 범위 밖의 K만 현재 K catalog와 중복 검증 후 반영한다. 이 선택은 D2I를 재실행하거나 오류를 해결됨으로 표시하지 않는다.

Electron의 기존 검토 화면은 이 보고가 있을 때 “D2I 정보 오류 · 사용자 확인 필요”와 정확한 관련 I 링크를 표시한다. 원문에서 K를 생성하거나 D2I를 다시 돌리는 버튼은 없다. historical 검토의 숫자는 해당 실행 당시의 기록이다.

## 보존·검증

기존 raw D/I/K/Revision/profile/판정과 SQL0001–0013은 유지한다. 직접 D 구현 초안은 DB/provider 실행 전 철회했고 원래 source hash로 복원했다. 기존 request replay와 Generator/Validator prompt/schema는 과거 snapshot에 해당 policy가 없으면 동일하다. 새로운 정책 profile만 새 규칙을 적용한다.

[순수 오류 검사](../../tests/app/test_information_errors.py), [실제 PG의 합성 모델 판정 검사](../../tests/app/test_information_error_runtime.py), 기존 multi-source/review/desktop 회귀 검사로 오류 코드·보류·무관한 K 반영·후보 정리·exact refs·재개 차단을 확인한다. 테스트는 source/D2I/provider 접근 trap을 두며 실제 LLM의 누락 감지 회수율 평가는 아니다.

페이지 힌트와 `/pdf_info/<0-based-page>/...` block 근거가 함께 있으면 보류 범위는 그 페이지를 직접 인용한 후보로 제한한다. 하나의 큰 I에 여러 페이지가 들어 있어도 한 페이지의 전사 신고가 I 전체 후보를 보류하지 않는다. 페이지·block 범위를 확인할 수 없는 신고만 해당 I 전체를 보수적으로 보류한다. Validator의 target별 누락 판정은 source-review target binding으로 별도 제한한다.

Page-scoped media citations use the retained I media SHA-256 to recover its page_index. A report for one page holds only candidates cited from that page; only citations whose page cannot be resolved remain conservatively held.
