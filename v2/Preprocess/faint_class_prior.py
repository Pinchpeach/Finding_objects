"""Magnitude- and latitude-dependent star:galaxy prior for faint objects (2.46.0).

The fused probabilities are calibrated on the training mix (about equal
classes), but the real sky mix depends strongly on brightness and on Galactic
latitude.  Stars thin out with height above the disc (Juric et al. 2008, ApJ
673, 864: thin/thick disc scale heights 300/900 pc, halo rho ~ r^-2.8) while
galaxy counts climb steeply, N ~ 10^0.6m at r < 16 (Yasuda et al. 2001, AJ
122, 1104), so by r ~ 21 at high latitude most point-like objects are
galaxies.  Henrion et al. (2011, MNRAS 412, 2286) classify stars and galaxies
with exactly this prior -- the type-specific number counts dN_t/dm in a
reference band -- and halve the mismatch rate against deep SDSS (0.044 ->
0.022) relative to a morphology-only classifier.

The prior here is the class mix of our own top-level classifications (not
the truth labels) in bins of LS r magnitude and |b|, counted over the 200
independent validation regions (sets A and B, 2.45.0 products), with +1
(Laplace) smoothing: ``faint_class_prior.csv``.  For an object classified
STAR or GALAXY from evidence with r >= R_MIN, the STAR and GALAXY
probabilities are multiplied by (bin fraction x 3) -- the training prior is
1/3 per class -- and the class is re-decided if the winner keeps p >= 0.5.
QSO probabilities are left alone: faint quasars are point sources too, and a
star:galaxy prior pushes them to STAR (replay: 28 QSO broken when included).

Measured on the independent regions (2.45.0 replay, 24,663 truth objects),
with the prior table counted on the other set only (A scored with B's table
and vice versa): see v2/LITERATURE_REMAINING_ERRORS_2026-11-06.md.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

TABLE = Path(__file__).resolve().parent / "faint_class_prior.csv"
# 2.52.0: star and galaxy counts of COSMOS2020 truth objects we detect, per
# 0.5 mag of LS r (benchmark/build_faint_prior_cosmos.py, calibration fields
# only).  The 2.46.0 table above counts our own labels in regions centred on
# stellar targets and leans to STAR at the faint end (r = 25: 58 % stars at
# |b| = 40-60 deg against 9 % in COSMOS2020).  Position enters through the
# local Gaia density prior of Stage 5 (galaxy counts are isotropic, star
# counts follow the local stellar density), so this table has no |b| axis.
TABLE_COSMOS = Path(__file__).resolve().parent / "faint_class_prior_cosmos.csv"
SOURCES = ("labels", "cosmos")  # default cosmos since 2.52.0; labels = the 2.46.0 table


def source() -> str:
    v = os.environ.get("V2_FAINT_PRIOR", "cosmos").strip().lower() or "cosmos"
    if v not in SOURCES:
        raise ValueError(f"V2_FAINT_PRIOR={v!r}; known: {SOURCES}")
    return v


R_COLUMN = "std_mag__ls_r"
R_MIN = 20.0
# r non-detections (2.55.0).  A Legacy Surveys source detected in another band
# whose r flux was measured (flux_ivar_r > 0) but is not positive has no
# std_mag__ls_r, so the prior skipped it, and the faint z-only sources were
# left to the evidence alone (labelled STAR; ls_gbm.py).  Its true r is
# fainter than the 3-sigma limit with probability > 99.8 % for Gaussian flux
# errors around a non-positive measurement, so the prior is read at
# r_3sigma = 22.5 - 2.5 log10(3 / sqrt(flux_ivar_r)) (observed AB, the same
# system as std_mag__ls_r and the COSMOS table).  V2_FAINT_PRIOR_UNDETECTED:
# limit (default) or off (2.54 and earlier).
# Only faint z-only sources: an r flux <= 0 on a source seen by Gaia or in
# another survey's r band, or bright in z, is a failed r measurement
# (saturation, masking, blending), not faintness.  In the 400 stored set A/B
# products 1,010 of the 17,827 observed-but-undetected r sources have a Gaia G
# (median 18.6) and 883 have z < 18; 6 of the 8 with spectroscopic truth are
# such stars (APOGEE / LAMOST).  15,104 are fainter than z = 22.
LS = "desi_legacy_surveys_dr10__"
UNDETECTED_SIGMA = 3.0
UNDETECTED_Z_MIN = 20.0
OTHER_BRIGHT = ("gaia_dr3__phot_g_mean_mag", "std_mag__ps1_r", "std_mag__sdss_r")


def undetected_mode() -> str:
    v = os.environ.get("V2_FAINT_PRIOR_UNDETECTED", "limit").strip().lower() or "limit"
    if v not in ("limit", "off"):
        raise ValueError(f"V2_FAINT_PRIOR_UNDETECTED={v!r}; known: limit, off")
    return v


def r_magnitude(df: pd.DataFrame) -> np.ndarray:
    """LS r for the prior: the measured magnitude, or for an r non-detection
    the 3-sigma upper-limit magnitude (NaN where r was not observed)."""
    n = len(df)
    num = lambda c: pd.to_numeric(df[c], errors="coerce").to_numpy(float) if c in df else np.full(n, np.nan)
    r = num(R_COLUMN)
    if undetected_mode() == "off":
        return r
    f, iv, fz = num(LS + "flux_r"), num(LS + "flux_ivar_r"), num(LS + "flux_z")
    with np.errstate(divide="ignore", invalid="ignore"):
        lim = 22.5 - 2.5 * np.log10(UNDETECTED_SIGMA / np.sqrt(np.where(iv > 0, iv, np.nan)))
        zmag = np.where(fz > 0, 22.5 - 2.5 * np.log10(fz), np.nan)
    seen_elsewhere = np.zeros(n, dtype=bool)
    for c in OTHER_BRIGHT:
        seen_elsewhere |= np.isfinite(num(c))
    undetected = (
        ~np.isfinite(r) & np.isfinite(f) & (f <= 0) & np.isfinite(lim) & (zmag >= UNDETECTED_Z_MIN) & ~seen_elsewhere
    )
    return np.where(undetected, lim, r)


R_EDGES = np.arange(16, 25.5, 0.5)
B_EDGES = np.array([0, 20, 40, 60, 91])
MIN_P = 0.5
N_TRAIN_CLASSES = 3


@lru_cache(maxsize=4)
def load_table(path: str | Path = TABLE) -> pd.DataFrame:
    """Smoothed class fractions indexed by (latitude bin, magnitude bin)."""
    t = pd.read_csv(path).set_index(["bb", "rb"])[["STAR", "GALAXY", "QSO"]].astype(float)
    t = t + 1.0
    return t.div(t.sum(axis=1), axis=0)


def abs_b(df: pd.DataFrame) -> np.ndarray:
    ra = pd.to_numeric(df.get("ra", pd.Series(np.nan, index=df.index)), errors="coerce").to_numpy(float)
    dec = pd.to_numeric(df.get("dec", pd.Series(np.nan, index=df.index)), errors="coerce").to_numpy(float)
    a, d = np.radians(ra), np.radians(dec)
    # north Galactic pole at ICRS (192.85948, +27.12825) deg (Hipparcos, ESA 1997)
    sinb = -0.867666135683 * np.cos(d) * np.cos(a) - 0.198076389613 * np.cos(d) * np.sin(a) + 0.455983794521 * np.sin(d)
    return np.degrees(np.abs(np.arcsin(np.clip(sinb, -1, 1))))


@lru_cache(maxsize=4)
def load_cosmos(path: str | Path = TABLE_COSMOS) -> pd.DataFrame:
    """Smoothed (+1) STAR / GALAXY fractions per r bin of the COSMOS2020 counts."""
    t = pd.read_csv(path)
    ns, ng = t.n_star + 1.0, t.n_galaxy + 1.0
    return t.assign(STAR=ns / (ns + ng), GALAXY=ng / (ns + ng))


def cosmos_factors(df: pd.DataFrame, table: pd.DataFrame | None = None) -> np.ndarray:
    table = load_cosmos() if table is None else table
    r = r_magnitude(df)
    out = np.full((len(df), 2), np.nan)
    lo = table.r_lo.to_numpy(float)
    use = np.flatnonzero(np.isfinite(r) & (r >= max(R_MIN, lo[0])))
    if len(use):
        k = np.clip(np.searchsorted(lo, r[use], side="right") - 1, 0, len(lo) - 1)
        out[use] = table[["STAR", "GALAXY"]].to_numpy(float)[k] * N_TRAIN_CLASSES
    return out


def star_galaxy_factors(df: pd.DataFrame, table: pd.DataFrame | None = None, which: str | None = None) -> np.ndarray:
    """(n, 2) multipliers for the STAR and GALAXY probabilities; NaN where the prior does not apply."""
    if which is None:  # an explicit table decides by its format, else V2_FAINT_PRIOR
        which = source() if table is None else ("cosmos" if "r_lo" in table.columns else "labels")
    if which == "cosmos":
        return cosmos_factors(df, table)
    table = load_table() if table is None else table
    r = r_magnitude(df)
    rb = np.digitize(r, R_EDGES)
    bb = np.digitize(abs_b(df), B_EDGES)
    out = np.full((len(df), 2), np.nan)
    use = np.flatnonzero(np.isfinite(r) & (r >= R_MIN))
    if len(use):
        keys = pd.MultiIndex.from_arrays([bb[use], rb[use]], names=["bb", "rb"])
        got = table.reindex(keys)[["STAR", "GALAXY"]].to_numpy(float) * N_TRAIN_CLASSES
        out[use] = got
    return out


def apply(q: np.ndarray, factors: np.ndarray, classes=("STAR", "GALAXY", "QSO")):
    """Re-decide one STAR/GALAXY object: returns (class, confidence, margin) or None if unchanged rules apply."""
    if not np.all(np.isfinite(factors)):
        return None
    w = np.array(q, dtype=float).copy()
    w[classes.index("STAR")] *= factors[0]
    w[classes.index("GALAXY")] *= factors[1]
    w /= w.sum()
    order = np.argsort(-w)
    if w[order[0]] < MIN_P:
        return None
    return classes[order[0]], float(w[order[0]]), float(w[order[0]] - w[order[1]])
