# I2K의 I 부족 → D2I 오류 보고·보류

2026-09-13 최신 사용자 정정에 따른 구현. [현재 결정](../docs/decisions/I2K_INFORMATION_ERRORS.md)이 [중단한 직접 D 계획](T14_direct_source_execplan.md)의 전제를 철회한다.

## 목표

source K는 반드시 I의 실제 근거로만 생성한다. I2K가 I 자체의 부족/전사/이미지/provenance 문제를 발견하면 정확한 I/Data/source execution과 실제 모델 보고·Validator 이유를 사용자에게 보여주고 관련 K를 보류한다. D2K, 직접Dgrounding, D2I자동재실행·I수정은 모두없다. 일반 K 선택 누락은 D2I오류와구분해 기존review-resume으로진행한다.

## 범위와 소유권

Root: 최신결정/문서, KnowledgeRuntime의new-policyprofile·영속오류·후보보류, requestpolicy/CLI/review-resume차단,통합검증. Pureagent:information_errors.py+puretests. PGagent:전용test_information_error_runtime.py. UIagent:기존review화면의정확오류/관련I표시와렌더러검사. schema0013과기존DB를유지하고공통fixture시험은Root하나만실행한다.

## 복원 기록

직접D초안의기존Python/worker12파일은검증된0.13image/역패치에서이번작업전SHA로복원했고desktop4파일도최종0.2ASAR/역패치로원래SHA와일치시켰다. 새직접D모듈2개/0014draftSQL/새test1개를실행source에서제거했다. `output/t14-source-issues`에복원proof와폐기초안을보존한다. DB/migration/provider실행0,원문/자료version/I/K변경0이다.

## 구현·검증 순서

1. 기존source_requests/per-IValidator판정에서D2I정보오류를읽는순수projection과recognizedreasoncodes. unknownI/다른D지정거부,일반selectiongap오분류금지.
2. 새multi-I2Kprofile에정책을고정하고Generator/Validator모두I-only/K2K경계를전달. Generator보고와Validator-only보고모두관련후보를needs_human으로유지. unrelatedI의검증K허용,rawreceipt/이력보존.
3. CLI source-issues/review-status와읽기UI오류배너. 자동review-resume은사용자확인필요오류를반환하며원문fetch/D2I/직접K경로가없음을검증.
4. isolatedPG영속/원자성/보존/재실행검사,전체앱/Node/필요한실제UI검사와보고. 실제모델회수율평가와합성receipt검사를구분한다.

## 현재 상태

복원과최신결정문서를작성했고새구현을시작했다. 앱테스트/PG/UI검증은완료전이다. 원래208파일코드크기측정은[보고서](../output/t14-direct-source/code-context-size.md)에보존한다.

## 최종 결과

[완료 보고서](../output/t14-source-issues/REPORT.md)와[검증요약](../output/t14-source-issues/verification-summary.json)에실제명령/실패/복구를기록했다. 앱0.14/UI0.3/schema0013. 최초D2K초안은실행전철회/복원했고최종source에는없다. 현재I오류보고·관련K보류·일반재개차단/선택누락재개구분·exactI위치조회가구현됐다.

- 전체최종image검사847(831pass/16skip),별도PDF22pass로16skip보완/6중복,focused49pass. 제어된PG사례에서관련후보2개보류·다른I후보1개반영을기록했다. Provider/D2I복구/directDcanonical쓰기0.
- 실제codeDB137읽기전용검사로이력/원문/source/Version을보존했다. 실제CLI는기존완료I2K의D2I오류없음을반환했다.
- UI source24/ASARrenderer15pass,기존code자료의실제source/package읽기호환각통과. 새오류banner는합성Nodefixture로검증했으며실제자료에오류를주입하지않았다.
- 부적절한testcandidatebody조회/잘못된test모듈명/schema설명중복/CLI인자오용의실패로그를유지했다. 문서validator기존외부948오류와이번작성문서오류0을구분했다.

이수직범위완료후직접D→K는계속금지다. 기존K전체의영향재검토/일반의미개정·상충/전체scheduler/오류확인UI와원래전체202파일의의미분석은이번완료로표시하지않는다.
