# 실행 환경 — U01–U10 적용, 나머지 P12 승인 전

## 현재 T03 실행 상태

제공 native PDF14쪽을 MinerU3.4.5 pipeline/로컬 Docker/RTX4060Ti로 실제 파싱하고 Codex OAuth gpt-5.6-terra/medium 두 역할로 Text23/Image5를 저장했다. PG18.6/vector0.8.6, schema0002_information, 앱139tests 통과. [T03 실행 안내](T03_RUNTIME.md)와 [실제 결과](../../progress/T03_result.json)를 따른다. 개발 DB와 최종 이미지/볼륨은 보존하고 시험 컨테이너/구이미지는 정리했다. 아래 T02/T00/U10은 당시 관찰이다.

## T02 당시 실행 상태

2026-09-09 T02에서 Python 3.12.14/psycopg 3.3.5와 Linux amd64 Docker profile을 구현했다. 실제 서버는 PostgreSQL **18.6** (`180006`), pgvector **0.8.6**이며 `0001_data`를 독립 DB에 적용했다. CLI/파일/DB 등 앱 테스트 52개가 통과했다. [고정 image digest·lock·구성·실행 명령](T02_RUNTIME.md)과 [실행 근거](../../progress/T02_execplan.md)를 따른다. 아래 T00/U10 관찰은 각 당시 기록이며 현재 앱 부재를 뜻하지 않는다.

승인 실행 경로에서 image pull/build·컨테이너/volumes 생성·실제 DB 연결·migration/fixture·CLI 실행이 가능했다. 일반 sandbox의 pipe 접근 제한은 유지한다. 테스트 project는 `palimpsest-t02-test`, 개발용 문서 profile은 `palimpsest-dev`로 분리한다. 사용자 원문이나 기존 DB를 사용하지 않았고 MinerU/모델은 아직 설치하지 않았다.

## 확인된 것과 미확인인 것

확인된 자료는 2026-09-09 canonical Markdown입니다. 실제 Git repository, 앱 코드, OS 런타임, Python/Node/.NET 버전, DB 접속, migration 도구, provider credential과 실행된 앱 테스트는 이 패키지 제작 과정에서 조사하지 않았습니다.

U09는 PostgreSQL 최소 major 18, 최초 18 계열과 pgvector를 선택합니다. Canonical Store와 Compiler Runtime은 같은 database의 별도 schema에서 transaction을 공유합니다. U10은 앱 언어 Python과 Docker 기반 실행·배포를 확정합니다. Python exact version·CLI/worker library·DB driver/migration runner와 구체 container profile은 별도입니다. U04/U05의 검색 모델 계열과 MinerU 버전 정책을 유지하며, T00의 실제 환경 조사와 당시 관찰은 [inventory](../../progress/repository_inventory.md)에 있습니다.

## T00 조사 항목

project root/branch/dirty changes, package manifests/lockfiles, 기존 AGENTS/README, dependency manager, migration chain, test suites, local artifact path, mock/live mode, 실제 build/test/lint/typecheck commands를 기록합니다. env 파일 내용/secret은 출력하지 않습니다.

## 권장 접근 — 제안

기존 repo가 있으면 승인된 선택과 호환되는 stack을 유지합니다. greenfield라면 먼저 single-process + PostgreSQL 18/pgvector + deterministic provider mocks의 작은 vertical slice를 제안합니다. Docker 기반의 구체 service/volume/port·image profile, CLI framework/library 버전과 MinerU version/backend/profile은 선택 근거와 설치 가능성을 확인해 고정합니다. PDF parser 제품은 이미 MinerU이며 GUI framework 선택은 T13까지 하지 않습니다.

live OpenAI 또는 다른 provider 사용은 별도 허용이 필요합니다. 이 문서는 API key를 요구하거나 생성하거나 실제 호출하지 않습니다. 사용자의 source를 외부로 전송하는 범위와 비용 승인은 따로 확인합니다. 무제한 semantic propagation이 무제한 외부 비용 지출 권한을 뜻하지는 않습니다. 비용 때문에 멈추면 paused/partial로 남기며 completed로 위장하지 않습니다.

## Codex local environment

검증된 setup/test 명령이 생긴 후 Codex의 프로젝트 local environment에 연결합니다. 현재 문서에 맞는 command가 없는데 그럴듯한 npm/uv/docker 명령이나 `.codex` 설정 문법을 지어내지 않습니다. OpenAI 공식 자료는 [REFERENCES](../../codex/REFERENCES.md)에 있습니다.

## 최소 필요한 실행 분리

개발용 DB, test DB, 사용자 실제 DB를 분리합니다. worktree 별 DB/schema/artifact root도 분리합니다. 테스트 중 원본 user storage를 쓰지 않습니다. model/prompt/schema/retrieval profiles는 versioned config로 관리하며 credentials와 분리합니다.


## 확정된 범위와 추가 inventory

현재 interface=CLI, GUI=T13 deferred, PDF parser=MinerU, 구성요소=Artifact Store/Canonical Store/Compiler Runtime이다. U04는 embedding `BAAI/bge-m3`(dense 1024)와 동일 모델의 multi-vector ColBERT 점수를 이용한 재순위화, U05는 MinerU 최신 안정판 선택 정책을 확정한다. 앱 언어는 U10의 Python이고 Docker로 실행·배포한다. exact toolchain/CLI library와 backend/model/hardware의 실행 검증은 별도다.

T00은 OS/CPU architecture/GPU/accelerator runtime/memory, MinerU 설치 여부·version/help, 모델 cache 준비 상태, parser config와 endpoint의 local/remote 여부, file permissions를 확인한다. secret values는 출력하지 않는다. `doctor`는 진단 중 자동 모델 다운로드나 문서 외부 업로드를 수행하지 않는다.

실제 parser 설치·모델 다운로드·DB migration은 해당 실행 권한과 environment profile을 확인한 뒤 진행한다. MinerU 사용을 승인한 것은 사용자 원문을 공개 hosted API로 전송하도록 승인한 것이 아니다. 상세 adapter 요구는 [MINERU_ADAPTER](../interfaces/MINERU_ADAPTER.md)를 읽는다.

MinerU는 설치/명시적 업그레이드 시점의 공식 최신 안정판을 선택하고 그 실행에서 사용할 exact package version/digest와 model/backend/adapter profile을 기록한다. 2026-09-09 확인값 3.4.5는 설치 성공이나 영구 pin이 아니다. 모델·버전의 승인 근거와 출처, 미정값은 [U04/U05](../decisions/USER_OVERRIDES.md)를 따른다.

Embedding/Reranker는 독립 교체 가능한 profile을 사용한다. 향후 Qwen3-Embedding/Reranker 4B·8B는 후보이며 현재 기본값을 바꾸거나 미리 설치하지 않는다. 역할별 input/output과 dimension·score 호환성 및 재색인 경계는 [RETRIEVAL_PROFILE](../interfaces/RETRIEVAL_PROFILE.md)에 있다.

U06에 따라 한 애플리케이션 안에서 domain/변환 모듈을 분리하고 저장·실행·전파·commit 구현을 공유한다. 논리 모듈과 단계별 구현/테스트 책임은 [MODULE_BOUNDARIES](MODULE_BOUNDARIES.md)에 있다. MinerU의 격리된 로컬 runtime은 parser adapter의 실행 세부사항이며 모듈마다 별도 서비스/DB를 요구하지 않는다. Python packaging·import 검사 명령은 실제 P12 실행 profile 구체화 후 확정한다.

## U09 — DB 실행 profile

설치/명시적 갱신 시 PostgreSQL 18의 최신 안정 minor와 호환 pgvector 안정 릴리스를 확인하고 server_version/server_version_num, pgvector extversion, 배포 artifact 또는 image digest를 기록한다. 2026-09-09 공식 조회값은 18.6/0.8.6이며 설치 기록이 아니다. PG19 이상은 정식 출시 후 테스트 사본의 업그레이드·복구·호환성 검증을 거친다. `>=18` 또는 latest tag만으로 자동 전환하지 않는다.

PG18 내장 uuidv7()를 신규 opaque ID에 사용한다. data_id는 실제 보존 bytes의 SHA-256이다. [U09 저장 계약](../decisions/STORAGE_IDENTITY.md)과 [T02 SQL 초안](../schema/T02_STORAGE_SCHEMA.md)은 이 선택을 구체화하지만 DB 설치·migration 적용이나 P12의 언어/driver/migration runner 선택을 완료한 것은 아니다.

## U10 — Python/Docker와 현재 Docker 접근

앱 언어는 Python, 실행·배포 기반은 Docker로 확정됐다. CLI 우선·도메인/변환 모듈화·PostgreSQL 18/pgvector와 같은 DB의 cross-schema transaction을 유지한다. 호스트의 번들 Python을 배포 runtime으로 암묵 채택하지 않는다. 실제 Python image/version/digest, package lock, CLI/DB driver/migration runner와 service/volume/port는 후속 실행안에서 고정한다. Compose는 설치 확인만 했으며 구체 배포 파일은 아직 없다.

2026-09-09 읽기 관찰: 일반 sandbox의 docker info는 config 파일과 engine pipe 접근 거부(exit 1), 같은 명령의 require_escalated 실행은 server 29.7.2 반환(exit 0). 추가 info는 linux/x86_64, compose version은 5.5.1(exit 0)을 반환했다. Docker ACL/설정 변경·image pull·container 생성·DB 접속은 하지 않았다. 따라서 이전 접근 거부는 일반 sandbox 범위의 관찰이고 현재 승인 실행 경로에서는 engine 조회가 가능하다. 접근 가능한 범위는 수행한 읽기 명령으로 한정해 보고한다.


## U11 현재 D2I 실행 경계

위의 Codex OAuth Generator/Validator 관찰은 이전 의미 실험 이력이다. 현재 tools/run_d2i.py는 모델 provider를 import/call하지 않고 MinerU parser와 script-based source materialization을 사용한다. 원본 parser는 MinerU3.4.5 pipeline의 기존 exact profile/모델/이미지를 재사용했다. U11 source 생성 당시 앱 image ID는 `sha256:4f6dc7e177db23d21344b5de24e7a8d64e4073fa163a1592bdcedbd851604cb6`이었다. 페이지 조회를 추가한 현재 `palimpsest-t03:0.2.0`은 `sha256:594c68dcf8b7ebab5461f45a041e78dce407b8c44368aabc645978c268ceb528`이며 전체202개 회귀를 통과했다. PG18.6/pgvector0.8.6에0003_source_information이 추가됐고 이전migration은불변이다. source 결과189 I/LLM0회와190개앱테스트통과를 [실행 결과](../../progress/T03_source_result.json)에 기록한다. 테스트컨테이너는정리하고 개발DB·이미지·모든볼륨을보존했다.
