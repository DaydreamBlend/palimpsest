# Electron 첫 UI 착수 — 2026-09-13

사용자는 Electron 조사 결과를 읽고 “MinerU나 LLM을 붙이는 비용에 비하면 Electron 부담은 적을 것 같아. 한번 구현해줘.”라고 명시했다. 이 후속 지시는 **지금 Electron의 첫 동작 가능한 UI를 구현하는 범위**에서 이전 T12 이후 GUI 착수 순서에 우선한다. T12의 미완료 항목을 완료로 바꾸거나 전체 P/W·공개 배포·자동 수집을 승인한 것으로 해석하지 않는다.

첫 수직 구현은 기존 Python 서비스를 이용해 논문/주제 목록, Wiki 본문, 인용 I·원본 PDF, K Revision과 문서 snapshot, 저장된 질문의 답변/보류/원문 확인 이력을 연결하는 데스크톱 UI다. 호스트 Electron과 Docker backend를 분리하고 기존 원문·I·K·Wiki·query 이력은 그대로 읽는다. 새 모델 호출·D2I 재실행·canonical 쓰기·원본 DB migration은 이 UI 연결에 필요하지 않다.

설치할 UI dependencies와 실행 profile을 정확히 기록하고 로컬 Electron 실제 창·기존 데이터·안전한 메시지 경계를 검사한다. 화면을 웹 기술로 작성하되 아직 없는 서버 API나 편집·질의 실행을 작동하는 기능처럼 보이지 않는다. 추가 기능은 별도 수직 구현으로 진행한다.

[실행 계획](../../progress/T09_electron_ui_execplan.md), [선행 조사](../implementation/ELECTRON_UI_ASSESSMENT.md).
