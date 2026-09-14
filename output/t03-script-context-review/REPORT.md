# 스크립트 초안 + Qwen3.5-9B 재검토 결과

Test_Paper 1편의 기존 image200 MinerU source I를 이용한 비canonical 문맥 projection 실험이다. 스크립트가 만든 초안을 먼저 고정하고 Qwen3.5-9B Q8_0가 지정된 후보만 검토했다. 원문 D/I, 과거 파서 결과, DB, K 및 제품 모델 기본값은 변경하지 않았다.

정식 21회 중 21회가 독립 구조 검증을 통과했다. 3개 반복의 최종 partition은 1종류였다. 세 번 모두 제목 없는 Abstract I57을 metadata에서 분리했고 기존 원문 구조를 유지했다. 그룹 구성과 역할 개선의 대부분은 스크립트에서 발생했다.

| 항목 | 스크립트 초안 | 9B 검토 후 |
|---|---|---|
| 원문 배정 | 229/229, 누락·중복 0 | 각 반복 229/229, 누락·중복 0 |
| 제목 없는 Abstract | metadata로 보류된 1개 I | 독립 Abstract 그룹, 1,239자 |
| Introduction | p1–2의 4개 I를 한 그룹 | 유지, 2,882자 |
| Results / Methods | 실제 소제목 기준 7개 / 6개 그룹 | 유지 |
| Figure 5·6의 다음 페이지 캡션 | 원래 Figure 근거와 연결됨 | 유지 |
| Primary pairwise F1 | 0.966346 | 0.966346 |

Primary F1은 검토된 한 가지 그룹 구성과의 비교이며 일반 정확도가 아니다. Figure 1의 실제 두 소절을 유지한 데서 28쌍의 차이가 생긴다. 두 소절 모두 같은 Figure companion을 참조한다. Abstract는 primary 103개 안에서 singleton이므로 역할 수정이 이 F1을 바꾸지 않는다. metadata 오분류와 Abstract exact-group 판정을 별도로 봐야 한다. 이전 전체 논문 9B assignment의 F1은 약0.377이었지만, 입력·작업 분담·출력 구조가 함께 달라져 단일 변수 비교는 아니다.

모델의 정식 결정 60개는 {'keep': 57, 'abstract': 3}였다. 이유 코드의 검토 유형 불일치는 33개다. 실제 소절을 유지한 판단에 explicit_caption 코드가 붙는 오류를 확인했다. 구조화 JSON이 설명의 의미까지 보장하지 않는 사례다. 실제 적용 구조에서는 검토 유형은 애플리케이션이 기록하고, 모델에는 필요한 판단과 evidence IDs만 요청하는 편이 간단하다. 원래 모델 응답·잘못된 코드는 수정하지 않았다.

| 사후 민감도 대조 | 기대 | 실제 | 통과 |
|---|---|---|---|
| 원래 이어지는 문단을 임의 분할 | merge_previous | merge_previous | True |
| Figure5에 Figure6 continuation을 잘못 연결 | needs_context | needs_context | True |

이 대조는 첫 정식 반복 뒤 추가한 1회·2개 오류 점검이다. 명시적인 무제목 경계와 올바른 caption inventory를 함께 주었다. 원문은 바꾸지 않았고 expected.json은 모델에 보내지 않았다. 쉬운 두 사례의 관찰을 일반 오류 검출률이나 자동 교정 성능으로 확대하지 않는다.

실행 조건: 기존 Unsloth Qwen3.5-9B-Q8_0.gguf, revision3885219b6810b007914f3a7950a8d1b469d598a5, SHA809626574d0cb43d4becfa56169980da2bb448f2299270f7be443cb89d0a6ae4. llama.cpp b10380 고정 이미지·RTX5080·context32768·temperature0·seed42·cache off·thinking 설정2048·출력최대4096. thinking2048은 설정값이며 실제 reasoning token을 usage에서 따로 측정한 것은 아니다. 외부 추론/새 다운로드/이미지 빌드는0이다.

7개 packet에는 중복을 제외한 83개 I가 들어갔다. 실제 prompt는 1,111–7,146 tokens이고 잘라내지 않았다. 호출 시간 중앙값은 71.16초, 한 번의 7packet 합계는 [484.24, 511.81, 486.73]초다. 정식 호출시간 합계는 1482.78초다. 서버 로드·smoke·대조·도구 준비 시간은 별도다. GPU가 다른 작업과 경쟁하던 상태였으므로 이전 실험과 속도 우열을 단정하지 않는다.

미검증 범위: 논문 1편과 지정 후보20개, text-only 입력에 한정된다. native font/span 후보는 이 초안에 사용하지 않았다. 앞부분의 짧은 Abstract나 다른 배치, 후보에 포함되지 않은 잘못된 경계·누락된 제목은 추가 검토가 필요하다. 참고문헌과 뒤따르는 이해상충/저작권은 한 그룹에 남아 있다. Figure 번호 정규식은 완전한 인용 문법 해석기가 아니며 supplementary asset 존재를 만들어내지 않는다. 원문 OCR 정확도, 이미지 내용·panel의 시각 검증, K 생성, semantic embedding/reranking, 실제 app/PG e2e는 이번 시험에서 검증하지 않았다.

원본8파일과 PDF Data hash, 원문229 I의 provenance, 14개200DPI PNG 및 전체142개 이미지 파일 참조를 확인했다. 이미지 경로는 [경로·해시 audit](runtime/image-reference-audit.json)에 원래 기준 디렉터리와 함께 기록했다. mock invariant10개 및 독립 scorer의 합성/변조 검사를 통과했다. 문서 validator는 보존된 raw Markdown의 기존11오류로 exit1이며 새 오류와 구분했다.

[독립 평가](EVALUATION.md), [원문 대조 판정](FINDINGS.md), [상세 metrics](metrics.json), [문맥 그룹 크기](CONTEXT_GROUPS.md), [첫 반복 projection](final/repeat-1/projection.json), [동결 입력·정책](protocol.json), [실행 계획](../../progress/T03_script_context_review_execplan.md).
