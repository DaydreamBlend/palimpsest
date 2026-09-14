# 자동 I2K·K2K의 Realm 기본 범위

2026-09-14 후속 지시. 자료를 등록할 때 Realm을 선택하고, 자동 I2K와 K2K는 같은 Realm에서 시작한다. 다른 Realm은 명시적으로 함께 선택한다. Realm 혼합이나 분류 이동을 K의 오류로 선언하거나, 완료된 K/Revision을 고치거나 기존 실행을 취소하지 않는다.

I2K의 새 실행에서 `--realm-id`가 없으면 실제 전달할 모든 I의 D/완료 source execution/정확한 자료 version이 함께 속한 **현재 Realm**을 찾는다. 후보가 하나이면 그 Realm의 정확한 Revision을 고정한다. 여러 공통 Realm이 있으면 모든 source가 공유하는 최초 등록 Realm을 현재도 소속인 경우에만 우선한다. 여전히 모호하면 `realm_selection_ambiguous`로 선택을 요청한다. 공통 Realm이 없을 때 여러 Realm을 자동 합치지 않는다. `--realm-id` 반복과 `--allow-cross-realm`은 기존 명시적 교차 계약을 사용한다. 기존 frozen request/feedback의 scope와 profile은 그대로 재생한다.

`PropagationRuntime`의 새 제품 prepare는 `require_realm=True`와 trusted `PropagationRealmGuard`를 사용한다. CLI는 이 모드다. `--realm-id`가 없으면 모든 root Record의 실제 I2K 또는 선행 전파 실행이 같은 단일 Realm을 가리킬 때 그 Realm을 선택한다. 과거 unscoped root, 여러 root Realm 또는 과거 교차 scope는 현재 작업의 Realm 선택을 명시해야 한다. 이 동작은 임의 전제 K를 직접 지정하는 모든 저수준 K2K API에 새로운 전면 금지를 붙이는 것이 아니라 자동 전파의 후보 범위이다.

선택한 Realm의 현재 Revision에서 trusted store에 실제 등록된 Data와 자료 계열을 조회한다. 자료 계열은 current head 또는 명시적으로 pinned한 정확한 version/Data로 해석한다. 새 scope의 기본 `allowed_data_ids`는 이 자료 목록이며 `--allow-data-id`는 그 안에서 좁히는 인자다. Realm 밖으로 넓힐 수 없다. current 모드에서 다른 head의 version을 선택하면 거부한다. 다른 물리 저장소의 Data를 이 실행으로 옮기거나 결합하지 않는다.

기존 propagation run scope 안에 `realm-automation-scope-v1`을 추가하여 store, 정확한 Realm Revisions, 허용 Data, 해석한 series/version, 명시적 교차 선택과 actor를 보존한다. run과 model input은 기존 request fingerprint·scope binding을 사용하며 별도 SQL table이 필요하지 않다. 이후 membership·자료 head·Wiki import가 달라져도 같은 준비 요청의 재시도는 저장된 scope/policy를 다시 반환한다. 그 변경을 예전 승인에 조용히 반영하지 않는다. 실제 작업 실행 시의 기존 current/pinned·K current support 검사는 유지한다.

자동 discovery는 기존 `_nodes`와 `k_revision_supported_by_version_data`를 통해 이 Data 범위의 current K를 선택한다. 전역 동일 의미 K 재사용과 선택한 근거 경로의 source 제한은 유지한다. **필수 의존성 열거는 Realm 필터로 잘라내지 않는다.** 이미 있는 범위 밖 consumer는 계속 의무로 열거하며, 그 scope에서 처리할 수 없으면 기존 blocked 상태로 남아 완료를 막는다. 분류 이동을 이유로 의무를 버리거나 성공으로 표시하지 않는다.

저수준 `PropagationRuntime(dsn, root, directory)`의 기본값은 기존 fixture/API 호환을 위해 `require_realm=False`다. 새 제품 서비스는 명시적으로 guard와 `require_realm=True`를 사용한다. 이전 run은 원래 scope와 anomaly/materiality policy를 그대로 재생한다. 자동 모델 호출·D2I 재실행·source DB migration은 이 선택 helper의 역할이 아니다.

검사 파일은 `tests/app/test_realm_automation.py`, `tests/app/test_realm_i2k.py`와 기존 propagation 검사를 사용한다. synthetic unit 검사와 실제 PostgreSQL 검사는 [하위 실행 계획](../../progress/T24_realm_registration_execplan.md)에서 구분한다.
