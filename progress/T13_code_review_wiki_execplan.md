# Python 코드 D2I → I2K 검토 재개 → Wiki/RAG/Electron

2026-09-13 사용자 지시: 남은 구현 목록에서 권고한 순서대로 계속 구현한다. 이번 수직 범위는 Python-native D2I, 미해결 I2K 검토 재개, 그 결과와 기존 K2K provenance의 Wiki 검색/Electron 조회다. K 일반 의미개정/전체scheduler/개인Decision/온라인수집은 후속이며 전체 roadmap을 완료 처리하지 않는다.

## 보존·권한·완료 기준

후속 사용자 재확인: 제품 D2I에는 Terra 등 application LLM이 개입하지 않는다. 선택한 MinerU 내부 OCR/layout VLM만 예외이며, 코드/Markdown 구조화·청킹·전체 원문/좌표 검증은 스크립트다. 개발 중 LLM 품질 감사는 별도 평가로 기록하고 I 생성·채택의 필수 의존성으로 만들지 않는다.

- 현재0.12/schema0013의 D/I/SQL/profile/Record와 기존 논문·코드 실험을 보존한다. 새 Python parser profile만 명시적으로 추가한다. I2K/질의는 D2I를 호출하지 않는다.
- 기존 코드 snapshot의 exactbytes/manifest를 입력으로 사용하고 파일별 문법 구조를 읽는다. 원본의 모든 wrapper/주석/공백/미지원언어/parse오류 구간도 보존하며 application D2I LLM은0이다.
- 실제 모델 평가에는 명시 승인된 V1/V2 코드 사본 bytes만 사용한다. 새 workspace 전체 파일의 외부 전송이나 기존 원문 DB migration으로 승인을 확대하지 않는다.
- 코드 전용 D2I 착수 승인은 이전 parser-deferred 지시보다 최신이다. 명시된 새 parser 평가를 I2K 근거 공백을 고치는 자동 재파싱으로 바꾸지 않는다. 기존 완료 source execution은 변하지 않는다.
- parser의 원문/좌표 검증, 합성 Runtime/DB 테스트, 실제 LLM 의미 검토, 실제 Electron 동작을 각각 보고한다. 보류/실패·추론 origin·현재/과거 version을 숨기지 않는다.

## 단계와 소유권

1. `code_adapter.py`: stdlib AST 기반의 순수 source bundle/단위/segments/coverage. agent가 단독 소유. Root는 CompilerRuntime/d2i/I2K/좌표 조회/CLI 연결.
2. `knowledge_review.py`: 모든 I/target/item의 검토 상태·실제 reasons·accepted refs·이전 시도와 resume_prepare. agent 소유. Root는 동일 parent의 중복 진행 방지, CLI/provider runner와 source-grounding 필요 경계.
3. `wiki_retrieval.py`: exact selected-I support route, K2K의 실제 premise/transitive근거와 버전 현재성, corpus/index결속. agent 소유. Root는 Wiki 문서/질의 계약과 Electron의 좁은 읽기·검토 실행 경로 연결.

공통 schema/migration/commit 경로의 소유자는 Root 하나다. 같은 fixture DB에서 여러 suite를 동시에 실행하지 않는다. 원래 paper DB는 검사·migration 대상으로 사용하지 않는다.

## 구현 판단

처음에는 같은 generated code dossier D를 Python-native profile로 읽는다. 파일별 D/membership이라는 별도 새 identity model은 이번에 도입하지 않는다. 텍스트 좌표의 기존 계약을 재사용하고 code_context에 원본 member/symbol 위치를 추가한다. 큰 함수 자체를 임의의 길이로 자르지 않으며 soft grouping target은 profile에 기록한다.

I2K 검토 재개는 기존의 정확한 source input과 version 문맥을 유지한다. 같은 의미의 K를 다시 만들지 않고 실제 Validator reuse에 연결한다. 완료된 검토의 무조건 반복과 아직 처리 중인 호출의 중복 dispatch를 막는다. 호출 횟수를 성공 종료 조건으로 삼지 않는다.

K2K 검색의 근거는 선택한 source 실행의 I까지 완전하게 도달하는 accepted support 경로다. 가짜 direct I grounding을 만들지 않는다. source-version/current premise 상태와 검색용 projection을 분리하고 기존 index/history를 재작성하지 않는다. 기존 source-only query 답변 정책과 accepted-inference 답변을 혼동하지 않는다.

## 검증 계획

- Python/BOM/CRLF/Unicode/decorator/async/class/중첩/문법오류/미지원파일/빈파일과 전체 exact D 복원·양방향 위치.
- parser profile과 DB materialization/replay/실패복구, 기존 Markdown/PDF source history 회귀.
- I2K status/resume의 frozen source·version·review reasons·기존Krefs·동일요청 replay·동시중복 방지와실제미해결검토.
- Wiki corpus의 직접/추론 근거 구분, 누락된 premise/source 배제, version head 변경 후 stale index 차단, historical read 보존.
- 실제 scoped code Data→I→K와 source-aware Wiki 페이지/검색, Electron에서문서·I·원문·KRevision/추론/버전조회.
- 현재image의관련tests와필요한전체회귀를단독fixture실행. 기존문서validator의vendor/raw 오류와직접작성문서오류를구분.

## 현재 진행

Python-native parser, Runtime/CLI 저장·양방향 위치, I2K 검토 상태·재개·전송 파일 검증, exact 버전/전제에 결속된 추론 K 검색과 Electron 읽기 구현을 연결했다. 최종 whole-suite와 실제 Electron 확인은 진행 중이다.

- 실제 승인 코드 A의 101,675 bytes를 native source execution `01a09a68-700c-7c5c-bbd2-1e4bd31f9cd5`의 28 I로 저장했다. 전체 원문 재결합이 정확히 같고 D2I application LLM/OCR 호출은 모두 0이다. 기존 Markdown 5 I·완료 기록은 보존했다.
- 첫 I2K `01a09a69-26ac-73be-9326-75771045ce6f`는 전체 28 I를 검토하고 K 8개를 새로 채택, 기존 K 7개를 재사용했다. 21 I에 추가 의미 항목 검토가 남아 상태는 `needs_human`이다. 이를 완료로 숨기지 않고 같은 입력·V3·실제 Validator 이유로 재개 실행 `01a09a74-ee55-7578-ad33-3ac3960fa25f`를 준비했다. 이 과정은 D2I를 호출하지 않았다.
- 초기 review/desktop PG 40검사 중 5오류는 합성 receipt의 delivered_data_version_ids 누락이었다. fixture를 고친 후 관련 7/7 pass. 실제 입력 보호를 완화하지 않았다. 추가 전송 파일 변조 검사와 추론 query 검사를 진행한다.
- 자동 승인 검토가 같은 코드의 native 28I I2K 전송을 한 차례 차단했다. 승인된 기존 V1의 5I와 새 28I가 원문 바이트까지 같고 새 파일이 없음을 `authorization-source-equivalence.json`으로 입증한 뒤 기존 승인을 인정받아 진행했다.
- Wiki 모델 호출은 별도 범위라는 자동 승인 검토 거절 후 정확한 준비 파일을 사용자에게 제시했다. 사용자가 “동일 코드의 Wiki 생성·검증·재검토 전송 승인”으로 명시 승인했다. 승인 후 첫 Wiki Generator를 실행 중이다. 차단된 시도는 전송되지 않았으며 D2I에 LLM을 도입하지 않았다.

## 최종 관찰과 범위

[실제 결과](../output/t13-code-review-wiki/REPORT.md), [검증된 호출/결과 요약](../output/t13-code-review-wiki/actual-summary.json)에 원문·K·Wiki·검색·실패 이력과 실행 명령을 연결했다.

- 두 번째 I2K는 completed,28 I reviewed/모든pending0. 두차례신규K16개·기존Revision재사용7건이다. 첫needs_human을과거판정그대로보존했다.
- 새K2K1개를독립검증/저장했고exact전제2개,직접I0,transitive참조3개를검증했다. 자료A→B→A3version/V3head,기존D3/214 I·과거16개행hash묶음은137readonlyassertion에서유지됐다.
- 코드Wiki는1차3항목,2차상수정의인용부족1항목을보존하며3차citationrepair후compiled. 본문18항목/1page를DBsync했다. wrapper의중복결과파일쓰기만실패한경우는sync성공과구분해기록했다.
- 실제BGE-M3:70문서(전체I28/K24/Wiki18),125검색창,현재K2K1개포함. 코드질의는I9/K4를전달하고directsource/K2Kinference를구분해answered. 질의전송은별도자동승인거절후사용자명시승인,모델2호출,canonical/D2I쓰기0.
- 전체실제Terra14호출(I2K4/K2K2/Wiki6/query2),D2IapplicationLLM0. 원문code여러개에대한일반회수율검증이아닌이통제source의실제결과다.
- 최종appimage8fea4752b223…에서831검사(815pass/16skip)exit0. 기존PDFruntime22pass로16skip보완/6중복. 신규focused35pass,문서Markdown7pass. bundle전체는기존외부vendor/raw/복제948오류로exit1이며현재작성문서오류0. validator전체mutation복사suite는이번변경범위가아니므로재실행하지않았다.
- Electron0.2 source/ASAR18pass와실제source/package읽기를확인했다. 첫연결timeout은sandboxDocker접근거부였고기존승인된실행경로로해결했다. 보류/실패캡처와현재버전K·실제추론질의화면검사결과는UI보고서에보존한다.
- 사용자용량질의에61.246GiB중53.644GiB모델임을실측했다. 이어사용자가현재역할없으면전부지우도록승인하여Qwen/Gemma9가중치47.395GiB를삭제했다.65metadata파일SHA/MinerU/BGE/Paddle/원문/기록은보존했다. 정리후약14.293GiB다.

이번에완료한경계는Python-native dossier D2I,전체I2K검토상태/재개/요청검증,현재source-version/추론의Wiki검색·읽기연결이다. 직접Dcanonicalgrounding,범용materialrevision/상충/시간/자동scheduler,다른언어nativeparser,개인Decision,새질의·등록의GUI실행,온라인수집과전체releasegate는남은항목이며완료로표시하지않는다.
