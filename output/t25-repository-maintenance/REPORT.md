# Git 도입과 현재 문서 분리 — 2026-09-15

사용자가 지적한 두 문제를 실제 확인했다. Git이 없었고, 시작 문서에 상충하는 과거 구현/승인 기록이 계속 누적돼 있었다. 이는 변경 추적과 필요한 문서 선택 비용을 늘리지만, 전체 토큰 비용 중 정확한 비율을 측정한 결과는 아니다.

## 적용

- 로컬 `main`에 초기 기준점 `c10dc88`을 생성했다. 소스·테스트·문서·요약 보고서631파일, working bytes8,923,858을 보존했다. 이전 개발 commit을 꾸며내지 않았으며 원격 저장소/업로드는 없다.
- `.gitignore`는 원본 데이터·모델·실행 캐시·대형 산출물·자격 증명을 제외한다. `output/README.md`와 작업별 `REPORT.md`는 추적한다. `.gitattributes`의 `* -text`와 로컬 autocrlf 설정으로 역사적 원문/SQL bytes가 checkout에서 변환되지 않도록 했다. Git은 DB·Artifact Store의 별도 백업을 대체하지 않는다.
- `progress/STATUS.md`를 현재 상태의 단일 진입점으로 정리했다. README는 실행/진입 링크, INDEX는 작업별 계약 선택, AGENTS는 지속 규칙만 담는다. 폴더별 AGENTS와 PLANS에서도 이미 철회된 GUI-last/항상 전체 이력을 읽는 규칙을 제거했다. 기존 문구는 초기 커밋에서 정확히 조회할 수 있다.
- 문서 검사기는 dependency/runtime/generated output 디렉터리를 순회하지 않는다. source/canonical 문서와 hash 검사는 유지한다. vendor·산출물까지1,089개를 검사하던 범위를 프로젝트 문서224개로 줄였고, 남은 깨진 링크16개 중15개는 실제 T23 ZIP entry를 확인해 연결했다. 제거된 과거 exe 링크는 현재 런처로 수정했다. 로그나 원문을 재생성하지 않았다.

| 진입 문서 | 변경 전 bytes | 변경 후 bytes | 감소 |
|---|---:|---:|---:|
| AGENTS.md | 47,868 | 4,270 | 91.1% |
| README.md | 26,289 | 1,229 | 95.3% |
| progress/STATUS.md | 21,997 | 4,904 | 77.7% |
| docs/INDEX.md | 32,719 | 4,218 | 87.1% |
| 합계 | 128,873 | 14,621 | 88.7% |

이 수치는 문서 bytes이며 토큰/과금 감소율이 아니다. [OpenAI의 AGENTS.md 안내](https://learn.chatgpt.com/docs/agent-configuration/agents-md)는 작업 전 지시 파일 로딩과 기본 합계32KiB 한도를 설명한다. 기존47.9KB root 파일은 이 기본 한도보다 컸다. 이 세션의 실제 설정/잘림/캐시 과금은 측정하지 않았다. 이미 긴 대화에 들어온 기록은 파일 축소로 없어지지 않으므로 새 작업의 짧은 진입 경로에서 효과가 가장 명확하다. 실제 추론·도구 출력·반복 검증도 비용 요소이며 이번에 그 과금 내역까지 산출한 것은 아니다.

## 검증과 복원

`python tools/validate_bundle.py`는224개 문서·1,613개 로컬 링크와 원본/정식 snapshot hash를 검사해 통과했다. 관련 문서 검사10개가 통과했고 `git diff --check`도 통과했다. 앱 코드·UI·SQL·DB·모델·원문은 변경하지 않았으며 앱 전체/DB/LLM 검사를 수행한 것으로 표시하지 않는다. 대용량/자격 증명 경로와 알려진 실제 키 형태가 staging에 들어가지 않았음을 확인했다. 완전한 비밀정보 감사나 원격 백업의 완료를 뜻하지 않는다.

이전 시작 문서는 `git show c10dc88:AGENTS.md`, `git show c10dc88:README.md`, `git show c10dc88:progress/STATUS.md`로 조회한다. 이후 변경은 `git status --short`, `git diff`, `git log --oneline`로 확인한다. 사용자 변경을 먼저 검토하고 필요한 파일만 선택해 복원한다. 변경 확인에 전체 파일 hash 보고서를 새로 만드는 대신 Git diff를 사용하되, DB/원문 provenance hash는 기존 규약대로 유지한다.
