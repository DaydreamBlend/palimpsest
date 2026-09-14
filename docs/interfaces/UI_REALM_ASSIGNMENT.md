# Realm을 직접 지정하는 UI

2026-09-14, UI0.6.0/backend0.22.0. 사용자가 제공한 HTML은 시각적 참고이며 샘플 답변·Decision·온라인 검색 코드를 제품 동작으로 사용하지 않았다. [결과와 용량 정리](../../output/t23-ui-realm/REPORT.md).

자료 카드와 상세의 **Realm 지정**에서 Realm과 적용 범위, 변경 이유를 선택한다. 자료는 여러 Realm에 속할 수 있고 각 소속을 개별적으로 추가·해제한다. `이 원본 D`는 같은 SHA를 가진 알려진 모든 보존 위치를 한 Realm Revision에서 변경한다. 코드 등의 `자료 계열 전체`는 특정 store의 정확한 series membership을 변경한다. 직접 D 소속을 해제해도 series 소속은 유지되므로 UI에서 이를 표시한다. 다른 자료의 membership은 수정하지 않는다.

저장은 기존 Realm `revise`와 expected Revision CAS·UUIDv7 request replay·Main의 실제 source 검증을 재사용한다. 한 번의 저장은 선택한 Realm 하나에 원자적으로 반영된다. 서로 다른 Realm의 소속을 한꺼번에 이동시키는 새 분산 transaction을 만들지 않았다. Realm 변경은 D/I/K/Revision을 재작성하거나 compiler/provider를 실행하지 않는다.

Realm 선택은 자료·Wiki·K·검토·질문 목록에 유지된다. Wiki는 실제 source/contribution Data, K는 source Data, 검토는 전체 입력 source, 질문은 해당 query index의 source 범위를 기준으로 분류한다. 모델이 실제 읽은 근거의 판정은 기존 정확한 인용·receipt에 남아 있으며 UI 필터로 새 delivery를 주장하지 않는다. 여러 Data에 관련된 공통 주제나 K는 관련 Realm에서 나타날 수 있다. 이 탐색 필터는 ACL이나 I2K 실행 승인 자체가 아니다.

자료 상세는 이미 저장된 K가 있으면 K 탭을 먼저 보여준다. I와 source execution 이력은 별도 탭에서 모두 읽을 수 있다. I2K 상태는 실제 typed input I 소유권으로 연결한 실행·모델 호출 기록에서 읽는다. 여러 Data가 들어간 실행의 생성/재사용 개수는 그 실행 전체의 수치다. prepared/0 calls를 완료로 표시하지 않는다.

기존 코드 Wiki가 A Data만 포함하여 B의 K가 기본 목록에서 제외되던 것을, trusted 코드 연결의 세 등록 Data를 명시적으로 포함하여 개선했다. 새 Source 읽기에서 정확한 D/I/execution을 확인하므로 Wiki page가 없는 B의 K도 해당 I로 되돌아간다. 기존 Wiki page bytes와 I2K 결과는 유지한다. 전체202파일 source는 I204/K0/모델0인 준비 상태다. 별도 통제 A/B에는 I2K K39개와 inferred K3개가 있으며 이 기존42개를 통합해 표시한다.

실행은 [Palimpsest.cmd](../../Palimpsest.cmd)가 기존 `desktop/node_modules/electron/dist/electron.exe`와 `output/t23-ui-realm/release/app.asar`를 사용한다. `node tools/package_desktop.cjs`는 첫 당사자 assets와 browser PDF.js만 묶고 Electron 엔진을 복사하지 않는다. 현재 assets package는33.24MiB다. 이전 전체 실행본은 사용자의 삭제 승인에 따라 정리했고 해당 source/report는 유지한다. 다른 PC의 완전 자동 설치 배포판은 아니다.

별도 Realm 환경의 테스트/운영 연결은 trusted `PALIMPSEST_DESKTOP_REALM_CONFIG` 파일로 지정할 수 있다. renderer 요청으로 DB를 바꾸지 못한다. 기본 Realm catalog는 기존 `palimpsest_realms`이며 실제 UI 쓰기 검사는 `palimpsest_realm_checks`에서 수행했다.
