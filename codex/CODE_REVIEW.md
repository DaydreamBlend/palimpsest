# Palimpsest code review checklist

## 우선 판단

변경한 code/schema가 baseline의 어느 절과 **실제로 accepted된** P 항목을 구현하는지 확인합니다. 새 요구를 PROPOSED 문서에서 몰래 끌어와 production 결정을 바꾸지 않았는지 먼저 봅니다. 검토 결과는 추측이 아니라 코드 경로와 재현 가능한 사례를 포함합니다.

## P0 관점

cap 없는 전파를 max-depth/max-records/cost 성공 종료로 잘랐는지, empty ready queue를 quiescence로 오판하는지 확인합니다. dependency enumeration이 RAG top-K에 가려지는지, failed/pending work가 visited로 사라지는지도 봅니다.

no-material이 새 semantic Revision/branch를 만들지 않아야 합니다. 그러나 갱신된 support/dependency receipt나 blocked obligation release가 누락되어서는 안 됩니다. 실제 endpoint를 소비한 downstream의 영향 검증이 relation unchanged에 가려지지 않는지 확인합니다.

EffectiveEdgeRef에서 semantic edge revision, effective endpoint pair, applicability basis를 복원할 수 있어야 합니다. latest negative precedence, pending unknown, endpoint lifecycle, historical refs 불변을 확인합니다.

CAS가 target base만 검사하고 stale input/authority를 승인하지 않는지, canonical+Record+provenance+Candidate+outbox가 atomic인지, lease/redelivery/fan-in이 작업을 유실/중복시키는지 확인합니다.

Decision confirmation은 LLM 문자열이 아니라 actor/payload-bound evidence여야 합니다. 같은 승인 retry와 새 event를 구분하고 W2K의 LLM 호출은 0이어야 합니다.

## P1 관점

cross-Data I merge, historical FP 무조건 재사용, context-dependent hard rejection, predicate change에 같은 edge identity 사용, general semantic graph에 blanket DAG, source 수를 독립 evidence 수로 계산하는 오류를 검사합니다.

self-generated P/B 재수입이 독립 evidence로 세탁되는지, direct I를 accepted truth로 표시하는지, current 상태를 과거 decision rationale에 주입하는지 확인합니다.

파일/DB 복구, secret logging, unauthorized external transmission, path escape, untrusted text의 command 승격, user pause/cancel을 성공으로 표시하는 오류를 확인합니다.

## 테스트와 보고

AT IDs에 실제 assertions가 있는지 확인합니다. mock-only를 PostgreSQL race/e2e/live semantic correctness로 오인하지 않습니다. 실패를 숨기기 위해 test를 제거/skip하거나 thresholds를 임의 완화했는지 확인합니다.

각 finding에는 severity, 파일/함수, 반례, source/accepted decision/AT 근거, 최소 수정, 아직 실행하지 않은 검증을 적습니다. 읽기만 한 review를 테스트 실행이라고 보고하지 않습니다.


## CLI / MinerU / Naming — U01–U03

CLI가 T02부터 구현되어 있고 T11을 GUI 작업으로 해석하지 않았는가? frontend dependency 없이 help/import/query/review/decision/export/운영이 가능한가? JSON stdout/stderr와 비TTY confirmation, job 상태/exit code를 구분했는가?

PDF parser가 실제 MinerU adapter인가? 실패 때 다른 parser로 몰래 대체하지 않았는가? package/backend/model/config/output profile, page coverage, raw artifact와 원문 grounding을 보존했는가? parser success와 I validation을 구분하는가? 실제 parser 결과와 synthetic fixtures를 구분하는가? 환경 변수의 remote endpoint와 원문 외부 전송을 차단/승인하는가?

현재 모듈이 Artifact Store/artifact_store, Canonical Store/canonical_store, Compiler Runtime/compiler_runtime을 사용하는가? legacy alias migration 때문에 IDs/hashes/과거 refs를 재작성하지 않았는가? archived source/review의 과거 용어를 잘못 ‘고치지’ 않았는가? T13은 아직 deferred인가?

## 단계별 모듈 경계 — U06

D/I/K/W/P/B의 의미 규칙과 각 변환의 정책이 별도 모듈에 있는가? Domain에서 DB/parser/model/CLI 구현을 import하지 않는가? 각 모듈은 공개 refs/snapshot 계약을 통해 연결되고 Operation끼리 직접 재귀 호출하지 않는가? code dependency cycle 금지가 semantic graph DAG 강제로 바뀌지 않았는가?

공통 execution/Record/Candidate/propagation/commit을 복제하지 않고 재사용하는가? 모듈마다 commit해서 Decision W와 W2K 효과 등의 atomicity를 깨뜨리지 않는가? W2K의 LLM 호출이 0이며 W2P/P2B 모듈 이름에서 새 Compiler Record subtype을 만들지 않았는가?

실제 구현 모듈의 독립 unit/contract tests와 store/parser integration을 구분한다. 문서 정책 검사를 실제 import graph 또는 앱 모듈 실행 검사로 보고하지 않는다. 자세한 소유권은 [MODULE_BOUNDARIES](../docs/implementation/MODULE_BOUNDARIES.md)를 따른다.
