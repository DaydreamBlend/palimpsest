# D 불변성·자료 버전 이력·공유 저장 제안

상태: **권고안 승인 — 2026-09-13 구현·실험 진행.** 사용자는 “네 권고대로 하는 게 좋겠어. 그렇게 해서 코드베이스의 변동이 있어도 K2K까지의 과정이 잘 동작하는지 (특정 Revision 유래임을 확인 가능한지 등 여러 측면에서) 확인해줘.”라고 승인했다. 아래 제안의 설계 근거는 유지하고, 실제 구현·검증 상태는 [현재 실행 계획](../../progress/T07_versioned_code_execplan.md)에 별도로 기록한다. 기존 D/I/hash와 과거 migration은 보존하며, 신규 적용 대상은 격리 fixture 및 코드 실험 DB다.

## 권고

**D는 그 시점의 정확한 원문을 나타내는 불변 객체로 유지하고, 자료별 버전 이력과 물리적인 중복 제거를 분리한다.** Revision이라는 개념을 UI/자료 관리에 제공할 수 있지만, 새 이름만 붙여 전체 bytes를 복사하면 용량 문제는 해결되지 않는다.

현재 `data_id=SHA256(보존한 원본 bytes)` 계약을 유지한다. 동일한 자료의 버전들을 묶는 UUIDv7 `data_series`와 불변 UUIDv7 `data_versions`가 각 exact D를 가리킨다. 이는 폐기된 public Source domain을 다시 도입하거나 기존 data_id를 UUID로 바꾸는 결정이 아니다. 승인 범위의 additive 0013은 parent, expected-head CAS, 요청 replay와 compilation의 exact version binding을 구현한다.

저장층은 D의 원문을 구성하는 content-addressed blob과 작은 manifest로 나눈다. 코드베이스는 이미 알고 있는 파일 경계를 사용해 변경되지 않은 파일 bytes를 공유할 수 있다. D가 generated Markdown인 현재 임시 경로에서도 원래 파일 body와 wrapper/manifest bytes를 별개 piece로 보관하고 정확한 순서로 재조립하는 표현을 검토할 수 있다. 읽기/export 결과는 원래 D bytes와 일치하고 전체 data_id hash를 검증해야 한다. storage manifest hash를 기존 data_id인 것처럼 치환하지 않는다.

Git의 blob/tree/commit 분리는 동일한 파일 내용의 공유와 snapshot/history를 함께 표현하는 참고 구조다. Git object hash 알고리즘/형식을 Palimpsest의 raw SHA-256 규칙으로 오인하지 않는다. [Git Objects](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects).

## 실제 캡처 두 개의 비교

비교 대상은 `output/t11-codebase-k2k/source/manifest.json`과 `source-release/manifest.json`이다. 첫 번째는 등록 전 실패 조사용 capture이며 두 개 모두 canonical D로 등록된 것은 아니다.

| 항목 | 값 |
|---|---:|
| 각 capture의 파일 수 | 202 |
| 동일한 path/content hash | 201 |
| 변경 파일 | src/palimpsest/code_snapshot.py |
| 변경 파일의 새 원문 bytes | 14,761 |
| 두 번째 전체 dossier bytes | 2,692,920 |

파일 내용 공유를 가정할 때 추가 file payload는14,761 bytes다. snapshot manifest, wrapper bytes, DB metadata, 압축, 첫 전환 비용은 이 수치에서 제외했다. 이것은 잠재 절감의 근거이며 실제 설치된 dedup 성능 측정이 아니다. 기존 dossier의 보존과 새 공유 저장의 초기 구축 비용도 따로 계산해야 한다.

## 논리 이력과 실제 복원

- UI의 자료 항목은 안정적인 ID를 갖고 여러 버전 기록을 보여준다.
- 버전 기록은 exact immutable D와 parent/변경 설명/획득 시점을 가리킨다. 같은 원문으로 되돌아간 경우 기존 D bytes를 재사용하면서 필요하면 새 전이 기록을 남긴다.
- 같은 head의 내용이 바뀌지 않은 재확인은 새 D/I를 만들지 않는다. 일반 duplicate import의 거부와 명시적 자료 갱신의 이력 관리는 별도 command 의미다.
- 각 D의 저장 manifest는 완전한 원문을 복원할 ordered blob refs와 원래 길이/hash를 가진다. 이전 버전에서 patch를 순서대로 실행해야만 내용을 이해할 수 있는 canonical 의미 모델로 만들지 않는다.
- rename/path/파일 mode 등 snapshot 문맥은 파일 내용 hash와 별개로 버전 manifest에 보존한다. 단순 경로 동일성만으로 같은 논리 자료라고 자동 확정하지 않는다.

## Diff와 추가 압축

Diff는 우선 두 버전의 비교 결과로 제공한다. 작은 파일 한두 개가 바뀌는 코드베이스에서는 파일 단위 공유부터 적용하는 편이 단순하다. 큰 단일 파일을 자주 수정해 파일별 공유만으로 부족하면 content-defined chunking 또는 delta compression을 Artifact Store 내부 최적화로 평가한다.

Git은 snapshot 객체 구조와 별개로 packfile에서 유사 객체의 delta compression을 사용한다. restic은 파일을 content-defined chunk로 나누고 snapshot/tree가 content hashes를 참조한다. 이러한 제품 전체를 설치한다는 결정은 아니다. [Git Packfiles](https://git-scm.com/book/en/v2/Git-Internals-Packfiles), [restic 저장 형식](https://restic.readthedocs.io/en/stable/100_references.html).

delta를 쓴다면 base와 delta의 무결성, 복원 비용, base 보존, 압축 재작성 중 복구를 별도로 검증한다. UI 버전 이력의 parent와 물리 압축의 base는 같은 객체일 필요가 없다.

## I/K에 대한 영향

파일 bytes 공유와 canonical I 재사용을 혼동하지 않는다. 현재 I는 Data/locus에 종속된다. **같은 D와 같은 완료 parser/profile 실행**은 재사용할 수 있지만, 서로 다른 D에 속한 I를 본문이 같다는 이유로 같은 I ID로 합치지 않는다. I 본문·raw parse·embedding input의 물리 blob/cache는 exact bytes와 profile hash가 같다면 별도로 공유하는 방안을 검토할 수 있다.

장기적으로 파일별 D와 code snapshot membership을 분리하면 변경되지 않은 파일 D/I를 그대로 참조하는 방식도 가능하다. 이는 D/I의 granularity와 코드 전용 parser 계약을 함께 검토할 별도 선택이며, 이번 용량 문제의 해결에 필수인 즉시 변경은 아니다.

K/K2K는 정확한 D/I/KRevision 및 적용되는 자료 버전 문맥을 계속 기록한다. 파일 내용이 같아도 import 경로·설정·의존성이 바뀌면 과거 K의 현재 적용성은 별도 검토가 필요하다. 과거 근거를 latest 자료로 자동 바꾸거나, 자료 head 변경을 기존 KRevision 변경과 같은 사건으로 가정하지 않는다.

## 안전한 첫 적용 범위

1. 기존 raw D/I/IDs와 artifact 읽기를 그대로 지원한다.
2. Artifact Store에 공유 저장 표현을 추가하고, 같은 Data ID의 exact read/export와 손상/중단/동시성 검사를 먼저 구현한다.
3. 그 위에 자료별 버전 목록·변경 비교·명시적 update와 no-op/revert 처리를 추가한다.
4. 코드 파일 기반 D/I 주소·추출 재사용은 이후 native parser와 함께 결정한다.

GC는 최신 버전만 보고 지우지 않는다. 보존한 D/I/KRevision, snapshot/history 및 진행 중 등록이 참조하는 전체 blob closure를 보호해야 한다. 새 manifest를 canonical로 반영하기 전에 모든 참조 bytes의 보존·무결성을 확인한다. [현재 U09 저장·복구 경계](../decisions/STORAGE_IDENTITY.md)를 유지한다.
