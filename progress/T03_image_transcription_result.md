# T03 — PDF 이미지 전용 OCR·layout 비교 결과

2026-09-10. **이미지 전용 전사는 기존 Greek/단위 오류 5건을 모두 복구했고, 고정 문장 exact는32/51→41/51로 개선됐다.** 다만 원래 하이픈의 소실1건, Figure 패널 I의 pipe 오전사와 일부 crop의 라벨 잘림이 남았다. 제품 기본값 변경이나 전체 T03 완료를 승인한 결과가 아니다.

[기계판독 결과](T03_image_transcription_result.json), [실행 계획](T03_image_transcription_execplan.md), [최종 paired 채점](../output/t03-image-transcription/runtime/paired-final.json), [전사10건 원시 검토](../output/t03-image-transcription/runtime/transcription-paired-review.json).

## 실험 조건

이전 확대 평가17편에서 결과 관찰 전에 고정했던 first/middle/last **51페이지**와 동일한 원본 oracle을 사용했다. 각 논문의 선택3페이지를200DPI PNG로 렌더하고 이미지 객체만 있는 PDF로 만들었다. 원본 전체243페이지를 이번에 모두 OCR한 것은 아니다. 기존 baseline은 전체 논문을 읽었으며, 이번 비교는 원래 물리 페이지에 대응하는 preproc 블록의 전사·제목·Figure 표본에 한정한다. 떨어져 있던 페이지의 인접 배치나 문단 연결 품질은 평가하지 않았다.

- MinerU3.4.5 / Hybrid high / Pro2605 1.2B / local Transformers / method auto를 재사용했다. 공식 모델 revision은 `bff20d4ae2bf202df9f45284b4d43681555a97ed`, image는 `sha256:3f9361035fa4d601d54ed524410d89871fe2524047b04a821594485aae93e0d4`다. 기존 GPU별 profile·runner·model manifest를 변경하지 않았다.
- RTX5080과RTX4060Ti에서 network none으로 실행했다. 실제17개 raw middle 모두 `_ocr_enable=true`, `_effort=high`를 확인했다. 기존16편은 OCR false였고 paper12만 이미 true였다. `image_analysis=false`, formula/table true도 기존 설정 그대로다.
- 51페이지 모두 native text0자·이미지 객체1개, PNG↔내장 RGB pixel exact, 표준200DPI 재렌더 pixel exact를 통과했다. 원본 PDF·PNG·파생 PDF의 서로 다른 SHA와 original page↔derived page/affine을 보존했다. [입력 검증](../output/t03-image-transcription/runtime/render-verification.json), [입력 manifest](../output/t03-image-transcription/inputs-a2/render-manifest.json).
- 파생 PDF는 pixel-grid 크기를 명시적으로 사용한다. 원본과 크기가 같은27페이지/다른24페이지이며 최대 차이는0.2406005859375pt다. 원본을 변경하지 않았고 좌표 왕복 검증 최대 오차는약1.14e-13pt다. 처음 같은 point 크기를 쓴 시도에서 PDFium 재렌더 오차가 발생한 기록도 보존했다.

## 결과와 분모

| 항목 | 기존 Hybrid auto | 이미지 전용 입력 |
|---|---:|---:|
| 고정51문장 strict exact | 32/51 (62.7%) | 41/51 (80.4%) |
| clear 제목74개의 parser title exact | 48/74 (64.9%) | 50/74 (67.6%) |
| clear 제목이 parser title 문자열에 포함 | 50/74 (67.6%) | 52/74 (70.3%) |
| 기존 Greek/단위 오류5표적의 표현 복구 | 0/5 | 5/5 |
| 오류페이지5장의 본문·캡션 micro 단위16개: 표현 동치 | 1/16 | 16/16 |

Strict exact의 정규화는 기존 Unicode NFC·공백 collapse·제한된 HTML 태그 제거만 사용했다. Greek·숫자·문장부호·LaTeX를 점수를 올리기 위해 추가 정규화하지 않았다. 51문장 중30개는 양쪽 exact, 11개는 새 exact, 2개는 exact→nonexact, 8개는 양쪽 nonexact다. 최소 substring 편집거리 합은49→43/고정7,812자이며, 이를 OCR 정확도나 실제 소실 문자 수로 환산하지 않는다.

새 nonexact10개를 모두 원시 span과 대조했다. **9개는 수식/위아래첨자·공백·인용 대시 표기 차이이고1개는 실제 하이픈 소실이다.** 두 exact→nonexact 문장도 `CD11b+`, `E. coli-GFP+`, `CD4+`의 plus가 `^{+}`로 표현된 경우다. 문자 그대로 같은 점수는 실패 상태로 유지한다. 제목의 exact 회귀3개도 `TH17`, `PGE2`, `CD4+`의 수식 표현 차이이며 title 블록은 남아 있다. 제목 exact의5개 개선과3개 회귀가48→50에 대응한다.

실제 잔여 전사 차이는 Rovere paper18 p5의 `OVA-RMA → OVARMA`다. 원본에서는 OVA- 뒤에 줄이 바뀌며 RMA가 이어지고, 기존 raw도 하이픈을 보존했다. 새 MinerU `model.json`의 `/1/3`에 이미 OVARMA가 있어 Palimpsest source 조립 이전 차이임을 확인했다. 저장된 결과를 자동 교정하지 않았다. [제목 회귀 검토](../output/t03-image-transcription/runtime/heading-regression-review.md).

## Greek·단위 진단

| 원본 | 기존 출력 | 이미지 전용 출력 |
|---|---|---|
| `Mφ-mediated` | `Mf-mediated` | `Mφ-mediated` |
| `TGF-β1` | `TGF-b1` | `TGF-` + `\beta` + `1` |
| `FcγRIIA` | γ 대신U+0001 | `FcγRIIA` |
| `1 μg/ml` | `1 mg/ml` | `1` + `\mu` + `g/ml` |
| `1 μM FBG` | `1 mM FBG` | `1` + `\mu` + `M FBG` |

이는 알려진 오류5건에 대한 진단이다. native text와 오류를 공유하던 경로에서 이미지 전사로 바꾸자 복구됐으므로, 이 사례들을 Pro 이미지 인식의 한계로 단정할 수 없다는 근거다. 모든 문서에서 이미지 전사가 우월하다는 인과/모집단 주장으로 확대하지 않는다. [5사례 상세](../output/t03-image-transcription/runtime/greek-five-review.md).

별도 source-only 주석은 같은5페이지의 모든 visible micro 단위21곳을 새 출력 관찰 전에 동결했다. 본문·캡션16곳은 새 literal4/16, 명시한 LaTeX 표현을 포함하면16/16이며 기존 단위 차이15곳을 복구하고1곳의 표현 동치를 유지했다. `3 M`의 μ 부재와 `1 mg/m`의 μ/l 문제도 실제 기존 raw에 있음을 확인했다. 그림 내부5곳은 text 전사 분모에서 제외하며 양쪽 이미지에5/5 보존됐다. [최종 v2 단위 결과](../output/t03-image-transcription/runtime/units-paired.md), [수동 매핑·검토](../output/t03-image-transcription/runtime/units-paired-review.md).

좌표만 쓰던 최초 평가 matcher는 caption 전체 bbox를 공유하는 표현들을 잘못 대응시켰다. 잘못된 v1 부분 점수는 진단용으로 보존하고 최종 점수에 사용하지 않았다. v2는 원본 anchor와 raw 문자 범위를 수동으로32쌍 지정한 뒤 SHA·정확 문자열·span 범위·중복 사용을 검증했다. 단위16/16은 **오류를 알고 고른 페이지의 유한 표본**이며 corpus μ 정확도100%가 아니다.

## Figure·위치 근거

동결된19개 Figure 본체에 해당하는 실제 raw JPEG41개를 시각 검토했다. 단일 crop에 전체 본체가 있는 것은15/19, crop 집합 안에 전체 본체·라벨이 있는 것은16/19다. 네 Figure가 분할됐고, crop 자체가 없는 Figure는0개다.

- paper02 F6와 paper09 F4의 도표는 남아 있다. 일부 패널 문자·그룹 제목은 이미지 밖의 별도 text로 보존돼 있으며 부모 연결 오류도 남았다.
- paper08 F2는3패널로 나뉘었지만 이미지 집합으로 본체·라벨이 모두 보존됐다.
- paper10 F5는11조각이고 A–G 문자는 별도 text에 남았다. **G의 anti-RAGE 왼쪽과 H의 +iNKT 상단 글자 일부는 실제 crop에서 잘렸다.** 전체 원본 PDF와 페이지 PNG에는 남아 있다.

이 지표는 **raw image_body crop 평가**이며 이전 numbered whole-Figure 연결 성공16/19와 같은 지표가 아니다. [Figure 상세](../output/t03-image-transcription/runtime/figure-raw-review.md), [검증 receipt](../output/t03-image-transcription/runtime/figure-raw-review-verification.json).

추가로 paper10 p8 Figure5의 패널 **대문자 I(U+0049)가 pipe(U+007C)로 전사**됐다. 원본의 A–I 순서와 캡션의 (I)를 대조했으며, `source_model.json`의 `/1/18`부터 잘못된 문자가 존재한다. Palimpsest 조립이나 Markdown 내보내기만의 오류가 아니다. 실제 패널 JPEG와 원본 페이지에는 문자 모양이 보존됐다. 고정51문장 밖의 추가 발견이므로 문장 점수와 crop 완전성 수치는 변경하지 않았다. [원시 locator·12개 증거 파일을 담은 부록](../output/t03-image-transcription/runtime/figure-text-appendix.md).

OCR span의 bbox가 문단/캡션 전체 영역을 공유하는 경우도 확인했다. 원시 bbox는 그대로 보존하되 이를 개별 기호의 정확한 좌표라고 표현하지 않는다. 원본 PDF의 native 글꼴/span 근거와 전체 페이지 이미지를 함께 유지해야 하는 이유다.

## 실행·검증·변경 범위

두GPU parser+source 검증 배치는 **1,429.734초(23분49.734초), exit0**다. 최초 렌더 준비·진단 시간이나 이전243페이지 batch와의 속도 비교는 이 값에 포함하지 않는다. 17/17의 파생 source 제안631개(Text586/Image45)를 생성하고 raw page51·block631·leaf2,033개를 검증했다. 동일 raw의 반복 조립은17/17 같았으며 GPU 재추론 반복성 시험은 수행하지 않았다.

원본·이전 결과·production/profile115파일과 새 실행 freeze를 대조했다. Docker는 기존 컨테이너7·이미지13·볼륨27과 같고 새 이미지0, 실험 컨테이너 잔여0이다. 사용자DB·canonical I·이전ID/hash 변경0, application semantic LLM 호출0이며 실제PG commit 시험이나 I2K 이후 실행은 하지 않았다. 이번 산출물의 derived Data hash는 실험용 identity이며 원본 canonical Data 등록을 대신하지 않는다.

실행 명령은 각 [batch document receipt](../output/t03-image-transcription/runtime/parser-results.json)에 전체 argv로 보존했다. 주요 진입점과 결과는 다음과 같다.

| 명령/검증 | 결과 |
|---|---|
| 기존 Hybrid Docker에서 `render_inputs.py --repo /repo --output /out/inputs-a2` | exit0,51페이지 pixel/text/geometry 검사통과 |
| Host Python `run_experiment.py freeze` / `run` / `audit` | 각 exit0;17개 offline parser/source 검증;기존 Docker 동일 |
| 기존 app Docker에서 `score_paired.py` | 최종 exit0,51문장·74제목·19Figure 고정 분모 |
| Host Python `review_transcription_paired.py` | 최종 exit0,nonexact10건/새 exact회귀2건 원시 검토 |
| `score_units_v2.py --self-check` 및 수동32쌍 검증 | self-check15개 및 실제 raw 결속 검사통과 |
| `prepare_figure_review.py`, `finalize_figure_review.py` | exit0,입력162파일/실제JPEG41개 검증 |
| `python tools/validate_bundle.py` | exit1: MinerU raw `source.md`의 단독 `\|`를 표 시작으로 판정해 delimiter 오류1건; 원문/결과는 수정하지 않음 |

첫 scorer 호출은 output을 readonly mount에 두어 exit1로 저장이 거부됐고, 결과 디렉터리만 쓰기 가능하게 고쳐 재실행했다. 전사 검토기도 새 nonexact4건이 나타났을 때 미검토 상태로 exit1을 반환했으며, 원시 확인 후 명시적 검토를 추가했다. 실패 기록을 parser 실패나 gold 변경으로 숨기지 않았다. 제품 코드가 바뀌지 않아 전체 app suite를 반복하지 않았다. 문서 검사·구조 검사·시각 평가를 구분하며 T03 전체는in_progress다.

전체 문서 검사의 오류 경로는 `output/t03-image-transcription/runs/paper10/parse/parser/source/hybrid_auto/source.md:60`이다. 검사기는 저장소의 모든 Markdown을 순회하면서 raw OCR의 단독 pipe 문자를 table로 판정했다. 이 표 판정은 오탐이지만 원래 패널 I를 pipe로 전사한 오류는 실제로 존재한다. 오류를 없애기 위해 원시 산출물의 문자/해시를 고치거나 검사 기준을 완화하지 않았다. [정확한 최종 명령·오류](../output/t03-image-transcription/runtime/document-validation-final.json)에 exit1을 보존하며 전체 문서 검사 PASS라고 보고하지 않는다. 실험의 parser/source 구조 검사와는 별개다.

## 판단

이 자료에서는 **이미지 기반 전사를 D2I의 주 전사 후보로 삼을 근거가 강화됐다.** 원본 PDF·native 글꼴/span·기존 parser raw와 페이지/전체Figure 근거를 함께 보존하고, 수식은 원시 표현과 조회용 표현을 분리하는 방향이 적절하다. 하이픈 손실·패널 문자 혼동·crop 잘림·거친 span bbox·제목 분류 누락은 여전히 별도 보완이 필요하다. 이번 실험만으로 기본값을 전환하거나 자동 교정을 적용하지 않았다.

평가 oracle와 후속 검토는 Codex의 원본 시각 주석/원시 대조이며 독립 전문가 gold가 아니다. 전체 논문의 모든 글자·수식·표·그림 라벨을 채점한 것도 아니고, 모델 추론의 결정론성을 입증한 결과도 아니다.
