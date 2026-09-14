# Markdown D → D2I → I 시험 결과

2026-09-11. 작업 중 작성한 [DIKW_STORAGE_SCHEMA_V1.md](../../docs/schema/DIKW_STORAGE_SCHEMA_V1.md)를 실제 CLI로 등록·변환했다. **Data1개, D2I실행1개, I24개와 text grounding24개**가 생성됐고, I의 본문을 원문 순서대로 연결해 입력 bytes를 정확히 복원했다. [검증 JSON](document-attempt-02/verification.json), [24 I의 제목·줄 범위](document-attempt-02/INFORMATION.md), [전체 I JSON](document-attempt-02/information.json), [사용법](../../docs/implementation/MARKDOWN_RUNTIME.md).

## 실제 생성 결과

| 항목 | 결과 |
|---|---:|
| 원본 파일 | DIKW_STORAGE_SCHEMA_V1.md |
| 원본 bytes / Unicode 문자 / 줄 | 54,581 / 39,730 / 400 |
| Data / D2I 실행 | 1 / 1 |
| I / grounding / D2IRecord / outbox | 각각24 |
| 반영 후 candidate | 0 |
| I 길이 최소 / 중앙 / 최대 | 273 / 1,420.5 / 4,686자 |
| LLM / OCR / 외부 참조 fetch | 모두0 |

Data SHA-256은 `28659708f26f4e9d71dc80bf917935a5c75a1a6b365c051cdb5cec877b71ddeb`, 실제 D2I execution은 `01a08e9c-db28-7a76-b770-09fc0f791f49`였다. [Data 등록 결과](document-attempt-02/data-import.json)와 [D2I 상태/receipt](document-attempt-02/job.json)를 보존했다. 이 ID는 격리 시험 DB의 기록이며 사용자 live DB의 ID라고 제시하지 않는다.

원문은 read-only mount했고 수정하지 않았다. 각 I는 exact byte/char/line 범위를 갖고 원문 구간과 content가 일치했다. [복원 텍스트](document-attempt-02/restored-source.txt)의 SHA도 Data ID와 동일하다. 제목·표·코드·링크·공백을 보존했고, 문서 안의 SQL/작업 지시는 데이터로 취급했다. 원문의 설계 SQL을 DB에 실행하지 않았다. 실제 적용한 migration은 앱 코드의0004 파일뿐이다.

모든 신규 opaque ID는 UUIDv7이며 같은 compile/retry는 같은 I ID를 반환했다. 동일 등록 요청은 원래 Data를 반환하고, 새 요청으로 같은 bytes를 등록하면 `duplicate_data`/exit6이었다. [I2K 준비 입력](document-attempt-02/input.json)은 text ranges와 원문을 보존하고 PDF요청지원false·media_assets빈목록·actual_deliveryfalse다. PDF pages조회는 `pdf_page_view_required`/exit4로 거부됐다. 모델 전달·K 생성은 실행하지 않았다.

## 추가 migration과 PDF 호환성

이전 앱의0003 schema에 PDF I6개·grounding7개를 먼저 실제 저장했다. 새 `0004_text_groundings`를 추가한 후 기존 I의 모든 열 값, 기존 grounding의 모든 이전 열 값, 전체 I2K 입력이 같음을 확인했다. 새 grounding 열의 PDF기본값은 `pdf_region`/text_rangeNULL이다. [업그레이드 검증](document-attempt-02/upgrade-verification.json), [변경 전 기준](legacy-before-upgrade.json).

Markdown grounding은 locator_type=text_range, byte/char 0-based반열림 범위, line1-basedinclusive이며 page/bbox/page_size는 SQL NULL이다. 새 CHECK와 trigger는 typed range와 원래 parse bundle의 정확한 일치를 검사한다.0001–0003 SQL과 PDF fingerprint의 표현은 바꾸지 않았다.

## 검사와 실패 기록

- Markdown adapter 단위8개 통과0.098초. BOM/CRLF/CR/LF/Unicode, ATX/Setext, fence/indented code·quote·list·HTML의 가짜heading, title-only부모/빈형제/빈문서, 외부이미지미fetch, 범위/metadata/hash변조를 검사했다.
- root의 Markdown/I2K/Information 순수34개 통과0.125초. 독립 검토에서 기존 semantic/source text/image FP4건이 baseline과 같고 적대적Markdown4건의 bytes/범위/이미지참조가 보존됨을 추가 확인했다. 이 검토는 순수Python이며 DB평가와 구분한다.
- 최종 Docker 전체 앱 **367tests, failures0/errors0/skipped16**,31.344초,exit0. [기계판독 결과](app-tests.json), [전체 로그](app-tests.log). 신규 Markdown PG검사6개는 실제D등록/저장/동시compile/동일ID/duplicate/atomicrollback/SQL범위변조/PDF조회거부/canonical범위와원본변조/CLI를 포함한다. skipped16은 별도 PDFium native renderer 환경용 기존 검사다.
- 실제 문서 첫 harness는 D와24 I 생성 후 `information list`에 `--data-id`를 누락해 exit1이었다. [첫 로그](document-first-failed.log), [당시 스크립트](test_document-before-cli-fix.py), `document-attempt-01/`의 성공·실패 JSON을 그대로 보존했다. 앱 코드를 바꾸지 않고 harness의 인자를 수정했다. 두 번째 실행은 같은 요청/실행을 재사용해 모든 검증을 통과했다. 검증4.26초는 이 재시도·조회/업그레이드 대조를 포함한 시간이며 최초 신규compile latency로 해석하지 않는다.
- patch문맥/순서가 맞지 않은2회 적용은 파일에 부분 반영되지 않았고 hunk순서를 바로잡아 적용했다. 경로 탐색의 일부 파일미발견은 실제경로로 다시 확인했다. 실행되지 않은 검사를 통과로 기록하지 않았다.

## 구현과 환경

순수 `markdown_adapter.py`가 문법/그룹/원문 범위를 소유하고, `d2i.py`가 algorithm별 검증을 선택한다. Runtime의 `compile_markdown`은 기존 Data/Artifact Store와 parse publication·Record·atomic commit을 재사용한다. `information._locus`와 I2K는 text range를 명시적으로 처리하고 PDF전용조회는 거부한다.

고정 의존성은 markdown-it-py4.2.0, mdurl0.1.2다. 두 wheel SHA를 공식 PyPI metadata와 대조한 [기록](dependencies/verified.json)을 보존하고 requirements.lock에 넣었다. CommonMark token map을 원문 줄 위치에 대응시킬 수 있는 공식API를 사용했다. [공식 API](https://markdown-it-py.readthedocs.io/en/latest/using.html), [PyPI 배포](https://pypi.org/project/markdown-it-py/4.2.0/). 전역 host환경은 수정하지 않았고 단위검사에는 다운로드wheel경로를 사용했다.

실제환경은 PostgreSQL18.6/pgvector0.8.6, Python3.12 Docker다. 아래명령은 저장소root의PowerShell에서 실행했다. source파일은read-only이고 새 model/PDFparser/GPU/외부provider호출은없다.

```powershell
$env:PALIMPSEST_APP_IMAGE='palimpsest-grouped-i:0.2.0'
docker compose -p palimpsest-markdown run --rm -T migrate
docker compose -p palimpsest-markdown run --rm --no-deps -T --volume 'C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/output/t03-markdown:/results' --entrypoint python app -B /results/prepare_upgrade.py
docker build -t palimpsest-markdown:0.2.0 .
$env:PALIMPSEST_APP_IMAGE='palimpsest-markdown:0.2.0'
docker compose -p palimpsest-markdown run --rm -T migrate
docker compose -p palimpsest-markdown run --rm --no-deps -T --volume 'C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/output/t03-markdown:/results' --entrypoint python app -B /results/run_tests.py
docker compose -p palimpsest-markdown run --rm --no-deps -T --volume 'C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/docs/schema/DIKW_STORAGE_SCHEMA_V1.md:/inputs/DIKW_STORAGE_SCHEMA_V1.md:ro' --volume 'C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/output/t03-markdown:/results' --entrypoint python app -B /results/test_document.py
python -X utf8 -B tools/validate_bundle.py --json
```

새 재현에는 과거로그를 덮어쓰지 않을 새output경로를 사용한다. profile의 코드hash가 바뀌면 새 compilation profile이 되는 기존규칙을 유지한다. 같은sourcebytes Data ID는같고 새profile의I는새스냅샷이다.

## 한계와 다음 단계

문서 validator는 이전과 동일한 raw/oracle Markdown12개 오류로 exit1이고 추가 오류는0이다. [검사 결과](document-validation.json). 원본 문서나 과거 raw의 문법을 수정해 검사를 통과시킨 것이 아니다.

최종 image는 `palimpsest-markdown:0.2.0`, ID `sha256:f60d107d0448bb1a1d64dbd7323239e01b4881a473fb7157d77afd074d734d90`이며 Compose기본으로 선택된다. [소유권 확인](cleanup-preflight.json) 후 `docker compose -p palimpsest-markdown down --volumes`로 이번 테스트 컨테이너2개·볼륨4개·네트워크1개를 정리했다. [최종 확인](cleanup-verification.json)에서 기존 컨테이너/이미지/볼륨은 모두 보존됐고 신규image는 성공본1개만 남았다. 시험 DB는 정리했으며 source와 JSON/I출력·검증기록은 이 폴더에 남는다.

지원범위는 UTF-8 CommonMark+table의 원문 저장이다. Unicode정규화/개행치환을 하지 않고 비UTF8/NUL은명시거부한다. 외부이미지/문서내용은자동fetch하지않는다. CommonMark 이미지token은refs-only metadata를만들지만 HTML img/미해결·비표준이미지문법은원문에만남을수있다. HTML렌더링·외부media첨부·정적사이트발행을 구현한것은아니다.

전체I는 구조검증 결과이며 문서의SQL설계나기술주장이현재사실이라는의미승인이아니다. T03전체품질gate와 T04모델전달/판단·K/Revision/검색저장은후속작업으로유지한다.
