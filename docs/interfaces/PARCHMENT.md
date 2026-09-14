# W2P — Wisdom을 구성한 Wiki 문서

2026-09-14 사용자 정정: Wiki가 표시하는 문서는 Parchment P다. K는 별도 조회한다.
한 논문 또는 여러 자료의 accepted K를 질문/목적에 맞게 설명한 결과는 explanation W이고,
하나 이상의 W를 순서대로 구성한 독립 문서가 P다. 추천 W도 명확한 advisory 표시를 유지해
문서에 포함할 수 있다. W를 반드시 하나 이상 사용한다.

## 첫 구현

`ParchmentRuntime.compose(request_id, title=..., wisdom_ids=[...], actor=...)`는
동일 DB의 exact immutable W를 조회한다. `w2p-exact-wisdom-v1` script가 순서대로
W의 query, context, answer claims, recommendation, uncertainty와 citations를 복사한다.
모델 호출·새 Knowledge·새 원문 근거·새 판단 문구를 추가하지 않는다.
사용자가 지정한 title, actor와 실행 script의 SHA-256을 별도 provenance에 보존한다.

새 요청은 UUIDv7 P 하나를 만들며 제목/내용이 같아도 별도 문서다. 같은 성공 요청의
같은 payload 재시도만 기존 P를 반환한다. 같은 request ID의 다른 입력은 conflict다.
P는 immutable이고 ParchmentRevision을 만들지 않는다. 첫 구현은 create-only이며
문서 대체 연결·편집 CAS·Book은 후속 범위다.

## exact 연결

`parchment-v1`은 ordered `input_wisdom_ids`, section별 W ID/hash, claim별 W citations,
`supersedes_parchment_id=null`, `snapshot_sha256`을 보존한다. body의 sections는
W의 문구뿐 아니라 가정·한계·Context·미해결 부분까지 함께 유지한다.
직접 K/I를 사용하는 경로는 첫 구현에 없으므로 direct refs는 빈 배열이다.

Additive `0022_parchment`는 `canonical_store.parchments`와 ordered
`canonical_store.parchment_wisdoms`를 추가한다. P와 W의 typed FK, exact section/citation
대응과 원자적 link 완성을 DB에서 검사한다. 저장된 JSON bytes의 SHA도 검증한다.
W가 생성된 뒤 K 상태가 바뀌어도 그 역사적 W/P를 다시 쓰지 않는다. 현재 사실성을
별도로 평가해야 할 때 새로운 K2W 실행을 만들며 과거 P를 최신 사실로 자동 승격하지 않는다.

## CLI

```text
palim parchment compose --request-id UUIDv7 --title "주제 문서" --wisdom-id UUIDv7 --actor "사용자"
palim parchment show UUIDv7
palim parchment list
```

`--wisdom-id`를 반복하면 그 순서로 구성한다. CLI 결과는 기존 automation-safe JSON 경로를 사용한다.
`W2P`는 model Compiler Record subtype이 아닌 별도 deterministic application service다.

기존 Wiki 요약은 실제로 I에서 생성한 noncanonical projection이다. 이를 K2W가 만들었다고
바꾸거나 가짜 W/P ID를 붙이지 않는다. 실제 원문 refs/모델 receipt는 legacy 이력으로 보존하고,
새 W/P 경로의 결과와 구분한다. 실제 DB/패키지/UI 검증 결과는 실행 보고서에서 확인한다.

## Electron 읽기

UI0.7은 모든 trusted store의 `parchment_catalog`를 읽고 P를 기존 문서와 같은 Wiki 목록에 표시한다. `parchment_get`은 정확한 P와 W sections를 읽기만 한다. Wiki projection이 없는 저장소도 P 조회가 가능하다. 이전 schema6/10/13의 연결에는 빈 목록과 `supported=false`를 반환하며 자동 migration을 하지 않는다.

문서의 source/Realm 필터는 생성 당시 `w_inputs.payload`에 고정된 Data hash를 사용한다. 같은 K에 훗날 다른 출처의 지원이 추가돼도 과거 P의 분류 근거는 바뀌지 않는다. W별 설명·질문/조건·가정·한계·K/EffectiveEdge refs·W/P hash를 표시한다. 현재 K의 사실성을 재검증한 문서로 표시하지 않는다. 별도 Wiki가 없는 연결에서는 K 탐색을 꾸며내지 않고 exact Revision ID를 보여준다.
