# D↔I 원문 대응과 전체 I의 LLM 중요성 선택

2026-09-11 최신 명확화: [다중 source I2K](MULTI_SOURCE_I2K.md)에 따라 한 K는 서로 다른 D의 I들을 함께 근거로 사용할 수 있다. 아래 하나의 fullsource 실행은 신규 문서의 전체 검토 의무이며 개별 K의 근거를 그 D에 제한하는 규칙이 아니다. 추가 조회한 타 문서 I를 해당 문서의 전체 검토로 기록하지 않는다. I 자체와 source-specific 실험 결과의 불변성은 유지한다.

2026-09-11 최신 후속: [I2K 근거 공백의 직접 D 근거 정책](I2K_DIRECT_SOURCE_EVIDENCE.md)을 적용한다. D2I는 원문을 충실히 보존하는 단회 처리를 목표로 하며 I2K에서 재호출하지 않는다. I에 없는 근거는 등록 원본을 직접 검증하고 K와 오류/품질 이력을 연결한다. 전체 I 검토·기존 I/Revision 불변성·source scope는 유지한다.

2026-09-11 사용자 후속 승인. 사용자는 “D의 어느 구간을 찾더라도 I에서 그것을 찾을 수 있어야 함”, “어떤 I를 고르더라도 원본 D의 그 위치를 찾을 수도 있어야” 함을 명시했다. 복원은 I에 원문 내용을 보존하고 연결된 original artifact에서 exact 원본 파일도 복원하는 기준이다.

D2I는 중요성을 선택하지 않는다. 원문을보존하는기존MinerU/스크립트와정확한양방향위치를유지한다. PDF의OCR누락영역도찾을수있도록새sourceprofile에검증된originalpagefacsimile을ImageI로추가할수있다. 기존I를수정하거나존재하지않던pageimage를기존I의미디어라고취급하지않는다. 원문block을찾는coverage와D의모든시각구간주소coverage, OCR검색가능성을구분한다.

I2K의처리범위는하나의선택된fullsource실행의전체I다. scripts는중요도를판단하거나제목/길이/종류로미리버리지않는다. LLM이각I를검토하고K선택/문맥사용/선택하지않음/검토필요와그이유를출력한다. 출력과실제전달receipt를분리하고미처리I를선택하지않음으로기록하지않는다. context길이에맞춘분할은처리계획이며전체미해결의무를성공중단하는제한이아니다.

일반적명제가거의완전히같은의미라면기존K에근거를추가하고새K/semanticRevision을만들지않는다. 유사도나같은단어만으로의미동등성을확정하지않는다. source-specific실험결과/그해석은출처와실험조건을보존하고다른Data의유사결과와병합하지않는다. Observation은source-specific이며Proposition도실험에귀속된경우source-specific일수있다. 같은Data의반복서술은실험맥락까지같을때재사용한다.

중요성/identity_scope/의미동등성은LLM의구조화제안과독립검증대상이고, Data scope/FK/FP/ID/정확quote/read-set/atomiccommit은애플리케이션이검사한다. 기존K의scope분류를추가해도과거ID/FP/Revision을덮어쓰지않는다. accepted K 이후 N2E를수행하고EdgeRevision은정확NodeRevision을참조한다.

이후정책은[실행계획](../../progress/T04_full_source_selection_execplan.md)에구현·검증상태를기록한다. 이전firstgraph의principalclaims추출방식보다이승인범위가우선하며, 원본보존/실제권위/R07·R08/후속K2K와미정P범위는유지한다.
