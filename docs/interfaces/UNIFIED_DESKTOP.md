# 통합 Electron 자료 공간

**UI0.6 이후 현재 안내:** [직접 Realm 지정·새 실행 구조](UI_REALM_ASSIGNMENT.md)를 따른다. 기본 launcher는 공유 Electron 엔진과 T23 assets를 사용한다. 아래0.5의 전체 실행본은 후속 사용자 정리 승인으로 삭제됐고 [T23 결과](../../output/t23-ui-realm/REPORT.md)에 기록했다. 기존 D/I/K 보존 경계는 유지한다.

2026-09-14. 사용자는 논문과 코드 자료를 별도 앱으로 나누지 않고 하나의 Electron 앱에서 탐색하도록 요청했다. UI **0.5.0**은 기존 Python 서비스를 사용하는 통합 읽기 화면이며, 준비된 backend 이미지는 `palimpsest-unified:0.21.0`이다. 자료의 D/I/K와 원문은 읽기 전용으로 유지한다. Realm 분류 metadata의 생성·수정은 별도로 준비한 Realm Catalog에 기록한다. 따라서 Realm 관리를 포함한 앱 전체가 무조건 읽기 전용이라는 뜻은 아니다.

기존 DB를 합치거나 D를 재등록하지 않는다. 연결된 저장소의 자료를 한 화면에 모으고, 실제 조회는 선택한 저장소의 정확한 Data·I·KRevision·source 실행·Wiki snapshot으로 보낸다. 이 화면을 열거나 자료를 분류하는 동작은 D2I, I2K, D2K, K2K 또는 provider 호출을 실행하지 않는다.

실제 결과는 [T22 실행 계획](../../progress/T22_unified_electron_execplan.md)과 [완료 보고](../../output/t22-unified-electron/REPORT.md)에 기록한다. Source 읽기·Realm PostgreSQL·I2K 범위 검사와 실제 소스/패키지 Electron 검증을 구분한다. 배포 패키지는 별도 hidden 창에서 17개 실제 자료 탐색 검사를 통과했다.

## 등록 자료와 보존 위치

실제 읽기 전용 inventory는 고유한 D **6개**와 저장소별 등록 위치 **9개**를 확인했다. 고유 D는 논문 PDF 3개와 코드 source snapshot 3개다. 논문 3개의 원본 보존 DB와 Wiki DB에 같은 Data hash가 있으므로 위치 수가 더 많다.

| 기본 저장소 | Compose project / DB | 실제 source schema | 등록 D | 원문 volume |
|---|---|---|---:|---|
| 논문 Wiki | `palimpsest-multi-checks` / `palimpsest_wiki_pg` | `0010_wiki_retrieval` | 3 | `palimpsest-knowledge_artifacts` |
| Palimpsest 코드 | `palimpsest-multi-checks` / `palimpsest_codebase_k2k` | `0013_data_versions` | 3 | `palimpsest-codebase_artifacts` |
| 원본 보존 이력 | `palimpsest-knowledge` / `palimpsest` | `0006_i2k_selection` | 3 | `palimpsest-knowledge_artifacts` |

증거는 [논문 inventory](../../output/t22-unified-electron/papers-inventory.json), [코드 inventory](../../output/t22-unified-electron/code-inventory.json), [원본 inventory](../../output/t22-unified-electron/original-inventory.json)에 있다. 이 목록은 지정된 신뢰 연결의 현재 등록부를 읽은 결과이며, 서버의 모든 DB나 개발용 출력 폴더를 자동 검색한 결과가 아니다.

**모든 자료** 화면은 SHA-256이 같은 D를 한 항목으로 묶되, 각 보존 위치를 남긴다. Wiki가 있는 위치를 대표로 보여줄 수 있지만 다른 위치의 I·K·실행 이력을 그 Wiki의 provenance로 합치지 않는다. 같은 원본의 다른 보존 위치를 선택하면 해당 위치의 Data 상세, source 실행과 I를 다시 읽는다. 코드 변경으로 bytes가 달라진 snapshot은 서로 다른 D이며, Data series/version은 그 관계를 별도로 표시한다. 이전 bytes로 돌아간 버전이 기존 D를 가리키는 경우에도 해당 version ID를 없애거나 새 Data를 만들지 않는다.

과거 Markdown와 HTML 시험 DB는 [Markdown 보고서](../../output/t03-markdown/REPORT.md), [HTML 보고서](../../output/t03-html-review/REPORT.md)에 따라 정리되었다. 보존된 실험 JSON이나 HTML 파일을 live canonical D/I로 표시하지 않는다. 새 화면은 Markdown·웹 자료 유형을 처리하지만, 유형 지원을 현재 해당 자료의 등록 여부로 대신하지 않는다.

## 화면과 탐색

- **모든 자료:** Wiki 유무와 관계없이 선택한 저장소의 `canonical_store.data` 전체를 목록에 넣는다. D2I가 없거나 실패한 자료도 등록 D로 표시한다. 파일 형식과 Realm 필터를 함께 사용할 수 있다.
- **자료 상세:** 원본 hash·MIME·크기·acquisition, 모든 D2I 실행 상태, 정확한 I directory, 자료 version, 관련 KRevision 요약을 표시한다. 아직 읽지 않은 artifact의 존재나 내용 검증을 metadata 조회만으로 완료했다고 표시하지 않는다.
- **Wiki:** 기존 논문/코드/주제 페이지와 과거 snapshot을 읽는다. 같은 I를 공유하는 K 탐색 링크는 `shared_source_evidence`이며, 의미적 `supports` 관계와 구분한다.
- **Information과 원본:** 정확한 source 실행의 I 본문, 이미지와 page/region 또는 byte/char/line 범위를 읽는다. PDF는 등록 원본 bytes를 PDF.js에 전달하고, Markdown·HTML·코드 원문 문자열은 그대로 표시한다. HTML의 script·외부 URL은 실행하거나 다시 수집하지 않는다.
- **지식·검토·질문 기록:** Wiki가 설정된 연결의 기존 읽기 API를 재사용한다. source-only 연결도 자료 상세에서 해당 D에 직접 또는 전이적으로 연결된 현재·역사 KRevision 요약을 제공한다. source-only 요약을 기존 Wiki 전용 full Knowledge 조회와 같은 기능이라고 주장하지 않는다.

자료 형식은 `PDF`, `코드`, `Markdown`, `웹`, `텍스트`, `이미지`, `기타`로 구분한다. 등록 MIME, 알려진 Python source profile, 정확한 code snapshot acquisition을 사용하며 파일명만으로 코드라고 추정하지 않는다. 코드 snapshot이 Markdown dossier로 저장되어 있어도 확인된 코드 provenance가 있으면 코드로 분류할 수 있다.

Realm은 형식 필터와 별개다. 한 프로젝트 Realm에 코드, 설계 Markdown와 참고 논문이 함께 들어갈 수 있고, 하나의 자료가 여러 Realm에 속할 수 있다. **모든 Realm**, 특정 Realm, 미분류 자료를 선택할 수 있다. 여러 저장소에 같은 Data hash가 있어도 Realm membership은 해당 `store_id`의 Data 또는 Data series 참조에 적용된다.

초기 연결과 개별 목록 조회의 오류는 저장소별로 표시한다. 늦게 도착한 이전 저장소의 응답은 현재 선택한 자료나 원문 패널을 덮지 않는다. I·K·페이지·저장 질문의 ID가 복제 DB에서 같더라도 다른 저장소의 응답으로 대체하지 않는다.

## 신뢰된 연결 설정

[stores.example.json](../../desktop/stores.example.json)은 `desktop-stores-v1` registry다. 각 항목은 UUIDv7 `store_id`, 표시용 `label`, 신뢰된 `connection`을 가진다. `connection`에는 `project`, `database`, `wikiId`, `artifactVolume`, `queryDirectory`, `image`가 있다. source-only 연결은 `wikiId`와 `queryDirectory`를 `null`로 둔다. 비밀번호나 provider credential은 설정 파일의 필드가 아니다.

통합 registry의 선택 순서는 다음과 같다.

1. 명시한 `PALIMPSEST_DESKTOP_STORES` 파일.
2. workspace의 `.local/electron-ui/stores.json`.
3. 패키지에 포함된 `stores.example.json`.

`PALIMPSEST_DESKTOP_CONFIG`를 명시하면 기존 단일 연결 방식을 선택한다. `PALIMPSEST_DESKTOP_STORES`와 동시에 지정하면 `ambiguous_desktop_configuration`으로 거부한다. registry 파일이 없는 이전 설치의 `.local/electron-ui/connection.json`과 기본 단일 연결도 호환 경로로 남는다. 통합 패키지에 registry가 있는 경우 단일 연결을 명시하려면 `PALIMPSEST_DESKTOP_CONFIG`를 사용한다.

Realm 연결은 workspace의 `.local/electron-ui/realm.json`, 없으면 패키지의 [realm.example.json](../../desktop/realm.example.json)을 사용한다. 기본 대상은 별도로 준비한 `palimpsest_realms` DB다. Realm 설정에는 `wikiId`와 `queryDirectory`가 `null`이며 `include_data_ids`는 받지 않는다. Realm 설정의 오류가 자료 저장소 설정을 변경하거나 원본 DB를 초기화하는 원인이 되지 않는다.

Main process의 registry는 요청 시작 시 `store_id`에 대응하는 연결을 고정한다. Renderer에는 임의 DB 이름, DSN, SQL, artifact 경로, Docker project/image를 전달하는 API가 없다. Query 디렉터리는 workspace 안의 실제 경로인지 확인하고 링크를 통한 경로 이탈을 거부한다. 동일 저장소의 예전 backend 설정을 새 자료 공간으로 자동 추가하지 않는다.

## Source 읽기 API

`window.palimpsest.request()`의 통합 요청에는 `store_id`와 아래 operation 및 필드가 들어간다. Main process가 `store_id`를 검증하여 reader를 고른 뒤 이를 제거하고 Python에 전달한다. Source API는 Wiki ID를 요구하지 않는다.

| operation | Python 요청 필드 | 결과 |
|---|---|---|
| `source_catalog` | 없음 | `source-catalog-v1`, 전체 등록 D 요약, acquisition·실행·버전 정보, capabilities |
| `source_detail` | `data_id` | Data 상세, source 실행, I directory, 버전, 관련 Knowledge 요약 |
| `source_information` | `data_id`, `source_execution_id`, `information_id` | exact I, source refs, media descriptor, 원본 metadata, 검증 방식 |
| `source_artifact` | `data_id` | hash·크기를 검증한 등록 원본 text 또는 base64 bytes |
| `source_artifact`의 I media | `data_id`, `source_execution_id`, `sha256` | 해당 완료 source 실행에 실제로 속한 이미지 bytes |

`source_artifact`의 추가 두 필드는 반드시 함께 지정한다. 이미지 hash만으로 다른 D의 media를 읽거나, source 실행을 바꿔 같은 I ID를 사용하는 요청은 거부한다. 원본은 요청 D의 content hash로 읽고, source media는 전체 source packet의 실제 소유 관계를 확인한다.

`SourceReadService`는 `default_transaction_read_only=on` 및 `REPEATABLE READ READ ONLY`를 사용한다. PostgreSQL 18 / pgvector 0.8.6과 설치된 전체 migration prefix의 checksum을 확인한다. schema0006, 0010, 0013, 0020을 포함한 확인된 prefix를 읽되, 해당 schema에 없는 version·Wiki·추론 기능은 capabilities에서 구분한다. 읽기 때문에 migration하거나 원본 DB를 최신 schema로 맞추지 않는다.

완료된 `source-d2i-v1` I는 기존 `CompilerRuntime.prepare_input()`의 전체 source snapshot 검증을 재사용한다. 이는 보존된 I·parse artifact·grounding을 읽고 검증하는 동작이다. 새로운 source 실행이나 I를 만들거나 D2I를 다시 수행하지 않는다. 원문 문자열·I·Record·source 실행의 결속이 다르면 오류를 반환한다.

역사적 `d2i-v1`의 semantic I는 `stored_legacy_information`으로 표시한다. 그 결과를 완전한 source coverage 검증으로 바꾸지 않으며, 원래 payload와 grounding을 보존한다. 알 수 없는 profile에 이 역사 읽기를 자동 적용하지 않는다. 현대 source packet 검증 실패를 원문 대체, 파싱 재시도 또는 LLM 호출로 해결하지 않는다.

원본과 이미지 읽기는 Artifact Store의 no-follow 파일 검증 및 SHA/byte size 검사를 거친다. UTF-8 text는 Unicode 정규화나 개행 치환 없이 반환하고, 비UTF-8 또는 binary는 원래 bytes를 base64로 반환한다. Renderer는 제공된 원문을 문자 데이터로 취급한다.

## Realm metadata와 실행 범위

[Realm 승인 규칙](../decisions/REALM_SCOPE.md)과 [Realm Desktop IPC 계약](REALM_DESKTOP.md)을 따른다. UI는 빈 Realm을 생성한 뒤, Data 또는 Data series membership을 별도 Revision으로 수정한다. 생성·변경에는 사용자 입력 이름과 이유를 요구하며, 수정에는 현재 보던 `expected_revision_id`를 전달한다. 오래된 head에 대한 변경은 `realm_revision_changed`로 보류되고 현재 상태를 다시 확인해야 한다.

멤버는 `{store_id, member_kind, member_id}`다. Main process는 저장소를 registry에서 찾고 실제 읽기 전용 `source_catalog`로 등록 Data/series 소유를 확인한다. Realm Revision은 과거 membership을 덮어쓰지 않는다. Series membership은 이후 버전도 포함하는 논리 범위이며, 특정 I2K 실행은 그 시점의 정확한 자료 버전을 별도로 고정해야 한다.

Realm 수정 권한이나 `actor` 표기는 provider 전송 승인이나 W2K Decision authority가 아니다. Realm metadata UI가 있다는 사실만으로 I2K의 실행 범위 검사까지 완료됐다고 표시하지 않는다. 같은 Realm 기본 입력·명시적 교차 선택·준비 후 범위 변경 검사는 별도 I2K 실행 계약의 책임이다. 자료 형식 필터나 UI 검색어가 해당 실행 권한을 대신하지 않는다.

## 실행·검증·제한

정상 진입점은 workspace의 [Palimpsest.cmd](../../Palimpsest.cmd)다. 현재 UI0.6은 공용 Electron 엔진과 T23의 app.asar를 사용한다. 과거 전체 실행 패키지는 후속 정리 승인에 따라 삭제했고 보고서와 source는 보존한다.

이 패키지는 workspace와 기존 Docker backend를 사용하는 Windows x64 portable 앱이다. 다른 PC에 exe 하나를 복사하면 PostgreSQL·원문·Realm Catalog까지 설치되는 배포판은 아니다. 실행에는 해당 workspace, 준비된 DB, 정확한 artifact volume과 backend 이미지가 필요하다. `PALIMPSEST_WORKSPACE`는 host의 workspace 선택에 사용한다.

Electron 44.3.0, PDF.js 6.3.289, packager 20.3.0의 기존 dependency를 유지한다. 준비된 로컬 도구에서 확인할 명령은 다음과 같다. 명령의 기재는 해당 검사가 이미 완료됐다는 뜻이 아니다.

```text
node --test desktop/test/security.test.cjs desktop/test/connection-registry.test.cjs desktop/test/realm-bridge.test.cjs desktop/test/renderer.test.cjs
python -B -m unittest test_unified_source_read
node desktop/test/electron-unified-ui.cjs
```

Python 검사는 기존 Docker 이미지에서 `PYTHONPATH`에 `src`와 `tests/app`을 포함해 실행한다. 실제 Electron 검사는 준비된 `PALIMPSEST_PLAYWRIGHT_MODULE`을 사용하며, `PALIMPSEST_ELECTRON_EXECUTABLE`로 새 패키지 exe를 선택할 수 있다. 검사용 별도 숨김 창을 만들고 사용자가 열어 둔 창에는 연결하지 않는다. 사용자 화면을 보여주는 것과 자동 클릭 시연은 구분한다.

Source API의 실제 원본 preview 한도는 **50 MiB**다. 그보다 큰 D도 metadata와 source 실행 목록에서 없어지지 않으며, 원문 전송을 명시적으로 거부한다. 매우 큰 JSON text 응답도 bridge 한도에서 거부할 수 있다. PDF 원본을 새로 렌더링한 화면은 과거 모델에 실제 전달된 page-image bytes와 같은 것이라고 주장하지 않는다.

자료 이름/hash·Wiki 제목·지식 문장·저장 질문 등의 화면 필터는 표시 범위를 바꾸는 로컬 기능이다. 새 BGE 검색, LLM 질의, 인터넷 수집, 원문 편집, D2I 교정, Knowledge 생성·Revision 승인 또는 전파 worker 실행 버튼으로 동작하지 않는다. 이 기능들의 실제 실행은 각 CLI/Runtime 계약과 별도 승인 범위를 유지한다.
