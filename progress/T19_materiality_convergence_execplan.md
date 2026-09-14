# 반복 자동 중단을 의미 변화 기준으로 바꾸기

2026-09-14. 사용자는 단순한 A→B→A 반복만으로 중단하지 말고, 의미 변화가 미미하면 전파를 멈추는 방식을 요청했다. 뒤이은 질문에서는 감쇠가 자동 보장되는지와 Contradict Edge의 역할을 물었다. 반복은 항상 수축하는 과정이 아니며 threshold·비단조 추론·LLM 변화가 있을 수 있지만, 반복 구조만으로 중단할 이유도 없다. 새 기본 정책은 반복을 advisory로 기록하고 실제 독립 materiality/equivalence 판정으로 semantic frontier를 결정한다.

## 구현 범위

새 run: `repeated_outcome=observe`, `materiality_policy=accepted-state-materiality-v1`을 동결한다. 반복 witness는 append하되 block/확인 요구로 전환하지 않는다. 이전 T17 run의 policy/진단/확인/SQL을 재작성하지 않는다. transport failure·lease·근거 불충분·미완료 의무·사용자의 pause/cancel은 보존한다.

현재 accepted target과 비교해 독립 Validator가 nonmaterial로 확인하면 기존 Revision을 유지하고 새 의미 branch를 만들지 않는다. 무시한 직전 candidate를 다음 base로 쓰지 않으며 작은 변화 누적이 accepted 기준을 벗어나면 다시 material일 수 있다. discovery K2K에서도 같은 의미는 current usable K의 reuse이며 새 FP만으로 신규 K를 만들지 않는다. 표현·숫자·embedding 거리에 공통 epsilon을 만들지 않는다. domain precision/허용 오차가 근거에 없으면 모델이 임의로 만들 수 없다. 작은 polarity/unit/scope/조건/절차 변경도 중요할 수 있다. 변경된 근거는 기존 accepted 주장을 여전히 지지해야 한다.

R02/R03에 따라 semantic branch 종료와 provenance maintenance 완료를 분리한다. 전제/current support만 바뀐 경우 exact downstream 재검증과 Wiki 갱신은 계속 필요하다. K2K 자기 전제 금지는 유지한다. 기존 N2E의 applicability true↔false는 Record disposition이 no_material_delta여도 실제 material effect이므로 dispatch가 빠지지 않도록 수정한다.

Contradict Edge는 상충하는 주장을 보존하는 관계이지 자동 수렴/선택 규칙이 아니다. 이번 범위는 전파 정책이며 현재 supports 중심 N2E를 새 predicate로 확장하거나 충돌 판정 정책을 추가하지 않는다.

## 소유권과 검사

Root: run policy/관찰 event/material effect dispatch·profile 결속·실제PG·release. contract agent: 새로운 frozen policy에만 붙는 K2K/N2E prompt guidance와 순수 검사. Wiki agent: nonmaterial/maintenance 경계 독립 검토. 기존 compiler/reuse/Record/atomic commit을 재사용하고 DB schema0016을 유지한다.

검사: material 반복이 있어도 dispatch진행/advisory한번, material 연속갱신뒤nonmaterial semantic정지, acceptedbase 누적비교, 다른FP의의미동일discoveryreuse, current-support maintenance/Wiki완료, Edgeflipmaterial/unchangednonmaterial, oldhaltpolicy호환·scope보존·unknown판정보류. 수치 tolerance는 synthetic Validator fixture의 설명일 뿐 production threshold가 아니다. 새 provider 없이 구조/실제PG 동작을 검증하고 실제 의미 품질 보장으로 확대하지 않는다.

## 완료 결과

앱0.18/schema0016에서 새 기본 정책을 적용했다. 반복은semantic_return_observed로 한 번 남기고 dispatch한다. 독립accepted-base materiality/reuse가 semantic frontier를 결정하고 실제support maintenance는 계속한다. 이미 current인 origin derivation의불필요한재검증을줄였으며, disposition이no_material_delta인Edge applicability flip도실제material effect으로분류한다. 신규propagation K2K/N2E요청에만guidance를붙이고Coreprofile에정책을결속했다. Generic K2K export를request wrapper에맞춰실제receipt검증과일치시켰다.

실제PG17개(새materiality7/기존전파5/과거halt호환5)통과. 순수지침/개정/K2K/N2E request34개통과. 패키지회귀44개개별검사는통과했으나 기존K2Kclass의DB이름guard가달라setUpClass오류가1개났고, 요구한별도합성palimpsest DB에서9개를실행해통과했다. 처음없는test_n2e명령은test_edge_requests로바로잡아로그를보존했다. 사용자code이력137/이전T16실제Terra/Wiki18도read-only통과했다.

새provider0/migration0/userDB쓰기0. 이전unbound/legacy prompt/schema4쌍의SHA가동일하다. 수치예시는합성Validator판정에만0.01기준을둔흐름검사이며실제LLM수렴성능이나production tolerance설정이아니다. 모순이없어도규칙n→n+1처럼새결과가계속생길수있으며Contradict Edge가수렴보장을대신하지않는다고설명했다. 실제N2E는supports이며Contradict추가는이번에하지않았다.

이미지는palimpsest-propagation:0.18.0/sha256:82d81abe2b6bcb6d431e8fb9e53293fcc12cec5197ee830bd019d319c1424cb5. 앱/SQL99파일·test104파일의workspace일치검사를통과했다. 반복관찰후확인없이완료한실제PG예시는output/t19-materiality-convergence/observed-return.json. [최종결과](../output/t19-materiality-convergence/REPORT.md). 현재정정범위는완료하며T18dependency paging과새관계유형은별도다.

최종중복제거집계97개관련검사모두pass/미해결실패0. 전체앱재실행은아니다. 첫fixture DB설정오류와test명령오타를보존했다. SQL16개SHA동일, bundle948기존오류/이번문서범위0. 사용자질문의수렴보장과Contradict역할을설명했으며수렴성능실제LLM시험으로확대하지않는다.
