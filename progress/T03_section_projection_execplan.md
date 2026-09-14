# T03 — 스크립트 기반 전체 문서·읽기 그룹·Figure 참조 구현

상태: COMPLETE — 이번 읽기 slice만 완료, 2026-09-11. 사용자는 LLM wiki + RAG + provenance를 통한 결정 이유와 Revision 보존을 고려해 후속 진행하도록 지시했다. [완료된 설계](T03_script_context_design_execplan.md)의 slice 1–2를 구현했다. 이어진 전체 논문 I 순차 입력 + 별도 이미지 제안을 반영해 전체 문서 조회도 포함했다. 읽기 projection의 버전/근거를 보존하되 projection 변경을 K 의미 Revision이나 결정 이벤트로 취급하지 않는다. T03 전체 gate와 T04는 완료되지 않았다.

## 목표와 경계

기존에 보존된 PDF evidence에서 원문 순서·전체 범위를 유지하는 절/문단 읽기 그룹과 명시적 다대다 Figure 참조를 CLI로 조회한다. label로 원문을 제외하지 않고, 원본 페이지/이미지·caption continuation·불확실성을 함께 찾을 수 있어야 한다. 원문 I/DB/과거 raw·실험·canonical snapshot과 parser/model profile은 불변이다. 신규 parser/LLM 호출, embedding 실행, K/W 생성·Decision 승인·Revision commit, T04 runtime는 이번 범위가 아니다.

USER_OVERRIDES, INDEX, DECISION_REGISTER, T03/T04, U11, image-default, I2K_CONTEXT_POLICY, MODULE_BOUNDARIES, current Information/Knowledge/identity/Decision 계약과 CODE_REVIEW, PLANS를 적용한다. U01–U11와 P의 미정 범위를 유지한다. Python/Docker·CLI-first와 BGE-M3 기본 검색 역할은 그대로다. provenance는 source/조회/input/실제 K근거/Decision 당시 이유를 구분하고 현재 검색 결과로 과거 근거를 덮어쓰지 않는다.

## 실제 코드와 계획

- `section_projection.py`를 실제 순수 읽기 기능으로 추가한다. 검증된 `pdf_evidence.read_evidence` 및 기존 page/paragraph projection을 재사용한다.
- `figure_references.py`는 source 기반 Figure mention/caption 구분을 담당한다. 기존 `pdf_visual_evidence` 산출물·해석을 바꾸지 않고 새 읽기 버전에만 사용한다.
- `information sections/section-context/document-context` CLI는 DB 없는 evidence 조회를 제공하고, execution 선택 시 완료된 단일 source execution의 기존 page_view를 통해 canonical I와 결속한다. 동일 D라는 이유로 서로 다른 parser 실행의 I를 합치지 않는다. 두 context 조회는 최신 projection SHA가 필요하다.
- exact Data/bundle/evidence/profile과 projection digest, 원문 범위 및 target/context 구분을 노출한다. artifact-only 조회에 canonical I ID나 실행을 지어내지 않는다.
- 기존 Test_Paper와 추가 Q8 세 문서의 frozen evidence를 읽기 전용으로 재사용하여 전체 배정, 재현성·원문 바이트/offset·명시적 연결과 알려진 반례를 확인한다. 새 결과는 `output/t03-section-projection/`에 별도 저장한다.

## 검증과 복구

새 순수 기능과 source 경계에는 실제 단위/회귀 테스트를 추가하고 기존 page/paragraph/visual/evidence/CLI 검사를 실행한다. DB 연계는 mock 계약 검사와 실제 PostgreSQL 실행 여부를 구분한다. Docker 앱 검증을 수행하면 기존 이미지 기반 task 전용 임시 컨테이너만 쓰고 완료 후 정리한다. 문서 validator baseline은 기존 12개 서식 오류이며 새 오류 여부를 분리한다.

새 코드/CLI 동작은 이번 파일 변경만 되돌릴 수 있다. DB migration이나 기존 source 결과 덮어쓰기가 없어 원문 복구는 필요하지 않다. AT source/저장 gate를 완화하지 않으며 T03 전체 완료와 T04 K 의미 품질을 주장하지 않는다. 실제 명령, 실패/수정, 측정과 남은 제약은 완료 시 아래에 누적한다.

## 실행 결과와 설계 조정

1. source projection과 Figure 참조 모듈을 추가했다. 별도 agent가 caption 자체 번호와 내부 타 Figure 참조를 구분하는 helper/8 tests를 작성했고, root가 절·context와 CLI/runtime 연결을 소유했다. schema/migration 변경은 없다.
2. 초기 독립 검토에서 exact mapping 없는 ambiguous paragraph가 context에 보이지 않고, 추가 context의 canonical I mapping이 빠지는 사례를 확인했다. 가능한 source refs와 uncertainty를 보이도록 수정하고 canonical context의 모든 보이는 block에 I 매핑을 제공했다. stale projection SHA를 필수로 받아 예전 section 번호가 다른 내용에 대응하지 못하게 했다.
3. 기존 frozen evidence 4편의 모든 source751개, 68개 그룹, 모든 그룹의 target/context/원문 offset·읽기 재현을 검사했다. main Figure26개의 명시적 번호·본문·caption anchor 연결을 확인했으나 caption 완전성 점수로 세지 않는다. supplementary 참조21개는 source 내 caption/visual이 없어 warning을 유지한다.
4. Chen의 번호 없는 caption tail3개가 source에 남지만 Figure별 context에는 빠지는 한계를 확인했다. 소속을 추정해 고치지 않았다. 이어 사용자의 전체 문서 입력 제안을 반영해 `document-context`를 추가하고 `caption_completeness=not_verified`를 명시했다. 최신 전체 입력에는 해당3개 원문과24/26/28쪽이 모두 포함된다.
5. 최초 I2K는 실제 multimodal 한도가 허용하면 전체 문서 입력을 우선한다. 절/문단은 RAG·탐색·부분 재검증·긴 문서 분할에 유지한다. source 불변·조회 snapshot·실제 모델 입력/인용·K 근거·Decision 당시 이유를 구분하는 정책을 SECTION_CONTEXT/I2K_CONTEXT_POLICY/T04와 인덱스에 반영했다.

## 실제 명령과 검사

실행 가능한 전체 Docker 명령과 실패 이력은 [최종 보고서](../output/t03-section-projection/REPORT.md)에 기록했다. 컨테이너의 소스 evidence는 read-only, 새 출력 경로만 writable이고 network-none이다.

- host 단위 최초9개:8통과, psycopg 미설치로 CLI import1 error/exit1. host corpus probe는 PYTHONPATH 누락(exit1), 설정 후 Linux secure-I/O `os.O_DIRECTORY` 미지원(exit1)이었다. 보안 처리를 변경하지 않고 지원 환경 Docker로 검증했다.
- `docker build --network none -t palimpsest-t03-sections:0.3.0 .`: pip dependency layer의 offline cache 불일치로 exit1. `docker build -t palimpsest-t03-sections:0.3.0 .`: dependency cache 사용/exit0. 전체 문서 코드 추가 후 같은 일반 build로 최종 이미지 생성/exit0. runtime/model dependency 변경0.
- 초기 image200 image+현재 source read-only mount에서 section 전수 corpus 검사:4편/751blocks/68groups/exit0. 이후 설치된 첫 새 image에서 section CLI4건과 stale SHA 거부 확인/exit0. 이 이력은 `initial-code/`, `corpus-results.json`, `final-cli-results.json`에 그대로 남기며 최신 whole 결과로 덮어쓰지 않았다.
- 최종 설치 이미지의 `python -B output/t03-section-projection/run_tests.py`: **66tests/0.258초/failure0/error0/skip0/exit0**. section/document13, Figure8, 기존 page/paragraph/evidence/CLI45. 실제 PostgreSQL 검사는 아니며 Runtime binding은 mock이다. 직전65개 결과도 별도 보존했다.
- 최종 설치 이미지의 `python -B output/t03-section-projection/whole_cli.py`: **exit0**, 실제 `palim information sections/document-context` 각4번 exit0, Test_Paper stale SHA는 expected exit4. 4편/751blocks/67페이지 PNG descriptor, 모든 원문 exactonce/offset·manifest 불변. 공백 기준 단어8,455–12,405/편이며 tokenizer 측정이나 모델 전달은0이다.
- 독립 읽기 검토: 최신 document 함수·CLI·runtime route에 actionable defect 없음. 별도 메모리 projection으로 세 추가 문서522blocks/53pages의 exactonce·offset·digest·입력 불변을 확인했다. source 파일 read_evidence 무결성 전수 검사는 위 실제 Docker CLI의 범위다.
- 최종 문서 검사 `python -X utf8 -B tools/validate_bundle.py --json`: 기존12개 raw/과거 실험 Markdown 표 오류로 exit1. [결과](../output/t03-section-projection/document-validation-final.json). 새 문서/링크 오류와 기존 오류를 구분하며 원문/validator 기준을 수정하지 않는다. 문서 mutation suite는 변경되지 않아 반복하지 않았다.
- Docker 최종 감사: **7containers/15images/35volumes → 7containers/16images/35volumes**, 기존 자원 제거0, 추가 컨테이너/volume0, 최종 성공 image1개. task 컨테이너는 모두 `--rm`으로 제거됐다. 기록된 중간 image ID는 마지막 inspect 때 이미 존재하지 않았고 추가 이미지가 최종 하나뿐임을 대조했다. global prune/volume 삭제0. [감사](../output/t03-section-projection/docker-audit.json).

## 변경 파일과 인계

- 새 source 읽기 모듈: `src/palimpsest/section_projection.py`, `src/palimpsest/figure_references.py`.
- 기존 adapter 연결: `src/palimpsest/cli.py`, `src/palimpsest/compiler_runtime.py`의 section_view. 기존 page_view/SQL·source_units·parser·projection 산출물의 해석은 변경하지 않았다.
- 새 tests: `tests/app/test_section_projection.py`, `tests/app/test_figure_references.py`.
- 문서: `docs/implementation/SECTION_CONTEXT.md`, `I2K_CONTEXT_POLICY.md`, `docs/INDEX.md`, `docs/interfaces/PDF_EVIDENCE.md`, `tasks/T03.md`, `tasks/T04.md`, 이 계획. 모든 새 실행·결과·검증 도구는 `output/t03-section-projection/` 아래다.

이번 읽기 기능에 미해결 승인 질문은 없다. source 보존·CLI·provenance와 관련한 회귀를 추가했지만 T03의 AT22/23/25/27/33/36/68/69/71/76/77/81/83/85/90–102/104/105/107/111/112를 일괄 pass로 변경하지 않았다. 전체 native/scanned/mixed QA·원문 충실성 승인·실제 PG 및 후속 의미 gate는 기존 상태다. T04의 AT06/07/08/20/21/24/28/29/30/41/42/43/44/73/74/82/83와 K identity/materiality/CAS 검증도 미실행이다.

다음 경계는 T04에서 모델/provider의 실제 multimodal 예산과 전달, 구조화된 K 후보·exact 인용·검증 상태·identity/reuse·atomic commit을 구현/평가하는 것이다. 전체를 입력에 담았다는 사실을 모든 주장을 읽었거나 모든 K가 검증됐다는 사실로 바꾸지 않는다. 외부 provider 호출이 필요하면 기존 승인 범위를 확인하고 실제 전송 범위가 필요한 시점에만 구체적으로 결정한다. 새 source I·semantic D2I LLM·embedding·K/W 저장을 이 slice에서 실행하지 않았다.
