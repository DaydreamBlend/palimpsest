# U11 — 원문 보존 D2I와 구조화된 지식 compilation

> 상태: accepted scoped policy, 2026-09-09. 사용자의 새 정의가 기존 D2I semantic Generator/Validator 설계보다 우선한다. 정책 승인과 실제 앱·migration·PDF 품질 검증 완료는 구분한다. P01–P12의 나머지 제안은 승인하지 않는다.

## 사용자 승인 근거

사용자 메시지 전문:

> 일단 D2I 자체는 PDF등 LLM이 읽기 어려운 파일을 읽기 쉬운 형태로 바꾸는 것에 의의가 있어. 그러니까 D2I는 최대한 D 원본을 보존하면서, 페이지 정보나 위치 정보 등을 포함해야 해.
>
> Terra Medium 등 LLM 부분은 I2K 단계부터 적용하는 방식으로 해야해.

후속 사용자 메시지 전문:

> 지금 우리가 만드는 건 일종의 LLM wiki인데, 구조화된 출력을 사용해서 최대한 결정론적인 결과가 나오는 거야. Provenance도 보존되어야 하고.
>
> 그러니까 D2I는 최대한 스크립트 기반의 결정론적인 작업이어야 해. I2K나 N2E, K2K, K2W는 어쩔 수 없이 LLM이 관여해서 상황에 따라 달라질 수도 있겠지만, 이것도 출력을 최대한 구조화해서 중복 노드 생성이나 주관 개입 등을 피해야 해.
>
> 이 부분을 잘 생각해서 작업해주면 좋겠어.

## 승인된 단계 경계

```text
immutable Data bytes
→ local MinerU parser → retained noncanonical parser artifacts
→ versioned deterministic normalization / source-unit assembly
→ structural, hash, page/region and complete block-coverage checks
→ immutable source Information + exact provenance + durable Record
→ I2K structured semantic proposals / independent validation
→ accepted K with application-controlled identity, reuse and atomic commit
```

D2I는 원본 표현을 읽기 쉬운 구조로 옮긴다. D2I의 새 application 단계에는 LLM Generator/Validator 호출이 없다. 원문을 임의로 요약·해석하거나 주관적인 정보 가치에 따라 남길 내용을 고르지 않는다. MinerU 자체의 OCR/layout/model inference는 parser profile에 기록하는 추출 과정이며, 이것을 Palimpsest의 semantic LLM 승인으로 취급하지 않는다. local parser 실패를 다른 parser나 LLM으로 조용히 대체하지 않는다.

Information의 새 profile은 `source-information-v1`이다. `unit_type`은 Text/Image 및 필요한 Table/Equation 같은 원문 표현의 종류를 나타내며 proposition/observation 같은 semantic kind가 아니다. 새 source Information의 `semantic_type`은 null이다. physical registry와 추가 migration은 해당 구현 slice가 관리한다. 신규 I의 opaque ID는 UUIDv7이고 identity는 exact Data와 source grounding에 종속된다. 같은 문장이라도 다른 Data의 I로 병합하지 않는다.

새 D2I 처리 profile `source-d2i-v1`은 parser/package/backend/model artifact/config/adapter, source-unit schema·assembly·검사 version을 고정한다. 새 D2I의 model/prompt profile을 만드는 대신 결정적 처리 profile과 input/output/manifest digest를 기록한다. 같은 고정된 parser 산출물과 처리 profile에 대한 script 결과는 재현 가능해야 한다. 서로 다른 GPU/backend/추출 model에서 PDF parsing 자체가 bit-for-bit 같다는 보장은 하지 않는다.

## 최대한 보존한다는 뜻

- D에는 PDF 원본 bytes와 raw-byte SHA-256을 그대로 보존한다. I는 원본 bytes 재현물을 대신하지 않으며 D와 retained parser artifacts로 역추적할 수 있어야 한다.
- parser가 추출한 text, reading order, 원문 type, parent/child와 segment 관계를 보존한다. 제목·본문·header·footer·page number·reference text도 가치 판단으로 삭제하지 않는다. 알려지지 않은 type은 원문과 명시적 상태를 보존하거나 unsupported로 실패하며 조용히 버리지 않는다.
- 모든 요청 page와 모든 normalized source block은 canonical source units의 coverage map에 연결한다. 한 source unit이 여러 block을 포함할 수 있고 figure와 caption 같은 refs를 공유할 수도 있다. 누락·unknown ref·잘못된 page/region·손상 artifact·검증할 수 없는 구조는 완료로 처리하지 않는다.
- Figure는 전체 figure, 각 panel, caption과 continuation을 보존한다. 제공 Test_Paper.pdf에서는 6개 전체 Figure에 대한 원문 대조와 coverage를 확인한다. 단일 panel crop을 전체 Figure라고 표시하거나 별도 페이지 caption을 근거 없이 합치지 않는다. 검토된 full-figure crop/inventory를 추가하면 exact Data·parser output·inventory hash에 결합하고 기존 raw blocks도 유지한다.
- 각 I는 Data ID, original page index/size와 coordinate convention, region, parser profile/version, raw artifact locator, source block refs, text/image/manifest hash 또는 stable anchor를 보존한다. 여러 페이지의 unit은 page별 exact regions를 유지한다. parent/child의 실제 bbox 포락영역을 사용하면 `bbox_policy=explicit_region_envelope`, 원래 `upstream_bbox` 및 `grounding_regions`를 함께 보존한다. 포락영역을 단일 exact raw bbox라고 부르지 않는다.
- 원문 extraction의 불확실성·parser confidence/오류 가능성은 flags와 provenance로 보존한다. PDF 전반의 text/order/시각적 충실성을 hash만으로 증명할 수 없다. 명백한 구조 누락은 실패이며, 이를 성공 flags 뒤에 숨기지 않는다.

## acceptance·실행·이력

새 D2I의 `accepted`는 source-unit schema, grounding, digest, coverage와 저장 불변조건을 통과해 canonical commit되었다는 뜻이다. 이는 내용의 참·거짓, 해석의 타당성, 사람의 원문 충실성 승인 또는 완전한 OCR 품질 보증이 아니다. parser/execution failure는 epistemic rejection이 아니며 후보·기록·재시도 상태를 보존한다. partial/zero-output/blocked는 전체 성공이 아니다.

원문 보존 대상 전체가 검증되기 전에 일부만 canonical 성공으로 공개하지 않는다. 검증된 I/grounding/provenance, durable Runtime Record, 필요한 candidate cleanup 및 outbox를 같은 승인된 commit 경계에서 반영한다. 평범한 retry는 같은 generation의 성공을 재생하고, 명시적 recompile/repair는 별도 generation으로 추적한다. 같은 exact input의 동시 요청은 unique constraint 또는 동등한 atomic guard로 중복 canonical effects를 막는다.

U11 이전 semantic I와 Generator/Validator receipt, terminal Record, ID/hash 및 설치된 migration은 immutable history로 남긴다. 과거 결과를 source-information-v1로 재분류하거나 판정을 고쳐 쓰지 않는다. source Information은 별도 profile과 additive migration으로 편입하며 자동으로 이전 I를 supersede하지 않는다. 필요한 repair/supersession은 명시적 경로와 기존 current-support revalidation 계약을 따른다. 이전 실물 시험의 Text23/Image5 결과는 U11 전체 원문 coverage의 통과 근거가 아니다.

## I와 context projection

canonical I는 원문 보존 단위다. 긴 문서를 모델 context 길이에 맞추는 chunk, overlap, embedding input, rerank input, header/footer 제외와 retrieval 선택은 versioned projection이다. projection마다 어느 exact I/source range에서 왔는지 추적한다. 한 번의 모델 context 제한으로 원문 I를 버리거나 전체 처리를 성공 종료하지 않는다. 모델 또는 chunk policy를 바꿔도 canonical I를 재작성할 필요가 없다.

## I2K 이후의 결정성 책임

I2K부터 의미 해석과 K 채택을 위한 LLM을 사용한다. I2K/N2E/K2K/K2W는 versioned strict structured output, exact input refs와 별도 validation을 사용해 임의 표현과 주관 개입을 줄인다. JSON schema 통과만으로 의미적 진실·동등성이나 완전한 결정론을 보장하지 않는다. 실질적인 의미 판단은 출처와 관련 accepted 지식에 근거해 검증한다.

ID 생성, canonicalization/fingerprint, exact retry/replay, dedupe/reuse 검사, allowed typed refs, 권한, read-set freshness와 atomic commit은 애플리케이션 책임이다. 모델이 제안한 ID나 자유 형식 주장만으로 새 canonical node/revision을 만들지 않는다. 같은 의미의 표현 변경·새 grounding·endpoint-only rebase는 기존 계약대로 K semantic Revision을 만들지 않는다. 독립 근거는 append-only support로 남기고 provenance를 치환하지 않는다.

W2K는 기존대로 실제 authority-confirmed Decision만 결정론적으로 처리하며 LLM 호출이 없다. 이번 U11은 I2K 이후 실행을 자동 착수하거나 빈 future module을 만드는 승인이 아니다. 아직 미정인 public K revalidation subtype과 관련 P 계약은 그대로 남는다.

## 적용 문서와 검증 범위

[현재 canonical](../canonical/PALIMPSEST_CANONICAL_MODEL.md), [MinerU adapter](../interfaces/MINERU_ADAPTER.md), [CLI 계약](../interfaces/CLI_CONTRACT.md), [모듈 경계](../implementation/MODULE_BOUNDARIES.md), [T03](../../tasks/T03.md)에 적용한다. [직전 canonical snapshot](../history/2026-09-09_pre_d2i_source_preservation.md)은 변경 전 bytes를 보존한다. 기계 판독 승인은 [user_overrides.json](user_overrides.json)에 기록한다.

문서 validator는 U11의 승인 근거·정책·snapshot·task 연결을 검사한다. 실제 source-unit 변환, PostgreSQL atomicity/retry, parser/native/scanned/mixed PDF 품질, 전체 Figure·block coverage는 각 앱 테스트와 원문 QA 결과로 별도 보고한다. 문서 체크를 앱의 완료 근거로 쓰지 않는다.

## 2026-09-10 최신 후속 — 이미지 OCR과 원본 이미지 동반 I2K

[사용자 후속 선택](MINERU_IMAGE_DEFAULT.md)에 따라 신규 PDF D2I는 200 DPI 이미지 기반 MinerU OCR을 기본으로 한다. OCR text는 source I로 보존하고 native PDF text는 별도 차이 검출/제목 후보 근거로 남긴다. I2K는 parsed I와 exact 원본 페이지/Figure 이미지를 함께 입력받는 계약이며 해당 의미 runtime은 T04에서 구현한다. 이 선택은 D 원본·과거 I/IDs/hashes 불변과 semantic LLM의 I2K 경계를 바꾸지 않는다.
