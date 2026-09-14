# 코드베이스 D/I 등록과 첫 K2K Runtime 구현 결과

2026-09-13. 사용자가 현재 Palimpsest 코드베이스를 K2K 실험 자료로 선택하고, 우선 생성 Markdown snapshot을 쓰며 코드 전용 D2I parser는 후속으로 만들기로 승인했다. **실제 원문 코드202파일을 D1개와 I204개로 저장했고, 첫 node-only K2K Runtime과 exact derivation 저장을 구현·합성 PostgreSQL 검사로 검증했다.** 실제 코드에서 K나 추론 결론을 생성하는 provider 호출은 아직0회다.

계약: [코드 snapshot](../../docs/interfaces/CODEBASE_SNAPSHOT.md), [K2K Runtime](../../docs/interfaces/K2K_RUNTIME.md), [실행 계획](../../progress/T07_codebase_k2k_execplan.md).

## 실제 코드 데이터셋

| 항목 | 결과 |
|---|---:|
| 포함된 직접 관리 파일 | **202개** |
| 원래 파일 bytes 합계 | **2,625,372 bytes** |
| 생성 snapshot D | **1개 / 2,692,920 bytes** |
| 저장된 Information | **204개: 파일202 + 소개/manifest2** |
| exact I grounding | **204개** |
| D2I execution | **1개, completed** |
| code source review target | **204개** |
| I 길이 | 최소97 / 중앙10,985.5 / 최대78,293 Unicode문자 |
| 전체 I 문자 합계 | **2,672,868** |
| 같은 request replay / 새 중복 import | 원래 결과 재사용 / duplicate_data 거부 |
| 실제 코드 기반 K / K2K derivation | **0 / 0 — 아직 모델 미호출** |

Data ID: `310a3f3384f2b5f9e75df950e5ba0dc589f30f80a5f53d70ffdd7a8e9c6de02c`  
D2I execution: `01a099a4-74a1-779f-8297-9b8b78464e80`  
I2K execution: `01a099a6-beac-734d-8925-64b621950047` — **prepared, not delivered**.

실제 저장 DB는 새 **`palimpsest_codebase_k2k`**, Artifact Store는 **`palimpsest-codebase_artifacts`** volume이다. 기존 논문 source/Wiki DB를 migrate하거나 원문/I/Revision을 변경하지 않았다. 기존 PostgreSQL 서버에 새 DB만 추가했으며 공용 로그인이나 비밀번호는 바꾸지 않았다.

[정확 원문 dossier](source-release/dossier.md), [embedded manifest의 검증용 사본](source-release/manifest.json), [실제 등록 receipt](registration.json), [D2I 결과](compiled.json), [전체 I 입력](input.json), [최종 source 검증](source-result.json)에 상태가 있다.

이 D는 원문 코드가 포함된 **생성 Markdown 문서 자체**다. raw Python/JS 파일의 media type을 Markdown으로 속이지 않는다. 파일별 hash·경로·원래 줄 수·dossier byte/문자 범위를 보존한다. 기본 포함 root와 생성물/의존성/민감 이름 제외 policy를 manifest에 기록했고, 입력 파일이나 선택 목록이 capture 도중 바뀌면 실패하게 했다.

## 원문 보존·양방향 위치 검증

전체 I content를 순서대로 이어 UTF-8로 인코딩한 bytes가 등록 D와 정확히 일치했다. Artifact Store에서 읽은 원본도 [복원 dossier](dossier.restored.md)와 일치한다. [원래 파일 복원](restored-release-result.json)은202개 파일의 BOM·CRLF·Unicode·마지막 개행 유무를 보존했고, 모든 개별 hash를 확인했다.

모든202개 파일의 dossier byte 구간에서 해당 I를 찾고, I의 정확한 문자 구간을 다시 dossier byte 구간으로 돌려 원래 파일 hash와 비교했다. [파일↔I 범위 목록](file-information-map.json)에 exact Information ID/char range/source line range가 있다. 모든 I도 실제 D source refs를 가진다. [재조립 결과](reconstruction.json)를 보존했다.

소개·file heading·manifest와 같은 wrapper metadata는 원래 코드 파일의 위치로 위장하지 않는다. `palim code locate`는 이러한 구간을 unmapped_ranges로 구분한다. 이후 workspace가 바뀌어도 기존 D와 그 파일 snapshot은 바뀌지 않는다.

코드 전용 AST parser는 만들지 않았다. 이번 I 저장은 기존 `markdown-it-py 4.2.0` heading grouping을 재사용하며 application LLM/OCR 호출은0회다. 코드 실행·정적 분석의 새 결론도 D2I에 넣지 않는다.

## 구현한 K2K 범위

현재 accepted KRevision 두 개 이상 → Proposition 후보 → 독립 Validator → 새 K 또는 동일 의미 재사용 → 정확 도출/전제 이력 저장의 한 실행 단위다. 기존 KnowledgeRuntime의 profile·Record·receipt·scope·atomic commit·outbox를 재사용한다.

- 실제 K2K origin Record에서 `origin_operation=k2k`, `is_inferred=true`를 표시한다.
- 전제는 정확한 KRevision이며 같은 논리 K의 두 Revision을 별개 전제로 세지 않는다.
- inference_type, assumptions, limitations, 간결한 derivation_basis, validation과 계산된 depth를 보존한다.
- 새 파생 K에는 가짜 direct I grounding을 만들지 않는다. 전제의 I/D를 `transitive_source_refs`로 조회한다.
- 같은 의미의 재사용은 기존 semantic Revision·최초 origin을 유지하고 새 derivation만 추가한다.
- 자기 자신/전이된 자기 전제를 재사용하는 순환, 전제 일부 누락, 잘못된 depth·candidate validation·direct I 위조는 거부한다.
- 새 K와 derivation/premise/Record/scope/outbox가 같은 transaction으로 반영·rollback된다.
- Data별 graph에도 직접 I grounding 없는 derived K를 transitive source membership으로 포함한다.

새 inferred K에 original I가 직접 연결된 것처럼 보이게 하지 않는다. 새 원문/추론 support가 추가되어도 최초 origin은 바꾸지 않는다. origin 전제가 stale하면 needs_revalidation을 표시하지만, 별도 dependency 재검토 실행기와 자동 회복은 아직 구현하지 않았다.

## 실제 테스트 결과

| 검사 | 결과 |
|---|---|
| 최종 이미지 전체 앱 suite | **702개 / 686 pass / 16 skip / 실패0**, 214.425초, exit0 |
| 별도 기존 PDFium 이미지 | **22개 / 22 pass / skip0 / 실패0**, 0.751초, exit0 |
| 새 code snapshot·CLI | 9개, Linux에서 실제 symlink 경계 포함 pass |
| 새 K2K 순수 contract | 11개 pass |
| 새 K2K 실제 PostgreSQL Runtime | 9개 pass |
| 새 K2K 실제 PostgreSQL 직접 SQL 우회 | 4개 pass, 주요 위조5사례 포함 |
| 실제 코드 D/I |1 D,204 I, 전체 원문/파일 복원·위치 대응·중복 거부 pass |

위 네 새 테스트 묶음은 전체 suite에 포함된 **33개**이며 별도 가산하지 않는다. PDF 전용22개 중16개가 앱 suite의 skip을 보완하고 나머지6개는 중복 실행이다. 따라서724개의 서로 다른 테스트를 통과했다고 계산하지 않는다. [최종 앱 로그](app-tests-release.log), [이번 실제 PDF 로그](native-pdf-tests.log), [기계 판독 검증](verification.json).

PG 검사는 `palimpsest-multi-checks`의 **별도 fixture DB palimpsest**에서 합성 원문/후보/판정으로 수행했다. source/code DB의 실제 모델 추론과 구분한다. 새 결론의 실제 의미 품질이나 codebase에서의 유용한 발견을 입증한 결과가 아니다.

## 발견한 실패와 수정

1. **공유 SQL trigger 회귀:** 최초701tests에서errors6이 발생했다. 그중5개는 N2E Edge 저장에서 Node 전용 NEW.knode_id를 읽는 오류였다. 설치된0011을 바꾸지 않고0012에서 Node/Edge 분기를 분리해 수정했다. 나머지1개는 불변성 테스트가 DB wrapper의 PalimpsestError 대신 psycopg.Error를 기대한 오류였으며 올바른 공용 예외를 검사하도록 수정했다. [최초 실패](app-tests-first.log), [0012 적용](fixture-migration-final.log), [수정 후 검사](app-tests-final.log).
2. **새 DB 초기화 보호:** 일반 CLI migration은 같은 서버에 이미 palimpsest 역할이 있어 안전하게 migration_conflict로 중단했다. 새 DB가 비어 있는지 확인하는 [별도 초기화 script](bootstrap_codebase.py)에서 기존 로그인/비밀번호를 그대로 두고 동일 migration을 설치했다. [초기 보호 동작](codebase-migration.log), [설치 결과](codebase-bootstrap.log). 기존 DB를 초기화하거나 역할을 삭제하지 않았다.
3. **Windows→Docker snapshot 읽기:** private temporary-directory ACL을 hard link가 물려받아 앱 사용자와 root 모두 snapshot을 읽지 못했다. 두 시도 모두 D 등록 전에 실패했다. 같은 bytes를 일반 파일로 복사하면 읽히는 것을 확인한 뒤, 도구의 staging file이 출력 디렉터리 ACL을 상속하도록 고쳤다. 수정된 source-release는 일반 앱 사용자로 직접 읽어 실제 등록·D2I가 성공했다. source 권한을 임의 완화하거나 root 실행으로 우회하지 않았다.
4. **capture 중 파일 추가:** 파일 내용만 다시 읽으면 새 파일 추가를 놓칠 수 있어 선택 목록도 재검사하도록 보완했다. 새 회귀 검사에서 새 파일이 추가된 capture를 실패시켰다.

첫 [등록 전 snapshot](source/manifest.json)과 Docker permission probe 사본은 실패 조사 자료로 보존한다. 이 bytes를 별도 canonical D로 등록한 것은 아니다. 최종 실제 D는 source-release의 `310a…`다. 첫 source run 로그와 root 확인 로그도 지우지 않았다.

## 모델 입력의 준비 상태

모든204개 I가 새 공통 source review를 포함한 I2K 입력에 들어갔다. [준비된 실제 Runtime context](i2k-prepared.json), [전송 전 Generator 요청](i2k-request/generator-request.json), [준비 결과](i2k-request/preparation.log)를 보존한다. prompt는3,198,068자이며 이미지0개다. 이 수치를 모델 token 수나 provider context 적합성 검증으로 바꾸어 말하지 않는다.

**provider 호출은0회이며 실제 코드 K와 K2K derivation도0개다.** 원문 전체의 의미 검토·K 선택을 수행하기 전에는 codebase K2K premise가 준비됐다고 주장할 수 없다. 다음 실제 모델 실험은 전체 I의 검토를 유지하면서 source-explicit K를 만들고, 승인된 서로 다른 KRevision을 K2K에 넣는 순서다. 입력 규모·출력 규모에 따른 호출 분할/재개와 실제 semantic 검증은 별도로 확인해야 한다. 코드 원문에 테스트가 존재한다는 이유로 통과한 실행 Observation을 만들지 않는다.

## 배포·변경 파일·남은 범위

최종 이미지 **`palimpsest-inference:0.11.0`**, digest **`sha256:3bc7bd4e19200df58dbf762c8a774d759fe6cd5a3dc5996078b99a53a8945bcc`**. 실제 CLI 버전은 `palim 0.11.0`이다. core schema는 새 실험/fixture에서0012이며 원래 source/Wiki DB와 Compose default를 자동 업그레이드하지 않았다.

변경 모듈은 `code_snapshot.py`, `k2k.py`, `knowledge_provenance.py`, 기존 `knowledge_runtime.py`·`canonical_store.py`·CLI, 추가0011/0012, request export/worker 전달 receipt와 새 tests다. Python/Docker와 기존 module boundaries를 유지하고 GUI frontend·MinerU 선택·원문 I·기존 migration bytes를 변경하지 않았다. 코드 snapshot native parser는 사용자 지시대로 후속이다.

실행 명령의 핵심:

```text
docker build --tag palimpsest-inference:0.11.0 .
PALIMPSEST_APP_IMAGE=palimpsest-inference:0.11.0
docker compose -p palimpsest-multi-checks run --rm --no-deps -T migrate
docker compose -p palimpsest-multi-checks run --rm --no-deps -T test
palim code snapshot . output/t11-codebase-k2k/source-release --json
palim code restore output/t11-codebase-k2k/source-release output/t11-codebase-k2k/restored-release-source --json
```

PowerShell에서는 위 image 선택을 `$env:PALIMPSEST_APP_IMAGE=...`로 지정했다. [실제 code source runner](prepare_codebase.py)는 명시된 새 DB/volume만 사용한다. 전체 source 준비·등록·I 저장·위치 검증·I2K prepare는 약150.765초이며 D2I completed 도달은 약51초였다. structural preparation/reverification을 포함한 측정이고 parser/model 벤치마크가 아니다.

전체 T07 scheduler/quiescence, EffectiveEdge 입력 추론, 일반 K material Revision 변경, 자동 dependency revalidation, derived K의 Wiki/RAG 색인·GUI, 실제 code I2K/K2K model 품질 실험은 남아 있다. 이번 실행 단위 완료를 그 범위의 완료로 표시하지 않는다.

문서 bundle 검사 결과는 exit1/948개 오류다. 외부 npm/Electron 문서808개, 보존된 이전 raw12개, 이번 snapshot/복원 사본에서128개로 구분됐다. 복원한 README 등의 원래 상대 링크를 고쳐 raw bytes를 바꾸지 않았다. 이번에 직접 작성·수정한10개 문서는 같은 inspector의 구조·로컬 링크 검사에서 오류0이었다. [전체 로그](document-validation.log), [분류와 작성 문서 검사](document-validation-summary.json). 이를 전체 문서 validator 통과로 보고하지 않는다.

마지막 사용자 안내에 따라 PC 접근이 가능해졌으며 모바일 전용 화면 표시 요구는 해제했다. 결과 보고서의 Codex 파일 패널 열기 요청은 queued로 반환되어 실제 화면 열림을 확인했다고 주장하지 않는다.
