# Ambiguity of the association stage (2.61.7)

Stage 1 turns a detection into a new object, `ambiguous_new`, when its second-best candidate scores at least 0.67 of the best.  This folder
measures how often that happens and what it costs, and holds the default-off switches that were tried against it.  Reports:
`v2/WORK_REPORT_2026-11-27f.md` (Korean, with the design reasons), literature: `v2/LITERATURE_ASSOCIATION_AMBIGUITY_2026-11-27.md`,
predictions and the adoption rule (written before any variant was run): `PREDICTIONS.md`.

## The switches (`V2_ASSOC_AMBIG`, a comma list, default empty = no change)

| option | what it does |
|---|---|
| `profiles` | position errors for catalogues that fell to the 0.6'' default: SDSS point sources brighter than psfMag_r 20 get 0.1'' (Pier et al. 2003) and every SDSS row its imaging epoch; VLASS 0.5'' (Dec >= -20 deg) / 1'' (Gordon et al. 2021); LoTSS errors plus 0.2'' (Shimwell et al. 2022) |
| `spectra` | LAMOST and SDSS spectra are targets like the DESI ones: a row within 0.3'' of an imaging row of a group joins it |
| `same` | the anchors of the two best candidates are closer than `V2_ASSOC_SAME_ARCSEC` (0.3''): they are one object, the best is taken |
| `nearest` | the nearest candidate is closer than `V2_ASSOC_NEAREST_SEP` (0.3'') and the next is `V2_ASSOC_NEAREST_RATIO` (3) times further: it is taken |
| `best` | never ambiguous (the literature reference: Marrese et al. 2017, 2019); not proposed |
| `all` | `profiles` + `spectra` + `same` + `nearest` |

With a switch the stage writes the column `ambiguity_resolution` (`same_object`, `nearest_clear`, `best` or empty).  `V2_ASSOC_DIAG=1` writes the two
best candidates of every detection (`diag_*`), nothing else reads them.

## Tools

| script | what it does |
|---|---|
| `run_stage1.py` | Stage 1 on many stored raw folders with a set of environment switches, one CSV per region, and the time |
| `analyse_ambiguity.py` | size of `ambiguous_new` by set, catalogue and local density; the share with a clear nearest candidate; the catalogue profile table |
| `candidate_truth.py` | for every `ambiguous_new` row of the COSMOS fields: which candidate was the right object (COSMOS2020 truth), and the grids behind the thresholds |
| `missed_by_path.py` | the share of the 2.60.9 association misses that went through `ambiguous_new` |
| `predict_from_calibration.py` | the joins each rule should make, from the calibration fields only |
| `compare_variants.py` | variants against the baseline on the COSMOS2020 association truth: rates, exchange table, field-bootstrap intervals, fragments |
| `label_changes.py` | primary-label changes of a variant, objects paired by position (ids are not comparable between runs) |
| `lowlat_exchange.py` | false QSO labels gained and lost at low latitude, objects paired by position |

## Reproduce (calibration: COSMOS fields 1-9, low-latitude calibration cones; confirmation: fields 10-26 and the confirmation cones)

```
V2_ASSOC_DIAG=1 python run_stage1.py --sets cosmos_orig9=cosmos:ROOT:FIELDS.csv ... --out DIR      # baseline with diagnostics
python analyse_ambiguity.py --stage1 DIR --out OUT ; python candidate_truth.py --stage1 DIR --truth-flux TRUTH --out OUT
bash ../association_truth/run_full.sh FIELDS_ROOT OUT 4 V2_ASSOC_AMBIG=same,nearest                     # full pipeline of a variant
python ../association_truth/measure_association.py --truth-flux TRUTH --assoc-dir OUT --out M/<variant> --variant <variant>
python compare_variants.py --measure M --variants base same_nearest all --out CMP
python ../faint_qso_candidates.py compare --deep DEEP --base base --variant all --out LABELS               # fixed / broken, McNemar
python label_changes.py --base OUT_BASE --variant OUT_VAR --fields deep_cosmos_1,... --out LC
# low latitude: v2/benchmark/lowlat_qso/ab_variants.py on the compact records, then lowlat_exchange.py; spectro_held.py for the spectroscopic QSOs
```

`results_2026-11-27f/` holds the tables: `baseline/` (size, catalogue profiles, candidate truth, predicted joins), `calibration/` and `confirmation/`.
