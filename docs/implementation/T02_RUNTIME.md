# T02 Python/Docker 실행 profile

2026-09-09 구현. U09/U10과 사용자 “계속 진행해줘.” 지시에 따라 Data 등록의 실제 실행 profile을 구체화했다. 전체 D/I/K/W 스키마 v1 중 이번 migration은 D·acquisition·등록 journal만 설치한다. P01–P12의 나머지 미정은 승인된 것으로 간주하지 않는다.

## 고정한 배포물

| 항목 | 실행 profile |
| --- | --- |
| 플랫폼 | Linux amd64 컨테이너; Windows에서는 Docker Desktop의 Linux engine 사용 |
| Python | `python:3.12.14-slim-bookworm` |
| Python image digest | `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254` |
| DB image | `pgvector/pgvector:0.8.6-pg18-bookworm` |
| DB image digest | `sha256:2ba9ca5f2e7daa0f0e7723cba1ee9167bab54efd3640516a44ac1a928dd67e7a` |
| 앱 | `palimpsest` 0.1.0 / CLI `palim` / 표준 라이브러리 argparse |
| DB driver | `psycopg[binary]==3.3.5` |
| 나머지 lock | typing-extensions 4.16.0, setuptools 84.0.0 |
| Migration | `0001_data`; 패키지 SQL, psycopg runner, transaction + advisory lock + checksum receipt |
| 테스트 | 표준 라이브러리 unittest; 실제 Linux 파일 및 PostgreSQL, CLI subprocess |

이미지 tag와 digest를 함께 고정하고 [requirements.lock](../../requirements.lock)에 Linux amd64/CPython 3.12 wheel SHA-256을 고정한다. 설치 시 공개 registry metadata와 wheel hash를 확인했다. 이미지의 실제 server/extension 관찰과 테스트 결과는 [T02 실행 기록](../../progress/T02_execplan.md)에 있다. 자동 latest/PG19 전환은 없다. 다른 Python minor/CPU architecture로 변경할 때 wheel lock과 통합 검증을 갱신한다.

## 실행

저장소 root에서 다음을 실행한다. 개발용 project 이름은 `palimpsest-dev`, 검사 전용은 `palimpsest-t02-test`로 구분한다. 서로 다른 Compose project는 별도의 DB·credentials·Artifact Store volumes를 갖는다.

```powershell
docker compose -p palimpsest-dev build
docker compose -p palimpsest-dev up -d db
docker compose -p palimpsest-dev run --rm migrate
docker compose -p palimpsest-dev run --rm app doctor --json
```

Compose는 credential 초기화→DB health→명시적 migration 순서를 제공한다. `app`의 dependency로 migration이 재실행되어도 적용 이력과 checksum이 같으면 `applied: false`다. `palim doctor` 자체는 설치·migration·폴더 생성을 수행하지 않는다. 이미 초기화된 실행 환경에서 진단만 할 때는 다음처럼 dependency 시작을 생략한다.

```powershell
docker compose -p palimpsest-dev run --rm --no-deps app doctor --json
docker compose -p palimpsest-dev run --rm --no-deps app --help
docker compose -p palimpsest-dev run --rm --no-deps app --version
```

사용자 입력 폴더를 읽기 전용으로 mount한 뒤 등록한다. 아래 호스트 경로는 사용자가 실제 자료 폴더로 바꾼다. 관리 Artifact Store 폴더에 직접 원본을 복사하는 방식은 등록 경로가 아니다.

```powershell
docker compose -p palimpsest-dev run --rm --no-deps --volume "C:/papers:/input:ro" app data import "/input/논문 원본.pdf" --json
docker compose -p palimpsest-dev run --rm --no-deps app data show <data-id> --json
docker compose -p palimpsest-dev run --rm --no-deps app data verify <data-id> --json
docker compose -p palimpsest-dev run --rm --no-deps app requests show <request-id> --json
docker compose -p palimpsest-dev run --rm --no-deps app requests recover <request-id> --json
```

`<data-id>`는 결과의 SHA-256, `<request-id>`는 UUIDv7로 치환한다. import 시작 때 stderr의 `request_started`에 request ID를 즉시 출력한다. 성공 후 같은 요청을 재생하려면 원본 경로·metadata를 유지하고 `data import ... --request-id <request-id>`를 사용한다. journal 준비 이후에는 원본이 사라져도 검증된 staging/object로 `requests recover`가 가능하다. journal 생성 전 중단이면 원본과 같은 request ID를 다시 제출한다.

새 request로 동일 bytes를 제출하면 `duplicate_data`와 기존 Data ID, exit 6을 반환한다. 같은 논문이라도 bytes가 다르면 별도 Data다. 일반 중복 등록은 acquisition을 추가하지 않는다. 독립적인 두 번째 acquisition 보존은 SQL 제약/서비스 조회로 검증했으며 전용 acquisition 추가 CLI는 아직 없다.

DB를 멈추고 volumes를 보존하려면 `docker compose -p palimpsest-dev stop db`를 사용한다. DB만 복사한 것은 원본까지 복구 가능한 backup이 아니다. 전체 backup/restore·outbox 복원은 AT57 후속 범위다.

## 구성·권한

[compose.yaml](../../compose.yaml)은 host port를 노출하지 않는 internal network를 쓴다. DB volume은 PostgreSQL 18의 `/var/lib/postgresql`에 mount한다. `init`이 volume 안에 임의 credential을 생성하고 완성 파일은 회전하지 않는다. credential은 임시파일 fsync와 덮어쓰기 없는 게시로 저장한다. 기존 사용자 DB나 전역 Docker 설정을 바꾸지 않는다.

일반 앱은 UID/GID 10001, 전용 DB 역할 `palimpsest`로 실행한다. canonical Data/acquisition은 SELECT/INSERT만, 등록 journal은 제약 내 SELECT/INSERT/UPDATE만 허용한다. admin credential volume은 init/DB/migrate만 mount하고 앱에는 별도의 runtime DSN volume만 읽기 전용으로 전달한다. `.dockerignore`는 소스·lock·실행 도구·synthetic tests만 build context에 포함한다.

직접 구성하는 경우 `PALIMPSEST_DATABASE_DSN_FILE` 또는 `PALIMPSEST_DATABASE_DSN` 중 하나를 사용한다. `PALIMPSEST_ARTIFACT_ROOT`는 관리 root, `PALIMPSEST_ACTOR`는 기본 `local`인 로컬 운영자 표식이다. 이 표식은 request 소유자 비교용이며 다중 사용자 인증이나 Decision authority 확인을 구현한 것은 아니다. DSN은 CLI 출력이나 예외 메시지에 노출하지 않는다. Windows native filesystem 실행은 지원하지 않으며 파일 잠금·no-follow·fsync 경로는 Linux Docker에서 검증한다.

## 저장과 복구 경계

`data.py`는 SHA-256/UUIDv7/등록 fingerprint 규칙, `service.py`는 등록 use case, `artifact_store.py`는 파일 잠금·staging·publish·verify, `canonical_store.py`는 DB transaction과 migration을 담당한다. `cli.py`는 인자/출력 변환만 수행한다. 미래 도메인이나 변환의 빈 모듈은 만들지 않았다.

파일은 request별 잠금 아래 복사·fsync한 후 content-addressed object로 덮어쓰기 없이 게시한다. 준비된 journal의 입력은 고정한다. Data·최초 acquisition·성공 receipt는 하나의 DB transaction에 기록한다. 파일 게시 자체는 DB transaction 밖이므로 journal과 실제 bytes를 검사해 재개한다. 실패 정리는 해당 요청 staging만 대상으로 하고 공유 object와 사용자 원본은 삭제하지 않는다. 잠금 inode는 재사용 중인 프로세스와 분리되지 않도록 보존한다.

Migration checksum은 **UTF-8 SQL을 LF 개행으로 정규화한 bytes의 SHA-256**이다. Windows CRLF checkout과 Linux 실행에서 같은 의미의 SQL checksum을 얻는다. `migrate`와 `doctor`는 동일 helper를 사용한다. 이미 적용한 `0001_data` SQL은 고치지 않고 이후 변경은 새 migration으로 추가한다. 설치 이력 없는 기존 schema나 기존 앱 role 발견 시 자동 덮어쓰기를 거부한다. 과거 이름의 live DB 변환은 이번 신규 설치에 포함하지 않는다.

## CLI 출력과 진단

JSON stdout은 한 개의 `schema_version: 1` envelope다. `command_status`, `job_status`, `result_refs`, `result`, `warnings`, `error`를 포함한다. T02는 동기 등록만 구현하므로 `job_status`는 null이고 영속 상태는 `result.state`로 조회한다. progress/warnings는 stderr에 분리한다. 파일명과 원문 metadata의 terminal control 문자는 escape한다. `--non-interactive`는 입력을 기다리지 않는다.

| Exit | 의미 |
| --- | --- |
| 0 | 명령 성공; Data import의 경우 canonical 등록 또는 같은 성공 결과 재생 |
| 2 | usage/configuration 오류 |
| 3 | 환경 준비 불가/DB 연결·버전 문제; doctor 준비 불가 |
| 4 | 기술적 실행·파일 검증 실패 |
| 5 | request 소유 actor 불일치 등 권한 오류 |
| 6 | duplicate/idempotency/migration/등록 무결성 충돌 |
| 7 | 아직 확정할 수 없는 등록 상태 |
| 130 | Ctrl-C에 의한 명령 중단; durable request 삭제를 뜻하지 않음 |

`doctor.ready`는 T02 등록용 DB·Artifact Store 준비 상태다. MinerU는 `parser.status: not_configured`, `parser.ready: false`와 경고를 별도로 반환한다. 파서 다운로드·설치·PDF 처리·embedding/reranker 호출은 수행하지 않는다. MinerU 최신 안정판의 실제 설치·profile 기록은 T03에서 진행한다.

## 검증 명령

```powershell
docker compose -p palimpsest-t02-test build
docker compose -p palimpsest-t02-test up -d db
docker compose -p palimpsest-t02-test run --rm migrate
# 아래 SQL fixture는 빈 테스트 테이블에서 먼저 실행한다. 성공 시 ROLLBACK.
docker compose -p palimpsest-t02-test run --rm --no-deps --entrypoint python migrate tools/check_storage_sql.py
docker compose -p palimpsest-t02-test --profile test run --rm test
```

App suite는 고유 synthetic bytes와 case별 임시 Artifact Store를 쓴다. DB의 synthetic journal/Data는 삭제하지 않으므로 SQL fixture를 다시 실행하려면 새 테스트 Compose project를 사용한다. 개별 case의 임시 artifact를 정리한 이 DB는 사용자 저장소나 전체 backup fixture로 재사용하지 않는다. 문서 도구 검사와 실제 DB/파일/CLI 테스트, mock fault injection은 [실행 기록](../../progress/T02_execplan.md)에 별도로 표시한다.
