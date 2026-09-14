# T03 — 현재 방식의 추가 논문 평가

2026-09-10 사용자 요청: 현재 방식을 유지하고 더 많은 논문으로 성공률을 확인한다. MinerU3.4.5 Hybrid high + Pro2605 1.2B, native font/span 후보·전체Figure/페이지·전사차이·문단 projection의 현재 구현을 고정한다. 이미지 전용 OCR 전환·튜닝·모델 변경·I2K 이후 실행은 하지 않는다.

## 자료와 분모

승인된 Desktop/졸업논문 참고문헌 폴더의 PDF21개를 raw SHA로 조사했다. 이전 Nassar/Torchinsky/Wallet3개 및 논문이 아닌 MCM 제조 프로토콜1개를 제외한 **17편243페이지**를 모두 포함한다. Test_Paper는 기존 코호트로 별도다. Chen 두 파일은 다른 제목의 논문이며 같은 bytes가 아니다. HMGB1.pdf는 실제 학술논문임을 원본 첫 페이지에서 확인해 포함한다. 파서 성공 여부를 보고 표본을 바꾸지 않는다. 전후 비교 코호트4편은 확대 코호트의 성공률에 합산하지 않는다.

17편 전체의 parser/원문구조/조회package 성공률을 각각 측정한다. 각 문서의 첫·중간(floor((N-1)/2)+1)·마지막 물리 페이지, 총51페이지를 미리 정해 소제목·Figure·전사 표본의 원문 품질을 평가한다. native text가 있다고 정확한 텍스트층이라고 가정하지 않는다. corpus는 생의학 논문이며 일반 PDF 모집단의 성공률로 확대하지 않는다.

## 진행 순서와 책임

1. 원본 SHA/geometry/페이지수와 고정 평가 페이지를 inventory한다. 원본만으로 만든 페이지렌더와 native text를 annotator에게 제공한다.
2. production/profile/소제목·visual·paragraph/evidence 코드 hash를 동결한다. 두GPU(RTX5080/RTX4060Ti)는 같은 모델·engine·parsing옵션을 사용하되 GPU UUID를 별도 profile에 기록한다. 기존 image/모델을 그대로 사용한다.
3. 원본만 보는 두 독립 담당자가 선정51페이지의 명확한 제목, 번호가 있는Figure 영역, 페이지당 전사표본1개를 기록한다. 원문 annotation 동결 전 파서결과를 보지 않는다. 이 평가는 Codex 시각검토이며 독립 인간gold가 아니다.
4. production runner를 직접호출해 각 PDF전체를 로컬파싱한다. DB없는 실험경로에서 production source-unit build/verify를 호출해 원문I제안까지검증한다. DB등록/commit성공률로표현하지않는다. 실제PG저장·재실행검증은 이전Test_Paper기록과구분한다.
5. 같은 현재코드로 native evidence를 생성하고 source/receipt/hash/page/block/leaf/asset/context결합을검사한다. 실패한문서는분모에남기며원인과산출물을보존한다. 실패때fallback하거나예외를완화해성공시키지않는다.
6. 소제목 exact/contains recall과 sampled precision, Figure 존재/전체crop보존(애매한경계별도), 전사표본 exact/문자차이를분리한다. 전체페이지fallback제공을독립Figurecrop성공으로세지않는다. 전사 discrepancy 수를확정오류수로세지않는다.
7. 결과·분모·명령·실패·품질한계·실행시간과코드불변을보고한다. 이번실험컨테이너를정리하고기존서비스·볼륨·모델·raw/history를보존한다.

## 운영 경계와 검사

Python/Docker, CLI-first, U01–U11과 최신Hybrid선택, PLANS/T03/CODE_REVIEW를따른다. source PDF/model/profile는readonly, 추론networknone이다. 새코드는실험batch/평가스크립트만 output/t03-expanded-papers에두며제품모듈·schema·migration·기존canonical텍스트와UUID/hash를변경하지않는다. 공유DB를사용하지않는다.

실험harness는기존Test_Paper에대한읽기전용source검증과실패입력검사로확인한다. 앱코드변경이없으면기존전체앱시험을불필요하게반복하지않는다. 문서bundle검사를최종수행하고raw프로파일및코드hash를재검증한다. T03의AT22/23/25/27/33/36/68/69/71/76/77/81/83/85/90–102/104/105/107/111/112는해당실물범위의추가근거일뿐일괄완료로표시하지않는다. T03전체는in_progress다.

## 진행

- inventory완료:17편243페이지,고정시각검토51페이지. 제조프로토콜및기존3논문은별도기록.
- production 32개 파일·두 GPU profile·inventory와 평가 규칙을 동결했다. 모든 새 실행은 같은 Hybrid high/Pro2605/Transformers/auto 설정을 사용한다.
- 기존 Test_Paper에 대한 DB 없는 source verifier selfcheck가 통과했다: 14페이지, source 제안229개, raw leaf1,147개, 보존파일66개. 동일 output 디렉터리에 재실행하면 기존 결과를 덮어쓰지 않고 거부하는 것도 확인했다.
- 전체17편 GPU batch와 source/evidence 후처리를 실행 중이다. 원문 annotation A는 24페이지·명확한 heading28개·Figure10개·전사24개를 결과 관찰 전에 고정했다. annotation B와 실제 crop 시각 검토는 진행 중이다.
- 새로운 source 제안의 구조 검증과 기존 PG 저장 검증은 구분한다. 이번 코호트의 canonical 쓰기와 application semantic LLM 호출은 0이다. 승인 대기 없음.

## 최종 실행 결과

- 전체 batch와 후처리 종료(exit0). 새17편243페이지의 parser/source 검증은 모두 통과했다. Source 제안2,834개(Text2,599/Image235), raw leaf18,537개와 retained files932개를 확인했다. Source 검증 통과는 PDF 인식 정확도 승인이 아니다.
- Native/visual/paragraph package와 모든 페이지 context 조회는16/17이다. Manfredi의3/5/7페이지 CropBox가 effective bbox보다 커서 `unsupported_pdf_geometry`로 거부됐다(evidence CLI exit4). 파서/source 제안 및 모든 raw는 보존했다. 규칙 완화나 fallback 없이 실패를 분모에 남겼다.
- 두 원본 oracle의51페이지/제목74개/Figure19개/전사51개를 동결했고, Figure 최종 시각 검토는16complete·2association missing·1missing evidence·pending0이다. 옆 caption인 Clarke/Piccinini는 parser 이미지 누락이 아니라 projection 연결 실패다.
- 최종 채점은state complete, pending0, failed document paper12, changing inputs0이다. Native 제목25/74 exact·36/74 contains·precision25/168, parser 제목48/74 exact·50/74 contains다. Parser 전사32/51 exact·최소편집거리49/7,812이며 수식/직렬화 차이와 과학 glyph 오류를 별도 검토한다.
- Scorer의 최소 substring 거리는225개 독립 brute-force 경우 및6개 정규화/누락/geometry 검사로 확인했고 독립 검토에서도 수정할 결함이 없었다. 전체 앱 suite는 production 코드가 바뀌지 않아 재실행하지 않았다.
- 최종 read-only audit에서 원본17개·고정 implementation32개·평가파일3개·원본oracle2개, 총54개 hash 불변과 Docker 기존 컨테이너7/이미지13/볼륨27의 동일성을 확인했다. 새 이미지0·실험컨테이너 잔여0, 기존 모델·볼륨·raw·서비스 유지.
- [상세 결과](T03_expanded_papers_result.md)와 [JSON](T03_expanded_papers_result.json)에 분모·실패·한계·명령을 기록했다. 위 진행 중 문장은 당시 단계 기록이다. 이번 추가 평가를 완료하고 T03 전체는in_progress, T04 이후는미실행 상태를 유지한다.
- 최종 문서 bundle 검사 PASSED/exit0. 전사 불일치19건도 전체 검토해 줄바꿈10·공유 문자 대체5·수식3·accent1로 설명하고 점수는 바꾸지 않았다. 독립 보고서 대조에서 숫자·분모·시간과 참조파일61개 hash에 불일치가 없었다. 추가 원문/코드/모델 수정 없이 평가를 종료한다.
