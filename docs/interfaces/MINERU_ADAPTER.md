# PDF D2I — MinerU adapter 계약

현재 기본은 [이미지 OCR 계약](../decisions/MINERU_IMAGE_DEFAULT.md)의 `mineru-hybrid-image200-v1`이다. `image_adapter`는 단일 image200 OCR raw와 retained model/origin/raster/profile을 검증하고 OCR text를 그대로 원본 페이지 좌표에 연결한다. `page.source_page_image`는 실제 parser 입력 PNG bytes의 descriptor다. `hybrid_receipt`는 공통 실행 결속을, `pdf_raster`와 `pdf_raster_adapter`는 픽셀 보존 렌더와 원본 좌표 매핑을 맡는다. 구조 검증과 의미 정확성 승인은 별개다.

직전 [이중 전사 계약](../decisions/MINERU_DUAL_TRANSCRIPTION.md)의 `mineru-hybrid-dual200-v1`도 유지한다. `dual_adapter`는 두 전체 preproc를 검증하고 국소 `transcription_selection`을 적용하며 native text/segments와 양쪽 provenance를 보존한다. CLI는 `mineru-hybrid-dual`을 명시한다. 과거 native는 `mineru-hybrid-native`이며 adapter 해석과 기존 hash는 유지한다.


2026-09-10 직전 구현 기록: [Hybrid + Pro 선택](../decisions/MINERU_HYBRID_SELECTION.md)에 따라 새 기본값은 `mineru-hybrid-preproc-v1`이다. 모든 원래 페이지의 `preproc_blocks`와 leaf span을 검증하고, `para_blocks` 문단은 [PDF evidence projection](PDF_EVIDENCE.md)에서 별도로 연결한다. 과거 adapter/profile 해석은 보존한다. [실물 검증 결과](../../progress/T03_pdf_evidence_result.md)는 아래 전체 acceptance 계약의 일부만 검증한다.

> PDF parser=MinerU는 U02, 최신 안정판 선택 정책은 U05, 원문 보존과 결정적 source D2I는 U11로 승인되었다. 아래 내부 DTO/필드와 실행 경계는 구현 초안이다. 설치/명시적 업그레이드 시 공식 최신 안정판을 선택하고 exact version/backend/실행 환경을 검증해 pin한다. MinerU upstream schema를 Palimpsest의 영구 canonical schema로 사용하지 않는다.

## 1. 정확한 위치

```text
Artifact Store의 immutable PDF D
→ Compiler Runtime의 MinerUParser adapter
→ noncanonical parse artifacts + normalized block view
→ deterministic source-unit assembly
→ schema / grounding / hash / complete page-and-block coverage checks
→ Canonical Store의 immutable Information commit
```

MinerU는 이 파이프라인의 PDF 파싱 엔진이다. parser가 0으로 종료했다는 사실과 canonical source I의 구조적 acceptance는 다르다. 어느 쪽도 객관적 진실이나 완전한 추출 충실성을 보장하지 않는다. D2I application LLM으로 수식/표/이미지를 재해석하거나 요약하지 않는다. 원본 D의 SHA-256, page/region과 parser artifact를 함께 대조한다.

## 2. 기본 배치와 의존성

첫 구현 계획은 공식 local `mineru` CLI를 subprocess/worker adapter로 호출한다. U10에 따라 Palimpsest 앱은 Python/Docker를 사용하며 MinerU는 별도 고정된 parser container/runtime으로 격리한다. 정확한 실행 profile은 검증된 구현 기록을 따른다.

현재 공식 문서는 `mineru` CLI와 CLI 내부의 local API orchestration을 설명한다. local API의 존재를 외부 hosted parsing과 혼동하지 않는다. [M1] 특정 공개 API나 `mineru-open-api` cloud client를 기본 parser로 바꾸지 않는다. 문서 bytes가 나가는 endpoint와 실효 backend를 확인하고 remote transfer에는 별도 승인이 필요하다.

실제 설치 전에 OS/CPU architecture/GPU와 accelerator runtime, memory, Python 및 MinerU 지원 조합을 inventory한다. U05에 따라 공식 최신 안정판을 선택하고 package version/digest, model identifiers/digests, runtime dependencies, code/model license 정보와 다운로드 출처를 잠금 파일 또는 parser profile에 기록한다. 최신판 선택과 해당 GPU/backend의 설치·실행 검증은 구분한다. 공식 설치 자료는 [M3][M4]를 확인한다.

## 3. Preflight와 버전 고정

확인용 공식 CLI 명령은 다음과 같다. 여기서는 실행하지 않았다. [M1]

```text
mineru --version
mineru --help
```

`palim doctor`의 parser 검사는 executable 존재, reported version, 선택 backend의 지원 여부, model readiness, output directory 권한, local/remote endpoint 여부를 secret 노출 없이 확인한다. 진단만으로 모델을 다운로드하거나 사용자 PDF를 보내지 않는다. 모델 다운로드의 네트워크 허가와 document inference의 전송 허가는 별개다.

버전의 default backend에 기대지 않고 실제 선택한 backend와 설정을 명시한다. 환경 변수·config file이 CLI 옵션을 덮어쓸 가능성도 조사하여 effective config fingerprint에 반영한다. 비밀 값은 hash 재료나 log에 넣지 않고 credential-independent profile identity를 사용한다.

## 4. Parser execution contract — 내부 초안

최소 기록할 정보:

```text
parser_execution_id
logical_compilation_fingerprint
input_data_id / input_sha256
parser_name = MinerU
parser_package_version / adapter_version
requested_backend / resolved_backend
model_artifact_refs
redacted_effective_config / effective_config_fingerprint
requested_original_page_range / completed_original_pages
execution_status / partial_or_failure_reason
output_manifest_ref / output_manifest_sha256
started_at / finished_at
```

이것은 runtime record/DTO이며 새 Data/Information layer나 public D2IRun domain을 도입하지 않는다. source unit이 생기기 전 parser 실패는 공통 operation execution에 기록한다. compilation_generation, logical request와 parse attempt를 구분한다.

같은 exact parser input/profile에서 이미 완료·무결성 검증된 artifact는 retry 때 재사용할 수 있다. package/backend/model/config/adapter version 변화는 parser-profile identity의 변화다. 새 파싱을 시작할 때 기존 artifact를 덮어쓰지 않는다. parser 교체가 기존 I의 자동 수정·재추출을 의미하지 않으며 필요한 경우 명시적 recompile generation을 사용한다.

## 5. 보존할 산출물과 normalization

공식 출력 문서는 Markdown 외에 `middle.json`, `content_list.json` 및 backend별 보조 산출물을 설명하며, 출력 집합과 구조가 backend에 따라 달라질 수 있다고 명시한다. [M2] 설치한 버전의 출력 파일을 manifest로 검사하고 schema별 adapter를 둔다. development output 형식을 영구 안정 계약으로 가정하지 않는다.

원본 parser output은 hash와 profile을 붙인 비canonical derived artifact로 보존한다. Artifact Store의 `derived/`처럼 D 원본과 분리된 namespace를 사용할 수 있으며 Canonical Store에는 필요한 provenance/manifest refs만 등록한다. raw output 파일을 그대로 검색 corpus에 넣지 않으며, 결정적 source-unit 조립·전체 coverage·구조 검사를 거친 I를 canonical로 편입한다. committed grounding을 복원하는 데 쓰는 parse artifact는 일반 임시 cache 정리로 삭제하지 않는다. 미참조 실패 산출물은 별도 retention 정책으로 정리한다.

normalized view는 최소 ordered blocks, block type, extracted text/structured content, page/region, parent-child 또는 caption relation, exact raw output locator를 제공하도록 설계한다. 표/수식/이미지의 원문 표현을 보존하며 임의로 plain text 하나로 평탄화하지 않는다. 여러 페이지에 걸친 표는 실제 여러 원문 anchor를 유지한다.

## 6. Grounding과 coordinate contract

원문 anchor와 parser-output locator를 분리한다. 예를 들어 `data_id + original_page_index + region/coordinate_system`은 PDF 원문 위치이고, `parse_artifact_hash + JSON pointer + extracted_text_hash`는 그 추출 결과의 위치/무결성이다. 추출 텍스트 hash만으로 원문 충실성이 증명되지는 않는다.

페이지 인덱스의 0/1-based 여부, 부분 파싱의 original-page offset, page size, rotation/crop과 bbox의 coordinate space를 명시한다. backend/파일 종류가 다르면 좌표 scale과 block 계층이 같다고 가정하지 않는다. adapter는 native 좌표 및 원문 PDF 좌표로의 검증된 transform을 보존한다. 해당 버전에 필요한 정보가 없으면 anchor를 추정하지 말고 unsupported/blocked로 분리한다. 그런 미해결 구조를 전체 성공으로 처리하지 않는다.

Markdown byte/character offset은 파생 텍스트의 위치다. 이를 PDF bytes의 offset인 것처럼 저장하지 않는다. scanned PDF에서 OCR이 필요한 경우 MinerU profile 안에서 처리하고, 충분한 native text가 있는 문서를 별도 OCR 파이프라인으로 반복 처리하지 않는다. 추출 confidence와 Information validation outcome은 별개다.

## 7. Failure / partial / retry

MinerU 미설치, 모델 미준비, unsupported backend/output, encrypted/corrupt PDF, timeout, process crash, missing/invalid JSON, 누락 page, resource exhaustion을 구분한다. 실패를 Information의 epistemic rejection으로 기록하지 않는다. MinerU 실패를 PyMuPDF/pdfplumber/다른 parser의 조용한 대체 성공으로 감추지 않는다. MinerU 내부 의존 라이브러리까지 금지하는 규칙은 아니다.

전체 요청에 대해 일부 페이지만 완료했다면 partial과 page coverage를 보고한다. memory window와 page batching은 모든 요청 page를 eventual 처리하기 위한 방식이다. 부분 결과를 전체 완료로 인정하거나 나머지를 버리지 않는다. 재시작은 동일 generation/request에서 미완료 page/attempt를 이어가되 committed canonical effects를 중복 만들지 않는다.

## 8. 안전한 실행

shell 문자열 대신 argument array로 실행하고, input은 검증된 Artifact Store 경로로 고정한다. 출력은 작업별 별도 staging 경로를 사용한다. input/output symlink escape, path traversal, ZIP extraction escape, 임의 파일 overwrite를 검사한다. documents/model output의 명령문은 instruction이 아니라 untrusted data다.

환경 변수나 설정에 남은 remote endpoint 때문에 승인 없이 외부 문서 전송이 일어나지 않게 한다. local profile에서 loopback listener만 허용하고 임시 worker의 ownership/cleanup을 관리한다. offline mode는 모델이 사전 준비된 상태에서 검증한다. 횟수·timeout·worker concurrency는 기술적 운영 제어이고 propagation success cutoff가 아니다.

## 9. 검증

AT90–AT102 및 AT105가 이 adapter 관련 acceptance를 정의한다. 실제 MinerU smoke는 합법적으로 사용할 수 있는 native-text PDF와 scanned/mixed PDF를 포함하고, 표/수식·한국어·읽기 순서·페이지 anchor를 원문과 대조한다. synthetic normalized fixtures만으로 upstream output 호환성이나 OCR 품질 통과를 주장하지 않는다.

## 외부 근거

[M1]–[M4]와 확인일은 [MinerU references](MINERU_REFERENCES.md)에 있다. upstream 사실과 위 Palimpsest 내부 설계 요구를 구분한다.

## U11 — source-unit 조립과 검증

`source-d2i-v1`은 exact parser artifacts에 script 기반 normalization/assembly/검사를 적용하며 application Generator/Validator LLM을 호출하지 않는다. `source-information-v1`의 source `unit_type`은 Text/Image 및 필요한 Table/Equation 표현이고 `semantic_type`은 null이다. parser의 upstream type도 보존한다. 추출된 text를 임의 요약·해석하거나 가치로 선별하지 않는다. header/footer/page number/reference text를 포함한 모든 normalized block과 모든 요청 page의 coverage map이 필요하다. unknown type이나 누락/invalid ref를 조용히 제외하지 않는다.

Figure 전체·panel·caption·continuation을 보존하며 single-panel crop을 전체 figure로 간주하지 않는다. 검토된 full-figure crop/inventory 추가는 exact Data·raw parser output·inventory hash에 결합하고 기존 raw blocks와 caption refs를 유지한다. page별 exact region을 보존한다. 실제 parent/descendant bbox들의 포락영역이면 `bbox_policy=explicit_region_envelope`, `upstream_bbox`, exact `grounding_regions`를 함께 기록하며 포락영역을 원래 parent bbox라고 표시하지 않는다.

PDF 원본 bytes는 D에 있고 raw parser 산출물은 retained noncanonical artifacts다. 추출 불확실성은 flags/profile로 보존한다. hash와 구조 검사만으로 OCR/text/읽기 순서의 완전한 충실성을 승인하지 않는다. 명백한 구조 누락은 실패이며 partial/zero-output은 전체 완료가 아니다. source-unit 수가 raw block 수와 같을 필요는 없지만 모든 block이 exact refs로 설명되어야 한다.

긴 문서의 context chunk와 retrieval filter는 exact I/source range에 연결된 별도 projection이다. 모델 교체는 I 재작성을 요구하지 않는다. 이전 semantic D2I 결과·receipt·schema는 immutable history로 남긴다. [U11 계약](../decisions/D2I_SOURCE_PRESERVATION.md)의 범위와 테스트 구분을 따른다.
