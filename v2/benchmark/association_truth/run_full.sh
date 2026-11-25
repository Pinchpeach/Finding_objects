#!/bin/bash
# Full pipeline (stages 1-7 + grouping) on the raw data of the 26 deep COSMOS fields for one variant (2.60.9).
#   run_full.sh FIELDS_ROOT OUT_DIR [PARALLEL] [ENV=VALUE ...]
# FIELDS_ROOT/<field>/{field.json,raw/<tag>/*.csv}; OUT_DIR/<field>/ gets the stage products.  The variant switches
# are environment variables (V2_ASSOC_...), given after the parallelism.
ROOT=$1; OUT=$2; P=${3:-3}; shift $(( $# < 3 ? $# : 3 ))  # two arguments are enough (2.60.9 review)
export PYTHONHASHSEED=0 "$@"
V2="$(cd "$(dirname "$0")/../.." && pwd)"
mkdir -p "$OUT"
run_one() {
  f=$1
  raw=$(ls -d "$ROOT/$f/raw"/*/ | head -1)
  read ra dec < <(python3 -c "import json;j=json.load(open('$ROOT/$f/field.json'));print(j['ra'],j['dec'])")
  [ -f "$OUT/$f/objects_summary.csv" ] && return 0
  python3 "$V2/pipeline.py" --work "$OUT/$f" --raw-dir "$raw" --ra "$ra" --dec "$dec" --radius 6 > "$OUT/$f.log" 2>&1
}
export -f run_one; export ROOT OUT V2
# a failed field fails the batch: no completion marker (2.60.9 review, Codex)
if ! ls "$ROOT" | grep '^deep_cosmos_' | xargs -P "$P" -I{} bash -c 'run_one {}'; then
  echo "run_full.sh: at least one field failed, see $OUT/*.log" >&2
  exit 1
fi
echo done > "$OUT/done.txt"
