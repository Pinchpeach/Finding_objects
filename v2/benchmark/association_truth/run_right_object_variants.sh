#!/bin/bash
# Association variants counted with the metrics of METRICS.md (right_object, missed, false, anchor-independent chance joins) on the 26 deep COSMOS fields (2.62.7, task "러").
#   run_right_object_variants.sh FIELDS_ROOT TRUTH_FLUX_DIR OUT_DIR
# Variants (all with the legacy position-error units, the default): base (the default code); file / position (the tie orders: file = the order of 2.60.x, a tie is decided by the row of the
# input file; the default is brightness since 2.61.0); same, nearest, same_nearest (V2_ASSOC_AMBIG, 2.61.8); floored (V2_ASSOC_ORDER_KEY, 2.62.7).
# Stage 1 once per variant and once on the shifted-catalogue copy, then measure_association.py (which now writes right_object and shifted_any_pct), then the table.
set -e
R=$1; T=$2; O=$3; mkdir -p "$O"; HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE"
export PYTHONHASHSEED=0 V2_CACHE=0
unset V2_ASSOC_TIE_ORDER  # an empty value is an error of the switch: the default variants must not set it
python3 "$HERE/../run_info.py" begin --out "$O/summary" --input "$R" "$T" --note "run_right_object_variants.sh"
declare -A ENVS=(
  [base]="V2_ASSOC_AMBIG= V2_ASSOC_ORDER_KEY="
  [file]="V2_ASSOC_TIE_ORDER=file V2_ASSOC_AMBIG= V2_ASSOC_ORDER_KEY="
  [position]="V2_ASSOC_TIE_ORDER=position V2_ASSOC_AMBIG= V2_ASSOC_ORDER_KEY="
  [same]="V2_ASSOC_AMBIG=same V2_ASSOC_ORDER_KEY="
  [nearest]="V2_ASSOC_AMBIG=nearest V2_ASSOC_ORDER_KEY="
  [same_nearest]="V2_ASSOC_AMBIG=same,nearest V2_ASSOC_ORDER_KEY="
  [floored]="V2_ASSOC_AMBIG= V2_ASSOC_ORDER_KEY=floored"
)
VARIANTS="base file position same nearest same_nearest floored"
# A bare `wait` returns 0 whatever its children did (Codex review of 2.62.10): every child's pid is waited for by itself, and a failure ends the run as failed
# (a partial baseline compared with complete variants gives spurious deltas).
PIDS=()
wait_all() {
  local p failed=0
  for p in "${PIDS[@]}"; do wait "$p" || failed=1; done
  PIDS=()
  if [ "$failed" -ne 0 ]; then
    echo "a background job failed: see the logs in $O" >&2
    python3 "$HERE/../run_info.py" end --out "$O/summary" --status failed
    exit 1
  fi
}
two() { # run the variants two at a time: two SUFFIX EXTRA_ARGS
  for v in $VARIANTS; do
    python3 run_variant.py --fields-root "$R" --out "$O/$v$1" $2 --env ${ENVS[$v]} > "$O/$v$1.log" 2>&1 &
    PIDS+=($!)
    if [ "${#PIDS[@]}" -eq 2 ]; then wait_all; fi
  done
  wait_all
}
two "" ""
two "_shift" "--shift"
for v in $VARIANTS; do
  python3 measure_association.py --truth-flux "$T" --assoc-dir "$O/$v" --shifted-dir "$O/${v}_shift" --variant "$v" --out "$O/meas_$v" > "$O/meas_$v.log" 2>&1 &
  PIDS+=($!)
done
wait_all
python3 summarize_native_error_variants.py --root "$O" --out "$O/summary" --variants $VARIANTS --cats AllWISE "2MASS PSC" "GALEX AIS" --stem right_object
python3 "$HERE/../run_info.py" end --out "$O/summary" --status ok
