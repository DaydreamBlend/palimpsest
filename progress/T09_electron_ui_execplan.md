# Electron 첫 작업 UI — 2026-09-13

사용자의 명시적 구현 요청으로 GUI 첫 slice를 시작한다. [현재 승인 범위](../docs/decisions/ELECTRON_UI_START.md)가 이전 GUI 순서보다 이 범위에서 우선한다. T12 release·formal P/W/B·public site·전체T13을완료처리하지않는다.

## 관찰 가능한 완료 동작

호스트 Electron 창에서 기존 논문3/주제22를 조회하고 본문을 읽는다. 인용 버튼으로 exact I와 원본 PDF 페이지를 확인하고, 문서 snapshot 이력과 관련 KRevision을 본다. 저장된6개 query의 answered/needs_review/needs_attention 및검토/원문확인경로를구분해조회한다. 화면에서모델을새로호출하거나원문을재파싱하지않는다. 연결실패와재시도상태를실제환경에서확인한다.

## 경로·소유권

- root: Electron main/preload의 좁은 IPC·로컬 asset protocol·Docker bridge 생명주기, vanilla ES module renderer/CSS, UI실제검증·패키징·문서통합.
- backend 담당: `desktop_read.py`, `desktop_bridge.py`, 실제PG/파일 focused tests. 기존 WikiDatabase/CompilerRuntime/정확query자료를재사용하며읽기만한다.
- toolchain 담당: exact Electron/pdfjs-dist/packager package+lock, workspace local install, 테스트환경확인.
- 독립검토: 실제page/topic/query/source data계약과UI의안전/역사refs 검사.

현재코드에GUI/Node package는없다. Electron44.3.0/pdfjs-dist6.3.289/packager20.3.0을공식registry로확인한뒤고정한다. 새PythonMLdeps나DBschema는필요하지않다. 새앱image0.9.0은readservice를추가하며기존0010은유지한다.

## 단계

1. 승인문서·실행계획, exact UI toolchain, read API 계약.
2. 비밀이없는연결설정과권한없는renderer→제한된preload/main→JSONL Docker readservice.
3. 논문/주제목록·검색·본문·인용·원문PDF·검토/이력 UI.
4. 실제Electron/Playwright로키보드/목록/인용/이미지/PDF/역사/held표시·연결실패를확인하고스크린샷을검토한다.
5. Windows portable 앱과실행도구를만들고실제패키지에서도동작검사. CLI회귀와원본불변검사를실행해보고한다.

## 제약과 검증

Renderer는Node/fs/shell/DB자격증명에접근하지않으며문서/모델출력은textContent로표시한다. query의answer_path가있어도answered+accepted검증이없으면현재확정답변을표시하지않는다. 역사topic→paper는그catalog의exactsnapshot을찾고현재상태를소급주입하지않는다. PDFbbox는block영역이며문자단위정확성을주장하지않는다. 모르는source경로를열거나새D2I로복구하지않는다.

외부privateAPI/새LLM호출0,원본sourceDB변경0. 개발DB는wiki_pg0010을읽고tests는별도fixture만쓴다. Dockerreadservice는포트공개없이stdin/stdout이며새장기UI세션컨테이너는앱종료에정리한다. 사용자workspace/성공한원본volume·이전profile은보존한다. 문서validator 기존raw오류12개와앱/UI테스트를구분한다.

## 완료한 첫 UI slice

Electron44.3.0/PDF.js6.3.289/Packager20.3.0 exactlock, vanillaUI, Python0.9.0 readservice와 Windows portable package를완료했다. 개발실행과패키지exe에서25문서·I/PDF·페이지이동/회전·과거2→1논문topic·확정/보류질문·재연결·renderer격리를실제로검사했다. 최초PDF빠른이동상태경합은원인수정후동일실물검사가통과했고testlocator오류와초기prototypeguard실패기록도보존했다.

최종Python649개(633pass/16skip), Node보안9개, 실제source/packagedElectron UX/security는모두통과했다. 기존DB48표/6,420행전체hash불변. 원문/query/credential mount RW=false를마지막실행reader에서도확인했다. 새schema/migration/LLM/D2I0이다. 패키지73files/458,394,930bytes, exe/sourceASAR대조와실제launch를확인하고앱창을열어뒀다.

문서전체checker는820오류/exit1: 새third-party package문서808+기존raw12. checker범위나원본문서를바꾸지않았다. 이번작성/수정문서12개는기존inspector로별도검사해오류0이다. [보고서](../output/t09-electron/REPORT.md)와[실행안내](../docs/interfaces/DESKTOP_UI.md)에정확명령/각검증범위/한계를기록했다. T12/전체T13, formal결정taskT09와새질의·편집·등록·graph화면은완료처리하지않는다.
