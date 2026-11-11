# ab_2_51 (2026-11-11)

89 regions (set B + COSMOS deep), variants:
- base;
- `cgbm` (single coarse GBM);
- `fw-fusion_weights_nopresence` (adopted in 2.51.0 as `fusion_weights.json`);
- wavelength-band rule ablations (`off-...`).

**Data caveat:** NOIRLab (Legacy Surveys TAP) answered 502 / timed out all day.
- Only 2 of 89 regions have LS rows (`assoc_pairs.csv.gz`, `object_anchor_catalog`).
- AllWISE and 2MASS are present (VizieR 404 mirror fail-over, 2.51.0).
- The paired comparisons are valid but describe the sky **without Legacy Surveys**.
- Analysis: `v2/WORK_REPORT_2026-11-11.md` 3.4.
