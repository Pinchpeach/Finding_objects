# results_2026-11-25: how each table is made (2.60.11)

All of it is made by scripts in `v2/benchmark/association_truth/` from the 26 deep COSMOS fields (`fields_split.csv`:
15 calibration, 11 test) and COSMOS2020 truth fetched at **6.35'** (`collect_truth_flux.py`; the fields are 6' cones, the
extra 0.35' is the search radius of a low-resolution row's flux-dominant counterpart; every count of truth sources is
restricted to the 6' field, `measure_association.inside`).  `S1` is the folder of the collected fields
(`<field>/{field.json,raw/<tag>/*.csv,truth/}`), `T` the truth folder, `D` a scratch folder.

| file | script and command |
|---|---|
| `false_missed_base.csv`, `cut_curves_base.csv`, `structure_base.csv`, `rows_base.csv.gz` (not kept) | `run_variant.py --fields-root S1 --out D/diag` and `... --shift --out D/diag_shift`, then `measure_association.py --truth-flux T --assoc-dir D/diag --shifted-dir D/diag_shift --variant base --out D/m` |
| `cut_curves_nocut.csv` | the same with `--env V2_ASSOC_MAX_NSEP=0` for both runs, `--variant nocut` |
| `error_model.csv`, `assignment_blocking.csv` | `error_model_and_assignment.py --rows D/m/rows_base.csv.gz --out D/m` |
| `q0_by_field.csv`, `calibration_summary_{conditional,unconditional}.csv`, `reliability_tables_{conditional,unconditional}.csv` | `posterior_calibration.py --rows D/m/rows_base.csv.gz --assoc-dir D/diag --fields-root S1 --out D/m` (add `--include-no-counterpart` for the unconditional ones) |
| `isotonic_check_test_half.csv` | `isotonic_check.py --rows D/m/rows_base.csv.gz --out D/m` |
| `fragment_variants_summary.csv`, `merges_<variant>.csv` | `run_full.sh S1 D/runs/base 3` once, then per variant `regroup.py --runs D/runs/base --truth-flux T --variant V --env KEY=VALUE ... --out D/regroup` and `fragment_variants_summary.py --regroup D/regroup --base replay_base --out D` |
| `wrong_merge_types_<v>.csv`, `wrong_merge_objects_<v>_calibration.csv` | `wrong_merge_types.py --runs D/runs/base --truth-flux T --variant V --env KEY=VALUE ... --out D/types` (the test half is only counted; objects are listed for the calibration half) |

Variants (`--env`): `replay_base` = nothing; `hc` = `V2_FRAG_HOST_CANDIDATE=1`; `m15hc` = `V2_FRAG_MIN_ARCSEC=1.5 V2_FRAG_HOST_CANDIDATE=1`;
`m15` / `m20` = `V2_FRAG_MIN_ARCSEC=1.5` / `2.0`; `f1hc` = `V2_FRAG_HOST_CANDIDATE=1 V2_FRAG_FAINTER_MAG=1.0`; `halo1` = `V2_HALO_FRACTION=1.0`.
