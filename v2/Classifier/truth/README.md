# Independent truth lists (2.61.9)

The cross-validation workflow (`.github/workflows/v2_scientific_cross_validation.yml`) validates the classifier against per-axis truth lists made from
VizieR catalogues (Vrard+2025 red giants, ASAS-SN variables, ATNF pulsars, Acker planetary nebulae, Asiago supernovae).  Until 2.61.8 the lists were built
again in every run from "the first rows the archive answers", and over the 25 bot commits since 2026-10-25 the variability classes had 6-7 different
sets of truth ids (`../validation/reproducibility/sample_states.csv`), so two runs could not be compared.

## The rule

* **Selection is order-free** (`deterministic.py`): a class keeps the 250 rows with the smallest SHA-256("independent-truth-v1|<truth_id>").  The same ids
  are chosen from any permutation of the candidates, and a candidate that is not among the 250 does not change the choice.  Queries ask for the whole table;
  no `row_limit` cuts it at a place the server decides (IVOA ADQL 2.1, Sect. 2.2: "The order of the rows MAY be arbitrary unless an ORDER BY clause is
  specified").  A query that fails raises; a class never goes missing silently.
* **The list is a committed file** `fixed/` with `truth_manifest.json` (SHA-256 of every file and of the id set of every class).  The workflow checks the
  directory against its manifest (`build_independent_truth_sets.py --verify fixed`) and does not query VizieR for the truth.
* **Until `fixed/` is committed** the workflow builds the same deterministic list itself and marks the run UNFROZEN in its report.

## Freezing (once, and again only when a truth catalogue should change)

1. Run the workflow by hand with `freeze_truth = true` (builds the list with `--require-complete`, uploads the artifact `frozen-truth-candidate`, validates nothing).
2. Copy the artifact to `v2/Classifier/truth/fixed/`, check `python build_independent_truth_sets.py --verify v2/Classifier/truth/fixed`, commit with a version bump
   and a CHANGELOG row that names the new `list_sha256`.
3. The next normal run measures the baseline on the frozen list.  A refit of the calibration (`refit_calibration = true`) is a separate, explicit run.

`generated/` is the output of older builds (2.38.0) and is not read any more.
