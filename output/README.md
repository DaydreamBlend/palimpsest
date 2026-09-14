# 실행 산출물 안내

현재 UI와 정리 결과는 [t23-ui-realm](t23-ui-realm/REPORT.md)에 있다. 실행은 workspace의 [Palimpsest.cmd](../Palimpsest.cmd)를 사용한다. 새 UI는 하나의 설치된 Electron 엔진을 공유하므로 이후 버전마다 전체 실행 파일을 복제하지 않는다.

이 폴더에는 단순 로그뿐 아니라 **로컬 모델, PDF 원본 사본, 파싱 text/span/image, 모델 입력·응답·판정과 과거 검증 기록**도 있다. 폴더 이름이 output이라고 해서 전체가 삭제 가능한 캐시는 아니다. 특히 models/evidence/raw/source/corpus, source/Record/receipt와 연결된 파일은 별도 보존 검토 대상이다.

2026-09-14 사용자의 정리 승인으로 이전 Electron 실행 패키지, 중간 UI 패키지와 종료된 테스트 프로필·다운로드 캐시를 제거했다. [정확한 삭제 내역](t23-ui-realm/electron-cleanup-result.json), [다운로드 캐시 내역](t23-ui-realm/download-cache-result.json).

과거 빌드·테스트 로그와 반복 검증 JSON290개는 [하나의 압축 기록](t23-ui-realm/build-test-logs.zip)으로 옮기고 개별 파일을 제거했다. ZIP 내부는 원래 workspace 상대 경로와 정확한 bytes를 유지한다. [경로·SHA-256 목록](t23-ui-realm/output-cleanup-plan.json), [삭제 확인](t23-ui-realm/output-cleanup-result.json). 과거 문서의 해당 로그/검증 파일 링크는 ZIP에서 필요한 파일을 복원한 뒤 읽을 수 있다. 모델 응답·원문·I/K 근거를 단순 실행 로그로 분류하여 삭제하지 않았다.
