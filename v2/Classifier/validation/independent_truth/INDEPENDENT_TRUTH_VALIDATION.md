# Independent truth-set cross-validation

Truth-catalog rows are used only as coordinates/labels. The same catalog is excluded from production evidence for that validation family.

| axis | class | n | classified | coverage | exact all | exact classified | family all | family classified |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| compact | PULSAR | 250 | 1 | 0.4% | 0.0% | 0.0% | 0.4% | 100.0% |
| phenomenon | PN | 250 | 0 | 0.0% | 0.0% | n/a | 0.0% | n/a |
| phenomenon | SN | 250 | 2 | 0.8% | 0.8% | 100.0% | 0.8% | 100.0% |
| physical | AGB | 250 | 106 | 42.4% | 0.0% | 0.0% | 42.4% | 100.0% |
| physical | RGB | 203 | 105 | 51.7% | 0.0% | 0.0% | 51.7% | 100.0% |
| variability | CEPHEID | 250 | 241 | 96.4% | 91.6% | 95.0% | 91.6% | 95.0% |
| variability | LPV | 250 | 189 | 75.6% | 64.8% | 85.7% | 64.8% | 85.7% |
| variability | MIRA | 250 | 250 | 100.0% | 91.6% | 91.6% | 100.0% | 100.0% |
| variability | RR_LYRAE | 250 | 235 | 94.0% | 81.2% | 86.4% | 81.2% | 86.4% |

Exact accuracy requires the requested leaf label. Family accuracy additionally credits a Mira truth object classified as the broader Gaia LPV family, and a pulsar classified as a radio pulsar candidate, and an RGB or AGB star classified as a red giant; it is reported separately and never substituted for the exact value. UNKNOWN is abstention. Low coverage is therefore reported separately from errors. Pulsar truth explicitly excludes ATNF evidence, and SN truth excludes Asiago evidence; those rows test whether another evidence family can independently recover the identity.
