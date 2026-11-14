# White-dwarf DA/DB Gaia XP data (2.53.0)

Inputs of the Gaia XP DA/DB sub-type model (`fit_wd_subtype_xp_model.py`,
`apply_wd_subtype_xp.py`; validation in `WD_SUBTYPE_XP_VALIDATION.md` and
`WD_SUBTYPE_XP_EXTERNAL_VALIDATION.md`).  They were artifacts of workflow runs
until 2.53.0; the artifacts expired after 30 days and every run of
`build-wd-subtype-xp-model.yml` failed at the download step, so the tables are
kept here.  All of them are reproducible: the truth is fixed, the Gaia DR3 XP
coefficients are a fixed data release, the SDSS sample is drawn at evenly
spaced ranks (no random draw) and the models use random_state = 42.

| file | content | written by |
|---|---|---|
| `wd_subtype_gaia.csv.gz` | Gaia DR3 crossmatch (2″) of the fixed LAMOST DR5 DA/DB truth (`../wd_subtype_truth.csv`) | `validate-wd-subtype-xp.yml` |
| `wd_subtype_xp.csv.gz` | the same rows with the 55 BP + 55 RP XP continuous coefficients (ESA Gaia DataLink): the training table | `validate-wd-subtype-xp.yml` |
| `sdss_wd_subtype_external_truth.csv.gz` | independent SDSS DR14 DA/DB truth (200 per class requested, S/N ≥ 10, LAMOST objects excluded: the primary external benchmark) | `validate-wd-subtype-xp-external.yml` |
| `sdss_wd_subtype_gaia.csv.gz`, `sdss_wd_subtype_xp.csv.gz` | its Gaia crossmatch and XP coefficients: the external test table | `validate-wd-subtype-xp-external.yml` |

The workflows collect a table only when it is absent here; both validation workflows
re-collect with `refresh=true`.  Order for a fresh start: `validate-wd-subtype-xp.yml`,
then `validate-wd-subtype-xp-external.yml`, then `build-wd-subtype-xp-model.yml`.

## Re-collected on 2026-11-14 (CDS XMatch down: VizieR batch fallback)

The fallback measures the 2″ cut on Gaia's epoch-2016.0 positions, as CDS
XMatch does (a first collection used the propagated J2000 positions and lost
one high-proper-motion LAMOST white dwarf: 290 / 227 instead of 291 / 228;
Codex review on PR #66).  With that fixed the tables reproduce the original
runs exactly (`WD_SUBTYPE_XP_VALIDATION.md`, `WD_SUBTYPE_XP_EXTERNAL_VALIDATION.md`):

| | original | 2026-11-14 |
|---|---|---|
| LAMOST truth → Gaia → XP | 300 → 291 → 228 (DA 118, DB 110) | same |
| LAMOST held-out test: XP random forest / broadband | 48 / 50 / 37 / 50 | same (confusion matrices identical) |
| SDSS external truth → Gaia → XP (200 per class requested) | 400 → … → 213 (DA 114, DB 99) | 400 → 391 → 213 (same) |
| external: accuracy / balanced accuracy | 95.31 % / 95.28 % | same |
| external p ≥ 0.80 / 0.90 / 0.95 | 162 rows 99.38 % / 128 rows 100 % / 74 rows 100 % | same |
| deploy model on the external set: ungated / p ≥ 0.90 | 95.77 % / 124 of 213, 100 % | same |

The workflow had the 100-per-class setting of the compact confirmation run (105 rows; the
deploy-model check, ≥ 80 rows at p ≥ 0.90, fails there with 63); it now collects the
primary 200-per-class benchmark the check was set on.
