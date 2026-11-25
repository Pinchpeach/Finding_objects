# Finding Objects: program overview

Program version 2.60.2 · 2026-11-24 · A field-level multi-catalogue integration and annotation tool for sources on the sky (radio to X-ray), with a coarse STAR / GALAXY / QSO classifier and a sub-classification layer

**Read first:** [Overview PDF, version 2.60.2 (English)](v2/document/OVERVIEW_v2.60.2.pdf) · [Release 2.60.2 with Windows, macOS and Linux downloads](https://github.com/Pinchpeach/Finding_objects/releases/tag/v2.60.2) · [How to run](#12-running-it) · [Algorithm in detail (Korean)](v2/ALGORITHM.md) · [Changelog (Korean)](v2/CHANGELOG.md)

The older material is listed in [section 15](#15-other-documents): the 2.36.1 overview (Korean) and the 2.44.0 deck (English) are kept but not updated.

## 1. At a glance

| Item | What it is |
|---|---|
| What it does | You give it a position and a radius (or an object name). It asks **30 public archives** for every catalogued source there, cross-matches the detections into **one row per object**, and reports for each object a coarse class, a sub-class where one can be given, the evidence behind the decision and **where each decision came from**. |
| Input | An object name (Sesame) or RA, Dec in degrees plus a radius; or a folder of catalogue files that were already collected (`--raw-dir`). |
| Coarse class | `STAR`, `GALAXY`, `QSO` or `UNKNOWN` (the classifier abstains, and says why, when the evidence is weak or in conflict). **What decides the class is optical colour and morphology, WISE mid-infrared colours, Gaia astrometry and the Gaia DSC class probabilities.** X-ray and radio data contribute nothing measurable to the coarse class (rule-ablation tests, version 2.51.0); they are used for tags and sub-types. It is not an "all-wavelength" classifier. |
| Provenance | Every decision says whether it was copied from a catalogue (`CATALOG`), taken from another survey's classifier (`EXTERNAL_CLASSIFIER`), inferred from measurements by this program (`INFERRED`) or is missing (`NONE`). The accuracy of a look-up is the accuracy of the catalogue it came from. |
| Sub-classes | Spectral types, white dwarfs, hot subdwarfs, ultracool dwarfs, red giants and AGB stars (carbon or oxygen rich), variable stars, pulsars, AGN and blazars, planetary nebulae, galaxy activity and more, plus five independent axes (physical state, variability, compact objects, extragalactic, phenomena). **Most sub-classes are catalogue look-ups**, see section 6. |
| Output | `objects_summary.csv` (29 columns to read first, one row per independent detected object), `classified_objects.csv` (the full record, 833–2,513 columns in the three 2.60.2 test fields depending on how many archives cover the field), `literature_only_entries.csv` (objects known only from NED or SIMBAD), stage CSVs, `catalog_coverage.json` and `pipeline_summary.csv`. |
| How to use | Desktop app for Windows, macOS and Linux (no Python needed) or the command line `v2/pipeline.py`, see section 12. |
| Working rules | Every threshold and rule needs a literature basis recorded in a code comment or a `LITERATURE*.md` note. Accuracy and speed are measured together; a change that costs one needs measurements for both. |

## 2. Processing flow

| Stage | What happens |
|---|---|
| **Collect** | 30 collectors in parallel (6 workers, a time budget per archive, a 3–5 s pause before every request, local cache, mirrors and fallback routes, footprint checks that skip archives that do not cover the field). A failed collector is recorded, not hidden. |
| **1 Associate** | Detections of the same object are grouped: positional likelihood ratio with each catalogue's error model, epoch and proper-motion propagation, chance-coincidence probability. |
| **2 Integrate** | One row per object, all original columns kept, units unified (AB magnitudes, mJy, redshift). |
| **3 Features** | Colours, morphology, signal-to-noise, quality flags, per-catalogue quality confidence. |
| **4 Evidence** | 35 literature-based rules turn measurements into STAR / GALAXY / QSO evidence. |
| **5 Coarse class** | Trained fusion (gradient-boosted trees plus a sign-constrained linear model), deterministic motion rule, one prior layer (position, magnitude, faint star:galaxy ratio), abstention. |
| **6-7 Sub-classes** | Sub-classifiers and five independent axes, each with the measured precision of the rule. |
| **Post-processing** | Large-galaxy fragments, duplicate PS1 detections, bright-star halos, unconfirmed detections, radio components, galaxy clusters, archive warnings, faint-quasar candidate flag, high-confidence flag. |

Output: `objects_summary.csv` (summary), `literature_only_entries.csv`, `classified_objects.csv` (full record). Every stage also writes its own CSV into the work directory so intermediate products can be inspected.

## 3. Data sources (30 collectors)

| Kind | Collectors | Mainly provides |
|---|---|---|
| Astrometry | Gaia DR3 (+ variability SOS, DSC, astrophysical parameters) | parallax and proper motion (decisive evidence for stars), class probabilities, variability |
| Optical | Pan-STARRS1 DR2, DESI Legacy Surveys DR10, SDSS DR18 imaging | colours, morphology (point source or extended), faint-object machine-learning evidence (LS-GBM) |
| UV / infrared | GALEX, 2MASS, AllWISE | UV colour, near-infrared colour, mid-infrared AGN colours |
| Radio | LoTSS DR2, FIRST, NVSS, TGSS, VLASS | radio flux, multi-component radio sources |
| X-ray | 4XMM-DR13, Chandra CSC 2.0, eROSITA eRASS1 | X-ray to optical ratio (tags and sub-types), cluster gas |
| Spectroscopy | SDSS DR18, DESI DR1 (+ FastSpecFit), LAMOST DR5 | spectral class (evidence), redshift, emission lines, stellar parameters |
| Time domain | ZTF periodic variables | variable-star sub-types |
| Special lists | ATNF pulsars, Roma-BZCAT, Suh 2021 AGB stars, Siena Galaxy Atlas, galaxy-cluster lists, MYStIX young stars, Galaxy Zoo DESI | pulsar, blazar and AGB tags, large-galaxy sizes, cluster membership, young-star membership, galaxy morphology |
| Literature databases | SIMBAD, NED | literature object types (low-weight evidence; objects known only from the literature are listed separately) |

If a key archive (Gaia, Pan-STARRS1, Legacy Surveys, AllWISE) cannot be queried, a warning is shown above the result table and the photometry-only high-confidence path is switched off. Section 10 describes the fallback routes.

## 4. Coarse classification (STAR / GALAXY / QSO)

### What actually decides the class

Rule-ablation tests (2.51.0; the same raw data classified with one rule group switched off) show which wavelengths do the work. Counts are objects whose label becomes right / wrong when the group is removed.

| Switched off | Bright fields (3,428 objects) | COSMOS deep fields (28,194) | Reading |
|---|---|---|---|
| Optical colour | 7 / 22 | 935 / 1,895 | the backbone of the classification |
| Optical morphology | 0 / 2 | 55 / 87 | matters at the faint end |
| WISE mid-infrared | 1 / 3 | 3 / 22 | contributes; QSO recall 96 to 92 % without it |
| Gaia astrometry | 2 / 4 | 0 / 0 | not significant in these samples |
| Gaia DSC | 3 / 3 | 0 / 0 | no effect when Legacy Surveys is present (large effect when it is missing) |
| Variability | 0 / 1 | 0 / 9 | small |
| X-ray and radio | 0 / 0 | 0 / 0 | **no contribution to the coarse class** (third confirmation) |

Gaia parallax and proper motion remain decisive evidence when they are significant (rule below), although removing them changed few labels in these samples. X-ray, radio and UV information is used for tags and sub-types.

### Evidence rules (35 rows of `v2/Preprocess/classification_rules.csv`)

| Group | Rows | Content |
|---|---|---|
| Spectroscopy (SPC) | 9 | SDSS, DESI and LAMOST spectral classes; confidence 1.0 or 0.5 by quality. Excluded from validation, where spectra are the truth |
| Optical (PS1, Legacy Surveys, SDSS) | 12 | morphology (PSF minus Kron, Tractor models), colour kNN, LS-GBM (gradient boosting trained on 149,769 DESI spectra, 95.6 % test accuracy), high-redshift QSO colour cut, PS1 variability |
| Astrometry (Gaia) | 4 | significant parallax or proper motion means a Galactic star; consistent with zero means extragalactic |
| Gaia DSC and variability | 2 | DSC class probability with its prior removed; Gaia variability |
| WISE | 3 | mid-infrared AGN colours (Stern 2012, Assef 2018 R90) and a colour rule |
| Radio and X-ray | 2 | radio strength, X-ray to optical ratio (linear features only) |
| Lists (SGA, NED, SIMBAD) | 3 | large-galaxy catalogue, literature types (low weight) |

### How the evidence is combined

- **Fusion:** gradient-boosted trees and a sign-constrained multinomial logistic model, each trained on the train split of the SDSS and DESI spectroscopic benchmarks, combined as a geometric mean. Evidence without training support (spectra, literature types) enters through literature prior weights. The test split is for reporting only.
- **Deterministic motion:** parallax or proper motion at 10σ or more with good quality means STAR, even against other evidence (extragalactic objects do not move).
- **One prior layer (2.52.0):** the probabilities are trained on a 1:1:1 class mix, so the real-sky class mix is applied once, before the decision (Saerens et al. 2002): a local Gaia-density position prior, a magnitude prior for QSOs, and a faint star:galaxy ratio counted from COSMOS2020 truth (4 % stars at r = 24). Before 2.52.0 the faint ratio was applied to the label only, so probability and label disagreed for 1,635 of 28,194 COSMOS objects.
- **Abstention:** the object is `UNKNOWN` with a reason when the top probability is below 0.50 or strong evidence conflicts (Chow 1970 reject option). `--min-confidence` raises the threshold.
- **Literature-only objects:** if the only basis is a NED or SIMBAD type, the type is shown with status `LITERATURE_LABEL` and no probability (a catalogue type is not a calibrated classifier output).

### Provenance of every decision

`CATALOG` (copied from a literature or spectroscopic list), `EXTERNAL_CLASSIFIER` (another survey's classifier: Gaia variability, ESP and DSC candidates, ZTF periodic list, Galaxy Zoo DESI), `INFERRED` (measured and inferred here), `NONE`. The coarse class is `CATALOG` only if removing the catalogue tags would change or remove the decision; if measurements alone give the same class it is `INFERRED`. The pipeline's own performance is therefore measured on `INFERRED` decisions.

## 5. Post-processing and result tables

| Step | What it does | Since |
|---|---|---|
| Large-galaxy grouping | pieces inside an SGA-2020 D26 ellipse (HII regions, nuclei, arms) are grouped under the parent galaxy | 2.2.0 |
| PS1 duplicates | several PS1 measurements of one galaxy become parts of that galaxy | 2.34.0 |
| Bright-star halos | single-catalogue artefacts around G < 16 stars are grouped under the star | 2.35.0 |
| Unconfirmed detections | objects seen only twice in PS1 and absent from the deeper Legacy Surveys, and Legacy-Surveys-only z-band detections without an r detection, are marked `UNCONFIRMED` (9 % of the latter have a COSMOS2020 counterpart, chance 3.5 %) | 2.30.0, 2.55.0 |
| Radio components | catalogue artefacts and lobes of radio galaxies are marked `RADIO_COMPONENT` | 2.31.0 |
| Galaxy clusters | brightest cluster galaxy and spectroscopic-redshift membership | 2.32.0 |
| Solar-system objects | PS1 flag and SDSS motion | 2.29.0 |
| Faint-quasar candidate | 22 ≤ LS r < 24, not labelled QSO, `p_qso` ≥ 0.1: `secondary_class = QSO` with reason `FAINT_QSO_CANDIDATE`; the primary label is untouched; shown grey as "QSO?" in the app. A lead, not a classification (section 8) | 2.58.0 |
| Archive warning | failed collectors and what is lost are written to `catalog_coverage.json`, the app banner and the `run_archives_status` / `run_archives_missing` columns of every row; only `complete` is a complete run, so a CSV passed on without the app still says it was degraded | 2.36.0, 2.57.0 |
| High-confidence flag | `high_confidence` with its reason: confirmed by a spectrum or an estimated real-sky purity of at least 98 %. Objects with the faint-quasar flag get no photometric high confidence (spectroscopic stays) | 2.36.0, 2.59.0 |

`objects_summary.csv` is the file to read first (one row per independent object detected by a survey; large-galaxy pieces and NED/SIMBAD-only entries are kept out of it). `classified_objects.csv` is the full record.

## 6. Sub-classification and independent axes

Sub-classes are decided per primary class, each with a stated basis and the precision of its rule measured on independent truth where such truth exists. Five independent axes (physical state, variability, compact objects, extragalactic, phenomena) are judged separately and each says UNKNOWN when it has no basis.

| Mostly look-ups (`CATALOG`, `EXTERNAL_CLASSIFIER`) | Inferred here (`INFERRED`) |
|---|---|
| SIMBAD MK spectral types and LAMOST / SDSS templates; ATNF pulsars; Roma-BZCAT blazars; HASH and Acker planetary nebulae; supernova lists; Suh 2021 AGB stars; Gaia SOS (RR Lyrae, Cepheids) and Gaia variability classes; ZTF periodic variables; Galaxy Zoo DESI morphology | photometric spectral type (Gaia BP-RP and temperature on the Pecaut and Mamajek sequence); luminosity class from parallax; AGB chemistry (carbon or oxygen) from a photometric model; white-dwarf, hot-subdwarf and red-giant gates from the Gaia HR-diagram position; galaxy activity from WISE W1-W2 and W2-W3, GALEX NUV-r and emission-line ratios (WHAN, BPT) from the spectra; light-profile type; AGN and QSO tags |

| Measured on independent truth | Result | Note |
|---|---|---|
| Mira / Cepheid / RR Lyrae / long-period variables | 94.8 / 93.2 / 82.4 / 63.6 % | random independent truth, 250 per class (ALGORITHM section 7) |
| Planetary nebulae | 89.2 % | same cross-validation |
| AGB chemistry (carbon / oxygen) | 95.8 % | photometric model |
| Red giant branch / AGB, sequence match | 51.7 / 42.4 % | the two cannot be separated without asteroseismology, so they are merged into `RED_GIANT` in the physical-state axis |
| Pulsars | 0.4 % (cross-validation), 21.6 % recall (separate benchmark) | the truth set has almost no TGSS-NVSS pairs; pulsar tags are mostly ATNF look-ups |
| 520 literature-confirmed objects, 52 types, 10 each (2.47.0) | blind: coarse class 89.5 %, sub-type 45.8 %; full: 87.9 % / 55.0 % | blind = spectra and literature lists removed from the evidence. Fixes were made after seeing failures on these objects, so they are cases, not statistics |

**X-ray rules that were tested and not adopted (2.56.0).** (1) The Rodriguez et al. 2024 F_X/F_opt line recovers 101/135 = 75 % of accreting binaries but calls 9/126 = 7.1 % of SDSS spectroscopic stars accretors; applied to the 4XMM × Gaia galaxy sample the precision ceiling is about 0.80. (2) The Lin et al. 2012 F_X/F_IR star rule keeps 162/209 = 78 % of spectroscopic stars but calls 22–32 % of X-ray binaries stars. Neither was added.

## 7. Performance of the coarse classifier

Accuracy counts an abstention as wrong. Intervals are 95 % intervals from a bootstrap over regions (or sky cells), not over objects. Each row names its sample, because the samples differ a lot.

| Test | Version | Result | Sample and caveat |
|---|---|---|---|
| **Locked test set C** (60 regions, 12′ radius, list locked by SHA-256, scored once per release, aggregate only) | 2.52.0 | **99.65 %** (99.40–99.86), 3,170 objects | Regions never used in development. About 95 % of the truth are stars (always answering STAR scores 95.24 %), about 144 galaxies and 7 QSOs: **little information on galaxies and QSOs**. On the 97.8 % of objects that have a Gaia DSC class, DSC alone scores 99.52 % and the pipeline 99.81 %. Not scored again since 2.52.0 (2.55.0 changed the coarse path for sources without an r detection). |
| **Sky-spread SDSS spectroscopic benchmark** (768 equal-area sky cells) | 2.51.3 | **93.79 %** (93.24–94.30), 9,999 objects | All objects unseen in training; 3,333 per class, so the class mix is artificial; SDSS spectroscopic targets only. Recall STAR / GALAXY / QSO 98.7 / 98.5 / 84.1 %. **r > 21: 87.99 %** (QSO recall 71.6 %, star precision 69.9 %). \|b\| < 20°: 96.09 % but only 32 galaxies and 49 QSOs. Labels unchanged by 2.52.0. |
| **COSMOS deep fields**, HST/ACS truth (galaxy morphology plus SED, Weaver et al. 2022) | 2.51.0 | 94.31 % against 91.09 % for always answering GALAXY, 28,194 objects | Nine fields, faint objects (hard end); no QSOs in this truth; truth exists only where HST/ACS covers the field. Before the 2.52.0 prior layer. |
| COSMOS test fields after the prior layer | 2.52.0 | **96.36 %** (was 94.48 %), ECE 0.37 % (was 1.52 %), 12,245 objects | Prior counted on separate calibration fields (split rule fixed before the results). Cost: COSMOS r > 23 star recall 81 to 65 %, precision 47 to 64 % (stars are about 5 % there). |
| COSMOS, **17 new fields**, confirmation only (nothing tuned on them) | 2.60.1 code | 96.68 % and 96.75 % (two halves, 16,057 and 16,757 objects), ECE 0.37 and 0.33 % | Odd / even field split by field number. The always-GALAXY baseline was not recomputed for these fields (91.09 % for the first nine). |
| Independent blind fields, sets A and B (200 regions each, 3.5° apart) | 2.46.0 | 99.30 % and 99.33 % (24,663 objects together) | **Development sets**: about 15 releases were built while looking at them (set B was scored once unseen, 98.6 % at 2.40.2). Blind = spectroscopic and literature lists removed from the evidence. |
| Old SDSS / DESI spectroscopic benchmarks, test split | 2.52.0 | 97.99 % (n = 1,991) / 90.33 % (n = 962) | **Not representative:** class-balanced, concentrated in 142 SDSS plates (7 for galaxies), about 4 points higher than the sky-spread benchmark. Kept for the fusion-training lineage. |

- **Bright sky:** stable. The locked set shows 99.6 % on a sample that is mostly stars, only slightly above Gaia DSC alone (99.5 % on the same objects), so it says little about galaxies and QSOs.
- **Faint end (r > 21) and QSOs are weak,** see section 8.
- **Probabilities** are calibrated where they were measured (high-latitude COSMOS and set B regions, ECE 0.37 %, `coarse_probability_calibrated = True` since 2.52.0); not for faint QSO probabilities and not for dense low-latitude fields at r > 20, where there is no truth.

## 8. Limits at the faint end

- **r > 22 high-confidence GALAXY is little more than the base rate.** The flag requires an estimated real-sky purity of at least 98 % (threshold 0.6 at r > 22) and it holds: purity 0.983 (84 % lower bound 0.982) on the 17 new COSMOS fields (24,169 flagged objects), 0.982 on the first nine. But faint objects are mostly galaxies anyway (stars are 5 % of the COSMOS2020 truth at r > 23 and 4 % at r = 24), so the flag adds only a few points over the base rate: it says the label is as reliable as the prior, not that this object was individually identified.
- **Faint stars are uncertain.** COSMOS r > 23: star recall 65 %, precision 64 % (2.52.0); SDSS sky benchmark r > 21: star precision 69.9 %. The faint-star truth sample is small, so some magnitude bins cannot prove a high-confidence star label.
- **Type-1 AGN recall by magnitude.** The QSO label recovers 96 % of X-ray-selected (Chandra COSMOS Legacy) type-1 AGN at r < 21, 76 % at 21–22, 19 % at 22–23 and 6–7 % at 23–24 (nine fields, 2.56.0 and its reproduction in 2.58.0); 20 % over 22–24 on the 21 fields not used to choose the candidate threshold. Galaxies outnumber quasars by hundreds to one there, so the posterior rarely exceeds 0.5.
- **The "QSO?" candidate flag** (threshold 0.1, chosen on five calibration fields), measured on the 21 deep COSMOS fields not used to choose it: **purity 29/119 = 24 % (Wilson 18–33 %)**, **recall 47/97 = 48 % (39–58 %)**. Purity counts only candidates that lie where HST/ACS covers the field (the nearest COSMOS2020 row within 1.0″ has F814W photometry), because the COSMOS2020 star and galaxy classes exist only there (without this the new fields read 0.357). The truth is X-ray selected, so purity is a lower bound; nine candidates inside the ACS area have no COSMOS2020 row, and counting them all as false would give 29/128 = 23 %. Three of four candidates are something else. It is a lead that needs a spectrum or X-ray / variability data.
- **`p_qso` is under-confident at 22 ≤ r < 24.** In deep COSMOS the observed type-1 fraction is above the mean `p_qso` in every probability bin (0.05–0.1: 0.15 against 0.07; 0.1–0.2: 0.20 against 0.14; 0.3–0.5: 0.57 against 0.38). The 2.52.0 calibration (ECE 0.37 %) does not cover these probabilities.
- **Known inconsistency of the r > 22 QSO prior.** The prior for QSO at r > 22 (`PI_QSO` = 0.0011) is not the real-sky fraction: its numerator is the literature density of one magnitude bin (22 to 23) and its denominator all objects from r = 22 on, so it is 3–7 times lower than the fractions measured in deep COSMOS (0.51–0.81 % at 22–23, 0.23–0.33 % at 23–24). Two corrected variants broke COSMOS2020 labels without fixing any and worsened ECE and NLL, so the prior was not changed; the faint quasar is treated as a candidate flag instead.
- **Quasars are not recovered at r ≥ 24:** none of 33 X-ray-selected type-1 AGN there received the QSO label (deep COSMOS, 2.56.0), and the candidate flag is applied only at 22 ≤ r < 24 because no truth measures its purity fainter. Stars and galaxies at r ≥ 24 are still labelled.
- **Many faint objects have only a literature type:** in the COSMOS 2′ field 2,361 of 3,621 objects carry only a NED or SIMBAD type, shown without a probability (2.54.0).

## 9. How it is validated

- **Blind independent fields.** Truth comes from spectroscopic surveys that were not used for training (LAMOST, 2QZ/6QZ, 2SLAQ, 2dFGRS, 6dFGS, WiggleZ, RAVE, APOGEE, Gaia-ESO and others); in the blind run the spectroscopic and literature catalogues are removed from the evidence, so the truth cannot leak. Sets A and B are now development sets.
- **Locked test set C.** 60 regions at least 3.5° from sets A, B and COSMOS; the list is locked by SHA-256 and the workflow refuses to run if it changes. It is scored **once per release, aggregate only**, with no tuning on its number, and not at all when a core archive failed in more than 10 % of the regions.
- **Sky-cell split benchmark.** SDSS spectra spread over 768 equal-area cells, split into train, calibration and test by cell, objects used for tuning removed.
- **COSMOS deep fields** with HST/ACS truth and Chandra COSMOS Legacy AGN. Odd-numbered fields calibrate, even-numbered test (rule fixed before results); the 17 added fields are confirmation only (list locked by SHA-256).
- **Statistics.** Bootstrap over fields or cells for the intervals, Wilson intervals for proportions, exact McNemar test for paired changes, balanced accuracy, ECE and NLL for probabilities.
- **Baselines always reported:** the majority class, Gaia DSC alone, a single gradient-boosted classifier. (The single classifier won on the spectroscopic benchmarks in all 14 cases and on the sky-spread SDSS targets, but lost on real-sky COSMOS by 2.6 points, p below 1e-80, so it is not the default: success on spectroscopic targets does not carry over to the real sky.)
- **Archive-health gate.** Scoring stops when the key archives are down, so the single look at a release is not spent on a degraded run.

## 10. Operation: speed, archives and failures

### Time and requests, first search of a new field (cold cache)

Measured on 2026-11-24 for three fields (NGC 4522 2′, COSMOS 2′, Galactic plane 1′) with the cache switched off and an empty VizieR cache; every request waits 3–5 s first (project rule), so run time is set mainly by the number of requests.

| Code | End to end | Collection (mean) | Archive requests |
|---|---|---|---|
| 2.60.2 | 128–235 s (6 runs) | 124–231 s (173 s) | 71–87 (mean 80.5) |
| 2.60.1, before the request reduction | 160–304 s (9 runs) | 154–274 s (227 s) | 82–113 (mean 93.7) |

- Classification adds 4–39 s depending on the number of objects (about 38 s for the roughly 3,600 objects of the COSMOS field).
- The spread between repeats of the same code (154–274 s) comes from VizieR mirrors that were unstable that day (see the dated notes below); the 24 % faster mean is a direction, not a precise figure.
- Searching the same field again uses the local cache (11–46 s end to end, measured at 2.54.0). Later searches in one session need 48–51 requests and none goes to a mirror known to be dead.

### Dependence on external archives and what happens when one fails

The program is only as available as the archives it queries; results change with archive state, and a degraded run is marked rather than hidden. Fallback routes:

| Archive | Fallback |
|---|---|
| VizieR (CDS) | official mirrors in order; empty answers are confirmed, database-error answers are asked again, mirrors that lack a catalogue move to the back for 24 h; dead mirrors are remembered across searches |
| SIMBAD | one direct TAP query for cone and types (and one for references); Harvard mirror if Strasbourg fails; astroquery path if SIMBAD rejects the query |
| Gaia (ESA) | if the archive returns its maintenance page, the VizieR copy is used at once; columns the copy lacks are named in the warning and in `run_archives_missing` |
| Pan-STARRS1 (MAST) | VizieR DR2 copy (objects with two detections are missing) |
| Legacy Surveys (Data Lab) | viewer catalogue (`cat.fits`) is asked as well when Data Lab is slow (30 s) or fails, and the first answer is used; only for DR10 South within 10′ (DR9 North values differ, so it is not used there) |
| ATNF pulsars (HEASARC) | VizieR copy after 30 s |
| Any non-key collector | a failure is remembered for 10 minutes for that cone so it is not waited for again |

- **Marking a degraded run:** warning band in the app, `catalog_coverage.json`, and `run_archives_status` / `run_archives_missing` on every result row. Only `complete` is a complete run.
- **Asking again:** `python v2/pipeline.py --work DIR --retry-failed` asks only the key archives that failed in the last search (`all`: every failed one) and classifies again; the app has an "Ask failed archives again" button.
- **Footprints:** archives that do not cover the field are not asked (NVSS, VLASS south of −40°, TGSS south of −53°, eRASS1-DE outside its half of the sky, LoTSS DR2 south of +16°, FIRST outside its two areas, DESI outside its tile list, MYStIX outside its 20 regions).
- **Bulk use is limited:** about 2–4 minutes per field (128–235 s end to end for the 1–2′ test fields in the table above) and dependent on external services.

### Dated notes (not permanent facts)

- **2026-11-11:** VizieR answered 404 and NOIRLab 502 for hours; every field run of that day lost AllWISE / 2MASS or Legacy Surveys. This is why the locked-set scoring has an archive-health gate.
- **From 2026-11-15:** CDS Strasbourg (SIMBAD and the main VizieR server) returned 404 or timed out after a CDS security incident. The mirror and fallback routes above were built or tightened in response, and the 2026-11-24 timings were measured in this state.
- **2026-11-25 to 12-02 (announced):** the Gaia ESA archive is down for the Gaia DR4 release; Gaia data then come from the VizieR copy, which lacks some columns. DR4 is expected to need re-validation of every Gaia-dependent rule.

## 11. What is not claimed

- **No novelty over Gaia DSC on the bright sky.** On the locked set the pipeline reaches 99.8 % where Gaia DSC alone reaches 99.5 % on the same objects. No independent scientific result is claimed yet; the contribution is the integration, the provenance, the validation design and the measured limits.
- **No calibrated QSO probabilities at the faint end** (22 ≤ r < 24 is under-confident; at r ≥ 24 quasars are not recovered, 0 of 33 type-1 AGN, and no truth measures the candidate flag there).
- **Not a bulk-processing tool**, and not a replacement for a spectrum: sub-classes are mostly look-ups of other people's catalogues, and the pipeline's own sub-type recovery without spectra or literature lists is 45.8 % on the 520-object check (2.47.0).
- **Not validated** for dense low-latitude fields at r > 20 (no truth there).
- **Development-set numbers** (sets A and B, the 520 objects, COSMOS fields used for calibration) are not unbiased; the unbiased ones are the locked set C and the COSMOS confirmation fields.

## 12. Running it

**Desktop app (no Python needed).** Download the zip for your system from the [release page](https://github.com/Pinchpeach/Finding_objects/releases/tag/v2.60.2) (or [all releases](https://github.com/Pinchpeach/Finding_objects/releases)), unpack it and run `FindingObjects` (`FindingObjects.exe` on Windows). Search by object name or coordinates plus a radius, or double-click the map. The app has a sortable and filterable result table, an object panel with probabilities, evidence, sub-classes and links, a sky map (high-confidence objects have a gold ring), the archive warning band, bookmarks (Ctrl+D, Ctrl+B) and a log (Ctrl+L). Builds are tested offline on all three systems for every release.

**From source:**

```bash
pip install -r v2/app/requirements.txt
python v2/app/qt_app.py
```

**Command line:**

```bash
# collect around a position and classify (needs archive access)
python v2/pipeline.py --ra 188.4155 --dec 9.1751 --radius 0.5 --work runs/ngc4522

# classify catalogue files that were collected before
python v2/pipeline.py --raw-dir v2/rawdata --work runs/ngc4522

# after a run that lost an archive: ask only the failed key archives again
# (add 'all' to ask every failed archive)
python v2/pipeline.py --work runs/ngc4522 --retry-failed
```

`--radius` is in arcminutes. Start with `objects_summary.csv` in the `--work` directory; `classified_objects.csv` is the full record and `pipeline_summary.csv` has the time of each stage.

## 13. Code layout and development

| Location | Role |
|---|---|
| `v2/Get_data/` | the 30 collectors, parallel execution and time limits (`controller.py`), cache, request pause and mirrors (`throttle.py`), footprints (`footprint.py`) |
| `v2/Preprocess/` | stages 1–5 (association, integration, features, evidence, coarse class), rule table, fusion weights, literature notes |
| `v2/Classifier/` | sub-classification (`subclass.py`), the five axes, per-axis calibration, high-confidence table |
| `v2/*.py` | `pipeline.py` and the post-processing modules |
| `v2/app/` | PySide6 app and PyInstaller packaging |
| `v2/benchmark/` | truth sets, preserved catalogue features, evaluation, training, independent-validation and purity scripts |
| `.github/workflows/` | data collection and validation (manual runs), app build and release |
| `v2/document/` | this overview (`overview_content.py`, `build_overview.py`), the paper list, older decks |

- **Literature first:** a rule or threshold is changed only after its basis is recorded (code comment or `LITERATURE*.md`; classified paper list: [`v2/document/PAPERS.md`](v2/document/PAPERS.md)).
- **Adoption rule:** a change without a significant gain on benchmarks and independent truth is not adopted (GALEX UV, the u band and PS1 variability were measured and rejected).
- **Versions:** every merge raises `v2/VERSION` and adds a row with changes, reasons and measurements to `v2/CHANGELOG.md`; work reports (`v2/WORK_REPORT_*.md`) record the design reasons and the alternatives dropped.
- **Tests:** 307 pytest tests at 2.60.2 (preprocessing, classifier and app; the app tests need PySide6). Benchmarks reproduce offline from the preserved catalogue features. Anything that needs the archives runs as a GitHub Actions workflow and returns its results as a commit.

```bash
# tests
cd v2 && python -m pytest -q Preprocess/tests Classifier/tests app/tests

# code style (pyproject.toml)
black v2

# rebuild README.md and the overview PDF from overview_content.py
python v2/document/build_overview.py
```

## 14. Licence and third-party data

- Code: MIT licence, see [`LICENSE`](LICENSE).
- **No catalogue data are bundled.** The program queries the archives when it runs. The repository holds only small derived files (for example the DESI DR1 tile centres used to skip the DESI archives, prior tables counted from COSMOS2020, fusion weights) and, for the benchmarks, preserved feature files. An optional feature (off by default, `V2_LOCAL_LISTS=all`) lets the user's own computer download two small fixed VizieR tables once, on first use, and keep them in the user's cache folder to save requests; nothing is shipped or passed on, and it stays off until the terms of use of those tables have been read in the original text.
- Third-party components of the app (Qt / PySide6 under LGPLv3, Python, NumPy, pandas, Astropy, astroquery, PyVO, Requests, PyInstaller) and the terms of the data services are listed in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) (in Korean).
- When you publish results, follow the citation and acknowledgement requirements of each survey you used.

## 15. Other documents

| Document | Language | Content |
|---|---|---|
| [`v2/ALGORITHM.md`](v2/ALGORITHM.md) | Korean | the classification algorithm in detail, stage by stage |
| [`v2/CHANGELOG.md`](v2/CHANGELOG.md) | Korean | changes, reasons and measurements per version |
| [`v2/STATUS_2026-11-12.md`](v2/STATUS_2026-11-12.md) | Korean | state of the classifier after the first locked-set scoring, and the directions drawn from it |
| [`v2/benchmark/LOCKED_TEST_SET_C.md`](v2/benchmark/LOCKED_TEST_SET_C.md) | English | protocol and scores of the locked test set |
| `v2/WORK_REPORT_*.md` | Korean | work reports: results, errors and the design reasons and dropped alternatives |
| `v2/Preprocess/LITERATURE.md`, `v2/Classifier/LITERATURE_*.md` | English | the literature basis of the rules and thresholds |
| `v2/LITERATURE*.md` | Korean (citations in English; `LITERATURE_REVIEW_2026-10.md` mostly English) | literature surveys behind later changes (dated) |
| [`v2/document/OVERVIEW_v2.36.1.pdf`](v2/document/OVERVIEW_v2.36.1.pdf) | Korean | the previous overview (version 2.36.1, 2026-10-23); its figures are out of date |
| [`v2/document/PIPELINE_STACK_v2.44.0.pdf`](v2/document/PIPELINE_STACK_v2.44.0.pdf) ([PPTX](v2/document/PIPELINE_STACK_v2.44.0.pptx)) | English | **the v2.44.0 deck**, 12 slides on the pipeline and tech stack; **not updated since version 2.44.0**, so its headline figures (29 archives, 36 + 2 rules and models, 99.16 % blind accuracy, 141 tests) are out of date |

## Where the numbers come from

Paths are relative to the repository root. All figures were read from these files at version 2.60.2.

| Figure | File |
|---|---|
| 30 collectors; 35 evidence rules; 29 summary columns; 307 tests | `v2/Get_data/controller.py` (COLLECTORS); `v2/Preprocess/classification_rules.csv`; `v2/summary.py`; `pytest` run of 2.60.2 |
| 833 / 1,649 / 2,513 columns of `classified_objects.csv` | `v2/WORK_REPORT_2026-11-24.md` section 13 |
| Locked set C (99.65 %, baselines, composition) | `v2/benchmark/LOCKED_TEST_SET_C.md` |
| Sky-spread SDSS benchmark; ablation by wavelength; COSMOS 94.31 % and the single-classifier result | `v2/STATUS_2026-11-12.md` sections 2.2 and 2.3; `v2/WORK_REPORT_2026-11-11.md` |
| Prior layer, COSMOS after 2.52.0, star recall cost | `v2/WORK_REPORT_2026-11-13.md` section 4; `v2/CHANGELOG.md` row 2.52.0; `v2/ALGORITHM.md` section 5 |
| COSMOS 17 new fields, candidate flag purity and recall, ACS definition | `v2/WORK_REPORT_2026-11-24.md` sections 3, 6 and 15.1; `v2/benchmark/deep_cosmos_confirmation/` (`groups_base.csv`, `variants/accuracy_ece.csv`); `v2/benchmark/DEEP_COSMOS_EXPANSION.md` section 6.1 |
| High-confidence purity at r > 22 | `v2/WORK_REPORT_2026-11-24.md` section 5; `v2/WORK_REPORT_2026-11-13.md` section 5 |
| `p_qso` under-confidence; QSO prior inconsistency; type-1 recall by magnitude | `v2/ALGORITHM.md` sections 5 and 10; `v2/WORK_REPORT_2026-11-23c.md` |
| Sets A and B (99.30 / 99.33 %) | `v2/WORK_REPORT_2026-11-07.md` |
| Old SDSS / DESI benchmarks | `v2/ALGORITHM.md` section 5 (table of measured values) |
| 520 reference objects | `v2/reference_objects/validation/REFERENCE_VALIDATION_2026-11-07.md` (2.47.0 section) |
| Sub-class accuracies | `v2/ALGORITHM.md` sections 6 and 7; `v2/CHANGELOG.md` rows 2.22.0 and 2.18.0 |
| X-ray rules not adopted | `v2/WORK_REPORT_2026-11-23.md` sections 9 and 10; `v2/CHANGELOG.md` row 2.56.0 |
| Time and requests; mirror behaviour | `v2/WORK_REPORT_2026-11-24.md` sections 10–15; `v2/benchmark/request_reduction_2_60_2/pipeline_runs.csv`; `v2/WORK_REPORT_2026-11-15.md` (2.54.0 repeat timings) |
| Fallback routes, footprints | `v2/ALGORITHM.md` section 1; `v2/CHANGELOG.md` rows 2.54.0–2.60.2 |
| Dated archive notes | `v2/benchmark/LOCKED_TEST_SET_C.md` rule 4; `v2/ALGORITHM.md` section 1; `.github/workflows/v2_deep_cosmos.yml` |
| Release page and zips | [https://github.com/Pinchpeach/Finding_objects/releases/tag/v2.60.2](https://github.com/Pinchpeach/Finding_objects/releases/tag/v2.60.2) |

---

*This README and the overview PDF are generated from `v2/document/overview_content.py` by `v2/document/build_overview.py`. Edit that file, not this one.*
