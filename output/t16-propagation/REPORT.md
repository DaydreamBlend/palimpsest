# 중단·재개 전파 worker와 독립 검증된 Wiki 갱신

2026-09-14. 앱0.16.0 / PostgreSQL18.6·pgvector0.8.6 / additive schema0016.

사용자가 요청한 **저장된 변경 영향 → outbox 소비 → 현재 K/관계 재검증 → Wiki 재생성 → 독립 검증 → DB 반영** 경로를 구현하고 실제 Terra Medium으로 실행했다. [운영 안내](../../docs/interfaces/PROPAGATION_WORKER.md), [실행 계획](../../progress/T16_propagation_execplan.md), [생성된 Wiki 문서](regenerated-wiki.md).

## 실제 실행 결과

실험은 격리 DB `palimpsest_propagation_checks`의 직접 작성한 가상 R1 문서로 수행했다. 초기 보고값3을4로 정정하고 상한5는 유지하는1117-byte Markdown을 등록해5 I를 보존했다. 초기 K/관계/Wiki 상태는10개 synthetic fixture receipt로 준비했으며, 이것을 실제 모델 품질 검사로 집계하지 않는다. 저장된 material revision Record에서 시작한 후속만 실제 OAuth `gpt-5.6-terra`/medium, CodexCLI0.153.4에 전달했다.

| 실제 후속 | 결과 |
|---|---|
| K 재검증·독립 Validator | 2회. 현재 전제4와5에서 기존 ‘상한보다 작다’ K를 재사용. `material_change=false`, `novel_conclusion=false` |
| Supports 적용성 재검증·독립 Validator | 4회. root 영향과 이어진 current-support 갱신의 의무를 각각 처리. 현재 endpoint pair에 대한 명시적 적용성 저장 |
| Wiki 생성·독립 Validator | 2회. 전체5 I를 전달·검토하고 출처 인용을 갖춘 새 페이지 저장 |
| worker | 7개 task 전부done, run completed. pending/leased/retry/blocked 및 미등록 causal outbox/support0 |
| 보존 검사 | 별도 read-only verifier18/18. 원본 D·I·최초 추론 기원·기존 semantic Revision·옛 Wiki bytes/snapshot 유지 |

실제 모델 호출은 **8회**이고 초기 synthetic receipt는 **10개**다. 전파 중 D2I/D2K와 원문 재등록은0회다. 완료 표시는 한정한 root와 그 causal 후속의 완료이며 가능한 모든 지식의 완전성을 뜻하지 않는다. [전체 구조 검증과 실제 receipt](live/verification.json), [준비 입력/초기화 구분](live/setup.json), [worker 종료](live-worker.log), [독립 대조 결과](live-verify.log).

현재 KRevision은 `01a09b9a-8781-7acd-abf7-65f11f8d4014`를 유지한다. 최초3<5 추론 이력은 보존하고, 현재 근거는 정정값4의 Revision `01a09b9a-8cd6-7b34-94dc-b69f0aa36051`과 상한5 Revision을 가리킨다. 새 Wiki snapshot은 `01a09ba8-1959-789d-87b4-1db771698083`, 이전 snapshot은 `01a09b9a-8a3d-7772-ba2f-e19ab57ac5b8`이며 둘 다 DB에 있다. 새 문서는 초기3과 정정4를 구별하고, 출처에 없는4<5 추론을 source-only 본문으로 섞지 않았다.

## 구현과 복구 경계

기존 불변 `k_outbox`를 삭제·수정하는 대신 `propagation_runs/tasks/events/task_causes/execution_bindings`에 처리 상태·원인·lease·실제 실행을 저장한다. 같은 작업의 여러 원인은 합치며, 시작 watermark 이후 반영된 causal child도 계속 수집한다. 같은 의미의 K는 새 Revision이나 material outbox를 만들지 않고, 검증한 현재 support를 추가하고 필요한 후속 유지 작업만 전달한다.

pause/resume은 epoch를 바꾸어 이전 lease의 반영을 차단한다. 실제 모델 호출은 transaction 밖에서 하고 반영 때 exact current input과 lease를 다시 확인한다. commit이 끝나고 ACK 전에 중단되어도 같은 execution/import를 찾아 이어 간다. 불완전한 모델 출력·불확실한 판정·전제 누락은 완료가 아니다. 연속 전송 실패3회는 검토가 필요한 운영상 보류다. 의미 보류의 재검토에는 명시적 이유가 필요하고 원래 실패/응답을 보존한다.

Wiki의 파일 저장과 DB import는 별도 checkpoint다. Generator/Validator에 동일한 전체 I·정확한 인용을 제공하며 두 실제 provider ref를 구분한다. DB head·원본 버전·K의 현재 근거·lease가 바뀌면 반영을 차단한다. cached completed 표시도 실제 import receipt와 대조한다. 이미 저장한 query 답변이나 과거 Wiki를 자동 덮어쓰지 않는다.

## 검사 기록

수정 후 재검사와 별도 native PDF 검사를 합쳐 **서로 다른 앱 검사1,020개 모두 통과**했다. 전체1,013개 실행은989 pass /23 native skip /Wiki 완료 cache 오류1개였다. 해당 오류 수정과 추가7개 검사, native 누락23개를 보충했다. 전체1,020개를 한 명령으로 다시 실행했다고 주장하지 않는다. [정확한 testcase별 중복 제거 집계](verification-summary.json), [전체 실행](regression-all.log), [마지막 lease 검사](final-fence-pg.log), [오류 수정·실제PG 재검사](final-cache-followup.log), [최종 이미지49개 검사](release-pure.log), [native PDF28개](native-pdf-pure.log), [native PG1개](native-pdf-pg.log).

초기 pure/container38개, 실제PG revalidation/worker11개, queue/Wiki/compatibility34개도 각각 통과했다. Windows controller14개는 별도로 검증했다. 기존 사용자 코드 DB read-only 검사는 **137개 모두 통과**했다. [보존 proof](history-proof.json). 최종 이미지에서 실제 demo 결과18/18을 다시 확인했고, 모델 호출 없이 completed run을 다시 읽는 [완료 재생](completed-replay.log)도 성공했다.

실제 PostgreSQL에서12단계 chain·두 부모 fan-in, 빈 discovery 결과와 무관한 exact dependency 처리, commit후ACK전 crash복구, pause/resume의 오래된 응답 거절, 독립 Validator 보류 시 Wiki 게시 금지, same-Revision support 갱신과 최신 negative edge applicability를 검증했다. 128단계나100001 fanout의 전체 명세 검증으로 확대하지 않는다.

초기 fixture 초기화 및 intermediate edge-pair 검사 실패는 수정 후 통과했으며 로그를 보존했다. 마지막 lease/cache 강화 과정에서는 실제 import와 응답의 전송용 `replayed` 필드 차이로 완료 확인 오류가 났고, 그 필드만 비교에서 분리한 뒤 통과했다. Tx의 모든 쓰기와 deferred constraint 검사 후 lease가 만료되면 stage/commit 전체가 rollback된다. 호스트 순수 검사 첫 시도는 PYTHONPATH와 psycopg 부재로 실패했고, 같은 검사는 잠긴 의존성이 설치된 Docker에서 통과했다. bundle validator는 기존 의존성/보관 문서의948개 오류로 전체 실패이며 이번 수정 문서 범위의 오류는0개다. 이를 앱 검사 실패나 전체 문서 정합성 통과로 바꾸어 보고하지 않는다.

실행한 주요 명령은 다음과 같다. 아래 Python 검사는 해당 Docker 안의 명령이며 mount/DB 선택은 연결한 로그·검사 도구에 기록했다.

```text
docker build -t palimpsest-propagation:0.16.0 .
$env:PALIMPSEST_APP_IMAGE='palimpsest-propagation:0.16.0'
docker compose -p palimpsest-multi-checks run --rm --no-deps -T test
python output/t16-propagation/run-tests.py test_revalidation_runtime test_wiki_refresh_integration test_propagation_runtime
python output/t16-propagation/run-tests.py test_wiki_refresh_integration test_wiki_refresh test_propagation_runtime_unit
python -m unittest test_propagation_runtime_unit test_wiki_refresh test_wiki_schema_compatibility test_revalidation test_propagation_controller -v
python output/t16-propagation/run-tests.py test_d2k_pdf_runtime
python tools/validate_bundle.py --json
```

최종 이미지 `palimpsest-propagation:0.16.0`의 ID는 `sha256:df179bdae69720b14a9f8449ca1db0a6e50932a97a96666aeedbb06b607db7f9`다. [배포 파일 대조](release-verification.json)에서 앱/SQL98파일·검사100파일이 최종 workspace와 일치했다. 실제8회 모델 실험은 최종 lease/cache 보강 전의 별도 image ID에 결속돼 있으며 [집계](verification-summary.json)에 둘을 구분했다. 최종 이미지로 기존 실제 결과를 읽고 대조하는 검사는 통과했다. 기존 고정 PDF 이미지에 최신 source를 읽기 전용으로 얹어 native 검사를 수행했고, 새 모델·PDF runtime 이미지를 내려받지 않았다.

## 적용 범위와 남은 일

새0016은 합성 `palimpsest_propagation_checks`와 회귀용 `palimpsest`에만 설치했다. 기존 실제 코드 DB `palimpsest_codebase_k2k`는 schema0013과 원래 D/I/Revision을 유지한다. 실제 논문 DB, 기존 Electron 패키지, 과거0001–0015 migration bytes도 유지했다. 새 worker는 운영 안내의 이미지·DB·Artifact Store를 명시하여 실행한다. 이 실험은 사용자 코드/논문의 자동 갱신 배포 완료를 뜻하지 않는다.

K2K는 아직 node premise만 지원한다. source-origin K의 자동 폐기 정책이나 source I 부족의 자동 D2K 우회는 추가하지 않았다. 의미 A→B→A 진동의 자동 탐지, 대규모 reverse-dependency paging/스트레스, EffectiveEdge 전제 추론, 정식 W/P/Decision과 인터넷 수집은 전체 T07 및 후속 작업으로 남아 있다. 실제 모델 실험은 작은 가상 문서에서의 기능 검증이며 일반 논문·코드의 의미 정확도 보장은 아니다.
