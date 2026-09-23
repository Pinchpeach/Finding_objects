# Preprocess

`Get_data/`가 수집한 catalog 데이터를 **동일 천체 연결 → 통합 → feature 추출 → evidence 생성 → likelihood vector** 순서로 처리합니다. 각 단계는 독립 실행 파일이며 `control.py`가 전체 파이프라인을 관리합니다.

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
```

`classification_rules.csv`는 분류 rule의 근거와 provenance를 관리합니다. 문헌/카탈로그 기준과 프로젝트에서 추후 calibration할 기준을 구분하며, Stage 4는 최종 class를 확정하지 않고 rule별 evidence를 보존합니다.

## Controller

```bash
cd v2/Preprocess
python control.py
```

개별 stage가 실패하거나 기대 출력이 생성되지 않아도 controller 자체는 종료하지 않고 다음 stage를 시도하며, 상태를 `preprocess_summary.csv`에 기록합니다. 따라서 일부 catalog 값이 없거나 한 단계가 실패해도 전체 실행 기록은 남습니다.

## 현재 상태

Stage 4/5에는 classification-rule v1 로직이 연결되어 있습니다. Gaia astrometry, Gaia DSC posterior, SDSS spectral class를 evidence로 보존하고 primary vector `STAR / WD / GALAXY / QSO / BINARY`를 생성합니다.

Stage 1~3은 아직 scientific association/feature engineering의 scaffold입니다. 특히 Stage 1의 positional uncertainty, PSF/resolution, source-density 기반 association calibration과 Stage 2의 실제 one-object-per-row wide merge는 후속 구현 대상입니다.

## 원칙

- 한 천체당 최종 한 행을 목표로 합니다.
- 원본 catalog identifier와 provenance를 보존합니다.
- ambiguous counterpart를 강제로 합치지 않습니다.
- missing feature는 neutral/skip 처리합니다.
- 상충하는 evidence는 삭제하지 않고 기록합니다.
- 임의 threshold와 문헌 기반 threshold를 구분합니다.
