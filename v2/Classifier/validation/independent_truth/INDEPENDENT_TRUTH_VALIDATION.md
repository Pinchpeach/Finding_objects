# Independent truth-set cross-validation

Truth-catalog rows are used only as coordinates/labels. The same catalog is excluded from production evidence for that validation family.

| axis | class | n | classified | coverage | exact all | exact classified | family all | family classified |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| compact | PULSAR | 250 | 2 | 0.8% | 0.0% | 0.0% | 0.8% | 100.0% |
| phenomenon | PN | 250 | 225 | 90.0% | 86.0% | 95.6% | 86.0% | 95.6% |
| phenomenon | SN | 250 | 2 | 0.8% | 0.8% | 100.0% | 0.8% | 100.0% |
| physical | AGB | 250 | 118 | 47.2% | 0.0% | 0.0% | 47.2% | 100.0% |
| physical | RGB | 203 | 168 | 82.8% | 0.0% | 0.0% | 82.8% | 100.0% |
| variability | CEPHEID | 250 | 241 | 96.4% | 91.2% | 94.6% | 91.2% | 94.6% |
| variability | LPV | 250 | 192 | 76.8% | 63.6% | 82.8% | 63.6% | 82.8% |
| variability | MIRA | 250 | 249 | 99.6% | 94.8% | 95.2% | 99.6% | 100.0% |
| variability | RR_LYRAE | 250 | 237 | 94.8% | 80.8% | 85.2% | 80.8% | 85.2% |

Exact accuracy requires the requested leaf label. Family accuracy additionally credits a Mira truth object classified as the broader Gaia LPV family, and a pulsar classified as a radio pulsar candidate, and an RGB or AGB star classified as a red giant; it is reported separately and never substituted for the exact value. UNKNOWN is abstention. Low coverage is therefore reported separately from errors. Pulsar truth explicitly excludes ATNF evidence, and SN truth excludes Asiago evidence; those rows test whether another evidence family can independently recover the identity.
