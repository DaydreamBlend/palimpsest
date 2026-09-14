# MinerU 이미지 OCR 기본값과 PDF I2K의 원본 이미지 입력

**2026-09-11 후속 우선권:** 아래 PDF I2K의 원본 이미지 필수 동시 제공 계약은 [I 우선·필요 시 원본 PDF](I2K_I_FIRST_SOURCE_ON_DEMAND.md)로 대체됐다. image200 MinerU 기본값·원본/파생 artifact 보존은 그대로 유효하다. 아래 사용자 인용과 당시 선택 이유는 이력으로 남긴다.

2026-09-10 후속 사용자 승인이다. 이 부록은 [직전 이중 전사 선택](MINERU_DUAL_TRANSCRIPTION.md)의 **신규 PDF D2I 기본 text 선택**을 대체한다. U01–U11, R07/R08, 미정 P 계약과 모든 기존 Data/raw/I/Record/ID/hash는 유지한다.

사용자 요청:

> MinerU 이미지 방식을 기본으로 하되, PDF D 기반으로 만들어진 I의 I2K 과정에서는 LLM에 파싱된 내용과 이미지화된 PDF 원본을 모두 주는 방식으로 할까?

## 새 PDF 기본값

등록된 원본 PDF를 기존 고정 renderer로 200 DPI RGB PNG로 렌더링하고 image-only PDF로 조립한다. MinerU 3.4.5 Hybrid high + Pro2605 1.2B의 로컬 이미지 OCR 전사를 그대로 source I로 구조화한다. 일반 문자 native/특수문자 OCR의 합성은 새 기본값에서 수행하지 않는다. PDF native text/font span은 제목 후보·전사 차이 검출용 별도 근거로 유지한다. 원문을 의미·중요도로 선별하거나 D2I에서 application semantic LLM을 호출하지 않는다.

새 profile은 `adapter_version=mineru-hybrid-image200-v1`, `transcription_mode=image200`, `input_mode=image_only_pdf`다. `mineru-hybrid-image-source-v1` receipt는 원본 Data SHA, 전체 원본·파생 페이지 geometry, renderer와 raster manifest, 실제 OCR route 및 middle/model/origin artifacts를 검증한다. 기존 renderer의 3500 pixel long-side cap과 실제 scale 기록을 유지하며, 회전 페이지 등 지원되지 않는 입력은 명시적으로 실패한다. 파서 실패 시 다른 parser나 native 경로로 자동 fallback하지 않는다.

원래 PDF bytes는 D의 Artifact Store에 보존한다. 200 DPI 페이지 PNG·image-only PDF는 hash가 있는 파생 artifact다. 파서 raw 좌표와 원본 페이지 좌표를 affine transform으로 함께 보존한다. 새 bundle의 `page.source_page_image`는 파서에 실제 투입한 동일 PNG bytes를 가리킨다. 저장된 I content/segments를 OCR raw와 재대조하며, 구조·coverage·hash 통과를 OCR의 의미적 정확성 승인으로 취급하지 않는다.

CLI 기본 `--parser mineru-hybrid`는 새 이미지 경로다. 과거 dual 경로는 `--parser mineru-hybrid-dual`, 과거 native 경로는 `--parser mineru-hybrid-native`로 명시한다. 과거 job을 재시도할 때 그 job의 원래 parser 선택과 exact profile을 사용한다. 새 기본값으로 과거 job/profile을 재해석하거나 기존 I를 덮어쓰지 않는다.

## PDF I2K 입력 계약 — T04 구현 예정

PDF에서 생성한 I의 I2K에는 다음을 **함께** 제공한다.

- 처리 대상 I의 exact ID, 원문 text/table/equation 표현과 순서, Data·parse·block·page·bbox·raw locator/hash.
- 해당 I의 모든 근거 페이지를 포함하는 원본 페이지 이미지. 새 image200 profile은 retained 200 DPI PNG를 재사용한다. 화면 표시용 144 DPI companion과 구분한다.
- 해당 Figure의 전체 이미지, 패널·캡션·연속 페이지와 필요한 확대 region. Figure/caption이 창 밖이면 추가 근거를 조회한다.
- 페이지·절별 입력 projection에서 주 처리 대상과 앞뒤 참고 자료를 구분한다. overlap 때문에 같은 K를 확정하는 것은 애플리케이션의 identity/FP/reuse 검사로 막는다.

페이지 이미지를 모델에 함께 전달할 수 있는 multimodal provider/adapter가 필요하다. provider가 이미지를 지원하지 않거나 exact 이미지 근거를 불러오지 못하면 text-only로 조용히 대체하지 않는다. 아직 의미 모델/provider는 새로 선정하지 않았다. 전체 논문을 매번 한 호출에 넣는 계약도 아니다. 필요한 근거를 exact refs로 추가 조회할 수 있도록 한다.

Generator는 strict structured KNode 후보와 근거를 제안하고, Validator는 원문 이미지·I에 대한 충실성과 주장 범위·조건·수치·단위·기호를 확인한다. 파싱 text와 이미지가 충돌하면 canonical I를 자동 수정하지 않고 불일치를 기록하고 해당 K 확정을 보류하는 경로를 T04에서 구현·검증한다. 모든 충돌을 자동으로 발견할 수 있다는 보장은 없다. ID/FP·typed refs·중복/재사용·read-set freshness·atomic commit은 애플리케이션 책임이며 JSON 형식만으로 의미의 정확성이나 결정론을 보장하지 않는다.

이번 T03 slice는 이미지 OCR 기본값과 재현 가능한 입력 artifact/조회만 구현한다. I2K의 multimodal model 호출·K 확정 차단·K/W 물리 저장은 아직 구현하지 않는다. [T04](../../tasks/T04.md), [현재 D/I/K/W 구조](../implementation/DIKW_CURRENT.md), [실행 계획과 검증 상태](../../progress/T03_image_default_execplan.md)를 구분해서 읽는다.

## 선택 근거와 한계

[같은 51페이지의 200 DPI 비교](../../progress/T03_paddle200_result.md)에서 image MinerU의 표적 strict 문장은 41/51, native MinerU는 32/51, image PaddleOCR는 37/51이었다. 표적 제목은 각각 50/74, 48/74, 45/74다. 이는 고정된 표본·채점 항목의 결과이며 전체 문서의 무누락률이 아니다. 직전 dual 합성은 이 전체 코호트에서 채점하지 않았다.

이미지를 함께 입력하면 원문 재확인 기회를 제공하지만 OCR 누락·Figure 잘림·첨자/그리스 문자 오독을 완전히 없애지 않는다. 원문 보존, 구조 검증, 내용 충실성 검증, 실제 주장에 대한 지식 검증은 각각 구분한다. 이번 실제 실행과 테스트 결과는 완료 후 실행 계획에 기록한다.
