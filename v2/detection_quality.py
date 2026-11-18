"""Unconfirmed single-survey detections (2.30.0).

Most UNKNOWN objects in real fields are Pan-STARRS1 DR2 MeanObject rows seen
by no other survey, typically with nDetections = 2 and a mean magnitude in
one or two bands at 20.8-22 mag, the PS1 single-epoch 5 sigma limit (g 22.0,
r 21.8, i 21.5; Chambers et al. 2016, Table 11).  A pair of detections from
one night can be a GPC1 artefact (correlated read noise etc.): "such
artifacts dominate the Detection and Object tables" (Chambers et al. 2016,
Sect. 4.2.2), and Magnier et al. (2020c, Sect. 6.4) require >= 3 detections
"to reject artifacts detected in a pair of exposures from the same night".
They are not Solar System objects either (2.29.0: no PS1 SOLSYS bits, no
SkyBoT match).

Such a row is labelled UNCONFIRMED -- a likely artefact or transient, not an
astrophysical class -- when the much deeper Legacy Surveys imaging covers the
position and shows nothing there: Legacy Surveys single-frame 5 sigma PSF
depths are r = 23.5 (DECaLS) / 23.1 (BASS), g 23.7-24.0 (Dey et al. 2019,
Table 4), so a real source at <= LS_DEPTH_MARGIN_MAG brighter than r 23 would
be detected.  Coverage: at least MIN_LS_NEIGHBOURS Legacy Surveys objects
within COVERAGE_RADIUS_ARCSEC (the survey observed that patch).
"""

from __future__ import annotations
import numpy as np
import pandas as pd

PS1 = "Pan-STARRS1 DR2 MeanObject"
LS = "DESI Legacy Surveys DR10"
LITERATURE = {"SIMBAD", "NED"}
MAX_DETECTIONS = 2
MAX_BANDS = 2
MAX_PS1_MAG = 22.5  # >= 0.6 mag brighter than the shallowest LS r depth (BASS 23.1)
NO_COUNTERPART_ARCSEC = 2.0
COVERAGE_RADIUS_ARCSEC = 60.0
MIN_LS_NEIGHBOURS = 3


def _unit(ra, dec):
    ra, dec = np.radians(np.asarray(ra, float)), np.radians(np.asarray(dec, float))
    return np.column_stack([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)])


def _neighbours(src, ref, radius_arcsec):
    """(nearest separation in arcsec, count within radius) of each src row among ref."""
    if not len(src) or not len(ref):
        return np.full(len(src), np.inf), np.zeros(len(src), int)
    a, b = _unit(src.ra, src.dec), _unit(ref.ra, ref.dec)
    cos_r = np.cos(np.radians(radius_arcsec / 3600.0))
    near, count = np.empty(len(a)), np.empty(len(a), int)
    for s in range(0, len(a), 512):
        dot = np.clip(a[s : s + 512] @ b.T, -1.0, 1.0)
        near[s : s + 512] = np.degrees(np.arccos(dot.max(axis=1))) * 3600.0
        count[s : s + 512] = (dot >= cos_r).sum(axis=1)
    return near, count


def flag(out: pd.DataFrame) -> pd.Series:
    """Boolean Series: rows that are unconfirmed PS1-only detections."""
    res = pd.Series(False, index=out.index)
    if out.empty or "catalogs" not in out:
        return res
    cats = out.catalogs.astype(str).map(lambda s: frozenset(c for c in s.split("|") if c) - LITERATURE)
    unknown = out.get("primary_class", pd.Series("UNKNOWN", index=out.index)).astype(str).str.upper().eq("UNKNOWN")
    status = out.get("classification_status", pd.Series("", index=out.index)).astype(str)
    cand = unknown & cats.map(lambda c: c == frozenset({PS1})) & ~status.isin({"SOLAR_SYSTEM", "WITHIN_LARGE_GALAXY"})
    if "parent_object_id" in out:  # a measurement of a galaxy already grouped under it (2.34.0)
        cand &= out.parent_object_id.isna()
    n = pd.to_numeric(
        out.get("pan_starrs1_dr2_meanobject__nDetections", pd.Series(np.nan, index=out.index)), errors="coerce"
    )
    mags = out[[c for c in (f"std_mag__ps1_{b}" for b in "grizy") if c in out]].apply(pd.to_numeric, errors="coerce")
    cand &= n.le(MAX_DETECTIONS) & mags.notna().sum(axis=1).le(MAX_BANDS) & mags.min(axis=1).le(MAX_PS1_MAG)
    if not cand.any():
        return res
    ls = out[cats.map(lambda c: LS in c)]
    near, count = _neighbours(out[cand], ls, COVERAGE_RADIUS_ARCSEC)
    res[cand] = (near > NO_COUNTERPART_ARCSEC) & (count >= MIN_LS_NEIGHBOURS)
    return res


# Legacy Surveys sources seen only in z (2.55.0).  A Tractor source whose r
# flux was measured (flux_ivar_r > 0) but is not positive, detected in z at
# z >= Z_ONLY_MIN_MAG and in no other survey: in the central 6' of COSMOS
# 9.0 % of such sources (n = 244) have a COSMOS2020 counterpart within 0.5"
# (Weaver et al. 2022, complete to i ~ 26-27), against 3.5 % by chance at the
# COSMOS2020 density and 83.8 % for r-detected LS sources of the same z
# (n = 2,394); median nearest separation 2.49" against 2.20" for random
# positions (WORK_REPORT_2026-11-17.md).  They are mostly noise peaks or
# pieces of other objects, not stars or galaxies; before 2.55 the faint-object
# classifier called 99.9 % of the 14,775 in the 400 stored set A/B products
# STAR.  Such a row is UNKNOWN / UNCONFIRMED.
LS_P = "desi_legacy_surveys_dr10__"
Z_ONLY_MIN_MAG = 20.0
# Detected in another LS band = S/N >= OTHER_BAND_SNR there (g, and i where
# DR10 has it): such a source is not "z only" and keeps its class.
OTHER_BAND_SNR = 3.0


def flag_ls_z_only(out: pd.DataFrame) -> pd.Series:
    """Rows that are Legacy Surveys z-only detections seen by no other survey."""
    res = pd.Series(False, index=out.index)
    if out.empty or "catalogs" not in out or LS_P + "flux_r" not in out:
        return res
    cats = out.catalogs.astype(str).map(lambda s: frozenset(c for c in s.split("|") if c) - LITERATURE)
    num = lambda c: pd.to_numeric(out.get(c, pd.Series(np.nan, index=out.index)), errors="coerce")
    fz = num(LS_P + "flux_z")
    with np.errstate(divide="ignore", invalid="ignore"):
        zmag = 22.5 - 2.5 * np.log10(fz.where(fz > 0))
    other = pd.Series(False, index=out.index)
    for b in ("g", "i"):
        f, iv = num(LS_P + f"flux_{b}"), num(LS_P + f"flux_ivar_{b}")
        other |= (f * np.sqrt(iv.where(iv > 0))).ge(OTHER_BAND_SNR)
    res = (
        cats.map(lambda c: c == frozenset({LS}))
        & num(LS_P + "flux_r").le(0)
        & num(LS_P + "flux_ivar_r").gt(0)
        & zmag.ge(Z_ONLY_MIN_MAG)
        & ~other
    )
    if "parent_object_id" in out:  # a part of a galaxy is already grouped under it
        res &= out.parent_object_id.isna()
    return res.fillna(False).astype(bool)


def apply(out: pd.DataFrame) -> pd.DataFrame:
    """Mark unconfirmed detections: classification_status UNCONFIRMED and the reason."""
    z = flag_ls_z_only(out)
    if z.any():
        out = out.copy()
        out.loc[z, "primary_class"] = "UNKNOWN"
        out.loc[z, "classification_status"] = "UNCONFIRMED"
        if "primary_provenance" in out:
            out.loc[z, "primary_provenance"] = "NONE"
        out.loc[z, "unknown_reason"] = (
            "Legacy Surveys z only (r measured but not detected), no other survey: in COSMOS most such "
            "sources have no COSMOS2020 counterpart, likely noise or a piece of another object"
        )
    f = flag(out)
    if not f.any():
        return out
    out = out.copy()
    n = pd.to_numeric(
        out.get("pan_starrs1_dr2_meanobject__nDetections", pd.Series(np.nan, index=out.index)), errors="coerce"
    )
    out.loc[f, "classification_status"] = "UNCONFIRMED"
    out.loc[f, "unknown_reason"] = [
        f"Pan-STARRS1 only ({int(k) if k == k else '?'} detections), not seen in the deeper Legacy Surveys "
        "imaging: likely an artefact or transient (Chambers+2016; Magnier+2020)"
        for k in n[f]
    ]
    return out
