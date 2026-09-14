# 다중 논문 I2K — 구현과 실제 의미 평가

2026-09-11. **출처를 구분해 K를 저장하고 같은 의미를 재사용하는 구조는 작동했다. 그러나 원문 의미와 인용의 충분성을 자동 승인만으로 보장하지 못했고, 여러 Data가 함께 근거가 되는 실제 K도 아직 나오지 않았다. 제품 품질 통과로 판정하지 않는다.**

## 적용한 경계

I2K는 원문에 명시된 정의·관측·저자의 해석을 선택하고 구조화한다. 새 인과관계·일반화·추측은 만들지 않는다. 여러 I의 명시 내용을 한 K로 정리할 수 있으나 새로운 관계를 추가하는 작업은 K2K다. 새 CLI I2K는 단일 문서도 `multi-source-explicit-i2k-v1`으로 실행한다. `claim_basis=explicit_source_content`, `is_inferred=false`, 원문 지지·추론 없음·source identity 검증을 저장한다. 과거 Revision의 기원은 바꾸지 않는다.

기존 내부 `KnowledgeRuntime.prepare()` 호환 경로에서는 새 legacy 실행을 만들 수 있다. 공개 CLI 기본 경로는 고쳤지만 모든 내부 호출의 강제를 완료한 것은 아니다. K2K 실행기와 기존 K의 재검토·수정 Revision 작업은 이번 구현 범위에 포함하지 않았다.

## 실제 자료와 저장 위치

| 자료 | 페이지 | 선택한 I | 실제 이번 사용 |
|---|---:|---:|---|
| Test_Paper, Bonnefoy et al. 2018 | 14 | 36 | 기존 K 32·Edge 26을 비교 문맥으로 사용. 세 논문 I를 함께 보낸 최초 호출은 응답 확보 실패 |
| Clarke et al., Journal of Leukocyte Biology, 2015 | 14 | 35 | 전체 I를 Generator·Validator에 전달 |
| Dejani et al., PNAS, 2018 | 10 | 16 | 전체 I를 Generator·Validator에 전달 |

두 추가 논문에는 전체 51 I와 I 소유 이미지 44개가 있다. 준비된 세 source 전체는 87 I/94 이미지다. 기존의 전체 image200 MinerU 파싱을 재사용했다. 새 parser 호출과 application D2I LLM 호출은 0이며, I2K 인용 오류 때문에 D2I를 다시 실행하지 않았다. 원본 파일 export SHA, I에서 D의 위치로 가는 대응, 페이지 영역에서 I로 돌아가는 대응을 검사했다. OCR 문자 전사가 완전하다고 주장하지 않는다.

추가 D/I는 기존 source 저장소에 등록했고 새 다중 I2K K는 **`palimpsest-multi-checks` 서버의 별도 `palimpsest_multi_papers` DB**에 저장했다. 기존 `palimpsest-knowledge` DB의 schema는 0006이다. 그 DB에 대한 0007 적용은 자동 승인 검토가 거절해 사용자 승인을 기다리고 있다. 격리 실험 DB는 변경 전 백업을 복원해 0007을 적용한 별도 대상이다.

준비 중 실수도 있었다. 과거 block profile 경로를 사용해 Clarke 159개와 Dejani 126개, 합계 **285개의 원치 않은 부모 block I**를 만든 뒤 최종 group/page I를 만들었다. 최신 grouped 저장 원칙에 맞지 않는다. 기존 IDs/내용을 삭제하거나 다시 쓰지 않고 이력을 남겼다. 해당 helper는 이후 로컬 검증 전용으로 바꿨으며 새 등록에 사용할 수 없다. 285개는 모델에 전달한 51개 I에 포함하지 않았다.

## 실제 모델 결과

동일 Codex OAuth `gpt-5.6-terra`, reasoning `medium`을 사용했다. Generator와 Validator는 다른 실제 provider 세션이다. 구조화 출력과 원문 블록 ID를 검증했으며, 원본 PDF를 전달한 것처럼 기록하지 않았다.

| 실행 | 결과 | canonical 영향 |
|---|---|---|
| attempt-01 | 87 I/94 이미지, 응답 확보 실패·원인 미확정 | 없음 |
| attempt-02 재시도 | 8 후보, Unicode/LaTeX 인용 불일치 | 없음 |
| attempt-03 | 12 후보, Figure caption을 건너뛴 비연속 인용 | 없음 |
| attempt-04 | 10 후보 모두 Validator 승인. R848 실험 누락은 별도 지적 | 새 K 10개; 실행은 `needs_human` |
| attempt-05 → attempt-06 | 11 후보. 실행 profile 설정 오류는 실패로 남기고, 실제 요청 bytes와 입력 snapshot이 완전히 같은 새 실행에서 응답 재사용 | 새 K 1, 기존 Revision 재사용 9, 기각 1; `needs_human` |

attempt-05 응답을 attempt-06에서 새 모델 호출로 세지 않았다. [정확한 재사용 감사](attempt-06/generator-reuse-audit.json)에 원래 실행, 새 실행, request/response SHA와 동등성 검사를 남겼다. Runtime이 새 profile의 prompt/schema/media/input 해시를 다시 검사했다.

새 K는 합계 **11개**다. 후속 9개는 기존 K와 같은 의미로 판정돼 같은 Revision을 사용했다. 별도 R848 실험 1개만 새 K로 만들었다. 같은 요청의 replay는 같은 실행 ID를 반환했다. 기존 32 K를 합치면 **43 K/43 NodeRevision**이다. 다중 Data 근거를 가진 실제 K는 **0개**이며, 일반 K는 단일 source에서만 선택됐다. 여러 Data → 한 K 저장은 synthetic source/receipt를 사용한 실제 PG 테스트에서는 통과했지만 실제 논문 모델의 성공으로 대체해 보고하지 않는다.

## 확인된 의미 오류

1. **처치군별 결과의 범위 확대.** Dejani의 체중·대장 길이 개선을 EP4와 indomethacin 두 처치 모두의 결과처럼 묶었다. 처음 Validator는 승인했지만 강화한 후속 Validator는 원문에서 EP4 처치에만 명시됐다는 이유로 기각했다. 앞서 승인된 같은 오류의 K는 역사 Revision으로 실험 DB에 남아 있으므로 재검토가 필요하다. 후속 후보 기각이 기존 K를 자동 취소하지 않는다.
2. **인용 범위가 부족한 승인.** Clarke DC의 PD-L2 증가 방향은 앞 블록에 있는데 continuation만 인용했다. 전체 I에는 근거가 있지만 선택된 quote만으로는 주장 전체가 충분히 뒷받침되지 않는다. 후속 Validator도 이를 기존 K 재사용으로 통과시켰다.
3. **공통 지식과 추출 단위.** 모델은 서로 다른 실험을 별도 source로 유지했으나 공유 정의·배경을 거의 선택하지 않았다. 일부 서로 다른 assay·cell system·perturbation을 한 Observation에 묶는 경향도 남았다.

새 C1q/PGE2/SuperMApo 통합 기전을 만들어내는 cross-paper 추론은 관찰되지 않았다. 그 사실이 모든 원문 범위 오류의 부재를 의미하지 않는다. [독립 의미 감사](evaluation/attempt-04-generator-review.md)는 고정 평가 기준을 모델에 제공하지 않고 수행했다. 전체 I별 review가 있다는 사실과 모든 중요한 주장을 회수했다는 사실도 구분한다. 비canonical 모델 출력·실패 자료는 이번 조사 증거이며 기각 후보의 유사 검색 corpus로 쓰지 않는다.

## 검증과 후속 판단

- 최종 고정 이미지 `palimpsest-multi:0.5.0`, ID `sha256:87730e28a1d03dd295ea55905dfa25205881cfc840281ee7a0b8486a48304753`.
- `docker build --tag palimpsest-multi:0.5.0 .` 성공. source/test bind 없이 `docker compose -p palimpsest-multi-checks run --rm --no-deps -T test`: **484 실행, 468 pass, 기존 환경 skip 16, 실패/오류 0**, 77.305초. [정확한 명령·결과](app-tests-frozen-final.json).
- 다중 source PG 13개와 신규 CLI routing PG 2개가 최종 전체 검사에 포함됐다. 이는 실제 PostgreSQL 테스트이며 semantic 응답은 fixture다.
- `python tools/validate_bundle.py`: exit 1. 기존 raw Markdown 표 오류 **12개와 동일**, 새 오류 0. 문서 검사를 성공이라고 보고하지 않는다.
- DB의 원문 quote/char 범위와 Edge endpoint Revision 소유권 오류 0. 기존 32 NodeRevision·26 EdgeRevision·69 grounding은 정렬된 실제 행의 SHA가 변경 전과 같다. 최종 계수와 N2E 결과는 [DB 감사](database-verification.json)와 후속 결과에서 확인한다.

다음 구현 우선순위는 기존 K를 안전하게 재검토하는 경로, 각 명제의 material clause와 인용 범위를 확인하는 검증, 한 번에 모든 논문을 넣기보다 전체 I 검토 의무를 유지한 작은 추출·공통 의미 대조 루프다. 중요성 선택은 계속 LLM이 담당한다. D2I 재생성, 스크립트의 중요도 필터, 원문에 없는 결론 생성으로 해결하지 않는다.

N2E는 기존 K를 포함한 43개 NodeRevision으로 실제 Generator·Validator를 실행했다. 제안 2개 중 1개는 대조군 실패만으로 여러 인자의 공동 작용을 뒷받침할 수 없다는 이유로 기각됐고, 1개는 원문의 제한된 저자 해석에서 더 넓은 결론의 해당 부분을 지지하는 관계로 승인됐다. 새 Edge는 Test_Paper의 기존 K 사이 관계이며 새 논문이나 여러 Data를 연결하는 Edge가 아니다. N2E 실행 자체는 completed이고 **최종 43 K/43 NodeRevision, 27 Edge/27 EdgeRevision, 91 grounding**이다. I2K의 미완료 검토와 후속 전파 의무는 남는다.

기존 오류 K 두 개의 정확한 Node/Revision/Record와 재검토 이유는 [review-required.json](review-required.json)에 남겼다. 이는 정식 canonical invalidity 상태나 수정 Revision 구현을 대신하지 않는다. [summary.json](summary.json)에 의미 품질의 `semantic_release_acceptance=false`를 명시했다.

최종 격리 DB 백업은 `palimpsest-multi-papers-final-20260911.dump`, **5,141,480 bytes**, SHA `d409a270c54dbadc4e615fa86f8581de349f353de5f4bae58caad1193bc91b78`이다. PGDMP header와 `pg_restore --list` 성공(395줄)을 확인했다. 최종 dump를 다시 전체 복원한 검사는 하지 않았다. DB dump와 별도로 원본/파생 bytes가 있는 `palimpsest-knowledge_artifacts` 볼륨을 보존해야 한다. [백업 기록](final-backup.json)을 확인한다.

Docker 확인에서는 이미지 22개/컨테이너 11개/dangling 0개였고, 이번 작업에서 생긴 실패 자원 중 제거 후보는 0개였다. 검증된 현재/이전 앱, 선택 MinerU, 실제 DB와 볼륨, 모델 가중치는 보존했다. 삭제했다고 보고하지 않는다. [자원 점검](docker-removal-candidates.json)에 범위와 제외 근거가 있다.

이번 실험을 T04 전체, K2K 또는 RAG 제품 완료로 표시하지 않는다. 실제 다중 source 입력·저장과 재사용은 확인했고, **실제 multi-Data 근거 K 생성·기존 오류 K의 재검토·의미 추출 완전성**은 미충족이다. 문서에 예시를 써 넣거나 모델 후보를 수작업으로 고쳐 이 기준을 통과시키지 않았다.
