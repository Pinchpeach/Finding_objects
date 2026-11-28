#!/bin/bash
# The order-key variants on the real-use fields and the 309 low-latitude cones (no association truth; 2.62.7, task "너" item 3).
#   run_order_key_outside.sh ROOTS_DIR OUT_DIR       ROOTS_DIR/{real,cal,conf}/<field>/raw/<tag>/*.csv (symlinks are fine)
set -e
# The directory arguments are made absolute BEFORE the cd below: a relative path given from the repository root would otherwise point into this directory (Codex review of 2.62.10).
R=$(cd "$1" && pwd); mkdir -p "$2"; O=$(cd "$2" && pwd); HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE"
export PYTHONHASHSEED=0 V2_CACHE=0
python3 "$HERE/../run_info.py" begin --out "$O/summary" --input "$R" --note "run_order_key_outside.sh"
declare -A ENVS=(
  [base]="V2_POSERR_NATIVE= V2_ASSOC_ORDER_KEY="
  [allwise]="V2_POSERR_NATIVE=allwise V2_ASSOC_ORDER_KEY="
  [allwise_order]="V2_POSERR_NATIVE=allwise_order V2_ASSOC_ORDER_KEY="
  [allwise_sigma]="V2_POSERR_NATIVE=allwise_sigma V2_ASSOC_ORDER_KEY="
  [floored]="V2_POSERR_NATIVE= V2_ASSOC_ORDER_KEY=floored"
)
VARIANTS="base allwise allwise_order allwise_sigma floored"
for S in real cal conf; do
  mkdir -p "$O/$S"
  for sh in "" "_shift"; do
    n=0
    for v in $VARIANTS; do
      python3 run_variant.py --fields-root "$R/$S" --field-glob '*' --out "$O/$S/$v$sh" ${sh:+--shift} --env ${ENVS[$v]} > "$O/$S/$v$sh.log" 2>&1 &
      n=$((n+1)); [ $((n % 2)) -eq 0 ] && wait
    done
    wait
  done
done
python3 outside_cosmos_summary.py --root "$O" --sets real cal conf --variants $VARIANTS --out "$O/summary"
python3 "$HERE/../run_info.py" end --out "$O/summary" --status ok
