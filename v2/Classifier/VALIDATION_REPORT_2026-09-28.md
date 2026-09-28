# v2 Classifier Scientific Validation Report — 2026-09-28

## Executive summary

The v2 pipeline now produces scientifically interpretable measurements and can
recover several physically distinct classes from independent catalog evidence.
It is **not yet a uniformly validated discovery classifier across all requested
classes**. Performance depends strongly on whether a scientifically diagnostic
catalog/measurement is available and whether cross-survey association succeeds.

The latest completed blind named-source validation used SIMBAD only to resolve
the requested coordinate and external reference type. No SIMBAD row or otype was
passed into the blind pipeline.

Latest completed named-source result:

- requested targets: **9**
- successfully executed: **9/9**
- exact expected-axis matches: **6/9 = 66.7%**
- targets with usable independent blind catalog evidence: **7/9**
- exact matches among evidence-available targets: **6/7 = 85.7%**
- the evidence-available failure was **Mira physical=AGB**, where the Suh (2021)
  AGB collector returned a counterpart but it was not fused into the selected
  physical object.

These nine named objects are diagnostic positive/negative controls, not a
statistically representative population. The large truth-set benchmarks below
remain the appropriate quantitative performance measurements.

## 1. Validation layers

| Layer | Independent truth / sample | Result | Interpretation |
|---|---|---:|---|
| Preprocess coarse STAR/GALAXY/QSO | 1,991-object SDSS spectroscopic test split | 33.8% coverage; 88.4% classified-only accuracy; 74.7% macro-F1 | Conservative, high abstention; QSO remains weakest |
| WD vs normal star external | 977 Gaia-matched LAMOST objects independent of SDSS training truth | 99.90% coverage; 99.69% classified-only accuracy | Strong WD branch, mainly validated for DA WDs |
| WD DA/DB subtype external | 213 independent SDSS DR14 XP-available WDs | 95.31% ungated; p>=0.90 gives 128/213 coverage and 100% accuracy | Gated DA/DB inference is useful but label space is narrow |
| Radio/X-ray benchmark | 951 spectroscopic truth objects; 178 test rows | baseline and enriched accuracy both 97.753% | Radio/X-ray should not be globally enabled without calibration benefit |
| NGC4522 E2E | real multi-catalog field | pipeline execution success | Engineering/E2E validation, not an object-class accuracy benchmark |
| Named-source blind E2E | 9 physically diverse named objects | 6/9 overall; 6/7 with evidence | Exposes real retrieval/association/coverage failures |

## 2. Blind named-source validation

The current completed result is stored in:

- `v2/Classifier/validation/REAL_SAMPLE_VALIDATION.md`
- `v2/Classifier/validation/real_sample_validation.csv`
- result commit: `a62828bd5c1fda6e12ae69a341c68ca01b94c6ff`

| Object | Expected axis label | Blind result | Status | Scientific interpretation |
|---|---|---|---|---|
| GD 71 | physical=WD | **WD** | CLASSIFIED_WD | Recovered from Gaia astrometry/photometry after allowing strong physical evidence through coarse UNKNOWN |
| RR Lyr | variability=RR_LYRAE | **RR_LYRAE** | GAIA_DR3_VARIABLE_CANDIDATE | Correct variability recovery from Gaia |
| delta Cep | variability=CEPHEID | **CEPHEID** | GAIA_DR3_VARIABLE_CANDIDATE | Correct variability recovery from Gaia |
| Mira | physical=AGB | OTHER_STELLAR | STELLAR_UNREFINED | Gaia identifies LPV behaviour, but AGB catalog counterpart is not fused into selected object |
| PSR B0531+21 | compact=PULSAR | **PULSAR** | ATNF_CATALOG_MATCH | Correct independent ATNF counterpart |
| M 57 | phenomenon=PN | **PN** | HASH_PN_CATALOG_MATCH | Correct independent HASH PN counterpart |
| SN 2018oh | phenomenon=SN | UNKNOWN | NO_BLIND_CATALOG_EVIDENCE | Selected ASAS-SN VizieR query returned zero; catalog/sample coverage issue |
| SN 2011fe | phenomenon=SN | UNKNOWN | NO_BLIND_CATALOG_EVIDENCE | Deliberate coverage/abstention control; no independent SN collector queried |
| 3C 273 | extragalactic=AGN | **AGN** | GAIA_DR3_AGN_CANDIDATE | Gaia variability evidence supports AGN; SIMBAD main type BLL is also an AGN-family identity |

### Progress across validation rounds

| Round | Main change | Exact blind matches |
|---|---|---:|
| Initial named-source test | masked SIMBAD rows still entered association; Gaia complex TAP joins fragile | 1/8 = 12.5% |
| Retrieval/leakage fix | SIMBAD removed from blind raw input; Gaia source retrieved before optional tables; target selection improved | 3/8 = 37.5% |
| Physical/phenomenon fix | coarse UNKNOWN no longer vetoes validated WD evidence; HASH PN added; 3C273 taxonomy corrected to AGN | 6/9 = 66.7% |

The improvement is not from relaxing labels arbitrarily. It comes from removing
validation leakage, preserving partial Gaia measurements when auxiliary services
fail, and allowing already-validated physical evidence to reach the relevant
axis.

## 3. Scientific measurements actually extracted

The following values are derived directly from the completed blind validation
measurements. Inverse-parallax distances are quoted only for high-S/N examples
and are simple diagnostic estimates, not full Bayesian distance inferences.

| Object | Extracted / derived quantity | Value | Note |
|---|---|---:|---|
| GD 71 | parallax | 19.5638 ± 0.0551 mas | Gaia DR3 |
| GD 71 | simple 1/parallax distance | 51.115 ± 0.144 pc | very high parallax S/N |
| GD 71 | Gaia absolute G | 9.457 mag | from G=12.9998 and parallax |
| GD 71 | BP-RP | -0.4523 mag | blue WD-like SED |
| RR Lyr | parallax | 3.98486 ± 0.02652 mas | Gaia DR3 |
| RR Lyr | simple 1/parallax distance | 250.95 ± 1.67 pc | diagnostic estimate |
| RR Lyr | Gaia absolute G | 0.621 mag | diagnostic |
| RR Lyr | Gaia variable class | RR | catalog score 0.5516; score is not treated as calibrated probability |
| delta Cep | parallax | 3.5551 ± 0.1475 mas | Gaia DR3 |
| delta Cep | simple 1/parallax distance | 281.3 ± 11.7 pc | caution: RUWE=2.713 |
| delta Cep | Gaia absolute G | -3.395 mag | diagnostic |
| delta Cep | Gaia variable class | CEP | catalog score 0.1606; not a posterior probability |
| Mira | BP-RP | 5.5906 mag | extremely red |
| Mira | Gaia variable class | LPV | correctly captures variability even though physical AGB association failed |
| Crab pulsar | period P | 0.0333924123 s | ATNF |
| Crab pulsar | period derivative Pdot | 4.20972e-13 s/s | ATNF |
| Crab pulsar | characteristic age P/(2Pdot) | 1,256.8 yr | standard spin-down diagnostic |
| Crab pulsar | dipole B estimate | 3.79e12 G | 3.2e19 sqrt(P Pdot), standard vacuum-dipole estimate |
| Crab pulsar | spin-down power estimate | 4.46e38 erg/s | assumes moment of inertia I=1e45 g cm^2 |
| M 57 | HASH counterpart separation | 0.291 arcsec | independent PN catalog match |
| 3C 273 | parallax | -0.01595 ± 0.02080 mas | consistent with zero |
| 3C 273 | total proper-motion magnitude | ~0.101 mas/yr | consistent with extragalactic behaviour at this precision |
| 3C 273 | Gaia variable class | AGN | independent AGN evidence |

A machine-readable version is stored in
`v2/Classifier/validation/scientific_derived_metrics.csv`.

## 4. What is scientifically working

### WD

This is currently the strongest detailed physical branch.

The independent LAMOST validation contains 977 Gaia-matched objects. The
literature Gaia HR-locus rule reaches 99.69% overall accuracy and 100% WD
precision in that external sample. The production policy combines this physical
signal with a calibrated learned fallback and abstains on conflicts.

The GD 71 blind recovery confirms that the same branch also works in the
sky-to-catalog-to-classifier path when Gaia measurements are available.

### Variable stars

RR Lyr and delta Cep were recovered directly from Gaia DR3 variability evidence
without feeding the SIMBAD type into the classifier. This validates the routing
for RR Lyrae and Cepheid positive controls.

Gaia `best_class_score` is retained as evidence metadata only. It is not
interpreted as a calibrated class probability.

### Pulsars

The Crab pulsar was recovered independently through the ATNF Pulsar Catalog.
The pipeline also preserved timing measurements sufficiently well to derive
standard pulsar quantities such as characteristic age and dipole-field scale.

### Planetary nebulae

M 57 was recovered through an independent HASH PN counterpart. This establishes
that the phenomenon axis can ingest a PN-specific catalog rather than relying
only on SIMBAD labels.

However, this is still **catalog identity evidence**, not yet an independent
spectroscopic PN classifier. A future PN branch should use diagnostic emission
lines/ratios where spectra are available.

### AGN

3C 273 was recovered as AGN through Gaia variability evidence. Its nearly zero
parallax/proper motion is also qualitatively consistent with an extragalactic
source, though those astrometric values alone are not sufficient to determine
the AGN subtype.

## 5. Remaining scientific failures

### 5.1 AGB association is the clearest current cross-match failure

For Mira:

- Gaia retrieval succeeded and returned `best_class_name=LPV`.
- AllWISE retrieval succeeded.
- 2MASS retrieval succeeded.
- Suh (2021) AGB retrieval succeeded with one row.
- The final selected integrated object was still `OTHER_STELLAR`.

This means the evidence exists but is being lost at **counterpart association /
object integration**, not at catalog retrieval.

The current Stage-1 association has a hard maximum match radius of 2 arcsec.
That is too simplistic for a heterogeneous set containing high-proper-motion
stars and IRAS/WISE-derived positions. This should be replaced by an
epoch-aware, survey-uncertainty-aware association likelihood.

### 5.2 Multi-epoch astrometry is not yet handled rigorously

Gaia DR3 positions/proper motions refer to reference epoch J2016.0. The current
association stage compares catalog coordinates directly without propagating
positions to a common epoch.

RR Lyr demonstrates why this matters: its Gaia proper motion is approximately
(-109.6, -195.9) mas/yr and its Gaia position is several arcseconds from the
validation reference coordinate. The class was recovered because the validation
cone was broad enough, but a strict cross-match can fragment such objects.

Required change:

1. preserve a `ref_epoch` or observation epoch per catalog row where available;
2. propagate Gaia five-parameter astrometry to the candidate catalog epoch;
3. compute the positional likelihood using propagated uncertainty;
4. apply survey PSF/FWHM and source-density terms separately for confusion/chance association.

### 5.3 SN classification is primarily a coverage problem

The completed named-source run did not independently recover SN 2018oh or
SN 2011fe because no usable SN-catalog row reached the blind pipeline.

This should not be solved by labeling any transient-looking source as SN.
The correct next step is to add event-time-aware transient catalogs/light curves
and, where available, spectroscopic SN evidence.

### 5.4 Coarse QSO coverage is still weak

On the 1,991-object SDSS spectroscopic coarse benchmark, most QSO truth objects
abstain and 75 are routed to GALAXY while only 25 reach QSO. This remains the
largest coarse-class weakness even though the detailed AGN positive control
works.

### 5.5 Radio/X-ray data must remain calibration-gated

The 951-object radio/X-ray benchmark shows that naïvely concatenating native
radio/X-ray features did not improve test accuracy and slightly worsened several
calibration metrics. High-energy/radio evidence should therefore remain
conditional rather than receiving a large unconditional global weight.

## 6. Reliability changes made during this validation

- Gaia retrieval now acquires `gaia_source` first and joins astrophysical /
  variability products independently by `source_id`.
- Supplementary Gaia-table failure no longer erases base astrometry/photometry.
- SIMBAD rows were removed entirely from blind validation input.
- A coarse `UNKNOWN` no longer blocks a strongly validated WD HR-locus signal.
- ATNF pulsar and HASH PN catalog routes are independent classification evidence.
- Missing catalog coverage remains UNKNOWN/abstention rather than negative evidence.

## 7. Priority work from here

1. **Epoch-aware source association** — highest priority. Add catalog epochs and
   Gaia proper-motion propagation before cross-survey positional likelihood.
2. **Survey-specific association calibration** — use positional errors,
   official PSF/FWHM and local source density instead of a universal 2 arcsec cap.
3. **Repair AGB fusion** — distinguish WISE-position and IRAS-position AGB rows
   and use the appropriate positional uncertainty model.
4. **Transient/event branch** — add independent SN/transient catalogs and
   observation time; do not treat host-galaxy detections as the event itself.
5. **PN spectroscopy** — add emission-line evidence so PN can be inferred even
   when HASH is absent.
6. **Per-axis truth benchmarks** — expand independent truth to statistically
   useful samples for RGB, AGB, RR Lyrae, Cepheid, Mira, pulsar/NS, PN and SN.
7. **Likelihood calibration** — calibrate each axis/evidence family before
   calling fused values probabilities.

## 8. Bottom-line assessment

The pipeline is now demonstrably capable of producing real scientific
measurements and scientifically meaningful classifications for several branches.
The strongest evidence is for WD, RR Lyrae/Cepheid variability, pulsars, PN
catalog counterparts and AGN.

The current limiting factor is increasingly **not the classifier function
itself**, but the integrity and coverage of the observation-to-counterpart layer.
In particular, epoch-aware association and survey-specific positional
calibration are required before the system can be described as a reliable
all-sky multi-class discovery pipeline.

The conservative abstention policy should be retained while those gaps are
closed.
