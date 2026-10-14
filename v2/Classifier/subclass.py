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
    the Ciardi et al. (2011) Teff-log g boundary on spectroscopic / GSP-Phot log g.
  * white dwarfs come from the physical axis (Gentile Fusillo+2021 locus).
GALAXY
  * activity: SDSS broad lines > emission-line WHAN / BPT > SDSS spectral
    subclass (Bolton+2012) > SIMBAD type > WISE mid-IR AGN (W1-W2 >= 0.8,
    W2 < 15.05, S/N >= 10; Stern+2012) > WISE W2-W3 (> 3.5 star-forming,
    < 1.5 quiescent; Jarrett+2017/2019) > GALEX NUV-r (> 5 red sequence;
    Salim 2014, Wyder+2007).
  * light profile: Legacy Surveys DEV (de Vaucouleurs, early-type-like) /
    EXP (exponential disc); SDSS u-r >= 2.22 early type (Strateva+2001).
QSO
  * radio loudness R_i = 0.4 (m_i - t), t = -2.5 log10(F_1.4GHz / 3631 Jy);
    radio-loud when R_i > 1 (Ivezic et al. 2002).
  * redshift class from a spectroscopic redshift: z >= 2.1 (Ly-alpha forest
    in the optical; Ross et al. 2012; the DESI Lya-quasar boundary,
    Chaussidon et al. 2023) "high-z".
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
import importlib.util as _ilu

_s = _ilu.spec_from_file_location("v2_simbad_otypes_sub", ROOT / "simbad_otypes.py")
OTYPES = _ilu.module_from_spec(_s)
_s.loader.exec_module(OTYPES)
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
RADIO_OTHER = (
    (("lotss_dr2__Stotal", "lotss_dr2__SpeakTot", "lotss_dr2__Total_flux", "lotss_dr2__Stot"), (1400 / 144) ** -0.7),
    (("vlass__Ftot", "vlass__Total_flux"), (1400 / 3000) ** -0.7),
)
XRAY_CATALOGS = ("Chandra CSC 2.0", "XMM 4XMM-DR13", "eROSITA eRASS1")

SIMBAD_GALAXY = {
    "Sy1": ("AGN", "Seyfert 1"),
    "Sy2": ("AGN", "Seyfert 2"),
    "SyG": ("AGN", "Seyfert"),
    "LIN": ("AGN", "LINER"),
    "AGN": ("AGN", "AGN"),
    "SBG": ("STARBURST", "starburst galaxy"),
    "H2G": ("STAR_FORMING", "HII galaxy"),
    "EmG": ("STAR_FORMING", "emission-line galaxy"),
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
    if v is not None or std_key in row:  # harmonised: a missing value stays missing
        return v
    if raw_flux_key:
        return _ab_mag(_num(row, raw_flux_key))
    v = _num(row, *raw_mag_keys)
    return None if v is None or not 0 < v < 40 else v + offset  # PS1 -999 / SDSS -9999 sentinels


WISE_AB = {1: 2.699, 2: 3.339, 3: 5.174, 4: 6.620}  # units.WISE_AB (Jarrett+2011)


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
    if sub >= 10:  # not an MK subtype ("M10", "Y10" would index past the letter list)
        return float("nan")
    return LETTERS.index(m.group(1)) * 10 + sub


def spt_label(num: float) -> str:
    letter = LETTERS[int(num // 10)]
    sub = num - (num // 10) * 10
    return f"{letter}{sub:g}"


@lru_cache(maxsize=16)
def _column_arrays(column: str):
    """(values, spectral numbers) of the dwarf sequence where ``column`` is
    defined; built once per column (2.19.0: was ~1 ms of pandas per call,
    about five calls per star)."""
    ref = sequence().dropna(subset=[column])
    return ref[column].to_numpy(float), ref.num.to_numpy(float)


def _nearest(column: str, value: float, lo=None, hi=None):
    x, num = _column_arrays(column)
    keep = np.ones(len(x), bool)
    if lo is not None:
        keep &= num >= lo
    if hi is not None:
        keep &= num <= hi
    x, num = x[keep], num[keep]
    if not len(x) or value < x.min() - 0.15 or value > x.max() + 0.15:
        return None  # outside the calibrated sequence
    return float(num[np.abs(x - value).argmin()])


@lru_cache(maxsize=1)
def _ms_arrays():
    ref = sequence().dropna(subset=["Bp-Rp", "M_G"]).sort_values("Bp-Rp")
    return ref["Bp-Rp"].to_numpy(float), ref["M_G"].to_numpy(float)


def _ms_abs_g(bprp0: float):
    x, y = _ms_arrays()
    if bprp0 < x[0] or bprp0 > x[-1]:
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


# SFD-type E(B-V) is the whole line of sight; a star inside the dust layer
# sees only the part in front of it.  Exponential dust disc with scale height
# 134 pc (Drimmel & Spergel 2001, ApJ 556, 181): fraction in front of a star
# at distance d and latitude b = 1 - exp(-d |sin b| / h).  Applied only with a
# parallax (2.23.0: a 20 pc star was dereddened by the full column, 0.4 mag in
# BP-RP); without one the full column is kept, as before.
DUST_SCALE_HEIGHT_PC = 134.0


def _galactic_b(row):
    ra, dec = _num(row, "ra"), _num(row, "dec")
    if ra is None or dec is None:
        return None
    r, d = math.radians(ra), math.radians(dec)
    x, y, z = math.cos(d) * math.cos(r), math.cos(d) * math.sin(r), math.sin(d)
    gz = -0.8676661490 * x - 0.1980763734 * y + 0.4559837762 * z  # ICRS -> Galactic (Hipparcos)
    return math.degrees(math.asin(max(-1.0, min(1.0, gz))))


def _dust_fraction(row):
    """Fraction of the total line-of-sight E(B-V) in front of the star (1 without a parallax)."""
    plx, eplx = _num(row, "gaia_dr3__parallax", "parallax"), _num(row, "gaia_dr3__parallax_error", "parallax_error")
    b = _galactic_b(row)
    if None in (plx, eplx, b) or plx <= 0 or eplx <= 0 or plx / eplx < 5:
        return 1.0
    d_pc = 1000.0 / plx
    return 1.0 - math.exp(-d_pc * abs(math.sin(math.radians(b))) / DUST_SCALE_HEIGHT_PC) if abs(b) > 0 else 1.0


def _sfd_ebv_in_front(row):
    ebv = _ebv(row)
    return None if ebv is None else ebv * _dust_fraction(row)


def _ag(row):
    """A_G: GSP-Phot, else the SFD column in front of the star x 2.74 (one fallback for all callers)."""
    ag = _num(row, "gaia_dr3__ag_gspphot", "ag_gspphot")
    if ag is not None:
        return ag
    ebv = _sfd_ebv_in_front(row)
    return A_G_PER_EBV * ebv if ebv is not None else 0.0


def _result(subclass, code, conf, rule, basis, **extra):
    return {"subclass": subclass, "code": code, "confidence": conf, "rule": rule, "basis": basis, **extra}


# -------------------------------------------------------------------- STAR
def _parse_mk(sp: str):
    """Spectral letter/subtype and luminosity class from an MK string."""
    s = sp.replace(" ", "")
    lum = None
    m = (
        re.search(r"(Ia|Ib|III|II|IV|VI|V)(?![IV])", s[1:]) if s else None
    )  # 2.22.0: qualifiers (b, e, n, CN) may follow
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
    ebv = _sfd_ebv_in_front(row)
    if ebv is not None:
        return bprp - E_BPRP_PER_EBV * ebv, "SFD E(B-V) x 1.339 (part in front of the star)"
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
        return (
            n,
            None,
            "GAIA_BPRP0_TEFF",
            (
                f"Gaia (BP-RP)0 = {bprp0:.2f} ({how}) -> {spt_label(n_bp)}, GSP-Phot Teff = "
                f"{teff:.0f} K -> {spt_label(n_te)} (Pecaut & Mamajek dwarf scale)"
            ),
        )
    if n_bp is not None:
        return n_bp, None, "GAIA_BPRP0", f"Gaia (BP-RP)0 = {bprp0:.2f} ({how}) on the Pecaut & Mamajek dwarf sequence"
    ebv = _ebv(row) or 0.0
    g = _mag(row, "std_mag__ls_g", "desi_legacy_surveys_dr10__flux_g")
    r = _mag(row, "std_mag__ls_r", "desi_legacy_surveys_dr10__flux_r")
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
    mg = gmag + 5 * math.log10(plx) - 10 - _ag(row)
    ms = _ms_abs_g(bprp0)
    return None if ms is None else (mg, mg - ms, bprp0)


# Spectroscopic atmospheric parameters (2.6.0): LAMOST LASP (Luo et al. 2015;
# errors ~110 K, 0.2 dex in log g, 0.1 dex in [Fe/H]) and Gaia GSP-Spec from
# RVS spectra (Recio-Blanco et al. 2023), accepted when the flags of the
# parameter are 0 (positions 1/4/8/13 for Teff, 2/5/8/13 for log g, 3/6/8 for
# [M/H]; Babusiaux et al. 2023, DR3 validation).  On 388 benchmark stars with
# LAMOST parameters the log g class agrees with the Gaia CMD class for 219 of
# 221 dwarfs, while GSP-Phot log g finds 1 of the 22 LAMOST giants.
GSPSPEC_FLAG_POS = {"teff": (1, 4, 8, 13), "logg": (2, 5, 8, 13), "mh": (3, 6, 8)}


def _gspspec_ok(flags, par, row=None):
    """GSP-Spec parameter usable?  The collector stores the decision
    (gspspec_<par>_ok, from the zero-padded flags); otherwise the flags string
    is read here, restoring the leading zeros a numeric round trip removes."""
    if row is not None:
        ok = _num(row, f"gaia_dr3__gspspec_{par}_ok", f"gspspec_{par}_ok")
        if ok is not None:
            return ok == 1
    raw = str(flags or "").strip().lstrip("F")
    if "e" in raw.lower():  # float notation (>= 1e16): digits already lost
        return False
    f = raw.split(".")[0]
    if not f.isdigit():
        return False
    f = f.zfill(41)
    return all(f[i - 1] == "0" for i in GSPSPEC_FLAG_POS[par])


def spectro_params(row):
    """{'teff', 'logg', 'feh', 'source'} from a spectroscopic survey, or None."""
    teff, logg, feh = (_num(row, f"lamost_dr_catalog__lasp_{k}") for k in ("teff", "logg", "feh"))
    if teff is not None and logg is not None:
        return {"teff": teff, "logg": logg, "feh": feh, "source": "LAMOST"}
    flags = _text(row, "gaia_dr3__flags_gspspec", "flags_gspspec")
    teff, logg, mh = (_num(row, f"gaia_dr3__{k}_gspspec", f"{k}_gspspec") for k in ("teff", "logg", "mh"))
    if teff is not None and logg is not None and _gspspec_ok(flags, "teff", row) and _gspspec_ok(flags, "logg", row):
        mh = gspspec_mh_calibrated(mh, logg) if mh is not None and _gspspec_ok(flags, "mh", row) else None
        return {"teff": teff, "logg": gspspec_logg_calibrated(logg), "feh": mh, "source": "GSPSPEC"}
    return None


# GSP-Spec calibrations recommended by the producers (Recio-Blanco et al.
# 2023, Sect. 9.1, Eqs. 1-2 and Table 3; Fouesneau et al. 2023, App. A):
# GSP-Spec log g is biased low, more for giants; [M/H] of giants is
# underestimated and of dwarfs overestimated.  Both corrections are
# polynomials in the uncalibrated log g (literature-based row for [M/H]).
GSPSPEC_LOGG_CAL = (0.4496, -0.0036, -0.0224)
GSPSPEC_MH_CAL = (0.274, -0.1373, -0.0050, 0.0048)


def gspspec_logg_calibrated(logg):
    return logg + sum(c * logg**i for i, c in enumerate(GSPSPEC_LOGG_CAL))


def gspspec_mh_calibrated(mh, logg_raw):
    return mh + sum(c * logg_raw**i for i, c in enumerate(GSPSPEC_MH_CAL))


# Gaia DR3 ESP-ELS emission-line classes from BP/RP spectra (Creevey et al.
# 2023; DR3 documentation 11.3.7).  Checked against SIMBAD on 4000 ESP-ELS
# stars (2.6.2, benchmark/evaluate_bright.py): "TTauri" matched a young-star
# type for 2 % (most are long-period variables), "HerbigStar" 30 %, "beStar"
# 27 %, while 40-80 % are emission-line stars of some kind.  Only the
# emission itself is used (tag); the class label decides nothing.
# classlabel_espels_flag 0/1/2 = gap between the two highest class
# probabilities >= 0.8/0.6/0.4 (DR3 documentation 11.3.7); +10 / +20 mark
# GSP-Phot parameters inconsistent with / removed for the spectral type.
ESP_ELS = {
    "bestar": ("BE", "Be star (emission-line B star)"),
    "herbigstar": ("YSO", "Herbig Ae/Be star (young stellar object)"),
    "ttauri": ("YSO", "T Tauri star (young stellar object)"),
    "reddwarfemstar": ("DME", "active M dwarf (dMe)"),
    "wc": ("WR", "Wolf-Rayet star (WC)"),
    "wn": ("WR", "Wolf-Rayet star (WN)"),
    "planetarynebula": ("PN", "planetary nebula (central star)"),
}


def emission_line_class(row):
    """(kind, name, basis) from Gaia ESP-ELS, or None."""
    label = _text(row, "gaia_dr3__classlabel_espels", "classlabel_espels")
    if not label:
        return None
    flag = _num(row, "gaia_dr3__classlabel_espels_flag", "classlabel_espels_flag")
    hit = ESP_ELS.get(label.replace(" ", "").replace("_", "").lower())
    if hit is None or (flag is not None and flag > 2):
        return None
    return (
        hit[0],
        hit[1],
        f"Gaia ESP-ELS class {label}"
        + (f" (flag {flag:.0f}: top-two probability gap >= 0.4)" if flag is not None else ""),
    )


GIANT_MAX_LOGG = 3.5


def _logg_class(logg, lim):
    """Ciardi et al. (2011) separate dwarfs from evolved stars; the overlap
    near log g 3.7 is "likely dominated by sub-giants", so below their
    boundary only log g < 3.5 is a giant (III), the rest IV (2.17.0)."""
    if logg > lim:
        return "V"
    return "III" if logg < GIANT_MAX_LOGG else "IV"


def _giant_logg_limit(teff):
    # Ciardi et al. (2011, AJ 141, 108) dwarf / evolved-star boundary for Kepler targets.
    return 4.0 if teff <= 4250 else (5.2 - 2.8e-4 * teff if teff < 6000 else 3.5)


def star_luminosity_class(row, num):
    pos = cmd_position(row)
    if pos is not None:
        mg, dm, bprp0 = pos
        # Unresolved equal-mass binaries sit up to 0.75 mag above the MS
        # (Hurley & Tout 1998); metallicity/age spread adds ~0.3 mag.
        # White dwarfs: the Gentile Fusillo et al. (2021, Eq. 1) locus
        # M_G > 6 + 5 (BP-RP), the same cut as branches/star.py (2.17.0;
        # was dM > 3, which reaches ~2 mag above the WD locus).
        if mg > 6.0 + 5.0 * bprp0:
            return (
                None,
                "GAIA_CMD",
                f"M_G = {mg:.2f} at (BP-RP)0 = {bprp0:.2f}: white-dwarf region (Gentile Fusillo+2021)",
            )
        if dm > 1.0:
            # Metal-poor subdwarfs lie 1-2 mag below the solar-metallicity
            # sequence (Kuiper 1939; Gizis 1997).  On the SDSS benchmark stars
            # with 1 < dM <= 3 have median GSP-Phot [M/H] = -1.4 (MS: -0.66).
            # Blue objects there are hot subdwarfs, WD+MS binaries or CVs
            # (Culpan et al. 2022), not metal-poor dwarfs.
            if bprp0 < 0.3 or dm > 3.0:
                return (
                    None,
                    "GAIA_CMD",
                    f"M_G = {mg:.2f}, {dm:+.2f} mag below the dwarf sequence at (BP-RP)0 = {bprp0:.2f} (hot subdwarf / WD+MS region)",
                )
            return "VI", "GAIA_CMD", f"M_G = {mg:.2f}, {dm:+.2f} mag below the dwarf sequence (subdwarf)"
        if dm > -1.0:
            return "V", "GAIA_CMD", f"M_G = {mg:.2f}, {dm:+.2f} mag from the dwarf sequence"
        # Giants proper are >= 3 mag above the dwarf sequence at red colours;
        # Ruiz-Dern et al. (2018) select red giants with M_G < 4.  Between,
        # red stars are subgiants, pre-main-sequence stars or overluminous
        # binaries (2.17.0; was "III" for any red star 1 mag above).
        if dm <= -3.0 or (mg < 4.0 and dm <= -2.5) or (mg < 4.0 and bprp0 >= 1.3):
            return "III", "GAIA_CMD", f"M_G = {mg:.2f}, {dm:+.2f} mag above the dwarf sequence"
        return (
            "IV",
            "GAIA_CMD",
            f"M_G = {mg:.2f}, {dm:+.2f} mag above the dwarf sequence (subgiant / pre-main-sequence)",
        )
    sp = spectro_params(row)
    if sp is not None:
        lim = _giant_logg_limit(sp["teff"])
        name = {"LAMOST": "LAMOST LASP", "GSPSPEC": "Gaia GSP-Spec"}[sp["source"]]
        return (
            _logg_class(sp["logg"], lim),
            f"{sp['source']}_LOGG",
            f"{name} log g = {sp['logg']:.2f} at Teff = {sp['teff']:.0f} K vs giant boundary {lim:.2f} (spectroscopic)",
        )
    teff, logg = _num(row, "gaia_dr3__teff_gspphot", "teff_gspphot"), _num(
        row, "gaia_dr3__logg_gspphot", "logg_gspphot"
    )
    if teff is not None and logg is not None:
        lim = _giant_logg_limit(teff)
        return _logg_class(logg, lim), "GAIA_LOGG", f"GSP-Phot log g = {logg:.2f} vs giant boundary {lim:.2f}"
    return None, None, "no parallax or log g"


# Tangential-velocity selections of Babusiaux et al. (2018, A&A 616, A10,
# Gaia DR2 HRDs): thin disc V_T < 40, thick disc 60-150, halo > 200 km/s.
# Between the windows the population is left open.
POPULATION_VT = (("THIN_DISC", 0.0, 40.0), ("THICK_DISC", 60.0, 150.0), ("HALO", 200.0, float("inf")))
RUWE_BINARY = 1.4  # Lindegren et al. (2018); Belokurov et al. (2020)


def star_tags(row):
    tags = []
    plx, eplx = _num(row, "gaia_dr3__parallax", "parallax"), _num(row, "gaia_dr3__parallax_error", "parallax_error")
    pmra, pmdec = _num(row, "gaia_dr3__pmra", "pmra"), _num(row, "gaia_dr3__pmdec", "pmdec")
    if None not in (plx, eplx, pmra, pmdec) and plx > 0 and eplx > 0 and plx / eplx >= 5:
        vt = 4.74047 * math.hypot(pmra, pmdec) / plx
        for pop, lo, hi in POPULATION_VT:
            if lo <= vt < hi:
                tags.append(
                    {
                        "tag": pop,
                        "label": {"THIN_DISC": "thin-disc star", "THICK_DISC": "thick-disc star", "HALO": "halo star"}[
                            pop
                        ],
                        "rule": "GAIA_VTAN",
                        "basis": f"V_T = {vt:.0f} km/s (Babusiaux+2018 windows 40 / 60-150 / 200)",
                    }
                )
    ruwe = _num(row, "gaia_dr3__ruwe", "ruwe")
    # For AGB stars a high RUWE "more likely reflects detector saturation,
    # stellar size, or convective photocentre shifts than binarity"
    # (Andriantsaralaza et al. 2022): no binary tag for them (2.17.0).
    if ruwe is not None and ruwe > RUWE_BINARY and not agb_candidate(row):
        tags.append(
            {
                "tag": "ASTROMETRIC_BINARY",
                "label": "astrometric binary candidate",
                "rule": "GAIA_RUWE",
                "basis": f"RUWE = {ruwe:.2f} > 1.4 (unresolved companion; Belokurov+2020)",
            }
        )
    # No tag from the Gaia DSC "binary" class (removed 2.17.0): its purity
    # is 0.075 and completeness 0.002 (Delchambre et al. 2023, Table 3; "the
    # results on the binary class are largely meaningless").
    # Distance and motion.
    if plx is not None and eplx is not None and plx > 0 and eplx > 0:
        if plx > 10.0 and plx / eplx >= 10:
            # Inside the Gaia Catalogue of Nearby Stars volume (100 pc;
            # Gaia Collaboration, Smart et al. 2021).
            tags.append(
                {
                    "tag": "NEARBY",
                    "label": f"nearby star ({1000 / plx:.0f} pc)",
                    "rule": "GAIA_PARALLAX",
                    "basis": f"parallax {plx:.2f} +- {eplx:.2f} mas (< 100 pc)",
                }
            )
    if pmra is not None and pmdec is not None and math.hypot(pmra, pmdec) > 150.0:
        tags.append(
            {
                "tag": "HIGH_PM",
                "label": "high-proper-motion star",
                "rule": "GAIA_PM",
                "basis": f"mu = {math.hypot(pmra, pmdec):.0f} mas/yr > 150 (LSPM limit; Lepine & Shara 2005)",
            }
        )
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
                tags.append(
                    {
                        "tag": "RED_CLUMP",
                        "label": "red-clump giant candidate",
                        "rule": "GAIA_RC",
                        "basis": f"M_G = {mg:.2f} vs red clump {m_rc:.2f} at G-Ks = {gk:.2f} (Ruiz-Dern+2018)",
                    }
                )
    # Mid-IR excess over the photosphere (stellar W1-W2 ~ W2-W3 ~ 0, Vega):
    # lower bounds of the Koenig et al. (2012) class II locus.  Dusty discs
    # (YSOs, debris discs) or circumstellar shells (AGB); background
    # galaxies can mimic it.
    w1, w2, w3 = (_wise_vega(row, k) for k in (1, 2, 3))
    ew3 = _num(row, "std_magerr__wise_w3", "allwise__e_W3mag")
    if None not in (w1, w2, w3, ew3) and ew3 < 0.2 and w1 - w2 > 0.25 and w2 - w3 > 1.0:
        tags.append(
            {
                "tag": "IR_EXCESS",
                "label": "infrared-excess star (dust disc / shell candidate)",
                "rule": "WISE_IR_EXCESS",
                "basis": f"W1-W2 = {w1 - w2:.2f} > 0.25, W2-W3 = {w2 - w3:.2f} > 1.0 (Koenig+2012)",
            }
        )
    xr = _catalogs(row) & set(XRAY_CATALOGS)
    if xr:
        # Stellar X-rays trace coronal activity (young / fast rotators / active binaries).
        tags.append({"tag": "XRAY", "label": "X-ray active star", "rule": "XRAY", "basis": ", ".join(sorted(xr))})
    sp = spectro_params(row)
    if sp is not None and sp["feh"] is not None and sp["feh"] < -1.0:
        # Beers & Christlieb (2005): [Fe/H] < -1 metal-poor, < -2 very metal-poor.
        very = sp["feh"] < -2.0
        tags.append(
            {
                "tag": "VERY_METAL_POOR" if very else "METAL_POOR",
                "label": "very metal-poor star" if very else "metal-poor star",
                "rule": f"{sp['source']}_FEH",
                "basis": f"spectroscopic [Fe/H] = {sp['feh']:.2f} ({sp['source']}; Beers & Christlieb 2005)",
            }
        )
    # GSP-Phot [M/H] is not used for the metal-poor tag (2.6.2): against
    # APOGEE DR17 its [M/H] < -1 flag has precision 0.15 / recall 0.14
    # (0-0.25 at any cut), against GSP-Spec 0.78 / 0.89 and LAMOST 0.98 / 0.88.
    els = emission_line_class(row)
    if els is not None:
        tags.append(
            {
                "tag": "EMISSION_LINE",
                "label": "H-alpha emission-line star",
                "rule": "GAIA_ESP_ELS",
                "basis": f"{els[2]}; class label not used (SIMBAD agreement 2-30 %)",
            }
        )
    var = str(row.get("variability_class") or "")
    if var and var not in ("UNKNOWN", "nan", "None"):
        sub = row.get("variability_subtype")
        name = var.replace("_", " ").lower() + (f" ({sub})" if isinstance(sub, str) and sub else "")
        tags.append(
            {
                "tag": f"VAR_{var}",
                "label": f"{name} variable",
                "rule": "VARIABILITY_AXIS",
                "basis": f"variability axis: {row.get('variability_status', '')}",
            }
        )
    return tags


# ------------------------------------------------------------ AGB chemistry
# AGB stars are oxygen-rich (C/O < 1; silicate dust, M-type spectra) or
# carbon-rich (C/O > 1; amorphous-carbon/SiC dust, C-type spectra) after third
# dredge-up.  Order of evidence: spectra / curated types, the Suh (2021)
# catalogue, then photometry.  The photometric models are only applied to AGB
# candidates (long-period variables or AGB physical class): on ordinary stars
# the same colours mean nothing (benchmark stars with J-Ks >= 1 mostly have
# W_RP - W_KJ >= 0.9).
#
# Photometric chemistry (2.6.0): logistic models in agb_chemistry_model.json,
# fitted (benchmark/fit_agb_chemistry.py) on half of two truth sets and
# scored on the other half (benchmark/agb_truth):
#   * Suh (2021) O-AGB / C-AGB stars: IR-selected, dusty;
#   * GCVS Miras / semiregulars / irregulars with literature spectral types
#     (Samus et al. 2017): mostly dust-free M giants.  Without them the 2.5.3
#     models (Suh only) called 60 % of field Gaia LPVs carbon-rich, because
#     "little dust" meant "carbon" in the Suh set.
# Cascade (first model whose inputs exist; saturated WISE bands masked):
#   1. W_RP - W_KJ (Lebzelter et al. 2018), Ks - W3, Gaia LPV C-star flag
#      (Lebzelter et al. 2023): 96.0 % on 3656 stars;
#   2. W_RP - W_KJ, J - Ks, C-star flag: 96.9 % on 1987;
#   3. W_RP - W_KJ, J - Ks: 79.0 % on 614;
#   4. J - Ks, Ks - W3, W1 - W2, W3 - W4: 88.5 % on 26.
#   A Ks - W3 model without the flag was dropped (73.8 %: dusty O-rich and
#   dust-free stars overlap).  Within 0.15 of p = 0.5: "chemistry uncertain".
#   All together: 94.6 % at 83 % coverage (Suh 91.2 %, GCVS 98.3 %; C
#   precision 0.87, O 0.97).  On 23 969 field LPVs in random cones the
#   predicted C fraction is 25.7 % (Gaia C-star flag: 24.4 %).
# The published single cuts did worse on these mostly dust-obscured Galactic
# AGB stars: W_RP - W_KJ >= 0.9 (Mowlavi+2019) 68.5 %, the AllWISE line of
# Lian et al. (2014) 75.4 %; WISE colours alone (46.6 % on stars without
# 2MASS) are not used.  Ks - W3 carries most of the separation: silicate dust
# brightens W3 (O-rich median 1.93 vs C-rich 1.02).
# Silicate (dusty O-rich) AGB: O-rich with Ks - W3 > 1.0 (98.4 % of the Suh
# O-AGB stars; an M-giant photosphere has Ks - W3 near 0).
AGB_DUST_KW3 = 1.0
# Luminosity veto (2.6.0).  AGB stars are brighter than the red clump
# (M_Ks = -1.61; Alves 2000, ApJ 539, 732; Hawkins et al. 2017, MNRAS 471,
# 722).  With a good parallax (S/N >= 5, RUWE < 1.4) a star fainter than
# M_Ks = -1 is not on the AGB.  Measured on the Suh (2021) stars with good
# astrometry: no O-rich AGB star is fainter than M_Ks = -1, but 263 of the
# 1565 "C-rich" ones are (median G - Ks = 2.2 against 5.4 for the bright ones, none
# a Gaia LPV): dwarf and CH carbon stars from the general carbon-star
# catalogue.  Of those, M_G > 5 marks a dwarf carbon star (dC; the screen of
# Li et al. 2024, ApJS 271, 12, LAMOST DR7 carbon stars; Green 2013).
AGB_MAX_MKS = -1.0
DC_MIN_MG = 5.0
# RGB tip: M_Ks = -6.2 (2MASS LMC tip Ks = 12.3 at m - M = 18.5; Nikolaev &
# Weinberg 2000; Ks tip intercept -6.28, Gorski et al. 2018).  The tip is
# colour- and metallicity-dependent (brighter, ~-6.5 to -7, for metal-rich
# disc giants), so this is a conservative value.  Between the clump and the
# tip an LPV can be a red giant (RGB) or an AGB star (early AGB and low-mass
# thermally pulsing AGB stars sit there too), which photometry cannot
# separate: 340 of the
# Gaia DR3 LPVs with good parallaxes in random cones lie there
# (benchmark/evaluate_agb_contamination.py).  They are named "red giant
# (RGB or AGB below the tip)" with luminosity class III instead of AGB.
RGB_TIP_MKS = -6.2
A_KS_PER_A_G = 0.137  # A_K/A_V = 0.114 (Cardelli et al. 1989), A_G/A_V = 0.83
AGB_VARIABILITY = {"LPV", "MIRA"}
WISE_SAT_VEGA = (8.0, 6.7, 3.8, -0.4)
# SIMBAD codes: AB* is the AGB code ("AGB*" is its label; 2.22.0), Mi* is its child.
SIMBAD_AGB = {"AB*", "C*", "S*", "Mi*", "LP*", "OH*", "pA*"}


@lru_cache(maxsize=1)
def _agb_model():
    import json

    try:
        return json.loads((ROOT / "agb_chemistry_model.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def wesenheit_dw(row):
    """W_RP - W_KJ (Gaia RP/BP Vega, 2MASS J/Ks Vega), or None."""
    rp = _num(row, "gaia_dr3__phot_rp_mean_mag", "phot_rp_mean_mag")
    bp = _num(row, "gaia_dr3__phot_bp_mean_mag", "phot_bp_mean_mag")
    j = _num(row, "2mass_psc__Jmag", "allwise__Jmag")
    k = _num(row, "2mass_psc__Kmag", "allwise__Kmag")
    if None in (rp, bp, j, k):
        return None
    return (rp - 1.3 * (bp - rp)) - (k - 0.686 * (j - k))


def agb_features(row):
    """Colour features of the AGB chemistry models (Vega magnitudes)."""
    j = _num(row, "2mass_psc__Jmag", "allwise__Jmag")
    k = _num(row, "2mass_psc__Kmag", "allwise__Kmag")
    w1, w2, w3, w4 = (_wise_vega(row, b) for b in (1, 2, 3, 4))
    # AllWISE saturates at W1 < 8.0, W2 < 6.7, W3 < 3.8, W4 < -0.4 (Vega;
    # Cutri et al. 2012): saturated bands are not used (as in the fit).
    w1, w2, w3, w4 = (None if v is None or v < lim else v for v, lim in zip((w1, w2, w3, w4), WISE_SAT_VEGA))
    cst = gaia_lpv_cstar(row)
    sub = lambda a, b: None if a is None or b is None else a - b
    return {
        "dW": wesenheit_dw(row),
        "kw3": sub(k, w3),
        "jk": sub(j, k),
        "w12": sub(w1, w2),
        "w34": sub(w3, w4),
        "cst": None if cst is None else float(cst),
    }


def gaia_lpv_cstar(row):
    """Gaia DR3 LPV C-star flag where Lebzelter et al. (2023) advise using it:
    G_BP < 19 and 7 < median_delta_wl_rp < 11 (when the collector provides
    it).  True / False, or None without the flag (2.17.0).  On 2,180 Suh
    (2021) AGB stars the raw flag is C-rich for 76.2 %, with G_BP < 19 for
    97.7 % (11.3 % for G_BP >= 19); spurious C flags crowd the faint,
    reddened plane and bulge (Sanders & Matsunaga 2023)."""
    flag = _num(row, "gaia_lpv_is_cstar")
    if flag is None:
        return None
    if flag < 0.5:
        return False
    bp = _num(row, "gaia_dr3__phot_bp_mean_mag", "phot_bp_mean_mag")
    wl = _num(row, "gaia_lpv_median_delta_wl_rp")
    return bp is not None and bp < 19.0 and (wl is None or 7.0 < wl < 11.0)


def agb_candidate(row):
    """Why the object counts as an AGB candidate, or None."""
    if str(row.get("physical_class") or "") == "AGB":
        return "physical axis AGB"
    var = str(row.get("variability_class") or "")
    if var in AGB_VARIABILITY:
        return f"{var} variable"
    if _num(row, "gaia_lpv_frequency", "gaia_lpv_amplitude", "gaia_lpv_is_cstar") is not None:
        return "Gaia DR3 long-period variable"
    ot = _text(row, "simbad__otype")
    if any(c in SIMBAD_AGB for c in OTYPES.lineage(ot)):
        return f"SIMBAD type {ot}"
    return None


def _good_parallax(row):
    plx, eplx = _num(row, "gaia_dr3__parallax", "parallax"), _num(row, "gaia_dr3__parallax_error", "parallax_error")
    ruwe = _num(row, "gaia_dr3__ruwe", "ruwe")
    if None in (plx, eplx) or plx <= 0 or eplx <= 0 or plx / eplx < 5 or (ruwe is not None and ruwe >= RUWE_BINARY):
        return None
    return plx


def abs_mags(row):
    """(M_Ks, M_G) from a good Gaia parallax (S/N >= 5, RUWE < 1.4), either
    None when its magnitude is missing; None without a good parallax."""
    plx = _good_parallax(row)
    if plx is None:
        return None
    dm = 5 * math.log10(plx) - 10
    ag = _ag(row)  # same extinction as cmd_position (2.23.0)
    k = _num(row, "2mass_psc__Kmag", "allwise__Kmag")
    g = _num(row, "gaia_dr3__phot_g_mean_mag", "phot_g_mean_mag")
    return (None if k is None else k + dm - A_KS_PER_A_G * ag), (None if g is None else g + dm - ag)


def _inner_plane(row):
    """|b| < 5 deg and |l| < 30 deg (toward the bulge); False without a position."""
    ra, dec = _num(row, "ra"), _num(row, "dec")
    if ra is None or dec is None:
        return False
    r, d = math.radians(ra), math.radians(dec)
    x, y, z = math.cos(d) * math.cos(r), math.cos(d) * math.sin(r), math.sin(d)
    # ICRS -> Galactic rotation (Hipparcos, ESA 1997)
    gx = -0.0548755604 * x - 0.8734370902 * y - 0.4838350155 * z
    gy = 0.4941094279 * x - 0.4448296300 * y + 0.7469822445 * z
    gz = -0.8676661490 * x - 0.1980763734 * y + 0.4559837762 * z
    b = math.degrees(math.asin(max(-1.0, min(1.0, gz))))
    l = math.degrees(math.atan2(gy, gx))
    return abs(b) < 5.0 and abs(l) < 30.0


def agb_photometric(row):
    """(chem 'C'/'O'/None, probability of C, model name, basis) from the first
    applicable model, or None when no model has its inputs."""
    model = _agb_model()
    if not model:
        return None
    f = agb_features(row)
    for name, m in model["models"].items():
        x = [f.get(k) for k in m["features"]]
        if any(v is None for v in x):
            continue
        z = m["intercept"] + sum(c * v for c, v in zip(m["coef"], x))
        p = 1.0 / (1.0 + math.exp(-max(-700.0, min(700.0, z))))  # no overflow on extreme inputs
        vals = ", ".join(f"{k} = {v:.2f}" for k, v in zip(m["features"], x))
        if abs(p - 0.5) < m.get("abstain_band", model.get("abstain_band", 0.15)):
            return None, p, name, f"{vals}; P(C-rich) = {p:.2f} (uncertain)"
        return ("C" if p >= 0.5 else "O"), p, name, f"{vals}; P(C-rich) = {p:.2f}"
    return None


def agb_chemistry(row):
    """{'chem': 'C'|'O'|'S'|None, 'rule', 'basis', 'confidence', 'dusty'} or None."""
    sp = _text(row, "simbad__sp_type") or ""
    ot = _text(row, "simbad__otype") or ""
    out = None
    if re.match(r"^C[-\d(]|^C$|^C-?[NRJH]", sp) or ot == "C*":
        out = {
            "chem": "C",
            "rule": "SIMBAD_CSTAR",
            "basis": f"SIMBAD {'type C*' if ot == 'C*' else 'spectral type ' + sp}",
        }
    elif re.match(r"^(MS|SC|S)([\d(/ -]|$)", sp) or ot == "S*":
        out = {
            "chem": "S",
            "rule": "SIMBAD_SSTAR",
            "basis": f"SIMBAD {'type S*' if ot == 'S*' else 'spectral type ' + sp}",
        }
    if out is None:
        # Survey spectra: SDSS / LAMOST carbon templates (C2 and CN bands).
        for key, src in (("sdss_dr18_spectroscopy__subclass", "SDSS"), ("lamost_dr_catalog__SubClass", "LAMOST")):
            lab = _text(row, key) or ""
            if lab.upper().startswith("CARBON") and "WD" not in lab.upper():
                out = {"chem": "C", "rule": f"{src}_CSTAR", "basis": f"{src} spectrum subclass {lab} (C2 / CN bands)"}
                break
    if out is None:
        sub = (_text(row, "suh_2021_agb_catalog__agb_subclass", "agb_subclass") or "").upper()
        if sub.startswith(("CAGB", "OAGB")):
            out = {"chem": sub[0], "rule": "SUH2021", "basis": f"Suh (2021) catalogue {sub}"}
    gate = agb_candidate(row)
    if out is None and gate:
        ph = agb_photometric(row)
        if ph is not None:
            chem, p, name, basis = ph
            if chem == "C" and _inner_plane(row):
                # Toward the bulge at low latitude, reddened O-rich LPVs look
                # carbon-rich in dW (Sanders & Matsunaga 2023).  Measured on
                # the Suh + GCVS truth: C calls there 33 % correct (98 of
                # 294), elsewhere 96-99 %; withholding them raises C precision
                # 0.912 -> 0.981 (2.17.0).
                chem, basis = None, f"{basis}; C call withheld at |b| < 5, |l| < 30 deg (extinction)"
            out = {
                "chem": chem,
                "rule": f"AGB_{name}",
                "basis": f"{gate}; {basis}",
                "confidence": None if chem is None else round(max(p, 1 - p), 3),
            }
        elif gaia_lpv_cstar(row):
            # Gated flag alone: C-rich precision 0.977 on the Suh (2021) stars.
            out = {
                "chem": "C",
                "rule": "GAIA_LPV_CSTAR",
                "confidence": 0.977,
                "basis": f"{gate}; Gaia DR3 LPV RP-spectrum C-star flag (Lebzelter et al. 2023)",
            }
    if out is None:
        return None
    out["agb_candidate"] = gate
    mags = abs_mags(row)
    mk, mg = mags if mags else (None, None)
    sp = spectro_params(row)
    if sp is not None and sp["logg"] > 3.5:
        # A spectroscopic dwarf / subgiant (AGB stars have log g < ~1).
        if out["rule"].startswith("AGB_") or out["chem"] is None:
            return None
        out["not_agb"] = f"spectroscopic log g = {sp['logg']:.2f} ({sp['source']}): not a giant"
        out["dwarf"] = sp["logg"] > _giant_logg_limit(sp["teff"])
        out["basis"] = f"{out['basis']}; {out['not_agb']}"
    elif mk is not None and mk > AGB_MAX_MKS:
        if out["rule"].startswith("AGB_") or out["chem"] is None:
            return None  # the photometric models describe AGB stars only
        out["not_agb"] = f"M_Ks = {mk:.2f} fainter than the red clump (AGB stars: M_Ks < {AGB_MAX_MKS})"
        out["dwarf"] = mg is not None and mg > DC_MIN_MG
        if out["dwarf"]:
            out["not_agb"] += f"; M_G = {mg:.2f} > {DC_MIN_MG} (dwarf)"
        out["basis"] = f"{out['basis']}; {out['not_agb']}"
    elif mk is not None and mk > RGB_TIP_MKS:
        out["below_tip"] = True
        out["basis"] = f"{out['basis']}; M_Ks = {mk:.2f} below the RGB tip ({RGB_TIP_MKS}): RGB or AGB"
    kw3 = agb_features(row)["kw3"]
    out["dusty"] = kw3 is not None and kw3 > AGB_DUST_KW3
    return out


AGB_NAME = {
    "C": ("Carbon star (C-rich AGB)", "STAR:C:AGB"),
    "O": ("O-rich AGB star", "STAR:M:AGB"),
    "S": ("S-type star (C/O ~ 1, AGB)", "STAR:S:AGB"),
    None: ("AGB star (chemistry uncertain)", "STAR:?:AGB"),
}


# Chemistry names without "AGB", for stars the luminosity veto rejects (2.23.0:
# "O-rich AGB star" has no "(...)" suffix, so the split left "AGB" in the name).
NON_AGB_NAME = {"C": "Carbon star", "O": "O-rich (M-type) star", "S": "S-type star", None: "Red star"}


LUM_NAME = {
    "V": "dwarf",
    "IV": "subgiant",
    "III": "giant",
    "II": "bright giant",
    "Ib": "supergiant",
    "Ia": "supergiant",
    "VI": "subdwarf",
}


def classify_star(row):
    phys = str(row.get("physical_class") or "")
    sdss = _text(row, "sdss_dr18_spectroscopy__subclass") or ""
    lam = _text(row, "lamost_dr_catalog__SubClass") or ""
    for label, src in ((sdss, "SDSS"), (lam, "LAMOST")):
        u = label.upper()
        if u.startswith("CARBON") and "WD" in u:  # SDSS CarbonWD: DQ white dwarf (C2 bands)
            return _result(
                f"White dwarf ({label})", "STAR:WD", None, f"{src}_SUBCLASS", f"{src} spectrum subclass {label}"
            )
        if u == "CV":
            return _result(
                "Cataclysmic variable", "STAR:CV", None, f"{src}_SUBCLASS", f"{src} spectrum subclass {label}"
            )
        if u.startswith(("WD", "DA", "DB", "DC", "DQ", "DZ", "DO")):
            return _result(
                f"White dwarf ({label})", "STAR:WD", None, f"{src}_SUBCLASS", f"{src} spectrum subclass {label}"
            )
    sp_simbad = _text(row, "simbad__sp_type") or ""
    if re.match(r"^D[ABCOQZX]", sp_simbad):  # MK white-dwarf type (DA3, DB, DQ ...; 2.23.0)
        return _result(
            f"White dwarf ({sp_simbad})", "STAR:WD", None, "SIMBAD_SPTYPE", f"SIMBAD spectral type {sp_simbad}"
        )
    if phys == "WD":
        sub = row.get("physical_subtype")
        return _result(
            "White dwarf" + (f" ({sub})" if isinstance(sub, str) and sub else ""),
            "STAR:WD",
            _num(row, "physical_confidence"),
            "WD_LOCUS",
            "physical axis: Gaia WD locus / DSC",
        )
    if phys == "ULTRACOOL_DWARF":
        teff = _num(row, "gaia_dr3__teff_espucd", "teff_espucd")
        return _result(
            "Ultracool dwarf (M7 or later)" + (f", Teff {teff:.0f} K" if teff else ""),
            "STAR:M:UCD",
            _num(row, "physical_confidence"),
            "ESP_UCD",
            "physical axis: Gaia DR3 ESP-UCD (Sarro+2023) / SIMBAD BD*",
        )
    if phys == "HOT_SUBDWARF":
        # 2.22.0: Gaia CMD hot subluminous star (Culpan et al. 2022) or SIMBAD HS*;
        # the "below the dwarf sequence" class VI does not apply to these.
        return _result(
            "Hot subdwarf (sdO/sdB candidate)",
            "STAR:O:SD",
            _num(row, "physical_confidence"),
            "HOT_SUBLUMINOUS",
            "physical axis: Gaia colour - absolute magnitude (Culpan+2022) / SIMBAD HS*",
        )
    agb = agb_chemistry(row)
    if agb is not None:
        name, code = AGB_NAME[agb["chem"]]
        if agb["chem"] == "O" and agb["dusty"]:
            name = "O-rich AGB star with silicate dust"
        spectral = agb["rule"].startswith(("SIMBAD", "SDSS", "LAMOST"))
        if agb.get("dwarf"):
            name, code = (
                ("Dwarf carbon star (dC)", "STAR:C:V")
                if agb["chem"] == "C"
                else (NON_AGB_NAME[agb["chem"]] + " (dwarf)", code.replace(":AGB", ":V"))
            )
        elif agb.get("not_agb") or (agb["chem"] in ("C", "S") and not agb.get("agb_candidate") and spectral):
            name = NON_AGB_NAME[agb["chem"]]  # carbon dwarfs / CH stars are not AGB stars
            code = code.replace(":AGB", ":?")
        elif agb.get("below_tip"):
            name = {"C": "Carbon giant", "O": "O-rich red giant", "S": "S-type giant", None: "Red giant"}[agb["chem"]]
            name += " (RGB or AGB below the RGB tip)"
            code = code.replace(":AGB", ":III")
        conf = agb.get("confidence", RULE_PRECISION.get(agb["rule"]))
        return _result(name, code, conf, agb["rule"], agb["basis"], agb_chemistry=agb["chem"])
    num, lum, rule, basis = star_spectral_type(row)
    if num is None:
        return _result(None, None, None, None, basis, status="NO_SPECTRAL_INFORMATION")
    if lum is None:
        lum, lrule, lbasis = star_luminosity_class(row, num)
    else:
        lrule, lbasis = "SIMBAD_SPTYPE", "luminosity class from the SIMBAD MK type"
    letter = LETTERS[int(num // 10)]
    # The physical axis' evolved-giant label (RGB / AGB / RED_GIANT; the last
    # since 2.13.0) sets class III unless a spectrum already gives a giant or
    # supergiant class (II, Ib, Ia are more specific than "giant").  2.22.0:
    # RED_GIANT was missing, so a FLAME / CMD giant could read "IV subgiant".
    # 2.23.0: a SIMBAD MK class (from a spectrum) is never replaced by the
    # photometric giant label; spectroscopy outranks photometry here.
    if phys in {"RGB", "AGB", "RED_GIANT"} and lum not in {"III", "II", "Ib", "Ia"} and lrule != "SIMBAD_SPTYPE":
        lum, lrule, lbasis = "III", "PHYSICAL_AXIS", f"physical axis {phys}"
    label = spt_label(num) + (f" {lum}" if lum else "")
    name = f"{letter}-type " + (LUM_NAME.get(lum, "star") if lum else "star")
    conf = RULE_PRECISION.get(rule)
    return _result(
        f"{label} ({name})",
        f"STAR:{letter}:{lum or '?'}",
        conf,
        rule,
        basis,
        spectral_type=spt_label(num),
        spectral_letter=letter,
        luminosity_class=lum,
        luminosity_rule=lrule,
        luminosity_basis=lbasis,
    )


# ------------------------------------------------------------------ GALAXY
# Emission-line diagnostics from the SDSS spectrum: Portsmouth fits
# (emissionLinesPort; Thomas et al. 2013), else MPA-JHU (galSpecLine /
# galSpecIndx; Brinchmann et al. 2004, Kauffmann et al. 2003), merged by
# Get_data/sdss_spectroscopy.py into line_* columns (EW positive in emission).  The SDSS
# pipeline subclass (Bolton et al. 2012) needs all lines at 10 sigma; these
# rules reach the weaker-line galaxies it leaves empty.
#  * BPT with S/N >= 3 in H-beta, [O III] 5007, H-alpha, [N II] 6584
#    (Baldwin, Phillips & Terlevich 1981): AGN above the maximum-starburst
#    line y = 0.61 / (x - 0.47) + 1.19 (Kewley et al. 2001); star-forming
#    below y = 0.61 / (x - 0.05) + 1.3 (Kauffmann et al. 2003); composite
#    between.  x = log [N II]/H-alpha, y = log [O III]/H-beta.  Seyfert vs
#    LINER on the same diagram: y > 1.05 x + 0.45 (Schawinski et al. 2007).
#  * WHAN (Cid Fernandes et al. 2011, MNRAS 413, 1687), applied first for
#    weak H-alpha: EW(H-alpha) < 3 A retired, < 0.5 A with EW([N II]) < 0.5 A
#    passive (both quiescent: no star formation, ionised by old stars).
#    When H-beta / [O III] are too weak for the BPT, [N II]/H-alpha alone
#    (Stasinska et al. 2006, MNRAS 371, 972): x < -0.4 star-forming, -0.4 to
#    -0.2 composite, > -0.2 AGN (strong EW > 6 A, weak 3-6 A).
#  * 4000 A break with no emission measured: Dn4000 >= 1.6 old stellar
#    population (Kauffmann et al. 2003 bimodality; narrow index of Balogh
#    et al. 1999).
LINE_SNR = 3.0
D4000_OLD = 1.6


# Line sources in order of precedence: SDSS (Portsmouth / MPA-JHU), then DESI
# DR1 FastSpecFit (2.7.0; Get_data/desi_fastspec.py writes the same line_*
# columns: fluxes, 1-sigma errors, EW positive in emission, Dn4000).
LINE_SOURCES = (("sdss_dr18_spectroscopy__", "SDSS"), ("desi_dr1_fastspecfit__", "DESI"))


def _line(row, name, prefix="sdss_dr18_spectroscopy__"):
    """(flux, S/N) of an emission line from one source, or (None, None)."""
    f = _num(row, f"{prefix}line_{name}_flux")
    e = _num(row, f"{prefix}line_{name}_flux_err")
    if f is None:
        return None, None
    return f, (f / e if e and e > 0 else None)


def galaxy_lines(row):
    """(activity, rule, basis) from the first line source that decides, or None."""
    for prefix, tag in LINE_SOURCES:
        r = _galaxy_lines(row, prefix, tag)
        if r is not None:
            return r
    return None


def _galaxy_lines(row, prefix, tag):
    ha, ha_sn = _line(row, "ha", prefix)
    hb, hb_sn = _line(row, "hb", prefix)
    o3, o3_sn = _line(row, "oiii5007", prefix)
    n2, n2_sn = _line(row, "nii6584", prefix)
    good = lambda f, sn: f is not None and f > 0 and sn is not None and sn >= LINE_SNR
    w = ew_ha = _num(row, f"{prefix}line_ha_ew")
    wn = _num(row, f"{prefix}line_nii6584_ew")
    # Weak H-alpha first: LINER-like ratios with EW(Ha) < 3 A come from old
    # stars, not an AGN (retired galaxies; Cid Fernandes et al. 2010, 2011).
    if w is not None and w < 0.5 and wn is not None and wn < 0.5:
        return "QUIESCENT", f"{tag}_WHAN", f"EW(Ha) = {w:.1f} A, EW([N II]) = {wn:.1f} A < 0.5 A (passive; WHAN)"
    if w is not None and w < 3.0:
        return "QUIESCENT", f"{tag}_WHAN", f"EW(Ha) = {w:.1f} A < 3 A (retired; WHAN)"
    if all(good(f, sn) for f, sn in ((ha, ha_sn), (hb, hb_sn), (o3, o3_sn), (n2, n2_sn))):
        x, y = math.log10(n2 / ha), math.log10(o3 / hb)
        pos = f"log [N II]/Ha = {x:.2f}, log [O III]/Hb = {y:.2f}"
        if x >= 0.47 or y > 0.61 / (x - 0.47) + 1.19:
            kind = "Seyfert" if y > 1.05 * x + 0.45 else "LINER"
            return "AGN", f"{tag}_LINES_BPT", f"{pos}: above Kewley+2001 ({kind}-like, Schawinski+2007)"
        if x < 0.05 and y < 0.61 / (x - 0.05) + 1.3:
            return "STAR_FORMING", f"{tag}_LINES_BPT", f"{pos}: below Kauffmann+2003"
        return "COMPOSITE", f"{tag}_LINES_BPT", f"{pos}: between Kauffmann+2003 and Kewley+2001"
    if w is not None and good(ha, ha_sn) and n2 is not None and n2 > 0:
        # [N II]/Ha alone (Stasinska et al. 2006): < -0.4 star-forming,
        # -0.4 to -0.2 composite, > -0.2 AGN.  WHAN calls everything above
        # -0.4 AGN, but on the benchmark 96 of 104 such SDSS star-forming
        # galaxies are star-forming / composite in the Portsmouth BPT.
        x = math.log10(n2 / ha)
        pos = f"EW(Ha) = {w:.1f} A, log [N II]/Ha = {x:.2f}"
        if x < -0.4:
            return "STAR_FORMING", f"{tag}_WHAN", f"{pos} < -0.4 (WHAN; Stasinska+2006)"
        if x < -0.2:
            return "COMPOSITE", f"{tag}_WHAN", f"{pos} in -0.4..-0.2 (composite; Stasinska+2006)"
        kind = "strong" if w > 6.0 else "weak"
        return "AGN", f"{tag}_WHAN", f"{pos} >= -0.2 ({kind} AGN; WHAN, Stasinska+2006)"
    d4 = _num(row, f"{prefix}d4000_n")
    if d4 is not None and d4 >= D4000_OLD and ew_ha is None:
        return "QUIESCENT", f"{tag}_D4000", f"Dn4000 = {d4:.2f} >= {D4000_OLD} (old stellar population)"
    return None


# WISE W2-W3 sequence (Jarrett et al. 2017, ApJ 836, 182; 2019, ApJS 245,
# 25): spheroids < ~2, intermediate discs 2-3.5, star-forming discs > 3.5.
# 2.18.0: SF cut 3.0 -> 3.5 (the published boundary); on the SDSS test split
# its precision rises 0.754 -> 0.871 and activity accuracy 79.5 -> 87.9 %,
# while coverage falls 42.3 -> 31.8 % (galaxies at 3-3.5 stay unlabelled).
# Quiescent < 1.5 (Jarrett et al. 2011 spheroid colour; measured 0.70/0.83).
# No K-correction: WISE colours change at z > ~0.1.
W23_SF = 3.5
W23_Q = 1.5


def galaxy_activity(row):
    sub = (_text(row, "sdss_dr18_spectroscopy__subclass") or "").upper()
    # Broad lines first: a narrow-line fit misses broad H-alpha (29 SDSS
    # BROADLINE objects look WHAN-retired).  Otherwise the line diagnostics
    # (WHAN -> BPT) decide before the SDSS pipeline subclass (2.18.0): the
    # pipeline's SF/AGN line (Bolton et al. 2012) is neither Kewley nor
    # Kauffmann, so composites become "AGN", and it has no retired-galaxy
    # test (Cid Fernandes et al. 2011).  Agreement with the Portsmouth BPT on
    # 1,190 SDSS galaxies with a subclass: 84.1 -> 86.9 %.
    if "BROADLINE" in sub:
        return "AGN", "SDSS_BPT", f"SDSS spectrum subclass {sub} (broad lines)"
    lines = galaxy_lines(row)
    if lines is not None:
        return lines
    if sub:
        if "AGN" in sub:
            return "AGN", "SDSS_BPT", f"SDSS spectrum subclass {sub} (BPT)"
        if "STARBURST" in sub:
            return "STARBURST", "SDSS_BPT", f"SDSS spectrum subclass {sub} (H-alpha EW > 50 A)"
        if "STARFORMING" in sub:
            return "STAR_FORMING", "SDSS_BPT", f"SDSS spectrum subclass {sub} (BPT)"
    ot = _text(row, "simbad__otype")
    hit, _c = OTYPES.resolve(ot, SIMBAD_GALAXY)
    if hit is not None:
        act, name = hit
        return act, "SIMBAD_OTYPE", f"SIMBAD type {ot} ({name})"
    w1, w2, w3 = (_wise_vega(row, k) for k in (1, 2, 3))
    ew3 = _num(row, "std_magerr__wise_w3", "allwise__e_W3mag")
    # Stern et al. (2012) is calibrated on S/N >= 10 photometry (as in the
    # Stage-4 rule WISE-AGN-001; 2.18.0).
    s1, s2 = _num(row, "allwise__snr1"), _num(row, "allwise__snr2")
    snr_ok = s1 is None or s2 is None or min(s1, s2) >= 10
    if w1 is not None and w2 is not None and w1 - w2 >= 0.8 and w2 < 15.05 and snr_ok:
        return "AGN", "WISE_STERN12", f"W1-W2 = {w1 - w2:.2f} >= 0.8 with W2 = {w2:.2f} < 15.05"
    if w2 is not None and w3 is not None:
        c = w2 - w3
        if ew3 is not None and ew3 < 0.2:
            if c > W23_SF:
                return "STAR_FORMING", "WISE_W23_SF", f"W2-W3 = {c:.2f} > {W23_SF} (star-forming disc)"
            if c < W23_Q:
                return "QUIESCENT", "WISE_W23_Q", f"W2-W3 = {c:.2f} < {W23_Q} (spheroid)"
        elif ew3 is None and c < W23_Q:
            # AllWISE W3 upper limit: the true W2-W3 is bluer still.
            return "QUIESCENT", "WISE_W23_UL", f"W2-W3 < {c:.2f} (W3 upper limit) < 1.5"
    nuv = _mag(row, "std_mag__galex_nuv", raw_mag_keys=("galex_ais__NUVmag",))
    r = _mag(row, "std_mag__ls_r", "desi_legacy_surveys_dr10__flux_r")
    if r is None:
        r = _mag(
            row,
            "std_mag__ps1kron_r",
            raw_mag_keys=("pan_starrs1_dr2_meanobject__rMeanKronMag", "sdss_dr18_photoobj__petroMag_r"),
        )
    if nuv is not None and r is not None:
        ebv = _ebv(row) or 0.0
        # A_NUV / E(B-V) = 8.2 (Wyder et al. 2007, Cardelli et al. 1989 R_V = 3.1).
        nuvr = nuv - r - (8.2 - 2.165) * ebv
        if nuvr > 5.0:
            # Red sequence NUV-r > 5 (Salim 2014; Wyder et al. 2007).  Kaviraj
            # et al. (2007) put recent star formation below 5.5, so 5-5.5 is
            # "quiescent" on the red sequence, not necessarily dead.
            return "QUIESCENT", "GALEX_NUVR", f"(NUV-r)0 = {nuvr:.2f} > 5 (red sequence)"
        if nuvr > 4.0:
            # Green valley between the blue cloud and red sequence (Salim 2014,
            # SerAJ 189, 1: 4 < NUV-r < 5; Wyder et al. 2007).
            return "GREEN_VALLEY", "GALEX_NUVR_GV", f"4 < (NUV-r)0 = {nuvr:.2f} <= 5 (green valley)"
    return None, None, "no spectrum, mid-IR or UV activity indicator"


# ------------------------------------------------- distances (flat LCDM)
H0, OMEGA_M = 70.0, 0.3  # cosmology of the SDSS DR7 quasar catalogue (Schneider+2010)


@lru_cache(maxsize=4096)
def luminosity_distance_mpc(z: float) -> float:
    zz = np.linspace(0.0, z, 257)
    e = np.sqrt(OMEGA_M * (1 + zz) ** 3 + (1 - OMEGA_M))
    trap = getattr(np, "trapezoid", None) or np.trapz  # numpy < 2.0
    dc = (299792.458 / H0) * trap(1.0 / e, zz)
    return float((1 + z) * dc)


def distance_modulus(z: float) -> float:
    return 5 * math.log10(luminosity_distance_mpc(z) * 1e6) - 5


def _optical_gr(row):
    """Dereddened (g, r) AB magnitudes: Legacy Surveys, else SDSS model mags."""
    ebv = _ebv(row) or 0.0
    g, r = _mag(row, "std_mag__ls_g", "desi_legacy_surveys_dr10__flux_g"), _mag(
        row, "std_mag__ls_r", "desi_legacy_surveys_dr10__flux_r"
    )
    if g is not None and r is not None:
        return g - 3.214 * ebv, r - 2.165 * ebv
    g = _mag(row, "std_mag__sdss_g", raw_mag_keys=("sdss_dr18_photoobj__modelMag_g",))
    r = _mag(row, "std_mag__sdss_r", raw_mag_keys=("sdss_dr18_photoobj__modelMag_r",))
    if g is not None and r is not None:
        return g - 3.303 * ebv, r - 2.285 * ebv
    return None, None


SIMBAD_ENVIRONMENT = {
    "IG": ("INTERACTING", "interacting galaxy"),
    "PaG": ("PAIR", "galaxy pair"),
    "GiP": ("PAIR", "galaxy in a pair"),
    "GiG": ("GROUP", "galaxy in a group"),
    "GiC": ("CLUSTER", "galaxy in a cluster"),
    "BiC": ("BCG", "brightest cluster galaxy"),
    "LSB": ("LSB", "low-surface-brightness galaxy"),
    "rG": ("RADIO_GALAXY", "radio galaxy"),
}


# Fibre aperture (Kewley, Jansen & Geller 2005, PASP 117, 227): the 3"
# SDSS fibre captures > 20 % of the galaxy light only at z > 0.04; the 1.5"
# DESI fibre needs about twice the distance.  Below that a line class
# describes the nucleus (e.g. a nuclear LINER in a star-forming disc).
APERTURE_MIN_Z = {"SDSS": 0.04, "DESI": 0.08}
# Radio AGN (2.18.0): below L1.4 ~ 1e23 W/Hz star-forming galaxies dominate
# radio samples (Mauch & Sadler 2007; Best & Heckman 2012), so a radio
# detection of a quiescent galaxy is an AGN candidate only above it.
RADIO_AGN_MIN_L14 = 1e23


def radio_luminosity_w_hz(flux_mjy, z, alpha=-0.7):
    """L_1.4GHz = 4 pi D_L^2 S (1 + z)^(-1 - alpha), S_nu ~ nu^alpha."""
    d_m = luminosity_distance_mpc(z) * 3.0857e22
    return 4 * math.pi * d_m * d_m * flux_mjy * 1e-29 * (1 + z) ** (-1 - alpha)


def galaxy_tags(row, activity, activity_rule=None):
    tags = []
    z_spec = spectroscopic_z(row)
    src = (activity_rule or "").split("_")[0]
    if (
        src in APERTURE_MIN_Z
        and (activity_rule or "").endswith(("_LINES_BPT", "_WHAN", "_D4000"))
        and z_spec is not None
        and 0 < z_spec < APERTURE_MIN_Z[src]
    ):
        tags.append(
            {
                "tag": "APERTURE_NUCLEAR",
                "label": "line class of the nucleus (fibre covers < 20 % of the light)",
                "rule": "FIBRE_APERTURE",
                "basis": f"{src} fibre at z = {z_spec:.4f} < {APERTURE_MIN_Z[src]} (Kewley+2005)",
            }
        )
    sub = (_text(row, "sdss_dr18_spectroscopy__subclass") or "").upper()
    ot = _text(row, "simbad__otype")
    # 2.22.0: the rule / basis name the source that actually fired (a SIMBAD
    # Sy1 / Sy2 with an unrelated SDSS subclass was reported as SDSS).
    sdss1 = "BROADLINE" in sub and "AGN" in sub
    sdss2 = sub == "AGN"
    if sdss1 or ot == "Sy1":
        tags.append(
            {
                "tag": "AGN_TYPE1",
                "label": "type 1 (broad-line) AGN",
                "rule": "SDSS_BROADLINE" if sdss1 else "SIMBAD_OTYPE",
                "basis": f"SDSS subclass {sub}" if sdss1 else "SIMBAD Sy1",
            }
        )
    elif sdss2 or ot == "Sy2":
        tags.append(
            {
                "tag": "AGN_TYPE2",
                "label": "type 2 (narrow-line) AGN",
                "rule": "SDSS_BPT" if sdss2 else "SIMBAD_OTYPE",
                "basis": "BPT AGN without broad lines" if sdss2 else "SIMBAD Sy2",
            }
        )
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
            tags.append(
                {
                    "tag": "DWARF",
                    "label": f"dwarf galaxy (M_B = {mb:.1f})",
                    "rule": "ABS_MAG_TAMMANN",
                    "basis": f"M_B = {mb:.2f} > -16 at z = {z:.4f} (Tammann 1994)",
                }
            )
        elif mb < -21.0:
            tags.append(
                {
                    "tag": "LUMINOUS",
                    "label": f"luminous galaxy (M_B = {mb:.1f})",
                    "rule": "ABS_MAG",
                    "basis": f"M_B = {mb:.2f} < -21 at z = {z:.4f} (brighter than L*: M*_bJ = -19.66 + 5 log h ~ -20.4, Norberg et al. 2002)",
                }
            )
    z = spectroscopic_z(row)
    ba = _num(row, "sga_2020__sga_ba", "sga_ba")
    if ba is not None and _num(row, "sga_2020__catalog_object_id") is not None:
        # Thin-disc inclination cos^2 i = (q^2 - q0^2) / (1 - q0^2), q0 = 0.2
        # (Hubble 1926; Holmberg 1958): b/a <= 0.3 -> i >~ 77 deg.
        q0 = 0.2
        inc = math.degrees(math.acos(math.sqrt(max(min((ba * ba - q0 * q0) / (1 - q0 * q0), 1.0), 0.0))))
        if ba <= 0.3:
            tags.append(
                {
                    "tag": "EDGE_ON",
                    "label": f"edge-on galaxy (i ~ {inc:.0f} deg)",
                    "rule": "SGA_AXIS_RATIO",
                    "basis": f"SGA b/a = {ba:.2f}, inclination from Hubble (1926) with q0 = 0.2",
                }
            )
        elif ba >= 0.85:
            tags.append(
                {
                    "tag": "FACE_ON",
                    "label": f"face-on galaxy (i ~ {inc:.0f} deg)",
                    "rule": "SGA_AXIS_RATIO",
                    "basis": f"SGA b/a = {ba:.2f}",
                }
            )
    if z is not None and z > 0:
        tags.append(
            {
                "tag": "SPEC_Z",
                "label": f"spectroscopic z = {z:.4f}",
                "rule": "SPEC_Z",
                "basis": f"distance {luminosity_distance_mpc(z):.0f} Mpc (flat LCDM, H0 = 70)",
            }
        )
    flux, src = radio_14ghz_mjy(row)
    lum = radio_luminosity_w_hz(flux, z_spec) if flux is not None and z_spec is not None and z_spec > 0 else None
    if flux is not None and activity == "QUIESCENT" and lum is not None and lum > RADIO_AGN_MIN_L14:
        # Radio emission from a galaxy without star formation is AGN-powered
        # (radio-mode AGN in early types; Best & Heckman 2012).
        tags.append(
            {
                "tag": "RADIO_AGN",
                "label": "radio-loud AGN candidate",
                "rule": "RADIO_IN_QUIESCENT",
                "basis": f"{src} {flux:.2f} mJy, L1.4 = {lum:.1e} W/Hz > 1e23 in a quiescent galaxy",
            }
        )
    elif flux is not None:
        tags.append(
            {"tag": "RADIO", "label": "radio source", "rule": "RADIO_DETECTED", "basis": f"{src} {flux:.2f} mJy"}
        )
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
        return (
            ("EARLY_TYPE" if n >= 2.5 else "DISK"),
            "LS_SERSIC",
            f"Legacy Surveys Sersic n = {n:.2f} (early type if >= 2.5)",
        )
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


ACT_NAME = {
    "AGN": "AGN host",
    "STARBURST": "starburst",
    "STAR_FORMING": "star-forming",
    "QUIESCENT": "quiescent",
    "GREEN_VALLEY": "green-valley",
    "COMPOSITE": "composite (star-forming + AGN)",
}
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
    return _result(
        name,
        f"GALAXY:{act or '?'}:{prof or '?'}",
        RULE_PRECISION.get(arule) if act else None,
        arule or prule,
        "; ".join(b for b in (abasis if act else None, pbasis if prof else None) if b),
        activity=act,
        activity_rule=arule,
        profile=prof,
        profile_rule=prule,
    )


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
    qhit, qcode = OTYPES.resolve(ot, SIMBAD_QSO)
    if qhit is not None and qcode != "QSO":
        parts.append(qhit)
        rules.append("SIMBAD_OTYPE")
        basis.append(f"SIMBAD type {ot}")
    flux, src = radio_14ghz_mjy(row)
    i = qso_i_mag(row)
    radio = None
    if flux is not None and i is not None:
        t = -2.5 * math.log10(flux * 1e-3 / 3631.0)
        ri = 0.4 * (i - t)
        radio = "RADIO_LOUD" if ri > 1 else "RADIO_QUIET"
        rules.append("RADIO_RI")
        basis.append(f"R_i = {ri:.2f} ({src} {flux:.2f} mJy, i = {i:.2f}; loud if > 1)")
    elif flux is not None:
        radio = "RADIO_DETECTED"
        rules.append("RADIO_DETECTED")
        basis.append(f"{src} {flux:.2f} mJy, no i-band magnitude")
    xray = bool(_catalogs(row) & set(XRAY_CATALOGS))
    if xray:
        rules.append("XRAY")
        basis.append("X-ray counterpart: " + ", ".join(sorted(_catalogs(row) & set(XRAY_CATALOGS))))
    z = spectroscopic_z(row)
    zc = None
    if z is not None and z > 0:
        zc = "HIGH_Z" if z >= 2.1 else "LOW_Z"
        rules.append("SPEC_Z")
        basis.append(f"spectroscopic z = {z:.3f}")
    if not rules:
        return _result(
            None, None, None, None, "no radio, X-ray, redshift or SIMBAD type", status="NO_SUBCLASS_EVIDENCE"
        )
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
    return _result(
        name,
        f"QSO:{radio or '?'}:{zc or '?'}:{'X' if xray else '-'}",
        None,
        rules[0],
        "; ".join(basis),
        radio=radio,
        xray=xray,
        redshift=z,
        redshift_class=zc,
    )


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
        tags.append(
            {
                "tag": "QUASAR_LUMINOSITY" if quasar else "SEYFERT_LUMINOSITY",
                "label": ("quasar-luminosity" if quasar else "Seyfert-luminosity AGN") + f" (M_i(z=2) = {mi2:.1f})",
                "rule": "ABS_MAG_RICHARDS06",
                "basis": f"i = {i:.2f}, z = {z:.3f}, M_i(z=2) = {mi2:.2f}",
            }
        )
    if z is not None and z >= 5.0:
        tags.append(
            {
                "tag": "VERY_HIGH_Z",
                "label": f"very-high-redshift quasar (z = {z:.2f})",
                "rule": "SPEC_Z",
                "basis": "z >= 5: reionisation-era quasar (Fan et al. 2001, 2006)",
            }
        )
    # Obscured (red) quasar: R - [4.5] > 6.1 (Vega; Hickox et al. 2007), with
    # R = r - 0.1837 (g - r) - 0.0971 (Lupton 2005) and W2 for [4.5].
    g, r = _optical_gr(row)
    w2 = _wise_vega(row, 2)
    if g is not None and r is not None and w2 is not None:
        rv = r - 0.1837 * (g - r) - 0.0971
        if rv - w2 > 6.1:
            tags.append(
                {
                    "tag": "OBSCURED",
                    "label": "obscured (red) quasar candidate",
                    "rule": "HICKOX07",
                    "basis": f"R - W2 = {rv - w2:.2f} > 6.1 (Vega; Hickox+2007)",
                }
            )
    ot = _text(row, "simbad__otype")
    if OTYPES.is_a(ot, "Bla"):
        tags.append(
            {
                "tag": "BLAZAR",
                "label": SIMBAD_QSO.get(ot, "blazar"),
                "rule": "SIMBAD_OTYPE",
                "basis": f"SIMBAD type {ot}",
            }
        )
    return tags


# -------------------------------------------------------------------- main
def classify(row):
    coarse = str(row.get("primary_class") or "UNKNOWN").upper()
    if coarse == "STAR":
        out = classify_star(row)
        tags = star_tags(row) if out.get("code") != "STAR:WD" else []
    elif coarse == "GALAXY":
        out = classify_galaxy(row)
        tags = galaxy_tags(row, out.get("activity"), out.get("activity_rule"))
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
        out["rule"] = tags[0]["rule"]
        out["basis"] = tags[0]["basis"]
        out["code"] = f"{coarse}:?"
    out.setdefault("status", "CLASSIFIED" if out.get("subclass") else "NO_SUBCLASS_EVIDENCE")
    if out.get("subclass") and out.get("status") != "CLASSIFIED":
        out["status"] = "CLASSIFIED"
    return out


@lru_cache(maxsize=1)
def _literature():
    import importlib.util

    spec = importlib.util.spec_from_file_location("v2_literature", ROOT / "literature.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@lru_cache(maxsize=1)
def _unknown_reason():
    import importlib.util

    spec = importlib.util.spec_from_file_location("v2_unknown_reason", ROOT / "unknown_reason.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def annotate(df: pd.DataFrame, rows=None) -> pd.DataFrame:
    import json

    rows = rows if rows is not None else df.to_dict("records")
    # The subclass needs the physical-axis result (WD / giant) of the same row.
    for col in (
        "physical_class",
        "physical_subtype",
        "physical_confidence",
        "physical_status",
        "variability_class",
        "variability_subtype",
        "variability_status",
        "phenomenon_status",
    ):
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
