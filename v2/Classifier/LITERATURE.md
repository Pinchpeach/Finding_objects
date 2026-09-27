# Classifier literature basis

## Coarse-to-detailed boundary

Gaia DR3 Apsis/DSC provides posterior probabilities for QSO, galaxy, star, white dwarf and physical binary star using multiple classifiers (Specmod, Allosmod and Combmod). In this project those five Gaia categories are deliberately collapsed to the coarse Preprocess routing classes; WD and binary information is retained for the STAR branch rather than used as a Preprocess final label.

Reference:
- Creevey et al. / Gaia DR3 Apsis methods overview, A&A 674, A26 (2023), doi:10.1051/0004-6361/202243688
- Gaia DR3 summary/content paper, A&A 674, A1 (2023), doi:10.1051/0004-6361/202243940

## STAR branch

White dwarf refinement should be a dedicated downstream task. Vincent et al. (2023) demonstrated a modular Gaia+SDSS pipeline for WD candidate selection, primary spectral-type classification, and main-sequence-companion detection; the spectral classifier achieved >90% precision for most WD classes on validated spectra.

Reference:
- Vincent et al., "Data-driven selection and spectral classification of white dwarf stars", MNRAS 521, 760 (2023), doi:10.1093/mnras/stad580
- Jiménez-Esteban et al., "Spectral classification of the 100 pc white dwarf population from Gaia-DR3 and the virtual observatory", MNRAS 518, 5106 (2023), doi:10.1093/mnras/stac3382

Implication:
- STAR branch should separate WD candidate selection from WD spectral subtype inference.
- Spectral subtype should not be produced when no validated spectrum/model is available.
- Binary/companion detection can be treated as an orthogonal flag.

## GALAXY branch

Galaxy morphology is naturally hierarchical/probabilistic. Galaxy Zoo work shows that image-based models can reproduce visual morphology and that detailed morphology benefits from probabilistic labels rather than one flat hard class.

References:
- Banerji et al., "Galaxy Zoo: reproducing galaxy morphologies via machine learning", MNRAS 406, 342 (2010), doi:10.1111/j.1365-2966.2010.16713.x
- Walmsley et al., "Galaxy Zoo: probabilistic morphology through Bayesian CNNs and active learning", MNRAS 491, 1554 (2020), doi:10.1093/mnras/stz2816
- Walmsley et al., "Galaxy Zoo DECaLS: Detailed visual morphology measurements...", MNRAS 509, 3966 (2022), doi:10.1093/mnras/stab2093

Implication:
- morphology branch should be hierarchical (disc/elliptical first, then bar/spiral/merger features)
- output probabilities and uncertainty should be retained
- image morphology and AGN/star-formation state should be separate axes

## QSO / AGN branch

Radio loudness is a downstream QSO/AGN property, not a replacement for the coarse QSO label. Recent SDSS DR16Q work combines FIRST matching with optical/IR/X-ray features and explicitly treats radio-loudness as an imbalanced classification problem.

Reference:
- Joshi & Shinde, "A statistical investigation of radio-loudness in SDSS DR16Q quasars using ML-based classification and physical feature analysis", Eur. Phys. J. C 86, 766 (2026), doi:10.1140/epjc/s10052-026-15968-7

Implication:
- radio-loud/quiet should be evaluated only for QSO/AGN-routed objects
- radio selection/missingness must not be confused with astrophysical class evidence
- class weighting/calibration is required for imbalanced radio-loud samples

## Project rule

No downstream branch may emit a detailed class solely because the object was routed to that branch. Unsupported detailed labels remain `UNRESOLVED`.
