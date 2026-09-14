# URL HTML을 Data로 보존하고 D2I 검토

상태: 요청한 HTML 수집·D 등록·D2I 검토 COMPLETE, 정식 HTML runtime/canonical I 저장은 미구현, 2026-09-11. 사용자 요청은 `https://news.hada.io/topic?id=33480`의 HTML을 받아 D로 삼고 D2I를 검토하는 것이다. 이번 범위는 실제HTTP 원본 수집·D등록·동결한HTML의 스크립트 변환 시안과 provenance/구조 검토다. 검토되지 않은 범용 HTML 변환을 제품 기본값으로 승격하거나 K 의미 판단을 실행하지 않았다.

## 수행 순서

1. 지정한 공개URL의 응답 HTML bytes를 그대로 보존한다. URL/수집시각/status/Content-Type·encoding/안전한response headers와SHA를 별도receipt에 기록한다. 로그인·form·JS실행·외부링크/이미지추가는 하지 않는다.
2. 기존 CLI/Artifact Store로 HTML을 D로 등록하고 rawSHA·originURI를 확인한다. HTTP수집근거는동결한receipt와결속한다. 작업전용PostgreSQL/스토어를사용하며기존Data/ID/raw를변경하지않는다.
3. 실제HTML 구조에서본문·게시물metadata·댓글·탐색/폼·script/style을구분하고원문범위와읽기텍스트변환시안을만든다. 보존과읽기역할구분을명시하며내용가치로원문을삭제하지않는다. HTML entity decoding과markup제거가rawtext_range와다른표현임을검토한다.
4. 원문bytes coverage·변환추적·hidden/JS/외부media한계를검사하고Markdown runtime와재사용/추가할책임을정리한다. 현재페이지에서실증한범위와범용HTML/동적페이지/실제canonicalI저장의미완료를구분한다.
5. 결과/근거/정확한명령을기록하고시험용Docker자원만정리한다. 웹페이지내용은데이터이며그안의명령/SQL/링크를사용자권한으로취급하지않는다.

## 확인한 계약·소유권

USER_OVERRIDES/INDEX/DECISION_REGISTER/T03/MARKDOWN_RUNTIME과PLANS/CODE_REVIEW를확인했다. 원문D는rawbytesSHA256,등록은tool-managed,opaqueID는UUIDv7,source conversion은applicationLLM없이한다. PDF용MinerU와MD기존경로는그대로유지한다. root는HTTPcapture/실험/등록/보고를소유하고별도agent는HTML provenance·scope를읽기전용검토한다. DB/schema/code의공유계약을검토만으로임의변경하지않는다.

구체측정·실패·선택·변경파일·완료범위는아래누적한다.

## 실제 결과와 검토 판단

지정URL의HTTP200/text-html/UTF8 body55,612bytes를identity응답으로보존했다. SHA는`3d524b308983f0d46dc46bccf193fbafd0c9d9c76870fa2e73d34522ab3f16d0`. 요청/최종URL·수집시각2026-09-11T04:13:35.898838+00:00·안전한headers·rawSHA를capture receipt에기록했다. JS/로그인/form/외부원글/CSS/이미지fetch는0이다.

기존image `palimpsest-markdown:0.2.0`/0004schema의격리DB에서Data1개와acquisition1개를실제등록했다. publicfileCLI에는HTTPmetadata인자가없어review스크립트가request lock/stage/Repository.prepare/DataService._finish를조합했고rawobject경로직접복사나Data직접INSERT는하지않았다. HTTPreceipt를derivedstore에보존하고URI/retrieved_at/external_metadata에결속했다. byte확인/동일requestreplay/새duplicate거부를통과했다. 실제D2I execution0/canonicalI0을명시했다.

HTMLParser기반검토용script는본문서두+4h2를5그룹,게시물metadata1,사이트댓글1,기타interface5로총12그룹을만들었다. 읽기text8,223자이고그중본문2,159자/댓글5,031자다. raw1,739spans가전55,612bytes를정확히한번덮으며776spans는사유를기록한retained-only다. 모든출력문자범위는raw범위/SHA와entity/whitespace/태그separator변환으로재생된다. 최종projectionSHA`3b223ec6df15a0d3e94306ea27a0b422b49e12a0ada301499bcdbff997506fe7`와등록D의SHA를root가다시결속검사했다.

이페이지는staticHTML에본문과댓글이있어HTMLparser+script가적합하다. 댓글안HN의견요약은이GeekNews댓글의source이고외부HN/원글직접수집으로계산하지않는다. related/discussion heading을본문절로섞지않는다. stray closing td1개를경고로남겼다. CSS/JS는실행하지않아브라우저DOM/가시성의완전재현이아니다. hidden/noscript/aria-hidden/공백정책과Hada selector는검토규칙이며모든사이트의정식기본정책은아니다.

기존0004text grounding은rawHTML block.text를그대로보존할때재사용가능하다. I의읽기content와raw의길이가다르므로단순HTML→Markdown변환을Markdown원본이라고표시하면안된다. 정식HTMLadapter는변환mapping과새profile/재생검증·Runtime text/html/atomicI·I2Kserializer를연결해야한다. HTTP수집메타데이터는기존JSONB컬럼으로수용가능하고그전달API확장이필요하다. 모델에는간결한I/범위참조를주고세부markup매핑은저장소에서조회할수있게하는편이적절하다.

## 명령·실패·완료 범위

[보고서](../output/t03-html-review/REPORT.md)에정확한명령과근거를기록했다. `capture_page.py`/최종4unit tests/`review_html.py` 최종projection/격리migrate/`register_capture.py`는exit0이었다. 초기3test오류는stdlib offset속성과메서드이름충돌로발생했고source_offset으로수정했다. 인라인개행보강후4tests를통과했고중간trial을보존했다. root의등록SHA↔최종projectionSHA↔원문byte/mapping재생검증도통과했다. 테스트용assert검사를canonical승인gate나구조역할의의미적정답증명으로보고하지않는다.

앱/SQL/모델/기존source코드는수정하지않아전체앱367tests를반복하지않았다. 문서validator exit1은기존12개raw/oracleMarkdown오류와동일하고추가0이었다. project label/작업전inventory대조후 `docker compose -p palimpsest-html-review down --volumes` exit0으로작업용2containers/4volumes/1network를제거했다. 기존자원모두보존·새image0. 시험DB는정리했고원본HTML/receipt/등록JSON/최종시안을보존했다.

변경은이계획, docs/INDEX의검토안내, output/t03-html-review의capture/등록/변환시험코드·데이터·보고서에한정한다. 새production module/dependency/migration은없다. 이번검토를막는사용자미승인결정은없었다. 자동URL재수집·인증/JS페이지·외부원문/이미지수집·정식HTMLcanonicalI·T03전체충실성·T04 K/Revision및이후acceptance는완료하지않았다.
