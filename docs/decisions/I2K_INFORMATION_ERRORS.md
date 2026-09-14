# I2K는 I만 근거로 사용하며 I 부족은 D2I 오류로 보고한다

2026-09-13 최신 사용자 정정. 사용자는 직접 D를 근거로 K를 만드는 경로가 규약에 없는 D2K라고 명시하고, D2I의 충실성을 전제로 I2K에서 I 부족을 발견하면 사용자에게 D2I 오류를 알려야 한다고 지시했다.

이 결정은 [과거 직접 D 예외](I2K_DIRECT_SOURCE_EVIDENCE.md)의 직접 grounding 허용을 **철회**한다. 이전 논의·실험 기록은 역사로 보존하며 현재 실행 허용으로 재인용하지 않는다. source 기반 K는 `D → D2I → I → I2K → K`를 따른다. K2K는 기존 규약대로 검증된 K 전제에서 추론하며 I/D의 우회 입력을 받지 않는다.

## 현재 실행 규칙

- I2K에 필요한 근거는 실제 I의 content 또는 그 I에 속한 실제 media에 있어야 한다. 원문 D의 직접 grounding, 가짜 I FK, null-I 후보, D에서의 K 우회 생성은 허용하지 않는다.
- 전체 I를 검토하다 필요한 내용·올바른 전사·이미지·provenance가 없음을 발견하면 D2I 정보 오류로 사용자에게 보고하고, 문제 I를 근거로 삼는 관련 K 후보를 보류한다. 보고된 내용은 `reported_error / verification_pending`으로 구분한다. 모델이 오류를 보고했다는 사실을 원문을 대조해 누락을 확정했다는 사실로 바꾸지 않는다.
- 이미 I 안에 충분한 근거가 있지만 K로 선택·추출되지 않은 경우는 I2K의 검토 미완료다. 이것만으로 D2I 오류를 만들지 않는다. 검색 일부 범위의 miss도 D2I 누락의 증명이 아니다.
- 오류를 숨기기 위해 D2I 재파싱·재청킹·regroup·새 I 생성을 자동 호출하지 않는다. 등록 원문을 읽어 바로 K를 만드는 복구도 없다. 원문 확인과 D2I 유지보수는 사용자에게 오류를 알린 뒤 별도 작업으로 진행한다.
- 원문·I·완료 D2I 실행·profiles/IDs/판정·Revision을 자동 수정하지 않는다. D2I 품질 오류 보고와 과거 D2I 실행 상태는 별개로 보존한다. 오류를 보고한 I2K 전체를 성공으로 표시하지 않는다.
- 관련 없는 I의 독립 검증된 K는 기존 원자적 반영 규칙을 따른다. 오류는 epistemic rejection이 아니므로 미해결 후보와 이유를 보존한다. source 오류가 있으면 일반 자동 review-resume 대신 사용자 확인이 필요함을 반환한다.

## 호환성과 구현

기존 structured wire의 `source_requests`는 과거 기록 호환을 위해 보존한다. 새로운 `i2k-information-required-v1` 정책에서는 이 필드를 원문 fetch 명령으로 처리하지 않고 사용자에게 전달할 I 부족/D2I 오류 보고로 사용한다. 요청 ID·관련 I·Data·source execution·문제 설명과 실제 Generator receipt를 남긴다. 독립 Validator도 per-I reason code로 `d2i_information_error`, `d2i_missing_information`, `d2i_transcription_error`, `d2i_missing_media`, `d2i_provenance_error`를 보고할 수 있다. 이 코드는 후보 수나 중요도 계산으로 스크립트가 만들어내지 않는다.

직접 D 구현 초안은 DB에 설치하거나 실제 K 생성에 사용하기 전에 중단했다. 기존 source/model/SQL/history를 복원·검증하고 초안은 폐기된 개발 기록으로만 보존한다. 새로운 source-error 정책과 보고는 기존 Runtime JSONB/판정/요청 이력을 사용하며 직접-D canonical table이나 D2K operation을 추가하지 않는다.

현재 query의 원문 열람은 canonical K 생성 권한이 아니다. 저장된 원문을 표시하거나 대조한 결과도 I2K의 I 근거 규약을 우회해 K로 승격하지 않는다.
