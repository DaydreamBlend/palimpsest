# Wiki PostgreSQL 저장과 exact KRevision 탐색 연결

2026-09-12. 사용자는 이전 Wiki 첫 구현 결과에서 후속 진행을 요청했다. 이번 수직 구현은 기존 논문3/주제22의 page·snapshot·인용·검토 이력을 PostgreSQL에 보존하고, 같은 원문을 참조하는 exact KRevision으로 탐색하는 경로다.

## 범위와 권한

- Python/Docker/PG18+pgvector 및 기존 Artifact Store를 재사용한다. CLI 우선, GUI/crawler는 후속이다. 새 dependency는 필요하지 않다.
- 정식 P는 현재 canonical §23.1의 W>=1 계약을 유지한다. 이번 DB read projection을 P로 이름만 바꾸거나 가짜 W를 만들지 않는다. P 입력 확장과 live 원본 DB0007 적용은 별도 승인 범위다.
- 기존 source D/I, 모든 K/Edge/Revision 및 파일 Wiki를 덮어쓰지 않는다. D2I 및 실제 모델 호출은 이번 구조적 저장/조회 검사에 필요하지 않다.
- 원본 palimpsest-knowledge는 읽기만 사용한다. 이전 multi-source 실험 DB의 보존 사본을 새 실험 DB로 복원하고 additive0008을 검증한다. 기존palimpsest_multi_papers도보존한다.
- 같은 I/겹치는 인용은 의미상 supports/equivalent가 아니다. 링크는 source-span 교집합이라는 검증 가능한 탐색 관계로 표시하며 exact Node/Revision/grounding/상태를 고정한다. 알려진 K 검토 필요2건을 숨기거나 canonical 상태를 바꾸지 않는다.

## 구현 경로

1. 기존 ProjectionStore의 안전한 읽기로 archive manifest·원래 JSON bytes·catalog/snapshot chain·선택된 proposal/Validator 연결을 검증한다. Media/원본은 Artifact Store의 exact hash로 복원하며 PG만으로 binary 원본까지 백업됐다고 하지 않는다.
2. `0008_wiki_projection.sql`: 비canonical wiki_projection schema에 Wiki identity, immutable raw blobs/files, pages/snapshots/source citations, catalog membership, import receipt/current checkpoint와 exact K 링크를 저장한다. 기존 migration bytes는 유지한다.
3. PostgreSQL import는 expected current checkpoint를 잠근 한 transaction에서 source 검증·snapshot/refs/receipt 삽입·current 선택을 완료한다. 같은 요청 재생과 같은ID 다른payload 충돌, commit 응답 손실 복구를 제공한다.
4. 같은 source I의 exact/overlapping text range 또는 같은 owned image를 참조하는 current KRevision을 탐색한다. K 본문/FP/기원과 연결 당시 state version, grounding IDs, review annotations를 보존한다. legacy null origin을 임의로 채우지 않는다.
5. CLI에 DB sync/catalog/history/related/restore/export를 추가하고 복원된 파일 cache는 기존 renderer로 동일 출력이 가능한지 검증한다. Topic은 해당 catalog가 선택한 paper snapshot/item을 통해 K를 조회한다.

## 소유권

- root: SQL/migration 목록, PG repository/service, CLI와 실험 환경·검증·문서 통합.
- archive 담당: `wiki_archive.py`와 순수/파일 archive tests.
- K 연결 담당: `wiki_knowledge_links.py`와 pure source-overlap tests.
- 별도 검토자: PG race/replay/source FK/restore의 integration tests와 최종review(계약이구체화되면배정).

## 검증과 완료

- 원본37items/72citations 및 selected source packet은 실제 DB와 일치해야 한다. 이전page/snapshot/원래JSON bytes/전후I·K표는보존한다.
- source/quote/소유권·다른page이전snapshot·같은ID변조·동시CAS·postcommit replay·과거catalog복원·KG변경후역사ref를검사한다.
- 실제3편을수입하고복원/Markdown해시/원본·mediaSHA를대조한다. 최종CLI·Docker검사와문서validator의기존12오류를구분한다.
- 신규본체P/W/B와T10의AT54/AT61/AT62/AT72/AT78/AT83/AT104, T12 release전체를완료처리하지않는다. 이T06번호는후속plan이름이며표준taskT06의모든K재검증완료를뜻하지않는다.

## 착수 시 확인한 상태

- 파일Wiki: paper3/topic22、catalog3, 전체87 I/94media. 기존app0.6.0 최종555tests(539pass/16skip).
- original source DB0006; multi 실험DB0007. multi graph43K/43NodeRevision/27Edge/27EdgeRevision/91groundings, state263, propagation미수렴(outbox70).
- known review-required2 revisions는Dejani처치군범위/ClarkePD-L2인용누락이다. exactcitation교집합22쌍→14item/K연결후보가있지만semantic support 수가아니다.
- Git 저장소는없다. 기존docmutationtests는Windows긴경로/격리작업폴더와기존raw표때문실패한기록이있다. 새작업에맞는targeted검사와전체문서오류차이를별도기록한다.

## 완료한 수직 구현 — 2026-09-12

계획 1–5의 archive/DB/current CAS/K 탐색/복원 CLI를 완료했다. 새 dependency 없이 0.7.0 image, additive 0008과 독립 SQL review 후 0009를 구현했다. 0008 기존 bytes와 최초 잘못된 K disposition 비교로 생긴 0-link import도 이력으로 보존하고, 최종 import에서 실제 35개 탐색 링크와 검토 필요 3개 계승을 확인했다.

최종 full app suite는 592개(576 pass/16 skip), 103.796초/exit 0이다. 직접 SQL 부정 8건은 0008에서 red를 재현하고 0009에서 거부됐으며 정상 control은 통과했다. 새 checkpoint 동시 CAS, commit 전 rollback/후 응답 손실 replay, source 위조, 과거 KRevision 보존, annotation 계승, 복원 충돌 선검사를 포함한다.

논문 3·주제 22·snapshot 27·인용 72, 원래 JSON 136 paths/media 94/current export 30의 복원 bytes 일치를 검증했다. 실제 PG 최종 backup→새 DB 복구의 46개 표/6,157행 hash가 일치하고 원래 canonical/runtime 33개 표/5,213행은 clone 이후 그대로다. 원본 live source DB·이전 multi_papers·모든 artifact는 보존한다. 임시 app/migrate/test는 --rm, 새 dependency/모델/D2I/canonical 효과 0이다.

fixture migration의 최초 자동 승인 검토 거절은 default DB의 격리 증거가 부족한 경우였다. read-only로 프로젝트 volume/DB명/fixture markers를 확인하고 같은 대상에 대한 검토를 다시 받아 승인 후 적용했다. 원본 DB 승인 문제를 우회하지 않았으며 현재 이 수직 구현에 남은 승인 차단은 없다.

[전체 결과·정확 명령·남은 acceptance](../output/t06-wiki-postgres/REPORT.md), [CLI와 모듈 계약](../docs/interfaces/WIKI_DATABASE.md), [파일 복원 대조](../output/t06-wiki-postgres/restore-comparison-final.md)를 참조한다. formal P/W/B·원본 live migration·전체 RAG/GUI/crawler와 표준 task T06/T10/T12는 별도로 남겨둔다.

최종 문서 validator는 기존 parser raw Markdown 오류 12개로 exit 1이며 새 Wiki 문서 오류는 없다. 기존 원본 bytes 보존 때문에 raw 표를 수정하지 않았다. 이전 실패가 기록된 전체 문서 mutation suite는 마무리에서 재실행하지 않았고 앱 테스트와 구분한다.
