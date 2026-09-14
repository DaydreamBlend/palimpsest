# 논문별 Wiki와 공통 주제 문서 — 첫 구현

2026-09-12 사용자는 구현 착수를 요청했고, 이전 논문 묶음의 논문별 Wiki 페이지와 BMDC 같은 별도 주제 문서를 지정했다. 우선 기존 D/I가 완료된 Test_Paper·Clarke·Dejani 3편(87 I)을 사용한다. BMDC에 없는 출처를 억지로 연결하지 않는다.

## 범위

- 첫 slice는 기존 PostgreSQL D/I를 검증하여 만드는 **비canonical Wiki projection**이다. 고정된 논문 template, source별 LLM 편집/독립 검증, topic별 출처 분리 집계, 안정적 page ID와 immutable JSON snapshots·current catalog, Markdown 내보내기를 구현한다.
- 정식 P의 W-없는 입력 계약/DB migration, GUI, 인터넷 자동 수집, 새 K/N2E/K2K 생성은 이번 slice와 구별한다. 위키 파일을 만들었다고 새 canonical K/P 또는 authority-confirmed Decision을 생성했다고 하지 않는다.
- 기존 D/I/raw/IDs/profile/Revision은 유지한다. 원문 보완을 이유로 D2I를 다시 실행하지 않는다. 기존 DB의 0007 승인은 이 새 작업과 별개이며 이번에는 migration을 실행하지 않는다.

## 구현과 소유권

1. source inventory와 독립 평가: 보존된 3편 입력·BMDC/MoDC 등 구분을 read-only로 확인한다. gold는 모델 입력으로 보내지 않는다.
2. `paper_wiki.py`: proposal/decision schema와 구조·exact I evidence 검사, 고정 Markdown renderer. 독립 구현자 소유.
3. `paper_wiki_prompts.py`: source-only 논문 편집과 독립 Validator. 전체 I와 실제 I 이미지를 전달하고 선택한 인용 원문을 읽기 쉽게 구성. 별도 구현자 소유.
4. root: `paper_wiki_runtime.py`/projection 파일 저장, CLI와 기존 model worker 연결. 실제 source 검증은 기존 CompilerRuntime/KnowledgeRuntime 입력 검사를 재사용하며 모델 호출은 저장 lock 밖에서 수행한다.
5. source별 승인 결과로 논문 문서를 만들고 topic contribution을 집계한다. topic 문서의 per-paper 내용은 검증된 동일 items를 재사용해 새 추론을 만들지 않는다. K 통합은 없다.

## 검증

- 구조: 모든 source I 검토, owned block/quote/media refs, full source/media digest, 없는 ID/경로/레이아웃 제어 거부, source-only 판정.
- 저장: 동일 request replay, page identity 유지, stale catalog 거부, 실제 Linux 파일 lock/atomic current 선택, immutable snapshot 보존·export 재생성.
- 실제 입력: 3편별 모든 I와 I 이미지를 같은 승인된 Codex OAuth Terra Medium에 전달. Generator와 Validator의 실제 profile/prompt/schema/input/output/attachment receipt를 보존한다. 실패·재시도와 실제 전달을 구분한다.
- 의미: BMDC와 다른 DC 종류, 처치×결과 조건, source별 귀속, 정확 인용의 충분성을 독립 감사한다. 정형 JSON/문서 자체를 의미 정확성 증거로 사용하지 않는다.
- 결과: 논문별 3개 페이지, 모델이 실제 선택한 topic 문서, backlinks/목차/원문 증거 refs, 반복 입력과 추가 논문에 의한 갱신 이력을 확인한다. 주제 개수 목표는 두지 않는다.

## 진행

- 기존 3편의 Data/source inputs는 보존돼 있다. 기존 앱0.5.0과 PG test/live 컨테이너는 재사용 가능하다. 공개 출처 증거는 이전 실험에 기록돼 있다.
- Source 담당자가 18개 exact 인용과 독립 gold를 확인했으며, BMDC의 직접 실험 근거는 Dejani에만 있다. source inventory와 gold는 생성 입력에서 제외한다.
- 작업 중 결과와 실행 명령·오류·미완료 항목은 아래에 추가한다. T05 번호는 이 후속 실행 plan 이름이며 기존 전체 task catalog의 T05/다른 task 완료를 선언하지 않는다.

## 저장·실행 검증 중간 결과

- `palimpsest-wiki:0.6.0` Docker 앱을 빌드했다. 새 Python dependency는 없다. 첫 고정 이미지 전체 검사: 529 tests, 513 pass/16 환경 skip, 89.564s, exit0. 이후 명시 review notes 편집을 추가해 release image 검사를 다시 실행 중이다.
- 실제 Linux projection store 7/7, Runtime 18/18 pass. Runtime 중 2개는 전용 실제 PostgreSQL D/I와 보존 검사이고 16개는 canonical 조회를 mock한 실제 Linux 파일/lock 테스트다. 모델 receipt는 이 테스트에서 합성이다.
- Validator 입력과 다른 proposal 파일, frozen input과 다른 source owner, 이미지 byte 변조를 거부한다. 단계 중단과 catalog commit 직후 중단에서 같은 요청을 복구한다. 동일 Data의 page UUID와 이전 snapshot hash chain, 공통 topic의 출처별 누적, topic dormant/재등장 identity를 확인했다.
- 실제 보존 DB는 읽기 전용 transaction으로 32개 canonical/runtime 테이블의 총4,427행을 해시했다. `database-before.json`에 값 자체 없이 count/digest만 보존한다. Wiki 모델 worker에는 DB authority가 없다.
- Test_Paper 1차: 전체36 I/50 image 전송, 생성13 items/7 topics 구조통과. 별도 Terra Validator가 인용 부족4 items를 needs_review 처리하여 current 미반영. 독립 감사가 승인된 2 items에서 시간 기준·문장 continuation 근거 문제를 추가로 찾았다.
- 2차는 기존 Validator 피드백으로 다시 생성했으나 `used` 검토와 실제 citation I 집합이 달라 `paper_wiki_review_evidence_mismatch`로 구조거부했다. 원래 응답·실패를 보존하며 Validator 호출/문서 반영은 하지 않았다.
- 추가 검토 지적을 숨기지 않도록 `wiki prepare --review-notes`를 구현했다. 같은 source의 기존 요청에 메모를 연결하고 새 input/request hash에 결속한다. explicit notes가 있으면 compiled 페이지도 새 편집으로 검토할 수 있으며 기존 current/history는 새 결과 검증 전 유지된다. 메모 자체는 승인이나 원문이 아니다.
- 3차는 1차 피드백과 독립 감사 메모로 진행한다. 과거 응답/판정/원문/ID를 수정하지 않고 D2I도 다시 실행하지 않는다.

## Test_Paper 첫 반영과 다중 논문 진행

- Test_Paper 3차는 CIA 기준 점수 인용 부족으로 재보류됐고 독립 검토에서 human 제조 조건 및 CIA 투여 횟수의 항목별 인용을 추가 지적했다. 4차는13 items/7 topics/36 I reviews/24 citations가 구조검사를 통과하고 별도 Terra Validator가 전부 accepted·complete로 판정했다. source-I spot review도 기존 문제 수정을 확인했다. 논문1/주제7·catalog v1로 반영했다.
- 첫 실제 export는 원본 PDF SHA-256, 모든 I 근거와 exact 인용24개, wiki 링크22개, 동일 renderer/catalog의 byte-identical 재생을 검증했다. `verification-after-first-paper.json`은 당시 결과를 고정한다.
- Clarke 1차는 item에서 참조한 기존 topic3개를 response topics에 선언하지 않아 구조거부됐다. 2차는12 items/6 topics로 구조통과했지만 PD-L2 선행 문장과 LPS 조건의 인용 부족으로 Validator 보류됐다. 독립 검토는 처치 순서, 평균/개별 donor 표현, R848 농도 인용을 함께 지적했다.
- 일반 topic scope를 특정 논문 실험에 묶는 문제가 발견돼 prompt를 명확히 했다. 새 일반 topic은 재사용 가능한 개념 범위로, 실험 조건은 논문별 items/contributions로 보존한다. 기존 topic의 정의·IDs는 덮어쓰지 않는다. 모든 job에는 실제 prompt/profile hash가 남고 과거입력은 변경하지 않는다.
- Clarke 3차는 기존 Treg topic의 scope를 바꾸어 구조거부됐고 Validator 요청은 생성되지 않았다. worker를 요청 없는 경로로 시작한 한 번의 실행은 FileNotFoundError로 호출 전 종료됐다. 실제 provider 호출이나 의미 판정으로 세지 않는다. 독립 감사는 앞선 문제 수정과 새 Methods 순서 오류를 구분했다. 4차에 이 feedback을 전달한다.
- 마지막 code spot review의 CLI stage replay 상태 표시 P2도1줄 수정했다. 이미 compiled인 job은CLI에서도compiled를반환하며 새target2tests통과. 신규 topic 정책을 포함한 **최종 Docker 이미지534 tests,518 pass/16 skip,84.828s,exit0**. 이미지/profile/문서 검사 한계는 `runtime-verification.json`에 남긴다.
- 문서 bundle validator는 이전 raw Markdown의표오류12개로exit1이다. Windows 문서 mutation tests44개는기존표오류1failure와fixture copy의긴경로/isolated provider작업폴더접근때문70 errors로실패했다. 이 결과는앱534tests의실패가아니며문서검사를통과했다고주장하지않는다. 보존대상raw를이목적으로고치지않았다.

## 실제 회귀 원인에 따른 인용 추가 편집

- Clarke4차는12items/7topics로 구조통과했지만 overview LAL 정의, CD86L 표기 변경, PD-L2 선행 인용의3개가Validator에서보류됐다. 5차는그문제를고쳤고Validator가all-accepted로판정했으나, 독립감사가R8485μM의item자체근거가다시빠졌음을찾았다. 5차는current에반영하지않고proposed 이력을보존했다. 이약어표에는CD40/86L 표기도있으므로CD86L을OCR오류로단정하지않는다.
- 원인: 전체논문을매번다시작성하도록하면한인용을보완하며다른인용을제거하는회귀가생긴다. 요청의자료와modelresponse를수동교정하지않고 **`wiki prepare --citation-repair`** 를추가했다. same-source와기존validation-context/proposalhash에base를고정하며기존items/text/sections/topic/evidence를보존하고정확citation추가만허용한다.
- repair의LLM응답은additions/reviews/complete/issues다. 전체I와기존full인용·media를전달하며reviews도전체I를다시검토한다. 추가근거를찾을수없거나본문수정이필요하면emptyadditions/completefalse로보류한다. 새정규화결과전체를다시별도Validator에보내므로patch자체를승인으로취급하지않는다.
- repair부모는기존needs_review/failed(유효proposal필요)이며명시review_notes가있을때compiled/proposed도새편집기준으로쓸수있다. 이전current/응답/판정을변경하지않는다. 일반re-edit와근거추가전용모드의request/inputhash를구분하고없는모드기존requestfp는유지한다.
- Clarke6차repair입력: `01a093a7-54cc-7d26-a538-fd7070d3128a`. 본문12개·주제7개를고정한채R848의명시Figure근거추가를검토하도록준비했다. 이시점의실모델repair성공은아직미판정이다.

## 최종 실물 결과

- [결과 보고서](../output/t05-paper-wiki/REPORT.md), [전체 검증](../output/t05-paper-wiki/verification.json), [현재 Wiki 목차](../output/t05-paper-wiki/wiki/exports/b8894b5d5542325e6fdb730251fe2c289c7b1d399aa6598c867992d2d0e7ad1d/index.md).
- 최종 반영: Test_Paper4차, Clarke7차, Dejani2차. **논문3·주제22·본문37항목·전체87 I·94개 I 이미지**. 실제 provider 호출은 실패/보류를 포함22회이며 독립 감사 feedback이 개입한 개발 실험이다. 무인 첫 시도 정확도라고 보고하지 않는다.
- Clarke6은 인용1개만 추가하고 기존12본문/주제/근거가 그대로였으나 새Validator가 배양농도의‘각각’ 표현을 거부했다. `--repair-item`으로 해당1개text만 허용범위에 고정하는 옵션을 추가했고7차는 그 문구만 바꾸어 전체Validator를 통과했다. 기존 인용·나머지본문·topics는모두같다. 해당결과는별도 비교JSON에보존했다.
- Dejani1은 기존topic 정의변경으로 구조거부됐고2차는인용3곳과범위를보완해통과했다. BMDC새페이지를만들었으며 human MoDC/Th17은기존Clarke페이지의동일UUID에새snapshot으로확장됐다. 두공통페이지의출처1→2·이전contribution불변을 [실제 이력 검사](../output/t05-paper-wiki/common-page-history-verification.json)로확인했다.
- 인용72개 exact char/source refs, Wikilink73개, 원본PDF3개 SHA, 모든I입력일치, export byte replay가 통과했다. 기존DB32tables/4,427rows는전후전체hash가같다. D2I·migration·canonical K/P/W 효과0이다. 실제Clarke의prepare/stage/decide재생도같은page/snapshot/commit과compiled상태를반환했다.
- 최종 image `palimpsest-wiki:0.6.0`, `sha256:c82bf4c95b68cdbc8c2707b605bc0aaf3edf286fe698ecf5bd1b870acd0fa07e`. **앱555tests:539pass/16skip,errors0/failures0,90.078s,exit0**. Wiki Runtime대상23개중실제PG2/mockcanonical+Linux21을구분한다. 문서검사는앞서명시한실패를보존하며새Wiki결과를그대체로사용하지않는다.
- 변경파일: `src/palimpsest/{paper_wiki,paper_wiki_prompts,paper_wiki_runtime,wiki_projection_store,cli,__init__}.py`, `pyproject.toml`, `tests/app/test_paper_wiki*.py`와`test_wiki_projection_store.py`; `AGENTS.md`, `README.md`, `docs/INDEX.md`, `docs/decisions/{USER_OVERRIDES,DECISION_REGISTER,PAPER_WIKI_PROJECTION}.md`, `docs/interfaces/PAPER_WIKI_PROJECTION.md`, 본plan및`output/t05-paper-wiki`의실제실험기록이다. 새dependency나SQLmigration은없다.
- Wiki실행컨테이너는`--rm`으로정리됐고dangling image0개를확인했다. 기존정상DB·image·volume·원문artifacts는삭제하지않았다. 전체task T05/T10/T12 완료를선언하지않으며 정식P/DB연결·KRevision연결·검색·crawler·GUI는후속범위다. T10 gate AT54/AT61/AT62/AT72/AT78/AT83/AT104를이projection출력으로완료처리하지않는다.
