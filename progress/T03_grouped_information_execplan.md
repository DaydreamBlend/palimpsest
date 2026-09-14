# 스크립트 그룹을 canonical I로 저장

상태: 그룹 I 저장 후속 slice COMPLETE, T03 전체 품질 gate와 T04 의미 실행은 IN_PROGRESS, 2026-09-11. 사용자: “수백개를 저장하지 말고, I를 스크립트 기반으로 묶어서 저장하는 게 나을 거 같아”. 이번 승인은 기존 조회-only 그룹 정책을 새 I의 영속 단위에 대해서 대체한다. 과거 I/ID/hash/원시 parser artifact는 그대로 보존하고, 새 기본 D2I는 그룹 수만큼 I/Record/outbox를 만든다. 원문 블록은 그룹의 payload/grounding에 남는다.

## 목표와 경계

기존 스크립트 heading/원문 순서 규칙을 재사용해 본문 절과 문맥을 묶는다. 페이지 머리말/꼬리말/번호도 버리지 않고 별도 그룹에 보존한다. Text 중심 그룹에 여러 원문 이미지가 함께 존재할 수 있으며 source_artifacts와 exact source refs를 모두 제공한다. 기존 required Figure의 명시적 coverage 계약은 유지한다. 새 모델·LLM·embedding·K 저장·GUI는 이번 작업 범위가 아니다.

기존 source-information-v1은 다수 source_blocks/groundings/images를 지원하므로 새 SQL/migration/unit_type가 필요하지 않다. 새 source-groups-v1 알고리즘과 frozen profile로 구분하고 source-units-v1 재현을 보존한다. CLI/runtime가 단일 완료 source 실행을 명시적으로 인용해 frozen parse를 새 grouped 실행으로 재조립하도록 한다. 과거 parser receipt를 새 parser 실행인 것처럼 재작성하지 않는다.

## 읽은 계약·실제 경로

USER_OVERRIDES, INDEX, DECISION_REGISTER, T03/T04, I2K_I_FIRST_SOURCE_ON_DEMAND, source 보존 U11와 PLANS/CODE_REVIEW를 확인했다. 최신 사용자 지시는 저장 단위 변경의 승인이고 P 제안 전체 승인/기존 I 삭제 승인이 아니다. 기존 section_projection의 heading 순회, source_units 정확한 원문검사, compiler_runtime atomic materialize, source-information-v1/0003 schema, page projection 다대일 매핑과 T04 prepare-input/source를 재사용한다. hybrid receipt가 전체 compilation profile hash에 결속된 점을 유지한다.

## 구현 순서·소유권

1. agent: source_groups.py + section_projection.py의 재사용 helper + 독립 단위검사. 기존 절 조회 결과를 보존하며 그룹 text의 각 원문 문자 범위를 만든다.
2. root: d2i algorithm dispatch, profile/receipt/worker 기본값, source 재조립 CLI/runtime와 검증 provenance, grouped payload·I2K 연결. 모든 DB/shared execution 계약 편집은 root가 소유한다.
3. 독립 읽기 검토: 호환성과 원문/media/ref 경계 확인. root는 기존 code snapshot을 output/t03-grouped-information/baseline에 저장하고 Docker 작업 전 자원 inventory를 수집한다.
4. 단위·실제 격리 PostgreSQL 및 Test_Paper 재생으로 저장 I 수 감소와 모든 block/text/media 보존, retry·atomic rollback·legacy 조회를 확인한다. 기존 parser/model 재실행은 불필요하며 frozen source 재생을 실제 신규 OCR과 구분한다.
5. 승인/현재 설계·사용법 문서 갱신, 문서 validator 기존12오류 대조, 코드 diff 검토, 테스트용 Docker 자원만 정리. 성공한 새 앱 이미지1개를 보존한다.

## 필수 검증·완료 제한

모든 source block 정확히1회배정, 원문 Unicode/개행/공백과 그룹content offset 재현, multi-page/multi-image/table 보존, metadata/빈원문 포함, required Figure primary/member/caption 일관성, source fidelity 미승인 유지. grouped 실행은 그룹행만 저장하며 grounding이 전부 남고 같은 실행 재시도는 동일UUID여야 한다. 과거 v1와 profile/receipt/hash를 섞으면 실패한다. canonical I 변경/삭제는 하지 않는다.

앱 테스트는 Linux Docker/격리 PostgreSQL18/pgvector에서 수행한다. 호스트 Python의 psycopg/PDFium 미설치와 Windows secure-FD 제약을 검증 성공으로 보고하지 않는다. 새 migration이 없으므로 기존 migration checksum은 그대로여야 한다. T03 전체 충실성 acceptance와 T04 K 의미·저장 acceptance는 여전히 미완료다.

실행 명령·실패·측정·검토·남은 한계는 아래에 누적한다.

## 실제 구현·검토

병렬 작업 중 section_projection의 첫 로컬 snapshot은 helper 추출 이후에 수집된 것으로 확인했다. 해당 관측본을 별도 보존하고, 이전 검증 image `palimpsest-t04-input:0.2.0`에서 원래 파일 bytes를 읽어 baseline을 복구했다. 원본 파일 SHA는 `1dc8a9cf431263eb99765c2da3f222a9d739df2e5d70ecb4b7ae9452f8486d04`이며 변경 전 diff는 이 원본을 기준으로 작성했다. source 및 테스트 결과는 변경하지 않았다.

`source_groups.py`에 새 builder/checker와 exact content_segments를 구현하고, 기존 `section_projection.py`의 경계 loop를 순수 helper로 재사용했다. 역사 section/document fixture SHA가 그대로임을 검사했다. `d2i.py`의 algorithm dispatch, Runtime의 profile/receipt/checks/atomic payload 저장, I2K의 frozen algorithm/content_segments 대조를 연결했다. `tools/run_d2i.py`는 groups 기본/blocks 명시 선택이며 `hybrid_receipt.py`와 parser runner는 두 알고리즘에 결속된 정확한 profile hash를 검증한다.

`compile regroup`은 완료된 source v1을 검증해 새 grouped 실행을 만든다. parent execution/profile/parse manifest SHA와 원래 bundle/files를 검증하고 원래 raw/receipt bytes를 그대로 유지한다. 조립 코드 hash는 새 profile에 기록한다. 기존 단일 SQL/schema로 그룹 I만 저장하고 block grounding을 유지한다. 이미 grouped 실행의 재시도는 기존 ID를 반환한다.

독립 검토에서 native 옵션의 parser 이미지에는 앱 module이 없는 점을 발견했다. runner에 불필요한 application import를 제거하고 두 algorithm 값만 guard에 명시했다. 앱 module을 import할 수 없는 조건에서 profile 검사를 통과하는 회귀를 추가했다. 완료 replay에서 동시 요청 한쪽의 information_ids가 빠질 수 있는 경로도 regroup의 성공 응답에서 보완했고 실제2요청 PostgreSQL 검사를 통과했다. 후보를 지식으로 승인하거나 파서 fidelity를 승인하는 변경은 없다.

## 실제 실행·실패 보존

[전체 결과와 정확한 Docker/CLI 명령](../output/t03-grouped-information/REPORT.md)을 보존했다. `migrate`는 격리 palimpsest-grouped-i 프로젝트/기존0003 source schema로 exit0. 빌드3회 모두 exit0이며 최종 성공 image `palimpsest-grouped-i:0.2.0`/`sha256:c3c5823bc706abc637482bf0dae22157453f7a2f81ef6af05e847dd615845cae`를 Compose 기본으로 설정했다. SQL/dependency/Dockerfile 변경은 없다.

- host 순수22tests 통과0.267초. 초기 신규 Counter test오류1건은 수정했고 초기35tests 묶음 중기존 Runtime import1error는 host psycopg 미설치였다. 보안/runtime 검사를 약화하지 않고 Docker에서 검사했다.
- 기존 성공 image에 변경 src/tests/tools/deploy를 read-only mount해 targeted58tests 통과5.011초. 이후 신규 동시 regroup 검사까지 포함한 최종 앱 image로 전체실행.
- 첫 전체353tests는 failures0/errors3/skipped16, exit1. 기존 Paddle/pipeline worker의 임시 ROOT fixture에서 새 source_groups/section_projection/figure_references 해시 대상 파일이 빠져 발생했다. fixture를 보완하고 실패 JSON/log를 별도 보존했다.
- 최종 전체353tests, failures0/errors0/skipped16,28.900초, exit0.16skips는 별도 PDFium용 기존 검사다. 실제 PG의 그룹-only 최초저장, 과거 payload 불변, reassembly provenance, rollback/retry·동시성 및 CLI를 포함한다.
- 최종 Test_Paper installed CLI/PG 시험 exit0,37.70초. 과거 parser 재생229 I와 분리한 새실행은22 I/22Records/22outbox/229groundings/0candidates. 229개원문block/63031문자 exactoffset복구,36이미지bytesSHA/14페이지media전부확인. 과거 I/grounding 전체 snapshot hash 전후동일, 같은재시도 groupedUUID동일. 신규parser/modelcalls0, 원본PDF는scripted요청으로로컬준비하고actualdeliveryfalse.
- 기존image200 추가3편은 host순수함수 read-only 검증: Chen237blocks→23groups, Clarke159→21, Dejani126→6.522blocks 단일배정/문자복구/media원본참조/입력파일SHA불변, exit0.0.156초는조립만측정이며DB/parser/model평가아님.
- 문서 validator exit1: 기존 raw/oracle Markdown12개 오류와 동일하며 추가0. 초기 경로 조회와 Windows rg glob 조회 실패는 올바른 파일 경로로 다시 조회했다. 원본 raw/기존 validator 기준 변경없음.
- project label/작업전inventory와비교한뒤 `docker compose -p palimpsest-grouped-i down --volumes` exit0. 작업용2containers/4volumes/1network를제거했고 기존모든Docker자원은보존됐다. 새image는최종성공본1개만남았다. 실물JSON UUID는삭제한격리testDB의기록이고liveDB의ID가아니다.

## 변경 파일과 인계

코드: `source_groups.py`, `section_projection.py`, `d2i.py`, `compiler_runtime.py`, `i2k.py`, `hybrid_receipt.py`, `cli.py`, `tools/run_d2i.py`, `deploy/mineru-hybrid/run_parser.py`, `compose.yaml`. Tests: 신규 `test_source_groups.py`, 기존 source_runtime_integration/hybrid_runtime/hybrid_worker/paddle_worker. 문서: GROUPED_INFORMATION_STORAGE/GROUPED_INFORMATION, AGENTS/USER_OVERRIDES/DECISION_REGISTER/INDEX/README, DIKW_CURRENT/I2K_CONTEXT_POLICY/T04_INPUT/MODULE_BOUNDARIES/I2K_I_FIRST_SOURCE_ON_DEMAND와T03/T04작업서. 기존canonical/source snapshot/JSON P승인목록은변경없음.

그룹 경계는 구조적 hint이다. Chen 번호없는caption tail3개는 References 그룹에보존되므로제목만으로처리대상에서제외하면안된다. 다른논문은소제목미검출로최대24816자의큰I가존재한다. 필요시I2K exactsource범위window를추가하며현재준비는I전체를반환한다. 별도LLM그룹검토/새OCR/임의caption소속결정은추가하지않았다.

미승인결정으로막힌항목은없다. 이번승인밖의기존I삭제/과거hash재작성·새parser선택은하지않았다. T03전체원문충실성acceptance와T04 AT06/07/08/20/21/24/28/29/30/41/42/43/44/73/74/82/83 및107/111/112의의미·K/Revision commit은완료하지않았다. 다음실제I2K runtime는새groupedI를입력으로쓰고exactI/block/range인용과필요시원본PDF요청/전달/사용이력을연결한다.
