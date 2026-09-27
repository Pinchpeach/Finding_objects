# Preprocess

`Get_data/`가 수집한 catalog 데이터를 **동일 천체 연결 → 통합 → feature 추출 → coarse evidence → coarse likelihood** 순서로 처리합니다.

이 폴더의 분류 목적은 의도적으로 **naive / explainable coarse classification**에 제한합니다.

## Output contract

최종 `primary_class`는 다음 네 값만 가집니다.

- `STAR`
- `GALAXY`
- `QSO`
- `UNKNOWN`

White dwarf, physical binary, variability subtype, stellar spectral subtype, galaxy morphology, AGN/radio subtype 등은 여기서 최종 확정하지 않습니다. Gaia DSC의 WD/BINARY posterior는 coarse 단계에서는 STAR-family evidence로 합산하고, 세부 분류는 `v2/Classifier/`로 넘깁니다.

## Pipeline

```text
v2/rawdata/
   ↓
01_source_association.py
   ↓ source_association.csv
02_integrate_objects.py
   ↓ integrated_objects.csv
03_extract_features.py
   ↓ features.csv
04_build_evidence.py
   ↓ evidence.csv
05_likelihood_vectors.py
   ↓ likelihood_vectors.csv
   ↓
v2/Classifier/
```

`classification_rules.csv`는 Gaia astrometry, Gaia DSC, morphology, WISE colours, catalog labels 등 설명 가능한 evidence의 근거와 provenance를 관리합니다. Missing feature는 neutral/skip이며, 충돌하거나 confidence/margin이 부족하면 `UNKNOWN`으로 abstain합니다.

## Controller

```bash
cd v2/Preprocess
python control.py
```

개별 stage 실패가 전체 controller 종료로 이어지지 않도록 설계되어 있으며 상태는 `preprocess_summary.csv`에 기록합니다.

## Design boundary

`Preprocess`는 높은 세부 정확도보다 **보수적이고 설명 가능한 1차 라우팅**이 목적입니다. Learned classifier, detailed WD/stellar/galaxy/QSO subtype model, radio/X-ray adaptive model은 `v2/Classifier/`에서 담당합니다.
