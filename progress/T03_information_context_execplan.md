# T03 — Information 길이와 문서 구조별 I2K 입력 검토

2026-09-10 사용자 요청: 각 I의 실제 길이를 확인하고, 논문 Abstract/Introduction과 Results의 Figure 단위, Markdown heading 단위로 문맥을 구성한다. Semantic embedding과 provenance로 관련 I를 묶고 같은 D의 관련 I를 우선 제공하도록 한다.

## 범위

새 image200 Test_Paper의 고정 source I229개를 기준으로 정확한 ID별 문자/공백 단어 분포를 측정한다. 기존 `source_units.build_source_units`와 저장 검증 결과, `source-pages-v1`의 block→Information ID·offset 매핑을 재사용한다. 저장 I를 덮어쓰지 않고 절/소절과 연결된 Figure의 조회용 입력 시안을 만들어 실제 크기를 비교한다. 표본의 검토된 경계와 범용 자동 절 검출을 구분한다.

같은 D와 semantic/provenance 검색의 우선순위는 기존 canonical I2K seed/related/corpus 입력 계약 및 BGE-M3 교체 가능한 profile 경계 안에서 문서화한다. 이번에는 DB migration, embedding 모델 실행, I2K semantic model/Node 생성과 범용 Markdown parser를 구현하지 않는다. 원문 보존과 입력 그룹의 저장 경계를 재확인하는 분석 slice다.

## 근거와 절차

AGENTS/USER_OVERRIDES/INDEX/DECISION_REGISTER/PLANS/T04/CODE_REVIEW, source units/page/evidence 구현과 RETRIEVAL_PROFILE을 읽었다. 기존 U11의 projection/I 불변과 latest image200·I2K 원본 이미지 계약을 따른다. 미정 P registry/weights/top-K/provider는 확정하지 않는다. Ponytail 원칙에 따라 기존 측정·원문 조립과 stdlib만 재사용한다.

1. 고정 source bundle·page projection·source-unit manifest를 상호 대조한다. 이미지 I의 문자 길이는 이미지 픽셀/모델 vision token과 다르다고 명시한다.
2. Unicode codepoint와 공백 words를 실측하고 전체229 I의 ID·type·페이지·길이 inventory와 분포 보고서를 만든다. 모델 tokenizer를 실행하지 않으면 token 수를 실측으로 표시하지 않는다.
3. Test_Paper의 exact source boundary를 명시한 절/소절 입력 시안을 만들어 all-I coverage, Figure 참조와 원래 순서, 접합 separator·offset·원본 이미지 참조를 확인한다. 미분류 metadata는 원문/목록에 남긴다.
4. I2K context/embedding/provenance 계약을 기록하고 관련 문서에 연결한다. 실제 검색 adapter/ANN index·quality 평가와 구분한다.
5. 재현 스크립트의 assertions, 독립 측정과 수치 일치, snapshot 불변 및 document validator를 확인해 결과를 보고한다. 전체 app/DB/model 검사는 production code가 바뀌지 않으므로 반복하지 않는다.

## 완료·보류 기준

사용자가 전체 I 길이 및 묶은 입력의 크기를 검토할 수 있으면 이 분석 slice를 완료한다. I2K 실행·검색·의미 정확성을 완료로 표시하지 않는다. T03/T04 acceptance 상태는 변경하지 않는다. 원본/canonical snapshot/기존 I/ID/hash와 Docker 자원은 건드리지 않는다.

## 진행

- 현재 I의 page projection·source bundle과 독립 agent의 singleton source-unit 대조에서229개가 일치했다. 전체 문자63,031/공백 단어8,995이며 source text/image 종류를 나누어 보고한다.
- [재현 도구](../output/t03-information-context/analyze.py)는 고정된 이전 PG 저장 검증과 bundle/page/checks/evidence hash를 대조하고 source-unit 조립을 재사용한다. 첫 실행은 `Counter(mapping)`이 key count가 아닌 mapping values를 사용해 assertion 실패(exit1)했다. `.keys()`로 바로잡고 group membership의 반복 pop도 수정했으며 이후 실제 입력에서 exit0을 확인했다. parser/DB의 실패는 아니다.
- `python -X utf8 -B output/t03-information-context/analyze.py`: 최종 exit0. [전체 I별 길이·입력 그룹](../output/t03-information-context/REPORT.md), [exact ID/content/segment/좌표/이미지 매핑](../output/t03-information-context/analysis.json), [검증 receipt](../output/t03-information-context/verification.json)를 생성했다.229개 exact Information ID는 모두 한번씩 배정되고 각 그룹의 문자구간에서 원래 I content가 정확히 재현된다. 입력8개 파일 SHA는 실행 전후 동일하다. 모형 토큰/이미지 token은 미측정이며 embedding/semantic model/DB writes0이다.
- Text193개의 중앙값39자/4words, 평균271.16자, 137개가50자 미만이다. Header33/Footer28/PageNumber14/Title30/초록 전 metadata text42개의 영향을 구분했다. 초록 이후 text에서 keywords·caption continuation2개를 제외한41개(후반 설명 포함)는 중앙672자/102words, 평균914.34자다. 독립 실측과 일치한다.
- 논문 구조를 source refs로 검토한 시안은18그룹이다. Abstract1,239자/150words; Introduction(title포함)2,888자/378words. Results는7소절을 명시적 main Figure 참조로 연결한6그룹이며 각각6,420/3,539/4,600/4,753/5,546/4,934자다. 원문간 구분자2개 개행을 명시적으로 포함한 길이다. Figure1에2소절이 속한다는 표본 관찰을 범용1:1 grouping 규칙으로 일반화하지 않는다.
- Figure5(p9/10), Figure6(p11/12)는 Results 본문 범위(p2–8) 밖에도 걸쳐 있어 source refs 기반 추가 조회가 필요하다. Supplementary Figure 자료는 제공되지 않은 상태로 남겼고 main Figure로 잘못 연결하지 않았다. 그룹 text는 exact block concat이며 ambiguous 문단을 임의 복구하지 않는다. 문맥 완전성·semantic truth는 미평가다.
- 새 [I2K_CONTEXT_POLICY](../docs/implementation/I2K_CONTEXT_POLICY.md)와 T04/INDEX/DIKW_CURRENT/RETRIEVAL_PROFILE/USER_OVERRIDES/DECISION_REGISTER를 연결했다. 원문 I/검색 index/모델 입력 그룹을 분리하고 same-D 우선은 문맥의 우선순위로 한정한다. 모든 원문/기존 I/IDs/hashes와 앱·schema·Docker 자원은 변경하지 않았다.
- `python -X utf8 -B tools/validate_bundle.py --json`: exit1, 보존된 raw Markdown delimiter11건만 있으며 authored 문서/링크 추가 오류0이다. [검사 결과](../output/t23-ui-realm/build-test-logs.zip#output/t03-information-context/document-validation.json). raw나 validator 규칙을 수정하지 않는다. production code·DB·model은 바꾸지 않아 전체 app/DB/GPU suite를 반복하지 않았다.
- 독립 재계산·읽기 검토: 전체/Text/Image/source-type 통계,229 I/18그룹의1회 배정, exact content/offset/ID/bbox/anchor/projection hash/PNG metadata와 입력8개·산출물3개 hash가 모두 일치했다. Main Results의 title/text22개, Image36개와 떨어진 caption continuation2개가6그룹에 정확히 연결된다. 검토자가 앞선 수기 요약의 Keywords14words를11words로 바로잡았으며 보고서의 실제 계산과 전체합계8,995words에는 영향이 없었다. 새로운 모델/DB 실행을 한 검증은 아니다.

## 결과와 후속 경계

길이 측정·원문 기준 입력 시안·계약 구체화 범위를 완료했다. 새롭게 승인받아야 하는 결정은 없다. 실제 Markdown/범용 section projection, model별 tokenizer window, embedding/reranker adapter/index, same-D/corpus retrieval 및 I2K model/commit은 T04의 후속 구현·평가 범위다. 이번18그룹은 수작업 검토 source boundary에 대한 재현 가능한 예시이며 전체 문서 자동 grouping 성능은 아니다. 관련 AT와 T03/T04 상태를 일괄 pass로 올리지 않는다.

로그 링크의 ZIP fragment는 T23 정리 때 보존한 원래 entry 경로다. 원문 내용은 archive와 cleanup manifest에서 확인한다.
