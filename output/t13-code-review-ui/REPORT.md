# 실제 코드 Wiki / Knowledge / 검토 / 질의 UI 확인

Electron UI 0.2.0과 준비된 코드 Wiki의 실제 읽기 연결을 확인했다. 소스 앱과 Windows package에서 동일한 코드 원문·정확한 KRevision·전제·검토 이력을 열었으며, 최종 package에서는 검증된 v2 답변까지 확인했다. 이번 UI 검사에서 provider 호출, canonical DB 쓰기, Python 변경, 기본 연결 파일 변경은 하지 않았다.

## 최종 확인 결과

- [소스 앱의 현재 자료 버전 K 확인](code-source-current-020/result.json): pass, renderer error 0.
- [패키지의 현재 자료 버전 K 확인](code-packaged-current-020/result.json): pass, renderer error 0.
- [최종 패키지의 저장 질의 확인](code-packaged-query-020-final/result.json): pass, renderer error 0.
- 정확한 현재 자료 버전 추론 KRevision: `01a09a81-9c28-79e5-9878-92218e97230b`.
- 확인한 전제 Revision: `01a099f8-9c11-7bc0-b113-c8b6ed0d0514`; 답변에 보존된 나머지 전제 refs도 실제 DOM과 대조했다.
- 저장된 query: `01a09a86-bb46-7f91-944f-e44d734f3d55`; `accepted_system_inference` 표시, exact K, frozen assumptions/limitations와 실제 원문 인용을 확인했다.
- 과거 자료 버전 근거의 추론 KRevision `01a09a08-49f7-7b87-aab3-66bd8cccaf41`도 [앞선 최종 코드-label package run](code-packaged-020-final/result.json)에서 확인했다.
- 과거 I2K 실행 `01a09a69-26ac-73be-9326-75771045ce6f`의 당시 미해결 I 21개를 실제 이유와 함께 표시했다. 이는 그 실행에 보존된 상태이며 이후 검토의 현재 미해결 총수를 뜻하지 않는다. UI도 **이 실행 당시**를 표시한다.

## 직접 확인한 화면

- [코드 Wiki](code-packaged-query-020-final/01-code-wiki.png): 코드 label과 코드용 `구현과 동작` 절 제목.
- [보존된 native Information](code-packaged-query-020-final/02-native-code-source.png): 파일명·파일 줄·byte 범위·상위 정의·구조 해석과 literal source text. 최초 인용의 `EXPERIMENT.md`는 native profile이 보존한 비Python member이며 `not_python` 표기를 유지한다.
- [현재 자료 버전 추론 K](code-packaged-query-020-final/03-inferred-knowledge.png): 실제 origin, exact IDs, 가정·한계·정확한 전제.
- [과거 실행의 검토 이유](code-packaged-query-020-final/05-unresolved-review.png).
- [검증된 저장 답변](code-packaged-query-020-final/06-accepted-inference-query.png): 원문 기반 claim과 승인된 K2K 추론 claim을 구분.
- [답변의 실제 원문 인용](code-packaged-query-020-final/07-query-retained-source.png).

이미지 도구로 코드 Wiki, native I, 추론 K, 검토, 저장 답변과 원문 패널 PNG를 직접 확인했다. 표시가 읽기 가능하고 코드 텍스트가 HTML로 실행되지 않으며, 원문·생성 기원·전제와 실제 실행 성공을 혼동하는 UI가 없는지 대조했다.

## 보존한 실패와 제한

첫 run의 60초 timeout은 기본 sandbox에서 Docker Desktop named pipe/config 접근이 거부되어 발생했다. 원문·모델·DB 오류로 분류하지 않았다. 승인된 동일 읽기 실행은 성공했다. [실패 결과](code-source-020/result.json)는 보존했다.

추가 질의 테스트의 첫 두 실패는 테스트의 범위/필드 가정이었다. 다른 claim의 실제 direct I 인용을 inference-only claim의 인용으로 세는 selector를 고쳤고, source execution ID가 없는 frozen transitive row에 가짜 링크를 만들지 않았다. 해당 row의 K→I→D는 그대로 표시하며, 실제 direct source citation과 exact K 화면의 backend-resolved 근거 링크를 사용한다. [첫 실패](code-packaged-query-020/result.json), [두 번째 실패](code-packaged-query-020-corrected/result.json)를 보존했다.

최종 Node tests는 source와 ASAR renderer에서 각각 18/18 pass이며 application/PDF.js 파일 10개의 ASAR bytes가 source와 일치한다. [패키지 검증](app/REPORT.md), [최종 hash/크기](app/package-inspection.json). 패키지는 하나의 새 디렉터리만 유지하고 기존 t09 패키지를 보존했다.
