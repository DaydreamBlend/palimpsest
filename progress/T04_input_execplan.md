# T04 첫 slice — I 입력 준비와 등록 원본 PDF 요청 검증

상태: 첫 입력 준비 slice COMPLETE, T04 전체 IN_PROGRESS, 2026-09-11. 사용자는 최신 I 우선 정책 이후 후속 과정을 계획하고 진행하도록 지시했다. [최신 승인](../docs/decisions/I2K_I_FIRST_SOURCE_ON_DEMAND.md)을 실제 CLI/application 동작으로 연결했다. T03 전체 품질 gate를 완료로 바꾸지 않고 승인된 다음 입력 slice를 구현했다.

## 후속 순서와 이번 완료 경계

1. **이번 구현:** 완료된 단일 D2I 실행의 canonical I를 검증해 최초 입력 snapshot을 구성한다. 전체 I 또는 스크립트 절의 target/context를 선택한다. Image I와 text-kind table 등의 실제 I media를 포함하되 원본 PDF/전체 페이지 companion을 자동 첨부하지 않는다. 같은 snapshot에 결속한 구조화 원본 요청을 검사하고 등록된 원본 PDF bytes/hash를 로컬에서 준비한다. CLI success는 준비 성공이고 모델 전달·K 생성 성공이 아니다.
2. **후속 실행:** 실제 provider의 I text/media 및 PDF 지원·입력 예산을 확인하고, 구조화 요청/후속 응답/실제 전달·사용·검증 상태를 durable Runtime에 연결한다. 고정 Test_Paper에서 원본을 요청해야 하는 사례와 미요청 오류를 평가한다. 기존 Terra/Codex 시험 승인 범위를 확인하고 이미 승인된 동작을 재질문하지 않는다.
3. **K 저장:** 첫 K kind의 구체 schema·identity/materiality fixtures를 만들고 효력이 달라지는 미정 사항만 사용자에게 제시한다. accepted K reuse/grounding append/의미 Revision·read-set freshness·atomic commit을 구현하고 격리 PostgreSQL에서 경쟁/실패를 검증한다. N2E 이후 및 GUI는 이번 범위가 아니다.

## 확인한 계약과 코드

AGENTS, USER_OVERRIDES, INDEX, DECISION_REGISTER, T04, PLANS/CODE_REVIEW, I2K_I_FIRST_SOURCE_ON_DEMAND, CLI_CONTRACT와 canonical I2K/identity 및 승인 R05/U09 경계를 적용한다. 독립 검토 결과 입력 준비와 원본 요청 준비를 막는 미승인 선택은 없다. 첫 K identity/materiality 상세와 새 state/effect/public revalidation subtype·실제 provider 입력은 후속 단계에서 구체화한다. P 전체를 승인 처리하지 않는다.

기존 `CompilerRuntime.page_view`의 단일 완료 실행 조회·artifact 검증, `build_pages` source↔I 매핑, `build_source_units`/`fingerprints`의 source content 검증과 `section_projection`을 재사용한다. `ArtifactStore`의 no-follow FD와 hash 검증을 유지하며 원본 PDF를 derived image-only PDF로 대체하지 않는다. 기존 DB는 d2i operation/D2IRecord만 허용하므로 이 read-only 준비를 D2IRecord로 저장하지 않는다.

## 소유권·변경·복구

- agent: 새 `src/palimpsest/i2k.py`의 순수 입력/요청 계약과 `tests/app/test_i2k.py`.
- root: ArtifactStore의 검증 bytes 읽기, Runtime/CLI 연결, 실제 storage/CLI 검증·문서·완료 보고. 별도 agent는 승인/근거 경계를 읽기 전용 검토한다.
- 변경 전 파일은 `output/t04-input/baseline/*.snapshot`에 보관했다. 새 schema/migration·기존 source/raw/I/ID/hash 수정·모델 호출은 이번 slice에 없다. 소스 코드는 이번 변경을 복원할 수 있고 테스트는 작업 전용 DB/스토어만 사용한다.

## 검증 계획

정확한 source text/FP/grounding/media 보존, target/context 선택·중복 제거, 최초 PDF/raster 미첨부, legacy/cross-execution/변조된 I 거부, stale snapshot/임의 path/없는 I/범위 밖 페이지 요청 거부, 원본 PDF missing/hash mismatch/non-PDF 검사를 추가한다. 실제 PostgreSQL18/pgvector와 Docker CLI로 synthetic 저장 경로와 Test_Paper의 frozen parser 재생을 확인하되 새 parser/LLM 실행과 구분한다. 새 앱 image는 성공 확인 후 하나만 남기고 작업 전용 자원만 정리한다. 현재12개 문서 validator 오류와 추가 오류를 분리한다. T04 AT06–08·20/21/24·28–30·41–44·73/74·82/83 및 T03 전체 acceptance를 일괄 pass로 바꾸지 않는다.

실제 명령·실패·수정·측정·한계는 완료 시 아래에 누적한다.

## 구현·검토 결과

새 `src/palimpsest/i2k.py`가 입력 snapshot/요청 구조 검증을 담당한다. `ArtifactStore.read`는 원본 파일을 동일 no-follow FD로 읽으면서 hash/크기/교체를 검사한다. `CompilerRuntime`는 기존 source 완료 실행 조회를 재사용하며 canonical I 내용/FP/grounding/manifest media를 대조하고, `cli.py`는 `information prepare-input`과 `prepare-source`를 연결한다. DB/LLM 호출 없는 순수 변환 모듈과 저장·실행 adapter 책임을 구분했다. 새로운 schema/migration/dependency, public Candidate domain, 빈 후속 모듈은 만들지 않았다.

독립 검토에서 media의 byte_size가 manifest와 정확히 같은지 검사하는 guard와 일반 Image I의 원문 범위를 파생 Figure로 오인하지 않는 수정을 추가했다. unit/실제 store/PG 테스트가 두 반례를 포함한다. 원본 요청은 모델 관측이 아닌 로컬 JSON fixture로 표시하고, 입력 준비와 actual delivery/semantic verification을 분리했다. 최종 검토에서 추가 blocking finding은 없었다.

변경 파일: `src/palimpsest/i2k.py`, `artifact_store.py`, `compiler_runtime.py`, `cli.py`; `tests/app/test_i2k.py`, `test_artifact_store.py`, `test_source_runtime_integration.py`; `tasks/T04.md`, `docs/INDEX.md`, `docs/implementation/T04_INPUT.md`, `I2K_CONTEXT_POLICY.md`, `MODULE_BOUNDARIES.md`, `README.md`와 이 계획·`output/t04-input/` 기록. [실제 사용법](../docs/implementation/T04_INPUT.md).

## 실제 명령과 결과

1. `PALIMPSEST_APP_IMAGE=palimpsest-t03-sections:0.3.0`으로 `docker compose -p palimpsest-t04-input run --rm -T migrate`: exit0, 신규 격리 PostgreSQL18.6/pgvector0.8.6에 기존0003 source schema 적용. 기존 DB 사용 없음.
2. `docker build -t palimpsest-t04-input:0.2.0 .`: 초기·수정 후 build 모두 exit0. 최종 image ID `sha256:9638a950900d7419b461f09010ae5551f16b1f822053cf7a70c68f3ca5134918`.
3. `docker compose -p palimpsest-t04-input run --rm --no-deps -T --volume C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/output/t04-input:/results --entrypoint python app -B /results/run_tests.py`: 최초 exit1,340tests/8failures. 임시 runner에 main guard가 없어 spawn child가 suite를 재귀 실행했다. 진단 중 이미 종료·자동 제거된 컨테이너를 stop한 명령도 exit1(`No such container`); 실제 강제 중단은 없었다. runner에 main guard만 추가한 최종 재실행은 **exit0,340tests/0failures/0errors/16skips,27.175초**. skipped16은 미설치 PDFium runtime용 검사다. [전체 결과·원래 실패 보존](../output/t04-input/REPORT.md).
4. 같은 최종 image에서 Desktop/Test_Paper.pdf와 `output/t03-image-default`를 read-only mount하고 `/results/test_paper.py`: exit0,87.89초. [실제 명령](../output/t04-input/REPORT.md)의 설치된 CLI를 사용해 frozen parser 재생→canonical I229개(Text193/Image36)→전체/절 입력→원본 요청 준비를 확인했다. source parser/semantic model 재실행은 없다. 63,031자·36 media bytes/hash·원본3,890,649 bytes를 확인했고 초기 PDF/raster 미첨부와 stale 요청 거부를 관찰했다. I 전후 불변 항목은 행 수 비교이며 전체 행 digest를 측정했다는 주장이 아니다.
5. `python -X utf8 -B tools/validate_bundle.py --json`: exit1. [이번 결과](../output/t04-input/document-validation.json)는 [직전 기준](../output/t03-i-first-policy/document-validation.json)과 동일한12개 과거 raw/oracle Markdown 오류다. 새 오류는0이며 문서 검사를 앱 의미 검증으로 보고하지 않는다. 작업 중 문서 경로 조회1건과 원문 line 불일치 patch2건이 실패했고, patch는 부분 반영 없이 올바른 경로·문맥으로 재적용했다.
6. 생성 전후 Docker inventory와 project label을 검사한 뒤 `docker compose -p palimpsest-t04-input down --volumes`: exit0. 테스트용2containers/4volumes/1network를 제거했고 기존 자원은 모두 보존했다. 새 image는 최종 성공본1개만 남음. [정리 확인](../output/t04-input/cleanup-verification.json). 전역 prune 없음. 격리 test UUID는 기록에서 재현 근거로 보존되며 live DB ID가 아니다.

## 인계와 미완료 acceptance

이 slice를 막는 미승인 결정은 없었다. 다음 단계는 상단2번의 실제 I2K provider/구조화 원본 요청 loop 및 durable Runtime이고, 그다음3번의 K schema·identity/materiality·atomic commit이다. provider의 실제 PDF/media 처리와 입력·출력 예산을 코드/문서로 확인하고 기존 승인 범위를 재사용한다. 효력이 달라지는 미정 의미 정책은 구체 schema·반례를 만든 후 필요한 부분만 사용자에게 제시한다.

T04 AT06/07/08/20/21/24/28/29/30/41/42/43/44/73/74/82/83 및 추가 AT107/111/112의 K 의미·freshness·atomic effects acceptance를 완료하지 않았다. T03 전체 원문 충실성 gate, Markdown ingestion, 실제 embedding/RAG, Generator/Validator, N2E 이후와 GUI도 미완료다. 준비 snapshot의 hash를 K cache key/commit freshness 증명으로 전용하지 않는다. 알려진 evidence 경고는 검증 의무이고 미요청만으로 해소되지 않는다. 이 경계에서 첫 구현을 보고한다.
