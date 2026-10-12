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



## Unit harmonisation (`units.py`, Stage 2)
Quantities measured by several catalogues are converted to one system and
added as `std_*` columns. The native columns are kept unchanged.

| quantity | standard | conversion | source |
|---|---|---|---|
| Legacy Surveys g r i z W1 W2 | AB mag | 22.5 − 2.5 log10(f [nanomaggy]); σ = 1.0857 / (f √ivar) | Dey et al. 2019; unWISE calibrated to AllWISE (Schlafly et al. 2019) |
| Pan-STARRS1 | AB mag | — | Tonry et al. 2012 |
| SDSS | AB mag | u − 0.04, z + 0.02 | SDSS DR14 flux-calibration notes |
| GALEX | AB mag | — | Morrissey et al. 2007 |
| AllWISE W1–W4 | AB mag | Vega + 2.699 / 3.339 / 5.174 / 6.620 | Jarrett et al. 2011; WISE Explanatory Supplement IV.4.h |
| 2MASS J H Ks | AB mag | Vega + 0.91 / 1.39 / 1.85 | Blanton & Roweis 2007 |
| Gaia G BP RP | Gaia (Vega) system, not converted | — | compared only with Gaia-system references |
| reddening | SFD E(B−V) | LS mw_transmission_g, R_g = 3.214; else GALEX E(B−V) | Schlafly & Finkbeiner 2011 |
| radio | mJy; 1.4 GHz equivalent | LoTSS 144 MHz and VLASS 3 GHz with α = −0.7 | Condon 1992 |
| redshift | spectroscopic z only | SDSS / DESI / LAMOST; NED z or v/c unless flagged photometric; SIMBAD → `std_z_catalog` | |

Consistency checks (median difference, NMAD), benchmark point sources:

| comparison | stars | quasars | why |
|---|---|---|---|
| LS − PS1 g | 0.003 (0.024), n = 3183 | | |
| LS − PS1 r | −0.059 (0.040), n = 3225 | | |
| LS − PS1 z | −0.030 (0.032), n = 3246 | | |
| scatter | | 0.21–0.23 | variability between epochs |
| 2MASS PSC Ks − AllWISE Kmag | 0.000 | | |

* The star offsets are the DECam/PS1 passband differences (a few hundredths
  of a mag).
* A wrong unit would show as offsets of magnitudes; for example, 2.7 mag for
  a missing WISE Vega → AB term.
* WISE W1/W2 (LS unWISE AB − AllWISE after Vega → AB), field 245/+43
  point sources (`v2_field_validation.yml`): W1 +0.026 (NMAD 0.147, n = 59),
  W2 +0.039 (NMAD 0.166, n = 57). Without the Vega → AB terms the offsets
  would be −2.7 and −3.3 mag, so the conversion is confirmed.
* Missing-value sentinels (PS1 −999, SDSS −9999, nulls) are removed: a
  magnitude counts only if 0 < m < 40 and an error only if 0 < σ < 10. The
  first version copied PS1 −999 into `std_mag__ps1_*` (seen as magnitude
  quartiles of −999 for PS1-only objects in the field diagnostics).

## Decisive Gaia motion (`05_likelihood_vectors.py`, `DECISIVE_MOTION_SIGMA`)
A Gaia DR3 parallax or proper motion measured at ≥ 10σ classifies the object
as STAR, even when photometric evidence conflicts. The criterion also needs
astrometry and association reliability ≥ 0.8 (RUWE ≲ 1.75).

* Physics: galaxies and quasars have no measurable parallax or proper motion
  at Gaia precision. Gaia DR3 quasars scatter around zero with normalised
  widths of ≈ 1.05–1.1 (Lindegren et al. 2021, A&A 649, A2; Klioner et al.
  2022, Gaia-CRF3).
* 10σ stays decisive even if faint-end errors are underestimated by about 1.5
  (El-Badry, Rix & Heintz 2021).
* Before the change, a 26σ proper motion entered the fusion only as STAR
  score 26/31 = 0.84. Any other strong claim then made the object CONFLICT,
  including one star at 1020σ.

Benchmark (spectroscopic truth):

| set | objects with motion ≥ 10σ | spectroscopic stars | changed | correct after change |
|---|---|---|---|---|
| SDSS (all) | 2989 | 99.6 % | 23 (19 UNKNOWN, 2 GALAXY → STAR; 2 non-stars UNKNOWN → STAR) | 21 |
| DESI faint | 518 | 99.0 % | 7 (6 UNKNOWN, 1 QSO → STAR) | 7 |

Coarse metrics before → after:

| set | abstention | accuracy (UNKNOWN = wrong) | accuracy when classified |
|---|---|---|---|
| SDSS test | 2.56 → 2.21 % | 0.9372 → 0.9402 | 0.9619 → 0.9615 |
| DESI faint | 7.92 → 7.80 % | 0.8488 → 0.8503 | 0.9219 → 0.9222 |

The non-stars with large motions in the truth sets were already predicted
STAR before the change. They are most likely mis-associations (a
foreground star at the spectroscopic position); the rule neither creates
nor fixes them.

Confidence for such objects = the measured precision (0.99), or the fused
STAR probability when that is higher.

## Magnitude-conditioned colour kNN (`color_knn.py`, 2.6.5)

The Legacy Surveys colour kNN (LS-CKNN-001) uses the dereddened r magnitude as
an extra coordinate (4 mag ≈ 1 mag of colour), so a faint object is compared
with reference objects of similar depth.

- Bovy et al. (2011, ApJ 729, 141), XDQSO: star and quasar densities in colour
  space are modelled in bins of apparent magnitude, since photometric errors,
  colour distributions and the relative number counts all change with depth.
- Measured (DESI DR1 held-out split): kNN accuracy 0.805 → 0.834; the fused
  coarse classifier abstains on 5.9 % instead of 7.7 % at the same or better
  accuracy when classified (CHANGELOG 2.6.5).
- The magnitude never counts toward the minimum number of colours, so a
  source with only a magnitude is not classified by colour.

## Legacy Surveys gradient boosting (`ls_gbm.py`, LS-GBM-001, 2.11.0)

A histogram gradient-boosting classifier (Friedman 2001, Ann. Stat. 29, 1189;
histogram binning as in LightGBM, Ke et al. 2017) gives STAR/GALAXY/QSO
probabilities from the Legacy Surveys Tractor measurements: dereddened r,
g−r, r−z, z−W1, W1−W2, r−W1, log r S/N and the morphological type.
Machine-learned classification on these features is how DESI selects its own
quasar targets (Chaussidon et al. 2023, random forest on LS colours).

- Training: 149,769 DESI DR1 spectra (ZWARN = 0, ΔCHI2 > 25, primary
  spectrum), 50,000 per class, LS DR9 photometry, every benchmark object
  removed (`benchmark/build_desi_gbm_truth.py`).  Held-out 10 %: 95.6 %
  (r < 21: 97.5 %, 21–22: 95.3 %, 22–23: 90.4 %, > 23: 90.5 %).
- Inference is numpy-only (trees exported to `ls_gbm_model.npz`), identical
  to scikit-learn (max |Δp| = 0).
- Half-light radius, Sersic index and W1 S/N were left out: the preserved
  benchmark features do not carry them, and they added only 0.2 points.

## Sign-constrained fusion fit (2.11.0)

The multinomial fusion fit could give a one-class claim the opposite sign
when it is collinear with other evidence (every benchmark object has Legacy
Surveys data).  Gaia DSC "STAR" and Gaia parallax/proper-motion "STAR" got
negative STAR weights, so a star with only Gaia evidence was fused to GALAXY
(p = 0.85).  `fit_fusion_weights.py` now removes any key whose fitted weight
does not raise its own class most and refits; removed keys keep their
literature prior weight in Stage 5 (one-sided support).  A Gaia-only copy of
the training rows (all LS, PS1 and WISE evidence dropped, weight 0.3) teaches
the remaining weights that case.
