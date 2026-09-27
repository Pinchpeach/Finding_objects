# Gaia XP white-dwarf subtype external validation

## Purpose

Test whether the LAMOST-trained Gaia XP DA/DB classifier generalizes across a
spectroscopic-survey domain shift.

Training/calibration domain:
- LAMOST DR5 visually classified white dwarfs from Guo et al. (2022)
- Gaia DR3 XP continuous coefficients as model inputs
- 118 DA + 110 DB with XP data
- training rows: 128
- calibration rows: 50

Independent external domain:
- SDSS DR14 white-dwarf catalogue from Kepler et al. (2019)
- exact pure DA/DB labels only
- g-band spectral S/N >= 10
- objects within 2 arcsec of the LAMOST subtype truth removed
- Gaia XP coefficients are the only model inputs

## Full external run

GitHub Actions run: **36304882268**

The requested external truth was 200 DA + 200 DB before Gaia/XP availability
filtering. The final XP-available independent sample was:

- total: **213**
- DA: **114**
- DB: **99**
- XP features: **110** (55 BP + 55 RP continuous coefficients)

### Ungated model performance

- accuracy: **95.31%**
- balanced accuracy: **95.28%**
- macro-F1: **95.28%**
- DB precision: **94.95%**
- DB recall: **94.95%**
- DB F1: **94.95%**
- log loss: **0.1799**

Confusion matrix:

| truth \ prediction | DA | DB |
|---|---:|---:|
| DA | 109 | 5 |
| DB | 5 | 94 |

The cross-survey external result is close to the earlier held-out LAMOST result
(96% accuracy), indicating that the Gaia-XP signal is not merely memorizing a
single spectroscopy-survey domain.

## Conservative selective classification

The production-oriented rule is to output a subtype only when the calibrated
model is sufficiently confident; otherwise return `UNRESOLVED`.

Fixed confidence operating points on the untouched SDSS external set:

| minimum max probability | coverage | classified rows | accuracy | balanced accuracy |
|---|---:|---:|---:|---:|
| 0.80 | 76.06% | 162 | 99.38% | 99.44% |
| 0.90 | **60.09%** | **128** | **100.00%** | **100.00%** |
| 0.95 | 34.74% | 74 | 100.00% | 100.00% |

The 0.90 threshold was not tuned on the SDSS labels; it is a fixed conservative
confidence gate evaluated after the external predictions were produced.

A second compact high-S/N run (GitHub Actions **36305684125**) gave:
- external XP rows: 105 (55 DA, 50 DB)
- ungated accuracy: 97.14%
- p >= 0.90: 65 rows, 98.46% accuracy
- p >= 0.95: 40 rows, 100% accuracy

This smaller result is directionally consistent but the 213-row full run is the
primary external benchmark.

## Decision

DA/DB output can move from a pure prototype to a **gated experimental inference
path**:

1. The object must already be routed as a white-dwarf candidate.
2. Gaia XP continuous coefficients must be available.
3. The DA/DB model must return max calibrated probability >= **0.90**.
4. Otherwise the subtype remains `UNRESOLVED`.
5. Unsupported WD types (DC, DQ, DZ, DO, magnetic, hybrid, WD+MS, etc.) must not
   be forced into DA/DB by the production routing layer.

The last point is important: this benchmark contains only pure DA and DB truth.
A high DA/DB probability is meaningful only after the object has passed the
white-dwarf-candidate route and the subtype task is explicitly limited to the
currently supported label space.

## Remaining limitations

- External XP coverage is incomplete, so many WDs cannot enter this path.
- Only two WD subtypes are currently supported.
- The training sample is modest (228 XP-available LAMOST objects).
- Rare and composite WD classes need explicit out-of-distribution / unsupported
  class handling before a broader multiclass deployment.
- The 100% accuracy at p>=0.90 is based on 128 external objects and should not be
  interpreted as a universal error-free guarantee.

## Reproducibility

Primary external workflow:
- run: **36304882268**
- artifact: `wd-subtype-xp-external-eval`

Compact confirmation:
- run: **36305684125**

Key code:
- `build_sdss_wd_subtype_external_truth.py`
- `collect_star_gaia.py`
- `collect_gaia_xp_coefficients.py`
- `validate_wd_subtype_xp_external.py`
- `.github/workflows/validate-wd-subtype-xp-external.yml`


## Reproducible deploy model

A deployable model is generated from the validated LAMOST XP data without
committing a binary model file into Git.

Workflow:
- **Build WD Subtype Gaia XP Model**
- successful run: **36306249028**
- artifact: `wd-subtype-xp-deploy-model`
- retention: 90 days

For deployment fitting, the deterministic calibration partition remains held
out for sigmoid calibration and all other LAMOST XP rows are used to fit the
Random Forest base model.

Re-evaluation of this deploy artifact on the untouched 213-row SDSS external XP
set:

- ungated accuracy: **95.77%**
- p >= 0.90 classified rows: **124 / 213 (58.22%)**
- p >= 0.90 accuracy: **100.00%**
- p >= 0.90 balanced accuracy: **100.00%**

The STAR routing branch now accepts DA/DB output only when:
- the object is independently a `WHITE_DWARF_CANDIDATE`,
- an externally validated XP model provides `DA` or `DB`, and
- calibrated subtype confidence is >= **0.90**.

Otherwise `spectral_type` remains `UNRESOLVED`.

Implementation:
- `fit_wd_subtype_xp_model.py`
- `apply_wd_subtype_xp.py`
- `branches/star.py`
- `.github/workflows/build-wd-subtype-xp-model.yml`
