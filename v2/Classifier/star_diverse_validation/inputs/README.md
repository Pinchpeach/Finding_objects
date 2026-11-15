# Frozen STAR model and inputs of the diverse LAMOST validation (2.53.1)

Inputs of `evaluate_star_diverse.py` (protocol `../../STAR_DIVERSE_PROTOCOL.md`,
report `../../STAR_DIVERSE_VALIDATION.md`).  Until 2.53.1 the workflow
`validate-star-diverse.yml` downloaded the frozen model from the artifact of
run 36295747956, which expired on 2026-10-27, so every run failed at that
step.  The files here were copied by that workflow from the full validation
artifact of run 36306280498 (`star-diverse-frozen-validation`, expires
2026-12-26), which holds the model exactly as the published evaluation
downloaded it, and were committed only after the model SHA256 matched the
protocol and the published `../metrics.json` was reproduced.

| file | content |
|---|---|
| `frozen_star_wd_classifier.joblib` | the frozen STAR model (`{"model", "features", "classes"}`, scikit-learn 1.9.1) from run 36295747956; SHA256 `22ae268a6525fc9fafbd6cff048c96512f235e75f998bdc63354610f518a9d5c` (protocol) |
| `frozen_star_gaia_features.csv.gz` | its original SDSS Gaia feature table: the 183/194 internal-test reproduction |
| `external_gaia.csv.gz` | Gaia DR3 2″ matches of the fixed diverse truth (`../truth.csv`) |
| `previous_gaia.csv.gz` | Gaia matches of the previously inspected LAMOST sets (`../../lamost_star_external_truth.csv`, `../../wd_subtype_truth.csv`), used to exclude overlaps by source ID |
| `SHA256SUMS` | hashes of the files as the published run used them (CSV before gzip; `data/truth.csv` is `../truth.csv`) |

The model is a pickle: the workflow checks its SHA256 before loading it.
It is never refitted, recalibrated or re-thresholded (protocol).

Every run evaluates these files and checks that `../metrics.json` is
reproduced (hashes, audit counts, the four confusion matrices, log loss,
Brier).  `refresh=true` evaluates the frozen model on a fresh collection of
the truth and the Gaia matches and commits nothing: the protocol fixes the
truth.  To restore a deleted file, check it out from git history; the
artifact the one-off restore step reads expires on 2026-12-26.
