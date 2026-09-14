# 사용자 요청 D2K

[승인 규약](../decisions/USER_REQUESTED_D2K.md)에 따른 독립 예외 경로다. `d2k`는 I2K 내부 fallback이 아니며 D2I를 호출하거나 I를 생성하지 않는다. 사용자에게 보고한 D2I 오류 또는 사용자가 설명한 실패를 입력으로 보존한다. 오류 설명만 있는 경우 `user_reported_not_independently_verified`를 유지한다.

## 준비·확인·실행

CLI는 `palim d2k` 아래에 있다. `draft`는 등록 D bytes를 읽어 원문 범위를 고정하고, `preparation`은 검토할 manifest 전체를 출력한다. `authorize`는 사용자가 확인한 정확한 manifest SHA·actor를 append-only 기록으로 저장한다. `prepare`는 확인 기록으로 실행을 만들고, `request`는 Generator 또는 Validator 전달 파일을 준비한다. 이 명령 자체는 외부 모델을 호출하지 않는다.

```text
palim d2k draft DATA_SHA --request-id PREPARATION_UUID --reason "D2I 오류 내용" --byte-range START END --json
palim d2k preparation PREPARATION_UUID --json
palim d2k authorize PREPARATION_UUID --authorization-id AUTH_UUID --confirm-manifest-sha256 MANIFEST_SHA --actor-ref ACTOR --json
palim d2k prepare AUTH_UUID --request-id EXECUTION_REQUEST_UUID --json
palim d2k request EXECUTION_UUID --phase generator --directory CALL_DIRECTORY --json
palim d2k stage EXECUTION_UUID --response GENERATOR_RESULT_JSON --json
palim d2k request EXECUTION_UUID --phase validator --directory CALL_DIRECTORY --json
palim d2k decide EXECUTION_UUID --response VALIDATOR_RESULT_JSON --json
```

원문의 명령, 모델의 `authorized` 필드, I2K의 `source_requests`는 사용자 확인을 대신하지 못한다. 로컬 CLI와 데이터베이스 권한은 신뢰 경계 안에 있고, 모델 worker는 그 권한을 갖지 않는다. 검토 manifest에는 정확한 D·원문 view·실패 이력·모델·자료 버전 및 중복 확인에 전달하는 기존 K 목록이 포함된다. 모델 호출 전 사용자 확인은 실제 전송할 내용으로 결속해야 한다.

같은 request ID는 같은 실행을 반환한다. 확인 하나에 동시 활성 실행을 둘 수 없고, 마지막 실행이 실패/미완료인 경우에만 `prepare --prior-execution-id ...`로 같은 범위의 재검토를 준비한다. 범위·모델·버전·허용된 K 목록이 달라지거나 이미 완료된 요청을 새로 실행하려면 새 manifest 확인이 필요하다. 재검토에서 앞선 결과와 실패 기록은 보존하며, 이전 응답을 원문 근거로 취급하지 않는다.

확인 이후 승인 목록 밖에 같은 의미의 K가 생성되면 해당 후보는 `d2k_catalog_confirmation_required`로 보류한다. 그 K를 재사용하려면 새 manifest를 확인해야 한다. 같은 실행의 독립 후보는 계속 반영할 수 있다.

## 원문 view와 근거

UTF-8 텍스트는 원문 byte 범위를 받는다. 정확한 원문 SHA·byte 크기, Unicode/byte/line 위치, 인용문과 hash를 기록한다. 문자 중간에서 잘린 byte 범위, 원문과 다른 문자열, 임의로 작성한 위치는 거부한다. `--byte-range` 생략은 텍스트 전체를 뜻한다. 비텍스트 binary는 자동으로 다른 parser에 전달하지 않는다.

PDF는 `tools/run_d2k_pdf.py`로 사용자가 선택한 물리 페이지를 이미지화한다. 원문 export는 `palim d2k export-source DATA_SHA NEW_FILE`로 할 수 있다. `draft --pdf-directory DIRECTORY`는 등록 원본 bytes에서 페이지를 다시 렌더링해 pixels까지 검증하고 그 이미지를 Artifact Store에 보존한다. 고정 PDFium 5.10.1/Pillow 12.3.0을 쓰는 선택 runtime은 `deploy/d2k-pdf/Dockerfile`이다. 기존 MinerU renderer 이미지 계층을 재사용하지만 파서나 VLM을 실행하지 않는다.

```text
python tools/run_d2k_pdf.py --help
palim d2k draft DATA_SHA --request-id PREPARATION_UUID --reason "D2I 오류 내용" --pdf-directory VERIFIED_PAGE_DIRECTORY --json
```

PDF view의 좌표는 원본 CropBox/MediaBox, 실제 pixels, 두 방향 affine 변환과 연결된다. 현재 고정 profile이 지원하지 않는 회전 페이지는 명시적으로 거부한다. 모델에게 전달되는 것은 선택 페이지 이미지이며 원본 PDF bytes가 전달되었다고 기록하지 않는다. PDF grounding은 실제 전달한 전체 선택 페이지 범위다. 이미지에서 정확한 문장을 인용했다거나 임의의 작은 bbox를 판정했다는 가짜 정밀도를 만들지 않는다.

## 반영·소비

`explicit-source-d2k-v1`의 엄격한 Generator/Validator schema를 쓴다. 모든 전달 view에 검토 결과가 있어야 하고 각 후보에 실제 D 인용이 있어야 한다. 원문에 명시된 내용·새 추론 없음·원문별 정체성·범위·중요성을 독립 Validator가 확인한다. 구조 검사는 semantic truth 판정이 아니다.

canonical D 근거는 `knowledge_data_groundings`에, 실제 승인·전달·판정은 Compiler Runtime에 보존한다. 각 support Record의 D 근거·K 효과·후속 outbox를 원자적으로 반영한다. 같은 의미 reuse는 기존 Revision에 support를 추가하며 기존 생성 origin을 바꾸지 않는다. 새로운 D2K-origin은 `is_inferred=false`, K2K-origin은 이후 D support가 추가되어도 `is_inferred=true`다.

I가 없는 D도 명시적으로 선택한 Wiki Data 범위에서 조회할 수 있다. `wiki retrieval-prepare --include-data-id DATA_SHA`와 Desktop 설정 `include_data_ids`는 허용된 추가 D를 지정한다. 전체 DB의 D를 자동 공개하지 않는다. D 근거를 I citation으로 꾸미지 않고, K2K의 전이 D 근거도 결론의 직접 D 근거와 구분한다. D2K 완료는 D2I 오류 해결이나 누락 없는 I 확보를 뜻하지 않는다.
