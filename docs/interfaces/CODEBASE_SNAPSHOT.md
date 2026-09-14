# 코드베이스 원문 snapshot D와 기존 Markdown D2I

2026-09-13. 사용자는 현재 Palimpsest 코드베이스를 K2K 실험 자료로 선택하고, 우선 원문을 보존한 생성 Markdown 문서로 진행하며 코드 전용 D2I parser는 나중에 만들기로 승인했다. [실제 결과](../../output/t11-codebase-k2k/REPORT.md)와 [계획](../../progress/T07_codebase_k2k_execplan.md)을 따른다.

## D의 의미

이번 D는 선택한 코드 파일의 원문 bytes를 담은 `dossier.md`다. 개별 `.py`/`.js` 파일의 media type을 Markdown으로 속이지 않는다. 생성 dossier의 SHA-256이 Data ID이며 원래 파일의 상대 경로·SHA·크기·줄 수와 dossier 안의 byte/Unicode 문자 범위를 embedded manifest에 함께 보존한다. `manifest.json`은 같은 내용과 전체 dossier hash를 가진 검증용 사본이다.

원문 코드의 BOM·CRLF·분해 Unicode·backtick과 마지막 개행 유무를 바꾸지 않는다. 코드 안의 heading이 문서 구분자로 처리되지 않도록 충분히 긴 fenced block을 사용한다. 코드·설정·주석은 실행 명령이나 authority가 아닌 원문 데이터다. dossier의 소개·heading·manifest는 생성 metadata이며 원래 파일의 구간으로 위장하지 않는다.

기본 포함 범위는 `src`, `tests/app`, `tools`, `deploy`, 직접 작성한 `desktop` 최상위 파일과 `desktop/test`, 지정된 루트 설정/README다. output·model/cache·node_modules·private credential 이름·binary 등은 선택 policy와 제외 목록으로 구별한다. 모든 workspace 파일을 무조건 보관한 snapshot은 아니며, 경로명 검사만으로 모든 임베디드 비밀값이 없음을 보장하지 않는다. 이번 도구는 원문을 외부로 전송하지 않는다.

## CLI와 모듈

```text
palim code snapshot <repository-root> <new-output-directory> --json
palim code verify <snapshot-directory> --data-id <dossier-sha256> --json
palim code locate <snapshot-directory> --byte-range <start> <end> --json
palim code restore <snapshot-directory> <empty-target-directory> --json
palim data import <snapshot-directory>/dossier.md --media-type text/markdown --json
palim compile markdown <data-id> --json
```

후속 승인된 공유 저장은 `palim data import-code-snapshot <snapshot-directory> --json`을 사용한다. 이 명령은 dossier의 원래 전체 SHA-256을 유지하면서 파일 body와 포장 bytes를 공유 blob으로 보관한다. 기존 일반 raw 등록은 계속 지원한다. `manifest_from_bytes`, `compare`, `restore_bytes`는 sidecar나 현재 checkout 없이 보존된 Artifact Store bytes만으로 검증·파일 차이 비교·복원을 수행한다. [자료 버전 구현 계획](../../progress/T07_versioned_code_execplan.md)을 참고한다. 기존 snapshot을 새 표현으로 바꾸거나 이미 저장한 I를 재작성하지 않는다.

snapshot/verify/locate/restore 자체는 DB 없이 동작한다. 등록과 compilation은 기존 DataService/Artifact Store/Compiler Runtime을 사용한다. 기존 출력과 비어 있지 않은 복원 폴더는 덮어쓰지 않는다. symlink/junction/reparse point와 경로 탈출을 거부하고, source bytes와 선택 목록을 다시 확인해 capture 도중 바뀐 입력을 보류한다. manifest를 마지막에 게시하며 검증되지 않은 불완전 출력은 등록용 결과로 쓰지 않는다.

[code_snapshot.py](../../src/palimpsest/code_snapshot.py)는 원문 보존·manifest·locator·restore를, [기존 Markdown adapter](../../src/palimpsest/markdown_adapter.py)는 D2I를 담당한다. Windows private temporary-directory ACL이 hard link에 따라가 Docker가 파일을 읽지 못하는 문제를 실제로 확인해, 출력 디렉터리의 정상 ACL을 상속하는 staging file을 사용하도록 수정했다. source 파일의 권한을 완화하거나 root 실행에 의존하는 방식으로 마무리하지 않았다.

## I와 코드 위치

기존 Markdown heading 그룹을 이용하므로 기본적으로 파일 하나가 I 하나다. 파일 내부의 의미 분석이나 AST 추론은 이 D2I에서 하지 않는다. 모델이 필요로 하는 의미 항목은 [공통 source review](SOURCE_REVIEW.md)의 I2K 검토에서 나눈다.

정확한 역추적은 `I의 문자 범위 → dossier D의 byte/문자 범위 → embedded manifest → 원래 파일 hash/상대 경로/줄 범위`다. 코드 파일을 복원할 때는 해당 dossier byte 구간을 그대로 쓰고 개별 hash를 확인한다. 이후 workspace 내용이 바뀌어도 이 snapshot의 원문이 바뀌지는 않는다.

이번 release snapshot은 **202개 파일 / D1개 / I204개**다. 202개 파일 I와 소개·manifest I 두 개이며 원문 D를 전체 I에서 bytes까지 동일하게 재조립했다. 모든 파일의 D→I→D 범위와 모든 I의 원문 refs를 확인했다. 일반 중복 D 등록은 거부했고 같은 request의 replay는 동일 결과를 반환했다. 실제 D2I 실행은1회, OCR/application LLM 호출은0회다.

## 후속 코드 전용 parser

사용자 지시대로 이번 단계에서 만들지 않았다. 후속 parser는 언어별 구조·함수/클래스/모듈 경계와 파일/심볼/줄 위치를 보존할 수 있지만, 정적 코드 구조에서 새로운 동작·인과·성공한 실행을 추론해 I에 쓰면 안 된다. source-only I2K와 K2K의 경계는 유지한다. 기존 dossier D/I/ID/Revision을 네이티브 parser 결과로 소급 치환하지 않고 새 profile/source 실행으로 구별한다.

코드에 테스트 함수가 있다는 사실과 해당 테스트가 실제로 통과했다는 사실은 다르다. 실행 결과를 K의 근거로 쓰려면 해당 실제 로그/receipt를 별도 원문 근거로 관리해야 한다.
