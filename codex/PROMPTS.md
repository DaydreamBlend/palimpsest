# 복사해서 사용할 개발 지시문 — CLI / MinerU 현재판

## 기존 작업 중인 저장소에 이번 변경만 적용

```text
AGENTS.md와 docs/decisions/USER_OVERRIDES.md를 먼저 읽고 현재 ExecPlan을 조정해 주세요.
GUI는 마지막 T13로 미루고 T02부터 CLI 기능을 구현합니다. T11도 CLI review/운영 완성 단계입니다.
PDF D2I 파서는 MinerU로 고정합니다. parser 결과를 바로 I로 승인하지 말고 grounding/validation을 거치세요.
구성요소는 Artifact Store(artifact_store), Canonical Store(canonical_store),
Compiler Runtime(compiler_runtime)이며 원본 경로 필드는 artifact_path입니다.

기존 코드/DB/원문/IDs/hashes를 무작정 rename하거나 재작성하지 마세요.
기존 GUI는 삭제하지 말고 동결하고 같은 application service를 CLI에서 재사용하세요.
U01–U03은 적용된 요청이며 다시 제품/우선순위 승인을 묻지 마세요.
P01–P12의 다른 미승인 설계는 여전히 승인 전입니다.
변경된 plan/task 범위와 필요한 migration/실행 권한, 실제 검사 결과를 보고해 주세요.
```

## 새로 시작할 때 — T00만

```text
AGENTS.md, docs/decisions/USER_OVERRIDES.md, docs/INDEX.md,
docs/decisions/DECISION_REGISTER.md, tasks/T00.md를 읽고 T00만 수행해 주세요.

CLI 우선·GUI 마지막, PDF parser=MinerU, 새 영어 구성요소명은 확정입니다.
실제 repo의 코드/schema/tests/CLI entrypoint/GUI 결합을 조사하세요.
MinerU 설치 여부, version/help, OS/architecture/GPU/runtime/model readiness와
local/remote parser 설정을 secret 노출 없이 확인하세요.
자동 설치·모델 다운로드·PDF 외부 전송·DB rename은 하지 마세요.

progress/repository_inventory.md와 progress/STATUS.md를 실제 근거로 갱신하세요.
P01–P12는 이번 세 변경으로 일괄 승인되지 않았습니다.
production code/schema/의존성을 바꾸지 말고 필요한 다음 선택과 검사 결과만 보고하세요.
```

## 계약 확인 — T01

```text
tasks/T01.md와 docs/decisions/USER_OVERRIDES.md를 읽고 미정 계약을 구체화하세요.
U01–U03을 다시 미정으로 돌리지 말고, P01–P12의 실제 선택/승인을 분리하세요.
CLI contract, MinerU 버전/backend/output normalization과 환경 profile을 확인하고
명시적으로 승인된 세부사항만 register에 반영하세요.
GUI framework를 선택하지 말고 propagation hard cap을 복원하지 마세요.
archived source는 보존하며 current canonical과 split map을 독립적으로 어긋나게 수정하지 마세요.
```

## 승인 후 한 task 구현

아래 T02를 실제 지정할 task로 바꾼다. command 예시는 아직 앱에서 실행된 결과가 아니다.

```text
AGENTS.md와 tasks/T02.md를 읽고 해당 task 범위만 구현하세요.
required_user_overrides와 required_decisions를 확인하고 실제 코드를 읽으세요.
PLANS.md에 따라 task-local ExecPlan을 작성하고 feature와 CLI를 함께 연결하세요.
GUI는 만들지 말고 PDF 경로는 MinerU adapter를 사용하세요.
parse artifact/Information validation을 분리하고 silent parser fallback을 금지하세요.

관련 AT tests를 구현·실행하고 문서 검사/mock/실제 MinerU/DB/e2e 결과를 구분해 보고하세요.
테스트하지 않은 것을 pass로 기록하지 마세요. codex/CODE_REVIEW.md로 diff를 검토하고
progress를 갱신한 뒤 이 task에서 멈추세요. T13을 자동 시작하지 마세요.
```

## 독립 review

```text
이번 diff를 codex/CODE_REVIEW.md, U01–U03, task/AT 기준으로 검토하세요.
CLI-first, MinerU PDF, 새 이름이 current code/spec에 일관되는지 확인하세요.
archive의 옛 이름을 현재 요구로 오인하지 말고 P 제안을 셀프 승인하지 마세요.
GUI 조기 착수, 원문/provenance 변조, parser 성공=I 승인, remote 전송,
없는 CLI command나 미실행 test의 완료 주장을 먼저 찾으세요.
코드를 즉시 수정하지 말고 재현 가능한 반례/경로/영향/최소 수정안을 보고하세요.
```

## 세션 재개

```text
AGENTS.md, docs/decisions/USER_OVERRIDES.md, progress/STATUS.md,
현재 task의 ExecPlan을 읽고 실제 git diff와 tests를 확인하세요.
CLI/MinerU/current naming을 유지하고 미완료 obligation/미승인 P 결정을 지우지 마세요.
현재 task의 다음 작은 구현·검증만 수행하고 결과를 보고하세요.
```
