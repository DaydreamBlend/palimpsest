# T24 Realm 등록 하위 실행 계획

## 목표와 범위

사용자가 D 등록 전에 Realm을 선택하게 하고, Source 등록/Realm 연결 사이의 실패를 원본 보존과 같은 요청 복구로 처리한다. 자동 I2K/K2K는 같은 Realm 기본·명시적 교차라는 후속 지시를 따르며, 이 하위 작업은 등록과 I2K guard의 연결을 맡는다. Root가 CompilerRuntime/KnowledgeRuntime hook 및 K2K·전파 scope를 통합한다. 기존 분류 이동만으로 K 무효화 또는 frozen 실행 취소를 추가하지 않는다.

## 확인한 현재 경로와 보존 규약

`DataService.import_file/import_code_snapshot`와 CLI의 등록 경로, 기존 import journal/Artifact Store 요청 잠금, standalone Realm CAS/불변 Revision, `RealmI2KGuard`를 읽었다. PLANS, CODE_REVIEW, USER_OVERRIDES, INDEX, DECISION_REGISTER와 최신 REALM_SCOPE/REALM_DESKTOP/UI_REALM_ASSIGNMENT를 확인했다. D raw SHA·동일 요청 replay·일반 duplicate 거부, UUIDv7, 기존 source schema/모델/Revision을 보존한다. P 제안을 새로 채택하지 않는다.

## 구현

- 신규 `realm_registration.py`: metadata 검증, 기존 journal에 최초 Realm 선택 동결, 별도 Realm receipt 검사, 연결 복구, 컴파일 전 `verify_ready`.
- `service.py`: 요청 잠금 안에서 trusted Realm 선택을 해석하고 기존 storage metadata와 함께 저장한다. 과거 low-level API 호출은 변경하지 않는다.
- `realms.py`: 현재 exact Revision과 이미 완료된 request 결과를 읽는 작은 read helper.
- `cli.py`: 신규 등록 Realm 요구, 과거 unscoped request 재생·복구, 새 등록의 `requests show/recover` routing.
- `realm_i2k.py`: 실제 source 소유권 확인 때 등록 연결 완료도 확인한다.
- DDL 없음. Source 또는 Realm DB를 이 하위 agent가 호출하지 않았다. source/provider 호출 없음.

## 검증과 실제 결과

Host command: `python -X utf8 -B -m unittest test_realm_registration test_realms test_realm_i2k test_cli_unit test_knowledge_cli_routing test_code_snapshot_cli test_cli_integration` (`PYTHONPATH=src;tests/app`).

첫 검사: 43개 중 legacy CLI unit 한 개가 새 필수 Realm 인자를 전달하지 않아 실패했다. 테스트를 신규 제품 routing에 맞추고 같은 stderr request notification 검사를 유지했다.

수정 뒤 검사: **45개 실행, 33 통과, 12 skip, 0 실패**. skip은 별도 PostgreSQL source/Realm 환경이 없는 실제 DB 검사이다. 새 in-memory 검사 4개는 선택 필수, duplicate/replay, 부분 commit 후 복구, Realm 수정 뒤 과거 receipt 유지, 연결 전 컴파일 거부와 잘못된 receipt를 확인했다. 실제 PG용 새 검사 1개와 headless CLI 검사를 준비했으며 실행·판정은 root의 격리 환경 검증으로 넘긴다. 이 숫자는 실제 PostgreSQL 또는 Electron UI 검증 결과가 아니다.

## 인계와 남은 일

Root: 두 Runtime의 공통 시작에 `verify_ready` 호출, CLI K2W hook과 전체 packaging을 통합한다. 실제 PG 검사는 `PALIMPSEST_TEST_DSN`과 `PALIMPSEST_REALM_TEST_DSN` 모두 필요하다. Realm DB는 `palimpsest_realm_checks`, 새 등록 fixture의 source DB는 `palimpsest`, `palimpsest_effective_k2k_checks` 또는 root가 새로 준비한 `palimpsest_wisdom_checks`만 허용한다. 기존 CLI integration도 등록이 두 저장소에 걸치므로 이제 두 DSN을 명시한다. 테스트가 원본/DB를 삭제하거나 migration을 수행하지 않는다.

## 자동 Realm 범위 후속

Root가 추가로 위임한 범위: 신규 `realm_automation.py`, `PropagationRuntime`의 신규 제품 scope 준비/동일 요청 replay, propagation CLI의 Realm 인자, I2K의 새 기본 Realm 선택. root가 연결한 원본 등록 gate와 별개로 진행했다.

- I2K는 unique current common Realm을 찾고 여러 후보일 때 모든 입력의 공통 최초 등록 Realm이 현재도 유효한 경우만 우선한다. ambiguous/cross는 명시적 선택이 필요하다. 기존 frozen source feedback은 변경하지 않았다.
- 제품 전파는 `require_realm=True`; root execution에서 단일 Realm을 유추하거나 CLI로 Realm과 교차를 지정한다. 실제 등록 Data/series version을 기존 `allowed_data_ids`로 해석하고 정확한 Realm Revision/store/선택/자료 버전을 기존 run JSON scope에 저장한다.
- 과거 run 재시도는 현재 membership/head/Wiki 값을 다시 주입하지 않고 원래 scope/policy를 재생한다. 실제 실행의 current/pinned 및 scope blocked 동작을 유지한다. 필수 consumer 열거를 수정하지 않았다.
- `test_realm_automation.py`에 공통 Realm·초기 분류 tie-break·root scope·store 소유권·교차·frozen replay·제품 CLI unit 검사 및 실제 PG default/reclassification replay/pinned version 검사 2개를 추가했다. `test_realm_i2k.py`에 실제 I2K 자동 기본 선택/ambiguity PG 검사 1개를 추가했다.
- Host 검사(`test_realm_automation test_realm_i2k test_realm_registration test_realms test_cli_unit test_knowledge_cli_routing`) 첫 실행은 51개=37pass/14PGskip/0fail. 이후 CLI routing 검사를 추가했으며 마지막 실제 실행 결과는 아래에 기록한다. DB/provider는 하위 agent가 호출하지 않았다.

최종 하위 host 검사: **52개 실행, 38 통과, 14 PG skip, 0 실패** (0.380초). 변경한 automation/propagation/I2K Python 4개 파일 AST parse도 성공했다. 실제 PG 3개 신규 검사와 관련 regression은 root의 `palimpsest_wisdom_checks`/`palimpsest_realm_checks` 실행으로 인계한다.
