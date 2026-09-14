# 반복 결과의 운영상 중단·정확한 재개 — 0.17

2026-09-14. 사용자의 후속 구현 요청에 따라 T16 다음 단계로 **동일한 authoritative 전제에서의 정규화된 결과 복귀 감지**를 구현했다. 앱0.17.0, schema0016 유지. [운영 안내](../../docs/interfaces/PROPAGATION_WORKER.md), [실행 계획](../../progress/T17_propagation_anomaly_execplan.md).

## 동작

같은 logical K가 같은 exact K premise Revision·current support·자료 버전·모델/profile에서 A→B→A 또는 A→B→C→A로 돌아오면, 검증된 canonical 전이를 확인하고 후속 outbox dispatch 전에 run을 `needs_human`으로 보존한다. Edge도 같은 semantic Revision·방향 있는 endpoint pair의 적용성 복귀를 검사한다. 중간 평가의 입력·profile·pair가 달라지거나 predecessor 연결이 끊기면 같은 반복 구간으로 연결하지 않는다. 길이가151인 순수 전이 목록도 길이만으로 진단하지 않는다. 이는 실제128개 canonical chain이나100001 fanout 시험을 대신하지 않는다.

기존의 comparison target Revision·이전 적용성·전역 DB watermark를 key에 넣으면 매 단계가 다른 입력처럼 보여 진단이 불가능하다. 이들은 key에서 제외한다. 비교 catalog는 달라졌을 수 있으므로 별도의 hash와 변경 여부를 witness에 보존한다. 이 key는 cache나 기각 fingerprint가 아니며, 전체 prompt가 동일하다거나 결과가 거짓이라는 판정에 쓰지 않는다.

이미 반영된 K/Revision/Record/적용성/outbox는 그대로 유지한다. 진단은 epistemic rejection, K invalidation, canonical rollback이 아니다. 이후 전파·Wiki 게시를 멈추며 미처리 작업을 완료로 표시하지 않는다. LLM이나 유사도 모델을 새로 붙이지 않고 기존 정규화된 FP·정확한 이력으로 판단한다.

`show`의 `anomalies`에 exact 전이와 `witness_sha256`이 나온다. 일반 `resume` 또는 다른 blocked task의 `retry`로 확인을 우회할 수 없다. `retry --acknowledge-anomaly WITNESS_SHA --actor-ref OPERATOR --reason ...`는 현재 target/premise/support/자료 버전/scope를 다시 확인한 뒤, 그 진단에 대한 확인과 재시도를 같은 DB transaction에 남긴다. 달라졌으면 새 범위를 요구한다. 한 번의 확인을 대상 K의 영구 허용으로 만들지 않는다. 확인 없이 취소할 수 있으며 취소 상태도 미완료로 남는다.

## 실제 검사

| 검사 | 결과 |
|---|---|
| 변경 영역 집중 회귀 | **64/64 통과**, 실제 PostgreSQL·순수 검사 혼합,161.709초 |
| 최종 Docker 내부 순수/controller | **30/30 통과** |
| 원래 사용자 코드 D/I/K·자료 버전·판정 이력 | **읽기 전용137/137 통과** |
| 실제 저장 진단·확인·완료 예시 | **읽기 전용5/5 통과** |
| T16의 실제 Terra/Wiki 이력과 old policy 호환 | **읽기 전용18/18 통과**, 과거8회 호출 보존 |
| 새 application LLM/provider 호출 | **0회** |
| 새 migration / 사용자 DB 수정 | **0회** |

실제 PG 검사5개는 synthetic 판정으로 의도적인 returning trajectory를 만든 뒤 저장된 outbox와 실제 queue를 실행했다. Node/Edge 이력 유지, 재시작 후 보류 유지, 정확한 확인, stale 확인 거절, 이후 복귀의 새 확인, 다른 task 재시도 우회 차단, 확인 없이 취소를 검증했다. 모델이 실제로 무한 루프에 빠졌다는 실험이나 일반적인 의미 품질 검증은 아니다. 테스트용 임시 Artifact Store는 사용자 자료 저장소가 아니다.

[64개 로그](targeted-regression.log), [최종 패키지30개](package-tests.log), [사용자 이력 proof](history-proof.json), [실제 진단 예시](diagnostic-example.json), [대조 결과](diagnostic-export.log).

[최종 집계](verification-summary.json)는 이번 새 검사17개와 집중 회귀64개를 구분한다. 새 이미지의 앱/SQL99파일·검사102파일이 workspace와 일치했고, 이전0001–0016 migration16개의SHA도모두같았다. 문서 bundle 검사는 기존 의존성/보관 문서948개 오류로 전체 실패이며 이번 수정 문서 범위는0개다. 이를 전체 문서 검사 통과로 표시하지 않는다.

최종 이미지 `palimpsest-propagation:0.17.0`의 ID는 `sha256:2731f2c99086add58ceb7ce39cffbab60c1f7851bc9fbc927ea891aea3a4bd8e`다. [이전 실제 실행 호환성](legacy-demo-compatibility.json)은 새 provider 호출 없이 검증했다. 원래 T16 proof 파일을 덮어쓰지 않았다.

실제 예시 run은 `01a09bda-8fdd-77fa-a409-8bd19ac84b0c`이고 witness는 `69dd98012562016094fcb8becaaceed9073f6a4942663c4717b579aeef8387bd`다. 이 예시에는 의도적으로 `synthetic-test-operator` 확인이 표시되어 있으며, 실제 사용자가 특정 논문/코드에 새 확인을 했다는 뜻이 아니다.

주요 실행 명령:

```text
docker build -t palimpsest-propagation:0.17.0 .
python output/t17-propagation-anomaly/run-tests.py test_propagation_anomalies test_propagation_anomaly_runtime test_propagation_queue test_propagation_runtime test_propagation_runtime_unit test_propagation_controller test_revalidation_runtime test_wiki_refresh_integration
python -m unittest test_propagation_anomalies test_propagation_runtime_unit test_propagation_controller -v
python output/t17-propagation-anomaly/export-diagnostic.py
```

Python 명령은 잠긴 의존성을 가진 Docker에서 실행했다. 실제 PG 선택은 `run-tests.py`에 고정된 `palimpsest_propagation_checks`이며 reset이나 schema 변경은 없다. 초기 PG4개/host25개도 통과했고, 최종64개에 새 우회 방지와 edge 연속성 검사를 포함했다. T16의 전체1020개 검증은 이전 baseline이며 이번에 전체 앱을 다시 실행했다고 표시하지 않는다.

## 부속 개선과 한계

maintenance-only 또는 nonmaterial support 처리에서는 쓰지 않는 discovery 전체 node 조회를 하지 않도록 옮겼다. 이 경로가 호출되면 실패하게 만든 실제 PG 검사로 확인했다. 대규모 처리 개선을 완료했다거나 처리량 수치를 측정한 것은 아니다.

자동 진단은 **정규화된 결과의 정확한 복귀**를 다룬다. 표현이 달라 FP가 모두 다른 의미적 반복, 새로운 주장이 계속 추가되는 모든 비수렴, 근거 binding이 없는 legacy 입력은 포괄하지 않는다. 기존 run의 frozen policy와 과거0001–0016 SQL bytes를 바꾸지 않았다. 새로운 run에서 새 진단 정책을 고정한다. 기존 코드/논문 DB와 Electron 패키지, D2I/I2K/D2K 및 정식 W/P/Decision 규칙은 유지한다.

다음 병목은 전체 graph/history를 읽는 조회와 한 번에 모든 의존 관계를 펼치는 과정이다. [T18 의존 관계 paging 후속안](../../progress/T18_dependency_paging_proposal.md)에 좁은 대상 조회, 영속 page cursor·coverage, SQL 집계와 bounded harvest 순서를 기록했다. 이 문서는 제안이고 128 canonical chain/100001 fanout/EffectiveEdge 전제 K2K를 구현·실행한 기록이 아니다.
