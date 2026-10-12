# Multi-axis classifier literature survey

## Design principle

The classifier should be multi-axis rather than a single mutually-exclusive tree.
Physical state, variability and transient/nebular phenomena can coexist. Missing
data must remain neutral, and classes without validated evidence should abstain.

## 1. White dwarfs (physical axis)

Recommended observables:
- Gaia astrometry and colour-magnitude location for WD candidate routing.
- Gaia BP/RP (XP) spectrophotometry / synthetic photometry for DA vs non-DA.
- SDSS or other spectroscopy for subtype truth and detailed atmospheric typing.

Literature:
- Jiménez-Esteban et al. (2023), MNRAS 518, 5106: Gaia DR3 WD population,
  Gaia low-resolution spectra / SED fitting; DA/non-DA classification above 90%
  accuracy on labelled objects.
- García-Zamora et al. (2023), MNRAS 521, 760: data-driven WD candidate
  selection and spectroscopic classification using Gaia + SDSS spectra.
- Gaia DR3 synthetic photometry paper (Montegriffo et al. 2023, A&A 674 A33):
  XP spectra support synthetic photometry and a WD DA/non-DA catalogue.

Gaia DSC (2.17.0): the Combmod white-dwarf class has completeness 0.43 and
purity 0.25 at the all-sky prior, and the physical-binary class purity 0.075
(Delchambre et al. 2023, A&A 674, A31, Table 3).  A WD needs the Gentile
Fusillo et al. (2021, Eq. 1) HR locus; DSC WD alone no longer routes WD, and
the DSC binary class only adds to the stellar probability (no
BINARY_CANDIDATE family).

Implementation implication:
Keep the already validated WD routing and Gaia-XP DA/DB path. Expand only when
external truth exists for DC/DO/DQ/DZ/magnetic/composite subclasses.

## 2. RGB / RC / AGB (physical axis)

Recommended observables:
- Gaia distance, extinction-aware absolute magnitude and colour.
- Stellar parameters (Teff, log g, metallicity) from spectroscopy when available.
- Long-period variability and infrared excess for AGB support.
- Asteroseismology is the strongest evolutionary-state discriminator when
  available, especially for RGB vs core-He burning stars.

Literature:
- Elsworth et al. / APOKASC evolutionary-state consolidation (MNRAS 489, 4641,
  2019): multiple asteroseismic methods provide robust red-giant evolutionary
  state; AGB separation is substantially harder.
- Vrard et al. (2024 preprint): complete Kepler red-giant evolutionary-state
  catalogue; emphasizes that RGB/AGB separation degrades as stars evolve.
- Gaia DR3 GSP-Phot (Andrae et al. 2023, A&A 674 A27) provides BP/RP-derived
  stellar parameters but they require quality-aware use.

Implementation implication:
Do not make hard RGB/AGB labels from a single colour cut. Use a hierarchical
evidence model and abstain when only broad red-giant evidence is available.

### 2.1 RED_GIANT on the physical axis (2.13.0)

RGB and AGB stars cannot be separated without asteroseismology (Vrard et al.
2025, the truth set) or luminosity.  "Cool giant" can: the luminosity class
of the sub-class classifier (Gaia CMD with parallax S/N ≥ 5; else LAMOST /
GSP-Spec log g; else GSP-Phot log g, against the Ciardi et al. 2011 giant
boundary) agrees with APOGEE DR17 for 96.9–98.3 % (2.6.2).  RED_GIANT =
luminosity class III and Teff < 5500 K.  Gaia FLAME was not usable for these
stars: for the Kepler giants its masses and ages are unphysical (median
3.3 M☉, 0.3 Gyr; `benchmark/probe_flame_giants.py`), as the Gaia DR3
documentation and Fouesneau et al. (2023) warn for giants.

2.17.0 (literature review):
- Luminosity class III is stricter (`LITERATURE_SUBCLASS.md`): ΔM ≤ −3 or
  M_G < 4 on the CMD (Ruiz-Dern et al. 2018), log g < 3.5 below the Ciardi
  boundary (subgiants become IV), and GSP-Spec log g calibrated
  (Recio-Blanco et al. 2023).  Teff for the 5500 K cut comes only from
  flag-checked spectroscopy or GSP-Phot.
- Gaia FLAME giants: the documented guardrails are 1.0 ≤ M < 2.0 M☉,
  age > 1.5 Gyr, evolstage 490–1300, and second flags_flame digit 0
  (Fouesneau et al. 2023, Sect. 3.3.2; DR3 documentation 11.3.6).
  - The FLAME tracks end at the RGB tip, so red-clump and AGB stars are
    forced onto an "RGB" stage.  A passing star is therefore RED_GIANT, not
    RGB.
  - On the 180 Kepler stars, 9 pass the new guardrails (8 RGB, 1 AGB).  The
    old guardrails passed 10 (8 RGB, 2 AGB).
- Suh (2021) match: with a good parallax and M_Ks > −1 (fainter than the
  red clump) it is not AGB.  The catalogue includes visual carbon stars from
  general lists.

Cross-validation (Vrard+2025 Kepler RGB 203, AGB 250): RGB family accuracy
0 → 51.7 %, AGB 0 → 41.2 %; none labelled a non-giant.  The rest have no
GSP-Phot log g in the validation collector.  Before 2.11.0 these stars never
reached the axis: the coarse fusion called them GALAXY (wrong-signed Gaia
weights).

## 3. Variable stars (variability axis)

Recommended observables:
- Multi-epoch light curves.
- Period, amplitude, colour, Fourier coefficients, phase-shape features.
- Period-luminosity relations where appropriate.
- Catalogue-level Gaia SOS classifications may be used as strong labelled
  evidence, while preserving provenance.

Literature:
- Gaia DR3 SOS RR Lyrae processing (Clementini et al. 2022/2023): validation
  uses period-amplitude and Fourier phase parameters (phi21, phi31).
- Gaia DR3 SOS Cepheid processing (Ripepi et al. 2022/2023): multi-band
  time-series characterization and validation for Cepheid subclasses.
- Groenewegen (2017): period-luminosity relations are central for Mira,
  RR Lyrae and Cepheid families.

Implementation implication:
Variability classification should consume time-series features rather than static
photometry alone. AGB and Mira must remain separate axes so an object can be
physical=AGB and variability=MIRA simultaneously.

### 3.1 ZTF periodic variables (2.8.0)

Source: Chen et al. (2020, ApJS 249, 18), 781,602 periodic variables from
ZTF DR2 g/r light curves (Bellm et al. 2019, PASP 131, 018002; Masci et al.
2019, PASP 131, 018003), VizieR J/ApJS/249/18/table2. Types from period,
amplitude and Fourier shape: EW, EA, BYDra, RSCVN, SR, Mira, RR, RRc,
DSCT, CEP, CEPII (map in `axes/variability.py: ZTF_MAP`).

Order of evidence: SIMBAD curated type > Gaia SOS RR Lyrae / Cepheid
(dedicated multi-band fits) > ZTF type > Gaia LPV C-star flag > broad Gaia
classifier. ZTF is the only source here with a Mira leaf.

Cross-validation on ASAS-SN variables (II/366, independent of ZTF and
Gaia), 250 per class:

| truth | exact before | exact after | ZTF-labelled (exact) |
|---|---:|---:|---|
| MIRA | 0.0 % | 25.6 % | 65 (98.5 %) |
| LPV | 68.8 % | 68.0 % | 24 (83.3 %; 3 called Mira) |
| RR Lyrae | 82.4 % | 82.4 % | 11 (9.1 %; 10 called EW/EA) |
| Cepheid | 93.2 % | 93.2 % | 0 |

The RR → eclipsing cases are the known RRc / EW ambiguity (near-sinusoidal
light curves; an EW at twice the period looks alike) and partly matches
3–6″ away (blends). These objects had no correct label before either, so
the RR Lyrae exact rate is unchanged.

#### 3.1.1 RR Lyrae vs eclipsing binaries in ZTF (2.11.1)

ASAS-SN RRAB/RRC/EW/EA stars (II/366) matched to Chen et al. (2020) ZTF
types (`benchmark/build_rr_ew_truth.py`, `evaluate_rr_ew.py`).  The ZTF g/r
amplitude ratio is a physical arbiter: a pulsator changes temperature over
its cycle, so its amplitude grows towards the blue; a contact binary of two
similar-temperature stars varies nearly achromatically.

| ASAS-SN → ZTF | n | A_g/A_r median | P_ZTF / P_ASAS-SN |
|---|---:|---:|---:|
| RRC → RRc (agree) | 1,612 | 1.42 | 1.0 |
| EW → EW (agree) | 1,670 | 1.07 | 1.0 |
| RRC → EW | 182 | **1.05** | 2.0 |
| EW → RRc | 41 | **1.40** | 0.5 |

In both directions of disagreement the amplitude ratio sides with ZTF: the
ASAS-SN single-band (V) type is the error.  A veto on the ratio (pulsator
label with A_g/A_r < 1.15–1.20, eclipsing label > 1.20–1.25) would reject
only labels that ASAS-SN also confirms (detached binaries with unequal
components are chromatic too), so the rule is unchanged and the ratio is
reported in the ZTF evidence (`amplitude_ratio_g_r`).  Part of the
"RR Lyrae → eclipsing" cross-validation errors are therefore truth errors.

### 3.2 Mira from the Gaia DR3 LPV amplitude (2.12.0)

Miras are the large-amplitude long-period variables (GCVS: ΔV > 2.5 mag).
Gaia DR3 LPV `amplitude` is half the peak-to-peak range of the fitted G
model (Lebzelter et al. 2023, A&A 674, A15).  In Gaia DR2 the Mira-like LPVs
sit at G ranges of ~1–2.5 mag and the semi-regulars below ~1 mag (Mowlavi et
al. 2018, A&A 618, A58); Grady et al. (2019) cut ΔG > 0.433 mag on a
different amplitude statistic.

Rule: semi-amplitude ≥ 0.6 mag (G range ≥ 1.2 mag) and, when a period is
published, P ≥ 80 d (GCVS Mira range).  Fitted on even-numbered ASAS-SN
M/SR stars matched to the Gaia LPV table (3,681 M, 2,592 SR), checked on the
odd half: precision 0.934, recall 0.968 (precision levels off at 0.93–0.95
for any threshold: a tail of large-amplitude ASAS-SN SR stars).

2.17.0: a published period with 80 ≤ P < 1000 d is required.  This is the
Gaia DR3 Mira selection of Zhang & Sanders (2023, MNRAS 521, 5309): 80 < P <
1000 d, semi-amplitude ≥ 0.5.  It made no change on the truth set, where
every star has a period.  Their alias windows (170–200 d with amplitude >
1.3, 350–400 d with amplitude > 1.6) are not excluded: they mark unreliable
periods, and excluding them removed 30 Miras for 6 SRs.  The C-star subtype
uses the gated `is_cstar` (G_BP < 19, 7 < median_delta_wl_rp < 11; Lebzelter
et al. 2023).

Cross-validation (250 ASAS-SN Miras, 250 SR): Mira exact 25.6 → 94.8 %.
The rule labelled 184 objects Mira, 173 correctly (precision 0.94); the 11
SR stars it called Mira lower LPV exact 68.0 → 63.6 %.

## 4. Neutron stars / pulsars (compact axis)

Recommended observables:
- Pulsations / period and period derivative when available.
- Radio compactness, steep radio spectral index and variability.
- Gamma-ray spectral shape and variability for Fermi sources.
- X-ray counterpart properties and multiwavelength association evidence.

Literature:
- Manchester et al. (2005), ATNF Pulsar Catalogue: primary reference/truth
  catalogue for published pulsar properties.
- Bates et al. (2014), SPINN: neural-network pulsar candidate selection from
  radio survey candidates.
- Saz Parkinson et al.-style / later Fermi ML work: gamma-ray spectral and
  variability features can distinguish pulsar-like sources from AGN-like sources.
- Hui et al. (2020), MNRAS 495, 1093: ML selection of pulsar-like Fermi sources
  followed by X-ray/optical/IR counterpart analysis.

Implementation implication:
Output NS/PULSAR as candidate likelihood unless pulsation or trusted catalogue
identification gives direct evidence. Do not equate an X-ray source with an NS.

### 4.1 Radio pulsar candidates without ATNF (2.6.3; revised 2.10.0)

Rule (`axes/compact.py: radio_pulsar_evidence`, label `PULSAR_CANDIDATE`):
alpha(150 MHz → 1.4 GHz) ≤ −1.5 AND TGSS S_total/S_peak ≤ 1.5 (Frail et al.
2018). NVSS linear polarisation is supporting evidence (status
`RADIO_STEEP_COMPACT_POLARISED`) only when significant: P/σ_P ≥ 3 and
P/S > 5 %.

- Frail et al. (2016, ApJ 829, 119; 2018, MNRAS 475, 942): TGSS ADR1 – NVSS
  spectral index alpha ≤ −1.5 with compactness S_int/S_peak ≤ 1.5 selects
  pulsar candidates; known pulsars are recovered by this cut.
- Han & Tian (1999, A&AS 136, 571): NVSS linear polarisation > ~5 % keeps most
  pulsars and rejects most extragalactic sources (median ~2 %).
- Jankowski et al. (2018, MNRAS 473, 4436): mean pulsar spectral index
  −1.60 ± 0.54; Bates et al. (2013, MNRAS 431, 1352): −1.4 ± 1.0.
- Intema et al. (2017, A&A 598, A78): TGSS ADR1, 150 MHz, 25″ beam.
- Condon et al. (1998, AJ 115, 1693): NVSS 1.4 GHz with Stokes Q/U.

Calibration (`benchmark/build_pulsar_truth.py`, `evaluate_pulsar.py`; every
quantity measured around the NVSS position, ATNF only as label; one row per
NVSS source, since e.g. 33 Terzan 5 pulsars share one source):

| quantity | ATNF pulsar sources (116 in NVSS) | NVSS control (2,531) |
|---|---|---|
| median alpha(150–1400) | −1.38 | −0.73 |
| median NVSS fractional pol. | 0.139 | 0.024 |
| Gaia DR3 within 5″ | 38.8 % | 16.8 % |
| alpha + compactness (rule) | 25 (recall 0.216) | 3 (FPR 0.0012) |
| + "fpol > 5 %" (2.6.3 rule) | 16 (0.138) | 3 (0.0012) |
| + significant polarisation | 6 (0.052) | 0 |

Why polarisation is not a cut: NVSS polarised-flux errors are ~0.3 mJy, so
for the typical 3–7 mJy candidate "fpol > 5 %" is a ~1σ test; it removed no
false positive and lost 9 pulsars. "No optical counterpart" was not used:
pulsars in the Galactic plane have a chance Gaia neighbour within 5″ more
often than the control sources. The rule needs a TGSS detection (66/116
pulsar sources). With ~3,000 pulsars among ~1.8 M NVSS sources the sky-wide
purity is low (an FPR of 0.12 % is ~2,000 sources), so the label is a
candidate, not an identification.

### 4.2 Pulsar-candidate posterior (2.14.0)

The candidate label is kept (no recall loss); its confidence is a sky-level
posterior from naive Bayes with likelihood ratios measured per NVSS source
(`benchmark/evaluate_pulsar.py`):

| factor | pulsar sources | ordinary sources | LR present / absent |
|---|---|---|---|
| prior | 116 known pulsar sources among 1.77 M NVSS sources | | odds 6.6 × 10⁻⁵ |
| steep + compact | 25/116 | 3/2531 (Laplace 4/2533) | 137 |
| Galactic plane, \|b\| < 10° | 0.621 | 0.099 | 6.3 / 0.42 |
| significant polarisation (P/σ ≥ 3, > 5 %) | 28/116 | 84/2531 | 7.3 / 0.79 |

Normal pulsars concentrate to the plane (scale height 330 pc; Lorimer et al.
2006); millisecond pulsars are nearly isotropic, so the plane factor
under-rates them.  The factors are combined assuming independence.  Posterior
by group, with the candidates of the sample:

| group | pulsars | controls | posterior |
|---|---:|---:|---:|
| plane, polarised | 2 | 0 | 0.29 |
| plane, not polarised | 10 | 1 | 0.042 |
| off-plane, polarised | 4 | 0 | 0.027 |
| off-plane, not polarised | 9 | 2 | 0.003 |

Not done: LoTSS 144 MHz as a second spectral index (only 5 of the 116 pulsar
sources are in LoTSS); Fermi 4FGL (only γ-ray pulsars, ~10 %, and a full
rebuild of the sample); circular polarisation surveys (Sobey et al. 2022;
Wang et al. 2022) -- the most promising next step.

## 5. Planetary nebulae (phenomenon/nebular axis)

Recommended observables:
- Optical emission-line ratios: [O III]/Hbeta, [N II]/Halpha, [S II]/Halpha,
  He II where available.
- SMB/BPT-like diagnostic diagrams.
- H-alpha morphology and angular extent.
- 2MASS + WISE infrared colours for candidate discrimination.
- HASH status as external truth/provenance, not an unqualified model feature.

Literature:
- Parker, Bojicic & Frew (2016), HASH PN database: curated Galactic PN database
  designed to remove mimics and collect multiwavelength/spectroscopic evidence.
- Akras et al. (2019), MNRAS 488, 3238: 2MASS/WISE colour diagnostics and
  classification-tree discrimination of compact PN from mimics.
- Akyuz et al. (2024), MNRAS 527, 1481: spectroscopic confirmation using
  characteristic emission-line ratios and SMB/BPT diagnostics.

Implementation implication:
PN should not be inferred from IR colour alone. Spectroscopic evidence should
receive the strongest weight; photometry is candidate-level evidence.

## 6. Supernovae / transients (phenomenon axis)

Recommended observables:
- Multi-band time-series light curves, cadence and uncertainty.
- Rise/decline shape, colours, peak epoch and peak brightness.
- Host association and host redshift as optional supporting information.
- Spectroscopy remains the strongest confirmation/type evidence.

Literature:
- Lochner et al. (2016): feature extraction from light curves followed by ML;
  representative training sets are critical.
- Möller & de Boissière (2020), SuperNNova: recurrent neural-network SN
  classification directly from photometric light curves, including incomplete
  pre-maximum curves.
- HSC transient ML work (2020): performance improves as more temporal data
  become available.
- Recent 4MOST transient classifier comparison (2025): SNID, DASH and NGSF
  illustrate the continuing role of spectroscopic transient typing.

Implementation implication:
SN classification belongs to a temporal/event pipeline. A single static catalogue
row without multi-epoch evidence should not produce a confident SN subtype.

## Confidence of axis labels (2.15.0)

Most axis labels come from rules without a score.  Their calibrated
probability is the measured precision of the rule that produced them on the
independent truth sets (`calibration/fit_axis_calibration.py`,
`rule_precision`): the share of rows with that (status, label) whose truth is
that label (a broader family label counts as right for its members), only for
labels among the axis's truth classes and with ≥ 20 rows; the Wilson (1927)
95 % lower bound is stored with it.  The truth sets are class-balanced (250
per class), so this is a precision for that mix, not a sky-prior posterior.
Labels without truth (e.g. ECLIPSING) stay uncalibrated.

## Implementation order

1. Preserve and wire validated WD path into physical axis.
2. Implement Variables because Gaia DR3 provides direct SOS truth plus strong
   period/amplitude/Fourier diagnostics.
3. Implement RGB/AGB as a conservative hierarchical red-giant model, keeping an
   explicit RED_GIANT/UNKNOWN state when RGB-vs-AGB evidence is insufficient.
4. Implement PN using spectroscopy-first evidence and IR candidate support.
5. Implement pulsar/NS candidate scoring using ATNF/Fermi/radio/X-ray evidence.
6. Implement SN only after time-series ingestion exists; static rawdata is not
   sufficient for a reliable transient classifier.

## Validation policy

Every branch must:
- use an external truth set distinct from training where possible;
- preserve class probability/evidence provenance;
- measure per-class precision/recall and confusion;
- define an abstention threshold;
- keep missing observations masked/neutral;
- never convert catalogue query failure into negative astrophysical evidence.
