# 자료 버전·공유 원문 저장·Knowledge 버전 문맥

2026-09-13. 앱 `0.12.0`과 additive `0013_data_versions`의 구현 계약이다. 사용자 승인·적용 대상·실제 검증은 [실행 계획](../../progress/T07_versioned_code_execplan.md)에 기록한다. 이 문서는 특정 DB의 설치 완료나 실제 모델 품질 평가를 대신하지 않는다. 기반 설계는 [자료 버전·공유 저장 제안](../implementation/DATA_VERSION_STORAGE_PROPOSAL.md), 원문 표현은 [코드 snapshot 계약](CODEBASE_SNAPSHOT.md), 추론은 [K2K Runtime](K2K_RUNTIME.md)을 따른다.

## D와 자료 버전의 관계

`data_id`는 계속 **원본 전체 bytes의 SHA-256**이다. 같은 자료의 내용이 바뀌면 다른 D가 되고, 이전 D/I/해시·source 실행·KRevision은 그대로 남는다. `data_series`는 사용자가 명시적으로 만든 안정적인 관리 ID이며, `data_versions`의 불변 행이 그 자료의 각 시점에 해당하는 exact D를 가리킨다. 폐기된 public Source domain을 다시 만드는 구조가 아니다.

| 객체 | 저장 내용 |
|---|---|
| Data | 기존 raw SHA-256 ID, media type, 원문 크기, 논리 Artifact Store 주소 |
| Data series | UUIDv7 `series_id`, 이름, 생성 actor, 현재 `head_version_id` |
| Data version | UUIDv7 `version_id`, `series_id`, `parent_version_id`, `data_id`, series 내 `version_number`, 제목·변경 설명·actor·시각 |
| Version request | UUIDv7 요청 ID, 입력 fingerprint와 원래 payload, actor, 생성/no-op 결과 및 원래 결과 snapshot |

series의 이름·생성 actor와 version 행은 불변이며 head만 직접 후속 version으로 이동한다. 같은 이름으로 별도 series를 생성할 수 있다. 이름이나 경로가 같다는 이유로 두 이력을 자동 병합하지 않는다.

Version은 이미 등록된 Data만 참조한다. 새 version 반영 전에 해당 D의 보존 bytes를 Artifact Store에서 검증한다. Version을 추가하는 명령은 D2I나 모델 실행을 호출하지 않는다.

## 변경·no-op·되돌림·동시 요청

`append`는 조회한 정확한 head를 `expected_head`로 받는다. 빈 series의 첫 version만 `expected_head=None`을 사용한다. 요청별 transaction 잠금 후 series 행을 잠그고 actor와 head를 확인한다. 새 version·head·요청 결과는 하나의 transaction에서 반영된다.

- **내용 변경:** head가 D A이고 새 내용이 D B이면 새 version을 만든다. 번호는 series별로 1부터 연속 증가한다.
- **같은 head 내용:** 새 D가 head의 D와 같으면 `outcome=no_op`이다. 새 version이나 I는 만들지 않는다. 기존 version의 제목·설명도 바꾸지 않으며, 이번 확인 요청의 제목·설명은 request payload에 보존한다.
- **A→B→A:** D A의 bytes를 재사용하는 새 version을 만든다. 마지막 version의 parent는 B version이다. head를 과거 version으로 직접 되돌려 이력을 없애지 않는다.
- **stale head:** `data_version_head_changed`와 `series_id`, `expected_head`, `current_head`를 반환한다. 해당 갱신의 version·head·성공 요청 결과는 반영하지 않는다.
- **동일 요청 재전송:** 입력 fingerprint·원래 payload·actor가 같으면 원래 결과에 `replayed=true`를 붙여 반환한다. 이후 head가 바뀌어도 원래 결과의 version을 반환한다. 같은 요청 ID의 다른 입력은 `idempotency_conflict`, 다른 actor의 요청 재사용이나 series 변경은 `permission_denied`다.

동일 head를 기준으로 서로 다른 두 요청이 경합하면 하나만 그 head의 다음 version을 만들 수 있다. 저장 오류나 요청 결과 기록 전 실패는 version과 head 변경도 함께 rollback한다. 실패한 transaction을 성공한 no-op으로 표시하지 않는다.

## 공유 저장의 실제 범위

공유 저장은 D의 정체성과 별개인 **물리적 표현**이다. `segmented-artifact-v1` manifest는 순서가 있는 blob SHA-256·길이 목록과 원래 D의 SHA-256·전체 길이를 가진다. blob은 내용 주소로 공유하고, 읽을 때 각 blob과 조립한 전체 bytes를 모두 검사한다. 저장 manifest의 hash를 `data_id`로 대체하지 않는다.

현재 자동 segment 계획은 검증된 **코드 Markdown dossier**에서 만든다. 원래 파일 본문과 그 사이의 wrapper/manifest bytes 경계를 나누므로, 바뀌지 않은 파일 본문은 다른 snapshot에서도 같은 blob을 사용할 수 있다. wrapper bytes도 모두 보존한다. 새 native code parser, 파일별 canonical D/I, AST 기반 의미 추출을 구현한 것은 아니다.

기존 raw 저장도 계속 읽을 수 있다. raw와 segmented 표현이 함께 존재하면 둘 다 검증한다. 존재하는 manifest나 blob이 손상됐다고 다른 표현을 조용히 사용해 손상을 숨기지 않는다. manifest는 필요한 blob이 완전히 보존·검증된 뒤 게시하며, 중단된 요청은 원래 요청 정보로 복구한다. 이전 raw·blob을 자동 삭제하거나 GC하지 않는다.

`ArtifactStore.read(data_id, byte_size)`와 `verify`는 저장 표현에 관계없이 원래 D의 정확한 bytes/hash 계약을 유지한다. version history의 parent를 따라 patch를 차례대로 적용해야만 D를 복원하는 방식은 아니다. delta compression·content-defined chunking·전역 GC는 이번 범위가 아니다.

`storage_stats`는 `storage`, `logical_bytes`, `manifest_bytes`, `chunk_count`, `unique_blob_count`, `unique_blob_bytes` 등을 반환하며 raw가 있으면 `raw_bytes`도 표시한다. `unique_blob_bytes`는 **해당 D가 참조하는 고유 blob의 합**이다. 여러 version의 값을 더하면 공유 blob을 중복 계산할 수 있으므로 전역 사용량이나 증분 저장량으로 해석하지 않는다. 게시 시 `new_blob_bytes`는 그 호출에서 새로 게시한 blob payload이고, 초기 전환 비용·manifest·기존 raw·파일시스템 할당량을 구분해 보고해야 한다.

## 실행에 고정되는 version 문맥

I2K/N2E/K2K의 `prepare`는 선택적으로 `data_version_ids`와 `data_version_mode`를 받는다. 버전 ID를 제공하면 정확한 불변 version 행을 `input_snapshot.data_versions`에 저장하고 `input_snapshot.data_version_mode`에 mode를 고정한다. 원래 행의 `created_at`·제목·설명·parent도 포함하지만 가변 head 값은 이 snapshot에 넣지 않는다.

`compiler_runtime.k_execution_data_versions(execution_id, version_id)`는 모델 실행 전에 이 문맥을 typed FK로 연결한다. SQL은 선언된 version과 실제 행 전체의 일치, 모든 선언 ID의 연결, 실제 입력 출처와의 관계를 검사한다. 연결된 ID를 나중에 latest version으로 치환하거나 완료된 실행에 새로운 version을 덧붙이지 않는다.

| Mode | 의미 |
|---|---|
| `current` | series당 한 version만 선택한다. 준비·stage·canonical 반영 때 head가 해당 version인지 확인한다. series head는 잠금 아래 다시 확인한다. |
| `pinned` | 명시적으로 고른 과거·비교 범위를 분석한다. 같은 series의 A/B version을 함께 선택할 수 있다. 이후 head 이동이 이 요청을 현재판 분석으로 바꾸지 않는다. |

자료 head 이동은 K semantic Revision 변경이 아니며 `knowledge_state` counter를 갱신하지 않는다. 따라서 K read-set 검사와 별도로 series head 검사가 필요하다. Runtime은 Knowledge 상태 잠금 다음에 series ID 순서로 head 공유 잠금을 잡는다. SQL도 새 current-mode context/link를 commit할 때 head를 확인하지만, 과거 immutable context를 나중의 무관한 UPDATE에서 다시 검사하지 않는다. canonical 반영 시의 freshness 검사는 계속 Runtime이 수행한다.

이미 성공한 요청·같은 Validator receipt의 재전송은 저장 결과를 재생한다. 이를 새로운 current-mode commit으로 취급해 오늘의 head를 과거 결과에 주입하지 않는다.

Generator/Validator receipt에는 순서까지 같은 `delivered_data_version_ids`가 필요하다. I2K는 정확한 I 전달 목록, N2E/K2K는 정확한 KRevision 전달 목록도 유지한다. version 문맥을 포함한 prompt/schema/input/output hash 및 독립 Validator 세션을 검사한다. 이름·변경 설명은 untrusted metadata이며, 이름이 “승인됨”이라고 해서 배포·실험 수행·사용자 권위를 입증하지 않는다.

## 실제 근거와 실행 문맥을 구분하는 규칙

I2K의 version 문맥은 **실제로 입력한 모든 source Data**를 포함해야 한다. 선택하지 않은 추가 Data의 version을 끼워 넣을 수 없다. N2E/K2K에서는 각 입력 KRevision에 대해 선택한 version Data만으로 성립하는 **완전한 accepted support 경로가 하나 이상** 있어야 한다. 모든 과거 grounding을 필수 근거로 합산하지 않는다.

예를 들어 일반 K가 처음 A+B의 조합으로 승인됐다면 B만으로는 그 경로가 충분하지 않다. 이후 독립 I2K 검증이 같은 주장 전체를 B의 I만으로 재사용했다면, 현재 B를 선택한 작업에서 그 별도 경로를 사용할 수 있다. 정확한 B grounding 행이 이미 있어 새 grounding이 생성되지 않은 경우에도 `k_information_review_records`가 해당 재사용 Record의 실제 I를 보존한다. 이때 기존 origin과 A의 이력은 그대로 남는다.

SQL 함수 `canonical_store.k_revision_supported_by_version_data(revision, allowed_data, seen)`는 다음을 검사한다.

- Source scope K는 의미상 소유 `source_data_id`가 선택 범위에 있어야 한다.
- I2K는 exact 결과 Revision을 낸 terminal Record별 actual I review-record 연결을 사용한다. 이전 profile에 그 연결이 없으면 해당 Record가 만든 직접 I grounding을 사용한다. 한 경로의 Data 집합이 비어 있지 않고 선택 범위 안에 있어야 한다.
- K2K는 actual derivation별 모든 전제가 같은 조건을 재귀적으로 만족해야 한다. 해당 도출 실행에 version 문맥이 있으면 그 version Data도 선택 범위 안에 있어야 한다. 순환은 `seen`으로 차단하며 임의의 depth 성공 종료 cap은 없다.
- 선택된 추가 version Data도 실제 입력 K의 원문 계보에 있어야 한다.

이 함수는 이미 검증된 Record의 구조와 근거 범위를 확인한다. 새 의미적 진실성 판정이나 원문 모든 내용의 완전성 평가를 대신하지 않는다.

`origin_data_versions`는 최초 생성 Record가 실행된 **version 문맥**이다. 그 문맥의 모든 Data가 해당 K의 직접 근거였다는 뜻이 아니다. `data_version_supports`도 후속 accepted/reused Record와 그 실행 version 문맥을 보존한다. 실제로 기여한 원문은 exact I grounding/review-record, 파생 결론은 actual K premise 연결에서 확인한다.

## 조회·재사용·현재성

`knowledge show`는 실행의 고정 `data_versions`/mode와 별도로 현재 head를 표시한다. `knowledge graph`의 K에는 불변 `origin_data_versions`, 후속 `data_version_supports`, 현재 head를 반영한 `source_version_status=current|historical|untracked`와 head 목록이 있다.

`source_version_status=current`는 해당 K에 현재 head와 맞는 지원 문맥이 있다는 뜻이다. 의미적 진실·배포 상태·전제 현재성의 보증은 아니다. 자료 head 이동만으로 기존 KRevision이나 I를 수정하지 않는다. K2K의 `current_applicability`와 전제 재검증 필요 여부는 별도의 축이다.

기존 실행은 자동으로 version에 소급 결속하지 않는다. exact version 문맥이 없던 K는 `origin_data_versions=[]`와 `untracked`를 유지할 수 있다. 이후 같은 K가 새 version 문맥에서 재사용되면 후속 support만 추가한다. 이미 version support가 있는 전제를 새 N2E/K2K에 사용하는 경우 version 문맥을 생략할 수 없다.

`knowledge graph --data-version-id`는 해당 version의 exact D를 선택하고 version metadata를 함께 반환한다. 그 시점에 존재했던 전체 KGraph를 복원하는 time-travel checkpoint 명령은 아니다. 같은 D를 참조하는 이후 지원 이력·현재 head 표시가 함께 보일 수 있으므로 각 origin/support의 실제 version을 확인한다.

같은 D와 같은 완료 D2I/profile의 I는 재사용할 수 있다. A→B→A에서도 A의 기존 I를 그대로 사용해 새로운 V3 실행 문맥을 남길 수 있다. 다른 D의 I를 본문이 같다는 이유로 하나의 I ID로 합치지 않는다. 같은 의미의 K 재사용은 기존 KRevision과 최초 origin을 유지하고 새 Record/support를 더한다.

## CLI

아래는 이미 올바른 DB와 Artifact Store가 연결된 Linux 앱 내부 명령 형식이다. placeholder는 실제 SHA-256·UUIDv7·경로로 바꾼다. version 추가에 앞서 Data 등록을 별도로 완료한다.

```text
palim code snapshot /source /results/capture-v1 --json
palim data import-code-snapshot /results/capture-v1 --request-id <import-request> --json
palim data storage-stats <data-sha256> --json

palim data series-create "Maintained code snapshot" --request-id <create-request> --json
palim data series-append <series-id> <first-data-sha256> --request-id <append-request-1> --title "V1" --json
palim data series-show <series-id> --json
palim data series-append <series-id> <next-data-sha256> --request-id <append-request-2> --expected-head <version-1-id> --message "Changed source" --json
palim data series-history <series-id> --json
palim data version <version-id> --json
palim data compare-code-versions <before-version-id> <after-version-id> --json
palim data restore-code-version <version-id> <empty-directory> --json

palim knowledge prepare --operation i2k --data-id <data-sha256> --request-id <compile-request> --input /results/source-input.json --data-version-id <version-id> --json
palim knowledge prepare --operation k2k --data-id <data-sha256> --request-id <inference-request> --input /results/premises.json --data-version-id <version-id> --data-version-mode current --json
palim knowledge graph --data-version-id <version-id> --json
```

`--data-version-id`는 반복 가능하다. 과거 A/B 비교는 두 version ID와 `--data-version-mode pinned`를 명시한다. `knowledge prepare`는 모델 호출이 아니라 정확한 입력·profile·요청을 고정하는 단계이며, 이후 실제 전달·stage·독립 validation·decide 단계를 따라야 한다.

일반 duplicate import의 거부는 계속 유지한다. 이미 등록된 D를 version에 연결하는 작업은 `series-append`이며, duplicate import를 새로운 D나 새로운 acquisition으로 바꾸지 않는다.

## Python API와 diff

`DataVersions(dsn, store)`는 `create(name, request_id=None, actor_ref=...)`, `append(series_id, data_id, request_id, expected_head, message=..., title=..., actor_ref=...)`, `show`, `version`, `history`를 제공한다. create/show/version/history에는 원문 파일 읽기가 필요하지 않다. `immutable_versions(conn, ids)`는 caller transaction 안에서 정확한 version 행을 입력 순서대로 반환하고 중복 ID를 거부한다. current-head 정책과 잠금은 caller가 담당한다.

현재 코드 snapshot diff API는 `code_snapshot.compare(before_bytes, after_bytes)`다. 각 version이 가리키는 Data를 Artifact Store에서 검증해 읽은 뒤 비교한다.

```python
from palimpsest.code_snapshot import compare

before = versions.version(before_version_id)
after = versions.version(after_version_id)
left = repository.get_data(before['data_id'])
right = repository.get_data(after['data_id'])
changes = compare(store.read(left['data_id'], left['byte_size']),
                  store.read(right['data_id'], right['byte_size']))
```

결과는 `before_data_id`, `after_data_id`, `scope=captured_snapshot_members`, `added`, `removed`, `changed`, `unchanged`다. path와 원래 file hash/size를 비교한다. rename을 추정하거나 캡처 범위 밖의 파일 삭제, file mode 변화, 실제 배포 변경을 판정하지 않는다. 비교는 조회 결과이며 D/I/K의 변경이나 재파싱을 일으키지 않는다. `data compare-code-versions`는 이 조회를 exact version ID에 연결하고, `data restore-code-version`은 비어 있는 폴더로 해당 버전 파일을 복원한다. 두 명령 모두 sidecar나 현재 checkout 없이 보존된 원문 bytes를 검증하며 일반 Markdown을 코드 snapshot으로 간주하지 않는다.

## 검사와 실행 결과

- [Data version PG tests](../../tests/app/test_data_versions.py): no-op/revert, 원래 요청 replay, actor, CAS 경합, 원문 검증 실패, atomic rollback, history/parent 무결성 및 대체 support 경로.
- [Versioned Knowledge PG tests](../../tests/app/test_versioned_knowledge.py): exact I2K→K→K2K/N2E version 연결, head 변경 거부와 pinned 역사 입력, version 전달·schema 검증, 최초 origin과 V3 재사용 support, 성공 receipt replay.
- [공유 저장 tests](../../tests/app/test_segmented_artifact_store.py): 실제 Linux CAS read/hash·경로·중단·동시성 검사. 모델 품질 검사가 아니다.

Fixture DB의 `knowledge_state`는 모든 테스트가 공유한다. 서로 다른 synthetic Data를 사용해도 두 application suite를 동시에 실행하면 정상 CAS 보호가 실패를 반환할 수 있으므로 한 번에 하나의 suite만 실행한다. 최초 동시 실행의 실패를 지우지 않고 [간섭 기록](../../output/t12-versioned-code/focused-tests-interference.json)과 전체 실행 로그에 보존했다. 최종 결과와 실제 코드 변경 실험은 [실행 계획](../../progress/T07_versioned_code_execplan.md)에서 fixture·provider·보존 검사를 구분해 확인한다.
