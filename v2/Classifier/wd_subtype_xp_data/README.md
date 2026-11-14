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

The tables reproduce the original runs (`WD_SUBTYPE_XP_VALIDATION.md`, `WD_SUBTYPE_XP_EXTERNAL_VALIDATION.md`):

| | original | 2026-11-14 |
|---|---|---|
| LAMOST truth → Gaia → XP | 300 → 291 → 228 (DA 118, DB 110) | 300 → 290 → 227 (DA 117, DB 110) |
| LAMOST held-out test, XP random forest | 48 / 50 | 49 / 50 (broadband: 37 / 50 both times) |
| SDSS external (compact, 100 per class) truth → Gaia → XP | 200 → … → 105 (DA 55, DB 50) | 200 → 198 → 105 (DA 55, DB 50) |
| compact external: accuracy ungated / p ≥ 0.90 / p ≥ 0.95 | 97.14 % / 65 rows 98.46 % / 40 rows 100 % | 97.14 % / 64 rows 98.44 % / 41 rows 100 % |
| SDSS external (primary, 200 per class) truth → Gaia → XP | 400 → … → 213 (DA 114, DB 99) | 400 → 391 → 213 (DA 114, DB 99) |
| primary external: balanced accuracy ungated | 95.28 % | 95.28 % |
| primary external: p ≥ 0.80 / 0.90 / 0.95 | 162 rows 99.38 % / 128 rows 100 % / 74 rows 100 % | 161 rows 99.38 % / 132 rows 100 % / 74 rows 100 % |

The first collection used the workflow's 100-per-class setting, the compact confirmation run; the deploy-model check
(`build-wd-subtype-xp-model.yml`: ≥ 80 rows at p ≥ 0.90) was set on the primary 200-per-class run (213 XP rows, 124 at
p ≥ 0.90) and fails on the compact set (63 rows).  The SDSS tables are therefore re-collected at 200 per class.
