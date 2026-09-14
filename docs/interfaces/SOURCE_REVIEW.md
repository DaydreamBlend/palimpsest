# 모든 source I의 원문 구간·의미 항목 검토

후속 코드 실험의 검토 지침: 코드의 literal 선언·설정값·함수 interface·명시된 조건/분기 동작도 원문에 있는 사실이다. 주석/docstring만 요약하거나 큰 파일을 하나의 추상적인 설명으로 처리하지 않는다. 무엇을 K로 선택할지는 LLM이 결정하고, 코드가 선언한 동작을 실제 실행/배포/테스트 결과로 바꾸어 말하지 않는다. 여러 구성요소를 결합한 새 결과는 K2K에서만 도출한다. [자료 버전 코드 실험](../../output/t12-versioned-code/REPORT.md)은 검토 보류와 실제 승인된 K를 구분한다.

2026-09-13 사용자 지시: 특정 논문의 Figure에 과적합하지 않고 모든 D→I→K에 같은 검토 구조를 적용한다. 새 전체-source I2K에 `source-review-v1`을 기본 추가한다. 기존 I2K의 원문 명시 내용만 K로 정리하는 경계, LLM의 중요성 선택, K2K만 새 결론 생성, 의미 동일 K 재사용과 정확한 Revision 보존을 유지한다.

구현은 [source_review.py](../../src/palimpsest/source_review.py), [공통 prompt/schema](../../src/palimpsest/knowledge_requests.py), [KnowledgeRuntime](../../src/palimpsest/knowledge_runtime.py)에 있다. [실행 계획](../../progress/T04_source_review_execplan.md)과 [실제 결과](../../output/t10-source-review/REPORT.md)를 구분해 읽는다.

## 세 종류의 단위

1. **Information:** 기존에 D2I가 저장한 불변 원문 표현이다. 수백 개 block I로 분할하거나 새로 생성하지 않는다.
2. **원문 검토 target:** 기존 I의 source block/문자 범위/소유 media 주소를 실행 입력에 열거한 비canonical projection이다. 중요도·과학적 의미·새 K 수를 결정하지 않는다.
3. **의미 검토 item:** LLM이 target 내부의 독립적으로 평가할 사실·결과·조건·예외·설명 등을 구분해 제출한다. 같은 큰 절이나 그림에 여러 item이 있을 수 있다. 독립 Validator가 원래 target을 다시 보고 내부 누락을 확인한다.

논문의 subpanel은 의미 item의 한 사례다. 표의 비교, Markdown/HTML의 문장·목록, 코드의 정의·동작·계약도 같은 구조로 검토한다. 구현에는 Figure 수, Test_Paper ID, 논문 절 이름을 이용한 중요도 규칙이 없다. 새로운 HTML/code D2I adapter를 이번에 구현한 것은 아니다. 이 계약은 유효한 source I 입력을 전제로 한다.

## 입력과 정확한 근거

`build_manifest(packet)`은 기존 `source_block_ranges`와 I의 `source_refs`·`media`를 재사용한다. 단일/다중 Data 모두 각 target에 정확한 Data, source execution, I, source block, 문자 범위, media SHA와 source refs를 연결한다. `target_id`는 이 불변 주소 기술의 SHA-256이며 새 canonical 객체의 opaque ID가 아니다. manifest 전체도 hash로 결속한다.

명확한 source 범위나 실제 소유 이미지가 있으면 `mapped`다. source refs가 없는 과거 입력은 원본 좌표를 추정하지 않고 `information_only`로 exact I 범위를 표시한다. 주소를 확인할 수 없는 block은 `unmapped`로 보존하고 `needs_review`를 요구한다. 실제 빈 target과 미확인 원문을 구분한다. 모든 source refs를 열거해도 의미적 완전성이나 OCR 정확도가 증명되지는 않는다.

Runtime은 기존 canonical source 검증 후 manifest를 frozen input snapshot에 저장한다. profile은 `source_review=source-review-v1`과 구현 hash를 추가한다. 기존 semantic fingerprint profile이나 과거 KRevision을 바꾸지 않는다. provider request export와 receipt 검증은 같은 prompt/schema builder를 사용하며, 전체 I와 필수 media의 실제 전달 확인을 유지한다. 모델에는 중복된 parser leaf metadata를 줄인 주소 projection을 제공하고 원래 전체 manifest는 Runtime에 보존한다.

## Generator와 Validator 출력

Generator는 기존 `nodes`, `reviews`, `source_requests`, `complete` 등에 다음 구조를 추가한다.

```json
{
  "source_reviews": [{
    "target_id": "exact frozen target hash",
    "items": [{
      "item_key": "content-1",
      "label": "원문이 보고하는 개별 내용",
      "disposition": "selected",
      "candidate_keys": ["candidate-1"],
      "anchors": [{"char_start": 10, "char_end": 30, "media_sha256": null}],
      "reason": "이 내용을 선택하거나 보류한 구체적 이유"
    }]
  }]
}
```

실제 값은 요청 schema와 exact source에 맞아야 한다. Text anchor는 해당 I의 Unicode codepoint 범위, image anchor는 char_start/end=null과 실제 소유 media hash를 사용한다. 한 target의 item 목록은 비어 있을 수 없다. disposition은 `selected`, `context_only`, `not_selected`, `needs_review`다. selected는 실제 후보에 연결하며, 기존 K와 같아도 후보를 내고 Validator가 reuse를 판정한다. context_only/not_selected는 빈 candidate_keys와 구체적 이유를 갖는다.

검사는 양방향이다. item의 각 후보가 해당 anchor 근거를 사용해야 하고, 모든 후보의 각 인용 I와 text/media 방식도 적어도 하나의 item anchor에 연결돼야 한다. 다른 Data/I의 같은 문장이나 같은 image hash를 출처 대용으로 쓰지 않는다. 넓은 caption 인용 안에 anchor가 있다는 사실은 그 안의 모든 의미를 K가 담았다는 증거가 아니다.

Validator는 기존 후보/I 판정과 별도로 `source_review_decisions.targets`의 모든 target과 `.items`의 모든 item에 confirmed/needs_review 및 이유를 반환한다. Generator가 제출한 item만 확인하지 않고 원문 target 내부의 누락된 결과·조건·대조·예외도 확인하도록 요청한다. 고정 item 수나 `complete=true`는 의미적 충분성의 근거가 아니다.

## 저장·완료·재사용

- Manifest는 기존 `k_execution_contexts.input_snapshot`, Generator 검토는 `operation_executions.generator_receipt.source_reviews`에 보존한다.
- 독립 검토와 pending target/item은 `validator_receipt.source_review_result`에 저장한다.
- Runtime이 실제 commit 결과를 사용해 item → candidate → Compiler Record → KNode/정확 KRevision의 `bindings`를 만든다. provider가 이 앱 소유 결과를 주입하면 거부한다.
- 기존 PostgreSQL JSONB를 사용하므로 새 migration은 없다. K 효과와 검토 결과는 같은 transaction으로 반영/rollback한다.
- target/item의 미검토, source 요청, rejected/needs_human 후보에 의존한 선택은 성공 완료가 아니다. 독립 검증된 다른 K가 저장되더라도 실행은 `needs_human`으로 남을 수 있다.
- 동일 의미의 새 근거는 기존 KRevision을 재사용한다. 패널/문장/이미지 표현이 늘었다고 semantic Revision이나 독립 실험 수를 늘리지 않는다.
- I가 부족하면 원본 D 확인과 근거 공백 이력을 유지한다. D2I 재실행·I 재작성·가짜 I 인용은 없다. 아직 실제 전달할 수 없는 원본 요청은 기존 Runtime과 같이 unresolved로 남는다.

`knowledge show` JSON의 `source_review`는 manifest, generator_reviews, validation과 exact 결과 연결을 제공한다. 전용 GUI 패널과 일반 원문 gap 해결 worker를 이번에 추가한 것은 아니다. 정상 canonical 반영 후 N2E는 기존 별도 과정이며, 이 기능이 supports를 자동 생성하지 않는다.

## 기본값과 과거 호환

새 CLI I2K는 단일 D도 기존 source-explicit wrapper를 사용하며 source_review가 기본으로 켜진다. Python Runtime의 기존 명시적 legacy 경로(`selection=False`)는 유지하고, 전체-source 작업은 `source_review=False`를 명시하면 이전 계약을 시험·재현할 수 있다. `source_review=None`인 같은 request의 replay는 저장된 원래 profile을 따른다. 이전 완료 Record가 새 검토를 통과한 것으로 표시되지 않는다.

원래 Compose 기본 이미지와 원본 DB의 migration 승인 상태는 바꾸지 않는다. 새 코드는 `palimpsest-source-review:0.10.0`에 빌드한다. 이미 준비된 별도 실행 환경에서는 그 이미지를 명시하고 기존 DB에 맞는 `--no-deps` 실행 경로를 사용한다. 이번 기능의 시험 대상은 격리 fixture DB뿐이며 원본 논문 DB를 자동 migrate하지 않는다.

구조·PG 검사는 정확한 주소, 이력, 반영 경계를 검증한다. 실제 LLM이 모든 의미 항목을 빠짐없이 찾는지와 일반적인 회수율·중복률은 별도 live 평가가 필요하다.
