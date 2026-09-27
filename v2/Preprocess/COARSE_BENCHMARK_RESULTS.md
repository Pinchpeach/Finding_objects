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
