"""Second-stage (sub-class) classifier: literature criteria per coarse class.

Runs after the coarse STAR/GALAXY/QSO decision and the multi-axis
classifier. Each criterion is documented in ``LITERATURE_SUBCLASS.md`` with
its measured precision on the SDSS/DESI spectroscopic benchmark
(``v2/benchmark/evaluate_subclass.py``); that precision is reported as the
confidence of the rule that fired. Spectroscopic catalogue labels outrank
photometric criteria; when nothing applies the field stays empty
(``subclass_status`` says why) rather than guessing.

STAR
  * spectral type: SIMBAD (curated MK type) > LAMOST > SDSS spectrum
    subclass; otherwise the dereddened Gaia BP-RP, Legacy Surveys g-r or
    Pan-STARRS1 i-z mapped onto the Pecaut & Mamajek (2013) dwarf sequence
    (Mamajek table v2022.04.16, ``reference/mamajek_dwarf_sequence.csv``),
    then Gaia GSP-Phot Teff.
  * luminosity class: height above the main sequence in the Gaia CMD
    (parallax S/N >= 5): V (dwarf), IV (subgiant), III (giant); otherwise
    the Ciardi et al. (2010/2011) Teff-log g giant boundary on GSP-Phot.
  * white dwarfs come from the physical axis (Gentile Fusillo+2021 locus).
GALAXY
  * activity: SDSS spectral subclass (BPT, Bolton+2012) > SIMBAD type >
    WISE mid-IR AGN (W1-W2 >= 0.8, W2 < 15.05; Stern+2012) > WISE W2-W3
    (> 3 star-forming, < 1.5 quiescent; Jarrett+2017/2019) > GALEX NUV-r
    (> 5 quiescent; Kaviraj+2007).
  * light profile: Legacy Surveys DEV (de Vaucouleurs, early-type-like) /
    EXP (exponential disc); SDSS u-r >= 2.22 early type (Strateva+2001).
QSO
  * radio loudness R_i = 0.4 (m_i - t), t = -2.5 log10(F_1.4GHz / 3631 Jy);
    radio-loud when R_i > 1 (Ivezic et al. 2002).
  * redshift class from a spectroscopic redshift: z >= 2.1 (Ly-alpha forest
    in the optical; Ross et al. 2012) "high-z".
  * X-ray detection; SIMBAD Seyfert/blazar types.
"""
from __future__ import annotations
import math
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
LETTERS = "OBAFGKMLTY"
# Measured on the spectroscopic benchmark (evaluate_subclass.py); see
# LITERATURE_SUBCLASS.md.  Used as the reported confidence of each rule.
def _load_precision() -> dict[str, float]:
    import json
    try:
        return json.loads((ROOT / "subclass_rule_precision.json").read_text())["precision"]
    except (OSError, ValueError, KeyError):
        return {}


RULE_PRECISION: dict[str, float] = _load_precision()

# Casagrande & VandenBerg (2018, MNRAS 479, L102): Gaia extinction
# coefficients per E(B-V); E(BP-RP) = (3.374 - 2.035) E(B-V), A_G ~ 2.740 E(B-V).
E_BPRP_PER_EBV = 1.339
A_G_PER_EBV = 2.740
# Schlafly & Finkbeiner (2011) DECam g coefficient, used to recover E(B-V)
# from the Legacy Surveys mw_transmission_g column.
R_DECAM_G = 3.214
R_SDSS_U, R_SDSS_R = 4.239, 2.285

RADIO_14GHZ = (("first__Fint", 1.0), ("nvss__S1.4", 1.0))
# LoTSS 144 MHz and VLASS 3 GHz scaled to 1.4 GHz with alpha = -0.7 (S ~ nu^alpha),
# the canonical optically-thin synchrotron index (Condon 1992, ARA&A 30, 575).
RADIO_OTHER = ((("lotss_dr2__Stotal", "lotss_dr2__SpeakTot", "lotss_dr2__Total_flux", "lotss_dr2__Stot"), (1400 / 144) ** -0.7),
               (("vlass__Ftot", "vlass__Total_flux"), (1400 / 3000) ** -0.7))
XRAY_CATALOGS = ("Chandra CSC 2.0", "XMM 4XMM-DR13", "eROSITA eRASS1")

SIMBAD_GALAXY = {
    "Sy1": ("AGN", "Seyfert 1"), "Sy2": ("AGN", "Seyfert 2"), "SyG": ("AGN", "Seyfert"),
    "LIN": ("AGN", "LINER"), "AGN": ("AGN", "AGN"), "SBG": ("STARBURST", "starburst galaxy"),
    "H2G": ("STAR_FORMING", "HII galaxy"), "EmG": ("STAR_FORMING", "emission-line galaxy"),
    "bCG": ("STAR_FORMING", "blue compact galaxy"),
}
SIMBAD_QSO = {"BLL": "BL Lac", "Bla": "blazar", "Sy1": "Seyfert 1", "Sy2": "Seyfert 2", "QSO": "quasar", "LIN": "LINER"}


# ----------------------------------------------------------------- helpers
def _num(row, *keys):
    for k in keys:
        v = row.get(k)
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(x):
            return x
    return None


def _text(row, *keys):
    for k in keys:
        v = row.get(k)
        if v is None or (isinstance(v, float) and v != v):
            continue
        s = str(v).strip()
        if s and s.lower() not in {"nan", "none", "<na>"}:
            return s
    return None


def _catalogs(row):
    return set(str(row.get("catalogs") or "").split("|"))


def _mag(row, std_key, raw_flux_key=None, raw_mag_keys=(), offset=0.0):
    """AB magnitude from the harmonised ``std_mag__*`` column (Preprocess/units.py);
    falls back to the raw catalogue field when the row was not harmonised."""
    v = _num(row, std_key)
    if v is not None or std_key in row:          # harmonised: a missing value stays missing
        return v
    if raw_flux_key:
        return _ab_mag(_num(row, raw_flux_key))
    v = _num(row, *raw_mag_keys)
    return None if v is None or not 0 < v < 40 else v + offset    # PS1 -999 / SDSS -9999 sentinels


WISE_AB = {1: 2.699, 2: 3.339, 3: 5.174, 4: 6.620}     # units.WISE_AB (Jarrett+2011)


def _wise_vega(row, band):
    """WISE magnitude in the Vega system the WISE colour criteria are defined in."""
    v = _num(row, f"std_mag__wise_w{band}")
    if v is not None or f"std_mag__wise_w{band}" in row:
        return None if v is None else v - WISE_AB[band]
    v = _num(row, f"allwise__W{band}mag")
    return v if v is not None and 0 < v < 40 else None


def _ab_mag(flux_nmgy):
    return 22.5 - 2.5 * math.log10(flux_nmgy) if flux_nmgy and flux_nmgy > 0 else None


@lru_cache(maxsize=1)
def sequence() -> pd.DataFrame:
    ref = pd.read_csv(ROOT / "reference" / "mamajek_dwarf_sequence.csv")
    ref["num"] = ref.SpT.map(spt_number)
    return ref


def spt_number(spt) -> float:
    """'K3V' -> 53.0, 'M2.5' -> 62.5 (O=0 ... Y=90); NaN when not an MK type."""
    m = re.match(r"^\s*([OBAFGKMLTY])\s*(\d+(?:\.\d+)?)?", str(spt))
    if not m:
        return float("nan")
    sub = float(m.group(2)) if m.group(2) else 5.0
    if sub >= 10:                  # not an MK subtype ("M10", "Y10" would index past the letter list)
        return float("nan")
    return LETTERS.index(m.group(1)) * 10 + sub


def spt_label(num: float) -> str:
    letter = LETTERS[int(num // 10)]
    sub = num - (num // 10) * 10
    return f"{letter}{sub:g}"


def _nearest(column: str, value: float, lo=None, hi=None):
    ref = sequence().dropna(subset=[column])
    if lo is not None:
        ref = ref[ref.num >= lo]
    if hi is not None:
        ref = ref[ref.num <= hi]
    x = ref[column].to_numpy(float)
    if not len(x) or value < x.min() - 0.15 or value > x.max() + 0.15:
        return None                       # outside the calibrated sequence
    return float(ref.num.to_numpy()[np.abs(x - value).argmin()])


def _ms_abs_g(bprp0: float):
    ref = sequence().dropna(subset=["Bp-Rp", "M_G"]).sort_values("Bp-Rp")
    x, y = ref["Bp-Rp"].to_numpy(float), ref["M_G"].to_numpy(float)
    if bprp0 < x.min() or bprp0 > x.max():
        return None
    return float(np.interp(bprp0, x, y))


def _ebv(row):
    v = _num(row, "std_ebv")
    if v is not None:
        return v
    t = _num(row, "desi_legacy_surveys_dr10__mw_transmission_g")
    if t and 0 < t <= 1:
        return -2.5 * math.log10(t) / R_DECAM_G
    return _num(row, "galex_ais__E(B-V)")


def _result(subclass, code, conf, rule, basis, **extra):
    return {"subclass": subclass, "code": code, "confidence": conf, "rule": rule, "basis": basis, **extra}


# -------------------------------------------------------------------- STAR
def _parse_mk(sp: str):
    """Spectral letter/subtype and luminosity class from an MK string."""
    s = sp.replace(" ", "")
    lum = None
    m = re.search(r"(Ia|Ib|III|II|IV|VI|V)(?![a-z])", s[1:]) if s else None
    if m:
        lum = m.group(1)
    num = spt_number(s)
    return num, lum


def _bprp0(row):
    bprp = _num(row, "gaia_dr3__bp_rp", "bp_rp")
    if bprp is None:
        return None, None
    e = _num(row, "gaia_dr3__ebpminrp_gspphot", "ebpminrp_gspphot")
    if e is not None:
        return bprp - e, "Gaia GSP-Phot E(BP-RP)"
    ebv = _ebv(row)
    if ebv is not None:
        return bprp - E_BPRP_PER_EBV * ebv, "SFD E(B-V) x 1.339"
    return bprp, "not dereddened"


def star_spectral_type(row):
    sp = _text(row, "simbad__sp_type")
    if sp and sp[0] in LETTERS:
        num, lum = _parse_mk(sp)
        if num == num:
            return num, lum, "SIMBAD_SPTYPE", f"SIMBAD spectral type {sp}"
    for key, src in (("lamost_dr_catalog__SubClass", "LAMOST"), ("sdss_dr18_spectroscopy__subclass", "SDSS")):
        sub = _text(row, key)
        if not sub:
            continue
        num = spt_number(sub)
        # SDSS template subclasses of A/F/G stars are offset from the MK
        # colour scale on the benchmark (LITERATURE_SUBCLASS.md); K/M agree to
        # ~1 subtype.  Use them only when no photometric estimate exists.
        if src == "SDSS" and num == num and num < 50 and _bprp0(row)[0] is not None:
            continue
        if num == num:
            return num, None, f"{src}_SUBCLASS", f"{src} spectrum subclass {sub}"
    bprp0, how = _bprp0(row)
    teff = _num(row, "gaia_dr3__teff_gspphot", "teff_gspphot")
    n_bp = _nearest("Bp-Rp", bprp0) if bprp0 is not None else None
    n_te = _nearest("Teff", teff) if teff is not None else None
    if n_bp is not None and n_te is not None:
        # Mean of the two Gaia estimates: GSP-Phot models extinction and
        # metallicity from the BP/RP spectra, the colour is model-free.
        # On DESI DR1 stars the mean raises letter accuracy 0.61 -> 0.82.
        n = round((n_bp + n_te) / 2 * 2) / 2
        return n, None, "GAIA_BPRP0_TEFF", (f"Gaia (BP-RP)0 = {bprp0:.2f} ({how}) -> {spt_label(n_bp)}, GSP-Phot Teff = "
                                             f"{teff:.0f} K -> {spt_label(n_te)} (Pecaut & Mamajek dwarf scale)")
    if n_bp is not None:
        return n_bp, None, "GAIA_BPRP0", f"Gaia (BP-RP)0 = {bprp0:.2f} ({how}) on the Pecaut & Mamajek dwarf sequence"
    ebv = _ebv(row) or 0.0
    g = _mag(row, "std_mag__ls_g", "desi_legacy_surveys_dr10__flux_g"); r = _mag(row, "std_mag__ls_r", "desi_legacy_surveys_dr10__flux_r")
    if g is not None and r is not None:
        gr0 = g - r - (3.214 - 2.165) * ebv
        if gr0 < 1.3:
            n = _nearest("g-r", gr0)
            if n is not None:
                return n, None, "LS_GR0", f"Legacy Surveys (g-r)0 = {gr0:.2f} on the Pecaut & Mamajek dwarf sequence"
    i = _mag(row, "std_mag__ps1_i", raw_mag_keys=("pan_starrs1_dr2_meanobject__iMeanPSFMag",))
    z = _mag(row, "std_mag__ps1_z", raw_mag_keys=("pan_starrs1_dr2_meanobject__zMeanPSFMag",))
    if i is not None and z is not None and i - z > 0.25:
        n = _nearest("i-z", i - z, lo=60)
        if n is not None:
            return n, None, "PS1_IZ", f"Pan-STARRS1 i-z = {i - z:.2f} on the Pecaut & Mamajek M-dwarf sequence"
    if n_te is not None:
        return n_te, None, "GAIA_TEFF", f"Gaia GSP-Phot Teff = {teff:.0f} K on the Pecaut & Mamajek scale"
    return None, None, None, "no spectral type, colour or Teff available"


def cmd_position(row):
    """(M_G, height above the dwarf sequence dM = M_G - M_G,MS, (BP-RP)0) for a
    parallax S/N >= 5, else None.  Negative dM = brighter than the sequence."""
    plx, eplx = _num(row, "gaia_dr3__parallax", "parallax"), _num(row, "gaia_dr3__parallax_error", "parallax_error")
    gmag = _num(row, "gaia_dr3__phot_g_mean_mag", "phot_g_mean_mag")
    bprp0, _ = _bprp0(row)
    if None in (plx, eplx, gmag, bprp0) or plx <= 0 or eplx <= 0 or plx / eplx < 5:
        return None
    ag = _num(row, "gaia_dr3__ag_gspphot")
    if ag is None:
        ebv = _ebv(row); ag = A_G_PER_EBV * ebv if ebv is not None else 0.0
    mg = gmag + 5 * math.log10(plx) - 10 - ag
    ms = _ms_abs_g(bprp0)
    return None if ms is None else (mg, mg - ms, bprp0)


def star_luminosity_class(row, num):
    pos = cmd_position(row)
    if pos is not None:
        mg, dm, bprp0 = pos
        # Unresolved equal-mass binaries sit up to 0.75 mag above the MS
        # (Hurley & Tout 1998); metallicity/age spread adds ~0.3 mag.
        if dm > 3.0:
            return None, "GAIA_CMD", f"M_G = {mg:.2f}, {dm:+.2f} mag below the dwarf sequence (white-dwarf region)"
        if dm > 1.0:
            # Metal-poor subdwarfs lie 1-2 mag below the solar-metallicity
            # sequence (Kuiper 1939; Gizis 1997).  On the SDSS benchmark stars
            # with 1 < dM <= 3 have median GSP-Phot [M/H] = -1.4 (MS: -0.66).
            return "VI", "GAIA_CMD", f"M_G = {mg:.2f}, {dm:+.2f} mag below the dwarf sequence (subdwarf)"
        if dm > -1.0:
            return "V", "GAIA_CMD", f"M_G = {mg:.2f}, {dm:+.2f} mag from the dwarf sequence"
        if dm > -2.5 and bprp0 < 1.3:
            return "IV", "GAIA_CMD", f"M_G = {mg:.2f}, {dm:+.2f} mag above the dwarf sequence"
        return "III", "GAIA_CMD", f"M_G = {mg:.2f}, {dm:+.2f} mag above the dwarf sequence"
    teff, logg = _num(row, "gaia_dr3__teff_gspphot", "teff_gspphot"), _num(row, "gaia_dr3__logg_gspphot", "logg_gspphot")
    if teff is not None and logg is not None:
        # Ciardi et al. (2010) red-giant boundary used for Kepler targets.
        lim = 4.0 if teff <= 4250 else (5.2 - 2.8e-4 * teff if teff < 6000 else 3.5)
        return ("III" if logg <= lim else "V"), "GAIA_LOGG", f"GSP-Phot log g = {logg:.2f} vs giant boundary {lim:.2f}"
    return None, None, "no parallax or log g"


# Tangential-velocity selections of Babusiaux et al. (2018, A&A 616, A10,
# Gaia DR2 HRDs): thin disc V_T < 40, thick disc 60-150, halo > 200 km/s.
# Between the windows the population is left open.
POPULATION_VT = (("THIN_DISC", 0.0, 40.0), ("THICK_DISC", 60.0, 150.0), ("HALO", 200.0, float("inf")))
RUWE_BINARY = 1.4      # Lindegren et al. (2018); Belokurov et al. (2020)


def star_tags(row):
    tags = []
    plx, eplx = _num(row, "gaia_dr3__parallax", "parallax"), _num(row, "gaia_dr3__parallax_error", "parallax_error")
    pmra, pmdec = _num(row, "gaia_dr3__pmra", "pmra"), _num(row, "gaia_dr3__pmdec", "pmdec")
    if None not in (plx, eplx, pmra, pmdec) and plx > 0 and eplx > 0 and plx / eplx >= 5:
        vt = 4.74047 * math.hypot(pmra, pmdec) / plx
        for pop, lo, hi in POPULATION_VT:
            if lo <= vt < hi:
                tags.append({"tag": pop, "label": {"THIN_DISC": "thin-disc star", "THICK_DISC": "thick-disc star",
                                                    "HALO": "halo star"}[pop],
                             "rule": "GAIA_VTAN", "basis": f"V_T = {vt:.0f} km/s (Babusiaux+2018 windows 40 / 60-150 / 200)"})
    ruwe = _num(row, "gaia_dr3__ruwe", "ruwe")
    if ruwe is not None and ruwe > RUWE_BINARY:
        tags.append({"tag": "ASTROMETRIC_BINARY", "label": "astrometric binary candidate", "rule": "GAIA_RUWE",
                     "basis": f"RUWE = {ruwe:.2f} > 1.4 (unresolved companion; Belokurov+2020)"})
    b = _num(row, "gaia_dr3__classprob_dsc_combmod_binarystar", "classprob_dsc_combmod_binarystar")
    if b is not None and b >= 0.8 and not any(t["tag"] == "ASTROMETRIC_BINARY" for t in tags):
        tags.append({"tag": "PHOTOMETRIC_BINARY", "label": "binary candidate (Gaia DSC)", "rule": "GAIA_DSC_BINARY",
                     "basis": f"Gaia DSC binary probability {b:.2f}"})
    # Distance and motion.
    if plx is not None and eplx is not None and plx > 0 and eplx > 0:
        if plx > 10.0 and plx / eplx >= 10:
            # Inside the Gaia Catalogue of Nearby Stars volume (100 pc;
            # Gaia Collaboration, Smart et al. 2021).
            tags.append({"tag": "NEARBY", "label": f"nearby star ({1000 / plx:.0f} pc)", "rule": "GAIA_PARALLAX",
                         "basis": f"parallax {plx:.2f} +- {eplx:.2f} mas (< 100 pc)"})
    if pmra is not None and pmdec is not None and math.hypot(pmra, pmdec) > 150.0:
        tags.append({"tag": "HIGH_PM", "label": "high-proper-motion star", "rule": "GAIA_PM",
                     "basis": f"mu = {math.hypot(pmra, pmdec):.0f} mas/yr > 150 (LSPM limit; Lepine & Shara 2005)"})
    # Red clump: core-helium-burning giants, M_G = 0.495 + 1.121 (G - Ks - 2.1)
    # (Ruiz-Dern et al. 2018, A&A 609, A116; intrinsic spread ~0.2 mag).
    pos = cmd_position(row)
    gmag = _num(row, "gaia_dr3__phot_g_mean_mag", "phot_g_mean_mag")
    ks = _num(row, "2mass_psc__Kmag", "allwise__Kmag")
    if pos is not None and gmag is not None and ks is not None:
        mg, dm, bprp0 = pos
        gk = gmag - ks
        if 1.8 <= gk <= 2.6 and dm <= -2.5:
            m_rc = 0.495 + 1.121 * (gk - 2.1)
            if abs(mg - m_rc) <= 0.5:
                tags.append({"tag": "RED_CLUMP", "label": "red-clump giant candidate", "rule": "GAIA_RC",
                             "basis": f"M_G = {mg:.2f} vs red clump {m_rc:.2f} at G-Ks = {gk:.2f} (Ruiz-Dern+2018)"})
    # Mid-IR excess over the photosphere (stellar W1-W2 ~ W2-W3 ~ 0, Vega):
    # lower bounds of the Koenig et al. (2012) class II locus.  Dusty discs
    # (YSOs, debris discs) or circumstellar shells (AGB); background
    # galaxies can mimic it.
    w1, w2, w3 = (_wise_vega(row, k) for k in (1, 2, 3))
    ew3 = _num(row, "std_magerr__wise_w3", "allwise__e_W3mag")
    if None not in (w1, w2, w3, ew3) and ew3 < 0.2 and w1 - w2 > 0.25 and w2 - w3 > 1.0:
        tags.append({"tag": "IR_EXCESS", "label": "infrared-excess star (dust disc / shell candidate)", "rule": "WISE_IR_EXCESS",
                     "basis": f"W1-W2 = {w1 - w2:.2f} > 0.25, W2-W3 = {w2 - w3:.2f} > 1.0 (Koenig+2012)"})
    xr = _catalogs(row) & set(XRAY_CATALOGS)
    if xr:
        # Stellar X-rays trace coronal activity (young / fast rotators / active binaries).
        tags.append({"tag": "XRAY", "label": "X-ray active star", "rule": "XRAY", "basis": ", ".join(sorted(xr))})
    mh = _num(row, "gaia_dr3__mh_gspphot", "mh_gspphot")
    if mh is not None and gmag is not None and gmag < 17 and mh < -1.0:
        # [M/H] < -1 "metal-poor" (Beers & Christlieb 2005).  GSP-Phot [M/H]
        # is only indicative (Andrae et al. 2023), hence "candidate".
        tags.append({"tag": "METAL_POOR", "label": "metal-poor star candidate", "rule": "GAIA_GSPPHOT_MH",
                     "basis": f"GSP-Phot [M/H] = {mh:.2f} < -1 (G = {gmag:.1f})"})
    var = str(row.get("variability_class") or "")
    if var and var not in ("UNKNOWN", "nan", "None"):
        sub = row.get("variability_subtype")
        name = var.replace("_", " ").lower() + (f" ({sub})" if isinstance(sub, str) and sub else "")
        tags.append({"tag": f"VAR_{var}", "label": f"{name} variable", "rule": "VARIABILITY_AXIS",
                     "basis": f"variability axis: {row.get('variability_status', '')}"})
    return tags


# ------------------------------------------------------------ AGB chemistry
# AGB stars are oxygen-rich (C/O < 1; silicate dust, M-type spectra) or
# carbon-rich (C/O > 1; amorphous-carbon/SiC dust, C-type spectra) after third
# dredge-up.  Order of evidence: spectra / curated types, the Suh (2021)
# catalogue, the Gaia DR3 RP-spectrum C-star flag, then photometry.  The
# photometric criteria are only applied to AGB candidates (long-period
# variables or AGB physical class): on ordinary stars the same colours mean
# nothing (benchmark stars with J-Ks >= 1 mostly have W_RP - W_KJ >= 0.9).
#
# * Gaia-2MASS Wesenheit difference (Lebzelter et al. 2018, A&A 616, L13):
#   W_RP = G_RP - 1.3 (G_BP - G_RP), W_KJ = Ks - 0.686 (J - Ks); C-rich above
#   ~0.9 mag and extreme (dust-enshrouded) C-rich above ~1.7 mag for Galactic
#   LPVs (Mowlavi et al. 2019; Abia et al. 2020, A&A 633, A135).
# * AllWISE colours (Lian et al. 2014, A&A 564, A84): the line
#   W1-W2 = 2.35 (W3-W4) - 1.24 separates 87 % of O-rich and 86 % of C-rich
#   AGB stars; used when Gaia/2MASS photometry is missing (dusty stars).
# * Silicate (dusty O-rich) AGB: O-rich with a mid-IR dust excess, Ks - W3 above
#   the stellar photosphere (Suh 2021 two-colour diagrams).
AGB_DW_C, AGB_DW_XC = 0.9, 1.7
AGB_DUST_KW3 = 1.0
AGB_VARIABILITY = {"LPV", "MIRA"}
SIMBAD_AGB = {"AGB*", "C*", "S*", "Mi*", "LP*", "OH*", "pA*"}


def wesenheit_dw(row):
    """W_RP - W_KJ (Gaia RP/BP Vega, 2MASS J/Ks Vega), or None."""
    rp = _num(row, "gaia_dr3__phot_rp_mean_mag", "phot_rp_mean_mag")
    bp = _num(row, "gaia_dr3__phot_bp_mean_mag", "phot_bp_mean_mag")
    j = _num(row, "2mass_psc__Jmag", "allwise__Jmag")
    k = _num(row, "2mass_psc__Kmag", "allwise__Kmag")
    if None in (rp, bp, j, k):
        return None
    return (rp - 1.3 * (bp - rp)) - (k - 0.686 * (j - k))


def agb_candidate(row):
    """Why the object counts as an AGB candidate, or None."""
    if str(row.get("physical_class") or "") == "AGB":
        return "physical axis AGB"
    var = str(row.get("variability_class") or "")
    if var in AGB_VARIABILITY:
        return f"{var} variable"
    if _num(row, "gaia_lpv_frequency", "gaia_lpv_amplitude") is not None:
        return "Gaia DR3 long-period variable"
    ot = _text(row, "simbad__otype")
    if ot in SIMBAD_AGB:
        return f"SIMBAD type {ot}"
    return None


def agb_chemistry(row):
    """{'chem': 'C'|'O'|'S', 'rule', 'basis', 'extreme', 'dusty'} or None."""
    sp = _text(row, "simbad__sp_type") or ""
    ot = _text(row, "simbad__otype") or ""
    out = None
    if re.match(r"^C[-\d(]|^C$|^C-?[NRJH]", sp) or ot == "C*":
        out = {"chem": "C", "rule": "SIMBAD_CSTAR", "basis": f"SIMBAD {'type C*' if ot == 'C*' else 'spectral type ' + sp}"}
    elif re.match(r"^(MS|SC|S)([\d(/ -]|$)", sp) or ot == "S*":
        out = {"chem": "S", "rule": "SIMBAD_SSTAR", "basis": f"SIMBAD {'type S*' if ot == 'S*' else 'spectral type ' + sp}"}
    if out is None:
        sub = (_text(row, "suh_2021_agb_catalog__agb_subclass", "agb_subclass") or "").upper()
        if sub.startswith(("CAGB", "OAGB")):
            out = {"chem": sub[0], "rule": "SUH2021", "basis": f"Suh (2021) catalogue {sub}"}
    if out is None and _num(row, "gaia_lpv_is_cstar") == 1:
        out = {"chem": "C", "rule": "GAIA_LPV_CSTAR",
               "basis": "Gaia DR3 LPV RP-spectrum C-star flag (Lebzelter et al. 2023)"}
    gate = agb_candidate(row)
    dw = wesenheit_dw(row)
    if out is None and gate:
        if dw is not None:
            out = {"chem": "C" if dw >= AGB_DW_C else "O", "rule": "GAIA_2MASS_WESENHEIT",
                   "basis": f"{gate}; W_RP - W_KJ = {dw:.2f} ({'>=' if dw >= AGB_DW_C else '<'} {AGB_DW_C}, Lebzelter+2018)"}
        else:
            w1, w2, w3, w4 = (_wise_vega(row, b) for b in (1, 2, 3, 4))
            if None not in (w1, w2, w3, w4):
                line = 2.35 * (w3 - w4) - 1.24
                chem = "C" if w1 - w2 > line else "O"
                out = {"chem": chem, "rule": "WISE_LIAN14",
                       "basis": f"{gate}; W1-W2 = {w1 - w2:.2f} vs 2.35(W3-W4)-1.24 = {line:.2f} (Lian+2014)"}
    if out is None:
        return None
    out["agb_candidate"] = gate
    out["extreme"] = out["chem"] == "C" and dw is not None and dw >= AGB_DW_XC
    k = _num(row, "2mass_psc__Kmag", "allwise__Kmag")
    w3 = _wise_vega(row, 3)
    out["dusty"] = k is not None and w3 is not None and k - w3 > AGB_DUST_KW3
    out["k_w3"] = None if k is None or w3 is None else k - w3
    return out


AGB_NAME = {"C": ("Carbon star (C-rich AGB)", "STAR:C:AGB"), "O": ("O-rich AGB star", "STAR:M:AGB"),
            "S": ("S-type star (C/O ~ 1, AGB)", "STAR:S:AGB")}


LUM_NAME = {"V": "dwarf", "IV": "subgiant", "III": "giant", "II": "bright giant", "Ib": "supergiant",
            "Ia": "supergiant", "VI": "subdwarf"}


def classify_star(row):
    phys = str(row.get("physical_class") or "")
    sdss = _text(row, "sdss_dr18_spectroscopy__subclass") or ""
    lam = _text(row, "lamost_dr_catalog__SubClass") or ""
    for label, src in ((sdss, "SDSS"), (lam, "LAMOST")):
        u = label.upper()
        if u.startswith("CARBON"):
            return _result("Carbon star", "STAR:C", None, f"{src}_SUBCLASS", f"{src} spectrum subclass {label}")
        if u == "CV":
            return _result("Cataclysmic variable", "STAR:CV", None, f"{src}_SUBCLASS", f"{src} spectrum subclass {label}")
        if u.startswith(("WD", "DA", "DB", "DC", "DQ", "DZ", "DO")):
            return _result(f"White dwarf ({label})", "STAR:WD", None, f"{src}_SUBCLASS", f"{src} spectrum subclass {label}")
    if phys == "WD":
        sub = row.get("physical_subtype")
        return _result("White dwarf" + (f" ({sub})" if isinstance(sub, str) and sub else ""), "STAR:WD",
                       _num(row, "physical_confidence"), "WD_LOCUS", "physical axis: Gaia WD locus / DSC")
    agb = agb_chemistry(row)
    if agb is not None:
        name, code = AGB_NAME[agb["chem"]]
        if agb["chem"] == "O" and agb["dusty"]:
            name = "O-rich AGB star with silicate dust"
        elif agb["chem"] == "C" and agb["extreme"]:
            name = "Extreme (dust-enshrouded) carbon star"
        if agb["chem"] != "S" and not agb.get("agb_candidate") and agb["rule"].startswith("SIMBAD"):
            name = name.replace(" (C-rich AGB)", "")      # carbon dwarfs / CH stars are not AGB stars
            code = code.replace(":AGB", ":?")
        return _result(name, code, RULE_PRECISION.get(agb["rule"]), agb["rule"], agb["basis"], agb_chemistry=agb["chem"])
    num, lum, rule, basis = star_spectral_type(row)
    if num is None:
        return _result(None, None, None, None, basis, status="NO_SPECTRAL_INFORMATION")
    if lum is None:
        lum, lrule, lbasis = star_luminosity_class(row, num)
    else:
        lrule, lbasis = "SIMBAD_SPTYPE", "luminosity class from the SIMBAD MK type"
    letter = LETTERS[int(num // 10)]
    if phys in {"RGB", "AGB"}:
        lum, lrule, lbasis = "III", "PHYSICAL_AXIS", f"physical axis {phys}"
    label = spt_label(num) + (f" {lum}" if lum else "")
    name = f"{letter}-type " + (LUM_NAME.get(lum, "star") if lum else "star")
    conf = RULE_PRECISION.get(rule)
    return _result(f"{label} ({name})", f"STAR:{letter}:{lum or '?'}", conf, rule, basis,
                   spectral_type=spt_label(num), spectral_letter=letter, luminosity_class=lum,
                   luminosity_rule=lrule, luminosity_basis=lbasis)


# ------------------------------------------------------------------ GALAXY
def galaxy_activity(row):
    sub = (_text(row, "sdss_dr18_spectroscopy__subclass") or "").upper()
    if sub:
        if "AGN" in sub or "BROADLINE" in sub:
            return "AGN", "SDSS_BPT", f"SDSS spectrum subclass {sub} (BPT / broad lines)"
        if "STARBURST" in sub:
            return "STARBURST", "SDSS_BPT", f"SDSS spectrum subclass {sub} (H-alpha EW > 50 A)"
        if "STARFORMING" in sub:
            return "STAR_FORMING", "SDSS_BPT", f"SDSS spectrum subclass {sub} (BPT)"
    ot = _text(row, "simbad__otype")
    if ot in SIMBAD_GALAXY:
        act, name = SIMBAD_GALAXY[ot]
        return act, "SIMBAD_OTYPE", f"SIMBAD type {ot} ({name})"
    w1, w2, w3 = (_wise_vega(row, k) for k in (1, 2, 3))
    ew3 = _num(row, "std_magerr__wise_w3", "allwise__e_W3mag")
    if w1 is not None and w2 is not None and w1 - w2 >= 0.8 and w2 < 15.05:
        return "AGN", "WISE_STERN12", f"W1-W2 = {w1 - w2:.2f} >= 0.8 with W2 = {w2:.2f} < 15.05"
    if w2 is not None and w3 is not None:
        c = w2 - w3
        if ew3 is not None and ew3 < 0.2:
            if c > 3.0:
                return "STAR_FORMING", "WISE_W23_SF", f"W2-W3 = {c:.2f} > 3 (star-forming disc)"
            if c < 1.5:
                return "QUIESCENT", "WISE_W23_Q", f"W2-W3 = {c:.2f} < 1.5 (spheroid)"
        elif ew3 is None and c < 1.5:
            # AllWISE W3 upper limit: the true W2-W3 is bluer still.
            return "QUIESCENT", "WISE_W23_UL", f"W2-W3 < {c:.2f} (W3 upper limit) < 1.5"
    nuv = _mag(row, "std_mag__galex_nuv", raw_mag_keys=("galex_ais__NUVmag",))
    r = _mag(row, "std_mag__ls_r", "desi_legacy_surveys_dr10__flux_r")
    if r is None:
        r = _mag(row, "std_mag__ps1kron_r", raw_mag_keys=("pan_starrs1_dr2_meanobject__rMeanKronMag", "sdss_dr18_photoobj__petroMag_r"))
    if nuv is not None and r is not None:
        ebv = _ebv(row) or 0.0
        nuvr = nuv - r - (8.2 - 2.165) * ebv
        if nuvr > 5.0:
            return "QUIESCENT", "GALEX_NUVR", f"(NUV-r)0 = {nuvr:.2f} > 5"
        if nuvr > 4.0:
            # Green valley between the blue cloud and red sequence (Salim 2014,
            # SerAJ 189, 1: 4 < NUV-r < 5; Wyder et al. 2007).
            return "GREEN_VALLEY", "GALEX_NUVR_GV", f"4 < (NUV-r)0 = {nuvr:.2f} <= 5 (green valley)"
    return None, None, "no spectrum, mid-IR or UV activity indicator"


# ------------------------------------------------- distances (flat LCDM)
H0, OMEGA_M = 70.0, 0.3            # cosmology of the SDSS DR7 quasar catalogue (Schneider+2010)


@lru_cache(maxsize=4096)
def luminosity_distance_mpc(z: float) -> float:
    zz = np.linspace(0.0, z, 257)
    e = np.sqrt(OMEGA_M * (1 + zz) ** 3 + (1 - OMEGA_M))
    trap = getattr(np, "trapezoid", None) or np.trapz      # numpy < 2.0
    dc = (299792.458 / H0) * trap(1.0 / e, zz)
    return float((1 + z) * dc)


def distance_modulus(z: float) -> float:
    return 5 * math.log10(luminosity_distance_mpc(z) * 1e6) - 5


def _optical_gr(row):
    """Dereddened (g, r) AB magnitudes: Legacy Surveys, else SDSS model mags."""
    ebv = _ebv(row) or 0.0
    g, r = _mag(row, "std_mag__ls_g", "desi_legacy_surveys_dr10__flux_g"), _mag(row, "std_mag__ls_r", "desi_legacy_surveys_dr10__flux_r")
    if g is not None and r is not None:
        return g - 3.214 * ebv, r - 2.165 * ebv
    g = _mag(row, "std_mag__sdss_g", raw_mag_keys=("sdss_dr18_photoobj__modelMag_g",))
    r = _mag(row, "std_mag__sdss_r", raw_mag_keys=("sdss_dr18_photoobj__modelMag_r",))
    if g is not None and r is not None:
        return g - 3.303 * ebv, r - 2.285 * ebv
    return None, None


SIMBAD_ENVIRONMENT = {
    "IG": ("INTERACTING", "interacting galaxy"), "PaG": ("PAIR", "galaxy pair"), "GiP": ("PAIR", "galaxy in a pair"),
    "GiG": ("GROUP", "galaxy in a group"), "GiC": ("CLUSTER", "galaxy in a cluster"),
    "BiC": ("BCG", "brightest cluster galaxy"), "LSB": ("LSB", "low-surface-brightness galaxy"),
    "rG": ("RADIO_GALAXY", "radio galaxy"),
}


def galaxy_tags(row, activity):
    tags = []
    sub = (_text(row, "sdss_dr18_spectroscopy__subclass") or "").upper()
    ot = _text(row, "simbad__otype")
    if "BROADLINE" in sub and "AGN" in sub or ot == "Sy1":
        tags.append({"tag": "AGN_TYPE1", "label": "type 1 (broad-line) AGN", "rule": "SDSS_BROADLINE" if sub else "SIMBAD_OTYPE",
                     "basis": f"SDSS subclass {sub}" if sub else "SIMBAD Sy1"})
    elif sub == "AGN" or ot == "Sy2":
        tags.append({"tag": "AGN_TYPE2", "label": "type 2 (narrow-line) AGN", "rule": "SDSS_BPT" if sub else "SIMBAD_OTYPE",
                     "basis": "BPT AGN without broad lines" if sub else "SIMBAD Sy2"})
    elif ot == "LIN":
        tags.append({"tag": "LINER", "label": "LINER", "rule": "SIMBAD_OTYPE", "basis": "SIMBAD LIN"})
    if ot in SIMBAD_ENVIRONMENT:
        t, lab = SIMBAD_ENVIRONMENT[ot]
        tags.append({"tag": t, "label": lab, "rule": "SIMBAD_OTYPE", "basis": f"SIMBAD type {ot}"})
    # Luminosity: M_B from the spectroscopic redshift.  B = g + 0.313(g-r) + 0.227
    # (Lupton 2005 SDSS->Johnson); dwarf when M_B > -16 (Tammann 1994).  No
    # K-correction, so only 0.003 < z < 0.1 (peculiar velocities / K-term).
    z = spectroscopic_z(row)
    g, r = _optical_gr(row)
    if z is not None and 0.003 < z < 0.1 and g is not None and r is not None:
        mb = g + 0.313 * (g - r) + 0.227 - distance_modulus(z)
        if mb > -10.0:
            # Fainter than any galaxy seen beyond the Local Group: the
            # redshift or the association is wrong, so no luminosity label.
            pass
        elif mb > -16.0:
            tags.append({"tag": "DWARF", "label": f"dwarf galaxy (M_B = {mb:.1f})", "rule": "ABS_MAG_TAMMANN",
                         "basis": f"M_B = {mb:.2f} > -16 at z = {z:.4f} (Tammann 1994)"})
        elif mb < -21.0:
            tags.append({"tag": "LUMINOUS", "label": f"luminous galaxy (M_B = {mb:.1f})", "rule": "ABS_MAG",
                         "basis": f"M_B = {mb:.2f} < -21 at z = {z:.4f} (brighter than L*; Schechter M*_B ~ -20.5)"})
    z = spectroscopic_z(row)
    ba = _num(row, "sga_2020__sga_ba", "sga_ba")
    if ba is not None and _num(row, "sga_2020__catalog_object_id") is not None:
        # Thin-disc inclination cos^2 i = (q^2 - q0^2) / (1 - q0^2), q0 = 0.2
        # (Hubble 1926; Holmberg 1958): b/a <= 0.3 -> i >~ 77 deg.
        q0 = 0.2
        inc = math.degrees(math.acos(math.sqrt(max(min((ba * ba - q0 * q0) / (1 - q0 * q0), 1.0), 0.0))))
        if ba <= 0.3:
            tags.append({"tag": "EDGE_ON", "label": f"edge-on galaxy (i ~ {inc:.0f} deg)", "rule": "SGA_AXIS_RATIO",
                         "basis": f"SGA b/a = {ba:.2f}, inclination from Hubble (1926) with q0 = 0.2"})
        elif ba >= 0.85:
            tags.append({"tag": "FACE_ON", "label": f"face-on galaxy (i ~ {inc:.0f} deg)", "rule": "SGA_AXIS_RATIO",
                         "basis": f"SGA b/a = {ba:.2f}"})
    if z is not None and z > 0:
        tags.append({"tag": "SPEC_Z", "label": f"spectroscopic z = {z:.4f}", "rule": "SPEC_Z",
                     "basis": f"distance {luminosity_distance_mpc(z):.0f} Mpc (flat LCDM, H0 = 70)"})
    flux, src = radio_14ghz_mjy(row)
    if flux is not None and activity == "QUIESCENT":
        # Radio emission from a galaxy without star formation is AGN-powered
        # (radio-mode AGN in early types; Best & Heckman 2012).
        tags.append({"tag": "RADIO_AGN", "label": "radio-loud AGN candidate", "rule": "RADIO_IN_QUIESCENT",
                     "basis": f"{src} {flux:.2f} mJy in a quiescent galaxy"})
    elif flux is not None:
        tags.append({"tag": "RADIO", "label": "radio source", "rule": "RADIO_DETECTED", "basis": f"{src} {flux:.2f} mJy"})
    xr = _catalogs(row) & set(XRAY_CATALOGS)
    if xr:
        tags.append({"tag": "XRAY", "label": "X-ray source", "rule": "XRAY", "basis": ", ".join(sorted(xr))})
    return tags


def galaxy_profile(row):
    t = (_text(row, "desi_legacy_surveys_dr10__type") or "").upper()
    if t == "DEV":
        return "EARLY_TYPE", "LS_DEV", "Legacy Surveys de Vaucouleurs profile"
    if t == "EXP":
        return "DISK", "LS_EXP", "Legacy Surveys exponential profile"
    n = _num(row, "desi_legacy_surveys_dr10__sersic")
    if t == "SER" and n is not None and n > 0:
        # Sersic n = 2.5 separates early (bulge-dominated) from late (disc)
        # types (Shen et al. 2003, MNRAS 343, 978; Blanton et al. 2003).
        return ("EARLY_TYPE" if n >= 2.5 else "DISK"), "LS_SERSIC", f"Legacy Surveys Sersic n = {n:.2f} (early type if >= 2.5)"
    # Strateva et al. defined u-r = 2.22 in the native SDSS system: undo the
    # AB offset of u (units.SDSS_AB, -0.04).
    u = _mag(row, "std_mag__sdss_u", raw_mag_keys=("sdss_dr18_photoobj__modelMag_u",))
    if u is not None and _num(row, "std_mag__sdss_u") is not None:
        u += 0.04
    r = _mag(row, "std_mag__sdss_r", raw_mag_keys=("sdss_dr18_photoobj__modelMag_r",))
    if u is not None and r is not None:
        ur = u - r - (R_SDSS_U - R_SDSS_R) * (_ebv(row) or 0.0)
        return ("EARLY_TYPE" if ur >= 2.22 else "LATE_TYPE"), "SDSS_UR", f"(u-r)0 = {ur:.2f} vs 2.22 (Strateva+2001)"
    return None, None, "no profile or u-r colour"


ACT_NAME = {"AGN": "AGN host", "STARBURST": "starburst", "STAR_FORMING": "star-forming", "QUIESCENT": "quiescent",
            "GREEN_VALLEY": "green-valley"}
PROF_NAME = {"EARLY_TYPE": "early-type", "DISK": "disc", "LATE_TYPE": "late-type"}


def classify_galaxy(row):
    act, arule, abasis = galaxy_activity(row)
    prof, prule, pbasis = galaxy_profile(row)
    if act is None and prof is None:
        return _result(None, None, None, None, f"{abasis}; {pbasis}", status="NO_SUBCLASS_EVIDENCE")
    words = [w for w in (ACT_NAME.get(act), PROF_NAME.get(prof)) if w]
    name = " ".join(words).capitalize() + " galaxy"
    if row.get("n_components") and int(_num(row, "n_components") or 0) > 0:
        name += " (large, resolved)"
    return _result(name, f"GALAXY:{act or '?'}:{prof or '?'}", RULE_PRECISION.get(arule) if act else None,
                   arule or prule, "; ".join(b for b in (abasis if act else None, pbasis if prof else None) if b),
                   activity=act, activity_rule=arule, profile=prof, profile_rule=prule)


# --------------------------------------------------------------------- QSO
def radio_14ghz_mjy(row):
    for key, k in RADIO_14GHZ:
        v = _num(row, key)
        if v is not None and v > 0:
            return v * k, key.split("__")[0].upper()
    for keys, k in RADIO_OTHER:
        v = _num(row, *keys)
        if v is not None and v > 0:
            return v * k, keys[0].split("__")[0].upper() + " (alpha=-0.7)"
    return None, None


def qso_i_mag(row):
    i = _mag(row, "std_mag__ps1_i", raw_mag_keys=("pan_starrs1_dr2_meanobject__iMeanPSFMag",))
    if i is None:
        i = _mag(row, "std_mag__sdsspsf_i", raw_mag_keys=("sdss_dr18_photoobj__psfMag_i",))
    if i is None:
        i = _mag(row, "std_mag__ls_i", "desi_legacy_surveys_dr10__flux_i")
    return i


def spectroscopic_z(row):
    """Redshift measured from a spectrum: SDSS / DESI / LAMOST, or an NED
    redshift not flagged photometric.  SIMBAD rvz_redshift is not used: its
    source (spectroscopic or photometric) is not carried by the collector,
    and in COSMOS it produced impossible luminosities (M_B ~ -5)."""
    z = _num(row, "std_z_spec", "sdss_dr18_spectroscopy__z", "desi_dr1_spectroscopy__z", "lamost_dr_catalog__z")
    if z is not None:
        return z
    flag = str(row.get("ned__Redshift Flag") or "").upper()
    if "PHOT" not in flag and "PZ" not in flag:
        return _num(row, "ned__Redshift")
    return None


def classify_qso(row):
    parts, rules, basis = [], [], []
    ot = _text(row, "simbad__otype")
    if ot in SIMBAD_QSO and ot != "QSO":
        parts.append(SIMBAD_QSO[ot]); rules.append("SIMBAD_OTYPE"); basis.append(f"SIMBAD type {ot}")
    flux, src = radio_14ghz_mjy(row)
    i = qso_i_mag(row)
    radio = None
    if flux is not None and i is not None:
        t = -2.5 * math.log10(flux * 1e-3 / 3631.0)
        ri = 0.4 * (i - t)
        radio = "RADIO_LOUD" if ri > 1 else "RADIO_QUIET"
        rules.append("RADIO_RI"); basis.append(f"R_i = {ri:.2f} ({src} {flux:.2f} mJy, i = {i:.2f}; loud if > 1)")
    elif flux is not None:
        radio = "RADIO_DETECTED"; rules.append("RADIO_DETECTED"); basis.append(f"{src} {flux:.2f} mJy, no i-band magnitude")
    xray = bool(_catalogs(row) & set(XRAY_CATALOGS))
    if xray:
        rules.append("XRAY"); basis.append("X-ray counterpart: " + ", ".join(sorted(_catalogs(row) & set(XRAY_CATALOGS))))
    z = spectroscopic_z(row)
    zc = None
    if z is not None and z > 0:
        zc = "HIGH_Z" if z >= 2.1 else "LOW_Z"
        rules.append("SPEC_Z"); basis.append(f"spectroscopic z = {z:.3f}")
    if not rules:
        return _result(None, None, None, None, "no radio, X-ray, redshift or SIMBAD type", status="NO_SUBCLASS_EVIDENCE")
    words = []
    if radio == "RADIO_LOUD":
        words.append("Radio-loud")
    elif radio == "RADIO_QUIET":
        words.append("Radio-quiet")
    elif radio == "RADIO_DETECTED":
        words.append("Radio-detected")
    words.append(parts[0] if parts else "quasar")
    name = " ".join(words)
    name = name[0].upper() + name[1:]
    extra = []
    if z is not None and z > 0:
        extra.append(f"z = {z:.2f}")
    if xray:
        extra.append("X-ray")
    if extra:
        name += " (" + ", ".join(extra) + ")"
    return _result(name, f"QSO:{radio or '?'}:{zc or '?'}:{'X' if xray else '-'}", None, rules[0], "; ".join(basis),
                   radio=radio, xray=xray, redshift=z, redshift_class=zc)


def qso_tags(row):
    tags = []
    z, i = spectroscopic_z(row), qso_i_mag(row)
    if z is not None and z > 0.01 and i is not None:
        # M_i(z=2) (Richards et al. 2006): continuum K-correction for
        # alpha_nu = -0.5, K(z) = -2.5 (1 + alpha) log10((1 + z) / 3); the
        # emission-line term (+-0.2 mag) is not modelled.  Quasar luminosity
        # when M_i(z=2) < -22 (Schneider et al. 2010 DR7Q cut, converted
        # M_i(z=0) = M_i(z=2) + 0.596).
        ebv = _ebv(row) or 0.0
        k = -2.5 * 0.5 * math.log10((1 + z) / 3.0)
        mi2 = i - 1.698 * ebv - distance_modulus(z) - k
        quasar = mi2 + 0.596 < -22.0
        tags.append({"tag": "QUASAR_LUMINOSITY" if quasar else "SEYFERT_LUMINOSITY",
                     "label": ("quasar-luminosity" if quasar else "Seyfert-luminosity AGN") + f" (M_i(z=2) = {mi2:.1f})",
                     "rule": "ABS_MAG_RICHARDS06", "basis": f"i = {i:.2f}, z = {z:.3f}, M_i(z=2) = {mi2:.2f}"})
    if z is not None and z >= 5.0:
        tags.append({"tag": "VERY_HIGH_Z", "label": f"very-high-redshift quasar (z = {z:.2f})", "rule": "SPEC_Z",
                     "basis": "z >= 5: reionisation-era quasar (Fan et al. 2001, 2006)"})
    # Obscured (red) quasar: R - [4.5] > 6.1 (Vega; Hickox et al. 2007), with
    # R = r - 0.1837 (g - r) - 0.0971 (Lupton 2005) and W2 for [4.5].
    g, r = _optical_gr(row)
    w2 = _wise_vega(row, 2)
    if g is not None and r is not None and w2 is not None:
        rv = r - 0.1837 * (g - r) - 0.0971
        if rv - w2 > 6.1:
            tags.append({"tag": "OBSCURED", "label": "obscured (red) quasar candidate", "rule": "HICKOX07",
                         "basis": f"R - W2 = {rv - w2:.2f} > 6.1 (Vega; Hickox+2007)"})
    ot = _text(row, "simbad__otype")
    if ot in ("BLL", "Bla"):
        tags.append({"tag": "BLAZAR", "label": SIMBAD_QSO[ot], "rule": "SIMBAD_OTYPE", "basis": f"SIMBAD type {ot}"})
    return tags


# -------------------------------------------------------------------- main
def classify(row):
    coarse = str(row.get("primary_class") or "UNKNOWN").upper()
    if coarse == "STAR":
        out = classify_star(row)
        tags = star_tags(row) if out.get("code") != "STAR:WD" else []
    elif coarse == "GALAXY":
        out = classify_galaxy(row)
        tags = galaxy_tags(row, out.get("activity"))
    elif coarse == "QSO":
        out = classify_qso(row)
        tags = qso_tags(row)
    else:
        out = _result(None, None, None, None, "coarse class UNKNOWN", status="NOT_ROUTED")
        tags = []
    out["tags"] = tags
    if tags and out.get("subclass") is None:
        # Attributes without a main sub-class still describe the object.
        out["subclass"] = tags[0]["label"][0].upper() + tags[0]["label"][1:]
        out["rule"] = tags[0]["rule"]; out["basis"] = tags[0]["basis"]
        out["code"] = f"{coarse}:?"
    out.setdefault("status", "CLASSIFIED" if out.get("subclass") else "NO_SUBCLASS_EVIDENCE")
    if out.get("subclass") and out.get("status") != "CLASSIFIED":
        out["status"] = "CLASSIFIED"
    return out


@lru_cache(maxsize=1)
def _literature():
    import importlib.util
    spec = importlib.util.spec_from_file_location("v2_literature", ROOT / "literature.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


@lru_cache(maxsize=1)
def _unknown_reason():
    import importlib.util
    spec = importlib.util.spec_from_file_location("v2_unknown_reason", ROOT / "unknown_reason.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def annotate(df: pd.DataFrame, rows=None) -> pd.DataFrame:
    import json
    rows = rows if rows is not None else df.to_dict("records")
    # The subclass needs the physical-axis result (WD / giant) of the same row.
    for col in ("physical_class", "physical_subtype", "physical_confidence",
                "variability_class", "variability_subtype", "variability_status"):
        if col in df:
            for r, v in zip(rows, df[col]):
                r[col] = v
    res = [classify(r) for r in rows]
    # Literature ("from paper") classification. It is reported for every
    # object, but replaces the sub-class only where the catalogue data leave
    # the object UNKNOWN; the primary class itself stays UNKNOWN.
    papers = [_literature().from_paper(r) for r in rows]
    for row, r, p in zip(rows, res, papers):
        if p and str(row.get("primary_class") or "UNKNOWN").upper() == "UNKNOWN":
            r["subclass"] = f"from paper: {p['paper_class']}" + (" (detection only)" if p["detection_only"] else "")
            r["status"], r["rule"], r["basis"] = "FROM_PAPER", "LITERATURE", p["paper_source"]
    out = df.copy()
    out["subclass"] = [r.get("subclass") for r in res]
    out["subclass_code"] = [r.get("code") for r in res]
    out["subclass_confidence"] = [r.get("confidence") for r in res]
    out["subclass_rule"] = [r.get("rule") for r in res]
    out["subclass_status"] = [r.get("status") for r in res]
    out["subclass_basis"] = [r.get("basis") for r in res]
    for col in ("paper_class", "paper_source", "paper_refs", "paper_ads"):
        out[col] = [p.get(col) if p else None for p in papers]
    out["unknown_reason"] = [_unknown_reason().reason(r) for r in rows]
    out["subclass_tags"] = ["; ".join(t["label"] for t in r.get("tags", [])) or None for r in res]
    out["subclass_json"] = [json.dumps(r, separators=(",", ":"), default=str) for r in res]
    return out
