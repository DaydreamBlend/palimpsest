# T03 — MinerU Hybrid 원문 보존과 PDF 근거 보완 결과

2026-09-10. 사용자가 승인한 이번 보완 범위를 구현하고 Test_Paper 및 추가 논문 3편, 총 43페이지에서 확인했다. 새 D2I 기본값은 **MinerU 3.4.5 / Hybrid high / Pro2605 1.2B / local Transformers / CUDA**다. 이 조합은 앞선 비교에서 속도와 Figure 보존에 장점이 있었으며 모든 품질 지표의 최고 성능을 뜻하지 않는다.

**원문 I의 페이지·영역·leaf span을 보존하고, 문단 통합·소제목 후보·전사 차이·전체 Figure/페이지 이미지를 별도 조회 projection으로 제공한다.** application semantic LLM 호출은 0회이고, 파서 내부 Pro VLM 전사만 사용했다. I2K 이후는 실행하지 않았다. 기존 사용자 DB와 과거 raw/I/Record/ID/hash는 수정하지 않았다.

## 구현한 동작

| 모듈 | 역할 |
|---|---|
| `hybrid_profile.py`, `deploy/mineru-hybrid/run_parser.py` | 검증된 image/model revision·weight·runner hash와 GPU를 고정하고 새 Hybrid 실행·receipt를 남긴다. 자동 parser/engine fallback은 없다. |
| `mineru_adapter.py`, 기존 Compiler Runtime | 새 profile은 모든 페이지의 병합 전 `preproc_blocks`를 요구한다. 기존 profile의 해석과 과거 이력은 보존하며 공통 원자적 저장 경로를 재사용한다. |
| `pdf_text_evidence.py` | PDFium에서 문자·font·size·flags·좌표·문자 범위를 추출한다. 소제목 후보와 PDF/파서의 양쪽 전사를 비교하는 검토 항목을 만든다. |
| `pdf_visual_evidence.py` | 원본 페이지 이미지, 기존 parser 이미지 영역의 정확한 복사본, 전체 Figure 영역 제안을 제공한다. native image 객체 근거가 부족하면 영역 불확실성과 전체 페이지를 남긴다. |
| `paragraph_projection.py` | 문단의 각 조각을 원래 page/bbox/raw locator/hash로 연결하고 현재±1페이지 조회를 만든다. `source_asset`는 provenance, `display_asset`는 실제 읽을 복사본이다. |
| `pdf_evidence.py`, `tools/run_pdf_evidence.py`, `palim` | 위 결과를 검증된 불변 패키지로 결합하고 CLI로 읽는다. Data·bundle·receipt·middle 및 파일 hash를 검사하며 최종 manifest를 원자적으로 게시한다. |

소제목 후보와 문단의 anchor는 조회용이다. canonical 제목·절 계층·Knowledge Node를 생성하거나 원문을 자동 교정하지 않는다. 글꼴 숫자 weight만으로 bold를 단정하지 않으며, PDF text matrix가 반영된 실제 크기와 명시적 style을 사용한다. 원래 font size와 변환 행렬도 그대로 남긴다.

## 실제 문서 결과

| 문서 | 페이지 | native 소제목 후보 | 검토용 전사 차이 | 조회용 문단 | 전체 Figure 영역 제안 |
|---|---:|---:|---:|---:|---:|
| Test_Paper | 14 | 35 | 72 | 154 | 6 |
| Nassar | 10 | 56 | 99 | 88 | 7 |
| Torchinsky | 5 | 19 | 43 | 40 | 4 |
| Wallet | 14 | 67 | 87 | 93 | 8 |

native 문자 222,284개, 소제목 후보 177개, 문단 375개다. 문단 segment 3,900개의 원래 페이지·bbox·raw locator·내용 hash·표시 offset을 대조했다. 문단 조회 밖의 204개 segment는 모두 원문 bundle의 `discarded_blocks`에 보존돼 있다. 제거한 원문이 아니다.

고정 평가의 **기존 누락 소제목 39개 중 32개를 정확한 후보 경계로 수집**했다. Nassar 19/21, Torchinsky 0/3, Wallet 13/15다. 후보 안에 문자열이 포함된 기준은 35/39, native 페이지 문자열 확인은 38/39다. 이는 정식 title label·계층 결정이나 전체 후보 precision을 평가한 수치가 아니다. 알고리즘을 고정한 뒤 기존 평가 표와 대조했으며, 평가 표는 이 프로젝트의 기존 annotation이지 독립적인 인간 gold standard는 아니다. 남은 7개와 후보별 연결은 [독립 데이터 QA](../output/t03-pdf-evidence/final-review/final-data-qa.md)에 있다.

567개 parser 비교 block 중 266개는 제한된 표시 정규화에서 동등하고 301개는 검토용 차이로 남는다. Test_Paper의 알려진 `P <` 통계 표기 및 `β` 차이도 표시한다. **301건이 모두 확정된 OCR 오류라는 의미는 아니다.** native PDF Unicode 매핑, 수식·표시 정규화, 공간 대응의 불확실성도 차이를 만든다. 어느 쪽 전사도 자동으로 덮어쓰지 않는다.

Test_Paper는 **전체 Figure 6개와 원본 페이지 14개, parser 이미지 영역 36개, 캡션 anchor 8개**를 제공한다. 36은 의미적 panel 수가 아니라 parser가 반환한 이미지 영역 수다. Figure 5의 범례와 Figure 6H의 네 그래프·공통 범례가 전체 Figure 이미지에 포함된다. 모든 Figure를 원본 PDF와 직접 대조한 a2 시각 QA를, bbox·PNG·crop·caption 배열이 정확히 같은 최종 a3에 연결했다. a3 자산 93개 및 패키지 파일 103개의 SHA/크기를 다시 검증했다. [Figure QA](../output/t03-pdf-evidence/visual-review/Test_Paper-a3-final-qa.md), [QA 결속 receipt](../output/t03-pdf-evidence/visual-review/Test_Paper-a3-qa-binding.json).

## 격리된 실제 D → D2I → I 시험

프로젝트 `palimpsest-t03-evidence-verify`의 PostgreSQL **18.6 / pgvector 0.8.6**에서 실행했다. 사용자 개발 DB는 이 작업 시작 시 이미 중지 상태였으며 시험 쓰기는 하지 않았다.

- Data: `a2268b37570f41bb07189cf083376e5823fae364165d5e0e256f796a0814cffe` — 첨부 원본의 raw-byte SHA-256.
- 완료 execution: `01a08912-af7f-7864-89c1-405cfe21dc57`.
- RTX 5080에서 새 파싱 14페이지, parser 시간 **216.355초**. 이 시간은 새 실행 한 번의 값이며 전체 등록·저장·보완 시간은 아니다.
- **229 I = Text 193 + Image 36**, source Record 229, grounding 229, 임시 후보 0, 후속 I2K outbox 229. Image I는 parser 원문 영역이며 전체 Figure는 별도 evidence projection으로 제공한다.
- 원문 block 229개의 완전한 coverage와 canonical payload의 원래 block 필드를 대조했다. 모든 I의 `semantic_type=null`, `semantic_checked=false`, 새 I/Record ID는 UUIDv7이다.
- 동일 profile/work directory로 재실행한 job·I·event JSON이 완전히 같았다. 새 inference/I 생성 없이 completed 실행을 재생했다.
- 같은 PDF의 새로운 등록 요청은 `duplicate_data`, exit 6으로 거부됐다. 해당 Data와 acquisition은 각각 1개다.
- canonical 14페이지 조회와 10페이지의 앞뒤 문맥 조회 통과. 보존 raw 66파일을 Artifact Store에서 다시 export하여 모든 크기·hash가 원래 실행과 같음을 확인했다.

[최종 실물 검증 receipt](../output/t03-pdf-evidence/runtime/final-audit.json), [DB 읽기 검사](../output/t03-pdf-evidence/runtime/db-audit.json), [전체 I](../output/t03-pdf-evidence/runtime-worker/information.json), [기계 판독 결과](T03_pdf_evidence_result.json).

sidecar bundle은 복사한 parser receipt hash를 profile에 연결하고, canonical bundle은 전체 runtime profile을 연결한다. 따라서 bundle hash는 서로 다르지만 원래 source block 필드는 정확히 같다. 마지막 읽기 검증 강화는 이미 생성한 a3의 생산 코드 hash를 덮어쓰지 않았으며, 현재 reader hash와 a3 producer hash를 최종 audit에 각각 기록했다.

## 실행 명령과 검사

명령은 repository root에서 수행했다. 아래 `python`은 호스트의 `C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -X utf8 -B`를 뜻하고, 호스트 앱 import에는 `PYTHONPATH=src`를 사용했다. Docker 앱 명령에는 `PALIMPSEST_APP_IMAGE=palimpsest-t03-evidence:0.2.0`를 지정했다.

| 검사/명령 | 실제 결과 |
|---|---|
| `docker compose -p palimpsest-t03-evidence-verify build app` | 최종 image build exit 0 |
| `docker compose -p palimpsest-t03-evidence-verify run --rm --no-deps -T test` | **241 tests / 26.205초 / exit 0**, lean 앱에 native PDF library가 없어 8 skip |
| 기존 Hybrid 이미지에서 `python -B -m unittest discover -s tests/app -p 'test_pdf_*.py' -v` | **19 tests / 0.298초 / exit 0 / skip 0**. 위 native 8개를 포함한다. |
| `python -m unittest discover -s tools -p 'test_*.py' -v` | 문서 도구 **44 tests / 221.099초 / exit 0**. 앱 검사와 별개다. |
| `python tools/run_d2i.py --data-id a2268b37570f41bb07189cf083376e5823fae364165d5e0e256f796a0814cffe --project palimpsest-t03-evidence-verify --work-dir output/t03-pdf-evidence/runtime-worker --parser mineru-hybrid` | 새 GPU 실행 완료 및 동일 실행 재생 모두 exit 0 |
| `palim jobs export-parser 01a08912-af7f-7864-89c1-405cfe21dc57 --directory /exchange/parser-export --json` | raw 66파일 exact 복구, exit 0 |
| `palim information pages --execution-id 01a08912-af7f-7864-89c1-405cfe21dc57 --json` 및 `information context ... --page 10` | 14페이지와 9–11페이지 문맥, exit 0 |
| `palim information evidence-context --directory /evidence --page 10 --json` | 최종 a3의 원문·문단·후보·차이·실제 이미지 연결, exit 0 |
| `python output/t03-pdf-evidence/runtime/audit_final.py` | 12개 실물 검증 및 4편 43페이지 문맥 반복 일치, exit 0 |

최종 `python tools/validate_bundle.py`는 exit 0, 문서 무결성 오류 0으로 통과했다. [앱 로그](../output/t23-ui-realm/build-test-logs.zip#output/t03-pdf-evidence/runtime/app-tests-final-a2.log), [native PDF 로그](../output/t23-ui-realm/build-test-logs.zip#output/t03-pdf-evidence/runtime/native-tests-final-a2.log), [문서 도구 로그](../output/t23-ui-realm/build-test-logs.zip#output/t03-pdf-evidence/runtime/document-tests.log), [bundle 로그](../output/t23-ui-realm/build-test-logs.zip#output/t03-pdf-evidence/runtime/bundle-validation-final.log)를 별도로 보존했다.

Docker 정리는 전용 컨테이너 3개와 network 1개만 제거했다. 기존 컨테이너 7개·기존 이미지 ID 12개·기존 볼륨 23개와 이번 시험 볼륨 4개가 모두 남아 있다. 최종 `palimpsest-t03-evidence:0.2.0` 이미지만 baseline에 추가됐고, 이전 중간 이미지 ID는 정리 전부터 존재하지 않아 추가 이미지 삭제는 0이다. [정리 검증](../output/t03-pdf-evidence/runtime/cleanup-verification.json).

[변경 파일 목록과 hash](../output/t03-pdf-evidence/runtime/changes.json)에 새 모듈·테스트·승인 문서·CLI/runner 연결 및 기존 파일 수정을 기록했다. [기존 코드와의 diff](../output/t03-pdf-evidence/runtime/changes.diff.txt)는 작업 전 보존본 기준이다. repository에 Git 이력은 생성하지 않았다.

## 실패에서 수정한 사항과 남은 경계

첫 새 GPU 작업은 Torch와 NVIDIA의 같은 GPU UUID에 `GPU-` 접두사가 있고 없는 차이로 실패했다. 두 표기를 UUID로 정규화하되 실제 GPU 동일성 검증은 유지했다. 실패 execution `01a0890d-bd07-7a6f-8b31-7440cf2a096c`는 그대로 남겼고 canonical 효과는 0이다. 초기 앱 테스트는 runner 파일을 이미지에 복사하지 않아 실패했으며 Dockerfile과 build context를 수정했다. 초기 5 Figure 출력은 `FIGuRE 2U` 캡션 경계를 놓친 것이어서 typed caption에 한정한 규칙으로 6개를 회복했다. 초기 native heading 후보 228개는 raw weight/size 해석 문제를 수정한 뒤 Test_Paper 35개로 줄었다. 이러한 실패 출력은 역사로 보존했다.

독립 검토에서 다른 Data의 문단·receipt 연결, 출력 경로 alias, 문단 이미지 복사본 연결, 최종 manifest 게시 실패를 재현해 수정하고 회귀 검사했다. source/receipt/raw hash를 유지하며 실제 a3는 모두 유효하다. 알려진 parser 전사와 crop 손실을 교정 완료로 기록하지 않는다.

회전·CropBox 좌표 대응이 검증되지 않은 PDF는 명시적으로 거부한다. native text가 없는 페이지는 부재 상태를 남기며 임의의 OCR로 대체하지 않는다. native top-level image 객체가 아닌 복잡한 vector/Form Figure는 전체 영역 제안이 불확실할 수 있다. Test_Paper 외 3편의 모든 Figure 경계를 인간 정답과 대조한 것은 아니다.

원문 페이지 복원은 정확하더라도 upstream의 문단 연결 의미는 미검증이다. Test_Paper의 p5/p8, Nassar의 p8/p10처럼 인접하지 않은 페이지 association은 경고와 원래 refs를 함께 남긴다. 표제 7개 미회복·후보 precision·scanned/mixed·일반 대형 문서·전체 reconciliation/supersession 및 후속 Knowledge 단계는 남아 있다.

이번 보완 slice는 완료했지만 **T03 전체는 in_progress**다. AT22/23/25/27/33/36/68/69/71/76/77/81/83/85/90–102/104/105/107/111/112를 일괄 완료로 바꾸지 않는다. 승인 대기 결정은 없으며 T04 이후나 GUI를 시작하지 않았다. 상세 사용법은 [PDF_EVIDENCE](../docs/interfaces/PDF_EVIDENCE.md)를 따른다.

로그 링크의 ZIP fragment는 T23 정리 때 보존한 원래 entry 경로다. 원문 내용은 archive와 cleanup manifest에서 확인한다.
