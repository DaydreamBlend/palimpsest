# Python 코드 D2I → I2K 검토 재개 → K2K/Wiki/RAG/Electron

2026-09-13. App **0.13.0**, Electron UI **0.2.0**, PostgreSQL schema **0013 유지**. 사용자에게 권고한 후속 범위 중 Python native source parsing, 전체 I2K 검토 재개, exact K2K/자료 버전의 Wiki 검색·읽기 화면을 연결했다. 이후 roadmap 전체 완료 보고가 아니다.

## 실제 완료 동작

| 단계 | 실제 결과 |
|---|---|
| D | 기존 승인 코드 A의 등록 D를 사용. 새 D 0개, 기존 A→B→A 자료 이력과 V3 head 보존 |
| D2I | Python stdlib AST/tokenizer로 28 I 저장. 원문 101,675 bytes의 전체 재조립 일치, application LLM 0회, OCR 0회 |
| I2K 1차 | 모든 28 I 전달·검토. 신규 K 8개, 기존 K 재사용 7건. 추가 검토가 필요한 I 21개를 `needs_human`으로 보존 |
| I2K 재개 | 같은 전체 28 I·source 실행·V3·실제 검증 이유를 유지. 신규 K 8개 추가, 28 I 모두 검토 완료, pending I/target/item 0개 |
| K2K | 승인·재사용된 exact KRevision 23개를 입력으로 검토. 전제 2개에 기반한 새로운 연역 K 1개와 실제 검증·가정·한계 저장 |
| Wiki | 코드 자료 페이지 1개, 검증된 항목 18개. 1차 서술/인용 오류와 2차 추가 인용 지적을 보존하고 3차 인용 보완 후 compiled |
| 검색 | 전체 I 28개 + 현재 선택 source/버전의 K 24개 + Wiki 항목 18개 = 70문서, BGE-M3 검색 창 125개. 추론 K 1개 포함 |
| 실제 질의 | BGE dense/ColBERT 검색 → 9 I·4 K 입력 → Terra 답변·독립 검증. `answered`, canonical 쓰기 0회, D2I 재호출 0회 |
| Electron | 코드 Wiki, native 파일/줄/byte 원문, 추론 origin/전제, 과거 I, 검토 이력의 실제 source 및 Windows package 동작 검증 |

최종 Windows package의 [실제 결과](../t13-code-review-ui/code-packaged-query-020-final/result.json)는 현재 버전의 새 추론 K와 위 live query까지 통과했다. [실제 답변 화면](../t13-code-review-ui/code-packaged-query-020-final/06-accepted-inference-query.png), [원문 확인 화면](../t13-code-review-ui/code-packaged-query-020-final/07-query-retained-source.png)을 보존했다. renderer error0, source/ASAR 검사각18/18이다. package ASAR SHA는 `ea8b08aac2ef0c9c1d93e61a54cf581de4e1b78efc58bc903be232209d93ce31`이다.

이 실험은 승인된 **두 Python 모듈과 EXPERIMENT.md**가 들어 있는 통제 사본이다. 전체202파일 코드베이스의 의미 분석 완료나 모든 코드/문서에 대한 의미 회수율 증명이 아니다. 이전 Markdown 기반 V1/V2 검토 상태도 덮어쓰지 않았다. 화면에 보이는 첫 실행의 `needs_human`/21 I는 당시의 보존 기록이고, 이번 source의 두 번째 실행은 completed다.

## D2I의 모델 경계와 원문 보존

`python-code-groups-v1`은 함수·클래스·decorator·설정/관련 정의와 원래 순서를 바탕으로 묶는다. 작은 인접 정의는6,000문자 soft target이며 긴 함수 내부를 길이만으로 자르지 않는다. 이번 source는 Python 그룹23개, opaque member1개, dossier framing/manifest4개다. 가장 긴 I는12,713문자로 원래 큰 함수를 유지한 결과다. 주석·공백·BOM/CRLF·문법 오류·미지원 언어·빈 member도 보존 대상이다.

원본 member 경로/SHA, global·member byte/char/line 범위, 심볼·enclosing context가 I의 payload/grounding/input에 이어진다. D2I는 코드를 실행하거나 중요도를 판단하지 않는다. Python 외 언어는 이 범위에서 native 문법 해석을 제공하지 않고 원문 보존을 표시한다. 임의 Python 파일은 현재 등록된 dossier 계약을 거쳐 입력한다.

**제품 D2I에는 Terra나 별도 Qwen/Gemma 의미 LLM이 필요하지 않다.** PDF는 기존 선택한 MinerU 내부 OCR/layout VLM을 사용하고 나머지 조립·청킹·구조 검증은 스크립트다. 개발 중 의미 품질 평가를 source I 생성의 필수 model gate로 만들지 않았다. I2K·query가 근거 부족 때문에 D2I를 호출하는 경로도 추가하지 않았다.

## 정확한 결과와 이력

- Data A: `dfbb33fbd8966f392582c8d72c32f7e1136ca212cdfcf5e5ae1e3d7cabb6859f`
- native source execution: `01a09a68-700c-7c5c-bbd2-1e4bd31f9cd5`
- I2K 1차: `01a09a69-26ac-73be-9326-75771045ce6f`; 재개: `01a09a74-ee55-7578-ad33-3ac3960fa25f`
- 새 K2K Revision: `01a09a81-9c28-79e5-9878-92218e97230b`
- Wiki: `01a09a84-f980-7dde-97af-2c3f0944c28f`; 검색 index: `01a09a85-17bc-775a-81fb-d7d57f4c715e`
- 검증된 질의: `01a09a86-bb46-7f91-944f-e44d734f3d55`

새 K2K는 “준비 때 캡처한 knowledge-state version과 다르면 committed decision을 결정할 수 없다”는 범위가 제한된 연역이다. 정확한 전제2개, 실제 K2K 생성 Record, `is_inferred=true`, 필요조건이라는 가정과 비실행·V1 구현 범위의 한계를 보존한다. 직접 I grounding은0개이며, transitive source refs3개가 실제 전제 근거로 이어진다. 이를 원문에 직접 적힌 새 관찰로 위장하지 않는다.

[읽기 전용 이력 검증](history-verification.json)의137개 assertion은 과거16개 행 묶음 hash,3 D, A→B→A3version/V3head, 기존214 I와 새28 I, exact Record→KRevision 연결23건, 새 추론 계보를 검증했다. 기존 모든 비교 hash가 일치했고 검증 전후 DB 상태가 같았다. 현재 실험 DB에는 총42 K/42 Revision,3 derivation이 있다. 이는 다른 논문 DB의 전체 개수가 아니다.

## 질의 결과

[실제 검증된 답변](query-store/queries/01a09a86-bb46-7f91-944f-e44d734f3d55/rounds/0/answer.md)은 source I에서 확인되는 version 검사와 기존 accepted K2K의 결론을 별도 claim으로 제시했다. 후자는 exact KRevision·두 전제 Revision·가정/한계를 포함하며 독립 Validator의 `accepted_inference_faithful`와 `inference_limits_preserved`도 통과했다.

source-only의 과거 query bytes는 유지하고, 지원되는 context만 `wiki-query-answer-v2`를 사용한다. query는 새로운 추론을 만들거나 K를 자동 승격하지 않는다. 현재 source/버전의 완전한 accepted support 경로가 없는 K는 검색 corpus에 포함하지 않으며 historical index/기원은 보존한다. 빈 I는 원문을 발명하지 않는 명시적인 metadata descriptor로 검색한다.

## 검증과 실제 호출

| 종류 | 명령/결과 |
|---|---|
| 최종 앱 이미지 전체 회귀 | `PALIMPSEST_APP_IMAGE=palimpsest-code-wiki:0.13.0 docker compose -p palimpsest-multi-checks run --rm --no-deps -T --entrypoint python app tools/run_app_tests.py`:831개,815 pass/16 skip,365.286초,exit0 |
| 별도 PDF runtime | 기존 `palimpsest-mineru-hybrid:3.4.5-pro2605`에서 `python -B -m unittest test_pdf_raster test_pdf_text_evidence test_pdf_visual_evidence -v`:22/22 pass,0.817초,exit0 |
| 신규 집중 검사 | review request 변조·current inference retrieval·query:35/35 pass,38.482초 |
| 실제 DB 보존 | `verify_history.py`:137 assertion pass, 읽기 전용 |
| Electron/Node | source 및 ASAR HTML/renderer 검사18/18, 실제 source/package 읽기 흐름과 PNG 검증은 [UI 결과](../t13-code-review-ui/app/REPORT.md) |
| 문서 Markdown 검사 | `PYTHONPATH=tools python -m unittest test_validate_bundle.MarkdownChecks -v`:7/7 pass |
| 전체 문서 bundle | `python tools/validate_bundle.py --json`:exit1, 기존 vendor/raw/복제문서 관련948오류. 현재 작성 문서 오류0; 앱 통과와 혼동하지 않음 |

PDF22개 중16개는 core skip을 보완하고6개는 겹치는 검사다. 별도 검사 숫자를 새 고유 case처럼 합산하지 않는다. 도구 bundle mutation suite 전체는 `desktop/node_modules/.local`까지 복사하는 기존 방식이므로 반복 실행하지 않았고, 이번에 validator 자체를 수정하지 않았다.

실제 Terra 호출은 **14회**: I2K4, K2K2, Wiki6, query2다. 각 호출의 실제 input/output/schema/전달 I/K/version 결속과 usage는 [actual-summary.json](actual-summary.json)에 검증해 모았다. D2I0회와 구분한다. 작은 통제 source에도 정확 근거/profile/이전 검토를 반복한 입력이 크므로 입력 projection의 중복 최소화는 후속 성능 최적화다. 구조 검증·독립 모델 검증이 의미 정확성의 절대 보증은 아니다.

## 실패와 복구를 보존한 부분

- 초기 합성 review/desktop fixture의 receipt에 version 전달 목록이 빠져5개 오류가 발생했다. fixture를 고치고 관련7개, 이후 변조 검사 포함8개 및 전체 suite를 통과했다. production 검증을 완화하지 않았다.
- I2K export를 이미 사용 중인 결과 폴더에 하려다 거부됐다. 별도 managed `call/`을 사용했다. 변조된 request와 binding을 함께 고쳐도 재구성된 원래 요청과 다르면 거부하는 검사를 추가했다.
- I2K 원문 동일성, Wiki 생성, query 생성의 자동 승인 검토 차단을 보존했다. 동일성 검증 또는 사용자의 해당 준비 파일에 대한 명시 승인 이후에만 실제 전송했다. 차단된 시도는 호출 수에 포함되지 않는다.
- Wiki1차3개,2차1개 보류는 실제 의미/인용 지적이다.3차는 본문을 고정하고 부족한 상수 정의 인용만 보완하여 통과했다. 과거 출력/실패 이유는 유지했다.
- 실험 wrapper가 성공한 Wiki DB sync 결과 파일을 두 번 쓰려다 두 번째 쓰기에서 `FileExistsError`가 났다. 원자적 sync와 첫 결과 파일은 이미 성공했고, 중복 write를 제거했다. 이후 corpus/실제 UI에서 exact sync를 검증했다. DB 실패나 rollback으로 표시하지 않는다.
- 최초 Electron 화면 검사는 sandbox의 Docker pipe 접근 거부로 연결 대기 timeout이 났다. 기존 승인된 Docker 실행 경로로 source/package 검사가 통과했다. 앱 DB/원문 손상으로 오인하지 않는다. 테스트의 실패 캡처와 query claim 범위 selector도 실제 결과에 맞게 고쳤다.

## 용량 정리

61.246GiB 중53.644GiB가 로컬 모델 디렉터리였다. 사용자가 현재 역할이 없으면9B Q8까지 제거하도록 승인한 뒤, Qwen/Gemma 가중치9개 **47.395GiB**를 제거했다. 대상의 실제 SHA를 저장하고 남은65개 metadata 파일 hash를 전후 비교했다. MinerU/Pro·BGE·Paddle, 원본·parse·I/K/판정/실패·실험 기록은 보존했다.

정리 후 폴더는 **약14.293GiB**다. 새 Electron package 약458MB가 병행 생성되어 단순 전후 차감과 약간 다르다. [용량 원인](disk-usage.md), [정리 결과와 검증](model-cleanup.md)을 확인한다. 과거 Qwen/Gemma 실험 재실행에는 가중치 재확보가 필요하다. 이번 새0.13 초기 image는 최종 빌드 후 Docker 조회에서 이미 존재하지 않았고, 이번 --rm 테스트 container는 남지 않았다. 기존 정상 image와 DB volume은 보존했다.

## 실행과 남은 범위

저장된 새 코드 Wiki를 여는 PowerShell launcher는 [Open-Code-Wiki.ps1](Open-Code-Wiki.ps1)다. [별도 연결 설정](desktop-connection.json)을 사용하며 기존 논문 Wiki 기본 연결은 바꾸지 않는다. Docker Desktop이 실행된 일반 사용자 PowerShell에서 `& ./output/t13-code-review-wiki/Open-Code-Wiki.ps1`로 시작한다. 창의 질문 기록에서 위 실제 질의 답변을 읽을 수 있다.

변경한 주요 application 경로: `code_adapter.py`, `d2i.py`, `compiler_runtime.py`, `i2k.py`, `source_reconstruction.py`, `knowledge_review.py`, `knowledge_runtime.py`, `knowledge_prompts.py`, `multi_source_prompts.py`, `cli.py`, `wiki_retrieval.py`, `wiki_query.py`, `wiki_query_runtime.py`, `paper_wiki.py`, `paper_wiki_prompts.py`, `paper_wiki_runtime.py`, `wiki_archive.py`, `desktop_read.py`, desktop renderer/security/tests와 CLI host `tools/ask_wiki.py`. [구현 계약과 CLI](../../docs/interfaces/CODE_REVIEW_WIKI.md)를 따른다.

직접 D canonical grounding, 여러 언어 native parser, 일반 K 의미 개정·상충/시간, 전체 변경 영향 scheduler, GUI 등록/검토/질문 실행, 개인 Decision/W2K, HTML/인터넷 자동 수집, source별 증분 index는 이번 수직 범위의 완료 항목이 아니다. 이전 full202-file I2K 미전송 작업도 그대로 보존했다.
