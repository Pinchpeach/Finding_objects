# Decision-tree classification

Classification is now filled from the top of an interpretable physical tree.

1. **Observation validity** — official footprint, calibrated counterpart status, spectrum provenance/quality. Failed or unresolved association stays UNKNOWN.
2. **Physical branch: stellar vs extragalactic** — spectroscopic redshift, significant parallax/proper motion, morphology, stellar absorption pattern.
3. **Extragalactic branch: QSO/AGN vs galaxy** — broad permitted lines, high-ionization lines, narrow nebular lines, morphology, X-ray/radio excess and WISE AGN-like SED.
4. **Subtype** — only after the parent branch is secure. Galaxy subtype uses valid line ratios/BPT only when all required lines are covered and significant. Stellar subtype requires appropriate absorption/continuum features. QSO/AGN subtype uses broad-line and SED/radio/X-ray evidence.
5. **UNKNOWN/AMBIGUOUS rejection** — missing prerequisites never force a leaf label.

Each object stores its ordered decision path, evidence, counter-evidence, missing decisive observations, and calibrated confidence where calibration exists. Binary line detection is not sufficient: quantitative EW, flux, S/N, FWHM, line ratios and continuum/SED features are preferred.

Method 1 predictions are never promoted into the spectroscopy-confirmed Method 2 reference set.
