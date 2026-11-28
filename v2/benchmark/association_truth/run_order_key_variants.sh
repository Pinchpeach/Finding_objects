#!/bin/bash
# The order key of Stage 1 and AllWISE eeMaj on the 26 deep COSMOS fields (2.62.7, task "너"; predictions: PREDICTIONS_ORDER_KEY_2026-11-28.md).
#   run_order_key_variants.sh FIELDS_ROOT TRUTH_FLUX_DIR OUT_DIR
# Same structure as run_native_error_variants.sh: Stage 1 once per variant and once on the shifted-catalogue copy, then measure_association.py, then the table.
# Variants: base; allwise (eeMaj in sigma AND order); allwise_order (eeMaj in the order only); allwise_sigma (eeMaj in sigma only); floored (order key = the floored sigma
# of every catalogue); allwise_floored (eeMaj in sigma, order key floored); allwise_order_floored.
set -e
# The directory arguments are made absolute BEFORE the cd below: a relative path given from the repository root would otherwise point into this directory (Codex review of 2.62.10).
R=$(cd "$1" && pwd); T=$(cd "$2" && pwd); mkdir -p "$3"; O=$(cd "$3" && pwd); HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE"
export PYTHONHASHSEED=0 V2_CACHE=0
python3 "$HERE/../run_info.py" begin --out "$O/summary" --input "$R" "$T" --note "run_order_key_variants.sh"
declare -A ENVS=(
  [base]="V2_POSERR_NATIVE= V2_ASSOC_ORDER_KEY="
  [allwise]="V2_POSERR_NATIVE=allwise V2_ASSOC_ORDER_KEY="
  [allwise_order]="V2_POSERR_NATIVE=allwise_order V2_ASSOC_ORDER_KEY="
  [allwise_sigma]="V2_POSERR_NATIVE=allwise_sigma V2_ASSOC_ORDER_KEY="
  [floored]="V2_POSERR_NATIVE= V2_ASSOC_ORDER_KEY=floored"
  [allwise_floored]="V2_POSERR_NATIVE=allwise V2_ASSOC_ORDER_KEY=floored"
  [allwise_order_floored]="V2_POSERR_NATIVE=allwise_order V2_ASSOC_ORDER_KEY=floored"
)
VARIANTS="base allwise allwise_order allwise_sigma floored allwise_floored allwise_order_floored"
two() { # run the variants two at a time: two ARGS...
  local n=0
  for v in $VARIANTS; do
    python3 run_variant.py --fields-root "$R" --out "$O/$v$1" $2 --env ${ENVS[$v]} > "$O/$v$1.log" 2>&1 &
    n=$((n+1)); if [ $((n % 2)) -eq 0 ]; then wait; fi
  done
  wait
}
two "" ""
two "_shift" "--shift"
for v in $VARIANTS; do
  python3 measure_association.py --truth-flux "$T" --assoc-dir "$O/$v" --shifted-dir "$O/${v}_shift" --variant "$v" --out "$O/meas_$v" > "$O/meas_$v.log" 2>&1 &
done
wait
python3 summarize_native_error_variants.py --root "$O" --out "$O/summary" --variants $VARIANTS --cats AllWISE "2MASS PSC" "GALEX AIS" --stem order_key
python3 "$HERE/../run_info.py" end --out "$O/summary" --status ok
