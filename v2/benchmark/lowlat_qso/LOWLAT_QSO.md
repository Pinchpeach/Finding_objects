# Low-latitude quasar recall (2.61.2, measurement only)

**Question.** The locked set C scored on 2026-11-25 had a low-latitude pool (`cpln`, 11 regions, 879 truth objects) that
was all stars, so nothing measures what the classifier does with a galaxy or a quasar behind the Galactic plane.  This
measures the recall of the `QSO` label on spectroscopically confirmed quasars at |b| <= 20 deg.  **Nothing in the
classifier was changed or tuned.**

## 1. Samples (read from the papers and the public tables, not from memory)

| | Huo et al. 2025 | Fu et al. 2022 |
|---|---|---|
| paper | arXiv:2502.05480, "Finding Quasars Behind the Galactic Plane: Spectroscopic Identifications of ~1300 New Quasars at \|b\|<=20 degree from LAMOST DR10" | arXiv:2206.05704, ApJS 261, 32, "Finding Quasars behind the Galactic Plane. II. Spectroscopic Identifications of 204 Quasars at \|b\|<20 deg" |
| table | NADC PaperData doi:10.12149/101489 (`GPQs_LAMOST_DR10.fits.gz`, 1,982 quasars, 39 columns) | VizieR J/ApJS/261/32 (`gpqcat` 204 quasars; `tablec1` 17 stars + 2 galaxies); tables also at doi:10.12149/101095 |
| spectra | LAMOST DR10 | Xinglong 2.16 m, Lijiang 2.4 m, Palomar 200 inch, MDM 1.3 m, ANU 2.3 m |
| selection | candidates from Pan-STARRS1 + AllWISE: PS1 variability (Hernitschek et al. 2016, pQSO >= 0.2, i < 20) and the XGBoost transfer-learning list of Fu et al. 2021 (PS1 + AllWISE colours, Gaia proper-motion cut), i_P1 <= 19.5 for the later lists | the Fu et al. 2021 candidate catalogue (PS1 + AllWISE colours, transfer learning, Gaia proper-motion cut) |
| success rate | 1,949 QSO of 2,454 observed candidates = 79 % (success rate ~80 % at 10 < \|b\| < 20 and E(B-V) < 0.3, "very low" at \|b\| < 5 and E(B-V) > 0.6) | 243 observed: 204 QSO, 17 star, 2 galaxy, 20 unknown; purity lower limit 85.2 % (196 of 230) |
| useful columns | RA, DEC, Z_VI, PS1 g r i z, E(B-V) (Planck), NOTE (N new / K known) | name, GLON, GLAT, imag, z, class |

16 quasars are in both tables.  The compact table (`lowlat_truth.csv.gz`: sample, name, position, l, b, z, PS1 i, E(B-V),
class) is built by `build_lowlat_truth.py`; the SHA-256 of the two source files are printed there (Huo `8001d5f9...`, Fu
`da586d54...`).

**Why the recall is an upper bound.**  Both samples were chosen from PS1 + AllWISE photometry, the same kind of data our rules
and fused evidence use (`PS1-CKNN-001`, the AllWISE R90 rule, ...): a quasar the selection missed is not in the sample, and
the colours of the sample quasars are by construction those the selection liked.  The samples are bright (PS1 i median 18.8
Huo, 17.7 Fu; 99 % brighter than 20), and Huo/LAMOST covers Dec >= -10 and l = 0-240 deg.  So the numbers below are a
recall *of an easy subset*, not a completeness.

## 2. Design (fixed before anything was collected)

1. **Regions** (`select_fields_lowlat.py`, list `fields_lowlat.csv`, **SHA-256 `8b0f52e28ea3819fd6a9ea97ab922c305acd2a404c5dcc8df9981337a7e4d0d7`**,
   also the lock of `.github/workflows/v2_lowlat_qso.yml`): 150 quasars drawn from the unique quasars of the two samples in four
   strata of |b| (< 5: all 20; 5-10: 50; 10-15: 40; 15-20: 40), inside a stratum round-robin over cells (sample x l bin x E(B-V)
   bin) in the order of sha1(salt + name); no two cones closer than 6'.  Plus the 19 Fu stars and galaxies.  169 regions.
2. **Cone** radius 3'.  Every quasar of the truth table inside a cone is scored (in this draw every cone held exactly the one it was
   centred on).
3. **Blind**: `V2_SKIP_COLLECTORS=blind` (no spectroscopic or literature catalogue, in particular not LAMOST), then the same
   raw-file filter as the other blind runs.
4. **Score** (`score_lowlat_qso.py`): the counterpart of a quasar is the object with the most catalogues within 2'' (a grouped
   object is answered by its parent); recall = objects labelled `primary_class == QSO` / quasars with an object, Wilson 95 %
   interval; by |b|, E(B-V) (Planck from the Huo table, else the pipeline's SFD `std_ebv`; unknown for 33 of 150), PS1 i, redshift,
   sample, presence of a Legacy Surveys / AllWISE row, AllWISE R90 sky.
5. **Why a miss happened** (replayed from the stored prior factors of Stage 5, `class_prior.py`): rule-decided; abstained; the fused
   evidence alone (`p_*_training_prior`) does not say QSO; or it says QSO and the position factor (the local Gaia density where it
   can be measured, else latitude x Magellanic Clouds), the QSO magnitude prior or the veto turns it.  And what the label would be
   without a prior (`counterfactual_recall.csv`).
6. **False-positive scale**: the objects labelled QSO in the cones that are not a sample quasar, per square degree, against the
   expected quasar density.  There is no non-quasar truth at low latitude beyond the 19 Fu objects, so the purity cannot be measured.

## 3. Result (2.61.0 classifier, Gaia from the VizieR DR3 copy)

Run in the session's own container on 2026-11-27 (live archives, 169 regions, `results_2026-11-27/`); the workflow
`v2_lowlat_qso.yml` repeats it (manual) and should be run again when the ESA Gaia archive is back (2026-12-02).  Collection: 169/169
regions classified; the Legacy Surveys archive timed out in 4 regions and was asked again once (it answered with 0 rows there, probably outside
its footprint); Gaia came from the VizieR I/355 copy in all 169 regions, without its variability flags, G/BP/RP fluxes and
`rv_nb_transits`.

| QSO recall (86 of 150; 95 % Wilson) | |
|---|---|
| all | **57 % (49-65 %)** |
| \|b\| 0-5 / 5-10 / 10-15 / 15-20 deg | **10 % (2/20)** / 46 % (23/50) / 78 % (31/40) / 75 % (30/40) |
| E(B-V) < 0.1 / 0.1-0.2 / 0.2-0.3 / >= 0.3 | 96 % (25/26) / 64 % (23/36) / 73 % (19/26) / **21 % (6/29)** |
| PS1 i < 17.5 / 17.5-18.5 / 18.5-19 / 19-19.5 | 57 % / 51 % / 70 % / 58 % |
| z < 1 / 1-2 / 2-3 / >= 3 | 67 % / 55 % / 35 % / 20 % (1/5) |
| sample Huo / Fu | 60 % / 51 % |
| AllWISE R90 rule fired (60) / not (90) | 87 % (52/60) / 38 % (34/90) |

Labels of the 150 quasars: 86 QSO, 57 STAR, 5 GALAXY, 2 UNKNOWN; every quasar had an object.  The 19 known non-quasars: none was
labelled QSO (17 stars: 16 STAR and 1 GALAXY; 2 galaxies: 1 GALAXY, 1 STAR).

**Why the 64 misses** (all with an object): the fused evidence alone says STAR for 14; the position factor turns 21 (all by the
local Gaia density), the QSO magnitude prior 26 (22 to STAR, 4 to GALAXY), the veto 1; 2 abstained (CONFLICT, the evidence alone
said QSO).  Without a prior the label of an evidence-decided object would be QSO for **134 of 150 (89 %)**: 71 % without the
position factor, 75 % without the QSO magnitude prior, 89 % without either (|b| < 5: 10 % -> 55 %; 5-10: 46 % -> 92 %).  This is
what the priors *cost in recall*; what removing them would cost in false QSO labels is not measured here (below).

**False-positive scale.**  In the 150 cones (1.18 deg^2), 170 objects other than the sample quasars were labelled QSO (144 +- 11
deg^-2; 197 +- 25 at 10-15 deg, 293 +- 31 at 15-20 deg), 23 of them with PS1 i < 19.5 (19.5 +- 4.1 deg^-2).  The quasar surface
density at i < 19 to 19.3 is about 5-8 deg^-2 at high latitude (Richards et al. 2006, Table 2: N(<i) = 5.3 at i = 18.98, 7.9 at
i = 19.2; 0.3 < z < 2.2) and the known low-latitude quasars are < 1 deg^-2 (Huo et al. 2025, Sec. V.1), so most of these 23
labels are false: at least 60-70 % even if every real quasar of that depth were labelled QSO, and more with extinction.  The
all-depth 144 deg^-2 is not by itself a sign of false labels (the high-latitude density to r < 23 is ~300 deg^-2); split by
depth it is (Section 6, item 1).  100 of the 170
objects have no PS1 magnitude and 77 are single-survey rows (48 Legacy Surveys-only, 28 AllWISE-only): the QSO label rests on one survey.  The priors that cost recall at low latitude exist because of this (`05_likelihood_vectors.py`: a field at
l = 182 deg, b = +2 deg had 616 "QSO" among G ~ 20 stars).

## 4. Limits

- One measurement, 150 quasars, bright (i < 20), selected from PS1 + AllWISE colours: an upper bound for the easy subset.
- |b| < 5 deg has 20 quasars (recall 10 %, interval 3-30 %); the Huo sample has only 13 there and LAMOST sees Dec >= -10 deg, l < 240 deg.
- E(B-V) is missing for 33 quasars (the Fu table has none and the pipeline's `std_ebv` needs a Legacy Surveys or GALEX row).
- Legacy Surveys DR10 has a row for only 14 of the 150 quasars (all 14 labelled QSO): the low-latitude northern sky is outside it, so
  the LS-based evidence that dominates the high-latitude benchmarks is absent for 91 % of these quasars.  Recall by presence of an LS
  row is confounded with latitude and sample.
- The prior-factor replay reproduces the stored `p_*` for every miss (`path_ok`); the confidence gates are not replayed in the
  counterfactual, so it is an upper bound on what dropping a prior would recover.
- Purity cannot be measured: 19 non-quasars.  The density comparison is a plausibility check with a literature density that is for
  high latitude, SDSS-selected quasars.
- Gaia is the VizieR copy (no variability flags): re-run when the ESA archive is back.
- **These 169 regions are now a development set** (Section 6, item 5): a prior or rule tuned on these numbers must be checked
  on a new draw locked before collection.

## 5. Reproduce

```
python build_lowlat_truth.py --out lowlat_truth.csv.gz            # downloads the two tables (NADC, VizieR)
python select_fields_lowlat.py --truth lowlat_truth.csv.gz --out fields_lowlat.csv
# per region (V2_SKIP_COLLECTORS=blind): python v2/pipeline.py --ra RA --dec DEC --radius 3 --work W
#   python score_lowlat_qso.py compact --work W --out ROOT/<name>   (+ the blind raw csv files under ROOT/<name>/raw)
python score_lowlat_qso.py score --root ROOT --regions fields_lowlat.csv --truth lowlat_truth.csv.gz --out results_DATE
```
or run the workflow `Low-latitude quasar recall (measurement)` (169 region jobs + score job, results committed to
`v2/benchmark/lowlat_qso/results_<VERSION>/` on a non-main branch).

## 6. Review before merge (2.61.2)

Checked against the committed tables (`results_2026-11-27/`) and the code; nothing in the measurement was re-run or changed.

1. **The false-QSO density depends on the depth of the region.**  The all-depth 144 +- 11 deg^-2 is below the high-latitude
   quasar density to r < 23 (Palanque-Delabrouille et al. 2016, Tables 5 and 7: 296-311 deg^-2; DESI selects > 200 deg^-2 at
   16.5 < r < 23, Chaussidon et al. 2023; `v2/LITERATURE_FAINT_QSO_2026-11-23.md`), so on its own it does not show false labels.
   Split by whether the region has Legacy Surveys DR10 data (the sample quasar has an LS row; r reaches ~23.5 there):

   | regions (quasar-centred) | area deg^2 | QSO labels other than the sample quasar | deg^-2 | median per region |
   |---|---|---|---|---|
   | inside LS DR10 (14) | 0.110 | 88 | **800 +- 85** | 3 (= 382 deg^-2) |
   | outside (136, PS1 + AllWISE depth) | 1.068 | 82 | 77 +- 9 | 0 |

   The 14 LS regions are at |b| = 13-20 deg with E(B-V) = 0.02-0.13, where extinction lowers the real count.  800 deg^-2 is
   2.6-2.7 times the total quasar density to r < 23 at high latitude, so **at least ~60 % of the QSO labels in LS regions are
   false** (still >= 50 % if the true density to r ~ 23.5 were 400 deg^-2, an extrapolation of the same luminosity function), even
   if every real quasar there were labelled QSO.  All 14 sample quasars in these regions were labelled QSO: there the priors do not
   cost recall and do not stop the false labels either.  Outside LS, 77 deg^-2 at PS1/AllWISE depth cannot be judged without a
   quasar density at the same depth (21 of the 82 have PS1 i < 19.5, the part covered by the 60-70 % statement above).
2. **Where the 77 single-survey QSO labels are** (`n_catalogs == 1` in `qso_other_objects.csv`, joined to the LS presence of the
   region): 49 in 11 of the 14 LS regions, **36 of them in three** (lq2_012 at l = 195, b = +13.8: 18; lq3_016 at l = 21, b = -16.8:
   10; lq3_036 at l = 50, b = -18.0: 8); 28 in 21 regions without LS (lq3_003: 4, lq3_006: 3, the rest 1-2).  By |b|: 0-5 deg 0,
   5-10 deg 3, 10-15 deg 28, 15-20 deg 46.  The LS-only labels are a few crowded LS regions, not a uniform rate.
3. **Why an AllWISE-only row can be labelled QSO** although WISE colours alone are not evidence (2.44.0).  2.44.0 made only the
   continuous features `WISE-COLOR-001` support-only (`SUPPORT_ONLY_RULES`, `05_likelihood_vectors.py`).  The two cut rules on
   AllWISE, `WISE-AGN-001` (Stern et al. 2012: W1 - W2 >= 0.8, W2 <= 15.05, S/N >= 10) and `WISE-AGN-R90-001` (Assef et al. 2018),
   emit EXTRAGALACTIC evidence, which the fusion spreads over GALAXY and QSO (`GROUPS`), and the support colours then tip it to
   QSO.  They are the only rules that read an AllWISE row (`classification_rules.csv`), so each of the 28 AllWISE-only labels (all
   170 labels have `classification_basis == evidence`, none comes from the sparse priors) had one of them.  R90 is gated by its sky (|b| > 10 deg, > 30 deg from the Galactic Centre) and by the near-infrared point-source
   test; **the Stern rule has no latitude gate** (`04_build_evidence.py`, `WISE-AGN-001` branch), although
   `LITERATURE_REVIEW_2026-10.md` (WISE-AGN-001 row) recommended down-weighting it at |b| < 10 deg because young stars, AGB stars
   and planetary nebulae also have W1 - W2 > 0.8 there.  Here 25 of the 28 single-survey labels outside LS regions are at |b| = 10-20
   deg, so a |b| < 10 deg gate alone would move at most 3: the open question is the single-survey row, not only the latitude.  Not changed (measurement only).
4. **Upper bound.**  Stated in Section 1 ("Why the recall is an upper bound": both samples were selected from PS1 + AllWISE
   colours, i < 20) and Section 4; the summary line of the CHANGELOG carries it too.
5. **Overlap with the locked set C and development-set status.**  The 169 centres against `v2/benchmark/fields_c.csv` (60 regions,
   radius 12'): the nearest pair is 0.52 deg (31') apart, more than 12' + 3', so no cone overlaps a set C region and set C stays
   unseen (one centre is within 1 deg of a set C region, 22 within 5 deg).  The 169 regions themselves are now **seen**: a position
   or QSO magnitude prior, a Stern latitude gate or a single-survey rule tuned on these numbers makes them a development set, and
   a claim about low-latitude QSO recall after such a change needs a new draw (quasars of the two samples not drawn here, or
   another spectroscopic sample) whose list is locked before collection, as this one was.
6. **Scorer fixes from the code review** (they do not change the committed results, where all 169 regions have a record and
   none is empty): a region without detections has the pipeline's empty-result schema (no `parent_object_id`, no `p_*`), which
   aborted the whole scoring; the compact record is now completed with the missing columns and its quasar scores as `NO_OBJECT`.
   A region without a record used to drop its quasars from every denominator silently; they are now `REGION_MISSING` in
   `per_truth.csv`, still in no denominator (they were not measured), counted in a `coverage` row of `recall_summary.csv` and in
   `coverage.json` (copied into the workflow's `run.json`), and the score log prints `INCOMPLETE` with the missing regions.  A run where no quasar has a counterpart (every region
   empty) no longer stops at the summary: the per-object columns are added as missing values before grouping.  A region classified without a key archive (Gaia, PS1,
   Legacy Surveys or AllWISE: a failed query or time-out, not an empty answer) is now reported: the pipeline's
   `run_archives_status` / `run_archives_missing` are kept in the compact record (for a region without rows the copied
   collection summary is read), `regions.csv` has them per region, and `coverage.json` counts those regions and their quasars
   (`degraded`; the score log prints `DEGRADED`).  A run where no region has a record writes its tables and coverage with the
   density marked unavailable (NaN) instead of stopping.  The 2026-11-27 run predates this: its records were compacted without those
   columns, and Section 3 states the collection outcome (Legacy Surveys timed out in 4 regions, asked again, answered with 0 rows).

## 7. Limiting the false QSO labels (2.61.3)

**What was done.**  (1) The 170 objects of the calibration regions that are labelled QSO but are not a sample quasar were taken apart
(`dissect_false_qso.py`, `results_2026-11-27b/dissection/`): 28 % rest on Legacy Surveys alone and 16 % on AllWISE alone (77 of 170 on
one catalogue), 22 % on AllWISE plus one other, 33 % on two or more surveys; one cone holds 30 of them and ten cones 56 %.  Of the 106
with W1, W2: 80 % have W1-W2 >= 0.8, 73 % lie in the Koenig & Leisawitz (2014) Class I/II colour region (so colours alone do not
separate them from young stellar objects), 95 % in their AGN colour-magnitude region.  All 33 with a Gaia row pass the Fu et al.
(2021, Sec. 5.3) proper-motion cut, none has parallax S/N > 3, and 20 of 33 have a Gaia DSC quasar probability above 0.5: the
astrometry removes nothing among them.  (2) The literature (`../../LITERATURE_LOWLAT_QSO_2026-11-27.md`) says: every quasar selection
uses two surveys or more; the Stern et al. (2012) reliability is for high latitude; Assef et al. (2018) R90 is defined only for
|b| > 10 deg and > 30 deg from the Galactic Centre; Gaia's own classification is 24 % pure over the sky.  (3) Switches in
`Preprocess/lowlat_qso.py` (`V2_LOWLAT_QSO`, off by default, act only at |b| < 20 deg) were tried on the 169 calibration regions;
(4) the survivors were scored once on 140 new regions drawn by the same rule from the pool that remains
(`fields_lowlat_confirm.csv`, SHA-256 `8638a9df...` written to `PREDICTIONS_CONFIRM.md` with the predictions and the adoption
criteria **before** the first of them was collected; collected blind from this session's container on 2026-11-27).

**Result** (`results_2026-11-27b/`; false = labelled QSO, not a sample quasar; density per deg^2 of the cones with a region-bootstrap
95 % interval; "removed" = the paired density of control labels the switch takes away):

| variant | set | sample quasars labelled QSO | false QSO density | with PS1 i < 19.5 | quasars lost | removed (paired) |
|---|---|---|---|---|---|---|
| base | calibration | 86 / 150 (57 %) | 144 [90-211] | 19.5 | - | - |
| base | confirmation | 95 / 143 (66 %; 5-10 deg 45 %, 10-15 78 %, 15-20 86 %) | 159 [90-242] | 11.8 | - | - |
| `surveys2` | calibration | 86 | 79 [53-109] | 13.6 | 0 | 65 [32-108] |
| `surveys2` | confirmation | 95 | 74 [45-108] | 8.2 | 0 | 85 [42-141] |
| `surveys3` | calibration | 86 | 36.5 [25-48] | 10.2 | 0 | 108 [61-170] |
| `surveys3` | confirmation | 95 | 31.8 [17-50] | 6.4 | 0 | 127 [66-203] |
| `wise_second` | calibration | 86 | 121 [68-188] | 14.4 | 0 | 24 [14-34] |
| `wise_second` | confirmation | 95 | 129 [64-208] | 8.2 | 0 | 30 [18-43] |
| `pm` | both | unchanged | unchanged | | 0 | 0 |
| `surveys2` + `wise_second` + `wise_footprint` | confirmation | 91 | 74 [45-108] | 8.2 | 4 | 85 [42-141] |

Predictions (`results_2026-11-27b/predictions.csv`): 19 of 20 held.  **Failed:** prediction 7 for `surveys3` (false labels with
PS1 i < 19.5 "stay above the high-latitude quasar density of 5-8 deg^-2, about 10"): observed 6.4 deg^-2 (7 objects, interval 1.8-11.8),
which is not distinguishable from that density.  Adoption criteria (`adoption.csv`; the default stays off): `surveys2`, `surveys3` and
`wise_second` are offered as options (paired removed-density interval above 0, 0 of 143 quasars lost, labels at |b| >= 20 deg
identical in 5 fields at |b| = 42-72 deg / 32,866 objects, `highlat_identity.csv`; a 6th, a 1' Galactic-plane field, is below the limit and has no QSO label either way); `pm` removes nothing (criterion a fails); `wise_footprint` loses sample
quasars (2 of 150, 4 of 143, all at 5-10 deg) and is not offered.  The 26 of 130,577 objects that differ between the collection-time
output and the offline re-run are cone-edge objects (SGA components, Gaia/AllWISE singletons), none labelled QSO.

**By depth** (`by_depth.py`, `results_2026-11-27b/*/by_ls_coverage.csv`; the review in Section 6 shows that the all-depth density is not by itself a sign
of false labels, because the high-latitude quasar density to r < 23 is ~300 deg^-2).  Cones with a Legacy Surveys DR10 object
(confirmation: 19 cones, 0.149 deg^2, 14 % of the area, 69 % of the base labels not on a sample quasar) against the others:

| confirmation set | cones | base | `surveys2` | `surveys3` | `wise_second` |
|---|---|---|---|---|---|
| with LS (deg^-2, objects) | 19 | 811 (121) | 335 (50) | 134 (20) | 737 (110) |
| without LS (PS1 + AllWISE depth) | 121 | 57 (54) | 33 (31) | 16 (15) | 34 (32) |

In the LS cones the base density is 2.7 times the total quasar density, so at least ~60 % of those labels are false (as in Section 6);
`surveys2` removes 59 % of them and leaves a density equal to the total quasar density, `surveys3` leaves less than that.
**`surveys2` alone therefore does not clear the LS depth**; the cones without LS have no quasar density to compare with at their depth.

**Limits.**  (a) Every sample quasar has at least 3 catalogues (the sample is selected through PS1, AllWISE and Gaia): 46 of the 181
quasars labelled QSO have exactly 3, none has 2, and all 9 sample quasars with 2 were already unlabelled; so "0 quasars lost" is a
statement about bright, well-observed quasars.  What `surveys2` / `surveys3` cost faint real quasars that have only two or three
catalogues cannot be measured here.  (b) There is no purity: "false" means "not a sample quasar", and the 140 / 169 cones have no
non-quasar truth beyond the 19 stars and galaxies of the calibration list (none of them was labelled QSO, base or variant; the confirmation draw has none).  (c) The recall is
an upper bound for the bright PS1 + AllWISE-selected sample; LAMOST-type stars in the truth are bright.  (d) Gaia comes from the
VizieR DR3 copy (no variability flags) until the ESA archive is back (2026-12-02).  (e) The switches change labels, so the locked
set C scoring applies if one is turned on: its low-latitude pool `cpln` has only spectroscopic stars as truth, so it can show at
most whether a star stops being labelled QSO, and it cannot show what the switches cost quasars or galaxies behind the plane.
(f) 5 of the 140 confirmation regions had SDSS SkyServer error pages that the collector retried successfully; one lost its VLASS
rows to a parse error (radio only; `confirmation/score_base/coverage.json`: 140 of 140 regions recorded, 0 without a key archive).

Reproduce: `ab_variants.py --variants base=ROOT ... --regions fields_lowlat_confirm.csv --truth lowlat_truth.csv.gz --out DIR`
(each variant's `ROOT` is the compact output of the offline re-classification of the saved raw files with `V2_LOWLAT_QSO=<switches>`),
then `adoption_check.py --calibration DIR1 --confirmation DIR2 --highlat-identical yes --out DIR3`; the identity at high latitude:
`highlat_identity.py --raw RAWDIR... --out DIR`.

### Review before merge (2.61.3)

Checked against the code, the committed tables and the git history; the measurement was not re-run.  Three code changes come out of it
(`Preprocess/lowlat_qso.py`, `05_likelihood_vectors.py`, `Classifier/unknown_reason.py`, tests 460 -> 463); with every switch off
nothing changes (no new column, the same labels).

1. **How surveys are counted.**  The switches counted distinct catalogue *names*.  Four pairs of names are one survey's products of the
   same measurement, and now count once (`SURVEY_OF`): Gaia DR3 + its SOS variability tables, ZTF light curves + ZTF periodic
   variables, DESI spectra + their FastSpecFit fits, and the Siena Galaxy Atlas (built from Legacy Surveys imaging) + Legacy Surveys.
   WISE cannot be counted twice: only AllWISE is collected, and the W1/W2 forced photometry of a Legacy Surveys row belongs to that
   row.  The Gaia DSC probabilities are columns of the Gaia row.  Pan-STARRS1, Legacy Surveys and SDSS imaging (different
   telescopes, the same optical bands) still count separately, deliberately: the switches ask for independent *detections* (a
   deblending fragment or a pipeline artefact has none), not for independent wavelengths.  An SDSS spectrum and SDSS imaging are
   different measurements and count separately.  The committed tables were made with name counting; they can differ only for
   objects carrying one of the four pairs.  The blind runs drop spectra, SOS rows are RR Lyrae, Cepheids and long-period variables,
   ZTF periodic rows are periodic variables and SGA rows are large galaxies, so no such pair is expected among the QSO labels.  This
   was not re-measured, because the raw files are not in the repository.  An offline replay should confirm it before any default
   is changed.
2. **What a held-back object becomes.**  It was `UNKNOWN` with status `LOW_CONFIDENCE` and best candidate `QSO`, and its
   `unknown_reason` read "QSO or GALAXY: probabilities overlap (0.72 vs ...)", which did not say why.  Now, while a label switch is
   on, it also keeps the reading `secondary_class = QSO`, `secondary_class_reason = LOWLAT_QSO_HELD` (where it has no other reading),
   and the new column `lowlat_qso_hold` says why, for example "QSO label withheld at |b| = 13.8 < 20 deg (V2_LOWLAT_QSO): measured by
   1 survey, 2 needed".  `unknown_reason`, and through it the summary file, shows that text.  `run_archives_status` is about archives
   and is not used for this.  `wise_second` and `wise_footprint` remove evidence instead of holding the label, so such an object
   ends with what its other evidence says, often `NO_EVIDENCE` with the AllWISE-only reason.  That reason does not name the switch.
3. **Order of pre-registration and collection.**  The region list was locked in `8a941ef` (2026-11-27 12:45:59 UTC) and the
   predictions and adoption criteria in `8b108c2` (13:15:51 UTC).  `PREDICTIONS_CONFIRM.md` is unchanged since (empty diff from
   `8b108c2` to the work branch head).  When the confirmation regions were collected is not recorded in the repository: they were
   collected in the work session's container and the raw files were not committed.  So the order rests on the work session's
   statement; its log or raw-folder times would settle it.  A later confirmation run should write its start time into its results.
4. **"removed (paired)".**  This is the density of the control (base) false labels that the variant no longer has.  It is a subset
   of the control's labels, so its region bootstrap draws the same regions for both (`ab_variants.py`).  It is defined in the
   table header above and in the work report.  It equals base minus variant: 159.15 - 73.67 = 85.49 deg^-2 for `surveys2`.
5. **Intervals.**  All densities have a region bootstrap (4,000 resamples of whole cones, area-weighted; `ab_variants.boot_density`),
   not a Poisson interval.  This matters because ten cones hold 56 % of the calibration labels.
6. **|b| >= 20 deg unchanged, and the boundary.**  This is now structural, not only measured.  Every switch tests the object's own
   |b| against `V2_LOWLAT_QSO_ABSB`: the label holds use the object position, the two WISE switches the AllWISE row position.
   `wise_footprint` did not do this.  It removed the Stern evidence within 30 deg of the Galactic Centre at any latitude, for example
   at l = 5 deg, b = 25 deg.  The five fields measured at |b| = 42-72 deg are far from the Centre and could not show it.  It now acts
   only below the limit, and a test covers it.  A region that straddles 20 deg is split object by object.
7. **Not measured: spectroscopic quasars.**  `surveys2` / `surveys3` also hold back a label decided by a spectroscopic catalogue
   class, because that is evidence too, when the object has fewer surveys.  Spectroscopic targets normally have imaging rows as
   well, but the blind runs drop spectra, so this was not measured.  Exempting a spectroscopic class should be considered before
   any default is changed.

