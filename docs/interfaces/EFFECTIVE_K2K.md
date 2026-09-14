# EffectiveEdge를 실제 전제로 사용하는 K2K

2026-09-14. 앱0.20/schema0020은 기존 Node-only K2K를 유지하면서 `knowledge-inference-effective-v1`과 `k2k-effective-input-v1`을 추가한다. [실행 계획](../../progress/T21_effective_edge_k2k_execplan.md), [N2E 계약](N2E_RELATIONS.md), [기존 K2K](K2K_RUNTIME.md)를 함께 따른다.

## 입력과 저장

Edge 하나를 선택하면 현재 유효한 관계와 양 endpoint의 실제 KRevision 값을 함께 전달한다. 추가 Node 전제도 포함할 수 있다. 각 후보는 전달된 Node와 Edge 전체를 정해진 순서로 선언해야 하며, 모델이 일부 값을 인용하지 않았다는 이유로 의존성을 제거하지 않는다. 비교 catalog와 explicit target은 authoritative premise가 아니다. relation-only 별도 모드는 없다.

각 Edge는 logical ID, predicate, qualifiers, original endpoint pair, 6필드 EffectiveEdgeRef 및 endpoint support signatures를 동결한다. 이 typed 입력과 derivation Record를 추가 테이블로 연결한다. 과거 semantic Edge의 endpoint를 덮어쓰지 않는다. K2K 결과는 Proposition이며 새 결과의 실제 origin은 `k2k`/`is_inferred=true`다. Edge는 독립 실험·관측 수나 추가 추론 depth로 세지 않는다. transitive I/D는 실제 전달한 Node 전제를 통해 유지하고 새 직접 I grounding을 만들지 않는다.

Generator/Validator는 전체 Node IDs와 `delivered_effective_edge_refs`, `delivered_effective_input_sha256`을 실제 receipt에 결속한다. 독립적인 두 호출이 필요하고, 빈 discovery도 이를 우회하지 못한다. 코드가 결과 ID/FP와 정확한 Edge 참조를 결속한다. 동일 의미는 기존 K를 재사용하며 원래 origin과 과거 근거는 보존한다.

## 현재 상태와 전파

Global knowledge-state가 포함된 read-state token은 prepare→commit의 정확한 입력 증거로 저장한다. 영구 currentness를 새 global token과 비교하지 않으므로 결과의 자기 commit 때문에 스스로 stale이 되지 않는다. 장기 현재성은 semantic EdgeRevision, effective pair, 실제 최신 basis, pending fence, endpoint support로 검사한다. Node ancestry를 한 번 확장한 뒤 Edge의 로컬 상태를 검사하여 Node/Edge resolver 상호 재귀를 피한다.

필수 관계가 pending이면 consumer를 기다리게 한다. 최신 confirmed negative이면 기존 결론을 `needs_revalidation`으로 표시하고 유효하지 않은 Edge를 전제로 쓰지 않는다. 결론을 자동 삭제하거나 필수 Edge를 조용히 버려 다른 근거로 대체하지 않는다. 필요한 검토가 남으면 전파가 완료됐다고 표시하지 않는다.

관계가 true→true여도 새로운 exact basis를 소비하도록 현재 consumer의 유지보수 의무를 만든다. 이는 semantic material change와 구분하며 새 지식 discovery를 유발하지 않는다. endpoint 값 변경으로 이미 생긴 의무도 유지한다. 독립 검증 후 같은 결론이면 Node/Edge semantic Revision을 추가하지 않고 current-support Record만 갱신한다. 이전에 불가능했던 관계가 복구되면 보류된 의무를 다시 검사할 수 있다.

`supports`를 무조건 논리적 함의로 보거나, `contradicts`에서 임의의 결론·승자·평균값을 만들지 않는다. `qualifies`의 제한과 `composes`의 부분-전체 의미를 보존한다. 독립 inference validity·sufficiency·limits·novelty 검증을 그대로 적용한다. 일반적인 관계 순환에 대한 자동 중단이나 전파 깊이/비용 cap을 추가하지 않는다.

## 조회와 CLI

Graph/Desktop은 원래 도출의 exact Edge 근거와 현재 선택된 지원 경로의 Edge를 구분한다. 역사 origin의 근거가 오래되었어도 새 유효한 지원이 완전하면 같은 KRevision을 사용할 수 있다. 검색은 허용된 source 경로 전체를 검증하고, 선택되지 않은 역사 Edge qualifiers는 hash-only metadata로 처리한다. 새 mixed inference query는 실제 제공된 Edge 근거 목록을 context·citation·두 receipt에 결속한다. 질의 시점의 새 추론이나 Edge 자체의 embedding 검색은 추가하지 않는다.

```text
palim knowledge inference-input --data-id <SHA256> --edge-revision-id <E UUID>
palim knowledge inference-input --data-id <SHA256> --node-revision-id <K UUID> --edge-revision-id <E UUID>
palim knowledge prepare --operation k2k --data-id <SHA256> --request-id <UUID> --input <packet.json>
palim knowledge inference-call <execution UUID> --phase generator --directory <managed directory>
palim knowledge stage <execution UUID> --response <generator-response.json>
palim knowledge inference-call <execution UUID> --phase validator --directory <same directory>
palim knowledge decide <execution UUID> --response <validator-response.json>
```

기존 Node-only 입력도 그대로 사용할 수 있다. versioned Data는 기존 current/pinned Data version 결속을 적용한다. 새 worker run은 mixed K2K 정책을 동결하고, 기존 run은 원래 정책을 유지한다. 승인된 source 범위 밖의 근거가 필요하면 작업을 보류하며 자동으로 범위를 넓히지 않는다.

이 구현은 K2K 소비자이며 W/P의 Edge 소비, 일반 lifecycle, 대규모 paging, Realm 및 통합 Electron 구현 완료를 대신하지 않는다. Realm의 [기본 I2K 분리 정책](../decisions/REALM_SCOPE.md)은 별도 후속으로 적용한다. 기존 사용자 DB를 자동 마이그레이션하거나 원문을 다시 파싱하지 않는다.
