# 사용자 요청 D2K와 명시적 K 개정

승인2026-09-13, 검증 마감2026-09-14(KST). 앱0.15.0 / Electron UI0.4.0 / additive schema0014·0015. [승인](../../docs/decisions/USER_REQUESTED_D2K.md), [D2K CLI](../../docs/interfaces/D2K.md), [K 개정 CLI](../../docs/interfaces/KNOWLEDGE_REVISION.md), [진행 기록](../../progress/T15_explicit_d2k_execplan.md).

## 구현

- D2K는 등록 D·실패/문제 보고·원문 선택 view·모델·버전·기존 K catalog를 manifest에 고정하고 사용자가 정확히 확인한 별도 실행만 허용한다. I2K 오류나 모델 출력으로 자동 승인/호출하지 않는다. I가 없는 실패도 처리하며 D2I와 I 생성은 호출하지 않는다.
- UTF-8 byte/문자/줄 범위와 PDF 선택 페이지를 원본 SHA에 결속한다. PDF 페이지는 실제 원본에서 재렌더링하여 pixels를 대조한 뒤 Artifact Store에 보존한다. Generator/독립 Validator의 실제 전달과 원문 근거·중요도·scope·source-only 검증이 canonical D grounding·K·Record와 함께 반영된다.
- 같은 의미 K는 기존 Revision에 support만 추가한다. D2K 생성 origin은 source-only이며 추론은 K2K로 표시한다. 나중에 지원을 추가해도 최초 origin을 유지한다. D2K 성공으로 원래 D2I 실패나 I2K 오류를 완료 처리하지 않는다.
- Wiki의 명시적 추가 Data scope, I 없는 D 근거 검색·답변·Desktop 읽기를 지원한다. 직접 D와 K2K 전이 D를 구분하고, scope 밖 원문과 저장 답변을 차단한다.
- 명시적 I2K/K2K 개정은 같은 KNode·논리 FP에 새 의미 Revision을 만든다. 독립 same-identity/materiality/grounding 판정, exact target 전달·CAS, 과거 Revision·근거·의존 참조·N2E/K2K outbox를 원자적으로 보존한다. 같은 의미/판정 불가/오래된 target/후보 없음은 서로 다른 결과다. D2K 의미 개정은 현재 사용자 확인 범위에 포함하지 않는다.

## 검증 상태

단계별 실행을 합쳐 **서로 다른 앱 검사947개가 모두 검증**됐다. 전체942개 실행은918 pass/23 native skip/옛 fixture 오류1개였다. 오류 fixture가 명시적 개정 규약을 거치도록 수정한 뒤 해당1개와 새 읽기 호환성5개를 통과했고, 빠졌던23개 native 검사를 고정 PDF 환경에서 전부 통과했다. 전체947개를 한 명령으로 다시 돌렸다고 보고하지 않는다. [집계와 로그 결속](verification-summary.json), [전체 실행](full-app-first.log), [실패 수정·추가 검사](final-followup-checks.log), [native23](native-final.log).

| 검사 | 관찰 |
|---|---|
| D2K pure 원문·schema·scope | 17 pass |
| 고정 PDF renderer 위조·geometry·원본 pixels | 9 pass |
| D2K Runtime·원자성·버전·혼합 K2K | 13 pass, I2K 오류 연결·승인 이후 catalog 충돌 포함 |
| 실제 PDF→view→ArtifactStore→PG D2K | 1 pass, 합성 모델 receipt |
| 실제 Wiki/pgvector/검색답변/원문 Desktop 소비 | 5 pass, 합성 vector·모델 receipt |
| 실제 I2K/K2K 의미 개정 | 8 pass |
| 기존 실제 코드 이력 보존 | 137 pass, DB·artifact 읽기 전용 |
| source Node / ASAR renderer | 28 pass / 19 pass |
| 실제 packaged Electron | 숨겨진 창의 DOM·기존 Code Wiki·K2K·원문·저장 답변 읽기 통과, screenshots0 |
| 실제 외부 모델·D2K 사용자 자료 전송 | 0 |

문서 bundle 검사 전체는 기존 외부 패키지/보존 산출물 문서 오류948개로 failed다. 현재 `AGENTS.md`, `README.md`, `docs/`, T15 진행·결과 문서의 오류는0이다. 전체 문서 mutation 테스트는 외부 의존성·산출물까지 반복 복사하는 방식이어서 중단했으며 pass로 세지 않는다. 앱 검증과 분리한다.

실제 코드 DB `palimpsest_codebase_k2k`는 schema0013을 유지한다. D3/I242/K42/KRevision42/DataVersion3과 과거 hash·raw bytes·자료 A→B→A 이력을 대조했다. 새 migration은 `palimpsest-multi-checks-db-1` 안의 전용 합성 DB `palimpsest`, 이번 작업에서 새로 만든 `palimpsest_d2k_checks`에만 적용했다. 원래 논문 서버와 사용자 자료 DB를 migration/파괴 테스트 대상으로 사용하지 않았다.

초기 테스트 DB template 복사 중 PG의 untracked child process exit2로 서버가 자동 재시작했다. WAL 복구 뒤 접속·기존 code DB 개수와 위137개 보존 검사를 확인했다. 원인을 단정하지 않는다. template0에서 만든 빈 격리 DB로 검사를 계속했으며, SQL 초안의 문법·별칭·append-only 잠금 오류 및 테스트 fixture 불일치는 실패 로그를 보존하고 수정했다.

## 패키지·한계

[새 Code Wiki 실행](ui/Open-Code-Wiki.ps1). UI0.4.0은 기존 캐시의 Electron44.3.0으로 만들었고 dependency 다운로드는0이다. 기존0.3 ASAR을 보존했다. 준비된 새ASAR은 `b71c5efa1e23a9f29d142669df8b517de886284ac8d67e4aa629a287ff2a42d2`다.

최종 이미지는 `palimpsest-d2k:0.15.0` (`sha256:8a9ce79ca9183a35a0a333ef5c354d63055829a8a6a5f29e76ee2242c56974bf`), 선택 PDF runtime은 `palimpsest-d2k-pdf:0.15.0` (`sha256:3a4dbef12f9ce65fff5749720326e7b2a3900901e4bb53193e9a4c67b0b544fe`)이다. 테스트 컨테이너는 `--rm`으로 정리됐고 dangling image는0개였다. 기존 실제 DB·모델·정상 과거 이미지와 데이터가 남아 있는 옛 개발 DB container는 삭제하지 않았다.

실제 패키지 첫 연결은 schema0013과 최신 schema 일치 검사 때문에 실패했다. 정확한 checksum prefix13·14는 **읽기 전용 transaction에서만** 허용하고 쓰기는 최신15를 요구하는 호환성을 추가했다. 재검사에서는 기존 실제 DB를 변경하지 않고 Code Wiki·현재 inferred K·정확한 과거 premise I·미완료 검토·저장 질문을 읽었다. [실제 UI 기록](ui/packaged-ui-compatible.log). 최초 실패 로그도 보존한다.

기존 renderer를 재사용한 PDF runtime은 앱 SQL 드라이버·코드만 추가했으며 새 모델 다운로드가 없다. 원문 페이지 이미지와 native PDF bytes 전달은 다르다. 현재 D2K는 UTF-8 text와 고정 renderer가 지원하는 PDF 선택 페이지를 다루며 PDF 회전 페이지는 명시적으로 거부한다.

전체 자동 propagation scheduler, 변경된 Wiki의 재생성·독립 검증, 개인 Decision/W2K, 온라인 수집은 후속이다. 현재 material revision의 exact impact·outbox가 남아 있으면 `outbox_pending_not_converged`이며 자동 확장 전체가 끝났다고 표시하지 않는다. D2K 품질과 LLM의 중요도/중복/추론 정확성을 합성 receipt 테스트로 증명하지 않는다.
