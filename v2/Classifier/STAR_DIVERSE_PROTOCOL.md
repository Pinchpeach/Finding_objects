# Prospective frozen STAR external-validation protocol

Defined before new predictions, 2026-09-27. This is a challenge-set experiment,
not a measurement of prevalence or all-sky completeness.

## Fixed estimator

Use the actual serialized model from Actions run 36295747956, artifact
`star-wd-classifier-eval`, with its original Gaia feature table and dependency
versions. Do not refit, recalibrate, select thresholds, or choose models using
the new data. First require reproduction of the original 183/194 test accuracy.
Record model and truth SHA256 hashes. Coordinates, source IDs, spectroscopy
labels, and sample membership are metadata only. Gaia measurement NaNs remain
NaNs. The existing frozen missingness schema is preserved.

## Truth sampling

- Guo et al. (2022), VizieR `J/MNRAS/509/2674/table3`: all exact
  DA/DB/DC/DQ/DZ/DO labels, with unique object names/positions. This adds non-DA
  coverage absent from the previous table6 DA-only validation.
- LAMOST DR5 `V/164/dr5`: ordinary O/B/A/F/G/K/M pipeline labels, sampled in
  four 90-degree RA quadrants. Query up to 2,000 candidates per family/quadrant,
  then take at most 100 by a fixed SHA256 ordering of observation ID.
- Save raw responses and the exact selected truth; report query truncation,
  underfilled cells, and subtype counts. Capped query pools still have ordering
  bias; RA stratification reduces concentration but does not remove selection
  bias. Pipeline normal-star labels are less secure than visual WD labels.
- Exclude positions within 2 arcsec of *all* original SDSS truth, the previously
  inspected LAMOST WD/normal set, and the previously inspected DA/DB subtype set.
- Match Gaia using the existing 2-arcsec nearest-match method. Then exclude
  matching Gaia source IDs against all original SDSS and previously inspected
  LAMOST rows. Collapse duplicate Gaia identities and reject conflicting binary
  truth labels, retaining an audit of every removed row.
- This positional association is not epoch propagated; high proper-motion
  objects and ambiguous crowded fields remain a limitation. Report attrition.

## Reporting and research gate

Report the frozen learned model and original HR baseline separately. Include
confusion matrices, Wilson 95% intervals for accuracy/recall/specificity/precision,
log loss, Brier score, subtype/family, magnitude, parallax-SNR and missing-feature
subgroups, and pre/post-match coverage. Pure subtype labels are used only to
audit WD detection, not as predictions.

Proceed to a subtype truth/design stage only if the lower Wilson 95% bounds of
both overall WD recall and normal-star specificity are at least 0.90, and the
non-DA group has at least 100 objects with recall lower bound at least 0.90.
These are explicit research criteria, not proof of production suitability.
Rare subtypes without adequate sample sizes remain unvalidated even if the
pooled gate passes. A failed gate must be reported without tuning the model
against this set. No six-class production classifier is enabled by this test.

## Sources

- [Guo et al. (2022), White dwarfs identified in LAMOST DR5](https://arxiv.org/abs/2111.04939)
- [VizieR WD catalogue](https://vizier.cds.unistra.fr/viz-bin/VizieR?-source=J/MNRAS/509/2674)
- [VizieR LAMOST DR5](https://vizier.cds.unistra.fr/viz-bin/VizieR?-source=V/164/dr5)
