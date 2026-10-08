# Model status and applied accuracy improvement — 2026-10-08

## Decision

The classifier should continue to expose its strongest validated routes, but it
is not yet a generally validated all-sky multi-class classifier. The immediate
correctness improvement is to abstain on an unvalidated physical state rather
than converting generic stellar evidence into the physical label
`OTHER_STELLAR`.

This release applies that change and does **not** claim a higher all-object
accuracy. It trades unsupported physical labels for `UNKNOWN`, so coverage and
accuracy must be read together.

## Current evidence by branch

| Branch | Independent evaluation | Current assessment |
|---|---|---|
| WD vs normal star | 977 Gaia-matched LAMOST sources, primarily DA WDs | 99.69% classified-only accuracy; strongest branch, but not a full subtype validation. |
| WD DA/DB with Gaia XP | 213 independent SDSS DR14 XP sources | 95.31% ungated; 100% for 128/213 at `p >= 0.90`. Only DA/DB are in scope. |
| Coarse STAR/GALAXY/QSO | 1,991 SDSS test sources | 33.8% coverage, 88.4% classified-only accuracy; QSO coverage remains weak. |
| Radio/X-ray enrichment | 178 held-out test rows from 951-object benchmark | No accuracy gain over baseline; remains calibration-gated. |
| Real named-source routes | Nine positive/negative controls | 9/9 expected-axis matches. These are integration controls, not a population accuracy estimate. |
| Independent multi-axis truth | Previous 8-per-class run | Cepheid and classified LPV results were strong; RGB/AGB were overconfident, while pulsar and SN lacked independent evidence coverage. |

The previous small independent truth report measured RGB as 1/8 correct while
classifying all 8, and AGB as 0/8 correct while classifying all 8. Those rows
had Gaia/IR catalog coverage but no validated evolutionary-state evidence for
the requested label. `OTHER_STELLAR` therefore looked like a physical answer
despite only establishing a stellar family.

## Applied change

`axes/physical.py` now returns:

```text
physical_class  = UNKNOWN
physical_status = STAR_LIKE_NO_VALIDATED_PHYSICAL_STATE
```

when the evidence supports only `STAR_LIKE` or `BINARY_CANDIDATE` and neither
the WD, RGB, nor AGB branch has independently validated the physical state.
The output still retains the original stellar-family evidence inside the
evidence payload. WD, validated Gaia-FLAME RGB, and Suh-catalog AGB routes are
unchanged.

The independent report also now keeps two metrics:

- **exact accuracy**, which requires the requested leaf label;
- **family accuracy**, which separately credits a Mira truth object mapped to
  Gaia's broader LPV family.

Family accuracy never replaces exact accuracy. This prevents the previous
Mira-to-LPV behaviour from being presented as Mira subtype accuracy.

Finally, the sharded scientific validation workflow no longer cancels an
already-running long evaluation when a later documentation or harness update
is pushed.

## Fresh external regression check

The updated physical axis was executed on 2026-10-08 against the same
independent Vrard+2025 truth coordinates, with live Gaia DR3 physical,
AllWISE, 2MASS, and Suh catalog retrieval. The truth catalog itself was not an
input to the classifier.

| Truth class | N | Before: coverage / exact accuracy when classified | After: coverage / exact accuracy when classified |
|---|---:|---:|---:|
| RGB | 8 | 100.0% / 12.5% | **12.5% / 100.0%** (1 correct supported label) |
| AGB | 8 | 100.0% / 0.0% | **0.0% / n/a** |

The all-row exact accuracy is unchanged (RGB 12.5%, AGB 0.0%) because an
abstention is not counted as a correct classification. This is intentional:
the change reduces false physical claims; it does not invent new RGB/AGB
evidence or relabel truth to improve a score.

## Validation completed

- Python compilation passed for the changed classifier and validation harness.
- Six cross-match, calibration, and reporting tests passed.
- Physical-axis, multi-axis route, and end-to-end controller smoke tests passed.
- The live 16-row external physical-axis regression completed successfully.

## Next algorithm work

The accuracy-limited branches require new information, not a threshold tuned on
the same test set:

1. add independently validated asteroseismic/evolutionary evidence for
   RGB/AGB, then reserve a new held-out truth set for evaluation;
2. add period, amplitude, and light-curve shape features before attempting an
   exact Mira label from Gaia LPV;
3. add independent compact-object and transient evidence before attempting
   pulsar/SN recall improvements;
4. complete the 250-per-class sharded workflow, then fit per-axis calibration
   only where it meets its preregistered support thresholds.

The current report files should therefore be read as evidence-limited
classification results, with coverage reported alongside accuracy.
