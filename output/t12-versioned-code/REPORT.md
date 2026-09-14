# 공유 원문 저장·자료 버전·실제 코드 K2K 검증

2026-09-13. 승인된 자료 버전 기능을 Python/Docker 앱0.12.0과 additive0013에 구현했다. 전체202파일 snapshot의 물리 저장을 측정하고, 별도로 실제 두 모듈 전체를 담은 코드 사본 V1/V2를 D→I→I2K→N2E→K2K로 실행했다. 의미 검토의 미완료와 실제 저장·provenance 검증을 구분한다.

## “V1로 되돌린다”의 대상

대상은 **실험용 자료 시리즈 `Palimpsest model contract controlled copies`**다. 그 시리즈에 V3라는 새로운 이력 행을 추가하고, V3가 V1과 동일한 불변 D를 가리키도록 하는 A→B→A 시험이다. 개발 중인 Palimpsest 앱의 배포 버전은0.12.0이다.

| 자료 버전 | 가리키는 원문 | 의미 |
|---|---|---|
| V1 | D A (`dfbb33…`) | 처음 캡처한 두 모듈과 실험 metadata |
| V2 | D B (`2820b8…`) | 사본 Runtime의 MODEL 값을 Terra→Sol로 바꾼 내용 |
| V3 | 기존 D A (`dfbb33…`) | A로 돌아온 새 자료 이력; parent는 V2 |

V3는 V1의 번호나 생성시각을 수정하는 방식이 아니다. V1·V2·그때의 I/K/추론은 계속 남으며, 같은 원문 bytes와 완료된 D2I를 재사용한다. 실제 작업 폴더의 개발 코드를 V1 사본으로 덮어쓰지 않는다. CLI 복원 시험은 별도 `version-cli-verification/restored-v1` 폴더에 세 파일을 출력한다.

이력 시리즈 ID는 `01a099ee-b70b-738f-91b1-4ff1e2edc61c`다. V1/V2의 정확한 version ID, 원문·I·K의 보존 결과는 [208개 읽기 전용 검사](readonly-history.json), 새 V3와 CAS/no-op/replay 결과는 [되돌림 검사](revert-history.json), 실제 CLI·앱 source 보존은 [CLI 결과](version-cli-verification/result.json)에 기록한다.

실제 최종 head는 V3 `01a09a28-b3cd-7521-8659-82b2013d2308`이다. no-op·stale CAS 거부·동일 요청 replay가 통과했다. 전이 전후의 Data/I/K/실행 context/모델 호출 행 hash, 원본 D3개 SHA 및 실제 src/desktop 파일 hash가 일치했다. 이 마지막 전이에서 새 Data/I/K와 D2I/provider 호출은 각각0개다. 과거 K가 V3에서 다시 검증됐다고 자동 표시하지도 않는다.

## 구현한 저장·실행 계약

- D는 계속 전체 원본 bytes의 SHA-256이다. UUIDv7 data_series/data_versions를 별도 metadata로 추가했다.
- Artifact Store는 파일 본문과 wrapper를 content-addressed blob으로 공유한다. 원문 전체를 복원할 ordered manifest를 별도 namespace에 두며, 기존 raw `artifact_path`의 논리 계약을 유지한다. raw 경로에 JSON을 대신 넣지 않는다.
- 코드 등록은 `DataService.import_code_snapshot`으로 처리한다. 원본/manifest/hash를 검증하고 복구용 분할 요청을 durable journal에 남긴다. 기존 raw 등록과 duplicate/replay 동작을 보존한다.
- 같은 head의 같은 D는 no-op이다. A→B→A는 새 버전 행을 만들지만 D/I를 새로 만들지 않는다. expected-head가 오래됐으면 새 버전을 저장하지 않고 현재 head와 함께 오류를 반환한다.
- I2K/N2E/K2K의 version context는 정확한 불변 version 행과 실제 전달 ID 목록을 고정한다. `current`는 준비·stage·commit에서 head를 검사하고, `pinned`는 명시적인 과거/비교 범위다. pinned도 accepted/current KRevision 조건을 면제하지 않는다.
- K의 최초 생성 version, 추가 accepted/reused support context, 현재 자료 head 상태를 따로 표시한다. 새 버전이 생겼다고 과거 origin이나 정확한 premise Revision을 바꾸지 않는다.
- K2K의 실제 전제는 accepted K다. 모델 입력에서는 원문 인용 본문을 provenance hash/문자 길이로 바꾸고, canonical 근거와 frozen input은 유지한다. 원문 내용을 새로운 미인용 전제로 쓰지 못하게 경계를 명시했다.

[자료 버전 계약·CLI](../../docs/interfaces/DATA_VERSIONS.md), [구현 모듈 경계](../../docs/implementation/MODULE_BOUNDARIES.md), [진행 기록](../../progress/T07_versioned_code_execplan.md)을 함께 참고한다.

## 전체 코드 저장 측정

기존 보존된202파일 snapshot 두 개를 전용 Artifact Store volume에서 비교했다. 두 snapshot 사이의 변경 파일은 `code_snapshot.py` 하나이며201개 파일 본문이 동일했다. 이 측정은 canonical DB 등록이나 모델 추론 시험과 별개다.

| 항목 | 값 |
|---|---:|
| 두 번째 원문 dossier 전체 크기 | 2,692,920 B |
| 두 번째 버전 추가 blob 내용+descriptor | **109,589 B** |
| 두 번째 버전 추가 Linux 파일 할당 | **114,688 B** |
| 두 버전을 통째로 저장한 내용 크기 | 5,385,701 B |
| 공유 저장의 두 버전 합계 내용+descriptor | 2,840,774 B |
| 내용 크기 기준 절감 | **47.253%** |
| 같은 volume의 파일 할당 기준 절감 | **23.936%** |

첫 snapshot은 작은 blob들의 파일 할당 단위 때문에 raw 한 파일보다 할당량이 컸다. 이후 변경분의 추가량이 작아져 두 버전 합계에서 공간을 절약했다. 양쪽202개씩, 총404개 파일을 전수 복원해 원래 SHA와 크기를 확인했다. 이전 버전 재읽기와 no-op 재게시도 파일 수·inode·bytes 변화 없이 통과했다.

**이 절감률은 원문 Artifact Store 기준이다.** PostgreSQL의 I/K, parser raw, 실행 context, 모델 요청/응답과 전체 Docker VHD 사용량을 포함한 수치가 아니다. 현재 I는 서로 다른 D마다 별도 identity를 유지한다. 물리적인 I/derived artifact 공유, file-level D/I 재사용과 native code parser는 후속 범위다. [상세 저장 보고서](storage-benchmark/REPORT.md), [측정 JSON](storage-benchmark/result.json).

## 실제 모델 실험

두 모듈은 `knowledge_runtime.py`와 `codex_provider.py`의 전체 내용이다. 여기에 실험 범위 metadata 파일을 더한 세 파일을 각 D로 등록했다. V2 사본의 코드 변경은 Runtime의 MODEL.model 한 값이며, 실험 metadata도 V2로 표시된다. 실제 workspace의 모델 설정은 Terra로 유지했다. 전체202파일 codebase를 의미 평가한 실험은 아니다.

| 항목 | V1 | V2 |
|---|---:|---:|
| 원문 dossier bytes | 101,675 | 101,673 |
| D2I 실제 source 실행 | 1 | 1 |
| 모든 내용을 보존한 I | 5 | 5 |
| I2K 검토 시도 | 3 | 1 |
| 승인된 source KRevision | 14 | 9 |
| I2K 최신 상태 | needs_human | needs_human |
| 승인된 supports EdgeRevision | 3 | 4 |
| K2K 신규 추론 KRevision | 1 | 1 |
| N2E·K2K 최신 실행 상태 | completed | completed |

두 D 모두 모든 I를 순서대로 합치면 exact D bytes를 복원한다. 모든 I가 두 단계 I2K 모델 호출에 실제로 전달됐고, 검토 의견과 실패/이전 시도도 보존했다. D2I의 application LLM 호출은0회다.

최종 코드 실험 DB에는 **KNode25개/NodeRevision25개, KEdge7개/EdgeRevision7개, derivation2개**가 있다. V1의 반복 I2K에서는 동일 의미에 대한 reuse Record10개가 생겼고 새 semantic Revision은 만들지 않았다. 서로 다른 D에 속한 source-specific K는 owner와 version을 유지한다.

실제 K2K 결과는 다음과 같다.

1. **V1:** 성공한 provider transport만으로는 K를 반영할 수 없고 Runtime의 Validator 판정이 필요하다는 제한된 연역. 전제 Revision은 `01a099f3-4fae-71ad-8088-8be082538f41`, `01a099f3-4fb8-797b-9afe-13d8d8663a63`이다.
2. **V2:** Generator와 같은 provider/thread reference를 가진 Validator receipt는 거부되므로 staged 후보의 반영을 결정할 수 없다는 제한된 연역. 전제 Revision은 `01a09a0e-9eb8-723a-90db-334d141d2aab`, `01a09a0e-9ebe-732a-a1cf-d3e665f69800`이다.

두 결과 모두 실제 K2K Record의 `is_inferred=true`, deductive 유형, 가정·한계·독립 Validator 결과와 exact premise refs를 저장한다. K2K Record가 만든 가짜 direct I grounding은0개이며 전제 K를 거쳐 I/D에 도달한다. 정적 코드에 대한 추론이고 해당 코드 동작이나 테스트를 실제로 실행했다는 Observation은 아니다. [V1 graph](live/v1/k2k-1/graph.json), [V2 graph](live/v2/k2k-1/graph.json), [최종 의미 실험 집계](semantic-summary-final.json).

실제 provider transport는 **18회**다. 입력1,573,322 tokens, 출력33,712 tokens이며 provider의 reasoning 필드8,424는 별도 기록했다. 호출 시간 합계는737.596초이고 전체 개발 wall-clock 시간이 아니다. Runtime이 차단한 실제 응답2회도 호출/usage에 포함했다. 실행 전에 자동 승인 검토가 차단한 두 호출은 전송이 없으므로18회에 포함하지 않았다.

## 의미 품질의 한계

**코드 전체의 의미 검토는 끝나지 않았다.** 독립 Validator는 큰 파일 안의 설정·예외·상태 전이 등의 개별 검토가 불충분하거나 기존 항목 연결이 빠졌다고 판단했다. 이를 successful completion으로 바꾸지 않고 두 I2K의 needs_human 상태를 유지했다. 이번 후속 실행은 이미 승인된 K만 사용한다.

V2의 변경된 `gpt-5.6-sol` 설정은 source K로 저장됐지만, 처음 계획한 “Runtime과 provider의 모델 설정 불일치를 스스로 찾아내는 결론”은 생성되지 않았다. 이 실험은 **코드 변경 후에도 exact version 기반 저장·추론·역추적이 동작함**을 확인했다. 모든 변경의 영향이나 버그를 자동으로 발견하는 능력, 높은 의미 회수율 또는 일반적인 코드 분석 완성도를 입증하지는 않는다. [실험 계획과 기대 기준](SEMANTIC_EXPERIMENT_PLAN.md)을 실제 결과와 구분한다.

원문의 내용이 K로 선택되지 않았다는 사실은 D2I 누락이나 원문 부재의 증거가 아니다. 원문은 I에 남아 있으며 필요한 후속 질문·검토의 근거로 사용할 수 있다.

## 테스트와 발견한 문제

| 검사 | 결과 |
|---|---|
| 독점 전체 application suite | 764개:748 pass/16 skip/실패0,290.929초 |
| 마지막 N2E 타입 schema 변경 후 관련 검사 | 11/11 pass,skip0,22.417초 |
| 별도 기존 PDFium 이미지의 현재 소스 검사 | 22/22 pass,skip0,0.789초 |
| 실제 code DB의 읽기 전용 source/Revision 이력 검사 | 208 assertions pass |
| 전체202파일×2 Artifact Store 복원 | 404개 파일 SHA/크기 일치 |

전체764개 검사의 image는 `76e84…`이고, 마지막 타입 schema 보완 후의 최종 image는 `a55a64…`이다. 11개 focused 중8개는 기존 검사의 반복이고3개가 새 schema 검사다. PDF22개 중16개가 core의 skip을 보완하고6개는 중복 실행이다. 이 숫자들을 서로 다른 테스트 개수인 것처럼 단순 합산하지 않는다. [전체 검증](verification-results.json), [마지막 schema 검증](edge-schema-verification.json), [PDF 로그](native-pdf-tests.log).

보존한 실패와 수정:

- 두 suite를 같은 fixture DB에서 동시에 실행해 정상 knowledge_state CAS가 충돌했다. 제약을 완화하지 않고 단독 실행으로 다시 검증했다. [간섭 기록](focused-tests-interference.json).
- N2E stage 반환값과 JSONB 재조회에서 dictionary 키 순서가 달라 Validator prompt hash가 바뀌었다. 최초 실제 receipt를 failed call로 남긴 뒤 정확한 DB context로 독립 검증을 새로 실행했고, helper 직렬화를 고쳤다. 수정 전 RED→수정 후 GREEN과 실제 V1 복구를 모두 기록했다.
- V2 첫 N2E는 Observation을 도착점으로 제안해 구조 검사에서 차단됐다. 원래 응답을 수정하지 않고 failed execution/0개 Record로 마감했다. 새 schema의 도착점을 실제 Proposition에 제한한 다음 새 모델 호출로 정상 검증했다.
- 코드 snapshot 등록 runner의 누락된 import는 DB 변경 전에 실패했으며 바로잡았다. K2K 파일이 아직 준비되지 않았을 때의 후속 request-export 시도도 모델 실행으로 세지 않는다.
- 자동 승인 검토가 N2E 파생 데이터 및 V2 I2K Validator 전송을 각각 차단했다. 준비된 payload에 대한 사용자 명시 승인을 받은 뒤 실행했다. [N2E/K2K 승인](n2e-approval-granted.json), [I2K 승인](i2k-approval-granted.json).

문서 검사는 application 검사와 별개다. 전체 bundle validator는 기존 외부 문서808개 오류, 보존된 snapshot/복원 사본128개 오류, 이전 raw12개 오류로 합계948개 오류/exit1이다. 원문을 고쳐 이 수치를 없애지 않았다. 이번 작성·수정 문서15개는 구조와 로컬 링크 오류0개다. 전체 tools mutation suite는 큰 workspace clone 단계에서 중단하여 통과로 보고하지 않고, Markdown inspector7개 검사는 통과했다. [문서 검사 구분](document-validation-summary.json), [전체 로그](document-validation.log).

## 실제 적용·정리·남은 범위

최종 image는 **`palimpsest-versions:0.12.0`**, Docker engine ID는 `sha256:a55a64d1a26552a953e05d7a3abe772cdb8fb766f09026b41022974195193d41`다. 초기 PG18/pgvector0.8.6 계약과 SQL0001–0012 bytes를 유지하고0013을 추가했다. 설치 대상은 합성 fixture 및 `palimpsest_codebase_k2k`이며, 기존 논문/Wiki DB를 migrate하지 않았다.

이번0.12의 중간 이미지2개는 활성 컨테이너가 없고 최종 이미지가 보존됐음을 확인한 뒤 삭제했다. DB/Artifact volume, 다른 프로젝트와 기존 정상 parser 이미지는 유지했다. [정리 receipt](docker-cleanup.json). 모든 시험 컨테이너는 `--rm`으로 실행했다.

변경 모듈은 Artifact Store의 segmented backend, DataService/code_snapshot, data_versions/0013, version_context/version_provenance, 공통 KnowledgeRuntime/requests, K2K prompt projection, CLI와 worker request export다. 새 source version 기능은 CLI/Runtime slice이며 현재 Electron의 기존 Wiki 읽기 화면을 코드 버전 편집 UI로 확장한 것은 아니다.

native code D2I parser, I2K의 큰 코드 파일 의미 검토 완성, 전체 EffectiveEdge 기반 K2K, 자동 dependency revalidation, 전체 scheduler/quiescence와 Wiki/RAG/GUI의 새 버전 표시 연결은 후속이다. T07의 AT01/02/03/04/05/12/16/31/32/34/44/60/79/85/86 전체 acceptance를 완료 처리하지 않는다. 현재 graph의 `outbox_pending_not_converged`도 유지한다.

사용자가 지정한 [향후 인터넷 검색 참고 링크](https://chatgpt.com/s/t_6aa65b41bae0819188a4b26b95b8e11b)는 실행 계획에 보관했다. 현재 내용을 읽거나 구현에 적용하지 않았고, 인터넷 검색 기능 착수 때 검토할 자료다.

주요 실제 명령은 다음과 같다. DB 명령은 위에서 명시한 격리 환경을 선택한 상태에서 실행했다. [모델 실행 runner](run_semantic_case.py), [컨테이너 wrapper](run_case.ps1), [읽기 전용 검사](verify_live_history.py)와 각 결과 JSON이 정확한 인자를 보존한다.

```text
docker build --tag palimpsest-versions:0.12.0 .
docker compose -p palimpsest-multi-checks run --rm --no-deps -T migrate
docker compose -p palimpsest-multi-checks run --rm --no-deps -T --entrypoint python app tools/run_app_tests.py
palim data import-code-snapshot SNAPSHOT_DIRECTORY --json
palim data compare-code-versions BEFORE_VERSION AFTER_VERSION --json
palim data restore-code-version VERSION EMPTY_DIRECTORY --json
palim knowledge graph --data-version-id VERSION --json
```
