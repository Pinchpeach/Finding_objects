# results_2026-11-28c: where the objects sit relative to the truth, by order of Stage 1 and by output-position design (2.62.7, task "너", addition of 02:33)

Question (planning session): the 2.61.0 order change turned 105 of 108 broken `exists` readings into "no object within 0.5'' any more" -- is it the anchor POSITION that moved away from the truth?
Predictions: `../PREDICTIONS_POSITION_RESIDUAL_2026-11-28.md` (commit c993b60, before the analysis).  Tool: `../position_residual.py` (definitions in its docstring and in the predictions file).
Data: the 26 deep COSMOS fields, Stage 1 on the stored blind raw rows, COSMOS2020 truth (HSC i < 25); clean objects only (the resolving rows reach exactly one truth source), 136,820 for `new`.

| file | content |
|---|---|
| `residual_summary.csv` | per variant and slice (all, HSC i bin, anchor catalogue): objects, median, 90 / 99 percentile, share beyond 0.3 / 0.5 / 0.7 / 1.0'' |
| `residual_paired.csv` | each variant against `new`, for the truth sources that have a clean single object in both: worse / better by more than 0.1'', crossings of 0.5'', anchor transitions |
| `design_summary.csv`, `design_summary_floored_groups.csv` | the output position as a design (anchor / most precise member / inverse-variance mean) on the groups of `new` and of `floored` |
| `stage1_*.run_info.json`, `position_residual.run_info.json` | the records of the runs (`V2_ASSOC_TIE_ORDER`, `V2_ASSOC_ORDER_KEY`, `V2_POSERR_NATIVE` as set and as the code reads them, input hashes; `dirty` is true because the tool files of this folder were not committed yet when the runs started) |

Variants: `new` = the default tie order since 2.61.0 (brightness); `file` = the order of 2.60.x (a tie is decided by the row of the input file); `position`; `floored` = `V2_ASSOC_ORDER_KEY=floored`; `allwise_order`.

| variant | median '' | p90 '' | p99 '' | beyond 0.5'' % | beyond 1.0'' % |
|---|---|---|---|---|---|
| `new` (anchor position) | 0.072 | 0.289 | 1.485 | 4.51 | 1.94 |
| `file` | 0.072 | 0.288 | 1.477 | 4.46 | 1.92 |
| `position` | 0.072 | 0.288 | 1.478 | 4.46 | 1.92 |
| `allwise_order` | 0.072 | 0.283 | 1.434 | 4.26 | 1.78 |
| `floored` | 0.070 | 0.259 | 1.255 | **3.27** | 1.36 |
| `new` groups, output = most precise member | 0.070 | 0.258 | 1.196 | **3.16** | 1.24 |
| `new` groups, output = inverse-variance mean | 0.072 | 0.263 | **1.049** | 3.28 | **1.05** |

By anchor (`new`): LS 112,900 objects, median 0.066'', 0.94 % beyond 0.5''; PS1 17,736, median 0.136'', 17.4 % beyond 0.5'', 9.0 % beyond 1''; AllWISE 2,620, median 0.78'', 71 % beyond 0.5'' (30 % of all objects beyond 0.5'' are AllWISE-anchored, 50 % PS1-anchored).
