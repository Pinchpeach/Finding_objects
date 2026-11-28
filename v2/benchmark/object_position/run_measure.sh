#!/bin/bash
# The measurement of V2_OBJECT_POSITION=best on the 26 deep COSMOS fields (task "버"): run_pipeline_both.sh first, then
#   run_measure.sh TRUTH_FLUX_DIR OUT_DIR       (OUT_DIR = the RESULT_DIR of run_pipeline_both.sh, with per_field/)
# measure_object_position.py --stage aggregate (invariance, residuals, shifts, timing, label tables), then rescore_labels.py for the two splits of the fields: the 2.60.9 split
# (15 / 11, name hash) and the 2.61.8 split (COSMOS fields 1-9 / 10-26).
set -e
T=$1; O=$2; HERE="$(cd "$(dirname "$0")" && pwd)"; AT="$HERE/../association_truth"; mkdir -p "$O"
python3 "$HERE/measure_object_position.py" --runs "$O" --truth-flux "$T" --out "$O" --stage aggregate
python3 "$AT/rescore_labels.py" --pairs best_vs_anchor="$O/labels_anchor.csv.gz:$O/labels_best.csv.gz" --out "$O/rescore_split_15_11.csv"
python3 "$AT/rescore_labels.py" --pairs best_vs_anchor="$O/labels_anchor.csv.gz:$O/labels_best.csv.gz" --out "$O/rescore_split_9_17.csv" --fields-split "$HERE/fields_split_9_17.csv"
