# Repository inventory — T00 관찰 결과

2026-09-13 Electron 첫UI: Electron44.3.0/PDF.js6.3.289/Packager20.3.0, vanilla renderer와읽기전용Pythonbridge를추가했다. 앱0.9.0/schema0010, Windowsportableexe를생성하고실제PDF/문서이력/질문보류/보안검사를했다. Python649개(633pass/16skip), Node경계9개, source/packaged 실제Electron검사를구분한다. [결과](../output/t09-electron/REPORT.md), [실행안내](../docs/interfaces/DESKTOP_UI.md). Dockerbackend와원문은별도준비된환경을재사용하며이번UI는읽기/검토범위다.

2026-09-12 query/UI 조사 후속: 앱0.8.0/additive0010에 Wiki/K→I→원본페이지 검색·구조답변·검증 CLI와 BGE-M3 dense/ColBERT worker를 추가했다. 실제PG index154docs/261chunks/87I, 전체앱643개(627pass/16skip), 실제Terra23회/6질문(최종4answered·2보류)을확인했다. 이는수정과독립검토를포함한기능시험이며정확도benchmark가아니다. [실물결과](../output/t07-wiki-query-ui/REPORT.md), [실행계약](../docs/interfaces/WIKI_QUERY.md), [Quartz/Wiki.js등UI조사](../docs/implementation/WIKI_UI_INTEGRATION.md). GUI설치·배포는0이다.

2026-09-12 Wiki DB 후속: `wiki_archive.py`, `wiki_knowledge_links.py`, `wiki_database.py` 및 additive 0008/0009, `wiki database-*` CLI를 추가했다. Python/Docker 앱 0.7.0, PG18.6/vector0.8.6의 격리 DB에서 592개 앱 테스트(576 pass/16 skip)를 실행했다. 논문 3·주제 22·snapshot 27·인용 72 및 exact KRevision 탐색 35개와 원래 JSON/Markdown 복원을 검증했다. [현재 계약](../docs/interfaces/WIKI_DATABASE.md), [결과](../output/t06-wiki-postgres/REPORT.md). 아래 inventory는 각 시점의 기록이다.

2026-09-11 Markdown 후속: `markdown_adapter.py`/`markdown-groups-v1`, `palim compile markdown <data_id> --json`, typed text grounding의 additive `0004_text_groundings`를 구현했다. Python3.12 Docker 앱에 markdown-it-py4.2.0/mdurl0.1.2를 배포SHA로 고정했다. 실제367개 앱 검사(16native PDF skip)와 작성문서54,581 bytes→24 I의 격리 PostgreSQL 검증을 수행했다. 아래 T00 관찰은 당시 기록이며 [현재 Markdown 실행 안내](../docs/implementation/MARKDOWN_RUNTIME.md)와 [명령·결과](../output/t03-markdown/REPORT.md)가 이 추가 범위의 현재 상태다.

조사일: 2026-09-09, Asia/Seoul. 대상: `C:/Users/DaydreamBlend/Documents/Codex/Palimpsest`. missing은 명시한 검색 범위에서 발견되지 않았다는 뜻이며, unknown은 접근 제한 또는 미실행으로 확인하지 못했다는 뜻이다.

## 저장소와 구현 상태

| 항목 | 실제 관찰 | 판정 |
|---|---|---|
| Git/branch/user changes | `git status --short` exit 1, `not a git repository`; `.git` 없음 | Git 미초기화. branch/dirty history 확인 불가 |
| 초기 파일 | `rg --files --hidden --no-ignore`로 109개. Markdown/JSON와 `tools/*.py` | 설계·검증 번들 |
| 앱 언어/패키지 관리자 | production code, manifest, lockfile 없음 | 미선택. 문서 검증 도구의 Python과 앱 언어 선택은 별개 |
| 지침 | root AGENTS/README/PLANS 및 하위 docs/AGENTS, tests/AGENTS 존재 | 기존 내용 보존 |
| CLI | entrypoint/package scripts/CLI tests 없음; `palim`은 CLI_CONTRACT의 제안 이름 | missing |
| GUI/application services | GUI 및 application service 구현 없음 | headless 앱 실행도 아직 불가 |
| DB/schema/migration | 실행 DDL, migration chain, DB config 없음 | 운영 DB 상태 unknown. DB 변경 없음 |
| provider/embedding profile | 저장소 앱 profile 없음, 조사한 관련 환경변수 이름 없음 | provider/model/dimensions 미선택. 다른 앱 credential 저장소 미조사 |

Git diff가 불가능하므로 시작 시 109개 파일의 SHA-256/bytes를 세션에 보존하고 종료 시 비교한다. `bundle_manifest.json`, `PACKAGE_VERIFICATION.md`의 기존 결과, `verification/*`는 **최초 번들 제작 시점의 근거**이며 현재 개발 파일 전체의 최신 hash 목록이 아니다. 기존 validator는 bundle_manifest 자체를 검사하지 않는다.

## 실제 module ownership map

| 책임 | 현재 code/schema/physical path | 근거와 다음 소유 범위 |
|---|---|---|
| Artifact Store / `artifact_store` | missing; 같은 이름의 루트 디렉터리 없음 | canonical §2.1. T02 bytes stage/publish/read/verify와 `artifact_path` |
| Canonical Store / `canonical_store` | missing; live DB 연결·schema 미확인 | canonical §2.2. T02 Data metadata/acquisition DB adapter |
| Compiler Runtime / `compiler_runtime` | missing | canonical §2.3. T03 execution 및 MinerU adapter |
| CLI/application service | missing | CLI_CONTRACT의 T02 help/version/doctor/data import/show/verify |
| MinerU adapter | MINERU_ADAPTER 계약 문서만 존재 | package 실행 코드 없음 |
| 문서 검증 도구 | `tools/validate_bundle.py`, `policy_checks.py`, `reassemble_canonical.py`, `test_validate_bundle.py` | 앱 모듈이 아님. 이번 코드 변경 없음 |

legacy→current mapping은 [MIGRATION](../docs/implementation/MIGRATION.md)에 있다. current canonical/contracts/interfaces/tasks/implementation 검색에서 옛 명칭은 MIGRATION의 역사 mapping 두 줄에서만 발견했다. 옛 이름을 쓰는 실행 코드·운영 schema를 발견한 것은 아니며 rename도 수행하지 않았다.

## 로컬 하드웨어와 도구

| 항목 | 관찰 결과 | 한계 |
|---|---|---|
| OS | Python platform = Windows-11-10.0.26200-SP0, AMD64; registry DisplayVersion=25H2, build=26200, UBR=9278 | registry ProductName은 Windows 10 Pro로 이름 표기 불일치. build/architecture 기준 기록 |
| CPU | AMD Ryzen 7 9800X3D 8-Core Processor | 현재 프로세스의 Environment.ProcessorCount는 8. 전체 hardware logical threads로 단정하지 않음 |
| RAM | Win32 GlobalMemoryStatusEx 성공: total 189.38 GiB, available 151.49 GiB | 조사 순간 가용량 |
| 디스크 C | free 3357.02 GiB | parser output 경로/권한 profile 미선택 |
| GPU 1 | NVIDIA GeForce RTX 5080, VRAM 16303 MiB, compute capability 12.0 | 실제 tensor/model 실행 미검증 |
| GPU 2 | NVIDIA GeForce RTX 4060 Ti, VRAM 16380 MiB, compute capability 8.9 | 두 GPU VRAM 자동 합산을 가정하지 않음 |
| NVIDIA driver/toolkit | driver 616.56; nvcc release 13.3 / V13.3.73 | Torch/LMDeploy 호환성 증거가 아님 |
| PowerShell | 7.6.5 | 현재 shell |
| Python | 기본 PATH의 python/python3/py/pip 없음. 번들 interpreter 3.12.14, AMD64 사용 가능 | 앱 production runtime 채택은 아님 |
| Python packages 일부 | 번들에 pip 26.2.1, numpy 2.3.5. MinerU/magic-pdf/Torch/psycopg/SQLAlchemy/Alembic/pytest는 조회 대상 distribution 중 없음 | 이 interpreter에 한정 |
| uv | 0.12.3, 사용자 `.local/bin/uv.exe` | managed Python 디렉터리 읽기 실패, 환경 목록 unknown |
| Node/Git | Node v24.19.0, Git 2.53.0.windows.3, Codex 번들 경로 | npm/dotnet/cargo/rustc PATH missing |
| Docker | CLI 29.7.2 | config 읽기와 engine named pipe 접근 거부. server/container 상태 unknown |
| WSL | system32/wsl.exe 존재 | distro 조회 E_ACCESSDENIED, 배포판/runtime unknown |
| PostgreSQL | psql/pg_isready/postgres PATH missing; `C:/Program Files/PostgreSQL` 없음 | Docker/WSL/다른 위치 DB unknown. 접속·migration 미실행 |

검증에 사용한 기존 번들 Python 경로:

```text
C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe
```

환경 도구가 반환한 실행 파일을 사용했다. 새 Python/패키지 설치나 사용자 PATH 변경은 하지 않았다.

## MinerU readiness와 공식 자료

- 현재 PATH에 `mineru` 없음. 저장소 `.venv`/`venv`도 없고 번들 interpreter에 MinerU distribution이 없다. `mineru --version`/`mineru --help`는 실행하지 않았다. PC 전체의 미등록 환경은 unknown이다.
- 사용자 홈의 `mineru.json`, `magic-pdf.json` 없음. 기본 Hugging Face hub cache는 읽을 수 있었으나 이름에 MinerU/PDF-Extract/unimernet/DocLayout이 해당하는 모델 디렉터리는 없었다. 기본 ModelScope hub cache 없음. 다른 위치 모델 readiness는 unknown이다.
- 현재 프로세스 환경변수 이름 중 `MINERU*`, `MAGIC_PDF*`, `HF_HOME`, `HF_HUB_CACHE`, `HUGGINGFACE_HUB_CACHE`, `MODELSCOPE_CACHE`, `CUDA_VISIBLE_DEVICES`, `PALIM*`, `PGHOST`, `PGPORT`, `PGDATABASE`, `DATABASE_URL`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `HF_TOKEN`, `HUGGING_FACE_HUB_TOKEN`은 없었다. 값이나 env 파일 본문은 출력하지 않았다.
- 선택된 profile이 없어 effective backend/endpoint/model digest/output directory는 unknown이다. 기본 실행이 offline이라고 가정하지 않는다. 설치·모델 다운로드·PDF 업로드·추론은 수행하지 않았다.

공식 GitHub latest와 PyPI에서 조사한 배포 후보는 **MinerU 3.4.5**, PyPI 업로드일은 2026-08-14다. 같은 release tag의 `mineru/version.py`에는 **3.4.4**가 선언되어 있다. T01에서 배포 artifact metadata와 설치 후 reported version을 대조하기 전까지 검증된 profile로 pin하지 않는다. [공식 release](https://github.com/opendatalab/MinerU/releases/tag/mineru-3.4.5-released), [PyPI](https://pypi.org/project/mineru/), [태그 version.py](https://github.com/opendatalab/MinerU/blob/mineru-3.4.5-released/mineru/version.py)

| 후보 | 공식 근거 | T00 판단 |
|---|---|---|
| Windows Python 3.10–3.12 | package metadata는 3.10 이상 3.14 미만이나 Windows 안내는 ray 때문에 3.12까지 제한 | Python 3.12.14는 후보 범위. 전용 환경·dependency lock은 T01 선택 |
| pipeline CPU/GPU | CPU 지원. RAM 최소 16 GB/권장 32 GB 이상, 디스크 최소 20 GB. GPU 경로 VRAM 최소 4 GB | 하드웨어 수치상 조사 후보. OCR/속도/의존성 검증 없음 |
| hybrid-engine / vlm-engine | 순수 CPU 미지원; VRAM 최소 8 GB. Windows 추가 backend 후보 LMDeploy/Torch | 각 GPU 용량은 기준 이상이나 세대/driver/Torch/backend 실호환성 unknown |

표는 [공식 Quick Start](https://opendatalab.github.io/MinerU/quick_start/), [해당 release README](https://raw.githubusercontent.com/opendatalab/MinerU/mineru-3.4.5-released/README.md), [pyproject](https://raw.githubusercontent.com/opendatalab/MinerU/mineru-3.4.5-released/pyproject.toml)의 upstream 요구사항이다. 현재 PC에서 실행에 성공했다는 뜻이 아니다. upstream core extra 자체에 gradio가 포함되어 있어 필요한 CLI 의존성 조합과 parser 내부 의존성을 구분해야 한다.

태그 모델 참조 후보는 `opendatalab/MinerU2.5-Pro-2605-1.2B`와 `opendatalab/PDF-Extract-Kit-1.0`이다. 모델 revision/digests, 필요 파일 집합, 모델별 license와 용량은 미검증이다. [태그 ModelPath 정의](https://raw.githubusercontent.com/opendatalab/MinerU/mineru-3.4.5-released/mineru/utils/enum_class.py)

공식 CLI 기본 backend는 hybrid-engine이며, 내부 local API와 http-client용 backend URL은 다른 설정이다. 모델 source는 기본적으로 네트워크 확인/다운로드를 할 수 있다. T01 profile은 backend와 local 모델 경로를 명시하고 실효 환경설정/endpoint를 검사해야 한다. `MINERU_MODEL_SOURCE=local`도 모델 준비의 증거를 대신하지 않는다. [공식 CLI](https://opendatalab.github.io/MinerU/usage/cli_tools/), [Model Source](https://opendatalab.github.io/MinerU/usage/model_source/)

## 실행한 검사와 오류

| 명령 | 결과 |
|---|---|
| `git status --short` | exit 1, Git repository 아님 |
| `rg --files --hidden --no-ignore` | exit 0, 시작 시 109개 파일 |
| `Get-Command`으로 runtime/DB/parser 명령 조회 | 위 표의 경로 또는 missing 확인 |
| `Get-CimInstance Win32_OperatingSystem -ErrorAction Stop` | exit 1, 접근 거부. 같은 묶음의 후속 CIM 조회 중단 |
| Python platform/importlib.metadata/ctypes GlobalMemoryStatusEx inline probe | exit 0, 위 runtime/package/RAM 관찰값 반환 |
| `Get-ItemProperty -LiteralPath 'HKLM:/HARDWARE/DESCRIPTION/System/CentralProcessor/0' -Name ProcessorNameString,Identifier` | 오류 없이 CPU 식별 문자열 반환. 앞선 전체 property 조회의 Byte[]→Int32 오류를 필드 한정으로 해결 |
| `nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap --format=csv,noheader` | exit 0, GPU 두 개 반환 |
| `nvcc --version`, `uv --version`, `node --version`, `git --version` | 각 exit 0, 위 버전 반환 |
| `uv python list --only-installed` | cache 초기화 오류. 뒤의 독립 명령 성공이 이 실패를 지우지 않음 |
| `uv python list --only-installed --no-cache` | exit 2, managed Python 디렉터리 접근 거부 |
| `docker --version` | exit 0, config 접근 거부 경고 동반 |
| `docker info --format '{{.ServerVersion}}'` | exit 1, Docker engine 접근 거부 |
| `wsl --list --quiet` | exit -1, Wsl/EnumerateDistros/Service/E_ACCESSDENIED. 출력 인코딩 일부 깨짐 |
| 환경변수 이름·config/cache 존재 여부 조회 | 첫 PowerShell foreach 뒤 pipe 구문은 parse error(exit 1). 배열로 수집한 재실행 exit 0 |
| `rg -n -i 'horreum\|bibliotheca\|scriptorium' docs/canonical docs/contracts docs/interfaces docs/implementation tasks` | exit 0, MIGRATION.md의 역사 mapping 2줄 |

문서/도구 검증은 아래 **실제 실행 명령**을 사용했다. PYTHONUTF8은 해당 자식 shell 프로세스에만 설정한다. `-B`로 bytecode cache 생성을 막는다.

```powershell
$env:PYTHONUTF8 = '1'
& 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B tools/validate_bundle.py --json
& 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -m unittest discover -s tools -p 'test_*.py' -v
```

첫 실행: validator exit 0, errors 0; unit/mutation **26개 통과**, exit 0 (6.941초). source 2,331줄/13 slices, current 2,360줄/13 slices, 원본 invariant 45개, acceptance specs 105개, U01–U03을 검사했다. unit test는 OS 임시 디렉터리에 번들 사본을 만들어 변조·정리하며 DB에 접속하지 않는다. 최종 문서 변경 후 결과는 [T00 실행 계획](T00_execplan.md)에 기록한다.

Build/lint/typecheck/application test 명령은 **발견하지 못했다**. 위 두 명령만 이 환경에서 실행 검증된 문서/검증 도구 명령이다. current/baseline 재결합은 unit test에서 byte equality를 검사했으므로 별도 출력 파일은 만들지 않았다.

## Acceptance와 검증 수준

| 항목 | T00 결과 | 남은 검증 |
|---|---|---|
| AT64 | 실제 inventory와 실행 명령 기록으로 T00 수동 검토 기준 충족 | T01 앱 profile의 명령 확정 |
| AT88 | current 문서 명칭 검색 및 기존 naming policy test 통과 | production code/schema 명칭은 T02 이후 검증 |
| AT102 | 진단 중 설치/다운로드/업로드 없음 | **미실행**: CLI doctor 부재. T02/P10/P12 인계 |
| 앱/mock unit | 실행 없음 | production code 없음 |
| 실제 PostgreSQL integration | 실행 없음 | 실행 환경/접속/profile 미확정 |
| 실제 MinerU/PDF | 실행 없음 | parser/model/backend 미준비 |
| e2e/live semantic evaluation | 실행 없음 | 후속 구현·명시적 provider 권한 필요 |

105개 AT의 catalog 상태는 spec_only 유지. T00 조사 완료는 앱 acceptance 완료가 아니다.

## T01 인계와 승인 대상

- U01–U03은 재승인 대상이 아니다. GUI는 T13 deferred다.
- **F26/P12:** 기존 앱 stack은 없다. 관찰된 Python 3.12와 stdlib CLI 도구는 검토 후보지만 앱 언어/CLI library/명령·exit schema/DB driver·migration 도구/실행 profile은 T01에서 구체안으로 선택·승인해야 한다. 번들 Python을 배포 runtime으로 암묵 채택하지 않는다.
- PostgreSQL은 canonical의 방향과 맞지만 서버/개발·테스트 DB 환경은 unknown이다. Docker/WSL 접근 제한을 해결하거나 다른 승인된 DB 환경이 필요하다.
- MinerU 3.4.5 후보의 버전 identity 불일치, GPU별 Torch/runtime 호환성, backend·model digests·local endpoint·output schema는 T01 검증 대상이다. 현재 설치 명령을 검증 완료로 기록할 근거는 없다.
- **P10(F22/F23) 및 P12(F26)**는 T02 production 구현의 선행 승인이다. P10의 storage publish/reconciliation·보안/운영 정책을 이번 inventory로 승인하지 않았다. P01–P12 전체는 proposed다.
- 뒤 단계의 다른 P 계약/finding은 해당 task에서 검토한다. 이번 작업은 T00 경계에서 종료한다.

## T02 후속 구현 inventory — 2026-09-09

위 내용은 T00 당시의 조사 결과로 보존한다. U09/U10 및 사용자 후속 실행 지시로 T02 Data vertical slice를 구현했다. 이제 Python package/lock, Dockerfile/Compose, 실제 migration/CLI/서비스/파일 저장/DB 저장과 tests/app가 있다. Git은 여전히 초기화하지 않았다.

| 실제 경로 | 책임 |
| --- | --- |
| `src/palimpsest/data.py` | Data SHA-256, request UUIDv7, 고정 command fingerprint |
| `src/palimpsest/artifact_store.py` | Linux 관리 파일 복사·잠금·게시·검증·정리 |
| `src/palimpsest/canonical_store.py` | PostgreSQL Data/acquisition/journal transaction, migration/진단 |
| `src/palimpsest/service.py` | Data 등록·조회·중복/재시도·복구 use case |
| `src/palimpsest/cli.py`, `config.py` | argparse/JSON/안전 오류·명시적 DSN 설정 |
| `src/palimpsest/migrations/0001_data.sql` | 최초 D schema; 후속 schema는 새 migration으로 확장 |
| `tests/app/` | 파일16, CLI/config unit14, bootstrap3, PG Data18, CLI workflow1 |
| `tools/container_init.py`, `run_app_tests.py`, `check_storage_sql.py` | Compose credentials/volume 준비, 명시적 테스트 실행, SQL fixture 실행 |

Build: `docker compose -p palimpsest-t02-test build`. App test: `docker compose -p palimpsest-t02-test --profile test run --rm test`. SQL fixture는 [T02_RUNTIME](../docs/implementation/T02_RUNTIME.md)의 순서대로 빈 독립 테스트 DB에서 먼저 실행한다. lint/typecheck 도구는 아직 별도 도입하지 않았고 package build·unittest·문서 도구 AST 검사를 수행했다. 실제 명령/exit/소요와 공개 이미지/lock은 [T02 실행 기록](T02_execplan.md)에 있다. 전체 MinerU/LLM/DIKWPB e2e는 아직 없다.


## T03 이전 의미 실험 inventory — 역사 기록

현재 사용자 PDF의 D→D2I→I 실물 시험을 완료했다. T03 전체 gate는 in_progress다. 이전 T00/T02의 부재 관찰은 당시 기록이다. Python package0.2.0, PostgreSQL18.6/pgvector0.8.6, `0001_data` 보존 + `0002_information` 추가 적용, 실제 앱139tests pass. [결과](T03_result.json), [실행 명령과 검증 구분](T03_execplan.md), [실행 안내](../docs/implementation/T03_RUNTIME.md).

| 실제 경로 | 책임 |
| --- | --- |
| `src/palimpsest/information.py` | Text/Image 의미 payload·구조 검사·fingerprint |
| `src/palimpsest/mineru_adapter.py` | 실제 MinerU middle v2 정규화·원문별 region·image hash |
| `src/palimpsest/d2i.py`, `codex_provider.py` | 독립 Generator/Validator 호출과 source/proposal receipt binding |
| `src/palimpsest/compiler_runtime.py`, `worker_claim.py` | durable execution/Record/candidate/atomic I·grounding·outbox/동기 worker 배타 처리 |
| `src/palimpsest/migrations/0002_information.sql` | immutable Information·grounding·profile·실행·영속 판정·temporary candidate·outbox와 lifecycle guards |
| `tools/run_d2i.py` | 호스트 Codex OAuth와 로컬 parser/app Docker를 연결하는 명시적 worker |
| `deploy/mineru/` | 별도 MinerU3.4.5 이미지, exact 모델 준비/검증, 원본 hash/페이지 geometry 검사 |

Build: `docker compose -p palimpsest-t03-verify build`; test: `docker compose -p palimpsest-t03-verify run --rm --no-deps test` (먼저 task-local 빈 DB/migration 준비). 실제 model/원문은 별도 동의가 필요하며 이번 파일+Codex OAuth에는 사용자가 이미 선택했다. lint/typecheck 별도 도구는 도입하지 않았다. Docker 시험 자원은 요청에 따라 정리했고 모든 모델/DB/artifact 볼륨은 보존했다. 개발 DB와 최종 앱/MinerU/PG18 이미지는 남아 있다.


## U11 현재 source D2I inventory — 2026-09-09

현재 D2I는 LLM 호출0회인 source-information-v1이다. information.py/source_units.py/d2i.py가 exact 원문단위·fingerprint·완전성 검사를 담당하고 figure_adapter.py/figure_coverage.py가 reviewed whole Figure refs를 연결한다. compiler_runtime.py는 materialize_source와 shared atomic commit을 제공한다. cli.py의 공개 jobs materialize와 tools/run_d2i.py에는 모델호출이 없다. 이전 semantic 코드는 legacy_semantic_d2i.py로 보존하며 현재 CLI에서 호출하지 않는다.

0003_source_information 확장을 disposable PG18에서 먼저 검증한 뒤 dev DB에 적용했다. 기존 0001/0002 migration과 I34개 이력은 불변이다. 실제 source I189·원문249개·grounding255개를 확인했다. Build: `docker compose -p palimpsest-t03-verify build app`. App test: `docker compose -p palimpsest-t03-verify run --rm --no-deps test` →190tests/27.582초/exit0/skip0. 기존 실패174tests 중2errors는 legacy import와 crossDatafixture schema marker를 수정한 뒤 해소했다. 결과 [T03_source_result](T03_source_result.json)를 따른다.


### 페이지 조회 후속 slice

`page_projection.py`와 `CompilerRuntime.page_view`, `information pages/context` CLI를 추가했다. 기존 schema/DB 행·I 불변, projection만 읽기 전용 생성한다. `tests/app/test_page_projection.py`의12개 단위 회귀를 포함해 전체202tests/24.832초/exit0이다. Build/test 명령은 위 T03 전용 Compose와 같고 결과는 [T03_page_result](T03_page_result.json)를 따른다.
