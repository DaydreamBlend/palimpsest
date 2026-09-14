# PDF 원문 근거와 조회 projection

**2026-09-11 최신 입력 정책:** [I 우선·필요 시 원본 PDF](../decisions/I2K_I_FIRST_SOURCE_ON_DEMAND.md)에 따라 I2K는 I content/provenance만 먼저 전달하고 필요 판단 시 원본 PDF를 제공한다. 아래 evidence 조회는 원본 페이지/이미지 descriptor까지 보존한 로컬 근거 조회이며 모델 payload 직렬화나 자동 원본 첨부가 아니다. Image I 자체의 media는 최초 I에 포함한다. T04가 입력 선택·원본 요청/전송·실제 사용 이력을 구현한다.

2026-09-11 [전체 문서·절 읽기·Figure 참조](../implementation/SECTION_CONTEXT.md)도 이 파일의 `read_evidence` 검증을 재사용한다. `information sections/section-context/document-context`는 추가 parser/LLM 호출 없이 전체 source를 읽기용으로 구성한다. 전체 문서 조회는 순서대로 한 번 결합한 text와 exact spans, 별도 원본 페이지 PNG·Figure/panel 색인을 제공한다. 이미지 descriptor는 실제 모델 전송과 구분한다. canonical I 결속은 선택한 완료 source execution과 exact bundle 일치가 필요하며, context 조회에는 해당 projection SHA도 요구한다. 과거 evidence manifest와 parser raw/visual/paragraph 산출물은 덮어쓰지 않는다.

현재 [이미지 OCR 기본값](../decisions/MINERU_IMAGE_DEFAULT.md)에도 같은 build/read CLI를 사용한다. evidence v2의 `image_transcription`과 `parser_raw/`에 단일 OCR tree, 원본 PDF, raster manifest·PNG·derived PDF·renderer를 보존하고 read 때 공통 image adapter로 bundle과 문단을 재현한다. `rendered_source_pages`는 실제 OCR 입력인 동일 200 DPI PNG descriptor와 원본/파생 좌표 transform을 제공하며 경로 기준은 `parser_artifact_base_directory`다. 기존 `page_images`의 표시용 144 DPI 이미지와 구분한다. PDF I2K의 multimodal 호출 자체는 아직 T04 구현 범위다.

직전 [이중 전사 후속 승인](../decisions/MINERU_DUAL_TRANSCRIPTION.md)의 evidence도 유지한다. 원래 문단 text/offset, `selected_text`/`selected_segments`, `transcription_selection`, exact 양쪽 raw refs를 보존하고 read 때 dual adapter로 선택 결과를 재검증한다. 과거 이력의 profile/hash를 새 이미지 기본값으로 바꾸지 않는다.


[사용자 후속 승인](../decisions/MINERU_HYBRID_SELECTION.md)에 따른 T03 보완이다. MinerU Hybrid + Pro2605 1.2B high의 고정 실행 결과와 원본 PDF를 결합한다. 문서·그림 원문은 신뢰하지 않는 입력이며 코드 실행 지시나 권위로 취급하지 않는다.

## 실행과 읽기

등록·새 파싱·source I 생성은 기존 `tools/run_d2i.py`의 `--parser mineru-hybrid` 기본 경로다. Pipeline 또는 Paddle은 명시적으로 선택할 수 있고 자동 fallback은 없다. 모델과 이미지 및 실행 코드 hash를 profile에 기록한다.

이미 보존된 동일 조합의 실행에 PDF 보완을 만들 때는 다음을 사용한다. 별도의 모델 추론이나 DB 등록을 반복하지 않는다.

```powershell
python tools/run_pdf_evidence.py --parse-result output/t03-mineru-hybrid-pro/parse/Test_Paper-a1/parse_result.json --output output/t03-pdf-evidence/Test_Paper
```

worker는 기존 고정 Hybrid 이미지에서 설치된 PDFium으로 native 문자·글꼴·좌표와 페이지 이미지를 읽는다. source/model은 읽기 전용이며 network none이다. 출력은 새 디렉터리여야 한다. 다른 보존 결과를 덮어쓰는 옵션은 없다.

```text
palim information evidence-context --directory <evidence-directory> --page 9 --json
```

이는 DB 쓰기·model 호출 없이 complete manifest와 파일 hash를 확인한 뒤 현재 물리 페이지와 앞뒤 페이지를 반환한다. `python -m palimpsest.pdf_evidence context`도 같은 service를 호출한다. 앱 이미지에는 native PDF library를 추가하지 않아도 읽기 명령을 사용할 수 있다.

## 모듈과 의미

- `pdf_text_evidence.py`: native PDF 문자의 exact index·font·size·flags·bbox, typography 소제목 후보, PDF/파서 양쪽 전사와 원문 참조를 가진 불일치 검토 항목.
- `pdf_visual_evidence.py`: 원본 페이지 렌더, 원시 panel bytes와 bbox, native image/레이아웃 근거에서 도출한 전체 Figure 영역 제안. 경계가 확정되지 않으면 uncertainty와 전체 페이지 근거를 제공한다.
- `paragraph_projection.py`: `para_blocks` 내용과 정확히 일치하는 원래 `preproc_blocks` span을 연결한다. 중복 후보로 원래 페이지가 모호하거나 전사가 달라 일치하지 않으면 해당 상태와 가능한 원문 refs를 보존한다. source page를 para 컨테이너 page로 덮어쓰지 않는다.
- `pdf_evidence.py`: 원본/receipt/artifact hash 검증, 위 sidecar 결과와 보존할 출력 manifest, 읽기 service 결합. `tools/run_pdf_evidence.py`와 `palim`은 얇은 CLI adapter다.

모든 projection ID는 조회용 anchor이며 새 canonical UUID나 Knowledge Node가 아니다. 원문 I 및 기존 provenance를 재작성하지 않는다. 본문·caption·reference를 가치로 제거하지 않는다. 후보와 discrepancy는 원문을 자동 수정하거나 제목을 canonical 사실로 승격하지 않는다. 페이지 밖에 이어지는 문단도 source refs를 유지한다. 원래 parser 이미지 경로는 provenance locator로 남기고, `display_asset`/`copied_asset` 및 `source_asset_resolution`으로 실제 복사본을 연결한다. 이 표시용 자산은 반환된 asset base에 상대적이다.

`pdf-evidence-v2`는 마지막에 원자적으로 게시된 `manifest.json`의 `state=complete`가 완료 표식이다. 중간 `status.json`의 `artifacts_verified`만으로 완료를 표시하지 않는다. 읽기는 모든 파일 hash와 각 sidecar의 Data·bundle·middle 연결을 확인한다. 이전 v1 산출물의 읽기 호환성은 유지한다.

## 한계와 검증

native text가 없는 scanned page에는 상태를 명시하며 다른 OCR을 조용히 실행하지 않는다. 회전·CropBox 좌표 대응이 검증되지 않으면 실패한다. 레이아웃 기반 alignment와 후보 검출은 휴리스틱이며 모든 전사 오류/제목의 검출을 보장하지 않는다. 고정 source에 대한 script 반복 결과와 파서 VLM 자체의 반복성은 별개다.

원본 PDF·native text와 parser 전사는 각각 보존된다. 파일 hash 일치는 원문 의미·OCR 정확도·전체 Figure fidelity 승인이 아니다. 실제 결과와 미실행 AT 범위는 [실행 계획](../../progress/T03_pdf_evidence_execplan.md)에 기록한다. T03 전체 gate와 I2K 이후 실행은 별개다.
