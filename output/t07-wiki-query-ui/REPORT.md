# Wiki 검색·근거 답변 구현과 UI 재사용 조사

2026-09-12. **현재 Wiki/K 검색 → 근거 I 읽기 → 전체 I 의미 검색 → 요청한 원본 페이지 확인 → 구조화 답변·독립검증**을 Python/Docker CLI로 연결했다. 동시에 Obsidian+Quartz, Wiki.js, Outline, BookStack의 공식 자료를 조사했다. UI를 설치·배포하거나 논문을 인터넷에 게시하지 않았다.

## 구현과 실제 저장

| 항목 | 실제 결과 |
|---|---:|
| 입력 논문 / 선택된 전체 I | 3 / 87 |
| 검색 문서 | 154: Wiki 항목 37 + 관련 current K 30 + I 87 |
| BGE-M3 검색 창 / 차원 | 261 / 1024 |
| 실제 query | 6 |
| 최종 answered / needs_review / needs_attention | 4 / 1 / 1 |
| 실제 Terra 호출 | 23: Generator 16 + Validator 7 |
| 이번 D2I 호출 / canonical D/I/K/W/P 변경 | 0 / 0 |

기존 논문·주제 페이지는 3/22, snapshot 27개다. 이번 검색의 K는 현재 Wiki가 선택한 source I에 grounding이 있는 accepted/current K이며 알려진 검토 필요 Revision을 제외했다. 모든 역사 K/KEdge를 대상으로 하는 전역 graph RAG를 완료했다는 뜻은 아니다.

모델은 `BAAI/bge-m3` revision `5617a9f61b028005a4858fdac845db406aefb181`이다. 필요한 공개 파일 7개·2,295,415,758 bytes를 별도 로컬 폴더에 저장하고 공식 hash를 검증했다. 기존 다른 모델은 보존했다. BGE dense cosine으로 후보를 검색하고 **같은 모델의 ColBERT token late-interaction**으로 재정렬한다. 전용 bge-reranker나 dense score로 재정렬을 대체하지 않았다.

I 87개 가운데 **49개는 원문 text, 38개는 image-only I의 보존 제목과 명시적 descriptor**로 색인됐다. 38개 이미지의 시각적 의미를 BGE가 embedding한 것은 아니다. 이미지 자체는 I/media·원문 artifact로 보존하고, 선택된 I를 모델에 줄 때 exact 이미지 bytes를 첨부한다. 긴 I는 tokenizer의 512-token/64-token overlap 검색 projection으로 나누며 모든 원래 문자를 덮는다. canonical I의 저장 단위나 원문을 바꾸지 않았다.

실제 index ID는 `01a095c9-16b1-74ef-8660-7ac02483e46e`, Wiki ID는 `01a0941f-90b3-792b-bd4b-a3e83c18eaeb`, 결속된 Wiki import는 `01a0944e-69f8-73a5-9454-baa63e93b534`다. PostgreSQL 18.6 / pgvector 0.8.6의 기존 격리 실험 DB `palimpsest_wiki_pg`에 additive `0010_wiki_retrieval`을 적용했다. 원본 source DB에 migration하지 않았다.

## 실제 질문 결과

아래는 작은 기능 시험의 결과이며 무인 답변 정확도 benchmark가 아니다. 수정·원문 추가 요청·독립 검토를 포함한다. [모든 query/round/실제 receipt 집계](trial-summary.json), [독립 의미 검토](SEMANTIC_REVIEW.md)를 함께 읽는다.

| 질문 | 최종 상태 | 관찰과 한계 |
|---|---|---|
| SuperMApo의 마우스·사람 제조 방법 | answered, round 0 | 종·배지·세포 비율·주요 시간을 구분하고 I 2개/인용 3개로 답했다. 논문 보고로 귀속했다. 마우스 대식세포의 사전 RPMI 6시간 단계를 본문 요약에서 생략했으므로 완전한 실행 protocol이라고 해석하지 않는다. |
| BMDC 배양·처리 조건 | needs_attention, round 4 | 첫 답변의 mouse strain 인용이 부족해 Validator가 보류했다. 후속 원본 확인 중 미등록 SI Appendix의 상세 조건을 같은 본문 p9에서 반복 요청해 새 근거가 없었다. 모순된 answered/unresolved 응답도 구조적으로 거부·보존했다. 부족한 농도·기간을 추정해 확정하지 않았다. |
| Test_Paper의 0.22 μm 필터 lot 번호 | answered, round 2 | 처음 번호를 날조하지는 않았지만 일부 I만으로 전논문 부재를 단정했고 Validator도 놓쳤다. 독립 검토 지적·prompt 보강·원본 재확인 후 “확인한 방법 근거에서는 lot 번호를 알 수 없다”는 범위로 수정했다. 이전 accepted 결과와 수정 이유를 유지했다. |
| Test_Paper 원본 p13의 RPMI/MEM·기간·비율 | answered, round 1 | 모델이 원본을 요청했고 등록 PDF bytes를 로컬 검증한 뒤 보존 p13 이미지를 전달했다. 새 Generator와 Validator가 그 이미지 hash를 receipt에 기록하고 해당 조건을 확인했다. |
| Test_Paper 통계 검정·소프트웨어·반복측정 | needs_review, round 0 | GraphPad와 일반 검정의 근거는 맞았으나 Figure 6H/반복측정 주장에 필요한 캡션 부분이 선택 인용에서 빠졌다. Validator가 답변 전체를 보류했다. |
| Clarke 연구비 지원 기관·grant 번호 | answered, round 4 | 초기 모델이 p14/p13을 추측해 읽고도 못 찾았다. I corpus 검색을 우선하도록 보완한 후 BGE 검색에서 실제 ACKNOWLEDGMENTS I를 찾아 p12의 정확한 지원기관·grant 번호를 인용했다. 실제 `needs_information → embedding → pgvector → ColBERT → I → 답변/검증` 경로를 수행했다. |

바로 읽을 수 있는 최종 출력:

- [SuperMApo 방법 요약](query-store/queries/01a095c9-16c0-7d73-bfc8-cca1f9843805/rounds/0/answer.md)
- [원본 p13 확인 답변](query-store/queries/01a095d4-ca43-765d-bd0e-bce13681b0ad/rounds/1/answer.md)
- [범위를 한정한 lot 확인 답변](query-store/queries/01a095d4-ca43-7639-a5a6-c2c66264dbc3/rounds/2/answer.md)
- [전체 I 검색으로 찾은 Clarke 지원 정보](query-store/queries/01a095e4-e535-7c56-8c9b-3bc3d0309f8b/rounds/4/answer.md)
- [통계 답변 보류 표시](query-store/queries/01a095db-a272-798e-94e4-a8b7ba549d50/rounds/0/answer.md)

이 결과는 Validator도 의미 오류를 놓칠 수 있음을 보여준다. 정확한 I·원문 위치·실제 전달 기록·별도 검토와 이전 답변을 보존하는 구조가 필요한 이유이며, 구조화 JSON만으로 의미적 결정론이나 완전한 정확성이 증명된 것은 아니다.

## 보존·검증

[독립 PostgreSQL 검사](preservation.md)에서 이전 0009 기준의 **45개 테이블·6,148행 전체 컬럼 hash가 불변**임을 확인했다. 기존 migration 9개 행도 적용시각까지 같고 0010 기록만 추가됐다. 새 검색 표는 index 1개/chunk 261개다. 문서별 무누락 coverage·정확 Unicode substring SHA·I/Data/source 대응 오류는 0개이고 모든 vector는 1024차원, norm은 0.9999999100–1.0000000802다. [기계판독 검사](preservation.json).

최종 앱 suite는 **643개, 627 pass / 16 skip, 123.718초, exit 0**이다. [최종 로그](app-tests-final-qa.log). 16 skip은 기존 native PDF 환경 조건이며 새로운 query 실패를 숨긴 skip이 아니다. 앞선 637/641개 실행도 성공했고 이후 실물에서 필요해진 변경을 추가한 뒤 최종 suite를 다시 실행했다.

주요 검사:

- 실제 PG retrieval 7개: source 소유·현재 상태·index replay·layer 검색·old Revision/history·profile·immutable coverage. SQL overlap control 및 9개 부정 사례. [로그](retrieval-db-tests.log).
- BGE pure 8개와 실제 GPU smoke: 한글·그리스 문자를 포함한 12,604자 입력의 전체 coverage, dense L2, BMDC 관련 문장의 ColBERT score. 합성 문장의 관련성 smoke를 일반 품질 수치로 확대하지 않는다. [worker 결과](../t07-retrieval-worker/).
- strict query pure 15개, 실제 Linux 파일·lock을 사용하는 Runtime fake 21개: I/source ref 위조, 잘못된 profile·nonfinite rerank, proposal/request/question/소유 변조, exact physical image 전달, Validator 독립성, source history 선택, 실패·재검토·동결 정책·pause 이력.
- 실제 논문 외부 호출과 원본 이미지 확인은 위 6개 query의 별도 실험이다. fake tests를 실제 모델 판정으로 보고하지 않는다.

실물에서 발견한 구현 문제인 read-only transaction의 K shared lock 충돌, grounding 컬럼명, image-only I의 검색 표현, 원래 source execution 선택, model request/input/실제 첨부 결속을 수정했다. 과거 원문/ID/FP를 고치지 않고 새 모듈·현재 query 작업에 해결했다. 모델의 잘못된 상태 조합은 응답을 고쳐 받아들이지 않고 실패 원문과 오류를 저장했다.

## 실행 환경·명령

앱 image `palimpsest-query:0.8.0`:

```text
sha256:35afae55d6a108884269462e66757ce32d0d77b533bf68d9e1b0b761fe0c21c7
```

BGE worker `palimpsest-retrieval-bge:0.1.0`:

```text
sha256:1d54d66b2dacfc56901aa939941ea3c51e4ddc5139671d2802a2759a770f985b
```

앱에 새 ML pip dependency를 추가하지 않았다. 별도 BGE image는 보존된 MinerU Hybrid ML runtime의 torch/transformers를 재사용하고 parser를 실행하지 않는다. GPU inference는 네트워크 없이, repo/model은 read-only mount로 실행했다. CPU 선택 코드가 있지만 CPU 실물 추론은 이번에 검사하지 않았다. 배포용 exact base/model/profile와 명령은 [BGE worker 안내](../../deploy/retrieval/README.md)에 있다.

```powershell
docker build --tag palimpsest-query:0.8.0 .
docker build --pull=false -t palimpsest-retrieval-bge:0.1.0 deploy/retrieval
$env:PALIMPSEST_APP_IMAGE='palimpsest-query:0.8.0'
docker compose -p palimpsest-multi-checks run --rm --no-deps -T migrate db migrate --database-name palimpsest_wiki_pg --json
docker compose -p palimpsest-multi-checks run --rm --no-deps -T test
python tools/ask_wiki.py --directory output/t07-wiki-query-ui --project palimpsest-multi-checks --database-name palimpsest_wiki_pg --artifact-volume palimpsest-knowledge_artifacts --model-directory .local/models/bge-m3-5617a9f61b028005a4858fdac845db406aefb181 --index-id 01a095c9-16b1-74ef-8660-7ac02483e46e --request-id 01a095c9-16c0-7d73-bfc8-cca1f9843805 --question "SuperMApo를 어떻게 만들었지? 논문에 보고된 마우스와 사람 제조 방법을 구분해서 알려줘." --codex <approved-codex-executable> --allow-model-calls
```

위 예시의 Python 실행에는 실제로 bundled Python의 `-X utf8 -B`를 사용했다. 개별 모든 Docker/embedding/OAuth/CLI argv·exit/stdout/stderr는 `controller/<query-id>/*.json`에 남아 있으며 secrets를 출력하지 않았다. full build와 tests의 로그도 보존했다. [전체 명령별 사용 계약](../../docs/interfaces/WIKI_QUERY.md).

23개 실제 호출의 provider-reported usage 합은 input 3,293,151 tokens(그 안의 cached input 17,664), output 10,035다. 이는 receipt에 보고된 합이며 금액이나 새 context 길이 보증으로 환산하지 않았다. 선택 I의 이미지·provenance를 Generator/Validator에 전달하는 현재 경로의 입력량과 cold worker latency는 후속 최적화 대상이다. 실행한 source inspection에서 native PDF model delivery는 0회이며 실제로는 exact 원본 page image를 보냈다.

새 일회용 Docker app/test/migrate/embedding 컨테이너는 `--rm`으로 정리됐고 최종 확인에서 dangling image는 없었다. 기존 DB 컨테이너·volume·성공한 이전 이미지와 원문은 보존했다. Git 저장소가 아니므로 Git diff/commit 검사를 했다고 주장하지 않는다.

## UI 조사 결론

**첫 읽기 UI는 Quartz를 우선 검증하고, 브라우저 협업·권한·편집이 먼저 필요하면 Wiki.js를 선택하는 안을 권고한다.** 이 판단은 현재 Palimpsest가 fixed Markdown을 생성하는 구조에 근거한다. 실제 비교 설치 결과가 아니다.

- Quartz는 현재 공식 v5 문서에서 Markdown 기반 사이트, Obsidian 호환, 검색·backlinks·문서 graph·수식 등을 제공한다. 기본 UI의 상당 부분을 재사용할 수 있다. 한글 토큰화는 공식 지원이지만 우리 문서의 실제 품질은 아직 검사하지 않았다. [공식 기능](https://quartz.jzhao.xyz/), [검색](https://quartz.jzhao.xyz/features/full-text-search).
- Wiki.js는 PostgreSQL·GraphQL·문서 history·권한을 제공해 온라인 편집형 서비스에 적합한 후보다. 외부 page ID와 Palimpsest page/snapshot ID를 매핑하는 연결이 필요하다. [공식 API](https://docs.requarks.io/dev/api), [stable schema](https://raw.githubusercontent.com/requarks/wiki/v2.5.314/server/graph/schemas/page.graphql).
- Obsidian은 선택적인 개인 입력/열람 클라이언트로 두는 편이 맞다. 서버 자동 갱신에 앱을 필수로 만들 필요는 없다. [CLI](https://obsidian.md/help/cli), [Headless](https://obsidian.md/help/headless).
- Outline은 협업·자동 backlinks가 강점이며 현재 BSL 사용 조건을 따로 봐야 한다. BookStack은 책·매뉴얼형 구조에 적합하지만 MySQL/MariaDB 운영이 추가된다. [Outline backlinks](https://docs.getoutline.com/s/guide/doc/backlinks-f9YSmlNSkr), [license](https://raw.githubusercontent.com/outline/outline/main/LICENSE), [BookStack 요구사항](https://www.bookstackapp.com/docs/admin/installation/).

세부 버전·라이선스·설치 및 provenance 경계는 [통합 권고](../../docs/implementation/WIKI_UI_INTEGRATION.md), [Quartz/Obsidian 조사](quartz-obsidian-research.md), [Wiki.js 등 조사](wiki-platform-research.md)에 있다. Quartz v5는 전환 직후이므로 실제 채택 시 exact commit/lock/plugins와 현재 25개 페이지의 호환 검사가 필요하다.

어느 UI도 exact KRevision·I/D provenance·구조화 답변 검증을 자동으로 대신하지 않는다. Palimpsest가 데이터와 판정을 관리하고 UI는 재생성 가능한 문서 화면·검색답변 패널을 제공하도록 연결한다. 문서 링크 graph와 N2E semantic Edge도 구분한다.

## 남은 범위와 검토 상태

6개 질문의 최종 상태 4 answered/2 보류를 정확도 66.7%로 부르지 않는다. 질문 선택·수정·수동 독립검토를 포함하고 검증기 자체의 오류도 관찰했다. BMDC의 미등록 supplement와 통계 답변의 불충분한 citation은 이번 데이터로 성공 처리하지 않았다. I-only 이미지의 visual semantic search, 모든 역사 K/usable effective KEdge RAG, incremental index, 장기 worker/API latency 개선, formal K2W/W/P, GUI·crawler·공개 배포와 전체 T08/T11/T12는 별도로 남는다.

처음 작성한 개인 실험처럼 보이는 합성 negative 질문은 자동 승인 검토가 사적 데이터 전송으로 해석해 거절했다. 해당 호출은 실행하지 않았고, 실제 개인 날짜·실험·수율 기록은 전송하지 않았다. 공개 논문의 lot 번호 질문으로 범위를 바꿔 승인 후 실행했다. 현재 사용자 승인을 기다리는 차단은 없다.

문서 bundle 검사는 `python -X utf8 -B tools/validate_bundle.py`를 실행해 **exit 1, 기존 raw Markdown 오류 12개**를 확인했다. 새 문서 오류는 추가되지 않았다. 원본 parser 산출물을 고쳐 검사 결과를 맞추지 않았다. [문서 validator 로그](document-validation.log). 이전 Windows 환경에서 실패가 기록된 전체 tools 문서 mutation suite는 이번에 다시 실행하지 않았으며 앱 643개 검사와 구분한다.

주요 변경 파일은 `wiki_retrieval.py`, `bge_retrieval.py`, `wiki_query.py`, `wiki_query_runtime.py`, additive `0010_wiki_retrieval.sql`, CLI·migration 목록·앱 version, `run_wiki_embeddings.py`, `ask_wiki.py`, `deploy/retrieval`와 네 focused test 모듈이다. README/AGENTS/INDEX/DECISION_REGISTER/MODULE_BOUNDARIES/Wiki DB 후속 안내 및 새 query/UI 문서·실행 계획을 함께 갱신했다. 기존 canonical/source 문서 snapshot과 과거 migrations를 수정하지 않았다.
