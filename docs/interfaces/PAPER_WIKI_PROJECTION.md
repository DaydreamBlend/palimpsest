# 논문·주제 Wiki projection CLI

후속 버전 0.7.0의 [Wiki PostgreSQL 저장·복원·K 탐색 CLI](WIKI_DATABASE.md)를 함께 참고한다. 아래 모델 편집·파일 snapshot·renderer 흐름을 유지하고, 완료된 작업 공간의 명시적 DB sync를 추가했다. 이 후속 비canonical DB 저장과 정식 P 입력 계약은 별개다. 아래 0.6.0 예시는 첫 실험의 재현 환경이다.

2026-09-12. 이 문서는 기존에 등록·완료된 D/I를 읽어 논문별 문서와 관련 주제 문서를 만드는 첫 구현의 사용법이다. 구현·검사·실제 모델 실험의 진행 상태는 [실행 계획](../../progress/T05_paper_wiki_execplan.md)에서 확인한다. 이 문서는 모델 성공 건수나 논문 전체의 의미 정확성을 선언하지 않는다.

## 1. 어떤 문서를 만드는가

한 Data의 선택된 완료 source execution에서 논문 페이지 하나를 작성한다. 같은 Data를 다시 편집할 때는 같은 paper page ID를 유지한다. 서로 다른 Data는 논문 페이지를 공유하지 않는다. 같은 논문처럼 보이는 제목만으로 Data나 page identity를 병합하지 않는다.

모델은 해당 논문에 명시된 내용을 `overview`, `methods`, `findings`, `limitations`로 나누고, 각 항목의 정확한 I 근거와 관련 주제를 제안한다. renderer는 이를 **개요 → 방법 → 주요 결과 → 한계** 순서의 Markdown으로 만든다. 선택된 내용이 없는 섹션은 생략한다. 제목, frontmatter, 파일 이름, 링크, 인용 번호와 heading은 프로그램이 만든다.

주제 페이지는 각 논문에서 검증된 항목을 **논문별 구획으로 모은 문서**다. 예를 들어 BMDC 주제에 연결된 항목을 출처 논문별로 보여준다. 관련 항목이 한 논문에만 있어도 주제 페이지를 만들 수 있으며, 공통성을 만들기 위해 다른 논문을 끼워 넣지 않는다. 주제 문서를 만들면서 별도 모델이 새로운 통합 결론을 작성하는 단계는 없다.

같은 주제 페이지에 실렸다는 사실은 서로 다른 실험이 같은 K라는 뜻이 아니다. 세포 기원·종·처치·대조군·시점·측정값을 보존해야 한다. BMDC, 사람 단핵구 유래 DC, pDC 등의 용어를 같은 대상으로 바꾸지 않는다. 기존 주제는 `topic_key`, `title`, `scope`를 함께 제공하며, 같은 key의 정의를 편집 중 조용히 변경할 수 없다. 주제 동일성의 의미 판단은 모델 검증 사항이고, key 형식이나 JSON 검사는 그것을 대신하지 않는다.

새 일반 주제의 `scope`는 다른 논문에서도 재사용할 수 있는 **개념의 범위**로 정의한다. 특정 논문·처치·실험 결과에 해당하는 조건은 source별 item과 contribution에 보존하며, 일반 주제의 identity를 “이 연구에서 측정한…”으로 제한하지 않는다. 다만 연구가 정의한 특정 제제나 사건 자체가 주제이면 그 정의 범위를 유지한다. 기존 topic을 재사용할 때도 proposal의 `topics`에 같은 key/title/scope를 명시해야 한다. 이 규칙이 이미 저장된 topic 정의나 과거 snapshot을 자동으로 일반화·수정하지는 않는다.

이 첫 구현은 **비canonical 읽기용 projection**이다. 파일에 저장하는 page/snapshot ID는 canonical KNode/KRevision/Parchment ID가 아니며, Wiki 생성이 K/P 저장이나 사용자 Decision 확정을 의미하지 않는다. 페이지 편집에 따른 표현·배치 변경은 K semantic Revision을 만들지 않는다. 정식 P 입력 확장과 publication catalog의 DB 저장은 별도 계약·구현 범위다. 제품 설계 배경은 [자동 Wiki 설계](../../progress/AUTOMATIC_WIKI_DESIGN.md)를 참고한다.

## 2. 입력과 원문 경계

입력은 D2I가 이미 완료된 `source_execution_id`다. Runtime은 기존 CompilerRuntime이 제공하는 전체 I와 소유 media 목록을 사용하며, source packet hash·전체 I 포함·media 소유를 검사한다. stage와 decide에서는 보존된 I가 실제 PostgreSQL source와 일치하는지 다시 확인한다.

- 선택된 source의 모든 I를 읽기 순서와 전체 content로 제공한다. block preview는 탐색 보조이며 본문을 대체하지 않는다.
- mixed Text/Image I와 Image I에 포함된 media도 실제 모델 요청 첨부 목록에 포함한다. 선택된 I 자체가 원본 page-image I를 포함하면 그 이미지도 입력된다.
- 모든 I에 `used`, `context_only`, `not_selected`, `needs_review` 중 하나의 검토 결과를 남긴다. `used`는 실제 항목 근거에 사용한 I여야 한다. 모든 I가 wiki 본문이나 K로 선택되어야 하는 것은 아니다.
- 본문에서 선택하지 않은 I·raw·원본 artifact·기존 UUID·hash·profile·과거 Revision은 보존된다. I는 독립적인 원문·의미 검색 대상이라는 계약을 유지하며, 이번 Wiki CLI 자체가 I embedding 검색 기능을 추가하는 것은 아니다.
- 원문에 명시된 내용만 정리한다. 저자가 해석으로 보고한 내용은 그 귀속·불확실성을 유지한다. 새로운 인과·가설·계산 결과·자료 간 결론은 이 페이지 편집기나 I2K에서 생성하지 않는다. 새 추론은 검증된 K 전제를 사용하는 별도 K2K의 범위다.
- 근거 공백 때문에 I를 재조립·재등록하거나 D2I를 다시 실행하지 않는다. 필요한 원문을 이 입력으로 확인할 수 없다면 issue와 미해결 상태를 남긴다.

현재 모델 worker는 등록 원본 PDF bytes를 모델에 자동 전달하지 않는다. receipt의 `original_pdf_delivered`는 `false`여야 한다. 출력 export가 원본 PDF를 로컬에 복사하는 동작은 **모델에 PDF를 전달한 기록과 다르다**. 직접 D 근거 처리 정책은 [I2K 원문 근거 공백](../decisions/I2K_DIRECT_SOURCE_EVIDENCE.md), source-only 경계는 [I2K와 K2K](../decisions/I2K_SOURCE_ONLY_K2K_INFERENCE.md)를 따른다.

## 3. 실행 환경과 저장 폴더

Wiki 기능을 포함한 앱 image는 `palimpsest-wiki:0.6.0`이다. 기존 Compose 기본 image는 유지되므로 이 기능을 사용할 때 명시적으로 선택한다. 이미 초기화된 source 프로젝트의 DB와 Artifact Store를 사용하며, Wiki 실행을 위해 기존 DB migration을 자동 실행하지 않는다.

```powershell
$env:PALIMPSEST_APP_IMAGE = 'palimpsest-wiki:0.6.0'
docker compose build app
docker compose -p palimpsest-knowledge run --rm --no-deps -T --volume "${PWD}/output/t05-paper-wiki/wiki:/wiki" app wiki catalog --directory /wiki --json
```

위 마지막 명령은 이번 실험의 기존 source 프로젝트와 저장 폴더를 조회하는 예시다. 별도 배포에서는 프로젝트명과 host mount를 실제 설정에 맞춘다. `--no-deps`는 이미 준비된 DB에 연결하며 종속 migration 서비스를 시작하지 않게 한다. 실제 실험에서는 Artifact Store volume도 `:ro`로 덮어 mount해 원본을 읽기 전용으로 사용했다.

CLI는 기존 Python/Linux Docker 앱과 PostgreSQL·Artifact Store 설정을 사용한다. 아래 `python -m palimpsest` 명령은 설정과 볼륨이 연결된 앱 실행 환경에서 수행한다. `<...>`는 실제 값으로 바꾸는 자리이며, 예시 명령을 실행한 결과를 뜻하지 않는다.

모든 `wiki` 명령에 같은 `--directory`를 전달한다. 처음 사용하는 폴더는 없거나 비어 있어야 한다. Runtime이 `.paper-wiki.json` 관리 표시를 만든다. 비어 있지 않은 미관리 폴더나 다른 profile의 폴더는 거부한다. 일반 문서 폴더, 기존 Artifact Store, canonical DB 저장 폴더를 이 경로로 지정하지 않는다.

저장 구성은 다음과 같다.

| 경로 | 내용 |
|---|---|
| `.paper-wiki.json` | 비canonical Wiki export cache profile |
| `jobs/<request-id>/` | 입력 snapshot, profile, 요청, 응답·실제 호출 receipt, 제안, 판정, 실패 기록과 현재 job 상태 |
| `media/<sha256>.<ext>` | 선택된 I가 소유한 이미지의 검증된 복사본 |
| `snapshots/<snapshot-id>.json` | immutable paper/topic snapshot |
| `catalog.json` | 현재 paper/topic snapshot을 선택하는 catalog |
| `catalogs/<sha256>.json` | 과거 catalog snapshot |
| `exports/<export-key>/` | 특정 catalog와 renderer에 대한 Markdown·원본·manifest |
| `latest-export.json` | 가장 최근 export 결과의 위치와 manifest |
| `locks/` | 프로세스 간 공용 파일 잠금 |

파일 경로는 프로그램이 구성한다. 저장소는 상대 경로·부모 디렉터리·일반 파일을 검사하고 심볼릭 링크를 따라가지 않는다. immutable 파일에 같은 bytes를 다시 쓰는 요청은 재사용하며 다른 bytes는 `wiki_projection_conflict`로 거부한다. mutable job/catalog 교체는 완성된 임시 파일을 원자적으로 선택한다. 여러 작업의 catalog 변경은 공용 잠금으로 직렬화한다. 외부 모델 호출 동안에는 이 잠금을 유지하지 않는다.

## 4. CLI 흐름

자동화에는 `--json --non-interactive`를 사용한다. 결과와 job 상태를 함께 확인하며, 명령이 처리됐다는 사실만으로 문서 생성이 완료됐다고 판단하지 않는다.

| 명령 | 역할 |
|---|---|
| `wiki prepare` | source, metadata, 현재 topic catalog를 고정하고 `prepared` job 생성 |
| `wiki request --phase generator` | Generator prompt/schema/image 목록을 요청 JSON으로 저장 |
| `wiki stage` | Generator 응답과 실제 호출 receipt, source, 제안 구조·근거를 검사하여 `proposed`로 전환 |
| `wiki request --phase validator` | 고정된 제안·source로 독립 Validator 요청 JSON 생성 |
| `wiki decide` | Validator receipt·판정·current 상태 검사 후 snapshot/catalog 반영 또는 `needs_review` 보류 |
| `wiki show` | 요청의 상태·profile·결과·실패 조회. `--include-input`일 때 전체 입력 포함 |
| `wiki catalog` | 현재 논문·주제 문서와 catalog version 조회 |
| `wiki export` | 현재 또는 지정한 과거 catalog를 Markdown 묶음으로 내보내기 |
| `wiki history` | page ID의 현재 snapshot부터 이전 snapshot까지 이력 조회 |
| `wiki call-failed` | worker가 남긴 호출 실패를 기록. 실행 실패를 의미적 기각으로 처리하지 않음 |

### 입력 준비

metadata JSON은 `title`, `filename`이 필수이며 `doi`는 선택이다. 이 셋 외의 field는 허용하지 않는다.

```json
{
  "title": "논문의 실제 제목",
  "filename": "paper.pdf",
  "doi": "논문에 기록된 DOI"
}
```

```text
python -m palimpsest wiki prepare --directory <wiki-dir> --execution-id <completed-source-execution-uuidv7> --request-id <new-request-uuidv7> --metadata <metadata.json> --json --non-interactive
python -m palimpsest wiki request --directory <wiki-dir> --request-id <request-uuidv7> --phase generator --json --non-interactive
```

같은 request ID에 같은 source·metadata·feedback reference·검토 메모·인용 보완 모드·문구 수정 허용 항목을 제출하면 원래 고정한 입력을 재사용한다. 같은 request ID로 다른 요청을 제출하면 `idempotency_conflict`다. 같은 Data의 다른 source snapshot이나 편집 시도에는 새 request ID를 사용한다. 이미 생성한 Data/I/page ID를 수동으로 바꾸지 않는다.

### 모델 호출과 Generator 응답 반영

`wiki request`는 호출 준비 명령이며 자체적으로 모델을 호출하지 않는다. 반환된 `request_file`에는 prompt/schema, input digest, 실제 첨부할 이미지 경로와 hash, output 파일 이름이 들어 있다. 호스트 worker가 이 요청을 읽어 승인된 모델 호출을 수행한다.

```text
python tools/run_knowledge_model.py <host-visible-generator-request.json> --codex <codex-executable>
python -m palimpsest wiki stage --directory <wiki-dir> --request-id <request-uuidv7> --response <generator-response.json> --json --non-interactive
```

worker를 호스트에서 실행한다면 요청 JSON과 `../../media/...` 이미지 상대 경로가 같은 폴더 구조로 보여야 한다. 컨테이너 내부 경로를 호스트 경로라고 가정하지 않는다. 파일 위치만 달리 보이는 mount 매핑은 허용되지만 source·prompt·schema·첨부 내용이나 receipt를 임의로 수정해서 맞추지 않는다.

응답 파일은 `response`와 `receipt`를 포함한다. Runtime은 모델 profile, prompt/schema/input/output hash, 실제 전송 표시, 전체 Information ID 목록, 첨부 이미지 hash·크기를 확인한다. 요청·descriptor가 존재한다는 사실을 실제 전송 완료로 기록하지 않는다.

### 독립 검증과 문서 반영

```text
python -m palimpsest wiki request --directory <wiki-dir> --request-id <request-uuidv7> --phase validator --json --non-interactive
python tools/run_knowledge_model.py <host-visible-validator-request.json> --codex <codex-executable>
python -m palimpsest wiki decide --directory <wiki-dir> --request-id <request-uuidv7> --response <validator-response.json> --json --non-interactive
```

Validator는 Generator와 다른 provider execution reference여야 한다. 같은 모델을 별도 호출한 검증이며, 인간 검증이나 오류의 통계적 독립성을 보장한다는 뜻은 아니다. 원문 지지, 인용의 충분성, 실험 범위 보존, 새로운 추론 없음과 주제 의미를 평가한다. exact quote가 일치하는 구조 검사와 문장이 충분한 근거를 갖추었는지 판단하는 의미 검증은 별개다.

현재 첫 slice는 항목과 주제 판정이 모두 accepted이고 Generator/Validator가 complete이며 I review에 미해결 항목이 없을 때 문서를 반영한다. 그렇지 않으면 `needs_review`로 남기고 current catalog를 변경하지 않는다. 일부 accepted 항목만 골라 부분 발행하는 경로는 없다. `wiki decide`의 `needs_review` 결과는 exit code **7**이다.

## 5. 재시도·피드백·동시 변경

```text
python -m palimpsest wiki show --directory <wiki-dir> --request-id <request-uuidv7> --json --non-interactive
python -m palimpsest wiki prepare --directory <wiki-dir> --execution-id <same-source-execution-uuidv7> --request-id <new-request-uuidv7> --metadata <metadata.json> --feedback-request-id <previous-request-uuidv7> --json --non-interactive
```

검토 메모를 지정하지 않은 `--feedback-request-id`는 **같은 source execution의 `needs_review` 또는 `failed` 요청**에 연결할 수 있다. 새 입력에는 이전 제안·판정 또는 오류를 재검토 자료로 보존한다. 이전 판정을 정답으로 복사하거나 새로운 성공 receipt를 만들어내는 기능은 아니다. 준비된 기존 요청을 덮어쓰지 않는다.

이미 `compiled`인 문서에서 후속 감사로 오류를 발견했다면 `--feedback-request-id`와 **`--review-notes <file>`을 함께** 지정해 같은 source의 새 편집 요청을 준비할 수 있다. 메모 파일은 비어 있지 않은 JSON 문자열 목록이어야 한다. 각 문자열도 공백뿐인 값이나 NUL 문자를 포함할 수 없다. notes만 지정하거나 빈 목록을 지정하면 `invalid_wiki_review_notes`다.

```json
[
  "결과 문장의 시간 기준이 원문의 처치 시점·측정 시점과 일치하는지 다시 확인해 주세요."
]
```

```text
python -m palimpsest wiki prepare --directory <wiki-dir> --execution-id <same-source-execution-uuidv7> --request-id <new-request-uuidv7> --metadata <metadata.json> --feedback-request-id <compiled-request-uuidv7> --review-notes <review-notes.json> --json --non-interactive
```

메모는 이전 요청·제안·판정과 함께 새 입력 snapshot에 보존되고 request hash와 input digest에 결속된다. 이후 메모를 바꾼 작업을 같은 요청의 재시도로 취급하지 않는다. 메모는 원문과 대조할 검토 지적이며 정답·새 출처·확정 승인으로 사용하지 않는다. **새 Generator와 독립 Validator 호출 및 정상 stage/decide가 필요하다.** 일반 재편집에서는 notes가 있어도 `proposed` 상태의 요청은 feedback 대상으로 허용하지 않는다. 아래 인용 보완 모드에는 명시적 메모가 있을 때만 좁은 예외가 있다.

새 편집을 준비하는 동안 기존 current 문서와 과거 snapshot은 유지한다. 검증된 변경이 정상 반영되면 같은 page ID의 새 snapshot이 current로 선택되고 이전 snapshot은 이력으로 남는다. 수정안이 보류되거나 실패했다고 기존 문서의 이력을 삭제·덮어쓰지 않는다. 이 흐름은 최초 Validator가 놓친 오류를 후속 검토에서 다루기 위한 경로이며 최초 판정이 항상 정확하다는 전제를 두지 않는다.

### 본문을 고정한 인용 보완: `--citation-repair`

문장은 원문과 맞지만 그 항목이 선택한 인용만 부족한 경우에는 전체 제안을 다시 작성하는 대신 **근거만 추가하는 새 요청**을 준비할 수 있다. 이 기능은 인용 하나를 보완하면서 다른 인용을 빠뜨리는 회귀를 막기 위해 추가했다. 실제 모델의 인용 선택 성공률이나 의미 정확성을 보장하는 기능은 아니며, 후속 실험·감사 결과는 별도로 기록한다.

```text
python -m palimpsest wiki prepare --directory <wiki-dir> --execution-id <same-source-execution-uuidv7> --request-id <new-request-uuidv7> --metadata <metadata.json> --feedback-request-id <base-request-uuidv7> --review-notes <review-notes.json> --citation-repair --json --non-interactive
```

`--citation-repair`에는 `--feedback-request-id`가 필수다. Runtime은 부모 요청의 검증 context hash와 정규화된 proposal을 확인하고, 현재 입력 packet이 그 부모의 **동일 source snapshot**인지 검사한다. 정규화된 제안·검증 context가 없는 실패 요청은 인용 보완의 base로 사용할 수 없다. base proposal, source, 메모와 보완 모드는 새 요청·입력 hash에 결속된다. 과거 base와 source/UUID/hash를 고쳐서 맞추지 않는다.

| 부모 요청 상태 | 인용 보완의 조건 |
|---|---|
| `needs_review`, `failed` | 동일 source와 검증 가능한 base가 필요. 추가 메모는 선택 |
| `compiled` | 위 조건에 더해 비어 있지 않은 `--review-notes` 필수 |
| `proposed` | **`--citation-repair`와 비어 있지 않은 `--review-notes`를 함께** 지정한 경우에만 허용 |

이후 명령 흐름은 동일하다. 새 요청에 `wiki request --phase generator`를 실행하면 전용 인용 보완 prompt/schema가 생성된다. 기본 모드에서 모델은 `additions`, 전체 I의 `reviews`, `complete`, `issues`만 반환한다. 각 addition은 기존 `item_key`와 추가할 exact I/block/quote 또는 소유 이미지 근거를 지정한다.

기본 인용 보완 모드에서 프로그램은 기존 item의 본문·section·순서·topic 연결, topic 정의와 **모든 기존 인용을 그대로 보존**하고 허용된 새 근거만 붙인다. 기존 근거를 누락한 응답이 들어와도 삭제하지 않으며, 기존 근거의 source role만 바꾼 것은 새 인용으로 인정하지 않는다. 새 item이나 topic을 만들거나 기존 인용을 다른 것으로 교체할 수 없다. 본문 수정은 아래의 명시적인 `--repair-item` 범위에서만 추가 허용할 수 있다.

모델에는 축약된 차이만 제공하지 않는다. 같은 source의 전체 I·실제 I 이미지, base의 각 항목과 기존 full citation catalog를 제공한다. 모든 I를 다시 검토하며 `used`는 **기존 인용과 새 인용의 합집합**에 맞아야 한다. 새 인용이 없다는 이유로 이미 근거로 사용 중인 I를 미사용으로 바꾸지 않는다.

근거를 찾지 못하거나 허용 범위 밖의 본문 수정이 필요한 경우에는 `additions=[]`, `complete=false`, 전체 I reviews와 issues로 미해결 상태를 보고할 수 있다. 기본 모드의 `complete=true`에는 최소 하나의 새 인용이 필요하다. 본문 자체가 틀린 문제를 인용만 덧붙여 성공으로 만들지 않는다. 해당 항목을 명시한 제한적 문구 수정 요청 또는 일반 재편집 요청으로 다시 생성·검증한다.

`wiki stage`가 추가분을 병합한 후에는 **새 독립 Validator가 병합된 전체 제안의 모든 항목과 주제**를 다시 검증한다. 변경한 인용만 검사하거나 부모의 판정을 자동 승계하지 않는다. `wiki request --phase validator`와 worker 호출, `wiki decide`를 거쳐야 하며, `complete=false` 또는 미해결 판정은 current 문서를 바꾸지 않는다. 기존 source·모델 응답·snapshot은 이력으로 남는다.

### 지정한 항목의 문구만 수정: `--repair-item`

원문에 없는 개별 농도를 단정한 표현처럼 특정 항목의 문구도 고쳐야 한다면, `--citation-repair`에 `--repair-item <existing-item-key>`를 추가한다. 여러 항목은 옵션을 반복해 지정한다. 같은 key 중복이나 base에 없는 key, 인용 보완 모드 없는 지정은 `invalid_wiki_editable_items`다.

```text
python -m palimpsest wiki prepare --directory <wiki-dir> --execution-id <same-source-execution-uuidv7> --request-id <new-request-uuidv7> --metadata <metadata.json> --feedback-request-id <base-request-uuidv7> --review-notes <review-notes.json> --citation-repair --repair-item <first-item-key> --repair-item <second-item-key> --json --non-interactive
```

Runtime은 이 허용 목록을 request hash와 input digest에 고정한다. 모델 응답에는 `text_changes: [{item_key, text}]`가 추가되며 **명시된 기존 item의 `text`만** 수정할 수 있다. 미지정 항목의 문구, 모든 section·순서·topic 정의와 연결, 모든 기존 인용은 그대로 유지한다. 새 인용 추가는 함께 가능하지만 허용 목록은 근거의 정확성이나 변경의 승인을 뜻하지 않는다. 보완 후 전체 제안에 새 독립 Validator가 필요하다.

옵션을 생략하거나 Runtime의 key 목록이 `None` 또는 `[]`이면 기존의 본문 고정 계약과 같다. 문구 수정이 허용된 모드에서는 `complete=true`에 **새 인용 또는 실제 허용 문구 변경**이 최소 하나 필요하다. 해결하지 못하면 additions와 text_changes를 모두 비우고 전체 I reviews·issues와 `complete=false`로 보류할 수 있다. 다른 항목의 문구도 수정해야 한다면 새 요청의 허용 목록에 명시한다. section·topic·기존 인용을 바꿔야 한다면 일반 재편집을 사용한다. 이 확장이 실제 모델의 수정 성공을 보장하지는 않는다.

### current 선택과 호출 실패

다른 요청이 먼저 catalog를 갱신하면, 뒤의 편집안은 `wiki_catalog_changed`로 거부된다. 새 request로 현재 catalog를 다시 고정하고 재검토한다. 동일 입력의 오래된 검증 결과를 current에 강제로 적용하지 않는다. 일반 재편집의 새 prepare는 feedback 없이 시작할 수 있다. `proposed`를 부모로 삼는 인용 보완은 위의 명시적 메모 조건을 지켜야 하며 current 상태 검사도 그대로 적용된다.

표현 내용과 근거를 포함한 page body가 기존 snapshot과 같으면 snapshot을 재사용한다. body가 달라지면 같은 page ID에 새 snapshot을 만들고 이전 snapshot ID/hash를 연결한다. topic contribution이 없어지면 해당 topic은 inactive로 남고 기본 export에서 빠진다. 과거 snapshot을 삭제하지 않는다.

catalog의 원자적 current 선택이 반영 지점이다. 선택 직후 프로세스가 중단돼 job 상태 저장이 끝나지 않았더라도 동일 판정 재시도는 catalog의 commit receipt에서 결과를 복구한다. commit 전에 생성됐지만 current에서 선택되지 않은 파일은 완료 문서로 취급하지 않는다.

호출 실패는 worker의 `*.failure.json`을 사용해 기록한다.

```text
python -m palimpsest wiki call-failed --directory <wiki-dir> --request-id <request-uuidv7> --phase <generator-or-validator> --response <worker.failure.json> --json --non-interactive
```

Generator 호출 실패는 `failed`로 남고, Validator 호출 실패는 이미 준비된 제안의 `proposed` 상태를 보존한다. worker는 기존 응답·실패 파일을 덮어쓰지 않으므로 같은 output 이름으로 자동 재호출되는 기능은 제공하지 않는다. 실패 기록을 삭제하거나 receipt를 조작해서 재시도하지 않는다.

주요 오류를 다음처럼 구분한다.

| 상태·오류 | 의미와 처리 |
|---|---|
| `needs_review` | 의미/전체 검토 미해결. 현재 문서는 유지하고 새 feedback 요청으로 재검토 |
| `wiki_catalog_changed` | 준비 이후 catalog 변경. 새 request로 최신 상태에서 준비 |
| `wiki_implementation_changed` | 고정한 구현 profile과 현재 코드 불일치. 과거 입력·응답을 그대로 새 profile의 실행으로 취급하지 않음 |
| `wiki_delivery_mismatch` | 실제 호출 receipt와 요청·첨부가 불일치. 전달 근거를 확인 |
| `wiki_context_changed` / `wiki_snapshot_changed` | 고정 context 또는 snapshot 무결성 불일치. 손상된 내용을 선택하지 않음 |
| `idempotency_conflict` | 같은 request ID에 다른 요청·응답. 기존 이력 보존 |
| `invalid_wiki_review_notes` / `invalid_wiki_feedback` | 검토 메모 형식, feedback ID, 같은 source 여부 또는 허용 상태를 확인 |
| `invalid_wiki_citation_repair` / `invalid_paper_wiki_citation_repair` | 부모 제안·동일 source 결속 또는 인용 보완 응답 형식을 확인 |
| `invalid_wiki_editable_items` | 문구 수정 모드와 기존 item key의 허용 목록·중복 여부를 확인 |
| `wiki_projection_unmanaged_root` / `unsafe_path` | 저장 폴더 또는 경로 부적합. 도구가 관리하는 올바른 폴더 사용 |

## 6. 내보내기와 이력 확인

```text
python -m palimpsest wiki catalog --directory <wiki-dir> --json --non-interactive
python -m palimpsest wiki export --directory <wiki-dir> --json --non-interactive
python -m palimpsest wiki history --directory <wiki-dir> --page-id <page-uuidv7> --json --non-interactive
python -m palimpsest wiki export --directory <wiki-dir> --catalog-sha256 <historical-catalog-sha256> --json --non-interactive
```

export는 논문 Markdown, 활성 주제 Markdown, `index.md`, 등록 원본 복사본과 `manifest.json`을 만든다. paper↔topic 탐색은 Obsidian wikilink로 연결한다. 인용에는 Data, I, source execution, 정확한 문자 범위, block/raw locator, anchor hash, 페이지·bbox와 원문 인용을 담는다. PDF 인용은 함께 내보낸 해당 Data 원본의 페이지 링크를 제공한다.

원본은 Artifact Store에서 Data hash와 크기를 검증해 복사한다. 모델에 사용한 media와 구조화 citation도 보존하지만, 현재 Markdown renderer가 인용된 이미지 모두를 본문에 직접 표시하는 것은 아니다. image 근거는 SHA와 원본 위치로 추적한다.

export key는 catalog와 renderer 구현 hash에 묶인다. 같은 catalog와 같은 renderer의 출력은 재현 가능한 bytes를 사용한다. 과거 catalog를 현재 renderer로 다시 출력하는 것은 과거 renderer 자체를 복구하는 동작과 다르며, manifest의 renderer hash로 구분한다. 내보낸 Markdown을 직접 편집해도 Canonical Store나 projection snapshot으로 자동 역반영되지 않는다.

현재 export의 visibility는 `local_private`다. 이 명령은 인터넷 게시·웹 서버·crawler를 시작하지 않는다. 첫 slice에서 I 검색, K2K, W/P/B, GUI와 자동 수집을 모두 구현했다고 주장하지 않는다. 논문 입력 3편의 범위·실제 호출·보류·문서 수와 의미 감사 결과는 [실행 계획](../../progress/T05_paper_wiki_execplan.md)에 별도로 기록한다.
