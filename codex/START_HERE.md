# Codex 시작 안내 — CLI-first / MinerU

## 1. 기존 저장소 보호

신규 프로젝트면 이 폴더를 작업 루트로 사용할 수 있다. 기존 프로젝트면 별도 위치에 압축을 풀고 AGENTS/README/PLANS/docs/task 파일 충돌을 확인해 병합한다. 실제 code나 운영 DB가 변경된 패키지가 아니다. 기존 GUI를 삭제하거나 physical storage/schema를 즉시 rename하지 않는다.

## 2. 이번에 확정된 세 요청

[USER_OVERRIDES](../docs/decisions/USER_OVERRIDES.md)를 먼저 읽는다. CLI를 T02부터 우선 구현하고 GUI는 T13 마지막으로 미룬다. PDF parser는 MinerU다. 세 모듈은 Artifact Store / Canonical Store / Compiler Runtime을 사용한다.

이미 Codex 작업을 진행 중이면 [PROMPTS](PROMPTS.md)의 ‘기존 작업 중인 저장소에 이번 변경만 적용’을 사용한다. 아직 시작하지 않았다면 같은 파일의 ‘T00만’을 사용한다. 새로운 변경을 적용한다고 이미 완료된 task를 이유 없이 재작성하지 않는다.

## 3. 읽을 파일

`AGENTS.md`는 핵심 제약과 문서 경로를 제공한다. 모든 Markdown이 자동으로 읽힌다고 가정하지 않는다. task의 read_paths를 명시적으로 읽고 관련 source/contract만 확대한다. [INDEX](../docs/INDEX.md)가 active canonical과 archived baseline을 구분한다.

## 4. T00 → T01 → CLI 기능 단위

T00에서 실제 code/toolchain/CLI/MinerU 환경을 조사한다. T01에서 P01–P12의 나머지 계약과 MinerU version/backend/output profile을 고정한다. U01–U03은 이미 적용되어 있으므로 다시 CLI 우선순위나 PDF parser 제품을 질문하지 않는다.

T02는 CLI skeleton와 Data, T03은 MinerU/D2I/I, 이후 task는 K/propagation/query/decision/publication을 CLI로 확장한다. T11은 human review/운영 CLI를 완성하고 T12에서 headless release를 검증한다. T13 GUI는 deferred이며 T12 후에도 사용자의 착수 지시가 필요하다.

## 5. 완료 보고

변경 파일, 실행 명령과 결과, AT IDs, 미실행 이유와 blockers를 보고한다. 문서 검사/합성 fixture/실제 MinerU/실제 DB/e2e/live model 평가를 구분한다. U03 naming 선택을 live DB rename 권한으로 해석하지 않는다. parser 선택을 hosted API 전송 승인으로 해석하지 않는다.

## 관련 문서

[CLI 계약](../docs/interfaces/CLI_CONTRACT.md), [MinerU adapter](../docs/interfaces/MINERU_ADAPTER.md), [현재 roadmap](../docs/implementation/ROADMAP.md), [기존 Codex 공식 참고 자료](REFERENCES.md)를 참고한다.
