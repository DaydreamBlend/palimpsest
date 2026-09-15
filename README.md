# Palimpsest

원문과 판단 근거를 보존하는 로컬 지식 Wiki이자 지식 컴파일러다. 논문 PDF, Markdown, Python 코드 같은 자료에서 정보를 추출하고, 검증된 지식과 설명을 구성하면서 각 결과가 어떤 원문과 판단에서 나왔는지 추적한다.

Python/Docker backend가 저장·검증·컴파일을 담당하고, Electron 앱이 자료·원문 근거·지식·Wiki를 탐색하는 화면을 제공한다. 현재는 개발 중이며, backend 기능과 앱에서 직접 실행할 수 있는 기능의 범위가 다르다.

**구현 버전, 실제 검증 결과, 남은 작업은 [현재 상태](progress/STATUS.md)에서 관리한다.** 이 README는 프로젝트의 개념과 시작 경로를 안내한다. 상세 계약은 [문서 인덱스](docs/INDEX.md)에서 찾을 수 있다.

## 핵심 개념

| 단계 | 의미 | 보존하는 내용 |
|---|---|---|
| **D · Data** | 등록한 원본 자료 | 정확한 원문 bytes, SHA-256, 취득 정보와 자료 버전 |
| **I · Information** | 원문에서 추출한 정보 단위 | 본문·표·그림 등 추출 내용, 페이지·영역·코드 위치, 파싱 실행과 profile |
| **K · Knowledge** | 원문에 보고된 내용을 결합한 지식 또는 검증된 전제로부터 얻은 추론 | 정확한 근거, 의미 revision, 원문 기반·추론 기반의 구분과 한계 |
| **W · Wisdom** | 질문과 맥락에 맞춰 지식으로 구성한 설명·추천 | 사용한 K와 관계, 가정·불확실성, 독립 검증 결과 |
| **P · Parchment** | 검증된 W를 순서대로 구성한 문서 | 구성에 사용한 정확한 W와 변경 불가능한 문서 snapshot |

주요 흐름은 다음과 같다. 각 화살표는 별도 처리·검증 단계이며, 자료를 열었다고 전체 과정이 자동 실행되는 것은 아니다.

```text
원본 D ──D2I──> 정보 I ──I2K──> 지식 K
                                  │
                       수락된 K·관계 ──K2K──> 새로운 추론 K
                                  │
                           질문·맥락과 함께
                                  ↓ K2W
                              설명·추천 W
                                  ↓ W2P
                                문서 P ──> Wiki
```

- **D2I:** 결정적 스크립트와 선택된 MinerU 내부 OCR/layout VLM으로 원문을 추출한다. application LLM으로 I를 요약하거나 중요도에 따라 제거하지 않는다.
- **I2K:** 선택한 source I 전체를 검토하고 명시적으로 보고된 내용을 결합한다. I가 누락되거나 잘못된 경우 오류를 보고하고 영향받은 K를 보류한다.
- **K2K:** 수락된 정확한 K·관계를 전제로 새로운 결론을 만든다. 원문의 주장과 새 추론의 출처를 구분한다.
- **K2W·W2P:** 지식에 근거한 설명·추천을 검증하고 문서로 구성한다. 추천은 권한 있는 확정 Decision을 대신하지 않는다.

Wiki는 P를 표시하고 K는 별도 지식 뷰에서 탐색한다. 기존 I 기반 Wiki 요약도 역사적 결과로 보존하며, 이를 새 W/P 파이프라인의 결과로 바꾸어 표시하지 않는다. 원본을 직접 해석하는 별도 **D2K**는 정확히 선택한 자료에 대한 별도 사용자 요청이 필요하다.

### Realm과 근거 보존

**Realm**은 프로젝트나 주제별로 자료를 묶고 컴파일 범위를 정하는 단위다. 하나의 자료가 여러 Realm에 속할 수 있으며, 같은 Realm에 논문과 코드를 함께 둘 수 있다. 새 자료 등록은 Realm 소속 기록을 완료해야 컴파일로 이어진다. 새 I2K와 자동 K2K·전파는 Realm 내부를 기본 범위로 사용하고, 범위를 넘는 입력은 명시적으로 선택한다.

원본 D는 원문 bytes의 SHA-256으로 식별하고, 다른 신규 opaque ID는 UUIDv7을 사용한다. 원문·과거 revision·실행 기록을 보존하며, 같은 의미의 지식을 재사용하거나 근거를 추가할 때 불필요한 의미 revision을 만들지 않는다. 관계의 방향·적용 범위와 모순을 구분하고, 보류·실패·미확인을 거짓으로 취급하지 않는다.

## 현재 사용할 수 있는 기능과 개발 범위

- **원문과 정보:** 원본 등록·중복 방지·자료 버전, PDF/Markdown/Python D2I, 추출 정보에서 정확한 원문 위치로 돌아가는 탐색.
- **지식과 관계:** source-only I2K, 독립 검증·검토, 동등한 K 재사용, typed 관계와 K2K 추론, 변경 전파와 중단·재개.
- **Desktop:** 여러 저장소의 자료·원문·I·K·기존 Wiki·P 탐색과 Realm 소속 수정.
- **검색과 설명:** 기존 Wiki의 BGE-M3 검색·근거 질문 CLI, 명시적으로 선택한 K·관계에 대한 K2W와 W2P.

앱의 신규 자료 등록·컴파일·질문 실행 연결, 논문·주제별 K 선택과 설명 일괄 생성, K 변경에 따른 정식 W/P 자동 갱신 등은 후속 작업이다. 기존 사용자 DB에 새 schema를 일괄 적용한 상태도 아니다. 우선순위는 [현재 backlog](progress/IMPLEMENTATION_BACKLOG_2026_09_14.md)를 따른다.

구현 여부와 실제 자료에 대한 실행 완료는 구분한다. 특히 W/P의 최근 검증에는 synthetic fixture가 사용되었으며, 이를 실제 논문 설명 품질 평가로 해석하지 않는다. 상세 수치와 검증 범위는 [현재 상태](progress/STATUS.md)와 연결된 보고서를 확인한다.

## 기술 구성

| 구성 | 역할·요구사항 |
|---|---|
| Python 3.12 | backend와 `palim` CLI. 지원 범위·의존성은 [pyproject.toml](pyproject.toml) |
| Docker / Docker Compose | backend, PostgreSQL, parser 등의 실행 환경. 기본 구성은 [compose.yaml](compose.yaml) |
| PostgreSQL 18 + pgvector | canonical 데이터·revision·관계·실행 상태와 검색 데이터 저장 |
| Artifact Store | 원본과 파싱·모델 실행 근거 파일 보존 |
| Electron + PDF.js | Desktop과 등록 원본 PDF 표시. Node.js 요구사항과 버전은 [desktop/package.json](desktop/package.json) |
| MinerU / BGE-M3 | PDF OCR·layout 추출 / 기존 Wiki 검색 embedding. 모델과 실행 환경은 별도로 준비 |

## 실행과 개발 환경

### 기존 설치에서 앱 실행

Windows에서 [Palimpsest.cmd](Palimpsest.cmd)를 실행한다. 런처는 workspace의 공용 Electron 엔진과 보존된 앱 패키지를 사용한다. 필요한 파일은 다음과 같다.

- Electron: `desktop/node_modules/electron/dist/electron.exe`
- 앱 패키지: `output/t24-wisdom-realm/release-final/app.asar`
- 연결 대상 Docker 환경·DB·artifact volume과 해당 환경에 맞는 저장소 설정

여러 저장소의 설정은 `.local/electron-ui/stores.json`, Realm 설정은 `.local/electron-ui/realm.json`에 둔다. [저장소 설정 예시](desktop/stores.example.json)와 [Realm 설정 예시](desktop/realm.example.json)는 기존 로컬 환경의 연결을 보여 주며, 다른 PC에서 그대로 사용할 수 있는 빈 DB 초기 설정이 아니다. 설정 우선순위와 필드는 [통합 Desktop 계약](docs/interfaces/UNIFIED_DESKTOP.md)을 따른다. 실제 최신 패키지 경로는 현재 런처와 [현재 상태](progress/STATUS.md)를 기준으로 한다.

### 새 clone에서 소스 확인·개발 준비

이 저장소는 소스·설계·보고서 백업이며 완전 자동 설치 배포판은 아니다. clone만으로 기존 DB, 원문, 모델, Docker volume 또는 패키지 앱이 복원되지는 않는다.

Python 3.12가 설치된 환경에서 CLI 개발 환경을 준비할 수 있다. 아래는 Windows PowerShell 기준이며 프로젝트 루트에서 실행한다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\palim.exe --help
.\.venv\Scripts\palim.exe --version
```

위 명령은 Python 패키지와 CLI 준비 단계다. 자료 조회·등록·컴파일에는 DB와 Artifact Store 설정이 추가로 필요하고, PDF 추출·모델 단계에는 해당 worker와 모델이 필요하다. DB 초기 구성은 [저장소 실행 안내](docs/implementation/T02_RUNTIME.md), PDF 경로는 [MinerU 계약](docs/interfaces/MINERU_ADAPTER.md)을 확인한다. 과거 안내의 이미지 이름·버전을 최신 배포값으로 간주하지 않는다.

Desktop 소스 개발은 Node.js 요구사항을 충족한 뒤 진행한다.

```powershell
cd desktop
npm ci
npm run install:electron
npm start
```

`npm start`는 소스 앱을 연다. 실제 자료 탐색에는 앞서 설명한 저장소 연결이 필요하다. 배포용 assets 구성은 [패키징 도구](tools/package_desktop.cjs)를 따른다.

CLI의 실제 지원 명령은 `palim --help`와 각 하위 명령의 `--help`로 확인한다. [CLI 계약](docs/interfaces/CLI_CONTRACT.md)에는 과거 제안도 포함되어 있으므로 모든 예시를 현재 구현된 기능으로 해석하지 않는다. 기존 사용자 DB의 migration과 새 자료의 모델 전송은 별도 범위로 검토한다.

## 저장소 구조

| 경로 | 내용 |
|---|---|
| `src/palimpsest/` | backend, CLI, 저장·컴파일·검증 서비스와 SQL migration |
| `desktop/` | Electron 앱, PDF 표시, 연결 설정 예시와 UI 관련 테스트 |
| `deploy/` | parser·검색 등 별도 실행 환경의 Docker 구성 |
| `tools/` | 실행·패키징·검증 보조 도구 |
| `tests/` | 앱 테스트와 acceptance 명세 |
| `docs/` | 모델, 기능 계약, 설계 결정과 보존된 과거 문서 |
| `progress/` | 현재 상태, backlog, 작업 계획과 결과 기록 |
| `output/` | 실행 산출물. Git에는 안내와 작업별 `REPORT.md`만 포함 |
| `verification/` | 보존된 문서·패키지 검증 결과 |

## 검증과 기여

문서 링크·canonical 재결합·문서 무결성 검사는 프로젝트 루트에서 실행한다.

```powershell
python tools/validate_bundle.py --json
```

이 검사는 앱·DB·모델 품질 검사가 아니다. Desktop의 Node 테스트는 `desktop/`에서 `npm test`로 실행한다. 실제 PostgreSQL, 별도 숨긴 Electron 인스턴스의 UI 검사, live 모델 검증은 각각 환경과 범위를 준비해야 하며, skip을 통과로 세지 않는다.

- 작업 범위와 보존 규칙: [AGENTS.md](AGENTS.md)
- 코드 변경 검토 기준: [codex/CODE_REVIEW.md](codex/CODE_REVIEW.md)
- 현재 구현·검증·다음 작업: [현재 상태](progress/STATUS.md)
- 기능별 계약·과거 기록: [문서 인덱스](docs/INDEX.md)

변경할 기능의 계약과 코드를 먼저 확인하고 기존 모듈을 재사용한다. DB 변경은 additive migration으로 관리하고 격리된 저장소에서 검사한다. 기존 사용자 DB와 사용자가 열어 둔 앱 창은 개발 테스트 대상으로 사용하지 않는다.

## 백업에 포함되는 것

Git은 코드·설계 문서·계획·보고서와 변경 이력을 보존한다. [.gitignore](.gitignore)에 따라 로컬 설정·credential, 의존성·캐시, 모델·원문 등 실행 산출물은 제외한다. **DB와 Artifact Store는 별도 백업이 필요하다.**

보고서에서 연결한 상세 JSON·이미지·모델 응답·receipt는 로컬에만 남아 있어 GitHub나 새 clone에서 링크가 열리지 않을 수 있다. `output/`에는 재생성 가능한 로그뿐 아니라 원문과 판단 근거도 있으므로 폴더 전체를 삭제 가능한 캐시로 취급하지 않는다. 보존 경계는 [실행 산출물 안내](output/README.md)를 확인한다.

과거 실행 보고서는 당시의 결과다. 로컬 Git 최초 기준점은 `c10dc88`이며, 그 이전 개발 commit 이력을 재구성한 것은 아니다. 이전 진입 문서를 조회하는 방법은 [문서 인덱스](docs/INDEX.md)에 있다.
