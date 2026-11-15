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
2. **Aggregate only.** The run commits only `locked_c/<VERSION>/summary.csv`, `score.log` and `run.json`:
   - accuracy with a field-bootstrap 95 % CI;
   - balanced accuracy with CI;
   - per-class recall and precision;
   - the majority-class and Gaia DSC baselines;
   - the unmatched-truth rate.

   Per-object errors and probabilities are not written (`compare_ab_fields.py --aggregate-only`). Run artifacts expire after 7 days.
3. **No tuning.**
   - Do not change a rule, threshold or weight because of a set-C number.
   - A drop on C is reported in the CHANGELOG with the release. Investigate it on sets A / B / COSMOS, never on C.
4. **Healthy archives only.**
   - The score job checks each region's collection summary.
   - If gaia_dr3, desi_legacy, panstarrs1, allwise or twomass failed (error / timeout) in more than 10 % of the regions, or fewer than 54 regions finished, it stops before writing `locked_c/<VERSION>/`. The release's single look is not spent.
   - Re-run when the archives recover.
   - Reason: on 2026-11-11 VizieR answered 404 and NOIRLab 502 for hours, and every field run of that day lost AllWISE / 2MASS or Legacy Surveys.
5. **Retirement.**
   - If C is ever examined object by object, it becomes a development set.
   - A new set D is then selected the same way, excluding A, B, C and COSMOS.
   - Record the retirement here.

## Scores
| VERSION | regions scored | objects | accuracy (95 % CI) | balanced accuracy (95 % CI) | note |
|---|---|---|---|---|---|
| 2.51.0 | 60 (58 with truth) | 3,150 | 99.62 % (99.34–99.86) | 93.95 % (79.33–99.47) | first look, 2026-11-12, archive health check passed. See the reading notes below the table. |
| 2.52.0 | 60 (59 with truth) | 3,170 | 99.65 % (99.40–99.86) | 94.03 % (81.87–99.45) | 2026-11-14, commit `16cfdc3`. Third attempt: the first two (11-13, 11-14) stopped at the archive gate when Legacy Surveys timed out. No core collector failed this time. See the reading notes. |

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
