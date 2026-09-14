# Identity·fingerprint·materiality

> 상태: PROPOSED IMPLEMENTATION CONTRACT · 주 승인 항목 P01.
> U08 부분 적용: R04의 domain eligibility/identity 우선, 현재 usable reuse, 사전 context digest와 rejection scope 규칙은 [해결 계약](../decisions/ARCHITECTURE_FIXES.md)의 정확한 범위에서 현재 규칙이다. 나머지 P 세부 제안/enum/DDL은 미승인이다.
> U09 부분 적용: Data 원본 SHA-256, 나머지 신규 opaque UUIDv7와 등록 duplicate/retry 구분은 [저장 계약](../decisions/STORAGE_IDENTITY.md)을 따른다. 승인된 U 범위 밖의 새 필드·enum·명칭은 관련 P의 구체 승인 전 production canonical 계약으로 사용하지 않습니다.


## 원본에서 유지하는 규칙

I는 Data/grounding-specific snapshot입니다. K는 logical identity와 immutable semantic revision을 분리합니다. Decision은 event identity를 가집니다. 표시 문장이나 embedding similarity만으로 truth/identity를 확정하지 않습니다. 근거: baseline §5–7, §11–12, §20, A7/A9/A19/A26/A38/A39.

## 이번에 제안하는 구현 계약

### 1. Identity registry

각 Information/KNode kind와 KEdge predicate에 다음을 정의하십시오: identity projection schema, semantic payload schema, normalization version, identity에서 불변인 필드, 동일 identity 안에서 수정 가능한 필드, 별도 객체로 공존해야 하는 경우, 허용되는 Operation/mode.

특히 proposition의 scope/time/polarity는 변경되었다는 이유만으로 자동으로 같은 Node의 Revision이 되지 않습니다. 원문 정정인지 서로 공존하는 조건별 주장인지 확인합니다. entity name은 ID가 아니며, 이름이 같다는 이유로 node를 병합하지 않습니다.

### 2. Domain-aware duplicate pipeline

판정 순서는 eligibility → identity domain → exact content comparison → materiality입니다.

- Data 등록: 실제 보존 bytes의 SHA-256을 data_id로 사용한다. 새 request의 같은 bytes는 duplicate_data이며 새 Data/acquisition/D2I를 만들지 않는다. 동일 성공 request와 고정 입력의 retry는 기존 결과를 반환한다. bytes가 다른 같은 논문은 별도 Data이며 제목/DOI/embedding 유사도로 자동 기각하지 않는다.
- Information reuse: 같은 D + 같은 evidence locus + 같은 semantic snapshot만 허용합니다. 다른 D는 별도 I입니다.
- 일반 K reuse: current usable semantic state와 동일한지 확인합니다. historical content match는 비교 대상일 뿐 current pointer를 과거로 이동하는 명령이 아닙니다.
- W2K reuse: 동일 confirmation event가 만든 같은 Wisdom retry만 허용합니다. 다른 사건의 동일 선택은 새 decision입니다.
- `reused` 후보의 새 evidence는 별도 grounding validation을 통과해야 합니다. content equality가 새 근거의 유효성을 증명하지 않습니다.
- content_fp는 lookup key이며 모든 proposal Record에 걸 전역 unique key가 아닙니다. 동일 content에 여러 검토·근거 추가 Record가 필요합니다.

### 3. 두 단계의 validation context

사전 cache key는 Validator에 실제 전달할 frozen candidate/input/context/check/profile의 digest입니다. LLM 실행 후 보고한 used refs는 audit/attribution이며 사전 key를 대체하지 않습니다. 입력에서 볼 수 있었던 중요한 반증을 “사용하지 않았다”는 이유로 cache key에서 빼지 않습니다.

동일한 계산을 구분하는 semantic work key와 실행 원인을 추적하는 trigger/root/attempt 기록은 분리할 수 있습니다. 사건 ID·현재 시각·telemetry counter가 달라졌다는 이유만으로 동일 의미의 재검증이 무한 반복되어서는 안 됩니다. 반대로 유효성이나 authority가 변하면 payload가 같아도 relevant context token은 바뀌어야 합니다.

### 4. Rejection key

전역 invariant-hard rejection은 context와 무관한 동일한 불법 표현에 한정합니다. locator 오류에는 D/extractor/locator, schema 오류에는 schema version, forbidden operation-kind 조합에는 policy/registry version을 key에 포함합니다. corrected grounding을 semantic content FP만으로 막지 않습니다. provider failure는 failed execution이지 rejected knowledge가 아닙니다.

### 5. Materiality receipt

제안 필드: `comparison_base_revision_id`, `comparison_policy_version`, `changed_paths`, `identity_relation`, `materiality`, `reason_codes`, `evidence_refs`.

`materiality`는 제안 enum `material | non_material | undecidable`이며 불확실할 때 false로 축약하지 않습니다. 각 필드의 단위/정규화/정밀도/허용 오차는 kind 정책이 소유합니다. 오차의 실제 수치나 near-duplicate threshold는 이 문서가 승인하지 않습니다.

항상 current accepted snapshot을 기준으로 비교합니다. 무시된 candidate를 다음 비교의 base로 쓰지 않아 작은 변화의 누적 손실을 막습니다. 동일 의미 관계는 자동으로 추이적이라고 가정하지 않습니다. 극성·양화사·적용 대상·권한·행위·순서 있는 procedure 단계의 변경은 deterministic check로 드러내야 합니다.

### 6. 검증 조건

AT06–08, AT22–27, AT41–42, AT76을 fixture로 구현합니다. threshold를 넘어섰다는 이유만으로 승인하지 않으며 Validator와 grounding이 모두 필요합니다. semantic gate의 결과와 side effect의 실제 impact를 구분합니다.

U08/R08 사용자 선택: rejected Record는 정확한 rejection scope/FP로만 조회한다. rejected semantic similarity는 의무/기능으로 두지 않는다. accepted semantic similarity는 유지하며 다른 FP/수정된 locator는 새 검증 경로로 간다. optional audit/raw output을 rejected retrieval 데이터원으로 사용하지 않는다.

U09의 신규 opaque object/revision/Record/execution/acquisition/request ID는 UUIDv7이다. 외부 actor/provider/model ID와 fingerprint/digest/counter의 의미는 그대로 두며 과거 ID를 재발급하지 않는다. content hash와 UUID의 SQL 형식·검사는 [T02 SQL 초안](../schema/T02_STORAGE_SCHEMA.md)에 있고 아직 DB에 적용하지 않았다.
