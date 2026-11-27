# Bare columns that two or more catalogues share (2.61.4)

Stage 2 (`Preprocess/02_integrate_objects.py`) keeps every raw field under `<catalog>__<field>`.  Until 2.61.3 it also wrote the bare
name, as the first valid value of any catalogue of the object: for a name that two catalogues publish (`type` of Legacy Surveys and
SDSS, `pmra` of Gaia and SIMBAD, `RAJ2000` of seven catalogues) the value depended on which row came first and nothing said where it
came from.  From 2.61.4 such names have **no bare column**; names that only one catalogue has (`W1mag`, `iMeanPSFMag`) keep it.
`V2_KEEP_SHARED_BARE=1` writes the old columns again (A/B, external scripts).

| file | content |
|---|---|
| `shared_columns.csv` | one row per name (80): the catalogues that publish it, where the bare name is read in the code, what was changed, app / summary / tests, the status in Stage 2 now (`build_table.py` writes it; `Preprocess/tests/test_shared_columns.py` keeps it equal to `SHARED_FIELDS`) |
| `shared_candidates.json` | the starting list: names found in the raw headers of 30 collectors (26 deep COSMOS fields, 309 low-latitude regions, three real-use fields, the committed NGC 4522 files) |
| `equivalence.py` | the same raw folders classified with two checkouts (before / after); labels, probabilities, columns removed, other columns that differ |
| `results_2026-11-27/` | `equivalence.csv` (320 raw folders, 380,492 objects), `columns_removed_summary.csv`, `other_differences_summary.csv`, `benchmark_identity.md` |

Names found in the headers of a run but not in the static list are added at run time (`shared_fields`), so a collector added later that
reuses a name is covered the first time it runs; the static list is for a schema that does not depend on which archives answered.
