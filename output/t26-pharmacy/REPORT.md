# 약물치료학 PDF 등록

2026-09-15 사용자 요청: `test_input/약물치료학.pdf`를 Realm `약사`로 등록하고 후속 처리 시작.

- 원본: 39,793,408 bytes, 37페이지, 암호화 없음.
- D SHA-256: `221b80112be654770e4a2e432f70625fb10e7a05afe8a4bf860aaf32caac9bfd`.
- Realm: `01a0a37b-55ae-7257-b058-677c0a88c830`, 등록 membership receipt 완료.
- Store: `01a0a37b-55a6-7208-9285-8529a9b1d410`.
- 새 Compose project `palimpsest`: PG18.6/pgvector0.8.6, source schema0023, 별도 `palimpsest_realms` catalog. 과거 삭제 DB를 복원한 것이 아니다.
- D2I: MinerU3.4.5 Hybrid Pro high, image200, script grouped I, 외부 application LLM 호출 없음.
- 최초 컴파일 연결 실패는 명시적 Realm DSN 파일로 해결. 첫 parser 실행은 이전 GPU UUID가 없어 0페이지 실패. 실패 기록은 `d2i/`에 보존.
- 현재 GPU를 지정한 실행: `01a0a37e-84c4-7de3-8a02-0902ab20a89f`, 결과 위치 `d2i-current-gpu/`. 2026-09-15 14:58 KST 확인에서 worker_failure로 종료. 마지막 예측 로그는 45/76(29:18)이며 parser 컨테이너가 없다. worker의 parser command timeout=1900과 finally의 강제 종료가 원인으로 판단된다. parser status의 running은 종료 시 갱신되지 않은 값이며 실제 실행 상태가 아니다. 완료된 I는 없고 추출 충실성 미검증. 자동 재파싱은 하지 않았다.
- 사용자가 제한 수정·실패 D2I 재실행을 승인했다. parser timeout을 None으로 변경하고 취소 시 해당 컨테이너 정리는 유지했다. 같은 execution의 attempt 2는 37/37페이지를 처리해 2026-09-15 16:40 KST `completed`가 됐다. 과거 failed 이벤트는 보존한다.
- D2I 결과는 accepted I 2개다: 원문 본문 203,496자/38 groundings와 page furniture 285자/37 groundings. I2K/N2E/K2K는 아직 미실행이며 로컬 GLM 후속 자동화가 ACTIVE다.
- 후속 개선: 본문 전체가 단일 I인 것은 너무 장문이다. 이 완료 실행은 재파싱하지 않고 현재 I2K 실험에만 사용하며, 다음 PDF D2I profile은 페이지 provenance와 전량 coverage를 보존한 채 장·절·주제 경계로 결정론적 분할한다.

등록 요청과 결과는 같은 디렉터리의 JSON에 보존. `compose.realm.yaml`과 `PALIMPSEST_APP_IMAGE=palimpsest-ui:0.23.0`을 함께 사용한다. 원본 PDF는 Git에서 제외한다.
2026-09-15 provider change: I2K/N2E/K2K Generator and Validator calls use local `glm-5.3-flash-nvidia-nvfp4` at `http://172.30.1.11:8888/v1` with context `700160`; model-list, strict JSON Schema, real 200 DPI PDF page-image, and provider-code live smoke checks passed.
