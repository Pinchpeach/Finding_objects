# Predictions and adoption rule, written before any variant was run (2.61.7)

Written after the size of `ambiguous_new` was measured with the baseline Stage 1 (`analyse_ambiguity.py`, `candidate_truth.py`) and
before one variant was run on a COSMOS or low-latitude region.  Calibration = deep COSMOS fields 1-9 and the 169 low-latitude
calibration cones (150 quasar + 19 contaminant); confirmation = deep COSMOS fields 10-26 and the 140 low-latitude confirmation cones.

**Disclosure.**  The first `candidate_truth.py` table pooled all 26 COSMOS fields, so the confirmation fields were seen once (as
pooled counts) before the thresholds were fixed.  The table was then recomputed on fields 1-9 alone and the thresholds below were
read from that one (`same_object_by_c12.csv`, `nearest_rule_grid.csv` of the calibration run); they are round values that the pooled
table also supports.  Nothing of the low-latitude confirmation cones was read except the ambiguous-row counts of the diagnostics
(no truth, no label).

## Thresholds (calibration fields only)

| rule | value | calibration evidence (COSMOS2020 truth, fields 1-9) |
|---|---|---|
| `same`: two best candidates are one object | anchors of the two candidate groups closer than **0.3''** | resolving rows: 188 of 189 pairs share one truth source (99.5 %; 0.3-0.5'': 64 of 64, 0.5-0.8'': 62 %); AllWISE/GALEX rows: 24 of 26 (92 %) |
| `nearest`: the nearest candidate is clear | nearest **< 0.3''** and the next at least **3 times** further | resolving rows 132 joins, 0 wrong (Wilson upper 2.8 %); AllWISE 21 joins, 20 right, 0 wrong, 1 unknown |
| `best` | reference only: the best-scoring candidate always | GALEX: 6 wrong of 103 known (5.8 %) |

## Predicted joins on the calibration fields (`predict_from_calibration.py`)

Ambiguous rows that would join instead of anchoring a new object, and what the join is against COSMOS2020:

| rule | resolving rows (of 547) | AllWISE (of 143) | GALEX (of 149) | wrong joins |
|---|---|---|---|---|
| `same` | 202 (37 %) | 1 | 24 (16 %) | 0 of 214 with truth |
| `nearest` | 139 (25 %) | 21 (15 %) | 2 | 0 of 156 |
| `same` + `nearest` | 316 (58 %) | 22 (15 %) | 26 (17 %) | 0 of 346 |
| `best` | 547 (100 %) | 143 | 149 | 6 (all GALEX) of 614 with truth |

## Predictions for the confirmation sets (stated now, to be scored)

1. **Size.**  About 0.7-0.8 % of the COSMOS rows and 0.35 % of the low-latitude rows are `ambiguous_new` (new 17: 1534 of 208 500, low-latitude
   confirmation: 892 of 236 486, from the diagnostics only).  `same` + `nearest` resolve 55-60 % of the resolving-catalogue ones and 15-17 % of the
   AllWISE and GALEX ones in the confirmation fields too; `best` resolves all.
2. **COSMOS2020 association truth (fields 10-26), `same` + `nearest`.**  False rate of AllWISE, GALEX, 2MASS changes by at most +0.1 percentage
   points (0 wrong joins expected; unknown joins do not count as false).  Missed share of unjoined AllWISE rows falls by 0.3-1.0 points, GALEX by
   1-3 points.  `best` reaches AllWISE missed -2 to -4 points and GALEX -6 to -10 points but GALEX false +0.3 to +0.8 points.
3. **Fragments and duplicates.**  Top-level objects fall by about 0.1 % of the rows (resolving-row ambiguities that joined, 200-320 per 9 fields);
   the fraction of COSMOS2020 sources with an extra one-catalogue top-level object falls with it.  No new merge of two truth sources more than 2'' apart.
4. **`profiles`.**  Changes the status of fewer than 0.2 % of the rows; the main effect is on the SDSS point sources.  Risk stated: a tighter SDSS
   sigma (0.1'') can turn a few SDSS rows into new objects (no match within the acceptance); on deep COSMOS `all` of field 1 gave 7 more `new`
   rows than base.  Whether this increases fragments is part of what is measured.
5. **`spectra`.**  Brings spectroscopic QSOs held at low latitude (spectral class QSO, one survey) from 5 of 32 to at most 2 of 32 (LAMOST rows
   that `ambiguous_new` split from their photometric objects now join, 0.3'' target match).  `same` and `nearest` alone remove at most one of the five.
6. **Low-latitude QSO.**  Recall of the sample quasars with the survey switch unchanged (>= 3 surveys) does not fall; the false QSO density does not
   rise beyond the bootstrap interval.  Primary labels change on fewer than 0.3 % of the objects; changes are mostly UNKNOWN -> labelled when two
   surveys' rows end up in one object.
7. **Shuffle reproducibility** stays 0 differences for every variant (the new rules use only the sorted candidate list and the anchors).
8. **Stage 1 time** changes by less than 3 % (one extra `assess_pair` per ambiguous row).

## Adoption rule (a variant is proposed only if all hold on the confirmation sets; the default stays unchanged either way)

* COSMOS2020 false link rate (AllWISE, GALEX, 2MASS, pooled over the 17 fields) does not rise by more than +0.1 percentage points and
  the bootstrap interval of the paired difference includes 0 or is negative; wrong joins (known truth, different source) are at most 1 % of the joins;
* the missed share falls (the benefit exists), duplicates / fragments do not rise;
* low-latitude sample-quasar recall does not fall and the false QSO density does not rise outside its bootstrap interval;
* primary labels that change on COSMOS: more fixed than broken against COSMOS2020 (McNemar exact p reported);
* shuffle differences 0.

If false links rise the variant is not proposed and the exchange table (links gained against false links added) is the result.

**Correction (second commit, before any variant was run):** the first version of the `same` row of the threshold table said "189 of 191 pairs (98.9 %)"; the table `same_object_by_c12.csv` of the calibration run gives 188 of 189 (99.5 %).  Only that quoted evidence changed, not a threshold or a prediction.

## Addendum (calibration fields only, before any confirmation set was run): `profiles` was revised twice

Prediction 4 named the risk that a tighter SDSS sigma turns SDSS rows into new objects.  It happened and was measured on fields 1-9
(Stage 1, then the COSMOS2020 association truth and the fragment count of the full pipeline):

| version | SDSS rule | new objects (base 85 271) | matched (base 22 753) | extra one-catalogue objects next to a truth source (base 867) |
|---|---|---|---|---|
| v1 (commit 18d42c4) | every type 6 row 0.1'', galaxies 0.6'', no epoch | 85 366 (+95) | 22 693 | 889 (+22) |
| v2 | v1 + the imaging epoch from `mjd` | 85 331 (+60) | 22 739 | not run |
| v3 (final) | 0.1'' only for type 6 with psfMag_r < 20 (the range of the 45 mas of Pier et al. 2003), epoch from `mjd`; everything else 0.6'' | 85 274 (+3) | 22 775 | see the report |

The 330 SDSS rows v1 split from their Legacy Surveys / PS1 object lie 0.55'' (median) from it: faint type 6 "stars" are partly compact
galaxies and their centroids are photon-noise limited, which the 45 mas figure does not cover.  v3 is the version under test from here on; the
confirmation fields are run with v3 only.  The low-latitude `a_all` run that was in progress when v2 and v3 were written was deleted and
restarted from scratch with v3.

## Calibration results against the predictions, and the confirmation plan (written before any confirmation set is run)

Calibration = COSMOS fields 1-9, the 169 blind low-latitude cones (150 sample quasars) and the 15 low-latitude cones with a spectral-class QSO
object (the calibration part of the 32).  Final code (`profiles` v3).

| prediction | calibration result | verdict |
|---|---|---|
| 1 size, 55-60 % of resolving ambiguities and 15-17 % of AllWISE / GALEX ones resolved by `same`+`nearest` | Stage 1: 908 ambiguous rows of fields 1-9 fall to 539 (-369, cascade); joins 24 AllWISE, 25 GALEX, 3 2MASS (predicted 22, 26, 3) | held |
| 2 false rate within +0.1 pp, missed down | AllWISE false 2.69 -> 2.67 %, missed 41.7 -> 40.7 % (-1.0 pp, interval -1.4 to -0.7); GALEX false 4.99 -> 4.76 %, missed 93.8 -> 93.3 %; 0 new false links | held |
| 2 `best`: AllWISE missed -2 to -4 points, GALEX -6 to -10, GALEX false +0.3 to +0.8 | AllWISE missed -6.5 pp (more than predicted, 0 false), GALEX missed -5.3 pp, GALEX false +0.10 pp (6 wrong of 101 known joins, interval -0.5 to +0.9) | magnitudes off: `best` gains more on AllWISE and less on GALEX than predicted |
| 3 fragments down, no new merge | extra one-catalogue objects 867 -> 817 (`same`+`nearest`), 818 truth sources with fragments -> 782; merged objects 16 / 3 unchanged | held |
| 4 `profiles` changes < 0.2 % of rows | v1 failed (above); v3: new objects +3, matched +22, COSMOS association numbers and fragments unchanged | held for v3 |
| 5 `spectra` brings held spectroscopic QSOs from 5/32 to <= 2/32; `same` and `nearest` alone remove at most one of the five | calibration part: 3 of 14 held without a fix; `spectra`, `same`+`nearest` and `all` each hold 0 of 14 | first half held, **second half wrong**: `same`+`nearest` alone also release all three |
| 6 low-latitude recall does not fall, false density does not rise | blind 169: sample quasars labelled QSO 86 -> 88 (`same`+`nearest`) -> 91 (`all`) of 150; QSO objects that are not the sample quasar 170 -> 164 -> 160 (positions matched: 12 / 16 lost, 6 / 6 gained) | held |
| 7 shuffle differences 0 | 0 object differences and 0 status changes for `all` and `best` on two COSMOS fields and one spectroscopic cone, seeds 1-3 | held |
| 8 Stage 1 time within 3 % | 190-208 s for 178 regions in every variant (base 197 s) | held |
| primary labels change on < 0.3 % of objects | `same`+`nearest` and `all`: 58 of 85 770 objects (0.07 %), all to GALAXY (STAR 23, UNKNOWN 35), QSO labels 89 -> 89; truth-matched 25 943: 2 fixed, 1 broken (McNemar p = 1); `best`: 186 changed, 4 fixed, 10 broken (p = 0.18) | held |

**Confirmed on the confirmation sets (once, final code, nothing tuned afterwards):** `all` (= `profiles`, `spectra`, `same`, `nearest`), `same`+`nearest` (to separate
`profiles`, which is neutral on COSMOS but adds three quasars at low latitude) and, as the literature reference, `best`.  COSMOS fields 10-26 get the full pipeline for
`base`, `same`+`nearest`, `all`, `best`; the 140 blind low-latitude confirmation cones `same`+`nearest` and `all` against the existing `base`; the 17 low-latitude
confirmation cones with a spectral-class QSO object `base`, `same`+`nearest`, `spectra`, `all` with each survey switch.

Point predictions for the confirmation, from the calibration per row (fields 10-26 hold 1.9 times the rows of fields 1-9): `same`+`nearest` newly joined AllWISE rows
40 +- 15, GALEX 35 +- 15, no known-false join (upper bound 3); AllWISE missed -0.8 to -1.2 pp, GALEX -0.3 to -0.7 pp; extra fragment objects -70 to -110;
labels changed 100 to 150 objects (0.07 % of ~165 000), QSO labels unchanged +- 2.  Low latitude: sample quasars labelled QSO +1 to +4 of 140 for `all`, false QSO
objects not above the base; spectroscopic QSO objects held by `surveys2` / `surveys3` without a fix 0-5 of 17, with any variant 0 of 17.  The adoption rule above is unchanged.
