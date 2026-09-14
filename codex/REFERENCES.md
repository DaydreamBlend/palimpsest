# Codex 운영 지침의 외부 근거

확인일: 2026-09-09. Palimpsest domain의 근거는 이 패키지의 source snapshot입니다. 아래 외부 자료는 Codex에 전달할 파일/작업 구조를 설계할 때만 참고했습니다. 보완 계약의 새로운 내용은 모델의 설계 제안이지 OpenAI가 Palimpsest를 검증했다는 뜻이 아닙니다.

## O1 · Custom instructions with AGENTS.md — OpenAI

```text
https://developers.openai.com/codex/agent-configuration/agents-md
```

AGENTS instruction discovery, root-to-working-directory 계층, 가까운 지침 우선, 기본 project_doc_max_bytes 32 KiB를 확인했습니다. 모든 Markdown을 AGENTS에 붙이지 않고 task별 경로로 읽도록 구성한 근거입니다. 일부 기존 docs 경로는 OpenAI의 learn.chatgpt.com 문서로 redirect될 수 있습니다.

## O2 · Best practices — OpenAI

```text
https://developers.openai.com/codex/learn/best-practices
```

task에 goal/context/constraints/done when을 명시하고, AGENTS를 짧고 실용적으로 유지하며 검증과 diff review를 함께 수행하는 지침을 참고했습니다. 이 패키지의 모든 task는 이 네 가지를 포함합니다.

## O3 · Using PLANS.md for multi-hour problem solving — OpenAI Cookbook

```text
https://developers.openai.com/cookbook/articles/codex_exec_plans
```

긴 작업의 계획과 진행/발견/결정을 파일로 보존하는 패턴을 참고했습니다. PLANS.md와 ExecPlan은 이 프로젝트가 명시적으로 채택한 문서 workflow이며 단순 파일명만으로 임의의 작업이 자동 실행되지는 않습니다.

## O4 · Worktrees — OpenAI

```text
https://developers.openai.com/codex/app/worktrees/
```

독립 checkout에서 병렬 작업을 진행하는 방식을 참고했습니다. DB/artifact storage까지 자동으로 격리된다고 가정하지 않는 것은 Palimpsest의 별도 운영 권고입니다.

## O5 · Local environments — OpenAI

```text
https://developers.openai.com/codex/app/local-environments/
```

프로젝트별 실행 환경과 setup/actions를 관리하는 문서를 참고했습니다. 이 패키지는 실제 repo 명령을 아직 모르므로 추측한 `.codex` 설정이나 dependency 설치 명령을 생성하지 않았습니다.
