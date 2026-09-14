## 27. 핵심 불변조건

1. D payload는 수정하지 않는다.
2. 동일 D bytes의 여러 수집 경로는 DataAcquisition으로 append-only 보존하며 별도 Source 계층을 만들지 않는다.
3. D2I의 exactly-once 단위는 D 전체 수명이 아니라 `data_id + extraction_profile_family + compilation_generation` logical compilation이다.
4. 평범한 retry는 같은 compilation generation을 재사용하고, 명시적 recompile/repair만 새 generation을 시작한다.
5. D2I proposal 한 건마다 D2IRecord 하나를 만들고 호출 묶음은 `batch_id`로 표현한다.
6. canonical I는 validated immutable Information뿐이며 `InformationRevision`을 두지 않는다.
7. Information identity는 exact originating Data와 grounding에 종속된다. 서로 다른 D의 동일 semantic content를 하나의 Information으로 병합하지 않는다.
8. Information grounding은 extractor/parser profile/version과 stable anchor를 보존해 locator 재현성을 확보한다.
9. Information 교정은 새 I와 append-only supersession/invalidation 관계로 표현한다.
10. Information supersession graph는 DAG이며 self-edge/cycle을 허용하지 않는다.
11. superseded/invalidated I는 삭제하지 않고 기본 RAG와 새 I2K 입력에서 제외한다.
12. 새 I가 기존 I를 supersede하면 기존 I를 직접 사용한 K를 재검증 대상으로 등록한다.
13. I supersession은 기존 K를 자동 수정하지 않으며 과거 K provenance는 exact old information_id를 유지한다.
14. 직접 K에서 material graph delta가 발생한 경우에만 간접 downstream K를 재검증하며, non-material/no-material 결과에서는 해당 propagation branch를 종료한다.
15. I2K/K2K는 허용된 KNode kind만 제안하며 K2K는 새 observation 또는 authority-confirmed decision을 만들 수 없다.
16. N2E는 KEdge semantic relation과 명시적 edge revalidation/lifecycle effect만 다룬다.
17. I/K 후보는 terminal acceptance 전까지 Bibliotheca canonical 객체가 아니다.
18. accepted/rejected/suppressed FP는 해당 D2IRecord 또는 KCompilationRecord에 남는다.
19. terminal Candidate semantic payload는 accepted canonical 객체로 이동하거나 삭제한다. 선택적 audit 보존은 비canonical bounded-retention이다.
20. exact accepted semantic duplicate는 새 K semantic Revision을 만들지 않는다. 다만 새 독립 evidence는 grounding_added effect를 가질 수 있다.
21. disposition과 canonical effect는 분리한다. `reused`는 `grounding_added` 같은 side effect와 공존할 수 있다.
22. style-only 또는 paraphrase-only 변화는 K Revision을 만들지 않는다.
23. KNode/KEdge Revision과 과거 endpoint는 수정·삭제하지 않는다.
24. K current revision 변경은 expected base revision을 검사하는 atomic concurrency guard를 사용한다.
25. K lifecycle과 epistemic/decision status는 immutable semantic payload와 분리된 append-only event/projection이다.
26. 반박은 먼저 semantic KEdge로 표현하며 자동으로 상대 Node를 수정하지 않는다.
27. KNode Revision이 바뀌면 과거 incident edge는 historical provenance를 유지하고 새 current endpoint pair에 대해 applicability를 재검증한다.
28. endpoint만 바뀌고 relation semantic이 materially 동일하면 새 KEdgeRevision을 만들지 않고 KEdgeApplicabilityEvent(applicable)만 append하며 그 branch를 종료한다.
29. 기존 edge의 current applicability 상실은 “새 edge가 제안되지 않음”만으로 추론하지 않고 KEdgeApplicabilityEvent(not_applicable) 같은 명시적 revalidation decision을 요구한다. 이 material graph delta는 dependent downstream K 재검증을 유발한다.
30. 모든 propagation과 K revalidation은 causal root, propagation depth metadata, exact-input/context fingerprint와 visited guard를 가지며, size/depth/Record/token/cost hard cap을 정상 semantic completion 조건으로 사용하지 않는다.
31. K2K-derived K는 causal root와 독립적인 derivation_depth/evidence distance를 누적해 provenance와 uncertainty에 사용한다.
32. derivation_depth 값 자체는 K2K result의 자동 rejection 또는 propagation cutoff가 아니다. propagation은 material-delta frontier가 사라진 fixed point에서 종료한다.
33. Query와 Context/Memory는 KQ2W의 임시 overlay이지 canonical K가 아니다.
34. KQ2W가 direct Information을 사용하면 Wisdom에 retrieval_mode와 epistemic_basis를 남겨 accepted K와 구분한다.
35. Recommendation은 LLM의 제안이며 자동 W2K하지 않는다.
36. Decision W는 권한 있는 actor의 authority-confirmed event이며 deterministic W2K에 필요한 subject/scope/constraints/effective_at을 자체 보존한다.
37. 외부 Data가 보고한 decision event는 I2K의 `origin_type=reported` decision KNode로 표현하며 authority-confirmed W2K decision과 구분한다.
38. Decision W와 authority-confirmed decision KNode/W2KRecord는 원자적으로 일치해야 한다.
39. Decision event identity는 origin_wisdom_id에 고정되며 서로 다른 Wisdom은 semantic content가 같아도 같은 decision KNode로 병합하지 않는다.
40. Decision의 active/superseded/expired 상태는 semantic payload가 아니라 current projection이다.
41. Decision supersession graph는 DAG이며 실제 재결정은 새 decision event로 남긴다.
42. 과거 결정 이유는 Decision trace를 사용하는 Explanation W로 생성한다.
43. embedding과 retrieval hit는 canonical truth가 아니다.
44. global hard-rejection suppression은 invariant-hard reason에만 사용하고 contextual/policy rejection은 context fingerprint 범위에서만 억제한다.
45. 모든 파생 결과는 exact input Information/K revision, origin Record, 필요한 lifecycle/effect까지 추적할 수 있어야 한다.

---

## 28. 승인된 Architecture Decision A1–A40

| ID | 승인된 결정 |
|---|---|
| `A1` | Source를 별도 계층으로 두지 않고 D를 불변 원본으로 사용한다. |
| `A2` | D2IRecord는 Information proposal 한 건당 하나이며 D2IOutput을 두지 않고 batch_id로 호출 묶음을 표현한다. |
| `A3` | D2IRecord/I2KRecord/N2ERecord/K2KRecord/W2KRecord는 제안 한 건당 하나이며 batch_id로 호출 묶음을 표현한다. |
| `A4` | PostgreSQL에서는 공통 KCompilationRecord table과 typed record view/type을 사용한다. |
| `A5` | 승인·기각 FP와 결과를 해당 D2IRecord/KCompilationRecord에 보존하고 별도 rejection domain 객체를 두지 않는다. |
| `A6` | Generator와 Validator를 하나의 Operation pipeline에 두고 별도 KReviewRun을 두지 않는다. |
| `A7` | KNodeRevision은 material semantic delta에만 생성한다. |
| `A8` | 반박은 먼저 contradicts KEdge로 표현하고 기존 KNodeRevision을 자동 수정하지 않는다. |
| `A9` | 같은 identity의 실질적 수정만 기존 KNode의 새 Revision으로 승인한다. |
| `A10` | root/parent/depth로 causality를 추적하고 fingerprint/visited guard로 동일 상태의 중복 계산을 막되, propagation은 hard size/depth/cost cap이 아니라 material-delta fixed point에서 종료한다. |
| `A11` | Query와 Memory는 임시 QueryContextGraph이며 canonical K에 직접 넣지 않는다. |
| `A12` | 확정된 Decision W만 W2K를 통해 decision KNode로 승격한다. |
| `A13` | 별도 canonical 장기 Memory 계층을 두지 않고 decision KNode와 immutable Wisdom이 장기 기억을 담당한다. |
| `A14` | Decision W 저장 시 W2K를 결정론적으로 자동 실행하여 decision KNode와 W2KRecord를 같은 transaction에서 생성한다. |
| `A15` | Wisdom kind는 explanation, recommendation, decision 세 종류다. |
| `A16` | Decision action은 select, defer, decline이다. |
| `A17` | decision_replay Wisdom kind를 제거한다. |
| `A18` | 과거 결정 설명은 query_intent=explain_decision, retrieval_mode=decision_trace를 사용하는 Explanation W다. |
| `A19` | Information은 그 자체가 immutable semantic snapshot이며 InformationRevision을 두지 않는다. |
| `A20` | Information 오류 교정·재추출은 기존 I를 수정하지 않고 새 Information을 만든다. |
| `A21` | Information 교체와 무효화는 append-only InformationSupersession/InformationInvalidation으로 기록한다. |
| `A22` | I2K와 K provenance는 exact information_id를 참조하며 supersession 뒤에도 과거 참조를 자동 치환하지 않는다. |
| `A23` | embedding·검색 index·reranker·표시 projection 변화는 새 Information을 만들지 않는다. |
| `A24` | 동일 logical D2I compilation generation은 exactly-once canonical effect를 가지며, 오류 교정·재추출은 새 compilation_generation의 명시적 recompile/repair로 수행한다. |
| `A25` | 새 I가 기존 I를 supersede하면 직접 연관 K를 재검증하고, 실제 material graph delta만 downstream convergent propagation을 이어간다. |
| `A26` | Information은 originating Data/grounding-specific evidence object이며 cross-Data semantic dedup을 하지 않는다. |
| `A27` | 동일 semantic K에 새 독립 근거가 추가되면 Revision 대신 grounding effect를 append하며 disposition과 effect를 분리한다. |
| `A28` | D2I exactly-once 단위는 logical compilation generation이며 explicit recompile/repair를 정상 경로로 모델링한다. |
| `A29` | Source layer 없이 append-only DataAcquisition으로 수집 provenance를 보존한다. |
| `A30` | K lifecycle/epistemic 상태는 append-only event와 projection으로 관리하며 semantic payload에 넣지 않는다. |
| `A31` | KNode current revision commit은 expected-base CAS를 사용한다. |
| `A32` | KNode revision 변화 후 incident KEdge는 새 current endpoint pair에 대해 N2E revalidation하며, relation semantic이 그대로면 KEdgeRevision을 만들지 않고 applicability event로 재확인한다. |
| `A33` | N2E는 discovery와 explicit edge revalidation mode를 가지며, material edge/applicability 변화만 downstream propagation을 만든다. |
| `A34` | K2K derivation depth는 propagation root와 독립적으로 누적해 epistemic distance를 추적하지만 hard depth budget이나 자동 cutoff로 사용하지 않는다. |
| `A35` | Operation×KNode-kind compatibility를 deterministic invariant로 둔다. |
| `A36` | decision KNode는 `reported`와 `authority_confirmed` origin type을 구분한다. |
| `A37` | Decision W는 deterministic W2K에 필요한 subject/scope/constraints/effective_at을 직접 보존한다. |
| `A38` | 서로 다른 Decision Wisdom은 semantic content가 같아도 별도 event이며 W2K content-based reuse를 금지한다. |
| `A39` | rejection suppression은 invariant-hard와 contextual/policy/temporary scope를 구분한다. |
| `A40` | KQ2W의 direct-I 사용은 retrieval_mode/epistemic_basis로 명시한다. |

---

