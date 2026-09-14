# 여러 입력 형식의 결정적 D2I 설계

상태: 설계 검토·문서화 COMPLETE, 새 HTML/코드 구현은 PLANNED, 2026-09-11. 사용자는 웹사이트 주소/PDF/Markdown/코드베이스 파일 등을 최대한 스크립트+MinerU로 비교적 결정론적이고 문맥이 있는 I로 만들고자 한다. 이번 작업은 현재 코드·검증 결과를 바탕으로 공통 처리 계약과 형식별 그룹화·구현 순서를 문서화했다. HTML/코드 production runtime을 구현했다고 보고하지 않는다.

## 읽은 계약과 목표

USER_OVERRIDES/INDEX/DECISION_REGISTER/T03, GROUPED_INFORMATION_STORAGE, MODULE_BOUNDARIES, MARKDOWN_RUNTIME과 HTML 검토를 확인했다. 기존 D raw-byte SHA와 tool-managed 등록, UUIDv7, immutable I, D2I application LLM0, source별 provenance와 atomic commit을 유지한다. 의미 단위는 원문 구조에 근거한 문맥 그룹으로 구체화하고 의미 판단·요약·가치선별·서로 다른 D의 주제 병합은 I2K 책임으로 둔다.

## 수행 범위

1. URL 수집과 응답 형식을 분리하고, PDF/HTML/Markdown/code의 parser·group·source locus·현재 구현 상태를 비교한다.
2. raw 보존·파싱 inventory·읽기 변환·I 저장·모델 입력을 구분하는 공통 계약을 설계한다. 형식별 위치를 가짜 page 또는 단일 Markdown 원문으로 바꾸지 않는다.
3. 독립 agent는 코드/승인의 충돌을 읽기 전용 검토한다. root는 설계 문서와 기존 INDEX/T03/모듈·입력 정책 연결을 편집한다. 앱 코드·DB·모델·Docker는 변경하지 않는다.
4. 문서 validator와 기존12오류를 대조하고 구현/시험 미완료를 표시한다. 새로운 P/권위/코드베이스 전체 identity 정책을 임의 승인하지 않는다.

현재 PDF/Markdown은 실제 저장 검증됐고 HTML은 D등록+시안, 코드는 미구현이다. 다음 vertical slice는 HTML 일반화와 Runtime 연결, Python code adapter, 파일 목록 수집과 source range별 I2K 입력 순서로 제안한다.

## 결과와 검토

[D2I_INPUT_FORMATS.md](../docs/implementation/D2I_INPUT_FORMATS.md)에 원본 형식·위치의 보존, URL 수집과 MIME 분리, 구조적 문맥 그룹과 I2K 의미 해석의 경계, 정적/동적 HTML의 capture profile, 코드 AST/CST와 원문 보존, 파일별 Data와 코드베이스 맥락, 공통 검증·구현 순서를 작성했다. INDEX/T03/입력 정책/모듈 경계에 연결했다. 원래 문서4개는 output/t03-multiformat-design/baseline에 보존했다.

독립 검토에서 고정 글자 수에 맞춰 canonical I를 자르지 않는 기존 승인, 코드의 다른 파일 참조를 원문과 섞지 않는 규칙, 동일 bytes의 다중경로/중복Data 문제, Runtime/I2K의 PDF/Markdown 이분 분기를 확인했다. 문서에 반영했고 이번 설계에서 승인이 필요한 미정 권위 정책은 발견하지 못했다. 전체repo를archive D로 정의하는 방식이나 파일수집 범위를 임의 확정하지 않았다.

Python AST와 Tree-sitter 공식 문서를 조회해 구문 트리/원문 위치 설명을 확인했다. Python column의 UTF8 byte 위치와 Unicode 문자 범위를 구분하도록 명시했다. 라이브러리를 설치하거나 코드를 실행해 adapter 지원을 시험한 결과로 표시하지 않았다.

변경은 설계문서와 링크·이 계획에 한정한다. 앱 코드·DB·Docker·새 source·model 호출은 없고 새 application tests를 작성하거나 실행하지 않았다. 문서 validator 결과는 output/t03-multiformat-design에 남긴다. 기존 raw/oracle Markdown12개 오류와 추가 오류를 구분한다. T03 전체 충실성 및 T04의 K 의미/저장 acceptance는 미완료 상태를 유지한다.

실행한 `python -X utf8 -B tools/validate_bundle.py --json`은 exit1이었다. 기존12개 오류와 같고 새 오류/사라진 기존 오류는 모두0이다. [비교 결과](../output/t03-multiformat-design/document-comparison.json). 문서 검사를 앱이나 의미 품질 검증으로 보고하지 않는다.
