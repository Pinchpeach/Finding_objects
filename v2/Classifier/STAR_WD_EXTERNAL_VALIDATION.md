# STAR white-dwarf external validation

## Purpose

Test whether the SDSS-trained Gaia white-dwarf classifier generalizes to an
independent spectroscopic survey.

Training/calibration:
- SDSS DR18 spectroscopy truth
- Gaia DR3 astrometry/photometry only as model features

External truth:
- LAMOST DR5
- 500 published LAMOST DA white dwarfs from Guo et al. (2022)
- 500 ordinary LAMOST O/B/A/F/G/K/M spectra
- objects within 2 arcsec of the SDSS STAR truth set are excluded before use
- the resulting external truth file is fixed in the repository for reproducibility

Final fixed external truth:
- requested rows: 1000
- Gaia DR3 matched rows: **977**
- NORMAL_STAR: **498**
- WHITE_DWARF (DA): **479**

Important limitation: the positive external WD sample is DA-dominated/pure DA,
so this validates robust WD-vs-normal-star separation for DA white dwarfs, not
all WD spectral subtypes.

## Literature HR baseline

Broad Gaia HR rule:
`M_G > 6 + 5(BP-RP)` with `parallax_over_error > 1`.

External result:
- accuracy: **99.69%**
- balanced accuracy: **99.69%**
- WD precision: **100.00%**
- WD recall: **99.37%**
- WD F1: **99.69%**
- directly usable fraction: **99.18%**

On the 969 rows where the rule is directly applicable:
- accuracy: **99.79%**

## SDSS-trained learned Gaia model

External result:
- accuracy: **99.59%**
- balanced accuracy: **99.58%**
- macro-F1: **99.59%**
- WD precision: **100.00%**
- WD recall: **99.16%**
- WD F1: **99.58%**
- log loss: **0.0465**
- WD Brier: **0.0074**

The learned model remains excellent, but the simple literature HR rule is
slightly more robust on this independent LAMOST sample.

## Consensus policy

Policy:
1. If the HR rule is usable and agrees with the calibrated model, classify.
2. If the HR rule is unavailable, accept the learned model only when max
   calibrated probability is >= 0.90.
3. Otherwise return UNKNOWN.

External result:
- coverage: **99.90%**
- classified rows: **976 / 977**
- classified-only accuracy: **99.69%**
- classified-only balanced accuracy: **99.69%**
- UNKNOWN: **1**

Internal SDSS held-out test:
- coverage: **94.33%**
- classified-only accuracy: **97.81%**
- classified-only balanced accuracy: **97.86%**
- UNKNOWN: **11 / 194**

## Decision

For the STAR branch, the robust production direction is:

- use the literature-backed Gaia HR locus as the primary WD-candidate signal
  when its required measurements are available;
- keep the learned Gaia model as a secondary/fallback evidence source;
- abstain when robust signals conflict;
- do not treat the learned model as an unconditional replacement.

This is more robust to survey/domain shift than selecting whichever model has
the best accuracy on a single benchmark.

## Reproducibility

- fixed external truth commit: `a9ebe8e`
- fixed-truth external validation workflow run: **36298207498**
- consensus internal validation workflow run: **36297957426**

Key code:
- `build_lamost_star_external_truth.py`
- `validate_star_wd_external.py`
- `train_validate_star_wd.py`
