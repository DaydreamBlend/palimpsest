# MinerU 공식 근거

확인일: 2026-09-09. 아래는 PDF adapter 설계에 필요한 공개 upstream 문서다. 특정 버전의 실제 설치·모델 다운로드·PDF 실행 검증을 완료했다는 뜻이 아니다. 구현 시 설치할 버전의 문서와 `--help`로 다시 확인한다.

## M1 — 공식 CLI 도구

```text
https://opendatalab.github.io/MinerU/usage/cli_tools/
```

`mineru --version`/`--help`, local input/output 옵션, backend 선택, local API orchestration과 외부 backend URL 구분을 확인했다. GUI를 쓰지 않고 parsing adapter를 구성할 수 있는 근거다. 각 설정의 정확한 precedence와 command shape는 pin한 버전으로 검사한다.

## M2 — 공식 출력 형식

```text
https://opendatalab.github.io/MinerU/reference/output_files/
```

Markdown와 structured output의 역할, middle/content-list 구조, page/region 정보, backend별 schema 차이를 확인했다. 같은 bbox 명칭을 모든 출력에서 같은 좌표 단위로 해석하지 않는 adapter 검증의 근거다.

## M3 — 공식 Quick Start

```text
https://opendatalab.github.io/MinerU/quick_start/
```

설치 환경과 backend/runtime 선택을 확인할 공식 시작점이다. 실제 Palimpsest runtime 환경이 제공되지 않았으므로 이 패키지에서는 특정 OS/GPU/메모리 요구치를 확정하지 않았다.

## M4 — 공식 저장소

```text
https://github.com/opendatalab/MinerU
```

선택할 release/commit과 설치 metadata, code/model dependency 및 license를 추적할 출처다. 현행 main의 내용을 다른 과거 release에 자동 적용하지 않는다. 법률적 이용 허용 여부를 이 문서가 보증하지 않는다.
