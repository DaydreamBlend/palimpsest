# 논문별 Wiki와 별도 주제 문서 — 2026-09-12

후속 진행으로 비canonical Wiki의 [PostgreSQL 저장·복원·exact KRevision 탐색](../interfaces/WIKI_DATABASE.md)을 추가했다. 아래 첫 구현의 파일 저장은 편집 작업 공간으로 유지하며 별도 `database-sync`가 PG current checkpoint를 선택한다. canonical P의 입력 계약은 그대로이고, live 원본 DB 대신 보존 사본에서 additive 0008/0009를 검증했다. [후속 결과](../../output/t06-wiki-postgres/REPORT.md).

사용자는 “일단 구현 시작해줘”라고 요청하고, 이전 논문 묶음을 입력으로 논문 하나당 Wiki 페이지 하나를 만들도록 지정했다. 여러 논문이 다루는 BMDC 등의 공통 내용은 별도 주제 문서로 저장해도 된다고 명시했다. BMDC가 모든 논문에 있다는 지시나 서로 다른 실험 K를 병합하라는 지시는 아니다.

이번 구현의 첫 범위는 기존 완료 D/I에 근거한 **읽기용 Wiki projection**이다. 고정 schema·renderer로 논문 문서를 만들고, 검증된 항목을 원문 논문별로 나누어 주제 문서에 모은다. page ID와 snapshot 이력, 정확한 I/D 인용, 현재 catalog와 과거 export를 보존한다. LLM이 전체 I에서 중요 내용을 고르고 별도 호출이 근거를 검증한다. 형식·ID·인용 범위·동시 변경·원자적 current 선택은 프로그램이 담당한다.

이는 요청을 작은 수직 구현으로 시작하는 구현 선택이다. 정식 P의 W 없는 입력 계약이나 canonical publication schema 변경을 사용자가 구체 승인했다고 간주하지 않는다. K/P/W/B에 새 효과를 쓰지 않고 기존 canonical D/I를 읽어 JSON snapshot·Markdown을 생성한다. canonical P/DB 통합은 후속 범위이며 이 첫 단계의 문서 생성을 그 완료로 보고하지 않는다.

I의 원문·검색 역할, I2K의 명시 원문 범위와 K2K만의 새 추론, K 통합 비필수, D2I 재실행 금지와 과거 원본·I·KRevision 보존은 유지한다. 기존 승인된 Terra Medium과 같은 공개 논문 입력을 사용한다. GUI·인터넷 게시·주기 수집은 이번 착수 범위에 포함하지 않는다.

[실행 계약과 CLI](../interfaces/PAPER_WIKI_PROJECTION.md), [진행과 검증](../../progress/T05_paper_wiki_execplan.md)을 확인한다. 초기 3편은 Test_Paper, Clarke, Dejani이며 기존 완료 source의 총 87 I를 사용한다. 실제 생성 수·보류·의미 평가 결과는 실행 기록에서 별도로 확인한다.
