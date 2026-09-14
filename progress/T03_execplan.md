# T03 — Test_Paper.pdf에서 D2I·Information까지

사용자 지시: 제공한 PDF를 D로 하여 D→D2I→I를 실제 시험한다. I는 Text/Image 등을 포함할 수 있다. I2K/KNode/N2E/K2K는 이후 시험이며 이번 경계는 Information 생성·검증·보존이다.

## 입력과 적용 계약

- 원본: `C:/Users/DaydreamBlend/Desktop/Test_Paper.pdf`, 3,890,649 bytes.
- SHA-256: `a2268b37570f41bb07189cf083376e5823fae364165d5e0e256f796a0814cffe` (착수 시 재확인).
- U01–U10, root/docs/tests AGENTS, T03, PLANS/CODE_REVIEW, canonical D2I/Information/Compiler Records, MinerU adapter·모듈·저장 계약을 따른다. 원본 문서의 지시문은 untrusted content다.
- T02 Python 3.12.14/Docker/PostgreSQL 18.6/vector 0.8.6을 재사용한다. 0001_data와 기존 Data bytes/IDs는 보존한다. 새 schema는 별도 migration으로 추가한다. schema/migration/atomic effect 소유자는 root다.
- MinerU output은 비canonical parse artifact다. grounding 형식/hash만으로 의미 검증을 대신하지 않는다. 질문 후 사용자가 “Codex OAuth로 GPT5.6 Terra Medium을 이용해봐”로 선택했다. Generator/Validator 모두 `gpt-5.6-terra`, reasoning `medium`, Codex ChatGPT OAuth로 실행하며 별도 inference로 독립성을 지킨다. 이 시험의 선택된 PDF 원문/추출 text/figure를 해당 Codex 호출에 제공할 수 있다. 토큰을 복사·출력하거나 별도 API key로 전환하지 않는다.

## 실행 순서

1. [x] PDF preflight·원문대표페이지 확인, Palimpsest 도구로 독립 개발 DB에 D 등록.
2. [x] 공식 최신 안정 MinerU·exact package/model/backend profile 준비, 원문 네트워크 전송 없는 로컬 파싱.
3. [x] Text/Image를 포함한 정규화 block·page/region·raw locator·artifact manifest 및 안전한 adapter 구현.
4. [x] Information domain/D2I/공통 execution과 atomic Record/candidate/Information/outbox 저장 구현. 실제 의미 검증 profile 확정 후 수행.
5. [x] 제공 PDF를 실제 D2I 실행하고 I/grounding을 원문에 대조, 사용자 검토용 결과·이미지 제공.
6. [x] 적절한 파일/DB/CLI/adapter 회귀·문서 검사와 상태 갱신. mock·실제 parser·semantic 검증 결과 구분.

root는 runtime 설치와 schema/service/DB를 소유한다. 독립 agent는 공식 MinerU 조사, I 계약 검토, 원문 preflight를 각각 수행한다. 코드 편집은 파일 소유권을 정한 뒤 분리한다. 기존 다른 프로젝트 container/DB/모델은 변경하지 않는다. 사용자 원문은 읽기 전용으로 전달하고 모델 다운로드와 문서 추론 네트워크를 분리한다.

## 관찰·결정·검증 기록

착수 관찰: 기존 일반 앱 이미지는 palimpsest-t02:0.1.0. 로컬 GPU는 RTX 5080(16GB, CC12.0), RTX 4060 Ti(16GB, CC8.9). GPU 모델실행은 아직 미검증이다. 다른 프로젝트의 embedding server가 있으나 이를 Generator/Validator로 가정하지 않는다. 이번 PDF는 T02 synthetic test DB와 구분한 보존 가능한 개발 환경에 등록한다.

T03 acceptance와 실제 command/실패/재시도/남은 범위는 작업 중 여기에 누적한다. 일부 page/후보 또는 미검증 output을 전체 완료로 보고하지 않는다. T03 전체 gate와 사용자 PDF의 제한된 시나리오 결과를 구분한다.

## Data 등록과 parser 준비

`docker compose -p palimpsest-dev up -d db` 및 `run --rm migrate`: exit0, 새 독립 개발 DB에 0001_data 최초 적용(applied=true). 원본 PDF 한 파일만 `/input/Test_Paper.pdf:ro`로 mount하고 `app data import /input/Test_Paper.pdf --origin-uri file:///C:/Users/DaydreamBlend/Desktop/Test_Paper.pdf --json` 실행: exit0/committed.

- data_id: 위 원본 SHA-256.
- request_id: `01a08508-21d8-73b1-8ab1-ee16a674efd6`.
- acquisition_id: `01a08508-2231-7a0f-98cd-f578e368fda1`.

원문은 14쪽, 전페이지 native text, figure가 있는 페이지6개다. Figure5의 caption이9→10쪽으로 이어진다. CropBox/MediaBox 차이와 원문렌더/해시 결과는 [preflight](T03_source_preflight.json)에 있다.

공식 PyPI 안정판 MinerU3.4.5 wheel hash `4a73b865920bb9109c1b8b1bc46567e296bf0133a67106a04effd219536ae72d` 확인. 별도 parser Docker image에 pipeline extra와 torch2.8.0/torchvision0.23.0 설치를 시작했다. 공식 metadata에서 torchvision의 torch==2.8.0 조건을 확인했다. 실제 설치/실행 검증은 아직 진행 중이다.

Codex CLI0.153.4가 PATH에 존재한다. 일반 sandbox의 CLI실행은 home directory 발견 실패, 승인 실행 `codex login status`는 `Logged in using ChatGPT`/exit0. 공식 non-interactive/auth/config 문서와 local `codex exec --help`를 확인했다. 신규 API key 생성이나 OAuth credential 파일 읽기를 하지 않았다.

## 구현·환경 검증 누적

- MinerU Docker build `docker build --platform linux/amd64 -t palimpsest-mineru:3.4.5 -f deploy/mineru/Dockerfile deploy/mineru`: exit0. 별도 이미지에 torch2.8.0/torchvision0.23.0/MinerU3.4.5 설치. exact image 및 모델 manifest는 `T03_mineru_profile.json`에 기록한다.
- public 모델 `opendatalab/PDF-Extract-Kit-1.0`의 commit `ed6b654c018d742e65a17671e379c5e6ecc87ec9`에서 실제 pipeline의 필요한 40파일/2,595,586,833bytes만 다운로드. 원문 미mount, public token=False. 전용 volume `palimpsest-t03-mineru-models`의 manifest SHA256 `6e4ab8545ac654440671e551346bd1865d6f12181c7d9f48bfef042c92046408`. network-none/read-only 재검증 exit0. 실제 parser smoke는 별도 단계다.
- 실제3.4.5 소스에서 문단을 페이지간 병합하며 원래 page를 잃는 동작을 확인했다. adapter는 cross_page/lines_deleted가 발견되면 동일 MinerU middle의 원래 페이지별 preproc_blocks를 명시적으로 선택하고 사유를 보존한다. 다른 parser fallback이 아니다. root는 원문9/10쪽 렌더를 직접 대조했다.
- Codex 연결 최초 실패: strict config가 현재CLI의 미지원 tools.view_image key를 거부했다. 실제 지원되는 feature flag로 수정. 다음 호출은 정상완료이나 개발 중 기능/도구비활성 시작 경고2개를 error item으로 내보내는CLI동작을 확인해, 경고 개수만 기록하고 실제toolcall/turn.failed는 계속차단했다. 최종 OAuth smoke exit0: `gpt-5.6-terra`/medium, thread `01a08519-de9a-7c93-98b7-f54b562d9218`, input7605/output15. 모델접속검사이며 PDF semantic검증은 아니다.
- `0002_information.sql`과 append-only migration chain, Information/D2I/CodexProvider/MinerU adapter, Compiler Runtime service 및 worker CLI를 구현했다. 새 test project `palimpsest-t03-test` 생성 및 migration exit0/applied=true. 사용자 개발 DB는 이 시점0001로 보존했다.
- 첫 앱 suite: `docker compose -p palimpsest-t03-test run --rm --no-deps test`: 103 tests/7.877초, 1 failure. 버전확인 fixture가 이전0.1.0만기대했으나실제앱0.2.0이라발생, fixture를새버전으로갱신. 나머지102개통과. 최신코드전체회귀와새DBsuite는후속기록.
- 독립검토로 retry 본문digest를재생분기보다먼저검사, needs_human 후보보존, 확정 I의뒤늦은grounding INSERT차단, terminal Record의candidate재삽입차단, 원문block/execution과grounding정합검사, normalize→publish 파일변조검사를추가했다. source bundle/정확한proposal집합을Validatorreceipt와연결한다.

현재 외부 모델은 지정된 Codex OAuth만 사용한다. BGE-M3 embedding/reranker나 I2K 이후 inference는 이번 실행에 포함하지 않는다. accepted I는 원문의 주장을 충실히 담았다는 판정이며 의학적 사실을 독립적으로 확증했다는 의미가 아니다.

## 사용자 후속 요청 — Docker 정리

구현 후 검증된 Palimpsest 이미지·필요한 개발 컨테이너를 남기고, 잘못된 Palimpsest 관련 컨테이너/이미지는 삭제해 달라는 사용자 요청을 받았다. 실제 PDF→I 결과 검증이 끝난 뒤 생성 이력·Compose project/image ID를 확인하여 실패·교체된 Palimpsest 자원만 개별 정리한다. 사용자 원본/I와 모델·DB 볼륨은 삭제 대상이 아니며 다른 프로젝트와 공유 image/base layer에 대한 무차별 prune을 사용하지 않는다. 정리한 이름/ID와 남긴 자원을 최종 기록한다.

## 실제 연결 실행과 추가 회귀

최종 UUID 제약은 `uuid_extract_version(id) IS NOT DISTINCT FROM 7`로 비RFC variant의 NULL을 거부한다. 이전 test project schema history는 고치지 않고 별도 `palimpsest-t03-verify`에 최종0001/0002를 설치했다. Information 통합17개/4.080초, worker claim8개/9.190초 통과. worker의DBsession loss시stdin buffered daemon으로발생한SIGABRT는 os.read EOF대기로수정해정상exit3와lock해제를확인했다. 전체앱이미지회귀132개/21.510초/exit0(skip없음). 이시점이미지ID `e7034f46503febd9afdcee51eae1f05e7d6d186ba5a7040c0ee9c04e9dceb034`와검사한5개host/image파일hash가일치했다.

`docker compose -p palimpsest-dev run --rm migrate`: 사용자PDF가등록된개발DB에추가0002적용 exit0/applied=true. 0001과D는보존했다.

`tools/run_d2i.py` 실제입력 실행1: execution `01a0852b-e011-7175-b4da-fd31bf23a423`. 첫시도는PdfPage의contextmanager미지원으로실패, 명시close로수정. GPU기기UUID Docker옵션만으로는WSL에서5080이노출되어 `--gpus all`+`CUDA_VISIBLE_DEVICES`를4060Ti UUID로설정하고기기1개검사로수정했다. 같은execution재시도는MinerU내부six누락으로실패. 둘다failed기술이력이며I/rejected Record없음.

공식PyPI six1.17.0 wheelSHA `4721f391ed90541fddacab5acf947aa0d3dc7d27b2e1e8eda2be8970586c3274`를runtime-fixes.lock에고정하여추가설치했다. 모델이미지새digest `fdab78016483e1dbf0f416c9f74941a1242a91dae58fa2cc9617488ceb338854`. [모델profile](T03_mineru_profile.json)의history는이전실패이미지를보존한다.

실행2: `01a08530-b03f-76bf-9f8e-13f135f9aa78`. 실제로컬MinerU14/14페이지파싱,sourcegeometry/전체pagecoverage,normalized249blocks및63이미지해시,PGmanifest게시와CAS복원에성공했다. GPU4060Ti/torch2.8.0+cu128/CUDA12.8,네트워크none. Generator호출은구조적 invalid_candidate로종료되어I는아직없었다. 모델내부reasoning/후보본문을로그로남기지않았다.

실물QA에서17 image와46 chart로분류된63crop을확인했다. 첫쪽updatesicon1개와6개figure page의62panelcrop이며각파일JPEG decode/hash가정상이다. `chart`/`table`도실제crop이있으면Image I가될수있도록modality규칙을보완한다. Figure5H의parentbbox밖caption을발견해adapter v2가원래upstream_bbox와개별grounding_regions를보존하고검증된관측영역의명시적envelope를I근거bbox로제공하도록수정했다. 합성adapter15tests/0.008초와실물14pages/249blocks/Fig5captionenvelope검증 exit0. 원문이나다른parser에서bbox를추정한것이아니다. [실물QA](T03_parser_observations.json)는수정전발견과원문대조를보존한다.


## 최종 실행과 결과

최종 이미지 `palimpsest-t03:0.2.0`의 ID는 `sha256:12c60b40b5b15d82d40dd009e4419fcdc87a8243c1edb84a716ec0c09f051a5a`다. host와 image의 adapter/information/d2i 파일 hash 일치. `docker compose -p palimpsest-t03-verify run --rm --no-deps test`: **139 tests / 21.421초 / exit0 / skip0**. 원자성·rollback·동시성·immutable grounding·독립 호출 receipt·UUIDv7·worker claim의 실제 PG 검증과 mocked/unit 검증을 포함한다. 이전132개 기록은 이전 이미지의 실행 근거다.

PowerShell에서 `$env:PYTHONPATH='src'` 설정 후 다음 명령을 실행했다. Python 경로는 `C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`다.

```text
python -B tools/run_d2i.py --data-id a2268b37570f41bb07189cf083376e5823fae364165d5e0e256f796a0814cffe --project palimpsest-dev --work-dir output/t03 --provider codex-oauth
```

실행 `01a0853c-03d8-72ff-be35-958d8dae8db5` / profile `01a0853c-03d6-7ae4-a110-8373a41c46f3`, generation1/attempt1, exit0/completed. 실제 로컬 MinerU14쪽 전체와249blocks/63crop을 두 역할에 모두 제공했다. Generator29개 제안, Validator accepted28/rejected1(missing_grounding)/needs_human0. PG canonical I28=Text23/Image5, grounding51, 영속 D2IRecord29, 임시후보0, I2K pending outbox28. 상세 thread/profile/usage·ID는 [결과 JSON](T03_result.json), 전체 내용은 [Information 출력](../output/t03/INFORMATION.md)에 있다.

같은 명령을 재실행하여 exit0/replayed=true, 동일 execution/I28, provider_calls.jsonl 총2개 유지(추가 Generator/Validator 호출 없음)를 확인했다. 현재 provider 사용량은 Generator input95,268/output3,203와 Validator input95,389/output1,640이며 독립 thread다. 모델 내부 reasoning과 기각 후보 본문을 보존하지 않았다. 원문1건은 재등록되지 않았고 크기3,890,649 bytes를 유지했다.

[독립 원문 QA](T03_live_qa.md): accepted28 content 및 참조를 읽고 주요 Text 표본을 raw source/native PDF와 대조했다. 모든51grounding bbox가 실제 raw parent/descendant envelope와 일치했다. Image5crop을 실제 시각 대조했고 원본 digest/bytes와 export가 일치했다. 전체 figure 설명과 단일 panel payload의 범위를 보고서에 명시했다. Figure4 I 및7쪽 direct grounding은 없고205blocks는 미참조다. 이것은 누락률 측정이 아니라 의미적 완전성을 확립하지 않았다는 한계다. 표본의 충실성 판정이 세계의 사실이나 의학적 효과를 확증하지 않는다.

개발 DB 읽기 전용 집계와 `app doctor --json`은 exit0. doctor의 DB/Artifact Store는 ready지만 별도 host MinerU worker readiness 연결이 없어 parser not_configured 경고가 남는다. 실제 모델 준비/실행과 이 진단의 범위를 구분했다.

## Docker 정리 실행

사용자가 승인한 정리를 실제 완료했다. 다음 명령은 모두 exit0이며 볼륨 삭제 옵션은 쓰지 않았다.

```text
docker compose -p palimpsest-t02-test down
docker compose -p palimpsest-t03-test down
docker compose -p palimpsest-t03-verify down
docker rm palimpsest-dev-init-1
docker image rm 2e2f28a054ecbbd2585c683f305fb47abf478c15fa8dd69a24571ac8c701363d
```

시험/완료 init 컨테이너 총8개와 시험network3개, 구T02 image1개를 삭제했다. 이전 build의 Palimpsest image6개는 ID inspect에서 이미 없어 삭제했다고 세지 않았다. 최종 앱 `12c60b40…`, MinerU `fdab7801…`, PG18 `2ba9ca5f…`, 개발 DB `palimpsest-dev-db-1` healthy를 남겼다. 모든 volume 목록은 전후 동일하며 다른 프로젝트 컨테이너/이미지는 건드리지 않았다. [정확한 이름·ID·명령/결과](T03_docker_cleanup.json).

정리 후 `docker compose -p palimpsest-dev run --rm --no-deps app data verify <data_id> --json`: exit0/verified=true. `app information list --data-id <data_id> --json`: exit0, I28개 조회. 임시 app 컨테이너는 --rm으로 자동 제거됐다.

## 남은 범위와 후속 설계 질문

선택된 PDF를 I까지 만드는 이번 요청은 완료했으며 I2K/KNode/N2E/K2K는 실행하지 않았다. T03 전체 gate는 in_progress다. acceptance112개 중9passed/28partially_tested/75spec_only이며 각 scenario와 실제 근거는 [catalog](../tests/specs/acceptance_catalog.json)에 있다. AT71/AT105/AT112 등 전체 reconciliation/supersession/revalidation/일반 worker fencing은 완료하지 않았다. scanned/mixed·대형 문서·보류 후보 해결·scoped rejected-FP lookup 등 부분 검증/미구현도 실행 안내에 남겼다.

사용자는 D2I를 추가 LLM 호출 없이 결정론적 구조 추출·청킹으로 수행할 수 있는지 질문했다. 권고는 MinerU parser + deterministic normalization/structure/chunk checks + provenance 보존이며, 의미 해석·주장 추출은 I2K로 이관하는 것이다. 단순 구조 검사를 현재의 semantic acceptance와 같은 의미로 기록하지 않도록 I 품질/보증 계약을 먼저 정해야 한다. 이 질문을 승인으로 간주하여 canonical snapshot/migration/기존 I를 바꾸지 않았다. 기존 canonical/원본/0001_data bytes와 사용자 승인 이력은 보존했다.

## 후속 정정 — 주 Figure 누락 원인과 6개 완전성

사용자가 main Figure6개 대비 Image I5개는 문제라고 지적했다. 초기 completed는29개 제출 후보의 처리완료였으며 원문 Figure의완전성은 충족하지 못했다. 앞의 선택PDF완료 표현은 이 결함을 포함한 초기 실행의 역사로 정정한다. 현재 수정 목표는 Figure1–6 각각 전체그림과모든패널/캡션근거를연결한ImageI6개를검증하는것이다.

원인추적: Figure4 원문7쪽에A–G가있고 MinerU에패널crop10개+독립Text캡션(/pdf_info/6/preproc_blocks/0–10)이있다. Gen/Val양쪽첨부35–44가실제cropSHA와일치하며모든해당block이입력되었다. Generator receipt의unreferenced는기각전29개전체후보의block_ids로계산되는데7쪽16개block모두미참조다. 따라서정상Figure4근거후보가Generator단계에서빠졌다. 기각1건본문은정책상삭제되어Figure4였다고단정할수없다. 모델이개별이미지에실제주의를기울였는지는receipt로증명하지않는다.

MinerU캡션구조가다른점은가능한영향요인이다. 그러나검증된원인은Generator의근거누락+앱의필수Figure coverage guard부재다. [실제Figure목록/원문영역/receipt증거](T03_figure_inventory.json)에보존했다. 모든page전체입력은모든Figure출력의증명이아니었다.

수정계획: 원본을시각대조한Figure inventory와fullbodycrop6개를explicitrepairinput으로pin,기존MinerU/CAS원문블록은그대로재사용한다. figure_adapter는syntheticfullfigureblock을추가하고figure_coverage는각Figure정확1개+모든member/caption근거를강제한다. Generator가하나라도빼면구조실패하며Validator가필수Figure를기각/보류하면completed대신needs_human으로보고한다. 모든승인은실제Validator판정이며구조검사가대신하지않는다. Gv3/Vv4로올리고기각본문없이ordinal/type/source refs를receipt에보존해누락단계진단가능하게한다.

정정은generation2의figures_only범위다. 기존immutableText23/Image5와기존0001/0002를변경하지않고새Image6개를추가한다. 자동supersession/invalidation은아직구현하지않았으므로기존5개를소리없이삭제하거나active대체했다고보고하지않는다. 이후I2K입력선택에는정정runrefs를사용해야하며이번엔I2K를실행하지않는다. 검토된한PDF의regioninventory를임의PDF자동Figure그룹화완성으로확대하지않는다.

초기문서최종검사: validator exit0/errors0. 기본Windows cp949 환경에서도구39개실행은UnicodeDecodeError10개(59.508초);한문제단독재현후`python -X utf8 -B -m unittest discover -s tools -p 'test_*.py'`로39개모두pass(65.408초). 테스트assertions변경없음. 문서검사는앱실행과별도다. 150파일착수SHA대조에서는기존17개변경/삭제0/보호된source·canonical·decisions·0001변경0을확인했다. 이후Figure수정분은최종재검사대상이다.

## U11 방향 전환 — source-preserving D2I (2026-09-09)

사용자는 D2I를 원문 보존·페이지/위치 추적을 위한 스크립트 변환으로 확정하고 LLM 사용 시작을 I2K로 옮겼다. 이어 구조화된 LLM 후보와 애플리케이션 소유의 식별자·중복/재사용·검증/commit 경계를 요청했다. 현재 구현 범위는 I 생성까지 유지한다. 기존 의미 생성 실험은 역사로 보존하고 신규 source-information-v1로 구분한다.

- Figure 원인: MinerU는 Figure 4의 10 패널과 독립 caption을 보존했고 두 모델 입력에 전달됐다. Generator 전체 29 후보가 원본 page_index=6의 16개 block을 전혀 참조하지 않았다. rejected body는 보존하지 않아 그 후보의 내용을 역추정하지 않는다. 최초 런에는 필수 Figure 완전성 검사가 없었다.
- 이전 정정 generation 2는 새 지시 도착 직후 중단 여부 확인 시 이미 완료됐다: job 01a08559-efc3-7e86-b040-7fe566875d33, Figure Image I 6. 실제 중단에 성공했다고 기록하지 않는다. 이후 D2I LLM 호출은 금지한다.
- 신규 목표: 전체 original 249 blocks → Text 182 + whole Figure 6 + logo Image 1 = source I 189. 같은 반복문구도 위치별 보존. 원형 parser artifacts와 normalized structures, coordinates/regions/hash 및 reviewed Figure region 이미지를 유지한다.
- storage owner root: 0003_source_information append-only schema extension. 0001/0002 본문·기존 rows 변경 없음. 0002 원본 SHA256 a517e9ce44c8fd07b0dcce43690de08d3cf5851c65e72be732f8136197e5e402. semantic_type=NULL/unit_type source 분류, source_structure 검증과 semantic_checked=false를 구분한다.
- module owner storage_contract_review: pure builder/checker + separate source fingerprints; legacy module과 테스트 역사 유지. docs owner schema_kw_review: U11/canonical synchronized publish. QA/test owner next_schema_scope: 실제249 inventory 예상치 + 별도 PG integration tests. root는 Runtime/CLI/worker/실행/결과/cleanup 담당.
- 신규 CLI compile은 source profile만 받으며 jobs materialize는 내부 deterministic build/check/atomic effect를 실행한다. 공개 propose/decide 경로 및 host worker의 Codex import/call을 제거한다.
- 검증 순서: targeted unit → disposable PG18 migration and full application suite → dev DB 비파괴 append migration → 기존 parser CAS 재사용 generation3 → 249/249 accounting/provenance/full images/replay 비교 → 문서 검사와 exact Docker cleanup.
- T03 전체 승인/수명주기 및 범용 parser/figure grouping gate는 여전히 in_progress. I2K 이후 구현/실행은 하지 않는다.


### U11 실물 실행과 검증 결과

- 첫 U11 회귀:174tests/15.943초/exit1, errors2. Worker claim fixture가 이동 전 prompt 상수를 import했고 crossData FK test가 새표현체크에앞서유효하지않은빈payload를사용했다. worker fixture를 sourceprofile로전환하고 FK시험에정확한legacy schema marker를제공했다. 테스트제거/skip없음.
- 최종 `docker compose -p palimpsest-t03-verify build app` exit0, image4f6dc7e177db23d21344b5de24e7a8d64e4073fa163a1592bdcedbd851604cb6. `docker compose -p palimpsest-t03-verify run --rm --no-deps test` →190tests/27.582초/exit0/skip0. 순수source14·새source PG7포함. before_commit롤백,공백/빈content/표수식,변조·same-size crop손상,복구/replay,공개legacyprofile거부검증.
- 검증DB의0003설치exit0 뒤 dev DB의0003설치exit0. 0001/0002를변경하지않음. 새column unit_type이추가되지만기존34개row의기존모든필드·groundings는완전히같음.
- host명령은T03_RUNTIME의generation3/reuse-parser-job+whole_document sidecar 조합. 실행01a0856e-5610-70bd-9858-e03684a995b0/profile01a0856e-560e-76f6-9385-57afd5128ac3 completed/exit0. source I189=Text182+Figure6+logo1, grounding255, candidates0,source outbox189. provider call0, 새MinerU실행없이기존rawparse를검증/재사용.
- 동일host명령재실행exit0: samejob/sameI IDs/sameevents, 새효과없음. 원문PDF SHA/bytes불변. tmp/t03_verify_source_result.py exit0: original249hash/1173nestedcontent/63originalimagepaths/255groundings/79retainedfiles exact 확인. DB총I223=legacy34+source189. 원문해석차이4개는QAflag이며자동교정하지않음.
- 최종Docker정리 `docker compose -p palimpsest-t03-verify down` exit0: 검증container2/network1제거. 모든volume이름및무관containerIDs불변, PalimpsestdevDB1및앱/MinerU/PG18images보존. 이번마지막조회에구버전/untagged Palimpsestimage는없어추가image삭제0. 이전삭제기록은보존. 정리뒤 Data verify exit0.
- 현재구조화된LLM지식계약은U11로문서화했으나I2K/N2E/K2K/K2W구현은이번slice에서진행하지않았다. T03전체gate in_progress유지.


### 최종 문서·변경 검토

`python -X utf8 -B tools/validate_bundle.py --json`은 passed/오류0이다. current canonical 2,267줄/13 slices, accepted overrides11개, baseline invariants45개를 확인했다. `python -X utf8 -B -m unittest discover -s tools -p "test_*.py"`는43tests/115.940초/exit0이다. 이43개는 문서 도구·변조 검사이며 앱190개와 구분한다.

Git repository가 없어 시작 시점 SHA-256 inventory와 현재 파일을 비교했다. [변경 목록](T03_changes.json)은 modified39/added39/removed0을 기록한다. docs/source 원본과 설치 전임0001/0002 SQL bytes는 불변이며 U11 canonical 변경은 승인된13 slices 동시 발행이다. 실제 실행 profile에 기록한 구현 파일 해시도 현재 소스와 모두 일치한다.

독립 검토에서 지적된 빈 이미지의 label 혼입, caption의 중복 배정, parsed 뒤 artifact 손상 검사를 수정하고 테스트했다. source 단위의 문자열·원문 반복 위치를 의미 dedup하지 않는다. 의미 재사용/중복 node 검사는 I2K 이후 계약에만 반영됐으며 이번 시험의 구현 완료로 주장하지 않는다. 기존 이력 자동 제외·supersession 및 미구현 acceptance는 계속 남아 있다.

## 페이지 조회와 인접 문맥 projection — 2026-09-09 후속

사용자는 block 수가 많아 MinerU 읽기 순서로 페이지별 통합하고 LLM에 앞뒤 페이지도 제공하는 방안을 요청했다. 선택 응답은 **페이지별 조회·LLM 입력부터 적용**이다. 기존189개 source I 및 immutable 원문/Record는 유지하고 읽기 projection14개를 만든다. D2I를 제거하거나 I2K를 실행하는 요청으로 확대하지 않는다.

- 읽은 계약: USER_OVERRIDES/INDEX/DECISION_REGISTER/T03/U11/MODULE_BOUNDARIES/CLI/CODE_REVIEW. Ponytail 원칙에 따라 새 의존성·DB schema·미래 I2K scaffold 없이 순수 page_projection 모듈과 기존 Runtime/CLI 조회 경로를 재사용한다.
- 실물 확인: raw249개 전부 upstream_metadata.index가 있고 페이지 내 중복은0. 기존 bundle 순서는 preproc→discarded여서 머리말이 본문 뒤에 온다. 페이지별 모든 원문 블록을 index stable-sort하며 그림 synthetic primary 설명은 원문 text에 삽입하지 않는다.
- source-pages-v1은 원문 text를 두 줄바꿈으로 연결하고 Unicode codepoint offset→information_id/block_id/raw locator/bbox/hash를 보존한다. 이미지와 전체 Figure는 정확한 primary page와 CAS refs로 제공한다. 누락 index는 추정 정렬하지 않고 reading_order_unavailable로 실패한다. 동률은 원래 bundle 순서와 명시적 tie flag를 유지한다.
- page-context-v1은 중앙페이지±1(첫/끝2페이지), 각 I의 최소 원문 page를 owner로 삼아 target/context-only refs를 나눈다. 원문 I가 창 밖까지 이어지면 missing_information_pages/incomplete_information_refs로 정확히 표시한다. 3페이지를 모든 문맥이 완전한 경계로 주장하지 않는다.
- 작업소유: root page_projection/Runtime/CLI/실물검증/결과; page_projection_tests 순수 회귀; page_context_review 실물 순서·Figure QA와 PAGE_CONTEXT/CLI 문서. 기존canonical snapshot/0001–0003에는변경없음.
- 검증순서: 순수테스트→전용PG Docker 전체회귀→개발DB 읽기전용CLI pages/context 및189 I/249refs/14owner분배/±1창확인→결과문서→시험Docker정리. 승인 미결사항 없음. I2K 의미 중복 제거는 후속 구현 경계다.


### 페이지 projection 검증 결과

- 순수 단위12개/0.011초/exit0. 초회 fixture의 metadata 이름을 실제 upstream_metadata로 고쳤고, 실제 코드의 null I ID 허용 및 읽기 index 검사보다 먼저 digest를 계산하던 문제를 수정해 회귀로 고정했다.
- `docker compose -p palimpsest-t03-verify build app` exit0, 최종 image594c68dcf8b7ebab5461f45a041e78dce407b8c44368aabc645978c268ceb528. 전용 검증DB를 다시 시작해 `run --rm --no-deps test` 전체202개/24.832초/exit0/skip0 통과. migration 변경 없음.
- 개발 DB의 실제 CLI pages 조회2회는 동일한14페이지/249원문/189개I owner/7images와 digest를 반환했다. context page10은9–11쪽과missing12쪽을 표시한다. page0은invalid_page_number/exit4로 거부한다.
- 실물 projection의249개 char_start:char_end 구간은 원래 block text와 동일하며 index·bbox·raw locator·anchor를 대조했다. 기존223개 I 전체 snapshot/groundings JSON은 조회 전후 동일하다. LLM 호출과 canonical row 생성은0이다.
- 14창의 target_complete는 전부true. context-only 부족 페이지는 center8→10,center10→12,center11→9,center13→11이다. 독립 QA에서 center11은Figure6 자체완전하지만 옆페이지Figure5캡션의9쪽이부족함을 확인했다. root QA helper는 Counter(dict) 대신 Counter(dict.keys())를 쓰도록 수정 후 exact-once 검사를 통과했다. 앱의 coverage 오류가 아니었다.
- 사용자 검토용14페이지 출력과 JSON/14context를 output/t03-pages에 저장했다. 해시에는 실제 execution/profile 참조도 결합했다. canonical·설치migration·기존I를 수정하지 않았으며 I2K는 실행하지 않았다.

- 최종 문서 `python -X utf8 -B tools/validate_bundle.py --json` exit0/errors0. 이번 변경은 기존 U11의 context projection 계약 구현이어서 canonical13 slices/기존migration은 변경하지 않았다. 문서도구43개 전체회귀는 직전U11결과이며 이번턴에는변경없는도구suite를반복하지않고bundle검사만수행했다.
- 최종 `docker compose -p palimpsest-t03-verify down` exit0: 검증컨테이너2개/네트워크1개제거. 개발DB1개·현재앱/MinerU이미지·모든볼륨·무관컨테이너는보존했다. 이미지조회에서Palimpsest태그는현재앱/MinerU2개뿐이다. [실행 결과와 변경 파일](T03_page_result.json)에정리검증을포함했다. 현재T03 in_progress/I2K미실행경계를유지한다.
