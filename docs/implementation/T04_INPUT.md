# T04 — I2K 입력 준비와 원본 PDF 요청

2026-09-11 최신 상태: [전체 I 선택과 K/Edge Revision 저장](FULL_SOURCE_SELECTION.md)은 이후 실제 구현·실험됐다. 아래 최초 slice의 미구현 설명은 당시 상태다. 원본 PDF의 실제 provider 전달과 직접 D grounding은 여전히 미구현이며, [최신 근거 공백 정책](../decisions/I2K_DIRECT_SOURCE_EVIDENCE.md)에 따라 I2K에서 D2I를 재실행하지 않는다. 조회 구조는 [LLM Wiki의 K → I → D](../decisions/LLM_WIKI_RETRIEVAL.md)를 따른다.

2026-09-11 후속: [그룹 I 저장](GROUPED_INFORMATION.md)이 새 D2I 기본값이다. 준비 모듈은 실행의 `source-units-v1` 또는 `source-groups-v1`을 정확히 적용한다. 새 그룹 I의 본문·모든 media와 `source_assembly.content_segments`를 함께 검증·직렬화하며 기존 I와 ID/hash를 변경하지 않는다. 아래 최초229 I 실험은 그 당시 저장 단위의 결과다.

2026-09-11 첫 실행 slice. [사용자 승인](../decisions/I2K_I_FIRST_SOURCE_ON_DEMAND.md)의 I 우선 정책을 실제 canonical I 조회와 CLI에 연결했다. 모델에 보낼 입력과 요청한 원본 PDF를 **로컬에서 준비**한다. provider 전송, 모델의 원본 필요 판단, K 생성·저장은 후속 단계다. [실행 계획](../../progress/T04_input_execplan.md), [검증 결과](../../output/t04-input/REPORT.md).

## 구현된 경로

`CompilerRuntime.prepare_input`은 완료된 하나의 source D2I 실행을 읽는다. 등록 Data, parser manifest, source bundle, 파생 파일의 bytes/hash, canonical I의 내용·FP·grounding·이미지 descriptor를 대조한다. legacy 의미 I, 서로 다른 실행의 I, 변조된 내용이나 provenance를 섞지 않는다. 기존 I/Record와 ID/hash는 바뀌지 않는다.

순수 모듈 `palimpsest.i2k`는 I를 최초 원문 페이지·MinerU 읽기 순서로 정렬한다. 기본 대상은 해당 실행의 전체 I다. 명시한 I ID 목록 또는 검증된 절 projection으로 일부를 선택할 수 있다. 절 안의 source 범위에 해당하는 **I 전체**를 읽으므로 실제 입력이 절 경계를 조금 넘을 수 있다. target과 context가 겹치면 target을 유지하고 나머지 I는 excluded 목록에 남긴다. 제외 목록은 미처리 범위이며 처리 완료를 뜻하지 않는다.

Text I의 원문과 Image I의 보존 이미지, table처럼 text kind에 속한 이미지도 포함한다. media descriptor는 SHA별로 모으고 각 I의 source 관계는 유지한다. 모델용 `model_input`에는 content·I ID·FP·origin Record·Data/block/page/bbox/raw locator·grounding/parse refs·image SHA를 허용된 필드로 직렬화한다. 호스트 파일 경로, 임의 raw parser tree, 전체 원본 PDF·페이지 PNG는 자동 첨부하지 않는다. 애플리케이션용 `media_assets`는 별도 필드에 verified derived descriptor로 둔다. provider adapter는 후속 단계에서 실제 bytes를 첨부해야 한다.

`--directory`로 같은 source bundle의 evidence package를 제공하면 알려진 전사 discrepancy, 불완전한 문단 매핑과 Figure/문서 projection 경고를 전달한다. 원본의 다른 전사 전체를 초기 payload에 넣지 않는다. evidence가 없으면 `not_supplied`, 충실성 검증은 항상 `false`다. 경고가 없거나 모델이 원본을 요청하지 않았다는 이유로 충실성을 승인하지 않는다.

## CLI

DB/Artifact Store 설정은 [T02 runtime](T02_RUNTIME.md)을 따른다. 다음 명령은 앱 컨테이너 내부 경로를 사용한다. 이번 검증 image는 `palimpsest-t04-input:0.2.0`이며 Compose에서 사용하려면 `PALIMPSEST_APP_IMAGE`를 해당 값으로 설정한다. 기존 기본 tag를 사용할 때는 현재 소스로 앱 image를 빌드해야 새 명령을 사용할 수 있다.

```text
palim information prepare-input --execution-id <completed-source-execution-UUIDv7> --json
palim information prepare-input --execution-id <execution> --information-id <I-UUIDv7> --json
palim information prepare-input --execution-id <execution> --directory /evidence --section-id <section-id> --projection-sha256 <current-projection-sha256> --json
```

절 번호와 hash는 `palim information sections --execution-id <execution> --directory /evidence --json`의 현재 결과에서 함께 가져온다. `section-id`와 `projection-sha256`은 둘 다 필요하며 명시 I ID 목록과 동시에 사용하지 않는다. 변경된 projection은 `section_projection_changed`로 거부한다.

준비 결과는 `schema_version=i2k-input-v1`, `state=prepared_not_delivered`, `input_sha256`, target/context/excluded I 목록, `model_input`, `media_assets`를 포함한다. `llm_calls=0`, `actual_delivery=false`, `canonical_writes=0`, `model_budget_status=not_measured`다. SHA는 이 입력 준비물의 결속이며 실제 전송/토큰 적합성이나 K commit 시점의 read-set freshness 증명이 아니다.

원본 요청 파일은 다음 다섯 필드만 허용한다. I ID는 이 입력에 포함된 target/context 중 하나여야 한다. 페이지는 동일 Data의 1-based 힌트이며 빈 배열도 가능하다. 현재 I 밖의 페이지를 요청할 수 있지만 다른 Data로 전환할 수 없다.

```json
{
  "schema_version": "i2k-source-request-v1",
  "input_sha256": "<prepare-input에서 받은 hash>",
  "information_ids": ["<이 입력에 포함된 I UUIDv7>"],
  "question": "수치와 그리스 문자의 전사가 원본과 일치하는지 확인합니다.",
  "page_numbers": [1]
}
```

```text
palim information prepare-source --execution-id <execution> --request /requests/source-request.json --json
```

입력을 만들 때 `--directory`, `--information-id` 또는 절 선택을 사용했다면 원본 준비에도 **같은 선택 인자**를 사용한다. 애플리케이션이 현재 입력을 다시 만들고 요청의 `input_sha256`과 비교한다. 다른 hash는 `i2k_input_changed`로 거부한다. 중복 JSON key, 추가 path/data_id/status 필드, 중복/없는 I, 범위 밖 페이지를 거부한다. 요청 파일 상한은 64 KiB이고 질문은 최대 4,096자다. 이는 한 요청의 형식 한도이며 지식 전파의 성공 종료 한도가 아니다.

원본 준비는 등록된 Data의 `application/pdf` metadata, canonical object 경로, 동일 파일 descriptor로 읽은 실제 bytes의 SHA/크기를 확인한다. PDF signature를 확인하며 image-only 파생 PDF로 대체하지 않는다. missing·symlink·읽는 중 교체·hash 불일치는 실패한다. PDF bytes는 stdout에 출력하지 않는다. 원본 확인은 파일 전체를 메모리에 읽으므로 메모리 사용은 원본 크기에 비례한다.

반환값 `i2k-source-preparation-v1`은 원본 descriptor와 request/preparation hash를 포함하며 `delivery_status=not_delivered`, `request_validation=structural_only`, `model_request_observed=false`, `actual_citations=[]`다. 로컬 JSON 파일의 요청이 모델 판단이었다고 주장하지 않는다. 결과는 durable I2K job/Record로 저장되지 않는다. CLI exit 0은 준비 성공이고 의미 검증 완료가 아니다.

## 다음 실행 경계

1. 실제 provider가 I text/media와 요청 시 원본 PDF를 읽는 경로, tokenizer/이미지 비용·출력 여유, 구조화 요청과 후속 응답을 구현한다. request/delivery/use/verification을 durable Runtime에서 구분하고 실제 전송 파일·profile·I/source 인용을 남긴다. 알려진 OCR 문제에서 필요한 요청과 미요청 오류를 평가한다.
2. 첫 K kind의 identity/materiality schema와 구체 반례를 확정한다. 효력이 달라지는 미승인 선택만 별도로 제시하고, 이미 승인된 중복 reuse·같은 의미 grounding append·실질 의미 Revision 규칙을 유지한다.
3. KCompilationRecord, exact grounding, freshness/CAS, atomic canonical commit을 검증한다. I 기반 K와 N2E의 실제 PostgreSQL 검증은 후속 [Knowledge Runtime](KNOWLEDGE_RUNTIME.md)에 기록됐다. I 밖의 원본 정보는 D2I 재실행 없이 직접 D 근거와 오류 이력으로 연결해야 하며 이 경로는 아직 미구현이다. K2K·K2W·W2K·RAG·GUI와 전체 task는 완료 처리하지 않는다.
