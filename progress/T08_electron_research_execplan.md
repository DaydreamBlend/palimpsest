# Electron 직접 UI 적합성 조사 — 2026-09-13

사용자는 Electron으로 UI를 직접 만드는 것이 더 적절한지 조사하도록 요청했다. 구현·설치·배포를 요청한 것은 아니다. 현재 Wiki/query 계약, UI 비교, USER_OVERRIDES/INDEX/DECISION_REGISTER, PLANS와 T13의 CLI-first 경계를 확인했다.

조사 목표는 (1) 위키/PDF/I/K/Revision을 함께 다루는 주 작업 화면 적합성, (2) 기존 Python/Docker와 연결, (3) 향후 웹 위키와 UI 재사용, (4) 직접 개발·배포 책임, (5) Tauri/기존 Wiki UI와의 비교다. 공식 Electron/Node/Docker와 컴포넌트 문서를 사용하며 제품 기능과 우리 프로젝트의 설계 판단을 구분한다.

root는 프로젝트 적합성과 종합 보고를, 독립 조사자는 배포/backend 연결과 대안/컴포넌트를 나누어 검토한다. 변경은 조사 문서와 인덱스·기존 UI 권고의 날짜가 명시된 후속 설명에 한정한다. 앱·schema·원문·모델·Docker 환경과 UI scaffold는 변경하지 않는다. 라이브 provider 호출과 source 전송은 필요하지 않다.

결과는 `docs/implementation/ELECTRON_UI_ASSESSMENT.md`와 `output/t08-electron-research/`의 공식 근거 notes에 남긴다. 기존 2026-09-12 Quartz 권고의 읽기/게시 범위는 보존하면서 주 작업 UI와 구분한다. T13 착수·AT103/GUI 완성·앱 회귀 통과를 조사 결과로 보고하지 않는다. 문서 연결·형식 검사는 기존 raw Markdown 오류12개 baseline과 비교한다.

## 완료 결과

2026-09-13 공식 Electron/Node/Docker, Tauri 및 PDF/editor/graph component 자료를 조사했다. 주 작업 UI에는 Electron 전용 화면, 선택적 읽기/게시에는 Quartz를 두는 후속 권고를 작성했다. Electron host와 Python/Docker backend 분리, 초기 JSON CLI 재사용과 향후 좁은 API, renderer/web component 재사용, exact PDF 좌표와 source/Revision 연결 및 배포·업데이트 책임을 구분했다.

변경 파일은 이 계획, [종합 조사](../docs/implementation/ELECTRON_UI_ASSESSMENT.md), [배포 notes](../output/t08-electron-research/deployment-notes.md), [대안·부품 notes](../output/t08-electron-research/alternatives-notes.md), 기존 WIKI_UI_INTEGRATION의 날짜 명시 후속 설명, INDEX와 DECISION_REGISTER다. 앱 코드·schema·AGENTS·모델·원문은 바꾸지 않았다.

실행한 문서 검사: bundled Python `-X utf8 -B tools/validate_bundle.py`, exit1. [로그](../output/t08-electron-research/document-validation.log)의 오류는 기존 parser/raw Markdown12개와 같으며 새 문서 오류는 없다. 전체 앱 tests와 문서 mutation suite, Electron/Tauri 설치·실행, PDF/한글/성능/서명·업데이트 실험은 수행하지 않았다. 조사 범위에 미해결 승인 요청은 없으며 T13/AT103 완료나 GUI 착수를 선언하지 않는다.
