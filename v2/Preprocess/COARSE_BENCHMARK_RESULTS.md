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

## 2026-10-08 (later): DESI DR1 external validation, colours, combined training

**External truth** (`v2/benchmark/desi_external/`): 1,797 DESI DR1 spectra
(Redrock SPECTYPE, ZWARN=0, DELTACHI2>25), ~150 per class in each of
r = 18–20, 20–21, 21–22, 22–23, from eight sky windows, none within 2″ of the
SDSS benchmark. Built by `build_desi_truth.py`; features collected and
evaluated by `.github/workflows/v2_desi_external_validation.yml`.

**Finding.** The SDSS-fitted model generalised to bright DESI objects but
failed for faint quasars: QSO accuracy 90% (r 18–20) → 13% (21–22) → 3%
(22–23), almost all called STAR. Without Gaia astrometry (G ≲ 21) or AllWISE
detections only point-source morphology remains, which cannot separate stars
from quasars.

**Changes.** (1) Legacy Surveys collector adds unWISE forced W1/W2; benchmark
LS features re-collected. (2) `LS-COLOR-001`: dereddened g−r, r−z, z−W1, W1−W2
(S/N ≥ 3) as continuous features — quasars' mid-IR excess and blue optical
colours (Chaussidon+2023). (3) Fitting on SDSS alone made colours *hurt*
faint DESI galaxies (covariate shift), so the fusion is now fitted on the
SDSS **and** DESI train splits; the threshold on both calibration splits;
each test split reported separately.

| test split | metric | previous (SDSS fit, no colours) | combined fit + colours |
|---|---|---:|---:|
| SDSS (1,991) | accuracy when classified | 97.5% | **97.9%** |
| SDSS | log-loss | 0.091 | **0.075** |
| DESI (353) | accuracy when classified | 78.3% | **83.3%** |
| DESI | QSO recall | ~0.44 | **0.88** |

DESI test accuracy by magnitude (combined fit; 24–38 objects per cell):

| r | GALAXY | QSO | STAR |
|---|---:|---:|---:|
| 18–20 | 0.92 | 0.83 | 1.00 |
| 20–21 | 1.00 | 0.93 | 0.74 |
| 21–22 | 0.89 | 0.76 | 0.55 |
| 22–23 | 0.61 | 0.92 | 0.75 |

DESI coverage/accuracy by confidence threshold: 0.7 → 83% / 90.1%,
0.8 → 74% / 93.5%, 0.9 → 50% / 98.3%.

Caveats: DESI targets were themselves selected with grz/W1/W2 colours and
QSO targets with PSF morphology, which favours these features on DESI; faint
STAR spectra in DESI are rare and partly mis-targeted. The DESI test split is
small; a larger set is the next step.

Fitted weights are physically sensible: W1−W2 and z−W1 favour QSO, red g−r
favours STAR, Legacy Surveys PSF morphology strongly disfavours GALAXY,
significant proper motion favours STAR. Gaia DSC-Combmod evidence, which
previously had an untested prior weight of 1.0 per logit, is now fitted on
the SDSS-independent DESI rows only (DSC was trained on SDSS labels) and
receives weights of ~0.1–0.2: given astrometry, morphology and colours it
adds little.

### Refit on the enlarged DESI set (current weights)

The DESI external set was enlarged to 4,795 spectra (~400 per class per r
bin); the fusion was refitted on the SDSS and DESI train splits (threshold
from both calibration splits, `min_confidence` = 0.53).

| test split | n | coverage | accuracy when classified | log-loss | ECE |
|---|---:|---:|---:|---:|---:|
| SDSS | 1,991 | 98.4% | **97.9%** | 0.080 | 0.010 |
| DESI (r 18–23) | 962 | 93.8% | **87.9%** | 0.393 | 0.029 |

DESI test accuracy by magnitude (70–91 objects per cell):

| r | GALAXY | QSO | STAR |
|---|---:|---:|---:|
| 18–20 | 0.86 | 0.83 | 0.96 |
| 20–21 | 0.95 | 0.90 | 0.76 |
| 21–22 | 0.92 | 0.81 | 0.49 |
| 22–23 | 0.83 | 0.82 | 0.73 |

DESI coverage/accuracy by threshold: 0.7 → 83% / 92.7%, 0.8 → 73% / 94.2%,
0.9 → 55% / 95.8%. The main remaining error is faint stars called QSO
(50 of 318): at r ≈ 21–22 blue stars (e.g. white dwarfs, hot subdwarfs) share
quasars' optical colours and lack Gaia astrometry. Variability or deeper
UV/IR data would be needed to separate them.

## Real-field end-to-end check (collection + association + classification)

`.github/workflows/v2_field_validation.yml` runs `v2/pipeline.py` on a field
outside the DESI truth-set sky windows (RA 245°, Dec +43°, r = 3′) and compares
coarse classes with the DESI DR1 spectra found in the field (DESI spectra are
not classification evidence). The benchmarks never exercised field-wide
association; this check exposed three catalog-hygiene problems:

1. DESI DR1 rows included **sky fibres** (OBJTYPE=SKY) at blank positions.
2. **Pan-STARRS1** MeanObject returned ~4× more rows than the deeper Legacy
   Surveys catalog; single-detection rows (spurious/moving; STScI recommends
   nDetections ≥ 2) duplicated real sources.
3. **Catalog-internal duplicates** (several DESI TARGETIDs per object; SDSS
   secondary detections, mode 2).

Because one object can hold only one row per catalog, duplicates either
became evidence-less objects or made Stage-1 matches "ambiguous", splitting
the DESI, LS and PS1 detections of one object apart.

| | before | after collector fixes |
|---|---:|---:|
| objects in field | 2,516 | 723 |
| NO_EVIDENCE | 72% | 25% |
| coverage of DESI-spectroscopic objects | 57% | 88% |
| accuracy when classified (n = 42) | 84% | 86.5% |
| wall time (collect / classify) | 127 s / 13 s | 130 s / 4 s |

Remaining unclassified DESI objects are r ≈ 24 sources below the colour
(S/N ≥ 3) and morphology (S/N ≥ 10) limits.
