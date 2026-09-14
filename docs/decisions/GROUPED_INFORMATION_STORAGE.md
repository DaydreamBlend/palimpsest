# 스크립트로 묶은 Information의 영속 저장

2026-09-11 사용자 후속 승인. 사용자 요청 원문:

> 수백개를 저장하지 말고, I를 스크립트 기반으로 묶어서 저장하는 게 나을 거 같아

새 D2I 실행은 스크립트로 묶은 원문 그룹을 canonical I로 저장한다. 파서의 작은 block마다 별도 I 행을 만드는 방식을 새 실행의 기본값으로 사용하지 않는다. 이 지시는 [직전 I 우선 정책](I2K_I_FIRST_SOURCE_ON_DEMAND.md)의 “I의 영속 단위를 새로 바꾸는 지시가 아니다” 및 이전의 조회 그룹만 허용한 문구보다 **새 I 저장 단위의 범위에서만** 우선한다. 기존 I의 삭제·재작성, parser 교체, P 제안 전체 승인으로 확장하지 않는다.

## 새 저장 단위

파서가 제공한 페이지별 읽기 순서와 명시적 제목을 이용해 본문을 절 단위로 묶는다. 기존 스크립트의 절 경계 규칙을 재사용하며, 경계가 확인된 Abstract와 Introduction은 각각 한 그룹으로 유지하고 Results 등은 명시적 소제목을 사용한다. 제목이나 역할을 확인할 수 없는 원문도 `Unclassified source content` 그룹에 보존한다. 그룹명과 역할 hint는 원문 구조에 관한 표시이며 의미 해석이나 K 판정이 아니다.

본문 흐름을 방해하는 머리말·꼬리말·페이지 번호는 문서 전체의 `Document page furniture` 한 그룹으로 모아 저장한다. 내용은 제거하지 않는다. 저장할 I 개수나 글자 수를 미리 정해 원문을 잘라내지 않으며, 긴 그룹의 모델 입력 분할은 I2K 입력 준비에서 처리한다.

`source-information-v1`의 기존 schema와 `unit_type`을 유지하고, 새 조립 알고리즘을 `source-groups-v1`로 기록한다. 본문 그룹은 텍스트·표·수식·이미지 block을 함께 포함할 수 있다. 이런 혼합 그룹은 현재 schema에서 `kind=text`, `unit_type=text`, `image_block_id=null`로 저장하되 모든 이미지 파일과 block 연결은 `source_artifacts` 및 I2K `media`에 보존한다. **`kind=text`라는 이유로 해당 I의 이미지를 생략하지 않는다.** 새로운 의미 유형이나 별도 이미지 요약을 만들지 않는다.

이미 명시적으로 검증된 `required_figures`가 있으면 기존 Figure unit의 primary·패널·캡션 구성과 content를 그대로 별도 유지한다. 그렇지 않은 이미지·표·수식은 해당 원문 그룹 안에 보존한다. 인접한 caption이라는 이유로 Figure 귀속을 확정하거나 Figure 개수를 맞추기 위해 관계를 생성하지 않는다.

## 원문과 provenance

모든 원문 block과 검증된 synthetic Figure primary를 정확히 한 I에 배정한다. 새 그룹의 원문 텍스트는 파서 읽기 순서대로 `\n\n` 구분자를 넣어 결합하고, block 내부의 Unicode·공백·줄바꿈·기호는 그대로 유지한다. 기존 required Figure의 caption 결합은 역사적 `source-units-v1` 규약을 유지한다.

각 I는 포함된 block 원문을 payload에 보존하며, Data·페이지·bbox·raw locator·anchor hash·이미지 hash 및 기존 leaf provenance를 그대로 연결한다. 조립한 content의 문자 범위와 각 원문 block의 문자 범위를 함께 기록하여 I2K와 K의 인용이 큰 I 내부의 정확한 근거를 가리킬 수 있게 한다. synthetic primary의 표시 문자열이나 content에 들어가지 않은 Figure panel 텍스트를 전사된 본문처럼 표시하지 않는다.

파서 raw와 canonical I payload/grounding에 세부 block을 보존하는 것은 계속 필요하다. 이 block들에 대해 별도 canonical I 행을 추가로 복제하지 않는다. I 행 수 감소를 raw·grounding·이미지 파일 삭제로 구현하지 않는다. 구조 검사에서는 동일 입력의 동일 조립 결과, 전체 block의 1회 배정, content 범위·원문 일치, Figure coverage와 이미지 보존을 확인한다. 이 검사는 OCR 충실성이나 의미적 진실의 승인이 아니다. 기존 discrepancy와 미해결 transcription 검토도 유지한다.

## 기존 실행과 새 실행

기존 I·UUID·fingerprint·Record·receipt·raw 및 parser profile의 bytes/hash를 삭제하거나 덮어쓰지 않는다. 새 I의 opaque ID는 UUIDv7을 유지하고 같은 Data의 content hash도 그대로 사용한다. 그룹 경계가 달라져 새 I snapshot이 생기는 것은 K의 의미 Revision을 만드는 사건이 아니다.

완료된 source 실행을 `palim compile regroup --execution-id <기존 실행 ID>`로 다시 묶을 때는 해당 실행의 검증된 parser 결과를 사용한다. 부모 실행 ID, 부모 profile hash와 parse manifest hash를 새 실행에 명시하고, 새 조립 profile과 조립 근거 manifest를 따로 기록한다. 이전 parser receipt를 새 조립 profile로 다시 쓴 것처럼 만들지 않으며 재파싱도 요구하지 않는다. 같은 재조립 요청의 재실행은 기존 실행·검증 규약에 따라 처리한다.

새 worker의 Information layout 기본값은 `groups`다. 기존 block 저장 방식은 `--information-layout blocks`로 명시적으로 선택하는 호환 경로로 남긴다. 새 그룹 경로가 실패했다고 기존 block 경로로 조용히 대체하지 않는다. 이 승인만으로 기존 운영 DB 전체를 변환하거나 모든 과거 I를 다시 생성하지 않는다.

## 유지되는 입력 정책과 구현 경계

선택된 image200 MinerU Hybrid high + Pro2605 1.2B와 parser 내부 OCR/layout VLM은 그대로 사용한다. 파싱 이후의 조립은 application LLM 호출 없이 결정적 스크립트로 수행한다. 동일 고정 parser 결과에 대한 재현성과 OCR 모델 전체의 결정론성을 구분한다.

I2K는 그룹 I의 content·모든 관련 media·정확한 provenance를 먼저 받는다. 등록 원본 PDF와 전체 페이지 raster를 처음부터 자동 첨부하지 않으며, 원문 확인이 필요하다고 판단한 경우 exact Data/I/source refs 및 hash에 연결된 등록 원본 PDF bytes를 제공한다. 요청 이유·실제 전달·사용·인용 기록은 [I 우선·원본 추가 조회 정책](I2K_I_FIRST_SOURCE_ON_DEMAND.md)을 따른다. 저장 단위 변경은 실제 I2K provider 호출·K 생성·Revision/CAS/commit의 완료를 뜻하지 않는다.

범위 밖 U/P 승인 상태, canonical snapshot/slices 및 과거 승인 원문은 그대로 유지한다. 구현·실행·검증 결과는 [그룹 I 저장 실행 계획](../../progress/T03_grouped_information_execplan.md)에서 관리하며, 이 승인 문서를 PostgreSQL 실물 저장이나 모델 평가의 통과 기록으로 사용하지 않는다.
