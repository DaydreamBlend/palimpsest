# Script draft + bounded Qwen3.5-9B review

2026-09-10 사용자 승인: 스크립트로 먼저 문맥을 나누고 9B로 재검증하는 방식을 Test_Paper에서 실제 시험한다. 기존 Qwen3.5-9B Q8_0 파일과 llama.cpp b10380을 재사용한다. 이전 전체 논문 grouping 실험은 불변 비교 기록이다.

## 범위와 근거

AGENTS, USER_OVERRIDES, INDEX, DECISION_REGISTER, T03/T04, PLANS, CODE_REVIEW, I2K_CONTEXT_POLICY를 읽었다. U11과 현재 MinerU image200 기본값을 유지한다. 이 작업은 I2K 입력용 비canonical projection이며 D2I 의미 판단이나 K 생성이 아니다. 원문229 I, 원본 PDF, 파서 raw, Data/Information ID, DB와 과거 실험을 수정하지 않는다. 아직 완료하지 않은 T03/T04 application AT를 통과 처리하지 않는다.

Ponytail/local community-evals 원칙에 따라 Python 표준 라이브러리와 기존 로컬 runtime을 재사용한다. 별도 모델 다운로드·이미지 빌드·외부 추론은 없다. 모델에는 원문 텍스트와 source type, 페이지, script 그룹/후보를 제공한다. 이미지 참조는 보존하되 pixels를 입력하지 않는 실험이다.

## 구현·평가 순서

1. 독립 runtime/source hash baseline을 기록한다. generic script는 기존 source-map의 source rows와 raw evidence/visual manifest만 읽으며 수동 oracle/analysis groups를 읽지 않는다.
2. header/footer/page number를 보존하는 metadata 그룹, 명시된 큰 절과 Results/Methods 소제목, Figure manifest의 panel/caption/continuation을 이용해 초안을 만든다. 본문에 명시된 Figure를 여러 절에서 참조할 수 있다. 같은 Figure를 다루는 실제 소절을 무조건 합치지 않는다.
3. 제목 없는 앞부분은 임의로 Abstract로 확정하지 않고 재검토 후보를 만든다. 모델은 고정 후보 key에 keep/허용된 변경/needs_context와 해당 창 안의 evidence IDs만 반환한다. 원문 재작성·임의 ID·Figure 생성·원본 caption anchor 변경은 허용하지 않는다.
4. 초안/후보/프로토콜/코드 hash를 고정한 후 작은 합성 smoke 1회, 논문 packet별3회 반복을 실행한다. 원문을 자르지 않고 packet token 수를 사전 검증한다. 온도0/seed42/thinking 설정2048/context32768, cache off. 실패는 receipt에 보존한다.
5. script-only와 적용후 projection을 독립 평가한다.229 ID coverage, primary103 pairwise agreement, metadata 오류, Abstract/Introduction 분리, 뒤쪽 Figure5/6 caption 연결, 모델 수정으로 생긴 회귀와 unresolved 요청을 구분한다. 수동 reference는 한 가지 packing이며 semantic truth/일반화 성공률이 아니다.
6. 실제 호출 로그와 provenance hash를 보존하고 task label로 생성한 컨테이너만 정리한다. 기존 컨테이너/이미지/volume ID 집합과 대조한다. 도구에 대한 의미 있는 failure/patch invariant 검사를 실행하고 문서 baseline 오류와 새 오류를 구분한다.

## 파일과 복구

새 도구 tools/run_script_context_review.py, 새 output/t03-script-context-review/*, 본 계획이 주 변경이다. source 입력은 read-only이며 산출물은 exclusive create로 이전 run을 덮어쓰지 않는다. 모델 제안 원문/검증/적용 ledger와 최종 projection을 분리한다. 잘못된 proposal은 원본을 바꾸지 않고 실패/보류로 남긴다. 승인 차단 결정은 없다.

## 진행

- raw visuals manifest에 이미 Figure5/6의 explicit continuation anchors가 존재함을 독립 확인했다. raw Figure bounds는 proposal 상태이므로 이를 human-verified로 승격하지 않는다.
- 시작 GPU snapshot에서 RTX5080에 다른 사용량이 있어 latency 비교 시 경쟁 부하를 기록한다. 타서비스를 중단하지 않는다.
- 실험 도구 작성 중이며 아직 모델 추론/결과 판정은 실행하지 않았다.

## 중간 검증

- `python -X utf8 -B tools/run_script_context_review.py prepare --root output/t03-script-context-review --repo .`: exit0,18개 초안 그룹·7개 packet·20개 후보. source-map의 rows를 원래 bundle의 text/type/page/hash와 재결속했다. 수동 grouping/oracle는 생성 경로가 읽지 않는다.
- 독립 구현 검토에서 source block 유일성, 진짜 exclusive file create, Abstract 이동 후 source 순서와 Figure callout 재연결 검사를 보완했다. 첫 모델 호출 전에 preflight-v1/v2를 보존하고 final freeze했다. source/draft bytes는 전부 동일하다. 최종 runner SHA626912067bd0910a9c7435e4ccc233e873cd77a7db0d8e325bcdef66933884a9.
- `python -X utf8 -B output/t03-script-context-review/check_invariants.py`: exit0,10tests/0failure/0error/0skip. HTTP 전부 mock이며 canonical/model/DB calls0. 부적절한 evidence, 누락·추가 key, caption 수정, 연쇄 merge, Abstract/source order, 필요 문맥 보류, malformed HTTP 실패 receipt 및 기존 파일 보호를 검증했다. [checks](../output/t03-script-context-review/checks.json).
- 서버는45.75초에 context32768로 로드됐다. 현재5080의 다른 GPU 부하를 유지한 채 실행했고 snapshot에서 약14,089MiB/99%를 관찰했다. 모델 단독 메모리 peak가 아니다.
- 제외 smoke1회:68.55초,387prompt+2079completion tokens,valid. 실제 논문 검토는7packet×3회로 실행 중이다. 첫 round는 19keep/1abstract,19그룹,229/229coverage,unresolved0. 후보가 포함하는 unique source는83I이므로 전체229I에 대한 모델 의미 검증이라고 하지 않는다.
- 첫 round에서11개 실제 소절 경계에 대해 올바른 keep와 부적절한 reason_code=explicit_caption이 함께 나왔다. 결정 정확성과 설명 코드 의미를 분리하며, 이 사후 진단을 사전18probe에 섞지 않는다. 동결된 모델 출력은 수정하지 않는다.
- 첫 round 관찰 후 좁은 민감도 대조1packet/2fault를 추가 준비했다. 실제 source 문단75→104를 잘못 나눈 projection과 Figure5에 Figure6의 continuation을 잘못 붙인 proposal만 만든다. 기대값은 호출 전 별도hash로 고정하고 모델에 보내지 않는다. 원문9rows는 불변이다. 올바른 원래 caption inventory와 명시적인 무제목 경계 신호를 주는 쉬운 사후 점검이며 holdout/일반화 성능이 아니다. 주21회와 별도1회 실행·집계한다.
- [이미지 참조 검사](../output/t03-script-context-review/runtime/image-reference-audit.json):142개 기존 파일 경로·186descriptor 참조·30,355,466bytes의 hash/bytes 일치.14개200DPI PNG의 parser base와 visual companion base를 명시했다. 이미지 복사/수정/모델 pixels 입력0.
- `python -X utf8 -B tools/validate_bundle.py --json`: exit1,기존rawMarkdown delimiter11건과 정확히 동일,새오류0. [비교](../output/t03-script-context-review/runtime/document-audit.json). 전체 문서 검사를 pass로 표시하지 않는다.
- 원본 Desktop/Test_Paper.pdf와 보존된 evidence/source.pdf의 SHA가 DataID와 일치했다. 새 runner/evaluator/control/check Python4파일 AST 검사 exit0. 앱/PG/e2e 검증은 이 실험 범위 밖이며 미실행이다.

## 모델 실험 완료

- 실제 호출23회: 정식21회(7packet×3반복), 제외 transport smoke1회, 별도 사후 대조1회. 정식21/21 구조 통과,3/3 독립 patch replay 일치. 세 final projection의 fileSHA는 모두 dd2634ba80f00295ced883c52f875413e28aaa81b1d27960a1463921dc4e829e다.
- 초안18그룹→최종19그룹.229개 I가 각각1회 유지됐고, 모델은 매반복Abstract57만metadata에서분리했다. Introduction1/Results7/Discussion1/Methods6/뒤부분2 및metadata1을 유지했다. Figure1의두실제소절은서로분리하면서같은Figure를참조한다. Figure5/6 continuation과먼본문연결은초안부터보존됐다.
- primary103 pairF1=.966346은전후동일,metadataFP1→0,새실패probe0,새분할/병합회귀0. reference packing이Figure1의두소절을합치는구성차이28쌍을의미오류로계산하지않는다. 18사전probe 중새통과는Abstract분리1개다.
- 정식 결정60개:keep57/abstract3. reason_code 유형불일치는33개로,11실제경계×3반복에서keep에explicit_caption이붙었다. 자동설명을신뢰할수있다는근거가아니며,향후출력은모델판단/evidence에집중하고검토type은스크립트가보유하는것이단순하다.
- `python -X utf8 -B tools/score_script_context_review.py --root output/t03-script-context-review`: exit0. metricsSHA50f7bdf20cea9aeeb44cf19aaa0f48009c6be07f963b7b5c20439afa4a156960. 생성기/소스/실제request/response/결정/projection hash와독립재적용을검증했다. scorer자체의modelcalls0과실제실험21회를별도필드로표시했다.
- 정식 actual backend usage:prompt93,036/completion45,231/total138,267; 한반복31,012+15,077=46,089tokens. prompt크기1,111–7,146tokens,잘림없음. packet합계1482.780초(24분42.8초),호출중앙71.156초,7packet반복시간484.242/511.807/486.730초. GPU경쟁부하가있어이전모델단독실험과속도우열로비교하지않는다.
- 대조1회는75.161초,2559prompt+2133completiontokens,구조valid. source75→104 인위적분할에merge_previous,Figure5에Figure6 continuation을붙인proposal에needs_context를반환해2개기대판정과일치했다. 원문·기본projection은변경하지않았고잘못된Figure연결을자동확정하지않았다. 대조expectedhash는53f093dbd5f86c633918c90f1b77eba2d4acf09241154d2803b82fbe6d6f7cd9로호출전에고정했다.
- `python -X utf8 -B output/t03-script-context-review/write_report.py`: exit0,[보고서](../output/t03-script-context-review/REPORT.md)와[문맥크기표](../output/t03-script-context-review/CONTEXT_GROUPS.md)생성. [독립평가](../output/t03-script-context-review/EVALUATION.md)와[원문판정](../output/t03-script-context-review/FINDINGS.md)을함께참조한다.
- `output/t03-script-context-review/cleanup_runtime.ps1`: exit0. tasklabel을확인하고smoke/run/control/server4개컨테이너의로그를보존한뒤제거했다. 새이미지빌드/다운로드0이며기존모델파일은보존한다. Docker자원ID와원문최종대조는후속receipt에기록한다.
- 변경파일: tools/run_script_context_review.py, tools/score_script_context_review.py, docs/implementation/I2K_CONTEXT_POLICY.md, docs/INDEX.md, 본계획및output/t03-script-context-review/* 실험산출물. 이전문서bytes는docs-before/*.snapshot에보존했고생산app/src/schema/DB/canonical문서를변경하지않았다.
- 현재범위의실제모델비교는완료했다. 일반논문성능·누락된후보발견·시각판독·OCR충실도·embedding/reranking·K생성및실제app/PG검증은미완료범위다. 추가승인이필요한차단결정은없고T03/T04 application AT상태를승격하지않는다.

## 최종 보존·완료 확인

- runtime/final-integrity-audit.json:Docker container ID7/image ID15/volume name35의전후집합이정확히같다.이번task4컨테이너는모두제거됐다.원본8파일최종SHA가시작전과일치한다.모델은시작전전체해시검증과RO mount기록을사용했고불필요하게9.5GB를재해시하지않았다.
- 23/23call의requestSHA/usage/result/finishstop/cache0/fullprompt/context-fit을검증했다.보존된server.log의23release모두truncated0,actualQ8_0/context32768/slot1/buildb10380/text-only를확인했다.실제thinkingtoken수분리측정이나GPUpeak측정이라고표현하지않는다.
- root는metrics에결속된108개파일hash와세projectionhash를재확인해불일치0을관찰했다.독립원문검토는원래Figure6개객체와panel36refs보존및제한된대조2건을확인했다.
- 문서최종검사도exit1/기존rawMarkdown11errors로유지됐으며원문Markdown수정이나validator완화는하지않았다.최종verification.json에서보고서·코드·검사receipt·실행계획의hash를연결한다.
- 이사용자요청의실험·정리·보고는완료다.새생산기본값이나후속T04완료로해석하지않는다.
