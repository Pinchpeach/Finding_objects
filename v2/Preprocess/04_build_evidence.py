#!/usr/bin/env python3
"""Stage 4: rule-table-driven feature -> evidence conversion.

classification_rules.csv is the source of truth. A rule is evaluated only when
its required feature columns are present and usable. Missing values are neutral.
"""

from __future__ import annotations
import argparse, importlib, importlib.util, json, math, sys
from pathlib import Path
import pandas as pd


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _import_local(name):
    """Import a sibling Preprocess module by name (shared module cache)."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    return importlib.import_module(name)


_V2 = Path(__file__).resolve().parents[1]
TABLE_IO = _load("v2_table_io", _V2 / "Preprocess" / "table_io.py")
OTYPES = _load("v2_simbad_otypes_s4", _V2 / "Classifier" / "simbad_otypes.py")
# SIMBAD-TYPE-001 through the otype hierarchy (2.22.0; the old exact-code map
# missed every child type, e.g. BLL, Sy1, cC*, Mi*, and listed "Star", which
# is not a code).  Most specific first: QSO (incl. blazars) before AGN before
# galaxy; anything under "*" is a star.  Candidate codes ("?") give nothing.
SIMBAD_COARSE = {"QSO": "QSO", "AGN": "EXTRAGALACTIC", "G": "GALAXY", "*": "STAR"}

PRIMARY = ("STAR", "GALAXY", "QSO")
# Unresolved morphology cannot separate stars from quasars (both are point
# sources); it is emitted as POINT_SOURCE and fused onto STAR and QSO alike.
DSC_MAP = {
    "QSO": "classprob_dsc_combmod_quasar",
    "GALAXY": "classprob_dsc_combmod_galaxy",
    "STAR": "classprob_dsc_combmod_star",
    "WD": "classprob_dsc_combmod_whitedwarf",
    "BINARY": "classprob_dsc_combmod_binarystar",
}


def num(row, name):
    try:
        v = float(row.get(name))
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


R90_MIN_SNR2 = 5.0
# AST-EXT-001 is the Gaia-CRF3 consistency cut |(plx+0.017)/sigma| < 5
# (Klioner+2022 Eq. 2), which Klioner et al. apply only to filter catalogued
# QSO candidates.  As positive EXTRAGALACTIC evidence it is informative only
# when sigma_plx is small: with sigma = 1 mas any star beyond ~0.2 kpc passes.
# Emitted for sigma_plx <= 0.3 mas (G <~ 19.5 in DR3; Lindegren+2021 A2)
# (2.16.0; DESI benchmark 89.29 -> 89.50 %, SDSS unchanged).
AST_EXT_MAX_PLX_ERR = 0.3


def _r90_sky(ra, dec):
    """Assef+2018 R90 footprint: |b| > 10 deg and > 30 deg from the Galactic
    Centre.  Unknown position -> allowed (the colour cut still applies)."""
    if ra is None or dec is None:
        return True
    r, d = math.radians(ra), math.radians(dec)
    # ICRS -> Galactic unit vector (rotation matrix, ESA 1997 Hipparcos vol. 1)
    x, y, z = math.cos(d) * math.cos(r), math.cos(d) * math.sin(r), math.sin(d)
    gx = -0.0548755604 * x - 0.8734370902 * y - 0.4838350155 * z
    gy = +0.4941094279 * x - 0.4448296300 * y + 0.7469822445 * z
    gz = -0.8676661490 * x - 0.1980763734 * y + 0.4559837762 * z
    b = math.degrees(math.asin(max(-1.0, min(1.0, gz))))
    return abs(b) > 10.0 and math.degrees(math.acos(max(-1.0, min(1.0, gx)))) > 30.0


class CatalogFields:
    """Read survey-native fields from the catalog a rule is about.

    Stage 2 stores every raw field as ``<catalog_prefix>__<field>``.  When the
    input carries that namespace for the rule's catalog, only the namespaced
    value is used, so a same-named field from another survey (e.g. DESI Legacy
    ``type`` vs SDSS PhotoObj ``type``) can never stand in for it.  Inputs
    without the namespace (legacy wide tables) fall back to bare names.
    """

    def __init__(self, row, prefix, namespaced):
        self.row = row
        self.prefix = prefix if prefix in namespaced else None

    def get(self, name, default=None):
        key = f"{self.prefix}__{name}" if self.prefix else name
        return self.row.get(key, default)


# Survey-native fields read by evaluate() (bare or ``<catalog>__`` namespaced).
# Rows are materialized with only these plus derived/confidence columns, so a
# rule reading a new raw field must list it here.
RAW_FIELDS = {
    "parallax",
    "parallax_error",
    "pmra",
    "pmra_error",
    "pmdec",
    "pmdec_error",
    "pmra_pmdec_corr",
    "pmRApmDEcor",
    "class",
    "zwarning",
    # DESI DR1 Redrock / LAMOST DR5 spectral class (SPC-DESI-*, SPC-LAMOST-*)
    "OType",
    "ZWARN",
    "delChi2",
    "Prog",
    "Class",
    "snrg",
    "snri",
    "iMeanPSFMag",
    "rMeanPSFMag",
    "zMeanPSFMag",
    "W1mag",
    "W2mag",
    "snr1",
    "snr2",
    "type",
    "clean",
    "Type",
    "otype",
    "best_class_name",
    "best_class_score",
    *DSC_MAP.values(),
    "flux_r",
    "flux_ivar_r",
    "flux_z",
    "flux_ivar_z",
    "catalog_object_id",
    "RAJ2000",
    "DEJ2000",
    "phot_bp_rp_excess_factor",
    "bp_rp",
    "phot_g_mean_mag",
    # radio flux densities (RADIO-001; same columns as units.py)
    "Fint",
    "S1.4",
    "Stotal",
    "SpeakTot",
    "Total_flux",
    "Ftot",
    # Pan-STARRS1 multi-epoch statistics (PS1-VAR-001)
    *(f"{b}MeanPSFMag{k}" for b in "gri" for k in ("Std", "Npt", "Err")),
    "iMeanPSFMag",
    "iMeanKronMag",
    # X-ray fluxes (XRAY-001)
    "Fluxb",
    "Flux8",
    "MLFlux1",
    "EXTLike",  # eRASS1 extent likelihood (2.32.0: extended = cluster gas, not a point counterpart)
    # ZTF light-curve statistics (ZTF-VAR-001; Get_data/ztf_lightcurve.py)
    *(f"ztf_{b}_{k}" for b in ("g", "r") for k in ("n", "mag", "rms", "chi2r", "exvar", "sf_a", "sf_gamma")),
}
DERIVED_PREFIXES = ("association_confidence__", "catalog_confidence_", "ps1_", "ls_", "catalogs")


def _rule_columns(columns):
    return [c for c in columns if c.startswith(DERIVED_PREFIXES) or c.split("__", 1)[-1] in RAW_FIELDS]


# Riello et al. (2021, A&A 649, A3) corrected BP/RP flux excess C* (Eq. 6,
# Table 2) and its 1-sigma scatter for isolated point sources (Eq. 18); same
# formulae as Classifier/branches/star.py.  |C*| > 5 sigma means the BP/RP
# flux comes from more than one point source: an extended source (galaxy
# nucleus, HII region) or a blend, whose Gaia astrometry is not that of a
# single star (2.22.0).  The 5-sigma cut itself is applied by Stage 5 and
# host grouping (CSTAR_MAX_SIGMA there).


def cstar_sigma(src):
    c, x, g = num(src, "phot_bp_rp_excess_factor"), num(src, "bp_rp"), num(src, "phot_g_mean_mag")
    if None in (c, x, g):
        return None
    if x < 0.5:
        f = 1.154360 + 0.033772 * x + 0.032277 * x * x
    elif x < 4.0:
        f = 1.162004 + 0.011464 * x + 0.049255 * x * x - 0.005879 * x**3
    else:
        f = 1.057572 + 0.140537 * x
    return abs(c - f) / (0.0059898 + 8.817481e-12 * g**7.618399)


def _tag_cstar(out, rid, src):
    """Record C* significance on the astrometric evidence just emitted; Stage
    5 and host grouping do not let it override the in-galaxy status or the
    fusion when the source is extended."""
    if out and out[-1].get("rule_id") == rid:
        cs = cstar_sigma(src)
        if cs is not None:
            out[-1]["cstar_sigma"] = round(cs, 2)


def emit(out, rule, cls, score, value=None, note="", reliability=1.0, association_reliability=1.0):
    raw = float(max(0, min(1, score)))
    # Catalog-quality and association reliabilities are independent factors;
    # each is applied exactly once.
    rel = float(max(0, min(1, reliability))) if reliability is not None else 0.0
    arel = float(max(0, min(1, association_reliability))) if association_reliability is not None else 0.0
    effective = raw * rel * arel
    if effective <= 0:
        return
    out.append(
        {
            "class": cls,
            "rule_id": rule["rule_id"],
            "score": effective,
            "raw_score": raw,
            "reliability": rel,
            "association_reliability": arel,
            "kind": rule["likelihood_method"],
            "origin": rule["threshold_origin"],
            "feature_group": rule["feature_group"],
            "value": value,
            "note": note,
        }
    )


# Gaia DR3 DSC-Combmod class prior (Delchambre et al. 2023, Table 2), coarse
# classes: STAR family = star + binary + white dwarf.
DSC_PRIOR = {"STAR": 0.988728 + 0.009887 + 0.000198, "GALAXY": 0.000198, "QSO": 0.000989}
DSC_FLOOR = 1e-6

# Per-rule catalogue-quality column and association namespace (module
# constants since 2.19.0; they were rebuilt for every row x rule).
RELMAP = {
    "AST-EXT-001": "catalog_confidence_gaia_astrometry",
    "AST-EXT-002": "catalog_confidence_gaia_astrometry",
    "AST-GAL-001": "catalog_confidence_gaia_astrometry",
    "AST-GAL-002": "catalog_confidence_gaia_astrometry",
    "SPC-SDSS-001": "catalog_confidence_sdss_spectroscopy",
    "SPC-SDSS-002": "catalog_confidence_sdss_spectroscopy",
    "SPC-SDSS-003": "catalog_confidence_sdss_spectroscopy",
    **{f"SPC-DESI-00{i}": "catalog_confidence_desi_spectroscopy" for i in (1, 2, 3)},
    **{f"SPC-LAMOST-00{i}": "catalog_confidence_lamost_spectroscopy" for i in (1, 2, 3)},
    "DSC-001": "catalog_confidence_gaia_dsc",
    "PS1-MORPH-001": "catalog_confidence_ps1_morphology",
    "PS1-MORPH-002": "catalog_confidence_ps1_morphology",
    "WISE-AGN-001": "catalog_confidence_allwise",
    "SDSS-PHOTO-001": "catalog_confidence_sdss_photometry",
    "SDSS-PHOTO-002": "catalog_confidence_sdss_photometry",
    "NED-TYPE-001": "catalog_confidence_ned_type",
    "SIMBAD-TYPE-001": "catalog_confidence_simbad_type",
    "WISE-AGN-R90-001": "catalog_confidence_allwise",
}
ASSOC_PREFIX = {
    "AST-EXT-001": "gaia_dr3",
    "AST-EXT-002": "gaia_dr3",
    "AST-GAL-001": "gaia_dr3",
    "AST-GAL-002": "gaia_dr3",
    "DSC-001": "gaia_dr3",
    "VAR-001": "gaia_dr3",
    "SPC-SDSS-001": "sdss_dr18_spectroscopy",
    "SPC-SDSS-002": "sdss_dr18_spectroscopy",
    "SPC-SDSS-003": "sdss_dr18_spectroscopy",
    **{f"SPC-DESI-00{i}": "desi_dr1_spectroscopy" for i in (1, 2, 3)},
    **{f"SPC-LAMOST-00{i}": "lamost_dr_catalog" for i in (1, 2, 3)},
    "PS1-MORPH-001": "pan_starrs1_dr2_meanobject",
    "PS1-MORPH-002": "pan_starrs1_dr2_meanobject",
    "PS1-QSO-Z6-001": "pan_starrs1_dr2_meanobject",
    "PS1-QSO-HIZ-001": "pan_starrs1_dr2_meanobject",
    "WISE-AGN-001": "allwise",
    "WISE-AGN-R90-001": "allwise",
    "PS1-VAR-001": "pan_starrs1_dr2_meanobject",
    "SDSS-PHOTO-001": "sdss_dr18_photoobj",
    "SDSS-PHOTO-002": "sdss_dr18_photoobj",
    "NED-TYPE-001": "ned",
    "SIMBAD-TYPE-001": "simbad",
    "LS-MORPH-001": "desi_legacy_surveys_dr10",
    "LS-MORPH-002": "desi_legacy_surveys_dr10",
    "SGA-001": "sga_2020",
}


# 1.4 GHz flux density (mJy) from the radio surveys, in units.py's order and
# spectral index (S ~ nu^-0.7): FIRST, NVSS, LoTSS 144 MHz, VLASS 3 GHz.
RADIO_14GHZ = (
    (("first__Fint",), 1.0),
    (("nvss__S1.4",), 1.0),
    (("lotss_dr2__Stotal", "lotss_dr2__SpeakTot", "lotss_dr2__Total_flux"), (1400 / 144) ** -0.7),
    (("vlass__Ftot", "vlass__Total_flux"), (1400 / 3000) ** -0.7),
)


def radio_14ghz_mjy(row):
    for names, scale in RADIO_14GHZ:
        for n in names:
            v = num(row, n)
            if v is not None and v > 0:
                return v * scale
    return None


# X-ray flux (erg/s/cm^2) in the 0.3-3.5 keV band of the X-ray-to-optical
# flux ratio (Maccacaro et al. 1988, ApJ 326, 680), converted from each
# survey band with a photon index Gamma = 1.8 (F ~ E2^0.2 - E1^0.2), the mean
# AGN slope.  Order: Chandra CSC 2.0 broad (0.5-7 keV), 4XMM-DR13 band 8
# (0.2-12 keV), eRASS1 band 1 (0.2-2.3 keV); the first positive flux is used.
def _band(e1, e2):
    return (3.5**0.2 - 0.3**0.2) / (e2**0.2 - e1**0.2)


XRAY_FLUX = (
    ("chandra_csc_2_0__Fluxb", _band(0.5, 7.0)),
    ("xmm_4xmm_dr13__Flux8", _band(0.2, 12.0)),
    ("erosita_erass1__MLFlux1", _band(0.2, 2.3)),
)


def xray_flux(row):
    # An extended eRASS1 source (EXT_LIKE > 0; point sources have EXT_LIKE = 0,
    # Merloni et al. 2024, Table 4) is hot gas of a galaxy cluster or group
    # (Bulbul et al. 2024), not X-ray emission of the matched object (2.32.0).
    extended = (num(row, "erosita_erass1__EXTLike") or 0.0) > 0
    for name, scale in XRAY_FLUX:
        if extended and name.startswith("erosita_"):
            continue
        v = num(row, name)
        if v is not None and v > 0:
            return v * scale
    return None


def optical_r_mag(row):
    """Dereddened Legacy Surveys r, else Pan-STARRS1 r (PSF, AB)."""
    r = num(row, "ls_r_mag")
    if r is None:
        r = num(row, "pan_starrs1_dr2_meanobject__rMeanPSFMag")
    return r if r is not None and 5 < r < 30 else None


# Option c2 of the 2.38.0 QSO comparison (qso_options.py): Mahalanobis
# distance of the proper motion from zero with the pmra-pmdec correlation,
# scaled by s = 1.1485 fitted to Gaia-CRF3 quasars (Li & Fynbo 2026).
PM_MAHALANOBIS = False
PM_MAHALANOBIS_SCALE = 1.1485


def _pm_sigma(src):
    """Total proper-motion significance (diagonal errors), or None."""
    a, ae, d, de = (num(src, x) for x in ("pmra", "pmra_error", "pmdec", "pmdec_error"))
    if None not in (a, ae, d, de) and ae > 0 and de > 0:
        if PM_MAHALANOBIS:
            rho = num(src, "pmra_pmdec_corr")
            rho = num(src, "pmRApmDEcor") if rho is None else rho
            rho = 0.0 if rho is None or not -0.999 < rho < 0.999 else rho
            x, y = a / ae, d / de
            return math.sqrt((x * x - 2 * rho * x * y + y * y) / (1 - rho * rho) / PM_MAHALANOBIS_SCALE)
        return math.sqrt((a / ae) ** 2 + (d / de) ** 2)
    return None


def evaluate(rule, row, namespaced=frozenset()):
    rid = rule["rule_id"]
    out = []
    rcol = RELMAP.get(rid)
    reliability = num(row, rcol) if rcol else 1.0
    # Gate only by the association confidence of the catalog that produced
    # this evidence. A weak PS1/NED counterpart must not downweight Gaia/SDSS.
    ap = ASSOC_PREFIX.get(rid)
    association_reliability = num(row, f"association_confidence__{ap}") if ap else 1.0
    if association_reliability is None:
        association_reliability = 1.0
    src = CatalogFields(row, ap, namespaced)
    if rcol and reliability is None:
        reliability = 0.0

    def hit(cls, score, value=None, note=""):
        emit(out, rule, cls, score, value, note, reliability, association_reliability)

    def feature(name, value, note):
        # Continuous feature for the fitted linear fusion (weights only from Stage 5).
        out.append(
            {
                "class": f"FEATURE:{name}",
                "rule_id": rid,
                "value": value,
                "kind": "linear_feature",
                "origin": rule["threshold_origin"],
                "feature_group": rule["feature_group"],
                "note": note,
            }
        )

    if rid == "AST-EXT-001":
        p, e = num(src, "parallax"), num(src, "parallax_error")
        if p is not None and e and 0 < e <= AST_EXT_MAX_PLX_ERR:
            x = abs((p + 0.017) / e)
            if x < float(rule["threshold"]):
                hit("EXTRAGALACTIC", 1 - x / float(rule["threshold"]), x)
    elif rid == "AST-EXT-002":
        x = _pm_sigma(src)
        if x is not None and x < float(rule["threshold"]):
            hit(
                "EXTRAGALACTIC",
                1 - x / float(rule["threshold"]),
                x,
                "diagonal-error approximation; covariance unavailable",
            )
    elif rid == "AST-GAL-001":
        p, e = num(src, "parallax"), num(src, "parallax_error")
        if p is not None and e and e > 0:
            # Only a positive parallax is evidence of distance: a significantly
            # negative one is noise or a spurious solution (e.g. a close
            # companion; El-Badry et al. 2021), and |plx|/sigma >= 10 used to
            # trigger the decisive-motion STAR rule (2.19.0).
            x = max(p, 0.0) / e
            hit("STAR", x / (x + 5), x, "uncalibrated physical support")
            _tag_cstar(out, rid, src)
    elif rid == "AST-GAL-002":
        x = _pm_sigma(src)
        if x is not None:
            hit("STAR", x / (x + 5), x, "uncalibrated physical support")
            _tag_cstar(out, rid, src)
    elif rid.startswith("SPC-SDSS-"):
        c = str(src.get("class", "")).strip().upper()
        target = rule["target_class"]
        if (target == "QSO" and c in {"QSO", "QUASAR"}) or c == target:
            zw = num(src, "zwarning")
            score = 1.0 if zw in (None, 0) else 0.75
            hit(target, score, c, "nonzero zwarning downweights spectral label" if zw not in (None, 0) else "")
    elif rid.startswith(("SPC-DESI-", "SPC-LAMOST-")):
        # Pipeline spectral class (DESI Redrock SPECTYPE, LAMOST 1D class);
        # spectrum quality is the catalogue reliability (Stage 3).
        c = str(src.get("OType" if rid.startswith("SPC-DESI-") else "Class", "")).strip().upper()
        if c == rule["target_class"]:
            hit(c, 1.0, c)
    elif rid.startswith("PS1-MORPH-"):
        delta = num(row, "ps1_i_psf_minus_kron")
        imag = num(src, "iMeanPSFMag")
        valid = num(row, "ps1_i_photometry_valid")
        if None not in (delta, imag, valid) and valid == 1 and 14 <= imag <= 21:
            if rid == "PS1-MORPH-001" and delta > 0.05:
                # Extended morphology is direct GALAXY support within the documented regime.
                score = min(0.9, 0.55 + min(delta - 0.05, 0.35))
                hit("GALAXY", score, delta, "PS1 i-band PSF-Kron extended-source evidence")
            elif rid == "PS1-MORPH-002" and delta <= 0.05:
                # Point-like morphology is deliberately weak STAR evidence: QSOs are unresolved too.
                score = min(0.65, 0.50 + min(max(0, 0.05 - delta), 0.15))
                hit(
                    "POINT_SOURCE",
                    score,
                    delta,
                    "weak point-source evidence; unresolved morphology is not STAR-specific",
                )
    elif rid == "WISE-AGN-R90-001":
        # Assef+2018 (ApJS 234, 23) sec. 3 build R90 only where it is
        # calibrated: W2 S/N > 5, W1 > 8 and W2 > 7 mag (saturation), and
        # outside |b| <= 10 deg and 30 deg of the Galactic Centre (YSOs, AGB
        # stars, PNe mimic AGN colours there).  cc_flags = 0 is already
        # enforced by catalog_confidence_allwise.  (2.16.0; was S/N >= 3 only.)
        w1, w2, s1, s2 = (num(src, x) for x in ("W1mag", "W2mag", "snr1", "snr2"))
        ra, dec = num(src, "RAJ2000"), num(src, "DEJ2000")
        if None not in (w1, w2, s1, s2) and s1 >= 3 and s2 > R90_MIN_SNR2 and w1 > 8 and w2 > 7 and _r90_sky(ra, dec):
            cut = 0.650 if w2 <= 13.86 else 0.650 * math.exp(0.153 * (w2 - 13.86) ** 2)
            color = w1 - w2
            if color > cut:
                hit("EXTRAGALACTIC", 0.90, color, f"Assef+2018 AllWISE R90 AGN color selection; boundary={cut:.3f}")
    elif rid == "PS1-QSO-Z6-001":
        iz = num(row, "ps1_i_z_color")
        zy = num(row, "ps1_z_y_color")
        eg = num(row, "ps1_g_psf_mag_err")
        er = num(row, "ps1_r_psf_mag_err")
        ez = num(row, "ps1_z_psf_mag_err")
        ey = num(row, "ps1_y_psf_mag_err")
        vz = num(row, "ps1_z_photometry_valid")
        vy = num(row, "ps1_y_photometry_valid")
        # S/N from magnitude uncertainty: sigma_mag ~= 1.0857/SNR.
        sn = lambda e: (1.0857 / e if e is not None and e > 0 else None)
        sg, sr, sz, sy = sn(eg), sn(er), sn(ez), sn(ey)
        rz = None
        r = num(src, "rMeanPSFMag")
        z = num(src, "zMeanPSFMag")
        if r is not None and z is not None and 0 < r < 40 and 0 < z < 40:
            rz = r - z
        if None not in (iz, zy, sz, sy, vz, vy) and vz == 1 and vy == 1 and iz > 2.0:
            gdrop = sg is None or sg < 3
            if zy < 0.5:
                rcond = sr is None or sr < 3 or (rz is not None and rz > 2.2)
                selected = gdrop and sz > 10 and sy > 5 and rcond
            else:
                selected = gdrop and sz > 7 and sy > 7 and (sr is None or sr < 3)
            if selected:
                # Candidate-selection evidence only. Keep moderate because the
                # paper explicitly requires follow-up to reject cool dwarfs/artifacts.
                hit(
                    "QSO",
                    0.70,
                    {"i-z": iz, "z-y": zy},
                    "Bañados+2016 PS1 z~6 quasar color-selection candidate; follow-up required",
                )
    elif rid == "PS1-QSO-HIZ-001":
        # z ~ 3.5-4.5 quasars: the Lyman-alpha forest leaves g faint (red
        # g-r) while r-i and i-z stay blue, off the stellar locus that the
        # z ~ 2.7 quasars cross.  Richards et al. 2002 (AJ 123, 2945) "gri"
        # branch, with SDSS ~ PS1 gri (Tonry et al. 2012 offsets < 0.1 mag),
        # point sources only.  Benchmark: 7 of 8 point sources passing are
        # quasars (SDSS + DESI), but only ~11 % of z > 3 quasars pass.
        gr, ri, iz = (num(row, f"ps1_{c}_color") for c in ("g_r", "r_i", "i_z"))
        er, ei = num(row, "ps1_r_psf_mag_err"), num(row, "ps1_i_psf_mag_err")
        pk = num(row, "ps1_i_psf_minus_kron")
        if None not in (gr, ri, iz, er, ei, pk) and er < 0.2 and ei < 0.2 and pk < 0.05:
            if gr > 1.0 and (ri < 0.08 + 0.42 * (gr - 0.96) or gr > 2.26) and iz < 0.25:
                hit(
                    "QSO",
                    0.80,
                    {"g-r": gr, "r-i": ri, "i-z": iz},
                    "Richards+2002 high-z (gri) quasar colours, point source",
                )
    elif rid == "WISE-AGN-001":
        w1, w2, s1, s2 = (num(src, x) for x in ("W1mag", "W2mag", "snr1", "snr2"))
        if None not in (w1, w2, s1, s2) and w1 - w2 >= 0.8 and w2 <= 15.05 and s1 >= 10 and s2 >= 10:
            hit(
                "EXTRAGALACTIC",
                0.95,
                w1 - w2,
                "Stern+2012 AGN selection; 0.95 is reported sample reliability, not per-source posterior",
            )
    elif rid.startswith("SDSS-PHOTO-"):
        typ = num(src, "type")
        clean = num(src, "clean")
        if clean == 1 and typ is not None:
            if rid == "SDSS-PHOTO-001" and int(typ) == 3:
                hit("GALAXY", 0.8, typ, "SDSS extended morphology")
            elif rid == "SDSS-PHOTO-002" and int(typ) == 6:
                hit("POINT_SOURCE", 0.55, typ, "weak point-source morphology; stars and quasars both unresolved")
    elif rid.startswith("LS-MORPH-"):
        # Legacy Surveys Tractor model choice (Dey+2019). Below S/N~10 a PSF
        # fit is preferred by default, so morphology is used only above it.
        typ = str(src.get("type", "")).strip().upper()
        snr = [
            f * math.sqrt(iv)
            for f, iv in ((num(src, "flux_r"), num(src, "flux_ivar_r")), (num(src, "flux_z"), num(src, "flux_ivar_z")))
            if f is not None and iv is not None and iv > 0
        ]
        if snr and max(snr) >= float(rule["threshold"]):
            if rid == "LS-MORPH-001" and typ in {"REX", "EXP", "DEV", "SER"}:
                hit("GALAXY", 0.75, typ, "Legacy Surveys resolved Tractor model")
            elif rid == "LS-MORPH-002" and typ == "PSF":
                hit("POINT_SOURCE", 0.60, typ, "Legacy Surveys PSF model; stars and quasars both unresolved")
    elif rid == "LS-COLOR-001":
        # Continuous colour features for the fitted linear fusion; each colour
        # comes with a presence indicator so a missing colour is not read as 0.
        for name in ("g_r", "r_z", "z_w1", "w1_w2"):
            v = num(row, f"ls_{name}_color")
            if v is not None:
                feature(name, max(-3.0, min(6.0, v)), "dereddened AB colour")
                feature(f"{name}_present", 1.0, "colour available")
    elif rid == "PS1-VAR-001":
        # Multi-epoch variability of point sources (2.36.0).  Quasars vary
        # stochastically by ~0.1-0.3 mag over years (MacLeod et al. 2010,
        # ApJ 721, 1014); PS1 3pi has ~12 epochs per band over ~4 yr and
        # separates quasars by variability (Hernitschek et al. 2016, ApJ 817,
        # 73).  Index per band: R = Std / (MeanErr * sqrt(Npt)), the epoch
        # scatter over the scatter the photometric errors predict (MeanErr is
        # the error of the mean, so R ~ 1 without variability; median 1.08-1.14
        # measured on 373 benchmark objects).  Median of g, r, i over bands
        # with >= 5 epochs.  Point sources only: resolved galaxies scatter in
        # PSF magnitude with the seeing (benchmark galaxies reached R ~ 2-6).
        typ = str(row.get("desi_legacy_surveys_dr10__type", "")).strip().upper()
        psf_kron = None
        if num(src, "iMeanPSFMag") is not None and num(src, "iMeanKronMag") is not None:
            psf_kron = num(src, "iMeanPSFMag") - num(src, "iMeanKronMag")
        point = typ == "PSF" if typ in {"PSF", "REX", "EXP", "DEV", "SER", "COMP"} else (psf_kron is not None and psf_kron <= 0.05)
        if point:
            ratios = []
            for b in "gri":
                sd, n, e = num(src, f"{b}MeanPSFMagStd"), num(src, f"{b}MeanPSFMagNpt"), num(src, f"{b}MeanPSFMagErr")
                if sd is not None and n is not None and e is not None and n >= 5 and e > 0 and sd >= 0:
                    ratios.append(sd / (e * math.sqrt(n)))
            if ratios:
                ratios.sort()
                rmed = ratios[len(ratios) // 2] if len(ratios) % 2 else 0.5 * (ratios[len(ratios) // 2 - 1] + ratios[len(ratios) // 2])
                feature("ps1_var_log_r", max(-2.0, min(3.0, math.log(max(rmed, 1e-3)))), "log epoch scatter / predicted")
                feature("ps1_var_present", 1.0, "PS1 multi-epoch statistics (point source)")
    elif rid == "RADIO-001":
        # Radio loudness R = 0.4 (r - t), t = -2.5 log10(S_1.4GHz / 3631 Jy)
        # (Ivezic et al. 2002, AJ 124, 2364; radio-loud R > 1).  Radio-loud
        # quasars and AGN in galaxies are detected at the survey limits
        # (FIRST ~1 mJy) while stars almost never are; star-forming galaxies
        # are radio-detected at low R.  Continuous features; weights come
        # only from the fitted Stage-5 model.
        s = radio_14ghz_mjy(row)
        r = optical_r_mag(row)
        if s is not None:
            feats = {"radio_detected": 1.0}
            if r is not None:
                t = -2.5 * math.log10(s * 1e-3 / 3631.0)
                feats["radio_log_r"] = max(-2.0, min(6.0, 0.4 * (r - t)))
            for name, v in feats.items():
                feature(name, v, "radio counterpart")
    elif rid == "XRAY-001":
        # X-ray-to-optical flux ratio log(fX/fopt) = log fX + r/2.5 + 5.37
        # (Maccacaro et al. 1988, Eq. 1; r used for V): AGN and quasars lie
        # at -1 to +1.2, coronal stars below -1 and normal galaxies below
        # ~ -2 (Stocke et al. 1991, ApJS 76, 813).  Continuous features;
        # weights come only from the fitted Stage-5 model.
        fx = xray_flux(row)
        r = optical_r_mag(row)
        if fx is not None:
            feats = {"xray_detected": 1.0}
            if r is not None:
                feats["xray_log_fx_fo"] = max(-4.0, min(3.0, math.log10(fx) + r / 2.5 + 5.37))
            for name, v in feats.items():
                feature(name, v, "X-ray counterpart")
    elif rid == "ZTF-VAR-001":
        # Aperiodic optical variability from ZTF light curves: quasars vary
        # stochastically with a rising structure function (A ~ 0.1 mag at 1 yr,
        # gamma ~ 0.3-0.5; Schmidt et al. 2010), most stars are constant at ZTF
        # precision.  As in Palanque-Delabrouille et al. (2011) only point
        # sources are used: PSF photometry of a resolved galaxy changes with
        # seeing, which reads as variability (benchmark galaxies: median
        # chi2_red 10.6).  Point-like = Legacy Surveys PSF model or PS1
        # i(PSF) - i(Kron) < 0.05.  The r band is used, else g; survey-
        # dependent quantities (epoch count, magnitude) are not features.
        # Continuous features; weights come only from the fitted Stage-5 model.
        z = "ztf_light_curves__"
        ls_type = str(row.get("desi_legacy_surveys_dr10__type", "")).strip().upper()
        pk = num(row, "ps1_i_psf_minus_kron")
        point = ls_type == "PSF" if ls_type not in {"", "NAN", "NONE"} else (pk is not None and pk < 0.05)
        band = next((b for b in ("r", "g") if (num(row, f"{z}ztf_{b}_n") or 0) >= 10), None)
        if point and band is not None:
            p = f"{z}ztf_{band}_"
            chi2r = num(row, p + "chi2r")
            if chi2r is not None and chi2r > 0:
                feature("ztf_chi2r_log", max(-1.0, min(3.0, math.log10(chi2r))), "ZTF light-curve variability")
            sf_a = num(row, p + "sf_a")
            if sf_a is not None:
                feature("ztf_sf_a_log", max(-3.0, min(0.5, math.log10(max(sf_a, 1e-3)))), "ZTF light-curve variability")
            gamma = num(row, p + "sf_gamma")
            if gamma is not None:
                feature("ztf_sf_gamma", max(-1.0, min(1.5, gamma)), "ZTF light-curve variability")
    elif rid == "SGA-001":
        if "SGA-2020" in str(row.get("catalogs", "")).split("|"):
            hit("GALAXY", 0.95, src.get("catalog_object_id"), "Siena Galaxy Atlas 2020 large galaxy")
    elif rid == "NED-TYPE-001":
        typ = str(src.get("Type", "")).strip()
        # NED "*" for faint sources is mostly inherited from photometric
        # catalogues' unresolved morphology, which quasars and compact
        # galaxies share; it is used as point-source evidence only.
        mp = {"G": "GALAXY", "QSO": "QSO", "*": "POINT_SOURCE", "WD*": "STAR"}
        if typ in mp:
            hit(mp[typ], 0.85, typ, "curated NED preferred physical type")
    elif rid == "SIMBAD-TYPE-001":
        typ = str(src.get("otype", "")).strip()
        cls, _hit = OTYPES.resolve(typ, SIMBAD_COARSE)
        if cls:
            hit(cls, 0.85, typ, "curated SIMBAD hierarchical physical type")
    elif rid == "DSC-001":
        # Preprocess is intentionally coarse. Gaia DSC white-dwarf and
        # physical-binary posterior mass belongs to the stellar family here;
        # detailed stellar subclassification is deferred to v2/Classifier.
        # DSC-Combmod posteriors carry a fixed class prior (Delchambre et al.
        # 2023, A&A 674, A31, Table 2: star 0.9887, binary 0.0099, WD 0.0002,
        # QSO 0.00099, galaxy 0.0002).  The fusion is fitted on class-balanced
        # benchmarks, so that prior would be counted twice (it is what made the
        # unconstrained fit give DSC "STAR" a negative weight).  The prior is
        # divided out (their App. C) and the evidence is the prior-free
        # probability over STAR family / GALAXY / QSO (2.16.0).
        pv = {cls: num(src, col) for cls, col in DSC_MAP.items()}
        # An all-zero stellar family is a valid (confidently extragalactic)
        # posterior, not a missing one; DSC_FLOOR handles the zero.  Before
        # 2.27.0 it suppressed the rule for 41 % of benchmark DSC rows.
        stellar = [v for cls, v in pv.items() if cls in {"STAR", "WD", "BINARY"} and v is not None]
        coarse = {"STAR": sum(stellar) if stellar else None, "GALAXY": pv.get("GALAXY"), "QSO": pv.get("QSO")}
        if all(v is not None for v in coarse.values()):
            lr = {c: max(v, DSC_FLOOR) / DSC_PRIOR[c] for c, v in coarse.items()}
            z = sum(lr.values())
            for cls in PRIMARY:
                hit(
                    cls,
                    lr[cls] / z,
                    coarse[cls],
                    "Gaia DSC posterior with its class prior divided out (Delchambre+2023 App. C)",
                )
    elif rid == "VAR-001":
        cls = str(src.get("best_class_name", "")).strip()
        score = num(src, "best_class_score")
        if cls and score is not None:
            hit(f"VAR:{cls}", score, score)
    return out


def _color_knn_evidence(df, rule_list):
    """LS-CKNN-001 / PS1-CKNN-001: colour-space kNN class fractions, computed for all rows at once."""
    empty = [[] for _ in range(len(df))]
    color_knn = _import_local("color_knn")

    rules = {r["rule_id"]: r for r in rule_list if r["rule_id"] in color_knn.COLOR_SETS}
    ref = color_knn.load_reference() if rules else None
    if ref is None:
        return empty
    ids = df["benchmark_id"].astype(str).to_numpy() if "benchmark_id" in df else None
    for rid, rule in rules.items():
        colors = color_knn.COLOR_SETS[rid]
        if not any(c in df for c in colors):
            continue
        frac = color_knn.class_fractions(df, ref, ids=ids, colors=colors)
        for i, f in enumerate(frac):
            if f[0] == f[0]:
                for cls, v in zip(color_knn.CLASSES, f):
                    emit(empty[i], rule, cls, float(v), round(float(v), 4), "colour-space kNN class fraction")
    return empty


def _ls_gbm_evidence(df, rule_list):
    """LS-GBM-001: gradient-boosting STAR/GALAXY/QSO probabilities from the Legacy Surveys Tractor columns (2.11.0)."""
    empty = [[] for _ in range(len(df))]
    rule = next((r for r in rule_list if r["rule_id"] == "LS-GBM-001"), None)
    if rule is None:
        return empty
    ls_gbm = _import_local("ls_gbm")

    prob = ls_gbm.predict_proba(df)
    for i, f in enumerate(prob):
        if f[0] == f[0]:
            for cls, v in zip(ls_gbm.CLASSES, f):
                emit(empty[i], rule, cls, float(v), round(float(v), 4), "gradient-boosting class probability")
    return empty


# Soft statistical evidence (class fractions / probabilities over all three
# classes), weighed by the fitted fusion; never counted as a hard conflict.
SOFT_SUFFIXES = ("-CKNN-001", "-GBM-001")


def run(features: Path, rules_path: Path, out: Path) -> Path:
    global PM_MAHALANOBIS
    PM_MAHALANOBIS = "c2" in _import_local("qso_options").parse()
    df = TABLE_IO.read_table(features)
    rules = pd.read_csv(rules_path, keep_default_na=False)
    result = df.copy()
    payload = []
    counts = []
    conflicts = []
    namespaced = frozenset(c.split("__", 1)[0] for c in df.columns if "__" in c)
    # Plain dicts: building a pandas Series per row/rule dominated runtime.
    rule_list = rules.to_dict("records")
    knn = _color_knn_evidence(df, rule_list)
    gbm = _ls_gbm_evidence(df, rule_list)
    for i, row in enumerate(df[_rule_columns(df.columns)].to_dict("records")):
        ev = []
        for rule in rule_list:
            ev.extend(evaluate(rule, row, namespaced))
        ev.extend(knn[i])
        ev.extend(gbm[i])
        payload.append(json.dumps(ev, separators=(",", ":")))
        counts.append(len(ev))
        # kNN class fractions are soft statistical evidence, weighed by the
        # fitted fusion; they are not independent hard claims that can conflict.
        strong = {
            e["class"]
            for e in ev
            if e["class"] in PRIMARY and e["score"] >= 0.8 and not e["rule_id"].endswith(SOFT_SUFFIXES)
        }
        conflicts.append(int(len(strong) > 1))
    result["evidence_json"] = payload
    result["evidence_count"] = counts
    result["evidence_conflict"] = conflicts
    out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out, index=False)
    print(f"[OK] rules={len(rules)} objects={len(result)} -> {out}")
    return out


def main():
    root = Path(__file__).resolve().parent
    p = argparse.ArgumentParser()
    p.add_argument("--features", type=Path, default=root / "features.csv")
    p.add_argument("--rules", type=Path, default=root / "classification_rules.csv")
    p.add_argument("--out", type=Path, default=root / "evidence.csv")
    a = p.parse_args()
    run(a.features, a.rules, a.out)


if __name__ == "__main__":
    main()
