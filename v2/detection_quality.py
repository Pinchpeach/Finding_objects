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


def apply(out: pd.DataFrame) -> pd.DataFrame:
    """Mark unconfirmed detections: classification_status UNCONFIRMED and the reason."""
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
