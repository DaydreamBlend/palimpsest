# T03 — MinerU Hybrid 원문 근거와 읽기 projection

2026-09-10 사용자 후속 승인: 병합 전 페이지·span 근거를 보존하고 페이지를 넘는 문단은 조회·LLM 입력 projection으로 제공한다. 비교한 MinerU 중 Hybrid + Pro2605 1.2B high를 사용해 PDF 글꼴·텍스트 span 소제목 후보, 패널/전체 Figure/페이지 이미지, PDF 텍스트와 parser 전사의 불일치 검출을 구현·시험한다.

## 관찰 가능한 완료 동작

CLI에서 고정된 MinerU Hybrid 실행과 원본 PDF를 지정하면 원문 페이지·영역·문자·raw locator를 추적하는 읽기 자료와 JSON을 만든다. 원본/파서 전사를 각각 보존하며 소제목 후보와 전사 불일치는 별도 projection이다. 페이지를 넘는 문단은 원래 페이지와 span을 되찾을 수 있는 매핑을 가진다. Test_Paper 6개 Figure와 추가 3편을 실제 자료로 대조한다. 이 단계에서 I2K나 semantic LLM을 실행하지 않는다.

## 현재 구현과 책임

- `mineru_adapter.py`는 기존 cross-page 표시가 있을 때만 preproc를 선택한다. 새 versioned Hybrid profile은 모든 페이지의 preproc를 명시적으로 요구하고 과거 profile 결과는 유지한다.
- 기존 `tools/run_d2i.py`·Compiler Runtime·source-unit assembly·CLI를 재사용한다. Hybrid Docker runner만 기존 실험 코드에서 제품 경로로 연결하고 exact image/model/config를 확인한다.
- `pdf_text_evidence.py`는 native PDF span 추출, font 기반 후보와 양쪽 전사의 보수적 비교를 맡는다.
- `pdf_visual_evidence.py`는 원본 페이지 렌더, 원본 패널 근거 및 전체 Figure 영역 제안을 맡는다.
- 공통 읽기 projection/CLI는 위 결과와 exact source ref를 결합한다. DB schema/domain 변경이나 빈 미래 모듈은 없다.

Python/Docker, U01–U11, T03·PLANS·CODE_REVIEW·원문 보존 및 기존 parser follow-up을 읽었다. 최신 사용자 지시가 새 MinerU 선택에 우선하며 별도 날짜 부록에 기록한다. P 제안 전체를 승인하지 않고 source/canonical snapshot·과거 I/Record/ID/hash는 보존한다. 현재 코드의 작업 전 bytes는 `output/t03-pdf-evidence/baseline/`에 보존했다.

## 순서와 검증

1. 새 선택/범위를 문서에 기록하고 기존 코드와 raw 실행을 확인한다.
2. 서로 독립된 runtime, PDF text, PDF visual 모듈을 구현한다. root가 결합 CLI/paragraph projection·공유 계약을 소유한다.
3. 기존 Pro 4편 43페이지 raw를 hash 확인 후 재사용하여 추가 script 결과를 만든다. 기존 평가 oracle을 새 알고리즘의 입력으로 사용하지 않는다.
4. inline 제목, 원래 페이지 보존, 중복 span, 애매한 그림 경계, 전사 차이, 좌표/경로 오류를 실제 작은 회귀 검사로 확인한다. 새 동작의 real PDF 품질과 구조 검사를 구분한다.
5. 필요 시 격리 PostgreSQL 18 프로젝트에서 Hybrid source 저장·재시도·조회만 확인한다. 사용자 개발 DB에 시험 쓰기를 하지 않는다.
6. 실제 Figure/불일치 QA, 앱 회귀·문서 검사, 변경 파일 검토와 작업 소유 Docker 정리를 완료하고 보고한다.

완료 기준은 이번 보완 slice다. T03의 native/scanned/mixed 전체 gate 및 AT22/23/25/27/33/36/68/69/71/76/77/81/83/85/90–102/104/105/107/111/112를 일괄 pass로 바꾸지 않는다. known crop/transcription 오류와 OCR 없는 native text 부재를 숨기지 않는다. 실패/명령/해시·실측 수치는 수행하면서 누적한다.

## 진행

- 이번 보완 slice 완료. raw PDF와 모델은 로컬 읽기 전용이며 원문 업로드 없음. [실제 결과](T03_pdf_evidence_result.md)와 [기계 판독 결과](T03_pdf_evidence_result.json)에 실측·명령·파일 hash를 기록한다.
- rollback은 새 profile/projection의 사용을 중단하는 방식이다. 이전 profile과 실행 산출물은 남기며 canonical 이력을 되돌려 쓰지 않는다.

## 실행·검토의 최종 상태

1. 새 Hybrid profile/runner와 명시적인 preproc normalizer, native text/visual 및 paragraph/evidence 모듈을 구현했다. CLI는 기존 application service를 재사용하고 source I 저장과 읽기 projection 생성은 별도다.
2. 고정 Pro raw 4편43페이지의 native text·소제목·전사 차이와 이미지·문단을 생성했다. PDFium의 raw FontSize/CTM과 numeric weight가 실제 font style과 다른 반례를 수정했다. 후보 알고리즘 고정 후 이전 annotation을 대조한 결과 기존 누락39개 중 정확한 후보32개다. 전체 제목/계층 승격이나 후보 precision 완료로 해석하지 않는다.
3. Test_Paper 새 GPU 파싱은216.355초이며 source229I(Text193/Image36)를 격리 PG18에 저장했다. 초기 GPU UUID 접두사 차이의 실패기록을 남기고 같은 GPU 표기 정규화만 수정했다. 완료작업 재생의 job/I/events 동일, 중복Data새요청exit6, 원래14페이지조회와raw66파일exactexport를 검증했다.
4. 전체Figure6·페이지14·원시이미지영역36의 시각 QA를 최종a3 패키지에 결속했다. 모든 패키지에서 문단segment3900/원래page/bbox/hash/offset을 대조했고 문단밖204segment는discarded_blocks에 남아있다. 원문 의미를 자동 교정하지 않았다.
5. 독립 코드 검토의 Data/receipt/middle 연결, path alias, 문단 display asset, 조기완료표식 문제를 재현·수정했다. 원자적 manifest 게시 실패 검사 첫 Windows 실행에서 read-only descriptor fsync가 실패해 r+b로 고쳤고 통과했다. a3 producer bytes/hash는 수정하지 않고 마지막 reader 검증 강화 hash를 별도로 기록했다.
6. 최초233개 앱검사는 runner COPY 누락으로1실패(skip8)였고 수정 후237개·241개 최종회귀가 통과했다. 최종241tests/26.205초/exit0, native library19tests/0.298초/exit0(skip0), 문서도구44tests/221.099초/exit0다. `runtime/app-tests-final-a2.log`, `native-tests-final-a2.log`, `document-tests.log`에 원출력을 남겼다. 문서 fixture의 임시 baseline `.md`는 원래 bytes를 `.md.snapshot`으로 보존하여 잘못된 상대 링크 검사만 피했으며 validator를 완화하지 않았다.
7. `docker compose -p palimpsest-t03-evidence-verify down`(no `-v`)으로 전용컨테이너3개·network1개를 정리했다. 이전 중간 앱image ID는 모두 이미 존재하지 않아 추가image삭제는0이며 최종workingimage를 남겼다. 원래7컨테이너와 전체volume/image 대조는 최종 cleanup receipt를 따른다.
8. 최종 `python tools/validate_bundle.py` exit0/오류0. 정리 후 기존7컨테이너·12image ID·23기존volume과4시험volume을 보존했고 최종앱image만 추가됐다. 작업전86개baseline파일hash가 그대로임을 확인했다. 실행 전후 통계와 전체 변경 경로는 result/changes/cleanup receipt로 연결한다.

승인 대기 blocker는 없다. 이번 native PDF 보완의 검증을 T03 전체 AT 완료로 올리지 않는다. 남은 제목7개·복잡한Figure경계·scanned/mixed·회전좌표·문단의 의미적 연결 및 후속I2K는 결과 문서의 한계를 따른다. 현재 정책·raw원문·SQL migration·과거 I/Record의 불변성은 유지한다.

## 이후 승인과 현재 기본값

사용자의 이후 지시로 MinerU 원본 PDF auto + 200 DPI 이미지 OCR 이중 전사를 신규 기본값에 적용했다. 일반 문자 native/특수문자 OCR 우선의 새 선택 I와 양쪽 원시 근거를 보존한다. [후속 승인](../docs/decisions/MINERU_DUAL_TRANSCRIPTION.md), [실행 계획](T03_paddle200_execplan.md), [최종 구현·실물 PG·evidence 검증](T03_dual_transcription_result.md)을 따른다. 위 단독 Hybrid 수치와 산출물은 해당 시점의 이력으로 남긴다.
