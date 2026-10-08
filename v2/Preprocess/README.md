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

### Stage 동작 요약 (2026-10-08 갱신)

- **Stage 2**: 모든 raw field를 `<catalog>__<field>` namespace로 저장합니다(접두어 없는 이름은 legacy 호환용, 먼저 들어온 값). Stage 3/4 규칙은 자기 카탈로그의 namespaced field만 읽습니다.
- **Stage 2**: SGA-2020 큰 은하 타원(D26, PA, b/a) 안에 있는 검출은 `host_large_galaxy`, `host_elliptical_radius`(D26 장반경 단위)로 표시합니다.
- **Stage 4**: 점광원 형태(PS1 PSF−Kron, SDSS `type=6`, Legacy Surveys `PSF`)는 `POINT_SOURCE` evidence이며 STAR와 QSO를 똑같이 지지합니다. 외부은하 evidence(`EXTRAGALACTIC`)는 GALAXY와 QSO를 지지합니다.
- **Stage 5**: 선형 log-odds 융합입니다. `fusion_weights.json`이 있으면 벤치마크 **train** split에서 학습한 규칙별 가중치와, **calibration** split에서 정한 abstention 임계값을 씁니다. 학습 데이터가 없는 evidence(Gaia DSC, SIMBAD, NED 등)는 기존 prior 가중치를 그대로 씁니다. 큰 은하 타원 안(`host_elliptical_radius < 1`)에서는 Gaia 시차/고유운동으로 확인된 전경 별이 아니면 `WITHIN_LARGE_GALAXY`로 abstain합니다.
- **색 공간 kNN** (`color_knn.py`, 규칙 `LS-CKNN-001`/`PS1-CKNN-001`): 같은 색 조합으로 측정된 train split 벤치마크 천체 중 가장 가까운 31개의 클래스 비율을 증거로 씁니다. 참조 집합은 `color_reference.csv.gz`이고 `v2/benchmark/build_color_reference.py`로 다시 만듭니다.
- 증거 신뢰도(카탈로그 품질 × 연관 사후확률)는 `신뢰도 × logit(점수)`로 반영합니다. 신뢰도가 낮으면 증거가 약해질 뿐 반대 방향 증거가 되지는 않습니다. 학습 가중치가 없는 규칙은 지지 방향으로만 반영합니다.
- 필드 클래스 사전확률 EM 보정은 추정치만 기록하고, 적용은 `--field-prior`를 줄 때만 합니다(근거: `COARSE_BENCHMARK_RESULTS.md`).
- 가중치 재학습(현재 설정): `python v2/benchmark/fit_fusion_weights.py --truth v2/benchmark/truth_data/ground_truth.csv v2/benchmark/desi_external/truth.csv --catalog-root v2/benchmark/catalog_features v2/benchmark/desi_external/catalog_features --manifest <sdss manifest> <desi manifest> --augment-drop LS-MORPH,PS1-MORPH,SDSS-PHOTO LS- --augment-weight 0.3 --target-scope each --target-accuracy 0.925`. 결과와 한계는 `COARSE_BENCHMARK_RESULTS.md`에 있습니다.

## Controller

```bash
cd v2/Preprocess
python control.py
```

개별 stage 실패가 전체 controller 종료로 이어지지 않도록 설계되어 있으며 상태는 `preprocess_summary.csv`에 기록합니다.

## Design boundary

`Preprocess`는 높은 세부 정확도보다 **보수적이고 설명 가능한 1차 라우팅**이 목적입니다. Stage 5의 학습 가중치는 규칙 하나당 계수 하나인 선형 모델이라 각 규칙의 기여를 그대로 읽을 수 있습니다. Learned classifier, detailed WD/stellar/galaxy/QSO subtype model, radio/X-ray adaptive model은 `v2/Classifier/`에서 담당합니다.
