# rawdata

`v2/Get_data/`의 각 catalog collector가 내려받은 **원본 조회 결과**를 저장합니다.

- 가능한 한 좁은 cone-search 영역으로 테스트합니다.
- catalog별 CSV를 분리해 저장합니다.
- cross-match, 분류, 보정으로 원본 값을 덮어쓰지 않습니다.
- 동일 catalog ID가 중복되면 collector 단계에서 마지막 행을 유지합니다.
- 후속 동일천체 판정과 통합은 `v2/Preprocess/`에서 수행합니다.

권장 파일명: `<catalog>_<ra>_<dec>_<radius_arcmin>.csv`
