# T24 — Realm 등록·자동 범위, K2W/W2P와 Wiki P

2026-09-14. Backend **0.23.0**, Electron UI **0.7.0**, 새 검사 DB schema **0023_wisdom_snapshot_guards**. 사용자의 최종 설명인 `K + Query/Context → K2W → Explanation W → W2P → P → Wiki`를 구현했다. 기존 I 기반 요약문의 실제 생성 이력은 보존했다.

## 구현한 범위

- 새 제품 파일/코드 등록 CLI에 Realm 선택이 필수다. 기존 import journal과 별도 Realm CAS를 연결하고, 원본 저장 뒤 Realm DB 실패를 같은 요청으로 복구한다. 연결 완료 전 새 D2I/I2K 컴파일을 시작하지 않는다. 과거 unscoped 요청과 저수준 fixture API는 원래 계약을 유지한다.
- 새 I2K는 모든 입력의 현재 공통 Realm을 기본 선택한다. 자동 K2K/전파도 단일 Realm이 기본이며 명시적인 교차 선택을 지원한다. 정확한 Realm Revision·store·Data/version 범위를 기존 run에 고정하고 재시도는 그 범위를 그대로 사용한다. Realm 변경으로 과거 K를 거짓 판정하거나 필수 의존 작업을 누락시키지 않는다.
- K2W는 accepted/current KNode 및 선택적 EffectiveEdge의 정확한 입력과 Query/Context를 고정한다. 구조화된 Explanation/Recommendation 생성·독립 검증·원자적 immutable W 저장을 연결했다. K를 만들거나 수정하지 않는다. 추천은 사용자의 확정 Decision이 아니다.
- W2P는 실제 W 하나 이상을 순서대로 구성한다. 문구·Context·가정·한계·인용을 그대로 보존하고 P 및 ordered P→W FK를 같은 transaction에 저장한다. 새 요청은 새 P, 같은 성공 요청의 재시도만 같은 P다.
- Electron은 같은 Wiki 목록에서 canonical P를 읽는다. 실제 W/K Revision·W/P hash·한계를 표시한다. 기존 논문/주제 문구는 실제 I 기반 설명 이력을 유지한다. P의 출처 분류는 W 준비 당시 고정된 Data hash를 사용한다.

## 실제 검증

| 범위 | 결과 | 근거 |
|---|---:|---|
| W/P·Realm·읽기·CLI 관련 혼합 회귀 | 74/74 통과, skip0 | [focused-pg-2.json](focused-pg-2.json) |
| 최종 이미지 W/P 저장 회귀 | 17/17 통과, skip0 | [packaged-wp-pg.json](packaged-wp-pg.json) |
| 최종 이미지 전체 비연결 앱 검사 | 1231개 중 871 통과·360 skip·실패0 | [packaged-app-tests-final.json](packaged-app-tests-final.json) |
| Node renderer/IPC/store/Realm | 71/71 통과 | 현재 desktop/test의 네 unit test 모듈 |
| 실제 최종 ASAR의 P 읽기 | 32/32 통과 | [parchment-final-ui/result.json](parchment-final-ui/result.json) |
| 실제 ASAR의 기존 논문/코드/Realm 탐색 | 14/14 통과 | [기존 자료 UI 결과](../t23-ui-realm/t24-readonly-regression/result.json) |
| 기존 코드 D/I/K·V1/V2/V3·추론 이력 | 읽기 전용 137/137 통과 | [preserved-code-history.json](preserved-code-history.json) |
| 설치 Python/SQL와 현재 소스 동일성 | 125파일 바이트 일치 | [package-source-verification.json](package-source-verification.json) |
| 이전 SQL0001–0020 보존 | 20개 모두 동일 | [old-sql-preserved.json](old-sql-preserved.json) |

74개는 실제 PG와 pure/mocked 검사를 함께 센 수다. 최종 17개 W/P 검사에는 실제 PG 15개와 pure P 2개가 포함된다. 전체 앱의360skip은 해당 비연결 실행에 PG/별도 runtime 조건이 없는 검사로, 모두 실행한 것으로 계산하지 않는다. 이 표의 실행들은 중복을 포함하므로 숫자를 합산한 독립 테스트 수로 해석하지 않는다.

실제 PG 검사 대상은 새 `palimpsest_wisdom_checks`와 별도 metadata 검사 DB `palimpsest_realm_checks`다. 테스트 W의 생성/독립 검증 응답과 receipt는 명시적인 **synthetic fixture**다. **실제 Terra/provider 호출은0회**이며 논문 설명의 의미 품질을 새로 평가한 결과가 아니다. 기존 사용자 source DB(schema6/10/13)는 migration하지 않았다. 원본 사용자 D/I/K/기존 Wiki 내용은 유지했고 사용자 자료 D2I/I2K를 다시 실행하지 않았다.

## 발견한 오류와 수정

1. 중단돼 있던 기존 PostgreSQL 컨테이너를 재시작했다. 최초 신규 설치는 PL/pgSQL의 CASE 조건식 괄호 문제로 원자적으로 rollback됐다. 아직 설치되지 않은0021 draft 구문을 수정한 뒤0021/0022 설치가 완료됐다.
2. 첫74개 검사 전 실행은73개 중9개가 W commit에서 실패했다. `ref`의 SQL 열/변수 이름 충돌이었다. 이미 설치된0021을 덮어쓰지 않고0023에서 함수를 교체했다. 실제 used Edge 합집합·중복 방지, uncertainty와 epistemic basis의 exact 검사도 추가했다. 잘못된 원문·인용·한계를 넣는 음성 검사가 통과했다.
3. 독립 검토에서 K2W prompt의 source/version 구분 누락을 수정했다. 원문을 추가 전송하지 않고 hash/UUID 기반 실험·자료 버전 귀속을 유지한다. P 분류에서 현재 K의 추가 지원을 따라가던 읽기도 생성 당시 W 입력 기준으로 고쳤다.
4. 전체 앱 첫 검사는 새 Realm 필수 계약을 반영하지 않은 과거 코드 등록 mock 테스트1개가 실패했다. 제품 coordinator의 정확한 Realm 전달을 검사하도록 수정했고 최종1231개 실행에서 실패0을 확인했다.
5. 자동 승인 검토의 사용량 한도 때문에 Docker 진단이 한 번 차단됐다. 사용자의 계속 진행 요청 뒤 같은 격리 작업을 정상 재개했다. 현재 미해결 승인 차단은 없다.

실패 결과 [focused-pg-1.json](focused-pg-1.json), [commit-diagnostic.json](commit-diagnostic.json), [packaged-app-tests.json](packaged-app-tests.json)은 원인과 함께 보존한다.

## 배포와 범위의 한계

[Palimpsest.cmd](../../Palimpsest.cmd)는 `release-final/app.asar`를 사용한다. 공용 Electron44.3.0 엔진을 재사용하며 새 엔진 사본을 만들지 않았다. 최종 ASAR는34,864,258bytes, SHA-256 `fe0c963c0f48577406767bff130594644b50b4e560a45742c9e8ea02d86de98a`다. [패키지 파일 검증](release-final/package-inspection.json)을 따른다. 사용자 창은 조작하거나 종료하지 않았고, 검증은 별도 숨긴 창에서 했다.

최종 Docker image는 `palimpsest-ui:0.23.0`, ID `sha256:7b1eaf086442822ec632552c927d759805e479443db318eb63c2d4caed7e8a2b`다. 검증 뒤 이번 작업의 중간 ASAR34,864,213bytes를 [정확한 hash 기록](intermediate-cleanup.json)과 패키징 manifest를 남기고 삭제했다. 첫 중간 Docker ID 삭제 시도는 이미 이미지가 없어 변경하지 않았으며, 최종 조회에서 dangling image는0개였다. 기존 사용 창의0.22 엔진/이미지·원본/모델/receipt는 건드리지 않았다. 마지막 P 상단 간격 수정 후 renderer42개와 최종 ASAR32개를 재확인했다. 관련 문서44개 링크도 존재를 확인했다.

새 P 화면의 [실제 검사 이미지](parchment-final-ui/02-preserved-W-explanation.png)는 가상의 테스트 설명이며 사용자 논문을 변환한 P가 아니다. 기존 Th17/논문 요약을 canonical W/P로 이전하거나 새 Terra로 재생성하지 않았다. 다음 주요 작업은 주제별 K 선택→K2W 자동 실행과 현재 P 선택·갱신 정책, 기존 Wiki 이전 계획, 앱 등록/질문/검토 조작이다. Decision/W2K·Book·자동 인터넷 수집은 후속이다. [남은 작업 목록](../../progress/IMPLEMENTATION_BACKLOG_2026_09_14.md)에 완료 범위와 남은 연결을 구분했다.
