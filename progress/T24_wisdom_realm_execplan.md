# Realm 등록·자동 범위와 K2W/W2P 구분

2026-09-14 사용자 후속 요청. D는 처음 등록할 때 Realm을 지정한다. 자동 I2K/K2K는 같은 Realm을 기본 범위로 사용하고 교차 사용은 허용 가능하게 둔다. 분류 혼합 자체를 epistemic 오류로 보거나 기존 추론을 자동 삭제/무효화하지 않는다.

사용자는 처음의 'Wiki에 K 그대로' 표현을 정정했다. **Wiki는 P를 보여주고 K는 별도 조회한다.** 논문 설명과 Th17 같은 주제 설명은 Explanation W, 이 설명들을 구성한 문서가 P다. 기존 canonical의 P 입력 W필수는 유지한다. K2W는 Query/Context와 accepted K를 사용한 설명/추천이며, W2P는 문서 구성이다. K2W 명칭을 유지한다. Decision/W2K 및 Book은 이번 범위가 아니다.

현재 기존 Wiki 요약은 실제 I 기반 생성/독립 검증 기록을 가진 legacy noncanonical projection이다. 이를 과거에 실제 K2W가 수행된 것으로 위조하거나 존재하지 않는 K/W 인용을 추가하지 않는다. 기존 문구와 실제 source/receipt는 유지하고 legacy 설명 구성과 새 정식 W/P를 구분한다.

## 작업 소유와 범위

- Realm agent: 기존 import journal/external_metadata + Realm CAS를 사용하는 등록 coordinator, CLI realm 요구, 새등록의 연결 완료 검증. D/raw SHA/UUID/retry/duplicate 정책 유지. 새 schema 없이 별도 source/Realm DB 중간 실패를 복구한다.
- W contract agent: wisdom/k2w 순수 schema/구조화 prompts/검증. 첫 knowledge_only explanation/recommendation slice; 새 모델-owned IDs·Decision authority·K mutation 없음.
- W runtime agent: 추가0021 draft, same-DB canonical W·typed K/EffectiveEdge inputs·actual G/V receipt·stale/원자적 commit·replay/CLI. Root만 migration을 검토·설치한다.
- Root: 기존 D2I/I2K registration completion gate, 자동 전파 Realm scope, P/W2P의 최소 immutable 문서 구성과 계층/UI 문구, schema registry/통합·실제 격리PG·배포검증.

현재 operation_executions는 source Data를 요구하고 K2W를 지원하지 않는다. W가 가짜 대표 Data를 갖게 하지 않고 좁은 Wisdom runtime을 추가하되 profiles/hash/current K/EffectiveEdge/transaction 검사를 재사용한다. 별도 broker/framework나 W2K authority를 만들지 않는다.

## 검증·보존

신규 isolated DB에만 추가 SQL을 설치하고 기존 사용자 source DB(schema6/10/13), D/I/K/기존 Wiki JSON 및 이전 SQL0001–0020을 유지한다. 새 사용자 source/model 전송은 이 구현 요청만으로 수행하지 않는다. Synthetic receipt tests는 live 의미 평가가 아니다. typed W/P 저장·정확 인용·stale/replay/atomic rollback·Realm 등록 중간 실패/기본 범위/교차 선택을 검사한다. UI는 별도 hidden instance에서 검사하고 공용 Electron 엔진/작은 ASAR 패키지를 유지한다.

실제 진행과 제한은 아래에 누적한다. 아직 구현 완료, schema 설치, provider 성공을 선언하지 않는다.

## 완료 결과

상기 첫 구현 범위는 backend0.23/UI0.7에서 완료했다. 등록 coordinator·두 compiler gate, 자동 I2K/전파 Realm, structured K2W W 및 deterministic W2P P, Electron의 실제 P 읽기를 연결했다. 새 스키마0021/22 및 설치 후 발견한 W SQLguard 오류의 추가0023은 격리 `palimpsest_wisdom_checks`에만 적용했다. 기존 사용자 DB6/10/13과SQL0001–20은 보존했다.

관련74개pass, 최종이미지W/P17개pass, 전체 비연결앱1231개=871pass/360skip, Node71개pass, 실제P Electron32개pass, 기존자료Electron14개pass, 코드이력137개pass, 설치파일125개/구SQL20개동일을 확인했다. 첫SQL구문·commit별칭 오류와 오래된CLI mock실패를 수정하고 실패 결과도 남겼다. 모델 응답은 합성 fixture이며 live provider0, 사용자 source재컴파일0이다.

완료 보고서·실행별 counts·실패·한계는 [T24 REPORT](../output/t24-wisdom-realm/REPORT.md)에 기록했다. 기존 I 기반 Wiki 문구를 canonical W/P로 이전한 것은 아니며, 자동 주제별 K 선택/새 W/P refresh, UI 생성 조작, Decision/W2K/Book은 다음 범위다. 기본 launcher는검증한최종ASAR로전환했고 사용자 창을 조작하지 않았다.
