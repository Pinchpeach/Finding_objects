# Classification rule literature register

This file records the external basis for rules in `classification_rules.csv`.

## Pan-STARRS1 morphology — PS1-MORPH-001 / PS1-MORPH-002

- Tachibana, Y. & Miller, A. A. (2018), PASP 130, 128001, DOI 10.1088/1538-3873/aae3d9.
  https://iopscience.iop.org/article/10.1088/1538-3873/aae3d9
  Section 4.1 documents the baseline `iPSFMag-iKronMag > 0.05` resolved-source separator and its limitations.
- STScI/MAST Pan-STARRS Public Archive, *How to separate stars and galaxies*.
  https://outerspace.stsci.edu/spaces/PANSTARRS/pages/298812369/How+to+separate+stars+and+galaxies
  The PSF-Kron section documents the 0.05 i-band example, applicability to MeanObject, unreliability faintward of about i=21, and saturation caveats brighter than about i=14 in the shown sample.
- Farrow, D. J. et al. (2014), MNRAS 437, 748-770, DOI 10.1093/mnras/stt1933.
  https://doi.org/10.1093/mnras/stt1933
  Peer-reviewed PS1 star/galaxy separation background and validation.

Implementation policy: extended morphology supplies moderate GALAXY evidence only within 14 <= i <= 21 and valid i-band photometry. Point-like morphology supplies only weak STAR evidence because unresolved sources also include QSOs. Stage-4 numeric evidence scores are project fusion weights, not probabilities reported by the papers, and require later calibration against labelled validation data. No colour-only hard QSO/STAR/GALAXY cut is added yet because the reviewed literature supports trained/data-driven colour models rather than a portable calibrated threshold for this pipeline.

## Colour-selection rules

### WISE-AGN-R90-001
- Assef, R. J. et al. (2018), *The WISE AGN Catalog*, ApJS 234, 23, DOI 10.3847/1538-4365/aaa00a.
  https://iopscience.iop.org/article/10.3847/1538-4365/aaa00a
  Equation 4 recalibrates the AllWISE reliability-optimized R90 boundary:
  W1-W2 > alpha_R exp(beta_R (W2-gamma_R)^2) for W2>gamma_R, otherwise W1-W2>alpha_R,
  with (alpha_R90,beta_R90,gamma_R90)=(0.650,0.153,13.86).
  The published catalog is designed for ~90% reliability, but this is a sample-selection
  reliability, not a per-source posterior probability. The pipeline maps it to
  EXTRAGALACTIC/AGN evidence rather than QSO-only evidence.

### PS1-QSO-Z6-001
- Bañados, E. et al. (2016), *The Pan-STARRS1 Distant z>5.6 Quasar Survey*,
  ApJS 227, 11, DOI 10.3847/0067-0049/227/1/11.
  https://iopscience.iop.org/article/10.3847/0067-0049/227/1/11
  Section 2.1.1, equations (1)-(3), defines the i-dropout selection. The implemented
  measured-i branch requires i-z>2.0 and g S/N<3; for z-y<0.5 it additionally requires
  z S/N>10, y S/N>5 and r S/N<3 or r-z>2.2; for z-y>=0.5 it requires z and y S/N>7
  and r S/N<3. The paper emphasizes contamination by cool dwarfs and uses follow-up,
  so the rule is moderate candidate evidence rather than a definitive QSO label.
  The limiting-magnitude dropout branch is not implemented because the current PS1
  collector does not provide the per-source 3-sigma limiting magnitude needed to
  reproduce it faithfully.

## Colour rules deliberately not promoted to primary evidence
- 2MASS J-H/H-K colour regions overlap strongly among ordinary stars, galaxies and
  AGN and are sensitive to extinction/redshift. No portable 2MASS-only hard primary
  STAR/GALAXY/QSO rule was found that matches this pipeline's conservative standard.
- GALEX FUV-NUV is astrophysically informative but published selections generally
  depend on optical colour/morphology/redshift or target a narrower population.
  It remains a feature until a matching multi-band rule can be implemented.
- SDSS quasar target selection (Richards et al. 2002) uses distance from an empirical
  multi-dimensional stellar locus with photometric errors plus exclusion regions,
  not a small set of independent scalar colour thresholds. It should be implemented
  as a locus-distance model rather than approximated by ad-hoc cuts.

