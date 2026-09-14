# 스크립트 그룹 I 저장

2026-09-11 [사용자 승인](../decisions/GROUPED_INFORMATION_STORAGE.md)에 따라 새 D2I는 스크립트로 묶은 단위를 canonical I로 저장한다. 기존의 블록별 I와 읽기 projection은 과거 이력으로 유지한다. [실행 계획](../../progress/T03_grouped_information_execplan.md), [실물 저장·검증 결과](../../output/t03-grouped-information/REPORT.md). Compose 기본 앱은 검증한 `palimpsest-grouped-i:0.2.0`이다.

## 저장 형태

기존 heading/읽기 순서 규칙을 재사용해 절의 원문을 `\n\n`으로 연결한다. 확실한 Abstract/Introduction 등은 절 단위로 묶고, 확인되지 않은 경계나 역할은 원문 그대로 미분류 그룹에 남긴다. 본문의 Figure 참조만으로 이미지·caption의 소속을 새로 확정하지 않는다. 머리말·꼬리말·페이지 번호는 문서 전체의 별도 I 하나에 모아 보존한다. 그룹 수를 특정 숫자로 제한하거나 원문을 요약하지 않는다.

일반 그룹은 기존 `kind=text`, `unit_type=text`, `semantic_type=null`을 사용한다. 이 `text`는 이미지가 없다는 뜻이 아니다. 본문과 함께 있는 모든 이미지·표 crop은 해당 I의 `source_artifacts`와 I2K의 `media`에 들어간다. 임의의 이미지 하나를 primary로 선택하지 않는다. 기존 `required_figures` inventory가 있는 경우에는 검증된 Figure I를 별도로 유지해 primary/member/caption coverage 규약을 보존한다.

| 항목 | 보존 위치 |
|---|---|
| 묶인 원문 | I `content`, 삽입 구분자를 제외한 원문은 그대로 |
| 개별 블록 내용·페이지·좌표·leaf/raw 참조 | I `payload.source_blocks` 및 block별 grounding |
| 그룹 content에서 각 원문을 인용할 문자 범위 | `payload.source_assembly.content_segments` |
| 이미지 원본 bytes/hash | Derived Artifact Store, I `source_artifacts` |
| 선택한 조립 알고리즘 | frozen profile의 `transformation.algorithm=source-groups-v1` |
| 파서 원본·전체 원본 PDF·페이지 raster | 기존 Artifact Store/evidence와 exact SHA |

새로 생성되는 canonical I, D2IRecord와 outbox는 그룹 수만큼이다. 세부 블록 수만큼의 별도 I 행을 중복 생성하지 않는다. grounding은 세부 근거를 나타내므로 block별로 남는다. 기존 `source-information-v1` SQL/schema가 이를 지원하여 migration은 추가하지 않았다.

문자 범위는 Unicode codepoint의 반열림 구간이다. 일반 그룹에서는 해당 범위의 `content`가 원문 block text와 정확히 같다. 과거 required Figure의 caption-only 내용은 기존 규칙을 유지한다. synthetic primary와 caption 외 panel처럼 I `content`에 전사되지 않은 블록은 `char_start/end=null`로 구분하고 원문 블록을 보존한다.

## 새 실행과 기존 실행의 재조립

`tools/run_d2i.py`의 새 기본값은 `--information-layout groups`다. 기존 parser/model 선택·등록 도구·CLI-first 정책은 유지하며 명시한 `--information-layout blocks`는 과거 `source-units-v1`을 사용한다. 실패 시 다른 조립 방식으로 자동 전환하지 않는다. 이미 생성된 작업의 재시도는 frozen profile을 따른다.

이미 완료된 source 실행의 parser 결과를 재사용하려면 앱 컨테이너에서 다음을 실행한다.

```text
palim compile regroup --execution-id <completed-source-execution-UUIDv7> --json
palim information prepare-input --execution-id <returned-grouped-execution-UUIDv7> --json
palim information pages --execution-id <returned-grouped-execution-UUIDv7> --json
```

`regroup`은 등록 Data와 원래 source 실행의 artifact를 검증하고 새 grouped profile/execution을 만든다. 원래 execution ID, profile SHA와 parse manifest SHA를 새 profile·조립 manifest에 남긴다. 원래 parser profile/receipt/raw bytes와 source bundle을 그대로 참조하므로 새 OCR 실행으로 기록하지 않는다. 새 조립 구현의 코드 hash는 따로 기록한다. 같은 source/조립 profile의 재시도나 동시 요청은 동일한 grouped 실행·I ID를 반환한다.

기존 I의 UUID·내용·hash를 수정하거나 삭제하지 않는다. 이미 grouped 완료 실행을 입력하면 그 실행을 재사용한다. 이전 I를 지우는 migration이나 live DB 재작성은 이 명령에 포함하지 않는다. 검증 실패 시 atomic canonical 반영을 하지 않고 기존 Runtime 복구·재시도 경로를 따른다.

## I2K와 검증 범위

T04 `prepare-input`은 해당 실행의 frozen algorithm을 사용해 그룹 내용/FP/source blocks/문자 범위/이미지 descriptor를 다시 대조한다. 기존 블록별 I에도 과거 algorithm을 적용한다. 여러 페이지에 걸친 그룹과 모든 media를 유지하며 처리 대상과 참고 context를 구분한다. 저장 그룹보다 작은 범위를 조회해도 현재 I2K 준비는 해당 I 전체를 반환한다.

I2K에는 I의 텍스트·이미지·정확한 provenance를 먼저 제공하는 정책을 유지한다. 필요 시 동일 Data의 등록 원본 PDF를 준비하며, 원본 PDF나 전체 페이지 raster를 자동 첨부하지 않는다. source grouping의 결정론은 고정된 parser 결과에 대한 조립 재현성이며 OCR 충실성·의미 정확성의 보증이 아니다. 실제 모델 요청 판단·전송·K 생성은 여전히 후속 T04 작업이다.
