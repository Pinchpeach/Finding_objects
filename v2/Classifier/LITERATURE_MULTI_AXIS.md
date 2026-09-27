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
