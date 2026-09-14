# Electron 첫 작업 UI 구현·실물 검증

2026-09-13. 사용자의 명시적 구현 요청에 따라 **Electron 데스크톱 UI와 Windows portable 실행 파일**을 만들었다. 기존 논문·주제 Wiki, exact I와 원본 PDF, 문서 snapshot 및 관련 KRevision, 저장된 질문의 답변·검토 이력을 실제 PostgreSQL/Artifact Store에서 읽어 표시한다.

첫 실행은 [Palimpsest.cmd](../../Palimpsest.cmd), 직접 실행 파일은 [Palimpsest.exe](app/Palimpsest-win32-x64/Palimpsest.exe)다. 실행 방법과 범위는 [DESKTOP_UI.md](../../docs/interfaces/DESKTOP_UI.md)에 있다. 새 자료 등록·문서 편집·새 LLM 질문 실행·graph 시각화·자동 수집을 구현한 버전은 아니다. 제공 화면에는 없는 기능의 작동 버튼을 배치하지 않았다.

## 실제 화면

아래는 mock이 아니라 생성한 **Palimpsest.exe**의 실제 화면이다. 기존 Test_Paper의 인용 3을 선택해 I를 확인한 뒤 원본 PDF 10페이지와 보존된 원문 block 영역을 표시했다. 글자별 glyph 좌표를 새로 만들어 표시한 것이 아니다.

![실제 패키지에서 Wiki와 원본 PDF를 함께 표시](ui-packaged/final/03-original-pdf.png)

다른 확인 화면: [라이브러리](ui-packaged/final/01-library.png), [exact Information](ui-packaged/final/02-exact-information.png), [PDF 회전](ui-packaged/final/04-pdf-rotation.png), [과거 주제 문서](ui-packaged/final/05-topic-history.png), [검증된 질문 답변](ui-packaged/final/06-verified-answer.png), [보류된 질문](ui-packaged/final/07-held-answer.png).

## 제공 기능

| 화면 | 실제 동작 |
|---|---|
| 라이브러리 | 논문3/주제22, 총25문서. 종류 필터와 제목 검색 |
| Wiki 본문 | 고정된 항목/절·주제 링크·인용 번호·현재 snapshot |
| 원문 I | exact Data/I/source execution, 인용문, Unicode codepoint 범위와 보존 이미지 |
| 원본 PDF | SHA 검증한 등록 원본, 인용 page 이동, 앞뒤 page, 확대/축소·회전, block 영역 강조 |
| 문서 이력 | 현재/과거 snapshot 전환과 해당 catalog에 결속된 논문 연결 |
| K 연결 | exact KRevision·현재 여부·기원 미기록 구별, shared_source_evidence 의미 유지 |
| 질문 기록 | 실제6개 query, answered4·needs_review1·needs_attention1의 결과·검토·round 이력 |
| 연결 관리 | 로딩·실패·재연결, 앱별 read bridge 수명 관리 |

문서 graph나 의미상 supports를 새로 판정하지 않는다. 관련 K는 기존 원문 공유 탐색 관계이고, 검토 필요 연결은 기본 목록에서 제외한다. legacy 기원을 임의로 “원문 생성”으로 채우지 않는다.

질문의 `answer_path` 또는 이전 답변 파일이 존재한다는 이유만으로 확정 답변을 표시하지 않는다. 현재 `answered` 상태와 exact proposal/validation hash 및 전체 checks를 다시 확인한 경우에만 답변 본문을 표시한다. 보류 상태에는 검토 이유와 이력을 보여주며 과거 answered 제안과 독립 Validator verdict도 구분한다.

## 구조와 변경 파일

- `desktop/main.cjs`, `preload.cjs`, `bridge.cjs`, `security.cjs`: Electron process 격리, 허용된 read IPC, 정적 asset protocol, 기존 Docker Python bridge 연결.
- `desktop/index.html`, `styles.css`, `renderer.js`, `pdf-view.js`: 실제 문서·질문·근거·PDF UI. 외부 텍스트는 DOM textContent로 표시하고 실행하지 않는다.
- `src/palimpsest/desktop_read.py`, `tools/desktop_bridge.py`: 기존 WikiDatabase/CompilerRuntime/query 검증 함수를 재사용하는 읽기 전용 service와 JSONL transport.
- `desktop/package.json`, `package-lock.json`: Electron/PDF.js/packager exact pin. React/bundler는 추가하지 않았다.
- Python version/COPY 목록, `.dockerignore`/`.gitignore`, launcher·connection example, 승인·작업 계획·문서 인덱스와 실행 안내를 갱신했다.

앱 core는 Python/Docker를 유지한다. Electron은 호스트에서 실행하고 renderer에는 Node·filesystem·shell·DB credentials를 노출하지 않는다. JSONL은 HTTP port를 공개하지 않으며 backend는 `default_transaction_read_only=on`과 원문/query read-only mount를 사용한다. UI 화면이 source 등록·K/W 승인·canonical commit을 대신하지 않는다.

이번 GUI 착수는 [2026-09-13 후속 지시](../../docs/decisions/ELECTRON_UI_START.md)에 따른다. 이전 GUI-last 순서에 이 첫 slice 범위에서 우선하지만, T12 release나 전체 T13·formal W/P 계약 완료를 뜻하지 않는다.

## 검증 결과

| 구분 | 결과 |
|---|---|
| Python 앱 전체 suite | **649개, 633 pass / 16 skip**, 120.735초, exit0 |
| 새 Python reader tests | 6개 pass. 실제 Linux 파일과 별도 fixture PG2개 포함 |
| Node 보안 경계 | **9개 pass**, Windows junction/path escape·prototype·operation/필드/UUID/hash 검사 |
| 실제 Electron source 보안 | sandbox/contextIsolation/Node 미노출, IPC write 차단, private file404, 외부 fetch/popup 차단, 실제25문서 연결, error0 |
| 실제 Electron source UX | I·PDF10/11·빠른 앞뒤 이동·회전/확대·block overlay·2논문 topic→1논문 역사·질문 보류·재연결 pass |
| 실제 packaged exe 보안 | source와 같은 조건 pass, ASAR asset 경로/접근 제한 확인 |
| 실제 packaged exe UX | 같은 논문/PDF/history/질문/재연결 시나리오 pass, renderer error0 |
| 기존 데이터 보존 | 48개 table / 6,420행의 전체 행 SHA와 이름·행 수가 이전 감사와 동일 |
| 이번 모델/D2I/schema 변경 | 실제 모델 호출0, D2I0, migration0 |

16 skip은 기존 native PDF 검사 환경 조건이다. full Python suite는 실제 논문 DB를 테스트 fixture로 사용하지 않고 `palimpsest-multi-checks`의 분리된 기본 fixture DB에서 실행했다. 이전 643개 결과를 새 실행으로 재사용한 것이 아니라 649개를 새로 실행했다. [앱 로그](app-tests.log).

Electron source와 packaged 실행 결과는 각각 [source UX](ui-runtime/verified-3/result.json), [package UX](ui-packaged/final/result.json), [source security](security-runtime/result.json), [package security](security-runtime-packaged/result.json)에 있다. Playwright가 실제 Electron binary를 실행했다. Windows hidden window는 paint되지 않아 screenshot 단계에서는 `showInactive()`로 창을 표시했으며 이를 headless rendering 성공이라고 보고하지 않는다.

### 이번 slice의 확인 항목

- UI01: 실제25문서와6질문을 읽고 필터/전환한다.
- UI02: 인용된 I를 읽고 해당 원본 PDF/page/block을 표시한다.
- UI03: 과거 MoDC 문서의 source contribution이 현재2편에서 당시1편으로 달라짐을 확인한다.
- UI04: 검토/미해결 질문의 이전 답변을 현재 확정 답변으로 표시하지 않는다.
- UI05: renderer에는 읽기 operation만 제공하고 임의 shell/path/SQL/외부 탐색을 거부한다.
- UI06: source뿐 아니라 Windows package에서 같은 기능과 재연결이 동작한다.

이 UI01–06은 이번 수직 구현의 확인 항목이며 기존 acceptance catalog의 같은 번호를 대체하지 않는다. T13/AT103의 전체 release 기능이나 이후 편집·새 질의 동작의 완료 기록이 아니다.

## 발견·수정·미실행 구분

실제 PDF10→다음→렌더 완료 전 이전 클릭에서9페이지로 잘못 가는 문제가 있었다. desired page를 렌더 대기 전에 갱신하고 이전 비동기 완료가 새 값을 덮어쓰지 않게 수정했다. 동일한 실제 동작은 source와 package에서 통과했다. [최초 실패](ui-runtime/result.json), [수정 후 결과](ui-runtime/verified-3/result.json).

Node 경계 시험에서는 상속된 operation/non-record 객체가 통과하는 것을 발견해 plain-record 및 own-property 검사를 추가했다. 동일한 Windows junction/IPC suite는 최종9개 통과했다. backend test의 첫 실패는 Markdown escaping과 평문 assertion 비교였으며 의미 내용의 올바른 비교로 수정했다. 보안 및 동작 assertion을 제거하거나 실패를 skip하지 않았다.

추가 UI test 두 번은 제목 대소문자 가정 및 같은 검색어의 다른 주제를 첫 결과로 선택한 test locator 문제로 실패했다. 실제 catalog의 고정 page ID와 정확한 제목으로 목표를 선택한 후 history 시나리오가 통과했다. 이전 실패 JSON/화면은 [첫 selector 실패](ui-runtime/verified/result.json), [유사 주제 선택 실패](ui-runtime/verified-2/result.json)에 보존했다.

PDF 자체의 nonstandard crop origin·userUnit·기본 rotation 또는 일치하지 않는 source page ratio는 현재 overlay를 추정하지 않고 강조 생략을 표시한다. 사용자 UI 회전은 정상 지원하며 원본 PDF 내용은 언제나 별개로 표시한다. 실제 한글 문자열 검색은 검사했지만 모든 OS IME의 composition·접근성·대규모 graph·RAM/startup benchmark는 실시하지 않았다.

## Windows package

Electron **44.3.0**, PDF.js **6.3.289**, Packager **20.3.0**을 고정했다. UI version0.1.0/Python app0.9.0/기존 schema0010이다. 앱·PDF.js·보안 파일10개의 ASAR hash가 소스와 일치하고 test/dev tool 의존성은 package에서 제외됐다. [package report](app/REPORT.md), [manifest](app/package-manifest.json), [ASAR 비교](app/asar-inspection.json).

- 실행 파일: `app/Palimpsest-win32-x64/Palimpsest.exe`.
- package 폴더: **73개 파일 / 458,394,930 bytes (약437.16 MiB)**. RAM 사용량이나 압축 다운로드 크기가 아니다.
- exe SHA-256: `42803A355BF23689DE7707552F938A0E3A9CC8189AF28257262CF67FDEB91A6A`.
- app.asar SHA-256: `12084B06FD7AED691132DC77D6B086DC9829716301B0667914CA60A42FB3B36A`.

이 package는 현재 workspace·준비된 Docker/PG/Artifact Store에 연결하는 portable 앱이다. 단일 exe만 다른 PC에 복사해 전체 시스템이 설치되는 것은 아니다. 서명/자동업데이트/OS installer와 macOS/Linux는 후속 검증이다. 개발 폴더와 성공한 원본 이미지/volume은 보존했으며 처음 package를 만들 때 기존 디렉터리를 삭제하지 않았다.

패키지 exe를 일반 창으로 실행했다. [실행 PID](launch.json), [창 handle 확인](launch-confirmed.json), [현재 reader의 실제 read-only mounts](live-read-mounts.json)를 기록했다. 앱이 열려 있는 동안 reader 컨테이너1개가 동작하며 앱 종료 시 reader를 정리한다. 기존 PostgreSQL·모델 worker를 종료하지 않는다.

## 원본 보존

[독립 보존 감사](preservation.md), [table별 hash](preservation.json)에서 이전 t07 기준의 **48개 table / 6,420행**이 모두 동일했다. 원래45개 table6,148행, ledger10행, retrieval262행과 Wiki blob135개/28,793,581bytes의 실제 hash가 보존됐다. 새 DB migration이나 canonical 쓰기는 없다.

query-store의 UI 실행 전 별도 file manifest는 없으므로 전후 file bytes를 측정해 동일했다고 주장하지 않는다. 읽기 전용 mount·no-follow 읽기·쓰기 operation 부재를 확인했다. 감사 당시에는 reader가 종료된 상태여서 runtime mount 관찰이0개였고, 앱을 마지막에 실행한 뒤 [별도 실물 mount 기록](live-read-mounts.json)을 남겼다.

## 정확한 실행 명령과 남은 범위

```powershell
docker build --tag palimpsest-desktop:0.9.0 .
$env:PALIMPSEST_APP_IMAGE='palimpsest-desktop:0.9.0'
docker compose -p palimpsest-multi-checks run --rm --no-deps -T test
```

Node 도구와 테스트는 bundled Node24.19.0 절대 경로로 실행했다. `PALIMPSEST_PLAYWRIGHT_MODULE`에 준비된 Playwright1.62.1 경로를 지정했으며 package검사는 `PALIMPSEST_ELECTRON_EXECUTABLE`에 생성된exe를지정했다.

```text
node --test desktop/test/security.test.cjs
node desktop/test/electron-security.cjs
node desktop/test/electron-ui.cjs
```

정확한 toolchain install/package 명령과 최초 network 실패·재실행은 [toolchain 기록](toolchain/REPORT.md), [package 기록](app/REPORT.md)에 있다. 실제 앱 테스트·Electron 검증과 문서 bundle검사를 구분한다. Git 저장소가 아니므로 Git diff/commit 성공을 주장하지 않는다.

미완료 범위는 자료 등록/편집·새 질문 실행·K graph 시각화·작업 재개/취소 UI,50MiB초과artifact streaming,전체T12/T13,formalP/W/B,코드서명/자동업데이트/다른OS배포다. 이번에사용자가승인한첫읽기UI를구현했고미완료범위를작동하는기능으로표시하지않았다.

문서 검사 `python -X utf8 -B tools/validate_bundle.py`는 **exit1/820개 오류**다. 이 도구가 workspace의 모든 Markdown을 검사해 새 npm/Electron third-party 문서의 상대 링크·표에서808개, 기존 보존 raw 문서에서12개를 보고했다. checker나 third-party 문서를 고쳐 오류를 숨기지 않았다. 이번에 작성·수정한12개 문서는 같은 inspector로 표/로컬 링크를 따로 검사해 **오류0**을 확인했다. [전체 로그](document-validation.log), [범위별 분류와 작성 문서 검사](document-validation-summary.json). 이 구분을 전체 문서 validator 통과로 해석하지 않는다. 전체 tools 문서 mutation suite는 이번에 재실행하지 않았다.
