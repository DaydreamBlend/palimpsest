# UI 개선·직접 Realm 지정·용량 정리

2026-09-14. 사용자 HTML을 참고해 실제 Electron UI를 개선하고, Realm 선택을 탐색 화면 전반에 유지했다. 자료 카드/상세에서 직접 소속을 지정할 수 있다. 이미 저장된 코드 K42개를 통합해 표시했으며 새 I2K·Terra 호출은0이다. [실행](../../Palimpsest.cmd), [동작 계약](../../docs/interfaces/UI_REALM_ASSIGNMENT.md).

## 폴더 용량

| 측정 | 파일 크기 합계 |
|---|---:|
| 시작 | 17,046,701,326 bytes · 약15.88GiB |
| 정리 후 | 14,002,442,832 bytes · 약13.04GiB |
| 순감소 | 3,044,258,494 bytes · 약2.84GiB |

[시작 조사](disk-audit.json), [Electron 정리 후](disk-after-electron.json), [최종 조사](disk-final.json). 파일 크기를 합산한 값이며 NTFS의 압축/할당 단위별 실제 사용량과 구분한다. 확인한 hard-link 중복은 없다. Docker VM/DB volume 등 이 폴더 외부의 용량은 포함하지 않는다.

주요 원인은 모델 가중치 약6.23GiB(BGE-M3 약2.14, MinerU Pro 약2.17, PaddleOCR 모델 약1.92), 여러 파싱 실험의 PDF·JSON·이미지, 버전별 Electron 엔진 복제였다. 단순 로그 전체는 약19.18MB로 큰 원인이 아니었다. [output 분류](output-inventory.json)의 큰 JSON은 native PDF text/span과 OCR/레이아웃 검증 결과가 상당 부분이며, 파일 크기만으로 불필요한 데이터로 판정하지 않았다.

## 승인된 정리

1. 이전 Electron 실행 패키지5개(T09/T13/T14/T15/T22), 이번 중간 UI assets1개, 비활성 test profile33개를 제거했다.39개 대상/3,022,039,973 bytes. 실행 중인 삭제 대상은 없었다. 각 절대 경로·reparse/ancestor·작동 중인 process와 새 release 검증을 먼저 확인했다. [계획](electron-cleanup-plan.json), [결과](electron-cleanup-result.json).
2. 과거 Electron ZIP 및 npm 다운로드 cache2곳,218,033,300 bytes를 제거했다. 현재 설치된 runtime과 node_modules는 유지했다. [결과](download-cache-result.json).
3. 빌드/테스트 stdout254개와 반복 검증 JSON36개, 총290개/17,530,149 bytes를 정리했다. 실패 진단까지 잃지 않도록 먼저 원래 상대 경로·SHA로 ZIP을 만들고 모든 파일을 다시 해시 검증했다. ZIP은1,832,461 bytes다. [압축 기록](build-test-logs.zip), [경로·SHA·분류](output-cleanup-plan.json), [삭제 확인](output-cleanup-result.json).

삭제량 합계와 폴더 순감소의 차이는 작업 중 만들어 검사한 UI assets·테스트 cache·검증 보고서 때문이다. 현재 assets package는34,857,531 bytes(약33.24MiB)이며 기존 Electron44.3.0 엔진을 공유한다. 이전처럼 매 버전마다 약437MiB 전체 실행본을 만들지 않는다. [패키지 증거](release/package-inspection.json).

원문, I/K/Revision, 모델 요청·응답·receipt, source/raw/evidence/corpus/models와 그 근거 자료는 일괄 삭제하지 않았다. 이전 보고서·source scripts는 유지한다. 일부 과거 문서의 로그 링크는 이제 ZIP에서 해당 상대 경로를 복원해 읽을 수 있다. 오래된 전체 exe는 사용자 승인에 따라 제거됐으므로 과거 실행본이 여전히 존재한다고 주장하지 않는다. [output 안내](../README.md).

## UI와 Realm

- 참고 HTML의 녹색 계열, 간결한 정보 카드, 상시 Realm 선택과 오른쪽 근거 패널을 반영했다. HTML의 가상 답변·발견함·Decision·검색 시연 코드를 실제 기능으로 사용하지 않았다.
- 기존에는 Realm이 Data 목록에만 적용되고 다른 화면에서는 사라졌다. 새 UI는 자료/Wiki/K/검토/질문에 같은 선택을 유지하며 실제 source Data refs로 필터링한다. 공통 주제와 다중 출처 K는 관련 Realm에 표시될 수 있다. 질의 기록은 해당 index 자료 범위에 따른 분류이며 실제 model delivery는 기존 receipt/인용을 따른다.
- 자료의 **Realm 지정**은 현재 소속, 선택 Realm, 이 원본 또는 자료 계열 전체, 변경 이유를 보여 준다. 같은 D의 알려진 보존 위치는 같은 Realm Revision에 함께 저장한다. 직접 소속 해제로 다른 자료나 series 소속을 지우지 않는다.
- 기존 CAS와 UUIDv7 요청 재시도를 유지한다. 동시에 수정된 Realm을 덮어쓰지 않고 현재 상태를 다시 확인하게 한다. UI에서의 목록 필터는 I2K 실행 권한/선택을 대신하지 않는다.
- K가 있는 자료는 상세의 K 탭부터 보여 준다. I와 전체 source 실행 이력은 별도 탭에 남는다. 각 Data의 실제 I2K 실행/모델 호출/완료 여부를 읽어 prepared를 완료로 표시하지 않는다.

[자료 목록](release-ui/01-library.png), [기존 코드 K42개](release-ui/02-code-knowledge.png), [논문 근거](release-ui/03-paper-evidence.png), [과거 코드 K→I](release-ui/04-versioned-code-evidence.png), [직접 Realm 지정](release-ui/05-realm-dialog.png).

## 코드 I2K의 실제 범위

[읽기 전용 DB 조사](code-status.json):

| 자료 | I | I2K 출처 K | K2K 추론 K | 상태 |
|---|---:|---:|---:|---|
| 9/13 등록 전체202파일 스냅샷 | 204 | 0 | 0 | I2K prepared, model calls0 |
| 통제 코드 A, V1/V3가 참조하는 같은 D | 33(기존5+추가28) | 30 | 2 | 실제 I2K 성공 호출10회, 최종 source review completed |
| 통제 코드 B/V2 | 5 | 9 | 1 | 실제 I2K 성공 호출2회, needs_human 이력 유지 |

따라서 코드 I2K를 전혀 안 한 상태가 아니다. 작은 코드 샘플을 실제로 처리했고, 전체 repository snapshot은 아직 모델에 전달하지 않았다. 이 둘을 섞어 설명하지 않는다. A의30개에는 이전14개와 T13의새16개가 포함된다. 샘플의 결과를 현재 전체 workspace 설명이나 완전한 코드 지식 coverage로 확대하지 않는다.

이전 trusted Wiki 연결이 A의 자료만 포함해 B의 K10개가 기본 K목록에서 빠지고, 일부 exact I 조회도 Wiki 범위에 막혔다. 코드 연결의 실제 D3개를 명시적으로 포함하고, 통합 UI의 인용은 등록 Data/source execution을 검증하는 SourceRead로 열도록 연결했다. DB의 K를 합치거나 다시 생성하지 않았으며 기존42개가 모두 보인다. source-specific K와 역사적 version refs는 그대로다.

## 검증과 발견한 문제

- Node security/router/Realm/renderer 전체68개 통과. 새 Realm 유지·복수 보존 위치 지정·다른 membership 보존·series 소속 구분·stale CAS·I2K 준비 상태 검사 포함. 최종 ASAR renderer39개도 통과했다.
- Source/Desktop/Realm Python38개 실행:28 pass/10 기존 실제DB조건부 skip. 새 SourceRead I2K metadata 검사는 통과했고, 실제 자료/API는 별도 UI 검사에서 확인했다. 이 숫자를 전체 app suite 통과로 표시하지 않는다.
- 실제 숨김 Electron 읽기14개 검사 통과. codeRealmK42, paperRealmK43, Wiki Realm 필터, PDF14페이지, full-sourceI204/K0 상태, V2K10과 정확 I 역추적을 포함한다. [최종 결과](release-ui/result.json).
- 실제 UI로 별도 `palimpsest_realm_checks`에서 Realm 생성→같은 D의2곳 소속 지정→다시 열기→해제→이력 확인7개 검사 통과. 사용자 Realm catalog나 원문/K를 테스트로 변경하지 않았다. [결과](realm-edit-final/result.json).
- 기존 실제 코드 D/I/K/자료 버전/모델 판정 이력137개 read-only 확인 통과. [증거](preserved-code-history.json). 새 sourceDB writes0, D2I0, I2K0, provider calls0.
- 설치된 backend의 app/SQL112개와tests119개 및 실제 설치 package bytes가 현재 source와 일치했다. [증거](installed-proof/release-verification.json).
- 문서 bundle 전체는 기존 vendor/archive 문제와 이번 승인 정리로 사라진 과거 파일 링크를 포함하여1023개 오류가 남았다. 이번 작성 범위의 오류는0이다. 전체 문서 검증이 통과했다고 주장하지 않는다. [검사](bundle-summary.json).
- 참고 HTML은 로컬 headless browser에서 network를 막고 렌더링했다. 사용자 앱 창은 조작하지 않았다. 기존 Electron 대상도 사용 중인 process가 없는 것을 확인한 뒤 삭제했다.

첫 UI 저장 시험은 저장 후 선택 Realm이 첫 option으로 돌아오는 표시 문제로 timeout됐다. DB의 소속 저장은 이미 성공했다. 선택 Realm/적용 범위/이유를 새 화면에도 유지하도록 고쳤으며 [원래 실패](realm-edit-test/result.json)와 성공을 구분한다. 일반 경로로 stat하지 못한 output 이미지51개는 Windows 긴 경로 문제였고 extended path로 모두 존재함을 확인했다. 해당 source 파일을 정리 대상으로 삼지 않았다.

현재 실행은 [Palimpsest.cmd](../../Palimpsest.cmd), assets는 `output/t23-ui-realm/release/app.asar`, engine은 `desktop/node_modules/electron/dist/electron.exe`, backend는 `palimpsest-ui:0.22.0`이다. Image ID는 `sha256:40f0b65d2c4dc2e35b4236e1814c6f1b631ca28e503227b8832abc6a825d16ee`. 코드·자료 DB의 기존 schema와 canonical history는 유지하며 standalone Realm schema도 변경하지 않았다.
