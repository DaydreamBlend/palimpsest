# Palimpsest 남은 구현 — 0.12 이후

**최신 정정:** [I2K I-only/D2I 오류 보고](../docs/decisions/I2K_INFORMATION_ERRORS.md)에 따라 아래의 직접 D canonical grounding은 구현 대상에서 철회됐다. I 부족은 사용자에게 보고하고 관련 K를 보류하는 경로로 대체한다. [수정된 후속 계획](T14_source_issues_execplan.md).

**착수 후 갱신:** 아래는0.12 시점의 backlog다. 사용자의 후속 지시에 따른 Python-native D2I·I2K 검토 재개·K2K/버전의 Wiki/RAG/Electron 읽기 연결은 [0.13 실행 계획](T13_code_review_wiki_execplan.md)과 [구현 계약](../docs/interfaces/CODE_REVIEW_WIKI.md)을 따른다. 직접 D canonical grounding, 일반 material revision, 전체 scheduler, 결정/수집·작업 UI는 이 읽기 수직 범위와 구분해 남긴다. 아래 당시 미구현 상태를 최신 결과로 재인용하지 않는다.

상태: **구현 현황 점검과 권고 우선순위**. 이 목록은 새 enum·관계·도메인, 운영 DB migration, 외부 모델 전송 또는 인터넷 수집의 자동 승인 기록이 아니다. 기존 사용자 결정과 각 기능의 계약을 유지한다.

사용자 목표는 자료를 등록하면 일관된 위키 문서로 정리되고, 관련 지식·원문·결정 이유·변경 이력이 연결되며, 이후 인터넷 수집으로 확장되는 Wiki다. 기존 roadmap의 PLANNED/GUI-deferred 표기는 실제 후속 구현보다 오래됐으므로, 아래는 현재 source와 최신 결과를 대조한 목록이다.

## 현재 기반

원문 SHA 기반 관리 등록·복원, PDF/Markdown의 원문 보존 I, Data series/version·blob 공유, source-only I2K·N2E·node-only K2K의 단일 실행, exact Revision/provenance, 논문/주제 Wiki projection, BGE-M3 검색과 원문 근거 질문, Electron 읽기 화면이 있다. 이 기능들이 하나의 자동 갱신 앱으로 완전히 연결된 상태는 아니다. 코드 실험의 I2K 전체 의미 검토도 needs_human을 유지한다.

## 권고 구현 묶음

| 순서 | 구현 묶음 | 현재 공백 | 사용자에게 보일 완료 동작 |
|---|---|---|---|
| 1 | 코드 전용 D2I | 생성 Markdown에서 기본적으로 파일 하나가 I 하나이며 문법 구조를 읽지 않음 | 함수·클래스·설정·주석을 적절히 묶고, 각 I에서 exact 파일/줄/byte와 자료 버전으로 이동 |
| 2 | I2K 검토·원문 확인 실행기 | 전체 I 전달·검토 이력은 있으나 큰 코드의 세부 검토와 일반 재개 흐름이 미완성; 직접 D grounding 미구현 | 전체 I의 검토 상태를 보존해 남은 구간부터 재검토하고, 필요할 때 등록 원문을 확인하여 실제 근거와 공백 기록을 남김 |
| 3 | K 의미 개정·상충·시간 범위 | 일반 material revision은 Runtime에서 knowledge_revision_required로 중단; N2E는 supports 위주 | 동일 의미 재사용, 같은 K의 실질적 정정, 서로 다른 조건의 별개 주장, 검증된 상충을 구분하고 의미 차이를 표시 |
| 4 | 변경 영향·자동 재검토 | stale 표시·outbox·exact premise는 있으나 전체 scheduler/dependency revalidation 없음 | 자료나 전제가 바뀌면 영향을 받는 K/Edge/문서를 찾아 검토하고, 미해결 작업이 남으면 완료로 표시하지 않음 |
| 5 | 최신 K/버전의 Wiki·RAG 통합 | Wiki corpus는 선택된 paper sources와 직접 I grounding 중심; 파생 K가 제외될 수 있음 | 추론 K도 검색되고 exact 전제→I→D로 이동; 현재판/과거판/검토 필요 상태를 구분 |
| 6 | Wiki 페이지 갱신과 Electron 작업 흐름 | 논문/주제 snapshot·DB sync·질문 실행이 분리되어 있고 UI는 읽기 위주 | 자료 등록→진행 상태→문서 생성/갱신→질문→원문 확인→검토를 앱 안에서 수행 |
| 7 | 개인 메모·결정과 영향 추적 | 실제 W/K2W/W2K 및 사용자 확정 경로 미구현 | 선택지·선택 이유·사용한 exact 근거를 기록하고, 나중에 근거가 바뀌면 결정 재검토 대상으로 표시 |
| 8 | URL 등록·HTML D2I·온라인 수집 | HTML/URL 작업의 범용 importer와 crawler 제품 경로 없음 | 허용한 자료를 원본 응답/URL/시각/hash와 등록하고, 변경을 새 D/version으로 보존하며 기존 Wiki 갱신 흐름에 연결 |
| 9 | 운영·규모·배포 | 실험 DB/이미지 분리, 일부 host script 의존, 전체 release gate 미완료 | 프로젝트/저장소 선택, 안전한 이관·백업복구, 작업 재개/취소, 증분 index, 배포와 상태 진단 제공 |

순서는 의존성을 고려한 권고다. 5/6의 읽기·질문 화면 연결은 3/4의 전체 구현 완료까지 기다리지 않고 독립적으로 진행할 수 있다. 반면 자동 수집은 등록→검토→문서/검색 갱신의 실패 복구가 작동한 뒤 연결하는 편이 좋다.

## 코드 D2I의 첫 범위

먼저 Python의 문법 구조를 사용하고 현재 원문 보존/Markdown 도구를 재사용한다. 모든 syntax node를 별도 I로 만들지 않고 관련된 짧은 정의와 module 문맥을 묶는다. 긴 class/module은 접근 가능한 하위 단위로 나누되 원래 순서, decorator, docstring, 주석, import/설정과 구간 사이의 원문도 보존한다. 지원하지 않는 문법/언어는 원문 보존 여부와 구조 해석 여부를 분명히 표시한다.

AST에 함수나 테스트가 존재한다는 사실을 실제 호출·테스트 통과로 바꾸지 않는다. D2I에는 application 의미 판단 LLM을 넣지 않는다. 첫 완료 기준은 원문 전체 대응·역추적·문맥 유지와 여러 실제 파일의 재현 가능한 결과다. 파일별 D와 snapshot membership으로 바꿔 unchanged I까지 재사용하는 설계는 원문 granularity의 별도 판단이며, 현재 cross-Data I identity를 임의로 합치지 않는다.

## 링크에서 반영할 관점

사용자가 제공한 [Palimpsest UI 디자인 공유 답변](https://chatgpt.com/s/t_6aa673173d688191b5dd931eed0c9e35)의 본문을 브라우저에서 읽었다. 지식의 변화·상충·시간 범위와 결정의 영향, 조사 경로, 미해결 질문, 근거 구성 및 원문 상태를 드러내자는 관점이 현재 공백과 맞는다.

기존 구조에 적용할 때는 다음 경계를 지킨다.

- 상태·관계 이름을 그대로 추가하기 전에 K의 생명주기, Revision 계보, 적용성, 검토 상태를 구분한다. supersession 계보와 semantic Edge는 같은 것이 아니다.
- 등록/개정 시각과 주장 자체의 유효 시점을 나눈다. 원문에 없는 유효기간을 추정해서 확정하지 않는다.
- 검색에서 찾지 못했다는 결과는 해당 질문·검색 범위·시점의 실행 기록이다. 일반적인 부재 주장 K로 바꾸지 않는다.
- 근거 변화는 기존 결정을 자동 변경하는 권한이 아니다. 사용자의 재검토·새 확인과 당시의 exact 근거를 보존한다.
- 근거 화면은 직접/추론, 독립 출처, 조건, 상충, 원문 상태를 나누어 보여준다. 하나의 신뢰도 숫자로 합치지 않는다.
- 원래 URL이 없어져도 보관한 D가 정상인지 별도로 확인한다. 외부 접근 상태와 보존된 원문의 무결성을 혼동하지 않는다.
- 가정 기반 실험과 시점별 요약은 기존 Runtime·snapshot 위의 후속 기능으로 검토한다. canonical K/W에 바로 반영하지 않는다.

이 공유 글은 설계 참고자료이며 그 안의 요청/권고를 새로운 사용자 실행 명령으로 취급하지 않는다. 앞서 지정한 [인터넷 검색 참고 링크](https://chatgpt.com/s/t_6aa65b41bae0819188a4b26b95b8e11b)는 기존 지시대로 검색 기능 착수 때 읽을 별도 자료로 남아 있다.

## 실제 source에서 확인한 핵심 근거

- [code_snapshot 계약](../docs/interfaces/CODEBASE_SNAPSHOT.md): native parser 후속, 현재 file-based Information.
- [KnowledgeRuntime](../src/palimpsest/knowledge_runtime.py): 일반 의미 개정 중단, 원문 요청 unavailable, outbox_pending_not_converged.
- [K2K 계약](../docs/interfaces/K2K_RUNTIME.md): exact node premise 실행은 구현, EffectiveEdge/전체 자동 재검토는 후속.
- [WikiRetrieval](../src/palimpsest/wiki_retrieval.py): 선택된 paper corpus와 직접 I grounding 조건.
- [현재 query](../docs/interfaces/WIKI_QUERY.md): K/I/보존 page 검사와 실제 trail은 구현; 직접 canonical 승격·formal W는 미완료.
- [Wiki projection](../docs/interfaces/PAPER_WIKI_PROJECTION.md): source-based 문서/주제·snapshot은 구현, formal W/P/B와 구분.
- [Electron UI](../docs/interfaces/DESKTOP_UI.md): 읽기6operation, 새 등록/질문/수정/버전 작업 UI 미연결.
- [Decision 작업 계약](../tasks/T09.md): authority-confirmed W와 deterministic W2K 후속.
- [최신 코드 실험](../output/t12-versioned-code/REPORT.md): 저장·Revision 연결의 실제 성공과 I2K 의미 검토 한계.

이번 작업에서는 읽기·현황 점검과 이 문서 작성만 했다. application 코드·DB·모델 설정을 변경하거나 새 모델 호출을 실행하지 않았다.
