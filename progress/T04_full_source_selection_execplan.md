# 전체 I의 LLM 선택과 출처를 구분한 K 재사용

2026-09-11 요청한 bounded 구현·실물 실험 완료. 사용자는 D의 어느 구간에서든 해당 I를 찾고, 어느 I에서든 D의 정확한 구간을 찾을 수 있어야 한다고 명시했다. 복원 기준은 I에 원문 내용을 보존하고 provenance가 연결한 original Artifact에서 원본 파일의 exact bytes를 복원하는 것이다. PDF를 I만으로 byte-identical 재인코딩하는 요구는 아니다.

그 다음 전체 I가 I2K 루프에 들어가야 하며 중요성은 LLM이 판단한다. 일반 명제의 거의 완전한 의미 중복은 기존 K를 재사용하고, D가 다른 실험 결과 등 source-specific 지식은 유사해도 보존한다. accepted K 이후 N2E를 실행한다. 이 명시된 범위가 직전 principal-claims-only 실험보다 우선하며 나머지 P/U와 과거 source/K/Revision/판정을 재작성하지 않는다.

## 실행 범위와 소유권

- 원문 담당 agent: source_reconstruction/source_pages, compiler_runtime, 관련 d2i/source schema profile와 tests. 기존22sourcegroup과파서산출물을재사용하고 originalpage facsimile14개를새sourceprofile에서추가해36I를저장한다. 원문block이나MinerU결과로위장하지않고원본PDF/page/이미지profile·hash를명시한다. D→I구간조회/I→Drefs/원본export를검증한다.
- Knowledge 담당 agent: 새i2k_selection의순수schema/검사/FP와knowledge_runtime의selectionprofile·전체I검토·scope일치·reuse/추가저장과tests.
- SQL 담당 agent: 추가0006_i2k_selection과PG제약tests만소유한다. 0001–0005는동결한다. I검토와review→Record참조, K identity scope는append-only이며같은transaction에결속한다.
- root: 승인문서/CLI/worker/실제Terra실험/Docker최종검증·정리·보고. 공유schema는SQL담당한명만편집한다.

## 계획

1. 현재실제27K/21E/34grounds와0005 DB/원본source를보존하고baselineinventory를저장한다.
2. 양방향source주소를구현한다. 현재파서block전체coverage는D전체coverage의증명이아니므로, 빠진시각영역은실제로저장된full-pageImageI로찾을수있게한다. OCR텍스트검색품질과페이지시각coverage를구별한다. 원본export는overwrite없이SHA동일성검증.
3. 새로운source-complete-i2k-v1은선택한하나의completedsource실행의모든I를입력/전달/검토한다. 서로다른과거sourceprofile의I를합쳐중복입력하지않는다. LLM이각I의selected/context_only/not_selected/needs_review와이유를출력하고스크립트는누락·참조·구조만검증한다.
4. 후보identity_scope를general/source로LLM이분류하고Validator가중요성·scope·의미동등성·근거를독립검사한다. Observation은source-specific이다. source-specific결과해석Proposition도다른Data로merge하지않는다. 새grounding/동일의미는Revision증가없이재사용하고, 기존legacyK의scope분류추가도원래ID/FP를바꾸지않는다.
5. 실제Test_Paper의새36I를TerraMedium으로처리하고각I검토·선택근거·K/Revision/Edge를DB에저장한다. 같은입력재검토에서의미재사용을실제로평가한다. cross-Data 일반명제reuse/실험결과분리는격리fixture와필요시명시적synthetic문서LLM실험으로구분검증한다.
6. 실제PG에서allI누락/잘못된scope재사용/stale/rollback/identity불변/typedrefs/재시도를검사한다. 전체앱회귀와문서baseline오류집합을확인한다. 성공DB를보존하고이번에생성한임시test자원만정리한다.

## 완료 기준·제한

완료는원문구간의양방향주소/원본복원, 모든I의실제LLM전달·개별검토, 중요성선택과source-aware재사용, acceptedK의후속N2E실행을실제관찰하는것이다. 페이지이미지로찾을수있다는것은모든수식/문자의OCR검색이완벽하다는뜻이아니다. LLM의모든의미판정정확도/논문전체진실/원본PDF전달runtime/일반materialRevision과전체K2K전파완료를주장하지않는다. unresolved문제를완료로숨기지않는다.

## 실제 결과

[보고서](../output/t04-full-selection/REPORT.md), [최종 DB 요약](../output/t04-full-selection/summary.json), [독립 검토](../output/t04-full-selection/semantic-review.md)를 보존했다.

- 새 source execution `01a08f4f-d4fd-7563-8fd7-90e3e2ae0e5d`: 기존22group+14originalpageImage=36I,50media.229originalblocks+14pageblocks=243개 exact 재조립. 14page의bbox[0,0,1,1] 역조회와 I36→D refs 확인. original PDF export SHA는Data ID와동일.
- 중요성은LLM이판단했고모든호출에서36I·50media와전체review를검사했다. 헤딩/종류/길이선별스크립트는없다. 선택된I의역참조누락2개만후보의실제citation에서완성했고중요성상태/이유/주장/인용은바꾸지않았다.
- 마지막I2K `01a08f8b-081f-7f9c-b895-b92384e6b8ef`: completed, Generator selected5/context28/notselected3, Validator36confirmed,7reuse+2new. 앞선적용까지기존27K→32K,grounding34→69. 신규5개모두Observation. source분류21/역사legacy미분류11, 기존FP/IDs/Revision을재작성하지않음.
- N2E `01a08f96-4b8e-7bc3-8d08-6bb8400d37b1`:32acceptedNodeRevision 입력,5supports 생성/독립검증/저장,completed. 최종32NodeRev/26EdgeRev. 기존27NodeRev/21EdgeRev전체행불변,잘못된owner0/quote0.
- 합성Alder/Birch각5I를실제Terra로검토: general tuple명제는같은Node/Revision에두Data grounding,비슷한fluorescence결과는별도sourceNode. 고유11K=general1+source10. [live검증](../output/t04-full-selection/cross-data-eval/verification-birch-schema2.json).

## 실패와 교정 이력

selected인데후보연결이빈응답,정확quote1개불일치,중복된역참조목록누락을구분했다. 오류를canonical효과로반영하지않고failedcall+sourceexcerpt+이전의미review를다음snapshot에결속했다. Validator의자기candidate와existingRevision동시재사용문제는nestedanyOf닫힌object schema로고쳐새실제판정을받았다. `complete=false`+fullreviews는미완료검토로인정하고누락/복합관측을피드백했다. 개별승인과I에남은추가검토는분리했다.

실패logger에Validatorcontext인자가빠졌던것은수정·회귀검증했고,과거응답의입력/원래export/DBcontext SHA는동일함을읽기검사로확인했다. 늦게도착한Validator실패metadata복구도idempotent하며canonical효과가없다는검사를추가했다.

N2E외부호출자동승인검토가2회거부했으나전송파일을완성·검사한뒤사용자에게명시적승인을받았다. 사용자답변은“같은 Terra Medium으로 전송하여 N2E 실행 승인”이다. 이후같은목적지에서생성·검증했고다른경로로우회하지않았다.

## 실행한 검사와 배포

| 구분 | 명령·범위 | 실제 결과 |
|---|---|---|
| source순수/PG | Docker current src/tests, PDF/Markdown source test와source runtime | 43통과,부모quality호환추가14targeted통과 |
| SQL0006 | `palimpsest-selection-checks`, `test_selection_postgres.py` | 7통과,0006 SHA eefc3b8210ff55b17723d98d849070cc1f7ec5fd2dc3b7e041a4deaf2306c250 |
| 선택순수 | `python -m unittest discover -s tests/app -p test_i2k_selection.py` | 최종12통과 |
| 선택Runtime | 실제PG,scope/allI/receipt/review/feedback/legacy/metadata회귀 | 최종release전체suite에포함 |
| JSONschema | task-temp jsonschema4.23.0 Draft202012Validator | 12사례통과,실제invalid재사용응답거부 |
| 전체앱 | `docker compose -p palimpsest-selection-checks run --rm --no-deps -T ... --entrypoint python app -B tools/run_app_tests.py` | 최종431중415통과/기존PDFium16skip/실패0오류0,57.057초 |
| 실제DB | `verify_final.py` | Node32/Edge26/ground69,oldRevision전체행불변/owner·quote검사통과 |
| 최종이미지 | `docker compose -p palimpsest-knowledge build app` | palimpsest-selection:0.4.0, SHA9e34e0d652df0868f114770810f0b3a021dcd114e70ed43980f9329e7a6c8d9e |
| 이미지CLI | source bind없이`knowledge graph --data-id ... --json` | export graph.json과동일 |
| 문서validator | `python tools/validate_bundle.py --json` | 기존rawMarkdown12오류만,새오류0 |

새baseline README를이동한.md로검사하면서49개상대링크오류가발생했다. 정확bytes를유지하는README.md.snapshot으로명확히보관하고hash manifest를남겼다. 실제문서링크를고치거나raw기존12오류를숨기려고validator를완화하지않았다. Windows긴경로문제회피를위한동일Linux문서unit은44개중43통과/기존baseline실패1/errors0,148.887초였다. 결과는output/t04-full-selection/document-tests-linux-summary.json에보존한다.

## 보존과 남은 범위

실제Data/I/K/E는palimpsest-knowledge의PG/ArtifactStore에보존한다. 합성검사palimpsest-selection-checks의컨테이너/4volumes만export후삭제했고기존사용자자원은보존했다. 제거할새danglingimage는없었다. terminal기각context의로컬교환초안2개는정리했고,별도로실패/보류된시도의후보·metadata는복구이력으로유지했다.

실물모델은이번Paper12uniquecalls(input1277008/output47762,1003.547초),별도synthetic7calls(input338003/output9295,205.906초). 실제Generator재사용은새호출로중복계산하지않았다. 구현교정비용을정상운영성공률/비용으로일반화하지않는다.

최신I2K/N2E실험은완료됐지만원문시각평가/의미정답률100%,모든개별claim회수,PDFbytes모델전송,대규모분할·BGEindex,일반materialRevision교정,전체K2K전파/T04·T06전체acceptance/GUI완료는아니다. 과거실패5·needs_human2와후보13은이력에있고,outbox58pending을성공수렴으로표시하지않는다. source_role=discussion인Results인용1개와일부24h관찰누락,약한간접supports를독립검토에명시했다.
