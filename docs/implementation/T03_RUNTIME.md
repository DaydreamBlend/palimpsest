# T03 — 원문 보존 D2I 실행

현재 후속: [MinerU 이미지 OCR 승인](../decisions/MINERU_IMAGE_DEFAULT.md)에 따라 `python tools/run_d2i.py --data-id <sha256> --work-dir <새 작업 디렉터리>`는 원본 PDF를 200 DPI 이미지화한 뒤 단일 MinerU OCR을 실행한다. 기본 adapter는 `mineru-hybrid-image200-v1`이다. App은 `docker compose build app`으로 `palimpsest-t03-image200:0.3.0`를 빌드한다. 원본 Data SHA와 원본/파생 geometry·동일 raster bytes를 보존한다. 동일 원본·profile 재시도는 기존 I를 재사용하며 원문 구조 저장은 OCR 정확성 승인이 아니다. [이번 실행 계획·검증](../../progress/T03_image_default_execplan.md)을 확인한다.

직전 dual 경로는 `--parser mineru-hybrid-dual`, native 단독은 `--parser mineru-hybrid-native`다. 과거 job resume은 원래 parser 선택을 명시해야 하며 기존 profile/raw/I/ID/hash를 재작성하지 않는다. 이전 dual의 `transcription_review`는 선택·대응 상태이지 모든 누락을 검출하는 품질 점수가 아니다. 아래 과거 실행 수치도 새 profile 결과와 구분한다.


2026-09-10 직전 후속 기록: 기본 worker는 [MinerU Hybrid + Pro2605 1.2B high](../decisions/MINERU_HYBRID_SELECTION.md)다. 병합 전 source span과 원래 페이지를 보존하며 native PDF 제목 후보·전체 Figure/페이지·전사 차이는 [별도 evidence projection](../interfaces/PDF_EVIDENCE.md)으로 만든다. `python tools/run_d2i.py ... --parser mineru-hybrid`와 `python tools/run_pdf_evidence.py --parse-result ... --output ...`를 사용한다. 아래 Paddle 선택과 MinerU 249 blocks/189 I 수치는 각각 당시의 선택·실험 이력이다.

2026-09-10 후속: 새 PDF worker 기본값은 [승인된 PaddleOCR-VL-1.6](../decisions/PADDLEOCR_SELECTION.md)이다. [Paddle adapter와 실행 조건](../interfaces/PADDLEOCR_ADAPTER.md)을 함께 읽는다. 아래 MinerU 249 blocks/189 I/6 Figure 수치는 보존된 이전 실험 기록이며 새 파서의 결과로 해석하지 않는다. application 의미 생성 호출은 계속 없지만, Paddle parser 내부에는 VLM 전사가 포함된다.

> U11은 D2I를 LLM 없는 원문 변환으로 확정했다. 현재 시험 범위는 D→D2I→I이며 I2K는 실행하지 않는다. T03 전체 acceptance gate는 아직 in_progress다. 결과는 [source 실행 결과](../../progress/T03_source_result.json)와 [실행 기록](../../progress/T03_execplan.md)에서 확인한다.

[U11 계약](../decisions/D2I_SOURCE_PRESERVATION.md), [사용자 변경](../decisions/USER_OVERRIDES.md), [저장 계약](../decisions/STORAGE_IDENTITY.md), [T03 작업서](../../tasks/T03.md)가 우선한다. LLM 기반의 이전 두 실험은 immutable 이력으로 보존한다. 현재 D2I에서 Codex/OAuth 호출 경로는 없다.

## 모듈과 실행 경계

| 모듈 | 책임 |
| --- | --- |
| data.py / service.py / artifact_store.py | 도구 등록, 원본 SHA-256 검증, CAS 파일 게시·복구 |
| mineru_adapter.py | MinerU middle JSON을 페이지·위치·nested segments를 보존하는 bundle로 정규화 |
| paddle_adapter.py | Paddle 원시 페이지 JSON·crop·좌표 변환을 같은 source bundle에 연결; 원시 배열 순서 보존 |
| figure_adapter.py | 해시가 고정된 reviewed Figure inventory와 원본 region 이미지를 추가; 원본 block 불변 |
| information.py | source-information-v1 구조·원문별 fingerprint 검사; legacy fingerprint 호환 유지 |
| source_units.py / d2i.py | 전체 원문 block을 결정적으로 조립하고 정확한 출력·완전한 block accounting 확인 |
| figure_coverage.py | 검토된 Figure group별 전체 member/caption 연결 확인 |
| compiler_runtime.py | parsed/proposed/완료 단계의 durable 상태와 I·grounding·Record·후보 정리·outbox의 atomic commit |
| worker_claim.py | 실행별 PostgreSQL session advisory lock; 프로세스/연결 종료 후 복구 |
| cli.py / tools/run_d2i.py | 얇은 CLI와 로컬 Docker worker; LLM import/call 없음 |
| legacy_semantic_d2i.py / codex_provider.py | 이전 실험의 재현·호환 코드. 현재 D2I 공개 명령에서 사용하지 않음 |

새 source profile의 schema_version은 source-d2i-v1이다. parser의 exact version/backend/image/model manifest/GPU/config와 transformation.algorithm=source-units-v1, transformation.schema_version=source-information-v1을 기록한다. policy에는 llm_calls=0, source_fidelity=source_preserving, extraction_scope=whole_document 및 실행 코드 SHA-256을 기록한다. Generator/Validator model·auth 설정은 없다.

## 원문과 위치 보존

원본 PDF bytes는 Data CAS에 그대로 남는다. MinerU middle JSON 및 63개 원래 crop은 noncanonical derived CAS와 immutable parse manifest에 보존한다. normalized bundle은 pages, ordered blocks, parser profile, pdf_points_top_left 좌표계를 가진다. 각 source I payload의 source_blocks에는 원래 parser type·text·segments·grounding_regions·upstream_bbox·raw locator·anchor와 raw block hash를 복사한다. JSON 원형은 parse manifest의 middle 파일로 복원할 수 있다.

page_index는 0 기반이다. bbox는 explicit_region_envelope로 검증된 원문 영역을 포괄하며, 부모의 원래 bbox와 하위 영역의 개별 bbox도 따로 보존한다. 합쳐진 cross-page 표현 대신 원래 페이지의 preproc_blocks 및 discarded_blocks를 사용한다. 페이지 머리말·꼬리말·쪽번호·참고문헌도 보존하며 동일 문구의 다른 위치를 dedup하지 않는다.

표·수식의 HTML/LaTeX와 빈 텍스트를 허용하며 source content의 공백·개행·Unicode를 의미 정규화하지 않는다. 정확한 raw parser 문자열은 segments와 원형 JSON에 남는다. 지원하지 않는 구조, 잘못된 좌표·이미지 경로·해시, 누락 block은 기술적 실패다. MinerU의 OCR·수식 인식 정확성이 구조 검사로 보증되는 것은 아니다.

이번 PDF의 6 Figure는 원본 PDF와 MinerU의 249 blocks를 대조한 [검토 inventory](../../progress/T03_figure_inventory.json)로 묶는다. 원본 PDF region을 Poppler로 렌더링한 전체 Figure 이미지 6개를 추가했고, 각 Figure는 모든 패널과 독립·다음 페이지 caption refs를 가진다. 이 reviewed map을 적용하는 변환은 결정적이지만, 임의의 새 PDF에서 Figure를 자동으로 완전히 묶는 기능은 아직 구현하지 않았다. 원본 region 렌더는 MinerU 실패를 다른 parser로 대체하는 fallback이 아니다.

## source I 저장 형식

[0003_source_information.sql](../../src/palimpsest/migrations/0003_source_information.sql)은 기존 0001/0002 migration과 기존 rows를 재작성하지 않고 source 표현을 추가한다. opaque IDs는 UUIDv7, Data ID는 원본 SHA-256이다.

| 필드 | 의미 |
| --- | --- |
| kind | text 또는 image |
| unit_type | text, image, figure, table, equation 중 원문 표현 단위 |
| semantic_type | source I에서는 null; 의미 분류는 I2K 이후 |
| title | 원문 제목 또는 페이지·block/검토된 Figure 번호 |
| content | 정확한 parser block text; Figure는 원래 block 순서의 caption 결합. 빈 원문은 빈 문자열 |
| payload.schema_version | source-information-v1 |
| payload.validation_basis / semantic_checked | source_structure / false |
| payload.source_blocks / source_artifacts | 원문 구조와 모든 관련 이미지 CAS 참조 |
| groundings | Data, parse artifact, block, page, bbox, raw locator, anchor hash |

구조화된 output은 추가 필드를 허용하지 않는다. 애플리케이션은 builder를 재계산해 후보의 내용·순서·단위·refs가 정확히 일치하는지 검사한다. 모든 original block과 synthetic Figure primary는 정확히 한 단위에 배정돼야 한다. 같은 문구라도 다른 위치의 Text는 별도 source I다. source fingerprint namespace는 legacy information-v1과 분리된다.

Record의 accepted는 source 경로에서 source_structure_verified라는 구조 판정이다. 세계의 참·거짓, 의미의 재사용 가치, 요약 정확성을 승인했다는 뜻이 아니다. 기존 generator_receipt/validator_receipt DB column은 migration 호환을 위해 남지만, 새 값은 role=source_builder/source_checker, receipt_kind=deterministic_source_check, llm_calls=0이고 모델 thread/auth를 포함하지 않는다.

## 실행과 복구

```powershell
docker compose -p palimpsest-dev build app
docker compose -p palimpsest-dev up -d db
docker compose -p palimpsest-dev run --rm --no-deps migrate
$env:PYTHONPATH='src'
python -X utf8 -B tools/run_d2i.py --data-id DATA_SHA256 --work-dir output/new-source
```

원본은 먼저 data import로 등록한다. 기존 PDF 시험은 retained parser job을 명시하고 reviewed inventory를 고정하여 같은 raw parser를 재사용한다.

```powershell
python -X utf8 -B tools/run_d2i.py --parser mineru --data-id a2268b37570f41bb07189cf083376e5823fae364165d5e0e256f796a0814cffe --project palimpsest-dev --work-dir output/t03-source --generation 3 --reuse-parser-job 01a0853c-03d8-72ff-be35-958d8dae8db5 --figure-inventory output/t03-source/reviewed-figures/palimpsest_figures.json
```

CLI는 compile data, jobs parsed, jobs materialize, jobs show/retry/fail/export-parser/hold, information list/show를 제공한다. 공개 jobs propose/decide와 host worker의 provider/codex 인자를 제거했다. compile data는 legacy 모델 profile을 거부한다. 완료된 동일 Data/profile/generation은 기존 execution 및 I IDs를 반환한다. 다른 generation은 명시적인 별도 이력이며 자동으로 기존 I를 대체하지 않는다.

parse 파일은 manifest 참조보다 먼저 게시한다. materialize는 parsed에서 임시 source 후보/Record를 저장하고 proposed에서 구조 검증·canonical 효과를 함께 commit한다. 중간 실패 시 canonical 부분 반영을 rollback하고 같은 Record/후보로 재시도한다. 최종 I, grounding, accepted Record, 후보 제거, outbox는 한 transaction으로 반영한다. 후보 본문과 기술적 실패를 epistemic rejection으로 바꾸지 않는다.

## 검증 및 남은 범위

[독립 QA 예상치](../../progress/T03_source_unit_expectations.json)는 14 pages/249 original blocks → Text 182 + whole Figure 6 + logo Image 1 =189 source I다. [source 결과](../../progress/T03_source_result.json)는 실제 DB 결과·해시·재실행을 구분해서 기록한다. 이전 실험28 I와 Figure 정정6 I는 별도 legacy 이력이다. 현재 조회는 이력을 자동 제외하지 않으므로 다음 I2K는 새로운 source execution refs를 명시적으로 소비해야 한다.

기존 순수·mock·실제 PG 회귀와 source 전용 테스트는 [앱 테스트](../../tests/app/)에 있다. 문서 validator는 애플리케이션 성공 증거가 아니다. 일반 문서 Figure grouping, scanned/mixed PDF, parser 자체 오류 교정, reconciliation/supersession/current view, 비동기 scheduler/fencing 및 I2K 이상의 의미 작업은 이 slice 완료 범위를 넘는다.

I2K/N2E/K2K/K2W에서는 향후 LLM이 엄격한 스키마의 후보를 제안한다. ID·근거 확인·exact replay/중복 검사·기존 node 재사용·검증·atomic 저장은 애플리케이션 책임이다. JSON schema만으로 의미 판단이 결정적이 되는 것은 아니며, 같은 의미의 재표현이나 grounding 추가를 새 K semantic revision으로 만들지 않는 기존 invariant를 유지한다. W2K는 승인된 결정에 대해 계속 LLM 없이 결정적으로 실행한다.


## 페이지 조회와 앞뒤 문맥

사용자는 I 저장 단위를 바꾸기보다 페이지별 조회·LLM 입력부터 적용하기로 선택했다. [PAGE_CONTEXT](PAGE_CONTEXT.md)의 읽기 전용 projection은 기존189 source I의249블록을 MinerU index 순서로14페이지에 통합한다. 원문 문자 구간·I/block/좌표·해시를 보존하며 새 canonical row나 LLM 호출을 만들지 않는다.

```text
palim information pages --execution-id 01a0856e-5610-70bd-9858-e03684a995b0 --json
palim information context --execution-id 01a0856e-5610-70bd-9858-e03684a995b0 --page 10 --json
```

물리 페이지는1부터 시작한다. 현재 페이지의 주 처리 I와 앞뒤 참고 I를 분리하며, I마다 가장 이른 원문 페이지를 주 처리 페이지로 정한다. 예를 들어 중심10쪽의9–11쪽 창에는 Figure6의12쪽 캡션이 없어 missing_information_pages=[12]로 명시한다. 이 표시는 후속 I2K가 추가 근거를 요청할 수 있게 하는 계약이며 이번 slice에서 모델 호출·K 생성을 수행하지 않는다. [실물 결과](../../progress/T03_page_result.json)에서 전체202개 회귀와 반복 조회·원문 이력 불변을 확인한다.
