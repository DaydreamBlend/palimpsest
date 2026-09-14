# T03 후속 — Qwen3.5-4B 제목 계층 비교

## 승인·목표·경계

2026-09-09 사용자: “Qwen 3.5 4B로 실험해줘”. 기존 Gemma E4B 실험과 같은 Test_Paper/MCM/Penteado의 고정 MinerU 입력, v2 prompt, JSON schema, 독립 기대치를 사용해 로컬 Qwen3.5-4B의 계층·부모·비제목 제외·반복 일치·지연 시간을 비교한다. 다운로드와 로컬 추론은 승인 범위에 포함된다. 원문 외부 전송, canonical I/DB 변경, D2I 기본 LLM 활성화, I2K 완료는 이번 범위가 아니다.

AGENTS, USER_OVERRIDES(U01–U11), INDEX, DECISION_REGISTER, PLANS, T03, CODE_REVIEW와 기존 T03_e2b_execplan/harness/profile을 읽었다. P01–P12 전체 승인이나 새 schema 결정은 없다. HF CLI/로컬 평가/ponytail 스킬을 적용하며 기존 stdlib harness와 llama.cpp Docker 이미지를 재사용한다.

## 실행·복구 계획

1. [x] 기존 입력·기대치·실행 도구와 Docker/GPU 상태 확인.
2. [x] 공개 Qwen GGUF artifact의 repo/revision/file/SHA-256/양자화와 runtime 지원을 고정하고 workspace 안에 다운로드.
3. [x] 내부 전용 임시 서버에서 smoke. 같은 v2/temperature0/seed42/ctx8192/parallel1로 non-thinking과 thinking을 문서별 3회 비교. 출력 미완료는 실패로 보존하고 필요시 별도 reasoning budget 조건으로 재시험.
4. [x] 기존 E4B와 request/input 동등성 및 계층·부모·비제목 제외 점수를 검증. GGUF 양자화 차이와 개발용 3문서라는 한계를 명시.
5. [x] 원시 request/result, runtime profile, 결과 보고를 보존. 필요한 도구 변경만 검사하고 bundle validator 실행.
6. [x] 이번 실험의 ID/label이 확인된 컨테이너·network만 제거. 기존 container/image/volume 집합과 원본 PDF hash 보존 확인.

root는 runtime/download/run/report 소유자다. e2b_runtime_review는 공식 모델·런타임 조사, 추가 독립 검토자는 결과 무결성/비교 검토만 수행한다. 앱/DB/schema 코드 소유권 변경 없음. 재시도는 새 condition/output 경로를 사용해 기존 실패를 덮어쓰지 않는다.

## 실행 기록

- 일반 sandbox의 Docker 조회는 named pipe 권한 오류. 승인 실행 경로에서 기존 container 7개와 llama.cpp b10380 CUDA 이미지, RTX5080/4060Ti 각16GB를 확인했다.
- 재사용 이미지: llama.cpp `sha256:a50b12bb92de0253d2737824ca1887f410e07b4dd3e3028f74a5a0a67c789e4b`; HTTP client `sha256:594c68dcf8b7ebab5461f45a041e78dce407b8c44368aabc645978c268ceb528`; MinerU/HF CLI `sha256:fdab78016483e1dbf0f416c9f74941a1242a91dae58fa2cc9617488ceb338854`.
- 기존 harness에 모델별칭과 thinking 설정이 이미 있어 우선 코드 변경 없이 실행한다. 기존 E4B 기본값은 유지한다.
- Unsloth revision `e87f176479d0855a907a41277aca2f8ee7a09523`, Q4_0 파일 2,583,221,408 bytes와 SHA256 `298fcb5fe7a77ccc79745ae24751560c5ac56874caff4bb39b1f2055bd72b8bb`를 다운로드·대조했다. 공개 모델만 수신했고 mmproj는 제외했다. 기존 이미지의 HF CLI에서 `--version` 인자가 지원되지 않았지만 실제 `hf download`는 exit0이었다.
- 서버는 기존 b10380에서 12.779초에 정상 로딩. 첫 non-thinking Test_Paper 3회는 약3초/JSON 출력완료지만 `front_matter`에 level2를 부여해 기존 role-level 검사에서 실패했다. 실패를 정답으로 정정하지 않았다. 초기 runner는 이 실패 후 멈추도록 되어 있다.
- Thinking Test_Paper 첫 실행은 4096토큰을 소진해 최종 응답 미완료. 기존 조건18회를 모두 보존하고, 별도 `think2048` 조건9회를 추가해 최종 JSON을 위한 출력 여유를 확보한다. 이는 기존12B에서 사용한 같은 per-request budget이다. 온도0은 공통 비교 설정이며 Qwen 공식 권장 sampling 평가로 주장하지 않는다.

## 완료·미실행 구분

전체27회 실행과 scoring/equivalence 검사를 완료했다. Thinking 예산2048은9/9회 유효/각문서3회동일이며 level77/77, parent74/74, MCM panel제외3/3이다. Test_Paper role27/27도 일치한다. 공통non-thinking6/9회유효, 공통thinking0/9회유효이며 실패3회는role-level,9회는최종출력미완료다. 점수와 비교표는 [보고서](T03_qwen35_experiment.md)에 기록한다.

`score --root output/t03-qwen35 --output output/t03-qwen35/scores.json` 및 `output/t03-qwen35/runtime/verify_comparison.py` exit0. 요청은 모델/thinking/명시적예산 외 차이가 없고 입력·기대치bytes와 각조건3회기록을 확인했다. root는 모델·서버·데이터 해시를 보존하고 임시컨테이너5개/network1개를 정리했다. 기존container7개와image/volume집합은 불변이며 모델파일은 유지한다.

이 작업은 live local heading evaluation이며 T03 전체 AT gate, PostgreSQL 통합, I2K 의미 추출의 검증을 대신하지 않는다. 기존 문서 3개는 프롬프트 개발에 사용된 자료이므로 새로운 holdout 성능으로 보고하지 않는다. 코드/기대치/평가threshold 변경 없이 관찰된 성능이며 신규 승인 대기 결정은 없다.

- 독립 재계산: raw27개를 별도 JSON 중복키 검사/parent 계산으로 대조해 불일치0. 예산2048은 단일root·level jump 없음9/9, Test role27/27, 실제 MCM non_outline3/3을 확인했다. 결과는 `output/t03-qwen35/runtime/independent-result-review.json`에 보존한다.
- 최종 원본PDF3개의 SHA와 `tools/run_title_experiment.py`/실행복사본 SHA 불변 확인. `python -B tools/run_title_experiment.py check` exit0. 앱 코드/공유harness 변경0이며 산출물 내부 실행·검증 스크립트와 보고만 추가했다.
- `python -B tools/validate_bundle.py` exit0/문서오류0. `runtime/bundle-validation.log` 보존. 문서120개·source2331줄/13parts·current2267줄/13parts·승인override11개가 기존 계약대로 검사됐다. 원시결과와초기comparison manifest의최종무결성을검사한 [runtime profile](../output/t03-qwen35/runtime-profile.json)에실행·정리·해시를집계한다.
