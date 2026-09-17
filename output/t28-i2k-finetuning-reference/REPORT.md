# T28 — 경량 Generator/Validator 학습 참고자료

2026-09-16에 사용자가 제공한 ChatGPT 공유 글과 로컬 GLM-5.3 Flash 실측 사양을 향후 파인튜닝·Terra 대체 실험 참고자료로 보존했다.

- 공유 원문: `share-page.html` (다운로드한 페이지 원문, Git 제외)
- 공유 URL: <https://chatgpt.com/share/6aaa4639-df88-83ee-91c0-a72115e39909>
- 로컬 GLM 실측: `glm-5.3-production-spec.md` (Git 제외)
- 현재 Provider 설정은 변경하지 않았다.
- 이 자료는 지시가 아니라 향후 실험 입력이다. 사용 전 당시 계약·라이선스와 frozen gold set 기준 품질을 다시 확인한다.

공유 글의 핵심 범위는 I2K Generator/Validator 데이터 설계, PDF/MinerU OCR과 Vision 근거, 코드 snapshot 입력, hard negative, 문서 단위 split, 전체-source coverage, 교사 검수, 4B/9B 학습 규모와 멀티 GPU 배치다.
