# 논문 Wiki의 PostgreSQL 저장·복원과 K Revision 탐색

2026-09-12. 기존 Test_Paper·Clarke·Dejani의 논문 페이지와 주제 문서를 PostgreSQL에 저장하고, 해당 문서의 원문 근거를 공유하는 정확한 KRevision을 조회하도록 구현했다. 문서 작성·모델 검토는 이전 [첫 Wiki 실험](../t05-paper-wiki/REPORT.md)의 결과를 사용했다. 이번 저장·조회·복원 과정의 **모델 호출 0회, D2I 호출 0회, canonical D/I/K/P/W 변경 0건**이다.

## 실제 저장 결과

| 항목 | 결과 |
|---|---:|
| 논문 / 주제 페이지 | 3 / 22 |
| 현재 페이지 / 전체 문서 snapshot | 25 / 27 |
| 본문 항목 / I 근거 인용 | 37 / 72 |
| 현재 catalog version / 보존 catalog | 3 / 4 |
| 전체 입력 I / 보존 media | 87 / 94 |
| archive JSON 경로 / 고유 raw blob | 136 / 135 |
| 고유 raw blob bytes | 28,793,581 |
| 현재 K 탐색 연결 / exact KRevision | 35 / 32 |
| 기본 조회 노출 / 검토 필요로 보류 | 32 / 3 |
| source 범위 일치 | 52 |

문서 snapshot 27개에는 공통 MoDC·Th17 주제의 과거 snapshot 2개가 포함된다. 페이지 identity, 과거 snapshot와 부모 hash, 원래 모델 요청·제안·판정·실패 이력의 JSON bytes를 그대로 보존했다. BMDC는 별도 주제 페이지로 남아 있으며 다른 종류의 DC를 강제로 병합하지 않았다.

현재 DB는 **`palimpsest_wiki_pg`**, Wiki ID는 `01a0941f-90b3-792b-bd4b-a3e83c18eaeb`, 최종 import는 `01a0944e-69f8-73a5-9454-baa63e93b534`다. [identity](final-identity.json), [최종 CLI 검증](final-cli-verification.json), [각 명령의 정확한 argv와 JSON 응답](final-cli/)을 보존했다. 기존 source DB와 별도로 만든 실험 DB다.

| 논문 | K 탐색 연결 | 검토 필요 | 기본 조회 | 일치 원문 범위 |
|---|---:|---:|---:|---:|
| Test_Paper / SuperMApo | 21 | 0 | 21 | 30 |
| Clarke / C1q | 8 | 1 | 7 | 11 |
| Dejani / PGE₂ | 6 | 2 | 4 | 11 |
| 합계 | 35 | 3 | 32 | 52 |

이는 **`shared_source_evidence` 탐색 관계**다. 같은 I의 인용 범위 교집합 또는 같은 owned image를 확인하며 `semantic_support_validated=false`를 보존한다. N2E의 `supports`나 K 동일성 판정으로 해석하지 않는다. 한 KRevision이 여러 Wiki 항목에 연결될 수 있으므로 연결 수와 K 수가 다르다. 새 KNode/KEdge를 만들지 않았다.

알려진 의미 검토 필요 사항은 기존 KRevision 2개에 대한 3개 링크다. 기본 조회에서 제외하고 명시적으로 요청하면 원래 이유와 함께 보여준다. 최종 sync에는 새 review 파일을 전달하지 않았지만 이전 표시가 계승됐고 같은 요청 재생도 같은 receipt를 반환했다. canonical K의 기각 상태를 임의로 변경하지 않았다.

## 구현

- [archive 모듈](../../src/palimpsest/wiki_archive.py): 허용된 JSON 경로·원래 bytes·source packet·proposal/판정/실제 전달 receipt와 snapshot chain 검증.
- [K 탐색 모듈](../../src/palimpsest/wiki_knowledge_links.py): exact Data/I/grounding의 인용 구간 교집합 및 이미지 소유권에 따른 Revision 탐색.
- [DB 서비스](../../src/palimpsest/wiki_database.py): source와 canonical DB 대조, immutable import, expected-head CAS, 재시도, 과거 조회, cache 복원과 기존 renderer export.
- [0008](../../src/palimpsest/migrations/0008_wiki_projection.sql), [0009](../../src/palimpsest/migrations/0009_wiki_binding_guards.sql): 비canonical `wiki_projection` 12개 table과 source/Revision/coverage 제약. 이미 설치된 0008 bytes를 수정하지 않고 추가 migration으로 보강했다.
- [CLI](../../src/palimpsest/cli.py), [DB 이름 선택](../../src/palimpsest/config.py), migration 목록과 앱 버전 0.7.0을 연결했다. 추가 dependency는 없다.

파일 Wiki의 모델 편집과 PG 반영은 명시적으로 구분된다. `wiki decide`로 파일 snapshot을 만든 뒤 `wiki database-sync`가 PG의 현재 import를 선택한다. 현재 DB 저장이 자동 이중 쓰기라고 주장하지 않는다. 공개 명령과 배포 mount 예시는 [Wiki DB 계약](../../docs/interfaces/WIKI_DATABASE.md)에 있다.

초기 실험 import는 K Record disposition을 잘못 비교하여 문서는 저장됐지만 링크가 0개였다. 실제 enum `accepted_new/accepted_revision`과 exact result refs를 사용하도록 수정했다. 초기 import를 삭제하거나 수정하지 않고 두 번째 import에서 35개를 저장했으며, 최종 0009 환경에서 세 번째 import를 저장·재생했다. 이전 import의 조회 결과도 이력으로 유지한다.

독립 review에서는 직접 SQL로 K payload·review 표시·선언된 연결 행을 위조/누락할 수 있는 0008 제약 공백을 발견했다. 동일한 fresh-ID 부정 입력 8개가 0008에서 거부되지 않는 것을 먼저 재현했고, 0009에서 모두 거부됨을 확인했다. 정상 copy control은 양쪽에서 통과했다. 모든 부정 probe는 rollback했다.

## 검증 결과

| 검사 | 실행 결과 |
|---|---|
| 최종 Docker build | exit 0, `palimpsest-wiki-pg:0.7.0` |
| 전체 앱 suite | **592개, 576 pass / 16 skip**, 103.796초, exit 0 |
| Wiki PG + CLI/config targeted suite | 실제 PG 9개 + CLI/config 4개 = 13개 모두 통과, 11.299초 |
| SQL negative8 + 정상 copy control | 0008에서 의도된 red → 0009에서 green |
| 실제 3편 최종 CLI | sync·same-request replay·catalog·논문/주제 related·공통 페이지 history·export 모두 exit 0 |
| PG 복원 → 파일 비교 | JSON 136, media 94, 현재 export 30, 관리 파일 2 전부 byte-identical |
| 이전 0008 dump 복구 → 0009 upgrade → export | 동일한 파일 집합과 bytes, 차이 0 |
| 최종 0009 dump → 새 DB 실제 복구 | 46개 표 / 6,157행 전체 hash 동일 |
| 최초 source clone 대비 D/I/K 및 원래 runtime | migration ledger 제외 33개 표 / 5,213행 hash 불변 |

16 skip은 기존 native PDF 검사 환경 조건에 따른 항목이며 로그에 이유를 보존한다. 앱 suite의 source/knowledge fixture 검사는 합성 입력으로 실제 PostgreSQL을 사용한 구조적 검사다. 실제 논문 CLI 검사는 기존 의미 산출물의 저장·근거 결속·복원 검사이며 새로운 semantic 품질 평가가 아니다.

[전체 앱 로그](app-tests-0009.log), [최종 build 로그](build-0009.log), [최종 파일 비교](restore-comparison-final.md), [경로별 SHA/bytes 결과](restore-comparison-final.json)를 확인할 수 있다. Markdown 26개는 논문 3·주제 22·목차 1이고, 현재 export 나머지는 원본 PDF 3개와 manifest 1개다. 모든 JSON을 새로 직렬화해서 비교한 것이 아니라 원래 bytes를 비교했다.

최종 이미지 ID는 `sha256:e645a6d27718656cb252336b9505c0769928d8bba32288fff44a93061698588f`다. PostgreSQL 18.6 / pgvector 0.8.6과 정확한 migration checksum을 실행 시 검사한다. 기존 Compose 기본 image와 기존 source DB의 migration 상태는 변경하지 않았다. 새 일회용 app/migrate/test 컨테이너는 `--rm`으로 정리됐고 최종 확인에서 dangling image는 없었다. 기존 DB 컨테이너·volume·성공한 이전 버전은 보존했다.

## 백업·원본 보존

[최초 source 복제 검사](environment/), [0008 백업·복구](recovery/REPORT.md), [최종 0009 백업·복구](recovery-final/REPORT.md)를 분리해 보존했다. 최종 새 복구 DB는 `palimpsest_wiki_final_restore`다. 원본 전·새 복구본·원본 후의 전체 table hash가 같다. 최초 clone와 비교해 원래 D/I/K/runtime 33개 표가 변하지 않았고 기존 0001–0007 checksum도 동일하다.

최종 dump는 11,922,007 bytes, SHA-256 `03553d2e340b584a7d9a20934f01a9462cb85f63af2ccb7fbb0f94dbc8a43dc2`다. 이 dump는 DB schema·행·Wiki raw JSON을 포함한다. Artifact Store의 PDF/media와 cluster role/credential까지 포함한 백업이라고 해석하지 않는다. 이번 복원 검사는 기존 role이 있는 같은 PG 서버의 새 DB에 실제 복구했다.

## 실제 실행 명령

아래 두 test/build 명령은 이 작업에서 실행한 것이다. 이 fixture 프로젝트와 실제 논문 DB 이름을 바꾸어 해석하지 않는다.

```powershell
docker build --tag palimpsest-wiki-pg:0.7.0 .
$env:PALIMPSEST_APP_IMAGE='palimpsest-wiki-pg:0.7.0'
docker compose -p palimpsest-multi-checks run --rm --no-deps -T test
docker compose -p palimpsest-multi-checks run --rm --no-deps -T migrate db migrate --database-name palimpsest_wiki_pg --json
docker compose -p palimpsest-multi-checks run --rm --no-deps -T migrate db migrate --database-name palimpsest_wiki_restore_check --json
docker compose -p palimpsest-multi-checks run --rm --no-deps -T --volume 'palimpsest-knowledge_artifacts:/var/lib/palimpsest/artifacts:ro' --volume 'C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/output/t05-paper-wiki/wiki:/source-wiki' --volume 'C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/output/t06-wiki-postgres:/results' --entrypoint python app /results/final_verify.py
```

공개 CLI의 개별 argv는 `final-cli/*.json`, 백업·복구 명령과 exit code는 각 recovery 보고에 있다. 비밀 DSN/credential 값은 산출물에 기록하지 않았다. source Wiki mount는 archive 잠금 획득 때문에 write 가능하지만 검증된 원래 JSON bytes를 수정하지 않았다.

## 남은 범위

정식 P는 현재 canonical 계약상 W 입력을 요구한다. 이번 `wiki_projection` 저장을 P 완료로 부르거나 가짜 W를 만들지 않았다. P의 입력 계약 확장은 별도 결정이다. 기존 `palimpsest-knowledge` DB0007의 적용 승인 상태도 그대로다. 이번 fixture DB migration은 대상 격리 증거를 보강한 후 자동 검토 승인을 받아 완료했으며 현재 이 작업을 막는 승인 거절은 없다.

I embedding 검색·자연어 질문에 대한 근거 조립 답변, 자동 증분 수집/재편집, 새로운 N2E/K2K 효과, GUI·crawler·인터넷 게시를 완료한 것은 아니다. 기존 multi-source graph의 outbox 70개 미수렴과 알려진 K 의미 문제 2개도 그대로다. T10의 전체 AT54/AT61/AT62/AT72/AT78/AT83/AT104와 T12 release, 정식 task T06 전체는 완료 처리하지 않는다.

문서 bundle 검사는 `python -X utf8 -B tools/validate_bundle.py`를 실행해 **exit 1, 기존 raw Markdown 오류 12개**를 확인했다. 새 Wiki 계약·보고의 오류는 추가되지 않았다. [문서 검사 로그](document-validation.log)에 정확한 경로와 이유를 보존했다. `python -m unittest discover -s tools -p "test_*.py"`의 전체 문서 mutation suite는 이번 마무리에서 다시 실행하지 않았다. 이전 Windows 긴 경로/격리 작업 폴더 및 raw 문서 문제로 실패한 기록을 앱 테스트 통과와 혼동하지 않는다.

변경 문서에는 README, AGENTS, docs/INDEX, DECISION_REGISTER, PAPER_WIKI_PROJECTION의 후속 설명, MODULE_BOUNDARIES, repository_inventory와 이번 실행 계획을 포함한다. Git 저장소가 아니므로 Git diff/commit 검사를 했다고 보고하지 않는다. 기존 canonical/source 문서와 historical bytes를 고쳐 검사 결과를 맞추지 않았다.
