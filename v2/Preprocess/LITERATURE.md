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

## Pan-STARRS1 duplicates and fragments of small galaxies (2.34.0)
- **Problem.** PS1 sometimes makes two or three MeanObjects from one resolved galaxy, and the pipeline then counted that galaxy two or three times.
- **Literature.**
  - PS1 MeanObjects link single-epoch detections that lie within 1″ of each other, and one-time false detections also become objects (Chambers et al. 2016, arXiv:1612.05560, §4.2).
  - Generic object finders in PS1 DR2 break flat galaxies into pieces (Makarov et al. 2022, MNRAS 511, 3063).
  - Bright galaxies are also shredded in SDSS (Blanton et al. 2005, AJ 129, 2562) and in the Legacy Surveys (Dey et al. 2019 §8; Moustakas et al. 2023).
  - Gaia's external cross-match keeps the extra catalogue entries of one source as "mates" instead of dropping them (Marrese et al. 2019, A&A 621, A144).
  - Host galaxies are assigned with a light-radius-normalised separation, d_DLR < 4 (Sullivan et al. 2006, ApJ 648, 868; Gupta et al. 2016, AJ 152, 154).
- **Review of 2026-10-20** (`WORK_REPORT_2026-10-20.md`), PS1-only rows lying inside an extended LS galaxy:
  - The Legacy Surveys image shows a single galaxy every time.
  - No Gaia source lies within 0.5″.
  - Where both rows have a Kron magnitude, each holds the whole galaxy's flux, so they are repeated measurements of the galaxy.
- **Rule** (`host_groups.attach_ps1_fragments`, applied after classification):
  - A PS1 (or PS1+SDSS) object becomes a component of the galaxy when it lies within 2 r_e of the galaxy centre (minimum 1″).
  - It is kept independent if another LS source lies within 1″, or a Gaia or SDSS source of another object lies within 0.7″. The exception is an SDSS source that is the only SDSS source on the galaxy: that is SDSS's own measurement of the galaxy.
  - It is also kept independent if it is more than 0.75 mag brighter than the galaxy.
- **Not used.**
  - LS `shape_e1/e2`: we could not confirm their position-angle convention, so the circular major-axis r_e is used instead. That is generous along the minor axis.
  - Galaxy sizes beyond r_e (the halo of bright galaxies) are left for later.

## Faint stars vs quasars: methods measured 2026-10-20 (2.34.1, none adopted)
Failure analysed: on the DESI test split, faint stars go to QSO (19), to GALAXY (10) or to UNKNOWN (7). The STAR->QSO cases are blue point sources (g-r ~ 0.3), the colour region where stars and low-z quasars overlap without a u band (Richards et al. 2002; Yèche et al. 2020).

| Method (literature) | How it was tested | DESI test (962) | SDSS test (1991) | Verdict |
|---|---|---|---|---|
| Class-balanced LS-GBM per 0.5-mag r bin (Chaussidon et al. 2023 reweight stars to the QSO magnitude distribution; Bovy et al. 2011 keep the prior out of the likelihood) | `train_ls_gbm.py --balance` + fusion refit | 92.41 -> 92.31 %; faint (r>21) stars 127 -> 132 of 149, QSO recall 93.6 -> 89.8 %; McNemar p = 1.0 | 98.69 -> 98.74 % | not adopted: stars gained = quasars lost |
| + per-band S/N features (photometric errors as inputs; Bovy et al. 2011) | `--balance --snr` | 91.79 %; faint stars 134/149, QSO 88.5 %; p = 0.39 | 98.54 % | not adopted |
| IR-excess feature grz-W vs g-z (Yèche et al. 2020) | GBM holdout | no change in macro recall (0.888 vs 0.885 at r 21-22) | – | not adopted |
| Galactic latitude as a feature (number-count prior; Bovy et al. 2011) | GBM holdout | no gain (DESI targets are selected, so the latitude dependence of the sky mix is not in the training set) | – | not adopted; a real-sky prior cannot be validated on the class-balanced benchmarks |
| r magnitude as a fusion feature (magnitude-dependent classification; Nakoneczny et al. 2021) | LS-COLOR-001 `r_mag` + fusion refit | 92.31 %, p = 1.0 | 98.54 % | not adopted |
| Balanced GBM + r-magnitude fusion feature | both | 92.10 %, faint stars 133/149, p = 0.71 | 98.69 % | not adopted |
| Gaia proper-motion significance | error analysis | only 4 of 140 misclassified DESI stars (all splits) have mu/sigma > 3, and the motion rules (AST-GAL-001/002) already use it | – | no headroom |

The holdout of the LS-GBM training set alone showed a large faint-star gain from class balancing (r 21-22 recall 0.44 -> 0.86). In the full pipeline the fusion already corrects most of the GBM's DESI-target prior, so what remains is the genuine star/QSO colour overlap. Separating those needs a u band or variability, which are not available at r > 21 in our sources.

## Independent-truth validation fixes (2.35.0, 2026-10-21)
Found by validating on 18 sky regions against spectroscopic surveys never used for training (`WORK_REPORT_2026-10-21.md`).

| Problem | Literature | Rule |
|---|---|---|
| LAMOST re-observes 40-50 % of the stars in crowded plates; every repeat spectrum (a new ObsID, input-catalogue position up to ~1″ off) became its own evidence-less "only in LAMOST" object (368-606 per field) | LAMOST fibres are 3.3″ wide and cannot be placed closer than ~3.5″ (Cui et al. 2012, RAA 12, 1197); repeat observations are listed as separate spectra (Luo et al. 2015, RAA 15, 1095) | `lamost_spectroscopy.fetch`: one row per target within 1″, the best-band S/N spectrum; the same for SDSS spectra (zwarning = 0, smallest zerr; 2-3″ fibres) |
| LS-GBM scored extended Sérsic galaxies STAR 1.00 where DR10 has no r-band imaging (field 340/-30) | the model is trained on DESI targets, which all have g, r and z imaging (NOBS >= 1; Myers et al. 2023, AJ 165, 50) | `ls_gbm.predict_proba`: no evidence without flux_ivar > 0 in each of g, r, z |
| Saturated stars leave single-survey rows in their halo: single-catalogue PS1 rows were 40-100x the background within 2″ of G < 13 stars, 5-10x within 1-5″ of G = 13-15 stars, 4x at 20-30″ of G < 11 stars; 51 of 214 such objects (12 fields, < 3″) were classified, mostly GALAXY | PSPHOT splits bright stars and diffraction spikes into several detections, so PS1 analyses mask bright stars (Chambers et al. 2016, arXiv:1612.05560; Metcalfe et al. 2013, arXiv:1310.6368); Legacy Surveys bright-star masks with radius R(G) = 1630″ x 1.396^-G (legacypipe `mask_radius_for_mag`; LS DR9/DR10 bitmask documentation: MEDIUM = R, BRIGHT = R/2) | `host_groups.attach_bright_star_artifacts`: a top-level object measured by one survey (PS1, AllWISE, GALEX, SDSS imaging or 2MASS) within R/2 (min 2″) of a G < 16 star is grouped under the star; R/4 where the star has no LS source within 60″ (there a PS1-only object is often a real faint star) |
| The fusion was trained only at high latitude (no benchmark object at \|b\| < 10°, 21 of 23,000 at \|b\| < 20°); in a field at l = 182°, b = +2° it labelled 616 G ~ 20 disc stars QSO (zero proper motion toward the anticentre) | star counts rise roughly as csc\|b\| (Bahcall & Soneira 1980, ApJS 44, 73); Gaia DR3 classification uses a class prior that varies with latitude and magnitude (Hughes, Bailer-Jones & Jamal 2022, A&A 668, A99; Bailer-Jones et al. 2024, arXiv:2405.01340); quasar catalogues cut \|sin b\| <= 0.1 (e.g. arXiv:2111.02131) | `05_likelihood_vectors.latitude_factor`: GALAXY and QSO odds x sin\|b\| / sin 20° below \|b\| = 20° (extinction ignored, so conservative); benchmarks unchanged |
| Gaia DSC and astrophysical parameters missing in a crowded field (6,966 sources): 14 optional-table queries of 500 ids, each paced 3-5 s, ran past the shared 80 s deadline | – (engineering) | 2000 ids per query |

Measured and not adopted: dropping the LS colour kNN (LS-CKNN-001) where LS-GBM is present, replayed on the saved evidence of 1,232 truth objects without refitting: accuracy 95.70 -> 95.78 %, galaxy recall +0.6 points, QSO recall -3.3 points (not significant).

## Spectral classes, missing archives, real-sky purity and the high-confidence flag (2.36.0, 2026-10-22)

| Item | Literature / measurement | Rule |
|---|---|---|
| DESI DR1 Redrock class as evidence (`SPC-DESI-001..003`) | Redrock SPECTYPE; ZWARN = 0 and DELTACHI2 >= 25 (best template ~5 sigma better than the next) is the DR1 reliable-redshift cut (DESI Collaboration 2025, arXiv:2503.14745; galaxy VI purity > 99 %, arXiv:2208.08516; quasar VI, arXiv:2208.08517). Backup-programme GALAXY fits are mostly misfit faint stars (~65 %; arXiv:2505.17230) | catalogue label (prior weight 1.5, like SDSS); reliability 1.0 for good spectra, 0.5 otherwise and for backup GALAXY |
| LAMOST DR5 class as evidence (`SPC-LAMOST-001..003`) | 1D pipeline STAR/GALAXY/QSO/Unknown; S/N > 10 in g or i is good quality (Luo et al. 2015, RAA 15, 1095). Cross-check against the other surveys of the 18 independent fields: 44/45 agree at S/N >= 10, 16/18 below (Unknown excluded) | reliability 1.0 at S/N >= 10, else 0.5; Unknown gives nothing |
| Benchmarks unchanged | neither benchmark carries spectroscopy features (their truth *is* SDSS/DESI spectra) | SDSS 98.69 %, DESI 92.41 %, 0 predictions changed |
| Real-sky purity (`benchmark/natural_purity.py`) | the truth samples are not the sky (class-balanced DESI test; star/ELG/UVX-quasar surveys). Recall matrices are mix-independent; purity under the field mix by Bayes (cf. Bovy et al. 2011, ApJ 729, 141). Quasar counts fixed from the literature: 147 deg^-2 to g < 22.5 (Palanque-Delabrouille et al. 2016, A&A 587, A41), ~230 deg^-2 to r < 23 (DESI Collaboration 2016, arXiv:1611.00036), ~10 deg^-2 to i < 19.1 (Schneider et al. 2010); stars/galaxies by NNLS from the 18 fields' predictions. Rates are Jeffreys estimates (k + 1/2)/(n + 1); 200 bootstrap resamples | table in `benchmark/natural_purity/` |
| High-confidence flag (`high_confidence.py`) | purity >= 98 % at the 16th bootstrap percentile per class and magnitude bin (`Classifier/high_confidence.json`), or a good spectrum of the same class with association >= 0.8. The blind fields predict ~1,750 QSO deg^-2 against <= 230 real, so no photometric QSO qualifies | gold ring in the app; photometric route withheld when a key archive failed |
| Missing-archive warning (`catalog_coverage.py`) | 2.35.0: unreachable archives were the main cause of worse fields (UNKNOWN 39-68 % without Legacy Surveys) | `catalog_coverage.json` + app banner; key = Gaia, PS1, LS, AllWISE |

## Nebular stars and the Magellanic Clouds (2.37.0, 2026-10-25)

| Item | Literature / measurement | Rule |
|---|---|---|
| Decisive parallax without the C* gate | The C* gate (Riello et al. 2021, A&A 649, A3) was added for a spurious 14-sigma *proper motion* of a galaxy nucleus (2.22.0). Nebular background raises the BP/RP excess of genuine young stars (ONC, M8). Gaia quasar parallaxes scatter with width ~1.05-1.1 (Lindegren et al. 2021, A&A 649, A2); blended faint sources can have errors underestimated by ~1.5 (El-Badry, Rix & Heintz 2021; Fabricius et al. 2021, A&A 649, A5). 200-region truth: 151 of 152 C*-failing objects with parallax >= 15 sigma (reliability, association >= 0.8) are spectroscopic stars | AST-GAL-001 >= 15 sigma decisive whatever C*; proper motion keeps the gate |
| Magellanic star-count prior | Gaia DR3 meets the same stellar contamination: 38 % of the DSC quasar labels lie in the LMC and 6.4 % in the SMC (Delchambre et al. 2023, A&A 674, A31), and excluding generous regions around the Clouds removes 41 % of the 6.6 M qso_candidates (Gaia Collaboration, Bailer-Jones et al. 2023, A&A 674, A41); Quaia adds a G−W1 / W1−W2 cut against Cloud stars (Storey-Fisher et al. 2024). ~25 quasars deg^-2 at I < 20 behind the Clouds vs > 10^6 stars deg^-2 (Kozłowski et al. 2013). (2.37.1 correction: 2.37.0 wrongly said the Gaia DR3 purer sample excludes the Clouds; it does not, and it shows Cloud overdensities.) Exponential profile fitted to the Gaia counts of the 11 Cloud fields of the 200-region validation (LMC rho0 = 1.2e6 deg^-2, h = 1.97 deg; SMC 1.09e6, 0.66 deg; 0.2 dex scatter); reference density = median of the fields at the same latitude away from the Clouds (1.2e4, 6.6e3) | GALAXY and QSO odds x rho_ref / rho(R), <= 1 (1 beyond 9.1 deg LMC, 3.4 deg SMC) |
| Magellanic proper-motion likelihood ratio | Systemic motions: LMC (mu_a*, mu_d) 1.85-1.91, 0.23-0.39 mas/yr over HST and Gaia DR1-EDR3 (Kallivayalil et al. 2013, ApJ 764, 161; van der Marel & Sahlmann 2016, ApJ 832, L23; Gaia Collaboration, Helmi et al. 2018, A&A 616, A12; Luri et al. 2021, A&A 649, A7), disc rotation ~0.3 mas/yr at 50 kpc; SMC 0.69-0.87, -1.21..-1.24 (Zivick et al. 2018, ApJ 864, 55; Helmi et al. 2018). Adopted LMC (1.88, 0.31) +- 0.4, SMC (0.82, -1.21) +- 0.3; Gaia errors x 1.1 | odds x min(1, prior / LR(member : zero motion)); a motion that fits zero but not the Cloud restores the fusion's odds |

## QSO-separation candidates compared (2.38.0, 2026-10-25)

Candidates of `v2/LITERATURE_QSO.md` replayed on the same Stage-4 evidence (`benchmark/compare_qso_options.py`, table in `benchmark/qso_options/`).

| Item | Literature | Rule | Measurement |
|---|---|---|---|
| Proper-motion significance with full covariance (adopted in 2.38.0, reverted in 2.39.0: 200-field Stage-5 accuracy 96.12 -> 96.01 %; option c2) | Li & Fynbo 2026 (arXiv:2610.13742): Mahalanobis distance from zero motion, scaled chi^2 (k = 2) with s = 1.1485 fitted to Gaia-CRF3; ignoring the pmra-pmdec correlation biases the test | AST-EXT-002 / AST-GAL-002 value sqrt(D^2/1.1485); `pmra_pmdec_corr` collected; fusion refitted | SDSS 98.69 -> 98.69 %, DESI 92.41 -> 92.62 % |
| X-ray star line (adopted) | Salvato et al. 2018 (MNRAS 473, 4937) Eq. 2: [W1] = -1.625 log F(0.5-2 keV) - 8.8 separates stars (brighter W1) from AGN | X-ray counterpart on the stellar side: QSO odds x 0.1 | with the above: SDSS 98.74 %, DESI 92.62 %; real-sky QSO purity r 20-21 8.4 -> 10.6 % |
| Magellanic systemic motions (adopted) | Gaia Collaboration, Luri et al. 2021 Table 4: LMC (1.871, 0.391), SMC (0.686, -1.237) mas/yr | MAGELLANIC in Stage 5 | no benchmark object; field check pending |
| Magnitude prior, DESI tanh threshold (kept as options c1a, c3b) | Bovy et al. 2011; Jamal & Bailer-Jones 2024; Chaussidon et al. 2023 | V2_QSO_OPTIONS | real-sky QSO purity x2-3, QSO recall -16 to -49 %p |
| Quaia colours, faint abstention (not adopted) | Storey-Fisher et al. 2024; Nakoneczny et al. 2019 | - | SDSS -0.6 %p; DESI -5.7 %p |

### 200 independent fields (2.39.0)

Stage-5 replay of every option on the blind evidence of the 200 fields (14,498 truth objects; `benchmark/qso_options/qso_options_fields.csv`).

| Item | Literature | Rule | Measurement |
|---|---|---|---|
| Local stellar-density prior (adopted) | continuous position prior: Jamal & Bailer-Jones 2024 (A&A 687, A258); Hughes et al. 2022 (A&A 668, A99) | GALAXY/QSO odds x min(1, 5000 deg^-2 / Gaia density from the 10th neighbour); latitude + Magellanic priors where < 11 Gaia sources | 96.12 -> 96.16 %, QSO predictions -16 % (Clouds -59 %) |
| DESI WISE cut (adopted) | Chaussidon et al. 2023 (ApJ 944, 107) Sect. 3: W1 < 22.3 and W2 < 22.3 | QSO odds x 0.1 otherwise | 96.21 %, QSO precision 77.1 -> 79.2 % |
| Gaia DSC ignored in the Clouds (adopted) | Delchambre et al. 2023: 38 % of DSC quasars lie in the LMC, 6.4 % in the SMC | DSC-001 dropped where the Magellanic prior < 1 | Magellanic QSO 5,657 -> 3,162 |
| Magnitude prior, half strength (option c1a_half) | Bovy et al. 2011; Jamal & Bailer-Jones 2024 | QSO odds x sqrt(real-sky / training odds) per r bin | 96.30 %, QSO precision 87 %, recall 96 -> 91 %; benchmarks SDSS -0.75, DESI -3.4 %p |
