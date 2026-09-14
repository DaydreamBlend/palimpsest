# 코드 원문·검토 재개·Wiki/Electron — 0.13 구현 계약

**0.14 최신 정정:** [I-only·D2I 오류 보고](INFORMATION_ERRORS.md)에 따라 I 부족을 직접 D 근거 K로 보완하는 경로는 금지된다. 오류가 있으면 사용자에게 알리고 관련 K와 일반 자동 review-resume을 보류한다. 아래0.13의 일반 K 선택 검토 재개와 원문 조회 설명은 이 최신 경계 안에서 사용한다.

2026-09-13. 사용자의 후속 요청으로 Python 코드 전용 D2I, 보존된 I2K 검토의 재개, Wiki 검색과 Electron 조회를 연결한다. 이 범위는 [코드 snapshot](CODEBASE_SNAPSHOT.md)의 이전 parser 보류를 대체한다. 기존 D/I/Compiler Record/KRevision과 schema 0013까지의 이력은 보존한다. 이 문서는 구현 계약이며 실제 모델 실행 완료나 의미 품질 판정은 별도 실행 결과로 확인한다.

## 원문 코드 D2I

[code_adapter.py](../../src/palimpsest/code_adapter.py)는 등록된 완전한 `codebase-markdown-snapshot-v1` dossier를 입력으로 받는다. D는 여전히 dossier 전체 raw-byte SHA-256이며, 개별 파일을 새 D로 바꾸거나 기존 Markdown I를 덮어쓰지 않는다. embedded manifest의 member 경로·SHA·범위·framing을 먼저 검증한다. 임의 Python 파일이나 일반 Markdown을 dossier로 간주하지 않는다.

```text
palim code snapshot <repository-root> <new-snapshot-directory> --include src/example.py --json
palim data import-code-snapshot <snapshot-directory> --json
palim compile code <data-sha256> --json
palim jobs show <source-execution-id> --include-input --json
```

이미 등록된 dossier에는 새 등록 없이 `compile code`를 명시적으로 실행한다. `python-code-groups-v1`/`python-code-source-v1`은 Python 표준 라이브러리 AST·tokenizer와 실제 Python 구현/버전 profile을 사용한다. `.py`/`.pyi`의 작은 인접 정의를 6,000 Unicode 문자 soft target으로 묶고, 큰 클래스는 메서드·중첩 클래스 경계에서 나눈다. 함수 내부를 길이만으로 자르지 않는다. decorator, docstring, import/configuration, 주석·공백·모든 gap과 class preamble을 보존한다. 클래스 문맥은 exact enclosing-symbol metadata로 연결하며 I 본문에 설명을 합성하지 않는다.

구문 오류는 `parse_status=syntax_error`와 오류 위치를 남긴 전체 member로 보존한다. 다른 형식의 member는 `language=opaque`, `parse_status=not_python`으로 남긴다. 이는 해당 언어의 native parser 지원이 아니다. 빈 파일도 주소를 가진 I이며 dossier 포장·manifest는 `representation_role=dossier_metadata`로 원래 파일 본문과 구별한다. 모든 I는 `kind=text`, `unit_type=text`, `semantic_type=null`이고 전체 ordered blocks에서 D bytes를 정확히 복원할 수 있어야 한다.

**Production D2I의 application LLM 호출은 0이다.** 코드 D2I는 원문 코드를 실행하지 않고 Terra를 호출하지 않는다. PDF의 기존 승인된 로컬 MinerU 내부 OCR/layout VLM은 parser 내부 처리로 유지되며, application의 의미 선택·Generator/Validator 호출은 I2K부터다. D2I 구조 통과는 코드 실행·테스트 통과·사실의 참을 뜻하지 않는다.

## I ↔ dossier D ↔ member 위치

```text
palim information prepare-input --execution-id <source-execution-id> --json
palim information reconstruct --execution-id <source-execution-id> --json
palim information locate-information --execution-id <source-execution-id> --information-id <information-id> --char-range 0 10 --json
palim information locate --execution-id <source-execution-id> --byte-range 150 160 --json
palim information export-source --execution-id <source-execution-id> --destination <new-dossier-path> --json
```

예시 범위는 실제 I/D 크기에 맞춰 선택한다. `text_range`의 byte/Unicode codepoint 좌표는 0-based half-open이고 `line_start`/`line_end`는 1-based inclusive다. 줄 경계는 CR/LF/CRLF이며 BOM·Unicode·마지막 개행을 정규화하지 않는다. PDF 좌표를 대신 만들지 않는다.

block, `source_assembly.content_segments`, I2K `source_refs`의 `code_context`는 member 경로·SHA, member 내부 범위, 심볼의 local/global 범위와 enclosing symbols를 보존한다. `locate-information`의 부분 문자열 결과는 `matched_source_*`로 dossier 좌표를, `matched_member_char_range`, `matched_member_byte_range`, `matched_member_line_range`로 파일 내부 좌표를 제공한다. 포장 구간에는 member 좌표를 만들지 않는다. 원래 파일 복원은 기존 `palim code restore` 또는 `palim data restore-code-version` 계약을 따른다.

## 전체 I2K 검토 상태와 재개

[knowledge_review.py](../../src/palimpsest/knowledge_review.py)는 [source-review-v1](SOURCE_REVIEW.md)의 I/target/item 판정, 미해결 항목, source request, 실제 Record→KRevision 연결과 이전 검토 이력을 읽는다. `accepted_new`, `accepted_revision`, `reused`, `no_material_delta` 결과는 보존된 accepted 결과로 구분한다. 미해결 source 검토가 있어도 독립적으로 승인된 K를 지우지 않으며, 승인 K가 있다는 이유로 전체 검토를 완료하지 않는다.

```text
palim knowledge review-status <i2k-execution-id> --json
palim knowledge review-resume <held-i2k-execution-id> --request-id <new-request-uuidv7> --json
palim knowledge review-call <prepared-i2k-execution-id> --phase generator --directory <managed-call-directory> --json
palim knowledge stage <prepared-i2k-execution-id> --response <generator-exchange.json> --json
palim knowledge review-call <proposed-i2k-execution-id> --phase validator --directory <managed-call-directory> --json
palim knowledge decide <proposed-i2k-execution-id> --response <validator-exchange.json> --json
```

`review-status.next_action`이 `resume_review`인 보류/해당 생성 실패만 재개한다. 준비 중·검증 대기·진행 중 모델 호출은 해당 단계를 이어가고, 완료 결과는 `no_work`다. `review-resume`은 원래 전체 packet, source execution, version 범위와 이전 검토를 다음 실행에 고정한다. 같은 request ID는 같은 결과를 재사용하며, 같은 부모에 다른 request ID가 동시에 활성 후속 실행을 만들면 `review_resume_in_progress`로 거부한다. 현재 버전 문맥의 head 재검사와 pinned 범위는 [Data versions](DATA_VERSIONS.md) 규칙을 유지한다.

`review-call`은 정확한 prompt/schema, 전체 I 목록, version 목록, 필요한 보존 media와 binding을 로컬에 작성한다. Generator는 `prepared`, Validator는 `proposed` 실행을 요구한다. 재사용 시 요청을 다시 구성해 request/binding/hash를 대조하고 변조·다른 실행의 디렉터리 사용을 거부한다. 결과는 `actual_delivery=false`다. 요청 파일의 `delivered_*` 목록은 전달 후 검사할 기대 목록이며 그 자체가 실제 전달 receipt가 아니다. 이 명령은 provider를 실행하지 않는다. 실제 외부 전달은 승인된 원문 범위와 provider 흐름을 따르고, `stage`/`decide`에는 실제 호출 결과와 결속된 receipt가 필요하다.

I2K는 원문에 명시된 내용만 선택·정리한다. 새 결론은 accepted/current exact KRevision을 전제로 한 K2K에서만 생성한다. **I2K 재개와 Wiki 질의는 근거 부족을 이유로 D2I를 다시 실행하거나 I를 수정하지 않는다.** 보존 I에서 해결하지 못한 공백은 등록 원본 확인과 실제 전달/검증 여부를 기록하며 미해결로 남긴다.

## 현재 버전의 K 검색과 기존 추론 인용

[wiki_retrieval.py](../../src/palimpsest/wiki_retrieval.py)의 `wiki-accepted-support-v1` projection은 current KRevision과 현재 적용 가능한 전제를 사용한다. terminal accepted Record의 **전체 지원 경로**가 선택된 source I에 들어오는지 확인하며, 부분적으로 공유한 I 하나만으로 multi-Data K를 검색 근거에 넣지 않는다. 등록된 version support는 series head와 대조한다. 원래 generation origin과 나중에 추가된 accepted support 경로는 별개다.

K2K 결과는 모든 exact premise 경로가 해결된 경우에만 포함한다. `retrieval_support`에 실제 Record·derivation·premise refs·version과 transitive I를 보존한다. 이전 원문 I는 삭제하지 않으며 선택된 source 실행의 모든 I를 계속 검색 projection에 포함한다. 빈 I의 검색용 metadata descriptor는 원문 전사가 아니다. profile·K state·source version head가 달라지면 기존 index/context를 현재 결과로 조용히 재사용하지 않는다.

[Wiki query](WIKI_QUERY.md)는 원문 인용과 기존 accepted K2K 인용을 구별한다. 지원되는 context에서 `knowledge_evidence=[{"node_revision_id": "..."}]`는 정확한 기존 추론을 조건·가정·한계와 함께 충실하게 재진술하는 데만 사용한다. source-created K/Wiki 항목은 실제 I/원본 근거로 가는 탐색 문맥이다. 파생 K의 transitive I를 결론의 직접 원문 인용으로 위장하지 않으며 query-time K2K나 새로운 추론은 수행하지 않는다. 독립 Validator의 `accepted_inference_faithful`·`inference_limits_preserved` 검사가 추가된다. 검색 miss는 전체 D의 부재나 D2I 누락 증거가 아니다.

## 읽기 전용 Electron

[DesktopReadService](../../src/palimpsest/desktop_read.py)는 기존 [Electron UI](DESKTOP_UI.md)에 `knowledge_catalog`, `knowledge_node`, `review_catalog`, `review_status` 읽기를 제공한다. 화면은 source-created/system-inferred/기원 미기록을 구별하고, 실제 K2K origin Record, exact premises, assumptions/limits, direct/transitive evidence, current/historical version과 원문 code 위치를 표시한다. 검토 재개·모델 실행·canonical 쓰기는 이 IPC에 포함하지 않는다.

현재 Wiki 소유 Data의 보존된 다른 completed D2I 실행은 과거 I 조회에 사용할 수 있다. 다른 Data의 source execution, 잘못 짝지은 I, 외부 자료를 포함한 전체 Knowledge provenance는 공개하지 않는다. 전체 provenance를 보여 주는 상세 화면은 소유 Data의 지원 경로 하나가 존재한다는 이유만으로 외부 origin/support를 노출하지 않는다. 연결은 `default_transaction_read_only=on`을 강제하고 원문은 exact 소유권·SHA를 검사한다. 실제 Windows 패키지/화면 검증은 Python service 검사와 별도로 기록한다.

## 검증 범위

- [어댑터 검사](../../tests/app/test_code_adapter.py): exact bytes, BOM/CRLF/Unicode/decorator, AST 경계, syntax error·opaque·빈 member, tamper 거부.
- [Runtime 검사](../../tests/app/test_code_runtime.py): 격리 PostgreSQL의 native/기존 Markdown 이력, replay, 전체 D 복원과 양방향 위치·I2K metadata.
- [검토/Electron 검사](../../tests/app/test_code_review_desktop.py): synthetic receipt의 accepted 결과·재개 경쟁, request 변조, 외부 Data 격리, 실제 origin/전제/version 표시. Provider subprocess는 차단한다.

이 검사는 원문 보존·영속화·경계·재현성을 검증하며 LLM 의미 완전성을 대신하지 않는다. 실제 Terra I2K/독립 검토, 코드 Wiki의 live 의미 품질, 실제 Electron source/package 동작과 최종 회귀 결과는 해당 실행 기록에서 별도로 판정한다. 이 문서만으로 최종 통과·모델 호출 수·T12/T13 전체 완료를 주장하지 않는다.
