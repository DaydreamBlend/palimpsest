# T03 — 이미지 OCR 기본값과 I2K 멀티모달 입력 계약

2026-09-10 후속 사용자 지시: MinerU 이미지 방식을 PDF D2I의 기본으로 사용하고 PDF에서 생성한 I의 I2K에는 파싱 내용과 이미지화한 원본 PDF를 함께 제공한다. 현재 D/I/K/W 구조 설명도 실제 구현과 승인된 설계로 나누어 제공한다.

## 목표와 범위

원본 PDF → 200 DPI lossless 이미지/image-only PDF → MinerU3.4.5 Hybrid high + Pro2605 1.2B 전사를 신규 I의 기본 content로 삼는다. 이전 native/dual profile과 모든 raw/I/ID/hash는 보존하고 새 이미지 profile만 추가한다. 원본 Data SHA를 유지하고 OCR 파생 좌표를 기존 raster affine으로 원래 페이지에 연결한다. 일반 문자 native/특수문자 OCR 합성은 과거 명시 옵션으로 남긴다. 실패 시 자동 fallback은 없다.

I2K는 파싱한 I와 대응하는 원본 페이지/전체 Figure/필요한 region 이미지를 함께 받는 계약을 기록한다. 이번에는 T04의 K 생성·의미 모델 호출이나 K/W 저장 schema를 구현하지 않는다. 전사 오류의 완전한 자동 검출이나 K 확정 차단을 이미 구현했다고 표시하지 않는다.

## 확인한 구현과 책임

AGENTS, USER_OVERRIDES, INDEX, DECISION_REGISTER, T03/T04, PLANS, CODE_REVIEW 및 최신 source/dual 계약을 확인했다. Python/Docker와 PostgreSQL18/pgvector, 원문별 I 및 opaque UUIDv7, D SHA-256, U01–U11와 R07/R08 승인 범위는 유지한다. 현재 renderer/mapper와 preproc normalizer, source-unit assembly, evidence projections를 재사용한다. 작업 전 파일은 `output/t03-image-default/baseline/manifest.json`으로 동결했다.

Parser profile/receipt/runner/새 image normalizer와 관련 회귀는 한 agent가 소유한다. Root는 worker CLI·Compiler Runtime/evidence의 새 adapter 연결, 승인 문서·실물 검증·최종 설명을 소유한다. 다른 agent는 D/I/K/W 계약과 실제 schema를 읽기 전용으로 검토한다. 공유 schema/migration은 수정하지 않는다.

## 순서와 검증

1. 별도 승인 부록과 새 exact image profile을 정의한다.
2. 단일 이미지 OCR 실행과 원본/파생 provenance 결속을 구현하고 기존 native/dual 처리를 명시 옵션으로 유지한다.
3. 원본 hash·페이지 geometry·OCR route·전체 raw/model/origin·mapping·source I coverage를 검사하는 targeted tests를 실행한다.
4. 최종 코드로 전체 앱 회귀와 필요한 실제 Test_Paper parser/source/evidence 경로를 검증한다. 격리 DB를 사용하고 기존 사용자 DB는 시험하지 않는다.
5. 변경 문서·원본 보존과 Docker 자원을 확인하고 실행 명령/결과/한계를 보고한다. raw Markdown 단독 pipe에 대한 기존 validator 오류는 원문 수정으로 숨기지 않는다. 변경하지 않은 문서 mutation suite 전체를 불필요하게 반복하지 않는다.

이번 slice는 T03 AT22/23/25/27/33/68/69/71/90–102 관련 단언을 다루며 T03 전체 acceptance를 일괄 완료하지 않는다. T04는 입력 계약만 보완한다. Rollback은 새 기본 profile 선택을 되돌리는 방식이며 이력 재작성은 없다. 진행과 검증은 아래에 누적한다.

## 진행

- 기본값 변경과 I2K의 멀티모달 입력을 승인된 후속 지시로 기록하기 시작했다. 새 provider·model 다운로드는 필요하지 않다.
- `mineru-hybrid-image200-v1` profile, single OCR runner, image adapter와 worker/Runtime/evidence 연결을 구현했다. 기존 mapper/renderer/dual adapter는 작업 전 bytes와 동일하다. 원본 PNG descriptor와 문단의 original/raw bbox를 함께 조회한다.
- 독립 검토에서 retained bundle을 native profile로 가장해 raw 재생 검증을 건너뛰는 문제를 재현했다. bundle/receipt/manifest mode를 결속해 차단했으며 image/dual 변조 regression이 통과했다. 기존 저장 결과의 bytes는 바꾸지 않았다.
- agent targeted: image/receipt/native/dual 관련31 tests PASS; evidence8+paragraph10 PASS. PDF/normalizer 경계 mock와 Linux secure-I/O synthetic fixture의 범위를 실제 GPU/DB 검증과 구분한다. 새 paragraph2 tests는 baseline 코드에서 의도대로 실패함도 확인했다.
- root worker targeted 최초 실행은 PYTHONPATH 누락으로 import 실패(exit1)였다. `PYTHONPATH=src`로 바로잡아2 tests/0.036초/PASS(exit0)를 확인했다. 기능 실패를 숨기지 않는다.
- `docker compose -p palimpsest-t03-image-verify build app`: exit0. 새 태그 `palimpsest-t03-image200:0.3.0`이며 기존 이미지는 보존했다.
- `docker compose -p palimpsest-t03-image-verify run --rm -T migrate`: exit0, 격리 PG에 기존 `0003_source_information`까지 적용했다. 새 schema/migration은 추가하지 않았다.
- `docker compose -p palimpsest-t03-image-verify run --rm --no-deps -T test`: **307 tests/28.413초/failure0/error0/skip16/exit0**. [로그](../output/t03-image-default/runtime/app-tests.log). 별도 pinned MinerU image에서 `python -B -m unittest -v test_pdf_raster test_pdf_text_evidence test_pdf_visual_evidence`: **22 tests/0.728초/failure0/error0/skip0/exit0**. [로그](../output/t03-image-default/runtime/native-tests.log).
- 첫 변경 문서 validator는 exit1, 기존 raw Markdown delimiter9건만 보고했다. 추가 authored 문서 오류는 없으며 실제 OCR 산출물 생성 후 다시 최종 검사한다. 원문/validator 규칙은 수정하지 않는다.
- 실제 고정 실행: `python -X utf8 -B output/t03-image-default/runtime/run_test_paper.py`, exit0, **392.625초/14페이지/OCR=true**. 모델 GPU 재추론을 실행했으며 semantic D2I LLM 호출0이다. [receipt](../output/t03-image-default/Test_Paper/execution.json). 새 코드/profile로 생성한 결과이며 과거 raw를 새 실행으로 표시하지 않았다.
- `docker compose -p palimpsest-t03-image-verify run --rm --no-deps -T ... app -B /repo/output/t03-image-default/runtime/verify_store.py ...`: exit0. 실제 PG18.6/pgvector0.8.6에 **I229개(Text193/Image36)**를 저장하고 모든 source content/block/grounding/hash와 source unit coverage를 확인했다. 같은 import request 및 materialize retry는 동일 ID를 재사용했다. [PG receipt](../output/t03-image-default/store/verification.json), [source 검사](../output/t03-image-default/store/checks.json). 시험 DB만 사용했으며 사용자 live DB는 변경하지 않았다.
- `python tools/run_pdf_evidence.py --parse-result output/t03-image-default/Test_Paper/parse/parse_result.json --output output/t03-image-default/evidence`: exit0. 원본 페이지14장, 전체 Figure companion6개, 제목 후보35개와 전사 불일치/검토 후보70개를 생성했다. 후보70개는 확정 오류 수가 아니다. Figure는 별도 조회 companion이며 이번 canonical source I의 unit_type은 text/image다.
- 기존 pinned MinerU image에서 `python -B /repo/output/t03-image-default/runtime/verify_evidence.py`: exit0. raw에서 재현한 source bundle은 실제 PG의 `a9d636bdde6c6d9485040903826ca725e96c0228701252d60e0db9327f3080df`와 같다. 14장 모두 OCR 입력과 동일 PNG bytes이며 p10 context는 p9–11의 정확한 이미지/원본·raw 문단좌표를 반환한다. [읽기 receipt](../output/t03-image-default/evidence-review/verification.json). source_fidelity_verified=false이며 semantic/canonical writes0이다.
- `docker compose -p palimpsest-t03-image-verify down --remove-orphans`: exit0. 이번 임시 컨테이너와 network를 정리했다. 기존7containers/14images/31volumes가 모두 남고, 추가 잔여는 검증된 새 앱 image1개 및 시험 Data/DB 보존용 volume4개다. 전체 prune/volume 삭제0. [자원 대조](../output/t03-image-default/runtime/final-resource-audit.json). 새 앱 exact ID는 `sha256:f5637baa6ad9fe8162825bdc864891a02bc32212ce9ec68ab8021352d0034981`이다.

## 완료 범위와 미완료

이 이미지 기본값·원본 근거 조회 slice는 완료했다. [현재 구조 안내](../docs/implementation/DIKW_CURRENT.md), [승인 계약](../docs/decisions/MINERU_IMAGE_DEFAULT.md), [T04 입력 계약](../tasks/T04.md)을 연결했다. 새 provider·model·의미 schema 선택이나 승인 대기 결정은 없다. I2K의 실제 multimodal model 입력·semantic 검증·K 확정 보류, K/W 저장과 이후 단계는 미구현이다.

전체 논문의 무누락·원문 충실성 승인은 하지 않았다. 기존17편51표적 페이지의 image MinerU 점수와 이번 Test_Paper 저장/재현 검증을 구분한다. T03 전체 gate 및 AT22/23/25/27/33/36/68/69/71/76/77/81/83/85/90–102/104/105/107/111/112를 일괄 pass로 변경하지 않는다. 전체 native/scanned/mixed QA와 해당 미충족 시나리오는 기존 상태를 유지한다. 기존 canonical snapshot/설치 migration/원문 raw/I/ID/hash는 변경하지 않았다.

최종 `python -X utf8 -B tools/validate_bundle.py --json`은 exit1이다. 원시 Markdown의 delimiter 오류11건(기존9건+새 OCR 원본/근거 사본의2건)이며 authored 문서·상대 링크·source/canonical snapshot 계약의 추가 오류는0이다. [최종 결과](../output/t03-image-default/runtime/document-validation-final.json). 원문 보존을 위해 raw의 단독 pipe를 수정하지 않았다. 변경하지 않은 문서 mutation suite 전체는 이번에 반복하지 않았으며 이전 실패 기록을 pass로 바꾸지 않았다.

## 변경 파일

- 실행: `tools/run_d2i.py`, `deploy/mineru-hybrid/run_parser.py`, `compose.yaml`.
- application: `hybrid_profile.py`, `hybrid_receipt.py`, 새 `image_adapter.py`, `compiler_runtime.py`, `pdf_evidence.py`, `paragraph_projection.py`(모두 `src/palimpsest/` 아래).
- tests: `test_hybrid_worker.py`, `test_hybrid_runtime.py`, 새 `test_image_adapter.py`, `test_pdf_evidence.py`, `test_paragraph_projection.py`(모두 `tests/app/` 아래).
- 계약/안내: `AGENTS.md`, `README.md`, `docs/INDEX.md`, `docs/decisions/USER_OVERRIDES.md`, `DECISION_REGISTER.md`, `D2I_SOURCE_PRESERVATION.md`, 새 `MINERU_IMAGE_DEFAULT.md`, `docs/interfaces/MINERU_ADAPTER.md`, `PDF_EVIDENCE.md`, `docs/implementation/T03_RUNTIME.md`, 새 `DIKW_CURRENT.md`, `tasks/T03.md`, `tasks/T04.md`, 이 실행 계획.
- 이번 재현 도구·exact profile/raw·검증 로그·결과는 `output/t03-image-default/` 아래에 추가했다. [baseline 대조](../output/t03-image-default/runtime/code-audit.json)는 동결한27개 파일 중20개 변경/7개 불변과 Python 구문을 확인했다. `source_units.py`, `page_projection.py`, 기존 dual adapter/renderer/mapper는 byte-identical이다.
