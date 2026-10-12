# Spectroscopic classification criteria — literature basis

This file collects the literature for classifying objects with **spectroscopic
data** and records which criteria the v2 pipeline implements. The pipeline does
not fit raw spectra. It uses the products that spectroscopic surveys publish
from their spectra: classes and template subclasses, line fluxes and
equivalent widths, spectral indices, and atmospheric parameters.

Status codes:
- **used**: implemented in `Classifier/subclass.py`.
- **data**: the pipeline collects the product, but no rule uses it yet.
- **ref**: background or future work; the product is not collected.

Validation results are in the "Validation" sections and in `CHANGELOG.md`.

## 1. Spectroscopic data products in the pipeline

| Product | Collector (`Get_data/`) | Content | Reference |
|---|---|---|---|
| SDSS DR18 SpecObj | `sdss_spectroscopy.py` | class (STAR/GALAXY/QSO), template subclass, z | Bolton et al. 2012, AJ 144, 144 |
| SDSS galaxy emission lines (2.6.0) | `sdss_spectroscopy.py` | Hα, Hβ, [O III] 5007, [N II] 6584 flux and EW from the Portsmouth fits (SDSS-I/II and BOSS; 100 % of the benchmark galaxies), else MPA-JHU (SDSS-I/II only; 1.6 %); Dn4000 from MPA-JHU | Thomas et al. 2013, MNRAS 431, 1383 (Portsmouth); Brinchmann et al. 2004, MNRAS 351, 1151; Kauffmann et al. 2003, MNRAS 341, 33; Tremonti et al. 2004, ApJ 613, 898 |
| LAMOST DR5 | `lamost_spectroscopy.py` | class, subclass, z (LASP Teff, log g, [Fe/H] for AFGK stars) | Luo et al. 2015, RAA 15, 1095; Wu et al. 2011, RAA 11, 924 |
| DESI DR1 redshift catalogue | `desi_spectroscopy.py` | spectral type, z | Guy et al. 2023, AJ 165, 144; DESI Collaboration 2025 (DR1) |
| DESI DR1 galaxy emission lines (2.7.0) | `desi_fastspec.py` | Hα, Hβ, [O III] 5007, [N II] 6584 flux and inverse variance, EW(Hα), broad Hα; FastSpecFit fits as carried by the DESI DR1 AGN/galaxy VAC (Data Lab `desi_dr1.agngal`; the full FastSpecFit VAC is not cone-searchable). Used only where no SDSS lines exist | Moustakas et al. 2023 (FastSpecFit, ASCL 2308.005); DESI Collaboration 2025 (DR1) |
| Gaia DR3 astrophysical parameters | `gaia_dr3.py` | GSP-Phot (BP/RP) Teff, log g, [M/H]; DSC class probabilities; GSP-Spec (RVS) and ESP-ELS (emission-line class), see §3 | Creevey et al. 2023, A&A 674, A26; Andrae et al. 2023, A&A 674, A27; Recio-Blanco et al. 2023, A&A 674, A29 |
| Gaia DR3 LPV RP-spectrum C-star flag | `gaia_dr3_variability_sos_vizier.py` | `is_cstar` from the C2/CN band shape of RP spectra | Lebzelter et al. 2023, A&A 674, A15 |
| Acker PN spectroscopy | `pn_spectroscopy.py` | PN line intensities | Acker et al. 1992 (Strasbourg–ESO PN catalogue) |

## 2. Stars

### 2.1 Spectral type (temperature class)

| Criterion | Status | Reference |
|---|---|---|
| MK system: spectral type from line ratios; luminosity class from pressure-sensitive lines | used (SIMBAD MK types) | Morgan, Keenan & Kellman 1943; Gray & Corbally 2009, *Stellar Spectral Classification* |
| SDSS template subclass (Elodie/SDSS templates); K/M agree with MK to about 1 subtype, A/F offset | used | Bolton et al. 2012 |
| LAMOST pipeline subclass | used | Luo et al. 2015 |
| Teff → spectral type on the dwarf scale | used (Gaia Teff) | Pecaut & Mamajek 2013, ApJS 208, 9 |

### 2.2 Luminosity class and evolutionary state from spectroscopic log g

Spectroscopic log g separates dwarfs, subgiants and giants without a parallax.
- **Giant boundary:** log g ≤ 4.0 for Teff ≤ 4250 K, 5.2 − 2.8×10⁻⁴ Teff for 4250–6000 K, and 3.5 above 6000 K (Ciardi et al. 2011, AJ 141, 108). Already used with Gaia GSP-Phot log g.
- **LAMOST LASP:** typical errors are 110 K in Teff, 0.20 dex in log g and 0.10 dex in [Fe/H] for late-A to K stars (Luo et al. 2015; Gao et al. 2015).
- **Gaia GSP-Spec (RVS):**
  - Quality is set by `flags_gspspec`. The first 13 characters equal to zero define the "golden sample" (Gaia Collaboration, Creevey et al. 2023, A&A 674, A39).
  - Raw log g is biased low. Recio-Blanco et al. 2023 give polynomial calibrations.
  - The DR3 validation paper advises against GSP-Spec log g for AGB stars (Babusiaux et al. 2023, A&A 674, A32).
- **Metallicity:** [Fe/H] < −1 metal-poor, < −2 very metal-poor, < −3 extremely metal-poor (Beers & Christlieb 2005, ARA&A 43, 531). GSP-Phot [M/H] is not used for the metal-poor tag since 2.6.2 (precision 0.15 against APOGEE; table below). Spectroscopic [Fe/H] from LAMOST, or calibrated GSP-Spec [M/H] (Recio-Blanco et al. 2023, Eq. 2; since 2.17.0), is used directly.

### 2.2.1 Validation on bright stars (2.6.2, APOGEE DR17)

Data: 8,196 APOGEE DR17 stars (S/N > 100, 24 RA slices).

- **Truth:** the luminosity class comes from APOGEE log g, using the Ciardi boundary.
- **Luminosity-class rules:**

  | Rule | n | Accuracy | Giant recall | Giant precision |
  |---|---|---|---|---|
  | Gaia GSP-Spec (flags 0) | 3,078 | 97.8 % | 98.5 % | 97.9 % |
  | LAMOST LASP | 1,880 | 98.3 % | 97.5 % | 99.2 % |
  | Gaia GSP-Phot | 5,331 | 96.9 % | 96.1 % | 98.4 % |

- **Metal-poor ([Fe/H] < −1):**

  | Source | Precision | Recall | Note |
  |---|---|---|---|
  | GSP-Spec | 0.78 | 0.89 | 32 flagged |
  | LAMOST | 0.98 | 0.88 | |
  | GSP-Phot | 0.15 | 0.14 | 0.0–0.25 at any cut, so no longer used |

- **GSP-Spec flags:** VizieR serves the 41-character `flags_gspspec` as a number, which drops leading zeros. A CSV round trip does the same. The collector therefore stores the per-parameter decision (`gspspec_<par>_ok`).

### 2.2.2 Validation on faint benchmark stars (2.6.0)

Data: 388 benchmark stars with LAMOST LASP parameters.

- **Luminosity class:**
  - The LAMOST log g class agrees with the Gaia parallax CMD class for 219 of 221 dwarfs.
  - It gives a class to 152 stars without a usable parallax.
  - Gaia GSP-Phot log g finds only 1 of the 22 LAMOST giants.
- **Metallicity:**
  - LAMOST finds 104 metal-poor stars ([Fe/H] < −1); GSP-Phot [M/H] flags 156.
  - Both agree on 91, so 65 GSP-Phot flags are not confirmed by LAMOST.
  - The spectroscopic [Fe/H] therefore decides when present.
- **Not measured on the benchmark:**
  - Gaia GSP-Spec and ESP-ELS have no values for these faint benchmark stars (GSP-Spec covers G_RVS ≲ 14).
  - Their literature validation is quoted above.

### 2.3 Carbon, S and AGB stars

| Criterion | Status | Reference |
|---|---|---|
| Revised MK carbon classes C-R, C-N, C-J, C-H | used (SIMBAD types) | Keenan 1993, PASP 105, 905; Barnbaum, Stone & Keenan 1996, ApJS 105, 419 |
| S stars (ZrO bands), MS and SC types | used (SIMBAD types) | Keenan & Boeshaar 1980, ApJS 43, 379 |
| SDSS / LAMOST carbon templates (C2, CN bands); SDSS "CarbonWD" is a DQ white dwarf, not a carbon star | used (2.6.0) | Bolton et al. 2012; Green 2013, ApJ 765, 12; Li et al. 2018, ApJS 234, 31 |
| Gaia RP-spectrum C-star flag | used | Lebzelter et al. 2023 |
| Dwarf carbon stars (dC): main-sequence C stars from mass transfer. Screen M_G > 5 | used (2.6.0) | Green 2013 (dC M ≈ 6.5–10.5, about 69 % of SDSS carbon stars); Li et al. 2024, ApJS 271, 12 (LAMOST DR7 carbon stars, M_G > 5); Roulston et al. 2025, ApJ 982, 184 |
| AGB stars are brighter than the red clump (M_Ks = −1.61) | used (2.6.0 veto) | Alves 2000, ApJ 539, 732; Hawkins et al. 2017, MNRAS 471, 722 |
| RGB tip M_Ks ≈ −6.2 (2MASS LMC tip Ks = 12.3 at μ = 18.5) | ref (diagnostic) | Nikolaev & Weinberg 2000, ApJ 542, 804; Cioni et al. 2000, A&A 359, 601 |
| AGB luminosity limit M_bol ≈ −7.1 (core-mass–luminosity relation); red supergiants mostly brighter, with overlap to −8 | ref (diagnostic) | Paczyński 1970, Acta Astron. 20, 47; Wood, Bessell & Fox 1983, ApJ 272, 99; Wagenhuber & Groenewegen 1998, A&A 340, 183 |
| Gaia DR2 LPVs include YSOs (removable with parallax cuts) | ref (contamination) | Mowlavi et al. 2018, A&A 618, A58 |

### 2.4 Emission-line stars (Gaia ESP-ELS)

- **Classes:** ESP-ELS classifies Gaia BP/RP spectra with Hα emission into Be stars, Herbig Ae/Be stars, T Tauri stars, active M dwarfs, Wolf-Rayet WC and WN stars, and planetary nebulae (Creevey et al. 2023; Gaia DR3 documentation §11.3.7).
- **Size and precision:**
  - 57 511 stars are classified.
  - A class flag ≤ 2 means probability > 0.5.
  - 96 % of known classical Be stars are labelled Be.
  - 229 of 443 known Wolf-Rayet stars were found, with 1 misassignment.
  - PNe are the hardest class.
  - Weak Hα emitters are missed.
- **Validation (2.6.2, `benchmark/evaluate_bright.py`):** 4,000 ESP-ELS stars were compared with SIMBAD types. The query returned 1,500 Be, 1,500 T Tauri and 1,000 Herbig; no other labels.

  | ESP-ELS label | SIMBAD class match | Notes |
  |---|---|---|
  | TTauri | 2 % | Most are long-period variables (LP?/LP*) |
  | HerbigStar | 30 % | |
  | beStar | 27 % | 541 of 1,111 are generic emission-line stars (Em*) |

  Requiring flag ≤ 2 does not help (9–44 %).
- **Use in the pipeline (2.6.2):** only the emission itself is used, as the tag "H-alpha emission-line star". The class label changes nothing, and it no longer vetoes the AGB label: T Tauri-labelled stars are mostly AGB-type variables.

### 2.5 White dwarfs and cataclysmic variables

SDSS and LAMOST WD and CV templates (Bolton et al. 2012; Kleinman et al. 2013,
ApJS 204, 5) are used as before. WD subtypes are listed in
`WD_SUBTYPE_VALIDATION.md`.

## 3. Galaxies

| Criterion | Status | Reference |
|---|---|---|
| SDSS subclass: STARFORMING / AGN from the BPT diagram with all lines at 10σ; STARBURST for EW(Hα) > 50 Å; BROADLINE | used | Bolton et al. 2012; Brinchmann et al. 2004 |
| BPT diagram [O III]/Hβ vs [N II]/Hα | used (2.6.0, S/N ≥ 3) | Baldwin, Phillips & Terlevich 1981, PASP 93, 5 |
| Maximum-starburst line y = 0.61/(x − 0.47) + 1.19 (AGN above) | used | Kewley et al. 2001, ApJ 556, 121 |
| Empirical star-forming line y = 0.61/(x − 0.05) + 1.3 (composite between the two) | used | Kauffmann et al. 2003, MNRAS 346, 1055 |
| Seyfert / LINER split on the [N II] diagram: y = 1.05x + 0.45 | used (basis text) | Schawinski et al. 2007, MNRAS 382, 1415 |
| Seyfert / LINER with [S II] and [O I] | ref ([S II], [O I] not collected) | Kewley et al. 2006, MNRAS 372, 961 |
| WHAN: EW(Hα) < 3 Å "retired" (ionised by old stars, not an AGN), < 0.5 Å passive; EW 3–6 Å weak AGN. Applied before the BPT | used (2.6.0) | Cid Fernandes et al. 2010, MNRAS 403, 1036; 2011, MNRAS 413, 1687 |
| [N II]/Hα alone when Hβ / [O III] are weak: x < −0.4 star-forming, −0.4 to −0.2 composite, > −0.2 AGN | used (2.6.0) | Stasińska et al. 2006, MNRAS 371, 972 |
| 4000 Å break Dn4000 (narrow index); bimodal, old populations at Dn4000 ≳ 1.6 | used (2.6.0, only without Hα) | Balogh et al. 1999, ApJ 527, 54; Kauffmann et al. 2003, MNRAS 341, 33 |
| Broad Balmer lines (FWHM ≳ 1200 km/s) → type-1 AGN | used through the SDSS BROADLINE subclass | Hao et al. 2005, AJ 129, 1783 |
| Hδ_A, post-starburst (E+A) | ref | Worthey & Ottaviani 1997; Goto 2007 |

### 3.1 Validation (2.6.0, `benchmark/evaluate_spectro.py`)

Data: 3,333 SDSS benchmark galaxies with Portsmouth lines
(`benchmark/spectro_truth/`).

- **Coverage:** 98.6 % get an activity class from the lines.
  - WHAN: 2,325.
  - BPT: 961.
- **Against the SDSS pipeline subclass** (all lines at 10σ):

  | SDSS subclass | line rules |
  |---|---|
  | STAR_FORMING (1,066) | 812 SF, 217 composite, 19 AGN, 12 retired |
  | AGN (72) | 51 AGN, 9 composite, 10 retired |

  - The composites are the Kauffmann–Kewley zone, which the simpler SDSS line counts as star-forming.
  - The retired ones have EW(Hα) < 3 Å.
  - The pipeline subclass keeps precedence in the classifier.
- **The BPT rule reproduces the Portsmouth BPT label for 95.1 %.**
- **Galaxies without an SDSS subclass** (2,128; 2,089 labelled). Against the WISE colour, which is independent of the spectrum:

  | label | n | median W2 − W3 | W2 − W3 > 3 |
  |---|---|---|---|
  | quiescent (retired / passive) | 1,667 | 1.92 | 2 % |
  | star-forming | 129 | 3.41 | 81 % |
  | composite | 213 | 3.04 | 53 % |
  | AGN | 80 | 2.56 | 20 % |

- **Change found in validation:** plain WHAN called 104 SDSS star-forming galaxies AGN. 96 of them are star-forming or composite in the Portsmouth BPT. The Stasińska et al. (2006) composite zone reduces this to 19.

### 3.2 DESI FastSpecFit lines (2.7.0, `benchmark/evaluate_desi_lines.py`)

The same rules (WHAN, BPT, [N II]/Hα, rule names `DESI_*`) run on DESI
lines when a galaxy has no SDSS line measurement. Lines with zero inverse
variance (outside 3,600–9,800 Å, e.g. Hα at z > 0.49) are left empty, so
"not measured" never reads as "no emission". EW([N II]) is not in the table,
so the WHAN "passive" sub-case is not reachable from DESI (retired still is).

Check on 3,492 galaxies with both a DESI DR1 and an SDSS spectrum
(Data Lab DESI × SDSS DR17 1.5″ crossmatch, z < 0.3, median z 0.12):

- **Coverage:** SDSS lines decide 2,592, DESI 2,864; 691 only by DESI.
- **Agreement where both decide (2,173):** 80.7 % exact, 94.4 % within
  the neighbouring class on the SF – composite – AGN sequence. BPT
  decisions agree 86.6 %, WHAN / [N II]–Hα decisions 76.8 %.

  | SDSS → DESI | AGN | composite | quiescent | SF |
  |---|---:|---:|---:|---:|
  | AGN (117) | 81 | 10 | 26 | 0 |
  | composite (375) | 60 | 205 | 63 | 47 |
  | quiescent (714) | 8 | 4 | 701 | 1 |
  | SF (967) | 9 | 181 | 11 | 766 |

- **Systematic:** DESI log [N II]/Hα is +0.053 dex higher than SDSS
  (1,653 galaxies, scatter 0.076 dex); [O III]/Hβ agrees (+0.005 dex);
  DESI EW(Hα) is 0.82 × SDSS. This is what a smaller aperture gives: the
  DESI fibre (1.5″) samples more of the bulge than the SDSS fibre (3″;
  BOSS 2″),
  with higher [N II]/Hα and more old-star continuum (Kewley, Jansen &
  Geller 2005, PASP 117, 227). Hence the SF → composite shift.
- **No correction applied.** Removing the measured offsets raises agreement
  only to 83.4 % (in-sample), the thresholds are the literature ones, and
  the aperture difference is physical (the DESI spectrum describes the
  central region). SDSS lines keep precedence when both exist.

## 4. Quasars

| Criterion | Status | Reference |
|---|---|---|
| Spectroscopic class QSO and redshift (SDSS, DESI, LAMOST) | used | Bolton et al. 2012; Lyke et al. 2020, ApJS 250, 8 (DR16Q) |
| High-z quasar: z ≥ 2.1 (Lyα forest in the optical); very high z ≥ 5 | used | Ross et al. 2012; Fan et al. 2001, 2006 |
| Broad absorption-line (BAL) quasars, BALnicity | ref (needs DR16Q BAL flags) | Weymann et al. 1991, ApJ 373, 23 |

## 5. Planetary nebulae

A counterpart in the Strasbourg–ESO PN catalogue (Acker et al. 1992) is
identity evidence, like HASH (2.18.0). The old "≥ 2 positive lines" test
only checked that data existed. The line ratios used against PN mimics,
[O III] 5007 / Hα and [S II] / Hα (Frew & Parker 2010, PASA 27, 129), are
**reported** in the evidence and not used as a veto: no threshold has been
measured on this pipeline's data. HASH entries are graded (Parker, Bojičić &
Frew 2016):
- True / Likely → PN.
- Possible → PN with status `HASH_POSSIBLE_PN`, calibrated separately.
- Mimics, post-AGB stars and other non-PN entries → not PN.
