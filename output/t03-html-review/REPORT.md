# HTML 수집·Data 등록·D2I 검토 결과

2026-09-11. [지정한 GeekNews 페이지](https://news.hada.io/topic?id=33480)의 HTML을 받아 **원본 D를 실제 등록하고, D2I의 읽기 그룹·원문 매핑 시안을 검증했다.** 이 페이지는 서버 응답에 본문과 사이트 댓글이 포함되어 있어 browser/JS/MinerU/LLM 없이 정적 HTML 파서와 스크립트를 적용할 수 있다. 정식 HTML D2I Runtime과 canonical I 저장은 아직 구현하지 않았다. [통합 검증](verification.json), [D 등록 결과](registration-verification.json), [읽기 그룹 요약](trial-final/group-summary.json).

## 실제 수집과 등록

| 항목 | 결과 |
|---|---|
| 요청·최종 URL | https://news.hada.io/topic?id=33480 |
| HTTP | 200, text/html; charset=UTF-8 |
| 수집 시각 | 2026-09-11 04:13:35 UTC / 13:13:35 KST |
| HTML bytes | 55,612 |
| Data SHA-256 | 3d524b308983f0d46dc46bccf193fbafd0c9d9c76870fa2e73d34522ab3f16d0 |
| 실제 Data / acquisition | 1 / 1 |
| 실제 D2I execution / canonical I | 0 / 0 — 이번에는 변환 시안 검토 |

수집은 지정된 공개 URL의 identity 응답 body만 읽었다. credentials·cookies를 공급하거나 JS/form을 실행하지 않았고 외부 원글·이미지·CSS·script 파일을 추가 조회하지 않았다. status/Content-Type/선언 charset·안전한 header·요청 및 최종 URL·수집 시각을 [receipt](capture/receipt.json)에 기록했다. HTML bytes는 디코딩·재작성하지 않은 상태로 SHA를 계산했다.

검토용 등록 스크립트는 기존 Artifact Store의 request lock/stage/publish, Repository.prepare와 DataService의 commit/duplicate/replay 경로를 재사용했다. Data row에 직접 INSERT하거나 canonical object 경로에 수동으로 파일을 넣지 않았다. 기존 schema의 acquisition.retrieved_at/external_metadata에 HTTP receipt와 별도 보존된 receipt artifact의 SHA/경로를 연결했다. [저장된 Data·acquisition](registered-data.json), [등록 코드](register_capture.py).

현재 public file-import CLI는 HTTP metadata 인자를 제공하지 않아 위 부분은 실험용 application composition이다. 정식 URL 수집 CLI/API가 완성됐다는 뜻은 아니다. 같은 요청의 replay, 동일 bytes의 새로운 등록 요청 거부, 원본/receipt의 Artifact Store byte 일치를 실제 격리 PostgreSQL에서 확인했다.

## D2I 시안

| 읽기 그룹 | 개수 | 읽기 문자 수 |
|---|---:|---:|
| 본문 서두+4개 소절 | 5 | 2,159 |
| 게시물 제목·metadata | 1 | 100 |
| 사이트 댓글 | 1 | 5,031 |
| navigation/forms/related/footer/기타 interface | 5 | 933 |
| 합계 | **12** | **8,223** |

본문은 `section#topic_contents`와 그 안의 h2로, 댓글은 `.comment_row`의 원문 경계로 나누었다. 이는 동결한 Hada 페이지를 검토하는 selector 규칙이며 범용사이트의 확정 기본값이 아니다. 전체 heading만 따라가면 관련 글과 토론 제목이 본문에 섞일 수 있으므로 구조 역할을 먼저 구분했다.

이 D는 GeekNews snapshot이다. 본문의 외부 원글 링크는 별도 출처이며 수집하지 않았다. 사이트 댓글1개 안에는 다른 커뮤니티의 의견을 요약한 내용이 있지만, 그 내용을 여러 외부 원문의 직접 수집이나 독립 acquisition으로 세지 않았다. [대상 페이지의 실제 구조](https://news.hada.io/topic?id=33480).

원문55,612 bytes를1,739개 source span ledger로 정확히 한 번 덮었다. 이것은 I1,739개가 아니라 위치 검증용 구간이다. 776개 span은 head/script/style/HTML comment/숨김정책·markup 등으로 읽기 문자열에 넣지 않고 원본과 제외 이유를 보존했다. HTML원본은 모두 남는다. 코드·메타데이터·숨김영역을 읽기에서 제외하는 기준은 검토용 구조 정책이며 내용가치 판정이 아니다.

출력에는 source byte/char 범위·원문SHA·변환종류·출력 문자 범위/SHA를 결속했다. entity는 해석하고 pre 내부의 원문 공백은 유지하며 나머지 ASCII whitespace는 한 칸으로 축약한다. 태그가 만드는 줄바꿈/표셀 탭은 derived separator로 표시한다. 저장된 원문과 규칙으로 출력 text를 다시 계산해 일치함을 확인했다. [최종 매핑 검증](trial-final/verification.json).

본문을 직접 Markdown으로 바꿔 기존 Markdown source라고 기록하는 방식은 적절하지 않다. 예를 들어 raw HTML의 entity 길이는 해석된 문자의 길이와 다르다. 새 HTML adapter는 **raw HTML source block+raw text_range/anchor**를 유지하고, 읽기 content와의 변환 mapping을 별도로 보존해야 한다. 기존0004 SQL은 이 raw locus를 저장할 수 있으므로 현재 검토로는 새 SQL이 필수라고 보지 않는다. 별도 html parser/assembly profile과 Runtime 검증·I2K 직렬화 연결은 필요하다.

## 검증 범위와 남은 문제

- 정적파서 시험4개 통과: entity/inline공백/pre/code/br/list/table, script·hidden, stray closing tag, EOF미종결, source/output변조 검사. 최초시험3개오류는 stdlib 내부offset 속성과 같은 이름의메서드를 만든 충돌이었고 source_offset으로 바꾼 뒤 통과했다. 이후 인라인줄바꿈의단어연결을보강하고 최종4개를통과했다. 중간 trial 산출물도보존했다.
- 실제raw의전byte coverage, 매핑text재생, 반복동일성 통과. root가최종projection의sourceSHA와실제등록D SHA를다시대조했다. 최종projectionSHA는 `3b223ec6df15a0d3e94306ea27a0b422b49e12a0ada301499bcdbff997506fe7`.
- 이 페이지에는 짝이 없는 closing td1개가 있었다. token stack의경고로남겼으며브라우저의DOM복구와같다는주장은하지않는다. 주된원문근거는rawSHA/byte범위다.
- CSS를평가하지않으므로 결과는 static readable text다. aria-hidden/noscript/inlinehidden 처리와desktop/mobile중복을모든브라우저의정확한가시성으로해석하지않는다. JS로추가로생성되는내용까지수집했다는주장도없다.
- URL/img/script/link140개참조를기록했지만fetch0이다. 실제img태그1개는src없는숨김UI이며article image를수집했다고표시하지않았다. 외부원문·이미지는별도승인범위와Data등록으로다뤄야한다.
- 이검토의assert/매핑검사는canonical승인gate가아니다. 정식HTML컴파일에서는동결한profile/입력으로분할·제외·변환을다시계산해검증해야하며, 역할분류의의미적정답을JSON/hash만으로증명하지않는다.
- 동일URL도투표수·시간·댓글·페이지구성변경으로bytes가달라질수있다. Data ID는URL이아닌bytesSHA이므로다른snapshot은다른D가된다. 같은bytes의재등록은기존중복정책을따른다. 자동재수집/최신본연결은이번범위가아니다.

## 권고하는 다음 구현

1. 실제capture결과를acquisition에넘기는HTTP등록서비스/CLI를추가한다. 원본응답과charset/encoding/redirect/수집정보의결속을명시하고본문추출text로Data ID를대체하지않는다.
2. 별도HTMLsource adapter와grouped assembly를추가한다. rawgroup/원문span은보존하고본문·댓글·UI/metadata역할과entity/markup변환mapping을기록한다. 검토용사이트selector는명시profile로분리한다.
3. Runtime의text/html허용·검증·atomic I저장과I2K입력준비를연결한다. 세부raw mapping은저장소에두고모델에는읽기text와간결한I/범위참조를제공한다. 원문확인은등록HTML snapshot으로수행하고외부원글조회와구분한다.

이번 단일snapshot 검토를 막는 중대 미승인 결정은 없었다. production HTML기본 정책·실제canonicalI·K작업까지완료했다고보고하지않는다.

## 실행 명령

문서 validator는 기존 raw/oracleMarkdown12개오류로exit1이며새오류0이다. [검사결과](document-validation.json). [정리전소유권확인](cleanup-preflight.json) 후검토용컨테이너2개·볼륨4개·네트워크1개를정리했다. [최종확인](cleanup-verification.json)에서기존Docker자원은모두보존됐고새이미지는0개다. 등록시험DB는정리했으므로등록UUID는시험기록이며liveDB ID가아니다. HTML과receipt·등록JSON·projection은이폴더에보존했다.

호스트Python은기존Codex의3.12.14다. 앱이미지 `palimpsest-markdown:0.2.0`와기존0004 schema를재사용했고 새앱코드/SQL/의존성/image는만들지않았다.

```text
python -X utf8 -B output/t03-html-review/capture_page.py
python -X utf8 -B -m unittest discover -s output/t03-html-review -p test_review_html.py -v
python -X utf8 -B output/t03-html-review/review_html.py output/t03-html-review/capture/response.html output/t03-html-review/trial-final
docker compose -p palimpsest-html-review run --rm -T migrate
docker compose -p palimpsest-html-review run --rm --no-deps -T --volume C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/output/t03-html-review/capture:/capture:ro --volume C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/output/t03-html-review:/results --entrypoint python app -B /results/register_capture.py
```

수집/최종시험/시안생성/migrate/등록은exit0이었다. 첫stdllib메서드명충돌을제외한새실패는없었다. 변환시안은exclusive-create이므로재현은새출력경로를사용한다. 앱코드를변경하지않아전체앱367tests를반복실행하지않았다. 실제DB검사는D등록·metadata결속·replay·duplicate·bytes에한정한다.
