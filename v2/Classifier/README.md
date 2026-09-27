# Classifier

`v2/Classifier`는 `v2/Preprocess`가 만든 coarse class를 입력으로 받아 더 세밀한 분류를 수행하는 계층입니다.

## Contract

Input:
- `primary_class ∈ {STAR, GALAXY, QSO, UNKNOWN}`
- coarse likelihood vector
- integrated multi-survey features/provenance

Routing:
- STAR → stellar branch
- GALAXY → galaxy branch
- QSO → QSO/AGN branch
- UNKNOWN → no forced detailed class

## Branch targets

### STAR
Initial targets:
- normal/main-sequence-like star
- white dwarf candidate → later DA/DB/non-DA spectral refinement when spectra are available
- physical binary candidate
- variable-star family
- optional spectral subtype when justified by spectroscopy/validated photometric model

### GALAXY
Initial targets:
- broad morphology: early-type / spiral-disc / irregular-merger
- bars/merger/tidal features when suitable images are available
- star-forming vs passive
- AGN-host flag as a separate property, not necessarily a mutually exclusive morphology class

### QSO / AGN
Initial targets:
- QSO/AGN confidence refinement
- radio-loud / radio-quiet when radio coverage and a documented radio-loudness definition are available
- X-ray detected / high-energy properties
- redshift/subtype modules only when validated inputs exist

## Current implementation

`control.py` validates the coarse input and routes each object to an explicit branch interface. Branches intentionally return `UNRESOLVED` rather than inventing a subtype when the required model/data are not yet installed.

The benchmark learned classifiers remain reproducible through wrappers in this folder:
- `train_primary_classifier.py`
- `train_rx_adaptive.py`

These wrappers keep the learned models out of `Preprocess` while reusing the validated benchmark implementations during the transition.

See `LITERATURE.md` for the scientific design basis.


## Validated STAR path

The current STAR branch has two validated layers:

1. **WHITE_DWARF candidate routing**
   - literature-backed Gaia HR locus as primary robust evidence
   - calibrated Gaia astrometry/photometry model as secondary/fallback evidence
   - conflict -> abstain / `UNRESOLVED`
   - independently checked on LAMOST spectroscopy

2. **DA / DB spectral subtype**
   - only for `WHITE_DWARF_CANDIDATE`
   - Gaia DR3 XP continuous coefficients (55 BP + 55 RP)
   - calibrated Random Forest
   - subtype is exposed only at probability >= **0.90**
   - independently checked across LAMOST-training -> SDSS-DR14-external domain
   - unsupported WD types remain `UNRESOLVED`

The model binary is produced as a GitHub Actions artifact rather than committed
to source control. See `WD_SUBTYPE_XP_EXTERNAL_VALIDATION.md`.

Typical subtype inference flow:

```text
STAR
  -> WHITE_DWARF_CANDIDATE
  -> Gaia XP available?
       no  -> spectral_type = UNRESOLVED
       yes -> DA/DB model
                p >= 0.90 -> DA or DB
                p < 0.90  -> UNRESOLVED
```

DA/DB support does not imply that DC/DQ/DZ/DO/magnetic/composite white dwarfs
are safely classifiable yet.
