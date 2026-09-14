# Electron Realm metadata 연결

Realm은 [승인된 자료 범위](../decisions/REALM_SCOPE.md)를 표현하는 분류 공간이다. 이 연결은 별도로 준비한 Realm Catalog의 생성·수정·현재 목록·이력을 제공한다. 원본 저장소의 D/I/K, source 실행, 원문 파일에는 쓰지 않는다. Realm 분류가 provider 전송 허가나 Decision 권한을 부여하지 않는다.

Renderer API는 `window.palimpsest.realms(payload)`이며 다음 요청만 받는다.

| operation | 필드 |
|---|---|
| `catalog` | 없음 |
| `history` | `realm_id` |
| `create` | `name`, `description`, `actor`, `reason`, `request_id` |
| `revise` | `realm_id`, `expected_revision_id`, `name`, `description`, `members`, `actor`, `reason`, `request_id` |

생성은 빈 Realm을 만든다. 멤버 추가·제거는 현재 `expected_revision_id`에 대한 별도 revise다. 멤버는 `{store_id, member_kind, member_id}`이고 kind는 `data` 또는 `data_series`다. Data는 원래 SHA-256, store·series·Realm·Revision·요청 ID는 UUIDv7을 유지한다. 멤버십은 여러 Realm에 속할 수 있으며 기존 Revision을 덮어쓰지 않는다. `actor`는 분류 변경 이력에 남는 행위자 표기이며 인증·provider 권한·W2K authority를 대체하지 않는다.

Main process는 요청을 복사하고 필드를 검사한 뒤, 모든 멤버의 `store_id`를 신뢰된 연결 레지스트리에서 찾는다. 해당 저장소의 실제 `source_catalog`를 읽어 Data 등록과 series/version의 Data 소유를 확인한다. 하나라도 존재하지 않거나 읽기를 완료하지 못하면 metadata 수정 요청을 보내지 않는다. Source 연결은 read-only를 유지하며, 원문을 복제하거나 D2I를 호출하지 않는다. Series 멤버십은 논리 series를 가리킨다. 이 catalog 검사는 source 목록에 실제 version이 있는 series를 확인하며, 특정 head version을 Realm Revision에 고정한 것으로 주장하지 않는다.

Realm 연결은 host의 `.local/electron-ui/realm.json`, 없으면 패키지의 `realm.example.json`에서 읽는다. 기존 connection JSON 형태를 사용하되 `wikiId`와 `queryDirectory`는 null이고 `include_data_ids`는 받지 않는다. Docker project·database·image·Artifact volume은 신뢰된 이 파일이 지정한다. Renderer에는 DB·DSN·파일 경로·실행 이미지 선택 인자가 없다. Artifact volume은 read-only mount이고 Realm 서비스는 그것을 사용하지 않는다. Realm 설정 오류는 다른 자료 저장소의 reader를 중단하지 않는다.

`ReadBridge`의 JSONL transport를 재사용한다. Realm 요청은 `{request_id: 통신_ID, payload: Realm_요청}`으로 전송하며, nested `payload.request_id`는 canonical idempotency ID로 보존한다. 다른 통신 ID로 재전송해도 같은 Realm 요청 ID와 같은 내용은 기존 결과를 반환한다. 같은 요청 ID에 다른 내용은 conflict이고, 뒤늦은 expected head는 `realm_revision_changed`로 거부된다. UI는 현재 catalog를 다시 읽고 새 수정 내용을 명시적으로 준비해야 한다. 65,000 UTF-8 bytes를 넘는 요청은 현재 JSONL 전송 한도로 거부하며, 이것은 분류 저장 완료나 전파 수렴을 뜻하지 않는다.

`tools/realm_bridge.py`는 `RealmCatalog`만 호출하며 schema 생성·migration·source 연결·모델 호출을 수행하지 않는다. I2K의 Realm 범위 고정·검증은 별도 실행 모듈의 책임이며, 이 metadata IPC만 구현한 것을 전체 I2K 범위 연결 완료로 표시하지 않는다.

새 제품 I2K의 CLI prepare·review-resume 경로는 `RealmI2KGuard`와 `KnowledgeRuntime(..., require_realm=True)`를 사용한다. 직접 Python에서 생성하는 저수준 `KnowledgeRuntime(dsn)`의 기본값은 기존 코드·fixture 호환을 위해 `require_realm=False`로 남는다. 이것을 새 제품 서비스의 기본 진입점으로 복사하면 Realm이 강제되지 않는다. 새 Python 서비스도 trusted store/Source DSN에 결속한 guard와 `require_realm=True`를 명시해야 한다. 이미 저장된 이전 unscoped 실행의 같은 요청 재생과 새 I2K 시작은 구분한다. Propagation worker의 N2E/K2K, Wiki projection과 별도 사용자 요청 D2K에 I2K 전용 Realm 강제를 확장하지 않는다.

검증 코드는 `desktop/test/realm-bridge.test.cjs`와 `tests/app/test_realm_bridge.py`다. Fake source/catalog 기반 계약 검증과 실제 PostgreSQL·Electron 검증은 별도로 보고한다. 이 문서 자체는 DB 또는 사용자 UI 동작을 검증한 기록이 아니다.
