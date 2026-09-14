# T03 — 동일 200 DPI PaddleOCR와 MinerU 비교

2026-09-10. 이전 MinerU 이미지 전사에 입력한 **동일한 PNG bytes**를 PaddleOCR-VL-1.6 full pipeline에 제공했다. 17편의 고정 첫/중간/마지막 51페이지이며, 전체 243페이지를 다시 평가한 결과가 아니다. gold·채점 규칙·실행 설정을 바꾸지 않았다. 관찰자는 Codex이며 독립된 인간 전문가 gold가 아니다.

| 같은 표본·규칙 | MinerU 이미지 전사 | PaddleOCR 200 DPI |
| --- | --- | --- |
| 엄격 문장 일치 | 41/51 (80.4%) | 37/51 (72.5%) |
| 최소 부분문자열 편집거리 합계, gold 7,812자 | 43 | 57 |
| 제목 정확 일치 | 50/74 | 45/74 |
| 제목 포함 일치 | 52/74 | 47/74 |
| 알려진 Greek 오류 5곳, 표시 동등성 | 5/5 | 5/5 |
| 표적 micro 단위 16곳, 표시 동등성 | 16/16 | 16/16 |
| Figure 한 crop에 본체·패널·라벨 보존 | 15/19 | 2/19 |
| Figure 여러 crop의 합집합에 보존 | 16/19 | 3/19 |

엄격 일치는 LaTeX/Unicode·첨자 표기 차이도 실패로 센다. Paddle의 불일치14문장을 모두 검토했으며 표기11·dash형태1·실제 문자오류2(`CII→CI`, `C1q→Clq`)였다. MinerU 이미지 전사의 `OVA-RMA→OVARMA` 오류는 Paddle이 이 표본에서 정확히 보존했다. Paddle 제목의 추가 실패5건은 분류2·표기2·두 줄 제목의 두 번째 줄 실제 누락1건이다. 이 수치들을 문서 전체의 단어·의미 정확도로 해석하지 않는다.

Figure 평가는 실제 crop 안의 픽셀 보존을 확인했다. 별도 텍스트·HTML·페이지 이미지가 남았더라도 crop 밖의 라벨 픽셀은 완전 crop으로 세지 않았다. Paddle의 actual crop122개와 SDK image_assets 밖의 nested/layout-only 저장 이미지13개도 포함했다. 단일 crop partial17은 Figure 원문 전체가 사라졌다는 뜻이 아니다. 전체 페이지 PNG는 모두 보존됐다.

실행은 PaddleOCR3.7.0/PaddleX3.7.2, VL1.6 0.9B BF16와 layout FP32, 기존 immutable Docker image와 두 로컬 GPU를 사용했다. 네트워크 none, 원본·모델 read-only, 일회성 컨테이너이며 application semantic LLM·canonical 쓰기는0이다. 17편 모두 sampled_complete, batch wall 1,162.031초였다. MinerU 이전 batch 1,429.734초에는 source verification이 포함되어 직접적인 순수 추론 속도 비율로 비교하지 않는다.

구조 검증은 **51페이지, 1,112개 block, 124개 직접 crop asset**의 원본 page mapping·PNG hash·bbox·원시 저장을 확인했다. partial raw schema는 whole-document source adapter에서 거부됐다. Figure 추가 SDK asset 시각 검토의 집계 범위는 별도다. 두 카운트를 같은 모집단으로 합치지 않는다.

사용자는 비교 중 **MinerU 원본 PDF + 이미지 OCR의 이중 전사**를 명시적으로 선택했다. [승인과 새 기본값](../docs/decisions/MINERU_DUAL_TRANSCRIPTION.md), [구현 실행 계획](T03_paddle200_execplan.md)을 따른다. 이 보고서는 Paddle 비교 완료이며 새 이중 전사의 전체 품질이나 T03 전체 완료를 주장하지 않는다.

## 검증 산출물

- [전체 parser 실행 기록](../output/t03-paddle200/runtime/parser-results.json): 17/17, exit0.
- [구조·asset 검증](../output/t03-paddle200/runtime/source-verification.json): 기존 app Docker에서 `python -B /repo/output/t03-paddle200/runtime/verify_outputs.py`, exit0.
- [고정 paired score](../output/t03-paddle200/runtime/evaluation/paired-final.json), [모든 전사 불일치 검토](../output/t03-paddle200/runtime/evaluation/transcription-review.json), [제목 검토](../output/t03-paddle200/runtime/evaluation/heading-review.json).
- [Greek·micro 근거 검토](../output/t03-paddle200/runtime/evaluation/scientific-review.json), [평가 freeze](../output/t03-paddle200/runtime/evaluation/evaluation-freeze.json).
- [Figure 시각 검토](../output/t03-paddle200/runtime/figures/review.md), [Figure 검증](../output/t03-paddle200/runtime/figures/verification.json): 232개 참조 파일 hash 재검증, helper exit0.

기존 원본·parser raw·I·ID·hash를 변경하지 않았다. 원시 Markdown의 실제 단독 pipe에 대한 전체 문서 validator 오탐은 원문 수정으로 숨기지 않는다. DB 통합·새 default 실물 검증은 이 문서의 성공 항목과 구분한다.
