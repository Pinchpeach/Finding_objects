# Reproducibility of the scientific cross validation (2.61.9)

Tables read from git (`git log`/`git show`, no network) by `history_table.py`, `refit_check.py` and `ci_test_inventory.py`; reasons and the fix in
`v2/WORK_REPORT_2026-11-27g.md`.

| file | what it holds |
|---|---|
| `models_history.csv` | every bot commit since 2026-10-25: Platt coefficient, intercept, n, positives, negatives per axis / class, and the rule precisions |
| `sample_history.csv` | per commit and truth class: rows, SHA-256 of the id set, ids kept from the previous commit, exact-match and classified rate, rows in which a collector raised |
| `sample_states.csv` | the distinct truth-id sets of each class over the 25 commits and in how many commits each occurred |
| `exact_match_range.csv` | lowest / highest exact-match and classified rate per class, and in how many commits a collector raised |
| `refit_check.csv` | a refit of the committed predictions reproduces the committed `models.json` (8 commits): the coefficients are a function of the predictions |
| `ci_test_inventory.csv` | tests that exist against tests a workflow runs |

Reproduce: `python history_table.py --out .`, `python refit_check.py --out refit_check.csv`, `python ci_test_inventory.py --out ci_test_inventory.csv` (from the repository root).
