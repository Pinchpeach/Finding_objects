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
    return LETTERS.index(m.group(1)) * 10 + (float(m.group(2)) if m.group(2) else 5.0)


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
    g = _ab_mag(_num(row, "desi_legacy_surveys_dr10__flux_g")); r = _ab_mag(_num(row, "desi_legacy_surveys_dr10__flux_r"))
    if g is not None and r is not None:
        gr0 = g - r - (3.214 - 2.165) * ebv
        if gr0 < 1.3:
            n = _nearest("g-r", gr0)
            if n is not None:
                return n, None, "LS_GR0", f"Legacy Surveys (g-r)0 = {gr0:.2f} on the Pecaut & Mamajek dwarf sequence"
    i, z = _num(row, "pan_starrs1_dr2_meanobject__iMeanPSFMag"), _num(row, "pan_starrs1_dr2_meanobject__zMeanPSFMag")
    if i is not None and z is not None and i - z > 0.25:
        n = _nearest("i-z", i - z, lo=60)
        if n is not None:
            return n, None, "PS1_IZ", f"Pan-STARRS1 i-z = {i - z:.2f} on the Pecaut & Mamajek M-dwarf sequence"
    if n_te is not None:
        return n_te, None, "GAIA_TEFF", f"Gaia GSP-Phot Teff = {teff:.0f} K on the Pecaut & Mamajek scale"
    return None, None, None, "no spectral type, colour or Teff available"


def star_luminosity_class(row, num):
    plx, eplx = _num(row, "gaia_dr3__parallax", "parallax"), _num(row, "gaia_dr3__parallax_error", "parallax_error")
    gmag = _num(row, "gaia_dr3__phot_g_mean_mag", "phot_g_mean_mag")
    bprp0, _ = _bprp0(row)
    if None not in (plx, eplx, gmag, bprp0) and plx > 0 and eplx > 0 and plx / eplx >= 5:
        ag = _num(row, "gaia_dr3__ag_gspphot")
        if ag is None:
            ebv = _ebv(row); ag = A_G_PER_EBV * ebv if ebv is not None else 0.0
        mg = gmag + 5 * math.log10(plx) - 10 - ag
        ms = _ms_abs_g(bprp0)
        if ms is not None:
            dm = mg - ms
            # Unresolved equal-mass binaries sit up to 0.75 mag above the MS
            # (Hurley & Tout 1998); metallicity/age spread adds ~0.3 mag.
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
    w1, w2, w3 = (_num(row, f"allwise__W{k}mag") for k in (1, 2, 3))
    ew3 = _num(row, "allwise__e_W3mag")
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
    nuv = _num(row, "galex_ais__NUVmag")
    r = _ab_mag(_num(row, "desi_legacy_surveys_dr10__flux_r"))
    if r is None:
        r = _num(row, "pan_starrs1_dr2_meanobject__rMeanKronMag", "sdss_dr18_photoobj__petroMag_r")
    if nuv is not None and r is not None:
        ebv = _ebv(row) or 0.0
        nuvr = nuv - r - (8.2 - 2.165) * ebv
        if nuvr > 5.0:
            return "QUIESCENT", "GALEX_NUVR", f"(NUV-r)0 = {nuvr:.2f} > 5"
    return None, None, "no spectrum, mid-IR or UV activity indicator"


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
    u, r = _num(row, "sdss_dr18_photoobj__modelMag_u"), _num(row, "sdss_dr18_photoobj__modelMag_r")
    if u is not None and r is not None:
        ur = u - r - (R_SDSS_U - R_SDSS_R) * (_ebv(row) or 0.0)
        return ("EARLY_TYPE" if ur >= 2.22 else "LATE_TYPE"), "SDSS_UR", f"(u-r)0 = {ur:.2f} vs 2.22 (Strateva+2001)"
    return None, None, "no profile or u-r colour"


ACT_NAME = {"AGN": "AGN host", "STARBURST": "starburst", "STAR_FORMING": "star-forming", "QUIESCENT": "quiescent"}
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
    i = _num(row, "pan_starrs1_dr2_meanobject__iMeanPSFMag", "sdss_dr18_photoobj__psfMag_i")
    if i is None:
        i = _ab_mag(_num(row, "desi_legacy_surveys_dr10__flux_i"))
    return i


def spectroscopic_z(row):
    return _num(row, "sdss_dr18_spectroscopy__z", "desi_dr1_spectroscopy__z", "lamost_dr_catalog__z",
                "host_redshift", "simbad__rvz_redshift", "ned__Redshift")


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


# -------------------------------------------------------------------- main
def classify(row):
    coarse = str(row.get("primary_class") or "UNKNOWN").upper()
    if coarse == "STAR":
        out = classify_star(row)
    elif coarse == "GALAXY":
        out = classify_galaxy(row)
    elif coarse == "QSO":
        out = classify_qso(row)
    else:
        out = _result(None, None, None, None, "coarse class UNKNOWN", status="NOT_ROUTED")
    out.setdefault("status", "CLASSIFIED" if out.get("subclass") else "NO_SUBCLASS_EVIDENCE")
    return out


def annotate(df: pd.DataFrame, rows=None) -> pd.DataFrame:
    import json
    rows = rows if rows is not None else df.to_dict("records")
    # The subclass needs the physical-axis result (WD / giant) of the same row.
    if "physical_class" in df:
        for r, p, s, c in zip(rows, df["physical_class"], df.get("physical_subtype", [None] * len(df)),
                              df.get("physical_confidence", [None] * len(df))):
            r["physical_class"], r["physical_subtype"], r["physical_confidence"] = p, s, c
    res = [classify(r) for r in rows]
    out = df.copy()
    out["subclass"] = [r.get("subclass") for r in res]
    out["subclass_code"] = [r.get("code") for r in res]
    out["subclass_confidence"] = [r.get("confidence") for r in res]
    out["subclass_rule"] = [r.get("rule") for r in res]
    out["subclass_status"] = [r.get("status") for r in res]
    out["subclass_basis"] = [r.get("basis") for r in res]
    out["subclass_json"] = [json.dumps(r, separators=(",", ":"), default=str) for r in res]
    return out
