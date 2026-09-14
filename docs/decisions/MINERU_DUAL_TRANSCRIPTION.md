# 2026-09-10 후속 승인 — MinerU 원본 PDF와 이미지 OCR의 문자 선택

상태: accepted scoped follow-up. 사용자는 200 DPI 비교 뒤 MinerU로 고정하고, 원본 PDF를 직접 처리한 전사와 PDF를 이미지로 만든 뒤 OCR한 전사를 비교하도록 명시했다. 일반 문자는 직접 처리 결과를 우선하고 그리스 문자·위첨자·특수문자가 다른 구간은 OCR 결과를 우선한다. 이 결정은 [앞선 Hybrid 선택](MINERU_HYBRID_SELECTION.md)의 신규 PDF 기본값과 새 전사 선택 범위에 우선한다.

## 고정한 실행

- MinerU **3.4.5**, Hybrid engine, Pro2605 1.2B, effort high, 로컬 Transformers/CUDA. 공식 최신 안정판은 3.4.5이고 4.0.0a6는 사전 릴리스다. 확인 출처: [공식 릴리스](https://github.com/opendatalab/MinerU/releases).
- 새 기본 `mineru-hybrid` / `mineru-hybrid-dual200-v1`은 원본 PDF auto와 200 DPI image-only PDF auto를 모두 실행한다. 원본 auto도 스캔 입력에서는 내부 OCR을 사용할 수 있어 실제 `_ocr_enable`을 기록한다. 두 번째 경로는 OCR 활성화를 반드시 검증한다.
- 렌더는 pypdfium2 5.10.1, Pillow 12.3.0, RGB lossless PNG와 image-only PDF를 사용한다. 200 DPI 목표와 긴 변 3,500 pixel 상한, 실제 pixel 크기·배율·원본/파생 geometry·affine·파일 hash를 기록한다. 파생 PDF는 원본 Data로 다시 등록하지 않는다.
- 기존 native Hybrid는 `--parser mineru-hybrid-native`로 명시적으로 실행할 수 있다. 과거 Pipeline/Paddle 선택과 모든 raw/I/Record/ID/hash는 그대로 읽을 수 있다. 자동 fallback은 없다.

## 선택과 보존 계약

두 전체 raw 전사는 바꾸지 않는다. 새 source I의 `content`는 스크립트가 만든 선택 전사이며 primary block의 `native_text`, 원래 segments/raw locator/anchor와 선택 감사 기록을 함께 저장한다. raw 전사 하나의 verbatim 복사라고 표시하지 않는다. 기존 I·hash는 재작성하지 않는다. 이 한정된 새 선택 정책에 대해서만 U11의 자동 수정 금지 문장에 후속 승인이 우선한다.

같은 원래 페이지에서 영역과 문자 문맥이 유일하게 대응할 때만 국소 교체한다. 일반 단어·숫자·구두점의 차이는 native를 유지한다. 그리스 문자·명시적 첨자·지원하는 수학 기호의 OCR 근거는 whitelist 표시 규칙으로 읽을 수 있는 문자에 대응시키며 원래 OCR LaTeX/문자열과 exact field offset을 보존한다. `C1q` 대 `Clq`, `OVA-RMA` 대 `OVARMA` 같은 일반 문자 차이를 OCR로 덮어쓰지 않는다.

대응이 모호하거나 서로 다른 일반 문자가 특수문자 구간에 섞이거나 수식을 안전하게 분리할 수 없으면 그 구간의 native 전사를 유지하고 검토 대상으로 남긴다. 원본에 없는 OCR block도 비교 inventory에 보존한다. 이 정책은 OCR의 진실성을 보장하거나 전문적 의미를 판단하는 규칙이 아니다.

각 선택에는 양쪽 block ID, 원래 page/bbox, raw leaf/field의 문자 범위와 hash, OCR artifact 경로/hash, 선택 규칙/version을 기록한다. OCR 파생 좌표와 원래 PDF 좌표를 구분하고 명시적인 affine을 적용한다. 페이지/문단 조회에도 선택 결과와 원래 전사·근거를 함께 노출한다. 페이지를 넘는 문단 결합은 계속 조회·LLM 입력 projection이다.

Application semantic LLM 호출은 **0회**다. MinerU 내부 VLM 전사만 사용한다. I2K 이후의 구현·실행과 전체 T03 acceptance 승인은 포함하지 않는다. 구현·실물 시험·남은 한계는 [실행 계획](../../progress/T03_paddle200_execplan.md)과 [최종 결과](../../progress/T03_dual_transcription_result.md)에 기록한다.
