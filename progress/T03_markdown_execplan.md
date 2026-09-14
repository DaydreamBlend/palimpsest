# Markdown D → D2I → 그룹 I

상태: Markdown source slice COMPLETE, T03 전체 품질 gate와 T04 의미 실행은 미완료, 2026-09-11. 사용자는 이번 작업 중 작성한 큰 Markdown 파일 하나로 실제 D 등록·D2I·I 저장을 시험하도록 요청했다. 테스트 원문은 `docs/schema/DIKW_STORAGE_SCHEMA_V1.md`(54,581 bytes)로 선택했다. 이 문서의 SQL·작업 지시는 source data로만 읽고 실행 권한으로 사용하지 않았다. 원본 문서는 수정하지 않았다.

## 완료 목표

기존 도구 등록으로 raw-byte SHA256 Data를 만들고, Markdown 구조 파서와 결정적 스크립트로 heading 기반 그룹 I를 저장한다. source text의 줄/Unicode 문자/UTF8 byte 범위를 유지하고 코드·표·공백·BOM/CRLF를 재조립할 수 있어야 한다. 코드 fence/인용/list/HTML 안의 #를 문서 최상위 제목으로 취급하지 않는다. 원문 링크·이미지 URL은 참조로 보존하고 자동 접근/실행하지 않는다.

## 확인한 경계와 설계

USER_OVERRIDES, INDEX, DECISION_REGISTER, T03, GROUPED_INFORMATION_STORAGE와 기존 grouped source/I2K/SQL을 확인했다. 이 요청은 Markdown source 변환의 승인이고 PDF MinerU 선택·K 의미 정책·외부 provider 허가를 바꾸지 않는다. provenance용으로 가짜 PDF page/bbox를 만들지 않는다.

기존 source-information-v1/Record/atomic commit을 재사용하고, 새 markdown-source-v1 bundle 및 markdown-groups-v1 algorithm을 사용한다. 위치는 text_range로 명시하고 PDF 위치 필드는 null이다. additive0004 migration에서 grounding discriminator/text_range와 조건별 CHECK/trigger를 추가한다. 기존 PDF fingerprint 반환값과0001–0003 SQL은 변경하지 않는다. Markdown은 page 조회를 명시적으로 거부하고 I2K 입력은 text refs와 원문 그룹 순서를 사용한다.

공식 markdown-it-py의 CommonMark tokenizer와 line maps를 사용한다. raw text는 tokenizer가 정규화한 문자열로 대체하지 않고 원본 bytes에서 정확한 구간을 복사한다. 선택 버전/배포 SHA를 고정해 Docker requirements에 기록한다. 새 모델이나 GPU/OCR 호출은 없다.

## 소유권·구현 순서

1. root가 기존 코드/문서를 output/t03-markdown/baseline에 복사하고 실제 source SHA와 Docker inventory를 기록한다.
2. 독립 agent: 순수 Markdown adapter·그룹 builder/검사/범위와 단위검사. root: dependency pin, DB/migration, domain locus, Runtime/CLI·I2K 연결. schema/shared commit은 root만 편집한다.
3. 실제 새 project PostgreSQL18/pgvector에 migration을 적용하고 원본 파일 도구등록→source compilation→그룹 I 저장/조회→동일ID retry/중복등록 거부/원문재조립 검사를 수행한다. 사용자 live DB는 사용하지 않는다.
4. 기존 PDF 전체 회귀·문서 validator를 실행하고 실패 원인을 보존한다. 결과/사용법과 미지원 범위를 기록하고 테스트용 Docker 자원만 정리한다.

## 필수 검증과 완료 제한

ATX/Setext, fence/indented code/container/HTML false heading, header-only prefix, BOM/CRLF/UTF8/emoji/combining chars, 빈 파일/invalid UTF8, 전체 source 범위1회배정, byte/char/line 변조, 실제 DB trigger, 실패 시 atomic rollback, 단일 Data/UUIDv7 refs·same-request retry·duplicate import 거부. 기존 PDF row·FP/IDs/migrations 및 I2K source-on-demand 회귀를 확인한다. Markdown의 외부 media bytes 수집·렌더링·모델 전달/판단·K 저장과 T03 전체 품질 gate는 이번 범위에 포함하지 않는다.

실행 명령·결과·실패·검토와 남은 일은 아래에 누적한다.

## 구현 및 검토 결과

순수 `markdown_adapter.py`가 pinned CommonMark/token maps와 원본구간 복사를 담당하고, `d2i.py`가 Markdown algorithm을 선택한다. `_locus`는 text-range일 때만 별도 fingerprint 표현을 사용해 PDF의 과거값을 유지한다. Runtime의 `compile_markdown/_attach_markdown`과 공통 `_save_parse`는 원본 Artifact Store의 검증 bytes를 읽고 기존 Record/atomic commit을 재사용한다. CLI `compile markdown`, I2K의 Markdown순서/typed refs/falsePDFrequest와 PDF전용조회거부를 연결했다.

새0004 migration은 locator_type/text_range를 추가하고 PDF위치를nullable로 바꾸되 유형별 CHECK/원실행 bundle trigger가 빈값·잘못된범위를 거부한다. 기존0001–0003 SQL은 변경하지 않았다. 원본문서의 SQL은 데이터였으며 실행하지 않았다. MARKDOWN_PARSER는 markdown-it-py4.2.0/commonmark+table/UTF8/refs-only이고 mdurl0.1.2가 의존한다. 공식PyPI의배포SHA와wheel을대조해 lock에 기록했다.

## 실제 검증과 실패 기록

[실제 명령·로그·생성물](../output/t03-markdown/REPORT.md)에 전체 기록을 보존했다.

1. `pip download --only-binary=:all: --dest output/t03-markdown/dependencies markdown-it-py==4.2.0 mdurl==0.1.2`: exit0. 공식PyPI JSON배포SHA와 실제wheel SHA 일치. host전역install은 없었다.
2. wheel경로를 sys.path에 둔 adapter8tests 통과0.098초. root Markdown/I2K/Information34tests 통과0.125초. 독립검토의 PDF FP4건 differential 및 적대적Markdown4건도 통과했다. 최초module조회 일부경로미발견은 실제파일로 다시 확인했다.
3. `PALIMPSEST_APP_IMAGE=palimpsest-grouped-i:0.2.0`과 `docker compose -p palimpsest-markdown run --rm -T migrate`: exit0, 격리0003생성. `/results/prepare_upgrade.py`: exit0, PDF I6개/grounding7개를 먼저 저장하고 모든이전값·I2K입력을동결했다.
4. `docker build -t palimpsest-markdown:0.2.0 .` 두번 모두 exit0. 최종image로 같은project의 migrate 실행 exit0,0003→0004추가적용. 최종image ID `sha256:f60d107d0448bb1a1d64dbd7323239e01b4881a473fb7157d77afd074d734d90`.
5. 최종image `/results/run_tests.py`: **367tests/failures0/errors0/skipped16**,31.344초,exit0. 신규 실제PG6tests는동시compile·중복등록·원자rollback/retry·SQL범위변조삽입과positivecontrol·원본/canonical범위변조·CLI까지 포함한다.16skip은별도PDFium환경용기존검사이며 OCR/모델평가가아니다.
6. 원문read-only mount로 `/results/test_document.py` 첫실행은Data및24 I저장후조회harness가`information list --data-id`의flag를빠뜨려exit1. 첫스크립트·로그·attempt01출력은보존했다. 앱코드는그대로두고harness만수정한재실행exit0. 같은Data/실행/I를재사용하여Data1/execution1/I24/grounding24/Record24/outbox24/candidate0을확인했다.54,581bytes/39,730chars/400lines가그대로복원됐고SHA는`28659708f26f4e9d71dc80bf917935a5c75a1a6b365c051cdb5cec877b71ddeb`. 실제D2I ID`01a08e9c-db28-7a76-b770-09fc0f791f49`.4.26초는재시도·검증시간이며신규compile latency로확대하지않는다.
7. migration후기존PDF6 I/7groundings의기존모든열과전체I2K입력이동일했다. PDF신규location default도확인했고PDF FP기존형태는그대로다. 새문서일반중복은exit6, 같은요청과compile은동일UUID, PDFpage조회는명시exit4로거부했다.
8. 문서validator exit1: 이전raw/oracleMarkdown12개오류와동일하며새오류0. patch문맥/순서실패2번은부분반영없이재적용했고검사나원본을완화하지않았다.
9. project label과작업전inventory를검증한뒤 `docker compose -p palimpsest-markdown down --volumes` exit0. 테스트2containers/4volumes/1network만정리했고기존자원은모두보존했다. 새image는최종성공본1개이며Compose기본tag도이image로변경했다. `docker compose config --images` 읽기에서선택을확인했다. 테스트DB는정리했으므로기록의UUID는liveDB ID가아니다.

## 변경 파일·남은 범위

신규 adapter/tests/0004 SQL/MARKDOWN_RUNTIME 안내와 실행산출물을 만들었다. 기존 information/canonical_store/d2i/compiler_runtime/cli/page_projection/i2k, requirements.lock/pyproject.toml/compose.yaml, README/INDEX/T03/DIKW_CURRENT/I2K_CONTEXT_POLICY/MODULE_BOUNDARIES/repository_inventory를 갱신했다. source문서·canonical/history·과거SQL은 수정하지 않았다. baseline과변경diff를output폴더에보존한다.

승인을 기다리는 결정은 없다. 이 source변환·저장에는모델/원격provider호출이필요하지않다. UTF8/NUL정책·CommonMark+table범위를명시했으며외부이미지bytes수집·HTML렌더링·미해결/비표준image token·다른인코딩은완료로주장하지않는다. 별도원본PDF요청은Markdown에서지원하지않고I2K는텍스트근거를받는다. T03전체PDF충실성gate와T04 AT06/07/08/20/21/24/28/29/30/41/42/43/44/73/74/82/83 및107/111/112의K 의미/atomic효과검증은이번작업으로완료되지않았다. 다음I2K단계는PDF그룹과Markdown그룹의typedsource refs를사용하면된다.
