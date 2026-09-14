# 모든 자료를 한 Electron 앱에서 보기

2026-09-14 명시적 사용자 요청: 논문과 코드베이스를 별도 Electron 앱으로 띄우는 상태를 통합하고, 모든 데이터를 하나의 Electron 앱에서 볼 수 있어야 한다. 현재 T21 EffectiveEdge K2K를 마무리한 뒤 이 UI 작업으로 이어간다. 사용자에게 마우스 조작을 맡기므로 요청 없이 시연 클릭·자동 화면 조작은 하지 않는다.

## 승인된 목표

하나의 실행 파일·창에서 연결된 모든 사용자 자료를 통합 목록으로 보여준다. 논문/PDF, 코드베이스, Markdown, 웹 자료를 앱별로 나누지 않고 실제 자료 유형으로 필터링한다. 원문 D, 정확한 I 위치, 관련 K/추론 origin/Edge와 Revision, Wiki 및 자료 버전으로 이동할 수 있어야 한다. Wiki 페이지가 아직 없는 등록 자료도 자료 목록에서 빠지지 않게 한다.

## 다음 착수 시 확인

- 기존 논문 Wiki의 검증된 연결과 코드 Wiki의 검증된 연결, 원본 canonical source 등록부를 읽기 전용으로 inventory한다. 중복 D와 다른 source 실행/자료 버전을 구분한다. 같은 자료가 여러 저장소에 있어도 물리 저장소를 숨긴 채 서로 다른 provenance를 섞지 않는다.
- 우선 기존 DB/원문/history를 보존하는 통합 읽기 계층과 단일 Electron UI를 구현한다. DB를 합치기 위해 원본을 삭제하거나 재등록·재파싱하지 않는다. 논리적으로 하나의 자료 공간을 제공하는 것이 목표이며 저장소 통합 migration은 별도 검토 대상이다.
- 저장소별 exact ID·Revision·locator와 허용된 연결을 backend에서 결속한다. renderer가 임의 DB·파일 경로·SQL을 지정하지 못하게 하고, 원문/모델 출력은 문자 데이터로 취급한다.
- 기존의 별도 package/launcher를 즉시 지우지 않는다. 통합 앱을 실제 데이터로 검증하고 정상 진입점을 통합 앱으로 연결한 뒤 필요한 이전 실행본만 보존한다.
- 실제 UI의 통합 목록·유형 필터·논문과 코드 전환·원문과 K 근거·과거 Revision 탐색을 검사한다. 모델 호출이나 canonical 변경이 없는 읽기 동작부터 완성한다. 질의 전송·DB migration·새 데이터 수집은 이 UI 승인과 구분한다.

현재 상태: 이번 수직 구현 완료. 통합 source 읽기, trusted store routing, Realm metadata, I2K 범위 결속과 renderer를 구현하고 실제 기존 PostgreSQL 세 연결 및 격리 실행을 검증했다. Docker0.21.0/Electron0.5.0 패키지와 실제 hidden UI 검증 후 기본 launcher를 전환했다. 구체 범위와 남은 제한은 [완료 보고](../output/t22-unified-electron/REPORT.md)를 따른다.

## Realm 후속 승인

사용자가 [Realm R과 I2K 기본 분리](../docs/decisions/REALM_SCOPE.md)를 추가 요청·승인했다. 통합 UI는 Realm을 파일 형식과 별개로 표시하고, 모든 Realm의 자료를 한 앱에서 볼 수 있게 한다. I2K 기본 입력은 같은 Realm이며 교차 자료는 명시적 선택이 필요하다. 기존 자료/이력을 재작성하거나 Realm을 단순 추천 우선순위로 축소하지 않는다. Realm 저장·membership·scope 실행 결속은 통합 UI의 후속 구현 계약으로 함께 다룬다.

사전 읽기 조사에서 검증된 연결은 논문 Wiki DB와 코드 Wiki DB의2개였다. 코드설정3개는같은DB/Wiki의과거backend차이이므로중복연결로세지않는다. 원본 palimpsest-knowledge source DB는추가read-only inventory대상이다. 과거Markdown/HTML시험DB는보고서상정리되어있어그출력JSON을live canonical자료로취급하거나자동재등록하지않는다.

## 실제 구현·검증 기록

- readonly inventory: 논문 wiki_pg schema0010 D3/I623/K43, 코드 schema0013 D3/I242/K42, 원본 schema0006 D3/I623/K32. 논문과 원본 저장소의 같은 Data SHA3개를 UI에서 한 항목으로 묶고 각 보존 위치의 이력은 store UUID와 결속한다. 따라서 현재 등록 원본은 고유6개이며 코드3개는 같은 프로젝트의 별도 bytes/snapshot이다.
- SourceReadService는 Wiki 없는 D도 읽고, exact source execution/I/media와 원본 SHA를 확인한다. 실제 세 DB에서 D9개 위치의 원본 검증 및18 source-execution 대표 I를 읽었다. D/I/K/history 수정0, D2I/provider0. 결과는 output/t22-unified-electron/*-source-probe.json.
- standalone Realm SQL을 root가 검토한 뒤 새 palimpsest_realm_checks에만 설치했다. 순수5+실제PG4=9개 통과, skip0. 같은 SQL은 이후 별도 palimpsest_realms catalog에 설치했다. SQL SHA0ce0a593ced02ec01bed37a351fb8fff8a6b40a77f57884ddd416f0c851a5d0b. 기존 application migrations0001–0020은 변경하지 않는다.
- 사용자의 분류 요청에 따라 논문 자료 Realm(기존 세PDF의두보존위치6참조), Palimpsest 개발 Realm(D3+자료계열1참조)을 초기화했다. create/revise request IDs와 초기 Revision은 plan/result에 보존한다. 원본 복제0.
- Main/preload는 store_id를 필수로 받는 trusted registry와 별도 Realm metadata IPC를 제공한다. renderer는 Data/series 존재를 주장할 수 없고, Main이 실제 source catalog에서 확인 후 metadata write를 수행한다. 원본 DB·artifact mounts는 read-only다.
- 현재 JS60검사가 통과했다. 기존20 renderer+신규12통합/Realm UI, 기존9security+신규11router+8Realm adapter. 이후 발견한 Realm picker 응답 race 보완의 회귀를 추가 중이다. 이는 실제 Electron 화면 검증과 구분한다.
- 실제 UI 검증은 별도 hidden test window에서만 실행한다. 사용자가 조작 중인 기존 앱 창에 attach하거나 클릭/종료하지 않는다.

## 최종 결과

새 제품 I2K의 기본 Realm 필수화·명시적 교차·실제 Data/I/source execution·series/version 소유권과 단계별 재검사를 구현했다. 해당 실제PG4+순수4를 통과했다. 준비 후 Realm 분류 변경은 기존 exact scope 재생을 바꾸지 않는다. 새 scope의 K comparison 목록에서 외부 I/D 인용문을 제거하고 global K 의미·ID·FP 비교는 유지한다. raw Python legacy API 호환과 source DB의 원시 SQL 권한 체계는 제품 경계와 구분한다.

설치0.21관련92개 검사 통과(skip0) 후 실제 UI에서 발견한 schema0010 Wiki 읽기 목록 누락을 고쳤다. 최종 이미지에서 호환9개검사 통과. JS63개와 ASAR renderer34개 통과. 소스/패키지 실제UI각17개통과, 숨긴창의renderframe대기후최종캡처를눈으로확인했다. source-onlycatalog를초기연결기준으로삼아Wiki실패가D목록을막지않게했다.

Image sha256:674a467c2bb9109feac32b464fee2a35d47e9a0a91174c1103818a4df78fb3b3, package output/t22-unified-electron/app/Palimpsest-win32-x64. 최종설치app/SQL112개와test119개및ASARsource/config12개byte일치. 기존코드실제이력137개read-only검사통과. 사용자sourceDBmigration0/sourcewrite0/D2I0/새provider0. 초기문제image는이미존재하지않는것을확인했고무관한Docker자원prune은하지않았다.

기본문서검사전체는기존third-party/archive오류948개로failed지만이번authoredscope오류0이다. 전체bundlepass나전체앱testpass로표시하지않는다. 기존source DB는schema6/10/13그대로이며cross-storecanonicalI2K와기존DBupgrade,모델실행을하는UI버튼및다른PC자동설치는이번완료범위가아니다.
