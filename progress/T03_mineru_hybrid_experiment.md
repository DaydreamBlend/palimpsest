# T03 — MinerU Hybrid + Pro 1.2B 비교 결과

2026-09-10. 사용자가 요청한 MinerU Hybrid + Pro 1.2B를 네 논문 43페이지에서 시험했다. **파싱은 모두 성공했고 PaddleOCR-VL보다 이번 관찰 실행 시간이 짧았지만, 기존 소제목 누락 39개 중 독립 제목 복구는 0개다.** Figure5의 crop은 개선됐고 Figure6H 범례 잘림은 남았다. source/원시 결과는 보존했으며 이번 Hybrid 비교에서 사용자 Canonical Store에 쓰지 않았다.

## 이전 MinerU도 GPU 실행이었다

이전 Test_Paper의 [실제 parse receipt](../output/t03/parser/01a0853c-03d8-72ff-be35-958d8dae8db5/1-873c01ff0766433fb85a51511da1ed35/parse_result.json)와 [추가 논문 parser profile](../output/t03-qwen35-original/runtime/parser-profile.json)은 `backend=pipeline`, `device=cuda`, RTX4060Ti, Torch2.8.0+cu128/CUDA12.8을 기록한다. Pipeline은 CPU 실행도 지원하지만 당시 실행은 CPU-only가 아니었다. 이번 비교 축은 Pipeline→Hybrid+Pro이다. 모든 세부 연산이 GPU에서만 수행됐다는 뜻은 아니다.

## 실행 프로필

- MinerU3.4.5, `hybrid-engine`, `effort=high`, 실제 해석 엔진 Transformers4.57.6. mineru-vl-utils1.2.1, Torch2.8.0/CUDA12.8. 기존 이미지에 Accelerate1.15.0/psutil7.2.2만 hash lock으로 추가했다.
- 공식 모델 [opendatalab/MinerU2.5-Pro-2605-1.2B](https://huggingface.co/opendatalab/MinerU2.5-Pro-2605-1.2B), revision `bff20d4ae2bf202df9f45284b4d43681555a97ed`. 원본 weight2,312,126,640 bytes, SHA256 `abf8681ca63b8dec7b67de257af47b821f179442f72998d0696ae2ed9232a5f0`. 13개 공개 파일의 크기/hash를 검증했다.
- 이미지 ID `sha256:3f9361035fa4d601d54ed524410d89871fe2524047b04a821594485aae93e0d4`. 로컬 read-only pipeline/pro model과 PDF, Docker network none. 실제 mount/종료 상태는 [container receipts](../output/t03-mineru-hybrid-pro/runtime/container-receipts.json)에 보존했다.
- method auto/language ch/formula true/table true/image-analysis false. 페이지 count·원본/재직렬화 PDF geometry·Data hash 전후 일치, resolved Transformers 엔진과 모델 manifest를 검증한다. 기존 pipeline config는 수정하지 않고 attempt별 local config를 만든다.
- Hybrid가 생성한 `_model.json`, 후처리 `_middle.json`, 원본 그대로의 source.pdf, 재직렬화 `_origin.pdf`, crop, 로그와 SHA inventory를 함께 남긴다. Hybrid의 문단/페이지 간 표/제목 후처리는 여전히 있으므로 middle을 모델 원응답이나 완전한 원문 전사라고 표현하지 않는다.

모델 자체의 smoke는 CUDA/BF16 로딩과2.31GB parameter allocation을 확인했다. 이것은 실파싱 peak VRAM 측정이나 반복 재현성 검증이 아니다. runtime의 생성 설정은 설치 코드 근거와 별도로 구분한다. 문서당1회이며 K 생성/Q4 의미 모델 호출은 없다.

설치 코드의 [실효 생성 설정 분석](../output/t03-mineru-hybrid-pro/evaluation/generation-parameters.json)에서는 Transformers 호출에 `do_sample=False`가 명시되고 temperature/top_p/top_k는 None으로 덮어쓰이는 것을 확인했다. 모델 폴더 generation_config의 do_sample=true가 이 경로의 실제 설정이라는 뜻은 아니다. repetition_penalty1.0/no_repeat_ngram_size100/use_cache true이며 dtype=auto는 모델 config의 BF16을 선택하는 코드 근거다. 별도 seed/deterministic-kernel 설정 및 반복실험은 확인하지 않았으므로 수학적 재현성 인증으로 확대하지 않는다.

## 동일 원본에서 관찰한 실행 시간

| 문서 | 페이지 | 같은 문서에 사용한 GPU | PaddleOCR-VL1.6 | Hybrid+Pro high |
|---|---:|---|---:|---:|
| Test_Paper |14|RTX5080|394.001초|239.473초|
| Nassar |10|RTX4060Ti|312.069초|174.455초|
| Torchinsky |5|RTX5080|228.349초|125.774초|
| Wallet |14|RTX4060Ti|613.443초|173.496초|

각 값은 모델 다운로드를 제외한 해당 runner의 완료 경과시간이며 초기화/파일 검사/저장을 포함한다. 서로 다른 GPU에서 논문 두 편을 병행했고 runner와 추론 batching도 다르다. 1회 관찰값이며 무작위 반복·통제된 속도 benchmark는 아니다.

## 고정된 제목 평가

기존 source oracle와 평가기28개 SHA를 유지했다. Hybrid 결과를 보기 전에 추가 projection10개 파일을 [동결](../output/t03-mineru-hybrid-pro/review/frozen-projection.json)했고 label을 변경하거나 제목을 추가로 승격하지 않았다. 기존 MinerU 결과에도 동일 projection/scorer를 실행했다. 정확한 제목 경계는 원래 제목 label을 가지면서 해당 block 전체가 oracle 제목과 같아야 한다. 본문을 포함한 큰 block은 성공으로 세지 않는다.

| 명확한 제목의 정확한 경계 | 기존 MinerU Pipeline | PaddleOCR-VL1.6 | Hybrid+Pro high |
|---|---:|---:|---:|
| Test_Paper |23/23|22/23|23/23|
| Nassar |5/26|5/26|5/26|
| Torchinsky |1/5|1/5|1/5|
| Wallet |5/23|7/23|6/23|
| 추가 논문3편 합계 |11/54|13/54|12/54|
| 기존에 누락된39개 중 복구 |0/39|0/39|0/39|

Hybrid는 기존 누락1개를 제목 label block 안에 포함했지만 뒤의 다른 내용까지 붙어 정확한 경계 복구는 실패했다. 추가3편에서 strict 제목 문구 존재는 Pipeline47/54, Paddle49/54, Pro47/54다. LaTeX·글자/공백·하이픈 차이에 민감한 문자열 지표이므로 모든 미일치를 원문 누락으로 해석하지 않는다. 원시 대응 문구/실제 전사 오류는 별도 검토한다. 기준 주석은 기존 Codex의 원문 검토이며 사람이 승인한 gold가 아니다. 전체 절 level/parent 정확도는 이번 시험에서 평가하지 않았다.

최종 Pro [점수](../output/t03-mineru-hybrid-pro/evaluation/final-a1/scores.json)는43페이지·72개 연결 crop에서 구조오류0/누락페이지0이다. 이는 평가 입력의 형식·좌표·해시 검사이며 모든 문자의 충실성이나 완전한 Figure 보존 인증이 아니다. [동일 기준의 이전 Pipeline 점수](../output/t03-mineru-hybrid-pro/review/old-compat-attempt1/scores.json), [Paddle 점수](../output/t03-paddleocr-vl16/inspection/final-score.json).

[3-way 비교 JSON](../output/t03-mineru-hybrid-pro/evaluation/comparison.json)과 [평가 receipt](../output/t03-mineru-hybrid-pro/evaluation/final-evaluation-receipt.json)에 전체 수치·7개 문자열 미일치 후보·실행 명령·입력과 결과 hash를 기록했다. 미일치 중4개는 표기 차이 후보이고3개는 Gas6 상첨자/Wallet의 β·α 등의 문자 손상 가능성으로 구분했다. 실패 문자열을 사후 정규화해 점수에 더하지 않았다. 네 parser receipt와 전체218 artifacts를 원본 Data/파일 SHA에 결합했고10개 projection 의존성 및28개 기존 평가 입력은 최종에도 불변이었다.

## Figure와 과학 표기

Test_Paper 주 Figure6개의 영역은 모두 남는다. Figure별 선택된 crop 수는1→10,2→8,3→5,4→1,5→1,6→11이다. Figure4/5는 전체 Figure 형태이고 나머지는 패널 단위로 나뉜다.

이 문서의 실제 저장 JPG51개는 최종 참조36개와 Figure4의 중간 패널7개/Figure5의 중간 패널8개다. 뒤의15개를 원문 누락으로 세지 않는다. 두 Figure가 최종 whole-Figure 표현으로 합쳐졌고 중간 이미지도 원시 산출물에 보존된다.

- Figure5의 단일 crop에는 Paddle에서 잘렸던 Figure5A 마지막 범례와 Figure5F `72 h post-treatment` 문구가 온전히 남는다.
- Figure6H 첫 plot crop은 공통 범례 오른쪽이 여전히 잘린다. 이웃 crop에도 해당 부분이 포함되지 않고 별도 text/footnote로 복구되지 않은 것을 확인했다. 원본 PDF는 보존된다.
- 캡션 시작6개와 다음 페이지 이어짐2개 영역은 있으나 문자 인식은 완전하지 않다. Figure2의 `FIGURE`/단어 전사와 Figure5 continuation의 통계 기호·P 표기 등을 원본과 대조했다. 실제 캡션 영역 존재와 정확한 문자열 보존을 구분한다.

[독립 시각·provenance 검토](../output/t03-mineru-hybrid-pro/visual-review/Test_Paper-a1-visual-qa.md)와 [전체 근거 JSON](../output/t03-mineru-hybrid-pro/visual-review/Test_Paper-a1-visual-qa.json)에 원본 페이지, 실제 crop, 캡션 locator와 SHA를 기록했다. Figure 5의 이어진 캡션에서 원본 `*P < 0.05, **P < 0.01, ***P < 0.001`는 `* 0.05, ** 0.01, *** 0.001`로 전사됐고, H 설명의 `TGF-β`도 한 곳에서 `TGF-`로 손실됐다. 읽기 전용 audit는 원본 PDF와 receipt의 산출물 61개, 보호 입력 65개의 검토 전후 SHA를 확인하고 exit 0으로 끝났다. 파일 무결성 통과와 전사 품질 실패를 구분한다.

페이지 provenance에는 `preproc_blocks`를 사용해야 한다. 같은 문서의 `preproc_blocks`와 `para_blocks`를 비교하면 페이지를 제외한 1,071개 span의 문자·bbox·image_path는 같지만, `para_blocks`의 90개 span은 다른 페이지 컨테이너로 이동했다(p5→p4 16개, p8→p5 47개, p13→p12 27개). 이동 표시에 `cross_page:true`는 있지만 원래 page index는 없다. 따라서 합쳐진 문단의 컨테이너 페이지를 해당 span의 출처로 사용하면 안 된다. 이번 평가 projection은 합치기 전 `preproc_blocks`를 선택했으며, 위 JSON에 이동한 90개 span의 이전·이후 locator를 보존했다.

파서를 바꾸는 것만으로 현재 D2I의 완전한 Figure/범례와 inline 소제목 문제를 해결하지 못한다. 다음 보완은 원본 PDF의 font/span 정보를 사용한 소제목 후보 수집과 page/전체 Figure 표현을 함께 제공하는 projection, parser 전사와 원본 text layer의 불일치 검출이 적절하다. 이는 이번 비교에서 구현·검증한 기능이 아니며 의미 요약이나 가치 선별을 D2I에 다시 넣는 제안이 아니다.

## 검증과 완료 경계

공식 모델 다운로드/해시, 실제 CUDA 로딩, 네 문서 실파싱·원본 페이지/SHA 검증, frozen projection/scorer를 실행했다. parser raw/중간 결과가 있고 사용자 DB 쓰기0이다. 기존 source I/Record/ID/hash는 유지한다. 현재 앱의 Hybrid compile/provider 경로를 새로 열거나 기본 parser를 추가 변경하지 않았다. 비교 실험 완료와 제품 기본값 채택은 별개이며, T03 전체 acceptance는 계속 in_progress다.

이번 연속 작업에서 Paddle adapter의 앱 검증210tests/35.590초/exit0와 격리 PG18 Test_Paper308I 저장 검증을 별도로 완료했다. 그것은 Hybrid의 PostgreSQL 연결 검증을 뜻하지 않는다. 문서 fixture 대용량 복사 문제도 수정했고 문서 tests44개/213.159초/exit0를 확인했다. 상세 실패/복구 이력은 [Paddle 실행 계획](T03_paddleocr_execplan.md), Hybrid 준비·실행 경계는 [이번 계획](T03_mineru_hybrid_execplan.md)에 보존한다.

Hybrid 요청에서 추가한 재실행 파일은 [Dockerfile](../deploy/mineru-hybrid/Dockerfile), [의존성 lock](../deploy/mineru-hybrid/requirements-delta.lock), [실험 runner](../output/t03-mineru-hybrid-pro/runtime/run_hybrid.py), [고정 projection](../output/t03-mineru-hybrid-pro/review/project.py), [시각 검증 스크립트](../output/t03-mineru-hybrid-pro/visual-review/audit_test_paper.py)다. 결과·진행 문서는 이 보고서, 위 실행 계획과 [STATUS](STATUS.md)를 갱신했다. 제품의 Hybrid adapter나 DB migration은 만들지 않았다.

정확한 projection/scoring 명령과 exit 0은 [평가 receipt](../output/t03-mineru-hybrid-pro/evaluation/final-evaluation-receipt.json)의 `commands`에 기록했다. 최종 문서 검사는 bundled Python으로 `python -X utf8 -B tools/validate_bundle.py`를 실행해 exit 0을 확인했다. 이는 문서 무결성 검사이며 실제 모델 품질 검사를 대체하지 않는다.

Hybrid 종료 컨테이너4개와 준비 컨테이너1개를 제거했다. Paddle의8개+격리 시험프로젝트3개 정리까지 합쳐 이번 연속 실험 컨테이너16개를 제거했고, 원래7개 컨테이너 및 모든 기존 볼륨이 보존됨을 마지막 목록과 대조했다. 최종 모델/이미지/원시 결과는 남긴다. [정리 receipt](../output/t03-mineru-hybrid-pro/runtime/cleanup-result.json).
