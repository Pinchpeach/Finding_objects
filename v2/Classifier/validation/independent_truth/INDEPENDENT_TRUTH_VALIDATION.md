# Independent truth-set cross-validation

Truth-catalog rows are used only as coordinates/labels. The same catalog is excluded from production evidence for that validation family.

| axis | class | n | classified | coverage | exact all | exact classified | family all | family classified |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| compact | PULSAR | 250 | 0 | 0.0% | 0.0% | n/a | 0.0% | n/a |
| phenomenon | PN | 250 | 233 | 93.2% | 93.2% | 100.0% | 93.2% | 100.0% |
| phenomenon | SN | 250 | 2 | 0.8% | 0.8% | 100.0% | 0.8% | 100.0% |
| physical | AGB | 250 | 0 | 0.0% | 0.0% | n/a | 0.0% | n/a |
| physical | RGB | 203 | 0 | 0.0% | 0.0% | n/a | 0.0% | n/a |
| variability | CEPHEID | 250 | 240 | 96.0% | 93.2% | 97.1% | 93.2% | 97.1% |
| variability | LPV | 250 | 181 | 72.4% | 68.8% | 95.0% | 68.8% | 95.0% |
| variability | MIRA | 250 | 249 | 99.6% | 0.0% | 0.0% | 99.6% | 100.0% |
| variability | RR_LYRAE | 250 | 234 | 93.6% | 82.4% | 88.0% | 82.4% | 88.0% |

Exact accuracy requires the requested leaf label. Family accuracy additionally credits a Mira truth object classified as the broader Gaia LPV family; it is reported separately and never substituted for the exact value. UNKNOWN is abstention. Low coverage is therefore reported separately from errors. Pulsar truth explicitly excludes ATNF evidence, and SN truth excludes Asiago evidence; those rows test whether another evidence family can independently recover the identity.
