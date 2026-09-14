# T03 — PaddleOCR-VL 1.6 실험 결과

2026-09-10. 사용자 승인에 따라 로컬 PaddleOCR-VL 1.6을 실행했다. **네 문서 43페이지의 파싱과 source Information 제안 검증은 완료했지만, 기존 소제목 누락 39개 중 독립 제목으로 복구된 것은 0개다.** Test_Paper의 주 Figure 6개와 캡션은 확인했으나 일부 crop 잘림과 실제 OCR 오전사도 남아 있다. 파서의 종합 벤치마크 점수와 이 저장소의 원문 보존 요구 충족은 구분한다.

이 보고서는 Paddle 실험의 관찰 결과다. 제품의 기본 parser 선택을 추가 변경하거나 T03 전체를 완료 처리하지 않는다. 사용자가 추가 요청한 MinerU Hybrid + Pro 실험과 최종 비교는 별도 실행 범위다.

## 실행 환경과 재현 근거

| 항목 | 실제 실행값 |
|---|---|
| Parser | PaddleOCR 3.7.0 / PaddleX 3.7.2 / pipeline v1.6 |
| Layout 모델 | `PaddlePaddle/PP-DocLayoutV3_safetensors`, revision `97d101e6db2642e162a1d05392d1b0231c91033e` |
| VL 모델 | `PaddlePaddle/PaddleOCR-VL-1.6`, revision `c5630abae1d940eafe0697512a0325494b02ab42` |
| Engine | Transformers 5.17.0 / Torch 2.8.0, CUDA 12.8; layout FP32 / VL BF16 |
| Parser 이미지 | `sha256:bae83def099a4fc88febeb122c29472720e14cd1a8c84460d310f05ef94c4dee` |
| Model manifest SHA-256 | `e88058a440b3c1bc0136643943e6efcf5e452b4e25cbc79185095fd8431b9327` |
| GPU 0 | NVIDIA GeForce RTX 5080, 16303 MiB |
| GPU 1 | NVIDIA GeForce RTX 4060 Ti, 16380 MiB |
| NVIDIA driver | 616.56 |
| 입력·설정 | 원본 PDF read-only, 원본 CropBox를 scale 2로 렌더, 원본 page index 보존, seed 42, batch 1 |
| 보존 관련 설정 | `merge_layout_blocks=false`, orientation/unwarp 꺼짐, chart recognition/image OCR/formatting 꺼짐, `markdown_ignore_labels=[]` |
| 네트워크·의미 모델 | 파싱 시 Docker network none; application semantic LLM 및 Q4 보정 호출 0회 |

GPU는 각 문서에 하나씩 할당했다. 두 GPU의 VRAM을 합쳐 쓰지 않았다. parser의 VL 전사는 생성 모델을 사용하므로 application 의미 LLM 호출이 0회라는 사실이 파서 출력의 수학적 결정성이나 무오류를 뜻하지 않는다. 모델 다운로드 이후 고정된 로컬 모델로 실행했으며 원문을 원격 API에 보내지 않았다.

모델 파일별 hash는 [models-manifest.json](../output/t03-paddleocr-vl16/runtime/models-manifest.json), 실행 설정은 각 attempt의 `requested_pipeline.json`·`resolved_pipeline.yaml`·`status.json`, 입력/출력/평가 hash와 실제 실행 명령은 [최종 평가 receipt](../output/t03-paddleocr-vl16/inspection/final-evaluation-receipt.json)에 있다. Nassar a2는 runner hash를 status에 추가하기 전 실행한 시도로, 해당 필드가 없다는 이력도 원본 status에 그대로 남긴다.

## 네 문서의 실행과 source 제안

| 문서·채택한 attempt | 페이지 | GPU | 파싱 시간 | Text 제안 | Image 제안 | 전체 block/source 제안 |
|---|---:|---|---:|---:|---:|---:|
| Test_Paper a3 | 14 | RTX 5080 | 394.001초 | 243 | 65 | 308 |
| Nassar a2 | 10 | RTX 4060 Ti | 312.069초 | 197 | 64 | 261 |
| Torchinsky a1 | 5 | RTX 5080 | 228.349초 | 96 | 14 | 110 |
| Wallet a1 | 14 | RTX 4060 Ti | 613.443초 | 201 | 27 | 228 |
| 합계 | **43** | — | — | **737** | **170** | **907** |

각 시간은 runner의 `elapsed_seconds`로, 해당 실행의 pipeline 초기화·페이지 처리·저장을 포함하며 모델 다운로드는 포함하지 않는다. 다른 GPU에서 문서를 병행했고 그림·본문 양도 다르므로 이를 파서 간 통제된 속도 벤치마크나 전체 벽시계 시간으로 해석하지 않는다.

최종 adapter 검사는 네 문서 모두 `source_check.status=complete`이며 원시 parsing block 전부에 source 제안이 대응했다. page index, 좌표 범위, crop hash 및 exact raw text 보존을 검증했다. 이것은 **파서가 내놓은 block을 조립하는 경계의 완전성**이다. PDF에서 파서가 놓치거나 잘못 읽은 내용까지 완전하다는 뜻은 아니다. 전체 907개는 source 제안이며, 실제 PostgreSQL 저장은 아래 Test_Paper 308개에 대해서만 별도로 실행했다.

## 고정 제목 평가

평가 입력과 코드 28개는 추론 전 `2026-09-09T16:19:55.215210+00:00`에 고정했다. 최종 평가 시 모든 SHA가 일치했다. 최종 manifest는 네 문서 43페이지 전체이며 구조 오류 0, 누락 페이지 0이다. 평가의 기준은 이전 source-only oracle로, Codex의 주석이며 사람이 승인한 gold가 아니다.

다음 세 지표를 구분한다.

1. **원문 문구 존재:** 올바른 페이지의 어느 block에 정규화한 제목 문자열이 단어 경계를 지켜 포함됨.
2. **제목 label에 포함:** 그 문구가 `doc_title`·`paragraph_title` 등 제목 label의 block에 포함됨.
3. **정확한 제목 경계:** 제목 label을 가지며 block 전체 문자열이 해당 제목과 정확히 일치함. 본문까지 붙은 큰 block은 복구로 세지 않음.

| 명확한 제목만 평가 | 기준 제목 | 원문 문구 존재 | 제목 label에 포함 | 정확한 제목 경계 | 기존 누락 중 정확한 제목 복구 |
|---|---:|---:|---:|---:|---:|
| Test_Paper | 23 | 22/23 | 22/23 | 22/23 | 해당 없음 |
| Nassar | 26 | 24/26 | 5/26 | 5/26 | 0/21 |
| Torchinsky | 5 | 4/5 | 1/5 | 1/5 | 0/3 |
| Wallet | 23 | 21/23 | 7/23 | 7/23 | 0/15 |
| **추가 논문 3편 합계** | **54** | **49/54** | **13/54** | **13/54** | **0/39** |

기존 MinerU 3.4.5 출력에서 제목 후보로 선택되지 않은 명확한 제목 39개를 같은 cohort로 유지했다. Paddle에서는 이 중 36개의 문구가 strict 문자열 검사로 확인됐지만, **39개 모두 독립적인 제목 경계로 복구되지 않았다.** 나머지 3개도 아래처럼 대응 문구가 raw에 있으나 표기가 다르다. 파서 교체만으로 inline 소제목 분리가 해결되었다고 판단할 근거는 없다.

Torchinsky와 Wallet의 애매한 제목 각 1개는 별도 집계하며 위 54개에 포함하지 않는다. 둘 다 문구는 있으나 독립 제목으로 인식되지는 않았다. **전체 절 계층의 level/parent 정확도는 평가하지 않았다.** Raw label에는 완전한 문서 계층 예측이 없고, I2K 또는 Q4로 사후 보정해 파서 점수를 높이지 않았다.

평가기의 정규화는 Unicode·공백·일부 Markdown/HTML·대시만 다룬다. LaTeX를 임의 해석하거나 fuzzy matching을 추가하지 않았다. 모든 결과는 [final-score.json](../output/t03-paddleocr-vl16/inspection/final-score.json)에 있다.

## 문자열 미일치와 실제 오전사 구분

strict 문구 검사에 걸린 아래 6개는 대응 raw 문구를 별도로 확인했다. **이 관찰로 동결 점수를 고치지 않았다.**

| 문서·물리 페이지·block | 차이 | 실제 label/경계 |
|---|---|---|
| Test_Paper p5 b8 | `TGF-β`가 `TGF- $ \beta $` 형태로 전사 | 독립 paragraph_title 있음 |
| Nassar p3 b5 | `Gas6−/−`가 상첨자 LaTeX로 전사 | 제목 문구와 본문이 text block에 함께 있음 |
| Nassar p7 b13 | 동일한 Gas6 상첨자 표기 차이 | 제목 문구와 본문이 text block에 함께 있음 |
| Torchinsky p1 b3 | `TH17`이 `T_{H}17` LaTeX로 전사 | doc_title 있음 |
| Wallet p6 b2 | `β`가 LaTeX로 전사 | 독립 paragraph_title 있음 |
| Wallet p8 b3 | `CD11c+ CD8α+`의 표지 사이 공백 차이 | 제목과 뒤 본문이 하나의 text block |

별개로 Wallet p8 block 3에서는 **실제 내용 전사 오류**를 확인했다. 원본 페이지의 `NOD.MerTK` 상첨자 `KD/KD`가 raw text에서는 `NOD.MerTK⁰/¹⁰K⁺`로 네 번 나온다. 원본 page PNG를 직접 대조했다. 이는 위 제목 공백/LaTeX 일치 규칙과 다른 문제다. 원본 PNG·raw 결과는 그대로 보존했고 수정을 가하지 않았다. 이 단일 spot check는 전체 OCR 오류율이 아니지만, 구조 검사 통과가 과학적 표기의 충실도를 보장하지 않는 실제 반례다. 위치·bbox·hash는 최종 평가 receipt에 기록했다.

## Test_Paper Figure 검토

| Figure | 물리 페이지 | 원본 패널 | SDK visual crop | 캡션 페이지 |
|---|---:|---|---:|---|
| 1 | 3 | A–K | 13 | 3 |
| 2 | 4 | A–G | 15 | 4 |
| 3 | 6 | A–E | 7 | 6 |
| 4 | 7 | A–G | 9 | 7 |
| 5 | 9 | A–H | 8 | 9 → 10 |
| 6 | 11 | A–H | 11 | 11 → 12 |

**주 Figure 6개의 위치와 캡션 8조각, 그중 다음 페이지 이어짐 2개를 확인했다.** Figure 페이지의 visual crop은 63개이며 첫 페이지의 로고·Crossmark 2개와 구분한다. SDK가 Figure 전체를 통째로 담은 crop은 0개다. crop 개수를 주 Figure 개수로 사용하지 않는다.

a3의 실제 page PNG 14개와 crop 65개를 재해시하여 a2와 byte hash가 전부 같음을 확인했다. 모든 bbox·layout도 같으므로 이전 시각 관찰을 명시적인 동일성 근거로 a3에 적용했다. Figure 5A의 마지막 범례 하단, Figure 5F의 `72 h post-treatment` 상단, Figure 6H 공통 범례의 오른쪽 잘림이 남아 있다. 일부 plot의 범례는 별도 text block에 있어 단독 crop만으로는 문맥이 완전하지 않다.

Figure 2B는 누락 판정을 정정했다. B 전용 표지 block은 없지만 B 표지 픽셀은 A 타임라인 crop 오른쪽 위에 남아 있고 두 발 사진도 별도 crop으로 존재한다. 따라서 후속 application 모델이 B를 삭제했다는 증거가 아니다. 명시적 패널 표지와 이미지의 연결은 부족하다.

전체 페이지 PNG에는 잘린 범례 등이 온전히 남는다. SDK의 auto/polygon crop에는 마스킹도 관여할 수 있다. [a3 최종 시각 QA](../output/t03-paddleocr-vl16/visual-review/Test_Paper-a3-final-qa.md)와 [기계 판독 증거](../output/t03-paddleocr-vl16/visual-review/Test_Paper-a3-final-qa.json)는 Figure 존재·crop 충실도·전사 충실도·저장 검증을 각각 구분한다.

## 실패 이력과 수정 확인

- Test_Paper a1: 네트워크를 차단한 상태에서 SDK box annotation이 폰트 다운로드를 시도하여 실패했다. 선택적인 annotation 호출을 제거하고 원본 페이지 PNG·좌표·SDK crop을 보존하도록 변경했다. 실패 산출물은 별도 attempt에 남겼다.
- Test_Paper a2 및 Nassar a1: 파싱은 끝났지만 `merge_layout_blocks=true`가 여러 영역의 text를 첫 block bbox로 합치고 뒤 block을 비웠다. 원문 영역을 잘못 가리키므로 저장용 채택에서 제외했다.
- Test_Paper a3: merge를 끄자 p1의 reviewer/author 및 correspondence/affiliation, p4의 두 단 본문이 각각 원래 영역에 분리됐다. 비시각 빈 block은 8개에서 0개로 줄었다. 모든 채택한 최종 attempt의 43페이지에서 merge=false를 확인했다.
- 앱 검증 이력: 처음 207개/28.876초 통과, 후속 209개/30.763초에서 doctor 기대값과 test image의 worker 파일 누락으로 실패했다. 수정 후 최종 210개/35.590초가 통과했다. 실패 로그를 삭제하거나 성공으로 덮어쓰지 않았다.

SDK 내부에는 detector overlap filtering·formula formatting·긴 반복 전사 trimming 등이 있다. raw SDK JSON 보존은 PDF 픽셀과 모델 decoder 원응답까지 완전히 같은 문자열임을 뜻하지 않는다. 정적 검토와 런타임 관찰은 [pipeline-preservation-review.json](../output/t03-paddleocr-vl16/runtime/pipeline-preservation-review.json)에 구분되어 있다.

## 실제 실행한 검사와 저장 범위

| 검사 | 결과와 범위 | 증거 |
|---|---|---|
| Linux Docker `inspect_outputs.py /work` | exit 0; 네 문서 907개 source 제안과 전체 raw block 대응 확인. GPU·네트워크·canonical 쓰기 없음 | [inspection/results.json](../output/t03-paddleocr-vl16/inspection/results.json) |
| 고정 `evaluate.py score` | exit 0; 43페이지 전체, 구조 오류 0, 누락 0, crop hash 검사 168개 | [final-score.json](../output/t03-paddleocr-vl16/inspection/final-score.json) |
| 입력 동결 검증 | scorer가 시작할 때 28개 SHA를 재확인, 그대로 일치 | [frozen-inputs.json](../output/t03-paddleocr-vl16/review/frozen-inputs.json) |
| 실제 Test_Paper → I 저장 | 별도 `palimpsest-t03-paddle-verify` PG18/pgvector에서 308 I(Text 243/Image 65), UUIDv7, 중복 Data 거부, 동일 실행 재시도 ID 유지, 14페이지·앞뒤 페이지 조회, 125파일 export·raw/crop hash 보존 통과 | [actual-storage/result.json](../output/t03-paddleocr-vl16/actual-storage/result.json) |
| 전체 앱 테스트 | root가 격리 PG18 환경에서 실행한 최종 로그 확인: 210개/35.590초, OK. synthetic/unit와 PG integration 포함 | [app-tests04.log](../output/t03-paddleocr-vl16/runtime/app-tests04.log) |
| 문서·링크 검사 | `python -B tools/validate_bundle.py` exit 0, 별도 두 보고서의 상대 링크 누락 0. 문서 무결성 검사이며 application 검증과 구분 | 최종 보고서 작성 후 실행 |

전체 Image 제안 170개 중 Test_Paper와 Nassar의 `header_image` 2개는 frozen scorer의 image label 집합에 없어 crop 채점 manifest에서 제외된다. 이 두 자산은 adapter와 source 제안에 보존됐다. 이 차이를 맞추려고 frozen scorer나 원본 label을 바꾸지 않았다.

실제 저장 검증의 application semantic LLM 호출은 0회이고 `semantic_checked=false`다. 사용자 개발 DB는 수정하지 않았다. 실제 PDF를 격리 DB에 저장한 결과와 synthetic integration만 통과한 결과를 구분한다. 이 보고서 작성 단계에서는 추가 canonical 쓰기를 하지 않았다.

최종 평가 명령은 다음과 같다. 전체 Docker 명령·mount·exit code는 최종 평가 receipt에 그대로 보존했다.

```text
docker run --rm --network none --read-only --tmpfs /tmp --env PYTHONPATH=/workspace/src --volume C:/Users/DaydreamBlend/Documents/Codex/Palimpsest:/workspace:ro --volume C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/output/t03-paddleocr-vl16:/work --entrypoint python palimpsest-t03:0.2.0 -B /work/runtime/inspect_outputs.py /work

C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -B output/t03-paddleocr-vl16/review/evaluate.py score --manifest output/t03-paddleocr-vl16/inspection/manifest.json --output output/t03-paddleocr-vl16/inspection/final-score.json
```

## 상태와 남은 검증

**T03는 in_progress다.** 이 실험의 parser 실행, 고정 제목 평가, Test_Paper Figure QA 및 격리 저장 검증은 끝났다. AT68/69/71/76 및 source coverage 관련 AT104/105의 부분 근거이며, 전체 PDF 충실도나 T03 전체 acceptance 통과로 확대하지 않는다.

현재 남은 문제는 독립 소제목 경계 복구, 완전한 Figure/범례 문맥 제공, 파서 오전사의 탐지와 원문 재확인이다. 전체 절 계층은 아직 평가하지 않았다. 후속 MinerU Hybrid + Pro 비교에도 동일 원본·고정 기준을 사용하되 결과를 보기 전에 평가 기준을 바꾸지 않아야 한다. 과거 I/Record/ID/hash는 그대로 유지한다.
