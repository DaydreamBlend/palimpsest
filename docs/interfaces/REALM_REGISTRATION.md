# 등록할 때 Realm 선택

2026-09-14 후속 구현. 신규 제품 CLI의 `data import`와 `data import-code-snapshot`은 `--realm-id`를 요구한다. 분류 이유는 `--realm-reason`으로 지정한다. trusted host의 `PALIMPSEST_STORE_ID`와 기존 Realm DSN/DSN_FILE 설정을 사용하며, 기본 catalog 이름은 `palimpsest_realms`다. renderer·원문·모델이 연결을 지정하지 않는다.

`RealmRegistration`은 기존 `DataService`와 `RealmCatalog.revise`를 사용한다. Data import journal의 `external_metadata.realm_registration`에 `realm-data-registration-v1`, store, 선택한 Realm과 최초 Revision, 별도 UUIDv7 membership request ID, actor와 reason을 보존한다. 동일 import request의 Realm 선택은 바꿀 수 없고, 선택 기록은 기존 요청 잠금 안에서 한 번 결정된다. 코드 snapshot의 segmented storage metadata도 함께 보존한다. D의 raw SHA, 중복 거부, Artifact Store와 기존 schema는 바꾸지 않는다.

Source DB와 Realm DB는 서로 다른 commit이다. 원본 등록 뒤 Realm 연결이 실패하면 원본과 journal은 남으며 응답은 `realm_registration_pending`/exit7이다. `requests show`는 source state와 Realm 연결 상태를 구분한다. `requests recover` 또는 동일 등록 요청 재시도는 기존 원본을 확인한 뒤 같은 membership request를 완료한다. `--realm-database`는 기존 trusted 연결 안에서 catalog를 선택하는 운영 인자다. 완료 응답이 유실되어도 저장된 Realm request 결과를 확인하므로 membership Revision을 중복 생성하지 않는다. 다른 동시 분류 변경은 기존 CAS로 보호하며 실패한 요청은 복구할 수 있다.

`verify_ready(conn, data_ids, catalog=None, store_id=None)`는 새 등록 marker가 있는 Data의 불변 Realm 연결 receipt를 확인한다. 등록이 아직 연결 대기이면 컴파일을 시작하지 않는다. 이미 연결된 Data의 Realm을 나중에 수정해도 과거 연결 성공은 유지한다. 현재 membership head의 이동을 과거 K의 오류나 기존 실행 취소로 해석하지 않는다. T24는 CompilerRuntime.start와 신규 I2K 준비에 이 gate를 연결했으며, 자동 K2K/전파는 [Realm 자동 범위](REALM_AUTOMATION.md)를 사용한다.

기존 unscoped import request는 원래 요청대로 재생·복구한다. 저수준 `DataService`의 unscoped import는 fixture와 기존 Python 호출 호환용이다. 새로운 제품 등록 서비스는 `RealmRegistration`을 사용한다. 동일한 Data를 다른 Realm에도 분류하는 작업은 기존 membership 수정이며 새 Data import가 아니다.

이 구현은 분류 연결을 추가하며 D2I·I2K·provider를 자동 실행하지 않는다. 원본 삭제 rollback, K/derivation 재작성, 기존 frozen 작업 취소를 수행하지 않는다. 검증 구분은 [등록 실행 계획](../../progress/T24_realm_registration_execplan.md)에 기록한다.
