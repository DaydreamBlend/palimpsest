# 공유 원문 저장·자료 버전·실제 코드 I2K/K2K 검증

최종 상태: **승인된 자료 버전/공유 저장 구현과 두 코드 사본의 실제 K2K·과거 이력 검증 완료.** 전체 코드 의미 검토와 전체 T07 scheduler는 미완료다. 최종 결과는 [보고서](../output/t12-versioned-code/REPORT.md), [18회 실제 모델 집계](../output/t12-versioned-code/semantic-summary-final.json), [208개 읽기 전용 검사](../output/t12-versioned-code/readonly-history.json), [자료 A→B→A 검증](../output/t12-versioned-code/revert-history.json)을 따른다.

2026-09-13 사용자 승인: DATA_VERSION_STORAGE_PROPOSAL의 권고대로 구현하고 코드 변경 후에도 특정 Revision 유래와 K2K까지의 동작을 확인한다. 코드 전용 D2I parser는 계속 후속이며 현 Markdown dossier D의 원문 SHA/불변성을 유지한다.

## 목표와 범위

1. 원문 D를 ordered shared blobs로 저장하고 exact read/export/복원과 손상·중단·동시성을 검증한다.
2. 안정적인 data_series와 불변 data_versions로 no-op,변경,revert,stale-head 충돌/동일요청replay를 기록한다.
3. I2K/N2E/K2K execution을 exact source version에 결속하고 현재 head 검사와 명시적 historical/pinned 분석을 구분한다.
4. K 최초 생성 version과 후속 support version을 별도로 조회하고, 과거 근거/Revision을 덮어쓰지 않는다.
5. 전체 코드 snapshot의 저장/복원 검증과, 실제 두 모듈 전체를 사용한 작고 완전한 D의 Terra 실험을 구분해 실행한다.

읽은 계약: AGENTS/USER_OVERRIDES, PLANS/CODE_REVIEW, DATA_VERSION_STORAGE_PROPOSAL, STORAGE_IDENTITY, CODEBASE_SNAPSHOT, SOURCE_REVIEW, K2K_RUNTIME, 원문 전용 I2K/K2K 추론 및 modular boundaries. 기존 source/Wiki DB와 모든 과거migration/raw/I/ID/FP/Revision은 보존한다. 새 적용은 격리 fixture 및 코드 실험 DB에만 한다.

## 구현 소유권

- ArtifactStore/segmented_artifact_store: raw 호환 + 공유 byte manifest, canonical artifact_path/data_id 유지, source별stagingcleanup만. GC/기존raw삭제없음.
- data_versions +0013: stable series/head,불변version+요청replay/currentheadCAS,prepared execution/version typed bindings.
- version_provenance: origin과accepted/reusedsupport의immutable annotations 및 별도현재head projection.
- 루트: DataService/CLI의관리등록,KnowledgeRuntime의versioncontext·receipt·실제모델실험·최종검증.

## version context 규칙

`data_version_ids`를 지정한 execution은 immutable version rows를 input_snapshot.data_versions로 고정한다. `data_version_mode=current`는 series별정확head를 준비/반영시확인하고, `pinned`는명시적역사/비교분석을허용한다. mutable head는 frozen prompt에섞지않는다. Data version 변경은 K semantic Revision 변경이아니므로지식상태counter만으로검증하지않고head를별도확인/잠근다.

출처가다른I를같은ID로합치지않는다. no-op/revert는rawD와완료D2I를재사용할수있지만새version전이/분석context는정확히남긴다. K의originversion을나중supportversion으로덮어쓰지않는다. 현재버전상태는근거의진실성이나K semantic현재성과별개다.

## 실제 실험 계획

전체 code source 공유저장은 manifest/file hash 기준으로 확인한다. semantic 실험은 `knowledge_runtime.py`와`codex_provider.py` 전체원문+중립EXPERIMENT.md를D로쓸것이며,본문/I를중요도script로나누어누락하지않는다. V2는사본의Runtime MODEL.model 한곳만Terra→Sol로바꾸고실제앱/Provider설정은유지한다. Generator가원문사실을선택하고K2K가전제들로model-field조건부결론을도출하는지독립검증한다. 기대결론은모델입력metadata에미리쓰지않는다.

sourcecopies/snapshots와lineage: `output/t12-versioned-code/semantic-case/`; 계획: [SEMANTIC_EXPERIMENT_PLAN](../output/t12-versioned-code/SEMANTIC_EXPERIMENT_PLAN.md). 기존검증Codex0.153.4절대경로를사용하며credential은읽거나출력하지않는다. 이번사용자지시는코드변경의실제I2K/K2K검증을요청했으므로해당명시코드실험범위에서기존Terra설정을재사용한다. 자동승인검토가막으면해당전송/이유를보고하고영향없는작업을계속한다.

## 검증해야 할 조건

- 다른D 사이공유blobs,정확원문SHA/size,누락/변조/order/잘못된range,파일/Dno-follow,crash/retry/동시publish.
- series no-op과A→B→A전이,동일요청replay,stalehead현재상태반환,부모/owner/crossseries오류,불변history.
- version없는legacy요청보존,exactversion검증/전송hash,foreignversion거부,current반영중head변경차단,pinned역사분석.
- K/I/derivation의sourceversion역추적,sourcebody같은revert의재사용과origin불변,과거graph의행보존.
- 새구조unit/실제격리PG,실제코드D/D2I/I,liveTerra의구조·의미판정을별도로보고한다.

## 진행

공유store는실제Linux기존18+신규12=30tests pass/skip0. 첫parallelCAS실패는정상hardlink제거ctime변경으로인한오인이었고,linkcount변화만제한적으로허용하면서inode/size/mtime/hash검사를유지해수정했다. data_versions/0013와version_provenance의코드·tests는작성됐으며통합/PG검증전이다. V1/V2원문사본과snapshot생성은완료,DB/live모델은아직미실행이다.

후속 진행: 0013을 fixture palimpsest 및 palimpsest_codebase_k2k에 설치했다. 첫 전체753tests와 focused20tests를 같은 fixture에서 겹쳐 실행한 운영 실수가 있어 global knowledge_state CAS로 각각4errors/3failedcases가 발생했다. 제약을 완화하지 않고 로그를 보존했으며 단독 전체 재시험 중이다. 첫 전체에서 새 versioned8tests는 모두 통과했다. 버전 없는 기존 K 경로도 별도 검증한다.

실제 코드V1 `dfbb…`는 정확한 version `01a099ee-b72a-7260-879e-bac04e0befd8`와 D2I 1회/I5개로 저장됐다. 모든 I가 exact D를 복원한다. Terra 첫Generator/Validator는6K를 승인했지만3개source target의 세부 검토 누락을 발견해 needs_human으로 기록했다. 같은I/이전검토의 후속I2K를 진행하며 D2I는 반복하지 않는다. 실험runner의 DataService import누락으로 첫실행이DB변경전에실패했고수정후정상실행됐다.

전체202파일×2 snapshot의 [실제 저장 측정](../output/t12-versioned-code/storage-benchmark/REPORT.md)은201개본문을공유하고둘째버전에109,589B(payload+descriptor),114,688B(파일할당)만추가했다. 양쪽모든404파일복원hash와no-op/oldread가통과했다. 두버전합은payload47.253%,동일volume파일할당23.936%절감이다. DB등록/I/K/모델시험과구분한storage-only벤치마크다.

## 나중에 할 인터넷 검색 기능

사용자가 [ChatGPT 공유 답변](https://chatgpt.com/s/t_6aa65b41bae0819188a4b26b95b8e11b)을 훗날 인터넷 검색 기능을 붙일 때 참고하도록 지정했다. **현재 내용은 읽거나 검증하지 않았으며 이번 구현에 반영하지 않는다.** 검색 기능 착수 시 링크 접근성과 실제 내용을 확인하고 참고한다. 이것은 새 예약작업이나 현재 scope 확장 요청이 아니다.

## 최종 실행·검증 기록

- 앱0.12.0/격리schema0013. 최종image a55a64d1…; 직전 전체764tests는748pass/16skip/실패0(290.929초). 마지막 N2E타입schema 보완 뒤최종image의관련11tests가모두통과(22.417초)했다. 별도PDFium현재source22tests도22pass/skip0이다. 중복실행수를별도신규tests로더하지않는다.
- 실제V1 source K14/Edge3/추론K1, V2 source K9/Edge4/추론K1. 합계25KNode/25Revision,7KEdge/7Revision,2derivation. V1재검토의reuse Record10개는원래Revision을유지한다. 모든source I5개씩전달했고 D2I는각1회다.
- 독립I2KValidator는큰코드블록의세부검토를보류해두버전모두needs_human이다. 승인된K의N2E/K2K실행만completed이다. 기대했던Runtime/Provider MODEL불일치추론은생성되지않아자동회귀검출성능을입증했다고보고하지않는다.
- 실제provider18calls(원문I2K8,N2E6,K2K4),input1,573,322/output33,712tokens,reasoningfield8,424,cached0. Runtime실패2calls도포함한다. 호출합시간737.596초는전체개발시간이아니다.
- Live N2E의stage/JSONB dictionary순서차이는prompt hash불일치로차단됐다. 최초실제receipt를failed로보존하고DBcontext로새Validator를호출해복구,공유helper정렬로수정했다. V2의Observation target제안은정상typedguard가차단,0Record failed실행을보존하고schema도Propositiontarget으로제한했다.
- 자동승인검토가코드N2E전송과V2I2KValidator를각각거절했다. 사용자가구체payload의V1/V2 N2E/K2K와I2K생성·검증·재검토를각각명시승인한뒤실행했다. 차단된명령자체는provider0call이다.
- 읽기전용208assertions에서old310a D/204I/이전prepared未전달job,신규D2개/I10개,exactorigin/premise/version/actualreceipt를확인했다. 실제CLI로V1을별도폴더에복원하고3개파일hash를검사했다.
- 최종실험자료시리즈의head는V3 `01a09a28-b3cd-7521-8659-82b2013d2308`이며V1과같은D A를가리킨다. 이것은실험자료이력의A→B→A시험이다. 실제src/desktop hash와앱0.12.0은유지됐고Data/I/K/실행/모델call행hash도불변이다. no-op,staleCAS,replay통과. 원본재조립208개검증은확인된baseline으로재사용하고새전이전후의행·rawSHA를비교했다.
- 사용자의기존Docker정리요청에따라이번0.12중간이미지2개를정확ID/비사용확인후삭제했다. 최종image/DB/Artifact volume/다른프로젝트는보존했다.
- 문서전체validator의기존vendor/보존raw/복원사본오류는별도보고한다. tools전체mutation suite는큰workspace clone단계에서중단했으므로통과라고하지않는다. Markdown inspector7tests는통과했다.

남은범위: nativecodeparser,큰코드I의의미검토완성,자동dependencyrevalidation/EffectiveEdgeK2K/전체scheduler,새버전표시의Wiki/RAG/GUI연결. 승인된실행slice완료를전체T07 acceptance완료로확대하지않는다.
