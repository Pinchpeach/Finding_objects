# Stellar detailed-classification evidence configuration

## Decision

The classifier now keeps three Gaia observation products separate rather than
forcing a single stellar subtype from broad-band photometry:

| scientific question | evidence accepted in production | emitted result | abstention rule |
|---|---|---|---|
| White-dwarf atmospheric primary type | Gaia XP continuous coefficients through the existing externally validated DA/DB model | `spectral_type=DA` or `DB` only at calibrated confidence >= 0.90 | non-DA/DB, missing XP, low confidence, or no independent WD route stays `UNRESOLVED` |
| RR Lyrae pulsation subtype | Gaia DR3 SOS `vari_rrlyrae` published `best_classification` | `variability_class=RR_LYRAE`, `variability_subtype=RRAB`, `RRC`, or `RRD` | no period-only subtype inference |
| Cepheid type and mode | Gaia DR3 SOS `vari_cepheid` published type, subclass, and mode | `variability_class=CEPHEID`, `variability_subtype` such as `DCEP_F` | no subtype when the SOS label is unavailable or outside the documented vocabulary |
| Long-period-variable chemistry | Gaia DR3 SOS `vari_long_period_variable` published C-star-candidate flag | `variability_class=LPV`, `variability_subtype=C_STAR_CANDIDATE` | Mira is **not** inferred from period or amplitude |
| MK spectral type (O/B/A/F/G/K/M) or RGB/AGB leaf state | no new output | `UNRESOLVED` unless an already validated independent axis supports a class | GSP-Phot temperature, gravity, metallicity, and FLAME alone are not converted into hand-built subtype cuts |

This preserves the project rule that spectroscopy labels and coordinates are
truth/evaluation material, never runtime features.  The new runtime fields are
Gaia DR3 time-series products and Gaia XP-derived model inputs only.  Missing
SOS values remain missing; no imputation is applied.

## Why this configuration

Gaia DR3's broad variability classifier covers 24 groups, while its SOS
pipelines publish a more specific and separately validated result for RR Lyrae,
Cepheids, and LPVs.  The RR Lyrae catalogue contains 270,905 cleaned,
characterised sources, including fundamental-, first-overtone-, and
double-mode pulsators.  The LPV catalogue reports 1,720,558 candidates, a
published period for 392,240, and a C-star-candidate classification; it does
not publish a validated Mira leaf label.  The implementation therefore uses
the published SOS label when it exists and retains the family label otherwise.

For atmospheric white-dwarf type, XP has a demonstrated signal.  The existing
DA/DB route was externally tested on an untouched SDSS DR14 set: 213
XP-available pure DA/DB objects, 95.31% ungated accuracy, and 128 classified
objects with 100% observed accuracy at the fixed >=0.90 gate.  It remains a
two-class route, not a claim that all white dwarfs are DA or DB.

For ordinary-star MK types, published Gaia DR3 experiments show that a
supervised model is possible, but a model based only on GSP-Phot/FLAME values
would not satisfy this project's independent-validation standard.  Gaia XP is
the next appropriate input space for that work: build a spectroscopic truth
set, train on XP coefficients, evaluate against a disjoint survey, and enable
only labels that pass the gate.  This change does not substitute temperature
thresholds for that benchmark.

## Implementation

- Added `v2/Get_data/gaia_dr3_variability_sos_vizier.py`, which retrieves
  Gaia DR3 SOS fields from VizieR tables `I/358/vrrlyr`, `I/358/vcep`, and
  `I/358/vlpv`.
- Added it to the normal collection controller and to sampled independent
  variable-star validation.  ASAS-SN remains the truth source for that
  validation; it is not inserted as production evidence.
- Extended the variability axis with a separate `variability_subtype` output.
  The existing family labels and probability calibration remain unchanged.
- Extended route and collector-schema tests.  Full independent validation is
  triggered by the scientific cross-validation workflow after integration.

## Sources

- [Gaia DR3 all-sky variability classification](https://www.aanda.org/articles/aa/full_html/2023/06/aa45591-22/aa45591-22.html)
- [Gaia DR3 RR Lyrae SOS catalogue](https://www.aanda.org/articles/aa/full_html/2023/06/aa43964-22/aa43964-22.html)
- [Gaia DR3 long-period-variable catalogue](https://www.aanda.org/articles/aa/full_html/2023/06/aa44241-22/aa44241-22.html)
- [Gaia XP white-dwarf primary-type classification](https://www.aanda.org/articles/aa/full_html/2024/02/aa47694-23/aa47694-23.html)
- [Gaia DR3 Apsis II stellar-parameter processing](https://www.aanda.org/articles/aa/full_html/2023/06/aa43919-22/aa43919-22.html)
