# 원문 기반 전체 문서·절 읽기와 Figure 참조

2026-09-11 T03 후속 구현. 사용자가 재확인한 목적은 **LLM wiki + RAG + provenance에 의한 결정 이유 보존 + Revision 보존**이다. 이 slice는 그 입력이 되는 원문 읽기 경로다. [스크립트 우선 정책](I2K_CONTEXT_POLICY.md), [구현·검증 기록](../../progress/T03_section_projection_execplan.md)을 따른다.

같은 날 후속 사용자는 **D2I는 스크립트로 청킹하고, I2K는 I만 먼저 받은 뒤 필요 판단 시 원본 PDF를 제공하는 방식**을 선택했다. [최신 부록](../decisions/I2K_I_FIRST_SOURCE_ON_DEMAND.md)이 직전 전체 페이지 이미지 동시 입력을 대체한다. 일반 논문은 한도 안이면 전체 I를 순서대로 제공하고 초과하면 절/문단으로 나눈다. Image I 자체는 포함하며 원본 PDF/전체 페이지 companion의 자동 동봉과 구분한다. 절 그룹은 탐색·RAG·부분 재검증에 유지한다. 현재 구현은 evidence 조회이며 실제 입력 선택/전송/원본 PDF 요청은 T04 범위다.

## 책임과 이력

원문 I는 immutable source snapshot이다. 절·문단 묶음과 Figure 연결은 재생성 가능한 읽기 projection이며 원본 I를 다시 쓰지 않는다. 출력에 source bundle/evidence manifest/parser profile의 digest와 조회 규칙 버전·최종 projection digest가 들어간다. 문서 전체의 block 배정이 완료됐다는 사실은 I2K가 실제로 입력을 받았거나 K를 만들었다는 뜻이 아니다.

| 시스템 역할 | 이번 읽기 기능의 책임 | 후속 단계에서 보존할 이력 |
|---|---|---|
| LLM wiki | 원문을 연속된 범위로 읽고 원문 표제·Figure를 찾게 함 | KNode/KEdge와 검증된 의미 Revision, 같은 의미의 근거 추가 |
| RAG | 검색 결과가 돌아갈 exact Data/block/I/페이지와 묶음 snapshot 제공 | 당시 검색 후보·순서·profile과 실제 사용한 근거의 분리 |
| Provenance | 원문 bytes·raw locator·범위·이미지와 실행 결속 | 실제 I2K 입력·추가 조회·K의 exact 근거 |
| 결정 이유 | 읽기용 boundary hint를 행위자의 이유로 취급하지 않음 | authority-confirmed Decision W의 actor reason·당시 Context·basis Recommendation W·사용한 K revisions |
| Revision | 묶음 hash 변경만으로 K Revision을 만들지 않음 | 의미가 실질적으로 바뀐 경우의 검증된 Revision과 과거 참조 보존 |

현재 K나 새 검색 결과로 과거 결정 이유를 덮어쓰지 않는다. PDF가 보고한 다른 사람의 결정은 원문 근거이며 사용자 본인이 확인한 Decision W가 아니다. 이 구분과 실제 W2K 권한 확인은 기존 canonical 계약을 유지한다. 이번 slice가 RAG index나 K/W 저장·Decision commit을 구현한 것은 아니다.

## CLI 읽기

보존된 evidence를 먼저 검증한다. DB 없는 조회는 canonical Information ID를 만들어 넣지 않고 `canonical_information_binding=not_requested`라고 표시한다.

```text
palim information sections --directory <evidence-directory> --json
palim information document-context --directory <evidence-directory> --projection-sha256 <sections-result-sha256> --json
palim information section-context --directory <evidence-directory> --section-id <section-id> --projection-sha256 <sections-result-sha256> --json
```

이미 등록된 I와 결속하려면 목록과 context 명령에 같은 `--execution-id <completed-source-execution>`을 준다. Runtime의 `page_view`가 완료된 단일 source 실행과 그 origin Record의 I만 읽고, evidence의 정확한 bundle digest와 일치하는지 검사한다. 같은 Data의 과거 native/dual/image200 I를 섞지 않는다. artifact-only 목록의 hash와 canonical execution을 결속한 목록의 hash는 서로 다를 수 있다.

`section-id`는 해당 projection 안에서만 의미가 있다. 두 context 명령은 함께 전달한 projection SHA가 현재 계산 결과와 다르면 `section_projection_changed`로 거부한다. 새 규칙/근거에 예전 section 번호를 대입해 다른 내용을 보여 주지 않는다. 과거 JSON snapshot의 보관과 과거 구현 재생 가능성은 구분하며, 이 명령이 임의 과거 버전의 replay 엔진은 아니다.

## 구성과 조회 결과

`document-context`는 모든 원문 block의 전사를 순서대로 한 번 결합한 `text`와 정확한 `spans`, 본문이 중복되지 않는 `section_outline`을 반환한다. 빈 전사의 이미지 block도 target과 source/image 참조에 남는다. `rendered_source_pages`에는 모든 retained 원본 PNG의 페이지·경로·좌표 변환을 담고, Figure/panel/source image는 별도 참조 색인으로 제공한다. 이 JSON의 이미지 경로 자체가 모델에 이미지 bytes를 전송한 것은 아니다. **이 evidence JSON 전체를 최초 모델 입력으로 그대로 전송하지 않는다.** T04는 canonical I의 text/media/content/provenance를 선택해 전달하고, 필요 판단 후 원본 PDF를 별도로 제공하며 요청·제공·실제 인용을 기록한다. 기존 page descriptor는 원문 확인과 로컬 조회를 위해 유지한다.

원문 text를 다시 실은 페이지·절 JSON 전체를 함께 붙이지 않는다. 전체 I 입력이 가능해도 모든 K를 한 번의 응답으로 완성해야 하는 것은 아니다. 출력 한도나 미검증 주장·필수 근거가 남으면 같은 문서 snapshot을 참조한 후속 추출/원본 요청/검증이 필요하다. 입력 coverage, 실제 전달, 주장·근거 검증 완료를 각각 기록하는 책임은 T04에 남는다.

`section_projection.py`는 원문 순서와 전체 block을 유지하고 명시적 title에 따라 읽기 그룹을 만든다. 제목 없는 앞부분은 역할 미확정 그룹으로 남는다. Significance·Abstract·Introduction 등의 역할은 원문 표제에서 만든 hint이며 입력 제외나 지식 승인 기준이 아니다. Results/Methods의 소절은 parser title을 사용하고 title만 있는 부모 절은 첫 소절과 함께 읽는다. 원문에 더한 두 줄바꿈과 실제 원문 문자 범위는 구분한다. 원래 Figure 영역의 표시용 설명은 원문 전사에 넣지 않는다.

`figure_references.py`는 `Figure/Fig./Figs.`, 복수 번호·panel·supplement와 명시적 continuation을 읽는다. Figure 자체의 caption 번호와 caption 속 다른 Figure 언급을 구분한다. 큰/모호한 범위를 끝까지 확장하지 않은 경우 warning을 남긴다. 명시적 Figure/caption과 부딪히는 과거 visual 제안은 확정 연결하지 않으며 기존 파일도 고치지 않는다.

단일 그룹 조회는 다음을 반환한다.

- 기본 처리 대상 block과 별도 참고 block. overlap을 새 target으로 중복 배정하지 않음.
- exact 원문 text·page/bbox·raw locator/hash와 해당 group의 원문 문자 범위.
- 관련 Figure/caption 원문, 원본 페이지·panel 및 불확실한 전체 Figure 제안. 실제 OCR에 사용한 retained page PNG와 표시용 visual page를 구분.
- source 문단 연결과 ambiguous/unmatched 상태, 같은 D의 native heading 후보와 OCR discrepancy. 후보가 원문을 교정한 것처럼 표시하지 않음.
- canonical 실행을 지정한 경우 보이는 모든 block의 exact Information ID 매핑. 모델이 실제 사용한 인용이라는 뜻은 아님.

I2K의 tokenizer·이미지/출력 예산에 맞춘 호출 분할·추가 도구 호출 실행은 T04 책임이다. 이 조회는 `model_input_status=not_budgeted_or_delivered`이며, 길고 여러 페이지인 context도 반환할 수 있다. 문맥 후보가 준비된 것과 모델이 실제 읽고 검증한 것은 구분한다.

## 한계와 완료 범위

native font/span은 계속 후보로 보여 주고 자동으로 새 OCR offset이나 의미 경계를 만들지 않는다. 본문 안에 있는 소제목을 모두 찾아 나누지는 않는다. 번호가 없는 caption tail을 Figure에 자동 확정하지 않으며 원문 위치와 문단·페이지 조회로 남긴다. Chen 문서의 24/26/28쪽 tail 3개는 보존되지만 Figure별 context에는 연결되지 않았다. 전체 문서 조회에는 세 원문과 페이지 descriptor가 모두 포함되며 이는 최초 I2K에 원본 페이지가 자동 전송된다는 뜻이 아니다. Figure의 `caption_completeness=not_verified`는 warning이 없어도 caption 전체가 확인된 것은 아님을 명시한다. 확정 mapping이 없는 문단의 가능한 원문 refs도 uncertainty와 함께 유지한다. 그룹 역할이나 의미적 이해의 일반 정확도를 보장하지 않는다.

실제 보존 evidence/CLI 재생, 단위 검사, Docker 실행 및 DB 실행 여부는 구현 기록에서 구분한다. 과거 raw Markdown의 알려진 표 서식 오류를 없애려고 역사 산출물이나 validator 기준을 바꾸지 않는다.
