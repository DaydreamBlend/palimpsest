# T03 follow-up — local context grouping comparison

2026-09-10: 사용자는 비교 대상을 **Qwen3.5-4B Q4_0와 Gemma 4 E4B Q4_0**로 정정·승인했다. 기존 source I에서 읽기용 문맥 그룹을 제안하는 로컬 실험이다. 원문 D2I, canonical I, DB, K 생성, 제품 모델 기본값을 변경하지 않는다.

## 실행 기준

AGENTS, USER_OVERRIDES, INDEX, DECISION_REGISTER, T03/T04 경계, PLANS, CODE_REVIEW와 I2K_CONTEXT_POLICY를 읽었다. U11의 원문 불변과 사용자의 선택적 local context grouping 승인을 함께 적용한다. Ponytail 및 local community-evals skill에 따라 기존 llama.cpp 이미지와 Python 표준 라이브러리를 재사용한다. 다운로드·외부 provider 호출은 없다.

- 고정 실제 논문: image200 Test_Paper의 229 I, exact content/page/source_type만 모델에 전달. 이전 analysis의 group/label/statistics는 모델 입력에서 제외한다.
- 보조 진단: 독립 작성한 Markdown fixture 3개. 정답 section/Figure refs는 scorer에서만 읽는다. 실제 논문 1개와 합성 문서 3개이므로 일반 문서 전체의 우열로 확대하지 않는다.
- 두 모델을 같은 RTX 5080에서 순차 실행. llama.cpp b10380 image sha256:a50b12bb92de0253d2737824ca1887f410e07b4dd3e3028f74a5a0a67c789e4b. context 32768, parallel 1, flash attention, temperature 0, seed 42, thinking budget 2048, 전체 출력 최대 8192 tokens. 실제 token 사용과 finish reason을 기록한다.
- 먼저 별도 smoke 입력으로 실행/구조/용량을 확인한 뒤 동일 고정 prompt와 schema로 논문 및 Markdown 각 3회(모델당 12회) 실행한다. 오류·불완전 출력은 숨기거나 자동 수리하지 않는다. smoke는 정식 점수에서 제외한다.
- 구조: 모든 입력 ID 정확히 1회 배정, unknown/duplicate/omitted ID를 검사. 모델이 내용을 재작성하지 않고 group kind, ID 목록, main/supplementary Figure refs만 제안한다. 이것은 semantic determinism의 보장이 아니다.
- 주지표는 고정 primary 103 I의 pairwise reference agreement. Metadata 126 I를 포함한 높은 전체 점수가 본문 오류를 가리지 않도록 metadata 분류/전 항목 coverage를 별도 보고한다. 검토된 18그룹은 한 가지 packing reference이며 유일한 정답은 아니다. Markdown boundary와 Figure 링크, 반복 partition 일치, 속도를 별도 보고한다.
- 텍스트와 이미지의 기존 원문 참조를 보존하지만 이번 소형 모델에 pixels/mmproj는 입력하지 않는다. 따라서 이미지 이해나 멀티모달 I2K 품질 실험이 아니다.

## 변경·복구와 검증

새 tools/run_context_grouping_experiment.py, tools/score_context_grouping_experiment.py, output/t03-context-models/*와 이 계획을 만든다. 기존 원문/analysis/model 파일 해시를 검증하며 출력은 덮어쓰지 않는다. 새 컨테이너는 task label을 붙이고 network none + 공유 loopback namespace만 사용한다. 생성 전후 container/image/volume 목록을 비교하며 작업에서 만든 컨테이너만 로그 보존 후 제거한다. 기존 이미지·volume·타서비스는 유지한다.

실제 로컬 model evaluation과 scorer assertions를 검증한다. production app/DB를 변경하지 않으므로 전체 앱/PG suite를 반복하지 않는다. 문서 검사 기존 raw Markdown delimiter 11건을 새 문서 오류와 구분한다. T03/T04 AT 상태를 일괄 통과시키지 않는다.

## 진행

- 두 GGUF의 현재 SHA/bytes가 이전 다운로드 profile과 일치함을 독립 재검증했다. 현재 Qwen/Gemma task 서버는 없다. runtime baseline은 기록 후 고정한다.
- 정식 추론과 점수 집계는 아직 미실행.

- Gemma transport smoke: 562 prompt/518 completion tokens,3.55초,2groups,strict valid. 서버 actual context32768, truncated0을 확인했다. preflight tokenize는 실제 usage보다 BOS1개 적어 margin1을 추가했다. 독립 검토에서 MD fenced-code 안 Figure 참조 취급을 명시하도록 조언받아 정식 실행 전 양 모델 공통 policy v2를 고정했다. 이전 smoke harness/protocol/cases를 별도 보존했다. Setext는 prompt에 허용하지만 이번 fixture에 없으므로 평가 성공을 주장하지 않는다.
- 공개 로컬 모델 raw response의 reasoning_content는 비canonical 실험 artifact에 원문 보존하며 reasoning 내용을 점수 근거나 보고서로 사용하지 않는다. Compiler Record private CoT 보존 계약과 이 로컬 실험 data를 구분했다. 이전 heading 도구의 제거 방식과 차이를 명시한다.

- 양 소형모델 baseline PDF에서 누락/중복이 발생하여 추가 assignment arm을 승인 범위 안에서 준비했다. 모든229 source ID를 required object key로 고정하고 모델은 group_id만 선택한다. schema 변경과 큰 Results/Methods 대신 subsection을 구분하라는 재강조를 함께 적용하므로 단일변수 ablation이라고 주장하지 않는다. 동일 원문·각3회·thinking2048·출력8192 유지, PDF만 추가 비교. script 정렬/결합은 membership 판단을 바꾸지 않는다. raw와 normalized를 별도 저장한다.
- 후속 사용자 승인: 두소형모델불충족시 Qwen3.5-9B Q8 추가 비교. baseline양쪽실패를 확인해 exact Q8 GGUF 다운로드준비를 독립진행중이다. 동일 baseline12회와 assignment PDF3회를 계획하며 모델 파일/revision/hash/메모리를 기록한다.

- Gemma assignment 최초client는 model reload완료 전 /health503으로 추론호출 전에 exit1했다. startup-failure.log를 보존했고 모델로드완료후 같은client를재시작했다. 평가repeat 출력이 생성되기 전의runtime준비실패이며 semantic평가성공으로숨기지않는다.
- 독립 scorer review에서 enum KINDS가set→list로변환되어 실제schema array순서와hash가불일치할수있음을 발견, deterministic ordered list와 실제request schema 대조를추가하도록수정중이다. 최종metrics는아직생성하지않았다.

- Scorer KINDS set 관찰은 작성중 오래된 snapshot이었다. 최종파일은 이미orderedtuple로수정돼있어해당최종finding은철회했다. 저장된각arm 실제request schema와stream을self-check에추가했으며root도실행했다. 최종score전입력/분모/invalid처리독립검토를유지한다.

- 9B Q8: Unsloth revision3885219b6810b007914f3a7950a8d1b469d598a5,9,527,502,048bytes,SHA809626574d0cb43d4becfa56169980da2bb448f2299270f7be443cb89d0a6ae4를실제파일로검증했다. 기존hf CLI/image재사용,download689.266초+hash약4.8초,새imagebuild0. 공식원본revision관측과third-party변환원본revision을동일시하지않는다.
- 완료된소형모델서버/client8개는라벨·종료상태검사후로그보존및제거했다.9Bdownload컨테이너도--rm종료했다. 기존자원유지 최종대조는9B종료후수행한다.
- 9B actual context32768로43.09초만에로드,RTX5080 순간GPU전체메모리10,706MiB,smoke24.87초/valid2groups/565prompt+2140completion tokens. GPU순간값은peak측정이아니다.정식baseline12회시작했다.

## 완료 — 2026-09-10

- 정식45회(baseline36 + assignment9)와 제외smoke3회를 모두실행했다. 모델호출은로컬loopback만사용했으며 canonical/DB writes0이다. [최종보고서](../output/t03-context-models/REPORT.md), [원문대조판정](../output/t03-context-models/FINDINGS.md), [metrics](../output/t03-context-models/metrics.json), [통합manifest](../output/t03-context-models/manifest.json)에결과를기록했다.
- baseline PDF: E4B0/3통과(50누락/11중복ID),Qwen4B0/3(6누락/138중복ID),9B3/3. 고정ID: E4B0/3(undefined group refs),Qwen4B3/3(primaryF1=.556),9B3/3(primaryF1=.377). 모든정식실행에서33/45구조통과.9BmetadataF1=.992이지만Discussion본문159를metadata로잘못배정하는등의오류가남았다.유효결과의partition/annotation은설정별3회동일했다.
- 고정ID시간중앙값:E4B34.31초(실패),Qwen4B31.88초,9B60.02초.같은21–22K규모source입력·5080·context32768을사용했다.2Kthinking은서버/요청설정확인이며실제reasoning-token수를usage에서독립분리측정한것은아니다.
- 세모델모두이전체논문입력방식의Figure/소절별문맥요구를충족하지못했다.9B는큰절/metadata/허위Figure번호억제에서좋아진점이있고4B는referencepairF1이높지만main7/8허위참조가있어점수만으로채택하지않는다.더짧은후보/절입력·이미지입력성능은미평가다.기존heading profile/제품모델기본값은변경하지않았다.
- 새파일: tools/run_context_grouping_experiment.py, tools/run_context_assignment_experiment.py, tools/score_context_grouping_experiment.py 및 output/t03-context-models/*, 본계획. docs/implementation/I2K_CONTEXT_POLICY.md와docs/INDEX.md에사용자의localgrouping/9B실험승인·범위를연결했다.문서변경전bytes는output/t03-context-models/docs-before에보존했다.
- 실제검증명령(호스트Python C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe 사용):
  - `python -X utf8 -B tools/score_context_grouping_experiment.py --root output/t03-context-models --self-check`: exit0,oracle4개·실제request schema45개통과.
  - `python -X utf8 -B tools/score_context_grouping_experiment.py --root output/t03-context-models --models gemma4-e4b-q4 qwen35-4b-q4 qwen35-9b-q8`: exit0,complete_for_planned_models,45개결과·33개valid,metricsSHA822295dae53a3e890b803666cc6e8bcf6761c5a094f9dc4e117ba2a2c64de3cf.
  - `python -X utf8 -B output/t03-context-models/write_report.py`: exit0,수치표보고서생성.이후원문판정및재현하네스링크를generator와report양쪽에동기화했다.
  - 독립소스/조건검토:36baseline request는model명제외동일하고server조건/ctx/loopback/image가동일,cache0·finishstop·입력truncated0.229I내용과원본8file hash일치.이는전체DB/semanticI2K검증이아니다.
- 평가종료후독립review에서찾은HTTP200 malformed response 기록경로를보완했다.최종response가[]/choices=[]/message=null이면실패receipt를기록하는중다시예외가나는문제를두runner에서수정했다.실제평가한원래도구4개는runtime/frozen/tools에exactbytes로보존했고기존protocol/hash/모델입출력/metrics를수정하지않았다.
  - `python -X utf8 -B output/t03-context-models/check_failure_receipts.py`: exit0,두runner×3종오류shape에서실패receipt12개와raw응답보존확인.모의네트워크·모델호출0.새하네스hash와기존평가hash차이는manifest에명시했다.
- source/model/runtime통합검증:metrics가참조하는모든run파일hash일치,원본8file불변,frozen하네스hash=각protocol,9B실파일검증receipt보존.초기model-profile의download0은기존두모델범위이며최종manifest는새모델download1로구분한다.
- 종료된실험server/client12개만tasklabel·상태검사후로그를남기고제거했다.다운로드/도구확인helper도--rm제거.최종Docker containers7/images15/volumes35의ID집합이시작전과정확히같다.기존자원·모델파일·데이터는보존했다.
- 현재모델비교slice는완료했다.생산앱/schema/DB를바꾸지않아전체app·PostgreSQL suite는미실행이며기존T03/T04 AT 상태를변경하지않는다.원문정보를일괄확정하는모델기본값선정은보류하고,script경계/명시적Figure연결을고정한작은범위모델지원은후속구현·평가로남긴다.새승인요청이필요한차단결정은없다.

- 문서검사첫회는docs-before에복사한백업.md의상대링크오류도보고했다(document-validation.json보존).동일bytes를.md.snapshot파일로이름만변경해백업과발행문서를구분했다.원래문서/링크/검증규칙은완화하지않았다.최종 `python -X utf8 -B tools/validate_bundle.py --json`: exit1,기존rawMarkdown delimiter11건과정확히동일하며새문서오류0(document-validation-final.json).이결과를전체pass로표시하지않는다.
- 최종Python5파일AST검사통과,변경한문서2개와post-run실패경로diff를확인했다(reviewed-diffs.json).최종verification.json에보고서/판정/metrics/manifest/검사결과hash와검증범위를기록했다.실행계획완료상태와T03/T04 application AT미완료경계는별개다.
