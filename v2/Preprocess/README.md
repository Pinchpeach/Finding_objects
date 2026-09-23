# Preprocess

`Get_data/`에서 수집한 여러 카탈로그의 광원을 비교하여 같은 천체에서 나온 관측인지 판단하고, 하나의 대상이 가진 특성으로 정리하는 코드를 두는 폴더입니다.

## 역할

- 서로 다른 catalog/survey의 광원 위치(RA, Dec)를 비교합니다.
- 단순 최근접 거리만으로 확정하지 않고, 이후 positional uncertainty, survey resolution/PSF, source density 등 필요한 정보를 함께 사용할 수 있도록 설계합니다.
- 같은 출처로 판단된 관측값을 하나의 천체 record로 통합합니다.
- 어떤 catalog의 어떤 source가 통합되었는지 추적할 수 있도록 원본 identifier와 provenance를 보존합니다.
- 애매한 counterpart는 억지로 하나의 대상으로 합치지 않고 이후 검증할 수 있도록 남깁니다.

## 정리된 CSV의 기본 구조

최종적으로 **천체 하나당 한 행(row)** 을 사용합니다.

```text
object_name,ra,dec,<other properties...>
```

- `object_name`: 카탈로그에서 가져온 천체 이름 또는 식별자
- `ra`: 대상의 적경
- `dec`: 대상의 적위
- `<other properties...>`: 측광, 분광, astrometry, survey별 식별자 등 해당 대상에서 확보한 특성

같은 대상에 여러 catalog identifier가 존재할 수 있으므로 대표 `object_name`과 함께 원본 catalog identifier들을 별도 특성으로 보존할 수 있게 확장합니다.

데이터 흐름:

`Get_data raw catalogs -> positional/counterpart comparison -> same-object grouping -> one object per CSV row`
