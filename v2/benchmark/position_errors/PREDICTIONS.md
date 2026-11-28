# Predictions written before any pipeline output of this study was looked at (2.63.0, work order "카")

Written 2026-11-27, **committed before the first Stage-1 / pipeline run of the position-error study** (see `git log` order: this file and
the switch `V2_POSERR_UNITS` first, results later).  What was looked at before writing it: the raw VizieR rows (column names and value ranges, to find the units; `UNITS.md`), the code that reads them
(`association_model.infer_poserr_arcsec`), the fitted fusion weights (`fusion_weights.json`), the raw-row geometry below (distance from every
VLASS / NVSS row to the nearest optical row) and **one synthetic two-row Stage-1 experiment** (a PS1 row and a VLASS row 0.15-3'' apart, written
as the unit test `test_poserr_units.py`).  No pipeline output of the 335 regions had been looked at.  The first draft of this file predicted
+10-40 changed joins; the synthetic experiment showed that joins are not gated by the error alone (the join radius is ~5 combined sigma and the
PS1 pair floor, PSF / 6 = 0.2'', dominates it) and that the large change is the **anchor**, so predictions 2-4 below were rewritten before the first
real run and this note records that.

## What changes in the code

`infer_poserr_arcsec` read every `e_RAJ2000` / `e_DEJ2000` pair as arcsec.  Per catalogue (`UNITS.md`): VLASS = **degrees**, NVSS RA = **seconds
of time** (Dec arcsec), TGSS / LoTSS = arcsec.  The new default converts; `V2_POSERR_UNITS=legacy` restores the old reading.

## Inventory (raw rows, all three sets of this study)

| set | regions | VLASS rows | NVSS rows | VLASS rows with an optical row (LS / PS1 / SDSS / Gaia) within 0.3'' / 1'' / 2'' |
|---|---|---|---|---|
| deep COSMOS | 26 | 61 | 42 | 21 / 41 / 50 |
| low-latitude calibration | 169 | 179 | 111 | 38 / 53 / 75 |
| low-latitude confirmation | 140 | 144 | 69 | 18 / 49 / 59 |
| total | 335 | 384 | 222 | 77 / 143 / 184 |

So at most 143 of the 384 VLASS rows (37 %) have an optical row within 1'' to join; the study is small in absolute numbers by construction.

## Predictions

1. **Which rows change error.**  Only VLASS and NVSS rows.  Every other catalogue (LoTSS, TGSS, FIRST, eRASS1, 4XMM, Chandra, GALEX, AllWISE,
   2MASS, Gaia, PS1, SDSS, LS, SIMBAD ...) gets the identical `poserr_arcsec`: 0 rows differ (checked row by row over all raw files).
   VLASS: legacy value ~1e-4'' (held at 0.02'' by the pair floor) -> fixed median 0.08-0.2'' (x4-10).  NVSS: median +10-35 % where
   15 cos(dec) e_RA exceeds e_Dec, unchanged elsewhere.
2. **Association order and anchor** (the mechanism, from the synthetic experiment).  Stage 1 processes detections by position error, smallest first.
   Legacy: a VLASS row has ~1e-4'' and is processed before every row but a Gaia row with proper motion; it starts the group and every optical row
   joins *it* (anchor catalogue = VLASS, object position = the radio position, systematic 0.5-1'', Gordon et al. 2021 Sect. 2.1).  Fixed: 0.086'' sorts after
   PS1, Gaia and Legacy Surveys point sources (formal errors 0.01-0.1'') and still before resolved Legacy Surveys (0.6''), SDSS (0.6''), AllWISE (0.5'')
   and GALEX (0.8'').  Prediction: the number of objects whose anchor catalogue is VLASS **falls by 20-60 %** (from about 100-140: the VLASS rows that
   have an optical row within the join radius); where it changes, the object position moves by the radio-optical offset (median ~0.5'' in COSMOS).
3. **Joins.**  The join radius is ~5 combined sigma including the pair floors (PSF / 6): for PS1 0.200'' -> 0.218'' (+9 %), i.e. +0.1'' at a 1'' separation.
   Prediction: **at most 10 VLASS rows** (of 384) change between "joined to an object with a non-radio catalogue" and "separate", in both
   directions; NVSS <= 2 (beam 45'', errors 1-3'', PSF floor far larger than the change).  Object count changes by the same <= 10.
4. **Labels.**  The order says "X-ray / radio contribute 0 to the primary class".  That is **not exactly so**: `fusion_weights.json` holds fitted
   coefficients for `radio_log_r` (GALAXY +0.196, QSO +0.050, STAR -0.246) and `xray_log_fx_fo`; only the `*_detected` terms have weight 0.  A radio
   flux that joins a different object, or an anchor that moves by 0.5'', can move an object across the decision margin.  Prediction: **0-10
   primary-class changes** over the ~300 000 objects of the 335 regions (< 0.003 %), all among the objects of point 2-3; `compact_class` (pulsar
   candidates use NVSS + TGSS) 0-2 changes; `extragalactic_class` / `subclass` (they read Gaia AGN evidence and the primary label) 0-10 changes, none
   outside those objects.
5. **Default.**  Because the default behaviour changes (the anchor and the position of ~100 objects, a few joins, possibly a few labels) this is a MINOR candidate
   (2.63.0), with `V2_POSERR_UNITS=legacy` as the way back.

## What would show these wrong

* a catalogue other than VLASS / NVSS with a different `poserr_arcsec` (the unit table would be incomplete);
* more than 10 VLASS rows changing join status, an anchor change outside the 20-60 % band, or > 10 primary-class changes (the radio coefficients
  matter more than the 0.003 % guessed);
* fixed errors that make a VLASS row join an object at > 2'' (the 1''-0.5'' astrometric systematic of Gordon et al. 2021 Sect. 2.1 is not in the
  fixed error; `profiles` adds it and is measured as a third column).
