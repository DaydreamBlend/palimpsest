# N2E의 관계 생성과 현재 적용성

2026-09-14 사용자 요청에 따른 `n2e-relations-v1`. 앱0.19와 추가0017–0019를 사용하는 새 실행의 계약이다. [실행 기록](../../progress/T20_n2e_completion_execplan.md)을 구현·검사 상태의 기준으로 삼는다. 이전 supports-only 프로필/실행/0001–0016은 변경하지 않는다. 이번 격리 DB에 설치한0017·0018도 수정하지 않고 후속 가드를 추가했다.

## 입력과 관계

N2E는 실제 accepted/current KNode Revision을 입력받아 KEdge를 생성하거나 재검토한다. 원문 내용 해석·새 Node 생성·D2I·D2K는 수행하지 않는다. source-created와 K2K-inferred Node의 실제 origin, exact premise/source-version 근거와 한계를 유지한다. 현재 저장 가능한 Node 종류는 Proposition(P), Observation(O)이다.

| Predicate | 방향 | 의미와 검사 |
|---|---|---|
| supports | P/O → P | 조건을 보존한 근거의 지지 |
| contradicts | P/O ↔ P/O | 같은 대상·scope·시점·조건에서 양립 불가능. logical UUID 순서와 연결된 Revision을 함께 정규화 |
| qualifies | P/O → P | 실제 조건·예외·적용 범위를 제한 |
| composes | P/O → P/O | 명시적인 전체 명제·합성의 진부분. 단순 근거·같은 자료·작은 수치만으로 생성하지 않음 |

현재 usable/applicable composes에만 DAG 제약을 적용한다. 과거·부정·보류 관계를 합친 그래프에 DAG를 적용하지 않는다. 다른 predicate의 순환은 금지하지 않는다. `supersedes`는 R06의 authority-confirmed W2K 소유권을 보존하며 N2E 모델 스키마에 제공하지 않는다. 아직 구현되지 않은 Decision 등 Node 종류를 임의로 추가하지 않는다.

## 구조화 검증과 저장

Generator는 후보 관계·qualifiers·간결한 근거만 제안한다. 코드가 UUIDv7·FP·identity·대응 Revision을 결정한다. 독립 Validator는 모든 후보의 exact comparison base, 관계 타당성, scope 호환성, material change를 판정한다. JSON 적합성은 의미 검증의 대체가 아니다.

같은 predicate/logical endpoint pair는 같은 logical Edge이다. supports의 과거 fingerprint bytes는 유지한다. 의미상 조건 변경은 `accepted_revision`과 `supersedes_revision_id`를 가지는 새 semantic Edge Revision을 만들고 CAS로 현재 pointer를 바꾼다. 단순 표현 변경·같은 의미는 accepted Revision을 재사용한다. endpoint만 새 Revision이 된 경우에는 semantic Edge Revision을 유지하고 exact pair의 새 applicability event를 저장한다.

predicate나 방향 identity가 바뀌면 새 logical Edge이다. 재검토의 `edge_review_target`은 기존 관계에 대한 true/false/unknown 평가를 별도 Record로 요구한다. 새 관계가 생겼다는 사실만으로 기존 관계를 부정하지 않는다. 후보를 생략했다고 false로 판단하지 않는다. 기존 관계 평가와 선택적인 새 관계의 결과·기록·outbox는 하나의 decide transaction으로 저장된다. 미해결 판정은 durable candidate/이유를 보존한다. composes cycle은 해당 현재 context의 보류이며 영구 FP blacklist가 아니다.

## 현재 적용성과 양방향 추적

재검토를 준비하면 exact semantic Edge Revision/current endpoint pair에 pending fence를 열고 knowledge-state를 갱신한다. 실패·unknown은 이전 positive로 돌아가지 않으며, 이후 같은 pair의 확인된 event가 fence를 해제한다. lease 갱신 시간은 의미 상태의 ordering token으로 사용하지 않는다.

현재 적용성은 현재 semantic Revision, current endpoint pair, 두 endpoint의 accepted/current support, 최신 exact-pair event, pending fence를 함께 검사한다. 같은 Node Revision이라도 사용된 transitive support signature가 달라지면 재검토가 필요하다. `pending`, `endpoint_unusable`, `historical`은 false와 구분한다.

과거 supports-only 실행의 bytes와 판정 이력은 그대로 보존한다. 다만 새 schema에서 오래된 추론 K endpoint의 support signature를 당시 N2E 입력으로 확인할 수 없다면, 원래 endpoint pair여도 현재 적용성을 `pending`으로 표시할 수 있다. 이는 과거 positive를 현재 근거에 자동 승계하지 않는 보수적 정책이다. 새 N2E 재검토가 확인되면 별도의 applicability event로 현재 사용 가능성을 확정하며, 기존 Edge Revision이나 원래 endpoint를 수정하지 않는다. 0016 이하 DB를 읽을 때의 legacy 조회 경로와 구분한다.

읽기 projection은 original endpoints를 보존하며 `effective_from_revision_id`, `effective_to_revision_id`, 현재 상태, 마지막 판정 근거를 별도 필드로 제공한다. usable 관계의 `effective_edge_ref`는 semantic Revision, effective endpoint pair, applicability basis type/ref와 relation read-state token을 묶는다. projection key는 유효 상태·근거·pending 변화를 반영한다. Node revision의 immutable 의미·origin은 갱신하지 않는다.

확인된 현재 usable contradicts가 있으면 양쪽 endpoint의 `epistemic_projection=contested`를 계산한다. 이는 lifecycle 변경·거짓 판정·자동 승자 선택이 아니다. 다른 predicate나 false/pending 관계는 이 표시를 만들지 않는다. source 제한 읽기에도 전역적으로 알려진 contested 표시를 유지하되 상대 문서의 ID/내용을 Node annotation에 넣지 않는다. 검색에서 disputed K를 삭제하거나 embedding 문구를 상대 주장으로 오염시키지 않는다.

## CLI와 실행

아래 명령은 구성된 DB/Artifact Store에서 실행한다. `prepare`/`edge-call`은 모델 전송이 아니다. 기존 `tools/run_knowledge_model.py`가 정확히 저장된 요청을 전송하고 `stage`/`decide`가 실제 receipt·독립 호출을 검사한다.

```text
palim knowledge edge-input --data-id <SHA256> --node-revision-id <UUID> --node-revision-id <UUID>
palim knowledge prepare --operation n2e --data-id <SHA256> --request-id <UUID> --input <packet.json>
palim knowledge edge-call <execution UUID> --phase generator --directory <managed directory>
palim knowledge stage <execution UUID> --response <generator-response.json>
palim knowledge edge-call <execution UUID> --phase validator --directory <same managed directory>
palim knowledge decide <execution UUID> --response <validator-response.json>
palim knowledge edge-revalidate --edge-revision-id <UUID> --request-id <UUID>
palim knowledge graph --data-id <SHA256>
palim knowledge show <execution UUID>
```

versioned Data에는 기존 `--data-version-id`/current 또는 명시적 pinned mode가 적용된다. 자동 전파 worker도 같은 N2E prepare/request/stage/decide를 사용한다. material semantic relation/적용성 변화는 outbox로 후속 전파를 만들고, nonmaterial 결과는 새 의미 branch를 만들지 않는다. 근거 재검증 의무·실패·보류는 성공 종료로 처리하지 않는다. T19의 반복 advisory 정책은 유지된다.

현재 K2K는 Node를 전제로 사용한다. Edge를 직접 전제로 사용하는 K2K/W/P, Edge embedding 검색, 일반 lifecycle/suppression, authority-confirmed W2K `supersedes`는 별도 후속 범위다. 이 문서의 EffectiveEdgeRef 생산·읽기 검사를 해당 소비자 전체의 AT09–17 완료로 확대하지 않는다. Wiki 본문은 I 기반 기존 페이지 compiler를 유지하며 현재 관계 표시는 읽기 projection으로 제공한다.

Optional relation discovery may use BGE-M3 dense similarity to retrieve nearby Node pairs. The frozen embedding profile/result hashes, exact Revision pairs and scores bind the request. Similarity is candidate selection rather than relation evidence; Generator and independent Validator still decide the predicate and validity. Mandatory relation revalidation and applicability maintenance are never truncated by this candidate window.
