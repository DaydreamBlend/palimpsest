# 전체 논문·절 입력 조회 검증 — 2026-09-11

일반 논문의 최초 I2K는 **전체 I의 원문을 읽기 순서대로 한 번 제공하고, 모든 원본 페이지 이미지를 별도로 제공하는 방식**을 우선한다. 실제 모델의 텍스트·이미지·출력 한도를 넘으면 절/문단 범위로 나눈다. 이번 작업은 이 입력을 구성하는 읽기 기능이며 모델 전송, K 추출·검증, RAG index, Decision W와 Revision commit은 실행하지 않았다.

이 방식은 source I를 거대한 새 I로 바꾸지 않는다. exact Data/source block/범위/원본 페이지와 parser profile 및 조회 snapshot을 유지한다. canonical 조회는 완료된 단일 source execution의 I에 결속한다. 절 그룹은 RAG·탐색·부분 재검증·긴 문서 분할에 계속 사용한다. [정책과 CLI](../../docs/implementation/SECTION_CONTEXT.md), [실행 계획](../../progress/T03_section_projection_execplan.md).

## 최종 전체 문서 검증

최종 Docker 이미지에 설치된 실제 CLI의 `information sections`와 `information document-context`를 네 문서에 실행했다. 기존 MinerU image200 evidence를 읽기 전용으로 재검증했으며 추가 파싱·GPU 추론·의미 LLM 호출·DB 쓰기는 없다.

| 문서 | 원문 block | 원문 문자 수 | 공백 기준 단어 수 | 별도 원본 페이지 이미지 | 조회 그룹 |
|---|---:|---:|---:|---:|---:|
| Test_Paper | 229 | 63,487 | 8,995 | 14 | 21 |
| Chen, paper02 | 237 | 82,871 | 12,405 | 29 | 22 |
| Clarke, paper04 | 159 | 74,871 | 11,751 | 14 | 20 |
| Dejani, paper05 | 126 | 57,586 | 8,455 | 10 | 5 |
| 합계 | 751 | 278,815 | 41,606 | 67 | 68 |

문자 수에는 원문 block/그룹 사이의 표시용 두 줄바꿈이 포함된다. 공백 기준 단어 수는 모델 token 수가 아니다. 이 숫자만으로 특정 provider의 multimodal 한도 안에 들어간다고 판단하지 않는다.

- 751개 target source block이 중복·누락 없이 한 번씩 포함됐다. 각 원문 span을 전체 text에서 잘랐을 때 원래 block text와 정확히 일치했다. 빈 image 전사도 target/source 참조에서 유지한다.
- 67페이지의 retained 200 DPI PNG descriptor와 원본/파생 좌표 변환이 source bundle과 일치했다. descriptor 준비와 실제 이미지 bytes의 모델 전송은 다르다.
- `section_outline`은 원문 본문을 중복 포함하지 않는다. Figure/panel/crop은 별도 참조 색인이고, 전체 원문 text를 다시 중복 첨부하지 않는다.
- 각 CLI exit0, Test_Paper의 다른 projection SHA는 `section_projection_changed`/exit4로 거부됐다. evidence manifest는 전후 동일했다.
- 단위·회귀 **66 tests, failure0/error0/skip0, 0.258초, exit0**. section/document13, Figure8, 기존 page/paragraph/evidence/CLI45 tests다. canonical 단일 실행 binding은 mock 검사이며 실제 PostgreSQL integration은 이번에 실행하지 않았다.

[최종 전체 조회 결과](whole-document-results.json), [단위 검사](unit-results.json), [Test_Paper 입력 JSON](whole-test_paper/document-context.json), [Chen 입력 JSON](whole-paper02/document-context.json), [Clarke 입력 JSON](whole-paper04/document-context.json), [Dejani 입력 JSON](whole-paper05/document-context.json).

## 절/Figure 조회와 알려진 한계

초기 절 조회 실험에서 68개 그룹 전체의 target/context를 대조했다. 본문 주 Figure 26개 모두 명시적 본문 언급과 같은 번호의 caption anchor 및 기존 visual 제안이 연결됐다. supplementary 참조 21개는 이 PDF 안에서 caption/visual을 찾지 못했다는 warning을 유지한다. 이것은 caption 전체의 충실성 또는 Figure 의미 이해가 26/26이라는 점수가 아니다.

Chen의 번호 없는 caption tail 세 곳은 원문에 보존됐지만 Figure 3/4/5를 다루는 본문 그룹의 context에는 연결되지 않았다. 각각 원본 24/26/28쪽, `/pdf_info/23/preproc_blocks/0`, `/pdf_info/25/preproc_blocks/0`, `/pdf_info/27/preproc_blocks/0`이다. Figure 소속을 추측해서 확정하지 않는다. **최종 전체 문서 조회에는 세 원문과 세 페이지 이미지가 모두 들어갔다.** Figure의 `caption_completeness=not_verified`는 경고가 없어도 전체 caption 검증 완료가 아님을 명시한다.

번호 없는/인라인 소제목은 자동으로 모두 복원하지 않는다. ambiguous/unmatched paragraph 연결은 가능한 source refs와 uncertainty를 유지한다. 절 이름·경계가 사람의 분류와 다른 점과, 원문이 실제로 모델 입력에서 빠지는 문제를 구분한다. 전체 문서 입력도 OCR 자체의 오독이나 모델의 주장 누락을 자동 해결하지 않는다.

긴 문서에서 여러 페이지와 text/image/table 근거를 함께 회수하는 능력은 별도 평가 대상이다. [MMLongBench-Doc](https://arxiv.org/abs/2407.01523)은 이 문제를 다루는 2024년 benchmark다. 그 당시 모델 점수를 현재 미선정 I2K 모델의 품질로 대입하지 않는다.

## 실행과 재현

작업 디렉터리는 저장소 root이며 Windows host Python은 `C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`다. 최종 app image는 `palimpsest-t03-sections:0.3.0`, exact ID는 `sha256:48844a16e0f5977ee0b95f98af89c248be9ac627e557f053a74997ac44325348`이다. 기존 패키지 버전은 0.2.0이고 dependency나 Dockerfile은 변경하지 않았다.

```text
docker build --network none -t palimpsest-t03-sections:0.3.0 .
docker build -t palimpsest-t03-sections:0.3.0 .
docker run --rm --name palimpsest-section-regression-final --network none --read-only --tmpfs /tmp --mount type=bind,source=C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/output/t03-section-projection,target=/opt/palimpsest/output/t03-section-projection --entrypoint python palimpsest-t03-sections:0.3.0 -B output/t03-section-projection/run_tests.py
docker run --rm --name palimpsest-section-whole-cli --network none --read-only --tmpfs /tmp --mount type=bind,source=C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/output/t03-image-default,target=/workspace/output/t03-image-default,readonly --mount type=bind,source=C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/output/t03-qwen9b-extended,target=/workspace/output/t03-qwen9b-extended,readonly --mount type=bind,source=C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/output/t03-section-projection,target=/workspace/output/t03-section-projection -w /workspace --entrypoint python palimpsest-t03-sections:0.3.0 -B output/t03-section-projection/whole_cli.py
python -X utf8 -B tools/validate_bundle.py --json
```

첫 offline build는 dependency layer가 일치하지 않아 pip network 불가로 exit1이었다. 일반 build는 기존 dependency cache를 사용해 exit0이었고, 전체 문서 코드 추가 후 재build도 exit0이었다. registry metadata 조회와 실행 컨테이너의 network-none을 혼동하지 않는다. 단위/전체 CLI 컨테이너는 모두 network-none이며 소스 PDF 외부 전송은 없다. `whole_cli.py`는 결과를 exclusive-create하므로 같은 출력 경로에 다시 실행하면 덮어쓰지 않고 실패한다. 재현에는 새 출력 경로를 사용해야 한다.

초기 host 단위9개는 psycopg 미설치로 CLI import1 error였고 나머지8개는 통과했다. host corpus 실행은 첫 PYTHONPATH 누락, 이어 Linux 전용 secure I/O의 `os.O_DIRECTORY` 미지원으로 실패했다. 지원 환경인 Docker에서 전수 검사했고 보안 검사를 약화하지 않았다. 이전 65 tests 결과와 초기 코드/실험 JSON은 그대로 보관했다.

`run_corpus.py`와 초기 `projection.json`/`example-context.json`은 mandatory SHA와 전체 문서 경로 추가 전 코드 결과다. 당시 코드는 `initial-code/`에 보존했다. `final-cli-results.json`도 최종 whole-document 추가 이전의 section CLI 확인이며, 최신 결과는 `whole-*/`와 `whole-document-results.json`이다. 이후 더해진 caption completeness 표기 등으로 조회 SHA가 달라졌으므로 과거 SHA를 현재 결과처럼 쓰지 않는다.

## 자원·완료 범위

작업 전 7containers/15images/35volumes → 작업 후 7containers/16images/35volumes. 이번 검증용 컨테이너는 `--rm`으로 모두 제거됐고, 추가 잔여는 검증된 최종 이미지 하나뿐이다. 중간 이미지 ID는 최종 조회 때 이미 존재하지 않았다. 기존 자원 삭제나 global prune은 실행하지 않았다. [Docker 전후 대조](docker-audit.json).

문서 validator는 기존 12개 raw/과거 실험 Markdown 표 서식 오류로 exit1이며, 과거 산출물이나 검사 기준을 고쳐 숨기지 않는다. 새 문서/링크의 추가 오류 여부는 [최종 문서 검사](document-validation-final.json)에 기록한다. 전체 문서 mutation suite나 PostgreSQL integration, 새 parser/LLM 실행은 이번 범위에서 반복하지 않았다.

후속 T04는 실제 모델 profile의 입력 예산과 전달을 검사하고, 구조화된 K 후보에 exact source 근거를 남긴다. 전체 입력도 한 응답의 K 완결성을 보장하지 않으므로 미처리/미검증 범위를 추적해야 한다. LLM wiki의 K 의미 Revision, RAG의 검색 당시 snapshot, 실제 사용한 근거와 authority-confirmed Decision W의 행위자 이유/당시 Context는 별개로 보존한다. 이번 읽기 hash 변화는 K Revision이나 결정 이벤트가 아니다. T03 전체 gate와 T04 acceptance는 일괄 pass로 바꾸지 않았다.
