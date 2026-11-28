#!/bin/bash
# The full pipeline of the 26 deep COSMOS fields twice, V2_OBJECT_POSITION unset (anchor) and best (task "버", 2.62.10+).
#   run_pipeline_both.sh FIELDS_ROOT OUT_DIR [PARALLEL]
# FIELDS_ROOT/<field>/{field.json, raw/<tag>/}: the layout of benchmark/collect_deep_cosmos.py.  Writes OUT/anchor/<field>/ and OUT/best/<field>/ (the pipeline's work folders).
# A field is skipped when its classified_objects.csv exists, so an interrupted run goes on where it stopped.
set -e
R=$1; O=$2; P=${3:-3}; HERE="$(cd "$(dirname "$0")" && pwd)"; V2="$(cd "$HERE/../.." && pwd)"
export PYTHONHASHSEED=0 V2_CACHE=0
unset V2_OBJECT_POSITION
mkdir -p "$O"
run_one() { # run_one MODE FIELD
  local mode=$1 f=$2 w="$O/$1/$2"
  [ -f "$w/classified_objects.csv" ] && return 0
  local tag; tag=$(ls "$R/$f/raw" | head -1)
  local ra dec rad
  read -r ra dec rad < <(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d['ra'], d['dec'], d['radius_arcmin'])" "$R/$f/field.json")
  mkdir -p "$O/$mode"
  if [ "$mode" = best ]; then export V2_OBJECT_POSITION=best; else unset V2_OBJECT_POSITION; fi
  python3 "$V2/pipeline.py" --work "$w" --raw-dir "$R/$f/raw/$tag" --ra "$ra" --dec "$dec" --radius "$rad" > "$O/$mode/$f.log" 2>&1
}
export -f run_one; export R O V2
for mode in anchor best; do
  ls "$R" | grep '^deep_cosmos_' | xargs -P "$P" -I{} bash -c "run_one $mode {}"
done
echo done > "$O/done"
