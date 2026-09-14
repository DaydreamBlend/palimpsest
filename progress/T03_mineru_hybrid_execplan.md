# T03 — MinerU Hybrid + Pro 1.2B 비교 실험

2026-09-10 사용자 후속 요청: “2번 MinerU Hybrid + Pro 1.2B도 시험해보자. 이전에 쓴 MinerU는 CPU only였어?”

## 목표와 경계

기존 MinerU 3.4.5 Pipeline, PaddleOCR-VL-1.6와 동일한 원본 Test_Paper 및 추가 논문을 사용해 Hybrid + 공식 Pro2605 1.2B의 제목 경계와 그림·캡션·좌표 보존을 비교한다. 기존 평가 입력/39개 누락 cohort는 추론 전 동결 상태를 재사용한다. 새 실험은 별도 `output/t03-mineru-hybrid-pro`에 보존한다. 이 요청은 비교 시험이며 앱 기본 parser 재변경이나 기존 canonical I 교체 승인이 아니다.

이전 MinerU는 CPU-only가 아니었다. `output/t03-qwen35-original/runtime/parser-profile.json`과 이전 source receipt에 CUDA12.8, Torch2.8.0, RTX4060Ti, backend pipeline이 남아 있다. 이번 변경 축은 Pipeline→Hybrid+Pro이며 GPU 여부가 아니다.

## 실행 계획

1. 공식 현재 버전/Pro model revision·SHA와 설치된 MinerU3.4.5의 실제 hybrid 엔진 계약을 확인한다.
2. 기존 CUDA/MinerU image와 read-only pipeline model volume을 재사용하고 필요한 Pro weights·최소 의존성만 별도로 추가한다. 다운로드는 공개 Hugging Face CLI로 수행하고 모델 hash를 기록한다.
3. 공개 SDK/CLI의 명시적 Transformers Hybrid backend를 사용한다. 추론은 network none, PDF/model read-only, 원본 SHA 및 원래 page/geometry를 검증한다. 자동 fallback은 사용하지 않는다.
4. Test_Paper와 동결된 추가 논문을 실행하고, backend 원시 JSON과 실제 crop/원본 페이지를 남긴다. 평가용 중간 표현만 명시적으로 정규화하며 raw를 다시 쓰지 않는다.
5. 같은 제목 경계·기존 누락 cohort, Figure6/캡션8 조각·crop 충실도, 원문좌표 및 실행시간을 대조한다. 구조 검사와 원문 인식 품질, model/engine 효과와 GPU 성능 차이를 구분한다.
6. 결과 보고와 이번 작업 소유 Docker container/불필요한 image 정리를 수행한다. 전체 모델·비교 raw·실패 로그·기존 DB/볼륨은 유지한다.

## 계약과 검사

AGENTS/PLANS/T03/CODE_REVIEW 및 승인된 원문 보존·Paddle 후속 계약을 따른다. 이번 비교에서는 I2K·K·Q4 의미 모델 호출이나 사용자 DB migration/쓰기 작업이 없다. 작은 실험 runner/evaluation projection만 필요하며 제품의 새 일반 provider 계층을 만들지 않는다.

진행 중. 수행한 명령, 실패와 수정, exact runtime/model profile, 미실행 범위를 완료 보고서에 남긴다. T03 전체 acceptance 및 후속 task 완료로 확대하지 않는다.

## 실행 중 기록

- official 최신 안정 MinerU3.4.5와 기본 Pro2605를 확인했다. 기존 이미지에는 Torch2.8.0/CUDA12.8, Transformers4.57.6, mineru-vl-utils1.2.1이 있다. Accelerate1.15.0과 psutil7.2.2만 exact hash lock으로 추가했다.
- Pro repository는 `opendatalab/MinerU2.5-Pro-2605-1.2B`, revision `bff20d4ae2bf202df9f45284b4d43681555a97ed`, 2,312,126,640 bytes weight SHA `abf8681ca63b8dec7b67de257af47b821f179442f72998d0696ae2ed9232a5f0`이다. HF CLI 다운로드162.331초, 공개 metadata의13개 파일 크기/hash 검증 통과.
- 최종 실험 이미지 `sha256:3f9361035fa4d601d54ed524410d89871fe2524047b04a821594485aae93e0d4`. 별도 CUDA 로딩 smoke는 RTX5080에서 Qwen2VLForConditionalGeneration/BF16/allocated2,312,097,792 bytes 확인. 파서 실제 profile과 smoke를 구분한다.
- 평가 projection은 새 추론 전 SHA `528af9eb680b397a5636825c24a29b2c183d2e661d0ae420c29696ec2e3722ce`로 고정했고, 이전28개 oracle 입력도 불변이다. 기존 MinerU 결과를 같은 projection/scorer로 재평가하여43p/구조오류0/누락0을 확인했다.
- runner는 모델 manifest·원본 SHA/geometry·실제 Transformer engine·network none을 확인하고 `_model.json`과 후처리 `_middle.json` 및 모든 crop을 보존한다. `high`, image-analysis false, auto/ch/formula/tabletrue를 명시한다. 실행에는 별도 frozen runner 파일을 read-only로 mount했다.
- Test_Paper-a1(14p/RTX5080)239.473초, nassar-a1(10p/RTX4060Ti)174.455초에 완료했고 원본 전후 hash와 모든 원래 페이지가 일치했다. Torchinsky/Wallet은 실행 중이다. Figure 시각 QA와 동결 제목 평가를 별도로 수행 중이다.
- inference 이전 host/Linux `check_runner.py` 및 `--help`가 통과했다. 이 작은 integrity 검사는 모델 추출 품질의 증거가 아니다. 현재 사용자 DB/canonical 쓰기0이다.

## 최종 상태

이번 비교 실험은 완료했다. [결과 보고서](T03_mineru_hybrid_experiment.md), [고정 점수](../output/t03-mineru-hybrid-pro/evaluation/final-a1/scores.json), [3-way 비교](../output/t03-mineru-hybrid-pro/evaluation/comparison.json)를 참조한다. Torchinsky125.774초/Wallet173.496초도 완료하여43페이지 전부 성공, raw/model/middle/원본218개 artifacts hash 검증 및 frozen evaluator/projection 불변을 확인했다.

기존 누락 39개 중 독립 제목 복구는 0개, 추가 3편의 정확한 제목 경계는 12/54다. Pro의 Figure 5 전체 crop은 Paddle의 잘림을 보완했으나 Figure 6H 범례와 과학 표기 전사 손실은 남는다. 전체 OCR·절 계층·일반 PDF 품질 승인이나 Hybrid 앱 통합 완료로 확대하지 않는다. 사용자 DB/canonical 쓰기는 0이고 제품 기본값을 추가 변경하지 않았다.

최종 실험 컨테이너 5개를 정리했고 모델·이미지·raw·기존 컨테이너 7개와 모든 볼륨은 보존했다. 다음 보완 후보는 원문 font/span 기반 제목 후보, 전체 Figure/페이지 근거 projection, parser 전사 차이 검사다. 이번 비교 범위에서 자동 착수하지 않으며 T03 전체는 in_progress를 유지한다.

[최종 시각 QA](../output/t03-mineru-hybrid-pro/visual-review/Test_Paper-a1-visual-qa.md)는 Figure 6개/캡션 8영역 존재와 위 손실 사례를 확인했다. `para_blocks`가 90개 span을 다른 페이지 컨테이너로 옮기는 동작도 확인했으므로 이번 projection의 `preproc_blocks` 선택을 유지한다. 원본 및 receipt 산출물 61개와 보호 입력 65개의 hash 검증은 통과했다.
