# 현재 상태

문서 갱신: **2026-09-15**. 기능·실행 결과의 기준은 **2026-09-14 T24**다. **2026-09-15 사용자 요청으로 Palimpsest Docker DB·아티팩트·자격증명 볼륨 43개, DB 컨테이너 3개와 앱·PG18 이미지를 삭제했다. 아래 기능·검증은 삭제 전 결과이며 현재 조회 가능한 DB를 뜻하지 않는다.** MinerU/BGE 이미지 3개와 MinerU 모델 볼륨, 호스트의 코드·원본·모델·실행 기록은 보존했다. 재사용에는 앱 이미지 빌드와 DB 생성·자료 등록/컴파일이 필요하며, 과거 DB 이력의 완전 복구는 보장하지 않는다. 이 파일을 현재 상태의 단일 진입점으로 유지한다. 상세 계약은 [문서 인덱스](../docs/INDEX.md), 실제 검증 근거는 [T24 보고서](../output/t24-wisdom-realm/REPORT.md)를 따른다.

현재 새 실행 환경: 사용자 요청으로 단일 Compose project `palimpsest`와 앱 이미지 `palimpsest-ui:0.23.0`을 재생성했다. 새 PG18.6/pgvector0.8.6 source schema0023 및 별도 Realm catalog에 **약물치료학.pdf(37페이지)를 Realm ‘약사’로 등록 완료**했다. MinerU image200 D2I는 37/37페이지를 처리했고, 완성된 D2I를 재실행하지 않은 채 원문 페이지 I를 보강해 현재 I2K 입력은 39개 I·112개 고정 source-review target이다. 단일 대형 호출은 폐기하고 **36개 중단·재개 가능한 분할 I2K**로 전환했다. 로컬 GLM 첫 batch는 1,200초 timeout 뒤 장시간 재시도에서 65,536 출력 token 한도를 소진해 valid response가 0개다. 두 실패를 보존하고, 사용자 승인에 따라 새 frozen execution부터 GPT-5.6 Terra Medium으로 전환한다. 격리 PG의 분할/기존 회귀 검사는 통과했다. 기존 삭제 DB는 복원하지 않았다. [자료 처리 기록](../output/t26-pharmacy/REPORT.md), [분할 I2K 결과](../output/t27-batched-i2k/REPORT.md).

확인된 후속 D2I 개선: 약물치료학 본문 203,496자가 단일 I로 묶인 것은 너무 거칠다. 완료된 실행은 재파싱하지 않고 현재 I2K 실험에 사용하되, 이후 PDF profile은 페이지별 원자 provenance와 전량 coverage를 유지하면서 장·절·주제 경계의 여러 I로 결정론적으로 묶어야 한다.

## 구현과 실행 환경

| 항목 | 확인된 상태 |
|---|---|
| Backend / Electron UI | 0.23.0 / 0.7.0 ([Python](../pyproject.toml), [Electron](../desktop/package.json)) |
| 현재 런처 | [Palimpsest.cmd](../Palimpsest.cmd): 공용 Electron 엔진 + `output/t24-wisdom-realm/release-final/app.asar` |
| 앱 이미지 | `palimpsest-ui:0.23.0` 재빌드 완료; 현재 Knowledge Runtime은 로컬 GLM profile 사용 |
| W/P DB | 삭제됨. 삭제 전 격리 `palimpsest_wisdom_checks`에서 0021–0023 검증 |
| 사용자 source DB | 새 `palimpsest` project에 PG18.6/pgvector0.8.6 및 source schema0023 생성 |
| Realm 저장소 | 새 별도 Realm catalog에 약사 Realm과 자료 membership 저장 |
| Git | 로컬 최초 기준점 `c10dc88`부터 변경 추적. 그 이전 개발 commit을 재구성하지 않음 |

- **원문과 K:** immutable D·Data version, PDF/Markdown/Python D2I, source-only I2K와 독립 검증·검토·동일 의미 K 재사용이 있다. Production D2I는 application LLM을 호출하지 않으며 PDF의 선택된 MinerU 내부 OCR/layout VLM은 별도다. I2K의 I 부족/오류는 보고·보류한다. 별도 D2K는 정확한 자료에 대한 사용자 요청 범위에서만 실행한다.
- **관계와 전파:** 네 N2E 관계, exact Node/EffectiveEdge K2K, outbox worker의 중단·재개·근거 유지보수, accepted 의미 변화 기준 전파를 구현했다. 과거 run의 frozen policy와 실제 판단 이력은 유지한다.
- **Realm과 앱:** 신규 제품 등록은 source journal과 별도 Realm membership receipt를 완료해야 컴파일할 수 있다. 새 I2K는 공통 Realm, 자동 K2K/전파는 선택한 단일 Realm이 기본이며 교차 범위는 명시한다. 통합 Electron은 store-qualified 자료·근거·기존 Wiki·P를 읽고 Realm 소속을 수정한다.
- **W와 P:** `accepted exact K + Query/Context → K2W → 설명/추천 W → W2P → P → Wiki`를 구현했다. 현재 K2W는 명시적 K/EffectiveEdge 선택의 `knowledge_only` 경로다. 독립 검증된 W와 ordered W로 구성한 P는 immutable이며 추천은 확정 Decision이 아니다. 기존 I 기반 논문/주제 요약은 실제 legacy 생성·검증 이력을 유지한다.
- **검색:** 기존 Wiki projection·BGE-M3 검색·근거 질문 CLI와 독립 검증이 있다. 정식 W/P의 자동 갱신과 앱의 새 질문 실행 연결은 남아 있다.

기존 전체 202파일 코드 dataset은 **I204/K0/prepared**, 통제 코드 샘플은 기존 **K42**다. 기능 구현을 전체 dataset의 실제 I2K 실행으로 해석하지 않는다([실측](../output/t23-ui-realm/code-status.json)).

## 최근 검증과 한계

[T24 보고서](../output/t24-wisdom-realm/REPORT.md)에 최초 실패·수정·최종 결과를 함께 보존했다.

| 검증 | 최종 결과 |
|---|---|
| 관련 W/P·Realm 회귀 / 패키지 W/P | 74 통과 / 17 통과 |
| 전체 패키지 앱 검사 | 1,231개: 871 통과, 360 skip, 실패 0 |
| Node / 실제 P UI / 기존 source UI | 71 / 32 / 14 통과 |
| 기존 코드 이력 읽기 전용 검사 | 137 통과 |
| 패키지와 소스 / 이전 SQL 보존 | 125파일 일치 / 0001–0020 모두 일치 |

검사 집합은 중복되므로 합산하지 않는다. W/P 모델 응답과 receipt는 **synthetic fixture**, T24의 실제 provider 호출은 **0회**다. 사용자 자료 D2I/I2K 재실행이나 실제 논문 설명 품질 평가 결과가 아니다. 사용자 창은 조작하지 않고 별도 숨긴 인스턴스로 검사했다.

## 다음 작업

[현재 backlog](IMPLEMENTATION_BACKLOG_2026_09_14.md)의 우선순위와 승인 경계를 따른다.

1. 사용자 저장소 적용·기존 I 기반 Wiki 이관 절차를 구체화한다. 원문과 실제 이력을 보존하고 과거 K2W/W/P provenance를 만들지 않는다.
2. 논문·주제별 K 선택, Query/Context 구성, K2W batch와 W2P 연결을 구현한다.
3. 앱의 자료 등록·컴파일 진행과 새 질문·검토·승인·재개 조작을 연결한다.
4. K 변경에 따른 정식 W/P 재생성·현재 P 선택/대체·검색 갱신을 연결한다.

추가 native parser/URL importer, Decision/W2K, Book·게시, crawler, cross-store canonical compile과 대규모 paging/운영 검증도 남아 있다. 이 목록은 사용자 DB migration·새 자료 전송·provider 실행의 포괄적 승인이 아니다. 과거 계획과 결과는 [문서 인덱스의 역사 경로](../docs/INDEX.md#과거-기록)를 통해 필요한 때만 조회한다.
2026-09-15 provider change: active Generator/Validator calls now use local `glm-5.3-flash-nvidia-nvfp4` at `http://172.30.1.11:8888/v1` with context `700160`; model-list, strict JSON Schema, real PDF page-image, and provider-code live smoke checks passed. Historical Terra receipts remain unchanged.

2026-09-16 desktop recovery: `Palimpsest.cmd` now selects workspace-local store/Realm configuration for the live `palimpsest` project instead of the deleted historical example stores. A read-only bridge check returned `약물치료학.pdf`, 41 I, 448 K, five I2K executions, and Realm `약사`. The T28 reference preserves the shared fine-tuning discussion and measured GLM-5.3 deployment profile; it does not trigger model calls or change the active provider.

2026-09-17 T29 current delivery: the fresh `palimpsest-pharmacy-full` PostgreSQL
18/pgvector store contains the registered 37-page `약물치료학.pdf` in Realm
`약사`, deterministic dual-path D2I with 77 complete I, 712 accepted Korean
source K, 262 typed N2E revisions, and one accepted K2K inference (713 current K
total). BGE-M3 produced 736 searchable chunks. Fifty-nine semantic K2W groups
cover all current K exactly once and passed independent local-GLM validation. The
corrected P `01a0af4b-f2da-7465-9ca2-35514bed464e` composes 59 Explanation W into
59 sections and 702 substantive Korean claims. The replaced placeholder W and
first P remain immutable audit history. A hidden packaged Electron check connected
both configured stores and rendered the corrected P without renderer errors. Exact
counts, token usage and validation evidence are in
[T29](T29_pharmacy_full_slice_execplan.md).
