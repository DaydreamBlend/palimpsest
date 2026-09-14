# 원문에 명시된 내용을 정리하는 다중 Data I2K

2026-09-11 구현 안내. [I2K 원문 정리·새 결론은 K2K](../decisions/I2K_SOURCE_ONLY_K2K_INFERENCE.md)와 [다중 Data 입력 계약](../decisions/MULTI_SOURCE_I2K.md)을 적용한다. **입력 결합·검증·DB 반영과 두 추가 논문의 실제 모델 실험을 수행했다. 신규 K 11개와 기존 Revision 재사용을 확인했으나, 잘못된 의미 범위의 승인과 인용 부족이 남아 제품 품질 통과로 판단하지 않는다.** [실험 보고서](../../output/t04-multi-source/REPORT.md)와 [실행 계획](../../progress/T04_multi_source_runtime_execplan.md)에 결과와 한계를 구분했다.

## 적용 상태

| 구분 | 확인된 상태 |
|---|---|
| 앱 이미지 | `palimpsest-multi:0.5.0` |
| 새 I2K profile | `multi-source-explicit-i2k-v1` |
| 결합 입력 schema | `multi-source-i2k-input-v1` |
| 새 migration | `0007_multi_source_i2k`, 기존 0001–0006을 재작성하지 않음 |
| 고정 이미지 전체 검사 | source/test bind 없이 484개 실행: 468 pass, 기존 환경 skip 16, 실패/오류 0 |
| 다중 source PG 대상 검사 | 다중 source 13개, 신규 CLI routing PG 2개가 최종 전체 검사에 포함됨. synthetic source·receipt, 모델 호출 0 |
| 실제 논문 실험 | 세 Data의 87 I·94 이미지를 준비. 성공 응답을 확보한 두 추가 논문 입력은 전체 51 I·44 이미지. 신규 K 11개, 후속 reuse 9개, 기각 1개. 실행은 미완료 의미 검토를 보존하는 needs_human |
| 기존 보존 DB | `palimpsest-knowledge`의 0007 적용은 자동 승인 검토 거절로 사용자 승인 대기. 기존 schema는 0006 |
| 격리 논문 실험 DB | `palimpsest-multi-checks` 서버의 별도 `palimpsest_multi_papers` DB에 백업 복원·0007 설치 완료 |

기존 보존 DB에 대한 승인을 받은 것으로 간주하거나 해당 DB의 schema가 바뀌었다고 보고하지 않는다. 별도 DB는 기존 DB를 변경하지 않는 격리 실험이며 승인 거절을 우회해 원래 대상을 변경한 것이 아니다. [승인 상태](../../output/t04-multi-source/migration-approval-status.json), [격리 DB migration 결과](../../output/t04-multi-source/migration-isolated-papers.json)를 확인한다. 아래 명령은 **0007이 설치된 명시적인 대상 DB와 일치하는 Artifact Store/DSN 설정**을 전제로 한다.

## 입력 결합과 검증

`multi_source_i2k.combine_packets()`는 각 완료 source 실행의 `i2k-input-v1` packet을 결합한다. 각 packet의 Data·source 실행·profile·내용/입력 hash·원문 refs와 전체 I 순서를 유지한다. 동일 Data의 여러 역사 실행이나 중복 I를 한 입력에 섞지 않는다. 같은 이미지 bytes는 전송 asset 목록에서 한 번만 보낼 수 있지만 각 I의 소유 관계와 위치는 남는다.

결합 packet의 `data_id`는 첫 source를 가리키는 **실행 시작점**이며 `data_id_role=operational_anchor_not_evidence_owner`로 표시한다. 실제 근거 소유자는 각 I의 `data_id`와 source snapshot이다. 후보가 두 번째 문서의 관측을 설명한다면 그 문서가 source owner이며 실행 시작점으로 바꾸지 않는다.

로컬 packet hash 검사만으로 DB 검증이 끝난 것은 아니다. `KnowledgeRuntime.prepare()`는 각 packet을 해당 Data의 canonical I·grounding·source bundle과 다시 대조하고, 전체 입력·기존 K catalog·profile·현재 K state를 동결한다. 여러 문서의 같은 페이지 번호도 Data별 refs로 구분한다.

**이번 구현은 결합하는 각 Data의 전체 source packet을 요구한다.** 최초 문서의 전체 검토 의무와 다른 문서에서 필요한 일부 I만 가져오는 제품 계약은 구별되지만, 관련 I subset을 별도 역할로 구성하는 일반 RAG 입력 경로는 아직 후속 범위다. 현재는 입력한 모든 source를 전체 검토 대상으로 삼고, 후보별 grounding은 그중 실제 사용한 I로 한정한다. 일부 I의 검토를 생략하고 미선택으로 기록하지 않는다.

## 후보, 판정, source identity

I2K는 명시된 내용을 정리·통합하며 원문에 없는 인과관계·일반화·가설·예측·새 결론을 만들지 않는다. 여러 문서가 명시한 내용의 각 부분을 함께 정리할 수 있지만 문서에 없는 관계나 조건을 추가하면 안 된다. 새 결론은 검증된 K 전제를 사용하는 K2K 범위다.

Generator 후보는 `claim_basis=explicit_source_content`, `is_inferred=false`, general/source scope, source owner, 중요성 선택 이유와 exact I evidence를 갖는다. 원문 저자의 해석을 귀속해 정리하는 것은 가능하지만 시스템의 새 추론이나 Observation으로 바꾸지 않는다. Validator는 기존 의미·중요성·scope 검토 외에 다음 세 조건을 명시적으로 판정한다.

- `source_explicit`: 원문에 명시된 내용이 근거인지.
- `no_novel_inference`: 원문에 없는 새 결론을 만들지 않았는지.
- `source_identity_preserved`: 실험·관측의 귀속을 유지했는지.

accepted/reused에는 세 판정이 모두 필요하다. 이 boolean이나 exact substring 검사를 통과했다는 사실만으로 의미적 원문 지지가 입증되지는 않는다. 실제 모델 평가에서 범위 확대·실험 혼합·인용 충분성과 잘못된 재사용을 따로 확인해야 한다.

| 대상 | 처리 |
|---|---|
| 같은 general 명제를 지지하는 여러 Data의 I | K 하나에 근거를 연결하고 같은 의미이면 기존 Revision 재사용 |
| 서로 다른 실험의 유사 Observation | source owner별 K를 구분 |
| source A의 동일 실험을 설명하는 B의 명시적 보완 근거 | owner A를 유지하고, 실제 owner 근거와 독립적인 귀속 검증이 있을 때 B의 grounding 추가 가능 |
| legacy scope 미분류 K | 원래 I2K Record의 owner를 확인해 검증된 scope를 연결. 현재 grounding Data 집합을 owner로 오인하지 않음 |
| 같은 의미의 새 근거·표현 변경 | 새 semantic Revision 없이 reuse/grounding 추가 |
| 원문에 없는 종합 결론 | I2K에서 반영하지 않음. K2K 구현·검증 대상으로 구분 |

이미 분류된 source owner와 기존 K/Revision/FP는 변경하지 않는다. 새로운 I2K-origin Revision의 조회 결과는 `generation_origin`에 실제 origin Record와 `origin_operation=i2k`, `is_inferred=false`, explicit-source 검증을 표시한다. 재사용 작업의 operation으로 기존 Revision의 생성 기원을 덮어쓰지 않으며, 과거 행에 없던 metadata를 임의로 소급 작성하지 않는다.

## PostgreSQL 원장과 반영

`0007_multi_source_i2k`는 다음 관계를 추가하고 기존 guard를 새 profile의 typed source 검증으로 확장한다.

| 관계 | 역할 |
|---|---|
| `compiler_runtime.k_execution_sources` | 실행과 source ordinal·Data·완료 source 실행·input SHA를 연결 |
| `compiler_runtime.k_explicit_source_decisions` | 후보 Record의 scope/owner와 원문 명시·새 추론 없음·source identity 검증 결과를 보존 |
| 기존 `k_input_information`·I별 review 관계 | 실제 전달한 I, 선택/문맥/미선택/검토 필요, 후보 링크와 Validator review 보존 |
| 기존 KNode/Revision·grounding·scope | exact I 소유권과 source owner를 검사하며 새 K 또는 재사용 효과를 저장 |

후보/검증·현재성 검사는 모델 호출 뒤의 짧은 transaction에서 수행한다. canonical 효과·원문 grounding·판정 Record·scope·후보 cleanup·후속 outbox를 함께 반영한다. 중간 실패는 canonical 효과를 rollback하고 durable staged Record를 남긴다. 같은 성공 request는 원래 결과를 replay하며, 다른 요청이 검증 중 K state를 바꾸면 stale 승인으로 반영하지 않는다.

I별 미완료 review는 추가 추출 의무로 남길 수 있으며 독립적으로 검증된 개별 K를 자동 무효화하지 않는다. 다만 실제 제공되지 않은 원본이 꼭 필요한 후보는 별도로 보류한다. 현재 native PDF 모델 전달과 직접 D grounding은 미구현이므로 원본 요청은 정확한 Data/I/page와 함께 지원 불가 상태로 보존한다. D2I 재실행·새 I 생성으로 해결하지 않는다.

## CLI와 worker

신규 공개 `knowledge prepare --operation i2k`는 단일 `i2k-input-v1` packet도
`combine_packets([packet])`으로 감싸 `multi-source-explicit-i2k-v1`을 적용한다.
`--selection` 유무와 관계없이 원문 명시·새 추론 금지 검증을 사용하며, 이 경로도
0007이 설치된 DB가 필요하다. 같은 request ID로 재시도할 때는 저장된 profile을
조회하여 새 단일 문서 실행의 동일한 wrapper를 재구성한다. 과거 legacy/selection
request는 원래 packet과 profile로 replay하고 입력 파일·역사 digest를 다시 쓰지 않는다.

**내부 호환 API의 제한:** `KnowledgeRuntime.prepare()`를 직접 호출하는 과거 테스트와
worker 경로는 기존 `selection=False/True` 동작을 유지하므로 새 legacy/selection 실행도
만들 수 있다. 이번 변경은 공개 CLI의 신규 경로를 고친 것이며, 모든 내부 호출 경로에서
새 explicit-source 계약을 강제한 것으로 보고하지 않는다. 신규 연동은 공개 CLI 또는
명시적으로 결합한 packet을 사용한다. 내부 API의 신규 legacy 실행 차단은 호출자·테스트를
명시적인 호환 경로로 옮기는 별도 변경이 필요하다.

각 source의 입력은 완료 실행에서 준비한다. 아래 `input-a.json`, `input-b.json`, `combined-input.json`은 **CLI envelope의 `result`만 저장한 packet**이다. `combine-inputs`와 `knowledge prepare --input`에 전체 envelope를 넣지 않는다.

```text
palim information prepare-input --execution-id SOURCE_A --json
palim information prepare-input --execution-id SOURCE_B --json
palim knowledge combine-inputs input-a.json input-b.json --json
palim knowledge prepare --operation i2k --selection --data-id FIRST_DATA_SHA --request-id REQUEST_UUID7 --input combined-input.json --json
palim knowledge show EXECUTION_UUID --json
palim knowledge stage EXECUTION_UUID --response generator.json --json
palim knowledge validation-context EXECUTION_UUID --json
palim knowledge decide EXECUTION_UUID --response validator.json --json
palim knowledge graph --data-id DATA_SHA --json
```

예를 들어 CLI 응답을 `combined-response.json`으로 저장했다면, 성공 상태를 확인한 뒤 원본 문자열을 변경하지 않고 `result`를 직렬화한다.

```python
import json
from pathlib import Path

envelope = json.loads(Path('combined-response.json').read_text(encoding='utf-8'))
if envelope['command_status'] != 'succeeded':
    raise RuntimeError('Input preparation did not succeed')
with Path('combined-input.json').open('x', encoding='utf-8') as output:
    json.dump(envelope['result'], output, ensure_ascii=False)
```

`prepare_selection_call.py`는 single/multi schema를 구분한다. `--context`에는 prepare 또는 validation-context의 응답을, `--source-directory`에는 실제 이미지와 `attachments.json`이 있는 검증된 export 디렉터리를 전달한다. 이 스크립트는 CLI envelope도 읽으며, 이미지 hash·크기·경로를 대조하고 새 request 파일을 만든다.

```text
python tools/prepare_selection_call.py generator --context prepared.json --source-directory SOURCE_EXPORT --request generator-request.json --response-name generator.json
python tools/run_knowledge_model.py generator-request.json --codex CODEX_EXECUTABLE
python tools/prepare_selection_call.py validator --context validation-context.json --source-directory SOURCE_EXPORT --request validator-request.json --response-name validator.json
python tools/run_knowledge_model.py validator-request.json --codex CODEX_EXECUTABLE
```

실제 순서는 prepare → Generator 호출 → stage → 반환된 validation context 저장 → Validator 호출 → decide다. 각 worker 파일은 `response`와 실제 `receipt`를 포함한다. Runtime은 frozen 입력으로 prompt/schema hash를 재구성하고 전체 I ID·이미지 목록과 실제 receipt를 비교한다. ID 목록만 유지하고 본문을 지운 요청도 거부한다. 모델 호출은 원문 전송 권한이 있는 범위에서만 수행하며, 예시 명령 자체가 새 원문의 전송 승인은 아니다.

호출 실패는 확보한 증거에 따라 구분한다. `call-failed`는 실제 provider 응답과 output hash가 있지만 구조 검사를 통과하지 못한 경우의 원장이다. 응답을 확보하지 못한 실행·전송 실패에는 `dispatch-failed`를 사용한다. 계획된 input/prompt/schema/request-file hash와 허용된 오류를 기록하되 `actual_delivery=null`, `output_sha256=null`, provider ref는 NULL로 남긴다. 원문을 보냈거나 모델이 읽었다고 꾸미지 않는다. 이 원장은 K 후보 승인·원본 요청 해결·canonical 효과를 만들지 않는다.

```text
palim knowledge call-failed EXECUTION_UUID --phase generator --response delivered-but-invalid.json --code knowledge_quote_mismatch --json
palim knowledge dispatch-failed EXECUTION_UUID --phase generator --response dispatch-failure.json --json
```

`dispatch-failure.json`의 `failure` 객체는 `input_sha256`, `prompt_sha256`, `schema_sha256`, `request_file_sha256`, `error_code`, `actual_delivery=null`, `output_sha256=null`을 갖는다. 잘못된 입력 결속, 허위 전달/출력 주장, 이미 성공한 단계에 새 실패를 넣는 요청을 거부한다. 같은 실패의 재전송은 원래 call ID를 반환하며 정상 재시도를 막지 않는다. 이 추가 경로의 현재 source/test bind 검사는 [11개 대상 결과](../../output/t04-multi-source/test-multi-dispatch.json)에 있고, 고정 이미지 전체 검사 시점의 결과와 구분한다.

기존 single-source profile·raw parser profile·완료 receipt와 request replay는 유지한다. 새 multi profile을 사용했다고 과거 모델 응답을 새로 실행한 것처럼 기록하지 않는다. N2E는 이후 accepted NodeRevision으로 별도 실행하며, 이 안내가 K2K·RAG index·전체 전파 완료를 뜻하지 않는다.

## 현재 실험 입력과 알려진 준비 오류

| 문서 | 선택된 I | 페이지 |
|---|---:|---:|
| Test_Paper | 36 | 14 |
| Clarke et al., Journal of Leukocyte Biology, 2015 | 35 | 14 |
| Dejani et al., PNAS, 2018 | 16 | 10 |
| 합계 | 87 | 38 |

결합한 I media는 94개, 31,026,087 bytes다. [입력 준비 요약](../../output/t04-multi-source/combined/summary.json)은 결합 시점의 결과이며, 진행 중인 Generator/Validator의 완료나 K 생성 성공을 뜻하지 않는다.

추가 source 준비에는 오류가 있었다. 과거 block profile을 재사용한 helper가 최종 grouped/page I 전에 **Clarke 159개와 Dejani 126개, 합계 285개의 원치 않은 중간 block I**를 생성했다. 이는 최신 그룹 저장 기본값에 맞지 않는 결과다. 행을 지우거나 ID를 다시 쓰지 않고 [source 준비 기록](../../output/t04-multi-source/sources-summary.json)에 남겼으며, 실제 모델 입력에는 선택된 최종 87 I만 포함한다. 해당 helper는 이후 기존 결과 검증 전용으로 제한했고 새 등록에 재사용하지 않는다. 기존 K 32개·Edge 26개·grounding 69개 및 당시 schema가 유지된 검증과, source 준비에서 추가 I가 생긴 사실을 구분해야 한다.

**실제 Terra 결과는 구조 검증과 의미적 품질을 구분해야 한다.** 새 K 11개를 더해 격리 DB에 43 K/43 NodeRevision이 있으며 같은 의미 9개는 기존 Revision을 재사용했다. 여러 Data의 근거를 가진 실제 K는 0개다. 초기 Validator가 처치군별 결과를 과도하게 합친 후보를 승인했고 후속 Validator는 같은 오류를 기각했다. 이미 승인된 잘못된 K의 재검토는 남아 있다. 전체 I별 검토 기록이 의미 추출의 완전함을 증명하지 않는다. [최종 고정 이미지 검사](../../output/t04-multi-source/app-tests-frozen-final.json), [실제 DB 감사](../../output/t04-multi-source/database-verification.json), [독립 의미 감사](../../output/t04-multi-source/evaluation/attempt-04-generator-review.md)를 각각 확인한다.
