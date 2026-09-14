# Markdown D2I — 그룹 Information 저장

2026-09-11. 작업 중 작성한 큰 Markdown 문서로 D 등록→D2I→I를 시험해 달라는 사용자 요청을 구현했다. [실행 계획](../../progress/T03_markdown_execplan.md), [실제 결과](../../output/t03-markdown/REPORT.md). PDF의 image200 MinerU 기본값과 과거 I는 유지한다.

## 경로와 사용법

Markdown은 원래 UTF-8 bytes를 도구로 등록하고 스크립트로 구조를 읽는다. OCR이나 LLM은 호출하지 않는다. parser는 `markdown-it-py==4.2.0`, CommonMark + table로 고정했다. 토큰의 line map을 구조 경계로 쓰고 실제 I 내용은 정규화된 token text가 아닌 원본 구간에서 복사한다. [공식 API·line map 설명](https://markdown-it-py.readthedocs.io/en/latest/using.html), [고정 배포](https://pypi.org/project/markdown-it-py/4.2.0/).

앱 컨테이너 안의 명령은 다음과 같다. 입력 폴더는 read-only mount하고, 실행 전 새 `0004_text_groundings` migration을 적용한다. 초기환경/설정은 [T02 runtime](T02_RUNTIME.md)을 따른다.

```text
palim data import /inputs/document.md --media-type text/markdown --json
palim compile markdown <data-sha256> --json
palim information list --data-id <data-sha256> --json
palim information show <information-uuidv7> --json
palim information prepare-input --execution-id <source-execution-uuidv7> --json
```

Data ID는 원본 bytes의 SHA-256이며 일반 중복 등록은 exit6으로 거부한다. 동일 등록 요청 ID는 원래 결과를 재사용한다. 같은 Data/profile/generation의 compile은 같은 실행/I UUID를 반환한다. `compile markdown`은 등록된 Artifact Store 파일만 읽고, profile 생성→파싱→결정적 검증→atomic I 저장까지 실행한다. `jobs show`는 prepared/parsed/proposed/completed 상태·receipt를 조회한다. 실패 중 남은 작업은 기존 `jobs retry/materialize` 경로로 재시도하며, 실행 실패를 의미적 기각으로 저장하지 않는다.

## 그룹과 원문 근거

최상위 ATX/Setext heading을 경계로 삼는다. 제목만 있는 부모 절은 첫 하위 절에 합치고 heading path를 유지한다. 내용 없는 형제 절과 서두·빈 문서도 보존한다. fenced/indented code, quote, list, HTML block 안의 heading은 문서 경계로 삼지 않는다. 표·코드·URL·원문의 지시는 source content이며 실행하거나 따라야 할 권한이 아니다.

새 `markdown-source-v1` bundle과 `markdown-groups-v1` 조립은 한 절을 한 source block/I로 만든다. I는 기존 `source-information-v1`, kind/unit_type=text, semantic_type=null이며, Record/outbox는 I 수만큼 생성된다. 원문을 잇는 추가 구분자를 넣지 않으므로 I를 source 순서대로 연결해 UTF-8로 인코딩하면 D bytes를 정확히 복원할 수 있다.

Markdown에는 `locator_type=text_range`를 사용한다. `page_index`, `bbox`, `page_size`는 SQL NULL이고 PDF page0이나 가짜 좌표를 만들지 않는다.

| 위치 | 규약 |
|---|---|
| `byte_start`, `byte_end` | 원본 UTF-8의 0-based 반열림 byte 범위 |
| `char_start`, `char_end` | 원문 Unicode codepoint의 0-based 반열림 범위 |
| `line_start`, `line_end` | 1-based inclusive 줄 범위 |
| `anchor_sha256` | 해당 원본 byte 구간의 SHA-256 |
| `raw_locator` | Data ID와 byte/char/line 범위가 결속된 참조 |

CR/LF/CRLF만 줄 구분으로 사용하고 원래 bytes를 유지한다. 마지막 개행은 앞줄에 속하며 빈 파일은 line1의 빈 위치로 표시한다. UTF-8 BOM은 content와 byte 범위에 보존하되 제목 판별을 방해하지 않게 처리한다. 비 UTF-8 또는 NUL은 명시 오류다. Unicode 정규화·개행 변환·SQL 실행은 수행하지 않는다.

`0004_text_groundings.sql`은 grounding 위치 discriminator와 text_range를 추가하고, 조건별 CHECK/trigger가 원래 parse bundle의 위치·anchor와 정확한 일치를 요구한다. 기존 PDF의 locus/FP와0001–0003 SQL은 그대로 유지하며 기존 행은 `pdf_region`으로 구분한다. I/grounding/accepted Record/candidate 정리/outbox는 한 transaction으로 반영된다.

## 이미지 참조와 I2K

Markdown의 이미지 문법·URL·alt·사용 위치와 존재하는 reference definition을 보존한다. descriptor의 URL은 parser 정규화 값일 수 있어 `url_origin=parser_normalized`와 원래 Markdown 구간을 함께 둔다. `fetched=false`이며 상대경로나 URL을 자동으로 열거나 내려받지 않는다. HTML img 및 비표준/미해결 이미지 문법은 원문 문자열로 남지만 CommonMark image descriptor를 생성하지 않을 수 있다. 외부 이미지 bytes의 등록·동봉은 아직 구현하지 않았다.

I2K 준비는 canonical I와 모든 text grounding을 재검증해 heading path·source 범위를 전달한다. Markdown은 `source_format=markdown`, `original_pdf_request_supported=false`, `page_count=0`이다. PDF 전용 pages/evidence 조회와 원본 PDF 요청은 명시적으로 거부한다. 모델 전송이나 K 생성은 이번 구현 범위가 아니다.

## 실제 시험 범위

선택한 `docs/schema/DIKW_STORAGE_SCHEMA_V1.md`는54,581 bytes/39,730자/400줄이다. 실제 격리 PostgreSQL18.6/pgvector0.8.6에서 Data1개, D2I실행1개, I24개와 exact text grounding24개를 저장했다. I 길이는 최소273자·중앙1,420.5자·최대4,686자다. 원문 bytes 재조립 SHA, 중복 등록 거부, 동일UUID재시도와 PDF기존6 I/7groundings의 migration 전후 불변을 확인했다. [I별 제목·줄 범위](../../output/t03-markdown/document-attempt-02/INFORMATION.md).
