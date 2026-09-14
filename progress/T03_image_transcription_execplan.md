# T03 — 이미지 전용 전사 비교 실험

2026-09-10 사용자는 PDF를 이미지로 바꾸고 OCR+layout parsing하는 실험을 승인했다. 기존 Hybrid auto에서 native text와 공유된 Greek/단위 오류를 분리하기 위한 실험이다. 이 승인은 production parser 기본값 변경이나 canonical I 재작성 승인이 아니다.

## 고정 범위

- 앞선 추가 논문 평가의 17편 first/middle/last 51페이지와 동결된 source-only oracle을 그대로 사용한다. 오류가 알려진 5페이지도 포함되며 성공한 페이지의 회귀를 함께 평가한다.
- 기존 MinerU 3.4.5 Hybrid high / Pro2605 1.2B / Transformers / method auto의 image, model, runner와 GPU별 profile을 재사용한다. 200 DPI, long side 3500px 상한으로 원본을 PNG 렌더링하고 논문별 선택 3페이지의 image-only PDF를 만든다. 추가 해상도 튜닝은 별도 조건으로 승인·기록하지 않고 섞지 않는다.
- 파생 입력의 PDF text characters가 0인지와 실제 parser OCR 활성 여부를 검증한다. 원본 page bounds, CropBox/MediaBox, raster 크기, 좌표 변환, 원본/PNG/파생 PDF SHA를 보존한다. 파생 PDF는 별도 SHA를 갖고 원본 Data라고 표시하지 않는다. 아래 진단 뒤 파생 페이지는 200 DPI 정수 픽셀 격자의 크기를 사용하고 원본 point 좌표와의 축별 변환을 명시한다.
- 기존 baseline은 전체 논문을 읽었고 이번 입력은 선택 3페이지다. preproc 원문 블록의 같은 물리 페이지 전사를 비교하며 문서 문맥·이중 rasterization 가능성 등 한계를 기록한다. 문단 병합 품질이나 전체 논문 완전성으로 확대하지 않는다.
- 엄격한 전사 exact와 최소 substring 편집거리 계산은 기존 scorer를 재사용한다. Greek/단위 오류 5건을 개별 검토하고 새 exact→nonexact 회귀를 모두 검토한다. 추가 μ occurrence 평가는 결과를 보지 않은 원본 시각 annotation을 먼저 동결하고 표적 페이지 분모임을 명시한다.

## 실행 및 경계

1. 원본·기존 결과·모델/코드/profile와 평가 oracle hash, Docker 목록을 기록한다.
2. 픽셀 전용 파생 입력과 정확한 원본 page mapping을 만들고 재렌더·text absence·geometry를 검증한다.
3. 두 GPU에서 offline `--network none`, readonly input/model/runner, 임시 `--rm` 컨테이너로 실행한다. 새 모델/image를 다운로드하지 않는다.
4. production source assembler/verifier로 파생 입력의 구조를 검사한다. 이는 원본 canonical I 등록/PG commit 검증과 다르다.
5. 고정 gold와 paired 채점, μ/Greek 및 새 회귀 시각 검토를 수행한다. 실행시간과 실패도 분모에 남긴다.
6. 결과·정확한 명령·한계·미완료 acceptance를 기록하고 문서 검사를 수행한다. 임시 컨테이너 잔여와 원본/production 불변을 확인한다.

제품 코드/schema/migration/기존 raw/I/IDs/hashes 변경, DB 쓰기, application semantic LLM 호출은 없다. T03 전체는 in_progress이며 T04 이후를 실행하지 않는다. PDF/ponytail skill을 적용해 기존 PDFium와 parser/scorer를 재사용하고 실험 helper만 추가한다.

## 진행

- 실험 설계와 51페이지 cohort를 고정했다. renderer, OCR 경로 독립 검토, 원본 μ occurrence annotation을 병렬로 진행한다.
- 원본/이전 raw·결과/production/profile 115파일 hash 및 Docker 컨테이너7·이미지13·볼륨27을 고정했다. 원본-only annotation은 표적5페이지의 micro 단위21곳(본문·캡션16/그림내부5)을 동결했으며 새 parser 출력 관찰 전이다.
- 첫 렌더 `inputs`는 paper01–08의24페이지에서 text0·크기동일·embedded/re-render pixel exact를 통과했으나 paper09의 재렌더 불일치로 실패했다. 실패 입력/로그는 보존하며 아직 추론에 사용하지 않았다. 원인을 조사하고 새 시도 `inputs-a2`를 사용할 예정이다. 검증 기준을 완화하지 않는다.
- 독립 코드 검토로 scorer의 실행후 mapping/source/bundle hash 재검증과 입력 변경 시 실패 처리를 보완했다. source-vs-derived identity 및 고정 page mapping이 틀린 결과는 채점하지 않는다.
- Paper09 진단: embedded RGB는 exact지만 비정수 page 크기 602.9860×782.9860pt와 PDFium image CTM 반올림이 재렌더 차이를 만들었다. max channel 차이195라 무시하지 않았다. 임의 epsilon 보정 대신 전체 문서에 동일하게 `derived_points = raster_pixels * 72 / 200` 규칙을 적용한다. 원본 size 불변이라는 첫 계획의 가정을 변경하며, 파생 size 계획 일치·exact pixels·원본↔파생 축별 scale을 검증한다. 예시 1675×2175px는603×783pt가 되고 원본 Data는 수정하지 않는다.
- 최종 renderer는 nominal pixel-grid 크기 이하의 가장 가까운 float32로 파생 크기를 표현해 ceil 경계의 추가 pixel을 방지한다. `inputs-a2` 전체17편51페이지가 text0·embedded RGB exact·표준200DPI 재렌더 exact·planned-derived size 검사를 통과했다(exit0,21.722615초). Host PNG 재비교51/51 및157파일hash·좌표roundtrip 검증도 통과했다. 파생크기 변경24p/불변27p, 최대변경0.2406005859375pt이며 원본은 불변이다. 자세한 명령·기하 진단은 `output/t03-image-transcription/runtime/render-verification.json`에 보존한다.
- 두 GPU offline parser/source-verifier batch를 시작했다. μ 오류 논문 paper10/17을 먼저 실행하며 고정17편 모두 분모에 남긴다. 실행 helper/입력mapping/gold는 별도 `experiment-freeze.json`에 동결하고, 채점 helper는 각 결과에 자체 SHA를 기록한다.

## 최종 실험 결과

- 두GPU17편51페이지 batch완료/exit0/1429.734초. 모두 OCRtrue/high, source 제안631(Text586/Image45), raw page51/block631/leaf2033 검증통과·동일raw반복조립17/17동일. DB/canonical commit·GPU재추론반복시험은미실행이다.
- 고정문장 strict32/51→41/51,30개exact유지·11개exact개선·2개exact→nonexact·8개양쪽nonexact. 새nonexact10건전체raw검토는수식/첨자/인용표기9건과실제OVA-RMA하이픈소실1건으로구분했다. 새2개exact회귀는위첨자표현차이다. 검토기는최초6건외추가4건등장시exit1로차단한뒤수동검토를추가했다.
- Greek표적5/5복구,본래오류5페이지본문/캡션micro16개는명시적표현동치1/16→16/16(새literal4/16·LaTeX12/16). 그림내부5는전사분모밖이며이미지5/5유지. 최종v2수동32raw매핑과15selfcheck통과;v1공통caption bbox자동매칭오류는보존하고점수에서제외했다.
- RawFigure19개/실제JPEG41개시각검토완료. 단일전체crop15/19·crop집합전체16/19,missing/pending0. 4Figure가분할됐으며paper02/09라벨은별도text,08은crop집합전체완전,10F5일부라벨은실제crop잘림이다. 원본전체페이지는모두보존됐다.
- 첫pairedscorer호출은readonly output mount로저장거부/exit1이었고결과폴더만rw마운트하여재실행했다. 최종scorerexit0,단위/Greek/rawFigure검증도통과했다. 제품코드변경이없어전체앱suite는반복하지않았다.
- Docker최종audit exit0:기존7컨테이너/13이미지/27볼륨동일·임시잔여0,기존115파일hash불변. 결과는[상세 보고서](T03_image_transcription_result.md)와[JSON](T03_image_transcription_result.json)에기록한다. 전체T03의미완료AT목록은기존T03계획상태를유지하며이번실물평가를일괄acceptance완료로취급하지않는다. 승인대기없음·이후변환미실행.
- 최종전사/root집계검증exit0:새nonexact10개중표기차이9/실제하이픈소실1,기존exact→newnonexact2는위첨자표기차이다. 제목48/74→50/74의3회귀도title유지·수식표현차이다. 새raw retained358파일재hash·기존/새freeze137건확인통과.
- 전체문서validator는exit1이다. 유일오류는paper10새MinerU raw source.md:60의단독pipe를table시작으로판정해delimiter를요구한것이다. 원시산출물보존원칙에따라파일수정/검사완화없이실패기록과영향범위를최종보고한다. 이검사를PASS로표현하거나parser/source검증과혼동하지않는다.
- 최종 Figure 텍스트 추가 검토에서 paper10 p8 Figure5 패널 I→pipe를 확인했다. 원시 model /1/18부터 존재하며 별도 부록에 12개 증거 hash와 locator를 보존했다. 고정51문장 밖의 실제 전사 오류이고 이미지에는 원래 문자 모양이 남아 있어 문장 점수/crop 수치는 변경하지 않았다. 문서 검사의 표 판정 오탐과 실제 전사 오류를 구분한다.
