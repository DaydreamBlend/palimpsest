# N2E 관계 생성·재검토 구현 결과

2026-09-14. 현재 저장 가능한 Proposition·Observation에 대해 N2E의 생성 → 독립 검증 → PostgreSQL 저장 → Revision/적용성 재검토 → 전파·조회 연결을 구현했다. 앱은 **0.19.0**, PostgreSQL은 **18 유지**, migration은 **0019_n2e_effect_fence**다. [계약과 CLI](../../docs/interfaces/N2E_RELATIONS.md), [실행 기록](../../progress/T20_n2e_completion_execplan.md).

## 실제 추가된 동작

supports, contradicts, qualifies, composes를 고정 스키마와 타입 규칙으로 처리한다. contradicts는 logical UUID 순서로 양 끝과 해당 Revision을 같이 정규화하여 반대 방향 제안이 중복 Edge가 되지 않게 한다. 같은 대상·scope·조건·시점의 양립 불가능성은 독립 Validator가 확인한다. composes는 명시적 전체의 진부분이며 현재 usable/applicable 관계에만 DAG를 적용한다.

같은 의미는 기존 Edge Revision을 사용하고, material qualifier 변경은 기존 logical Edge의 새 semantic Revision을 만든다. endpoint만 변경되면 original endpoint를 보존하면서 새 exact pair의 applicability event를 저장한다. predicate·방향 identity 변경은 새 logical Edge이며 기존 관계의 true/false/unknown 평가는 별도 Record다. 중요성·의미 동일성을 FP 문자열이나 스크립트가 대신 판단하지 않는다.

재검토를 준비하는 순간 exact pair가 pending이 된다. unknown·실패는 false나 기존 positive 복원으로 처리하지 않는다. 새 확인된 판정만 이를 해제한다. 기존 Record를 다시 쓰거나 legacy profile로 바꿔 pending을 지울 수 없고, 오래된 준비 상태·lease·독립 검증 누락·잘못된 endpoint/support signature도 거부한다. 동일한 negative를 재확인하면 새 material outbox를 만들지 않는다.

compilation Record·실제 모델 이유·script 보류 이유·정확한 Edge/Node Revision·applicability·outbox를 원자적으로 연결한다. 여러 composes 후보가 함께 순환하면 배열 순서에 따라 일부를 먼저 살리지 않는다. 조건부 target 복원도 prospective graph에 포함한다. 이 보류는 현재 context에 대한 판정이며 영구 FP blacklist가 아니다.

현재 usable contradicts가 있는 양쪽 K에만 `contested` 표시를 계산한다. Node의 의미·lifecycle·Revision을 수정하거나 어느 쪽이 참인지 자동 선택하지 않는다. Graph/Desktop/검색에 일반 상태 flag를 제공하고, source 범위 밖의 반대 주장·원문은 섞지 않는다. 이 과정에서 다른 current support 경로의 raw I/D가 검색 입력에 따라오던 문제도 수정했다. usable 관계만 exact EffectiveEdgeRef를 제공한다.

## 실제 Terra Medium 실험

직접 작성한 [가상 자료](live/fictional-relations.md)를 D로 등록하여 script D2I로 **I 9개**를 만들었다. N2E만 평가하기 위해 **K 8개는 synthetic receipt로 준비**했다. 이 부분을 실제 I2K 모델 성능으로 주장하지 않는다. 이후 N2E 생성과 독립 Validator는 기존 Codex OAuth의 `gpt-5.6-terra`/medium/CLI0.153.4로 실제 실행했다.

| 관계 | 실제 저장 | 모델이 연결한 의미 |
|---|---:|---|
| supports | 1 | Alpha20C의 10→20 관측이 증가 주장을 지지 |
| contradicts | 1 | 같은 Alpha20C의 증가/비증가 주장 |
| qualifies | 1 | 증가 주장을 Alpha20C로 제한하는 조건 |
| composes | 2 | 세척·배양이 명시된 Protocol Beta의 각 부분 |

Generator의 **5개 후보를 독립 Validator가 모두 승인**했고, 5개의 Edge 및 최초 Revision을 DB에 저장했다. 다른 실험인 Gamma40C의 10→8 결과는 Alpha20C에 대한 모순 관계로 생성하지 않았다.

같은 contradicts를 다시 검토한 실제 두 호출에서는 `edges=[]`와 명시적 `applicable=true`를 반환했고 Validator가 이를 확인했다. Runtime이 별도 assessment Record를 만들어 **no_material_delta**로 끝냈다. Edge Revision은 총5개, Node/Node Revision은8개 그대로이며 pending이 해제됐다. 실제 호출은 총 **4회**다.

이 실험은 통제된 가상 사례의 작동 검증이다. 실제 논문 전체에서의 정밀도·재현율을 측정한 결과가 아니다. 이후 추가된 guard와 repeated-negative 정책은 별도 PostgreSQL 회귀로 확인했다. 실제 실행 당시 Runtime bytes와 request/response/receipt는 모두 보존했다. [실제 호출·근거 검증](live-verification.json), [생성 결과](live/result.json), [재검토 결과](live/review-result.json), [exact graph](live/review-graph.json).

## 검증 결과

| 구분 | 결과 |
|---|---|
| 배포 이미지에 설치된 앱의 관련 검사 | 137개 통과, 실패/skip0 |
| 기존 schema0016 I2K/N2E Runtime 호환성 | 6개 통과 |
| 실제 PostgreSQL 검사 | 위 검사 중 새 N2E/worker/SQL22개 + 기존 Runtime6개 |
| 순수 계약·조회·검색·기존 K 회귀 | 위 배포 검사 중115개 |
| renderer 소스 | 20개 통과 |
| 실제 사용자 코드의 원문·이력 보존 | 읽기 전용137개 확인 |
| 이전 실제 Terra/Wiki 전파 실험 보존 | 읽기 전용18개 확인 |
| 이번 실제 N2E 호출·원문·Revision 보존 | 읽기 전용23개 확인 |
| 이미지/source/설치된 package bytes | 앱·SQL105파일 및 tests110파일 일치 |
| 과거 SQL0001–0016 | 보존된0.18 이미지와16개 모두 byte-identical |

중복을 제거한 관련 Python 검사는 **143개**, 별도의 renderer 검사는 **20개**다. 전체 앱 suite를 모두 재실행한 결과로 확대하지 않는다. [기계 판독 집계](verification-summary.json), [최종 패키지137검사](package-tests-final.json), [기존 Runtime6검사](legacy-runtime-tests.json), [SQL 최종검사](sql-guard-tests-final.json), [이미지 검증](release-verification.json).

초기22개 PG 검사 중 1개는 테스트가 legacy measurement payload를 K2K 입력에 제공하여 오류였다. 정상 구조의 I2K fixture를 쓰도록 테스트만 고쳤고, production 검증은 완화하지 않았다. [처음 실패한 결과](final-postgres-tests.json)와 최종 성공을 모두 보존했다. 첫 관리자 initializer의 파일 PermissionError도 일회성 root initializer로 해결했다. Docker build는 성공했고 새 이미지 하나만 만들었다. 시험 컨테이너는 `--rm`으로 종료했다.

문서 bundle 검사 결과는 [별도 파일](bundle-summary.json)로 기록한다. 기존 third-party/archive 문서 오류와 이번 작성 범위 오류를 구분하며, 문서 검사를 앱 검사로 세지 않는다.

## 사용과 배포 범위

배포 이미지: `palimpsest-n2e:0.19.0`

Image ID: `sha256:f886005d40683d8abcee9e1d15ac2076b3b24d20d65913c6d6a5b6c700e4754f`

새 DB는 `palimpsest_n2e_checks`이며 여기에만0017–0019를 적용했다. 기존 사용자 코드·논문 DB에는 쓰지 않았다. 이미 설치한0017/0018도 수정하지 않고 후속 검증 가드를 추가했다. 기존 원문·I·K·자료 버전·과거 SQL·모델 응답과 Electron 패키지는 보존했다. 이번 source renderer의 badge 변경은 개발 소스에 반영됐으며 기존 배포된 Electron 패키지를 재빌드하지 않았다.

```text
palim knowledge edge-input --data-id <SHA256> --node-revision-id <UUID> --node-revision-id <UUID>
palim knowledge prepare --operation n2e --data-id <SHA256> --request-id <UUID> --input <packet.json>
palim knowledge edge-call <execution UUID> --phase generator --directory <managed directory>
palim knowledge stage <execution UUID> --response <generator-response.json>
palim knowledge edge-call <execution UUID> --phase validator --directory <same directory>
palim knowledge decide <execution UUID> --response <validator-response.json>
palim knowledge edge-revalidate --edge-revision-id <UUID> --request-id <UUID>
palim knowledge graph --data-id <SHA256>
```

## 남은 별도 범위와 acceptance

현재 P/O를 입력받는 N2E의 핵심 경로는 완료했다. `supersedes`는 기존 R06의 authority-confirmed W2K 소유권을 유지한다. 아직 존재하지 않는 Decision/Procedure/Question/Entity 저장 유형이나 권한 정책을 이 작업에서 만들지 않았다.

AT11(original/effective endpoint 구분), AT14(latest negative 우선), AT17(repeated negative의 no material/no duplicate outbox)은 실제 PG 경로로 확인했다. AT09의 EffectiveEdgeRef 생산·조회, AT10의 projection key, AT13의 nonmaterial maintenance, AT15의 endpoint support usability, AT16의 pending·worker lease release는 해당 부분을 검증했다. 그러나 AT09/12/13/16의 **Edge를 실제 전제로 쓰는 K2K/W/P 소비자**, AT10의 **Edge embedding retrieval**, AT15의 **일반 lifecycle invalidation**은 별도 작업이므로 full T06 AT09–17을 전부 완료했다고 표시하지 않는다.

현재 K2K는 Node를 전제로 사용한다. Wiki 본문 생성도 기존의 I 기반 compiler를 유지한다. 관계만 바뀐 경우 Graph/Desktop의 current flag는 즉시 계산되지만 RAG는 기존 계약대로 Wiki DB 동기화와 index refresh가 필요하다. 보존된 답변이나 과거 Wiki snapshot의 의미를 새 current 상태로 덮어쓰지 않는다. 기존 전파의 대규모 paging 제안도 별도다.
