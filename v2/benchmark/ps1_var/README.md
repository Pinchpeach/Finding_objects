# PS1 multi-epoch variability headroom (2026-10-22)

Question: do quasars' stochastic variations (MacLeod et al. 2010) in the Pan-STARRS1 3π epochs separate the stars and quasars the classifier still confuses?

## Data
- Same 373 targets as `../u_band/targets.csv`: every QSO-related test error of 2.35.0 plus 300 correct STAR/QSO test objects.
- PS1 DR2 MeanObject from the MAST catalogs API, 1.5″ cone: per-band `MeanPSFMagStd`, `MeanPSFMagNpt`, `MeanPSFMagErr`.
- Hernitschek et al. 2016 (VizieR J/ApJ/817/73): nothing at the probe position, so not used.

## Index
`vx` = per-band PSF-magnitude scatter divided by the median scatter of correct STAR objects at the same magnitude (0.5-mag bins). The median over g, r, i is used, needing ≥ 5 epochs per band.

`Std/(Err·√N)` has a median of 1.08–1.14, so `MeanPSFMagErr` is the error of the mean.

## Result
- **Coverage:** ≥ 5 epochs for 59 of 73 errors (DESI 37 of 51) and for 271 of 300 correct objects.
- **Correct objects, fraction with vx > 1.5:**

  | Test split | Stars | QSOs | QSO median vx |
  |---|---|---|---|
  | DESI | 3 % | 36 % | 1.39 |
  | SDSS | 13 % | 69 % | 1.81 |

  A threshold alone separates stars from QSOs 81 % at r < 20 but only ~55 % at r > 20, so variability is useful as weighted evidence, not as a cut.
- **Extended objects:** galaxies have high `vx` (SDSS GALAXY→QSO errors: 1.7–6.0), from seeing-dependent PSF magnitudes of resolved sources. The index can only be used for point sources (star vs QSO).
- **Bayes update of the 2.35.0 star/QSO decisions:**
  - Method: multiply the odds by the leave-one-out KDE likelihood ratio of log vx.
  - DESI errors: 10 of 19 star↔QSO errors fixed, 0 broken.
  - DESI correct sample: 3 of 121 broken. Scaled to the test split that is ~12 broken, so the net is uncertain.
  - SDSS: nothing changes.

## Conclusion
- The upper bound is about +1 point on the DESI test (10 of 962).
- A proper measurement needs `vx` for the whole benchmark (re-collecting PS1 with `MeanPSFMagStd`/`Npt`, ~23,000 objects) and a fusion refit. The naive update above overstates the breakage risk as much as it may understate it.
