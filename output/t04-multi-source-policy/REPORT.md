# 다중 Data I2K 계약 점검

2026-09-11. 사용자가 명확히 한 관계는 **I 1개 이상 → K 하나**이며 I들은 서로 다른 Data에서 올 수 있다. 한 호출은 여러 후보를 처리할 수 있고 한 I는 여러 K를 지원할 수 있어 저장 관계는 다대다다.

[새 계약](../../docs/decisions/MULTI_SOURCE_I2K.md), [LLM Wiki·추론 메타데이터 보완](../../docs/decisions/LLM_WIKI_RETRIEVAL.md), [진행 기록](../../progress/T04_multi_source_i2k_execplan.md)에 반영했다. 이번 작업은 설계/현재 코드 점검이며 실제 다중 논문 컴파일 구현이나 모델 실험이 아니다.

## 확인한 제한

| 위치 | 실제 상태 |
|---|---|
| canonical §13 / MODULE_BOUNDARIES | 원래 I 1개 이상과 corpus의 관련 I 입력을 허용 |
| `knowledge.py` evidence / `knowledge_node_groundings` | 후보와 K Revision에 여러 I를 연결 가능 |
| `KnowledgeRuntime.prepare/_verify_i` | 실행 입력의 `data_id`와 `source_execution_id`가 단일 값 |
| 0005 `guard_k_input` | I의 Data가 실행 Data와 일치해야 함 |
| 0006 전체 검토/`source_data_id` scope guard | 한 source execution과 한 Data를 기준으로 검증 |

따라서 현재 한 논문의 여러 I로 K를 만드는 것과, 서로 다른 논문의 I를 함께 받아 하나의 K를 만드는 기능은 구분해야 한다. 단일 Data 제한을 단순 삭제하지 않고 각 입력 source를 검증하는 추가 profile/schema가 필요하다. 기존 앱/SQL/profile은 이번에 변경하지 않았다.

## 적용한 경계

- 문서별 전체 I 검토 의무, 추가 조회한 타 문서 I, 후보별 실제 evidence를 구분한다. 일부 I 조회를 그 문서 전체 검토로 기록하지 않는다.
- 각 grounding의 exact I → 해당 Data/source execution/원문 구간을 보존한다. 여러 I를 한 K에 연결하되 새 I로 합치지 않는다.
- 일반 의미가 같으면 같은 K/Revision에 근거를 추가한다. 서로 다른 실험 Observation을 하나의 관측으로 병합하지 않는다. 새 종합 결론은 실험 귀속·범위·불확실성을 검증한다.
- evidence의 Data 집합과 K의 의미 scope를 분리한다. 첫 Data를 대표 출처로 지정하거나 `general`로 강제 분류해 단일 scope 제약을 우회하지 않는다.
- 실제 원본 요청은 각 I의 소유 Data에 결속한다. D2I 재실행과 canonical I 변경은 없다.
- `origin_operation`은 직접 입력 경로, `is_inferred`는 실제 도출 방식이다. I2K가 I들을 근거로 새 귀납·연역 결론을 도출했으면 추론 사실과 I 전제를 기록한다. K2K는 accepted KRevision/EffectiveEdge를 전제로 쓴다.

이 마지막 항목 때문에 직전 문서의 “추론 생성이면 operation=k2k”라는 좁은 표현도 수정했다. 여러 출처가 이미 같은 주장을 보고하는 경우에는 다중 출처라는 사실만으로 시스템 추론이라고 단정하지 않는다.

## 검증

앱·DB·Docker·모델을 실행/변경하지 않았다. 기존 단일 문서의 검증 결과를 이번 다중 Data 검증으로 보고하지 않는다. 새 계약의 마지막 절에 후속 runtime acceptance를 기록했다.

문서 검증 명령:

```powershell
& 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 -B tools/validate_bundle.py --json
```

결과와 기존 오류 집합 비교는 [검증 JSON](verification.json), [validator 원문](document-validation.json)에 기록한다. 보존된 raw Markdown의 기존 오류를 이번 변경으로 고치지 않는다. 기존 문서 13개의 변경 전 bytes와 SHA는 [manifest](before-manifest.json)에 보존하며 [문서 diff](documents.diff)로 변경을 확인한다.
