# 전체 source의 주소와 LLM 지식 선택

2026-09-11 최신 I2K 경계: [원문 정리와 K2K 새 결론의 구분](../decisions/I2K_SOURCE_ONLY_K2K_INFERENCE.md)을 적용한다. [다중 Data Runtime](MULTI_SOURCE_RUNTIME.md)의 코드·격리 PG 검증과 아직 미확정인 세 논문 의미 실험을 구분하며 [실행 계획](../../progress/T04_multi_source_runtime_execplan.md)을 확인한다. 아래 단일 문서 결과를 다중 Data 의미 실험의 완료로 보고하지 않는다. 전체 source 검토 의무와 후보별 근거 집합은 구분하고 신규 I2K-origin Revision은 `is_inferred=false`다.

2026-09-11 최신 관점: [LLM Wiki 계층 검색](../decisions/LLM_WIKI_RETRIEVAL.md)에서 K는 자주 활용할 것으로 LLM이 판단한 사전 지식이며, K에 없는 내용도 I 검색에 보존한다. [직접 원본 근거 정책](../decisions/I2K_DIRECT_SOURCE_EVIDENCE.md)에 따라 I2K의 근거 부족으로 D2I/regroup/source-pages나 새 I 생성을 호출하지 않는다. 아래 source-pages CLI는 기존 보존 기능 설명이며 I2K에서의 누락 복구 수단이 아니다.

[사용자 승인](../decisions/FULL_SOURCE_LLM_SELECTION.md)에 따라 D의 구간에서 I를 찾고, I에서 D의 원문 위치를 찾는다. 중요성은 I2K의 LLM이 판단하며 스크립트는 원문을 선별해 버리지 않는다. [실제 결과](../../output/t04-full-selection/REPORT.md)와 [실행 기록](../../progress/T04_full_source_selection_execplan.md)을 함께 읽는다.

## 원문과 I의 양방향 대응

`source_pages.py`의 `source-groups-pages-v1`은 기존 source groups를 그대로 재사용하고 원본 PDF의 전체 페이지 이미지를 실제 Image I로 추가한다. 부모 bundle/profile/parse manifest, original PDF hash·크기, renderer/geometry/PNG hash를 결속한다. 별도 `original_page_facsimile` collection으로 표시하므로 MinerU가 찾은 block으로 위장하지 않는다. 기존 source 실행·I·FP는 변경하지 않는다.

PDF의 어느 유효 page/bbox를 조회해도 해당 페이지 Image I가 있으며, 세부 파서 근거가 있으면 해당 text/image group도 같이 반환한다. 페이지 이미지 보존은 기록한 해상도의 시각적 대응이며 완벽한 OCR·문자별 glyph bbox의 증명은 아니다. 원본 PDF 전체 bytes는 등록된 Artifact Store에서 hash를 확인해 복원한다. Markdown은 보존된 block text를 합쳐 원본 UTF-8 SHA를 확인하고 byte/line/character 범위로 조회한다.

```text
palim compile source-pages --execution-id SOURCE_EXECUTION --directory EVIDENCE
palim information reconstruct --execution-id NEW_SOURCE_EXECUTION
palim information locate --execution-id NEW_SOURCE_EXECUTION --page 3 --bbox 0 0 1 1
palim information locate-information --execution-id NEW_SOURCE_EXECUTION --information-id I_UUID
palim information locate-information --execution-id NEW_SOURCE_EXECUTION --information-id I_UUID --char-range 10 40
palim information export-source --execution-id NEW_SOURCE_EXECUTION --destination OUTPUT.pdf
```

`source_reconstruction.py`는 순수 재조립/위치 규칙, Compiler Runtime은 실제 DB/원본/derived 파일 검증을 소유한다. `export-source`는 다른 기존 파일을 덮어쓰지 않으며 같은 bytes의 재호출을 구분한다. 완전한 source 처리에는 한 source execution을 선택한다. 서로 다른 역사 버전의 I를 모두 합쳐 중복 입력하지 않는다.

## 중요성 선택과 identity scope

새 I2K CLI의 기본은 `source-complete-i2k-v1`이다. source execution의 모든 I를 target으로 입력하고, subset·누락된 review·실제 전달하지 않은 media를 거부한다. PDF 선택에는 원본 페이지 Image I가 있는 source profile을 요구한다. 과거 실행의 replay와 명시적인 내부 legacy 호환은 보존하지만, 새 legacy 실행의 미분류 cross-Data 재사용도 차단한다.

LLM은 각 I에 selected/context_only/not_selected/needs_review와 이유를 반환한다. 후보에는 중요성을 선택한 이유와 general/source scope가 있다. Validator도 전체 I를 검토하고 각 후보의 중요성·scope·의미 동등성·근거를 판정한다. `complete=false`라도 모든 판정이 있으면 검토 의견으로 저장하고 해당 실행을 needs_human으로 남긴다.

| 대상 | 재사용 규칙 |
|---|---|
| general Proposition | 의미·조건·범위가 거의 동일하면 기존 K/Revision과 연결하고 새 grounding 추가 |
| source Observation | Data가 다르면 재사용하지 않음 |
| source 결과 해석 Proposition | 일반 사실처럼 처리하지 않고 Data 귀속 보존 |
| 같은 Data의 반복된 주장 | 같은 실험·조건·의미임을 검증한 뒤 재사용 |
| legacy scope 미분류 K | 명시적으로 검증한 compatible scope를 한 번 연결; 기존 ID/FP/Revision은 그대로 |

유사도는 의미 동일성을 확정하지 않는다. 현재 작은 catalog는 기존 K를 모두 비교 문맥에 제공하며 BGE 검색/index 구현을 완료했다고 주장하지 않는다. 중요성·scope·동등성은 LLM 판단이고, Data scope/typed refs/FP/ID/현재성/atomic commit은 코드가 검사한다.

## 스크립트와 LLM의 책임

`i2k_selection.py`가 전체 I coverage·동적 schema·정확 citation·scope FP를 검사하고, `selection_prompts.py`가 LLM의 선택/검증 정책을 정의한다. `knowledge_runtime.py`는 `0006_i2k_selection`의 I별 review·review→Record 연결·Validator review·K scope를 durable 저장한다.

후보 evidence가 이미 가리키는 I와 selected review 사이의 누락된 역참조는 스크립트로 완성한다. 이때 I의 선택 상태·이유·후보 의미·인용은 바꾸지 않고 `review_link_completions`를 기록한다. 존재하지 않는 인용을 만들거나 context_only/not_selected를 임의로 selected로 바꾸지는 않는다. 중요도 선별과 기계적인 참조 목록 정리를 구분한다.

I에 추가로 추출할 것이 있다는 review는 개별 승인 K를 무효화하지 않는다. 개별 accepted/reused 효과는 저장하고 I 검토 의무 때문에 전체 실행을 needs_human으로 남긴다. 원본 확인을 요청했으나 실제로 제공하지 못한 근거에 의존하는 후보는 별도로 보류한다.

```text
palim information prepare-input --execution-id NEW_SOURCE_EXECUTION --directory PARENT_EVIDENCE
palim knowledge prepare --operation i2k --selection --data-id DATA_SHA --request-id UUID7 --input INPUT.json
palim knowledge stage EXECUTION --response GENERATOR.json
palim knowledge decide EXECUTION --response VALIDATOR.json
palim knowledge prepare --operation i2k --selection --data-id DATA_SHA --request-id NEW_UUID7 --input INPUT.json --feedback-execution-id PREVIOUS_EXECUTION
```

후속 실행은 같은 Data/source의 이전 review·오류를 동결 snapshot에 포함하고 전체 I를 다시 받는다. 구조 오류의 원문 excerpt는 실제 I의 위치에 결속하며 의미를 자동 교정하지 않는다. 과거 판정과 실패는 덮어쓰지 않는다. 실제 input/prompt/schema/media가 모두 같은 경우에만 기존 Generator 응답을 새 구현 profile에 재사용할 수 있다.

`tools/prepare_selection_call.py`는 전체 source context에서 실제 요청을 구성한다. `tools/run_knowledge_model.py`는 [현재 로컬 GLM provider](MODEL_PROVIDER.md)를 호출하고 입력·출력·prompt·schema·전체 I ID·이미지 hash receipt를 남긴다. Runtime은 DB snapshot으로 기대 prompt/schema를 재구성해 실제 receipt와 비교한다. 원문 일부를 빼고 ID 목록만 유지한 요청도 거부한다.

Validator의 재사용 참조는 상호 배타적인 object schema다. 기존 Revision, batch candidate, non-reuse 중 하나만 선택할 수 있다. nested `anyOf` 지원은 [공식 Structured Outputs 문서](https://developers.openai.com/api/docs/guides/structured-outputs)와 실제 모델 호출로 확인했다. JSON schema의 준수와 의미의 정확성은 별개다.

## accepted K 이후

N2E는 canonical의 정확 NodeRevision과 grounding을 받아 새 관계를 생성·검증하고 EdgeRevision에 저장한다. 이번 profile은 supports이며 공유 source를 독립 증거 수로 세지 않는다. Node와 Edge의 기존 semantic Revision을 원문 재조립이나 같은 의미의 grounding 추가만으로 변경하지 않는다.

이번 구현의 기준은 한 문서의 전체 I가 모델 context에 들어가는 실제 실행이다. 큰 문서의 여러 호출 분할·검색 index·일반 semantic Revision 교정·전체 K2K propagation·GUI release는 이후 범위다. per-I reviewed/confirmed는 모델이 반환한 처리 기록이며 사람의 원문 충실성 승인이나 전체 과학적 claim 정답률이 아니다.
