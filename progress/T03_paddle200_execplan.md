# T03 — 동일 200 DPI PaddleOCR 비교와 PDF 기본값 확정

2026-09-10 사용자 승인: “200DPI로 재실험 한번 해주고, 더 나은 걸로 PDF용 D2I는 고정하자”. 비교 후 더 나은 파서를 선택하고 신규 PDF D2I 기본값·실행 profile·문서를 반영하는 권한이 포함된다. 이전 parser/raw/I/ID/hash는 보존하며 추가 선택 승인을 반복 요청하지 않는다.

## 범위와 완료 동작

기존 MinerU image-only 실험의 17편, 고정 첫/중간/마지막 51페이지 PNG를 그대로 PaddleOCR-VL-1.6에 입력한다. 200 DPI 픽셀 SHA·원본 Data/page mapping과 기존 oracle를 고정한다. 이전 Paddle 설정·모델·image를 재사용하고 추가 해상도/생성 설정 튜닝은 섞지 않는다. 원문 전사 충실성을 먼저, 제목·Figure 보존과 운영 안정성/시간을 다음으로 평가한다. 의미를 바꾸는 단위·기호 오류를 표기 차이와 구분하고 일관된 숫자 없는 임의 종합점수를 만들지 않는다.

더 나은 조합을 신규 PDF 기본값에 고정하고 원본 Data identity와 원래 페이지 좌표로 source I를 생성하는 실제 경로를 검증한다. 실험은 일부 페이지만 처리하므로 original page_count와 sampled status를 기록하며 canonical 전체 문서 파싱으로 표시하지 않는다. 두 raw 전사는 불변으로 보존하고, 아래 후속 승인에 따른 새 선택 I와 native 글꼴/span·페이지/전체 Figure 근거 및 조회 projection 경계를 유지한다. I2K 이후/T03 전체 acceptance는 별도다.

## 현재 구현·권위

AGENTS, U01–U11, INDEX, DECISION_REGISTER, T03, PLANS, CODE_REVIEW 및 최신 Hybrid/Paddle 부록을 읽었다. 현재 worker 기본은 `tools/run_d2i.py`의 mineru-hybrid auto다. 기존 image-only 실험은 파생 PDF identity를 썼으므로 그 출력을 원본 canonical I로 바로 저장하지 않는다. production 통합 때 명시적 렌더 mapping·새 profile과 구조/해시 검증을 적용한다. schema 변경은 필요성을 입증하기 전 추가하지 않는다.

PDF/ponytail skill을 적용하여 기존 렌더 PNG, `deploy/paddleocr/run_parser.py`의 pipeline/export 함수를 동결 복사해 재사용한다. 실험 helper는 `output/t03-paddle200/runtime/`, 평가와 Figure 검토는 각 하위 디렉터리를 독립 소유한다. root는 추론 실행·설정/문서와 최종 통합을 소유하고 agent는 평가/시각 검토/통합 위험 검토를 병렬 수행한다.

## 순서·검증·복구

1. 기존 Docker/입력/모델/코드와 gold hash를 동결한다. 과거 실패 output도 보존한다.
2. 두 GPU에서 기존 Paddle image를 immutable digest로 실행한다. 원본 PNG/model은 read-only, 네트워크 none, 임시 --rm 컨테이너다. PNG→RGB→BGR만 수행하고 PDF 내장 텍스트는 모델 입력에 제공하지 않는다.
3. strict51문장/74제목·기존 Greek5·표적 micro16·Figure19를 같은 근거로 비교한다. parser failure/미검토를 성공으로 합치지 않는다.
4. 선택 근거를 기록하고 새 원본 Data→I 경로와 기존 profile 호환을 구현한다. 원본/파생 bbox·hash 구분, 재시도/coverage·projection 참조 회귀를 테스트한다.
5. 실제 Test_Paper 전체 파싱과 source 구조·근거 export를 확인하고, 영향에 맞는 격리 PG 테스트를 수행한다. 기본값 변경 후 새 profile이 실제 runner/model/input 방식에 결속되는지 확인한다.
6. 문서/targeted app checks·diff review와 Docker 정리를 마친다. 원시 Markdown 단독 pipe로 기존 전체 문서 검사 오류1건이 있음을 기준선으로 남기며 원문 수정으로 통과시키지 않는다.

실패는 새 attempt로 남기며 자동 fallback하지 않는다. 원본 DB/서비스는 변경하지 않고 검증용 별도 저장소를 사용한다. 동작 전환은 새 profile/default만 되돌릴 수 있으며 과거 I/Records를 재작성하지 않는다. AT22/23/25/27/33/68/69/71/90–102 등의 이번 변경 관련 단언과 실제 실행 범위를 기록하고 전체 AT를 완료로 올리지 않는다.

## 진행

- 기존 Docker 7컨테이너/13이미지/27볼륨과 GPU 여유 확인. Paddle 기존 digest `sha256:bae83def099a4fc88febeb122c29472720e14cd1a8c84460d310f05ef94c4dee`와 로컬 두 모델을 재사용한다.


## 후속 승인 — MinerU 이중 전사

사용자가 MinerU로 고정하고 원본 PDF 직접 처리와 PDF→200 DPI 이미지 OCR을 비교하도록 명시했다. 일반 문자는 원본 PDF 처리 우선, 그리스 문자·위첨자·특수문자가 다른 국소 구간은 OCR 우선이다. 이는 새 선택 전사 생성에 대한 승인이고 과거 원문/raw/I 수정 권한이 아니다. 모호한 정렬, 미지원 수식 등은 native 유지와 검토 표시로 남긴다. 원본 auto 경로가 스캔 페이지에서 내부 OCR을 사용할 수 있어 실제 `_ocr_enable` 값을 양쪽에 기록한다.

- Paddle 비교 완료: 17편/51페이지, strict 문장 MinerU41/51 vs Paddle37/51; 제목50/74 vs45/74. Greek5·micro16은 양쪽 모두 표시 동등성 회복. Figure19의 단일 crop 완전 보존15 vs2, crop 집합16 vs3. 표본 품질 검토이며 논문 전체 정확도는 아니다.
- Paddle source 검증: 17편/51페이지, 1,112 blocks, 124 crop assets, 모두 hash/geometry 통과, sampled schema의 whole-document attach 거부 확인. source I/DB 쓰기0.
- 신규 기본 adapter `mineru-hybrid-dual200-v1`: MinerU3.4.5 Hybrid high + Pro2605 1.2B, 원본 auto + image200 auto. 기존 `mineru-hybrid-preproc-v1`은 명시적 native 옵션과 과거 profile에서 유지한다.
- `pdf_raster`는 원본 SHA/페이지/좌표 변환과 PNG·image-only PDF 픽셀 검증을 기록한다. `pdf_raster_adapter`는 derived bbox를 원래 페이지 좌표로 명시적으로 변환한다. `transcription_selection`은 국소 glyph 선택과 exact raw 범위를 기록한다. `dual_adapter`는 두 raw 전체를 검증·보존하고 새 I를 조립한다. 후보 선택은 의미 판정이나 사실 검증을 뜻하지 않는다.


## 통합 검증 진행 — 이중 전사

- 새 공통 renderer 원본 geometry/PNG/image-only 픽셀 검증과 mapper 회귀를 추가했다. 기존 native/Paddle adapter와 원문 이력은 불변이다.
- 독립 검토에서 일반 identifier/URL의 underscore를 첨자로 바꾸던 오류와 OCR model/origin 파일 누락을 받던 receipt 빈틈을 수정했다. 실물 첫 전사에서 발견한 β 삽입 공백 위치도 v3에서 수정했다. 문제가 발견된 earlier attempt/profile/raw는 보존하며 canonical로 반영하지 않는다.
- 최종 selector는 `native-ordinary-ocr-special-v3`; source I 저장과 comparison needs_review를 명시적으로 구분한다. 불확실한 block은 native 그대로, 변경0개이며 ledger·durable receipt·materialize/replay 응답에 검토 상태를 기록한다.
- 앱 Docker build exit0. 격리 PostgreSQL18/pgvector의 전체 앱 테스트 최종296개/30.724초/실패0/skip16. skip16의 PDF 의존성은 기존 Hybrid runtime의 native PDF22tests/0.775초/실패0/skip0으로 별도 검증했다.
- 첫 real parser raw를 최종 v3로 읽기 전용 재생: 14페이지, native/OCR각229blocks, source제안229(Text193/Image36), 선택8곳, 비교검토14blocks, 미대응OCR8blocks. 이 재생은 canonical0이며 첫 parser profile의 이전 implementation hash를 새 승인 실행으로 둔갑시키지 않는다. 최종 전체 v3 profile 실행·PG 반영은 별도다.
- 선택8건 시각 검토: 실제 누락 β1곳, 이미맞았던 µ/첨자표기 변경5곳, native U+2212에서OCRASCII hyphen으로선택2곳이다. 8개를8개정확도개선으로세지않는다. p10caption의 `P <`3개누락은 ordinarynative 정책 때문에남는다. 원본/두raw/페이지이미지로추적가능하다.

## 최종 완료 — 이번 비교와 기본값 적용 범위

최종 v3 profile로 Test_Paper 14페이지를 새로 이중 파싱했다(597.797초). 격리 PostgreSQL 18.6/pgvector 0.8.6에 source I 229개(Text193/Image36)를 저장하고, 재시도의 동일 ID·모든 I/content/grounding·bundle hash·14페이지 조회를 확인했다. 선택 8건과 검토 14 blocks, 미대응 OCR 8 blocks는 비교 상태에 공개한다. 원본 Figure 6개와 페이지 14개를 포함한 evidence를 생성했으며 실제 reader 결과가 저장 bundle과 일치했다. β의 v3 선택과 모든 선택의 원시 근거도 다시 대조했다.

최종 앱 296 tests(16 skip), PDF runtime 22 tests(0 skip)에 실패는 없다. 문서 Linux local fixture 44 tests는 raw Markdown 표 오탐으로 1 failure이고 실행 오류는 없다. 실제 저장소의 최종 validator도 보존 raw의 delimiter 오류 9건으로 exit 1이며 원문을 수정하지 않았다. 임시 컨테이너와 전용 network를 정리했고 새로 남은 이미지는 검증한 최종 앱 하나다. 기존 Docker 자원과 새 검증 DB/Artifact 볼륨은 보존했다.

[최종 결과·명령·한계](T03_dual_transcription_result.md), [기계판독 결과](T03_dual_transcription_result.json), [원문 근거 패키지](../output/t03-dual-transcription/evidence-v3/README.md)를 따른다. 이번 slice 완료와 T03 전체 acceptance 및 I2K 이후는 구분한다. 추가 승인 대기 항목은 없다.
