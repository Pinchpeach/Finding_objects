# Position-error inputs of Stage 1 (2.63.0)

`association_model.infer_poserr_arcsec` gives every detection a 1-sigma position error; Stage 1 orders the detections by it (smallest first) and scores
every pair with it.  This folder is the measurement of whether the columns it reads are in the units it assumes.

| file | what it is |
|---|---|
| `PREDICTIONS.md` | written and committed **before** the first Stage-1 / pipeline run of the study (git order: this file and the switch, then the results) |
| `UNITS.md` | the table: collector column, documented unit, evidence level, what the code assumed, verdict.  Only VLASS (degrees) and NVSS RA (seconds of time) were wrong |
| `check_units_from_rows.py` | row by row over every stored raw file: which rows change their error between `V2_POSERR_UNITS=legacy` and `fixed` (22 catalogues, 860 000 rows: only VLASS and NVSS) and the unit evidence; writes `regions_changed.csv`, the 179 regions the rest of the study runs |
| `dump_vizier_units.py` | prints the unit / description VizieR itself stores for the columns (needs the network; closes the "none" entries of `UNITS.md`) |
| `run_pe.py` | the full pipeline on those regions once per mode, slim outputs |
| `compare_by_members.py` | the two runs compared by what the objects are made of (`detection_id` sets), not by position: the anchor of an object moves when the radio row stops being the anchor |
| `results_2026-11-27h/` | the tables of the study (`rows_changed.csv`, `unit_evidence.csv`, `regions_changed.csv`, the comparison tables) |

Reproduce (paths of the raw folders are the ones of `benchmark/lowlat_qso` and `benchmark/deep_cosmos`):

```
python check_units_from_rows.py --roots <cosmos raw> <low-lat calibration raw> <low-lat confirmation raw> <real-use raw> --out results_2026-11-27h
python run_pe.py --regions results_2026-11-27h/regions_changed.csv --out OUT --roots raw=... ll_run=... ll_conf=... B1=... --cosmos-fields fields_all26.csv
python compare_by_members.py --a OUT/legacy --b OUT/fixed --regions results_2026-11-27h/regions_changed.csv --out results_2026-11-27h/compare
```

`V2_POSERR_UNITS=legacy` reproduces the results of every release before 2.63.0 exactly.
