# u-band headroom measurement (2026-10-22, not adopted)

Question: would a u band (UV excess, Richards et al. 2002: u-g < 0.6 for z < 2.2 quasars) fix the classifier's remaining star/QSO/galaxy confusions?

## Data
- Targets (`targets.csv`): every QSO-related test error of 2.35.0 (DESI 51, SDSS 22) and 150 correct STAR/QSO test objects per set.
- VizieR 1.5″ cones (CDS XMatch did not answer from the GitHub runners on 2026-10-22):
  - SDSS DR16 V/154 (PSF `upmag`)
  - KiDS (II/347)
  - SkyMapper DR4 II/379 (`uPSF`)
- Stripe 82 co-add: no catalogue answered at the probe position.

## Result
- **Errors with u at S/N ≥ 5:**
  - DESI: 10 of 51 (20 %). The faint errors (r > 21) are below the single-epoch SDSS u depth (~22).
  - SDSS: 16 of 22.
- **DESI errors that u−g < 0.6 would correct:** at most 4 of the 9 with SDSS u.
  - Correctable: the 3 STAR→QSO cases (u−g = 0.73–1.37) and 1 QSO→STAR case (u−g = −0.40).
  - Not correctable: the 4 GALAXY→QSO cases are UV-blue (u−g ≤ 0.58), so u agrees with the wrong label.
  - Upper bound: +0.4 points on the 962-object test split.
- **SDSS errors that u could correct:** about 8 of 16, nearly all GALAXY↔QSO.
  - Many true QSOs labelled GALAXY are UV-red (u−g > 1): AGN in galaxies, or z > 2.5 quasars.
  - SDSS chose its QSO targets with ugriz colours, so a u gain on this set is biased upwards.
- **UVX on correctly classified objects with u:**

  | Test split | Stars with u−g < 0.6 | QSOs with u−g < 0.6 |
  |---|---|---|
  | DESI | 20 % (4/20) | 81 % (25/31) |
  | SDSS | 10 % | 87 % |

  As a separator, u alone (about 80–90 %) is weaker than the present classifier (about 98 % on bright objects), so it can only add marginal evidence.

## Decision
Not implemented.
- The upper bound on the DESI test is +0.4 points, the same scale as the GALEX UV features measured the same day: 92.41 → 92.62 %, McNemar p = 0.63, also not adopted.
- Deep u (KiDS, CFIS, Stripe 82 co-add, about 24 mag) covers few benchmark objects.
- The faint star/QSO overlap needs u ≳ 23.5 over the whole sky, or variability (LSST).
