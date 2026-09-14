# T03 — 현재 PDF 처리 방식의 추가 논문 평가

상태: 추가 평가 완료. **파싱과 source I 제안 검증17/17, 조회용 근거 package16/17, 표본 Figure 완성16/19**다. T03 전체 acceptance 완료를 뜻하지 않는다. [기계판독 결과](T03_expanded_papers_result.json)와 [고정 기준 전체 점수](../output/t03-expanded-papers/runtime/quality-final-a1.json)를 함께 보존한다.

## 최종 결과

| 항목 | 결과 | 해석 |
|---|---:|---|
| MinerU 파싱 종료 | 17/17, 100% | 새 논문243페이지 전체 |
| Source I 제안 조립·raw coverage/hash 검증 | 17/17, 100% | 제안2,834개: Text2,599 / Image235; DB commit은 아님 |
| Native 근거·Figure/page·문단 package 생성 | 16/17, 94.1% | Manfredi의 CropBox 불일치로1편 거부 |
| 모든 페이지 context 조회·동일 재조회 | 16/17, 94.1% | 완성된16편233페이지; 실패1편은 제외하지 않음 |
| 전체 페이지 companion | 233/243, 95.9% | 실패 문서10페이지는 source-review 평가용 렌더로 대체하지 않음 |
| 표본 독립 Figure crop 존재 | 16/19, 84.2% | 옆 caption 연결 실패2개, package 실패1개 |
| 표본 Figure body·축·범례 시각 보존 | 16/19, 84.2% | 생성된16개 모두 complete; missing3, uncertain0 |
| MinerU title 분류의 정확한 제목 경계 | 48/74, 64.9% | 제목 전체가 긴 title block 안에 포함되는 경우까지50/74, 67.6% |
| Native font/span 제목 후보의 정확한 경계 | 25/74, 33.8% | 제목 전체가 긴 후보 안에 포함되는 경우까지36/74, 48.6% |
| Native 후보 중 정확한 제목 경계 비율 | 25/168, 14.9% | ambiguous와만 정확히 일치3개, unmatched140개를 별도 보존 |
| Parser 전사 표본의 엄격한 문자열 일치 | 32/51, 62.7% | non-title 보조집계29/48, 60.4%; 의미 정확도가 아님 |

Source verifier는 파서 블록2,834개, raw leaf18,537개와 payload segment18,533개, 원래 페이지 refs243개, 보존파일932개를 대조했다. 동일 raw에서 제안을 두 번 조립한 결과는 모든 문서에서 같았다. 이는 이미 파싱된 raw→I 스크립트의 재현성 검증이며, GPU VLM 재추론을 여러 번 수행해 동일함을 입증한 시험은 아니다.

완성된16편의 부가 산출물에는 제목 후보663개, caption 기반 Figure 후보103개, 문단 projection1,648개가 있다. Figure 후보103개는 null region을 포함한 후보 수이며 독립 crop103개 성공이라는 뜻이 아니다. Native/parser 차이 신호1,391개도 확정 오류1,391개가 아니다. 문단 projection 밖의 source segment1,160개는 원문에서 삭제하지 않고 별도 refs로 유지했다.

전사 표본은 총7,812자이며 parser의 최소 substring 편집거리 합은49(0.63%)다. LaTeX 표현, 줄바꿈 하이픈, 문자 직렬화 차이와 실제 glyph 오류가 섞이므로 **99.37% OCR 정확도 또는49자 실제 소실로 환산하지 않는다.** Native 채널은32/51 exact, 최소거리22(0.28%)이며,48개는 완성된 production native chars, 나머지3개는 실패한 Manfredi의 동결된 source-review native text를 평가 목적으로만 읽었다. 이 읽기는 제품 fallback이나 package 성공이 아니다.

[불일치19건 전체 원인 검토](../output/t03-expanded-papers/runtime/transcription-review-final.md)에서는 줄바꿈·분철·하이픈/제어문자10건, native와 공유된 문자 대체5건, 수식 표현3건, 분리 accent의 직렬화1건을 확인했다. 문자 대체는 φ→f, β→b, γ→U+0001, μg→mg, μM→mM이다. 이 분류를 새로운 의미 정확도로 환산하거나 strict 실패를 성공으로 바꾸지 않는다. 검토한 표본에서 block 경계 때문에 문장이 사라졌다고 확인된 경우는0건이며, 전체 PDF의 완전성 주장과 구분한다. 검토는 입력87개 파일과 raw block/excerpt 위치를 대조했고 고정 점수를 유지했다.

참고 산술 집계로 두 제목 경로의 합집합은 exact49/74(66.2%), contains54/74(73.0%)다. 새 의미 모델 없이 같은 고정 문자열 판정 결과를 합친 보조 지표이며, 실제 절 계층이 확정됐다는 뜻이 아니다. 이전4편의 ‘기존 누락39개 중32개’는 이미 알려진 누락 집합의 복구율로, 이번 새 코호트74개와 분모·구성이 달라 직접적인 성능 증감 시험으로 비교하지 않는다. 이번 결과만으로도 native 후보를 확정된 절 제목으로 바로 사용하기에는 부족하다.

## 확인한 실패 위치

1. **Manfredi, 1998 — native 좌표 지원 범위.** 파싱과 source 조립은 성공했지만 PDF의3·5·7페이지에서 CropBox가 실제 MediaBox/bbox보다 약0.72–1.44pt 가로,0.48–0.96pt 세로로 컸다. 현재의 정확한 좌표 대응 guard가 `unsupported_pdf_geometry`로 거부했다. 기존 로그는 오류 코드만 보존하므로 최초 거부 페이지3은 PDFium 측정값과 순차 guard로 도출한 위치다. [측정 근거](../output/t03-expanded-papers/runtime/geometry-failure-paper12.json). 이 문서를 조용히 보정하거나 다른 경로로 성공시킨 결과는 없다.
2. **Clarke, 2015 p7 Figure4 / Piccinini, 2016 p9 Figure6 — caption과 그림 연결.** 두 그림의 raw parser crop에는 패널과 범례가 보존돼 있다. 옆으로 놓인 caption을 현재 후처리가 연결하지 못해 `member_panel_ids=[]`, `region_proposal=null`이 됐다. MinerU의 그림 인식 누락과 구분한다. Whole-page fallback이 남아 있어도 독립 Figure 성공에는 넣지 않았다.
3. **과학 표기 — native에 있는 잘못된 문자도 전달됨.** Lee p8의 `1 μg/ml → 1 mg/ml`, Piccinini p9의 `1 μM → 1 mM`, Clarke의 `Mφ → Mf`를 원본 시각 근거와 확인했다. 같은 오표기가 native text에도 있어 Pro VLM만의 오류로 귀속할 수 없다. Native/parser가 같은 잘못된 문자를 공유하면 두 문자열의 차이 검사만으로는 그 오류를 보장해 찾을 수 없다.
4. **제목 후보 — 경계·후보 누락·과잉 포함.** 저자명, 배너, caption 제목, 굵은 abstract가 제목 후보에 포함되고 일부 명확한 subsection은 빠졌다. 정확한 제목 문자열에 각주 숫자나 저자가 붙은 경우도 strict 미일치에 포함된다. 이는 원문 텍스트가 모두 사라졌다는 뜻과 다르다.

[Figure 시각 검토 A](../output/t03-expanded-papers/source-review/visual-crops-a3.md)와 [B](../output/t03-expanded-papers/source-review/visual-crops-b3.md)는 고정19개 전체의 complete/missing 원인과 실제 파일 hash를 기록한다. 기하 screen은15/19를 통과했고 시각 검토는16/19다. 수동 bbox의 여백 근사로 생긴 screen 미통과를 실제 내용 잘림으로 간주하지 않았다. 원문에 원래 잘려 보이는 요소도 새 crop의 손실과 구분했다.

## 문서별 실행

모든 문서에서 parser와 source verifier는 성공했다. 아래 ‘근거’는 native/visual/paragraph package와 전체 context 조회까지의 상태다. 시간은 모델 확인·초기화 등을 포함하는 parser receipt의 경과 시간이며 GPU별로 서로 다른 논문을 처리했으므로 GPU 성능 비교값은 아니다.

| ID / 논문 | 페이지 | Text / Image 제안 | 근거 | Parser 초 / GPU |
|---|---:|---:|---|---:|
| paper01 Campisi | 12 | 151 / 12 | 완료 | 208.7 / 5080 |
| paper02 Chen, (2) | 29 | 227 / 10 | 완료 | 226.9 / 4060Ti |
| paper03 Chen | 30 | 281 / 8 | 완료 | 236.2 / 5080 |
| paper04 Clarke | 14 | 151 / 8 | 완료 | 210.7 / 5080 |
| paper05 Dejani | 10 | 114 / 12 | 완료 | 197.6 / 5080 |
| paper06 Fadok | 9 | 89 / 9 | 완료 | 158.3 / 4060Ti |
| paper07 HMGB1 / Telusma | 11 | 119 / 6 | 완료 | 233.1 / 4060Ti |
| paper08 Hart | 7 | 82 / 9 | 완료 | 136.7 / 4060Ti |
| paper09 Kool | 15 | 188 / 67 | 완료 | 224.7 / 5080 |
| paper10 Lee | 15 | 201 / 27 | 완료 | 250.1 / 4060Ti |
| paper12 Manfredi | 10 | 95 / 6 | 실패: unsupported_pdf_geometry | 336.5 / 4060Ti |
| paper13 Matta | 25 | 238 / 13 | 완료 | 248.4 / 4060Ti |
| paper15 Notley | 7 | 84 / 7 | 완료 | 126.4 / 5080 |
| paper16 Penteado | 10 | 133 / 10 | 완료 | 154.0 / 5080 |
| paper17 Piccinini | 17 | 192 / 19 | 완료 | 278.0 / 5080 |
| paper18 Rovere | 9 | 90 / 6 | 완료 | 181.6 / 5080 |
| paper20 Valente | 13 | 164 / 6 | 완료 | 203.2 / 4060Ti |

논문당126.4–336.5초, 중앙값210.7초다. 두 GPU 병렬 batch의 첫 시작부터 마지막 parser 종료까지1,827.24초(약30.5분)였다. 시각 annotation·검토 시간은 이 batch 시간에 포함하지 않는다. raw `_ocr_enable`은 false16편/true1편(Manfredi)으로, 기존 `auto` 설정의 실제 선택을 기록한 것이며 실험 중 모드를 바꾸지 않았다.

## 평가 범위

2026-09-10 사용자는 현재 방식을 유지한 채 더 많은 논문으로 성공률을 확인하도록 요청했다. 승인된 `Desktop/졸업논문 참고문헌`의 PDF21개를 원본 SHA-256으로 조사하고, 이전 평가 논문3개와 논문이 아닌 제조 프로토콜1개를 제외한 **새 논문17편·243페이지**를 모두 실행 대상으로 고정했다. 두 Chen 파일은 제목이 서로 다른 논문이다. 기존 Test_Paper 및 이전 비교3편의 성적은 새 코호트의 성공률에 합산하지 않는다.

전체17편의 파싱·source I 제안 조립/검증·근거 package·모든 페이지 조회를 검사한다. 내용 품질은 각 문서의 첫·중간·마지막 물리 페이지로 미리 고정한 **51페이지**에서 평가한다. 두 담당자는 새 parser 출력을 보기 전에 원본만으로 명확한 제목74개, 실제 numbered Figure body19개, 전사 표본51개를 동결했다. 애매한 metadata/title8개와 외부 보충자료 caption-only Figure S1은 해당 clear 분모와 구분했다. 제목에는 structured abstract label8개와 publisher synopsis heading1개가 포함되며 종류별 점수를 제공한다. 전사51개에는 본문 없는 표지의 title-only3개가 포함되어 non-title48개 결과도 별도로 제공한다.

이는 **Codex의 시각 주석과 검토이며 독립 인간 gold나 분야 전문가 검증이 아니다.** 생의학 논문으로 구성된 폴더 전체의 추가 코호트이지 일반 PDF 모집단에서 무작위 추출한 표본이 아니다. Figure19개는 고정51페이지에 보이는 그림이며, 243페이지 전체 그림의 recall은 평가하지 않았다.

## 고정한 현재 구현

- MinerU3.4.5 / Hybrid high / 공식 Pro2605 1.2B / local Transformers / CUDA / `auto`. 모델·이미지·옵션은 기존 구현과 동일하다. RTX5080과 RTX4060Ti를 문서별로 나눠 사용하며 GPU UUID를 각각 profile에 기록했다.
- 병합 전 `preproc_blocks`, 원래 페이지/leaf/raw refs로 source I 제안을 조립하고 coverage·hash·좌표·동일 입력 재조립을 검증했다. Native PDF 글꼴/문자 증거, 제목 후보, 전체 Figure/페이지, 전사 불일치, 문단 조회 projection도 변경 없이 실행한다.
- 모델 내부 VLM 전사는 사용한다. Terra/Qwen 등 application semantic LLM 호출과 canonical/사용자DB 쓰기는 **0**이다. 새17편은 DB 없는 동일 source build/verify 경로의 평가이며, 이전 Test_Paper의 실제 PostgreSQL 저장·재생 검증과 구분한다.
- 실행 중 fallback, OCR 모드 강제 전환, 제목/그림 규칙 튜닝, source 교정은 하지 않았다. 새 코드와 산출물은 이 실험의 실행·검증·채점 도구에 한정한다.

## 품질 수치 해석

실행 성공은 파서 결과를 구조적으로 보존할 수 있다는 뜻이다. PDF의 모든 글자·그림을 올바르게 인식했다는 승인이 아니다. 제목 exact는 후보가 해당 제목과 정확히 일치하는 비율이고, contains는 제목 전체가 더 큰 후보 안에 포함된 경우도 인정한다. 후보 precision은 표본 페이지의 모든 후보 중 정확한 제목인 비율이다.

Figure는 같은 원래 페이지의 번호와 독립 crop을 확인한다. 전체 페이지 fallback은 독립 Figure 성공으로 세지 않는다. 수동 bbox의 95% coverage/1.5배 area 검사는 기하 선별 지표일 뿐이며, 실제 패널·축·범례의 보존 여부는 PNG를 원본과 별도로 비교한다.

전사는 Unicode NFC·HTML 표시 태그 제거·공백 정리 후 원문 표본이 같은 페이지의 native text 또는 단일 parser block 안에 정확히 나타나는지 검사한다. 대소문자·그리스 문자·단위·문장부호는 유지한다. 최소 substring 편집거리는 검토 보조값이며 전체 OCR 정확도나 실제 삭제 문자 수가 아니다. 수식의 LaTeX 표현, 줄바꿈 하이픈, 분리 accent의 직렬화도 불일치로 잡히므로 구체적인 원인을 별도로 기록한다.

## 근거와 재현 자료

- [실행 계획](T03_expanded_papers_execplan.md), [코호트 inventory](../output/t03-expanded-papers/inventory.json).
- [고정 metric 규칙](../output/t03-expanded-papers/runtime/quality_metrics.json), [production freeze](../output/t03-expanded-papers/runtime/freeze.json), [평가 도구 freeze](../output/t03-expanded-papers/runtime/evaluation-freeze.json), [원본 annotation freeze](../output/t03-expanded-papers/source-review/oracle-freeze.json).
- [원본 주석 A](../output/t03-expanded-papers/source-review/oracle-a.json), [원본 주석 B](../output/t03-expanded-papers/source-review/oracle-b.json). 주석·채점과 추론은 각각 분리되어 있다.
- [batch 도구](../output/t03-expanded-papers/runtime/run_batch.py), [source 검증](../output/t03-expanded-papers/runtime/verify_source.py), [후처리](../output/t03-expanded-papers/runtime/postprocess.py), [채점](../output/t03-expanded-papers/runtime/score_quality.py). 논문별 원본 결과·명령·로그는 `output/t03-expanded-papers/runs/paperNN`에 보존한다.

## 실행·검증 명령과 유지 범위

호스트 Python은 `C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`이며, 아래 Python 명령에 `-X utf8 -B`를 사용했다. 기존 산출물을 덮어쓰는 재실행은 거부한다.

| 실행한 명령 또는 실제 경로 | 결과 |
|---|---|
| `python output/t03-expanded-papers/runtime/run_batch.py` | exit0;17개 parser receipt complete |
| `python output/t03-expanded-papers/runtime/postprocess.py` (`PYTHONPATH=src`) | orchestration exit0;source verifier17개 exit0, evidence CLI16개 exit0/1개 exit4 |
| 기존 앱 이미지 안의 `verify_source.py --parse-result … --profile … --output …` | Test_Paper 사전 selfcheck:229제안/66파일; 동일 output 덮어쓰기 거부 확인; 새17편은 source 구조 검증 통과 |
| `python output/t03-expanded-papers/runtime/score_quality.py --self-check` | 225개 독립 substring 비교 +6개 정규화/누락/geometry 검사 PASS |
| `python output/t03-expanded-papers/runtime/score_quality.py --output output/t03-expanded-papers/runtime/quality-final-a1.json` | exit0;평가 complete, pending0, failed paper12, changing inputs0 |
| `python output/t03-expanded-papers/runtime/final_audit.py` | exit0;54개 원본/코드/oracle hash 확인, 기존 Docker 자원 동일 |
| `python output/t03-expanded-papers/runtime/review_transcription.py` | exit0;19개 불일치 전체와 paper12 native-only3개 부록, 입력87개 hash·raw block·excerpt 범위 확인 |
| `python tools/validate_bundle.py` | PASSED / exit0; [최종 실행 로그](../output/t23-ui-realm/build-test-logs.zip#output/t03-expanded-papers/runtime/document-validation-final.log). 앱/runtime/LLM 검증과 별도 |

[최종 audit](../output/t03-expanded-papers/runtime/final-audit.json)은 실험 전후 기존 컨테이너7개, 이미지13개, 볼륨27개의 ID/이름/상태 동일성을 확인한다. 새 이미지는 만들지 않았으며 `--rm` 실험 컨테이너는 남지 않았다. 사용자 개발DB와 다른 프로젝트 서비스, 기존 모델·볼륨·원문 이력을 유지했다.

제품 코드·공유 schema·migration·canonical 문서는 변경하지 않았다. 변경은 이번 실험 폴더와 결과/계획/STATUS/INDEX에 한정했다. Production source가 동결되어 있어 이전241개 앱 테스트를 불필요하게 재실행하지 않았고, 그 이전 통과 기록을 이번 실행으로 표시하지 않는다.

이 결과는 T03의 AT22/23/25/27/33/36/68/69/71/76/77/81/83/85/90–102/104/105/107/111/112 관련 제한된 실물 근거다. 이 acceptance들의 전체 조건을 일괄 passed로 바꾸지 않았다. Parser 인식의 완전성, 임의 스캔/다국어/수식 중심 문서의 일반화, 미지원 좌표, 전체 reconciliation/supersession·backup/restore·scheduler/fencing, 이후 I2K/K 단계의 의미 품질은 완료되지 않았다.

현재 parser를 유지하면서 우선 보완할 곳은 **유효 page box의 명시적 좌표 변환, 옆 caption과 이미 존재하는 raw 그림의 연결, 소제목 후보 경계/coverage, 과학 단위·기호 검증**이다. 이번 평가는 현재 성능을 측정하기 위해 이 보완을 적용하지 않은 상태로 마무리했다.

로그 링크의 ZIP fragment는 T23 정리 때 보존한 원래 entry 경로다. 원문 내용은 archive와 cleanup manifest에서 확인한다.
