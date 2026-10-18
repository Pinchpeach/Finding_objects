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
  Since 2.16.0 the rule is applied only in the regime Assef et al. (§3) built
  the catalogue in: W2 S/N > 5, W1 > 8 and W2 > 7 mag (saturation), cc_flags =
  0 (via `catalog_confidence_allwise`), |b| > 10° and > 30° from the Galactic
  Centre (YSOs, AGB stars and PNe have AGN-like W1−W2 there).  The earlier
  gate was S/N ≥ 3 in both bands only.

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
**Superseded (2.4.x onward):** the final coarse class now comes from the
fitted multinomial logistic fusion of the evidence keys with a calibrated
abstention threshold (Stage 5, `fusion_weights.json`; sign-constrained since
2.11.0, see below), plus the decisive-Gaia-motion rule. The hierarchy below
is kept as the record of the earlier design.

The pipeline used an interpretable hierarchical decision tree for final
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

## Gaia DSC class prior removed (2.16.0)

Gaia DR3 DSC-Combmod probabilities are posteriors under a global class prior
(Delchambre et al. 2023, A&A 674, A31, Table 2: star 0.988728, binary 0.009887,
WD 0.000198, QSO 0.000989, galaxy 0.000198).  The fusion is trained on
class-balanced data, so feeding these posteriors in counted a ~1000:1 star
prior on top of the fitted weights.  Following Delchambre et al. App. C, each
probability is divided by its prior and renormalised (STAR = star + binary +
WD), with a 1e-6 floor.  The DSC-001 and VAR-001 rows of
`classification_rules.csv` were also missing one field, which made their
`likelihood_method` empty and the Stage-5 weight fall to the 0.25 default.
Measured with the refitted fusion (test splits): DESI 88.46 → 90.96 %
(abstention 5.3 → 2.6 %), SDSS 97.64 → 97.69 %.

## Gaia parallax consistent with zero (AST-EXT-001, 2.16.0)

|(ϖ + 0.017)/σϖ| < 5 is the Gaia-CRF3 consistency cut (Klioner et al. 2022,
A&A 667, A148, Eq. 2; the −0.017 mas QSO median parallax, Lindegren et al.
2021, A&A 649, A4).  Klioner et al. use it only to clean catalogued QSO
candidates.  As positive EXTRAGALACTIC evidence it is informative only when
σϖ is small (σϖ = 1 mas lets every star beyond ~0.2 kpc pass), so it is now
emitted for σϖ ≤ 0.3 mas only (G ≲ 19.5 in DR3).  DESI 89.29 → 89.50 % before
the refit; after the refit the key is no longer sign-dropped.

## Survey positional profiles (`association_model.py`, 2.16.0)

| Survey | Change | Source |
|---|---|---|
| Pan-STARRS1 | PSF 0.83″ → 1.2″ (delivered i-band median; 0.83″ was the site DIMM seeing); `epochMean` read as the epoch of the mean position | Chambers et al. 2016, Table 11 |
| FIRST | beam 5.0″ → 5.4″ | Becker, White & Helfand 1995 |
| eRASS1 | fallback error 4.0″ → 4.5″ (POS_ERR peak), resolution 26″ → 30″ (survey-averaged HEW), epoch 2020.5 → 2020.2; per-source POS_ERR read | Merloni et al. 2024 |
| Chandra CSC 2.0 | per-source r0 is a 95 % radius: σ = r0/2.448 ⊕ 0.16″ systematic | Evans et al. 2010; CSC column docs |
| 4XMM | per-source POSERR (1σ incl. systematic) read | Webb et al. 2020 |
| Legacy Surveys DR10 | new profile (was the 0.6″ default): seeing 1.2″, per-source σ from `ra_ivar`/`dec_ivar`, `ref_epoch` for Gaia-matched stars | Dey et al. 2019 |

The benchmark features are already matched, so these do not change the
benchmark numbers; they change real-field association (larger PSF/6 floor
for PS1, correct X-ray error circles, proper-motion propagation to PS1/LS
epochs).

## Rejected after measurement (2.24.0)

| Idea | Source | Why not adopted |
|---|---|---|
| Resolved-host AGN: "resolved × max(0, W1−W2 − R75)" feature | Assef et al. 2018 (ApJS 234, 23), R75: W1−W2 > 0.486 Vega (= −0.154 AB with the Jarrett et al. 2011 offsets) at W2 ≤ 13.07 | The QSOs still called GALAXY have a median excess of 0 (below R75), so mid-IR colour does not separate them from their hosts. Correctly classified resolved QSOs already carry the excess. In the fit the feature made the sign constraint drop DSC-001:QSO and LS-CKNN-001:QSO, and DESI STAR recall fell 0.899 → 0.855. A presence indicator ("resolved") was worse: it duplicated LS-MORPH-002 and dropped it. |
| CatWISE2020 proper motions for faint STAR vs QSO | Marocco et al. 2021 (ApJS 253, 8): motions good to ~20 mas/yr at W1 ≈ 15 and ~100 mas/yr at W1 ≈ 17; formal errors ~2× too small near W1 ≈ 17.2 | The DESI stars misread as QSO have median W1 = 17.5 (Vega); halo-star motions of 5–20 mas/yr are far below that error. |
| GALEX UV excess (FUV−NUV, NUV−r) | Bianchi et al. 2011; Trammell et al. 2007 (AJ 133, 1780) | 0 % of those stars, and 11 % of the QSOs misread as STAR, have a GALEX AIS detection. |

## Hybrid Stage-5 fusion (2.25.0)

| Element | Source | Use |
|---|---|---|
| Gradient-boosted trees over the evidence keys | Friedman 2001 (Ann. Stat. 29, 1189); Ke et al. 2017 (LightGBM, NeurIPS) | Lets evidence interact (e.g. a colour meaning something different for resolved and unresolved sources), which the linear log-odds sum cannot express. Absent evidence is a missing value, not logit 0. |
| Temperature scaling | Guo et al. 2017 (ICML, "On Calibration of Modern Neural Networks") | One scalar (T = 1.3) fitted on the calibration split, so the abstention threshold works on calibrated probabilities. |
| Geometric mean with the linear model (product of experts) | Hinton 2002 (Neural Computation 14, 1771) | The trees alone lowered Gaia-only faint-star recall (0.886 → 0.834, DESI test) for evidence combinations rare in training. The sign-constrained linear model keeps a predictable direction there, and the 0.5 blend was not below the linear model in any missing-evidence case on the calibration split. |

## X-ray, radio and high-redshift quasar evidence (2.26.0)

| Element | Source | Use |
|---|---|---|
| X-ray-to-optical flux ratio, log(fX/fopt) = log fX + m/2.5 + 5.37 (XRAY-001) | Maccacaro et al. 1988 (ApJ 326, 680), Eq. 1; Stocke et al. 1991 (ApJS 76, 813) | AGN and quasars lie at −1 to +1.2, coronal stars below −1, normal galaxies below ~ −2. Survey bands (CSC 0.5–7, 4XMM 0.2–12, eRASS1 0.2–2.3 keV) are converted to 0.3–3.5 keV with a photon index Γ = 1.8 (mean AGN slope); r is used for V. |
| Radio loudness R = 0.4 (r − t), t = −2.5 log10(S1.4 / 3631 Jy) (RADIO-001) | Ivezić et al. 2002 (AJ 124, 2364), Section 4 | Radio-loud quasars and AGN are detected at the survey limits while stars almost never are; LoTSS and VLASS are scaled to 1.4 GHz with S ∝ ν^−0.7. |
| High-z quasar gri branch (PS1-QSO-HIZ-001) | Richards et al. 2002 (AJ 123, 2945), Section 3.4 | z ≈ 3.5–4.5 quasars are red in g−r from the Lyα forest and move off the stellar locus; benchmark purity 7/8, completeness ~11 % at z > 3. |
| X-ray and radio keys kept out of the trees (linear only) | eRASS1 footprint: Merloni et al. 2024 (A&A 682, A34), Galactic l > 180°; LoTSS DR2: Shimwell et al. 2022 (A&A 659, A1), northern sky | A missing counterpart reflects the survey footprint, not the class: 33 % of SDSS-truth QSOs but 4 % of DESI-truth QSOs have an X-ray match. Tree missing-value branches learned that difference (DESI STAR recall 0.893 → 0.852); the linear model treats absence as logit 0. |
| Gaia match at the truth epoch | Gaia DR3 epoch J2016.0 (Gaia Collaboration, Vallenari et al. 2023, A&A 674, A1) | Benchmark Gaia counterparts are searched within 15″ and moved by their proper motion to the spectroscopic epoch (SDSS MJD); 46 high-proper-motion SDSS stars gained their Gaia match. |

## ZTF variability (2.27.0, measured, not adopted)

| Element | Source | Outcome |
|---|---|---|
| Structure function SF(dt) = A (dt / 1 yr)^γ, χ²_red, from ZTF r/g light curves (ZTF-VAR-001, off unless its rule row is present) | Schmidt et al. 2010 (ApJ 714, 1194); Palanque-Delabrouille et al. 2011 (A&A 530, A122); Masci et al. 2019 (PASP 131, 018003) | Point sources only, since PSF photometry of resolved galaxies varies with seeing (benchmark galaxies: median χ²_red 10.6). The fitted weights point the right way (γ → QSO +1.28), but test accuracy changed by one object per set (SDSS +0.05 pp, DESI −0.11 pp) and the calibration log-loss rose (0.1433 → 0.1473). IRSA light-curve cones also take minutes per field. Not adopted. |
| Gaia DSC all-zero stellar posterior | Delchambre et al. 2023 (A&A 674, A31) | A zero stellar probability is a confident extragalactic posterior; DSC-001 now emits it (2.27.0) instead of dropping the rule for 41 % of DSC rows. |

## DESI spectra in association (2.28.0)

| Element | Source | Use |
|---|---|---|
| A DESI spectrum is a measurement at its Legacy Surveys target position (TARGET_RA/DEC), position error 0.1″ instead of the 0.6″ default | Myers et al. 2023 (AJ 165, 50), DESI target selection pipeline; Dey et al. 2019 (AJ 157, 168) LS astrometry | With 0.6″ a spectrum on a star 0.85″ from a galaxy scored 0.85 vs 1 and was left ambiguous (field RA 250). |
| Spectra associate after the imaging, and a spectrum within 0.3″ of a group's LS member joins that group (decisive) | same (spectra have no independent position) | LS DR10 south release 10000 differs from the DR9 TARGETID, so the catalogue alias can fail; a shredded galaxy's PS1/SDSS fragments otherwise made its LS source ambiguous (RA 250), and a group anchored by a PS1 detection 0.71″ off sent the spectrum to a lone GALEX detection (RA 20). Distance is measured to the group's LS members, not its anchor. |
| Duplicate spectra of one target: kept once (best ΔΧ², greedy 0.5″), a second spectrum never joins a neighbour | DESI DR1 has several spectra per target (zcat_primary) | A rounded 0.5″ grid key kept both copies when they straddled a cell edge. |

## Two-colour-diagram galaxy evidence (2.29.0 candidate, measured, not adopted)

| Element | Source | Outcome |
|---|---|---|
| Offset from z − W1 = 0.8 (r − z) − 0.6 (star rejection by the galaxies' 1.6 µm bump) | Zhou et al. 2023 (AJ 165, 58), Eq. 1b; AB, dereddened LS + W1 | SDSS benchmark: 1 % of stars above the line, 99 % of QSOs, 91 % of point-like galaxies. DESI (faint): 53 % of stars above it — faint blue stars (median r 21.2) whose unWISE W1 is blended; Zhou et al. note leakage by M dwarfs and bad W1 |
| Offset from z − W1 = 0.66 (g − z) + 2.01 (W1 Vega; −0.69 in AB) | Wu et al. 2012 (AJ 144, 49), Sect. 4: 98.3 % of QSOs kept, 95.2 % of stars rejected | on the QSO side: SDSS stars 0.7 %, DESI stars 45 % |
| Distance from the stellar locus \|(g − r) − 1.53 (r − z) − 0.2\| | DESI desitarget isQSO_colors veto (Myers et al. 2023, AJ 165, 50) | within 0.1 (g − r > 0.2): stars 57 % / 49 %, galaxies 7 % / 12 % (SDSS / DESI) |
| All three as Stage-5 features (rule LS-2COL-001), refit on the train split | — | test accuracy SDSS 98.54 → 98.24 %, DESI 92.41 → 92.41 % (fit report; locus only 98.29 / 92.10 %, offsets only 98.49 / 92.31 %); tree calibration log-loss 0.1182 → 0.1163. A straight line is a linear combination of the LS-COLOR-001 colours already in the model, and the colour kNN (LS-CKNN-001) and LS-GBM-001 already use the full g−r, r−z, z−W1, W1−W2 space, so the published lines add no test accuracy. Not adopted. |
