# 2026-09-10 후속 승인 — PaddleOCR-VL-1.6 PDF 파서

후속 이력: 이 선택 이후 사용자는 비교 결과에 따라 [MinerU Hybrid + Pro 및 PDF 근거 보완](MINERU_HYBRID_SELECTION.md)을 선택했다. 새 parser 기본값에는 더 나중의 지시를 적용하고 이 문서는 당시 승인·호환 경로의 근거로 보존한다.

> 상태: accepted scoped follow-up. 그림 영역 분리·저장 지원을 확인한 뒤 PaddleOCR-VL-1.6으로 진행하라는 사용자 선택이다. 이 선택의 승인과 실제 PDF 추출 품질·앱 연결·T03 acceptance 완료는 별도다.

## 사용자 근거와 조건 확인

사용자 후속 지시:

> 1번이 그림 인식/분리 기능 있다면 1번으로 진행해줘

이 대화의 1번 후보는 **PaddleOCR-VL-1.6**이다. 앞선 질문에서는 대체 레이아웃 파서가 LLM 기반이어도 된다고 명시했다.

2026-09-10 확인한 [공식 PaddleOCR-VL 사용 문서](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/PaddleOCR-VL.html)는 전체 파이프라인이 레이아웃 요소의 위치·읽기 순서를 찾고 영역별 이미지를 분리한 뒤 VLM으로 인식한다고 설명한다. Python 결과 객체의 JSON·Markdown 및 관련 이미지 저장 기능도 제공한다. 따라서 사용자가 제시한 그림 분리 기능 조건은 공식 기능 설명으로 확인되었다. 특정 논문의 모든 Figure와 패널이 온전히 추출된다는 실물 검증은 아직 이 선택의 근거가 아니다.

## 승인 범위와 적용 우선순위

- 새 PDF D2I의 선택된 파서는 **로컬 PaddleOCR-VL-1.6 전체 파이프라인**이다. 레이아웃 검출·영역 분리와 VLM 인식을 함께 사용한다. VLM 구성요소만 호출한 결과를 전체 파이프라인 실행이라고 표시하지 않는다.
- 이 날짜의 후속 선택은 [U02/U05와 U11의 이전 MinerU 제품 지정](USER_OVERRIDES.md) 중 새 parser 선택에 충돌하는 범위보다 우선한다. 이전 MinerU 선택과 실행 기록은 당시 승인·재현 근거로 보존한다. P01–P12의 나머지 proposed 상태를 변경하지 않는다.
- 앱은 Python, 실행·배포는 Docker, 공개 interface는 CLI 우선이다. exact package/model revision·weights hash·image digest·추론 engine·precision·GPU·실효 설정·adapter version은 해당 실행 profile에 기록하고 검증한다. 모델 제품명만으로 실행 호환성이나 성공을 주장하지 않는다.
- 파싱은 명시적으로 선택한 로컬 profile로 수행한다. 실패 시 MinerU나 다른 모델로 조용히 대체하지 않는다. 원문을 외부 hosted API에 전송하는 권한은 이 선택에 포함되지 않는다.

## D2I의 책임과 원문 보존

```text
immutable PDF Data
→ local PaddleOCR-VL-1.6 layout / crop / transcription
→ retained noncanonical raw JSON, page renders, image crops and execution profile
→ deterministic normalization / source-unit assembly / structural coverage checks
→ immutable source Information and provenance
```

parser 내부 VLM의 OCR·전사·표/수식 인식은 허용된 문서 추출 과정이다. Palimpsest application의 Generator/Validator가 원문을 요약하거나 정보 가치로 선별하는 D2I 경로를 다시 도입하지 않는다. `source-d2i-v1`의 application `llm_calls=0`은 parser 내부 모델 추론까지 0회라는 뜻이 아니며, 모델 추론은 parser profile에 따로 기록한다. LLM의 의미 해석·K 제안은 계속 I2K부터 시작한다.

[U11 원문 보존 계약](D2I_SOURCE_PRESERVATION.md)의 전체 페이지·블록·header/footer/reference·Figure/panel/caption/continuation 보존, `source-information-v1`, `semantic_type=null`, exact Data/page/region/raw locator/hash, 구조 검사와 원문 충실성의 구분은 유지한다. 생성된 그림 설명을 원문 crop으로 대체하지 않는다. 그림의 번호·전체 Figure 경계·패널과 캡션 연결은 추출 결과와 원본을 대조한 근거 없이 확정하지 않는다.

원시 JSON은 덮어쓰지 않고, 정규화된 block에서 실제 raw JSON의 위치를 직접 참조한다. pixel 좌표와 PDF point 좌표를 구분하고 실제 렌더 크기·CropBox·회전 및 검증된 변환을 보존한다. 검증되지 않은 좌표 변환이나 누락 구조를 전체 성공으로 처리하지 않는다.

## 이력과 검증 범위

기존 MinerU raw artifacts, I, Records, IDs, hashes, installed migrations와 과거 평가 결과를 수정·삭제·재분류하지 않는다. 새 parser profile 및 명시적 compilation 이력으로 구분하며 이전 I를 자동 대체하거나 다시 작성하지 않는다. context chunk와 제목 projection은 계속 별도 projection이다.

이 문서는 U01–U11을 담은 `user_overrides.json`과 동기화된 canonical snapshot을 독립적으로 다시 발행하지 않는 **날짜가 명시된 후속 승인 부록**이다. 새로운 U 번호나 P 승인으로 위장하지 않는다. AGENTS·USER_OVERRIDES·INDEX·DECISION_REGISTER의 후속 선택 참조를 통해 이 운영상 우선순위를 알린다. canonical full/slices/current_map 및 `docs/source/`의 bytes는 이 변경에서 손대지 않는다.

작성 시점에 공식 기능 조건은 확인했으나 실제 Paddle PDF 추론 품질은 미검증이다. [T03 Paddle 실행 계획·진행 기록](../../progress/T03_paddleocr_execplan.md)에서 parser 실물 평가, Figure 시각 검토, adapter unit, PostgreSQL/app 연결, 문서 검사의 실행 여부와 결과를 각각 확인한다. Test_Paper의 주 Figure 6개와 추가 논문 소제목의 누락 여부를 검증하며, 이 선택만으로 전체 T03이나 I2K 이후 작업을 완료 처리하지 않는다.
