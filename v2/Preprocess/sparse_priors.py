"""Class priors for objects without any classification evidence (2.43.0).

Two kinds of objects reach Stage 5 with no evidence at all, although what
was detected already says much about the class (LITERATURE_WEAKNESSES_2026-10-29.md):

* Gaia sources in crowded fields.  In globular clusters 20-30 % of Gaia
  stars with a 5- or 6-parameter solution lack BP/RP photometry (Fabricius
  et al. 2021, A&A 649, A5), and in the cores many have only a 2-parameter
  solution (no parallax or proper motion), so neither the Gaia colour rules
  nor the motion rules can speak.  Where the local Gaia density is above
  CROWDED_GAIA_DENSITY, a Gaia source brighter than G_MAX is a star: the
  cores hold 10^5-10^6 stars deg^-2 against a few quasars and galaxies
  deg^-2 at G < 19.  Outside crowded fields only 5-6-parameter sources are
  taken, because "most of the galaxies have only two-parameter astrometry in
  Gaia DR3" (Gaia Collaboration, Bailer-Jones et al. 2023, A&A 674, A41).
  Independent regions A+B (2.42.0): all 18 evidence-less Gaia sources at
  G < 19 were stars (16 in globular clusters, all 2-parameter at >= 10^5.5
  deg^-2); of all 2-parameter G < 19 truth objects at >= 10^5 deg^-2, 45 are
  stars and 1 a galaxy (inside a starburst galaxy, which the large-galaxy
  status handles first).
* Mid-IR-only detections.  An AllWISE source seen by no optical survey with
  W2 - W3 > 2 (Vega) has the colour of a dusty star-forming galaxy; stellar
  photospheres have W2 - W3 ~ 0 (Wright et al. 2010, AJ 140, 1868; Jarrett
  et al. 2011, ApJ 735, 112).  Embedded young stars and AGB stars are red
  too, so the rule is used only at |b| >= MIN_ABS_B.  Regions A+B: 15 of 15
  such objects were galaxies.

Both are priors for evidence-free objects; they never override evidence.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

_s = importlib.util.spec_from_file_location("v2_qso_options_sparse", Path(__file__).resolve().parent / "qso_options.py")
QSO_OPT = importlib.util.module_from_spec(_s)
_s.loader.exec_module(QSO_OPT)

G_MAX = 19.0
CROWDED_GAIA_DENSITY = 1.0e5  # deg^-2
P_GAIA_STAR = 0.98
GAIA_BASIS = "Gaia point-source counts"

W2_W3_MIN = 2.0  # Vega
W3_MIN_SNR = 3.0
W3_MAX_VEGA = 11.3  # AllWISE W3 ~5-sigma depth, used when snr3 is not at hand
MIN_ABS_B = 20.0
P_WISE_GALAXY = 0.95
WISE_BASIS = "mid-IR colour of a mid-IR-only source"
WISE_AB_VEGA = {"w2": 3.339, "w3": 5.174}  # Jarrett et al. 2011
OPTICAL = ("Gaia DR3", "DESI Legacy Surveys DR10", "Pan-STARRS1 DR2 MeanObject", "SDSS DR18 PhotoObj")


def _col(df, name):
    return pd.to_numeric(df[name], errors="coerce").to_numpy(float) if name in df else np.full(len(df), np.nan)


def _catalogs(df):
    return df["catalogs"].fillna("").astype(str) if "catalogs" in df else pd.Series("", index=df.index)


def _abs_b(df):
    a, d = np.radians(_col(df, "ra")), np.radians(_col(df, "dec"))
    sinb = -0.867666135683 * np.cos(d) * np.cos(a) - 0.198076389613 * np.cos(d) * np.sin(a) + 0.455983794521 * np.sin(d)
    return np.degrees(np.abs(np.arcsin(np.clip(sinb, -1, 1))))


def gaia_point_star(df: pd.DataFrame) -> np.ndarray:
    """True for a Gaia source that the counts make a star (see module doc)."""
    n = len(df)
    if n == 0:
        return np.zeros(n, bool)
    g = _col(df, "gaia_dr3__phot_g_mean_mag")
    in_gaia = _catalogs(df).str.contains("Gaia DR3", regex=False).to_numpy() & (g < G_MAX)
    full_solution = np.isfinite(_col(df, "gaia_dr3__parallax"))
    dens = QSO_OPT.density_prior(df)  # min(1, rho_ref / rho), NaN without Gaia coverage
    crowded = np.isfinite(dens) & (dens <= QSO_OPT.RHO_REF / CROWDED_GAIA_DENSITY)
    return in_gaia & (full_solution | crowded)


def wise_only_galaxy(df: pd.DataFrame) -> np.ndarray:
    """True for a mid-IR-only AllWISE source with the colour of a star-forming galaxy."""
    n = len(df)
    if n == 0:
        return np.zeros(n, bool)
    cats = _catalogs(df)
    only_ir = cats.str.contains("AllWISE", regex=False).to_numpy().copy()
    for c in OPTICAL:
        only_ir &= ~cats.str.contains(c, regex=False).to_numpy()
    # Vega catalogue magnitudes, else the harmonised AB ones (compact products)
    w2 = np.where(np.isfinite(_col(df, "allwise__W2mag")), _col(df, "allwise__W2mag"), _col(df, "std_mag__wise_w2") - WISE_AB_VEGA["w2"])
    w3 = np.where(np.isfinite(_col(df, "allwise__W3mag")), _col(df, "allwise__W3mag"), _col(df, "std_mag__wise_w3") - WISE_AB_VEGA["w3"])
    snr3 = _col(df, "allwise__snr3")
    detected = np.where(np.isfinite(snr3), snr3 >= W3_MIN_SNR, w3 <= W3_MAX_VEGA)
    with np.errstate(invalid="ignore"):
        red = (w2 - w3) > W2_W3_MIN
    return only_ir & detected & red & (_abs_b(df) >= MIN_ABS_B)
