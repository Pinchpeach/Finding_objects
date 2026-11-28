# results_2026-11-28b: the order key of Stage 1 and AllWISE eeMaj (2.62.7, task "너")

Predictions: `../PREDICTIONS_ORDER_KEY_2026-11-28.md` (committed before the variants existed).  Report: `../../../WORK_REPORT_2026-11-28d.md`.

| file | what | made by |
|---|---|---|
| `order_key_false_missed.csv`, `order_key_structure.csv` | the 26 deep COSMOS fields (Stage 1, COSMOS2020 truth, calibration 9 / confirmation 17): per catalogue and half, matched / correct / rightly alone / false / missed / shifted control, and objects, anchors, objects differing from `base` | `run_order_key_variants.sh` (+ `summarize_native_error_variants.py --stem order_key --cats AllWISE "2MASS PSC" "GALEX AIS"`) |
| `outside_cosmos.csv` | `deep26`: the same 26 fields; `real`: NGC 4522 + Galactic plane; `cal` / `conf`: the 169 + 140 low-latitude cones (no truth): objects, AllWISE anchors, AllWISE rows joined, objects differing, the shifted-catalogue control in two definitions (`shifted_false_pct` = joined to an object anchored by an unshifted catalogue, the 2.49.0 definition; `shifted_any_pct` = the shifted row's object holds any row of an unshifted catalogue) | `run_order_key_outside.sh`, `outside_cosmos_summary.py` |
| `trade_table.csv` | what `allwise_order` and `floored` buy and cost on the AllWISE rows of the 26 fields, by half | assembled from the two above |
| `real_use_label_changes.csv`, `real_use_objects.csv`, `real_use_labels/` | the three real-use fields through the full pipeline: primary labels changed against `base` (objects paired by position, 0.2'') and object counts | `association_ambiguity/label_changes.py` |
| `shuffle_check.csv` | row-order independence: 3 seeds x NGC 4522 / COSMOS 2' x 4 variants | `order_dependence/shuffle_check.py stage1` |
| `tie_order_interaction.csv` | objects that differ between the tie orders `brightness` (default), `position`, `file` per variant, on the three real-use fields | `tie_order_interaction.py` |

Variants: `base`; `allwise` (eeMaj in sigma AND in the order key, as 2.62.4); `allwise_order` (eeMaj in the order key only); `allwise_sigma` (eeMaj in sigma only); `floored` (`V2_ASSOC_ORDER_KEY=floored`: the
order key is the sigma the match uses, with the PSF/6 floor, for every catalogue); `allwise_floored`, `allwise_order_floored`.

Read before using the tables: the `correct` column counts a row only when it JOINED an existing group.  A row that anchors its object, with the right counterpart in the same object, is `rightly_alone`.  An order key that moves
AllWISE rows behind the optical rows turns `rightly_alone` into `correct` without any new right association; `right_object = correct + rightly_alone` does not depend on who anchors.  The same holds for the shifted-catalogue control
(`shifted_false_pct` vs `shifted_any_pct`).
