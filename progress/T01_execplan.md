# T01 실행 계획 — 기본 모델·MinerU 정책·단계별 모듈 경계

시작일: 2026-09-09. 상태: in_progress. 사용자 요청에 따른 기본 모델/버전 정책 및 단계별 모듈 경계를 반영하며 T01의 나머지 계약 동결은 미완료다.

## 목표와 승인 범위

사용자 원문: “Embedding/Reranker는 BGE-M3을 기본으로 쓰고, MinerU는 최신 버전을 쓰도록 하자.”

- U04로 BGE-M3 검색 모델 기본값, U05로 MinerU 최신 안정 릴리스 선택 정책을 기록한다. 최신 안정판은 prerelease 요청이 없는 이번 문장의 실행 해석이다.
- U01–U03의 기존 승인 원문을 보존하고 새 결정에는 이번 승인 근거를 별도로 연결한다. P12 전체나 다른 P 항목을 승인으로 바꾸지 않는다.
- 임베딩 식별자는 공식 `BAAI/bge-m3`, 기본 dense dimension은 공식 모델 카드의 1024다. 기존 production schema나 DB가 있다는 뜻이 아니다.
- 전용 `BAAI/bge-reranker-v2-m3`와 bge-m3 자체 multi-vector scoring은 다른 구현이므로 정확한 Reranker 선택을 비동기 질문했다. 사용자가 “bge-m3 자체의 다중 벡터 점수로 재순위화”라고 답했다. 동일 `BAAI/bge-m3`의 ColBERT late-interaction 점수를 선택하고 별도 reranker 모델은 채택하지 않는다.
- 후속 요청으로 Qwen3-Embedding/Reranker 4B·8B 교체 가능성을 반영한다. U04에 추가 승인 근거와 독립 profile/adapter 경계, embedding 공간 분리·필요한 파생 projection 재생성·canonical history 보존을 기록한다. 후보 모델 구현/설치는 하지 않는다.
- 설치/모델 다운로드/원문 전송/실제 추론/DB migration은 이번 기본값 문서 반영에 포함되지 않는다.

## 근거와 현재 환경

T00 완료 inventory를 이어받는다. production code/manifest/DB 없음. 문서 검증은 기존 번들 Python 3.12.14로 실행한다. Git 미초기화이므로 이번 시작 시 110개 파일의 SHA-256을 세션에 보존했다.

root/docs AGENTS, PLANS, INDEX, USER_OVERRIDES/JSON, DECISION_REGISTER/JSON, T01, CODE_REVIEW, 관련 canonical §0–3/§24/§29–30, current_map, ENVIRONMENT, CLI_CONTRACT, MINERU_ADAPTER/REFERENCES, 도구 policy checks와 테스트 범위를 확인한다. 나머지 P 계약 구현은 이번 범위 밖이다.

공식 근거: BAAI bge-m3/bge-reranker-v2-m3 모델 카드, PyPI MinerU release metadata. 현재 최신 안정판 관찰은 3.4.5(2026-08-14), 4.0.0a6는 prerelease다. 설치 후 version/profile 검증은 별도이며 T00의 tag version.py 불일치 관찰을 보존한다.

## 변경과 담당

root가 승인 JSON/문서, 관련 실행 계약, current canonical snapshot/map, policy validator와 필요한 mutation tests를 함께 소유한다. 보조 agent는 승인 근거·snapshot 일관성을 읽기 전용으로 검토한다.

source archive, A1–A40, P01–P12 상태, T00 당시 관찰·검증 기록은 보존한다. current canonical은 관련 줄을 변경한 slices/full/map을 동기화해 새 edition으로 갱신한다. 후속 task 상태를 임의 완료하지 않는다.

## 순서와 검증

1. [x] 현재 문서/도구 및 공식 모델·release 자료 조사.
2. [x] 정확한 Reranker 역할 확인, 새 승인 근거와 기본값 기록.
3. [x] 관련 문서와 synchronized current snapshot/map 갱신. 교체 profile 계약 작성.
4. [x] 승인 누락·모델/버전/교체 정책 drift·map 누락을 확인할 mutation tests 추가.
5. [x] 문서 validator와 도구 unit tests 실행, SHA 변경 범위·archive 보존 검사. 아래 최종 결과 기록.

검증 명령은 T00과 동일하다. process-local `PYTHONUTF8=1`, interpreter `C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`로 `-B tools/validate_bundle.py --json`과 `-B -m unittest discover -s tools -p 'test_*.py' -v`를 실행한다.

AT64는 확인된 사실과 미실행을 구분해 문서 검토, AT88/AT103은 기존 naming/GUI gate 검사를 유지한다. AT63(P11 전체 정합성)과 실제 retrieval/MinerU runtime acceptance는 이번에 완료로 표시하지 않는다. 실패·재검증 결과를 아래 기록한다.

## 복구와 남은 작업

이번 변경 파일만 이전 내용으로 복원하면 되며 DB/runtime rollback은 해당 없다. T01의 언어/CLI/DB-test, 나머지 schema/authority 계약은 여전히 미정이다. P10/P12 전체 승인이나 T02 착수 완료를 주장하지 않는다.

## 실행 기록

공식 자료 조회와 읽기 전용 검토 완료. user_overrides는 기존 3개 근거를 보존하고 U04/U05 및 추가 답변 근거를 기록했다. full canonical은 2360줄을 유지하며 변경 slice 2개/full/map을 동기화했다. current-map effective override 누락도 검사하도록 보완했다.

기존 도구 test 26개에 정책 mutation test 5개를 추가했다. 1024 차원/embedding 모델, BGE-M3 자체 multi-vector reranking, 새 승인 근거, 최신 안정판 및 exact profile, override map 일치, 교체 경계와 history 보존의 drift를 검사한다. 이는 runtime 모델 테스트가 아니다.

첫 실행: validator exit 0/errors 0, unit/mutation test 31개 pass(exit 0, 13.636초). 읽기 전용 리뷰에서 future_candidates를 active/implemented로 바꾸는 drift가 검출되지 않는 점을 찾아 해당 guard와 같은 test method의 subcase 2개를 보완했다. 모델 지원을 새로 구현한 것은 아니다.

최종 재검증: validator exit 0/errors 0(Markdown 83개, current 2360줄/13 slices, accepted overrides 5개), unit/mutation test **31개 모두 pass**, exit 0, 14.461초. 최종 model 선택 JSON과 T00 completed/T01 in_progress/T02 planned/T13 deferred 상태도 read-only로 확인했다. 실행 명령:

```powershell
$env:PYTHONUTF8 = '1'
& 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B tools/validate_bundle.py --json
& 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -m unittest discover -s tools -p 'test_*.py' -v
```

## 변경 범위와 인계

기존 110개 파일 중 21개 변경, 새 파일 2개, 삭제 없음. 나머지 89개는 시작 SHA-256과 일치한다. docs/source 및 baseline_parts, 원본 A1–A40/traceability, docs/decisions/decisions.json, T00 실행 기록·inventory·초기 verification/manifest는 보존했다.

- 승인/안내: AGENTS.md, README.md, docs/AGENTS.md, docs/INDEX.md, docs/decisions/USER_OVERRIDES.md, user_overrides.json, DECISION_REGISTER.md, docs/implementation/ENVIRONMENT.md.
- current snapshot: docs/canonical/00_foundation.md, 12_open_implementation.md, PALIMPSEST_CANONICAL_MODEL.md, current_map.json. 줄 수·범위는 유지하고 edition/hash/effective overrides를 함께 갱신했다.
- interface: docs/interfaces/MINERU_ADAPTER.md, 신규 docs/interfaces/RETRIEVAL_PROFILE.md.
- 정책 검증: tools/policy_checks.py, tools/test_validate_bundle.py, tests/specs/ACCEPTANCE.md, acceptance_catalog.json. AT64에 U04/U05를 연결했으며 105개 spec_only 유지.
- 진행: progress/STATUS.md, 신규 progress/T01_execplan.md, tasks/T01.md, tasks/README.md, tasks/task_graph.json.

이번 사용자 선택과 교체 가능성 요구 반영은 완료했다. T01 전체는 in_progress로 남는다. 언어/CLI/DB-test/runtime profile, 나머지 P 계약의 미정 항목은 아직 완료되지 않았다. AT63(P11)과 실제 앱/retrieval/MinerU/DB/e2e/live semantic 검증은 미실행이다. 설치·다운로드·외부 원문 전송 없음.

## 추가 요청 — U06 단계별 모듈화

사용자 원문: “각 단계를 모듈식으로 작성해줄래? 그러니까, D I K W P B와 각 단계를 잇는 D2I, I2K 등 역시 모듈화해서, 향후 유지보수가 쉽도록 해줘.”

이번 범위는 D/I/K/W/P/B domain과 D2I/I2K/N2E/K2K/KQ2W/W2K, W2P/P2B의 코드 책임·공개 경계·의존성·테스트 소유권이다. T01의 언어/CLI/DB 미정값을 임의 채택해 빈 앱 패키지를 만들지 않는다. U06으로 승인 근거와 실제 코드 구현 전의 module plan을 기록한다.

시작 시 112개 파일의 SHA-256을 세션에 보존했다. root가 MODULE_BOUNDARIES, 승인 JSON/문서, current canonical full/slices/map, 관련 task/review 안내 및 policy tests를 소유한다. 보조 agent는 W2P/P2B의 지위, W2K 권위, shared transaction과 graph/code 의존성 혼동을 읽기 전용 검토한다.

읽은 범위: root/docs AGENTS, PLANS, STATUS, T01, INDEX, USER_OVERRIDES/JSON, DECISION_REGISTER, MODULE_BOUNDARIES, canonical §0–3/§8–10/§18–24/§29–30의 관련 규칙, CLI_CONTRACT, 계약 08(미승인 상태 유지), CODE_REVIEW. 실제 앱 코드는 여전히 없고 기존 도구만 있다.

작업 순서:

1. [x] 6 domain과 각 변환의 입력·출력·책임/의존성·검증 경계 작성.
2. [x] U06 승인 기록 및 current snapshot/map, 시작 지침/task 안내 동기화.
3. [x] 모듈 누락·결정론적 W2K·공통 commit 경계/승인 근거 drift를 검증하는 도구 테스트 추가.
4. [x] 기존 validator/unit tests 실행 및 원본 보존·변경 범위 검토.

복구는 이번 변경 파일의 내용 복원으로 한정한다. production dependencies/DB/runtime 변경 없음. 실제 import 의존성 및 개별 Operation 동작 검사는 해당 모듈을 구현할 T02 이후에 수행한다. AT64/AT88/AT103의 문서 검토와 실제 앱 AT 미실행을 구분하고 T01 전체는 미완료 상태를 유지한다.

### U06 검증 결과와 검토

앞 절과 동일한 절대 interpreter/명령으로 validator exit 0/errors 0, unit/mutation **33개 pass**, exit 0(20.645초)를 확인했다. 신규 test_stage_module_coverage/test_stage_module_boundaries와 U06 승인 근거 누락 subcase를 추가했다. 현재 canonical은 2360줄/13 slices, 승인된 override 6개이며 baseline 2331줄/13 slices를 보존한다.

읽기 전용 검토에서 I2K 입력 설명을 usable exact I 1개 이상과 관련 K 비교 문맥으로 분리하라는 지적을 반영했다. 새 public Operation/Record 추가, W2K LLM 호출, 모듈별 commit 분할, P 일괄 승인은 없다는 검토 결과를 받았다. 최종 문구 변경 뒤 문서 validator를 다시 실행해 exit 0/errors 0을 확인했다.

시작 112개 파일 중 24개 변경, 신규/삭제 0개, 88개 byte-identical. source/baseline archive, P01–P12 JSON, 이전 T00 inventory/실행 기록, retrieval profile 및 MinerU adapter의 기존 동작 계약과 초기 verification/manifest는 보존했다. 이번 U06 설계·지침 반영은 완료했으나 실제 앱 모듈·import graph·DB/MinerU/LLM 동작은 검증하지 않았다. T01 나머지 P12/F26 실행 profile 및 P10/F22/F23 등의 미정 계약은 후속 작업으로 남는다.

이번 변경 파일:

- AGENTS.md, README.md, codex/CODE_REVIEW.md, docs/AGENTS.md, docs/INDEX.md.
- docs/decisions/USER_OVERRIDES.md, user_overrides.json, DECISION_REGISTER.md.
- docs/implementation/MODULE_BOUNDARIES.md, ENVIRONMENT.md, ROADMAP.md.
- docs/canonical/00_foundation.md, 12_open_implementation.md, PALIMPSEST_CANONICAL_MODEL.md, current_map.json.
- tools/policy_checks.py, tools/test_validate_bundle.py, tests/specs/ACCEPTANCE.md, acceptance_catalog.json.
- progress/T01_execplan.md, progress/STATUS.md, tasks/T01.md, tasks/README.md, tasks/task_graph.json.

## 추가 요청 — U07 K2W 명칭 간소화

사용자 원문: “kq2w는 k2w로 이름을 간소화하자. 다른 문서에도 반영해줘.”

현재 Operation/모듈 이름을 K2W/k2w로 통일한다. KGraph + Query + Context 입력과 Wisdom 생성 의미는 유지한다. root가 현재 문서·승인 JSON·task/acceptance metadata·policy check 및 canonical full/slices/map을 동기화하고 보조 agent가 누락과 원본 보존을 읽기 전용 검토한다. 시작 시 112개 파일 SHA-256을 보존했다.

root/docs AGENTS, INDEX, USER_OVERRIDES, DECISION_REGISTER, T01/T08, PLANS, CODE_REVIEW, MODULE_BOUNDARIES와 관련 canonical·acceptance·validator를 확인했다. docs/source와 baseline_parts, 원본 invariant_traceability.json/TRACEABILITY 인용, 과거 실행 기록은 유지한다. TRACEABILITY에는 현재 이름 안내만 덧붙인다. production code/DB가 없어 migration은 필요하지 않다. 복구 범위는 이번 문서/도구 변경 파일이며 새 앱 모듈은 생성하지 않는다.

1. [x] U07 승인 근거와 현재 문서·모듈 식별자·task/acceptance 명칭 반영.
2. [x] canonical full/13 slices/current_map 동기화 및 기존 정책 검증 규칙 갱신.
3. [x] 기존 문서 validator와 33개 unit/mutation tests 실행, 잔존 이름과 보존 파일 SHA 확인.

검증 범위는 AT88 현재 명칭의 문서 정책과 기존 번들 무결성이다. AT58/AT78/AT80은 명칭만 갱신하며 앱 acceptance 105개 spec_only를 유지한다. T01 나머지 미정 P 계약, 실제 앱/DB/MinerU/e2e/live semantic 검증은 이번 명칭 변경 범위 밖이다. 초기 읽기에서 존재하지 않는 tools/test_policy_checks.py 경로 조회가 exit 1로 실패하여 실제 파일 tools/test_validate_bundle.py를 확인했다. 변경이나 테스트 실패는 아니었다.

### U07 검증 결과와 변경 범위

다음 명령을 process-local PYTHONUTF8=1로 실행했다.

```powershell
$env:PYTHONUTF8 = '1'
& 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B tools/validate_bundle.py --json
& 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -m unittest discover -s tools -p 'test_*.py' -v
```

validator exit 0/errors 0, 기존 unit/mutation **33개 pass**, exit 0(20.922초). 새 테스트/의존성/앱 파일은 추가하지 않았다. 현재 canonical 2360줄/13 slices와 승인 7개를 검증했다. current full에서 이름과 개정 안내만 역치환한 bytes의 SHA-256이 변경 전 3e810849f3cc072eb783249b0bcd70bca5e83346f01aea487cc263a0a997b389와 정확히 일치한다. 입력/출력·overlay·direct-I·자동 실행 규칙의 변경은 없다.

읽기 전용 리뷰에서 현재 이름 누락이나 의미 변경은 발견되지 않았다. 중간 diff 확인에서 AT89의 Markdown 의존성에 함께 붙었던 U07을 제거하여 기존 JSON과 동일한 U03 범위를 유지했다. AT88만 명칭 요구에 U07을 연결했다. 잔존 이전 이름은 archive/원본 invariant 인용, 과거 기록, 승인 원문·변경 매핑, 금지 검사 문자열이다.

시작 112개 파일 중 26개 변경, 신규/삭제 0개, 86개 byte-identical. docs/source 및 baseline_parts, invariant_traceability.json, docs/review, decisions.json의 P01–P12, T00 기록·inventory, retrieval/MinerU profile, 초기 verification/manifest의 SHA-256은 보존했다. 변경 파일:

- 안내: AGENTS.md, README.md, docs/AGENTS.md, docs/INDEX.md.
- 승인/계약: docs/decisions/USER_OVERRIDES.md, user_overrides.json, DECISION_REGISTER.md, docs/implementation/MODULE_BOUNDARIES.md, docs/contracts/02_effective_relations_dependencies.md.
- current snapshot: docs/canonical/00_foundation.md, 08_wisdom_decisions.md, 10_relational_vocabulary.md, 11_invariants_decisions.md, 12_open_implementation.md, PALIMPSEST_CANONICAL_MODEL.md, current_map.json.
- task/명세/정책: tasks/T01.md, T08.md, README.md, task_graph.json, tests/specs/TRACEABILITY.md, ACCEPTANCE.md, acceptance_catalog.json, tools/policy_checks.py.
- 진행: progress/T01_execplan.md, progress/STATUS.md.

U07 명칭 반영은 완료했다. T01은 in_progress, T02–T12 planned, T13 deferred이며 모든 앱 acceptance 105개는 spec_only다. 이번 요청으로 새 blocked decision은 없다. 기존 P12/F26 실행 profile 및 P10/F22/F23 등의 미정 사항은 유지하며 실제 앱/DB/MinerU/e2e/live semantic evaluation은 미실행이다.

## 추가 요청 — 전체 구조 설계 검토

사용자 요청: “전체 구조 설계에서 혹시 이상한 부분 있는지 확인해줘.” 현재 canonical/U01–U07과 모듈·interface·작업 계약을 대조해 구현 전에 해소할 구조 충돌 및 누락을 검토한다. 기존 F01–F26/P01–P12와 새 발견을 구분하고, 구체적 반례·영향·최소 보완·관련 AT를 기록한다. 설계 승인이나 수정 요청으로 확대하지 않는다.

root는 모듈/저장/검색·모델 교체/전체 task 경계를 검토하고, 읽기 전용 보조 검토를 K·관계·전파·transaction, W·Decision·publication, D2I·I·validation으로 나눈다. source/review 원본과 현재 canonical/결정 상태는 수정하지 않는다. 결과는 progress/T01_architecture_review.md에 작성하고 이 실행 기록과 STATUS의 링크만 갱신한다. 복구는 새 검토 문서와 진행 기록의 이번 추가분을 되돌리는 것으로 한정한다.

1. [x] 현재 설계·기존 findings·미정 계약의 상호 대조와 근거 줄 확인.
2. [x] 독립 검토를 합쳐 실제 충돌/미해결 사항과 과도하지 않은 권고 작성.
3. [x] 문서 validator 실행, 결과·변경 범위·미실행 한계 기록.

시작 시 112개 파일의 SHA-256을 보존했다. 초기 findings JSON을 출력한 Python 명령은 Windows cp949 UnicodeEncodeError로 exit 1이었다. process-local PYTHONUTF8=1로 재실행해 exit 0을 확인했다. 이는 읽기용 출력 오류이며 문서 손상이나 앱 실행 실패가 아니다. 기존 33개 도구 테스트는 이번에 코드가 바뀌지 않으므로 재작성하지 않는다. 의미·동시성·실제 DB/모델 테스트가 아니라 설계 분석임을 구분한다.

### 전체 구조 검토 결과

progress/T01_architecture_review.md에 R01–R09를 기록했다. 7개는 기존 F의 현재판 재확인·통합이며, R07은 기존 F11/F19에서 구체화되지 않은 병렬 Decision 대체 반례, R08은 rejected similarity/terminal cleanup 사이의 새 불일치다. read-only agent 3개와 root가 근거 및 기존 제안 계약을 대조했다. T03에 AT35가 빠졌다는 초기 검토 후보는 T05가 해당 barrier와 시나리오를 소유함을 확인하여 finding에서 제외했다.

실행 명령:

```powershell
$env:PYTHONUTF8 = '1'
& 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B tools/validate_bundle.py --json
```

결과: exit 0/status passed/errors 0. Markdown 84개, current canonical 2360줄/13 slices, 원본 2331줄/13 slices, 승인 U 7개, P 제안 12개, acceptance 105개를 검증했다. review markdown의 링크·표·문서 무결성 검사이며 설계의 의미 정확성이나 동시성 증명이 아니다. 도구 코드/테스트는 변경이 없어 직전 U07에서 33개 pass한 suite를 이번에는 재실행하지 않았다.

SHA 비교: 기존 112개 중 progress/T01_execplan.md와 progress/STATUS.md만 변경, progress/T01_architecture_review.md 1개 추가, 삭제 0개. 나머지 110개는 byte-identical이며 current/source canonical, 승인/제안 JSON, 기존 review, 도구 코드, task/acceptance metadata를 포함한다. 원본 F26개와 AT105개를 수정하거나 새 검토를 승인으로 표시하지 않았다.

이번 사용자 요청인 전체 구조 검토와 결과 기록은 완료했다. T01 전체는 in_progress다. P01/P02/P04/P05/P06의 상태·효과·commit 계약, P03의 완료 기준, P08의 Decision/retrieval 계약 및 기존 P12 실행 profile은 후속 확정 사항으로 남는다. 실제 앱/domain mock/PostgreSQL/MinerU/e2e/live semantic evaluation은 미실행이며 어떤 AT도 새로 pass/complete 처리하지 않았다.

통합 보고서 최종 읽기 전용 대조에서 R08의 model_calls 설명을 좁혔다. 현재 정책이 raw output과 audit의 동일 TTL을 확정했다는 인상을 피하고, 지속 보존·검색 용도가 보장되지 않았다는 정확한 한계로 기록했다. 그 외 담당 범위의 추가 실질 오류는 발견되지 않았다. 최종 문서 validator도 exit 0/errors 0을 확인했다.

## 추가 요청 — R01–R09 설계 문제 수정

사용자 원문: “각 문제를 해결해주되, 중대해서 내 승인이 필요한 경우 나한테 요청해줘.” 앞서 제시한 구체적인 권고 중 기존 invariant를 보존하는 R01–R06/R09를 U08의 위임 수정 범위로 기록한다. P01–P12 전체를 승인하지 않는다. R07의 결정 경쟁 정책과 R08의 기각 payload/검색 보존 정책은 사용자가 선택할 두 중요한 동작이므로 concrete draft를 만든 뒤 요청한다. 질문 전에 독립적인 수정과 검토 가능한 산출물을 완성한다.

root 한 명이 문서·current canonical full/slices/map·해결 상태 JSON·검증 규칙을 소유한다. 이번 작업에는 subagent를 사용하지 않는다. root/docs/tests AGENTS, T01, USER_OVERRIDES/INDEX/DECISION_REGISTER, PLANS, CODE_REVIEW, 기존 구조 검토, 관련 canonical·contracts·validator를 확인했다. 시작 파일 113개 SHA-256을 보존했다. 현재 앱/DDL/runtime는 없으며 T01 설계 수정과 문서 정책 검증만 수행한다.

변경 전 current 통합본을 docs/history에 exact bytes로 보존하고 새 current snapshot/map을 동기화한다. 기존 source/baseline, F/A 원본 근거, 과거 progress 기록과 미승인 P 상세는 보존한다. 복구는 이번 문서/도구 변경분과 새 파일에 한정하며 DB migration은 없다.

1. [x] 9개 항목의 구체 해결 계약과 2개 선택안·시나리오 작성.
2. [x] 위임된 7개 해결을 canonical/관련 계약/명세/모듈 지침에 일관 반영.
3. [x] 중대한 두 정책의 승인을 요청하고, 응답 범위에서만 후속 반영.
4. [x] 문서 validator/필요한 승인 경계 mutation tests, snapshot·변경 범위 검사.
5. [x] 해결/대기·검증 범위·잔여 T01 사항을 기록하고 인계.

R07/R08 답변이 없으면 미승인 정책을 default로 활성화하지 않는다. 나머지 수정은 완료한다. 실제 AT의 앱/DB/모델 실행 상태를 문서 수정만으로 pass로 바꾸지 않는다.

### R01–R09 수정 결과와 후속 승인

[해결 계약](../docs/decisions/ARCHITECTURE_FIXES.md)에 R01–R09를 구체화하고 canonical full/13 slices/map, 관련 계약, 모듈·CLI 경계와 task/acceptance metadata를 동기화했다. R01의 최신 applicability 우선, R02의 current support·effective input dependency, R03의 완료 scope·obligation fence, R04의 identity/cache 순서, R05의 read-set commit 충돌과 split/merge 교체 집합, R06의 deterministic atomic supersedes, R09의 evidence/retrieval 두 축을 U08의 명시된 범위로 적용했다.

두 중요한 정책은 선택안과 시나리오를 준비하고 독립 수정·검증을 마친 뒤 질문했다. 이후 실제 사용자 답변을 승인 JSON과 해결 상태에 보존했다.

- R07: “뒤늦은 요청은 새 결정을 저장하지 않고 현재 상태를 보여준 뒤 재확인받기 (권고)”. prepare의 scope/head/state token을 확인 payload에 결합하고 commit까지 보호한다. 상태가 바뀐 늦은 요청은 새 canonical W/K를 저장하지 않으며 확인 시도 이력을 남기고 재확인을 요구한다. 권한과 key/payload가 같은 성공 event의 retry는 기존 결과를 반환한다. AT106에 명세화했다.
- R08: “기각 이력은 정확한 fingerprint로만 조회하고, 다른 표현의 후보는 다시 검증하기 (권고)”. rejected 조회는 exact rejection scope/FP로 제한하고 다른 FP·수정된 locator는 새 validation을 거친다. accepted similarity는 유지한다. optional audit/raw payload를 기각 검색 데이터원으로 사용하지 않는다. AT107에 명세화했다.

해결 상태는 9개 모두 resolved_design, 선택 대기 0개, implementation_status는 모두 not_implemented다. P01–P12 JSON의 proposed 상태는 그대로이며 U08이 명시한 조항 외의 전체 계약을 승인한 것으로 처리하지 않았다. 공개 K 재검증 subtype 등 별도 미정 사항도 유지했다.

### 실행 검증과 보존 확인

다음 명령을 process-local PYTHONUTF8=1로 실행했다. PATH Python 대신 T00에서 확인한 번들 interpreter를 사용했다.

```powershell
$env:PYTHONUTF8 = '1'
& 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B tools/validate_bundle.py --json
& 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -m unittest discover -s tools -p 'test_*.py' -v
```

승인 요청 전 validator exit 0/errors 0, unit/mutation 35개 pass/exit 0(26.185초). R07/R08 승인 후 validator exit 0/errors 0, 35개 pass/exit 0(24.851초). tools/test_validate_bundle.py의 두 새 테스트는 선택 승인 근거를 제거하거나 대기 상태에 활성 옵션을 붙였을 때 validator가 거부하는지 확인한다. 이는 문서 승인 경계와 번들 무결성 검증이다. 모델 의미 판정, 실제 runtime 경쟁, PostgreSQL transaction, MinerU, end-to-end/live semantic evaluation은 실행하지 않았다.

현재 canonical은 2376줄/13 slices이며 current_map에 U01–U08과 동기화된 SHA를 기록했다. 이전 current snapshot의 exact SHA-256은 d22dddeabb21b222c3b81c00deebdb7141715223c53fed7be806527cb849f2fb이며 docs/history/2026-09-09_pre_architecture_fixes.md에 동일 bytes로 보존했다. docs/source와 baseline_parts, 원본 invariant_traceability.json 및 docs/review, decisions.json, T00 기록·inventory, 최초 verification/manifest는 시작 SHA와 일치한다. 이전 구조 검토는 옛 줄 번호의 근거를 보존하고 해결 계약으로 연결하는 안내만 추가했다.

시작 113개 파일 중 48개 변경, 3개 추가, 삭제 0개, 65개 byte-identical. 변경 파일은 다음과 같다.

- 지침/안내: AGENTS.md, README.md, docs/AGENTS.md, docs/INDEX.md, tests/AGENTS.md.
- 승인/경계: docs/decisions/USER_OVERRIDES.md, user_overrides.json, DECISION_REGISTER.md, docs/implementation/MODULE_BOUNDARIES.md, docs/interfaces/CLI_CONTRACT.md.
- 관련 계약: docs/contracts/01_identity_materiality.md, 02_effective_relations_dependencies.md, 03_propagation_completion.md, 04_transactions_execution.md, 05_compiler_validation_evidence.md, 06_decision_wisdom_publication.md, 08_interfaces_schema_plan.md.
- current snapshot: docs/canonical/PALIMPSEST_CANONICAL_MODEL.md, current_map.json와 00_foundation.md부터 12_open_implementation.md까지의 13개 slice 전부.
- 작업/명세: tasks/T01.md, T03.md, T04.md, T08.md, T09.md, T12.md, README.md, task_graph.json, tests/specs/ACCEPTANCE.md, acceptance_catalog.json, TRACEABILITY.md.
- 도구/진행: tools/policy_checks.py, tools/test_validate_bundle.py, progress/T01_execplan.md, T01_architecture_review.md, STATUS.md.
- 신규: docs/decisions/ARCHITECTURE_FIXES.md, architecture_fixes.json, docs/history/2026-09-09_pre_architecture_fixes.md.

이번 요청의 R01–R09 설계 수정은 완료했다. 앱 인수 명세 AT01–AT107은 모두 spec_only이며 새 pass/complete는 없다. T01은 in_progress, T02–T12는 planned, T13은 deferred다. 남은 T01 실행 profile/P12/F26, P10/F22/F23 등의 미정 계약은 각 후속 작업의 선행 조건으로 유지한다. 별도 정책 선택이 필요한 R07/R08은 모두 답변을 받아 이번 범위에 승인 대기는 없다.

## 추가 요청 — PostgreSQL·ID·관리 등록·canonical 반영

사용자의 네 선택을 U09의 명시 범위로 기록하고 T02용 SQL 초안까지 구체화한다. PostgreSQL은 18 계열로 시작하며 pgvector를 사용한다. Data는 원본 bytes SHA-256, 신규 opaque ID는 UUIDv7이다. 평범한 중복 import를 거부하고 원본 등록은 Palimpsest 도구의 staging/publish/복구 경로를 통한다. 임시 후보·잠정 판정은 Runtime에서 관리하고 승인된 효과를 Canonical Store에 atomic하게 반영하되 영속 Record를 보존한다.

root가 공유 schema/승인/검증 도구의 편집을 소유한다. 보조 agent 두 개는 PostgreSQL/pgvector 공식 자료와 기존 저장·판정 계약 충돌을 읽기 전용으로 검토한다. root/docs/tests AGENTS, PLANS, CODE_REVIEW, T01/T02, USER_OVERRIDES/INDEX/DECISION_REGISTER, ARCHITECTURE_FIXES, 관련 current slices/CLI/retrieval/transaction/storage 계약을 확인했다. 시작 파일 116개 SHA-256을 보존했다. Ponytail의 최소 구현 원칙을 유지하며 아직 필요한 기능이 없는 I/K/W/P/B SQL scaffold는 만들지 않는다.

1. [x] 네 선택의 승인 범위·중복/retry·Runtime 승격 계약 구체화.
2. [x] PostgreSQL 18/pgvector profile과 Data/acquisition/등록 journal SQL 초안 작성.
3. [x] current full/slices/map, 관련 지침·작업·인수 명세 동기화.
4. [x] 정책 mutation tests와 문서 검증, SQL 독립 검토 및 실행 가능성 확인.
5. [x] 원본 보존·변경 파일·검증 한계·남은 T01 선택 기록.

이 작업은 T01의 계약/schema draft 경계다. 앱 언어/DB driver/migration runner, DB 설치 위치·개발/테스트 실행 환경과 MinerU 실 profile은 이번 사용자 선택으로 확정되지 않았다. 실제 사용자 DB나 원본 파일을 변경하지 않는다. 복구 범위는 이번 변경 파일과 새 초안이며 현재 canonical 변경 전 snapshot도 exact bytes로 보존한다.

초기 plan patch는 문단 일부를 독립 줄로 가정해 적용 실패했으며 파일 변경 없이 실제 문단을 확인해 재적용했다. DB 도구 조회에서 psql/pg_config/postgres가 PATH에 없었다. 번들 Python에는 pglast/psycopg가 없었다. Docker info는 config/engine 접근 거부(exit 1)였으며 실제 DB 사용 가능성을 확인한 것으로 기록하지 않는다.

### U09 결과와 설계 선택

[STORAGE_IDENTITY](../docs/decisions/STORAGE_IDENTITY.md)에 사용자 네 선택의 원문·적용 범위와 세부 해석을 연결했다. 공식 조회 기준 PostgreSQL 18.6/pgvector 0.8.6, PG19 Beta3를 확인했으며 실제 설치값과 구분했다. 최초 major는 18이고 향후 major는 명시적으로 검증한다. Data ID=보존 원본 bytes SHA-256, 나머지 신규 opaque ID=UUIDv7이며 외부 ID/FP/version/counter/commit ordering을 바꾸지 않는다.

평범한 duplicate import는 새 Data/acquisition/원본 복제/D2I를 만들지 않고 기존 ID와 duplicate_data를 반환한다. 같은 성공 request/입력은 기존 result를 재생한다. 독립 acquisition은 명시적 provenance 기록으로만 추가할 수 있다. 같은 논문의 다른 bytes를 hash만으로 의미 중복 기각하지 않는다.

관리 등록은 배타적인 request staging 소유·복사한 bytes 검증·prepared journal·overwrite 없는 publish·Data/acquisition/result atomic commit·reconcile로 정리했다. 사용자 원본과 공유 objects를 실패 cleanup으로 삭제하지 않는다. 파일만 이미 존재할 때와 canonical Data가 존재할 때를 구분해 crash/병렬 등록을 복구하도록 했다.

“판정을 Runtime에 임시 저장 후 옮기기”는 후보·잠정 결과의 검증된 payload/effects를 canonical에 반영하는 뜻으로 구체화했다. 최종 판정 Record/FP/reason/refs는 Runtime에서 영속 보존하고 효과·provenance/support·terminal Record·candidate cleanup·outbox는 같은 PostgreSQL transaction에 반영한다. 기존 U08/R08의 기각 이력이나 실제 승인 근거를 삭제하지 않는다.

[T02_STORAGE_SCHEMA](../docs/schema/T02_STORAGE_SCHEMA.md)와 SQL에는 canonical_store.data/data_acquisitions, compiler_runtime.data_import_requests의 세 테이블만 구체화했다. hash/UUIDv7/PK/FK·acquisition 소속/불변 snapshot·journal 상태 전이·고정 입력/terminal receipt 보호를 작성했다. 아직 사용하지 않는 I/K/W/P/B 및 embedding tables/ANN index는 만들지 않았다. pgvector extension 요구와 profile별 저장/ANN 차원 경계는 확정했지만 실제 모델 교체 차원·precision을 자동 선택하지 않았다.

root가 DDL과 공유 계약을 소유했다. 보조 검토는 공식 자료와 SQL/복구 계약을 읽기 전용으로 검토한 후 맡긴 15개 주변 문서만 동기화했고, 다른 agent는 SQL constraint fixture 한 파일만 작성했다. 독립 검토에서 동일 request staging 경쟁과 publish된 object의 Data 중복 오인을 보완했다. SQL CHECK의 NULL 결과가 허용되는 문제를 전체 조건 IS TRUE로 막고 fixture에도 반례를 포함했다. 새 공개 Compiler Record subtype은 없다.

### 실행 검증·원본 보존

다음 두 명령을 실행했다.

```powershell
$env:PYTHONUTF8 = '1'
& 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B tools/validate_bundle.py --json
& 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -m unittest discover -s tools -p 'test_*.py' -v
```

validator exit 0/status passed/errors 0. unit/mutation **38개 pass**, exit 0(35.172초). 신규 세 test method는 PG19 자동 선택/pgvector 제거, SHA/UUID/duplicate/retry/Record 승격 정책 drift, 이전 snapshot 변조를 검출한다. U09 승인 원문 누락 subcase도 검사한다. 승인/문서 정책 검증이며 앱 또는 SQL 실행 검증이 아니다.

추가 읽기 명령은 Get-Command psql,pg_config,postgres,docker 및 번들 Python의 importlib.util.find_spec으로 도구/패키지 존재를 조회했다. Docker 실행 가능성은 다음 읽기 전용 명령이 exit 1이었다.

```powershell
& 'C:/Program Files/Docker/Docker/resources/bin/docker.exe' info --format '{{.ServerVersion}}'
```

psql/postgres/pg_config 부재, pglast/psycopg 부재와 Docker config/engine 접근 거부로 현재 실제 DB 실행을 확인하지 못했다. 이는 automatic approval review의 거절을 받은 것이 아니며 별도 설치·권한 변경을 시도하지 않았다. SQL/fixture는 미실행이다. 앱/파일 crash/복수 PostgreSQL session/e2e/live semantic tests도 미실행이다. AT01–AT112는 모두 spec_only다.

중간 편집용 functions JavaScript 한 번은 template literal의 backtick으로 SyntaxError가 나서 shell 실행 전 종료됐다. 내용 전달을 hex-encoded JSON 인자로 바꿔 다시 적용했다. STATUS patch의 문단 부분 줄 일치 실패도 파일 변경 없이 재적용했다. 이 오류들을 테스트 성공으로 덮지 않았으며 final validator와 suite 결과와 구분한다.

변경 전 current bytes를 docs/history/2026-09-09_pre_storage_identity.md에 보존했다. SHA-256은 85c0886655c2b765e9ee461c58779273d64bbc73c7025aa4245baae1de10141b이며 current_map의 previous_snapshot과 일치한다. 기존 U08 이전 snapshot은 history_snapshots에 계속 연결했다. 현재 canonical은 2381줄/13 slices, 승인 U09까지 9개, 인수 명세 112개다. 원본 source/baseline, 과거 snapshots, docs/review, 원본 invariant_traceability.json, P01–P12 decisions.json, T00 inventory/기록·초기 manifest/verification은 보존한다.

시작 116개 파일 중 38개 수정, 5개 추가, 삭제 0개, 78개 byte-identical이다. 변경 파일:

- 안내·승인: AGENTS.md, README.md, docs/AGENTS.md, docs/INDEX.md, docs/decisions/USER_OVERRIDES.md, user_overrides.json, DECISION_REGISTER.md, tests/AGENTS.md.
- current: docs/canonical/00_foundation.md, 01_data_d2i.md, 04_compiler_records.md, 10_relational_vocabulary.md, 12_open_implementation.md, PALIMPSEST_CANONICAL_MODEL.md, current_map.json.
- 관련 계약: docs/contracts/01_identity_materiality.md, 04_transactions_execution.md, 07_storage_retrieval_security.md, 08_interfaces_schema_plan.md.
- interface/실행: docs/interfaces/CLI_CONTRACT.md, RETRIEVAL_PROFILE.md, docs/implementation/ENVIRONMENT.md, MIGRATION.md, MODULE_BOUNDARIES.md.
- 작업·명세: tasks/T01.md, T02.md, T03.md, T04.md, T12.md, README.md, task_graph.json, tests/specs/ACCEPTANCE.md, acceptance_catalog.json, TRACEABILITY.md.
- 도구·진행: tools/policy_checks.py, tools/test_validate_bundle.py, progress/T01_execplan.md, STATUS.md.
- 신규: docs/decisions/STORAGE_IDENTITY.md, docs/schema/T02_STORAGE_SCHEMA.md, T02_storage_draft.sql, T02_storage_checks.sql, docs/history/2026-09-09_pre_storage_identity.md.

U09 선택 반영과 T01 SQL 초안 산출은 완료했다. T01은 in_progress, T02–T12 planned, T13 deferred를 유지한다. 남은 직접 실행 선택은 P12/F26의 앱 언어/CLI·DB driver/migration runner와 독립 DB 실행 환경이다. P10의 전체 보존·삭제/backup, P06의 공개 재검증 subtype, 실제 MinerU/backend/model profile 등 범위 밖 미정 사항은 해당 후속 단계에 남는다. 이번 네 선택을 재질문하지 않는다.

## 추가 요청 — Python·Docker 선택과 현재 접근 확인

사용자 원문: “앱 언어는 Python으로 작성해주고, 배포 용이성을 위해 Docker 기반으로 작동하면 좋겠어. Docker 접근 권한 너한테 있나 지금?” U10으로 언어/배포 방식을 확정하고 Docker 현재 접근을 읽기 전용으로 확인한다. root/docs/tests 지침과 승인/INDEX/DECISION_REGISTER, T01, PLANS/CODE_REVIEW, ENVIRONMENT와 current 미정값을 확인했다. 시작 파일 121개 SHA-256을 보존했다.

1. [x] 일반 sandbox와 승인 실행 경로에서 Docker 연결을 각각 확인.
2. [x] Python/Docker 승인 및 current canonical/실행 지침·task/명세의 미정값 동기화.
3. [x] 문서/정책 mutation 검사, 원본 보존과 정확한 검증 범위 기록.

root가 모든 편집을 소유하고 보조 agent 한 명이 남은 미정 범위를 읽기 전용 검토한다. Docker 확인에는 OpenAI Docs 지침과 현재 도구 결과를 사용하며 Ponytail의 최소 변경 원칙을 유지한다. 이번 선택은 앱 언어/배포 방식이며 Python exact version/CLI·DB driver/migration runner·image digest를 사용자가 구체적으로 선택했다는 뜻은 아니다. 컨테이너 생성·image pull·DB 적용·앱 구현은 이번 접근 확인 범위에서 실행하지 않는다.

일반 docker --version은 29.7.2지만 docker info는 config/engine pipe Access denied로 exit 1이었다. 같은 info 명령을 require_escalated로 실행하자 exit 0, server 29.7.2를 반환했다. 이전 sandbox 실패를 보존하되 “현재 Docker 접근 불가”를 전체 권한 상태로 일반화하지 않는다. 사용자의 설정/파일 ACL이나 daemon 설정을 변경하지 않았다.

### U10 결과와 검증

Python 앱·Docker 실행/배포를 U10으로 기록하고 current canonical full/13 slices/map, 실행 지침, T01/T02/task graph와 AT64/AT82/AT108 명세의 승인 의존성을 동기화했다. 이전 current exact bytes는 docs/history/2026-09-09_pre_python_docker.md에 보존했다(SHA-256 bef554affeab9ddb20166eb023e0afa65591a85f274b690d788e297cdb441a92). 기존 history chain과 source/baseline은 유지한다. 새 canonical은 2381줄이며 hash는 3bce40b044222f1e82e3e3d0e787a64107e8896fcc0775653e743f0cc7df59b5다.

승인 실행 경로에서 실행한 읽기 전용 명령과 결과:

```powershell
& 'C:/Program Files/Docker/Docker/resources/bin/docker.exe' info --format '{{json .ServerVersion}}'
# exit 0: "29.7.2"
& 'C:/Program Files/Docker/Docker/resources/bin/docker.exe' info --format 'server={{.ServerVersion}} os={{.OSType}} arch={{.Architecture}}'
# exit 0: server=29.7.2 os=linux arch=x86_64
& 'C:/Program Files/Docker/Docker/resources/bin/docker.exe' compose version --short
# exit 0: 5.5.1
```

문서/도구 검증 명령:

```powershell
$env:PYTHONUTF8 = '1'
& 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B tools/validate_bundle.py --json
& 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -m unittest discover -s tools -p 'test_*.py' -v
```

validator exit 0/status passed/errors 0. 도구 unit/mutation 39개 pass, exit 0(37.785초). 새 test method는 Python/Docker 정책 변경을 두 subcase로 검출하며 U10 승인 근거 누락도 기존 검사에 추가했다. 이는 문서와 정책 검사이며 AT01–AT112의 앱 acceptance는 모두 spec_only다. 컨테이너/실제 PostgreSQL/SQL fixture/앱 unit/e2e/live semantic 검증은 미실행이다.

T01 in_progress와 T02–T12 planned/T13 deferred를 유지한다. 언어와 배포 방식은 더 이상 미정이 아니다. exact Python version·CLI library·dependency manager·DB driver·migration runner·image digest·service/volume/port profile과 실제 PostgreSQL 앱 검증은 후속 구체화 항목이다. 이번 범위에서 사용자 승인을 추가로 요구하는 blocker는 없다. Docker 읽기 접근 성공은 모든 변경 작업의 무제한 권한을 뜻하지 않는다.


U10 변경 대조: 시작 121개 파일 중 23개 수정, 1개 추가, 삭제 0개, 98개 byte-identical. source/baseline·기존 history·원본 review/traceability·decisions.json·T00 기록·초기 manifest/verification은 byte-identical이다. 변경 파일:

- tools/test_validate_bundle.py
- tools/policy_checks.py
- tests/specs/acceptance_catalog.json
- tests/specs/ACCEPTANCE.md
- tasks/task_graph.json
- tasks/T02.md
- tasks/T01.md
- README.md
- progress/T01_execplan.md
- progress/STATUS.md
- AGENTS.md
- docs/canonical/PALIMPSEST_CANONICAL_MODEL.md
- docs/canonical/current_map.json
- docs/canonical/12_open_implementation.md
- docs/canonical/00_foundation.md
- docs/AGENTS.md
- docs/schema/T02_STORAGE_SCHEMA.md
- docs/INDEX.md
- docs/decisions/USER_OVERRIDES.md
- docs/decisions/user_overrides.json
- docs/decisions/DECISION_REGISTER.md
- docs/implementation/MODULE_BOUNDARIES.md
- docs/implementation/ENVIRONMENT.md
- 신규: docs/history/2026-09-09_pre_python_docker.md

진행 기록 갱신 후 문서 validator를 다시 실행해 exit 0/errors 0을 확인했다. 전체 실행 명령과 미실행 범위는 위 결과를 따른다.

## 추가 요청 — D/I/K/W 저장 스키마 v1

사용자는 다음 작업으로 제안한 “D/I/K/W 저장 스키마 v1 — ERD, 필드 정의, 제약조건, 트랜잭션 경계, 단계별 migration 계획”에 “작업 진행해줘.”라고 답했다. 이 작업은 T01의 검토 가능한 저장 설계 산출물 작성이다. 실제 T02 앱/DB migration 실행 완료나 P01–P12의 일괄 승인을 뜻하지 않는다.

root/docs 지침, USER_OVERRIDES/INDEX/DECISION_REGISTER, T01, PLANS/CODE_REVIEW와 U08/U09/U10 및 관련 current slices를 기준으로 한다. 시작 122개 파일의 SHA-256을 보존했다. root가 공유 schema 문서/계약/주변 링크의 유일한 편집자이고 두 보조 검토가 K/W 및 Runtime/검색/acceptance를 읽기 전용으로 확인한다. 별도 새 agent 생성은 thread limit으로 실패하여 이미 완료한 agent를 재사용했다.

1. [x] 현재 D 초안과 I/K/W/Runtime 계약의 저장 요구 및 승인 경계를 추출한다.
2. [x] docs/schema/DIKW_STORAGE_SCHEMA_V1.md에 ERD·필드/참조/제약·읽기·commit·단계별 migration·미정표를 작성한다.
3. [x] 독립 검토에서 참조 누락·동시성·불변성·모델 교체·승인 확대를 확인하고 필요한 부분을 수정한다.
4. [x] INDEX/T01/기존 D 초안과 진행 상태를 연결하고 문서 검사 및 기존 도구 테스트를 실행한다.
5. [x] 원본/기존 canonical/SQL 보존을 대조하고 변경 파일·실행 결과·미실행 acceptance·후속 작업을 기록한다.

추가 문서 한 개와 기존 안내/진행 문서만 변경할 계획이다. 의미 정책을 바꾸지 않으면 canonical full/slices/map과 승인 registry는 그대로 둔다. production table/placeholder enum/빈 Python 모듈을 생성하지 않는다. 제안 자료형/테이블명은 구현 설계안으로 표시하며, 새로운 공개 K 재검증 subtype은 확정하지 않는다. 실제 PostgreSQL 동시성/파일 복구는 후속 vertical slice의 검증으로 남긴다. 롤백은 이번 변경 파일과 신규 문서 범위에서만 가능하며 사용자 DB/Artifact Store는 건드리지 않는다.

검증은 tools/validate_bundle.py --json 및 기존 tools/test_*.py suite를 번들 Python으로 실행한다. 새 문서를 위한 구현 모방 테스트는 추가하지 않는다. AT63/64/88/103/108의 설계·실행 구분을 유지하고 각 도메인의 관련 acceptance ID를 새 문서에 연결한다. 문서 검사 통과는 앱 acceptance 통과가 아니다.

### 저장 스키마 v1 산출물과 검토 결과

docs/schema/DIKW_STORAGE_SCHEMA_V1.md를 작성했다. 공통 SQL 자료형과 typed refs, ERD 2개, D/I/K/W 필드·소속/불변 제약, Runtime execution/Record/candidate/input/effect, exact current support, scope 의무와 완료, parser/profile/embedding, W2K confirmation의 event별 성공 binding, 공통 commit와 순서, P/B 경계, migration 단계·조회/index·AT 매핑·미정표를 포함한다. 실제 DB 적용이나 새 public subtype 확정은 하지 않았다.

root가 공유 설계를 단독 편집하고 두 agent가 읽기 검토했다. K/W 검토의 confirmation event parent/성공 유일 키와 성공 retry 우선순위를 보완했다. Runtime 검토의 Record→retrieval snapshot FK, execution→work claim 및 canonical commit fencing, scope/work의 다중 cause relation, K root 필수/parent 조건부 참조를 보완했다. 두 agent는 지적한 여섯 항목의 문서 수준 해소를 재확인했다. root는 parse artifact Data/profile 소속, 최초 I/Record Data 일치, pointer 이력, commit order FK와 T06 N2E의 단계 배치도 대조했다.

단일 row gate/transactional counter는 R01/R05를 검증할 첫 물리 구현안이며 canonical 쓰기 throughput 한계와 세분화 조건을 명시했다. snapshot을 얻은 뒤 auth/key/payload 및 기존 성공을 먼저 확인하고 새 요청의 read-set/scope/시간을 검사한다. 실행의 lease fencing도 terminal 효과 반영까지 적용한다. 이 동시성 설계는 실제 PG 검증 전이며 사실상 설치된 구현으로 표시하지 않는다.

미정 P06 공개 이름에 KRevalidationRecord/record_type=k_revalidation을 후보로만 제시했다. 전체 effect-only matrix, identity/materiality 세부, authority/scope/직접 Decision profile과 검색/보존 정책은 각 후속 기능의 동결 조건이다. 이번 검토 문서 작성 및 독립 T02 준비를 막는 새 승인 요청은 없다. U01–U10과 P01–P12 status는 변경하지 않았다.

### 실행한 명령과 범위

```powershell
$env:PYTHONUTF8 = '1'
& 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B tools/validate_bundle.py --json
& 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -m unittest discover -s tools -p 'test_*.py' -v
```

validator exit 0/status passed/errors 0. Markdown 91개, table occurrences 329개, relative links 508개. 기존 도구 unit/mutation 39개 pass, exit 0(38.597초). 새로운 test method나 dependency는 추가하지 않았다. 마지막 진행 기록 갱신 후 validator도 재실행해 exit 0/errors 0을 확인했다. Mermaid는 관계/문법을 읽기 검토했고 별도 renderer 실행은 하지 않았다. Codex 파일 preview 요청은 queued로 반환되어 현재 화면에 열렸다고 단정하지 않는다.

PostgreSQL 18 공식 constraints/CREATE TABLE/transaction isolation/explicit locking/JSON types 및 pgvector v0.8.6 README를 조회해 자료형·FK·잠금·sequence·JSON/벡터 경계를 확인했다. 잘못된 sql-createconstraint 문서 URL 한 번은 조회 오류였으며 실제 sql-createtable 공식 문서를 확인해 대체했다. DB/컨테이너/SQL fixture/CLI/MinerU/model/e2e/live semantic 실행은 없었다. AT63/64/88/103/108을 포함한 앱 AT01–AT112는 모두 spec_only이며 의미 품질·동시성 실행 통과를 주장하지 않는다.

### 변경 파일·보존·후속

시작 122개 중 기존 6개 수정, 1개 추가, 삭제 0개, 116개 byte-identical이다.

- 신규: docs/schema/DIKW_STORAGE_SCHEMA_V1.md.
- 수정: docs/INDEX.md, docs/schema/T02_STORAGE_SCHEMA.md, tasks/T01.md, tasks/task_graph.json, progress/STATUS.md, progress/T01_execplan.md.

docs/source·baseline·docs/history·current canonical full/slices/map·승인 registry·decisions.json·기존 T02 SQL/fixture·검증 도구/테스트·T00 기록과 초기 manifest/verification을 그대로 보존했다. Git repository가 없어 변경 전 SHA-256 목록과 파일별 결과를 대조했다.

요청한 저장 설계 v1 문서 작성은 완료다. T01 전체는 in_progress, T02–T12 planned, T13 deferred를 유지한다. 다음은 구체 Python/CLI/driver/migration/Docker image·독립 DB/volume profile을 선택·검증하고 기존 D SQL 초안을 실제 T02 import/show/verify/recovery와 연결하는 것이다. I/K/W 미래 테이블은 단계별로 추가하고 §13의 미정 사항은 영향받는 기능 전에 해결한다.
