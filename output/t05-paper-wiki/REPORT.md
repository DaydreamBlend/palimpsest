# 논문별 Wiki와 공통 주제 문서 — 구현·실물 결과

2026-09-12. 기존 완료 source 3편의 전체 87 I를 사용해 **논문 페이지3개·주제 페이지22개·본문 항목37개**를 만들었다. 같은 Terra Medium의 별도 Generator/Validator 호출과 구조 검사, source-I 독립 검토를 거쳤다. 이 첫 구현은 canonical D/I를 읽는 비canonical Wiki projection이며, 새 KNode·KEdge·Parchment를 저장한 결과는 아니다.

[현재 Wiki 목차](wiki/exports/b8894b5d5542325e6fdb730251fe2c289c7b1d399aa6598c867992d2d0e7ad1d/index.md)에서 결과를 읽을 수 있다. export 폴더는 논문·주제 Markdown, 원본 PDF3개, manifest를 포함하며 Obsidian wikilink로 연결된다. 별도의 GUI·웹 서버·crawler는 시작하지 않았다.

| 원문 | 페이지 | 입력 I | 입력 이미지 | 최종 본문 항목 | 인용 |
|---|---:|---:|---:|---:|---:|
| Test_Paper | 14 | 36 | 50 | 13 | 24 |
| Clarke | 14 | 35 | 22 | 12 | 23 |
| Dejani | 10 | 16 | 22 | 12 | 25 |
| 합계 | 38 | 87 | 94 | 37 | 72 |

## 실제 문서와 공통 페이지 갱신

- [Test_Paper 논문](wiki/exports/b8894b5d5542325e6fdb730251fe2c289c7b1d399aa6598c867992d2d0e7ad1d/papers/01a09388-351f-75a8-84e9-aaea17f5d21f.md)
- [Clarke 논문](wiki/exports/b8894b5d5542325e6fdb730251fe2c289c7b1d399aa6598c867992d2d0e7ad1d/papers/01a093b8-9ef5-7d43-8abc-06b6798224e5.md)
- [Dejani 논문](wiki/exports/b8894b5d5542325e6fdb730251fe2c289c7b1d399aa6598c867992d2d0e7ad1d/papers/01a093c7-30f1-7dc9-8d86-2d9deb4cc2fe.md)
- [BMDC 주제](wiki/exports/b8894b5d5542325e6fdb730251fe2c289c7b1d399aa6598c867992d2d0e7ad1d/topics/01a093c7-311c-744c-8f56-c1cb70706e35.md)
- [Human monocyte-derived DC 공통 주제](wiki/exports/b8894b5d5542325e6fdb730251fe2c289c7b1d399aa6598c867992d2d0e7ad1d/topics/01a093b8-9f7d-7b31-acff-50c44a8998fe.md)
- [Th17 공통 주제](wiki/exports/b8894b5d5542325e6fdb730251fe2c289c7b1d399aa6598c867992d2d0e7ad1d/topics/01a093b8-9fe0-7f88-8581-7793a9ea06a2.md)

BMDC의 직접 실험 근거는 이3편 중 Dejani에 있다. Clarke의 human monocyte-derived DC나 Test_Paper의 pDC/cDC를 BMDC로 잘못 묶지 않았다. BMDC는 원문에 맞는 별도 페이지로 만들고, 실제 공통 페이지 갱신은 human monocyte-derived DC와 Th17에서 확인했다.

두 공통 페이지는 Clarke만 있던 snapshot에서 Dejani를 포함한 새 snapshot으로 바뀌었다. **page UUID는 같고 출처가1→2로 늘었으며, 이전 논문 contribution은 그대로 유지됐다.** [실제 이력 검사](common-page-history-verification.json)에 두 snapshot ID와 보존 결과가 있다. 공통 페이지는 검증된 항목을 논문별로 모으며 서로 다른 실험을 같은 K로 병합하거나 새 통합 결론을 만들지 않는다.

## 구현한 경로

`wiki prepare → request → Generator → stage → Validator → decide → export/history`를 Python CLI에 추가했다. 프로그램이 문서 형식·UUID·정확 인용·current catalog·immutable snapshots를 관리하고, 모델은 전체 I의 중요 내용과 분류를 제안한다. accepted 문서는 개요·방법·주요 결과·한계의 고정된 순서로 렌더링하고, 해당하는 내용이 없는 섹션은 생략한다. 이미지·본문·원본 source refs는 입력과 이력에 보존한다.

Source 입력과 실제 모델 receipt는 profile/input/prompt/schema/output/image hash 및 전체 I ID 목록에 연결된다. 각 I의 review가 존재하고 실제 근거의 사용과 일치해야 한다. 고정한 제안과 다른 내용을 Validator 판정으로 반영하려는 변경, source owner 변경, media byte 변경, 오래된 catalog에 대한 뒤늦은 반영을 거부한다.

실제 실험에서 전체 원고를 다시 작성할 때 이미 보완한 인용이 빠지는 회귀가 나타났다. 이를 해결하기 위해 인용을 추가할 때 기존 본문·주제·인용을 고정하는 `--citation-repair`를 구현했다. 문구도 수정해야 하면 `--repair-item`으로 허용할 item만 명시한다. [인용1개 추가 검사](clarke-citation-repair-verification.json)와 [지정한 문구1개 수정 검사](clarke-item-repair-verification.json)는 나머지 내용을 그대로 유지했음을 확인한다. 두 경우 모두 새 전체 Validator를 통과해야 한다.

[사용자 CLI 문서](../../docs/interfaces/PAPER_WIKI_PROJECTION.md)에 Docker image 선택, mount, 일반 편집과 범위 제한 보완, 실패·재시도·과거 export 사용법을 기록했다. 기본 Compose image는 바꾸지 않았으며 이번 기능은 `palimpsest-wiki:0.6.0`을 명시해 사용한다.

## 의미 검증과 실제 반복 결과

이번 실험에는 성공·보류·구조 거부를 포함한 **실제 provider 호출22회**가 있었다. 이를 무인 첫 시도 성공률이나 모델 벤치마크 점수로 해석하지 않는다. 개발 중 발견한 문제를 수정하고 평가자가 명시적 피드백을 제공한 실험이다. 실제 모든 호출은 기존 Codex OAuth의 `gpt-5.6-terra`, reasoning `medium`, CLI `0.153.4`다.

- Test_Paper는4번째 요청에서 반영됐다. 인용 부족, 투여 후와 질병 해소 후의 시간 기준 혼동, continuation 근거를 보완했다. 한 요청은 전체 I의 used 검토와 실제 citation이 달라 구조 거부됐다. [최종 source-I 감사](semantic-audit-test-paper-04.md).
- Clarke는7번째 요청에서 반영됐다. 주제 정의 충돌, 처치 순서, 평균/개별 donor 표현, 앞 문단·용량 인용, 개별농도가 명시되지 않은 값의 배정을 수정했다. 후반 두 요청은 인용 추가1개와 지정된 문구1개만 바꾸는 새 편집 경로로 수행했다. 기존 CD86L 표기는 유지했으며, 원문 약어표에도 관련 표기가 있어 이를 OCR 오류로 단정하지 않았다. [인용 보완 감사](semantic-audit-clarke-06.md), [한정된 문구 교정 확인](clarke-item-repair-verification.json).
- Dejani는2번째 요청에서 반영됐다. 기존 주제 scope를 덮어쓰지 않고 올바른 개념으로 분류했으며 BMDC 페이지를 만들었다. CM 대조·PGE2 변화·세균수 결과에 필요한 앞 문장을 인용했다. [최종 source-I 감사](semantic-audit-dejani-02.md).

Validator가 accepted로 판단했어도 독립 감사에서 인용 부족이 발견된 사례가 있었다. 따라서 정형 JSON과 별도 모델 검증만으로 의미 정확성을 보장할 수 없다. 현재 문서는 원문에 근거한 연구 자료 정리이며, 논문 전체·모든 Figure의 재검증이나 과학적 사실의 확정을 뜻하지 않는다. 일반 topic scope는 재사용 가능한 개념으로 개선했지만 초기의 좁은 topic 정의는 이력으로 보존한다. 기존 주제의 명시적 정의 확장·alias 정책은 후속 검토 사항이다.

최종 job 이력은 compiled3, needs_review5, failed4, proposed1이다. 과거 보류·실패·미반영 초안도 보존한 수치다. Clarke5의 proposed 초안은 별도 Validator가 accepted로 판정했지만 독립 감사에서 R848의 item 인용 부족이 발견돼 반영하지 않았다. 그 문제와 뒤의 문구 문제는 새 요청6·7에서 보완했다. 현재 catalog는 각 논문의 최신 반영3건만 선택한다.

## 실제 검사와 보존

[전체 검증 JSON](verification.json)은 다음을 확인한다.

- 기존 canonical I와 입력 packet이 정확히 같고 전체87 I의 review가 있다.
- 인용72개가 지정 I의 exact char range 및 source refs와 일치한다.
- 원본 PDF3개의 SHA-256이 등록 Data ID와 같다.
- Wiki 링크73개 및 원본 PDF 페이지 링크가 실제 파일과 범위에 연결된다.
- 같은 catalog/renderer의 export가 동일 bytes로 재생성된다.
- 공통 페이지는 해당 논문에서 검증된 items만 복사하며 snapshot hash chain이 유효하다.

[DB 전](database-before.json)·[DB 후](database-after.json)를 대조한 결과 **Canonical/Compiler32개 테이블의4,427행이 모두 동일**했다. 새 D2I 호출·canonical migration·K/P/W 쓰기는0이다. source Artifact Store를 읽기 전용으로 mount했다. 완료된 실제 Clarke의 prepare/stage/decide도 재생하여 같은 페이지·snapshot·commit 결과를 반환하고 current catalog3을 바꾸지 않음을 확인했다.

최종 Docker image는 `palimpsest-wiki:0.6.0`, ID `sha256:c82bf4c95b68cdbc8c2707b605bc0aaf3edf286fe698ecf5bd1b870acd0fa07e`다. [최종 앱 검사 로그](app-tests-release-complete.log)는 **555개 실행,539 pass/16 skip, 실패·오류0,90.078초,exit0**이다. Wiki Runtime 대상23개 중2개는 실제 PostgreSQL D/I 검사이고21개는 canonical 조회를 mock한 실제 Linux 저장소 검사다. 회귀 검사의 모델 receipt는 합성이며 위22회 실제 호출과 구분한다.

정확한 실행 명령·결과는 각 `runs/<paper>-<attempt>/logs`와 build/test 로그에 보존한다. 주요 명령은 다음과 같다.

```powershell
docker build -t palimpsest-wiki:0.6.0 .
$env:PALIMPSEST_APP_IMAGE = 'palimpsest-wiki:0.6.0'
docker compose -p palimpsest-multi-checks run --rm --no-deps -T test
python tools/run_knowledge_model.py <request.json> --codex <approved-codex-executable>
python tools/validate_bundle.py
python -m unittest discover -s tools -p "test_*.py"
```

문서 bundle validator는 보존된 raw Markdown 표의 기존 오류12개로 exit1이다. Windows 문서 mutation 검사는44개 실행에서 기존 문서 오류1 failure와 긴 fixture 경로·격리된 provider 임시폴더 복사의70 errors로 실패했다. 문서 검사나 앱555개를 서로의 대체 증거로 사용하지 않는다. [실행 환경·검사 요약](runtime-verification.json)에 구분했다. 이 문제 때문에 원본 parser raw를 수정하지 않았다.

모든 문서와 Wiki export를 작성한 뒤 validator를 다시 실행해 [작업 전후 오류 집합이 동일하고 새 오류0개](document-regression-verification.json)임을 확인했다. 이는 기존12개 오류를 해결했거나 전체 문서 검사를 통과했다는 뜻은 아니다.

이번 Wiki 실행 컨테이너는 모두 `--rm`으로 종료 시 제거됐다. 최종 image는 남겼고 dangling image 조회 결과는0이었다. 기존 정상 DB·image·모든 volume 및 사용자 artifacts는 보존했다. 저장소에는 Git이 없어 git diff/commit 검증을 실행했다고 주장하지 않는다.

## 남은 범위

정식 P의 W 없는 입력 계약과 canonical publication DB 통합, 기존 KRevision을 페이지에 연결하는 편집 경로, I embedding 검색·자연어 답변, 자동 웹 수집·스케줄러·GUI는 아직 이 첫 slice에 포함하지 않는다. 기존 T10의 AT54/AT61/AT62/AT72/AT78/AT83/AT104와 T12 전체 release gate를 이번 Markdown 결과로 완료 처리하지 않는다. 기존 보존 DB의0007 승인 대기는 이번 읽기 projection으로 변경하지 않았다.

모듈·CLI·tests의 변경 파일과 결정 범위는 [실행 계획](../../progress/T05_paper_wiki_execplan.md)과 [착수 기록](../../docs/decisions/PAPER_WIKI_PROJECTION.md)에 연결했다. 다음 구현은 현재 페이지 identity와 source provenance를 유지하며 canonical K/Revision 및 publication 저장 계약을 연결하는 범위다.
