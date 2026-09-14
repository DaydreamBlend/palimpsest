# 남은 구현 — UI0.7/backend0.23 기준

2026-09-14 T24의 Realm 등록·자동 범위와 K2W/W2P 구현을 반영한 목록이다. 이전0.12/0.22 목록의 미구현 표현을 현재 상태로 재인용하지 않는다. 아래 완료 표시는 각 수직 기능의 구현 범위다. 최종 실행 명령·테스트 수·배포 확인과 알려진 제한은 [T24 보고서](../output/t24-wisdom-realm/REPORT.md)와 [실행 계획](T24_wisdom_realm_execplan.md)을 따른다.

## 이번에 확정하고 구현한 경계

새 제품 등록 CLI는 처음 D를 넣을 때 Realm을 지정한다. 기존 Data 등록 journal과 별도 Realm catalog의 연결을 coordinator가 관리한다. 원본 등록 후 분류 연결이 실패하면 같은 요청으로 복구하고, 연결이 완료되기 전에는 D2I/I2K의 컴파일 시작을 막는다. 이는 등록과 분류의 완성을 보장하는 기능이며 등록 즉시 모델을 자동 호출한다는 뜻은 아니다. 기존 저수준 Python API와 과거 unscoped import의 재생 호환성은 유지한다.

자동 I2K는 실제 입력 I의 Data가 공통으로 속한 Realm을 기본 범위로 선택한다. 모호하거나 공통 Realm이 없으면 조용히 혼합하지 않는다. 자동 K2K를 포함한 전파의 후보 범위에도 Realm 기본 선택과 명시적 교차 선택을 적용한다. 이 정책은 모든 저수준 K2K API나 N2E에 전면 격리를 추가한 것이 아니다. 이미 존재하는 필수 의존성은 Realm 필터로 버리지 않으며 처리 불가능한 의무를 성공으로 표시하지 않는다.

사용자는 Realm 혼합 자체를 오류로 보지 않는 방향으로 앞선 우려를 정정했다. 소속 수정 기능은 유지하되 분류 이동만으로 기존 K·추론을 삭제/무효화하거나 이전 실행의 frozen scope를 바꾸지 않는다. 최초 등록 Realm, 실행 때 고정한 Realm Revision, 현재 자료 분류를 구분한다. 분류 정정 시 모든 작업을 취소하거나 재검토하도록 하는 직전 backlog의 권고는 현재의 자동 처리 정책이 아니다.

Wiki의 문서는 Parchment P이고 K는 별도 지식 화면에서 조회한다. 현재 새 정식 경로는 `accepted K + Query/Context → K2W → 설명/추천 W → W2P → P → Wiki`다. K2W의 첫 범위는 exact K/EffectiveEdge를 명시적으로 선택하는 `knowledge_only` 설명·추천이다. 독립 검증을 통과한 W를 immutable snapshot으로 저장하고, W2P는 하나 이상의 W의 문구·Context·가정·한계·인용을 그대로 구성해 immutable P를 만든다. Electron에서 이 P를 읽는다. 추천은 조언이며 authority-confirmed Decision이나 자동 W2K가 아니다.

기존 논문/주제 Wiki 요약은 실제 I 기반 생성·독립 검증 기록을 가진 legacy 설명 구성이다. 이를 과거 K2W가 생성한 W/P라고 소급해서 바꾸지 않는다. 새 canonical W/P와 기존 문서가 같은 UI에서 구분되며 기존 문구·I 인용·모델 receipt는 유지된다.

## 구현된 기반

- 도구를 통한 immutable D 등록·중복 확인·원문 복원, Data series/version과 공유 blob.
- 신규 CLI 등록의 Realm 필수 지정, 중간 실패 복구와 등록 완료 gate, 직접 소속 수정 UI.
- PDF MinerU image200 + scripts, Markdown grouping, Python 코드 AST 기반 D2I와 exact I provenance. D2I application LLM 호출은 없다.
- source-only I2K 전체 I 검토·독립 검증·K 재사용, K 의미 개정, 네 N2E 관계와 applicability, Node/EffectiveEdge K2K.
- 자동 I2K 공통 Realm 선택, 자동 K2K/전파 후보의 Realm 기본 scope와 명시적 교차 선택.
- outbox/중단·재개 worker, 현재 근거 재검증, 의미 변화 기반 전파와 기존 Wiki projection의 재생성·독립 검증.
- source/topic Wiki snapshots, BGE-M3 retrieval와 근거 질문 CLI, 통합 Electron 읽기/Realm metadata 관리.
- knowledge-only K2W 설명·추천 W, exact Node/Edge citations와 독립 검증·stale commit 차단·성공 replay.
- deterministic W2P의 새 P 생성·ordered W 연결·불변 저장과 Electron의 P 읽기.

이 기반을 초기 등록부터 자동 주제 문서 생성·질문·검토까지 앱에서 연결하는 제품 흐름은 아직 남아 있다. 사용자 source DB의 schema6/10/13은 이번 작업으로 migration하지 않았다. 새 W/P 저장 검증은 격리 DB에서 수행하며 실제 사용자 자료에 대한 새 모델 호출과 구분한다.

## 우선순위

| 순서 | 기능 | 현재 남은 부분 | 완료될 사용자 동작 |
|---|---|---|---|
| 1 | 사용자 저장소 적용과 기존 문서 이관 | 새 기능의 격리 DB 구현과 실제 사용자 DB migration은 별개다. 기존 I 기반 요약을 정식 W/P로 옮기는 검토 가능한 절차도 필요하다. 과거에 없던 K2W 이력은 만들지 않는다. | 기존 자료와 근거 이력을 보존하며 새 기능을 사용할 저장소로 이관 |
| 2 | 논문·주제별 K2W/W2P 자동 구성 | 명시적 K 선택과 W/P 생성은 있다. 논문/Th17 등 주제별 K 선택, Query/Context 구성, K2W batch, 기존 문서와 새 P 연결을 자동화해야 한다. | 자료를 넣으면 관련 K에서 설명 W와 일관된 논문·주제 P 생성 |
| 3 | 앱의 자료 등록과 컴파일 진행 | 등록·Realm coordinator CLI는 있다. UI에서 파일/코드 등록, D2I/I2K/N2E/K2K/W/P 진행·실패·복구를 연결해야 한다. | Realm 선택 후 자료 등록, 진행 상태 확인, 완료된 P 열기 |
| 4 | 앱에서 새 질문·검토·승인·재개 | 검색/답변/독립 검증과 Runtime 검토 기반은 있다. UI는 저장 질문과 검토 기록 읽기가 중심이며 새 실행 조작은 미연결이다. | 질문 입력, 근거 확인, I2K 보류·정보 오류·K/Edge 재검토의 후속 작업 시작 |
| 5 | 전파와 새 W/P의 갱신 연결 | 기존 Wiki projection refresh는 있다. 새 canonical W/P에 대한 영향 추적·K2W 재생성·독립 검증·새 P 구성과 문서 대체 연결은 아직 연결하지 않았다. | K/자료 변경 뒤 기존 문서를 보존하면서 새 근거의 문서를 생성하고 비교 |
| 6 | 자료 변경과 최신 RAG 운영 | version·전파는 있다. 지속적인 변경 감지, 새 version ingestion, source별 증분 embedding/index 갱신을 운영 흐름으로 묶어야 한다. | 코드나 자료 변경 등록 후 exact version의 영향과 검색 최신 상태 확인 |
| 7 | 범용 URL/HTML·추가 코드 parser | HTML 실험 이력이 있으며 범용 제품 importer와 JavaScript/TypeScript 등 추가 native parser는 후속이다. T24에서 새 HTML parser/model 지원을 구현한 것은 아니다. | URL/저장 HTML과 여러 언어 source를 원문 보존 규약으로 등록 |
| 8 | 개인 판단·확정 결정 | 설명·추천 K2W/W는 있다. 실제 authority confirmation, Decision W, deterministic W2K, 당시 선택 이유의 Decision trace는 남아 있다. | A/B 선택과 실제 결정 이유, 당시 exact 근거를 보존 |
| 9 | 문서 편집·대체·Book | 현재 W2P는 새 immutable P 구성이다. P 편집/대체 CAS, ordered Book, 생성물 재수입 lineage와 게시 흐름은 별도 범위다. | 새 P로 문서를 대체하고 문서 묶음을 이력과 함께 발행 |
| 10 | 자동 인터넷 수집·확장 | crawler·수집 정책·중복/변경 감지의 제품 연결이 없다. | 지정 Realm과 수집 범위에서 원문/version을 보존하며 Wiki 확장 |
| 11 | 운영 배포·규모 | cross-store canonical compile, 대규모 의존성 paging/stress, 백업/복원·설치·이관 자동화가 남아 있다. 통합 UI 조회는 DB 간 컴파일 결합과 다르다. | 실험 설정에 의존하지 않는 설치·복구·대규모 운영 |

1–5가 기존 자료를 이용하는 로컬 Wiki의 다음 묶음이다. 기능이 이미 있는 N2E/K2K/worker, Realm 등록, K2W 또는 P 저장 자체를 다시 구현할 항목으로 나열하지 않고 연결과 남은 범위를 구분한다. 사용자 자료를 실제 모델에 보내는 실행과 DB migration은 각각 해당 자료·저장소의 승인 범위에서 진행한다.

## 확인 근거와 남은 실험

- [등록 계약](../docs/interfaces/REALM_REGISTRATION.md), [coordinator](../src/palimpsest/realm_registration.py), [등록 검사](../tests/app/test_realm_registration.py).
- [Realm I2K](../docs/interfaces/REALM_I2K.md), [자동 전파 범위](../docs/interfaces/REALM_AUTOMATION.md), [자동 scope 검사](../tests/app/test_realm_automation.py).
- [K2W](../docs/interfaces/K2W.md), [W Runtime](../src/palimpsest/wisdom_runtime.py), [W2P/P](../docs/interfaces/PARCHMENT.md), [사용자 W/P 구분](../docs/decisions/WIKI_WISDOM_PARCHMENT.md).
- [기존 UI·Realm 지정](../docs/interfaces/UI_REALM_ASSIGNMENT.md), [EffectiveEdge K2K](../docs/interfaces/EFFECTIVE_K2K.md), [N2E](../docs/interfaces/N2E_RELATIONS.md), [질문](../docs/interfaces/WIKI_QUERY.md).
- [paging 미구현 제안](T18_dependency_paging_proposal.md), [Decision 작업](../tasks/T09.md), [publication 작업](../tasks/T10.md).
- [기존 코드 실측](../output/t23-ui-realm/code-status.json): 전체202파일은 **I204/K0/prepared**, 통제 샘플은 기존 **K42**다. 이번 구현을 전체 code I2K의 실제 실행이나 의미 평가로 보고하지 않는다.

검증은 pure/unit, synthetic receipt를 사용한 실제 PostgreSQL, 패키지 UI 읽기, 기존 코드 이력 보존, 실제 provider 의미 평가를 구분한다. 전체 회귀 재검증의 최종 결과와 실패 후 수정 내역은 [T24 보고서](../output/t24-wisdom-realm/REPORT.md)에 기록하며, 이 backlog에서 진행 중인 결과를 완료 수치로 고정하지 않는다.
