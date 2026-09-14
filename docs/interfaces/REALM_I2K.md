# Realm으로 고정하는 I2K 범위

상태: 제품 진입점 구현과 격리 PostgreSQL 검사 완료. Realm metadata PG4개와 I2K 결속 PG4개가 실제 통과했다. 실행 증거는 [T22 결과](../../output/t22-unified-electron/REPORT.md)에서 확인한다. 이 계약은 I2K의 기본 분리·명시적 교차 선택을 구현하며 N2E/K2K/query의 범위를 소급 제한하지 않는다.

Realm은 프로젝트·주제별 자료 소속이다. 원본 Data hash, Information, Knowledge identity와 이전 Revision을 바꾸거나 복제하지 않는다. 같은 Data를 여러 Realm에서 참조할 수 있다. Realm 변경은 자료 분류 변경이며 기존 K의 진실성 변경, 접근 권한 변경, provider 전송 승인이 아니다.

## 제품 CLI

trusted host 설정에서 `PALIMPSEST_STORE_ID`를 실제 source connection에 결속한다. Realm catalog는 `PALIMPSEST_REALM_DSN_FILE`로 지정한다. 별도 파일을 지정하지 않으면 source credential로 `palimpsest_realms` DB를 선택할 수 있다. `--realm-database`는 이 catalog DB 이름을 명시한다. 모델 입력이나 renderer가 DSN을 지정하지 않는다.

새 `knowledge prepare --operation i2k`에는 `--realm-id UUID`가 필요하다. 여러 Realm을 선택하려면 `--realm-id`를 반복하고 이번 실행에 `--allow-cross-realm`을 명시한다. `knowledge review-resume`에도 같은 선택 옵션이 있다. 이미 scope가 고정된 source 검토는 원래 scope를 상속할 수 있다. 기존 Realm membership head가 바뀌어도 원래 revision을 재생하며, 변경된 head로 근거를 몰래 바꾸지 않는다.

Series membership으로 선택하려면 `--data-version-id`로 실제 version을 함께 지정한다. source의 Data·source execution·series·version 소유권을 실제 source DB에서 확인한다. 기존 current/pinned version 규칙도 유지한다. Realm revision만으로 동적인 series head가 고정되었다고 주장하지 않는다.

`knowledge stage`와 `knowledge decide`도 저장된 Realm scope를 재검사한다. 별도 catalog DB를 사용했다면 같은 trusted 설정 또는 `--realm-database`를 유지한다. 신규 scope가 없는 제품 I2K 시작은 `realm_required`로 실패한다. 기존 unscoped 실행의 조회·정확한 요청 재생은 유지한다.

`information prepare-input`과 `knowledge combine-inputs`는 읽기용 입력 파일 구성이다. Realm 승인이나 provider 호출이 아니며, 실제 I2K 시작은 다시 Runtime의 Realm 검사를 통과해야 한다. D2I 호출·원문 복구·I 생성은 Realm 작업으로 실행하지 않는다.

## API와 저장 경계

제품 API는 `RealmI2KGuard(catalog, store_id, source_dsn, realm_ids=[...], explicit_cross=False, actor=...)`를 trusted 설정으로 만들고 `KnowledgeRuntime(source_dsn, realm_guard=guard, require_realm=True)`를 사용한다. source DSN과 guard의 binding은 같아야 한다. 직접 제공한 교차 `realm_scope`의 boolean만으로는 새 교차 실행을 허용하지 않는다. trusted 호출자의 교차 선택이 필요하다.

`require_realm=False`는 이전 실험·fixture·명시적 low-level API 호환 경로다. 제품 API에서 이 설정을 사용하지 않는다. 저장된 profile에 `realm_i2k_policy`가 있는 실행은 이 low-level 경로로 stage·decide하더라도 Realm guard 없이 진행할 수 없다.

실행의 immutable `k_execution_contexts.input_snapshot.realm_scope`와 profile marker에 exact Realm revision·source 목록·정책·선택·hash가 결속된다. request fingerprint, Generator 입력 digest와 Validator context digest에도 포함된다. 새 SQL schema나 기존 source DB migration은 이 경로에 추가하지 않았다. 제품 서비스가 catalog의 실제 immutable revision과 source DB를 함께 검증한다. 원시 SQL 쓰기에 Realm 권한 체계를 추가했다는 주장은 하지 않는다.

Realm catalog는 source 자료의 위치를 보관하지만 source bytes를 복제하지 않는다. 여러 저장소를 한 Realm에 표시할 수 있어도 현재 I2K canonical FK는 한 저장소 안에서 동작한다. cross-store I2K scope는 명확하게 거부한다.

## 기존 K 비교와 원문 근거

일반 K의 중복 제거는 같은 source store의 global K identity를 유지한다. Realm ID를 K fingerprint에 추가하지 않는다. 새 Realm I2K의 comparison catalog는 exact K IDs·statement·semantic payload·identity scope·fingerprint·현재 support 상태로 제한한다. 기존 K에 붙은 raw I/D quote, grounding 전체, artifact 경로를 비교 목록을 통해 다시 전달하지 않는다.

source 근거는 선택한 Realm의 실제 입력 I에서만 가져온다. 비교용 K의 존재는 그 I가 후보를 뒷받침한다는 증명이 아니다. 원문에 없는 결론은 계속 K2K에만 속하며, 새 근거 추가도 독립 검증을 통과해야 한다. 과거 unscoped 실행의 보존된 snapshot/prompt를 이 정책으로 다시 쓰지는 않는다.
