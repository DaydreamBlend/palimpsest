# T00 실행 계획 — repository·CLI·MinerU inventory

시작일: 2026-09-09 (Asia/Seoul). 상태: completed (환경 inventory). 앱 구현 완료가 아니다.

## 목표와 완료 동작

사용자 요청 “내부 파일 읽고, 단계별로 구현 시작해줘”에 따라 첫 미완료 작업 T00을 수행한다. 실제 구현·도구·하드웨어·검증 명령의 관찰 결과를 inventory에 기록하고 다음 T01에서 결정할 사항을 구분한다. T00은 앱 구현 전 환경 조사 단계이며 문서·inventory·plan만 변경한다.

## 현재 관찰과 권위

- 작업 루트: `C:/Users/DaydreamBlend/Documents/Codex/Palimpsest`.
- 초기 inventory는 미실행 placeholder이며 STATUS의 T00은 planned였다.
- `git status --short`는 exit 1, `not a git repository`. branch/dirty 상태를 추정하지 않는다.
- 최초 전체 파일 목록은 109개다. 문서, JSON 설계 fixture, Python 문서 검증 도구가 있으며 앱 manifest/lockfile/production code는 발견하지 못했다.
- 읽은 지침: root AGENTS, PLANS, README, docs/INDEX, USER_OVERRIDES, DECISION_REGISTER, T00, CODE_REVIEW. 관련 current canonical §0–3/§29–30, CLI_CONTRACT, MINERU_ADAPTER, ENVIRONMENT, MODULE_BOUNDARIES, MINERU_REFERENCES를 읽었다. T01/task queue는 다음 단계 경계 확인 용도다.
- U01–U03은 accepted: CLI 우선, GUI는 T13, PDF는 MinerU, 현재 영어 구성요소명 적용. P01–P12는 proposed이며 이번 구현 착수 요청을 상세 계약 승인으로 기록하지 않는다.
- source/current snapshots와 기존 검증 기록은 보존한다. shared schema/migration/effect 계약 변경은 없다.

## 변경 범위와 담당

- root: 이 계획, repository_inventory, STATUS와 T00 진행 표시; 환경 조사 및 기존 검증 실행.
- 읽기 전용 보조 조사: MinerU 공식 버전/설치 요구사항, 문서 검증 도구의 부작용·AT 판정 범위 검토.
- production code, 의존성, DB, AGENTS, 개인 설정, immutable canonical/source는 변경하지 않는다.
- 사전 SHA-256 파일 목록을 세션에 보존했다. Git diff 대신 최종 파일별 비교로 기존 파일 변경 범위를 확인한다.

## 실행 순서와 복구

1. [x] 필수 지침, T00, 관련 canonical/interface와 실제 파일 목록 읽기.
2. [x] OS/CPU/RAM/GPU, runtime/DB/CLI/MinerU 경로·버전과 설정 준비 상태를 읽기 전용으로 조사.
3. [x] 공식 MinerU 자료를 대조하고 후보 profile과 미확인 항목 기록. 설치·모델 다운로드·PDF 전송 없음.
4. [x] 기존 validator/unit test를 검토한 뒤 실행 가능한 명령으로 검증.
5. [x] inventory/STATUS/T00 상태를 갱신. 최종 문서 일관성·변경 범위 검증 결과는 아래 실행 기록에 남김.

복구는 이번에 수정한 진행 문서의 이전 내용을 복원하고 신규 T00 기록만 제거하는 범위다. 앱/DB/runtime rollback은 변경 자체가 없어 해당하지 않는다.

## 검증 계획

- AT64: 실제 경로·명령·결과와 missing/unknown을 명시하는 inventory 검토.
- AT88: 기존 naming policy 검사와 module ownership map 검토. 문서 검사와 앱 검사를 구분한다.
- AT102: doctor가 아직 없으면 앱 acceptance는 미실행으로 남긴다. 수동 진단을 doctor 실행 성공으로 보고하지 않는다.
- 기존 문서 검사: `python tools/validate_bundle.py`.
- 기존 도구 unit 검사: `python -m unittest discover -s tools -p "test_*.py"`.
- 현재 PATH에 Python이 없어 번들 interpreter 경로를 확인해 사용했다. 자동 설치 없음. 실제 전체 명령은 [inventory](repository_inventory.md)에 있다.

## 실행 기록과 인계

- 초기 read-only 파일/manifest/CLI 검색 완료. Python/MinerU/PostgreSQL CLI는 현재 PATH에서 missing. 기존 번들 Python 3.12.14로 문서 도구 실행 가능함을 확인했다.
- Windows build 26200/AMD64, Ryzen 7 9800X3D, RAM 189.38 GiB, RTX 5080/4060 Ti, driver 616.56, CUDA toolkit 13.3을 관찰했다. 실제 model/runtime GPU 호환성을 검증한 것은 아니다.
- CIM, Docker engine, WSL, uv 관리 Python 목록 조회가 접근 제한/오류로 실패했다. OS/CPU/RAM은 제한된 registry field와 Win32 read-only API로 보완했다. 실패는 inventory에 보존했다.
- MinerU 후보는 upstream 3.4.5이나 동일 tag version.py는 3.4.4라서 T01 pin 검증 이슈다. parser/model 미준비, 실제 PDF smoke 없음.
- 첫 문서 validator: exit 0, errors 0. 첫 unit/mutation: 26개 pass, exit 0, 6.941초. red result를 만든 앱 테스트가 아니며 기존 검증 도구를 실행한 것이다.
- AT64 T00 수동 검토 기준 충족, AT88 문서 명칭·policy 확인. AT102 실제 doctor는 미실행. catalog 105개 spec_only 유지. 앱/mock/DB/MinerU/e2e/live semantic test 실행 없음.
- 첫 문서 patch는 같은 파일을 delete/add 두 번 지정해 도구가 적용 전 거부했다. update patch로 다시 적용했으며 이 실패로 파일이 삭제되지는 않았다.
- 변경 파일: `progress/repository_inventory.md`, `progress/STATUS.md`, 신규 `progress/T00_execplan.md`, `tasks/T00.md`, `tasks/README.md`, `tasks/task_graph.json`, `PACKAGE_VERIFICATION.md`. 마지막 파일은 최초 기록임을 설명하는 현재 상태 링크만 추가했다.
- 다음 단계는 T01 계약 동결. T02 production 구현에는 P10(F22/F23)/P12(F26) 구체 승인과 실행 profile이 필요하다. T01–T12는 planned, T13은 deferred 유지.

## 검토와 최종 검증

CODE_REVIEW 체크리스트에 따라 변경 범위를 검토했다. production/schema/authority/전파/effect 계약 변경 없음. 초기 release manifest 및 verification을 현재 검사와 혼동하지 않도록 명시했다. 다른 P 제안의 채택, canonical/source 편집, DB rename, 사용자 설정/의존성/원문 외부 전송은 없다.

진행 문서 작성 후 검증에서 inventory 표 안의 정규식 pipe가 열 구분자로 해석되는 오류를 발견했다. validator exit 1, unit 26개 중 test_current_bundle 1개 실패(exit 1, 6.507초). Markdown pipe escape만 수정했으며 테스트나 validator를 완화하지 않았다. 수정 후 같은 명령으로 재검증했다.

시작 SHA-256 snapshot과 비교: 최초 109개 중 변경 6개/그대로 103개/삭제 0개, 신규 T00_execplan 1개로 총 110개. 변경 경로는 위 목록과 일치한다. source/current canonical/map, 승인 기록, 기존 tools와 AGENTS/README, 최초 manifest/verification 파일은 byte-identical이다.

읽기 전용 보조 검토에서도 T00 상태/AT102 미실행/후속 task/P 상태/초기 manifest 설명 사이 모순은 발견하지 못했다.

최종 재검증: `-B tools/validate_bundle.py --json` exit 0, errors 0 (Markdown 81개/표 174개/상대 링크 338개). `-B -m unittest discover -s tools -p 'test_*.py' -v` **26개 모두 pass**, exit 0, 6.484초. interpreter 절대 경로와 process-local PYTHONUTF8 설정은 inventory의 실행 명령과 동일하다. source/current byte 재결합, U01–U03, 45개 invariant, 105개 acceptance 참조 검사가 포함된다.

T00 완료. 다음 담당자는 이 계획과 inventory를 읽고 T01 계약/profile 제안을 구체화한다. 미실행 AT102와 실제 DB/MinerU/e2e/live 검증은 후속 단계에 남긴다.
