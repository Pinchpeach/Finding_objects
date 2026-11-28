# results_2026-11-28: the decision table with the exchange columns re-measured and the three switches together (2.62.7)

`decision_table.csv` replaces `../results_2026-11-27h/decision_table.csv`: the same columns, one more row (`fixed+same_nearest+surveys2`) and 12 cells different.  The 12 cells are the four exchange columns
(`lowlat_{conf,cal}_{removed,added}_vs_base_per_deg2`) of the rows `same_nearest`, `same_nearest+surveys2` and `same_nearest+surveys2+spectro_keep`: the 2.62.2 table passed a table with one row per object id
(the coordinates of the first variant that has the id) to the positional exchange, which pairs an id that a variant renumbered with another source (review of 2.62.2).  Every other cell is identical to
the old table (checked cell by cell).  The inputs of `inputs/` are those of `../results_2026-11-27h/inputs/` with the new variant added, except `lowlat_calibration.csv` / `lowlat_confirmation.csv`
(`combos_table.py` with the fixed exchange), `held_{b,d}_fixed_same_nearest.csv`, `type1_loss_by_r.csv` / `claims.csv` / ... (`faint_cost.py tables`, the old cells reproduced exactly) and the rows of
`cosmos_label_changes.csv`, `real_use_label_changes.csv`, `real_use_counts.csv` (`label_changes.py`, `real_use_counts.py`).  `assoc/` is the `rates.csv` / `structure.csv` of
`../../association_ambiguity/results_2026-11-27f` with the rows of `fixed_same_nearest` added (`compare_variants.py` on the 9 + 17 deep COSMOS fields; the old rows reproduced).

The three switches together = `V2_POSERR_UNITS=fixed V2_ASSOC_AMBIG=same,nearest V2_LOWLAT_QSO=surveys2` on the 169 + 140 low-latitude cones, the 26 deep COSMOS fields (limit lifted,
`V2_LOWLAT_QSO_ABSB=90`) and the three real-use fields; the base of every column is the legacy-unit base.  Each directory has a `run_info.json`.
