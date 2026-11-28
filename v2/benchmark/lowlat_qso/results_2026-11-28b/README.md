# results_2026-11-28b: the decision table with a tenth row, `fixed + same,nearest + surveys2 + lit_keep` (2.62.7)

Order of 2026-11-28 (task b, addition): `surveys2` is on by default in the three-switch combination, so not erasing a NED / SIMBAD QSO label (`V2_LOWLAT_QSO=surveys2,lit_keep`, 2.62.4) is the explainable behaviour.
`decision_table.csv` is `../results_2026-11-28/decision_table.csv` plus one row; **the nine old rows are identical, cell by cell** (checked).  `inputs/` are the inputs of the 2.62.6 table with the new variant added
(`combos_table.py` on the 169 + 140 cones, `spectro_held.py` on the 15 + 17 cones with spectra, `faint_cost.py tables` on the 26 deep COSMOS fields with the old variants reproduced exactly,
`label_changes.py` for the 26 deep fields and the three real-use fields, `real_use_counts.py --update`); `assoc/` holds the `exchange.csv` of `../../association_ambiguity/results_2026-11-27f` and the `rates.csv` /
`structure.csv` of `../results_2026-11-28/assoc` (the association is the same as in the row above: `lit_keep` acts after Stage 1).  Every file has a `run_info.json`.
`lc_deep_litkeep/`, `lc_real_litkeep/`: the `label_changes.py` outputs of the new variant (the "all" rows are in `inputs/`).

The only cells in which the new row differs from `fixed+same_nearest+surveys2` are the two real-use cells (the blind sets, the low-latitude cones and the deep fields have no NED / SIMBAD rows, so `lit_keep` has
nothing to exempt there; that is by construction, not a measurement of safety):

| cell | `fixed+same,nearest+surveys2` | `+ lit_keep` |
|---|---|---|
| real-use primary labels changed (4,757 pairs) | 13 (from QSO 12) | **2** (from QSO 1) |
| real-use QSO labels NGC 4522 / COSMOS 2' / plane | 0 / 0 / 0 | 0 / **15** / 0 |
| QSO labels held by the survey-count switch, COSMOS 2' | 23 | 8 |
| low-latitude calibration 169 / confirmation 140: sample quasars, false QSO density, lost / gained | same | same |
| spectroscopic QSO held (32) | 0/32 | 0/32 |
| Chandra type 1 AGN lost (26 deep fields) | 0/123 | 0/123 |
| primary labels changed, 26 deep fields | 199 (from QSO 34) | 199 (from QSO 34) |

**Review of 2.62.7.** `decision_table.csv` was rebuilt with the merged tool, which carries 2.62.6's rule that a row whose association has no exchange table of its own leaves the four `assoc_new_joins_false_*` cells empty.  The first build put the `same_nearest` numbers in the two rows `fixed+same_nearest+surveys2` and `fixed+same_nearest+surveys2+lit_keep`, because it predates that rule.  Every other cell is unchanged.  The first nine rows are now identical to `../results_2026-11-28/decision_table.csv` cell by cell.  The tenth row differs from the ninth only in `history`, `real_labels_changed` (13 -> 2 of 4,757) and `real_use_qso_labels_ngc_cosmos_plane` (0 / 0 / 0 -> 0 / 15 / 0).

