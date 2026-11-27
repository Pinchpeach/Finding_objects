# results_2026-11-27: does the result depend on the order of the rows? (2.61.0)

Tool: `../shuffle_check.py` (modes `stage1`, `full`, `later`, `ties`, `root`, `compare`), `../before_after.py`.  Data: the raw rows of
the 26 deep COSMOS fields (`S1/<field>/raw/<tag>/*.csv`, `benchmark/association_truth/fields_split.csv`), the three
real-use fields (NGC 4522 2', COSMOS 2', Galactic plane 1') and NGC 4522 12' (Legacy Surveys rows from TAP and from the
viewer, 2.60.10).  "Before" = 2.60.x, which is `V2_ASSOC_TIE_ORDER=file` in 2.61.0; "after" = 2.61.0.  `D` is a scratch folder.

| folder / file | what | how it was made |
|---|---|---|
| `scope/sort_ties_deep_cosmos_1.csv` | detections that agree on every sort key but the row, per catalogue | `shuffle_check.py ties --raw RAW --out D` |
| `scope/stage1_shuffle_all_fields_before_fix.csv` | Stage 1, all raw files shuffled (seeds 1-3), 26 fields, 2.60.x code | `shuffle_check.py stage1 --raw RAW --out D --seeds 1 2 3` per field |
| `scope/stage1_shuffle_one_catalogue_before_fix.csv` | the same shuffling one catalogue's file only (12 catalogues x 6 fields x seeds 1-2) | `... --only desi_legacy` etc. |
| `scope/later_stages_row_order_real_use_fields.csv` | stages 2-7 and the grouping steps with the rows of every stage output permuted, association as collected | `shuffle_check.py later --raw RAW --ra --dec --radius --out D --seeds 1 2` |
| `before_after/objects_labels_before_vs_after_original_order.csv` | per field, 2.60.x against 2.61.0 on the rows in the order as collected | full pipeline of both (`run_full.sh S1 D 4`; for 2.60.x `V2_ASSOC_TIE_ORDER=file`), then `before_after.py --fields-root S1 --a RUNS_A --b RUNS_B --out CSV` |
| `before_after/objects_labels_before_original_vs_shuffled.csv` | 2.60.x, original order against rows shuffled with seed 1 | `shuffle_check.py root --raw S1 --out D/root_s1 --seeds 1`, `run_full.sh`, `before_after.py ... --seed-b 1` |
| `before_after/objects_labels_after_original_vs_shuffled.csv` | the same for 2.61.0 (all zeros) | same |
| `before_after/ngc4522_12arcmin_tap_vs_viewer_and_real_use_fields.csv` | NGC 4522 12': TAP rows against viewer rows, both tie orders; the three real-use fields, 2.60.x against 2.61.0 | `pipeline.py --raw-dir RAW --ra --dec --radius` for each, `shuffle_check.py compare --a WORK_A --b WORK_B` |
| `association/false_missed_{before,after}.csv`, `cut_curves_{before,after}.csv`, `structure_after.csv`, `*_shuffled_seed1.csv` | false associations, missed counterparts and cut curves of the association against COSMOS2020 | `run_variant.py --fields-root S1 --out D/diag`, `... --shift --out D/diag_shift`, `measure_association.py --truth-flux T --assoc-dir D/diag --shifted-dir D/diag_shift --variant V --out D/m`; `T` = COSMOS2020 truth fetched at 6.35' |
| `association/cut_curves_nocut_after.csv` | no-cut run | the same with `--env V2_ASSOC_MAX_NSEP=0`, `--variant nocut` |
| `association/error_model_after.csv`, `assignment_blocking_after.csv`, `q0_by_field_after.csv`, `calibration_summary_*_after.csv`, `reliability_tables_*_after.csv`, `isotonic_check_test_half_after.csv` | the rest of the 2.60.11 tables with the fixed Stage 1 | commands of `../../association_truth/results_2026-11-25/README.md` with `D/m/rows_after_orig.csv.gz` |
| `fragments/fragment_variants_summary_vs_2.60.x_base.csv` | fragment counts, labels changed against the 2.60.x base, McNemar | `regroup.py --runs RUNS --truth-flux T --variant V --env ... --out D/regroup` for each run (2.60.x original/shuffled, 2.61.0 original/shuffled, `hc`, `m15hc` of both), `fragment_variants_summary.py --regroup D/regroup --base before_orig --out D` |
| `fragments/fragment_variants_summary_vs_2.61.0_base.csv` | the same against the 2.61.0 base (the table of the hc decision) | `... --base after_orig` |
| `fragments/wrong_merge_types_*.csv`, `wrong_merge_objects_*_calibration.csv` | what the grouped objects are in the truth, by type; objects listed for the calibration half only | `wrong_merge_types.py --runs RUNS --truth-flux T --variant V --env ... --out D/types` |

Variants (`--env`): `*_base` = `V2_X=0` (replay of the run's own grouping); `*_hc` = `V2_FRAG_HOST_CANDIDATE=1`;
`*_m15hc` = `V2_FRAG_MIN_ARCSEC=1.5 V2_FRAG_HOST_CANDIDATE=1`.  Run names: `before_orig` = 2.60.x original order,
`after_orig` = 2.61.0 original order, `before_s1` / `after_s1` = the same with the rows shuffled by seed 1.
