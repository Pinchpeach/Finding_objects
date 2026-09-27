# White-dwarf subtype validation with Gaia XP

## Goal

Evaluate whether Gaia DR3 XP continuous spectral coefficients materially improve
the first detailed white-dwarf spectral subtype split beyond broadband Gaia
astrometry/photometry.

Current prototype task:

- DA
- DB

Truth comes from the LAMOST DR5 white-dwarf catalogue (Guo et al. 2022), using
only unambiguous pure DA and DB labels.

## Dataset

Initial balanced truth:
- DA: 150
- DB: 150

Gaia DR3 source matches:
- 291 / 300

Gaia XP continuous spectra retrieved:
- **228 / 291 = 78.4%**
- DA: 118
- DB: 110

Split on the XP-available sample:
- train: 128
- calibration: 50
- test: 50

XP inputs:
- 55 BP continuous coefficients
- 55 RP continuous coefficients
- total spectral coefficient features: **110**

No LAMOST spectral label or optical spectrum is used as a model feature.

## Broadband model on the same XP-available test subset

Using only Gaia broadband astrometry/photometry:

- accuracy: **74.00%**
- balanced accuracy: **75.81%**
- macro-F1: **73.91%**
- DB precision: **64.52%**
- DB recall: **90.91%**
- DB F1: **75.47%**
- log loss: **0.4881**

Confusion matrix:

| truth \ prediction | DA | DB |
|---|---:|---:|
| DA | 17 | 11 |
| DB | 2 | 20 |

This confirms the earlier conclusion that Gaia broadband information alone is
not sufficiently reliable for production WD spectral typing.

## Gaia XP Random Forest

Using the 110 BP/RP continuous coefficients:

- accuracy: **96.00%**
- balanced accuracy: **96.43%**
- macro-F1: **95.97%**
- DB precision: **91.67%**
- DB recall: **100.00%**
- DB F1: **95.65%**
- log loss: **0.1154**

Confusion matrix:

| truth \ prediction | DA | DB |
|---|---:|---:|
| DA | 26 | 2 |
| DB | 0 | 22 |

Relative to the broadband model on the identical test subset:

- accuracy: **74% → 96% (+22 pp)**
- DA false-to-DB errors: **11 → 2**
- DB false-to-DA errors: **2 → 0**
- log loss: **0.488 → 0.115**

## Important XP coefficients

The highest Random-Forest feature importances were concentrated primarily in
BP coefficients, including:

- xp_bp_15
- xp_bp_16
- xp_bp_28
- xp_bp_20
- xp_bp_17
- xp_bp_22
- xp_rp_11

Feature importance is not interpreted as a direct physical line measurement;
the Gaia XP coefficients are basis-function coefficients and correlated.

## Interpretation

The experiment strongly supports the architecture:

`WHITE_DWARF_CANDIDATE -> spectral-data availability -> XP/spectrum subtype model`

rather than attempting DA/DB classification from broadband photometry.

The gain is large enough that Gaia XP should become the preferred path for WD
spectral subtype inference when XP data are available.

However, this is still an experimental subtype classifier because:

1. XP coverage in this truth sample is only 78.4%.
2. The held-out test contains only 50 objects.
3. Train/calibration/test are all drawn from the same LAMOST catalogue domain.
4. Only DA and DB are represented.
5. DC/DQ/DZ/DO/magnetic/hybrid/WD+MS classes are not yet validated.

Therefore the production STAR branch should still output
`spectral_type=UNRESOLVED` unless a separately validated subtype model is
explicitly enabled.

## Decision

- Keep Gaia broadband WD subtype classification disabled.
- Promote Gaia XP coefficients to the primary experimental feature source for
  WD spectral typing.
- Next validation should add independent DA/DB spectroscopy and then expand to
  DC/DQ/DZ/DO and composite classes.
- Maintain an abstention/UNKNOWN path for low-confidence or unsupported subtype
  cases.

## Reproducibility

Successful GitHub Actions run: **36299457097**

Artifact:
- `wd-subtype-gaia-xp-eval`

Key code:
- `build_wd_subtype_truth.py`
- `collect_gaia_xp_coefficients.py`
- `train_validate_wd_subtype_xp.py`
- `.github/workflows/validate-wd-subtype-xp.yml`
