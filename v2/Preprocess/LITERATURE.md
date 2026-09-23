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

## Decision-tree architecture

### DT-HIER-001
The pipeline now uses an interpretable hierarchical decision tree for final
classification while retaining the evidence probability vector as a fallback.
The hierarchy is: spectroscopy -> curated physical type -> Gaia DSC ->
two-indicator Galactic astrometry -> extended morphology -> validated
class-specific colour selection -> probability-vector consolidation -> UNKNOWN.

This is intentionally not presented as a trained decision tree. Published
astronomical tree classifiers learn split locations from large labelled
spectroscopic samples; our current 167-source field is far too small and sparse
to learn such a tree without severe overfitting. Therefore DT-HIER-001 uses
evidence precedence and literature-supported catalog semantics, while marking
the Gaia DSC 0.80 acceptance threshold as PROJECT policy pending calibration.

Key methodological references:
- Ball, N. M. et al. (2006), ApJ 650, 497, DOI 10.1086/507440,
  *Robust Machine Learning Applied to Astronomical Data Sets. I. Star-Galaxy
  Classification of the Sloan Digital Sky Survey DR3 Using Decision Trees*.
  https://iopscience.iop.org/article/10.1086/507440
  Decision trees trained on 477,068 spectroscopically labelled SDSS objects;
  demonstrates probability outputs and explicitly warns about extrapolation
  beyond the magnitude regime represented by the training set.
- Suchkov, A. A., Hanisch, R. J. & Margon, B. (2005), AJ 130, 2439,
  DOI 10.1086/497363, *A Census of Object Types and Redshift Estimates in the
  SDSS Photometric Catalog from a Trained Decision-Tree Classifier*.
  https://iopscience.iop.org/article/10.1086/497363
  ClassX used ten oblique decision trees with weighted voting and returned class
  probability distributions. Independent validation reported approximately
  98.1% star, 98.5% galaxy, and 96.5% AGN completeness in its SDSS validation
  sample, while documenting class overlap and training-set dependence.
- Vasconcellos, E. C. et al. (2011), AJ 141, 189,
  DOI 10.1088/0004-6256/141/6/189, *Decision Tree Classifiers for Star/Galaxy
  Separation*.
  https://iopscience.iop.org/article/10.1088/0004-6256/141/6/189
  Compared 13 tree algorithms on spectroscopically labelled SDSS DR7 data.
  Performance depends strongly on magnitude; the selected Functional Tree kept
  >80% faint-end completeness with about 2.5% contamination, demonstrating why
  a tree must be validated in the regime where it is applied.
- Delchambre, L. et al. (2023), A&A 674, A31,
  *Gaia DR3 Apsis III: Non-stellar content and source classification*.
  https://www.aanda.org/articles/aa/full_html/2023/06/aa43423-22/aa43423-22.html
  Gaia DSC Specmod itself uses an ExtraTrees ensemble over BP/RP spectral
  samples; Combmod combines it with an independent GMM classifier. Gaia's
  classlabel_dsc requires maximum Combmod probability >0.5, while the joint
  label requires independent classifiers to agree and is purer. The paper also
  cautions that extragalactic purity varies with priors, magnitude and sky
  position.
- Clarke, A. O. et al. (2020), A&A 639, A84,
  *Identifying galaxies, quasars, and stars with machine learning*.
  https://www.aanda.org/articles/aa/full_html/2020/07/aa36770-19/aa36770-19.html
  Random-forest classification of SDSS+WISE sources trained on millions of
  spectroscopic labels illustrates the value of ensembles of decision trees,
  class probabilities, feature importance, and held-out validation.

Design consequence: the present tree is a conservative expert hierarchy, not a
claim that literature performance numbers transfer to this NGC 4522 sample.
A future trained tree/random forest should be learned from a large external
spectroscopic training set matched to exactly the same Gaia/PS1/WISE/2MASS
features, with train/validation/test separation and magnitude/sky-domain checks.

