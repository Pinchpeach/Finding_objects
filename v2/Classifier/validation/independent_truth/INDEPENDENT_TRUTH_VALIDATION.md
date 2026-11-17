# Independent truth-set cross-validation

Truth-catalog rows are used only as coordinates/labels. The same catalog is excluded from production evidence for that validation family.

| axis | class | n | classified | coverage | exact all | exact classified | family all | family classified |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| compact | PULSAR | 250 | 2 | 0.8% | 0.0% | 0.0% | 0.8% | 100.0% |
| phenomenon | PN | 250 | 191 | 76.4% | 73.2% | 95.8% | 73.2% | 95.8% |
| phenomenon | SN | 250 | 2 | 0.8% | 0.8% | 100.0% | 0.8% | 100.0% |
| physical | AGB | 250 | 105 | 42.0% | 0.0% | 0.0% | 42.0% | 100.0% |
| physical | RGB | 203 | 98 | 48.3% | 0.0% | 0.0% | 48.3% | 100.0% |
| variability | CEPHEID | 250 | 236 | 94.4% | 88.8% | 94.1% | 88.8% | 94.1% |
| variability | LPV | 250 | 177 | 70.8% | 61.6% | 87.0% | 61.6% | 87.0% |
| variability | MIRA | 250 | 248 | 99.2% | 89.6% | 90.3% | 99.2% | 100.0% |
| variability | RR_LYRAE | 250 | 236 | 94.4% | 80.4% | 85.2% | 80.4% | 85.2% |

Exact accuracy requires the requested leaf label. Family accuracy additionally credits a Mira truth object classified as the broader Gaia LPV family, and a pulsar classified as a radio pulsar candidate, and an RGB or AGB star classified as a red giant; it is reported separately and never substituted for the exact value. UNKNOWN is abstention. Low coverage is therefore reported separately from errors. Pulsar truth explicitly excludes ATNF evidence, and SN truth excludes Asiago evidence; those rows test whether another evidence family can independently recover the identity.
