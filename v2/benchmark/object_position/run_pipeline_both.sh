#!/bin/bash
# The full pipeline of the 26 deep COSMOS fields twice, V2_OBJECT_POSITION unset (anchor) and best, measured field by field (task "버", 2.62.11).
#   run_pipeline_both.sh FIELDS_ROOT WORK_DIR RESULT_DIR TRUTH_FLUX_DIR [PARALLEL]
# FIELDS_ROOT/<field>/{field.json, raw/<tag>/}: the layout of benchmark/collect_deep_cosmos.py.  One job per field: the pipeline with the switch off, then on (WORK_DIR/{anchor,best}/<field>/),
# then ``measure_object_position.py --stage field`` (slim results into RESULT_DIR/per_field/<field>.pkl), then the heavy work folders of that field are deleted: the stage tables of one deep
# field are ~0.6 GB (26 fields x 2 modes filled the disk of the first attempt).  A field with a result in RESULT_DIR/per_field is skipped, so an interrupted run goes on where it stopped.
# At the end ``run_measure.sh`` makes the tables from the per-field results.
set -e
R=$1; W=$2; O=$3; T=$4; P=${5:-3}; HERE="$(cd "$(dirname "$0")" && pwd)"; V2="$(cd "$HERE/../.." && pwd)"
export PYTHONHASHSEED=0 V2_CACHE=0
unset V2_OBJECT_POSITION
mkdir -p "$W" "$O/per_field"
run_one() { # run_one FIELD
  local f=$1
  [ -f "$O/per_field/$f.pkl" ] && return 0
  local tag ra dec rad
  tag=$(ls "$R/$f/raw" | head -1)
  read -r ra dec rad < <(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d['ra'], d['dec'], d['radius_arcmin'])" "$R/$f/field.json")
  for mode in anchor best; do
    mkdir -p "$W/$mode"
    if [ "$mode" = best ]; then export V2_OBJECT_POSITION=best; else unset V2_OBJECT_POSITION; fi
    python3 "$V2/pipeline.py" --work "$W/$mode/$f" --raw-dir "$R/$f/raw/$tag" --ra "$ra" --dec "$dec" --radius "$rad" > "$W/$mode/$f.log" 2>&1
  done
  unset V2_OBJECT_POSITION
  python3 "$HERE/measure_object_position.py" --runs "$W" --truth-flux "$T" --out "$O" --fields "$f" --stage field > "$W/$f.measure.log" 2>&1
  rm -rf "$W/anchor/$f" "$W/best/$f"
}
export -f run_one; export R W O T HERE V2
ls "$R" | grep '^deep_cosmos_' | xargs -P "$P" -I{} bash -c "run_one {}"
echo done > "$O/done"
