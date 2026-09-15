# 문서 인덱스

현재 구현·검증·남은 작업은 **[progress/STATUS.md](../progress/STATUS.md)**에서 확인한다. 아래는 작업별 탐색 경로다. 전체 링크를 순서대로 읽지 말고 현재 변경에 해당하는 행의 계약부터 선택한다. 과거 문서의 당시 상태를 현재 상태로 가져오지 않는다.

## 기능별 계약

| 작업 | 먼저 확인할 계약 |
|---|---|
| 원문 등록·D2I·Data version | [원문 보존](decisions/D2I_SOURCE_PRESERVATION.md), [MinerU](interfaces/MINERU_ADAPTER.md), [Data versions](interfaces/DATA_VERSIONS.md), [Python D2I](interfaces/CODE_REVIEW_WIKI.md) |
| Realm 등록·입력·자동 범위 | [등록 coordinator](interfaces/REALM_REGISTRATION.md), [I2K 범위](interfaces/REALM_I2K.md), [자동 전파 범위](interfaces/REALM_AUTOMATION.md) |
| I2K·source 검토·정보 오류 | [source-only I2K](decisions/I2K_SOURCE_ONLY_K2K_INFERENCE.md), [전체 source 검토](interfaces/SOURCE_REVIEW.md), [Information 오류](interfaces/INFORMATION_ERRORS.md), [명시 요청 D2K](interfaces/D2K.md) |
| K 관계·추론 | [N2E typed relations](interfaces/N2E_RELATIONS.md), [EffectiveEdge K2K](interfaces/EFFECTIVE_K2K.md) |
| 전파·materiality·재개 | [worker](interfaces/PROPAGATION_WORKER.md), [의미 변화 우선 정책](decisions/MATERIALITY_FIRST_PROPAGATION.md) |
| 설명/추천 W·P·Wiki | [W/P 구분](decisions/WIKI_WISDOM_PARCHMENT.md), [K2W](interfaces/K2W.md), [W2P/Parchment](interfaces/PARCHMENT.md) |
| Electron·store·Realm UI | [통합 Desktop](interfaces/UNIFIED_DESKTOP.md), [Realm IPC](interfaces/REALM_DESKTOP.md), [직접 소속 지정](interfaces/UI_REALM_ASSIGNMENT.md) |
| 기존 Wiki projection·검색·답변 | [legacy I 기반 Wiki](interfaces/PAPER_WIKI_PROJECTION.md), [Wiki DB](interfaces/WIKI_DATABASE.md), [query](interfaces/WIKI_QUERY.md) |
| CLI·공유 Runtime 구조 | [CLI](interfaces/CLI_CONTRACT.md), [모듈 경계](implementation/MODULE_BOUNDARIES.md), [현재 모델 provider](implementation/MODEL_PROVIDER.md), [저장·identity](decisions/STORAGE_IDENTITY.md) |

구체적인 승인 변경은 해당 계약에서 연결한 `decisions/` 기록을 확인한다. [USER_OVERRIDES](decisions/USER_OVERRIDES.md)는 초기 선택과 후속 변경의 이력이며, 모든 과거 기본값을 동시에 적용하는 지침이 아니다. 다음 제품 연결 작업은 [현재 backlog](../progress/IMPLEMENTATION_BACKLOG_2026_09_14.md)에 있다.

## 설계 원본과 검증

- [통합 canonical](canonical/PALIMPSEST_CANONICAL_MODEL.md)과 [current_map.json](canonical/current_map.json)은 현재 설계 snapshot과 분할본의 대응을 관리한다. 특정 설계 범위가 필요할 때만 해당 slice를 읽는다. 기능의 실제 구현 여부는 STATUS와 실행 보고서로 확인한다.
- [보존 원본](source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md)과 [source_map.json](source/source_map.json)은 수정 전 증거다. 원본·baseline slices·[review](review/REVIEW.md)의 원문 인용은 당시 줄 번호를 사용한다.
- [acceptance specs](../tests/specs/ACCEPTANCE.md)는 명세이며 실제 실행 결과와 구분한다. 문서 링크·canonical 재결합 검사는 [validate_bundle.py](../tools/validate_bundle.py)로 확인한다.

## 과거 기록

[최근 T24 보고서](../output/t24-wisdom-realm/REPORT.md)는 현재 release의 검증 근거다. 이전 결과는 `progress/T*_execplan.md`, `progress/*_result.*`, `output/t*/REPORT.md`에서 해당 작업만 찾아 읽는다. `docs/history/`의 기존 snapshot, `docs/source/`와 실제 source/model/receipt 증거는 원래 위치에서 보존한다. 과거 `tasks/`의 번호와 미착수 표시는 현재 backlog를 대체하지 않는다.

로컬 Git 최초 기준점 **`c10dc88`**은 2026-09-15 정리 직전 파일을 보존한다. 그 이전 개발 과정의 commit 이력이 생긴 것은 아니다. 이전 진입 문서의 정확한 본문은 필요한 파일만 조회한다.

```text
git show c10dc88:README.md
git show c10dc88:progress/STATUS.md
git show c10dc88:docs/INDEX.md
```

일상 작업에는 현재 파일과 `git diff`를 사용한다. 세부 원인·변경 시점이 필요할 때 `git log -- <path>` 또는 위 기준점을 조회한다.
