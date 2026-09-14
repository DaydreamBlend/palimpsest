# I2K 입력 그룹과 검색 projection 정책

2026-09-11 최신 생성 경계: [I2K 원문 정리·새 결론은 K2K](../decisions/I2K_SOURCE_ONLY_K2K_INFERENCE.md)에 따라 여러 D의 I를 함께 사용해도 명시된 내용만 정리한다. 원문에 없는 결론·추측은 I2K에서 승인하지 않으며 신규 I2K-origin Revision은 `is_inferred=false`다. 실제 다중 Data 구현·실험 상태는 [실행 계획](../../progress/T04_multi_source_runtime_execplan.md)에 기록한다.

2026-09-11 최신 후속: [LLM Wiki의 계층 조회](../decisions/LLM_WIKI_RETRIEVAL.md)는 사전 생성 K, 드문 정보의 I embedding 검색, 원본 D 확인 순서다. [직접 D 근거](../decisions/I2K_DIRECT_SOURCE_EVIDENCE.md)는 I2K 내부에서 검증하며 D2I를 재실행하거나 새 I를 만들지 않는다. 아래 별도 D2K 불필요 판단은 유지한다. [전체 I 선택·K/N2E 저장](FULL_SOURCE_SELECTION.md)은 이후 구현·실험됐고, 검색 index·원본 직접 grounding·원본 PDF 실제 모델 전달은 후속 범위다.

2026-09-11 여러 입력 형식: [D2I 형식별 처리 설계](D2I_INPUT_FORMATS.md)를 따른다. 저장 I는 원문 구조의 문맥 그룹이며 크기 제한을 위한 원문 window는 I2K에서 구성한다. PDF·HTML·Markdown·코드는 실제 위치 표현을 유지하고, 코드의 외부 정의나 웹의 외부 원글을 같은 I 원문으로 합치지 않는다. HTML/code 등 미구현 범위는 설계와 구분한다.

2026-09-11 Markdown 구현: [Markdown D2I](MARKDOWN_RUNTIME.md)는 실제 heading 기반 그룹 I와 byte/char/line provenance를 저장한다. 아래 Markdown runtime 미구현 설명 중 source 변환·저장·I2K 로컬 입력 준비는 구현됐다. 외부 media bytes 수집과 실제 I2K 모델 전달·K 저장은 후속 단계다.

2026-09-11 최신 후속: [새 그룹 I 저장 승인](../decisions/GROUPED_INFORMATION_STORAGE.md)에 따라 **스크립트 그룹 자체가 새 I의 영속 단위**가 된다. [구현과 CLI](GROUPED_INFORMATION.md)를 따른다. 아래 저장 I는 작게 두고 입력에서만 묶는 설명은 과거 I에 적용되며, 새 그룹 내부의 exact block/range/media 보존과 I2K 추가 context projection을 구분한다. 기존 I/ID/hash는 유지하고 grouping 개선은 새 source 실행으로 기록한다.

2026-09-11 후속 구현: [T04 입력 준비 CLI](T04_INPUT.md)가 canonical I content/media/provenance 구성과 등록 원본 PDF 요청의 구조 검증·로컬 준비를 제공한다. 아래 미구현 I2K runtime 언급 중 이 준비 범위는 구현됐으며, 실제 provider 전달·원본 필요 판단·추가 검증·K 저장은 여전히 후속 단계다. [실제 검증](../../output/t04-input/REPORT.md).

2026-09-11 최신 사용자 지시: **D2I 청킹은 application LLM 없이 스크립트로 구성하고, I2K에는 I만 먼저 보내며 필요하다고 판단되면 원본 PDF를 제공한다.** [최신 승인 부록](../decisions/I2K_I_FIRST_SOURCE_ON_DEMAND.md)이 직전 전체 원본 페이지 이미지 동시 입력을 대체한다. 일반 논문은 실제 I payload/출력 한도 안이면 전체 I를 순서대로 제공하고 초과할 때 절/문단으로 나눈다. Image I 자체의 이미지는 I에 포함되며 원본 PDF·전체 페이지 companion의 일괄 첨부와 구분한다. [전체 문서·절 읽기·Figure 참조 CLI](SECTION_CONTEXT.md)는 그 자료를 스크립트로 조회한다. LLM wiki/RAG의 source/input 근거와 결정 이유·K 의미 Revision의 이력을 보존하며, [현재 변경](../../progress/T03_i_first_policy_execplan.md)과 미구현 T04를 구분한다.

2026-09-10 목적 정정과 최신 지시를 반영한다. **원본 I를 보존하고 스크립트로 읽기 좋은 문맥을 구성한다. 절 이름이나 경계가 조금 달라도 I2K가 필요한 원문과 문맥을 읽을 수 있다면, 그 차이를 고치기 위한 별도 소형 LLM 사전 검토를 사용하지 않는다.** 실제 I2K에서 사소한 차이가 교정되는지는 후속 평가 대상이며 아직 입증된 결과가 아니다.

Abstract 전체와 Introduction 전체는 확인 가능한 경우 각각 하나의 논리적 그룹으로 읽는다. Results는 소절을 우선하며 Figure와 다대다로 연결한다. 이 그룹이 최초 I2K의 강제 호출 경계인 것은 아니다. 제목 없는 내용을 억지로 이 역할에 분류하는 것보다 원문과 연속 문맥을 모두 제공하는 것을 우선한다. 읽기 runtime는 상단의 후속 구현에 포함됐고 I2K runtime는 미구현이다. [이전 설계와 검증 범위](../../progress/T03_script_context_design_execplan.md)

이 문서는 [원문 보존 D2I](../decisions/D2I_SOURCE_PRESERVATION.md), [PDF 이미지 OCR 기본값](../decisions/MINERU_IMAGE_DEFAULT.md), [I 우선·원본 추가 조회](../decisions/I2K_I_FIRST_SOURCE_ON_DEMAND.md), [기존 I2K 의미 계약](../canonical/06_knowledge_operations.md), [검색 profile](../interfaces/RETRIEVAL_PROFILE.md)을 구체화한다. 모델/provider, kind registry, 검색 가중치·top-K·threshold 또는 미정 P 계약을 새로 확정하지 않는다.

## 설계 판단 — 앞단은 보존과 가독성, I2K는 의미 해석

```text
등록된 PDF D
  → MinerU image200 + 결정적 source 조립·검사
  → 원문 I + 페이지/위치/raw/이미지 근거
  → 스크립트의 전체 문서·절·문단 조회 projection
  → I2K 최초 입력: I의 content와 provenance (한도 초과 시 절/문단 분할)
  → 필요 판단 시 동일 Data의 원본 PDF 조회·제공·검증
  → I2K의 의미 해석·검증 → 기존 identity/commit 계약을 거친 K
```

저장할 I와 LLM에게 한 번에 보여 줄 묶음을 분리한다. D2I의 source 보존 계약은 그대로이며, 읽기 그룹은 Information의 조회 책임이다. 실제 모델 한도에 맞춘 호출 배정·추가 읽기·K 의미 판정은 I2K의 책임이다. D2K나 별도 public domain, 의미적으로 재작성된 I, 별도의 상시 소형 모델 서버는 필요하지 않다. MinerU 내부 OCR/layout VLM은 기존 parser profile의 일부이고, 여기서 제외하는 것은 application의 의미 분류·사전 재검토 LLM이다.

최근 [9B Q8 실험](../../output/t03-qwen9b-extended/REPORT.md)의 판정·인용·이유 코드 정확도는 문맥 수정기의 성능이다. 그 숫자를 script-only 입력의 K 품질이나 D2I의 실패율로 해석하지 않는다. 자연 검토는 522개 보존 블록 중 154개를 보여 준 제한된 후보 검토였다. `tools/run_script_context_review.py`의 `make_packets()`를 전체 문서 입력 planner로 재사용하지 않는다.

## 사소한 차이와 반드시 막을 문제

아래의 경미함은 **원문 범위·읽기 순서·원본 표제·관련 이미지가 보이고, 초과 문맥이 잘리지 않으며, 라벨로 처리 대상을 제외하지 않는 조건**에서만 성립한다.

| 상황 | 설계 판단 | 처리 |
|---|---|---|
| Abstract와 Introduction 일부가 한 묶음, Significance의 추정 역할 오류 | 조건부 허용 가능한 분류 차이 | 원본 heading과 원문 순서를 보여 주고 그룹 역할을 hint로 표시. I2K가 내용의 역할을 해석하며 I를 재분류하지 않음 |
| Results 내부 소제목 미탐지, 한 절이 여러 호출로 나뉨 | 조건부 허용 가능한 경계 차이 | 상위 heading path·원문 범위·앞뒤 문맥을 유지. 문단 또는 source 범위로 계속 처리 |
| 각주·교신·약어가 본문 묶음에 함께 존재 | 가독성과 비용 문제 | 원문 type/위치를 유지한 별도 표시로 본문과 구분. parser 추정 type만으로 본문을 처리 대상에서 제거하지 않음 |
| 실제 Abstract가 metadata로 표시되어 입력 계획에서 누락 | 입력 coverage 오류 | 역할과 무관하게 요청한 전체 범위에 기본 처리 대상을 배정. 보존됐다는 이유로 전부 읽었다고 표시하지 않음 |
| Figure 4 continuation을 Figure 5의 확정 caption으로 연결 | 근거 연결 오류 | 명시적 번호 충돌을 코드로 검사. 소속 미확정 후보로 표시하고 각 원문·페이지를 유지 |
| 이어지는 문단·캡션이 입력 밖에 존재 | 문맥 보완 필요 | exact refs와 실제 추가 조회 경로 제공. 필요한 원문이 읽히기 전에 관련 주장 검증을 완료하지 않음 |
| 페이지·block·이미지 누락, 잘못된 Data/hash/좌표 결속 | source 무결성 오류 | 기존 D2I 구조/근거 gate로 실패 처리. I2K의 추론으로 복원했다고 간주하지 않음 |
| OCR와 원본의 수치·그리스 문자·첨자 불일치 | 주장 충실성 문제 | 알려진 discrepancy를 전달하고 필요 시 원본 PDF 확인. 미해결이면 해당 K 확정을 보류. canonical I 자동 수정 없음 |

원본 이미지가 남았다고 파서의 알려진 구조 누락이 허용되는 것은 아니다. 반대로 원문과 연결 근거가 온전히 남아 있는데 사람이 선호하는 section tree와 다르다는 이유만으로 D2I 실패로 만들지도 않는다. 회복 가능한 구조 차이인지와 실제로 I2K가 회복했는지는 각각 검사한다.

## 스크립트의 최소 구성

1. **원문 순회가 기본이다.** 같은 source execution의 검증된 I/block 매핑과 MinerU 읽기 순서를 사용한다. 모든 source 범위에 기본 읽기 그룹을 배정하고, 제목 없는 첫 본문·각주·참고문헌·caption도 남긴다. 원문이 있는 곳을 `metadata`라는 추정 역할 때문에 순회에서 제외하지 않는다. 문서 전체를 요청했다면 전체 범위가 대상이며, 사용자가 요청한 일부 범위는 그 범위를 명시한다.
2. **확실한 구조로 먼저 묶는다.** 명시적 절/소절 heading을 사용하고 native font/span은 위치가 대조된 후보로만 보완한다. Abstract와 Introduction의 경계가 불확실하면 역할 미확정 원문 묶음으로 유지한다. 인라인 소제목을 못 찾으면 상위 절을 문단으로 읽을 수 있으면 된다. `para_blocks`의 join은 조회 제안이며, 원래 `preproc_blocks`의 leaf refs와 페이지를 바꾸지 않는다. 연결이 모호하면 원문 블록을 병렬로 보여 준다.
3. **Figure는 별도 참조로 붙인다.** `Figure/Figures/Fig./Figs.`, 복수 번호·범위·panel·supplement 표기를 source에 근거해 인식한다. 본문의 언급 번호와 caption 자체의 식별 번호를 구분하고 scope도 함께 대조한다. 한 문단이 여러 Figure를, 한 Figure가 여러 절을 지원할 수 있다. 번호 없는 tail은 인접성만으로 확정 결합하지 않고 후보와 원본 페이지로 남긴다. 그림 때문에 본문을 반드시 Figure 수만큼 나누지는 않는다.
4. **길이는 호출 단계에서 맞춘다.** 일반 논문의 최초 처리에서는 Text/Image I 등 전체 I의 content/provenance와 출력 여유를 합친 한도를 확인한다. 넘으면 논리적 절을 유지하며 그 아래 문단/source range window를 만든다. 경계의 앞뒤 문단과 이어지는 source refs를 참고 문맥으로 연결한다. 원본 PDF를 추가 제공할 때는 그 payload의 한도를 별도로 확인한다. 제목이 없는 구간도 원문 순서로 계속 읽으며 원본을 몰래 요약·대체하지 않는다.

외부 라이브러리·새 framework보다 기존 페이지/문단/evidence 검증을 재사용한다. 후속 구현은 `src/palimpsest/section_projection.py`가 실제 절 읽기를 소유하며, `figure_references.py`가 명시적 본문/캡션 표기를 구분한다. 기존 `pdf_visual_evidence.py`와 과거 visual 산출물은 바꾸지 않고 새 읽기 projection에서 연결을 검증한다. 실험 helper에 제품 로직을 의존시키지 않는다. 상세 slice와 기존 테스트 경로는 실행 계획에 기록한다.

## I2K에 전달할 읽기 묶음과 교정 범위

입력은 다음 정보를 함께 담는 안이다. 아래는 의미상 필요한 내용이며 새 DB/wire schema를 동결하는 것이 아니다.

전체 문서 입력은 I의 전사를 순서대로 한 번 넣고 exact source spans와 목차를 연결한다. Image I 자체의 media/content도 제공하며, 원본 PDF와 전체 원본 페이지 이미지는 일괄 첨부하지 않는다. 별도 페이지/절/캡션 JSON을 통째로 중복 첨부하지 않고 Figure/source 목록은 참조로 둔다. 필요한 원문이 있으면 해당 Data의 원본 PDF를 요청한다. 입력 구성은 OCR 충실성이나 모델의 주장 회수를 자동 보증하지 않는다.

- 대상: exact I/block/source 범위와 순서, 원문 text/table/equation, 실제 원문 heading과 그룹 경계의 확실성.
- 참고: 상위 절 경로, 경계 앞뒤 문맥과 cross-page continuation, 다대다 Figure·caption·panel 참조. 대상과 별도 표시하여 overlap을 새 처리 대상이나 독립 근거로 세지 않음.
- I의 시각 content: Image I의 실제 보존 이미지와 caption/source refs. 전체 PDF의 페이지 raster는 원본 확인용 artifact로 따로 보존하며 I media와 혼동하지 않음.
- 추가 읽기: 같은 D의 I·페이지·block·Figure anchors와 원본 PDF 요청 경로. 번호 충돌·전사 의문·잘림·필수 근거 부족이 있으면 확인할 질문과 I/source refs를 남김. 실제로 가져와 사용한 파일 SHA·페이지·영역은 단순 요청/조회 가능성과 구분해 기록.

현재 ±1 페이지의 I 조회를 활용하되 모든 절마다 항상 3페이지씩 복사하는 정책으로 고정하지 않는다. 같은 절의 연속 문단과 명시적 Figure 참조를 먼저 채우고 모호한 경계에 주변 I를 제공한다. 원본 확인이 필요하면 원본 PDF를 별도 요청한다. 전체 문서는 절/페이지/원문 번호와 범위로 된 찾아보기로 탐색할 수 있게 하며 거대한 색인도 나누어 조회한다. 새 문서 요약 LLM은 사용하지 않는다.

I2K는 묶음 이름을 참고하고 원문을 실제 근거로 사용한다. 예를 들어 한 묶음에 Abstract와 Introduction이 함께 있어도 각각의 주장·조건을 읽을 수 있다. 후반부가 앞쪽 Figure를 언급하면 문서 내 exact Figure/페이지 조회를 먼저 사용한다. 명시적 참조로 찾을 수 없는 관련 문맥은 기존 BGE-M3 검색 계약으로 보완하되, embedding 준비를 전체 원문 순회나 exact 조회의 선행 조건으로 만들지 않는다.

교정은 **이번 K 후보를 위한 읽기 범위와 해석의 조정**이다. 원본 I를 다시 쓰거나 새 의미 I를 만들지 않는다. 실제 사용한 원문 범위를 인용하고, 부정·수치·단위·조건·Figure 소속을 별도 검증한다. 이미지/텍스트 충돌이나 필수 근거 부족은 관련 후보의 보류/추가 읽기로 남긴다. 단순 경계·라벨 모호성만으로 관련 없는 전체 문서를 보류하지 않는다. 미충족 의무가 남은 전체 실행을 성공으로 표시하지 않는 기존 계약도 유지한다.

## 검증 목표와 소형 LLM 재검토의 도입 조건

기존 Test_Paper와 추가 실험 3편의 frozen 원문을 재사용해 **스크립트만으로** 전체 문서와 절 입력을 구성한다. 파서를 다시 실행하거나 모델을 추가 다운로드할 필요는 없다. source 배정·조회 실험은 상단 실행 기록에 누적하며, 아래 모델 길이·실제 전달·K 의미 품질 기준까지 통과한 것은 아니다.

- 원문/target: source 보존과 입력 배정을 별도 대조하고, 요청 범위가 기본 target에서 빠지지 않으며 겹침은 별도 context가 된다. 실제 전달·완료·미처리 상태를 입력 계획 생성과 구분한다.
- 근거/연결: exact Data/I/range/hash/좌표/이미지 연결, explicit Figure 번호 충돌, 알려진 continuation, 원문 heading 노출을 검사한다. 순서가 모호하면 그 상태를 보존하며 새 의미 순서를 발명하지 않는다.
- 길이/회복 경로: 실제 tokenizer·이미지 비용·prompt·출력 여유를 합쳐 한도 안에 구성한다. 넘치는 대상은 이어서 처리하고, 필수 context를 가져오는 exact 조회가 실제 반환하는지 확인한다. 잘린 문장을 이름만 남은 ref로 대체하고 완료하지 않는다.
- 고정 반례: metadata 속 실제 Abstract, Significance 표제, 무표제 Introduction, 인라인 Results heading, `Fig.` 표기, caption continuation과 충돌 번호를 포함한다. 모든 경우에 사람이 고른 절 이름·경계와 같아야 하는 테스트는 만들지 않는다.

T04에서는 **I 우선 입력→필요 판단→원본 PDF 요청/검증**의 실제 경로를 평가한다. 특히 알려진 OCR·기호·캡션 문제에서 필요한 원문을 요청하는지, 요청 후 실제로 확인하는지, 미요청/미해결 오류를 성공으로 처리하지 않는지 확인한다. 분할이 필요하거나 회수 품질 문제가 반복될 때 전체 I·스크립트 분할·사람이 확인한 그룹을 같은 모델과 원본 추가 조회 조건에서 비교한다. 사람 기준 입력도 요약이나 K 정답을 추가하지 않는다. 주장과 exact 근거·중대 오류 기준을 응답 전에 고정하며 같은 의미의 표현·ID 차이는 오류로 세지 않는다.

주요 결과는 주장/근거 누락, 잘못된 Figure 귀속, 수치·단위·조건·부정 변화와 근거 부족의 보류 여부다. 별도로 입력 길이·반복 context·추가 조회·전체 토큰·시간을 기록한다. 그룹 라벨 정답률은 진단용이다. 개발에 사용한 4편으로만 일반화를 주장하지 않고 다음 실제 I2K 평가에서는 구조가 다른 미조정 문서도 포함한다.

최신 지시에 따라 **별도 소형 LLM 청킹·재검토는 사용하지 않는다.** 남은 차이는 source 순서·heading·문단·명시적 참조 규칙을 개선하고 I2K에서 필요한 원문을 조회하는 방식으로 다룬다. 과거 모델 선택·실험 기록은 이력으로 유지하며 현재 기본 실행 경로로 재활성화하지 않는다.

## 저장 단위와 입력 단위

canonical I는 exact D의 원문 block·text/image/table/equation과 grounding을 보존하는 immutable snapshot이다. I 길이는 고정 token 수가 아니며 image I의 text가 비어 있을 수도 있다. I의 문자 수, 모델별 token 수, 이미지 입력 비용은 서로 다르다. 전체 길이와 각 I의 분포를 확인한 뒤 실제 모델의 입력 길이 정책을 적용한다. [현재 D/I/K/W 구조](DIKW_CURRENT.md)

입력 그룹은 exact I/source range를 모은 **versioned read projection**이다. 그룹·chunk·embedding 설정을 바꿔도 기존 I의 content, ID, FP, grounding을 재작성하거나 새로운 의미의 I를 만들지 않는다. 동일 I가 다른 그룹의 context에 다시 등장해도 같은 원문 참조다.

| 문서 구조 | 논리적 입력 그룹 | 유지할 문맥 |
|---|---|---|
| Abstract | 경계가 확인 가능하면 Abstract 전체를 하나의 그룹으로 유지 | 절 제목, exact source refs, 해당 원본 페이지. 모호하면 역할 미확정 원문 범위 유지 |
| Introduction | 경계가 확인 가능하면 Introduction 전체를 별도 하나의 그룹으로 유지 | 문단 순서, 절 제목, 필요한 인접·참조 근거. 억지로 앞쪽 본문을 분류하지 않음 |
| Results | 확인 가능한 소절을 우선 | 본문과 관련 Figure의 caption·panel·전체 Figure·원본 페이지 |
| 그 밖의 논문 절 | 원문에서 확인한 절·소절 범위 | 실제 heading path와 source 순서. 정해진 논문 양식에 억지로 맞추지 않음 |
| Markdown | 원문의 heading 계층과 그 하위 내용 | heading의 원래 수준·줄/문자 범위와 code/table/image 참조 |

PDF parser의 title/level과 native font/span은 절 경계의 근거다. native typography 후보는 여전히 `candidate_only`이며 확정된 section tree가 아니다. 제목 누락·인라인 소제목·Figure 표제와의 혼동이 있으면 불확실성을 남기고 페이지·문단 범위를 유지한다. source text를 고치거나 빠진 제목을 만들어 넣지 않는다. native PDF 문자 index를 OCR text offset으로 재해석하지 않는다. [후보 수집](../../src/palimpsest/pdf_text_evidence.py), [기존 제목 실험의 한계](../../progress/T03_heading_experiment.md)

Markdown은 단순히 `#`가 포함된 줄을 자르는 방식으로 처리하지 않는다. ATX heading과 Setext heading을 고려하고, fenced code 안의 `#` 등 코드 내용은 heading에서 제외한다. 문법이 정한 heading 수준·범위를 보존하며 code block과 본문을 혼동하지 않는다. PDF에서 생성한 Markdown heading은 parser의 추정 결과이므로 명시적 원본 Markdown heading과 구분한다. Markdown parser/runtime가 현재 구현됐다는 뜻은 아니다.

## Results와 Figure 연결

소절의 본문과 Figure는 다대다로 연결한다. 한 소절 또는 한 문단이 여러 Figure를 언급하면 해당 항목을 모두 유지하며 Figure 하나당 별도 본문으로 무리하게 분할하지 않는다. 하나의 Figure를 Results·Discussion이 함께 참조할 수도 있다.

명시적 Figure 번호·panel callout, caption과 source refs를 우선 사용한다. 시각적 근접성만으로 본문·panel·caption의 소속을 확정하지 않는다. 현재 Figure 영역·panel 연결은 조회용 제안이며, 불명확한 연결과 caption continuation을 표시하고 전체 원본 페이지를 함께 보존한다. [Figure companion 구현](../../src/palimpsest/pdf_visual_evidence.py)

PDF 기반 I2K는 parsed I를 먼저 받는다. 필요 판단 후 same-Data의 원본 PDF bytes를 제공하고 exact I/source refs·요청 이유·파일 SHA·실제 사용한 페이지/영역을 남긴다. image200의 retained PNG/좌표 변환은 보존된 조회 근거이며 처음부터 일괄 전송하지 않는다. 필요한 원본을 provider가 읽지 못하면 관련 후보를 미해결로 유지한다. OCR 충돌은 I 자동 교정이 아니라 discrepancy/검증 대상으로 남기고, I 밖의 새 원문 내용을 기존 I의 근거로 꾸미지 않는다. [최신 계약](../decisions/I2K_I_FIRST_SOURCE_ON_DEMAND.md), [PDF evidence 조회](../interfaces/PDF_EVIDENCE.md).

## 한 호출의 길이와 전체 처리 범위

문서가 짧다는 추정만으로 전체 입력이 가능하다고 표시하지 않는다. 최초에는 I content의 token/media, prompt/source refs와 출력 여유를 실제 profile로 확인한다. 필요 시 PDF를 제공할 때 그 파일/이미지 비용을 별도로 확인한다. 현재 네 논문의 whitespace 단어 수와 페이지 수는 이 한도 측정을 대체하지 않는다. I 자체의 이미지나 원문 target을 몰래 빼거나 요약으로 대신하지 않는다.

입력에 문서 전체가 들어간 경우에도 모든 K를 한 응답으로 완성할 필요는 없다. 구조화된 후보 출력과 주장·근거 검증 상태를 추적하고, 출력 한도나 미해결 근거로 남은 범위는 같은 immutable source snapshot으로 이어서 처리한다. 전체 전달, 모델의 실제 인용, 검증·commit 완료는 다른 상태다. 반복 입력은 독립 지지 근거로 세지 않으며 여러 호출의 같은 의미 후보는 기존 identity/reuse 계약을 적용한다.

하나의 논리적 그룹이 반드시 하나의 LLM 호출이라는 뜻은 아니다. 실제 모델의 tokenizer·이미지 한도·출력 여유를 포함한 context 한도를 넘으면 그룹 아래에 child token window를 만들고 계속 처리한다. 가능한 문단 경계와 원문 순서를 유지하고, 각 window에 heading path·필요한 overlap·관련 이미지와 exact source ranges를 연결한다. 한 문단 자체가 너무 길어 더 나누어도 원래 문단과 정확한 문자 범위가 남아야 한다.

target seed와 참고 context를 구분한다. target 범위가 어느 child window에 배정됐는지, 무엇이 남았는지 추적하고 overlap을 새 seed나 독립 근거로 다시 세지 않는다. seed coverage와 각 입력의 근거 완전성을 검사한다. 전부 읽었다는 사실은 모든 I에서 K를 만들어야 한다는 뜻도, 내용의 진실을 승인했다는 뜻도 아니다.

검색 top-K는 추가 context 후보를 고르는 한 호출의 정책이다. seed 원문을 잘라 버리거나 미처리 window·해결되지 않은 필수 근거가 있는데 전체 I2K를 성공 종료하는 제한으로 쓰지 않는다. 경계가 모호하거나 근거가 창 밖이면 부족한 항목을 명시하고 추가 읽기 또는 검토 상태로 남긴다. [페이지 target/context·누락 표시](PAGE_CONTEXT.md), [원문 범위 보존 규칙](../decisions/D2I_SOURCE_PRESERVATION.md)

## 의미 관련성과 provenance를 함께 사용하는 검색

기존 계약의 `seed I + same-D related I + corpus RAG related I`를 유지한다. 일반 논문의 최초 전체 처리는 한도가 허용하면 같은 D의 전체 범위를 seed 입력으로 삼고, 이후 질문·부분 재검증·긴 문서에서는 같은 D의 인접 문단·절·Figure·방법·용어를 우선 찾는다. lexical/semantic 관련성 및 중복·다양성을 함께 고려하며 모든 검색 요청마다 문서 전체를 반복 전송하는 정책으로 확장하지 않는다. [같은 D와 Information RAG](../canonical/02_information.md)

same-D 우선은 문맥을 찾는 순서이지 동의·정확성·진실의 prior가 아니다. Abstract·Results·Discussion에 반복된 같은 주장이나 겹치는 window를 독립적인 지지 근거로 가산하지 않는다. 유사한 표현에도 부정·수치·단위·범위·조건·시간이 다를 수 있으므로 similarity만으로 identity, reuse 또는 truth를 승인하지 않는다.

corpus에서 관련 근거와 상충·반박 가능성이 있는 근거를 확보하는 경로를 유지한다. 같은 D 결과만으로 외부 검토를 대체하지 않으며, 관련 근거를 찾지 못했으면 그 부족을 남긴다. 반대로 다른 `data_id`라고 반드시 독립 증거인 것도 아니다. 같은 논문의 다른 bytes나 동일 연구의 재보고·인용 여부 등 source lineage를 구분해야 한다. 근거의 강도·독립성을 임의 확률이나 가산점으로 만들지 않는다.

검색된 refs와 실제 사용한 refs를 구분하고, 후보는 실제 사용한 exact I/source 범위를 인용한다. 관련 accepted K 검색은 I2K의 identity/materiality/reuse 비교용이며, K를 직접 근거로 하는 추론은 K2K의 책임이다. ID·FP·typed refs·read-set freshness·dedupe와 atomic commit은 애플리케이션이 검증한다. [모듈 경계](MODULE_BOUNDARIES.md), [Identity/materiality 규칙](../canonical/05_identity_materiality.md)

## Embedding은 별도 profile의 파생 index

기본값은 `BAAI/bge-m3` dense embedding과 **같은 BGE-M3의 multi-vector ColBERT late-interaction 재순위화**다. 전용 `bge-reranker-v2-m3`나 새 image embedding 모델을 선택한 것이 아니다. BGE 기본 dense 차원은 1024지만 domain이나 CLI에 고정하지 않는다. [교체 가능한 profile 계약](../interfaces/RETRIEVAL_PROFILE.md)

Embedding은 immutable I 본문 밖의 재생성 가능한 검색 projection으로 둔다. exact source I/범위·bundle, embedding profile, input projection version과 입력 digest를 결속한다. 이것은 필요한 결속 관계이며 새 DB table/JSON wire schema를 이 문서에서 동결하는 것은 아니다. section 전체와 하위 문단의 검색 표현은 목적에 따라 구성할 수 있지만 원문으로 역추적해야 한다.

모델/revision/차원/전처리/입력 projection이 달라지면 query와 문서를 같은 새 profile 공간에 맞춘다. 차원이 같아도 다른 profile의 vector를 섞지 않는다. Reranker profile은 독립이며 Reranker만 바꿨다고 dense index 재작성을 강제하지 않는다. 과거 retrieval 결과·점수·profile과 원본 I는 덮어쓰지 않는다. [pgvector와 검색 저장 설계](../schema/DIKW_STORAGE_SCHEMA_V1.md)

이미지의 text 검색 표현은 실제 보존된 caption/OCR text 등으로 만들고 exact image/I refs를 연결한다. 텍스트 표현이 없으면 검색 가능한 문장을 지어내거나 임의·가짜 vector로 빈 자리를 채우지 않는다. 해당 이미지의 text index 부재를 표시하되 원본 I는 유지하고 Data/section/Figure/page 참조로 가져올 수 있어야 한다. 이미지 이해용 multimodal 입력과 image embedding index는 별개이며, 후자는 아직 구현하지 않았다.

## 현재 구현 상태와 이전 측정

- 구현됨: source I 보존·조회, [페이지 projection](../../src/palimpsest/page_projection.py), [문단·evidence context](../../src/palimpsest/paragraph_projection.py), 원본 이미지·heading 후보·불일치 근거. 후속 [PDF 전체 문서·절 읽기](SECTION_CONTEXT.md)는 모든 source의 기본 그룹 배정과 명시적 Figure 참조, snapshot hash를 확인한 전체/부분 context 조회를 제공한다.
- 재사용할 연결: evidence block/raw refs에 같은 frozen bundle의 `block_id → information_id` 매핑을 결합해 exact I를 연결한다. source range와 native/OCR 좌표 공간을 섞지 않는다.
- 이전 측정: Test_Paper의 전체 I별 길이·종류·원문 참조와 사람이 검토한 grouping preview는 [이전 결과](../../output/t03-information-context/REPORT.md)에 있다. 검토된 예시는 모든 논문의 section 자동 복원 성능을 입증하지 않는다. 현재 작업은 상단의 스크립트 우선 설계·후속 구현 계획이며 새 모델 실행이 아니다.
- 첫 구현: [I2K 입력 준비](T04_INPUT.md)는 실제 canonical I payload 구성, 전체/선택 I와 절 target/context, known evidence signals, 입력 SHA에 결속한 원본 요청 검증과 로컬 PDF bytes 준비를 제공한다. 모델 호출/전달은 0이며 요청을 모델 판단으로 기록하지 않는다.
- 아직 미구현: Markdown 입력 runtime, 예산별 I2K 호출 배정·원본 PDF의 실제 provider 전달·모델의 요청 판단·추가 검증, embedding/reranking adapter·index·검색, Generator/Validator와 K commit. 조회/로컬 준비가 해당 기능 완료를 뜻하지 않는다.

실제 실행과 검증은 [T04](../../tasks/T04.md)에서 진행한다. provider/model, 상세 registry, token-window 수치, retrieval weights/top-K/threshold, index 전환 세부 정책 등 미정 사항은 해당 구현·평가에서 구체화하며 기존 승인 밖의 의미·권위 계약을 자동 확정하지 않는다.

## 로컬 모델을 이용한 문맥 묶음 실험 — 2026-09-10

사용자는 원문 I를 보존한 문맥 묶음 제안에 소형 로컬 LLM을 시험하도록 승인했고, 비교 대상을 **Qwen3.5-4B Q4_0와 Gemma 4 E4B Q4_0**로 정정했다. 두 모델이 요구를 충족하지 못하면 **Qwen3.5-9B Q8**도 시험하도록 추가 승인했다. 이는 I2K 입력용 비canonical projection의 실험이며, source D2I에 의미 LLM을 넣거나 제품의 모델 기본값을 새로 확정하는 지시가 아니다.

모델이 제안한 source ID와 그룹 소속은 애플리케이션이 검증한다. Source coverage, 중복 ID, 존재하지 않는 ID·group 참조, 출력 완결성을 통과해야 하며, 구조를 통과해도 절/문단/Figure 연결의 의미 정확성은 별도로 평가한다. 고정 ID key를 사용해도 잘못된 소속이나 Figure 참조가 올바르게 바뀌는 것은 아니다. 불완전한 제안으로 기존 원문 I를 삭제·재작성하지 않는다.

실행 조건, 실패 및 비교 결과는 [문맥 모델 실험 기록](../../progress/T03_context_models_execplan.md)에 남긴다. 실제 논문 1개와 합성 Markdown 3개, 텍스트·page·source_type 입력으로 평가하므로 이미지 이해, 일반적인 모든 논문 성능, Markdown 전체 문법 또는 K 생성 품질까지 검증한 것으로 확대하지 않는다. 기존 heading-only 모델 실험과도 구분한다.

후속 사용자 승인에 따라 [스크립트 초안 + 9B 재검토 실험](../../progress/T03_script_context_review_execplan.md)을 진행한다. 스크립트는 원문 제목·소절과 명시적 Figure/caption/continuation 근거로 초안을 만들고, 모델은 미리 지정한 작은 후보 범위의 역할·경계·연결을 검토한다. 모델이 임의 source ID나 Figure 번호를 생성하거나 원문 caption anchor를 재작성하는 방식이 아니다. `needs_context`는 미해결 상태로 유지하며 후보에 들어가지 않은 영역까지 검증 완료로 표시하지 않는다. source I, 읽기용 기본 소속, 다대다 Figure companion 참조는 구분한다. 이 시험은 text-only context preparation이며 PDF 기반 멀티모달 I2K 계약을 대체하지 않는다.

이어 사용자는 같은 스크립트가 있으면 4B에서도 같은 결과가 나오는지 확인하도록 요청했다. [4B 비교 기록](../../progress/T03_script_context_review_4b_execplan.md)에서는 기존 Qwen3.5-4B Q4_0와 동결된 동일 입력을 사용한다. 문맥 구성·개별 판단·근거 ID·이유 코드의 동일성과 실제 속도를 구분하며, GPU 외부 부하 및 양자화 차이를 함께 기록한다. 이전 9B 결과나 원문을 새 모델 출력으로 덮어쓰지 않는다.

사용자는 이어 **Qwen3.5-9B NVFP4**가 있으면 마지막으로 같은 실험을 진행하도록 요청했고, 모델명을 다시 확인했다. [NVFP4 실행 기록](../../progress/T03_script_context_review_nvfp4_execplan.md)에 공개 파일의 revision/해시, 실제 tensor 형식, runtime 및 동일 입력 비교를 기록한다. 커뮤니티 변환본의 출처와 tokenizer/template 차이를 확인하며, 저장 형식이 NVFP4라는 사실을 모든 연산의 native FP4 실행이나 성능 보증으로 확대하지 않는다. 제품 모델 기본값은 이번 비교만으로 바꾸지 않는다.

후속 **9B Q8 추가 시험**은 [3편 53쪽의 실험 보고서](../../output/t03-qwen9b-extended/REPORT.md)에 기록했다. 12개 고유 후보를 3회 반복해 선택 33/36, 선택과 필수 인용 근거 30/36이었으며, 다른 Figure의 continued caption을 붙인 제안을 세 번 모두 유지했다. 자연 검토에서는 Significance를 Abstract로 새로 오분류했다. 스크립트의 `Fig.` 약어·무표제 절·본문 내부 소제목 및 후보 범위 누락은 별도 문제다. 522개 source 보존과 자연 모델 입력 154개를 구분하며, 이유 enum 적합성이나 반복 동일성으로 전체 의미 검증을 대신하지 않는다. 이 결과는 제품 기본값 변경이나 멀티모달 I2K/K runtime 완료가 아니다.
