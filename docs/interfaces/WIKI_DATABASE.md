# Wiki PostgreSQL 저장·복원·K Revision 탐색

후속 2026-09-14: [전파 worker와 Wiki refresh](PROPAGATION_WORKER.md)는 앱0.16/schema0016에서 전체 I 생성·독립 검증 뒤 이 DB sync를 호출한다. 파일·DB checkpoint와 과거 import를 보존하고 마지막 쓰기/제약 검사 후 lease를 재확인한다. 새 worker 쓰기에는 명시적으로 검증한0016 DB를 사용한다. 기존 실제 코드0013·논문0010 DB를 자동 upgrade한 것으로 해석하지 않는다.

후속 [검색·답변 버전 0.8.0](WIKI_QUERY.md)은 추가 0010을 사용한다. 현재 `palimpsest_wiki_pg`에는 0010이 설치돼 있으므로 조회 시 `palimpsest-query:0.8.0`을 선택한다. 아래 0.7.0/0009는 당시 검증 환경이며 0009 복구 사본과 이전 이미지도 보존했다. 기존 Wiki schema·JSON·IDs를 변경한 것이 아니다.

2026-09-12. `palimpsest-wiki-pg:0.7.0`, PostgreSQL 18.6 / pgvector 0.8.6, additive migrations `0008_wiki_projection`와 `0009_wiki_binding_guards`의 구현 계약이다. [논문·주제 문서 생성](PAPER_WIKI_PROJECTION.md)에 영속 DB 저장을 추가한다. [실제 결과](../../output/t06-wiki-postgres/REPORT.md)와 [실행 계획](../../progress/T06_wiki_postgres_execplan.md)에서 검사 범위를 확인한다.

## 저장과 편집의 관계

기존 파일 Wiki의 `prepare → stage → decide`는 문서 편집 작업 공간이다. `wiki database-sync`가 검증된 archive를 PostgreSQL의 `wiki_projection`에 저장하고 해당 Wiki의 현재 import를 한 transaction에서 선택한다. 이후 DB catalog/history/related가 그 선택을 읽는다. 파일 편집 직후 DB에도 자동 반영된다고 간주하지 않는다. 자동화는 decide 성공 후 명시적으로 sync를 호출하고 두 단계 결과를 각각 기록해야 한다.

이 저장소는 비canonical Wiki 문서 projection이다. page/snapshot은 KNode/KRevision 또는 정식 P가 아니다. 문구·배치 변경으로 K semantic Revision을 만들지 않으며, canonical P의 W 입력 요구도 변경하지 않는다. D/I/K의 기존 내용과 ID, compiler Records, 원본 artifact는 보존한다. 입력 검증에 실패했다고 D2I를 다시 실행하지 않는다.

| 저장 대상 | PostgreSQL 내용 |
|---|---|
| Wiki·현재 선택 | UUIDv7 `wiki_id`, 현재 import request, 예상 이전 head |
| 논문·주제 페이지 | 기존 page UUIDv7, 논문 Data 또는 주제 identity |
| 문서 snapshot | 기존 UUID·body/hash·이전 snapshot와 그 hash·원래 JSON |
| 본문·근거 | item key/hash, exact I/Data/source execution, 문자 범위·인용·media hash |
| catalog | 현재·과거 version, 페이지별 선택된 snapshot |
| archive | 허용된 JSON 파일의 원래 bytes, SHA-256, path/size manifest |
| import receipt | request fingerprint, frozen K graph/state/profile, 검토 표시, 결과 건수 |
| K 탐색 연결 | exact KNode/KRevision/FP, 당시 본문·기원 필드, 실제 grounding 및 겹치는 source 범위 |

원본 PDF·이미지는 기존 Artifact Store에 보존한다. PostgreSQL에는 Wiki JSON 원본 bytes도 저장하지만 PDF/이미지 전체를 중복 저장하지 않는다. 따라서 배포 백업은 DB dump와 Artifact Store, 필요한 role/credential 설정을 함께 관리해야 한다.

## 원자적 저장과 재시도

첫 sync는 새 Wiki UUID와 request UUID를 사용한다. 후속 sync는 새 request와 `--expected-head`에 읽었던 current import를 넣는다. 같은 Wiki의 head row를 잠그고 현재 상태를 확인한 뒤 전체 archive/refs/receipt와 head를 함께 commit한다. 다른 작업이 먼저 갱신했으면 stale 오류로 종료하고 current를 조회해 재확인한 요청을 만들어야 한다.

같은 request에 같은 요청을 재전송하면 기존 receipt를 반환한다. 같은 ID의 다른 입력은 충돌이다. commit 전 실패는 새 current를 만들지 않고, commit 후 응답을 잃은 경우 같은 요청 재생으로 결과를 회복한다. 이전 snapshot·catalog·import·raw bytes는 수정하지 않는다. 같은 catalog에서 K 연결만 새로 조회한 sync도 새 import checkpoint를 만들고 이전 연결을 유지한다.

archive는 경로·파일 hash뿐 아니라 proposal/판정/실제 전달 receipt와 전체 source packet을 검증한다. source packet의 I와 인용은 실제 canonical DB와 대조한다. blob의 raw SHA·typed FK·snapshot chain·인용 소유권은 SQL에서도 검사한다. `0009`는 K 본문/Revision 결속, 검토 표시, nonempty matches와 선언된 파일·link·match의 commit 시 완전성을 추가한다. SQL은 source 관계의 무결성을 검사하며 문장의 의미적 참 여부를 판정하지 않는다.

## K 링크의 정확한 의미

`database-related`는 같은 Data/I의 실제 인용 구간이 겹치거나 같은 owned image를 참조하는 KRevision을 반환한다. `relation=shared_source_evidence`, `semantic_support_validated=false`다. 이는 원문을 따라 탐색할 수 있는 관계이며 N2E의 `supports` 판정이나 K 동일성 판단을 대신하지 않는다. 같은 페이지의 모든 문장이 K를 가진다고 보장하지 않는다.

연결할 때 current인 accepted KRevision을 고정한다. 이후 K가 개정되어도 과거 import는 원래 Revision을 유지하고 조회에서 `is_current_now=false`를 표시한다. 새 import는 그때의 current를 사용한다. 원래 기원 필드가 없는 legacy K에 `is_inferred=false` 등을 추정해 채우지 않는다. 명시된 기원은 원래 Record와 함께 보존한다.

주제 페이지는 조회 대상 catalog가 선택한 논문 snapshot/item을 통해 K를 찾는다. 서로 다른 논문들의 관찰·실험을 합치지 않는다. 오래된 논문 snapshot에 오늘의 K를 소급 연결하지 않는다.

선택적인 `--review-annotations` 파일은 기존 실험에서 알려진 검토 필요 사항을 exact `node_revision_id`에 연결한다. canonical K의 기각 상태가 아니다. 정상 갱신은 이전 표시를 계승하고 중복을 제거한다. 검토 표시는 해당 Revision에 남으며 새 Revision으로 자동 옮기지 않는다. 기본 조회는 표시된 링크를 제외하고 보류 수를 반환한다. `--include-review-required`는 원래 표시와 함께 조회한다. 표시 해제 정책은 이번 구현에 없다.

## CLI

다음은 설정과 volume이 연결된 앱 내부 명령 형식이다. UUID와 경로는 실제 값으로 대체한다. `--database-name`은 DSN의 DB 이름만 명시적으로 선택하며 자격 증명을 바꾸거나 출력하지 않는다.

```text
palim wiki database-sync --wiki-id <wiki-uuidv7> --request-id <request-uuidv7> --directory /wiki --database-name <db> --json --non-interactive
palim wiki database-sync --wiki-id <wiki-uuidv7> --request-id <new-request-uuidv7> --expected-head <prior-import-uuidv7> --directory /wiki --database-name <db> --json --non-interactive
palim wiki database-catalog --wiki-id <wiki-uuidv7> --database-name <db> --json
palim wiki database-history --wiki-id <wiki-uuidv7> --page-id <page-uuidv7> --database-name <db> --json
palim wiki database-related --wiki-id <wiki-uuidv7> --page-id <page-uuidv7> --database-name <db> --json
palim wiki database-restore --wiki-id <wiki-uuidv7> --directory /restored-wiki --database-name <db> --json
palim wiki database-export --wiki-id <wiki-uuidv7> --directory /restored-wiki --database-name <db> --json
```

조회·복원 명령에는 `--import-id <prior-import>`로 과거 DB checkpoint를 선택할 수 있다. `database-export --catalog-sha256 <sha>`는 선택된 archive 안의 과거 catalog를 기존 renderer로 내보낸다. sync만 `--review-annotations <json-path>`를 받는다.

실제 실험의 현재 catalog를 조회하는 PowerShell 명령은 다음과 같다. 기존 Compose 기본 image는 변경하지 않았다. `--no-deps`는 대상과 무관한 종속 migration을 실행하지 않게 한다.

```powershell
$env:PALIMPSEST_APP_IMAGE = 'palimpsest-wiki-pg:0.7.0'
docker compose -p palimpsest-multi-checks run --rm --no-deps -T app wiki database-catalog --wiki-id 01a0941f-90b3-792b-bd4b-a3e83c18eaeb --database-name palimpsest_wiki_pg --json
```

실제 원문 검증·복원·export에는 `palimpsest-knowledge_artifacts:/var/lib/palimpsest/artifacts:ro`를 mount한다. sync 입력 폴더는 archive 잠금을 위해 write 가능한 mount가 필요하지만 기존 JSON bytes는 수정하지 않는다. restore/export 출력 폴더는 별도로 mount한다. 기존 source DB `palimpsest-knowledge`에 이 버전의 전체 migration을 자동 적용하지 않는다. 이번 실험은 보존 사본인 `palimpsest_wiki_pg`에서 수행했다.

## 복원 경계

restore는 PG에서 archive 전체를 읽어 hash/chain/manifest를 검증하고 필요한 모든 media를 Artifact Store에서 먼저 확인한다. 대상 폴더의 들어올 파일과 충돌하는 bytes가 있으면 payload를 쓰기 전에 거부한다. 새 폴더에 일부 파일만 기록된 중단은 같은 bytes로 재시도할 수 있고 `catalog.json`은 마지막에 선택한다. 관리 표시·lock 파일은 초기화할 수 있다.

복원은 이미 다른 파일이 섞인 폴더를 정리하거나 삭제하는 명령이 아니다. 빈 전용 폴더를 권장하며, 기존 경로에서 충돌하면 새 폴더를 사용한다. 복원된 파일 cache에서 기존 Markdown renderer를 그대로 실행한다. DB K 연결은 DB 조회로 제공하고 과거 Markdown bytes에 임의로 삽입하지 않는다.

## 모듈

- `wiki_archive.py`: 안전한 파일 archive와 원래 JSON/receipt/source chain 검증.
- `wiki_knowledge_links.py`: I source 구간 교집합으로 exact Revision 탐색 링크 생성.
- `wiki_database.py`: canonical source 확인, PG transaction/import/head, 조회·복원·export.
- `0008_wiki_projection.sql`, `0009_wiki_binding_guards.sql`: 추가 schema와 DB 무결성 제약.
- 기존 `paper_wiki*`, `wiki_projection_store.py`: 모델 편집 작업 공간과 고정 renderer.

추가 dependency, application LLM 호출, D2I 호출은 이 저장·탐색 구현에 필요하지 않다. 실제 semantic RAG 답변, N2E/K2K 새 효과, formal P/W/B, GUI와 crawler는 이 범위의 완료 항목이 아니다.
