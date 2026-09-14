# LLM Wiki 계층·추론 기원 정책과 실제 근거 조회

2026-09-11. 사용자 후속 요구 네 가지를 설계·작업 지침에 반영하고 기존 PostgreSQL을 읽기 전용으로 확인했다. 앱 runtime이나 migration을 변경한 작업이 아니다.

## 반영한 요구

1. I2K의 근거 부족을 이유로 D2I를 다시 수행하지 않는다. 등록 D 원본에서 확인한 내용으로 K를 검증하는 직접 근거 경로와 오류/품질 이력을 보존한다. I 검색 실패만으로 D2I 누락을 단정하지 않는다.
2. K → I embedding 검색 → D 원본 확인의 LLM Wiki 조회를 따른다. K는 자주 활용할 것으로 LLM이 판단해 미리 정리한 지식이며, 나머지 I도 보존·검색한다. I/D 직접 답변과 canonical K 승격은 구별한다.
3. K는 K2K 귀납·연역으로 새로운 지식도 생성하는 층이다. I는 원문 표현으로 유지하고 전제 KRevision과 transitive I/D provenance를 연결한다.
4. 추론 생성 K는 그 사실을 필수 metadata로 보존·노출한다. 실제 origin에서 `origin_operation`/`is_inferred`를 표시하고 추론 유형·전제·가정/한계·검증을 연결한다. 나중에 원문 근거가 추가되어도 최초 생성 기원은 변경하지 않는다.

[원본 직접 근거 계약](../../docs/decisions/I2K_DIRECT_SOURCE_EVIDENCE.md), [LLM Wiki·K2K·추론 기원 계약](../../docs/decisions/LLM_WIKI_RETRIEVAL.md), [실행 계획](../../progress/T04_direct_source_policy_execplan.md).

## 실제 PostgreSQL 역추적

[재현 스크립트](verify_wiki_trace.py)는 기존 `palimpsest-knowledge` app image의 읽기 API를 사용했다. [결과 JSON](live-trace.json)에 정확한 원본 refs와 전후 수치를 보존했다.

```text
KNode 01a08ef3-5725-7da4-9a83-31e59cd71853
→ Revision 01a08ef3-5726-70f4-9388-89cd2a826cc2
→ Grounding 01a08ef3-5729-7be3-a786-6b5781bea7e9
→ 역사 I 01a08edf-e6a1-7491-9c89-26cea4222ba9
   Efferocytosis, 문자 [1399,1478)
→ Test_Paper 원본 물리 페이지 10
   /pdf_info/9/preproc_blocks/9
```

Data SHA는 `a2268b37570f41bb07189cf083376e5823fae364165d5e0e256f796a0814cffe`다. 저장 quote가 실제 I의 해당 substring과 일치하고, exact grounding의 원본 페이지가 10임을 확인했다. K의 짧은 인용만으로 제작 조건 전체를 설명할 수 있다는 검증은 아니다. 답변에서는 연결 I의 충분한 문맥을 읽어야 한다.

새 source snapshot의 같은 그룹 I `01a08f4f-ea58-7fc1-8da0-d3700ce789be`는 이 역사 I와 내용이 동일하다. mouse 제작 문맥 `[1241,1596)`은 10페이지, human 제작 문맥 `[4583,4799)`은 12페이지로 연결됐다. 역사 K grounding을 새 I로 교체하지 않았다. 한 I에도 여러 실험 문맥이 있으므로 단어/헤딩만으로 절차를 합치면 안 된다. 문헌은 사용자의 개인 실험 수행 기록을 증명하지 않는다.

| 실제 확인 항목 | 결과 |
|---|---|
| 선택 source I | 36개 |
| 현재 graph | KNode 32개, KEdge 26개 |
| DB 전체 역사 I 행 | 287 → 287 |
| DB operation execution 행 | 16 → 16 |
| NodeRevision / EdgeRevision | 32 / 26, 전후 동일 |
| 전체 Data graph 내용 | 전후 동일 |
| 이번 D2I / 모델 호출 / canonical 쓰기 | 0 / 0 / 0 |

이것은 명시적 ID를 사용한 실제 PostgreSQL·Artifact Store 역추적 검사다. 자연어 검색, BGE 검색 성능, 새 원문 누락 발견, 직접 D 근거 K 생성 또는 K2K 실행 시험이 아니다. 임시 조회 app 컨테이너는 `--rm`으로 실행했고 새 image를 만들지 않았다.

## 구현된 부분과 필요한 부분

현재 source 조회, I2K 전체 I 선택, N2E 및 K/Edge Revision 저장은 구현되어 있다. I2K에서 D2I로 돌아가는 코드 경로는 없었다. 기존 문서 세 곳의 D2I 보완 요구를 최신 지시로 교체했다.

현재 원본 요청은 durable 저장되지만 native PDF provider 전달은 지원되지 않아 관련 후보를 보류한다. 직접 D grounding, K2K 전제/추론 저장·실행·전파, BGE-M3 adapter/index, 자연어 질의·K2W 답변 runtime은 미구현이다. 특히 현재 migration의 direct I grounding 요구와 단일 Data scope를 모든 파생 K에 그대로 적용하면 안 된다. 정확 전제와 실제 출처 집합을 유지하는 추가 계약/검증이 필요하며, 설치된 migration은 수정하지 않았다.

## 검증 명령과 한계

```powershell
docker compose -p palimpsest-knowledge run --rm --no-deps -T --volume 'C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/output/t04-direct-source-policy:/probe:ro' --entrypoint python app /probe/verify_wiki_trace.py
```

Exit 0, 실제 PostgreSQL trace assertions 통과. secret 값이나 DSN은 출력하지 않았다.

```powershell
& 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 -B tools/validate_bundle.py --json
```

Exit 1. 보존된 parser/raw Markdown의 기존 표 형식 오류 12개가 남아 있다. [이번 결과](document-validation.json)와 [직전 기준](../t04-full-selection/document-validation-final.json)을 비교하며 새 오류는 별도 검증 JSON에 기록한다. 원본 raw를 validator 통과 목적으로 수정하지 않는다. 앱 코드 변경이 없어 앱 회귀/모델 시험을 다시 수행하지 않았으며, 이전 431-test 결과를 이번 실행으로 보고하지 않는다.

변경 전 13개 문서의 정확 bytes는 `.snapshot` 파일과 [SHA manifest](before-manifest.json)에 보존했다. 현재 canonical 원본/분할 snapshot과 앱/DB/model profile은 변경하지 않았다.
