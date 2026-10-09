# Gaia HR white-dwarf locus: quality-gate evaluation (2026-10-08)

## Question

`branches/star.py` emits `WHITE_DWARF_CANDIDATE` from the Gaia HR locus
`M_G > 6 + 5(BP-RP)` alone when Gaia DSC is unavailable. The previous gate,
`parallax_over_error > 1`, is only the **first-stage preselection** of
Gentile Fusillo et al. (2021, MNRAS 508, 3877); that paper follows it with
astrometric/photometric quality cuts and a WD probability map. With a
low-S/N parallax, `5 log10(parallax)` makes faint extragalactic sources look
intrinsically faint and land on the WD locus.

## Literature basis

- Gentile Fusillo+2021: HR locus; parallax-significance branch
  `parallax_over_error >= 4`, with an alternative branch accepting
  significant total proper motion (`pm/pm_err > 10`).
- Riello+2021 (A&A 649, A3): corrected BP/RP excess
  `C* = C - f(BP-RP)` (Eq. 6, Table 2) and its 1-sigma scatter
  `sigma_C*(G) = 0.0059898 + 8.817481e-12 G^7.618399` (Eq. 18).
- RUWE <= 1.4 as the conventional single-star astrometric quality limit.

## Truth sets (all spectroscopic, Gaia DR3 via CDS XMatch, 2 arcsec)

| set | rows | WD | non-WD |
|---|---:|---:|---:|
| SDSS DR18 STAR truth (`star_truth.csv`) | 974 | 489 | 485 normal stars |
| LAMOST DR5 external (`lamost_star_external_truth.csv`) | 977 | 479 DA | 498 normal stars |
| SDSS mixed classes (`benchmark/truth_data/ground_truth.csv`) | 8736 | 144 | 3264 STAR, 3287 QSO, 2185 GALAXY |

The mixed set is the realistic contamination test: it contains the faint
extragalactic sources that a field classification actually meets.

## Results (`evaluate-wd-hr-gates.yml`, run 37773303733)

Precision / recall of HR-locus `WHITE_DWARF` flags.

| gate | SDSS STAR P / R | LAMOST P / R | mixed P / R | mixed false WDs (QSO / STAR / GAL) |
|---|---|---|---|---|
| broad (`plx/err > 1`, previous) | 0.989 / 0.879 | 1.000 / 0.994 | 0.592 / 0.917 | 52 / 38 / 1 |
| plx4 | 0.994 / 0.691 | 1.000 / 0.994 | 0.820 / 0.729 | 4 / 19 / 0 |
| plx4 + C* < 3 sigma | 0.994 / 0.679 | 1.000 / 0.983 | 0.825 / 0.722 | 3 / 19 / 0 |
| plx4 + C* < 5 sigma | 0.994 / 0.681 | 1.000 / 0.985 | 0.825 / 0.722 | 3 / 19 / 0 |
| plx4 + C* < 5 sigma + RUWE | 0.994 / 0.679 | 1.000 / 0.971 | 0.825 / 0.722 | 3 / 19 / 0 |
| **plx4 or pm/err > 10** | 0.990 / 0.830 | 1.000 / 0.994 | **0.774 / 0.882** | **6 / 31 / 0** |
| plx4 or pm/err > 10, + C* < 5 sigma | 0.990 / 0.820 | 1.000 / 0.985 | 0.778 / 0.875 | 5 / 31 / 0 |

## Decision

Default gate: **`plx4_or_pm10`**.

- Mixed-class F1 0.72 -> 0.82; QSO false WDs 52 -> 6.
- LAMOST external performance unchanged (P = 1.000, R = 0.994).
- C* and RUWE add almost nothing once parallax/proper-motion significance is
  required, and cost recall, so they are kept as options, not defaults.

Sources that fail the gate return `None` (abstain), not `False`, so they do
not create a spurious conflict with Gaia DSC.

## Remaining limitation

About 31 non-WD SDSS STAR spectra still fall on the locus under the default
gate (likely hot subdwarfs, CVs and WD+M composites, which share the region).
Separating these needs spectroscopy or Gaia XP, not a tighter HR cut.
