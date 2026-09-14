# T02 — Python/Docker CLI·Data 등록 구현

사용자 지시: 저장 스키마 v1 후 “계속 진행해줘.”. 앞서 제시한 다음 실행 단계(Python/Docker 구체화, 독립 PG18/pgvector, D import/show/verify/recovery)를 진행한다. U09/U10 및 해당 D 계약이 승인된 범위이며 T01의 다른 K/W/P 미정은 해당 후속 기능에만 남긴다. T02를 진행하기 위한 실행 선택을 이번 구현 profile로 구체화한다.

## 목표·경계

Docker에서 Python CLI `palim`의 help/version/doctor, data import/show/verify, request status/recover를 실행하고 원본을 보존하며 실제 PostgreSQL에 등록한다. 새 duplicate는 거부하고 같은 성공 request는 재생하며 crash 후 준비한 등록을 복구한다. MinerU/LLM/GUI/미래 도메인 scaffolding은 포함하지 않는다. 필요한 최소 앱 모듈과 실제 tests를 함께 만든다.

root/docs/tests 지침, PLANS/CODE_REVIEW, USER_OVERRIDES/INDEX/DECISION_REGISTER, T02, CLI_CONTRACT, STORAGE_IDENTITY, D SQL/fixture, 저장 스키마 v1과 T00 inventory를 확인했다. T00는 역사 관찰이며 현재 Docker approved execution 접근 성공과 혼동하지 않는다. 시작 파일 hash를 보존했다. 사용자 원본/기존 DB/다른 프로젝트 컨테이너는 변경하지 않는다.

## 실행 계획

1. [x] exact Python/psycopg/PG18+pgvector 이미지와 dependency lock·Compose profile 확정.
2. [x] 최소 Data/domain 오류, Artifact Store, PostgreSQL repository/migration, 등록 서비스 및 CLI 구현.
3. [x] 독립 Docker project/DB/volume에서 실제 migration/SQL fixture와 파일/CLI/동시성/crash 테스트 실행.
4. [x] 독립 코드 검토의 실제 결함 수정, 필요한 검증만 재실행.
5. [x] 사용법·현재 runtime 관찰·AT coverage·미실행 범위·변경 파일·명령/결과 기록과 문서 검사.

root는 schema/migration/repository/service/infra와 공통 계약을 소유한다. 별도 agent에게 Artifact Store, CLI, 테스트의 분리된 파일 범위를 맡기며 shared schema는 동시에 편집하지 않는다. 프로세스 crash tests와 SQL fixture는 task-local test DB/volume만 사용한다. build context에 사용자 자료나 비밀을 포함하지 않는다. 이미지 pull/build는 로컬 실행에 필요한 공개 배포물이며 원문 외부 업로드가 아니다.

## 검증과 보존

AT56/67/70/82/83/89/102/104/108/109/110을 실제 범위대로 검증한다. AT57 전체 backup/restore 및 MinerU readiness 중 실제 parsing은 후속 범위로 구분한다. CLI/SQL/file tests, document tools, live semantic tests를 구분한다. T02 이후 task는 완료 처리하지 않는다. test project/volume 이름과 실제 command는 검증 후 기록한다. 새 파일 삭제로 rollback 가능한 앱 변경이며 사용자 DB에 destructive migration을 하지 않는다.

## 실제 실행 — 2026-09-09

모든 Docker 명령은 일반 sandbox pipe 접근 거부 후 `require_escalated` 실행 경로로 수행했다. 자동 승인 검토의 거절은 없었다. Docker engine 29.7.2, Linux x86_64, Compose 5.5.1. 공개 Docker/PyPI metadata와 wheel hash 조회 후 Python 3.12.14와 pgvector 0.8.6/PG18 이미지를 pull하고 dependency hash lock으로 빌드했다. 정확한 이미지/driver profile은 [T02_RUNTIME](../docs/implementation/T02_RUNTIME.md)에 있다.

| 명령 | 실제 결과 |
| --- | --- |
| `docker compose -p palimpsest-t02-test build` | 최초 및 수정 후 성공, exit 0 |
| `docker compose -p palimpsest-t02-test up -d db` | 전용 volumes/init/DB 생성·healthy, exit 0 |
| `docker compose -p palimpsest-t02-test run --rm migrate` | 최초 `0001_data`, `applied: true`, exit 0 |
| `docker compose -p palimpsest-t02-test run --rm --no-deps --entrypoint python migrate tools/check_storage_sql.py` | 빈 테스트 테이블에서 원래 SQL fixture 통과, transaction ROLLBACK, exit 0 |
| `docker compose -p palimpsest-t02-test --profile test run --rm test` (첫 실행) | 41개 중 40 pass/1 fail, 4.874초, exit 1. doctor checksum 불일치와 생성 전 root fixture를 발견 |
| 위 app suite 수정 후 재실행 | **52 tests / 8.817초 / OK / exit 0**, skip 없음 |
| `docker compose -p palimpsest-t02-test run --rm --no-deps app doctor --json` | ready=true, server `18.6 (Debian 18.6-1.pgdg12+2)`/180006, vector 0.8.6, `0001_data`, writable=true, MinerU not_configured, exit 0 |
| `docker compose -p palimpsest-t02-test run --rm --no-deps migrate` | 같은 migration checksum 확인, `applied: false`, exit 0 |

첫 fixture의 header `NOT EXECUTED`는 작성 당시 기록으로 bytes를 보존했다. 실제 실행은 이 표가 근거다. 첫 SQL/initial install 성공 후에는 checksum helper만 LF 정규화로 통일했고 설치된 SQL 본문은 변경하지 않았다.

App suite 52개: [파일 저장 16개](../tests/app/test_artifact_store.py), [CLI/config unit 14개](../tests/app/test_cli_unit.py), [credential 초기화 3개](../tests/app/test_container_init.py), [Data 서비스·PostgreSQL 18개](../tests/app/test_data_integration.py), [실제 CLI workflow 1개](../tests/app/test_cli_integration.py). Data 테스트 중 canonical size mismatch는 DB를 변조하지 않는 repository-read stub, readonly filesystem flag는 mock fault injection이다. 다른 DB 동시성·프로세스 crash·CLI 경로는 실제 DB/파일/프로세스를 사용했다.

실제 CLI workflow는 비TTY·DISPLAY/브라우저 없이 help/version/doctor/import/show/verify/새 duplicate/성공 replay/requests show/recover를 subprocess로 실행했다. stdout JSON과 stderr 이벤트, Korean/공백/quote/terminal escape 파일명, duplicate exit 6, 원본 bytes 불변을 검사했다. 각 crash 테스트는 자식 프로세스 `os._exit`를 쓰며 단순 Python exception만으로 process crash를 대신하지 않았다. 파일 복사 중 변경/부분 staging과 symlink/FIFO/path-swap은 별도 실제 파일 검사다. 전원 차단이나 Docker VM 자체의 disk fault를 주입한 것은 아니다.

## 독립 검토와 수정

1. 설치 SQL checksum은 LF 정규화였으나 doctor는 raw CRLF bytes를 hash했다. 동일 source helper로 통일해 이미 적용한 checksum을 보존했다. 첫 doctor fixture는 root가 미생성이었으므로 준비된 디렉터리를 생성하도록 바로잡았다.
2. 성공 receipt에 다른 bytes로 재시도하면 잘못된 staging이 남아 정상 재시도를 막았다. terminal receipt의 staging만 정리하며 prepared 요청의 정상 복구 bytes는 보존한다. 성공→wrong bytes 거부→원본 복원→동일 결과 replay 회귀가 통과했다.
3. duplicate 판정 시 canonical byte_size도 비교해 크기 불일치를 integrity_conflict로 보고한다. read stub 회귀가 실제 DB 기록을 오염시키지 않고 이 조건을 검사했다.
4. doctor의 파일 접근은 읽기뿐 아니라 effective-ID 쓰기/탐색·readonly filesystem을 비변경 검사한다. root/하위 폴더 권한 회귀를 추가했다.
5. credential 최종 경로에 직접 쓰던 bootstrap은 중간 crash 시 재개 불가였다. 잠금 아래 pending write/fsync→no-overwrite link→directory fsync로 바꾸고 link 전후 실제 crash·partial pending 복구·완성 secret 불변을 검사했다. agent의 선행 targeted 검사 3개/0.141초 통과 후 통합 suite에서도 통과했다.

## Acceptance 실행 범위

| ID | 현재 상태 | 근거와 남은 범위 |
| --- | --- | --- |
| AT56 | passed | 부분 staging·prepare/publish/commit 후 process crash/recovery, missing/corrupt object 실패. 파일+DB 검증 |
| AT57 | spec_only | DB/artifact/outbox 전체 backup·빈 환경 restore는 후속 범위 |
| AT67 | passed | SQL immutable 제약, 원본 변경 후 새 SHA/Data, 과거 snapshot/bytes 불변 |
| AT70 | passed | SQL의 명시적 두 origin/acquisition 보존 + service show + 일반 duplicate 거부. 전용 acquisition CLI는 없음 |
| AT82 | passed | 실제 headless CLI workflow와 파일·DB 연결 |
| AT83 | passed | CLI unit + 실제 subprocess stdout/stderr/JSON/오류 출력 분리 |
| AT88 | partially_tested | 현재 문서 policy + 구현된 Data/Store/Runtime schema 이름 검토. 미래 모듈 검사는 후속 |
| AT89 | spec_only | legacy schema 이름 변환 rehearsal 없음. 신규 migration이며 기존 schema 자동 변경 거부 |
| AT102 | passed | 미구성 MinerU 진단, 실제 DB/root readiness, 진단의 비변경 파일 검사; 모델 호출·다운로드 없음 |
| AT104 | partially_tested | 실제 Korean/공백/quote/escape CLI와 안전 파일 경로 검사. MinerU subprocess 부분 미실행 |
| AT108 | partially_tested | PG18.6/vector0.8.6, D/request/acquisition SHA/UUIDv7 제약. 후속 객체/Compiler Record ID는 미구현 |
| AT109 | passed | 두 request 동일 bytes 경쟁/한 request 경쟁, 원래 성공 replay, 바뀐 입력 conflict, Data/최초 acquisition 하나 |
| AT110 | partially_tested | 실제 copy/publish/commit/recovery/잠금·공유 object 재사용·DB 원자성. 향후 관리 폴더 reconciliation/운영 도구의 전체 시나리오는 후속 |

7 passed/4 partially_tested/101 spec_only를 catalog에 반영한다. `passed`는 해당 AT의 명시한 시나리오 결과이며 전체 앱·MinerU·semantic correctness의 통과가 아니다. T02 Done when의 AT56/67/70를 실행했으며 AT57 확장 범위를 명시한다. T01 전체 계약이나 T03 이후는 완료 처리하지 않는다.

## 변경 파일과 운영 상태

앱: `src/palimpsest/`의 data/errors/config/CLI/service/artifact_store/canonical_store와 `migrations/0001_data.sql`, package entrypoint. 배포: Dockerfile, compose.yaml, pyproject.toml, requirements.lock, .dockerignore/.gitignore. 실행 도구: container_init/run_app_tests/check_storage_sql. 테스트: tests/app 5개 파일. 문서: README, INDEX, CLI_CONTRACT, ENVIRONMENT, T02_RUNTIME, T02 task/task_graph, STATUS/inventory/본 plan, acceptance catalog/안내, T02 schema 안내.

테스트 project는 `palimpsest-t02-test`, volumes는 해당 prefix의 postgres/artifacts/db_credentials/app_credentials다. host port 없음/internal network. 일반 앱 UID/GID10001과 runtime DB role을 사용하고 admin secret은 앱에 mount하지 않는다. 원문 사용자 파일·기존 DB·다른 프로젝트 컨테이너는 사용하지 않았다. synthetic integration rows는 DB에 남지만 case별 임시 artifact는 정리하므로 이 테스트 DB를 사용자 환경으로 쓰지 않는다. Git 부재 때문에 시작 파일 SHA-256과 종료 파일 목록을 비교한다. 원본/current canonical/history/기존 SQL·fixture와 사용자 승인 JSON은 변경하지 않는다.

다음은 T03의 MinerU 최신 안정판 실행 profile·parse artifacts/provenance·D2I/Information 저장이다. live provider/원문 외부 전송·파괴적 migration은 이번 실행 범위에 없다. 지금 중대한 정책 승인 대기는 없으며 후속 기능의 P 미정과 다중 사용자 authority는 그대로 남는다.

## 최종 문서 검사와 종료 상태

다음 명령은 호스트의 번들 Python으로 실행했다. 배포 runtime은 별도로 고정한 Docker Python이다.

```powershell
$env:PYTHONUTF8='1'
& 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B tools/validate_bundle.py --json
& 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -m unittest discover -s tools -p 'test_*.py'
```

문서 validator: exit 0/errors 0. 문서 도구 unit/mutation: **39 tests / 40.805초 / OK / exit 0**. 이는 앱 52개와 별개 결과다. 시작/종료 hash 비교는 **새 파일 26개, 기존 변경 12개, 삭제 0개**다. AGENTS/PLANS·원본·current canonical 13 slices/map/full·history·승인 JSON·원래 SQL/fixture·기존 도구/명세 본문은 보존했다. catalog에는 실행 상태와 참조만 추가했다.

실제 runtime DB 권한 조회에서 `data INSERT=true`, `data UPDATE=false`, `data DELETE=false`, `request UPDATE=true`를 확인했다. 마지막 검증 이미지 `palimpsest-t02:0.1.0`의 로컬 image ID는 `sha256:2e2f28a054ecbbd2585c683f305fb47abf478c15fa8dd69a24571ac8c701363d`다. 이는 로컬 빌드 관찰이며 외부 registry에 게시하지 않았다.

`docker compose -p palimpsest-t02-test stop db`를 exit 0으로 실행해 테스트 DB를 중지했다. 네 개 named volumes는 보존했고 삭제하지 않았다. `palimpsest-dev` project는 문서의 새 개발용 실행 예시이며 아직 생성하지 않았다. T02 작업 경계에서 종료한다.
