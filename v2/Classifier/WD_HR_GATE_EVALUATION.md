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

## 2.53.0: error-aware locus (literature review 2026-11-13)

GF21 do not stop at the Eq. 1 line: they give each source a probability
P_WD that carries its measurement errors and recommend P_WD > 0.75.  Their
map (built from SDSS spectra) is not available offline, so the gate now uses
the probability that the source lies on the WD side of the Eq. 1 line given
its errors:

- M_G > 6 + 5(BP−RP) exactly when ϖ > ϖ_line = 10^((16 + 5(BP−RP) − G)/5);
- P = Φ((ϖ − ϖ_line) / √(σ_ϖ² + (ϖ_line ln10 σ_c)²)), σ_c from the BP and RP
  flux errors (first order; the G error is negligible);
- on the locus at P ≥ 0.75, off it at P ≤ 0.25, abstain in between, after the
  same parallax / proper-motion significance gate (`plx4_or_pm10_p75`).

Local mixed benchmarks (Gaia features preserved with the benchmarks; SDSS
split by the benchmark manifest):

| set | gate | flagged | true WD | false WD | P | R | F1 |
|---|---|---:|---:|---:|---:|---:|---:|
| SDSS train (82 WD) | plx4_or_pm10 | 108 | 74 | 34 (28 STAR, 6 QSO) | 0.685 | 0.902 | 0.779 |
| | **plx4_or_pm10_p75** | 103 | 74 | 29 (23 STAR, 6 QSO) | 0.718 | 0.902 | **0.800** |
| | plx4_or_pm10_p90 | 100 | 73 | 27 | 0.730 | 0.890 | 0.802 |
| SDSS test (68 WD) | plx4_or_pm10 | 66 | 59 | 7 | 0.894 | 0.868 | 0.881 |
| | **plx4_or_pm10_p75** | 63 | 59 | 4 | 0.937 | 0.868 | **0.901** |
| | plx4_or_pm10_p90 | 60 | 57 | 3 | 0.950 | 0.838 | 0.891 |
| DESI DR1 (42 WD) | plx4_or_pm10 | 42 | 31 | 11 | 0.738 | 0.738 | 0.738 |
| | **plx4_or_pm10_p75** | 39 | 31 | 8 | 0.795 | 0.738 | **0.765** |
| | plx4_or_pm10_p90 | 36 | 28 | 8 | 0.778 | 0.667 | 0.718 |

t = 0.75 (GF21's recommended cut on their own probability) removes false WDs
without losing true ones on every set; t = 0.9 is level on the train split
and loses WDs on the others.  The remaining false WDs are stars (hot
subdwarfs, WD+MS pairs, CVs), as before.

The crossmatched truth sets of the original evaluation
(`evaluate-wd-hr-gates.yml`, run 43572719091, 2026-11-14; CDS XMatch was
down, so the Gaia crossmatch used the VizieR batch fallback):

| set | gate | flagged | true WD | false WD | P | R |
|---|---|---:|---:|---:|---:|---:|
| SDSS DR18 STAR (489 WD) | plx4_or_pm10 | 411 | 407 | 4 | 0.990 | 0.832 |
| | **plx4_or_pm10_p75** | 408 | 406 | 2 | 0.995 | 0.830 |
| | plx4_or_pm10_p90 | 400 | 398 | 2 | 0.995 | 0.814 |
| LAMOST DR5 external (475 DA) | plx4_or_pm10 / **p75** / p90 | 472 | 472 | 0 | 1.000 | 0.994 |
| SDSS mixed classes (144 WD) | plx4_or_pm10 | 164 | 127 | 37 (31 STAR, 6 QSO) | 0.774 | 0.882 |
| | **plx4_or_pm10_p75** | 156 | 127 | 29 (23 STAR, 6 QSO) | 0.814 | 0.882 |
| | plx4_or_pm10_p90 | 150 | 124 | 26 (21 STAR, 5 QSO) | 0.827 | 0.861 |

LAMOST is unchanged; on both SDSS sets the error-aware gate removes false
WDs (4 → 2, 37 → 29) for at most one true WD, so `plx4_or_pm10_p75` stays the
default.  The remaining false WDs are stars, as before.
