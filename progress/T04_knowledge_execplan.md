# Test_Paper I2K → N2E와 Revision graph 실험

상태 IN_PROGRESS, 2026-09-11. 사용자 지시로 D2I 확장/새 파서 실험은 보류한다. 기존 Test_Paper의 원문 I를 Terra Medium으로 해석해 observation/proposition KNode를 만들고, supports KEdge와 exact Revision endpoints를 DB에 저장하는 실제 실험을 수행한다. 최신 요청이 T04와 T06의 이 첫 실행 범위를 명시하며 T05/전파 전체·K2K·W/GUI 완료로 확장하지 않는다.

## 목표와 승인 범위

현재 PDF/MinerU raw와 grouped I 내용은 그대로 재사용한다. 필요한 DB source 복원은 기존 parser 산출물/조립 함수 재생이며 새 OCR/VLM/그룹 개선이 아니다. 모델은 기존에 승인한 Codex OAuth `gpt-5.6-terra`, reasoning medium으로 호출한다. API키를 만들거나 토큰을 읽지 않는다. OpenAI Docs와 기존 provider 코드를 확인했고 API-key 스킬의 신규키 경로는 이미 지정된 OAuth 실행에 적용하지 않는다.

I2K는 node만 생성·독립 검증 후 저장하고, N2E는 이미 accepted된 exact NodeRevision을 입력받아 supports edge를 생성·검증한다. Abstract/Results는 grounding의 문서 역할이며 같은 의미면 K reuse와 grounding 추가가 맞다. graph 모양을 만들기 위한 중복 node/self supports는 허용하지 않는다. Observation은 논문이 보고한 실제 실험/측정에 한정하고 환자효능이나 미보고수치를 추론해 만들지 않는다.

## 적용 계약과 구현 소유권

USER_OVERRIDES/INDEX/DECISION_REGISTER/T04/T06, canonical03/04/05/06와 identity/transaction 계약, CODE_REVIEW/PLANS를 확인했다. first profile은 proposition/observation+supports로 제한한다. 미정 P 전체 승인·일반 자동identity/tolerance규칙·미정revalidation subtype을 확정하지 않는다. 첫 실제논문graph는 초기Revision1 저장, synthetic fixtures에서materialRevision/CAS/과거endpoint불변·applicability를 검사한다.

root는 공통 KnowledgeRuntime/CLI, 모델 worker, DB통합·실험·결과보고를 소유한다. 별도 agent는 knowledge/n2e 순수schema/검사/FP와 unit tests를 소유한다. 다른 agent는 새0005 SQL만 단독 소유하고 root와 컬럼계약을 공유한다. 독립 원문 oracle은 모델 출력 전에 작성한4chains/35quotes이며 모델 정답으로 전달하지 않는다.

## 실행 순서

1. source/기존provider/login 및 exact model 확인. 기본sandbox의codex login status는home검색오류였고 승인된host실행은Logged in using ChatGPT/CLI0.153.4였다. 실제 모델 호출은별도로검증한다.
2. 성공 graph를 보존할 새 `palimpsest-knowledge` DB/Artifact Store를 준비하고 frozen source를 복원한다. 기존22 I의 내용·FP와동일함을대조하되 이전testDB의UUID를임의복구/재작성하지않고새 source실험ID대응표를남긴다.
3. I의원문text/media와간결한provenance를모델에제공한다. 초기원본PDF/전체페이지이미지는자동첨부하지않는다. 필요한원문요청은별도상태로기록하고provider가원본PDF를읽지못하면미해결을성공검증으로표시하지않는다.
4. Generator→deterministic검사→독립Terra Validator→node atomiccommit. 후보전체/현재accepted를검증입력으로주어semanticduplicate를검사한다. 작은실험graph이므로BGE검색미구현이선행blocker는아니다.
5. acceptedNodeRevisions→N2E Generator/Validator→edge atomiccommit. logicalid/currentpointer와immutableRevision/typedFK,실제I범위grounding/Record/실제전달receipt를보존한다.
6. 실제PG에서동시성/retry/rollback/잘못된revisionowner/staleinput/조건차이와표현차이/endpoint-onlyapplicability를검증하고, 별도sourceoracle와실제graph를대조한다. 원문실험의가짜수정은하지않는다.
7. 코드·문서검사와실험결과/실패/제한을보고한다. disposable testDB만정리하고검증된K/Revision이담긴실험DB는유지한다. 무차별Dockerprune이나기존모델/사용자DB변경없음.

## 완료의 의미

성공조건은 실제Terra 호출·독립판정·canonical Node/Edge/Revision/FK 저장과근거에맞는대표supports chain이다. JSON생성만으로의미정확성을선언하지않고형식적인3층구조를강요하지않는다. 원문내NOG/NSG·n=.3·실험일수/단백질표기충돌등은검토의무로남긴다. 전체논문의완전한K추출·K2K전파quiescence·모든P계약/acceptance는이번범위의성공으로간주하지않는다. pending의무/outbox를보존한다.

실제실행·수정·측정·미완료사항은아래누적한다.

## 2026-09-11 실행 결과 — 요청한 첫 graph 실험 완료

[결과 보고서](../output/t04-knowledge/REPORT.md), [최종 graph](../output/t04-knowledge/graph.json), [독립 의미 감사](../output/t04-knowledge/semantic-audit.md), [직접 DB 검사](../output/t04-knowledge/database-verification.json)를 보존했다. 이번 bounded 실험은 완료했고 T04/T06 전체 acceptance와 일반 K Revision/K2K workflow는 계속 미완료다.

- 실제 source 복원: 원본 Data SHA `a2268b37570f41bb07189cf083376e5823fae364165d5e0e256f796a0814cffe`, grouped source 실행 `01a08edf-e477-753d-ac3d-4bba379787bd`. 22 I/36media/14pages, 기존 content/FP 동일, 역사 UUID 대응표 별도. 새 OCR와 청킹 개선 0.
- I2K 실행 `01a08eea-99d3-7e3e-9f2f-2aa51ef85b43`: 첫16candidate/5exactquote오류 반영0 → 실패callmetadata 보존 → 재생성21/독립Validator21accepted. 실제Node21/Revision21/grounding25.
- I2K 해석 패스 `01a08ef4-2b10-7c68-a9f5-902003450fd1`: 기존K를비교하면서ResultsProposition6생성/판정/저장. 최종Node27(Observation19/Proposition8), grounding34.
- N2E 실행 `01a08ef8-3352-7553-8d9d-21478fc9baf5`: 21후보/18accepted/3rejected. 두기각은Proposition→Proposition 자체를independent observation이아니라는이유로배제한policy오류로확인.
- 명확한supports지침의새N2E `01a08efc-4d70-7867-8cf5-9fe717eece96`: 새Proposition관계3accepted. 이전판정/FP/Record불변. 최종Edge21/Revision21, 정확두hop경로9.
- 9actualTerraMedium OAuth calls, input445427/output19676/reasoning2612, 모델호출경과합415.344초. 실제I이미지전달, originalPDF전달0/원문요청0. CodexProvider tools차단·freshValidator세션·profile/prompt/schema/input/output/image hash receipt 사용.
- DB직접검사: PostgreSQL18.6/pgvector0.8.6, 잘못된endpoint소유자0/quote불일치0/임시후보0. K27+21개 모두initialRevision; fake논문Revision2를만들지않음. 48outbox는pending, 전체propagation완료아님.

## 실행한 코드/DB/문서 검사

호스트의 `python`은 inventory의 Python3.12 runtime 전체 경로, 모든 직접호출은 `-X utf8 -B`를 사용했다. 아래축약명은 그실행기를뜻한다.

| 구분 | 실제 명령·환경 | 결과 |
|---|---|---|
| pure K | `python -m unittest discover -s tests/app -p test_knowledge.py` + `PYTHONPATH=src` | 9통과 |
| 기존 provider | `python -m unittest discover -s tests/app -p test_codex_provider.py` | 9통과 |
| actualPG schema | 전용 `palimpsest-k-checks`, `test_knowledge_postgres.py` | 6통과, ownerFK/materialsuccessor/stale/2worker/rollback/applicability |
| actual Runtime | 같은전용DB, `test_knowledge_runtime.py` | 6통과, prepare/stage/decide/replay/reuse/stale/failedcall/미전달sourcehold/receipt/negativeapplicability |
| 전체 앱 | `docker compose -p palimpsest-k-checks run --rm --no-deps -T` + current src/tests bind + `tools/run_app_tests.py` | 388중372통과/16기존PDFiumskip, 실패0오류0,38.165초 |
| 이미지 | `docker compose -p palimpsest-knowledge build app` | exit0,최종 `palimpsest-knowledge:0.3.0`, SHA `3fd2e9af9d7c523e2bf3b752148a10d165ed17ffe42cc9b213f51903461436c4` |
| 실제paperDB | `docker compose -p palimpsest-knowledge run --rm --no-deps -T --entrypoint python ... /results/verify_database.py` | assertions통과,Node27/Edge21/exactrefs/34quotes/9calls |
| 문서validator | `python tools/validate_bundle.py --json` | 기존rawMarkdown12오류,새오류0 |
| Windows문서unit | `python -m unittest discover -s tools -p test_*.py` | 44tests,baselinefailure1+clone MAX_PATH70errors,450.338초 |
| Linux동일문서unit | `docker run --rm --network none ... python /results/run_document_tests_linux.py` | 44중43통과/기존failure1/errors0,147.702초;오류집합12동일 |

Windows 경로 문제를 숨기지 않고 network 없는 Linux에서 동일 tests와 clone정책으로 구분했다. 원본raw문서·validator조건은 수정하지 않았다. 전체앱검사는 최신source/test bind, 최종이미지의추가변경은prompt문구/함수이며 최종DB 읽기검사로배포경로를확인했다.

## 변경 파일과 보존·한계

새 실제모듈은 `knowledge.py`, `n2e.py`, `knowledge_prompts.py`, `knowledge_runtime.py`; 추가migration은 `0005_knowledge.sql`이다. CLI/canonical migration목록/앱0.3.0/Compose기본이미지를연결했고 `tools/run_knowledge_model.py`가승인된hostOAuth호출을수행한다. `tests/app/test_knowledge.py`, `test_knowledge_postgres.py`, `test_knowledge_runtime.py`와CLI버전검사를추가·갱신했다. 문서INDEX/MODULE_BOUNDARIES 및 [KNOWLEDGE_RUNTIME](../docs/implementation/KNOWLEDGE_RUNTIME.md)을연결했다.

공유SQL은한agent만작성했고실PG에서괄호문법오류1건rollback/수정후적용했다. 적용후0005는동결했다. 해시없는임의원문·거짓quote/미디어·stale판정은차단하며, 원본요청영향범위는needs_human, currentedge와historicalendpoint/applicability는구분한다. 기각content는DB및해당로컬교환파일에서정리하고메타데이터/FP/판정근거는유지했다.

성공graph는 `palimpsest-knowledge` DB/ArtifactStore에보존한다. 이작업에서생성한 `palimpsest-k-checks` 컨테이너/네volume만검증후삭제했고기존Docker자원은보존했다. 새로제거할danglingimage는없었다.

독립의미검토: C1급성염증/C2APC는Observation→Results까지만부분충족, C3CIA/C4human-cell은실제Results→Abstract연결이있지만세부coverage한계가있다. 일부exactquote가조건전체를포함하지않고24h대비/음성재구성결과등누락이남았다. 정확도100%·논문전체완전추출·live반복semanticreuse를입증하지않았다. 입력/commit/역사저장은동작하나 일반materialRevision API, BGE비교index, 비교catalog typedFK, 원본PDF전달, 전체K2K/전파종료는후속이다. AT06–08/20/21/24/28–30/41–44/73/74/82/83/107/111/112 및 T06 AT09–17/38–40/75/83/88을전체완료로승격하지않는다.
