# Method 2 calibration and classification policy

## Counterpart probabilities
Science-use probabilities must use **official survey footprint membership** and the survey-provided angular resolution/positional uncertainty. A nearby empty catalog query is not accepted as proof of non-coverage. FWHM is converted to Gaussian sigma only when a more appropriate per-source positional error/PSF is unavailable. Frequency-, band-, epoch-, and off-axis-dependent resolution must use the corresponding survey value.

The positional association model is a likelihood-ratio/Bayesian model: true-match positional density is compared with the local background source density. Survey counterpart fraction Q is calibrated on spectroscopy-confirmed reference objects. Report both chance-coincidence probability and calibrated posterior. Position alone cannot create a confirmed physical counterpart; SED continuity, redshift, morphology and variability are independent evidence channels.

## Status vocabulary
- not_observed: outside official footprint / no usable observation.
- observed_no_counterpart: inside footprint, no catalog source satisfying the search.
- probable_counterpart: calibrated posterior above the validated threshold.
- ambiguous: insufficient evidence or competing candidates.
- likely_not_same_object: calibrated posterior below the rejection threshold.
- no_response: service/query failure; never interpreted astrophysically.

## Classification
Method 2 spectroscopy-confirmed objects are immutable reference labels. Method 1 objects are predictions only. The first classifier uses spectral-line feature distributions learned from Method 2 and returns class probabilities plus the second-best class. Later versions add calibrated multi-band SED, counterpart, morphology and variability features. Predictions are never copied into the reference set.
