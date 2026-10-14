"""Physical/evolutionary-state axis with conservative independent evidence."""

from __future__ import annotations
import importlib.util, math
from pathlib import Path

AXIS = "physical"
CLASSES = ("WD", "HOT_SUBDWARF", "ULTRACOOL_DWARF", "RGB", "AGB", "RED_GIANT", "UNKNOWN")
# RED_GIANT (2.13.0): an evolved cool giant (RGB or AGB, not separable without
# asteroseismology or luminosity) from the luminosity class of the sub-class
# classifier (Gaia CMD with parallax S/N >= 5, else spectroscopic log g from
# LAMOST / Gaia GSP-Spec, else Gaia GSP-Phot log g against the Ciardi et al.
# 2011 giant boundary; 96.9-98.3 % agreement with APOGEE DR17, 2.6.2) and
# Teff < 5500 K.  Used where Gaia FLAME gives no validated RGB stage: FLAME
# masses / ages of the Kepler giants are unphysical (median 3.3 Msun,
# 0.3 Gyr; benchmark/flame_giants), so its RGB guardrails reject most.
GIANT_TEFF_MAX = 5500.0
ROOT = Path(__file__).resolve().parents[1]


def _load_branch(name):
    p = ROOT / "branches" / f"{name}.py"
    s = importlib.util.spec_from_file_location(f"classifier_branch_{name}", p)
    if s is None or s.loader is None:
        raise ImportError(p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def _text(row, key):
    v = row.get(key)
    if v is None:
        return None
    v = str(v).strip()
    return None if not v or v.lower() == "nan" else v


def _num(row, key):
    try:
        v = float(row.get(key))
        return v if math.isfinite(v) else None
    except Exception:
        return None


STAR = _load_branch("star")
EVOLVED = _load_branch("evolved_star")
_os = importlib.util.spec_from_file_location("v2_simbad_otypes_phys", ROOT / "simbad_otypes.py")
OTYPES = importlib.util.module_from_spec(_os)
_os.loader.exec_module(OTYPES)
_SUB = None


def _subclass():
    global _SUB
    if _SUB is None:
        p = ROOT / "subclass.py"
        s = importlib.util.spec_from_file_location("classifier_subclass_for_physical", p)
        m = importlib.util.module_from_spec(s)
        s.loader.exec_module(m)
        _SUB = m
    return _SUB


def _teff(row):
    # Spectroscopic Teff only through spectro_params (GSP-Spec flag checks,
    # 2.17.0), else GSP-Phot.
    sp = _subclass().spectro_params(row)
    if sp is not None:
        return sp["teff"]
    for k in ("gaia_dr3__teff_gspphot", "teff_gspphot"):
        v = _num(row, k)
        if v is not None:
            return v
    return None


# HOT_SUBDWARF (2.22.0): hot subluminous star (sdO/sdB, plus some BHB stars,
# hot post-AGB stars and PN central stars) from the Gaia colour - absolute
# magnitude selection of Culpan et al. (2022, A&A 662, A40, Table 1; Gaia
# EDR3, same astrometry and photometry as DR3):
#   -0.7 <= BP-RP <= 0.7, -5 <= G_abs <= 7, parallax > 0,
#   parallax_over_error > 5, |C*| < 0.6 (Riello et al. 2021 corrected excess),
#   main-sequence rejection: the MS region G_abs < 17.7 c^3 - 6.9 c^2 +
#   7.35 c + 1.95 is removed (hot subdwarfs lie below = fainter than it).
# No extinction correction and no parallax zero-point, as in the paper.  Not
# applied: astrometric_sigma5d_max < 1.5 (not collected) and their 5" crowding
# filter.  Their parallax selection is 80-90 % complete for single sdO/Bs;
# contamination by cooler stars is ~10 % (Geier et al. 2019, A&A 621, A38),
# mainly WDs and MS A/B stars.  The reduced-proper-motion selection (28 %
# contamination, 50 % completeness) is not used.  SIMBAD "HS*" (hot subdwarf)
# is the curated route.
HSD_BPRP = (-0.7, 0.7)
HSD_GABS = (-5.0, 7.0)
HSD_MIN_PLX_SNR = 5.0
HSD_MAX_ABS_CSTAR = 0.6


def _gaia(row, key):
    v = _num(row, "gaia_dr3__" + key)
    return v if v is not None else _num(row, key)


def hot_subdwarf_evidence(row):
    c, g, p, pe, ex = (
        _gaia(row, k) for k in ("bp_rp", "phot_g_mean_mag", "parallax", "parallax_error", "phot_bp_rp_excess_factor")
    )
    if None in (c, g, p, pe, ex) or p <= 0 or pe <= 0 or p / pe <= HSD_MIN_PLX_SNR:
        return None
    if not HSD_BPRP[0] <= c <= HSD_BPRP[1]:
        return None
    gabs = g + 5 * math.log10(p) - 10  # parallax in mas
    if not HSD_GABS[0] <= gabs <= HSD_GABS[1]:
        return None
    cstar = ex - (
        1.154360 + 0.033772 * c + 0.032277 * c * c
        if c < 0.5
        else 1.162004 + 0.011464 * c + 0.049255 * c * c - 0.005879 * c**3
    )
    if abs(cstar) >= HSD_MAX_ABS_CSTAR:
        return None
    ms_edge = 17.7 * c**3 - 6.9 * c**2 + 7.35 * c + 1.95
    if gabs < ms_edge:
        return None
    return {
        "kind": "gaia_cmd_hot_subluminous",
        "bp_rp": round(c, 3),
        "abs_g": round(gabs, 2),
        "parallax_over_error": round(p / pe, 1),
        "cstar": round(cstar, 3),
        "ms_rejection_edge": round(ms_edge, 2),
        "rule": "Culpan et al. 2022 Table 1 (criteria 1-4)",
    }


# ULTRACOOL_DWARF (2.22.0): Gaia DR3 ESP-UCD candidate -- Teff < 2700 K from
# the RP spectrum (~M7 and later; Stephens et al. 2009: M7 = 2656 K) --
# with quality category 0 or 1, the two Sarro et al. (2023, A&A 669, A139)
# use for their science sample (first digit of flags_espucd).  Brown dwarf
# vs very-low-mass star needs an age, so only "ultracool dwarf" is claimed.
# SIMBAD BD* (brown dwarf) is the curated route.
UCD_MAX_TEFF = 2700.0
UCD_QUALITY = {0, 1}


def _ucd_quality(v):
    if v is None:
        return None
    t = str(v).strip()
    if not t or t.lower() == "nan" or t.lower() == "<na>":
        return None
    try:
        t = int(float(t))
    except (ValueError, OverflowError):
        return None
    return None if t < 0 else int(str(t).zfill(2)[0])  # archive values 00-21


def ultracool_evidence(row):
    teff = _gaia(row, "teff_espucd")
    if teff is None or teff >= UCD_MAX_TEFF:
        return None
    q = _ucd_quality(row.get("gaia_dr3__flags_espucd", row.get("flags_espucd")))
    if q not in UCD_QUALITY:
        return None
    return {
        "kind": "gaia_dr3_esp_ucd",
        "teff_espucd": round(teff),
        "quality_category": q,
        "rule": "Sarro et al. 2023 (Teff < 2700 K, quality 0/1)",
    }


def classify(row):
    catalogs = _text(row, "catalogs") or ""
    if "Suh 2021 AGB Catalog" in catalogs:
        # Suh (2021) includes visual carbon stars from general lists; with a good
        # parallax, M_Ks > -1 (fainter than the red clump, M_Ks = -1.61) is not an
        # AGB star (dwarf / CH carbon stars; same veto as subclass.agb_chemistry).
        sub_mod = _subclass()
        mags = sub_mod.abs_mags(row)
        mk = mags[0] if mags else None
        if mk is not None and mk > sub_mod.AGB_MAX_MKS:
            return {
                "axis": AXIS,
                "label": "UNKNOWN",
                "confidence": None,
                "status": "SUH2021_MATCH_BELOW_RED_CLUMP",
                "evidence": [
                    {
                        "kind": "suh2021_agb_catalog_counterpart",
                        "abs_ks": round(mk, 2),
                        "note": f"M_Ks = {mk:.2f} > {sub_mod.AGB_MAX_MKS}: fainter than the red clump, not on the AGB",
                    }
                ],
            }
        assoc = _num(row, "association_confidence__suh_2021_agb_catalog")
        sub = _text(row, "agb_subclass")
        if mk is not None and mk > sub_mod.RGB_TIP_MKS:
            # Below the RGB tip an evolved giant can be on either branch: the same
            # "RGB or AGB" call as the sub-class (2.23.0; was AGB here, RGB-or-AGB there).
            return {
                "axis": AXIS,
                "label": "RED_GIANT",
                "confidence": assoc,
                "status": "SUH2021_BELOW_RGB_TIP",
                "evidence": [
                    {
                        "kind": "suh2021_agb_catalog_counterpart",
                        "agb_subclass": sub,
                        "abs_ks": round(mk, 2),
                        "note": f"M_Ks = {mk:.2f} fainter than the RGB tip ({sub_mod.RGB_TIP_MKS}): RGB or AGB",
                    }
                ],
            }
        return {
            "axis": AXIS,
            "label": "AGB",
            "confidence": assoc,
            "status": "SUH2021_AGB_CATALOG_MATCH",
            "evidence": [
                {
                    "kind": "suh2021_agb_catalog_counterpart",
                    "agb_subclass": sub,
                    "position_basis": _text(row, "position_basis"),
                    "association_confidence": assoc,
                    "score_semantics": "raw association score; not calibrated posterior",
                }
            ],
        }
    simbad = _text(row, "otype")
    # SIMBAD codes through the hierarchy (2.22.0): the AGB code is AB* ("AGB*"
    # is its label, so the old test never fired); Mira (Mi*) is an AB* child.
    # A curated white dwarf (2.23.0): without it, a WD the Gaia HR gate
    # abstained on was named a hot main-sequence star by its colour.
    if OTYPES.is_a(simbad, "WD*"):
        return {
            "axis": AXIS,
            "label": "WD",
            "confidence": None,
            "status": "SIMBAD_CURATED_WD",
            "evidence": [{"kind": "simbad_physical_type", "otype": simbad}],
        }
    if OTYPES.is_a(simbad, "HS*"):
        return {
            "axis": AXIS,
            "label": "HOT_SUBDWARF",
            "confidence": None,
            "status": "SIMBAD_CURATED_HOT_SUBDWARF",
            "evidence": [{"kind": "simbad_physical_type", "otype": "HS*"}],
        }
    if OTYPES.is_a(simbad, "BD*"):
        return {
            "axis": AXIS,
            "label": "ULTRACOOL_DWARF",
            "confidence": None,
            "status": "SIMBAD_CURATED_BROWN_DWARF",
            "evidence": [{"kind": "simbad_physical_type", "otype": "BD*"}],
        }
    if OTYPES.is_a(simbad, "AB*"):
        return {
            "axis": AXIS,
            "label": "AGB",
            "confidence": None,
            "status": "SIMBAD_CURATED_AGB",
            "evidence": [{"kind": "simbad_physical_type", "otype": simbad}],
        }
    coarse = str(row.get("primary_class", "")).strip().upper()
    if coarse in {"GALAXY", "QSO"}:
        return {
            "axis": AXIS,
            "label": "UNKNOWN",
            "confidence": None,
            "status": "NOT_STELLAR_ROUTE",
            "evidence": [{"kind": "coarse_route", "primary_class": coarse}],
        }
    ucd = ultracool_evidence(row)
    if ucd is not None:
        return {
            "axis": AXIS,
            "label": "ULTRACOOL_DWARF",
            "confidence": None,
            "status": "GAIA_DR3_ESP_UCD",
            "evidence": [ucd],
        }
    hsd = hot_subdwarf_evidence(row)
    if hsd is not None:
        return {
            "axis": AXIS,
            "label": "HOT_SUBDWARF",
            "confidence": None,
            "status": "GAIA_CMD_HOT_SUBLUMINOUS",
            "evidence": [hsd],
        }
    star = STAR.classify(row)
    family = star.get("stellar_family")
    evidence = [
        {
            "kind": "star_branch",
            "stellar_family": family,
            "stellar_family_score": star.get("stellar_family_score"),
            "basis": star.get("basis"),
            "wd_hr_locus_signal": star.get("wd_hr_locus_signal"),
            "spectral_type": star.get("spectral_type"),
            "spectral_type_confidence": star.get("spectral_type_confidence"),
        }
    ]
    if family == "WHITE_DWARF_CANDIDATE":
        return {
            "axis": AXIS,
            "label": "WD",
            "confidence": star.get("stellar_family_score"),
            "status": "CLASSIFIED_WD",
            "evidence": evidence,
        }
    evolved = EVOLVED.classify(row)
    evidence.extend(evolved.get("evidence", []))
    if evolved.get("label") in {"RGB", "AGB", "RED_GIANT"}:
        return {
            "axis": AXIS,
            "label": evolved["label"],
            "confidence": evolved.get("confidence"),
            "status": evolved.get("status", "CLASSIFIED"),
            "evidence": evidence,
        }
    # A stellar-family route establishes only that the object is stellar.  It is
    # not evidence for a physical/evolutionary state, and must not become a
    # catch-all physical class.  In particular, doing so turns missing RGB/AGB
    # evidence into a confident but wrong label in independent truth tests.
    sub = _subclass()
    teff = _teff(row)
    # The SIMBAD MK luminosity class (spectroscopic) first, as in the sub-class
    # (2.23.0): a CMD "giant" with SIMBAD "K2V" was a red giant here but a dwarf
    # there.  II / Ib / Ia count as giants for this RGB-or-AGB label.
    sp = _text(row, "simbad__sp_type")
    mk = sub._parse_mk(sp) if sp and sp[0] in sub.LETTERS else (None, None)
    if mk[1]:
        lum = "III" if mk[1] in {"III", "II", "Ib", "Ia"} else mk[1]
        rule = "SIMBAD_SPTYPE"
        basis = f"SIMBAD MK type {sp}"
        if teff is None and mk[0] is not None and mk[0] == mk[0] and mk[0] >= 48:
            teff = GIANT_TEFF_MAX - 1  # G8 or later: cool
    else:
        lum, rule, basis = sub.star_luminosity_class(row, sub._num)
    if lum == "III" and teff is not None and teff < GIANT_TEFF_MAX:
        evidence.append({"kind": "luminosity_class", "class": lum, "rule": rule, "basis": basis, "teff": teff})
        return {
            "axis": AXIS,
            "label": "RED_GIANT",
            "confidence": None,
            "status": f"RED_GIANT_{rule}",
            "evidence": evidence,
        }
    if family == "STAR_LIKE":
        return {
            "axis": AXIS,
            "label": "UNKNOWN",
            "confidence": None,
            "status": "STAR_LIKE_NO_VALIDATED_PHYSICAL_STATE",
            "evidence": evidence,
        }
    return {
        "axis": AXIS,
        "label": "UNKNOWN",
        "confidence": None,
        "status": "INSUFFICIENT_PHYSICAL_EVIDENCE",
        "evidence": evidence,
    }
