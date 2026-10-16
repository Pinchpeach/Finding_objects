# Second-stage (sub-class) classifier — literature basis and validation

Implementation: `subclass.py` (run by `control.py` after the coarse class and
the multi-axis classifier). Evaluation: `v2/benchmark/evaluate_subclass.py`,
which writes the per-rule precision (`subclass_rule_precision.json`, SDSS
train split) that the classifier reports as `subclass_confidence`.

Output columns: `subclass` (display label), `subclass_code`
(`STAR:<letter>:<lum>`, `GALAXY:<activity>:<profile>`,
`QSO:<radio>:<zclass>:<X>`), `subclass_confidence`, `subclass_rule`,
`subclass_status`, `subclass_basis`, `subclass_json`.

Order of authority everywhere: a spectroscopic or curated catalogue label
outranks a photometric criterion; when no criterion applies the field stays
empty with a status (`NO_SUBCLASS_EVIDENCE`, `NOT_ROUTED`).

## STAR

### Spectral type (temperature class)
* Scale: the Pecaut & Mamajek (2013, ApJS 208, 9) dwarf colour–Teff
  sequence, in its maintained version (E. Mamajek, "A Modern Mean Dwarf Stellar
  Color and Effective Temperature Sequence", v2022.04.16), stored as
  `reference/mamajek_dwarf_sequence.csv` (SpT, Teff, Gaia BP−RP, M_G, g−r,
  i−z, …). For example: A0V 9700 K / BP−RP −0.04; G2V 5770 K / 0.82;
  K0V 5270 K / 0.98; M0V 3850 K / 1.84.
* Estimators, in priority order:
  1. SIMBAD MK type (curated literature; also gives the luminosity class);
  2. LAMOST, then SDSS spectrum subclass. SDSS A/F/G subclasses are used only
     when no Gaia colour exists (see validation below);
  3. Gaia: the mean of the dereddened (BP−RP)₀ type and the GSP-Phot Teff
     type (Andrae et al. 2023, A&A 674, A27). Dereddening uses GSP-Phot
     E(BP−RP), or else SFD E(B−V) × 1.339 (Casagrande & VandenBerg 2018,
     MNRAS 479, L102);
  4. Legacy Surveys (g−r)₀ (< 1.3, i.e. up to K7), Pan-STARRS1 i−z (M dwarfs),
     then the Teff alone.
* What the label means: the temperature-equivalent MK type on the dwarf
  scale. Metal-poor halo stars have weak metal lines and are typed earlier
  by line-based spectral templates.

### Luminosity class
* Primary: height above the dwarf sequence in the Gaia CMD,
  ΔM_G = M_G − M_G,MS((BP−RP)₀). This needs parallax S/N ≥ 5 and A_G
  (GSP-Phot, or 2.740 E(B−V)).
  * White-dwarf region: M_G > 6 + 5 (BP−RP)₀ (Gentile Fusillo et al. 2021,
    Eq. 1; the same line as the WD branch). No class is given. Before 2.17.0
    the line was ΔM > 3, which sits about 2 mag above the WD locus.
  * VI: 1 < ΔM ≤ 3 and (BP−RP)₀ ≥ 0.3. Bluer stars, or stars more than
    3 mag below the sequence, are hot subdwarfs, WD+MS binaries or CVs
    (Culpan et al. 2022), so no class is given.
  * V: ΔM > −1.0. Unresolved equal-mass binaries lie ≤ 0.75 mag above the
    main sequence (Hurley & Tout 1998); metallicity and age spread add about
    0.3 mag.
  * III: ΔM ≤ −3, or M_G < 4 with ΔM ≤ −2.5 or (BP−RP)₀ ≥ 1.3. Red giants
    are ≥ 3 mag above the sequence, and Ruiz-Dern et al. (2018) select red
    giants with M_G < 4.
  * IV: everything else above the sequence. Red stars 1–3 mag above it are
    subgiants, pre-main-sequence stars or overluminous binaries. Before
    2.17.0 these were III.
  * Measured against APOGEE DR17 giants (log g < 3.5, 8,196 stars, no
    extinction applied): III precision 0.948 → 0.959, recall 0.994 → 0.994.
* Fallback: the Ciardi et al. (2011, AJ 141, 108) dwarf / evolved-star
  boundary, as used for Kepler targets:
  * log g ≤ 5.2 − 2.8×10⁻⁴ Teff for 4250 < Teff < 6000 K;
  * log g ≤ 4.0 below 4250 K;
  * log g ≤ 3.5 above 6000 K.

  The overlap near log g 3.7 is "likely dominated by sub-giants", so since
  2.17.0 only log g < 3.5 below the boundary is III; the rest is IV. The
  log g comes from LAMOST LASP, Gaia GSP-Spec or GSP-Phot.
  * Measured against APOGEE, III precision rises and recall falls:

    | Source | Precision | Recall |
    |---|---|---|
    | GSP-Spec | 0.948 → 0.995 | 0.992 → 0.928 |
    | LAMOST | 0.949 → 0.994 | 0.991 → 0.943 |
    | GSP-Phot | 0.963 → 0.982 | 0.971 → 0.952 |
* GSP-Spec log g and [M/H] are calibrated as the producers recommend
  (Recio-Blanco et al. 2023, Eqs. 1–2 and Table 3; Fouesneau et al. 2023
  App. A).
  * Median log g residual vs APOGEE: −0.13 → +0.07.
  * Median [M/H] residual for giants: −0.066 → +0.020.
  * Metal-poor tag: 25 → 24 of 32 flagged are correct, within noise.
* The physical axis (Gaia FLAME giant stage) forces III. The white-dwarf route
  (Gentile Fusillo et al. 2021 locus + Gaia DSC) overrides the spectral type.
* Carbon stars, CVs and WD subtypes are taken only from LAMOST/SDSS spectra.
* Binary tags: no tag from the Gaia DSC "binary" class (purity 0.075;
  Delchambre et al. 2023, Table 3). There is no RUWE binary tag for AGB
  candidates, because for AGB stars a high RUWE reflects size and saturation,
  not binarity (Andriantsaralaza et al. 2022).

### Validation
SDSS DR18 stars (template subclass) and DESI DR1 stars (letter type),
coarse class given:

| sample | typed | letter accuracy | within ±1 letter | notes |
|---|---|---|---|---|
| SDSS test | 603 / 611 | 0.54 | 0.94 | K/M truth: median \|Δ\| = 1 subtype, 84 % within 2 subtypes |
| SDSS train | 1854 / 1889 | 0.54 | 0.94 | K 0.96, G 0.87, M 0.74 |
| DESI DR1 (independent) | 1463 / 1508 | 0.61 | 0.94 | Gaia BP−RP + Teff rule: 0.81 (n = 336); PS1 i−z: 0.92 |

* SDSS A0/F labels are offset from both Gaia estimators. For example, the
  814 SDSS "A0" stars have median (BP−RP)₀ = 0.47 and GSP-Phot Teff 6900 K
  (≈ F2V), and "F5"/"F9" sit at G0–K0 colours.
* DESI G stars sit at bluer colours (F on the dwarf scale) than SDSS
  G stars, so the two spectroscopic pipelines disagree with each other
  across F/G.
* Letter accuracy is therefore truth-limited in A–G. The ±1-letter rate
  (0.94 in all three samples) and the K/M subtype error are the meaningful
  figures.
* Luminosity classes: almost all faint high-latitude benchmark stars come
  out V, as expected for those samples. There is no giant truth set yet.

## GALAXY

### Activity
1. SDSS spectrum subclass and the project's own line diagnostics (order
   changed in 2.18.0):
   * BROADLINE → AGN first: a narrow-line fit misses broad Hα, so 29 SDSS
     BROADLINE objects would look WHAN-retired.
   * Then WHAN → BPT from the line fluxes (`galaxy_lines`, below).
   * Then the SDSS subclass (Bolton et al. 2012, AJ 144, 144) as a fallback.
     Its SF/AGN line, log([O III]/Hβ) = 0.7 − 1.2(log([N II]/Hα) + 0.4), is
     neither Kewley et al. 2001 nor Kauffmann et al. 2003, so composites
     become "AGN". It also has no retired-galaxy test (Cid Fernandes et al.
     2011).
   * STARBURST means EW(Hα) > 50 Å.
   * Agreement with the Portsmouth BPT on 1,190 SDSS galaxies with a
     subclass: 84.1 % (subclass first) → 86.9 % (lines first).
   * Fibre aperture: SDSS spectra cover > 20 % of the galaxy light only at
     z > 0.04 (Kewley, Jansen & Geller 2005); the DESI 1.5″ fibre needs
     about twice the distance (z > 0.08). Below that the line class is
     tagged `APERTURE_NUCLEAR`, meaning it describes the nucleus.
2. SIMBAD types: Sy1/Sy2/SyG/LIN/AGN → AGN; SBG → starburst; H2G/EmG/bCG →
   star-forming.
3. Mid-IR AGN: W1−W2 ≥ 0.8 with W2 < 15.05 (Vega; Stern et al. 2012, ApJ
   753, 30), with S/N ≥ 10 in W1 and W2 (the photometry Stern et al.
   calibrated on, as in Stage-4 WISE-AGN-001; 2.18.0).
4. WISE W2−W3 (Jarrett et al. 2017, ApJ 836, 182; 2019, ApJS 245, 25):
   * star-forming discs > 3.5 (Jarrett et al. 2017; 3.0 before 2.18.0),
     spheroids < 1.5, intermediate discs in between (no label);
   * SDSS test split: SF precision 0.754 → 0.871, activity accuracy
     79.5 → 87.9 %, coverage 42.3 → 31.8 %;
   * applied when W3 S/N ≥ 5 (σ < 0.2 mag);
   * when AllWISE gives only a W3 upper limit, the true colour is bluer than
     W2 − W3_lim, so W2 − W3_lim < 1.5 also implies a spheroid.
5. GALEX (NUV−r)₀ > 5 → quiescent: the red sequence of Salim (2014, SerAJ
   189, 1) and Wyder et al. (2007). Kaviraj et al. (2007) find recent star
   formation below 5.5, so 5–5.5 is "red sequence", not necessarily dead.
   R_NUV = 8.2 (Wyder et al. 2007).

### Light profile
* Legacy Surveys DEV (de Vaucouleurs) → early-type-like; EXP → disc
  (Dey et al. 2019 Tractor models). SER models: Sérsic n ≥ 2.5 → early type,
  n < 2.5 → disc (Shen et al. 2003, MNRAS 343, 978; Blanton et al. 2003).
* Otherwise SDSS (u−r)₀ ≥ 2.22 → early type, < 2.22 → late type
  (Strateva et al. 2001, AJ 122, 1861).

### Validation
SDSS galaxies, truth = SDSS subclass. "Quiescent" here means no emission
line strong enough for an SDSS subclass.

| rule | train n | train precision | test n | test precision |
|---|---|---|---|---|
| WISE W2−W3 > 3 → SF | 605 | 0.76 | 215 | 0.75 |
| WISE W3 upper limit, W2−W3 < 1.5 → quiescent | 104 | 0.96 | 38 | 1.00 |
| WISE W2−W3 < 1.5 (detected) → quiescent | 20 | 0.70 | 6 | 0.83 |
| GALEX NUV−r > 5 → quiescent | 117 | 0.91 | 33 | 0.88 |
| Stern W1−W2 ≥ 0.8 → AGN | 4 | 0.25 | 5 | 0.40 |

* Overall (test): 42 % of galaxies receive a photometric activity label,
  79 % of them correct.
* Most "SF" errors have SDSS-weak lines but dusty mid-IR emission.
* The Stern AGN cut is kept for its literature reliability on luminous AGN
  (95 % in COSMOS). Its low precision against BPT reflects composite /
  star-forming BPT hosts of IR AGN, and n is tiny.

## QSO
* Radio loudness:
  * R_i = log(F_1.4GHz / F_i) = 0.4 (m_i − t), with
    t = −2.5 log10(F_1.4GHz / 3631 Jy); radio-loud when R_i > 1, i.e. a
    flux ratio > 10 (Ivezić et al. 2002, AJ 124, 2364; Kellermann et al.
    1989).
  * 1.4 GHz flux: FIRST F_int, else NVSS. LoTSS (144 MHz) and VLASS (3 GHz)
    are scaled with α = −0.7 (Condon 1992).
  * i magnitude: PS1 → SDSS → LS.
* Redshift class from a spectroscopic redshift only: z ≥ 2.1 "high-z", where
  the Lyα forest enters the optical (Ross et al. 2012).
* X-ray counterpart (Chandra CSC 2.0, 4XMM-DR13, eRASS1); SIMBAD
  Seyfert/BL Lac/blazar types.
* Not validated here: the benchmark preserves no radio or X-ray fluxes. These
  are definitional properties computed from the measurements.

## Attributes (`subclass_tags`, 2026-10-10 extension)
Each object can carry several attributes besides its main sub-class. They are
stored with their measurement in `subclass_json["tags"]`, listed in
`subclass_tags`, and shown in the app.

### STAR
| attribute | rule | basis |
|---|---|---|
| thin disc / thick disc / halo | Gaia V_T = 4.74 μ/ϖ (ϖ/σ ≥ 5): < 40, 60–150, > 200 km/s (gaps left open) | Babusiaux et al. 2018, A&A 616, A10 (Gaia DR2 HRDs) |
| subdwarf (luminosity class VI) | 1 < ΔM_G ≤ 3 below the dwarf sequence | metal-poor subdwarfs lie 1–2 mag below the MS (Kuiper 1939; Gizis 1997) |
| astrometric binary candidate | RUWE > 1.4 | Lindegren et al. 2018; Belokurov et al. 2020 |
| binary candidate | Gaia DSC binary probability ≥ 0.8 | Creevey et al. 2023 |
| variable type | the variability axis (Gaia DR3 SOS / classifier, SIMBAD) | Rimoldini et al. 2023 |
| nearby star | ϖ > 10 mas, ϖ/σ ≥ 10 (within 100 pc) | Gaia Catalogue of Nearby Stars volume (Gaia Collaboration, Smart et al. 2021) |
| high proper motion | μ > 150 mas/yr | LSPM-North limit (Lépine & Shara 2005) |
| red-clump giant | giant, 1.8 ≤ G−Ks ≤ 2.6, \|M_G − (0.495 + 1.121(G−Ks−2.1))\| ≤ 0.5 | Ruiz-Dern et al. 2018, A&A 609, A116 |
| infrared excess (dust disc / shell) | W1−W2 > 0.25 and W2−W3 > 1.0 (W3 S/N ≥ 5) | lower bounds of the Koenig et al. 2012 class II locus; YSO, debris disc or AGB shell (background galaxies can mimic it) |
| X-ray active star | Chandra / XMM / eROSITA counterpart | coronal activity: young stars, fast rotators, active binaries |
| metal-poor / very metal-poor | spectroscopic [Fe/H] < −1 / < −2 (LAMOST LASP, Gaia GSP-Spec). GSP-Phot [M/H] is no longer used (2.6.2): against APOGEE DR17 its [M/H] < −1 flag had precision 0.15, recall 0.14 | Beers & Christlieb 2005; validation `LITERATURE_SPECTROSCOPY.md` §2.2.1 |

Physical checks (no truth labels exist for these):
* SDSS stars: median GSP-Phot [M/H] falls from the thin disc (−0.52) to the
  thick disc (−0.69) to the halo (−1.35).
* SDSS stars with 1 < ΔM ≤ 3 have [M/H] = −1.40 / −1.47, against −0.66 on the
  main sequence.
* The fainter DESI star sample has no halo stars with ϖ/σ ≥ 5, and its
  thin/thick-disc [M/H] trend is not monotonic (−0.51 / −0.36, n = 56 / 36).

### GALAXY
| attribute | rule | basis |
|---|---|---|
| green valley (activity) | 4 < (NUV−r)₀ ≤ 5 | Salim 2014; Wyder et al. 2007 |
| type 1 / type 2 AGN | SDSS AGN with or without BROADLINE; SIMBAD Sy1/Sy2; LINER | Bolton et al. 2012; Khachikian & Weedman 1974 |
| dwarf / luminous | M_B = g + 0.313(g−r) + 0.227 − DM(z), 0.003 < z < 0.1: dwarf if M_B > −16; luminous if < −21 | Tammann 1994; Lupton 2005 SDSS→Johnson; flat ΛCDM H0 = 70, Ωm = 0.3 |
| interacting / pair / group / cluster / BCG / LSB / radio galaxy | SIMBAD object type (IG, PaG, GiP, GiG, GiC, BiC, LSB, rG) | Wenger et al. 2000 |
| radio-loud AGN candidate | radio detection in a quiescent galaxy | Best & Heckman 2012 |
| X-ray source | Chandra / XMM / eROSITA counterpart | |
| edge-on / face-on | SGA b/a ≤ 0.3 / ≥ 0.85; inclination from cos²i = (q² − q0²)/(1 − q0²), q0 = 0.2 | Hubble 1926; Holmberg 1958 |
| spectroscopic redshift | z and luminosity distance (flat ΛCDM) | |

NGC 4522: "galaxy in a group; edge-on galaxy (i ≈ 81°); z = 0.0077". Kenney et al.
(2004) give i ≈ 78° for this ram-pressure-stripped Virgo spiral.

Redshifts for luminosities come only from spectra: SDSS, DESI and LAMOST,
or an NED redshift not flagged photometric. SIMBAD rvz_redshift is not used,
because its source is unknown. In the first COSMOS run it produced 30
"dwarf galaxies" with M_B ≈ −4 to −6. A value M_B > −10 (fainter than any
galaxy seen beyond the Local Group) means a wrong redshift or association,
and no luminosity label is given.

On the SDSS test split, green-valley galaxies are 30 with no strong lines,
5 AGN and 2 star-forming. This matches the green valley's transitional,
AGN-rich nature (Salim 2014), so the label is reported but not scored.

### QSO
| attribute | rule | basis |
|---|---|---|
| quasar vs Seyfert luminosity | M_i(z=2) with K(z) = −1.25 log10((1+z)/3) (α_ν = −0.5); quasar when M_i(z=0) = M_i(z=2) + 0.596 < −22 | Richards et al. 2006; Schneider et al. 2010 |
| BL Lac / blazar | SIMBAD BLL / Bla | |
| obscured (red) quasar candidate | R − W2 > 6.1 (Vega), R = r − 0.1837(g−r) − 0.0971 | Hickox et al. 2007 (≈ 80 % reliable); Lupton 2005 |
| very-high-redshift quasar | spectroscopic z ≥ 5 | Fan et al. 2001, 2006 |

Benchmark counts:
* Obscured-quasar candidates: 9 / 644 SDSS-test quasars, 56 / 1595 DESI
  quasars. DESI goes fainter and redder.
* Metal-poor star candidates (SDSS test, 75): their kinematics are halo 14,
  thick disc 12 and thin disc 2, as expected for metal-poor stars.

Check: 87 % of SDSS and 93 % of DESI spectroscopic quasars come out at
quasar luminosity.

## Large galaxies
Hosts made by `v2/host_groups.py` inherit the nucleus SDSS spectrum, the
redshift and the SIMBAD type of their identity/nucleus entries. Their
sub-class is computed after grouping. NGC 4522 → "Star-forming galaxy
(large, resolved)", from its nucleus spectrum (SDSS STARFORMING).

## From paper (`Classifier/literature.py`)
Objects that the catalogue data leave UNKNOWN show what the literature
calls them, as `from paper: <class>` with status `FROM_PAPER`. The primary
class stays UNKNOWN, so the classifier's accuracy is not mixed with
literature labels.

Sources, in order:

1. Paper catalogues that the pipeline cross-matches. Each is the product of
   one publication:
   * Suh 2021 AGB, 2021ApJS..256...43S
   * HASH PN, 2016JPhCS.728c2008P
   * ATNF pulsars, 2005AJ....129.1993M
   * Asiago SN, 1999A&AS..139..531B
   * ASAS-SN SN, 2017MNRAS.464.2672H
2. SIMBAD object type. Curators assign it from the literature (Wenger et al.
   2000). It comes with the three papers that discuss the object most:
   `has_ref.obj_freq`, then the most recent (`Get_data/simbad.py`, TAP
   tables `basic`, `has_ref`, `ref`, `otypedef`).
3. NED preferred type and its number of references.

Types that only name the band of a detection are marked "(detection only)":
SIMBAD IR/X/Rad/UV/mR/cm/smm/Opt/?, and NED IrS/RadioS/UvS/XrayS/VisS. They
do not say what the object is.

Output columns: `paper_class`, `paper_source`, `paper_refs` (bibcode (year)
title, '|' separated) and `paper_ads` (ADS links). They are filled for
every object. A classified object keeps its own sub-class, and its paper
class is shown alongside.

## Why UNKNOWN (`Classifier/unknown_reason.py`)
`unknown_reason` explains each abstention from the data:

* Inside a large galaxy.
* Conflicting evidence, listing the classes and rules.
* Two classes whose probabilities overlap, with both values.
* Single-survey limits:
  * SDSS beyond r = 22.2, its 95 % point-source completeness (York et al.
    2000; Stoughton et al. 2002).
  * Legacy Surveys S/N < 10, where Tractor morphology is not used (Dey et al.
    2019).
  * Pan-STARRS1 rows without a valid mean PSF magnitude.

## AGB chemistry: carbon (C-rich) and O-rich silicate AGB stars (2.5.0, calibrated 2.5.3)
After third dredge-up, AGB stars are either:
- **O-rich** (C/O < 1): M-type spectra, silicate dust with the 9.7 µm feature.
- **C-rich** (C/O > 1): carbon stars, with amorphous-carbon and SiC dust.

**S stars** (C/O ≈ 1) lie between the two. Separating them traces the third
dredge-up and makes carbon stars and dusty O-rich ("silicate") stars good AGB
markers. `Classifier/subclass.py` `agb_chemistry()` tries the following
evidence in order and stops at the first that applies.

| Order | Evidence | Rule | Source |
|---|---|---|---|
| 1 | SIMBAD spectral type C… (C-N, C-R, C-J, C-H) or type C* → carbon; S, MS or SC, or type S* → S star | `SIMBAD_CSTAR` / `SIMBAD_SSTAR` | Wenger et al. 2000 (curated literature types) |
| 2 | Suh (2021) catalogue membership (OAGB/CAGB tables) | `SUH2021` | Suh 2021, ApJS 256, 43 |
| 3 | AGB candidates only: logistic models (`agb_chemistry_model.json`, below) on W_RP − W_KJ, Ks − W3, Gaia DR3 LPV `is_cstar`, J − Ks and WISE colours. Here W_RP = G_RP − 1.3 (G_BP − G_RP) and W_KJ = Ks − 0.686 (J − Ks). Within 0.15 of p = 0.5 → "chemistry uncertain" (`STAR:?:AGB`) | `AGB_GAIA_2MASS_WISE_CSTAR`, `AGB_GAIA_2MASS_CSTAR`, `AGB_GAIA_2MASS`, `AGB_NIR_MIR` | Lebzelter et al. 2018, A&A 616, L13 (ΔW); Lebzelter et al. 2023 (`is_cstar`); calibrated on Suh 2021 + GCVS |
| 4 | AGB candidate lacking the model inputs, with Gaia DR3 LPV `is_cstar` = 1 inside its reliability window (G_BP < 19, 7 < median_delta_wl_rp < 11) → carbon (C precision 0.977 on the Suh stars) | `GAIA_LPV_CSTAR` | Lebzelter et al. 2023 (Gaia DR3 LPV catalogue) |

**Photometric models.**

The 2.5.0 rules used published single cuts:
- ΔW ≥ 0.9 → C-rich (Mowlavi et al. 2019; ≥ 1.7 "extreme", Abia et al. 2020);
- the AllWISE line W1−W2 = 2.35 (W3−W4) − 1.24 (Lian et al. 2014).

On the Suh (2021) stars, which are mostly dust-obscured Galactic AGB stars,
these cuts scored only 68.5 % and 75.4 %. In 2.5.3 they were replaced by
logistic models fitted on Suh.

Version 2.6.0 refits the models on two truth sets:
- **Suh (2021):** IR-selected and dusty.
- **GCVS LPVs with literature spectral types** (Samus et al. 2017;
  `benchmark/build_agb_gcvs_truth.py`): 5,699 M → O-rich and 792 C/R/N → C-rich,
  mostly dust-free.

Why the refit was needed: the Suh-only models called 60 % of 23,969 field
Gaia LPVs carbon-rich (`benchmark/evaluate_agb_contamination.py`), because in
that set "little dust" meant "carbon".

How the cascade is built:
- AllWISE magnitudes brighter than the saturation limits (W1 8.0, W2 6.7,
  W3 3.8, W4 −0.4; Cutri et al. 2012) are masked. 61 % of the GCVS stars are
  saturated in W3.
- A star uses the first model whose inputs it has.
- The fit is on a random half (seed 42) and the scores are on the other half
  (7,567 stars; `benchmark/fit_agb_chemistry.py`):

Since 2.17.0, `is_cstar` enters the models only inside the reliability window Lebzelter et al. (2023) give: G_BP < 19 and 7 < median_delta_wl_rp < 11 (`gaia_lpv_cstar`, below). The models were refitted with this gated flag. Before → after:

| Model | Features | Decided / n | Accuracy |
|---|---|---|---|
| `GAIA_2MASS_WISE_CSTAR` | ΔW, Ks − W3, `is_cstar` | 3760 / 3761 | 96.0 → 97.1 % |
| `GAIA_2MASS_CSTAR` | ΔW, J − Ks, `is_cstar` | 2027 / 2042 | 96.9 → 98.5 % |
| `GAIA_2MASS` | ΔW, J − Ks | 614 / 1346 | 79.0 % |
| `NIR_MIR` | J − Ks, Ks − W3, W1 − W2, W3 − W4 | 26 / 28 | 88.5 % |

All models together:
- Coverage: 83 → 84.9 %.
- Accuracy: 94.6 → **95.8 %** (Suh 93.1 %, GCVS 98.7 %).
- C-rich: precision 0.87 → 0.919, recall 0.887.
- O-rich: precision 0.968, recall 0.978.

- **Dropped model:** ΔW + Ks − W3 without the Gaia flag scored 73.8 %, and
  64 % with a wider abstain band. Dusty O-rich stars and dust-free stars
  overlap there, so the model is not used.
- **Field LPVs:**
  - The predicted C fraction is 3.3 % (25.7 % before the 2.17.0 gate),
    against 24.4 % raw Gaia flags. LAMOST spectra give 3.4 %, so the raw
    flags of faint stars near the plane were mostly spurious, as Lebzelter
    et al. warned.
  - Above the RGB tip with a good parallax: 232 O-rich and 13 C-rich.
- **Independent spectra (2.6.2):** 29 field LPVs have LAMOST C or M spectral types (1 carbon). The models got all 26 decided stars right, with predicted C 3.8 % vs true 3.4 %. That LAMOST-covered subsample is bright and away from the plane. The 25.7 % C fraction of the whole field sample comes from faint stars near the plane and is still not checked independently.
- **Gaia `is_cstar` reliability:**
  - Good for the bright GCVS stars: 31 of 4,706 O-rich flagged.
  - Weaker on the fainter Suh stars: 519 of 4,442 O-rich flagged.
  - Used alone, the flag is right 76.2 % of the time on the Suh stars.
    With G_BP < 19 it is 97.7 % (1,600 C of 1,638); with G_BP ≥ 19 it is
    11.3 %. Since 2.17.0 the flag counts only with G_BP < 19 and
    7 < median_delta_wl_rp < 11 (Lebzelter et al. 2023, quoted by Sanders &
    Matsunaga 2023), and it gets confidence 0.977 when used alone.
- **Extinction guard (2.17.0):** toward the bulge (|b| < 5°, |l| < 30°),
  reddened O-rich LPVs look carbon-rich in ΔW (Sanders & Matsunaga 2023).
  Photometric C calls there were 33 % correct (98 of 294 on Suh + GCVS);
  elsewhere they are 96–99 %. These calls are withheld ("chemistry
  uncertain"), which raises C precision from 0.912 to 0.981 (all truth
  stars).

- **AGB-candidate gate:** the photometric models (row 3) are applied only to
  AGB candidates. A candidate is a long-period or Mira variable (variability
  axis, Gaia SOS LPV), has AGB physical class (Suh 2021, SIMBAD AGB*), or
  has a SIMBAD type among C*, S*, Mi*, LP*, OH* and pA*. Without the gate
  the colours mean nothing: on the SDSS benchmark stars, 200 of 257 with
  J−Ks ≥ 1 already have ΔW ≥ 0.9, and L dwarfs reach ΔW ≈ 3.
- **Silicate tag:** an O-rich AGB star with a mid-IR dust excess,
  Ks − W3 > 1.0, is labelled "O-rich AGB star with silicate dust". The
  stellar photosphere has Ks − W3 ≈ 0.
- **Carbon stars that are not AGB:** a SIMBAD carbon type without AGB
  evidence is labelled "Carbon star" with code `STAR:C:?`, not as an AGB
  star. These are dwarf carbon and CH stars.
- **Codes:**
  - `STAR:C:AGB`: carbon AGB star
  - `STAR:M:AGB`: O-rich AGB star
  - `STAR:S:AGB`: S-type AGB star
  - `STAR:?:AGB`: AGB star, chemistry uncertain
- **Below the RGB tip (2.6.0):** with a good parallax and −6.2 < M_Ks ≤ −1
  (2MASS RGB tip; Nikolaev & Weinberg 2000) an LPV may be a red giant or an
  early-AGB star; it is named "O-rich red giant / Carbon giant (RGB or early
  AGB)" with code `STAR:<M|C>:III`. 340 field LPVs with good parallaxes lie
  there, 254 above the tip.
- **Non-AGB vetoes (2.6.0):** a star is not called AGB when
  - its Gaia parallax is good (S/N ≥ 5, RUWE < 1.4) and it is fainter than
    the red clump, M_Ks > −1 (red clump M_Ks = −1.61; Alves 2000, Hawkins
    et al. 2017). In the Suh (2021) truth set this removes 263 "C-AGB"
    stars (none an LPV, median G − Ks 2.2 vs 5.4) and no O-AGB star;
  - a spectroscopic log g (LAMOST LASP or clean-flag Gaia GSP-Spec) is
    above 3.5;
  - (until 2.6.2 also: Gaia ESP-ELS calls it a T Tauri or Herbig Ae/Be
    star. Removed: the ESP-ELS "T Tauri" class matched a young-star type in
    SIMBAD for only 2 %, and most are AGB-type variables; see
    `LITERATURE_SPECTROSCOPY.md` §3.)
  A carbon star caught by a veto is "Dwarf carbon star (dC)" (`STAR:C:V`)
  if M_G > 5 (Li et al. 2024; Green 2013) and "Carbon star" (`STAR:C:?`,
  CH / sub-giant carbon star) otherwise. SDSS and LAMOST carbon spectra
  (rule `SDSS_CSTAR` / `LAMOST_CSTAR`) enter the chemistry after SIMBAD;
  SDSS "CarbonWD" is a DQ white dwarf. Spectroscopic criteria in general:
  `LITERATURE_SPECTROSCOPY.md`.
- **Validation (2.5.3):** see the model table above. The truth set is
  `benchmark/agb_truth/agb_chemistry_truth.csv.gz`, built by
  `benchmark/build_agb_chemistry_truth.py` (GitHub Actions, VizieR cone
  search): Suh 2021 O-AGB (5,301) and C-AGB (3,576) stars with Gaia DR3,
  2MASS, AllWISE and Gaia DR3 LPV photometry. 98.4 % of the O-AGB stars have
  Ks − W3 > 1.0, which supports the silicate threshold.

## New targets examined in 2.28.0

Candidates came from the gaps of the sub-class benchmark (`evaluate_subclass.py`): faint white dwarfs (DESI WDs typed as WD: 18 %), galaxy activity of faint galaxies (photometric rules reached 3.6 % of DESI benchmark galaxies) and quasar redshift class without a spectrum. Each criterion was taken from the literature and measured before adoption.

| Target | Criterion (source) | Measurement | Decision |
|---|---|---|---|
| QSO z < 2.1 without a spectrum (`PHOT_Z_KNN`) | kNN (k = 31) in dereddened LS g−r, r−z, z−W1, W1−W2 (errors ≤ 0.2) + r/4; reference = DESI DR1 quasars of the fusion training set (`benchmark/build_qso_photoz_reference.py`). Quasar colours vs z: Richards et al. 2001 (AJ 121, 2308); grzW photo-z 72 % within 0.1(1+z): Yang et al. 2017 (AJ 154, 269); kNN photo-z: Ball et al. 2008 (ApJ 683, 12). Claimed when P(z ≥ 2.1) ≤ 0.2 | purity 0.958 (DESI external, 834 QSOs, 70 % of its z < 2.1 QSOs) and 0.994 (SDSS test, 81 %); |Δz|/(1+z) < 0.1 for 70 % (cf. Yang+2017 72 %) | **adopted** (low-z only) |
| QSO z ≥ 2.1 without a spectrum | same kNN, P ≥ 0.7–0.8; no published grzW cut with a z > 2.1 purity (Chaussidon et al. 2023, ApJ 944, 107: one random forest for all z; Yèche et al. 2020 colour cuts) | purity 0.88–0.91 on DESI but 0.40–0.65 on SDSS (prior dependent); z ~ 2.8 quasars sit on the stellar locus (Yang+2017) | not adopted |
| Faint star-forming galaxies (`LS_ELG`) | DESI ELG box, dereddened LS: g > 20, r−z > 0.15, g−r < 0.5(r−z) + 0.1 (Raichoor et al. 2023, AJ 165, 126, Table 2; [O II] emitters at 0.6 < z < 1.6); g-fibre < 24.1 not applied (no fibre fluxes) | truth: FastSpecFit EW([O II] 3726+3729) of 4,361 DESI benchmark galaxies (`benchmark/desi_galaxy_activity`, passive below 5 Å: Balogh et al. 1999, ApJ 527, 54; Dressler et al. 1999, ApJS 122, 51). 601/637 decided cases are emitters (0.943; 0.932 / 0.950 on the two sets); 152 more have EW ≥ 5 Å below 3σ (median 10.4 Å). Activity coverage of the DESI benchmark galaxies 3.6 → 21.6 % | **adopted**, last in the activity chain, precision 0.943 |
| Faint quiescent galaxies via the DESI LRG box | Zhou et al. 2023 (AJ 165, 58) Eqs. 1–2 | only 0.63 of LRG-box galaxies have EW([O II]) < 5 Å; the box is a stellar-mass selection (complete for log M* > 11.5), not a quiescence selection | not adopted |
| WD without a usable parallax, reduced proper motion | H_G = G + 5 log μ + 5 > 10 + 7(BP−RP), pm/σ > 10 (Gentile Fusillo et al. 2021, MNRAS 508, 3877, Sect. 2.3 — a pre-cut before their P_WD map); inclusive H_g line of Kilic et al. 2006 (AJ 131, 582) | where the parallax gate abstains: DESI 4 WD / 4 non-WD, SDSS 5 WD / 30 non-WD (halo A/BHB stars just above the line); Kilic line with offsets ≤ 50 % purity | not adopted |
| Hot WD from GALEX UV | FUV−NUV < −0.13 and NUV−r < 0.1, both errors ≤ 0.3 (Bianchi et al. 2011, MNRAS 411, 2770) | hot stars 96 % (as published) but WDs only ~50 % (B/A/BHB/sdB stars share the colours) | not adopted as WD |
| Gaia DSC vs HR-locus conflict | the veto of a WD-locus star with DSC star ≥ 0.8 (2.17.0) | conflicting cases are 22 WD / 20 non-WD (SDSS), 9 / 10 (DESI) | kept |

The faint DESI white dwarfs without a WD label (47 of 89) have no Gaia counterpart at all; no published grz white-dwarf cut with a measured purity exists (hot WDs overlap z ≈ 2–3 quasars and BHB / sdB stars in grz), so they stay unclassified.
