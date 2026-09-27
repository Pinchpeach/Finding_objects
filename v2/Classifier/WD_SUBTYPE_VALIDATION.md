# White-dwarf subtype prototype: DA vs DB

## Goal

Test whether Gaia broadband astrometry/photometry alone is sufficient for the
first white-dwarf spectral subtype split.

Truth:
- LAMOST DR5 WD catalogue from Guo et al. (2022)
- only unambiguous pure `DA` and `DB` labels
- visually checked WD catalogue labels in the source work

Initial balanced truth:
- 150 DA
- 150 DB

Gaia DR3 matches:
- total: **291**
- DA: **145**
- DB: **146**

Split:
- train: **163**
- calibration: **68**
- test: **60**

Features:
- Gaia broadband astrometry/photometry only
- 16 derived/missingness features
- no LAMOST spectral label or spectrum is used as a feature

## Linear baseline

Logistic regression:
- accuracy: **73.33%**
- balanced accuracy: **73.44%**
- macro-F1: **73.30%**
- DB precision: **70.00%**
- DB recall: **75.00%**
- DB F1: **72.41%**

Confusion:
- true DA: 23 DA / 9 DB
- true DB: 7 DA / 21 DB

## Nonlinear Gaia-broadband model

Calibrated HistGradientBoosting:
- accuracy: **75.00%**
- balanced accuracy: **75.89%**
- macro-F1: **74.83%**
- DB precision: **67.57%**
- DB recall: **89.29%**
- DB F1: **76.92%**
- log loss: **0.4934**
- DB Brier: **0.1644**

Confusion:
- true DA: 20 DA / 12 DB
- true DB: 3 DA / 25 DB

## Interpretation

The nonlinear model recovers many DBs, but does so at the cost of too many DA
false positives. A 75% global accuracy is not sufficient for a production
spectral subtype classifier.

The result supports a strict architectural boundary:

- Gaia broadband photometry/astrometry is adequate for WD candidate routing.
- DA/DB/DC/DQ/DZ/DO spectral typing should require Gaia XP spectral
  coefficients or an optical spectrum.

This matches published work. García-Zamora et al. (2023) obtained substantially
stronger WD spectral classification using Gaia low-resolution spectral
coefficients, including about 90% global accuracy for DA vs non-DA and >80%
recall for DA and DB in their reported validation framework.

## Decision

Do **not** enable DA/DB output from broadband Gaia features.

Keep `spectral_type=UNRESOLVED` until a dedicated spectral-feature branch is
available. The next implementation target is:

`WHITE_DWARF_CANDIDATE -> XP/spectrum feature extraction -> spectral model -> DA/DB/DC/DQ/DZ/DO`

Workflow run: **36298470467**
