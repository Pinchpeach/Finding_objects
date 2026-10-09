# Independent truth-set cross-validation

Truth-catalog rows are used only as coordinates/labels. The same catalog is excluded from production evidence for that validation family.

| axis | class | n | classified | coverage | exact all | exact classified | family all | family classified |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| compact | PULSAR | 250 | 0 | 0.0% | 0.0% | n/a | 0.0% | n/a |
| phenomenon | PN | 250 | 233 | 93.2% | 93.2% | 100.0% | 93.2% | 100.0% |
| phenomenon | SN | 250 | 2 | 0.8% | 0.8% | 100.0% | 0.8% | 100.0% |
| physical | AGB | 250 | 0 | 0.0% | 0.0% | n/a | 0.0% | n/a |
| physical | RGB | 203 | 0 | 0.0% | 0.0% | n/a | 0.0% | n/a |
| variability | CEPHEID | 250 | 236 | 94.4% | 91.6% | 97.0% | 91.6% | 97.0% |
| variability | LPV | 250 | 176 | 70.4% | 66.8% | 94.9% | 66.8% | 94.9% |
| variability | MIRA | 250 | 240 | 96.0% | 0.0% | 0.0% | 96.0% | 100.0% |
| variability | RR_LYRAE | 250 | 228 | 91.2% | 80.8% | 88.6% | 80.8% | 88.6% |

Exact accuracy requires the requested leaf label. Family accuracy additionally credits a Mira truth object classified as the broader Gaia LPV family; it is reported separately and never substituted for the exact value. UNKNOWN is abstention. Low coverage is therefore reported separately from errors. Pulsar truth explicitly excludes ATNF evidence, and SN truth excludes Asiago evidence; those rows test whether another evidence family can independently recover the identity.
