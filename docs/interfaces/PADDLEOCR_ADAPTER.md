# PaddleOCR-VL source adapter

현재 parser 선택은 [2026-09-10 사용자 후속 승인](../decisions/PADDLEOCR_SELECTION.md)에 따른다. Python/Docker CLI와 원문 보존 계약은 유지한다. [실험 계획과 검증](../../progress/T03_paddleocr_execplan.md)은 실제 추론 품질과 앱 구조 검사를 구분한다.

## 고정된 실행 경로

PaddleOCR 3.7.0 / PaddleX 3.7.2 / PaddleOCR-VL-1.6 전체 pipeline, Transformers 5.17.0 / Torch 2.8.0 CUDA 12.8을 사용한다. PP-DocLayoutV3는 FP32, 0.9B VL 모델은 BF16이다. 두 모델의 exact repository revision과 파일 SHA-256은 로컬 `models/manifest.json`에 기록하고 실행 전에 모두 대조한다. 이미지 digest, GPU, 구현 파일 hash는 compilation profile에 남긴다.

PDF를 원래 CropBox에서 scale 2로 렌더링한다. 현재 worker는 회전 0과 유효한 CropBox만 지원하고 다른 경우 명시적으로 실패한다. orientation/unwarping, 텍스트 formatting, layout block merging, chart-to-table 생성, image OCR, seal recognition은 끈다. 페이지 render와 SDK raw JSON·Markdown·crop·요청/실효 설정은 모두 noncanonical parse artifacts로 남긴다. 원문은 read-only mount하고 추론 container network는 `none`이다.

`merge_layout_blocks=False`는 필수다. SDK 기본 병합은 다른 영역의 문구를 첫 block에 합치면서 bbox는 첫 영역에만 두어 grounding을 손상시킨다. adapter는 병합이 켜졌거나 설정을 확인할 수 없는 formal raw 결과를 거부한다. Markdown 제외 label은 빈 목록이지만, SDK 자체의 layout 필터가 검출 후보 일부를 제외할 수 있으므로 전체 원문 충실성은 별도 실물 검토가 필요하다.

## Raw와 Information 경계

`paddleocr-raw-v1`은 원본 Data hash, page count, model manifest hash, package versions와 순서대로 모든 원래 페이지를 담는다. 각 페이지의 `result`는 SDK의 원시 결과이고 `render_size`, `pdf_size`, `cropbox`, `image_assets`는 worker가 생성한 검증 가능한 receipt다. ndarray 입력의 SDK `page_index=null`은 고치지 않고 바깥 `page_index`에 실제 PDF index를 기록한다.

`paddle_adapter.normalize_paddle`은 MinerU 형식을 거치지 않고 기존 source bundle을 만든다. pixel bbox는 검증된 render 크기 비율로 PDF point에 변환하고 원래 bbox·다각형·block order·group ID·raw locator/hash를 보존한다. 읽기 순서는 SDK 배열 순서이며 nullable `block_order`를 임의로 채우지 않는다. 페이지 projection은 `paddleocr_array_order`와 `paddleocr_index`를 표시한다.

모든 parsed block은 기존 `source_units` builder/checker를 통과한다. 경로 이탈·symlink·crop hash 불일치·잘못된 좌표·모델 profile 불일치·누락 페이지·지원하지 않는 label은 실패한다. 같은 Data의 기존 I를 바꾸거나 다른 Data와 dedup하지 않는다. parsed block accounting은 원래 PDF 전체 내용의 인식 정확도 인증이 아니다.

image/chart crop은 Figure 전체와 동일한 단위가 아니다. 패널·범례·패널 문자·캡션이 별도 block일 수 있으며, 새 파서에서 일반적인 전체 Figure grouping은 아직 제공하지 않는다. 기존 MinerU reviewed Figure map의 자동 재사용을 거부한다. 원시 페이지 이미지와 PDF는 시각 감사 근거로 보존한다.

## 로컬 실행

이 저장소의 검증된 CUDA base image와 manifest에 대응하는 로컬 model 디렉터리가 선행 조건이다. `Dockerfile`은 해당 base digest를 사용하고 새 의존성은 exact hash lock으로 설치한다. 모델을 Docker image 안에 다시 복제하지 않는다.

```powershell
docker build -t palimpsest-paddleocr:3.7.0-vl1.6 deploy/paddleocr
docker compose -p palimpsest-dev build app
$env:PYTHONPATH='src'
python -X utf8 -B tools/run_d2i.py --parser paddleocr-vl --data-id DATA_SHA256 --project palimpsest-dev --work-dir output/new-paddle-source --generation GENERATION
```

Data는 먼저 Palimpsest import로 등록한다. 이미 존재하는 Data는 재등록하지 않고 그 hash를 사용한다. `GENERATION`은 기존 이력을 덮어쓰지 않는 명시적 새 실행 번호다. 기본 model path는 `output/t03-paddleocr-vl16/models`, image는 위 tag이며 각각 `--models-volume`, `--parser-image`로 명시할 수 있다. 다른 모델/버전을 자유롭게 받아들이는 일반 provider 계약은 아니다.

원시 결과를 별도로 연결하는 CLI는 `jobs parsed --raw paddle_raw.json`을 지원하며 기존 `--middle`도 같은 인자의 호환 alias다. durable job claim, retry, CAS 저장 및 atomic I/Record/outbox commit은 기존 Compiler Runtime을 재사용한다. 실패 시 다른 파서로 자동 전환하지 않는다.
