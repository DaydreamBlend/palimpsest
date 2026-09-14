# 45개 원본 invariant → acceptance 시나리오

> 연결이 존재한다는 뜻이며 테스트 구현/통과를 뜻하지 않습니다. 번호와 문구는 원본 §27을 그대로 따릅니다.
> 현재 명칭은 [U07](../../docs/decisions/USER_OVERRIDES.md)에 따라 K2W다. 아래 I33/I34의 KQ2W 표기는 원본 인용으로 보존하며 현재 구현에는 K2W를 적용한다.

## I01 · 원본 L2179

D payload는 수정하지 않는다.

검증 ID: AT67.

## I02 · 원본 L2180

동일 D bytes의 여러 수집 경로는 DataAcquisition으로 append-only 보존하며 별도 Source 계층을 만들지 않는다.

검증 ID: AT70.

## I03 · 원본 L2181

D2I의 exactly-once 단위는 D 전체 수명이 아니라 `data_id + extraction_profile_family + compilation_generation` logical compilation이다.

검증 ID: AT36.

## I04 · 원본 L2182

평범한 retry는 같은 compilation generation을 재사용하고, 명시적 recompile/repair만 새 generation을 시작한다.

검증 ID: AT36.

## I05 · 원본 L2183

D2I proposal 한 건마다 D2IRecord 하나를 만들고 호출 묶음은 `batch_id`로 표현한다.

검증 ID: AT33.

## I06 · 원본 L2184

canonical I는 validated immutable Information뿐이며 `InformationRevision`을 두지 않는다.

검증 ID: AT68, AT69.

## I07 · 원본 L2185

Information identity는 exact originating Data와 grounding에 종속된다. 서로 다른 D의 동일 semantic content를 하나의 Information으로 병합하지 않는다.

검증 ID: AT22, AT23.

## I08 · 원본 L2186

Information grounding은 extractor/parser profile/version과 stable anchor를 보존해 locator 재현성을 확보한다.

검증 ID: AT25, AT56.

## I09 · 원본 L2187

Information 교정은 새 I와 append-only supersession/invalidation 관계로 표현한다.

검증 ID: AT69.

## I10 · 원본 L2188

Information supersession graph는 DAG이며 self-edge/cycle을 허용하지 않는다.

검증 ID: AT40.

## I11 · 원본 L2189

superseded/invalidated I는 삭제하지 않고 기본 RAG와 새 I2K 입력에서 제외한다.

검증 ID: AT71.

## I12 · 원본 L2190

새 I가 기존 I를 supersede하면 기존 I를 직접 사용한 K를 재검증 대상으로 등록한다.

검증 ID: AT18, AT19.

## I13 · 원본 L2191

I supersession은 기존 K를 자동 수정하지 않으며 과거 K provenance는 exact old information_id를 유지한다.

검증 ID: AT18, AT71.

## I14 · 원본 L2192

직접 K에서 material graph delta가 발생한 경우에만 간접 downstream K를 재검증하며, non-material/no-material 결과에서는 해당 propagation branch를 종료한다.

검증 ID: AT02, AT12.

## I15 · 원본 L2193

I2K/K2K는 허용된 KNode kind만 제안하며 K2K는 새 observation 또는 authority-confirmed decision을 만들 수 없다.

검증 ID: AT74.

## I16 · 원본 L2194

N2E는 KEdge semantic relation과 명시적 edge revalidation/lifecycle effect만 다룬다.

검증 ID: AT37, AT39, AT74.

## I17 · 원본 L2195

I/K 후보는 terminal acceptance 전까지 Bibliotheca canonical 객체가 아니다.

검증 ID: AT68.

## I18 · 원본 L2196

accepted/rejected/suppressed FP는 해당 D2IRecord 또는 KCompilationRecord에 남는다.

검증 ID: AT77.

## I19 · 원본 L2197

terminal Candidate semantic payload는 accepted canonical 객체로 이동하거나 삭제한다. 선택적 audit 보존은 비canonical bounded-retention이다.

검증 ID: AT68, AT55.

## I20 · 원본 L2198

exact accepted semantic duplicate는 새 K semantic Revision을 만들지 않는다. 다만 새 독립 evidence는 grounding_added effect를 가질 수 있다.

검증 ID: AT08, AT73.

## I21 · 원본 L2199

disposition과 canonical effect는 분리한다. `reused`는 `grounding_added` 같은 side effect와 공존할 수 있다.

검증 ID: AT20, AT38, AT73.

## I22 · 원본 L2200

style-only 또는 paraphrase-only 변화는 K Revision을 만들지 않는다.

검증 ID: AT08.

## I23 · 원본 L2201

KNode/KEdge Revision과 과거 endpoint는 수정·삭제하지 않는다.

검증 ID: AT11, AT54.

## I24 · 원본 L2202

K current revision 변경은 expected base revision을 검사하는 atomic concurrency guard를 사용한다.

검증 ID: AT28, AT29.

## I25 · 원본 L2203

K lifecycle과 epistemic/decision status는 immutable semantic payload와 분리된 append-only event/projection이다.

검증 ID: AT21, AT50, AT54.

## I26 · 원본 L2204

반박은 먼저 semantic KEdge로 표현하며 자동으로 상대 Node를 수정하지 않는다.

검증 ID: AT75.

## I27 · 원본 L2205

KNode Revision이 바뀌면 과거 incident edge는 historical provenance를 유지하고 새 current endpoint pair에 대해 applicability를 재검증한다.

검증 ID: AT09, AT16.

## I28 · 원본 L2206

endpoint만 바뀌고 relation semantic이 materially 동일하면 새 KEdgeRevision을 만들지 않고 KEdgeApplicabilityEvent(applicable)만 append하며 그 branch를 종료한다.

검증 ID: AT10, AT13, AT38.

## I29 · 원본 L2207

기존 edge의 current applicability 상실은 “새 edge가 제안되지 않음”만으로 추론하지 않고 KEdgeApplicabilityEvent(not_applicable) 같은 명시적 revalidation decision을 요구한다. 이 material graph delta는 dependent downstream K 재검증을 유발한다.

검증 ID: AT17, AT37.

## I30 · 원본 L2208

모든 propagation과 K revalidation은 causal root, propagation depth metadata, exact-input/context fingerprint와 visited guard를 가지며, size/depth/Record/token/cost hard cap을 정상 semantic completion 조건으로 사용하지 않는다.

검증 ID: AT01, AT03, AT04, AT60.

## I31 · 원본 L2209

K2K-derived K는 causal root와 독립적인 derivation_depth/evidence distance를 누적해 provenance와 uncertainty에 사용한다.

검증 ID: AT44, AT79.

## I32 · 원본 L2210

derivation_depth 값 자체는 K2K result의 자동 rejection 또는 propagation cutoff가 아니다. propagation은 material-delta frontier가 사라진 fixed point에서 종료한다.

검증 ID: AT01, AT04, AT79.

## I33 · 원본 L2211

Query와 Context/Memory는 KQ2W의 임시 overlay이지 canonical K가 아니다.

검증 ID: AT80.

## I34 · 원본 L2212

KQ2W가 direct Information을 사용하면 Wisdom에 retrieval_mode와 epistemic_basis를 남겨 accepted K와 구분한다.

검증 ID: AT51, AT81.

## I35 · 원본 L2213

Recommendation은 LLM의 제안이며 자동 W2K하지 않는다.

검증 ID: AT78.

## I36 · 원본 L2214

Decision W는 권한 있는 actor의 authority-confirmed event이며 deterministic W2K에 필요한 subject/scope/constraints/effective_at을 자체 보존한다.

검증 ID: AT45, AT47, AT66.

## I37 · 원본 L2215

외부 Data가 보고한 decision event는 I2K의 `origin_type=reported` decision KNode로 표현하며 authority-confirmed W2K decision과 구분한다.

검증 ID: AT52, AT74.

## I38 · 원본 L2216

Decision W와 authority-confirmed decision KNode/W2KRecord는 원자적으로 일치해야 한다.

검증 ID: AT30, AT66.

## I39 · 원본 L2217

Decision event identity는 origin_wisdom_id에 고정되며 서로 다른 Wisdom은 semantic content가 같아도 같은 decision KNode로 병합하지 않는다.

검증 ID: AT45, AT46.

## I40 · 원본 L2218

Decision의 active/superseded/expired 상태는 semantic payload가 아니라 current projection이다.

검증 ID: AT49, AT50.

## I41 · 원본 L2219

Decision supersession graph는 DAG이며 실제 재결정은 새 decision event로 남긴다.

검증 ID: AT40, AT46, AT49.

## I42 · 원본 L2220

과거 결정 이유는 Decision trace를 사용하는 Explanation W로 생성한다.

검증 ID: AT52, AT54.

## I43 · 원본 L2221

embedding과 retrieval hit는 canonical truth가 아니다.

검증 ID: AT53, AT76.

## I44 · 원본 L2222

global hard-rejection suppression은 invariant-hard reason에만 사용하고 contextual/policy rejection은 context fingerprint 범위에서만 억제한다.

검증 ID: AT25, AT26, AT27.

## I45 · 원본 L2223

모든 파생 결과는 exact input Information/K revision, origin Record, 필요한 lifecycle/effect까지 추적할 수 있어야 한다.

검증 ID: AT09, AT18, AT54, AT77.


## CLI/MinerU/이름 변경의 별도 추적

위 45개 invariant와 문구는 수정 전 archived source의 원문 추적이다. 현재 명칭은 U03을 적용한다. U01–U03은 `user_override_dependencies`를 통해 AT82–AT105와 연결하며 [user overrides](../../docs/decisions/USER_OVERRIDES.md)에 근거가 있다. 원본 invariant 인용문을 새 이름으로 고쳐 과거 원문처럼 표시하지 않는다.

현재 U08 수정은 [구조 해결 계약](../../docs/decisions/ARCHITECTURE_FIXES.md)을 따른다. 위 원본 invariant 인용/번호는 보존하며 특히 completion, no-material maintenance, retrieval_mode의 현재 해석은 승인된 해결 계약과 함께 읽는다.

U09 적용: Data ID·일반 중복 등록과 명시적 acquisition 기록, 도구 등록·Runtime Record 보존은 STORAGE_IDENTITY와 현재 AT56/67/68/70/107 및 AT108–112를 따른다. 원본 invariant 인용과 JSON은 역사 근거로 보존한다.
