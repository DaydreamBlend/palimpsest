# 통합 Electron과 Realm I2K 결과

2026-09-14. 앱0.21.0/UI0.5.0에서 논문·코드와 Wiki 없는 등록 D를 한 Electron 앱에서 읽고 Realm으로 분류할 수 있게 했다. 새 제품 I2K는 같은 Realm을 기본 입력 경계로 사용하며 교차 Realm은 명시적 선택이 필요하다. [실행 파일](app/Palimpsest-win32-x64/Palimpsest.exe), [workspace launcher](../../Palimpsest.cmd), [UI 계약](../../docs/interfaces/UNIFIED_DESKTOP.md), [Realm I2K 계약](../../docs/interfaces/REALM_I2K.md).

## 실제로 연결한 자료

| 연결 | 원본 D | 보존 I 전체 | KNode | 기존 source schema |
|---|---:|---:|---:|---|
| 논문 Wiki | 3 | 623 | 43 | 0010 |
| Palimpsest 코드 | 3 | 242 | 42 | 0013 |
| 원본 보존 이력 | 3 | 623 | 32 | 0006 |

원본 보존 이력의 PDF3개는 논문 Wiki와 Data SHA가 같다. 통합 자료 목록은 고유 D6개(논문3+코드스냅샷3)를 표시하고, 동일 D의 다른 보존 위치를 선택하면 해당 위치의 정확한 I·K·source execution·Wiki snapshot으로 이동한다. 위 I 개수는 과거 실행까지 포함한 보존 이력 전체이며, 최신 한 번의 D2I 산출량이 아니다. Wiki26페이지(논문/주제25+코드1), 저장된 질문7개도 같은 앱에서 조회한다. 지식 기본 목록은 기존 서비스의 승인·현재 자료 범위를 유지하고, 자료 상세에는 직접/전이 근거에 연결된 과거 KRevision도 남긴다.

실제 세 source DB에서 D9개 위치의 원본 hash와 byte size, 전체 I directory를 확인했다.18 source-execution의 대표 I와 보존 media도 읽었다. 모든 I를 각각 미리 보기한 것과는 구분한다. [논문](papers-source-probe.json), [코드](code-source-probe.json), [원본](original-source-probe.json). 과거 Markdown/HTML 실험 출력 파일을 현재 canonical 등록 자료로 간주하거나 자동 재등록하지 않았다.

## Realm과 실행 경계

별도 `palimpsest_realms` catalog에 `논문 자료`와 `Palimpsest 개발`을 만들었다. 논문은 세 Data의 두 보존 위치6참조, 코드는 D3+자료계열1참조다. source DB나 원문을 복제하지 않는다. [초기 요청 계획](realm-initialization-plan.json), [정확한 Realm revisions](realms-initialized.json).

Realm metadata는 UUIDv7·immutable revisions·원래 membership·actor·변경 이유·idempotency request를 보존한다. 오래된 head에 대한 변경은 CAS로 거부하고 현재 상태를 다시 확인하게 한다. Data는 여러 Realm에 속할 수 있다. 자료 계열은 이후 버전도 분류하지만, I2K 실행은 실제 사용한 Data/series/version/source execution을 별도로 고정한다.

새 제품 CLI/API I2K는 Realm 선택 없이 시작할 수 없다. Realm 밖 I, 실제 다른 Data에 속한 I, 잘못된 자료 버전·계열을 거부한다. 여러 Realm은 trusted 호출자의 명시적 교차 선택이 필요하며, prepare·stage·decide와 재검토에 정확한 scope를 연결한다. 분류 head가 나중에 바뀌어도 이미 준비된 실행은 원래 immutable Realm Revision을 재생한다. 기존 current/pinned version 검사도 유지한다.

기존 K 비교 목록에 raw I/D quote가 포함되던 경로를 찾아 새 Realm-scoped snapshot에서 제거했다. K의 statement·ID·FP·현재 지원 상태를 비교하므로 일반 K의 전역 중복 제거는 유지한다. 비교 K는 source I 근거가 아니며 I2K에서 새로운 추론 결론을 만들 수 없다. 역사 실행은 재작성하지 않는다.

## 검증

- Realm catalog: 순수5+실제PG4=9개 통과. 요청 재생, stale head, 동시 수정 단일 승자, SQL history 변경·불완전 publication 거부를 포함한다. [기록](realm-tests.json).
- Realm I2K: 실제PG4+순수4 통과. 양단계 guard, multi-Realm 선택, scope 상속, raw Runtime 우회 거부, 실제 Data/series/version 소유와 old-head pinned 보존을 검사했다. [첫7검사](realm-i2k-tests.json), [추가실제version검사](realm-version-test.json).
- 설치0.21 이미지: source/Realm/CLI/기존 I2K/EffectiveEdge K2K 관련92개 통과, 실패/skip0. [정확한 목록](package-tests.json). 이후 발견한 Wiki schema0010 읽기 허용 수정은 별도 최종 이미지의9개 회귀로 검증했다. [schema검사](wiki-compatibility-tests.json). 전체 앱 suite를 일괄 실행했다는 주장은 하지 않는다.
- JS: source63개 통과(보안9+store routing12+Realm IPC8+renderer34). 패키지 ASAR에서 같은 renderer34개 통과. 실제 UI 검사와 별개다.
- 실제 Electron: 소스 실행과 배포 실행 각각17개 검사 통과. 세 저장소 연결·D6목록·Realm 필터·Test_Paper 원본14페이지·Wiki 정확한 I·코드 I·두 저장소 K·Realm 이력을 확인했다. [소스](source-ui-v2/result.json), [배포](packaged-ui/result.json), [최종 화면 갱신 후 검사](packaged-ui-frames/result.json). 테스트 창은 숨겨진 별도 인스턴스이며 사용자가 조작 중인 기존 창은 건드리지 않았다.
- 최종 이미지 앱/SQL112파일·tests119파일 및 설치 package가 workspace bytes와 일치한다. [증거](release-final/release-verification.json). Electron의 source/설정12파일도 ASAR와 일치한다. [패키지 증거](package-inspection.json).
- 기존 실제 코드 D/I/K·자료 버전·판정과 원본 이력137개 read-only 검사가 통과했다. [보존 증거](preserved-code-history.json).
- 문서 bundle 전체는 기존 third-party/archive 오류948개로 실패하지만 이번 authored scope의 오류는0이다. 전체 문서 검증 통과로 주장하지 않는다. [문서 검사](bundle-summary.json).

주요 실행은 `run-tests.py`에 module 목록과 결과를 기록한 Docker 실행, `setup-realms.py`의 명시적 신규 DB 설치, `probe-sources.py`의 read-only 검증, `node --test desktop/test/security.test.cjs desktop/test/connection-registry.test.cjs desktop/test/realm-bridge.test.cjs desktop/test/renderer.test.cjs`, `node desktop/test/electron-unified-ui.cjs`, `node output/t22-unified-electron/package-ui.mjs`다. 실제 테스트 모듈·개별 test ID는 각 JSON에 보존한다.

## 발견한 실패와 수정

첫 실제 UI 시험에서 논문 schema0010이 기존 Wiki read compatibility 목록에서 빠져 있음을 발견했다. 등록 D는 보존해 표시하고 Wiki 오류를 드러냈다. 정확한0001–0010 checksum이 모두 맞고 transaction이 read-only인 경우만 허용하도록 수정했다. source DB migration이나 SQL 원문 변경은 없었다. [원래 실패](source-ui/result.json)를 보존한다.

숨겨진 Electron에서 일반 screenshot이 timeout되거나 직전 화면을 캡처하는 문제는 검사 인스턴스의 background throttling을 끄고 animation frame을 기다린 뒤 `capturePage(stayHidden=true)`로 해결했다. [최종 논문 근거](packaged-ui-frames/03-paper-wiki-evidence.png), [코드 I](packaged-ui-frames/04-code-information.png), [Realm 이력](packaged-ui-frames/05-realm-history.png). 실제 앱을 사용자 대신 클릭하거나 보여주기 위해 창을 활성화하지 않았다.

## 배포와 범위

최종 backend: `palimpsest-unified:0.21.0`.

Image ID: `sha256:674a467c2bb9109feac32b464fee2a35d47e9a0a91174c1103818a4df78fb3b3`.

Electron0.5.0, Electron runtime44.3.0, PDF.js6.3.289, packager20.3.0. 기존 정상 패키지와 source DB는 그대로 둔다. 교체된 이번 중간 image ID는 Docker에서 이미 존재하지 않고 해당 ID를 쓰는 컨테이너도 없는 것을 확인했다. 일괄 prune은 하지 않았다.

Source DB의 기존0001–0020 migration bytes를 바꾸지 않았고 Realm catalog만 별도 설치했다. 이번 작업의 실제 사용자 source DB 쓰기0, 사용자 원문 provider 전송0, D2I 재실행0, 새 모델 호출0이다. Realm/I2K PG 시험의 모델 판정은 명시된 synthetic receipts이며 새 의미 품질 실험으로 주장하지 않는다.

다른 물리 저장소의 I를 한 canonical I2K 실행으로 결합하는 것은 아직 지원하지 않는다. 한 Realm에 여러 저장소를 표시할 수 있어도 cross-store 실행은 명확히 거부한다. 기존 오래된 source DB를 새 컴파일 작업에 사용하려면 별도로 검토한 migration이 필요하며 이번 읽기 통합이 이를 수행하지 않는다. Python low-level `require_realm=False`는 과거 실험·역사 호환 경로이며 새 제품 서비스에는 `require_realm=True`를 사용한다. 이 분류 기능은 ACL/provider/Decision 권한 체계가 아니다.

현재 앱은 준비된 workspace·Docker·DB·artifact volume을 사용하는 Windows portable UI다. exe 단독의 다른 PC 전체 설치, 인터넷 수집, 새 질의 모델 전송, UI에서 변환/승인/worker를 실행하는 기능까지 포함한 배포판은 아니다. 원문 preview transport는50MiB까지이며 큰 D의 metadata는 계속 표시한다.

별도 T21의 “세션32개·세션당 캐시64항목”은 K2K 계산·근거추적용 가상 조건이고 실제 Palimpsest 제한이 아니다. 해당 조건에서 최대2,048항목을 도출한 [T21 실제 모델 결과](../t21-effective-k2k/REPORT.md)와 이번 UI/Realm 검증을 구분한다.
