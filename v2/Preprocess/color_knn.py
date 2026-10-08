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
CLASSES = ("STAR", "GALAXY", "QSO")
REFERENCE_PATH = Path(__file__).with_name("color_reference.csv.gz")
K = 31
MIN_COLORS = 2
CHUNK = 1024


def load_reference(path=REFERENCE_PATH):
    path = Path(path)
    if not path.exists():
        return None
    ref = pd.read_csv(path)
    return ref if {"truth_class", *COLORS} <= set(ref.columns) else None


def class_fractions(df: pd.DataFrame, ref: pd.DataFrame, k: int = K, ids=None):
    """Return (n, 3) smoothed STAR/GALAXY/QSO fractions; NaN rows lack colours.

    ``ids`` (optional, aligned with ``df``) are matched against ``ref.id`` so a
    reference object never counts itself (leave-one-out on the train split).
    """
    X = np.column_stack([pd.to_numeric(df[c], errors="coerce").to_numpy(float) if c in df else np.full(len(df), np.nan)
                         for c in COLORS])
    R = ref[list(COLORS)].to_numpy(float)
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
        Rc = R[np.ix_(cand, cols)]; yc = y[cand]; rn = (Rc * Rc).sum(axis=1)
        pos = {v: j for j, v in enumerate(rid[cand])} if rid is not None else {}
        rows = np.array(rows)
        for s in range(0, len(rows), CHUNK):
            r = rows[s:s + CHUNK]
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
