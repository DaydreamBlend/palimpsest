# T03 후속 — 스크립트 중심 문맥 구성 설계

상태: COMPLETE (설계·기획만). 사용자 최신 요청은 PDF를 LLM이 읽기 좋은 의미적 단위로 구성하고, I2K에서 교정할 수 있는 사소한 경계 차이 때문에 D2I에 application LLM을 넣지 않도록 재평가하는 것이다. T03 전체 acceptance와 T04 runtime은 미완료 상태를 유지한다.

## 목표와 범위

- 기존 실험을 절 라벨 정답률 대신 원문 가용성·읽기 순서·필요 문맥과 I2K의 실제 이해에 대한 영향으로 해석한다.
- `docs/implementation/I2K_CONTEXT_POLICY.md`에 스크립트 우선 설계, 허용 가능한 차이, 처리해야 할 오류, 입력 구성과 후속 검증을 구체화한다. INDEX와 T03/T04에 인계 링크를 연결한다.
- 이번에는 production code, DB/schema, parser/model default, canonical snapshot, 과거 실험·동결 평가 기록을 바꾸거나 새 모델 실행을 하지 않는다. 후속 구현 범위·명령은 계획이며 실행 결과가 아니다.

## 확인한 근거와 계약

`PLANS.md`, USER_OVERRIDES, INDEX, DECISION_REGISTER, T03/T04, CODE_REVIEW, U11 D2I_SOURCE_PRESERVATION, MINERU_IMAGE_DEFAULT, I2K_CONTEXT_POLICY, PAGE_CONTEXT, PDF_EVIDENCE, MODULE_BOUNDARIES, current Information/I2K canonical과 repository inventory를 확인했다. U01–U11 및 기존 사용자 입력·모듈화 선호를 유지하며 P 전체 승인이나 의미 모델 선정으로 확대하지 않는다. canonical 통합본/slice/map은 편집하지 않는다.

현재 production의 페이지/문단/evidence 조회는 재사용할 수 있다. `tools/run_script_context_review.py`는 실험용 선택 후보 검토기이며 전체 원문 입력 planner가 아니다. 추가 Q8 실험의 522개 원문 보존과 자연 입력 154개를 구분한다. 모델의 판정 정답률은 script-only I2K 품질 점수가 아니다.

## 순서와 확인

1. 원문 계약·실제 코드·실패 사례를 읽고 독립적으로 경계 및 코드 재사용을 검토한다.
2. 원문 I → 읽기 그룹 → 호출 입력 → I2K 책임을 기존 모듈 위에 배치한다. 일반 라벨·경계는 hint이며 대상 선별이나 K 근거의 권위가 아니다.
3. 설계문서와 task 인계를 편집한다. 변경 전/후 번들 validator 결과, 문서 링크와 보존해야 할 파일의 hash를 확인한다.
4. 설계 검토를 반영하고 이번 완료 범위와 후속 구현·실제 I2K 비교 평가를 분리해 보고한다.

복구는 이번 문서 변경만 되돌리는 것이다. 원문/DB/과거 모델 산출물 복구는 필요하지 않다. 신규 migration, dependency, provider, 소형 모델 상시 운영은 도입하지 않는다.

## 후속 구현 — 작은 4개 slice

아래는 실행할 순서의 계획이다. 현재 turn에서 구현·모델 평가를 실행하지 않았다. 모든 신규 경로는 실제 기능을 만들 때만 생성하며 빈 scaffolding을 만들지 않는다.

| 순서와 경계 | 실제 재사용 경로 및 최소 추가 책임 | 확인할 동작 |
|---|---|---|
| 1. T03 원문 기반 읽기 그룹 | `page_projection.build_pages`, `paragraph_projection.build_paragraphs`, `pdf_evidence.read_evidence`를 재사용. 새 `src/palimpsest/section_projection.py`에 순수 절 projection을 구현하고 기존 information 조회/CLI에 연결 | source range 전부 기본 그룹 배정, 같은 입력의 재현성/무변경, 읽기 순서와 원본 heading, 제목 없는 앞부분·Significance·인라인 제목을 놓쳐도 원문 유지 |
| 2. T03 명시적 Figure 참조·입력 초안 검증 | 기존 `pdf_visual_evidence.py`의 caption 감지와 section의 body callout 연결을 보강. source I·raw·과거 Figure inventory는 불변 | Fig./Figs./복수·panel·supplement, caption 자체 번호와 다른 그림 언급 구분, 충돌 미확정, caption continuation/원본 페이지, 다대다 연결 |
| 3. T04 실제 입력 배정·추가 읽기 | 페이지·문단·evidence selector를 기존 I2K 책임에서 조합. 한도는 실제 tokenizer·이미지·출력 여유를 포함해 구현 시 결정 | target/context 구분, 모든 source target의 child range 배정·실제 전달 추적, 긴 문단 범위, 이미지 hash/전체 근거 페이지, 창 밖 Figure 추가 읽기, 미처리 범위를 성공으로 표시하지 않음 |
| 4. T04 실제 의미 영향 비교 | 같은 PDF I·이미지·모델·조회 기능에서 script-only와 사람이 검토한 원문 그룹을 비교. 미정 registry/provider 계약은 T04에서 해결 | 사전 고정 주장/근거 기준, 누락·Figure 귀속·수치/단위/부정/조건 오류와 적절한 보류, overlap 중복 K 방지, 전체 비용/시간과 후속 조회 비교 |

Slice 1–2는 먼저 Test_Paper와 추가 Q8 평가의 3편 frozen source로 진행한다. 새로운 파싱·다운로드·소형 LLM 없이 fixture를 재사용하며, 이 4편은 개발 자료로 표시한다. 새 raw/canonical I/ID/hash/DB migration은 필요하지 않다. 실제 I2K 비교에서는 구조가 다른 미조정 문서를 더해 개발 자료에 맞춘 결과와 분리한다. 이번 기획이 T04 자동 착수 지시는 아니다.

기존 회귀: `tests/app/test_page_projection.py`, `test_paragraph_projection.py`, `test_pdf_visual_evidence.py`, `test_pdf_evidence.py`. 신규 순수 section 동작에는 `tests/app/test_section_projection.py`를 해당 slice에서 추가한다. CLI/runtime 연결에 실제 DB 실행 결속이 추가되면 기존 `tests/app/test_information_integration.py` 경로에서 검증하며 문서/순수 테스트 결과를 PG 성공으로 확대하지 않는다.

예정된 순수 projection 검사 명령은 `PYTHONPATH=src`인 환경에서 `python -X utf8 -B -m unittest discover -s tests/app -p test_section_projection.py`다. 아직 파일/구현이 없으므로 실행하지 않았다. 기존 관련 4개 test 파일도 각 실제 변경에 맞춰 같은 discover 패턴으로 실행한다. Docker build 및 별도 빈 PG의 전체 test는 runtime 연결을 실제 변경하는 slice에서 기존 T03 명령을 사용한다. 현재 기획에 무관한 DB·Docker 준비를 하지 않는다.

## 설계 검토 결과

독립 검토 두 개를 수행했다. 하나는 원문/입력 범위/모델 의미 오류를 분리하고, 다른 하나는 production 코드의 재사용 경로를 추적했다. 핵심 합의는 기존 `make_packets()`가 일부 후보 검토기이므로 전체 I2K 입력기로 승격하지 않는 것, 경계/라벨을 hint로만 사용하는 것, Figure를 독점 소속보다 다대다 원문 참조로 제공하는 것이다.

초안 재검토에서 중대 문제는 없었고 문구 불일치 2개를 수정했다. 이전 표·T04 문장의 Abstract/Introduction 분리에 “경계가 확인 가능한 경우”를 추가했으며, 과거 Test_Paper preview를 현재 작업으로 표시한 문장을 이전 측정으로 고쳤다. 전체 source/실제 입력 coverage, 관련 후보 보류/전체 미충족 완료 금지, parser VLM/application LLM, 향후 I2K 가설/실측 구분을 확인했다.

## 검증·결과

이번 산출물은 설계 문서다. 앱 단위/PG/모델/e2e 검사를 실행했다고 주장하지 않는다. AT22·AT23·AT25·AT27·AT33·AT36 및 T03의 나머지 source/저장 gate를 새 문맥 품질 기준으로 대체하지 않는다. T04 AT06·AT07·AT08·AT20·AT21·AT24 등도 실제 구현에서 검증한다.

변경 전 `python -X utf8 -B tools/validate_bundle.py --json`은 exit 1, 기존 오류 12개다. 이전 parser raw Markdown의 표 delimiter 11건과 Q8의 동결 evaluator 메모 표 1건이며, 이번 기획에서 과거 기록을 수정하지 않는다. [변경 전 결과](../output/t03-script-context-design/validator-before.json). 명령은 inventory의 고정 host Python으로 실행했다.

최종 `python -X utf8 -B tools/validate_bundle.py --json`도 exit 1이며, [변경 후 결과](../output/t03-script-context-design/validator-after.json)의 오류 목록은 baseline 12개와 정확히 같다. 목록 동일성 검사는 exit 0, 새 오류 0이다. current/source canonical 각 13개 slice 검사가 유지된다. 문서 검사를 전체 통과했다고 표시하지 않는다.

변경 파일은 `docs/implementation/I2K_CONTEXT_POLICY.md`, `docs/INDEX.md`, `tasks/T03.md`, `tasks/T04.md`, 이 실행 계획 5개다. 검사 산출물은 `output/t03-script-context-design/`에만 추가했다. 현재 설계의 남은 위험은 script-only 입력의 실제 I2K 의미 정확성을 아직 측정하지 않았다는 점이다. 큰 모델도 읽지 못한 원문을 복원한다고 가정하지 않으며, 모든 OCR 오류가 원본 이미지로 자동 발견된다고 보장하지 않는다.

다음 구현은 slice 1–2의 전체 원문 읽기 그룹·명시적 Figure 참조·입력 초안 검사다. 작은 LLM 모델/양자화 비교를 계속하는 대신 이미 보존된 PDF 근거를 재사용한다. T04 runtime/모델 조건과 실제 의미 비교는 해당 task에서 이어간다. 이번 설계에 추가 사용자 승인으로 막힌 항목은 없다.
