# Independent truth-set cross-validation

Truth-catalog rows are used only as coordinates/labels. The same catalog is excluded from production evidence for that validation family.

| axis | class | n | classified | coverage | exact all | exact classified | family all | family classified |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| compact | PULSAR | 250 | 4 | 1.6% | 0.0% | 0.0% | 1.6% | 100.0% |
| phenomenon | PN | 250 | 206 | 82.4% | 78.8% | 95.6% | 78.8% | 95.6% |
| phenomenon | SN | 250 | 2 | 0.8% | 0.8% | 100.0% | 0.8% | 100.0% |
| physical | AGB | 250 | 123 | 49.2% | 0.0% | 0.0% | 49.2% | 100.0% |
| physical | RGB | 203 | 128 | 63.1% | 0.0% | 0.0% | 63.1% | 100.0% |
| variability | CEPHEID | 250 | 239 | 95.6% | 90.0% | 94.1% | 90.0% | 94.1% |
| variability | LPV | 250 | 188 | 75.2% | 62.4% | 83.0% | 62.4% | 83.0% |
| variability | MIRA | 250 | 250 | 100.0% | 93.2% | 93.2% | 100.0% | 100.0% |
| variability | RR_LYRAE | 250 | 240 | 96.0% | 81.6% | 85.0% | 81.6% | 85.0% |

Exact accuracy requires the requested leaf label. Family accuracy additionally credits a Mira truth object classified as the broader Gaia LPV family, and a pulsar classified as a radio pulsar candidate, and an RGB or AGB star classified as a red giant; it is reported separately and never substituted for the exact value. UNKNOWN is abstention. Low coverage is therefore reported separately from errors. Pulsar truth explicitly excludes ATNF evidence, and SN truth excludes Asiago evidence; those rows test whether another evidence family can independently recover the identity.
