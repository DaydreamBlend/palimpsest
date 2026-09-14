# Qwen3.5-9B Q8_0 추가 문맥 검토 결과

**명확한 Abstract·문장 경계 후보는 잘 판정했지만, 잘못된 Figure 연결을 세 번 모두 통과시켰다. 현재 스크립트와 Q8을 조합해 논문 전체의 문맥 묶음을 자동 승인하기에는 남은 문제가 있다.** 원문은 보존됐으며 이 시험에서는 source I나 canonical K를 변경하지 않았다.

사용자 요청은 “9B Q8 좀 더 테스트해줘.”이다. 앞선 Test_Paper만의 평가를 확장해 Chen 2009, Clarke 2015, Dejani 2018 세 논문을 사용했다. 모델 성적을 보고 문서를 고르지 않고 단일단 저자 원고, 양단 구성, 별도 Significance 상자와 페이지를 넘는 캡션 등 문서 구조를 기준으로 선정했다. 이전 D2I 실험에 사용된 자료이므로 완전히 미노출된 holdout이나 모델의 학습 미포함 자료라고 주장하지 않는다.

## 결과

12개 고유 판정 사례를 각각 3회 실행했다. 기대값과 필수 evidence 조건은 응답을 읽기 전에 고정했고, 모델에는 원문과 검토용 proposal만 제공했다. 각 호출은 독립적이며 짝의 정답을 함께 보여 주지 않았다. 서로 다른 사례·문서를 포함하는 균형 평가로, 모든 정상/오류 사례가 동일 입력의 엄밀한 대조쌍인 것은 아니다.

| 판정 종류 | 고유 사례 | 3회 반복 선택 정답 | 선택과 필수 근거 모두 충족 |
|---|---:|---:|---:|
| 정상 제안 유지 | 6 | 18/18 | 18/18 |
| 실제 Abstract 재분류 | 2 | 6/6 | 3/6 |
| 잘못 나눈 Methods·Results 문장 병합 | 2 | 6/6 | 6/6 |
| 잘못된 연결·근거 부족 보류 | 2 | 3/6 | 3/6 |
| 합계 | **12** | **33/36 (91.7%)** | **30/36 (83.3%)** |

- 출력 구조 유효성: 36/36. 이유 코드의 사전 기준 적합성: 21/36 (58.3%). 알려진 ID를 반환했다는 사실만으로 그 인용이 판정을 뒷받침한다고 세지 않았다.
- 세 번 모두 판정이 맞은 고유 사례는 11/12, 판정과 근거가 모두 맞은 사례는 10/12다. 36회는 36개 독립 논문/문제 표본이 아니다.
- 선택·필수 근거·이유 코드 세 조건을 모두 충족한 경우는 18/36회, 고유 사례로는 6/12다. 이유 코드 오류와 연결 판정 오류의 중요도를 같은 것으로 간주하지 않고 각 항목을 별도로 공개한다.
- 12개 모두 세 반복에서 선택·evidence ID 집합과 순서·이유 코드가 같았다. **이번 입력에서는 오류도 안정적으로 반복됐다.** 구조화된 출력과 고정 seed가 의미 정확성을 보증하지 않는다.
- 별도로 이전 Test_Paper의 알려진 두 오류를 한 번 재실행했다. 문장 분리에는 `merge_previous`, 잘못된 Figure 5/6 연결에는 `needs_context`로 **2/2**를 다시 맞혔다. 이 결과를 새 사례 점수에 합산하지 않는다.

[실제 측정값](metrics.json), [독립 사례 검토](CHALLENGE_REVIEW.md), [사전 평가 기준](oracle/expected.json), [동결된 입력](challenge/packets.json)

## 놓친 부분

**Case-11: 다른 Figure의 continued caption을 붙인 제안을 승인했다.** Clarke의 Figure 5 caption(원본 9쪽, alias 102)과 Figure 4의 continued caption(원본 8쪽, alias 92)을 Figure 5의 연결로 제시했다. 기대값은 `needs_context`지만, 세 번 모두 `keep`이며 evidence는 `[102]`뿐이었다. 충돌하는 92도 입력과 target에 있었으나 인용하지 않았다. 원문 소실이 아니라 연결 판정과 근거 선택의 실패다.

**Case-01: 분류는 맞았지만 Abstract 대부분을 근거에서 빠뜨렸다.** 두 단에 걸친 실제 Abstract 본문은 `[7,10]`이다. 세 번 모두 `abstract`를 골랐지만 evidence `[6,9,10]`에는 왼쪽 본문 7이 없고 표제 6·온라인 부록 안내 9가 포함됐다. 원문 7을 삭제하거나 후보에서 제거한 것은 아니며, 인용의 충분성에서 실패한 것이다.

## 실제 스크립트 초안의 검토

각 논문의 자연 초안은 한 번씩만 검토했다. 새 기본 파서인 MinerU 3.4.5 Hybrid high + Pro2605 1.2B에 PDF 전체를 200 DPI 이미지로 제공했다. 원본 Data SHA, 전체 페이지, 원본/파생 좌표, raw block, 보존 PNG와 artifact hash를 유지했다.

| 논문 | 전체 페이지 | 보존 원문 블록 | 자연 검토에서 보인 고유 블록 | 최종 그룹 |
|---|---:|---:|---:|---:|
| Chen, Journal of Immunology 2009 (2) | 29 | 237 | 79 | 28 → 28 |
| Clarke, Journal of Leukocyte Biology 2015 | 14 | 159 | 50 | 25 → 25 |
| Dejani, PNAS 2018 | 10 | 126 | 25 | 11 → 12 |
| 합계 | **53** | **522** | **154** | **64 → 65** |

자연 검토는 18호출/48판정이며 직접 target은 129개 블록이다. 전체 522개가 모델에 전달되거나 의미적으로 검증된 것은 아니다. Source block의 실험 alias를 사용했고 새 canonical Information UUID를 발급하지 않았다. 모든 최종 projection은 원문 522개를 정확히 한 번씩 유지하고 독립 replay와 일치했다. 이것은 원문 보존 및 구조 검사이며, 전체 grouping 정확도 점수가 아니다.

남은 문제는 [자연 초안 검토](NATURAL_REVIEW.md)에 원문 ID별로 기록했다.

1. **후보 생성 범위 누락:** Chen의 제목 없는 Introduction이 Abstract에 붙고 각주가 혼입됐다. Clarke에도 약어·온라인 안내·교신 정보 혼입이 남았다. Dejani에서는 Significance 이후만 front 후보로 잡아 실제 Abstract 5를 모델에 주지 않았고, 본문 text block 안의 소제목은 boundary 후보가 되지 않았다. 추론 전에 기록한 네 구조 문제는 해결되지 않았다.
2. **새 모델 오분류:** Dejani의 명시적 Significance 표제 11 아래 본문 12를 Q8이 새 Abstract로 옮겼다. 실제 Abstract 5는 metadata에 남았다. Introduction 25와 caption-7은 `needs_context`로 남겼다. 이 자연 입력은 1회 관찰이다.
3. **Figure 연결 규칙 누락:** 현재 draft의 정규식이 `Fig.`/`Figs.` 약어를 인식하지 못해 20개 Figure 객체 모두 본문 `context_groups`가 비어 있다. Chen의 실제 caption continuation 206·216·226도 References에 남고 자연 caption 입력에서 빠졌다. ledger에 보류 항목이 없다는 사실은 이런 미검출 문제의 해결을 의미하지 않는다.
4. **이유 코드의 유형 문제:** 자연 boundary 25건 중 22건이 `explicit_caption`을 반환했다. 구조 enum에는 맞지만 판정 종류에는 맞지 않는다.

현재 판정과 근거로는 Q8을 **제한된 후보 검토 도구**로 사용할 수 있다. 자동 승인에 앞서 `Fig.` 변형과 caption continuation, 무표제 Introduction·Significance·본문 내부 소제목의 후보 coverage를 보완하고, 후보의 모든 연결 대상 및 이유 유형을 검증하는 경로가 필요하다. 근거가 빠지면 exact refs로 추가 문맥을 가져와 보류를 해소해야 한다. 이번에 이 후속 정책이나 제품 기본값을 새로 적용한 것은 아니다.

## 실행 조건과 시간

- 모델: 기존 `Qwen3.5-9B-Q8_0.gguf`, 9,527,502,048 bytes. SHA-256 `809626574d0cb43d4becfa56169980da2bb448f2299270f7be443cb89d0a6ae4`.
- llama.cpp b10380 / `0b1bad14f`, RTX 5080, context 32,768, reasoning budget 2,048, output 4,096, temperature 0, seed 42, cache off. 모델 디렉터리와 동결 입력은 read-only, 외부 네트워크는 없고 사용자 원문 업로드도 없다.
- Q8은 이 실험에서 **text-only 문맥 준비**를 수행했다. 모델에 PDF 이미지 픽셀을 제공한 I2K/K 생성 실험이 아니다. 원본 페이지 이미지를 함께 제공하는 PDF I2K 계약은 유지한다.
- 자연 검토 18회: 458.27초. 별도 반복 36회: 921.95초. 이전 회귀 1회: 26.60초. 총 **55회 / 약 23분 27초 / 200,314 tokens**, 호출 중앙값은 각 본 평가군 약 25.6초다. 파싱·근거 생성·모델 로드·검토 시간은 이 추론 시간에 포함하지 않았다. 다른 양자화의 과거 속도와 직접 비교하지 않는다.
- 평가 protocol SHA `4e72be0b4dd3ec4bc7e9a605dc06397501812fac2f59dc414911801b074d257a`; metrics SHA `d0039152c647e18453b8aaa56b8006c8be42ae13740859b62e7bc7f5e8ebbd51`.

## 변경과 검사

새 [평가 도구](../../tools/run_extended_context_review.py)는 기존 policy/schema/HTTP runner와 독립 scorer/replay를 재사용한다. 새 논문에서 발견한 [기존 초안 helper](../../tools/run_script_context_review.py)의 unresolved Figure `figure_refs` 초기화 누락만 한 줄 수정했다. 최초 Chen 준비는 이 오류로 exit 1이었고 수정 후 exit 0이다. 기존 Test_Paper draft와 7개 packet이 수정 전 기록과 정확히 같음을 재생성 검사로 확인했다. 과거 frozen helper·모델·원문·실험 결과는 그대로다.

주요 실행 명령과 결과:

```text
python -X utf8 -B output/t03-qwen9b-extended/runtime/run_corpus.py                    exit 0
python -X utf8 -B tools/run_extended_context_review.py prepare-document --root output/t03-qwen9b-extended --paper paper02
python -X utf8 -B tools/run_extended_context_review.py prepare-document --root output/t03-qwen9b-extended --paper paper04
python -X utf8 -B tools/run_extended_context_review.py prepare-document --root output/t03-qwen9b-extended --paper paper05
  세 문서 수정 후 exit 0
python -X utf8 -B tools/run_extended_context_review.py self-check                  exit 0, 4 checks
python -X utf8 -B output/t03-qwen9b-extended/runtime/check_harness.py                exit 0, 8 checks
python -X utf8 -B tools/run_extended_context_review.py freeze --root output/t03-qwen9b-extended
  exit 0
./output/t03-qwen9b-extended/runtime.ps1 -Mode server
./output/t03-qwen9b-extended/runtime.ps1 -Mode natural
./output/t03-qwen9b-extended/runtime.ps1 -Mode challenge
./output/t03-qwen9b-extended/runtime.ps1 -Mode regression
  세 평가 client exit 0
python -X utf8 -B output/t03-qwen9b-extended/frozen/run_extended_context_review.py score --root output/t03-qwen9b-extended
  exit 0, 55/55 요청·응답 검증 및 독립 projection replay
```

Python 명령은 작업 환경의 고정 host Python으로 실행했다. [입력 무결성 감사](runtime/input-integrity-audit.json)에서 522개 원문 연결, protocol 26개 artifact, 기존 원문 8개와 과거 실험 368개 파일이 일치했다. [사전 교차 감사](runtime/preflight-peer-review.json)는 차단사항 0이다. 첫 peer 기록 시도는 protocol 부재라는 시점 가정 때문에 exit 1이었고 실제 source/expected 검사는 통과했으며, 최종 기록은 exit 0이다.

번들 문서 검사는 별도다. 기존 raw Markdown 표 delimiter 오류 11개에 더해, 이번에 동결한 evaluator-only `oracle/source-review.md` 22행의 표 열 수 오류 1개가 있어 exit 1이다. 이 Markdown은 모델 payload가 아니며 해당 서식 오류로 입력·기대 판정·점수를 바꾸지 않았다. 동결 artifact를 결과 이후 수정하지 않고 오류 기록을 보존한다. 앱 전체 테스트, PostgreSQL 통합, K 생성, 전수 OCR 충실성 검증 또는 T03/T04 acceptance 완료를 주장하지 않는다.

`runtime.ps1 -Mode cleanup`은 exit 0이며 이번 평가 client 3개와 전용 서버 1개를 로그 보존 후 제거했다. 준비용 16개를 포함해 이번 임시 컨테이너는 20개다. 새 이미지는 만들지 않았다. [최종 실행 감사](runtime/final-run-audit.json)는 55/55 요청·응답·토큰·stop/cache/truncation 검사를 통과했고, [정리 기록](cleanup.json)에 제거한 정확한 ID와 로그가 남아 있다. 원본 D/I, 이전 parser 결과와 모델, DB, canonical은 보존한다.

[정리 후 무결성 감사](runtime/final-integrity-audit.json)에서 기존 Docker 7 containers/15 image IDs/35 volumes가 baseline과 정확히 같고 이번 임시 컨테이너 20개가 모두 사라졌음을 확인했다. 원본 8개·이전 실험 368파일·새 원본 PDF 3개·동결 artifact 26개도 그대로다.
