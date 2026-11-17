# Independent truth-set cross-validation

Truth-catalog rows are used only as coordinates/labels. The same catalog is excluded from production evidence for that validation family.

| axis | class | n | classified | coverage | exact all | exact classified | family all | family classified |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| compact | PULSAR | 250 | 2 | 0.8% | 0.0% | 0.0% | 0.8% | 100.0% |
| phenomenon | PN | 250 | 231 | 92.4% | 88.4% | 95.7% | 88.4% | 95.7% |
| phenomenon | SN | 250 | 2 | 0.8% | 0.8% | 100.0% | 0.8% | 100.0% |
| physical | AGB | 250 | 105 | 42.0% | 0.0% | 0.0% | 42.0% | 100.0% |
| physical | RGB | 203 | 105 | 51.7% | 0.0% | 0.0% | 51.7% | 100.0% |
| variability | CEPHEID | 250 | 240 | 96.0% | 90.0% | 93.8% | 90.0% | 93.8% |
| variability | LPV | 250 | 180 | 72.0% | 62.8% | 87.2% | 62.8% | 87.2% |
| variability | MIRA | 250 | 250 | 100.0% | 92.8% | 92.8% | 100.0% | 100.0% |
| variability | RR_LYRAE | 250 | 236 | 94.4% | 80.8% | 85.6% | 80.8% | 85.6% |

Exact accuracy requires the requested leaf label. Family accuracy additionally credits a Mira truth object classified as the broader Gaia LPV family, and a pulsar classified as a radio pulsar candidate, and an RGB or AGB star classified as a red giant; it is reported separately and never substituted for the exact value. UNKNOWN is abstention. Low coverage is therefore reported separately from errors. Pulsar truth explicitly excludes ATNF evidence, and SN truth excludes Asiago evidence; those rows test whether another evidence family can independently recover the identity.
