# 중단·재개 전파 worker와 Wiki refresh

2026-09-14. 사용자는 저장된 변경 영향/outbox를 실제로 처리하는 중단·재개 가능한 전파 worker와 그 결과의 Wiki 재생성·독립 검증을 명시 요청했다. T07의 현재 node-only K2K와 R01–R05 승인 규칙을 구현한다. P 전체·새 public K revalidation subtype·K 폐기 정책·정식 W/P나 인터넷 수집을 승인한 것으로 확대하지 않는다.

## 완료 동작

선택한 root Record와 허용 source/Wiki 범위를 고정하여 실행을 준비한다. 불변 outbox는 유지하고 별도 task/claim/event/causal binding으로 소비한다. 필수 현재 consumer는 정확한 의존 관계를 빠짐없이 재검증하고, discovery는 명시한 두 K 문맥 단위로 실행한다. timeout·pause·cancel·실패·lease 소실은 미완료로 보존한다. semantic 결과·지식 판정·workflow 완료를 구분한다.

동일 의미 재검증은 최초 origin/Revision을 유지하면서 active support와 실제 소비 support refs를 append한다. 다음 support 변경도 downstream 의무로 인식한다. 기존 관계는 exact semantic revision/current endpoint pair에 대해 applicable/not_applicable/unresolved를 독립 판정한다. 생략/zero-output을 필수 관계 검증 성공으로 바꾸지 않는다. 불명확한 node 폐기·invalidated lifecycle은 추가하지 않고 needs_human에 남긴다.

원래 root watermark보다 뒤에 commit된 causal child도 포함한다. knowledge_state fence에서 미등록 outbox·미열거 영향·pending/leased/retry/blocked와 child 완료를 검사한 뒤에만 완료 receipt를 낸다. 깊이/전체개수/비용 cap은 성공 조건이 아니다. 한 번의 worker 작업량·context·lease는 운영 경계이며 남은 일은 partial이다.

Wiki는 현재 선택된 page/import만 다시 만들고 과거 snapshot은 유지한다. 기존 source-only full-I Page Generator/독립 Validator와 별도 DB sync CAS를 재사용한다. K2K 새 결론을 source-only 문장으로 섞지 않고 지식 탐색/기원 표시로 구분한다. 저장된 query 답변을 자동 재작성하지 않는다. D2I/D2K 자동 호출은 없다.

## 소유권·검증

Root: propagation Runtime/CLI/hostworker, 공유동작조율, 격리DB·통합·실제provider 검증. schema agent: additive0016와migration registry. revalidation agent: 기존n2e/k2k targetedmode/current support/provenance와관련공유Runtime hooks. Wiki agent: 독립wiki_refresh orchestration/tests. 각공유파일은협의한부분만수정한다. Python/Docker/기존OAuthTerraMedium/BGE/MinerU설정은유지한다. ponytail원칙에따라기존compiler·commit·store를재사용하고새broker/framework는추가하지않는다.

읽은계약: tasks/T07, docs/contracts/03_propagation_completion, R01–R05, MODULE_BOUNDARIES, CLI_CONTRACT, KNOWLEDGE_REVISION, K2K_RUNTIME, CODE_REVIEW. 실제schema15/기존k_outbox는pending-only불변이며, 이전지원만보는원기원stale판정과positive-only N2E적용성경로가후속의핵심수정이다.

AT01/02/03/04/05/16/31/32/34/60/79/85/86의현재구현범위에대한합성/실제PG검사를작성한다. chain/fanout/diamond, ACK전crash, 오래된lease결과, emptyready중미등록outbox·human, pause/resume, sameRevision support변경과negative관계,Wiki검증보류/동시편집/DBsync실패·ACK복구를구분한다.100001fanout등실행하지않은스트레스규모를작은fixture결과로통과처리하지않는다.

## 현재

시작 baseline은0.15/schema0015/이전947개검사·원본137이력이다. additive0016을 `palimpsest_propagation_checks`에 먼저 설치·검증한 뒤 기존 합성 회귀 DB `palimpsest`에만 추가했다. 실제 코드/논문 DB는 변경하지 않았다. 앱0.16 이미지에서 CLI/host controller, current support revalidation, exact edge applicability, Wiki refresh를 구현했다.

실제 모델 시험은 직접 작성한 비공개 정보 없는1117-byte fictional R1 문서를 도구로 등록해5 I를 만들고, 초기 reported3→corrected4·상한5의 저장된 root 변경을 처리했다. 초기10개 synthetic seed receipt는 모델 품질 증거가 아니다. 이후 실제 Terra Medium8회(노드2, 관계4, Wiki2)로7개task가 모두done, run이completed가 됐다. independent readonly verifier18/18이 원문/I/기원/Revision/causal closure/old Wiki 보존과 현재 전제·전체I전달·새Wiki DB import를 확인했다. 세부 raw결과는 `output/t16-propagation/live/verification.json`에 있다.

38개 초기 pure/container 검사,11개 실제PG revalidation/worker 검사,34개 queue/Wiki/compatibility 검사가 각각 통과했다. 이전 첫PG검사의 fixture 초기화 오류와12-chain intermediate edge-pair 오류는 고쳤으며 실패로그도보존했다. 현재 입력과비교전용 stale target을 분리한 truthful reused/novel=false 검증이 통과한다. 12단계 chain과두부모fanin, discovery빈결과에도 exact obligations완료, commit후ACK전중단, oldlease응답거절, validator보류시Wiki미게시를 검증했다.

마지막 검토에서는3회연속transport실패를needs_human으로 남기는 운영장치, schema15의정확한readonly호환성, cachedWiki완료를 실제import로검증하는장치를 추가했다. stage/decide와Wiki sync는 쓰기·deferred constraint 후 최종commit직전 lease를 확인한다. 실제Tx에서 lease를1초로 만들고1.1초지연해 candidate/modelreceipt/K/current-support/outbox/impact/stateversion 전체rollback을검증했다. Wiki완료확인에서 발견한 전송용replayed필드 차이는 해당필드만분리해 실제PG 재검사를통과했다.

최종: 전체1013개 실행989pass/23native skip/완료cache오류1. 오류수정·신규7개·native누락23개를후속검증한결과 **중복을제외한1020개모두pass**, 미해결실패0. 별도history137/read-only actual-demo18/Windowscontroller14통과. 단일명령all-green전체재실행이아닌합산검증임을 `output/t16-propagation/verification-summary.json`에명시했다. 마지막이미지49개집중검사와앱/SQL98·test100파일workspace일치검증도pass. actual-demo8회이미지와최종fence/cache이미지ID를구분했고최종코드에서도이전actual-result18/18및completed replay성공. 새이미지는 `palimpsest-propagation:0.16.0`/sha256:df179bdae69720b14a9f8449ca1db0a6e50932a97a96666aeedbb06b607db7f9. bundle전체948기존오류/이번문서범위0이며app검사와구분한다. [최종보고](../output/t16-propagation/REPORT.md).

현재 요청의worker+실제Wiki검증범위를완료했다. 전역 의미 oscillation A→B→A 자동탐지,128단계/100001fanout규모,EffectiveEdge전제K2K는이번검증에포함하지않으며전체T07미완료로유지한다. 사용자코드/논문DB의migration·자동갱신배포,GUI제어·W/P/Decision·인터넷수집도별도범위다.
