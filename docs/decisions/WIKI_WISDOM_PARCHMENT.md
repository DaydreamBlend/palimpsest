# Wiki는 W를 구성한 P를 표시한다

2026-09-14 사용자 정정과 설명을 반영한다. Wiki가 K를 그대로 나열해야 한다는 직전 표현은 철회됐다. K는 별도 지식 조회에서 보고, Wiki의 문서는 Parchment P다.

논문을 설명한 결과는 Explanation 타입의 Wisdom W다. 서로 다른 논문에서 확인된 Th17 지식을 모아 질문·목적에 맞게 설명한 것도 Th17에 대한 Explanation W다. 하나 이상의 W를 구성해 논문 P 또는 Th17 P를 만든다. 한 P에 W가 하나뿐이어도 된다.

새 정식 경로는 `accepted K + Query/Context → K2W → Explanation W → W2P → P → Wiki`다. K2W는 설명·추천을 생성하고 독립 검증한다. 새 지식의 추론은 K2K 소유이며 K2W가 K를 자동 생성하지 않는다. W2P는 문서 구성과 W 인용을 소유한다. K, W, P를 서로의 ID나 Revision으로 대체하지 않는다.

이 분류는 기존 요약문의 **제품상 역할**도 설명한다. 다만 기존 paper/topic Wiki 실행은 실제로 I를 읽어 문구를 생성·검증한 비canonical projection이었다. 당시 실행하지 않은 K2W·W2P 이력이나 존재하지 않는 K/W ID를 소급해서 만들지 않는다. 원래 문구·I 인용·실제 모델 응답과 receipt는 유지한다. 새 canonical W/P와 기존 I 기반 설명 문서를 UI에서 구분한다.

첫 구현은 exact K/EffectiveEdge를 명시적으로 선택한 knowledge_only K2W, explanation/recommendation W의 불변 저장, W를 순서대로 그대로 구성한 P다. 기존 요약의 canonical 이전, 자동 주제별 K 선택, P 편집·대체·Book, Decision/W2K는 이번 구현의 완료 항목이 아니다. 실제 구현·검증은 [T24 계획](../../progress/T24_wisdom_realm_execplan.md), [K2W](../interfaces/K2W.md), [W2P](../interfaces/PARCHMENT.md)를 따른다.
