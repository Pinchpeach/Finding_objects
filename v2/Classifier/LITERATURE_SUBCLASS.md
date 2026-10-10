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
  * V: ΔM > −1.0. Unresolved equal-mass binaries lie ≤ 0.75 mag above the
    main sequence (Hurley & Tout 1998); metallicity and age spread add about
    0.3 mag.
  * IV: −2.5 < ΔM ≤ −1.0, and only blueward of (BP−RP)₀ = 1.3, where a
    subgiant branch exists.
  * III: otherwise.
* Fallback: the Ciardi et al. (2010/2011) giant boundary on GSP-Phot
  log g, as used for Kepler targets:
  * log g ≤ 5.2 − 2.8×10⁻⁴ Teff for 4250 < Teff < 6000 K;
  * log g ≤ 4.0 below 4250 K;
  * log g ≤ 3.5 above 6000 K.
* The physical axis (Gaia FLAME RGB) forces III. The white-dwarf route
  (Gentile Fusillo et al. 2021 locus + Gaia DSC) overrides the spectral type.
* Carbon stars, CVs and WD subtypes are taken only from LAMOST/SDSS spectra.

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
1. SDSS spectrum subclass (Bolton et al. 2012, AJ 144, 144).
   * STARFORMING / AGN come from the BPT [O III]/Hβ vs [N II]/Hα diagram
     (Baldwin, Phillips & Terlevich 1981; Kauffmann et al. 2003; Kewley et
     al. 2001).
   * STARBURST means EW(Hα) > 50 Å. BROADLINE is treated as AGN.
2. SIMBAD types: Sy1/Sy2/SyG/LIN/AGN → AGN; SBG → starburst; H2G/EmG/bCG →
   star-forming.
3. Mid-IR AGN: W1−W2 ≥ 0.8 with W2 < 15.05 (Vega; Stern et al. 2012, ApJ
   753, 30).
4. WISE W2−W3 (Jarrett et al. 2017, ApJ 836, 182; 2019, ApJS 245, 25):
   * star-forming discs > 3.0, spheroids < 1.5, intermediate discs in
     between (no label);
   * applied when W3 S/N ≥ 5 (σ < 0.2 mag);
   * when AllWISE gives only a W3 upper limit, the true colour is bluer than
     W2 − W3_lim, so W2 − W3_lim < 1.5 also implies a spheroid.
5. GALEX (NUV−r)₀ > 5 → quiescent (Kaviraj et al. 2007; red sequence of
   Wyder et al. 2007). Uses R_NUV ≈ 8.2.

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
| metal-poor candidate | GSP-Phot [M/H] < −1, G < 17 | Beers & Christlieb 2005. GSP-Phot [M/H] is only indicative (Andrae et al. 2023) |

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
