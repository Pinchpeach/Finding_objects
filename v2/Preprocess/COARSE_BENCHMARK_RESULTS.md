# Coarse Preprocess benchmark

Validated on the 9,999-object SDSS spectroscopic benchmark using the existing
multi-survey catalog artifacts. Test split: **1,991** objects.

## Before coarse-only refactor

The previous Preprocess likelihood space was STAR / WD / GALAXY / QSO / BINARY.

- classified: 241 / 1,991
- abstention: 87.9%
- accuracy among classified: 81.7%
- macro-F1 among classified: 53.0%

## After STAR / GALAXY / QSO coarse refactor

- classified: **673 / 1,991**
- classification coverage: **33.8%**
- abstention: **66.2%**
- accuracy among classified: **88.4%**
- macro-F1 among classified: **74.7%**
- overall accuracy when UNKNOWN counts as incorrect: **29.9%**

Confusion including abstentions:

| truth | STAR | GALAXY | QSO | UNKNOWN |
|---|---:|---:|---:|---:|
| STAR | 357 | 2 | 0 | 286 |
| GALAXY | 1 | 213 | 0 | 488 |
| QSO | 0 | 75 | 25 | 544 |

## Interpretation

The coarse-only mapping substantially improves both coverage and classified-only
accuracy without replacing the explainable evidence-fusion design with a learned
model. QSO remains the weakest coarse branch: most QSO objects still abstain,
and a non-trivial subset is routed to GALAXY. This is acceptable for the current
conservative Preprocess role but should be treated as the next rule-calibration
target rather than solved by moving a black-box model into Preprocess.

GitHub Actions validation:
- Evaluate Preprocess Coarse Classifier run 36294866251: success
- Test Preprocess Pipeline after coarse changes: success

## 2026-10-08: point-source grouping, Legacy Surveys morphology, fitted fusion

Same 9,999-object benchmark and deterministic split (test: 1,991). Catalog
features are now preserved in `v2/benchmark/catalog_features/` because the
original Actions artifacts expire on 2026-10-10.

Changes, each with a literature basis:

1. Unresolved morphology (PS1 PSF-Kron, SDSS `type=6`) is emitted as
   `POINT_SOURCE` and supports STAR and QSO equally; quasars are point
   sources too (DESI QSO targeting requires PSF morphology, Chaussidon+2023).
   Previously it supported STAR only, so "point-like + extragalactic" could
   never single out QSO.
2. New `LS-MORPH-001/002`: Legacy Surveys DR10 Tractor model choice (Dey+2019),
   used only at r- or z-band S/N >= 10.
3. Stage 5 is a linear log-odds model. Per-evidence-key weights are fitted
   (multinomial logistic regression) on the **train** split only; the
   regularization and abstention threshold are chosen on the **calibration**
   split (threshold rule fixed beforehand: calibration accuracy >= 0.95); the
   test split is reported once. Keys with no training support (Gaia DSC,
   SIMBAD, NED, SDSS photometry, PS1 z~6 QSO, variability) keep their prior
   weights. Weights: `fusion_weights.json`; fit: `v2/benchmark/fit_fusion_weights.py`.

| test split | main (before) | rules 1-2 only | rules 1-2 + fitted fusion |
|---|---:|---:|---:|
| classified | 673 (33.8%) | 1,373 (69.0%) | **1,983 (99.6%)** |
| accuracy when classified | 88.4% | 88.7% | **97.4%** |
| macro-F1 when classified | 0.747 | 0.872 | **0.974** |
| accuracy, UNKNOWN counted wrong | 29.9% | 61.2% | **97.0%** |

Fitted-fusion test detail: log-loss 0.091, expected calibration error 0.015;
precision STAR 98.9% / GALAXY 97.0% / QSO 96.7%. Raising `min_confidence` to
0.9 gives 93.8% coverage at 99.1% accuracy.

Limits: SDSS spectroscopic targets are brighter and cleaner than a typical
field, and the benchmark is class-balanced (equal priors), so field accuracy
will be lower and the probabilities assume equal priors. Gaia DSC is absent
from this benchmark (Gaia features come from the VizieR main table), so its
prior weight is untested here.

### Field class priors (label shift)

The fitted weights assume the benchmark's equal class priors. Stage 5 now
re-estimates each field's class mix with the EM procedure of Saerens, Latinne
& Decaestecker (2002, Neural Computation 14, 21) when a fitted model is present
and at least 50 objects have evidence outside large-galaxy hosts, and
rescales the posteriors accordingly (`field_prior_*`, `p_*_training_prior`,
`coarse_prior_adjusted`). Simulated label shift on the test split (600
objects per draw, 20 draws):

| field mix STAR/GAL/QSO | accuracy before → after | log-loss before → after | estimated prior |
|---|---|---|---|
| 0.33/0.33/0.33 | 0.974 → 0.974 | 0.092 → 0.092 | 0.33/0.32/0.34 |
| 0.70/0.20/0.10 | 0.979 → 0.984 | 0.070 → 0.056 | 0.70/0.20/0.10 |
| 0.10/0.80/0.10 | 0.977 → 0.987 | 0.095 → 0.050 | 0.10/0.79/0.11 |
| 0.85/0.10/0.05 | 0.986 → 0.992 | 0.045 → 0.029 | 0.85/0.10/0.05 |

This corrects class-mix shift only; a field that is also fainter than the
SDSS spectroscopic benchmark (covariate shift) is not corrected by it.

### Accuracy by magnitude (test split, PS1 Kron r)

| r | n | coverage | accuracy when classified |
|---|---:|---:|---:|
| < 17 | 372 | 99.5% | 97.8% |
| 17–18 | 686 | 98.8% | 97.8% |
| 18–19 | 430 | 99.3% | 97.4% |
| 19–20 | 378 | 100% | 98.4% |
| 20–21 | 96 | 100% | 91.7% |
| > 21 | 9 | – | too few to measure |

The SDSS benchmark validates the coarse classifier only to r ≈ 20; accuracy
starts to drop at 20–21 and fainter sources are untested. A deeper,
SDSS-independent truth set (DESI DR1) is the next validation step.
