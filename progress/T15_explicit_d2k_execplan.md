# 독립 사용자 D2K와 K 개정 후속

2026-09-13 최신 사용자 승인에 따라 [독립 D2K 규약](../docs/decisions/USER_REQUESTED_D2K.md)을 구현한다. 기존0.14/schema0013/I-only 오류 처리와 사용자 데이터 이력을 보존한다. `ponytail` 원칙에 따라 기존CompilerRuntime/ArtifactStore/검증·commit을 재사용하고 신규빈도메인·LLM D2I를 추가하지 않는다.

## 단계

1. **명시적 D2K:** 등록 D의text/PDF page view 준비, 정확manifest 사용자확인, 독립d2k input/profile/Record, Generator·Validator/exactDgrounding/동일의미reuse, I0실패지원. 준비·확인·실제전달·반영을분리하고I2K에서자동호출하지않는다.
2. **소비 경로:** directD/전이D·immutableorigin·current/pinned version, K2Kpremises, 사용자가선택한WikiData범위·검색/직접근거질의·읽기UI. I가없는D를전체등록DB에서임의공개하지않는다.
3. **K개정 후속:** exacttarget/currentrevisionCAS, 독립same-identity/materiality/근거판정, non-materialreuse와materialRevision분리, 과거identity FP보존, 영향을받는K/edge/문서재검토의무목록. 전체scheduler/개인Decision/온라인수집은기존계약의별도후속이며없는부분을완료로표시하지않는다.

## 소유권

Root는공통SQL/migration/KnowledgeRuntime/authorization·source preparation/CLI/최종검증을단독소유한다. pureagent는d2k.py·puretests, PDFagent는tools/run_d2k_pdf.py·nativePDFtests, consumeragent는명확한SQL/API공유후provenance/Wiki/query/desktop Python을맡는다. 동일fixture DB의mutation검사는Root하나가순차실행한다. 기존실제code/paper/WikiDB는복원·격리본을우선하고불필요한live migration을하지않는다.

## 불변성·승인

사용자확인은검토manifest에결속하고모델출력에서는허용하지않는다. I2K오류·단순K선택누락·D2K권한·source품질복구를별개로기록한다. 같은범위retry/history를유지하며실제전송범위/모델변경에는새확인이필요하다. 특정자료D2K를이번기능승인에서추정해실행하지않는다. Source-onlyD2K를시스템추론으로표시하지않는다. D2K성공으로D2I실패를completed로바꾸지않는다.

## 검증 계획

- 확인없음/위조확인/다른hash·view·model·version/재사용scope초과거부; 같은request replay와동시실행중복방지.
- I0D2Ifailure에서D2K준비/반영, 실제원문bytes/UTF8범위/selectedPDFpages/hash/renderer검증; 원문model미전달·Validator같은역할재사용·잘못된quote/페이지거부.
- I2K직접D금지회귀, D2Kdirectgrounding과acceptedRecord/후속outbox원자성/failpoint/retry, same-meaningRevision0추가, origin불변·actualsourceversion.
- D-only 및I/D전제의K2K소비, 선택범위밖Data차단, 부분support경로금지, exactdirectD읽기/검색citation, 과거query/history보존.
- materialtargetstaleCAS/다른logicalscope/같은payload새Revision거부, 새contentFP+기존logicalFP, exactold/newrefs·미해결변경영향보존.
- 단위/실제격리PG/nativePDF/UI/실제provider평가를구분한다. 미실행은pass로기록하지않는다.

## 현재 진행

현재코드와계약을읽고pure D2K/PDFview/consumer범위를분리했다. 0.14에는d2k operation/직접Dgrounding이없으므로additiveSQL과명시적사용자요청서비스가필요하다. 함수모양·sourceview좌표를조정중이며DB/provider실행은아직0이다.

2026-09-13 구현 진행: pure D2K17검사와기존CLI14검사통과. PDF native9검사는기존고정renderer에서통과했다. 기존Kcatalog의rawD인용누출을차단하고현재성기본값을정규화했다. 독립manifest/확인/Runtime/CLI를연결했으며0014SQL은별도agent가현재작성중이다. 첫DDLrollback검사에서PLpgSQL예약어authorization를변수로쓴문법오류를발견하여수정중이다. 아직0014미설치/liveprovider0이다.

테스트DB `palimpsest`를template로복사하는중PG의untracked child process exitcode2로서버가자동재시작했다. WAL자동복구후접속과기존codeDB D3/I242/K42/KRevision42/DataVersion3/schema0013을확인했다. 원인을확정하지않으며실패한복사DB는생성되지않았다. 이어template0로빈`palimpsest_d2k_checks`를만들고기존0001–0013을적용했다. 현재T15mutation검사는이DB만대상으로한다. 실제code/paper/WikiDB는변경하지않는다.

## 2026-09-14 마감

단계1·2·3의이번범위를구현했다. 독립D2K는I0·text/PDFview·exactmanifest확인·samegrant재검토·source-only검증·typedDgrounding·동일의미reuse를지원한다. I2K가보고한오류는수동D2K성공후에도그대로남는다. 승인후생긴외부중복K는후보만보류하고새확인을요구하며독립후보는반영된다. 소비경로는명시적Data범위·I0K검색/답변·직접/전이D원문reader까지연결됐다.

I2K/K2K의명시적target개정은새Recordsubtype없이기존연산을사용한다. same-identity/materiality/grounding의독립판정과exacttargetdelivery를검사하고, 같은K/논리FP의새Revision·근거·Record·CAS·완전한직접영향목록·두outbox를원자적으로남긴다. 같은의미는이전Revision/origin유지, 빈후보/불확실/오래된target은보류다. D2K의의미개정은현재grant범위에없어거부한다.

검증은서로다른앱947개를단계별로완료했다(전체942실행→기존fixture오류1수정재검사+호환성5추가→native23skip전부보완). 첫전체명령은failed였고전체를다시돌린것으로기록하지않는다. 실제원본/이력137readonlychecks,Node28/ASAR19,실제hiddenElectronDOM읽기도pass다. 실제외부provider호출0,model다운로드0,userDBmigration0이다. 처음새격리DB에서0014/15를검증한뒤기존전용합성`palimpsest`fixture에만최신schema를적용했다. 실제codeDB13은exactprefixreadonly호환성으로그대로열었다.

최종기록은[REPORT](../output/t15-manual-d2k/REPORT.md),[집계](../output/t15-manual-d2k/verification-summary.json),[UI](../output/t15-manual-d2k/ui/REPORT.md)다. app이미지0.15/UI0.4를준비했고기존SQL0001–0013/ASAR0.3/source이력을보존했다. 문서검사전체의기존외부문서오류948개와중단한전체문서mutation검사는앱성공과분리했다.

다음구현우선순위는outbox를소비하는중단/재개가능전파scheduler,변경된Wiki재생성·독립검증,사용자Decision/W2K,온라인수집이다. exact영향frontier만저장한현재상태를수렴/자동확장전체완료로표시하지않는다. 특정실제자료D2K전송·운영DB쓰기upgrade는구체자료/DB범위요청이있을때진행한다.
