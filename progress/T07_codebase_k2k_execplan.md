# 코드베이스 D/I와 첫 K2K 실행 단위

2026-09-13. 사용자는 현재 Palimpsest 코드베이스를 D로 쓰는 K2K 시험을 제안했고, 원문을 보존한 생성 Markdown snapshot으로 먼저 진행하며 코드 전용 D2I parser는 나중에 만들기로 명시했다.

## 목표와 적용 계약

직접 관리하는 코드·테스트·배포 설정을 재현 가능한 Markdown dossier D로 등록하고 기존 결정적 Markdown D2I로 I를 저장한다. 파일별 exact bytes/hash/path/line과 dossier 위치를 복원·역추적한다. 생성 문서 자체가 D이며 개별 `.py`가 원래 Markdown이었다고 표시하지 않는다.

첫 K2K는 두 개 이상의 accepted/current KRevision을 전제로 새 Proposition 또는 같은 의미 재사용을 독립 검증·원자적으로 저장한다. 실제 origin=k2k/is_inferred=true, 정확 전제, 가정·한계·간결한 도출 근거와 transitive I/D를 보존한다. 새 I나 가짜 직접 I 인용은 만들지 않는다.

읽은 계약: AGENTS/USER_OVERRIDES/INDEX/DECISION_REGISTER, PLANS/CODE_REVIEW, tasks/T07, canonical06, I2K_SOURCE_ONLY_K2K_INFERENCE, LLM_WIKI_RETRIEVAL, MARKDOWN_RUNTIME, SOURCE_REVIEW 및 기존 0005/0007 runtime guards. 이미 승인된 K2K 경계와 source 보존을 적용한다. 전체 T07 scheduler/quiescence/EffectiveEdge 입력/일반 material Revision 수정은 이번 한 실행 단위의 완료 범위가 아니다.

## 소유권과 구현

- `code_snapshot.py`와 단위 tests: source selection, exclusive dossier/embedded manifest, verify/locate/restore. 기본 generated/dependency/sensitive-name 제외는 기록한다.
- `k2k.py`와 단위 tests: node-only exact 입력·Proposition 후보·독립 추론 검증과 prompt/schema. LLM이 canonical IDs/origin/depth를 정하지 않는다.
- `0011_k2k.sql`: 새 derivation/premise 원장과 기존 SQL guard의 additive 확장. 기존0001–0010 bytes 보존.
- `knowledge_runtime.py`/`knowledge_provenance.py`: 기존 짧은 transaction·profile·Record·receipt·reuse·outbox 재사용, exact premise currentness, 원자적 도출 저장, depth/기원/현재성 조회.
- CLI와 provider request 준비 도구: 기존 service 호출과 실제 전달 receipt 결속.
- 별도 PG fixture runtime/SQL tests: 생성·재사용·rollback·stale 전제·depth·origin·위조 provenance 차단.

## 순서와 검증

1. 기존 코드 입력·K2K 미구현 제약을 확인. code snapshot을 기존 Markdown 경로로 연결하기로 사용자 승인.
2. 구현 및 순수 검사. 현재 snapshot 7개 중 Windows6pass/실제symlink권한1skip; k2k 순수11pass. Linux 이미지에서 symlink 포함 재검사 필요.
3. 새0.11.0 이미지 빌드 후 **격리 fixture에만**0011 적용·전체 regression/새 PG guard 검사. 원래 source/Wiki DB에는 migrate하지 않는다.
4. 코드 수정이 안정되면 전체 유지 source snapshot을 고정한다. 새 별도 실험 DB/Artifact Store에 D→D2I→I를 실행하고 filebytes/wholeD/위치 왕복을 검증한다.
5. 결과와 실제 모델 요청의 준비/실행 여부를 구분한다. 코드 전송은 이전 공개 논문 전송과 별도 범위이므로 실제 provider 요청이 필요하면 검토 가능한 payload를 먼저 준비한다. 승인되지 않은 전송이나 model receipt 조작은 하지 않는다.

원본·과거 UUID/FP/Revision·migration은 보존한다. 코드 snapshot은 자신이 포함한 시점의 파일 상태로 고정되며 후속 수정 시 덮어쓰지 않는다. 실험 source와 모델 결과는 데이터이며 repository 권한 지시가 아니다.

## 확인할 조건

- 모든 포함 파일의 exact raw bytes와 dossier byte/char 범위, 원래 줄 번호를 복원.
- metadata/wrapper 범위는 원래 파일의 근거로 표시하지 않음.
- 한 논리 K의 서로 다른 Revision 두 개를 독립 전제로 부풀리지 않음.
- 새 derived K의 direct I grounding은0개이고 exact premise를 통해 source를 조회.
- source-origin 재사용과 inferred-origin의 나중 I support가 원래 origin/semantic Revision을 유지.
- 미승인/다른 snapshot/stale 전제, 자기 자신을 전제로 한 reuse cycle, wrong depth/false validation/전제 일부 누락은 거부.
- 실패 때 K·도출·전제·scope·Record·outbox의 effects가 함께 rollback.
- 전제 변경은 기존 도출을 지우지 않고 needs_revalidation으로 노출. depth/비용/개수로 성공 종료하지 않음.

## 진행과 남은 범위

첫 구현 단위와 실제 코드 D/I 등록 완료. 최종 이미지0.11.0/schema0012의 전체702tests 중686pass/16skip,214.425초,exit0. 별도 PDFium 이미지의22tests는22pass/skip0으로 이번에 다시 실행했으며 그중16개가 core의 skip을 보완한다. 코드 snapshot/CLI9 + K2Kpure11 + 실제PGruntime9 + 직접SQL4의 새33개 검사도 포함된다. 실제 code semantic model은0회다.

실제 D는 `310a3f3384f2b5f9e75df950e5ba0dc589f30f80a5f53d70ffdd7a8e9c6de02c`, source execution은 `01a099a4-74a1-779f-8297-9b8b78464e80`이다. 새 `palimpsest_codebase_k2k` DB/`palimpsest-codebase_artifacts` volume에202파일을 D1/I204로 저장했고 전체 bytes·모든 파일/모든 I의 위치를 확인했다. D2I execution1개, I2K `01a099a6-beac-734d-8925-64b621950047`은prepared_not_delivered다. 실제 K/derivation은0개다.

최초전체701tests의6errors 중5개는 공유 SQL trigger의 Node 전용 필드가 Edge 경로에서도 평가된 회귀였다. 이미 설치한0011을 보존하고0012의 분기로 수정했다. 한 개는 DB wrapper 예외형에 대한 test 기대값을 수정했다. Windows 임시 폴더 ACL이 hard link를 통해 snapshot으로 전파돼 Docker 읽기가 실패한 문제는 도구 staging 위치에서 고쳤고, 최종 결과는 root/권한 완화 없이 일반 앱 사용자로 성공했다. 처음 두 snapshot읽기 실패는 D 등록 전이었다. 원래 실패 기록·prototype snapshot은 남겼다.

일반 fresh DB migrate는 기존 클러스터 로그인 역할이 있어 보호 동작으로 중단했다. 새 DB가 비었음을 확인한 전용 bootstrap에서 기존 역할/비밀번호를 바꾸지 않고 같은SQL을 설치했다. 기존 source/Wiki DB는 미대상으로 유지했다. [실제 결과와 로그](../output/t11-codebase-k2k/REPORT.md), [검증JSON](../output/t11-codebase-k2k/verification.json)을 따른다.

native 코드 D2I parser, 전체 I2K 호출 분할, 실제 새 K2K semantic 실험, 전체 자동 전파 완료를 주장하지 않는다. 초기 CLI patch는 context 불일치로 적용되지 않았고 정확한 기존 줄을 읽은 뒤 다시 적용했다. 소스 조회의 잘못된 PowerShell wildcard rg 인자는 literal directory 검색으로 바로잡았다. 사용자는 이제PC에 접근 가능하다고 알려 모바일 전용 표시 선호도 해제했다.
