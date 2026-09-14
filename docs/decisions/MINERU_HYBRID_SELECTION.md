# 2026-09-10 후속 승인 — MinerU Hybrid와 PDF 원문 근거 보완

후속 적용: [MinerU 이중 전사 선택](MINERU_DUAL_TRANSCRIPTION.md)이 신규 PDF 기본값과 국소 문자 선택 범위에 우선한다. 이 문서의 이전 실행·원문·승인 이력은 보존한다.

상태: accepted scoped follow-up. 사용자는 Pipeline/Paddle/Hybrid 비교 결과를 읽고 다음과 같이 지시했다.

> 원문 근거는 이 수준에서 보존하고, 페이지를 넘는 문단 통합은 조회·LLM 입력용으로 따로 만드는 것
>
> 이걸로 가고, MinerU에서 성능 가장 좋았던 조합 이용해서 원본 PDF의 글꼴·텍스트 span을 이용한 소제목 후보 수집, 패널과 함께 전체 Figure·페이지 이미지 제공, PDF 텍스트와 파서 전사의 불일치 검출
>
> 네가 말했던 대로 해보자

## 선택과 근거

새 실행에는 비교한 MinerU 중 **3.4.5 Hybrid engine / Pro2605 1.2B / effort high / local Transformers**를 선택한다. [직전 비교](../../progress/T03_mineru_hybrid_experiment.md)에서 처리 시간과 Figure 5 보존에 장점이 있었으며 제목 누락 39개의 정확한 복구는 0개였고 Figure 6H·과학 기호 전사 손실도 남았다. 모든 품질 항목에서 가장 좋은 모델이라는 승인은 아니다.

이후 사용자 지시는 [앞선 PaddleOCR 선택](PADDLEOCR_SELECTION.md)의 새 parser 기본값 범위에 우선한다. Paddle/Pipeline을 명시적으로 선택하는 호환 경로와 과거 승인·raw/I/Records/IDs/hashes는 보존한다. 실패 시 parser/engine 자동 fallback은 없다. 이미 검증한 exact image/model revision·hash를 재사용하며 무조건 최신 다운로드를 수행하지 않는다.

## 원문과 projection 경계

- 새 Hybrid 원문 정규화는 병합 전 `preproc_blocks`와 개별 leaf span의 원래 page/region/raw locator를 요구한다. `para_blocks` 컨테이너의 페이지를 원문 페이지로 간주하지 않는다. 상위 bbox는 자식의 exact bbox를 대체하지 않는다.
- 페이지를 넘는 문단·절/문맥 묶음은 원문 ref에 결합된 조회·LLM 입력 projection이다. 원래 I·Data를 합치거나 재작성하지 않는다. 모호한 span 대응은 표시하거나 거부하고 출처를 추정해 확정하지 않는다.
- native PDF 글꼴·텍스트 span으로 모은 소제목은 후보이며 canonical 제목/의미 판단이 아니다. 원본과 parser 양쪽 문자열, 좌표·offset·hash를 보존하고 전사 불일치를 검출하되 원문을 자동 수정하지 않는다.
- 모든 페이지 이미지와 parser의 패널 근거를 제공하며 전체 Figure 영역은 도출 근거와 불확실성을 기록한다. 패널 crop을 전체 Figure라고 표시하지 않는다. native text 부재, 알려진 누락, 잘림과 전사 손실을 별도 보고한다.
- parser 내부 VLM 전사는 허용하지만 application 의미 LLM은 I2K부터다. 이 요청은 T03 보완이며 I2K 이후 실행이나 전체 T03 acceptance 승인이 아니다.

후속 날짜 부록으로 운영 선택을 기록한다. U01–U11과 P 제안의 기존 상태, canonical full/slices/current_map 및 immutable source baseline을 독립적으로 다시 발행하지 않는다. 구현·실험 상태는 [실행 계획](../../progress/T03_pdf_evidence_execplan.md)에서 구분한다.
