"""Gaia star-galaxy test of the DESI Bright Galaxy Survey (2.42.0).

DESI BGS separates stars from galaxies with Gaia: a Legacy Surveys source is a
galaxy when G - r_raw > 0.6 (an extended source loses flux in Gaia's small
window, so its G is fainter than its total r) or when it has no Gaia
counterpart at all, Gaia being complete well beyond the BGS limit r = 20.175
(Ruiz-Macias et al. 2021, MNRAS 502, 4328; Hahn et al. 2023, AJ 165, 253).
r_raw is the magnitude without Galactic-extinction correction.

In the 400 independent regions (2.41.0) the remaining galaxy errors gathered
in the 2dFGRS SGP strip, where DR10 south often lacks r imaging: resolved LS
galaxies with no Gaia source were called STAR by the colour evidence.  Of the
truth objects that pass the test (extended LS model, uncrowded sky), 828 of
831 without Gaia and 1,059 of 1,079 with G - r > 0.6 are galaxies.

Where r is missing, z < 19.5 or g < 20.5 stands for r < 20 (galaxy colours
r - z ~ 0.4-0.8 and g - r ~ 0.5-1.0 at these magnitudes).  The test needs
Gaia to be complete there: at least KNN + 1 Gaia sources in the search (Gaia
was reached) and a local Gaia density below MAX_GAIA_DENSITY, above which
Gaia's completeness at G ~ 20 drops (Cantat-Gaudin et al. 2023, A&A 669,
A55).  Crowded clusters, the Magellanic bars and the Bulge are thereby left
out.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

_s = importlib.util.spec_from_file_location("v2_qso_options_bgs", Path(__file__).resolve().parent / "qso_options.py")
QSO_OPT = importlib.util.module_from_spec(_s)
_s.loader.exec_module(QSO_OPT)

LS = "desi_legacy_surveys_dr10__"
EXTENDED = {"REX", "EXP", "DEV", "SER"}
G_MINUS_R = 0.6
R_MAX = 20.0
Z_MAX, G_MAX = 19.5, 20.5  # stand-ins for r < 20 when r is missing
MAX_GAIA_DENSITY = 1.0e5  # deg^-2
P_GALAXY = 0.98
BASIS = "Gaia star-galaxy test (DESI BGS)"


def _col(df, name):
    return pd.to_numeric(df[name], errors="coerce").to_numpy(float) if name in df else np.full(len(df), np.nan)


def _raw_mag(df, band):
    """LS magnitude without extinction correction; the harmonised one where fluxes are absent."""
    f = _col(df, f"{LS}flux_{band}")
    with np.errstate(divide="ignore", invalid="ignore"):
        m = np.where(f > 0, 22.5 - 2.5 * np.log10(f), np.nan)
    return np.where(np.isfinite(f), m, _col(df, f"std_mag__ls_{band}"))


def galaxy_test(df: pd.DataFrame) -> np.ndarray:
    """True for a resolved LS source that the BGS Gaia test calls a galaxy."""
    n = len(df)
    if n == 0 or f"{LS}type" not in df:
        return np.zeros(n, bool)
    typ = df[f"{LS}type"].astype(str).str.strip().str.upper().isin(EXTENDED).to_numpy()
    g, r, z = (_raw_mag(df, b) for b in "grz")
    G = _col(df, "gaia_dr3__phot_g_mean_mag")
    dens = QSO_OPT.density_prior(df)  # min(1, rho_ref / rho); NaN without Gaia coverage
    covered = np.isfinite(dens) & (dens >= QSO_OPT.RHO_REF / MAX_GAIA_DENSITY)
    bright = np.where(np.isfinite(r), r < R_MAX, (z < Z_MAX) | (g < G_MAX))
    no_gaia = ~np.isfinite(G) & bright
    with np.errstate(invalid="ignore"):
        faint_in_gaia = np.isfinite(G) & np.isfinite(r) & (G - r > G_MINUS_R)
    return typ & covered & (no_gaia | faint_in_gaia)
