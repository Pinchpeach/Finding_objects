# Radio/X-ray benchmark results

## Dataset

A separate radio/X-ray-selected benchmark was constructed so that the general
9,999-object benchmark remains representative of its original selection.

- Total spectroscopic truth objects: **951**
- STAR: **177**
- GALAXY: **327**
- QSO: **447**
- FIRST-selected radio objects: **600**
- X-ray-selected objects: **351**
- Truth labels: clean SDSS spectroscopy
- Radio/X-ray detection is a selection condition, not a truth label.

Observed selection breakdown:

| Selection | STAR | GALAXY | QSO |
|---|---:|---:|---:|
| RADIO_FIRST | 174 | 311 | 115 |
| XRAY_CATALOG | 3 | 16 | 332 |

The severe X-ray class imbalance is preserved instead of fabricating a balanced
sample. It means the current X-ray subset is useful mainly for QSO-focused
validation and is not yet sufficient for a strong three-class X-ray conclusion.

## Validated model comparison

Validated on GitHub Actions run **36293695121**, using the same split for both
models. Test rows: **178**.

| Metric | Optical/IR/UV baseline | Radio/X-ray enriched |
|---|---:|---:|
| Accuracy | 0.97753 | 0.97753 |
| Balanced accuracy | 0.97950 | 0.97696 |
| Macro F1 | 0.97856 | 0.97847 |
| Log loss | 0.06601 | 0.06362 |
| Multiclass Brier | 0.03173 | 0.03325 |
| ECE (10 bins) | 0.02949 | 0.03742 |
| RADIO_FIRST accuracy | 0.97414 | 0.97414 |
| XRAY_CATALOG accuracy | 0.98387 | 0.98387 |

Baseline confusion matrix:

| True \ Pred | STAR | GALAXY | QSO |
|---|---:|---:|---:|
| STAR | 35 | 0 | 1 |
| GALAXY | 0 | 53 | 0 |
| QSO | 0 | 3 | 86 |

Radio/X-ray enriched confusion matrix:

| True \ Pred | STAR | GALAXY | QSO |
|---|---:|---:|---:|
| STAR | 35 | 0 | 1 |
| GALAXY | 0 | 52 | 1 |
| QSO | 0 | 2 | 87 |

## Interpretation

Directly concatenating native radio/X-ray measurements did **not** improve
classification accuracy on this benchmark. Log loss improved slightly, but
balanced accuracy, Brier score and ECE became slightly worse. Therefore the
radio/X-ray feature branch should not be enabled unconditionally.

The enriched model changed one GALAXY/QSO decision in each direction: one QSO
error was corrected while one GALAXY became a new error. This is consistent
with radio/X-ray information carrying useful local evidence without yet being
reliable enough to improve the global classifier.

## Improvements applied

1. Preserve catalog-native radio/X-ray measurements captured at selection time,
   because later per-object public-service re-queries can fail or return zero
   coverage even for known selected detections.
2. Exclude detection-presence flags and cross-match separation from the native
   radio/X-ray feature branch. Since this dataset is selected by detection,
   these fields can encode sample-selection bias rather than astrophysics.
3. Add physical transforms: log radio flux, integrated/peak radio ratio, and
   log transforms for positive flux/rate/count measurements.
4. Keep an explicit optical/IR/UV baseline and evaluate the radio/X-ray branch
   on exactly the same train/calibration/test split.
5. Add a **calibration-gated adaptive classifier**. The radio/X-ray branch is
   selected only if a held-out calibration-selection subset shows at least
   0.005 lower log loss and a non-worse Brier score. The final test set is not
   used for model selection.

## Relevant commits

- `6243f0a` — preserve native radio/X-ray measurements
- `57d9538` — allow observed class mixture in radio/X-ray benchmark
- `2a9954c` — separate baseline and physical radio/X-ray feature model
- `04b3efe` — compare baseline and enriched models
- `0955817` — fast reproducible model-comparison workflow
- `ad4850a` — calibration-gated radio/X-ray classifier
- `e883e84` — adaptive model validation workflow

## Next scientific limitation

The primary limitation is not current classifier accuracy but X-ray truth
coverage by class: only three X-ray-selected STAR objects and sixteen GALAXY
objects are present. Future expansion should seek additional independently
spectroscopically confirmed X-ray STAR/GALAXY samples before assigning large
global weights to X-ray features.
