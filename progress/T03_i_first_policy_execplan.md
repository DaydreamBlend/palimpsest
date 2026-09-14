# T03 후속 — 스크립트 청킹·I 우선·필요 시 원본 PDF

상태: COMPLETE — 입력 정책 동기화만 완료, 2026-09-11. 사용자의 최신 지시는 D2I 청킹은 application LLM 없이 스크립트로 구성하고, I2K에는 I만 먼저 전달하며 원문이 필요하다고 판단되면 원본 PDF를 제공하는 것이다. 직전 전체 I+전체 페이지 이미지 동시 입력 계약의 해당 부분을 대체한다. T03 전체 gate와 T04 runtime는 완료되지 않았다.

## 범위와 실제 상태

USER_OVERRIDES, INDEX, DECISION_REGISTER, T03/T04, MINERU_IMAGE_DEFAULT, SECTION_CONTEXT, I2K_CONTEXT_POLICY, PLANS와 CODE_REVIEW를 확인했다. 기존 image200 MinerU parser/internal OCR VLM 선택은 유지하고 의미적 청킹 LLM을 추가하지 않는다. 원문 I, page/paragraph/section projections는 구현됐지만 실제 I2K payload/provider/tool-calling/K commit은 미구현이다. 이번 변경은 최신 승인 부록과 active 설계/작업서 동기화다. 존재하지 않는 T04 실행 경로를 만들거나 기존 evidence 조회에서 원본 이미지 descriptor를 지우지 않는다.

I-only는 Image I 자체를 빼는 text-only 정책이 아니다. 초기 입력에서 제외하는 것은 원본 PDF와 전체 원본 페이지 companion의 자동 동봉이다. 요청 시 exact Data의 원본 PDF를 제공하고 실제 요청·제공·사용과 K의 I provenance를 연결한다. 원본이 필요하지만 읽지 못한 후보는 미해결로 유지하며 원본을 추측해 채우지 않는다.

## 계획·검증

- root: 승인 부록, I2K_CONTEXT_POLICY/SECTION_CONTEXT/T04와 index/register/evidence 문서 동기화.
- 별도 agent: 실제 전송 코드 유무와 경계 검토, AGENTS/README/DIKW_CURRENT/T03만 수정. schema/migration 소유권 충돌 없음.
- 변경 전12파일은 `output/t03-i-first-policy/baseline/*.snapshot`에 보관했다. 과거 output/progress/canonical/source/JSON 승인 상태는 수정하지 않는다. 과거 계약에는 우선권 안내를 추가하고 사용자 당시 인용·실험 결과는 남긴다.
- 문서 validator를 실행해 직전의 기존12개 raw/과거 Markdown 오류와 비교한다. source/runtime 변경이 없어 앱·Docker·PG·모델 실험을 새로 했다고 주장하지 않으며 불필요한 이미지도 생성하지 않는다.
- 변경 파일/결과/미완료를 아래에 기록한다. 되돌리기는 이번 문서만 baseline snapshot으로 복원하는 범위이며 DB·원문 복구는 필요하지 않다.

## 완료 결과

새 승인 부록 `docs/decisions/I2K_I_FIRST_SOURCE_ON_DEMAND.md`에 사용자 원문과 우선권, MinerU 내부 VLM/application 청킹 구분, Image I를 포함한 최초 입력, 필요 판단·원본 bytes/hash·요청/제공/인용 기록, I 밖의 원문 근거 공백 처리와 미구현 T04 경계를 기록했다.

변경한12개 기존 파일은 AGENTS.md, README.md, docs/INDEX.md, docs/decisions/USER_OVERRIDES.md·DECISION_REGISTER.md·MINERU_IMAGE_DEFAULT.md, docs/implementation/I2K_CONTEXT_POLICY.md·SECTION_CONTEXT.md·DIKW_CURRENT.md, docs/interfaces/PDF_EVIDENCE.md, tasks/T03.md·T04.md다. 과거 승인 문서는 새 우선권 안내를 추가하고 사용자 당시 인용을 보존했다. 초기 입력에서 원본 PDF를 제외하는 정책과 evidence 조회에서 원본 artifact를 보존하는 책임을 구분했다.

독립 검토에서 실제 I2K/provider 전송 경로가 아직 없고 현재 source/page/paragraph/section 조립은 이미 application LLM0임을 확인했다. 따라서 source 변경이나 신규 payload/runtime scaffolding은 하지 않았다. 기존 section/document 조회에서 이미지 descriptor를 제거하지 않았다. 청킹의 알려진 불확실성이나 새로운 I2K 원본 필요 판단의 정확도를 이번 문서 변경으로 해결했다고 주장하지 않는다.

검증 명령은 `python -X utf8 -B output/t03-i-first-policy/audit.py`다. 지정 host Python으로 실행해 exit0, 내부 `python -X utf8 -B tools/validate_bundle.py --json`은 기존12개 raw/과거 Markdown 표 오류로 exit1, 직전 오류 목록과 동일하며 추가 오류0이었다. 변경12문서와 직전 구현·테스트6파일의 SHA 불변을 확인했다. [검사 결과](../output/t03-i-first-policy/audit.json), [문서 validator](../output/t03-i-first-policy/document-validation.json). 원문·canonical/slice/map·기존 raw/I/ID/hash·이전 검사 결과는 수정하지 않았다.

코드 변경이 없으므로 앱/PG/모델 테스트와 Docker build/run은 반복하지 않았다. 추가 컨테이너/이미지/모델 호출0. T03/T04 acceptance IDs의 완료 상태는 그대로이며 실제 I payload 선택, PDF 필요 판단·요청/제공·사용 검증, K provenance·identity/reuse·commit 테스트는 T04에서 남는다. 새 승인 질문이나 차단된 결정은 없다. 필요한 원본을 모델이 요청하지 않는 실패 사례와 요청했으나 읽지 못한 사례도 T04 평가에 포함한다.
