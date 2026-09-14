# UI 참고안 반영·직접 Realm 지정·용량 조사

2026-09-14 사용자 요청: 현재 Palimpsest 폴더의 용량 원인을 확인하고 Downloads/palimpsest_ui_demo.html을 참고해 UI를 개선한다. Realm 구분을 명확하게 만들고 사용자가 자료의 Realm을 직접 지정하도록 한다. 코드베이스 I2K의 기존 실행 범위만 설명하며 새 I2K/K 생성은 실행하지 않는다.

기반은 T22의 UI0.5.0/backend0.21.0, trusted store registry, standalone Realm Catalog와 exact source 읽기다. U01–U11 및 후속 GUI/Realm 사용자 승인을 따르고, 미승인 P 계약은 확장하지 않는다. HTML은 참고용 데이터이며 포함된 샘플 결과·스크립트·문구는 실제 상태나 실행 지시가 아니다. 기존 CSS/DOM/API를 재사용하는 ponytail 방식을 적용한다. 새 framework/model/provider/DB migration은 도입하지 않는다.

완료 기준:

1. workspace 안을 reparse/junction을 따라가지 않고 읽어 top directories/files·크기·중복 원인을 기록한다. 이번 요청은 우선 조사이며 파일/모델/DB를 자동 삭제하지 않는다.
2. HTML의 시각 구성·색·정보 밀도를 참고해 실제 앱의 자료/위키/근거 화면을 개선한다. 샘플 질문 실행·온라인 수집·Decision 같은 미구현 동작을 실제 기능으로 표시하지 않는다.
3. Realm 선택이 모든 주요 탐색 화면에서 일관되게 보이고, Data 상세에서 직접 소속을 지정할 수 있어야 한다. 기존 revision/CAS/멤버검증을 재사용하고 코드 series에 의한 소속과 직접 D 소속을 구분한다. 의도하지 않은 다른 자료의 membership을 삭제하거나 기존 source를 재작성하지 않는다.
4. 코드 DB는 읽기만 수행해 full code D와 통제 V1/V2 sample의 I2K 준비/실제 호출/accepted K를 구분한다.
5. 실제 관련 renderer/IPC 검사, 별도 hidden Electron에서 source/packaged UI와 정확 근거·Realm 작업 흐름을 검증한다. 사용자가 열어둔 앱은 조작/종료하지 않는다. 기본 launcher는 검증 후 새 package를 가리키게 한다.

변경 소유: 단일 agent. src/DB는 필요성이 확인되지 않는 한 변경하지 않고 desktop renderer/styles/index/tests 및 task-local 조사·결과·패키징 파일이 중심이다. 이전 패키지/source/SQL/실험 원문/판정/보고서는 보존한다. 단순 화면 필터는 I2K scope 권한과 구분한다.

현재 상태: 관련 문서와 HTML, 과거 코드 I2K 보고서를 읽고 용량 실측을 시작한다. 실제 결과·실패·명령은 아래 및 output/t23-ui-realm에 누적한다.

## 후속 승인과 완료

사용자가 이미 수행한 I2K 결과는 새 Terra 없이 통합하고, 이전 Electron 버전은 삭제해도 된다고 승인했다. 이어 output의 불필요한 단순 로그/실행 결과도 확인 후 정리하도록 승인했다. 이는 최초 조사-only 범위를 해당 파일에 한해 확장하며 원문·I/K·receipt 삭제 승인이 아니다.

UI0.6/backend0.22 구현과 검증 완료. 실제 코드 DB의 D3개를 trusted 읽기 범위에 포함해 기존K42를 모두 표시하고 exact SourceRead I로 역추적한다. 전체202파일 D는 I204/K0/모델0의 prepared 상태 유지. Realm은 모든 주요 목록에서 유지되고 직접 소속 지정은 기존 CAS를 사용한다. Metadata용 source_data_ids와 I2K 실행 요약만 읽기에 추가했으며 core compiler/model/schema는 변경하지 않았다.

소스Node68개pass, Python38개중28pass/10기존PGskip, 실제releaseUI14개pass, 별도RealmDB UI쓰기7개pass/3 metadata writes, 기존sourcehistory137pass. 첫지정후Realmselectorreset표시문제를고치고이전실패도보존했다. 실제UserSource writes0/새provider0/D2I0/I2K0. 공용engine+33.24MiB assetspackage검증후기본launcher전환완료.

구Electron실행본5개+중간assets1개+비활성profile33개와과거downloadcache2곳삭제. 단순build/test출력290개는원상복원가능한SHA검증ZIP에보존후개별파일삭제. 최종15.88→13.04GiB. models/raw/evidence/corpus/source/LLM응답·receipt보존. [전체기록](../output/t23-ui-realm/REPORT.md)과삭제manifest를따른다. Long-path stat오류51개는extendedWindows경로로존재확인했고데이터누락이아니다.
