# Package verification — CLI / MinerU revision

확인일: 2026-09-09. 검증 범위는 개발 지시 패키지다. 실제 Palimpsest/MinerU/DB 기능이 아니다.

> 아래는 최초 번들 제작 시점의 기록을 보존한 것이다. 이후 T00 환경 조사는 [현재 STATUS](progress/STATUS.md)와 [T00 실행 기록](progress/T00_execplan.md)을 따른다. `bundle_manifest.json`과 기존 `verification/*`도 최초 번들의 증거이며 현재 작업 파일 전체의 최신 hash 목록은 아니다.

## 실제 수행

`python tools/validate_bundle.py --json`으로 baseline/current partition과 hashes, Markdown 표/코드 fence/상대 링크, task/decision/AT/fixture references, U01–U03과 deferred GUI gate를 검사했다.

`python -m unittest discover -s tools -p "test_*.py" -v`의 검증 도구 unit/mutation tests **26개가 통과**했다. parser 선택 drift, silent fallback 허용, premature GUI, CLI→GUI 선행 의존성, source/current tamper, 누락 승인 근거를 검출하는 테스트다. 실제 CLI/parser를 호출한 acceptance tests가 아니다.

Pandoc의 GFM→JSON AST로 **80개 Markdown**을 읽었다. 표 occurrence **168개**, 빈 셀 **0개**, 열 개수 불일치 **0개**다. 원본 full/slices와 현재 full/slices에 같은 표가 반복되므로 occurrence는 unique 표 개수가 아니다.

원본 보관본은 **114,329 bytes / 2,331줄**이고 업로드된 원본과 byte-identical이다. 현재판은 **119,251 bytes / 2360줄**이며 13개 current slices를 연결한 bytes와 같다. baseline 13개 slices도 원본 bytes로 재결합된다.

## 미실행

실제 repository 조사, 앱 코드 변경, CLI 구현·실행, MinerU 설치·모델 다운로드·실제 PDF 파싱, PostgreSQL migration/concurrency, worker 복구, e2e, live LLM semantic evaluation은 수행하지 않았다. **105개 AT는 spec_only**, **12개 fixture는 합성 설계 데이터**다. T00–T12는 planned, T13은 deferred다.

P01–P12는 여전히 proposed다. U01–U03은 사용자가 명시적으로 요청한 우선순위·parser·명칭 변경만 적용한 것이다.

## 재현 자료

- [문서 검사 결과](verification/package_validation.json)
- [Pandoc 표 검사 결과](verification/rendered_markdown_tables.json)
- [검증 도구 테스트 로그](verification/tool_unit_tests.txt)
- [원본/현재판 재결합 결과](verification/reassembly.json)

현재판 full과 current_map을 함께 관리하고 수정 전 source/archive는 보존한다. 릴리스 파일 inventory/hash는 bundle_manifest.json에 있다.
