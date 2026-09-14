# Electron 작업 UI — 첫 구현

이 문서는 첫 UI 구현의 이력이다. 현재 버전·통합 실행 경로는 [현재 상태](../../progress/STATUS.md)와 [통합 Desktop](UNIFIED_DESKTOP.md)을 따른다.

**0.3 후속:** [I2K Information 오류](INFORMATION_ERRORS.md)를 기존 검토 화면에서 사용자 확인 필요 상태로 표시한다. 직접 D2K·D2I 재실행 작업은 추가하지 않았다. 실제 기본 연결·패키지별 버전과 결과는 해당 보고서를 따른다.

**0.2 후속:** [코드·검토·Wiki 계약](CODE_REVIEW_WIKI.md)과 [실제 실행 결과](../../output/t13-code-review-wiki/REPORT.md)는 code 파일 위치, exact KRevision/추론/전제/자료 버전, 실행 당시 검토 상태, accepted-inference query 답변 읽기를 추가한다. 새 코드 연결은 [전용 launcher](../../output/t13-code-review-wiki/Open-Code-Wiki.ps1)를 사용한다. 아래0.1의 논문 연결·패키지는 이력으로 유지하며 새 자료/질문/판정 쓰기 UI 완료를 뜻하지 않는다.

2026-09-13. [명시적 UI 착수](../decisions/ELECTRON_UI_START.md)에 따라 기존 Python 서비스를 사용하는 Windows Electron 앱을 구현했다. 이 첫 버전은 문서·근거·이력의 읽기와 검토 화면이다. [검증 보고서](../../output/t09-electron/REPORT.md), [실행 계획](../../progress/T09_electron_ui_execplan.md).

## 실행

현재 workspace의 [Palimpsest.cmd](../../Palimpsest.cmd)를 실행한다. 첫 버전의 독립 exe 패키지는 [T23 정리](../../output/t23-ui-realm/REPORT.md) 때 제거됐고 현재 런처는 공용 Electron 엔진을 사용한다. Docker Desktop과 기존 DB가 준비돼 있어야 한다. 앱은 기존 source DB를 migration하거나 Docker 서비스를 임의로 초기화하지 않는다.

기본 연결은 `palimpsest_wiki_pg` / Wiki `01a0941f-90b3-792b-bd4b-a3e83c18eaeb`, Artifact volume `palimpsest-knowledge_artifacts`, 저장 질문 `output/t07-wiki-query-ui/query-store`다. DB 비밀번호와 provider 자격 증명은 UI 설정에 들어가지 않는다. 필요하면 [connection.example.json](../../desktop/connection.example.json)을 `.local/electron-ui/connection.json`에 복사해 같은 workspace의 준비된 읽기 대상에 맞춘다. UI에서 임의 파일·DB를 탐색하는 설정 기능은 없다.

현재 패키지는 **이 workspace와 기존 Docker backend를 사용하는 portable Windows x64 앱**이다. 다른 PC에 복사한 단일 exe만으로 PostgreSQL·모델·원문까지 설치되는 배포판이 아니다. 파일을 옮기면 `PALIMPSEST_WORKSPACE`로 올바른 workspace를 지정하고 backend를 별도로 준비해야 한다. exe 외의 package 폴더 파일도 함께 필요하다. OS 설치·서명·자동 업데이트는 이번에 구현하지 않았다.

## 제공하는 화면

- **위키:** 논문 3개와 주제 22개, 문서 종류 필터와 제목 검색, 구조화된 본문과 주제 링크.
- **원문 근거:** 인용 번호로 exact I·Data·source execution·인용문·Unicode 문자 범위·보존 이미지를 조회.
- **원본 PDF:** 등록된 원본 bytes의 SHA 검증 후 PDF.js로 표시. 인용 페이지로 이동, 이전/다음 페이지, 확대/축소·회전, 보존 block 영역 강조.
- **문서 이력:** 현재·이전 snapshot 선택. 역사 topic은 당시 catalog의 paper snapshot으로 연결하며 현재 K 링크를 임의로 붙이지 않음.
- **관련 Knowledge:** exact KRevision·현재 여부·기원 정보와 `shared_source_evidence` 관계를 조회. 의미상 supports로 표시하지 않으며 미기록 기원을 추정하지 않음.
- **질문 기록:** 저장된 6개 질문, 현재 검증된 답변·인용과 검토/실패/원문 요청 round 이력. `needs_review`와 `needs_attention`은 확정 답변으로 노출하지 않음.
- **연결 상태:** 초기 로딩·읽기 오류·재연결을 표시. 로컬 read bridge를 다시 시작할 수 있음.

검색 입력은 **표시 문서 제목/저장 질문을 찾는 필터**다. 새로운 BGE 질의나 LLM 호출을 실행하는 입력이 아니다. 이번 UI에는 자료 등록·문서 편집·새 질문 실행·K2K/Decision 확정·그래프 시각화 기능이 없다. 기존 CLI/Runtime 기능이 그 경로의 기준이며 이후 수직 구현에서 연결한다. 없는 기능의 작동 버튼을 만들어두지 않았다.

## 연결과 보존

호스트 Electron main/preload는 허용된 6개 읽기 operation만 JSONL로 전달한다. Python read service는 기존 WikiDatabase/CompilerRuntime/정확한 query 검증 함수를 재사용하고 `default_transaction_read_only=on`을 강제한다. renderer에 Node·filesystem·shell·SQL·credentials를 노출하지 않는다.

Electron은 `docker compose run --rm --no-deps -T --pull never`로 별도 장기 read bridge 한 개를 실행한다. Artifact Store와 query 폴더는 read-only mount이고 HTTP 포트를 열지 않는다. 앱 종료는 이 reader의 stdin을 닫으며, PostgreSQL이나 모델 worker를 `docker down`으로 종료하지 않는다. read bridge가 없어지면 앱에서 재연결할 수 있다.

UI는 원문·모델 텍스트를 `textContent`로 표시하고 script를 실행하지 않는다. `sandbox`, `contextIsolation`, `webSecurity`를 유지하며 `nodeIntegration=false`다. 로컬 custom protocol은 UI/PDF.js의 허용된 정적 파일만 제공한다. 외부 fetch·popup·webview·임의 navigation과 renderer 권한 요청은 차단한다. 원본 artifact는 정확한 Wiki 소유와 SHA를 검사한 데이터로만 받는다.

현재 artifact 전송은 base64 응답이며 **50 MiB 초과 파일은 명시적으로 거부**한다. 이 제한은 canonical source의 삭제/파싱 완료 여부와 무관한 현재 UI transport 한계다. 더 큰 PDF에는 후속 streaming/range transport가 필요하다.

PDF 강조는 원래 보존된 **block/leaf 영역**이다. 문자 offset은 Unicode codepoint 기반으로 처리한다. PDF 자체의 nonzero crop origin·비기본 userUnit/rotation이나 page 비율이 맞지 않는 경우 추정 overlay를 그리지 않고 강조 생략을 표시한다. 사용자가 UI에서 회전하는 동작은 정상 지원한다. 현재 화면의 PDF.js 재렌더링은 과거 모델에 전달한 원본 page image bytes와 동일하다는 증명이 아니며, I나 모델 receipt를 변경하지 않는다.

## 빌드와 테스트

UI dependency는 Electron **44.3.0**, PDF.js **6.3.289**, 개발 패키징 도구 **20.3.0**을 package-lock으로 고정했다. React/bundler나 별도 ML dependency는 추가하지 않았다. Python 앱은 **0.9.0**, DB schema는 이전 **0010** 그대로다. dependency versions는 Electron의 bundled Node와 빌드용 host Node를 구분한다.

```text
docker build --tag palimpsest-desktop:0.9.0 .
cd desktop
npm ci
npm run install:electron
npm start
npm test
npm run package
```

이 workspace에서는 시스템 npm 설치 대신 bundled Node와 workspace-local npm CLI로 동일 작업을 실행했다. 설치 profile·명령·실패 및 재실행은 [도구 기록](../../output/t09-electron/toolchain/REPORT.md)에 있다. package는 처음 만들 때 기존 출력에 overwrite하지 않는다.

실제 Electron 검증에는 Playwright를 사용한다. `PALIMPSEST_PLAYWRIGHT_MODULE`에 준비된 Playwright module 경로를 지정하고 아래를 실행한다. `PALIMPSEST_ELECTRON_EXECUTABLE`을 패키지 exe로 지정하면 소스 실행과 별도로 패키지 자체를 검사한다.

```text
node desktop/test/electron-security.cjs
node desktop/test/electron-ui.cjs
```

소스/패키지의 실제 PDF·history·질문 동작, Windows junction/path escape와 IPC 부정 검사는 Python/DB 테스트와 별개로 보고한다. 앱 테스트는 `PALIMPSEST_APP_IMAGE=palimpsest-desktop:0.9.0`을 설정한 뒤 전용 fixture 프로젝트에서 `docker compose -p palimpsest-multi-checks run --rm --no-deps -T test`로 실행한다. 원본 또는 실제 논문 DB를 fixture로 쓰지 않는다.

## 상태

첫 읽기 UI의 실제 동작과 패키지를 검증했으며, 전체 T12/T13 release·macOS/Linux·서명·자동 업데이트·배포 전용 installer·새 질의/편집 UX는 별도다. 현재 UI 선택은 앱 core의 원문 보존, source-only I2K, K2K 추론 경계나 W authority 규칙을 바꾸지 않는다.
