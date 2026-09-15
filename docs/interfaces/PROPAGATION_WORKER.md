# 변경 영향 전파와 Wiki 갱신 worker

2026-09-14 앱0.19 후속: 새 worker 이미지 `palimpsest-n2e:0.19.0`와 검증된 schema0019에서 [N2E typed relations](N2E_RELATIONS.md)을 사용한다. edge_revalidate는 네 관계의 exact `edge_review_target`을 처리하며 새 predicate·semantic Revision·applicability 변화를 구분한다. 최신 negative가 반복되면 새 material outbox를 만들지 않는다. 현재 K2K는 여전히 Node 전제를 쓰므로 이 안내를 Edge-consuming inference의 완료로 확대하지 않는다. 아래0.18의 공통 materiality 정책은 유지한다.

앱 **0.18.0**, schema **0016_propagation_worker**의 운영 안내다. [사용자 정정](../decisions/MATERIALITY_FIRST_PROPAGATION.md)에 따라 신규 run은 반복 자체로 멈추지 않고 독립 materiality/equivalence 판정으로 새 의미 전파를 결정한다. 과거0.17의 frozen halt policy와 모든 SQL bytes는 보존한다. 최초 실제 모델 실행은 [T16 결과](../../output/t16-propagation/REPORT.md), 과거 진단은 [T17 결과](../../output/t17-propagation-anomaly/REPORT.md), 현재 정책은 [T19 결과](../../output/t19-materiality-convergence/REPORT.md)를 따른다. 전체 T07 acceptance나 수렴을 자동 보장한다는 뜻은 아니다.

기존 [K 의미 개정](KNOWLEDGE_REVISION.md), [K2K](K2K_RUNTIME.md), [Wiki 편집](PAPER_WIKI_PROJECTION.md), [Wiki DB 저장](WIKI_DATABASE.md) 규약을 함께 사용한다. D2I·D2K는 이 worker의 실행 경로에 없다. I를 추가하거나 원문을 다시 파싱하지 않는다.

## 1. 실행 범위와 저장

한 run은 시작 Record, 허용 Data, 선택 Wiki와 그 현재 import, 자료 버전, 모델과 discovery 정책을 고정한다. 이 범위의 시작 Record 및 run이 반영한 후속 Record에서 발생한 outbox를 계속 처리한다. 다른 프로젝트의 모든 outbox를 함께 소비하거나 미래의 외부 변경까지 완료했다고 표시하는 방식은 아니다.

| 저장 항목 | 의미 |
|---|---|
| `propagation_runs` | 불변 scope/policy/fingerprint와 실행 상태, 초기 source watermark |
| `propagation_tasks` | outbox 처리, node/edge 재검증, N2E/K2K, Wiki 갱신의 durable 작업 |
| `propagation_task_causes` | 같은 작업으로 합쳐진 정확한 시작 Record·outbox·부모 task 참조 |
| `propagation_execution_bindings` | task와 실제 Knowledge execution의 결속 |
| `propagation_events` | 시작 확인, lease, 오류, 재시도, 판정·완료와 중단 이력 |
| 기존 `k_outbox` | 반영된 효과의 불변 사건. 처리했다고 삭제하거나 내용·ID를 바꾸지 않음 |
| `knowledge_current_supports` | 같은 KRevision에 새로 검증된 현재 추론 근거를 선택하는 추가 이력 |

작업은 소유권 token과 만료 시각을 가진 lease로 실행한다. 재전달은 같은 task의 이력을 잇고, 오래된 worker의 token으로는 결과를 반영할 수 없다. 모델 호출은 DB transaction 밖에서 이루어진다. 반영 시에는 현재 입력·근거·lease를 다시 확인한다.

같은 의미의 결과는 기존 Revision을 유지한다. 새로 검증된 근거나 applicability가 필요한 경우에는 별도 support/적용성 이력을 추가한다. 최초 `generation_origin`, 추론 유형, 원래 전제 Revision과 옛 근거는 보존한다. `current_support_record_id`, `current_support_signature`, `current_transitive_*`는 현재 유효한 경로를 나타내며 최초 생성 근거와 구분한다.

## 2. 준비와 명시적 시작

새 전파 쓰기에는 검토된 schema0016이 설치된 DB와 해당 자료의 Artifact Store가 필요하다. 아래 명령은 migration을 실행하지 않는다. 보존 DB의 schema0013·0014·0015를 읽기 전용으로 열 수 있다는 호환성은 새 worker 쓰기 권한이나 자동 upgrade를 의미하지 않는다.

**아래 대문자 식별자는 모두 설명용 placeholder다. 그대로 실행하지 말고 실제 출력값으로 바꾼다.**

| Placeholder | 넣을 값 |
|---|---|
| `RUN_UUID` | 이번 prepare에 사용할 새 UUIDv7. 이 값이 run ID가 됨 |
| `ROOT_RECORD_UUID` | 이미 반영된 `k_compilation_records.record_id`. KNode ID와 다름 |
| `DATA_SHA256` | 이번 실행에서 사용할 등록된 불변 Data ID |
| `WIKI_UUID` | 기존 Wiki DB projection의 Wiki ID |
| `VERSION_UUID` | 선택적으로 고정할 등록 Data version ID |
| `SCOPE_FINGERPRINT` | prepare가 반환한 정확한 `request_fingerprint` |
| `TASK_UUID` | show/worker 응답에 나온 task ID |
| `DATABASE_NAME` | 이미 구성된 연결에서 선택할 실제 DB 이름 |
| `HOST_WORK_DIRECTORY` | repository 안의 전용 작업 폴더 절대 경로 |
| `COMPOSE_PROJECT`, `ARTIFACT_VOLUME` | 실제 서버 network/credential 구성의 Compose project와 원본 artifact volume 이름 |

다음 `palim` 예시는 DB·Artifact Store·작업 폴더가 연결된 Docker 앱 내부 명령이다. 작업 폴더는 `/results`로 mount한 것을 가정한다.

```text
palim propagation prepare --request-id RUN_UUID --record-id ROOT_RECORD_UUID --allow-data-id DATA_SHA256 --wiki-id WIKI_UUID --directory /results --database-name DATABASE_NAME --json
```

Record/Data/Wiki 옵션은 여러 번 지정할 수 있다. `--allow-data-id`를 생략하면 시작 Record의 원문 근거에서 범위를 정하고, `--wiki-id`를 생략하면 허용 Data의 페이지가 있는 기존 Wiki를 선택한다. 실제 선택은 반환된 manifest에서 확인한다. 자료 버전은 `--data-version-id VERSION_UUID`와 `--data-version-mode current|pinned`로 지정할 수 있다. 생략된 버전 선택은 현재 등록 상태를 바탕으로 manifest에 고정된다.

기본 정책은 허용 범위의 서로 다른 현재 K 두 개를 문맥으로 N2E/K2K discovery도 수행한다. 기존의 정확한 의존 관계 유지보수만 원하면 prepare에 **`--maintenance-only`**를 추가한다. 이 옵션은 discovery를 제외하는 명시적 범위 선택이며, 미처리 의무를 완료 처리하는 크기 제한이 아니다. 해당 범위의 Wiki 갱신은 유지된다.

prepare는 `prepared` 상태와 `manifest_file`, `request_fingerprint`를 반환한다. manifest에는 선택 source의 hash/크기/종류, 자료 버전, Wiki import와 모델 정책이 포함된다. 본문을 전달할 때에는 뒤에서 생성되는 실제 요청 JSON과 이미지 목록도 확인한다. 선택 Wiki의 기존 topic key/title/scope는 모델 문맥에 포함될 수 있다.

```text
palim propagation start RUN_UUID --confirm SCOPE_FINGERPRINT --actor-ref ACTOR_REFERENCE --directory /results --database-name DATABASE_NAME --json
```

`ACTOR_REFERENCE`도 실제 사용자/운영자 참조로 바꿀 placeholder다. `--confirm`에는 prepare의 `request_fingerprint`를 넣는다. manifest 파일 bytes를 별도로 hash한 값으로 대체하지 않는다. 같은 ID의 다른 범위는 충돌로 거부하며, source/Wiki/version 범위를 바꿀 때는 새 run을 준비·확인한다. 시작 확인은 후보 K의 의미적 진실을 승인하는 행위와 구분된다.

## 3. Windows host에서 실행

host controller는 repository의 `compose.yaml`과 기존 project credential mount를 사용한다. 매 CLI 호출은 `docker compose run --rm --no-deps`이며, 작업 폴더는 쓰기 가능하게, repository와 지정한 원본 Artifact Store는 읽기 전용으로 mount한다. host는 DB DSN/password 파일을 직접 읽지 않는다.

```text
python -X utf8 -B tools/run_propagation.py --run-id RUN_UUID --directory HOST_WORK_DIRECTORY --project COMPOSE_PROJECT --database-name DATABASE_NAME --artifact-volume ARTIFACT_VOLUME --app-image palimpsest-propagation:0.18.0 --allow-model-calls
```

`python`은 실제 설치 경로로 바꾼다. 현재 모델 adapter는 [사용자 로컬 GLM](../implementation/MODEL_PROVIDER.md)을 사용하며 host controller는 인증정보를 읽지 않는다.

`--allow-model-calls`가 없으면 새 provider 프로세스를 시작하지 않고 검토 가능한 요청에서 멈춘다. 정확한 기존 response가 있으면 요청·receipt 검증 후 재사용할 수 있다. 이 flag와 run 시작 확인은 별개이며, 실제 원문의 외부 전송에는 해당 범위의 사용자 승인이 필요하다.

`--once`는 한 task 처리 차례만 진행하고 부분 결과를 반환한다. 이 옵션 때문에 run을 수렴·완료로 표시하지 않는다. `--lease-seconds` 기본값은 180초이고 host controller에서는 최소 60초다. 모델 실행 중 약 30초마다 lease를 갱신하며, 갱신 실패·중단·token 교체를 감지하면 자신이 시작한 모델 worker와 그 자식 프로세스만 종료한다. 오래된 token으로 accept를 이어가지 않는다.

host 작업 기록은 작업 폴더의 형제 경로인 `HOST_WORK_DIRECTORY-controller/<attempt>/`에 쌓인다. 명령·출력·종료 상태와 최종 부분/완료 결과를 보존하고, 명령 인자의 lease token은 hash로 기록한다. 모델 request/response/failure는 `/results`와 대응하는 실제 작업 폴더에 보존한다. 디렉터리를 지우거나 응답 파일을 덮어써서 재시도하지 않는다.

controller 종료 코드 0은 실제 run 완료 응답을 받은 경우다. 준비·중단·보류·`--once` 등 정상적인 부분 종료는 7이며, 설정·무결성·실행 오류는 해당 오류 코드로 끝난다. 개별 task의 `task_completed`와 run의 `completed`는 다르다.

## 4. 상태 확인과 제어

```text
palim propagation show RUN_UUID --directory /results --database-name DATABASE_NAME --json
palim propagation pause RUN_UUID --reason "검토를 위해 중단" --actor-ref ACTOR_REFERENCE --directory /results --database-name DATABASE_NAME --json
palim propagation resume RUN_UUID --reason "동일 범위 작업 재개" --actor-ref ACTOR_REFERENCE --directory /results --database-name DATABASE_NAME --json
palim propagation retry TASK_UUID --reason "보류 이유를 검토한 후 다시 판정 요청" --directory /results --database-name DATABASE_NAME --json
palim propagation cancel RUN_UUID --reason "이 실행을 종료" --actor-ref ACTOR_REFERENCE --directory /results --database-name DATABASE_NAME --json
```

`show`에서 scope/policy, 작업별 상태·오류·결과, 원인 참조와 event 이력을 확인한다. 모델을 붙이기 전 요청을 검토하려면 host controller에서 `--allow-model-calls`를 생략하거나 `propagation next`를 사용할 수 있다.

```text
palim propagation next RUN_UUID --lease-seconds 180 --directory /results --database-name DATABASE_NAME --json
```

이 호출이 task를 claim했다면 응답의 task/token과 요청 파일을 보존한다. 수동 worker 연동용 `advance`, `accept`, `renew`, `call-failed`도 있으며 host controller가 이 명령들을 사용한다. 유효한 token은 같은 task의 해당 처리 차례에만 사용한다.

pause/cancel은 durable run 상태와 lease epoch를 바꾼다. 이미 반영된 K·Wiki·Revision은 이력으로 남는다. pause 후 resume은 같은 범위의 진행을 재개하지만 개별 의미 판정 보류를 자동 해제하지 않는다. 필요한 task에는 이유를 담은 명시적 retry를 사용한다. 취소된 run은 재개 대상이 아니며 새 실행이 필요하다.

host의 Ctrl+C는 소유한 모델 프로세스를 정리하고 pause를 기록하려고 시도한다. DB에 접근할 수 없어 pause를 확인하지 못하면 `pause_not_confirmed` 부분 상태를 남긴다. 이후 `show`로 실제 run 상태를 확인한다.

## 5. 실패와 재시도

| 상태/오류 | 처리 |
|---|---|
| `retry_wait` | 기록된 호출 실패의 backoff 또는 현재 처리 대기. 완료가 아님 |
| `propagation_transport_anomaly` | 같은 task/phase의 연속 호출 실패가 3회에 도달해 보류. 원인 확인 후 명시적 retry 필요 |
| `needs_human`, `wiki_refresh_needs_review` | 의미 검토 미해결. 자동 transport 재시도와 구분하고 이유를 담은 retry로 새 검토 |
| `wiki_refresh_failed`, `knowledge_invalid_response` | 실제 보존 응답의 구조·검증 문제를 확인한 뒤 명시적 재검토 |
| `propagation_claim_lost` | 중단·만료·다른 worker의 claim. 이전 token으로 반영하지 않고 현재 상태 확인 |
| `propagation_new_scope_required` | source/version/Wiki head 또는 고정 문맥이 변경됨. 기존 확인을 확장하지 말고 새 run 준비 |
| `propagation_cached_exchange_invalid` | 기존 파일과 정확한 요청/receipt가 불일치. 덮어쓰거나 자동 재호출하지 않고 보존 파일 확인 |

연속 3회 보류는 **호출 실패에 대한 운영 장치**다. 의미적 전파 깊이·노드 수·토큰·비용을 제한해 성공을 선언하는 규칙이 아니다. 성공한 단계나 명시적인 retry가 실패 streak의 경계를 만든다. 실패의 원인·시도·이전 response/failure와 미해결 task는 남으며 보류는 완료로 계산하지 않는다.

현재 ready queue가 비어 있어도 leased/retry/blocked 작업이나 미처리 outbox가 남으면 완료가 아니다. 종료 receipt는 고정 root와 실제로 발생한 모든 causal descendant에 대해 확인한 의무, 초기/완료 watermark와 완료 범위를 기록한다.

## 5.1. 의미 변화 기준 — 새 기본값 0.18

새 run에는 `repeated_outcome=observe`, `materiality_policy=accepted-state-materiality-v1`을 동결한다. A→B→A/A→B→C→A 등 반복이 발견되면 `semantic_return_observed`를 한 번 기록하고 실제 효과의 dispatch를 계속한다. 반복만으로 자동 보류·확인 요구·기각·reuse·승인을 만들지 않는다. `show`의 `anomalies`에 있는 이 event는 advisory이며 미완료 task가 아니다.

Generator/독립 Validator는 현재 accepted snapshot을 기준으로 의미 변화와 근거를 평가한다. nonmaterial이면 기존 Revision을 유지하고 새 semantic branch를 만들지 않는다. 직전에 무시한 candidate를 다음 비교 기준으로 이동시키지 않아 작은 변화의 누적을 놓치지 않는다. discovery에서도 같은 의미는 current usable K의 재사용이며 새 FP만으로 신규 K가 되지 않는다. 새 evidence가 후보를 지지한다는 사실만으로 기존 accepted claim의 근거까지 유효하다고 간주하지 않는다.

숫자·문자·embedding 거리에 공통 epsilon을 적용하지 않는다. 근거에 정밀도나 허용 오차가 없으면 임의로 만들지 않는다. 작은 극성·단위·범위·조건·절차 변경도 material일 수 있다. 불확실한 materiality는 null/보류이며 false가 아니다. 상충하는 사실을 평균하거나 다른 실험 기록을 지워 수렴을 만들지 않는다.

semantic branch가 멈춰도 변경된 current support와 정확한 소비자들의 maintenance, 다른 부모의 의무, Wiki 검증은 남을 수 있다. 이미 현재인 accepted 원래 derivation은 추가 LLM 재검증 없이 그 exact support Record로 coverage를 남긴다. N2E의 applicability true↔false는 Record disposition이 no_material_delta여도 material effect으로 처리한다. 로그의 `semantic_revision_change`, `applicability_change`, `maintenance`를 구분한다. 현재 K2K는 node-premise 방식이므로 아직 없는 EffectiveEdge 전제 소비자를 생성했다고 해석하지 않는다.

## 5.2. 과거 frozen halt policy의 재현 — 0.17

이 절은 이미0.17 policy로 준비된 이전 run에만 적용한다. 신규 run의 기본값이 아니다. 해당 run은 `semantic-return-under-unchanged-premises-v1`에서 같은 전제의 정규화된 결과 복귀를 후속 dispatch 전에 `needs_human`으로 멈춘다. 실제 premise/support/자료 버전/profile 또는 predecessor가 달라지면 같은 반복 구간으로 합치지 않는다. 이전 policy와 진단을 새 advisory였던 것처럼 재작성하지 않으며, 새 기본 정책을 사용할 때는 새 run을 준비한다.

비교 catalog는 바뀌었을 수 있으므로 그 hash와 변경 여부를 진단에 따로 남긴다. 이는 같은 전체 prompt의 반복이나 결론의 거짓을 입증하는 검사가 아니다. 이 진단 key를 모델 실행 cache·기각 fingerprint로 재사용하지 않는다. 같은 내용의 반복/reuse만으로는 material cycle을 만들지 않고, old profile에 근거 binding이 없으면 동일 근거라고 추정하지 않는다. 이전 run의 policy를 자동 변경하지 않는다.

이미 검증·반영된 K/Revision/적용성/Record/outbox는 유지한다. 진단은 새로운 epistemic rejection이나 자동 rollback이 아니다. 남은 전파와 Wiki 게시가 중단되며 `show`의 `anomalies`에 exact 전이·근거·입력/catalog/profile hash와 `witness_sha256`이 표시된다. 단순 `resume`이나 다른 blocked task의 `retry`로 확인을 우회할 수 없다.

```text
palim propagation show RUN_UUID --directory WORK_DIRECTORY --database-name TEST_DATABASE --json
palim propagation retry TASK_UUID --acknowledge-anomaly WITNESS_SHA --actor-ref OPERATOR --reason "이 정확한 복귀 진단을 검토한 이유" --directory WORK_DIRECTORY --database-name TEST_DATABASE --json
```

대문자는 설명용 placeholder다. `WITNESS_SHA`는 방금 검토한 실제 진단 값이어야 한다. 재시도와 확인 이력은 같은 DB transaction에서 저장한다. 현재 target/premise/support/자료 버전/scope가 바뀌었으면 `propagation_anomaly_scope_changed`로 거절하고 새 범위를 준비해야 한다. 확인은 그 전이에만 적용되며 다음 복귀를 영구 허용하지 않는다. 확인 없이 취소할 수 있지만 취소와 미처리 작업은 완료로 표시하지 않는다.

## 6. Wiki 재생성과 publication checkpoint

Knowledge 처리가 끝난 뒤 관련된 변경을 Wiki별로 모은다. 새 K는 아직 기존 Wiki K 링크가 없어도 그 실제 source provenance를 통해 선택한 기존 페이지를 갱신할 수 있다. material revision의 저장된 impact와 current-support 변경은 실제 receipt로 구분한다. 역사적 링크만 있는 경우는 `no_current_page_effect`로 남긴다.

페이지 생성은 기존 source execution의 **전체 I와 소유 media**를 사용한다. K 변경 ID는 재검토 문맥이며 근거를 대신하지 않는다. source-only 본문에 새 K2K 결론을 섞거나 원본 D를 대체 근거로 가져오지 않는다. 기존 topic key/title/scope에는 다른 source의 설명이 포함될 수 있으므로 실제 전송 요청에서 그 metadata도 확인한다.

1. 고정한 DB import를 전용 작업 폴더에 복원하고, 현재 source 페이지·원문 I·KRevision/support signature·Data-series head를 확인한다.
2. 각 source 페이지를 순서대로 Generator에 전달한다. 모든 I의 사용/문맥/미선택/보류 결과와 실제 전달 receipt를 남긴다.
3. 별도의 Validator가 전체 제안·근거·주제를 검토한다. Generator와 같은 provider reference는 독립 검증으로 인정하지 않는다.
4. 허용된 판정만 파일 catalog에 반영하고, source별 topic contribution을 갱신한다. 같은 body는 snapshot을 재사용할 수 있고, 달라진 body는 같은 page ID에 새 snapshot을 만든다.
5. 대상 페이지가 모두 검증된 뒤 별도의 원자적 Wiki DB sync로 import/head를 선택한다. 오래된 snapshot·catalog·검토 표시는 보존한다.

파일 catalog 반영과 DB import는 서로 다른 durable checkpoint다. 파일 반영 뒤 중단되면 보존된 exchange와 commit receipt로 이어가며, DB commit 응답을 잃으면 실제 import의 head·archive SHA·결과를 확인해 복구한다. 로컬 `completed` cache만으로 성공을 인정하지 않는다.

파일 stage/decide는 유효한 publication claim 아래 실행한다. DB sync는 같은 transaction에서 K 상태·claim·Data-series head를 고정하고, 모든 projection 쓰기와 deferred constraint 검사를 마친 직후 lease를 다시 확인한 다음 commit한다. 반영 중 만료되면 새 head와 projection 쓰기를 함께 rollback한다. 모델 호출 동안 이 잠금을 유지하지 않는다.

전송 실패의 재시도는 새 page-job/request 경로를 만든다. Validator만 실패했다면 정확히 같은 이미 전달된 Generator exchange를 로컬에서 재사용하고 새 독립 Validator를 호출한다. 이 재사용을 새로운 Generator 호출로 집계하지 않는다. 이전 실패와 provider reference, `reuse_generator_from` 관계를 보존한다.

의미 보류와 보존된 구조 실패는 사용자가 task retry를 요청해야 새 page-job으로 열린다. 이전 작업이 feedback parent가 되고 사용자의 이유는 untrusted review notes로 제공된다. source·profile·현재 head가 달라진 경우에는 이 재시도로 범위를 넓힐 수 없다. 파일의 재검토 준비와 queue 재개는 별도 checkpoint이므로 중단 시 `show`와 보존된 요청 이력을 확인한다.

## 7. 현재 완료 경계

이 worker는 새 D/I 생성, D2I 복구, 사용자 요청 없는 D2K, 기존 query 답변 재작성, semantic index의 자동 재구축, 공개 웹 게시를 수행하지 않는다. Wiki는 비canonical source projection이며 W/P/B 확정이나 실제 사용자 Decision 생성을 대신하지 않는다.

현재 discovery의 모델 입력은 허용 범위의 현재 K 두 개다. 정확한 기존 의존 관계는 별도로 열거하지만, 이것이 가능한 모든 고차 조합의 추론을 발견한다는 보장은 아니다. 구조화된 출력·독립 검증과 실제 모델의 의미 품질도 구분한다.

정확한 반복은 관찰할 수 있지만 신규 기본 정책에서는 종료 조건이 아니다. 독립 nonmaterial 판정으로 semantic frontier를 줄이고 실제 의무가 소진되어야 완료한다. 모든 LLM 과정의 수렴이나 damping을 보장하지 않으며 Contradict 관계가 그 보장을 대신하지 않는다. 현재 실제 N2E predicate는 supports이고 Contradict 확장은 별도다. **100,001개 규모의 실제 처리 검증**과 전체 T07은 후속이다. 장기 비수렴을 비용/깊이 성공 cutoff로 감추지 않는다. [의존 관계 paging 후속안](../../progress/T18_dependency_paging_proposal.md)은 아직 제안이다.

구현은 [전파 queue](../../src/palimpsest/propagation_queue.py), [전파 Runtime](../../src/palimpsest/propagation_runtime.py), [Wiki refresh](../../src/palimpsest/wiki_refresh.py), [host controller](../../tools/run_propagation.py)로 나뉜다. 모델 실행은 기존 [구조화 호출 worker](../../tools/run_knowledge_model.py)를 재사용한다.
