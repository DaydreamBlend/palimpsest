# 여러 Data의 Information을 근거로 하는 I2K

2026-09-11 최신 정정: [I2K 원문 정리·새 결론은 K2K](I2K_SOURCE_ONLY_K2K_INFERENCE.md)를 적용한다. 여러 D의 I에 명시된 내용은 함께 정리할 수 있지만 I2K에서 원문에 없는 결론·추측을 도출하지 않는다. 새 I2K-origin Revision은 `is_inferred=false`이며 실제 다중 Data 실험은 [진행 계획](../../progress/T04_multi_source_runtime_execplan.md)에서 별도로 검증한다.

2026-09-11 사용자 명확화: **I2K는 하나 이상의 I를 근거로 하나의 K를 만드는 조합이며, 그 I들은 서로 다른 D에서 올 수 있다.** [기존 I2K §13](../canonical/06_knowledge_operations.md)의 seed I + same-D related I + corpus related I를 다시 명확히 한다. [전체 I 검토](FULL_SOURCE_LLM_SELECTION.md)의 단일 문서 실험을 제품의 입력 한계로 해석하지 않는다. 실제 구현 상태는 아래와 구분한다.

## 입력과 결과의 단위

일반 I 기반 후보/판정 Record는 I 1개 이상을 근거로 사용하고, 승인·재사용 시 결과는 하나의 KNode 또는 그 정확 Revision이다. 기각·보류에는 새 canonical K 결과가 없다. 한 모델 호출·실행은 이런 후보를 여러 개 처리할 수 있다. 한 I가 여러 K의 근거가 될 수도 있으므로 전체 저장 관계는 I ↔ K의 다대다다. 한 호출에서 한 K만 반환해야 한다거나 한 I가 하나의 K에만 속해야 한다는 제한을 만들지 않는다.

직접 D 예외에서는 I가 원본 조회의 출발점일 수 있지만 결론을 지지하는 I grounding을 강제하지 않는다. [원본 예외 계약](I2K_DIRECT_SOURCE_EVIDENCE.md)의 실제 D 근거와 누락/불일치 기록을 사용하며, 존재하지 않는 supporting I를 만들어 이 cardinality에 맞추지 않는다.

```text
D_A → I_A1 ─┐
D_A → I_A2 ─┼→ I2K 후보/검증 → K_X Revision
D_B → I_B3 ─┘
```

I의 소유 Data는 그대로다. 서로 다른 D의 I를 합쳐 새 I로 저장하지 않으며, 같은 I 본문·이미지·페이지 번호가 등장해도 각 원문의 위치를 유지한다. 후보에는 실제 근거가 된 I만 연결하고 모델에 보여 준 모든 I를 무조건 grounding으로 붙이지 않는다. 참고 문맥/상충 근거/선택 근거와 실제 사용을 구분한다.

## 전체 검토와 후보 근거

새 문서의 최초 I2K 처리에서는 선택된 완료 source execution의 **전체 I를 검토하는 의무**를 유지한다. 문서 A를 검토하면서 문서 B/C의 관련 I를 함께 조회·사용할 수 있다. B에서 일부 I를 가져왔다고 B 전체를 검토했다고 기록하지 않는다. 여러 문서를 전체 검토 대상으로 삼았다면 각 문서의 source snapshot과 I별 의무를 따로 추적한다.

하나의 K는 그 검토 입력 중 필요한 I 집합을 사용한다. 문서의 전체 검토와 K별 evidence 집합은 별도다. 기존 I를 조합하는 후속 작업이 과거 문서의 전체 검토 기록을 덮어쓰지 않는다. corpus의 모든 I 조합을 무차별 열거할 의무로 확대하지 않으며, 검색 후보의 부재를 근거 부재나 전체 검토 완료로 처리하지 않는다.

## provenance와 저장 계약

실행은 실제 입력된 I의 순서/역할과 각 I가 속한 Data·source execution·profile·parse/source/input hash를 동결한다. Data별 완료 source snapshot을 결속하고 동일 Data의 여러 역사 실행을 의도 없이 섞지 않는다. 실행의 대표 Data가 남더라도 그것은 작업 시작점을 나타내는 값이며 모든 K 근거의 소유 Data로 사용하지 않는다.

K의 각 grounding에는 exact I ID, 문자 범위/quote 또는 실제 I media SHA, 해당 I의 source 위치와 origin Record를 연결한다. I의 Data는 canonical FK로 확인한다. 새 다중 source 입력은 각 source를 검증한 뒤 결합하며 단일 `data_id`를 바꿔 다른 D의 I를 끼워 넣지 않는다. 같은 문구가 여러 문서에 있어도 인용의 I/Data 귀속을 잃지 않는다.

원본 확인이 필요하면 요청이 지정한 I의 실제 D로 내려간다. 여러 문서의 같은 페이지 번호를 하나의 원본으로 해석하지 않는다. 직접 D 근거와 누락/불일치 기록은 [기존 원본 예외 계약](I2K_DIRECT_SOURCE_EVIDENCE.md)을 따르며 D2I를 재실행하거나 새 I를 만들지 않는다.

모든 입력의 read-set, 실제 전달 receipt, 후보 판정과 정확 result refs, grounding, Record, 후속 outbox를 기존 freshness/atomic commit 규약으로 묶는다. 기존 I·K·Revision·FP와 완료 migration/profile/replay를 재작성하지 않고 추가 구현한다.

## 여러 근거와 의미 중복

| 경우 | 처리 |
|---|---|
| 서로 다른 문서가 같은 일반 명제를 직접 뒷받침 | 하나의 K를 생성/재사용하고 각 I의 근거 추가 |
| 여러 I가 같은 대상의 설명·조건을 상호 보완 | 함께 검증해 하나의 의미 일관된 K를 구성 |
| 서로 다른 논문의 별개 실험 결과가 유사 | 원래 source-specific 결과 K를 별도로 유지; 하나의 Observation으로 합치지 않음 |
| 여러 실험에서 원문에 없는 새 종합 결론이 필요 | I2K에서는 생성하지 않음. 검증된 전제 K를 사용한 K2K에서 도출·범위·불확실성을 검증 |
| 기존 K와 같은 의미에 새 I 또는 도출 근거만 추가 | 기존 K/Revision 재사용. semantic Revision 증가 없음 |

**근거의 Data 집합과 K의 의미 scope는 다르다.** K가 여러 D의 I를 인용한다고 자동으로 `general`인 것은 아니다. 실험 결과의 귀속, 종/코호트/조건/시간과 결론이 적용되는 범위를 유지한다. 여러 Data에 한정된 종합 주장을 현재의 단일 `source_data_id`에 억지로 맞추거나 대표 D 하나에 귀속하지 않는다.

새 grounding Data가 추가되었다는 사실만으로 K의 identity FP를 바꾸지 않는다. 같은 명제의 evidence 집합과 명제 자체의 의미를 분리한다. 명제의 대상이 특정 연구 집합 자체이거나 조건/범위가 실질적으로 변한 경우에는 기존 materiality 검증을 적용한다. 다른 Data에 보고된 실험의 독립성도 단순 파일 수로 승인하지 않는다.

## I2K/K2K와 추론 표시

I2K는 실제 I에 명시된 내용을 직접 근거로 정리한다. K2K는 accepted KRevision/EffectiveEdge를 전제로 새로운 결론을 도출한다. 기존 K를 의미 중복 비교용으로 조회했다는 이유만으로 I2K가 K2K가 되는 것은 아니다. 명시된 내용을 하나의 K로 통합할 때 모든 I를 먼저 각각 K로 만들 필요는 없다. 그러나 원문에 없는 새 관계·일반화·가설을 만들려면 필요한 전제 K를 검증한 뒤 K2K의 typed dependency와 검증 경계를 따른다.

새 I2K-origin Revision은 `origin_operation=i2k`, `is_inferred=false`다. I2K에서 원문에 없는 결론을 생성한 뒤 추론 flag만 붙여 허용하지 않는다. 새로운 귀납·연역 결론은 K2K가 생성하며 `is_inferred=true`와 실제 KRevision 전제·도출 유형·가정/범위·검증을 연결한다. 기원 metadata는 실제 생성 Record와 검증된 operation에서 확인하며 모델의 임의 선언을 신뢰하지 않는다. 기존 K를 재사용할 때는 재사용 작업의 operation으로 기존 Revision의 생성 기원을 바꾸지 않는다.

이 규칙은 [추론 기원 표시](LLM_WIKI_RETRIEVAL.md)를 세분화한다. 원문 저자의 추론을 전달하는 것과 시스템 자체의 새 도출을 구분한다. 추론으로 새로운 실제 Observation이나 authority-confirmed Decision을 만들어내지 않는다. 동일 K에 직접·추론 근거가 나중에 추가되어도 기존 Revision의 생성 기원을 바꾸지 않는다.

## 현재 제한과 후속 검증

현재 입력 결합·원문 명시 검증·원자적 저장 코드는 [다중 Data Runtime 안내](../implementation/MULTI_SOURCE_RUNTIME.md)에 따라 구현되고 격리 PG 검사를 통과했다. 세 논문의 실제 의미 평가는 첫 호출의 실행 오류 이후 진행 중이며 결과는 미확정이다. 기존 보존 DB의 0007 적용 승인 대기와 별도 격리 DB 설치를 구분한다. 아래 단일 Data 제약 설명은 확장을 시작한 시점의 기준이다.

이 요구를 받은 시점의 `knowledge.py` 후보 evidence와 `knowledge_node_groundings`는 여러 I를 표현하지만 `KnowledgeRuntime.prepare/_verify_i`, `i2k-input-v1`, `0005` 입력 guard와 `0006` scope/전체 source 완료 guard는 단일 Data/source execution을 전제로 했다. 사용자는 이제 **원문 정리 경계를 지키는 다중 Data I2K의 구현과 실제 실험**을 요청했다. [현재 실행 계획](../../progress/T04_multi_source_runtime_execplan.md)의 결과로 지원 여부를 판단하며 이번 문서 변경을 구현·실험 완료로 보고하지 않는다.

후속 구현은 각 source snapshot을 검증하는 입력 목록, 후보별 다중 I 근거, 문서별 전체 검토 의무, source scope와 evidence Data의 분리, 실제 전달/원본 요청, 중복/추론 기원 및 atomic 저장을 함께 확장해야 한다. 단일 Data 검증을 단순 삭제해 무검증 입력을 허용하지 않는다. 기존 single-source 실행과 replay는 유지한다.

최소 acceptance는 다음과 같다. 이번 문서 검증으로 통과 처리하지 않는다.

- 두 Data에서 각각 한 I를 사용한 K 하나가 두 exact I/Data/source 구간으로 역추적된다.
- 같은 I가 두 K의 근거가 되어도 복제 I가 생기지 않으며 후보별 인용/판정이 구별된다.
- 다른 D의 유사 Observation은 병합하지 않고, 원문에 없는 종합 결론은 I2K에서 차단한다. 새 결론의 실제 도출·검증은 K2K 범위다.
- 같은 의미에 근거만 추가하면 Node/semantic Revision이 늘지 않으며 입력 순서 변경을 새 의미로 취급하지 않는다.
- 미등록 I, 다른 source/hash, 실제로 전달하지 않은 media, 바뀐 read-set을 거부한다. 완료/replay와 실패 시 atomicity를 검사한다.
- 새 문서의 전체 I 검토 의무와 추가 조회한 타 문서 I를 구분하고 일부 조회를 전체 검토로 기록하지 않는다.
- 여러 원본의 페이지 번호 충돌에서 정확한 D를 조회하며 D2I 호출/I 변경은 0이다.
- 새 I2K-origin Revision은 exact 원문 지지와 `is_inferred=false`를 갖고, 원문에 없는 결론을 승인하지 않는다. K2K 추론의 `is_inferred=true`·전제 refs와 기존 Revision 기원 보존은 해당 경로에서 검증한다.

[실행·점검 기록](../../progress/T04_multi_source_i2k_execplan.md).
