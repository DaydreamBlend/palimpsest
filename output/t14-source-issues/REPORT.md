# I-only I2K와 D2I 오류 보고 — 0.14

2026-09-13 최신 사용자 정정에 따라 **직접 D→K 구현 초안을 철회하고**, I가 부족하면 사용자에게 D2I 오류를 알리며 관련 K를 보류하는 경로를 구현했다. 앱0.14.0/UI0.3.0/schema0013이다. 실제 provider 호출은0회다.

## 먼저 답한 context 질문

현재 코드 전체를 agent의 활성 context에 넣어 둔 상태는 아니다. [측정한 코드 범위](../t14-direct-source/code-context-size.md)는 외부 의존성·모델·실험 출력 등을 제외한208파일,2,981,483 UTF-8 bytes,2,963,790문자,49,094줄이다. src+desktop은98파일/1,388,201문자다. 문서·root build/launch·JSON 설정은 별도이며 파일을 읽어 크기/hash를 계산한 것과 전체 원문을 모델 context에 전달한 것은 다르다.

로컬 tokenizer가 없어 token은 실측하지 않았다.3–4문자/token이라는 매우 거친 가정이면 전체 약74만–99만,src+desktop약35만–46만token이며 보장 범위가 아니다. 현재 root 모델의 실제 잔여 context 한도를 확정하지 못했으므로 전체 fit을 주장하지 않았다. OpenAI의 [공식 설정](https://learn.chatgpt.com/docs/config-file/config-reference)은 context window와 auto-compaction 임계값을 구분한다. 실제 구현은 관련 모듈·호출자·계약·테스트를 읽고 대조했다.

## 철회와 보존

처음에는 과거에 승인됐던 직접 D 근거 예외를 다음 미완성 범위로 선택했다. 사용자가 그것은 규약에 없는 D2K이며 허용하지 않는다고 정정한 즉시 해당 작업을 중단했다. 이 최신 지시가 과거 예외보다 우선한다.

- 기존 Python/worker12개와desktop4개를 작업 전 측정 SHA-256으로 복원했다. [Python proof](python-restoration.json), [desktop proof](desktop-restore.json).
- 새 direct-source module2개,0014 draft SQL,새 direct-source test1개를 실행source에서 제거했다. 폐기 초안은 `superseded-draft`의 개발 기록이며 package/migration 대상이 아니다.
- 직접 D 초안은 DB migration/provider/K 생성에 사용하지 않았다. SQL0001–0013의13개 실제 source hash는 이전 측정과 일치한다. [최종 검사](verification-summary.json).
- 실제 code DB는 읽기 전용으로137개검사를통과했다. 기존D3/I242/K42/3자료version·V3head,정확한 과거16개행hash묶음과판정/근거이력이유지됐다. [보존 결과](preserved-history.json).

## 현재 동작

source K의 경로는 `D → D2I → I → I2K → K`다. 실제 I text/owned media가 없는 후보, null Information ID, direct_evidence 추가는 구조 검증에서 거부한다. K2K는 기존 accepted exact K premises만 사용한다.

새 multi-I2K 실행은 `i2k-information-required-v1` 정책/구현 hash를 input/profile에 고정한다. 기존 wire `source_requests`는 호환을 위해 남겼지만 원문 fetch 요청으로 처리하지 않는다. 모델이 필요한 I의 부족/전사/이미지/provenance 문제를 보고하는 필드이며 새 runtime receipt에 D2I 오류·사용자 확인·직접K/자동D2I 금지를 남긴다.

독립 Validator도 `d2i_information_error`, `d2i_missing_information`, `d2i_transcription_error`, `d2i_missing_media`, `d2i_provenance_error`로 보고할 수 있다. 문제 I를 인용하는 후보는`needs_human`이고,그보류후보의batch reuse도보류한다. Validator가모순되게confirmed/accepted를내도오류코드가있으면K를통과시키지않는다. 원래per-I판정/이유는보존한다.

다른 I에만근거한독립검증K는반영할수있지만전체실행은미완료다. 반대로 I에내용이있는데K로덜선택된 `missing_material_content` 같은일반검토누락은D2I오류로분류하지않고기존review-resume을허용한다. source 오류가보고된실행은`d2i_information_error_requires_review`로자동재개를막는다.

오류 상태는 **보고된 오류 / 사실 확인 대기**다. 모델 보고만으로 원문과 대조해 누락이 입증됐거나 I가수정됐다고하지않는다. 정확 Data/source execution/profile/input hash·관련 I/source refs·실제 보고 주체/이유를 보여준다. 오류 처리기에서 원문 읽기/D2I/새I/원문K생성은없다.

## 실제 검사 사례와 CLI

[제어된 PG 사례](runtime-error-example.json)는 합성 Generator가한I의문제를보고한경우다. 실제Runtime/DB에서그I를포함한공통후보와해당출처후보2개는보류하고,다른I의후보1개만반영했다. 오류와요청은영속보존됐고D2I복구/provider호출은0회다. 이것은실제LLM이논문누락을발견한사례가아니다.

```text
palim knowledge source-issues <execution-uuidv7> --json
palim knowledge review-status <execution-uuidv7> --json
```

새정책의`knowledge show`/`review-status`에도information_errors가포함된다. 과거profile의`review-status`모양은보존하고명시적인source-issues명령으로이전실제기록도읽을수있다. [기존완료코드실행의CLI확인](source-issues-cli-final.json)은errors=[]/requires_user_review=false를반환했다. CLI는자신의기존DB설정을사용한다. 처음시험에서Wiki전용`--database-name`인자를Knowledge명령에넘겨invalid_arguments가났고,지원되는프로세스내부DB선택후정상실행했다. 새API인자를만들어맞추지않았다.

## 테스트

| 구분 | 결과 |
|---|---|
| 최종이미지전체application |847개:831pass/16skip/실패0,420.018초,exit0 |
| 신규/관련순수+PG회귀 |49/49pass,113.490초,exit0 |
| 기본이미지미설치PDF라이브러리보완 |기존PDFium이미지22/22pass,0.801초,exit0 |
| 실제코드DB읽기전용이력 |137assertionpass |
| 실제PG오류사례capture |1casepass,합성모델판정,2.571초 |
| UI source Node |24pass |
| packaged ASAR renderer |15pass,source검사의부분재실행 |
| 실제source/package Electron |기존codeWiki/currentK2K/정확I/검토/저장질문읽기각통과,pageerror0 |
| 문서bundle |기존vendor/raw/복제문서948오류로exit1,현재작성문서와이번output오류0 |

PDF22개중16개가core skip을보완하고6개는중복이다. 이숫자를새고유test수로합산하지않는다. 오류notice는controlledNode/ASARfixture로검증했고실제code자료에가짜오류를저장하지않았다. 전체적LLM오류감지회수율평가는실행하지않았다.

주요 실행 명령:

```text
docker build -t palimpsest-information-errors:0.14.0 .
PALIMPSEST_APP_IMAGE=palimpsest-information-errors:0.14.0 docker compose -p palimpsest-multi-checks run --rm --no-deps -T --entrypoint python app tools/run_app_tests.py
python -B -m unittest test_information_errors test_information_error_runtime test_knowledge_review test_multi_source_runtime test_code_review_desktop -v
python -B -m unittest test_pdf_raster test_pdf_text_evidence test_pdf_visual_evidence -v
node --test desktop/test/security.test.cjs desktop/test/renderer.test.cjs
python tools/validate_bundle.py --json
```

PG검사는전용`palimpsest`fixture/기존credentials mount와tests path에서실행했다. nativePDF는기존`palimpsest-mineru-hybrid:3.4.5-pro2605`의네트워크없는컨테이너에서실행했다. 실제user code/paper DB는migration/테스트mutation대상이아니다.

최종image ID는 `sha256:dbdf3cf67b0ba6058b63da150ba94f0cca80a23f0cf7e96bce91a882cac493db`다. 이번초기중간image7f66…는최종조회에서이미없었고,최종image를사용한임시testcontainer도남지않았다. 기존정상DB/volume/image는보존했다.

첫검사실패도로그로남겼다. 새testhelper가정상정리된accepted candidate body를읽으려던가정을고쳤고,존재하지않는test모듈명요청을제외했다. 다음회귀에서공통schemaexporter와달라진불필요한JSONschema설명문을제거해단일schema를유지했다. 입력hash/전달/의미경계검사를약화하지않았다.

## 파일과 실행

주요구현은 `information_errors.py`, `knowledge_runtime.py`, `knowledge_review.py`, `knowledge_requests.py`, `multi_source_prompts.py`, `cli.py`,renderer와관련테스트다. 직접D모듈/테이블/새IPC는없다. 최신결정/기존직접D문서의철회표시/README/AGENTS/목록/계획을함께갱신했다. [정확한계약](../../docs/interfaces/INFORMATION_ERRORS.md).

[UI0.3 실행스크립트](ui/Open-Code-Wiki.ps1)는별도codeWiki연결과app0.14이미지를사용한다. [UI보고서](ui/REPORT.md),[실행파일](ui/app/Palimpsest-win32-x64/Palimpsest.exe). 이전0.2패키지와기본논문연결은그대로다. 기존캐시를사용해새package1개437.19MiB를추가했고다운로드는없었다.

보류범위는해당I2K후보와그검토재개다. 기존K전체의영향분석·상충·일반의미Revision·자동재검토scheduler,오류확인/해소를위한사용자작업UI는후속이다. 원문으로K를우회생성하는복구는후속목록에서도철회했다.
