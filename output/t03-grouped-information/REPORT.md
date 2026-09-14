# 그룹 I 저장 결과 — 2026-09-11

**Test_Paper의 새 source 실행은 229개 원문 블록을 22개 canonical I로 저장했다.** 절·문맥 그룹21개와 page furniture1개이며, 원문·이미지·페이지·grounding은 모두 보존했다. [그룹별 길이와 구성](paper-attempt-01/GROUPS.md), [실물 검증 JSON](paper-attempt-01/verification.json), [실제 I2K 준비 입력](paper-attempt-01/i2k-input.json), [CLI/저장 사용법](../../docs/implementation/GROUPED_INFORMATION.md).

## 실물 저장·입력 결과

| 항목 | 결과 |
|---|---:|
| 원문 페이지 | 14 |
| 과거 세부 I | 229 |
| 새 grouped I / D2IRecord / outbox | 각각22 |
| 새 block grounding | 229 |
| 반영 후 임시 candidate | 0 |
| 원문 문자 | 63,031 |
| 그룹 content 총 문자 | 63,445 — 구분자414자만 추가 |
| I 길이 최소 / 중앙 / 최대 | 181 / 2,356 / 8,054자 |
| 이미지 | 36개 모두 실제 bytes/SHA 확인 |

새22개는 `kind=text`인 혼합 그룹이며 이미지36개는 해당 I의 source_artifacts/media로 들어간다. 이미지가 없어진 것이 아니다. 14페이지 조회의 이미지 SHA 집합도 전체36개와 일치한다. 기존 Test_Paper bundle은 required_figures inventory가 없으므로 검증되지 않은 Figure 소속을 추측해서6개 Image I를 새로 만들지 않았다.

PostgreSQL18.6/pgvector0.8.6에서 설치된 `palim compile regroup`, `information prepare-input`, `pages`, `prepare-source`를 실행했다. 새 실행과 재시도는 같은22개 I UUID를 반환했다. 과거229개 I/grounding 전체 snapshot digest는 전후 `88a1d6fa972c7a11b46b8288a4ba6159d875e6dc95c27092c233801dead0838b`로 동일했다. 원래 parser bundle과 파일 manifest도 같았다. 새 조립 실행이 부모 execution/profile/parse SHA를 인용하며 원래 parser receipt를 재작성하지 않는다.

원문63,031자는 그룹 content의 exact 문자 구간에서 모두 복구했다. 초기 I2K 입력에 원본 PDF와 전체 페이지 raster는 없고, fixture의 명시적 원본 요청에 등록 PDF3,890,649 bytes를 로컬 준비했다. 모델 전송/판단은 하지 않았다. 전체 실물 검증37.70초는 frozen parser 재생·DB 저장·조회 시간이며 새 PDF 파싱이나 LLM latency가 아니다.

이 검증은 사용자 live DB가 아닌 작업 전용 DB에 과거 source 실행을 재생한 뒤 새 그룹 실행을 만든 것이다. 신규 직접 grouped 저장도 별도 PG 테스트에서 검증했다. 기존 I 이력 삭제가 승인된 것으로 해석하지 않았다.

## 추가3편 순수 함수 확인

기존 image200 결과를 읽어 같은 스크립트를 적용했다. 세 편은 DB에 저장하지 않은 그룹 제안 검증이다. source bundle 파일은 쓰지 않았고, 모든522개 block의 단일배정·원문 문자범위 복구·이미지 `(block,path,SHA)` 참조가 일치했다.

| 논문 | 페이지 | 원문 block → 그룹 I | 그룹 길이 중앙 / 최대 | 이미지 참조 |
|---|---:|---:|---:|---:|
| Chen | 29 | 237 → 23 | 1,470 / 24,816자 | 10/10 |
| Clarke | 14 | 159 → 21 | 1,755 / 19,849자 | 8/8 |
| Dejani | 10 | 126 → 6 | 9,736 / 19,528자 | 12/12 |

원문/group content 총 문자: Chen82,399/82,827, Clarke74,555/74,831, Dejani57,336/57,576. 차이는 구분자뿐이다. source_groups의 build/verify/segments 순수 함수 실행은 exit0, 약0.156초였다. parser/model/DB 호출은0이다. 입력 위치는 기존 [4편 조회 검증](../t03-section-projection/whole-document-results.json)의 frozen source를 따른다.

남은 구조 한계도 유지한다. Chen의 번호 없는 caption tail3개는 읽기 순서상 References 그룹에 포함된다. 원문은 모두 있지만 그룹 제목만으로 참고문헌이라 단정하거나 처리에서 제외하면 안 된다. Dejani의 소제목 누락으로 Results/Discussion/Methods 일부는 긴 I다. 제목·경계는 스크립트가 읽는 구조이며 의미 승인/완벽한 문맥 구분의 증명이 아니다. 더 작은 모델 입력이 필요하면 exact source range를 이용한 후속 입력 window가 필요하다. 현재 T04 준비는 선택된 I 전체를 반환한다.

## 검사·실패·수정

- 소유 모듈 단위22개(source_groups8+기존 source_units14) 통과,0.267초. 초기 신규 Counter fixture 오류1건은 수정했다. 초기35개 host 묶음 검사에는 psycopg 미설치로 기존 section Runtime import1 error가 있었으며 지원 환경 Docker에서 다시 확인했다.
- Docker의 변경 코드/실제 격리 PG targeted58개 통과,5.011초. 그룹별 I/Record/outbox, 전부 남은 grounding, source ranges/media, legacy payload/입력 불변, stale receipt, 원자적 실패/재시도, 실제 CLI를 포함한다.
- 첫 전체353개 검사: failures0/errors3/skipped16, exit1. 다른 parser worker의 임시 ROOT fixture에 새 조립 모듈3개가 빠져 파일 해시를 읽지 못했다. [실패 결과](app-tests-fixture-failed.json), [로그](app-tests-fixture-failed.log)를 보존했다. 실제 worker의 파일 검사나 source 보존 검사를 완화하지 않고 fixture를 보완했다.
- 최종 전체 **353개: failures0/errors0/skipped16**,28.900초,exit0. [기계판독 결과](app-tests.json), [전체 로그](app-tests.log). Linux 파일/실제 PostgreSQL/동시 regroup/rollback/CLI를 포함한다. skips16은 별도 PDFium native renderer 환경용 기존 검사이고 parser/renderer 본문을 새로 실행한 것이 아니다.
- 독립 검토에서 native parser runner의 새 application import 의존성을 제거했고, 같은 파일에 지원 algorithm을 명시해 소스 mount가 없는 과거 native 옵션도 유지했다. 앱 모듈이 import 불가인 조건의 회귀 검사를 추가했다. 동시 regroup 성공 응답에 ID가 빠질 수 있는 replay 경로도 보완하고 두 요청이 같은 ID/단일 effects를 받는 PG 검사를 통과했다.
- 문서 validator는 기존 raw/oracle Markdown12개 오류로 exit1이며 새 오류는 없다. [문서 검사](document-validation.json). 원본 raw를 수정하거나 검사 기준을 완화하지 않았다.

## 명령·환경·정리

기존 성공 앱으로 아래 격리 project의 migrate를 실행해0003 source schema를 적용했다. SQL/migration·dependency·Dockerfile은 변경하지 않았다. 최종 앱 image는 `palimpsest-grouped-i:0.2.0`, ID `sha256:c3c5823bc706abc637482bf0dae22157453f7a2f81ef6af05e847dd615845cae`다. Compose 기본 앱 tag도 이 성공본을 선택한다.

```powershell
$env:PALIMPSEST_APP_IMAGE='palimpsest-t04-input:0.2.0'
docker compose -p palimpsest-grouped-i run --rm -T migrate
docker build -t palimpsest-grouped-i:0.2.0 .
$env:PALIMPSEST_APP_IMAGE='palimpsest-grouped-i:0.2.0'
docker compose -p palimpsest-grouped-i run --rm --no-deps -T --volume 'C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/output/t03-grouped-information:/results' --entrypoint python app -B /results/run_tests.py
docker compose -p palimpsest-grouped-i run --rm --no-deps -T --volume 'C:/Users/DaydreamBlend/Desktop/Test_Paper.pdf:/source.pdf:ro' --volume 'C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/output/t03-image-default:/frozen:ro' --volume 'C:/Users/DaydreamBlend/Documents/Codex/Palimpsest/output/t03-grouped-information:/results' --entrypoint python app -B /results/test_paper.py
docker compose -p palimpsest-grouped-i down --volumes
python -X utf8 -B tools/validate_bundle.py --json
```

migrate/build/최종 suite/Test_Paper/정리는 모두 exit0이었다. 재현할 때는 과거 실행 로그 보존을 위해 새 output 경로를 사용한다. parser/PDF 원본은 read-only mount이며 외부 provider로 전송하지 않았다.

[소유권 대조](cleanup-preflight.json) 후 테스트 컨테이너2개·볼륨4개·네트워크1개를 정리했다. [최종 자원 확인](cleanup-verification.json)에서 기존 컨테이너/이미지/볼륨은 모두 보존됐고 이번에 추가된 image는 최종 성공본1개뿐이다. test DB는 제거했으므로 JSON의 UUID는 격리 실험의 기록이며 live DB의 ID가 아니다.

현재 완료 범위는 새 그룹 I 저장·조회·I2K 입력 준비다. T03 전체 원문 충실성 acceptance, 실제 I2K 모델 판단·전송·K/Revision 저장, embedding/RAG와 이후 task는 완료로 바꾸지 않는다.
