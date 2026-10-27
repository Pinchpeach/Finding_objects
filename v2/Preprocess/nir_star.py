"""Bright clean 2MASS point sources as stars by number counts (2.41.0).

Young stars inside bright nebulae and crowded cluster stars often carry no
usable classification evidence: the nebula raises the Gaia BP/RP excess C*
(their proper motions are then gated), Gaia DSC and Pan-STARRS morphology
call them extended, and the embedded ones have no optical detection at all.
In the 400 independent regions (sets A and B, 2.40.0) 55 spectroscopic stars
with Ks < 13 were NO_EVIDENCE and 9 more CONFLICT, against 2-3 galaxies.

What decides it is the sky density of each class at such brightness:

* stars: 10^3 - 10^4 deg^-2 at Ks < 14 at |b| < 20 deg and > 1,000 deg^-2
  even in the "low-confusion" high-latitude fields (2MASS All-Sky Release
  Explanatory Supplement, Skrutskie et al. 2006, AJ 131, 1163);
* galaxies: ~20 deg^-2 at Ks < 13.5, and the 2MASS Extended Source
  Catalog is complete and reliable to Ks = 13.5 (Jarrett et al. 2000, AJ
  119, 2498), so they are resolved there and their Point Source Catalog
  entries carry gal_contam (Xflg) > 0;
* quasars: 0.081 deg^-2 unreddened at K <= 14 (Maddox et al. 2008, MNRAS
  386, 1605), plus 25-60 % red quasars (Glikman et al. 2007, ApJ 667, 673).

So a clean PSC point source with Ks < 13 and gal_contam = 0 is a star at
>= 25:1 against galaxies even at the Galactic pole, >= 100:1 at |b| < 20
deg, and >= 10^4:1 against quasars.  In the ONC the X-ray-detected AGN seen
through the cloud have no NIR counterpart and the NIR counterparts of members
are "nearly always brighter" (Getman et al. 2005, ApJS 160, 353).

The prior is used only where the evidence cannot decide: an object with no
evidence at all, or with conflicting strong evidence of which one is STAR.
Quality: ph_qual A or B (S/N >= 7) in H and Ks, cc_flg 0 in Ks (no artefact)
and gal_contam 0 (2MASS Explanatory Supplement sec. 4.5 and 4.7).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TMASS = "2mass_psc__"
KS_MAX = 13.0  # Vega
LOW_LATITUDE_DEG = 20.0
# Prior odds as probabilities: 25:1 at high latitude, 100:1 at |b| < 20 deg.
P_HIGH_LATITUDE = 25 / 26
P_LOW_LATITUDE = 100 / 101
BASIS = "2MASS point-source counts"


def _col(df, name):
    return df[name] if name in df else pd.Series(np.nan, index=df.index)


def _flags(s, n):
    """Flag strings as n characters; VizieR may deliver cc_flg 000 as the number 0."""
    s = s.astype(object).where(s.notna(), "")
    return s.map(lambda v: (str(int(v)) if isinstance(v, float) and v == int(v) else str(v)).strip().zfill(n))


def _abs_b(df):
    ra = pd.to_numeric(_col(df, "ra"), errors="coerce").to_numpy(float)
    dec = pd.to_numeric(_col(df, "dec"), errors="coerce").to_numpy(float)
    a, d = np.radians(ra), np.radians(dec)
    sinb = -0.867666135683 * np.cos(d) * np.cos(a) - 0.198076389613 * np.cos(d) * np.sin(a) + 0.455983794521 * np.sin(d)
    return np.degrees(np.abs(np.arcsin(np.clip(sinb, -1, 1))))


def bright_point_source(df: pd.DataFrame) -> np.ndarray:
    """True for a clean 2MASS PSC point source brighter than KS_MAX."""
    if f"{TMASS}Qflg" not in df or f"{TMASS}Xflg" not in df:
        return np.zeros(len(df), bool)  # flags not collected: no claim
    ks = pd.to_numeric(_col(df, f"{TMASS}Kmag"), errors="coerce")
    q = _flags(_col(df, f"{TMASS}Qflg"), 3)
    cc = _flags(_col(df, f"{TMASS}Cflg"), 3)
    xf = pd.to_numeric(_col(df, f"{TMASS}Xflg"), errors="coerce")
    ok = (ks < KS_MAX) & q.str[1].isin(["A", "B"]) & q.str[2].isin(["A", "B"]) & cc.str[2].eq("0") & xf.eq(0)
    return ok.to_numpy(bool)


def star_probability(df: pd.DataFrame) -> np.ndarray:
    """Count-prior STAR probability (higher at low Galactic latitude)."""
    b = _abs_b(df)
    return np.where(np.isfinite(b) & (b < LOW_LATITUDE_DEG), P_LOW_LATITUDE, P_HIGH_LATITUDE)
