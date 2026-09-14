# Synthetic fixture recipes

모든 데이터는 설계 검증용 가상 label입니다. 실제 논문·개인 데이터·API key가 없습니다. JSON은 생성 레시피/시나리오이며 완성된 production DTO가 아닙니다. AT01의 100001은 cap 검증용 sample size이지 production 상한이 아닙니다. 각 파일의 tests ID를 acceptance catalog와 연결해 Codex가 approved schema의 실제 fixture로 변환해야 합니다.


## CLI / MinerU 추가 fixtures

S09는 headless CLI contract, S10은 내부 normalized adapter view, S11은 parser 실패/재시도, S12는 naming migration의 합성 시나리오다. S10은 MinerU가 실제 생성한 raw output이 아니며 특정 release와 호환된다는 증거가 아니다. 실제 MinerU PDF sample/output은 T03에서 검증된 profile로 생성하여 별도 보존한다.
