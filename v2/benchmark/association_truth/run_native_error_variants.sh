#!/bin/bash
# AllWISE eeMaj / GALEX Nerr as the position error on the 26 deep COSMOS fields (2.62.4).
#   run_native_error_variants.sh FIELDS_ROOT TRUTH_FLUX_DIR OUT_DIR
# FIELDS_ROOT/<field>/raw/<tag>/*.csv (collect_deep_cosmos.py), TRUTH_FLUX_DIR/<field>.csv.gz (collect_truth_flux.py).  Stage 1 only, once per variant and
# once more on the shifted-catalogue copy (run_variant.py --shift); then measure_association.py per variant.  Two runs at a time.
set -e
R=$1; T=$2; O=$3; mkdir -p "$O"; HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE"
export PYTHONHASHSEED=0 V2_CACHE=0
# run_variant.py and measure_association.py write run_info.json in every directory they write; this one is for the table directory
python3 "$HERE/../run_info.py" begin --out "$O/summary" --input "$R" "$T" --note "run_native_error_variants.sh"
run()  { tag=$1; shift; python3 run_variant.py --fields-root "$R" --out "$O/$tag" --env "$@" > "$O/$tag.log" 2>&1; }
runs() { tag=$1; shift; python3 run_variant.py --fields-root "$R" --out "$O/${tag}_shift" --shift --env "$@" > "$O/${tag}_shift.log" 2>&1; }
run base V2_POSERR_NATIVE= & run galex V2_POSERR_NATIVE=galex & wait
run allwise V2_POSERR_NATIVE=allwise & run allwise_raw V2_POSERR_NATIVE=allwise_raw & wait
runs base V2_POSERR_NATIVE= & runs galex V2_POSERR_NATIVE=galex & wait
runs allwise V2_POSERR_NATIVE=allwise & runs allwise_raw V2_POSERR_NATIVE=allwise_raw & wait
for v in base allwise allwise_raw galex; do
  python3 measure_association.py --truth-flux "$T" --assoc-dir "$O/$v" --shifted-dir "$O/${v}_shift" --variant "$v" --out "$O/meas_$v" > "$O/meas_$v.log" 2>&1 &
done
wait
python3 summarize_native_error_variants.py --root "$O" --out "$O/summary"
python3 "$HERE/../run_info.py" end --out "$O/summary" --status ok
