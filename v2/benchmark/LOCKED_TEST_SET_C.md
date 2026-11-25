# Locked test set C: protocol (2.51.0)

## Why
- The scientific review (`SCIENTIFIC_REVIEW_2026-11-11.md` 3.3, 6.5) found that every headline number after 2.40.2 comes from data that were looked at while the pipeline was tuned:
  - sets A and B;
  - the 520 reference objects;
  - COSMOS;
  - the SDSS / DESI benchmarks.
- The only clean measurement was the first set-B score.
- A test set that is never looked at object by object gives an unbiased number. It is the standard train / validation / test split (Hastie, Tibshirani & Friedman 2009, sec. 7.2), applied to sky regions.

## The set
- 60 regions, 12′ radius, chosen by `select_fields_c.py`.
- Every region is at least 3.5° from:
  - sets A and B;
  - the COSMOS deep fields;
  - each other.
- The regions come from three pools of the Fibonacci sky grid, taken in a fixed order that differs from set B:

  | Pool | Regions | Where |
  |---|---|---|
  | csth | 18 | Dec ≤ −20°, \|b\| ≥ 25° (DES / LS-south) |
  | cpln | 12 | 5° ≤ \|b\| < 15° (low latitude, never measured before) |
  | clam | 30 | −5° ≤ Dec ≤ 60°, \|b\| ≥ 15° (LAMOST / PS1 / LS-north) |

- Set B's SGP, NGP and Stripe 82 pools have no free region left 3.5° from sets A and B, so they are not used.
- The list `fields_c.csv` is locked by its SHA-256: `21c42406ce3700ce7c271f2773a81297484e4f7543a821aaa05cf521f378b7e4`.
- The workflow refuses to run if the file changes.
- The truth catalogues, the centring on the densest truth cone and the blind run (spectroscopic and literature catalogues dropped) are the same as for set B.

## Rules
1. **Once per release.**
   - Run `v2_locked_set_c.yml` (workflow_dispatch) after `v2/VERSION` is bumped.
   - It refuses a VERSION that already has `locked_c/<VERSION>/`.
2. **Aggregate only.** The run commits only `locked_c/<VERSION>/summary.csv`, `summary_by_pool.csv` (2.57.0), `score.log` and `run.json`:
   - accuracy with a field-bootstrap 95 % CI;
   - balanced accuracy with CI;
   - per-class recall and precision;
   - the majority-class and Gaia DSC baselines;
   - the unmatched-truth rate.

   Per-object errors and probabilities are not written (`compare_ab_fields.py --aggregate-only`). Run artifacts expire after 7 days.

   **By pool (2.57.0).** `summary_by_pool.csv` repeats the accuracy (field-bootstrap CI), balanced accuracy, per-class recall and precision and the baselines for each pool of `fields_c.csv` separately (csth, cpln, clam; `compare_ab_fields.py --by-pool`, `field_stats.by_pool`). The 2.51.0 notes asked for it: the all-region number is dominated by the 30 clam regions, and the low-latitude pool (cpln) was never reported on its own. A pool is 12-30 regions chosen by one sky rule, so its aggregate is no more per-object than the all-region one. The scores below (2.51.0, 2.52.0) were taken before it existed and have no pool split; it starts with the next release's look. The rule does not change: no tuning on a pool's number either.
3. **No tuning.**
   - Do not change a rule, threshold or weight because of a set-C number.
   - A drop on C is reported in the CHANGELOG with the release. Investigate it on sets A / B / COSMOS, never on C.
4. **Healthy archives only.**
   - The score job checks each region's collection summary.
   - If gaia_dr3, desi_legacy, panstarrs1, allwise or twomass failed (error / timeout) in more than 10 % of the regions, or fewer than 54 regions finished, it stops before writing `locked_c/<VERSION>/`. The release's single look is not spent.
   - Re-run when the archives recover.
   - Reason: on 2026-11-11 VizieR answered 404 and NOIRLab 502 for hours, and every field run of that day lost AllWISE / 2MASS or Legacy Surveys.
   - **Collection conditions (2.60.4).** `run.json` also records which Gaia each region used (`gaia_source_regions`: `tap` = ESA archive, `vizier_fallback` = the VizieR DR3 copy), the Gaia release and how many regions lost each core survey (`core_failed_regions`). These are region counts, not per-object output. A later look (the Gaia DR4 switch) needs them to tell a Gaia effect from an archive-day effect: between 2.51.0 and 2.52.0 the archives alone moved Gaia DSC coverage from 91.5 % to 97.8 %.
   - **Blind input kept 90 days (2.60.4).** Each region's blind raw catalogues and truth are uploaded as a 90-day artifact (`craw-<region>`), not committed. Purpose: classify the same input again with only Gaia replaced (DR4) and score the difference in aggregate. Rule 2 still holds: the input is opened only by the aggregate scoring, never object by object (rule 5). It is not committed to `validation-data` because the input together with the truth would let anyone rebuild per-object errors at any time; an artifact that expires after the one comparison it serves keeps that risk bounded. If the DR4 comparison cannot run before the artifacts expire, decide then whether to move them.
   - **Collection step (2.60.8).** The set-C workflow collects with `V2_SKIP_COLLECTORS=blind`: the blind run drops the spectroscopic and literature collectors (NED, SIMBAD, LAMOST/SDSS/DESI spectra, BZCAT, AGB, ATNF, clusters) anyway, and NED asks for no concurrent automated queries, which a matrix of 20 parallel jobs makes. The gate below reads only the core collectors, so it is unchanged. Scores stay comparable across this change (2.60.8 review): the 14 skipped collectors are exactly the 14 files the blind copy has always removed, so the blind input is the same by construction. The 2.60.4 look collected them and dropped them; later looks do not ask for them. The Gaia-source record and the 90-day blind input above are unaffected.
5. **Retirement.**
   - If C is ever examined object by object, it becomes a development set.
   - A new set D is then selected the same way, excluding A, B, C and COSMOS.
   - Record the retirement here.

## Scores
| VERSION | regions scored | objects | accuracy (95 % CI) | balanced accuracy (95 % CI) | note |
|---|---|---|---|---|---|
| 2.51.0 | 60 (58 with truth) | 3,150 | 99.62 % (99.34–99.86) | 93.95 % (79.33–99.47) | first look, 2026-11-12, archive health check passed. See the reading notes below the table. |
| 2.52.0 | 60 (59 with truth) | 3,170 | 99.65 % (99.40–99.86) | 94.03 % (81.87–99.45) | 2026-11-14, commit `16cfdc3`. Third attempt: the first two (11-13, 11-14) stopped at the archive gate when Legacy Surveys timed out. No core collector failed this time. See the reading notes. |
| 2.60.4 | 60 (59 with truth) | 3,162 | 99.65 % (99.40–99.86) | 94.02 % (81.87–99.45) | 2026-11-25, commit `a1dc84f`, run 45590188973. Coarse code of 2.60.2 / 2.60.3. Second attempt: the first (run 45583226997, same day) stopped at the archive gate when the Data Lab TAP answered 502 in 40 regions. No core collector failed this time. Gaia: ESA archive in 57 regions, VizieR DR3 copy in 3. First look with the pool split. See the reading notes. |

**Reading the 2.51.0 score**
- **Composition:** the truth mix is about 95.5 % stars. The majority-class baseline is 95.46 %.
- **Small classes:** going by the recall and precision values there are only ~136 galaxies and ~7 QSOs. The QSO numbers (recall 85.7 %, precision 75.0 %) and the balanced-accuracy interval carry little weight.
- **Gaia DSC comparison:** on the 91.5 % of objects that have DSC, DSC scores 99.31 % and the pipeline 99.83 %.
- **Unmatched truth:** 1.65 %. Truth objects with single-catalogue fragments nearby: 743.
- **Not reported:** per-pool scores (the low-latitude pool `cpln` included) are not part of the aggregate. From the next release the aggregate should be split by pool, still aggregate only.

**Reading the 2.52.0 score**
- **Same as 2.51.0 within the noise:** 11 errors in 3,170 objects against 12 in 3,150.
  - Stars 5 against 6, galaxies 5 against 5, QSO 1 against 1 (counts recovered from the recall, precision and baseline values).
  - The intervals overlap almost entirely.
- **No change was expected.** 2.52.0 moved the faint star:galaxy prior (COSMOS test regions +1.66 points). Set C's truth is spectroscopic and ~95 % stars, with only ~144 galaxies and ~7 QSOs. The score is consistent with that; it does not confirm the COSMOS gain.
- **The data are not identical.** In the 2.51.0 look desi_legacy failed in 5 of the 60 regions (8.3 %, under the 10 % gate); this time no core collector failed.
  - This look scored 20 more truth objects, one more region with truth, and Gaia DSC coverage rose from 91.5 % to 97.8 %.
  - The code between the two commits does not change collection: only the prior layer and the extra columns the truth script keeps. So these differences come from the archives on each day.
  - Per-object records are not kept (rule 2), so they are not traced further.
- **Baselines:** majority class 95.24 %. On the 97.8 % with DSC, Gaia DSC scores 99.52 % and the pipeline 99.81 %.
- **Unmatched truth:** 1.61 %. Truth objects with fragments: 744.
- **Still not reported:** the per-pool split planned in the 2.51.0 notes. It needs a change to the score job before the next look.
- **2.53.0 and 2.53.1 are not scored.** They change only sub-classes and validation inputs; the coarse-class code (`v2/Preprocess`) is the same as 2.52.0, and set C scores the coarse class only.

**Reading the 2.60.4 score (2026-11-25)**
- **Why now:** 2.55.0 changed the coarse path for sources without an r detection, so the coarse class changed after the last look (2.52.0). It is also the Gaia DR3 baseline before the Gaia DR4 switch (`v2/GAIA_DR4_READINESS_2026-11-25.md`, protocol (라)).
- **Same as 2.52.0 within the noise:** 11 errors in 3,162 objects against 11 in 3,170: stars 5, galaxies 5, QSO 1 in both (counts recovered from the recall values and class totals 3,012 / 143 / 7). Accuracy, its interval and the balanced accuracy agree to 0.01 point. No change was expected either: the 2.55.0 path concerns faint objects without an r detection, and set C's spectroscopic truth is bright.
- **Baselines:** majority class 95.26 %. On the 98.0 % with Gaia DSC, DSC scores 99.52 % and the pipeline 99.81 %, the same as in 2.52.0.
- **By pool** (`summary_by_pool.csv`, first time):

  | Pool | Regions with truth | Objects (STAR / GALAXY / QSO) | Accuracy (95 % CI) | Balanced accuracy | Majority class | DSC / pipeline on DSC (coverage) |
  |---|---|---|---|---|---|---|
  | clam (LAMOST / PS1 / LS-north) | 30 | 2,065 (2,008 / 50 / 7) | 99.61 % (99.31–99.86) | 93.17 % | 97.24 % | 99.51 / 99.76 % (98.9 %) |
  | cpln (low latitude) | 11 | 879 (879 / 0 / 0) | 99.89 % (99.61–100) | – | 100 % | 100 / 100 % (99.2 %) |
  | csth (DES / LS-south) | 18 | 218 (125 / 93 / 0) | 99.08 % (97.22–100) | 98.92 % | 57.34 % | 97.30 / 99.46 % (84.9 %) |

  - **cpln** is the first number for the low-latitude regions. Its truth there is 879 spectroscopic stars and nothing else, so it measures only whether bright stars stay stars in crowded fields (one did not). The always-STAR answer scores 100 % on it. It says nothing about galaxies or QSOs behind the plane, and nothing about r > 20 there (the overview's "not validated" statement stands).
  - **csth** is the only pool with a galaxy-rich truth (93 galaxies). There the pipeline is 2.2 points above Gaia DSC on the objects DSC covers, but on 218 objects the interval is wide. Its 2 errors are both galaxies, and at least one of them was labelled QSO, though the pool's truth has no QSO (QSO precision 0 % there).
  - **clam** holds 65 % of the objects and all 7 QSOs, so it dominates the all-region number.
- **Collection conditions** (`run.json`, 2.60.4): no core collector failed (gaia_dr3, desi_legacy, panstarrs1, allwise, twomass: 0 regions each). Gaia DR3 came from the ESA archive in 57 regions and from the VizieR copy in 3 (cpln_310p53, clam_317p12, clam_283p35: in these three the collector's ESA query failed or ran past its time budget, and it fell back to the copy. This was before the archive's announced shutdown at 11:00 UTC.). The copy changed 6 of 26,024 coarse labels in the deep COSMOS comparison (`WORK_REPORT_2026-11-24.md`).
- **Fragments:** truth objects with single-catalogue fragments nearby fell from 744 to 555. This is the fragment folding of 2.54.0; it does not enter the accuracy.
- **Unmatched truth:** 1.86 % (2.52.0: 1.61 %).
- **Blind input for the Gaia DR4 comparison:** the `craw-<region>` artifacts of run 45590188973 (90 days, until about 2027-02-23). The first attempt's artifacts lack Legacy Surveys in 40 regions and are not used.
- **2.53.0–2.60.3 are not scored separately.** This is the first look since 2.52.0, so it covers every coarse-class change made in between (the r-undetected path of 2.55.0 among them) together, not one by one.
