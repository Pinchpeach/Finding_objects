# Independent truth-set cross-validation

Truth-catalog rows are used only as coordinates/labels. The same catalog is excluded from production evidence for that validation family.

| axis | class | n | classified | coverage | accuracy all | accuracy classified |
|---|---|---:|---:|---:|---:|---:|
| compact | PULSAR | 8 | 0 | 0.0% | 0.0% | n/a |
| phenomenon | PN | 8 | 6 | 75.0% | 75.0% | 100.0% |
| phenomenon | SN | 8 | 0 | 0.0% | 0.0% | n/a |
| physical | AGB | 8 | 8 | 100.0% | 0.0% | 0.0% |
| physical | RGB | 8 | 8 | 100.0% | 12.5% | 12.5% |
| variability | CEPHEID | 8 | 8 | 100.0% | 100.0% | 100.0% |
| variability | LPV | 8 | 5 | 62.5% | 62.5% | 100.0% |
| variability | MIRA | 8 | 7 | 87.5% | 0.0% | 0.0% |
| variability | RR_LYRAE | 8 | 8 | 100.0% | 75.0% | 75.0% |

UNKNOWN is abstention. Low coverage is therefore reported separately from errors. Pulsar truth explicitly excludes ATNF evidence, and SN truth excludes Asiago evidence; those rows test whether another evidence family can independently recover the identity.
