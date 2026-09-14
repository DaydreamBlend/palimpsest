# Wiki 검색·근거 답변과 기존 UI 비교 — 2026-09-12

사용자는 직전 제안한 질문→Wiki/K→I→D 흐름의 구현을 요청하고, 동시에 Obsidian+Quartz/Wiki.js 등 기존 UI 활용 가능성을 조사하도록 지시했다. UI는 이번에 비교·연결 설계까지 수행한다. 기존 CLI-first와 source/Revision 경계를 유지한다.

## 완료 동작

- 현재 Wiki import와 exact canonical source를 고정한 검색 corpus를 만든다. BGE-M3 dense embedding을 PG pgvector에 저장하고 같은 모델의 multi-vector score로 후보를 재정렬한다. I는 전부 색인하며 긴 I의 검색 창은 원문 범위를 가진 projection이다.
- 질문의 최초 Wiki/K 검색 결과에 실제 I 근거를 제공한다. LLM이 부족하다고 판단하면 I 전체 corpus의 의미 검색, 이어 등록 원본의 필요한 페이지 확인으로 진행한다. similarity 점수나 검색 top-k로 근거 충분성을 대신 판정하지 않는다.
- 구조화 답변과 독립 검증, 실제 전달 receipt, source 요청 이유/원본 hash/페이지, exact citations와 query 이력을 저장한다. 검색 결과/답변은 canonical K나 Decision이 아니며 D2I를 실행하지 않는다.
- 기존 세 논문으로 한국어 질문, K 미선택 I 조회, 근거 없는 질문, 원문 추가 요청을 검사한다. 모의 guard 검사와 실제 모델/PG 결과를 구분한다.
- 공식 자료로 Quartz/Obsidian, Wiki.js/BookStack/Outline을 비교하고, 현재 export와 연결 가능한 UI 및 별도 provenance/RAG 개발 범위를 권고한다. 설치·배포·공개 게시 요청으로 확대하지 않는다.

## 확인한 코드와 계약

AGENTS/USER_OVERRIDES/INDEX/DECISION_REGISTER, LLM_WIKI_RETRIEVAL, canonical publication/retrieval, T10/T11, PLANS/CODE_REVIEW와 현재 Wiki DB 계약을 읽었다. 기존 Wiki archive/PG/checkpoint, CompilerRuntime.prepare_input/locate_information/export_source, CodexProvider/기존 host worker를 재사용한다. 기존 BGE cache는 tokenizer_config 한 개뿐이고 검색·QA adapter는 없다. BGE 공식 모델카드의 1024차원/8192 token 및 ColBERT mode를 확인했다.

## 모듈·소유권

- root: `wiki_retrieval.py`, `wiki_query_runtime.py`, CLI, migration 목록, 실행/통합 검사·문서.
- 모델 담당: BGE tokenizer window·dense/ColBERT adapter, 별도 Docker/host worker, 모델 revision/artifact/dependency 검증, focused tests.
- 답변 담당: `wiki_query.py`의 strict schema/prompt/정확 인용 정규화/Validator/renderer 및 pure tests.
- SQL 담당: additive `0010_wiki_retrieval.sql`의 indexes/chunks와 immutable/source text 범위/coverage constraints. 기존 0008/0009 bytes 유지.
- UI 조사 담당들의 공식 자료 보고는 output/t07-wiki-query-ui에 저장한다.

## 실행·권한·한계

PostgreSQL 18/vector0.8.6, 기존 Python Docker 배포를 유지한다. 모델 runtime은 별도 image로 기존 ML 기반을 재사용하고 앱에 거대한 ML dependency를 섞지 않는다. 공개 BGE-M3 기본 선택과 기존 Terra Medium OAuth·같은 공개 논문 전송 승인을 재사용하며 새 API key나 provider는 만들지 않는다. live 원본 source DB에 migration하지 않고 wiki_pg 실험 사본과 fixture만 사용한다.

CodexProvider는 native PDF 입력이 없으므로 원본 요청 시 registered PDF bytes를 로컬 검증·보존하고 이미 보존된 exact original-page image를 전달하는 경로를 명시한다. 이미지 전달을 PDF bytes 전달로 기록하지 않는다. 원문 이미지 근거가 없으면 unresolved로 남기며 D2I 재실행/새 I를 만들지 않는다.

현재 전체 앱 592개(576pass/16skip), raw Markdown 문서 오류12개가 baseline이다. 정식 P/W/B 계약·outbox70 미수렴·기존 K 검토2건·전체 T07/T10/T11/T12 완료는 이번 수직 구현과 구분한다. 새 query 결과에 독립 evidence/authority를 부여하거나 UI의 history를 canonical Revision으로 바꾸지 않는다.

## 진행

- 공식 UI 조사 보고 2개 완료, 설치/배포0.
- BGE weights와 별도 local runtime 준비, strict 답변 계약 및 PG retrieval schema를 병렬 구현 중.

## 구현·실물 관찰

모델/SQL/답변/Runtime과 CLI·host runner를 구현했다. 공개 고정 BGE weights 7개/2,295,415,758 bytes를 준비했고 모델·앱 Docker는 별도다. actual index는 154문서(37 Wiki/30 K/87 I),261구간/1024차원이며 49 I 본문과38 image-only I의 제목descriptor를 구분한다. 기존45표/6,148행과0001–0009는불변이다.

실제 Terra trial에서 SuperMApo 원문제조요약과 요청원본p13이미지 확인이통과했다. BMDC/통계답변의선택인용부족은보류했다. lot질문의초기답변은부분I에서전논문부재로과장됐으며독립검토뒤subsetscope규칙추가·원본재확인·새round로수정했다. BMDC의미등록SI요청반복은동일본문page조회로해결되지않아needs_attention을남겼다. structuredstatus모순은invalid_response로보존하고새round재검토를구현했다. 실패/보류를삭제하거나품질pass로표시하지않는다.

추가된조회는D2I0/canonical쓰기0이며실제전달은receipt로집계한다. 개인실험처럼보인합성부정시험문구는자동승인검토가외부전송을거절했고실행하지않았다. 공개논문의필터lot미기재질문으로안전하게범위를바꾸어승인후시험했다. 현재이작업을막는승인요청은없다.

최종전체tests·정확모델호출수·남은사항은[최종보고](../output/t07-wiki-query-ui/REPORT.md)에기록한다. 정식taskT08의AT09/AT10/AT51/AT53/AT54/AT55/AT58/AT65/AT76/AT78/AT80/AT81/AT83/AT104 및 추가 AT107 전체, K2W/W/P 및 CLI release전체를완료처리하지않는다. T07은이후속plan파일명이며기존scheduler taskT07전체완료를뜻하지않는다.

## 이 수직 구현 완료

최종643개앱tests는627pass/16skip,123.718초/exit0이다. 실제6query에Terra23회(Generator16/Validator7), 최종4answered/1needs_review/1needs_attention을확인했다. Clarke funding은실제Information search후p12 I를찾아정확grant번호를인용했다. 미등록SI와인용부족은성공처리하지않았다. 독립semanticQA·이전정답과실패·보완후round를모두보존한다.

공식UI조사와연결권고를완료했다. 첫읽기UI는Quartz,온라인협업편집/권한이우선이면Wiki.js를권고하며Obsidian은선택적클라이언트다. GUI설치·배포는하지않았다. 문서validator는기존raw표오류12개/exit1이며신규오류는없다. 원본45개표/6,148행과이전schema행/hash는불변, 새임시컨테이너는--rm, danglingimage0을확인했다.
