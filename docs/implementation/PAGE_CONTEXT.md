# 페이지 조회와 인접 페이지 context

2026-09-10 추가: [PDF evidence 조회](../interfaces/PDF_EVIDENCE.md)는 같은 원본의 native text/font·후보·전사 차이·전체 Figure/페이지와 `preproc_blocks` 기반 문단 매핑을 별도 제공한다. `palim information evidence-context --directory ... --page ... --json`은 Data/파일·bundle hash를 검증하고 DB 없이 읽는다. 아래 기존 canonical I의 `pages/context` 명령은 그대로 유지한다.

## 목적과 범위

D2I가 보존한 원문 블록을 페이지별로 모아 읽고, 향후 I2K 입력에는 현재 페이지와 앞뒤 페이지를 함께 제공한다. 사용자 선택에 따라 이번 변경은 **페이지 조회와 모델 입력용 projection**부터 적용한다. 기존 canonical I의 저장 단위·ID·내용·grounding은 재작성하지 않는다. [U11](../decisions/D2I_SOURCE_PRESERVATION.md)이 허용한 context projection이며, 새 domain이나 D2K operation을 추가하는 변경이 아니다.

현재 명령은 읽기 전용이다. LLM 호출, 새 I/K 생성, semantic acceptance, outbox 처리를 수행하지 않는다. I2K 실행·후보 검증·중복 K 처리의 구현 완료를 뜻하지 않는다.

```text
Data PDF
  → MinerU와 결정적 D2I → 원문 I + exact provenance
  → 페이지별 조회 projection
  → 현재 페이지와 앞뒤 페이지 context projection
  → 후속 I2K의 구조화된 후보·검증·지식 저장
```

## 페이지별 읽기 순서

페이지 projection은 선택한 source D2I 실행의 frozen parser bundle과 그 실행이 저장한 source I를 사용한다. 같은 Data의 과거 semantic I를 함께 섞지 않는다. 원문 페이지 번호는 사용자에게 1부터 표시하며, 저장된 `page_index`는 0부터 시작한다.

현재 adapter는 원래 페이지를 보존하기 위해 cross-page merge 이전 `preproc_blocks`를 선택하고 `discarded_blocks`도 보존한다. 이 두 배열을 순서대로 이어 붙인 bundle 배열 자체는 페이지 전체의 읽기 순서가 아니다. 실제 파일에서는 각 raw block의 `upstream_metadata.index`가 MinerU 순서를 보존한다. 페이지 projection은 두 collection을 함께 이 index에 따라 정렬한다. 원래 collection, block ID, index, type, page, bbox, raw locator와 I 참조를 계속 추적할 수 있어야 한다. index가 없거나 모호한 입력을 검증된 MinerU 순서라고 표시해서는 안 된다.

예를 들어 Test_Paper.pdf의 첫 페이지는 `preproc_blocks`에 index 3–21이 있고, 그 뒤에 저장된 `discarded_blocks`에는 index 1, 2, 22, 23, 24가 있다. index에 따라 페이지 projection을 만들면 머리말을 본문 뒤에 붙이는 문제가 해소된다. 원문 블록 249개에는 모두 index가 있고 페이지 내 중복은 없었다. 이는 해당 파일의 관찰이며 모든 MinerU 출력의 보장은 아니다.

MinerU의 순서 추정 자체가 완벽하다는 뜻도 아니다. 제공 PDF의 12쪽에서는 꼬리말 하나의 index가 4여서 caption index 3과 본문 index 5 사이에 온다. 페이지 projection에서 의미를 추정해 원문을 교정하거나 순서를 다시 발명하지 않는다. 타입과 좌표를 보존해 이 문제를 확인할 수 있게 한다. index 누락·비정상 값은 `reading_order_unavailable`로 실패한다. 같은 index가 있으면 기존 parser 배열 순서를 유지하는 stable sort를 사용하고 `reading_order_ties`에 동률을 표시한다.

블록의 정확한 text는 두 줄바꿈으로 연결한다. 각 블록의 `char_start`와 `char_end`는 통합 text에서 Unicode code point 기준의 반열린 구간이며, 해당 구간을 읽으면 원래 block text를 그대로 얻는다. 추가된 구분자는 원문 block text에 속하지 않는다. 빈 text를 가진 이미지 블록도 길이 0의 구간과 이미지·I 참조를 유지한다.

본문·제목·머리말·꼬리말·쪽번호·참고문헌은 페이지 안에서 모두 보존한다. 전체 Figure와 로고의 이미지 참조는 원문 페이지 및 source I에 연결한다. 추가된 `/figures/N` 영역의 앱 설명 문구는 MinerU 원문 text와 구분한다. 페이지로 묶는 것은 저장된 189개 I나 provenance용 raw block 249개를 삭제하는 과정이 아니다. 이 파일의 조회 단위는 14개 페이지가 된다.

## 현재 페이지와 앞뒤 페이지

기본 context는 요청한 물리 페이지를 중심으로 앞뒤 한 페이지씩 포함한다. 첫 페이지는 1–2쪽, 마지막 페이지는 13–14쪽처럼 실제 문서 범위에 맞춘다. 페이지 경계를 숨긴 하나의 문자열로 취급하지 않고 중심 페이지와 참고 페이지를 구분한다.

```text
palim information pages --execution-id <source-execution-uuid>
palim information context --execution-id <source-execution-uuid> --page 11
```

두 번째 명령의 기본 페이지 범위는 10–12쪽이다. 요청한 실행, exact I ID와 원문 block refs를 유지하며 동일한 I가 여러 context에 나타나도 같은 참조를 사용한다.

현재 projection의 대상 I 소유 페이지는 그 I가 보존한 **원래 source block 페이지 중 최솟값**이다. 각 페이지의 `target_information_ids`는 그 페이지가 소유한 I만 포함한다. 인접 페이지의 I는 문맥을 위한 참조이며 새로운 처리 대상이나 독립 근거로 중복 계산하지 않는다. 이 규칙은 반복 window의 작업 배정을 위한 결정적 규칙이다. 지식의 의미가 특정 한 페이지에만 속한다는 판단은 아니다.

앞뒤 페이지가 문서 경계를 넘는 정보를 모두 해결하지는 않는다. 제공 PDF의 Figure 6은 11쪽의 그림·범례·caption과 12쪽의 이어지는 caption으로 구성된다. 중심 페이지가 11쪽 또는 12쪽이면 기본 window가 두 페이지를 모두 포함한다. 그러나 중심 페이지가 10쪽이면 window는 9–11쪽이고, 참고용 Figure 6의 caption 일부는 12쪽에 남는다.

이 경우 Figure I의 전체 source 참조를 기준으로 window 밖의 페이지를 `missing_information_pages`로 표시한다. `incomplete_information_refs`에는 해당 I와 target/context 역할 및 부족한 물리 페이지 번호가 들어간다. `target_complete`와 `context_complete`는 대상 I와 참고 I의 범위를 각각 설명한다. 중심 페이지의 대상 I가 완전해도 참고용 Figure 일부가 부족하면 `context_complete=false`다. 이 상태를 완전한 근거가 제공된 것으로 표시하지 않는다. 향후 I2K는 해당 I의 전체 근거를 추가로 가져오거나 context를 확장한 뒤 의미 판단을 해야 한다. 그 추가 읽기와 LLM 호출은 이번 조회 명령이 수행하지 않는다. Figure 5의 9–10쪽 caption도 같은 방식으로 처리한다.

실물 projection에서는 중심 페이지 8, 10, 11, 13쪽의 참고 문맥에 각각 10, 12, 9, 11쪽이 부족하다. 특히 중심 11쪽의 Figure 6은 완전하지만, 함께 들어오는 10쪽의 Figure 5 caption에는 9쪽의 그림이 연결되어 있어 전체 `context_complete`는 false다. 이 사례 때문에 특정 Figure의 완전성과 window에 보이는 모든 I의 완전성을 구분한다. 제공 PDF의 14개 중심 페이지에서는 각 `target_complete`가 모두 true였으며, 이 관찰을 더 긴 cross-page I에 일반화하지 않는다.

## 반복 window와 지식 중복

앞뒤 페이지를 겹쳐 제공하면 페이지 경계 문맥은 늘어나지만 입력량이 자동으로 줄지는 않는다. 14쪽 전체를 중심 페이지 14개로 각각 처리할 때 기본 window의 페이지 출현 횟수는 총 40회다. 호출 길이와 모델 한 번의 입력 한도를 관리하기 위한 projection이며, 전체 문서를 처리하지 않고 성공 종료하는 제한으로 사용하지 않는다.

페이지 소유권만으로 중복 K가 해결되지는 않는다. 같은 개념이 다른 페이지에 나타날 수 있고, 하나의 주장이 여러 페이지의 근거를 필요로 할 수 있다. 후속 I2K는 구조화된 후보에서 실제 사용한 I·block refs를 제시하고, 애플리케이션이 기존 K 조회, fingerprint, 의미 동등성 검증, 재사용과 atomic commit을 수행해야 한다. 모델이 같은 문장을 여러 window에서 읽었다는 이유로 새 node나 독립 support를 반복 생성해서는 안 된다. 같은 의미의 표현 변경이나 grounding 추가로 semantic Revision을 만들지 않는 기존 계약도 유지한다.

## D2I를 유지하는 이유와 오류 구분

D2I를 유지하면 원문 인식·변환 결과와 후속 의미 판단을 따로 검사하고 재사용할 수 있다. 동일한 source I에서 페이지 범위나 모델 입력 정책을 바꿔 시험할 수 있으며 모델 교체 때문에 원문을 다시 선택하거나 버릴 필요가 없다. 고정된 source bundle과 projection 정책의 반복 결과를 대조할 수 있는 것도 이 경계의 목적이다.

D2K라는 이름으로 합쳐도 PDF를 읽는 과정과 근거 연결은 필요하다. 현재 구조에서는 이 처리를 D2I로 명시해 parser 누락, 변환 오류, 모델 후보 누락과 지식 검증 오류를 구분한다. 이는 특정 모델의 우열을 판정한 결론이 아니다.

이전 Figure 4 누락은 MinerU의 해당 패널·caption 추출 누락이 아니었다. 패널 10개와 caption이 입력에 존재했지만 Generator의 29개 후보 중 해당 페이지를 근거로 참조한 후보가 없었고, 애플리케이션의 필수 Figure coverage 검사도 없었다. 모델이 필요성을 어떻게 판단했는지 내부 원인은 확인할 수 없다. 새 D2I는 그런 의미 선별을 수행하지 않는다.

## 검증 경계

실제 검증 결과와 명령·변경 내역은 [T03 실행 기록](../../progress/T03_execplan.md)에 남긴다. 필요한 검사는 페이지별 순서, raw block의 전체 coverage, I의 단일 소유 페이지, 경계 페이지, Figure 5·6의 cross-page 참조와 불완전 window 표시, 반복 출력의 안정성 및 읽기 전용 동작이다. 문서 설명이나 구조 테스트를 live I2K 의미 품질 평가로 표시하지 않는다.
