# Storage·retrieval·보안·운영

> 상태: PROPOSED IMPLEMENTATION CONTRACT · 주 승인 항목 P10.
> U09 부분 적용: PostgreSQL 18/pgvector, 원본 hash와 duplicate/retry, 도구 관리 등록·복구 및 Runtime Record 보존은 [저장 계약](../decisions/STORAGE_IDENTITY.md)의 현재 규칙이다. 나머지 P09/P10의 read/retention/backup 세부 계약은 proposed이며 승인된 U 범위 밖의 새 필드·enum·명칭을 production 계약으로 사용하지 않습니다.


## 원본에서 유지하는 규칙

Artifact Store은 원본 bytes, Canonical Store는 canonical metadata/objects, Compiler Runtime은 runtime을 소유합니다. 서비스 분산은 의무가 아닙니다. embedding은 재생성 가능한 projection입니다. 근거: baseline §2, §4, §10, §24–25.

## 이번에 제안하는 구현 계약

### 1. Artifact publication

Palimpsest 등록 서비스가 사용자 원본을 허용된 storage root의 staging에 복사하고 보존 bytes의 byte_size/SHA-256을 확인합니다. prepared runtime journal을 남긴 뒤 overwrite 없이 content-addressed artifact_path로 publish하고 durability를 확인합니다. 그 후 DB에 readable D/acquisition/committed result를 한 transaction으로 저장합니다. 관리 폴더에 직접 복사한 파일을 자동 Data로 등록하지 않으며 사용자 원본을 이동·삭제하지 않습니다. 중간 오류는 frozen journal과 파일을 대조해 reconcile하고 자동 cleanup은 요청별 staging에 한정합니다.

새 요청으로 같은 bytes가 들어오면 duplicate_data와 기존 data_id를 반환하며 acquisition이나 D2I를 자동 추가하지 않습니다. 같은 성공 request/입력 retry는 기존 result를 반환합니다. 병렬 등록은 Data PK와 overwrite 금지 publish로 보호하고 기존 파일의 손상을 정상 duplicate로 숨기지 않습니다. staging 배타 소유와 이미 존재하는 object의 경쟁 처리는 U09의 상세 복구 규칙을 따릅니다. [T02 SQL 초안](../schema/T02_STORAGE_SCHEMA.md)은 미적용이며 파일 crash와 복수 DB session 검증은 별도입니다.

상대경로 validation, path traversal, symlink escape, 허가되지 않은 URL fetch를 방어합니다. 존재하지 않는 artifact를 빈 내용으로 D2I 성공 처리하지 않습니다. parser/OCR/extractor와 anchor version을 보존합니다. OCR 필요성은 문서 형식에 맞게 선택하며 성공을 가정하지 않습니다.

### 2. Read consistency와 index

P09 제안입니다. retrieval은 candidate generation일 뿐 authoritative usability 확인을 대체하지 않습니다. current pointer/lifecycle/applicability를 재확인하고 stale hit를 걸러냅니다. index watermark/projection profile을 반환해 새 데이터가 index-ready가 아닌 상태를 표시합니다. embedding이 늦다는 이유로 canonical 의미를 revision하지 않습니다.

KEdge projection은 EffectiveEdgeRef를 key에 포함합니다. model/dimensions/normalization 변경 시 index side-by-side rebuild와 atomic read-profile 전환을 제안합니다. fusion weight/top-K 값은 승인되지 않았습니다. 한국어/영어 혼합 lexical retrieval은 실제 평가 사례로 선택합니다.

U09는 초기 PostgreSQL 18의 pgvector 사용을 확정한다. profile별 차원·metric·normalization·저장/ANN 표현을 구분하고 차원이나 precision을 자동 바꾸지 않는다. 상세 한도와 BGE/Qwen 교체 경계는 [검색 profile](../interfaces/RETRIEVAL_PROFILE.md)을 따른다.

### 3. Privacy와 trust boundary

imported document/웹 payload/모델 출력은 untrusted data입니다. 문서 내용으로 operator 명령, 권한 승격, Decision confirmation, 파일 삭제를 실행하지 않습니다. authoritative mutation은 typed command와 actor/permission check를 거칩니다.

provider로 보낼 데이터 범위와 live API 호출은 명시적 허용이 필요합니다. 키를 채팅·로그·fixture·version control에 넣지 않습니다. env 전체를 출력하지 않습니다. 승인 UI는 실제 저장될 payload와 scope를 확인하게 합니다. HTML/Markdown rendering은 active content를 실행하지 않도록 다룹니다.

### 4. Retention과 삭제

immutability는 통상 수정 금지의 domain 규칙이며 운영상 영구 보유를 강제하는 보안 정책이 아닙니다. 사용자 승인 삭제/보관 만료/암호 키 폐기 요구가 있으면 tombstone·영향 보고·backup retention을 별도 ADR로 정합니다. 현재 패키지는 법적 보존 기간이나 삭제 규칙을 임의 확정하지 않습니다. historical ref가 더 이상 해석되지 않으면 명시적인 unavailable/redacted 상태를 반환합니다.

### 5. Backup·restore·observability

DB snapshot, artifact manifest와 hashes, profile/schema versions를 묶어 restore를 검증합니다. embedding은 재생성 가능하지만 원본과 accepted semantic snapshot/authority history는 backup에 필요합니다. outbox와 lease의 복원 후 중복 처리를 시험합니다.

metrics는 queue age, blocked obligation, material/non-material 판정 수, CAS stale rate, provider error, grounding failure, index lag를 구분합니다. rate/time threshold는 진단이며 propagation success cap이 아닙니다. 사용자에게 pause/resume/cancel과 partial-state 표시를 제공합니다.
