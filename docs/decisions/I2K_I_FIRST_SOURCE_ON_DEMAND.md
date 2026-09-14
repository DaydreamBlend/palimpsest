# D2I 스크립트 청킹과 I2K의 I 우선·원본 PDF 추가 조회

**2026-09-13 최신 경계:** [I2K I-only·D2I 오류 보고](I2K_INFORMATION_ERRORS.md)가 I 부족을 원문으로 보완해 K를 생성하는 해석을 철회한다. 현재 I2K는 부족/오류를 사용자에게 보고하고 관련 K를 보류한다. D2I 자동 재실행이나 직접 D→K는 없다. 아래 원본 전달/직접 grounding 논의는 이전 기록으로 읽는다.

2026-09-11 최신 후속: [직접 D 근거 정책](I2K_DIRECT_SOURCE_EVIDENCE.md)에 따라 I2K의 근거 공백 때문에 D2I를 재실행하지 않는다. I에 없는 내용은 실제 등록 원본의 직접 근거와 오류/품질 이력을 남긴다. 아래 I 우선 입력·실제 전달 확인·과거 I 불변성은 유지한다.

2026-09-11 뒤이은 [그룹 I 저장 승인](GROUPED_INFORMATION_STORAGE.md)이 아래 “영속 단위 변경 아님”의 범위를 새 I 저장에 대해서 대체한다. 새 D2I는 스크립트 그룹을 canonical I로 저장하며 원문block/range/media를 그 안에 보존한다. 기존 I의 불변성과 이 문서의 I 우선·필요 시 등록 원본 PDF 제공 정책은 그대로 유지한다.

2026-09-11 사용자 후속 승인. 다음 지시를 그대로 적용한다.

> D2I에서는 llm 도움 없이 스크립트 기반으로 최대한 정확하게 청킹하도록 하고, I2K 할 땐 I만 보내고 혹시 원문이 필요하다고 판단되면 원문 PDF를 보내는 방식으로 하자.

이 부록은 [이전 원본 이미지 동시 입력](MINERU_IMAGE_DEFAULT.md)의 I2K 입력 계약 및 직전 전체 I+전체 페이지 이미지 동시 입력 정책을 **I 우선, 필요 시 원본 PDF 추가 제공**으로 대체한다. MinerU image200 parser 선택, 원본 보존, U01–U11/R07/R08와 범위 밖 P 상태는 유지한다. I의 영속 단위를 새로 바꾸거나 기존 I/ID/hash를 재작성하는 지시로 확장하지 않는다.

## D2I와 읽기 청크

MinerU의 기존 로컬 OCR/layout VLM을 이용한 파싱 이후, 읽기 순서·명시적 heading·문단·Figure 번호와 caption/continuation을 스크립트로 묶는다. 별도 application LLM의 의미 분류·요약·청크 재검토는 사용하지 않는다. 파서 내부 VLM까지 제거하거나 OCR 전체를 완전히 결정론적이라고 주장하는 것은 아니다. 동일하게 고정된 파싱 결과에 대한 스크립트 청킹의 재현성을 검사한다.

원문 I와 exact Data/page/bbox/raw locator·문자 범위·이미지 hash를 보존하고, 읽기 청크는 versioned projection으로 구성한다. 모든 source는 기본 범위에 한 번 배정하며 overlap은 참고 문맥으로 구분한다. 확실한 절/문단 경계와 Figure 참조를 우선하고, 제목 없는 본문·불확실한 경계·번호 없는 caption tail도 누락시키거나 소속을 추측해 확정하지 않는다. 역할 hint를 이유로 원문을 버리지 않는다. 청크 개선이 K 의미 Revision은 아니다.

## I2K의 최초 입력

먼저 I의 content와 exact provenance를 보낸다. 여기에는 Text I의 전사, Image I 자체의 보존 이미지/캡션 및 존재하는 다른 source 표현이 포함된다. **I-only는 text-only가 아니다.** 이미지 I를 임의 caption이나 설명으로 대체하지 않는다. 본문/참고 범위와 source 순서를 유지하고, 같은 내용을 중복 첨부하지 않는다.

일반 논문은 실제 I payload와 출력 여유가 한도 안이면 전체 I를 순서대로 제공할 수 있다. 초과하면 스크립트 청크와 필요한 인접/참조 I로 나누고 처리 범위를 추적한다. 원본 PDF와 전체 페이지 raster/companion은 최초 입력에 일괄 첨부하지 않는다. I에 있는 source ref와 원문 조회 가능성은 전달된 원본 파일 자체가 아니다.

## 원문이 필요한 경우

Generator 또는 Validator가 I만으로 필요한 사항을 확인할 수 없다고 판단하면 원본 PDF를 요청한다. 예를 들면 수치·단위·그리스 문자·첨자 전사의 의문, 잘린 Figure/캡션, 서로 맞지 않는 본문과 이미지, 페이지를 넘는 관계·레이아웃 확인, 필요한 원문 근거의 부족이다. 스크립트가 이미 발견한 discrepancy/coverage 문제는 판단에 제공하며, 모델이 요청하지 않았다는 사실만으로 알려진 문제를 해소했다고 보지 않는다. 모든 경고를 이유로 처음부터 PDF 전체를 자동 전송하는 정책도 아니다.

요청에는 관련 I/source refs, 확인할 질문/이유와 필요하면 페이지·영역 힌트를 남긴다. 애플리케이션은 해당 I의 exact `data_id`로 Artifact Store의 등록된 **원본 PDF bytes**를 찾아 SHA를 검증한다. OCR용 image-only PDF나 현재 경로의 다른 bytes로 조용히 대체하지 않는다. 읽을 페이지 힌트가 있어도 원본 PDF와 거기서 파생한 region 이미지는 구분한다. provider의 PDF 처리 방식/용량 제한은 실제 adapter 구현 시 확인한다.

요청 여부, 실제로 제공한 파일 SHA·provider/model·실행, 사용/인용한 원본 페이지·영역과 해당 I 범위를 구분해 보존한다. 필요한 PDF를 제공하지 못하거나 모델이 읽지 못하면 관련 후보를 미해결/추가 검토 상태로 둔다. 관련 없는 후보까지 자동 실패시키지 않되 미해결 의무가 있는 전체 실행을 성공 완료로 표시하지 않는다. 이 입력 정책은 provider 선택이나 범위 밖 문서의 외부 전송 권한을 새로 확정하는 계약이 아니다. 이미 승인된 범위에서는 추가 확인을 반복하지 않는다.

## K 근거와 구현 경계

원본 PDF 조회는 전체 I 검토를 유지하는 I2K의 추가 근거 경로다. K 후보는 실제 사용한 exact I/source 근거를 연결하고 원본을 확인한 기록을 덧붙인다. I에 표현되지 않은 새로운 원문 내용이나 충돌이 발견되면 기존 I를 자동 덮어쓰거나 그 I가 해당 주장을 담았다고 꾸미지 않는다. 최신 승인에 따라 D2I 재실행 없이 원본 D의 직접 근거를 검증해 K와 연결하고 누락/불일치 이력을 유지한다. 실제 원본을 확인하지 못하면 관련 후보는 미해결이다. PDF를 읽었다는 사실만으로 원문 충실성이나 지식의 진실성이 승인되지 않는다.

현재 `sections/section-context/document-context`는 원본 이미지 descriptor까지 포함하는 로컬 evidence 조회다. 이 결과 JSON 전체를 모델 payload로 그대로 전송하지 않는다. I2K의 선택적 I 직렬화·원본 PDF 요청/제공·후속 검증 실행은 [T04](../../tasks/T04.md)에서 구현한다. source I와 raw/페이지 이미지는 그대로 보존하며, 실제 결정 이유·사용한 K revision과 과거 retrieval/input snapshot도 현재 상태로 덮어쓰지 않는다.

[현재 입력 정책](../implementation/I2K_CONTEXT_POLICY.md), [읽기 CLI](../implementation/SECTION_CONTEXT.md), [변경·검증 기록](../../progress/T03_i_first_policy_execplan.md).
