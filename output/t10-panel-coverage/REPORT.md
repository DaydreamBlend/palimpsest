# Test_Paper의 subpanel별 K 충분성 감사와 후속 설계

2026-09-13. **논문의 결과 subpanel마다 근거를 반영한 K 연결을 확인하는 것이 적절하다. 현재 구현에는 그 확인 단계가 부족하다.** 다만 새 K 수를 panel 수 이상으로 강제하면 같은 실험을 반복 저장하거나 대표 이미지와 정량 결과를 서로 독립된 증거처럼 세게 된다. 목표는 각 패널의 검토·근거 연결과 독립적인 결과의 회수다.

후속 지시와 구현: 사용자는 이 사례에 과적합하지 않고 모든 D/I/K로 일반화하도록 요청했다. [공통 원문·의미 항목 검토 Runtime](../t10-source-review/REPORT.md)을 별도로 구현했으며 아래 내용은 그에 앞선 원문/K 감사다. 패널46개에 대한 새 live LLM 회수 검증을 수행한 기록은 아니다.

이번에는 저장된 원문·I·K·UI를 읽어 감사했다. 새 모델 호출, D2I 재실행, K/Edge 생성, canonical DB 변경은 없다. 아래 후속 profile은 설계 권고이며 이미 적용·실험된 정책으로 기록하지 않는다.

## 실제 수와 의미

| 항목 | 확인 결과 |
|---|---:|
| 주 Figure | 6개 |
| 명시된 subpanel label | 46개: Fig1 11, Fig2 7, Fig3 5, Fig4 7, Fig5 8, Fig6 8 |
| 현재 I에서 확인된 panel label | 46개 모두 |
| label을 포함한 caption | 8개 fragment, 그룹 I 4개 |
| 현재 parser의 이미지 영역 | 36개; labelled subpanel 수와 다름 |
| Test_Paper의 실제 current K | 32개: Observation 24, Proposition 8 |
| 현재 선택 source 실행에도 grounding이 있는 K | 21개 |
| 이전 source 실행 grounding만 있는 K | 11개 |
| Wiki 본문의 요약 항목 | 13개 |
| 현재 Wiki UI의 관련 K | 서로 다른 KRevision 21개 |

세 논문 전체 검색 index의 K 30개도 위 32/21/13과 다른 집합이다. **32÷46을 K 회수율로 계산할 수 없다.** 하나의 K가 여러 패널에 근거할 수 있고 하나의 패널에도 여러 조건·readout·결과가 있기 때문이다. 전수 의미 검토가 없으므로 누락 패널 수나 완전성 점수는 아직 모른다.

source 감사는 [46개 label의 exact I/문자 범위/원문 참조](figure-inventory.md)와 [기계 판독 목록](figure-inventory.json)에 있다. DB 감사는 [K와 UI/index 구분](knowledge-audit.md), [실제 read-only SQL 결과](knowledge-audit.json)에 있다. 과거 parser block ID를 현재 I에 옮기지 않았으며 서로 다른 실행의 참조를 구별했다.

## 왜 빈약하게 보이는가

첫째, Wiki 본문은 13개 요약 항목이고 canonical K 전체 목록이 아니다. 현재 관련 K 탐색은 선택한 source 실행의 정확한 I grounding에 결속돼 있어 과거 실행에만 근거한 11개 K를 표시하지 않는다. 이 K가 DB에서 사라졌다는 뜻은 아니다. 후속 UI에서는 과거 source 근거를 가진 K도 별도 표시할 수 있지만, 새 I에 검증 없이 옮겨 연결해서는 안 된다.

둘째, 실제 의미 추출도 더 세밀하게 평가해야 한다. 기존 [독립 의미 검토](../t04-full-selection/semantic-review.md)는 12시간 neutrophil 증가와 대비되는 24시간 neutrophil/apoptosis 정보가 32개 K에서 충분히 표현되지 않았다고 명시한다. 관련 I와 원본 이미지는 남아 있다. 이번 감사에서도 기존 K 목록과 Figure1 원본 crop을 확인했다. 이 사례는 K 선택·표현 부족이며 D2I 누락의 증거가 아니다.

셋째, 현재 완료 검사는 I 단위다. [선택 schema](../../src/palimpsest/i2k_selection.py)는 각 information_id의 검토와 candidate 참조를 확인한다. [Generator/Validator prompt](../../src/palimpsest/selection_prompts.py)는 대조군·음성 결과·시간 비교의 중요성을 지시하지만 Figure/panel별 결과 목록을 요구하지 않는다. 따라서 Figure1과2의 caption이 함께 든 큰 I 하나를 selected/confirmed로 처리해도 그 안의 모든 관측이 회수됐다고 볼 수 없다. 과거 completed Record는 당시 정책의 결과로 보존해야 한다.

## 권고하는 I2K 검토 단위

**결과를 제시하는 각 subpanel은 원칙적으로 한 개 이상의 검증된 K와 연결한다.** 새 K 생성, 같은 의미의 기존 K 재사용, 해결되지 않은 근거, 독립 결과가 없는 도식/방법 설명의 정당한 예외를 구분해 기록한다. 대조군이나 유의하지 않은 결과라는 이유만으로 예외로 처리하지 않는다. 판단은 LLM과 독립 Validator가 하고 스크립트는 목록·참조·검토 누락을 검사한다.

| 상황 | 처리 |
|---|---|
| 한 패널의 독립적인 실험 결과 | 조건·대조군·readout·시간·결과를 가진 source-specific K에 연결 |
| 대표 이미지와 같은 결과의 정량 패널 | 같은 의미 K에 양쪽 근거를 연결; 독립 실험으로 중복 계산하지 않음 |
| 한 패널 안의 서로 다른 조건·readout/결과 | 독립적으로 평가할 수 있는 주장 단위로 여러 K를 검토 |
| 결과가 유의하지 않거나 차이가 없는 관찰 | 범위와 불확실성을 보존한 Observation 후보로 검토 |
| 방법 도식/기존 지식의 설명 | 해당 의미를 담은 기존/신규 K 또는 구체적 예외 사유를 독립 검증 |
| I가 불충분하거나 시각 근거가 모호함 | 원본 D 조회와 근거 공백 이력; D2I를 재실행하지 않고 unresolved 상태 유지 |

Figure1B의 대표 flow plot과 Figure1C의 12시간 정량 결과처럼 같은 관찰을 보여주는 부분은 같은 K를 뒷받침할 수 있다. 반면 Figure1C의 다른 시간 비교를 12시간 효과로 덮었다고 가정하면 안 된다. 정확한 묶음과 신규 K 여부는 이번 감사에서 확정하지 않았으며 실제 caption·본문·이미지를 함께 받은 모델/Validator의 근거 판단이 필요하다.

## 최소 후속 구현

1. **목록을 I2K 입력에 결속:** 기존 I의 caption·보존 이미지·원문 위치에서 Figure/panel 검토 목록을 구성한다. 이번 46개 목록은 한 논문의 기준 사례다. 다른 논문의 label OCR 누락·continued caption·무표기 panel은 별도 불확실성으로 남기고 자동 추정치를 완전한 정답 목록으로 쓰지 않는다. I 행이나 원본 artifact를 다시 만들지 않는다.
2. **Runtime 검토 출력 확장:** 기존 I별 reviews를 유지하면서 panel별 outcome, candidate key 또는 exact KRevision, 실제 caption/body/image evidence와 간결한 이유를 추가한다. 요청 당시 목록/profile/입력 hash, 실제 전달과 독립 Validator 판정을 보존한다. 새 Runtime profile로 시작하고 이전 schema/Record를 재해석하지 않는다.
3. **완료 조건 보강:** 모든 I와 목록의 모든 panel을 검토하고, 중요한 독립 결과가 빠진 패널·미전달 원문 요청·needs_review가 남으면 성공 완료로 표시하지 않는다. 전체 caption 인용이나 `complete=true`만으로 panel을 covered로 세지 않는다. label 하나만 인용한 결과도 충분한 근거가 아니다.
4. **정상 K 반영 후 N2E:** 기존 dedupe/reuse/atomic commit을 재사용한다. 같은 의미의 근거 추가는 새 semantic Revision을 만들지 않는다. Observation → 저자가 보고한 Results Proposition → 전체 결론의 연결은 N2E에서 별도 검증하며 스크립트가 supports를 자동 생성하지 않는다. 원문에 없는 새 결론은 K2K에만 둔다.
5. **UI 노출:** 논문 페이지의 Figure별로 검증된 K 연결·재사용·보류/미검토 수를 표시하고 패널 → KRevision → 정확 I/원본으로 이동한다. 본문 요약과 전체 K 수, 현재 source와 과거 source 근거를 분명히 표시한다. 기존 source를 현재 source인 것처럼 표시하지 않는다.

실제 적용 검사는 panel 하나의 누락, continued caption, 한 K에 연결된 복수 패널, 한 패널의 복수 관찰, null result 누락, 임의 bbox/미전달 media, 과거 source grounding, 같은 의미 재사용과 Revision 보존을 포함해야 한다. 이후 Test_Paper 46개 목록으로 새 profile의 실제 I2K/N2E를 평가한다. 이번 감사는 그 실행을 대신하지 않는다.

## 이번에 완료한 범위

- 과거 source inventory와 현재 caption의 46개 label 일치, 원본 PDF 및 관련 보존 이미지 hash와 exact marker 위치를 확인했다.
- 실제 별도 wiki_pg DB에서 K 종류·source grounding·UI/index 범위를 읽기 전용으로 확인했다.
- 같은 파일을 읽어 낸 label match는 의미적 검증 결과로 승격하지 않았다.
- Runtime code·schema·DB 효과는 변경하지 않았다. 새 K 연결과 패널 완전성 점수는 아직 없다.

이전 Electron 구현은 [별도 완료 보고서](../t09-electron/REPORT.md)에 있다. 사용자가 스마트폰으로 대화를 보고 있으므로 실제 패키지의 [I 근거 패널](../t09-electron/phone-review/01-information.png), [원본 강조 영역](../t09-electron/phone-review/02-original-region.png), [검증된 답변 패널](../t09-electron/phone-review/03-answer.png)을 좁은 화면 캡처로 준비했다. 이는 웹 공개나 모바일 앱 배포가 아니다.
