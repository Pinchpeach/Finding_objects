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
* **Until `fixed/` is committed** a manual run builds the same deterministic list itself and marks the run UNFROZEN in its report; a **push** run does
  nothing and says `SKIPPED_UNFROZEN` (2.62.1: it would ask the archives for whole tables at every merge for numbers that cannot be compared).  The skip
  ends by itself once `fixed/truth_manifest.json` exists (`build_independent_truth_sets.py --run-mode`).
* **Queries ask for the columns the builder reads** (identifier, class, quality, position; 2.62.1), and fall back to the full row when that answer fails
  or lacks one of them.

## Freezing (once, and again only when a truth catalogue should change)

1. Run the workflow by hand with `freeze_truth = true` (builds the list with `--require-complete`, uploads the artifact `frozen-truth-candidate`, validates nothing).
2. Run `v2 commit frozen truth list` (`.github/workflows/v2_commit_frozen_truth.yml`, 2.62.8) by hand **on a working branch** with the freeze run's id, and
   with `compare_run_id` set to a second freeze run made at another time. The workflow downloads both artifacts and checks each with `--verify`. It refuses
   to commit when their `list_sha256` differ, copies only the manifest and its files into `fixed/`, and commits to that branch (never main). The list
   reaches main through a pull request with a version bump and a CHANGELOG row that names the `list_sha256`. (By hand, the same steps: copy the artifact,
   `python build_independent_truth_sets.py --verify v2/Classifier/truth/fixed`, commit.)
3. The next normal run measures the baseline on the frozen list.  A refit of the calibration (`refit_calibration = true`) is a separate, explicit run.

`generated/` is the output of older builds (2.38.0) and is not read any more.
