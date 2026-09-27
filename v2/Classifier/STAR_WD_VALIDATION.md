# STAR branch: WHITE_DWARF vs NORMAL_STAR validation

## Goal

Validate the first detailed STAR-branch classifier after coarse routing.

Task:
- WHITE_DWARF
- NORMAL_STAR

Truth labels come from clean SDSS DR18 spectroscopy
(`sciencePrimary=1`, `zWarning=0`). Spectroscopic class/subclass fields are
used only as truth metadata and are not model features.

## Dataset

- Initial spectroscopy truth: **1,000**
- Gaia DR3 matches within 2 arcsec: **974 (97.4%)**
- WHITE_DWARF: **489**
- NORMAL_STAR: **485**
- Train: **581**
- Calibration: **199**
- Test: **194**
  - NORMAL_STAR: **91**
  - WHITE_DWARF: **103**

The learned model uses Gaia DR3 astrometry/photometry only, including parallax,
proper motion, RUWE, G/BP/RP photometry, colours, absolute G where available,
and explicit missing-value indicators.

## Interpretable literature baseline

Baseline:
`M_G > 6 + 5(BP-RP)` and `parallax_over_error > 1`

This is the broad Gaia white-dwarf HR-diagram selection from Gentile Fusillo
et al. (2021), used here as an interpretable comparison rather than a complete
implementation of their full catalogue-quality selection.

Full test-set result:
- Accuracy: **91.75%**
- Balanced accuracy: **92.10%**
- WD precision: **97.80%**
- WD recall: **86.41%**
- WD F1: **91.75%**

Confusion matrix:

| truth \ prediction | NORMAL_STAR | WHITE_DWARF |
|---|---:|---:|
| NORMAL_STAR | 89 | 2 |
| WHITE_DWARF | 14 | 89 |

Only **157/194 (80.9%)** test objects had all measurements required to apply the
HR baseline directly. For full-coverage scoring, unusable baseline cases default
to NORMAL_STAR.

On the 157 directly usable objects only:
- Baseline accuracy: **96.82%**
- Baseline balanced accuracy: **96.83%**
- Baseline WD F1: **97.27%**

## Learned Gaia classifier

Model:
- HistGradientBoosting
- held-out sigmoid probability calibration
- NaN-aware training
- 31 Gaia-derived / missingness features
- no spectroscopy inputs

Full test-set result:
- Accuracy: **94.33%**
- Balanced accuracy: **94.47%**
- Macro-F1: **94.32%**
- WD precision: **96.94%**
- WD recall: **92.23%**
- WD F1: **94.53%**
- Log loss: **0.1426**
- WD Brier score: **0.0402**

Confusion matrix:

| truth \ prediction | NORMAL_STAR | WHITE_DWARF |
|---|---:|---:|
| NORMAL_STAR | 88 | 3 |
| WHITE_DWARF | 8 | 95 |

On exactly the same 157 objects where the HR baseline is directly usable:
- Learned accuracy: **98.73%**
- Learned balanced accuracy: **98.69%**
- Learned macro-F1: **98.69%**

## Interpretation

Compared with the full-coverage HR baseline, the learned model:
- raises accuracy by **2.58 percentage points**
- raises WD recall by **5.83 percentage points**
- raises WD F1 by **2.78 percentage points**
- reduces WD false negatives from **14 to 8**
- increases NORMAL_STAR false positives slightly from **2 to 3**

The main benefit is therefore improved WD completeness/recall at a small cost in
purity/precision. The learned model also remains better on the common
baseline-usable subset, so the gain is not solely due to native missing-value
handling.

## Decision

Keep the learned WD model as an **experimental STAR-branch candidate**, not yet
as an unconditional production replacement.

Reasons:
1. The current truth set is only about 1,000 objects.
2. The SDSS query is deterministic and not yet explicitly stratified by sky,
   magnitude, temperature, or survey selection.
3. The current positive truth is a broad SDSS WD subclass and does not validate
   detailed DA/DB/DC/DQ/DZ/etc. spectral typing.
4. Independent external validation is still required before deployment.

The current production-safe STAR branch therefore continues to expose
`WHITE_DWARF_CANDIDATE` conservatively, while this learned model is the next
candidate for integration after a larger, spatially/magnitude-diverse benchmark.

## Literature basis

- Gentile Fusillo et al. (2021), MNRAS 508, 3877:
  Gaia EDR3 white-dwarf candidate catalogue and HR-diagram selection.
- Vincent et al. (2023), MNRAS 521, 760:
  modular Gaia+SDSS white-dwarf candidate and spectral-classification pipeline.
- García-Zamora et al. (2023), A&A 679, A127:
  Gaia spectral-coefficient Random Forest white-dwarf classification.

## Reproducibility

Validated GitHub Actions run: **36295747956**

Key implementation:
- `v2/Classifier/collect_star_gaia.py`
- `v2/Classifier/train_validate_star_wd.py`
- `.github/workflows/validate-star-wd-classifier.yml`
