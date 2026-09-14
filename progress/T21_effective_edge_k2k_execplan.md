# EffectiveEdge를 전제로 사용하는 K2K

2026-09-14. 사용자는 N2E 후속 작업을 요청했다. 다음 수직 구현은 실제 관계를 exact K2K premise로 전달·검증·저장하고, 관계/endpoint/support가 바뀌면 해당 결론을 재검증하는 것이다. R01/R02/R03/R05, T07 및 current K2K/N2E 계약을 적용한다. source-only I2K, application LLM 없는 D2I, 명시적 사용자 요청에만 가능한 D2K, 기존 의미 반복 advisory 정책은 유지한다.

## 완료 동작과 최소 계약

- 새 `knowledge-inference-effective-v1` / `k2k-effective-input-v1`을 추가한다. 과거 Node-only 요청·schema·FP·receipt와0019까지의 SQL은 보존한다.
- Edge 하나를 선택할 수 있으며 실제 current endpoint Node 두 개의 내용을 함께 전달한다. predicate만 전달하는 별도 relation-only mode는 만들지 않는다. 비교 catalog는 authoritative premise가 아니다.
- R02에 따라 각 후보의 Node 목록과 Edge 목록은 전달한 authoritative bundle 전체와 정확히 일치한다. model-owned attribution으로 실제 의존성을 줄이지 않는다. Node depth/source/version/자기전제 guard는 실제 endpoint가 Node premise에도 포함되므로 기존 구현을 재사용한다.
- Input Edge는 logical ID·predicate·qualifiers·original pair·기존6필드 EffectiveEdgeRef·endpoint support signatures를 동결한다. execution과 derivation/current-support Record를 typed FK로 연결한다. Model은 premise_edge_revision_ids만 선택 형식으로 반환하며 exact refs/IDs/FP는 코드가 결속한다.
- Global knowledge-state를 포함한 relation_read_state_token은 delivery/read-set fence 증거다. 이를 영구 currentness와 비교해 결과의 자기 commit이 자신을 stale로 만들지 않게 한다. 장기 currentness는 exact semantic pointer/pair/basis/fence/support를 비교한다. current Node ancestry를 한 번 순회하며 Edge 로컬 상태를 검사하여 Node↔Edge SQL 함수 재귀를 피한다.
- 생성·독립 검증 receipt에 delivered_effective_edge_refs와 delivered_effective_input_sha256, 전체 delivered_knowledge_revision_ids를 결속한다. 새 결론은 Proposition/is_inferred=true이며 정확한 원래 Node/Edge 근거·가정·한계를 보존한다.
- pending 필수 Edge는 consumer를 대기시키고 confirmed false는 근거 상실을 표시한다. 없는 긍정 근거를 만들거나 필수 Edge를 조용히 버리지 않는다. 더는 유효하지 않은 Edge를 사용하던 결론의 자동 삭제·일반 lifecycle 변경·자동 대체 근거 탐색은 이 구현에 포함하지 않는다. 명시적 negative로 인해 필요한 검토가 남으면 성공 완료하지 않는다.
- true→true의 새 exact basis도 실제 consumer가 있으면 기존 outbox로 nonmaterial 유지보수를 전달한다. 새로운 semantic discovery와 구분하고 이미 생긴 endpoint-value 의무를 지우지 않는다. false→false의 중복 material outbox는 만들지 않는다.

## 구현 소유권과 검사

Root: Runtime prepare/stage/derive/commit·입력/receipt·CLI·target refresh·worker dispatch·격리PG·release. contract agent: k2k_effective.py와 k2k.py 조건 분기·순수 tests. SQL agent: 추가0020과 migration registry, 설치 전 전체 검토. consumer agent: knowledge_provenance·검색·query·Desktop의 origin/current Edge 근거와 currentness.

공통 KnowledgeRuntime/Record/current_support/outbox/전파 queue를 재사용한다. 두 typed Edge input/derivation tables 이외의 전체 그래프 복제나 새 broker를 만들지 않는다. 단계 중 각 변경의 public 소유권은 기존 K2K이며 새 operation/Record subtype을 만들지 않는다.

순서: (1) pure/schema/typed rows, (2) Runtime·provenance·현재 상태, (3) material/maintenance 역방향 의무와 pending release, (4) 실제 PG 생성·재사용·stale/basis/negative/lease/rollback·source/version 검사, (5) 필요 시 직접 작성한 가상 자료의 실제 Terra 생성·독립 검증, (6) 기존 이력·코드/package bytes 검증 및 문서화. 사용자 원문 전송·사용자 DB migration·D2I 재실행은 하지 않는다. 새로운 DB는 template0에서 root가 준비하며 설치된 SQL을 뒤늦게 덮어쓰지 않는다.

AT09의 실제 K2K EffectiveEdgeRef 소비/정확 replay, AT12의 endpoint 값 직접 의무, AT16의 pending 대기·해제와 AT13의 nonmaterial maintenance를 중점 검증한다. W/P 소비자·Edge embeddings·일반 lifecycle·대규모 paging과 전체 T07 완료는 별도 범위다. 실제 명령·실패·검증 결과를 아래에 누적한다.

## 완료 결과

새 schema0020을 독립 검토 후 두 신규 격리DB(checks/demo)에 설치했다. 초기 draft의 positive basis 유지보수, 빈 discovery 종료, 재검토 target Edge 결속을 보완한 뒤 설치했다. 이전SQL0001–0019는 수정하지 않았다. Runtime7/SQL5/worker3 실제PG 검사 모두통과했고, 설치된0.20이미지의관련138검사를32.930초에통과했다. 별도 중간consumer검사113개중108pass/5기존skip은최종138개실행과구분한다.

실제Terra2회가가상의K3+qualifies1을사용해조건부상한2,048항목이라는inferredK1을생성·독립승인했다. 이는Palimpsest설정이나실제32GPT세션이아니며,그구분을사용자에게설명했다. 원본/typedrefs/정확전달/독립성/현재유효성11read-only확인pass. sourceK와N2E는표시된syntheticseeds이며새사용자자료전송0이다.

앱0.20/schema0020이미지는palimpsest-effective-k2k:0.20.0/sha256:73a5d393571a1422edef213d6c76681f9f019dc9e187890d944e0cf79ae3013e. 앱·SQL108/test115파일및설치package의workspace일치를확인했다. [결과](../output/t21-effective-k2k/REPORT.md), [최종검사](../output/t21-effective-k2k/package-final.json).

사용자는추가로단일Electron앱과RealmR을요청했고,RealmI2K정책은기본분리·명시적교차허용으로답했다. T22/REALM_SCOPE에기록했다. 현재K2K수직구현은완료하며,통합Electron+Realm후속작업은아직미완료다. 사용자가직접조작하므로기존Electron창은열기만했고자동클릭/조작하지않았다.
