"""Known or moving Solar System objects among single-survey detections (2.29.0).

A main-belt asteroid moves ~0.25 deg/day, so a survey catalogue built from
several epochs records it as a short-lived detection that no other catalogue
(taken at other epochs) shares.  Such objects are not stars, galaxies or
quasars and stayed UNKNOWN (field RA 20, 7.8 deg from the ecliptic, had twice
the density of Pan-STARRS1-only UNKNOWN objects of fields at |beta| > 50 deg).

Two routes, both from the survey's own measurements (no extra queries):

* Pan-STARRS1 DR2 ``objInfoFlag``: MOST_SOLSYS_DET (0x400) -- most of the
  object's detections matched a known Solar System object in the PS1
  pipeline (Flewelling et al. 2020, ApJS 251, 7; MAST PS1 object flags).
  HAS_SOLSYS_DET (0x200, at least one detection) is used only for objects
  with at most MAX_PS1_DETECTIONS detections, where one moving detection is
  most of the object.
* SDSS PhotoObj velocity (rowv, colv; deg/day), measured from the ~5 min
  between the r, i, u, z, g exposures: the SDSS Moving Object Catalog
  selection 0.05 < v < 0.5 deg/day for point sources (type 6) at
  14.5 < r < 21.5 (Ivezic et al. 2001, AJ 122, 2749; ~95 % complete, ~6 %
  contamination in later releases), here with v >= 3 sigma_v instead of
  their photometric flags.  Without the type and magnitude limits the first
  field test labelled a faint galaxy (type 3, r = 22.3, v = 0.12 +- 0.03)
  that SkyBoT shows no known object near.

Only objects that no other survey catalogue shares are considered: a moving
detection cannot be associated with detections from other epochs.
"""

from __future__ import annotations
import math

PS1 = "Pan-STARRS1 DR2 MeanObject"
SDSS = "SDSS DR18 PhotoObj"
HAS_SOLSYS_DET, MOST_SOLSYS_DET = 0x200, 0x400
MAX_PS1_DETECTIONS = 3
SDSS_V_RANGE = (0.05, 0.5)  # deg/day
SDSS_V_SIGMA = 3.0
SDSS_R_RANGE = (14.5, 21.5)  # PSF r
LITERATURE = {"SIMBAD", "NED"}


def _num(row, key):
    try:
        x = float(row.get(key))
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def match(row) -> dict | None:
    """{'route', 'basis'} when the object is a Solar System object, else None."""
    cats = {c for c in str(row.get("catalogs") or "").split("|") if c} - LITERATURE
    if cats == {PS1}:
        flag = _num(row, "pan_starrs1_dr2_meanobject__objInfoFlag")
        n = _num(row, "pan_starrs1_dr2_meanobject__nDetections")
        if flag is not None:
            flag = int(flag)
            if flag & MOST_SOLSYS_DET:
                return {
                    "route": "PS1_SOLSYS",
                    "basis": "Pan-STARRS1: most detections match a known Solar System object",
                }
            if flag & HAS_SOLSYS_DET and n is not None and n <= MAX_PS1_DETECTIONS:
                return {
                    "route": "PS1_SOLSYS",
                    "basis": f"Pan-STARRS1: a detection matches a known Solar System object ({int(n)} detections)",
                }
    if cats == {SDSS}:
        p = "sdss_dr18_photoobj__"
        rv, cv, re, ce = (_num(row, p + k) for k in ("rowv", "colv", "rowvErr", "colvErr"))
        r = _num(row, p + "psfMag_r")
        point = _num(row, p + "type") == 6
        if (
            point
            and r is not None
            and SDSS_R_RANGE[0] < r < SDSS_R_RANGE[1]
            and None not in (rv, cv, re, ce)
            and re > 0
            and ce > 0
        ):
            v, sv = math.hypot(rv, cv), math.hypot(re, ce)
            if SDSS_V_RANGE[0] < v < SDSS_V_RANGE[1] and v >= SDSS_V_SIGMA * sv:
                return {
                    "route": "SDSS_MOVING",
                    "basis": f"SDSS apparent motion {v:.2f} +- {sv:.2f} deg/day (moving object; Ivezic+2001)",
                }
    return None
