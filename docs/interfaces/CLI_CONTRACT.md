# CLI-first interface 계약

> U01: 승인된 범위. T02의 palim help/version/doctor, data import/show/verify, requests show/recover, db migrate와 JSON/exit profile은 [T02 실행 안내](../implementation/T02_RUNTIME.md)에서 구현·검증했다. 아래 T03 이후 command와 나머지 계약은 구현 초안이다.

## 1. 범위와 경계

현재 배포 가능한 사용자 interface는 CLI다. terminal만으로 D 등록, PDF 파싱, D2I, I/K 조회와 compilation, 검토, 질의, Decision 확인/추적, P/B 생성·export, job 상태·pause/resume/cancel을 수행한다. GUI나 브라우저를 설치/실행하지 않아도 된다. T02부터 CLI와 application service를 함께 작은 기능 단위로 연결한다.

`palim`은 T02에 구현한 entrypoint다. domain/application layer가 argument parser, stdout/stderr, GUI toolkit, HTTP request에 의존하지 않게 한다. HTTP server를 CLI의 필수 사용자 interface로 새로 만들지 않는다. 같은 머신의 MinerU worker는 별도 parser adapter 내부일 수 있다.

## 2. 단계별 command surface — 제안

```text
T02  palim --help
     palim --version
     palim doctor
     palim data import <path> [--request-id <uuidv7>]
     palim data show <data-id>
     palim data verify <data-id>
     palim requests show <request-id>
     palim requests recover <request-id>
     palim db migrate

T03  palim compile data <data-id>
     palim information show <information-id>
     palim jobs list
     palim jobs show <job-id>

T04  palim compile information <information-id>
     palim knowledge show <node-id>

T05  palim information repair <information-id> --request <file>
     palim knowledge revalidate <node-id>

T06  palim edges show <edge-id>
     palim edges revalidate <edge-id>

T07  palim worker run
     palim jobs watch <job-id>
     palim jobs pause <job-id>
     palim jobs resume <job-id>
     palim jobs cancel <job-id>

T08  palim query <question>
     palim provenance show <object-id>

T09  palim decision prepare --input <json-file>
     palim decision confirm <draft-id> --payload-hash <hash>
     palim decision trace <decision-id>

T10  palim parchment compose --input <json-file>
     palim book compose --input <json-file>
     palim export <object-id> --output <path>

T11  palim review list
     palim review show <record-id>
     palim review resolve <record-id> --decision <accept-or-reject>
     palim maintenance status
```

사용할 수 없는 미래 command를 성공 stub으로 노출하지 않는다. command가 필요로 하는 schema/authority 정책이 아직 미승인이면 해당 기능은 blocked로 표시한다. T03부터 needs_human은 job status에서 보이며 그 상태가 CLI에서 해결되기 전까지 완료로 표시하지 않는다.

## 3. stdout/stderr와 안정된 machine output

자동화용 `--json`을 공통 옵션으로 계획한다. stdout에는 versioned JSON result만, stderr에는 progress/log/warning만 기록한다. 색상/ASCII animation이 JSON에 섞이면 안 된다. 사람이 읽는 출력과 동일한 result DTO를 사용한다. JSON에는 command success와 workflow completion을 분리해 `command_status`, `job_status`, `result_refs`, `warnings`, `error` 등 확정된 schema 필드를 둔다.

`jobs resume`의 command success는 resume 요청 접수일 수 있으며 underlying propagation의 정상 완료가 아니다. `compile data`가 비동기 job을 반환하면 job ID와 pending/running 상태를 반환한다. `--wait` 또는 후속 watch가 있을 때만 terminal status까지 관찰한다. 출력 pagination이나 한 번의 model context limit을 전체 전파 cap으로 사용하지 않는다.

## 4. 비대화형 실행과 authority

TTY가 없거나 `--non-interactive`이면 누락된 입력 때문에 무한 prompt 대기하지 않는다. 명시적 `needs_confirmation`, `missing_argument`, `blocked` 등 machine-readable 원인과 nonzero exit code를 반환한다. 보류된 semantic job을 실행 실패로 위장하지 않는다.

`--yes`는 실제 actor 권한이나 payload-bound decision evidence를 만들어내지 않는다. 일반 위험 확인을 생략하는 옵션이 존재하더라도 Decision의 actor/authority/payload binding 검증은 별도다. 사람이 terminal에서 정확한 payload를 확인해 승인한 event 또는 사전 검증된 confirmation artifact를 통해 같은 service를 호출한다. batch/pipe가 자동으로 LLM recommendation을 commitment로 만들면 안 된다.

review acceptance도 단순 DB insert가 아니다. canonical Validator/권한/현재 입력 freshness와 atomic commit을 우회하지 않는다. view/preview에서 revision과 provenance를 표시하고 변경 직전 payload가 바뀌면 다시 확인한다.

## 5. Exit status와 오류 — 제안

정확한 숫자는 T01/P12에서 registry로 고정한다. 최소한 success, usage/config error, environment/parser missing, technical execution failure, confirmation/permission failure, unresolved workflow 상태를 구분한다. 일반적인 Ctrl-C 취소는 CLI 관찰 종료와 durable job cancel을 혼동하지 않는다. watch를 중단했다고 job을 조용히 삭제하지 않는다.

logs에서 secret·민감한 원문·parser output 전체를 기본 출력하지 않는다. 파일명/문서에 포함된 terminal escape sequence는 escape한다. UTF-8 한국어 경로, 공백, quote가 포함된 경로를 shell string 결합 없이 안전하게 전달한다.

U09의 새 duplicate import는 `duplicate_data`와 기존 data_id, nonzero exit status를 반환한다. 동일 성공 request의 재시도는 권한과 고정된 bytes/metadata/actor를 확인해 기존 성공 result를 반환한다. 같은 request ID의 다른 입력은 `idempotency_conflict`, hash/기존 artifact 불일치는 `integrity_conflict`로 구분한다. 정확한 숫자 exit code는 미정이다.

## 6. 완료 gate

T12의 e2e는 display server/브라우저/GUI 없이 import→MinerU PDF parse→validated I→K→query→explicit decision→trace→P/B export를 검증한다. provider mock, 실제 MinerU parser, 실제 PostgreSQL, live semantic evaluation 결과를 구분한다. T13 GUI는 이 CLI release의 선행 조건이 아니며 지금은 deferred다.

## U08 구조 수정에 따른 결과/확인 계약

query/trace의 새 결과는 evidence_mode와 retrieval_strategy 및 실제 epistemic_basis를 함께 제공한다. reported trace는 I/D를, authority_confirmed trace는 origin W/confirmation을 사용한다. 과거 retrieval_mode는 재작성하지 않고 복원 불가 필드는 legacy unknown으로 표시한다.

decision confirm은 같은 event/payload retry에 같은 W/K를 반환하고 다른 payload의 key 재사용은 conflict다. payload에 명시된 supersedes와 scope/effective_at을 확인하여 W/K/Record/관계/provenance/outbox를 한 transaction에 저장한다. R07에 따라 준비한 scope/head state가 바뀌면 새 canonical W/K를 저장하지 않고 current 상태와 재확인 필요를 반환한다. 같은 성공 event/payload의 retry는 권한 확인 후 기존 결과를 반환한다. R08에 따라 기각 이력은 정확한 scoped FP만 조회하고 다른 표현은 새 검증으로 처리한다. jobs의 완료는 scope/watermark와 causal 의무의 completion receipt를 표시하며 queue empty를 완료로 치환하지 않는다.

## U09 — Data 관리 등록과 진단

data import는 application service가 사용자 원본을 관리 staging에 복사하고 전체 보존 bytes의 SHA-256으로 Data를 식별하는 경로다. 사용자 원본을 이동·삭제하지 않으며 관리 폴더 직접 복사를 자동 등록으로 간주하지 않는다. 새 request로 같은 bytes를 제출하면 Data/acquisition/원본 복제/D2I를 새로 만들지 않는다. 같은 논문이라도 bytes가 다르면 별도 Data이며 제목/DOI로 자동 병합하지 않는다. request ID는 등록을 시작할 때 반환·기록해 응답 유실 후 조회/재시도에 사용할 수 있게 한다. 위 옵션 문법은 구현 초안이다.

doctor는 PostgreSQL 최초 major 18과 vector extension 호환성, 실제 server/extension version과 Artifact Store 접근 상태를 진단한다. SQL 설치·업그레이드·폴더 스캔 import를 자동 수행하지 않는다. [저장 계약](../decisions/STORAGE_IDENTITY.md)과 [T02 SQL 초안](../schema/T02_STORAGE_SCHEMA.md)을 따르며 CLI library/DB 실행 위치·driver는 아직 미정이다.

## U11 — source D2I 결과와 모델 단계

새 `compile data`는 local MinerU와 결정적 source-unit 조립·구조 검사를 요청한다. D2I semantic Generator/Validator model/prompt를 요구하지 않으며 LLM 의미 해석은 `compile information`의 I2K 단계부터 적용한다. 미래 I2K command를 성공 stub으로 제공하거나 T03 실행으로 표시하지 않는다. 새 profile은 `source-d2i-v1` / `source-information-v1`이고 과거 semantic D2I job은 해당 역사 profile로 표시한다.

`information show`는 source unit_type, `semantic_type=null`, parser extracted content/image refs, exact Data/page/region/raw locator/anchor/profile/hash와 flags를 보여 준다. `jobs show`는 requested/completed pages, source-block coverage와 누락/invalid/unsupported 상태, source I/Record refs를 설명한다. 구조적 accepted/completed는 의미의 진실·사람의 충실성 승인과 다르다. partial/zero-output/coverage 누락을 전체 성공으로 노출하지 않는다. 실제 field/option은 versioned 구현 profile을 따르고 미구현 상태를 감추지 않는다.

header/footer/reference text와 Figure 전체/panel/caption/continuation을 D2I에서 정보 가치로 삭제하지 않는다. 검색/context filter는 원문 I와 별도 projection으로 표시한다. 같은 input/profile/generation의 성공 retry는 같은 canonical effects를 재생하며 모델 변경으로 I를 수정하지 않는다. 자세한 정책은 [U11](../decisions/D2I_SOURCE_PRESERVATION.md)에 있다.

## T03 — 페이지 조회와 context projection

현재 source I의 조회 경로에 다음 두 명령을 둔다. 명시적으로 선택한 source D2I 실행에서 페이지와 모델 입력용 projection을 읽으며 canonical I/Record를 생성·수정하지 않고 LLM을 호출하지 않는다.

```text
palim information pages --execution-id <source-execution-uuid>
palim information context --execution-id <source-execution-uuid> --page <physical-page-number>
```

`information pages`는 원문 블록을 페이지별로 MinerU index에 따라 정렬하고 exact I·page·region·raw block 참조와 이미지를 연결한다. `information context`의 `--page`는 1부터 시작하며 기본 범위는 현재 페이지와 앞뒤 한 페이지다. 각 페이지의 `target_information_ids`와 참고 I를 구분하고, 연결된 I의 원문이 window 밖에 있으면 `missing_information_pages`를 통해 불완전한 문맥을 표시한다. 이 결과를 I2K 실행·지식 승인·전체 문서 처리 완료로 표시하지 않는다. 소유 페이지, cross-page Figure와 반복 window의 중복 처리 경계는 [페이지 context 안내](../implementation/PAGE_CONTEXT.md)를 따른다.
