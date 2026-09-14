# 이번 패키지 변경 내역

기준: 앞서 전달한 CLI/MinerU 미지정 개발 패키지. 적용: 2026-09-09 U01–U03.

## 변경한 것

CLI-first/GUI-last를 root/nested AGENTS, roadmap, 모든 task, Codex prompts와 progress에 반영했다. CLI는 T02부터 단계별로 구현한다. T11은 CLI 운영 완성, T12는 CLI release, T13은 deferred GUI다.

PDF D2I parser를 MinerU로 지정하고 parser 실행/structured output/원문 grounding/실패/부분처리/no-silent-fallback/local 전송 경계를 명세화했다. 버전/backend/hardware는 실제 inventory 뒤 고정한다.

현재 canonical과 구현 문서의 세 구성요소명 및 namespace/path field를 새 영어 이름으로 바꿨다. 과거 원본·검토·인용은 보존하고 current/baseline map을 별도로 검사한다.

U01–U03 register, CLI/MinerU 명세, AT82–AT105와 S09–S12 합성 fixture를 추가했다. 기존 P01–P12와 26 findings, 원본 45 invariant 추적은 유지했다.

## 변경하지 않은 것

실제 app 코드·운영 DB·사용자 원문은 변경하지 않았다. MinerU/모델을 설치하거나 PDF를 파싱하지 않았다. 실제 CLI commands는 아직 구현되지 않았다. 다른 P 계약을 임의로 승인하지 않았다. propagation hard cap을 다시 넣지 않았다. D-I-K-W-P-B와 immutable provenance 원칙을 변경하지 않았다.
