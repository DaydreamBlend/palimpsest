# T03 후속 — Qwen Q4 기본값 선택

2026-09-10 사용자 “그럼 Q4를 쓰도록 하자”에 따라 검증된 Qwen3.5-4B Q4_0를 제목 계층 보조 실험의 기본 모델로 선택한다. Thinking 2048, 전체 출력4096, v2/temperature0/seed42를 유지한다. USER_OVERRIDES, INDEX, DECISION_REGISTER, T03, PLANS, CODE_REVIEW 및 이전 두 Qwen 실험을 확인했다. Ponytail의 기존 도구 재사용 원칙을 적용한다. 새 원문 파싱·모델 평가·배포·canonical I/DB 변경은 이번 선택에 필요하지 않다.

1. [x] 기존 도구의 model/budget 기본값을 변경하고 명시적 override·no-thinking 경로를 보존한다.
2. [x] 현재 모델 profile과 사용자 승인 근거를 작성하고 INDEX/Decision register/STATUS에서 연결한다. 과거 산출물·실행 코드·보고는 보존한다.
3. [x] 기존 harness check에 기본값·override의 최소 검사를 추가해 실행하고, Q4 파일 hash와 bundle integrity를 대조한다.

root는 도구/문서 소유자이며 독립 검토자는 호출자와 역사 재현 위험을 읽기 전용으로 확인한다. 승인 범위는 optional heading projection의 모델 선택이다. U11 source D2I LLM0와 이후 I2K 모델 결정 범위를 유지한다. 기존 frozen harness는 그대로 보존하며 원복은 현재 기본값만 되돌리는 방식으로 가능하다. 새 task나 global schema 결정을 만들지 않는다.

완료. CLI parse 단계에서 기본 model=qwen35-4b-headings, thinking=true이면 미지정 예산2048로 확정한다. 명시0/512/다른model/--no-thinking 및 새 `--reasoning-budget none`의 무제한 재현 경로를 검사했다. 확정값은 기존 run 함수의 request와 record가 함께 사용한다. 실행 원문·prompt/schema·과거 frozen harness는 변경하지 않았다.

`python -B tools/run_title_experiment.py check` exit0, `run --help` exit0, `python -B tools/validate_bundle.py` exit0/오류0(Markdown127개/상대링크872개). Q4 파일2,583,221,408bytes/SHA`298fcb5fe7a77ccc79745ae24751560c5ac56874caff4bb39b1f2055bd72b8bb` 재검증 및 과거 Q4/BF16 frozen harness SHA불변 확인. 독립 읽기 검토에서 앱 호출자 없음·역사 코드 보존 경로를 확인했다.

변경 파일은 현재 도구, 이 계획, HEADING_MODEL_PROFILE, INDEX, DECISION_REGISTER, STATUS의6개다. 모델 재추론·앱/PG테스트·Docker기동/삭제는 실행하지 않았다. 새 모델선택에 추가 승인 장애는 없고, 전체T03 AT gate나I2K 작업을 완료 처리하지 않는다.
