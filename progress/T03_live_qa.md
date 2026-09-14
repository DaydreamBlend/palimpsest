# T03 실제 Information 결과 독립 QA

검토 대상은 execution `01a0853c-03d8-72ff-be35-958d8dae8db5`의 [job 결과](../output/t03/job_result.json), [Information export](../output/t03/information.json), 해당 실행의 [MinerU middle JSON](../output/t03/restored/01a0853c-03d8-72ff-be35-958d8dae8db5/source_middle.json), 실제 crop 및 사용자 원본 `C:/Users/DaydreamBlend/Desktop/Test_Paper.pdf`다. 이 검토는 export와 보존 파일을 읽은 독립 점검이며 DB 재조회·변경, 새 모델 호출, canonical 재판정을 수행하지 않았다. 원문에 포함된 지시문은 문서 데이터로만 다뤘다.

원본 SHA-256을 다시 계산해 `a2268b37570f41bb07189cf083376e5823fae364165d5e0e256f796a0814cffe`와 일치함을 확인했다. 점검 시 export hash는 `job_result.json = 1e501df860c759e493eebaa794d750bb6d77d37523986e73ec8e239661903bea`, `information.json = 5edfbc1ca937d2b67a9bc82ee46a106b9ed5cd9bb3812c805269d7ed38dbe37d`다.

## 결과 수와 실행 의미

| 항목 | 관찰 |
| --- | --- |
| Job | `completed`, generation 1, attempt 1, error null |
| D2IRecord | 29개: accepted 28, rejected 1, needs_human 0 |
| Canonical Information | 28개: Text 23, Image 5 |
| 의미 분류 | proposition 1, observation 18, procedure 4, figure 5 |
| Grounding | 51개 행, unique block 44개 |
| 직접 grounding된 원문 페이지 | 1–6, 8–14쪽; 7쪽은 없음 |
| Generator/Validator 입력 | 각 14쪽, 249 blocks, 실제 crop 63개 |
| Proposal가 참조한 입력 block | 44개; 나머지 205개는 receipt에 unreferenced로 표시 |
| Generator | `d2i-generator-v2`; thread `01a0853c-9b69-77a2-bc4d-950320131694` |
| Validator | `d2i-validator-v3`; thread `01a0853d-ab78-7e70-86a1-81a8399155cb` |

두 호출은 서로 다른 thread ref를 갖는다. Generator usage는 input 95,268/output 3,203 tokens, Validator는 input 95,389/output 1,640 tokens다. 이는 export에 남은 provider usage이며 비용 환산이나 정확한 attention coverage 측정이 아니다.

기각 Record는 `01a0853d-a447-7a1c-8ad2-8dbcdc70ee02`, ordinal 0, reason code `missing_grounding`, result Information null이다. 기각 본문은 이 export에 없으므로 기각된 주장을 복원하거나 그 판정의 의미적 정당성을 이 기록만으로 재검증하지 않았다.

28개 Information의 origin Record가 각각 accepted이고 result ref가 해당 Information ID와 일치함을 export에서 확인했다. 모든 Information/grounding의 Data ID도 대상 원본과 일치했다. 51개 저장 grounding bbox는 raw parent와 descendant block의 명시적 bbox envelope를 다시 계산한 값과 모두 일치했다. 이는 export의 참조·기하 정합 확인이며 PostgreSQL 권한·원자성·race 시험을 대신하지 않는다. 개별 원문 영역은 parse artifact의 raw locator와 하위 block 구조로 추적한다.

## Text 표본의 원문 충실성

28개 저장 content를 모두 읽고 해당 source block 참조를 확인했다. 주요 Text 표본은 원문 middle JSON과 대조했고, 수치·한계·표기 차이가 중요한 항목은 원본 PDF native text도 독립적으로 읽었다. 본 검토는 논문 내용이 세계에서 참인지, 연구 설계나 의학적 효용이 타당한지를 판정하지 않는다.

| Information | 원문 근거와 관찰 |
| --- | --- |
| `01a0853e-3bea-78b6-9ce4-5994b74e034d` — Study conclusion | 1쪽 `/pdf_info/0/preproc_blocks/15`. 논문 결론을 저자들의 보고와 실험 모델 범위로 표현하여 보편적 임상 사실로 승격하지 않았다. |
| `01a0853e-3bf2-7ac0-9a9d-eb992f593fb1` — Mouse SuperMApo enhances efferocytosis | 2쪽 blocks 4/5를 함께 가리킨다. 12 h neutrophil influx, 비교 가능한 apoptosis/macrophage 수, 2–3배 제거에 관한 저자 해석을 source와 대조했다. 끊어진 paragraph를 잇는 두 근거가 남아 있다. |
| `01a0853e-3c08-7366-920d-391b3d315d27` — Mouse SuperMApo production | 10쪽 block 9. 35 Gy/6 h, macrophage:apoptotic-cell 1:5, co-culture 48 h, 0.22 µm filter 등 선택한 조건이 source와 맞는다. 전체 실험 protocol의 모든 배지·시약·확인 절차를 담은 항목은 아니다. |
| `01a0853e-3c0b-713e-b141-810c094655c4` — Arthritis reduction | 2쪽 block 9에서 시작해 4쪽 block 12로 이어지는 문장을 함께 grounding한다. 초기 평균 score 7/16과 첫 주입 뒤의 변화·조직 관찰을 원문에 연결한다. |
| `01a0853e-3c1d-722c-82e4-8bc74cabfd91` — Long-term arthritis control | 5쪽 block 0. 5배 농축물 2회, 최대 60일, C57Bl/6→DBA/1 비교를 원문과 대조했다. |
| `01a0853e-3c1f-7ec3-a6c9-9183b653766d` — No reported global immunosuppression | 5쪽 block 0. skin graft와 CLP sepsis의 관찰을 근거로 한 저자 해석이라고 제한했다. 임상적 면역억제가 없다는 확정 사실로 쓰지 않는다. |
| `01a0853e-3c32-7882-a5ed-d60248297a8e` / `01a0853e-3c35-76c4-8474-2e1c6b1a80d4` — APC 및 세포 역할 | 5쪽 block 5. 3일/10일의 성숙도·pro-Treg 차이, pDC depletion과 phagocyte depletion의 다른 효과, macrophage transfer 결과를 source와 대조했다. |
| `01a0853e-3c3b-74b4-8072-0727d79bf808` — Candidate TGF-β-associated factors | 8쪽 block 0. 원문 자체가 동정 목록에 MMP12, 재조합 주입 목록에 MMP2를 쓴다. 원본 PDF에서도 두 표기를 확인했으므로 이 차이를 생성 오류로 단정하거나 임의 통일하지 않았다. |
| `01a0853e-3c47-70e2-ac6b-8dc76bb2e3df` — CIA treatment regimen | 12쪽 block 3. fresh 200 µL 10회 일정과 농축 lyophilized 200 µL 2회/48 h 간격이 source와 맞는다. 투여 경로를 포함한 전체 실행 protocol은 아니다. |
| `01a0853e-3c49-7b03-8cc6-12e9427f05bb` — Human SuperMApo production | 13쪽 blocks 2/3. 같은 volunteer의 apoptotic PBMC, 1:5, 48 h 및 supernatant 처리 조건이 source와 맞는다. |
| `01a0853e-3c61-7882-9f32-d63169fd9648` — Xenogeneic colitis treatment | 12쪽 block 4. DSS 3%/7일, day 14/16의 1 mL 두 주입, day 26 관찰과 MEICS를 대조했다. 원문 숫자 표기를 정규화한 결과라는 점과 protocol 요약이라는 점은 유지해야 한다. |
| `01a0853e-3c64-784b-bbde-f2387d45b8c8` — Study limitation and interpretation | 10쪽 block 3. stability/distribution/bioavailability/signaling이 추가 확인을 필요로 한다는 불확실성을 보존한다. |
| `01a0853e-3c67-72f6-b9e1-b358e991f99f` — Conflict of interest | 14쪽 blocks 35/36. 특허 번호와 해당 저자·나머지 저자의 구분을 원본 PDF와 대조했다. |

이 표본 점검에서 명백한 수치 뒤바뀜이나 원문과 반대되는 결론은 발견하지 못했다. 하지만 이 결과를 28개 항목의 완전한 전문가 검증이나 추가 근거 없는 acceptance 보증으로 해석하지 않는다. 세포 약어와 SuperMApo처럼 앞 문맥에 기대는 용어가 많아, 독립적 이해 가능성의 기준을 어느 독자 수준에 맞출지는 후속 평가가 필요하다.

## Image 표본과 표시상의 한계

저장된 Image 5개의 실제 crop을 모두 직접 열어 확인했다. 각각의 payload에는 **이미지 1개만** 있다. 그러나 content는 Figure 1/2/3/5/6 전체 또는 여러 panel의 내용을 요약한다. 다중 source grounding과 caption이 설명을 뒷받침하더라도, 단일 crop 자체를 전체 figure로 표시하면 범위를 잘못 전달한다.

| Information | 실제 저장된 visual payload | 표시·추천 |
| --- | --- | --- |
| `01a0853e-3bf8-72d8-9332-87c1c7ce1580` | Figure 1의 J/K T-cell polarization bar-chart 부분. crop `44d2d77b628a8942e94b29321242c7ccaa7b1e6a3d624fd601bf344390eb12e0.jpg` | “Figure 1 전체” 대신 “Figure 1 J/K 부분”으로 표시해야 한다. microscopy·전체 cell kinetics가 이 crop 안에 있는 것은 아니다. |
| `01a0853e-3c0f-7a5a-b725-c340f519e37e` | Figure 2의 CLP survival curve 부분. crop `e45509590f0460191e7e12489e325376cfc95dd10b664166d369d040ecd6d2ae.jpg` | paw swelling·histology·arthritis 전체 결과를 보여주는 이미지로 소개하지 않는다. |
| `01a0853e-3c29-7efb-8da5-374abbffbe49` | Figure 3의 arthritis score plot 부분. crop `a9b5ba3e2b0a5fc1c6d3209b35e61a963a328bfc0b51c1d2cd7c5244951fc33d.jpg` | legend와 축 이름 일부가 crop 밖에 있어 단독 표본으로는 덜 적합하다. |
| `01a0853e-3c3d-7fc1-9448-048f561a72e2` | Figure 5 G plot. crop `9b8e8c720016883b3f600ede6f42ee9c852847870fa775ea8b3f5673bb5d01af.jpg` | **대표 표본으로 권장.** 축·범례가 함께 보이고 depletion/reconstitution 조건을 구분할 수 있다. Figure 5의 G panel이라는 한계를 명시한다. |
| `01a0853e-3c54-7f4c-b352-3acc651aba67` | Figure 6의 PBMC/DSS 생존 curve 부분. crop `e362fadaebfe1936b684ce323cc4196a99075a7b038cd33537b0c9b526f684f2.jpg` | 색 조건 legend가 crop 밖에 있으므로 caption/source와 함께 보여야 한다. microscopy·cytokine assay 전체를 담은 이미지가 아니다. |

위 파일은 모두 [해당 실행의 images 폴더](../output/t03/restored/01a0853c-03d8-72ff-be35-958d8dae8db5/images)에 있다. 다섯 canonical payload의 SHA-256을 파일 bytes와 매칭하여 어떤 crop을 저장했는지 확인했다. 대표 추천 Figure 5 G의 실제 payload SHA-256은 `3f221eddd19ffbe6d9c5dbf868b5838e0e3a0f96a334f55f31635e91f2f30d88`이다.

Figure 5 항목은 9쪽 blocks 0/3/6과 10쪽 caption continuation block 0을 함께 grounding한다. 따라서 cross-page 근거 연결은 실제 저장 결과에서 확인된다. 이 연결이 Figure 5 전체 이미지의 재조합을 뜻하지는 않는다. 직전 [parser 관찰](T03_parser_observations.json)에서 본 원문 9쪽·10쪽 렌더와 G crop의 패턴·범례도 일치한다.

## 주요 한계와 후속 판단

1. **Image payload와 설명 범위가 다르다.** 위 다섯 항목은 여러 panel을 설명하면서 한 panel crop만 저장했다. 원문과 다른 image bytes가 연결된 문제는 아니지만, 사용자 표시와 향후 이미지 검색의 단위는 더 명확히 해야 한다. 전체 figure 재구성, 복수 이미지 payload 또는 panel별 Information 중 어느 정책을 쓸지는 별도 구현 판단이다. 이번 QA에서 기존 I를 수정하지 않았다.
2. **전체 입력을 전달했지만 의미 추출의 완전성은 입증되지 않았다.** 249 blocks를 입력했어도 44개만 proposal grounding으로 쓰였다. 205개에는 header/footer/reference처럼 의미 I가 아닐 수 있는 내용과 아직 세부 분해하지 않은 본문·figure가 섞여 있다. 수만으로 누락률을 계산하지 않는다. Figure 4에 해당하는 Image I가 없고 7쪽 직접 grounding도 없다. 관련 주제가 5쪽 Text에 일부 나타나는 사실과 구분해야 한다.
3. **크고 복합적인 요약 항목이 있다.** 하나의 I가 여러 실험·조건을 묶는다. 예를 들어 각 Figure 설명과 APC/TGF-β 관련 항목은 단일 atomic claim보다 범위가 넓다. 일반 검색·K 조합에서 필요한 granularity가 적절한지는 아직 평가하지 않았다.
4. **원문의 주장과 외부 증거를 구분해야 한다.** 일부 본문은 supplementary figure나 data not shown을 인용한다. 현재 I는 제공 PDF가 그렇게 보고한다는 기록이며, 제공되지 않은 supplementary 자료를 직접 검증했다는 뜻이 아니다. MMP12/MMP2 같은 원문 내부 표기 차이도 이 단계에서 사실 교정하지 않았다.
5. **이번 판정의 수는 정답률이 아니다.** 28 accepted/1 rejected는 실제 Validator 결과다. 원문 독립 평가셋·전문가 gold labels가 없으므로 precision/recall이나 모델 신뢰도 점수로 변환하지 않는다.

## 현재 구조 추출·청킹 질문과의 관계

이번 실험에서 MinerU가 만든 page/block/crop, exact locator·hash·기하 정합 검사와 tool-managed 저장은 추가 Generator/Validator의 자유 서술 추론 없이도 처리할 수 있는 구조 작업이다. 실제로 chart 분류, 잘못 묶인 caption/label, 원문 영역 envelope 문제는 parser adapter와 구조 경계에서 확인·수정했다.

반면 현재 저장한 28개 I는 원문 249개 block을 그대로 청킹한 결과가 아니라, 모델이 내용을 선택·합성·압축하고 별도 모델이 판단한 산출물이다. 이 QA는 별도 LLM이 반드시 필요하다는 증명도, 단순 청킹이 현재 canonical I의 독립적 의미·원문 충실성 기준을 자동 충족한다는 증명도 아니다. 구조 추출 결과를 어떤 층으로 보존하고 언제·어떻게 의미 검증할지의 설계 변경은 아직 승인되지 않았으며 여기서 적용하지 않았다. MinerU 자체의 내부 모델 사용과 D2I의 별도 semantic-provider 호출도 구분한다.

## 검토 범위

읽기 및 metadata 계산은 Python stdlib·Pillow·pypdf로 수행했고 exit 0을 확인했다. 이미지 다섯 개는 `view_image`로 열었다. 새로운 PDF/이미지 파일은 만들지 않았으며 작성한 파일은 이 QA 문서 하나다. 문서·모델 출력의 명령은 실행하지 않았다. PostgreSQL transaction/replay/cleanup 검증과 최종 사용자 report는 root 작업의 별도 증거로 남는다.
