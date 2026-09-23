# Get_data

천문 카탈로그와 survey에서 원본 관측 데이터를 가져오는 코드를 두는 폴더입니다.

## 역할

- 지정한 하늘 영역 또는 대상에 대해 카탈로그를 조회합니다.
- 각 카탈로그가 제공하는 원본 식별자, 천구좌표(RA, Dec), 측광값, 분광 정보와 기타 메타데이터를 가능한 한 원형 그대로 수집합니다.
- 어떤 survey/catalog에서 얻은 값인지 provenance를 보존합니다.
- 이 단계에서는 서로 다른 카탈로그의 광원이 같은 천체인지 최종 판단하지 않습니다. 그 판단은 `Preprocess/`에서 수행합니다.

## 출력 원칙

후속 처리에서 원본 정보를 잃지 않도록 catalog별 결과를 분리해 저장하는 것을 기본으로 합니다. 카탈로그의 object name/identifier와 RA, Dec는 반드시 보존합니다.

데이터 흐름:

`Catalog / Survey -> Get_data -> raw catalog data -> Preprocess`
