"""Nonparametric colour-space class evidence (k nearest neighbours).

Stars, galaxies and quasars occupy curved, overlapping regions of optical/IR
colour space (the stellar locus, e.g. Covey et al. 2007; the mid-IR excess of
galaxies and quasars used by DESI target selection, Zhou et al. 2023 and
Chaussidon et al. 2023).  A linear model on colours cannot follow the stellar
locus, so it learns whatever split the training set rewards (e.g. "red point
source = star"), which breaks for faint objects without a morphology
measurement.  kNN classification in colour space (Ball et al. 2006, ApJ 650,
497) has no such shape restriction.

The reference set holds Legacy Surveys colours of spectroscopically classified
benchmark objects (train split only).  An object is compared only with
reference objects measured in the same colours (at least two), so a missing
colour is never imputed.  Output is the Laplace-smoothed class fraction among
the k nearest neighbours; Stage 5 learns how much to trust it.
"""

from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

COLORS = ("ls_g_r_color", "ls_r_z_color", "ls_z_w1_color", "ls_w1_w2_color")
# Pan-STARRS1 PSF colours cover the whole sky north of Dec -30 (also where the
# Legacy Surveys are missing or unavailable).  Not dereddened: PS1 rows carry
# no extinction, so this set is less reliable at low Galactic latitude.
PS1_COLORS = ("ps1_g_r_color", "ps1_r_i_color", "ps1_i_z_color", "ps1_z_y_color")
COLOR_SETS = {"LS-CKNN-001": COLORS, "PS1-CKNN-001": PS1_COLORS}
# A colour enters only if its propagated error (``<colour>_err``) is at most this.
MAX_COLOR_ERR = 0.2
CLASSES = ("STAR", "GALAXY", "QSO")
REFERENCE_PATH = Path(__file__).with_name("color_reference.csv.gz")
K = 31
MIN_COLORS = 2
# Objects per distance block: each block holds CHUNK x n_reference float64 (256 x 8820
# = 18 MB) plus temporaries. 1024 peaked at 137 MB and ran 4x slower (cache misses).
CHUNK = 256


def load_reference(path=REFERENCE_PATH):
    path = Path(path)
    if not path.exists():
        return None
    ref = pd.read_csv(path)
    return ref if "truth_class" in ref.columns else None


def color_matrix(df: pd.DataFrame, colors) -> np.ndarray:
    """Colours as floats; NaN where missing or where ``<colour>_err`` > MAX_COLOR_ERR."""
    cols = []
    for c in colors:
        v = pd.to_numeric(df[c], errors="coerce") if c in df else pd.Series(np.nan, index=df.index)
        if f"{c}_err" in df:
            v = v.where(pd.to_numeric(df[f"{c}_err"], errors="coerce") <= MAX_COLOR_ERR)
        cols.append(v.to_numpy(float))
    return np.column_stack(cols)


def class_fractions(df: pd.DataFrame, ref: pd.DataFrame, k: int = K, ids=None, colors=COLORS):
    """Return (n, 3) smoothed STAR/GALAXY/QSO fractions; NaN rows lack colours.

    ``ids`` (optional, aligned with ``df``) are matched against ``ref.id`` so a
    reference object never counts itself (leave-one-out on the train split).
    """
    X = color_matrix(df, colors)
    if not all(c in ref for c in colors):
        return np.full((len(df), len(CLASSES)), np.nan)
    R = ref[list(colors)].to_numpy(float)
    y = ref["truth_class"].map({c: i for i, c in enumerate(CLASSES)}).to_numpy()
    rid = ref["id"].astype(str).to_numpy() if ids is not None and "id" in ref else None
    out = np.full((len(df), len(CLASSES)), np.nan)
    present = ~np.isnan(X)
    patterns = {}
    for i, p in enumerate(map(tuple, present)):
        if sum(p) >= MIN_COLORS:
            patterns.setdefault(p, []).append(i)
    for p, rows in patterns.items():
        cols = np.array(p)
        cand = np.flatnonzero(~np.isnan(R[:, cols]).any(axis=1))
        kk = min(k, len(cand) - 1)
        if kk < 1:
            continue
        Rc = R[np.ix_(cand, cols)]
        yc = y[cand]
        rn = (Rc * Rc).sum(axis=1)
        pos = {v: j for j, v in enumerate(rid[cand])} if rid is not None else {}
        rows = np.array(rows)
        for s in range(0, len(rows), CHUNK):
            r = rows[s : s + CHUNK]
            Xr = X[np.ix_(r, cols)]
            D = (Xr * Xr).sum(axis=1)[:, None] + rn[None, :] - 2.0 * Xr @ Rc.T
            if pos:
                for a, oid in enumerate(np.asarray(ids)[r]):
                    j = pos.get(str(oid))
                    if j is not None:
                        D[a, j] = np.inf
            nn = np.argpartition(D, kk - 1, axis=1)[:, :kk]
            counts = np.stack([(yc[nn] == c).sum(axis=1) for c in range(len(CLASSES))], axis=1)
            out[r] = (counts + 1.0) / (kk + len(CLASSES))
    return out
