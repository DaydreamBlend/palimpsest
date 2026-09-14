# U09 — PostgreSQL·식별자·관리 등록·canonical 반영

상태: 사용자 네 선택을 적용한 설계 계약. SQL 물리 표현은 아래 링크의 T01 초안이며 앱/DB 설치·적용 완료가 아니다. 이 범위가 P01/P05/P10/P12의 충돌하는 제안 문장보다 우선한다. 나머지 P 항목의 전체 승인, 앱 언어·driver·migration runner 선택은 아니다. 승인 원문은 [USER_OVERRIDES](USER_OVERRIDES.md)에 보존한다.

## 1. PostgreSQL과 pgvector

최소 PostgreSQL major는 18, 최초 실행 대상은 18 계열이다. 설치/명시적 갱신 때 해당 major의 최신 안정 minor를 확인하고 실제 server_version, server_version_num, 배포 artifact/image digest와 pgvector extversion을 실행 profile에 기록한다. 19 이상은 정식 릴리스 이후 별도 업그레이드 검증을 거친다. major 하한이 18이라는 이유로 미검증 19/beta를 자동 선택하지 않는다.

pgvector extension 이름은 vector다. 선택된 PostgreSQL과 호환되는 안정 릴리스의 exact version을 기록한다. 2026-09-09 공식 조회값은 PostgreSQL 18.6과 pgvector 0.8.6이며 PG19는 Beta3였다. 이 값은 설치 성공 기록이 아니다. [PostgreSQL 버전 정책](https://www.postgresql.org/support/versioning/), [pgvector CHANGELOG](https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md)

초기 Canonical Store와 Compiler Runtime은 같은 PostgreSQL database의 canonical_store/compiler_runtime schema를 사용해 cross-schema transaction을 공유한다. Artifact Store는 도구가 관리하는 로컬 파일 영역이다. SQL schema 분리는 코드 모듈의 DB 분산을 의미하지 않는다.

PG18은 uuidv7()를 내장한다. 신규 opaque ID의 기본 생성에 사용하며 외부에서 제공한 ID도 v7인지 검증한다. UUID 정렬은 commit 순서·권한·최신 applicability 판정을 대신하지 않는다. [PG18 UUID 함수](https://www.postgresql.org/docs/18/functions-uuid.html)

18→19는 backup/restore 및 pg_upgrade 또는 dump/restore를 테스트 사본에서 검증한 뒤 적용한다. 새 major용 pgvector binary, extension 갱신, query/constraint/concurrency와 복구 검증이 필요하다. 현재 data directory를 새 major로 바로 열거나 image의 latest tag를 따라 자동 전환하지 않는다. [PostgreSQL pg_upgrade](https://www.postgresql.org/docs/18/pgupgrade.html)

## 2. ID와 중복 등록

data_id는 **도구가 실제 보존한 원본 전체 bytes의 SHA-256**이다. 파일명·경로·PDF 추출 텍스트·정규화된 문장을 해시하지 않는다. wire/SQL 초안의 표현은 64자리 소문자 hexadecimal text다. 기존 최소 metadata의 sha256은 같은 값이며 초안은 generated column으로 일치시킨다.

그 밖의 신규 opaque 객체·revision·Record·execution·acquisition·등록 request ID는 UUIDv7이다. 외부 actor/provider/model ID, fingerprint/digest, version, generation counter, ordinal, watermark·commit token은 기존 의미를 유지한다. 새 public Candidate ID를 만들지 않고 candidate_record_type + 소유 Record ID를 사용한다. 과거 ID/hash를 재발급하지 않는다.

| 상황 | 결과 |
|---|---|
| 새 요청으로 이미 등록된 동일 bytes를 제출 | duplicate_data와 기존 data_id 반환, nonzero CLI 결과. 새 Data/acquisition/원본 복제/D2I 시작 없음 |
| 같은 request ID와 같은 bytes·등록 metadata·actor로 성공 결과 재시도 | 권한 확인 후 기존 성공 result/동일 acquisition 반환. 응답 유실 때문에 중복 오류로 바꾸지 않음 |
| 같은 request ID를 다른 등록 내용에 재사용 | idempotency_conflict, 기존 결과 변경 없음 |
| 병렬 요청으로 같은 bytes 제출 | DB data_id 유일성으로 한 Data만 등록. 패자는 duplicate_data. 파일 publish도 overwrite 금지 |
| 같은 D의 독립 출처를 명시적으로 추가 기록 | 기존 Data에 별도 append-only acquisition 허용. 평범한 duplicate import가 자동 수행하지 않음 |
| 파일명만 다르고 bytes가 동일 | duplicate_data |
| 같은 논문이지만 bytes가 다름 | 새 Data. DOI/제목/유사 내용만으로 자동 기각·병합하지 않음 |

중복 검사 전에 파일 내용을 끝까지 해시한다. 동일 hash인데 크기/보존 bytes가 맞지 않거나 기존 artifact가 손상됐으면 정상 duplicate로 숨기지 않고 integrity_conflict로 처리한다. content hash는 동일 파일의 중복을 막지만, PDF 메타데이터·워터마크·개정판이 다른 같은 논문까지 판별하는 논문 식별자는 아니다.

## 3. 원본은 Palimpsest 등록 경로로 관리

사용자는 관리 폴더 바깥의 파일을 CLI/application service에 제공한다. 도구가 파일을 복사하며 사용자 원본을 이동·삭제하지 않는다. 관리 폴더에 직접 복사한 파일은 자동으로 Data가 되지 않고 자동 D2I도 시작하지 않는다. 지식 원문을 실행 지시로 해석하지 않는다.

등록 흐름:

1. request UUIDv7를 할당하고 staging 생성 전부터 해당 request의 배타 소유권을 확보한다. 기존 staging은 덮어쓰지 않고 소유·입력·복구 상태를 검사한다. 도구 소유 staging 경로에 원본을 스트리밍 복사한다. **복사한 bytes**에서 SHA-256/크기를 계산하고 읽기·쓰기 완료와 무결성을 확인한다. 외부 원본이 복사 도중 변경되면 안정된 입력을 재요청하며 사전 hash와 사후 파일을 혼동하지 않는다.
2. 입력 bytes hash, 등록 metadata, actor와 command version을 포함한 request_fingerprint로 prepared journal을 저장한다. 같은 request의 기존 fingerprint/result를 확인한다. staged 파일은 canonical Data가 아니다.
3. 같은 Data가 있으면 기존 artifact 무결성을 확인하고 duplicate receipt를 기록한다. 없으면 같은 filesystem의 content-addressed objects 경로에 overwrite 없이 publish하고 durability를 확인한다. object만 이미 존재하면 hash·크기·bytes를 검증해 재사용하고 자기 등록을 계속할 수 있다. 파일 존재만으로 duplicate를 반환하지 않으며 canonical Data의 존재가 기준이다.
4. artifact를 실제로 읽고 검증한 뒤 한 DB transaction에서 Data + 최초 acquisition + committed journal result를 확정한다. 병렬 insert의 유일성 충돌은 rollback 뒤 기존 Data를 조회해 duplicate receipt로 정리한다. 복사/파싱 중 장기 DB transaction을 유지하지 않는다.
5. 성공 후 해당 요청의 staging만 정리한다. 등록 성공은 D2I 성공이 아니다. D2I enqueue를 추가하는 단계에서는 성공한 최초 등록/명시적 compilation 요청만 원자적 outbox로 연결한다.

staging 전에/도중에 중단되어 journal이 없는 임시 파일은 미등록 상태로 남는다. 재실행은 같은 request를 검증하거나 새 요청으로 시작하며 파일 존재만으로 승인하지 않는다. journal 이후에는 frozen 입력으로 publish/commit 결과를 reconcile한다. file publish 후 DB commit 전 crash는 orphan 가능성이 있으므로 readable 파일과 journal·canonical 참조를 확인한다. 복구는 durable prepared 요청만 재개하며 관리 폴더 전체를 임의 import하지 않는다.

자동 cleanup은 요청별 staging에 한정한다. content-addressed 파일은 실패한 요청도 공유할 수 있으므로 cleanup이 삭제하지 않는다. orphan 제거는 live/진행 중 참조 확인과 별도 유지보수 절차가 필요하다. disk full, flush/publish 실패, path traversal·symlink/reparse escape, 사용자 임의 파일 덮어쓰기를 검사한다. 원본 외부 전송은 이 선택의 범위가 아니다.

## 4. 잠정 판정과 영속 Record

사용자의 “Runtime에 임시 저장 후 반영되면 옮기기”는 **후보와 잠정 결과를 준비하고, 검증된 semantic payload/effects를 canonical에 반영하는 방식**으로 구체화한다. 영속 판정 Record의 이동·삭제는 하지 않는다. canonical 결과가 어떤 판단에서 왔는지와 R08의 exact rejected FP 이력이 남아야 하기 때문이다.

| 단계 | Compiler Runtime | Canonical Store |
|---|---|---|
| 생성/검증 중 | 임시 후보 본문·근거, 잠정 검증 receipt, durable 실행 이력 | 미반영 |
| commit 대기/입력 stale | 후보·잠정 결과 유지 또는 새 입력으로 재검증 | 승인된 것으로 노출하지 않음 |
| accepted/reused | terminal Record의 FP·판정·reason·exact input/result refs·effects 영속 보존, 임시 본문 정리 | 검증된 새 snapshot 또는 허용된 grounding/effect 반영 |
| rejected | exact scoped FP·reason·Record 영속 보존, 임시 본문 정리 | 새 canonical 객체 없음 |
| no_material_delta | 검증 receipt·Record 보존 | 새 semantic revision 없이 필요한 support/applicability maintenance만 반영 |
| needs_human/기술 실패 | 미완료 의무·재시도 정보 유지. 기술 실패는 기각이 아님 | 미반영 |

canonical 효과 + provenance/current support + terminal Record + candidate cleanup + outbox는 같은 PostgreSQL transaction이다. 잠정 Validator 성공만으로 terminal canonical acceptance를 표시하지 않는다. transaction 실패 시 효과와 정리는 모두 rollback하고 준비 상태를 유지한다. commit 후 응답 유실은 같은 request/effect key로 기존 결과를 확인한다. `compiler_runtime`는 DB의 영속 schema이며 PostgreSQL TEMP/UNLOGGED 테이블을 의미하지 않는다.

## 5. 검색 profile과 pgvector

pgvector는 dense 검색 projection에 사용한다. BGE-M3 재순위화는 기존에 승인한 같은 모델의 multi-vector ColBERT 점수이며 pgvector dense 거리로 대체하지 않는다. profile별 차원/metric/normalization/index 표현을 구분한다. 재순위화 전용 token-vector cache도 해당 model/input profile에 귀속한다.

현재 pgvector는 vector/halfvec를 16,000차원까지 저장하지만 ANN index는 vector 최대 2,000, halfvec 최대 4,000차원이다. 따라서 BGE의 1024차원용 index를 향후 Qwen profile에 그대로 적용한다고 가정하지 않는다. 다른 profile의 차원 절삭·half precision·양자화는 자동 적용하지 않고 실제 교체 때 평가한다. [pgvector v0.8.6 README](https://github.com/pgvector/pgvector/blob/v0.8.6/README.md)

T02는 Data 등록 단계이므로 빈 embedding/profile 테이블이나 ANN index를 먼저 생성하지 않는다. extension 설치 요구와 version 기록은 지금 확정하고, 실제 typed source FK·profile 차원 검증과 index는 T03/T04의 검색 기능에서 추가한다. 이 선택이 fusion/top-K/유사도 threshold를 확정하지 않는다.

## 6. SQL 초안·검증·남은 범위

[T02 schema draft](../schema/T02_STORAGE_SCHEMA.md)와 SQL/fixture는 이 계약을 PostgreSQL 18용으로 검토 가능하게 만든다. 새로운 I/K/W/P/B 테이블, 미승인 public revalidation subtype, 별도 canonical Decision 판정 저장소를 scaffold하지 않는다.

AT56/67/68/70/107을 현재 의미로 보강하고 신규 AT108–AT112로 version/ID, duplicate/retry/race, 도구 등록·복구, 승격/Record 보존, pgvector profile 경계를 명세화한다. 실제 앱/파일 crash/PG 경쟁/모델 동작은 구현 후 실행해야 한다. P12의 앱 언어/CLI library/DB driver/migration runner·DB 실행 위치와 P10의 전체 보존·삭제·backup 정책은 미정이다.
