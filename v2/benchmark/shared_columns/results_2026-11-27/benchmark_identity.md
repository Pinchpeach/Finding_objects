Local coarse benchmark, both trees (2.61.3 = before, this change = after), `PYTHONHASHSEED=0`, commands of CLAUDE.md:

| output | md5 (before = after) |
|---|---|
| ready/benchmark_manifest.csv | 770c84fe1142 |
| eval/rule_baseline_metrics.json | 3f76af5bcc69 |
| eval/rule_baseline_test_predictions.csv (1,991 rows) | 5190d1ada19f |

The benchmark runs on per-catalogue feature tables (no Stage 2), so it exercises only the readers (Stage 4, coarse_gbm): their code did not
change (comments only); the identity says that the one-catalogue tables still read their bare names.
