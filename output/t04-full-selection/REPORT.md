# D↔I 원문 대응과 전체 I의 LLM 선택 — 실제 결과

2026-09-11 사용자 승인 범위를 구현하고 Test_Paper 및 합성 Markdown 두 문서로 시험했다. **D의 구간에서 I를 찾고 I에서 D 위치로 돌아가는 조회, 전체 I의 LLM 중요성 검토, 일반 K 재사용과 다른 Data의 실험 K 분리, 후속 N2E 저장까지 실제 실행했다.**

## 최종 Test_Paper 결과

| 항목 | 실제 결과 |
|---|---:|
| 원본 | PDF 14쪽 |
| 선택한 새 source 실행의 I | **36개: 기존 본문/그림 그룹 22 + 원본 페이지 Image I 14** |
| 모델에 실제 전달한 I media | **50개** |
| D→I / I→D 검증 | 14개 페이지의 파서 영역 밖 위치도 조회, I 36개 모두 원문 위치 확인 |
| 원본 파일 복원 | 등록된 PDF와 SHA-256 동일 |
| 최종 I2K 검토 | **I 36개 모두 Validator confirmed, 실행 completed** |
| 이번 반복 전체의 새 K | **5개** |
| 마지막 선택의 반영 | 기존 K 재사용 7건 + 새 K 2개 |
| 최종 K / NodeRevision | **32 / 32** |
| 이번 새 N2E | **supports 5개 생성·독립 검증·DB 저장** |
| 최종 Edge / EdgeRevision | **26 / 26** |
| 정확 I grounding | **69개**, 그중 새 36개 I에서 35개 추가 |
| 기존 NodeRevision 27개 / EdgeRevision 21개 | **전체 행 변경 없음** |

Data ID는 `a2268b37570f41bb07189cf083376e5823fae364165d5e0e256f796a0814cffe`, 새 source execution은 `01a08f4f-d4fd-7563-8fd7-90e3e2ae0e5d`다. 과거 source 실행과 I를 덮어쓰지 않았다. 모든 역사 버전의 I를 섞는 대신 한 완전한 source 실행의 I 전체를 입력으로 선택한다.

확인 파일: [직접 DB 요약](summary.json), [전체 graph](graph.json), [K 목록](nodes.csv), [Edge 목록](edges.csv), [I별 중요성 선택·독립 검토 이유](information-reviews.csv).

## 원문 대응의 의미

PDF 텍스트/그림 I는 원래 block·leaf·page/bbox·문자 범위를 보존한다. 파서가 찾지 못한 시각 영역도 해당 원본 페이지 Image I에서 확인할 수 있도록 새 source profile에 실제 페이지 이미지를 저장했다. 229개 원문 block과 14개 명시적 page-facsimile block, 총 243개를 I payload에서 정확히 재조립했다.

페이지 I는 기존에 원본 PDF에서 직접 렌더한 `pypdfium2 5.10.1`, scale 2, annotations=true 산출물을 사용한다. 이번에 MinerU를 다시 실행하거나 D2I에 application LLM을 추가하지 않았다. OCR의 모든 문자·첨자가 정확해졌다는 뜻은 아니다. 기록한 해상도의 원본 시각 정보와 정확한 D 위치를 보존하며, 원본 파일 전체 bytes는 연결된 Artifact Store에서 복원한다.

[source 검증](source/verification.json), [각 페이지 D→I→D 왕복](source/page-roundtrips.json), [36개 I의 원문 위치](source/all-information-locations.json), [재조립 manifest](source/reconstruction.json), [복원한 원본 PDF](source/Test_Paper.restored.pdf)를 보존했다. Markdown의 UTF-8 byte·줄·문자 범위 및 exact text 복원도 별도 실제 PG fixture로 검사했다.

## 중요성을 누가 선택하는가

스크립트는 I 제목·종류·길이로 중요성을 미리 선별하지 않는다. 각 호출의 실제 prompt는 동결 DB snapshot으로 다시 만들어 hash를 대조하고, I 36개의 순서와 이미지 50개의 SHA·크기를 검사했다. LLM은 각 I에 선택/문맥/선택하지 않음/추가 검토와 이유를 반환하고 Validator도 모든 I를 검토한다.

마지막 호출의 Generator 분류는 selected 5, context_only 28, not_selected 3이며 Validator는 36개 모두 confirmed였다. 이는 반복 후의 마지막 분류다. 앞선 반복에서 이미 선택·재사용한 K와 근거는 계속 DB에 있으므로 최종 K가 이 마지막 다섯 I에서만 생성됐다는 뜻은 아니다.

I별 review의 중복 참조 목록이 빠진 경우, 모델 후보의 실제 citation에서 이미 선택된 I의 역참조만 스크립트로 완성한다. 이번에는 그런 참조 2개를 완성했다. 중요성 상태·이유·주장·인용은 바꾸지 않았다. 실제로 인용하지 않은 I를 추가하거나 선택하지 않은 I를 임의로 selected로 바꾸지 않는다.

중요한 내용 누락이라는 I 검토 의견과 개별 K의 승인도 구분한다. 이미 독립 검증된 K는 저장하면서 추가 검토 의무를 남길 수 있다. 원본 요청을 실제 제공하지 못한 경우의 근거 보류는 별도다. 최종 I2K와 N2E는 각각 completed이며, 이전 시도의 상태와 판정은 덮어쓰지 않았다.

## 중복 처리의 실제 확인

일반 Proposition은 거의 같은 의미·조건·범위를 나타내면 기존 K/Revision에 새 grounding을 붙인다. Observation과 실험 결과 해석은 source scope를 사용하고 Data가 다르면 같은 K로 합치지 않는다. 같은 Data의 반복 서술은 같은 실험·의미인지 LLM이 검증한 뒤 재사용한다.

Test_Paper 반복에서는 실제 reused 판정과 DB 재사용을 확인했다. 최종 32개 K의 scope는 source 21개, 역사적으로 아직 미분류인 legacy 11개다. 과거 UUID·FP·Revision을 임의로 재분류하거나 바꾸지 않았다. 새로운 cross-Data 재사용에는 scope 호환 검사를 적용한다.

별도 합성 Markdown **Alder/Birch**는 일반 tuple 정의와 매우 비슷한 simulated 실험 결과를 포함한다. 각 문서를 D로 등록해 5개 I씩 전체를 Terra에 제공했다. 최종적으로:

- 같은 일반 정의는 **K 하나와 같은 Revision 하나**를 공유하고 두 Data의 grounding을 갖는다.
- 비슷한 fluorescence 결과는 **Data별 별도 Observation K**로 보존됐다.
- 두 문서의 고유 K는 **11개: 일반 1개 + source 10개**다.

[합성 실험 보고서](cross-data-eval/REPORT.md)와 [실제 DB 검증](cross-data-eval/verification-birch-schema2.json)에 ID와 판정이 있다. 이는 실제 LLM·DB를 사용한 합성 사례이며 모든 자연 문서의 의미 중복 제거율을 측정한 것이 아니다.

## 선택·검증 루프에서 수정한 문제

1. selected I에 연결할 후보가 없는 출력, 원문과 다른 정확 인용은 반영하지 않고 실패로 기록했다. 원문 excerpt와 앞선 의미 검토 의견을 함께 유지해 다음 실행에 전달했다.
2. Validator가 기존 Revision과 자기 candidate key를 동시에 재사용 대상으로 넣는 오류가 반복됐다. 모델 답을 수동으로 고치지 않고 상호 배타적인 JSON Schema로 고쳐 새 실제 판정을 받았다. 합성 문서에서도 이 교정 후 실제 general 재사용이 성공했다.
3. `complete=false`이지만 모든 node/I 판정이 있는 응답은 유효한 미완료 검토로 저장하도록 구분했다. 중요한 누락을 발견한 의견을 형식 오류로 버리지 않는다.
4. 서로 다른 CIA/TGF/colitis/GvHD 실험을 합친 후보와 중요한 Treg/APC 누락을 Validator가 실제로 지적했다. 이를 피드백해 분리·추가했다. 최종 신규 다섯 K에는 장기 CIA 효과, phagocyte depletion, TGF dependency, cofactor 재구성 실패, 별도 GvHD 관찰이 포함된다.
5. N2E의 외부 graph 전송은 자동 승인 검토가 두 번 차단했다. 사용자의 명시적 추가 승인 후 같은 Terra Medium으로 생성·검증해 다섯 관계를 저장했다. 차단을 우회한 다른 경로는 사용하지 않았다.

## 후속 N2E와 Revision

새 다섯 supports는 장기 CIA 결과, TGF dependency, phagocyte depletion, recombinant cofactor mixture, GvHD 결과를 기존 해석 Proposition과 연결한다. 모든 EdgeRevision의 원래 endpoint가 해당 논리 Node의 정확한 Revision인지 DB에서 확인했다.

supports는 해당 aspect에 한정된 근거다. 특히 특정 recombinant mixture의 실패가 모든 multifactor/synergy 이론을 증명하지는 않는다. phagocyte depletion 후 임상점수 감소는 유지됐으므로 phagocyte가 임상 resolution에 필수라고 확대하면 안 된다. [독립 의미 검토](semantic-review.md)에 관계의 범위와 약한 간접 지원을 기록했다.

## 검증·운영

추가 migration은 **0006_i2k_selection**이며 기존 0001–0005를 변경하지 않았다. PostgreSQL **18.6**, pgvector **0.8.6**에서 검사했다. 최종 앱 회귀는 **431개 중 415개 통과, 기존 PDFium 환경 검사 16개 skip, 실패·오류 0개**다. [release 검사 요약](app-tests-release-summary.json)을 참고한다.

테스트에는 모든 I 입력/전달/검토 누락 차단, 실제 prompt/schema hash 결속, source/general scope, 교차 Data 병합 방지, 정확한 quote·media-only 근거, atomic rollback, stale/read-set, 실패 피드백, 원본 위치·export·충돌·손상, 기존 Revision 보존을 포함한다. 문서 validator는 기존 raw Markdown 오류 12개만 남았다. 같은 문서 unit을 Linux에서 실행한 결과 **44개 중 43개 통과, 기존 baseline 실패 1개, 오류 0개**였다. [문서 검사 요약](document-tests-linux-summary.json)을 보존했다.

성공 DB는 Compose 프로젝트 **palimpsest-knowledge**에 보존한다. 기본 앱 이미지는 **palimpsest-selection:0.4.0**이며 최종 digest는 [image-id.txt](image-id.txt)에 있다. 별도 synthetic 검사 프로젝트만 결과 export 후 정리한다.

```powershell
docker compose -p palimpsest-knowledge run --rm --no-deps -T app knowledge graph --data-id a2268b37570f41bb07189cf083376e5823fae364165d5e0e256f796a0814cffe --json
docker compose -p palimpsest-knowledge run --rm --no-deps -T app information locate --execution-id 01a08f4f-d4fd-7563-8fd7-90e3e2ae0e5d --page 3 --bbox 0 0 1 1 --json
```

이번 Test_Paper의 고유 실제 모델 호출은 교정·실패를 포함해 **12회**, input **1,277,008** / output **47,762** tokens, 호출 경과 합계 **1,003.547초**다. Generator 응답의 검증된 재사용을 새 호출로 중복 계산하지 않았다. 별도 합성 실험은 **7회**, input **338,003** / output **9,295**다. 이 횟수에는 구현 과정의 오류 교정이 포함되므로 정상 운영의 고정 비용이나 성공률로 해석하면 안 된다.

## 남은 범위

36 confirmed는 모든 원문 의미의 사람 평가 정답률이 아니다. 24시간 비교 등 일부 지식은 여전히 독립 K로 충분히 표현되지 않았고, Results 인용 하나가 discussion 역할로 표시된 경미한 주석 오류가 있다. 정확 I/원문 위치 자체는 유지됐다.

현재 성공한 최신 I2K/N2E와 별개로 과거 실패 실행·보류 후보의 이력은 남아 있다. outbox 58개도 pending이며 전체 K2K propagation 수렴을 실행하지 않았다. 큰 문서의 호출 분할, BGE 검색/index, 일반적인 material Revision 교정 workflow, 원본 PDF bytes의 provider 전달과 GUI는 후속 범위다. 이번 결과는 양방향 원문 보존과 전체 I의 선택·재사용·관계 저장을 실제로 연결한 검증이다.
