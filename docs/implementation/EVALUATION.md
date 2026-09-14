# 평가와 release gate

## 서로 다른 다섯 가지 검증

**문서 검증**은 이 패키지의 hash/partition/링크/task/test ID/Markdown 구조 검사입니다. 앱 구현의 정확성을 의미하지 않습니다.

**결정론적 domain tests**는 immutable 객체, identity registry, materiality 필드, event state, confirmation mapping의 실행 규칙을 테스트합니다. 실제 자연어 이해 능력을 증명하지 않습니다.

**PostgreSQL/runtime integration**은 CAS/read-set freshness, atomic commit, outbox duplicate, lease/restart, replacement barrier, completion fence를 실제 저장소와 worker로 시험합니다. mock-only로 통과 처리하지 않습니다.

**End-to-end**는 import→I→K→query→decision→publication과 repair/revalidation/partial 상태를 실제 application surface로 연결합니다. mock provider인지 live provider인지 보고합니다.

**Semantic evaluation**은 독립적으로 label한 gold set에서 source fidelity, materiality false-negative/false-positive, relation applicability, contradiction scope, identity merge/split, citation fidelity와 authority 오류를 측정합니다.

## Gold set 구성

긍정/부정, 조건별 상충, 실제 모순이 아닌 scope 차이, 같은 의미의 표현 변경, cumulative numeric drift, 표/본문 차이, shared-study sources, internal publication reimport, reported/local decision, pending evidence, stale retrieval를 포함합니다. 학습/튜닝용과 최종 평가용을 구분합니다. 고정된 숫자 threshold는 사용자 승인 없이 넣지 않습니다.

## 평가 기록

dataset/version/labeler 근거, model/provider/prompt/schema/retrieval profiles, 정확한 inputs, outcomes, 오류 사례, token/cost telemetry와 external transmission 범위를 남깁니다. 서로 다른 파이프라인 실패를 하나의 accuracy 숫자에 숨기지 않습니다.

materiality에서 false negative는 필요한 propagation을 막고 false positive는 불필요한 revision/비용을 만듭니다. 두 방향을 따로 보고합니다. accepted/rejected 정도만 비교하지 말고 exact references와 resulting graph state도 검증합니다.

## Release 조건

원본 45 invariant에 최소 한 실행 assertion이 연결되고, 승인된 P 항목의 필수 AT tests가 구현되어야 합니다. 실행 불가·미구현·보류 테스트는 이름과 이유를 보고합니다. backup/restore를 실제로 해보지 않은 상태는 별도 미완료입니다. live evaluation 미실행 시 “실제 모델의 의미 정확성 확인 전”이라는 한계를 남깁니다.


## CLI / MinerU release coverage

T12는 GUI 없는 환경에서 CLI complete workflow를 검증한다. clean JSON stdout/stderr, non-TTY confirmation, partial/blocked job status, pause/resume, UTF-8/path safety를 포함한다. 실제 MinerU parser로 native/scanned/mixed PDF와 표/수식을 파싱해 원문 page/region에 대조한다. 선택한 version/backend/model/output schema를 결과와 함께 남긴다.

synthetic normalized fixtures는 Palimpsest adapter contract 검사에만 사용한다. upstream MinerU 호환성·OCR 품질·표/수식 정확성을 통과한 실제 테스트로 세지 않는다. 모델 download/외부 전송은 승인된 범위만 수행한다. GUI 시험은 T13 이후 별도이며 CLI release 선행 조건이 아니다.
